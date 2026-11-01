#!/usr/bin/env python3
"""ProductCraft ML Engineering: compare two independent samples of benchmark measurements.

Typical use: timings of a baseline (A) and a candidate (B), one measurement per run.
The samples are unpaired (different runs), so this is not the paired comparison done by
compare_scores.py.

Reported for each sample: count, mean, median, quartiles, standard deviation, coefficient
of variation, min, max and Tukey outliers. Comparisons (ratio = B / A):

  * Welch's t-test on log values: ratio of geometric means with a confidence interval.
  * Mann-Whitney U: exact two-sided p-value for small samples without ties, otherwise the
    normal approximation with tie and continuity corrections.
  * Seeded percentile bootstrap: ratio of medians with a confidence interval.

The verdict follows the Welch interval: improvement or regression only when the whole
interval lies beyond 1 (and beyond --threshold percent, if given); "equivalent" when the
whole interval lies inside the threshold band; otherwise "no significant difference"
(no threshold) or "inconclusive".

Inputs: plain text (numbers separated by newlines, commas or spaces; '#' starts a comment),
CSV (--column), JSON lists of numbers, hyperfine exports ({"results": [{"command", "times"}]})
and pytest-benchmark exports saved with raw data ({"benchmarks": [{"name", "stats": {"data"}}]}).

Exit codes: 0 computed; 1 when --fail-on-regression or --require-improvement trips;
2 bad input or usage. Reads only the files it is given, writes only to stdout and stderr,
never uses the network. Output is deterministic for a given --seed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"


class InputError(Exception):
    """Unusable input; exit code 2."""


# --- special functions ---------------------------------------------------------

def _beta_cf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta function (Lentz's method)."""
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    result = d
    for m in range(1, 1000):
        m2 = 2 * m
        num = m * (b - m) * x / ((a + m2 - 1.0) * (a + m2))
        d = 1.0 + num * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + num / c
        c = c if abs(c) > tiny else tiny
        result *= d * c
        num = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1.0))
        d = 1.0 + num * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + num / c
        c = c if abs(c) > tiny else tiny
        step = d * c
        result *= step
        if abs(step - 1.0) < 1e-15:
            break
    return result


