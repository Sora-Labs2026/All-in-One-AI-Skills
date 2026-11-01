#!/usr/bin/env python3
"""ProductCraft contrast check for text on translucent ("glass") surfaces. Read-only; no files written.

A translucent surface shows tint * alpha + backdrop * (1 - alpha), composited per
channel in sRGB as browsers do. Blur and saturation only mix and push backdrop
colors inside the RGB range, so when the backdrop can be anything, the worst case
is found by checking the whole range. This tool evaluates a grid over the RGB cube
(including pure black and white) or only the backdrop colors you pass with
--backdrop, and reports the lowest WCAG 2.x contrast ratio for the text.

Text drawn at reduced opacity (--text-alpha) is composited over the surface first.

Modes:
  check   --alpha A        worst-case ratio at a given tint opacity
  solve   --solve          smallest tint opacity (in steps of --step) from which every
                           higher opacity also meets --min

Exit codes: 0 the target is met (or a solving opacity exists); 1 it is not; 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

VERSION = "1.0.0"
HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def parse_hex(text: str):
    m = HEX.match(text.strip())
    if not m:
        raise ValueError(f"not a hex color: {text!r}")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def luminance(rgb) -> float:
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def mix(top, bottom, alpha: float):
    return tuple(t * alpha + u * (1 - alpha) for t, u in zip(top, bottom))


def grid_backdrops(levels: int):
    vals = sorted({round(i * 255 / (levels - 1)) for i in range(levels)})
    return [(r, g, b) for r in vals for g in vals for b in vals]


def worst_case(text, text_alpha, tint, alpha, backdrops):
    worst = None
    for bd in backdrops:
        surface = mix(tint, bd, alpha)
        shown = mix(text, surface, text_alpha)
        r = ratio(shown, surface)
        if worst is None or r < worst[0]:
            worst = (r, bd, surface)
    return worst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Worst-case WCAG contrast of text on a translucent surface "
                                 "over any backdrop, or over the backdrop colors you list.")
    ap.add_argument("--text", required=True, help="text color, hex (for example #FFFFFF)")
    ap.add_argument("--text-alpha", type=float, default=1.0, help="text opacity 0-1 (default 1)")
    ap.add_argument("--tint", required=True, help="surface tint color, hex")
    ap.add_argument("--alpha", type=float, help="tint opacity 0-1 to check")
    ap.add_argument("--solve", action="store_true", help="find the smallest tint opacity meeting --min")
    ap.add_argument("--min", type=float, default=4.5, help="target ratio (default 4.5; 3 for large text and UI)")
    ap.add_argument("--backdrop", action="append", default=[],
                    help="a backdrop color that can appear behind the surface (repeatable); default: any color")
    ap.add_argument("--levels", type=int, default=9, help="grid levels per channel for 'any backdrop' (default 9)")
    ap.add_argument("--step", type=float, default=0.005, help="opacity step when solving (default 0.005)")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    try:
        text, tint = parse_hex(args.text), parse_hex(args.tint)
        backdrops = [parse_hex(b) for b in args.backdrop]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.solve == (args.alpha is not None):
        print("error: give exactly one of --alpha or --solve", file=sys.stderr)
        return 2
    if not 0 <= args.text_alpha <= 1 or (args.alpha is not None and not 0 <= args.alpha <= 1):
        print("error: opacities must be between 0 and 1", file=sys.stderr)
        return 2
    if args.levels < 2 or not 0 < args.step <= 0.5 or args.min < 1:
        print("error: --levels >= 2, 0 < --step <= 0.5, --min >= 1", file=sys.stderr)
        return 2
    scope = "listed backdrops" if backdrops else "any backdrop"
    if not backdrops:
        backdrops = grid_backdrops(args.levels)

    result = {"tool": "glass_contrast", "version": VERSION, "text": to_hex(text), "text_alpha": args.text_alpha,
              "tint": to_hex(tint), "target": args.min, "scope": scope}
    if args.alpha is not None:
        r, bd, surface = worst_case(text, args.text_alpha, tint, args.alpha, backdrops)
        ok = r >= args.min
        result.update({"alpha": args.alpha, "worst_ratio": round(r, 2), "worst_backdrop": to_hex(bd),
                       "worst_surface": to_hex(surface), "meets_target": ok})
        line = (f"{'PASS' if ok else 'FAIL'}: worst-case {r:.2f}:1 (target {args.min}:1) over {scope}; "
                f"worst backdrop {to_hex(bd)} gives surface {to_hex(surface)} at alpha {args.alpha:g}")
    else:
        steps = int(round(1 / args.step))
        passes = []
        for i in range(steps + 1):
            a = min(1.0, i * args.step)
            passes.append((a, worst_case(text, args.text_alpha, tint, a, backdrops)))
        found = None
        for i in range(len(passes) - 1, -1, -1):
            if passes[i][1][0] >= args.min:
                found = passes[i]
            else:
                break
        ok = found is not None
        if ok:
            a, (r, bd, surface) = found
            result.update({"min_alpha": round(a, 4), "ratio_at_min_alpha": round(r, 2), "worst_backdrop": to_hex(bd),
                           "meets_target": True})
            line = (f"PASS: tint opacity {a:.3f} or more keeps {args.min}:1 over {scope} "
                    f"(worst {r:.2f}:1 against backdrop {to_hex(bd)})")
        else:
            r_full = passes[-1][1][0]
            result.update({"min_alpha": None, "ratio_at_full_opacity": round(r_full, 2), "meets_target": False})
            line = (f"FAIL: no tint opacity reaches {args.min}:1 over {scope}; a fully opaque tint gives "
                    f"{r_full:.2f}:1. Change the tint or the text color.")
    print(json.dumps(result, indent=2) if args.json else line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
