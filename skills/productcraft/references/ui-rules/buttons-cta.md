# UI rules: Buttons and calls to action

Hierarchy, states, sizing, placement and labels. Rule IDs use the `BTN-` prefix; cite them in change reports.

## BTN-01. One primary action per view, with a clear hierarchy

**Why:** Users should spot the main action instantly; secondary and tertiary styles support it instead of competing.

- **Do:** Style the primary action as a solid fill in the accent color, one per view or section.
- **Do:** Style secondary actions as outlined or neutral filled buttons, and minor actions as text buttons.
- **Do:** Keep height, radius and type identical across levels so only emphasis changes, and repeat the same mapping on every repeated card.
- **Avoid:** Two filled primary buttons side by side, or a different saturated color on each button.
- **Avoid:** Switching which action is filled between cards in the same list.

## BTN-02. Design every state of every button

**Why:** Visible states tell users what is interactive, what is happening and what is unavailable.

- **Do:** Define default, hover, pressed, focus-visible (2px ring with offset), disabled and loading states for every variant, including icon-only buttons.
- **Do:** Keep the button's width fixed while loading and block repeat presses.
- **Do:** Animate state changes briefly (about 100-200ms) and disable the motion under prefers-reduced-motion.
- **Avoid:** A pressed state that looks like disabled, a disabled state that looks enabled, or removed focus outlines.
- **Note:** Disabled buttons are exempt from contrast minimums but should stay legible; consider saying why an action is unavailable.

## BTN-03. Size buttons for touch and balance their padding

**Why:** Consistent height and padding make buttons easy to hit and visually balanced.

- **Do:** Make touch buttons at least 44pt (iOS) or 48dp (Android) tall; pointer-only interfaces can use 36-40px with an enlarged hit area.
- **Do:** Use roughly twice as much horizontal as vertical padding (for example 12-16px vertical, 24-32px horizontal).
- **Do:** With a leading icon, use slightly less padding on the icon side and a 6-8px icon-label gap.
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
- **Do:** In forms, put the submit button directly after the last field, aligned with the fields.
- **Do:** In dialogs, align footer buttons the way the target platform does, and keep the order identical across the product.
- **Avoid:** The primary action as a small button in a top corner of a mobile screen, or button order that changes between similar screens.
- **Note:** Primary-left versus primary-right ordering differs by platform; consistency matters more than either choice.

## BTN-06. Make the recommended option stand out

**Why:** Among similar items, the one that differs is noticed and remembered.

- **Do:** Give the recommended plan or default choice one distinct treatment, such as an accent border, a filled button or a "Recommended" badge.
- **Do:** Keep the other options visually quieter and emphasize only one item per group.
- **Avoid:** Emphasis by color alone, or emphasis used to push users toward an option against their interest.

## BTN-07. Make buttons look like buttons and links look like links

**Why:** Users expect buttons to act and underlined text to navigate; mixing the two causes mistakes.

- **Do:** Give buttons a filled or bordered shape with padding.
- **Do:** Use button elements for actions and anchor elements for navigation, and reserve underlines for links.
- **Avoid:** Actions shown as bare colored text, or an underlined link inside a row of action buttons.

## BTN-08. Pair labels with a meaningful icon when it helps

**Why:** A recognizable icon beside the label speeds scanning.

- **Do:** Add a leading icon that matches the action (for example a phone glyph on "Call"), sized to the label line height.
- **Do:** Keep the text label and mark the icon aria-hidden.
- **Avoid:** Ambiguous icons, or icon-only buttons for uncommon actions.

## BTN-09. Show keyboard shortcuts on desktop actions

**Why:** A shortcut hint on the control teaches the faster path at the moment it is needed.

- **Do:** Render the shortcut as a small kbd chip inside or beside the button, styled quieter than the label.
- **Do:** Show the platform's modifier (Cmd on macOS, Ctrl elsewhere) and mirror it in the tooltip and aria-keyshortcuts.
- **Avoid:** Shortcut chips on touch-only devices, or shortcuts documented nowhere in the UI.
