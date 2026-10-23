# UI Distiller: Practical transformation patterns

Use these as reasoning examples. Do **not** copy the same layout to every product.

## 1. Operational dashboard

**Before:** Oversized "Welcome back!" hero; inspirational subtitle; four identical KPI cards; gradient banner; excessive section headings; urgent pending tasks below fold.

**After:** Compact, precise page title. Primary task/status or exception appears immediately. The most important number gets the strongest type treatment with timeframe/unit. Supporting metrics become a restrained inline strip or compact list. Pending tasks and their next actions appear above decorative trends. Detailed charts remain when decisions depend on them.

**Integrity:** Preserve reporting definitions, source labels, filters, historical context, and drill-downs. A dashboard that needs all four KPIs may keep all four if each supports a real decision.

## 2. Product landing page

**Before:** "Unlock the future of your workflow" headline; three superlatives; two competing CTAs; glowing mock device and decorative blobs; six repeated benefit cards.

**After:** One specific outcome the product delivers, a concise qualifier for whom, one primary action, and truthful evidence or real product context. Feature sections use concrete language, distinctive rhythm, and demonstrate what people can actually do. Eliminate repeated claims and arbitrary icon badges.

**Integrity:** Keep pricing conditions, permissions, compatibility, and security claims precise. Do not invent social proof.

## 3. Search/catalog/listing page

**Before:** Huge page title; unnecessary intro paragraph; several summary cards; filters isolated in large boxes; actual results only after multiple scrolls.

**After:** Brief title, search/filter controls, result count when useful, then scannable results. Keep sort/filter state obvious. Preserve metadata necessary for evaluating results. Collapse rarely used filters under clear "More filters" if that genuinely helps.

**Integrity:** Do not remove pagination, result status, essential actions, or filter chips that communicate currently applied constraints.

## 4. Multi-step form

**Before:** Separate card for every input; repetitive helper paragraphs; animated progress decoration; vague submit CTA; placeholder-only labels.

**After:** One clear step title; logically grouped fields with persistent labels; inline help for ambiguous fields; immediate validation; informative primary button ("Create invoice" versus "Continue" when feasible); light progress indicator where process position matters.

**Integrity:** Preserve accessible labels, consent, fee disclosures, destructive consequences, validation, and back navigation.

## 5. Settings and preferences

**Before:** Many unrelated colorful cards; oversized icons; every option highlighted; decorative save banners; no distinction between everyday preferences and dangerous operations.

**After:** Calm grouped sections with clear headings and concise explanations only where consequences aren't obvious. Common preferences are easy to locate; dangerous and privacy-sensitive actions have adequate descriptions and safeguards. Keep state visibility and explicit Save/Cancel if the interaction model requires them.

**Integrity:** Never obscure data deletion, billing, authentication, privacy choices, or warnings.

## 6. AI tool or editor

**Before:** Big welcome, generic suggested prompts, loud gradient, stacked controls, three decorative sidebars, and little room for the actual artifact.

**After:** Content canvas/conversation and main input dominate. Tools are grouped by current task. Prompt suggestions show only when needed. Metadata and history remain reachable in clear panels. Unnecessary greetings and wrappers disappear.

**Integrity:** Preserve navigation to history, model/provider visibility when it affects user decisions, keyboard shortcuts, upload state, and explicit action feedback.

## 7. Small-screen adaptation

**Before:** Desktop cards stack into a very long page; primary action vanishes below content; labels truncate; tables overflow or silently lose columns.

**After:** The primary task remains immediately discoverable, supporting details compress or move into predictable views, actions stay reachable, and essential data remains accessible. Use responsive table approaches chosen for the actual data (scroll affordance, priority columns with detail expansion, or tailored rows).

**Integrity:** Do not conceal information that was visible on desktop without any discoverable way to retrieve it.
