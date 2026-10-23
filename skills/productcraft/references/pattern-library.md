# ProductCraft pattern library

Each pattern pairs a design principle with an implementation rule and a guardrail. Read only the entries that match the task in front of you; modules list their related pattern IDs. Rules are heuristics, not mandatory design laws: security, access, performance, facts and user consent take precedence over visual effects and engagement tricks.

Machine-readable version: `pattern-index.json`.

## 01. Drag and drop: pickup, snap, undo
- **Category:** `interaction`
- **Principle:** Good drag feedback shows pickup, movement mode and a short undo window; board columns and free canvases need different landing rules.
- **Implementation rule:** Provide visible drag handle/ghost, valid drop zones, keyboard alternative, meaningful post-drop announcement, reversible move where feasible.
- **Guardrail:** Never rely solely on cursor animation or silent persistence.

## 02. Five-level visual hierarchy
- **Category:** `foundation`
- **Principle:** Hierarchy comes from size, contrast, weight, position and rhythm working together.
- **Implementation rule:** Promote primary decision and next action; keep labels readable, secondary copy truly secondary, and one dominant focal point.
- **Guardrail:** Measure contrast and scan order; do not shrink necessary labels.

## 03. Rounded corners and perceived safety
- **Category:** `foundation`
- **Principle:** Softer shapes can feel more approachable, but radius should express product character rather than decoration.
- **Implementation rule:** Use a restrained, coherent radius scale reflecting product character and control boundaries.
- **Guardrail:** Rounding does not prove safety or trustworthiness; too much rounding harms dense tools.

## 04. Switches, feedback, anticipation
- **Category:** `feedback`
- **Principle:** Toggle feedback and action confirmation shape how certain users feel about the result.
- **Implementation rule:** Acknowledge every interaction, display correct pending/success/failure state, and keep semantics unambiguous.
- **Guardrail:** Do not fake server confirmation or omit error recovery.

## 05. Optimistic actions and fast perceived response
- **Category:** `feedback`
- **Principle:** Immediate local response makes actions feel fast while the real work continues in the background.
- **Implementation rule:** Use optimistic UI only for reversible low-risk actions, then reconcile on success or rollback with clear error on failure.
- **Guardrail:** Never confirm financial, medical, or destructive actions before server truth.

## 06. Dark patterns: hidden costs
- **Category:** `conversion`
- **Principle:** Surprise fees at checkout are a dark pattern that erodes trust and drives abandonment.
- **Implementation rule:** Disclose total price, mandatory fees, recurrence and significant terms before commitment; offer honest persuasive framing instead.
- **Guardrail:** Hidden fees and misleading choices are anti-patterns, not optimization.

## 07. Color focus and action prominence
- **Category:** `foundation`
- **Principle:** When every button is colorful, attention is diluted and no action stands out.
- **Implementation rule:** Use one clear primary action and reserved color for state, emphasis, and identity; check meaningful contrasts.
- **Guardrail:** Color must not be the only cue or make every button primary.

## 08. Variable rewards, loss aversion, reciprocity
- **Category:** `conversion`
- **Principle:** Variable rewards, streaks and reciprocity are powerful behavioral triggers that are easy to misuse.
- **Implementation rule:** Provide earned progress, authentic motivation, transparent reciprocity, and legitimate reminders when useful.
- **Guardrail:** Do not weaponize anxiety, gambling-like loops or false social obligation.

## 09. Fake wait duration, ghost typing, anxiety
- **Category:** `conversion`
- **Principle:** Artificially long loading and phantom typing manipulate users and break trust.
- **Implementation rule:** Make timing indicators truthful, stop simulated typing from implying a real person, and report known progress.
- **Guardrail:** Never create artificial waits or false human presence to manipulate users.

## 10. Hover affordance and press response
- **Category:** `feedback`
- **Principle:** Subtle scale, depth, accent and press states make controls feel interactive.
- **Implementation rule:** Define pointer hover and pressed states with modest transition and focus-visible equivalents.
- **Guardrail:** Do not depend on hover for touch or crucial information.

