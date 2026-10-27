# Azure with Terraform: Azure Verified Modules and provider practice

Read this when you write Terraform for Azure, use or contribute to an Azure Verified Module (AVM), choose between the `azurerm` and `azapi` providers, or review an Azure module against the AVM specification.

Azure Verified Modules are Microsoft's official, maintained set of Terraform (and Bicep) modules with a published specification. Using them saves writing secure defaults by hand; contributing to them means meeting that specification. The specification is versioned and changes; read the current Terraform requirements on the AVM site before claiming a module complies.

## Consuming AVM modules

- Modules are published on the Terraform Registry under the `Azure` namespace with predictable names: `avm-res-<provider>-<resource>` for one resource type with its supporting pieces (`Azure/avm-res-storage-storageaccount/azurerm`), `avm-ptn-*` for multi-resource patterns, `avm-utl-*` for utilities.
- Pin `version` exactly or with `~>` and upgrade deliberately; read the module's changelog, because modules below 1.0 may change their interface in minor releases.
- Most resource modules expose the same interface blocks, so learning one teaches the rest: `tags`, `lock`, `role_assignments`, `diagnostic_settings`, `private_endpoints`, `managed_identities` and, where supported, `customer_managed_key`. Use them instead of wiring those resources separately.
- AVM modules include a deployment telemetry toggle, `enable_telemetry`, which defaults to on. Tell the user and let them choose; set `enable_telemetry = false` if their policy forbids it.
- Read what the module creates by default (`terraform plan` on an example) before adopting it. A resource module may add diagnostic settings, locks or role assignments that need permissions the deploy identity lacks.

```hcl
module "storage" {
  source  = "Azure/avm-res-storage-storageaccount/azurerm"
  version = "0.6.4"                 # example; use the version you reviewed

  name                = "stappprodweu001"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  enable_telemetry    = false

  public_network_access_enabled = false
  shared_access_key_enabled     = false

  role_assignments = {
    app_reader = {
      role_definition_id_or_name = "Storage Blob Data Reader"
      principal_id               = azurerm_user_assigned_identity.app.principal_id
    }
  }
}
```

Argument names above illustrate the shape; check the module's README for the exact inputs of the version you pin.

## Provider practice for `azurerm` 4.x and `azapi` 2.x

- `azurerm` 4.0 (2024) requires `subscription_id` in the provider block or the `ARM_SUBSCRIPTION_ID` environment variable, and replaced automatic resource provider registration with the `resource_provider_registrations` setting. Upgrading from 3.x is a planned migration: read the upgrade guide and plan every environment.
- Use `azapi` for Azure resource types or properties that `azurerm` does not support yet, or for day-zero API versions. In `azapi` 2.x the `body` is an HCL object rather than a JSON string, and outputs are read through `response_export_values`. Pin the API version in the resource `type` and plan before every change.
- Authenticate with Azure CLI login locally and with OIDC (federated credentials on a user-assigned identity or app registration) in CI. Avoid client secrets; if one is unavoidable, it lives in the CI secret store and expires.
- Mind Azure name rules: storage accounts take 3 to 24 lowercase letters and digits and must be globally unique; Key Vault names are global too and enter soft-delete on destroy, so recreating the same name can fail until the vault is purged or recovered. Purging is irreversible; ask first.
- `features {}` in the provider controls destructive defaults (for example whether destroying a resource group that still contains resources is refused, and whether Key Vaults are purged on destroy). Keep the safe defaults in production; relax them only in test configurations.
- Resource groups are containers: destroying one deletes everything inside it, including resources Terraform never managed. `../scripts/plan_review.py` flags that as `DELETE_CONTAINER`.

## Writing a module to the AVM standard

The specification's requirements fall into a few groups. Treat this as orientation, then check each against the current spec:

- **Dependencies:** reference other modules only through the registry with pinned versions, and only AVM modules; no git sources.
- **Providers:** declare `azurerm` and/or `azapi` in `required_providers` with both a minimum and a maximum major version; no `provider` blocks inside the module.
- **Inputs:** every variable typed precisely and described for module users; no whole-module `enabled` switch; collections not nullable; no defaults for sensitive inputs; feature switches phrased positively (`*_enabled`).
- **Outputs:** discrete computed attributes rather than whole resource objects; sensitive outputs marked; deprecated inputs and outputs moved to clearly named files and removed at the next major version.
- **Compatibility:** new resources added in a minor release sit behind a toggle that defaults to off; renames use `moved` blocks; changes of type, default, nullability or `count` versus `for_each` are breaking.
- **Style:** lower snake case names, meta-arguments first and `lifecycle` last in blocks, `dynamic` blocks for optional nested blocks, `coalesce` or `try` for defaults, unquoted `ignore_changes` entries.
- **Quality gates:** `terraform fmt` and `validate`, tflint with the Azure ruleset, a misconfiguration scanner, terraform-docs generated README, and end-to-end examples that deploy and destroy in a test subscription (with the user's approval and budget).

These overlap heavily with `terraform-style.md` and `terraform-modules-and-state.md`; follow those for anything the spec does not fix.

## AVM module, community module or your own

| Choose | When |
|---|---|
| An AVM resource or pattern module | It covers the resource and the interfaces you need; you accept its release pace and review its defaults |
| A community module | No AVM module exists and the community one is maintained, pinned and read in full like any dependency |
| Your own module | Company-specific policy, or the AVM module drags in far more than you use; consider wrapping the AVM module instead of rewriting it |

When an AVM module lacks a feature, prefer an issue or contribution upstream over a private fork that stops receiving fixes.

## Testing an Azure module

- Plan-mode and mocked `terraform test` files cover naming, toggles and interface wiring without a subscription (`terraform-testing.md`).
- Example deployments that create and destroy real resources run only with the user's go-ahead, in a test subscription with a budget, and with the provider's test-friendly `features {}` settings (for example allowing deletion of resource groups that still contain resources) confined to that test configuration.
- After an apply test, run a second plan and expect no changes; Azure APIs often normalize values (casing of IDs, default tags), which shows up as perpetual diffs.

## Done when

- [ ] AVM modules are pinned, their default resources were reviewed in a plan, and the telemetry setting is the user's choice.
- [ ] The `azurerm` and `azapi` versions are constrained; authentication uses CLI login or OIDC, not stored secrets.
- [ ] Destroys of resource groups, Key Vaults and storage accounts were shown to the user with their consequences (soft delete, purge, contained resources).
- [ ] For a module claimed to meet AVM requirements, each requirement group was checked against the current specification and the report lists any gaps.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Plan fails on upgrade to `azurerm` 4.x | `subscription_id` missing, removed arguments | Follow the 4.0 upgrade guide; set the subscription explicitly |
| "Vault name already in use" after destroy and recreate | Key Vault soft delete | Recover the vault, or purge with approval, or use a new name |
| Deploy fails on role assignment inside an AVM module | Deploy identity lacks rights to assign roles | Grant a scoped role-assignment right, or remove that input |
| Unknown property error from `azapi` | API version does not support the property | Use an API version that does, and plan again |
| Destroy removed resources nobody expected | Resource group deleted with unmanaged contents | Review `DELETE_CONTAINER` findings; keep the provider's safe default |
