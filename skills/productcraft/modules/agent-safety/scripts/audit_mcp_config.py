#!/usr/bin/env python3
"""Static, read-only review of MCP server declarations in agent configuration files.

For every declared server it classifies what the launch command will fetch
(an exact version, a version range, a movable tag, a container image by tag or
digest, a local program, a remote URL) and flags configuration risks: secret
values written into the file, credentials in URLs, plain-HTTP remote servers,
auto-approved tools, filesystem roots such as / or ~, containers with host
access, and settings that enable every project-declared server at once.

It parses JSON (comments and trailing commas allowed) and never starts a
server, resolves a package or touches the network. Secret values are never
printed: only the variable or header name and the value's length.

Exit codes: 0 no finding at or above --fail-on, 1 at least one, 2 usage error,
missing path or unparsable configuration.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

KNOWN_FILES = (".mcp.json", "mcp.json", ".vscode/mcp.json", ".cursor/mcp.json",
               ".claude/settings.json", ".claude/settings.local.json")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target"}
SERVER_KEYS = {"mcpServers", "servers", "mcp_servers", "context_servers"}
SEVERITY = {"high": 3, "medium": 2, "review": 1, "info": 0}

NPX_LIKE = {"npx", "bunx", "pnpx"}
EXEC_FORMS = {("npm", "exec"), ("pnpm", "dlx"), ("yarn", "dlx"), ("bun", "x")}
LOCAL_RUNNERS = {"node", "python", "python3", "deno", "ruby", "java", "dotnet", "php", "perl", "bun"}
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "cmd", "powershell", "pwsh"}
NPX_VALUE_FLAGS = {"--registry", "--cache", "--userconfig", "-w", "--workspace", "--prefix", "--node-options", "--loglevel"}
UV_VALUE_FLAGS = {"--python", "-p", "--index", "--index-url", "--extra-index-url", "--default-index", "--constraint",
                  "-c", "--with-requirements", "--find-links", "-f", "--python-preference", "--directory"}
PIPX_VALUE_FLAGS = {"--python", "--pip-args", "--index-url", "--backend"}
DOCKER_VALUE_FLAGS = {"-e", "--env", "--env-file", "-v", "--volume", "--mount", "--name", "-p", "--publish", "--network",
                      "--net", "-w", "--workdir", "-u", "--user", "--entrypoint", "-l", "--label", "--platform", "--pull",
                      "-m", "--memory", "--cpus", "--add-host", "--device", "--cap-add", "--cap-drop", "--security-opt",
                      "--tmpfs", "-h", "--hostname", "--ulimit", "--restart", "--log-driver", "--log-opt", "--runtime",
                      "--ipc", "--pid", "--userns", "--shm-size", "--gpus", "--dns", "--stop-signal", "--health-cmd"}
SECRET_FLAGS = re.compile(r"^--?(api[-_]?key|token|access[-_]?token|auth[-_]?token|password|passwd|secret|client[-_]?secret|key)$", re.I)

EXACT_SEMVER = re.compile(r"^v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
NPM_TAG = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
NPM_RANGE = re.compile(r"^[0-9xX*.^~<>=| -]+(?:-[0-9A-Za-z.-]+)?$")
PY_EXACT = re.compile(r"^\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?$")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
REFERENCE = re.compile(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*|\{\{[^}]+\}\}|%[A-Za-z_][A-Za-z0-9_]*%")
PLACEHOLDER = re.compile(r"your[_-]|replace|change[_-]?me|placeholder|example|<[^>]*>|^x{3,}$|\.\.\.|\btodo\b|insert[_-]", re.I)
SECRET_NAME = re.compile(r"token|secret|passw|api[_-]?key|apikey|auth|credential|private[_-]?key|\bpat\b|access[_-]?key|cookie|session", re.I)
KNOWN_TOKEN = re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|sk_(live|test)_[A-Za-z0-9]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
                         r"xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|glpat-[A-Za-z0-9_-]{16,})")
TOKEN_SHAPE = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9_+/=.-]{24,}$")
SHELL_META = re.compile(r"[|;&<>`$()]")


class ConfigError(Exception):
    pass


def strip_jsonc(text):
    """Remove // and /* */ comments and trailing commas outside strings."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
        elif ch == '"':
            in_str = True
            out.append(ch)
            i += 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(ch)
            i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_config(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ConfigError(f"cannot read: {exc.strerror}") from None
    try:
        return json.loads(text)
    except ValueError:
        pass
    try:
        return json.loads(strip_jsonc(text))
    except ValueError as exc:
        raise ConfigError(f"not valid JSON: {exc}") from None


def discover(root, recursive):
    found = [root / rel for rel in KNOWN_FILES if (root / rel).is_file()]
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            if len(Path(dirpath).relative_to(root).parts) >= 4:
                dirnames[:] = []
            for name in sorted(filenames):
                if "mcp" in name.lower() and name.lower().endswith((".json", ".jsonc")):
                    p = Path(dirpath) / name
                    if p not in found:
                        found.append(p)
    return found


def walk_servers(node, trail=""):
    """Yield (json_path, name, server_dict) for every server declaration."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else key
            if key in SERVER_KEYS and isinstance(value, dict):
                for name, server in value.items():
                    if isinstance(server, dict) and any(k in server for k in ("command", "url", "type", "transport")):
                        yield here, str(name), server
            else:
                yield from walk_servers(value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from walk_servers(item, f"{trail}[{i}]")


def walk_flags(node, trail=""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else key
            if key == "enableAllProjectMcpServers" and value is True:
                yield here
            yield from walk_flags(value, here)
    elif isinstance(node, list):
        for item in node:
            yield from walk_flags(item, trail)


def ref(reference, result, why, nxt):
    return {"reference": reference, "result": result, "why": why, "next": nxt}


PIN_NEXT = "pin the exact version your team reviewed; do not substitute today's newest release unreviewed"


def classify_npm(spec):
    if spec.startswith((".", "/", "~")) or "://" in spec or spec.startswith(("git+", "github:", "file:", "npm:", "git@")):
        return ref(spec, "REVIEW", "local path, URL or repository source: version rules do not apply", "review the source and pin a commit or published version")
    if spec.startswith("@"):
        at = spec.find("@", 1)
        name, version = (spec, "") if at == -1 else (spec[:at], spec[at + 1:])
        if "/" not in name:
            return ref(spec, "REVIEW", "unrecognized package selector", "check this entry by hand")
    else:
        if "/" in spec.split("@", 1)[0]:
            return ref(spec, "REVIEW", "repository shorthand: fetches whatever the default branch holds", "use a published version or a pinned commit")
        name, _, version = spec.partition("@")
    if version in ("", "*", "x", "X", "latest"):
        return ref(spec, "MUTABLE", "no fixed version: each start can fetch a newer release", PIN_NEXT)
    if EXACT_SEMVER.match(version):
        return ref(spec, "PINNED", "exact version for the direct package (dependencies may still float without a lockfile)", "re-review when you raise the pin")
    if NPM_TAG.match(version):
        return ref(spec, "MUTABLE", f"distribution tag '{version}' can be moved to any release", PIN_NEXT)
    if NPM_RANGE.match(version):
        return ref(spec, "RANGE", "version range: resolution can move within it", PIN_NEXT)
    return ref(spec, "REVIEW", "unrecognized version selector", "check this entry by hand")


def classify_python(spec, at_syntax=True):
    s = spec.strip()
    if "://" in s or s.startswith(("git+", ".", "/", "~")) or " @ " in s or s.endswith((".whl", ".tar.gz", ".zip")):
        return ref(spec, "REVIEW", "direct URL, repository or local path", "review the source and pin a released version or commit")
    base = re.sub(r"\[[^\]]*\]", "", s)
    if at_syntax and "@" in base and not any(op in base for op in ("==", ">", "<", "~=", "!=")):
        version = base.split("@", 1)[1]
        if version in ("", "latest"):
            return ref(spec, "MUTABLE", "'@latest' resolves to the newest release on each run", PIN_NEXT)
        if PY_EXACT.match(version):
            return ref(spec, "PINNED", "exact version for the direct package", "re-review when you raise the pin")
        return ref(spec, "REVIEW", "unrecognized version selector", "check this entry by hand")
    if "===" in base or ("==" in base and "," not in base):
        version = base.split("==", 1)[1].lstrip("=")
        if "*" in version:
            return ref(spec, "RANGE", "wildcard version: resolution can move within it", PIN_NEXT)
        return ref(spec, "PINNED", "exact version for the direct package", "re-review when you raise the pin")
    if any(op in base for op in (">", "<", "~=", "!=", ",")):
        return ref(spec, "RANGE", "version range: resolution can move within it", PIN_NEXT)
    return ref(spec, "MUTABLE", "no version: each run can fetch a newer release", PIN_NEXT)


def classify_image(image):
    if "$" in image or "{" in image:
        return ref(image, "REVIEW", "image name is templated", "check the value that is substituted")
    if DIGEST.search(image):
        return ref(image, "PINNED", "image pinned by digest", "re-review when you change the digest")
    return ref(image, "MUTABLE", "tags, including version-like tags and the default 'latest', can be moved to new content",
               "pin by digest (image@sha256:...) of the image you reviewed")


def _flag_value(args, i, value_flags):
    """Return (value, next_index) for a flag at args[i] that takes a value, else (None, i + 1)."""
    arg = args[i]
    if "=" in arg and arg.startswith("--"):
        return None, i + 1
    if arg in value_flags and i + 1 < len(args):
        return args[i + 1], i + 2
    return None, i + 1


def parse_npx(args):
    selectors, positional, i = [], None, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            if positional is None and i + 1 < len(args):
                positional = args[i + 1]
            break
        if a in ("-c", "--call") or a.startswith("--call="):
            return [ref(" ".join(args), "REVIEW", "runs a shell command string", "replace with an explicit package and version")]
        if a in ("-p", "--package") and i + 1 < len(args):
            selectors.append(args[i + 1])
            i += 2
            continue
        if a.startswith("--package="):
            selectors.append(a.split("=", 1)[1])
            i += 1
            continue
        if a.startswith("-"):
            _, i = _flag_value(args, i, NPX_VALUE_FLAGS)
            continue
        positional = a
        break
    if not selectors and positional:
        selectors = [positional]
    if not selectors:
        return [ref(" ".join(args), "REVIEW", "no package found in the arguments", "check this entry by hand")]
    return [classify_npm(s) for s in selectors]


def parse_uvx(args):
    selectors, positional, i = [], None, 0
    while i < len(args):
        a = args[i]
        if a in ("--from", "--with") and i + 1 < len(args):
            selectors.append((a, args[i + 1]))
            i += 2
            continue
        if a.startswith(("--from=", "--with=")):
            flag, value = a.split("=", 1)
            selectors.append((flag, value))
            i += 1
            continue
        if a in ("--with-editable",):
            return [ref(" ".join(args), "REVIEW", "editable local install", "review the local source")]
        if a.startswith("-"):
            _, i = _flag_value(args, i, UV_VALUE_FLAGS)
            continue
        positional = a
        break
    has_from = any(flag == "--from" for flag, _ in selectors)
    specs = [value for _, value in selectors]
    if not has_from and positional:
        specs.insert(0, positional)
    if not specs:
        return [ref(" ".join(args), "REVIEW", "no package found in the arguments", "check this entry by hand")]
    return [classify_python(s) for s in specs]


def parse_pipx(args):
    if not args or args[0] != "run":
        return [ref(" ".join(args), "REVIEW", "not a 'pipx run' invocation", "check this entry by hand")]
    rest, i, spec = args[1:], 0, None
    while i < len(rest):
        a = rest[i]
        if a == "--spec" and i + 1 < len(rest):
            spec = rest[i + 1]
            i += 2
            continue
        if a.startswith("--spec="):
            spec = a.split("=", 1)[1]
            i += 1
            continue
        if a.startswith("-"):
            _, i = _flag_value(rest, i, PIPX_VALUE_FLAGS)
            continue
        if spec is None:
            spec = a
        break
    if spec is None:
        return [ref(" ".join(args), "REVIEW", "no package found in the arguments", "check this entry by hand")]
    return [classify_python(spec, at_syntax=False)]


def parse_docker(args, risks):
    start = 1 if args[:1] == ["run"] else 2 if args[:2] == ["container", "run"] else None
    if start is None:
        return [ref(" ".join(args), "REVIEW", "not a 'run' invocation", "check this entry by hand")]
    rest, i, image = args[start:], 0, None
    while i < len(rest):
        a = rest[i]
        low = a.lower()
        value = None
        if low == "--privileged":
            risks.append("--privileged gives the container full access to the host")
        if a.startswith("-") and "=" in a:
            value = a.split("=", 1)[1]
            flag = a.split("=", 1)[0]
            i += 1
        elif a in DOCKER_VALUE_FLAGS and i + 1 < len(rest):
            flag, value = a, rest[i + 1]
            i += 2
        elif a.startswith("-"):
            i += 1
            continue
        else:
            image = a
            break
        if flag in ("--network", "--net") and value == "host":
            risks.append("host networking")
        if flag == "--pid" and value == "host":
            risks.append("host process namespace")
        if flag in ("-v", "--volume", "--mount") and value:
            src = value.split(",")[0].replace("source=", "").replace("src=", "").split(":")[0]
            if "docker.sock" in value:
                risks.append("Docker socket mounted: control of the host's containers")
            elif src in ("/", "~", "$HOME", "${HOME}") or src.rstrip("/") in (os.path.expanduser("~"),):
                risks.append(f"mounts {src} into the container")
    if image is None:
        return [ref(" ".join(args), "REVIEW", "no image found in the arguments", "check this entry by hand")]
    return [classify_image(image)]


def classify_command(command, args, risks, depth=0):
    base = os.path.basename(str(command)).lower()
    for suffix in (".cmd", ".exe", ".bat", ".ps1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    args = [str(a) for a in args]
    if base in NPX_LIKE:
        return parse_npx(args)
    if args and (base, args[0]) in EXEC_FORMS:
        return parse_npx(args[1:])
    if base == "uvx":
        return parse_uvx(args)
    if base == "uv" and args[:2] == ["tool", "run"]:
        return parse_uvx(args[2:])
    if base == "uv" and args[:1] == ["run"]:
        return [ref("uv " + " ".join(args), "REVIEW", "runs from the local project environment", "check that the project's lockfile is committed and reviewed")]
    if base == "pipx":
        return parse_pipx(args)
    if base in ("docker", "podman"):
        return parse_docker(args, risks)
    if base == "go" and args[:1] == ["run"] and len(args) > 1:
        target = args[1]
        if "@" not in target:
            return [ref(target, "REVIEW", "runs a local Go package", "review the local source")]
        version = target.rsplit("@", 1)[1]
        if version == "latest":
            return [ref(target, "MUTABLE", "'@latest' resolves to the newest release on each run", PIN_NEXT)]
        if EXACT_SEMVER.match(version):
            return [ref(target, "PINNED", "exact module version", "re-review when you raise the pin")]
        return [ref(target, "REVIEW", "branch, commit or pseudo-version", "check this entry by hand")]
    if base in ("cmd",) and args[:1] and args[0].lower() in ("/c", "/k") and len(args) > 1 and depth < 2:
        return classify_command(args[1], args[2:], risks, depth + 1)
    if base in SHELLS:
        script = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-c", "-Command", "/c")), None)
        if script and not SHELL_META.search(script) and depth < 2:
            try:
                parts = shlex.split(script)
            except ValueError:
                parts = []
            if parts:
                inner = classify_command(parts[0], parts[1:], risks, depth + 1)
                return [dict(r, why=r["why"] + " (inside a shell wrapper)") for r in inner]
        return [ref(f"{command} " + " ".join(args), "REVIEW", "shell wrapper hides what actually runs", "declare the program and its arguments directly")]
    if base in LOCAL_RUNNERS:
        target = next((a for a in args if not a.startswith("-")), "")
        if target.startswith(("http://", "https://")):
            return [ref(target, "REVIEW", "runs code straight from a URL", "vendor a reviewed copy or pin a published version")]
        return [ref(f"{base} {target}".strip(), "REVIEW", "local script or module: its version is whatever is on disk", "review the code and its lockfile")]
    return [ref(str(command), "REVIEW", "installed program: its version is whatever is on PATH", "record which version was reviewed and how it is installed")]


def is_reference(value):
    stripped = REFERENCE.sub("", value)
    return bool(REFERENCE.search(value)) and not TOKEN_SHAPE.match(stripped.strip()) and not KNOWN_TOKEN.search(stripped)


def _looks_like_path_or_url(value):
    return "://" in value or value.startswith(("/", "./", "../", "~")) or bool(re.match(r"^[A-Za-z]:\\", value))


def secret_finding(name, value):
    """Return a message when a literal looks like a secret, else None. Never includes the value."""
    if not isinstance(value, str) or not value.strip() or is_reference(value):
        return None
    v = value.strip()
    if KNOWN_TOKEN.search(v):
        return f"{name} holds a literal value ({len(value)} characters) shaped like a known token format"
    if PLACEHOLDER.search(v) or _looks_like_path_or_url(v) or v.isdigit() or v.lower() in ("true", "false", "null"):
        return None
    if (SECRET_NAME.search(name or "") and len(v) >= 8) or TOKEN_SHAPE.match(v):
        return f"{name} holds a literal value ({len(value)} characters) that looks like a credential"
    return None


def is_loopback(host):
    if host in ("localhost",) or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Audit:
    def __init__(self):
        self.configs, self.findings, self.errors = [], [], []

    def add(self, severity, code, path, server, message):
        self.findings.append({"severity": severity, "code": code, "config": path, "server": server, "message": message})

    def review_file(self, path):
        try:
            data = load_config(path)
        except ConfigError as exc:
            self.errors.append({"config": str(path), "error": str(exc)})
            return
        entry = {"path": str(path), "servers": []}
        for flag_path in walk_flags(data):
            self.add("high", "AUTO-ENABLE-ALL", str(path), "-",
                     f"{flag_path} is true: every server declared in a project's .mcp.json starts without a per-server approval")
        for json_path, name, server in walk_servers(data):
            entry["servers"].append(self.review_server(str(path), json_path, name, server))
        self.configs.append(entry)

    def review_server(self, path, json_path, name, server):
        risks = []
        transport = str(server.get("type") or server.get("transport") or ("http" if "url" in server else "stdio"))
        disabled = server.get("disabled") is True
        refs = []
        url = server.get("url") or server.get("serverUrl")
        if isinstance(url, str) and url:
            refs.append(self.review_url(path, name, url))
        elif isinstance(server.get("command"), str):
            args = server.get("args") if isinstance(server.get("args"), list) else []
            refs = classify_command(server["command"], args, risks)
            self.review_args(path, name, [str(a) for a in args])
        else:
            refs.append(ref("-", "REVIEW", "no command or url", "check this entry by hand"))
        for r in refs:
            if r["result"] == "MUTABLE":
                self.add("high", "MUTABLE-REF", path, name, f"{r['reference']}: {r['why']}")
            elif r["result"] == "RANGE":
                self.add("medium", "RANGE-REF", path, name, f"{r['reference']}: {r['why']}")
            elif r["result"] == "REVIEW":
                self.add("review", "REVIEW-REF", path, name, f"{r['reference']}: {r['why']}")
            elif r["result"] == "REMOTE":
                self.add("info", "REMOTE-SERVER", path, name, f"{r['reference']}: {r['why']}")
        for risk in risks:
            self.add("high", "BROAD-CONTAINER", path, name, risk)
        for field in ("env", "headers", "environment"):
            block = server.get(field)
            if isinstance(block, dict):
                for key, value in block.items():
                    msg = secret_finding(f"{field}.{key}", value)
                    if msg:
                        self.add("high", "LITERAL-SECRET", path, name, msg + "; reference an environment variable or secret store instead")
        approve = server.get("autoApprove", server.get("alwaysAllow"))
        if approve is True or (isinstance(approve, list) and "*" in approve):
            self.add("high", "AUTO-APPROVE", path, name, "every tool of this server runs without a confirmation prompt")
        elif isinstance(approve, list) and approve:
            self.add("medium", "AUTO-APPROVE", path, name, f"{len(approve)} tool(s) run without a confirmation prompt: {', '.join(map(str, approve[:5]))}")
        return {"name": name, "json_path": json_path, "transport": transport, "disabled": disabled, "references": refs}

    def review_args(self, path, name, args):
        consumed = set()
        for i, a in enumerate(args):
            if i in consumed:
                continue
            if a in ("/", "~", "$HOME", "${HOME}", "%USERPROFILE%") or re.fullmatch(r"[A-Za-z]:\\?", a):
                self.add("medium", "BROAD-PATH", path, name, f"argument '{a}' gives the server the whole disk or home folder; pass the project folder only")
            flag, _, inline = a.partition("=")
            if SECRET_FLAGS.match(flag):
                value = inline
                if not inline and i + 1 < len(args) and not args[i + 1].startswith("-"):
                    value = args[i + 1]
                    consumed.add(i + 1)
                msg = secret_finding(flag.lstrip("-"), value) if value else None
                if msg:
                    self.add("high", "LITERAL-SECRET", path, name, f"argument {msg}; arguments also show up in process listings")
            elif KNOWN_TOKEN.search(a):
                self.add("high", "LITERAL-SECRET", path, name, f"argument {i + 1} contains a token-shaped value ({len(a)} characters)")

    def review_url(self, path, name, url):
        if REFERENCE.search(url):
            return ref(url.split("?")[0], "REVIEW", "URL is templated", "check the value that is substituted")
        parts = urlsplit(url)
        try:
            port = parts.port
        except ValueError:
            return ref(url.split("?")[0], "REVIEW", "URL has an invalid port", "check this entry by hand")
        shown = f"{parts.scheme}://{parts.hostname or ''}{(':' + str(port)) if port else ''}{parts.path}"
        if parts.password or (parts.username and parts.scheme in ("http", "https")):
            self.add("high", "URL-CREDENTIALS", path, name, "URL carries user credentials; use an auth header from the environment or the client's OAuth flow")
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if SECRET_NAME.search(key) and value and not REFERENCE.search(value):
                self.add("high", "URL-CREDENTIALS", path, name, f"URL query parameter '{key}' holds a literal credential ({len(value)} characters)")
        host = parts.hostname or ""
        if parts.scheme == "http" and not is_loopback(host):
            self.add("high", "PLAINTEXT-HTTP", path, name, f"remote server over plain HTTP ({host}): traffic and tokens travel unencrypted")
        if parts.scheme not in ("http", "https", "ws", "wss"):
            return ref(shown, "REVIEW", f"unexpected URL scheme '{parts.scheme}'", "check this entry by hand")
        where = "on this machine" if is_loopback(host) else "operated by someone else"
        return ref(shown, "REMOTE", f"remote server {where}: its code is not visible from the config", "confirm the operator, auth scopes and data handling")

    def summary(self):
        counts = {k: 0 for k in SEVERITY}
        for f in self.findings:
            counts[f["severity"]] += 1
        return counts


LIMITS = ("No server was started and no package was resolved. A mutable reference means the config does not fix which code "
          "runs later; it is not evidence of a compromise. PINNED covers only the direct package or image, not its dependencies, "
          "provenance or behavior. A clean result is not a full MCP security review: read what each server does before enabling it.")


def render(audit):
    lines = ["MCP configuration review (static)"]
    for cfg in audit.configs:
        lines.append("")
        note = f"  {cfg['note']}" if cfg.get("note") else ""
        lines.append(f"config {cfg['path']}  ({len(cfg['servers'])} server{'s' if len(cfg['servers']) != 1 else ''}){note}")
        for s in cfg["servers"]:
            for r in s["references"]:
                flag = " [disabled]" if s["disabled"] else ""
                lines.append(f"  {s['name']}{flag}  {s['transport']}  {r['reference']}  {r['result']}")
                lines.append(f"      why: {r['why']}; next: {r['next']}")
    for err in audit.errors:
        lines.append("")
        lines.append(f"ERROR {err['config']}: {err['error']}")
    if audit.findings:
        lines.append("")
        lines.append("findings")
        for f in sorted(audit.findings, key=lambda f: (-SEVERITY[f["severity"]], f["config"], f["server"])):
            lines.append(f"  {f['severity'].upper():6} {f['code']:16} {f['config']} [{f['server']}] {f['message']}")
    counts = audit.summary()
    lines.append("")
    lines.append("summary: " + ", ".join(f"{counts[k]} {k}" for k in ("high", "medium", "review", "info")))
    lines.append("")
    lines.append(LIMITS)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Statically review MCP server declarations (.mcp.json, editor and agent settings). "
                    "Never starts servers or resolves packages. Exit 0 = nothing at or above --fail-on, "
                    "1 = findings at or above it, 2 = usage error, missing path or unparsable file.")
    parser.add_argument("paths", nargs="+", help="configuration files, or project folders to search for known MCP config files")
    parser.add_argument("--recursive", action="store_true", help="in folders, also find *mcp*.json files up to 4 levels deep")
    parser.add_argument("--fail-on", choices=("high", "medium", "review"), default="high", help="lowest severity that makes the exit code 1 (default: high)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)
    audit, missing = Audit(), []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files = discover(p, args.recursive)
            if not files:
                audit.configs.append({"path": str(p), "servers": [], "note": "no MCP configuration file found"})
            for f in files:
                audit.review_file(f)
        elif p.is_file():
            audit.review_file(p)
        else:
            missing.append(raw)
    for raw in missing:
        audit.errors.append({"config": raw, "error": "no such file or folder"})
    if args.json:
        print(json.dumps({"configs": audit.configs, "findings": audit.findings, "errors": audit.errors,
                          "summary": audit.summary(), "limits": LIMITS}, indent=2))
    else:
        print(render(audit))
    if audit.errors:
        return 2
    threshold = SEVERITY[args.fail_on]
    return 1 if any(SEVERITY[f["severity"]] >= threshold for f in audit.findings) else 0


if __name__ == "__main__":
    sys.exit(main())
