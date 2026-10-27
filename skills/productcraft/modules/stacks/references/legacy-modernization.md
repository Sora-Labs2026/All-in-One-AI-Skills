# Legacy modernization

Read this when a system is old, undocumented, poorly tested or on an unsupported runtime and must change: assessing it, recovering what it actually does, building a safety net, replacing it piece by piece, moving its data, or upgrading its language, runtime or framework. The mechanics of restructuring code in small green steps (parallel change, branch by abstraction, adapters, syntax-aware rewrites, boundary enforcement) are in `../../engineering-practices/references/large-refactors.md`; this file covers what is specific to legacy systems and does not repeat them.

## Choose the strategy before the technology

| Option | Fits when | Main risk |
|---|---|---|
| Retain and contain | It works, rarely changes, and its runtime is still supported or can be isolated | Skills and dependencies keep ageing; set a review date |
| Upgrade in place | The architecture is acceptable; the runtime, framework or libraries are out of support | Underestimating behavior changes between versions |
| Refactor incrementally | The code is the problem (hard to change, fragile), the system boundary is fine | Never finishing; keep each step shippable |
| Replace piece by piece | Parts need a different technology or ownership; the system can be split at its edges | Running two systems and two data stores for a long time |
| Replace with a product | The capability is a commodity (billing, identity, CMS) | Migrating data and customizations; lock-in |
| Rewrite all at once | Almost never; only for small systems with a frozen scope | Losing undocumented behavior, a long period without delivery |

Write the choice, the alternatives and the reasons as an ADR draft for the user (`../../engineering-practices/references/docs-and-decisions.md`). The user decides; a modernization is costly to reverse.

## Assess the system

Work read-only first. Collect facts, not impressions:

- **Inventory:** languages and runtime versions with their end-of-support dates, frameworks, every dependency and whether it is maintained, build and deploy process, environments, scheduled jobs and batch chains, data stores, file drops and shared folders.
- **Integrations:** every inbound and outbound interface (HTTP, queues, files, database links, email, FTP), who owns the other side, and the data contract. Undocumented consumers are the biggest surprise in legacy work; search logs and network flows, and ask the user.
- **Usage:** which endpoints, screens, reports and jobs actually run, from access logs, job histories and database statistics. Features nobody uses are candidates to retire instead of migrate.
- **Change pressure:** churn hotspots from history (the commands in `../../engineering-practices/references/large-refactors.md`), open defects by area, the changes the business is waiting for.
- **Risk register:** single points of knowledge, missing source code or build steps, hard-coded credentials, licenses that end, hardware or OS dependencies, regulatory constraints.
- `../../codebase-map/GUIDE.md` and `../scripts/detect_stack.py` give a quick structural picture for supported languages.

## Recover the specification from the code

When nobody can say what the system does, write it down from evidence before changing anything.

1. **Pick a scope:** one capability (for example "invoice calculation"), not the whole system.
2. **Trace from entry points:** route, screen, job or message handler, through validation, business rules, persistence and outbound effects. Note configuration flags and data-driven behavior (lookup tables, rules stored in the database).
3. **State each behavior as a testable statement with evidence:**

```text
B-12  When an invoice is created for a customer with tax_exempt = 'Y', the system sets tax_amount to 0.
      Evidence: billing/InvoiceCalc.java:214-231; table CUSTOMER.TAX_EXEMPT
      Status: observed in code; confirmed by characterization test test_tax_exempt_zero_tax
```

   Trigger-and-response wording ("When ..., the system shall ...", "While ..., ...", "If <unwanted condition>, then ...") keeps statements precise and turns each one into a test case.
4. **Separate facts, inferences and questions.** Mark each statement as observed (code or a test shows it), inferred (likely but unproven) or open (needs a human). Never present an inference as a requirement.
5. **Record oddities without judging them:** rounding rules, special customer IDs, date cutoffs, error codes that clients branch on. Some are bugs, some are contracts. The user or the business decides which; until then, preserve them.
6. Keep the document next to the code, and update it as tests confirm or correct statements.

## Build the safety net

- **Characterization tests** pin current behavior, including odd behavior, at the most stable interface available: the HTTP API, the batch job's input and output files, the database state after an operation. Assert what the system does today, not what it should do.
- **Golden master (approval) testing** for large outputs: run many recorded or generated inputs through the system, store the outputs, and compare future runs against them. Scrub nondeterminism first: timestamps, generated IDs, ordering of unordered collections, floating-point formatting.
- **Seams** let you test code that was never designed for it: pass a dependency as a parameter instead of constructing it, wrap a static call in a small overridable method, substitute a library or module at link or import time, or extract the logic you need into a new, tested function and call it from the old code ("sprout"). Choose the least invasive seam; each one is a small behavior-preserving change.
- **Production as the oracle:** where tests cannot reach, record real inputs (with personal data removed or synthesized) and replay them against old and new code.
- Differential and property-based techniques for comparing two implementations are in `../../engineering-practices/references/advanced-testing.md`.

