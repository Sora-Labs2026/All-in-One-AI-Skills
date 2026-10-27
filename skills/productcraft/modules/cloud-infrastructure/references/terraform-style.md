# Terraform: writing configuration that reviews well

Read this when you write or review Terraform or OpenTofu configuration: a new root module, a new resource, variables and outputs, provider setup, or a lint and formatting pass. Module boundaries, state and refactoring are in `terraform-modules-and-state.md`; tests are in `terraform-testing.md`.

The goal is configuration whose plan a reviewer can predict from the diff. Every rule below serves that.

## Versions first

- Run `terraform version` (or `tofu version`) and read `required_version` and `.terraform.lock.hcl` before writing anything. Language features arrive in minor releases; the ones this module relies on are listed with the version that introduced them.
- Pin the core version with a lower and upper bound in root modules (`required_version = ">= 1.9, < 2.0"`) and every provider with a pessimistic constraint (`version = "~> 6.0"`). Reusable modules state the minimum they need and avoid tight upper bounds, so callers can upgrade.
- Commit `.terraform.lock.hcl`. When CI or teammates run on other platforms, add their hashes: `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64`. Upgrade providers deliberately with `terraform init -upgrade`, read the provider changelog, and review the lock file diff like a dependency bump (`../../engineering-practices/references/dependencies.md`).
- OpenTofu is a compatible fork. Most of this module applies to both; HCP Terraform features (Stacks, Terraform Search, some run tasks) are Terraform-only, and OpenTofu has features of its own such as client-side state encryption. Check which binary the project uses before suggesting commands.

## File layout

| File | Holds |
|---|---|
| `terraform.tf` or `versions.tf` | The `terraform` block: `required_version`, `required_providers`, backend (root modules only) |
| `providers.tf` | Provider configurations (root modules only) |
| `main.tf`, or one file per concern (`network.tf`, `database.tf`) | Resources and data sources, dependencies before dependents |
| `variables.tf` | Inputs: required first, then optional, each group alphabetical |
| `outputs.tf` | Outputs, alphabetical |
| `locals.tf` | Shared local values, when there are more than a few |
| `moved.tf`, `imports.tf` | Refactoring and import blocks, kept apart so they are easy to remove later |

Follow the project's existing layout when it has one. Inside a block, put meta-arguments first (`count`, `for_each`, `provider`), then arguments, then nested blocks, then `depends_on` and `lifecycle` last, each group separated by a blank line.

## Naming

- Lowercase with underscores for resource names, variables, outputs and locals. Name the thing, not its type: `aws_s3_bucket.audit_logs`, not `aws_s3_bucket.s3_bucket_logs`. Use `main` or `this` only for the single primary resource of its type in a module.
- Names are part of state addresses. Renaming later needs a `moved` block (see the modules reference), so choose deliberately.
- Booleans read as statements: `enable_versioning`, `create_nat_gateway`. Avoid negatives such as `disable_x`.
- Cloud resource names built from inputs (`"${var.name}-${var.environment}"`) must respect the provider's length and character limits; validate them in the variable rather than letting apply fail halfway.

## Variables

```hcl
variable "allowed_cidrs" {
  description = "CIDR ranges allowed to reach the admin endpoint. Empty means no access."
  type        = list(string)
  default     = []
  nullable    = false

  validation {
    condition     = alltrue([for c in var.allowed_cidrs : can(cidrhost(c, 0)) && c != "0.0.0.0/0"])
    error_message = "Each entry must be a valid CIDR range, and 0.0.0.0/0 is not allowed."
  }
}
```

- Every variable has `type` and `description`. Prefer precise types (`object({...})` with `optional(type, default)` attributes, available since 1.3) over `map(any)` or `any`.
- Set `nullable = false` on collections that feed `for_each` so callers cannot pass `null`.
- Validate early: formats, allowed values, ranges. Since 1.9, a validation condition may refer to other variables.
- `sensitive = true` hides a value in plan output only. The value is still stored in state and plan files in clear text. For credentials, prefer `ephemeral = true` variables and ephemeral resources (1.10+) and write-only arguments where the provider supports them (1.11+), which keep the value out of state entirely. Never give a sensitive variable a default.
- Never commit `*.tfvars` files that hold secrets. Supply secrets from a secret manager, the CI secret store or `TF_VAR_` environment variables set by the user (`../../agent-safety/references/secrets.md`).

## Outputs

