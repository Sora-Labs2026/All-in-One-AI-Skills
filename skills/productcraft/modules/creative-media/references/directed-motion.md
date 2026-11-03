# Directed motion graphics from code

Read this when an agent must produce studio-quality animation in code: motion graphics, kinetic type, product or logo animations, animated explainers, perfect loops, or 3D shots. It covers HTML with GSAP, Three.js, Remotion, HTML-to-video renderers and Blender, delivered as MP4 or GIF.

It covers four things:

- the render contract that makes every frame reproducible;
- a numeric brief;
- default motion numbers;
- a review loop that names exact frames.

Tool details live elsewhere:

- [remotion-video.md](remotion-video.md) for Remotion;
- [manim-explainers.md](manim-explainers.md) for math explainers;
- [blender-motion-inspection.md](blender-motion-inspection.md) for checking Blender motion;
- [video-editing.md](video-editing.md) for footage;
- [../../documents/references/animated-media.md](../../documents/references/animated-media.md) for small GIFs.

Interface motion (product UI rather than rendered video) is [../../ui-distiller/references/motion-engineering.md](../../ui-distiller/references/motion-engineering.md) and the `MOT` rules in [../../ui-rules.md](../../ui-rules.md).

## The idea in one paragraph

The agent writes a program that paints each frame. It does not generate pixels. The quality comes from three things, and talent is not one of them:

- a brief written in numbers instead of adjectives;
- code in which every frame is a pure function of time;
- a review loop that looks at actual frames and names the frame and the cause of each problem.

A vague prompt gives generic motion. A numeric brief, deterministic code and two to four rounds of frame-level notes give work that looks directed.

## 1. The render contract

Every frame must be a pure function of time: `draw(t)`, with `t` in seconds, or `draw(frame)`. The same input gives the same image on every run and on every machine.

| Rule | Why | How |
|---|---|---|
| Time comes only from an explicit `t` or frame index | Wall-clock time makes renders differ run to run and drop frames under load | Never use `Date.now()`, `performance.now()`, `new Date()` or a delta from the last tick for anything visible; pass `t` down |
| Randomness is seeded | `Math.random()` changes every run | One seeded generator (see [generative-art.md](generative-art.md)); Remotion's `random(seed)` |
| Every animation can be seeked | The renderer must be able to jump to frame 731 cold | GSAP: build timelines `paused: true` and call `tl.seek(t)`, or call `gsap.globalTimeline.pause()` and then seek. CSS and Web Animations: `document.getAnimations().forEach(a => { a.pause(); a.currentTime = t * 1000; })`. Video elements: set `currentTime` and wait for `seeked` |
| Assets are ready before frame 0 | A late font swaps glyphs mid-shot | `await document.fonts.ready`; `await img.decode()`; preload models and textures; render only after a ready flag is set |
| A frame can be frozen on demand | The agent and the reviewer must be able to look at one exact frame | Read `?t=2.5` or `?frame=75` from the URL, or expose `window.renderFrame(n)` that returns a promise once painted |
| Loops render frames 0 to N-1 only | Rendering frame N duplicates frame 0 and causes a visible hitch at the seam | `phase = frame / N`; every cyclic motion uses a whole number of cycles over N |
| No timers drive visible state | `setTimeout` and `setInterval` fire by wall-clock | Derive state from `t` (for example `visible = t >= 1.2`) |
| Physics and particles step at a fixed rate from a seed | Variable steps make the simulation diverge | Simulate in fixed steps from frame 0 (or cache states), with a seeded initial state |

`scripts/motion_contract_check.py` lints HTML, JS, TS and CSS for the usual breaches: wall-clock reads, unseeded randomness, timers, delta clocks, autoplaying media, GSAP timelines that are never paused or seeked, fonts without a ready wait, and a missing frame hook. It cannot prove determinism. The proof is in step 3 of the loop below: render the same frame twice and compare the hashes.

## 2. The directed brief

Fill in every line before writing code. Each adjective in the request becomes a number.

```text
GOAL:    one sentence: what the viewer should feel, understand or do afterwards
OUTPUT:  engine; width x height; fps; total frames; container and codec (for example "one HTML page + GSAP, 1080x1350, 30 fps, 240 frames, MP4 H.264")
TIME:    seconds x fps = frames; loop yes or no
LOOK:    palette as hex (background, text, one accent); typeface, weight, size in px, tracking; materials and light; grid and margins
MOTION:  easing curves (cubic-bezier), spring damping ratios, durations in frames, stagger in frames
SHOTS:   frame ranges, each with its one hero action and how it hands off (prefer hard cuts on a beat)
BANNED:  the patterns this piece must not use (start from the list below; add to it after every review)
QA:      frames to check as stills, a contact sheet, and any graphs of position against time
```

