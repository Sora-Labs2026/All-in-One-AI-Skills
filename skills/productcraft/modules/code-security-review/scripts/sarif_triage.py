#!/usr/bin/env python3
"""ProductCraft SARIF triage helper. Offline, read-only, deterministic.

Reads SARIF 2.1.0 files written by static analysis tools (Semgrep, CodeQL and
others) and turns them into something a reviewer can work through.

Subcommands:
  summary  Count results per tool, rule, level and file. Severity is resolved
           the way SARIF defines it: a result without its own level inherits
           its rule's default level (CodeQL leaves level off every result).
  diff     Compare a new SARIF file with a baseline and list results that are
           new, using fingerprints when the tool wrote them. Use it to review
           only what a branch introduced.
  leads    Write every distinct result as a POSSIBLE lead in the findings-JSON
           format of this module, so `code_audit.py findings` accepts the file
           and the audit result stays NEEDS_REVIEW until each lead is triaged.

Snippets are never copied. Messages are shortened and anything shaped like a
token or key is replaced with [REDACTED]. A clean summary only says that the
listed tools reported nothing for the files they analyzed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

VERSION = "1.0.0"
LEVELS = ("error", "warning", "note", "none")
LEVEL_RANK = {"error": 0, "warning": 1, "note": 2, "none": 3}
MAX_MESSAGE = 200
MAX_LEADS = 2000

REDACTIONS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|$)"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),
    re.compile(r"\b(?=[A-Za-z0-9_\-+=]*[0-9])(?=[A-Za-z0-9_\-+=]*[A-Za-z])[A-Za-z0-9_\-+=]{24,}"),
]


def redact(text: str, limit: int = MAX_MESSAGE) -> str:
    text = " ".join(str(text or "").split())
    for regex in REDACTIONS:
        text = regex.sub("[REDACTED]", text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def write_json(result: dict, out: str) -> None:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")


def load_sarif(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read SARIF {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        raise ValueError(f"{path} is not SARIF: no 'runs' list")
    return data


def _rules_of(component: dict) -> list[dict]:
    rules = component.get("rules") if isinstance(component, dict) else None
    return rules if isinstance(rules, list) else []


def resolve_rule(result: dict, run: dict) -> dict:
    """Find the rule object for a result: ruleIndex, rule.index with toolComponent, or matching ids."""
    tool = run.get("tool") or {}
    driver = tool.get("driver") or {}
    extensions = tool.get("extensions") or []
    ref = result.get("rule") if isinstance(result.get("rule"), dict) else {}
    component = driver
    tc = ref.get("toolComponent") if isinstance(ref.get("toolComponent"), dict) else None
    if tc is not None and isinstance(tc.get("index"), int) and 0 <= tc["index"] < len(extensions):
        component = extensions[tc["index"]]
    index = ref.get("index", result.get("ruleIndex"))
    rules = _rules_of(component)
    if isinstance(index, int) and 0 <= index < len(rules):
        return rules[index] or {}
    rule_id = result.get("ruleId") or ref.get("id")
    for comp in [driver] + list(extensions):
        for rule in _rules_of(comp):
            if isinstance(rule, dict) and rule.get("id") == rule_id:
                return rule
    return {}


def resolve_level(result: dict, rule: dict) -> str:
    """SARIF 2.1.0 section 3.27.10: kind other than fail means none; else result level; else rule default."""
    kind = result.get("kind", "fail")
    if kind != "fail":
        return "none"
    level = result.get("level")
    if level in LEVEL_RANK:
        return level
    default = ((rule.get("defaultConfiguration") or {}).get("level")) if rule else None
    return default if default in LEVEL_RANK else "warning"


def security_label(score) -> str | None:
    """Map a rule's security-severity score (0-10) to a label the way code-scanning dashboards do."""
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if value >= 9.0:
        return "critical"
    if value >= 7.0:
        return "high"
    if value >= 4.0:
        return "medium"
    if value > 0:
        return "low"
    return None


