#!/usr/bin/env python3
"""ProductCraft Data Engineering: offline profile of a CSV or other delimited text file.

Sniffs the encoding and delimiter, infers a type for every column, and reports
row counts, ragged rows, nulls (including null-like tokens such as "N/A"),
distinct counts, numeric and date summaries, duplicate rows, possible keys and
suspicious values: mixed types, numbers stored with formatting, leading zeros,
sentinel values, ambiguous day/month dates, spreadsheet formula prefixes,
encoding damage and more.

It reads one local file (optionally gzip-compressed), never writes, never uses
the network and never prints raw cell values unless --show-values is given.
Column names and aggregate statistics (counts, means, quantiles, minimum and
maximum of numeric and date columns) are printed. Findings are prompts to look
closer, not verdicts.

Exit codes: 0 profile complete; 1 profile complete, --strict given and at least
one WARN finding; 2 usage error or unreadable file.
"""
from __future__ import annotations

import argparse
import codecs
import csv
import gzip
import io
import json
import math
import os
import random
import re
import sys
from collections import Counter
from datetime import date

VERSION = "1.0.0"
SNIFF_BYTES = 256 * 1024
CANDIDATES = [",", ";", "\t", "|"]
DELIM_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe", ":": "colon", " ": "space"}
NULL_TOKENS = {"na", "n/a", "nan", "null", "none", "nil", "-", "--", "?", "#n/a", "missing", "(null)", "undefined"}
BOOL_TOKENS = {"true", "false", "yes", "no", "t", "f", "y", "n"}
NUMERIC_SENTINELS = {-99.0, -999.0, -9999.0, -99999.0, 999.0, 9999.0, 99999.0, 999999.0}
DATE_SENTINELS = {"0001-01-01", "1899-12-30", "1899-12-31", "1900-01-01", "1970-01-01", "9999-12-31"}
DISTINCT_CAP = 100_000
DUPLICATE_ROW_CAP = 1_000_000
COMPOSITE_KEY_MAX_ROWS = 200_000
SAMPLE_SIZE = 50_000
EXAMPLE_WIDTH = 40

INT_RE = re.compile(r"[+-]?\d+\Z")
FLOAT_RE = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?\Z")
SCI_RE = re.compile(r".*[eE][+-]?\d+\Z")
DEC_COMMA_RE = re.compile(r"[+-]?\d+,\d+\Z")
FORMATTED_RE = re.compile(
    r"[+-]?[$\u20ac\u00a3\u00a5]?\s?\d{1,3}(?:[,\u00a0 ]\d{3})+(?:\.\d+)?\s?%?\Z"
    r"|[+-]?[$\u20ac\u00a3\u00a5]\s?\d+(?:[.,]\d+)?\Z"
    r"|[+-]?\d+(?:[.,]\d+)?\s?%\Z"
)
ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\Z")
YMD_RE = re.compile(r"(\d{4})[/.](\d{1,2})[/.](\d{1,2})\Z")
XY_YEAR_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\Z")
ISO_DT_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:[.,]\d+)?)?\s?(Z|[+-]\d{2}(?::?\d{2})?)?\Z", re.I)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MOJIBAKE_RE = re.compile("[\u00c2\u00c3][\u0080-\u00bf]|\u00e2\u20ac")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class UsageError(Exception):
    """Raised for problems the user must fix (missing file, unparseable input)."""


class DecodeCounter:
    """Counts undecodable bytes while reading, replacing each with U+FFFD."""

    def __init__(self):
        self.errors = 0
        self.name = f"csv_profile_count_{id(self)}"
        codecs.register_error(self.name, self._handle)

    def _handle(self, exc):
        self.errors += exc.end - exc.start
        return ("\ufffd", exc.end)


def open_binary(path):
    return gzip.open(path, "rb") if path.endswith(".gz") else open(path, "rb")


