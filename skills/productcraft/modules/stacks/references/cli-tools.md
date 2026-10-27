# Command-line tools

Read this when you design, add to or change a command-line tool in any language: commands and flags, output, exit codes, configuration, prompts, signals, tests and distribution. The language references cover the code itself; this file covers the interface, which scripts and people depend on as much as on any API.

## A CLI is a contract

Scripts, CI jobs and other tools parse your output and branch on your exit codes. Treat flags, subcommands, output formats and exit codes like a public API (`../../engineering-practices/references/api-contracts.md`): add freely, deprecate before removing, never change the meaning of an existing flag in place.

## Commands, arguments and flags

- **Shape:** a single command for a single job; subcommands (`tool <noun> <verb>` or `tool <verb> <noun>`, consistently) when there are several jobs. Follow the shape already in the tool.
- **Positional arguments** for the main required inputs (`tool convert input.csv`); **flags** for everything optional. More than two positional arguments of different kinds is hard to remember; make the rest flags.
- **Long flags always, short aliases only for frequent ones** (`-o/--output`, `-v/--verbose`). Use kebab-case (`--dry-run`), never two spellings of the same idea across subcommands.
- Support `--` to end option parsing and `-` to mean stdin or stdout where a file is expected.
- Standard flags users expect:

| Flag | Meaning |
|---|---|
| `-h`, `--help` | Usage, short description, options and examples; exit 0 |
| `--version` | Version string; exit 0 |
| `-v`/`--verbose`, `-q`/`--quiet` | More or less diagnostic output on stderr |
| `--json` or `--output json` | Stable machine-readable output |
| `--dry-run` | Show what would change without changing it |
| `-y`/`--yes` or `--force` | Skip confirmations; required for destructive actions in non-interactive use |
| `--no-color` | Plain output |
| `--config <path>` | Explicit configuration file |

## Output and streams

- **stdout carries the result** (what a pipe consumes); **stderr carries everything else:** logs, progress, warnings, prompts and errors. `tool list | wc -l` must count results, not log lines.
- Human output may change between versions; machine output (`--json`, `--format csv`) is versioned and stable. In JSON mode print one document (or one object per line for streams) and nothing else on stdout.
- Detect terminals: colors, spinners, progress bars and tables only when the stream is a TTY. Honor `NO_COLOR` (any value disables color) and `TERM=dumb`; offer `--color=always` for forced color.
- Progress for operations longer than a second or two, on stderr, and nothing for fast ones.
- Errors say what failed, why, and what to do next, in one or two lines: `error: config file not found: ~/.config/tool/config.toml (run 'tool init' to create one)`. Stack traces only with `--debug` or a verbose level. Suggest the closest command for typos.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General failure (the operation ran and failed) |
| 2 | Usage error: unknown flag, missing argument, invalid value (the convention of getopt and argparse) |
| Documented others | Specific outcomes scripts need, for example "differences found" for a diff or check tool |
| 130 | Interrupted by Ctrl-C (128 + SIGINT) |

A check-style command (lint, verify, diff) exits non-zero when it finds problems, so CI fails without parsing output.

## Configuration

- Precedence, highest first: command-line flags, environment variables (`TOOL_*`), project config file, user config file, system config, built-in defaults. Document it and provide a way to show the effective configuration (`tool config show`).
- Put user files where the platform expects them: `$XDG_CONFIG_HOME` (default `~/.config/<tool>`) and `$XDG_CACHE_HOME` on Linux, the platform's application-support directories on macOS and Windows (most CLI libraries or a small helper library resolve these).
- **Secrets never as flag values:** command lines are visible in `ps` and shell history. Read them from an environment variable, a file path, stdin, the OS keychain, or an interactive prompt without echo (`getpass` in Python, `term.ReadPassword` in Go). Never print them back.

## Interactivity and safety

- Prompt only when stdin is a TTY. Every prompt has a flag equivalent so scripts and CI never hang waiting for input; without a TTY and without the flag, fail with a usage error that names the flag.
- Destructive actions (delete, overwrite, deploy, rewrite many files) confirm interactively, accept `--yes` for automation, and support `--dry-run`.
- Write files atomically: write to a temporary file in the same directory, flush, then rename over the target. Never truncate a user's file before the new content is complete.
- Do not overwrite existing outputs without `--force`.
- No network calls the user did not ask for. An update check, if any, is opt-out, rate-limited and never blocks.

