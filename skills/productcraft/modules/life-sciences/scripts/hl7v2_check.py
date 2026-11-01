#!/usr/bin/env python3
"""ProductCraft HL7 version 2 message checker. Offline, read-only, deterministic, standard library only.

Reads files of HL7 v2 messages (plain, one segment per line, or MLLP-framed captures)
and reports structural problems that break interfaces, without printing any field
value. Message content is usually protected health information, so output names
only rule IDs, message numbers, segment positions and field numbers, plus message
types, trigger events and version IDs.

Rules (error = the receiver will likely reject or misread the message):

  MSH-FIRST           error  message does not start with an MSH segment
  ENCODING-CHARS      error  MSH-1 or MSH-2 delimiters missing, repeated or alphanumeric
  MSH-REQUIRED        error  MSH-9 message type, MSH-10 control ID or MSH-12 version empty
  SEGMENT-ID          error  segment name is not three upper-case letters or digits
  TS-FORMAT           error  MSH-7, EVN-2, PID-7, OBR-7 or OBX-14 is not an HL7 date/time
  OBX-VALUE-TYPE      error  OBX-5 has a value but OBX-2 (value type) is empty
  OBX-NM-NUMERIC      error  OBX-2 is NM but a repetition of OBX-5 is not a number
  CONTROL-ID-DUP      warn   MSH-10 repeats within the input (receivers deduplicate on it)
  MSH-RECOMMENDED     warn   MSH-7 date/time or MSH-11 processing ID empty
  MSG-TYPE-FORMAT     warn   MSH-9 lacks a three-letter code or a trigger event
  PID-MISSING         warn   patient-centred message type without a PID segment
  PID3-AUTHORITY      warn   a PID-3 identifier has no assigning authority (PID-3.4)
  OBX-UNITS           warn   numeric OBX without units in OBX-6
  OBX-STATUS          warn   OBX-11 result status empty
  ESCAPE-SEQUENCE     warn   escape character starts a sequence HL7 does not define
  PROCESSING-MIXED    warn   one input mixes processing IDs (for example P and T)
  NON-ASCII-NO-CHARSET warn  non-ASCII bytes present but MSH-18 character set empty
  TS-NO-OFFSET        info   time-of-day values without a UTC offset (sender local time); counted
  LF-TERMINATORS      info   segments end with LF; the standard terminator is CR
  Z-SEGMENT           info   site-specific Z segments present; counted

A clean run means the structure looks sound, not that the interface specification
is met or that codes, units and values are right.

Exit codes: 0 no errors (and no warnings with --strict); 1 errors, or warnings with
--strict; 2 usage error, unreadable input or no messages found.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

VERSION = "1.0.0"
LEVELS = ("error", "warn", "info")
RULES = {
    "MSH-FIRST": "error", "ENCODING-CHARS": "error", "MSH-REQUIRED": "error", "SEGMENT-ID": "error",
    "TS-FORMAT": "error", "OBX-VALUE-TYPE": "error", "OBX-NM-NUMERIC": "error",
    "CONTROL-ID-DUP": "warn", "MSH-RECOMMENDED": "warn", "MSG-TYPE-FORMAT": "warn", "PID-MISSING": "warn",
    "PID3-AUTHORITY": "warn", "OBX-UNITS": "warn", "OBX-STATUS": "warn", "ESCAPE-SEQUENCE": "warn",
    "PROCESSING-MIXED": "warn", "NON-ASCII-NO-CHARSET": "warn",
    "TS-NO-OFFSET": "info", "LF-TERMINATORS": "info", "Z-SEGMENT": "info",
}
AGGREGATE = {"TS-NO-OFFSET", "Z-SEGMENT"}
PATIENT_TYPES = {"ADT", "ORU", "ORM", "OML", "OUL", "SIU", "MDM", "VXU", "RDE", "RAS", "DFT", "BAR", "PPR", "REF"}
TS_FIELDS = {"EVN": (2,), "PID": (7,), "OBR": (7,), "OBX": (14,)}
TS_RE = re.compile(r"^\d{4}(?:\d{2}(?:\d{2}(?:\d{2}(?:\d{2}(?:\d{2}(?:\.\d{1,4})?)?)?)?)?)?(?:[+-]\d{4})?$")
SEG_RE = re.compile(r"^[A-Z][A-Z0-9]{2}$")
NM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
ESCAPE_OK = re.compile(r"^(?:[FSTRE]|H|N|X[0-9A-Fa-f]*|Z[^\\]*|C[0-9A-Fa-f]{4}|M[0-9A-Fa-f]{4,6}|\.[a-z]{2}[^\\]*)$")


class Message:
    def __init__(self, index: int, segments: list[str]):
        self.index = index
        self.segments = segments
        self.field_sep = "|"
        self.comp_sep = "^"
        self.rep_sep = "~"
        self.esc = "\\"
        self.sub_sep = "&"
        self.msh: list[str] = []


def split_messages(raw: bytes) -> tuple[list[Message], dict]:
    """Split input into messages; return them plus input-level facts (terminators, non-ASCII)."""
    facts = {"lf_only": False, "non_ascii": any(b > 0x7F for b in raw)}
    text = raw.replace(b"\x0b", b"").replace(b"\x1c", b"").decode("utf-8", errors="replace")
    if "\n" in text and "\r" not in text:
        facts["lf_only"] = True
    lines = [ln for ln in re.split(r"\r\n|\r|\n", text) if ln.strip()]
    messages: list[Message] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("MSH") and current:
            messages.append(Message(len(messages) + 1, current))
            current = []
        current.append(line)
    if current:
        messages.append(Message(len(messages) + 1, current))
    return messages, facts


def _msh_field(msg: Message, n: int) -> str:
    # MSH-1 is the field separator itself, so split index i holds MSH-(i+1).
    if n == 1:
        return msg.field_sep
    idx = n - 1
    return msg.msh[idx] if idx < len(msg.msh) else ""


def _field(parts: list[str], n: int) -> str:
    return parts[n] if n < len(parts) else ""


def _comp(value: str, msg: Message, n: int) -> str:
    comps = value.split(msg.comp_sep)
    return comps[n - 1] if n - 1 < len(comps) else ""


def check_message(msg: Message, add) -> dict:
    info = {"type": "", "event": "", "version": "", "processing": "", "control_id": None}
    first = msg.segments[0]
    if not first.startswith("MSH"):
        add("MSH-FIRST", msg.index, 1, None)
        return info
    if len(first) < 8:
        add("ENCODING-CHARS", msg.index, 1, 2)
        return info
    msg.field_sep = first[3]
    enc = first[4:].split(msg.field_sep, 1)[0]
    if len(enc) < 4 or len(set(enc + msg.field_sep)) != len(enc) + 1 or any(c.isalnum() or c.isspace() for c in enc + msg.field_sep):
        add("ENCODING-CHARS", msg.index, 1, 2)
        return info
    msg.comp_sep, msg.rep_sep, msg.esc, msg.sub_sep = enc[0], enc[1], enc[2], enc[3]
    msg.msh = first.split(msg.field_sep)
    msh9 = _msh_field(msg, 9)
    info["type"] = _comp(msh9, msg, 1)
    info["event"] = _comp(msh9, msg, 2)
    info["version"] = _comp(_msh_field(msg, 12), msg, 1)
    info["processing"] = _comp(_msh_field(msg, 11), msg, 1)
    control = _msh_field(msg, 10)
    info["control_id"] = (_comp(_msh_field(msg, 4), msg, 1), control) if control else None
    for n in (9, 10, 12):
        if not _msh_field(msg, n).strip():
            add("MSH-REQUIRED", msg.index, 1, n)
    for n in (7, 11):
        if not _msh_field(msg, n).strip():
            add("MSH-RECOMMENDED", msg.index, 1, n)
    if msh9 and (not re.fullmatch(r"[A-Z]{3}", info["type"] or "") or not info["event"]):
        add("MSG-TYPE-FORMAT", msg.index, 1, 9)
    ts = _comp(_msh_field(msg, 7), msg, 1)
    _check_ts(ts, msg.index, 1, 7, add)

    seg_names = []
    for pos, seg in enumerate(msg.segments, start=1):
        name = seg[:3]
        seg_names.append(name)
        if not SEG_RE.match(name) or (len(seg) > 3 and seg[3] != msg.field_sep):
            add("SEGMENT-ID", msg.index, pos, None)
            continue
        if name.startswith("Z"):
            add("Z-SEGMENT", msg.index, pos, None)
        _check_escapes(seg, msg, pos, add)
        if pos == 1:
            continue
        parts = seg.split(msg.field_sep)
        for n in TS_FIELDS.get(name, ()):
            for rep in _field(parts, n).split(msg.rep_sep):
                _check_ts(_comp(rep, msg, 1), msg.index, pos, n, add, date_only_ok=(name == "PID"))
        if name == "PID":
            for rep in _field(parts, 3).split(msg.rep_sep):
                if rep.strip() and not _comp(rep, msg, 4).strip():
                    add("PID3-AUTHORITY", msg.index, pos, 3)
                    break
        if name == "OBX":
            vtype, value = _field(parts, 2).strip(), _field(parts, 5)
            if value.strip() and not vtype:
                add("OBX-VALUE-TYPE", msg.index, pos, 2)
            if vtype == "NM":
                for rep in value.split(msg.rep_sep):
                    if rep.strip() and rep.strip() != '""' and not NM_RE.match(rep.strip()):
                        add("OBX-NM-NUMERIC", msg.index, pos, 5)
                        break
                if value.strip() and not _field(parts, 6).strip():
                    add("OBX-UNITS", msg.index, pos, 6)
            if value.strip() and not _field(parts, 11).strip():
                add("OBX-STATUS", msg.index, pos, 11)
    if info["type"] in PATIENT_TYPES and "PID" not in seg_names:
        add("PID-MISSING", msg.index, None, None)
    info["segments"] = seg_names
    info["charset"] = _msh_field(msg, 18).strip()
    return info


def _check_ts(value: str, msg_index: int, pos: int, field: int, add, date_only_ok: bool = False) -> None:
    value = value.strip()
    if not value or value == '""':
        return
    if not TS_RE.match(value):
        add("TS-FORMAT", msg_index, pos, field)
        return
    digits = re.match(r"^\d+", value).group(0)
    if len(digits) >= 10 and not re.search(r"[+-]\d{4}$", value) and not date_only_ok:
        add("TS-NO-OFFSET", msg_index, pos, field)


def _check_escapes(seg: str, msg: Message, pos: int, add) -> None:
    esc = msg.esc
    if pos == 1:
        # Skip MSH-2, which holds the escape character itself.
        head, _, rest = seg[4:].partition(msg.field_sep)
        seg = rest
    if esc not in seg:
        return
    pieces = seg.split(esc)
    # Escape sequences sit between pairs of escape characters: odd-indexed pieces.
    if len(pieces) % 2 == 0:
        add("ESCAPE-SEQUENCE", msg.index, pos, None)
        return
    for body in pieces[1::2]:
        if not ESCAPE_OK.match(body):
            add("ESCAPE-SEQUENCE", msg.index, pos, None)
            return


def check_inputs(paths: list[Path]) -> dict:
    findings: list[dict] = []
    seen_keys = set()

    aggregated: dict = {}

    def add(rule, msg_index, segment, field, source=None):
        if rule in AGGREGATE:
            # Frequent informational rules: one finding per input, first location plus a count.
            entry = aggregated.get((rule, source))
            if entry:
                entry["count"] += 1
                return
            entry = {"rule": rule, "level": RULES[rule], "input": source, "message": msg_index, "segment": segment, "field": field, "count": 1}
            aggregated[(rule, source)] = entry
            findings.append(entry)
            return
        key = (rule, source, msg_index, segment, field)
        if key in seen_keys:
            return
        seen_keys.add(key)
        findings.append({"rule": rule, "level": RULES[rule], "input": source, "message": msg_index, "segment": segment, "field": field, "count": 1})

    summary = {"inputs": 0, "messages": 0, "types": Counter(), "versions": Counter(), "processing": Counter(), "segments": Counter()}
    for path in paths:
        raw = path.read_bytes()
        source = path.name if len(paths) > 1 else None
        messages, facts = split_messages(raw)
        summary["inputs"] += 1
        summary["messages"] += len(messages)
        if facts["lf_only"] and messages:
            add("LF-TERMINATORS", None, None, None, source)
        controls = Counter()
        processing = set()
        any_charset = False

        def add_here(rule, msg_index, segment, field, _src=source):
            add(rule, msg_index, segment, field, _src)

        for msg in messages:
            info = check_message(msg, add_here)
            if info.get("type"):
                summary["types"][f"{info['type']}^{info['event'] or '?'}"] += 1
            if info.get("version"):
                summary["versions"][info["version"]] += 1
            if info.get("processing"):
                summary["processing"][info["processing"]] += 1
                processing.add(info["processing"])
            for name in info.get("segments", []):
                summary["segments"][name] += 1
            if info.get("charset"):
                any_charset = True
            if info.get("control_id"):
                controls[info["control_id"]] += 1
                if controls[info["control_id"]] == 2:
                    add("CONTROL-ID-DUP", msg.index, 1, 10, source)
        if len(processing) > 1:
            add("PROCESSING-MIXED", None, 1, 11, source)
        if facts["non_ascii"] and not any_charset:
            add("NON-ASCII-NO-CHARSET", None, 1, 18, source)
    order = {lvl: i for i, lvl in enumerate(LEVELS)}
    findings.sort(key=lambda f: (order[f["level"]], f["input"] or "", f["message"] or 0, f["segment"] or 0, f["field"] or 0, f["rule"]))
    counts = {lvl: sum(1 for f in findings if f["level"] == lvl) for lvl in LEVELS}
    return {
        "version": VERSION,
        "summary": {k: (dict(sorted(v.items())) if isinstance(v, Counter) else v) for k, v in summary.items()},
        "counts": counts,
        "findings": findings,
    }


def _where(f: dict) -> str:
    parts = []
    if f["input"]:
        parts.append(f["input"])
    if f["message"]:
        parts.append(f"message {f['message']}")
    if f["segment"]:
        parts.append(f"segment {f['segment']}")
    if f["field"]:
        parts.append(f"field {f['field']}")
    return ", ".join(parts) or "input"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hl7v2_check.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="files with one or more HL7 v2 messages")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings as well as errors")
    parser.add_argument("--min-level", choices=LEVELS, default="info", help="hide findings below this level")
    parser.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    parser.add_argument("--version", action="version", version=VERSION)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if args.list_rules:
        for rule, level in RULES.items():
            print(f"{rule:<21} {level}")
        return 0
    if not args.paths:
        print("error: give at least one file", file=sys.stderr)
        return 2
    paths = []
    for p in args.paths:
        path = Path(p)
        if not path.is_file():
            print(f"error: not a readable file: {p}", file=sys.stderr)
            return 2
        paths.append(path)
    try:
        report = check_inputs(paths)
    except OSError as exc:
        print(f"error: {exc.strerror}", file=sys.stderr)
        return 2
    if report["summary"]["messages"] == 0:
        print("error: no HL7 v2 messages found", file=sys.stderr)
        return 2
    cutoff = LEVELS.index(args.min_level)
    shown = [f for f in report["findings"] if LEVELS.index(f["level"]) <= cutoff]
    if args.json:
        print(json.dumps({**report, "findings": shown}, indent=2, sort_keys=True))
    else:
        s = report["summary"]
        print(f"inputs {s['inputs']}, messages {s['messages']}")
        print("types: " + (", ".join(f"{k} x{v}" for k, v in s["types"].items()) or "none"))
        print("versions: " + (", ".join(f"{k} x{v}" for k, v in s["versions"].items()) or "none"))
        for f in shown:
            more = f" (first of {f['count']})" if f["count"] > 1 else ""
            print(f"{f['level'].upper():<5} {f['rule']:<21} {_where(f)}{more}")
        c = report["counts"]
        print(f"errors {c['error']}, warnings {c['warn']}, info {c['info']}; no field values printed")
    c = report["counts"]
    return 1 if c["error"] or (args.strict and c["warn"]) else 0


if __name__ == "__main__":
    sys.exit(main())
