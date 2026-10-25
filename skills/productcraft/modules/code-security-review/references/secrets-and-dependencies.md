# Secrets, dependencies, supply chain and CI

Phase 4 of the audit. LaunchGuard gate 1, baseline controls 1-3 and 20, and its `preflight_scan.py` already cover secrets in the working tree, client-exposed variables and running an audit tool. This file adds what a code audit needs on top: Git history, triage of every hit, reachability of dependency advisories, supply-chain risk and CI security.

## Secrets

### Where to look

| Place | How | Status if you cannot look |
|---|---|---|
| Tracked files at HEAD, client bundles, `NEXT_PUBLIC_`-style variables | LaunchGuard `preflight_scan.py` and gate 1 | per LaunchGuard |
| Every commit on local branches, tags and the stash | `code_audit.py history`, or Gitleaks if installed | `NOT_VERIFIED` |
| Files that were added and later deleted (`.env`, keys, dumps, state files) | `code_audit.py history` (sensitive file names) | `NOT_VERIFIED` |
| Branches and pull request refs that exist only on the remote | Fetching them contacts the remote: ask first | `NOT_VERIFIED` |
| Test fixtures, recorded HTTP cassettes, notebooks with saved output, SQL dumps, seed data | Read them; search for `Authorization`, `Bearer`, `password`, `token` | — |
| Terraform state, Docker build arguments and image layers, source maps, mobile builds | Inspect local artifacts if present | `NOT_VERIFIED` |
| CI logs, deployed web roots (an exposed `.git/` or `.env`), backups | Owner-observed only | `NOT_VERIFIED` |

### Commands

```bash
# Bundled, offline, never prints values
python3 <productcraft>/modules/code-security-review/scripts/code_audit.py history --root . \
  --json-out security/code-audit-history.json

# Gitleaks, if installed (8.19 and later; older releases use `gitleaks detect --redact --source .`)
gitleaks git --redact --report-path security/gitleaks-history.json .

# Plain Git: list files ever added with sensitive names, without printing contents
git log --all --diff-filter=A --name-only --format= | sort -u | \
  rg -i '(^|/)(\.env(\.|$)|id_(rsa|ed25519)|credentials|service.?account.*\.json$)|\.(pem|key|p12|pfx|tfstate)$'

# Plain Git: which commits touched a pattern, without printing the matching lines
git log --all -G'AKIA[0-9A-Z]{16}' --format='%h %ad %s' --date=short --name-only
```

- Keep scanner output out of the report and out of commits. Some scanners write raw values to their JSON; use their redaction option, keep the file local and delete it after triage.
- Some scanners can "verify" a hit by calling the provider's API with the found credential. That uses someone else's credential against a live service: do not enable it without the owner's explicit approval.
- `--all` covers local refs, including the stash. It does not cover unfetched remote branches, pull request refs on the host, forks, other clones, or objects reachable only from the reflog.

### Triage each hit

| Question | How to answer |
|---|---|
| Is it real or a placeholder? | Read the surrounding lines. `changeme`, `example`, `xxx`, `${VAR}`, all-same characters and documented sample keys are placeholders |
| What kind of credential is it? | Provider prefix and context. Publishable keys (a Stripe publishable key, a Supabase anon or publishable key, a Firebase web config) are public by design; check instead that what protects them holds (LaunchGuard baseline 3 and 4) |
| What can it do? | Live or test mode, scopes, which account or environment it belongs to (from code and config, not by calling the provider) |
| Where has it been exposed? | Tracked at HEAD, history only, shipped to the client, printed in logs, sent to a third party |
| Is it still in use? | Same value or same variable still read by the code or the deploy config |

A real credential in a test file is still exposed to everyone who can read the repository. The file's location lowers the chance it is used in production; it does not make the leak harmless.

Results map to the finding vocabulary:

- Placeholder, sample or intentionally public value: `FALSE_POSITIVE` with the reason (keep it so the next run does not re-raise it).
- Real secret, any location, any time in history: `CONFIRMED`, evidence `STATIC_CONFIRMED`, severity by what the credential can do (a live payment or cloud key with write access is CRITICAL; a test-mode key for a sandbox account is usually LOW).
- Cannot tell whether it is real or still valid: `LIKELY` with `unverified_condition: "owner to confirm whether key <type> at <location> is active"`.

### Response

