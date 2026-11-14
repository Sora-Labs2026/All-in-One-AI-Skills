# UI Distiller: Conversion surfaces

Read this when a page needs an interactive tool or flow that turns interest into a decision: a calculator, a comparison tool, a quiz, a configurator, a long form split into steps, a lead magnet, an upgrade prompt, a booking flow or a persuasive deck. Product guidance inside an app (onboarding wizards, tours, assistants and working indicators) is in [guided-product-surfaces.md](guided-product-surfaces.md); the page around these tools is in [landing-pages.md](landing-pages.md).

Field-level form rules live in [../../forms-conversion.md](../../forms-conversion.md) and the `FRM` rules in `../../../references/ui-rules/forms-inputs.md`. Every tactic here stays inside [../../ethical-persuasion.md](../../ethical-persuasion.md): no fake urgency, no hidden costs, no answers held hostage.

## The shared contract

Each surface below has the same three failure modes and one goal. The weak versions either **decorate** (looks like a tool, helps nobody decide), **trap** (real value held behind an email or a trick), or **dump** (everything shown, nothing recommended). The goal is a tool a stranger could use to make a decision they can defend to someone else.

Before building any of them, answer four questions in the plan:

1. **Is this the right tool?** Does the visitor actually face this calculation, comparison or choice? Would a table, a paragraph or a checklist serve as well at a tenth of the cost?
2. **What does the visitor get for free?** The answer they came for is always free and immediate.
3. **What, if anything, is worth an email?** Only additional value: a saved scenario, a formatted report, a tailored follow-up.
4. **How will it stay true?** Who updates prices, benchmarks and options, and how often. A stale tool is a false one.

Shared build rules:

- State lives in the URL where it can (`?seats=12&plan=team`) so results survive refresh, Back and sharing; persist longer inputs in `sessionStorage` and say so.
- Results update live with no submit button where computation is cheap; announce changes through one polite `role="status"` region, debounced to about 500 ms so screen readers are not flooded.
- Inputs are native controls with visible labels and units; sliders always have a paired number field and keyboard steps.
- Every number has a unit and a basis. Use `Intl.NumberFormat` for currency and locale; tabular numerals for columns.
- Mobile parity is not optional: test at 390 px with the on-screen keyboard open.
- Measure the downstream outcome (qualified leads, purchases, retained customers), not tool completions. If that data is unavailable, say so in the report rather than estimating it.

## Calculators

**Use when** the visitor's decision depends on a non-trivial calculation (five or more inputs, or branching logic) and the owner can defend the method. A calculation of "monthly cost times twelve" does not earn a tool.

**Build:**

- **Inputs:** only those that change the result. Default each to an honest, sourced baseline so the visitor gets a first result before typing anything; group them (your team, your current costs, your goals) and reveal advanced inputs on request.
- **Result:** a headline figure with units and its comparison ("About $14,200 a year less than your current setup"), a breakdown showing how it was reached, and a simple chart or before-and-after table. The result sits beside the inputs on desktop and directly below them on phones, without a scroll to find it.
- **Method:** show the formula inline or behind a "How we calculate this" disclosure, list assumptions in plain language, and cite every benchmark with source and year. Ranges are more honest than point estimates when inputs are uncertain ("between $9,800 and $16,500").
- **Value tiers:** free result, breakdown and method for everyone; an emailed or downloadable report for an email; saved and comparable scenarios over time for an account. Each tier must add something the previous one did not.
- **Edge cases:** zero, negative and very large inputs; results that favor *not* buying are shown as honestly as the rest.

**Pitfalls:** an eighteen-field form where five fields feed the math; an "efficiency score of 87" with no scale; unsourced "industry averages" flattering to the seller; units-free claims ("14x"); assumptions untouched for years.

## Comparison tools

**Use when** the visitor is choosing between known options with real differences (your plans, your product against alternatives, models in a range). If the options barely differ, write a paragraph instead.

**Build:**

- **Rows:** eight to twelve decision-relevant rows: capabilities that change the outcome, total cost including fees and add-ons, limits and capacity, service and support, risk (security, compliance, vendor stability). Delete rows where every column has a checkmark.
- **Defaults:** start with the options this audience most often weighs, including competitors where it is an alternatives page; let the visitor add or remove columns and toggle "show only differences".
- **Recommendation:** say what to choose and for whom, with reasons, conditionally where it depends ("If you need audit logs, choose Business; otherwise Team covers you"). The recommendation is visible and overridable, never baked silently into the defaults.
- **Honesty:** where a competitor wins on a row, say so; date the comparison and cite where competitor data came from.
- **Markup:** a real `<table>` with `<th scope>` headers and a caption; on phones, a sticky first column with horizontal scroll and a visible hint, or one card per option with the same row order.