def detect_encoding(raw: bytes):
    if raw.startswith(codecs.BOM_UTF32_LE) or raw.startswith(codecs.BOM_UTF32_BE):
        return "utf-32", "byte-order mark"
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-sig", "byte-order mark"
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return "utf-16", "byte-order mark"
    if len(raw) >= 4:
        even = raw[0::2].count(0) / max(1, len(raw[0::2]))
        odd = raw[1::2].count(0) / max(1, len(raw[1::2]))
        if odd > 0.3 and even < 0.05:
            return "utf-16-le", "guessed from NUL-byte pattern, no byte-order mark"
        if even > 0.3 and odd < 0.05:
            return "utf-16-be", "guessed from NUL-byte pattern, no byte-order mark"
    try:
        codecs.getincrementaldecoder("utf-8")().decode(raw, final=False)
        return "utf-8", ("ASCII only" if raw.isascii() else "valid UTF-8")
    except UnicodeDecodeError:
        pass
    try:
        raw.decode("cp1252")
        return "cp1252", "guessed: not valid UTF-8, decodes as Windows-1252"
    except UnicodeDecodeError:
        return "latin-1", "guessed: not valid UTF-8 or Windows-1252, Latin-1 fallback"


def detect_delimiter(sample: str, truncated: bool):
    lines = sample.splitlines(keepends=True)
    if truncated and len(lines) > 1:
        lines = lines[:-1]
    text = "".join(lines[:200])
    best, best_score = None, None
    for delim in CANDIDATES:
        try:
            rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if r][:50]
        except csv.Error:
            continue
        if not rows:
            continue
        counts = Counter(len(r) for r in rows)
        mode, hits = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
        score = (mode > 1, round(hits / len(rows), 3), mode)
        if best_score is None or score > best_score:
            best, best_score = delim, score
    if best is None or not best_score[0]:
        return ",", "no candidate splits rows; treated as one column"
    return best, f"{best_score[1]:.0%} of sampled rows have {best_score[2]} fields"


