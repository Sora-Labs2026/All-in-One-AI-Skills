# Terraform provider development with the Plugin Framework

Read this when you scaffold a new Terraform provider, add a resource, data source, ephemeral resource, function or action to one, write or run acceptance tests (`TestAcc*`, `TF_ACC=1`), or debug "inconsistent result" and perpetual-diff errors.

New providers and new resources should use the Terraform Plugin Framework (`github.com/hashicorp/terraform-plugin-framework`), not SDKv2. An existing SDKv2 provider can move resource by resource behind `terraform-plugin-mux`. Check `go.mod` for the framework and `terraform-plugin-testing` versions before writing code; interfaces gain methods between minor versions.

## Scaffold

1. Confirm you are not already inside a provider repository; if you are, ask before creating another.
2. Name the repository `terraform-provider-<name>`, run `go mod init`, and add the framework: `go get github.com/hashicorp/terraform-plugin-framework@latest` (then pin what `go.mod` records).
3. Start from HashiCorp's framework scaffolding template if the user agrees; otherwise the minimum is a `main.go`, an `internal/provider` package and a test file.

```go
// main.go
package main

import (
	"context"
	"flag"
	"log"

	"github.com/hashicorp/terraform-plugin-framework/providerserver"

	"example.com/terraform-provider-widgets/internal/provider"
)

var version = "dev" // overwritten at release time with -ldflags

func main() {
	debug := flag.Bool("debug", false, "start the provider for a debugger such as delve")
	flag.Parse()

	err := providerserver.Serve(context.Background(), provider.New(version), providerserver.ServeOpts{
		Address: "registry.terraform.io/acme/widgets", // must match the published source address
		Debug:   *debug,
	})
	if err != nil {
		log.Fatal(err)
	}
}
```

4. `go mod tidy`, `go build ./...`, `go vet ./...`, `go test ./...` (unit tests only; acceptance tests skip without `TF_ACC`).
5. To try the binary locally, point Terraform at it with `dev_overrides` in a project-local CLI config file (`TF_CLI_CONFIG_FILE=./dev.tfrc`) rather than editing the user's `~/.terraformrc`. With overrides active, skip `terraform init` and run `plan` directly.

## Anatomy of a resource

```go
type widgetModel struct {
	ID   types.String `tfsdk:"id"`
	Name types.String `tfsdk:"name"`
	Size types.Int64  `tfsdk:"size"`
}

var (
	_ resource.Resource                = &widgetResource{}
	_ resource.ResourceWithConfigure   = &widgetResource{}
	_ resource.ResourceWithImportState = &widgetResource{}
)

func (r *widgetResource) Schema(_ context.Context, _ resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Manages a widget.",
		Attributes: map[string]schema.Attribute{
			"id": schema.StringAttribute{
				Computed:      true,
				PlanModifiers: []planmodifier.String{stringplanmodifier.UseStateForUnknown()},
			},
			"name": schema.StringAttribute{
				Required:      true,
				PlanModifiers: []planmodifier.String{stringplanmodifier.RequiresReplace()},
				Validators:    []validator.String{stringvalidator.LengthBetween(1, 63)},
			},
			"size": schema.Int64Attribute{
				Optional: true,
				Computed: true,                            // a Default requires Computed
				Default:  int64default.StaticInt64(1),
			},
		},
	}
}

func (r *widgetResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	var state widgetModel
	resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
	if resp.Diagnostics.HasError() {
		return
	}
	w, err := r.client.GetWidget(ctx, state.ID.ValueString())
	if errors.Is(err, widgets.ErrNotFound) {
		resp.State.RemoveResource(ctx) // gone outside Terraform: the next plan recreates it
		return
	}
	if err != nil {
		resp.Diagnostics.AddError("Reading widget failed", err.Error())
		return
	}
	state.Name = types.StringValue(w.Name)
	state.Size = types.Int64Value(w.Size)
	resp.Diagnostics.Append(resp.State.Set(ctx, &state)...)
}

func (r *widgetResource) ImportState(ctx context.Context, req resource.ImportStateRequest, resp *resource.ImportStateResponse) {
	resource.ImportStatePassthroughID(ctx, path.Root("id"), req, resp)
}
```