## 11. Modal entry, exit and backdrop
- **Category:** `feedback`
- **Principle:** Entrance motion and a subdued backdrop keep a confirmation dialog focused, especially for destructive actions.
- **Implementation rule:** Use accessible dialog semantics, clear title, backdrop/focus containment, Escape policy, and predictable exit behavior.
- **Guardrail:** Support reduced motion, no accidental backdrop dismissal for dangerous actions.

## 12. Design system: color, type, component atoms
- **Category:** `foundation`
- **Principle:** A design system defines color roles, a type hierarchy and reusable atomic components.
- **Implementation rule:** Set design tokens, semantic color roles, type steps, spacing scales and composable components before sweeping changes.
- **Guardrail:** Prefer existing product tokens to a wholesale replacement.

## 13. 60-30-10 color distribution
- **Category:** `foundation`
- **Principle:** A dominant base, a supporting surface and a small accent make a balanced composition.
- **Implementation rule:** Use majority neutral/base, secondary surface and small purposeful accent where appropriate.
- **Guardrail:** 60/30/10 is guidance, not a quota; accessibility takes priority.

## 14. Transparency and glass style
- **Category:** `foundation`
- **Principle:** Transparency, blur and a subtle border create a glass-like surface that is easy to overuse.
- **Implementation rule:** If transparency fits the brand, set legible contrast, light/dark fallback and performance-safe blur.
- **Guardrail:** Do not add generic glassmorphism by default or sacrifice readable text.

## 15. Fitts law: targets and thumb reach
- **Category:** `interaction`
- **Principle:** Small targets and hard-to-reach positions slow users down, especially one-handed on mobile.
- **Implementation rule:** Size interactive targets generously; place mobile primary actions in reachable zones and reduce travel.
- **Guardrail:** Honor touch accessibility and do not create false urgency.

## 16. Whitespace: micro, macro, and active
- **Category:** `foundation`
- **Principle:** Whitespace works at three levels: micro inside groups, macro between sections and active around the focal point.
- **Implementation rule:** Use tight internal grouping, meaningful section separation and deliberate focal breathing room.
- **Guardrail:** Do not leave huge empty hero regions or remove dense useful content.

## 17. Grid ratios, responsive collapse
- **Category:** `responsive`
- **Principle:** Layouts should reflow to fewer columns when content stops fitting, not at arbitrary device sizes.
- **Implementation rule:** Define breakpoints around content failure, not phone brand; reflow navigation, tables and panels thoughtfully.
- **Guardrail:** Never hide functionality only because width becomes narrow.

## 18. Hue adjacency, gradients and text
- **Category:** `foundation`
- **Principle:** Hue relationships, gradient direction and accent type can add interest but can also hurt legibility.
- **Implementation rule:** Start with clear solid colors; add restrained gradient only for a justified identity moment or meaningful data treatment.
- **Guardrail:** Gradients alone do not make a design premium.

## 19. Skeletons and anticipation
- **Category:** `feedback`
- **Principle:** Placeholders that preview the coming content make waits feel shorter.
- **Implementation rule:** Use representative, bounded skeletons when latency merits them; announce loading and replace with truth.
- **Guardrail:** Avoid fake content and infinite skeletons when the system failed.

## 20. Golden ratio and type scale
- **Category:** `foundation`
- **Principle:** The golden ratio is a useful proportion idea for layout and type scales, not a law.
- **Implementation rule:** Choose a consistent modular type/spacing scale, then tune to readable content and actual responsive measurements.
- **Guardrail:** Do not enforce 1.618 mathematically or claim universal beauty.

## 21. Tokenized palettes, spacing, motion
- **Category:** `foundation`
- **Principle:** Scattered hard-coded styles drift; shared tokens for color, spacing and easing keep a product coherent.
- **Implementation rule:** Centralize CSS/theme variables for semantic colors, radii, typography, spacing and motion.
- **Guardrail:** Support user preferences, light/dark if present, and reduced motion.

## 22. Empty state design
- **Category:** `feedback`
- **Principle:** A good empty state explains what is missing and offers the next step.
- **Implementation rule:** Explain what is empty and offer a task-relevant action or import path; teach only when useful.
- **Guardrail:** Avoid empty-state decoration without a next step.

## 23. Skeleton timing and progress indicators
- **Category:** `feedback`
- **Principle:** How long an operation takes decides whether to show nothing, a skeleton or determinate progress.
- **Implementation rule:** Show nothing or lightweight delay for very short loads; use content skeletons or determinate progress when warranted.
- **Guardrail:** Never display fabricated progress percentages.

