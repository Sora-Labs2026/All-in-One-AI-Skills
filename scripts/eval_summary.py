#!/usr/bin/env python3
"""Summarize a `claude plugin eval --json` result: trigger rate, module reads, scores and uplift.

    python3 scripts/eval_summary.py results.json
    python3 scripts/eval_summary.py results.json --min-trigger 0.8   # exit 1 below 80 %

A positive case is one with a `tool_used: Skill` grader that expects at least
one call. Its trigger rate is the share of with-plugin runs where that grader
passed. A negative case expects zero Skill calls, so a run that calls the skill
anyway counts as a false trigger. "Module read" is the share of with-plugin runs
that passed a with-only `tool_used: Read` grader. Scores are the harness's own
weighted scores, and Δ is with minus without. The output is Markdown.
Exit codes: 0 ok, 1 below a --min-* bar, 2 unreadable input.
"""
import argparse
import json
import sys


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, pct=False):
    if x is None:
        return "–"
    return f"{x * 100:.0f} %" if pct else f"{x:.2f}"


def classify(case):
    """Return (skill_grader_names, expects_trigger, read_grader_names) from the case's grader configs."""
    skill, read, expects = [], [], None
    for g in case.get("graders", []):
        cfg = g.get("config", {})
        if g.get("type") != "tool_used":
            continue
        if cfg.get("tool") == "Skill":
            skill.append(g["name"])
            hi = cfg.get("max")
            expects = not (hi is not None and int(hi) == 0)
        elif cfg.get("tool") == "Read" and (g.get("arm") == "with-only" or cfg.get("arm") == "with-only"):
            read.append(g["name"])
    return skill, expects, read


def rate(runs, names):
    if not names or not runs:
        return None
    hits = [all(gr["passed"] for gr in r.get("graders", []) if gr["name"] in names) for r in runs]
    return sum(hits) / len(hits)


def summarize(data):
    rows, pos, neg, scores, deltas, reads = [], [], [], [], [], []
    for case in data.get("cases", []):
        arms = case.get("arms", {})
        with_runs, without_runs = arms.get("with", []), arms.get("without", [])
        skill, expects, read = classify(case)
        trig = rate(with_runs, skill)
        if expects is True and trig is not None:
            pos.append(trig)
        elif expects is False and trig is not None:
            neg.append(1 - trig)  # share of runs that wrongly loaded the skill
        rd = rate(with_runs, read)
        reads.append(rd)
        agg = case.get("aggregates", {})
        w = agg.get("score", mean(r.get("score") for r in with_runs))
        wo = agg.get("scoreWithout", mean(r.get("score") for r in without_runs) if without_runs else None)
        d = agg.get("delta", (w - wo) if (w is not None and wo is not None) else None)
        scores.append(w)
        deltas.append(d)
        kind = {True: "should load", False: "should not load", None: "–"}[expects]
        rows.append(f"| {case['name']} | {kind} | {fmt(trig if expects is not False else (1 - trig if trig is not None else None), True)} "
                    f"| {fmt(rd, True)} | {fmt(w)} | {fmt(wo)} | {fmt(d)} |")
    totals = {"trigger_rate": mean(pos), "false_trigger_rate": mean(neg), "module_read_rate": mean(reads),
              "mean_score": mean(scores), "mean_delta": mean(deltas), "cost_usd": data.get("costUsd")}
    lines = ["| Case | Expectation | Loaded (or wrongly loaded) | Module read | Score with | Score without | Δ |",
             "|---|---|---|---|---|---|---|", *rows, "",
             f"- Trigger rate on cases that should load the skill: {fmt(totals['trigger_rate'], True)}",
             f"- False triggers on cases that should not: {fmt(totals['false_trigger_rate'], True)}",
             f"- Module files read in with-plugin runs: {fmt(totals['module_read_rate'], True)}",
             f"- Mean score with the plugin: {fmt(totals['mean_score'])}; mean Δ against no plugin: {fmt(totals['mean_delta'])}",
             f"- Cost (list-price estimate): {'–' if totals['cost_usd'] is None else f'${totals['cost_usd']:.2f}'}"]
    return "\n".join(lines), totals


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("result", help="JSON written by `claude plugin eval --json <path>`")
    ap.add_argument("--min-trigger", type=float, help="fail when the trigger rate is below this share (0-1)")
    ap.add_argument("--max-false-trigger", type=float, help="fail when the false-trigger rate is above this share (0-1)")
    args = ap.parse_args(argv)
    try:
        with open(args.result, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"cannot read {args.result}: {e}", file=sys.stderr)
        return 2
    text, totals = summarize(data)
    print(text)
    bad = []
    if args.min_trigger is not None and (totals["trigger_rate"] or 0) < args.min_trigger:
        bad.append(f"trigger rate below {args.min_trigger:.0%}")
    if args.max_false_trigger is not None and (totals["false_trigger_rate"] or 0) > args.max_false_trigger:
        bad.append(f"false-trigger rate above {args.max_false_trigger:.0%}")
    for b in bad:
        print(f"FAIL: {b}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
