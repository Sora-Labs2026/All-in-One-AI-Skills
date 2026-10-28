# UI rules: Screen patterns

Dashboards, settings, search, onboarding and landing pages. Rule IDs use the `SCR-` prefix; cite them in change reports.

## SCR-01. Build dashboards around the decision they support

**Why:** Every widget should help users understand or act; decorative or redundant widgets bury the key numbers.

- **Do:** Lead with one primary metric, set larger than the rest, with its trend, a period selector and the date range in its heading ("Revenue, 1-30 Sep") rather than a greeting.
- **Do:** Follow with 3-4 secondary KPI cards showing value and change, then a short recent-items table with status pills and "View all".
- **Do:** Show the primary value large and the raw numbers smaller and muted.
- **Avoid:** Ten or more small widgets, upsell cards and icon grids on one screen, or uniform "Label: value" lists with equal weight.
- **Avoid:** A colored icon chip and an identical delta badge on every tile.

## SCR-02. Show statuses as labeled pills

**Why:** Status written as small plain text blends into metadata; colored pills are scannable.

- **Do:** Render statuses as small pill badges with a consistent color per status, keeping the status word inside the pill.
- **Do:** Default to a 100-level tint of the status hue with 800-level text of the same hue (for example #166534 on #DCFCE7, #92400E on #FEF3C7, #991B1B on #FEE2E2, about 6.4-6.8:1), in sentence case at 12px or larger; 700-level green and amber text sits right at 4.5:1 and leaves no margin.
- **Do:** Check the text against the pill fill for at least 4.5:1.
- **Avoid:** White or pale text on saturated mid-tone fills, status as faint gray text styled like other metadata, or color without a label.

## SCR-03. Group settings into titled sections

**Why:** A long flat list makes people read every row; themed groups let them jump to the right cluster.

- **Do:** Split settings into groups such as Security, General and Legal, each with a small label and its own inset block.
- **Do:** Keep section labels at 4.5:1 and show their rank by size, weight or spacing rather than paleness (for example #6D6D72 on #F2F2F7).
- **Do:** Put session and destructive actions ("Log out", "Close account") in a separate final group.
- **Do:** Order a danger zone by severity, giving each row one line on the consequence and whether it can be undone, who may act, and an outlined destructive button, with the filled red button kept for the final confirmation.
- **Avoid:** Twelve or more unrelated rows in one list, or destructive actions mixed with everyday preferences.
- **Avoid:** Pale gray section labels below 4.5:1.

## SCR-04. Disclose settings progressively

**Why:** Showing the most-used options first reduces load while details stay one tap away.

- **Do:** Keep frequent settings at the top level and move detailed options into sub-pages opened from chevron rows.
- **Do:** Add quick actions on detail pages, such as a copy button beside each account value.
- **Do:** In dense settings, mark values changed from their default and offer a per-setting reset, with a count such as "3 modified" in the section header.
- **Avoid:** Every option on one screen, or common actions buried several levels deep.

## SCR-05. Add search to long settings

**Why:** Typing a keyword is faster than drilling in and out of sub-screens.

- **Do:** Add a search field under the settings title once the list grows past about 6-8 items.
- **Do:** Match labels, section names and common synonyms, show each result with its path (Section › Group › Setting) and the matched text highlighted, and let Enter jump to and focus the setting itself.
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

**Why:** One message, one action and real proof communicate value within seconds.

- **Do:** Use a top bar with the logo left, a few short links and one distinct action on the right.
- **Do:** Use one headline of about 4-8 words and at most two lines at phone and desktop widths (text-wrap: balance), one supporting sentence beneath it and one primary call to action, cutting words before shrinking the type.
- **Do:** Add a trust signal only if a real, sourced one exists (a rating with its scale and count, a verified outcome figure); otherwise let the product itself, shown large, be the proof.
- **Do:** Pair the text with one dominant visual, keep text on calm image areas, and stack headline above the action on mobile.
- **Avoid:** Several equally weighted calls to action, long navigation menus, or competing badges and decorations.
- **Avoid:** Invented ratings, logos or user counts.

## SCR-12. Lay out sign-in screens predictably

**Why:** A familiar sign-in layout lets people and password managers finish quickly.

- **Do:** Order the card as a heading with the product name and a one-line value subtitle (not a generic welcome), fields, "remember me" with its duration beside "Forgot password?", full-width primary button, an "or continue with" divider, equal-width provider buttons, then a sign-up link.
- **Do:** On desktop, cap the form column at about 360-420px beside an optional visual panel; on mobile show the form first.
- **Do:** Keep the same shell for follow-up steps (code entry, password reset) so the flow feels continuous.
- **Do:** Design distinct failures: one generic message for wrong credentials ("Email or password is incorrect"), the retry time and a reset link for throttling or lockout, and an inline resend link for an unverified email.
- **Do:** When core features do not need an account, offer "Continue without an account" as a quieter option and ask for sign-up at the point of saving or syncing.
- **Avoid:** Essential copy only in a decorative panel that disappears on mobile, or looping animation beside the form.
- **Avoid:** Error messages that reveal whether the account exists or which credential was wrong.

## SCR-13. Never gate a core task behind a playful interaction

**Why:** People who came to sign in or pay should not have to discover a gesture or wait for a character first.

- **Do:** Render the form or main action on load, and let any playful element run alongside it as optional decoration.
- **Do:** If a reveal interaction is kept, also offer a visible, keyboard-operable button and a skip, and keep the form mounted with typed values intact when the decoration is switched off.
- **Avoid:** Hiding a sign-in form until the user pulls a cord, finds a hidden control or completes a game.

## SCR-14. Give every onboarding step one job and a way back

**Why:** Onboarding completes best when each step is short, predictable and skippable where optional.

- **Do:** Keep a back control top-left, Skip top-right on optional steps, a progress bar or dots with an accessible "Step 2 of 4", and one full-width primary button in the same bottom position.
- **Do:** Ask one question per screen, disable Continue until a required choice is made, and keep answers when users go back.
- **Do:** End with a preview of the personalized result and one clear final action.
- **Avoid:** Demanding account creation before showing any value when it can be deferred.

## SCR-15. Show every fee before payment

**Why:** Revealing costs only at the end destroys trust and causes disputes.

- **Do:** Number checkout sections on one page, render shipping and payment choices as card-shaped radios with price deltas, and keep a sticky order summary that recalculates instantly.
- **Do:** Before an irreversible payment, show a review sheet listing the amount, each fee and the total, then a processing state, then a confirmation with a copyable reference.
- **Do:** Set fee lines in the same size, weight and color as item lines, and include every fee in the total shown.
- **Do:** Echo the selected payment method (masked) beside the final button, and collapse the summary into a bar on mobile.
- **Do:** When wallets are available, put express pay buttons above the card form, separated by a divider such as "or pay with card".
- **Avoid:** Fees revealed only after payment or set smaller and paler than item lines, pre-ticked consent to save a card, or double submission while processing.

## SCR-16. Order product detail panels by the buying decision

**Why:** The buy box should answer what, how much, which variant and when it arrives.

- **Do:** Show breadcrumb, name, price with rating and review count, and a short description, then variant radios whose legend names the selection, a quantity stepper and a full-width add button.
- **Do:** Update the total live as options change, show delivery or pickup time near it, and put details, dimensions and care in tabs or accordions below.
- **Avoid:** Color-only swatches, stepper buttons under 44x44px, or price changes revealed only at checkout.

## SCR-17. State price, trial and terms plainly on paywalls

**Why:** Trust and conversion improve when the price, trial length and cancellation terms sit beside the button.

- **Do:** Show plan cards with price per period, a clear selected state and a few benefits; name the action and its terms on the button ("Start 7-day free trial").
- **Do:** Put "Cancel anytime, charged after 7 days" and "Restore purchases" under the button, and keep the close control visible.
- **Do:** Compute savings badges from the prices on the cards (annual against 12 times monthly, rounded down) and show the amount per charge ("$60 billed yearly").
- **Avoid:** Fake countdowns, reappearing "one-time" offers, or a hidden or delayed close button.

## SCR-18. Make error pages explain and offer a way forward

**Why:** An error page is a dead end unless it says what happened in plain words.

- **Do:** Use a small eyebrow with the code, a plain headline ("Page not found"), one sentence of explanation, a primary action home and a secondary "Go back".
- **Do:** On 401 offer sign-in; on 403 explain access and how to request it.
- **Do:** Keep illustrations decorative and below the actions; if the code itself is drawn as artwork, mark it aria-hidden when the eyebrow states the code, or give it role="img" with aria-label="Error 404".
- **Avoid:** Jokes in place of an explanation, or animated error pages with no navigation.

## SCR-19. Structure messaging around list, thread and composer

**Why:** Seeing conversations and the open thread together speeds triage.

- **Do:** Show conversations with avatar, name, one-line preview, time and an unread badge; highlight the open one.
- **Do:** Align bubbles by sender, pin the composer with labeled attach and send buttons (send disabled while empty), and collapse to one pane with Back on narrow screens.
- **Do:** Group consecutive messages from one sender within a few minutes under one avatar and name (about 4px between bubbles, 16px between groups), with date separators such as Today and Yesterday.
- **Do:** Keep the scroll position anchored when older messages load above, follow new messages only when the reader is at the bottom, and otherwise show a pill with the count of new messages.
- **Do:** Add a sent message to the thread at once with a pending, sent or failed mark, keeping the text and a Retry under a failed bubble.
- **Do:** Grow the composer to about 5 lines before it scrolls; on desktop Enter sends and Shift+Enter adds a line, while on touch keyboards Enter adds a line and the button sends.
- **Avoid:** Unread or presence shown by a colored dot alone.
- **Avoid:** A thread that jumps while the reader scrolls history, or typing indicators announced repeatedly.

## SCR-20. Keep context visible with bottom sheets

**Why:** A sheet over a map or list holds the current step while the context stays visible and actions stay in thumb reach.

- **Do:** Use a sheet with a visible handle and two or three snap points (for example a peek of about 15-25%, half, and about 90% so the page top stays visible), a short status headline, and the primary action pinned at its bottom.
- **Do:** Dismiss on a downward flick or a drag past about half the sheet's height, starting the drag only from the handle or header or when the content is scrolled to the top; if the sheet holds unsaved input, snap back and ask before discarding.
- **Do:** Show one sheet at a time, replacing rather than stacking, and use a side drawer (about 320px up to 40% of the viewport) on wide screens.
- **Do:** In live-service flows show ETA, progress and identifying details (name, photo, vehicle) so users can verify the provider, with call, message and cancel actions (cancel confirmed).
- **Do:** For quick-create sheets, name the context in the subtitle and offer equal-width Cancel and Save, dismissible by swipe, Escape or Cancel.
- **Avoid:** A primary action that scrolls out of view inside the sheet, or a floating button that covers the last item.
- **Avoid:** Sheets that rest at arbitrary heights between snap points.

## SCR-21. Make order confirmations complete and lasting

**Why:** Buyers need to know what they bought, how they paid and when it arrives.

- **Do:** Show a success icon, "Order confirmed", the order number, payment method with the last four digits, the items and a delivery tracker.
- **Do:** Offer a secondary action such as "Order another" or "View receipt".
- **Avoid:** Confirmation only as a transient animation or toast, or a celebration longer than a second before the details.

## SCR-22. Order landing pages the way visitors evaluate

**Why:** A familiar section order helps visitors judge a product quickly.

- **Do:** Use navigation with one call to action, a hero with one primary action, then features, a short numbered "how it works" (3-4 steps), proof, FAQ, a closing call to action and the footer.
- **Do:** Keep price and the purchase action within the first viewport for single-product pages.
- **Do:** Treat the order as a checklist: write each section as one claim with its proof, drop sections with no claim, and vary the layout of neighboring sections.
- **Avoid:** Burying price and purchase after long storytelling sections.

## SCR-23. Mask sensitive values on finance screens

**Why:** Balances and card numbers are often viewed in public.

- **Do:** Show card numbers as bullets with the last four digits and never the full number on overview screens.
- **Do:** Offer an eye toggle beside balances (aria-pressed, "Hide balance") and remember the choice.
- **Do:** Lead finance home screens with the balance, labeled quick actions and recent activity.
- **Avoid:** Icon-only quick actions, or full card number and expiry shown together.

## SCR-24. Design assistant surfaces around the user's data

**Why:** An assistant is most useful when it shows what it can do and answers next to the data it describes.

- **Do:** Offer 2-4 suggestion chips above a composer with a labeled send button, and group history by recency.
- **Do:** Show a live status line while the assistant works, render the streaming reply in an ordinary container marked aria-busy="true", and announce it through a separate polite status region once complete.
- **Do:** Include the period and source for any figure it reports, highlight the widget the figure came from, and use the same rounding as the dashboard.
- **Do:** Dock the panel beside the data by reflowing the layout (for example from 4 columns to 3) rather than covering it, and let users dismiss it.
- **Avoid:** Floating orbs or mascots that cover data, or generated figures without their time range.

## SCR-25. Anchor overlays on immersive views to the corners

**Why:** Overlays on 3D, map or video canvases must leave the center clear and stay readable over moving imagery.

- **Do:** Anchor legends, minimaps and live readouts to corners with safe-area insets, on translucent backing plates.
- **Do:** Make legends collapsible and offer on-screen or touch controls alongside keyboard keys.
- **Avoid:** Bare text floating on a busy scene, or keyboard-only controls.

## SCR-26. Make inline AI output stoppable, versioned and labeled

**Why:** Generated text inside a product edits real work, so people must be able to stop it, compare versions, trace it and keep their own words.

- **Do:** Give every streaming generation a visible Stop that keeps the partial output.
- **Do:** Keep earlier versions when regenerating, with a pager ("2 of 3") and a way back to the original.
- **Do:** Label generated content and show its source (message, document, date) until a person edits it.
- **Do:** Show inline suggestions as muted ghost text that Tab accepts only while it is visible, dismissed by Escape or by continuing to type, without changing focus order.
- **Avoid:** Overwriting user content on regenerate, or a spinner-only generation with no cancel.
- **Avoid:** A modal accept or reject dialog for every suggestion.

## SCR-27. Show which environment, account and scope a screen acts on

**Why:** Operations, admin and finance screens look the same in production and staging and across accounts, and acting on the wrong one is a common cause of serious incidents.

- **Do:** Keep the organization or account, the environment and the region or data scope in the top bar of every page, as a switcher whose current value is spelled out ("Production · eu-west-1").
- **Do:** Make production unmistakable without relying on color alone: a labeled badge, a distinct top border and the word "Production" inside confirmation dialogs.
- **Do:** Restate the scope in every destructive or bulk action ("Revoke 3 API keys in Production, Acme Corp?").
- **Do:** Keep the scope and time range in the URL, and print them on exports, reports and shared links.
- **Avoid:** A scope switcher hidden in a menu, or production and test data that look the same.

## SCR-28. Show what automation decided, why, and what still needs a person

**Why:** Automated detections and responses act on people's systems and money; operators can trust, correct or undo them only when they see the evidence and the limits of what was done.

- **Do:** For each automated decision, show what was detected or done, the evidence (signals, rule or model, data window), when, and the scope it touched.
- **Do:** Record automated actions in an audit trail that names the rule or playbook that acted, with Undo or rollback where the action allows it.
- **Do:** Leave consequential or irreversible steps, such as blocking accounts, deleting data, moving money or changing production, to an explicit human approval with the evidence on the same screen.
- **Do:** Show confidence only when it is calibrated, as a plain band or range with its basis ("High: 9 of the last 10 similar alerts were confirmed").
- **Avoid:** Unexplained scores such as "AI confidence 97%", rates without a denominator, or counts of automated actions presented as outcomes.
- **Note:** Label generated summaries and insights as generated, as in SCR-26.
