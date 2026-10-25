#!/usr/bin/env python3
"""ProductCraft Engineering Practices: read-only safety check for SQL migrations.

Reads SQL migration files and flags statements that commonly cause downtime or
data loss when applied to a live database: destructive drops, in-place renames
and type changes, NOT NULL columns without a default, index and constraint
builds that block writes, unbatched full-table updates and missing lock
timeouts.

It never connects to a database, never edits files and never uses the network.
Findings are prompts to review, not verdicts. A flagged statement can be
correct (for example the final contract step of an expand/contract change), and
a clean result does not prove that a migration is safe. Test migrations against
a production-sized copy before applying them anywhere that matters.

Acknowledge a reviewed statement with a comment directly above it, inside it,
or after its semicolon on the same line:

    -- migration-check: allow DROP_COLUMN reads removed in release 2026.10

or for file-level findings, anywhere in the file:

    -- migration-check: allow-file NO_LOCK_TIMEOUT tool sets lock_timeout
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
DIALECTS = ("postgres", "mysql", "sqlite", "generic")
SEVERITY_ORDER = {"HIGH": 0, "WARN": 1, "INFO": 2}
MAX_SIZE = 2 * 1024 * 1024
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "out", "coverage", "target", "vendor", ".cache",
}
ALL = frozenset(DIALECTS)
PG = frozenset({"postgres"})
LOCK_DIALECTS = frozenset({"postgres", "mysql"})
MYSQL = frozenset({"mysql"})


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    dialects: frozenset
    title: str
    safer: str


RULE_LIST = [
    Rule("DROP_TABLE", "HIGH", ALL,
         "Drops a table: running code that still uses it fails, and the data is gone.",
         "Remove every read and write in an earlier release, confirm there is no remaining usage, "
         "keep a verified backup, and drop it in its own migration."),
    Rule("DROP_SCHEMA_OR_DATABASE", "HIGH", ALL,
         "Drops a schema or database.",
         "This rarely belongs in an application migration. Confirm intent with the owner and a "
         "verified backup first."),
    Rule("TRUNCATE", "HIGH", ALL,
         "Deletes every row in the table.",
         "Confirm the data is disposable; otherwise archive it or delete in batches with a WHERE clause."),
    Rule("DROP_COLUMN", "HIGH", ALL,
         "Drops a column: code that still selects or writes it fails, and the data is gone.",
         "Contract step only. First deploy code that no longer reads or writes the column (and tell "
         "ORMs that cache column lists to ignore it), then drop it in a later migration."),
    Rule("RENAME", "HIGH", ALL,
         "Renames a table or column in place: the previous application version breaks during the deploy.",
         "Expand/contract: add the new name, write both, backfill, move reads, then drop the old "
         "name in a later release (a view can bridge a table rename)."),
    Rule("ALTER_COLUMN_TYPE", "WARN", ALL,
         "Changes a column type: often rewrites the table under an exclusive lock and can break "
         "readers of the old type.",
         "Add a column of the new type, dual-write, backfill in batches, switch reads, drop the old "
         "column later. Some changes are metadata-only (for example widening varchar in PostgreSQL); "
         "check the documentation for your version."),
    Rule("NOT_NULL_NO_DEFAULT", "HIGH", ALL,
         "Adds a NOT NULL column without a default: fails on a non-empty table in PostgreSQL and "
         "SQLite; MySQL silently fills an implicit default.",
         "Add the column as nullable (or with a constant default), backfill, then enforce NOT NULL "
         "in a later step."),
    Rule("ADD_COLUMN_REWRITE", "WARN", PG,
         "Adds a column whose value forces a full table rewrite under an exclusive lock (volatile "
         "default, serial, identity or stored generated column).",
         "Add the column as nullable without that default, set the default for new rows, and "
         "backfill existing rows in batches."),
    Rule("SET_NOT_NULL", "WARN", PG,
         "SET NOT NULL scans the whole table while holding an exclusive lock.",
         "Add CHECK (col IS NOT NULL) NOT VALID, run VALIDATE CONSTRAINT in a separate step, then "
         "SET NOT NULL (PostgreSQL 12+ skips the scan) and drop the check."),
    Rule("FK_VALIDATES_NOW", "WARN", PG,
         "Adds a foreign key that is validated immediately, blocking writes on both tables while "
         "it scans.",
         "Add it with NOT VALID, then run ALTER TABLE ... VALIDATE CONSTRAINT in a separate migration."),
    Rule("CHECK_VALIDATES_NOW", "WARN", PG,
         "Adds a CHECK constraint that scans the table while holding an exclusive lock.",
         "Add it with NOT VALID, then run VALIDATE CONSTRAINT separately; validation does not block "
         "reads or writes."),
    Rule("UNIQUE_OR_PK_LOCKS", "WARN", PG,
         "Adds a UNIQUE or PRIMARY KEY constraint, which builds its index while holding an "
         "exclusive lock.",
         "Run CREATE UNIQUE INDEX CONCURRENTLY first, then ALTER TABLE ... ADD CONSTRAINT ... "
         "UNIQUE USING INDEX (or PRIMARY KEY USING INDEX)."),
    Rule("INDEX_LOCKS_WRITES", "WARN", PG,
         "CREATE INDEX without CONCURRENTLY blocks inserts, updates and deletes on the table until "
         "the build finishes.",
         "Use CREATE INDEX CONCURRENTLY outside a transaction block; if it fails, drop the INVALID "
         "index and retry."),
    Rule("DROP_INDEX_LOCKS", "INFO", PG,
         "DROP INDEX takes an exclusive lock on the table and waits behind running queries.",
         "Use DROP INDEX CONCURRENTLY outside a transaction block."),
    Rule("CONCURRENTLY_IN_TRANSACTION", "WARN", PG,
         "A CONCURRENTLY operation inside BEGIN ... COMMIT fails: PostgreSQL does not allow it in a "
         "transaction block.",
         "Put it in its own migration and turn off the migration tool's per-migration transaction "
         "for that file."),
    Rule("FULL_TABLE_UPDATE", "WARN", ALL,
         "UPDATE without WHERE rewrites every row in one long transaction (locks, table bloat, "
         "replication lag).",
         "Run a batched, resumable backfill (keyset over the primary key, small transactions, "
         "throttled) outside the schema migration."),
    Rule("FULL_TABLE_DELETE", "HIGH", ALL,
         "DELETE without WHERE removes every row.",
         "Add the intended WHERE clause, delete large sets in batches, and confirm with the data owner."),
    Rule("DATA_BACKFILL", "INFO", ALL,
         "Changes data inside a schema migration: fine for small tables, risky for large ones.",
         "If it touches many rows, move it to a batched, resumable backfill and verify completion "
         "with a count query."),
    Rule("EXPLICIT_LOCK", "WARN", ALL,
         "Explicit table lock: blocks other sessions until the transaction ends.",
         "Avoid it in migrations; if it is unavoidable, keep the transaction short and set a lock timeout."),
    Rule("BLOCKING_MAINTENANCE", "WARN", ALL,
         "VACUUM FULL, CLUSTER, non-concurrent REINDEX or OPTIMIZE TABLE rebuild data and block "
         "writes (often reads too) while they run.",
         "Schedule it as an operations task with the owner, not inside an application deploy; "
         "PostgreSQL 12+ supports REINDEX CONCURRENTLY."),
    Rule("NO_LOCK_TIMEOUT", "INFO", LOCK_DIALECTS,
         "Statements that need strong locks run without a lock timeout: if a long transaction holds "
         "the table, the migration waits and new queries queue behind it.",
         "Set PostgreSQL lock_timeout (and statement_timeout) or MySQL lock_wait_timeout at the start "
         "and retry on timeout, unless the migration tool already sets one."),
    Rule("MYSQL_NO_ALGORITHM", "INFO", MYSQL,
         "ALTER TABLE without an ALGORITHM clause may silently fall back to a blocking table copy.",
         "State ALGORITHM=INSTANT, or ALGORITHM=INPLACE, LOCK=NONE, so MySQL refuses instead of "
         "copying; for large tables use an online schema change tool such as gh-ost or "
         "pt-online-schema-change."),
    Rule("MISSING_DOWN", "INFO", ALL,
         "Up migration has no matching .down.sql file.",
         "Write and test the down migration, or state in the file why the change is forward-only."),
]
RULES: Dict[str, Rule] = {r.code: r for r in RULE_LIST}


@dataclass
class Statement:
    line: int
    end_line: int
    text: str
    comments: List[str] = field(default_factory=list)


@dataclass
class Finding:
    file: str
    line: int
    code: str
    status: str = "open"
    ack_reason: str = ""

    def as_dict(self) -> dict:
        rule = RULES[self.code]
        data = {
            "file": self.file,
            "line": self.line,
            "code": self.code,
            "severity": rule.severity,
            "status": self.status,
            "title": rule.title,
            "safer": rule.safer,
        }
        if self.status == "acknowledged":
            data["ack_reason"] = self.ack_reason
        return data


# --------------------------------------------------------------------------- parsing

DOLLAR_TAG = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$")


def split_statements(sql: str, dialect: str = "postgres") -> List[Statement]:
    """Split SQL into statements with comments removed and literals blanked.

    The returned text is upper-case with single spaces. String literals become
    '' and quoted identifiers become QID_<NAME>, so keywords inside them never
    match a rule. Comments are kept per statement for allow directives.
    """
    newlines = [i for i, ch in enumerate(sql) if ch == "\n"]

    def line_of(pos: int) -> int:
        return bisect_right(newlines, pos - 1) + 1 if pos > 0 else 1

    statements: List[Statement] = []
    buf: List[str] = []
    comments: List[str] = []
    first_sig: Optional[int] = None
    n = len(sql)
    i = 0

    def add_comment(text: str, pos: int) -> None:
        # A comment on the same line as the previous statement's semicolon belongs to it.
        if first_sig is None and statements and line_of(pos) == statements[-1].end_line:
            statements[-1].comments.append(text)
        else:
            comments.append(text)

    while i < n:
        c = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if (c == "-" and nxt == "-") or (c == "#" and dialect == "mysql"):
            end = sql.find("\n", i)
            end = n if end == -1 else end
            add_comment(sql[i:end], i)
            buf.append(" ")
            i = end
            continue
        if c == "/" and nxt == "*":
            end = sql.find("*/", i + 2)
            end = n if end == -1 else end + 2
            add_comment(sql[i:end], i)
            buf.append(" ")
            i = end
            continue
        if c == "'":
            prev = sql[i - 1] if i > 0 else ""
            before = sql[i - 2] if i > 1 else ""
            backslash = prev in "eE" and not (before.isalnum() or before == "_")
            if dialect == "mysql":
                backslash = True
            j = i + 1
            while j < n:
                if backslash and sql[j] == "\\":
                    j += 2
                    continue
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            if first_sig is None:
                first_sig = i
            buf.append("''")
            i = j + 1
            continue
        if c in "\"`":
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            name = re.sub(r"\W", "_", sql[i + 1:j]).upper()
            if first_sig is None:
                first_sig = i
            buf.append("QID_" + name)
            i = j + 1
            continue
        if c == "$":
            m = DOLLAR_TAG.match(sql, i)
            if m:
                tag = m.group(0)
                end = sql.find(tag, m.end())
                end = n if end == -1 else end + len(tag)
                if first_sig is None:
                    first_sig = i
                buf.append(" '' ")
                i = end
                continue
        if c == ";":
            if first_sig is not None:
                text = " ".join("".join(buf).split()).upper()
                statements.append(Statement(line_of(first_sig), line_of(i), text, comments))
            buf, comments, first_sig = [], [], None
            i += 1
            continue
        if first_sig is None and not c.isspace():
            first_sig = i
        buf.append(c)
        i += 1

    if first_sig is not None:
        text = " ".join("".join(buf).split()).upper()
        if text:
            statements.append(Statement(line_of(first_sig), line_of(n - 1 if n else 0), text, comments))
    elif comments and statements:
        statements[-1].comments.extend(comments)
    return statements


def split_top_level(text: str) -> List[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


ALLOW_RE = re.compile(r"migration-check:\s*(allow-file|allow)\b(.*)", re.IGNORECASE)


def parse_allow(comments: Sequence[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return ({code: reason} for the statement, {code: reason} for the file)."""
    local: Dict[str, str] = {}
    whole: Dict[str, str] = {}
    for comment in comments:
        for raw_line in comment.splitlines():
            m = ALLOW_RE.search(raw_line)
            if not m:
                continue
            target = whole if m.group(1).lower() == "allow-file" else local
            tokens = re.split(r"[\s,]+", m.group(2).replace("*/", " ").strip())
            codes, rest = [], []
            for idx, tok in enumerate(tokens):
                if tok.upper() in RULES and not rest:
                    codes.append(tok.upper())
                else:
                    rest = tokens[idx:]
                    break
            reason = " ".join(t for t in rest if t).strip()
            for code in codes:
                target[code] = reason
    return local, whole


