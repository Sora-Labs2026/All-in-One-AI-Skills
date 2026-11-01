#!/usr/bin/env python3
"""ProductCraft cut-rhythm analyzer. Read-only: it reads a list of cuts and prints statistics.

Turns detected shot boundaries into a shot-length distribution, the "cadence"
part of a style pack, and can draw a seeded plan of shot lengths for a new edit
from that distribution.

Input (auto-detected; a file path or "-" for standard input):
  * an FFmpeg log from  -vf "select='gt(scene,0.3)',showinfo"  (reads pts_time values)
  * a CSV with a header naming start (and optionally end) columns, such as a
    scene list exported by a scene detector; seconds columns are preferred
  * a plain list of cut times in seconds or HH:MM:SS(.mmm), or HH:MM:SS:FF with --fps

Cut times become shots from 0 to the first cut, between cuts, and from the last
cut to --duration. Without --duration the last shot's length is unknown and is
left out (a warning says so). CSV rows with both start and end are used as shots.

Statistics: shot count, total, mean, median, median absolute deviation, 10th,
25th, 75th and 90th percentiles, min, max, cuts per minute, coefficient of
variation; in frames with --fps and in beats with --bpm. Shots shorter than
--min-shot seconds (default two frames, or 0.08 s without --fps) are listed as
suspect: they are often flashes or false detections.

--plan SECONDS draws shot lengths from the measured shots (sampling with
replacement, seeded with --seed) until the target is filled, snapped to whole
frames, or to the beat grid with --bpm; the plan's total equals the target
rounded to whole frames. Suspect shots are left out of the sampling pool unless
--keep-suspect is given.

Exit codes: 0 no warnings; 1 warnings (suspect shots, too few shots, unknown last
shot); 2 usage or parse error.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import re
import statistics
import sys

VERSION = "1.0.0"
PTS = re.compile(r"pts_time:\s*(-?\d+(?:\.\d+)?)")
TC_SEC = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)$")
TC_FRAMES = re.compile(r"^(\d+):(\d{2}):(\d{2})([:;])(\d{2})$")


class InputError(ValueError):
    pass


def parse_time(token: str, fps: float | None) -> float:
    token = token.strip()
    try:
        return float(token)
    except ValueError:
        pass
    m = TC_SEC.match(token)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = TC_FRAMES.match(token)
    if m:
        if m.group(4) == ";":
            raise InputError("drop-frame timecode is not supported; export times in seconds")
        if not fps:
            raise InputError("HH:MM:SS:FF timecode needs --fps")
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(5)) / fps
    raise InputError(f"not a time: {token!r}")


def pick_column(header: list[str], word: str):
    cols = [i for i, h in enumerate(header) if word in h.lower()]
    for pref in ("second", "time", ""):
        for i in cols:
            if pref in header[i].lower() and not (pref == "time" and "frame" in header[i].lower()):
                return i
    return None


def read_input(text: str, fps: float | None):
    """Return (cut_times, explicit_shots, end_time)."""
    pts = PTS.findall(text)
    if pts:
        return [float(p) for p in pts], None, None
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if "," in line and "start" in line.lower():
            rows = list(csv.reader(io.StringIO("\n".join(lines[idx:]))))
            header, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
            si, ei = pick_column(header, "start"), pick_column(header, "end")
            if si is None:
                break
            starts, shots, end = [], [], None
            for r in body:
                start = parse_time(r[si], fps)
                starts.append(start)
                if ei is not None and ei < len(r) and r[ei].strip():
                    stop = parse_time(r[ei], fps)
                    shots.append((start, stop))
                    end = stop if end is None else max(end, stop)
            if shots and len(shots) == len(body):
                return [], shots, end
            return starts, None, end
    tokens = [t for t in re.split(r"[\s,]+", text) if t]
    return [parse_time(t, fps) for t in tokens], None, None


def percentile(sorted_vals: list[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def build_shots(cuts, explicit, end, duration):
    warnings = []
    if explicit is not None:
        shots = [(s, e - s) for s, e in sorted(explicit) if e > s]
        return shots, warnings
    total = duration if duration is not None else end
    points = sorted({round(c, 6) for c in cuts if c > 0 and (total is None or c < total)})
    bounds = [0.0] + points
    if total is not None:
        bounds.append(total)
    else:
        warnings.append("last shot length unknown: pass --duration to include it")
    shots = [(bounds[i], bounds[i + 1] - bounds[i]) for i in range(len(bounds) - 1)]
    return shots, warnings


def summarize(lengths, fps, bpm):
    vals = sorted(lengths)
    med = statistics.median(vals)
    mean = statistics.fmean(vals)
    total = sum(vals)
    out = {
        "shots": len(vals), "total_s": round(total, 4), "mean_s": round(mean, 4), "median_s": round(med, 4),
        "mad_s": round(statistics.median(abs(v - med) for v in vals), 4),
        "p10_s": round(percentile(vals, 0.10), 4), "p25_s": round(percentile(vals, 0.25), 4),
        "p75_s": round(percentile(vals, 0.75), 4), "p90_s": round(percentile(vals, 0.90), 4),
        "min_s": round(vals[0], 4), "max_s": round(vals[-1], 4),
        "cuts_per_minute": round((len(vals) - 1) / total * 60, 2) if total > 0 else None,
        "coefficient_of_variation": round(statistics.pstdev(vals) / mean, 3) if mean > 0 else None,
    }
    if fps:
        out["median_frames"] = round(med * fps, 2)
        out["p10_frames"] = round(out["p10_s"] * fps, 2)
        out["p90_frames"] = round(out["p90_s"] * fps, 2)
    if bpm:
        out["median_beats"] = round(med * bpm / 60, 3)
    return out


def plan(lengths, target_s, fps, bpm, grid, seed):
    rng = random.Random(seed)
    target_frames = round(target_s * fps)
    if target_frames < 1:
        raise InputError("--plan is shorter than one frame")
    beat_s = 60 / bpm * grid if bpm else None
    boundaries, pos_units, pos_frames = [0], 0, 0
    while True:
        sample = rng.choice(lengths)
        if beat_s:
            units = max(1, round(sample / beat_s))
            nxt = round((pos_units + units) * beat_s * fps)
        else:
            units = max(1, round(sample * fps))
            nxt = pos_frames + units
        if nxt >= target_frames:
            remainder = target_frames - pos_frames
            if remainder * 2 < nxt - pos_frames and len(boundaries) > 1:
                boundaries[-1] = target_frames   # too short to stand alone: extend the previous shot
            else:
                boundaries.append(target_frames)
            break
        boundaries.append(nxt)
        pos_units += units
        pos_frames = nxt
    shots = []
    for i in range(len(boundaries) - 1):
        a, b = boundaries[i], boundaries[i + 1]
        item = {"index": i + 1, "start_frame": a, "frames": b - a,
                "start_s": round(a / fps, 4), "duration_s": round((b - a) / fps, 4)}
        if bpm:
            item["beats"] = round((b - a) / fps * bpm / 60, 3)
        shots.append(item)
    return {"target_s": target_s, "fps": fps, "bpm": bpm, "beat_grid": grid if bpm else None, "seed": seed,
            "total_frames": target_frames, "shots": shots}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Shot-length distribution from detected cuts, and a seeded "
                                 "shot-length plan for a new edit.")
    ap.add_argument("input", help="FFmpeg showinfo log, scene-list CSV or plain list of cut times; '-' for stdin")
    ap.add_argument("--duration", type=float, help="total duration in seconds (closes the last shot)")
    ap.add_argument("--fps", type=float, help="frame rate, for frame counts, frame timecodes and plans")
    ap.add_argument("--bpm", type=float, help="tempo, for lengths in beats and beat-snapped plans")
    ap.add_argument("--beat-grid", type=float, default=1.0, help="plan grid in beats with --bpm (default 1)")
    ap.add_argument("--min-shot", type=float, help="seconds below which a shot is suspect")
    ap.add_argument("--plan", type=float, metavar="SECONDS", help="draw a shot-length plan of this length")
    ap.add_argument("--seed", type=int, default=1, help="seed for --plan (default 1)")
    ap.add_argument("--keep-suspect", action="store_true", help="let --plan sample suspect short shots too")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    for name in ("duration", "fps", "bpm", "min_shot", "plan"):
        val = getattr(args, name)
        if val is not None and val <= 0:
            print(f"error: --{name.replace('_', '-')} must be positive", file=sys.stderr)
            return 2
    if args.beat_grid <= 0:
        print("error: --beat-grid must be positive", file=sys.stderr)
        return 2
    if args.plan is not None and not args.fps:
        print("error: --plan needs --fps", file=sys.stderr)
        return 2
    try:
        if args.input == "-":
            text = sys.stdin.read()
        else:
            with open(args.input, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        cuts, explicit, end = read_input(text, args.fps)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    shots, warnings = build_shots(cuts, explicit, end, args.duration)
    if not shots:
        print("error: no shots found in the input", file=sys.stderr)
        return 2
    lengths = [length for _, length in shots]
    stats = summarize(lengths, args.fps, args.bpm)
    min_shot = args.min_shot or (2 / args.fps if args.fps else 0.08)
    suspect = [{"index": i + 1, "start_s": round(s, 4), "length_s": round(length, 4)}
               for i, (s, length) in enumerate(shots) if length < min_shot]
    if suspect:
        warnings.append(f"{len(suspect)} shot(s) shorter than {min_shot:.3f} s: flashes or false cuts? check them by eye")
    if len(shots) < 3:
        warnings.append("fewer than 3 shots: too few for a distribution")
    result = {"tool": "cut_rhythm", "version": VERSION, "stats": stats,
              "shot_lengths_s": [round(x, 4) for x in lengths], "suspect_shots": suspect, "warnings": warnings}
    if args.plan is not None:
        flagged = {sh["index"] for sh in suspect}
        pool = [x for i, x in enumerate(lengths) if args.keep_suspect or i + 1 not in flagged] or lengths
        try:
            result["plan"] = plan(pool, args.plan, args.fps, args.bpm, args.beat_grid, args.seed)
        except InputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        s = stats
        print(f"{s['shots']} shots over {s['total_s']:.2f} s; median {s['median_s']:.3f} s "
              f"(MAD {s['mad_s']:.3f}); p10-p90 {s['p10_s']:.3f}-{s['p90_s']:.3f} s; "
              f"{s['cuts_per_minute']} cuts/min; CV {s['coefficient_of_variation']}")
        if args.fps:
            print(f"  median {s['median_frames']} frames at {args.fps:g} fps")
        if args.bpm:
            print(f"  median {s['median_beats']} beats at {args.bpm:g} BPM")
        for w in warnings:
            print(f"  warning: {w}")
        if "plan" in result:
            p = result["plan"]
            print(f"Plan: {len(p['shots'])} shots, {p['total_frames']} frames (seed {p['seed']})")
            for sh in p["shots"]:
                extra = f", {sh['beats']} beats" if "beats" in sh else ""
                print(f"  {sh['index']:>3}  start {sh['start_s']:>8.3f} s  {sh['frames']:>4} frames{extra}")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
