#!/usr/bin/env python3
"""ProductCraft ML Engineering: honest comparison of two models' scores.

Four subcommands, all offline and deterministic:

  cv         Paired per-fold scores from (repeated) k-fold cross-validation or
             repeated random splits. Runs the corrected resampled t-test
             (Nadeau and Bengio), which widens the variance because training
             sets overlap between folds. A plain paired t-test on fold scores
             is too optimistic and is not offered.
  bootstrap  Paired per-example (or per-query) values for model A and model B.
             Seeded paired bootstrap of the mean difference, optionally
             resampling whole clusters (users, documents, sites) when examples
             are not independent.
  mcnemar    Per-example correctness (0/1) of two classifiers on the same test
             set. Exact two-sided binomial McNemar test on the discordant pairs.
  adjust     A list of p-values from several comparisons. Holm (family-wise
             error) and Benjamini-Hochberg (false discovery rate) adjustment.

Differences are always reported as B - A. With --lower-is-better (losses,
errors) an improvement means B - A < 0.

Exit codes: 0 computed; 1 only with --require-improvement when the interval
(or test) does not show B better than A; 2 bad input or usage.

The script reads the files it is given and writes only to stdout. It never
uses the network.
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


class InputError(Exception):
    """Raised for unusable input; maps to exit code 2."""


# --- special functions --------------------------------------------------------

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(log_front) * _betacf(a, b, x) / a
    return 1.0 - math.exp(log_front) * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t: float, df: float) -> float:
    """Two-sided p-value P(|T| >= |t|) for Student's t with df degrees of freedom."""
    if math.isinf(t):
        return 0.0
    x = df / (df + t * t)
    return min(1.0, max(0.0, betainc(df / 2.0, 0.5, x)))


def t_cdf(t: float, df: float) -> float:
    p = t_sf_two_sided(t, df) / 2.0
    return 1.0 - p if t >= 0 else p


def t_quantile(q: float, df: float) -> float:
    """Quantile of Student's t (bisection; accurate to about 1e-10)."""
    if not 0.0 < q < 1.0:
        raise ValueError("quantile must be in (0, 1)")
    if q == 0.5:
        return 0.0
    if q < 0.5:
        return -t_quantile(1.0 - q, df)
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < q:
        hi *= 2.0
        if hi > 1e12:
            return math.inf
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return (lo + hi) / 2.0


def _logsumexp(values: Sequence[float]) -> float:
    top = max(values)
    if top == -math.inf:
        return -math.inf
    return top + math.log(sum(math.exp(v - top) for v in values))


def binom_two_sided_half(k: int, n: int) -> float:
    """Exact two-sided p-value for k successes in n trials with p = 0.5."""
    if n == 0:
        return 1.0
    low = min(k, n - k)
    log_half_n = -n * math.log(2.0)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + log_half_n
             for i in range(low + 1)]
    tail = math.exp(_logsumexp(terms))
    return min(1.0, 2.0 * tail)


# --- statistics ----------------------------------------------------------------

