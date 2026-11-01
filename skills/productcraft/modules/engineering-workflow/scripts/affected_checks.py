#!/usr/bin/env python3
"""ProductCraft Engineering Workflow: list the regression checks a change requires.

Reads a small regression ledger (JSON) that maps each module of a repository
to its paths, its downstream consumers and the command that proves it still
works. Given the changed files, it prints the modules changed directly, every
downstream module reached through the ledger, and the checks to run in
dependency order. It flags modules without a check, changed files no module
claims, and downstream edges the ledger marks as unverified.

It never runs the checks, never edits files and never uses the network. With
--git it runs read-only git commands (diff and ls-files) to list changes. The
output is a plan to review and run; exit codes of the real commands are the
regression evidence.

Ledger format:

    {
      "always": ["ruff check ."],
      "modules": {
        "ingest": {"paths": ["pipelines/ingest/"], "check": "pytest tests/ingest -q",
                   "downstream": ["clean"]},
        "clean":  {"paths": ["pipelines/clean/*.py"], "check": "python scripts/reconcile.py clean",
                   "downstream": ["report"], "unverified_downstream": ["export"]},
        "report": {"paths": ["pipelines/report/"], "check": null},
        "export": {"paths": ["pipelines/export/"], "check": "pytest tests/export -q"}
      }
    }

A path ending in "/" matches everything below it; other paths are glob
patterns in which "*" also matches "/".

Exit status: 0 on success, 1 with --strict while a WARN finding remains,
2 for a usage error, an invalid ledger or a failing git command.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

VERSION = "1.0.0"


class LedgerError(Exception):
    """The ledger or the change list cannot be used."""


def load_ledger(path: Path) -> Tuple[Dict[str, dict], List[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LedgerError(f"{path}: cannot read ({exc.strerror or exc})") from None
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}") from None
    if not isinstance(data, dict) or not isinstance(data.get("modules"), dict) or not data["modules"]:
        raise LedgerError(f"{path}: expected an object with a non-empty 'modules' object")
    always = data.get("always", [])
    if not isinstance(always, list) or not all(isinstance(c, str) and c.strip() for c in always):
        raise LedgerError(f"{path}: 'always' must be a list of commands")
    modules: Dict[str, dict] = {}
    names = set(data["modules"])
    for name, spec in data["modules"].items():
        if not isinstance(spec, dict):
            raise LedgerError(f"{path}: module '{name}' must be an object")
        paths = spec.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p.strip() for p in paths):
            raise LedgerError(f"{path}: module '{name}' needs a non-empty 'paths' list")
        check = spec.get("check")
        if check is not None and (not isinstance(check, str) or not check.strip()):
            raise LedgerError(f"{path}: module '{name}': 'check' must be a command or null")
        edges = {}
        for field in ("downstream", "unverified_downstream"):
            value = spec.get(field, [])
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise LedgerError(f"{path}: module '{name}': '{field}' must be a list of module names")
            unknown = sorted(set(value) - names)
            if unknown:
                raise LedgerError(f"{path}: module '{name}': unknown module(s) in '{field}': {', '.join(unknown)}")
            edges[field] = sorted(set(value))
        modules[name] = {
            "paths": [p.strip().replace("\\", "/") for p in paths],
            "check": check.strip() if isinstance(check, str) else None,
            "downstream": edges["downstream"],
            "unverified": edges["unverified_downstream"],
        }
    return modules, list(always)


def normalize(path: str) -> str:
    path = path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def matches(path: str, pattern: str) -> bool:
    pattern = normalize(pattern)
    if pattern.endswith("/"):
        return path.startswith(pattern) or path == pattern.rstrip("/")
    return fnmatch.fnmatchcase(path, pattern)


def git_changes(base: str, root: Path) -> List[str]:
    if base.startswith("-"):
        raise LedgerError(f"base revision must not start with '-': {base}")  # would be read as a git option
    commands = [
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        ["git", "diff", "--name-only"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    found: Set[str] = set()
    for command in commands:
        try:
            result = subprocess.run(command, cwd=str(root), capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LedgerError(f"cannot run {' '.join(command)}: {exc}") from None
        if result.returncode != 0:
            message = (result.stderr or "").strip().splitlines()
            raise LedgerError(f"{' '.join(command)} failed: {message[0] if message else result.returncode}")
        found.update(line for line in result.stdout.splitlines() if line.strip())
    return sorted(found)


def read_list(source: str) -> List[str]:
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError(f"{source}: cannot read ({exc.strerror or exc})") from None
    return [line for line in text.splitlines() if line.strip()]


def plan(modules: Dict[str, dict], always: List[str], changed: Sequence[str],
         exempt: Dict[str, str]) -> dict:
    files = sorted({normalize(f) for f in changed if normalize(f)})
    direct: Dict[str, List[str]] = {}
    unmapped: List[str] = []
    for path in files:
        owners = [name for name, spec in modules.items() if any(matches(path, p) for p in spec["paths"])]
        if not owners:
            unmapped.append(path)
        for name in owners:
            direct.setdefault(name, []).append(path)

    reached: Dict[str, str] = {name: "changed" for name in direct}
    unverified: List[Tuple[str, str]] = []
    queue = sorted(direct)
    while queue:
        name = queue.pop(0)
        if name in exempt:
            continue
        for target in modules[name]["unverified"]:
            unverified.append((name, target))
        for target in modules[name]["downstream"]:
            if target not in reached:
                reached[target] = f"downstream of {name}"
                queue.append(target)
    unverified = sorted(set(unverified))

    order, cyclic = topological(modules, set(reached))
    checks, gaps = [], []
    for name in order:
        command = modules[name]["check"]
        if command:
            checks.append({"module": name, "command": command, "why": reached[name]})
        else:
            gaps.append(name)

    findings = []
    for name in gaps:
        findings.append({"level": "WARN", "check": "no-check", "subject": name,
                         "detail": "affected module has no acceptance command; this is a gap, not a pass"})
    for source, target in unverified:
        findings.append({"level": "WARN", "check": "unverified-edge", "subject": f"{source} -> {target}",
                         "detail": "edge not established mechanically; include the module or confirm the scope"})
    for path in unmapped:
        findings.append({"level": "INFO", "check": "unmapped", "subject": path,
                         "detail": "no module claims this file"})
    for name in sorted(exempt):
        if name in reached:
            findings.append({"level": "INFO", "check": "exempt", "subject": name,
                             "detail": f"downstream not propagated: {exempt[name]}"})
    if cyclic:
        findings.append({"level": "INFO", "check": "cycle", "subject": ", ".join(cyclic),
                         "detail": "modules depend on each other; run all of them"})
    return {
        "changed_files": len(files),
        "direct": {name: sorted(paths) for name, paths in sorted(direct.items())},
        "affected": [{"module": name, "why": reached[name]} for name in order],
        "always": always,
        "checks": checks,
        "findings": findings,
    }


def topological(modules: Dict[str, dict], selected: Set[str]) -> Tuple[List[str], List[str]]:
    incoming = {name: 0 for name in selected}
    for name in selected:
        for target in modules[name]["downstream"]:
            if target in selected:
                incoming[target] += 1
    ready = sorted(name for name, count in incoming.items() if count == 0)
    order: List[str] = []
    while ready:
        name = ready.pop(0)
        order.append(name)
        for target in modules[name]["downstream"]:
            if target in incoming:
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
                    ready.sort()
    cyclic = sorted(selected - set(order))
    return order + cyclic, cyclic


def render_text(result: dict) -> str:
    lines = [f"affected_checks {VERSION}: {result['changed_files']} changed file(s)"]
    if not result["direct"]:
        lines.append("No ledger module is changed directly.")
    for name, paths in result["direct"].items():
        lines.append(f"changed  {name} ({len(paths)} file(s))")
    for item in result["affected"]:
        if item["why"] != "changed":
            lines.append(f"affected {item['module']} ({item['why']})")
    lines.append("Checks to run, in order:")
    step = 0
    for command in result["always"]:
        step += 1
        lines.append(f"  {step}. {command}    # always")
    for item in result["checks"]:
        step += 1
        lines.append(f"  {step}. {item['command']}    # {item['module']}")
    if step == 0:
        lines.append("  (none)")
    for finding in result["findings"]:
        lines.append(f"{finding['level']:<5} {finding['check']:<16} {finding['subject']}: {finding['detail']}")
    lines.append("Run the checks and report each exit code; this list is a plan, not evidence.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affected_checks.py",
        description="List the regression checks a change requires from a module ledger: changed modules, "
                    "downstream consumers and their commands in dependency order. Read-only; never runs them.",
        epilog="Example: affected_checks.py --ledger regression.json --git origin/main",
    )
    parser.add_argument("--ledger", required=True, help="regression ledger JSON file")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--git", metavar="BASE", help="changes since the merge base with BASE, plus staged, "
                        "unstaged and untracked files (read-only git commands)")
    source.add_argument("--changed", nargs="+", metavar="PATH", help="changed file paths")
    source.add_argument("--changed-from", metavar="FILE", help="file with one changed path per line ('-' for stdin)")
    parser.add_argument("--root", default=".", help="repository root for --git (default: current directory)")
    parser.add_argument("--exempt", action="append", default=[], metavar="MODULE=REASON",
                        help="do not propagate to downstream of MODULE; the reason is printed (repeatable)")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.add_argument("--strict", action="store_true", help="exit 1 while a WARN finding remains")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        modules, always = load_ledger(Path(args.ledger))
        exempt: Dict[str, str] = {}
        for item in args.exempt:
            name, sep, reason = item.partition("=")
            if not sep or not reason.strip() or name not in modules:
                raise LedgerError(f"--exempt needs MODULE=REASON with a known module, got '{item}'")
            exempt[name] = reason.strip()
        if args.git:
            changed = git_changes(args.git, Path(args.root))
        elif args.changed_from:
            changed = read_list(args.changed_from)
        else:
            changed = list(args.changed)
    except LedgerError as exc:
        print(f"affected_checks: error: {exc}", file=sys.stderr)
        return 2
    result = plan(modules, always, changed, exempt)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_text(result))
    warn = any(f["level"] == "WARN" for f in result["findings"])
    return 1 if args.strict and warn else 0


if __name__ == "__main__":
    sys.exit(main())
