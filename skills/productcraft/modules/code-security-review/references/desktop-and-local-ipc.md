# Desktop apps, local servers and local IPC

Read this when the scope contains a desktop app (Electron, Tauri, native), a helper or daemon that runs on the user's machine, a local HTTP or WebSocket server, a custom URL scheme or file association, a browser native-messaging host, or IPC over named pipes, Unix sockets, XPC or D-Bus. [Entry points and context](entry-points-and-context.md#2-surfaces-outside-the-web-routes) lists where these entries are declared. This file covers how to review them. Mobile apps, deep links on phones and their backends are in [mobile apps](mobile-apps.md). Native memory safety is in [C and C++](c-and-cpp.md) and [Rust](rust.md), and update signing in [supply-chain review](supply-chain-review.md#6-if-the-project-publishes-software).

## Name the attacker first

Local code has several distinct attackers. Each reaches different entries, so write down which ones the threat model includes:

| Attacker | Reaches | Typical boundary |
|---|---|---|
| Remote content inside the app (a web page, a message, a document rendered in a webview) | The renderer, its preload or bridge, navigation and window-opening | Web content to native code |
| Any website the user visits | Local HTTP and WebSocket servers, custom URL schemes, native messaging through an extension | Internet to the user's machine |
| A file the user opens | File associations, import paths, parsers | Document to app authority |
| Another app or local user | Sockets, pipes, XPC services, D-Bus names, loopback ports, shared files | One OS principal to another |
| An unprivileged process | Privileged helpers, services, installers, updaters | User to root or SYSTEM |

The same user doing something to their own data with their own authority is not a boundary crossing. A plugin the user installs into their own app is not one either, unless the product promises isolation.

## Electron

Defaults improved over time, so check the version first (`electron` in the lockfile). Electron supports only the latest three stable major versions, and an unsupported one ships an old Chromium with known renderer bugs.

| Setting or API | Safe state | Why it matters |
|---|---|---|
| `nodeIntegration` (false by default since 5) | `false` in every window, webview and subframe (`nodeIntegrationInSubFrames`) | With it on, any script in the page has full Node.js |
| `contextIsolation` (true by default since 12) | `true` | Without it, page scripts can tamper with the preload's objects |
| `sandbox` (renderers sandboxed by default since 20) | Not set to `false` | An unsandboxed renderer turns a renderer bug into code on the host |
| `webSecurity`, `allowRunningInsecureContent` | `true` and `false` | Turning off same-origin policy or allowing mixed content in a privileged window |
| `webviewTag` (false by default since 5) | Off unless needed; if on, `will-attach-webview` strips preloads and forces safe preferences | Pages can create webviews with their own settings |
| Preload `contextBridge.exposeInMainWorld` | Narrow, named functions with validated arguments | Exposing `ipcRenderer` itself, a generic `invoke(channel, ...args)`, `fs` or `child_process` hands the bridge to any script in the page |
| `ipcMain.handle` / `ipcMain.on` | Check `event.senderFrame` (its URL and origin) against the app's own origin; validate every argument | Any frame that reaches the bridge, including an iframe or a navigated page, can call the handler |
| `will-navigate`, `setWindowOpenHandler` | Deny by default; allow listed origins | A privileged window navigated to attacker content keeps its preload |
| `shell.openExternal(url)` | Only `https:` (and maybe `mailto:`) after parsing with `new URL` | `file:` and other schemes can launch local programs |
| `session.setPermissionRequestHandler` | Deny by default | Camera, microphone, notifications and similar for remote content |
| `protocol.handle` (Electron 25+) and older `register*Protocol` | Resolve the path, then check it stays under the app's folder | URL paths map to the filesystem; `..` and encoded separators escape |
| Fuses (`@electron/fuses` at package time) | `RunAsNode` off, `EnableNodeOptionsEnvironmentVariable` and `EnableNodeCliInspectArguments` off, `EnableEmbeddedAsarIntegrityValidation` and `OnlyLoadAppFromAsar` on | Otherwise a local process can run arbitrary code under the signed app's identity, or swap the app's code |

```bash
rg -n -e 'nodeIntegration(InSubFrames)?\s*:\s*true' -e 'contextIsolation\s*:\s*false' -e 'sandbox\s*:\s*false' \
  -e 'webSecurity\s*:\s*false' -e 'webviewTag\s*:\s*true' -e 'exposeInMainWorld' -e 'ipcMain\.(handle|on)\(' \
  -e 'openExternal\(' -e 'protocol\.(handle|register\w*Protocol)\(' -e 'setWindowOpenHandler|will-navigate' \
  -e 'loadURL\(' -e 'flipFuses|FuseV1Options' .
```

Review a window by asking what is loaded into it (local files, a remote URL, user content), what its preload exposes, and which IPC handlers can reach the filesystem, processes, credentials or network. A remote page in a window whose preload exposes file or shell access is the classic critical path. Prove it with a local page that calls the bridge and writes a marker file into a scratch folder.

