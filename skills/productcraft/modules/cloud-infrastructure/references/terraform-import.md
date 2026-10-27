# Terraform: importing existing resources

Read this when infrastructure that was created by hand, by a script or by another tool must come under Terraform management, when you inventory what exists in an account, or when you move resources between states.

Importing writes state only, but an import plan that also shows updates will change the real resource on apply. The target is a plan that says "N to import, 0 to add, 0 to change, 0 to destroy".

## Pick the mechanism

| Mechanism | Version | Use it when |
|---|---|---|
| `import` block with `id` | 1.5+ | The default. Reviewed in a plan, applied like any change, repeatable across environments |
| `import` block with `for_each` | 1.7+ | Many resources of one type from a map of names to IDs |
| `import` block with `identity` | 1.12+, provider support needed | The provider exposes resource identity (structured attributes such as account, region and ID) instead of a single ID string |
| `terraform query` with `list` blocks in `.tfquery.hcl` files | 1.14+, provider support needed | Discovering many resources by filter and generating `import` blocks and configuration for them |
| `terraform import ADDRESS ID` (CLI) | Any | Avoid: it writes state immediately with no plan. Only with the user's approval when blocks cannot express the case |

Run `terraform version` and check the provider's documentation for list-resource and identity support before choosing the newer paths; support is per resource type and growing.

## Workflow

1. **Confirm the target.** Account, subscription or project, region, and workspace (`aws sts get-caller-identity`, `az account show`, `gcloud config list`, `terraform workspace show`). Imports into the wrong state are hard to untangle.
2. **Inventory read-only.** List candidates with the provider CLI (`aws ec2 describe-instances --filters ...`, `az resource list --resource-group ...`, `gcloud asset search-all-resources --scope=projects/ID`) or with Terraform Search (below). Record name, ID, tags and owner for each.
3. **Settle ownership.** For each resource ask who manages it now: the console, a script, CloudFormation or ARM/Bicep, a Kubernetes controller, another Terraform state. Two tools managing one resource fight on every run. Remove the other owner first (for a CloudFormation stack, set `DeletionPolicy: Retain` and remove the resource from the stack) and never import an address that another state already holds.
4. **Write import blocks** in a separate `imports.tf`:

```hcl
import {
  to = aws_sqs_queue.jobs
  id = "https://sqs.eu-west-1.amazonaws.com/111122223333/jobs"
}

import {
  for_each = var.legacy_buckets          # map: logical name => bucket name
  to       = aws_s3_bucket.legacy[each.key]
  id       = each.value
}
```

   The `id` format differs per resource type (a name, an ARN, a URL, a full Azure resource ID, a composite string). Read the "Import" section of that resource's provider page instead of guessing.
5. **Generate configuration** for resources that have none: `terraform plan -generate-config-out=generated.tf`. The file must not exist yet. Generated code is a starting point, not a result.
6. **Clean it up.** Remove read-only and computed attributes and explicit defaults; replace literal IDs with references; replace environment-specific values with variables; give resources meaningful names (with `moved` blocks if you rename after the import); move them into the right files or modules. Check the generated file for sensitive values before it goes near a commit.
7. **Plan until clean.** Iterate until every imported resource shows "will be imported" with no changes. Then run `plan_review.py --expect-no-changes` on the JSON plan; `IMPORT_WITH_CHANGES` or `UNEXPECTED_CHANGE` means the configuration still differs from reality.
8. **Hand over the apply.** Applying writes the imports into state and needs the user's go-ahead, like any apply. Afterwards, remove the `import` blocks (they are no-ops once imported, but they clutter the configuration and confuse later readers).

## Discovery with Terraform Search (1.14+)

```hcl
# discover.tfquery.hcl
provider "aws" {
  region = "eu-west-1"
}

list "aws_instance" "team" {
  provider = aws
  limit    = 50
  config {
    filter {
      name   = "tag:team"
      values = ["payments"]
    }
  }
}
```

```bash
terraform init
terraform providers schema -json | jq '.provider_schemas[].list_resource_schemas // {} | keys'   # what can be listed
terraform query                                       # print matches, read-only
terraform query -generate-config-out=generated.tf     # import blocks plus configuration
```

- The `config` block schema is specific to each list resource; read it from `terraform providers schema -json` or the provider docs.
- Queries call the cloud's list APIs with your credentials. They are read-only, but large accounts can hit API rate limits; start with filters and a `limit`.
- Treat the generated file exactly like `-generate-config-out` output from step 5: clean, plan, review.

## Moving resources between states

1. In the old configuration add `removed { from = ADDRESS  lifecycle { destroy = false } }`, plan (it must show "will no longer be managed", not "destroy"), and apply with approval.
2. In the new configuration add the resource and an `import` block, plan until clean, apply with approval.
3. Do it one small group at a time, and keep a note of IDs in between so nothing is lost if step 2 stalls.

## Done when

- [ ] Every imported resource has exactly one owner, and the target account and state were confirmed first.
- [ ] Generated configuration was cleaned: no computed attributes, no hard-coded environment values, meaningful names, no secrets.
- [ ] The plan shows imports only; `plan_review.py --expect-no-changes` has no HIGH or `IMPORT_WITH_CHANGES` findings.
- [ ] The apply was run by or with the explicit approval of the user, and the import blocks were removed afterwards.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Import plan also replaces the resource | An attribute that forces replacement differs (name, AZ, engine) | Copy the real value into configuration |
| "Resource already managed by Terraform" | The address or object is already in some state | Find the owning state; move it with `removed` plus `import` |
| Endless diff after import on a nested setting | Provider splits the object into several resource types (bucket policy, versioning, encryption) | Import each sub-resource into its own resource type |
| Generated file fails to validate | Conflicting or deprecated arguments were emitted | Delete the conflicting argument and keep the one the provider documents |
| Two tools keep reverting each other | Another tool still manages the resource | Release it from the other tool before importing |