- Every output has a `description`. Output discrete attributes (`id`, `arn`, `endpoint`), not whole resource objects; whole objects leak sensitive fields and change shape with provider versions.
- Mark secret outputs `sensitive = true`, and ask whether the output needs to exist at all.

## Expressions that keep plans stable

- **`for_each` over `count`** for anything with more than one instance. With `count`, removing the middle element shifts every later index and Terraform replaces them. With `for_each`, keys are stable names.
- `for_each` keys must be known at plan time. Use static strings or input values, never IDs of resources created in the same apply ("Invalid for_each argument").
- Use `count = var.enabled ? 1 : 0` for a single optional resource and reference it with `one(aws_x.this[*].id)` or `try(aws_x.this[0].id, null)`.
- `dynamic` blocks only for genuinely optional or repeated nested blocks. Over-use makes configuration unreadable.
- Prefer implicit dependencies through references. `depends_on` hides intent and, on a module call, can push data sources inside the module to apply time, leaving more values unknown in the plan.
- Use `coalesce()` and `try()` for defaults instead of long conditionals. Keep `locals` for values used more than once or that need a name to be understood.
- Look up values that change (latest image IDs, availability zones) with data sources, and decide whether a change in the lookup should replace resources. An unpinned "most recent image" lookup replaces instances every time a new image is published.

## Providers

- Configure providers only in root modules; reusable modules declare `required_providers` (and `configuration_aliases` when they need more than one configuration) and receive configurations through `providers = { ... }`.
- Use provider-level default tags or labels (`default_tags` in the AWS provider) for ownership, environment and cost allocation, so every resource is attributable.
- Authenticate through the environment: workload identity (OIDC) in CI, SSO or CLI profiles locally. Never put access keys in provider blocks.

## Lifecycle settings

| Setting | Use it for | Trap |
|---|---|---|
| `prevent_destroy = true` | Databases, buckets, keys, DNS zones | It only blocks plans that destroy the resource while the block is in configuration; deleting the block removes the protection |
| `create_before_destroy = true` | Resources whose replacement must not cause downtime | Names must be unique per instance, or the new one collides with the old |
| `ignore_changes = [tags["LastScanned"]]` | Attributes another system legitimately owns | Broad lists (`all`) hide drift; list attributes narrowly and say why in a comment |
| `replace_triggered_by` | Forcing a replacement when a related resource changes | Easy to trigger unexpected replacements; confirm with a plan |

Pair `prevent_destroy` with the cloud's own protection (deletion protection on databases, versioning and object lock on buckets) because the Terraform flag does nothing outside Terraform.

## Format, validate, lint, scan

```bash
terraform fmt -check -recursive        # formatting; run without -check to fix
terraform init -backend=false          # providers and modules only, no state access
terraform validate                     # syntax and internal consistency
tflint --init && tflint --recursive    # provider-aware lint; enable the ruleset plugin for the cloud
trivy config .                          # or checkov -d . ; misconfiguration scan, advisory only
terraform-docs markdown table . > README.md   # if the project generates module docs
```

Scanner findings are leads. Fix real ones, and suppress a finding only with an inline comment that gives the reason. Report what ran; do not claim a scan you did not run.

## Repository hygiene

Ignore `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfplan` or other saved plan files, `crash.log`, and any `*.tfvars` that holds secrets. Commit `*.tf`, `.terraform.lock.hcl`, test files and example `*.tfvars.example` files with placeholders.

## Done when

- [ ] `terraform fmt -check` and `terraform validate` pass; tflint and the configured scanner ran, with each finding fixed or justified.
- [ ] Every variable and output has a type (variables) and a description; secrets have no defaults and no committed values.
- [ ] Multi-instance resources use `for_each` with keys known at plan time.
- [ ] Provider and core versions are constrained and the lock file is committed.
- [ ] A plan was produced and reviewed as described in `../GUIDE.md`; nothing was applied without the user's go-ahead.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Plan replaces several instances after removing one | `count` index shift | Move to `for_each` with a `moved` block per instance |
| "Invalid for_each argument" | Keys depend on values known only after apply | Key by input names; pass IDs as values, not keys |
| Secret visible in state or CI logs | `sensitive` treated as encryption | Ephemeral or write-only values; encrypted, access-controlled state; no plan files in public artifacts |
| Instances replaced on every plan | Data source returns the newest image each run | Pin the image ID or move image choice into a reviewed variable |
| Perpetual diff on one attribute | Provider normalizes the value (JSON, case, ordering) | Write the normalized form (`jsonencode`, sorted lists) or a narrow `ignore_changes` with a comment |