For 3D, add these lines:

```text
MODEL:   proportions and features that must never change; materials
CAMERA:  focal length or field of view; path; each move with start and end frames and easing
```

**BANNED starter list** (generic, machine-made motion):

- purple-to-blue gradients;
- glow, lens flares and bloom used as decoration;
- floating particles with no meaning;
- everything fading in at once;
- the same fade-and-slide-up on every element;
- everything centered;
- text that moves while someone is reading it;
- turntables and orbits with no purpose.

When a render shows a new cliché, add exactly that pattern to BANNED and re-render.

**One hero per shot.** One element performs the main action:

- **Secondary elements** travel about half to two-thirds as far and start 100-200 ms later.
- **Ambient motion** stays under about 5% of the hero's travel.

## 3. Default motion numbers

These are starting points to tune, not laws. Convert milliseconds to frames at the target rate with `scripts/motion_timing.py frames`.

**Easing**

| Use | Curve |
|---|---|
| Entrances | Ease-out, such as quint `cubic-bezier(0.22, 1, 0.36, 1)` or expo `cubic-bezier(0.16, 1, 0.3, 1)` |
| Exits | Ease-in, such as `cubic-bezier(0.64, 0, 0.78, 0)`, shorter than the entrance |
| Moves across the frame and camera moves | Ease-in-out, such as `cubic-bezier(0.65, 0, 0.35, 1)`; the softest curves belong to the camera |
| Linear | Only continuous rotation, progress, and the phase of a loop |

**Springs** (damping ratio ζ, comparable across libraries):

| ζ | Character |
|---|---|
| 1.0 | Settles with no overshoot |
| 0.7-0.85 | Restrained, premium |
| 0.4-0.6 | Playful |
| Below 0.3 | Cartoon |

Position and scale may overshoot. Opacity and color must never overshoot: clamp them.

**Durations**

| Motion | Duration |
|---|---|
| Small feedback | 100-200 ms |
| General moves | 200-500 ms |
| Hero reveals | 600-900 ms |
| Exits | 40-50% shorter than the matching entrance, so 50-60% of its length (Material 3 pairs a 400 ms emphasized entrance with a 200 ms exit) |

**Stagger**

| Unit | Gap |
|---|---|
| Letters | About 1 frame each |
| Words | 60-120 ms |
| List items | 40-80 ms |

Start the next element when the previous one is 30-50% complete.

**Holds.** Readable text stays still for at least 0.5 s plus 0.3 s per word (`motion_timing.py hold`). During a hold, allow only ambient motion, such as a push of 2% or less or a slow sine.

**Beat grid.**

- Frames per beat are `fps × 60 / BPM`.
- Compute each beat from absolute time, `round(k × 60 × fps / BPM)`. Never add a rounded step repeatedly, or the grid drifts.
- Cut on beats, and change the major layout every bar of four beats.
- `motion_timing.py beats` prints the grid.

**Parallax.** Use speeds of about 1.0 for the foreground, 0.5 for the midground and 0.2 for the background.

**Accessibility on every frame:**

- Text contrast is at least 4.5:1 against the actual moving background at the hold frames.
- No more than three flashes in any one-second period (WCAG 2.3.1).
- Provide captions for speech.

## 4. The production loop

1. Write the brief (section 2). Run the agent at a medium reasoning-effort setting; raise it only when a named problem needs deeper reasoning, because higher settings cost more time and money without improving routine shots.
2. Build the first version against the render contract.
3. **Prove determinism.** Render one mid-shot frame twice and compare the hashes. They must match.
4. Render the key frames as stills, plus a **contact sheet**: 12-24 frames on one image. Space them evenly by default; once the shots are known, use each shot's key frames or beats instead:
   ```bash
   ffmpeg -i draft.mp4 -vf "select='not(mod(n\,15))',scale=480:-1,tile=6x4" -frames:v 1 -update 1 sheet.png
   ```
5. For timing problems, plot position or scale against frame number for the hero element, or make an onion skin. To onion-skin, average a short frame range: `ffmpeg -i draft.mp4 -vf "trim=start_frame=60:end_frame=72,tmix=frames=12" -frames:v 1 onion.png`.
6. **Write notes that name a frame, a cause and a fix**, for example "Frame 84: the title peaks two frames late; move the peak to frame 82." Never write "make it pop". Convert every taste note into a number first.
7. Fix only the named issues, and re-render only the affected range.
8. Repeat steps 3 to 7. Two to four rounds is typical.
9. **Lock the picture, then add sound** placed at frame numbers (section 6).
10. Run the final encode and the delivery checks.

