# Pipelines for infrastructure as code

Read this when you create or change a CI/CD pipeline that runs Terraform, OpenTofu, the AWS CDK, Bicep or Pulumi: plan on pull requests, apply after approval, drift detection, or cloud credentials for CI. General pipeline practice (speed, flaky tests, pinned actions, rollout plans) is in `../../engineering-practices/references/ci-and-release.md`; workflows that run AI agents or react to outsiders are in `../../code-security-review/references/ci-agent-workflows.md`. Azure Pipelines specifics are in `azure-devops.md`.

## The shape

| Stage | Trigger | Credentials | Output |
|---|---|---|---|
| Static checks: fmt, validate, lint, tests with mocks, misconfiguration scan | Every pull request | None | Pass or fail |
| Plan per affected environment | Pull requests from trusted branches | Read-only plan role (read resources, read and lock state) | Saved plan file (private artifact), readable summary on the pull request, `../scripts/plan_review.py` and policy results |
| Apply | Merge to the default branch, then a manual approval on a protected environment | Apply role, only in that job | Applied changes and the apply log |
| Drift detection | Schedule | Read-only plan role | Alert or issue when the plan is not empty |

- **Apply exactly what was reviewed.** Save the plan (`terraform plan -out=tfplan`) and apply that file (`terraform apply tfplan`). Terraform refuses a saved plan whose state has changed since ("Saved plan is stale"), which forces a fresh plan and review. If your setup re-plans at apply time instead, require approval on the new plan.
- **One run per state at a time.** Serialize jobs per state (a concurrency group per environment) in addition to state locking, so queued runs do not apply stale plans one after another.
- **Environments in order.** Apply to staging, check it, then production, each with its own approval, role and state.
- **Never auto-apply production.** An approval step with named reviewers sits between plan and apply; the agent never approves.

## Credentials

- Use OIDC federation from the CI system to the cloud: no stored access keys. Narrow the trust to the repository and the environment, so a pull-request job cannot assume the apply role. Examples of the subject to match: GitHub Actions `repo:ORG/REPO:environment:production`, an Azure federated credential bound to that subject, a Google Cloud workload identity pool with an attribute condition on the repository.
- Separate roles: plan (read-only plus state access) and apply (write), per environment. Changes to these roles are IAM changes and need explicit approval.
- Provider credentials for third-party providers (DNS, monitoring, SaaS) come from the CI secret store, scoped to the apply environment.

## Untrusted code and plans

`terraform plan` runs code: providers are downloaded binaries, and data sources such as `external` run programs during planning. A pull request from a fork or an untrusted contributor can therefore exfiltrate whatever credentials the plan job holds. Run plans with credentials only for branches in the main repository from trusted authors; for outside contributions, run static checks only until a maintainer has reviewed the code. The same applies to `cdk synth` and `pulumi preview`, which execute the program.

## Plans are sensitive artifacts

Saved plan files and `terraform show -json` output contain resource attributes in clear text, including values marked sensitive. Upload them only as private, short-retention artifacts, never to pull-request comments or public logs. Post the human-readable summary (`terraform show -no-color tfplan`, which redacts sensitive values) or the `../scripts/plan_review.py` report instead, and check it for data that is not marked sensitive but should not be public (user data scripts, connection strings).

## A GitHub Actions sketch

```yaml
name: infra
on:
  pull_request:
    paths: ["infra/**"]
  push:
    branches: [main]
    paths: ["infra/**"]

permissions:
  contents: read

concurrency:
  group: infra-prod
  cancel-in-progress: false

jobs:
  plan:
    if: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    permissions: { contents: read, id-token: write, pull-requests: write }
    steps:
      - uses: actions/checkout@<full-commit-sha>                 # v4
      - uses: hashicorp/setup-terraform@<full-commit-sha>        # v3
        with: { terraform_version: "1.14.0" }
      - uses: aws-actions/configure-aws-credentials@<full-commit-sha>   # v4
        with: { role-to-assume: "${{ vars.PLAN_ROLE_ARN }}", aws-region: eu-west-1 }
      - run: terraform -chdir=infra init -input=false
      - run: terraform -chdir=infra plan -input=false -out=tfplan
      - run: terraform -chdir=infra show -json tfplan > plan.json
      - run: python3 tools/plan_review.py plan.json --fail-on high   # a vendored copy of the helper
      - run: rm -f plan.json

  apply:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: production          # required reviewers configured on the environment
    permissions: { contents: read, id-token: write }
    steps:
      - uses: actions/checkout@<full-commit-sha>
      - uses: hashicorp/setup-terraform@<full-commit-sha>
        with: { terraform_version: "1.14.0" }
      - uses: aws-actions/configure-aws-credentials@<full-commit-sha>
        with: { role-to-assume: "${{ vars.APPLY_ROLE_ARN }}", aws-region: eu-west-1 }
      - run: terraform -chdir=infra init -input=false
      - run: terraform -chdir=infra plan -input=false -out=tfplan
      - run: terraform -chdir=infra apply -input=false tfplan
```

This sketch re-plans in the apply job after the environment approval; reviewers approve that job knowing the plan was reviewed on the pull request. Teams that need byte-for-byte equality pass the saved plan from a dedicated plan-on-main job to the apply job as a private artifact. Replace every `<full-commit-sha>` with the pinned commit of the action version you reviewed.

## Drift detection

```bash
terraform plan -input=false -detailed-exitcode -lock=false -refresh=true   # 0 no changes, 1 error, 2 changes
```

Run it on a schedule with the read-only role (`-lock=false` avoids blocking real runs; it never writes state). Exit code 2 opens an issue or alert listing the drifted addresses (`../scripts/plan_review.py` reports drift without values). Drift is fixed by a reviewed change, never by an automatic apply.

## Other runners

HCP Terraform and Terraform Enterprise run plans and applies remotely with VCS-driven workflows, policy checks and approvals; Atlantis runs plan and apply from pull-request comments on your own infrastructure. The same rules hold: approvals by people, scoped credentials, no plans with credentials on untrusted code, and sensitive plan output kept private.

## Done when

- [ ] Pull requests get static checks without credentials, and plans only for trusted branches with a read-only role.
- [ ] Applies use a saved, reviewed plan or a fresh plan behind an approval, one at a time per state, environment by environment.
- [ ] CI authenticates with OIDC trust narrowed to repository and environment; no stored cloud keys.
- [ ] Plan files and JSON stay private and short-lived; pull-request comments carry only redacted summaries.
- [ ] Pipeline changes that alter roles, approvals or branch protection were approved by the user.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Fork pull request leaked cloud credentials | Plan with credentials on untrusted code | Plans only for trusted branches; static checks for forks |
| "Saved plan is stale" at apply | State changed after the plan | Re-plan and re-approve; serialize runs |
| Two merges applied out of order | No per-state concurrency control | Concurrency group per environment, no cancellation mid-apply |
| Secrets visible in a pull-request comment | Full plan or JSON posted | Post the redacted summary or the review report |
| Drift job blocks deploys | Drift plan takes the state lock | `-lock=false` for read-only drift plans |
