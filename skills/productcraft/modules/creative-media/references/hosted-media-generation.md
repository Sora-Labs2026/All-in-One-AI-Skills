# Generating media through hosted models: images, video, speech, music and sound

Read this when a pipeline calls a hosted generation API, directly or through a gateway that serves many models: images, video clips, narration, voices, music or sound effects. It covers authorization and budgets, picking a model, checking the request against the current schema, the job lifecycle without double billing, uploads, voice and music specifics, provenance and labels. Writing the prompts, deciding whether to generate at all, and the safety and likeness rules are in `generation-prompting.md`; read that first. Model names, prices and parameters change monthly; this file holds the practice that carries over (2025).

Contents: before the first call · choosing a model · the request · the job lifecycle · cost · uploads · speech and voices · music and sound effects · images and video in an edit · provenance and labels · testing without spending · done when.

## Before the first call

- **Explicit authorization with a cap.** The user approves generation for this task and names a spending limit. Without both, produce only the plan.
- **A dry-run plan first:** one line per job with model, mode, inputs (by file hash, not content), key parameters, count and estimated cost, plus the total. Run nothing until it is approved. Make dry run the pipeline's default and require an explicit flag for live calls.
- **Keys** live in the environment or a secret store, never in code, chat, logs or committed files (`../../agent-safety/GUIDE.md`, `../../integrations/GUIDE.md`).
- **Terms:** read the provider's and the model's terms for commercial use, ownership of outputs, retention of inputs and outputs, and use of uploads for training. Record what you read and when.

## Choosing a model

- Look the model up in the provider's current catalog; do not rely on a model name remembered from earlier work. Record the exact identifier and version.
- Read its card: supported modes (text to image, edit, image to video, first and last frame, reference images, audio), size and duration limits, frame rates, whether it generates sound, the content policy, the license for outputs, and the pricing unit (per image, per megapixel, per second of video, per character or minute of audio).
- Iterate on a cheaper draft model or lower resolution, then render finals on the model that meets the brief. Check that the draft model's behavior transfers before relying on it.

## The request

- **Fetch the current input schema** for the endpoint (many providers publish one per model) and validate the request against it before paying. Misspelled or outdated field names are often ignored silently: the job runs, bills, and quietly drops your reference images or settings.
- **Check units and enums:** seconds or milliseconds, pixel sizes or named aspect ratios, strings like `"5"` versus numbers.
- **Name inputs explicitly:** where a model takes several reference images, pass them in the fields it defines for each role; a wrong label can be worse than no image, because the model trusts it.
- **Read outputs by key, not position.** Responses often contain previews and thumbnails next to the asset; take the field that holds the asset and check its type and size after download.

## The job lifecycle

Most hosted generation is asynchronous: submit, wait, download.

```python
# Generic sketch; endpoint shapes differ by provider. Standard library only.
import json, os, time, uuid, urllib.request, pathlib

API, KEY = os.environ["GEN_API_BASE"], os.environ["GEN_API_KEY"]   # never print KEY
LEDGER = pathlib.Path("generation-log.jsonl")
CAP = float(os.environ["GEN_BUDGET_USD"])                           # set by the user, required

def spent():
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines()] if LEDGER.exists() else []
    return sum(r["cost_estimate"] for r in rows if r.get("event") == "submitted")

def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def log(**row):
    with LEDGER.open("a") as f:
        f.write(json.dumps({"t": time.time(), **row}) + "\n")

def generate(model, inputs, cost_estimate, max_wait=900):
    if spent() + cost_estimate > CAP:
        raise SystemExit("budget cap reached: ask the user before spending more")
    key = str(uuid.uuid4())                                         # idempotency key, if supported
    job = call("POST", f"/models/{model}/jobs", {"input": inputs, "idempotency_key": key})
    log(event="submitted", job_id=job["id"], key=key, model=model, input=inputs, cost_estimate=cost_estimate)
    delay, deadline = 2, time.time() + max_wait
    while time.time() < deadline:
        status = call("GET", f"/jobs/{job['id']}")
        if status["state"] in ("succeeded", "failed", "canceled"):
            log(event=status["state"], job_id=job["id"])
            return status
        time.sleep(delay)
        delay = min(delay * 2, 30)
    raise TimeoutError(f"job {job['id']} is still running: check its status before submitting again")
```

