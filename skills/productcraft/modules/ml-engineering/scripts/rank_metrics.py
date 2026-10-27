#!/usr/bin/env python3
"""ProductCraft ML Engineering: ranking metrics for retrieval and recommendations.

Reads JSON Lines, one query (or user) per line:

  {"query": "q1", "relevant": ["d3", "d9"], "retrieved": ["d3", "d4", "d9"]}
  {"query": "q2", "relevant": {"d1": 3, "d2": 1}, "retrieved": ["d2", "d1"]}

"relevant" is a list (binary relevance) or an object of graded relevance
(grade > 0 is relevant). "retrieved" is the system's ranked output, best first.

Metrics at each cutoff k (macro-averaged over queries that have at least one
relevant item):

  hit@k        1 if any relevant item is in the top k
  precision@k  relevant items in the top k divided by k
  recall@k     relevant items in the top k divided by all relevant items
  mrr@k        1 / rank of the first relevant item within the top k, else 0
  ndcg@k       DCG of the top k over the ideal DCG; gain 2^grade - 1
               (--gain linear uses the grade itself), discount log2(rank + 1)
  map@k        average precision at k, normalized by min(k, relevant count)

Optional: --catalog-size N adds coverage@k (distinct items shown in any top k
divided by N); --ci adds seeded bootstrap intervals over queries; --per-query
prints one CSV row per query instead of the summary, for paired comparison
with compare_scores.py bootstrap.

Exit codes: 0 computed; 1 a --min threshold was not met; 2 bad input.
Reads only the given file (or stdin) and writes only to stdout.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
METRICS = ("hit", "precision", "recall", "mrr", "ndcg", "map")


class InputError(Exception):
    pass


def load(lines: Sequence[str], qkey: str, rkey: str, tkey: str) -> Tuple[List[Tuple[str, Dict[str, float], List[str]]], Dict[str, int]]:
    queries: List[Tuple[str, Dict[str, float], List[str]]] = []
    stats = {"lines": 0, "no_relevant": 0, "duplicate_retrieved": 0}
    seen_q = set()
    for number, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text:
            continue
        stats["lines"] += 1
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError(f"line {number}: invalid JSON ({exc.msg})") from None
        if not isinstance(obj, dict):
            raise InputError(f"line {number}: expected a JSON object")
        q = str(obj.get(qkey, number))
        if q in seen_q:
            raise InputError(f"line {number}: query '{q}' appears twice")
        seen_q.add(q)
        rel_raw = obj.get(rkey)
        ret_raw = obj.get(tkey)
        if rel_raw is None or ret_raw is None:
            raise InputError(f"line {number}: needs '{rkey}' and '{tkey}'")
        if isinstance(rel_raw, list):
            rel = {str(i): 1.0 for i in rel_raw}
        elif isinstance(rel_raw, dict):
            try:
                rel = {str(k): float(v) for k, v in rel_raw.items()}
            except (TypeError, ValueError):
                raise InputError(f"line {number}: relevance grades must be numbers") from None
            if any(math.isnan(v) or v < 0 for v in rel.values()):
                raise InputError(f"line {number}: relevance grades must be non-negative numbers")
        else:
            raise InputError(f"line {number}: '{rkey}' must be a list or an object")
        if not isinstance(ret_raw, list):
            raise InputError(f"line {number}: '{tkey}' must be a list")
        ranked: List[str] = []
        seen = set()
        for item in ret_raw:
            key = str(item)
            if key in seen:
                stats["duplicate_retrieved"] += 1
                continue
            seen.add(key)
            ranked.append(key)
        rel = {k: v for k, v in rel.items() if v > 0}
        if not rel:
            stats["no_relevant"] += 1
            continue
        queries.append((q, rel, ranked))
    return queries, stats


def gain(grade: float, mode: str) -> float:
    return (2.0 ** grade - 1.0) if mode == "exp" else grade


def per_query(rel: Dict[str, float], ranked: List[str], k: int, gain_mode: str) -> Dict[str, float]:
    top = ranked[:k]
    hits = [1 if item in rel else 0 for item in top]
    n_hit = sum(hits)
    first = next((i for i, h in enumerate(hits, 1) if h), None)
    dcg = sum(gain(rel.get(item, 0.0), gain_mode) / math.log2(i + 1) for i, item in enumerate(top, 1))
    ideal = sorted(rel.values(), reverse=True)[:k]
    idcg = sum(gain(g, gain_mode) / math.log2(i + 1) for i, g in enumerate(ideal, 1))
    running = 0
    ap_sum = 0.0
    for i, h in enumerate(hits, 1):
        if h:
            running += 1
            ap_sum += running / i
    return {
        "hit": 1.0 if n_hit else 0.0,
        "precision": n_hit / k,
        "recall": n_hit / len(rel),
        "mrr": 1.0 / first if first else 0.0,
        "ndcg": dcg / idcg if idcg > 0 else 0.0,
        "map": ap_sum / min(k, len(rel)),
    }


def bootstrap_ci(values: Sequence[float], resamples: int, seed: int, level: float) -> Tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[i] for i in rng.choices(range(n), k=n)) / n for _ in range(resamples))
    lo_q = (1.0 - level) / 2.0
    lo = means[max(0, int(math.floor(lo_q * resamples)))]
    hi = means[min(resamples - 1, int(math.ceil((1.0 - lo_q) * resamples)) - 1)]
    return lo, hi


def parse_ks(text: str) -> List[int]:
    try:
        ks = sorted({int(p) for p in text.split(",") if p.strip()})
    except ValueError:
        raise InputError("--k must be comma-separated positive integers") from None
    if not ks or ks[0] < 1:
        raise InputError("--k must be comma-separated positive integers")
    return ks


def parse_mins(items: Sequence[str]) -> List[Tuple[str, int, float]]:
    out = []
    for item in items:
        try:
            name, value = item.split("=", 1)
            metric, k = name.split("@", 1)
            out.append((metric.strip(), int(k), float(value)))
        except ValueError:
            raise InputError(f"--min '{item}' must look like ndcg@10=0.4") from None
        if out[-1][0] not in METRICS:
            raise InputError(f"--min '{item}': unknown metric (use {', '.join(METRICS)})")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rank_metrics.py",
        description="Ranking metrics (hit, precision, recall, MRR, nDCG, MAP at k) for retrieval "
                    "and recommendation runs stored as JSON Lines.",
        epilog="Examples:\n"
               "  rank_metrics.py run.jsonl --k 1,5,10\n"
               "  rank_metrics.py run.jsonl --k 10 --ci --min recall@10=0.8\n"
               "  rank_metrics.py run.jsonl --k 10 --per-query > per_query.csv\n"
               "Exit codes: 0 computed, 1 a --min threshold failed, 2 bad input.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="JSON Lines file, or - for stdin")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    p.add_argument("--k", default="1,5,10", help="cutoffs (default 1,5,10)")
    p.add_argument("--gain", choices=("exp", "linear"), default="exp", help="nDCG gain (default exp)")
    p.add_argument("--query-key", default="query")
    p.add_argument("--relevant-key", default="relevant")
    p.add_argument("--retrieved-key", default="retrieved")
    p.add_argument("--catalog-size", type=int, help="number of items that could be shown, for coverage@k")
    p.add_argument("--ci", action="store_true", help="add bootstrap intervals over queries")
    p.add_argument("--resamples", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--level", type=float, default=0.95)
    p.add_argument("--per-query", action="store_true", help="print per-query CSV instead of the summary")
    p.add_argument("--min", action="append", default=[], metavar="METRIC@K=VALUE",
                   help="fail (exit 1) when the mean is below VALUE; repeatable")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        ks = parse_ks(args.k)
        mins = parse_mins(args.min)
        if not 0.5 < args.level < 1.0:
            raise InputError("--level must be between 0.5 and 1")
        if args.resamples < 100:
            raise InputError("--resamples must be at least 100")
        if args.path == "-":
            lines = sys.stdin.read().splitlines()
        else:
            try:
                with open(args.path, encoding="utf-8-sig") as handle:
                    lines = handle.read().splitlines()
            except OSError as exc:
                raise InputError(f"cannot read {args.path}: {exc.strerror}") from None
        queries, stats = load(lines, args.query_key, args.relevant_key, args.retrieved_key)
        if not queries:
            raise InputError("no query has a relevant item; nothing to score")
        for metric, k, _ in mins:
            if k not in ks:
                raise InputError(f"--min uses @{k}, which is not in --k")
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rows = []
    for q, rel, ranked in queries:
        row: Dict[str, object] = {"query": q, "relevant": len(rel), "retrieved": len(ranked)}
        for k in ks:
            for name, value in per_query(rel, ranked, k, args.gain).items():
                row[f"{name}@{k}"] = value
        rows.append(row)

    if args.per_query:
        writer = csv.writer(sys.stdout, lineterminator="\n")
        header = list(rows[0].keys())
        writer.writerow(header)
        for row in rows:
            writer.writerow([f"{row[h]:.6f}" if isinstance(row[h], float) else row[h] for h in header])
        return 0

    summary: Dict[str, object] = {"queries_scored": len(rows), "queries_without_relevant": stats["no_relevant"],
                                  "duplicate_retrieved_dropped": stats["duplicate_retrieved"], "gain": args.gain}
    metrics: Dict[str, Dict[str, object]] = {}
    for k in ks:
        for name in METRICS:
            key = f"{name}@{k}"
            values = [float(r[key]) for r in rows]  # type: ignore[arg-type]
            entry: Dict[str, object] = {"mean": sum(values) / len(values)}
            if args.ci:
                entry["ci"] = list(bootstrap_ci(values, args.resamples, args.seed, args.level))
            metrics[key] = entry
        if args.catalog_size:
            shown = {item for _, _, ranked in queries for item in ranked[:k]}
            metrics[f"coverage@{k}"] = {"mean": len(shown) / args.catalog_size}
    summary["metrics"] = metrics

    failed = []
    for metric, k, threshold in mins:
        value = metrics[f"{metric}@{k}"]["mean"]
        if value < threshold:  # type: ignore[operator]
            failed.append(f"{metric}@{k}={value:.4f} < {threshold}")
    summary["failed_thresholds"] = failed

    if args.json:
        print(json.dumps({"version": VERSION, **summary}, indent=2, sort_keys=True))
    else:
        print(f"queries scored: {len(rows)} (skipped without relevant items: {stats['no_relevant']}; "
              f"duplicate retrieved ids dropped: {stats['duplicate_retrieved']})")
        for key, entry in metrics.items():
            line = f"  {key:<14} {entry['mean']:.4f}"
            if "ci" in entry:
                lo, hi = entry["ci"]  # type: ignore[misc]
                line += f"  [{lo:.4f}, {hi:.4f}]"
            print(line)
        for f in failed:
            print(f"FAIL {f}")
    if stats["no_relevant"]:
        print(f"note: {stats['no_relevant']} queries had no relevant item and were left out; "
              "report them separately (for example, the share of correct abstentions)", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
