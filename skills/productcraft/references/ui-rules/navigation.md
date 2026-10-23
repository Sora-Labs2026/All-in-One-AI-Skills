# UI rules: Navigation

Navigation patterns, labels, active states, sidebars, breadcrumbs and conventions. Rule IDs use the `NAV-` prefix; cite them in change reports.

## NAV-01. Use one primary navigation pattern

**Why:** Combining navigation types splits destinations and makes the structure hard to learn.

- **Do:** On mobile apps, use a bottom tab bar with 3-5 top-level destinations.
- **Do:** Put overflow destinations such as settings into a Profile or More tab.
- **Do:** Keep the top bar for the screen title, search and notifications.
- **Avoid:** A hamburger menu on top of an existing tab bar, or primary destinations hidden in a drawer when a tab bar fits.
- **Note:** A menu drawer is fine for secondary links; it lowers discoverability for anything important.

## NAV-02. Label every navigation icon

**Why:** Icons alone are ambiguous; labels make navigation predictable.

- **Do:** Show an icon plus a short text label for every tab, and color both when active.
- **Do:** Give icon-only controls elsewhere an accessible name and a tooltip.
- **Avoid:** Icon-only tab bars with abstract icons, or vaguely named menus.

## NAV-03. Make the current location unmistakable

**Why:** Users orient themselves by the active item; a weak active state leaves them lost.

- **Do:** Mark the active item with at least two cues: a tinted pill or indicator plus a bolder label or filled icon.
- **Do:** Use one accent color for the active item and one neutral for inactive items, with inactive icons still at about 3:1 contrast.
- **Do:** Set aria-current="page" on the active link.
- **Avoid:** A different color for every nav icon, or a subtle color shift as the only active cue.

## NAV-04. Pick the navigation component that fits the scope

**Why:** Each component implies a different scope; the right one tells users where they are.

- **Do:** Use a tab bar or sidebar for top-level app sections, in-page tabs for views of one page, breadcrumbs for deep hierarchies and pagination for long result sets.
- **Do:** In pagination, highlight the current page, show previous/next arrows and use an ellipsis for skipped ranges.
- **Avoid:** Tabs for sequential steps (use a stepper), or pagination without a current-page indicator.

## NAV-05. Breadcrumbs for deep hierarchies

**Why:** A visible path orients users and lets them jump up levels without repeated Back taps.

- **Do:** Show breadcrumbs on pages three or more levels deep.
- **Do:** Link every crumb except the last; render the current page as plain text with aria-current="page".
- **Do:** On narrow screens, collapse middle levels into an ellipsis that expands on tap.
- **Avoid:** Breadcrumbs as a replacement for primary navigation, or on flat one-level sites.

## NAV-06. Follow the conventions people already know

**Why:** People learn habits from many other products; familiar layouts need no relearning.

- **Do:** Put the logo top-left, inline with the main navigation, linked to home (mirrored for right-to-left languages).
- **Do:** Use conventional icons: magnifier for search, bell for notifications, house for home, person for profile, gear for settings.
- **Do:** Reuse standard gestures and behaviors such as swipe back and pull to refresh.
- **Avoid:** Novel icons for common concepts, or a centered logo above a separate row of links on content and product sites.

## NAV-07. Put account and settings where people look for them

**Why:** People look for settings in a few conventional spots; anywhere else feels hidden.

- **Do:** In simpler apps, make the avatar in the header open profile and settings.
- **Do:** In larger apps, give Profile or More its own tab-bar item.
- **Do:** Keep the entry point in the same place on every top-level screen.
- **Avoid:** Settings reachable from only one screen or behind an unlabeled control.

## NAV-08. Structure sidebars top to bottom

**Why:** A predictable sidebar structure lets users orient themselves and switch sections quickly.

- **Do:** Order zones as logo with collapse toggle, optional search, main items under small section labels, secondary groups, settings and help, then the account or workspace switcher.
- **Do:** Use about 240px expanded width and a 64-80px icon rail when collapsed, with tooltips and accessible labels on every icon.
- **Do:** Use about 40px item rows with small gaps, consistent horizontal inset, and counts as right-aligned badges.
- **Avoid:** One long unlabeled list of links, or an icon-only rail without labels or tooltips.

## NAV-09. Limit sidebar nesting to two levels

**Why:** One expandable sub-level keeps related pages together; deeper nesting becomes hard to scan.

- **Do:** Let a primary item expand with a chevron to reveal indented second-level items, connected by a thin guide line.
- **Do:** Move deeper structure into in-page tabs or the page itself.
- **Avoid:** Third-level nesting inside the sidebar.

## NAV-10. Use the sidebar foot for at most one promo card

**Why:** The space below navigation is visible on every page without blocking tasks.

- **Do:** Place one compact card (usage meter with upgrade, trial offer or feature teaser) above settings and account.
- **Do:** Give it a close control, hide it in the collapsed rail and keep its button quieter than the page's primary action.
- **Avoid:** Several promo cards, or a card that pushes navigation out of view on short screens.

## NAV-11. Give tab bars full-size hit areas and safe-area padding

**Why:** Tab items need generous touch areas and must stay clear of the system home indicator.

- **Do:** Make each tab's hit area fill its whole column, with a 2-4px gap between icon and label.
- **Do:** Pad the bar's bottom with env(safe-area-inset-bottom) or the platform equivalent, and add bottom padding to the scroll content so the bar never covers it.
- **Avoid:** Labels sitting on the home indicator, or only the icon glyph being tappable.
