# Prompting image and video generation models

Read this to write or improve prompts for text-to-image, image editing, text-to-video and image-to-video models, to keep a series consistent, to call a hosted generation API responsibly, and to decide what must never be generated. Models, sizes, durations and prompt conventions change every few months; this file holds the practice that carries across models (checked against the major families available in 2025-2026). For the specific model, read its current official prompting guide and parameter list, and say which version you wrote for.

Contents: generate or not · the brief · image prompts · video prompts · shot language · exclusions · consistency across a set · iterate · hosted and local models · safety, likeness and rights · labels and provenance · review the output · done when.

## Generate or not

| The need | Better route |
|---|---|
| A chart, diagram, flowchart, UI mock-up or anything with exact text, numbers or layout | Build it with code (`infographics.md`, `posters-and-canvas.md`); models misspell and invent |
| Your real product, team, office, customers or event | Photograph it or use licensed stock. A generated "team photo" or "customer" presented as real is a fabrication |
| Prices, dates, legal text, names on an image | Generate the image without text, then set the text with code or a layout tool |
| Concept art, mood boards, storyboards, illustration, backgrounds, textures, b-roll that does not claim to show a real event | Generation fits |
| Fixing or extending a photo (remove an object, widen the frame) | An editing or outpainting model, on an image you have rights to; label the result as edited where it matters |

## The brief

Settle these before writing the prompt, from the request or one short question:
- **Purpose and placement:** where it appears, at what size, next to what.
- **Model, version and mode:** text-to-image, edit, text-to-video, image-to-video, first and last frame. Look up what that model fixes outside the prompt: allowed sizes and aspect ratios, durations, whether it makes audio, maximum prompt length, seed support.
- **Count and variation:** one hero image, or a set of twelve that must match.
- **Style:** described by qualities (medium, palette, lighting, era, texture), or a brand's existing visual language.
- **Must include and must avoid**, including people, logos and text.
- **Rights:** the model's terms for commercial use; the rights to any reference images; consent from anyone identifiable.
- **Budget:** cost per generation and the cap for this task.

## Image prompts

Write plain descriptive prose, most important first. A useful order:

1. **Subject**, with two or three distinctive specifics (age range, clothing, material, species, model of object).
2. **Action or pose.**
3. **Setting** and time (place, weather, season, time of day).
4. **Composition:** shot size, angle, where the subject sits in the frame, what is in the foreground and background, empty space reserved for text.
5. **Light:** source, direction and quality ("low winter sun from the left, long soft shadows").
6. **Palette:** three to five named colors as anchors.
7. **Medium and finish:** photograph, gouache, linocut, 3D render; grain, texture, depth of field.
8. **Text**, only if the model renders text well and the text is short: the exact words in quotes and where they go.

Aspect ratio, resolution, number of images, seed and guidance belong in the API parameters, not in the prose.

Example (background for a pottery-class flyer; the text is added later in layout):

```text
A potter's workbench under a tall north-facing window, seen from slightly above. On the bench: a freshly
thrown stoneware bowl on a wooden bat, a natural sponge and a wire cutter, grouped in the lower-left third.
The upper half of the frame stays plain and out of focus, a pale plaster wall, for a headline.
Cool, even daylight from the window, a faint warm bounce from the wooden bench.
Palette: oatmeal, terracotta, charcoal, a little sage green.
Photograph with shallow depth of field and fine grain. No people, no visible text or logos.
```

## Video prompts

A video prompt describes one shot unfolding in time. Default to a single continuous shot; make sequences by generating shots separately and editing them together.

