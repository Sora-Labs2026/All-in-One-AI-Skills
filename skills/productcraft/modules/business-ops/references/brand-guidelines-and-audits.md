# Brand guidelines, voice systems and experience audits

Read this when a brand exists (or has just been chosen) and must be written down so other people can apply it: a voice and tone system, a guidelines document or brand book, a check that new assets follow it, an organized asset library, or an audit of how the leading products in a category present themselves. Upstream work (positioning, naming, mood, the brief) is `brand-ideation-and-briefs.md`; the founder interview and a voice profile from samples are `brand-discovery-and-voice.md`; applying a theme to slides and documents is `../../creative-media/references/themes-and-brand-application.md`; the rules for brand in UI are `BRD-01` to `BRD-05` in `../../../references/ui-rules/branding.md`.

## Ground rules

- **Document what is true, not what is hoped.** A rule the brand already breaks everywhere is read as a suggestion. Either change the practice or leave the rule out.
- **Every rule has an example, every example has a rule.** Rules without pictures are ignored; pictures without rules cannot be applied to new cases.
- **Mark the strength of each rule:** fixed (never changes), flexible (choose within a range), forbidden. Most disputes come from not knowing which.
- **Publish where people work.** A web page or a design-file library with a stable link beats a long PDF on a shared drive.
- **Version and date it.** Each release lists what changed and why.

## 1. Voice and tone system

`brand-discovery-and-voice.md` captures how a person or brand already writes. This section turns that into a system a team, a freelancer or an AI assistant can apply across contexts.

**Voice traits.** Three to five traits, each with the limit that stops it overshooting: "plain-spoken, not blunt", "curious, not scattered", "warm, not syrupy". Generic traits ("friendly, professional") fail the test of distinguishing this brand from any other; replace them.

**Tone by context.** The voice stays fixed; tone moves with the reader's state. Map the contexts the brand actually writes in:

| Context | Reader's state | Tone setting |
|---|---|---|
| First run and onboarding | Curious, unsure | Encouraging, unhurried, one step at a time |
| Marketing pages | Evaluating | The voice at full strength, claims specific and sourced |
| Product interface | Busy | Short, literal, verbs first |
| Errors and failures | Frustrated or anxious | Calm, factual, no jokes, no apology theater; what happened and what to do |
| Success | Relieved | One short acknowledgement, then the next step |
| Empty states | Unsure where to start | Helpful; the value of the area and the first action |
| Billing, pricing, cancellation | Wary | Transparent and plain; no pressure (`../../ethical-persuasion.md`) |
| Legal and policy | Cautious | A plain-language summary next to the binding text |
| Incidents and outages | Worried | Factual, accountable, time-stamped, with the next update time |
| Support and help | Stuck | Patient, complete, never condescending |

**Vocabulary and mechanics.** Words the brand uses and avoids; any terms it defines for itself (and a glossary so they are used consistently); jargon kept or explained; person ("we" and "you"); case style (sentence case for interface text is easiest to translate and read); contractions; numerals; punctuation habits. Include only rules that distinguish the brand; generic grammar belongs to a house style guide.

**Paired examples.** The most-used part of any voice document. For each content type (headline, button, error, empty state, push notification, onboarding step, email subject, release note, support reply, social post, pricing line, cancellation screen, incident update, 404 page, legal summary), give an off-voice and an on-voice version plus one line on what changed. Aim for 15 to 25 pairs; the off-voice versions should be plausible drafts, not caricatures.

A skeleton for the voice document:

```text
VOICE AND TONE  (brand, version, date, owner)
Traits:        plain-spoken, not blunt | curious, not scattered | warm, not syrupy
Tone table:    context -> reader's state -> setting (as above, one row per context the brand writes in)
Vocabulary:    we say ... / we avoid ... / our own terms and their definitions
Mechanics:     person, case style, contractions, numerals, punctuation habits
Pairs:         content type -> off-voice draft -> on-voice version -> what changed
Anti-patterns: phrases and constructions that never appear, each with the reason
Sources:       the samples and decisions this document rests on
```

**Stress test.** Give a fresh brief to someone who did not write the document (or to an AI assistant that has only the document) and score the result 1 to 5 against each trait. Anything under 3 means the document is missing guidance; fix the document, not only the draft.

## 2. The guidelines document

| Section | Contents | Common gap |
|---|---|---|
| Story | Purpose, positioning statement, audience, values with the behavior each implies, what the brand is not | Values with no behaviors |
| Marks | Primary lockup, alternates (stacked, symbol-only, monogram), construction grid, clear space as a unit of the mark, minimum sizes per medium, color versions (full, one color, reversed), misuse examples, file locations (`../../creative-media/references/logos-and-marks.md`) | No small-size or one-color version |
| Color | Roles (not just swatches), values in hex, RGB and OKLCH for screens and CMYK or spot references for print, light and dark variants, measured contrast for every approved text pair, forbidden pairs, proportion of use | Swatches with no roles or contrast |
| Type | Families and their licenses, the scale with sizes and line heights, weights per role, tracking, fallback stacks, an open-licensed alternative for contexts where the main face cannot be embedded | No fallback, unlicensed web embedding |
| Imagery | Photo direction (subjects, light, crop), illustration style, icon family and how to add icons, treatments (duotone, grain), images that are off-brand | Mood words with no examples |
| Motion | Easing and duration tokens, how the mark enters and exits, reduced-motion behavior | Missing entirely |
| Voice | Section 1 above, condensed, with a link to the full document | Separate document nobody links |
| Applications | Real examples per channel: web, product UI, email, social, slides and documents, print, packaging and signage if relevant | Mockups that never shipped |
| Dos and don'ts | A scannable page of correct and incorrect pairs for marks, color, type, layout and copy | Treated as filler; it is the page people use most |

