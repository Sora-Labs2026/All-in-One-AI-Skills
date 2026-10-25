# Supply-chain review: dependencies, publishers, build inputs and releases

Deeper than [secrets and dependencies](secrets-and-dependencies.md), which already covers advisories and their reachability, checks for new packages, dependency confusion basics and container inputs. Use this file when dependencies are the subject of the review (a dependency audit, a suspicious update, a reported compromise), when the project publishes packages or self-updating software, or when install-time code needs to be understood before anything is installed. CI workflows have their own file: [CI and agent workflows](ci-agent-workflows.md).

## 1. Know what runs before the application does

Installing, building and even opening a project runs other people's code. Read this table before running any install command during an audit.

| Moment | What runs | How to see it | How to limit it |
|---|---|---|---|
| `npm install` / `npm ci`, Yarn, pnpm | `preinstall`, `install`, `postinstall` and `prepare` scripts of any package that has them; `binding.gyp` triggers native builds | `supply_chain.py lockfiles` (npm lockfiles record `hasInstallScript`); `npm view <pkg>@<v> scripts` | `npm ci --ignore-scripts`; pnpm 10 runs dependency build scripts only for packages you allow (`onlyBuiltDependencies`, `pnpm approve-builds`); Yarn 2+ `enableScripts: false` |
| `pip install`, `uv`, Poetry, from a source distribution | The package's build backend: `setup.py` or PEP 517 build hooks | `builds_from_source` in `supply_chain.py lockfiles` | Prefer wheels: `pip install --only-binary :all:`, `uv sync --no-build`; note that `pip download` of a source distribution also runs its build hooks to read metadata |
| Every Python start | `.pth` files in `site-packages` whose lines start with `import`, plus `sitecustomize.py` and `usercustomize.py` | List `.pth` files in the environment's `site-packages` and read any that import | Treat a new importing `.pth` file after an install as suspicious |
| `cargo build` | Every crate's `build.rs`, and procedural macros inside the compiler | `cargo metadata --format-version 1 --offline` lists targets of kind `custom-build` and `proc-macro` | Review those crates first; vendor and review (`cargo vendor`) for high-assurance builds |
| `go build` | Nothing at download time; cgo compiles C; `go generate` runs only when invoked | `//go:generate` lines; `replace` directives (`supply_chain.py lockfiles`) | Run `go generate` only after reading the commands |
| `bundle install` | Native extensions (`extconf.rb`) and gem plugins | `gem specification <gem> extensions` | Review gems with extensions |
| `composer install` | Root `scripts` and dependency plugins (`type: composer-plugin`) | `install_time_code` for `composer.lock` | Composer 2.2+ runs only plugins listed in `allow-plugins`; `--no-plugins --no-scripts` for a first look |
| Gradle or Maven builds | Build scripts, plugins, `buildSrc`, and the Gradle wrapper JAR | `gradle/wrapper/gradle-wrapper.properties`, `build.gradle(.kts)`, `pom.xml` plugins | `distributionSha256Sum` in the wrapper properties; dependency verification (`gradle --write-verification-metadata sha256`) |
| Opening the folder | Editor tasks set to run on folder open (`"runOn": "folderOpen"` in `.vscode/tasks.json`), dev container `initializeCommand` (runs on the host) and `postCreateCommand`, `direnv` `.envrc`, Git hooks installed by a `prepare` script | Read those files first | Open untrusted repositories in the editor's restricted mode; do not allow `direnv` or tasks until read |

An audit installs dependencies only with the user's approval, preferably with scripts disabled or inside a sandbox, and never with real credentials in the environment.

## 2. Read the lockfiles offline

```bash
python3 <productcraft>/modules/code-security-review/scripts/supply_chain.py lockfiles --root . \
  --registry npm.internal.example --json-out security/supply-chain-lockfiles.json
```

It reads npm, Yarn, pnpm, uv, Poetry, Pipenv, Cargo, Go module, Bundler and Composer lockfiles without contacting anything. Each rule is a lead:

