#!/usr/bin/env python3
"""ProductCraft codebase map: a read-only structural map of a repository.

Walks a source tree (honouring basic .gitignore rules and skipping vendored,
virtual-environment and build output), then reports:

  * languages and a top-level layout overview
  * entry points: package.json scripts/main/bin, pyproject/setup.py/setup.cfg
    console scripts, __main__ modules and main guards, Dockerfile CMD and
    ENTRYPOINT, Procfile, Makefile targets, Go and Rust mains, shebang scripts
  * obvious web routes: Python route decorators, Django urls.py, Express-style
    routers, Next.js app/ and pages/ routes, SvelteKit routes
  * an import graph for Python (ast) and JavaScript/TypeScript (regex), with
    relative paths and tsconfig/jsconfig path aliases resolved
  * top-level symbols per Python and JavaScript/TypeScript file
  * hotspots: largest files, fan-in, fan-out, import cycles, files nothing imports

Standard library only. It reads files and never writes, executes project code
or touches the network. Files whose names look like credentials are listed but
never opened, commands are printed with secret-looking values redacted, and no
file contents are printed beyond names, paths, line numbers, import specifiers
and route paths. Output is deterministic for a given tree.

Results are structural heuristics, not proof: dynamic imports, plugin loading,
dependency injection and framework conventions can hide real dependencies.
"""
from __future__ import annotations

import argparse
import ast
import bisect
import configparser
import json
import os
import posixpath
import re
import sys
import warnings
from collections import defaultdict, deque

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover - exercised only on older interpreters
    tomllib = None

VERSION = "1.0.0"
SCHEMA_VERSION = 1
DEFAULT_MAX_FILES = 5000
DEFAULT_TOP = 10
DEFAULT_DEPTH = 1
PARSE_LIMIT = 1_000_000  # bytes; larger files are counted but not parsed
SNIFF_BYTES = 8192
MAX_GIT_ROOT_HOPS = 20

ALWAYS_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".bzr", "node_modules", "bower_components", "jspm_packages",
    "vendor", "third_party", "third-party", "dist", "build", "out", "target", "coverage",
    "htmlcov", ".next", ".nuxt", ".svelte-kit", ".astro", ".turbo", ".parcel-cache",
    ".cache", ".vercel", ".netlify", ".output", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".venv", "venv", ".eggs",
    "site-packages", ".gradle", ".idea", ".terraform", "Pods", "DerivedData",
    ".dart_tool", "elm-stuff",
}

CODE_EXT = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".vue": "Vue", ".svelte": "Svelte", ".astro": "Astro",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".scala": "Scala", ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C",
    ".c": "C", ".h": "C/C++ header", ".cc": "C++", ".cpp": "C++", ".cxx": "C++",
    ".hpp": "C++", ".hh": "C++", ".cs": "C#", ".fs": "F#", ".rb": "Ruby", ".php": "PHP",
    ".dart": "Dart", ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang",
    ".hs": "Haskell", ".clj": "Clojure", ".lua": "Lua", ".r": "R", ".jl": "Julia",
    ".zig": "Zig", ".pl": "Perl", ".pm": "Perl", ".sh": "Shell", ".bash": "Shell",
    ".zsh": "Shell", ".ps1": "PowerShell", ".sol": "Solidity",
}
OTHER_TEXT_EXT = {
    ".sql": ("SQL", "schema"), ".proto": ("Protocol Buffers", "schema"),
    ".graphql": ("GraphQL", "schema"), ".gql": ("GraphQL", "schema"),
    ".prisma": ("Prisma", "schema"), ".tf": ("Terraform", "schema"),
    ".html": ("HTML", "markup"), ".htm": ("HTML", "markup"), ".xml": ("XML", "markup"),
    ".svg": ("SVG", "markup"),
    ".css": ("CSS", "style"), ".scss": ("SCSS", "style"), ".sass": ("Sass", "style"),
    ".less": ("Less", "style"),
    ".json": ("JSON", "config"), ".jsonc": ("JSON", "config"), ".json5": ("JSON", "config"),
    ".yaml": ("YAML", "config"), ".yml": ("YAML", "config"), ".toml": ("TOML", "config"),
    ".ini": ("INI", "config"), ".cfg": ("INI", "config"), ".conf": ("Config", "config"),
    ".properties": ("Properties", "config"), ".lock": ("Lockfile", "config"),
    ".md": ("Markdown", "docs"), ".mdx": ("MDX", "docs"), ".rst": ("reStructuredText", "docs"),
    ".txt": ("Text", "docs"), ".adoc": ("AsciiDoc", "docs"),
}
SPECIAL_NAMES = {
    "dockerfile": ("Dockerfile", "config"), "containerfile": ("Dockerfile", "config"),
    "makefile": ("Makefile", "config"), "gnumakefile": ("Makefile", "config"),
    "procfile": ("Procfile", "config"), "justfile": ("Justfile", "config"),
    "jenkinsfile": ("Groovy", "config"), "gemfile": ("Ruby", "config"),
    "rakefile": ("Ruby", "code"), "vagrantfile": ("Ruby", "config"),
}
GRAPH_LANGUAGES = {"Python", "JavaScript", "TypeScript", "Vue", "Svelte"}
JS_LANGUAGES = {"JavaScript", "TypeScript", "Vue", "Svelte"}
JS_RESOLVE_EXT = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".json")
JS_EXT_SWAP = {".js": (".ts", ".tsx"), ".jsx": (".tsx",), ".mjs": (".mts",), ".cjs": (".cts",)}
NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "crypto",
    "dgram", "dns", "events", "fs", "http", "http2", "https", "module", "net", "os",
    "path", "perf_hooks", "process", "querystring", "readline", "stream", "string_decoder",
    "timers", "tls", "tty", "url", "util", "v8", "vm", "worker_threads", "zlib",
}
RUNTIME_EDGE_KINDS = {"import", "reexport", "require"}
TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e", "cypress"}
FRAMEWORK_FILE_STEMS = {
    "layout", "page", "loading", "error", "not-found", "template", "default", "route",
    "middleware", "global-error", "instrumentation",
}
NOT_UNREFERENCED_NAMES = {
    "__init__.py", "__main__.py", "conftest.py", "setup.py", "manage.py", "wsgi.py",
    "asgi.py", "noxfile.py", "fabfile.py",
}

SECRET_NAME = re.compile(
    r"(?i)^(?:\.env(?:\..*)?|\.envrc|\.netrc|\.npmrc|\.pypirc|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?"
    r"|.*\.(?:pem|key|p12|pfx|jks|keystore|kdbx|asc|gpg)|credentials?(?:\..*)?|secrets?(?:\..*)?"
    r"|.*service[-_]?account.*\.json|.*token.*\.(?:json|txt))$"
)
SECRET_ENV_ASSIGN = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|AUTH|CREDENTIAL)[A-Z0-9_]*)=(\"[^\"]*\"|'[^']*'|\S+)"
)
SECRET_FLAG = re.compile(r"(?i)(--?(?:password|passwd|token|secret|api[-_]?key)(?:=|\s+))(\"[^\"]*\"|'[^']*'|\S+)")
URL_CREDENTIALS = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
TOKEN_SHAPES = re.compile(
    r"\b(?:sk_(?:live|test)_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}"
    r"|AKIA[A-Z0-9]{16}|xox[abpr]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+)"
)
GENERATED_MARK = re.compile(r"@generated|DO NOT EDIT")


# --------------------------------------------------------------------------- utils

def redact(command: str) -> str:
    """Hide secret-looking values in a command string before it is reported."""
    text = SECRET_ENV_ASSIGN.sub(lambda m: m.group(1) + "=<redacted>", command)
    text = SECRET_FLAG.sub(lambda m: m.group(1) + "<redacted>", text)
    text = URL_CREDENTIALS.sub("://<redacted>@", text)
    return TOKEN_SHAPES.sub("<redacted>", text)


def looks_secret(name: str) -> bool:
    return bool(SECRET_NAME.match(name))


def is_test_path(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1]
    if any(p.lower() in TEST_DIR_NAMES for p in parts[:-1]):
        return True
    if re.match(r"(?:test_.*\.py|.*_test\.(?:py|go)|conftest\.py)$", name):
        return True
    return bool(re.search(r"\.(?:test|spec)\.[cm]?[jt]sx?$", name))


def classify(name: str):
    """Return (language, category) for a file name; (None, 'other') if unknown."""
    lower = name.lower()
    if lower in SPECIAL_NAMES:
        return SPECIAL_NAMES[lower]
    if lower.startswith("dockerfile.") or lower.endswith(".dockerfile"):
        return ("Dockerfile", "config")
    if lower.endswith(".d.ts"):
        return ("TypeScript", "code")
    ext = os.path.splitext(lower)[1]
    if ext in CODE_EXT:
        return (CODE_EXT[ext], "code")
    if ext in OTHER_TEXT_EXT:
        return OTHER_TEXT_EXT[ext]
    return (None, "other")


def _line_starts(text: str):
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())
    return starts


def _line_of(starts, offset: int) -> int:
    return bisect.bisect_right(starts, offset)