**Accessibility inside the guide.** Each approved text-on-fill pair lists its WCAG ratio (4.5:1 for body text, 3:1 for large text and non-text elements). A brand color that fails as text is documented as "fill or accent only". Do not publish a palette whose primary action color fails on its own background.

**From guide to code.** The guide's color, type, space, radius and motion values are the primitive tier of the token system (`../../ui-distiller/references/design-system-construction.md`). Keep one source: either the token file generates the guide's swatch pages, or a script reads a structured block in the guide and writes the token file. Never maintain both by hand. When a script syncs them, have it refuse to overwrite token files it did not create, and show a diff first.

## 3. Checking new assets against the brand

Run this pass before a banner, deck, page or video is approved:

- **Marks:** right variant for the space, clear space and minimum size respected, approved color version for the background, no stretching, recoloring, outlines or effects.
- **Color:** only palette values (sample the export; any stray value is a finding), roles used as intended, every text pair at its contrast threshold.
- **Type:** brand families actually rendered (check the exported file's fonts, not the source), scale levels respected, no faux bold or italic.
- **Imagery:** fits the photo and illustration direction, license and model or property releases on file, credit given where the license asks.
- **Copy:** on voice for the context, claims sourced, no prohibited terms, call to action specific.
- **Access:** alt text written, reading order sensible, captions on video, no flashing above three per second.
- **Technical:** correct pixel size and format for the destination, file weight within the channel's limit, color profile sRGB for screens.

Record the result as pass, fix needed (with the item) or exception approved by the brand owner.

## 4. Organizing the asset library

- **Separate masters from deliverables.** Editable masters (vector, layered files, raw photos) live in one place; exported files are derived and can be regenerated.
- **Name files so they sort and say what they are:** `type_campaign_subject_variant_size_date.ext`, lowercase with hyphens inside fields, for example `banner_spring-sale_hero_dark_1200x628_2026-03-02.png`. Use `evergreen` for assets not tied to a campaign.
- **Keep metadata with each asset:** owner, source (made in house, licensed, generated with which model and prompt, commissioned), license terms and expiry, releases, alt text, approval status and date.
- **Track expiry.** Licensed photos, music and fonts often have term or seat limits; a monthly check lists assets whose rights end within 60 days.
- **Generated assets** carry their prompt, model and version, seed where available, and the human edits made (`../../creative-media/references/generation-prompting.md`).
- **Retire, do not delete.** Move superseded assets to an archive with the date and the replacement, so old pages can still be traced.

For the delivery pipeline (formats, responsive sizes, CDNs) see `../../creative-media/references/icon-sets-and-stock-imagery.md` and `../../engineering-practices/references/performance.md`.

## 5. Category experience audit

Use this before a new build in an unfamiliar category, to learn what users there have come to expect and where every leading product falls short. It complements `competitive-analysis.md`, which compares businesses; this compares experiences.

**Scope.** Three to six leading products or sites, chosen with the owner. Fewer than three cannot show a pattern; more than six rarely adds new ones. View each rendered, on the device most of its visitors use, signed out unless the owner provides test access. Record the date: sites change.

**Dimensions.** Judge each by things you can point at, not by taste:

| Dimension | Observable questions |
|---|---|
| Primary task | What is the largest interactive element in the first viewport? How many steps to the core task? How many elements compete for first attention? |
| Density and register | How many distinct modules sit above the fold? Does the page read as a store, a catalog, a publication or a pitch? |
| Breadth of offering | How many entry points to categories or products before scrolling? How is depth signaled (menu, grid, filters)? |
| Wayfinding | Is search primary, secondary or absent? Which browse paths exist (by category, by attribute, by need, by location)? |
| Brand posture | Color, type and image register; heading and button language; consistency across pages |
| Trust and conversion | Reviews, guarantees, price visibility and total cost, stock or availability, compatibility or eligibility checks, returns and service promises |

**Scoring.** Per dimension: "shared convention" when at least three of the sites do the same thing, "split" when the field divides between two or three approaches, "gap" when no site does it well, and "not assessable" when the evidence cannot support a judgment (layout and motion cannot be judged from fetched HTML; voice cannot be judged from one page). A move made by one site is a single observation, never a convention.

**Language discipline.** Report "four of five lead with a search box spanning the full width", never "the design is clean". If you cannot point at something, it is taste and stays out of the audit.

```markdown
## Primary task (scored: shared convention)
| Site | Largest first-view element | Steps to core task | Competing calls to action |
|---|---|---|---|
| A | Search box, full width | 2 | 1 |
| B | Search box with category picker | 2 | 2 |
| C | Category grid | 3 | 3 |
| D | Search box, full width | 2 | 1 |
Pattern: 3 of 4 lead with search spanning the content width. Gap: none shows availability before the results page.
Not assessable: motion on C (only a fetched HTML copy was available).
```

**Output.** The field and date, a dimension-by-site table with evidence (screenshots with locations), the list of conventions a credible entrant must meet, the gaps the whole field shares (the positioning opportunity), and what could not be assessed. For a public version, describe patterns without naming the competitors.

## Done when

- [ ] Voice traits have limits, a tone table covers every context the brand writes in, and 15 or more paired examples exist; a stress test by someone else scored 3 or more on every trait.
- [ ] The guide covers story, marks, color with measured pairs, type with licenses, imagery, motion, voice, applications and dos and don'ts, with each rule marked fixed, flexible or forbidden.
- [ ] One source feeds both the guide and the token files.
- [ ] New assets were checked against section 3 with results recorded; library assets carry source, license and approval metadata.
- [ ] An experience audit cites observable evidence for every pattern, uses the three-site threshold for conventions, and lists what was not assessable.
