# Reference originality audit

Read this when a site, app or campaign was built with reference material in hand (captured pages, screenshots, videos, prompt packs, a competitor's site, a mood board) and someone needs to know, before release, whether anything was copied too closely. The audit compares what ships with what was referenced, category by category, raises evidence-backed red flags, separates shared visual grammar from distinctive copying, and proposes fixes. Capturing references is `design-capture-workflows.md`; measuring a look without copying it is `../../creative-media/references/reference-look-measurement.md`; licenses for a launch are `../../legal-ready/GUIDE.md`.

## Ground rules

- **Audit only, unless fixes were requested.** Report; do not edit the site during the audit.
- **Call findings risks, overlaps or red flags,** never "plagiarism" or "infringement". Similarity is evidence; legal conclusions are for counsel.
- **Two locations per red flag:** the exact place in the shipped work and the exact place in the reference. A red flag without both is a hunch.
- **Keep fact, inference and gaps apart.** Missing evidence is reported as missing, never turned into a pass.
- **Check the whole shipped surface,** not the home page screenshot: every route, state, asset and the repository history.

## 1. Register the references

List every reference the project used, from the brief, prompt files, capture manifests, credits files and the team: path or URL, what it was used for, capture date, and which categories it can prove (text, images, motion). Prefer the copies captured at the time; a live page may have changed since. If a reference the brief mentions is missing, stop and report the gap rather than auditing a smaller set silently.

## 2. Inventory what ships

- Rendered text on every route, including navigation, buttons, legal text, alt text, accessible labels, page titles and meta descriptions.
- Names, marks, logos, people, company names, URLs and product names.
- Numbers: prices, metrics, percentages, dates, counts, plan structures.
- Every image, background, texture, icon, font, video, audio file and download, with its claimed source.
- Layout and motion: section order, distinctive compositions, scroll sequences, cursor effects, shaders.
- History: files that were renamed, recolored, cropped, replaced or deleted. Use `git log --all --name-status`, `git log -S "<distinctive phrase>"` and `git show <commit>:<path>` to find earlier versions. File names prove nothing; inspect contents.

Run the helper to collect leads from local files:

```bash
python3 <productcraft>/modules/builder-tools/scripts/reference_overlap.py --site dist/ --reference refs/ --reference prompts/ --json > overlap.json
```

It reports exact file matches by SHA-256, reused file names with different content, shared runs of eight or more words in visible text (markup tags, scripts and styles removed; alt and label attributes kept), and distinctive numbers found in both. It is read-only and offline. Exit code 0 means no leads, 1 leads found, 2 a usage error. Run it on both the source and the built output; built output can contain assets the source only references. Leads are starting points for comparison, never verdicts. Tests: `python3 -B -m unittest discover -s <productcraft>/modules/builder-tools/tests -v`.

## 3. Compare by category

| Category | What to compare | Strong evidence | Weak evidence |
|---|---|---|---|
| Text | Headlines, body, labels, calls to action, legal text, alt text, metadata | Identical or near-identical passages of eight words or more; a distinctive phrase plus the same structure | Short functional phrases ("Get started", "Learn more") |
| Brand identity | Names, marks, letterforms, slogans, people, partner names, URLs | A source name or mark rendered anywhere | A shared generic word |
| Numbers | Prices, metrics, dates, counts, plan structures | An unusual figure with matching wording | Round numbers alone |
| Images | Files, crops, composition, people and poses, props, color treatment | Same file bytes; same crop; recreated composition even if recolored | Similar palette or grain |
| Assets | Fonts, icons, textures, mockups, downloads, code bundles | Same files without a license record | Common open-source icon families used under their license |
| Video | Files, frames, shot order, timing, transitions, overlays, audio | Matching frames or the same cut sequence and timing | A common transition type |
| Structure and motion | The order of sections, rare layout devices, pinned scroll scenes, cursor and shader effects | Several distinctive elements reproduced together across sections | A standard hero, feature grid, pricing, FAQ and footer; fades, slides, marquees and parallax |

Do not flag common visual grammar on its own: dark backgrounds, one accent color, large sans-serif headings, a conventional page order, standard reveals. Escalate combinations of distinctive elements and any direct copy.

## 4. Triangulate each red flag

For every candidate:

1. Name the shipped artifact and its location (route, file and line, timestamp).
2. Name the reference artifact and its location.
3. Describe the observable overlap without guessing intent.
4. Describe what differs.
5. Assign a severity.
6. Propose the smallest change that removes the overlap while keeping the page's purpose.

Prove each finding: file hashes for assets, normalized text excerpts for copy, same-scale side-by-side crops for imagery, and the frame or time code on both sides for video. A source name that appears only in a test that forbids it, or in internal notes that do not ship, is context, not a shipped finding; say so.

| Level | Trigger | What to do |
|---|---|---|
| Stop the release | The build ships someone else's media, code, logo or a long run of their wording without a license | Take it out or swap in original work first |
| Serious | A section reproduces several of a reference's signature moves together, or shows its names or figures | Rework that section's layout or text from scratch |
| Moderate | A single recognizable element could make people think of the reference or credit it wrongly | Swap that element, or treat it in a clearly different way |
| Minor | Only general conventions are shared; the identity, words, composition and assets are your own | Note it in the report; a change is optional |
| None found | Nothing meaningful overlaps within what was examined | Keep the evidence, and list what was not examined |

## 5. Fixes that actually fix

- Rewrite copy from the new brand's own audience, offer and vocabulary, not by swapping synonyms.
- Swap every borrowed name, address, logo, face, figure, date, tier label and policy clause for the project's real ones.
- Commission, shoot, license or generate new imagery with a different subject, composition and motif arrangement; record provenance.
- Replace copied fonts, icons, textures and downloads with licensed equivalents and record the licenses.
- Rebuild video from your own footage: fresh shots, a different cut rhythm, your own transitions, captions and sound.
- Reorder or redesign distinctive section sequences and motion choreography.
- Remove copied material from build output, published artifacts and, where needed, repository history (history rewriting needs the owner's approval and coordination).

Recoloring, mirroring, cropping or blurring a copied element is not a fix.

## 6. Special cases

- **The reference is the owner's own work or licensed for reuse.** Record the license or ownership in the register; matches are then expected and become provenance notes, not red flags. Check that the license covers the new use (a template license may forbid resale, a photo license may forbid a logo or a product for sale).
- **Generated imagery and copy.** Check the prompts as well as the outputs: a prompt that names a living artist, a company or a specific campaign is a finding even if the output looks different. Compare generated images with the references fed to the model as conditioning; models conditioned on an image can reproduce its composition closely.
- **Templates and starter kits.** Code, layouts and placeholder copy from a bought or open-source template are fine under its license, but leftover demo copy, demo numbers and demo photos usually are not meant to ship; list them.
- **Code.** Distinctive effect code (a shader, a scroll sequence) copied from a reference site is a finding unless its license allows reuse and the notice is kept. Common library usage and standard patterns are not.
- **Open-ended references** ("we looked at a lot of sites") cannot be audited. Ask for the actual set, or report the audit as limited to the references that were recorded.

## 7. Report

Open with a single outcome: nothing found within the examined scope; only minor shared conventions; rework needed before release; release stopped; or no verdict because evidence is missing. Then:

1. The reference register (what was checked, dates, what could not be accessed).
2. Red flags ordered by severity, each with both locations, the overlap, the differences and the fix.
3. A pass list per category, including categories that could not be checked (marked as unverified).
4. History findings, separated from what is currently shipped.
5. A prioritized fix plan with owners.

```markdown
## Outcome: rework needed before release (scope: 9 routes, build of 2 March, 14 references)

### RF-1 [Serious] Pricing intro repeats a reference passage
- Shipped: /pricing, `src/routes/pricing.tsx:42`, "Every plan includes unlimited projects so your whole..." (23 words)
- Reference: refs/capture-03/full-page.png, pricing section; same 23 words in refs/capture-03/text.txt
- Overlap: identical wording and the same three-column order with the same plan names
- Differs: colors, type, imagery
- Fix: rewrite the intro from the brief's own offer; rename plans from the product's tiers

### Category results
| Category | Result | Notes |
|---|---|---|
| Text | 1 serious, 2 minor | RF-1; two common stock phrases kept and noted as minor |
| Video | Not verified | Reference video file missing from refs/ |
```

## Done when

- [ ] Every reference in the register was inspected, or its absence is reported.
- [ ] Rendered output, source, built output and history were all checked; the helper ran on source and build.
- [ ] All seven categories have a result or an explicit "not verified".
- [ ] Each red flag has two evidence locations, a severity and a concrete fix; exact matches are distinguished from stylistic resemblance.
- [ ] The report states its verdict, its scope and what remains unproven, without legal conclusions.
