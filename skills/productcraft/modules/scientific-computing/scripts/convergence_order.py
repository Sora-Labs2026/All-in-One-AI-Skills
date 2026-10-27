#!/usr/bin/env python3
"""ProductCraft Scientific Computing: observed order of accuracy and discretization error.

Takes one scalar quantity of interest computed on several grids (or with several
time steps) and reports:

- with a known exact or reference value (--exact), or with error norms as the
  values (--errors): the error per level, the observed order between
  consecutive levels and a least-squares order over all levels;
- without one, for every consecutive triplet of levels: the convergence type
  (monotone, oscillatory or divergent), the observed order p (solved by fixed-point
  iteration, so the refinement ratio need not be constant), the Richardson
  extrapolated value, relative errors and the grid convergence index (GCI) with
  its asymptotic-range ratio;
- with only two levels and an assumed order (--assumed-order): Richardson
  extrapolation and a GCI with the larger safety factor two-level studies need.

Spacing comes from --h (any consistent unit) or from cell counts with --cells and
--dim (h = N^(-1/dim), a representative spacing for unstructured meshes).

Pure computation on the numbers given: no files, no network, deterministic.
Exit codes: 0 = converging and, if --expected-order is given, the finest observed
order is within --order-tol of it; 1 = oscillatory or divergent finest triplet,
non-decreasing errors, or an order mismatch; 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, List, Optional, Sequence

VERSION = "1.0.0"
MIN_RATIO = 1.3  # refinement ratios below this make the observed order unreliable


def parse_list(text: str, name: str) -> List[float]:
    try:
        values = [float(item) for item in text.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError(f"{name}: not a comma-separated list of numbers ({exc})") from None
    if any(not math.isfinite(v) for v in values):
        raise ValueError(f"{name}: values must be finite")
    return values


def spacings_from_cells(cells: Sequence[float], dim: int) -> List[float]:
    if dim not in (1, 2, 3):
        raise ValueError("--dim must be 1, 2 or 3")
    if any(n <= 0 for n in cells):
        raise ValueError("--cells must be positive")
    return [n ** (-1.0 / dim) for n in cells]


def sort_fine_to_coarse(h: Sequence[float], values: Sequence[float]) -> List[tuple]:
    if len(h) != len(values):
        raise ValueError("the spacing list and --values must have the same length")
    if len(h) < 2:
        raise ValueError("at least two refinement levels are needed")
    if any(x <= 0 for x in h):
        raise ValueError("spacings must be positive")
    pairs = sorted(zip(h, values), key=lambda pair: pair[0])
    for (h_a, _), (h_b, _) in zip(pairs, pairs[1:]):
        if math.isclose(h_a, h_b, rel_tol=1e-12):
            raise ValueError("spacings must be distinct")
    return pairs


def classify(e21: float, e32: float) -> str:
    """Convergence type from the ratio of successive changes (fine pair over coarse pair)."""
    if e32 == 0.0:
        return "undetermined"
    ratio = e21 / e32
    if 0.0 < ratio < 1.0:
        return "monotone"
    if -1.0 < ratio < 0.0:
        return "oscillatory"
    if ratio == 0.0:
        return "converged"
    return "divergent"


def observed_order(r21: float, r32: float, e21: float, e32: float,
                   max_iter: int = 500, tol: float = 1e-12) -> Optional[float]:
    """Fixed-point iteration for p with refinement ratios r21 (medium/fine) and r32 (coarse/medium)."""
    if e21 == 0.0 or e32 == 0.0:
        return None
    s = 1.0 if e32 / e21 > 0 else -1.0
    log_ratio = math.log(abs(e32 / e21))
    p = abs(log_ratio) / math.log(r21)
    for _ in range(max_iter):
        if p <= 1e-12:
            return None
        try:
            q = math.log((r21 ** p - s) / (r32 ** p - s))
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
        p_next = abs(log_ratio + q) / math.log(r21)
        if abs(p_next - p) < tol * max(1.0, p):
            return p_next
        p = p_next
    return None


def relative(a: float, b: float) -> Optional[float]:
    """|a - b| / |a|, or None when a is zero."""
    return None if a == 0.0 else abs((a - b) / a)


def triplet_analysis(fine: tuple, medium: tuple, coarse: tuple, safety: float) -> Dict[str, object]:
    (h1, f1), (h2, f2), (h3, f3) = fine, medium, coarse
    r21, r32 = h2 / h1, h3 / h2
    e21, e32 = f2 - f1, f3 - f2
    kind = classify(e21, e32)
    result: Dict[str, object] = {"h": [h1, h2, h3], "values": [f1, f2, f3],
                                 "ratios": [round(r21, 6), round(r32, 6)], "type": kind, "notes": []}
    if min(r21, r32) < MIN_RATIO:
        result["notes"].append(f"a refinement ratio is below {MIN_RATIO}; the observed order is unreliable")
    if kind == "converged":
        result["notes"].append("fine and medium values are identical: below the precision of the data, "
                               "or the quantity does not depend on resolution")
        return result
    if kind in ("divergent", "undetermined"):
        result["notes"].append("changes do not shrink with refinement: no order or error band reported")
        return result
    p = observed_order(r21, r32, e21, e32)
    if p is None:
        result["notes"].append("the order iteration did not converge")
        return result
    result["observed_order"] = round(p, 6)
    if kind == "oscillatory":
        result["notes"].append("oscillatory convergence: the order and error band are indicative only")
    rp21, rp32 = r21 ** p, r32 ** p
    extrapolated = (rp21 * f1 - f2) / (rp21 - 1.0)
    ea21, ea32 = relative(f1, f2), relative(f2, f3)
    result["extrapolated"] = extrapolated
    result["approx_relative_error_fine"] = ea21
    result["extrapolated_relative_error_fine"] = relative(extrapolated, f1)
    if ea21 is None or ea32 is None:
        result["notes"].append("a value is zero, so relative errors and the GCI are undefined; "
                               "report the absolute difference instead")
        result["abs_band_fine"] = safety * abs(e21) / (rp21 - 1.0)
        return result
    gci21 = safety * ea21 / (rp21 - 1.0)
    gci32 = safety * ea32 / (rp32 - 1.0)
    result["gci_fine"] = gci21
    result["gci_medium"] = gci32
    result["abs_band_fine"] = gci21 * abs(f1)
    result["asymptotic_ratio"] = None if gci21 == 0.0 else gci32 / (rp21 * gci21)
    return result


def exact_analysis(pairs: Sequence[tuple], exact: float) -> Dict[str, object]:
    errors = [abs(value - exact) for _, value in pairs]
    result: Dict[str, object] = {"errors": errors, "pairwise_orders": [], "notes": []}
    if any(e == 0.0 for e in errors):
        result["notes"].append("an error is exactly zero: orders involving it are undefined")
    orders = []
    for (h_f, _), (h_c, _), e_f, e_c in zip(pairs, pairs[1:], errors, errors[1:]):
        if e_f > 0.0 and e_c > 0.0:
            orders.append(round(math.log(e_c / e_f) / math.log(h_c / h_f), 6))
        else:
            orders.append(None)
    result["pairwise_orders"] = orders
    points = [(math.log(h), math.log(e)) for (h, _), e in zip(pairs, errors) if e > 0.0]
    if len(points) >= 2:
        n = len(points)
        mean_x = sum(x for x, _ in points) / n
        mean_y = sum(y for _, y in points) / n
        sxx = sum((x - mean_x) ** 2 for x, _ in points)
        sxy = sum((x - mean_x) * (y - mean_y) for x, y in points)
        result["fitted_order"] = round(sxy / sxx, 6)
        result["fitted_constant"] = math.exp(mean_y - (sxy / sxx) * mean_x)
    result["errors_decrease"] = all(e_f < e_c for e_f, e_c in zip(errors, errors[1:]))
    return result


def analyse(pairs: Sequence[tuple], exact: Optional[float], assumed: Optional[float],
            safety: Optional[float], errors_only: bool = False) -> Dict[str, object]:
    report: Dict[str, object] = {"tool": "convergence_order", "version": VERSION,
                                 "levels_fine_to_coarse": [{"h": h, "value": v} for h, v in pairs]}
    if errors_only:
        if any(v < 0 for _, v in pairs):
            raise ValueError("--errors expects non-negative error norms")
        report["errors_only"] = True
        report["exact"] = 0.0
        report["exact_analysis"] = exact_analysis(pairs, 0.0)
        return report
    if exact is not None:
        report["exact"] = exact
        report["exact_analysis"] = exact_analysis(pairs, exact)
    if len(pairs) >= 3:
        factor = 1.25 if safety is None else safety
        report["safety_factor"] = factor
        report["triplets"] = [triplet_analysis(pairs[i], pairs[i + 1], pairs[i + 2], factor)
                              for i in range(len(pairs) - 2)]
    elif assumed is not None:
        factor = 3.0 if safety is None else safety
        (h1, f1), (h2, f2) = pairs[0], pairs[1]
        rp = (h2 / h1) ** assumed
        two: Dict[str, object] = {"assumed_order": assumed, "safety_factor": factor,
                                  "extrapolated": (rp * f1 - f2) / (rp - 1.0)}
        ea = relative(f1, f2)
        if ea is not None:
            two["gci_fine"] = factor * ea / (rp - 1.0)
            two["abs_band_fine"] = two["gci_fine"] * abs(f1)
        report["two_level"] = two
    elif exact is None:
        raise ValueError("two levels need --exact or --assumed-order; three or more levels give an observed order")
    return report


def verdict(report: Dict[str, object], expected: Optional[float], tol: float) -> List[str]:
    problems: List[str] = []
    observed: Optional[float] = None
    if "triplets" in report:
        finest = report["triplets"][0]
        if finest["type"] != "monotone":
            problems.append(f"finest triplet convergence is {finest['type']}")
        observed = finest.get("observed_order")
    if "exact_analysis" in report:
        exact = report["exact_analysis"]
        if not exact["errors_decrease"]:
            problems.append("errors against the exact value do not decrease with refinement")
        finest_pair = exact["pairwise_orders"][0] if exact["pairwise_orders"] else None
        observed = finest_pair if finest_pair is not None else observed
    if expected is not None:
        if observed is None:
            problems.append("no observed order available to compare with --expected-order")
        elif abs(observed - expected) > tol:
            problems.append(f"observed order {observed:.3f} differs from expected {expected:g} by more than {tol:g}")
    report["observed_order_used"] = observed
    report["problems"] = problems
    report["verdict"] = "PASS" if not problems else "CHECK"
    return problems


def fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_text(report: Dict[str, object]) -> str:
    lines = ["Convergence analysis (levels fine to coarse)"]
    for level in report["levels_fine_to_coarse"]:
        lines.append(f"  h={fmt(level['h'])}  value={fmt(level['value'])}")
    if "exact_analysis" in report:
        exact = report["exact_analysis"]
        if report.get("errors_only"):
            lines.append("Values are error norms against an exact solution:")
        else:
            lines.append(f"Against exact value {fmt(report['exact'])}:")
        lines.append("  errors: " + ", ".join(fmt(e) for e in exact["errors"]))
        lines.append("  pairwise orders (fine pair first): " + ", ".join(fmt(o) for o in exact["pairwise_orders"]))
        lines.append(f"  least-squares order: {fmt(exact.get('fitted_order'))}")
    for index, triplet in enumerate(report.get("triplets", [])):
        lines.append(f"Triplet {index + 1} (h={', '.join(fmt(h) for h in triplet['h'])}): {triplet['type']}")
        if "observed_order" in triplet:
            lines.append(f"  observed order p = {fmt(triplet['observed_order'])}; "
                         f"extrapolated value = {fmt(triplet['extrapolated'])}")
        if "gci_fine" in triplet:
            lines.append(f"  GCI fine = {triplet['gci_fine'] * 100:.4g}% (band +/- {fmt(triplet['abs_band_fine'])}); "
                         f"asymptotic ratio = {fmt(triplet['asymptotic_ratio'])} (near 1 is good)")
        for note in triplet["notes"]:
            lines.append(f"  note: {note}")
    if "two_level" in report:
        two = report["two_level"]
        lines.append(f"Two levels with assumed order {fmt(two['assumed_order'])}: extrapolated "
                     f"{fmt(two['extrapolated'])}, GCI fine {fmt(two.get('gci_fine'))} "
                     f"(safety factor {fmt(two['safety_factor'])})")
    lines.append(f"Verdict: {report['verdict']}")
    for problem in report["problems"]:
        lines.append(f"  - {problem}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Observed order of accuracy, Richardson extrapolation and grid convergence index "
                    "for one quantity computed at several resolutions.")
    spacing = parser.add_mutually_exclusive_group(required=True)
    spacing.add_argument("--h", help="comma-separated grid spacings or time steps, any order")
    spacing.add_argument("--cells", help="comma-separated cell or node counts (use with --dim)")
    parser.add_argument("--dim", type=int, help="spatial dimension for --cells (1, 2 or 3)")
    parser.add_argument("--values", required=True, help="comma-separated quantity values, same order as the spacing")
    parser.add_argument("--exact", type=float, help="exact or reference value of the quantity, if known")
    parser.add_argument("--errors", action="store_true",
                        help="--values are error norms against an exact solution (for example from a "
                             "manufactured solution); only the order analysis runs")
    parser.add_argument("--expected-order", type=float, help="formal order of the scheme to compare with")
    parser.add_argument("--order-tol", type=float, default=0.2,
                        help="allowed absolute difference between observed and expected order (default 0.2)")
    parser.add_argument("--assumed-order", type=float, help="order to assume when only two levels exist")
    parser.add_argument("--safety-factor", type=float,
                        help="GCI safety factor (default 1.25 with an observed order, 3.0 with an assumed one)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        values = parse_list(args.values, "--values")
        if args.h is not None:
            h = parse_list(args.h, "--h")
        else:
            if args.dim is None:
                raise ValueError("--cells needs --dim")
            h = spacings_from_cells(parse_list(args.cells, "--cells"), args.dim)
        if args.order_tol <= 0:
            raise ValueError("--order-tol must be positive")
        if args.safety_factor is not None and args.safety_factor < 1.0:
            raise ValueError("--safety-factor must be at least 1")
        if args.assumed_order is not None and args.assumed_order <= 0:
            raise ValueError("--assumed-order must be positive")
        if args.errors and args.exact is not None:
            raise ValueError("--errors and --exact are mutually exclusive")
        pairs = sort_fine_to_coarse(h, values)
        report = analyse(pairs, args.exact, args.assumed_order, args.safety_factor, args.errors)
    except ValueError as exc:
        parser.error(str(exc))
        return 2  # pragma: no cover - parser.error exits
    problems = verdict(report, args.expected_order, args.order_tol)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