def _read_text(path: str, limit: int = PARSE_LIMIT):
    """Read up to `limit` bytes as text. Returns (text or None, binary, lines)."""
    with open(path, "rb") as fh:
        data = fh.read(limit + 1)
    if b"\0" in data[:SNIFF_BYTES]:
        return None, True, None
    if len(data) > limit:
        lines = data.count(b"\n")
        with open(path, "rb") as fh:
            fh.seek(len(data))
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                lines += chunk.count(b"\n")
        return None, False, lines
    text = data.decode("utf-8", errors="replace")
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    return text, False, lines


# ----------------------------------------------------------------------- gitignore

class IgnoreRule:
    __slots__ = ("base", "outer", "regex", "negate", "dir_only")

    def __init__(self, base, outer, regex, negate, dir_only):
        self.base = base      # directory of the .gitignore, relative to the scan root
        self.outer = outer    # for .gitignore files above the scan root: path from them to it
        self.regex = regex
        self.negate = negate
        self.dir_only = dir_only


def _glob_to_regex(pat: str) -> str:
    out = []
    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        if c == "*":
            if pat.startswith("**/", i):
                out.append("(?:.*/)?")
                i += 3
                continue
            if pat.startswith("**", i):
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = pat.find("]", i + 2)
            if j == -1:
                out.append("\\[")
            else:
                cls = pat[i + 1:j]
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                out.append("[" + cls + "]")
                i = j + 1
                continue
        elif c == "\\" and i + 1 < n:
            out.append(re.escape(pat[i + 1]))
            i += 2
            continue
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


def compile_ignore_pattern(raw: str, base: str = "", outer: str = ""):
    """Compile one .gitignore line into an IgnoreRule, or None for blanks/comments."""
    line = raw.rstrip("\r\n")
    while line.endswith(" ") and not line.endswith("\\ "):
        line = line[:-1]
    if not line or line.startswith("#"):
        return None
    negate = False
    if line.startswith("!"):
        negate, line = True, line[1:]
    elif line.startswith(("\\!", "\\#")):
        line = line[1:]
    dir_only = line.endswith("/")
    line = line.rstrip("/")
    if not line:
        return None
    anchored = "/" in line
    body = _glob_to_regex(line.lstrip("/"))
    if not anchored:
        body = "(?:.*/)?" + body
    try:
        regex = re.compile("^" + body + "$")
    except re.error:
        return None
    return IgnoreRule(base, outer, regex, negate, dir_only)


def parse_gitignore(text: str, base: str = "", outer: str = ""):
    rules = []
    for raw in text.splitlines():
        rule = compile_ignore_pattern(raw, base, outer)
        if rule is not None:
            rules.append(rule)
    return rules


def is_ignored(rel: str, is_dir: bool, rules) -> bool:
    """Apply rules in order; the last matching rule decides (git semantics)."""
    ignored = False
    for r in rules:
        if r.dir_only and not is_dir:
            continue
        if r.outer:
            sub = r.outer + "/" + rel
        elif r.base:
            if not rel.startswith(r.base + "/"):
                continue
            sub = rel[len(r.base) + 1:]
        else:
            sub = rel
        if r.regex.match(sub):
            ignored = not r.negate
    return ignored


def _outer_rules(root: str):
    """Rules from .gitignore files between the enclosing git root and the scan root."""
    chain = []
    cur = root
    for _ in range(MAX_GIT_ROOT_HOPS):
        parent = os.path.dirname(cur)
        if os.path.exists(os.path.join(cur, ".git")) or parent == cur:
            break
        chain.append(parent)
        cur = parent
    if not chain or not os.path.exists(os.path.join(chain[-1], ".git")):
        return []
    rules = []
    for directory in reversed(chain):
        gi = os.path.join(directory, ".gitignore")
        if os.path.isfile(gi) and not os.path.islink(gi):
            outer = os.path.relpath(root, directory).replace(os.sep, "/")
            try:
                with open(gi, encoding="utf-8", errors="replace") as fh:
                    rules += parse_gitignore(fh.read(), "", outer)
            except OSError:
                pass
    return rules


# ---------------------------------------------------------------------------- walk

def _skip_dir(entry) -> bool:
    name = entry.name
    if name in ALWAYS_SKIP_DIRS or name.endswith(".egg-info"):
        return True
    return os.path.isfile(os.path.join(entry.path, "pyvenv.cfg"))


def collect_files(root: str, max_files: int = DEFAULT_MAX_FILES, use_gitignore: bool = True):
    """Deterministic pre-order walk. Returns ([(rel_path, size)], info)."""
    info = {"skipped_dirs": [], "ignored_paths": 0, "symlinks_skipped": 0, "truncated": False}
    files = []
    start_rules = _outer_rules(root) if use_gitignore else []
    stack = [("", start_rules)]
    while stack:
        rel_dir, rules = stack.pop()
        abs_dir = os.path.join(root, *rel_dir.split("/")) if rel_dir else root
        try:
            with os.scandir(abs_dir) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            continue
        if use_gitignore:
            for e in entries:
                if e.name == ".gitignore" and e.is_file(follow_symlinks=False):
                    try:
                        with open(e.path, encoding="utf-8", errors="replace") as fh:
                            rules = rules + parse_gitignore(fh.read(), rel_dir)
                    except OSError:
                        pass
                    break
        subdirs = []
        for e in entries:
            rel = rel_dir + "/" + e.name if rel_dir else e.name
            if e.is_symlink():
                info["symlinks_skipped"] += 1
                continue
            if e.is_dir(follow_symlinks=False):
                if _skip_dir(e):
                    info["skipped_dirs"].append(rel)
                elif use_gitignore and is_ignored(rel, True, rules):
                    info["ignored_paths"] += 1
                else:
                    subdirs.append(rel)
            elif e.is_file(follow_symlinks=False):
                if use_gitignore and is_ignored(rel, False, rules):
                    info["ignored_paths"] += 1
                    continue
                if len(files) >= max_files:
                    info["truncated"] = True
                    return files, info
                try:
                    size = e.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
                files.append((rel, size))
        for sd in reversed(subdirs):
            stack.append((sd, rules))
    return files, info


# -------------------------------------------------------------------------- python

PY_VERBS = {"get", "post", "put", "patch", "delete", "head", "options"}
PY_ROUTE_ATTRS = PY_VERBS | {"route", "api_route", "websocket"}


def _is_type_checking(test) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


def _py_imports(body, in_function, type_only, out):
    for node in body:
        kind = "type" if type_only else ("lazy" if in_function else "import")
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append({"kind": kind, "level": 0, "module": alias.name, "names": [], "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            out.append({"kind": kind, "level": node.level or 0, "module": node.module or "",
                        "names": [a.name for a in node.names], "line": node.lineno})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _py_imports(node.body, True, type_only, out)
        elif isinstance(node, ast.ClassDef):
            _py_imports(node.body, in_function, type_only, out)
        elif isinstance(node, ast.If) and _is_type_checking(node.test):
            _py_imports(node.body, in_function, True, out)
            _py_imports(node.orelse, in_function, type_only, out)
        else:
            for field in ("body", "orelse", "finalbody"):
                sub = getattr(node, field, None)
                if isinstance(sub, list):
                    _py_imports(sub, in_function, type_only, out)
            for handler in getattr(node, "handlers", None) or []:
                _py_imports(handler.body, in_function, type_only, out)
            for case in getattr(node, "cases", None) or []:
                _py_imports(case.body, in_function, type_only, out)


def _iter_defs(body):
    """Yield function definitions at any statement depth without visiting expressions."""
    stack = list(reversed(body))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node
        children = []
        for field in ("body", "orelse", "finalbody"):
            sub = getattr(node, field, None)
            if isinstance(sub, list):
                children += sub
        for holder in (getattr(node, "handlers", None) or []) + (getattr(node, "cases", None) or []):
            children += holder.body
        stack.extend(reversed(children))


def _is_main_guard(node) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1:
        return False
    sides = [test.left, test.comparators[0]]
    has_name = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return has_name and has_main


def _expr_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _expr_name(node.value) + "." + node.attr
    if isinstance(node, ast.Call):
        return _expr_name(node.func) + "()"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return repr(node.value)
    return "?"