**Pitfalls:** 40 rows by 5 columns; vendor-specific feature names nobody can map; costs shown but fees hidden; a "neutral" table whose axes were chosen so one column always wins.

## Quizzes and assessments

**Use when** the right answer depends on the visitor's situation and they do not yet know which option fits (unknown options, unlike a comparison). A quiz that only entertains produces traffic, not decisions.

**Build:**

- **Questions:** five to twelve, one per screen on phones, each plainly worded and each changing the result. Prefer single choice; multiple choice only when several attributes truly apply; avoid free text.
- **Scoring:** direct mapping when each answer points at one outcome; weighted points when answers contribute to several; two or three axes for genuine profiles; branching when later questions only make sense after earlier ones. Keep the scoring table in code as data, and unit-test that every outcome is reachable.
- **Outcomes:** four to eight, each meaningfully different, named so the person could describe it to a friend, and each with its own concrete next step (a plan, a resource, a path). Check the distribution with test answers: if one outcome absorbs most takers, the questions do not discriminate.
- **Result first:** show the outcome and its recommendation on screen immediately. Offer an email for a tailored report or follow-up, not as the price of seeing the result.
- **Progress:** "Question 4 of 9" in text, a Back button that keeps answers, and an exit that does not discard them.

**Pitfalls:** flattering results that apply to everyone; results with a description but no next step; an email wall after the last question.

## Configurators

**Use when** the product genuinely varies (size, materials, modules, seats, add-ons) and fixed bundles would force wrong purchases.

**Build:**

- **Start from a sensible configuration,** the most common good build, never a blank slate. Offer two or three named presets as starting points.
- **Constraints:** prevent impossible combinations before they happen (disabled options with the reason in text, not only grayed out); warn on unusual but allowed ones; when one choice requires another, add it and say so; cap at real capacity with an explanation.
- **Price:** the total is always visible (a sticky summary on desktop, a bottom bar on phones), each option shows its price delta ("+$120"), and a breakdown is one tap away. Delivery date and lead time update with the choices.
- **Preview:** when the product is visual, swap images per option and preload only the likely next view; a 3D view is an enhancement over photographs, not a replacement, and it needs a static fallback.
- **Save and share:** encode the configuration in the URL; offer save to account, emailed link, and a summary suitable for a purchase approval.
- **Cart handoff:** the cart shows the configuration, matches the price, and "Edit" returns to the configurator with state intact.

**Pitfalls:** dozens of equal options with no guidance; price revealed only at checkout; a cart line that says only the base product name.

## Multi-step forms

**Use when** the data is long or sensitive enough that one page would overwhelm (applications, quotes, intake), and the steps map to distinct units of work. Three short fields do not need steps.

**Build:**

- **Order by commitment:** identity, then situation, then need, then details, then review. Each step answers one sentence ("Tell us about your property").
- **Progress that tells the truth:** "Step 2 of 4" with step names for longer flows. If conditional logic changes the count, compute it up front or describe ranges ("about 3 minutes left"); never let "4 of 5" become "4 of 7".
- **Validation:** required fields per step on Next, the rest on blur and again on submit; specific messages next to the field; move focus to the first error and announce the count of errors.
- **Keep everything:** Back never loses input; refresh restores from storage; long forms offer save and resume by email link, saying what is stored, for how long, and who can see it.
- **Spam defense in layers,** least friction first: a honeypot field hidden from people and assistive technology, a minimum fill time of about 3 seconds, server rate limits, content filtering, and an invisible challenge that escalates to a visible one only when risk is high. A visible puzzle as the only defense costs real people.
- **Submission:** a review step for consequential forms, a confirmation that says what happens next and when, and a confirmation email for anything that creates an obligation.
- **Measure** the drop-off per step from launch: abandonment at the first field means the value is unclear; mid-form means a step is too long or too personal; at submit means anxiety about what happens next.

**Pitfalls:** one field per step to look short; thirty fields spread across five steps; marketing consent pre-ticked or bundled with terms; date pickers worse than the native input.

## Lead magnets

**Use when** the audience has a specific, immediate problem the owner can solve in a usable artifact, and there is a relevant follow-up to offer. A magnet is worth building only if it would be worth paying for.

- **Format by need:** a template when they must produce something; a checklist when the gap is completeness; a short course when the skill needs sequence; a calculator or quiz (above) when the answer depends on their numbers; a long guide only for complex research decisions.
- **Title:** a specific outcome for a specific audience, which also filters out the wrong audience. The page shows what is inside (a preview page, the table of contents, the length or time required).
- **Form:** email only, with the consent text naming exactly what they will receive and how often; separate, unticked consent for anything broader.
- **Delivery:** immediately, on screen and by email; never "we will be in touch".
- **Follow-up:** a first week that helps them use the resource, then one relevant offer; unsubscribing is one click.
- **Quality gates:** a template yields a usable result in under 30 minutes; every checklist item is actionable today; each course lesson stands alone.

