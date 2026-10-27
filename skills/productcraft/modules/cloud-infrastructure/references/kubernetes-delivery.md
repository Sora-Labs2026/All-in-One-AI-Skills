# Kubernetes delivery: Helm, Kustomize, GitOps, secrets and operators

Read this when you write or change a Helm chart or Kustomize overlay, set up or change Argo CD or Flux, keep secrets for Kubernetes in Git, add progressive delivery, consider a service mesh, or consider writing an operator. Manifest content is in `kubernetes-workloads.md`.

## Helm or Kustomize

- **Kustomize** (built into `kubectl`): plain YAML with overlays per environment. Best for your own services when variation is small.
- **Helm**: templated, versioned packages with dependencies and release history. Best for distributing software to others or consuming third-party software. Helm 4 was released in late 2025 with changed defaults and plugin handling; check `helm version` and follow the version's migration notes.
- Both together is common: render a third-party chart with Helm, patch it with Kustomize.

## Helm charts that review well

- `Chart.yaml` with semantic `version` (the chart) and `appVersion` (the software). Bump the chart version on every change.
- `values.yaml` holds documented, safe defaults; add `values.schema.json` so `helm install` and `helm lint` reject wrong types and unknown keys.
- Templates use helpers for names and labels (`_helpers.tpl`), quote strings (`{{ .Values.x | quote }}`), `required` for mandatory values, and `toYaml ... | nindent` for blocks. Add a checksum of rendered ConfigMaps to the pod template annotations so config changes roll pods.
- No secrets in `values.yaml`. Reference existing Secrets by name, or render them from an external secret store.
- Hooks (`pre-install`, `pre-upgrade`) for migrations run outside the normal rollout; give them `hook-delete-policy`, idempotent behavior and a timeout, or run migrations as a separate pipeline step (`../../engineering-practices/references/data-and-migrations.md`).

```bash
helm lint ./chart --strict
helm template app ./chart -f values-prod.yaml | kubeconform -strict -summary
helm unittest ./chart                      # helm-unittest plugin, if the project uses it
helm diff upgrade app ./chart -f values-prod.yaml -n shop   # helm-diff plugin: what an upgrade would change
```

- `helm upgrade --install` and `helm uninstall` change the cluster; hand them over with the diff. `helm rollback` is itself a change and needs approval too.
- Distribute charts through an OCI registry (`helm push chart.tgz oci://registry.example.com/charts`) and pin consumed charts by exact version; sign them where the registry supports it.
- Third-party charts are dependencies: read their default values (`helm show values`), pin the version, and check what RBAC and CRDs they install (`../../code-security-review/references/supply-chain-review.md`).

## Kustomize layout

```
deploy/
  base/            kustomization.yaml, deployment.yaml, service.yaml
  overlays/
    staging/       kustomization.yaml (namespace, replicas, image tag, patches)
    production/
```

```bash
kubectl kustomize deploy/overlays/production | kubeconform -strict -summary
kubectl diff -k deploy/overlays/production
```

Set images with `images:` entries (name, `newName`, `digest`) rather than editing the base, and keep patches small and named after their purpose.

## GitOps

In GitOps a controller in the cluster (Argo CD or Flux) continuously applies what is in Git. Git becomes the change path for production: changes are pull requests, approvals are reviews, rollback is a revert.

- Separate the application repository (code, image builds) from the environment configuration repository or directory (what runs where). CI builds and pushes an image, then opens a pull request that bumps the digest in the configuration.
- Per-environment directories or branches with promotion by pull request; production changes require review.
- Argo CD `Application` (or `ApplicationSet` for many clusters or services) with `syncPolicy.automated`; enable `prune` only when you are sure everything in the target namespace is declared in Git, because pruning deletes undeclared resources. `selfHeal` reverts manual changes, which is the point, but surprises people who `kubectl edit` in an incident; agree the emergency procedure in advance.
- Restrict what each Argo CD project may deploy (`AppProject` allowed repositories, destinations, cluster-scoped resource allow-lists). Flux uses `Kustomization` and `HelmRelease` objects with a service account per tenant for the same purpose.
- The agent's role: edit the configuration in a branch, show the rendered diff, open a pull request when asked. Do not trigger syncs, disable auto-sync, or change sync policies on production applications without the user's go-ahead.

## Secrets with GitOps

Never commit a plain Secret, even base64-encoded. Choose one approach:

| Approach | How it works | Watch out for |
|---|---|---|
| External Secrets Operator | Syncs from AWS Secrets Manager, Azure Key Vault, Google Secret Manager, Vault into Kubernetes Secrets | The operator's cloud identity becomes highly privileged; scope it per namespace |
| Secrets Store CSI driver | Mounts secrets from the store as files at pod start | Rotation needs the sync or restart behavior configured |
| SOPS (with age or a cloud KMS) | Encrypted files in Git, decrypted by Flux or a plugin at apply time | Key distribution; the decryption key must never be committed |
| Sealed Secrets | Encrypted for one cluster's controller key | Back up the controller key; resealing on cluster rebuild |

If a plain secret was ever committed, treat it as exposed: rotation first, then history cleanup (`../../launchguard/references/safe-operations.md`).

## Progressive delivery

Argo Rollouts and Flagger replace a Deployment's all-at-once rollout with canary or blue-green steps that check metrics (error rate, latency) and roll back automatically. Define the analysis from the service objective (`sre-practice.md`), test that a bad version is actually rolled back in staging, and keep the step weights and pause durations in Git. The rollout plan template in `../../engineering-practices/references/ci-and-release.md` applies.

## Service mesh

A mesh (Istio, Linkerd, or the mesh features of some CNIs) adds mutual TLS between workloads, traffic splitting and retries in configuration, and uniform request metrics. Adopt one for a concrete need (encryption and identity between services, canary traffic shifting, many services without consistent telemetry), not by default: it adds a control plane to upgrade, latency and resources per pod (sidecars, or a per-node proxy in Istio's ambient mode), and a new failure domain. Keep NetworkPolicies even with a mesh. Retries configured in the mesh count as a retry layer (`../../engineering-practices/references/resilience.md`): do not stack them on top of client retries. Installing or upgrading a mesh is cluster-wide; ask first.

## Operators and CRDs

- Write an operator only when a piece of software needs ongoing, domain-specific automation (failover, backup, scaling decisions) that plain controllers and Helm cannot express. Most applications do not; a Deployment and a Job do the work.
- Use Kubebuilder or the Operator SDK on controller-runtime. Reconcile loops must be idempotent and level-based (compute desired state from the object, not from the event), set `status` conditions and `observedGeneration`, use finalizers only for external cleanup and always remove them, and requeue with backoff on errors.
- Version CRDs (`v1alpha1` to `v1`) with conversion webhooks when the schema changes, and validate with OpenAPI schemas and CEL rules.
- Grant the operator's ServiceAccount only the verbs and resources it reconciles. Test with envtest (a real API server without nodes) before any cluster.
- Installing CRDs and operators is cluster-scoped: ask before installing them, and remember that deleting a CRD deletes every object of that kind.

## Several clusters and backups

- Manage many clusters from Git with Argo CD ApplicationSets or Flux, and keep clusters as similar as possible; per-cluster drift becomes per-cluster incidents.
- Cluster API or the cloud's managed node groups make clusters reproducible; treat clusters as replaceable and keep state outside them.
- Back up cluster objects and volumes (Velero or the platform's backup service), store backups outside the cluster's account, and rehearse a restore into a fresh cluster.

## Done when

- [ ] Charts pass `helm lint --strict` and render through `kubeconform`; overlays render through `kubectl kustomize`.
- [ ] No plain secrets in Git; the chosen secret approach is documented with its key or identity ownership.
- [ ] Production changes go through a reviewed pull request, and the rendered diff was shown.
- [ ] No sync, install, upgrade, rollback or CRD change ran against a cluster without the user's go-ahead.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Config change did not reach running pods | Environment variables from a ConfigMap; no rollout triggered | Checksum annotation on the pod template |
| Argo CD deleted a resource someone created by hand | `prune` enabled on a shared namespace | Declare it in Git or exclude it; disable prune for shared namespaces |
| Helm upgrade fails with "cannot patch" on an immutable field | Selector or other immutable field changed | Keep selectors stable; plan a replacement with approval |
| Secrets readable by every developer | Plain Secrets in Git or broad `get secrets` RBAC | External store plus scoped RBAC; rotate what leaked |
| Operator loops forever or leaves objects stuck deleting | Non-idempotent reconcile, finalizer never removed | Level-based reconcile; remove the finalizer after cleanup |