def valid_date(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def classify(value: str, decimal_comma: bool):
    """Return (class, detail) for a non-null, stripped value."""
    if INT_RE.match(value):
        return "integer", None
    if FLOAT_RE.match(value):
        return "float", None
    if decimal_comma and DEC_COMMA_RE.match(value):
        return "decimal_comma", None
    if FORMATTED_RE.match(value):
        return "formatted_number", None
    if value.casefold() in BOOL_TOKENS:
        return "boolean", None
    m = ISO_DATE_RE.match(value) or YMD_RE.match(value)
    if m:
        iso = valid_date(*m.groups())
        return ("date", ("iso", iso)) if iso else ("string", None)
    m = XY_YEAR_RE.match(value)
    if m:
        a, b, y = m.groups()
        dmy, mdy = valid_date(y, b, a), valid_date(y, a, b)
        if dmy and mdy and a != b:
            return "date", ("ambiguous", None)
        if dmy or mdy:
            if dmy and mdy:
                return "date", ("same_day_month", dmy)
            return "date", ("dmy", dmy) if dmy else ("mdy", mdy)
        return "string", None
    m = ISO_DT_RE.match(value)
    if m:
        g = m.groups()
        iso = valid_date(g[0], g[1], g[2])
        if iso and int(g[3]) < 24 and int(g[4]) < 60 and (g[5] is None or int(g[5]) < 61):
            return "datetime", ("aware" if g[6] else "naive", iso)
    return "string", None


def quantile(sorted_values, q):
    if not sorted_values:
        return None
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def num(x):
    if x is None:
        return None
    return float(f"{x:.6g}")


class Column:
    def __init__(self, name, index, opts):
        self.name, self.index, self.opts = name, index, opts
        self.seen = self.empty = self.tokens = 0
        self.token_names = Counter()
        self.types = Counter()
        self.exact, self.norm = set(), set()
        self.capped = False
        self.dup_before_cap = False
        self.flags = Counter()
        self.min_len = self.max_len = None
        self.n = 0
        self.mean = self.m2 = 0.0
        self.min = self.max = None
        self.zeros = self.negatives = self.nonfinite = self.big_ints = 0
        self.sentinels = Counter()
        self.sample = []
        self.rng = random.Random(index)
        self.date_min = self.date_max = None
        self.date_forms = Counter()
        self.sentinel_dates = Counter()
        self.top = Counter()
        self.examples = {}

    def add(self, raw):
        self.seen += 1
        stripped = raw.strip()
        if not stripped:
            self.empty += 1
            return
        if stripped.casefold() in self.opts.null_tokens:
            self.tokens += 1
            self.token_names[stripped.casefold()] += 1
            return
        if not self.capped:
            if raw in self.exact:
                self.dup_before_cap = True
            else:
                self.exact.add(raw)
                self.norm.add(stripped.casefold())
                if len(self.exact) >= self.opts.distinct_cap:
                    self.capped = True
        if stripped != raw:
            self.flags["whitespace"] += 1
        if not raw.isprintable():
            if "\n" in raw or "\r" in raw:
                self.flags["newlines"] += 1
            if CONTROL_RE.search(raw):
                self.flags["control"] += 1
        if not raw.isascii() and ("\ufffd" in raw or MOJIBAKE_RE.search(raw)):
            self.flags["damage"] += 1
        length = len(raw)
        self.min_len = length if self.min_len is None else min(self.min_len, length)
        self.max_len = length if self.max_len is None else max(self.max_len, length)
        cls, detail = classify(stripped, self.opts.decimal_comma)
        self.types[cls] += 1
        if self.opts.show_values:
            if len(self.top) < self.opts.distinct_cap or stripped in self.top:
                self.top[stripped] += 1
            self.examples.setdefault(cls, stripped[:EXAMPLE_WIDTH])
        if cls in ("integer", "float", "decimal_comma"):
            self._number(stripped, cls)
        elif cls in ("date", "datetime"):
            self._date(cls, detail)
        elif cls == "formatted_number":
            self.flags["formatted"] += 1
        if (cls == "string" and stripped.startswith(FORMULA_PREFIXES)) or raw.startswith(("\t", "\r")):
            self.flags["formula"] += 1

    def _number(self, text, cls):
        if cls == "integer":
            digits = text.lstrip("+-")
            if len(digits) > 1 and digits.startswith("0"):
                self.flags["leading_zeros"] += 1
            if abs(int(text)) > 2 ** 53:
                self.big_ints += 1
        elif SCI_RE.match(text):
            self.flags["sci"] += 1
        x = float(text.replace(",", ".")) if cls == "decimal_comma" else float(text)
        if math.isinf(x) or math.isnan(x):
            self.nonfinite += 1
            return
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)
        self.min = x if self.min is None else min(self.min, x)
        self.max = x if self.max is None else max(self.max, x)
        self.zeros += x == 0
        self.negatives += x < 0
        if x in NUMERIC_SENTINELS:
            self.sentinels[x] += 1
        if len(self.sample) < self.opts.sample_size:
            self.sample.append(x)
        else:
            j = self.rng.randrange(self.n)
            if j < self.opts.sample_size:
                self.sample[j] = x

    def _date(self, cls, detail):
        form, iso = detail
        self.date_forms[form] += 1
        if iso:
            self.date_min = iso if self.date_min is None else min(self.date_min, iso)
            self.date_max = iso if self.date_max is None else max(self.date_max, iso)
            if iso in DATE_SENTINELS:
                self.sentinel_dates[iso] += 1

    # ----- results -----
    @property
    def nulls(self):
        return self.empty + self.tokens

    @property
    def non_null(self):
        return self.seen - self.nulls

    def inferred_type(self):
        t, total = self.types, sum(self.types.values())
        if total == 0:
            return "empty", 0
        keys = set(t)
        exact = [({"integer"}, "integer"), ({"integer", "float"}, "float"),
                 ({"integer", "float", "decimal_comma"}, "float (decimal comma)"), ({"boolean"}, "boolean"),
                 ({"date"}, "date"), ({"date", "datetime"}, "datetime")]
        for allowed, name in exact:
            if keys <= allowed:
                return name, 0
        families = {
            "integer": t["integer"],
            "float": t["integer"] + t["float"] + t["decimal_comma"],
            "boolean": t["boolean"],
            "datetime": t["date"] + t["datetime"],
            "string": t["string"] + t["formatted_number"],
        }
        name, count = max(families.items(), key=lambda kv: (kv[1], kv[0] == "string"))
        if name != "string" and count / total >= 0.9:
            return name, total - count
        return ("string" if families["string"] / total >= 0.9 else "mixed"), 0

    def distinct(self):
        return len(self.exact)

    def numeric_summary(self):
        if self.n == 0:
            return None
        s = sorted(self.sample)
        q1, q3 = quantile(s, 0.25), quantile(s, 0.75)
        iqr = q3 - q1
        out = sum(1 for v in s if v < q1 - 1.5 * iqr or v > q3 + 1.5 * iqr)
        approx = len(s) < self.n
        if approx:
            out = round(out * self.n / len(s))
        std = math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0
        return {
            "count": self.n, "mean": num(self.mean), "std": num(std), "min": num(self.min),
            "p01": num(quantile(s, 0.01)), "p25": num(q1), "p50": num(quantile(s, 0.5)), "p75": num(q3),
            "p99": num(quantile(s, 0.99)), "max": num(self.max), "zeros": self.zeros,
            "negatives": self.negatives, "outliers_1_5_iqr": out, "quantiles_approximate": approx,
        }


