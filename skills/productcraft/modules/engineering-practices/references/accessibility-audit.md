# Accessibility audit

Read this when asked to audit a web or native app for accessibility, before a release where accessibility is a legal or contractual duty, after a redesign, or when reviewing a component library. How to build accessible screens is in `../../responsive-accessibility.md` and the UI rules (`../../../references/ui-rules/`); the legal targets, the accessibility statement and the legal-surface screens are in `../../legal-ready/references/accessibility.md`. This file is the audit itself: what to test, with which tools, and how to report findings that hold up.

## Ground rules

- **Name the standard.** Default to WCAG 2.2 Level AA (a W3C Recommendation since October 2023). A contract or law may name another version, for example WCAG 2.1 AA through EN 301 549 in the EU or the 2024 ADA Title II rule in the US; audit against what applies and say which.
- **Automated tools find part of the problems.** Many criteria need a person: whether alt text says the right thing, whether focus order makes sense, whether an error message helps. A clean scan is necessary, not sufficient. Never call a product "accessible" or "compliant" from an automated pass.
- **Audit real flows in a safe environment.** Use test accounts on a local, preview or staging build. No real customer data in screenshots or recordings, and no actions that send mail, charge cards or delete data outside a test system.
- **Every finding is reproducible.** It names the success criterion, the place, the steps with the browser and assistive technology used, who is affected and the fix.
- **Report scope honestly.** A conformance claim covers whole pages and complete processes. An audit of a sample supports statements about that sample only.

## 1. Agree the scope

- **Flows, not just pages.** Pick the complete processes users must finish: sign-up, sign-in and recovery, search, the main task of the product, checkout, settings, cancellation and account deletion, error pages and the consent banner. A step that fails breaks the whole process.
- **States.** Empty, loading, error and success states; dialogs, menus, tooltips, toasts; light and dark themes; logged out and logged in.
- **Sample a large site** the way the W3C evaluation methodology (WCAG-EM) does: every distinct template and flow, plus a few randomly chosen pages.
- **Platforms and assistive technology.** Write the matrix down before testing (step 4) so results are comparable later.
- **Done when:** the flow list, states, standard and test matrix are written and the owner agreed to them.

## 2. Automated scan

Fast, repeatable and good at the mechanical criteria (missing names and labels, contrast, invalid ARIA, missing document language). Run it on every state you reach, not only on page load: open the dialog, trigger the error, then scan.