# --------------------------------------------------------------------------- rules

CREATE_TABLE_RE = re.compile(
    r"^CREATE (?:OR REPLACE )?(?:(?:GLOBAL |LOCAL )?(?:TEMP|TEMPORARY|UNLOGGED) )?TABLE "
    r"(?:IF NOT EXISTS )?([^\s(]+)")
ALTER_TABLE_RE = re.compile(r"^ALTER TABLE (?:IF EXISTS )?(?:ONLY )?([^\s(]+)\s*(.*)$")
INDEX_RE = re.compile(r"^CREATE (?:UNIQUE )?INDEX\b")
INDEX_TABLE_RE = re.compile(r"\bON (?:ONLY )?([^\s(]+)")
BEGIN_RE = re.compile(r"^(?:BEGIN(?: (?:TRANSACTION|WORK|ISOLATION\b.*))?|START TRANSACTION\b.*)$")
END_RE = re.compile(r"^(?:COMMIT|END|ROLLBACK|ABORT)\b")
PG_TIMEOUT_RE = re.compile(r"^SET (?:SESSION |LOCAL )?LOCK_TIMEOUT\b")
MYSQL_TIMEOUT_RE = re.compile(r"^SET\b.*\bLOCK_WAIT_TIMEOUT\b")
VOLATILE_RE = re.compile(
    r"\bDEFAULT \(?\s*(?:RANDOM|CLOCK_TIMESTAMP|TIMEOFDAY|GEN_RANDOM_UUID|UUID_GENERATE_V[14]|UUIDV7|NEXTVAL)\s*\(")
