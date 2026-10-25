# Accessibility (items 13-15)

General guidance, not legal advice; have a qualified lawyer review. How to build accessible screens is already covered by [`../../responsive-accessibility.md`](../../responsive-accessibility.md) and the UI rules (`../../../references/ui-rules/`). This file sets the legal target, the evidence to keep and the legal-surface screens that are often missed.

## Why it is a legal item

- **US:** Title III of the ADA covers businesses open to the public. There is no codified technical standard for private websites, but lawsuits and settlements usually measure against WCAG 2.x level AA. The 2024 rule for state and local governments under Title II adopts WCAG 2.1 AA.
- **EU:** the European Accessibility Act (Directive (EU) 2019/882) has applied since 28 June 2025 to many consumer products and services, including e-commerce, consumer banking, e-books, electronic communications and passenger transport ticketing. Microenterprises providing services are exempt. Its harmonised standard, EN 301 549, currently references WCAG 2.1 AA. Service providers must publish information on how the service meets the requirements.
- **UK:** the Equality Act 2010 requires service providers to make reasonable adjustments, and public-sector sites have their own accessibility regulations.
- **Build target:** WCAG 2.2 level AA. It contains the 2.1 AA criteria (except the obsolete 4.1.1 Parsing) plus new ones, so it covers what these laws currently reference.
- **Accessibility statement:** publish `/accessibility` with the target standard, the known issues with dates for fixes, a contact for reporting problems (`[[LEGAL: accessibility contact]]`) and the date of the last review. Do not claim full conformance without an audit.
- **Legal surfaces get the same care:** the consent banner, policy pages, checkout, cancellation, account deletion, the unsubscribe page and the age gate are all in scope and often fail.

## 13. Alt text

- **What it is:** a text alternative for every image that carries meaning (WCAG 1.1.1 Non-text Content), and none for decoration.
- **When it applies:** every image, icon, chart, SVG and image-based control, on the web and in apps.
- **Implement:**
  - Informative images: concise alt that conveys the content or purpose. Functional images (an image inside a link or button): alt that names the action ("Search", "Go to home page"). Decorative images: `alt=""` or a CSS background. Complex images such as charts: a short alt plus a nearby description or data table. Avoid text inside images; where it is unavoidable, the alt contains that text.
  - Icon-only controls need an accessible name (`ICO-04`, `NAV-02`). Meaningful inline SVG gets `role="img"` and a `<title>` or `aria-label`; decorative SVG gets `aria-hidden="true"`. Animations get a still fallback that carries the alt (`ICO-09`).
  - Content systems and upload flows: `media(alt_text, is_decorative)`, with the admin form requiring one or the other. Machine-suggested alt text is a draft for a person to review, not the final answer.
  - Video: captions for prerecorded audio (WCAG 1.2.2), and a transcript or audio description where the visuals carry information.
- **Verify:** the scanner's `IMG_ALT` check is clean, then a person reviews alt quality on key pages; an automated accessibility checker runs in the end-to-end suite; a screen-reader pass on the home, pricing, signup and checkout screens.
- **Common mistakes:** alt set to "image" or a file name; alt on purely decorative images; image links with no name; alt that repeats the visible caption; hero images with baked-in text; a content system with no alt field.

## 14. Colour contrast

- **What it is:** enough contrast between text, controls and their background (WCAG 1.4.3 Contrast (Minimum), 1.4.11 Non-text Contrast), with information never carried by colour alone (1.4.1).
- **When it applies:** all UI, in every theme and state.
- **Implement:** follow `COL-01` (4.5:1 for normal text, 3:1 for large text of 24px or 18.66px bold; 3:1 for component boundaries, focus indicators and meaningful icons), `COL-07` (never colour alone), `COL-08` (text over images) and `COL-10` to `COL-13` (focus, accent fills, translucent surfaces, error states). Add a unit test that computes the WCAG contrast ratio for every foreground and background token pair, in light and dark themes:

  ```js
  const lum = (hex) => {
    const [r, g, b] = hex.match(/\w\w/g).map((h) => {
      const c = parseInt(h, 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  // expect(ratio(tokens.textMuted, tokens.surface)).toBeGreaterThanOrEqual(4.5);
  ```

- **Verify:** the token-pair test passes; an automated checker reports no contrast failures on key pages; a person checks hover, focus, error and disabled states, dark mode and 200% zoom, including the consent banner and the policy pages.
- **Common mistakes:** pale grey legal text and banners; white text on a bright brand button; a focus ring that vanishes on dark surfaces; links marked only by colour; placeholder text used as the only label.

## 15. Keyboard navigation

- **What it is:** everything can be done with a keyboard, focus is always visible and never trapped, and the order makes sense (WCAG 2.1.1 Keyboard, 2.1.2 No Keyboard Trap, 2.4.1 Bypass Blocks, 2.4.3 Focus Order, 2.4.7 Focus Visible). WCAG 2.2 adds 2.4.11 Focus Not Obscured (Minimum), 2.5.7 Dragging Movements, 2.5.8 Target Size (Minimum) of 24 by 24 CSS pixels, and 3.3.8 Accessible Authentication (Minimum), which rules out puzzles without an alternative and requires paste and password managers to work.
- **When it applies:** every interactive element and flow.
- **Implement:** native elements first (`ENG-01`, `FRM-27`); a visible focus state on every control (`BTN-02`); dialogs that trap focus and return it on close (`CMP-12`); hidden content made inert (`ENG-05`); menus as disclosures, not hover traps (`NAV-17`); a tap or keyboard alternative for every gesture and drag (`MOB-11`); a "Skip to content" link; sticky headers and the consent banner must not cover the focused element; a non-puzzle alternative for any challenge.
- **Verify:** tab through signup, checkout, the consent banner (first layer and preferences), cancellation, account deletion, the unsubscribe page and the age gate without a mouse. Record any failure. Add one end-to-end test per core flow that drives it with key presses only. Run the automated checker.
- **Common mistakes:** clickable `div`s; `outline: none` with no replacement; focus lost after a modal closes; a consent banner unreachable by keyboard or covering the focused field; custom selects that ignore arrow keys; puzzle-only challenges; small adjacent targets.
