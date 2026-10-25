# Preparing a repository for public release

Read this when a private repository is about to become public, when code is being extracted from a private codebase into a new public one, when a project's first public package release is planned, or when the user asks which license to use. Making a repository public is a one-way step: assume anything published is copied within minutes and stays copied. Work through the sections in order, because the first one can change everything after it.

The owner makes the decisions here: what to publish, under which license, with or without history, and when to flip visibility. Prepare the evidence and the changes; never change repository visibility, publish packages or push tags yourself unless explicitly asked. Licensing information below is general, not legal advice; for anything unclear, recommend the organization's legal or open-source contact.

## 1. Agree on scope

Ask, and write down the answers:

- What exactly is published: the whole repository, a subdirectory, or a cleaned extract?
- Who owns the code: the user, an employer, a client, several contributors? Code written for a client or employer may not be the user's to release.
- Did the project ever handle secrets, customer data or client-confidential material (fixtures, recorded responses, dumps, screenshots)?
- Will it accept outside contributions, and who will answer issues and review pull requests?
- Which license, and is there an organizational policy that dictates it?

## 2. Secrets and confidential content, across the whole history

- **Scan every commit, not only the current tree.** Use `../../code-security-review/scripts/code_audit.py history` (offline, never prints values) or Gitleaks if installed; procedures are in `../../code-security-review/references/secrets-and-dependencies.md`. Then run this module's `scripts/oss_readiness.py`, which lists tracked files with secret-like names, sensitive names that only exist in history, internal hostnames, private registries and the commit email domains that will be exposed.
- **Look beyond credentials.** Internal hostnames and IP ranges, customer and employee names, internal ticket and chat links, personal data in fixtures and test recordings, production data samples, internal-only comments, vendored code under incompatible licenses, and generated files that embed paths or usernames.
- **Rotate first.** Any real credential found anywhere in history is treated as exposed: it is rotated or revoked by its owner, whatever happens to the history afterwards.
- **Decide how history ships.** Publishing the full history publishes everything ever committed, plus every commit author's email address. The options, for the owner to choose:
  - **Fresh start** (the most reliable when anything sensitive was ever committed): create a new repository from a clean copy of the current tree with a single initial commit, and keep the old one private and archived.
  - **Keep history** only when the history scan is clean, the email exposure is acceptable, and the owner agrees.
  - **Rewrite history** (for example with `git filter-repo`) is the least reliable: it misses forks, clones, caches, CI logs and artifacts, and it rewrites every commit hash. Use it only with explicit permission, never as a substitute for rotation.
- **Platform content becomes public too** when visibility flips: issues and pull request discussions, wiki pages, releases and their assets, Actions logs and artifacts, project boards. Review or delete them, or start in a new repository.
- **Commit identities:** if contributors want their emails private, the fresh-start route avoids exposing them, and forges offer no-reply addresses for future commits.

## 3. Rights and licenses

Choose the license with the owner. Common choices:

| Family | Examples | Effect, in short |
|---|---|---|
| Permissive | MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC | Anyone may use, modify and redistribute, including in closed products, keeping the notice. Apache-2.0 adds an explicit patent grant |
| Weak copyleft | MPL-2.0, LGPL-3.0 | Changes to the licensed files stay open; larger works may use other licenses |
| Strong copyleft | GPL-3.0, AGPL-3.0 | Distributed derivatives must be released under the same license; AGPL also covers software offered as a network service |
| Documentation and media | CC BY 4.0, CC BY-SA 4.0, CC0 | For non-code content; Creative Commons does not recommend its licenses for software |

"Source-available" licenses (for example the Business Source License or SSPL) do not meet the Open Source Definition; use them only if the owner chooses that deliberately. No license file means nobody may legally reuse the code, even if it is public.

- **Apply it consistently:** the full license text in `LICENSE` at the root (or `LICENSE-MIT` and `LICENSE-APACHE` for a dual license), the SPDX identifier in every package manifest (`"license": "MIT"` in `package.json`, `license = "Apache-2.0"` in `pyproject.toml` and `Cargo.toml`, `spec.license` in a gemspec), and a short license section in the README. `oss_readiness.py` reports mismatches between these. Optional: an `SPDX-License-Identifier:` header per file, checked with the REUSE tool (`reuse lint`). Apache-2.0 projects keep a `NOTICE` file when they have attribution notices.
- **Check what you redistribute:** licenses of vendored code, copied snippets, fonts, images and datasets (see `../../legal-ready/references/business-children-email-assets-rights.md` for assets), and dependency licenses with the ecosystem's tool (for example `npx license-checker --summary`, `pip-licenses`, `cargo deny check licenses`, `go-licenses report ./...`). A strong-copyleft dependency can constrain the project's own license choice.
- **Existing code and notices:** keep the copyright and license notices of code you did not write. Relicensing code others contributed needs their agreement, or a license that allows it.
- **Contributions:** decide whether contributors sign off commits under the Developer Certificate of Origin (`git commit -s`) or sign a contributor license agreement, and say so in `CONTRIBUTING.md`.
- **Names and trademarks:** check that the project name does not collide with an existing product or package name in the target registries.

