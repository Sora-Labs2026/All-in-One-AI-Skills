# UI Distiller: Guided product surfaces

Read this when a product must teach, guide or reassure people while they use it: a first-run onboarding wizard, in-product tours and hints, a website chatbot or assistant flow, and the indicators that show an AI or background agent is working. Marketing-side tools (calculators, quizzes, upgrade prompts) are in [conversion-surfaces.md](conversion-surfaces.md).

Screen rules that already apply: `SCR-08`, `SCR-09` and `SCR-14` (onboarding), `SCR-24` and `SCR-26` (assistant surfaces and generated output) in `../../../references/ui-rules/screen-patterns.md`, and patterns 19, 23 and 56 in `../../../references/pattern-library.md`. The honesty rules in [../../ethical-persuasion.md](../../ethical-persuasion.md) cover streaks, nudges and fake typing.

## Onboarding wizards

**Fits** when the product cannot work until something is set up (connect a data source, import contacts, choose a workspace type), or when two or three answers change what the user sees first. **Does not fit** when the product is usable immediately; then an empty state with one clear first action and contextual hints beats any wizard.

**Find the first moment of value first.** Name the single action after which a new user understands why the product is worth returning to: first report run on their own data, first message answered, first file shared and opened by a teammate. Every wizard step either moves toward that moment or is deferred.

**Step plan** (cut any that does not serve the moment):

1. Optional welcome with what the setup will do and how long it takes ("3 steps, about 2 minutes").
2. One to three questions that change the first screen (role, use case, team size), one per screen, with a skip and sensible defaults (`SCR-08`, `SCR-09`).
3. The critical setup step, with the easiest path first (sample data or a one-click import) and the full path second.
4. The first real action, completed inside the wizard or on the real screen with a pointer to it.
5. A short recap: what was set up, what was deferred and where to finish it.

**Mechanics:**

