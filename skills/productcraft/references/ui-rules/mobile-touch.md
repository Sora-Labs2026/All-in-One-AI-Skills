# UI rules: Mobile and touch

Touch targets, thumb reach, safe areas, margins and device sizes. Rule IDs use the `MOB-` prefix; cite them in change reports.

## MOB-01. Make touch targets at least 44pt

**Why:** Small hit areas cause missed taps, especially on icon-only controls.

- **Do:** Make every tappable element at least 44x44pt (iOS) or 48x48dp (Android).
- **Do:** Keep icons visually small if desired (about 24px) and enlarge the hit area with padding or an invisible overlay; on the web, @media (pointer: coarse) { .icon-btn { padding: 12px } } turns a 20px glyph into a 44px target.
- **Do:** Give text buttons and links a full-height hit area even when the text is small.
- **Do:** Re-check every control's hit area after a spacing or density pass; extra whitespace can still leave steppers and chips below 44pt.
- **Avoid:** Hit areas that match a 16-24px glyph exactly, such as back, close, favorite or password-visibility icons.
- **Avoid:** Controls that need a hover state before they work; on touch, a first tap may only apply the hover style.
- **Note:** WCAG 2.2 sets 24x24 CSS px as the AA minimum and 44x44 as enhanced; platform guidance asks for 44pt/48dp.

## MOB-02. Space touch targets so taps land where intended

**Why:** Crowded targets cause mis-taps; the smaller the target, the more space it needs.

- **Do:** Keep hit areas from overlapping and leave at least 8px between adjacent 44-48px targets.
- **Do:** For targets smaller than 24x24 CSS px, apply the WCAG 2.2 SC 2.5.8 spacing test: a 24px circle centered on each target must not intersect another target or another target's circle.
- **Avoid:** Tiny icon buttons packed edge to edge or against screen edges.

## MOB-03. Keep key actions in the thumb zone

**Why:** In one-handed use the bottom of the screen is easiest to reach.

- **Do:** Anchor the main forward action (Continue, Next, Pay) at the bottom of the screen above the safe area; in multi-field forms put it directly after the last field instead, pinning it above the keyboard only on short single-question steps (BTN-05).
- **Do:** Add bottom padding to scroll content so a sticky action never covers the last field.
- **Do:** Keep destructive or rarely used actions out of the easiest reach zone.
- **Avoid:** Critical actions as small targets in the top corners.

## MOB-04. Respect safe areas

**Why:** Content under the status bar, notch or home indicator is obscured or collides with system gestures.

- **Do:** Read insets at runtime: env(safe-area-inset-top/bottom) on the web, with viewport-fit=cover in the viewport meta tag (without it iOS reports 0), SafeAreaView or platform APIs in native code.
- **Do:** Keep the top navigation row clear of the status area and leave the home-indicator zone free of controls, including when the keyboard is open.
- **Avoid:** Hard-coded inset values from one device; top insets range from about 20pt on home-button phones to about 59pt or more on phones with a camera cutout.

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
- **Do:** Let users control categories and frequency, batch updates and respect quiet hours, giving each notification type its own channel or category so it can be muted on its own.
- **Do:** Replace an outdated alert instead of stacking a new one (the same apns-collapse-id on iOS, the same notification tag on Android, since an FCM collapse_key only merges undelivered messages), and group related alerts (thread-id on iOS, setGroup with a summary notification on Android).
- **Avoid:** Bursts of near-identical notifications or generic marketing pushes to everyone.

## MOB-09. Keep forms clear of the keyboard and system bars

**Why:** On phones the keyboard covers half the screen, and inputs under it or the status bar break forms on real devices.

- **Do:** Wrap native forms in a keyboard-avoiding container (padding behavior on iOS; adjustResize usually covers Android) around a scroll view with keyboardShouldPersistTaps="handled", so the first tap on Submit works while the keyboard is up, and pad the bottom with the safe-area inset or at least 16px (Math.max(insets.bottom, 16)).
- **Do:** Chain fields with a "next" return key and make the last field submit.
- **Do:** On the web, let the form scroll and use scroll-padding with env(safe-area-inset-*) so the focused field and the submit button stay visible; an action pinned on a single-question step sits about 16px above the keyboard (BTN-05).
- **Avoid:** Fixed-height centered columns that cannot scroll when the keyboard opens, or hard-coded status-bar heights.

## MOB-10. Give small custom controls a real role and a larger hit area

**Why:** Tiny checkboxes and inline links are hard to hit and invisible to screen readers without roles and state.

- **Do:** Extend hit areas with padding or hit slop of (target size - visual size) / 2 per side, for example 12-14px around a 16-20pt checkbox for 44pt, or make the whole label row the target, so they reach 44pt (iOS) or 48dp (Android) and never fall below 24x24px (WCAG 2.2 SC 2.5.8).
- **Do:** Give custom checkboxes accessibilityRole="checkbox" with a checked state, or use a native checkbox with a label, and make the label part of the same target.
- **Avoid:** A checkbox built from a plain view with only a press handler, or a tappable square whose label is not tappable.

## MOB-11. Always pair gestures with a tap alternative

**Why:** Swipe, hold, slide and drag gestures are undiscoverable for some people and impossible for others.

- **Do:** Label both outcomes of a swipe as real buttons (for example "False" and "True") and support arrow keys.
- **Do:** Reserve slide-to-confirm and press-and-hold for rare, deliberate commitments and also accept tap-then-confirm or Enter; a slide-to-pay control states the exact amount (BTN-14).
- **Do:** Make holds clearly longer than the system long press but short (about 0.8-1.5s, never several seconds) with a ring that fills in proportion; on early release drain it back and say nothing happened, and cancel on pointercancel or when the pointer leaves.
- **Do:** For swipe rows, let a short swipe reveal actions without firing them and a long swipe past most of the row commit only the outermost action, signalled before release; keep each revealed action at least 44px wide and destructive actions on the trailing side.
- **Do:** For press-and-hold recording, respond on touch-down with feedback that extends beyond the fingertip, offer slide to cancel and a lock for long recordings, and also allow tap to start and tap to stop.
- **Do:** Add a short hint near any non-standard gesture ("Pull and release").
- **Avoid:** Swipe-only answers, slide-only buttons for routine actions, or drag as the only way to complete a task.
- **Note:** WCAG 2.2 SC 2.5.7 Dragging Movements (AA) requires a single-pointer alternative to any drag.