def iter_records(path, encoding, delimiter, counter):
    with open_binary(path) as fb:
        text = io.TextIOWrapper(fb, encoding=encoding, errors=counter.name, newline="")
        reader = csv.reader(text, delimiter=delimiter)
        try:
            for row in reader:
                yield reader.line_num, row
        except csv.Error as exc:
            raise UsageError(f"CSV parse error near line {reader.line_num}: {exc}") from None


def profile(path, opts):
    if not os.path.isfile(path):
        raise UsageError(f"not a file: {path}")
    try:
        with open_binary(path) as fb:
            raw = fb.read(SNIFF_BYTES + 1)
    except OSError as exc:
        raise UsageError(f"cannot read {path}: {exc}") from None
    truncated = len(raw) > SNIFF_BYTES
    raw = raw[:SNIFF_BYTES]
    if not raw.strip():
        raise UsageError("file is empty")
    if opts.encoding:
        try:
            codecs.lookup(opts.encoding)
        except LookupError:
            raise UsageError(f"unknown encoding: {opts.encoding}") from None
        encoding, enc_basis = opts.encoding, "given with --encoding"
    else:
        encoding, enc_basis = detect_encoding(raw)
    sample = raw.decode(encoding, errors="replace")
    if opts.delimiter:
        delimiter, delim_basis = opts.delimiter, "given with --delimiter"
    else:
        delimiter, delim_basis = detect_delimiter(sample, truncated)
    opts.decimal_comma = delimiter != ","

    counter = DecodeCounter()
    columns, names = [], []
    rows = blank = empty_rows = short = long_ = 0
    ragged_lines = []
    dup_seen, dup_count, dup_checked = set(), 0, 0
    first_line = None
    truncated_rows = False
    for line_no, row in iter_records(path, encoding, delimiter, counter):
        if not row:
            blank += 1
            continue
        if not columns:
            if opts.no_header:
                names = [f"column_{i + 1}" for i in range(len(row))]
            else:
                names = [c.strip() for c in row]
                first_line = line_no
            columns = [Column(n, i, opts) for i, n in enumerate(names)]
            if not opts.no_header:
                continue
        if opts.max_rows is not None and rows >= opts.max_rows:
            truncated_rows = True
            break
        rows += 1
        if len(row) != len(columns):
            if len(row) < len(columns):
                short += 1
            else:
                long_ += 1
            if len(ragged_lines) < 10:
                ragged_lines.append(line_no)
        if all(not f.strip() for f in row):
            empty_rows += 1
        for col, value in zip(columns, row):
            col.add(value)
        for col in columns[len(row):]:
            col.add("")
        if dup_checked < DUPLICATE_ROW_CAP:
            dup_checked += 1
            key = "\x1f".join(row)
            if key in dup_seen:
                dup_count += 1
            else:
                dup_seen.add(key)
    dup_seen = None
    if not columns:
        raise UsageError("no records found")

    keys = find_keys(path, encoding, delimiter, columns, rows, opts, truncated_rows)
    report = {
        "tool": "csv_profile", "version": VERSION,
        "file": {"path": path, "bytes": os.path.getsize(path), "encoding": encoding, "encoding_basis": enc_basis,
                 "decode_errors": counter.errors, "delimiter": delimiter,
                 "delimiter_name": DELIM_NAMES.get(delimiter, "other"), "delimiter_basis": delim_basis,
                 "header": not opts.no_header},
        "rows": {"data_rows": rows, "truncated_at_max_rows": truncated_rows, "blank_lines": blank,
                 "empty_rows": empty_rows, "short_rows": short, "long_rows": long_, "ragged_lines": ragged_lines,
                 "duplicate_rows": dup_count, "duplicate_rows_checked": dup_checked},
        "columns": [column_report(c, rows, opts) for c in columns],
        "keys": keys,
    }
    report["findings"] = findings(report, columns, names, first_line)
    report["summary"] = {
        "warn": sum(1 for f in report["findings"] if f["severity"] == "WARN"),
        "info": sum(1 for f in report["findings"] if f["severity"] == "INFO"),
    }
    return report


