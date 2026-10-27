# Testing Move code and using the Move Prover

Read this when writing Move unit tests, measuring coverage, writing specifications for the Move Prover, running a local network for integration tests, or setting up CI for a Move package. What to test for from a security angle (invariants, attacker-controlled entry points) comes from `../../code-security-review/references/smart-contracts.md`; this file is how to do it on Aptos.

## Unit tests

Tests live next to the code (`#[test]` functions and `#[test_only]` helpers inside the module) or in separate test-only modules under `tests/`.

```move
#[test_only]
module my_app::counter_tests {
    use std::signer;
    use my_app::counter;

    #[test(user = @0xA11CE)]
    fun increment_adds_one(user: &signer) {
        counter::create(user);
        counter::increment(user);
        assert!(counter::value(signer::address_of(user)) == 1, 0);
    }

    #[test(user = @0xA11CE)]
    // error::not_found(E_NO_COUNTER) = 0x6 << 16 | 1
    #[expected_failure(abort_code = 0x60001, location = my_app::counter)]
    fun increment_without_counter_aborts(user: &signer) {
        counter::increment(user);
    }
}
```

- **Signers** come from the attribute: `#[test(admin = @my_app, user = @0xA11CE, framework = @aptos_framework)]`. Create accounts with `account::create_account_for_test(addr)` when the code needs them.
- **Expected failures** name both the code and where it is raised: `abort_code = ..., location = Self` (or another module). Without `location`, an abort with the same number from a different module passes the test by accident. Arithmetic overflow uses `#[expected_failure(arithmetic_error, location = Self)]`.
- **Framework state** needs test setup: start time with `timestamp::set_time_has_started_for_testing(&framework)` and move it with `timestamp::update_global_time_for_test_secs`; randomness has test-only initialization and seeding helpers; test-only functions in `event` list emitted module events so tests can assert on them. Names change between framework versions; check the module source you depend on.
- **Run:** `aptos move test` (add `--named-addresses my_app=0xCAFE` unless `[dev-addresses]` covers it), `--filter <name>` for one test, `--coverage` and then `aptos move coverage summary` or `aptos move coverage source --module counter`. Coverage counts executed code, not checked behavior.

### What to cover

- Each entry function's success path, with state and emitted events asserted.
- Each abort, with the exact code and location.
- Each privileged function called by the wrong signer, by a former owner after a transfer, and by an object owner who does not own *this* object.
- Boundaries: zero, one, the maximum `u64`, maximum supply, empty and full collections.
- Sequences: create, use, transfer, use by the new owner, rejection of the old owner; pause and unpause; an upgrade migration followed by normal use.
- Arithmetic with rounding, using non-round values.

Move's unit-test framework has no built-in fuzzer. For property-style coverage, loop over chosen ranges or derive inputs from a fixed seed inside a test, and keep every failing input as its own named test.

## Integration tests on a local network

- `aptos node run-localnet` starts a local chain with a faucet; add the indexer API option (it needs Docker) when the app queries the indexer. Older CLIs call it `run-local-testnet`.
- Publish the package to it with a local profile, then drive it from the TypeScript SDK in your test runner: build, simulate, submit, wait, and assert on resources, view functions and events (`aptos-sdk-and-wallets.md`).
- Simulation returns the abort code and gas used without committing; use it to check failure paths end to end.

## The Move Prover

The prover checks specifications for *all* inputs and states, using SMT solvers through Boogie. It proves exactly what you write and nothing else, so specifications deserve the same review as code.

**Setup and run.** Install the solvers with `aptos update prover-dependencies`, then run `aptos move prove` (with `--named-addresses` as for tests, and `--filter <module>` while iterating). Proving can take minutes; run the full set in CI or nightly.

**Specification essentials:**

```move
spec increment {
    let addr = signer::address_of(owner);
    aborts_if !exists<Counter>(addr);
    aborts_if global<Counter>(addr).value + 1 > MAX_U64;
    ensures global<Counter>(addr).value == old(global<Counter>(addr)).value + 1;
    modifies global<Counter>(addr);
}
```

| Construct | Meaning |
|---|---|
| `aborts_if cond` | The function aborts if and only if one of these conditions holds (with `pragma aborts_if_is_strict`, every abort must be listed) |
| `ensures cond` | Holds after a successful call; `old(expr)` is the value before, `result` the return value |
| `requires cond` | An assumption about the caller |
| `modifies global<T>(addr)` | The only storage the function may change |
| `invariant` in `spec Struct` | Holds for every value of the struct |
| `invariant` in `spec module` | Holds in every state between transactions (global invariant) |
| `spec schema` with `include` | Reusable groups of conditions |
| `pragma verify = false` | Skip a function: a blind spot to list in the report |

**Make specifications that can fail:**

- `requires` on a `public` or `entry` function is an assumption the prover makes but nothing enforces: any caller can violate it. State such conditions as `aborts_if` and enforce them with `assert!` in the code.
- Check each important spec by breaking the code on purpose (change `+ 1` to `+ 2`, drop an ownership check) and confirming the prover now fails. A spec that still passes is vacuous.
- Contradictory `requires` or invariants make everything provable. Keep assumptions few and review them.

**Where to spend effort:** value-moving functions (mint, burn, transfer, withdraw, deposit), access control on configuration and upgrades, and arithmetic with rounding. Start with per-function specs; add global invariants (such as supply conservation, often with helper spec functions) once those pass.

**Timeouts and scale:** raise `pragma timeout` sparingly; split large functions; mark well-specified helpers `pragma opaque` so callers use their spec instead of their body; loops need loop invariants. If a function cannot be verified in reasonable time, say so in the report rather than disabling it silently.

**Limits:** the prover does not check gas, assumes the framework's own specifications, and knows nothing about other modules beyond their specs. Proved code can still be wrong if the specification is wrong.

## CI

- Install a pinned CLI release (package manager with a version, or a release binary verified by checksum). Do not pipe a remote install script into an interpreter in CI.
- Steps: compile with warnings treated as failures, `aptos move test --coverage` with a coverage floor, formatter and linter checks where available, and `aptos move prove` (on every change if fast enough, otherwise nightly with results posted).
- CI never holds keys that control real funds. Publishing from CI is limited to test networks, or to a protected environment that requires a person's approval, with the deployer key in a secrets manager.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `expected_failure` without `location` | Always name the module that aborts |
| Only happy-path tests | Abort, wrong-signer and boundary tests for every entry function |
| Coverage percentage treated as proof | Assert outcomes; add specs for value-moving code |
| `requires` hiding the attack on a public function | `aborts_if` plus runtime `assert!` |
| Specs never seen to fail | Break the code on purpose and watch the prover catch it |
| `pragma verify = false` added to get green | List every skipped function in the report with the reason |

## Done when

- [ ] Every entry function has success, abort and wrong-signer tests; abort tests name code and location.
- [ ] Coverage is reported and untested lines are explained.
- [ ] Value-moving and access-control functions have specifications that verify, and each was shown to fail on a deliberately broken version.
- [ ] Skipped or timed-out specifications are listed in the report.
- [ ] CI pins the CLI, runs tests and the prover, and holds no keys for real funds.
