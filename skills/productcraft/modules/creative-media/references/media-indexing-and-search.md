# Indexing and searching video and audio

Read this when a set of recordings (talks, lectures, meetings, interviews, podcasts, product videos, screen sessions) must become searchable: find the moment someone said something, every shot showing a whiteboard, the slide where a figure appeared; then cut clips or a highlights compilation from the results. The pipeline below runs locally with open tools; hosted indexing services follow the same model and the same questions apply. Tool versions as of 2025.

Contents: consent and privacy first · the pipeline · transcripts · shots and keyframes · text on screen and descriptions · the index · searching · acting on results · evaluating quality · live sources · hosted services · done when.

## Consent and privacy first

- **Recordings of people are personal data,** and transcripts are as sensitive as the audio. Index only material the owner has the right to process, for a purpose the people recorded would expect.
- **Meetings and calls:** participants must know they are recorded; several jurisdictions require every party's consent. Do not index other people's calls on someone's behalf without it.
- **Screen recordings** capture passwords, messages, customer records and tokens. Exclude sensitive windows when recording, and scan the index for secrets before sharing it (`../../credential-shield/GUIDE.md`).
- **No identification of private individuals:** do not add face recognition or voice identification of people who have not agreed to it. Speaker labels ("Speaker 1") are fine; names come from the people themselves or the meeting record.
- **Cameras and live feeds** that watch people are surveillance: they need a lawful basis, notice and, under the GDPR, usually a data protection impact assessment. Build alerts only for the owner's premises and purposes, and keep a person in the loop for any action.
- **Retention and deletion:** decide how long media, transcripts, embeddings and clips are kept, and make deleting a recording delete everything derived from it.

## The pipeline

```
ingest  ->  segment  ->  enrich  ->  index  ->  search  ->  act
probe,       speech,      on-screen   keyword     hybrid      clips,
checksum,    shots,       text, frame and vector  ranking,    montages,
audio        keyframes    descriptions            filters     chapters
```

Store every derived record with the media's SHA-256, its start and end time in seconds, the kind of record, and the model and version that produced it. When a model changes, you know exactly what to re-index.

## Transcripts

