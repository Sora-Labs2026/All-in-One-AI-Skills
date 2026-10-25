# Refactoring large codebases safely

Read this when a change restructures code across many files or modules: wide renames, extracting or merging modules, replacing a framework or library, introducing module boundaries, or reworking legacy code that has few tests.

A refactor changes structure and keeps behavior. Every step leaves the main branch building, passing its tests and deployable. The workflow module covers characterization tests and keeping diffs small for ordinary changes (`../../engineering-workflow/GUIDE.md`); this file covers what is different at scale.

## Decide whether and where it pays

- Refactor code you are about to change, or code that keeps causing bugs and slow changes. Restructuring stable code nobody touches buys little.
- Find hotspots where churn and size meet:

```bash
# files changed most often in the last year
git log --since="12 months ago" --format= --name-only | grep -v '^$' | sort | uniq -c | sort -rn | head -20
# then compare with size (lines) of those files
git ls-files -z | xargs -0 wc -l 2>/dev/null | sort -rn | head -20
```

- Signals that a module is the wrong shape: one concept spread across many tiny files callers must all know about; wrappers whose interface is as large as what they wrap; the same change repeatedly touching many unrelated files; tests that must mock internals to test anything; circular imports.
- Read the ADRs and history (`git log --follow -p <file>`, the pull requests that introduced odd code) before removing something whose purpose is unclear. Code that looks pointless often guards a case someone hit in production.
- Agree on the target shape and the step plan with the user before starting a multi-day refactor.

## Build the safety net first

- **Pin current behavior** of the paths you will move: characterization tests through the public entry points, including odd behavior you intend to keep for now.
- **Broad output checks** catch what unit tests miss: snapshot or approval tests of rendered output, generated files, API responses on a fixed dataset, or a diff of before and after outputs over many recorded inputs. Differential and property-based ways to do this are in `advanced-testing.md`.
- **Let the compiler help.** In typed languages, a deliberate signature change produces an exhaustive list of call sites; keep the type checker green at every step.
- **Test through stable interfaces** so tests survive the restructuring. Prefer real in-process code and local stand-ins (an in-memory implementation, a containerized database) over mocks; mock only what you do not control or what is slow or non-deterministic (third-party APIs, time, randomness). Once equivalent tests exist at the new interface, delete tests that only exercised internals that no longer exist.
- Record the baseline: full test, lint, type-check and build results before the first change, so you can tell new failures from old ones.

## Patterns for moving safely

- **Parallel change (expand, migrate, contract) in code.** Add the new function, module or API beside the old one; move callers in batches; delete the old one when nothing uses it. The old and new paths coexist only temporarily.
- **Branch by abstraction.** Put an interface in front of the component to replace, route all callers through it, build the new implementation behind the same interface, switch over (optionally per flag or per tenant), then remove the old implementation and, if it no longer earns its keep, the interface.
- **Incremental replacement of a system.** Route one slice of traffic, one endpoint or one feature at a time from the old system to the new one, verify, continue, and retire the old system piece by piece instead of a big-bang rewrite.
- **Adapters and shims** keep old call signatures working while callers migrate. Mark them deprecated and track their removal.
- **Block new uses of the old path** while migrating: a lint rule (`no-restricted-imports` in ESLint, `@deprecated` tags with a lint rule that reports them, import rules in Python with `import-linter`), with an allowlist of legacy files that only shrinks.

## Mechanical changes at scale

- **Use syntax-aware tools, not regex replace,** for renames and API migrations: IDE or language-server rename, `ts-morph` or `jscodeshift` codemods, `ast-grep`, `comby`, OpenRewrite (Java), LibCST codemods (Python), `gopls rename` and `gofmt -r` (Go), rust-analyzer (Rust).
- After the tool runs, search for what it cannot see: string-based lookups, reflection, dependency-injection names, templates, configuration files, SQL, serialized data, docs and other repositories (`git grep -n "<old name>"`).
- **Split the work into reviewable units:**
  1. Preparatory refactors that make the change easy, each green on its own.
  2. A purely mechanical commit or pull request produced by a script; include the script or command so a reviewer can rerun it and only spot-check the output.
  3. Manual fix-ups the tool could not do, in a separate commit.
  4. Behavior changes, if any, last and separately, each with its own test.
- Land wide renames and moves quickly and early, coordinated with the team, so that open branches rebase once instead of conflicting for weeks.
- Never hand-edit generated code; change the generator or its input and regenerate.

## Module boundaries

- Decide each module's public entry points and keep everything else internal (a package `index` or explicit exports in TypeScript, `__all__` and underscore-prefixed modules in Python, `internal/` packages in Go, `pub(crate)` in Rust).
- Enforce the boundaries with a tool so they do not erode: dependency-cruiser or ESLint import rules (`import/no-restricted-paths`, `no-restricted-imports`) for JavaScript and TypeScript, TypeScript project references, workspace boundary rules in Nx, `import-linter` for Python, ArchUnit for Java.
- Detect cycles (`npx madge --circular src/`, `import-linter` contracts) and break them by moving the shared part down a layer, not by adding lazy imports.
- **Prove each rule works:** run the check clean, add a deliberate violation locally and watch it fail, then remove the violation. A rule that never fails protects nothing.
- Avoid barrel files that re-export entire directories: they hide the real dependency graph, create cycles and slow down tooling. Prefer a few small, explicit entry points.

## Simplifying while you are there

- Aim to reduce the number of concepts a reader must hold, not the number of lines.
- Delete dead code once you have confirmed it is unused (search, coverage, runtime metrics or logs for endpoints and jobs); keep the deletion in its own commit.
- Replace clever compressed code with plain, named steps when that reads faster; keep helpers that give a concept a useful name.
- Name things in the domain's vocabulary and match the surrounding code's conventions.
- Bugs found during a refactor are recorded and fixed separately, with a test, so the refactor stays behavior-preserving and the fix stays reviewable.

## Track progress

- Count the remaining uses of the old path (`git grep -c "<old api>" | awk -F: '{s+=$2} END {print s}'`) and report the number in each pull request or in the tracking issue.
- Keep the migration plan and its status where the team will see it (the issue, the PR description, or the handoff file in `session-handoff.md`).
- Stop and ask when the refactor uncovers a question about intended behavior, or when the plan turns out to be much larger than agreed.

## Checks (done when)

- [ ] A safety net of tests at stable interfaces existed before the first structural change, and the baseline results were recorded.
- [ ] Each commit or pull request builds and passes on its own; mechanical changes are separate from manual edits and from behavior changes.
- [ ] Wide renames used a syntax-aware tool, followed by a search for dynamic and non-code uses.
- [ ] New boundaries are enforced by a check that was shown to fail on a violation.
- [ ] The old path is deleted (or its removal is tracked with a count and an owner).

## Anti-patterns

- A big-bang rewrite with no path to ship partial progress.
- "While I'm here" restructuring inside a feature or bug-fix pull request.
- Regex search-and-replace across code, strings and configuration at once.
- Refactoring code with no tests on the paths being moved.
- Mixing a bug fix into a mechanical change so neither can be reviewed or reverted cleanly.
- Introducing an interface with exactly one implementation and no test double, "for flexibility".
- Long-lived refactor branches that drift from main for weeks.