def find_keys(path, encoding, delimiter, columns, rows, opts, truncated):
    note = "exact"
    if rows == 0:
        return {"single": [], "composite": [], "note": "no data rows"}
    single, recheck = [], []
    for c in columns:
        if c.nulls or c.dup_before_cap or c.non_null != rows:
            continue
        if not c.capped and c.distinct() == rows:
            single.append(c.name)
        elif c.capped:
            recheck.append(c)
    composite = []
    candidates = []
    if not single and not recheck and rows <= COMPOSITE_KEY_MAX_ROWS:
        pool = [c for c in columns if c.nulls == 0 and c.non_null == rows and c.distinct() > 1]
        pool.sort(key=lambda c: (-c.distinct(), c.index))
        pool = pool[:6]
        candidates = [(a, b) for i, a in enumerate(pool) for b in pool[i + 1:]]
    elif not single and not recheck:
        note = f"composite keys not checked above {COMPOSITE_KEY_MAX_ROWS:,} rows"
    if recheck or candidates:
        recheck = recheck[:4]
        seen_single = {c.index: set() for c in recheck}
        dup_single = set()
        seen_pair = {(a.index, b.index): set() for a, b in candidates}
        dup_pair = set()
        counter = DecodeCounter()
        header_skipped = opts.no_header
        n = 0
        for _, row in iter_records(path, encoding, delimiter, counter):
            if not row:
                continue
            if not header_skipped:
                header_skipped = True
                continue
            if opts.max_rows is not None and n >= opts.max_rows:
                break
            n += 1
            for idx, seen in seen_single.items():
                if idx in dup_single:
                    continue
                v = row[idx] if idx < len(row) else ""
                if v in seen:
                    dup_single.add(idx)
                    seen.clear()
                else:
                    seen.add(v)
            for pair, seen in seen_pair.items():
                if pair in dup_pair:
                    continue
                v = tuple(row[i] if i < len(row) else "" for i in pair)
                if v in seen:
                    dup_pair.add(pair)
                    seen.clear()
                else:
                    seen.add(v)
        single += [c.name for c in recheck if c.index not in dup_single]
        composite = [[a.name, b.name] for a, b in candidates if (a.index, b.index) not in dup_pair]
        if recheck and not single:
            note = "composite keys not checked when a high-cardinality column needed a second pass"
    if truncated:
        note = f"checked within the first {rows:,} rows only (--max-rows)"
    return {"single": single, "composite": composite, "note": note}


def column_report(c, rows, opts):
    ctype, nonconforming = c.inferred_type()
    out = {
        "index": c.index + 1, "name": c.name, "type": ctype, "non_null": c.non_null, "nulls": c.nulls,
        "null_pct": round(100.0 * c.nulls / rows, 2) if rows else 0.0, "empty": c.empty,
        "null_tokens": sorted(c.token_names), "distinct": c.distinct(), "distinct_capped": c.capped,
        "type_counts": dict(sorted(c.types.items())), "nonconforming": nonconforming,
        "length": {"min": c.min_len, "max": c.max_len},
        "numeric": c.numeric_summary() if ctype in ("integer", "float", "float (decimal comma)") else None,
        "dates": None,
    }
    if ctype in ("date", "datetime"):
        out["dates"] = {"min": c.date_min, "max": c.date_max, "forms": dict(sorted(c.date_forms.items()))}
    if opts.show_values:
        top = sorted(c.top.items(), key=lambda kv: (-kv[1], kv[0]))[:opts.top]
        out["values"] = {"top": [[v[:EXAMPLE_WIDTH], n] for v, n in top],
                         "examples_by_class": dict(sorted(c.examples.items()))}
    return out