Follow the [LaunchGuard secrets leak response](../../launchguard/references/safe-operations.md#secrets-leak-response). In short: never print the value, mark `ROTATION REQUIRED`, rotate or revoke first, then move the secret to server-side configuration, and only then discuss a history rewrite with the owner. A history rewrite changes every collaborator's clone and does not reach forks, caches or logs, so it never replaces rotation.

To stop recurrence, propose a pre-commit secret scan (for example the Gitleaks or detect-secrets hooks), the host's secret scanning and push protection where available, and `.env*` patterns in `.gitignore` with an untracked `.env.example` of names only.

## Dependencies

### Inventory

`code_audit.py map` lists every manifest, whether a lockfile sits next to it, and dependencies resolved from Git, URLs or local paths. Then check:

- The lockfile is committed and CI installs from it: `npm ci`, `pnpm install --frozen-lockfile`, `yarn install --immutable` (Yarn 2+), `pip install --require-hashes -r requirements.txt`, `uv sync --locked`, `poetry install`, `cargo build --locked`, `go mod verify`, `bundle config set frozen true`, `composer install`.
- Production and development dependencies are separated, and the production build installs only what it needs.

### Known vulnerabilities

| Ecosystem | Command (if installed) |
|---|---|
| npm, pnpm | `npm audit --omit=dev --json`, then a full `npm audit` for build tooling; `pnpm audit --prod` |
| Python | `pip-audit -r requirements.txt` or `pip-audit` inside the project environment |
| Go | `govulncheck ./...` (checks whether vulnerable functions are actually called) |
| Rust | `cargo audit` |
| Ruby | `bundle-audit check` |
| PHP | `composer audit` |
| .NET | `dotnet list package --vulnerable --include-transitive` |
| Any lockfile | `osv-scanner scan source -r .` (osv-scanner 2; version 1 uses `osv-scanner -r .`) |

These tools download advisory data. Without network access or approval, the check is `NOT_VERIFIED`; say so instead of reporting zero advisories. Do not install a tool from the network without approval.

### Triage an advisory

An advisory in the dependency tree is a lead, not a finding. Work through:

1. **Is the vulnerable version resolved?** Read the lockfile, not the manifest range: `npm ls <pkg>`, `pnpm why <pkg>`, `pip show <pkg>`, `go list -m all`, `cargo tree -i <crate>`.
2. **Does it ship?** Development-only tools that never reach production or CI with secrets are lower priority, but build tools run with CI credentials.
3. **Is the affected code used?** Read the advisory for the affected function, option or file format, then search the imports and calls. For a transitive package, find which direct dependency calls it and whether that path is used.
4. **Can untrusted input reach it?** Trace from an entry point to the call, as in phase 3.
5. **Is it already mitigated?** Overrides or resolutions to a fixed version, configuration that disables the affected feature, input validation that excludes the trigger.

| Outcome | Record as |
|---|---|
| Vulnerable code is reachable with untrusted input | Finding, `CONFIRMED` or `LIKELY`; severity from phase 6, not copied from the advisory score |
| Used, but not reachable with untrusted input | Hardening note: upgrade on the normal schedule, say why it is not reachable |
| Not used, or development-only and not run with secrets | Hardening note: upgrade when convenient |
| Cannot tell | `POSSIBLE` with the `next_check` |

Recommend the upgrade in every case: reachability changes as code changes.

### Upgrade safely

Pick the smallest version that contains the fix, read its changelog for breaking changes, update one dependency per change, refresh the lockfile with the package manager (not by hand), and run the full test suite. For a transitive fix, prefer updating the direct dependency; use `overrides`, `resolutions` or constraints files only when needed, and note them for later removal.

## Supply-chain review

### New or unfamiliar dependencies

Check each package a change adds:

- The name is not a near-miss of a popular package, and the registry page links to the source repository you expect.
- Its age, release history and maintainers look normal; a recent ownership transfer or a sudden burst of releases deserves a closer look.
- It does not run install-time code it does not need (npm lifecycle scripts, `setup.py` code, Cargo `build.rs` network access, Gradle plugins).
- What it does matches the permissions it uses: a string utility does not need the network, the filesystem or child processes.
- The standard library or an existing dependency does not already do the job.

### Resolution and build inputs

- **Dependency confusion:** internal package names that a public registry could also serve. Check scoped registries in `.npmrc`, pip `--extra-index-url` (which consults both indexes), and repository order in Maven or Gradle.
- **Movable inputs:** Git and URL dependencies, `*` or `latest` versions, container base images by tag, tools downloaded in build scripts without a checksum, `curl | sh` installers, vendored code with no recorded upstream version.
- **Install-time execution during the audit:** installing an untrusted project's dependencies runs its code. Install with lifecycle scripts disabled (`npm ci --ignore-scripts`) or only inside a sandbox, and only with approval.
- **Containers:** pin base images by digest, run as a non-root user, keep secrets out of `ARG` and `ENV` (they remain visible in image history), and keep `.env` and `.git` out of the build context with `.dockerignore`.

## CI and CD security

### GitHub Actions

Run `code_audit.py workflows --root .`, then read each workflow to confirm or dismiss every candidate.

| Risk | What to look for | Safer pattern |
|---|---|---|
| Untrusted code in a privileged workflow | `pull_request_target` or `workflow_run` that checks out the pull request head and then installs, builds or tests it | Run untrusted code under `pull_request` with a read-only token; keep privileged steps in a separate workflow that treats artifacts as data |
| Script injection | `${{ github.event.issue.title }}`, `...pull_request.title`, `...comment.body`, `github.head_ref` and similar inside `run:` or `github-script` | Pass the value through `env:` and use the quoted shell variable |
| Broad token | No `permissions:` key, or `write-all` | Top-level `permissions: contents: read`, then grant per job only what it uses |
| Movable actions | Third-party `uses:` by tag or branch | Pin to the full commit SHA with a version comment and let Dependabot or Renovate update it |
| Secret exposure | `set -x` around secrets, printing env, uploading artifacts or caches that contain `.env` or credentials | Mask, scope secrets to the step that needs them, use environments |
| Self-hosted runners | Self-hosted runners reachable from pull requests on a public repository | GitHub-hosted runners for untrusted code, or ephemeral isolated runners |
| Cache and artifact poisoning | A job that runs untrusted code writes a cache or artifact that a release job restores | Separate cache keys by trust level; verify artifacts by digest before use |
| Cloud federation (OIDC) | Cloud trust policy that accepts any repository, branch or workflow (wildcard `sub`) | Restrict the subject to this repository and the protected branch or environment |

Repository settings decide much of the outcome: default token permissions, fork pull request approval, branch protection, required reviewers on environments, and CODEOWNERS on `.github/`. They are not in the source; mark them `NOT_VERIFIED` and list them for the owner.

### Other CI systems

Ask the same questions of GitLab CI, CircleCI, Jenkins, Azure Pipelines or Buildkite: which events run whose code, which secrets and tokens that code can read, what it can publish or deploy, and which settings outside the repository (protected branches and variables, token scopes, credential bindings) limit it.

## CI checks to propose

Propose these as changes for the owner to review; do not push CI configuration without permission. Start new checks as advisory, triage the first results, then make the ones with a low false-positive rate blocking.

| Check | Examples | Suggested gate |
|---|---|---|
| Secret scanning | Gitleaks in CI, the host's secret scanning and push protection, a pre-commit hook | Block on any new hit |
| Dependency advisories | The ecosystem tool above, or osv-scanner | Block on HIGH or CRITICAL in production dependencies after triage |
| Dependency updates | Dependabot or Renovate, including the `github-actions` ecosystem | Advisory |
| Static analysis | CodeQL or Semgrep with project rules; a rule for each confirmed finding whose shape is syntactic | Block on rules with proven precision |
| Workflow security | `code_audit.py workflows --fail-on high`, or a dedicated Actions linter such as zizmor or actionlint if available | Block on HIGH |
| Repository posture | OpenSSF Scorecard | Advisory |
| Audit regression tests | The tests written for each fixed finding, in the normal test job | Block |

Keep private code private: hosted analysis services and registry-backed rule sets send code or metadata off the machine. Use local rule files (and `semgrep --metrics=off`) when the owner has not approved that.

A minimal skeleton for the owner to adapt (replace each `<sha>` with the full commit SHA of the release you reviewed):

```yaml
name: security-checks
on: [pull_request]
permissions:
  contents: read
jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>   # vX.Y.Z
      - run: npm ci --ignore-scripts
      - run: npm audit --omit=dev --audit-level=high
      - run: python3 path/to/code_audit.py workflows --root . --fail-on high
```

## Done when

- Working tree (via LaunchGuard), local history and sensitive file names were scanned, or each is `NOT_VERIFIED` with the reason; remote-only refs and deployed artifacts are listed as not covered.
- Every secret hit is a placeholder, public-by-design, or a finding with `ROTATION REQUIRED`; no value appears anywhere in the output.
- Every manifest has a lockfile status, every advisory has a reachability outcome, and audit tools that could not run are `NOT_VERIFIED`.
- Every workflow candidate is confirmed or dismissed with a reason, and repository settings that matter are listed for the owner.
- Proposed CI checks are written down for the owner, not applied.
