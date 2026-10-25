# Isolating the agent: devcontainers, containers and VMs

Reference for the `agent-safety` module. The command guard and permission prompts catch mistakes; they do not contain a determined process. Isolation limits what anything running in the session can reach: the agent, a build script, a dependency's install hook, a test suite from an untrusted repository. Read this when the user asks for a sandboxed setup, wants to run the agent with broad auto-approval or unattended, or needs to build, test or inspect code they do not trust.

## Choose the layer

| Layer | What it stops | What it does not stop |
|---|---|---|
| Permission prompts, command guard | Recognizable mistakes the user would have refused | Anything hidden in scripts, programs or files the agent writes |
| Agent's built-in sandbox, where offered (for example Claude Code's `/sandbox` mode) | Filesystem writes and network access outside configured limits for the commands it covers | Tools and channels outside its scope; check what it covers in the agent's documentation |
| Container or devcontainer | Reading or writing host files outside the mounts; host processes; host credentials not passed in | Damage to the mounted project; kernel or runtime escapes; misuse of anything passed in |
| Virtual machine | All of the above, with a separate kernel | Misuse of credentials and network access given to the VM |
| Separate machine or disposable cloud environment | Everything on the user's own machine | Misuse of credentials and network access given to it |

Use a container or devcontainer for everyday autonomous work on the user's own projects. Use a VM for hostile code: malware samples (`../../code-security-review/references/yara-rules.md`), unknown binaries, or a repository suspected of being malicious.

## Who sets it up

The sandbox protects the user from the agent, so the user owns it. The agent may draft the files, but adding or changing `.devcontainer/`, container flags, mounts or network rules is an agent-configuration change: show the exact files and wait for the user's OK. Inside the sandbox, never edit its definition, add mounts, capabilities or network access, or ask for `sudo` to get a task done. If the sandbox blocks the task, stop and ask (ground rule 1).

## A minimal devcontainer

```jsonc
// .devcontainer/devcontainer.json: a starting point for an agent sandbox
{
  "name": "agent-sandbox",
  // Pin by digest (image@sha256:...) once chosen, so rebuilds are repeatable
  "image": "mcr.microsoft.com/devcontainers/base:bookworm",
  "remoteUser": "vscode",
  "workspaceMount": "source=${localWorkspaceFolder},target=/work,type=bind",
  "workspaceFolder": "/work",
  "mounts": [
    // The sandbox's own definition is read-only from inside the sandbox
    "source=${localWorkspaceFolder}/.devcontainer,target=/work/.devcontainer,type=bind,readonly",
    // Agent settings and history survive rebuilds without mounting the host home folder
    // (~/.claude is Claude Code's folder; use your agent's)
    "source=agent-state-${devcontainerId},target=/home/vscode/.claude,type=volume"
  ],
  // No capabilities, and setuid programs such as sudo cannot raise privileges
  "runArgs": ["--cap-drop=ALL", "--security-opt=no-new-privileges"],
  // Skip dependency install hooks; run a project's own needed scripts explicitly
  "containerEnv": { "NPM_CONFIG_IGNORE_SCRIPTS": "true" }
}
```

- **Non-root, and no way back to root.** Devcontainer base images usually give the `vscode` user passwordless `sudo`; `no-new-privileges` makes it useless. Install tools in the image or with devcontainer features at build time, not from inside the running session.
- **Mount only the project.** Never mount the host home folder, `~/.ssh`, `~/.aws`, `~/.config/gcloud`, `~/.kube`, `~/.docker`, browser profiles or other repositories.
- **Never pass the Docker socket** (`/var/run/docker.sock`) and never use `--privileged`, `--pid=host` or `--network=host`: each one hands the container control of the host.
- **`ignore-scripts`** stops npm lifecycle hooks during installs and the `pre`/`post` hooks around `npm run`; the named script itself still runs. Other ecosystems differ: pip runs a source package's build code during install (`pip install --only-binary :all:` accepts wheels only), and Cargo build scripts and procedural macros always run, so build untrusted projects only inside the sandbox.
- Start the container with the editor ("Reopen in Container") or the devcontainer CLI: `devcontainer up --workspace-folder .`, then `devcontainer exec --workspace-folder . bash`.