## 24. Errors: severity and surface
- **Category:** `forms`
- **Principle:** Inline field errors, toasts and blocking dialogs suit different severities.
- **Implementation rule:** Use field-level correction near inputs, a short nonblocking toast for minor confirmation, and blocking UI for dangerous decisions.
- **Guardrail:** Preserve error context and actionable recovery, avoid modal spam.

## 25. Motion choreography and feedback timings
- **Category:** `feedback`
- **Principle:** Fast click feedback, short entrances and purposeful staggering make motion feel responsive.
- **Implementation rule:** Use brief, interruptible animation; immediate interaction feedback; stagger only when clarifying sequence.
- **Guardrail:** Timing figures are starting points, not mandatory; respect prefers-reduced-motion.

## 26. Search and zero-result recovery
- **Category:** `navigation`
- **Principle:** Helpful prompts, relevant autocomplete and a productive zero-results state make search recoverable.
- **Implementation rule:** Search by intent, prioritize relevance, expose keyboard navigation and suggestions, and offer spelling/filter recovery.
- **Guardrail:** Do not pretend popular results are relevant or leak private search history.

## 27. Date-range selection across months
- **Category:** `forms`
- **Principle:** Date pickers need useful presets, cross-month ranges and a mobile-friendly layout.
- **Implementation rule:** Offer useful presets, true interval selection across months, explicit dates/timezones and mobile-friendly confirmation.
- **Guardrail:** Test DST, unavailable days, inclusive endpoints, locale formats.

## 28. Checkout steps and preserving state
- **Category:** `forms`
- **Principle:** Splitting a long checkout into steps with clear boundaries and back navigation reduces errors.
- **Implementation rule:** Chunk genuinely complex flows, keep progress honest, preserve state when moving back, and minimize fields.
- **Guardrail:** Do not hide mandatory charges or force needless steps.

## 29. Notification surfaces and lifecycle
- **Category:** `feedback`
- **Principle:** Toasts, banners, modals and badges differ in persistence and severity.
- **Implementation rule:** Match notification surface to importance, provide undo for reversible operations, allow persistent alerts where necessary.
- **Guardrail:** Avoid overusing urgent styles or masking critical notices.

## 30. Card-number input formatting
- **Category:** `forms`
- **Principle:** Grouping long card numbers makes them easier to scan and check.
- **Implementation rule:** Group input visually, validate via trusted payment provider, and handle formatting without changing semantics.
- **Guardrail:** Never store raw payment card numbers in application storage or logs; use tokenized hosted payment fields.

## 31. Ratings and interaction precision
- **Category:** `interaction`
- **Principle:** Star inputs need precise interaction, and rating summaries need honest aggregates.
- **Implementation rule:** Make star input operable with keyboard, expose accessible labels and show genuine aggregate data.
- **Guardrail:** Do not fabricate ratings, users or sample sizes.

## 32. Sliders: hit area, steps, keyboard
- **Category:** `interaction`
- **Principle:** A wide track, discrete steps and Home/End support make sliders usable.
- **Implementation rule:** Use accessible native slider semantics where possible; show current value, sensible bounds, keyboard and touch.
- **Guardrail:** Avoid slider for precise values when a numeric input would be better.

## 33. OTP input paste and autofill
- **Category:** `forms`
- **Principle:** Full-code paste across cells, a numeric keypad and instant status make OTP entry fast.
- **Implementation rule:** Support full-code paste, WebOTP/autocomplete when supported, clear focus behavior and retry/resend with limits.
- **Guardrail:** Do not disclose which part of an auth challenge was wrong; never log codes.

## 34. Pagination for changing datasets
- **Category:** `navigation`
- **Principle:** Offset pagination duplicates or skips rows when data changes; long page-link lists and missing URL state hurt navigation.
- **Implementation rule:** Choose cursor pagination for changing feeds; use short controls, stable sort, shareable URL state and page boundaries.
- **Guardrail:** Explain offset pagination tradeoffs rather than assuming all data requires cursors.

