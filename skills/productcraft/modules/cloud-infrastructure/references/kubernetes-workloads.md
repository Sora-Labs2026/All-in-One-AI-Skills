# Kubernetes workloads: manifests that survive production

Read this when you write or review Kubernetes manifests (Deployments, StatefulSets, Jobs, Services, Ingress or Gateway routes, NetworkPolicies, RBAC, autoscalers, storage), set resources and probes, or schedule GPU workloads. Packaging and delivery (Helm, Kustomize, GitOps, secrets in Git, operators) are in `kubernetes-delivery.md`; debugging is in `kubernetes-troubleshooting.md`.

Check the cluster version (`kubectl version`) and the API versions it serves (`kubectl api-resources`) before writing manifests; features graduate and old APIs are removed between minor versions.

## Before touching a cluster

- Confirm the context: `kubectl config current-context` and the namespace. Many accidents are the right command on the wrong cluster.
- Validate without changing anything: `kubeconform -strict -summary` (schema), `kubectl apply --dry-run=server -f ...` (admission and defaults, needs read access), `kubectl diff -f ...` (what would change).
- `kubectl apply`, `delete`, `scale`, `rollout restart`, `drain` and `helm install|upgrade|uninstall` change the cluster. Hand them over with the diff, or run them only with the user's go-ahead. Production clusters managed by GitOps change through Git, not `kubectl`.

## A Deployment with the essentials

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders
  namespace: shop
  labels: { app.kubernetes.io/name: orders, app.kubernetes.io/part-of: shop }
spec:
  replicas: 3
  revisionHistoryLimit: 5
  selector:
    matchLabels: { app.kubernetes.io/name: orders }
  strategy:
    rollingUpdate: { maxUnavailable: 0, maxSurge: 1 }
  template:
    metadata:
      labels: { app.kubernetes.io/name: orders }
    spec:
      serviceAccountName: orders
      automountServiceAccountToken: false        # enable only if the app calls the Kubernetes API
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        seccompProfile: { type: RuntimeDefault }
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector: { matchLabels: { app.kubernetes.io/name: orders } }
      containers:
        - name: app
          image: registry.example.com/shop/orders@sha256:<digest>   # immutable reference
          ports: [{ name: http, containerPort: 8080 }]
          resources:
            requests: { cpu: 250m, memory: 256Mi }
            limits: { memory: 256Mi }                                # memory limit = request; see below on CPU
          readinessProbe:
            httpGet: { path: /ready, port: http }
            periodSeconds: 5
          livenessProbe:
            httpGet: { path: /healthz, port: http }
            periodSeconds: 10
            failureThreshold: 3
          startupProbe:
            httpGet: { path: /healthz, port: http }
            periodSeconds: 5
            failureThreshold: 30                                     # up to 150 s to start
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          volumeMounts: [{ name: tmp, mountPath: /tmp }]
      volumes: [{ name: tmp, emptyDir: {} }]
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: orders, namespace: shop }
spec:
  minAvailable: 2
  selector:
    matchLabels: { app.kubernetes.io/name: orders }
```

### Resources

- **Requests** drive scheduling and autoscaling; set them from measured usage (p90 to p95 over a representative week), not guesses.
- **Memory limit equal to the request** avoids surprise OOM kills when a node is under pressure. A container over its memory limit is killed (exit code 137, `OOMKilled`).
- **CPU limits** cause throttling even when the node has idle CPU. Many teams set CPU requests and no CPU limit for latency-sensitive services; others need limits for fairness or licensing. Follow the cluster's policy (a LimitRange may impose one) and decide per workload.
- Language runtimes must see the container limits: recent JVMs, Node.js and Go read cgroup limits, but heap and thread-pool settings may still need explicit values.

### Probes

- **Readiness** removes a pod from Service endpoints; it may check critical dependencies with short timeouts.
- **Liveness** restarts the container; it must check only the process itself. A liveness probe that calls the database restarts every pod during a database outage and turns a dependency failure into a full outage.
- **Startup** probes protect slow starters from liveness kills; prefer them over long `initialDelaySeconds`.
- Handle `SIGTERM`: stop accepting work, finish in-flight requests within the grace period, exit. Readiness should fail as shutdown begins.

### Availability

- At least two replicas, spread across zones with `topologySpreadConstraints`, and a PodDisruptionBudget so node drains and upgrades keep enough pods. A PDB that allows zero disruptions blocks node maintenance entirely; avoid `maxUnavailable: 0` with one replica.
- `maxUnavailable: 0` with `maxSurge: 1` gives zero-downtime rollouts at the cost of one extra pod during the rollout.

## Security baseline

- Enforce Pod Security Admission at the namespace: `pod-security.kubernetes.io/enforce: restricted` (or `baseline` where a workload truly needs more), with `warn` and `audit` labels to preview stricter levels. PodSecurityPolicy was removed in 1.25.
- One ServiceAccount per workload, no token mounted unless needed, and RBAC Roles scoped to a namespace with the exact verbs and resources used. ClusterRoles and `cluster-admin` bindings are IAM changes that need explicit approval.
- On managed clusters, map ServiceAccounts to cloud identities (EKS Pod Identity or IRSA, AKS Workload Identity, GKE Workload Identity Federation) instead of node credentials or stored keys.
- **NetworkPolicy:** start with default deny for ingress (and egress where the CNI enforces it) per namespace, then allow specific flows, including DNS egress to kube-system. Policies do nothing unless the CNI enforces them; check which one the cluster runs.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: default-deny, namespace: shop }
spec:
  podSelector: {}
  policyTypes: [Ingress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: orders-from-gateway, namespace: shop }
spec:
  podSelector: { matchLabels: { app.kubernetes.io/name: orders } }
  ingress:
    - from:
        - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: gateway } }
      ports: [{ port: http }]
```