SERIAL_RE = re.compile(r"\b(?:SMALL|BIG)?SERIAL\d?\b")
GENERATED_STORED_RE = re.compile(r"\bGENERATED ALWAYS AS\b.*\bSTORED\b")
IDENTITY_RE = re.compile(r"\bGENERATED (?:ALWAYS|BY DEFAULT) AS IDENTITY\b")
NOT_DROPPABLE_COLUMN = (
    "CONSTRAINT", "DEFAULT", "NOT", "INDEX", "KEY", "PRIMARY", "FOREIGN", "IDENTITY",
    "EXPRESSION", "CHECK", "PARTITION", "SYSTEM",
)
NON_COLUMN_ADD = (
    "CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "INDEX", "KEY", "FULLTEXT",
    "SPATIAL", "PARTITION", "EXCLUDE",
)


def _base(name: str) -> str:
    return name.rstrip("(").split(".")[-1]


def _first_word(text: str) -> str:
    return text.split(" ", 1)[0] if text else ""


def alter_action_codes(action: str) -> List[str]:
    codes: List[str] = []
    if action.startswith("DROP "):
        rest = action[5:]
        if rest.startswith("COLUMN ") or _first_word(rest) not in NOT_DROPPABLE_COLUMN:
            codes.append("DROP_COLUMN")
    elif action.startswith("RENAME "):
        if _first_word(action[7:]) not in ("CONSTRAINT", "INDEX", "KEY"):
            codes.append("RENAME")
    elif re.match(r"^ALTER (?:COLUMN )?\S+ (?:SET DATA )?TYPE\b", action) or re.match(r"^(?:MODIFY|CHANGE)\b", action):
        codes.append("ALTER_COLUMN_TYPE")
    elif re.match(r"^ALTER (?:COLUMN )?\S+ SET NOT NULL\b", action):
        codes.append("SET_NOT_NULL")
    elif action.startswith("ADD "):
        rest = action[4:]
        if rest.startswith("CONSTRAINT "):
            rest = rest.split(" ", 2)[2] if rest.count(" ") >= 2 else ""
        word = _first_word(rest)
        not_valid = "NOT VALID" in action
        if word == "FOREIGN" and not not_valid:
            codes.append("FK_VALIDATES_NOW")
        elif word.startswith("CHECK") and not not_valid:
            codes.append("CHECK_VALIDATES_NOW")
        elif (word == "UNIQUE" or rest.startswith("PRIMARY KEY")) and "USING INDEX" not in action:
            codes.append("UNIQUE_OR_PK_LOCKS")
        elif word not in NON_COLUMN_ADD:
            col = re.sub(r"^(?:COLUMN )?(?:IF NOT EXISTS )?", "", rest)
            has_default = " DEFAULT " in f" {col} "
            rewrites = bool(VOLATILE_RE.search(col) or SERIAL_RE.search(col)
                            or GENERATED_STORED_RE.search(col) or IDENTITY_RE.search(col))
            requires_value = re.search(r"\bNOT NULL\b|\bPRIMARY KEY\b", col)
            fills_itself = has_default or "GENERATED" in col or SERIAL_RE.search(col)
            if requires_value and not fills_itself:
                codes.append("NOT_NULL_NO_DEFAULT")
            if rewrites:
                codes.append("ADD_COLUMN_REWRITE")
            if re.search(r"\bUNIQUE\b|\bPRIMARY KEY\b", col):
                codes.append("UNIQUE_OR_PK_LOCKS")
    return codes


