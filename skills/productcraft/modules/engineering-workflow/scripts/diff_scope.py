#!/usr/bin/env python3
"""ProductCraft Engineering Workflow: read-only self-review summary of a diff.

Reads a unified diff (a file, stdin, or `git diff` output) and reports which
files changed, whether tests moved with the code, and advisory findings an
author should check before calling a change done. It never edits files, never
touches the network and never prints the text of changed lines (only the
matched token), so secrets in a diff are not echoed back.

Findings are prompts to look, not verdicts. The default exit code is 0; pass
--strict to exit 1 when any WARN finding is present.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple

VERSION = "1.0.0"
DEFAULT_MAX_LINES = 400

CODE_EXT = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".go", ".rs", ".java", ".kt", ".kts", ".scala", ".rb", ".php", ".cs", ".fs",
    ".swift", ".m", ".mm", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".ex", ".exs",
    ".erl", ".hs", ".clj", ".dart", ".lua", ".pl", ".r", ".jl", ".sh", ".bash",
    ".zsh", ".ps1", ".sql",
}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}
DOC_EXT = {".md", ".markdown", ".rst", ".txt", ".adoc"}
LOCKFILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "poetry.lock", "pipfile.lock", "uv.lock", "pdm.lock", "cargo.lock", "go.sum",
    "gemfile.lock", "composer.lock", "packages.lock.json", "mix.lock", "pubspec.lock",
    "gradle.lockfile",
}
MANIFESTS = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "pipfile", "cargo.toml",
    "go.mod", "gemfile", "composer.json", "pom.xml", "build.gradle", "build.gradle.kts",
    "mix.exs", "pubspec.yaml", "directory.packages.props",
}
GENERATED_DIRS = {"dist", "build", "out", "target", "node_modules", "__pycache__", ".next", "coverage"}
GENERATED_SUFFIXES = (".min.js", ".min.css", ".js.map", ".css.map", ".pyc", ".class", ".o")
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs"}

# (code, severity, file extensions or None for any code/test file, pattern, label)
DEBUG_RULES = [
    (JS_EXT, re.compile(r"\bconsole\.(?:log|debug|trace|dir)\s*\("), "console.log/debug call"),
    (JS_EXT, re.compile(r"^\s*debugger\s*;?\s*$"), "debugger statement"),
    ({".py"}, re.compile(r"\bbreakpoint\(\s*\)"), "breakpoint()"),
    ({".py"}, re.compile(r"\b(?:i?pdb|pudb)\.set_trace\s*\("), "pdb.set_trace()"),
    ({".py"}, re.compile(r"^\s*(?:import\s+(?:i?pdb|pudb)\b|from\s+(?:i?pdb|pudb)\s+import\b)"), "debugger import"),
    ({".rb"}, re.compile(r"\bbinding\.(?:pry|irb)\b|^\s*byebug\b"), "Ruby debugger hook"),
    ({".rs"}, re.compile(r"\bdbg!\s*\("), "dbg! macro"),
    ({".php"}, re.compile(r"\b(?:var_dump|print_r|dd)\s*\("), "PHP dump call"),
]
FOCUS_RE = re.compile(
    r"\b(?:describe|it|test|context|suite)\.only\s*\(|(?<![\w.$])(?:fdescribe|fit|fcontext)\s*\("
)
SKIP_RE = re.compile(
    r"\b(?:describe|it|test|context|suite)\.skip\s*\("
    r"|(?<![\w.$])(?:xit|xdescribe|xtest|xcontext)\s*\("
    r"|@pytest\.mark\.skip\b(?!if)|@unittest\.skip\b(?!If|Unless)"
    r"|#\[ignore\]|@Disabled\b|@Ignore\b|\bSkip\s*=\s*\""
)
ASSERT_RE = re.compile(
    r"\bassert|\bexpect\s*\(|\.should\b|\bt\.(?:Error|Errorf|Fatal|Fatalf)\s*\("
    r"|\bAssert\.|\bassertThat\s*\(|\brequire\.\w+\s*\("
)
TODO_RE = re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b")
CONFLICT_RE = re.compile(r"^(?:<{7}|>{7})(?: |$)")
CONFLICT_MID_RE = re.compile(r"^={7}$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

SEVERITY_ORDER = {"WARN": 0, "INFO": 1}


@dataclass
class Hunk:
    new_start: int
    removed: List[str] = field(default_factory=list)
    added: List[str] = field(default_factory=list)


@dataclass
class FileChange:
    path: str
    old_path: Optional[str] = None
    status: str = "M"  # M modified, A added, D deleted, R renamed
    binary: bool = False
    old_mode: Optional[str] = None
    new_mode: Optional[str] = None
    hunks: List[Hunk] = field(default_factory=list)
    added_lines: List[Tuple[int, str]] = field(default_factory=list)
    removed_lines: List[str] = field(default_factory=list)

    @property
    def added(self) -> int:
        return len(self.added_lines)

    @property
    def removed(self) -> int:
        return len(self.removed_lines)


def _strip_prefix(path: str) -> str:
    path = path.strip()
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    path = path.split("\t", 1)[0]
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path


def parse_diff(text: str) -> List[FileChange]:
    """Parse unified diff text (git or plain `diff -u`) into file changes."""
    files: List[FileChange] = []
    cur: Optional[FileChange] = None
    hunk: Optional[Hunk] = None
    old_left = new_left = 0
    new_line = 0
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        in_hunk = hunk is not None and (old_left > 0 or new_left > 0)
        if in_hunk and not (line == "" or line[:1] in "+- \\") or line.startswith("diff --git "):
            in_hunk, old_left, new_left = False, 0, 0  # malformed or truncated hunk: stop counting
        if in_hunk:
            tag = line[:1]
            body = line[1:]
            if tag == "+":
                cur.added_lines.append((new_line, body))
                hunk.added.append(body)
                new_line += 1
                new_left -= 1
            elif tag == "-":
                cur.removed_lines.append(body)
                hunk.removed.append(body)
                old_left -= 1
            elif tag == "\\":
                pass  # "\ No newline at end of file"
            else:  # context line (a bare empty line counts as context)
                new_line += 1
                old_left -= 1
                new_left -= 1
            i += 1
            continue
        if line.startswith("diff --git "):
            m = re.match(r'^diff --git ("?a/.+?"?) ("?b/.+"?)$', line)
            path = _strip_prefix(m.group(2)) if m else line.split()[-1]
            cur = FileChange(path=path)
            files.append(cur)
            hunk = None
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            old = _strip_prefix(line[4:])
            new = _strip_prefix(lines[i + 1][4:])
            if cur is None or cur.hunks:
                cur = FileChange(path=new if new != "/dev/null" else old)
                files.append(cur)
            if old == "/dev/null":
                cur.status = "A"
            elif new == "/dev/null":
                cur.status = "D"
                cur.path = old
            elif cur.status != "R":
                cur.path = new
            hunk = None
            i += 2
            continue
        elif cur is not None:
            if line.startswith("new file mode"):
                cur.status, cur.new_mode = "A", line.split()[-1]
            elif line.startswith("deleted file mode"):
                cur.status, cur.old_mode = "D", line.split()[-1]
            elif line.startswith("old mode "):
                cur.old_mode = line.split()[-1]
            elif line.startswith("new mode "):
                cur.new_mode = line.split()[-1]
            elif line.startswith("rename from "):
                cur.status, cur.old_path = "R", line[len("rename from "):]
            elif line.startswith("rename to "):
                cur.path = line[len("rename to "):]
            elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
                cur.binary = True
            else:
                m = HUNK_RE.match(line)
                if m:
                    old_left = int(m.group(2)) if m.group(2) is not None else 1
                    new_left = int(m.group(4)) if m.group(4) is not None else 1
                    new_line = int(m.group(3))
                    hunk = Hunk(new_start=new_line)
                    cur.hunks.append(hunk)
        i += 1
    return files


def kind_of(path: str) -> str:
    """Classify a path as test, docs, lockfile, manifest, generated, code or other."""
    p = PurePosixPath(path)
    name = p.name
    lower = name.lower()
    parts = [x.lower() for x in p.parts[:-1]]
    if any(x in GENERATED_DIRS for x in parts) or lower.endswith(GENERATED_SUFFIXES):
        return "generated"
    if lower in LOCKFILES:
        return "lockfile"
    if lower in MANIFESTS or re.match(r"requirements[\w.-]*\.txt$", lower) or lower.endswith((".csproj", ".fsproj")):
        return "manifest"
    if (
        any(x in TEST_DIRS for x in parts)
        or lower.startswith("test_")
        or lower == "conftest.py"
        or re.search(r"(?:_test|_tests|_spec|\.test|\.spec)\.[^.]+$", lower)
        or re.search(r"(?:Test|Tests|Spec)\.(?:java|kt|cs|scala|swift|php|groovy)$", name)
    ):
        return "test"
    suffix = p.suffix.lower()
    if suffix in DOC_EXT or "docs" in parts:
        return "docs"
    if suffix in CODE_EXT:
        return "code"
    return "other"


def _matches_scope(path: str, scopes: Iterable[str]) -> bool:
    for s in scopes:
        s = s.strip()
        if not s:
            continue
        if any(ch in s for ch in "*?["):
            if fnmatch.fnmatchcase(path, s):
                return True
        else:
            base = s.rstrip("/")
            if path == base or path.startswith(base + "/"):
                return True
    return False


def _normalized(lines: Iterable[str]) -> List[str]:
    out = [" ".join(x.split()) for x in lines]
    return sorted(x for x in out if x)


def analyze(files: List[FileChange], scopes: Optional[List[str]] = None,
            max_lines: int = DEFAULT_MAX_LINES) -> Dict:
    """Return a deterministic report dict for parsed file changes."""
    findings: List[Dict] = []

    def add(code: str, severity: str, path: str, line: Optional[int], message: str) -> None:
        findings.append({"code": code, "severity": severity, "path": path, "line": line, "message": message})

    kinds = {f.path: kind_of(f.path) for f in files}
    test_touched = any(k == "test" for k in kinds.values())
    manifest_touched = any(k == "manifest" for k in kinds.values())

    for f in files:
        kind = kinds[f.path]
        suffix = PurePosixPath(f.path).suffix.lower()

        if scopes:
            outside = not _matches_scope(f.path, scopes)
            if f.old_path and not _matches_scope(f.old_path, scopes):
                outside = True
            if outside:
                add("OUT_OF_SCOPE", "WARN", f.path, None,
                    "file is outside the declared scope; revert it or say why the change needs it")

        if f.old_mode and f.new_mode and f.old_mode != f.new_mode:
            add("MODE_CHANGE", "WARN", f.path, None,
                f"file mode changed {f.old_mode} -> {f.new_mode}; confirm it was intended")
        if f.binary:
            add("BINARY_FILE", "INFO", f.path, None, "binary content changed; review it outside the diff")
        if kind == "generated":
            add("GENERATED_FILE", "WARN", f.path, None,
                "build output or compiled file changed; keep it only if the project commits these")
        if kind == "lockfile":
            if manifest_touched:
                add("DEPENDENCY_CHANGE", "INFO", f.path, None,
                    "lockfile changed with a manifest; confirm the dependency change was requested")
            else:
                add("LOCKFILE_WITHOUT_MANIFEST", "WARN", f.path, None,
                    "lockfile changed but no dependency manifest did; often churn from an install, revert unless intended")
        if kind == "manifest" and (f.added or f.removed):
            add("DEPENDENCY_CHANGE", "INFO", f.path, None,
                "dependency manifest changed; confirm each added or upgraded package was needed")
        if kind == "test" and f.status == "D":
            add("TEST_FILE_DELETED", "WARN", f.path, None,
                "a test file was deleted; make sure the behavior it covered is still tested or intentionally removed")

        ws_hunks = [h for h in f.hunks if (h.added or h.removed) and _normalized(h.removed) == _normalized(h.added)]
        if ws_hunks:
            add("WHITESPACE_ONLY", "WARN", f.path, ws_hunks[0].new_start,
                f"{len(ws_hunks)} hunk(s) change only whitespace or blank lines; revert unless reformatting was the task "
                "(in indentation-sensitive languages, confirm block structure)")

        has_open_marker = any(CONFLICT_RE.match(t) for _, t in f.added_lines)
        todo_reported = False
        for lineno, text in f.added_lines:
            if CONFLICT_RE.match(text) or (has_open_marker and CONFLICT_MID_RE.match(text)):
                add("CONFLICT_MARKER", "WARN", f.path, lineno, "merge conflict marker added")
            if kind in ("code", "test"):
                for exts, rx, label in DEBUG_RULES:
                    if suffix in exts and rx.search(text):
                        add("DEBUG_LEFTOVER", "WARN", f.path, lineno, f"{label} added; remove it unless it is intended output")
                if TODO_RE.search(text) and not todo_reported:
                    count = sum(1 for _, t in f.added_lines if TODO_RE.search(t))
                    add("NEW_TODO", "INFO", f.path, lineno,
                        f"{count} TODO/FIXME-style marker(s) added; each should name the limit and when to revisit, or be resolved now")
                    todo_reported = True
            if kind == "test":
                if suffix in JS_EXT and FOCUS_RE.search(text):
                    add("FOCUSED_TEST", "WARN", f.path, lineno, "focused test (.only/fit) added; the rest of the suite will not run")
                if SKIP_RE.search(text):
                    add("SKIPPED_TEST", "WARN", f.path, lineno,
                        "skip/ignore marker added; a skipped test is not a passing test, so get agreement or remove it")

        if kind == "test":
            removed_asserts = sum(1 for t in f.removed_lines if ASSERT_RE.search(t))
            added_asserts = sum(1 for _, t in f.added_lines if ASSERT_RE.search(t))
            if removed_asserts > added_asserts:
                add("ASSERTIONS_REMOVED", "WARN", f.path, None,
                    f"net {removed_asserts - added_asserts} assertion line(s) removed; confirm tests were not weakened to pass")

    code_changed = [f for f in files if kinds[f.path] == "code" and (f.added or f.removed)]
    if code_changed and not test_touched:
        add("CODE_WITHOUT_TEST_CHANGE", "INFO", "", None,
            f"{len(code_changed)} code file(s) changed and no test file did; name the existing test that covers this, "
            "or say why no test is needed")

    total = sum(f.added + f.removed for f in files)
    if max_lines and total > max_lines:
        add("LARGE_DIFF", "WARN", "", None,
            f"{total} changed lines (limit {max_lines}); consider splitting into steps a reviewer can check separately")

    findings.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["path"], x["line"] or 0, x["code"], x["message"]))
    by_kind: Dict[str, int] = {}
    for k in kinds.values():
        by_kind[k] = by_kind.get(k, 0) + 1
    return {
        "tool": "diff_scope",
        "version": VERSION,
        "summary": {
            "files": len(files),
            "added": sum(f.added for f in files),
            "removed": sum(f.removed for f in files),
            "by_kind": dict(sorted(by_kind.items())),
            "warn": sum(1 for x in findings if x["severity"] == "WARN"),
            "info": sum(1 for x in findings if x["severity"] == "INFO"),
        },
        "files": [
            {"path": f.path, "old_path": f.old_path, "status": f.status, "kind": kinds[f.path],
             "added": f.added, "removed": f.removed, "binary": f.binary}
            for f in sorted(files, key=lambda x: x.path)
        ],
        "findings": findings,
    }


def format_text(report: Dict) -> str:
    s = report["summary"]
    kinds = ", ".join(f"{k} {v}" for k, v in s["by_kind"].items()) or "none"
    out = [f"diff_scope {report['version']}: {s['files']} file(s), +{s['added']} -{s['removed']} ({kinds})", ""]
    if report["files"]:
        width = max(len(f["path"]) for f in report["files"])
        out.append("Files")
        for f in report["files"]:
            label = f["path"] if not f["old_path"] else f"{f['old_path']} -> {f['path']}"
            out.append(f"  {f['status']}  {label.ljust(width)}  +{f['added']:<5} -{f['removed']:<5} {f['kind']}")
        out.append("")
    if report["findings"]:
        out.append(f"Findings ({s['warn']} warn, {s['info']} info)")
        for x in report["findings"]:
            where = x["path"] + (f":{x['line']}" if x["line"] else "") if x["path"] else "(whole diff)"
            out.append(f"  {x['severity']:<4}  {x['code']:<26} {where}")
            out.append(f"        {x['message']}")
    else:
        out.append("Findings: none")
    out.append("")
    out.append("Advisory only: each finding is a prompt to check, not a verdict. Tests and review decide.")
    return "\n".join(out) + "\n"


def _git(args: List[str], repo: str) -> str:
    proc = subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="diff_scope.py",
        description=(
            "Read-only self-review summary of a unified diff: files changed, whether tests\n"
            "moved with code, and advisory findings (out-of-scope files, whitespace-only\n"
            "hunks, debug leftovers, focused or skipped tests, removed assertions, conflict\n"
            "markers, lockfile churn, generated files, mode changes, oversized diffs).\n"
            "Never edits files or uses the network, and never prints changed line text."
        ),
        epilog=(
            "Examples:\n"
            "  python3 diff_scope.py                          # working tree vs HEAD (git diff HEAD)\n"
            "  python3 diff_scope.py --git main...HEAD --scope src/billing tests/billing\n"
            "  git diff --cached | python3 diff_scope.py --diff -\n"
            "  python3 diff_scope.py --diff change.patch --json\n\n"
            "Untracked files are not part of `git diff`; when RANGE has no '..' they are listed as UNTRACKED_FILES.\n"
            "Exit codes: 0 report written; 1 with --strict when a WARN finding exists; 2 usage or input error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--diff", metavar="FILE", help="read a unified diff from FILE, or '-' for stdin")
    src.add_argument("--git", metavar="RANGE", help="run read-only `git diff RANGE` (default: HEAD)")
    p.add_argument("--repo", default=".", help="repository directory for --git mode (default: .)")
    p.add_argument("--scope", nargs="+", metavar="PATH_OR_GLOB",
                   help="paths or fnmatch globs the change is allowed to touch; others are flagged")
    p.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES,
                   help=f"flag diffs with more changed lines than this; 0 disables (default: {DEFAULT_MAX_LINES})")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.add_argument("--strict", action="store_true", help="exit 1 when any WARN finding is present")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    untracked: List[str] = []
    try:
        if args.diff == "-":
            text = sys.stdin.read()
        elif args.diff:
            with open(args.diff, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        else:
            rng = args.git or "HEAD"
            text = _git(["diff", "--no-color", "--no-ext-diff", "-M", rng], args.repo)
            if ".." not in rng:  # comparing against the working tree, so untracked files matter
                untracked = sorted(x for x in _git(["ls-files", "--others", "--exclude-standard"], args.repo).splitlines() if x)
    except (OSError, RuntimeError) as exc:
        print(f"diff_scope: error: {exc}", file=sys.stderr)
        return 2
    report = analyze(parse_diff(text), scopes=args.scope, max_lines=args.max_lines)
    if untracked:
        shown = ", ".join(untracked[:10]) + (f" (+{len(untracked) - 10} more)" if len(untracked) > 10 else "")
        report["findings"].append({"code": "UNTRACKED_FILES", "severity": "INFO", "path": "", "line": None,
                                   "message": f"{len(untracked)} untracked file(s) are not in this diff: {shown}; "
                                              "add the ones that belong to the change, review the rest separately"})
        report["summary"]["info"] += 1
    report["findings"].sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["path"], x["line"] or 0, x["code"], x["message"]))
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(format_text(report))
    if args.strict and report["summary"]["warn"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
