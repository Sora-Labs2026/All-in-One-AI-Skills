# UI rules: Screen patterns

Dashboards, settings, search, onboarding and landing pages. Rule IDs use the `SCR-` prefix; cite them in change reports.

## SCR-01. Build dashboards around the decision they support

**Why:** Every widget should help users understand or act; decorative or redundant widgets bury the key numbers.

- **Do:** Lead with one primary metric and its trend, with a period selector.
- **Do:** Follow with 3-4 secondary KPI cards showing value and change, then a short recent-items table with status pills and "View all".
- **Do:** Show the primary value large and the raw numbers smaller and muted.
- **Avoid:** Ten or more small widgets, upsell cards and icon grids on one screen, or uniform "Label: value" lists with equal weight.

## SCR-02. Show statuses as labeled pills

**Why:** Status written as small plain text blends into metadata; colored pills are scannable.

- **Do:** Render statuses as small pill badges with a consistent color per status, keeping the status word inside the pill.
- **Do:** Check the text contrast against the pill fill.
- **Avoid:** Status as faint gray text styled like other metadata, or color without a label.

## SCR-03. Group settings into titled sections

**Why:** A long flat list makes people read every row; themed groups let them jump to the right cluster.

- **Do:** Split settings into groups such as Security, General and Legal, each with a small muted label and its own inset block.
- **Do:** Put session and destructive actions ("Log out", "Close account") in a separate final group.
- **Avoid:** Twelve or more unrelated rows in one list, or destructive actions mixed with everyday preferences.

## SCR-04. Disclose settings progressively

**Why:** Showing the most-used options first reduces load while details stay one tap away.

- **Do:** Keep frequent settings at the top level and move detailed options into sub-pages opened from chevron rows.
- **Do:** Add quick actions on detail pages, such as a copy button beside each account value.
- **Avoid:** Every option on one screen, or common actions buried several levels deep.

## SCR-05. Add search to long settings

**Why:** Typing a keyword is faster than drilling in and out of sub-screens.

- **Do:** Add a search field under the settings title once the list grows past about 6-8 items.
- **Do:** Match labels, section names and common synonyms, and show each result with its group.
- **Avoid:** Forcing users to browse nested screens to find one option.

## SCR-06. Personalize the account header

**Why:** Showing the user's name and avatar makes the account area feel personal and confirms the right account.

- **Do:** Title the account screen with the user's name and plan, with an avatar, initials fallback and an edit badge.
- **Do:** Keep any offer card secondary and dismissible.
- **Avoid:** Turning the account screen into an ad surface.

## SCR-07. Make search one prominent field with filters on demand

**Why:** Most people just want to type; a wall of filters up front slows everyone down.

- **Do:** Use one full-width input with a magnifier icon and a specific placeholder ("Search products").
- **Do:** Put advanced filters behind a single filter button or panel, submit on Enter and show a clear control only after text is entered.
- **Avoid:** Five or more dropdowns plus extra buttons before anything is typed, or vague placeholders like "Type here".

## SCR-08. Collect sensible defaults during onboarding

**Why:** Gathering key preferences early lets the product start personal instead of blank.

- **Do:** Ask one topic per screen with a progress bar and a single Continue button.
- **Do:** Reuse the answers to prefill the profile and settings, keeping every value editable, and flag anything unconfirmed inline.
- **Avoid:** Asking again later for information already collected.

## SCR-09. Keep preference setup skippable

**Why:** A short preference step personalizes the experience, but forcing it traps users.

- **Do:** Offer a visible Skip with sensible defaults, and let users change preferences later in settings.
- **Avoid:** Mandatory wizards, or asking for preferences the product does not use.

## SCR-10. Open with a clear welcome screen

**Why:** The first screen sets expectations and trust.

- **Do:** Pair one relevant visual with a short value headline.
- **Do:** Offer a filled "Get started" and a lower-emphasis "Log in", with page dots if it is a short carousel.
- **Avoid:** A bare login form with no context, or a long animated splash screen.

## SCR-11. Keep hero sections focused

**Why:** One message, one action and one trust signal communicate value within seconds.

- **Do:** Use a top bar with the logo left, a few short links and one distinct action on the right.
- **Do:** Use one headline of a few short lines, one supporting sentence, one primary call to action and a trust signal such as a rating or outcome figure.
- **Do:** Pair the text with one dominant visual, keep text on calm image areas, and stack headline above the action on mobile.
- **Avoid:** Several equally weighted calls to action, long navigation menus, or competing badges and decorations.