## Signals and lifecycle

- Ctrl-C (SIGINT): stop promptly, clean up temporary files and partial outputs, restore the terminal state (cursor, raw mode), exit 130. A second Ctrl-C may exit immediately.
- SIGTERM: same cleanup, for containers and process managers.
- Broken pipes: when the reader goes away (`tool list | head -1`), exit quietly. Python raises `BrokenPipeError` on the next stdout write or flush; Rust ignores SIGPIPE, so `println!` panics unless writes go through a handle whose errors you check; Go programs are ended by SIGPIPE when writing to a closed stdout or stderr, while writes to other descriptors return an error. Test it.

## Performance

- Start fast: a CLI that takes a second to print `--help` feels broken. Python: import heavy modules inside the commands that need them. Node: avoid loading large dependency trees at startup. JVM: consider native images only for a measured need.
- Stream large inputs line by line or in chunks instead of reading whole files; respect memory limits in CI.
- Parallelize independent work with a bounded worker count and a `--jobs` flag.

## Libraries by language

| Language | Usual choices |
|---|---|
| Python | `argparse` (standard library), Click, Typer (built on Click), Rich for terminal output |
| Go | `flag` (standard library), Cobra (subcommands, completions), urfave/cli, Kong |
| Rust | clap (derive API), with `anstream`/`anstyle` for color; `indicatif` for progress |
| Node.js | `util.parseArgs` (built in), commander, yargs |
| Java and Kotlin | picocli; Clikt for Kotlin |
| .NET | System.CommandLine (its API changed considerably across releases; check the installed version) |
| Swift | swift-argument-parser |
| Ruby and PHP | OptionParser or Thor; Symfony Console |

Use the library the project already has. Node.js specifics (ES modules, streams, child processes, shutdown) are in `javascript-runtime.md`. Generated shell completions (Cobra, clap, Click and Typer can produce them) are a cheap usability win.

## Testing

- Most tests call the command in-process through the library's runner, with captured stdout, stderr and exit code: Click's and Typer's `CliRunner`, Cobra's `SetArgs`/`SetOut`/`SetErr` with `Execute`, picocli's `CommandLine.execute`. In Rust, `assert_cmd` with `predicates` runs the built binary.
- A few end-to-end tests run the installed or built binary as a subprocess, including a non-TTY run, piping, and Ctrl-C handling where feasible.
- Golden files for `--help` output and for machine-readable output, so changes to the interface show up in review.
- Test every exit code the tool documents, every flag-versus-environment precedence rule, and error messages for the most common mistakes.
- Run on every platform the tool claims to support; Windows path separators, quoting and line endings break naive code.

## Distribution

| Language | Install path |
|---|---|
| Python | `[project.scripts]` entry point; users install with `pipx` or `uv tool install` |
| Go | Single static binary per platform (GoReleaser builds archives, checksums and package-manager manifests); `go install module@version` |
| Rust | `cargo install`; prebuilt binaries via cargo-dist or a release workflow |
| Node.js | `bin` field in `package.json`, a `#!/usr/bin/env node` shebang; `npx` for one-off runs |
| Others | Homebrew formula or tap, OS packages, container image for tools with heavy dependencies |

- Version with semantic versioning; the changelog lists flag and output changes first.
- Publish checksums (and signatures if the project signs) next to binaries.
- Publishing to any registry, tap or package index is the user's decision; prepare the release and ask.

## Done when

- [ ] `--help` and `--version` work; help includes at least one example; usage errors exit 2 with a message naming the problem.
- [ ] Results go to stdout, diagnostics to stderr; color and progress appear only on a TTY and respect `NO_COLOR`.
- [ ] Every prompt has a flag; destructive actions confirm or require `--yes`, and support `--dry-run` where they change data.
- [ ] Exit codes, machine-readable output and the configuration precedence are documented and tested; existing flags keep their meaning.
- [ ] Ctrl-C and broken pipes leave no partial files and no stack trace.
