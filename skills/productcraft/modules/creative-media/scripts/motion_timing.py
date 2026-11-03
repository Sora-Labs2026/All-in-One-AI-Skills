#!/usr/bin/env python3
"""ProductCraft motion timing calculator. Read-only, standard library, deterministic.

Turns direction into whole frames so a brief and its review notes can name exact frames.

Subcommands:
  frames --fps F --ms MS [MS ...]          milliseconds to frames (rounded) at F fps
  beats  --fps F --bpm B [--bars N] [--beats-per-bar 4] [--offset-ms 0]
                                           beat grid computed from absolute time, so it never drifts;
                                           reports frames per beat and where rounding moves a beat
  loop   --fps F (--seconds S | --frames N) [--cycles C ...]
                                           frames to render (0..N-1) and whether each cycle count fits N
                                           exactly; with --period-frames P ... checks given periods
  gif    --fps F --frames N                GIF frame delays in hundredths of a second that add up to the
                                           exact loop length; warns about delays browsers clamp
  hold   --words W [--fps F] [--base 0.5] [--per-word 0.3]
                                           minimum reading hold for on-screen text
  blur   --fps F [--subframes 4] [--shutter 180] [--frame 0]
                                           subframe times for motion blur: k samples spread evenly over
                                           the open-shutter part of each frame (180 degrees = half a frame);
                                           average them in linear light

Add --json for machine-readable output. Exit codes: 0 ok, 1 a warning (drift,
a cycle that does not fit, clamped GIF delays), 2 usage error.
"""
import argparse
import json
import math
import sys
from fractions import Fraction

VERSION = "1.0.0"


def to_fraction(x):
    return Fraction(str(x))


def rnd(x):
    """Round half up (frame math should not use banker's rounding)."""
    return math.floor(Fraction(x) + Fraction(1, 2))


def cmd_frames(a):
    fps = to_fraction(a.fps)
    rows = []
    for ms in a.ms:
        exact = to_fraction(ms) * fps / 1000
        rows.append({"ms": ms, "frames": max(0, rnd(exact)), "exact": float(exact)})
    return {"fps": a.fps, "conversions": rows}, [], [f"{r['ms']:g} ms = {r['frames']} frames (exact {r['exact']:.3f})" for r in rows]


def cmd_beats(a):
    fps, bpm = to_fraction(a.fps), to_fraction(a.bpm)
    per_beat = fps * 60 / bpm
    total = a.bars * a.beats_per_bar
    offset = to_fraction(a.offset_ms) * fps / 1000
    grid, warnings = [], []
    for k in range(total + 1):
        exact = offset + k * per_beat
        frame = rnd(exact)
        grid.append({"beat": k, "bar": k // a.beats_per_bar + 1, "beat_in_bar": k % a.beats_per_bar + 1,
                     "frame": frame, "exact": float(exact), "downbeat": k % a.beats_per_bar == 0})
    naive_step = rnd(per_beat)
    naive_drift = abs(naive_step * total + rnd(offset) - float(offset + total * per_beat))
    if per_beat.denominator != 1 and naive_drift >= 1:
        warnings.append(f"adding a rounded {naive_step}-frame step drifts {naive_drift:.1f} frames by beat {total}; "
                        "use the absolute frames listed")
    lines = [f"{float(per_beat):.4f} frames per beat at {a.fps:g} fps, {a.bpm:g} BPM"
             + ("" if per_beat.denominator == 1 else " (not whole: compute each beat from absolute time)")]
    for g in grid:
        mark = "bar " + str(g["bar"]) if g["downbeat"] else "    "
        lines.append(f"  {mark:7} beat {g['beat']:3}  frame {g['frame']:6}  (exact {g['exact']:.2f})")
    return {"fps": a.fps, "bpm": a.bpm, "frames_per_beat": float(per_beat), "grid": grid}, warnings, lines


def cmd_loop(a):
    fps = to_fraction(a.fps)
    if a.frames is not None:
        n = a.frames
    else:
        exact = to_fraction(a.seconds) * fps
        n = rnd(exact)
    warnings = []
    if a.seconds is not None and to_fraction(a.seconds) * fps != n:
        warnings.append(f"{a.seconds:g} s at {a.fps:g} fps is {float(to_fraction(a.seconds) * fps):.3f} frames; "
                        f"the loop uses {n}")
    checks = []
    for c in a.cycles or []:
        fits = float(c).is_integer() and c > 0
        checks.append({"cycles": c, "fits": fits, "period_frames": n / c if c else None})
        if not fits:
            warnings.append(f"{c:g} cycles over the loop leaves a seam; use a whole number of cycles")
    for p in a.period_frames or []:
        fits = p > 0 and n % p == 0
        checks.append({"period_frames": p, "fits": fits, "cycles": n / p if p else None})
        if not fits:
            warnings.append(f"a period of {p} frames does not divide {n}; nearest fits: "
                            f"{', '.join(str(d) for d in nearest_divisors(n, p))}")
    lines = [f"render frames 0..{n - 1} ({n} frames, {n / float(fps):.3f} s); never render frame {n}",
             "phase = frame / " + str(n) + "; value = f(sin(2*pi*cycles*phase)) with whole cycles"]
    for c in checks:
        if "cycles" in c and c.get("period_frames") is not None and "fits" in c:
            lines.append(f"  cycles {c['cycles']:g} -> period {c['period_frames']:g} frames: "
                         + ("fits" if c["fits"] else "SEAM"))
    return {"fps": a.fps, "frames": n, "render_range": [0, n - 1], "checks": checks}, warnings, lines


def nearest_divisors(n, p):
    divs = [d for d in range(1, n + 1) if n % d == 0]
    return sorted(divs, key=lambda d: (abs(d - p), d))[:2]