| Rule | What it means | What to do |
|---|---|---|
| `INSTALL_TIME_CODE` | Packages that run code during install (where the format records it) | Read what each does; decide whether installs can run with scripts disabled |
| `BUILDS_FROM_SOURCE` | Only a source distribution is locked, so install runs a build | Prefer a wheel; review the build code of the rest |
| `NON_REGISTRY_SOURCE` | Resolved from Git or a direct URL; registry integrity checks and advisories do not cover it | Pin to a full commit SHA, record why it is not from the registry, check the repository owner |
| `OTHER_REGISTRY`, `MIXED_REGISTRIES` | Packages come from a host other than the public registry, or from several | Dependency confusion review below |
| `INSECURE_TRANSPORT` | A package or index over plain HTTP, or with TLS verification off | Finding: switch to HTTPS and re-lock |
| `CREDENTIAL_IN_URL` | A resolved URL embeds a token or password (never printed) | Finding: rotate, remove from the lockfile, configure registry auth outside the repository ([LaunchGuard secrets leak response](../../launchguard/references/safe-operations.md#secrets-leak-response)) |
| `MISSING_INTEGRITY` | No hash recorded, so a changed download would go unnoticed | Re-lock with a current package manager |
| `LOCAL_REPLACE`, `FORK_REPLACE`, `LOCAL_PATH_OUTSIDE_REPO` | Go `replace` directives or path dependencies point at local folders or forks | Confirm they are intended; local paths outside the repository are code this review cannot see |

**Dependency confusion.** When internal and public packages mix, every internal name must be impossible to fetch from the public registry: npm scopes mapped to the internal registry in `.npmrc` (`@corp:registry=...`) and the scope reserved publicly; for Python a single index (`--index-url`), or uv indexes marked `explicit = true` with per-package `[tool.uv.sources]`, or Poetry sources with `priority = "explicit"`; `pip --extra-index-url` alone consults both indexes and is the classic trap; Bundler `source "https://gems.internal" do ... end` blocks; Maven and Gradle repository order and content filters.

**Lockfile changes in a pull request.** A lockfile that changed without a manifest change, a resolved host that changed, or a new install script deserves a look even when the version numbers look routine: `git diff <base>...HEAD -- '*lock*' | grep -E '"resolved"|hasInstallScript|integrity'`.

## 3. A risk card for each dependency that matters

Do this for new direct dependencies in a change, dependencies that handle untrusted input, authentication, cryptography or money, and packages with install-time code. Most rows need the network: ask first, and mark the row `NOT_VERIFIED` without it.

| Signal | Read-only check | Record |
|---|---|---|
| Resolved version | The lockfile (offline) | Exact version |
| Known advisories at that version | The ecosystem audit tool or `osv-scanner` (secrets and dependencies) | IDs, then the reachability triage |
| Maintained | Last release, archived repository, deprecation (`npm view <pkg> deprecated time.modified`), unanswered security issues | State with dates |
| Who can publish | `npm view <pkg> maintainers`; `cargo owner --list <crate>`; the registry page for other ecosystems. Repository contributors are not publishers | Number of publishers; recent changes in who publishes |
| Install-time code | Lockfile (offline); `npm view <pkg>@<v> scripts` | What runs and what it does |
| Provenance | `npm audit signatures` after an install; attestations on the registry page or in `npm view <pkg>@<v> dist --json`; `gh attestation verify` for release artifacts | Present, absent or failed (absence is common and informational) |
| Source matches the release | The repository link resolves and a tag exists for the version; for small, critical packages compare the published files with the tag | Matches, differs (explain), or not checked |
| Change between versions | `npm diff --diff=<pkg>@<old> --diff=<pkg>@<new>`; for Python, download both wheels (`pip download --only-binary :all: --no-deps <pkg>==<v> -d <scratch>`) and diff them | New network, filesystem, process or install-time code is a red flag |
| Name | Distance to popular names, wrong ecosystem, unexpected scope (`AIG-10`) | Fine or suspicious |
| Repository practices | Individual OpenSSF Scorecard checks (dangerous workflows, branch protection, code review, token permissions) rather than the aggregate score | Per check |
| Popularity | Downloads and dependents (for example on deps.dev) | Context for prioritizing, never a verdict |

**Three states, always.** Every row is either *checked and fine* (with the value you saw), *checked and flagged* (with the value), or *could not check* (with the reason). "Could not check" is not risk and not safety. Never estimate maintainer counts, download numbers or release dates from memory or from a repository's contributor list; quote what a command returned, with the date.

**Single-publisher packages** are a concentration risk, not a vulnerability: one stolen account can ship a malicious version. Pinning, provenance checks and review of updates are the mitigation; replacing a healthy single-maintainer package is rarely worth it.

To read a package's code without installing it: `npm pack <pkg>@<v> --ignore-scripts` in a scratch directory, a wheel from `pip download --only-binary :all:`, the source distribution URL from `https://pypi.org/pypi/<pkg>/<v>/json` fetched with `curl` and extracted (not built), or a crate's `.crate` archive (a gzipped tarball) fetched from the registry. Keep downloaded code in its own empty directory and never execute it.

## 4. Reviewing an update

For a bot or human pull request that bumps dependencies:

- Read the release notes for the versions skipped, and the diff (`npm diff`, the wheel diff above, or the repository compare view between tags).
- Check the lockfile diff for new transitive packages, new install scripts, changed resolved hosts and changed publishers.
- Major-version jumps and packages that changed ownership since the previous version get a human reviewer.
- For pinned GitHub Actions, confirm that the new SHA belongs to the action's own repository and matches the tag it claims (`git ls-remote https://github.com/<owner>/<action> refs/tags/<tag>`), because a SHA from a fork can be made to look like an upstream pin.

## 5. When a dependency is reported compromised

This is incident response more than code review; keep the steps to what the repository can answer, and hand the rest to the owner.

1. **Were the bad versions ever resolved here?** Search current lockfiles and their history: `git log --all --oneline -S '<pkg>/-/<pkg>-<version>.tgz'` (the npm tarball URL inside lockfiles) and `git log --all --oneline -S '<pkg>@<version>'`.
2. **Where did they run?** Developer machines, CI runs between the dates the version was locked and removed, container images built in that window. CI logs and image registries are owner-observed (`NOT_VERIFIED` here).
3. **Treat every secret those environments could read as exposed:** CI secrets, registry publish tokens, cloud credentials, SSH keys and tokens on developer machines. Mark them `ROTATION REQUIRED` for the owner; rotation comes before cleanup.
4. **Remove it:** pin a known-good version, regenerate the lockfile, clear CI caches that may hold the tarball, rebuild images.
5. **Look for what such malware typically leaves behind**, as owner actions: unexpected workflow files or branches pushed to the organization's repositories, new tokens or deploy keys, changed `.npmrc` or registry settings, new `.pth` files.

## 6. If the project publishes software

| Practice | Check |
|---|---|
| Publish from CI with short-lived credentials | Trusted publishing (OIDC) on npm, PyPI, RubyGems or crates.io instead of a long-lived token in secrets; the publishing workflow runs only on protected tags or branches, behind an environment with required reviewers |
| Provenance for what is published | `npm publish --provenance`; build attestations (for example `actions/attest-build-provenance`); signatures for container images (`cosign sign`); PyPI attestations from trusted publishing |
| Consumers can verify | Document the command: `gh attestation verify <file> --repo <owner>/<repo>`, `cosign verify <image> --certificate-identity <workflow identity> --certificate-oidc-issuer https://token.actions.githubusercontent.com`, `npm audit signatures` |
| Release workflow isolation | No untrusted triggers, pinned actions, no caches shared with pull-request jobs, minimal token scopes ([CI and agent workflows](ci-agent-workflows.md)) |
| Self-updating applications | Update metadata signed with a key that is not on the update server; the client checks the signature and refuses older versions (rollback protection); frameworks such as The Update Framework, or the signature checks built into the platform's updater (for example Sparkle's EdDSA signatures). HTTPS alone is not enough |
| Plugins and extensions loaded at runtime | Where they come from, whether they are signed, and what they can access; for agent extensions see the [agent safety](../../agent-safety/GUIDE.md) module |
| Generated code | Generators and schemas pinned; generated files regenerated in CI and compared, so a hand edit or a tampered generator shows up |

## Done when

- Install-time code was understood before anything was installed, and any install during the audit ran with approval, scripts disabled or sandboxed, and no real credentials.
- Every lockfile has a `supply_chain.py lockfiles` result, and every candidate is confirmed, accepted with a reason, or dismissed.
- Each dependency that matters has a risk card in which every row is fine, flagged or could-not-check, with values quoted from commands and dated.
- For a reported compromise, exposure in history is answered from the repository, and owner actions (rotation, cache purge, organization-wide checks) are listed.
- Publishing projects have their release path checked against section 6, with gaps proposed as owner changes.