def _str_list(node):
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def parse_python(text: str, path: str) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            tree = ast.parse(text, filename=path)
        except (SyntaxError, ValueError):
            return {"parse_error": True}
    imports = []
    _py_imports(tree.body, False, False, imports)
    exported = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            exported = set(_str_list(node.value))
    symbols = []

    def add(name, kind, line):
        is_exported = (name in exported) if exported is not None else not name.startswith("_")
        symbols.append({"name": name, "kind": kind, "line": line, "exported": is_exported})

    main_line = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            add(node.name, "class", node.lineno)
        elif isinstance(node, ast.FunctionDef):
            add(node.name, "function", node.lineno)
        elif isinstance(node, ast.AsyncFunctionDef):
            add(node.name, "async function", node.lineno)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    add(t.id, "constant", node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id.isupper():
            add(node.target.id, "constant", node.lineno)
        elif _is_main_guard(node) and main_line is None:
            main_line = node.lineno
    routes = []
    for node in (_iter_defs(tree.body) if "@" in text else ()):
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            attr = dec.func.attr
            if attr not in PY_ROUTE_ATTRS or not dec.args:
                continue
            first = dec.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.startswith("/")):
                continue
            if attr in PY_VERBS:
                method = attr.upper()
            elif attr == "websocket":
                method = "WS"
            else:
                methods = []
                for kw in dec.keywords:
                    if kw.arg == "methods":
                        methods = [m.upper() for m in _str_list(kw.value)]
                method = ",".join(methods) if methods else "DEFAULT"
            routes.append({"method": method, "path": first.value, "line": dec.lineno,
                           "handler": node.name, "framework": "python-decorator"})
    if posixpath.basename(path) == "urls.py":
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("path", "re_path", "url") and len(node.args) >= 2
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                routes.append({"method": "ANY", "path": node.args[0].value, "line": node.lineno,
                               "handler": _expr_name(node.args[1]), "framework": "django"})
    symbols.sort(key=lambda s: (s["line"], s["name"]))
    routes.sort(key=lambda r: (r["line"], r["path"]))
    return {"parse_error": False, "imports": imports, "symbols": symbols, "main_line": main_line, "routes": routes}


# ---------------------------------------------------------------------- javascript

_JS_SPECIAL = re.compile(r"['\"`/]")


def strip_js_comments(text: str) -> str:
    """Blank out // and /* */ comments (keeping newlines and string literals)."""
    out = []
    i, n = 0, len(text)
    while i < n:
        m = _JS_SPECIAL.search(text, i)
        if not m:
            out.append(text[i:])
            break
        j = m.start()
        out.append(text[i:j])
        c = text[j]
        if c in "'\"`":
            k = j + 1
            while k < n:
                d = text[k]
                if d == "\\":
                    k += 2
                    continue
                if d == c:
                    k += 1
                    break
                if d == "\n" and c != "`":
                    break
                k += 1
            out.append(text[j:k])
            i = k
        elif text.startswith("//", j):
            k = text.find("\n", j)
            k = n if k == -1 else k
            out.append(" " * (k - j))
            i = k
        elif text.startswith("/*", j):
            k = text.find("*/", j + 2)
            k = n if k == -1 else k + 2
            out.append(re.sub(r"[^\n]", " ", text[j:k]))
            i = k
        else:
            out.append(c)
            i = j + 1
    return "".join(out)


_NO_KEYWORD = r"(?:(?!\b(?:import|export)\b)[\w$*{}\s,])*?"
_JS_FROM = re.compile(r"(?<![\w$.])(import|export)(?:\s+|(?=[{*]))(type(?:\s+|(?=\{)))?(" + _NO_KEYWORD + r")\s*from\s*(['\"])([^'\"\n]+)\4")
_JS_SIDE = re.compile(r"(?<![\w$.])import\s*(['\"])([^'\"\n]+)\1")
_JS_DYNAMIC = re.compile(r"(?<![\w$.])import\s*\(\s*(['\"`])([^'\"`\n]+)\1\s*\)")
_JS_REQUIRE = re.compile(r"(?<![\w$.])require\s*\(\s*(['\"`])([^'\"`\n]+)\1\s*\)")
_JS_SYMBOLS = [
    (re.compile(r"^export\s+default\s+(?:async\s+)?function\s*\*?\s*([\w$]+)", re.M), "function", True),
    (re.compile(r"^export\s+default\s+(?:abstract\s+)?class\s+([\w$]+)", re.M), "class", True),
    (re.compile(r"^export\s+(?:declare\s+)?(?:async\s+)?function\s*\*?\s*([\w$]+)", re.M), "function", True),
    (re.compile(r"^export\s+(?:declare\s+)?(?:abstract\s+)?class\s+([\w$]+)", re.M), "class", True),
    (re.compile(r"^export\s+(?:declare\s+)?(?:const|let|var)\s+([\w$]+)", re.M), "variable", True),
    (re.compile(r"^export\s+(?:declare\s+)?interface\s+([\w$]+)", re.M), "interface", True),
    (re.compile(r"^export\s+(?:declare\s+)?type\s+([\w$]+)\s*(?:<[^=\n]*>)?\s*=", re.M), "type", True),
    (re.compile(r"^export\s+(?:declare\s+)?(?:const\s+)?enum\s+([\w$]+)", re.M), "enum", True),
    (re.compile(r"^(?:async\s+)?function\s*\*?\s*([\w$]+)", re.M), "function", False),
    (re.compile(r"^(?:abstract\s+)?class\s+([\w$]+)", re.M), "class", False),
    (re.compile(r"^(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s*)?(?:\([^)\n]*\)|[\w$]+)\s*=>", re.M), "function", False),
    (re.compile(r"^interface\s+([\w$]+)", re.M), "interface", False),
    (re.compile(r"^type\s+([\w$]+)\s*(?:<[^=\n]*>)?\s*=", re.M), "type", False),
    (re.compile(r"^(?:module\.)?exports\.([\w$]+)\s*=", re.M), "export", True),
]
_JS_MODULE_EXPORTS = re.compile(r"^module\.exports\s*=", re.M)
_HTTP_METHODS = r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)"
_NEXT_HANDLER = re.compile(
    r"^export\s+(?:async\s+)?function\s+" + _HTTP_METHODS + r"\b|^export\s+const\s+" + _HTTP_METHODS
    + r"\b|\bas\s+" + _HTTP_METHODS + r"\b", re.M)
_EXPRESS_ROUTE = re.compile(
    r"(?<![\w$.])(app|server|fastify|router|[\w$]+Router|[\w$]+router)\s*\.\s*"
    r"(get|post|put|patch|delete|del|all|options|head|use|route)\s*\(\s*(['\"`])(/[^'\"`\n]*)\3")


def parse_js(text: str) -> dict:
    stripped = strip_js_comments(text)
    starts = _line_starts(stripped)
    imports = []
    taken = []
    for m in _JS_FROM.finditer(stripped):
        clause = m.group(3)
        type_only = bool(m.group(2))
        if not type_only and "{" in clause:
            inner = clause[clause.index("{") + 1:clause.rindex("}")] if "}" in clause else ""
            head = clause[:clause.index("{")].strip().rstrip(",").strip()
            parts = [p.strip() for p in inner.split(",") if p.strip()]
            if parts and not head and all(p.startswith("type ") for p in parts):
                type_only = True
        kind = "type" if type_only else ("import" if m.group(1) == "import" else "reexport")
        imports.append({"kind": kind, "spec": m.group(5), "line": _line_of(starts, m.start())})
        taken.append((m.start(), m.end()))

    def overlaps(pos):
        return any(a <= pos < b for a, b in taken)

    for regex, kind in ((_JS_SIDE, "import"), (_JS_DYNAMIC, "dynamic"), (_JS_REQUIRE, "require")):
        for m in regex.finditer(stripped):
            if overlaps(m.start()) or "${" in m.group(2):
                continue
            imports.append({"kind": kind, "spec": m.group(2), "line": _line_of(starts, m.start())})
    imports.sort(key=lambda x: (x["line"], x["spec"], x["kind"]))
    seen = set()
    symbols = []
    for regex, kind, exported in _JS_SYMBOLS:
        for m in regex.finditer(stripped):
            line = _line_of(starts, m.start())
            key = (m.group(1), line)
            if key in seen:
                continue
            seen.add(key)
            symbols.append({"name": m.group(1), "kind": kind, "line": line, "exported": exported})
    for m in _JS_MODULE_EXPORTS.finditer(stripped):
        symbols.append({"name": "module.exports", "kind": "export", "line": _line_of(starts, m.start()), "exported": True})
    symbols.sort(key=lambda s: (s["line"], s["name"]))
    routes = []
    for m in _EXPRESS_ROUTE.finditer(stripped):
        verb = m.group(2).lower()
        method = {"use": "USE", "all": "ANY", "route": "ANY", "del": "DELETE"}.get(verb, verb.upper())
        routes.append({"method": method, "path": m.group(4), "line": _line_of(starts, m.start()),
                       "handler": m.group(1), "framework": "express-style"})
    handlers = sorted({g for m in _NEXT_HANDLER.finditer(stripped) for g in m.groups() if g})
    shebang = text.split("\n", 1)[0] if text.startswith("#!") else None
    return {"parse_error": False, "imports": imports, "symbols": symbols, "routes": routes,
            "http_handlers": handlers, "shebang": shebang}


def _parse_jsonc(text: str):
    cleaned = strip_js_comments(text)
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return json.loads(cleaned)


# ------------------------------------------------------------------ entry points

_NPM_PRIORITY = ["dev", "start", "serve", "build", "test", "lint", "typecheck", "check", "format"]


def _join(base: str, rel: str) -> str:
    joined = posixpath.normpath(posixpath.join(base, rel)) if base else posixpath.normpath(rel)
    return "" if joined == "." else joined


def _npm_runner(pkg: dict, directory: str, file_set) -> str:
    manager = pkg.get("packageManager")
    if isinstance(manager, str) and manager:
        return manager.split("@", 1)[0]
    for lock, runner in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if _join(directory, lock) in file_set or lock in file_set:
            return runner
    return "npm"


