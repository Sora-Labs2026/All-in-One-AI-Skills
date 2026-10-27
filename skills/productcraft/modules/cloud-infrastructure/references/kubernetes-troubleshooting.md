# Kubernetes troubleshooting

Read this when pods are Pending, crash-looping, failing image pulls, getting OOM-killed, not receiving traffic, failing DNS lookups or storage mounts, or a rollout is stuck. The general debugging loop (reproduce, isolate, hypothesize, test, fix at the source) is in `../../engineering-workflow/references/debugging.md`; this file supplies the Kubernetes evidence.

Diagnosis is read-only: `get`, `describe`, `logs`, `events`, `top`, `auth can-i`. Anything that changes the cluster (deleting pods, restarting, scaling, editing objects, `kubectl debug` with ephemeral containers, `cordon` and `drain`) needs the user's go-ahead, and in GitOps-managed clusters a manual change will be reverted; fix it in Git. In an active incident, follow `sre-practice.md`: mitigate first, then diagnose.

## First five commands

```bash
kubectl config current-context                    # right cluster?
kubectl get pods -n NS -o wide                    # status, restarts, node, age
kubectl describe pod POD -n NS                    # events at the bottom tell most stories
kubectl get events -n NS --sort-by=.lastTimestamp | tail -30
kubectl logs POD -n NS -c CONTAINER --previous    # logs of the crashed instance, not the new one
```

Then read the owning object: `kubectl rollout status deploy/NAME -n NS`, `kubectl describe deploy/NAME`, `kubectl get rs -n NS` (old and new ReplicaSets during a rollout).

## By symptom

| Status or symptom | Look at | Usual causes |
|---|---|---|
| `Pending` | `describe pod` events: "FailedScheduling" with reasons | Requests larger than any node; quota exceeded (`kubectl describe quota`); taints without tolerations; node selector or affinity matches nothing; PVC unbound; zone mismatch between volume and nodes |
| `ContainerCreating` for minutes | Events | Volume attach or mount failing; Secret or ConfigMap missing; CNI out of IP addresses |
| `ImagePullBackOff`, `ErrImagePull` | Events | Typo in name, tag or digest; private registry without `imagePullSecrets` or node permissions; registry rate limits; architecture mismatch (`exec format error` shows later) |
| `CrashLoopBackOff` | `logs --previous`, exit code in `describe` | App error at startup; missing configuration or secret; failing dependency at boot; wrong command or entrypoint; liveness probe killing a slow starter |
| `OOMKilled`, exit code 137 | `describe` last state, memory metrics | Memory limit below real usage; leak; runtime heap not sized to the limit |
| `Running` but not `Ready` | Readiness probe events, endpoint list | Probe path or port wrong; dependency check in readiness failing; app listening on 127.0.0.1 instead of 0.0.0.0 |
| Service gets no traffic | `kubectl get endpointslices -n NS -l kubernetes.io/service-name=SVC` | Selector does not match pod labels; `targetPort` name or number wrong; pods not ready; NetworkPolicy blocking |
| DNS failures | `nslookup` from a debug pod; CoreDNS logs and load | Egress NetworkPolicy without DNS allowed; CoreDNS overloaded; `ndots` causing many lookups for external names |
| Rollout stuck | `rollout status`, new ReplicaSet's pods | New pods never ready; quota or capacity blocks the surge pod; PDB plus `maxUnavailable: 0` with too few replicas |
| Node `NotReady` or pods evicted | `describe node`: conditions and pressure | Disk or memory pressure; kubelet or runtime down; node lost |
| `Forbidden` from the API | `kubectl auth can-i VERB RESOURCE --as=system:serviceaccount:NS:SA -n NS` | Missing Role or RoleBinding; binding in the wrong namespace |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Process exited normally; for a long-running service that is itself a bug (wrong command, process daemonized) |
| 1 or other small numbers | Application error; read the logs |
| 126, 127 | Command not executable or not found: wrong entrypoint, missing binary, shell script line endings |
| 137 | SIGKILL: OOM kill or killed after the grace period |
| 139 | Segmentation fault |
| 143 | SIGTERM: normal shutdown, or a liveness probe failure restarting the container |

## Getting a shell without changing the workload

- `kubectl exec -it POD -c CONTAINER -- sh` works only if the image has a shell. Exec into production pods only with approval; commands run with the app's identity and data access.
- For distroless images, an ephemeral debug container shares the pod's namespaces: `kubectl debug -it POD --image=busybox:1.36 --target=CONTAINER`. It adds a container to the running pod spec (it cannot be removed until the pod is replaced), so it needs approval.
- `kubectl debug node/NODE -it --image=busybox:1.36` gives a privileged pod on the node with the host filesystem at `/host`. It is effectively root on the node; use only with explicit approval.
- A throwaway pod for network tests: `kubectl run nettest -n NS --rm -it --image=busybox:1.36 --restart=Never -- sh`, then `nslookup SVC`, `wget -qO- http://SVC:PORT/ready`. It creates and deletes a pod, so ask first in shared clusters. Use a pinned image you trust.

## Resource evidence

```bash
kubectl top pods -n NS --containers          # needs metrics-server
kubectl describe node NODE | sed -n '/Allocated resources/,/Events/p'
kubectl get pod POD -n NS -o jsonpath='{.status.containerStatuses[*].lastState}'
```

CPU throttling and memory working set over time come from the monitoring stack (`container_cpu_cfs_throttled_periods_total`, `container_memory_working_set_bytes`); see `monitoring-stack.md`.

## Writing up

Record the symptom, the evidence that located the cause (event lines, log lines without secrets, metric graphs), the cause, the fix and how it was verified, and what would have caught it earlier (an alert, a probe, a test). For incidents, this feeds the postmortem (`sre-practice.md`).

## Done when

- [ ] The cause is backed by evidence from events, logs or metrics, not inferred from the symptom alone.
- [ ] Every cluster-changing step (restart, delete, scale, debug container, drain) was approved first, and GitOps-managed fixes went through Git.
- [ ] The fix was verified with the same command that showed the problem (pod ready, endpoints present, rollout complete).
- [ ] Logs and outputs shared in the report contain no secrets or personal data.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Logs show nothing useful | Reading the new container, not the crashed one | `kubectl logs --previous` |
| Fixing a pod by hand "worked", then reverted | GitOps self-heal or the Deployment recreated it | Change the source in Git or the owning object |
| Deleting pods to "fix" a crash loop | Treats the symptom; the new pod crashes too | Find the cause in logs and events first |
| Endpoints empty but pods running | Label selector mismatch | Compare `kubectl get pods --show-labels` with the Service selector |
