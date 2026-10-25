#!/usr/bin/env python3
"""ProductCraft Firebase security-rules check. Offline, read-only, deterministic.

Reads Cloud Firestore and Cloud Storage rules files (*.rules) and Realtime
Database rules (database.rules.json), found through firebase.json or by their
usual names, and lists leads:

  FB-OPEN           access allowed with no effective condition
  FB-TEST-MODE      access open to everyone until a date ("test mode")
  FB-SIGNED-IN      access allowed to any signed-in user, which can include
                    anonymous and self-registered accounts
  FB-UNVALIDATED    a create or update allowed without looking at the
                    incoming data (request.resource)
  RTDB-OPEN, RTDB-TEST-MODE, RTDB-SIGNED-IN
                    the same for Realtime Database .read and .write rules
  FB-MISSING-FILE   firebase.json names a rules file that does not exist
  FB-PARSE-ERROR    a rules file could not be parsed and was not checked

Leads are not findings. Confirm each one with emulator tests (see
references/mobile-apps.md) before reporting it. The tool reads local files
only, never contacts Firebase, never modifies anything and never prints the
rule conditions themselves.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", ".venv", "venv",
    "__pycache__", "dist", "build", "out", "coverage", ".next", ".nuxt",
    ".cache", ".turbo", "vendor", "Pods", "DerivedData", ".gradle", ".idea",
    "target", ".firebase",
}
DEFAULT_NAMES = {"firestore.rules", "storage.rules", "database.rules.json"}
MAX_FILE_BYTES = 1_000_000
MAX_WALK_FILES = 50_000
LEVELS = ("high", "medium", "low", "info")
LEVEL_RANK = {name: rank for rank, name in enumerate(LEVELS)}
WRITE_METHODS = {"write", "create", "update", "delete"}
VALUE_WRITE_METHODS = {"write", "create", "update"}
KNOWN_METHODS = {"read", "get", "list"} | WRITE_METHODS

# Order used to combine conditions: lower is weaker (more open).
KIND_RANK = {"open": 0, "test_mode": 1, "signed_in": 2, "conditional": 3, "deny": 4}

SIGNED_IN_ATOMS = {
    "rules": [
        r"request\.auth!=null", r"null!=request\.auth",
        r"request\.auth\.uid!=null", r"null!=request\.auth\.uid",
        r"!\(request\.auth==null\)", r"!\(request\.auth\.uid==null\)",
        r"request\.auth\.token\.email_verified(==true)?",
        r"request\.auth\.token\.firebase\.sign_in_provider!=['\"]anonymous['\"]",
    ],
    "database": [
        r"auth!=null", r"null!=auth", r"auth\.uid!=null", r"null!=auth\.uid",
        r"!\(auth==null\)", r"auth\.token\.email_verified(==true)?",
        r"auth\.provider!=['\"]anonymous['\"]",
    ],
}
SIGNED_IN_RE = {k: re.compile("^(?:" + "|".join(v) + ")$") for k, v in SIGNED_IN_ATOMS.items()}
TEST_MODE_RULES_RE = re.compile(r"^request\.time<=?timestamp\.date\((\d{4}),(\d{1,2}),(\d{1,2})\)$")
TEST_MODE_DB_RE = re.compile(r"^now<=?(\d{10,16})$")
RECURSIVE_WILDCARD_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*=\*\*\}")
SERVICE_PREFIXES = (
    re.compile(r"^/databases/\{[^}/]+\}/documents(?=/|$)"),
    re.compile(r"^/b/\{[^}/]+\}/o(?=/|$)"),
)


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------


def strip_comments(text: str) -> str:
    """Blank out // and /* */ comments outside string literals, keeping offsets and line breaks."""
    out = []
    i, n, quote = 0, len(text), None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote or c == "\n":
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            out.append(c)
            i += 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end == -1 else end
            out.append(" " * (end - i))
            i = end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in text[i:end]))
            i = end
            continue
        out.append(c)
        i += 1
    return "".join(out)