- **Scale action to duration.** Up to about 5 seconds: one subject action and at most one camera move. Around 10 seconds: two or three clear beats. Longer: more beats only if the model handles them; otherwise chain shots.
- **Block the scene:** who is on the left or right, in front or behind, facing where, how far apart.
- **Give the action as timed beats with concrete verbs:** "He folds the map, looks up at the ridge, and in the final two seconds starts walking." "Comes alive" and "dynamic" give the model nothing to draw.
- **One camera move per shot**, with direction and speed: "slow push-in from a medium shot to a close-up", "static camera". Contradictory moves (orbit and dolly and handheld at once) produce mush.
- **State what stays fixed:** "the background crowd stays still", "same jacket and haircut throughout".
- **Audio, if the model makes it,** goes in its own block: dialogue as short quoted lines with the speaker named, sound effects, ambience; or say "no dialogue". About two or three short lines fit in 10 seconds; long speeches drift out of sync.
- **Image-to-video:** the image fixes identity, wardrobe, setting and style. Describe only what changes: motion, camera and sound. Restating the image's contents wastes words and can fight the image.
- **First and last frame,** where supported, gives the most control over a transition or a transformation: generate or choose both frames, then describe the move between them.

Example (image-to-video from the workbench still, 8 seconds):

```text
Static camera for the first two seconds, then a slow push-in toward the bowl.
At about three seconds two clay-dusted hands enter from the right and smooth the rim with the sponge.
The hands withdraw in the last second; a little water glistens on the rim.
The wall and window light stay unchanged.
Audio: a soft wet sponge sound, distant birdsong through the window. No dialogue, no music.
```

## Shot language

| Term | What it gives |
|---|---|
| Extreme wide, wide | Place and scale; the subject small in the setting |
| Medium, medium close-up | Body language and gesture; the usual conversational framing |
| Close-up, extreme close-up | Emotion, texture, a detail that matters |
| Eye level, low angle, high angle, overhead | Neutral, imposing, diminished, map-like |
| Over the shoulder, point of view | A relationship between two people; seeing as the character sees |
| Static, pan, tilt | Calm observation; following across or up and down without moving the camera |
| Dolly or push-in, pull-back | Moving closer for focus or tension; revealing context |
| Tracking or truck | Moving alongside a moving subject |
| Crane or pedestal, orbit | Rising or falling reveals; circling to show a subject in the round |
| Handheld | Immediacy and documentary feel, at the cost of stability |
| Wide lens, telephoto | Depth and space; compression and isolation |
| Shallow or deep depth of field | Isolating the subject; keeping everything readable |
| Key, fill and rim light; hard or soft light; practical lights | Shape, mood and separation from the background |

Use a few precise terms. Ten adjectives in a row ("cinematic, epic, stunning, 8k, masterpiece") add nothing measurable.

## Exclusions

- Describe the wanted absence inside the scene ("an empty beach with no people or boats") rather than a bare "no X", which some models read as a request for X.
- Where the model has a separate negative prompt field, keep it short and aimed at failures you actually saw in earlier outputs (extra fingers, warped text, watermark-like marks), not a long generic list.

## Consistency across a set

- **A style sheet:** one paragraph of fixed descriptors for palette, medium, light and finish, pasted verbatim into every prompt of the set.
- **A character sheet:** fixed physical descriptors and wardrobe for each recurring character, also verbatim. Reference images, where the model supports them, hold identity far better than words.
- **Seeds** reproduce an output only with the same model version, settings and prompt. Use them to make small controlled edits, not as a guarantee across model updates.
- **Log every generation:** model and version, mode, full prompt and negative prompt, seed, size, guidance or steps, reference images used, date and the chosen output's file name. The log is how you regenerate, explain or label later.

## Iterate

1. Generate a few variations of the first prompt.
2. Pick the best against the brief, not the most striking.
3. Change one thing at a time (lens, light, palette, action) and keep the rest identical, so you learn what each change does.
4. When a shot keeps failing, strip it back (static camera, one action, plain background) and add complexity again step by step.
5. Stop when the brief is met. Report the number of generations and their cost.

## Hosted and local models