## 4. The front door

| File | Minimum content |
|---|---|
| `README.md` | What it is and for whom; status (experimental, maintained, archived); install; one copy-paste usage example; how to run the tests; license |
| `LICENSE` | Full license text with the copyright line |
| `SECURITY.md` | How to report a vulnerability privately (an address or the forge's private reporting feature), what to expect, supported versions |
| `CONTRIBUTING.md` | Development setup, test and lint commands, how pull requests are reviewed, sign-off or CLA rules |
| `CODE_OF_CONDUCT.md` | If outside contributors are expected (the Contributor Covenant is widely used); name a contact who will act on reports |
| `CHANGELOG.md` | Newest release first, as in `docs-and-decisions.md` |
| Issue and pull request templates | See `repository-hygiene.md` |

## 5. Builds from a clean clone

The test that matters: an outsider clones into an empty directory or container with no access to the organization's network, follows the README word for word, and gets a passing build and test run.

- No private registries, internal mirrors or credentials needed to install (`oss_readiness.py` reports non-public registry hosts in lockfiles and package-manager configuration).
- No dependencies on paths outside the repository, absolute local paths, or private submodules.
- An example environment file with variable names and placeholder values only; the app starts or fails with a clear message without real secrets.
- Tests that need internal services are skipped with a clear reason, or use local stand-ins.

## 6. CI and repository settings before the switch

- Every pull request triggers the test suite in CI across the supported versions (see `ci-and-release.md`).
- Workflows are safe for pull requests from forks: no secrets exposed to untrusted code, least-privilege token permissions, actions pinned to a commit SHA. `../../code-security-review/scripts/code_audit.py workflows` checks the common mistakes.
- Branch protection or rulesets on the default branch: pull requests required, required status checks, no force-push.
- Secret scanning and push protection, private vulnerability reporting, and Dependabot or Renovate with grouped updates and a waiting period before adopting new releases.
- Labels, templates and `CODEOWNERS` as in `repository-hygiene.md`, and an `.editorconfig` that fixes indentation, final newlines and line endings for every editor.

These are settings in the hosting platform; prepare the list and let the owner apply them, or apply them only with explicit permission.

## 7. Releases

- Version with Semantic Versioning and annotated tags (`git-and-pull-requests.md`); a Go module version is published by pushing its tag, and tags fetched through the module proxy can never change, so never move a published tag.
- Publish from CI on a tag, not from a laptop. Prefer trusted publishing (OIDC from CI, no long-lived tokens) where the registry supports it, as PyPI, npm, crates.io and RubyGems do, and publish provenance or build attestations where available.
- Publish under an organization-owned registry account with two-factor authentication and at least two owners.

## 8. Final outsider check

1. Fresh clone in a clean container; follow the README verbatim; record what broke.
2. Rerun `oss_readiness.py --strict`; every remaining WARN is fixed or accepted by the owner in writing.
3. Confirm the history decision and the secrets scan happened, and that every real credential found was rotated.
4. Hand the owner the list of platform settings and the visibility switch. Do not flip it yourself.

## The readiness helper

```bash
python3 <productcraft>/modules/engineering-practices/scripts/oss_readiness.py --root .
python3 <productcraft>/modules/engineering-practices/scripts/oss_readiness.py --root . --json --strict
```

It is read-only and offline, and prints paths, license identifiers, hostnames, counts and email domains, never file contents. In a git checkout it inspects tracked files (what would be published) and the names in history. WARN findings: missing README, LICENSE or SECURITY.md; license text that disagrees with a manifest; a manifest that says `UNLICENSED`; a non-open-source license text; secret-like tracked files, private keys and `.npmrc` tokens; sensitive file names in history; dependencies outside the repository. INFO findings cover the rest of the front door, data dumps, large files, internal hosts, non-public registries, submodules, version tags and commit email domains. It does not scan secret values, dependency licenses, workflow security or platform content; the report lists these as not checked.

## Checks (done when)

- [ ] Ownership, scope, license and history route were decided by the owner and written down.
- [ ] Full-history secret scan ran; every real credential was rotated; the history route matches what was found.
- [ ] LICENSE text, manifest identifiers and README agree; dependency and asset licenses were checked.
- [ ] README, SECURITY.md and CONTRIBUTING.md exist and their commands were run from a clean clone.
- [ ] `oss_readiness.py --strict` passes or every remaining WARN is accepted by the owner.
- [ ] Platform settings and the visibility switch were handed to the owner, not changed silently.

## Anti-patterns

- Flipping visibility on a repository whose history was never scanned.
- Deleting a leaked key in a new commit and calling it fixed.
- A LICENSE file that says one thing and the package metadata another; `"license": "UNLICENSED"` meant as "Unlicense".
- A README whose setup only works on the company network.
- Publishing packages from a personal account with a long-lived token.
