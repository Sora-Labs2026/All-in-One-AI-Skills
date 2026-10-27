#!/usr/bin/env python3
"""ProductCraft ML Engineering: read-only leakage check across dataset splits.

Give it the CSV files of two or more splits (train, validation, test) and the
columns that matter. It reports:

  SCHEMA_MISMATCH   splits do not have the same columns
  ID_OVERLAP        the same row identifier appears in more than one split
  DUPLICATE_ID      an identifier repeats inside one split
  GROUP_OVERLAP     the same entity (patient, user, device, document) appears in
                    more than one split, so the model can memorize it
  TIME_OVERLAP      a later split contains timestamps at or before the end of
                    an earlier split (splits must be given oldest first)
  TIME_UNPARSED     timestamps that could not be read
  DUPLICATE_ROWS    rows whose feature values also appear in an earlier split
                    (features = every column except id, group, time, target
                    and --ignore columns)
  LABEL_CONFLICT    duplicated feature rows carry different labels
  TARGET_COPY       a column equals the target in nearly every row
  UNSEEN_CLASS      a class appears in a later split but not in the first one
  CLASS_BALANCE     per-split class shares (information)

Exit codes: 0 no WARN findings, 1 at least one WARN finding, 2 bad input.

A clean result does not prove the absence of leakage. It cannot see features
computed with future information, preprocessing fitted on all data, or near
duplicates. It reads only the files it is given, prints only column names,
counts and at most a few example identifiers (suppressed with --no-examples),
and never uses the network.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple

VERSION = "1.0.0"
MAX_EXAMPLES = 5
MAX_CLASSES = 50
TARGET_COPY_SHARE = 0.999
TARGET_COPY_MIN_ROWS = 20


class InputError(Exception):
    pass


def parse_time(text: str) -> Optional[float]:
    """Return a sortable number for an ISO date/datetime or a plain number."""
    value = text.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            dt = datetime.fromisoformat(value.replace(" ", "T", 1))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def iter_rows(path: str, delimiter: str) -> Tuple[List[str], Iterator[Dict[str, str]]]:
    try:
        handle = open(path, newline="", encoding="utf-8-sig")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror}") from None
    reader = csv.DictReader(handle, delimiter=delimiter)
    fields = list(reader.fieldnames or [])
    if not fields:
        handle.close()
        raise InputError(f"{path}: no header row")

    def gen() -> Iterator[Dict[str, str]]:
        try:
            for row in reader:
                yield row
        finally:
            handle.close()
    return fields, gen()


def digest(values: Sequence[str]) -> bytes:
    h = hashlib.sha1()
    for v in values:
        h.update(v.encode("utf-8", "surrogatepass"))
        h.update(b"\x1f")
    return h.digest()


class Finding:
    def __init__(self, severity: str, code: str, message: str, **data: object) -> None:
        self.severity, self.code, self.message, self.data = severity, code, message, data

    def as_dict(self) -> Dict[str, object]:
        out: Dict[str, object] = {"severity": self.severity, "code": self.code, "message": self.message}
        out.update(self.data)
        return out


def check(splits: List[Tuple[str, str]], id_col: Optional[str], group_col: Optional[str],
          time_col: Optional[str], target_col: Optional[str], ignore: Sequence[str],
          delimiter: str, examples: bool) -> Tuple[List[Finding], Dict[str, object]]:
    findings: List[Finding] = []
    summary: Dict[str, object] = {"splits": []}
    first_fields: Optional[List[str]] = None
    feature_cols: List[str] = []

    seen_ids: Dict[str, str] = {}
    seen_groups: Dict[str, str] = {}
    seen_rows: Dict[bytes, Tuple[str, str]] = {}
    max_time_so_far: Optional[float] = None
    max_time_split = ""
    first_classes: Optional[Set[str]] = None
    copy_equal: Dict[str, int] = {}
    copy_total = 0

    for name, path in splits:
        fields, rows = iter_rows(path, delimiter)
        for col, label in ((id_col, "--id"), (group_col, "--group"), (time_col, "--time"),
                           (target_col, "--target")):
            if col and col not in fields:
                raise InputError(f"{path}: column '{col}' given with {label} not found")
        if first_fields is None:
            first_fields = fields
            skip = {c for c in (id_col, group_col, time_col, target_col) if c} | set(ignore)
            feature_cols = [c for c in fields if c not in skip]
            if not feature_cols:
                raise InputError("no feature columns left after excluding id, group, time, target and "
                                 "ignored columns")
            copy_equal = {c: 0 for c in fields if c not in {target_col, id_col}} if target_col else {}
        elif set(fields) != set(first_fields):
            missing = sorted(set(first_fields) - set(fields))
            extra = sorted(set(fields) - set(first_fields))
            findings.append(Finding("WARN", "SCHEMA_MISMATCH",
                                    f"{name} columns differ from {splits[0][0]}",
                                    split=name, missing=missing, extra=extra))
        n_rows = 0
        id_hits: List[str] = []
        id_hit_count = 0
        group_hits: Set[str] = set()
        group_hit_rows = 0
        new_groups: Dict[str, str] = {}
        new_ids: Dict[str, str] = {}
        within_id_dups = 0
        time_overlap = 0
        unparsed = 0
        tmin: Optional[float] = None
        tmax: Optional[float] = None
        tmin_text = tmax_text = ""
        dup_rows = 0
        conflicts = 0
        within_dups = 0
        local_rows: Set[bytes] = set()
        new_rows: Dict[bytes, Tuple[str, str]] = {}
        classes: Dict[str, int] = {}
        for row in rows:
            n_rows += 1
            get = lambda c: (row.get(c) or "").strip()  # noqa: E731
            if id_col:
                rid = get(id_col)
                if rid:
                    if rid in seen_ids:
                        id_hit_count += 1
                        if len(id_hits) < MAX_EXAMPLES:
                            id_hits.append(rid)
                    elif rid in new_ids:
                        within_id_dups += 1
                    else:
                        new_ids[rid] = name
            if group_col:
                g = get(group_col)
                if g:
                    if g in seen_groups:
                        group_hits.add(g)
                        group_hit_rows += 1
                    else:
                        new_groups.setdefault(g, name)
            if time_col:
                raw_t = get(time_col)
                t = parse_time(raw_t)
                if t is None:
                    unparsed += 1
                else:
                    if tmin is None or t < tmin:
                        tmin, tmin_text = t, raw_t
                    if tmax is None or t > tmax:
                        tmax, tmax_text = t, raw_t
                    if max_time_so_far is not None and t <= max_time_so_far:
                        time_overlap += 1
            label = get(target_col) if target_col else ""
            if target_col:
                classes[label] = classes.get(label, 0) + 1
                copy_total += 1
                for c in copy_equal:
                    if get(c) == label:
                        copy_equal[c] += 1
            values = [get(c) for c in feature_cols]
            if any(values):
                d = digest(values)
                if d in local_rows:
                    within_dups += 1
                else:
                    local_rows.add(d)
                earlier = seen_rows.get(d)
                if earlier is not None:
                    dup_rows += 1
                    if target_col and earlier[1] != label:
                        conflicts += 1
                elif d not in new_rows:
                    new_rows[d] = (name, label)
        seen_groups.update(new_groups)
        seen_ids.update(new_ids)
        for d, info in new_rows.items():
            seen_rows.setdefault(d, info)
        split_info: Dict[str, object] = {"name": name, "rows": n_rows}
        if n_rows == 0:
            findings.append(Finding("WARN", "EMPTY_SPLIT", f"{name} has no rows", split=name))
        if id_hit_count:
            findings.append(Finding("WARN", "ID_OVERLAP",
                                    f"{id_hit_count} rows of {name} reuse an id from an earlier split",
                                    split=name, rows=id_hit_count,
                                    examples=id_hits if examples else []))
        if group_hits:
            ex = sorted(group_hits)[:MAX_EXAMPLES] if examples else []
            findings.append(Finding("WARN", "GROUP_OVERLAP",
                                    f"{len(group_hits)} {group_col} values in {name} also appear in an earlier "
                                    f"split ({group_hit_rows} rows); split by group instead",
                                    split=name, groups=len(group_hits), rows=group_hit_rows, examples=ex))
        if time_col:
            split_info["time_min"] = tmin_text or None
            split_info["time_max"] = tmax_text or None
            if unparsed:
                findings.append(Finding("WARN", "TIME_UNPARSED",
                                        f"{unparsed} rows of {name} have a missing or unreadable {time_col}",
                                        split=name, rows=unparsed))
            if time_overlap:
                findings.append(Finding("WARN", "TIME_OVERLAP",
                                        f"{time_overlap} rows of {name} are at or before the latest time in "
                                        f"{max_time_split}; later splits must start after earlier ones end",
                                        split=name, rows=time_overlap))
            if tmax is not None and (max_time_so_far is None or tmax > max_time_so_far):
                max_time_so_far = tmax
                max_time_split = name
        if dup_rows:
            findings.append(Finding("WARN", "DUPLICATE_ROWS",
                                    f"{dup_rows} rows of {name} have the same feature values as a row in an "
                                    f"earlier split", split=name, rows=dup_rows))
        if conflicts:
            findings.append(Finding("INFO", "LABEL_CONFLICT",
                                    f"{conflicts} of those duplicates carry a different {target_col}",
                                    split=name, rows=conflicts))
        if within_dups:
            split_info["duplicate_rows_within_split"] = within_dups
        if within_id_dups:
            findings.append(Finding("WARN", "DUPLICATE_ID",
                                    f"{within_id_dups} rows of {name} repeat an id already used in {name}",
                                    split=name, rows=within_id_dups))
        if target_col and n_rows:
            if len(classes) <= MAX_CLASSES:
                shares = {k: round(v / n_rows, 4) for k, v in sorted(classes.items())}
                split_info["class_shares"] = shares
                if first_classes is None:
                    first_classes = set(classes)
                else:
                    unseen = sorted(set(classes) - first_classes)
                    if unseen:
                        findings.append(Finding("WARN", "UNSEEN_CLASS",
                                                f"{name} has {len(unseen)} classes absent from {splits[0][0]}",
                                                split=name, classes=unseen[:MAX_EXAMPLES] if examples else []))
            else:
                split_info["distinct_targets"] = len(classes)
        summary["splits"].append(split_info)  # type: ignore[union-attr]

    if target_col and copy_total >= TARGET_COPY_MIN_ROWS:
        for c, eq in sorted(copy_equal.items()):
            if eq / copy_total >= TARGET_COPY_SHARE:
                findings.append(Finding("WARN", "TARGET_COPY",
                                        f"column '{c}' equals {target_col} in {eq} of {copy_total} rows; "
                                        f"it is probably the label or derived from it", column=c))
    summary["feature_columns"] = len(feature_cols)
    return findings, summary


def parse_split(text: str) -> Tuple[str, str]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("use NAME=PATH, for example train=data/train.csv")
    name, path = text.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("use NAME=PATH")
    return name, path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="split_check.py",
        description="Read-only leakage check across train/validation/test CSV files: id, group and "
                    "time overlap, duplicated rows, label copies and class balance.",
        epilog="Examples:\n"
               "  split_check.py --split train=train.csv --split test=test.csv --target churned\n"
               "  split_check.py --split train=a.csv --split valid=b.csv --split test=c.csv \\\n"
               "      --id order_id --group customer_id --time created_at --target fraud\n"
               "Give splits oldest first when using --time.\n"
               "Exit codes: 0 no warnings, 1 warnings found, 2 bad input.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    p.add_argument("--split", action="append", type=parse_split, required=True, metavar="NAME=PATH",
                   help="a split and its CSV file; repeat for each split (at least two)")
    p.add_argument("--id", dest="id_col", help="row identifier column")
    p.add_argument("--group", dest="group_col", help="entity column that must not cross splits")
    p.add_argument("--time", dest="time_col", help="timestamp column (ISO 8601 or numeric)")
    p.add_argument("--target", dest="target_col", help="label column")
    p.add_argument("--ignore", action="append", default=[], metavar="COL",
                   help="column to leave out of the duplicate check; repeatable")
    p.add_argument("--delimiter", default=",", help="CSV delimiter (default ',')")
    p.add_argument("--no-examples", action="store_true", help="do not print example ids or groups")
    p.add_argument("--json", action="store_true", help="print JSON")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if len(args.split) < 2:
        print("error: give at least two --split NAME=PATH", file=sys.stderr)
        return 2
    names = [n for n, _ in args.split]
    if len(set(names)) != len(names):
        print("error: split names must be unique", file=sys.stderr)
        return 2
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
    try:
        findings, summary = check(args.split, args.id_col, args.group_col, args.time_col,
                                  args.target_col, args.ignore, args.delimiter, not args.no_examples)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except csv.Error as exc:
        print(f"error: CSV parse failure: {exc}", file=sys.stderr)
        return 2
    warns = sum(1 for f in findings if f.severity == "WARN")
    if args.json:
        print(json.dumps({"version": VERSION, "summary": summary,
                          "findings": [f.as_dict() for f in findings], "warnings": warns},
                         indent=2, sort_keys=True))
    else:
        for s in summary["splits"]:  # type: ignore[union-attr]
            extra = ", ".join(f"{k}={v}" for k, v in s.items() if k not in {"name", "rows"})
            print(f"split {s['name']}: {s['rows']} rows" + (f" ({extra})" if extra else ""))
        for f in findings:
            line = f"{f.severity} {f.code}: {f.message}"
            ex = f.data.get("examples") or f.data.get("classes")
            if ex:
                line += " e.g. " + ", ".join(map(str, ex))
            print(line)
        print(f"{warns} warning(s). A clean result does not rule out leakage from features computed "
              f"with future data or preprocessing fitted on all rows.")
    return 1 if warns else 0


if __name__ == "__main__":
    sys.exit(main())
