# Debugging to the root cause

Read this for any bug, failing or flaky test, crash, wrong output, build or CI failure, or regression. The goal is a fix you can explain, at the place the problem starts, with a test that keeps it fixed.

## 0. Use the evidence you already have

- Read the whole error message and stack trace. In a long log, the first error is usually the cause and later ones are fallout.
- Note the file, line, error code and versions involved.
- Ask what changed: `git log --oneline --since="3 days ago" -- <area>`, `git diff <last-known-good>..HEAD -- <area>`, dependency and lockfile changes, configuration and environment changes.

## 1. Reproduce

- Record the exact command, input, environment and versions in a short debug log (template at the end).
- Make the reproduction small: a failing test if the harness allows it, otherwise a script that exits non-zero on failure.
- **Intermittent failure:** run it in a loop and count (4 failures in 50 runs is a fact you can compare against later). Vary load, parallelism and test order.
- **Can't reproduce:** don't guess. Collect more: logs with request or correlation IDs, targeted logging in a test environment, and a comparison of environments (`python -VV` and `pip freeze`, `node -v` and `npm ls --depth=0`, `go version` and `go list -m all`), configuration and data.
- **Done when:** one command reliably shows the failure, or you have a measured failure rate.

## 2. Isolate

| Technique | Use when | How |
|---|---|---|
| Bisect history | It used to work | `git bisect start`, `git bisect bad HEAD`, `git bisect good <sha>`, then `git bisect run ./repro.sh` (exit 0 = good, 125 = skip this commit, any other code from 1 to 127 = bad). Finish with `git bisect reset`. |
| Shrink the input | A large input fails | Halve it repeatedly and keep the half that still fails; then remove fields or lines one at a time |
| Log at boundaries | Data flows through several components | Log once what enters and leaves each component (IDs, sizes, types, never secrets or personal data) and find the first boundary where the data is already wrong |
| Compare working and failing | It works somewhere else | Compare environment variable names, configuration, dependency versions, data, feature flags, OS, architecture, locale and time zone |
| Change one thing per run | Several suspects | Alter exactly one variable per experiment and write down the outcome |
| Step through | A logic error on a reachable path | `python -m pdb`, `node --inspect`, `dlv test`, or the IDE debugger; inspect state just before the failure |
| Trace backward | A wrong value surfaces deep in the call stack | From the line that misbehaves, find where the value came from; repeat up the call chain until you reach the point where it first became wrong |

**Done when:** you can point to the component, function or commit, and the input, that make the difference between working and failing.

## 3. Hypothesize

Write it down in one line:

> Cause: the cache key omits the locale. Evidence: the second request returns the first request's language. Prediction: two requests for the same page in `fr` then `en` within the TTL return French text both times.

Prefer the hypothesis that explains all observations, not only the loudest one. Keep the list of hypotheses and cross out each one that an experiment rules out.

## 4. Test the hypothesis

- Design an experiment that could come out against you: log the suspect value, run the predicted input, revert the suspect commit locally, or pin the old dependency version.
- Change one thing per experiment. Revert experiment code that didn't confirm anything before trying the next idea.
- A change that makes the symptom go away without a confirmed cause is a coincidence until proven otherwise.
- **Done when:** the prediction held and the other explanations on your list are ruled out, or you say which ones remain possible.

## 5. Fix at the source

- Fix where the wrong value or state originates. Checks added downstream only hide the problem from the next person.
- If bad data enters from outside (user input, an external API, a file), validate at that trust boundary with a clear error, rather than adding defensive checks to every layer.
- Look for siblings: `git grep` for the same pattern (copy-pasted code often carries the same bug). Fix shared code once instead of patching each caller. If siblings lie outside the task, report them and ask before widening the change.
- Make one fix, with no unrelated refactoring in the same change.

## 6. Guard with a regression test

- Write the regression test, or promote the reproduction into one.
- Prove it guards: with the fix removed (`git stash push -- <source files of the fix>`, leaving the test file in place, or comment out the fix), the test fails; with the fix restored (`git stash pop`), it passes.
- Name the test after the behavior (`test_cache_key_includes_locale`), not the ticket number; link the issue in a comment if the project does that.
- Run the surrounding suite, then the full suite before finishing.
- Remove temporary logging, prints and breakpoints. `git diff` and `../scripts/diff_scope.py` catch most leftovers.

## When to stop and step back

Stop editing code when three fix attempts have failed, or when each fix exposes a new problem somewhere else. That pattern usually means a wrong assumption about the design (shared mutable state, unclear ownership of data, two sources of truth), not a missing patch. Revert the failed attempts so they don't pile up, write down what each attempt showed and what is ruled out, and bring the user options before going further.

## Special cases

- **External or environmental causes** (provider outage, clock skew, unreliable network): record the evidence, add bounded handling (a timeout, a few retries with backoff, a clear error message) and logging that would confirm the cause next time. Say plainly that the cause is external or not yet confirmed.
- **Failures that vanish under the debugger or extra logging:** suspect timing and concurrency. Use low-overhead logging with timestamps, add parallel load, and look for unsynchronized shared state.
- **Performance regressions:** measure before changing anything, with a profiler or timings on a fixed input; techniques are in `../../engineering-practices/GUIDE.md`.
- **Production problems:** do not debug against production systems or real user data without permission. Reproduce locally with sanitized data.
- **Fails only in CI:** compare CI and local versions, environment, caches, OS, locale and time zone, file-system case sensitivity and parallelism. Run the failing step locally in the same container image if the project provides one.

## Debug log template

```text
Symptom:
Reproduction: <command> -> <observed result> (rate: n of N runs)
Environment: <versions, OS, relevant config>
Ruled out: <what and how>
Hypothesis 1: <cause> | prediction: <...> | result: confirmed / ruled out (<evidence>)
Cause: <one or two sentences>
Fix: <file and function>, and why the fix belongs there
Regression test: <name> | fails without fix: yes/no | passes with fix: yes/no
Suite: <command> -> <result>
```