def _package_entries(pkg: dict) -> list:
    """Candidate entry files of a package, in the order a bundler would usually try them."""
    found = []

    def collect(value):
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                collect(v)

    exports = pkg.get("exports")
    if isinstance(exports, dict) and "." in exports:
        collect(exports["."])
    elif isinstance(exports, str):
        found.append(exports)
    for field in ("source", "module", "main", "types"):
        if isinstance(pkg.get(field), str):
            found.append(pkg[field])
    return [f for i, f in enumerate(found) if f not in found[:i]]


def entries_from_package_json(path: str, text: str, file_set) -> list:
    try:
        pkg = json.loads(text)
    except ValueError:
        return []
    if not isinstance(pkg, dict):
        return []
    directory = posixpath.dirname(path)
    out = []
    runner = _npm_runner(pkg, directory, file_set)
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    order = sorted(scripts, key=lambda k: (_NPM_PRIORITY.index(k) if k in _NPM_PRIORITY else len(_NPM_PRIORITY), k))
    for name in order:
        cmd = scripts[name]
        if not isinstance(cmd, str):
            continue
        targets = []
        for token in re.split(r"\s+", cmd):
            token = token.strip("'\"")
            cand = _join(directory, token) if token and not token.startswith("-") else ""
            if cand and cand in file_set:
                targets.append(cand)
        prefix = f"(cd {directory} && " if directory else ""
        suffix = ")" if directory else ""
        out.append({"kind": "npm-script", "name": name, "command": redact(cmd), "file": path,
                    "run": f"{prefix}{runner} run {name}{suffix}", "targets": sorted(set(targets))})
    for field in ("main", "module"):
        value = pkg.get(field)
        if isinstance(value, str) and value:
            out.append({"kind": "package-main", "name": field, "file": path,
                        "target": _join(directory, value), "run": f"{field}: {_join(directory, value)}"})
    bins = pkg.get("bin")
    if isinstance(bins, str):
        bins = {str(pkg.get("name", "bin")).split("/")[-1]: bins}
    if isinstance(bins, dict):
        for name in sorted(bins):
            if isinstance(bins[name], str):
                target = _join(directory, bins[name])
                out.append({"kind": "package-bin", "name": name, "file": path, "target": target,
                            "run": f"{name} -> {target}"})
    return out


def _pyproject_scripts_fallback(text: str) -> dict:
    tables = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line.strip("[]").strip()
            continue
        if current in ("project.scripts", "project.gui-scripts", "tool.poetry.scripts"):
            m = re.match(r"""^["']?([\w.-]+)["']?\s*=\s*["']([^"']+)["']""", line)
            if m:
                tables.setdefault(current, {})[m.group(1)] = m.group(2)
    return tables


def entries_from_pyproject(path: str, text: str) -> list:
    tables = {}
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except (tomllib.TOMLDecodeError, ValueError):
            data = {}
        project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
        poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
        for key, table in (("project.scripts", project.get("scripts")), ("project.gui-scripts", project.get("gui-scripts")),
                           ("tool.poetry.scripts", poetry.get("scripts") if isinstance(poetry, dict) else None)):
            if isinstance(table, dict):
                tables[key] = table
    else:
        tables = _pyproject_scripts_fallback(text)
    out = []
    for key in sorted(tables):
        for name in sorted(tables[key]):
            value = tables[key][name]
            if isinstance(value, dict):
                value = value.get("callable") or value.get("reference") or json.dumps(value, sort_keys=True)
            out.append({"kind": "python-script", "name": name, "target": str(value), "file": path,
                        "run": f"{name} -> {value}"})
    return out


def entries_from_setup_py(path: str, text: str) -> list:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return []
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _expr_name(node.func).split(".")[-1] == "setup"):
            continue
        for kw in node.keywords:
            if kw.arg == "entry_points" and isinstance(kw.value, ast.Dict):
                for k, v in zip(kw.value.keys, kw.value.values):
                    if isinstance(k, ast.Constant) and k.value in ("console_scripts", "gui_scripts"):
                        for spec in _str_list(v):
                            if "=" in spec:
                                name, target = (s.strip() for s in spec.split("=", 1))
                                out.append({"kind": "python-script", "name": name, "target": target,
                                            "file": path, "line": node.lineno, "run": f"{name} -> {target}"})
            elif kw.arg == "scripts":
                for script in _str_list(kw.value):
                    target = _join(posixpath.dirname(path), script)
                    out.append({"kind": "python-script", "name": posixpath.basename(script), "target": target,
                                "file": path, "line": node.lineno, "run": f"{posixpath.basename(script)} -> {target}"})
    return out


def entries_from_setup_cfg(path: str, text: str) -> list:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        return []
    out = []
    if parser.has_section("options.entry_points"):
        for key in ("console_scripts", "gui_scripts"):
            raw = parser.get("options.entry_points", key, fallback="")
            for line in raw.splitlines():
                if "=" in line:
                    name, target = (s.strip() for s in line.split("=", 1))
                    out.append({"kind": "python-script", "name": name, "target": target, "file": path,
                                "run": f"{name} -> {target}"})
    return out


def entries_from_dockerfile(path: str, text: str) -> list:
    out = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        start = i
        logical = lines[i].rstrip()
        while logical.endswith("\\") and i + 1 < len(lines):
            i += 1
            logical = logical[:-1].rstrip() + " " + lines[i].strip()
        i += 1
        m = re.match(r"^\s*(ENTRYPOINT|CMD)\s+(.+)$", logical, re.I)
        if m:
            cmd = redact(m.group(2).strip())
            out.append({"kind": "docker", "name": m.group(1).upper(), "command": cmd, "file": path,
                        "line": start + 1, "run": f"{m.group(1).upper()} {cmd}"})
    return out


def entries_from_procfile(path: str, text: str) -> list:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.+)$", line.strip())
        if m:
            cmd = redact(m.group(2))
            out.append({"kind": "procfile", "name": m.group(1), "command": cmd, "file": path, "line": n,
                        "run": f"{m.group(1)}: {cmd}"})
    return out


def entries_from_makefile(path: str, text: str) -> list:
    out = []
    seen = set()
    directory = posixpath.dirname(path)
    for n, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*::?(?!=)", line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            run = f"make -C {directory} {m.group(1)}" if directory else f"make {m.group(1)}"
            out.append({"kind": "make-target", "name": m.group(1), "file": path, "line": n, "run": run})
    return out


# ------------------------------------------------------------------------ routes

def _route_segments(parts):
    segs = []
    for p in parts:
        if (p.startswith("(") and p.endswith(")")) or p.startswith("@"):
            continue
        segs.append(p)
    return "/" + "/".join(segs)


def _next_roots(records, file_set):
    roots = set()
    for path, rec in records.items():
        name = posixpath.basename(path)
        directory = posixpath.dirname(path)
        if re.match(r"^next\.config\.(?:js|mjs|cjs|ts|mts)$", name):
            roots.add(directory)
        elif name == "package.json" and rec.get("_deps") and "next" in rec["_deps"]:
            roots.add(directory)
    return roots


def file_routes(path: str, rec: dict, next_roots) -> list:
    """Routes implied by file-system routing conventions."""
    routes = []
    name = posixpath.basename(path)
    stem, ext = posixpath.splitext(name)
    if rec["language"] not in JS_LANGUAGES:
        return routes
    for root in next_roots:
        prefix = root + "/" if root else ""
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):]
        for app_dir in ("app/", "src/app/"):
            if rest.startswith(app_dir):
                parts = rest[len(app_dir):].split("/")[:-1]
                if stem == "page":
                    routes.append({"method": "PAGE", "path": _route_segments(parts), "line": 1,
                                   "handler": name, "framework": "nextjs-app"})
                elif stem == "route":
                    methods = ",".join(rec.get("_http_handlers") or []) or "ANY"
                    routes.append({"method": methods, "path": _route_segments(parts), "line": 1,
                                   "handler": name, "framework": "nextjs-app"})
        for pages_dir in ("pages/", "src/pages/"):
            if rest.startswith(pages_dir) and not stem.startswith("_"):
                parts = rest[len(pages_dir):].split("/")
                parts[-1] = stem
                if parts[-1] == "index":
                    parts = parts[:-1]
                method = "ANY" if parts and parts[0] == "api" else "PAGE"
                routes.append({"method": method, "path": "/" + "/".join(parts), "line": 1,
                               "handler": name, "framework": "nextjs-pages"})
    marker = "src/routes/"
    idx = path.find(marker)
    if idx != -1 and (idx == 0 or path[idx - 1] == "/") and stem in ("+page", "+server"):
        parts = path[idx + len(marker):].split("/")[:-1]
        if stem == "+page":
            method = "PAGE"
        else:
            method = ",".join(rec.get("_http_handlers") or []) or "ANY"
        routes.append({"method": method, "path": _route_segments(parts), "line": 1,
                       "handler": name, "framework": "sveltekit"})
    return routes


# --------------------------------------------------------------------- resolution

