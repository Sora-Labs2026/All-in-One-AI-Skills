#!/usr/bin/env python3
"""ProductCraft row-level security check for SQL migrations. Offline, read-only, deterministic.

Reads PostgreSQL migration and schema files (*.sql, in path order, which is
migration order for timestamped names), replays the statements that shape
row-level security, and lists leads for the tables, views and functions that
the API exposes (schema "public" unless --exposed-schema says otherwise):

  RLS-DISABLED          table without row-level security, or with it disabled later
  RLS-NO-POLICY         RLS on, but no policy lets client roles reach any row
  POLICY-TRUE-WRITE     a client role may change rows with no condition
                        (USING (true) on UPDATE, DELETE or ALL; WITH CHECK (true))
  POLICY-TRUE-READ      a client role may read every row (USING (true) on SELECT or ALL)
  POLICY-SIGNED-IN      the only condition is "the user is signed in"
  POLICY-USER-METADATA  a policy trusts user_metadata, which users can edit themselves
  VIEW-BYPASSES-RLS     a view without security_invoker runs with its owner's rights
  MATVIEW-EXPOSED       a materialized view in an exposed schema (it cannot have RLS)
  SECDEF-EXPOSED        a SECURITY DEFINER function callable through the API
  SECDEF-SEARCH-PATH    a SECURITY DEFINER function without a fixed search_path
  PUBLIC-SECRET-ENV     a secret in a client-bundled environment variable (name only)
  DYNAMIC-SQL           a DO block that changes RLS; its effect was not evaluated
  POLICY-UID-PERF       auth.uid() called per row instead of (select auth.uid())

Client roles are PUBLIC, anon and authenticated (add your own with --client-role).
A policy without a TO clause applies to PUBLIC; one without FOR applies to ALL.
An UPDATE or ALL policy without WITH CHECK reuses its USING expression for new
rows, and an INSERT policy without WITH CHECK admits nothing, so neither is
reported. Leads are not findings: confirm each with a test that queries as two
users and as an anonymous caller (references/mobile-apps.md, and the Supabase
reference in modules/integrations/). The tool reads local files only, never
connects to a database, never modifies anything and never prints secret values.
It does not evaluate dynamic SQL, function bodies or default privileges, and it
assumes unqualified names live in "public".

Exit codes: 0 no lead at or above --fail-on, 1 at least one, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", ".venv", "venv",
    "__pycache__", "dist", "build", "out", "coverage", ".next", ".nuxt",
    ".cache", ".turbo", "vendor", "Pods", "DerivedData", ".gradle", ".idea", "target",
}
CODE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".json"}
MAX_SQL_BYTES = 5_000_000
MAX_CODE_BYTES = 1_000_000
MAX_WALK_FILES = 100_000
LEVELS = ("high", "medium", "low", "info")
LEVEL_RANK = {level: i for i, level in enumerate(LEVELS)}
DEFAULT_CLIENT_ROLES = {"public", "anon", "authenticated"}

IDENT = r'(?:"(?:[^"]|"")+"|[A-Za-z_][A-Za-z0-9_$]*)'
QNAME = rf'{IDENT}(?:\s*\.\s*{IDENT})?'
PUBLIC_SECRET_ENV = re.compile(
    r"\b((?:NEXT_PUBLIC|VITE|EXPO_PUBLIC|REACT_APP|NUXT_PUBLIC|GATSBY|PUBLIC)_[A-Z0-9_]*"
    r"(?:SERVICE_ROLE|SECRET|PRIVATE_KEY)[A-Z0-9_]*)\b")


# ---------------------------------------------------------------- SQL reading

def split_statements(text: str):
    """Split SQL into statements. Comments are dropped, dollar-quoted bodies are
    replaced by a placeholder and returned separately, other quoting is kept."""
    out, buf, bodies = [], [], []
    i, n, line, start_line = 0, len(text), 1, 1
    started = False
    dollar = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$")

    def flush():
        nonlocal started
        stmt = "".join(buf).strip()
        if stmt:
            out.append({"line": start_line, "text": stmt, "bodies": list(bodies)})
        buf.clear(); bodies.clear()
        started = False

    while i < n:
        c = text[i]
        is_comment = text.startswith("--", i) or text.startswith("/*", i)
        if not started and not c.isspace() and not is_comment and c != ";":
            start_line, started = line, True
        if c == "-" and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and text.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif text.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            line += text.count("\n", i, j); buf.append(" "); i = j
            continue
        if c == "'":
            backslash = i > 0 and text[i - 1] in "eE" and (i < 2 or not (text[i - 2].isalnum() or text[i - 2] == "_"))
            j = i + 1
            while j < n:
                if backslash and text[j] == "\\":
                    j += 2; continue
                if text[j] == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        j += 2; continue
                    break
                j += 1
            buf.append(text[i:j + 1]); line += text.count("\n", i, j + 1); i = j + 1
            continue
        if c == '"':
            j = i + 1
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2; continue
                    break
                j += 1
            buf.append(text[i:j + 1]); line += text.count("\n", i, j + 1); i = j + 1
            continue
        if c == "$":
            m = dollar.match(text, i)
            if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
                tag = m.group(0)
                j = text.find(tag, m.end())
                j = n if j < 0 else j
                bodies.append(text[m.end():j])
                buf.append(" $body$ ")
                end = min(n, j + len(tag))
                line += text.count("\n", i, end); i = end
                continue
        if c == ";":
            flush(); i += 1
            continue
        if c == "\n":
            line += 1
        buf.append(c); i += 1
    flush()
    return out


def unquote(part: str) -> str:
    part = part.strip()
    if part.startswith('"') and part.endswith('"'):
        return part[1:-1].replace('""', '"')
    return part.lower()


def split_top(s: str, sep: str = ","):
    """Split on sep outside quotes and parentheses."""
    parts, depth, cur, q = [], 0, [], None
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append("".join(cur)); cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def qname(s: str):
    parts = split_top(s, ".")
    if len(parts) == 1:
        return ("public", unquote(parts[0]))
    return (unquote(parts[0]), unquote(parts[1]))


def balanced(s: str, open_idx: int):
    """Return the text inside the parentheses that open at open_idx, and the end index."""
    depth, q = 0, None
    for j in range(open_idx, len(s)):
        ch = s[j]
        if q:
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1:j], j + 1
    return s[open_idx + 1:], len(s)


def clause(rest: str, keyword_re: str):
    m = re.search(keyword_re + r"\s*\(", rest, re.I)
    if not m:
        return None
    expr, _ = balanced(rest, m.end() - 1)
    return expr.strip()


def policy_head(rest: str) -> str:
    """The part of a policy definition before its USING or WITH CHECK expression."""
    m = re.search(r"\busing\s*\(|\bwith\s+check\s*\(", rest, re.I)
    return rest[:m.start()] if m else rest


def roles_of(text: str):
    return [unquote(r) for r in split_top(text) if r]


# ------------------------------------------------------------ expression tests

def _norm(expr: str) -> str:
    e = expr.lower()
    e = re.sub(r"::\s*[a-z_][a-z0-9_]*(\[\])?", "", e)
    e = re.sub(r"\bselect\b", "", e)
    e = re.sub(r"[\s()]", "", e)
    return e


TRUE_FORMS = {"true", "'t'", "'true'", "1=1", "'1'='1'"}
SIGNED_IN_FORMS = {
    "auth.uidisnotnull", "auth.role='authenticated'", "'authenticated'=auth.role",
    "auth.jwtisnotnull", "current_user='authenticated'", "current_role='authenticated'",
    "notauth.uidisnull",
}


def is_true(expr):
    return expr is not None and _norm(expr) in TRUE_FORMS


def is_signed_in_only(expr):
    return expr is not None and _norm(expr) in SIGNED_IN_FORMS


def uses_user_metadata(expr):
    return expr is not None and re.search(r"user_metadata|raw_user_meta_data", expr, re.I) is not None


def unwrapped_uid(expr):
    if expr is None:
        return False
    low = re.sub(r"\s+", " ", expr.lower())
    return "auth.uid()" in low and re.search(r"\(\s*select\s+auth\.uid\(\)\s*\)", low) is None


# -------------------------------------------------------------- replay model

class Model:
    def __init__(self):
        self.tables = {}      # (schema, name) -> dict
        self.policies = {}    # (schema, table, policy) -> dict
        self.views = {}       # (schema, name) -> dict
        self.matviews = {}
        self.functions = {}   # (schema, name) -> dict
        self.revoked = {}     # (schema, name) -> set of roles with access revoked
        self.dynamic = []     # (file, line)

    def apply(self, st, rel):
        raw = re.sub(r"\s+", " ", st["text"]).strip()
        low = raw.lower()
        line = st["line"]
        here = {"file": rel, "line": line}

        if low.startswith("do ") or low == "do $body$" or low.startswith("do $body$"):
            body = " ".join(st["bodies"]).lower()
            if "row level security" in body or "create policy" in body or "create table" in body:
                self.dynamic.append(here)
            return

        m = re.match(rf"create\s+(?:(?:global|local)\s+)?(?:(temp|temporary)\s+)?(?:unlogged\s+)?table\s+(?:if\s+not\s+exists\s+)?({QNAME})", raw, re.I)
        if m:
            if m.group(1):
                return
            key = qname(m.group(2))
            if key not in self.tables:
                self.tables[key] = {**here, "rls": None, "rls_at": None, "force": False}
            return

        m = re.match(rf"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?({QNAME})\s+(.*)$", raw, re.I)
        if m:
            key, rest = qname(m.group(1)), m.group(2)
            r = re.match(rf"rename\s+to\s+({IDENT})", rest, re.I)
            if r:
                self._rename_table(key, (key[0], unquote(r.group(1))))
                return
            r = re.match(rf"set\s+schema\s+({IDENT})", rest, re.I)
            if r:
                self._rename_table(key, (unquote(r.group(1)), key[1]))
                return
            for a in re.finditer(r"\b(enable|disable|force|no\s+force)\s+row\s+level\s+security\b", rest, re.I):
                t = self.tables.setdefault(key, {**here, "rls": None, "rls_at": None, "force": False, "external": True})
                act = re.sub(r"\s+", " ", a.group(1).lower())
                if act == "enable":
                    t["rls"], t["rls_at"] = True, here
                elif act == "disable":
                    t["rls"], t["rls_at"] = False, here
                elif act == "force":
                    t["force"] = True
                else:
                    t["force"] = False
            return

        m = re.match(r"drop\s+table\s+(?:if\s+exists\s+)?(.+)$", raw, re.I)
        if m:
            names = re.sub(r"\s+(cascade|restrict)\s*$", "", m.group(1), flags=re.I)
            for part in split_top(names):
                key = qname(part)
                self.tables.pop(key, None)
                for pk in [p for p in self.policies if p[:2] == key]:
                    del self.policies[pk]
            return

        m = re.match(rf"create\s+policy\s+({IDENT})\s+on\s+({QNAME})(.*)$", raw, re.I)
        if m:
            name, key, rest = unquote(m.group(1)), qname(m.group(2)), m.group(3)
            head = policy_head(rest)
            kind = re.search(r"\bas\s+(permissive|restrictive)\b", head, re.I)
            cmd = re.search(r"\bfor\s+(all|select|insert|update|delete)\b", head, re.I)
            to = re.search(r"\bto\s+(.+)$", head, re.I)
            self.policies[key + (name,)] = {
                **here, "name": name,
                "permissive": not (kind and kind.group(1).lower() == "restrictive"),
                "cmd": cmd.group(1).lower() if cmd else "all",
                "roles": roles_of(to.group(1)) if to else ["public"],
                "using": clause(rest, r"\busing"),
                "check": clause(rest, r"\bwith\s+check"),
            }
            return

        m = re.match(rf"alter\s+policy\s+({IDENT})\s+on\s+({QNAME})(.*)$", raw, re.I)
        if m:
            name, key, rest = unquote(m.group(1)), qname(m.group(2)), m.group(3)
            p = self.policies.get(key + (name,))
            if p is None:
                return
            r = re.match(rf"\s*rename\s+to\s+({IDENT})", rest, re.I)
            if r:
                new = unquote(r.group(1))
                p["name"] = new
                self.policies[key + (new,)] = self.policies.pop(key + (name,))
                return
            to = re.search(r"\bto\s+(.+)$", policy_head(rest), re.I)
            if to:
                p["roles"] = roles_of(to.group(1))
            u = clause(rest, r"\busing")
            if u is not None:
                p["using"] = u
            c = clause(rest, r"\bwith\s+check")
            if c is not None:
                p["check"] = c
            p.update(here)
            return

        m = re.match(rf"drop\s+policy\s+(?:if\s+exists\s+)?({IDENT})\s+on\s+({QNAME})", raw, re.I)
        if m:
            self.policies.pop(qname(m.group(2)) + (unquote(m.group(1)),), None)
            return

        m = re.match(rf"create\s+materialized\s+view\s+(?:if\s+not\s+exists\s+)?({QNAME})", raw, re.I)
        if m:
            self.matviews[qname(m.group(1))] = dict(here)
            return

        m = re.match(rf"create\s+(?:or\s+replace\s+)?(temp\s+|temporary\s+)?(?:recursive\s+)?view\s+({QNAME})(.*)$", raw, re.I)
        if m:
            if m.group(1):
                return
            key, rest = qname(m.group(2)), m.group(3)
            opts = re.match(r"\s*(?:\([^)]*\)\s*)?with\s*\(([^)]*)\)", rest, re.I)
            self.views[key] = {**here, "invoker": self._invoker(opts.group(1) if opts else "")}
            return

        m = re.match(rf"alter\s+view\s+(?:if\s+exists\s+)?({QNAME})\s+(.*)$", raw, re.I)
        if m:
            key, rest = qname(m.group(1)), m.group(2)
            v = self.views.get(key)
            r = re.match(rf"rename\s+to\s+({IDENT})", rest, re.I)
            if v is not None and r:
                self.views[(key[0], unquote(r.group(1)))] = self.views.pop(key)
                return
            s = re.match(r"set\s*\(([^)]*)\)", rest, re.I)
            if v is not None and s and "security_invoker" in s.group(1).lower():
                v["invoker"] = self._invoker(s.group(1))
            if v is not None and re.match(r"reset\s*\([^)]*security_invoker", rest, re.I):
                v["invoker"] = False
            return

        m = re.match(r"drop\s+(materialized\s+)?view\s+(?:if\s+exists\s+)?(.+)$", raw, re.I)
        if m:
            names = re.sub(r"\s+(cascade|restrict)\s*$", "", m.group(2), flags=re.I)
            target = self.matviews if m.group(1) else self.views
            for part in split_top(names):
                target.pop(qname(part), None)
            return

        m = re.match(rf"create\s+(?:or\s+replace\s+)?(?:function|procedure)\s+({QNAME})\s*\(", raw, re.I)
        if m:
            key = qname(m.group(1))
            self.functions[key] = {**here, "definer": re.search(r"\bsecurity\s+definer\b", raw, re.I) is not None,
                                   "search_path": re.search(r"\bset\s+search_path\b", raw, re.I) is not None}
            return

        m = re.match(rf"alter\s+(?:function|procedure)\s+({QNAME})\s*(?:\([^)]*\))?\s*(.*)$", raw, re.I)
        if m:
            f = self.functions.get(qname(m.group(1)))
            if f is not None:
                rest = m.group(2)
                if re.search(r"\bset\s+search_path\b", rest, re.I):
                    f["search_path"] = True
                if re.search(r"\breset\s+(search_path|all)\b", rest, re.I):
                    f["search_path"] = False
                if re.search(r"\bsecurity\s+invoker\b", rest, re.I):
                    f["definer"] = False
                if re.search(r"\bsecurity\s+definer\b", rest, re.I):
                    f["definer"] = True
            return

        m = re.match(r"drop\s+(?:function|procedure)\s+(?:if\s+exists\s+)?(.+)$", raw, re.I)
        if m:
            names = re.sub(r"\s+(cascade|restrict)\s*$", "", m.group(1), flags=re.I)
            for part in split_top(names):
                self.functions.pop(qname(re.sub(r"\(.*$", "", part)), None)
            return

        m = re.match(r"(grant|revoke)\s+(.+?)\s+on\s+(?:table\s+|function\s+|procedure\s+|routine\s+)?(.+?)\s+(?:to|from)\s+(.+?)(?:\s+(?:cascade|restrict|with\s+grant\s+option|granted\s+by\s+\S+))?$", raw, re.I)
        if m and not re.match(r"(all\s+tables|all\s+functions|all\s+routines|all\s+sequences|schema)\b", m.group(3), re.I):
            roles = set(roles_of(m.group(4)))
            for obj in split_top(m.group(3)):
                key = qname(re.sub(r"\(.*$", "", obj))
                held = self.revoked.setdefault(key, set())
                if m.group(1).lower() == "revoke":
                    held |= roles
                else:
                    held -= roles
            return

    @staticmethod
    def _invoker(opts: str) -> bool:
        m = re.search(r"security_invoker\s*(?:=\s*([A-Za-z0-9']+))?", opts or "", re.I)
        if not m:
            return False
        value = (m.group(1) or "true").strip("'").lower()
        return value in {"true", "on", "1", "yes"}

    def _rename_table(self, old, new):
        if old in self.tables:
            self.tables[new] = self.tables.pop(old)
        for pk in [p for p in self.policies if p[:2] == old]:
            self.policies[new + (pk[2],)] = self.policies.pop(pk)


# ---------------------------------------------------------------- lead rules

def lead(level, rule, where, obj, message):
    return {"level": level, "id": rule, "file": where["file"], "line": where["line"], "object": obj, "message": message}


def analyse(model: Model, exposed: set, client_roles: set):
    leads = []
    named_roles = client_roles - {"public"}
    # Tables and views: PUBLIC holds no default privileges, so revoking the named client roles closes access.
    closed_relation = lambda key: named_roles <= model.revoked.get(key, set())
    # Functions: PostgreSQL grants EXECUTE to PUBLIC by default, which every role inherits.
    closed_function = lambda key: client_roles <= model.revoked.get(key, set())
    policy_scope = lambda key: key[0] in exposed or key in {("storage", "objects"), ("storage", "buckets")}

    for key, t in sorted(model.tables.items()):
        if key[0] not in exposed or t.get("external"):
            continue
        name = f"{key[0]}.{key[1]}"
        if t["rls"] is not True:
            where = t["rls_at"] if t["rls"] is False else t
            state = "disabled" if t["rls"] is False else "not enabled"
            leads.append(lead("high", "RLS-DISABLED", where, name,
                              f"row-level security is {state}; with the usual API grants, anyone holding the public key "
                              "can read and change every row. Enable it in the migration that creates the table and add "
                              "one policy per operation and role."))
            continue
        reach = [p for pk, p in model.policies.items() if pk[:2] == key and p["permissive"] and set(p["roles"]) & client_roles]
        if not reach:
            leads.append(lead("low", "RLS-NO-POLICY", t["rls_at"] or t, name,
                              "RLS is on but no permissive policy lets client roles reach a row, so the API returns "
                              "nothing. Right for server-only tables; otherwise check the app does not fall back to "
                              "the service-role key for user requests."))

    for pk, p in sorted(model.policies.items()):
        key = pk[:2]
        if not policy_scope(key):
            continue
        roles = set(p["roles"]) & client_roles
        if not roles:
            continue
        name = f"{key[0]}.{key[1]} policy {p['name']} ({p['cmd'].upper()} to {', '.join(sorted(roles))})"
        who = "anyone holding the public key" if roles & {"public", "anon"} else "any signed-in user"
        check_eff = p["check"] if p["check"] is not None else (p["using"] if p["cmd"] in ("update", "all") else None)
        if p["permissive"]:
            using_true = p["cmd"] in ("update", "delete", "all") and is_true(p["using"])
            check_true = p["cmd"] in ("insert", "update", "all") and is_true(check_eff)
            if using_true:
                verb = {"update": "update", "delete": "delete"}.get(p["cmd"], "update and delete")
                leads.append(lead("high", "POLICY-TRUE-WRITE", p, name,
                                  f"{who} may {verb} every row with no condition. Limit USING to the owner or tenant "
                                  "((select auth.uid()) = user_id) and add a matching WITH CHECK."))
            elif check_true:
                scope = "insert rows with any values, including another user's id" if p["cmd"] == "insert" else \
                        "write any values, including the owner column, into the rows its USING allows"
                leads.append(lead("high", "POLICY-TRUE-WRITE", p, name,
                                  f"WITH CHECK (true) lets {who} {scope}. On UPDATE the change goes through whenever "
                                  "another policy lets them read the new row, for example a public SELECT policy. "
                                  "Compare the new row with the caller in WITH CHECK ((select auth.uid()) = user_id)."))
            if p["cmd"] in ("select", "all") and is_true(p["using"]):
                leads.append(lead("medium", "POLICY-TRUE-READ", p, name,
                                  f"{who} can read every row. Confirm the data is meant to be public; otherwise "
                                  "restrict USING to the owner or tenant."))
            exprs = [e for e in (p["using"], p["check"]) if e is not None]
            if any(is_signed_in_only(e) for e in exprs):
                leads.append(lead("medium", "POLICY-SIGNED-IN", p, name,
                                  "the only condition is that the caller is signed in, so every account, including "
                                  "self-registered ones, reaches every row. Compare the row's owner or tenant with "
                                  "the caller."))
        if uses_user_metadata(p["using"]) or uses_user_metadata(p["check"]):
            leads.append(lead("high", "POLICY-USER-METADATA", p, name,
                              "the policy trusts user_metadata (raw_user_meta_data), which users can change "
                              "themselves. Keep authorization data in app_metadata or in a table users cannot write."))
        if unwrapped_uid(p["using"]) or unwrapped_uid(p["check"]):
            leads.append(lead("info", "POLICY-UID-PERF", p, name,
                              "auth.uid() is called for every row; write (select auth.uid()) so it runs once per "
                              "statement."))

    for key, v in sorted(model.views.items()):
        if key[0] not in exposed or v["invoker"]:
            continue
        if closed_relation(key):
            continue
        leads.append(lead("high", "VIEW-BYPASSES-RLS", v, f"{key[0]}.{key[1]}",
                          "the view runs with its owner's rights, so the row-level security of the tables it reads is "
                          "checked against the owner (usually a role that bypasses it), not the caller. Create it "
                          "WITH (security_invoker = true) on PostgreSQL 15 or later, or revoke access for anon and "
                          "authenticated, or move it out of the exposed schema."))

    for key, v in sorted(model.matviews.items()):
        if key[0] not in exposed:
            continue
        if closed_relation(key):
            continue
        leads.append(lead("medium", "MATVIEW-EXPOSED", v, f"{key[0]}.{key[1]}",
                          "materialized views cannot have row-level security; with the usual grants every client can "
                          "read all of it. Revoke access for anon and authenticated or move it out of the exposed schema."))

    for key, f in sorted(model.functions.items()):
        if not f["definer"]:
            continue
        name = f"{key[0]}.{key[1]}()"
        if not f["search_path"]:
            leads.append(lead("medium", "SECDEF-SEARCH-PATH", f, name,
                              "a SECURITY DEFINER function without a fixed search_path can be made to call objects a "
                              "caller created. Add SET search_path = '' and schema-qualify every name inside it."))
        if key[0] in exposed and not closed_function(key):
            leads.append(lead("medium", "SECDEF-EXPOSED", f, name,
                              "the function is callable through the API and runs with its owner's rights, skipping "
                              "row-level security. Check the caller inside it, revoke EXECUTE from PUBLIC, anon and "
                              "authenticated, or move it to a schema the API does not expose."))

    for where in model.dynamic:
        leads.append(lead("info", "DYNAMIC-SQL", where, "DO block",
                          "this block changes tables or row-level security through dynamic SQL, which was not "
                          "evaluated; leads for the tables it touches may be wrong."))
    return leads


# ------------------------------------------------------------------ discovery

def walk(root: Path):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            count += 1
            if count > MAX_WALK_FILES:
                return
            yield Path(dirpath) / fn


def scan_env(root: Path):
    leads, seen = [], set()
    for path in walk(root):
        name = path.name
        if not (name.startswith(".env") or path.suffix in CODE_SUFFIXES):
            continue
        if name in {"package-lock.json", "tsconfig.json"} or name.endswith(".min.js"):
            continue
        try:
            if path.stat().st_size > MAX_CODE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for i, line_text in enumerate(text.splitlines(), 1):
            for m in PUBLIC_SECRET_ENV.finditer(line_text):
                key = (rel, m.group(1))
                if key in seen:
                    continue
                seen.add(key)
                leads.append(lead("high", "PUBLIC-SECRET-ENV", {"file": rel, "line": i}, m.group(1),
                                  "a secret is exposed through an environment variable that the build ships to "
                                  "browsers or apps; a service-role key there bypasses every policy. Rotate it and "
                                  "read it only in server code."))
    return leads


def check(sql_files, root: Path, exposed, client_roles, env_scan: bool):
    model, files = Model(), []
    for path in sql_files:
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        try:
            size = path.stat().st_size
            if size > MAX_SQL_BYTES:
                files.append({"file": rel, "statements": None, "note": "skipped: larger than 5 MB"})
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            files.append({"file": rel, "statements": None, "note": f"unreadable: {exc.strerror}"})
            continue
        statements = split_statements(text)
        for st in statements:
            model.apply(st, rel)
        files.append({"file": rel, "statements": len(statements)})
    leads = analyse(model, exposed, client_roles)
    if env_scan:
        leads.extend(scan_env(root))
    tables = [{"table": f"{k[0]}.{k[1]}", "rls": bool(t["rls"]), "force": t["force"],
               "policies": sum(1 for pk in model.policies if pk[:2] == k)}
              for k, t in sorted(model.tables.items()) if k[0] in exposed and not t.get("external")]
    return files, tables, leads


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="rls_check.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    ap.add_argument("--root", default=".", help="project folder to search for *.sql files (default: current folder)")
    ap.add_argument("--file", action="append", default=[], metavar="PATH",
                    help="check these SQL files, in the order given, instead of searching (repeatable)")
    ap.add_argument("--exposed-schema", action="append", default=[], metavar="NAME",
                    help="schema the API exposes (repeatable; default: public)")
    ap.add_argument("--client-role", action="append", default=[], metavar="ROLE",
                    help="extra database role that end users act as (default: public, anon, authenticated)")
    ap.add_argument("--no-env", action="store_true", help="skip the client environment-variable scan")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--json-out", metavar="PATH", help="also write the JSON result to PATH (mode 0600)")
    ap.add_argument("--fail-on", choices=["never", "high", "medium", "low"], default="never",
                    help="exit 1 when a lead at this level or above exists (for CI)")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: --root {args.root} is not a folder", file=sys.stderr)
        return 2
    root = root.resolve()
    if args.file:
        sql_files = []
        for item in args.file:
            p = Path(item)
            if not p.is_file():
                print(f"error: --file {item} does not exist", file=sys.stderr)
                return 2
            sql_files.append(p.resolve())
        env_scan = False
    else:
        sql_files = sorted((p.resolve() for p in walk(root) if p.suffix.lower() == ".sql"),
                           key=lambda p: p.relative_to(root).as_posix())
        env_scan = not args.no_env
    exposed = {s.lower() for s in args.exposed_schema} or {"public"}
    client_roles = DEFAULT_CLIENT_ROLES | {r.lower() for r in args.client_role}
    files, tables, leads = check(sql_files, root, exposed, client_roles, env_scan)
    leads.sort(key=lambda d: (LEVEL_RANK[d["level"]], d["id"], d["file"], d["line"], d["object"]))
    counts = {level: sum(1 for d in leads if d["level"] == level) for level in LEVELS}
    result = {
        "tool": "rls_check.py", "version": VERSION,
        "status": "NOT_APPLICABLE" if not files and not leads else (
            "LEADS" if any(d["level"] != "info" for d in leads) else "NO_LEADS"),
        "exposed_schemas": sorted(exposed), "client_roles": sorted(client_roles),
        "files": files, "tables": tables, "counts": counts, "leads": leads,
        "note": "Leads, not findings. Confirm each with a test that queries as two users and as an anonymous caller.",
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
            print(f"rls_check.py {VERSION}: no SQL files found under {args.root}"
                  + (" (NOT_APPLICABLE)." if not leads else "."))
        else:
            summary = ", ".join(f"{level} {counts[level]}" for level in LEVELS if counts[level])
            print(f"rls_check.py {VERSION}: {len(leads)} lead(s) from {len(files)} SQL file(s), "
                  f"{len(tables)} table(s) in {', '.join(sorted(exposed))}" + (f" ({summary})" if summary else ""))
        for d in leads:
            print(f"{d['level'].upper():<7} {d['id']:<20} {d['file']}:{d['line']} {d['object']}: {d['message']}")
        if files or leads:
            print("Leads, not findings: confirm each with a test that queries as two users and as an anonymous caller.")
    if args.fail_on != "never":
        limit = LEVEL_RANK[args.fail_on]
        if any(LEVEL_RANK[d["level"]] <= limit for d in leads):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