def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def sample_variance(values: Sequence[float]) -> float:
    m = mean(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def corrected_resampled_t(a: Sequence[float], b: Sequence[float], test_train_ratio: float,
                          level: float = 0.95) -> Dict[str, object]:
    if len(a) != len(b):
        raise InputError(f"A has {len(a)} scores and B has {len(b)}; fold scores must be paired")
    k = len(a)
    if k < 2:
        raise InputError("need at least 2 paired fold scores")
    if test_train_ratio <= 0:
        raise InputError("test/train size ratio must be positive")
    diffs = [y - x for x, y in zip(a, b)]
    d_mean = mean(diffs)
    s2 = sample_variance(diffs)
    df = k - 1
    result: Dict[str, object] = {
        "resamples": k,
        "test_train_ratio": test_train_ratio,
        "mean_a": mean(a),
        "mean_b": mean(b),
        "std_a": math.sqrt(sample_variance(a)),
        "std_b": math.sqrt(sample_variance(b)),
        "mean_diff_b_minus_a": d_mean,
        "df": df,
        "level": level,
    }
    if s2 == 0.0:
        result.update({"se": 0.0, "t": None, "p_two_sided": None, "ci": [d_mean, d_mean],
                       "note": "every fold shows the same difference; the test is undefined"})
        return result
    se = math.sqrt((1.0 / k + test_train_ratio) * s2)
    t = d_mean / se
    crit = t_quantile(1.0 - (1.0 - level) / 2.0, df)
    result.update({
        "se": se,
        "t": t,
        "p_two_sided": t_sf_two_sided(t, df),
        "ci": [d_mean - crit * se, d_mean + crit * se],
        "naive_se_for_contrast": math.sqrt(s2 / k),
    })
    return result


def paired_bootstrap(a: Sequence[float], b: Sequence[float], clusters: Optional[Sequence[str]],
                     resamples: int, seed: int, level: float) -> Dict[str, object]:
    if len(a) != len(b):
        raise InputError("A and B must have the same number of values")
    n = len(a)
    if n < 2:
        raise InputError("need at least 2 paired values")
    if resamples < 100:
        raise InputError("use at least 100 resamples")
    diffs = [y - x for x, y in zip(a, b)]
    rng = random.Random(seed)
    if clusters is None:
        units: List[Tuple[float, int]] = [(d, 1) for d in diffs]
    else:
        sums: Dict[str, List[float]] = {}
        for d, c in zip(diffs, clusters):
            entry = sums.setdefault(c, [0.0, 0])
            entry[0] += d
            entry[1] += 1
        units = [(s, int(cnt)) for s, cnt in (sums[key] for key in sorted(sums))]
        if len(units) < 2:
            raise InputError("need at least 2 clusters to resample")
    m = len(units)
    stats: List[float] = []
    for _ in range(resamples):
        total = 0.0
        count = 0
        for idx in rng.choices(range(m), k=m):
            s, cnt = units[idx]
            total += s
            count += cnt
        stats.append(total / count)
    stats.sort()
    lo_q = (1.0 - level) / 2.0
    lo = stats[min(resamples - 1, max(0, int(math.floor(lo_q * resamples))))]
    hi = stats[min(resamples - 1, max(0, int(math.ceil((1.0 - lo_q) * resamples)) - 1))]
    share_le_zero = sum(1 for s in stats if s <= 0.0) / resamples
    return {
        "n": n,
        "clusters": None if clusters is None else m,
        "resamples": resamples,
        "seed": seed,
        "level": level,
        "mean_a": mean(a),
        "mean_b": mean(b),
        "mean_diff_b_minus_a": mean(diffs),
        "ci": [lo, hi],
        "share_of_resamples_diff_le_0": share_le_zero,
    }


def mcnemar(a: Sequence[int], b: Sequence[int]) -> Dict[str, object]:
    if len(a) != len(b):
        raise InputError("A and B must have the same number of rows")
    if not a:
        raise InputError("no rows")
    both = sum(1 for x, y in zip(a, b) if x and y)
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    neither = len(a) - both - only_a - only_b
    n_disc = only_a + only_b
    return {
        "n": len(a),
        "both_correct": both,
        "only_a_correct": only_a,
        "only_b_correct": only_b,
        "neither_correct": neither,
        "accuracy_a": (both + only_a) / len(a),
        "accuracy_b": (both + only_b) / len(a),
        "diff_b_minus_a": (only_b - only_a) / len(a),
        "discordant": n_disc,
        "p_two_sided_exact": binom_two_sided_half(only_b, n_disc),
    }


def holm(pvalues: Sequence[float]) -> List[float]:
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[idx]))
        adjusted[idx] = running
    return adjusted


def benjamini_hochberg(pvalues: Sequence[float]) -> List[float]:
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m - 1, -1, -1):
        idx = order[rank]
        running = min(running, min(1.0, m * pvalues[idx] / (rank + 1)))
        adjusted[idx] = running
    return adjusted


# --- input helpers ---------------------------------------------------------------

def parse_float_list(text: str, label: str) -> List[float]:
    try:
        values = [float(part) for part in text.replace(";", ",").split(",") if part.strip()]
    except ValueError as exc:
        raise InputError(f"{label}: not a comma-separated list of numbers ({exc})") from None
    _check_finite(values, label)
    return values


def _check_finite(values: Sequence[float], label: str) -> None:
    for v in values:
        if math.isnan(v) or math.isinf(v):
            raise InputError(f"{label}: contains NaN or infinity")


def read_rows(path: str, delimiter: str) -> List[Dict[str, str]]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            rows = list(reader)
            fields = reader.fieldnames or []
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror}") from None
    if not fields:
        raise InputError(f"{path}: no header row")
    return rows


