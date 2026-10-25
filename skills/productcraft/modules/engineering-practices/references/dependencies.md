# Dependency hygiene

Read this when you add, upgrade, pin, audit or remove a package, change a lockfile, bump a runtime or base image, or write code against a third-party API.

Every dependency is code you ship but did not write or review: it brings bugs, vulnerabilities, license terms, install-time scripts and upgrade work. Security verdicts on dependencies belong to LaunchGuard control #20 and `../../code-security-review/GUIDE.md`; this file covers the day-to-day discipline.

## Before adding a package

1. **Check whether you need it.** Prefer, in order: the language's standard library or platform API (`fetch`, `URL`, `Intl`, `crypto.randomUUID()`, `structuredClone`, Python `pathlib`, `dataclasses`, `zoneinfo`), a utility the project already has, a dependency already installed, and only then a new package.
2. **Vet the candidate:**
   - Exact name and publisher. Typosquats differ by one character or a missing hyphen; check the registry page and the source repository link.
   - Maintenance: recent releases, responsiveness to issues and security reports, more than one maintainer for critical packages.
   - License compatible with the project (permissive licenses such as MIT, Apache-2.0 and BSD are simplest; copyleft licenses such as GPL or AGPL carry obligations the owner must accept). Ask when unsure; do not decide legal questions alone.
   - Size and transitive dependencies: for frontend code, measure the bundle impact after install with the project's bundle analyzer.
   - Install scripts (`preinstall`, `postinstall`, native builds), which run with your permissions during install.
   - Types available (bundled or `@types/...`) and the module format the project needs (ESM or CommonJS).
3. **Check the release age.** Be wary of versions published in the last few days; compromised releases are usually caught quickly. Some package managers can enforce a minimum release age (for example pnpm's `minimumReleaseAge`, uv's `exclude-newer`).
4. **Tell the user** when a new runtime dependency is user-visible or substantial, and say why it is worth it.

## Versions and lockfiles

- Applications commit the lockfile and install from it frozen in CI (commands in `ci-and-release.md`). Libraries also commit one for their own development, and declare dependency ranges as wide as they genuinely support, tested against the lowest and highest.
- One package manager per project. Record it (`packageManager` in `package.json`, a single lockfile type) and do not mix `npm`, `yarn` and `pnpm` lockfiles.
- Never hand-edit a lockfile. On a merge conflict, resolve the manifest (`package.json`, `pyproject.toml`), then regenerate the lockfile with the package manager and review the result.
- Review lockfile diffs in pull requests: unexpected new packages, changed sources or registries, and large transitive jumps from a small direct bump.
- Pin runtimes and toolchains (`.nvmrc` or `engines`, `.python-version`, `rust-toolchain.toml`, Go version in `go.mod`), and base images by digest with an update process.

## Write against the installed version

- Read the version from the lockfile before using a library's API. Use the documentation and changelog for that version; patterns from another major version can compile and still behave differently.
- If the documentation is not available in your environment, say which version you assumed and keep the usage to well-established APIs.

## Upgrading

- **Cadence over big bangs.** Small, regular updates (a dependency bot such as Dependabot or Renovate, grouped for low-risk patch updates of development tools) are cheaper than a yearly upgrade marathon.
- **Isolate risky upgrades:** one major version per pull request, and frameworks one major at a time following the official upgrade guide and codemods.
- **Read the changelog and migration notes,** not only the version number. A patch release can still change behavior you rely on.
- **Verify with tests before and after.** Run the suite on the current version first, so failures you see afterwards are attributable. If tests barely touch the dependency's behavior, add one for the part you rely on before upgrading.
- Fix new deprecation warnings during the upgrade, while the context is fresh.
- Prefer upgrading over overrides. An override or resolution to force a transitive version is a temporary measure: add a comment with the reason and an issue to remove it.
- Temporary patches to a dependency (`patch-package`, `pnpm patch`) carry a link to the upstream issue or fix and a note on when to remove them.

## Auditing

- Run the ecosystem's audit against the committed lockfile: `npm audit`, `pnpm audit`, `yarn npm audit`, `pip-audit`, `cargo audit`, `govulncheck ./...`, `bundle audit`, or `osv-scanner` across ecosystems.
- Triage by reachability and exposure: is the vulnerable code used at runtime, only at build time or only in tests, and is the vulnerable function called with attacker-controlled input?
- Never run forced automatic fixes (`npm audit fix --force`) unattended; they can install breaking majors. Upgrade deliberately and test.
- Record accepted risk (no fix available, not reachable) with the reason, an owner and a date to review it again.
- Audits only know published advisories. They do not detect a newly malicious package, so new dependencies and lockfile diffs still need a human look.
- Where required, generate a software bill of materials in a standard format (CycloneDX or SPDX) from the lockfile as part of the build.

## Removing

- Find unused dependencies with the ecosystem's tool (`knip` or `depcheck` for JavaScript and TypeScript, `deptry` for Python, `cargo machete` for Rust, `go mod tidy` for Go). Confirm each candidate by searching for dynamic imports, configuration files and scripts before removing it.
- Remove dependencies that duplicate each other (two date libraries, two HTTP clients) as part of planned work, not as a drive-by in an unrelated change.

## Checks (done when)

- [ ] Each new dependency has a stated reason, a vetted name and publisher, a compatible license and an acceptable size.
- [ ] The lockfile is committed, regenerated by the tool and its diff reviewed.
- [ ] Upgrades were tested before and after, with the changelog read; one major per change.
- [ ] Audit output was recorded, and every high or critical finding is fixed or has a documented decision.
- [ ] No overrides or patches without a comment and a removal plan.

## Anti-patterns

- Adding a package for something the platform already does.
- "Update all dependencies" in one pull request with no changelog review.
- Hand-merging lockfile conflicts.
- Mixed package managers in one project.
- `npm audit fix --force` in CI.
- Writing code from memory against an API that changed in the installed major version.
