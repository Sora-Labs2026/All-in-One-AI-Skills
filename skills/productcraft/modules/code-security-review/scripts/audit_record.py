#!/usr/bin/env python3
"""ProductCraft audit record checker. Offline, read-only, deterministic.

Subcommands:
  coverage  Check a coverage record (security/coverage-record.json): cell
            identity, statuses, per-check evidence, source revisions, reopened
            cells and gap reviews. With --findings, cross-check the record
            against the findings JSON that code_audit.py validates. Prints the
            strongest coverage claim the record supports: full, scoped,
            partial, or none when the record has errors.
  rigor     Check the stricter finding fields (invariant, impact level,
            severity reason, typed preconditions, access class, trace,
            reproduction, root-cause key, owner check) on live CONFIRMED and
            LIKELY findings, and compare each severity with the ceiling that
            the module's rating rules give.

Exit codes: 0 no errors (and any requested claim is supported); 1 errors found
or the requested claim is not supported; 2 usage or input error (unreadable
file, invalid JSON, duplicate JSON keys, file too large).

The tool reads the files it is given and nothing else. It does not use the
network, does not write files and never prints secret-shaped values.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath

VERSION = "1.0.0"
MAX_BYTES = 5_000_000

SEVERITIES = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
RANK = {name: index for index, name in enumerate(SEVERITIES)}

WORKING = {"PLANNED", "IN_PROGRESS"}
EVIDENCE_STATUSES = {"PASS", "FAIL", "NEEDS_REVIEW"}
REASON_STATUSES = {"NOT_APPLICABLE", "NOT_VERIFIED", "OUT_OF_SCOPE"}
CELL_STATUSES = WORKING | EVIDENCE_STATUSES | REASON_STATUSES
ATTEMPT_STATUSES = {"PASS", "FAIL", "NEEDS_REVIEW", "NOT_VERIFIED"}
METHODS = {"read", "test", "tool"}
DEPTHS = {"full", "diff", "focused"}
GAP_RESULTS = {"clean", "gaps_found"}

# Precondition kinds and how they move severity (phase 6 of the audit):
# reach kinds lower it by the given levels (the largest one applies);
# each condition the attacker does not control lowers it by one, at most two.
REACH_KINDS = {"account": 0, "role": 1, "internal_network": 1, "local_access": 2, "physical_access": 2}
CONDITION_KINDS = {"user_action", "configuration", "timing", "third_party"}
NEUTRAL_KINDS = {"data_state"}
PRECONDITION_KINDS = set(REACH_KINDS) | CONDITION_KINDS | NEUTRAL_KINDS

ACCESS_CLASSES = {"OPEN", "ANY_ACCOUNT", "ROLE_OR_OWNERSHIP", "SERVICE_ONLY", "OPERATOR_ONLY", "UNCLEAR"}
TRACE_STEPS = {"source", "hop", "sink"}
INTERFACES = {"http", "rpc", "message", "cli", "library", "file", "ipc", "browser", "policy"}
TESTED_EVIDENCE = {"TESTED_LOCAL", "TESTED_STAGING", "DEPLOYED_OBSERVED"}
ROOT_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
LINE_SUFFIX = re.compile(r"(?::|#L|@L)\d+$")

SECRET_PATTERNS = [
    ("private key block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("cloud access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("repository host token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("chat workspace token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("payment live key", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}")),
    ("browser API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("signed token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]


class InputError(Exception):
    """A file that cannot be read or parsed (exit code 2)."""


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _no_duplicate_keys(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {show(key)} in a JSON object")
        seen.add(key)
    return dict(pairs)


def load_json(path: str):
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
    if size > MAX_BYTES:
        raise InputError(f"{path} is larger than {MAX_BYTES} bytes")
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read {path}: {exc}") from None
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except ValueError as exc:
        raise InputError(f"{path}: invalid JSON: {exc}") from None


def show(value, limit: int = 60) -> str:
    """Quote a user-supplied value for messages: printable, short."""
    text = str(value)
    text = "".join(ch if ch.isprintable() else "?" for ch in text)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return repr(text)


def is_text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def safe_rel_path(value) -> bool:
    if not is_text(value) or "\x00" in value or value != value.strip():
        return False
    if value.startswith(("/", "\\", "~")) or PureWindowsPath(value).drive:
        return False
    parts = PurePosixPath(value.replace("\\", "/")).parts
    return bool(parts) and ".." not in parts and value not in (".", "./")


def text_list(value) -> bool:
    return isinstance(value, list) and all(is_text(v) for v in value)


def identity(*parts) -> str:
    return " | ".join(" ".join(str(p).split()).casefold() for p in parts)


def walk_strings(value, path="$"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_strings(item, f"{path}[{index}]")


def secret_errors(document, label: str) -> list[str]:
    errors = []
    for path, text in walk_strings(document):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{label} {path}: contains a {name}; record the type and location, never the value")
                break
    return errors


# --------------------------------------------------------------------------
# coverage
# --------------------------------------------------------------------------


def _check_checks(checks, where: str, errors: list[str]) -> set[str]:
    """Validate a list of checks and return the union of their paths."""
    union: set[str] = set()
    if not isinstance(checks, list):
        errors.append(f"{where}: 'checks' must be a list")
        return union
    for index, check in enumerate(checks):
        at = f"{where} check {index + 1}"
        if not isinstance(check, dict):
            errors.append(f"{at}: must be an object")
            continue
        method = check.get("method")
        if method not in METHODS:
            errors.append(f"{at}: 'method' must be one of {sorted(METHODS)}")
        paths = check.get("paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"{at}: 'paths' must list the repository files this check covered")
        else:
            for p in paths:
                if safe_rel_path(p):
                    union.add(p)
                else:
                    errors.append(f"{at}: path {show(p)} must be repository-relative, without '..'")
        for field in ("invariant", "result"):
            if not is_text(check.get(field)):
                errors.append(f"{at}: '{field}' is required (the rule checked and what the check established)")
        if method in ("test", "tool") and not is_text(check.get("command")):
            errors.append(f"{at}: a {method} check needs the 'command' that ran")
        if "artifact" in check and check["artifact"] is not None and not safe_rel_path(check["artifact"]):
            errors.append(f"{at}: 'artifact' must be a relative path inside the output folder")
        if "reviewer" in check and not is_text(check["reviewer"]):
            errors.append(f"{at}: 'reviewer' must be text")
    return union


def _check_cell(cell, index: int, audit_revision, errors: list[str], warnings: list[str]) -> dict:
    where = f"cells[{index}]"
    info = {"id": None, "status": None, "reviewer": None, "findings": [], "attempt_reviewers": set(),
            "has_attempts": False}
    if not isinstance(cell, dict):
        errors.append(f"{where}: must be an object")
        return info
    if is_text(cell.get("id")):
        where = f"cell {show(cell['id'])}"
        info["id"] = cell["id"]
    for field in ("id", "surface", "boundary", "class"):
        if not is_text(cell.get(field)):
            errors.append(f"{where}: '{field}' is required")
    status = cell.get("status")
    if status not in CELL_STATUSES:
        errors.append(f"{where}: 'status' must be one of {sorted(CELL_STATUSES)}")
        status = None
    info["status"] = status

    reviewer = cell.get("reviewer")
    if reviewer is not None and not is_text(reviewer):
        errors.append(f"{where}: 'reviewer' must be text or absent")
        reviewer = None
    info["reviewer"] = reviewer

    checks = cell.get("checks", [])
    union = _check_checks(checks, where, errors)
    has_checks = isinstance(checks, list) and len(checks) > 0

    if "paths" in cell:
        paths = cell["paths"]
        if not isinstance(paths, list):
            errors.append(f"{where}: 'paths' must be a list")
        else:
            listed = {p for p in paths if safe_rel_path(p)}
            for p in paths:
                if not safe_rel_path(p):
                    errors.append(f"{where}: path {show(p)} must be repository-relative, without '..'")
            for p in sorted(listed - union):
                errors.append(f"{where}: path {show(p)} is listed as reviewed but no check covers it")
            for p in sorted(union - listed):
                errors.append(f"{where}: check path {show(p)} is missing from the cell's 'paths'")

    findings = cell.get("findings", [])
    if not isinstance(findings, list) or not all(is_text(f) for f in findings):
        errors.append(f"{where}: 'findings' must be a list of finding ids")
        findings = []
    elif len(set(findings)) != len(findings):
        errors.append(f"{where}: 'findings' lists an id twice")
    info["findings"] = list(findings)

    reason = cell.get("reason")
    if status in WORKING:
        if status == "PLANNED" and has_checks:
            errors.append(f"{where}: PLANNED cell carries checks; set the status the evidence supports")
        if status == "IN_PROGRESS" and not reviewer:
            errors.append(f"{where}: IN_PROGRESS needs the 'reviewer' working on it")
    elif status in EVIDENCE_STATUSES:
        if not reviewer:
            errors.append(f"{where}: {status} needs the 'reviewer' who examined it")
        if not has_checks:
            errors.append(f"{where}: {status} needs at least one check (paths read, invariant, result)")
        if status == "FAIL" and not findings:
            errors.append(f"{where}: FAIL needs the finding ids in 'findings'")
        if status == "NEEDS_REVIEW" and not findings and not is_text(reason):
            errors.append(f"{where}: NEEDS_REVIEW needs a linked lead in 'findings' or a 'reason'")
        revision = cell.get("revision")
        if not is_text(revision):
            errors.append(f"{where}: {status} needs the source 'revision' the evidence applies to")
        elif is_text(audit_revision) and revision != audit_revision:
            carried = cell.get("carried")
            if not isinstance(carried, dict):
                errors.append(f"{where}: evidence is from revision {show(revision)}, not the audited "
                              f"{show(audit_revision)}; re-examine it or record 'carried' with how the paths "
                              "were shown unchanged")
            else:
                if carried.get("from_revision") != revision:
                    errors.append(f"{where}: 'carried.from_revision' must equal the cell's revision")
                if carried.get("unchanged") is not True:
                    errors.append(f"{where}: carried evidence needs 'carried.unchanged': true")
                if not is_text(carried.get("how")):
                    errors.append(f"{where}: carried evidence needs 'carried.how' (the diff or comparison run)")
    elif status in REASON_STATUSES:
        if not is_text(reason):
            errors.append(f"{where}: {status} needs a 'reason'")

    attempts = cell.get("attempts", [])
    if not isinstance(attempts, list):
        errors.append(f"{where}: 'attempts' must be a list")
        attempts = []
    info["has_attempts"] = bool(attempts)
    for a_index, attempt in enumerate(attempts):
        at = f"{where} attempt {a_index + 1}"
        if not isinstance(attempt, dict):
            errors.append(f"{at}: must be an object")
            continue
        if attempt.get("status") not in ATTEMPT_STATUSES:
            errors.append(f"{at}: 'status' must be one of {sorted(ATTEMPT_STATUSES)}")
        if not is_text(attempt.get("reviewer")):
            errors.append(f"{at}: 'reviewer' is required")
        else:
            info["attempt_reviewers"].add(attempt["reviewer"])
        if not is_text(attempt.get("reopen_reason")):
            errors.append(f"{at}: 'reopen_reason' is required")
        if "checks" in attempt:
            _check_checks(attempt["checks"], at, errors)
    if status in EVIDENCE_STATUSES and reviewer and reviewer in info["attempt_reviewers"]:
        warnings.append(f"{where}: re-examined by {show(reviewer)}, who also did an earlier attempt; "
                        "a fresh reviewer is preferred after a cell is reopened")
    return info


def _check_gap_reviews(reviews, cell_ids: set, errors: list[str]) -> tuple[list[dict], set]:
    valid: list[dict] = []
    reopened: set = set()
    if not isinstance(reviews, list):
        errors.append("'gap_reviews' must be a list")
        return valid, reopened
    for index, review in enumerate(reviews):
        where = f"gap_reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{where}: must be an object")
            continue
        if is_text(review.get("id")):
            where = f"gap review {show(review['id'])}"
        if not is_text(review.get("reviewer")):
            errors.append(f"{where}: 'reviewer' is required")
        result = review.get("result")
        if result not in GAP_RESULTS:
            errors.append(f"{where}: 'result' must be 'clean' or 'gaps_found'")
        lists = {}
        for field in ("added", "reopened"):
            value = review.get(field, [])
            if not isinstance(value, list) or not all(is_text(v) for v in value):
                errors.append(f"{where}: '{field}' must be a list of cell ids")
                value = []
            for cid in value:
                if cid not in cell_ids:
                    errors.append(f"{where}: '{field}' names unknown cell {show(cid)}")
            lists[field] = value
        if result == "clean" and (lists["added"] or lists["reopened"]):
            errors.append(f"{where}: a clean review cannot add or reopen cells; use 'gaps_found'")
        if result == "gaps_found" and not (lists["added"] or lists["reopened"]):
            errors.append(f"{where}: 'gaps_found' must name the cells it added or reopened")
        reopened.update(lists["reopened"])
        valid.append({"reviewer": review.get("reviewer"), "result": result})
    return valid, reopened


def _cross_check(cells: list[dict], record_revision, findings_doc, errors: list[str], warnings: list[str]) -> None:
    label = "findings file"
    if not isinstance(findings_doc, dict):
        errors.append(f"{label}: top level must be a JSON object")
        return
    f_audit = findings_doc.get("audit")
    if isinstance(f_audit, dict) and is_text(record_revision) and f_audit.get("revision") != record_revision:
        errors.append(f"{label}: audit revision {show(f_audit.get('revision'))} differs from the record's "
                      f"{show(record_revision)}")
    raw = findings_doc.get("findings")
    if not isinstance(raw, list):
        errors.append(f"{label}: 'findings' must be a list")
        raw = []
    by_id = {f["id"]: f for f in raw if isinstance(f, dict) and is_text(f.get("id"))}

    linked: set = set()
    for cell in cells:
        if not cell["id"]:
            continue
        where = f"cell {show(cell['id'])}"
        refs = cell["findings"]
        linked.update(refs)
        known = [by_id[r] for r in refs if r in by_id]
        for ref in refs:
            if ref not in by_id:
                errors.append(f"{where}: links finding {show(ref)}, which the findings file does not contain")
        status = cell["status"]
        if status in ("PASS", "NOT_APPLICABLE"):
            for f in known:
                if f.get("confidence") in ("CONFIRMED", "LIKELY") and f.get("status") in ("OPEN", "ACCEPTED"):
                    errors.append(f"{where}: is {status} while {f.get('confidence')} finding {show(f['id'])} "
                                  f"is {f.get('status')}")
        if status == "FAIL" and refs and not any(
                f.get("confidence") in ("CONFIRMED", "LIKELY") and f.get("status") != "FALSE_POSITIVE"
                for f in known):
            errors.append(f"{where}: FAIL links no CONFIRMED or LIKELY finding that still stands")

    for fid in sorted(by_id):
        f = by_id[fid]
        if f.get("status") == "FALSE_POSITIVE" or fid in linked:
            continue
        if f.get("confidence") in ("CONFIRMED", "LIKELY"):
            errors.append(f"finding {show(fid)}: {f.get('confidence')} but no coverage cell links it")
        else:
            warnings.append(f"finding {show(fid)}: lead not linked from any coverage cell")

    report_cells = findings_doc.get("coverage", [])
    if isinstance(report_cells, list) and report_cells:
        report = {c.get("id"): c.get("status") for c in report_cells if isinstance(c, dict)}
        record_ids = {c["id"] for c in cells if c["id"]}
        for cell in cells:
            if not cell["id"] or cell["status"] in WORKING or cell["status"] is None:
                continue
            if cell["id"] not in report:
                errors.append(f"cell {show(cell['id'])}: missing from the findings file's 'coverage'")
            elif report[cell["id"]] != cell["status"]:
                errors.append(f"cell {show(cell['id'])}: record says {cell['status']}, findings file says "
                              f"{show(report[cell['id']])}")
        for rid in sorted(k for k in report if is_text(k) and k not in record_ids):
            errors.append(f"findings file coverage {show(rid)}: not in the coverage record")


def check_coverage(record, findings_doc=None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(record, dict):
        return {"errors": ["record: top level must be a JSON object"], "warnings": [], "counts": {},
                "gap_reviews": 0, "supported_claim": "none", "claim_blockers": ["the record is invalid"]}
    if record.get("record_version") != 1:
        errors.append("'record_version' must be 1")
    audit = record.get("audit")
    if not isinstance(audit, dict):
        errors.append("'audit' object with repository, revision, depth and scope is required")
        audit = {}
    for field in ("repository", "revision"):
        if not is_text(audit.get(field)):
            errors.append(f"audit: '{field}' is required")
    depth = audit.get("depth")
    if depth not in DEPTHS:
        errors.append(f"audit: 'depth' must be one of {sorted(DEPTHS)}")
    if not text_list(audit.get("scope")) or not audit.get("scope"):
        errors.append("audit: 'scope' must be a non-empty list")
    out_of_scope = audit.get("out_of_scope", [])
    if not text_list(out_of_scope):
        errors.append("audit: 'out_of_scope' must be a list of text")
        out_of_scope = []

    raw_cells = record.get("cells")
    if not isinstance(raw_cells, list):
        errors.append("'cells' must be a list")
        raw_cells = []
    cells: list[dict] = []
    seen_ids: dict = {}
    seen_identity: dict = {}
    for index, raw in enumerate(raw_cells):
        info = _check_cell(raw, index, audit.get("revision"), errors, warnings)
        cells.append(info)
        cid = info["id"]
        if cid is not None:
            if cid in seen_ids:
                errors.append(f"cell {show(cid)}: duplicate id (also cells[{seen_ids[cid]}])")
            else:
                seen_ids[cid] = index
        if isinstance(raw, dict) and all(is_text(raw.get(k)) for k in ("surface", "boundary", "class")):
            key = identity(raw["surface"], raw["boundary"], raw["class"])
            if key in seen_identity:
                errors.append(f"cells[{index}]: same surface, boundary and class as cells[{seen_identity[key]}]; "
                              "merge them or make the difference explicit")
            else:
                seen_identity[key] = index

    reviews, reopened = _check_gap_reviews(record.get("gap_reviews", []), set(seen_ids), errors)
    for cell in cells:
        if cell["id"] in reopened and not cell["has_attempts"]:
            errors.append(f"cell {show(cell['id'])}: reopened by a gap review but has no archived 'attempts'")
    if reviews and reviews[-1]["result"] == "clean":
        final = reviews[-1]["reviewer"]
        examined = {c["reviewer"] for c in cells if c["status"] in EVIDENCE_STATUSES and c["reviewer"]}
        if is_text(final) and final in examined:
            warnings.append(f"the final clean gap review was done by {show(final)}, who also examined cells; "
                            "use a reviewer who did not")

    if findings_doc is not None:
        _cross_check(cells, audit.get("revision"), findings_doc, errors, warnings)
    errors.extend(secret_errors(record, "record"))

    counts = Counter(c["status"] for c in cells if c["status"])
    blockers: list[str] = []
    if errors:
        claim = "none"
        blockers.append("the record has errors")
    else:
        if not cells:
            blockers.append("the record has no cells")
        for status in ("PLANNED", "IN_PROGRESS", "NOT_VERIFIED"):
            if counts[status]:
                blockers.append(f"{counts[status]} {status} cell(s)")
        unlinked = sum(1 for c in cells if c["status"] == "NEEDS_REVIEW" and not c["findings"])
        if unlinked:
            blockers.append(f"{unlinked} NEEDS_REVIEW cell(s) with no linked lead")
        if not reviews:
            blockers.append("no gap review recorded")
        elif reviews[-1]["result"] != "clean":
            blockers.append("the last gap review found gaps")
        if blockers:
            claim = "partial"
        else:
            if counts["OUT_OF_SCOPE"]:
                blockers.append(f"{counts['OUT_OF_SCOPE']} OUT_OF_SCOPE cell(s)")
            if depth != "full":
                blockers.append(f"audit depth is {depth}")
            if out_of_scope:
                blockers.append("audit lists out-of-scope areas")
            claim = "scoped" if blockers else "full"
    return {
        "errors": errors,
        "warnings": warnings,
        "counts": dict(sorted(counts.items())),
        "gap_reviews": len(reviews),
        "supported_claim": claim,
        "claim_blockers": blockers,
    }


def claim_satisfied(supported: str, requested: str | None) -> bool:
    if requested is None:
        return True
    order = {"none": 0, "partial": 1, "scoped": 2, "full": 3}
    return order[supported] >= order[requested]


# --------------------------------------------------------------------------
# rigor
# --------------------------------------------------------------------------


def severity_ceiling(impact_level: str, kinds: list[str]) -> str:
    """Highest severity the module's phase 6 rules allow for this impact and these preconditions."""
    base = RANK[impact_level]
    if base == RANK["INFO"]:
        return "INFO"
    reach = max((REACH_KINDS[k] for k in kinds if k in REACH_KINDS), default=0)
    conditions = sum(1 for k in kinds if k in CONDITION_KINDS)
    value = base - reach - min(conditions, 2)
    return SEVERITIES[max(RANK["LOW"], value)]