Keep the notes from each round in a short `notes.md`. They are the record of what changed and why, and they belong in the final report.

## 5. Rendering

**Quick preview.** A self-contained HTML page with a visible frame counter, played in a browser. It is fine for exploring and never good enough to deliver.

**Production render.** Use Node, Playwright with headless Chromium, and FFmpeg:

1. Open the page.
2. Wait for the ready flag.
3. For each frame `n` from 0 to N-1, call `renderFrame(n)`, wait for it to resolve and save a PNG screenshot.
4. Encode with FFmpeg.

Playwright's clock API (`page.clock.install()`, then `pauseAt` and `runFor`) can freeze page timers for code you do not control, but an explicit frame hook is more reliable.

**Motion blur** for 3D or fast moves (subframe averaging):

- A 180-degree shutter exposes half of each frame interval. Render k subframes spread across that half and average them; start with k = 4 and raise it only when fast motion still strobes. `motion_timing.py blur` prints the subframe times.
- Average in linear light: convert sRGB to linear, average, convert back. Averaging gamma-encoded pixels (FFmpeg's plain `tmix`) darkens bright edges, so blend inside the renderer, or convert to a linear format before `tmix`.

**Remotion** uses `useCurrentFrame()` and its own renderer; see [remotion-video.md](remotion-video.md). **HyperFrames** (Apache-2.0) does the same seek-and-capture loop for plain HTML: write HTML, CSS and JavaScript with timing attributes and seekable animations (GSAP, CSS, Three.js), and it renders a deterministic MP4 through headless Chrome and FFmpeg. Check the current license file and that every animation is seekable.

**Three.js:**

- Drive every update from `t`, never from `THREE.Clock` or `getDelta()`.
- Set a fixed pixel ratio.
- Use `preserveDrawingBuffer: true` only when reading pixels back from the canvas.

**Blender:**

- Keyframe or drive everything from the frame number.
- Render headless with `blender -b scene.blend -a`, or render a range with `-s`, `-e` and `-a`.
- Pin the Blender version and seed the noise. Cycles noise differs per frame unless its seed is animated deliberately.

## 6. Sound and the last mile

**Picture first.** The piece must work muted, because many feeds play without sound.

**Sync:**

- Land each hit exactly one frame after its visual event. Never place a sound before its picture.
- Audio that leads the picture is noticed sooner than audio that lags (ITU-R BT.1359).
- Measure the decoded audio against frame numbers, not the timeline in an editor.

**Loudness:**

- Many streaming and social platforms normalize to about -14 LUFS integrated with -1 dBTP true peak.
- Broadcast targets differ (EBU R 128 is -23 LUFS).
- Measure and normalize in two passes with FFmpeg's `loudnorm`; see [video-editing.md](video-editing.md).

**Perfect loops:**

- Frame 0 is already a finished composition, not a build-up.
- Render frames 0 to N-1.
- Check that the jump from frame N-1 to frame 0 is no larger than any other step.
- `motion_timing.py loop` checks that every cycle fits N exactly.

**MP4 for posts:**

```bash
ffmpeg -framerate 30 -i frames/%05d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow -movflags +faststart out.mp4
```

- Use even dimensions.
- Use `yuv420p` for broad playback.
- Check the result with `ffprobe`.

**GIF for articles and loops:**

- Build a palette with `palettegen` and apply it with `paletteuse`.
- GIF delays are whole hundredths of a second, and browsers raise delays under 2 hundredths to about 10. So 50, 25 and 20 fps time exactly, and 30 fps does not.
- `motion_timing.py gif` spreads the remainder across frames so the loop stays on the beat.
- Respect each platform's size, length, frame-rate and aspect limits.

**Example: posting to X** (limits as published in 2026; check the current help and API docs before the final export):

| Format | Limits |
|---|---|
| MP4 | Up to 140 s and 512 MB on a standard account (longer on paid tiers); aspect 1:3 to 3:1; up to 60 fps; recommended 1280×720, 720×1280 or 720×720 |
| GIF | Up to 15 MB on the web, 350 frames and 1280×1080; width × height × frames at most 300 million |

Useful canvases are 1080×1080, 1920×1080 and 1080×1920. Check a GIF before export with `motion_timing.py gif` and the pixel budget (width × height × frames).

## 7. Tools by role

These tools are free for individuals and small teams. Read each license, because "free" is not always "open source".

| Role | Tool | License and caution |
|---|---|---|
| UI motion, kinetic type, timelines | GSAP | Free under its own no-charge license (since April 2025), not an open-source license. The terms forbid use in no-code visual animation builders that compete with its owner. Read the current text before shipping a builder tool |
| 3D in the browser | Three.js | MIT |
| Video composed in React | Remotion | Source-available: free for individuals and very small companies; larger companies need a company license (see [remotion-video.md](remotion-video.md)) |
| Plain HTML rendered to video | HyperFrames (headless Chrome and FFmpeg, with a CLI) | Apache-2.0. Check that every animation is seekable |
| 3D models, rigs, renders | Blender | GPL for the program; your renders and files are yours |
| Agent control of a Blender scene | The community Blender MCP server, which creates and edits objects and materials, runs Python and captures the viewport | Check its license. It runs Python inside Blender, which is code execution. Review it, keep it local and never open untrusted `.blend` files with auto-run on. See [../../agent-safety/GUIDE.md](../../agent-safety/GUIDE.md) |
| Agent sees its own render | Chrome DevTools MCP, or Playwright | Apache-2.0. Use it for screenshots, console errors and performance traces of the page |
| Encode, inspect, deliver | FFmpeg | LGPL or GPL depending on the build. Encoder licensing matters only if you redistribute FFmpeg itself |
| Voice-over | An open text-to-speech model such as Chatterbox | MIT, and its outputs carry an imperceptible watermark. Clone a voice only with the speaker's documented consent |
| Captions | faster-whisper | MIT. Proofread names and terms; captions are part of accessibility |
| Generated images or video | ComfyUI | GPL-3.0. Custom nodes are third-party code, so vet them like any dependency. Follow [generation-prompting.md](generation-prompting.md) |
| Reference clips and audio | yt-dlp | Unlicense. Download only what you have the right to use, under the site's terms. References stay private and never appear in the output (see [reference-look-measurement.md](reference-look-measurement.md)) |
| Design critique of frames | ProductCraft's own taste pass and quality gate; an external design-audit plugin only after vetting it ([../../agent-safety/references/vetting-extensions.md](../../agent-safety/references/vetting-extensions.md)) | See [../../ui-distiller/references/taste.md](../../ui-distiller/references/taste.md) and [../../ui-distiller/references/quality-gate.md](../../ui-distiller/references/quality-gate.md) |

Ask before installing any of these, and pin versions in the project.

## 8. Common failures and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Looks generic or machine-made | Defaults and decoration | Add exactly what appeared to BANNED; give the shot one hero; re-render |
| Robotic motion | Linear easing, or equal durations everywhere | Replace with the easing or spring from section 3; vary durations by role |
| An action lands early or late | Timing written in seconds by eye | Name the frame and shift by whole frames; snap to the beat grid |
| A jump at the loop seam | Frame N was rendered, or a cycle does not divide N | Render frames 0 to N-1; use whole cycles (`motion_timing.py loop`) |
| Text is hard to read | Moving background, or a short hold | Measure contrast on the hold frames; lengthen the hold; add a scrim |
| Two renders differ | Wall-clock time, unseeded randomness or timers | Run `motion_contract_check.py`; hash the same frame twice |
| A late font swap | Fonts not loaded before frame 0 | Wait for `document.fonts.ready` and a ready flag |
| Sound out of sync | Timing set in an editor timeline | Measure the decoded audio against frame numbers; land each hit one frame after its picture |
| GIF loop drifts off the beat | 30 fps cannot be timed in hundredths | Use 25 or 50 fps, or the spread delays from `motion_timing.py gif` |

## Done when

- [ ] The brief has every line filled with numbers, and BANNED reflects what the reviews found.
- [ ] `motion_contract_check.py` is clean, or each remaining finding is explained. The same frame rendered twice has the same hash.
- [ ] A contact sheet and the key stills were viewed at full size. The notes name frames, and each note was fixed and re-checked.
- [ ] Holds meet the reading time; text contrast is at least 4.5:1 on the hold frames; there are no more than three flashes per second; captions exist for any speech.
- [ ] The loop seam is invisible (frames 0 to N-1, whole cycles), when the piece loops.
- [ ] Each hit lands one frame after its picture, and loudness and true peak are measured for the target platform.
- [ ] `ffprobe` confirms the size, frame rate, frame count, duration, codec and pixel format. GIF delays add up to the intended loop length.
- [ ] Credits list every font, model, voice, sound and tool whose license needs it ([../GUIDE.md](../GUIDE.md), "Credits and provenance").
