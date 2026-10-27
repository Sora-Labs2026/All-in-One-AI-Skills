# Advanced testing: properties, mutants, differential and metamorphic checks

Read this when hand-picked examples are not enough to trust a piece of code: codecs, parsers, money or date arithmetic, data structures, state machines, a rewrite that must keep behavior, or a suite whose real strength nobody knows. Fuzzing has its own file (`fuzzing.md`). Checking code against a specification and checking units of measure are in `spec-and-units.md`. Ordinary unit tests, characterization tests and flaky tests stay in `../../engineering-workflow/references/test-first.md`.

These techniques sit on top of a few readable example tests; they do not replace them. A new test library is a development dependency: propose it once, with the concrete property you would write, and follow `dependencies.md` if the user agrees.

## Pick the technique

| Technique | Pays off when | Usually not worth it when | Typical cost |
|---|---|---|---|
| Property-based tests | A rule holds for every valid input: round trips, invariants, laws, bounds, a simpler model to compare with | The code is wiring, CRUD plumbing or layout, or the only rule you can state is "does not crash" (fuzz that instead) | Minutes to write, seconds per run |
| Model-based (stateful) tests | Sequences of operations matter: caches, queues, ledgers, carts, sessions, an API resource with create, update and delete | Single pure functions | An hour to write a model |
| Mutation testing | You must know whether the suite would catch a bug in critical code (authorization, billing, parsers), before a risky refactor, or when coverage is high and bugs still escape | No fast, deterministic suite exists yet | CPU minutes to hours; always scope it |
| Differential testing | Two implementations should agree: old and new during a refactor, fast and simple, your code and a mature library, two builds or platforms | No second implementation exists and none is cheap to write | Low once inputs exist |
| Metamorphic testing | No oracle gives the exact output (ranking, simulation, ML inference, geometry, report generators), but you know how the output must change when the input changes | An exact expected value is easy to work out by hand | Low |

| Combinatorial / pairwise tests | Several independent parameters interact and the full cross-product is too large to run: feature flags, configuration matrices, input-field combinations, platform and locale grids | One or two parameters, or the parameters are not independent so most combinations are invalid | Low once the model exists |
| Known-answer vectors | A published standard defines inputs and outputs: hashes, MACs, encodings, TOTP, Unicode, URL parsing | The domain publishes no vectors | Low |

## Property-based testing

A property test states a rule, lets a generator produce hundreds of inputs, and when the rule breaks, shrinks the failing input to a small counterexample.

### Find a property that can fail

| Family | Examples |
|---|---|
| Round trip | `parse(render(x)) == x`, `decode(encode(x)) == x`, `load(dump(cfg)) == cfg` |
| Agrees with a simpler model | Optimized search vs a linear scan; new pricing vs the legacy function; a repository class vs a plain dictionary |
| Invariant kept | Output is sorted and a permutation of the input; balances never go negative; splitting an amount into shares loses no cent; no duplicate IDs |
| Idempotence | `normalize(normalize(x)) == normalize(x)`; running the same import twice leaves one copy |
| Laws | `merge(a, b) == merge(b, a)`; `merge(a, merge(b, c)) == merge(merge(a, b), c)`; adding then removing an item restores the cart; equal values have equal hashes |
| Bounds and direction | A larger discount never raises the price; an extra filter never returns more rows; a probability stays in [0, 1] |
| Equivalent routes | Processing a batch at once or in two halves gives the same state; concatenated pages equal the unpaginated list |
| Error contract | For any input: a result or the documented error type, never another exception, never a hang |
| Determinism | Same input, same bytes, where purity is not certain: serializing maps and sets, output that depends on hashing or iteration order |

A property must be able to fail when the code is wrong. Two common ways it cannot:

- **Restating the implementation:** `assert total(lines) == sum(l.amount for l in lines)` shares every bug with a `total` written the same way. Assert something that constrains the result without recomputing it: a law, a bound, a comparison with an independent model.
- **Filtering everything away:** `assume()` calls that reject most inputs, or contradict each other, leave a test that passes after checking almost nothing. Build valid inputs in the generator instead (below).

If nothing stronger than "does not crash" turns up, the code may only need rearranging. Suggest it and let the user decide: pull the calculation out of the function that also reads and writes, return a new value instead of mutating in place, add the missing inverse (a parser for a renderer, a decoder for an encoder), or pass a limit as a parameter so the generator can push it to 0, 1 and the maximum.

