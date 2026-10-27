# Cloud cost: estimate, attribute, find waste

Read this when a change adds or resizes cloud resources, the user asks why a bill grew or how to reduce it, you set up budgets or cost alerts, or you review a plan for cost. Prices change and differ by region and agreement; never quote a price from memory as fact. Read current numbers from the provider's pricing pages, calculator or price-list API, and say which region and date they apply to.

## Ground rules

- **Read-only by default.** Cost discovery uses billing exports, cost APIs and describe or list calls. Deleting resources, resizing, changing storage classes and buying commitments all change the user's systems or money. Propose them with evidence; execute only what the user approves, through the normal plan and diff path.
- **Commitments are the owner's decision.** Savings Plans, reserved instances or capacity and committed-use discounts are one- to three-year financial contracts. Present the usage data and the break-even; never purchase or recommend a specific purchase as certain.
- **Cost APIs can cost money.** AWS Cost Explorer API requests are billed per request; use the console or a billing export for exploratory analysis and keep scripted queries few and paginated.
- **Attribute before optimizing.** Without owner and environment tags (or labels) on resources, nobody can say whose spend grew.

## Before a change: estimate

1. List what the change creates or resizes (from the plan, `cdk diff` or the manifest).
2. Identify each resource's price dimensions: hours, requests, GB stored, GB transferred, IOPS, per-node or per-GPU hours.
3. Estimate the usage of each dimension from real traffic numbers the user provides, not invented ones. Mark assumptions.
4. Compute a monthly figure with the provider's calculator or price list, and state region, date and assumptions.
5. For Terraform, a plan-based estimator (for example Infracost in CI) shows the cost difference of each pull request. Check what such a tool sends to its pricing service before running it on private code, and treat its usage-based lines as estimates.

Report the estimate with its biggest driver and the assumption it is most sensitive to.

## The usual cost drivers

| Area | Driver people miss | What to check |
|---|---|---|
| Network | Data processed by NAT gateways; traffic between availability zones; internet egress; inter-region replication | VPC endpoints (gateway endpoints for S3 and DynamoDB carry no data charge); keep chatty services in one zone where availability allows; CDN in front of public content |
| Compute | Idle or oversized instances; dev environments running nights and weekends; old instance generations | Utilization metrics over two to four weeks; schedules for non-production; current-generation and ARM instance types |
| Storage | Unattached volumes; snapshots of deleted instances; AMIs whose snapshots outlive them; old object versions | Lifecycle rules, snapshot retention, deregistering images together with their snapshots |
| Logs and metrics | Log groups with no retention; debug logging left on; high-cardinality custom metrics | Retention on every log group; sampling; metric label budgets (`monitoring-stack.md`) |
| Addresses | Public IPv4 addresses (AWS bills every public IPv4 address hourly since February 2024, attached or not) | Release unused addresses; prefer private subnets with a shared egress path |
| Managed services | Provisioned capacity sized for peak; Multi-AZ or replicas in non-production; idle load balancers | Autoscaling or on-demand modes; single-zone non-production; delete idle load balancers |
| Serverless | Provisioned concurrency left on; very high request volume on per-request services | Remove idle provisioned concurrency; batch requests; compare with a container at steady high load |
| Kubernetes | Requests far above usage; underused nodes; idle GPU nodes | Right-size requests from usage, cluster autoscaling, per-namespace cost allocation (OpenCost) |
| GPUs | Warm pools and minimum replicas; GPUs larger than the model needs | `gpu-and-serverless-compute.md` |

## Finding waste, read-only

AWS examples (the same questions apply to Azure and Google Cloud with their CLIs and Advisor or Recommender services):

