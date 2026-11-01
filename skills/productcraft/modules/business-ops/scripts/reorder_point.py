#!/usr/bin/env python3
"""ProductCraft Business Ops: safety stock and reorder points from a demand history CSV.

Reads per-period demand by item (columns sku, period, quantity), fills missing
periods inside each item's history with zero demand, and reports per item:
mean and standard deviation of demand per period, coefficient of variation,
average demand interval (ADI) and squared coefficient of variation of non-zero
demand sizes (CV2) with the demand pattern they imply (smooth, erratic,
intermittent, lumpy), ABC class by value and XYZ class by variability, safety
stock, and either a reorder point (continuous review) or an order-up-to level
(periodic review). With a position file it computes the inventory position and
whether the item is at or below its reorder point, or how much to order at the
review.

Safety stock uses SS = z * sqrt(T * sd^2 + mean^2 * sd_L^2), where z sets the
cycle service level, T = lead time + review period and sd_L is the lead-time
standard deviation, all in periods. The normal approximation is unreliable for
intermittent or lumpy demand, short histories and items without positive
demand; those items carry warnings.

It reads local files only, never writes, never uses the network, and its output
is deterministic. Results are recommendations for a planner, not orders.

Exit codes: 0 report complete; 1 report complete, --strict given and at least
one warning; 2 usage or input error.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from statistics import NormalDist

VERSION = "1.0.0"
ADI_CUTOFF = 1.32   # Syntetos-Boylan classification cut-offs
CV2_CUTOFF = 0.49
MAX_LISTED_ROWS = 5


class InputError(Exception):
    """A problem with the input files or arguments; exit code 2."""


def parse_number(text, what, allow_negative=True):
    value = (text or "").strip()
    if value == "":
        raise ValueError(f"{what} is empty")
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"{what} is not a number: {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"{what} is not finite: {value!r}")
    if not allow_negative and number < 0:
        raise ValueError(f"{what} must not be negative: {value!r}")
    return number


def pair(text, name):
    try:
        low, high = (float(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{name} must be two numbers separated by a comma") from None
    return low, high


def open_rows(path, delimiter):
    try:
        handle = open(path, newline="", encoding="utf-8-sig")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
    with handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise InputError(f"{path} is empty")
        names = [(name or "").strip().lower() for name in reader.fieldnames]
        rows = []
        for raw in reader:
            row = {}
            for key, value in raw.items():
                if key is None:
                    continue
                row[(key or "").strip().lower()] = value if isinstance(value, str) else ""
            rows.append((reader.line_num, row))
    return names, rows


def read_demand(path, delimiter):
    names, rows = open_rows(path, delimiter)
    missing = [c for c in ("sku", "period", "quantity") if c not in names]
    if missing:
        raise InputError(f"{path} is missing column(s): {', '.join(missing)}")
    demand = {}
    bad_rows = []
    negative_rows = 0
    for line, row in rows:
        sku = (row.get("sku") or "").strip()
        period = (row.get("period") or "").strip()
        try:
            if not sku or not period:
                raise ValueError("sku or period is empty")
            qty = parse_number(row.get("quantity"), "quantity")
        except ValueError:
            bad_rows.append(line)
            continue
        if qty < 0:
            negative_rows += 1
        per_sku = demand.setdefault(sku, {})
        per_sku[period] = per_sku.get(period, 0.0) + qty
    if not demand:
        raise InputError(f"{path} has no valid demand rows")
    return demand, bad_rows, negative_rows, len(rows)


PARAM_FIELDS = ("lead_time", "lead_time_sd", "service_level", "review_period", "unit_cost")


def read_params(path, delimiter):
    names, rows = open_rows(path, delimiter)
    if "sku" not in names:
        raise InputError(f"{path} is missing column: sku")
    params = {}
    for line, row in rows:
        sku = (row.get("sku") or "").strip()
        if not sku:
            raise InputError(f"{path} line {line}: sku is empty")
        entry = {}
        for field in PARAM_FIELDS:
            value = (row.get(field) or "").strip()
            if value == "":
                continue
            try:
                number = parse_number(value, field, allow_negative=False)
            except ValueError as exc:
                raise InputError(f"{path} line {line}: {exc}") from None
            if field == "service_level" and not 0.5 <= number < 1:
                raise InputError(f"{path} line {line}: service_level must be at least 0.5 and below 1")
            entry[field] = number
        params[sku] = entry
    return params


POSITION_FIELDS = ("on_hand", "on_order", "backorders", "committed")


def read_position(path, delimiter):
    names, rows = open_rows(path, delimiter)
    if "sku" not in names:
        raise InputError(f"{path} is missing column: sku")
    if not any(field in names for field in POSITION_FIELDS):
        raise InputError(f"{path} needs at least one of: {', '.join(POSITION_FIELDS)}")
    positions = {}
    for line, row in rows:
        sku = (row.get("sku") or "").strip()
        if not sku:
            raise InputError(f"{path} line {line}: sku is empty")
        values = {}
        for field in POSITION_FIELDS:
            value = (row.get(field) or "").strip()
            if value == "":
                values[field] = 0.0
                continue
            try:
                values[field] = parse_number(value, field)
            except ValueError as exc:
                raise InputError(f"{path} line {line}: {exc}") from None
        positions[sku] = values
    return positions


def classify_pattern(adi, cv2):
    if adi is None:
        return "no demand"
    if adi < ADI_CUTOFF:
        return "smooth" if cv2 < CV2_CUTOFF else "erratic"
    return "intermittent" if cv2 < CV2_CUTOFF else "lumpy"


def series_for(per_sku, all_periods):
    """Demand per period from the item's first period through the last period in the file."""
    first = min(per_sku)
    start = all_periods.index(first)
    window = all_periods[start:]
    filled = sum(1 for p in window if p not in per_sku)
    return [per_sku.get(p, 0.0) for p in window], filled


