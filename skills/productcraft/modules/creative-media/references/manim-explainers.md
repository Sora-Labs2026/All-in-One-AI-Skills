# Math and technical explainers with Manim

Read this to make an explainer animation with Manim: an equation that transforms step by step, a function and its tangent, a geometric construction, an algorithm's state changing, a graph or system diagram built up piece by piece. Examples target Manim Community Edition 0.19 (2025), the actively maintained, MIT-licensed fork. The original author's version (ManimGL) has a different API; many snippets online mix the two, so check which one a snippet was written for before copying it.

Contents: when Manim fits · setup · plan before code · a complete scene · rendering · idioms and pitfalls · style · narration and pacing · accessibility · checks · done when.

## When Manim fits

| Goal | Use |
|---|---|
| Equations rewriting themselves, plotted functions, geometry, vectors and matrices, algorithm states, precise diagrams that build up | Manim |
| Product UI, brand typography and layout, data from props, many variants, captions and compositing | Remotion (`remotion-video.md`) |
| A still diagram | Code-drawn SVG or a figure (`infographics.md`) |
| Cutting recorded footage around the animation | `video-editing.md` |

They combine well: render Manim scenes with a transparent background and composite them in Remotion or an editor.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install "manim==0.19.*"            # pin; the API still changes between minor versions
manim checkhealth                      # reports missing system pieces
```

- **System libraries:** Cairo and Pango (bundled in the wheels on macOS and Windows; on Linux install the distribution's development packages first, as the install guide lists).
- **LaTeX** only for `Tex` and `MathTex`: a TeX distribution (TeX Live or MiKTeX) with the packages the install guide names (including `standalone`, `preview` and `dvisvgm`). `Text` and `MarkupText` render through Pango and need no LaTeX.
- **Video encoding:** recent releases write video through PyAV, so a separate FFmpeg binary is no longer required for rendering; keep FFmpeg on the path for post-processing anyway.
- A container image (`manimcommunity/manim`) avoids installing LaTeX locally; pin its tag.

## Plan before code

1. **Thesis in one sentence:** "The derivative is the slope of the tangent line, and for x²/2 that slope equals x."
2. **Three to six scenes, each proving one thing.** Write a storyboard table before any code:

| Scene | Claim | On screen | What moves | Narration | Seconds |
|---|---|---|---|---|---|
| 1 | We want the steepness at a point | Axes, the curve | Curve draws in | "How steep is this curve at a single point?" | 6 |
| 2 | A secant approximates it | Two points and a line | Second point slides toward the first | "Join two points and shrink the gap." | 10 |
| 3 | The limit is the tangent | Tangent line, slope readout | Point moves along the curve; readout follows | "The slope at x is exactly x." | 12 |

3. **Narration drives timing.** Record or synthesize the voice-over first (about 130-160 words per minute), then set each animation's `run_time` to its line.
4. Render the smallest working version first, then refine typography, color and pacing.

## A complete scene

```python
# tangent.py  -  render: manim -pql tangent.py TangentSlope
from manim import *

class TangentSlope(Scene):
    def construct(self):
        axes = Axes(x_range=[-1, 4, 1], y_range=[-1, 9, 2], x_length=7, y_length=5,
                    axis_config={"include_numbers": True}).to_edge(LEFT)
        f = lambda x: 0.5 * x ** 2
        curve = axes.plot(f, x_range=[-1, 4], color=BLUE)
        label = axes.get_graph_label(curve, MathTex(r"f(x)=\tfrac12 x^2"), x_val=3.4, direction=UL)
        x = ValueTracker(0.5)

        def tangent():
            x0 = x.get_value()
            line = axes.plot(lambda t: f(x0) + x0 * (t - x0),            # slope f'(x0) = x0
                             x_range=[max(-1, x0 - 1.2), min(4, x0 + 1.2)], color=YELLOW)
            return VGroup(line, Dot(axes.c2p(x0, f(x0)), color=YELLOW))

        tan = always_redraw(tangent)
        value = DecimalNumber(x.get_value(), num_decimal_places=1)
        value.add_updater(lambda m: m.set_value(x.get_value()))
        readout = VGroup(MathTex(r"\text{slope}="), value).arrange(RIGHT).to_corner(UR)

        self.play(Create(axes), run_time=1.5)
        self.play(Create(curve), Write(label), run_time=2)
        self.play(FadeIn(tan), FadeIn(readout))
        self.play(x.animate.set_value(3), run_time=5, rate_func=smooth)
        self.wait(2)                                   # hold the final state long enough to read
        value.clear_updaters()
