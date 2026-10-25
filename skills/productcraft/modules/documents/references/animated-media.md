# Animated GIFs and short clips

Read this to make, convert or shrink an animated GIF or a short looping clip: a product demo for a README or a release note, a reaction or custom emoji for a chat app, an animation drawn in code, or a screen recording cut down to a few seconds. Examples use Pillow and ffmpeg. Tested with Pillow 12.3 and ffmpeg 6.1.

Contents: pick the format · plan the clip · draw frames with Pillow · save a GIF · from video or screen recordings with ffmpeg · make it smaller · check it · accessibility · privacy and untrusted media · done when.

## Pick the format

| Where it will be shown | Use | Why |
|---|---|---|
| A web page or docs site you control | MP4 (H.264) in `<video autoplay muted loop playsinline poster="still.png">`, optionally a WebM source first | Usually several times smaller than the same GIF, full color, and the viewer can pause it |
| A README on a code host, email, a chat message, a custom emoji, anywhere that strips video | GIF | Plays almost everywhere without controls or plugins |
| Places that support them (check first) | Animated WebP or APNG | Full color and alpha; support in chat apps and email clients is patchy |

Know the GIF format's limits before promising quality:
- **256 colors per frame,** from a palette. Photos, gradients and video fades band or speckle.
- **On or off transparency only.** Anti-aliased edges against a transparent background leave a light or dark fringe.
- **Frame delays in hundredths of a second.** Choose a rate whose delay is a whole number of hundredths: 10, 20, 25 or 50 fps (100, 50, 40, 20 ms). Pillow truncates other values (83 ms is stored as 80 ms), and most browsers slow delays under 20 ms to about 100 ms, so 50 fps is the ceiling. ffmpeg alternates delays (for example 60 and 70 ms at 15 fps) to keep the total time right.
- **The loop count lives in an extension block.** Without it, most viewers play the animation once and stop.

Platform limits change, so check the target's current help page and say which limit you aimed for. In general terms: chat apps show custom emoji at about 20 to 32 px from a small square upload (often 128 px) and cap emoji files at tens to a few hundred kilobytes; message GIFs are displayed a few hundred pixels wide, and files over a few megabytes may be rejected, re-encoded or shown as a still or a plain attachment.

## Plan the clip

Settle these before drawing or recording:
- **Length:** 1 to 3 seconds for an emoji or reaction, 4 to 15 seconds for a demo. Anything longer belongs in a video with controls.
- **Frame rate:** 10 to 20 fps for drawn motion and emoji; 15 to 25 fps for screen recordings with scrolling or a moving cursor.
- **Size:** render at the size it will be displayed (twice that for sharp high-density screens, if the file budget allows). H.264 needs even width and height.
- **Content:** one idea per clip. For an emoji, one bold shape that reads at 24 px: thick strokes, strong contrast, no small text. For a demo, the real product at a readable zoom, one task from start to result.
- **Loop seam:** the last frame should lead into the first. For periodic motion use `t = i / n` (never reaching 1), so frame *n* does not duplicate frame 0 and cause a stutter.

## Draw frames with Pillow

`ImageDraw` does not anti-alias. Draw at several times the final size and shrink with a good filter. Use shapes, not emoji glyphs: emoji fonts differ between systems and often are not installed. For text, load a font file you are allowed to ship (`ImageFont.truetype("fonts/YourFont-Bold.ttf", 28)`).

```python
from math import cos, pi
from PIL import Image, ImageDraw

W = H = 128            # output size in pixels
SS = 4                 # supersampling factor
FPS, SECONDS = 20, 2   # 20 fps = 5 hundredths per frame, which GIF stores exactly
N = FPS * SECONDS

def ease_in_out(t: float) -> float:
    """0..1 -> 0..1 with a gentle start and stop."""
    return (1 - cos(pi * t)) / 2

frames = []
for i in range(N):
    t = i / N                       # stops short of 1.0, so the loop has no repeated frame
    up_down = 1 - abs(2 * t - 1)    # 0 -> 1 -> 0 across the loop
    y = 28 + ease_in_out(up_down) * 72
    big = Image.new("RGB", (W * SS, H * SS), "#f4f1ea")
    draw = ImageDraw.Draw(big)
    r = 16
    draw.ellipse([(W / 2 - r) * SS, (y - r) * SS, (W / 2 + r) * SS, (y + r) * SS], fill="#1f5fbf")
    frames.append(big.resize((W, H), Image.Resampling.LANCZOS))
```

