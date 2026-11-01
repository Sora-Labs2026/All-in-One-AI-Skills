# Editing recorded footage

Read this to turn recorded footage into a finished video: a talk, interview, tutorial, screen recording, event or product walkthrough cut down to its strongest parts; short versions for social feeds; captions, music and levels; export for each destination; and a timeline an editor can open. Programmatic overlays and motion graphics are in `remotion-video.md`; GIFs and short loops in `../../documents/references/animated-media.md`; matching a reference look in `reference-look-measurement.md`. Commands target FFmpeg 6 and 7 (2023-2025).

Contents: principles · ingest · the paper edit · cutting accurately · captions · audio · color · reframing · export · handing off a timeline · rights · checks · done when.

## Principles

- **Originals are read-only.** Work on copies and proxies; never re-encode or overwrite the camera files.
- **Edit decisions are data.** Keep the cut list (in and out points, order, notes) in a CSV, EDL or timeline file, so the render can be rebuilt and reviewed.
- **Structure first, polish last.** Story and order, then trims, then audio, then color, then captions, then export.
- **The person decides the story.** An agent can transcribe, find pauses and propose selects with reasons; the owner of the footage approves what stays.

## Ingest

```
project/
  00_source/      camera and screen files, read-only (chmod a-w)
  01_proxies/     small edit-friendly copies
  02_audio/       extracted and cleaned audio
  03_edit/        cut list, EDL or timeline, project checkpoints
  04_renders/     exports, named with version and date
  credits.md      footage, music, fonts, generated media, releases
```

- **Probe everything first:**

```bash
for f in 00_source/*; do
  ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,pix_fmt,color_transfer,sample_rate,channels:format=duration -of compact "$f"
done
```

  Look for variable frame rate (`avg_frame_rate` differs from `r_frame_rate`; phones and screen recorders), HDR transfer (`arib-std-b67` is HLG, `smpte2084` is PQ), rotation metadata, mixed frame rates and odd audio layouts.
- **Normalize variable frame rate** to a constant rate before editing, or audio drifts (command in `remotion-video.md`, "Media, fonts and data").
- **Proxies** for heavy sources (4K, 10-bit HEVC): `ffmpeg -i in.mov -vf scale=-2:540 -c:v libx264 -crf 23 -preset veryfast -g 12 -c:a aac 01_proxies/in.mp4`; the short keyframe interval makes scrubbing fast. Cut with proxies, render from sources with the same timecodes.
- **Audio for transcription:** `ffmpeg -i in.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le 02_audio/in.wav`.

## The paper edit

1. Transcribe locally with word timestamps (a Whisper-family model, `media-indexing-and-search.md`) and correct names and terms.
2. Mark selects in the transcript; write them to `03_edit/cuts.csv`:

```csv
clip,source,in,out,note
01,00_source/talk.mp4,00:02:14.200,00:02:41.900,opening claim
02,00_source/talk.mp4,00:07:03.000,00:07:58.480,demo of the importer
```

3. **Find pauses** to tighten: `ffmpeg -i 02_audio/talk.wav -af silencedetect=noise=-35dB:d=0.6 -f null - 2>&1 | grep silence_`. The noise floor and minimum length depend on the room; listen before cutting, and keep breaths and short pauses so speech still sounds human.
4. **Find shot changes** in multi-camera or edited material: `ffmpeg -i in.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | grep pts_time`. The threshold depends on the material; check a few detected cuts by eye (`reference-look-measurement.md` describes a threshold sweep).

## Cutting accurately

- **Stream copy cuts only at keyframes.** `-c copy` with `-ss` starts the clip at the nearest earlier keyframe, so it may include extra frames or show a frozen picture until the next keyframe. Use it only for rough splits where exact frames do not matter.
- **Frame-accurate cuts re-encode.** With `-ss` before `-i`, seeking is fast and still frame-accurate when transcoding:

```bash
ffmpeg -ss 134.2 -i 00_source/talk.mp4 -t 27.7 -c:v libx264 -crf 18 -preset medium \
  -c:a aac -b:a 192k -af "afade=t=in:d=0.02,afade=t=out:st=27.68:d=0.02" 03_edit/01.mp4
```

  The 20 ms audio fades at each edge remove the clicks a hard audio cut makes.
- **Build commands from the CSV with a script** (argument lists, never shell strings built from file names), and log each command next to the output.
- **Joining:** the concat demuxer (`-f concat -safe 0 -i list.txt -c copy`) only works when every clip has identical codec, resolution, frame rate, time base and audio format, which clips encoded by the same command do. Otherwise use the `concat` filter and re-encode once.
- **Transitions:** hard cuts by default. For a dissolve, `xfade` (video) and `acrossfade` (audio) need matching size, frame rate and time base, and the `offset` is the first clip's duration minus the transition length.
- **J- and L-cuts** (sound leading or trailing the picture) are what make dialogue edits feel smooth; they are far easier in an editing application than in FFmpeg, which is a good reason to hand off a timeline (below).

## Captions

- **Sidecar first:** a WebVTT or SRT file is accessible, searchable and switchable; upload it wherever the platform accepts one. Embed it as a soft track in MP4 with `-c:s mov_text`.
- **Burn in** when the destination cannot show sidecars or the design requires it: `-vf "subtitles=captions.srt:force_style='FontName=Source Sans 3,FontSize=22,BorderStyle=3,Outline=1'"` (needs FFmpeg built with libass; escape colons and quotes in paths). Often deliver both.
- Timing, line length and reading-rate rules are in `remotion-video.md` ("Captions and audio"). Proofread names; check sync at the start, middle and end; keep captions clear of lower-thirds and of the areas feeds cover with their own interface.

## Audio