def squash(expr: str) -> str:
    """Remove whitespace outside string literals."""
    out, quote, i = [], None, 0
    while i < len(expr):
        c = expr[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < len(expr):
                out.append(expr[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            out.append(c)
        elif not c.isspace():
            out.append(c)
        i += 1
    return "".join(out)


def skip_string(text: str, i: int) -> int:
    """Return the index just after the string literal starting at text[i]."""
    quote, i = text[i], i + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return i


def find_matching(text: str, i: int) -> int:
    """text[i] is an opening bracket; return the index of its partner, or -1."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = [pairs[text[i]]]
    j = i + 1
    while j < len(text):
        c = text[j]
        if c in "\"'":
            j = skip_string(text, j)
            continue
        if c in pairs:
            stack.append(pairs[c])
        elif c in ")]}":
            if not stack or c != stack[-1]:
                return -1
            stack.pop()
            if not stack:
                return j
        j += 1
    return -1


def split_top(expr: str, op: str) -> list[str]:
    """Split expr on op where op is outside brackets and strings."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(expr):
        c = expr[i]
        if c in "\"'":
            i = skip_string(expr, i)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and expr.startswith(op, i):
            parts.append(expr[start:i])
            i += len(op)
            start = i
            continue
        i += 1
    parts.append(expr[start:])
    return parts


def strip_outer_parens(expr: str) -> str:
    while expr.startswith("(") and find_matching(expr, 0) == len(expr) - 1:
        expr = expr[1:-1]
    return expr


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


# --------------------------------------------------------------------------
# Condition classification
# --------------------------------------------------------------------------


def classify(expr: str, dialect: str) -> tuple[str, str | None]:
    """Return (kind, expiry) for a squashed condition. kind is one of KIND_RANK."""
    e = strip_outer_parens(expr)
    if e in ("", "true"):
        return "open", None
    if e == "false":
        return "deny", None
    alternatives = split_top(e, "||")
    if len(alternatives) > 1:
        results = [classify(part, dialect) for part in alternatives]
        return min(results, key=lambda r: KIND_RANK[r[0]])
    terms = split_top(e, "&&")
    if len(terms) > 1:
        results = [classify(part, dialect) for part in terms]
        kinds = {kind for kind, _ in results}
        if "deny" in kinds:
            return "deny", None
        if kinds <= {"open", "test_mode", "signed_in"}:
            expiry = next((x for kind, x in results if kind == "test_mode"), None)
            if "signed_in" in kinds:
                return "signed_in", expiry
            if "test_mode" in kinds:
                return "test_mode", expiry
            return "open", None
        return "conditional", None
    if SIGNED_IN_RE[dialect].match(e):
        return "signed_in", None
    if dialect == "rules":
        m = TEST_MODE_RULES_RE.match(e)
        if m:
            year, month, day = (int(g) for g in m.groups())
            return "test_mode", f"{year:04d}-{month:02d}-{day:02d}"
    else:
        m = TEST_MODE_DB_RE.match(e)
        if m:
            millis = int(m.group(1))
            stamp = _dt.datetime.fromtimestamp(millis / 1000, tz=_dt.timezone.utc)
            return "test_mode", stamp.strftime("%Y-%m-%d")
    return "conditional", None


def call_spans(expr: str, name: str):
    """Yield (start, end) spans of calls to name(...) in a squashed expression."""
    for m in re.finditer(r"(?<![A-Za-z0-9_.])" + re.escape(name) + r"\(", expr):
        open_at = m.end() - 1
        close_at = find_matching(expr, open_at)
        if close_at != -1:
            yield m.start(), close_at + 1


def inline_functions(expr: str, functions: dict) -> str:
    """Replace calls to known single-return functions whose bodies ignore their parameters."""
    for _ in range(6):
        if len(expr) > MAX_EXPR_CHARS:
            break
        changed = False
        for name in sorted(functions):
            body, params = functions[name]
            if body is None or any(re.search(r"(?<![A-Za-z0-9_.])" + re.escape(p) + r"(?![A-Za-z0-9_])", body) for p in params):
                continue
            spans = list(call_spans(expr, name))
            for start, end in reversed(spans):
                expr = expr[:start] + "(" + body + ")" + expr[end:]
                changed = True
        if not changed:
            break
    return expr


def mentions(expr: str, needle: str, functions: dict, depth: int = 0) -> bool:
    """True if expr, or any known function it calls (transitively), mentions needle."""
    if needle in expr:
        return True
    if depth > 6:
        return False
    for name in sorted(functions):
        body, _ = functions[name]
        if body is not None and re.search(r"(?<![A-Za-z0-9_.])" + re.escape(name) + r"\(", expr):
            if mentions(body, needle, functions, depth + 1):
                return True
    return False


# --------------------------------------------------------------------------
# Firestore and Storage rules language
# --------------------------------------------------------------------------

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FUNCTION_HEAD_RE = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*\{")
MAX_EXPR_CHARS = 50_000


def parse_rules(text: str):
    """Parse a rules file. Returns (service, functions, allows) or raises ValueError."""
    src = strip_comments(text)
    n = len(src)
    stack: list[tuple[str, str]] = []
    functions: dict[str, tuple[str | None, list[str]]] = {}
    allows = []
    service = None
    i = 0
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c in "\"'":
            i = skip_string(src, i)
            continue
        if c == "{":
            stack.append(("block", ""))
            i += 1
            continue
        if c == "}":
            if not stack:
                raise ValueError(f"unexpected '}}' on line {line_of(src, i)}")
            stack.pop()
            i += 1
            continue
        m = IDENT_RE.match(src, i)
        if not m:
            i += 1
            continue
        word, j = m.group(0), m.end()
        if i > 0 and (src[i - 1].isalnum() or src[i - 1] in "_."):
            i = j
            continue
        if word == "service":
            brace = src.find("{", j)
            if brace == -1:
                raise ValueError(f"'service' without a block on line {line_of(src, i)}")
            service = src[j:brace].strip()
            stack.append(("service", service))
            i = brace + 1
        elif word == "match":
            k = j
            while k < n and src[k].isspace():
                k += 1
            start = k
            while k < n and not src[k].isspace():
                if src[k] == "{":
                    if k == start or src[k - 1] != "/":
                        break  # the block starts here; wildcards always follow a '/'
                    close = src.find("}", k)
                    if close == -1:
                        raise ValueError(f"unclosed wildcard on line {line_of(src, k)}")
                    k = close + 1
                    continue
                k += 1
            path = src[start:k]
            while k < n and src[k].isspace():
                k += 1
            if k >= n or src[k] != "{":
                raise ValueError(f"'match {path}' without a block on line {line_of(src, i)}")
            stack.append(("match", path))
            i = k + 1
        elif word == "function":
            fm = FUNCTION_HEAD_RE.match(src, j)
            if not fm:
                raise ValueError(f"malformed function on line {line_of(src, i)}")
            open_at = fm.end() - 1
            close_at = find_matching(src, open_at)
            if close_at == -1:
                raise ValueError(f"unclosed function body on line {line_of(src, i)}")
            name = fm.group(1)
            params = [p.strip() for p in fm.group(2).split(",") if p.strip()]
            body = squash(src[open_at + 1:close_at])
            single = re.fullmatch(r"return(.+?);?", body, re.S)
            value = squash(single.group(1)) if single and "let" not in body.split("return", 1)[0] else None
            if name in functions and functions[name][0] != value:
                value = None  # defined twice with different bodies: do not guess
            functions[name] = (value, params)
            i = close_at + 1
        elif word == "allow":
            k = j
            depth = 0
            while k < n:
                ch = src[k]
                if ch in "\"'":
                    k = skip_string(src, k)
                    continue
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                    if depth < 0:
                        break
                elif ch == ";" and depth == 0:
                    break
                k += 1
            if k >= n or src[k] != ";":
                raise ValueError(f"'allow' without a closing ';' on line {line_of(src, i)}")
            statement = src[j:k]
            head, sep, cond = statement.partition(":")
            methods = [m_.strip() for m_ in head.split(",") if m_.strip()]
            unknown = [m_ for m_ in methods if m_ not in KNOWN_METHODS]
            if not methods or unknown:
                raise ValueError(f"unknown method {', '.join(unknown) or '(none)'} on line {line_of(src, i)}")
            condition = squash(cond)
            if sep:
                if not condition.startswith("if"):
                    raise ValueError(f"expected 'if' after ':' on line {line_of(src, i)}")
                condition = condition[2:]
            paths = [p for kind, p in stack if kind == "match"]
            allows.append({"line": line_of(src, i), "methods": methods, "condition": condition, "path": "".join(paths)})
            i = k + 1
        elif word == "rules_version":
            end = src.find(";", j)
            i = n if end == -1 else end + 1
        else:
            i = j
    if stack:
        raise ValueError("unbalanced braces: a block is never closed")
    return service, functions, allows


def display_path(path: str) -> str:
    for prefix in SERVICE_PREFIXES:
        path = prefix.sub("", path, count=1)
    return path or "/"


def check_rules_file(rel: str, text: str, hint: str | None):
    service, functions, allows = parse_rules(text)
    if service == "cloud.firestore":
        kind = "firestore"
    elif service == "firebase.storage":
        kind = "storage"
    else:
        kind = hint if hint in ("firestore", "storage") else "rules"
    leads = []
    for rule in allows:
        cond = inline_functions(rule["condition"], functions)
        verdict, expiry = classify(cond, "rules")
        methods = rule["methods"]
        shown = display_path(rule["path"])
        method_text = ", ".join(methods)
        everywhere = bool(RECURSIVE_WILDCARD_RE.search(rule["path"]))
        scope = (" It applies to every path below this one, and matching rules are combined with OR,"
                 " so stricter rules elsewhere do not limit it.") if everywhere else ""
        writes = bool(set(methods) & WRITE_METHODS)
        base = {"file": rel, "line": rule["line"], "service": kind, "path": shown, "methods": methods}
        if verdict == "open":
            leads.append(dict(base, id="FB-OPEN", level="high",
                              message=f"{method_text} allowed with no effective condition: anyone with the app's public config can do this.{scope}"))
        elif verdict == "test_mode":
            leads.append(dict(base, id="FB-TEST-MODE", level="high",
                              message=f"{method_text} open to everyone until {expiry} (a test-mode rule); after that date it denies all access.{scope}"))
        elif verdict == "signed_in":
            until = f" until {expiry}" if expiry else ""
            leads.append(dict(base, id="FB-SIGNED-IN", level="high" if writes else "medium",
                              message=f"{method_text} allowed{until} for any signed-in user, with no ownership or role check; anonymous and self-registered accounts count unless those sign-in methods are off.{scope}"))
        elif verdict == "conditional" and set(methods) & VALUE_WRITE_METHODS:
            if not mentions(cond, "request.resource", functions):
                what = ("any size and content type" if kind == "storage"
                        else "every field, including roles, owners, plans or credits")
                leads.append(dict(base, id="FB-UNVALIDATED", level="low",
                                  message=f"{method_text} never inspects request.resource, so the writer chooses {what}."))
    return kind, len(allows), leads


# --------------------------------------------------------------------------
# Realtime Database rules (JSON with comments)
# --------------------------------------------------------------------------


class _JsonParser:
    """Minimal JSON parser that remembers the line of every object key."""

    def __init__(self, text: str):
        self.s, self.i = text, 0

    def error(self, what: str):
        raise ValueError(f"{what} on line {line_of(self.s, self.i)}")

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t\r\n":
            self.i += 1

    def value(self):
        self.ws()
        if self.i >= len(self.s):
            self.error("unexpected end of file")
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"':
            return self.string()
        for word, val in (("true", True), ("false", False), ("null", None)):
            if self.s.startswith(word, self.i):
                self.i += len(word)
                return val
        m = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?").match(self.s, self.i)
        if m:
            self.i = m.end()
            return float(m.group(0)) if (m.group(1) or m.group(2)) else int(m.group(0))
        self.error("unexpected character")

    def string(self):
        end = skip_string(self.s, self.i)
        if end > len(self.s) or self.s[end - 1] != '"':
            self.error("unterminated string")
        raw = self.s[self.i:end]
        self.i = end
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self.error("invalid string")

    def obj(self):
        self.i += 1
        items = []
        self.ws()
        if self.s.startswith("}", self.i):
            self.i += 1
            return {"__items__": items}
        while True:
            self.ws()
            if not self.s.startswith('"', self.i):
                self.error("expected a quoted key")
            line = line_of(self.s, self.i)
            key = self.string()
            self.ws()
            if not self.s.startswith(":", self.i):
                self.error("expected ':'")
            self.i += 1
            items.append((key, self.value(), line))
            self.ws()
            if self.s.startswith(",", self.i):
                self.i += 1
                continue
            if self.s.startswith("}", self.i):
                self.i += 1
                return {"__items__": items}
            self.error("expected ',' or '}'")

    def arr(self):
        self.i += 1
        out = []
        self.ws()
        if self.s.startswith("]", self.i):
            self.i += 1
            return out
        while True:
            out.append(self.value())
            self.ws()
            if self.s.startswith(",", self.i):
                self.i += 1
                continue
            if self.s.startswith("]", self.i):
                self.i += 1
                return out
            self.error("expected ',' or ']'")


def parse_database(text: str):
    parser = _JsonParser(strip_comments(text))
    root = parser.value()
    parser.ws()
    if parser.i != len(parser.s):
        parser.error("unexpected content after the rules object")
    if not isinstance(root, dict):
        raise ValueError("the file is not a JSON object")
    rules = next((v for k, v, _ in root["__items__"] if k == "rules"), None)
    if not isinstance(rules, dict):
        raise ValueError("no top-level \"rules\" object")
    return rules


def check_database_file(rel: str, text: str):
    rules = parse_database(text)
    leads = []
    count = 0

    def walk(node: dict, path: str):
        nonlocal count
        for key, value, line in node["__items__"]:
            if key in (".read", ".write"):
                count += 1
                if isinstance(value, bool):
                    verdict, expiry = ("open", None) if value else ("deny", None)
                elif isinstance(value, str):
                    expr = squash(value).replace("===", "==").replace("!==", "!=")
                    verdict, expiry = classify(expr, "database")
                else:
                    verdict, expiry = "conditional", None
                action = "read" if key == ".read" else "write"
                base = {"file": rel, "line": line, "service": "database", "path": path or "/", "methods": [action]}
                tail = " Realtime Database rules cascade: child rules cannot narrow this grant."
                if verdict == "open":
                    leads.append(dict(base, id="RTDB-OPEN", level="high",
                                      message=f"'{key}' is true: anyone can {action} this path and everything below it.{tail}"))
                elif verdict == "test_mode":
                    leads.append(dict(base, id="RTDB-TEST-MODE", level="high",
                                      message=f"'{key}' is open to everyone until {expiry} (a test-mode rule).{tail}"))
                elif verdict == "signed_in":
                    until = f" until {expiry}" if expiry else ""
                    leads.append(dict(base, id="RTDB-SIGNED-IN", level="high" if action == "write" else "medium",
                                      message=f"'{key}' allows any signed-in user{until}; anonymous and self-registered accounts count unless those sign-in methods are off.{tail}"))
            elif not key.startswith(".") and isinstance(value, dict):
                walk(value, f"{path}/{key}")

    walk(rules, "")
    return count, leads


# --------------------------------------------------------------------------
# Discovery and driver
# --------------------------------------------------------------------------


def walk_files(root: Path):
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            seen += 1
            if seen > MAX_WALK_FILES:
                return
            yield path


def read_text(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"larger than {MAX_FILE_BYTES} bytes; not read")
    return path.read_text(encoding="utf-8", errors="replace")


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def discover(root: Path):
    """Return ({path: service hint}, notes) for rules files under root."""
    found: dict[Path, str | None] = {}
    notes = []
    candidates = list(walk_files(root))
    for path in candidates:
        if path.name != "firebase.json":
            continue
        try:
            config = json.loads(strip_comments(read_text(path)))
        except (ValueError, OSError) as exc:
            notes.append({"file": rel_to(path, root), "line": 1, "id": "FB-PARSE-ERROR", "level": "medium",
                          "service": "config", "path": "", "methods": [],
                          "message": f"could not read firebase.json ({exc.__class__.__name__}); configured rules files may be missed."})
            continue
        if not isinstance(config, dict):
            continue
        for key in ("firestore", "storage", "database"):
            entry = config.get(key)
            entries = entry if isinstance(entry, list) else [entry]
            for item in entries:
                if not isinstance(item, dict) or not isinstance(item.get("rules"), str):
                    continue
                target = (path.parent / item["rules"])
                if target.is_file():
                    found.setdefault(target.resolve(), key)
                else:
                    notes.append({"file": rel_to(path, root), "line": 1, "id": "FB-MISSING-FILE", "level": "info",
                                  "service": key, "path": "", "methods": [],
                                  "message": f"firebase.json names {item['rules']} for {key}, but that file does not exist."})
    for path in candidates:
        if path.resolve() in found:
            continue
        if path.name in DEFAULT_NAMES:
            found[path.resolve()] = {"firestore.rules": "firestore", "storage.rules": "storage",
                                     "database.rules.json": "database"}[path.name]
        elif path.suffix == ".rules":
            try:
                head = strip_comments(read_text(path))
            except (ValueError, OSError):
                continue
            if re.search(r"\bservice\s+(cloud\.firestore|firebase\.storage)\b", head):
                found[path.resolve()] = None
    return found, notes


def check_paths(paths: dict, root: Path):
    files, leads = [], []
    for path in sorted(paths, key=lambda p: rel_to(p, root)):
        hint = paths[path]
        rel = rel_to(path, root)
        is_db = hint == "database" or path.suffix == ".json"
        try:
            text = read_text(path)
            if is_db:
                count, found = check_database_file(rel, text)
                files.append({"file": rel, "service": "database", "rules": count})
            else:
                service, count, found = check_rules_file(rel, text, hint)
                files.append({"file": rel, "service": service, "rules": count})
            leads.extend(found)
        except (ValueError, OSError, UnicodeError) as exc:
            files.append({"file": rel, "service": "database" if is_db else (hint or "rules"), "rules": None})
            leads.append({"file": rel, "line": 1, "id": "FB-PARSE-ERROR", "level": "medium",
                          "service": "database" if is_db else (hint or "rules"), "path": "", "methods": [],
                          "message": f"could not parse ({exc}); this file was not checked."})
    return files, leads


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="firebase_rules.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    ap.add_argument("--root", default=".", help="project folder to search (default: current folder)")
    ap.add_argument("--file", action="append", default=[], metavar="PATH",
                    help="check this rules file instead of searching (repeatable)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--json-out", metavar="PATH", help="also write the JSON result to PATH (mode 0600)")
    ap.add_argument("--fail-on", choices=["never", "high", "medium", "low"], default="never",
                    help="exit 1 when a lead at this level or above exists (for CI)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: --root {args.root} is not a folder", file=sys.stderr)
        return 2
    notes = []
    if args.file:
        paths = {}
        for item in args.file:
            p = Path(item)
            if not p.is_file():
                print(f"error: --file {item} does not exist", file=sys.stderr)
                return 2
            paths[p.resolve()] = None
    else:
        paths, notes = discover(root)
    files, leads = check_paths(paths, root)
    leads.extend(notes)
    leads.sort(key=lambda d: (d["file"], d["line"], LEVEL_RANK[d["level"]], d["id"], d["path"]))
    counts = {level: sum(1 for d in leads if d["level"] == level) for level in LEVELS}
    result = {
        "tool": "firebase_rules.py", "version": VERSION,
        "status": "NOT_APPLICABLE" if not files else ("LEADS" if any(d["level"] != "info" for d in leads) else "NO_LEADS"),
        "files": files, "counts": counts, "leads": leads,
        "note": "Leads, not findings. Confirm each with emulator tests before reporting it.",
    }
    if args.json_out:
        fd = os.open(args.json_out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)
            fh.write("\n")
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if not files:
            print(f"firebase_rules.py {VERSION}: no Firebase rules files found under {args.root} (NOT_APPLICABLE).")
        else:
            summary = ", ".join(f"{level} {counts[level]}" for level in LEVELS if counts[level])
            print(f"firebase_rules.py {VERSION}: {len(leads)} lead(s) in {len(files)} rules file(s)"
                  + (f" ({summary})" if summary else ""))
        for d in leads:
            where = f"{d['file']}:{d['line']}"
            scope = f" {d['path']}" if d["path"] else ""
            methods = f" [{', '.join(d['methods'])}]" if d["methods"] else ""
            print(f"{d['level'].upper():<7} {d['id']:<16} {where}{scope}{methods}: {d['message']}")
        for f in files:
            if f["rules"] is not None:
                print(f"checked {f['file']} ({f['service']}, {f['rules']} rule statement(s))")
        if files:
            print("Leads, not findings: confirm each with emulator tests (references/mobile-apps.md) before reporting it.")
    if args.fail_on != "never":
        limit = LEVEL_RANK[args.fail_on]
        if any(LEVEL_RANK[d["level"]] <= limit for d in leads):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
