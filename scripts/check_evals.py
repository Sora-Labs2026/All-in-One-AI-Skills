#!/usr/bin/env python3
"""Statically check the plugin eval suite in evals/ before spending money on a run.

    python3 scripts/check_evals.py            # check evals/ in this repository
    python3 scripts/check_evals.py --dir PATH # check another eval directory

Checks each case's prompt.md frontmatter and every graders/*.md file against the
documented `claude plugin eval` fields. Patterns must compile, a Skill or Read
grader needs that tool in allowed_tools, and each case keeps at least one
grader that is scored in both arms. Exit codes: 0 clean, 1 problems found,
2 usage error.
"""
import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
PROMPT_KEYS = {"schema_version", "name", "description", "expected_outcome", "tags", "plugins", "runs", "model",
               "max_turns", "timeout_seconds", "allowed_tools", "append_system_prompt", "env"}
COMMON = {"type", "weight", "arm"}
GRADERS = {
    "regex": ({"pattern"}, {"flags", "match", "target"}),
    "tool_used": ({"tool"}, {"input_match", "min", "max"}),
    "tool_order": ({"before", "after"}, set()),
    "file_exists": ({"path"}, {"exists"}),
    "llm": (set(), {"criteria", "focus"}),
    "baseline": ({"baseline_file"}, {"criteria"}),
}
READ_ONLY_TOOLS = {"Read", "Glob", "Grep", "NotebookRead", "Skill", "AskUserQuestion", "Agent", "TodoWrite"}


def parse_frontmatter(text):
    """Return (fields, body) for a file that starts with a --- block; fields hold strings or lists."""
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    fields = {}
    for n, line in enumerate(text[4:end].splitlines(), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            raise ValueError(f"line {n}: not a 'key: value' line")
        key, raw = m.group(1), m.group(2).strip()
        if key in fields:
            raise ValueError(f"line {n}: duplicate key {key}")
        if raw.startswith("[") and raw.endswith("]"):
            fields[key] = [x.strip().strip("'\"") for x in raw[1:-1].split(",") if x.strip()]
        elif len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
            fields[key] = raw[1:-1].replace("''", "'") if raw[0] == "'" else raw[1:-1]
        else:
            fields[key] = raw
    return fields, text[end + 4:].lstrip("\n")


def as_int(value, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def check_case(case):
    problems = []
    prompt = case / "prompt.md"
    if not prompt.is_file():
        if (case / "case.yaml").is_file():
            return [], 0  # case.yaml cases are left to the eval command itself
        return [f"{case.name}: no prompt.md"], 0
    try:
        meta, body = parse_frontmatter(prompt.read_text())
    except ValueError as e:
        return [f"{case.name}/prompt.md: {e}"], 0
    for key in sorted(set(meta) - PROMPT_KEYS):
        problems.append(f"{case.name}/prompt.md: unknown key {key}")
    if not body.strip():
        problems.append(f"{case.name}/prompt.md: empty prompt body")
    if not meta.get("description"):
        problems.append(f"{case.name}/prompt.md: add a description")
    if not meta.get("tags"):
        problems.append(f"{case.name}/prompt.md: add tags so runs can be filtered")
    for key, lo, hi in (("runs", 1, 50), ("max_turns", 1, 200), ("timeout_seconds", 1, 3600)):
        if key in meta and as_int(meta[key], lo, hi) is None:
            problems.append(f"{case.name}/prompt.md: {key} must be an integer from {lo} to {hi}")
    tools = set(meta.get("allowed_tools") or [])
    for tool in sorted(tools - READ_ONLY_TOOLS):
        if not tool.startswith("Task"):
            problems.append(f"{case.name}/prompt.md: {tool} is not a read-only tool; grant it with --allow-tools instead")

    graders = sorted((case / "graders").glob("*.md")) if (case / "graders").is_dir() else []
    if not graders:
        problems.append(f"{case.name}: no graders/*.md")
    scored = 0
    for g in graders:
        label = f"{case.name}/graders/{g.name}"
        try:
            cfg, gbody = parse_frontmatter(g.read_text())
        except ValueError as e:
            problems.append(f"{label}: {e}")
            continue
        kind = cfg.get("type")
        if kind not in GRADERS:
            problems.append(f"{label}: unknown type {kind!r}")
            continue
        required, optional = GRADERS[kind]
        for key in sorted(required - set(cfg)):
            problems.append(f"{label}: {kind} grader needs {key}")
        for key in sorted(set(cfg) - required - optional - COMMON):
            problems.append(f"{label}: unknown key {key}")
        if "weight" in cfg:
            try:
                if float(cfg["weight"]) <= 0:
                    raise ValueError
            except ValueError:
                problems.append(f"{label}: weight must be a positive number")
        if cfg.get("arm", "both") not in ("both", "with-only"):
            problems.append(f"{label}: arm must be both or with-only")
        for key in ("pattern", "input_match"):
            if key in cfg:
                try:
                    re.compile(cfg[key], re.I if "i" in cfg.get("flags", "") else 0)
                except re.error as e:
                    problems.append(f"{label}: {key} does not compile: {e}")
        if kind == "regex" and "flags" in cfg and not re.fullmatch(r"[imsu]*", cfg["flags"]):
            problems.append(f"{label}: flags may only use i, m, s and u")
        if kind == "llm" and not (gbody.strip() or cfg.get("criteria")):
            problems.append(f"{label}: llm grader needs PASS/FAIL criteria in its body")
        if kind == "tool_used":
            tool = cfg.get("tool", "")
            if tool in READ_ONLY_TOOLS and tool not in tools:
                problems.append(f"{label}: add {tool} to allowed_tools or this grader can never pass")
            for key in ("min", "max"):
                if key in cfg and as_int(cfg[key], 0, 10_000) is None:
                    problems.append(f"{label}: {key} must be a non-negative integer")
        indicator = cfg.get("arm") == "with-only" or (kind == "tool_used" and cfg.get("tool") == "Skill"
                                                       and cfg.get("arm") != "both")
        scored += 0 if indicator else 1
    if graders and not scored:
        problems.append(f"{case.name}: every grader is a with-only indicator; add a grader that scores the answer")
    return problems, len(graders)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", default=str(REPO / "evals"), help="eval directory (default: evals/ in this repository)")
    args = ap.parse_args(argv)
    root = pathlib.Path(args.dir)
    if not root.is_dir():
        print(f"no eval directory at {root}", file=sys.stderr)
        return 2
    cases = sorted(p for p in root.iterdir() if p.is_dir() and p.name not in ("results", "mocks"))
    problems, total = [], 0
    for case in cases:
        found, n = check_case(case)
        problems += found
        total += n
    if not cases:
        problems.append("no eval cases found")
    for p in problems:
        print(p)
    print(f"{len(cases)} cases, {total} graders: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
