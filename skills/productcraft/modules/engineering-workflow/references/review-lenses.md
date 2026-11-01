# Focused review passes

Read this when a review needs depth in one dimension, or the user asks for a specific pass: errors that fail silently, whether the tests really cover a change, type design, comments, simplification, a UI control that "does nothing", or a change written by an agent. Each lens says what to look for, how to search, how to tell a finding from noise, and what the fix looks like.

The review procedure itself (pin base and head, triage by risk, read callers and history, confirm regressions, write findings) is in `reviewing-changes.md`; findings use its format and the severity scale in `verification-and-review.md`. A lens is an independent, read-only pass over the same pinned range. On a large change, each lens can go to its own fresh helper with the same brief.

## Pick the lenses

| Lens | Run it when | Usually skip when |
|---|---|---|
| Silent failures | The change adds or edits error handling, retries, fallbacks, background jobs, scripts or CI steps | Pure refactors with no error paths touched |
| Test gaps | Every Standard or Deep change with behavior changes | Docs, formatting, renames the compiler checks |
| Type design | New domain types, state shapes, public interfaces, data models | Local helpers with one caller |
| Comments | Public APIs, tricky algorithms, comments added or now contradicted by the change | Generated code |
| Simplification | After green, on code the change added | Code the change did not touch |
| UI handler trace | A button, toggle or form "does nothing" or ends in the wrong state; a shared store changed | API-only bugs (use the debugging loop) |
| Agent-written change | Code produced by a coding agent, including yourself | Never skip; it is cheap |

## Silent failures

A silent failure is an error that is caught, converted or ignored so the program carries on as if it had succeeded. Nothing fails now; data is wrong later. The principles are in `../../engineering-practices/references/resilience.md`; this lens is how to hunt for violations.

**Let the linters search first,** with the project's configuration, on the changed files:

| Language | Rules that find swallowed errors |
|---|---|
| JavaScript, TypeScript | ESLint `no-empty` (empty `catch`), typescript-eslint `no-floating-promises` and `no-misused-promises` (type-aware) |
| Python | Ruff `E722` (bare `except`), `BLE001` (blind `except Exception`), `S110` (`try`/`except`/`pass`), `S112` (`try`/`except`/`continue`) |
| Go | `errcheck` in golangci-lint (unchecked errors; enable `check-blank` to include `_ =`) |
| Rust | The `unused_must_use` warning on ignored `Result`; review `.ok()`, `let _ =`, `unwrap_or_default()` on fallible calls |
| Java, Kotlin | Error Prone `CatchAndPrintStackTrace`; SpotBugs `DE_MIGHT_IGNORE`; PMD or Checkstyle empty-catch rules; detekt `SwallowedException`, `TooGenericExceptionCaught` |
| C# | CA1031 (catching general exceptions); `async void` methods outside event handlers |
| Shell, CI | ShellCheck SC2155 (assignment masks a return value); `\|\| true`, `continue-on-error: true`, GitLab `allow_failure: true` |

**Then read for what linters miss:**

- **Fallbacks that look like success:** `.catch(() => [])`, `except Exception: return {}`, `?? 0` after a failed call, a `null` from an error path that callers read as "not found", a retry loop that gives up and returns the default.
- **HTTP errors that never raise:** `fetch` resolves on 4xx and 5xx, so code must check `response.ok`; Python `requests` raises only after `raise_for_status()`; `subprocess.run` raises only with `check=True`.
- **Log and continue** where the next step depends on the failed one, or the same error logged at every layer and handled at none.
- **Lost causes:** rethrowing without the original (`raise X` without `from err`, `new Error(msg)` without `{ cause }`, Go `%v` where `%w` keeps the chain).
- **Async work nobody watches:** floating promises, fire-and-forget tasks or goroutines whose errors go nowhere, `Promise.allSettled` results never inspected.
- **Partial success reported as success:** a batch that catches per item and returns 200 with no count of failures; a transaction that catches an error and still commits.
- **Interfaces that hide the error:** an error state set while stale data stays on screen; an optimistic update with no rollback when the request fails.