Rules for the CRUD methods:

- **Create** reads the plan, calls the API, waits until the object is usable, and sets every attribute in state, including all computed ones. An attribute left unknown after apply is an error.
- **Read** refreshes every attribute from the API and removes the resource from state on "not found". Never return an error for a deleted object.
- **Update** applies only what changed (compare plan and state) and writes the new state. Attributes the API cannot change in place get `RequiresReplace`.
- **Delete** treats "not found" as success and waits until deletion has finished when the API is asynchronous.
- **Configure** returns early when `req.ProviderData` is nil (it is called before the provider is configured) and type-checks the client.
- Long operations honor `ctx` cancellation and user-configurable timeouts (`terraform-plugin-framework-timeouts`). Retry only transient API errors, with backoff (`../../engineering-practices/references/resilience.md`).
- Mark secrets `Sensitive: true`. For values that should never reach state, use write-only attributes (Terraform 1.11+) or an ephemeral resource (1.10+).

### Schema choices that avoid perpetual diffs

| Situation | Choose |
|---|---|
| Server-generated, stable value (ID, creation time) | `Computed` with `UseStateForUnknown()`, so plans do not show "(known after apply)" on every update |
| Optional with a server-side default | `Optional` + `Computed`, plus a `Default` only if the default is fixed and documented |
| API normalizes the value (JSON whitespace, case, trailing slash) | A custom type with semantic equality (for JSON, the `jsontypes.Normalized` type), so equivalent values do not diff |
| Unordered collection | `SetAttribute` or `SetNestedAttribute`, not a list |
| Field that cannot change in place | `RequiresReplace()`, or `RequiresReplaceIf` with a documented condition |

"Provider produced inconsistent result after apply" means the value written to state differs from a known planned value. Fix it at the source: return exactly what the plan said, normalize with a custom type, or make the attribute computed. Never paper over it by copying the plan into state without reading the API.

## Newer provider capabilities

Check the Terraform and framework versions before using these; each needs both sides to support it.

- **Provider-defined functions** (Terraform 1.8+): pure computations exposed as `provider::<name>::<function>`.
- **Ephemeral resources** (1.10+): short-lived values such as tokens that are never stored in state or plan.
- **Write-only attributes** (1.11+): accepted on create or update, never persisted.
- **Resource identity** (1.12+): structured identity used by `import` blocks with `identity` and by list resources.
- **List resources** (1.14+): back the `list` blocks used by `terraform query`; required for Terraform Search support (`terraform-import.md`).
- **Actions** (1.14+): imperative operations (invoke a function, invalidate a cache, run a command) triggered from a resource's `lifecycle { action_trigger { ... } }` or invoked directly from the CLI. An action has a schema and an `Invoke` method, no state. Make it idempotent, report progress for long operations, honor cancellation and a configurable timeout, and document its side effects plainly; the lifecycle events available depend on the Terraform version. Running an action is a production change like an apply.

## Acceptance tests

Acceptance tests run real Terraform against the real API through `github.com/hashicorp/terraform-plugin-testing`. They create billable resources in whatever account the credentials point to, so run them only with the user's go-ahead, in a dedicated test account.

```go
var testAccProviders = map[string]func() (tfprotov6.ProviderServer, error){
	"widgets": providerserver.NewProtocol6WithError(provider.New("test")()),
}

func TestAccWidget_basic(t *testing.T) {
	name := acctest.RandomWithPrefix("tfacc")
	resource.Test(t, resource.TestCase{
		PreCheck:                 func() { testAccPreCheck(t) }, // fail fast when credentials are missing
		ProtoV6ProviderFactories: testAccProviders,
		CheckDestroy:             testAccCheckWidgetDestroyed,
		Steps: []resource.TestStep{
			{
				Config: testAccWidgetConfig(name, 2),
				ConfigStateChecks: []statecheck.StateCheck{
					statecheck.ExpectKnownValue("widgets_widget.test", tfjsonpath.New("size"), knownvalue.Int64Exact(2)),
				},
			},
			{
				Config: testAccWidgetConfig(name, 3),
				ConfigPlanChecks: resource.ConfigPlanChecks{
					PreApply: []plancheck.PlanCheck{
						plancheck.ExpectResourceAction("widgets_widget.test", plancheck.ResourceActionUpdate),
					},
				},
			},
			{ResourceName: "widgets_widget.test", ImportState: true, ImportStateVerify: true},
		},
	})
}
```

