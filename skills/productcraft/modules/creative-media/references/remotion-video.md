# Programmatic video with Remotion

Read this to make video from code: product demos and release videos, explainers with animated diagrams, data-driven clips (one video per customer, city or metric), title sequences, captioned social cuts, or templates that others fill with props. Remotion renders React components frame by frame in headless Chromium and encodes with FFmpeg. Examples target Remotion 4.x (2024-2026); several APIs were renamed during 4.x, so read the docs for the installed version.

Contents: when Remotion fits · license · setup · the frame model · timing and scenes · media, fonts and data · captions and audio · rendering · cloud rendering · performance · checks · done when.

## When Remotion fits

| Goal | Use |
|---|---|
| Video whose content comes from data or props; many variants of one template; motion graphics built from components and design tokens | Remotion |
| Cutting, trimming, concatenating or transcoding existing footage | FFmpeg directly, or a video editor |
| A short looping GIF or a reaction clip | `../../documents/references/animated-media.md` |
| A recorded walkthrough of a web app | Playwright video recording (`../../builder-tools/references/playwright-web-testing.md`), optionally placed inside a Remotion composition |
| Photoreal footage | A camera, stock footage, or a generation model (`generation-prompting.md`) |

## License

Remotion is source-available under its own license, not an open-source license. As of 2025-2026 it is free for individuals and very small companies, and larger companies need a paid company license. Check the current terms at remotion.dev/license and tell the user before building a commercial pipeline on it.

## Setup

```bash
npx create-video@latest my-video     # scaffolds a project; pick a blank or a template
cd my-video && npm run dev            # Remotion Studio: timeline, props editor, preview
npx remotion versions                 # every remotion and @remotion/* package must be the same version
```

- All `remotion` and `@remotion/*` packages move together; mismatched versions are the most common source of odd errors. Upgrade them in one step (`npx remotion upgrade`) and commit the lockfile.
- Use a current Node.js LTS. Rendering downloads a headless Chromium build on first run; on CI, cache it.
- Prop schemas use zod; install the zod version the Remotion docs list for your release.

## The frame model

Every frame is rendered independently, possibly in parallel tabs and out of order. Everything on screen must be a pure function of the frame number and the props.

```tsx
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const Title: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();                 // 0-based, relative to the enclosing <Sequence>
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });                  // 0 -> 1, no bounce
  const fadeOut = interpolate(frame, [2.5 * fps, 3 * fps], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",                           // never run past 0..1
  });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", background: "var(--bg)" }}>
      <h1 style={{ opacity: enter * fadeOut, transform: `translateY(${(1 - enter) * 40}px)` }}>{text}</h1>
    </AbsoluteFill>
  );
};
```

Rules that follow from the model:
- **No CSS transitions, CSS animations, `setTimeout`, `requestAnimationFrame` or wall-clock time** for motion. They are not tied to the frame and flicker or freeze in renders.
- **No state accumulated across frames** (`useState` counters, effects that advance a simulation). Compute from `frame` instead; for simulations, precompute all states from the props once and index by frame.
- **No `Math.random()`.** Use Remotion's `random("seed-string")`, which returns the same value in every tab and every render.
- **Clamp every `interpolate`** unless you want values beyond the output range.
- **Express time in seconds times `fps`**, never as fixed frame counts, so a change of frame rate keeps the timing.

## Timing and scenes

- Lay scenes out with `<Sequence from={...} durationInFrames={...}>` or `<Series>`; inside a sequence, `useCurrentFrame()` starts at 0. Transitions between scenes come from `@remotion/transitions` (`<TransitionSeries>` with fade, slide or wipe presentations).
- Keep the timeline as data: an array of scenes with durations in seconds, from which the composition builds its sequences. Then duration can be computed in `calculateMetadata` and unit-tested.
- Pace narration at roughly 130-160 words per minute; let the voice-over drive scene lengths, not the other way round. Hold each text card long enough to read twice.
- Motion character comes from the theme (`themes-and-brand-application.md`) and the motion rules in `../../../references/ui-rules/motion.md`: ease out on entry, short durations for small elements, one moving focus at a time.

## Media, fonts and data

- Put assets in `public/` and reference them with `staticFile("logo.svg")`. Remote URLs work but slow every render and can change; download and keep them with their licenses.
- Images with Remotion's `<Img>`, which delays the frame until the image has loaded. Video inside a composition with the component the docs recommend for rendering in your version (long the `<OffthreadVideo>` component, which extracts exact frames with FFmpeg); media component names and trimming props changed during 4.x.
- **Convert variable-frame-rate inputs** (phone and screen recordings) to constant frame rate first, or audio and video drift: `ffmpeg -i in.mov -vf fps=30 -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac in-cfr.mp4`.
- **Fonts:** load them through Remotion's font packages (`@remotion/google-fonts/<Family>` or `@remotion/fonts` for local files) so rendering waits for them; an unloaded font renders a fallback face in the first frames.
- **Async data:** fetch in `calculateMetadata` (which can also set duration, size and props) rather than inside components. Where a component must wait, wrap the wait in `delayRender()` / `continueRender()`; the default timeout is 30 seconds, and a forgotten `continueRender` fails the render with a timeout.
- **Props:** declare a zod schema on the `<Composition>` so props are typed, editable in the Studio, and validated when passed with `--props=props.json`.

