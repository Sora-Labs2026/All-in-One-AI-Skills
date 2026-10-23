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
