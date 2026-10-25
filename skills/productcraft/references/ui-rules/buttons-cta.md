# UI rules: Buttons and calls to action

Hierarchy, states, sizing, placement and labels. Rule IDs use the `BTN-` prefix; cite them in change reports.

## BTN-01. One primary action per view, with a clear hierarchy

**Why:** Users should spot the main action instantly; secondary and tertiary styles support it instead of competing.

- **Do:** Style the primary action as a solid fill in the accent color, one per view or section.
- **Do:** Style secondary actions as outlined or neutral filled buttons (for example a light gray fill with near-black text, or a pale accent tint with dark accent text), and minor actions as text buttons.
- **Do:** Lower emphasis only through fill and border (filled, then outlined or neutral, then text), and keep every enabled label at 4.5:1 or more.
- **Do:** Keep height, radius and type identical across levels so only emphasis changes, and repeat the same mapping on every repeated card.
- **Do:** Keep Cancel and Back neutral rather than red, and give a destructive action that sits beside Save an outlined or text style, set apart from it.
- **Avoid:** Two filled primary buttons side by side, or a different saturated color on each button.
- **Avoid:** Switching which action is filled between cards in the same list.
- **Avoid:** A secondary made from a lighter tint of the primary with the white label kept, or gray, faded labels that make enabled buttons look disabled.

## BTN-02. Design every state of every button

**Why:** Visible states tell users what is interactive, what is happening and what is unavailable.

- **Do:** Define default, hover, pressed, focus-visible, disabled and loading states for every variant, including icon-only buttons.
- **Do:** Derive hover, focus and pressed from one formula, such as an overlay of the label color at about 8% for hover and 10-12% for focus and pressed, or one or two steps darker on the color ramp.
- **Do:** Give each state's fill its own on-color label token, switched together with the fill, and check every pair; with white labels, darken on hover rather than lighten.
- **Do:** Draw focus as outline: 2px solid with outline-offset: 2px in a color that reaches at least 3:1 against the surrounding background (WCAG 2.2 SC 1.4.11), with a two-tone ring (light inside, dark outside) on colored or image surfaces, and add it without switching the fill to the pressed color.
- **Do:** Render disabled as a neutral container with dimmed content (for example about 12% and 38% of the text color), not a pale tint of the accent.
- **Do:** Keep the button's width fixed while loading and block repeat presses.
- **Do:** Show the pressed state immediately on press (a transition of about 100ms or less), use about 150-200ms for hover, focus and color changes, and disable the motion under prefers-reduced-motion.
- **Avoid:** A pressed state that looks like disabled, a disabled state that looks enabled, or removed focus outlines.
- **Avoid:** Pale tinted focus halos, focus drawn only with box-shadow (forced-colors mode removes it), or a hover shade that drops the label below 4.5:1.
- **Note:** Disabled buttons are exempt from contrast minimums but should stay legible; consider saying why an action is unavailable.

## BTN-03. Size buttons for touch and balance their padding

**Why:** Consistent height and padding make buttons easy to hit and visually balanced.

- **Do:** Make touch buttons at least 44pt (iOS) or 48dp (Android) tall; pointer-only interfaces can use 36-40px with an enlarged hit area.
- **Do:** Use roughly twice as much horizontal as vertical padding (for example 12-16px vertical, 24-32px horizontal).
- **Do:** With a leading icon, keep the full padding on the label side, take about 4-8px off the icon side (for example 16px and 24px) and use a 6-8px icon-label gap.
- **Do:** Set labels at about 14-17px on mobile in a medium or semibold weight.
- **Avoid:** Equal tiny padding on all sides, or primary buttons shorter than 44pt on touch screens.

## BTN-04. Make primary mobile buttons full width

**Why:** On narrow screens, full-width buttons are bigger targets and look finished.

- **Do:** Span the content width inside the platform side margins (typically 16-24px).
- **Do:** Stack paired actions vertically, with the secondary in a lower-emphasis style.
- **Avoid:** Small fixed-width buttons floating mid-screen, or buttons that touch the screen edges.
- **Note:** On wide desktop layouts, size buttons to content or a max width instead.

