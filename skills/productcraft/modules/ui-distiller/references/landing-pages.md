# UI Distiller: Landing pages

Read this when building, rewriting or auditing a marketing page whose job is to move one kind of visitor to one action: a product page, a pricing page, a launch page, a studio or service site. It covers the brief, the page plan for each kind of business, the hero, proof, pricing, copy, art direction and motion budget, a redesign audit, and the search hooks.

It assumes the rules already in [taste.md](taste.md) (detectors 13-19 and 29-33 are the landing-page ones), the section order `SCR-22` and the hero rules `SCR-11` in `../../../references/ui-rules/screen-patterns.md`, and the honesty rules in [../../ethical-persuasion.md](../../ethical-persuasion.md). Interactive tools that sit on a landing page (calculators, comparisons, quizzes, configurators, multi-step forms) are in [conversion-surfaces.md](conversion-surfaces.md).

## When a landing page is the right surface

- **Fits:** one offer, one audience, one primary action (start a trial, book a call, reserve a table, join a waitlist, buy). Paid or campaign traffic that arrives with one question. A launch that needs a single place to point at.
- **Does not fit:** a site that must serve many intents at once (that is a homepage with routes, not a landing page); a logged-in product screen (use the operational rules in `../GUIDE.md`); a help article (that is documentation, and a hero would only delay the answer).
- A homepage can borrow the structure below, but give it a router role: the hero states the category and the audience, then the next screen sends each audience to its own page.

## 1. Brief before pixels

Collect these in one batch. Ask only for what is missing; if the owner cannot answer, write the assumption in one line at the top of the plan and continue.

| Area | What to pin down |
|---|---|
| Action | The one primary action and what counts as a conversion (click, signup, paid order, booked slot) |
| Offer | Exactly what the visitor gets, at what price or commitment, with which limits |
| Audience | Who buys, the problem in their words, what they already know when they land |
| Traffic | Ads, search, email, social, partner; the promise made on the page that sent them |
| Objections | The three reasons they do not act today (price, risk, effort, trust, fit) |
| Evidence | Real product, screens, photographs, figures with source and date, quotes with permission |
| Constraints | Brand assets, voice, legal wording, regions, languages, accessibility commitments |

When the page is for a named product, release or version, confirm the current facts (what exists, what it costs, what version ships) from official sources before designing; stale or guessed facts are the most expensive error to find late.

Write a **fact sheet** of three to six statements only this product can make (see "Before styling" in [taste.md](taste.md)). Every headline and section later draws from it. If the sheet stays empty, the page will be generic whatever its styling.

## 2. Plan the page as claims, then as screens

Outline the page as the beliefs a visitor must reach, in the order they ask, each paired with its evidence. A section with no claim is cut. Then convert the outline into screens: at a 1440 x 900 desktop viewport each section should read as one or two screens, and the first screen holds the hero alone, with a hint of the next section only if it invites scrolling.

A dependable default argument (adapt, do not stamp):

1. **Hero:** what it is, for whom, one concrete outcome, the primary action, the product itself.
2. **The friction:** one section that names the problem as the visitor experiences it, with a measurable cost where one exists.
3. **The mechanism:** how it works in three or four steps, shown with the real interface or the real process.
4. **Outcomes:** three to five benefits, each a claim with its proof beside it, not a grid of icon cards.
5. **Proof:** verified quotes, case results with scope and date, ratings with their scale and count.
6. **Price and risk:** price or "from" price, what is included, the risk reversal (trial, cancel anytime, refund terms) stated plainly.
7. **Objections:** a short FAQ answering the real reasons people hesitate; move it higher for high-friction offers.
8. **Close:** the same primary action as the hero, restated with what happens next.

Pick one layout type deliberately and say why in the plan: **classic** (product understood from one view), **long-form argument** (skeptical buyers, a new category, a high price), **minimal** (warm traffic such as an email to existing users, or a single download), **alternatives page** (visitors searching for options; pair it with the comparison rules in [conversion-surfaces.md](conversion-surfaces.md)).