```javascript
// Playwright Test with @axe-core/playwright (axe-core 4.x)
const { test, expect } = require('@playwright/test');
const { default: AxeBuilder } = require('@axe-core/playwright');

test('checkout has no automatically detectable WCAG A/AA violations', async ({ page }) => {
  await page.goto('/checkout');
  await page.getByRole('button', { name: 'Pay now' }).click();          // reach the error state too
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  console.log(`needs manual review: ${results.incomplete.map((r) => r.id).join(', ') || 'none'}`);
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.length} node(s)`)).toEqual([]);
});
```

- `violations` are definite failures; `incomplete` lists checks axe could not decide (often contrast over images or gradients). Review the incomplete ones by hand; they are not passes.
- Component tests: `jest-axe` or `vitest-axe`. URL lists in CI: `pa11y-ci`. Lighthouse's accessibility category runs a subset of axe rules; its score is not a conformance measure.
- Native apps: Xcode's Accessibility Inspector audit and, from Xcode 15 with iOS 17, `XCUIApplication().performAccessibilityAudit()` in UI tests; on Android, the Accessibility Scanner app and `AccessibilityChecks.enable()` from `espresso-accessibility` in instrumented tests.
- Never disable a rule to get green. Document each exclusion with the reason and the issue that tracks it.

## 3. Keyboard pass (web and desktop)

Put the mouse away and complete every flow in scope:

- Every interactive element is reachable with Tab and operable with Enter, Space or arrow keys as its pattern expects (2.1.1). Custom widgets (menus, tabs, listboxes, comboboxes, grids, tree views) follow the keyboard patterns of the WAI-ARIA Authoring Practices.
- Focus is always visible (2.4.7) and never hidden behind a sticky header, cookie banner or chat widget (2.4.11, new in 2.2).
- Focus order follows the meaning of the page (2.4.3); no positive `tabindex` reordering.
- Nothing traps focus (2.1.2). A modal keeps focus inside while open, closes with Escape, and returns focus to the control that opened it.
- A skip link or landmarks let users bypass repeated blocks (2.4.1).
- Single-character shortcuts can be turned off or remapped (2.1.4).
- Every drag action has a single-pointer or keyboard alternative (2.5.7, new in 2.2).

## 4. Screen reader pass

Pick pairings that match the audience, at least one desktop and one mobile, and record their versions:

| Platform | Common pairings |
|---|---|
| Windows | NVDA with Firefox or Chrome; JAWS with Chrome; Narrator with Edge |
| macOS, iOS, iPadOS | VoiceOver with Safari |
| Android | TalkBack with Chrome |

Check, flow by flow:

- Page title and language (2.4.2, 3.1.1); landmarks and a heading outline that matches the visual structure (1.3.1).
- Every link, button and control has a name that says what it does, and announces its role, value and state: expanded, selected, checked, pressed (4.1.2). Visible label text is part of the accessible name (2.5.3).
- Form fields announce label, required state, format hints and errors (1.3.1, 3.3.1, 3.3.2).
- Status messages (saved, added to cart, five results) are announced without moving focus (4.1.3), through `role="status"` or a live region.
- Images, icons and charts: meaningful alternatives or hidden when decorative (1.1.1); data tables have header cells.
- Reading order makes sense when the layout is linearized (1.3.2).

The browser's accessibility tree pane and Playwright's `locator.ariaSnapshot()` show what assistive technology receives; use them to explain a finding, not to replace listening.

## 5. Visual and display checks

- **Contrast:** 4.5:1 for normal text, 3:1 for large text (1.4.3); 3:1 for control boundaries, focus indicators and meaningful graphics (1.4.11). Check hover, focus, error and selected states; inactive controls are exempt.
- **Color alone** never carries the meaning (1.4.1): errors, required fields, chart series and links in text.
- **Zoom and reflow:** text at 200% without loss (1.4.4); content at 320 CSS pixels wide, the equivalent of 1280 pixels at 400% zoom, without horizontal scrolling except for data tables, maps and similar (1.4.10).
- **Text spacing:** inject line height 1.5, paragraph spacing 2 times the font size, letter spacing 0.12 and word spacing 0.16 times the font size; nothing may be cut off or overlap (1.4.12).
- **Hover and focus content** (tooltips, popovers) can be dismissed without moving the pointer, can be hovered, and stays until dismissed (1.4.13).
- **Target size** at least 24 by 24 CSS pixels or enough spacing (2.5.8, new in 2.2). Platform guidance asks for more on touch: 44 by 44 points on Apple platforms, 48 by 48 dp in Material Design.
- **Motion:** auto-moving or auto-updating content can be paused (2.2.2); animations respect `prefers-reduced-motion`; nothing flashes more than three times a second (2.3.1).
- **Orientation:** works in portrait and landscape unless one is essential (1.3.4).
- Forced-colors mode (Windows contrast themes) is not a WCAG criterion, but icons and focus rings that vanish in it are worth reporting.

## 6. Forms, time and authentication

- Errors are identified in text and suggest a fix (3.3.1, 3.3.3); legal, financial and data-deleting submissions can be reviewed, corrected or reversed (3.3.4).
- Fields that collect personal data carry the right `autocomplete` value (1.3.5).
- Information already entered in a process is not asked for again (3.3.7, new in 2.2).
- Sign-in needs no cognitive test without an alternative, and allows paste and password managers (3.3.8, new in 2.2).
- Time limits can be turned off, adjusted or extended (2.2.1); sessions warn before they expire.
- Help mechanisms appear in the same relative place across pages (3.2.6, new in 2.2).

## 7. Media, documents and native specifics

- Prerecorded video has captions (1.2.2) and audio description or a full alternative when visuals carry information (1.2.5); audio has a transcript.
- PDFs and office documents offered for download are tagged, have a document language and a sensible reading order, or have an accessible HTML equivalent.
- iOS: test with the largest Dynamic Type sizes and the VoiceOver rotor. Android: test with font scale at its maximum (non-linear scaling up to 200% since Android 14), TalkBack and Switch Access.

## 8. Report

One finding per barrier, grouped by flow:

```markdown
### A11Y-07 [Blocker] Card number errors are not announced (WCAG 3.3.1 Error Identification, A)
- Where: /checkout, payment step, field "Card number" (`CardForm.tsx:88`)
- Steps: NVDA 2025.x with Firefox; enter "1234", press Pay now
- Actual: the field turns red; nothing is announced and focus stays on the button
- Expected: the error text is announced and tied to the field
- Affects: blind and low-vision users; cannot complete a purchase
- Fix: `aria-describedby` from the input to the error, `aria-invalid="true"`, move focus to the first invalid field on submit
- Evidence: recording, axe found nothing (manual finding)
```

- Severity uses the scale in `../../engineering-workflow/references/verification-and-review.md`: a barrier that stops some users from completing a flow in scope is a Blocker.
- The summary states the standard, the scope, the test matrix with versions, the tools and their versions, the dates, and what was not tested (`NOT VERIFIED: <check> - <why>`).
- The audit changes no code. Fixes the user picks go through the engineering workflow, and each is re-tested with the same steps and assistive technology.
- When the product publishes an accessibility statement, hand the known issues and their planned fix dates to the legal-ready statement, without claiming full conformance.

## Keep it from regressing

- An axe check in the end-to-end tests of each key flow, failing on new violations; existing ones listed with an issue each instead of rules switched off.
- One keyboard-only end-to-end test per core flow (Playwright `page.keyboard.press('Tab')` and an assertion on the focused element).
- Linting for markup mistakes: `eslint-plugin-jsx-a11y`, the accessibility rules of the Vue and Angular ESLint plugins.
- The contrast unit test over design tokens in `../../legal-ready/references/accessibility.md`.

## Done when

- [ ] Standard, flows, states and the assistive-technology matrix are written down.
- [ ] The automated scan ran on every state in scope; violations are listed and `incomplete` items were checked by hand.
- [ ] Keyboard, screen reader and display checks ran on every flow in scope, or each gap is marked `NOT VERIFIED` with the reason.
- [ ] Every finding has the success criterion, location, steps with versions, effect, fix and evidence.
- [ ] No claim of conformance beyond what was tested.

## Anti-patterns

- Reporting a Lighthouse or axe score as the audit result.
- Testing only page load, never the open dialog or the error state.
- Overlay widgets offered as the fix; they do not repair the underlying markup.
- `aria-label` pasted on everything, hiding the visible text or contradicting it.
- Findings without a reproduction, or style opinions labeled as WCAG failures.