def demand_stats(values):
    n = len(values)
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n >= 2 else 0.0
    cv = sd / mean if mean > 0 else None
    nonzero = [v for v in values if v > 0]
    if nonzero:
        adi = n / len(nonzero)
        if len(nonzero) >= 2:
            nz_mean = statistics.fmean(nonzero)
            cv2 = (statistics.stdev(nonzero) / nz_mean) ** 2
        else:
            cv2 = 0.0
    else:
        adi, cv2 = None, None
    return {"periods": n, "total": sum(values), "mean": mean, "sd": sd, "cv": cv,
            "nonzero_periods": len(nonzero), "adi": adi, "cv2": cv2}


def assign_abc(items, cuts, basis):
    """Class A/B/C by cumulative share of value, ranked descending; the share before an item decides its class."""
    key = "value" if basis == "value" else "total"
    total = sum(max(item[key], 0.0) for item in items)
    if total <= 0:
        for item in items:
            item["abc"] = None
        return False
    ranked = sorted(items, key=lambda it: (-it[key], it["sku"]))
    running = 0.0
    for item in ranked:
        share_before = running / total
        item["abc"] = "A" if share_before < cuts[0] else "B" if share_before < cuts[1] else "C"
        running += max(item[key], 0.0)
    return True


def assign_xyz(cv, cuts):
    if cv is None:
        return None
    return "X" if cv < cuts[0] else "Y" if cv < cuts[1] else "Z"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="reorder_point.py",
        description="Safety stock, reorder points and item segmentation from a demand CSV "
                    "(columns sku, period, quantity). Read-only and offline.",
        epilog="Lead time, its standard deviation and the review period are in the same "
               "periods as the demand file. Period labels must sort in time order "
               "(ISO dates or weeks). Exit codes: 0 complete, 1 warnings with --strict, 2 usage or input error.")
    parser.add_argument("demand", help="demand CSV with columns sku, period, quantity")
    parser.add_argument("--params", help="optional CSV: sku plus lead_time, lead_time_sd, service_level, review_period, unit_cost")
    parser.add_argument("--position", help="optional CSV: sku plus on_hand, on_order, backorders, committed")
    parser.add_argument("--lead-time", type=float, help="default lead time in periods")
    parser.add_argument("--lead-time-sd", type=float, default=0.0, help="default lead-time standard deviation in periods (default 0)")
    parser.add_argument("--review-period", type=float, default=0.0,
                        help="default review period in periods; 0 means continuous review (default 0)")
    parser.add_argument("--service-level", type=float, default=0.95,
                        help="default cycle service level, at least 0.5 and below 1 (default 0.95)")
    parser.add_argument("--abc", type=lambda t: pair(t, "--abc"), default=(0.8, 0.95),
                        help="cumulative value cut-offs for A and B (default 0.8,0.95)")
    parser.add_argument("--xyz", type=lambda t: pair(t, "--xyz"), default=(0.5, 1.0),
                        help="coefficient-of-variation cut-offs for X and Y (default 0.5,1.0)")
    parser.add_argument("--min-periods", type=int, default=12, help="warn when an item has fewer periods (default 12)")
    parser.add_argument("--delimiter", default=",", help="field delimiter for all input files (default ,)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a text table")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any warning is raised")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def validate_args(parser, args):
    if args.lead_time is not None and (not math.isfinite(args.lead_time) or args.lead_time < 0):
        parser.error("--lead-time must be a non-negative number")
    for name in ("lead_time_sd", "review_period"):
        value = getattr(args, name)
        if not math.isfinite(value) or value < 0:
            parser.error(f"--{name.replace('_', '-')} must be a non-negative number")
    if not 0.5 <= args.service_level < 1:
        parser.error("--service-level must be at least 0.5 and below 1")
    a, b = args.abc
    if not 0 < a < b <= 1:
        parser.error("--abc needs 0 < A < B <= 1")
    x, y = args.xyz
    if not 0 < x < y:
        parser.error("--xyz needs 0 < X < Y")
    if args.min_periods < 1:
        parser.error("--min-periods must be at least 1")
    if len(args.delimiter) != 1:
        parser.error("--delimiter must be a single character")


