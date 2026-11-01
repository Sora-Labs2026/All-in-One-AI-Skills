# Measuring a reference look: color, tone and cut rhythm as data

Read this when the brief is "make ours feel like these": you have reference footage or stills (the user's earlier work, a licensed mood film, footage you are allowed to analyze) and need new footage, generated shots or a whole edit to match their grade and pacing consistently. The method: measure the references into a small **style pack** of numbers, apply it to your own material, and verify the output with the same measurements. Code sketches use NumPy and OpenCV (2025 releases); `scripts/cut_rhythm.py` handles the pacing part with the standard library.

Contents: measure, do not copy · direction before numbers · the style pack · measuring color and tone · measuring cut rhythm · building a LUT · applying it · verifying · handoff · done when.

## Measure, do not copy

- **Statistics describe a look; frames are the work.** Color distributions, contrast and shot-length distributions are measurements. Frames, overlays, flares lifted from frames, title cards, footage and music belong to their authors.
- **References stay private.** Keep them in a `refs/` folder that never ships, never appears in deliverables, and is never uploaded as conditioning to a generation service unless the user holds the rights for that use.
- **Make your own graphic elements.** Do not cut light leaks, glitches or type out of someone else's video; design or shoot your own.
- **No imitation of a living artist's signature style on request** (`generation-prompting.md`, "Safety, likeness and rights"). Describe the qualities you want and build an original direction; measured numbers help you do that honestly.
- **Screen recordings of other people's posts** carry their interface, captions and content; they are references at most, never footage.

This is practice guidance, not legal advice; for commercial work with borrowed material, the user should check with counsel (`../../legal-ready/GUIDE.md`).

## Direction before numbers

Write the direction in words first, in `notes.md`, before measuring anything:

- One primary look and at most one accent look. Several looks at once read as no look.
- A small rule set you can check per shot, for example "one accent color per shot", "warm light only in dark frames", "backgrounds stay near black".
- An avoid list.
- **Keep look and content separate:** one field for what happens (subject, action, place), one for how it looks (palette, contrast, grain, light). Mixing them leaks style words into the scene ("teal" becomes a teal object) and scene words into the grade.

## The style pack

```
looks/<look-name>/
  pack.json      name, version, date, the reference files' SHA-256 and durations, tools and versions used
  grade.json     tone and per-zone color statistics (below)
  cadence.json   every shot length and the distribution (scripts/cut_rhythm.py output)
  look.cube      optional 3D LUT reproducing the per-pixel part of the grade
  notes.md       the written direction, rules, avoid list, and how the numbers were taken
```

- One look per pack. Never pool references of two looks into one set of numbers.
- A measured zero is a value; a missing field means "not measured". Keep the difference.
- Regenerate packs from the references with a script rather than editing numbers by hand.

## Measuring color and tone

1. **Sample by shot, not by second,** so long shots do not dominate: a few frames from each detected shot.
2. **Mask what is not the look:** letterbox bars, burned-in captions, logos, watermarks and interface overlays. Static elements show up in a per-pixel temporal median of many frames as sharp edges while moving content blurs away; crop or mask those regions. Animated overlays (a pulsing icon, a ticking counter) also have stable edges in the median, so check the mask by eye.
3. **Work in a perceptual space** (CIELAB or OKLab), converted from correctly decoded sRGB or Rec.709 values. With OpenCV, convert float images scaled to 0-1, which give L* from 0 to 100 and signed a* and b*; 8-bit input instead gives L* from 0 to 255 and a*, b* offset by 128, and mixing the two conventions produces nonsense.
4. **Record robust statistics:**
   - black point and white point as low and high percentiles of L* (for example the 1st and 99th), not min and max;
   - contrast as the standard deviation of L* (the min-to-max range is close to 100 for almost any footage and tells you nothing);
   - the share of near-black pixels (L* below about 10), because a grade can match mean and spread while lifting the blacks to gray;
   - median and median absolute deviation, not mean and standard deviation, for chroma, which is skewed;
   - **color per luminance zone:** median a*, b* and chroma in bands of L* (for example 0-15, 15-35, 35-55, 55-75, 75-100). Split toning (cool shadows, warm highlights, a tint only in the midtones) lives in one band; a single global average cannot represent it. Keep the whole curve, not just the ends.

```python
import cv2, numpy as np
ZONES = [0, 15, 35, 55, 75, 100]

def grade_stats(frames_bgr, mask=None):
    """frames_bgr: list of uint8 BGR frames; mask: boolean array of pixels that belong to the look."""
    labs = [cv2.cvtColor(f.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB) for f in frames_bgr]
    pix = np.concatenate([(lab[mask] if mask is not None else lab.reshape(-1, 3)) for lab in labs])
    L, a, b = pix[:, 0], pix[:, 1], pix[:, 2]
    out = {"black_point": float(np.percentile(L, 1)), "white_point": float(np.percentile(L, 99)),
           "contrast_std": float(L.std()), "near_black_share": float((L < 10).mean()), "zones": []}
    for lo, hi in zip(ZONES, ZONES[1:]):
        sel = (L >= lo) & ((L < hi) if hi < 100 else (L <= hi))
        zone = {"L": [lo, hi], "share": float(sel.mean())}
        if sel.sum() >= 500:                       # too few pixels give unstable medians
            c = np.hypot(a[sel], b[sel])
            zone.update(a_med=float(np.median(a[sel])), b_med=float(np.median(b[sel])),
                        chroma_med=float(np.median(c)), chroma_mad=float(np.median(abs(c - np.median(c)))))
        out["zones"].append(zone)
    return out
```

## Measuring cut rhythm

1. **Detect shot boundaries** with FFmpeg's scene score or PySceneDetect. The right threshold depends on the material: a high-contrast reference cuts clearly, a moody one hides its cuts. Sweep thresholds from high to low and take the highest one that still finds nearly all the boundaries the most sensitive setting finds; discard settings that imply implausible cut rates (camera moves, flashes and strobes trigger false cuts). Dissolves need a fade-aware detector.
2. **Spot-check boundaries by eye** at a handful of detected cuts and in a few long shots.
3. **Summarize the distribution, not just the mean:**

```bash
ffmpeg -i refs/a.mp4 -vf "select='gt(scene,0.35)',showinfo" -f null - 2> refs/a.scenes.log
python3 <productcraft>/modules/creative-media/scripts/cut_rhythm.py refs/a.scenes.log --duration 62.4 --fps 25 --json > looks/night-run/cadence.json
python3 <productcraft>/modules/creative-media/scripts/cut_rhythm.py refs/a.scenes.log --duration 62.4 --fps 25 --plan 30 --seed 7
```

   The script reports shot count, median, median absolute deviation, percentiles, cuts per minute and suspect very short shots, and with `--plan` draws a seeded sequence of shot lengths for a target duration from the measured distribution, snapped to whole frames (or to beats with `--bpm`). Two edits with the same mean shot length but different spread feel completely different, so plans sample from the distribution instead of repeating the mean.
4. **Music-driven edits:** express lengths in beats. Frames per beat = fps × 60 ÷ BPM (at 30 fps and 120 BPM, 15 frames). Cut on beats or transients; `--bpm` snaps the plan to the beat grid.

## Building a LUT

A 3D LUT is a fixed per-pixel RGB-to-RGB function. Use one when the look must travel to an editor, a colorist or many clips.

- **Only per-pixel transforms fit in a LUT.** Anything that depends on a clip's own distribution (matching its histogram to the reference) must either become a fixed transform first, or be applied per clip outside the LUT.
- **Shift color per zone by offsets** toward the reference medians and blend smoothly between zones. Scaling by the ratio of standard deviations overshoots on low-variance sources and can flip a tint's sign.
- **Anchor tone, do not force the whole histogram.** Match black point, median and white point; forcing a mostly dark shot onto a bright reference histogram lifts its blacks.
- **Gamut:** shifting Lab values can leave the RGB gamut. Some conversion routines clip silently, which hides how much was clipped; measure the out-of-gamut share with your own conversion, then clip or compress deliberately.
- **Write `.cube`:** a `LUT_3D_SIZE 33` header, input domain 0-1, then size³ lines of `R G B` with red changing fastest. The LUT expects display-referred Rec.709 input; apply camera log conversions before it.
- **In an editor:** place the LUT on its own node or adjustment layer as the first creative step, with corrections after it. In FFmpeg: `lut3d=file=look.cube:interp=tetrahedral`. Never apply it to shots that are already graded.

## Applying the look

- **Your footage:** correct each clip to neutral first (white balance, exposure, black level), match clips to a hero shot, then apply the look once.
- **Generated shots:** ask the model for the content, light structure, framing and motion, and request neutral color; apply the grade afterwards. Color words in prompts are an unreliable way to hit a measured grade. When the reference cuts fast, generate a few longer continuous takes and cut inside them instead of one generation per shot: fewer calls, less waste, and consecutive shots that belong together (`hosted-media-generation.md`).
- **Cutting:** cut frame-accurately with re-encoding (`video-editing.md`); when supplementing existing footage, cut at its own shot boundaries, because slicing one continuous shot into adjacent pieces produces cuts nobody sees.
- **3D renders and composites:** render with a neutral view transform (Blender's Standard rather than a filmic one such as AgX) or to scene-linear EXR, so the look is applied once in the grade and not twice (`blender-motion-inspection.md`).

## Verifying

- **Re-measure the output with the same code** and compare metric by metric against the pack: per-zone a* and b* (median against median), contrast, black and white points, near-black share, and the cadence median and spread. Present a table: metric, reference, output, difference.
- **Never trust one aggregate error number.** A small average color error can hide lifted blacks, a broken zone or banding; check each metric and look at the frames.
- **Banding:** in smooth gradients (sky, walls) count empty L* histogram bins lying between occupied ones; heavy grades of 8-bit compressed sources band. Grade from higher-bit sources where possible and add fine grain or dither.
- **Look:** compare stills from the output and the references side by side at the same size, then watch the cut with sound.

## Handoff

Deliver the graded shots, the editable timeline (`video-editing.md`, "Handing off a timeline"), `look.cube`, and `notes.md` with the measured targets: the zone table, tone figures, the shot-length distribution including its spread, and an explicit "do not" list (do not re-apply the LUT to delivered shots; set the project frame rate before import).

## Done when

- The direction is written, references are lawfully held and private, and nothing from them appears in the deliverable.
- The pack records how every number was measured, from which files (hashes) and with which tool versions.
- The output was re-measured; each metric is within the tolerance agreed with the user, and stills and the full cut were reviewed by eye.
- Shot lengths follow the measured distribution, not just its mean.
