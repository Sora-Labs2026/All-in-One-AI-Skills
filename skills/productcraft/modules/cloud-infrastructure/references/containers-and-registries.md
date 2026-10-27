# Container images and registries

Read this when you write or review a Dockerfile or Containerfile, build multi-architecture images, add SBOMs, provenance or signatures, set up or clean up a container registry (ECR, ACR, Artifact Registry, GHCR, Docker Hub), or move images between registries.

Supply-chain review of base images and build inputs is in `../../code-security-review/references/supply-chain-review.md`; container basics for secrets are also in `../../code-security-review/references/secrets-and-dependencies.md`. Pushing an image is publishing: build and scan locally, and push only when the user asked for that release.

## A Dockerfile that is small, reproducible and safe

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim@sha256:<digest> AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build && npm prune --omit=dev

FROM gcr.io/distroless/nodejs22-debian12@sha256:<digest>
WORKDIR /app
COPY --from=build --chown=nonroot:nonroot /app/dist ./dist
COPY --from=build --chown=nonroot:nonroot /app/node_modules ./node_modules
USER nonroot
EXPOSE 8080
CMD ["dist/server.js"]
```

- **Pin base images by digest** (keep the tag for readability) and let a dependency bot update the digest. A tag can be re-pointed at different content.
- **Multi-stage builds**: compilers, package managers and build secrets stay in the build stage; the final stage holds only the runtime and the artifact. Minimal or distroless runtime images shrink both size and attack surface, at the cost of no shell for debugging (`kubernetes-troubleshooting.md` covers debug containers).
- **Order layers for caching**: copy lockfiles and install dependencies before copying source, and use BuildKit cache mounts for package caches.
- **Run as a non-root user**, with a numeric UID if the platform enforces `runAsNonRoot` by UID.
- **Exec-form `CMD` and `ENTRYPOINT`** so the process is PID 1 and receives `SIGTERM`. If the process does not reap children or handle signals, use a minimal init (`tini`, or `docker run --init`).
- **`.dockerignore`** excludes `.git`, `.env*`, local credentials, `node_modules`, build output and test data. Everything in the build context can end up in a layer.
- `HEALTHCHECK` is used by Docker and Compose but ignored by Kubernetes, which uses probes.

## Secrets at build time

- Never `COPY` a secret file or pass one through `ARG` or `ENV`; both remain in the image history even if a later layer deletes them.
- Use BuildKit secret mounts, which exist only for one `RUN` step:

```dockerfile
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci
```

```bash
docker buildx build --secret id=npmrc,src=$HOME/.npmrc -t app:dev .
```

- Check an existing image with `docker history --no-trunc IMAGE` and a secret scanner on the exported layers. A secret found in a pushed image is exposed: rotate it (`../../launchguard/references/safe-operations.md`), then rebuild and remove the old image.

## Build, scan, attest

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  --provenance=mode=max --sbom=true \
  -t registry.example.com/shop/orders:1.4.2 .              # add --push only for an approved release
trivy image --severity HIGH,CRITICAL registry.example.com/shop/orders:1.4.2
```

- **Multi-architecture** builds use QEMU emulation or native builders; emulated builds are slow and can hide architecture-specific failures, so run tests on each architecture you ship.
- **Scanners** (Trivy, Grype, the registry's built-in scanning) report known vulnerabilities in OS and language packages. Triage by reachability and fix availability; a base-image update usually clears most findings. Scanner output is advisory.
- **SBOM and provenance** attestations (SLSA provenance from BuildKit or the CI system's attestation feature) record what went into the image and where it was built.
- **Signing**: `cosign sign` with keyless signing through the CI system's OIDC identity, and verification at deploy time (an admission policy that checks the signature and the signing identity). Signing proves origin, not safety.
- Tag with an immutable version and the commit SHA; deploy by digest. Never deploy `latest`.

## Registries

| Concern | Practice |
|---|---|
| Access | CI pushes with short-lived OIDC credentials scoped to its repositories; runtimes pull with their own identity (node role, managed identity, workload identity). No long-lived registry passwords in CI variables |
| Immutability | Enable tag immutability (ECR, Artifact Registry, ACR repository locks) for release tags so a tag always means one image |
| Retention | Lifecycle or cleanup policies that delete untagged images and keep the last N releases, written so nothing a running workload or rollback needs is deleted |
| Scanning | Scan on push and continuously; alert on new critical findings in deployed images |
| Upstream images | Pull-through caches or mirrors for public images, avoiding anonymous rate limits and outages of public registries |
| Visibility | Repositories private by default; a public repository exposes every layer of every tag |
| Replication | Replicate to the regions that pull, for latency and regional resilience |

```bash
# Read-only inspection
aws ecr describe-repositories --query 'repositories[].{name:repositoryName,immutable:imageTagMutability,scan:imageScanningConfiguration.scanOnPush}'
aws ecr get-lifecycle-policy --repository-name shop/orders
az acr repository show-tags --name REGISTRY --repository shop/orders --orderby time_desc --top 10
gcloud artifacts docker images list REGION-docker.pkg.dev/PROJECT/REPO --include-tags --limit=20
crane digest registry.example.com/shop/orders:1.4.2          # resolve a tag to its digest
```

- Lifecycle policies delete images: write them, test them with the registry's preview where it has one (ECR lifecycle policy preview), and apply only with approval. Make sure rollback targets stay.
- Copying or promoting an image between registries (`crane copy`, `skopeo copy --all`, `oras cp` for non-image artifacts) preserves the digest when done byte for byte; rebuilding does not. Promote by copying the tested digest.
- Deleting images or repositories is irreversible and can break running workloads on their next pull or reschedule. Treat it like any destructive command (`../../agent-safety/GUIDE.md`).

## Done when

- [ ] Base images pinned by digest; the final stage runs as non-root without build tools or secrets; `.dockerignore` excludes credentials and Git data.
- [ ] The image was built and scanned locally, with findings triaged; SBOM and provenance are produced where the pipeline supports them.
- [ ] Registry access uses short-lived identities; release tags are immutable; retention keeps rollback targets.
- [ ] No push, tag move, deletion or lifecycle policy change happened without the user's go-ahead.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Secret visible in `docker history` | Passed through `ARG`, `ENV` or `COPY` | BuildKit secret mount; rotate the exposed secret |
| Container ignores `SIGTERM`, killed after the grace period | Shell-form `CMD` makes the shell PID 1 | Exec form, or an init process |
| `exec format error` at start | Image built for another architecture | Multi-platform build or the matching platform |
| Rollback fails: image not found | Retention policy deleted the previous release | Keep the last N release tags; protect deployed digests |
| Builds slow and uncached in CI | Source copied before dependency install; no cache export | Reorder layers; BuildKit cache to the registry or CI cache |
| Pulls fail randomly from public registries | Anonymous rate limits | Authenticated pulls or a pull-through cache |