Motion that reads well: ease in and out instead of moving at constant speed, a short hold at the end of a gesture, and small anticipation before a big move. Keep the background flat; texture and gradients cost colors and bytes in every frame.

## Save a GIF

Build one palette for the whole animation, so colors do not shift from frame to frame, and turn dithering off for flat artwork:

```python
sample = frames[:: max(1, len(frames) // 8)]          # a few frames are enough to pick colors
strip = Image.new("RGB", (W, H * len(sample)))
for k, f in enumerate(sample):
    strip.paste(f, (0, H * k))
palette = strip.quantize(colors=32, method=Image.Quantize.MEDIANCUT)
indexed = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]

indexed[0].save(
    "bounce.gif", save_all=True, append_images=indexed[1:],
    duration=1000 // FPS,   # milliseconds per frame; a list sets each frame separately
    loop=0,                 # 0 repeats forever; omit it to play once
    optimize=True,
)
```

Pillow merges identical consecutive frames into one longer frame and stores only the changed rectangle of each later frame, so holds and static regions cost little. For transparency, composite onto a matte color close to the background it will be shown on, quantize with the shared palette, and pass that color's palette index as `transparency=` together with `disposal=2`; otherwise moving shapes leave trails. A solid background is simpler: pick a color that sits well on both light and dark themes, or make one version per theme.

The same frames as video, for the web: save them as numbered PNGs (`f000.png`, `f001.png`, ...) and run `ffmpeg -framerate 20 -i frames/f%03d.png -c:v libx264 -pix_fmt yuv420p -crf 23 -movflags +faststart -an clip.mp4`. In testing, the 25 KB example GIF became a 4 KB MP4 and a 3 KB WebM with the commands below.

## From video or screen recordings with ffmpeg

The default GIF encoder uses a generic palette. Generate one from the clip itself, then apply it. Trim with `-ss` (start) and `-t` (length), and use the same frame rate and scale in both passes:

```bash
F="fps=15,scale=480:-1:flags=lanczos"
ffmpeg -v error -ss 2 -t 6 -i demo.mp4 -vf "$F,palettegen=max_colors=128:stats_mode=diff" -y palette.png
ffmpeg -v error -ss 2 -t 6 -i demo.mp4 -i palette.png \
  -lavfi "$F[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" -loop 0 -y demo.gif

# The same in one command
ffmpeg -v error -ss 2 -t 6 -i demo.mp4 -filter_complex \
  "$F,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  -loop 0 -y demo.gif
```

- `stats_mode=diff` weights the palette toward what moves; `diff_mode=rectangle` re-encodes only the changed area of each frame.
- `dither=bayer` (ordered) compresses far better than error-diffusion dithering, whose noise changes every frame. Use `dither=none` for flat interface recordings.
- `-loop 0` repeats forever; `-loop -1` plays once.
- GIF to web video: `ffmpeg -i in.gif -c:v libx264 -pix_fmt yuv420p -crf 23 -movflags +faststart -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -an out.mp4`, and for WebM `-c:v libvpx-vp9 -b:v 0 -crf 35`.
- For a demo recorded in a test browser, Playwright can record the session (`recordVideo` on the browser context); see `../../builder-tools/references/playwright-web-testing.md`. Record at the size you will publish and use test accounts and data.

## Make it smaller

Change one thing at a time and check the size after each (`ls -l` or `os.path.getsize`), in roughly this order of effect:

1. **Fewer pixels.** File size grows with area: halving the width cuts it to roughly a quarter.
2. **Fewer frames.** Lower the frame rate, trim the start and end, shorten holds.
3. **Fewer colors.** Try 128, 64, then 32; stop where banding shows.
4. **Calmer dithering.** None or ordered, not error diffusion.
5. **Less change per frame.** Static backgrounds, no camera drift, no animated gradients, no blinking cursor in a recording.
6. **A lossy GIF optimizer** if one is already installed; ask before installing one.
7. **Switch to video** where the destination allows it.

## Check it

Read the result back instead of trusting the script. This Pillow snippet reports size, dimensions, frame count, timing and loop setting, and estimates the flash rate per region of the frame:

```python
import os
from PIL import Image, ImageSequence

LINEAR = [round(255 * ((c / 255) / 12.92 if c <= 10 else (((c / 255) + 0.055) / 1.055) ** 2.4)) for c in range(256)] * 3

def cell_luminance(frame, grid=4):
    """Mean relative luminance (0..1) of each cell of a grid x grid split."""
    lum = frame.convert("RGB").point(LINEAR).convert("L", (0.2126, 0.7152, 0.0722, 0))
    return [v / 255 for v in lum.resize((grid, grid), Image.Resampling.BOX).tobytes()]

def swing_times(values, times, step=0.10, dark=0.80):
    """Times of luminance swings of `step` or more whose darker end is below `dark`."""
    out, trend, extreme = [], 0, values[0]
    for v, t in zip(values[1:], times[1:]):
        if trend and (v - extreme) * trend > 0:
            extreme = v                                  # same swing, still growing
        elif abs(v - extreme) >= step:
            if min(v, extreme) < dark:
                out.append(t)
            trend, extreme = (1 if v > extreme else -1), v
    return out

def check(path, grid=4):
    im = Image.open(path)
    cells, starts, total = [], [], 0
    for f in ImageSequence.Iterator(im):
        ms = f.info.get("duration") or 0
        cells.append(cell_luminance(f, grid))
        starts.append(total)
        total += ms if ms >= 20 else 100                 # browsers slow tiny delays
    loops = 2 if "loop" in im.info else 1                # a looping file flashes across the seam too
    times = [s + k * total for k in range(loops) for s in starts]
    worst = 0
    for c in range(grid * grid):
        swings = swing_times([fr[c] for _ in range(loops) for fr in cells], times)
        worst = max([worst] + [sum(1 for s in swings[i:] if s - t0 < 1000) for i, t0 in enumerate(swings)])
    return {"bytes": os.path.getsize(path), "size": im.size, "frames": len(cells),
            "seconds": total / 1000, "loop": im.info.get("loop", "plays once"),
            "max_flashes_in_1s": worst / 2, "flash_ok": worst <= 6}

print(check("bounce.gif"))
```

The flash estimate is a screening heuristic, not a certified photosensitivity analysis. It can miss flashing smaller than one grid cell and can flag fast-moving objects. Treat `flash_ok: False` as a defect to fix, and anything near the limit as a reason to slow down. It does not check saturated red flashes; look for those by eye.

Then look at it: play it at its real display size in the target (a browser, the chat app's preview, the README preview), and check a contact sheet of every few frames (`convert-and-render.md` has one) for stray frames, cut-off text and personal data. For video, `ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,pix_fmt -of default=nw=1 clip.mp4` confirms the codec, size and rate.

## Accessibility

- **Flashing:** no more than three flashes in any one-second period, and no saturated red flashing (`MOT-21`). WCAG 2.3.1 (Level A) allows small flashing areas; generated media can be shown enlarged, so aim for the stricter "three flashes" rule of 2.3.2, which has no size exception.
- **Motion that keeps going:** on a web page, anything that moves for more than five seconds next to other content needs a way to pause it (WCAG 2.2.2, `MOT-19`). A forever-looping GIF has none. Use video with controls, a click-to-play poster, or a finite loop count that ends within five seconds; viewers disagree on whether the count includes the first play, so time it in the target browser.
- **Reduced motion:** offer a still frame to people who ask for less motion: `<picture><source srcset="demo-still.png" media="(prefers-reduced-motion: reduce)"><img src="demo.gif" alt="..."></picture>`.
- **Text alternative:** write what the animation shows and why it matters, not "animated GIF": `alt="Dragging a card from To do to Done moves it and updates the column counts"`. A demo with steps also gets the steps as text nearby. Decorative loops get `alt=""`. In chat apps, fill in the description or alt text field where there is one, and give custom emoji a name that says what they mean.
- **Text inside frames** cannot be searched, translated, resized or read by screen readers. Keep essential information outside the animation.

## Privacy and untrusted media

- Screen recordings capture whatever was on screen: names, email addresses, notification banners, tokens in URLs, other tabs. Record with test data, crop to the app, and check every frame before publishing. Remove container metadata from video with `-map_metadata -1`.
- Media uploaded by users is untrusted input. Decode it with size, duration and frame-count limits (`-t`, `-frames:v`; Pillow's `Image.MAX_IMAGE_PIXELS` warns about decompression bombs), in the app's isolated worker, following the file upload control in `../../launchguard/references/security-baseline.md`. Keep ffmpeg and Pillow updated.

## Done when

- The file meets the size, dimension and duration targets you stated for its destination, and you named the platform limit you aimed for.
- Read-back shows the intended frame count, timing and loop setting; the flash check passes.
- You watched it at display size and inspected the frames for glitches and personal data.
- Alt text or a description is written, and a still or pausable version exists where the page needs one.