def column(rows: List[Dict[str, str]], name: str, path: str) -> List[str]:
    if rows and name not in rows[0]:
        raise InputError(f"{path}: column '{name}' not found (have: {', '.join(rows[0].keys())})")
    return [(r.get(name) or "").strip() for r in rows]


def to_floats(values: Sequence[str], label: str) -> List[float]:
    out = []
    for i, v in enumerate(values, 1):
        try:
            out.append(float(v))
        except ValueError:
            raise InputError(f"{label}: row {i} value '{v}' is not a number") from None
    _check_finite(out, label)
    return out


TRUE = {"1", "true", "yes", "y", "t", "correct"}
FALSE = {"0", "false", "no", "n", "f", "incorrect", "wrong"}


def to_binary(values: Sequence[str], label: str) -> List[int]:
    out = []
    for i, v in enumerate(values, 1):
        low = v.lower()
        if low in TRUE:
            out.append(1)
        elif low in FALSE:
            out.append(0)
        else:
            raise InputError(f"{label}: row {i} value '{v}' is not 0/1 or true/false")
    return out


# --- output --------------------------------------------------------------------

def fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0 and (abs(value) < 1e-4 or abs(value) >= 1e6):
            return f"{value:.3e}"
        return f"{value:.4f}"
    return str(value)


def improved(lo: float, hi: float, lower_is_better: bool) -> bool:
    return hi < 0 if lower_is_better else lo > 0


def emit(command: str, result: Dict[str, object], notes: List[str], as_json: bool) -> None:
    if as_json:
        print(json.dumps({"command": command, "version": VERSION, "result": result, "notes": notes},
                         indent=2, sort_keys=True))
        return
    print(f"compare_scores {command}")
    for key, value in result.items():
        if isinstance(value, list) and value and not isinstance(value[0], dict):
            shown = ", ".join(fmt(v) for v in value)
            print(f"  {key}: [{shown}]")
        elif isinstance(value, list):
            for item in value:
                print("  " + "  ".join(f"{k}={fmt(v)}" for k, v in item.items()))
        else:
            print(f"  {key}: {fmt(value)}")
    for note in notes:
        print(f"note: {note}")


# --- commands ------------------------------------------------------------------

def load_pair(args: argparse.Namespace) -> Tuple[List[str], List[str], Optional[List[str]]]:
    """Return raw A values, raw B values and optional clusters from the chosen input form."""
    if args.a_csv or args.b_csv:
        if not (args.a_csv and args.b_csv and args.key and args.value):
            raise InputError("two-file mode needs --a-csv, --b-csv, --key and --value")
        rows_a = read_rows(args.a_csv, args.delimiter)
        rows_b = read_rows(args.b_csv, args.delimiter)
        map_a = dict(zip(column(rows_a, args.key, args.a_csv), column(rows_a, args.value, args.a_csv)))
        map_b = dict(zip(column(rows_b, args.key, args.b_csv), column(rows_b, args.value, args.b_csv)))
        shared = sorted(set(map_a) & set(map_b))
        missing = (set(map_a) ^ set(map_b))
        if missing:
            raise InputError(f"{len(missing)} keys appear in only one file; compare on the same items")
        return [map_a[k] for k in shared], [map_b[k] for k in shared], None
    if args.csv:
        if not (args.a_col and args.b_col):
            raise InputError("--csv needs --a-col and --b-col")
        rows = read_rows(args.csv, args.delimiter)
        clusters = column(rows, args.cluster_col, args.csv) if getattr(args, "cluster_col", None) else None
        return column(rows, args.a_col, args.csv), column(rows, args.b_col, args.csv), clusters
    raise InputError("give --csv FILE with --a-col/--b-col, or --a-csv/--b-csv with --key/--value")