def findings(report, columns, names, first_line):
    res = []

    def add(sev, code, col, msg):
        res.append({"severity": sev, "code": code, "column": col, "message": msg})

    f, r = report["file"], report["rows"]
    if f["decode_errors"]:
        add("WARN", "DECODE_ERRORS", None, f"bytes that are not valid {f['encoding']}: {f['decode_errors']:,} (replaced); "
            "confirm the encoding with the data owner or pass --encoding")
    elif f["encoding_basis"].startswith("guessed"):
        add("INFO", "ENCODING_GUESS", None, f"encoding {f['encoding']} was {f['encoding_basis']}; "
            "confirm it with the data owner or pass --encoding")
    if r["short_rows"] or r["long_rows"]:
        add("WARN", "RAGGED_ROWS", None, f"rows with fewer fields than the header: {r['short_rows']:,}, with more: "
            f"{r['long_rows']:,}; first lines: {', '.join(map(str, r['ragged_lines']))}")
    if r["duplicate_rows"]:
        add("WARN", "DUPLICATE_ROWS", None, f"rows that repeat an earlier row exactly: {r['duplicate_rows']:,}")
    if r["empty_rows"]:
        add("INFO", "EMPTY_ROWS", None, f"rows with only empty fields: {r['empty_rows']:,}")
    counts = Counter(names)
    for n in sorted(k for k, v in counts.items() if v > 1 and k):
        add("WARN", "DUPLICATE_HEADER", n, f"column name appears {counts[n]} times")
    if any(not n for n in names):
        add("WARN", "BLANK_HEADER", None, f"blank column names: {sum(1 for n in names if not n)}"
            + (f" in the header on line {first_line}" if first_line else ""))
    for c, cr in zip(columns, report["columns"]):
        name, nn, ctype = c.name or f"column_{c.index + 1}", c.non_null, cr["type"]
        fl = c.flags
        if report["rows"]["data_rows"] and nn == 0:
            add("INFO", "ALL_NULL", name, "every value is empty or a null token")
            continue
        if cr["nonconforming"]:
            add("WARN", "MIXED_TYPES", name, f"values that do not parse as {ctype}: {cr['nonconforming']:,} of {nn:,}")
        if ctype == "mixed":
            mix = ", ".join(f"{k} {v:,}" for k, v in sorted(c.types.items()))
            add("INFO", "MIXED_TYPES", name, f"no dominant type ({mix})")
        if c.tokens:
            add("INFO", "NULL_TOKENS", name, f"null-like tokens: {c.tokens:,} ({', '.join(sorted(c.token_names))})")
        if c.distinct() == 1 and nn > 1 and not c.capped:
            add("INFO", "CONSTANT", name, "only one distinct value")
        if fl["formatted"]:
            add("WARN", "FORMATTED_NUMBERS", name, f"numbers with thousands separators, currency or percent "
                f"signs: {fl['formatted']:,}; strip the formatting before converting")
        if c.types["decimal_comma"]:
            add("INFO", "DECIMAL_COMMA", name, f"numbers with a decimal comma: {c.types['decimal_comma']:,}; "
                "a comma followed by exactly three digits may be a thousands separator")
        if fl["leading_zeros"]:
            add("WARN", "LEADING_ZEROS", name, f"integer-like values with leading zeros: {fl['leading_zeros']:,}; "
                "read the column as text if it is an identifier or code")
        if fl["sci"] and c.types["integer"]:
            add("WARN", "SCI_NOTATION", name, f"scientific-notation values in an integer-like column: "
                f"{fl['sci']:,}; a spreadsheet may have rounded them")
        if c.big_ints:
            add("INFO", "BIG_INTEGERS", name, f"integers beyond 2^53, which lose precision as float64: {c.big_ints:,}")
        if c.min is not None:
            hit = sorted(v for v, n in c.sentinels.items() if n >= 2 and v in (c.min, c.max))
            if hit:
                add("WARN", "SENTINEL_VALUES", name, f"values equal to a typical missing-value code at the "
                    f"column's minimum or maximum: {sum(c.sentinels[v] for v in hit):,}")
        if c.sentinel_dates:
            add("WARN", "SENTINEL_DATES", name, f"dates equal to a typical placeholder (such as 1900-01-01 or "
                f"9999-12-31): {sum(c.sentinel_dates.values()):,}")
        forms = c.date_forms
        if forms["dmy"] and forms["mdy"]:
            add("WARN", "MIXED_DATE_ORDER", name, f"both day-first ({forms['dmy']:,}) and month-first "
                f"({forms['mdy']:,}) dates")
        elif forms["ambiguous"] and not (forms["dmy"] or forms["mdy"]):
            add("WARN", "AMBIGUOUS_DATES", name, f"dates that could be day-first or month-first: "
                f"{forms['ambiguous']:,}; confirm the order with the data owner")
        elif forms["dmy"]:
            add("INFO", "DAY_FIRST_DATES", name, "dates are day-first (DD/MM/YYYY); parse with an explicit format")
        if forms["aware"] and forms["naive"]:
            add("WARN", "MIXED_TIMEZONES", name, f"timestamps with a UTC offset: {forms['aware']:,}, without: "
                f"{forms['naive']:,}")
        if fl["formula"]:
            add("WARN", "FORMULA_PREFIX", name, f"text values starting with =, +, -, @, tab or CR: {fl['formula']:,}; "
                "they can run as formulas in a spreadsheet (CWE-1236)")
        if fl["damage"]:
            add("WARN", "ENCODING_DAMAGE", name, f"values with U+FFFD or mojibake sequences: {fl['damage']:,}")
        if fl["control"]:
            add("WARN", "CONTROL_CHARS", name, f"values with control characters: {fl['control']:,}")
        if fl["newlines"]:
            add("INFO", "EMBEDDED_NEWLINES", name, f"values with line breaks: {fl['newlines']:,}")
        if fl["whitespace"]:
            add("INFO", "WHITESPACE", name, f"values with leading or trailing whitespace: {fl['whitespace']:,}")
        if not c.capped and ctype in ("string", "boolean", "mixed") and c.distinct() <= max(1, nn) * 0.5:
            variants = len(c.exact) - len(c.norm)
            if variants:
                add("INFO", "CASE_VARIANTS", name, f"distinct values that differ from another only by case or "
                    f"surrounding spaces: {variants:,}")
    keys = report["keys"]
    if report["rows"]["data_rows"] and not keys["single"] and not keys["composite"]:
        add("INFO", "NO_KEY", None, "no single column or checked column pair uniquely identifies rows"
            + (f" ({keys['note']})" if keys["note"] != "exact" else ""))
    order = {"WARN": 0, "INFO": 1}
    res.sort(key=lambda x: (order[x["severity"]], x["column"] is not None, x["column"] or "", x["code"]))
    return res