## Tauri

Tauri 2 (stable since October 2024) replaced the 1.x allowlist with capabilities: JSON or TOML files, usually in `src-tauri/capabilities/`, that grant permissions to named windows or webviews.

- **Remote origins.** They get no IPC unless a capability lists them under `remote.urls`. Every remote URL listed there can call every permission in that capability. Review that list like a CORS allowlist.
- **Your own commands.** Functions marked `#[tauri::command]` are the app's attack surface. Validate arguments in Rust, canonicalize paths against a base directory, and never pass strings to a shell. Check whether commands are restricted per window (Tauri 2 can generate permissions for app commands through the build script's app manifest). If they are not, assume any window with IPC can call them.
- **Plugin scopes.** File-system scopes such as `$HOME/**`, shell permissions that run programs, and an HTTP scope with wildcards widen what an injected script can do. Keep scopes to the app's own directories and fixed programs, and keep the asset-protocol scope narrow too.
- **CSP.** Set it in `tauri.conf.json` (`app.security.csp` in 2.x). Without it, an injected script has the full IPC surface. The isolation pattern adds a sandboxed check of every IPC message before it reaches Rust.
- **Tauri 1.x projects.** Read `tauri.allowlist` and any `dangerousRemoteDomainIpcAccess` entries with the same questions.

## Custom URL schemes and file associations

