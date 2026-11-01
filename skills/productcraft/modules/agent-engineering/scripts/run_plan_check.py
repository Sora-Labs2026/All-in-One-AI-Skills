#!/usr/bin/env python3
"""ProductCraft Agent Engineering: check an autonomous run plan before launch.

Reads a run plan (JSON, or TOML on Python 3.11+) that describes an agent loop,
scheduled agent job or other unattended run, and reports whether it has what
every such run needs: a time budget and a token or money budget, stop
conditions beyond the budget, a checkpoint state file, an approval gate for
every consequential action, no permission bypass, caps and allowlists for any
payments, and no secret values written into the plan.

It checks the plan only. The driver that runs the loop still has to enforce
what the plan says. The script is read-only, never touches the network and
never prints a value that looks like a secret (only its location in the plan).

Exit codes: 0 no errors (and no warnings with --strict), 1 findings that fail
the check, 2 the plan could not be read or parsed.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

VERSION = "1.0.0"

# Tokens in an action name that make it consequential (effects beyond the run's own sandbox).
CONSEQUENTIAL = {
    "push", "merge", "deploy", "release", "publish", "upload", "tag",
    "send", "post", "email", "comment", "reply", "notify",
    "pay", "payment", "purchase", "buy", "transfer", "refund", "charge",
    "delete", "drop", "destroy", "purge", "truncate", "wipe",
    "migrate", "migration", "rotate", "grant", "revoke", "sign", "accept",
}
PAYMENT = {"pay", "payment", "purchase", "buy", "transfer", "refund", "charge"}
APPROVING_TIMEOUTS = {"approve", "approved", "auto", "auto-approve", "autoapprove", "proceed", "continue", "send", "allow", "yes"}
BYPASS_MODES = {"bypass", "bypasspermissions", "bypass-permissions", "dangerously-skip-permissions",
                "skip-permissions", "yolo", "all", "unrestricted", "full"}
SELF_JUDGES = {"self", "builder", "same", "same-agent", "author", "generator"}
OPEN_NETWORK = {"any", "all", "unrestricted", "full", "open"}
NO_ISOLATION = {"", "none", "host", "no"}

VAGUE = re.compile(
    r"\b(good|better|best|nice|clean|cleaner|properly|well|robust|polished|high[- ]quality|"
    r"looks?|as needed|appropriate(?:ly)?|improved?|improves|optimal|reasonable)\b", re.I)
DECIDABLE_MARKERS = re.compile(r"`|\d|\bexit|\bpass|\bfail|\bmatch|\bequal|\bdiff|==|<|>|%|\bzero\b|\bno\b", re.I)

SECRET_KEY = re.compile(r"(secret|token|passw(or)?d|api[_-]?key|private[_-]?key|credential|auth[_-]?header|bearer)", re.I)
REFERENCE_VALUE = re.compile(r"^(env:|vault:|secret:|ref:|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$|<[^>]*>$|[A-Z][A-Z0-9_]{2,}$)")
SECRET_SHAPES = [
    re.compile(r"^sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"^sk_(live|test)_[A-Za-z0-9]{10,}"),
    re.compile(r"^gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"^github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"^xox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"^AKIA[0-9A-Z]{16}$"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"^eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),
]


class Finding:
    __slots__ = ("severity", "code", "path", "message")

    def __init__(self, severity: str, code: str, path: str, message: str) -> None:
        self.severity, self.code, self.path, self.message = severity, code, path, message

    def as_dict(self) -> Dict[str, str]:
        return {"severity": self.severity, "id": self.code, "path": self.path, "message": self.message}


def tokens(name: str) -> List[str]:
    """Lower-case word tokens of an action name, with simple plural and -ing forms folded."""
    out = []
    for raw in re.split(r"[^A-Za-z0-9]+", name.lower()):
        if not raw:
            continue
        out.append(raw)
        if raw.endswith("ing") and len(raw) > 5:
            out.extend([raw[:-3], raw[:-3] + "e"])
        elif raw.endswith("ies") and len(raw) > 4:
            out.append(raw[:-3] + "y")
        elif raw.endswith("es") and len(raw) > 4:
            out.extend([raw[:-2], raw[:-1]])
        elif raw.endswith("s") and len(raw) > 3:
            out.append(raw[:-1])
    return out


def is_consequential(action: str) -> bool:
    return any(t in CONSEQUENTIAL for t in tokens(action))


def is_payment(action: str) -> bool:
    return any(t in PAYMENT for t in tokens(action))


def positive_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def norm(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def walk(node: Any, path: str = "") -> Iterable[Tuple[str, str, Any]]:
    """Yield (path, key, value) for every scalar in the plan."""
    if isinstance(node, dict):
        for key in sorted(node, key=str):
            child = f"{path}.{key}" if path else str(key)
            if isinstance(node[key], (dict, list)):
                yield from walk(node[key], child)
            else:
                yield child, str(key), node[key]
    elif isinstance(node, list):
        for i, item in enumerate(node):
            child = f"{path}[{i}]"
            if isinstance(item, (dict, list)):
                yield from walk(item, child)
            else:
                yield child, "", item


def secret_like(key: str, value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    if any(shape.search(text) for shape in SECRET_SHAPES):
        return True
    if (SECRET_KEY.search(key) and not REFERENCE_VALUE.match(text) and len(text) >= 8
            and " " not in text and not text.isdigit()):
        return True
    return False


def section(plan: Dict[str, Any], name: str) -> Dict[str, Any]:
    value = plan.get(name)
    return value if isinstance(value, dict) else {}


def check_plan(plan: Dict[str, Any]) -> List[Finding]:
    f: List[Finding] = []
    err = lambda code, path, msg: f.append(Finding("ERROR", code, path, msg))
    warn = lambda code, path, msg: f.append(Finding("WARN", code, path, msg))

    # Budget: time, and tokens or money; iteration cap recommended.
    budget = section(plan, "budget")
    for key in ("max_wall_clock_minutes", "max_iterations", "max_tokens", "max_cost", "max_cost_usd"):
        if key in budget and not positive_number(budget[key]):
            err("B04", f"budget.{key}", "must be a positive number")
    max_cost = budget.get("max_cost", budget.get("max_cost_usd"))
    if not positive_number(budget.get("max_wall_clock_minutes")):
        err("B01", "budget.max_wall_clock_minutes", "no time budget: set a wall-clock limit the driver enforces")
    if not (positive_number(budget.get("max_tokens")) or positive_number(max_cost)):
        err("B02", "budget.max_tokens|max_cost", "no token or money budget: set max_tokens, max_cost (with budget.currency) or both")
    if "max_cost" in budget and positive_number(max_cost) and not norm(budget.get("currency")):
        warn("B05", "budget.currency", "max_cost has no currency")
    if not positive_number(budget.get("max_iterations")):
        warn("B03", "budget.max_iterations", "no iteration cap: add one so a cheap, fast failure cannot repeat until the time budget runs out")

    # Goal: decidable done-when and boundaries.
    goal = section(plan, "goal")
    done = goal.get("done_when")
    if not isinstance(done, list) or not [d for d in done if isinstance(d, str) and d.strip()]:
        err("G01", "goal.done_when", "no machine-checkable done-when: list the commands or comparisons that decide success")
    else:
        for i, item in enumerate(done):
            if isinstance(item, str) and VAGUE.search(item) and not DECIDABLE_MARKERS.search(item):
                warn("G02", f"goal.done_when[{i}]", "reads like an opinion, not a check: name the command, number or comparison")
    must_not = goal.get("must_not")
    if not isinstance(must_not, list) or not must_not:
        warn("G03", "goal.must_not", "no boundaries: list what the run must not do to reach the goal (delete tests, edit the checker, leave scope)")
    if norm(goal.get("judge")) in SELF_JUDGES:
        warn("G04", "goal.judge", "the builder judges its own work: use an independent, deterministic judge")

    # Stop conditions beyond the budget.
    stop = section(plan, "stop")
    for key in ("no_progress_checkpoints", "max_same_failure"):
        if key in stop and not positive_int(stop[key]):
            err("S04", f"stop.{key}", "must be a positive integer")
    has_np = positive_int(stop.get("no_progress_checkpoints"))
    has_sf = positive_int(stop.get("max_same_failure"))
    if not (has_np or has_sf):
        err("S01", "stop", "no stop condition besides the budget: set no_progress_checkpoints and max_same_failure")
    elif not (has_np and has_sf):
        missing = "no_progress_checkpoints" if not has_np else "max_same_failure"
        warn("S02", f"stop.{missing}", "missing; a loop can still spin on one failure or make no progress")
    if not (norm(stop.get("stop_file")) or norm(stop.get("stop_signal"))):
        warn("S03", "stop.stop_file", "no external stop signal the owner can use without killing the process")

    # Checkpoints.
    cp = section(plan, "checkpoints")
    if not norm(cp.get("state_file")):
        err("C01", "checkpoints.state_file", "no state file: the run cannot be resumed or audited")
    if cp.get("commit_each_step") is not True:
        warn("C02", "checkpoints.commit_each_step", "not true: one commit per verified step makes a bad step one revert")

    # Actions and approval gates.
    actions = plan.get("actions")
    if actions is None:
        warn("A06", "actions", "no actions listed: list every kind of action the run may take so gates can be checked")
        actions = []
    elif not isinstance(actions, list):
        err("A07", "actions", "must be a list of action names")
        actions = []
    approvals = section(plan, "approvals")
    gated = {norm(a) for a in approvals.get("required_for", []) if isinstance(a, str)} if isinstance(approvals.get("required_for"), list) else set()
    exempt: Dict[str, Any] = {}
    raw_exempt = approvals.get("not_required", [])
    if isinstance(raw_exempt, list):
        for item in raw_exempt:
            if isinstance(item, dict) and norm(item.get("action")):
                exempt[norm(item["action"])] = item.get("reason")
    consequential = [a for a in actions if isinstance(a, str) and is_consequential(a)]
    for action in consequential:
        key = norm(action)
        if key in gated:
            continue
        if key in exempt:
            if not norm(exempt[key]):
                err("A02", f"approvals.not_required[{action}]", "exemption from approval has no recorded reason")
            else:
                warn("A02", f"approvals.not_required[{action}]", "runs without approval by owner decision; confirm the decision is current")
            continue
        err("A01", f"actions[{action}]", "consequential action without an approval gate: add it to approvals.required_for")
    needs_gate = bool(consequential) or bool(gated)
    timeout = norm(approvals.get("on_timeout"))
    if timeout in APPROVING_TIMEOUTS:
        err("A03", "approvals.on_timeout", "a timeout must never approve: use stop, hold or report")
    elif needs_gate and not timeout:
        warn("A04", "approvals.on_timeout", "not set: state that an unanswered approval stops or holds the action")
    if gated and not norm(approvals.get("approver")):
        warn("A05", "approvals.approver", "no approver named for gated actions")

    # Permissions and isolation.
    perms = plan.get("permissions")
    if not isinstance(perms, dict):
        warn("P02", "permissions", "no permission section: state the tool allowlist for the run")
        perms = {}
    mode = norm(perms.get("mode"))
    if perms.get("bypass") is True or mode in BYPASS_MODES:
        err("P01", "permissions", "permission bypass for an unattended run: use a per-phase tool allowlist")
    elif perms and mode != "allowlist":
        warn("P02", "permissions.mode", "not an allowlist")
    if norm(perms.get("network")) in OPEN_NETWORK:
        warn("P03", "permissions.network", "unrestricted network access: allowlist the hosts the run needs")

    schedule = plan.get("schedule")
    unattended = bool(schedule) or plan.get("unattended") is True
    if unattended and norm(plan.get("isolation")) in NO_ISOLATION:
        warn("U01", "isolation", "unattended run without isolation: use a worktree, container or VM without production credentials")
    if isinstance(schedule, dict) and not norm(schedule.get("overlap")):
        warn("U02", "schedule.overlap", "no overlap policy: say whether a new run is skipped or queued while one is running")

    # Payments: caps, allowlists, integer minor units.
    pay_actions = [a for a in actions if isinstance(a, str) and is_payment(a)]
    spending = plan.get("spending")
    if pay_actions:
        if not isinstance(spending, dict):
            err("M01", "spending", "payment actions without a spending policy: set caps, currency and allowed recipients")
        else:
            for key in ("max_per_payment", "max_per_session", "max_per_day"):
                if not positive_int(spending.get(key)):
                    err("M02", f"spending.{key}", "missing or not a positive integer in the currency's smallest unit (no floats for money)")
            if not norm(spending.get("currency")):
                err("M03", "spending.currency", "missing")
            recipients = spending.get("allowed_recipients")
            if not isinstance(recipients, list) or not recipients:
                err("M04", "spending.allowed_recipients", "no recipient allowlist")
            per, ses = spending.get("max_per_payment"), spending.get("max_per_session")
            if positive_int(per) and positive_int(ses) and per > ses:
                err("M05", "spending.max_per_payment", "larger than max_per_session")
            if spending.get("policy_set_by_agent") is True:
                err("M06", "spending.policy_set_by_agent", "the agent must not set or change its own spending policy")

    # Secrets written into the plan.
    for path, key, value in walk(plan):
        if secret_like(key, value):
            err("X01", path, "looks like a secret value: refer to it by name (env:NAME or vault:...) and rotate it if it was real")

    return f


def load_plan(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".toml":
        try:
            import tomllib  # Python 3.11+
        except ImportError as exc:  # pragma: no cover - depends on interpreter
            raise ValueError("TOML plans need Python 3.11 or later; use JSON") from exc
        data = tomllib.loads(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("the plan must be a JSON object at the top level")
    return data


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check an autonomous agent run plan for budgets, stop conditions, checkpoints, approval gates, "
                    "permissions, payment controls and secret values. Read-only and offline.",
        epilog="Exit codes: 0 pass, 1 findings that fail the check, 2 unreadable or invalid plan. "
               "Template: modules/agent-engineering/assets/run-plan.example.json")
    parser.add_argument("plan", help="run plan file (.json, or .toml on Python 3.11+)")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings as well as errors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    path = Path(args.plan)
    try:
        plan = load_plan(path)
    except FileNotFoundError:
        print(f"run_plan_check: cannot read {path}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"run_plan_check: invalid plan {path}: {exc}", file=sys.stderr)
        return 2

    findings = check_plan(plan)
    errors = sum(1 for x in findings if x.severity == "ERROR")
    warnings = len(findings) - errors
    if args.json:
        print(json.dumps({"plan": str(path), "errors": errors, "warnings": warnings,
                          "findings": [x.as_dict() for x in findings]}, indent=2, sort_keys=True))
    else:
        print(f"run_plan_check {VERSION}: {path}")
        for x in sorted(findings, key=lambda y: (y.severity != "ERROR", y.code, y.path)):
            print(f"{x.severity:5} {x.code} {x.path}: {x.message}")
        verdict = "FAIL" if errors or (args.strict and warnings) else "PASS"
        print(f"{verdict}: {errors} error(s), {warnings} warning(s). The driver must still enforce the plan.")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