## Credentials

Everything passed into the sandbox is readable by everything running there, including dependency code.

- Pass only what the task needs, as environment variables from the host (`"remoteEnv": { "GH_TOKEN": "${localEnv:SANDBOX_GH_TOKEN}" }`), never as files in the workspace.
- Prefer short-lived, narrowly scoped credentials: a fine-grained token limited to one repository, test-mode payment keys, a seeded local database instead of a shared one, an agent API key with a spending limit that can be revoked on its own.
- Editors can forward the host's SSH agent, Git credential helper and Git config into a devcontainer automatically. If the sandbox should not push or reach other repositories, turn that forwarding off in the editor's dev-container settings and verify it from inside (below).

## Network

| Option | How | Use when |
|---|---|---|
| No network | `docker run --network none ...` with the built image | Offline work: reading, refactoring, running tests that need no downloads |
| Allowlist outside the container | Attach the container only to an internal network (`docker network create --internal agent-net`); run a proxy container attached to that network and to an outside one, with a domain allowlist (package registries, the Git host, the agent's API); set `HTTPS_PROXY` in the sandbox | Normal autonomous work. Rules live outside the container, so nothing inside can change them, and tools that ignore the proxy fail closed |
| Firewall inside the container | `iptables` rules applied at start, needing `NET_ADMIN` | Only if no process in the container can become root; otherwise the rules can be flushed |
| Open network | Default | Supervised work only |

## Verify from inside

Run these after the first start and after every change to the setup. Print names and states, never values.

```sh
id -u                                            # not 0
sudo -n true 2>&1 | head -1                      # must fail
grep -E 'CapBnd|NoNewPrivs' /proc/self/status    # CapBnd 0000000000000000, NoNewPrivs 1
test -S /var/run/docker.sock && echo "DOCKER SOCKET PRESENT" || echo "no docker socket"
findmnt -rn -o TARGET,SOURCE,OPTIONS | grep -vE '^/(proc|sys|dev)'            # workspace, read-only .devcontainer, volumes, Docker's /etc files
test -w /work/.devcontainer && echo "DEFINITION WRITABLE" || echo "definition read-only"
echo "ssh agent: ${SSH_AUTH_SOCK:+forwarded}"; test -d ~/.ssh && echo "~/.ssh present" || echo "no ~/.ssh"
git config --show-origin --get-all credential.helper                          # empty unless forwarding is intended
env | cut -d= -f1 | sort                         # only the variable names you expect
curl -sS -m 5 -o /dev/null -w '%{http_code}\n' https://example.com            # fails when the network should be closed
```

## Bringing work back to the host

The workspace is shared with the host, so files written in the sandbox are live there at once, and some of them run on the host later. Before running anything on the host (Git commands included), review the diff and check these:

- `.devcontainer/` (its `initializeCommand` runs on the host when the container starts).
- Git hooks and config: `find .git/hooks -type f ! -name '*.sample'` and `git config --local --list --show-origin | grep -iE 'hooksPath|fsmonitor|sshCommand|pager|editor|textconv|filter\.|alias\..*=!|credential|include'`. These settings run commands on ordinary Git operations.
- Editor and tool automation: `.vscode/tasks.json` (tasks set to run when the folder opens), `.vscode/settings.json` paths to interpreters, formatters or terminals inside the workspace, `.envrc`, `.husky/`, `.pre-commit-config.yaml`, `Makefile` and `package.json` scripts.

Report every change to these files explicitly; they belong to risk class 11 in `destructive-commands.md`.

## Limits

- Containers share the host kernel. A kernel or container-runtime bug can lead to an escape; keep Docker and the kernel patched, prefer rootless Docker or Podman, and consider a user-space kernel runtime such as gVisor (`--runtime=runsc`). On macOS and Windows, Docker Desktop already runs containers inside a VM, which adds a boundary.
- The mounted project can still be deleted or corrupted. The stop-check, commits and backups still apply inside the sandbox.
- Named volumes keep agent history and settings between sessions. Removing them (`docker volume rm`) deletes data: ask first.
- Isolation does not make a session safe to run against production. No production credentials go in, whatever the setup.
