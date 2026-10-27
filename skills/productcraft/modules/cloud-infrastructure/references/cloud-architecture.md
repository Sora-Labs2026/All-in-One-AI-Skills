# Cloud architecture: design, accounts, networks, recovery and migration

Read this when you design a new system on AWS, Azure or Google Cloud, review an existing architecture, plan disaster recovery, set up or change account, subscription or project structure, plan a migration, or answer a multi-cloud question.

Architecture work produces decisions and documents, not deployments. Write the decision record (`../../engineering-practices/references/docs-and-decisions.md`), the diagram and the cost estimate; changes to organization-wide settings (guardrail policies, identity federation, network hubs) are the owner's to approve and apply.

## Start from requirements, not services

Ask, and do not invent the answers:

- Who uses it, from where, and how traffic varies over a day and a year.
- What data it holds, how sensitive it is, and where it must stay (residency, sector rules).
- The availability objective, and the recovery time (RTO) and recovery point (RPO) the business accepts for a regional outage and for data corruption.
- Compliance obligations, budget range, the team's skills and on-call capacity, and what already exists (accounts, networks, identity provider, CI).

Write assumptions down where the user has no answer yet, and mark them for review.

## Review lenses

The providers' well-architected frameworks group the same concerns into pillars: operational excellence, security, reliability, performance efficiency, cost optimization and (on AWS and Google Cloud) sustainability. Use them as a checklist of questions for each component: how it is deployed and observed, who can reach it, how it fails and recovers, how it scales, what it costs. They are lenses, not a certification.

## Defaults that hold up

- **Managed over self-run** when the team is small: managed databases, queues and container platforms remove patching, backups and failover work. Self-run only for a clear reason (cost at scale, a missing feature, portability requirement) that the team can staff.
- **One region, several availability zones** is the default for production. Multi-region adds cost and complexity; adopt it when RTO, latency for distant users or residency demand it.
- **Compute choice:** functions for spiky, event-driven, short tasks; containers on a managed platform (ECS, Cloud Run, Azure Container Apps, managed Kubernetes) for long-running services; virtual machines for software that needs them. Kubernetes pays off when there are many services and a team to run the platform (`kubernetes-workloads.md`).
- **Everything as code**, including networking and identity, reviewed through plans (`../GUIDE.md`).
- **Private by default:** no public databases, no management ports open to the internet, managed-service access through private endpoints where offered.

## Accounts, subscriptions and projects

- Separate production from everything else at the account (AWS), subscription (Azure) or project (Google Cloud) level. Account boundaries are the strongest isolation for permissions, quotas, cost and blast radius.
- A typical organization layout: a management or root account that runs no workloads; a log archive and a security tooling account; workload accounts per environment and team; a sandbox area with budgets. Group them (AWS Organizations units, Azure management groups, Google Cloud folders) so guardrail policies apply by group.
- Guardrails at the organization level: AWS service control policies, Azure Policy, Google Cloud organization policies. Typical rules: deny leaving the organization, deny disabling audit logs, restrict regions, require encryption. They affect every team; propose them, never apply them without the owner.
- Audit logs (CloudTrail organization trail, Azure Activity Log, Cloud Audit Logs) go to the log archive account with retention and immutability, out of reach of workload administrators.

## Identity

- People sign in through the organization's identity provider with single sign-on and MFA, and receive short-lived role credentials. No long-lived user access keys.
- Workloads use attached roles, managed identities or workload identity federation, never stored keys.
- CI systems authenticate with OIDC federation, with trust conditions narrowed to repository, branch or environment (`../../engineering-practices/references/ci-and-release.md`). A deploy role for production should not be assumable from a pull-request job.
- Least privilege per workload, reviewed with the provider's access analysis tools. Keep a documented break-glass path for when the identity provider is down.
- Any change to roles, policies, trust relationships or federation is an IAM change: show it in the plan and get explicit approval.

## Networks

