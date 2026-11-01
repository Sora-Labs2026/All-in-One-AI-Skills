#!/usr/bin/env python3
"""Grade agent tool-call traces against a behavioral spec (read-only).

A spec lists observable steps (tool name, a field of the tool input, optional
patterns on the result) with required flags and ordering constraints, plus
forbidden calls. A trace is either the stream-JSON event output of a headless
agent run (assistant tool_use blocks and user tool_result blocks) or a plain
JSONL file with one tool call per line ({"tool", "input", "output",
"is_error"}). The script reports, per trace, which steps passed with the call
that proved it, which failed and why, any forbidden calls, and a summary
across traces.

Standard library only. It reads the files it is given and never runs anything.
Exit codes: 0 every trace compliant, 1 at least one trace not compliant,
2 usage error, unreadable file or invalid spec.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

STEP_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MATCH_KEYS = {"id", "tool", "field", "match", "output", "output_not", "error", "required", "after", "before", "description"}
TOKENISH = re.compile(r"(?=[A-Za-z0-9_+/=-]*\d)(?=[A-Za-z0-9_+/=-]*[A-Za-z])[A-Za-z0-9_+/=-]{32,}")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
EXCERPT = 70


class SpecError(Exception):
    pass


def _regex(value, where):
    if value is None:
        return None
    if not isinstance(value, str):
        raise SpecError(f"{where} must be a string")
    try:
        return re.compile(value)
    except re.error as exc:
        raise SpecError(f"{where} is not a valid regular expression: {exc}") from None


def _ids(value, where):
    if value is None:
        return []
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
        raise SpecError(f"{where} must be a step id or a list of step ids")
    return items


class Matcher:
    def __init__(self, raw, where, ordered):
        if not isinstance(raw, dict):
            raise SpecError(f"{where} must be an object")
        unknown = set(raw) - MATCH_KEYS
        if unknown:
            raise SpecError(f"{where} has unknown keys: {', '.join(sorted(unknown))}")
        self.id = raw.get("id")
        if not isinstance(self.id, str) or not STEP_ID.match(self.id):
            raise SpecError(f"{where} needs an 'id' of letters, digits, '_', '-' or '.'")
        self.tool = _regex(raw.get("tool", ".*"), f"{where}.tool")
        field = raw.get("field")
        if field is not None and not isinstance(field, str):
            raise SpecError(f"{where}.field must be a string such as 'command' or 'file_path'")
        self.field = field
        self.match = _regex(raw.get("match"), f"{where}.match")
        self.output = _regex(raw.get("output"), f"{where}.output")
        self.output_not = _regex(raw.get("output_not"), f"{where}.output_not")
        self.error = raw.get("error")
        if self.error is not None and not isinstance(self.error, bool):
            raise SpecError(f"{where}.error must be true or false")
        self.required = raw.get("required", True)
        if not isinstance(self.required, bool):
            raise SpecError(f"{where}.required must be true or false")
        self.after = _ids(raw.get("after"), f"{where}.after") if ordered else []
        self.before = _ids(raw.get("before"), f"{where}.before") if ordered else []
        if not ordered and ("after" in raw or "before" in raw):
            raise SpecError(f"{where}: forbidden entries take no ordering")

    def field_text(self, event):
        data = event["input"]
        if self.field is None:
            return json.dumps(data, sort_keys=True, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data)
        node = data
        for part in self.field.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        if isinstance(node, (dict, list)):
            return json.dumps(node, sort_keys=True, ensure_ascii=False)
        return str(node)

    def matches(self, event):
        if not self.tool.fullmatch(event["tool"]):
            return False
        text = self.field_text(event)
        if self.match is not None and (text is None or not self.match.search(text)):
            return False
        if self.match is None and self.field is not None and text is None:
            return False
        if self.output is not None and not self.output.search(event["output"]):
            return False
        if self.output_not is not None and self.output_not.search(event["output"]):
            return False
        if self.error is not None and event["is_error"] != self.error:
            return False
        return True


def load_spec(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SpecError(f"cannot read spec: {exc.strerror}") from None
    except ValueError as exc:
        raise SpecError(f"spec is not valid JSON: {exc}") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list) or not raw["steps"]:
        raise SpecError("spec must be an object with a non-empty 'steps' list")
    steps = [Matcher(s, f"steps[{i}]", True) for i, s in enumerate(raw["steps"])]
    forbidden = [Matcher(s, f"forbidden[{i}]", False) for i, s in enumerate(raw.get("forbidden") or [])]
    ids = [s.id for s in steps]
    if len(set(ids)) != len(ids):
        raise SpecError("step ids must be unique")
    known = set(ids)
    for s in steps:
        for ref in s.after + s.before:
            if ref not in known:
                raise SpecError(f"step '{s.id}' refers to unknown step '{ref}'")
            if ref == s.id:
                raise SpecError(f"step '{s.id}' refers to itself")
    order = _topological(steps)
    return {"id": str(raw.get("id") or Path(path).stem), "steps": steps, "order": order, "forbidden": forbidden}


def _topological(steps):
    by_id = {s.id: s for s in steps}
    state, order = {}, []

    def visit(sid, chain):
        if state.get(sid) == "done":
            return
        if state.get(sid) == "active":
            raise SpecError("'after' constraints form a cycle: " + " -> ".join(chain + [sid]))
        state[sid] = "active"
        for dep in by_id[sid].after:
            visit(dep, chain + [sid])
        state[sid] = "done"
        order.append(sid)

    for s in steps:
        visit(s.id, [])
    return order


def _result_text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")) if item.get("type", "text") == "text" else "")
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        for key in ("stdout", "output", "text", "content"):
            if key in content:
                return _result_text(content[key])
        return json.dumps(content, sort_keys=True)
    return str(content)


def _input(value):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, (dict, list)) else value
        except ValueError:
            return value
    return value if value is not None else {}


def load_trace(path, main_only=False):
    """Return (events, skipped_line_count)."""
    events, pending, skipped = [], {}, 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if not isinstance(obj, dict):
                skipped += 1
                continue
            kind = obj.get("type")
            message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            content = message.get("content")
            if kind in ("assistant", "user") and isinstance(content, list):
                nested = obj.get("parent_tool_use_id") is not None
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if kind == "assistant" and block.get("type") == "tool_use":
                        if main_only and nested:
                            continue
                        event = {"tool": str(block.get("name", "unknown")), "input": _input(block.get("input")),
                                 "output": "", "is_error": False}
                        events.append(event)
                        if block.get("id"):
                            pending[block["id"]] = event
                    elif kind == "user" and block.get("type") == "tool_result":
                        event = pending.pop(block.get("tool_use_id"), None)
                        if event is not None:
                            event["output"] = _result_text(block.get("content"))
                            event["is_error"] = block.get("is_error") in (True, "true")
                continue
            tool = obj.get("tool", obj.get("tool_name"))
            if isinstance(tool, str):
                output = obj.get("output", obj.get("tool_response", obj.get("result")))
                events.append({"tool": tool, "input": _input(obj.get("input", obj.get("tool_input"))),
                               "output": _result_text(output), "is_error": obj.get("is_error") in (True, "true")})
            # other event types (system, result, stream deltas) carry no tool call
    return events, skipped


def excerpt(text):
    if text is None:
        return ""
    text = CONTROL.sub(" ", str(text)).replace("\n", " ")
    home = os.path.expanduser("~")
    if home and home not in ("/", "~"):
        text = text.replace(home, "~")
    text = TOKENISH.sub("[REDACTED]", text)
    return text if len(text) <= EXCERPT else text[:EXCERPT - 3] + "..."


def _violation(step, idx, chosen, candidates):
    """Why call `idx` cannot satisfy `step`'s ordering, or None when it can."""
    for a in step.after:
        if idx <= chosen[a]:
            return f"must come after '{a}' (call #{chosen[a] + 1}); match was call #{idx + 1}"
    for b in step.before:
        if candidates[b] and idx >= candidates[b][0]:
            return f"must come before '{b}' (first at call #{candidates[b][0] + 1}); match was call #{idx + 1}"
    return None