Cover for each resource: create with required arguments only, every updatable argument (and that it updates in place rather than replaces), import with `ImportStateVerify`, a "disappears" case (delete the object out of band, expect a non-empty plan, no error), and `CheckDestroy` confirming the API no longer returns it. After each apply step the framework plans again and fails on a non-empty plan, which catches perpetual diffs.

Running them:

```bash
go test -c -o /dev/null ./internal/provider                     # compile tests without running
TF_ACC=1 go test ./internal/provider -run '^TestAccWidget_basic$' -count=1 -timeout 60m
TF_ACC=1 TF_LOG=DEBUG go test ./internal/provider -run '^TestAccWidget_basic$' -count=1 -v   # when diagnosing
```

- `-count=1` defeats Go's test cache so a cached pass is not mistaken for a fresh run. Start without `-v`; add verbose output and `TF_LOG=DEBUG` only when diagnosing, and never paste logs that contain tokens.
- When a test needs credentials it does not have, name the environment variables the provider reads and let the user set them in their own shell (`../../agent-safety/references/guided-setup.md`). Never ask for the values in the chat.
- terraform-plugin-testing can keep a failed test's working directory and pin the Terraform binary it uses; see its environment variables in the package documentation for the installed version.
- **Prove the test can fail.** A passing acceptance test may assert nothing useful. Change one expected value in a check, run the test, see it fail, then restore the value and confirm it passes again. Report the result.
- Sweepers (`resource.AddTestSweepers` with `go test -sweep=<region>`) delete every resource matching a test prefix in the account. They are destructive by design: run them only with approval, only in the test account, and only with a prefix nothing else uses.

## Logging, docs and release

- Log with `tflog` (`terraform-plugin-log`); enable with `TF_LOG_PROVIDER=DEBUG`. Mask secret fields (`tflog.MaskFieldValuesWithFieldKeys`) and never log request bodies wholesale.
- Generate docs from schema descriptions and `examples/` with `tfplugindocs` (wire it to `go generate`) and commit the output; every resource needs an example and an import section.
- Publishing to the Terraform Registry requires a public `terraform-provider-<name>` repository, a GoReleaser build that signs checksums with a GPG key registered with the Registry, and a `terraform-registry-manifest.json` declaring the protocol version (`6.0` for the framework). Creating a release is publishing: prepare the tag and the configuration, and let the user push it.

## Done when

- [ ] `go build`, `go vet`, unit tests and `go test -c` succeed; `tfplugindocs` output is current.
- [ ] Each resource implements Read with not-found removal, import, and sets every computed attribute on create.
- [ ] Acceptance tests cover create, in-place update, import and disappears, ran with the user's approval in a test account, and at least one was shown to fail when its expectation was changed.
- [ ] No credentials or tokens appear in code, test fixtures, logs or the report.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| "Provider produced inconsistent result after apply" | State differs from a known planned value | Return what was planned, add semantic equality, or make it computed |
| Every plan shows "(known after apply)" for `id` | Missing `UseStateForUnknown` | Add the plan modifier to stable computed attributes |
| "Value Conversion Error" reading plan or state | Model field type does not match the schema (`types.String` versus `types.List`) | Align struct field types and `tfsdk` tags with the schema |
| Default rejected at schema validation | `Default` set without `Computed: true` | Mark the attribute computed |
| Acceptance test passes with no resources created | Missing `TF_ACC=1`, so the test was skipped | Check the output for "skipped"; run with `TF_ACC=1` and `-count=1` |
| Error after resource deleted by hand | Read returns an error on not found | Remove the resource from state instead |