### Generate the right inputs

- **Construct, don't reject.** Put bounds in the strategy (`st.integers(min_value=1)`, `fc.integer({ min: 1 })`, `1u32..`), and derive dependent values from earlier draws (`st.composite` or `.flatmap`, `fc.chain`, `prop_flat_map`). Keep `assume`, `fc.pre` and `prop_assume!` for rare conditions between already drawn values.
- **Aim at the corners:** empty, one, many; duplicates; zero, negative, maximum; NaN, infinities and very small (subnormal) floats (decide whether they are in the domain); non-ASCII, combining marks and lone surrogates in text; deep nesting; time zones, daylight-saving gaps and leap days.
- **Pin the cases you already know** as explicit examples (`@example(...)`, fast-check's `examples` option, or a plain example test) so they run every time.
- **Derive domain objects from types** (`st.builds(Order)`, `st.from_type(Order)`), then override fields whose real domain is narrower than the type.
- **Look at what is generated** before trusting a green run: `pytest --hypothesis-show-statistics` with `hypothesis.event()`, `fc.sample(arb, 20)` and `fc.statistics(...)`.

### When a property fails

1. Read the shrunk counterexample. It is usually small enough to reason about directly.
2. **Ground it:** is that input inside the documented domain? Check, in order of authority, the external specification, the types, the docstring or API docs, and the existing tests. The function name is the weakest evidence.
3. Act on the answer:
   - Outside the domain: narrow the generator, and consider validating at the trust boundary.
   - The specification is silent: that is a product decision. Ask the owner; don't pick silently.
   - Inside the domain and the rule breaks: it is a bug. Save the input as a permanent example test, then follow the debugging loop in `../../engineering-workflow/references/debugging.md`.
4. **Keep the failure reproducible:**
   - Hypothesis replays recent failures from its local `.hypothesis/` database (a cache; keep it out of version control). Copy the shrunk value into an `@example` for a permanent guard; a printed `@reproduce_failure(...)` line (enable `print_blob=True` if it is missing) replays the exact case.
   - fast-check prints a `seed` and a `path`; rerun with `fc.assert(prop, { seed, path, endOnFailure: true })`.
   - proptest writes `proptest-regressions/*.txt` files: commit them so the case reruns first.
   - rapid prints a command with `-rapid.failfile=...`.
5. A property that fails only sometimes depends on the clock, randomness, unordered iteration, float tolerance or a real service. Fix that cause (inject the clock, sort before comparing, use `math.isclose` or `pytest.approx` with a stated tolerance). Do not lower the example count to hide it.

### Budgets

Libraries default to about 100 cases per property. Keep the local run quick, raise the count in CI, and run a large count on a schedule:

```python
# conftest.py
import os
from hypothesis import settings

settings.register_profile("dev", max_examples=50)
settings.register_profile("ci", max_examples=500, deadline=None)
settings.register_profile("nightly", max_examples=5000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
```

`pytest --hypothesis-profile=ci` selects a profile per run; `deadline=None` stops slow CI machines from failing tests on timing. Elsewhere: fast-check `{ numRuns: 1000 }`, the `PROPTEST_CASES` environment variable, Go's `-rapid.checks=1000`.

### Model-based tests for sequences of operations

Generate random sequences of commands, apply each to the real implementation and to a deliberately simple model (a dictionary, a list), and compare the observable state after every step. Shrinking reduces a failure to the shortest sequence that breaks. Tools: Hypothesis `RuleBasedStateMachine` with `@rule` and `@invariant`, fast-check `fc.commands` with `fc.modelRun`, the `proptest-state-machine` crate, and rapid's state-machine support. Good targets: an LRU cache against an ordered dictionary, a money ledger against a list of entries, a REST resource against an in-memory map.

### Minimal examples

Check the dependency manifests for a library the project already uses before adding anything: `rg -il 'hypothesis|fast-check|proptest|pgregory.net/rapid|jqwik' pyproject.toml requirements*.txt package.json Cargo.toml go.mod pom.xml build.gradle*`

```python
# Python, Hypothesis
from decimal import Decimal
from hypothesis import example, given, strategies as st
from billing.money import format_amount, parse_amount

amounts = st.decimals(min_value=Decimal("-1e12"), max_value=Decimal("1e12"),
                      places=2, allow_nan=False, allow_infinity=False)

@given(amounts)
@example(Decimal("0.00"))
@example(Decimal("-0.01"))
def test_amount_text_round_trips(value):
    assert parse_amount(format_amount(value)) == value
```

```ts
// TypeScript, fast-check with Vitest (@fast-check/vitest); Jest has @fast-check/jest
import { test, fc } from '@fast-check/vitest';
import { expect } from 'vitest';
import { mergeIntervals } from './intervals';

const interval = fc.tuple(fc.integer({ min: -1e6, max: 1e6 }), fc.nat(1000))
  .map(([start, len]) => ({ start, end: start + len }));

test.prop([fc.array(interval)])('merging is idempotent and keeps every point covered', (xs) => {
  const merged = mergeIntervals(xs);
  expect(mergeIntervals(merged)).toEqual(merged);
  for (const x of xs) expect(merged.some((m) => m.start <= x.start && x.end <= m.end)).toBe(true);
});
```

```rust
// Rust, proptest
use proptest::prelude::*;

proptest! {
    #[test]
    fn header_round_trips(name in "[A-Za-z][A-Za-z0-9-]{0,30}", value in "[ -~]{0,200}") {
        let line = format_header(&name, &value);
        // A parser that trims trailing spaces fails here: decide whether that is the contract.
        prop_assert_eq!(parse_header(&line).unwrap(), (name, value));
    }
}
```

```go
// Go, pgregory.net/rapid (the standard library's testing/quick is frozen but still works)
func TestJoinSplitRoundTrip(t *testing.T) {
	rapid.Check(t, func(t *rapid.T) {
		parts := rapid.SliceOf(rapid.StringMatching(`[a-z,"]{0,8}`)).Draw(t, "parts")
		got, err := csvline.Split(csvline.Join(parts))
		if err != nil || !slices.Equal(got, parts) {
			t.Fatalf("round trip of %q gave %q (err %v)", parts, got, err)
		}
	})
}
```

Other ecosystems: jqwik (Java), Kotest property testing (Kotlin), FsCheck or CsCheck (.NET), ScalaCheck, StreamData (Elixir), QuickCheck or Hedgehog (Haskell), RapidCheck (C++).

## Mutation testing

A mutation tool makes one small change at a time (flips `<` to `<=`, swaps `+` for `-`, negates a condition, returns a default value, deletes a call) and reruns the tests. A mutant that survives marks behavior no assertion checks. Coverage says which lines ran; mutation testing says whether running them proved anything.

### Run it scoped

Start from a green, deterministic suite and estimate the cost first: mutants times the test time for that code. Mutate the module you changed or the code that protects money, permissions or data, never the whole repository on every push.

```bash
# Python: mutmut (runs pytest; version 3 needs Linux or macOS, use WSL on Windows)
#   pyproject.toml ->  [tool.mutmut]  paths_to_mutate = ["src/billing/"]
mutmut run && mutmut results          # then: mutmut show <mutant-name>