## Replace piece by piece

`../../engineering-practices/references/large-refactors.md` describes incremental replacement in general. For legacy systems specifically:

- **Put a routing layer in front first** (reverse proxy, API gateway, a facade in the old code, or a message router). With all traffic flowing through it and nothing else changed, it becomes the switch for every later step: by path, by operation, by tenant or customer, or by percentage.
- **Pick the first slice for learning, not glory:** a read-mostly, well-understood, low-risk capability with clear inputs and outputs.
- **Shadow before switching.** Send a copy of read traffic to the new implementation, compare responses asynchronously, log differences, and serve users from the old one. Never shadow writes unless the new side writes to an isolated store; duplicated side effects (emails, charges, external calls) are real.
- **Parallel run** for batch and calculation logic: run both implementations on the same input, compare outputs record by record, and investigate every difference until the remaining ones are explained and accepted.
- **Cut over gradually** with written criteria: difference rate, error rate and latency within agreed limits for an agreed period at each traffic step, and an instant route back to the old path.
- **Retire for real:** remove the old code path, its jobs, its data and its credentials once the new path has run at full traffic for an agreed period. Half-retired systems keep their costs and risks.

## Move the data

Data outlives code and is where modernizations fail.

- **One owner per data set at a time.** During transition, the new code may read the old database (a deliberate, temporary coupling) or the old code may call the new service, but never two writers with no agreed source of truth.
- **Synchronization options:** change data capture from the old database's log into the new store; a transactional outbox in the old code (`../../engineering-practices/references/resilience.md`); periodic batch sync for slow-changing data. Plain dual writes from application code drift on partial failures; if you must use them, add a reconciliation job.
- **Reconcile continuously:** counts, checksums or sampled comparisons of records between old and new stores, with a report the user can read.
- **Map identifiers** explicitly (old ID to new ID) and keep the mapping after cutover; external systems and old documents still reference old IDs.
- **Migrate history deliberately:** decide with the user what moves, what is archived read-only and what retention rules allow deleting. Mind encodings, time zones, implicit defaults and data that violates today's validation.
- Schema changes on live tables follow `../../engineering-practices/references/data-and-migrations.md`. Test the full migration on a production-sized copy (de-identified where personal data is involved) and time it.

## Upgrade runtimes and frameworks

- Upgrade one major version at a time, each step on a green suite and deployed, rather than jumping several majors. Read every intermediate release's upgrade notes.
- Fix deprecation warnings first: they are the next version's errors. Turn them into test failures in CI where the ecosystem allows it.
- Use automated rewriting tools, and review their output like any other diff:

| Ecosystem | Tools |
|---|---|
| Python | `pyupgrade` or Ruff's `UP` rules for syntax; `python -W error::DeprecationWarning` in tests; for the 2 to 3 era, run the suite under both until the switch |
| Java | OpenRewrite recipes (Java 8 to 17 or 21, Spring Boot 2 to 3 including `javax` to `jakarta`, JUnit 4 to 5) |
| .NET Framework to modern .NET | Microsoft's upgrade tooling and `try-convert` style project conversion, then API analyzers for unsupported APIs; check what Microsoft currently recommends |
| PHP | Rector rule sets per PHP and framework version |
| Ruby on Rails | `rails app:update`, stepwise `load_defaults`, dual-boot setups that run the suite on current and next versions |
| JavaScript and TypeScript | Codemods (jscodeshift, ts-morph) and framework-provided migration scripts |
| Go | `go fix`, `gopls` modernizers, and `go vet` after raising the `go` line |

- Run the old and new runtime side by side in CI (a matrix) until the switch, then remove the old one.
- Container base images, build agents and production hosts must all move; list them in the plan.

## Platforms that need specialists

Mainframe COBOL and JCL batch chains, RPG on IBM i, PowerBuilder or Visual Basic 6 clients, and business logic in thousands of stored procedures can be modernized with the same approach (characterize at the interfaces: input files, copybooks, database state, screens), but the tooling and the runtime knowledge are specialized. Say so, work at the interfaces you can observe, and do not guess at platform behavior.

## Done when

- [ ] The strategy, its alternatives and its risks are written as an ADR draft the user approved.
- [ ] The scope's behavior is written as evidence-backed statements, with inferences and open questions marked.
- [ ] Characterization or golden-master tests pass against the unchanged system before the first change.
- [ ] Each migration step has a routing switch back to the old path, comparison results, and agreed cutover criteria that were met.
- [ ] Data ownership is single at every step; reconciliation reports show no unexplained differences.
- [ ] The old path, jobs, data and credentials are retired, or their removal is tracked with an owner and a date.