def reg_inc_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b) for a, b > 0 and 0 <= x <= 1."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_cf(a, b, x) / a
    return 1.0 - front * _beta_cf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """Cumulative distribution function of Student's t."""
    if math.isinf(t):
        return 1.0 if t > 0 else 0.0
    tail = 0.5 * reg_inc_beta(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t > 0 else tail


def t_two_sided_p(t: float, df: float) -> float:
    if math.isinf(t):
        return 0.0
    return min(1.0, reg_inc_beta(df / 2.0, 0.5, df / (df + t * t)))


def t_quantile(p: float, df: float) -> float:
    """Inverse of t_cdf by bisection; accurate to about 1e-10."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    if p == 0.5:
        return 0.0
    lo, hi = -1.0, 1.0
    while t_cdf(lo, df) > p:
        lo *= 2.0
    while t_cdf(hi, df) < p:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return 0.5 * (lo + hi)


def normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


# --- descriptive statistics ------------------------------------------------------

def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear interpolation between closest ranks (the common 'type 7' definition)."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def ranks(values: Sequence[float]) -> List[float]:
    """Average ranks (1-based), ties share the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            result[order[k]] = mean_rank
        i = j + 1
    return result


def spearman_with_order(values: Sequence[float]) -> Optional[float]:
    """Spearman correlation between run order and value; None when undefined."""
    n = len(values)
    if n < 3:
        return None
    rv = ranks(values)
    ro = [float(i + 1) for i in range(n)]
    mv, mo = statistics.fmean(rv), statistics.fmean(ro)
    sv = math.sqrt(sum((x - mv) ** 2 for x in rv))
    so = math.sqrt(sum((x - mo) ** 2 for x in ro))
    if sv == 0 or so == 0:
        return None
    return sum((a - mv) * (b - mo) for a, b in zip(rv, ro)) / (sv * so)


def describe(values: Sequence[float]) -> Dict[str, float]:
    s = sorted(values)
    q1, q3 = quantile(s, 0.25), quantile(s, 0.75)
    iqr = q3 - q1
    mean = statistics.fmean(s)
    stdev = statistics.stdev(s) if len(s) > 1 else 0.0
    low_fence, high_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return {
        "n": len(s), "mean": mean, "median": quantile(s, 0.5), "q1": q1, "q3": q3,
        "stdev": stdev, "cv_percent": (100.0 * stdev / mean) if mean else float("nan"),
        "min": s[0], "max": s[-1],
        "outliers": sum(1 for v in s if v < low_fence or v > high_fence),
        "geometric_mean": math.exp(statistics.fmean(math.log(v) for v in s)),
    }


# --- comparisons -------------------------------------------------------------------

def welch_log(a: Sequence[float], b: Sequence[float], level: float) -> Dict[str, float]:
    la, lb = [math.log(v) for v in a], [math.log(v) for v in b]
    na, nb = len(la), len(lb)
    ma, mb = statistics.fmean(la), statistics.fmean(lb)
    va, vb = statistics.variance(la), statistics.variance(lb)
    diff = mb - ma
    se2 = va / na + vb / nb
    if se2 == 0.0:
        ratio = math.exp(diff)
        return {"ratio": ratio, "ci_low": ratio, "ci_high": ratio, "t": 0.0 if diff == 0 else math.copysign(math.inf, diff),
                "df": float(na + nb - 2), "p": 1.0 if diff == 0 else 0.0}
    se = math.sqrt(se2)
    denom = 0.0
    if na > 1:
        denom += (va / na) ** 2 / (na - 1)
    if nb > 1:
        denom += (vb / nb) ** 2 / (nb - 1)
    df = se2 ** 2 / denom if denom > 0 else float(na + nb - 2)
    tq = t_quantile(0.5 + level / 2.0, df)
    t = diff / se
    return {"ratio": math.exp(diff), "ci_low": math.exp(diff - tq * se), "ci_high": math.exp(diff + tq * se),
            "t": t, "df": df, "p": t_two_sided_p(t, df)}


def mann_whitney_counts(m: int, n: int) -> List[int]:
    """Number of orderings giving each U = 0..m*n (coefficients of a Gaussian binomial)."""
    poly = [1]
    for i in range(1, m + 1):
        k = n + i
        new = poly + [0] * k
        for j, c in enumerate(poly):
            new[j + k] -= c
        for j in range(i, len(new)):
            new[j] += new[j - i]
        poly = new
    return poly[: m * n + 1]


def mann_whitney(a: Sequence[float], b: Sequence[float], exact_limit: int = 20) -> Dict[str, object]:
    """U counts pairs where the B value is larger than the A value (ties count one half)."""
    m, n = len(a), len(b)
    u = 0.0
    for x in a:
        for y in b:
            if y > x:
                u += 1.0
            elif y == x:
                u += 0.5
    combined = list(a) + list(b)
    has_ties = len(set(combined)) < len(combined)
    if m <= exact_limit and n <= exact_limit and not has_ties:
        counts = mann_whitney_counts(m, n)
        total = math.comb(m + n, m)
        k = int(round(u))
        lower = sum(counts[: k + 1]) / total
        upper = sum(counts[k:]) / total
        return {"u": u, "p": min(1.0, 2.0 * min(lower, upper)), "method": "exact"}
    big_n = m + n
    tie_sum = 0.0
    seen: Dict[float, int] = {}
    for v in combined:
        seen[v] = seen.get(v, 0) + 1
    for t in seen.values():
        tie_sum += t ** 3 - t
    mean_u = m * n / 2.0
    var_u = m * n / 12.0 * ((big_n + 1) - tie_sum / (big_n * (big_n - 1)))
    if var_u <= 0:
        return {"u": u, "p": 1.0, "method": "normal approximation"}
    delta = u - mean_u
    corrected = max(0.0, abs(delta) - 0.5)
    z = math.copysign(corrected, delta) / math.sqrt(var_u)
    return {"u": u, "p": normal_two_sided_p(z), "method": "normal approximation", "z": z}


def bootstrap_median_ratio(a: Sequence[float], b: Sequence[float], level: float,
                           resamples: int, seed: int) -> Optional[Dict[str, float]]:
    if resamples <= 0:
        return None
    rng = random.Random(seed)
    ratios = []
    na, nb = len(a), len(b)
    for _ in range(resamples):
        ma = statistics.median(rng.choices(a, k=na))
        mb = statistics.median(rng.choices(b, k=nb))
        ratios.append(mb / ma)
    ratios.sort()
    alpha = 1.0 - level
    return {"ratio": statistics.median(b) / statistics.median(a),
            "ci_low": quantile(ratios, alpha / 2.0), "ci_high": quantile(ratios, 1.0 - alpha / 2.0),
            "resamples": resamples, "seed": seed}


def verdict(ci_low: float, ci_high: float, threshold_pct: float, higher_is_better: bool) -> str:
    t = threshold_pct / 100.0
    lo_band, hi_band = 1.0 - t, 1.0 + t
    if higher_is_better:
        better = ci_low > hi_band if t > 0 else ci_low > 1.0
        worse = ci_high < lo_band if t > 0 else ci_high < 1.0
    else:
        better = ci_high < lo_band if t > 0 else ci_high < 1.0
        worse = ci_low > hi_band if t > 0 else ci_low > 1.0
    if better:
        return "improvement"
    if worse:
        return "regression"
    if t > 0 and lo_band <= ci_low and ci_high <= hi_band:
        return "equivalent"
    return "inconclusive" if t > 0 else "no significant difference"


# --- input ---------------------------------------------------------------------------

def _to_float(token: str, where: str) -> float:
    try:
        value = float(token)
    except ValueError:
        raise InputError(f"{where}: not a number: {token[:40]!r}") from None
    if math.isnan(value) or math.isinf(value):
        raise InputError(f"{where}: not a finite number: {token!r}")
    return value


def parse_inline(text: str, label: str) -> List[float]:
    tokens = [t for t in text.replace(",", " ").split() if t]
    return [_to_float(t, label) for t in tokens]


def _select(items: list, selector: Optional[str], names: List[str], path: str) -> object:
    if selector is None:
        if len(items) != 1:
            raise InputError(f"{path}: contains {len(items)} entries ({', '.join(names[:6])}); "
                             "choose one with --select-a/--select-b (index or name)")
        return items[0]
    if selector.isdigit():
        index = int(selector)
        if index >= len(items):
            raise InputError(f"{path}: index {index} out of range (0..{len(items) - 1})")
        return items[index]
    matches = [item for item, name in zip(items, names) if name == selector]
    if len(matches) != 1:
        raise InputError(f"{path}: {'no' if not matches else 'several'} entries named {selector!r}")
    return matches[0]


def parse_json(path: str, data: object, selector: Optional[str]) -> List[float]:
    if isinstance(data, list):
        return [_to_float(str(v), path) for v in data]
    if isinstance(data, dict) and isinstance(data.get("results"), list):        # hyperfine
        results = data["results"]
        names = [str(r.get("command", i)) for i, r in enumerate(results)]
        chosen = _select(results, selector, names, path)
        times = chosen.get("times") if isinstance(chosen, dict) else None
        if not isinstance(times, list):
            raise InputError(f"{path}: hyperfine result has no 'times' list (export with --export-json)")
        return [_to_float(str(v), path) for v in times]
    if isinstance(data, dict) and isinstance(data.get("benchmarks"), list):     # pytest-benchmark
        benches = data["benchmarks"]
        names = [str(bm.get("name", i)) for i, bm in enumerate(benches)]
        chosen = _select(benches, selector, names, path)
        raw = chosen.get("stats", {}).get("data") if isinstance(chosen, dict) else None
        if not isinstance(raw, list):
            raise InputError(f"{path}: benchmark has no raw data; rerun pytest-benchmark with --benchmark-save-data")
        return [_to_float(str(v), path) for v in raw]
    if isinstance(data, dict) and isinstance(data.get("times"), list):
        return [_to_float(str(v), path) for v in data["times"]]
    raise InputError(f"{path}: unrecognized JSON layout")


def parse_csv(path: str, text: str, column: Optional[str], delimiter: str) -> List[float]:
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    if not reader.fieldnames:
        raise InputError(f"{path}: empty CSV")
    if column is None:
        raise InputError(f"{path}: CSV input needs --column (columns: {', '.join(reader.fieldnames[:10])})")
    if column not in reader.fieldnames:
        raise InputError(f"{path}: no column {column!r} (columns: {', '.join(reader.fieldnames[:10])})")
    values = []
    for line_no, row in enumerate(reader, start=2):
        cell = (row.get(column) or "").strip()
        if cell:
            values.append(_to_float(cell, f"{path}:{line_no}"))
    return values


def load_sample(path: str, selector: Optional[str], column: Optional[str], delimiter: str) -> List[float]:
    p = Path(path)
    if not p.is_file():
        raise InputError(f"{path}: file not found")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"{path}: cannot read ({exc.__class__.__name__})") from None
    stripped = text.lstrip()
    if p.suffix.lower() == ".json" or stripped.startswith(("{", "[")):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError(f"{path}: invalid JSON ({exc.msg} at line {exc.lineno})") from None
        return parse_json(path, data, selector)
    if p.suffix.lower() in (".csv", ".tsv") or column is not None:
        return parse_csv(path, text, column, "\t" if p.suffix.lower() == ".tsv" else delimiter)
    values: List[float] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        content = line.split("#", 1)[0]
        for token in content.replace(",", " ").split():
            values.append(_to_float(token, f"{path}:{line_no}"))
    return values