- Run a Whisper-family speech model locally (for example whisper.cpp or faster-whisper) on 16 kHz mono audio extracted with FFmpeg, with word-level timestamps.
- Give the model the vocabulary it will meet (product names, people's names) through its initial prompt or hotword option; correct remaining names by hand for important material.
- Split into sentence segments, then into overlapping windows of roughly 30-60 seconds for semantic search, so a search hit carries enough context to judge.
- Speaker diarization (who spoke when) comes from separate open models with their own licenses and accuracy limits; check the license before use and spot-check boundaries.
- Record the language; mixed-language recordings need a model and settings that handle them.

## Shots and keyframes

- **Edited or camera footage:** detect shot boundaries with FFmpeg's scene score (`select='gt(scene,0.3)',showinfo`) or PySceneDetect (`scenedetect -i talk.mp4 detect-adaptive list-scenes`). Thresholds depend on the material: sweep a few values and check boundaries by eye (`reference-look-measurement.md`).
- **Screens and slides** change little between "shots": sample a frame every few seconds and keep it only when it differs enough from the last kept frame, or when the on-screen text changes.
- Keep one representative frame per shot (the middle frame avoids transitions) as a small JPEG with its timestamp.

## Text on screen and descriptions

- **On-screen text:** run OCR (Tesseract, with the right language packs) on keyframes of slides, screens and signs. Text on screen is often the most precise search key in technical videos.
- **Descriptions:** a vision model can caption each keyframe ("a person draws a sequence diagram on a whiteboard"). Local models keep frames private; a hosted model is an upload of the frames and needs the owner's permission. Treat descriptions as approximate and never as identification of people.
- **Metadata:** title, date, event, chapter, speaker list from the meeting record, language.

## The index

A keyword index finds exact terms and names; a vector index finds paraphrases. Use both.

```python
import sqlite3  # Python's sqlite3 usually includes FTS5; check with: PRAGMA compile_options
db = sqlite3.connect("media-index.db")
db.executescript("""
CREATE TABLE IF NOT EXISTS media(sha256 TEXT PRIMARY KEY, path TEXT, title TEXT, duration REAL);
CREATE VIRTUAL TABLE IF NOT EXISTS segments USING fts5(
  body, sha256 UNINDEXED, t_start UNINDEXED, t_end UNINDEXED, kind UNINDEXED, model UNINDEXED,
  tokenize = 'porter unicode61');
""")
db.execute("INSERT INTO segments VALUES (?,?,?,?,?,?)",
           ("we keep an error budget of one percent per quarter", "3f2a...", 754.2, 761.9, "speech", "asr-small-2025"))
hits = db.execute("""
  SELECT sha256, t_start, t_end, snippet(segments, 0, '[', ']', '...', 12)
  FROM segments WHERE segments MATCH ? ORDER BY bm25(segments) LIMIT 20""", ('"error budget"',)).fetchall()
```

- `bm25()` returns lower values for better matches, hence the ascending order.
- For semantic search, embed each transcript window and each keyframe description (and optionally the keyframe image with an image-text embedding model) and store vectors with the same `sha256`, `t_start` and `t_end`; a vector extension for SQLite, a vector database or a flat NumPy array all work at small scale.
- Record the embedding model and version with every vector; vectors from different models cannot be compared.

## Searching

- **Hybrid ranking:** run the keyword and vector searches separately and merge with reciprocal rank fusion (score = Σ 1 / (60 + rank) across the lists), which needs no score calibration.
- **Filters** by recording, date, speaker label, kind (speech, on-screen text, description) before ranking.
- **Snap results** to sentence or shot boundaries and pad them by a second or two, so clips do not start mid-word.
- **Show evidence:** the matching text with the hit highlighted, the timestamp, a keyframe, and a link that opens the player at that time (`#t=754` media fragments work in browsers for local files and many players).
- **No results is a normal answer;** say so and suggest a broader query, rather than returning low-scoring noise. Set a minimum score for vector hits after looking at real queries.

## Acting on results

- **Clips:** cut frame-accurately with re-encoding (`video-editing.md`, "Cutting accurately"); validate every range first (`0 <= start < end <= duration`).
- **Highlights compilations:** order clips chronologically or by a reviewed ranking; add a title card per clip with the source and time; captions from the transcript.
- **Chapters:** generate WebVTT chapters from topic changes in the transcript, then review the titles by hand.
- **Summaries** produced by a language model from the transcript must link each statement to timestamps so a reader can check it; never present an unsupported summary as the record of a meeting.

## Evaluating quality

- Write 15-30 real queries with the recording and time range a person would expect for each. Measure hit@5 (a result overlapping the expected range within a few seconds) and the timestamp error, for keyword-only, vector-only and hybrid search; keep the set and re-run it whenever a model or setting changes.
- Measure transcription quality on a few hand-corrected minutes (word error rate), with special attention to names and numbers.
- Report numbers, not impressions: "hybrid hit@5 = 0.83 on 24 queries; keyword-only 0.67".

## Live sources

For a live stream or a capture session: buffer short segments (for example 10-30 seconds), process them as they close, and append to the index; publish alerts with rate limits and the evidence clip attached. Latency comes from segment length plus processing time; state it. A person reviews an alert before anything consequential happens. Record and keep only what the stated purpose needs.

## Hosted indexing services

The same model applies: upload or link media, build spoken and visual indexes, search, compile clips. Before using one, establish: where media and derived data are stored and for how long; whether they are used for training; how to delete a recording and everything derived from it; the price per hour indexed and searched; whether indexes can be exported; and how jobs report completion (webhooks with signatures, or polling). Keep keys out of code and chat (`../../agent-safety/GUIDE.md`). Make indexing idempotent: look up an existing index for the media before creating another. Treat "no results" responses as empty results, not failures, and validate timestamps before building timelines from them.

## Done when

- Consent, purpose and retention are written down, and sensitive recordings were reviewed or excluded.
- Every indexed record carries the media hash, time range and producing model version.
- Search returns timestamped evidence that opens at the right moment, and clips are frame-accurate.
- Retrieval quality was measured on a saved query set and the numbers are reported.
- Deleting a recording removes its transcripts, frames, vectors and clips.
