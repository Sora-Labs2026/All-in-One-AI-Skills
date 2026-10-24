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

## SCR-12. Lay out sign-in screens predictably

**Why:** A familiar sign-in layout lets people and password managers finish quickly.

- **Do:** Order the card as heading and one-line subtitle, fields, "remember me" with its duration beside "Forgot password?", full-width primary button, an "or continue with" divider, equal-width provider buttons, then a sign-up link.
- **Do:** On desktop, cap the form column at about 360-420px beside an optional visual panel; on mobile show the form first.
- **Do:** Keep the same shell for follow-up steps (code entry, password reset) so the flow feels continuous.
- **Avoid:** Essential copy only in a decorative panel that disappears on mobile, or looping animation beside the form.

## SCR-13. Never gate a core task behind a playful interaction

**Why:** People who came to sign in or pay should not have to discover a gesture or wait for a character first.

- **Do:** Render the form or main action on load, and let any playful element run alongside it as optional decoration.
- **Do:** If a reveal interaction is kept, also offer a visible, keyboard-operable button and a skip.
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
- **Do:** Echo the selected payment method (masked) beside the final button, and collapse the summary into a bar on mobile.
- **Avoid:** Fees revealed only after payment, pre-ticked consent to save a card, or double submission while processing.

## SCR-16. Order product detail panels by the buying decision

**Why:** The buy box should answer what, how much, which variant and when it arrives.

- **Do:** Show breadcrumb, name, price with rating and review count, and a short description, then variant radios whose legend names the selection, a quantity stepper and a full-width add button.
- **Do:** Update the total live as options change, show delivery or pickup time near it, and put details, dimensions and care in tabs or accordions below.
- **Avoid:** Color-only swatches, stepper buttons under 44x44px, or price changes revealed only at checkout.

## SCR-17. State price, trial and terms plainly on paywalls

**Why:** Trust and conversion improve when the price, trial length and cancellation terms sit beside the button.

- **Do:** Show plan cards with price per period, a clear selected state and a few benefits; name the action and its terms on the button ("Start 7-day free trial").
- **Do:** Put "Cancel anytime, charged after 7 days" and "Restore purchases" under the button, and keep the close control visible.
- **Avoid:** Fake countdowns, reappearing "one-time" offers, or a hidden or delayed close button.

## SCR-18. Make error pages explain and offer a way forward

**Why:** An error page is a dead end unless it says what happened in plain words.

- **Do:** Use a small eyebrow with the code, a plain headline ("Page not found"), one sentence of explanation, a primary action home and a secondary "Go back".
- **Do:** On 401 offer sign-in; on 403 explain access and how to request it.
- **Do:** Keep illustrations decorative and below the actions.
- **Avoid:** Jokes in place of an explanation, or animated error pages with no navigation.

## SCR-19. Structure messaging around list, thread and composer

**Why:** Seeing conversations and the open thread together speeds triage.

- **Do:** Show conversations with avatar, name, one-line preview, time and an unread badge; highlight the open one.
- **Do:** Align bubbles by sender, pin the composer with labeled attach and send buttons (send disabled while empty), and collapse to one pane with Back on narrow screens.
- **Avoid:** Unread or presence shown by a colored dot alone.

## SCR-20. Keep context visible with bottom sheets

**Why:** A sheet over a map or list holds the current step while the context stays visible and actions stay in thumb reach.

- **Do:** Use a sheet with a visible handle and snap points, a short status headline, and the primary action pinned at its bottom.
- **Do:** In live-service flows show ETA, progress and identifying details (name, photo, vehicle) so users can verify the provider, with call, message and cancel actions (cancel confirmed).
- **Do:** For quick-create sheets, name the context in the subtitle and offer equal-width Cancel and Save, dismissible by swipe, Escape or Cancel.
- **Avoid:** A primary action that scrolls out of view inside the sheet, or a floating button that covers the last item.

## SCR-21. Make order confirmations complete and lasting

**Why:** Buyers need to know what they bought, how they paid and when it arrives.

- **Do:** Show a success icon, "Order confirmed", the order number, payment method with the last four digits, the items and a delivery tracker.
- **Do:** Offer a secondary action such as "Order another" or "View receipt".
- **Avoid:** Confirmation only as a transient animation or toast, or a celebration longer than a second before the details.

## SCR-22. Order landing pages the way visitors evaluate

**Why:** A familiar section order helps visitors judge a product quickly.

- **Do:** Use navigation with one call to action, a hero with one primary action, then features, a short numbered "how it works" (3-4 steps), proof, FAQ, a closing call to action and the footer.
- **Do:** Keep price and the purchase action within the first viewport for single-product pages.
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
- **Do:** Show a live status line while the assistant works, stream replies into a polite live region, and include the period and source for any figure it reports.
- **Do:** Dock the panel beside the data rather than over it, and let users dismiss it.
- **Avoid:** Floating orbs or mascots that cover data, or generated figures without their time range.

## SCR-25. Anchor overlays on immersive views to the corners

**Why:** Overlays on 3D, map or video canvases must leave the center clear and stay readable over moving imagery.

- **Do:** Anchor legends, minimaps and live readouts to corners with safe-area insets, on translucent backing plates.
- **Do:** Make legends collapsible and offer on-screen or touch controls alongside keyboard keys.
- **Avoid:** Bare text floating on a busy scene, or keyboard-only controls.