```

## Rendering

| Command | Use |
|---|---|
| `manim -pql file.py Scene` | 480p at 15 fps, opens the result: drafts |
| `manim -qm` / `-qh` / `-qk` | 720p30 / 1080p60 / 2160p60 for review and delivery |
| `manim -s file.py Scene` | Save only the last frame as PNG: posters, thumbnails, CI snapshots |
| `manim -n 3,5 file.py Scene` | Render only animations 3 to 5 while iterating |
| `manim --fps 30 -r 1920,1080 ...` | Exact frame rate and resolution |
| `manim -t ...` | Transparent background (a `.mov` with alpha) for compositing |
| `manim --format gif ...` | GIF output; see `../../documents/references/animated-media.md` for size limits |
| `self.next_section("tangent")` plus `--save_sections` | One file per section, to align with narration in an editor |

- Put project settings (frame rate, background color, media directory) in a `manim.cfg` next to the scenes so every render uses them.
- **Vertical video** (`-r 1080,1920`): after changing the resolution, check that `config.frame_width` and `config.frame_height` (scene units) have the same aspect ratio as the pixels, set them in `manim.cfg` if not, and design the vertical layout separately rather than squeezing the landscape one.
- Output lands in `media/videos/<file>/<quality>/`. Re-encode for the web if the destination needs H.264 with `yuv420p` (`video-editing.md`).

## Idioms and pitfalls

- **`Transform` versus `ReplacementTransform`.** `Transform(a, b)` morphs `a` into the shape of `b` and leaves `a` on screen; later animating `b` does nothing visible because `b` was never added. Use `ReplacementTransform` when the target should replace the source in the scene.
- **Equations:** split `MathTex` into parts (separate strings, or double braces `{{ }}`) and use `TransformMatchingTex` so matching symbols travel to their new place instead of everything morphing at once. Use `substrings_to_isolate` to color one symbol.
- **Rotation:** `mob.animate.rotate(PI)` interpolates point positions in a straight line, so a half turn collapses through the center. Use `Rotate(mob, angle=PI)` for real rotation.
- **Continuous dependencies:** drive them from a `ValueTracker` with updaters or `always_redraw`. Updaters run every frame and slow rendering; remove them (`clear_updaters`) when the dependency ends. Avoid rebuilding `MathTex` inside `always_redraw`, which compiles LaTeX every frame; use `DecimalNumber` or `Variable` for changing numbers.
- **Emphasis:** `Indicate`, `Circumscribe` and `Flash` draw the eye without moving the layout. Use one at a time.
- **Camera:** `MovingCameraScene` with `self.camera.frame.animate.scale(0.5).move_to(target)` zooms; `ThreeDScene` with `set_camera_orientation` for 3D. Keep camera moves slow and few.
- **Graphs and networks:** `Graph(vertices, edges, layout="spring", layout_config={"seed": 1})` gives the same layout on every render; unseeded layouts move between renders.
- **Randomness:** Manim Community does not seed random generators by default. Pass a `random_seed` to the scene or call `random.seed()` and `np.random.seed()` at the top of `construct`, so re-renders match.
- **Caching:** Manim caches partial movies by a hash of each animation. If output depends on outside state the hash cannot see (files read during construction), render with `--disable_caching`; clear old partials with `--flush_cache`.
- **Code listings:** the `Code` mobject's parameters changed in 0.19; check its current signature rather than copying older examples.
- **OpenGL renderer** (`--renderer=opengl`) previews faster but still lacks some features of the default renderer; deliver with the default.

## Style

- Define a palette module (`palette.py`) from the project's theme (`themes-and-brand-application.md`) instead of Manim's saturated default colors; set `config.background_color` once.
- Fonts: `Text("…", font="Source Sans 3")` needs the font installed; load project fonts for the render with `with register_font("fonts/SourceSans3-Regular.ttf"):` and record their licenses in `credits.md`.
- One stroke width scale, one text size scale; labels at least about 1/20 of the frame height so they read on a phone.
- Keep color semantic: one color per concept (the function, its derivative, the error) used consistently across scenes, plus labels so color is never the only cue.

## Narration and pacing

- One idea per animation; let each finish before the next starts unless they are one thought.
- `run_time` follows the narration line; `self.wait()` after a reveal gives time to read (roughly the time it takes to read the new text twice).
- Render sections (`--save_sections`) and align them to the narration in an editor, or measure each narration clip's duration first and set `run_time` from it.
- Synthetic narration follows the consent and labeling rules in `hosted-media-generation.md`.

## Accessibility

- Captions for all narration (sidecar file and, for social video, burned in; `remotion-video.md` has caption timing rules).
- Contrast of text and key strokes against the background (`COL-01`); never color alone to tell two curves apart.
- No flashing above three times per second (`MOT-21`); `Flash` and rapid `Indicate` repeats count.
- Describe in narration anything that is only shown (audio description, WCAG 1.2.5), and publish a transcript with the equations written out.

## Checks

1. Render each scene with `-s` and look at the last frame at full size: overlaps, clipped labels, legibility at phone width.
2. Watch every scene at delivery quality, start to end, with the narration.
3. Verify the mathematics independently of the animation: every equation on screen is correct, every plotted function matches its label, axes are labeled with units where they have them.
4. `ffprobe` the deliverable for duration, size, frame rate and codec; captions load in a player.
5. In CI, render key scenes at `-ql -s` and compare the PNGs against approved ones; Manim's own test utilities in `manim.utils.testing` show a frame-comparison approach.

## Done when

- The thesis and storyboard exist, and each scene proves its one claim.
- Scenes render from a pinned Manim version with seeded randomness; two renders match.
- The mathematics was checked independently; labels, contrast and captions pass; nothing flashes.
- The delivered file matches the agreed size, frame rate and codec, and its fonts and any borrowed material are credited.