def _check_trace(trace, where: str, errors: list[str]) -> None:
    if not isinstance(trace, list) or not trace:
        errors.append(f"{where}: 'trace' must be a non-empty list of steps")
        return
    for index, step in enumerate(trace):
        at = f"{where} trace step {index + 1}"
        if not isinstance(step, dict):
            errors.append(f"{at}: must be an object")
            continue
        kind = step.get("step")
        if kind not in TRACE_STEPS:
            errors.append(f"{at}: 'step' must be source, hop or sink")
        elif len(trace) >= 2:
            expected = "source" if index == 0 else "sink" if index == len(trace) - 1 else "hop"
            if kind != expected:
                errors.append(f"{at}: expected '{expected}' (a trace runs source, hops, sink)")
        elif kind == "hop":
            errors.append(f"{at}: a one-step trace is a source or a sink, not a hop")
        if not safe_rel_path(step.get("file")):
            errors.append(f"{at}: 'file' must be repository-relative, without '..'")
        line = step.get("line")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            errors.append(f"{at}: 'line' must be a positive integer")
        if not is_text(step.get("note")):
            errors.append(f"{at}: 'note' must say what happens at this step")


def check_rigor(findings_doc) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    ratings: list[dict] = []
    if not isinstance(findings_doc, dict) or not isinstance(findings_doc.get("findings"), list):
        return {"errors": ["findings file: expected an object with a 'findings' list"], "warnings": [],
                "checked": {}, "ratings": []}
    keys: dict = {}
    checked = Counter()
    for index, f in enumerate(findings_doc["findings"]):
        if not isinstance(f, dict):
            errors.append(f"findings[{index}]: must be an object")
            continue
        where = f"finding {show(f.get('id'))}" if is_text(f.get("id")) else f"findings[{index}]"
        key = f.get("root_cause_key")
        if key is not None:
            if not isinstance(key, str) or not ROOT_KEY.match(key):
                errors.append(f"{where}: 'root_cause_key' must match {ROOT_KEY.pattern}")
            elif LINE_SUFFIX.search(key):
                errors.append(f"{where}: 'root_cause_key' must not end in a line number; lines move between runs")
            elif key in keys:
                errors.append(f"{where}: 'root_cause_key' repeats {keys[key]}; one root cause is one finding")
            else:
                keys[key] = where
        confidence, status = f.get("confidence"), f.get("status")
        if status == "FALSE_POSITIVE" or confidence not in ("CONFIRMED", "LIKELY"):
            continue
        checked[confidence] += 1

        if key is None:
            errors.append(f"{where}: 'root_cause_key' is required (stable across runs, no line numbers)")
        if not is_text(f.get("invariant")):
            errors.append(f"{where}: 'invariant' is required (the rule the code must keep)")
        if not is_text(f.get("severity_reason")):
            errors.append(f"{where}: 'severity_reason' is required (one sentence: who, what they get, conditions)")
        impact = f.get("impact_level")
        severity = f.get("severity")
        if impact not in RANK:
            errors.append(f"{where}: 'impact_level' must be one of {SEVERITIES} (the level the demonstrated "
                          "impact alone gives)")
            impact = None
        if severity not in RANK:
            errors.append(f"{where}: 'severity' must be one of {SEVERITIES}")
            severity = None
        if impact and severity:
            if RANK[severity] > RANK[impact]:
                errors.append(f"{where}: severity {severity} is above the demonstrated impact level {impact}")
            if confidence == "CONFIRMED" and severity == "INFO" and RANK[impact] >= RANK["LOW"]:
                errors.append(f"{where}: a confirmed boundary crossing is rated at least LOW")

        kinds: list[str] = []
        preconditions = f.get("preconditions")
        if not isinstance(preconditions, list):
            errors.append(f"{where}: 'preconditions' must be a list (empty if none)")
        else:
            for p_index, p in enumerate(preconditions):
                at = f"{where} precondition {p_index + 1}"
                if not isinstance(p, dict):
                    errors.append(f"{at}: type it as an object with 'kind' and 'detail'")
                    continue
                if p.get("kind") not in PRECONDITION_KINDS:
                    errors.append(f"{at}: 'kind' must be one of {sorted(PRECONDITION_KINDS)}")
                else:
                    kinds.append(p["kind"])
                if not is_text(p.get("detail")):
                    errors.append(f"{at}: 'detail' is required")

        if impact and severity:
            ceiling = severity_ceiling(impact, kinds)
            ratings.append({"id": f.get("id"), "impact_level": impact, "precondition_kinds": sorted(kinds),
                            "ceiling": ceiling, "severity": severity})
            if RANK[severity] > RANK[ceiling]:
                warnings.append(f"{where}: severity {severity} is above the ceiling {ceiling} that the rating "
                                f"rules give for impact {impact} and preconditions {sorted(kinds) or 'none'}; "
                                "lower it or explain the exception in 'severity_reason'")

        access = f.get("access_class")
        if access is not None:
            if access not in ACCESS_CLASSES:
                errors.append(f"{where}: 'access_class' must be one of {sorted(ACCESS_CLASSES)}")
            elif access == "OPERATOR_ONLY":
                warnings.append(f"{where}: operators are trusted in the threat model; confirm the actor is not")
            elif access == "UNCLEAR":
                warnings.append(f"{where}: access class is unsettled; settle the guard before rating")

        evidence = f.get("evidence_type")
        if "trace" in f:
            _check_trace(f["trace"], where, errors)
        elif confidence == "LIKELY" or evidence == "STATIC_CONFIRMED":
            errors.append(f"{where}: {confidence} with {evidence} evidence needs a 'trace' from source to sink")
        if confidence == "CONFIRMED" and evidence in TESTED_EVIDENCE:
            repro = f.get("reproduction")
            if not isinstance(repro, dict):
                errors.append(f"{where}: {evidence} needs a 'reproduction' (interface, steps, observed)")
            else:
                if repro.get("interface") not in INTERFACES:
                    errors.append(f"{where}: 'reproduction.interface' must be one of {sorted(INTERFACES)}")
                if not text_list(repro.get("steps")) or not repro.get("steps"):
                    errors.append(f"{where}: 'reproduction.steps' must list what was run")
                if not is_text(repro.get("observed")):
                    errors.append(f"{where}: 'reproduction.observed' must state the actual result")
        if confidence == "LIKELY" and not is_text(f.get("owner_check")):
            errors.append(f"{where}: LIKELY needs an 'owner_check' (the non-destructive observation that settles it)")
    return {"errors": errors, "warnings": warnings, "checked": dict(sorted(checked.items())), "ratings": ratings}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def emit(report: dict, as_json: bool, lines: list[str]) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    for line in lines:
        print(line)
    for message in report["errors"]:
        print(f"ERROR {message}")
    for message in report["warnings"]:
        print(f"WARNING {message}")