## Upgrade flows and paywalls

**Use when** a free tier or trial must convert to paid. The aim is to ask at the moment the visitor has felt the value, never before.

- **Trigger moments:** a usage or capacity limit reached, an advanced feature attempted, a successful outcome the paid plan would repeat, inviting teammates, a trial nearing its end. Not on first login, not as a banner on every screen.
- **Match intensity to trigger:** a hard limit or gated feature may use a dialog; softer prompts sit inline where the trigger happened; a passing notice may be a toast with a link.
- **Copy ties to what they just did:** "You have run 50 reports this month. Team removes the limit and adds shared folders." Price, period, trial length and cancellation terms sit beside the button (`SCR-17`).
- **Close and decline** are always visible and keyboard reachable; declining returns the user to their work with nothing lost. A smaller plan or monthly billing may be offered once, framed as fit ("If Team is more than you need..."), with the cost difference stated.
- **Win-back** after cancellation is one honest message with what changed, and returning users find their data intact where the terms allow.
- **Cancellation** is as easy as signing up, without confirm-shaming copy.

**Pitfalls:** a paywall before any value; a close button that appears after a delay; countdowns that reset; "free" trials that require a card without saying when it will be charged.

## Booking and appointment flows

**Use when** the visitor reserves a time with a person, place or resource.

- **Order:** service, then location, then practitioner (or "any"), then time, then details, then confirm. Keep every choice visible in a summary through the whole flow.
- **Availability** comes from the server and is re-checked at confirm. Never claim a slot before the server confirms it; if it was taken meanwhile, keep the details, explain, and offer the nearest alternatives.
- **Time slots** are buttons in a labeled group, with the time zone stated when visitors may be elsewhere; days with no availability are skipped or marked, not silently empty.
- **States to design:** loading, no availability, stale slot, invalid details, payment failure, retry, success, reschedule and cancel (with the policy and any fee stated before confirming).
- **Confirmation:** service, place, address, person, date and time with time zone, price, how to reschedule, an add-to-calendar file, and a confirmation email.
- Use native inputs where possible; return focus to the right field after an error; preserve selections across Back and recoverable failures.

## Persuasive decks

Mechanics (fixed canvas, scaling, notes, export) are in [../../creative-media/references/html-slide-decks.md](../../creative-media/references/html-slide-decks.md) and [../../creative-media/references/revealjs-presentations.md](../../creative-media/references/revealjs-presentations.md). The narrative choices:

| Goal | Arc (one idea per slide) |
|---|---|
| Raise early funding | Problem, insight, product, evidence of demand, market, business model, team, the ask |
| Win a deal | Their situation, cost of doing nothing, the approach, proof from a similar customer, differences, price and return, objections, next step |
| Demo a product | The job, the product doing it live, three capabilities, what it costs, how to start |
| Report to leadership | Headline result, what moved and why, risks, decisions needed |

- The slide title is the claim ("Support tickets fell 38% after onboarding changes"), not the topic ("Support").
- Alternate between how things are and how they could be when persuading; end on the specific decision or action requested.
- One chart per slide, annotated with the point it proves; keep the type floors in `html-slide-decks.md` (36-40 px body on a 1920 x 1080 canvas) and split a slide rather than shrink it.
- Reveal builds only when sequence aids understanding; reduced motion shows the final state.
- Numbers on slides follow the same sourcing rules as landing pages.

## Accessibility and reduced motion for all surfaces

- Every control is reachable and operable by keyboard in a logical order; focus is visible and never trapped except in true dialogs.
- Each step or result change moves focus to the new heading or announces it in a polite status region, not both.
- Error messages are tied to their fields with `aria-describedby`; error summaries list and link each problem.
- Color is never the only signal (selected options, recommended plans, disabled choices all carry text or shape).
- Live price or result changes animate only opacity or a short number transition (under 300 ms); under `prefers-reduced-motion` they change instantly.
- Contrast is measured at 4.5:1 for text and 3:1 for control boundaries and focus indicators.

## Done when

- [ ] The plan answers the four shared questions, and the tool beats a simpler format for this audience.
- [ ] The answer the visitor came for is free and immediate; anything gated is additional value, and consent is explicit.
- [ ] Every figure has a unit, a basis and a source; the method or scoring is inspectable.
- [ ] State survives refresh and Back; results and price update live and are announced once.
- [ ] Keyboard, screen reader, 390 px with the on-screen keyboard, and reduced motion were tested.
- [ ] No pattern listed in [../../ethical-persuasion.md](../../ethical-persuasion.md) remains; an owner is named for keeping prices, options and benchmarks current.
- [ ] Downstream outcomes are instrumented, or the gap is stated in the report.