Registration lives in the Windows registry (`HKEY_CURRENT_USER\Software\Classes\<scheme>` with a `URL Protocol` value and a `shell\open\command`), in macOS `CFBundleURLTypes`, and in Linux `.desktop` files (`MimeType=x-scheme-handler/<scheme>`). Any web page can trigger a scheme. Browsers ask the user first, but many offer "always allow" for a site. The URL reaches the app as a command-line argument (Windows, Linux, often forwarded through a single-instance lock such as Electron's `second-instance` event) or as an `open-url` event (macOS).

- **Argument injection.** If the command template does not quote `"%1"`, or the app parses options after the URL, a crafted URL can add command-line switches. Windows protocol handlers in several frameworks have shipped this bug. Make the URL the last argument, after `--` where the parser supports it, and reject URLs that contain quotes or whitespace before parsing.
- **Actions without consent.** A link must not connect to a server, import settings, install a plugin, run a command or sign in with a token it carries without an in-app confirmation that shows what will happen. Parse with a URL parser and dispatch through an allowlist of actions.
- **Auth callbacks.** Another local app can register the same scheme. For OAuth in desktop apps use a loopback redirect with PKCE and `state` ([OAuth and tokens](../../integrations/references/oauth-and-tokens.md)), or bind the callback to a pending request the app created.
- **Files the user opens** are untrusted input to every parser and importer they reach. Project files that contain scripts, plugin paths or shell hooks are code: open them with those features disabled until the user trusts the project.

## Local HTTP and WebSocket servers

Developer tools, companion daemons, "open in app" helpers and local agents often listen on `127.0.0.1`. The browser lets any website talk to them:

- **Simple requests.** A page can send GET, form POSTs and `text/plain` POSTs to `http://127.0.0.1:<port>` with no preflight. It cannot read the response without CORS, but the side effect happens. Treat every state-changing endpoint like a CSRF target.
- **DNS rebinding.** An attacker's hostname is re-pointed to `127.0.0.1`, so the attacker's page reads responses as same-origin. The defense is to check the `Host` header against an exact list (`localhost:<port>`, `127.0.0.1:<port>`, `[::1]:<port>`) and refuse everything else.
- **WebSockets** are not covered by the same-origin policy. The browser sends `Origin` and the server must check it against an exact list.
- **Authenticate every request** with a random per-install or per-session token. Keep it in a file only the user can read, or pass it at launch. Do not rely on the port being unknown: ports are easy to scan.
- **Bind to loopback,** not `0.0.0.0`, unless the LAN is meant to connect. Never answer data endpoints with `Access-Control-Allow-Origin: *`.
- **Port squatting.** Another local user can bind the port before the server starts. A client that sends secrets to the server should check the server's identity too, through the token exchange.
- Browsers are adding user prompts before public sites can reach local addresses (Chrome began rolling one out in 2025). Treat these as extra protection only: other and older browsers do not have them.

Prove with two local host names (a page on `http://127.0.0.2:8080` calling the service on `127.0.0.1`), or a hosts-file entry and a local resolver for rebinding. Never use a public rebinding service against someone else's machine.

## Named pipes, sockets, XPC and D-Bus

The rule is the same everywhere: the server learns who the peer is from the operating system, never from a field in the message. It then authorizes each method and each resource for that peer.

| Mechanism | Check |
|---|---|
| Windows named pipes | An explicit security descriptor. The default grants read access to Everyone and the anonymous account. `PIPE_REJECT_REMOTE_CLIENTS` unless the network is meant to connect. `FILE_FLAG_FIRST_PIPE_INSTANCE` so a squatter's earlier instance makes creation fail. Identify clients through the impersonation token, not `GetNamedPipeClientProcessId` (process IDs are reused). Clients open pipes with `SECURITY_SQOS_PRESENT \| SECURITY_IDENTIFICATION` so a rogue server cannot act as them |
| Unix domain sockets | Socket file in a directory only the intended users can enter. Linux requires write permission on the socket to connect, but some other systems ignore socket permissions. Abstract-namespace sockets (Linux) have no permissions at all: any process in the same network namespace can connect. Peer identity from `SO_PEERCRED` (Linux) or `getpeereid` (BSD, macOS); check user and group, not process ID |
| macOS XPC | Check the peer's code signature through its audit token: `setCodeSigningRequirement` on `NSXPCConnection` (macOS 13+) or `xpc_connection_set_peer_code_signing_requirement` (macOS 12+). Checking by process ID races. Hardened runtime and library validation on the client stop code injection into a trusted caller |
| D-Bus and polkit | System-bus policy files (`/usr/share/dbus-1/system.d/`, `/etc/dbus-1/system.d/`) restrict who may own names and call methods. polkit checks use the caller's bus name as the subject; the older process-ID subject had a known race |
| Loopback TCP used as IPC | Any local user can connect: needs the same token as a local HTTP server |
| Shared memory and mapped files | Permissions at creation. Read each value once into private memory before checking and using it |

Also check that request IDs are unpredictable and bound to the connection, so one peer cannot answer or cancel another's request. Check that socket files, lock files and pipes left by a crashed instance cannot be pre-created by another user.

## Privileged helpers, services and updaters

A helper that runs as root or SYSTEM on behalf of a user is a confused deputy unless it re-checks everything:

- **Paths.** The user controls paths, and so do symlinks and races. Open relative to a trusted directory descriptor, refuse symlinks (`O_NOFOLLOW`, `openat2` with `RESOLVE_BENEATH` on Linux 5.6+), check the final file's owner, and allowlist destinations ([C and C++](c-and-cpp.md#bug-classes) covers the file-race patterns).
- **Operations.** Allow named operations with validated arguments. Never "run this command" or "write these bytes to this path".
- **Code it runs.** Never execute or load a script, binary, library or plugin from a location a less privileged user can write: `%TEMP%`, `~/Library/Caches`, a world-writable install folder, the current directory.
- **Installers and updaters.** Verify the signature of the exact bytes you install, from a location the user cannot modify between check and use. Do not unpack to a user-writable folder and then run what was unpacked.
- **Windows services.** Check the service binary path quoting, a service DACL that lets users reconfigure the service (`sc sdshow <name>`), and writable service directories.
- **macOS.** `SMJobBless` is deprecated since macOS 13 in favor of `SMAppService`. Either way, the helper must verify each client's code signature through XPC.

## Browser native-messaging hosts

A native-messaging host runs as a normal program with the user's full rights. The browser starts it for extensions listed in its manifest (`allowed_origins` in Chromium, `allowed_extensions` in Firefox). Pages reach the host through the extension: through content scripts, or through `externally_connectable`. So the chain is web page, then extension, then host. Each link must treat what it receives as untrusted. The host never runs commands, opens arbitrary paths or returns secrets because a message asked.

## Local secrets

Token storage per platform is in [OAuth and tokens](../../integrations/references/oauth-and-tokens.md#storing-tokens). In a desktop review, also check for:

- secrets in files other users can read (`0600` for files, `0700` for folders);
- secrets in logs and crash dumps;
- secrets in command-line arguments, which other local users can read through `ps` and `/proc/<pid>/cmdline` on Linux unless `/proc` is mounted with `hidepid`.

Plaintext readable only by the same OS account is a hardening note unless the product promises protection from other apps of that user, as sandboxed platforms do.

## Confirm safely

Use the project's own build on a machine or VM you control, with a dummy profile and dummy accounts. Use two OS users for cross-user claims. Record the OS version, the app version and build flags, and the settings in force. Stop at a marker: a file written in a scratch folder, a handler invoked with a canary argument, a helper reporting the path it would have written. Never use another person's machine, account or running app. Rate with the [severity rules](audit-phases.md#phase-6-rate-severity). Remote web content reaching native code needs no local access, while a local-only path lowers reach.

## Done when

- Every window, webview, preload, IPC handler, custom scheme, file association, local listener, IPC endpoint, helper and native-messaging host has a coverage cell, with the attacker who can reach it.
- Electron or Tauri settings are recorded for the pinned version, and each bridge function has its sender check and argument validation cited.
- Local servers have Host, Origin and token checks cited, or a finding.
- Peer authentication for each IPC endpoint comes from the OS, with per-method authorization, or there is a finding.
- Privileged helpers and updaters have their path, operation and signature checks cited, and anything decided outside the repository (signing, packaging, OS policy) is `NOT_VERIFIED` with the owner check named.