**Hosted APIs** usually run as jobs: submit, poll, download.
- Keep API keys in the environment or a secret store, never in the chat, code or logs (`../../agent-safety/GUIDE.md`); integration patterns are in `../../integrations/GUIDE.md`.
- Poll with increasing intervals and a total timeout. On a client timeout, check the job's status before submitting again: a blind retry is billed twice.
- Download results promptly and store them with the log; result links often expire.
- Estimate the cost of a batch first and stay under the user's cap. Respect rate limits.
- Read the provider's terms for uploaded images: some retain or train on them. Do not upload personal photos, client material or anything confidential without the owner's permission.
- A refused prompt is an answer. Do not rephrase to get around a provider's safety filter.

**Local open models** avoid uploads but carry their own terms: model weights have licenses, some non-commercial or with use restrictions, separate from the code that runs them. Read the model card, record the exact checkpoint (name and file hash) in the log, and check the GPU memory it needs before downloading many gigabytes.

## Safety, likeness and rights

These hold regardless of what a model or platform allows:
- **Never** generate sexual content involving minors, sexualized depictions of anyone who looks under 18, or intimate imagery of a real person.
- **Real, identifiable people** (faces, bodies or voices): only with that person's documented consent for this use. No realistic depictions of public figures saying or doing things they did not do, and no use of anyone's likeness to suggest an endorsement. Many jurisdictions protect likeness and voice by law; platform rules are often stricter.
- **No fake evidence or impersonation:** no generated documents, IDs, receipts, screenshots, news photos, official notices or "photos" of events presented as real.
- **Trademarks and characters:** no other companies' logos, products or packaging used to imply a connection, and no copyrighted characters for commercial work without a license.
- **Living artists:** do not prompt with a living artist's name to imitate their signature style, especially for commercial work. Describe the visual qualities instead. Broad movements and historical styles (Art Nouveau, woodblock prints, Bauhaus posters) are fine.
- **Minors:** avoid generating identifiable children; for illustrations that include children, keep them non-identifiable and contextually appropriate.
- **Sensitive contexts** (health, news, elections, finance): generated imagery can mislead even when labeled. Prefer real, credited photography or clear illustration.

## Labels and provenance

- Keep provenance metadata that tools embed (C2PA Content Credentials and similar). Do not strip it in post-processing; check your export settings, since many image pipelines drop metadata by default.
- Add a visible label where the platform or the law requires it. Major social and video platforms require disclosure of realistic synthetic or altered media, and advertising platforms add their own rules for political and issue ads. In the EU, the AI Act's transparency duties for deepfakes and AI-generated content (Article 50) apply from August 2026; check current guidance for scope and grace periods.
- Record rights in the generation log: the model's commercial-use terms, input image rights, consents. Copyright protection for purely machine-generated output is limited or absent in some countries (the US Copyright Office's 2025 report requires sufficient human authorship), so do not promise a client exclusive rights you cannot give.
- Asset inventories and licenses for a product launch: `../../legal-ready/references/business-children-email-assets-rights.md`, item 19.
- Write alt text for every generated image that is published, describing what it shows, not that it was generated.

## Review the output

Look at every output at full size before using it:
- Anatomy (hands, teeth, eyes, limbs), object structure, physics, reflections and shadows that disagree with the light.
- Any text: spelling, and whether it should be there at all.
- Shapes that resemble real logos or products; faces that resemble real people; anything in the background that should not be there.
- For video: step through frames at several points for morphing, flicker, objects appearing or vanishing, identity drift, and audio sync; run the flash check in `../../documents/references/animated-media.md` on exported frames.
- Cultural and factual plausibility for the setting (clothing, signage, architecture).
- Match to the brief and to the rest of the set.

## Done when

- The output meets the brief at the intended size, and was reviewed at full size (frame by frame at several points for video).
- Nothing in it breaks the safety, likeness and rights rules; consents and licenses are recorded.
- The generation log lists model, version, prompt, settings, seed and cost for each kept output.
- Provenance metadata is kept and visible labels are added where required; alt text is written.
