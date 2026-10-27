# Delivering complete code, and splitting long output cleanly

Read this before you hand over a file, a patch or a set of files, and whenever a response is large enough that you are tempted to abbreviate it. The rule is simple: what you deliver must be whole. A file with a gap in the middle is not a smaller deliverable, it is a broken one, because the reader cannot run it and often cannot even tell what is missing.

This is not the same as `../../lean-output.md`. Lean output shortens the *prose around* the work on request; it never shortens the work. This reference is about the work itself: code, configuration and files, which are complete at every output level.

## What "complete" means

A deliverable is complete when the reader can use it without filling in anything you left out:

- Every file the task calls for exists, in full, from first line to last.
- Every function, class, branch and case the task needs is implemented, not described.
- Imports, types, configuration keys and wiring that the code depends on are present.
- Nothing is left as an exercise, a "same as above", or a comment standing in for code.

A skeleton is a correct deliverable only when the task asked for a skeleton (a template, a stub to fill in, an interface to implement later). Then the gaps are the point and you label them as such. Otherwise, gaps are defects.

## Placeholders that are not acceptable in delivered code

Do not emit these in a file or patch the user will keep, and remove them if they crept into your own draft:

- Elision inside code meant to run: `// ... rest unchanged`, `# ... (keep existing)`, a bare `...` where statements belong, `/* existing code here */`.
- A single example with "repeat for the others" in place of the other cases the task requires.
- The first and last part of a file with the middle skipped.
- Prose describing what the code should do, where the code itself was asked for ("this function would validate the token and ...").
- "Left as an exercise", "fill in your logic here", "and so on", when real content belongs there.

These differ from legitimate markers. A `TODO` with an owner for genuinely deferred work, a documented stub behind a feature flag, or an abbreviated *illustration in chat* that is clearly not the deliverable are fine. The test is whether the reader is expected to run what you gave them. If yes, it is whole.

## Elision inside a patch is different

When you show a change as a unified diff or a few edited lines rather than a whole file, you are not eliding the file: the unchanged lines genuinely stay as they are, and the diff's context lines place the change. That is complete, because applying the diff produces the whole file. What is never acceptable is a diff or an edit block with `...` standing in for lines you actually intend to change, or context so thin the hunk cannot be located. Give enough surrounding lines to apply the change unambiguously (`change-discipline.md` covers the diff self-checks).

## Scope the work before you build it

Most truncation starts as a scope that was never counted. Before building:

1. Read the whole request and count the distinct deliverables: files, functions, endpoints, components, answers. Write the number down.
2. Build each one in full. Do not start the next until the current one is whole.
3. Before finishing, compare what you produced against the count. Anything short of it is unfinished work, not a stylistic choice.

## When the output is genuinely too long

Some deliverables do not fit in one response. Splitting is fine; abbreviating to fit is not. When you approach the limit:

- Do not compress later sections or drop to a summary to squeeze everything in.
- Stop at a clean boundary: the end of a file, a function, or a self-contained section, never mid-statement.
- Say exactly where you stopped and what remains, so continuing is unambiguous: which files are done, which is next, and the point to resume from.
- On "continue", resume at that boundary without repeating what you already delivered and without re-deriving it.
- Prefer boundaries that leave the delivered part usable on its own: a complete module now, its dependents next, rather than half of each.

For work that spans sessions rather than one long reply, write a handoff instead so a fresh agent can resume (`../../engineering-practices/references/session-handoff.md`).

A better fix than splitting is often to deliver less surface: build the files to disk and report the paths and a short summary, rather than pasting every file into chat. The files are complete on disk; the reply stays short. This also keeps the context free for verification.

## Done when

- The number of deliverables produced matches the number the request implies, each one whole.
- No elision, "rest unchanged", lone `...` or "describe instead of write" appears in any file or patch meant to be used.
- Any split was at a clean boundary, with the remainder named precisely, and the delivered part works on its own.
- The code you handed over runs or applies as given, verified by the project's own checks (phase 6 of the workflow).