## 3. Page plans by kind of business

The kind of business decides what leads. Write the kind on the first line of the plan.

**Software or AI product (show the mechanism).** The hero carries the product doing one complete job: live HTML of the real interface with believable data, or a deterministic replay labeled "Sample workflow". Model the demo as explicit states (input, processing, draft, edit, approval, published, plus quota, error and retry) so it can be paused and read. Give the product panel more density than the marketing copy around it. Keep pricing limits, usage units and overage terms in one continuous decision path, with ambiguous plan terms linking to their FAQ answer. Never fake generation speed, output quality or typing.

**Automation, security or operations product for enterprises (show the boundary).** Buyers need its scope, its limits, the human sign-off points and the recovery path laid out plainly. Present each capability as a row that expands to the same fields: trigger, permissions, action, approval, output, audit record, exception path, rollback. Use only verified metrics with scope, source and time frame. Put security and governance before the conversion ask, connect each control to the risk it reduces, and never show a compliance badge the owner cannot evidence. The final action qualifies (who it is for, what happens after submitting, who receives the request, how the data is used). Avoid glowing spheres, particle clouds and "magic" copy; they signal the opposite of control. These pages follow `SCR-28` for how automated decisions are explained.

**Physical product.** Photographs lead: the product large and whole in its own frame, a different view in each section, every promise in the headline pictured (if the copy says it folds, show it folded). A color swatch changes the picture. No product shown twice from the same angle, no fact repeated. Reach for a 3D render only if the brief calls for one.