- Plan address space once for the whole organization, with non-overlapping ranges so networks can be peered or connected later.
- Public subnets hold only load balancers and egress gateways; workloads and data stores sit in private subnets. Control egress (NAT, egress firewall or proxy) and log it.
- Connect many networks through a hub (AWS Transit Gateway, Azure hub-and-spoke with Virtual WAN or a hub VNet, Google Cloud shared VPC or Network Connectivity Center) rather than a mesh of peerings.
- Put public entry points behind a load balancer, with a CDN and web application firewall where abuse is plausible; terminate TLS with managed certificates.
- Use private endpoints for managed services (S3, Key Vault, Cloud SQL) so traffic stays private and cheaper.

## Data protection

- Classify data and keep sensitive classes in fewer, better-guarded stores.
- Encryption at rest is on by default in most services; use customer-managed keys where policy requires control over rotation or revocation, and remember that deleting a key makes its data unrecoverable.
- Backups go to a separate account or subscription with immutability (AWS Backup vault lock, S3 Object Lock, Azure immutable vaults) so a compromised workload account cannot delete them.
- A backup counts only after a restore was tested. Schedule restore drills and record the measured restore time.

## Disaster recovery strategies

| Strategy | Standby in the recovery region | Typical RTO and RPO | Relative cost |
|---|---|---|---|
| Backup and restore | Backups only; infrastructure recreated from code | Hours; RPO equals backup interval | Lowest |
| Pilot light | Data replicated; core services defined but scaled to zero | Tens of minutes to hours; RPO minutes | Low |
| Warm standby | A scaled-down full copy running | Minutes; RPO seconds to minutes | Medium |
| Active-active | Full capacity serving traffic in several regions | Near zero, with conflict handling for writes | Highest |

- Pick the cheapest strategy that meets the agreed RTO and RPO; write the numbers next to the choice.
- Recovery depends on more than the application: DNS, the identity provider, CI and artifact registries, secrets, quotas and capacity in the recovery region. List them.
- Replication copies corruption and deletions too. Point-in-time recovery or versioned backups cover the data-corruption case that replication cannot.
- Test failover on a schedule, in an approved window, and compare measured times with the objectives (`chaos-engineering.md` covers game days).

## Migration

Classify each workload with the common seven options: retire, retain, rehost (lift and shift), relocate (move a whole platform unchanged, such as a VMware estate to a hosted VMware service), replatform (small changes such as a managed database), repurchase (move to a SaaS product) and refactor (rework for cloud-native services).

1. Discover and map dependencies (who calls whom, shared databases, batch jobs, hard-coded IPs) before choosing waves.
2. Move in waves, least critical and least coupled first.
3. For each cutover write the runbook: data sync method and lag check, freeze window, validation queries (row counts, checksums), DNS changes with TTL lowered days ahead, success criteria, and the rollback step with its deadline.
4. Keep the source system intact until the target has run through a full business cycle.

## Multi-cloud, honestly

Reasons that hold up: regulation or customer contracts, an acquisition, a specific service only one provider has, or a negotiated discount. Costs that are real: egress between clouds, two sets of skills, identity and network plumbing in both, and designing to the lowest common denominator. Portability comes cheapest from open interfaces (containers, PostgreSQL, S3-compatible APIs, OpenTelemetry) and IaC per provider, not from abstraction layers over every service. Recommend multi-cloud only with the user's stated reason.

## Done when

- [ ] Requirements and assumptions are written, with availability, RTO and RPO numbers agreed by the owner.
- [ ] The design names its account structure, identity model, network layout, data protection and DR strategy, each with a reason.
- [ ] A cost estimate exists (`cloud-cost.md`) and the main decisions have ADRs.
- [ ] Organization-level changes are proposals awaiting the owner, not applied changes.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Peering impossible later | Overlapping CIDR ranges | Central address plan before the first network |
| DR plan fails in the drill | Untested dependencies (DNS, IdP, quotas in the DR region) | List and test every dependency; raise quotas ahead |
| Backups deleted along with the workload | Backups in the same account with the same admins | Separate account, immutability, restricted delete |
| Production broken by a test deploy | Shared account or role for environments | Account per environment; scoped CI roles |
| Migration stalls at cutover | Data sync and validation never rehearsed | Rehearse the cutover on a copy; written rollback deadline |