Order: clean, shape, balance, then normalize loudness last.

- **Clean gently:** a high-pass around 80 Hz on voice (`highpass=f=80`) removes rumble; noise reduction (`afftdn`, or `arnndn` with a model file) in small amounts, because heavy settings make voices watery.
- **Even out speakers and clips** before the final mix, so one quiet clip does not get boosted with its noise at the end.
- **Duck music under speech** with a sidechain compressor keyed by the voice:

```bash
ffmpeg -i voice.wav -i music.wav -filter_complex \
 "[0:a]asplit=2[v][key];[1:a][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];\
  [v][duck]amix=inputs=2:normalize=0[mix]" -map "[mix]" -c:a pcm_s24le mix.wav
```

  `amix` scales its inputs down unless told otherwise (`normalize=0` in FFmpeg 5 and later); set each level explicitly instead of relying on it.
- **Normalize loudness in two passes** so the result is accurate and not pumped: run `loudnorm=I=-14:TP=-1:LRA=11:print_format=json` once with `-f null -`, then run again passing the measured values (`measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`, `offset`) with `linear=true`. Targets per destination and the measuring command are in `remotion-video.md`.

## Color

- **Correct, then grade.** First make clips match each other (exposure, white balance, black level) against one hero shot; then apply one look to all of them. Measuring a target look and building a LUT: `reference-look-measurement.md`.
- A LUT expects a specific input: apply a camera's technical log-to-Rec.709 conversion first, then the creative LUT (`lut3d=file=look.cube:interp=tetrahedral`). Never apply a look to clips that are already graded.
- **Tag the output** so players do not guess: `-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv` for standard dynamic range.
- **HDR clips** from phones mixed into an SDR timeline look washed out or clipped. Convert them deliberately (`zscale` and `tonemap`, which need FFmpeg built with libzimg) or keep an HDR pipeline end to end.

## Reframing for other formats

- Common delivery frames: 16:9 at 1920×1080, 9:16 at 1080×1920, 1:1 at 1080×1080, 4:5 at 1080×1350. Platforms change their specifications; check the destination's current help page and say which you targeted.
- A center crop is only a start: `-vf "crop=ih*9/16:ih,scale=1080:1920,setsar=1"`. Speakers and on-screen text move, so reframe per shot (keyframed crop in an editor, or per-segment crop offsets in the cut list).
- Keep titles and captions inside the safe area the destination's interface leaves free. Prefer a designed frame or a blurred, darkened copy of the shot behind it over black bars when a wide shot must sit in a tall frame.

## Export

| Use | Settings |
|---|---|
| Upload master for platforms that re-encode | H.264 High profile, `yuv420p`, CRF 16-20, `-preset slow`, keyframe every 2 s (`-g` = 2 × fps), source frame rate kept constant, AAC-LC 48 kHz stereo at 192-320 kb/s, `-movflags +faststart`, even width and height, `setsar=1` |
| Web embed you host | As above at CRF 21-24, plus a VP9 or AV1 version if you serve several formats |
| Handoff to an editor or colorist | ProRes 422 HQ or DNxHR HQX in `.mov`, PCM audio |

```bash
ffmpeg -i assembled.mov -c:v libx264 -profile:v high -pix_fmt yuv420p -crf 18 -preset slow -g 60 \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:a aac -b:a 256k -ar 48000 \
  -movflags +faststart 04_renders/talk-v3-2026-03-02.mp4
```

Strip location and device metadata from phone footage before publishing (`-map_metadata -1`), but keep any content credentials the project must carry for generated inserts (`generation-prompting.md`, "Labels and provenance").

## Handing off a timeline

- Ship an editable timeline next to the flattened video: CMX 3600 EDL for simple cuts, FCPXML or OpenTimelineIO (OTIO) for richer timelines, referencing the individual clips rather than the render.
- **Validate it:** clip offsets equal the running sum of earlier durations (no gaps or overlaps), every referenced file exists, the total duration matches the render, and it opens and relinks on another machine.
- **Set the project frame rate before importing**: several editors fix a timeline's frame rate when it is created and silently conform anything else.
- **Checkpoints:** before an automated change to a live project (a script or an editor's API), save a versioned copy and confirm the file exists; save and confirm again afterwards. A script's in-memory result is not a saved project, and a rendered file is not an approved edit.

## Rights and privacy

- People who can be identified need a release for commercial use; minors need a guardian's. Blur faces, names and screens that should not appear.
- Screen recordings often show email addresses, customer records, tokens and notifications; step through them frame by frame before publishing.
- Music needs a synchronization license for this use; a platform's audio library is licensed only on that platform. Footage from other creators needs their license, whatever the clip's source.
- List everything in `credits.md`, including generated inserts and synthetic voices with their labels (`hosted-media-generation.md`).

## Checks

1. `ffprobe` the export: duration, size, frame rate, codec, pixel format, color tags, audio channels and sample rate.
2. Watch the whole video at 100% with headphones. Step through ±2 frames at every cut for flash frames and stray frames.
3. Audio and picture in sync at the start, middle and end (a clap, a plosive, a door).
4. Loudness and true peak measured on the final file; no clipping.
5. Captions load, are in sync and are spelled right; burned-in captions sit inside the safe area.
6. Flash check (`MOT-21`) on any section with rapid cuts or strobing light.
7. Metadata reviewed; credits and releases complete.

## Done when

- The cut list or timeline reproduces the render; originals are untouched.
- Cuts are frame-accurate where it matters, with no clicks, flash frames or drift.
- Loudness meets the destination's target, captions are complete and checked, color is consistent across clips and tagged.
- The export matches the destination's current specification, an editable timeline accompanies it where useful, and rights are recorded.