# JavaScript and TypeScript: Stryker (also Stryker.NET via `dotnet stryker`)
npm init stryker@latest               # writes a config for the project's test runner
npx stryker run --mutate "src/billing/**/*.ts,!src/**/*.test.ts"   # HTML report in reports/mutation/
npx stryker run --incremental         # later runs reuse earlier results

# Rust: cargo-mutants
cargo install --locked cargo-mutants
cargo mutants --list --file src/billing.rs    # preview
cargo mutants --file src/billing.rs -j 4      # survivors listed in mutants.out/missed.txt
git diff origin/main... > /tmp/changes.diff && cargo mutants --in-diff /tmp/changes.diff

# Java: PIT
mvn org.pitest:pitest-maven:mutationCoverage -DtargetClasses='com.example.billing.*'
```

Go has no mutation tool in its toolchain; community tools exist (for example gremlins, `gremlins unleash ./billing`). Check that one is maintained and supports the project's Go version before relying on it. Without any tool, the manual mutation check in `test-first.md` still works.

### Read the results

- **Killed:** a test failed on the mutant. Good.
- **Survived:** tests passed with the mutant in place. Triage below.
- **No coverage:** no test even executes that code. Fix these first; they are the cheapest wins.
- **Timeout:** the mutant usually made a loop run forever. Most tools count this as detected; spot-check a few.
- **Unviable or compile error:** the mutant did not build. Ignore.

### Triage survivors

1. Read the mutant's diff (`mutmut show`, the Stryker HTML report, `mutants.out/missed.txt` for the location, the cargo-mutants log for the diff).
2. Decide whether it is **equivalent**: no input can tell it apart from the original. Typical cases: `i < n` changed to `i != n` in a loop counting up by one from zero to a length, which is never negative; a change to a value that is never read afterwards; a change inside code no input can reach. Prove equivalence from types and control flow. "No test reaches it" is a gap, not equivalence, and a moved boundary (`>` to `>=`) is equivalent only if the boundary value cannot occur.
3. Otherwise **write the test that tells them apart:** the input where the original and the mutant disagree, with an assertion on the outcome. Rerun and watch the mutant die.
4. Sometimes the mutant is the correct behavior (the specification says `>=`). Then it is a bug: fix it with a regression test.
5. Work in priority order of what the code protects: authorization, validation and security checks; then money, persisted state and state transitions; then other business rules; last, logging and display text.
6. Record accepted equivalent mutants with the tool's own marker and a reason: Stryker `// Stryker disable next-line <mutator>: <reason>`, mutmut `# pragma: no mutate`, cargo-mutants `#[mutants::skip]` or `exclude_re` in `.cargo/mutants.toml`.

