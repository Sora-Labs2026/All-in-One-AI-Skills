#!/usr/bin/env python3
"""ProductCraft style-value inventory. Read-only: it reads style sources and prints a report.

Scans CSS, SCSS, Less, HTML, Vue, Svelte, JS and TS files for raw style values
that a design system would normally express as tokens:

  colors        hex, rgb()/rgba() and hsl()/hsla() literals in declaration values,
                plus Tailwind arbitrary values such as bg-[#1a2b3c]; opaque colors
                closer than --near (OKLab distance, default 0.02, the just-noticeable
                difference used by CSS Color 4 gamut mapping) are grouped as
                near-duplicate clusters
  font sizes    font-size / fontSize values (rem converted with --root-px)
  spacing       margin, padding and gap lengths; values off the --spacing-base scale
                are listed (values below the base are reported as optical nudges)
  radii, shadows, durations (transition and animation, in ms) and z-index values
  flags         transition: all, will-change: all
  tokens        custom-property definitions (--name: value) and var() uses

Files matching --token-glob (default: names containing "token" or "theme") are
token sources: their custom-property definitions are counted but their raw values
are not reported as findings.

Exit codes: 0 nothing needs review; 1 findings need review (flags, near-duplicate
colors, off-scale spacing) or, with --baseline, a count grew; 2 usage error.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import sys

VERSION = "1.0.0"
EXTENSIONS = {".css", ".scss", ".sass", ".less", ".pcss", ".html", ".htm", ".vue", ".svelte",
              ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit",
             "coverage", "vendor", ".cache", "storybook-static", "__pycache__"}
MAX_BYTES = 2_000_000

COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
DECL = re.compile(r"(?<![\w$-])(-{0,2}[A-Za-z][\w-]*)\s*:\s*([^;{}\n]+)")
# In script files: object properties with quoted or numeric values, and CSS declarations ended by ";"
JS_DECL = re.compile(r"(?<![\w$-])([A-Za-z][\w-]*)\s*:\s*(\"[^\"\n]*\"|'[^'\n]*'|-?\d*\.?\d+(?=\s*(?:[,})]|$)))")
CSS_IN_JS_DECL = re.compile(r"(?<![\w$-])(-{0,2}[A-Za-z][\w-]*)\s*:\s*([^;{}\n\"']+);")
SCRIPT_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
HEX = re.compile(r"#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-zA-Z_-])")
FUNC_COLOR = re.compile(r"\b(rgba?|hsla?)\(\s*([^()]*)\)", re.I)
TW_COLOR = re.compile(r"\b[a-z][a-z-]*-\[(#[0-9a-fA-F]{3,8})\]")
TW_SPACE = re.compile(r"\b(?:p[xytrblse]?|m[xytrblse]?|gap(?:-[xy])?|space-[xy])-\[(-?\d*\.?\d+)(px|rem)\]")
LINE_COMMENT = re.compile(r"(^|\s)//.*$")
PREPROCESSOR_VAR = re.compile(r"^\s*[$@][\w-]+\s*:")
COLOR_PROP_PARTS = ("color", "background", "border", "outline", "fill", "stroke", "shadow", "caret",
                    "accent", "decoration", "column-rule", "stop", "flood", "scrollbar", "gradient")
LENGTH = re.compile(r"^(-?\d*\.?\d+)(px|rem|em|%|pt|vh|vw)?$")
TIME = re.compile(r"(?<![\w.])(\d*\.?\d+)(ms|s)\b")
FUNC_CALL = re.compile(r"[\w-]+\([^()]*\)")
VAR_USE = re.compile(r"var\(\s*--[\w-]+")

SPACING_PROPS = {"margin", "padding", "gap", "row-gap", "column-gap", "grid-gap"}
RADIUS_PROPS = {"border-radius", "border-top-left-radius", "border-top-right-radius",
                "border-bottom-left-radius", "border-bottom-right-radius"}


def kebab(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", name).lower()


def base_prop(prop: str) -> str:
    for side in ("-top", "-right", "-bottom", "-left", "-inline-start", "-inline-end", "-block-start",
                 "-block-end", "-inline", "-block", "-x", "-y"):
        if prop.endswith(side) and prop[: -len(side)] in ("margin", "padding"):
            return prop[: -len(side)]
    return prop


def clean_value(value: str) -> str:
    value = value.strip().rstrip(",;").strip().strip("'\"`").strip()
    return re.sub(r"\s+", " ", value.replace("!important", "")).strip()


def parse_hex(text: str):
    h = text.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return r, g, b, a


def _channel(tok: str) -> float:
    return float(tok[:-1]) * 2.55 if tok.endswith("%") else float(tok)


def _alpha(tok: str) -> float:
    return float(tok[:-1]) / 100 if tok.endswith("%") else float(tok)


def hsl_to_rgb(h: float, s: float, l: float):
    h = (h % 360) / 360
    if s == 0:
        v = l * 255
        return v, v, v

    def hue(p, q, t):
        t %= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return hue(p, q, h + 1 / 3) * 255, hue(p, q, h) * 255, hue(p, q, h - 1 / 3) * 255


def parse_func(kind: str, args: str):
    parts = [p for p in re.split(r"[\s,/]+", args.strip()) if p]
    if any(p.startswith("var") or p.startswith("calc") for p in parts) or len(parts) not in (3, 4):
        return None
    try:
        a = _alpha(parts[3]) if len(parts) == 4 else 1.0
        if kind.lower().startswith("rgb"):
            r, g, b = (_channel(p) for p in parts[:3])
        else:
            hue = float(re.sub(r"deg$", "", parts[0]))
            s = float(parts[1].rstrip("%")) / 100
            l = float(parts[2].rstrip("%")) / 100
            r, g, b = hsl_to_rgb(hue, s, l)
    except ValueError:
        return None
    clamp = lambda v: max(0, min(255, round(v)))
    return clamp(r), clamp(g), clamp(b), max(0.0, min(1.0, a))


def color_key(rgba) -> str:
    r, g, b, a = rgba
    base = f"#{r:02x}{g:02x}{b:02x}"
    return base if a >= 0.999 else f"{base}{round(a * 255):02x}"


def oklab(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb[:3])
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


class Inventory:
    def __init__(self, root_px: float, spacing_base: float, max_locations: int):
        self.root_px, self.base, self.max_loc = root_px, spacing_base, max_locations
        self.buckets: dict[str, dict[str, list]] = {k: {} for k in (
            "colors", "font_sizes", "spacing_off_scale", "spacing_optical", "radii", "shadows",
            "durations_ms", "z_index", "flags")}
        self.token_definitions = 0
        self.var_uses = 0
        self.files = 0

    def add(self, bucket: str, value: str, where: str):
        entry = self.buckets[bucket].setdefault(value, [0, []])
        entry[0] += 1
        if len(entry[1]) < self.max_loc:
            entry[1].append(where)

    def px(self, num: float, unit: str | None):
        if unit in (None, "px"):
            return num
        if unit == "rem":
            return num * self.root_px
        return None

    def scan_text(self, text: str, rel: str, is_token_file: bool):
        self.files += 1
        text = COMMENT_BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), text)
        for lineno, line in enumerate(text.splitlines(), 1):
            where = f"{rel}:{lineno}"
            self.var_uses += len(VAR_USE.findall(line))
            if not rel.endswith(".css"):
                line = LINE_COMMENT.sub(r"\1", line)
            if PREPROCESSOR_VAR.match(line):
                self.token_definitions += 1
                continue
            if not is_token_file:
                for m in TW_COLOR.finditer(line):
                    self.add("colors", color_key(parse_hex(m.group(1))), where)
                for m in TW_SPACE.finditer(line):
                    px = self.px(float(m.group(1)), m.group(2))
                    if px and abs(px) >= self.base and abs(px / self.base - round(px / self.base)) > 1e-6:
                        self.add("spacing_off_scale", f"{px:g}px (arbitrary class)", where)
            matches = (list(JS_DECL.finditer(line)) + list(CSS_IN_JS_DECL.finditer(line))
                       if rel.endswith(SCRIPT_EXT) else DECL.finditer(line))
            for m in matches:
                prop, raw = m.group(1), m.group(2)
                if prop.startswith("--"):
                    self.token_definitions += 1
                    continue
                if is_token_file:
                    continue
                self.scan_declaration(kebab(prop), clean_value(raw), where)

    def scan_declaration(self, prop: str, value: str, where: str):
        if not value or value.startswith(("http", "//")):
            return
        if any(part in prop for part in COLOR_PROP_PARTS):
            for m in HEX.finditer(value):
                self.add("colors", color_key(parse_hex(m.group(0))), where)
            for m in FUNC_COLOR.finditer(value):
                rgba = parse_func(m.group(1), m.group(2))
                if rgba:
                    self.add("colors", color_key(rgba), where)
        if prop in ("transition", "transition-property") and re.search(r"(^|[\s,])all([\s,]|$)", value):
            self.add("flags", "transition: all", where)
        if prop == "will-change" and value.strip() == "all":
            self.add("flags", "will-change: all", where)
        if "var(" in value and prop not in ("transition", "animation"):
            return
        if prop == "font-size":
            m = LENGTH.match(value)
            if m:
                num, unit = float(m.group(1)), m.group(2)
                px = self.px(num, unit)
                label = f"{px:g}px" if px is not None and unit != "px" else value if unit else f"{num:g}px"
                self.add("font_sizes", label, where)
        elif base_prop(prop) in SPACING_PROPS:
            stripped = FUNC_CALL.sub(" ", value)
            for tok in stripped.split():
                m = LENGTH.match(tok)
                if not m:
                    continue
                num, unit = float(m.group(1)), m.group(2)
                px = self.px(num, unit)
                if px is None or px == 0:
                    continue
                if abs(px) < self.base:
                    self.add("spacing_optical", f"{px:g}px", where)
                elif abs(px / self.base - round(px / self.base)) > 1e-6:
                    self.add("spacing_off_scale", f"{px:g}px", where)
        elif prop in RADIUS_PROPS:
            self.add("radii", value, where)
        elif prop == "box-shadow" and value not in ("none", "inherit", "initial", "unset"):
            self.add("shadows", value, where)
        elif prop in ("transition", "transition-duration", "animation", "animation-duration"):
            for num, unit in TIME.findall(value):
                ms = float(num) * (1000 if unit == "s" else 1)
                self.add("durations_ms", f"{ms:g}", where)
        elif prop == "z-index" and re.fullmatch(r"-?\d+", value):
            self.add("z_index", value, where)

    def clusters(self, threshold: float):
        opaque = [(k, v[0]) for k, v in self.buckets["colors"].items() if len(k) == 7]
        opaque.sort(key=lambda kv: (-kv[1], kv[0]))
        labs = {k: oklab(parse_hex(k)) for k, _ in opaque}
        assigned, out = set(), []
        for anchor, _ in opaque:
            if anchor in assigned:
                continue
            members = [k for k, _ in opaque if k not in assigned and math.dist(labs[anchor], labs[k]) <= threshold]
            assigned.update(members)
            if len(members) > 1:
                out.append({"anchor": anchor, "members": members,
                            "uses": sum(self.buckets["colors"][k][0] for k in members),
                            "max_distance": round(max(math.dist(labs[anchor], labs[k]) for k in members), 4)})
        return out

    def report(self, threshold: float) -> dict:
        def listing(bucket):
            items = sorted(self.buckets[bucket].items(), key=lambda kv: (-kv[1][0], kv[0]))
            return [{"value": k, "count": v[0], "locations": v[1]} for k, v in items]

        clusters = self.clusters(threshold)
        summary = {
            "files_scanned": self.files,
            "raw_colors": len(self.buckets["colors"]),
            "near_duplicate_clusters": len(clusters),
            "font_sizes": len(self.buckets["font_sizes"]),
            "spacing_off_scale": len(self.buckets["spacing_off_scale"]),
            "radii": len(self.buckets["radii"]),
            "shadows": len(self.buckets["shadows"]),
            "durations": len(self.buckets["durations_ms"]),
            "z_index_values": len(self.buckets["z_index"]),
            "flags": sum(v[0] for v in self.buckets["flags"].values()),
            "token_definitions": self.token_definitions,
            "var_uses": self.var_uses,
        }
        return {"tool": "token_inventory", "version": VERSION, "summary": summary,
                "near_duplicate_colors": clusters,
                **{k: listing(k) for k in self.buckets}}


def iter_files(paths, excludes):
    for base in paths:
        if os.path.isfile(base):
            yield base, os.path.basename(base)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, base)
                if os.path.splitext(name)[1].lower() not in EXTENSIONS or name.endswith(".min.css"):
                    continue
                if any(fnmatch.fnmatch(rel, pat) for pat in excludes) or os.path.islink(full):
                    continue
                yield full, rel


GROWTH_KEYS = ("raw_colors", "near_duplicate_clusters", "font_sizes", "spacing_off_scale", "radii",
               "shadows", "durations", "z_index_values", "flags")


def compare(summary: dict, baseline: dict) -> list[str]:
    base = baseline.get("summary", baseline)
    return [f"{k}: {base[k]} -> {summary[k]}" for k in GROWTH_KEYS
            if isinstance(base.get(k), int) and summary[k] > base[k]]


def render_text(rep: dict, growth: list[str] | None, top: int) -> str:
    s = rep["summary"]
    lines = [f"Style value inventory ({s['files_scanned']} files)",
             f"  raw colors {s['raw_colors']} | near-duplicate clusters {s['near_duplicate_clusters']} | "
             f"font sizes {s['font_sizes']} | off-scale spacing {s['spacing_off_scale']}",
             f"  radii {s['radii']} | shadows {s['shadows']} | durations {s['durations']} | "
             f"z-index values {s['z_index_values']} | flags {s['flags']}",
             f"  custom-property definitions {s['token_definitions']} | var() uses {s['var_uses']}"]
    for c in rep["near_duplicate_colors"][:top]:
        lines.append(f"  near-duplicates ({c['uses']} uses, max distance {c['max_distance']}): "
                     + ", ".join(c["members"]))
    sections = [("flags", "Flags"), ("colors", "Raw colors"), ("font_sizes", "Font sizes"),
                ("spacing_off_scale", "Off-scale spacing"), ("spacing_optical", "Optical nudges (below base)"),
                ("radii", "Radii"), ("shadows", "Shadows"), ("durations_ms", "Durations (ms)"),
                ("z_index", "z-index")]
    for key, title in sections:
        items = rep[key]
        if not items:
            continue
        lines.append(f"{title}:")
        for it in items[:top]:
            lines.append(f"  {it['value']}  x{it['count']}  {', '.join(it['locations'])}")
        if len(items) > top:
            lines.append(f"  ... {len(items) - top} more")
    if growth is not None:
        lines.append("Baseline: " + ("counts grew: " + "; ".join(growth) if growth else "no count grew"))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only inventory of raw style values (colors, type sizes, "
                                 "spacing, radii, shadows, durations, z-index) for design-system work.")
    ap.add_argument("paths", nargs="+", help="files or folders to scan")
    ap.add_argument("--spacing-base", type=float, default=4, help="spacing scale base in px (default 4)")
    ap.add_argument("--root-px", type=float, default=16, help="px per rem (default 16)")
    ap.add_argument("--near", type=float, default=0.02, help="OKLab distance for near-duplicate colors (default 0.02)")
    ap.add_argument("--token-glob", action="append", default=None,
                    help="glob for token source files (repeatable; default *token* and *theme*)")
    ap.add_argument("--exclude", action="append", default=[], help="glob of relative paths to skip (repeatable)")
    ap.add_argument("--baseline", help="earlier --json output; exit 1 if any count grew")
    ap.add_argument("--top", type=int, default=12, help="entries shown per section in text output")
    ap.add_argument("--max-locations", type=int, default=3, help="locations kept per value")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    for p in args.paths:
        if not os.path.exists(p):
            print(f"error: no such path: {p}", file=sys.stderr)
            return 2
    if args.spacing_base <= 0 or args.root_px <= 0 or args.near < 0:
        print("error: --spacing-base and --root-px must be positive, --near not negative", file=sys.stderr)
        return 2
    baseline = None
    if args.baseline:
        try:
            with open(args.baseline, encoding="utf-8") as fh:
                baseline = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"error: cannot read baseline: {exc}", file=sys.stderr)
            return 2

    token_globs = args.token_glob or ["*token*", "*theme*"]
    inv = Inventory(args.root_px, args.spacing_base, args.max_locations)
    for full, rel in iter_files(args.paths, args.exclude):
        try:
            if os.path.getsize(full) > MAX_BYTES:
                continue
            with open(full, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        is_token = any(fnmatch.fnmatch(os.path.basename(full).lower(), g.lower()) for g in token_globs)
        inv.scan_text(text, rel.replace(os.sep, "/"), is_token)

    rep = inv.report(args.near)
    growth = compare(rep["summary"], baseline) if baseline is not None else None
    if growth is not None:
        rep["baseline_growth"] = growth
    print(json.dumps(rep, indent=2, sort_keys=False) if args.json else render_text(rep, growth, args.top))
    s = rep["summary"]
    needs_review = s["flags"] or s["near_duplicate_clusters"] or s["spacing_off_scale"] or bool(growth)
    return 1 if needs_review else 0


if __name__ == "__main__":
    sys.exit(main())