**Service with appointments (salon, clinic, studio, repair, hospitality).** Browsing should feel calm and the booking should be bulletproof. Lead with one strong photograph of the place or the practitioner at work and a short statement of craft. Present services in one stable stage: a tab list or list of services on one side, a reserved media area on the other, with duration, price and a book link in the DOM for every service (no hover-only previews). Show address, hours, accessibility of the premises and contact before the booking step. The booking flow is in [conversion-surfaces.md](conversion-surfaces.md#booking-and-appointment-flows).

**A place people visit (cafe, shop, gym, guesthouse).** Photographs carry the page: twelve to twenty real frames for a full page, fewer for a short one. Put the visit block (address, hours, directions, phone) on the second screen, not only in the footer. Flat backgrounds, square photo crops, one button style; no shader effects or decorative loops. When hours or prices are not supplied, mark them as placeholders for the owner rather than inventing them.

**Creative studio, agency or portfolio (let the work lead).** Open with one strong piece of work and a positioning line, then go straight into selected projects; explain the studio only after the work has earned attention. Treat each case study as a chapter with its own muted color field or a hard black-to-white cut, title, role, year and action visible without hover. Services can be set as oversized type that hands off to a decisive contact chapter. Documentary variants use billboard-scale condensed type, exposed grid lines, square corners and irregular photo collages whose DOM order still follows the story. Brutalism here means hard contrast and visible structure, never random misalignment or failing contrast.

**Technical product told editorially.** Asymmetric columns, one large display headline beside compact supporting copy, a full-width media band that crosses the grid, thin rules and small monospaced labels for steps, timestamps and counts, one accent reserved for active state and key numbers. Keep it between a magazine and a product interface: drop the sci-fi chrome, keep the precision.

## 4. The hero

- **Headline:** four to eight words, at most two lines at 390 px and 1440 px, naming the category or the outcome and the buyer. Edit the words before shrinking the type; apply `text-wrap: balance`.
- **Supporting line:** one or two sentences: what it is, who it is for, the "how".
- **One primary action** whose label is a verb plus an object ("Start a 14-day trial", "Book a fitting"). A secondary path is a text link, not a second filled button.
- **One hard fact** on the first screen: a price, a time saved with its basis, a capacity, a location.
- **The dominant visual** shows the real thing. Keep text on calm image areas; check contrast at every breakpoint where the crop changes.
- **Message match:** if the visitor came from an ad or email, the hero repeats that promise in the same words and visual tone.
- On phones, stack headline, line, action, then visual; the primary action must sit in the first screen at 390 x 844.

## 5. Proof that survives scrutiny

- Put each piece of proof next to the claim it supports, not in a separate testimonials band at the bottom.
- A quote needs a real person, role and organization with permission; a result needs its scope, period and baseline ("median close time fell from 9 to 4 days across 31 teams, Jan-Jun"). Ratings carry scale and count.
- Logo rows only for customers who agreed to be named. With no verified proof, the product shown working is the proof (`SCR-11`, detector 31 in [taste.md](taste.md)).
- Use photographs for people, never generated faces presented as customers or staff, and never initials-in-circles posing as people.
- Missing facts become visible placeholders for the owner (`[customer quote pending approval]`), never invented values.

## 6. Pricing pages

The job is to reduce uncertainty, not to display numbers.

- **Plans:** two or three for most products, one marked "Recommended" with a reason in one line ("For teams of 3-20"). The emphasis is a tinted surface or border, not a badge that shouts.
- **Value metric:** one unit used everywhere (per seat, per 1,000 runs, per location). Never switch units mid-page.
- **Period toggle:** a real radio group or segmented control, keyboard operable, defaulting to the period most buyers choose. The annual saving is computed from the displayed prices (annual against twelve times monthly, rounded down) and the amount per charge is shown ("$480 billed yearly").
- **Per plan:** who it is for, three to six limits that actually change the decision, three to six inclusions, one action with a consistent verb across plans.
- **Comparison matrix** below, grouped (core, collaboration, administration and security, support), showing only rows that differ; on phones it becomes one card per plan or a table with a sticky first column and a visible scroll hint.
- **Usage pricing:** a slider or stepper with a sensible default near the median customer, the math visible beside it.
- **Enterprise:** procurement reassurance (security review, invoicing, data residency, response time for sales) instead of "Contact us" for everything.
- **FAQ:** cancellation, what happens at a limit, refunds, trial length, what counts as a seat, discounts for education or nonprofits.
- Fees, taxes and renewals follow `SCR-15` and `SCR-17`; no surprise costs at checkout.

## 7. Copy

- Specific beats clever: "Cut weekly reporting from four hours to fifteen minutes" over "Streamline your reporting".
- Every heading contains a noun the visitor cares about. Every button is a verb and an object. No "Learn more", "Submit", "Get started" when a precise label exists (`COP-01`).
- Feature bullets lead with the outcome, then the detail: **Fewer handoffs**: drafts go straight to the reviewer with comments attached.
- Keep tech pages around 60-80 words of prose per screen outside interface mockups; place pages fewer.
- Read every headline and button aloud; strike any line a competitor could print unchanged (detector 29 in [taste.md](taste.md)).
- Write all copy before laying out the page. Layout built around placeholder text hides the fact that the argument is missing.

## 8. Art direction and the motion budget

Choose a direction from [style-catalog.md](style-catalog.md) and write a one-paragraph visual thesis: type pairing, two background tones, one accent and its roles, radius tier, image treatment, and the one committed move. Then set a motion tier before writing any animation:

| Tier | What it allows | Typical page |
|---|---|---|
| Still | Hover, press and focus feedback only; one load entrance for the hero | Pricing, booking, documentation-led products |
| Fluid | Section reveals (rise 16-32 px and fade over 500-700 ms, once), shallow parallax under 5% of travel, navigation that condenses on scroll | Most product and studio pages |
| Immersive | Pinned or scrubbed sequences, a canvas or WebGL scene, cursor-aware effects | Launches and campaigns where the experience is the message |

Rules that hold at every tier:

- **Budget the memorable moments.** One in the hero, at most one or two more on a long page (a type moment, a photo sequence, an interactive demo). Everything else stays quiet. A page where every section performs has no peak.
- **One smooth-scroll engine at most**, and none unless a pinned or scrubbed sequence needs it. With GSAP ScrollTrigger and Lenis, connect them once and refresh measurements after fonts and images load. At most two pinned sections per page.
- **One canvas or WebGL scene per page**, paused by IntersectionObserver when offscreen and when the tab is hidden, device pixel ratio capped at 1.5-2, a static poster image painted first, and the whole scene replaced by the poster under reduced motion, on context loss or without WebGL. Pick one lane: a subtle depth field (safe for conversion), a data or particle field that shows system behavior (technical products), one hero object (hardware, launches), or a full scene with chapters (campaigns only, with a mobile fallback). On pricing and high-intent pages, WebGL is decoration at most.
- **Control feedback 150-220 ms; entrances 400-700 ms; staggers 40-70 ms between siblings**, decelerating curves such as `cubic-bezier(0.22, 1, 0.36, 1)`. Animate `transform` and `opacity` only. More numbers: [motion-engineering.md](motion-engineering.md) and [generic-tells-and-fixes.md](generic-tells-and-fixes.md).
- **Split-text reveals** keep the unsplit text as the accessible name, hide decorative word spans with `aria-hidden`, never split links or inline markup, and leave the text visible without JavaScript.
- **Reduced motion** renders final states immediately: no smooth scrolling, no scrub, no parallax, no word-by-word reveals; color and opacity changes may remain.
- **Pointer effects are additive.** Throttle `pointermove` through `requestAnimationFrame`; nothing important depends on hover; touch and keyboard reach every state.
- **Imagery:** real or licensed photographs and the real product first; generated imagery only as illustration, following [../../creative-media/references/generation-prompting.md](../../creative-media/references/generation-prompting.md), and never presented as the actual product, premises, staff or customers.

## 9. Spec first, then build section by section

For new pages, and whenever an AI generator does the drafting:

1. **Write a design spec** before code: visual thesis, color roles with values, type scale, component styles (buttons, cards, navigation, links, tags), layout grid and margins, depth rules, motion tier with durations, responsive behavior, and a short do and do-not list. Get it approved, then treat it as the contract.
2. **Master plus overrides.** One master spec holds the system; a page file overrides only what that page needs (a denser pricing table, a darker campaign hero). When building a page, read the override first, then the master.
3. **Three dials** make the brief concrete: *variance* (centered and calm to asymmetric and bold), *motion* (the tier above), *density* (spacious marketing spacing of 24-96 px between groups to dense product spacing of 8-32 px).
4. **Build in order:** hero, mechanism, outcomes, proof, price and objections, close. Lock the hero before moving on, and change one variable at a time when exploring (crop, accent, arrangement, background tone), stating "keep everything else unchanged" when prompting a generator.
5. **Show options when the direction is open:** three directions drawn from genuinely different families in [style-catalog.md](style-catalog.md), each as a quick hero sketch side by side, then commit to one.
6. **Reference pages are evidence of taste, not templates.** Take only high-level traits (hierarchy, pacing, contrast, crop style, motion character) and replace every name, word, figure, price, person and image with the owner's own. When producing several pages from several references, give each a distinct identity and check that no two read as color swaps of one another.
7. **Generated text in images is fragile:** reserve a clean area in the image and set the words as live text.

**Stack notes.** With Tailwind CSS, define color, radius and spacing as CSS variables in the theme so the master spec is the single source; with shadcn/ui, use its accordion for the FAQ, tabs for audience or service switches and dialog only for true modals, and keep their keyboard behavior intact. A self-contained page that must ship as one file can be built with React and bundled so scripts and styles are inlined; keep it under a few hundred kilobytes, lazy-load media, and test it opened from disk. Variant previews for an owner work best as one page with a toggle panel rather than several near-identical files.

## 10. Redesigning an existing page

Audit first, change surgically, keep everything that works.

1. **Scan:** framework, styling method, real tokens in use, components, routes, forms, analytics hooks, every state that exists today. List what must not change.
2. **Diagnose:** run `scripts/tell_scan.py`, `scripts/token_inventory.py` and `scripts/landing_check.py`, plus the measurement snippet in [taste.md](taste.md). Produce a findings table ranked by impact on the visitor's decision, each with evidence.
3. **Direct:** pick one direction that fits the brand; write the thesis.
4. **Apply in order:** tokens, then type and spacing, then component states, then layout of sections, then motion. Do not change URLs, data flow or semantic structure except to fix accessibility.
5. **Unify:** every page consumes one shared token theme; a redesign that leaves pages on different palettes has failed.
6. **Verify:** re-run the scans and compare counts before and after, smoke-test every previously working flow, check dark mode and phone widths.

## 11. Search and sharing hooks

Search work belongs to the `search-visibility` module; the landing page only needs to set it up correctly.

- **Index or not:** campaign-only pages, time-boxed offers and ad variants get `noindex`; evergreen offers that match a real search get indexed with a unique title and description, a canonical URL, and internal links from the homepage and feature pages. See [crawl-and-index-controls.md](../../search-visibility/references/crawl-and-index-controls.md) and [on-page-elements.md](../../search-visibility/references/on-page-elements.md).
- **FAQ:** write it in plain question-and-answer form for people and answer engines ([ai-answer-engines.md](../../search-visibility/references/ai-answer-engines.md)). FAQ structured data no longer produces rich results in the main search engine; see [structured-data-and-social-cards.md](../../search-visibility/references/structured-data-and-social-cards.md) before adding markup.
- **Sharing:** `og:title`, `og:description`, a 1200 x 630 `og:image` that is the real hero, `theme-color`, a favicon.
- **Speed:** largest contentful paint under 2.5 s, layout shift under 0.1 and interaction to next paint under 200 ms at the 75th percentile; reserve every media box with `width` and `height` or `aspect-ratio`, preload only the hero image, and lazy-load the rest.

## 12. Ship checklist

Skip link to `main`; landmarks (`header`, `nav`, `main`, `footer`); one `h1`; alt text on meaningful images and empty alt on decorative ones; visible focus; contrast measured at 4.5:1 for text and 3:1 for large text and interface parts, including text over imagery and through every color change; no horizontal scroll at 320 px and at 200% zoom; tap targets at least 44 x 44 px; current page shown in navigation; no link to `#`; privacy and terms links; a helpful 404; consent banner where the jurisdiction requires it; forms with labels, validation and success states ([../../forms-conversion.md](../../forms-conversion.md)); loading, empty and error states for any live element.

`scripts/landing_check.py <page.html>` checks the parts of this list that are visible in markup: a single `h1`, headline length, vague button labels, missing alt or dimensions on images, skip link and `main`, description and sharing tags, a robots `noindex` left on, autoplaying video without `muted` and `playsinline`, links to `#`, and whether any reduced-motion rule exists when animation is present. Exit 0 means nothing to review, 1 findings, 2 usage error.

## Pitfalls

- Two filled buttons of equal weight in the hero; a navigation bar with eight links on a single-offer page.
- Proof collected at the bottom where nobody deciding will see it.
- Every section the same split layout; every benefit an icon card.
- A demo that loops faster than anyone can read, or that cannot be paused.
- Motion that hides content until a script fires; a preloader on a page that has already loaded.
- WebGL that stutters on a mid-range phone and drags the hero's text contrast below 4.5:1 as it moves.
- Pricing "from" a figure no plan actually costs; annual savings computed against an inflated monthly price.
- Invented customers, results, awards or badges; claiming industry recognition without evidence.

## Done when

- [ ] The plan names the kind of business, the one action, the motion tier and the memorable moments, and each section carries one claim with its evidence.
- [ ] The hero passes the swap test in [taste.md](taste.md) and shows the real product or place.
- [ ] Every figure, quote, logo and badge is real and sourced, or a visible placeholder for the owner.
- [ ] `landing_check.py`, `tell_scan.py` and the measurement snippet were run, with findings fixed or given a written reason.
- [ ] Contrast was measured over imagery and animated backgrounds; reduced motion renders final states; keyboard reaches every control.
- [ ] Index or `noindex` was decided deliberately and the sharing tags show the real hero.
- [ ] Checked at 390, 768, 1024 and 1440 px and at 200% zoom.
