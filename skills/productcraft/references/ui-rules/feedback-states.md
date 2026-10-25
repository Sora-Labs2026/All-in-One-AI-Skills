# UI rules: Feedback, loading and empty states

Responsiveness, progress, outcome messages, confirmations and empty screens. Rule IDs use the `FBK-` prefix; cite them in change reports.

## FBK-01. Respond to every action immediately

**Why:** Silence after a tap leaves users unsure whether anything happened, so they tap again.

- **Do:** Acknowledge input within about 100ms with a pressed state or an optimistic change (keep Interaction to Next Paint at 200ms or less), then show a busy state (for example a spinner and "Saving...") while work runs.
- **Do:** Disable the control while the request is in flight to prevent double submits.
- **Do:** Confirm the result explicitly, success or failure.
- **Avoid:** A button that looks unchanged while a request runs in the background.
- **Note:** About 100ms feels instant; past about 300-400ms show a busy state in place (the control disabled with progress text, as in FBK-10), and add a standalone spinner or progress bar only past about 1s (FBK-02).

## FBK-02. Match the loading indicator to the wait

**Why:** The right indicator reassures users without flashing or lying about progress.

- **Do:** Show nothing for waits under about 300ms, a busy state in place from there, a spinner with a short label past about a second, and skeletons for content-shaped loads.
- **Do:** Once an indicator appears, keep it for about 400-500ms so a reply just after the delay does not flash it; if it became visible, await the request and the minimum time together (for example Promise.all([request, minVisible])).
- **Do:** Use a determinate bar or ring with a percentage when progress is measurable.
- **Do:** Draw spinners as an open arc or a ring with a visible gap; a uniform ring shows no motion when it rotates.
- **Do:** When refreshing content already on screen (search as you type, filters), keep the previous results visible, replace rows in place and signal the refresh with a thin progress line.
- **Do:** Mark loading regions with role="status" or aria-busy.
- **Avoid:** An indefinite spinner for an operation whose progress is known, a bar that fills and resets in a loop for one whose progress is unknown (use a moving segment or a spinner), or a progress bar with no label.
- **Avoid:** Clearing a list to show a centered spinner while new results load.

## FBK-03. Confirm outcomes with clear status messages

**Why:** Users need to know whether an action worked, failed or needs attention.

