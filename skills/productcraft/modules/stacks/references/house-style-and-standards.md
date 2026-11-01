# Following a codebase's house style and enforcing coding standards

Read this when you write code in an unfamiliar or legacy codebase and need its maintainers to accept it, when the user asks you to find and write down a project's unwritten conventions, when generated code keeps drifting from the project's style, or when a team wants standards enforced by tools instead of review comments. The short rules (read two or three neighbors, match local conventions, no drive-by edits, formatters only on changed files) are in the stacks `GUIDE.md` ground rules and `../../engineering-workflow/references/change-discipline.md`; this file is the method behind them.

## Read the conventions from the code

The configured tools are the written part of the style: read the formatter, linter and type-checker configs, `.editorconfig`, `CONTRIBUTING.md` and the CI workflow first. Everything else is unwritten and has to be observed.

Size the survey to the repository:

| Repository | How to sample |
|---|---|
| Small (a few dozen source files) | Read nearly everything; a "3 against 2" split is not a majority |
| Medium | Read all shared infrastructure (HTTP client, config, error handling, logging, base classes) and two or three examples of each kind of file you will touch |
| Large | Sample by directory and by recency; recently changed files show where the style is heading |

```bash
git ls-files | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -20            # where the code lives
git log --since="12 months ago" --name-only --format= | sort | uniq -c | sort -rn | head -20   # active files
rg -c "except Exception|catch \(e\)|rescue =>" --type-add 'src:*.{py,ts,rb}' -t src | sort -t: -k2 -rn | head   # count, do not guess
```

Look along these dimensions and note the evidence (paths and counts) for each finding:

| Dimension | What to observe |
|---|---|
| File anatomy | Order of imports, types, main logic, helpers and exports; one class or component per file; file naming |
| Naming | Types, functions, booleans, constants, test names; how loading, error and pagination state is named (`isLoading` or a `status` field) |
| Control flow and state | Early returns or nesting; exceptions or result values; how absence is modeled; async style |
| Errors and logging | Where errors are caught and translated, the error types and codes, which logger, message wording |
| Infrastructure placement | Where HTTP clients, configuration, middleware or interceptors, formatters and utilities live |
| Data access | Repositories or ORM calls in handlers; where transactions start |
| Tests | Location and naming, fixtures or factories, what is faked, assertion style |
| Comments and documentation | Docstring or JSDoc style, language of comments, what gets a comment |

## Decide between competing styles

- **A clear majority with a small minority:** follow the majority. Treat the minority as legacy; do not rewrite it as part of your change.
- **Newer code consistently differs from older code:** the team is migrating. Write new files in the newer style; when editing an old file, keep that file consistent with itself, because consistency within a file matters more to readers than global consistency. Ask when it is unclear which way the team is going.
- **A real split on something that matters** (error model, state management, layering, test style): ask the user, one question at a time, with the evidence, the options and your proposed default, for example: "`api/orders.py` and 11 other handlers raise `AppError`; `api/billing.py` and 2 others return `(result, error)` tuples. I will follow `AppError` in the new handler unless billing's style is the direction you want."
- **Never copy a defect because an exemplar has it:** a missing timeout, an injectable query, a swallowed exception. Follow the structure, and fix or report the defect separately.
- Style never outranks safety: security controls, data integrity, accessibility and the project's guardrails win over "the way it has always been done".

## Write the conventions down, with consent

Record conventions only when the user asks or agrees, in the place the team uses (`CONTRIBUTING.md`, a `docs/conventions.md`, and a pointer from the agent instruction file such as `AGENTS.md` or `CLAUDE.md` if the project keeps one). Keep it to a page or two; a long conventions file is not read.

```markdown
# Conventions (surveyed 2026-11-01 at commit 4f2c9e1)

## Exemplar files
- `src/api/orders.py`: handler shape, validation, error raising, response model
- `src/services/billing/refund.py`: service with injected clients and explicit transaction
- `tests/api/test_orders.py`: request tests with factories and the auth matrix

## Rules
- Handlers raise `AppError` subclasses; `src/api/errors.py` maps them to Problem Details.
- Outbound HTTP goes through `src/clients/http.py` (timeouts, retries, logging); no direct `httpx` calls.
- Money is integer minor units plus an ISO 4217 code.

## Don't
- `except Exception: pass` (exists in `legacy/importer.py`; do not copy).
- New code in `utils/`; put helpers next to their only caller.

## Exceptions
- `legacy/` keeps its own style until it is replaced.

## Change log
- 2026-11-01: initial survey.
```

