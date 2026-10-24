# UI rules: Feedback, loading and empty states

Responsiveness, progress, outcome messages, confirmations and empty screens. Rule IDs use the `FBK-` prefix; cite them in change reports.

## FBK-01. Respond to every action immediately

**Why:** Silence after a tap leaves users unsure whether anything happened, so they tap again.

- **Do:** Show a pressed state at once, then a loading state (for example a spinner and "Saving...") while work runs.
- **Do:** Disable the control while the request is in flight to prevent double submits.
- **Do:** Confirm the result explicitly, success or failure.
- **Avoid:** A button that looks unchanged while a request runs in the background.
- **Note:** Responses slower than roughly 400ms should show progress.

## FBK-02. Match the loading indicator to the wait

**Why:** The right indicator reassures users without flashing or lying about progress.

- **Do:** Show nothing for actions under about 300ms, a spinner with a short label for waits over about a second, and skeletons for content-shaped loads.
- **Do:** Use a determinate bar or ring with a percentage when progress is measurable.
- **Do:** Mark loading regions with role="status" or aria-busy.
- **Avoid:** An indefinite spinner for an operation whose progress is known, or a progress bar with no label.

## FBK-03. Confirm outcomes with clear status messages

**Why:** Users need to know whether an action worked, failed or needs attention.

- **Do:** Use distinct success, error and warning variants, each with a tinted background, a matching icon and plain wording.
- **Do:** Say what failed and what to do next (for example "Couldn't save your changes. Try again.").
- **Do:** Put decision buttons inside warning banners when a choice is needed, and expose messages with role="status" or role="alert".
- **Avoid:** Completing an action with no visible change, or generic errors without a next step.

## FBK-04. Use toasts for confirmations, not for errors that need work

**Why:** Toasts disappear; anything users must act on needs to stay visible.

- **Do:** Show short success toasts with an icon, a title and one line, auto-dismissing after a few seconds and pausing on hover or focus.
- **Do:** Announce toasts through an ARIA live region and give them a close control.
- **Do:** Keep errors that need action inline or in a persistent banner.
- **Avoid:** Important information that exists only in a toast.

## FBK-05. Show steps in multi-step flows

**Why:** Seeing which steps are done, current and left reduces anxiety and drop-off.

- **Do:** Show 3-6 named steps: completed steps with a check, the current one highlighted, upcoming ones muted.
- **Do:** Let users go back to completed steps.
- **Avoid:** States told apart by color alone, or hidden step counts.

## FBK-06. Show progress toward goals

**Why:** People are more motivated the closer they see themselves to a goal.

- **Do:** Show progress bars with a value for goals, profile completion and long tasks (for example "Step 2 of 4" or 70%).
- **Do:** Give an honest head start where the user has genuinely made progress.
- **Avoid:** Raw numbers with no visual indicator, or invented progress.

## FBK-07. Design the high point and the ending

**Why:** People judge an experience mostly by its most intense moment and how it ends.

- **Do:** Make completion screens clear and warm: an icon or illustration, a headline, a short summary and a useful next action.
- **Do:** Celebrate real milestones briefly without blocking the user.
- **Avoid:** Ending a long flow with a blank page or silent redirect, or placing upsells and extra forms at the final step.

## FBK-08. Make destructive confirmations unmistakable

**Why:** Destructive dialogs must say exactly what will be lost and which button does what.

- **Do:** Name the specific object being deleted and show a warning icon.
- **Do:** Label buttons with explicit outcomes ("Keep project", "Delete project") and style the destructive one red and the safe one neutral.
- **Do:** Offer undo, or require typed confirmation for high-impact irreversible actions.
- **Avoid:** Generic Yes/No buttons with identical styling.

## FBK-09. Turn empty states into a first step

**Why:** An empty screen is a dead end unless it explains what belongs there and how to start.

- **Do:** Show a specific headline ("No projects yet"), one line on what will appear and why it helps, and one primary action that starts it.
- **Do:** Offer templates, examples or import options where relevant, and keep navigation visible.
- **Do:** Write different messages for "nothing created yet", "no search results" and "failed to load" (with a retry).
- **Avoid:** A bare "No data" message on a blank screen, or several competing buttons.

## FBK-10. Show progress inside the button for async actions

**Why:** Feedback in the exact place the user clicked prevents double submits and doubt.

- **Do:** On activation, swap the label for a present-progressive verb with a spinner ("Signing in...", "Placing order...") or a percentage for measurable work.
- **Do:** Set aria-busy, block re-submission and keep the button width fixed while the label changes.
- **Do:** On success show a short confirmation state ("Added" with a check) for about 1.5-2s; on failure restore the button and show an inline error.
- **Avoid:** Spinner-only buttons with no text, or buttons that stay active during the request.

