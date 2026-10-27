#!/usr/bin/env python3
"""ProductCraft Move package and dApp repository lead finder. Offline, read-only, deterministic.

Lists leads in Aptos Move packages and the repositories around them:

  KEY-FILE-TRACKED           high    CLI config with a private key, or a keypair file, tracked by git
  PUBLIC-RETURNS-REF         high    public function returns a ref, a signer or a signer capability
  SIGNER-FROM-REF-UNCHECKED  high    callable function makes a signer from a stored ref with no visible check
  RANDOMNESS-EXPOSED         high    randomness used outside a private entry function marked #[randomness]
  KEY-FILE-UNIGNORED         medium  key-holding file present and not ignored by git (or status unknown)
  TIMESTAMP-RANDOMNESS       medium  timestamp or block height used with % as a source of randomness
  DEP-MOVING-BRANCH          low     Move.toml git dependency pinned to a moving branch
  DEBUG-PRINT                low     debug::print outside test-only code
  HARDCODED-ADDRESS          low     module declared at a literal hex address instead of a named address
  LEGACY-COIN                low     new coin created with the legacy coin module
  NO-TESTS                   low     package without any #[test] function

Leads are not findings and this is not a security audit: read the code and
confirm each lead with a test. The tool never runs the Aptos CLI, never uses the
network, never modifies files and never prints file contents or key material.
It runs read-only `git ls-files` and `git check-ignore` to learn whether key
files are tracked or ignored. Acknowledge a reviewed line with a comment on the
same line or the line above:  move-check: ignore RULE-ID <reason>

Exit codes: 0 no lead at or above --fail-on, 1 at least one, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VERSION = "1.0.0"
LEVELS = ("high", "medium", "low")
LEVEL_RANK = {name: rank for rank, name in enumerate(LEVELS)}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "build", "target", "dist", "out", ".venv", "venv",
    "__pycache__", ".next", ".cache", ".turbo", "coverage", "vendor", ".idea", ".gradle",
}
MAX_FILE_BYTES = 2_000_000
KEYPAIR_MAX_BYTES = 4096

RULES = {
    "KEY-FILE-TRACKED": ("high", "File holds a private key and is tracked by git. Treat the key as exposed: remove the file from the repository, have the owner move any funds and rotate, and ignore the path."),
    "PUBLIC-RETURNS-REF": ("high", "Public function returns a ref, signer or signer capability, so any module that can call it gets that power. Confirm it demands the matching authority, or keep refs inside resources and expose narrow, checked operations."),
    "SIGNER-FROM-REF-UNCHECKED": ("high", "Transaction-callable function creates a signer from a stored ref without a visible authorization check; confirm only authorized callers reach it."),
    "RANDOMNESS-EXPOSED": ("high", "Randomness must be used only in a private (non-public) entry function marked #[randomness]; otherwise callers can test the outcome and abort."),
    "KEY-FILE-UNIGNORED": ("medium", "File holds a private key and is not ignored by git (or its status could not be checked); add it to .gitignore before anything is committed."),
    "TIMESTAMP-RANDOMNESS": ("medium", "Timestamp or block height used with % looks like a randomness source; it is predictable. Use the randomness API."),
    "DEP-MOVING-BRANCH": ("low", "Git dependency pinned to a moving branch; pin a commit or tag for reproducible, auditable builds."),
    "DEBUG-PRINT": ("low", "debug::print outside test-only code; remove it before publishing."),
    "HARDCODED-ADDRESS": ("low", "Module declared at a literal hex address; use a named address set in Move.toml or on the command line."),
    "LEGACY-COIN": ("low", "New coin created with the legacy coin module; new fungible tokens use the Fungible Asset standard."),
    "NO-TESTS": ("low", "Package has no #[test] functions; add tests for success, abort and wrong-signer cases."),
}

IGNORE_RE = re.compile(r"move-check:\s*ignore\s+([A-Z0-9-]+|all)", re.I)
MOVING_BRANCH_RE = re.compile(r"""\brev\s*=\s*["'](main|master|mainnet|testnet|devnet)["']""")
FUN_RE = re.compile(
    r"(?P<prefix>(?:\bpublic(?:\s*\(\s*(?:friend|package)\s*\))?\s+)?(?:\bentry\s+)?(?:\binline\s+)?(?:\bnative\s+)?)\bfun\s+(?P<name>\w+)"
)
REF_TYPES_RE = re.compile(r"\b(?:ConstructorRef|ExtendRef|TransferRef|LinearTransferRef|DeleteRef|MintRef|BurnRef|MutatorRef|SignerCapability|signer)\b")
SIGNER_FROM_REF_RE = re.compile(r"\b(?:generate_signer_for_extending|create_signer_with_capability)\s*\(")
CHECK_RE = re.compile(r"assert|abort|is_owner|\bowns\s*\(|only_|check_|ensure_|require_|verify_|authorize")
RANDOMNESS_CALL_RE = re.compile(r"\brandomness::\w+\s*\(")
TIMESTAMP_RANDOM_RE = re.compile(r"(?:now_(?:seconds|microseconds)|get_current_block_height)\s*\(\s*\)\s*%")
DEBUG_RE = re.compile(r"\bdebug::print\b")
HEX_MODULE_RE = re.compile(r"\bmodule\s+0x[0-9a-fA-F]+::\w+")
LEGACY_COIN_RE = re.compile(r"\b(?:coin|managed_coin)::initialize\s*<")
TEST_ATTR_RE = re.compile(r"#\[\s*test\b")
TEST_ONLY_MODULE_RE = re.compile(r"#\[\s*test_only\s*\]\s*module\b")


def strip_comments_and_strings(text: str) -> str:
    """Blank out comments and string contents, keeping length and newlines, so offsets stay valid."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if c == "/" and nxt == "*":
            out[i] = out[i + 1] = " "
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            if i < n:
                out[i] = " "
                if i + 1 < n:
                    out[i + 1] = " "
            i += 2
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    out[i] = " "
                    i += 1
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            i += 1
            continue
        i += 1
    return "".join(out)


def matching(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket closing the one at `start`, or -1."""
    depth = 0
    for j in range(start, len(text)):
        if text[j] == open_ch:
            depth += 1
        elif text[j] == close_ch:
            depth -= 1
            if depth == 0:
                return j
    return -1


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def attributes_before(code: str, pos: int) -> str:
    """Attribute text directly above (or on the same line before) a declaration."""
    line_start = code.rfind("\n", 0, pos) + 1
    attrs = [code[line_start:pos]]
    k = line_start - 1
    while k > 0:
        prev_start = code.rfind("\n", 0, k) + 1
        line = code[prev_start:k].strip()
        if line.startswith("#["):
            attrs.append(line)
            k = prev_start - 1
            continue
        break
    return " ".join(attrs)


def functions(code: str):
    """Yield function facts from comment-stripped Move source."""
    for m in FUN_RE.finditer(code):
        prefix = re.sub(r"\s*\(\s*", "(", " ".join(m.group("prefix").split()))
        paren = code.find("(", m.end())
        if paren < 0:
            continue
        close = matching(code, paren, "(", ")")
        if close < 0:
            continue
        brace = code.find("{", close)
        semi = code.find(";", close)
        if brace < 0 or (0 <= semi < brace):
            ret, body = code[close + 1: semi if semi >= 0 else close + 1], ""
        else:
            ret = code[close + 1: brace]
            end = matching(code, brace, "{", "}")
            body = code[brace: end + 1 if end >= 0 else len(code)]
        ret = ret.split("acquires")[0]
        attrs = attributes_before(code, m.start())
        yield {
            "name": m.group("name"),
            "line": line_of(code, m.start()),
            "public": prefix.startswith("public") and not prefix.startswith("public("),
            "restricted": prefix.startswith("public("),
            "entry": "entry" in prefix.split(),
            "returns": ret.strip(),
            "body": body,
            "test": bool(re.search(r"#\[\s*test(?:_only)?\b", attrs)),
            "randomness_attr": bool(re.search(r"#\[\s*randomness\b", attrs)),
        }


def scan_move(text: str, test_file: bool) -> list[tuple[str, int]]:
    code = strip_comments_and_strings(text)
    module_test_only = test_file or bool(TEST_ONLY_MODULE_RE.search(code))
    leads: list[tuple[str, int]] = []
    test_ranges: list[tuple[int, int]] = []
    for f in functions(code):
        if f["test"] or module_test_only:
            test_ranges.append((f["line"], f["line"] + f["body"].count("\n")))
            continue
        callable_by_tx = f["public"] or f["entry"]
        if f["public"] and REF_TYPES_RE.search(f["returns"].lstrip(":")) and f["returns"].startswith(":"):
            leads.append(("PUBLIC-RETURNS-REF", f["line"]))
        if callable_by_tx and SIGNER_FROM_REF_RE.search(f["body"]) and not CHECK_RE.search(f["body"]):
            leads.append(("SIGNER-FROM-REF-UNCHECKED", f["line"]))
        uses_random = bool(RANDOMNESS_CALL_RE.search(f["body"]))
        if f["randomness_attr"] and (f["public"] or f["restricted"] or not f["entry"]):
            leads.append(("RANDOMNESS-EXPOSED", f["line"]))
        elif uses_random and (f["public"] or f["restricted"]):
            leads.append(("RANDOMNESS-EXPOSED", f["line"]))
    lines = code.splitlines()
    for i, line in enumerate(lines, 1):
        in_test = module_test_only or any(a <= i <= b for a, b in test_ranges)
        if TIMESTAMP_RANDOM_RE.search(line) and not in_test:
            leads.append(("TIMESTAMP-RANDOMNESS", i))
        if DEBUG_RE.search(line) and not in_test:
            leads.append(("DEBUG-PRINT", i))
        if HEX_MODULE_RE.search(line) and not module_test_only:
            leads.append(("HARDCODED-ADDRESS", i))
        if LEGACY_COIN_RE.search(line) and not in_test:
            leads.append(("LEGACY-COIN", i))
    return leads


def is_keypair_json(path: Path) -> bool:
    try:
        if path.stat().st_size > KEYPAIR_MAX_BYTES:
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    return (isinstance(data, list) and len(data) == 64
            and all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 255 for x in data))