def grade(spec, events):
    candidates = {s.id: [i for i, e in enumerate(events) if s.matches(e)] for s in spec["steps"]}
    by_id = {s.id: s for s in spec["steps"]}
    chosen, reasons = {}, {}
    for sid in spec["order"]:
        step = by_id[sid]
        failed_prereq = [a for a in step.after if a not in chosen]
        if failed_prereq:
            reasons[sid] = f"prerequisite '{failed_prereq[0]}' did not pass"
            continue
        if not candidates[sid]:
            reasons[sid] = "no matching tool call"
            continue
        first_reason = None
        for idx in candidates[sid]:
            why = _violation(step, idx, chosen, candidates)
            if why is None:
                chosen[sid] = idx
                break
            if first_reason is None:
                first_reason = why
        if sid not in chosen:
            reasons[sid] = first_reason
    steps = []
    for s in spec["steps"]:
        ev = None
        if s.id in chosen:
            e = events[chosen[s.id]]
            ev = {"index": chosen[s.id] + 1, "tool": e["tool"], "excerpt": excerpt(s.field_text(e))}
        steps.append({"id": s.id, "required": s.required, "passed": s.id in chosen, "evidence": ev,
                      "reason": None if s.id in chosen else reasons.get(s.id)})
    forbidden = []
    for f in spec["forbidden"]:
        for i, e in enumerate(events):
            if f.matches(e):
                forbidden.append({"id": f.id, "index": i + 1, "tool": e["tool"], "excerpt": excerpt(f.field_text(e))})
    required = [s for s in steps if s["required"]]
    passed = sum(1 for s in required if s["passed"])
    rate = passed / len(required) if required else 1.0
    return {"steps": steps, "forbidden": forbidden, "required_passed": passed, "required_total": len(required),
            "compliance": round(rate, 4), "compliant": passed == len(required) and not forbidden}