Make every rule checkable ("handlers raise `AppError` subclasses"), not aspirational ("handle errors well"). Append changes with a date and reason instead of silently rewriting earlier entries, so the history of decisions stays visible.

## Enforce standards mechanically

A rule that only lives in review comments erodes. Move each rule as far down this list as it will go:

| Mechanism | Catches | Typical tools |
|---|---|---|
| Formatter in check mode | Whitespace, quotes, wrapping, import order | Prettier, Ruff format or Black, gofmt, rustfmt, Pint, RuboCop, dotnet format, clang-format |
| EditorConfig | Indentation, line endings, final newline in every editor | `.editorconfig` |
| Linter rules | Banned APIs and imports, unsafe patterns, naming | ESLint (`no-restricted-imports`, `no-restricted-syntax`), Ruff rule sets, golangci-lint, RuboCop cops, PHPStan rules, Checkstyle, detekt |
| Type-checker strictness | Unchecked escapes and missing types | TypeScript `strict`, mypy or pyright strict per module (`../../engineering-practices/references/typescript.md`) |
| Architecture tests | Layering, forbidden dependencies | import-linter, dependency-cruiser, ArchUnit, Pest `arch()` (`hexagonal-architecture.md`) |
| Pre-commit hooks | Fast checks before a commit | The project's hook manager, if it has one; CI stays the authority |
| Review checklist | Judgment calls no tool can make | Pull request template |

- **Legacy codebases: ratchet instead of a big bang.** Enforce a new rule on changed lines or files first, using the tool's baseline or new-code mode (a PHPStan baseline, RuboCop's generated to-do config, a detekt baseline, golangci-lint's new-from-revision option, ESLint bulk suppressions in recent versions), or keep a committed violation count and fail CI when it rises. Never mix a codebase-wide reformat into a feature change; if the team wants one, it is a separate, agreed, formatting-only commit, listed in `.git-blame-ignore-revs` so blame stays useful.
- Each rule has a reason, an owner and, where possible, an autofix. Local disables carry a comment with the reason, and a lint rule can require that comment.
- Prove a new rule works: it passes on the codebase (or its baseline), fails on a deliberate violation, then passes again.
- Adding a linter, formatter or hook is the user's decision (stacks `GUIDE.md`, ground rule 5); propose it with the rules you would turn on and the expected number of findings.

## Standards worth keeping in most codebases

Language-neutral defaults, overridden by whatever the project already does:

- Names use domain language and carry units (`timeoutMs`, `amountMinor`); booleans read as predicates (`isActive`, `hasAccess`).
- A function does one job at one level of abstraction; guard clauses instead of deep nesting; an options object or keyword arguments instead of boolean flags that switch behavior.
- Errors follow `../../engineering-practices/references/resilience.md`: handled where something can be done, never swallowed, cause kept, logged once.
- Constants instead of unexplained literals; immutable data where the language makes it cheap.
- Comments explain why; dead code is deleted, not commented out.
- Length and nesting are review prompts, not hard limits. If the team wants a tool limit, set it from the codebase's own distribution rather than a rule of thumb.
- Test code follows the same standards as production code.

## Reviewing generated code in an existing codebase

- Does the new code reuse the project's helpers, clients and base classes instead of adding parallel ones?
- Would a maintainer recognize the file as belonging here (layout, naming, error and logging style, tests)?
- Does it introduce a library, pattern or abstraction the codebase does not use? If so, was it agreed?
- Are formatter and linter clean on the changed files, with no new suppressions lacking a reason?

## Done when

- [ ] The conventions that affect the change were observed with evidence (paths and counts), not assumed.
- [ ] Real conflicts were put to the user one at a time with a proposed default; minor ones followed the majority.
- [ ] New code matches its neighbors and copies no defect from an exemplar.
- [ ] Any conventions file was written with the user's consent, with exemplars, checkable rules, don'ts, exceptions and a dated log.
- [ ] Every new enforced rule fails on a deliberate violation, legacy code is ratcheted rather than reformatted, and new tools were agreed first.
