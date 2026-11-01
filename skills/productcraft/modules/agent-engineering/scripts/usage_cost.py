#!/usr/bin/env python3
"""ProductCraft Agent Engineering: token and cost report from LLM usage logs.

Reads JSON Lines usage records (one API call or one session snapshot per line)
and reports tokens by category, the prompt-cache hit rate and, with a price
table you supply, cost by model, day and session, the cost the same traffic
would have had without caching, and whether a budget was exceeded.

Two token-counter conventions are recognized per record:
  * separate counters: input_tokens is the uncached input, with
    cache_creation_input_tokens / cache_write_tokens and
    cache_read_input_tokens / cache_read_tokens beside it;
  * subset counters: prompt_tokens with prompt_tokens_details.cached_tokens,
    or input_tokens with input_tokens_details.cached_tokens, where the cached
    tokens are part of the input total.
Token fields may sit at the top level or inside a "usage" object. Use
--input-includes-cache for normalized logs whose input_tokens already include
the cache counters. Use --cumulative when each line is a running total for a
session (only the latest line per session counts).

No prices are built in: they change, so you keep a dated price file. Models
without a price are reported as unpriced and never guessed. The script reads
only numeric and identifying fields, never prompt text, is read-only and never
touches the network.

Exit codes: 0 report produced (and within --budget), 1 budget exceeded or not
verifiable (unpriced usage), 2 bad input (unreadable file, invalid price file,
no usable records).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"
Q = Decimal("0.000001")
CATEGORIES = ("ordinary", "cache_write", "cache_read", "output")


class InputError(Exception):
    pass


def as_count(value: Any) -> Optional[int]:
    """A non-negative integer token count, None when absent, ValueError when invalid."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("token count is not a number")
    if isinstance(value, float):
        if not math.isfinite(value) or value != int(value):
            raise ValueError("token count is not a whole number")
        value = int(value)
    if value < 0:
        raise ValueError("negative token count")
    return value