def statement_codes(stmt: Statement, created: set, in_tx: bool) -> Tuple[List[str], bool]:
    """Return (codes, takes_strong_lock) for one normalized statement."""
    t = stmt.text
    codes: List[str] = []
    locking = False
    if re.match(r"^DROP TABLE\b", t):
        codes.append("DROP_TABLE")
        locking = True
    elif re.match(r"^DROP (?:SCHEMA|DATABASE)\b", t):
        codes.append("DROP_SCHEMA_OR_DATABASE")
    elif re.match(r"^TRUNCATE\b", t):
        codes.append("TRUNCATE")
        locking = True
    elif re.match(r"^RENAME TABLE\b", t):
        codes.append("RENAME")
        locking = True
    elif t.startswith("ALTER TABLE "):
        m = ALTER_TABLE_RE.match(t)
        if m and _base(m.group(1)) not in created:
            locking = True
            actions = split_top_level(m.group(2))
            for action in actions:
                codes.extend(alter_action_codes(action))
            if "ALGORITHM" not in t:
                codes.append("MYSQL_NO_ALGORITHM")
    elif INDEX_RE.match(t):
        concurrent = " CONCURRENTLY " in f" {t} "
        tm = INDEX_TABLE_RE.search(t)
        existing = not (tm and _base(tm.group(1)) in created)
        if concurrent and in_tx:
            codes.append("CONCURRENTLY_IN_TRANSACTION")
        if not concurrent and existing:
            codes.append("INDEX_LOCKS_WRITES")
            locking = True
    elif re.match(r"^DROP INDEX\b", t):
        if " CONCURRENTLY " in f" {t} ":
            if in_tx:
                codes.append("CONCURRENTLY_IN_TRANSACTION")
        else:
            codes.append("DROP_INDEX_LOCKS")
            locking = True
    elif re.match(r"^REINDEX\b", t):
        if " CONCURRENTLY " in f" {t} ":
            if in_tx:
                codes.append("CONCURRENTLY_IN_TRANSACTION")
        else:
            codes.append("BLOCKING_MAINTENANCE")
            locking = True
    elif re.match(r"^(?:VACUUM FULL|VACUUM \(.*\bFULL\b|CLUSTER|OPTIMIZE TABLE)\b", t):
        codes.append("BLOCKING_MAINTENANCE")
        locking = True
    elif re.match(r"^LOCK\b", t):
        codes.append("EXPLICIT_LOCK")
        locking = True
    elif re.match(r"^UPDATE\b", t):
        codes.append("DATA_BACKFILL" if re.search(r"\bWHERE\b", t) else "FULL_TABLE_UPDATE")
    elif re.match(r"^DELETE\b", t):
        codes.append("DATA_BACKFILL" if re.search(r"\bWHERE\b", t) else "FULL_TABLE_DELETE")
    elif re.match(r"^INSERT INTO\b.*\bSELECT\b", t):
        codes.append("DATA_BACKFILL")
    return codes, locking