## BTN-05. Place actions where the task ends

**Why:** Actions placed where the eye and thumb finish their path are found and reached faster.

- **Do:** On mobile, anchor the main forward action at the bottom of the screen, inside the thumb zone and above the safe area.
- **Do:** In forms, put the submit button directly after the last field, aligned with the fields, and keep it there on long scrolling forms on phones.
- **Do:** On short single-question phone steps, pin the forward action about 16px above the keyboard and safe area, with a keyboard-avoiding view natively or, on the web, a visualViewport resize listener or the viewport meta's interactive-widget=resizes-content.
- **Do:** In dialogs, align footer buttons the way the target platform does (where none applies, right-align them with the primary rightmost), and keep the order identical across the product.
- **Do:** In unsaved-changes dialogs, keep Save in the usual primary slot and move Discard to the far side in a low-emphasis style, so a habitual click never destroys work.
- **Do:** In quick-add lists, put the add button in the same row as its input and also submit on Enter, rather than below a list that pushes it down with every item.
- **Avoid:** The primary action as a small button in a top corner of a mobile screen, or button order that changes between similar screens.
- **Note:** Primary-left versus primary-right ordering differs by platform; consistency matters more than either choice.

## BTN-06. Make the recommended option stand out

**Why:** Among similar items, the one that differs is noticed and remembered.

- **Do:** Give the recommended plan or default choice one distinct treatment, such as an accent border, a filled button or a "Recommended" badge.
- **Do:** Keep the other options visually quieter and emphasize only one item per group.
- **Avoid:** Emphasis by color alone, or emphasis used to push users toward an option against their interest.

## BTN-07. Make buttons look like buttons and links look like links

**Why:** Users expect buttons to act and underlined text to navigate; mixing the two causes mistakes.

- **Do:** Give primary and secondary buttons a filled or bordered shape with padding.
- **Do:** Make a tertiary text button a real button: a semibold accent label at 4.5:1 or more, no underline, button padding with a hit area at least 44px tall on touch, and a hover and pressed background.
- **Do:** Use button elements for actions and anchor elements for navigation, and reserve underlines for links.
- **Do:** If a soft extruded (neumorphic) style is required, add a border or fill step of at least 3:1 against the page and keep the label at 4.5:1.
- **Avoid:** Bare colored text with no padding or state feedback as an action, or an underlined link inside a row of action buttons.
- **Avoid:** Pressed or selected states shown only by a light-and-dark shadow pair on a fill that matches the page.

## BTN-08. Pair labels with a meaningful icon when it helps

**Why:** A recognizable icon beside the label speeds scanning.

- **Do:** Add a leading icon that matches the action (for example a phone glyph on "Call"), sized to the label line height.
- **Do:** Keep the text label and mark the icon aria-hidden.
- **Avoid:** Ambiguous icons, or icon-only buttons for uncommon actions.

## BTN-09. Show keyboard shortcuts on desktop actions

**Why:** A shortcut hint on the control teaches the faster path at the moment it is needed.

- **Do:** Render the shortcut as a small kbd chip inside or beside the button, styled quieter than the label.
- **Do:** Show the platform's modifier (Cmd on macOS, Ctrl elsewhere) and mirror it in the tooltip and aria-keyshortcuts.
- **Do:** In command palettes and launchers, keep a footer that names what Enter does for the highlighted item and which key opens more actions, and update it as the selection moves.
- **Avoid:** Shortcut chips on touch-only devices, or shortcuts documented nowhere in the UI.

## BTN-10. Explain unavailable actions instead of silently disabling them

**Why:** A plain disabled button cannot take focus and does not say what is missing.

- **Do:** Use aria-disabled="true" so the button stays focusable, and on activation move focus to the first invalid field.
- **Do:** Show a short live hint near the button that says what is still needed, and update it as fields become valid.
- **Do:** Let the primary label follow the state (Print, Re-print, Print next) and tint the suggested next action.
- **Avoid:** Disabled buttons with no explanation, or actions that stay clickable and fail silently.

## BTN-11. Keep the main action reachable

**Why:** A persistent, high-contrast primary action converts better than one buried in the hero.