Report the score (killed of total, per module) together with the surviving mutants in critical code and what you did about each. A score target invites tests written to kill mutants rather than to check behavior; don't add a CI threshold without the user's agreement, and if one is added, apply it to changed code (`--in-diff`, `--incremental`) rather than the whole repository.

## Differential testing

Run two implementations on the same inputs and investigate every difference.

1. **Choose the pair.** Old and new during a refactor (keep the old function callable until the switch, as in `large-refactors.md`); a slow, obviously correct version beside an optimized one; a mature implementation (your CSV writer against Python's `csv` module, your query against SQLite); two versions of a dependency before an upgrade; a debug and an optimized build; two platforms.
2. **Feed both the same inputs:** generated ones (a property `assert new(x) == old(x)`), existing fixtures, a fuzz corpus, or recorded real inputs only if the user allows it and personal data has been removed.
3. **Normalize before comparing:** ordering where it is not part of the contract, whitespace, timestamps and generated IDs, float tolerance, and error categories (both reject the input, even with different messages).
4. **Classify each difference:** a bug in the new code; a bug in the old code (callers may rely on it, so ask before changing behavior); an intended change (write it into an allowed-differences list with the reason); or noise (extend the normalization).
5. **Finish** when a stated set of inputs runs with zero unexplained differences, then remove the old path as planned.

Comparing against live production traffic (shadow or dark launches) needs explicit permission, read-only paths and no duplicated side effects; plan it with `ci-and-release.md`.

## Metamorphic testing

When the exact output is unknown, test how it must change. Run the code on an input, transform the input in a way whose effect you know, run again, and check the relation between the two outputs.

| Domain | Relation to check |
|---|---|
| Search and filtering | Adding a filter never adds results; a query for `A OR B` returns at least the results of `A`; reordering the indexed documents does not change the result set |
| Aggregation and reports | Shuffling input rows leaves totals unchanged; splitting the period in two and adding the parts equals the whole (for additive measures) |
| Pricing and finance | Doubling every quantity doubles the subtotal before rounding; adding a zero-value line changes nothing |
| Geometry and maps | Translating or rotating all points keeps pairwise distances; the shortest route from A to B is as long as the one from B to A on an undirected graph |
| Numeric code | `sin(pi - x)` is close to `sin(x)`; integrating over [a, b] equals [a, m] plus [m, b] |
| Parsers and compilers | Adding comments or insignificant whitespace leaves the syntax tree unchanged; renaming a local variable leaves the output unchanged |
| ML inference and ranking | Tiny input perturbations that should not matter (case, trailing space) leave the label or top result unchanged, within an agreed rate |

Generate the base inputs with a property-testing library and assert the relation as the property.

## Combinatorial and pairwise testing

When a feature has several independent parameters, the number of full combinations explodes (five parameters with four values each is 1,024 cases), but most defects that depend on configuration are triggered by the interaction of just two parameters. Pairwise (2-way) testing generates the smallest set of cases in which every pair of values from any two parameters appears together at least once, which usually cuts the case count by 80-90% while still catching the two-parameter interaction bugs. It complements the techniques above; it is a way to *choose* cases, not an oracle, so each generated case still needs an expected result.

### Build the model

1. **Name the parameters** that genuinely vary and affect behavior: inputs, flags, roles, environments, platforms. Leave out anything fixed.
2. **Choose values by equivalence partitioning**, not every literal. `FileSize: empty, small, at-limit, over-limit` beats ten sizes. Add the boundary values that matter as their own values.
3. **Add constraints** to exclude combinations that cannot occur or make no sense (`IF browser = Safari THEN os = macOS`). Under-constraining generates impossible cases; over-constraining drops real ones, so review what the generator produces.
4. **Generate** with a pairwise tool (for example Microsoft's PICT, or the all-pairs support built into some property and parameterized-test frameworks) rather than hand-picking, which misses pairs and wastes cases.

### Use it well

- **Raise the strength only where it pays.** Move from 2-way to 3-way for a small set of parameters whose three-way interaction is known to be risky (an authorization decision that depends on role, resource state and flag together), not across the board; higher strength grows the case count fast.
- **Keep the known edge cases.** Seed the required cases (a specific invalid combination from a past bug) so the generator always includes them, the way `@example` pins a property-test case.
- **Give every generated case an expected result.** Determine it from the requirements or a reference implementation; a combinatorial suite with vague "should work" assertions reduces cases without checking anything (the discriminating-check rule above).
- **Boundary values are separate.** Pairwise covers interactions between parameters, not the extremes within one; test zero, one, maximum and over-limit for each quantity in their own cases.
- **Re-generate when parameters or constraints change.** The set is derived from the model, so regenerate rather than editing cases by hand.

Pairwise reduces a configuration space to a runnable suite; property-based tests (above) cover the value space within one configuration. Large or safety-relevant features often want both: pairwise for which combinations to run, properties for what must hold in each.


## Known-answer vectors

- Use published vectors where they exist: RFC appendices (RFC 4231 for HMAC-SHA-256, RFC 6238 Appendix B for TOTP, RFC 8439 for ChaCha20-Poly1305, RFC 4648 section 10 for Base64), NIST CAVP files, Project Wycheproof for crypto edge cases and known attacks, the Unicode Character Database test files (`NormalizationTest.txt`, `GraphemeBreakTest.txt`), the URL test data in the web-platform-tests project, JSON parsing conformance suites.
- Vendor a pinned copy with its source and version noted next to it. Tests never download vectors at run time.
- Map every vector's expected outcome (valid, invalid, acceptable either way) to an assertion, and assert the number of vectors run, so a loader bug cannot turn the suite into zero checks.
- Vectors show that you call a vetted library correctly. They do not make home-made cryptography safe, and timing side channels need specialized tools: hand those to `../../code-security-review/GUIDE.md`.

## Where each runs

| Technique | Every pull request | Scheduled or on demand |
|---|---|---|
| Property and model-based tests | In the normal suite, moderate case count | Large case count nightly |
| Mutation testing | Changed files in critical modules, if the user wants it in CI | Full module runs before a risky refactor or a release |
| Differential tests | During the refactor or upgrade, in the suite | Wider recorded corpus |
| Known-answer vectors | Always | — |
| Fuzzing | Short runs (see `fuzzing.md`) | Long runs |

## What to report

- Technique, scope (files or modules), exact command and budget (cases, time, jobs).
- Results with counts: properties run and cases each; mutants killed, survived, no coverage and timed out; differences found and how each was classified.
- Each failure with its shrunk input and classification (bug, generator outside the domain, open specification question), and the test that now guards it.
- Surviving mutants left open, equivalent ones accepted (with reasons), and anything `NOT VERIFIED`.

## Checks (done when)

- [ ] Each property can fail for a plausible bug; none restates the implementation; generators build valid inputs instead of rejecting most of them.
- [ ] Known edge cases are pinned as explicit examples; every real failure became a permanent example or regression test.
- [ ] Mutation runs were scoped, and every survivor in critical code is killed by a new test, proven equivalent with a reason, or reported as open.
- [ ] Differential and metamorphic checks finished with zero unexplained differences, or the open ones are listed.
- [ ] New test dependencies were agreed with the user; CI budgets keep the pull-request run fast.

## Anti-patterns

- A property that recomputes the function under test, or a `@given` test whose `assume` calls let almost nothing through.
- Lowering `max_examples` or deleting a property because it "flakes", without finding the nondeterminism.
- Chasing a 100% mutation score, or killing a mutant with an assertion on an internal detail instead of on behavior.
- Calling a mutant equivalent because no current test reaches it.
- Comparing two implementations that share the same bug-prone helper, and calling agreement proof.
- Fetching test vectors from the network during the test run.
