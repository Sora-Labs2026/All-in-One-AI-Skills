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
- **Do:** Treat a bar that shows the label only on the active tab (an expanding pill) as icon-only for its inactive tabs: keep each one's accessible name (not removed with display: none) and give its icon at least 3:1 against the bar (NAV-03).
- **Do:** Size tab labels at about 10-12pt (never smaller) under icons of about 24pt.
- **Do:** Give icon-only controls elsewhere an accessible name and a tooltip.
- **Avoid:** Icon-only tab bars with abstract icons, or vaguely named menus.

## NAV-03. Make the current location unmistakable

**Why:** Users orient themselves by the active item; a weak active state leaves them lost.

- **Do:** Mark the active item with at least two cues: a tinted pill or indicator plus a bolder label or filled icon.
- **Do:** Use one accent color for the active item and one neutral for inactive items: inactive icons need at least 3:1, and every label, including an accent-colored active label, at least 4.5:1 (for example #707070 or darker on white or #F6F6F6).
- **Do:** When the active label turns bold, reserve its bold width (a hidden bold copy in ::after with content: attr(data-label), or a variable font's grade axis) so neighboring items do not shift.
- **Do:** Set aria-current="page" on the active link.
- **Avoid:** A different color for every nav icon, or a subtle color shift as the only active cue.
- **Avoid:** Fading inactive labels below 4.5:1 to make the active item stand out.

## NAV-04. Pick the navigation component that fits the scope

**Why:** Each component implies a different scope; the right one tells users where they are.

- **Do:** Use a tab bar or sidebar for top-level app sections, in-page tabs for views of one page, breadcrumbs for deep hierarchies and pagination for long result sets.
- **Do:** In pagination, highlight the current page, show previous/next arrows, render the first, last and current page with its neighbors with an ellipsis for skipped ranges, and compute the page count as ceil(total / pageSize); add a "Go to page" field for very long sets.
- **Do:** When in-page tabs overflow, scroll the row horizontally with edge fades (plus previous/next chevrons for pointer users) and keep the active tab in view; on phones switch to a section picker rather than shrinking tabs below 44px.
- **Avoid:** Tabs for sequential steps (use a stepper), or pagination without a current-page indicator.
- **Avoid:** Tabs wrapped onto a second row, or hundreds of page links.

## NAV-05. Breadcrumbs for deep hierarchies

**Why:** A visible path orients users and lets them jump up levels without repeated Back taps.

- **Do:** Show breadcrumbs on pages three or more levels deep.
- **Do:** Wrap an ordered list in nav aria-label="Breadcrumb" and link every crumb except the last; render the current page as plain text in the body text color with aria-current="page".
- **Do:** Draw separators with CSS (li + li::before) or aria-hidden elements so screen readers do not announce them.
- **Do:** On narrow screens, collapse middle levels into an ellipsis that expands on tap.
- **Avoid:** Breadcrumbs as a replacement for primary navigation, or on flat one-level sites.
- **Avoid:** A current crumb in the link or accent color, which reads as a link.

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

- **Do:** Order zones as logo with collapse toggle, optional search, main items under small section labels, secondary groups, settings and help, then the account or workspace switcher set off by a divider.
- **Do:** Use about 240px expanded width and a 64-80px icon rail when collapsed, with tooltips and accessible labels on every icon.
- **Do:** Use about 40px item rows with about 4px gaps, a consistent side inset of about 16px, about 24px between groups, and counts as right-aligned badges.
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

## NAV-12. Expand search in place, with focus and an easy exit

**Why:** Folding search into an icon saves space only if the field opens instantly, takes focus and closes predictably.

- **Do:** Make the trigger a button with aria-label="Search" and aria-expanded; on activation expand the field over about 200-250ms and move focus into it.
- **Do:** Use input type="search" with a specific placeholder, a labeled clear button, and close on Escape or outside click with focus returned to the trigger.
- **Do:** Reserve or overlay the space so neighboring links do not jump, and optionally offer a shortcut such as / or Ctrl/Cmd+K with a visible hint.
- **Avoid:** Search that opens on hover only, or an expanded field covering links that stay tabbable underneath.

## NAV-13. Collapse sidebars without losing wayfinding

**Why:** A collapsed rail frees space, but people still need to see where they are and what each icon means.

- **Do:** Toggle with a button that has aria-expanded, aria-controls and a name that flips between "Collapse sidebar" and "Expand sidebar".
- **Do:** Keep the active highlight, section dividers and accessible counts in rail mode, with tooltips on hover and keyboard focus.
- **Do:** Animate width over about 200-300ms with icons in a fixed-width leading column so they stay put, and fade labels out first inside a column with overflow: hidden and white-space: nowrap.
- **Do:** Persist the choice, and default to the rail on medium widths and an off-canvas drawer on phones.
- **Avoid:** Collapsed badges that become an unlabeled dot, or labels hidden with no tooltip or accessible name.
- **Avoid:** Icons that shift sideways, or labels re-truncated with an ellipsis on every frame, while the width animates.

## NAV-14. Derive the active item from the URL

**Why:** When the active state comes from the route, it can never disagree with what is on screen.

- **Do:** Use the router's link component (for example a NavLink) so the active class and aria-current="page" follow the current route.
- **Do:** Generate navigation items from one data array of name, path and icon.
- **Do:** Make hover and active look different so people do not lose their place while moving the pointer: give hover only a faint tint (about 6-10% of the text color) and keep the indicator, fill and semibold label for the current item.
- **Avoid:** A separate piece of state for the active tab that can drift from the URL.
- **Avoid:** A hover state identical to the current-page state, or a sliding hover underline that leaves no visible current location.

## NAV-15. Use navigation semantics for sections and tab semantics for panels

**Why:** Screen readers announce these differently, and each needs different keyboard behavior.

- **Do:** Use nav with links and aria-current="page" for app sections, including bottom tab bars.
- **Do:** Use role="tablist", role="tab" with aria-selected and aria-controls, a roving tabindex and arrow keys only for in-page panels.
- **Do:** Select tabs as focus moves when panels render instantly, and only on Enter or Space when panels load slowly; support Home and End, let Tab move into the panel (tabindex="0" on a panel with nothing focusable), and draw focus as a ring distinct from the selected indicator.
- **Avoid:** role="tablist" with no tab panels, or tabs built from divs with click handlers.

## NAV-16. Hide bars on scroll only with a threshold

**Why:** Hiding navigation while reading down and restoring it on scroll up gives content room without losing wayfinding.

- **Do:** Hide the bottom or top bar after a meaningful downward scroll (about 10px or more) and restore it on any upward scroll or at the top.
- **Do:** Hide the bar over about 200-250ms and bring it back faster (about 150ms), and let content extend under the bar so the layout does not jump.
- **Do:** Keep the title bar pinned (position: sticky) and keep labels on the restored bar.
- **Avoid:** Toggling the bar on tiny scroll jitters.

## NAV-17. Open submenus as disclosures, not hover traps

**Why:** Nested sections must open for keyboard and touch users and stay open while the pointer crosses gaps.

- **Do:** Make the parent a button with aria-expanded controlling a list of links, visually attached to its parent, opening on click, Enter and Space, staying open while focus or the pointer is inside, and closing on Escape and outside click.
- **Do:** For pointer users, keep the submenu open while the pointer moves toward it (a safe triangle toward the submenu, or a close delay of about 300ms), and close it promptly once the pointer leaves that path.
- **Do:** Highlight the current child item.
- **Avoid:** Hover-only flyouts that collapse when the pointer crosses a gap.
- **Avoid:** A collapsed navigation that expands only on hover, which hides every link from touch and keyboard users (WCAG 2.2 SC 2.1.1 and 1.4.13).

## NAV-18. Keep the user's place in long lists

**Why:** Returning from a detail view to the top of a list, or to a page whose rows have shifted, forces people to find their place again.

- **Do:** Choose the paging style by task: numbered pages for reference data people jump through, "Load more" when the footer must stay reachable, infinite scroll only for feeds.
- **Do:** Keep page, cursor, sort and filters in the URL (?page=, ?after=), and use cursor (keyset) pagination when rows are added while people browse.
- **Do:** On Back, restore the scroll position and focus to the row the user opened (save the item id and offset in history.state or sessionStorage; in virtualized lists scroll to the id), and briefly highlight it.
- **Do:** Keep each tab's scroll position when people switch between tabs.
- **Avoid:** Resetting scroll to the top after Back, or offset pages that repeat or skip rows when data changes.
- **Avoid:** Infinite scroll on pages whose footer holds needed links.
