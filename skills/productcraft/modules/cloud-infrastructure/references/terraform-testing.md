# Terraform: testing modules and plans

Read this when you add tests to a Terraform module, write `.tftest.hcl` files, mock providers, add validation or policy checks on plans, or decide whether a test may create real infrastructure. Provider acceptance tests (Go, `TF_ACC`) are in `terraform-provider-development.md`.

## The ladder: cheapest check first

| Rung | What it proves | Needs cloud access | Cost |
|---|---|---|---|
| `fmt`, `validate`, tflint, misconfiguration scan | Syntax, references, known bad settings | No | Seconds |
| Variable `validation`, `precondition`, `postcondition`, `check` blocks | Inputs and assumptions hold at plan or apply | No for plan-time checks | None |
| `terraform test` with `command = plan` or a mock provider | Module logic: counts, names, conditionals, outputs, rejected inputs | No | Seconds |
| Policy as code on the plan JSON (OPA/conftest, Sentinel) | Organization rules across every change | Only to make the plan | Seconds |
| `terraform test` with `command = apply` against a real provider | The cloud accepts the configuration and it converges | Yes, in a sandbox account | Real money and minutes |
| End-to-end tests (Terratest or a scripted smoke test) | The deployed system behaves: a URL answers, a role can reach a bucket | Yes | Highest |

Climb only as far as the risk needs. Most modules get strong coverage from the first four rungs without touching a cloud account. Real-infrastructure tests need the user's go-ahead every time: they create billable resources, may need broad permissions and can leave resources behind.

## Checks inside the configuration

```hcl
resource "aws_db_instance" "this" {
  # ...
  lifecycle {
    precondition {
      condition     = var.environment != "prod" || var.multi_az
      error_message = "Production databases must be Multi-AZ."
    }
  }
}

check "endpoint_answers" {           # 1.5+: reports a warning, never blocks apply
  data "http" "health" {
    url = "https://${aws_lb.this.dns_name}/healthz"
  }
  assert {
    condition     = data.http.health.status_code == 200
    error_message = "Health endpoint did not return 200."
  }
}
```

Use `validation` for one input, `precondition` for assumptions that span inputs and resources, `postcondition` for guarantees about what the provider returned, and `check` blocks for continuous health signals that should warn rather than fail.

## `terraform test` essentials (1.6+)

- Test files end in `.tftest.hcl` and live in the module root or `tests/`. Each file runs its `run` blocks in order against a fresh, temporary state; resources created by `apply` runs are destroyed when the file finishes, in reverse order.
- A `run` block has `command = plan` or `apply` (default `apply`), optional `variables`, `assert` blocks, `expect_failures`, and a `module` block to run a helper module (setup, fixtures, or a module under `examples/`). Helper module sources must be local paths or registry addresses.
- Variables set in a test file take precedence over every other source. A later run can read an earlier run's outputs as `run.<name>.<output>`.
- `expect_failures = [var.x]` (or an output, check block or resource) makes a run pass only when that object fails its validation or condition: the way to test that bad input is rejected.
- Mocks (1.7+): `mock_provider "aws" {}` replaces the real provider with one that returns generated values for computed attributes, so `command = apply` runs without credentials or real resources. `override_resource`, `override_data` and `override_module` pin specific values, inside a run, a mock provider or the whole file.
- Since 1.9, `state_key` lets runs share or separate state, and `parallel = true` lets independent runs execute concurrently.

### The unknown-value trap

In `command = plan` against a real provider, computed attributes (`id`, `arn`, endpoints) are unknown. An assertion that reads one fails with an unknown-value error, or, worse, gets written to test only known inputs. Assert on computed values with a mock provider and `command = apply`, or override the value:

```hcl
# tests/bucket.tftest.hcl
mock_provider "aws" {}

variables {
  name          = "audit-logs"
  environment   = "test"
  allowed_cidrs = []
}

run "rejects_open_admin_access" {
  command = plan
  variables {
    allowed_cidrs = ["0.0.0.0/0"]
  }
  expect_failures = [var.allowed_cidrs]
}

run "blocks_public_access_and_encrypts" {
  command = apply                       # mock provider: nothing is created
  assert {
    condition     = aws_s3_bucket_public_access_block.this.block_public_policy
    error_message = "Public bucket policies must be blocked."
  }
  assert {
    condition = alltrue([
      for r in aws_s3_bucket_server_side_encryption_configuration.this.rule :
      r.apply_server_side_encryption_by_default[0].sse_algorithm == "aws:kms"
    ])
    error_message = "Bucket must use KMS encryption."
  }
}

run "exposes_key_arn" {
  command = apply
  override_resource {
    target = aws_kms_key.this
    values = { arn = "arn:aws:kms:eu-west-1:111122223333:key/test-key" }
  }
  assert {
    condition     = output.kms_key_arn == "arn:aws:kms:eu-west-1:111122223333:key/test-key"
    error_message = "kms_key_arn output must pass the key ARN through."
  }
}
```