def rounded(value, digits=3):
    if value is None:
        return None
    result = round(value, digits)
    return 0.0 if result == 0 else result


def analyse(args):
    demand, bad_rows, negative_rows, row_count = read_demand(args.demand, args.delimiter)
    params = read_params(args.params, args.delimiter) if args.params else {}
    positions = read_position(args.position, args.delimiter) if args.position else {}

    warnings = []
    all_periods = sorted({p for per_sku in demand.values() for p in per_sku})
    if len({len(p) for p in all_periods}) > 1:
        warnings.append("period labels have different lengths; check that they sort in time order")
    if bad_rows:
        listed = ", ".join(str(n) for n in bad_rows[:MAX_LISTED_ROWS])
        more = "" if len(bad_rows) <= MAX_LISTED_ROWS else f" and {len(bad_rows) - MAX_LISTED_ROWS} more"
        warnings.append(f"{len(bad_rows)} demand row(s) skipped (empty sku or period, or quantity not a number): line {listed}{more}")
    if negative_rows:
        warnings.append(f"{negative_rows} demand row(s) have negative quantities (returns netted into demand?)")
    unknown = sorted(set(params) - set(demand))
    if unknown:
        warnings.append(f"{len(unknown)} sku(s) in --params have no demand rows")
    unknown = sorted(set(positions) - set(demand))
    if unknown:
        warnings.append(f"{len(unknown)} sku(s) in --position have no demand rows")

    with_cost = [sku for sku in demand if "unit_cost" in params.get(sku, {})]
    if with_cost and len(with_cost) == len(demand):
        abc_basis = "value"
    else:
        abc_basis = "quantity"
        if with_cost:
            warnings.append("unit_cost is missing for some sku(s); ABC uses quantity for all items")

    items = []
    for sku in sorted(demand):
        values, filled = series_for(demand[sku], all_periods)
        stats = demand_stats(values)
        p = params.get(sku, {})
        lead_time = p.get("lead_time", args.lead_time)
        lead_time_sd = p.get("lead_time_sd", args.lead_time_sd)
        review = p.get("review_period", args.review_period)
        service = p.get("service_level", args.service_level)
        item = {"sku": sku, **stats, "filled_zero_periods": filled,
                "pattern": classify_pattern(stats["adi"], stats["cv2"]),
                "xyz": assign_xyz(stats["cv"], args.xyz),
                "unit_cost": p.get("unit_cost"),
                "value": stats["total"] * p["unit_cost"] if "unit_cost" in p else None,
                "lead_time": lead_time, "lead_time_sd": lead_time_sd, "review_period": review,
                "policy": "periodic" if review > 0 else "continuous",
                "service_level": service, "z": NormalDist().inv_cdf(service),
                "safety_stock": None, "reorder_point": None, "order_up_to": None,
                "inventory_position": None, "reorder_now": None, "suggested_order": None,
                "warnings": []}
        notes = item["warnings"]
        if stats["periods"] < args.min_periods:
            notes.append(f"short history: {stats['periods']} period(s), fewer than {args.min_periods}")
        if item["pattern"] in ("intermittent", "lumpy"):
            notes.append(f"{item['pattern']} demand: the normal approximation is unreliable; "
                         "use a Croston-type forecast or an empirical lead-time demand distribution")
        elif item["pattern"] == "erratic":
            notes.append("erratic demand sizes: check for outliers, promotions or stockouts in the history")
        if stats["mean"] <= 0:
            notes.append("no positive mean demand; safety stock not meaningful")
        if lead_time is None:
            notes.append("no lead time given (--lead-time or params lead_time); safety stock not computed")
        else:
            protection = lead_time + review
            ss = item["z"] * math.sqrt(protection * stats["sd"] ** 2 + stats["mean"] ** 2 * lead_time_sd ** 2)
            item["safety_stock"] = ss
            if review > 0:
                item["order_up_to"] = stats["mean"] * protection + ss
            else:
                item["reorder_point"] = stats["mean"] * lead_time + ss
            if sku in positions:
                pos = positions[sku]
                ip = pos["on_hand"] + pos["on_order"] - pos["backorders"] - pos["committed"]
                item["inventory_position"] = ip
                if review > 0:
                    item["suggested_order"] = max(0.0, item["order_up_to"] - ip)
                else:
                    item["reorder_now"] = ip <= item["reorder_point"]
        if positions and sku not in positions:
            notes.append("no row in --position")
        items.append(item)

    if not assign_abc(items, args.abc, abc_basis):
        warnings.append("total demand is not positive; ABC classes not assigned")

    for item in items:
        for key in ("mean", "sd", "cv", "adi", "cv2", "total", "value", "z", "safety_stock",
                    "reorder_point", "order_up_to", "inventory_position", "suggested_order"):
            item[key] = rounded(item[key])

    settings = {"demand_rows": row_count, "items": len(items), "periods_in_file": len(all_periods),
                "first_period": all_periods[0], "last_period": all_periods[-1],
                "abc_basis": abc_basis, "abc_cutoffs": list(args.abc), "xyz_cutoffs": list(args.xyz),
                "adi_cutoff": ADI_CUTOFF, "cv2_cutoff": CV2_CUTOFF,
                "service_level_meaning": "cycle service level (probability of no stockout per replenishment cycle)"}
    return {"version": VERSION, "settings": settings, "items": items, "warnings": warnings}