**A legitimate ignore** is narrow (one exception type), deliberate (a comment says why), visible (a metric or a log at the right level) and harmless: best-effort cleanup after the real error, optional telemetry, "already deleted" on an idempotent delete. Anything else is a finding.

**Prove it and guard it:** inject the failure (a test double that raises, a route that returns 503, a full disk in a temporary directory) and assert the error surfaces: an exception, a non-zero exit, an error message, no success notice. That test is the fix's regression guard.

## Test gaps in a change

1. **List the changed behaviors, not lines:** new branches, new error paths, changed conditions and defaults, new inputs and outputs.
2. **Find the test that would fail** if each behavior were wrong. The quickest proof is a mutation: in a scratch worktree, revert or break the behavior and run the nearest tests (the mutation check in `test-first.md`; `cargo mutants --in-diff` or Stryker's `--mutate` for many at once). No failure means no protection.
3. **Judge the assertions:** "does not throw", "status 200" or "was called" with nothing about the result; expected values computed by the code under test; mocks that return whatever the code asks for; snapshots regenerated in the same change.
4. **Check the edges:** empty, one, many, boundary values, invalid input, a dependency that fails or times out, a retried or duplicated request, two actors at once.
5. **Rate each gap:** Critical (money, permissions, data loss or a public contract untested), Important (a likely bug path untested), Nice to have. For each gap, name the test to add: its name and its case.

Coverage of changed lines (`diff-cover`) shows what never ran; it does not show what is asserted. Use it to find candidates, not to close the lens.

## Type design

Ask whether the types make invalid states hard to build:

- **Can a value exist that the domain forbids?** Separate flags (`isLoading`, `error`, `data` all optional) allow nonsense combinations; a tagged union does not.

  ```typescript
  type Load<T> =
    | { state: 'idle' }
    | { state: 'loading' }
    | { state: 'failed'; error: string }
    | { state: 'loaded'; data: T };
  ```

- **Where is the invariant enforced?** One parse or constructor at the boundary (`parseEmail(raw): Email`) beats the same check scattered through callers.
- **Escape hatches:** public setters on objects with invariants, mutable collections handed out, `any`, unchecked casts, non-null assertions, default constructors that produce invalid objects.
- **Primitive obsession:** identifiers that can be swapped (`userId` and `orderId` both `string`), money as a float, quantities without units (`../../engineering-practices/references/spec-and-units.md`).
- **Is it worth it?** A stronger type earns its cost where a wrong value is expensive and callers are many. Do not propose type machinery for a helper with one caller.

A finding shows the invalid state, how it is reachable, and the caller that mishandles it, with a sketch of the type that prevents it.

## Comments

- **Accuracy:** read every comment and docstring in the diff, and those of changed functions, against the code: parameters, return values, raised errors, units, side effects. A comment that contradicts the code is a Should fix; one that misleads about safety ("thread-safe", "never null", "validated upstream") can be a Blocker.
- **Staleness:** references to removed functions, flags, files or behavior.
- **Debt markers added by the change:** `git diff <base>...HEAD | grep -nE '^\+.*\b(TODO|FIXME|HACK|XXX)\b'`; each needs an owner or an issue (`change-discipline.md`).
- **Low value:** comments that restate the code; commented-out code. Suggest deleting them, as Optional findings.

## Simplification

Run only on code the change added, only with the tests green, and keep the result in its own commit. Every step must keep behavior identical; when in doubt, add a characterization test first (`test-first.md`).

- Dead code the change created: unused parameters, imports, branches, return values nobody reads.
- Nesting that guard clauses flatten; conditions that can be named; duplicated blocks inside the diff.
- Abstractions with one implementation and one caller, options with one value, wrappers that only forward (`change-discipline.md`, signs of speculative design).
- Hand-written versions of what the standard library or an installed dependency already does.

Not in scope: reformatting untouched code, repository-wide renames, clever one-liners, and removing validation at trust boundaries, error handling or accessibility to shorten the diff.

## UI handler trace: the control that "does nothing"

Use when a handler runs without errors yet the final state contradicts what the control's label promises. Static reading misses these because each function works on its own.

1. **Map the shared state actions in scope.** For every store action, reducer or setter the handlers call, write what it sets and what it resets as a side effect: `selectThread(t)` sets `selectedThread`, `messages`; resets `composeMode`, `draft`. Mark actions that reset fields they do not own.
2. **Trace each control's handler in order.** For each call: what it reads, what it writes, what it resets. Then check:
   - a later call undoes an earlier one (set `composeMode = true`, then `selectThread(null)` resets it);
   - async results that can arrive out of order and overwrite newer state (guard with a request id or `AbortController`);
   - stale closures (`setCount(count + 1)` twice adds one; use the functional update form);
   - an effect that watches the state and resets it;
   - a condition that is always false at that point, so the real work never runs;
   - a label that promises an action the handler never performs (validates but never saves; sets a flag but never calls the API).
3. **Compare the final state with the label's promise.**
4. **Confirm with a test** that clicks the control and asserts the promised outcome; for races, control the order in which the stubbed responses resolve.

Write each finding as: control and location, the call sequence with the conflicting write marked, expected and actual state, and the fix (reorder the calls, stop the action resetting fields it does not own, add a dedicated action for the combined transition).

## Changes written by an agent

When the same model writes and reviews, both steps share its assumptions. Lean on checks that do not depend on judgment:

- **Mechanical first:** run the tests, type check, linters and build before reading. A failure there is a finding that needs no argument.
- **Parallel paths drift.** Code often has two paths behind one contract: a real backend and a fake, demo or sandbox mode; cached and fresh; old and new handler versions; server and client rendering; single and batch. A change frequently lands in one. `git grep` the field or function name, and add a contract test that runs every path and asserts the same response shape.
- **A field added end to end** must appear in the query or projection, the mapping, the serializer, the API type, the client type and the screen. The classic miss is a field added to the response mapping but not to the selected columns, so it is always empty. Assert the field's value, not just its presence.
- **Error and rollback paths** are the ones agents most often leave untested: failed requests, partial writes, optimistic updates.
- **Tests edited in the same change** get the scrutiny in `reviewing-changes.md`, step 7.
- **Every bug fixed gets a regression test** that reproduces the real failure shape through the same entry point, seen red before the fix and green after.
- **A second reviewer with fresh context** (a new helper, another model, or a person) gets the pinned range and the brief, not the transcript. Sending code to a model service outside the project's approved tools needs the owner's agreement.

## Before reporting: rule out false alarms

Drop or downgrade a candidate when:

- the error is handled one frame up (the caller, framework error middleware, an error boundary) and you traced it there;
- callers validate the input (read at least one caller before flagging "missing validation");
- a guard or narrowed type in scope already rules out the null;
- the fire-and-forget call is intentional and marked (a `void` prefix, a comment);
- the loop has a small fixed size, so the "N+1" costs nothing;
- the value is a test fixture, a well-known constant or a non-cryptographic random number for jitter or sampling;
- the suggestion is a style preference the project's conventions do not require, or a change of language or framework.

A pass that finds nothing is a valid result; report it as such, with what was checked.

## Done when

- [ ] The lenses that fit the change were run, and the report says which and why the others were skipped.
- [ ] Each finding has a location at the reviewed head, a concrete failing case, its effect, the smallest fix and an evidence label (demonstrated or reasoned).
- [ ] Silent-failure and handler findings were demonstrated by an injected failure or a test where that was cheap and safe.
- [ ] Test-gap findings name the missing test and its case.
- [ ] Nothing was edited, posted or merged without the user's request.
