# Reproducible developer environments

Read this when "works on my machine" is the problem: onboarding takes days, CI and laptops disagree about tool versions, a project needs system packages (compilers, databases, native libraries) next to language dependencies, or an agent needs project-scoped tools without installing anything globally. It covers Nix-based development shells, dev containers, runtime version managers, Docker Compose for local services, and locked-down containers for testing installers. Production images are in `containers-and-registries.md`; dependency hygiene in `../../engineering-practices/references/dependencies.md`.

## Choose the mechanism

| Need | Choose | Trade-off |
|---|---|---|
| Only language runtimes differ (Node 22, Python 3.12) | A runtime version manager (mise, asdf) or the language's own (`uv python`, `rustup`), with the version file committed | No system libraries; each developer still installs databases and tools by hand |
| Toolchains plus system packages, macOS and Linux, no virtualization | A Nix development shell (flake or a Nix-based manager with a simpler manifest) | Learning curve; Windows only through WSL2 |
| Full OS-level isolation, Windows hosts, editor integration | A dev container (`devcontainer.json`, an open specification supported by several editors and CI tools) | Container overhead; file sync slowness on macOS; Docker Desktop needs a paid subscription in larger companies |
| Databases, caches, queues for local development | Docker Compose services, or services started from the Nix shell | Compose needs a container runtime; Nix services need start and stop scripts |

Whatever you pick, the environment definition and its lock file are committed, CI uses the same definition, and the README says how to enter it in one command.

## Nix development shells

Nix builds each package from a pinned recipe into its own store path, so the same lock file gives the same tools on every machine and in CI. Flakes are the common entry point; upstream Nix has long labeled them experimental, so add `experimental-features = nix-command flakes` to `nix.conf` if your installation asks for it.

```nix
# flake.nix
{
  description = "Development shell for the orders service";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";   # a stable branch; flake.lock pins the exact revision

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = [ pkgs.python312 pkgs.uv pkgs.nodejs_22 pkgs.postgresql_16 pkgs.jq ];
          shellHook = ''
            export PGDATA="$PWD/.dev/pgdata"
            export UV_CACHE_DIR="$PWD/.dev/uv-cache"
          '';
        };
      });
    };
}
```

```bash
nix develop                         # enter the shell
nix develop --command make test     # run one command inside it (also how CI uses it)
nix flake update                    # moves flake.lock: a dependency change, reviewed like one
```

- **Commit `flake.nix` and `flake.lock`.** The lock pins the nixpkgs revision; the versions you get are the ones that revision packages. For an older version, pin a nixpkgs revision that has it or add an overlay, and say so.
- **direnv** with `use flake` in `.envrc` enters the shell when you `cd` into the project (nix-direnv caches it). `direnv allow` runs the file's code: read `.envrc` before allowing it in a repository you did not write, and never allow it on someone else's behalf.
- **Nix provides toolchains; language tools install project dependencies.** Let `uv`, `npm`, `cargo` or `go` install into the project from their own lock files. Managing every library through Nix as well creates two sources of truth.
- **Native binaries on NixOS:** prebuilt wheels and binaries downloaded by language package managers often cannot find shared libraries there. Use the Nix-packaged version, build from source, or enable a loader compatibility layer, and document which.
- **Platforms:** list the systems you support; guard Linux-only tools (for example `valgrind`) to Linux and test the shell on macOS in CI if developers use it.
- Several tools wrap Nix in a TOML or JSON manifest with their own lock file, per-package version constraints and service definitions. The same rules apply: commit the manifest and lock, keep hooks fast, keep secrets out.

## Hooks and services in the shell

- Shell hooks run on every entry: keep them fast and idempotent (create a directory or virtual environment only if missing). Hooks are sourced into the user's shell, so a failing check must `return`, never `exit`, or it closes the terminal.
- Put interactive helpers (aliases, functions) where the tool expects interactive configuration, not in the non-interactive hook.
- Use paths relative to the project (`$PWD` in the hook or the tool's project variable), never `/home/alice/...`.
- Local databases keep their data in an ignored project directory (`.dev/`), listen on `localhost` or a socket in that directory, and use development-only credentials.

## Secrets

Never commit secrets in `flake.nix`, manifests, `.envrc` or Compose files. Read them from the environment, a gitignored local file (`.envrc.local`, `.env`), or the team's secret manager. Agents follow `../../agent-safety/references/secrets.md`: names only, never values.

## Supply chain

- Binary caches serve prebuilt store paths signed by their keys. Trust the official cache and caches your team operates; adding a substituter means running binaries its owner built. A flake can ask for extra caches in `nixConfig`; do not accept that prompt for a project you do not trust.
- Entering a shell from an untrusted flake or dev container runs its hooks and build steps: review them first (`../../agent-safety/references/vetting-extensions.md`).
- Adding a package to the environment is a dependency change: show the manifest and lock diff and get agreement before committing.

## Docker Compose for local services

```yaml
# compose.yaml (development only)
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_PASSWORD: dev-only-password        # local throwaway credential, never reused
    ports: ["127.0.0.1:5432:5432"]               # loopback only
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 10
  app:
    build: { context: ., target: dev }
    depends_on:
      db: { condition: service_healthy }          # wait for health, not just for start
    volumes: [".:/app", "/app/node_modules"]      # keep the image's dependencies, not the host's
volumes:
  pgdata:
```

- Publish ports on `127.0.0.1` unless the team needs them on the network; a plain `"5432:5432"` listens on every interface.
- Profiles (`profiles: [observability]`) keep optional services off by default; `compose.override.yaml` holds personal tweaks and is usually gitignored.
- `docker compose down -v` deletes the named volumes and their data: say so before running it.

## Locked-down containers for testing installers and CLIs

To test an installer or a CLI against several Linux distributions without letting it touch the host:

```yaml
services:
  install-test:
    image: debian:bookworm-slim@sha256:<digest>   # pinned by digest
    user: "1000:1000"
    read_only: true
    network_mode: none                            # opt in to network only in a separately named service
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    pids_limit: 256
    tmpfs:
      - /tmp:size=512m
      - /work:size=1g,mode=0700,uid=1000,gid=1000
    volumes: ["./:/src:ro"]                       # source mounted read-only; tests copy it into /work
    command: ["/src/scripts/test-install.sh", "--dry-run"]
```

- Mount the source read-only and copy it into a writable temporary workspace before anything mutates it; pass no host credentials; default to a dry run.
- Call programs with argument arrays, never interpolated shell strings (`terminal-sessions.md`).
- A Linux container validates Linux only. macOS cannot run in a container, and Windows containers need a Windows host; run native macOS and Windows CI jobs for paths, quoting and file-system behavior on those systems.

## Checks (done when)

- [ ] One documented command enters the environment; CI runs tests through the same definition.
- [ ] Definition and lock file committed; updating the lock is a reviewed change.
- [ ] Hooks are idempotent, fast, use project-relative paths and never `exit`.
- [ ] No secrets in committed files; local services bind to loopback with throwaway credentials.
- [ ] Only trusted binary caches; untrusted hooks and dev containers reviewed before entry.
- [ ] Installer tests run read-only, offline and unprivileged by default, with native jobs for non-Linux platforms.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Lock file not committed, so everyone resolves differently | Commit it; update deliberately |
| Same library managed by Nix and by pip or npm | Nix for toolchains, the language lock file for project dependencies |
| Hook reinstalls dependencies on every entry | Guard with a marker or check |
| `exit 1` in a sourced hook closes the terminal | `return 1` |
| Compose database reachable from the whole network | Bind to `127.0.0.1` |
| "Tested on macOS" in a Linux container | Native macOS runner |