def check_sql(sql: str, display: str, dialect: str, sibling_down_exists: Optional[bool] = None) -> Tuple[List[Finding], int]:
    """Check one file's SQL text. Returns (findings, statement_count)."""
    statements = split_statements(sql, dialect)
    all_comments = [c for s in statements for c in s.comments]
    _, file_allow = parse_allow(all_comments)
    created: set = set()
    in_tx = False
    timeout_set = False
    lock_timeout_reported = False
    findings: List[Finding] = []

    def emit(line: int, code: str, local_allow: Dict[str, str]) -> None:
        if dialect not in RULES[code].dialects:
            return
        if any(f.line == line and f.code == code for f in findings):
            return
        if code in local_allow or code in file_allow:
            reason = local_allow.get(code, file_allow.get(code, ""))
            findings.append(Finding(display, line, code, "acknowledged", reason))
        else:
            findings.append(Finding(display, line, code))

    for stmt in statements:
        t = stmt.text
        local_allow, _ = parse_allow(stmt.comments)
        if BEGIN_RE.match(t) and "ATOMIC" not in t:
            in_tx = True
            continue
        if END_RE.match(t):
            in_tx = False
            continue
        if (dialect == "postgres" and PG_TIMEOUT_RE.match(t)) or (dialect == "mysql" and MYSQL_TIMEOUT_RE.match(t)):
            timeout_set = True
            continue
        cm = CREATE_TABLE_RE.match(t)
        if cm:
            created.add(_base(cm.group(1)))
            continue
        codes, locking = statement_codes(stmt, created, in_tx)
        for code in codes:
            emit(stmt.line, code, local_allow)
        if locking and not timeout_set and not lock_timeout_reported and dialect in RULES["NO_LOCK_TIMEOUT"].dialects:
            emit(stmt.line, "NO_LOCK_TIMEOUT", local_allow)
            lock_timeout_reported = True

    if sibling_down_exists is False:
        emit(1, "MISSING_DOWN", {})
    return findings, len(statements)