def first(d: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return None


TOKEN_KEYS = ("input_tokens", "output_tokens", "prompt_tokens", "completion_tokens",
              "cache_creation_input_tokens", "cache_read_input_tokens", "cache_write_tokens", "cache_read_tokens")


def extract_tokens(rec: Dict[str, Any], input_includes_cache: bool) -> Dict[str, int]:
    usage = rec.get("usage") if isinstance(rec.get("usage"), dict) else {}
    u = dict(rec)
    u.update(usage)
    if not any(u.get(k) is not None for k in TOKEN_KEYS):
        raise ValueError("no token counters")
    out = as_count(first(u, "output_tokens", "completion_tokens")) or 0
    if "prompt_tokens" in u and u["prompt_tokens"] is not None:
        total = as_count(u["prompt_tokens"]) or 0
        details = u.get("prompt_tokens_details") if isinstance(u.get("prompt_tokens_details"), dict) else {}
        read = as_count(details.get("cached_tokens")) or 0
        write = 0
        ordinary = total - read
    elif isinstance(u.get("input_tokens_details"), dict):
        total = as_count(u.get("input_tokens")) or 0
        read = as_count(u["input_tokens_details"].get("cached_tokens")) or 0
        write = 0
        ordinary = total - read
    else:
        base = as_count(u.get("input_tokens")) or 0
        write = as_count(first(u, "cache_creation_input_tokens", "cache_write_tokens")) or 0
        read = as_count(first(u, "cache_read_input_tokens", "cache_read_tokens")) or 0
        ordinary = base - write - read if input_includes_cache else base
    if ordinary < 0:
        raise ValueError("cached tokens exceed the input total")
    return {"ordinary": ordinary, "cache_write": write, "cache_read": read, "output": out}


def day_of(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        seconds = value / 1000.0 if value > 1e11 else value  # milliseconds or seconds since the epoch
        return _dt.datetime.fromtimestamp(seconds, tz=_dt.timezone.utc).strftime("%Y-%m-%d")
    if isinstance(value, str) and len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return value[:10]
    return "(unknown)"


def recorded_cost(rec: Dict[str, Any]) -> Optional[Decimal]:
    value = first(rec, "cost_usd", "estimated_cost_usd", "cost")
    if value is None or isinstance(value, bool):
        return None
    try:
        dec = Decimal(str(value))
    except InvalidOperation:
        return None
    return dec if dec.is_finite() and dec >= 0 else None


def read_records(paths: List[str], input_includes_cache: bool) -> Tuple[List[Dict[str, Any]], int, int]:
    records: List[Dict[str, Any]] = []
    malformed = invalid = 0
    order = 0
    for name in paths:
        path = Path(name)
        try:
            handle = path.open("r", encoding="utf-8", errors="replace")
        except OSError as exc:
            raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                if not isinstance(rec, dict):
                    malformed += 1
                    continue
                try:
                    tokens = extract_tokens(rec, input_includes_cache)
                except ValueError:
                    invalid += 1
                    continue
                usage = rec.get("usage") if isinstance(rec.get("usage"), dict) else {}
                model = first(rec, "model") or first(usage, "model") or "(unknown)"
                session = first(rec, "session_id", "session", "run_id", "conversation_id")
                stamp = first(rec, "timestamp", "ts", "time", "created_at")
                order += 1
                records.append({
                    "model": str(model), "session": None if session is None else str(session),
                    "stamp": stamp, "day": day_of(stamp), "order": order,
                    "tokens": tokens, "recorded_cost": recorded_cost(rec),
                })
    return records, malformed, invalid


def latest_per_session(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Keep the newest snapshot per session; records without a session are kept as they are."""
    best: Dict[str, Dict[str, Any]] = {}
    loose = []
    for rec in records:
        if rec["session"] is None:
            loose.append(rec)
            continue
        key = (str(rec["stamp"]) if rec["stamp"] is not None else "", rec["order"])
        cur = best.get(rec["session"])
        if cur is None or key >= (str(cur["stamp"]) if cur["stamp"] is not None else "", cur["order"]):
            best[rec["session"]] = rec
    kept = sorted(list(best.values()) + loose, key=lambda r: r["order"])
    return kept, len(records) - len(kept)


def load_prices(path: str) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    except OSError as exc:
        raise InputError(f"cannot read price file {path}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"price file {path} is not valid JSON: {exc.msg} at line {exc.lineno}") from exc
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, dict) or not models:
        raise InputError("price file needs a non-empty \"models\" object")
    unit = data.get("unit_tokens", Decimal(1000000))
    if not isinstance(unit, Decimal) or not unit.is_finite() or unit <= 0:
        raise InputError("unit_tokens must be a positive number")
    table = {}
    for name, rates in models.items():
        if not isinstance(rates, dict):
            raise InputError(f"prices for {name} must be an object")
        clean = {}
        for key in ("input", "output", "cache_write", "cache_read"):
            if key in rates:
                value = rates[key]
                if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                    raise InputError(f"price {name}.{key} must be a non-negative number")
                clean[key] = value
        if "input" not in clean or "output" not in clean:
            raise InputError(f"prices for {name} need at least input and output")
        table[str(name)] = clean
    return {"models": table, "unit": unit, "currency": str(data.get("currency", "USD")),
            "as_of": data.get("as_of"), "source": data.get("source")}


def match_price(model: str, table: Dict[str, Dict[str, Decimal]]) -> Optional[Dict[str, Decimal]]:
    if model in table:
        return table[model]
    best = None
    for pattern, rates in table.items():
        if pattern.endswith("*") and model.startswith(pattern[:-1]):
            if best is None or len(pattern) > len(best[0]):
                best = (pattern, rates)
    return best[1] if best else None


def price_record(tokens: Dict[str, int], rates: Dict[str, Decimal], unit: Decimal) -> Optional[Tuple[Decimal, Decimal]]:
    """(actual cost, cost if every input token were ordinary input); None if a needed rate is missing."""
    if tokens["cache_write"] and "cache_write" not in rates:
        return None
    if tokens["cache_read"] and "cache_read" not in rates:
        return None
    actual = (tokens["ordinary"] * rates["input"] + tokens["cache_write"] * rates.get("cache_write", Decimal(0))
              + tokens["cache_read"] * rates.get("cache_read", Decimal(0)) + tokens["output"] * rates["output"]) / unit
    total_in = tokens["ordinary"] + tokens["cache_write"] + tokens["cache_read"]
    uncached = (total_in * rates["input"] + tokens["output"] * rates["output"]) / unit
    return actual, uncached


def money(value: Decimal) -> float:
    return float(value.quantize(Q))


def build_report(records, malformed, invalid, deduped, prices, budget, top, cumulative) -> Dict[str, Any]:
    zero = lambda: {c: 0 for c in CATEGORIES}
    totals = zero()
    by_model: Dict[str, Dict[str, Any]] = {}
    by_day: Dict[str, Dict[str, Any]] = {}
    by_session: Dict[str, Dict[str, Any]] = {}
    unpriced: Dict[str, int] = {}
    cost = uncached_cost = Decimal(0)
    rec_cost = Decimal(0)
    rec_cost_count = 0
    with_reads = 0
    for rec in records:
        t = rec["tokens"]
        for c in CATEGORIES:
            totals[c] += t[c]
        if t["cache_read"] > 0:
            with_reads += 1
        if rec["recorded_cost"] is not None:
            rec_cost += rec["recorded_cost"]
            rec_cost_count += 1
        priced = None
        if prices:
            rates = match_price(rec["model"], prices["models"])
            priced = price_record(t, rates, prices["unit"]) if rates else None
            if priced is None:
                unpriced[rec["model"]] = unpriced.get(rec["model"], 0) + sum(t.values())
            else:
                cost += priced[0]
                uncached_cost += priced[1]
        groups = [(by_model, rec["model"]), (by_day, rec["day"])]
        if rec["session"] is not None:
            groups.append((by_session, rec["session"]))
        for table, key in groups:
            row = table.setdefault(key, {"records": 0, "tokens": zero(), "cost": Decimal(0), "unpriced_records": 0})
            row["records"] += 1
            for c in CATEGORIES:
                row["tokens"][c] += t[c]
            if priced is not None:
                row["cost"] += priced[0]
            elif prices:
                row["unpriced_records"] += 1

    input_total = totals["ordinary"] + totals["cache_write"] + totals["cache_read"]

    def rows(table, sort_by_cost, limit=None):
        items = []
        for key, row in table.items():
            item = {"key": key, "records": row["records"], "tokens": row["tokens"]}
            if prices:
                fully_unpriced = row["unpriced_records"] == row["records"]
                item["cost"] = None if fully_unpriced else money(row["cost"])
                item["unpriced_records"] = row["unpriced_records"]
            items.append(item)
        if sort_by_cost and prices:
            items.sort(key=lambda r: (r["cost"] is None, -(r["cost"] or 0), r["key"]))
        elif sort_by_cost:
            items.sort(key=lambda r: (-sum(r["tokens"].values()), r["key"]))
        else:
            items.sort(key=lambda r: r["key"])
        return items[:limit] if limit else items

    report: Dict[str, Any] = {
        "mode": "cumulative (latest record per session)" if cumulative else "per call",
        "records_used": len(records),
        "snapshots_superseded": deduped,
        "malformed_lines": malformed,
        "skipped_records": invalid,
        "tokens": totals,
        "cache": {
            "token_hit_rate": round(totals["cache_read"] / input_total, 4) if input_total else None,
            "records_with_cache_reads": with_reads,
        },
        "by_model": rows(by_model, True),
        "by_day": rows(by_day, False),
        "top_sessions": rows(by_session, True, top),
    }
    if rec_cost_count:
        report["recorded_cost"] = {"total": money(rec_cost), "records_with_cost": rec_cost_count}
    if prices:
        report["prices"] = {"as_of": prices["as_of"], "source": prices["source"], "currency": prices["currency"]}
        report["cost"] = {"total": money(cost), "without_caching": money(uncached_cost),
                          "caching_savings": money(uncached_cost - cost)}
        report["unpriced_models"] = [{"model": m, "tokens": n} for m, n in sorted(unpriced.items())]
    if budget is not None:
        if prices and not unpriced:
            spent, basis = cost, "computed from the price file"
        elif not prices and rec_cost_count == len(records):
            spent, basis = rec_cost, "recorded cost fields"
        else:
            spent, basis = None, "cost unknown: unpriced models or missing prices"
        status = "unknown" if spent is None else ("exceeded" if spent > budget else "within")
        report["budget"] = {"limit": money(budget), "spent": None if spent is None else money(spent),
                            "status": status, "basis": basis}
    return report


def fmt_tokens(t: Dict[str, int]) -> str:
    return (f"input {t['ordinary']:,} | cache write {t['cache_write']:,} | cache read {t['cache_read']:,}"
            f" | output {t['output']:,}")


def print_text(report: Dict[str, Any], paths: List[str]) -> None:
    print(f"usage_cost {VERSION}: {', '.join(paths)} ({report['mode']})")
    print(f"records used {report['records_used']}, superseded snapshots {report['snapshots_superseded']}, "
          f"malformed lines {report['malformed_lines']}, skipped records without valid token counts {report['skipped_records']}")
    print("tokens: " + fmt_tokens(report["tokens"]))
    rate = report["cache"]["token_hit_rate"]
    print(f"cache: token hit rate {'n/a' if rate is None else f'{rate:.1%}'}, "
          f"records with cache reads {report['cache']['records_with_cache_reads']}")
    if "recorded_cost" in report:
        rc = report["recorded_cost"]
        print(f"recorded cost fields: {rc['total']:.6f} over {rc['records_with_cost']} record(s)")
    if "cost" in report:
        p = report["prices"]
        cur = p["currency"]
        print(f"prices: as of {p['as_of'] or 'UNDATED'}{' from ' + str(p['source']) if p['source'] else ''}")
        c = report["cost"]
        print(f"cost: {c['total']:.6f} {cur}; without caching {c['without_caching']:.6f}; "
              f"caching saved {c['caching_savings']:.6f} (negative means caching cost more)")
        for u in report["unpriced_models"]:
            print(f"UNPRICED {u['model']}: {u['tokens']:,} tokens not costed; add it to the price file")
    for title, key in (("by model", "by_model"), ("by day", "by_day"), ("top sessions", "top_sessions")):
        if not report[key]:
            continue
        print(f"{title}:")
        for row in report[key]:
            if "cost" not in row:
                cost = ""
            elif row["cost"] is None:
                cost = "  unpriced"
            elif row["unpriced_records"]:
                cost = f"  {row['cost']:.6f} + {row['unpriced_records']} unpriced"
            else:
                cost = f"  {row['cost']:.6f}"
            print(f"  {row['key']}: {row['records']} rec{cost}  ({fmt_tokens(row['tokens'])})")
    if "budget" in report:
        b = report["budget"]
        spent = "unknown" if b["spent"] is None else f"{b['spent']:.6f}"
        print(f"budget: {b['status'].upper()} (spent {spent} of {b['limit']:.6f}; {b['basis']})")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Token and cost report from JSON Lines LLM usage logs, with a price file you supply. "
                    "Read-only and offline; never reads prompt text.",
        epilog='Price file: {"as_of": "YYYY-MM-DD", "source": "...", "currency": "USD", "unit_tokens": 1000000, '
               '"models": {"model-id": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3}, '
               '"family-*": {...}}}. Exit codes: 0 report produced, 1 budget exceeded or not verifiable, 2 bad input.')
    parser.add_argument("logs", nargs="+", help="JSON Lines usage log file(s)")
    parser.add_argument("--prices", help="JSON price file, rates per unit_tokens (default 1,000,000)")
    parser.add_argument("--cumulative", action="store_true", help="lines are running totals per session; keep the latest")
    parser.add_argument("--input-includes-cache", action="store_true",
                        help="input_tokens already include cache write and read tokens (separate-counter logs only)")
    parser.add_argument("--budget", type=str, help="spending limit in the price file's currency; exit 1 if exceeded or unknown")
    parser.add_argument("--top", type=int, default=10, help="sessions to list (default 10)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    budget = None
    if args.budget is not None:
        try:
            budget = Decimal(args.budget)
        except InvalidOperation:
            budget = None
        if budget is None or not budget.is_finite() or budget < 0:
            print("usage_cost: --budget must be a non-negative number", file=sys.stderr)
            return 2
    if args.top < 1:
        print("usage_cost: --top must be at least 1", file=sys.stderr)
        return 2
    try:
        prices = load_prices(args.prices) if args.prices else None
        records, malformed, invalid = read_records(args.logs, args.input_includes_cache)
    except InputError as exc:
        print(f"usage_cost: {exc}", file=sys.stderr)
        return 2
    if not records:
        print(f"usage_cost: no usable records ({malformed} malformed line(s), {invalid} record(s) without valid token counts)", file=sys.stderr)
        return 2
    deduped = 0
    if args.cumulative:
        records, deduped = latest_per_session(records)

    report = build_report(records, malformed, invalid, deduped, prices, budget, args.top, args.cumulative)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report, args.logs)
    status = report.get("budget", {}).get("status")
    return 1 if status in ("exceeded", "unknown") else 0


if __name__ == "__main__":
    sys.exit(main())