## Captions and audio

- **Captions are required for speech** (WCAG 1.2.2) and expected on social video, which usually autoplays muted. Produce word timings by transcribing locally (Remotion's Whisper.cpp helper package, or whisper.cpp directly), correct names and terms by hand, then render captions in the composition and also export an `.srt` or `.vtt` file for players that support sidecar captions.
- Caption style: at most two lines, about 42 characters per line, on screen long enough to read (roughly 15-20 characters per second) and never under about one second; high-contrast text on a solid or translucent box; placed clear of on-screen UI and faces.
- Information shown only visually (a number on a chart, text on a screen recording) is also spoken or described for audio-only listeners where it matters (audio description, WCAG 1.2.5).
- **Audio:** fade music in and out with a volume callback (`volume={(f) => interpolate(f, [0, fps], [0, 0.6], { extrapolateRight: "clamp" })}`), duck it under speech, and use only music you have rights to for this use: synchronization rights in video, and platform audio libraries only on that platform.
- **Loudness:** measure the final mix (`ffmpeg -i out.mp4 -af ebur128=peak=true -f null -`). Common targets: about -14 LUFS integrated for streaming and social platforms, -16 LUFS for podcasts, -23 LUFS for EBU R128 broadcast, with true peaks below -1 dBTP. Check the destination's current specification.

## Rendering

```bash
npx remotion still Main out/check-030.png --frame=30             # one frame, seconds to render
npx remotion render Main out/test.mp4 --frames=0-89              # the first three seconds at 30 fps
npx remotion render Main out/main.mp4 --codec=h264 --crf=18 --props=props/acme.json
npx remotion render Main out/main.mov --codec=prores --prores-profile=4444 \
  --pixel-format=yuva444p10le --image-format=png                 # with alpha, for editors
```

- H.264 with `yuv420p` (the default) plays everywhere; width and height must be even. ProRes or PNG sequences are for handing to an editor, not for publishing.
- Render many variants from a script that loops over prop files and names outputs after them; render one variant fully and review it before the batch.
- Render on the user's machine or CI by default. Long renders are CPU-bound; `--concurrency` trades speed against memory.

## Cloud rendering

Remotion can render on serverless cloud functions (`@remotion/lambda` on AWS, a Cloud Run variant on Google Cloud). Deploying them creates cloud resources, IAM roles and storage that cost money. Treat it as infrastructure: write the plan and the commands, estimate cost per minute of video from the provider's pricing, and run nothing without the user's explicit go-ahead, following `../../cloud-infrastructure/GUIDE.md`. Keep credentials out of the chat (`../../agent-safety/GUIDE.md`).

## Performance

- Blur, large shadows, `backdrop-filter`, big SVG filters and full-frame gradients are expensive in headless Chromium; prefer pre-rendered images for heavy effects.
- Large images: downscale to the output size before placing them. Large videos: trim to the used range with FFmpeg first.
- WebGL scenes (for example with `@remotion/three`) may need a GPU-backed `--gl` setting; test one frame with each option the docs list for your platform.
- Profile with a short frame range before rendering the whole video.

## Checks

1. `npx remotion still` at the first frame, last frame and each scene's midpoint; look at every one for fallback fonts, missing images, overflow and contrast.
2. Watch the full render at real size, with sound, start to finish.
3. Read back the file instead of trusting the renderer:

```bash
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,pix_fmt,channels,sample_rate -of default=nw=1 out/main.mp4
```

4. Captions: timing against speech, spelling of names, line length, contrast; the sidecar file loads in a player.
5. Loudness and peaks measured; no clipping.
6. Flashing: no more than three flashes per second (`MOT-21`); the check in `../../documents/references/animated-media.md` works on frames exported from the video.
7. Credits and licenses listed for footage, music, fonts, icons and any generated media (labeled as generated where the platform or law requires).
8. Pure helpers (timeline builders, data-to-scene mapping) have unit tests; a still render of a key frame per template guards against regressions.

## Done when

- The video has the agreed duration, size, frame rate and codec, confirmed with `ffprobe`.
- Every frame is a pure function of frame and props: no CSS animations, timers or unseeded randomness; two renders of the same props match.
- Speech is captioned (burned in and as a sidecar file where useful); loudness meets the destination's target.
- The full render was watched, and rights for every asset, including music, are recorded.
- Remotion's license was checked for the user's organization, and no cloud resources were created without approval.