- **Do:** Use distinct success, error and warning variants, each with a tinted background, a matching icon and plain wording.
- **Do:** Set message text in the dark step of the status hue or in neutral text so it reaches 4.5:1 on the tint (for example #166534 on #DCFCE7, about 6.5:1), and keep the brighter status color for the icon (3:1 against the tint) and the border.
- **Do:** Say what failed and what to do next (for example "Couldn't save your changes. Try again.").
- **Do:** Put decision buttons inside warning banners when a choice is needed, and expose messages with role="status" or role="alert".
- **Avoid:** Completing an action with no visible change, or generic errors without a next step.
- **Avoid:** Mid-tone status text on its own tint (#16A34A on #DCFCE7 is about 3:1), or one phrase of the message recolored in the status hue.

## FBK-04. Use toasts for confirmations, not for errors that need work

**Why:** Toasts disappear; anything users must act on needs to stay visible.

- **Do:** Show short success toasts with an icon, a title and one line, pausing the dismiss timer on hover or focus.
- **Do:** Scale auto-dismiss with length and weight: about 4-5s for a one-line confirmation, about 7-10s for warnings or toasts with an action, and no auto-dismiss for errors or for actions available nowhere else (WCAG 2.2.1).
- **Do:** Keep at most about 3 toasts visible, newest nearest the anchor edge, anchored clear of navigation and never over the middle of the content, and allow swipe to dismiss on touch.
- **Do:** Announce toasts through an ARIA live region and give them a close control.
- **Do:** Keep errors that need action inline or in a persistent banner.
- **Avoid:** Important information that exists only in a toast.
- **Avoid:** Toasts for routine navigation or for results the screen already shows.

## FBK-05. Show steps in multi-step flows

**Why:** Seeing which steps are done, current and left reduces anxiety and drop-off.

- **Do:** Show 3-6 named steps: completed steps with a check, the current one highlighted, upcoming ones muted.
- **Do:** Mark the current step with a heavier weight, the primary text color and aria-current="step", and add a text equivalent ("Step 3 of 5: Payment").
- **Do:** Mute upcoming steps through weight, outline markers and number style while keeping their text at 4.5:1 and their markers and connectors at 3:1; they are information, not disabled controls.
- **Do:** If the stepper also shows a bar or percentage, compute it from completed steps and reach 100% only after the final submit succeeds.
- **Do:** Let users go back to completed steps.
- **Avoid:** States told apart by color alone, or hidden step counts.

## FBK-06. Show progress toward goals

**Why:** People are more motivated the closer they see themselves to a goal.

- **Do:** Show progress bars with visible text naming the value and the goal for goals, profile completion and long tasks (for example "Step 2 of 4" or "700 of 1,000 points, 70%").
- **Do:** Build them with <progress> or role="progressbar" with aria-valuenow, aria-valuemin and aria-valuemax, drawn as a plain fill.
- **Do:** Give an honest head start where the user has genuinely made progress.
- **Avoid:** Raw numbers with no visual indicator, or invented progress.
- **Avoid:** A knob or thumb on a progress bar, which reads as a draggable slider.

## FBK-07. Design the high point and the ending

**Why:** People judge an experience mostly by its most intense moment and how it ends.

- **Do:** Make completion screens clear and warm: an icon or illustration, a headline, a short summary and a useful next action.
- **Do:** Match the success surface to the stakes: a short toast with Undo for reversible changes, a persistent confirmation page or receipt (items, amount, masked card, date) for payments and orders, and a status tracker with timestamps (Sent, Opened, Paid) when the real outcome comes later.
- **Do:** Celebrate real milestones briefly, with a full-size Continue or Close visible from the first frame, a tap anywhere skipping to the end state, and sharing kept secondary.
- **Avoid:** Ending a long flow with a blank page or silent redirect, or placing upsells and extra forms at the final step.
- **Avoid:** A celebration that holds back the way forward or offers it only as a small, faint link.

## FBK-08. Make destructive confirmations unmistakable

**Why:** Destructive dialogs must say exactly what will be lost and which button does what.

- **Do:** Title the dialog as the action on the named object ("Delete Q3 Report?"), show a warning icon, and repeat the name in bold in the body with its scope (how many items it holds, who loses access).
- **Do:** Label buttons with explicit outcomes ("Keep project", "Delete project") and style the destructive one red and the safe one neutral, using a red that gives its white label at least 4.5:1 (#DC2626 is about 4.8:1; #EF4444 fails at about 3.8:1).
- **Do:** Put initial focus on the safe action, let Escape cancel, and never let a backdrop click confirm (CMP-12).
- **Do:** For unsaved changes, offer three outcomes: Save (primary), Discard (a low-emphasis destructive style, placed away from Save, as in BTN-05) and Cancel to keep editing.
- **Do:** Offer undo, or require typed confirmation for high-impact irreversible actions.
- **Do:** For typed confirmation, show the exact name in monospace beside the field, allow paste, enable the button only when the trimmed input matches, label it with the consequence ("Permanently delete <name>"), and list what else disappears.
- **Avoid:** Generic Yes/No buttons with identical styling.

## FBK-09. Turn empty states into a first step

**Why:** An empty screen is a dead end unless it explains what belongs there and how to start.

- **Do:** Show a specific headline ("No projects yet"), one or two lines on what will appear and why it helps in text that meets 4.5:1, and one primary action that starts it.
- **Do:** Offer templates, examples or import options where relevant, and keep navigation visible.
- **Do:** Write different messages for "nothing created yet", "no search results" (clear the search, check spelling), "hidden by filters" (how many items are hidden, with Reset filters) and "failed to load" (with a retry).
- **Avoid:** A bare "No data" message on a blank screen, or several competing buttons.
- **Avoid:** Faint gray supporting text, or an empty collection presented as an error code such as "404".

## FBK-10. Show progress inside the button for async actions

**Why:** Feedback in the exact place the user clicked prevents double submits and doubt.

- **Do:** When the wait passes about 300ms, swap the label for a present-progressive verb with a spinner ("Signing in...", "Placing order...") or a percentage for measurable work.
- **Do:** Set aria-busy and block re-submission from the first press, and keep the button width fixed while the label changes.
- **Do:** On success show a short confirmation state ("Added" with a check) for about 1.5-2s; on failure restore the button and show an inline error.
- **Do:** Keep the form mounted and readable while it submits: make the fields read-only, and on failure keep the values and move focus to the field that needs fixing.
- **Do:** If a progress fill sweeps under the label, layer an on-accent copy of the label clipped to the filled part (clip-path driven by the same progress variable, marked aria-hidden) so every glyph keeps its contrast.
- **Avoid:** Spinner-only buttons with no text, or buttons that stay active during the request.
- **Avoid:** Replacing the form with a loader, or hiding it with opacity alone, which leaves its fields focusable; make any covered form inert (ENG-05).

## FBK-11. Never show success for consequential actions before the server confirms

**Why:** A success animation that runs on a timer can contradict what actually happened, especially for payments and orders.

- **Do:** For payments, transfers, orders, bookings and irreversible changes, start processing visuals when the request starts and show the verdict only when the real result arrives.
- **Do:** Treat only a 2xx response (response.ok) as success: send 401 to re-authentication, show 409 and 422 as inline field errors using the server's messages, and offer Retry for 5xx and network failures.
- **Do:** Design the failure path as carefully as success: distinct label, color and icon, and a retry.
- **Do:** Let animations celebrate a change that already happened, never delay the state change itself.
- **Avoid:** Fixed setTimeout waits before or instead of the real request, or treating any response with a body as success.
- **Note:** Low-risk reversible actions may update optimistically if they roll back visibly on failure (FBK-21).

## FBK-12. Report progress honestly

**Why:** Progress that jumps backwards, races ahead or keeps moving during a stall erodes trust.

- **Do:** Drive determinate progress from real work (for example bytes read from response.body.getReader() against Content-Length) and keep it monotonic.
- **Do:** Keep the printed percentage equal to work done, rounded down and held at 99 until the done event (Math.min(99, Math.floor(p * 100))), since rounding shows 100% at 99.5%; to make updates feel smooth, ease only between real values (about 200-300ms ease-out per update).
- **Do:** Keep the bar indeterminate when the total is unknown, never show 100% before the work is finished, and show a stalled state if nothing arrives for about a second, leaving the bar where it stopped.
- **Do:** For transfers longer than a few seconds, show done and total, rate and time left ("12 s left, 1.8 MB/s"), computing time left from a moving average over the last few seconds, hiding it for the first second or two and rounding to coarse units ("A few seconds left").
- **Do:** Expose role="progressbar" with aria-valuenow once determinate, show percent text, and offer Cancel (for example through AbortController).
- **Avoid:** Fixed-duration or front-loaded fills unrelated to the work.

## FBK-13. Give code verification explicit states

**Why:** After the last digit, people need to see that the code is being checked and what happened.

- **Do:** Move through entering, checking (digits stay visible and locked, aria-busy on the code field, a spinner beside it), verified (success color, check, next step) and error (message plus icon).
- **Do:** On error, show the message at once, keep the wrong digits visible for about half a second, then clear them and return focus to the code field (its first box if the boxes are separate inputs, FRM-17); keep the message until the user types again.
- **Do:** Keep any shake to about 300-400ms, 2-3 cycles and 8px or less, and drop it under reduced motion.
- **Do:** Announce state changes through a polite live region, using role="alert" for the error.
- **Do:** Keep the resend countdown running after an error and stop it once verification succeeds.
- **Avoid:** Signaling the result with glow color or a shake alone.
- **Avoid:** Replacing the code field with a loader while checking.

## FBK-14. Keep the app shell steady while content loads

**Why:** Blank flashes and full-page spinners between views jolt the eye and hide the layout.

- **Do:** Keep navigation and headers mounted and swap only the content region, using skeletons at the real sizes and positions.
- **Do:** Delay any spinner by about 300ms so fast loads show nothing, match the current theme's background, and set aria-busy on the loading region.
- **Do:** Hide skeleton blocks from assistive technology (aria-hidden) and give the region a visually hidden "Loading <thing>" status; animate any shimmer with a transform on a pseudo-element over about 1-1.5s in reading direction (mirrored for right-to-left), static under reduced motion.
- **Do:** Replace a skeleton with an error and Retry on failure or after a timeout (for example about 10s).
- **Do:** Reserve space for images and charts (aspect-ratio, fixed heights) so nothing shifts when data arrives.
- **Do:** Render new content as soon as its data is ready, with at most a 150-250ms opacity or translate entrance.
- **Avoid:** A white loading screen inside a dark app, or blur-in effects after the data is ready (animated blur across whole sections is also costly to render).

## FBK-15. Prefer undo over confirmation for reversible deletes

**Why:** An undo window is faster than a dialog and still protects against mistakes.

- **Do:** Remove the item immediately, update counts, and show a status toast ("Deleted brand-assets.zip") with Undo and a visible countdown, committing when it expires.
- **Do:** Keep the undo window at about 7-10s (FBK-04), pause it on hover, focus and while the page is hidden, and make Undo a full 44x44px target.
- **Do:** Back the toast with a soft delete (a deleted_at timestamp) and a Trash that keeps items restorable for a stated period such as 30 days, so the toast is not the only way back.
- **Do:** Restore undone items at their original position, and name the target in icon-only delete buttons.
- **Do:** For messages that cannot be recalled once delivered, hold the send for an adjustable grace period (about 5-30s) with a seconds countdown and an Undo that returns the draft to the editor, and commit on the server when the timer ends so closing the tab neither loses nor duplicates it.
- **Avoid:** Modal confirmations for actions that can be undone, or undo windows too short to reach.

## FBK-16. Confirm add-to-cart without interrupting

**Why:** Shoppers want proof the item was added and a path to the cart, not a modal that ends browsing.

- **Do:** Update the cart count at once (optimistically or on the add response), never when a fly-to-cart animation lands, switch the add button to "Added" briefly, and announce it at the same moment through a polite live region.
- **Do:** Show a toast or a persistent "View cart" pill with the count, keeping any toast for at least about 4-5s (FBK-04) and pausing it on hover or focus.
- **Do:** Restart the confirmation timer on every add (clear the previous timeout, or key the toast to the current count) so a quick second add is not hidden early.
- **Avoid:** Forcing a cart drawer or page open on every add, or confirmations shorter than a second.

## FBK-17. Name the state of long-running and sensing tasks

**Why:** For background jobs, voice input and camera capture, users need to know whether the system is working, listening, done or stuck.

- **Do:** Show a distinct status line per state (working on step X, listening, thinking, done, failed with retry), with the indicator animating only while active.
- **Do:** Give the status line body-text contrast (4.5:1); if streamed text fades in, fade only the newest words and bring them to full contrast within a few hundred ms.
- **Do:** Drive typing and thinking indicators from real events, clear them a few seconds after the last one, and label automated replies as such; never simulate typing or add a delay before a result that is already available.
- **Do:** For capture tasks, give live positioning guidance or an input-level meter, warn that the microphone may be muted after about 2s of near-silence, show numeric progress, and offer manual entry or upload as a fallback.
- **Do:** Mirror changes in a polite live region; give toggles such as a microphone a fixed name with aria-pressed, or an action label that changes, never both.
- **Avoid:** Animation or color as the only sign that a microphone is live or a job failed.

## FBK-18. Make exceptions stand out with more than color

**Why:** In monitoring and operational lists, out-of-range records must be visible at a glance.

- **Do:** Give exceptions a strong treatment plus an explicit text or icon marker, and offer a filter or sort that brings them to the top.
- **Do:** Show "last updated" times for live data and briefly tint newly arrived rows.
- **Avoid:** A red fill as the only signal, or small white text on saturated red without a contrast check.

## FBK-19. Keep splash screens and preloaders honest and short

**Why:** A launch screen only earns its delay if it reflects real loading.

- **Do:** Tie any progress to real asset loading, finish within about 1-2s, continue automatically and let users skip.
- **Do:** Keep the native launch screen until the first screen has rendered (hide it from a first-frame callback, not at process start) and give the root window the first screen's background, so no blank frame flashes between them.
- **Do:** Show a brand intro at most once per session.
- **Avoid:** Fake percentage counters that hold back content that has already loaded.

## FBK-20. Keep interface sounds opt-in

**Why:** Unexpected audio is disruptive, especially in shared spaces.

- **Do:** Keep UI sounds off by default, provide a visible sound toggle in a consistent place, and remember the choice.
- **Do:** Give the toggle a constant name ("Sound") and expose its state with aria-pressed and an icon that changes.
- **Avoid:** Playing sound on load or on the first interaction without an obvious control.
- **Avoid:** A label that flips between "Sound on" and "Sound off" while aria-pressed also changes, which announces the state twice.

## FBK-21. Update low-risk actions optimistically and roll back visibly

**Why:** Waiting for the server on likes, toggles or sent messages makes a fast product feel broken, but an optimistic change that silently reverts misleads people.

- **Do:** Apply reversible, high-success actions (like, follow, save, toggle, reorder, send message) locally at once, keeping the previous state and a pending marker.
- **Do:** On failure restore exactly the previous state and say what was reverted, with Retry ("Couldn't save, change undone").
- **Do:** Coalesce rapid repeats into the latest intent and ignore responses older than the last request (ENG-02).
- **Do:** Keep payments, transfers, permanent deletions and bookings on server-confirmed states (FBK-11).
- **Avoid:** Optimistic success for money, permissions or irreversible changes.
- **Avoid:** Silent rollback with no message, or a spinner in front of a low-risk action.

## FBK-22. Handle lost connections with a persistent status and automatic retry

**Why:** An outage is an ongoing condition, so a dismissable toast or a blocking dialog either hides it or traps the user, and blind retries can overload the server.

- **Do:** Show a persistent, non-modal banner (role="status") while offline or degraded, driven by failed requests as well as the online and offline events, and clear it with a brief "Back online" once requests succeed.
- **Do:** Retry automatically with exponential backoff and jitter (about 1, 2, 4, 8s, capped near 30s), show when the next attempt happens ("Retrying in 3s") and offer "Retry now".
- **Do:** Keep typed input and queued actions, mark unsent items as pending, and send them after reconnecting.
- **Avoid:** Auto-dismissing toasts or modal dialogs for an outage that is still happening.
- **Avoid:** Fixed-interval retry loops, or discarding the user's draft on a network error.
- **Note:** Give queued writes an idempotency key so a retry after a lost response cannot apply them twice.

## FBK-23. Give time-limited decisions a visible clock and a safe outcome

**Why:** Offers, holds and sessions that expire silently or under unseen time pressure cause missed choices and lost work.

- **Do:** Show the time left as text ("14 s", "Hold ends in 4:59"), optionally with a shrinking bar, computed from the deadline timestamp (ENG-09), and say what happens at zero (offer declined, seats released).
- **Do:** Give accept and decline equal size and reach, and on expiry return to a stable state with a status line ("Offer expired, still searching") instead of a blank screen or an error.
- **Do:** For limits the user did not choose (sessions, cart or seat holds), warn at least 20s before expiry and let them extend with one simple action (WCAG 2.2.1, which exempts real-time events such as auctions).
- **Avoid:** Countdowns on choices with no real deadline (false urgency), or limits that end without warning.
- **Avoid:** Announcing every second to assistive technology; announce only at thresholds such as 10s left (ENG-09).
