#!/usr/bin/env python3
"""Check genomic interval files, and convert between coordinate conventions.

Read-only, standard library only, no network. Two subcommands:

  check    Inspect BED-like and GFF/GTF files: coordinate convention, bounds,
           sort order, contig naming style, zero-length, inverted and duplicate
           intervals, and (with --genome) unknown contigs and coordinates past
           the end of a contig.
  convert  Print a region in both the 1-based closed and the 0-based half-open
           form, so a boundary is converted once and verified.

Exit codes: 0 no errors, 1 errors (or warnings with --strict), 2 bad usage.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys

BED_SUFFIXES = (".bed", ".narrowpeak", ".broadpeak", ".gappedpeak", ".bedgraph", ".peaks")
GFF_SUFFIXES = (".gff", ".gff3", ".gtf")
REGION_RE = re.compile(r"^(?P<contig>[^:]+):(?P<start>[0-9,]+)-(?P<end>[0-9,]+)$")
MAX_REPORTED = 5


class Finding:
    """One problem found in one file."""

    def __init__(self, level: str, code: str, message: str, line: int | None = None):
        self.level = level  # "error" or "warning"
        self.code = code
        self.message = message
        self.line = line

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message, "line": self.line}

    def text(self) -> str:
        where = f" (line {self.line})" if self.line else ""
        return f"  {self.level.upper():7} {self.code}: {self.message}{where}"


def open_text(path: str):
    """Open a plain or gzip-compressed text file."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", errors="replace")
    return open(path, "rt", errors="replace")


def guess_format(path: str, explicit: str | None) -> str:
    if explicit and explicit != "auto":
        return explicit
    name = path[:-3] if path.endswith(".gz") else path
    lower = name.lower()
    if lower.endswith(GFF_SUFFIXES):
        return "gff"
    if lower.endswith(BED_SUFFIXES):
        return "bed"
    return "bed"


def read_sizes(path: str) -> dict:
    """Read a chrom.sizes or .fai file: first column name, second column length."""
    sizes = {}
    with open_text(path) as handle:
        for raw in handle:
            if not raw.strip() or raw.startswith("#"):
                continue
            fields = raw.rstrip("\n").split("\t") if "\t" in raw else raw.split()
            if len(fields) < 2:
                continue
            try:
                sizes[fields[0]] = int(fields[1])
            except ValueError:
                continue
    return sizes


def naming_style(contigs) -> str:
    """Describe how contigs are named, so two files can be compared."""
    prefixed = sum(1 for c in contigs if c.startswith("chr"))
    if not contigs:
        return "unknown"
    if prefixed == len(contigs):
        return "chr-prefixed"
    if prefixed == 0:
        return "plain"
    return "mixed"


def parse_record(fields, fmt):
    """Return (contig, start0, end0, strand) in 0-based half-open form, or None."""
    if fmt == "gff":
        if len(fields) < 5:
            return None
        start, end = int(fields[3]), int(fields[4])
        strand = fields[6] if len(fields) > 6 else "."
        return fields[0], start - 1, end, strand
    if len(fields) < 3:
        return None
    start, end = int(fields[1]), int(fields[2])
    strand = fields[5] if len(fields) > 5 else "."
    return fields[0], start, end, strand