- **Write the job ID to the ledger before waiting.** If the process dies, the job still exists and is still billed.
- **Never resubmit on a timeout.** Query the job's status first; resubmitting creates and bills a second job. Use idempotency keys where the provider supports them.
- **Webhooks** instead of polling: verify the signature on every delivery, and still reconcile against the job list.
- **Download promptly** (result links often expire), store with a checksum, and record the file name in the ledger.
- **Concurrency:** respect the provider's rate limits; keep a small number of jobs in flight and back off on 429 responses.

## Cost

- Estimate the batch before running it, from the pricing unit and the plan; stop at the cap even mid-batch, and report spend against the cap at the end.
- **Video for a fast-cut edit:** many short generations are wasteful (minimum durations, unrelated clips). Generate fewer, longer continuous takes and cut inside them, and say so in the prompt: one continuous take, no cuts inside it, framing and subject changing every second or so, because it will be cut into short pieces. Track used seconds against generated seconds.
- Keep rejected outputs' cost in the ledger; it is part of the real cost.

## Uploads

- Upload only material the user has rights to use this way, and nothing personal or confidential without the owner's permission.
- Strip location and device metadata from photos before upload (`image-enhancement.md`).
- Note the provider's retention period for uploads and delete them through the API when the job is done, where possible.
- Prefer local models for sensitive material; their weights carry their own licenses (`generation-prompting.md`, "Hosted and local models").

## Speech and voices

- **Stock synthetic voices:** check that the voice's license covers the use (commercial, broadcast, advertising) and the regions.
- **Cloned voices:** only the speaker's own voice, with their documented, informed consent for this use: scope, duration, where it will appear, how they can withdraw. Keep the consent record with the project. Never clone a public figure or anyone who has not agreed; providers increasingly require proof, and several jurisdictions protect voice as part of a person's likeness (for example Tennessee's ELVIS Act, in force since July 2024).
- **Prepare the script for speech:** write numbers, dates, abbreviations and units as they should be spoken; give pronunciations for names (the provider's pronunciation dictionary or markup where supported); split long scripts into paragraphs and generate them separately so a fix does not re-render everything.
- **Listen to every take,** check names and numbers, then normalize loudness with the rest of the mix (`video-editing.md`, "Audio").
- **Disclose** synthetic narration where the platform, the advertising rules or the context require it, and always when a voice could be mistaken for a real, identifiable person.
- Captions and a transcript are still needed (`remotion-video.md`).

## Music and sound effects

- **Read the music license:** commercial use, whether outputs are exclusive, attribution, and whether the provider or others may register similar tracks with content identification systems, which can trigger claims against your video. Keep the generation record as evidence of origin.
- **Do not prompt with an artist's name or a specific song,** and do not try to produce a sound-alike of a known track.
- Generate stems or longer beds where possible so the editor can cut music to the picture; duck it under speech.
- **Sound effects** generated from video should be checked frame by frame for sync and layered under recorded sound rather than replacing it.

## Images and video in an edit

- **Color:** ask for neutral color and apply the project's grade afterwards (`reference-look-measurement.md`); color words in prompts give inconsistent results across a set.
- Choose aspect ratio and resolution by the delivery format; upscale separately when needed (`image-enhancement.md`).
- Review every output at full size, frame by frame for video (`generation-prompting.md`, "Review the output"), and keep two or three of each kind, not one.
- Reference images for identity or style need the same rights as any upload.

## Provenance and labels

- **The ledger is the record:** for every kept output, the model and version, mode, full prompt, inputs by hash, seed and parameters, job ID, cost, consent references, output hash and file name.
- **Keep embedded provenance** (C2PA content credentials) that providers attach; check that export steps do not strip it.
- **Label** synthetic or materially altered media where the platform or the law requires it; the EU AI Act's transparency duties apply from August 2026 (`generation-prompting.md`, "Labels and provenance").
- List generated media in `credits.md` with how they are labeled.

## Testing without spending

- Unit-test request building, schema validation, cost estimation and ledger logic against recorded responses (fixtures) with the network disabled.
- One live smoke test, approved and budgeted, after any change to model, endpoint or schema.
- Tests never read real keys; build fake ones at runtime when a code path needs a non-empty value.

## Done when

- The user approved the plan and the cap; spend stayed under it and is reported.
- Every request was validated against the model's current schema, and every job ID is in the ledger with its outcome.
- No job was submitted twice by accident; outputs were downloaded, checksummed and reviewed at full size.
- Consents for voices and likenesses are on file; music and model licenses were read and recorded.
- Provenance is kept, required labels are applied, and generated media appear in `credits.md`.
