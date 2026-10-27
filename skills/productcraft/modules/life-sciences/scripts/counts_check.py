#!/usr/bin/env python3
"""Check a bulk count matrix and its sample sheet before differential expression.

Read-only, standard library only, no network. Reports:
  * orientation (genes as rows or columns) and matrix shape
  * non-integer, negative or missing values (counts are required, not TPM or logs)
  * library sizes, detected genes per sample, and all-zero genes and samples
  * samples present in one input but not the other
  * replicates per group, and groups too small to test
  * factors that are confounded with each other, or constant
  * a rank check of the design matrix built from the named factors

Exit codes: 0 no errors, 1 errors (or warnings with --strict), 2 bad usage.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
from itertools import combinations

MAX_LISTED = 8


def open_text(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", newline="", errors="replace")
    return open(path, "rt", newline="", errors="replace")


def sniff_delimiter(path: str) -> str:
    with open_text(path) as handle:
        first = handle.readline()
    if "\t" in first:
        return "\t"
    if "," in first:
        return ","
    return "\t"


def read_table(path: str):
    """Read a delimited table; return (header, rows) with rows as lists of strings."""
    delim = sniff_delimiter(path)
    with open_text(path) as handle:
        reader = csv.reader(handle, delimiter=delim)
        rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError(f"{path}: no data rows")
    return rows[0], rows[1:]


def to_number(text: str):
    text = text.strip()
    if text in ("", "NA", "NaN", "nan", "null", "None", "."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


class Finding:
    def __init__(self, level: str, code: str, message: str):
        self.level, self.code, self.message = level, code, message

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message}

    def text(self) -> str:
        return f"  {self.level.upper():7} {self.code}: {self.message}"


def summarize(names) -> str:
    names = list(names)
    shown = ", ".join(str(n) for n in names[:MAX_LISTED])
    return shown + (f", ... ({len(names)} in total)" if len(names) > MAX_LISTED else "")


def load_counts(path: str, orientation: str):
    """Return (sample_ids, gene_ids, columns) where columns[sample] is a list of values."""
    header, rows = read_table(path)
    row_labels = [r[0] for r in rows]
    col_labels = header[1:]
    values = []
    bad_cells = 0
    for r in rows:
        cells = r[1:]
        if len(cells) < len(col_labels):
            cells = cells + [""] * (len(col_labels) - len(cells))
        parsed = [to_number(c) for c in cells[:len(col_labels)]]
        bad_cells += sum(1 for p in parsed if p is None)
        values.append(parsed)

    guessed = False
    if orientation == "auto":
        # Count matrices are written both ways; genes far outnumber samples in practice,
        # so the longer axis is taken to be the genes.
        guessed = True
        orientation = "genes-in-rows" if len(row_labels) >= len(col_labels) else "samples-in-rows"

    if orientation == "genes-in-rows":
        sample_ids, gene_ids = col_labels, row_labels
        columns = {s: [values[g][j] for g in range(len(gene_ids))] for j, s in enumerate(sample_ids)}
    else:
        sample_ids, gene_ids = row_labels, col_labels
        columns = {s: list(values[i]) for i, s in enumerate(sample_ids)}

    ambiguous = guessed and max(len(row_labels), len(col_labels)) < 10 * max(
        1, min(len(row_labels), len(col_labels)))
    return sample_ids, gene_ids, columns, orientation, bad_cells, ambiguous


def load_samples(path: str, sample_col: str | None):
    header, rows = read_table(path)
    key_index = 0
    if sample_col:
        if sample_col not in header:
            raise ValueError(f"{path}: column '{sample_col}' not found; columns are {header}")
        key_index = header.index(sample_col)
    table = {}
    order = []
    for r in rows:
        cells = r + [""] * (len(header) - len(r))
        key = cells[key_index].strip()
        table[key] = {h: cells[i].strip() for i, h in enumerate(header)}
        order.append(key)
    return header, order, table


def design_rank(rows) -> int:
    """Rank of a dense float matrix by Gaussian elimination with partial pivoting."""
    matrix = [list(map(float, row)) for row in rows]
    if not matrix:
        return 0
    n_cols = len(matrix[0])
    rank = 0
    pivot_row = 0
    for col in range(n_cols):
        best = None
        for r in range(pivot_row, len(matrix)):
            if best is None or abs(matrix[r][col]) > abs(matrix[best][col]):
                best = r
        if best is None or abs(matrix[best][col]) < 1e-9:
            continue
        matrix[pivot_row], matrix[best] = matrix[best], matrix[pivot_row]
        pivot = matrix[pivot_row][col]
        for r in range(len(matrix)):
            if r == pivot_row:
                continue
            factor = matrix[r][col] / pivot
            if factor:
                matrix[r] = [a - factor * b for a, b in zip(matrix[r], matrix[pivot_row])]
        rank += 1
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    return rank


def build_design(samples, meta, factors):
    """Full dummy-coded design matrix (intercept plus one column per non-reference level)."""
    columns = [[1.0] * len(samples)]
    labels = ["(intercept)"]
    for factor in factors:
        levels = sorted({meta[s].get(factor, "") for s in samples})
        for level in levels[1:]:                     # first level is the reference
            columns.append([1.0 if meta[s].get(factor, "") == level else 0.0 for s in samples])
            labels.append(f"{factor}[{level}]")
    rows = [[columns[c][i] for c in range(len(columns))] for i in range(len(samples))]
    return rows, labels


def check(args) -> dict:
    findings: list[Finding] = []

    def add(level, code, message):
        findings.append(Finding(level, code, message))

    sample_ids, gene_ids, columns, orientation, bad_cells, ambiguous = load_counts(
        args.counts, args.orientation)
    add("info", "SHAPE", f"{len(gene_ids)} genes x {len(sample_ids)} samples, read as {orientation}")
    if ambiguous:
        add("warning", "AMBIGUOUS_ORIENTATION",
            f"the two dimensions are of similar size, so '{orientation}' is only a guess; "
            f"pass --orientation to state the layout")

    if len(set(sample_ids)) != len(sample_ids):
        add("error", "DUP_SAMPLES", "duplicate sample names in the count matrix")
    if len(set(gene_ids)) != len(gene_ids):
        add("error", "DUP_GENES", "duplicate gene identifiers in the count matrix")
    if bad_cells:
        add("error", "MISSING", f"{bad_cells} cell(s) are missing or not numeric; counts must be complete")

    non_integer = negative = 0
    lib_sizes = {}
    detected = {}
    zero_samples = []
    for s in sample_ids:
        vals = [v for v in columns[s] if v is not None]
        total = 0.0
        det = 0
        for v in vals:
            if v < 0:
                negative += 1
            elif v > 0:
                det += 1
            if not float(v).is_integer():
                non_integer += 1
            total += v
        lib_sizes[s] = total
        detected[s] = det
        if total == 0:
            zero_samples.append(s)

    if negative:
        add("error", "NEGATIVE", f"{negative} negative value(s); counts cannot be negative")
    if non_integer:
        add("error", "NON_INTEGER",
            f"{non_integer} non-integer value(s): this looks like TPM, FPKM, CPM or log values, "
            f"not raw counts (estimated counts must be rounded first)")
    if zero_samples:
        add("error", "EMPTY_SAMPLE", f"sample(s) with zero total counts: {summarize(zero_samples)}")

    zero_genes = 0
    for g in range(len(gene_ids)):
        if all((columns[s][g] or 0) == 0 for s in sample_ids):
            zero_genes += 1
    if zero_genes:
        add("warning", "ZERO_GENES",
            f"{zero_genes} gene(s) are zero in every sample; filter them before fitting")

    sizes = [v for v in lib_sizes.values() if v > 0]
    if sizes:
        smallest, largest = min(sizes), max(sizes)
        add("info", "LIBRARY_SIZES",
            f"library sizes {smallest:,.0f} to {largest:,.0f} "
            f"(ratio {largest / smallest:.1f}x); median detected genes "
            f"{sorted(detected.values())[len(detected) // 2]:,}")
        if largest / smallest > 10:
            add("warning", "DEPTH_SPREAD",
                "library sizes differ by more than tenfold; check for failed libraries")

    meta_header, meta_order, meta = (None, [], {})
    factors = [f.strip() for f in args.design.split(",") if f.strip()] if args.design else []
    matched = sample_ids

    if args.samples:
        meta_header, meta_order, meta = load_samples(args.samples, args.sample_col)
        only_counts = [s for s in sample_ids if s not in meta]
        only_meta = [s for s in meta_order if s not in set(sample_ids)]
        if only_counts:
            add("error", "UNMATCHED_COUNTS",
                f"sample(s) in the matrix but not the sample sheet: {summarize(only_counts)}")
        if only_meta:
            add("warning", "UNMATCHED_META",
                f"sample(s) in the sample sheet but not the matrix: {summarize(only_meta)}")
        matched = [s for s in sample_ids if s in meta]
        if len(set(meta_order)) != len(meta_order):
            add("error", "DUP_META", "duplicate sample identifiers in the sample sheet")

        for factor in factors:
            if meta_header is not None and factor not in meta_header:
                add("error", "NO_FACTOR",
                    f"factor '{factor}' is not a column in the sample sheet; columns are {meta_header}")
        factors = [f for f in factors if meta_header is None or f in meta_header]

        for factor in factors:
            groups = {}
            for s in matched:
                groups.setdefault(meta[s].get(factor, ""), []).append(s)
            if "" in groups:
                add("error", "MISSING_LEVEL",
                    f"factor '{factor}' is empty for {len(groups[''])} sample(s)")
            if len(groups) < 2:
                add("error", "CONSTANT_FACTOR",
                    f"factor '{factor}' has one level; it cannot be tested or adjusted for")
            sizes_text = ", ".join(f"{k or '(empty)'}={len(v)}" for k, v in sorted(groups.items()))
            add("info", "GROUPS", f"{factor}: {sizes_text}")
            small = [k for k, v in groups.items() if len(v) < 2]
            if small:
                add("error", "NO_REPLICATES",
                    f"factor '{factor}' has level(s) with a single sample: {summarize(small)}")
            elif any(len(v) < 3 for v in groups.values()):
                add("warning", "FEW_REPLICATES",
                    f"factor '{factor}' has a level with two samples; dispersion estimates will be poor")

        for a, b in combinations(factors, 2):
            pairs = {(meta[s].get(a, ""), meta[s].get(b, "")) for s in matched}
            levels_a = {p[0] for p in pairs}
            levels_b = {p[1] for p in pairs}
            if len(levels_a) > 1 and len(levels_b) > 1 and len(pairs) == max(len(levels_a), len(levels_b)):
                add("error", "CONFOUNDED",
                    f"'{a}' and '{b}' are confounded: each level of one occurs with exactly one "
                    f"level of the other, so their effects cannot be separated")

        if factors and matched:
            rows, labels = build_design(matched, meta, factors)
            rank = design_rank(rows)
            if rank < len(labels):
                add("error", "RANK_DEFICIENT",
                    f"design ~{' + '.join(factors)} has {len(labels)} columns but rank {rank}; "
                    f"it is not full rank and cannot be fitted as written")
            else:
                add("info", "DESIGN",
                    f"design ~{' + '.join(factors)}: {len(labels)} columns, full rank, "
                    f"{len(matched)} samples ({len(matched) - rank} residual degrees of freedom)")
            if len(matched) <= len(labels):
                add("error", "NO_RESIDUAL_DF",
                    "there are no residual degrees of freedom: more coefficients than samples")

    return {
        "counts": args.counts,
        "samples": args.samples,
        "orientation": orientation,
        "n_genes": len(gene_ids),
        "n_samples": len(sample_ids),
        "n_matched": len(matched),
        "library_sizes": {s: lib_sizes[s] for s in sample_ids},
        "detected_genes": detected,
        "findings": findings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="counts_check.py",
        description="Check a bulk count matrix and sample sheet before differential expression.")
    parser.add_argument("--counts", required=True, help="count matrix, TSV or CSV (plain or .gz)")
    parser.add_argument("--samples", help="sample sheet, TSV or CSV (plain or .gz)")
    parser.add_argument("--sample-col", help="column in the sample sheet holding sample IDs (default: first)")
    parser.add_argument("--design", help="comma-separated factor columns, for example batch,condition")
    parser.add_argument("--orientation", choices=["auto", "genes-in-rows", "samples-in-rows"],
                        default="auto", help="matrix layout (default: guess)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when warnings remain")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    for path in (args.counts, args.samples):
        if path and not os.path.exists(path):
            print(f"error: file not found: {path}", file=sys.stderr)
            return 2
    if args.design and not args.samples:
        print("error: --design needs --samples", file=sys.stderr)
        return 2

    try:
        result = check(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    findings = result["findings"]
    errors = sum(1 for f in findings if f.level == "error")
    warnings = sum(1 for f in findings if f.level == "warning")

    if args.json:
        payload = {k: v for k, v in result.items() if k != "findings"}
        payload["findings"] = [f.as_dict() for f in findings]
        payload["errors"], payload["warnings"] = errors, warnings
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"counts: {result['counts']}")
        if result["samples"]:
            print(f"samples: {result['samples']}")
        for f in findings:
            print(f.text())
        print(f"\n{errors} error(s), {warnings} warning(s)")
        print("note: a clean result does not prove the design is sound; "
              "hidden batch structure is invisible here")

    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