Mocks prove the module's logic, not that the cloud accepts it. Provider-side rules (name length, region support, quota) only show up against the real API.

### Running

```bash
terraform init                                  # test files need initialized providers
terraform test                                  # all files
terraform test -filter=tests/bucket.tftest.hcl  # one file; -filter takes file paths
terraform test -verbose                         # print plans and state for each run
terraform test -help                            # check flags for your version (JUnit output, test directory)
```

Name files so CI can separate them: mocked or plan-only files run on every pull request without cloud credentials; files that apply real resources run on demand or on a schedule in a sandbox account with their own credentials.

## Tests that create real resources

Ask before running them, then:

- Use a dedicated sandbox account, subscription or project with a budget alert. Never point tests at shared or production accounts.
- Generate unique names per run (a helper module that outputs a random suffix) so parallel runs and leftovers do not collide.
- Watch the teardown. If destroy fails, Terraform lists the resources it could not remove; record them in the report and clean them up only with the user's approval.
- Expect minutes, not seconds, and give CI jobs generous timeouts. Databases, clusters and CDNs are slow to create and delete.

## Policy as code on plans

Policies check every change the same way, whoever wrote it. Run them on the JSON plan (`terraform show -json tfplan > plan.json`).

```rego
# policy/guardrails.rego (conftest or opa eval)
package main

import rego.v1

web_port(p) if p in {80, 443}

deny contains msg if {
  some rc in input.resource_changes
  rc.type == "aws_security_group_rule"
  rc.change.after.type == "ingress"
  "0.0.0.0/0" in rc.change.after.cidr_blocks
  not web_port(rc.change.after.from_port)
  msg := sprintf("%s opens port %v to the internet", [rc.address, rc.change.after.from_port])
}
```

```bash
conftest test --policy policy/ plan.json
```

- OPA 1.0 (December 2024) made the `if` and `contains` keywords mandatory; `import rego.v1` keeps the policy valid on older versions too. Check the installed version.
- Write a passing and a failing fixture plan for each policy and run `opa test` or `conftest verify`, so a policy that never fires is caught.
- HCP Terraform runs Sentinel or OPA policies between plan and apply; the same rules apply.
- The bundled `../scripts/plan_review.py` is a fixed, general review for the agent's own use; project policies encode the organization's specific rules. Use both.

## End-to-end tests

Terratest (Go) applies real configuration, checks behavior (HTTP responses, connectivity, IAM access) and destroys it with `defer terraform.Destroy(t, opts)`. It is the right tool when behavior, not configuration, is the risk. It carries every cost and approval requirement above. Keep these suites small and run them on a schedule.

## Done when

- [ ] Each variable with constraints has a validation and a test that bad input is rejected (`expect_failures`).
- [ ] Module logic (conditionals, `for_each` keys, outputs) is covered by plan-mode or mocked tests that run without cloud credentials.
- [ ] No assertion reads a computed attribute in plan mode against a real provider.
- [ ] Real-infrastructure tests ran only with the user's go-ahead, in a sandbox, and the report lists anything left behind.
- [ ] Policies have passing and failing fixtures; the report says which checks ran and which were `NOT VERIFIED`.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| "Unknown condition value" in a plan run | Assertion reads a computed attribute | Mock provider with `command = apply`, or `override_resource` |
| Tests pass but the module fails in the cloud | Only mocks were used | Add one sandbox apply test, run on a schedule |
| Module source error in a `run` block | Git or HTTP source in the test `module` block | Use a local path or registry address |
| Leftover resources after a failed run | Teardown error | Record them, clean up with approval, add unique name prefixes |
| Policy never fails | Wrong path into the plan JSON (`after` versus `before`, list versus object) | Add a failing fixture and `conftest verify` |