- Images by digest from a trusted registry; admission policy (Kyverno, Gatekeeper or the built-in ValidatingAdmissionPolicy) can require signatures, registries, resources and non-root.
- **Secrets** are base64-encoded, not encrypted. Enable encryption at rest for the API server (managed clusters offer KMS integration), restrict `get` and `list` on Secrets, and source them from a secret manager (External Secrets Operator or the Secrets Store CSI driver). Never commit plain Secret manifests (`kubernetes-delivery.md`).

## Configuration

- ConfigMaps for non-secret settings; mounted files update in place, environment variables do not (pods need a restart). Add a checksum annotation of the config to the pod template so a config change rolls the Deployment.
- Keep environment-specific values out of the base manifests (Kustomize overlays or Helm values).

## Traffic

- `ClusterIP` Services inside the cluster; expose externally through one entry point: a Gateway API implementation (`Gateway` and `HTTPRoute`, the successor to Ingress) or an Ingress controller. The community ingress-nginx controller reached end of maintenance in 2026; plan new work on Gateway API and migrate existing Ingresses deliberately, checking the current status of whichever controller the cluster uses.
- `type: LoadBalancer` creates a cloud load balancer per Service, which costs money and may be internet-facing by default; set the provider's internal annotation when it should be private.

## Scaling

- **HPA** (`autoscaling/v2`) on CPU, memory or custom metrics; it needs requests to be set and a metrics source. Set `minReplicas` for availability and `behavior` to slow scale-down and avoid flapping.
- **VPA** in recommendation mode is a good way to learn requests; do not let VPA and HPA act on the same CPU or memory metric.
- **Event-driven scaling** (KEDA) scales on queue length or lag, including to zero for workers.
- **Node autoscaling** (Cluster Autoscaler or Karpenter on AWS) adds nodes only for pending pods; PDBs and large requests decide how well it packs and drains.

## Stateful workloads and storage

- Prefer managed databases. When state must live in the cluster, use a StatefulSet with `volumeClaimTemplates`, a headless Service, a PDB, and an operator that knows the software's failover and backup.
- Choose the StorageClass deliberately: `reclaimPolicy: Retain` for data you cannot lose (the default `Delete` removes the disk with the claim), `volumeBindingMode: WaitForFirstConsumer` so volumes are created in the pod's zone, `allowVolumeExpansion: true`.
- Back up volumes and cluster objects (VolumeSnapshots, Velero) and test restores.

## Jobs and CronJobs

Set `backoffLimit`, `activeDeadlineSeconds` and `ttlSecondsAfterFinished` on Jobs; on CronJobs set `concurrencyPolicy: Forbid` unless overlapping runs are safe, `startingDeadlineSeconds`, and history limits. Jobs must be idempotent: a pod can run twice.

## GPU workloads

- GPUs are requested as an extended resource in `limits` (`nvidia.com/gpu: 1` with the NVIDIA device plugin or GPU Operator installed). They are not overcommitted; a pod gets whole GPUs unless the cluster offers MIG partitions or time-slicing.
- Put GPU nodes in their own pool with a taint and give GPU pods the matching toleration and node selector, so ordinary pods do not land on expensive nodes.
- Scale GPU pools to zero when idle where the platform supports it; idle GPU nodes are the most expensive waste in most clusters (`gpu-and-serverless-compute.md`).

## Done when

- [ ] Manifests pass `kubeconform` and a server-side dry run, and `kubectl diff` output was shown for the target cluster and namespace.
- [ ] Every container has requests, a memory limit, readiness and (where useful) liveness and startup probes, a non-root security context and an image by digest or immutable tag.
- [ ] Workloads have their own ServiceAccount, scoped RBAC, a PDB, zone spread and a NetworkPolicy.
- [ ] Nothing was applied to a cluster without the user's go-ahead.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| All pods restart when the database blips | Liveness probe checks dependencies | Liveness checks the process only |
| Latency spikes with low average CPU | CPU limit throttling | Raise or remove the CPU limit; check throttling metrics |
| Node drain hangs | PDB allows no disruption | Enough replicas for the PDB, or `maxUnavailable: 1` |
| Data lost after deleting a PVC | StorageClass reclaim policy `Delete` | `Retain` for important data; back up first |
| NetworkPolicy has no effect | CNI does not enforce policies | Use a CNI that does, or a managed policy add-on |
| Rollout never finishes | Readiness never passes or quota blocks the surge pod | `kubectl rollout status`, events, quota (`kubernetes-troubleshooting.md`) |