def is_cli_config_with_key(path: Path) -> bool:
    if path.name != "config.yaml" or path.parent.name != ".aptos":
        return False
    try:
        return "private_key" in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


class Git:
    def __init__(self, root: Path):
        self.root = root
        self.ok = self._run("rev-parse", "--is-inside-work-tree") == 0

    def _run(self, *args: str) -> int:
        try:
            proc = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, timeout=20,
                                  env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        except (OSError, subprocess.SubprocessError):
            return -1
        return proc.returncode

    def status(self, rel: str) -> str:
        if not self.ok:
            return "unknown"
        if self._run("ls-files", "--error-unmatch", "--", rel) == 0:
            return "tracked"
        return "ignored" if self._run("check-ignore", "-q", "--", rel) == 0 else "untracked"


def suppressed(lines: list[str], line: int, rule: str) -> bool:
    for k in (line - 1, line - 2):
        if 0 <= k < len(lines):
            for m in IGNORE_RE.finditer(lines[k]):
                if m.group(1).upper() in (rule, "ALL"):
                    return True
    return False


def scan(root: Path, use_git: bool = True) -> dict:
    leads: list[dict] = []
    ignored = 0
    packages, move_files, key_files = [], [], []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            if name == "Move.toml":
                packages.append(path)
            elif name.endswith(".move"):
                move_files.append(path)
            elif name == "config.yaml" and is_cli_config_with_key(path):
                key_files.append(path)
            elif name.endswith(".json") and is_keypair_json(path):
                key_files.append(path)

    def add(rule: str, rel: str, line: int, lines: list[str] | None = None, note: str = "") -> None:
        nonlocal ignored
        if lines is not None and suppressed(lines, line, rule):
            ignored += 1
            return
        level, message = RULES[rule]
        leads.append({"rule": rule, "level": level, "file": rel, "line": line,
                      "message": f"{message} {note}".strip()})

    git = Git(root) if (use_git and key_files) else None
    for path in key_files:
        rel = path.relative_to(root).as_posix()
        status = git.status(rel) if git else "unknown"
        if status == "tracked":
            add("KEY-FILE-TRACKED", rel, 1)
        elif status == "untracked":
            add("KEY-FILE-UNIGNORED", rel, 1)
        elif status == "unknown":
            add("KEY-FILE-UNIGNORED", rel, 1, note="(git status not available)")

    tests_by_package: dict[Path, bool] = {p.parent: False for p in packages}
    for path in packages:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if MOVING_BRANCH_RE.search(line.split("#", 1)[0]):
                add("DEP-MOVING-BRANCH", rel, i, lines)

    for path in move_files:
        rel = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        test_file = "tests" in path.relative_to(root).parts[:-1]
        for rule, line in scan_move(text, test_file):
            add(rule, rel, line, lines)
        if TEST_ATTR_RE.search(strip_comments_and_strings(text)):
            for pkg in tests_by_package:
                if pkg == path.parent or pkg in path.parents:
                    tests_by_package[pkg] = True

    for pkg, has_tests in sorted(tests_by_package.items()):
        if not has_tests:
            add("NO-TESTS", (pkg / "Move.toml").relative_to(root).as_posix(), 1)

    unique = {(d["rule"], d["file"], d["line"]): d for d in leads}
    leads = sorted(unique.values(), key=lambda d: (d["file"], d["line"], LEVEL_RANK[d["level"]], d["rule"]))
    counts = {level: sum(1 for d in leads if d["level"] == level) for level in LEVELS}
    return {
        "tool": "move_check.py", "version": VERSION, "packages": len(packages), "move_files": len(move_files),
        "key_files": len(key_files), "counts": counts, "suppressed": ignored, "leads": leads,
        "note": "Leads, not findings, and not a security audit. Confirm each lead by reading the code and writing a test.",
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Offline, read-only lead finder for Aptos Move packages and dApp repositories (key files, refs, randomness, pinning).",
    )
    p.add_argument("--root", default=".", help="repository or package folder to scan (default: current folder)")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p.add_argument("--fail-on", choices=("high", "medium", "low", "never"), default="medium",
                   help="exit 1 when a lead at or above this level exists (default: medium)")
    p.add_argument("--no-git", action="store_true", help="do not call git; key files are reported with unknown status")
    p.add_argument("--list-rules", action="store_true", help="list rule IDs, levels and meanings, then exit")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if args.list_rules:
        for rule, (level, message) in RULES.items():
            print(f"{rule:<27} {level:<7} {message}")
        return 0
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: --root {args.root} is not a folder", file=sys.stderr)
        return 2
    result = scan(root.resolve(), use_git=not args.no_git)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        counts = result["counts"]
        summary = ", ".join(f"{lvl} {counts[lvl]}" for lvl in LEVELS if counts[lvl])
        print(f"move_check.py {VERSION}: {len(result['leads'])} lead(s); {result['packages']} package(s), "
              f"{result['move_files']} Move file(s), {result['key_files']} key file(s)"
              + (f" ({summary})" if summary else "")
              + (f", {result['suppressed']} acknowledged" if result["suppressed"] else ""))
        for d in result["leads"]:
            print(f"{d['level'].upper():<7} {d['rule']:<26} {d['file']}:{d['line']}  {d['message']}")
        print(result["note"])
    if args.fail_on != "never":
        limit = LEVEL_RANK[args.fail_on]
        if any(LEVEL_RANK[d["level"]] <= limit for d in result["leads"]):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