def normalize_uri(uri: str, root: Path | None) -> tuple[str, bool]:
    """Return (repository-relative posix path, ok). ok is False when the path could not be made relative."""
    if not uri:
        return "", False
    parts = urlsplit(uri)
    path = unquote(parts.path if parts.scheme in ("file", "") else uri)
    if re.match(r"^/[A-Za-z]:/", path):
        path = path[1:]
    if root is not None and (path.startswith("/") or re.match(r"^[A-Za-z]:/", path)):
        try:
            path = Path(path).resolve().relative_to(root.resolve()).as_posix()
        except (ValueError, OSError):
            pass
    pure = PurePosixPath(path.replace("\\", "/"))
    ok = not pure.is_absolute() and ".." not in pure.parts and not re.match(r"^[A-Za-z]:", str(pure))
    clean = str(pure).lstrip("/")
    if clean.startswith("./"):
        clean = clean[2:]
    return clean, ok


def message_text(result: dict, rule: dict) -> str:
    msg = result.get("message") or {}
    text = msg.get("text")
    if not text and msg.get("id"):
        strings = (rule.get("messageStrings") or {}) if rule else {}
        text = (strings.get(msg["id"]) or {}).get("text", "")
        for i, arg in enumerate(msg.get("arguments") or []):
            text = text.replace("{" + str(i) + "}", str(arg))
    text = re.sub(r"\[([^\]]*)\]\(\d+\)", r"\1", text or "")  # drop SARIF embedded-link markup
    return text


def cwe_of(rule: dict) -> str | None:
    tags = ((rule.get("properties") or {}).get("tags") or []) if rule else []
    for tag in tags:
        m = re.search(r"cwe[-/:_ ]?0*(\d+)", str(tag), re.I)
        if m:
            return f"CWE-{m.group(1)}"
    return None


def collect(path: str, root: Path | None) -> tuple[list[dict], list[dict]]:
    """Return (results, run summaries) from one SARIF file."""
    data = load_sarif(path)
    results, runs = [], []
    for run_index, run in enumerate(data["runs"]):
        if not isinstance(run, dict):
            continue
        driver = ((run.get("tool") or {}).get("driver") or {})
        tool = str(driver.get("name") or "unknown-tool")
        artifacts = run.get("artifacts") if isinstance(run.get("artifacts"), list) else []
        invocations = run.get("invocations") if isinstance(run.get("invocations"), list) else []
        failed = [inv for inv in invocations if isinstance(inv, dict) and inv.get("executionSuccessful") is False]
        runs.append({"file": path, "run": run_index, "tool": tool, "tool_version": driver.get("semanticVersion") or
                     driver.get("version"), "results": len(run.get("results") or []),
                     "artifacts_listed": len(artifacts), "invocation_failed": bool(failed)})
        for result in run.get("results") or []:
            if not isinstance(result, dict):
                continue
            rule = resolve_rule(result, run)
            rule_id = str(result.get("ruleId") or (result.get("rule") or {}).get("id") or rule.get("id") or "unknown-rule")
            loc = ((result.get("locations") or [{}])[0] or {}).get("physicalLocation") or {}
            uri = ((loc.get("artifactLocation") or {}).get("uri")) or ""
            index = (loc.get("artifactLocation") or {}).get("index")
            if not uri and isinstance(index, int) and 0 <= index < len(artifacts):
                uri = ((artifacts[index] or {}).get("location") or {}).get("uri", "")
            file, ok = normalize_uri(uri, root)
            line = (loc.get("region") or {}).get("startLine")
            props = rule.get("properties") or {} if rule else {}
            fingerprints = {**(result.get("partialFingerprints") or {}), **(result.get("fingerprints") or {})}
            suppressions = result.get("suppressions") or []
            suppressed = any(isinstance(s, dict) and s.get("status", "accepted") == "accepted" for s in suppressions)
            text = message_text(result, rule)
            short = ((rule.get("shortDescription") or {}).get("text") or rule.get("name") or "") if rule else ""
            results.append({
                "tool": tool, "rule": rule_id, "level": resolve_level(result, rule),
                "security_severity": props.get("security-severity"),
                "precision": props.get("precision"),
                "cwe": cwe_of(rule),
                "file": file, "path_ok": ok, "line": line if isinstance(line, int) and line > 0 else None,
                "message": redact(text), "title": redact(short or text, 120),
                "fingerprint": next((f"{k}:{v}" for k, v in sorted(fingerprints.items())), None),
                "message_key": redact(text, 400),
                "suppressed": suppressed, "baseline_state": result.get("baselineState"),
            })
    return results, runs