def cmd_gif(a):
    fps = to_fraction(a.fps)
    n = a.frames
    total_cs = n * 100 / fps          # exact loop length in hundredths
    delays, prev = [], 0
    for i in range(1, n + 1):
        edge = rnd(i * 100 / fps)   # cumulative boundary, rounded once per frame: no drift
        delays.append(edge - prev)
        prev = edge
    warnings = []
    if total_cs.denominator != 1:
        warnings.append(f"the loop is {float(total_cs):.2f} hundredths long; GIF timing rounds it to {sum(delays)}")
    clamped = sum(1 for d in delays if d < 2)
    if clamped:
        warnings.append(f"{clamped} delay(s) under 2 hundredths: browsers stretch these to about 10; use 50 fps or less")
    uneven = len(set(delays)) > 1
    exact_rates = [r for r in (50, 25, 20, 10) if 100 % r == 0]
    lines = [f"{n} frames at {a.fps:g} fps -> delays (hundredths): {compress(delays)}",
             f"loop length {sum(delays) / 100:.2f} s" + (" (uneven delays spread the remainder)" if uneven else ""),
             "exact GIF rates: " + ", ".join(f"{r} fps" for r in exact_rates)]
    return {"fps": a.fps, "frames": n, "delays_cs": delays, "total_cs": sum(delays)}, warnings, lines


def compress(seq):
    out, i = [], 0
    while i < len(seq):
        j = i
        while j + 1 < len(seq) and seq[j + 1] == seq[i]:
            j += 1
        out.append(f"{seq[i]}x{j - i + 1}" if j > i else str(seq[i]))
        i = j + 1
    return " ".join(out)


def cmd_hold(a):
    seconds = a.base + a.per_word * a.words
    data = {"words": a.words, "seconds": round(seconds, 3)}
    lines = [f"{a.words} words: hold at least {seconds:.2f} s"]
    if a.fps:
        frames = math.ceil(round(seconds * a.fps, 6))
        data["frames"] = frames
        lines[0] += f" = {frames} frames at {a.fps:g} fps"
    return data, [], lines


def cmd_blur(a):
    fps = to_fraction(a.fps)
    open_part = to_fraction(a.shutter) / 360            # share of the frame interval the shutter is open
    k = a.subframes
    offsets = [open_part * (Fraction(2 * i + 1, 2 * k)) for i in range(k)]   # centre of each slice
    times = [(a.frame + o) / fps for o in offsets]
    warnings = []
    if k < 2:
        warnings.append("one subframe gives no blur; use 4 or more")
    lines = [f"frame {a.frame} at {a.fps:g} fps, {a.shutter:g}-degree shutter ({float(open_part) * 100:.0f}% of the frame open), "
             f"{k} subframes:"]
    lines += [f"  subframe {i}: t = {float(tm):.6f} s (frame + {float(o):.4f})" for i, (tm, o) in enumerate(zip(times, offsets))]
    lines.append("render each, convert to linear light, average, convert back to sRGB")
    return {"fps": a.fps, "frame": a.frame, "shutter_degrees": a.shutter, "subframes": k,
            "offsets_frames": [float(o) for o in offsets], "times_s": [float(x) for x in times]}, warnings, lines


def positive(x):
    v = float(x)
    if v <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("frames"); p.add_argument("--fps", type=positive, required=True)
    p.add_argument("--ms", type=float, nargs="+", required=True)
    p = sub.add_parser("beats"); p.add_argument("--fps", type=positive, required=True)
    p.add_argument("--bpm", type=positive, required=True); p.add_argument("--bars", type=int, default=4)
    p.add_argument("--beats-per-bar", type=int, default=4); p.add_argument("--offset-ms", type=float, default=0)
    p = sub.add_parser("loop"); p.add_argument("--fps", type=positive, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--seconds", type=positive); g.add_argument("--frames", type=int)
    p.add_argument("--cycles", type=float, nargs="+"); p.add_argument("--period-frames", type=int, nargs="+")
    p = sub.add_parser("gif"); p.add_argument("--fps", type=positive, required=True)
    p.add_argument("--frames", type=int, required=True)
    p = sub.add_parser("hold"); p.add_argument("--words", type=int, required=True)
    p.add_argument("--fps", type=positive); p.add_argument("--base", type=float, default=0.5)
    p.add_argument("--per-word", type=float, default=0.3)
    p = sub.add_parser("blur"); p.add_argument("--fps", type=positive, required=True)
    p.add_argument("--subframes", type=int, default=4); p.add_argument("--shutter", type=float, default=180)
    p.add_argument("--frame", type=int, default=0)
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="print JSON")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 2
    if a.cmd in ("loop", "gif") and a.frames is not None and a.frames < 1:
        print("--frames must be at least 1", file=sys.stderr)
        return 2
    if a.cmd == "beats" and (a.bars < 1 or a.beats_per_bar < 1):
        print("--bars and --beats-per-bar must be at least 1", file=sys.stderr)
        return 2
    if a.cmd == "hold" and a.words < 0:
        print("--words must be 0 or more", file=sys.stderr)
        return 2
    if a.cmd == "blur" and (a.subframes < 1 or not 0 < a.shutter <= 360 or a.frame < 0):
        print("--subframes must be at least 1, --shutter between 0 and 360, --frame 0 or more", file=sys.stderr)
        return 2
    data, warnings, lines = {"blur": cmd_blur, "frames": cmd_frames, "beats": cmd_beats, "loop": cmd_loop,
                             "gif": cmd_gif, "hold": cmd_hold}[a.cmd](a)
    if a.json:
        print(json.dumps({"version": VERSION, "command": a.cmd, **data, "warnings": warnings}, indent=2))
    else:
        print("\n".join(lines))
        for w in warnings:
            print("WARN " + w)
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