class Resolver:
    def __init__(self, records, file_set):
        self.file_set = file_set
        self.code = {p for p, r in records.items() if r["category"] == "code"}
        self.py_files = {p for p, r in records.items() if r["language"] == "Python"}
        self._pkg_cache = {}
        self.module_index = defaultdict(list)
        for p in sorted(self.py_files):
            name = self.module_name(p)
            if name:
                self.module_index[name].append(p)
        self.workspaces = {}
        for p in sorted(records):
            info = records[p].get("_pkg")
            if info and info.get("name") and posixpath.dirname(p) and info["name"] not in self.workspaces:
                self.workspaces[info["name"]] = (posixpath.dirname(p), info["entries"])
        self.ts_configs = {}
        for p in sorted(records):
            if posixpath.basename(p) in ("tsconfig.json", "jsconfig.json") and records[p].get("_jsonc") is not None:
                opts = records[p]["_jsonc"].get("compilerOptions", {}) if isinstance(records[p]["_jsonc"], dict) else {}
                directory = posixpath.dirname(p)
                if directory in self.ts_configs and posixpath.basename(p) == "jsconfig.json":
                    continue
                base_url = opts.get("baseUrl") if isinstance(opts.get("baseUrl"), str) else None
                base = _join(directory, base_url) if base_url else directory
                paths = opts.get("paths") if isinstance(opts.get("paths"), dict) else {}
                patterns = [(k, [t for t in v if isinstance(t, str)]) for k, v in sorted(paths.items()) if isinstance(v, list)]
                self.ts_configs[directory] = {"base": base, "has_base_url": base_url is not None, "paths": patterns}

    # Python ---------------------------------------------------------------
    def _is_pkg(self, directory):
        if directory not in self._pkg_cache:
            self._pkg_cache[directory] = bool(directory) and (directory + "/__init__.py") in self.file_set
        return self._pkg_cache[directory]

    def module_root(self, path):
        d = posixpath.dirname(path)
        while d and self._is_pkg(d):
            d = posixpath.dirname(d)
        return d

    def module_name(self, path):
        root = self.module_root(path)
        rel = path[len(root) + 1:] if root else path
        rel = re.sub(r"\.pyi?$", "", rel)
        parts = rel.split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts or not all(p.isidentifier() for p in parts):
            return None
        return ".".join(parts)

    def _py_at(self, base_path):
        for cand in (base_path + ".py", base_path + "/__init__.py", base_path + ".pyi", base_path + "/__init__.pyi"):
            if cand in self.py_files:
                return cand
        return None

    def _py_absolute(self, dotted, importer):
        rel = dotted.replace(".", "/")
        bases = []
        for b in (self.module_root(importer), "", "src", "lib"):
            if b not in bases:
                bases.append(b)
        for b in bases:
            hit = self._py_at(b + "/" + rel if b else rel)
            if hit:
                return hit
        cands = self.module_index.get(dotted)
        stdlib = getattr(sys, "stdlib_module_names", ())
        if cands and dotted.split(".")[0] not in stdlib:
            # Several roots define the module: prefer the one sharing the longest path with the importer.
            return max(sorted(cands), key=lambda c: len(posixpath.commonprefix([c, importer])))
        return None

    def resolve_python(self, imp, importer):
        """Return (targets, external_name or None, unresolved spec or None)."""
        names = [n for n in imp["names"] if n != "*"]
        if imp["level"] == 0:
            module = imp["module"]
            if imp["names"]:
                hits = []
                for n in names:
                    hit = self._py_absolute(module + "." + n, importer)
                    if hit:
                        hits.append(hit)
                if len(hits) == len(names) and hits:
                    return hits, None, None
                base = self._py_absolute(module, importer)
                if base:
                    return sorted(set(hits + [base])), None, None
                if hits:
                    return hits, None, None
                return [], module.split(".")[0], None
            parts = module.split(".")
            for i in range(len(parts), 0, -1):
                hit = self._py_absolute(".".join(parts[:i]), importer)
                if hit:
                    return [hit], None, None
            return [], parts[0], None
        pkg = posixpath.dirname(importer)
        for _ in range(imp["level"] - 1):
            pkg = posixpath.dirname(pkg)
        base = pkg
        if imp["module"]:
            base = (pkg + "/" if pkg else "") + imp["module"].replace(".", "/")
        hits = []
        for n in names:
            hit = self._py_at((base + "/" if base else "") + n)
            if hit:
                hits.append(hit)
        if not hits or len(hits) < len(names):
            hit = self._py_at(base) if base else self._py_at("__init__")
            if hit:
                hits.append(hit)
        if hits:
            return sorted(set(hits)), None, None
        return [], None, "." * imp["level"] + imp["module"]

    # JavaScript -----------------------------------------------------------
    def _js_at(self, p):
        if not p or p.startswith(".."):
            return None
        cands = [p]
        ext = posixpath.splitext(p)[1]
        for alt in JS_EXT_SWAP.get(ext, ()):
            cands.append(p[: -len(ext)] + alt)
        cands += [p + e for e in JS_RESOLVE_EXT]
        cands += [p + "/index" + e for e in JS_RESOLVE_EXT if e != ".json"]
        for c in cands:
            if c in self.file_set:
                return c
        return None

    def _ts_config_for(self, importer):
        d = posixpath.dirname(importer)
        while True:
            if d in self.ts_configs:
                return self.ts_configs[d]
            if not d:
                return None
            d = posixpath.dirname(d)

    def resolve_js(self, spec, importer):
        """Return (target or None, external_name or None, unresolved spec or None, via_alias)."""
        spec = spec.split("?", 1)[0].split("#", 1)[0]
        if not spec:
            return None, None, None, False
        if spec.startswith(("./", "../")) or spec in (".", ".."):
            target = self._js_at(_join(posixpath.dirname(importer), spec))
            return (target, None, None if target else spec, False)
        cfg = self._ts_config_for(importer)
        if cfg:
            for pattern, targets in cfg["paths"]:
                if "*" in pattern:
                    pre, post = pattern.split("*", 1)
                    if not (spec.startswith(pre) and spec.endswith(post) and len(spec) >= len(pre) + len(post)):
                        continue
                    star = spec[len(pre): len(spec) - len(post)]
                elif spec == pattern:
                    star = ""
                else:
                    continue
                for t in targets:
                    hit = self._js_at(_join(cfg["base"], t.replace("*", star)))
                    if hit:
                        return hit, None, None, True
            if cfg["has_base_url"]:
                hit = self._js_at(_join(cfg["base"], spec))
                if hit:
                    return hit, None, None, True
        if spec.startswith(("/", "$", "~", "#")) or re.match(r"^[a-z]+://", spec):
            # Absolute paths, URLs and unconfigured aliases ($lib, ~/x, #internal) are not packages.
            return None, None, spec, False
        if spec.startswith("node:"):
            return None, spec, None, False
        parts = spec.split("/")
        name = "/".join(parts[:2]) if spec.startswith("@") and len(parts) > 1 else parts[0]
        if name in self.workspaces:
            # A package defined in this repository (monorepo workspace): resolve into its folder.
            directory, entries = self.workspaces[name]
            sub = spec[len(name):].lstrip("/")
            if sub:
                cands = [_join(directory, sub), _join(directory, "src/" + sub)]
            else:
                cands = [_join(directory, e) for e in entries] + [_join(directory, "src/index"), directory]
            for c in cands:
                hit = self._js_at(c)
                if hit:
                    return hit, None, None, True
            return None, None, spec, False
        if name in NODE_BUILTINS:
            name = "node:" + name
        return None, name, None, False


# --------------------------------------------------------------------- analysis