## FBK-11. Never show success before the server confirms

**Why:** A success animation that runs on a timer can contradict what actually happened, especially for payments and orders.

- **Do:** Start processing visuals when the request starts and show the verdict only when the real result arrives.
- **Do:** Design the failure path as carefully as success: distinct label, color and icon, and a retry.
- **Do:** Let animations celebrate a change that already happened, never delay the state change itself.
- **Avoid:** Fixed setTimeout waits before or instead of the real request.

## FBK-12. Report progress honestly

**Why:** Progress that jumps backwards, races ahead or keeps moving during a stall erodes trust.

- **Do:** Drive determinate progress from real work (for example bytes read from response.body.getReader() against Content-Length) and keep it monotonic.
- **Do:** Keep the bar indeterminate when the total is unknown, never show 100% before the work is finished, and show a stalled state if nothing arrives for about a second.
- **Do:** Expose role="progressbar" with aria-valuenow once determinate, show percent text, and offer Cancel (for example through AbortController).
- **Avoid:** Fixed-duration fills unrelated to the work.

## FBK-13. Give code verification explicit states

**Why:** After the last digit, people need to see that the code is being checked and what happened.

- **Do:** Move through entering, checking (inputs locked, aria-busy), verified (success color, check, next step) and error (message plus icon, digits cleared and focus back in the first box).
- **Do:** Announce state changes through a polite live region, using role="alert" for the error.
- **Do:** Stop the resend countdown once verification succeeds.
- **Avoid:** Signaling the result with glow color or a shake alone.

## FBK-14. Keep the app shell steady while content loads

**Why:** Blank flashes and full-page spinners between views jolt the eye and hide the layout.

- **Do:** Keep navigation and headers mounted and swap only the content region, using skeletons at the real sizes and positions.
- **Do:** Delay any spinner by about 300ms so fast loads show nothing, match the current theme's background, and set aria-busy on the loading region.
- **Do:** Reserve space for images and charts (aspect-ratio, fixed heights) so nothing shifts when data arrives.
- **Avoid:** A white loading screen inside a dark app, or long blur-in effects after the data is ready.

## FBK-15. Prefer undo over confirmation for reversible deletes

**Why:** An undo window is faster than a dialog and still protects against mistakes.

- **Do:** Remove the item immediately, update counts, and show a status toast ("Deleted brand-assets.zip") with Undo and a visible countdown, committing when it expires.
- **Do:** Restore undone items at their original position, and name the target in icon-only delete buttons.
- **Avoid:** Modal confirmations for actions that can be undone, or undo windows too short to reach.

## FBK-16. Confirm add-to-cart without interrupting

**Why:** Shoppers want proof the item was added and a path to the cart, not a modal that ends browsing.

- **Do:** Update the cart count at once, switch the add button to "Added" briefly, and announce it through a polite live region.
- **Do:** Show a toast or a persistent "View cart" pill with the count, keeping any toast for at least 2-4s and pausing it on hover or focus.
- **Avoid:** Forcing a cart drawer or page open on every add, or confirmations shorter than a second.

## FBK-17. Name the state of long-running and sensing tasks

**Why:** For background jobs, voice input and camera capture, users need to know whether the system is working, listening, done or stuck.

- **Do:** Show a distinct status line per state (working on step X, listening, thinking, done, failed with retry), with the indicator animating only while active.
- **Do:** For capture tasks, give live positioning guidance and numeric progress, plus manual entry or upload as a fallback.
- **Do:** Mirror changes in a polite live region and swap control labels and aria-pressed with the state.
- **Avoid:** Animation or color as the only sign that a microphone is live or a job failed.

## FBK-18. Make exceptions stand out with more than color

**Why:** In monitoring and operational lists, out-of-range records must be visible at a glance.

- **Do:** Give exceptions a strong treatment plus an explicit text or icon marker, and offer a filter or sort that brings them to the top.
- **Do:** Show "last updated" times for live data and briefly tint newly arrived rows.
- **Avoid:** A red fill as the only signal, or small white text on saturated red without a contrast check.

## FBK-19. Keep splash screens and preloaders honest and short

**Why:** A launch screen only earns its delay if it reflects real loading.

- **Do:** Tie any progress to real asset loading, finish within about 1-2s, continue automatically and let users skip.
- **Do:** Match the native launch background to the first screen to avoid a flash, and show a brand intro at most once per session.
- **Avoid:** Fake percentage counters that hold back content that has already loaded.

## FBK-20. Keep interface sounds opt-in

**Why:** Unexpected audio is disruptive, especially in shared spaces.

- **Do:** Keep UI sounds off by default, provide a visible sound toggle with aria-pressed in a consistent place, and remember the choice.
- **Avoid:** Playing sound on load or on the first interaction without an obvious control.
