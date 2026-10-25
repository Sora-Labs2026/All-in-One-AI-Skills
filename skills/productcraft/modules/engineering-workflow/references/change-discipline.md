# Keeping changes small, complete and in the house style

Read this when deciding how much to build, before adding a dependency or abstraction, and before you call a diff ready for review.

## Find the smallest sufficient change

Work down this list and stop at the first option that fully solves the problem:

| Check | Example |
|---|---|
| 1. Is new code needed at all? The behavior may exist already, a setting may do it, or deleting code may be the real fix. | "Add a flag to disable caching": the client already honors `CACHE_TTL=0`. |
| 2. Does the project already have it? Helpers, components, services and patterns. Use them the way neighboring code does. | `git grep -nE "def slugify|function slugify"` before writing another one. |
| 3. Does the language's standard library or the platform do it? | `collections.Counter`, `itertools.groupby`, `zoneinfo`, `Intl.NumberFormat`, `URLSearchParams`, the HTML `<dialog>` element. |
| 4. Does a dependency that is already installed do it? | The date library already in the lockfile. |
| 5. Only then write new code: the least that fully works and reads clearly. | |

Measure "small" by what a reader has to understand, not by character count: three plain lines beat a clever one-liner. Among options of similar size, prefer the one that handles empty, missing and boundary inputs correctly.

**New dependencies must earn their place:** substantial functionality, actively maintained, a compatible license, acceptable size and transitive dependencies. Ask before adding one the user would notice, install it through the project's package manager so the lockfile records it, and apply the dependency control in `../../launchguard/references/security-baseline.md`.

## Signs of speculative design

Don't write these, and remove them from your own diff if they crept in:

- A parameter, option or flag with one caller that always passes the same value.
- An interface or abstract base class with one implementation; a factory that builds one type.
- A wrapper that only forwards calls.
- Configuration for values nobody changes; a plugin mechanism for one plugin.
- Generic names that hide a specific job (`Manager`, `Processor`, `utils2`).
- Branches for inputs that cannot occur, given the types and the validation upstream.
- Comments that say "in case we need".

Generalize when the second or third real use arrives; by then the code shows what shape the abstraction should have.

**Not speculative**, and never cut to shrink a diff: validation at trust boundaries, error handling that prevents data loss or corruption, security and accessibility requirements, limits real deployments hit (timeouts, size caps, pagination), and anything the user asked for.

## Make the change complete

Small does not mean partial. Before you finish:

- Search for every use of what you changed: `git grep -n "<old name or signature>"` across code, tests, fixtures, docs, configuration, scripts and string-based references (route names, reflection, templates, serialized keys).
- Update types, schemas, migrations, serializers, API descriptions, CLI help and the changelog if the project keeps one.
- Code you move or merge keeps its validation, error handling and logging.
- Remove imports, variables, functions, files and flags that *your* change made unused. Leave pre-existing dead code alone and mention it in the report.

## Keep the diff on-topic

- **Match local conventions** even where you would choose differently: naming, quoting, error style (exceptions or result values), logging, file layout, test style.
- **Format the way the project does.** If CI runs a formatter, run it on the files you changed (`npx prettier --write <files>`, `ruff format <files>`, `gofmt -w <files>`, `cargo fmt`). If the existing files are not formatted, don't reformat them wholesale; the real change disappears in the noise.
- **No drive-by edits:** no renames, reordering, comment rewrites or "while I'm here" refactors in code you are not otherwise changing. Report adjacent problems or propose them as a separate change.
- **Separate refactoring from behavior change:** two commits, or two pull requests for large refactors, so each can be reviewed and reverted alone.
- **Preserve file properties:** line endings, encoding and file modes stay as they were.

## Comments and known limits

- Comment why, not what. One line is usually enough.
- When you knowingly accept a limit, say so where the code is, with the limit and the condition that should trigger a revisit: `# Linear scan is fine below ~10k rows; switch to the indexed lookup if imports grow past that.` Use the project's TODO convention if it has one, and list accepted limits in your report so they don't silently become permanent. To review the markers you added: `git diff <base>...HEAD | grep -nE "^\+.*\b(TODO|FIXME)\b"`.

## Commits

- One logical change per commit, with a message that says what and why, in the repository's convention (for example Conventional Commits if the history uses it).
- Don't commit build output, local configuration, editor files or secrets unless the project tracks them on purpose.
- Commit when the user or the project's workflow expects you to. Never amend or rebase commits that are already pushed or shared without permission.

## Self-check commands

| Command | Shows |
|---|---|
| `git status --short` | Stray files, and untracked files you meant to include |
| `git diff --stat <base>` | Which files changed and by how much |
| `git diff --check` | Trailing whitespace and leftover conflict markers |
| `git diff -w <base>` | Hunks that disappear here are whitespace-only churn |
| `git diff --word-diff` | Exact token changes in prose and configuration |
| `python3 <productcraft>/modules/engineering-workflow/scripts/diff_scope.py --git <base>...HEAD --scope <paths>` | The advisory findings below |

`diff_scope.py` findings and what to do about them:

| Code | Severity | What to do |
|---|---|---|
| `OUT_OF_SCOPE` | WARN | Revert the file, or say in the report why the change needs it |
| `WHITESPACE_ONLY` | WARN | Revert the hunk unless reformatting was the task; in indentation-sensitive languages, confirm the block structure is intended |
| `DEBUG_LEFTOVER` | WARN | Remove the print, log call or breakpoint unless it is intended output |
| `FOCUSED_TEST`, `SKIPPED_TEST` | WARN | Remove the focus or skip, or get agreement and record why |
| `ASSERTIONS_REMOVED`, `TEST_FILE_DELETED` | WARN | Confirm tests were not weakened to make them pass |
| `CONFLICT_MARKER` | WARN | Resolve the merge properly |
| `LOCKFILE_WITHOUT_MANIFEST` | WARN | Usually churn from an install with a different tool version; revert unless intended |
| `GENERATED_FILE`, `MODE_CHANGE` | WARN | Keep only if the project commits these files or the permission change is intended |
| `LARGE_DIFF` | WARN | Consider splitting into steps a reviewer can check separately |
| `DEPENDENCY_CHANGE`, `NEW_TODO`, `CODE_WITHOUT_TEST_CHANGE`, `BINARY_FILE`, `UNTRACKED_FILES` | INFO | Confirm it was intended; name the covering test or say why none is needed; add or review untracked files |

The helper is a reading aid, not a gate: it can't judge correctness, and a clean run does not make a change ready.