def _strongly_connected(nodes, adj):
    """Iterative Tarjan; returns SCCs with more than one node or a self-loop."""
    index = {}
    low = {}
    on_stack = set()
    stack = []
    result = []
    counter = 0
    for start in nodes:
        if start in index:
            continue
        work = [(start, iter(adj.get(start, ())))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(adj.get(nxt, ()))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1 or node in adj.get(node, ()):
                    result.append(sorted(comp))
    return result


def _example_cycle(component, adj):
    members = set(component)
    start = component[0]
    if start in adj.get(start, ()):
        return [start, start]
    prev = {}
    queue = deque([start])
    seen = {start}
    while queue:
        node = queue.popleft()
        for nxt in sorted(adj.get(node, ())):
            if nxt not in members:
                continue
            if nxt == start:
                path = [node]
                while path[-1] != start:
                    path.append(prev[path[-1]])
                return list(reversed(path)) + [start]
            if nxt not in seen:
                seen.add(nxt)
                prev[nxt] = node
                queue.append(nxt)
    return component + [start]


def build_map(root: str, max_files: int = DEFAULT_MAX_FILES, use_gitignore: bool = True) -> dict:
    """Scan `root` and return the full (unfocused) map as a dict."""
    root = os.path.abspath(root)
    listed, info = collect_files(root, max_files, use_gitignore)
    file_set = {p for p, _ in listed}
    records = {}
    counters = {"not_opened": 0, "binary": 0, "too_large": 0}
    parse_errors = []
    for rel, size in listed:
        name = posixpath.basename(rel)
        language, category = classify(name)
        rec = {"path": rel, "language": language, "category": category, "bytes": size, "lines": None,
               "is_test": is_test_path(rel), "generated": False}
        records[rel] = rec
        abs_path = os.path.join(root, *rel.split("/"))
        if looks_secret(name) and category != "code":
            rec["not_opened"] = "credential-like name"
            counters["not_opened"] += 1
            continue
        if language is None:
            if "." in name or size > PARSE_LIMIT:
                counters["not_opened"] += 1
                continue
            try:
                with open(abs_path, "rb") as fh:
                    head = fh.read(128)
            except OSError:
                continue
            if not head.startswith(b"#!"):
                counters["not_opened"] += 1
                continue
            first = head.split(b"\n", 1)[0].decode("utf-8", "replace")
            rec["_shebang"] = first
            if "python" in first:
                rec["language"], rec["category"] = "Python", "code"
            elif re.search(r"\b(?:node|deno|bun)\b", first):
                rec["language"], rec["category"] = "JavaScript", "code"
            elif re.search(r"\b(?:ba|z|k)?sh\b", first):
                rec["language"], rec["category"] = "Shell", "code"
            else:
                rec["language"], rec["category"] = "Script", "code"
            language = rec["language"]
        try:
            text, binary, lines = _read_text(abs_path)
        except OSError:
            continue
        rec["lines"] = lines
        if binary:
            rec["binary"] = True
            counters["binary"] += 1
            continue
        if text is None:
            rec["too_large"] = True
            counters["too_large"] += 1
            continue
        if name.endswith((".min.js", ".min.css", ".bundle.js")) or GENERATED_MARK.search(text[:2048]):
            rec["generated"] = True
        if text.startswith("#!") and "_shebang" not in rec:
            rec["_shebang"] = text.split("\n", 1)[0]
        lower = name.lower()
        if language == "Python":
            parsed = parse_python(text, rel)
            if parsed["parse_error"]:
                rec["parse_error"] = True
                parse_errors.append(rel)
            else:
                rec["_imports"] = parsed["imports"]
                rec["symbols"] = parsed["symbols"]
                rec["_main_line"] = parsed["main_line"]
                rec["_routes"] = parsed["routes"]
            if lower == "setup.py":
                rec["_entries"] = entries_from_setup_py(rel, text)
        elif language in JS_LANGUAGES:
            parsed = parse_js(text)
            rec["_imports"] = parsed["imports"]
            if language in ("JavaScript", "TypeScript"):
                rec["symbols"] = parsed["symbols"]
            rec["_routes"] = parsed["routes"]
            rec["_http_handlers"] = parsed["http_handlers"]
        elif language == "Go":
            if re.search(r"^package\s+main\b", text, re.M) and re.search(r"^func\s+main\s*\(\s*\)", text, re.M):
                d = posixpath.dirname(rel)
                rec["_entries"] = [{"kind": "go-main", "name": "main", "file": rel,
                                    "run": f"go run ./{d}" if d else "go run ."}]
        elif language == "Rust":
            m = re.search(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+main\s*\(", text, re.M)
            if m:
                parts = rel.split("/")
                run = None
                if len(parts) >= 2 and parts[-2:] == ["src", "main.rs"]:
                    crate = "/".join(parts[:-2])
                    run = f"cargo run --manifest-path {crate}/Cargo.toml" if crate else "cargo run"
                elif len(parts) >= 3 and parts[-3:-1] == ["src", "bin"]:
                    run = "cargo run --bin " + parts[-1][:-3]
                elif len(parts) >= 2 and parts[-2] == "examples":
                    run = "cargo run --example " + parts[-1][:-3]
                rec["_entries"] = [{"kind": "rust-main", "name": "main", "file": rel,
                                    "line": text.count("\n", 0, m.start()) + 1, "run": run or rel}]
        if lower == "package.json":
            rec["_entries"] = entries_from_package_json(rel, text, file_set)
            try:
                pkg = json.loads(text)
                deps = set()
                for key in ("dependencies", "devDependencies", "peerDependencies"):
                    if isinstance(pkg.get(key), dict):
                        deps |= set(pkg[key])
                rec["_deps"] = deps
                rec["_pkg"] = {"name": pkg.get("name") if isinstance(pkg.get("name"), str) else None,
                               "entries": _package_entries(pkg)}
            except (ValueError, AttributeError):
                pass
        elif lower == "pyproject.toml":
            rec["_entries"] = entries_from_pyproject(rel, text)
        elif lower == "setup.cfg":
            rec["_entries"] = entries_from_setup_cfg(rel, text)
        elif lower in ("tsconfig.json", "jsconfig.json"):
            try:
                rec["_jsonc"] = _parse_jsonc(text)
            except ValueError:
                rec["_jsonc"] = None
        elif rec["language"] == "Dockerfile":
            rec["_entries"] = entries_from_dockerfile(rel, text)
        elif lower == "procfile":
            rec["_entries"] = entries_from_procfile(rel, text)
        elif rec["language"] == "Makefile":
            rec["_entries"] = entries_from_makefile(rel, text)

    resolver = Resolver(records, file_set)
    edge_kinds = defaultdict(set)
    edge_line = {}
    for path in sorted(records):
        rec = records[path]
        imports = rec.pop("_imports", None)
        if imports is None:
            continue
        externals = set()
        unresolved = set()
        for imp in imports:
            targets = []
            if rec["language"] == "Python":
                targets, ext, bad = resolver.resolve_python(imp, path)
                if ext:
                    externals.add(ext)
            else:
                target, ext, bad, _alias = resolver.resolve_js(imp["spec"], path)
                if target:
                    targets = [target]
                if ext:
                    externals.add(ext)
            if bad:
                unresolved.add(bad)
            for t in targets:
                if t == path and rec["language"] == "Python" and posixpath.basename(path) == "__init__.py":
                    continue
                if t in resolver.code:
                    edge_kinds[(path, t)].add(imp["kind"])
                    edge_line.setdefault((path, t), imp["line"])
        rec["external"] = sorted(externals)
        if unresolved:
            rec["unresolved"] = sorted(unresolved)

    stdlib = getattr(sys, "stdlib_module_names", None)
    out_edges = defaultdict(set)
    in_edges = defaultdict(set)
    runtime_adj = defaultdict(set)
    edges = []
    for (src, tgt) in sorted(edge_kinds):
        kinds = sorted(edge_kinds[(src, tgt)])
        edges.append({"source": src, "target": tgt, "kinds": kinds, "line": edge_line[(src, tgt)]})
        out_edges[src].add(tgt)
        in_edges[tgt].add(src)
        if RUNTIME_EDGE_KINDS & set(kinds):
            runtime_adj[src].add(tgt)

    for path, rec in records.items():
        if rec["language"] in GRAPH_LANGUAGES and rec["category"] == "code":
            importers = sorted(in_edges.get(path, ()))
            rec["imports"] = sorted(out_edges.get(path, ()))
            rec["imported_by"] = importers
            rec["fan_out"] = len(rec["imports"])
            rec["fan_in"] = sum(1 for i in importers if not records[i]["is_test"])
            rec["tested_by"] = [i for i in importers if records[i]["is_test"]]

    # Entry points and routes
    entry_points = []
    next_roots = _next_roots(records, file_set)
    routes = []
    for path in sorted(records):
        rec = records[path]
        entry_points += rec.pop("_entries", [])
        for r in rec.pop("_routes", []):
            routes.append(dict(r, file=path))
        if rec["category"] == "code":
            for r in file_routes(path, rec, next_roots):
                routes.append(dict(r, file=path))
        rec.pop("_http_handlers", None)
        rec.pop("_jsonc", None)
        rec.pop("_deps", None)
        rec.pop("_pkg", None)
        main_line = rec.pop("_main_line", None)
        shebang = rec.pop("_shebang", None)
        if rec["language"] == "Python" and not rec["is_test"]:
            if posixpath.basename(path) == "__main__.py":
                module = resolver.module_name(path)
                module = module[: -len(".__main__")] if module and module.endswith(".__main__") else None
                if module:
                    entry_points.append({"kind": "python-module", "name": module, "file": path,
                                         "run": f"python -m {module}"})
            elif main_line:
                in_pkg = resolver._is_pkg(posixpath.dirname(path))
                module = resolver.module_name(path) if in_pkg else None
                entry_points.append({"kind": "python-main-guard", "name": posixpath.basename(path), "file": path,
                                     "line": main_line, "run": f"python -m {module}" if module else f"python {path}"})
        if shebang and not rec["is_test"] and (rec["category"] == "code"):
            if rec["language"] not in ("Python",) or "." not in posixpath.basename(path):
                entry_points.append({"kind": "shebang", "name": posixpath.basename(path), "file": path, "line": 1,
                                     "interpreter": shebang[2:].strip(), "run": f"./{path}"})
    kind_order = ["docker", "procfile", "package-bin", "python-script", "python-module", "package-main",
                  "npm-script", "make-target", "go-main", "rust-main", "shebang", "python-main-guard"]
    entry_points.sort(key=lambda e: (kind_order.index(e["kind"]) if e["kind"] in kind_order else 99,
                                     e["file"], e.get("line") or 0))
    routes.sort(key=lambda r: (r["file"], r["line"], r["path"], r["method"]))

    entry_files = set()
    for e in entry_points:
        entry_files.add(e["file"])
        if e.get("target") in file_set:
            entry_files.add(e["target"])
        entry_files.update(e.get("targets", []))
    for e in entry_points:
        if e["kind"] == "python-script" and ":" in e.get("target", ""):
            module = e["target"].split(":", 1)[0].strip()
            hit = resolver._py_absolute(module, e["file"])
            if hit:
                entry_files.add(hit)
    route_files = {r["file"] for r in routes}

    cycles = []
    for comp in _strongly_connected(sorted(runtime_adj), {k: sorted(v) for k, v in runtime_adj.items()}):
        cycles.append({"files": comp, "size": len(comp), "example": _example_cycle(comp, runtime_adj)})
    cycles.sort(key=lambda c: (-c["size"], c["files"]))

    externals = defaultdict(lambda: {"files": 0})
    for rec in records.values():
        for name in rec.get("external", []):
            eco = "python" if rec["language"] == "Python" else "js"
            item = externals[(eco, name)]
            item["files"] += 1
    external_list = []
    for (eco, name), item in externals.items():
        entry = {"name": name, "ecosystem": eco, "files": item["files"]}
        if eco == "python":
            entry["stdlib"] = bool(stdlib) and name in stdlib
        else:
            entry["stdlib"] = name.startswith("node:")
        external_list.append(entry)
    external_list.sort(key=lambda d: (-d["files"], d["ecosystem"], d["name"]))

    files = [records[p] for p in sorted(records)]
    for rec in files:
        rec["entry_point"] = rec["path"] in entry_files
        rec["route_file"] = rec["path"] in route_files
    stats = {
        "files": len(files),
        "lines": sum(r["lines"] or 0 for r in files),
        "code_files": sum(1 for r in files if r["category"] == "code"),
        "graph_files": sum(1 for r in files if "imports" in r),
        "edges": len(edges),
        "truncated": info["truncated"],
        "max_files": max_files,
        "gitignore": use_gitignore,
        "ignored_paths": info["ignored_paths"],
        "skipped_dirs": len(info["skipped_dirs"]),
        "skipped_dir_examples": sorted(info["skipped_dirs"])[:20],
        "symlinks_skipped": info["symlinks_skipped"],
        "not_opened": counters["not_opened"],
        "binary": counters["binary"],
        "too_large": counters["too_large"],
        "parse_errors": sorted(parse_errors),
    }
    return {
        "tool": "map_codebase", "version": VERSION, "schema_version": SCHEMA_VERSION,
        "root": os.path.basename(root) or root, "focus": None, "stats": stats,
        "files": files, "edges": edges, "entry_points": entry_points, "routes": routes,
        "cycles": cycles, "external_dependencies": external_list,
    }


# ------------------------------------------------------------------- reporting

def _summaries(files, cycles, top):
    langs = defaultdict(lambda: {"files": 0, "lines": 0, "category": None})
    dirs = defaultdict(lambda: {"files": 0, "lines": 0, "lang_lines": defaultdict(int)})
    for r in files:
        if r["language"]:
            item = langs[r["language"]]
            item["files"] += 1
            item["lines"] += r["lines"] or 0
            item["category"] = item["category"] or r["category"]
        key = r["path"].split("/", 1)[0] if "/" in r["path"] else "(root files)"
        d = dirs[key]
        d["files"] += 1
        d["lines"] += r["lines"] or 0
        if r["category"] == "code" and r["language"]:
            d["lang_lines"][r["language"]] += max(r["lines"] or 0, 1)
    languages = sorted(({"language": k, "category": v["category"], "files": v["files"], "lines": v["lines"]}
                        for k, v in langs.items()), key=lambda x: (-x["lines"], -x["files"], x["language"]))
    directories = []
    for k, v in dirs.items():
        main = sorted(v["lang_lines"].items(), key=lambda kv: (-kv[1], kv[0]))
        directories.append({"path": k, "files": v["files"], "lines": v["lines"], "main_language": main[0][0] if main else None})
    directories.sort(key=lambda x: (-x["lines"], -x["files"], x["path"]))
    code = [r for r in files if r["category"] == "code" and not r["generated"]]
    graph = [r for r in files if "imports" in r]
    largest = sorted(code, key=lambda r: (-(r["lines"] or 0), r["path"]))[:top]
    fan_in = sorted((r for r in graph if r["fan_in"]), key=lambda r: (-r["fan_in"], r["path"]))[:top]
    fan_out = sorted((r for r in graph if r["fan_out"]), key=lambda r: (-r["fan_out"], r["path"]))[:top]
    unreferenced = []
    for r in graph:
        name = posixpath.basename(r["path"])
        stem = name.split(".", 1)[0]
        if (r["imported_by"] or r["is_test"] or r["entry_point"] or r["route_file"] or name in NOT_UNREFERENCED_NAMES
                or stem in FRAMEWORK_FILE_STEMS or stem.startswith("+") or ".config." in name or name.endswith(".d.ts")
                or "migrations" in r["path"].split("/")):
            continue
        unreferenced.append(r)
    unreferenced.sort(key=lambda r: (-(r["lines"] or 0), r["path"]))
    hotspots = {
        "largest": [{"path": r["path"], "lines": r["lines"], "language": r["language"]} for r in largest],
        "most_imported": [{"path": r["path"], "fan_in": r["fan_in"], "tested_by": len(r["tested_by"])} for r in fan_in],
        "most_dependencies": [{"path": r["path"], "fan_out": r["fan_out"]} for r in fan_out],
        "cycles": cycles,
        "unreferenced": [{"path": r["path"], "lines": r["lines"]} for r in unreferenced[:top]],
        "unreferenced_total": len(unreferenced),
    }
    return languages, directories, hotspots


def finalize(full: dict, top: int = DEFAULT_TOP, focus: str | None = None, depth: int = DEFAULT_DEPTH) -> dict:
    """Apply an optional focus and attach summaries and hotspots."""
    files = full["files"]
    by_path = {r["path"]: r for r in files}
    result = dict(full)
    if focus:
        focus = focus.strip("/")
        selected = {p for p in by_path if p == focus or p.startswith(focus + "/")}
        if not selected:
            raise ValueError(f"focus {focus!r} matches no scanned file")
        neighbors = set()
        frontier = set(selected)
        for _ in range(max(depth, 0)):
            nxt = set()
            for p in frontier:
                rec = by_path[p]
                nxt |= set(rec.get("imports", [])) | set(rec.get("imported_by", []))
            nxt -= selected | neighbors
            neighbors |= nxt
            frontier = nxt
        keep = selected | neighbors
        files = [dict(by_path[p], in_focus=p in selected) for p in sorted(keep)]
        result["files"] = files
        result["edges"] = [e for e in full["edges"] if e["source"] in keep and e["target"] in keep]
        result["entry_points"] = [e for e in full["entry_points"] if e["file"] in selected]
        result["routes"] = [r for r in full["routes"] if r["file"] in selected]
        result["cycles"] = [c for c in full["cycles"] if selected & set(c["files"])]
        ext = defaultdict(int)
        for p in selected:
            for name in by_path[p].get("external", []):
                ext[("python" if by_path[p]["language"] == "Python" else "js", name)] += 1
        known = {(d["ecosystem"], d["name"]): d for d in full["external_dependencies"]}
        result["external_dependencies"] = sorted(
            (dict(known[k], files=v) for k, v in ext.items()), key=lambda d: (-d["files"], d["ecosystem"], d["name"]))
        result["focus"] = {"path": focus, "depth": depth, "files_in_focus": len(selected), "neighbors": len(neighbors)}
        summary_files = [f for f in files if f["in_focus"]]
    else:
        summary_files = files
    languages, directories, hotspots = _summaries(summary_files, result["cycles"], top)
    result["languages"] = languages
    result["directories"] = directories
    result["hotspots"] = hotspots
    ordered = {}
    for key in ("tool", "version", "schema_version", "root", "focus", "stats", "languages", "directories",
                "entry_points", "routes", "hotspots", "external_dependencies", "files", "edges"):
        ordered[key] = result[key]
    return ordered


def _cell(value) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= 90 else text[:87] + "..."


def _code(value) -> str:
    text = _cell(value)
    return "`" + text.replace("`", "'") + "`"


def render_markdown(m: dict, top: int = DEFAULT_TOP) -> str:
    s = m["stats"]
    out = [f"# Codebase map: {m['root']}", ""]
    langs = ", ".join(f"{x['language']} {x['files']}" for x in m["languages"] if x["category"] == "code")
    out.append(f"{s['files']:,} files, {s['lines']:,} lines. Code files: {s['code_files']:,}"
               + (f" ({langs})." if langs else "."))
    out.append(f"Import graph: {s['graph_files']:,} Python/JS/TS files, {s['edges']:,} internal edges.")
    skipped = [
        f"{s['skipped_dirs']} vendor/build/env dirs",
        f"{s['ignored_paths']} gitignored paths" if s["gitignore"] else "gitignore not applied",
        f"{s['symlinks_skipped']} symlinks",
        f"{s['not_opened']} files not opened (unknown type or credential-like name)",
    ]
    out.append("Skipped: " + ", ".join(skipped) + ".")
    if s["parse_errors"]:
        shown = ", ".join(_code(p) for p in s["parse_errors"][:5])
        more = f" and {len(s['parse_errors']) - 5} more" if len(s["parse_errors"]) > 5 else ""
        out.append(f"Parse errors (no imports or symbols read): {shown}{more}.")
    if s["truncated"]:
        out.append(f"**Truncated at {s['max_files']:,} files: results are partial.** Re-run with `--focus <dir>` "
                   "or a higher `--max-files`.")
    if m["focus"]:
        f = m["focus"]
        out.append(f"Focus: {_code(f['path'])} ({f['files_in_focus']} files) plus {f['neighbors']} neighbors "
                   f"within {f['depth']} import hop(s). Sections below cover the focus files only.")
    out += ["", "## Languages", "", "| Language | Kind | Files | Lines |", "|---|---|---:|---:|"]
    for x in m["languages"][:top]:
        out.append(f"| {x['language']} | {x['category']} | {x['files']:,} | {x['lines']:,} |")
    if len(m["languages"]) > top:
        out.append(f"| ... {len(m['languages']) - top} more | | | |")
    out += ["", "## Layout", "", "| Path | Files | Lines | Main code language |", "|---|---:|---:|---|"]
    for d in m["directories"][:top]:
        out.append(f"| {_code(d['path'])} | {d['files']:,} | {d['lines']:,} | {d['main_language'] or '-'} |")
    if len(m["directories"]) > top:
        out.append(f"| ... {len(m['directories']) - top} more | | | |")
    out += ["", "## Entry points", ""]
    eps = m["entry_points"]
    if eps:
        limit = max(top * 2, 10)
        out += ["| Kind | Run | Defined in |", "|---|---|---|"]
        for e in eps[:limit]:
            run = e.get("run") or e["name"]
            if e.get("command") and e["kind"] == "npm-script":
                run = f"{run} -> {e['command']}"
            where = e["file"] + (f":{e['line']}" if e.get("line") else "")
            out.append(f"| {e['kind']} | {_code(run)} | {_code(where)} |")
        if len(eps) > limit:
            out.append(f"\n{len(eps) - limit} more in `--json` output.")
    else:
        out.append("None detected. Check the README, CI workflow files and framework config by hand.")
    rts = m["routes"]
    out += ["", f"## Routes ({len(rts)})", ""]
    if rts:
        limit = max(top * 2, 10)
        out += ["| Method | Path | Handler | File |", "|---|---|---|---|"]
        for r in rts[:limit]:
            out.append(f"| {r['method']} | {_code(r['path'])} | {_code(r['handler'])} | {_code(r['file'] + ':' + str(r['line']))} |")
        if len(rts) > limit:
            out.append(f"\n{len(rts) - limit} more in `--json` output.")
    else:
        out.append("None detected by the obvious patterns (route decorators, urls.py, Express-style routers, "
                   "Next.js and SvelteKit file routes).")
    h = m["hotspots"]
    out += ["", "## Hotspots", ""]

    def listing(items, fmt):
        return ", ".join(fmt(i) for i in items) if items else "none"

    out.append("- **Largest code files (lines):** " + listing(h["largest"], lambda i: f"{_code(i['path'])} {i['lines'] or 0:,}"))
    out.append("- **Most imported (fan-in, tests excluded):** "
               + listing(h["most_imported"], lambda i: f"{_code(i['path'])} {i['fan_in']}"))
    out.append("- **Most internal dependencies (fan-out):** "
               + listing(h["most_dependencies"], lambda i: f"{_code(i['path'])} {i['fan_out']}"))
    cyc = h["cycles"]
    if cyc:
        out.append(f"- **Import cycles ({len(cyc)}, runtime imports only):**")
        for c in cyc[:top]:
            out.append("  - " + " -> ".join(_code(p) for p in c["example"])
                       + (f" (component of {c['size']} files)" if c["size"] > len(c["example"]) - 1 else ""))
        if len(cyc) > top:
            out.append(f"  - {len(cyc) - top} more in `--json` output.")
    else:
        out.append("- **Import cycles:** none among runtime imports.")
    if h["unreferenced"]:
        out.append(f"- **Not imported by any scanned file ({h['unreferenced_total']}; verify before calling it dead code):** "
                   + listing(h["unreferenced"], lambda i: _code(i["path"])))
    deps = m["external_dependencies"]
    out += ["", "## External imports", ""]
    if deps:
        for eco, label in (("python", "Python"), ("js", "JS/TS")):
            third = [d for d in deps if d["ecosystem"] == eco and not d["stdlib"]][:top]
            std = [d for d in deps if d["ecosystem"] == eco and d["stdlib"]][:top]
            if third:
                out.append(f"- **{label} packages:** " + ", ".join(f"{_code(d['name'])} ({d['files']})" for d in third))
            if std:
                out.append(f"- **{label} standard library / built-ins:** " + ", ".join(_code(d["name"]) for d in std))
    else:
        out.append("None found.")
    if m["focus"]:
        focus_files = [f for f in m["files"] if f.get("in_focus")]
        limit = max(top * 2, 10)
        out += ["", f"## Focus files ({len(focus_files)})", ""]
        for f in focus_files[:limit]:
            meta = f"{f['language'] or 'unknown'}, {f['lines'] or 0:,} lines"
            if "fan_in" in f:
                meta += f", fan-in {f['fan_in']}, fan-out {f['fan_out']}"
            out.append(f"### {_code(f['path'])} ({meta})")
            if f.get("symbols"):
                syms = f["symbols"][:15]
                more = f" (+{len(f['symbols']) - 15})" if len(f["symbols"]) > 15 else ""
                out.append("- Symbols: " + ", ".join(f"{s['kind']} {_code(s['name'])}:{s['line']}" for s in syms) + more)
            for label, key in (("Imports", "imports"), ("Imported by", "imported_by"), ("Tests importing it", "tested_by")):
                if f.get(key):
                    out.append(f"- {label}: " + ", ".join(_code(p) for p in f[key][:15])
                               + (f" (+{len(f[key]) - 15})" if len(f[key]) > 15 else ""))
            if f.get("external"):
                out.append("- External: " + ", ".join(_code(x) for x in f["external"][:15]))
            if f.get("unresolved"):
                out.append("- Unresolved: " + ", ".join(_code(x) for x in f["unresolved"][:10]))
            if f.get("parse_error"):
                out.append("- Parse error: imports and symbols not read.")
            out.append("")
        if len(focus_files) > limit:
            out.append(f"{len(focus_files) - limit} more focus files in `--json` output; narrow `--focus` to see them here.")
    return "\n".join(out).rstrip() + "\n"


# ----------------------------------------------------------------------------- cli

def _parser():
    p = argparse.ArgumentParser(
        prog="map_codebase.py",
        description="Read-only structural map of a repository: languages, entry points, routes, "
                    "Python and JS/TS import graph, top-level symbols and hotspots. "
                    "Standard library only; never writes files or uses the network.",
        epilog="Examples:\n"
               "  python3 map_codebase.py .                       # Markdown summary\n"
               "  python3 map_codebase.py . --json > /tmp/map.json\n"
               "  python3 map_codebase.py . --focus src/billing --depth 1\n"
               "Output is written to stdout only. Heuristic: verify findings in the code.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("root", nargs="?", default=".", help="repository or directory to map (default: .)")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="print the full map as JSON")
    fmt.add_argument("--md", action="store_true", help="print a concise Markdown summary (default)")
    p.add_argument("--focus", metavar="PATH", help="limit the report to this file or directory (relative to root) "
                                                     "plus its import neighbors")
    p.add_argument("--depth", type=int, default=DEFAULT_DEPTH, metavar="N",
                   help=f"import hops of neighbors to include with --focus (default: {DEFAULT_DEPTH}; 0 = none)")
    p.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, metavar="N",
                   help=f"stop after listing N files; output is then marked truncated (default: {DEFAULT_MAX_FILES})")
    p.add_argument("--top", type=int, default=DEFAULT_TOP, metavar="N",
                   help=f"rows per Markdown list and hotspot list (default: {DEFAULT_TOP})")
    p.add_argument("--no-gitignore", action="store_true", help="do not apply .gitignore rules (vendor/build dirs are still skipped)")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.max_files < 1 or args.top < 1 or args.depth < 0:
        parser.error("--max-files and --top must be >= 1 and --depth >= 0")
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    focus = None
    if args.focus:
        absolute = os.path.abspath(os.path.join(root, args.focus)) if not os.path.isabs(args.focus) else os.path.abspath(args.focus)
        if not os.path.exists(absolute):
            print(f"error: focus path {args.focus} does not exist", file=sys.stderr)
            return 2
        rel = os.path.relpath(absolute, root).replace(os.sep, "/")
        if rel.startswith(".."):
            print(f"error: focus path {args.focus} is outside {args.root}", file=sys.stderr)
            return 2
        focus = None if rel == "." else rel
    full = build_map(root, max_files=args.max_files, use_gitignore=not args.no_gitignore)
    try:
        result = finalize(full, top=args.top, focus=focus, depth=args.depth)
    except ValueError as exc:
        print(f"error: {exc} (it may be gitignored, in a skipped directory or beyond --max-files)", file=sys.stderr)
        return 2
    if args.json:
        text = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    else:
        text = render_markdown(result, top=args.top)
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(text.encode("utf-8"))
    else:
        sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
