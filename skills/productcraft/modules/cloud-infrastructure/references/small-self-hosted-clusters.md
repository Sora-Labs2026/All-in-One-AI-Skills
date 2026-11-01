# Small self-hosted clusters

Read this when services run on one to a handful of machines the user controls (rented virtual servers, office or home servers, a rack in a lab) rather than a managed cloud platform: choosing how to orchestrate them, putting a reverse proxy with TLS in front, deploying without downtime, placing stateful services, connecting machines privately, and keeping it all patched and backed up. Networks, firewalls and VPNs at the edge are in `../../networking/GUIDE.md` (see `../../networking/references/wireguard-vpn.md` and `../../networking/references/home-firewall.md`); Kubernetes manifests in `kubernetes-workloads.md`.

The module's hard rule applies: plan and diff only. Deploys, restarts, volume removals, firewall changes and certificate requests against the user's machines run only after their go-ahead for that exact command and host.

## Choose the smallest thing that works

| Situation | Choose | Watch out for |
|---|---|---|
| One machine, a few services | Docker Compose plus a reverse proxy | Single point of failure; plan restores, not just backups |
| Two to five machines, stateless services, little operations time | Compose-based multi-machine tools (Docker Swarm mode, or newer tools that deploy Compose files across machines over a WireGuard mesh with a built-in proxy) | Smaller ecosystems; read each tool's behavior on machine loss |
| Need Kubernetes APIs, Helm charts or operators | A lightweight Kubernetes distribution (k3s, k0s, MicroK8s) | Kubernetes operations knowledge is now required; etcd or its replacement needs backups |
| Batch and mixed workloads across many machines | A general scheduler (Nomad is source-available under the Business Source License since 2023: check terms for the use) | License and ecosystem |
| Databases that must not lose data, few operators | A managed database, even when apps run on own hardware | Network latency and egress to the managed service |

Write down the reason for the choice and the expected size. Moving from Compose to Kubernetes later is easier than running Kubernetes nobody understands.

## Reverse proxy and TLS

- One proxy entry point per public IP (Caddy, Traefik or nginx with an ACME client) terminates TLS and routes by host name to services on private networks. Caddy and Traefik obtain and renew certificates automatically.
- ACME challenges: HTTP-01 needs port 80 reachable from the internet; DNS-01 works for wildcard certificates and hosts that are not reachable, but needs a DNS API token, which is a powerful secret: scope it to the one zone or record if the provider allows. Test against the certificate authority's staging endpoint first; production endpoints rate-limit repeated failures.
- A wildcard DNS record pointing at the proxy lets new subdomains work without DNS changes; it also means typos resolve, so the proxy should answer unknown hosts with an error, not a default site.
- Proxy configuration lives in the repository. Generated configuration is changed through its source, never edited in place.

## Docker and firewalls

Docker writes its own packet-filter rules for published ports, ahead of host firewall front ends such as ufw. A container started with `ports: ["5432:5432"]` is reachable from the internet even when the host firewall "denies" 5432.

- Publish only the proxy's ports (80 and 443). Other services join a private network shared with the proxy and publish nothing.
- When a port must be published, bind it to a specific address: `127.0.0.1:5432:5432` or the machine's private mesh address.
- Restrictions that must apply to containers go in Docker's `DOCKER-USER` chain or a cloud firewall in front of the machine. Verify from outside with a port scan of the public address the user owns, not by reading the configuration.

## Private networking between machines

- Connect machines over a private network (the provider's private network, or a WireGuard mesh) and bind internal services to those addresses. Never send database or cache traffic across the internet unencrypted.
- SSH with keys only, no password login, no direct root login, and access limited to the VPN or known addresses where possible.
- Management interfaces (server BMCs, NAS and router admin pages, hypervisor consoles) stay on a management network reachable only over the VPN. Do not publish them through the public proxy. If you must proxy an internal HTTPS device with a self-signed certificate, trust that device's certificate or CA in the proxy instead of disabling verification, and put authentication in front.

## Deploying without downtime

- Build once, push to a registry (self-hosted with TLS and authentication, or hosted), and deploy by digest; or stream images over SSH (`docker save | ssh host docker load`) for very small setups. Never build on the production machine from an unreviewed checkout.
- `docker compose up -d` recreates changed containers, which drops requests during the restart. For zero downtime run at least two replicas behind the proxy with health checks, start the new version, wait until healthy, shift traffic, then stop the old one; multi-machine tools and Kubernetes do this for you when health checks are defined.
- Render before applying: `docker compose config` (or the tool's plan or diff) shows exactly what will change. Keep the previous image digest for rollback.
- Database migrations follow expand and contract (`../../engineering-practices/references/data-and-migrations.md`) so the old version keeps working during the switch.

## Stateful services and backups

- Pin each stateful service to one machine with a named local volume, and write down which machine. Replicated databases are a project of their own; do not improvise them.
- Back up to a different machine and a different location, encrypted, with retention (restic and Borg are common open-source choices). Back up databases with their own dump or snapshot tools, not by copying live data files.
- Test a restore onto a fresh machine and time it. Alert when a backup job fails or has not run.

## Keeping it healthy

- Operating system security updates install automatically, with a planned reboot window. Container images are updated through reviewed changes (a dependency bot opening pull requests), not by an updater that pulls new tags into production on its own.
- Monitor from outside the cluster (uptime checks on public endpoints) and inside (node metrics, container restarts, disk space, certificate expiry, backup age). Disk-full is the most common outage on small setups: alert well before it.
- Logs go to one place with retention; they will contain personal data if the apps handle any.

## Commands at a glance

| Run freely (read-only) | Prepare and ask first |
|---|---|
| `docker ps`, `docker compose ps`, `docker compose config`, `docker logs --tail 200`, `docker inspect`, `docker stats --no-stream`, `df -h`, `ss -tlnp`, cluster tool `list` and `inspect` commands, `kubectl get` and `describe` | `docker compose up`, `down`, `restart`, `pull`; `docker volume rm`, `docker system prune` (with `--volumes` it deletes data); firewall changes; certificate requests on production endpoints; scaling, draining or removing a machine; anything run through `exec` on production |

## Checks (done when)

- [ ] The orchestration choice is written down with its reason; the hosts and the context in use were confirmed before any command.
- [ ] Only the proxy publishes ports; other services are on private networks; an external scan of the user's own address confirms it.
- [ ] TLS is automatic and was tested against a staging certificate authority; DNS tokens are scoped.
- [ ] Deploys use pinned digests, health checks and a written rollback; zero downtime needs two healthy replicas.
- [ ] Stateful services have a known home, off-site encrypted backups and a timed restore.
- [ ] Patching, monitoring and disk alerts are in place; nothing ran against the user's machines without approval.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Database open to the internet despite the firewall | Bind to loopback or a private address; `DOCKER-USER` rules |
| Downtime on every deploy | Replicas, health checks, start-then-stop |
| BMC or NAS admin page on a public host name | Management network plus VPN |
| `tls_insecure_skip_verify` to reach an internal device | Trust its certificate or CA |
| Backups on the same disk as the data | Off-host, encrypted, restore-tested |
| Auto-updater pulled a breaking image at night | Reviewed image updates by digest |