# --------------------------------------------------------------------------- files and output

def discover(paths: Sequence[str]) -> Tuple[List[Tuple[Path, str]], List[str]]:
    """Return ([(path, display_name)], errors) for .sql files, sorted by display name."""
    found: Dict[str, Path] = {}
    errors: List[str] = []
    for arg in paths:
        p = Path(arg)
        if p.is_file():
            found[p.as_posix()] = p
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in files:
                    if name.lower().endswith(".sql"):
                        fp = Path(root) / name
                        found[fp.as_posix()] = fp
        else:
            errors.append(f"path not found: {arg}")
    return [(found[k], k) for k in sorted(found)], errors


def down_sibling(path: Path) -> Optional[bool]:
    name = path.name
    if not name.lower().endswith(".up.sql"):
        return None
    down = path.with_name(name[: -len(".up.sql")] + ".down.sql")
    return down.is_file()


def run(paths: Sequence[str], dialect: str) -> dict:
    files, errors = discover(paths)
    findings: List[Finding] = []
    skipped: List[str] = []
    statement_total = 0
    for path, display in files:
        try:
            if path.stat().st_size > MAX_SIZE:
                skipped.append(f"{display}: larger than {MAX_SIZE} bytes")
                continue
            sql = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            skipped.append(f"{display}: {exc.strerror or 'unreadable'}")
            continue
        file_findings, count = check_sql(sql, display, dialect, down_sibling(path))
        findings.extend(file_findings)
        statement_total += count
    findings.sort(key=lambda f: (f.file, f.line, SEVERITY_ORDER[RULES[f.code].severity], f.code))
    summary = {"HIGH": 0, "WARN": 0, "INFO": 0, "acknowledged": 0}
    for f in findings:
        if f.status == "acknowledged":
            summary["acknowledged"] += 1
        else:
            summary[RULES[f.code].severity] += 1
    return {
        "tool": "migration_check",
        "version": VERSION,
        "dialect": dialect,
        "files_scanned": len(files) - len(skipped),
        "statements": statement_total,
        "errors": errors,
        "skipped": skipped,
        "summary": summary,
        "findings": [f.as_dict() for f in findings],
        "note": "Advisory heuristics. Review each finding and test the migration on a production-sized copy.",
    }