def fmt(value, digits=2):
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_text(report):
    s = report["settings"]
    lines = [f"reorder_point {report['version']}: {s['items']} item(s), {s['periods_in_file']} period(s) "
             f"from {s['first_period']} to {s['last_period']}; ABC by {s['abc_basis']}; "
             "service level = cycle service level",
             ""]
    header = ["sku", "n", "mean", "sd", "cv", "pattern", "abc", "xyz", "lt", "sl", "ss", "rop/S", "ip", "action"]
    table = [header]
    for it in report["items"]:
        level = it["reorder_point"] if it["policy"] == "continuous" else it["order_up_to"]
        if it["reorder_now"] is not None:
            action = "reorder" if it["reorder_now"] else "ok"
        elif it["suggested_order"] is not None:
            action = f"order {fmt(it['suggested_order'])}"
        else:
            action = "-"
        table.append([it["sku"], str(it["periods"]), fmt(it["mean"]), fmt(it["sd"]), fmt(it["cv"]),
                      it["pattern"], fmt(it["abc"]), fmt(it["xyz"]), fmt(it["lead_time"]),
                      fmt(it["service_level"], 3), fmt(it["safety_stock"]), fmt(level),
                      fmt(it["inventory_position"]), action])
    widths = [max(len(row[i]) for row in table) for i in range(len(header))]
    for row in table:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    item_notes = [(it["sku"], note) for it in report["items"] for note in it["warnings"]]
    if report["warnings"] or item_notes:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {w}" for w in report["warnings"])
        lines.extend(f"- {sku}: {note}" for sku, note in item_notes)
    return "\n".join(lines)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)
    try:
        report = analyse(args)
    except InputError as exc:
        print(f"reorder_point.py: error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    has_warnings = bool(report["warnings"]) or any(it["warnings"] for it in report["items"])
    return 1 if args.strict and has_warnings else 0


if __name__ == "__main__":
    sys.exit(main())