## 35. Password strength and entropy
- **Category:** `forms`
- **Principle:** Long, uncommon passwords are stronger than short complex ones, and strength meters need careful wording.
- **Implementation rule:** Favor length and breached-password checks; support paste and password managers; communicate strength carefully.
- **Guardrail:** Do not claim exact crack times from a simplistic meter or require symbols arbitrarily.

## 36. Multi-file upload with per-file recovery
- **Category:** `forms`
- **Principle:** Uploads can fail near completion; an independent per-file queue keeps one failure from sinking the batch.
- **Implementation rule:** Provide per-file progress, retry/cancel, supported types and accessible non-drag fallback.
- **Guardrail:** Enforce server-side size/type limits and scan/quarantine where required.

## 37. Destructive action friction proportional to risk
- **Category:** `safety`
- **Principle:** Hold-to-delete, restrained red and delayed deletion add friction in proportion to risk.
- **Implementation rule:** Use an appropriate confirmation or type-to-confirm for truly irreversible changes; make recoverable changes easy.
- **Guardrail:** No unnecessary friction for harmless actions; never mislead about deletion finality.

## 38. Undo, typed confirmation and delayed send
- **Category:** `safety`
- **Principle:** Repeated confirmations train users to click through; undo and a grace period protect them better.
- **Implementation rule:** Prefer undo for reversible changes; confirm truly destructive effects by naming consequences and offering a review window where feasible.
- **Guardrail:** Backend undo must actually work; never offer a placebo Undo.

## 39. Tabs with active indicator and keyboard
- **Category:** `navigation`
- **Principle:** A moving active indicator plus arrow-key and Home/End support make tabs clear and accessible.
- **Implementation rule:** Use semantic tabs/tabpanel and roving keyboard focus, keep visual focus distinct from selected state.
- **Guardrail:** Do not autoplay tabs or rely only on color.

## 40. Form validation on blur and success
- **Category:** `forms`
- **Principle:** Errors revealed late frustrate users; feedback on blur and a quiet success state guide them.
- **Implementation rule:** Validate at useful boundaries (blur/submit), reserve field space to prevent layout jumps and confirm correct entries discreetly.
- **Guardrail:** Avoid errors on every keystroke while users are still composing.

## 41. Context menus: placement and touch
- **Category:** `navigation`
- **Principle:** Context menus must open at the pointer, stay on screen and have a long-press equivalent on touch.
- **Implementation rule:** Collision-detect positions, manage submenu pointer intent, add keyboard access and mobile long-press alternative.
- **Guardrail:** Do not trap touch users in desktop-only context menus.

## 42. Dropdowns: click and keyboard interaction
- **Category:** `interaction`
- **Principle:** Dropdowns need full-row hit areas, arrow keys, Enter/Escape and fast opening.
- **Implementation rule:** Provide conventional dropdown/listbox behavior, visible focus, touch-safe items, and prompt open feedback.
- **Guardrail:** Do not invent unusual interactions that hurt accessibility.

## 43. Optimistic UI state synchronization
- **Category:** `feedback`
- **Principle:** Optimistic UI updates immediately, then reconciles with the server or reverts on error.
- **Implementation rule:** For low-risk interactions, update local state immediately and retry or rollback with notice; dedupe calls.
- **Guardrail:** Irreversible/payment/medical outcomes must wait for authenticated server truth.

## 44. Swipe actions on mobile
- **Category:** `interaction`
- **Principle:** Swipe should reveal actions rather than commit them, and direction should encode intent.
- **Implementation rule:** Use swipe to reveal optional actions, require explicit destructive commit and give undo where possible.
- **Guardrail:** Ensure screen-reader and non-swipe alternatives.

## 45. Accessible toggle anatomy
- **Category:** `interaction`
- **Principle:** A switch needs clear dimensions, a knob, keyboard support, ARIA state and rollback on server error.
- **Implementation rule:** Use real checked state, Space support, focus ring, proper label and server rollback if update fails.
- **Guardrail:** Use checkboxes rather than switches for non-immediate apply scenarios.

## 46. Toast positioning, stacking and status colors
- **Category:** `feedback`
- **Principle:** Toast position, stack limits and status styling decide whether notifications help or overwhelm.
- **Implementation rule:** Anchor toast consistently, limit concurrent stacking, distinguish status text/icons, announce via live region.
- **Guardrail:** Do not blanket the screen or rely on color alone.