def render_text(result: dict) -> str:
    out = [
        f"migration_check {result['version']} | dialect {result['dialect']} | "
        f"{result['files_scanned']} file(s), {result['statements']} statement(s)",
    ]
    for err in result["errors"]:
        out.append(f"ERROR {err}")
    for skip in result["skipped"]:
        out.append(f"SKIPPED {skip}")
    open_items = [f for f in result["findings"] if f["status"] == "open"]
    acked = [f for f in result["findings"] if f["status"] == "acknowledged"]
    if not result["findings"] and result["files_scanned"]:
        out.append("No findings. A clean result does not prove the migration is safe.")
    for f in open_items:
        out.append(f"{f['severity']:<5} {f['file']}:{f['line']}  {f['code']}")
        out.append(f"      {f['title']}")
        out.append(f"      Safer: {f['safer']}")
    for f in acked:
        reason = f" ({f['ack_reason']})" if f.get("ack_reason") else ""
        out.append(f"ACK   {f['file']}:{f['line']}  {f['code']}{reason}")
    s = result["summary"]
    out.append(f"Summary: HIGH {s['HIGH']}, WARN {s['WARN']}, INFO {s['INFO']}, acknowledged {s['acknowledged']}")
    out.append(result["note"])
    return "\n".join(out) + "\n"


def list_rules() -> str:
    lines = []
    for r in RULE_LIST:
        dialects = "all" if r.dialects == ALL else ",".join(sorted(r.dialects))
        lines.append(f"{r.code:<28} {r.severity:<5} {dialects:<15} {r.title}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migration_check.py",
        description=(
            "Read-only check of SQL migration files for statements that commonly cause downtime or "
            "data loss on a live database. Never connects to a database, edits files or uses the network."
        ),
        epilog=(
            "Examples:\n"
            "  migration_check.py db/migrations/20261024_add_status.sql\n"
            "  migration_check.py --dialect mysql --format json migrations/\n"
            "  migration_check.py --strict prisma/migrations   # exit 1 on open HIGH or WARN\n\n"
            "Acknowledge a reviewed statement with a comment above it or after its semicolon:\n"
            "  -- migration-check: allow DROP_COLUMN reads removed in release 2026.10\n"
            "Exit codes: 0 done, 1 open HIGH/WARN findings with --strict, 2 usage or path error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", help=".sql files or directories to scan (directories are searched recursively)")
    parser.add_argument("--dialect", choices=DIALECTS, default="postgres",
                        help="SQL dialect; database-specific rules apply only to their dialect (default: postgres)")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="output format (default: text)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any open HIGH or WARN finding remains")
    parser.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_rules:
        sys.stdout.write(list_rules())
        return 0
    if not args.paths:
        parser.print_usage(sys.stderr)
        sys.stderr.write("migration_check.py: error: give at least one .sql file or directory\n")
        return 2
    result = run(args.paths, args.dialect)
    if args.format == "json":
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_text(result))
    if result["errors"] or (result["files_scanned"] == 0 and not result["skipped"]):
        if not result["errors"]:
            sys.stderr.write("migration_check.py: error: no .sql files found\n")
        return 2
    if args.strict and (result["summary"]["HIGH"] or result["summary"]["WARN"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