- Layout per `SCR-14`: Back at top left, Skip at top right on optional steps, "Step 2 of 4" as text, one primary button fixed in the same place.
- **Skip leaves a usable product**, never an empty one: load sample content clearly labeled as sample, or pre-fill defaults the user can change; queue skipped steps as a dismissible "Finish setup (2 left)" item that tracks real completion.
- **Resume** where the user left off on the next visit; if they complete a step elsewhere in the product, mark it done instead of asking again.
- **Branch sparingly:** two or three variants by role or size are maintainable; more become untestable.
- **Account creation** waits until saving or sharing needs it when the product allows.
- Never use the wizard for upsell; pricing belongs to [conversion-surfaces.md](conversion-surfaces.md#upgrade-flows-and-paywalls).

**Measure** completion per step, time to the first moment of value, and return within 7 days, not wizard completion alone. Skipping everything is a signal the wizard did not earn its time.

**Celebrations:** a short confirmation when the first real result appears (under one second, no blocking overlay, reduced motion shows a static check). Confetti over a half-finished setup misstates progress.

## Product tours, hints and contextual help

**Fits** when people miss capabilities that would help them, at the moment they meet them. **Does not fit** as a single tour on first login that walks through every button; people skip it and the help is gone when they need it.

**Prefer a library of small, contextual hints** over one long tour. Each hint is tied to one feature and fires on a trigger:

| Trigger | Example |
|---|---|
| Event | First time the user opens the export panel |
| State | A dataset grows past the size where filters matter; the user has never used filters |
| Time | Return after 30 or more days away, for features that changed meanwhile |
| Friction | Three failed attempts at the same action, or an error the help addresses |

**Placement, least intrusive first:** inline help text or an empty-state tip; a popover anchored to the element; a side panel that stays open while the user works; a spotlight overlay only for one critical step in a short sequence.

**Mechanics:**

- At most one hint visible at a time and a daily cap per user (for example two). No pulsing dots on many elements at once; people stop seeing them.
- Popovers anchor to their element, flip at viewport edges, stay within the safe area on phones, and never cover the control they describe.
- Dismiss with a close button and Escape; clicking elsewhere closes non-blocking hints. Never auto-dismiss text before it can be read (allow at least 1 second per 10 words, and pause on hover or focus).
- A dismissed or completed hint does not return unless the feature meaningfully changes. Store state per user on the server so it follows them across devices.
- Offer a permanent way back: a help menu listing available walkthroughs, and a setting to turn hints off.
- Power users who already use a feature never see its introduction; check usage before firing.
- Steps in a spotlight sequence say "2 of 4", support Back, and end when the user does the real action, not when they click Next.

**Accessibility:** a hint that opens on its own must not steal focus from typing; announce it politely and let the user reach it with a shortcut or by tabbing. A spotlight overlay is a modal dialog: trap focus inside it, restore focus on close, and label it. Overlays respect reduced motion (appear without scaling or sliding).

**Measure** adoption of the feature the hint teaches, not hint views or "completed" clicks.

## Chatbot and assistant flows on websites

**Fits** when visitors ask the same questions repeatedly, answers exist in maintained sources (documentation, pricing, policies), someone owns keeping those sources current, and there is a human path for what the bot cannot do. **Does not fit** sensitive conversations, complex sales or troubleshooting that people expect from a person, or a team that cannot maintain it.

Avoid both extremes: rigid scripted trees that break on any unexpected phrasing, and open-ended model replies with no grounding that state prices and policies with false confidence. Design a guided conversation:

- **Scope:** a written list of intents the assistant handles (pricing questions, plan comparison, integration questions, order status, booking, handoff to sales or support), grouped into a small hierarchy, with explicit out-of-scope topics. Aim to cover most real conversations, not all of them.
- **Grounding:** answers come from retrieved, current sources, and the reply links the source it used ("From the pricing page, updated 3 Nov"). If retrieval finds nothing relevant, the assistant says so instead of improvising.
- **Opening:** say what it can help with in one line and offer two to four starting options as buttons; also accept free text.
- **Clarify once,** then offer choices ("Do you mean billing or plan limits?"), then hand off. Never loop people through repeated clarifications.
- **Handoff to a person** when asked (any phrasing of "talk to a human" works immediately), after two failed attempts, on signs of frustration, and for high-stakes topics (cancellation, complaints, security, health or money decisions). Pass the transcript and detected intent so nobody has to repeat themselves, and state the expected wait or the hours when people are available.
- **Context:** keep earlier turns in the same session; let the user restart or clear the conversation.
- **Voice:** the brand's tone, plainly worded, never pretending to be a person; label it as an automated assistant.

**Interface:** the conversation is a `log` region; each new reply is announced once when complete, not token by token. A visible Stop control keeps partial output (`SCR-26`). Quick-reply buttons are real buttons and remain in the transcript as the user's answer. The launcher does not cover page content or the main action on phones and can be closed for the session. Do not auto-open with a sound or a bouncing badge.

**Measure** per intent: how often it is recognized, resolved without handoff, sent to fallback, and escalated. High fallback means missing intents; low resolution means weak sources; high escalation in one intent may mean it should go to people by design.

## Working and status indicators for AI and agents

Show that work is happening, what kind, and what the user can do meanwhile. The indicator supports the state; the state itself is always in text.

**Name the real phase.** Map the system's actual lifecycle to a few honest labels and change the label only when the phase changes:

| Phase in the system | Label | Visual |
|---|---|---|
| Retrieval, search, file lookup | "Searching project files" | Indeterminate indicator |
| Reasoning, planning, analysis | "Working through the plan" | Indeterminate indicator |
| Writing a reply | "Writing" (then the streamed text itself) | Stream replaces indicator |
| Producing an image or layout | "Generating 4 options" | Placeholder frames of the final size |
| Listening for speech | "Listening" | Input level meter driven by real audio |
| Waiting for the user's approval | "Waiting for your approval" | Static; no animation |
| Long job with measurable steps | "Step 3 of 7: running tests" | Determinate progress |

- Use determinate progress whenever the system knows the fraction; an endless animation for a measurable job hides information.
- Avoid flicker: do not show an indicator for work that finishes in about 150 ms; once shown, keep it at least 400-600 ms.
- Remove the indicator on done, error or cancel, and show the result, the error with Retry, or the cancelled state. A spinner left running after failure is a lie.
- Keep Stop or Cancel reachable while working; long tasks show elapsed time and allow leaving the screen with a notification on completion.
- Never invent activity: no fake typing delays, no rotating "thinking" phrases that do not reflect real phases (pattern 9 in `../../../references/pattern-library.md`).

**Announce once:** put the label in a `role="status"` region (polite), and hide the decorative animation from assistive technology. Do not also give the animation its own label, or the state is read twice.

```html
<div class="agent-status" role="status">
  <span class="orb" aria-hidden="true"></span>
  <span>Searching project files</span>
  <button type="button">Stop</button>
</div>
```

**Activity orbs and dot fields.** A small canvas or CSS animation beside the label works at two fixed sizes: about 16-20 px inline with text and 48-64 px as the main visual of an empty conversation. Design each size separately rather than scaling one. Use one ink color tuned to the surface it sits on and measure 3:1 against that surface. For canvas, cap device pixel ratio at 2, run one `requestAnimationFrame` loop per visible instance, pause when offscreen (IntersectionObserver) or the tab is hidden, and draw one static frame under reduced motion. Do not enlarge the orb into a floating mascot that covers data (`SCR-24`).

**Edge glow on a busy surface.** A light traveling around a card's border can mark the one panel that is working or newly selected. Build it in CSS: a rotating conic gradient masked to the border ring.

```css
@property --beam-angle { syntax: "<angle>"; inherits: false; initial-value: 0deg; }
.beam { position: relative; border-radius: 12px; }
.beam::before {
  content: ""; position: absolute; inset: 0; padding: 1.5px; border-radius: inherit;
  background: conic-gradient(from var(--beam-angle), transparent 0 75%, var(--accent) 90%, transparent);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); mask-composite: exclude;
  pointer-events: none; opacity: 0; transition: opacity 400ms ease-out;
}
.beam[data-active="true"]::before { opacity: 1; animation: beam-turn 2.8s linear infinite; }
@keyframes beam-turn { to { --beam-angle: 360deg; } }
@media (prefers-reduced-motion: reduce) {
  .beam[data-active="true"]::before { animation: none; background: var(--accent); opacity: 0.6; }
}
```

- Loading or processing: about 2.3-3 s per turn at moderate intensity. A persistent selected state: slower (4-5 s) and fainter, or better, a static border after a 0.8-1.2 s flourish.
- One traveling beam per view at most; never on every card in a list.
- Keep the element mounted and toggle the state so the glow fades out (about 0.5 s) instead of vanishing.
- The meaning lives elsewhere: `aria-busy="true"` on the working region, `aria-selected` for tabs and options, `aria-current` for the current step or page, `aria-pressed` for toggles, plus a static selected style and the normal `:focus-visible` outline.
- Pressed states still get immediate feedback (fill, contrast or a 0.97 scale), not only a glow.
- On dark surfaces check the glow does not reduce the contrast of text near the edge.

## Pitfalls

- A wizard that front-loads every setting, or a skip that drops users into an empty product.
- Hints on every element, hints that return after dismissal, tours that end on "Next" rather than on the real action.
- A chatbot that answers pricing from memory, cannot hand off, or hides behind a cheerful persona.
- One "Thinking..." spinner for every phase; indicators that keep running after an error; a beam on every selected card.
- Status changes announced twice, or every streamed token read aloud.

## Done when

- [ ] The first moment of value is named, and every wizard step moves toward it or is deferred with a way back.
- [ ] Skip leaves a usable product; progress, Back and resume work; state is stored per user.
- [ ] Hints fire on triggers, appear one at a time, respect dismissal and reach keyboard and screen-reader users without stealing focus.
- [ ] The assistant has a written scope, cites current sources, says when it does not know, and hands off to a person with context.
- [ ] Every working state has a truthful text label announced once, a Stop or Cancel, and a defined end state; determinate progress is used when the fraction is known.
- [ ] Reduced motion freezes orbs and beams to a static frame; contrast of indicators and nearby text was measured.
- [ ] Measures are activation, feature adoption and resolution, not views or completions alone.
