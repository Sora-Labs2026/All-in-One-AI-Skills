# UI rules: Color and contrast

Contrast minimums, palette discipline, emphasis and text on images. Rule IDs use the `COL-` prefix; cite them in change reports.

## COL-01. Measure contrast against WCAG AA

**Why:** Text that looks fine to the designer can be unreadable for people with low vision or in bright light.

- **Do:** Reach at least 4.5:1 for normal text and 3:1 for large text (24px+, or 18.66px+ bold).
- **Do:** Reach at least 3:1 for UI component boundaries, focus indicators and icons that carry meaning.
- **Do:** Check every token pair with a contrast tool, including white labels on brand-colored buttons.
- **Avoid:** Judging contrast by eye, or pale brand text on a light tint of the same hue.
- **Note:** A bright brand color does not guarantee readable white text; many oranges, greens and cyans fail with white.

## COL-02. Start neutral and give one accent a job

**Why:** When everything is colorful nothing stands out; a neutral base lets the accent signal importance.

- **Do:** Lay out the screen in neutrals first, then add color only where it carries meaning: primary action, links, active state, status.
- **Do:** Work from a compact palette: a light base, a dark base, one accent and at most one supporting tone.
- **Do:** Keep structural colors (surfaces, text) separate from semantic colors (success, warning, error).
- **Avoid:** A different pastel or gradient on every card, banner and icon.
- **Avoid:** Using the accent on decorative elements until it no longer signals interactivity.

## COL-03. Use 60-30-10 as a starting balance

**Why:** A rough split between base, secondary and accent color keeps a screen calm and the accent meaningful.

- **Do:** Aim for about 60% neutral base, 30% secondary surfaces and 10% accent, judged by visual weight.
- **Do:** Define the three roles as tokens (for example --color-bg, --color-surface, --color-accent).
- **Avoid:** Spreading the accent across large backgrounds.
- **Note:** A heuristic, not a quota.

## COL-04. Give the most important action the strongest color

**Why:** The eye lands first on the most saturated, highest-contrast element.

- **Do:** Give the single most important action the most vivid fill on the screen and keep surrounding controls muted.
- **Do:** On dark screens, use a bold filled call to action rather than an outlined one that blends in.
- **Avoid:** Several equally vivid elements competing, or a muted primary action beside vivid decoration.

## COL-05. Avoid pure primaries and pure black on white for large areas

**Why:** Fully saturated hues and maximal contrast across large surfaces look harsh and tire the eyes.

- **Do:** Use slightly toned variants instead of #FF0000, #00FF00, #0000FF and similar pure hues.
- **Do:** Use near-black (for example #171717) for text and dark surfaces and an off-white for large light backgrounds.
- **Do:** Store the chosen values as tokens and verify each text pairing still meets contrast minimums.
- **Avoid:** Pure #000000 text on pure #FFFFFF across large reading areas.

## COL-06. Reserve status colors for status

**Why:** If red and green appear decoratively, users misread them as errors or success.

- **Do:** Keep red for errors, green for success and amber for warnings, applied consistently across the product.
- **Do:** Pair every status color with an icon and explicit wording.
- **Avoid:** Brand or decorative elements in the error red or success green.

## COL-07. Never rely on color alone

**Why:** Color-blind users, low-vision users and anyone in bright light can miss color-only cues.

- **Do:** Add a second cue to every color-coded meaning: text, icon, shape, weight or position.
- **Do:** Keep status words inside status badges and check marks on selected items.
- **Avoid:** Red borders as the only error signal, or color-only active states and chart series.

## COL-08. Protect text placed over images

**Why:** Text over photos becomes unreadable wherever the image is bright or busy.

- **Do:** Add a scrim behind overlaid text, such as linear-gradient(to top, rgba(0,0,0,.6), transparent) across the lower third.
- **Do:** Check contrast against the lightest part of the image behind the text.
- **Do:** Put small overlays such as ratings on solid pills.
- **Avoid:** White text straight on skies, buildings or busy textures, or a text shadow as the only protection for small text.

## COL-09. Collapse near-duplicate colors into tokens

**Why:** Five grays a few RGB steps apart are values that drifted off the system; they cause inconsistency and maintenance pain.

- **Do:** Define a small set of named tokens (text-primary, text-secondary, border, surface) and reference only those.
- **Do:** Search stylesheets for raw hex values and merge near-duplicates into the nearest token.
- **Avoid:** Hard-coded one-off colors inside components.