## 47. Settings density, search, dangerous zone
- **Category:** `navigation`
- **Principle:** Low-risk preferences can save instantly, identity changes need an explicit save, and settings search scales with size.
- **Implementation rule:** Persist low-risk toggles quickly, require explicit Save for high-impact fields, provide settings search and isolate danger zone.
- **Guardrail:** Protect identity/security changes with reauthentication when warranted.

## 48. Touch targets: no hover-only on mobile
- **Category:** `responsive`
- **Principle:** Actions hidden behind hover vanish on touch screens; larger hit areas and visible inline actions keep them reachable.
- **Implementation rule:** Expose essential actions directly or through visible menus, provide adequate hit area, and avoid hover assumptions.
- **Guardrail:** Do not shrink tap areas to fit visual composition.

## 49. Live cursors, presence and follow
- **Category:** `advanced`
- **Principle:** Interpolated remote cursors, presence before activity and an optional follow mode make collaboration feel live.
- **Implementation rule:** Throttled collaboration presence, jitter smoothing, accessible participant labels and opt-in follow mode.
- **Guardrail:** Limit private presence leakage and avoid user-surveillance implications.

## 50. Tooltip delay and edge placement
- **Category:** `feedback`
- **Principle:** Delayed tooltips that flip at screen edges and keep wording short stay helpful without getting in the way.
- **Implementation rule:** Delay nonessential hover tooltips appropriately, position within viewport and show keyboard focus alternatives.
- **Guardrail:** Critical guidance cannot live only in tooltips.

## 51. Dark-mode surfaces, text tiers and hairlines
- **Category:** `foundation`
- **Principle:** Layered near-black surfaces, three text tiers and subtle hairlines make dark mode readable.
- **Implementation rule:** Use dark-mode elevation and readable text hierarchy, reserve hairlines for helpful separation.
- **Guardrail:** Do not blindly choose low-contrast gray or assume OLED benefits justify poor readability.

## 52. Nested radius and concentric geometry
- **Category:** `foundation`
- **Principle:** Nested elements look right when the inner radius steps down by the parent's padding.
- **Implementation rule:** Use radius tokens; nested radius should normally step down relative to container padding.
- **Guardrail:** Treat formulas as visual heuristics rather than absolute laws.

## 53. Data tables: alignment, density, actions
- **Category:** `data`
- **Principle:** Right-aligned tabular numbers, left-aligned text and task-appropriate row height make tables scannable.
- **Implementation rule:** Align numeric columns right with tabular numerals, label headers, let density reflect workflow, provide visible keyboard actions.
- **Guardrail:** Do not hide needed actions in hover alone or truncate key values.

## 54. Responsive tables into labeled records
- **Category:** `data`
- **Principle:** Wide tables become readable on mobile when rows turn into labeled records.
- **Implementation rule:** Below a content-fit breakpoint, switch to labelled cards/rows or intentional scroll with sticky identifiers.
- **Guardrail:** Ensure dates, currency units and statuses remain unambiguous.

## 55. Dashboard anti-slop teardown
- **Category:** `foundation`
- **Principle:** Generic gradients, equal-weight metric cards and bloated greetings are dashboard noise.
- **Implementation rule:** Use real KPIs first, one primary focal point, meaningful comparison units, concise copy and direct controls.
- **Guardrail:** Never invent analytics or remove necessary expert data.

## 56. Chat system layout and anchoring
- **Category:** `advanced`
- **Principle:** Sender grouping, timestamps, scroll anchoring and composer behavior define a usable chat.
- **Implementation rule:** Group consecutive messages, preserve scroll position, show unread divider, manage composer growth and status semantics.
- **Guardrail:** Avoid fake presence, intrusive typing and chat-history jumps.

## 57. Calendar grid and event geometry
- **Category:** `data`
- **Principle:** A week grid has seven columns, and each event's position and height map to its time and duration.
- **Implementation rule:** Render time-to-pixel mapping consistently, handle overlapping events, accessible views and current-time indicator.
- **Guardrail:** Test daylight-saving transitions, locale week starts and timezone math.