def cmd_cv(args: argparse.Namespace) -> int:
    if args.csv:
        rows = read_rows(args.csv, args.delimiter)
        if not (args.a_col and args.b_col):
            raise InputError("--csv needs --a-col and --b-col")
        a = to_floats(column(rows, args.a_col, args.csv), args.a_col)
        b = to_floats(column(rows, args.b_col, args.csv), args.b_col)
    elif args.a is not None and args.b is not None:
        a = parse_float_list(args.a, "--a")
        b = parse_float_list(args.b, "--b")
    else:
        raise InputError("give --a and --b as comma-separated fold scores, or --csv with --a-col/--b-col")
    if args.test_train_ratio is not None:
        ratio = args.test_train_ratio
    elif args.folds is not None:
        if args.folds < 2:
            raise InputError("--folds must be at least 2")
        ratio = 1.0 / (args.folds - 1)
    else:
        raise InputError("give --folds K (k-fold CV) or --test-train-ratio (repeated random splits)")
    result = corrected_resampled_t(a, b, ratio, args.level)
    notes = ["fold scores share training data, so the corrected standard error is used; "
             "do not quote the naive one"]
    if args.folds is not None and len(a) == args.folds:
        notes.append("a single k-fold run gives few degrees of freedom; repeated k-fold "
                     "(for example 5x2 or 10x10) gives a steadier estimate")
    status = 0
    if args.require_improvement and isinstance(result.get("ci"), list):
        lo, hi = result["ci"]  # type: ignore[misc]
        if not improved(lo, hi, args.lower_is_better):
            notes.append("interval does not show B better than A")
            status = 1
    emit("cv", result, notes, args.json)
    return status


def cmd_bootstrap(args: argparse.Namespace) -> int:
    raw_a, raw_b, clusters = load_pair(args)
    a = to_floats(raw_a, "A")
    b = to_floats(raw_b, "B")
    if clusters is not None and any(c == "" for c in clusters):
        raise InputError("cluster column has empty values")
    result = paired_bootstrap(a, b, clusters, args.resamples, args.seed, args.level)
    notes = ["percentile interval of the mean of B - A over resampled "
             + ("clusters" if clusters is not None else "examples")]
    if clusters is None:
        notes.append("if several rows come from the same user, document or site, pass --cluster-col; "
                     "otherwise the interval is too narrow")
    status = 0
    lo, hi = result["ci"]  # type: ignore[misc]
    if args.require_improvement and not improved(lo, hi, args.lower_is_better):
        notes.append("interval does not show B better than A")
        status = 1
    emit("bootstrap", result, notes, args.json)
    return status


def cmd_mcnemar(args: argparse.Namespace) -> int:
    if not (args.csv and args.a_col and args.b_col):
        raise InputError("mcnemar needs --csv, --a-col and --b-col (0/1 correctness per row)")
    rows = read_rows(args.csv, args.delimiter)
    a = to_binary(column(rows, args.a_col, args.csv), args.a_col)
    b = to_binary(column(rows, args.b_col, args.csv), args.b_col)
    result = mcnemar(a, b)
    notes = ["only rows where exactly one model is correct carry information"]
    if result["discordant"] == 0:
        notes.append("no discordant rows: the models never disagree on correctness")
    status = 0
    if args.require_improvement:
        p = result["p_two_sided_exact"]
        better = result["only_b_correct"] > result["only_a_correct"]  # type: ignore[operator]
        if not (better and p < args.alpha):  # type: ignore[operator]
            notes.append(f"B is not shown better than A at alpha={args.alpha}")
            status = 1
    emit("mcnemar", result, notes, args.json)
    return status


def cmd_adjust(args: argparse.Namespace) -> int:
    labels: List[str]
    if args.csv:
        if not args.p_col:
            raise InputError("--csv needs --p-col")
        rows = read_rows(args.csv, args.delimiter)
        pvals = to_floats(column(rows, args.p_col, args.csv), args.p_col)
        labels = column(rows, args.label_col, args.csv) if args.label_col else [str(i + 1) for i in range(len(pvals))]
    elif args.p:
        pvals = parse_float_list(args.p, "--p")
        labels = [str(i + 1) for i in range(len(pvals))]
    else:
        raise InputError("give --p as a comma-separated list or --csv with --p-col")
    if not pvals:
        raise InputError("no p-values")
    if any(not 0.0 <= p <= 1.0 for p in pvals):
        raise InputError("p-values must lie in [0, 1]")
    h = holm(pvals)
    bh = benjamini_hochberg(pvals)
    table = [{"label": lab, "p": p, "holm": hp, "holm_reject": hp <= args.alpha,
              "bh": bp, "bh_reject": bp <= args.alpha}
             for lab, p, hp, bp in zip(labels, pvals, h, bh)]
    result: Dict[str, object] = {"m": len(pvals), "alpha": args.alpha,
                                 "holm_rejections": sum(1 for r in table if r["holm_reject"]),
                                 "bh_rejections": sum(1 for r in table if r["bh_reject"]),
                                 "tests": table}
    notes = ["Holm controls the chance of any false positive; Benjamini-Hochberg controls the "
             "expected share of false positives among rejections",
             "count every comparison you looked at, including ones you will not report"]
    emit("adjust", result, notes, args.json)
    return 0