def cmd_coverage(opts) -> int:
    record = load_json(opts.record)
    findings = load_json(opts.findings) if opts.findings else None
    report = check_coverage(record, findings)
    ok = claim_satisfied(report["supported_claim"], opts.claim)
    report["requested_claim"] = opts.claim
    report["claim_supported"] = ok
    total = sum(report["counts"].values())
    lines = [f"audit_record coverage: {total} cells {report['counts']}; gap reviews: {report['gap_reviews']}; "
             f"{len(report['errors'])} errors, {len(report['warnings'])} warnings."]
    emit(report, opts.json, lines)
    if not opts.json:
        blocked = f" (short of full: {'; '.join(report['claim_blockers'])})" if report["claim_blockers"] else ""
        print(f"Supported claim: {report['supported_claim']}{blocked}")
        if opts.claim and not ok:
            print(f"Requested claim '{opts.claim}' is not supported by this record.")
    return 1 if report["errors"] or not ok else 0


def cmd_rigor(opts) -> int:
    report = check_rigor(load_json(opts.findings))
    total = sum(report["checked"].values())
    lines = [f"audit_record rigor: {total} findings checked {report['checked']}; "
             f"{len(report['errors'])} errors, {len(report['warnings'])} warnings."]
    emit(report, opts.json, lines)
    if not opts.json:
        for r in report["ratings"]:
            print(f"  {show(r['id'])}: impact {r['impact_level']}, preconditions {r['precondition_kinds'] or 'none'}, "
                  f"ceiling {r['ceiling']}, rated {r['severity']}")
    return 1 if report["errors"] else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="audit_record.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("coverage", help="check a coverage record and the claim it supports")
    p.add_argument("--record", required=True, help="coverage record JSON (e.g. security/coverage-record.json)")
    p.add_argument("--findings", help="findings JSON to cross-check (e.g. security/code-audit-findings.json)")
    p.add_argument("--claim", choices=["full", "scoped"],
                   help="exit 1 unless the record supports this coverage claim")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser("rigor", help="check stricter fields and severity ceilings on findings")
    p.add_argument("--findings", required=True, help="findings JSON (e.g. security/code-audit-findings.json)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.set_defaults(func=cmd_rigor)
    return ap


def main(argv: list[str] | None = None) -> int:
    opts = build_parser().parse_args(argv)
    try:
        return opts.func(opts)
    except InputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