def fmt(x):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.6g}"
    return f"{x:,}" if isinstance(x, int) else str(x)


def clip(text, width):
    return text if len(text) <= width else text[:width - 3] + "..."


def render_text(rep):
    f, r = rep["file"], rep["rows"]
    out = [f"csv_profile {rep['version']}: {f['path']}"]
    delim = f["delimiter"].encode("unicode_escape").decode()
    out.append(f"  {f['bytes']:,} bytes, encoding {f['encoding']} ({f['encoding_basis']}), "
               f"delimiter '{delim}' {f['delimiter_name']} ({f['delimiter_basis']}), "
               f"header {'yes' if f['header'] else 'no'}")
    trunc = " (stopped at --max-rows)" if r["truncated_at_max_rows"] else ""
    out.append(f"  {r['data_rows']:,} data rows{trunc}, {len(rep['columns'])} columns, "
               f"{r['short_rows'] + r['long_rows']:,} ragged, {r['blank_lines']:,} blank lines, "
               f"{r['duplicate_rows']:,} duplicate rows")
    keys = rep["keys"]
    shown = keys["single"] + [" + ".join(p) for p in keys["composite"]]
    out.append(f"  possible keys: {', '.join(shown) if shown else 'none'}"
               + (f" ({keys['note']})" if keys["note"] != "exact" else ""))
    out.append("")
    width = min(28, max([4] + [len(c["name"]) for c in rep["columns"]]))
    out.append(f"  {'#':>3}  {'name':<{width}}  {'type':<21}  {'nulls':>14}  {'distinct':>10}")
    for c in rep["columns"]:
        nulls = f"{c['nulls']:,} ({c['null_pct']:.1f}%)"
        distinct = (">=" if c["distinct_capped"] else "") + f"{c['distinct']:,}"
        out.append(f"  {c['index']:>3}  {clip(c['name'], width):<{width}}  {c['type']:<21}  {nulls:>14}  {distinct:>10}")
    numeric = [c for c in rep["columns"] if c["numeric"]]
    if numeric:
        out.append("")
        out.append("  Numeric columns" + (" (quantiles from a sample)" if any(
            c["numeric"]["quantiles_approximate"] for c in numeric) else ""))
        cols = ["mean", "std", "min", "p25", "p50", "p75", "max", "zeros", "negatives", "outliers_1_5_iqr"]
        out.append(f"  {'name':<{width}}  " + "  ".join(f"{h if h != 'outliers_1_5_iqr' else 'outliers':>10}" for h in cols))
        for c in numeric:
            out.append(f"  {clip(c['name'], width):<{width}}  " + "  ".join(f"{fmt(c['numeric'][h]):>10}" for h in cols))
    dated = [c for c in rep["columns"] if c["dates"]]
    if dated:
        out.append("")
        out.append("  Date columns")
        for c in dated:
            d = c["dates"]
            out.append(f"  {clip(c['name'], width):<{width}}  {(fmt(d['min']) + ' to ' + fmt(d['max'])) if d['min'] else 'range unknown'}  "
                       + ", ".join(f"{k} {v:,}" for k, v in d["forms"].items()))
    if any("values" in c for c in rep["columns"]):
        out.append("")
        out.append("  Values (--show-values)")
        for c in rep["columns"]:
            top = ", ".join(f"{json.dumps(v, ensure_ascii=False)} x{n:,}" for v, n in c["values"]["top"])
            out.append(f"  {clip(c['name'], width):<{width}}  {top or '-'}")
            for cls, ex in c["values"]["examples_by_class"].items():
                if cls != c["type"]:
                    out.append(f"  {'':<{width}}    {cls}: {json.dumps(ex, ensure_ascii=False)}")
    s = rep["summary"]
    out.append("")
    out.append(f"  Findings: {s['warn']} WARN, {s['info']} INFO")
    for x in rep["findings"]:
        where = f"{x['column']}: " if x["column"] else ""
        out.append(f"  {x['severity']:<4}  {x['code']:<18}  {where}{x['message']}")
    return "\n".join(out) + "\n"


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="csv_profile.py",
        description="Offline, read-only profile of a CSV or delimited text file. "
                    "Prints no raw cell values unless --show-values is given.",
        epilog="Exit codes: 0 done; 1 --strict and WARN findings exist; 2 usage error or unreadable file.")
    p.add_argument("path", help="CSV, TSV or other delimited file (.gz is decompressed)")
    p.add_argument("--delimiter", help="field delimiter; use '\\t' for tab (default: sniffed)")
    p.add_argument("--encoding", help="text encoding, for example utf-8 or cp1252 (default: sniffed)")
    p.add_argument("--no-header", action="store_true", help="the first row is data, not column names")
    p.add_argument("--max-rows", type=int, help="profile only the first N data rows")
    p.add_argument("--null-token", action="append", default=[], metavar="TOKEN",
                   help="extra value to treat as null (repeatable, case-insensitive)")
    p.add_argument("--distinct-cap", type=int, default=DISTINCT_CAP,
                   help=f"distinct values tracked exactly per column (default {DISTINCT_CAP:,})")
    p.add_argument("--sample-size", type=int, default=SAMPLE_SIZE,
                   help=f"numeric values kept per column for quantiles (default {SAMPLE_SIZE:,})")
    p.add_argument("--show-values", action="store_true",
                   help="also print frequent values and one example per value class (may expose data)")
    p.add_argument("--top", type=int, default=5, help="frequent values per column with --show-values (default 5)")
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    p.add_argument("--strict", action="store_true", help="exit 1 when any WARN finding exists")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = p.parse_args(argv)
    if args.delimiter is not None:
        args.delimiter = args.delimiter.encode().decode("unicode_escape")
        if len(args.delimiter) != 1:
            p.error("--delimiter must be a single character")
    for name in ("max_rows", "distinct_cap", "sample_size", "top"):
        value = getattr(args, name)
        if value is not None and value < 1:
            p.error(f"--{name.replace('_', '-')} must be at least 1")
    args.null_tokens = NULL_TOKENS | {t.strip().casefold() for t in args.null_token if t.strip()}
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = profile(args.path, args)
    except UsageError as exc:
        print(f"csv_profile: error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False))
    else:
        sys.stdout.write(render_text(report))
    return 1 if args.strict and report["summary"]["warn"] else 0


if __name__ == "__main__":
    sys.exit(main())