## 58. Login UI fidelity and real error states
- **Category:** `forms`
- **Principle:** Ornamental login screens often hide weak error handling; working auth and clear failure states matter more.
- **Implementation rule:** Prioritize working auth, provider-specific login, useful validation, distinct failure states, and genuine brand styling.
- **Guardrail:** Never simulate a provider sign-in or mask auth errors as merely design.

## 59. Icons as a coherent system
- **Category:** `foundation`
- **Principle:** One icon stroke style, sized to the surrounding text, keeps an interface coherent.
- **Implementation rule:** Standardize stroke, viewbox, optical scale and semantic icon usage across surfaces.
- **Guardrail:** No mismatched emoji, mixed icon styles or icon-only unlabeled actions.

## 60. Internationalization and RTL expansion
- **Category:** `responsive`
- **Principle:** Long translations and right-to-left layouts expose weak layout assumptions.
- **Implementation rule:** Test longer strings, flexible controls, logical CSS properties and right-to-left flow incl. icons and motion.
- **Guardrail:** Do not mirror numbers, media play symbols or meaning-specific icons incorrectly.

## 61. Success outcomes and next steps
- **Category:** `feedback`
- **Principle:** A good success screen says what happened, for whom and when, with a receipt and next steps.
- **Implementation rule:** Show concrete outcome, relevant next action, reference/receipt, and permanence level.
- **Guardrail:** Never say paid/confirmed until independently verified.

## 62. AI editing version history and source labels
- **Category:** `advanced`
- **Principle:** AI edits need clear labels, version history and an explicit accept flow.
- **Implementation rule:** Keep original content recoverable, mark AI-generated suggestions, show provenance and offer compare/revert.
- **Guardrail:** Never silently overwrite user work or claim AI output is authoritative.

## 63. Kanban drag previews and column limits
- **Category:** `advanced`
- **Principle:** A lifted card, a landing placeholder and work-in-progress cues make Kanban boards predictable.
- **Implementation rule:** Expose drag preview and landing placeholder, preserve ordering atomically, indicate WIP limits and keyboard move action.
- **Guardrail:** Avoid hidden columns or unannounced state mutation.

## 64. View Transitions API with fallbacks
- **Category:** `advanced`
- **Principle:** Shared transition names can connect list and detail views, theme toggles and page navigation.
- **Implementation rule:** Use View Transitions API only where supported, with stable names, fallback, and reduced-motion guard.
- **Guardrail:** Never rely on experimental cross-document transitions for basic navigation.

## 65. Mobile forms: labels, errors, numeric codes
- **Category:** `forms`
- **Principle:** Placeholder-only labels, jumping submit buttons and numeric-typed codes break mobile forms.
- **Implementation rule:** Keep persistent labels, reserve validation space, anchor submit consistently and store codes as strings (preserve zeros).
- **Guardrail:** Use inputmode for keypad, not numerical conversion on codes.

## 66. Mobile sheets versus modal dialogs
- **Category:** `responsive`
- **Principle:** Bottom sheets suit contextual mobile tasks; swipe-to-dismiss needs velocity and scroll coordination.
- **Implementation rule:** Choose sheet for contextual mobile actions, modal for genuinely blocking tasks, manage focus/scroll and explicit close.
- **Guardrail:** Do not allow accidental destructive dismissal or trap gestures.

## 67. Checkout layout and error on blur
- **Category:** `forms`
- **Principle:** A visible total, well-timed card validation and a logical field order make checkout trustworthy.
- **Implementation rule:** Display authoritative total and terms, preserve keyboard order and tokenize payment with provider elements.
- **Guardrail:** Never let client decide charge amount or store PAN/CVC locally.

## 68. Voice notes: press feedback, lock, playback
- **Category:** `advanced`
- **Principle:** Voice recording needs controls away from the thumb, a lock for long recordings and scrub/speed on playback.
- **Implementation rule:** Give clear recording status, permission handling, pause/cancel, locked hands-free mode and accessible playback.
- **Guardrail:** No secret recording, false recording indicators or missing consent.

## 69. Command palette: ranking, shortcuts, context
- **Category:** `navigation`
- **Principle:** A command palette should rank exact and recent matches and layer context without dimming the app too much.
- **Implementation rule:** Prioritize exact/recent commands, keyboard shortcuts, clear action category and robust focus restoration.
- **Guardrail:** Do not reveal privileged actions before server authorization.