def check_file(path: str, fmt: str, sizes: dict | None) -> dict:
    """Inspect one interval file and return a summary with findings."""
    findings: list[Finding] = []
    counts = {"records": 0, "zero_length": 0, "inverted": 0, "negative": 0,
              "duplicates": 0, "unknown_contig": 0, "past_end": 0, "unparsed": 0}
    contigs: list[str] = []
    seen_contigs = set()
    seen_intervals = set()
    unsorted_at = None
    revisited_at = None
    prev = None
    strands = set()

    def add(level, code, message, line=None):
        if sum(1 for f in findings if f.code == code) < MAX_REPORTED:
            findings.append(Finding(level, code, message, line))

    with open_text(path) as handle:
        for lineno, raw in enumerate(handle, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.startswith("#") or line.startswith("track") or line.startswith("browser"):
                continue
            fields = line.split("\t")
            if len(fields) == 1:
                fields = line.split()
            try:
                parsed = parse_record(fields, fmt)
            except ValueError:
                parsed = None
            if parsed is None:
                counts["unparsed"] += 1
                add("error", "UNPARSED", f"cannot read coordinates from {len(fields)} fields", lineno)
                continue

            contig, start, end, strand = parsed
            counts["records"] += 1
            strands.add(strand)

            if contig not in seen_contigs:
                seen_contigs.add(contig)
                contigs.append(contig)
            elif prev is not None and prev[0] != contig and revisited_at is None:
                revisited_at = lineno          # this contig reappears after another one

            if start < 0:
                counts["negative"] += 1
                add("error", "NEGATIVE", f"negative start {start} on {contig}", lineno)
            if end < start:
                counts["inverted"] += 1
                add("error", "INVERTED", f"end {end} before start {start} on {contig}", lineno)
            elif end == start:
                counts["zero_length"] += 1
                add("warning", "ZERO_LENGTH",
                    f"zero-length interval at {contig}:{start} (an insertion point, or a 1-based "
                    f"start used as a 0-based start)", lineno)

            key = (contig, start, end, strand)
            if key in seen_intervals:
                counts["duplicates"] += 1
                add("warning", "DUPLICATE", f"repeated interval {contig}:{start}-{end}", lineno)
            else:
                seen_intervals.add(key)

            if prev is not None and prev[0] == contig and start < prev[1] and unsorted_at is None:
                unsorted_at = lineno
            prev = (contig, start)

            if sizes is not None:
                if contig not in sizes:
                    counts["unknown_contig"] += 1
                    add("error", "UNKNOWN_CONTIG",
                        f"{contig} is not in the sizes file (wrong build, or a naming mismatch)", lineno)
                elif end > sizes[contig]:
                    counts["past_end"] += 1
                    add("error", "PAST_END",
                        f"{contig}:{start}-{end} extends past the contig length {sizes[contig]}", lineno)

    if counts["records"] == 0:
        findings.append(Finding("error", "EMPTY", "no interval records found"))
    if unsorted_at is not None:
        findings.append(Finding("warning", "UNSORTED",
                                "records are not in ascending start order within a contig; "
                                "sort before streaming interval tools", unsorted_at))
    if revisited_at is not None:
        findings.append(Finding("warning", "INTERLEAVED",
                                "a contig reappears after another contig; sort by contig then start",
                                revisited_at))

    style = naming_style(contigs)
    if style == "mixed":
        findings.append(Finding("error", "MIXED_NAMING",
                                "both chr-prefixed and plain contig names appear in one file"))
    if sizes is not None and contigs:
        sizes_style = naming_style(list(sizes))
        if style != "unknown" and sizes_style != "unknown" and style != sizes_style:
            findings.append(Finding("error", "NAMING_MISMATCH",
                                    f"file is {style} but the sizes file is {sizes_style}"))

    return {
        "path": path,
        "format": fmt,
        "counts": counts,
        "contigs": len(contigs),
        "naming_style": style,
        "strands": sorted(strands),
        "findings": findings,
    }


def cmd_check(args) -> int:
    sizes = None
    if args.genome:
        if not os.path.exists(args.genome):
            print(f"error: sizes file not found: {args.genome}", file=sys.stderr)
            return 2
        sizes = read_sizes(args.genome)
        if not sizes:
            print(f"error: no contig lengths read from {args.genome}", file=sys.stderr)
            return 2

    results = []
    for path in args.files:
        if not os.path.exists(path):
            print(f"error: file not found: {path}", file=sys.stderr)
            return 2
        results.append(check_file(path, guess_format(path, args.format), sizes))

    errors = sum(1 for r in results for f in r["findings"] if f.level == "error")
    warnings = sum(1 for r in results for f in r["findings"] if f.level == "warning")

    if args.json:
        payload = []
        for r in results:
            item = {k: v for k, v in r.items() if k != "findings"}
            item["findings"] = [f.as_dict() for f in r["findings"]]
            payload.append(item)
        print(json.dumps({"files": payload, "errors": errors, "warnings": warnings},
                         indent=2, sort_keys=True))
    else:
        for r in results:
            c = r["counts"]
            print(f"{r['path']}  [{r['format']}]")
            print(f"  records {c['records']}, contigs {r['contigs']}, naming {r['naming_style']}, "
                  f"strands {','.join(r['strands']) or 'none'}")
            if r["findings"]:
                for f in r["findings"]:
                    print(f.text())
            else:
                print("  no findings")
        print(f"\n{errors} error(s), {warnings} warning(s)")
        if sizes is None:
            print("note: no --genome given, so coordinates were not checked against contig lengths")

    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


def cmd_convert(args) -> int:
    match = REGION_RE.match(args.region.strip())
    if not match:
        print("error: region must look like contig:start-end", file=sys.stderr)
        return 2
    contig = match.group("contig")
    start = int(match.group("start").replace(",", ""))
    end = int(match.group("end").replace(",", ""))

    if args.convention == "one-based":
        if start < 1:
            print("error: a 1-based start must be at least 1", file=sys.stderr)
            return 2
        one_start, one_end = start, end
        bed_start, bed_end = start - 1, end
    else:
        if start < 0:
            print("error: a 0-based start cannot be negative", file=sys.stderr)
            return 2
        bed_start, bed_end = start, end
        one_start, one_end = start + 1, end

    if bed_end < bed_start:
        print("error: end is before start", file=sys.stderr)
        return 2
    length = bed_end - bed_start

    if args.json:
        print(json.dumps({"contig": contig, "length": length,
                          "one_based_closed": {"start": one_start, "end": one_end},
                          "zero_based_half_open": {"start": bed_start, "end": bed_end},
                          "region_string": f"{contig}:{one_start}-{one_end}",
                          "bed_line": f"{contig}\t{bed_start}\t{bed_end}"},
                         indent=2, sort_keys=True))
    else:
        print(f"contig                 {contig}")
        print(f"length (bases)         {length}")
        print(f"1-based, closed        {contig}:{one_start}-{one_end}   (VCF, GFF, GTF, SAM text, region strings)")
        print(f"0-based, half-open     {contig}\t{bed_start}\t{bed_end}   (BED, pysam, most Python APIs)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="interval_check.py",
        description="Check genomic interval files and convert coordinate conventions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="inspect BED-like or GFF/GTF files")
    check.add_argument("files", nargs="+", help="interval files (plain or .gz)")
    check.add_argument("--genome", help="chrom.sizes or .fai file to check contigs and bounds against")
    check.add_argument("--format", choices=["auto", "bed", "gff"], default="auto",
                       help="input format (default: guess from the extension)")
    check.add_argument("--strict", action="store_true", help="exit 1 when warnings remain")
    check.add_argument("--json", action="store_true", help="machine-readable output")
    check.set_defaults(func=cmd_check)

    convert = subparsers.add_parser("convert", help="convert one region between conventions")
    convert.add_argument("region", help="region such as chr1:1000-2000")
    convert.add_argument("--from", dest="convention", choices=["one-based", "zero-based"],
                         default="one-based", help="convention of the input region (default: one-based)")
    convert.add_argument("--json", action="store_true", help="machine-readable output")
    convert.set_defaults(func=cmd_convert)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