```bash
aws sts get-caller-identity                                    # confirm the account first
aws ec2 describe-volumes --filters Name=status,Values=available \
  --query 'Volumes[].{id:VolumeId,gb:Size,created:CreateTime}'  # unattached volumes
aws ec2 describe-addresses --query 'Addresses[?AssociationId==null].PublicIp'   # unassociated Elastic IPs
aws ec2 describe-snapshots --owner-ids self \
  --query 'sort_by(Snapshots,&StartTime)[].[SnapshotId,StartTime,VolumeSize,Description]' --output table   # oldest first; check what uses them
aws logs describe-log-groups \
  --query 'logGroups[?retentionInDays==null].[logGroupName,storedBytes]'   # logs kept forever
aws compute-optimizer get-ec2-instance-recommendations          # only if Compute Optimizer is enabled
```

```bash
az account show                                                 # confirm the subscription
az disk list --query "[?diskState=='Unattached'].{name:name,gb:diskSizeGb,rg:resourceGroup}"
az network public-ip list --query "[?ipConfiguration==null].{name:name,rg:resourceGroup}"
az advisor recommendation list --category Cost
```

```bash
gcloud config list                                              # confirm the project
gcloud compute disks list --filter="-users:*"                   # disks attached to nothing
gcloud recommender recommendations list --project=PROJECT --location=REGION \
  --recommender=google.compute.commitment.UsageCommitmentRecommender   # commitment advice, for the owner to judge
```

For each candidate, find the owner and confirm nothing depends on it (a snapshot behind an image, a volume detached for maintenance, an address in a DNS record) before proposing deletion. Every deletion goes through the stop-check in `../../agent-safety/GUIDE.md`, with a snapshot or backup where the data might matter.

## Attribution and guardrails

- **Tags or labels** on everything: `owner`, `environment`, `service`, `cost-center`. Set them at the provider level in IaC (`default_tags`, Azure Policy inheritance, label defaults) and enforce them with policy. On AWS, user-defined tags appear in billing only after they are activated as cost allocation tags, and only for spend from then on.
- **Billing exports** (AWS Cost and Usage Report or Data Exports, Azure Cost Management exports, Google Cloud billing export to BigQuery) are the source of truth for analysis; dashboards built on them beat ad hoc API calls. Billing data is sensitive: it reveals architecture and business volume.
- **Budgets with alerts** at 50, 80 and 100 percent of forecast, per account or subscription and per team, sent to people who can act. Anomaly detection (AWS Cost Anomaly Detection, Azure cost anomaly alerts) catches spikes that budgets miss.
- **Sandbox accounts** for experiments and tests get small budgets and, where available, automated cleanup of expired resources.

## Reducing cost safely

1. Remove what is unused (with the owner's confirmation and a backup).
2. Turn off or scale to zero what is idle on a schedule (non-production nights and weekends).
3. Right-size from measured utilization, one service at a time, watching latency and error objectives (`sre-practice.md`).
4. Move storage to the right class with lifecycle rules (infrequent access, archive), after checking retrieval costs and minimum storage durations.
5. Use spot or preemptible capacity for interruptible work (batch, CI runners, stateless workers with checkpoints), never for the only copy of a stateful service.
6. Only then consider commitments, sized to the stable baseline that remains, as the owner's decision.

Re-measure after each step with the same method and period, and report the before and after with the date range.

## Done when

- [ ] Any new or resized resource has a written estimate with region, date, drivers and assumptions.
- [ ] Every finding names the resource, its owner (or "unknown"), the evidence and the estimated saving with its basis.
- [ ] No deletion, resize, storage-class change or purchase happened without the user's explicit approval.
- [ ] Tags or labels needed for attribution are in IaC, and budgets or alerts exist for the accounts touched.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Savings claimed, bill unchanged | Measured over different periods, or usage moved elsewhere | Same date range and method before and after |
| Deleted volume turned out to be needed | Owner and dependencies not checked | Snapshot first; confirm with the owner |
| Cost report shows "untagged" for most spend | Tags missing or not activated for billing | Default tags in IaC; activate cost allocation tags |
| Cost Explorer charges climbing | Scripted API polling | Use exports; cache results |
| Storage tiering raised the bill | Retrieval fees and minimum storage durations on cold tiers | Check access patterns before moving data |