# --- report -------------------------------------------------------------------------------

def finite_or_text(obj: object) -> object:
    """Replace non-finite floats with strings so the JSON output stays standard."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return "nan" if math.isnan(obj) else ("inf" if obj > 0 else "-inf")
    if isinstance(obj, dict):
        return {k: finite_or_text(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [finite_or_text(v) for v in obj]
    return obj


def fmt(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:.6g}"


def fmt_p(p: float) -> str:
    return "< 1e-300" if p == 0.0 else f"{p:.3g}"


def compare(a: List[float], b: List[float], args: argparse.Namespace) -> Dict[str, object]:
    stats_a, stats_b = describe(a), describe(b)
    welch = welch_log(a, b, args.level)
    mw = mann_whitney(a, b)
    boot = bootstrap_median_ratio(a, b, args.level, args.bootstrap, args.seed)
    v = verdict(welch["ci_low"], welch["ci_high"], args.threshold, args.higher_is_better)
    hints: List[str] = []
    for label, sample, st in (("baseline", a, stats_a), ("candidate", b, stats_b)):
        if st["n"] < 10:
            hints.append(f"{label}: only {st['n']} values; intervals are wide and normal approximations rough")
        if not math.isnan(st["cv_percent"]) and st["cv_percent"] > args.noisy_cv:
            hints.append(f"{label}: coefficient of variation {st['cv_percent']:.1f}% exceeds {args.noisy_cv:g}%; "
                         "check for background load, frequency scaling or mixed cold and warm runs")
        rho = spearman_with_order(sample) if st["n"] >= 10 else None
        if rho is not None and abs(rho) >= 0.5:
            hints.append(f"{label}: values {'rise' if rho > 0 else 'fall'} with run order (Spearman {rho:.2f}); "
                         "warm-up or drift not removed? Interleave runs and drop warm-up with --drop-first")
        if st["outliers"]:
            hints.append(f"{label}: {st['outliers']} value(s) outside 1.5 IQR; look at them before trusting means")
    welch_sig = welch["ci_high"] < 1.0 or welch["ci_low"] > 1.0
    if welch_sig != (mw["p"] < 1.0 - args.level):
        hints.append("Welch and Mann-Whitney disagree about significance; inspect the distributions")
    if boot is not None:
        boot_sig = boot["ci_high"] < 1.0 or boot["ci_low"] > 1.0
        if boot_sig != welch_sig:
            hints.append("the median bootstrap and the geometric-mean interval disagree; the distributions may differ in shape")
    change = (welch["ratio"] - 1.0) * 100.0
    return {"direction": "higher is better" if args.higher_is_better else "lower is better",
            "level": args.level, "threshold_percent": args.threshold,
            "dropped_first": args.drop_first,
            "baseline": stats_a, "candidate": stats_b,
            "welch_log": welch, "mann_whitney": mw, "bootstrap_median_ratio": boot,
            "change_percent": change, "verdict": v, "hints": hints}


def print_text(result: Dict[str, object], names: Tuple[str, str]) -> None:
    a, b = result["baseline"], result["candidate"]
    level = result["level"]
    print(f"Benchmark comparison ({result['direction']}; ratio = candidate / baseline)")
    print(f"  baseline:  {names[0]}")
    print(f"  candidate: {names[1]}")
    if result["dropped_first"]:
        print(f"  dropped the first {result['dropped_first']} value(s) of each sample as warm-up")
    rows = [("samples", "n"), ("median", "median"), ("mean", "mean"), ("geometric mean", "geometric_mean"),
            ("q1 / q3", None), ("stdev", "stdev"), ("cv %", "cv_percent"), ("min / max", None),
            ("outliers (1.5 IQR)", "outliers")]
    print(f"\n  {'':20}{'baseline':>16}{'candidate':>16}")
    for label, key in rows:
        if label == "q1 / q3":
            va, vb = f"{fmt(a['q1'])} / {fmt(a['q3'])}", f"{fmt(b['q1'])} / {fmt(b['q3'])}"
        elif label == "min / max":
            va, vb = f"{fmt(a['min'])} / {fmt(a['max'])}", f"{fmt(b['min'])} / {fmt(b['max'])}"
        else:
            va, vb = fmt(a[key]) if key != "n" else str(a[key]), fmt(b[key]) if key != "n" else str(b[key])
        print(f"  {label:20}{va:>16}{vb:>16}")
    w, mw, bs = result["welch_log"], result["mann_whitney"], result["bootstrap_median_ratio"]
    pct = int(round(level * 100))
    print(f"\n  ratio of geometric means  {w['ratio']:.4f}  {pct}% CI [{w['ci_low']:.4f}, {w['ci_high']:.4f}]"
          f"  Welch t on logs: t={w['t']:.3g}, df={w['df']:.1f}, p={fmt_p(w['p'])}")
    if bs is not None:
        print(f"  ratio of medians          {bs['ratio']:.4f}  {pct}% CI [{bs['ci_low']:.4f}, {bs['ci_high']:.4f}]"
              f"  bootstrap, {bs['resamples']} resamples, seed {bs['seed']}")
    print(f"  Mann-Whitney U            U={mw['u']:g}  p={fmt_p(mw['p'])} ({mw['method']})")
    change = result["change_percent"]
    lo, hi = (w["ci_low"] - 1.0) * 100.0, (w["ci_high"] - 1.0) * 100.0
    threshold = result["threshold_percent"]
    band = f", threshold +/-{threshold:g}%" if threshold else ""
    print(f"\nVerdict: {result['verdict']} (candidate {change:+.2f}% vs baseline, CI {lo:+.2f}% to {hi:+.2f}%{band})")
    for hint in result["hints"]:
        print(f"  hint: {hint}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bench_compare.py",
        description="Compare two independent samples of benchmark measurements (baseline A, candidate B): "
                    "Welch t-test on logs, Mann-Whitney U and a bootstrap of the median ratio.",
        epilog="Examples:\n"
               "  bench_compare.py base.txt new.txt --drop-first 3 --threshold 2\n"
               "  bench_compare.py bench.json bench.json --select-a 0 --select-b 1 --fail-on-regression\n"
               "  bench_compare.py runs.csv runs_new.csv --column seconds --json\n"
               "  bench_compare.py --a-values 912,905,931,899 --b-values 980,1002,975,990 --higher-is-better\n"
               "Exit codes: 0 computed, 1 --fail-on-regression or --require-improvement tripped, 2 bad input.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", nargs="?", help="file with the baseline sample (A)")
    parser.add_argument("candidate", nargs="?", help="file with the candidate sample (B)")
    parser.add_argument("--a-values", help="baseline values inline, comma or space separated")
    parser.add_argument("--b-values", help="candidate values inline, comma or space separated")
    parser.add_argument("--select-a", help="entry in a multi-result JSON for A: index or command/name")
    parser.add_argument("--select-b", help="entry in a multi-result JSON for B: index or command/name")
    parser.add_argument("--column", help="CSV column holding the measurements")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter (default ',')")
    parser.add_argument("--drop-first", type=int, default=0, help="discard the first N values of each sample (warm-up)")
    parser.add_argument("--higher-is-better", action="store_true", help="measurements are throughput-like (default: lower is better)")
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="practical threshold in percent; enables 'equivalent' and requires changes beyond it")
    parser.add_argument("--level", type=float, default=0.95, help="confidence level (default 0.95)")
    parser.add_argument("--bootstrap", type=int, default=4000, help="bootstrap resamples, 0 to skip (default 4000)")
    parser.add_argument("--seed", type=int, default=12345, help="bootstrap seed (default 12345)")
    parser.add_argument("--noisy-cv", type=float, default=10.0,
                        help="hint when a sample's coefficient of variation exceeds this percent (default 10)")
    parser.add_argument("--fail-on-regression", action="store_true", help="exit 1 when the verdict is regression")
    parser.add_argument("--require-improvement", action="store_true", help="exit 1 unless the verdict is improvement")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        if not 0.5 < args.level < 1.0:
            raise InputError("--level must be between 0.5 and 1")
        if args.threshold < 0 or args.threshold >= 100:
            raise InputError("--threshold must be in [0, 100)")
        if args.drop_first < 0 or args.bootstrap < 0:
            raise InputError("--drop-first and --bootstrap must not be negative")
        if args.a_values is not None:
            a, name_a = parse_inline(args.a_values, "--a-values"), "--a-values"
        elif args.baseline:
            a, name_a = load_sample(args.baseline, args.select_a, args.column, args.delimiter), args.baseline
        else:
            raise InputError("give the baseline as a file or with --a-values")
        b_file = args.candidate if args.a_values is None else (args.candidate or args.baseline)
        if args.b_values is not None:
            b, name_b = parse_inline(args.b_values, "--b-values"), "--b-values"
        elif b_file:
            if args.a_values is None and args.baseline and Path(args.baseline).resolve() == Path(b_file).resolve() \
                    and args.select_a == args.select_b:
                raise InputError("baseline and candidate are the same entry; use --select-a and --select-b")
            b, name_b = load_sample(b_file, args.select_b, args.column, args.delimiter), b_file
        else:
            raise InputError("give the candidate as a file or with --b-values")
        if args.select_a is not None and name_a != "--a-values":
            name_a = f"{name_a} [{args.select_a}]"
        if args.select_b is not None and name_b != "--b-values":
            name_b = f"{name_b} [{args.select_b}]"
        a, b = a[args.drop_first:], b[args.drop_first:]
        for label, sample in (("baseline", a), ("candidate", b)):
            if len(sample) < 2:
                raise InputError(f"{label}: need at least 2 values after --drop-first, got {len(sample)}")
            if min(sample) <= 0:
                raise InputError(f"{label}: all values must be positive (times, rates); found {min(sample):g}")
        result = compare(a, b, args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        result["baseline_source"], result["candidate_source"] = name_a, name_b
        print(json.dumps(finite_or_text(result), indent=2, sort_keys=True, allow_nan=False))
    else:
        print_text(result, (name_a, name_b))
    if args.fail_on_regression and result["verdict"] == "regression":
        return 1
    if args.require_improvement and result["verdict"] != "improvement":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