def _match_key(r: dict, by_fingerprint: bool) -> tuple:
    if by_fingerprint and r["fingerprint"]:
        return (r["tool"], r["rule"], r["fingerprint"])
    return (r["tool"], r["rule"], r["file"], r["message_key"])


def split_new(new: list[dict], old: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Multiset match of new results against a baseline. Returns (new, unchanged, absent count)."""
    use_fp = all(r["fingerprint"] for r in new + old) and bool(new or old)
    remaining = Counter(_match_key(r, use_fp) for r in old)
    fresh, same = [], []
    for r in new:
        key = _match_key(r, use_fp)
        if remaining[key] > 0:
            remaining[key] -= 1
            same.append(r)
        else:
            fresh.append(r)
    return fresh, same, sum(remaining.values())


def summarize(results: list[dict], runs: list[dict], top: int) -> dict:
    counted = [r for r in results if not r["suppressed"]]
    active = [r for r in counted if r["level"] != "none"]
    by_rule: dict[tuple, dict] = {}
    for r in active:
        key = (r["tool"], r["rule"])
        entry = by_rule.setdefault(key, {"tool": r["tool"], "rule": r["rule"], "count": 0, "levels": Counter(),
                                         "security_severity": r["security_severity"],
                                         "security_label": security_label(r["security_severity"]),
                                         "precision": r["precision"], "cwe": r["cwe"], "files": set()})
        entry["count"] += 1
        entry["levels"][r["level"]] += 1
        entry["files"].add(r["file"])
    rules = sorted(by_rule.values(), key=lambda e: (min(LEVEL_RANK[l] for l in e["levels"]), -e["count"], e["tool"], e["rule"]))
    files = Counter(r["file"] for r in active)
    return {
        "runs": runs,
        "results": len(results),
        "suppressed": len(results) - len(counted),
        "by_level": {lvl: sum(1 for r in counted if r["level"] == lvl) for lvl in LEVELS},
        "by_tool": dict(sorted(Counter(r["tool"] for r in active).items())),
        "rules": [{**{k: v for k, v in e.items() if k not in ("levels", "files")},
                   "levels": dict(sorted(e["levels"].items(), key=lambda kv: LEVEL_RANK[kv[0]])),
                   "files": len(e["files"])} for e in rules[:top]],
        "rule_count": len(rules),
        "top_files": [{"file": f, "results": n} for f, n in sorted(files.items(), key=lambda kv: (-kv[1], kv[0]))[:top]],
        "paths_not_relative": sum(1 for r in active if not r["path_ok"]),
        "runs_with_failed_invocation": sum(1 for r in runs if r["invocation_failed"]),
    }


def _score(r: dict):
    try:
        return float(r["security_severity"])
    except (TypeError, ValueError):
        return None


def build_leads(results: list[dict], prefix: str, min_level: str, audit: dict,
                min_security: float | None = None) -> dict:
    def kept(r):
        if r["suppressed"] or not r["path_ok"] or LEVEL_RANK[r["level"]] > LEVEL_RANK[min_level]:
            return False
        score = _score(r)
        return min_security is None or score is None or score >= min_security
    active = [r for r in results if kept(r)]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in active:
        groups[(r["tool"], r["rule"], r["file"], r["line"])].append(r)
    by_location: dict[tuple, set[str]] = defaultdict(set)
    for (tool, rule, file, line) in groups:
        by_location[(file, line)].add(f"{tool}:{rule}")
    ordered = sorted(groups.items(), key=lambda kv: (LEVEL_RANK[kv[1][0]["level"]], kv[0][2], kv[0][3] or 0, kv[0][0], kv[0][1]))
    findings = []
    width = max(3, len(str(min(len(ordered), MAX_LEADS))))
    for n, ((tool, rule, file, line), items) in enumerate(ordered[:MAX_LEADS], start=1):
        first = items[0]
        where = f"{file}:{line}" if line else file
        lead = {
            "id": f"{prefix}-{n:0{width}d}",
            "title": first["title"] or rule,
            "class": first["cwe"] or rule,
            "file": file,
            "confidence": "POSSIBLE",
            "status": "OPEN",
            "evidence_type": "NOT_TESTED",
            "evidence_summary": redact(f"{tool} rule {rule} reported a result at level {first['level']}: {first['message']}", 300),
            "next_check": (f"Read {where}, trace the reported value back to an entry point and check every guard on "
                           "the way; then set CONFIRMED or LIKELY with evidence, or FALSE_POSITIVE with "
                           "rejection_reason."),
            "source_tool": tool,
            "rule_id": rule,
            "scanner_level": first["level"],
            "occurrences": len(items),
        }
        if line:
            lead["line"] = line
        if first["cwe"]:
            lead["cwe"] = first["cwe"]
        if first["security_severity"] is not None:
            lead["rule_security_severity"] = str(first["security_severity"])
        others = sorted(by_location[(file, line)] - {f"{tool}:{rule}"})
        if others:
            lead["also_reported_by"] = others
        if first["fingerprint"]:
            lead["fingerprint"] = first["fingerprint"][:120]
        findings.append(lead)
    return {
        "audit": audit,
        "coverage": [],
        "findings": findings,
        "import_notes": {
            "tool": "productcraft-sarif-triage-leads", "version": VERSION,
            "leads_written": len(findings), "results_considered": len(active),
            "skipped_suppressed": sum(1 for r in results if r["suppressed"]),
            "skipped_below_level": sum(1 for r in results if not r["suppressed"] and
                                       LEVEL_RANK[r["level"]] > LEVEL_RANK[min_level]),
            "skipped_unresolvable_paths": sum(1 for r in results if not r["path_ok"] and not r["suppressed"]),
            "skipped_below_security_severity": sum(
                1 for r in results if min_security is not None and not r["suppressed"] and r["path_ok"] and
                LEVEL_RANK[r["level"]] <= LEVEL_RANK[min_level] and _score(r) is not None and _score(r) < min_security),
            "min_security_severity": min_security,
            "truncated": len(ordered) > MAX_LEADS,
            "rule": "Scanner results are leads. Confirm each one by reading the code before it becomes a finding.",
        },
    }


def _collect_many(paths: list[str], root: Path | None):
    results, runs = [], []
    for p in paths:
        r, s = collect(p, root)
        results.extend(r)
        runs.extend(s)
    return results, runs


def _root(value: str | None) -> Path | None:
    if not value:
        return None
    root = Path(value).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    return root


def cmd_summary(opts) -> int:
    results, runs = _collect_many(opts.sarif, _root(opts.root))
    s = summarize(results, runs, opts.top)
    print(f"sarif_triage summary: {len(runs)} runs, {s['results']} results ({s['suppressed']} suppressed), "
          f"{s['rule_count']} rules, by level {s['by_level']}.")
    for r in runs:
        flag = " INVOCATION FAILED" if r["invocation_failed"] else ""
        print(f"  run {r['tool']} {r['tool_version'] or ''}: {r['results']} results, "
              f"{r['artifacts_listed']} artifacts listed{flag}")
    for e in s["rules"][:20]:
        sev = f" security-severity {e['security_severity']} ({e['security_label']})" if e["security_label"] else ""
        print(f"  {e['count']:4} x {e['tool']}:{e['rule']} levels={e['levels']} files={e['files']}{sev}")
    if s["paths_not_relative"]:
        print(f"  {s['paths_not_relative']} result(s) have absolute paths or paths outside --root; pass --root.")
    if not s["results"]:
        print("No results. Check that the run analyzed the expected files (artifacts listed, extraction logs) "
              "before reading this as clean.")
    print("Levels are the tools' own labels, not severities. Every result is a lead until triaged.")
    if opts.json_out:
        write_json({"tool": "productcraft-sarif-triage-summary", "version": VERSION, **s}, opts.json_out)
        print(f"JSON written: {opts.json_out}")
    return 0


def cmd_diff(opts) -> int:
    root = _root(opts.root)
    new, runs = _collect_many(opts.sarif, root)
    old, _ = _collect_many(opts.baseline, root)
    new_active = [r for r in new if not r["suppressed"] and r["level"] != "none"]
    old_active = [r for r in old if not r["suppressed"] and r["level"] != "none"]
    fresh, same, absent = split_new(new_active, old_active)
    print(f"sarif_triage diff: {len(fresh)} new, {len(same)} unchanged, {absent} no longer reported.")
    for r in sorted(fresh, key=lambda r: (LEVEL_RANK[r["level"]], r["file"], r["line"] or 0))[:40]:
        loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
        print(f"  [{r['level']}] {r['tool']}:{r['rule']} {loc}")
    print("Matching uses fingerprints when every result has one, otherwise rule, file and message. A result that "
          "moved files shows as new.")
    if opts.json_out:
        write_json({"tool": "productcraft-sarif-triage-diff", "version": VERSION, "new": [
            {k: v for k, v in r.items() if k != "message_key"} for r in fresh],
            "unchanged": len(same), "absent": absent, "runs": runs}, opts.json_out)
        print(f"JSON written: {opts.json_out}")
    if opts.fail_on == "never":
        return 0
    return 1 if any(LEVEL_RANK[r["level"]] <= LEVEL_RANK[opts.fail_on] for r in fresh) else 0


def cmd_leads(opts) -> int:
    root = _root(opts.root)
    results, runs = _collect_many(opts.sarif, root)
    if opts.baseline:
        old, _ = _collect_many(opts.baseline, root)
        results, _, _ = split_new([r for r in results if not r["suppressed"]], [r for r in old if not r["suppressed"]])
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", opts.id_prefix):
        raise ValueError("--id-prefix must be 2-10 upper-case letters or digits, starting with a letter")
    audit = {"repository": opts.repository or (root.name if root else "unknown"), "revision": opts.revision or "unknown",
             "mode": "scanner import",
             "scope": sorted({r["file"].split("/", 1)[0] for r in results if r["path_ok"] and r["file"]})[:20] or ["."],
             "sources": sorted({f"{r['tool']} {r['tool_version'] or ''}".strip() for r in runs})}
    doc = build_leads(results, opts.id_prefix, opts.min_level, audit, opts.min_security_severity)
    write_json(doc, opts.out)
    notes = doc["import_notes"]
    print(f"sarif_triage leads: {notes['leads_written']} leads written to {opts.out} from {notes['results_considered']} "
          f"results ({notes['skipped_suppressed']} suppressed, {notes['skipped_below_level']} below {opts.min_level}, "
          f"{notes['skipped_unresolvable_paths']} with unresolvable paths).")
    print("Validate with code_audit.py findings --file " + opts.out + " ; it reports NEEDS_REVIEW until every lead is "
          "triaged.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sarif_triage.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("summary", help="count results per tool, rule, level and file")
    p.add_argument("--sarif", action="append", required=True, help="SARIF file (repeatable)")
    p.add_argument("--root", help="repository root, used to make absolute paths relative")
    p.add_argument("--top", type=int, default=50, help="rules and files kept in the JSON (default: 50)")
    p.add_argument("--json-out", help="write the summary as JSON (mode 0600)")
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("diff", help="list results that are not in a baseline SARIF")
    p.add_argument("--sarif", action="append", required=True, help="new SARIF file (repeatable)")
    p.add_argument("--baseline", action="append", required=True, help="baseline SARIF file (repeatable)")
    p.add_argument("--root", help="repository root, used to make absolute paths relative")
    p.add_argument("--json-out", help="write the new results as JSON (mode 0600)")
    p.add_argument("--fail-on", choices=["never", "error", "warning", "note"], default="never",
                   help="exit 1 when a new result at or above this level exists (default: never)")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("leads", help="write results as POSSIBLE leads in the findings-JSON format")
    p.add_argument("--sarif", action="append", required=True, help="SARIF file (repeatable)")
    p.add_argument("--baseline", action="append", help="only import results that are not in this baseline")
    p.add_argument("--root", help="repository root, used to make absolute paths relative")
    p.add_argument("--out", required=True, help="output JSON, e.g. security/sast-leads.json (mode 0600)")
    p.add_argument("--id-prefix", default="SAST", help="lead id prefix (default: SAST)")
    p.add_argument("--min-level", choices=["error", "warning", "note", "none"], default="note",
                   help="lowest resolved level to import (default: note)")
    p.add_argument("--min-security-severity", type=float, metavar="SCORE",
                   help="skip results whose rule has a security-severity below SCORE (rules without one are kept)")
    p.add_argument("--repository", help="repository name for the audit block")
    p.add_argument("--revision", help="commit the scan ran on, e.g. from git rev-parse --short HEAD")
    p.set_defaults(func=cmd_leads)
    return ap


def main(argv: list[str] | None = None) -> int:
    opts = build_parser().parse_args(argv)
    try:
        return opts.func(opts)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
