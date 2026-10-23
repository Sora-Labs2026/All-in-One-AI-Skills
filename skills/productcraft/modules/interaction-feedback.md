# Controls, feedback and motion

**System state must be comprehensible, not merely animated.** Related patterns in `../references/pattern-library.md`: 1, 4, 5, 10, 11, 19, 23-25, 29, 31-32, 36-46, 49-50, 61, 64, 68. Button and feedback specifics: `BTN` and `FBK` rules in `../references/ui-rules/`.

## State contracts

Represent asynchronous controls as `idle -> pending -> success | recoverable-error | terminal-error`. Surface latency honestly. For mutations allow cancel/retry/undo only if backed by real application semantics. Prevent duplicate submissions/idempotently guard actions. For reversible likes/bookmarks/draft edits, optimistic display can run with server reconciliation. For payments, clinical operations, irreversible deletion or admin privileges, use pending until verified.

## Control-specific expectations

- Buttons and links: visible hover where pointer exists; active, disabled, focus-visible states; no moving submit target during validation. Prefer coherent sizes and 44px-ish mobile target guidance, not a hard one-size-fits-all metric.
- Switches: controlled checked state, visible label, Space and `role=switch`/native semantics; optimistic toggle only when safe; roll back server failure. A checkbox may be correct for staged form settings.
- Sliders: full track hit area, actual numeric value, correct min/max/step, touch/keyboard/Home/End support. Do not substitute slider for precision input.
- Drag and drop: pickup state, valid placement, predictable snap/landing, keyboard alternative; action success/undo and announcement. Dragging should not unexpectedly delete.
- Modals: role/dialog name, focus trap and return focus, Escape policy, scroll lock, nonblocking backdrop; no accidental dismissal for high-risk decisions. Motion is optional.
- Toasts: minimize pileup, choose severity and duration, `aria-live`, dismissal and undo if applicable. Errors requiring work should persist somewhere meaningful rather than vanish.
- Context menus: collision-aware placement, submenu pointer intent, keyboard navigation and touch counterpart; no hover-only command.
- Voice recording: explicit consent/permission, recording timer/status, cancel, stop, and seekable playback. No fake recording indicator.
- Shared presence/live cursors: opt-in as appropriate, rate-limited updates, interpolation, visibility boundaries; no fake live colleagues.
- Success: state WHAT happened, to WHOM, WHEN, and what next. Never display success ahead of verified financial or clinical truth.

## Motion policy

Favor fast, subtle entrance/exit only when it explains continuity, location or cause. Interruptible, device-appropriate, reduced-motion-safe. Avoid blur-heavy animation and unnecessary icon wiggles. Fitts law matters more than fanciness: make targets discoverable and close to the task. Avoid arbitrary forced delays and 'typing…' animation that pretends a human is present.

## Tests

Click/tap/keyboard, very slow response, error, refresh, stale state, duplicate presses, low-power/reduced-motion, screen reader announcements, context closing, mobile pointer absence, and failure rollback.