# --- CLI -----------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compare_scores.py",
        description="Compare two models' scores honestly: corrected CV t-test, paired or cluster "
                    "bootstrap, exact McNemar, and Holm or Benjamini-Hochberg adjustment. "
                    "Differences are reported as B - A.",
        epilog="Examples:\n"
               "  compare_scores.py cv --a 0.81,0.79,0.83,0.80,0.82 --b 0.84,0.80,0.85,0.83,0.83 --folds 5\n"
               "  compare_scores.py bootstrap --csv per_example.csv --a-col loss_a --b-col loss_b --lower-is-better\n"
               "  compare_scores.py bootstrap --a-csv base.csv --b-csv new.csv --key query --value ndcg@10\n"
               "  compare_scores.py mcnemar --csv preds.csv --a-col a_correct --b-col b_correct\n"
               "  compare_scores.py adjust --p 0.01,0.04,0.03,0.20\n"
               "Exit codes: 0 computed, 1 --require-improvement not met, 2 bad input.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, gate: bool = True) -> None:
        p.add_argument("--json", action="store_true", help="print JSON instead of text")
        p.add_argument("--delimiter", default=",", help="CSV delimiter (default ',')")
        if gate:
            p.add_argument("--lower-is-better", action="store_true",
                           help="scores are losses or errors; improvement means B - A < 0")
            p.add_argument("--require-improvement", action="store_true",
                           help="exit 1 unless the result shows B better than A")

    p_cv = sub.add_parser("cv", help="corrected resampled t-test on paired fold scores")
    p_cv.add_argument("--a", help="comma-separated fold scores of model A")
    p_cv.add_argument("--b", help="comma-separated fold scores of model B, same fold order")
    p_cv.add_argument("--csv", help="CSV with one row per fold")
    p_cv.add_argument("--a-col")
    p_cv.add_argument("--b-col")
    p_cv.add_argument("--folds", type=int, help="K of the k-fold CV (test/train ratio = 1/(K-1))")
    p_cv.add_argument("--test-train-ratio", type=float,
                      help="n_test / n_train for repeated random splits")
    p_cv.add_argument("--level", type=float, default=0.95, help="interval level (default 0.95)")
    common(p_cv)
    p_cv.set_defaults(func=cmd_cv)

    p_bs = sub.add_parser("bootstrap", help="paired or cluster bootstrap of the mean difference")
    p_bs.add_argument("--csv", help="CSV with one row per example and columns for A and B")
    p_bs.add_argument("--a-col")
    p_bs.add_argument("--b-col")
    p_bs.add_argument("--cluster-col", help="resample whole clusters (user, document, site)")
    p_bs.add_argument("--a-csv", help="per-item values of model A (two-file mode)")
    p_bs.add_argument("--b-csv", help="per-item values of model B (two-file mode)")
    p_bs.add_argument("--key", help="join column in two-file mode, for example query")
    p_bs.add_argument("--value", help="value column in two-file mode, for example ndcg@10")
    p_bs.add_argument("--resamples", type=int, default=2000, help="bootstrap resamples (default 2000)")
    p_bs.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    p_bs.add_argument("--level", type=float, default=0.95, help="interval level (default 0.95)")
    common(p_bs)
    p_bs.set_defaults(func=cmd_bootstrap)

    p_mc = sub.add_parser("mcnemar", help="exact McNemar test on per-example correctness")
    p_mc.add_argument("--csv", required=False)
    p_mc.add_argument("--a-col")
    p_mc.add_argument("--b-col")
    p_mc.add_argument("--alpha", type=float, default=0.05)
    common(p_mc)
    p_mc.set_defaults(func=cmd_mcnemar)

    p_ad = sub.add_parser("adjust", help="Holm and Benjamini-Hochberg adjusted p-values")
    p_ad.add_argument("--p", help="comma-separated p-values")
    p_ad.add_argument("--csv")
    p_ad.add_argument("--p-col")
    p_ad.add_argument("--label-col")
    p_ad.add_argument("--alpha", type=float, default=0.05)
    common(p_ad, gate=False)
    p_ad.set_defaults(func=cmd_adjust)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    level = getattr(args, "level", 0.95)
    if not 0.5 < level < 1.0:
        print("error: --level must be between 0.5 and 1", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
