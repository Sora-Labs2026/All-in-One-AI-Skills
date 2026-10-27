#!/usr/bin/env python3
"""ProductCraft Stacks: read-only stack detector.

Walks a repository to a bounded depth and reads only known manifest, lockfile,
tool-configuration, task-runner and CI files. For each subproject it reports
the stack and framework hints, version pins with the file each came from, the
package manager and lockfiles, the tools configured, the commands the project
defines, ecosystem default commands, and conflicts worth a look (two lockfiles
for one ecosystem, a build without its wrapper, a manifest without a lock).

It never runs project code, never uses the network, never writes files and
never opens files whose names look like credentials (.env files, keys,
certificates, credential or secret stores). Secret-looking values in commands
it reports are redacted. Output is deterministic.

Exit status: 0 when at least one stack was found, 1 when none was, 2 for a bad
argument or a missing root.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

try:  # Python 3.11+
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover - older interpreters use the regex fallbacks
    tomllib = None  # type: ignore

VERSION = "1.0.0"
MAX_BYTES = 1_000_000
MAX_CI_COMMANDS = 40

SKIP_DIRS = {
    "node_modules", "vendor", "third_party", "venv", ".venv", "env", "__pycache__", "site-packages",
    "target", "build", "dist", "out", "obj", "bin", "coverage", "Pods", "DerivedData", ".build",
    ".gradle", ".pio", ".tox", ".nox", ".terraform", ".next", ".nuxt", ".svelte-kit", ".angular",
    ".dart_tool", ".cache", ".git", ".hg", ".svn", ".idea", ".vscode",
}
ALLOWED_HIDDEN = {".github", ".circleci", ".cargo", ".config", ".devcontainer"}
SENSITIVE = [re.compile(p, re.I) for p in (
    r"^\.env", r"\.pem$", r"\.key$", r"\.p12$", r"\.pfx$", r"^id_(rsa|dsa|ecdsa|ed25519)",
    r"credential", r"secret", r"\.keystore$", r"\.jks$", r"^wp-config", r"\.npmrc$", r"\.pypirc$", r"\.netrc$",
)]

PY_FRAMEWORKS = {"django": "Django", "djangorestframework": "Django REST Framework", "fastapi": "FastAPI",
                 "flask": "Flask", "celery": "Celery", "sqlalchemy": "SQLAlchemy", "pydantic": "Pydantic"}
GO_FRAMEWORKS = {"github.com/gin-gonic/gin": "Gin", "github.com/labstack/echo": "Echo", "github.com/go-chi/chi": "chi",
                 "github.com/gofiber/fiber": "Fiber", "github.com/spf13/cobra": "Cobra", "google.golang.org/grpc": "gRPC"}
RUST_FRAMEWORKS = {"tokio": "Tokio", "axum": "Axum", "actix-web": "Actix Web", "clap": "clap", "tauri": "Tauri",
                   "embassy-executor": "Embassy", "cortex-m": "cortex-m", "rtic": "RTIC", "bevy": "Bevy"}
NODE_FRAMEWORKS = {"next": "Next.js", "nuxt": "Nuxt", "react": "React", "vue": "Vue", "@angular/core": "Angular",
                   "svelte": "Svelte", "@sveltejs/kit": "SvelteKit", "express": "Express", "@nestjs/core": "NestJS",
                   "fastify": "Fastify", "expo": "Expo", "react-native": "React Native", "mjml": "MJML",
                   "typescript": "TypeScript"}
PHP_PACKAGES = {"laravel/framework": "Laravel", "symfony/framework-bundle": "Symfony"}
PHP_TOOLS = {"phpstan/phpstan": "phpstan", "larastan/larastan": "larastan", "nunomaduro/larastan": "larastan",
             "vimeo/psalm": "psalm", "pestphp/pest": "pest", "phpunit/phpunit": "phpunit", "laravel/pint": "pint",
             "friendsofphp/php-cs-fixer": "php-cs-fixer", "rector/rector": "rector"}
RUBY_GEMS = {"rails": "Rails", "sidekiq": "Sidekiq", "solid_queue": "Solid Queue", "hanami": "Hanami", "sinatra": "Sinatra"}
RUBY_TOOLS = {"rspec-rails": "rspec", "rspec": "rspec", "rubocop": "rubocop", "standard": "standard",
              "brakeman": "brakeman", "sorbet": "sorbet", "steep": "steep", "bundler-audit": "bundler-audit"}

SECRET_ASSIGN = re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)(\s*[=:]\s*|\s+)([^\s'\"]+)")
LONG_OPAQUE = re.compile(r"[A-Za-z0-9+/_\-]{32,}={0,2}")


# --- small helpers -----------------------------------------------------------------------------

def is_sensitive(name: str) -> bool:
    return any(p.search(name) for p in SENSITIVE)


def read_text(path: str) -> Optional[str]:
    name = os.path.basename(path)
    if is_sensitive(name):
        return None
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def load_toml(text: Optional[str]) -> Optional[dict]:
    if text is None or tomllib is None:
        return None
    try:
        return tomllib.loads(text)
    except Exception:  # malformed files are reported through regex fallbacks only
        return None


def load_json(text: Optional[str]) -> Optional[dict]:
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _looks_secret(token: str) -> bool:
    if len(token) < 32 or "/" in token:
        return False
    has_digit = any(c.isdigit() for c in token)
    has_alpha = any(c.isalpha() for c in token)
    mixed_case = any(c.islower() for c in token) and any(c.isupper() for c in token)
    return has_digit and has_alpha and (mixed_case or sum(c.isdigit() for c in token) >= len(token) // 6)


def redact(cmd: str) -> str:
    """Hide values assigned to secret-like names and long opaque tokens; keep $VAR and ${{ }} references."""
    cmd = SECRET_ASSIGN.sub(
        lambda m: m.group(0) if m.group(3).startswith(("$", "<")) else f"{m.group(1)}{m.group(2)}<redacted>", cmd)
    return LONG_OPAQUE.sub(lambda m: "<redacted>" if _looks_secret(m.group(0)) else m.group(0), cmd)


def find_up(d: str, root: str, names: Tuple[str, ...]) -> Optional[Tuple[str, str]]:
    """Nearest ancestor of d (excluding d, up to root) holding one of names: (relative dir, name)."""
    cur = os.path.dirname(d)
    while len(cur) >= len(root) and cur.startswith(root):
        for n in names:
            if os.path.isfile(os.path.join(cur, n)):
                return rel(root, cur), n
        if cur == root:
            break
        cur = os.path.dirname(cur)
    return None


def regex1(pattern: str, text: Optional[str], flags: int = re.M) -> Optional[str]:
    if not text:
        return None
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def first_line(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            return line
    return None


def dep_names_from_requirements(text: str) -> List[str]:
    names = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)", line)
        if m:
            names.append(m.group(1).lower().replace("_", "-"))
    return names


def dep_name(spec: str) -> str:
    m = re.match(r"\s*([A-Za-z0-9_.\-]+)", spec)
    return m.group(1).lower().replace("_", "-") if m else ""


class Project:
    def __init__(self, path: str, stack: str):
        self.path = path
        self.stack = stack
        self.frameworks: List[str] = []
        self.versions: List[Tuple[str, str, str]] = []
        self.package_manager: Optional[str] = None
        self.lockfiles: List[str] = []
        self.tools: List[str] = []
        self.commands: List[Tuple[str, str]] = []
        self.defaults: List[str] = []
        self.notes: List[str] = []

    def version(self, name: str, value: Optional[str], source: str) -> None:
        if value:
            item = (name, value.strip().strip("'\""), source)
            if item not in self.versions:
                self.versions.append(item)

    def add(self, attr: str, *values: str) -> None:
        target = getattr(self, attr)
        for v in values:
            if v and v not in target:
                target.append(v)

    def as_dict(self) -> dict:
        return {
            "path": self.path, "stack": self.stack, "frameworks": sorted(self.frameworks),
            "versions": [{"name": n, "value": v, "source": s} for n, v, s in self.versions],
            "package_manager": self.package_manager, "lockfiles": sorted(self.lockfiles),
            "tools": sorted(self.tools), "commands": [{"command": c, "source": s} for c, s in self.commands],
            "defaults": self.defaults, "notes": self.notes,
        }


def rel(root: str, path: str) -> str:
    r = os.path.relpath(path, root)
    return "." if r == "." else r.replace(os.sep, "/")


def src(prefix: str, name: str) -> str:
    return name if prefix == "." else f"{prefix}/{name}"


# --- task runners -------------------------------------------------------------------------------

def task_runner_commands(d: str, files: set, prefix: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for name in ("Makefile", "makefile", "GNUmakefile"):
        if name in files:
            text = read_text(os.path.join(d, name)) or ""
            targets = []
            for m in re.finditer(r"^([A-Za-z0-9][A-Za-z0-9_.\-/]*)\s*:(?!=)", text, re.M):
                t = m.group(1)
                if t not in targets and not t.startswith(".") and "%" not in t:
                    targets.append(t)
            out += [(f"make {t}", src(prefix, name)) for t in targets[:25]]
            break
    if "justfile" in files or "Justfile" in files:
        name = "justfile" if "justfile" in files else "Justfile"
        text = read_text(os.path.join(d, name)) or ""
        recipes = []
        for m in re.finditer(r"^@?([A-Za-z0-9][A-Za-z0-9_\-]*)(?:\s+[^:\n]*)?:(?!=)", text, re.M):
            if m.group(1) not in recipes and m.group(1) not in ("set", "export", "alias", "import", "mod"):
                recipes.append(m.group(1))
        out += [(f"just {r}", src(prefix, name)) for r in recipes[:25]]
    for name in ("Taskfile.yml", "Taskfile.yaml"):
        if name in files:
            text = read_text(os.path.join(d, name)) or ""
            block = re.search(r"^tasks:\s*\n((?:[ \t]+.*\n?|\s*\n)*)", text, re.M)
            if block:
                indent = None
                tasks = []
                for line in block.group(1).splitlines():
                    m = re.match(r"^([ \t]+)([A-Za-z0-9_:\-]+):\s*(?:#.*)?$", line) or re.match(r"^([ \t]+)([A-Za-z0-9_:\-]+):\s+\S", line)
                    if not m:
                        continue
                    if indent is None:
                        indent = m.group(1)
                    if m.group(1) == indent and m.group(2) not in tasks:
                        tasks.append(m.group(2))
                out += [(f"task {t}", src(prefix, name)) for t in tasks[:25]]
            break
    return out


# --- detectors ----------------------------------------------------------------------------------

def detect_python(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    reqs = sorted(f for f in files if fnmatch.fnmatch(f, "requirements*.txt"))
    markers = {"pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "manage.py"} & files
    if not markers and not reqs:
        return None
    p = Project(prefix, "Python")
    deps: List[str] = []
    text = read_text(os.path.join(d, "pyproject.toml")) if "pyproject.toml" in files else None
    data = load_toml(text)
    if data is not None:
        proj = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
        p.version("requires-python", proj.get("requires-python"), src(prefix, "pyproject.toml"))
        deps += [dep_name(s) for s in proj.get("dependencies", []) if isinstance(s, str)]
        for group in (proj.get("optional-dependencies") or {}).values():
            deps += [dep_name(s) for s in group if isinstance(s, str)]
        for group in (data.get("dependency-groups") or {}).values():
            deps += [dep_name(s) for s in group if isinstance(s, str)]
        tool = data.get("tool", {}) if isinstance(data.get("tool"), dict) else {}
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            pdeps = poetry.get("dependencies") or {}
            p.version("python (poetry)", pdeps.get("python") if isinstance(pdeps.get("python"), str) else None,
                      src(prefix, "pyproject.toml"))
            deps += [k.lower() for k in pdeps]
            for grp in (poetry.get("group") or {}).values():
                if isinstance(grp, dict):
                    deps += [k.lower() for k in (grp.get("dependencies") or {})]
            p.package_manager = "poetry"
        for t in ("ruff", "black", "isort", "mypy", "pyright", "pytest", "coverage", "pylint", "flake8"):
            if t in tool:
                p.add("tools", t)
        if "uv" in tool:
            p.package_manager = p.package_manager or "uv"
        if "pdm" in tool:
            p.package_manager = p.package_manager or "pdm"
        if "hatch" in tool:
            p.add("tools", "hatch")
        backend = (data.get("build-system") or {}).get("build-backend")
        if backend:
            p.version("build-backend", backend, src(prefix, "pyproject.toml"))
    elif text:
        p.version("requires-python", regex1(r"^requires-python\s*=\s*['\"]([^'\"]+)", text), src(prefix, "pyproject.toml"))
        for t in ("ruff", "black", "isort", "mypy", "pyright", "pylint"):
            if re.search(rf"^\[tool\.{t}[\].]", text, re.M):
                p.add("tools", t)
        if re.search(r"^\[tool\.pytest", text, re.M):
            p.add("tools", "pytest")
        if re.search(r"^\[tool\.poetry", text, re.M):
            p.package_manager = "poetry"
        deps += [n.lower() for n in re.findall(r"^\s*['\"]([A-Za-z0-9_.\-]+)", text, re.M)]
    if "setup.cfg" in files:
        cfg = read_text(os.path.join(d, "setup.cfg")) or ""
        p.version("python_requires", regex1(r"^python_requires\s*=\s*(.+)$", cfg), src(prefix, "setup.cfg"))
        for sect, tool in (("mypy", "mypy"), ("flake8", "flake8"), ("tool:pytest", "pytest"), ("isort", "isort")):
            if re.search(rf"^\[{re.escape(sect)}\]", cfg, re.M):
                p.add("tools", tool)
    for r in reqs:
        deps += dep_names_from_requirements(read_text(os.path.join(d, r)) or "")
    if ".python-version" in files:
        p.version(".python-version", first_line(read_text(os.path.join(d, ".python-version"))), src(prefix, ".python-version"))
    for name, tool in (("ruff.toml", "ruff"), (".ruff.toml", "ruff"), ("mypy.ini", "mypy"), (".mypy.ini", "mypy"),
                       ("pyrightconfig.json", "pyright"), ("pytest.ini", "pytest"), ("tox.ini", "tox"),
                       ("noxfile.py", "nox"), (".flake8", "flake8"), (".pre-commit-config.yaml", "pre-commit")):
        if name in files:
            p.add("tools", tool)
    lock_pms = {"uv.lock": "uv", "poetry.lock": "poetry", "pdm.lock": "pdm", "Pipfile.lock": "pipenv"}
    locks = [(n, pm) for n, pm in lock_pms.items() if n in files]
    p.add("lockfiles", *[n for n, _ in locks])
    if not locks:
        up = find_up(d, root, tuple(lock_pms))
        if up:
            locks = [(src(up[0], up[1]), lock_pms[up[1]])]
            p.add("lockfiles", locks[0][0] + " (workspace root)")
    if locks:
        if p.package_manager not in [pm for _, pm in locks]:
            p.package_manager = locks[0][1]
        if len(locks) > 1:
            p.notes.append("several Python lockfiles (" + ", ".join(n for n, _ in locks) + "): confirm which tool CI uses before installing")
    if not p.package_manager:
        if "Pipfile" in files:
            p.package_manager = "pipenv"
        elif reqs:
            p.package_manager = "pip (virtual environment)"
            texts = [read_text(os.path.join(d, r)) or "" for r in reqs]
            reqlines = [ln.split("#", 1)[0].strip() for t in texts for ln in t.splitlines()]
            reqlines = [ln for ln in reqlines if ln and not ln.startswith("-")]
            if reqlines and all("==" in ln for ln in reqlines):
                p.add("lockfiles", *reqs)
            else:
                p.notes.append("requirements are not fully pinned (==): installs can differ between machines")
    for dep in deps:
        if dep in PY_FRAMEWORKS:
            p.add("frameworks", PY_FRAMEWORKS[dep])
        if dep in ("pytest", "mypy", "ruff", "black", "pyright"):
            p.add("tools", dep)
    if "manage.py" in files:
        p.add("frameworks", "Django")
    run = {"uv": "uv run ", "poetry": "poetry run ", "pdm": "pdm run ", "pipenv": "pipenv run "}.get(p.package_manager or "", "")
    if "pytest" in p.tools or os.path.isdir(os.path.join(d, "tests")):
        p.defaults.append(f"{run}pytest")
    elif "Django" in p.frameworks:
        p.defaults.append(f"{run}python manage.py test")
    else:
        p.defaults.append(f"{run}python -m unittest discover")
    if "ruff" in p.tools:
        p.defaults.append(f"{run}ruff check .")
    if "black" in p.tools:
        p.defaults.append(f"{run}black --check .")
    elif "ruff" in p.tools:
        p.defaults.append(f"{run}ruff format --check .")
    for t in ("mypy", "pyright"):
        if t in p.tools:
            p.defaults.append(f"{run}{t}" + (" ." if t == "mypy" else ""))
    if "Django" in p.frameworks and "manage.py" in files:
        p.defaults += [f"{run}python manage.py check", f"{run}python manage.py makemigrations --check --dry-run"]
    return p


def detect_go(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    if "go.mod" not in files and "go.work" not in files:
        return None
    p = Project(prefix, "Go")
    if "go.mod" in files:
        text = read_text(os.path.join(d, "go.mod")) or ""
        p.version("module", regex1(r"^module\s+(\S+)", text), src(prefix, "go.mod"))
        p.version("go", regex1(r"^go\s+(\S+)", text), src(prefix, "go.mod"))
        tc = regex1(r"^toolchain\s+(\S+)", text)
        p.version("toolchain", tc, src(prefix, "go.mod"))
        if tc:
            p.notes.append("toolchain line: with GOTOOLCHAIN=auto the go command may download that toolchain (network)")
        for mod, fw in GO_FRAMEWORKS.items():
            if mod in text:
                p.add("frameworks", fw)
        if re.search(r"^tool\s*[(\S]", text, re.M):
            p.add("tools", "go tool directive")
    if "go.work" in files:
        p.add("frameworks", "go.work workspace")
    p.package_manager = "go modules"
    p.add("lockfiles", *[n for n in ("go.sum",) if n in files])
    if os.path.isfile(os.path.join(d, "vendor", "modules.txt")):
        p.add("lockfiles", "vendor/modules.txt")
        p.notes.append("vendored dependencies: run 'go mod vendor' after dependency changes")
    for name in (".golangci.yml", ".golangci.yaml", ".golangci.toml", ".golangci.json"):
        if name in files:
            text = read_text(os.path.join(d, name)) or ""
            p.add("tools", "golangci-lint v2 config" if re.search(r"^version:\s*['\"]?2", text, re.M) else "golangci-lint")
    p.defaults = ["gofmt -l .", "go vet ./...", "go build ./...", "go test -race ./..."]
    if any(t.startswith("golangci-lint") for t in p.tools):
        p.defaults.append("golangci-lint run")
    p.defaults.append("govulncheck ./...  (if installed)")
    return p


def detect_rust(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    if "Cargo.toml" not in files:
        return None
    p = Project(prefix, "Rust")
    text = read_text(os.path.join(d, "Cargo.toml"))
    data = load_toml(text)
    deps: List[str] = []
    if data is not None:
        pkg = data.get("package") if isinstance(data.get("package"), dict) else {}
        ws = data.get("workspace") if isinstance(data.get("workspace"), dict) else None
        wpkg = (ws or {}).get("package") if isinstance((ws or {}).get("package"), dict) else {}
        for key in ("edition", "rust-version"):
            val = pkg.get(key)
            if isinstance(val, dict) and val.get("workspace"):
                val = None
            p.version(key, val if isinstance(val, str) else None, src(prefix, "Cargo.toml"))
            p.version(f"workspace {key}", wpkg.get(key) if isinstance(wpkg.get(key), str) else None, src(prefix, "Cargo.toml"))
        if ws is not None:
            p.add("frameworks", "Cargo workspace")
            deps += list(((ws.get("dependencies") or {})).keys())
        deps += list((data.get("dependencies") or {}).keys()) + list((data.get("dev-dependencies") or {}).keys())
        if "lints" in data:
            p.add("tools", "[lints] table")
    elif text:
        p.version("edition", regex1(r"^edition\s*=\s*['\"]([^'\"]+)", text), src(prefix, "Cargo.toml"))
        p.version("rust-version", regex1(r"^rust-version\s*=\s*['\"]([^'\"]+)", text), src(prefix, "Cargo.toml"))
        deps += re.findall(r"^([A-Za-z0-9_\-]+)\s*=", text, re.M)
    for dep in deps:
        if dep in RUST_FRAMEWORKS:
            p.add("frameworks", RUST_FRAMEWORKS[dep])
    for name in ("rust-toolchain.toml", "rust-toolchain"):
        if name in files:
            t = read_text(os.path.join(d, name)) or ""
            p.version("toolchain channel", regex1(r"^channel\s*=\s*['\"]([^'\"]+)", t) or (None if name.endswith(".toml") else first_line(t)), src(prefix, name))
    cfg = os.path.join(d, ".cargo", "config.toml")
    if os.path.isfile(cfg):
        target = regex1(r"^target\s*=\s*['\"]([^'\"]+)", read_text(cfg))
        if target:
            p.version("build target", target, src(prefix, ".cargo/config.toml"))
            if target.startswith(("thumb", "riscv32", "xtensa")):
                p.add("frameworks", "embedded (no_std target)")
    if "memory.x" in files:
        p.add("frameworks", "embedded (no_std target)")
    p.package_manager = "cargo"
    if "Cargo.lock" in files:
        p.add("lockfiles", "Cargo.lock")
    else:
        up = find_up(d, root, ("Cargo.lock",))
        if up:
            p.add("lockfiles", src(up[0], up[1]) + " (workspace root)")
    for name, tool in (("clippy.toml", "clippy config"), (".clippy.toml", "clippy config"), ("rustfmt.toml", "rustfmt config"),
                       (".rustfmt.toml", "rustfmt config"), ("deny.toml", "cargo-deny"), ("nextest.toml", "nextest")):
        if name in files:
            p.add("tools", tool)
    p.defaults = ["cargo fmt --check", "cargo clippy --all-targets --all-features", "cargo test"]
    if "cargo-deny" in p.tools:
        p.defaults.append("cargo deny check")
    return p


def detect_jvm(d: str, files: set, prefix: str, root: str) -> List[Project]:
    out: List[Project] = []
    if "pom.xml" in files:
        p = Project(prefix, "JVM (Maven)")
        t = read_text(os.path.join(d, "pom.xml")) or ""
        for tag in ("maven.compiler.release", "maven.compiler.source", "java.version", "kotlin.version"):
            p.version(tag, regex1(rf"<{re.escape(tag)}>\s*([^<\s]+)\s*</", t), src(prefix, "pom.xml"))
        parent = re.search(r"<parent>(.*?)</parent>", t, re.S)
        if parent and "spring-boot-starter-parent" in parent.group(1):
            p.add("frameworks", "Spring Boot")
            p.version("spring-boot-starter-parent", regex1(r"<version>\s*([^<\s]+)\s*</version>", parent.group(1)), src(prefix, "pom.xml"))
        elif "spring-boot" in t:
            p.add("frameworks", "Spring Boot")
        if "kotlin-maven-plugin" in t or "kotlin-stdlib" in t:
            p.add("frameworks", "Kotlin")
        for plug, tool in (("maven-checkstyle-plugin", "checkstyle"), ("spotbugs-maven-plugin", "spotbugs"), ("maven-pmd-plugin", "pmd"),
                           ("spotless-maven-plugin", "spotless"), ("jacoco-maven-plugin", "jacoco"), ("error_prone", "error-prone"),
                           ("dependency-check-maven", "dependency-check"), ("flyway", "flyway"), ("liquibase", "liquibase")):
            if plug in t:
                p.add("tools", tool)
        up = None if "mvnw" in files else find_up(d, root, ("mvnw",))
        if "mvnw" in files:
            p.package_manager = "maven wrapper"
            p.defaults = ["./mvnw -q verify"]
        elif up:
            p.package_manager = f"maven wrapper ({src(up[0], 'mvnw')})"
            p.defaults = [f"./mvnw -q -pl {os.path.relpath(d, os.path.join(root, up[0])).replace(os.sep, '/')} -am verify  (run from {up[0]})"]
        else:
            p.package_manager = "maven"
            p.notes.append("no Maven wrapper (mvnw): use the Maven version CI uses")
            p.defaults = ["mvn -q verify"]
        mvn = "./mvnw" if (up or "mvnw" in files) else "mvn"
        if "spotless" in p.tools:
            p.defaults.append(f"{mvn} spotless:check")
        out.append(p)
    gradle_files = [n for n in ("build.gradle.kts", "build.gradle", "settings.gradle.kts", "settings.gradle") if n in files]
    if gradle_files:
        p = Project(prefix, "JVM (Gradle)")
        text = "\n".join(read_text(os.path.join(d, n)) or "" for n in gradle_files)
        main = next((n for n in gradle_files if n.startswith("build.")), gradle_files[0])
        p.version("java toolchain", regex1(r"JavaLanguageVersion\.of\(\s*(\d+)\s*\)", text) or regex1(r"jvmToolchain\(\s*(\d+)\s*\)", text), src(prefix, main))
        p.version("sourceCompatibility", regex1(r"sourceCompatibility\s*=\s*(?:JavaVersion\.VERSION_)?['\"]?([\d_.]+)", text), src(prefix, main))
        boot = regex1(r"id\s*\(?\s*['\"]org\.springframework\.boot['\"]\s*\)?\s*version\s*['\"]([^'\"]+)", text)
        if boot or "org.springframework.boot" in text:
            p.add("frameworks", "Spring Boot")
            p.version("spring boot plugin", boot, src(prefix, main))
        kotlin = regex1(r"kotlin\s*\(\s*['\"](?:jvm|multiplatform|android)['\"]\s*\)\s*version\s*['\"]([^'\"]+)", text)
        if kotlin or re.search(r"kotlin\s*\(|org\.jetbrains\.kotlin", text):
            p.add("frameworks", "Kotlin")
            p.version("kotlin plugin", kotlin, src(prefix, main))
        if "com.android.application" in text or "com.android.library" in text:
            p.add("frameworks", "Android")
        for key, tool in (("spotless", "spotless"), ("detekt", "detekt"), ("ktlint", "ktlint"), ("checkstyle", "checkstyle"),
                          ("jacoco", "jacoco"), ("errorprone", "error-prone"), ("flyway", "flyway")):
            if key in text:
                p.add("tools", tool)
        cat = os.path.join(d, "gradle", "libs.versions.toml")
        if os.path.isfile(cat):
            ctext = read_text(cat) or ""
            p.add("lockfiles", "gradle/libs.versions.toml")
            for key in ("kotlin", "spring-boot", "springBoot", "springboot", "java", "jvm", "agp"):
                p.version(f"catalog {key}", regex1(rf"^{re.escape(key)}\s*=\s*['\"]([^'\"]+)", ctext), src(prefix, "gradle/libs.versions.toml"))
        if "gradle.lockfile" in files:
            p.add("lockfiles", "gradle.lockfile")
        up = None if "gradlew" in files else find_up(d, root, ("gradlew",))
        g = "./gradlew" if ("gradlew" in files or up) else "gradle"
        if "gradlew" in files:
            p.package_manager = "gradle wrapper"
            p.defaults = ["./gradlew check"]
        elif up:
            sub = os.path.relpath(d, os.path.join(root, up[0])).replace(os.sep, "/").replace("/", ":")
            p.package_manager = f"gradle wrapper ({src(up[0], 'gradlew')})"
            p.defaults = [f"./gradlew :{sub}:check  (run from {up[0]}; the Gradle project path may differ, see settings.gradle)"]
        else:
            p.package_manager = "gradle"
            p.notes.append("no Gradle wrapper (gradlew): use the Gradle version CI uses")
            p.defaults = ["gradle check"]
        if "spotless" in p.tools:
            p.defaults.append(f"{g} spotlessCheck")
        if "detekt" in p.tools:
            p.defaults.append(f"{g} detekt")
        out.append(p)
    return out


def detect_dotnet(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    projs = sorted(f for f in files if f.endswith((".csproj", ".fsproj", ".vbproj")))
    slns = sorted(f for f in files if f.endswith((".sln", ".slnx")))
    if not projs and not slns and "global.json" not in files:
        return None
    p = Project(prefix, ".NET")
    for name in projs + [n for n in ("Directory.Build.props",) if n in files]:
        t = read_text(os.path.join(d, name)) or ""
        for tag in ("TargetFramework", "TargetFrameworks", "LangVersion", "Nullable", "TreatWarningsAsErrors", "AnalysisLevel"):
            p.version(tag, regex1(rf"<{tag}>\s*([^<]+?)\s*</{tag}>", t), src(prefix, name))
        if "Microsoft.NET.Sdk.Web" in t:
            p.add("frameworks", "ASP.NET Core")
        if "Microsoft.EntityFrameworkCore" in t:
            p.add("frameworks", "EF Core")
        if "Microsoft.NET.Sdk.BlazorWebAssembly" in t or "Microsoft.AspNetCore.Components" in t:
            p.add("frameworks", "Blazor")
        for pkg, tool in (("xunit", "xunit"), ("NUnit", "nunit"), ("MSTest", "mstest"), ("StyleCop", "stylecop")):
            if f'Include="{pkg}' in t:
                p.add("tools", tool)
    gj = load_json(read_text(os.path.join(d, "global.json"))) if "global.json" in files else None
    if gj and isinstance(gj.get("sdk"), dict):
        p.version("sdk", gj["sdk"].get("version"), src(prefix, "global.json"))
        p.version("sdk rollForward", gj["sdk"].get("rollForward"), src(prefix, "global.json"))
    if "Directory.Packages.props" in files:
        p.add("lockfiles", "Directory.Packages.props")
        p.notes.append("central package management: add package versions in Directory.Packages.props")
    if "packages.lock.json" in files:
        p.add("lockfiles", "packages.lock.json")
    if os.path.isfile(os.path.join(d, ".config", "dotnet-tools.json")):
        p.add("tools", "dotnet local tools")
    if slns:
        p.add("frameworks", "solution: " + ", ".join(slns))
    p.package_manager = "dotnet / NuGet"
    p.defaults = ["dotnet build", "dotnet test", "dotnet format --verify-no-changes",
                  "dotnet list package --vulnerable --include-transitive"]
    return p


def detect_cpp(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    markers = {"CMakeLists.txt", "meson.build", "MODULE.bazel", "WORKSPACE", "WORKSPACE.bazel"} & files
    if not markers:
        return None
    p = Project(prefix, "C/C++")
    if "CMakeLists.txt" in files:
        t = read_text(os.path.join(d, "CMakeLists.txt")) or ""
        p.version("cmake_minimum_required", regex1(r"cmake_minimum_required\s*\(\s*VERSION\s+([^\s)]+)", t, re.I | re.M), src(prefix, "CMakeLists.txt"))
        p.version("CMAKE_CXX_STANDARD", regex1(r"set\s*\(\s*CMAKE_CXX_STANDARD\s+(\d+)", t, re.I | re.M) or regex1(r"cxx_std_(\d+)", t), src(prefix, "CMakeLists.txt"))
        p.version("CMAKE_C_STANDARD", regex1(r"set\s*\(\s*CMAKE_C_STANDARD\s+(\d+)", t, re.I | re.M), src(prefix, "CMakeLists.txt"))
        if re.search(r"find_package\s*\(\s*Zephyr", t):
            p.stack = "Embedded (Zephyr)"
        if "IDF_PATH" in t and "project.cmake" in t:
            p.stack = "Embedded (ESP-IDF)"
        for key, tool in (("GTest", "googletest"), ("googletest", "googletest"), ("Catch2", "catch2"), ("doctest", "doctest"), ("enable_testing", "ctest")):
            if key in t:
                p.add("tools", tool)
        p.package_manager = "cmake"
    if "meson.build" in files:
        t = read_text(os.path.join(d, "meson.build")) or ""
        p.version("meson cpp_std", regex1(r"cpp_std=([\w+]+)", t), src(prefix, "meson.build"))
        p.package_manager = p.package_manager or "meson"
    if {"MODULE.bazel", "WORKSPACE", "WORKSPACE.bazel"} & files:
        p.package_manager = p.package_manager or "bazel"
        p.add("frameworks", "Bazel")
    presets = load_json(read_text(os.path.join(d, "CMakePresets.json"))) if "CMakePresets.json" in files else None
    names: List[str] = []
    if presets:
        names = [c.get("name") for c in presets.get("configurePresets", []) if isinstance(c, dict) and c.get("name") and not c.get("hidden")]
        if names:
            p.add("tools", "cmake presets: " + ", ".join(names))
    for name, lock in (("vcpkg.json", "vcpkg"), ("conanfile.txt", "conan"), ("conanfile.py", "conan")):
        if name in files:
            p.add("lockfiles", name)
            p.add("tools", lock)
    for name, tool in ((".clang-format", "clang-format"), (".clang-tidy", "clang-tidy"), ("compile_commands.json", "compile_commands.json")):
        if name in files:
            p.add("tools", tool)
    if p.stack == "Embedded (Zephyr)":
        p.defaults = ["west build -b <board> .  (board from the project's docs or CI)"]
    elif p.stack == "Embedded (ESP-IDF)":
        p.defaults = ["idf.py build"]
    elif p.package_manager == "cmake":
        if names:
            p.defaults = [f"cmake --preset {names[0]}", f"cmake --build --preset {names[0]}", f"ctest --preset {names[0]} --output-on-failure"]
        else:
            p.defaults = ["cmake -S . -B build", "cmake --build build", "ctest --test-dir build --output-on-failure"]
    elif p.package_manager == "meson":
        p.defaults = ["meson setup builddir", "meson compile -C builddir", "meson test -C builddir"]
    else:
        p.defaults = ["bazel build //...", "bazel test //..."]
    if "clang-format" in p.tools:
        p.defaults.append("clang-format --dry-run -Werror <changed files>")
    return p


def detect_php(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    if "composer.json" not in files:
        return None
    p = Project(prefix, "PHP")
    data = load_json(read_text(os.path.join(d, "composer.json"))) or {}
    req = data.get("require") if isinstance(data.get("require"), dict) else {}
    dev = data.get("require-dev") if isinstance(data.get("require-dev"), dict) else {}
    p.version("require php", req.get("php"), src(prefix, "composer.json"))
    platform = ((data.get("config") or {}).get("platform") or {}) if isinstance(data.get("config"), dict) else {}
    p.version("config.platform.php", platform.get("php") if isinstance(platform, dict) else None, src(prefix, "composer.json"))
    for pkg, fw in PHP_PACKAGES.items():
        if pkg in req:
            p.add("frameworks", fw)
            p.version(pkg, req.get(pkg), src(prefix, "composer.json"))
    for pkg, tool in PHP_TOOLS.items():
        if pkg in req or pkg in dev:
            p.add("tools", tool)
    for name, tool in (("phpstan.neon", "phpstan"), ("phpstan.neon.dist", "phpstan"), ("psalm.xml", "psalm"), ("pint.json", "pint"),
                       (".php-cs-fixer.php", "php-cs-fixer"), (".php-cs-fixer.dist.php", "php-cs-fixer"), ("phpunit.xml", "phpunit"),
                       ("phpunit.xml.dist", "phpunit"), ("rector.php", "rector")):
        if name in files:
            p.add("tools", tool)
    scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
    for name in sorted(scripts):
        if not name.startswith(("pre-", "post-")):
            p.commands.append((f"composer run {name}", src(prefix, "composer.json")))
    p.package_manager = "composer"
    if "composer.lock" in files:
        p.add("lockfiles", "composer.lock")
    else:
        p.notes.append("composer.json without composer.lock: installs are not reproducible")
    if "artisan" in files:
        p.add("frameworks", "Laravel")
    if os.path.isfile(os.path.join(d, "tests", "Pest.php")):
        p.add("tools", "pest")
    p.defaults = ["composer validate --strict"]
    if "Laravel" in p.frameworks and "artisan" in files:
        p.defaults.append("php artisan test")
    elif "pest" in p.tools:
        p.defaults.append("vendor/bin/pest")
    else:
        p.defaults.append("vendor/bin/phpunit")
    if "phpstan" in p.tools or "larastan" in p.tools:
        p.defaults.append("vendor/bin/phpstan analyse")
    if "psalm" in p.tools:
        p.defaults.append("vendor/bin/psalm")
    if "pint" in p.tools:
        p.defaults.append("vendor/bin/pint --test")
    elif "php-cs-fixer" in p.tools:
        p.defaults.append("vendor/bin/php-cs-fixer fix --dry-run --diff")
    p.defaults.append("composer audit")
    return p


def detect_ruby(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    if "Gemfile" not in files and "gems.rb" not in files:
        return None
    p = Project(prefix, "Ruby")
    gemfile = "Gemfile" if "Gemfile" in files else "gems.rb"
    t = read_text(os.path.join(d, gemfile)) or ""
    p.version("ruby (Gemfile)", regex1(r"^\s*ruby\s+['\"]([^'\"]+)", t), src(prefix, gemfile))
    gems = re.findall(r"^\s*gem\s+['\"]([^'\"]+)", t, re.M)
    for g in gems:
        if g in RUBY_GEMS:
            p.add("frameworks", RUBY_GEMS[g])
        if g in RUBY_TOOLS:
            p.add("tools", RUBY_TOOLS[g])
    if ".ruby-version" in files:
        p.version(".ruby-version", first_line(read_text(os.path.join(d, ".ruby-version"))), src(prefix, ".ruby-version"))
    lock = "Gemfile.lock" if "Gemfile.lock" in files else ("gems.locked" if "gems.locked" in files else None)
    if lock:
        lt = read_text(os.path.join(d, lock)) or ""
        p.add("lockfiles", lock)
        p.version("ruby (lock)", regex1(r"^RUBY VERSION\s*\n\s+ruby\s+(\S+)", lt), src(prefix, lock))
        p.version("rails (lock)", regex1(r"^    rails \(([^)]+)\)", lt), src(prefix, lock))
    else:
        p.notes.append("Gemfile without Gemfile.lock: installs are not reproducible")
    app = os.path.join(d, "config", "application.rb")
    if os.path.isfile(app):
        p.version("config.load_defaults", regex1(r"load_defaults\s+([\d.]+)", read_text(app)), src(prefix, "config/application.rb"))
    for name, tool in ((".rubocop.yml", "rubocop"), (".rspec", "rspec"), ("sorbet", "sorbet")):
        if name in files:
            p.add("tools", tool)
    p.package_manager = "bundler"
    p.defaults = []
    if "rspec" in p.tools or os.path.isdir(os.path.join(d, "spec")):
        p.defaults.append("bundle exec rspec")
    if "Rails" in p.frameworks and os.path.isdir(os.path.join(d, "test")):
        p.defaults.append("bin/rails test")
    if not p.defaults:
        p.defaults.append("bundle exec rake test")
    if "rubocop" in p.tools:
        p.defaults.append("bundle exec rubocop")
    if "standard" in p.tools:
        p.defaults.append("bundle exec standardrb")
    if "brakeman" in p.tools:
        p.defaults.append("bundle exec brakeman -q --no-pager")
    if "Rails" in p.frameworks:
        p.defaults.append("bin/rails zeitwerk:check")
    return p


def detect_swift(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    xc = sorted(f for f in files if f.endswith((".xcodeproj", ".xcworkspace")))
    if "Package.swift" not in files and not xc:
        return None
    p = Project(prefix, "Swift")
    if "Package.swift" in files:
        t = read_text(os.path.join(d, "Package.swift")) or ""
        p.version("swift-tools-version", regex1(r"swift-tools-version\s*:\s*([\d.]+)", t), src(prefix, "Package.swift"))
        for plat in re.findall(r"\.(iOS|macOS|tvOS|watchOS|visionOS|macCatalyst)\(\s*\.v([\d_]+)", t):
            p.version(f"platform {plat[0]}", plat[1].replace("_", "."), src(prefix, "Package.swift"))
        for key, fw in (("vapor/vapor", "Vapor"), ("hummingbird", "Hummingbird"), ("swift-argument-parser", "swift-argument-parser")):
            if key in t:
                p.add("frameworks", fw)
        p.package_manager = "swift package manager"
    if xc:
        p.add("frameworks", "Xcode: " + ", ".join(xc))
        p.package_manager = p.package_manager or "xcodebuild"
    if "Package.resolved" in files:
        p.add("lockfiles", "Package.resolved")
    if ".swift-version" in files:
        p.version(".swift-version", first_line(read_text(os.path.join(d, ".swift-version"))), src(prefix, ".swift-version"))
    for name, tool in ((".swiftlint.yml", "swiftlint"), (".swift-format", "swift-format"), (".swiftformat", "swiftformat")):
        if name in files:
            p.add("tools", tool)
    p.defaults = ["swift build", "swift test"] if "Package.swift" in files else ["xcodebuild -list", "xcodebuild test -scheme <scheme> -destination '<installed simulator>'"]
    if "swiftlint" in p.tools:
        p.defaults.append("swiftlint lint --strict")
    return p


def detect_embedded(d: str, files: set, prefix: str, root: str) -> List[Project]:
    out: List[Project] = []
    if "platformio.ini" in files:
        p = Project(prefix, "Embedded (PlatformIO)")
        t = read_text(os.path.join(d, "platformio.ini")) or ""
        envs = re.findall(r"^\[env:([^\]]+)\]", t, re.M)
        for key in ("platform", "board", "framework"):
            vals = sorted(set(v.strip() for v in re.findall(rf"^{key}\s*=\s*(.+)$", t, re.M)))
            if vals:
                p.version(key, ", ".join(vals), src(prefix, "platformio.ini"))
        if envs:
            p.add("tools", "environments: " + ", ".join(envs))
        p.package_manager = "platformio"
        p.defaults = [f"pio run -e {envs[0]}" if envs else "pio run"]
        if "native" in envs:
            p.defaults.append("pio test -e native")
        p.notes.append("build and host-test only; flashing a device needs the user's go-ahead")
        out.append(p)
    iocs = sorted(f for f in files if f.endswith(".ioc"))
    if iocs:
        p = Project(prefix, "Embedded (STM32Cube)")
        t = read_text(os.path.join(d, iocs[0])) or ""
        p.version("MCU", regex1(r"^Mcu\.UserName=(\S+)", t) or regex1(r"^Mcu\.Name=(\S+)", t), src(prefix, iocs[0]))
        p.version("firmware package", regex1(r"^ProjectManager\.FirmwarePackage=(\S+)", t), src(prefix, iocs[0]))
        p.package_manager = "STM32CubeMX project"
        p.notes.append("generated code: edit only inside USER CODE sections and regenerate from the .ioc file")
        p.notes.append("build and host-test only; flashing a device needs the user's go-ahead")
        out.append(p)
    if "west.yml" in files:
        p = Project(prefix, "Embedded (Zephyr west workspace)")
        p.package_manager = "west"
        p.defaults = ["west build -b <board> <app>"]
        p.notes.append("build and host-test only; flashing a device needs the user's go-ahead")
        out.append(p)
    return out


def detect_web_platforms(d: str, files: set, prefix: str, root: str) -> List[Project]:
    """Front-end, mobile and game platforms whose details live in the web-stacks references."""
    out: List[Project] = []
    if "pubspec.yaml" in files:
        t = read_text(os.path.join(d, "pubspec.yaml")) or ""
        p = Project(prefix, "Dart" + (" (Flutter)" if re.search(r"^\s+flutter:\s*$|sdk:\s*flutter", t, re.M) else ""))
        p.version("environment sdk", regex1(r"^\s+sdk:\s*['\"]?([^'\"\n]+)", t), src(prefix, "pubspec.yaml"))
        p.package_manager = "pub"
        p.add("lockfiles", *[n for n in ("pubspec.lock",) if n in files])
        p.defaults = ["flutter analyze", "flutter test"] if "Flutter" in p.stack else ["dart analyze", "dart test"]
        out.append(p)
    if "shopify.app.toml" in files:
        p = Project(prefix, "Shopify app")
        p.version("api_version", regex1(r"api_version\s*=\s*['\"]([^'\"]+)", read_text(os.path.join(d, "shopify.app.toml"))),
                  src(prefix, "shopify.app.toml"))
        out.append(p)
    elif os.path.isfile(os.path.join(d, "layout", "theme.liquid")) and os.path.isfile(os.path.join(d, "config", "settings_schema.json")):
        p = Project(prefix, "Shopify theme")
        p.defaults = ["shopify theme check"]
        out.append(p)
    wp_header = None
    if "style.css" in files and re.search(r"^\s*\*?\s*Theme Name:", (read_text(os.path.join(d, "style.css")) or "")[:4000], re.M):
        wp_header = "theme"
    else:
        for name in sorted(f for f in files if f.endswith(".php"))[:20]:
            if re.search(r"^\s*\*?\s*Plugin Name:", (read_text(os.path.join(d, name)) or "")[:4000], re.M):
                wp_header = "plugin"
                break
    if wp_header or "block.json" in files or ".wp-env.json" in files:
        out.append(Project(prefix, f"WordPress {wp_header or 'block or site'}"))
    for marker, stack in (("project.godot", "Godot"),):
        if marker in files:
            out.append(Project(prefix, stack))
    if os.path.isfile(os.path.join(d, "ProjectSettings", "ProjectVersion.txt")):
        p = Project(prefix, "Unity")
        p.version("editor", regex1(r"^m_EditorVersion:\s*(\S+)", read_text(os.path.join(d, "ProjectSettings", "ProjectVersion.txt"))),
                  src(prefix, "ProjectSettings/ProjectVersion.txt"))
        out.append(p)
    uprojects = sorted(f for f in files if f.endswith(".uproject"))
    if uprojects:
        out.append(Project(prefix, "Unreal Engine"))
    for p in out:
        p.notes.append("details for this stack: the front-end, web and mobile references in the stacks GUIDE")
    return out


def detect_salesforce(d: str, files: set, prefix: str, root: str) -> Optional[Project]:
    if "sfdx-project.json" not in files:
        return None
    p = Project(prefix, "Salesforce")
    data = load_json(read_text(os.path.join(d, "sfdx-project.json"))) or {}
    p.version("sourceApiVersion", data.get("sourceApiVersion"), src(prefix, "sfdx-project.json"))
    dirs = [x.get("path") for x in data.get("packageDirectories", []) if isinstance(x, dict) and x.get("path")]
    if dirs:
        p.add("frameworks", "package directories: " + ", ".join(dirs))
    if data.get("namespace"):
        p.add("frameworks", f"namespace {data['namespace']}")
    p.package_manager = "sf CLI"
    p.notes.append("an org is an environment: deploy and run Apex only in scratch orgs or sandboxes unless the user approves")
    p.defaults = ["sf project deploy start --target-org <scratch-or-sandbox-alias>",
                  "sf apex run test --target-org <alias> --test-level RunLocalTests --wait 20"]
    return p


def detect_node(d: str, files: set, prefix: str, root: str, owner: Optional[Project]) -> Optional[Project]:
    if "package.json" not in files:
        return None
    data = load_json(read_text(os.path.join(d, "package.json"))) or {}
    node_locks = {"pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "package-lock.json": "npm", "bun.lock": "bun", "bun.lockb": "bun"}
    locks = [(n, pm) for n, pm in node_locks.items() if n in files]
    if not locks:
        up = find_up(d, root, tuple(node_locks))
        if up:
            locks = [(src(up[0], up[1]) + " (workspace root)", node_locks[up[1]])]
    pm_field = data.get("packageManager") if isinstance(data.get("packageManager"), str) else None
    pm = pm_field.split("@", 1)[0] if pm_field else (locks[0][1] if locks else "npm")
    scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
    run = "npm run" if pm == "npm" else f"{pm} run"
    cmds = [(f"{run} {s}", src(prefix, "package.json")) for s in sorted(scripts)
            if s in ("test", "lint", "build", "typecheck", "type-check", "format", "format:check", "check", "test:unit", "prettier:verify")]
    p = owner if owner is not None else Project(prefix, "JavaScript/TypeScript (Node)")
    p.commands += [c for c in cmds if c not in p.commands]
    if owner is not None:
        p.add("tools", f"package.json tooling ({pm})")
        return None
    engines = data.get("engines") if isinstance(data.get("engines"), dict) else {}
    p.version("engines.node", engines.get("node"), src(prefix, "package.json"))
    p.version("packageManager", pm_field, src(prefix, "package.json"))
    for name in (".nvmrc", ".node-version"):
        if name in files:
            p.version(name, first_line(read_text(os.path.join(d, name))), src(prefix, name))
    deps: Dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        if isinstance(data.get(key), dict):
            deps.update(data[key])
    for dep, fw in NODE_FRAMEWORKS.items():
        if dep in deps:
            p.add("frameworks", fw)
    p.package_manager = pm
    p.add("lockfiles", *[n for n, _ in locks])
    if len({x for _, x in locks}) > 1:
        p.notes.append("lockfiles from several package managers (" + ", ".join(n for n, _ in locks) + "): confirm which one CI uses")
    if not locks and data.get("dependencies"):
        p.notes.append("package.json without a lockfile: installs are not reproducible")
    p.defaults = [] if cmds else [f"{run} test"]
    return p


# --- environment pins and CI ----------------------------------------------------------------------

def env_pins(d: str, files: set, prefix: str) -> List[dict]:
    out: List[dict] = []
    if ".tool-versions" in files:
        for line in (read_text(os.path.join(d, ".tool-versions")) or "").splitlines():
            parts = line.split("#", 1)[0].split()
            if len(parts) >= 2:
                out.append({"source": src(prefix, ".tool-versions"), "name": parts[0], "value": " ".join(parts[1:])})
    for name in ("mise.toml", ".mise.toml"):
        if name in files:
            text = read_text(os.path.join(d, name)) or ""
            data = load_toml(text)
            tools = (data or {}).get("tools") if data else None
            if isinstance(tools, dict):
                for k in sorted(tools):
                    out.append({"source": src(prefix, name), "name": k, "value": str(tools[k])})
    for name in sorted(f for f in files if f == "Dockerfile" or f.startswith("Dockerfile.") or f.endswith(".Dockerfile")):
        for image in re.findall(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", read_text(os.path.join(d, name)) or "", re.M | re.I):
            out.append({"source": src(prefix, name), "name": "FROM", "value": image})
    dc = os.path.join(d, ".devcontainer", "devcontainer.json")
    if os.path.isfile(dc):
        image = regex1(r"\"image\"\s*:\s*\"([^\"]+)\"", read_text(dc))
        if image:
            out.append({"source": src(prefix, ".devcontainer/devcontainer.json"), "name": "image", "value": image})
    return out


VERSION_KEYS = re.compile(r"^\s*-?\s*((?:python|go|java|dotnet|node|ruby|php|rust|swift|kotlin)-version|toolchain|distribution|image)\s*:\s*(.+?)\s*$", re.M)


def ci_commands(text: str) -> List[str]:
    cmds: List[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s*)(?:-\s+)?(run|script|before_script|after_script|command)\s*:\s*(.*)$", line)
        if m:
            indent = len(m.group(1))
            rest = m.group(3).strip()
            if rest and rest[0] not in "|>" and not rest.startswith("["):
                cmds.append(rest.strip("'\""))
            elif rest.startswith("["):
                cmds += [x.strip().strip("'\"") for x in rest.strip("[]").split(",") if x.strip()]
            else:
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
                    item = lines[j].strip()
                    if item:
                        cmds.append(item[2:].strip().strip("'\"") if item.startswith("- ") else item)
                    j += 1
                i = j
                continue
        else:
            for sh in re.finditer(r"\bsh\s*\(?\s*(['\"])(.+?)\1", line):  # Jenkinsfile steps
                cmds.append(sh.group(2))
        i += 1
    seen: List[str] = []
    for c in cmds:
        c = redact(c)
        if c and not c.startswith("#") and c not in seen:
            seen.append(c)
    return seen[:MAX_CI_COMMANDS]


def ci_files(d: str, files: set, prefix: str) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    norm = prefix.replace("\\", "/")
    if norm.endswith(".github/workflows") or norm == ".github/workflows":
        found += [(os.path.join(d, f), src(prefix, f)) for f in sorted(files) if f.endswith((".yml", ".yaml"))]
    if norm.endswith(".circleci") and "config.yml" in files:
        found.append((os.path.join(d, "config.yml"), src(prefix, "config.yml")))
    for name in (".gitlab-ci.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml", "Jenkinsfile", ".travis.yml"):
        if name in files:
            found.append((os.path.join(d, name), src(prefix, name)))
    return found


# --- scan and report ------------------------------------------------------------------------------

def scan(root: str, max_depth: int) -> dict:
    root = os.path.abspath(root)
    projects: List[Project] = []
    pins: List[dict] = []
    ci: List[dict] = []
    runners: List[dict] = []
    scanned = 0
    for d, dirs, filenames in os.walk(root):
        depth = 0 if d == root else os.path.relpath(d, root).count(os.sep) + 1
        bundles = {x for x in dirs if x.endswith((".xcodeproj", ".xcworkspace"))}
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and x not in bundles and depth < max_depth
                         and (not x.startswith(".") or x in ALLOWED_HIDDEN))
        scanned += 1
        files = {f for f in filenames if not is_sensitive(f)} | bundles
        prefix = rel(root, d)
        found: List[Project] = []
        sf = detect_salesforce(d, files, prefix, root)
        for det in (detect_python, detect_go, detect_rust, detect_dotnet, detect_cpp, detect_php, detect_ruby, detect_swift):
            p = det(d, files, prefix, root)
            if p:
                found.append(p)
        found += detect_jvm(d, files, prefix, root)
        found += detect_embedded(d, files, prefix, root)
        found += detect_web_platforms(d, files, prefix, root)
        if sf:
            found.append(sf)
        node = detect_node(d, files, prefix, root, sf)
        if node:
            found.append(node)
        runner_cmds = task_runner_commands(d, files, prefix)
        if found:
            for p in found:
                p.commands = runner_cmds + [c for c in p.commands if c not in runner_cmds]
        elif runner_cmds:
            runners.append({"path": prefix, "commands": [{"command": c, "source": s} for c, s in runner_cmds]})
        projects += found
        pins += env_pins(d, files, prefix)
        for path, label in ci_files(d, files, prefix):
            text = read_text(path) or ""
            versions = [{"name": k, "value": redact(v.strip().strip("'\""))} for k, v in VERSION_KEYS.findall(text)]
            uniq: List[dict] = []
            for v in versions:
                if v not in uniq:
                    uniq.append(v)
            ci.append({"file": label, "versions": uniq[:30], "commands": ci_commands(text)})
    projects.sort(key=lambda p: (p.path.count("/") if p.path != "." else -1, p.path, p.stack))
    notes = []
    stacks = sorted({p.stack for p in projects})
    if len({p.path for p in projects}) > 1:
        notes.append("several subprojects: run each project's commands from its own directory")
    return {"root": root, "max_depth": max_depth, "directories_scanned": scanned, "stacks": stacks,
            "projects": [p.as_dict() for p in projects], "environment_pins": pins, "ci": ci,
            "task_runners_outside_projects": runners, "notes": notes}


def to_markdown(report: dict, root_label: str) -> str:
    out = ["# Stack report", "",
           f"Root: `{root_label}` · {report['directories_scanned']} directories scanned to depth {report['max_depth']} · read-only, nothing was executed", ""]
    if not report["projects"]:
        out += ["No known manifest was found. Check the root, raise `--max-depth`, or read the README and CI files.", ""]
    for p in report["projects"]:
        title = p["stack"] + (f" ({', '.join(p['frameworks'])})" if p["frameworks"] else "")
        out += [f"## `{p['path']}`: {title}", ""]
        if p["versions"]:
            out.append("- Versions: " + "; ".join(f"{v['name']} `{v['value']}` ({v['source']})" for v in p["versions"]))
        if p["package_manager"]:
            out.append(f"- Package manager: {p['package_manager']}" + (f"; locked by {', '.join(p['lockfiles'])}" if p["lockfiles"] else "; no lockfile found"))
        if p["tools"]:
            out.append("- Tools configured: " + ", ".join(p["tools"]))
        if p["commands"]:
            out.append("- Project commands:")
            out += [f"  - `{c['command']}` ({c['source']})" for c in p["commands"]]
        if p["defaults"]:
            out.append("- Ecosystem defaults (not found in project files; confirm before relying on them):")
            out += [f"  - `{c}`" for c in p["defaults"]]
        if p["notes"]:
            out.append("- Notes:")
            out += [f"  - {n}" for n in p["notes"]]
        out.append("")
    if report["environment_pins"]:
        out += ["## Environment pins", ""]
        out += [f"- {e['source']}: {e['name']} `{e['value']}`" for e in report["environment_pins"]]
        out.append("")
    if report["ci"]:
        out += ["## CI", ""]
        for c in report["ci"]:
            out.append(f"### {c['file']}")
            if c["versions"]:
                out.append("- Versions and images: " + "; ".join(f"{v['name']}: `{v['value']}`" for v in c["versions"]))
            if c["commands"]:
                out.append("- Commands:")
                out += [f"  - `{x}`" for x in c["commands"]]
            out.append("")
    if report["task_runners_outside_projects"]:
        out += ["## Task runners outside projects", ""]
        for r in report["task_runners_outside_projects"]:
            out.append(f"- `{r['path']}`: " + ", ".join(f"`{c['command']}`" for c in r["commands"]))
        out.append("")
    if report["notes"]:
        out += ["## Notes", ""] + [f"- {n}" for n in report["notes"]] + [""]
    return "\n".join(out).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="detect_stack.py",
        description="Read-only stack detector: versions, package managers, tools and commands per subproject.",
        epilog="Exit status: 0 when at least one stack was found, 1 when none was, 2 for bad arguments or a missing root.",
    )
    p.add_argument("root", nargs="?", default=".", help="repository or subdirectory to scan (default: .)")
    p.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    p.add_argument("--max-depth", type=int, default=4, help="directory levels below the root to scan (default: 4)")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_depth < 0:
        parser.error("--max-depth must be 0 or more")
    if not os.path.isdir(args.root):
        print(f"error: not a directory: {args.root}", file=sys.stderr)
        return 2
    report = scan(args.root, args.max_depth)
    if args.json:
        report = dict(report)
        report["root"] = args.root
        print(json.dumps(report, indent=2, sort_keys=False))
    else:
        sys.stdout.write(to_markdown(report, args.root))
    return 0 if report["projects"] else 1


if __name__ == "__main__":
    sys.exit(main())
