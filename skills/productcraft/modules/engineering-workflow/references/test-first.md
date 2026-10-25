# Test-first, characterization tests and test quality

Read this when writing or changing tests, when working in code that has none, or when a suite is flaky.

## Run one test, then the suite

Keep the loop fast by running the single test you are working on, then the surrounding suite. Prefer the project's own wrapper (`npm test -- <args>`, `make test`) when it sets environment or configuration.

| Stack | One test | Suite |
|---|---|---|
| pytest | `pytest tests/test_tax.py::test_zero_rate -q` | `pytest -q` |
| unittest | `python -m unittest tests.test_tax.TaxTests.test_zero_rate` | `python -m unittest discover -s tests` |
| Jest | `npx jest src/tax.test.ts -t "zero rate"` | `npm test` |
| Vitest | `npx vitest run src/tax.test.ts -t "zero rate"` | `npx vitest run` |
| Go | `go test ./billing -run TestZeroRate -v` | `go test ./...` |
| Rust | `cargo test zero_rate` | `cargo test` |
| Maven | `mvn -Dtest=TaxTest#zeroRate test` | `mvn test` |
| Gradle | `./gradlew test --tests 'TaxTest.zeroRate'` | `./gradlew test` |
| .NET | `dotnet test --filter "FullyQualifiedName~TaxTests.ZeroRate"` | `dotnet test` |
| RSpec | `bundle exec rspec spec/tax_spec.rb:42` | `bundle exec rspec` |

## Red, green, refactor in practice

**Red.** Write a test for the next behavior on your done-when list and run it.

- It fails on an assertion about that behavior: good, continue.
- It fails with an import, name or compile error: add just enough scaffolding (an empty function, a stub returning nothing) until it fails on the assertion.
- It passes straight away: either the behavior already exists, and you may not need new code, or the test doesn't exercise what you think. Find out which before going on.

**Green.** Write the simplest code that passes. Don't add branches no test needs yet; the next test will ask for them. Run the test, then its neighbors.

**Refactor.** With everything green, improve names, remove duplication and simplify, in small steps, rerunning after each. No new behavior during this step.

Pick the next test from the done-when list. Edge cases are separate tests: empty, one, many, boundary values, invalid input, and failure of a dependency. When the input space is too large for hand-picked cases, add a property test (`../../engineering-practices/references/advanced-testing.md`).

When you explored first and wrote code before tests, either delete the exploration and redo it test-first, or at least prove each new test can fail with the mutation check below.

## Characterization tests for legacy code

Goal: a safety net that records what the code does today, so a refactor cannot change behavior without a test noticing.

1. **Pick the seam:** the narrowest entry point that covers the code you will change (a function, a CLI command, an HTTP endpoint).
2. **Make it runnable in a test:** control time (an injected clock, `freezegun`, fake timers), randomness (a fixed seed), and files and network (temporary directories, local fakes, environment variables set by the test).
3. **Feed representative inputs:** typical cases, boundaries, and the odd ones from bug reports or logs (with personal data removed).
4. **Assert what it returns now.** Write a deliberately wrong expectation, run the test, and copy the actual value from the failure into the assertion. Label surprises instead of fixing them: `# current behavior, possibly a bug: negative quantity gives a negative total`.
5. **Large outputs:** compare against a stored approved file (a golden master or snapshot) and review that file like code.
6. **Check reach:** run coverage over just these tests (`coverage run -m pytest tests/characterization && coverage report -m`, `npx jest --coverage <path>`, `go test -cover ./<pkg>`) and confirm the lines you will change are executed.
7. **Refactor in small steps,** rerunning each time. A failing characterization test means behavior changed: undo the step, or turn it into a deliberate change.
8. **Change behavior deliberately:** in a separate commit, updating the characterization assertion with a note saying why.

Getting untested code under test with the smallest seams:

- Pass a dependency in as a parameter whose default is the old behavior.
- Pull the pure calculation out of the function that also does input and output.
- Wrap a global or static call in a small function you can replace in tests.
- Write new logic as a new, tested function and call it from the legacy code, instead of editing deep inside it (the classic "sprout" technique).

Avoid big rewrites to make code testable before any safety net exists.

## What makes a test worth keeping

- **It names a failure.** You can say which bug it would catch. If you can't, don't write it.
- **Expected values are independent.** Use literals or hand-worked examples, not values computed by the code under test or by re-implementing its formula in the test.
- **It tests behavior through the public interface,** not private fields, the call order of internal helpers or exact log wording, unless that is the contract.
- **Doubles sit at real boundaries only:** network, clock, randomness, slow or paid services, systems owned by others. Learn what the real dependency does before faking it, and make fakes return realistic, complete data. Checking that a double was called is meaningful only when the call *is* the behavior, such as "sends exactly one email".
- **One behavior per test,** and the name says the behavior and condition: `test_rejects_expired_coupon`, `"returns 404 when the invoice belongs to another tenant"`.
- **Deterministic and isolated:** no dependence on test order, no shared mutable fixtures, its own temporary directory, no fixed sleeps. Wait for the condition with a timeout instead (`waitFor`, `expect.poll`, `Eventually`, or a polling loop that fails with a clear message).
- **Fast enough to run on every change.** Mark slow tests the way the project does so CI still runs them.
- **Test-only helpers live in test code,** not as extra methods on production classes.

## Mutation check: prove the test bites

After green, break the code on purpose (flip a comparison, return early, drop a call) and confirm a test fails. Revert, and check with `git diff` that your break is gone. For larger efforts, mutation testing tools automate this: mutmut (Python), Stryker (JavaScript and TypeScript, C#, Scala), PIT (Java), cargo-mutants (Rust). Run them on the module you changed, not the whole repository; commands, reading the results and triaging surviving mutants are in `../../engineering-practices/references/advanced-testing.md`.

## Test changes that need a reason

| Change | Why it is suspicious | What to do |
|---|---|---|
| Deleting or skipping a failing test | Hides a regression | Find out why it fails; delete only with agreement and a reason |
| Loosening an assertion (exact value to "contains", value to "not null") | The test can no longer catch the bug | Keep it strict unless the contract changed |
| Regenerating all snapshots | Approves whatever the code does now | Review the snapshot diff line by line |
| Adding sleeps or raising timeouts | Masks a race | Wait for the condition; fix the race |
| Committing a focused test (`.only`, `fit`) | The rest of the suite silently stops running | Remove it before committing |
| Catching an exception inside the test so it passes | Swallows the failure | Assert the exception explicitly |

`../scripts/diff_scope.py` flags several of these in a diff.

## Flaky tests

- **Measure the rate:** `for i in $(seq 1 30); do pytest -q tests/test_sync.py::test_merge >/dev/null || echo "failed on run $i"; done`.
- **Shuffle order** to expose hidden dependencies: the pytest-randomly plugin (shuffles once installed; replay an order with `--randomly-seed=<n>`), `go test -shuffle=on ./...`, `jest --randomize`, `rspec --order random`. Record the seed of a failing order so you can replay it.
- **Find the polluting test** by bisecting the list of tests that run before the flaky one: run half of them followed by the flaky test, keep the half that reproduces the failure, and repeat.
- **Usual causes:** shared global state, order dependence, the real clock, fixed timeouts, unawaited async work, port or file collisions, real network calls.
- Quarantine a flaky test only with the user's agreement and a tracked issue. A quarantined test is not a passing test.
