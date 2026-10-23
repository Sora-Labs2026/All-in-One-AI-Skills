# UI rules: Mobile and touch

Touch targets, thumb reach, safe areas, margins and device sizes. Rule IDs use the `MOB-` prefix; cite them in change reports.

## MOB-01. Make touch targets at least 44pt

**Why:** Small hit areas cause missed taps, especially on icon-only controls.

- **Do:** Make every tappable element at least 44x44pt (iOS) or 48x48dp (Android).
- **Do:** Keep icons visually small if desired (about 24px) and enlarge the hit area with padding or an invisible overlay.
- **Do:** Give text buttons and links a full-height hit area even when the text is small.
- **Avoid:** Hit areas that match a 16-24px glyph exactly, such as back, close, favorite or password-visibility icons.
- **Note:** WCAG 2.2 sets 24x24 CSS px as the AA minimum and 44x44 as enhanced; platform guidance asks for 44pt/48dp.

## MOB-02. Space touch targets so taps land where intended

**Why:** Crowded targets cause mis-taps; the smaller the target, the more space it needs.

- **Do:** Keep at least 8px between adjacent targets, and more between small ones (for example about 32px between 44px targets, 12px between 72px targets).
- **Do:** Keep hit areas from overlapping.
- **Avoid:** Tiny icon buttons packed edge to edge or against screen edges.

## MOB-03. Keep key actions in the thumb zone

**Why:** In one-handed use the bottom of the screen is easiest to reach.

- **Do:** Anchor the main forward action (Continue, Next, Pay) at the bottom of the screen above the safe area.
- **Do:** Add bottom padding to scroll content so a sticky action never covers the last field.
- **Do:** Keep destructive or rarely used actions out of the easiest reach zone.
- **Avoid:** Critical actions as small targets in the top corners.

## MOB-04. Respect safe areas

**Why:** Content under the status bar, notch or home indicator is obscured or collides with system gestures.

- **Do:** Read insets at runtime: env(safe-area-inset-top/bottom) on the web, SafeAreaView or platform APIs in native code.
- **Do:** Keep the top navigation row clear of the status area and leave the home-indicator zone free of controls, including when the keyboard is open.
- **Avoid:** Hard-coded inset values from one device.

## MOB-05. Use consistent side margins

**Why:** A fixed horizontal margin keeps content aligned and away from screen edges.

- **Do:** Apply the same page margin on every mobile screen, typically 16-24px, and align headers, titles and grids to it.
- **Do:** Let only intentional full-bleed elements such as images and carousels break the margin.
- **Avoid:** Text or cards touching the screen edges, or different margins on different screens.

## MOB-06. Design for the full range of phone sizes

**Why:** Phones vary widely in width and height; layouts must adapt without per-device tweaks.

- **Do:** Verify layouts from about 320pt to 440pt wide and on short screens.
- **Do:** Use fluid widths, flex and grid rather than fixed pixel layouts.
- **Do:** Check that primary actions and key content are not pushed off-screen on short devices.
- **Avoid:** Designing for one device size and assuming it scales.

## MOB-07. Use horizontal rows with a peek for browsable sections

**Why:** Horizontally scrolling rows let users see more categories without a long vertical scroll.

- **Do:** Lay out each category as one horizontal row under its heading, with the next card partly visible to signal more.
- **Do:** Use scroll snapping and offer a "See all" route.
- **Avoid:** Rows whose cards fit the viewport exactly, hiding that more content exists.
- **Note:** Content in carousels is easy to miss; put the most important items first.

## MOB-08. Keep push notifications rare and useful

**Why:** Too many or irrelevant notifications lead people to disable them or uninstall the app.

- **Do:** Send only notifications with clear value, written short and specific, and targeted to the relevant users.
- **Do:** Let users control categories and frequency, batch updates and respect quiet hours.
- **Avoid:** Bursts of near-identical notifications or generic marketing pushes to everyone.