def render_text(spec, results):
    lines = [f"spec {spec['id']}: {len(spec['steps'])} steps, {len(spec['forbidden'])} forbidden patterns"]
    width = max(len(s.id) for s in spec["steps"])
    for r in results:
        lines.append("")
        lines.append(f"trace {r['path']}  ({r['events']} tool calls" + (f", {r['skipped_lines']} unparsable lines skipped" if r["skipped_lines"] else "") + ")")
        for s in r["steps"]:
            tag = "PASS" if s["passed"] else ("FAIL" if s["required"] else "miss")
            opt = "" if s["required"] else " (optional)"
            if s["passed"]:
                ev = s["evidence"]
                lines.append(f"  {tag}  {s['id']:<{width}}  #{ev['index']} {ev['tool']} {ev['excerpt']}{opt}")
            else:
                lines.append(f"  {tag}  {s['id']:<{width}}  {s['reason']}{opt}")
        for f in r["forbidden"]:
            lines.append(f"  FORBIDDEN  {f['id']}  #{f['index']} {f['tool']} {f['excerpt']}")
        lines.append(f"  compliance {r['required_passed']}/{r['required_total']} required steps ({r['compliance']:.0%})"
                     + ("" if r["compliant"] else "  NOT COMPLIANT"))
    if len(results) > 1:
        lines.append("")
        lines.append(f"summary over {len(results)} traces")
        for s in spec["steps"]:
            n = sum(1 for r in results for x in r["steps"] if x["id"] == s.id and x["passed"])
            lines.append(f"  {s.id:<{width}}  {n}/{len(results)}" + ("" if s.required else "  (optional)"))
        ok = sum(1 for r in results if r["compliant"])
        lines.append(f"  compliant traces: {ok}/{len(results)}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Grade agent tool-call traces (stream-JSON or JSONL) against a behavioral spec. "
                    "Exit 0 = every trace compliant, 1 = at least one not, 2 = usage, file or spec error.")
    parser.add_argument("spec", help="JSON spec with 'steps' (and optional 'forbidden')")
    parser.add_argument("traces", nargs="+", help="trace files: stream-JSON event output or JSONL tool calls")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("--main-only", action="store_true", help="ignore tool calls made inside subagents (stream-JSON only)")
    args = parser.parse_args(argv)
    try:
        spec = load_spec(args.spec)
    except SpecError as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2
    results = []
    for path in args.traces:
        try:
            events, skipped = load_trace(path, main_only=args.main_only)
        except OSError as exc:
            print(f"cannot read trace {path}: {exc.strerror}", file=sys.stderr)
            return 2
        result = grade(spec, events)
        result.update({"path": path, "events": len(events), "skipped_lines": skipped})
        results.append(result)
    if args.json:
        summary = {s.id: sum(1 for r in results for x in r["steps"] if x["id"] == s.id and x["passed"]) for s in spec["steps"]}
        print(json.dumps({"spec": spec["id"], "traces": results,
                          "summary": {"traces": len(results), "compliant_traces": sum(1 for r in results if r["compliant"]),
                                      "steps_passed": summary}}, indent=2))
    else:
        print(render_text(spec, results))
    return 0 if all(r["compliant"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
