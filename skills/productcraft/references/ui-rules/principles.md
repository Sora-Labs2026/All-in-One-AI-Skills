# UI rules: UX principles

Decision load, memory, conventions and perceived quality. Rule IDs use the `PRN-` prefix; cite them in change reports.

## PRN-01. Offer fewer, clearer choices

**Why:** Decision time grows with the number and similarity of options.

- **Do:** Show only the options most users need at each step and move the rest behind "More" or "Advanced".
- **Do:** Mark a recommended default and give options short distinguishing subtitles.
- **Do:** Collapse fine-grained ranges into a few buckets that place every possible value in exactly one: 0-1, 2-3, 4-5, 6+ for whole numbers, half-open wording for continuous quantities ("Less than 1 year", "1 to under 3 years", "3 years or more").
- **Avoid:** Long flat lists of near-identical options, or every setting on the first screen.
- **Avoid:** Ranges that share endpoints (1-3, 3-5), or integer ranges for values that can fall between them.

## PRN-02. Put key items first and last

**Why:** People remember the first and last items of a sequence best; the middle is the weakest spot.

- **Do:** Lead lists, onboarding and landing sections with the strongest benefit or most-used item.
- **Do:** Place the most important action at the end of a sequence.
- **Avoid:** Burying essential information or actions in the middle of a long list.

## PRN-03. Chunk information without hard caps

**Why:** Grouped information is easier to scan and remember than one undivided mass.

- **Do:** Group related items under headings or spacing, keeping each visible group small.
- **Do:** Format long values in chunks (card numbers 4-4-4-4, phone numbers by local convention).
- **Do:** Reveal further items on demand.
- **Avoid:** Sixteen or more equally weighted items in one grid with no grouping.
- **Note:** The "seven plus or minus two" figure describes short-term recall, not a hard limit on menu or navigation length.

## PRN-04. Prefer conventions over trends

**Why:** Trendy effects date quickly and often add noise; standard patterns stay clear and familiar.

- **Do:** Default to solid single-color primary buttons, standard navigation placement and platform conventions.
- **Do:** Express personality through one or two restrained touches such as an accent color or illustration.
- **Do:** Before shipping, check for dated defaults (violet-indigo gradients, gradient headline text, glass cards over busy backgrounds, glowing buttons, emoji as icons (ICO-12), near-black pages with one neon accent, the same radius and shadow on every element regardless of size or elevation) and keep one only with a brand reason you can state.
- **Avoid:** Multi-color gradient buttons or extra floating controls added only for flair.

## PRN-05. Polish shapes perceived usability

**Why:** People perceive well-crafted interfaces as easier to use and forgive small issues in them.

- **Do:** Keep typography, spacing, color and corner radius consistent and deliberate on every screen.
- **Do:** Still test the flow itself, because polish can hide real usability problems.
- **Avoid:** Treating visual consistency as optional or "later".

## PRN-06. Give enough detail; avoid over-minimal UI

**Why:** Stripping supporting details in the name of minimalism leaves users guessing about state and size.

- **Do:** Show useful metadata under item titles (file size, date, episode number).
- **Do:** Label progress bars with a value and give in-progress tasks a cancel control.
- **Do:** Label ambiguous numbers ("Episode 3", not "#3").
- **Avoid:** Removing information that helps users decide.
