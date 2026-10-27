# Keeping a task board in Markdown

Read this when a task has more moving parts than a flat checklist holds comfortably, when work spans several sessions, or when a person wants to see what is in progress and what is left without reading the whole conversation. A board in the repository (or beside it) is durable, diff-able and readable by both the user and a fresh agent. It is a lightweight alternative to a project-management tool, not a replacement for one.

This complements the plan (`../assets/plan-template.md`) and the progress note in `clarify-and-plan.md`. Use a plan when the work is a single ordered sequence; use a board when there are several independent threads at different stages.

## When a board helps, and when it does not

Use one when: the work has five or more tasks that are not a strict line, several can be in flight at once, or the user tracks work this way already. A board costs upkeep, so for a short linear task the plan's numbered steps are enough.

Check the project first. If it already keeps work in a tool (issues, a tracker, a board file), use that and follow its conventions rather than starting a parallel system. Only introduce a Markdown board when nothing exists or the user asks for one.

## Shape of a board

A board is a set of columns by status and a card per task. The simplest form is one Markdown file with a section per column:

```markdown
# Board: checkout rework

## Backlog
- [ ] Refund path for partial captures
- [ ] Idempotency on the charge endpoint

## In progress
- [ ] Server-side price recomputation  — @me, started 2026-02-20
  - Acceptance: AC-03, AC-04 from specs/checkout.spec.md
  - Branch: feature/price-recompute @ a1b2c3d

## Review
- [ ] Webhook signature check  — PR #214, waiting on review

## Done
- [x] Reject second import while one runs  (AC-07) — merged a9f0e21
```

Columns that cover most work: Backlog (agreed, not started), In progress (one owner each), Review (built, awaiting a check or a reviewer), Done (merged or verified). Add or drop columns to match how the team actually works; do not impose extra ceremony.

For a larger board, one file per task in a folder (a card per file) reads better and produces smaller diffs than one growing file. Put the status in the card so it is visible without a tool, keep the file name stable, and move finished cards into a `done/` subfolder if the folder gets crowded. Pick one layout and keep to it.

## What a card carries

Keep a card to what the next person needs, and no history of the conversation:

- A short imperative title.
- Status, and a single owner while it is in progress (two owners on one card is a sign to split it).
- The acceptance criteria or done-when checks it satisfies, by identifier, so "done" is objective (`requirements-and-acceptance.md`).
- A link to the branch, commit or pull request where the work lives.
- Priority or due date only if the team uses them; an unused field is noise.

Leave out secrets, long logs and anything you have not verified. A card that claims done links to the evidence (a merged commit, a passing check), not to a promise.

## Keeping it honest

- Move a card only when its real state changes, and update the timestamp. A board that lags the code misleads worse than no board.
- A card reaches Done only when its acceptance checks passed and the work is integrated, not when the code was written. Verified over optimistic, as everywhere in this module.
- One card in progress per owner at a time; parallel threads are separate cards with separate owners (`parallel-work.md`).
- Do not encode workflow rules the team has not agreed to (work-in-progress limits, mandatory columns). The board serves the work, not the other way around.
- If the board lives in the repository, commit it with the change it describes so the two stay in step; if it is a personal scratch board, keep it outside the repository and give the user its path (the handoff rules in `../../engineering-practices/references/session-handoff.md`).

## Done when

- Each task is a card with a status, an owner while active, its acceptance checks and a link to where the work lives.
- The board matches the actual state of the code and branches right now.
- Finished cards cite the evidence that closed them, and nothing is marked done that was not verified.