- **Do:** Place the main action as a filled button at the right of a sticky header, paired with at most one quieter secondary in the hero.
- **Do:** Size any floating help or chat button at 48-56px with an accessible name, clear of content and safe areas.
- **Do:** On long mobile product pages, show a sticky bottom bar with the item name, price and main action once the hero action scrolls out of view, at least 56px tall plus env(safe-area-inset-bottom), with matching bottom padding on the page so it never covers the last content.
- **Avoid:** Several filled buttons of equal weight, or floating buttons that cover form fields or the last line of content.

## BTN-12. Give hover and press feedback without moving the hit box

**Why:** Subtle scale or lift confirms a target, but if the element under the pointer moves, hover flickers and clicks miss.

- **Do:** Use small changes (hover scale about 1.03-1.05, press about 0.95-0.97, card lift 2-5px) with ease-out: hover in over about 150-200ms and out slightly faster, press within about 100ms, and release over about 150-250ms with at most a slight overshoot, settled within about 400ms.
- **Do:** Animate an inner layer and keep the outer button or link box still.
- **Do:** Name the animated properties in transition-property and mirror the effect on :focus-visible.
- **Do:** Hide secondary row actions until hover only inside @media (hover: hover) and (pointer: fine), reveal them on :focus-within as well, and keep them visible or in an overflow menu elsewhere.
- **Avoid:** transition: all, wobbly springs that take most of a second to settle, or hover as the only way to reveal an action.

## BTN-13. Write identity-provider buttons consistently

**Why:** Recognizable, consistently worded provider buttons speed sign-in without competing with the main path.

- **Do:** Use "Continue with <provider>" text with the provider's logo, at equal width and at least 48px tall on mobile, under an "or" divider.
- **Do:** Give every provider button the same height and fill treatment, using each provider's approved color variants, and signal any preference by order rather than by restyling one of them.
- **Do:** Follow each provider's button guidelines and give any icon-only variant an accessible name.
- **Avoid:** Unlabeled logo circles, one provider as a full button and the others as text links, or provider buttons styled louder than the primary sign-in when email is the main path.
- **Note:** Platform sign-in guidelines require their button to be no smaller or harder to find than other providers' buttons.

## BTN-14. Put the amount in purchase buttons

**Why:** Showing the total inside the button makes the commitment explicit and removes a scan step.

- **Do:** Label purchase buttons with the verb and the exact amount ("Pay $248.00", "Add to order, $14.00") and update it as quantity changes.
- **Do:** When the price changes after the first quote, show the previous amount struck through and labeled as the old price, the new amount and the signed difference ("+$4.30"), and put the new amount in the accept button.
- **Do:** Place a quantity stepper beside it with labeled minus and plus buttons of at least 44x44px.
- **Avoid:** A generic "Continue" on the final charge step, or a button amount that disagrees with the summary or still shows an earlier quote.

## BTN-15. Add friction only for the riskiest choice

**Why:** Confirmation proportional to consequence protects users without slowing ordinary choices.

- **Do:** When the user selects the most severe option, reveal an acknowledgement checkbox that states the consequence in plain words, and keep the action aria-disabled (still focusable) and visibly unavailable until it is checked; if it is activated early, move focus to the checkbox and show a short live hint.
- **Do:** Relabel the action to describe the consequence and switch it to the warning style.
- **Avoid:** Confirmation steps on every option.
- **Avoid:** An action that looks the same before and after the acknowledgement is checked.

## BTN-16. Never make the decline option evasive

**Why:** Buttons that move away, shrink or cannot be pressed remove real choice and block keyboard, touch and motor-impaired users.

- **Do:** Give accept and decline stable positions and equal reachability, and differentiate them only by emphasis.
- **Do:** Set the decline option at body text size or larger, at 4.5:1 contrast, with neutral wording such as "No thanks".
- **Avoid:** A "No" button that jumps away on hover, or an "accept" option that grows each time the user tries to decline.
- **Avoid:** A tiny, faint decline link, or decline wording that shames the user.
- **Note:** Acceptable only as an obvious joke in a toy; in consent, payment or account flows it is a dark pattern.
