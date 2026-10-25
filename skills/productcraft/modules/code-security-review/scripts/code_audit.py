#!/usr/bin/env python3
"""ProductCraft code security review helper. Offline, read-only, deterministic.

Subcommands:
  map        Rank source files by entry-point and sink hints, and list
             dependency manifests, lockfiles, CI files and container base images.
  workflows  Check GitHub Actions workflows for privileged triggers, script
             injection, unpinned actions, broad token permissions and
             remote scripts piped to a shell.
  history    Scan every commit reachable from local refs for secret-shaped
             values and sensitive file names. Values are never printed.
  findings   Validate a findings JSON file against the module's evidence rules
             and print the audit result.

Results from map, workflows and history are leads to verify, never findings.
The tool does not use the network, does not modify the target and never
writes matched source text or secret values to its output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

VERSION = "1.0.0"

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".agents", ".claude", ".venv", "venv", "env",
    "node_modules", "bower_components", ".next", ".nuxt", ".svelte-kit",
    "dist", "build", "out", "coverage", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".tox", "vendor", "third_party", "target", ".turbo",
    ".cache", ".angular", ".idea", ".gradle", "Pods", "DerivedData",
}
SOURCE_SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".py", ".rb", ".go", ".rs", ".php", ".java", ".kt", ".kts", ".scala",
    ".cs", ".swift", ".ex", ".exs", ".erb",
}
TEST_PATH = re.compile(
    r"(?:^|/)(?:tests?|__tests__|spec|specs|fixtures?|testdata|mocks?|__mocks__|e2e|cypress|examples?)/"
    r"|\.(?:test|spec)\.[A-Za-z]+$|_test\.(?:go|py|rb)$|(?:^|/)test_[^/]+\.py$|Tests?\.(?:java|kt|cs)$"
)
MAX_FILE_BYTES = 1_000_000
MAX_FILES = 20_000
MAX_RESULTS = 500
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def iter_files(root: Path):
    """Yield (path, posix relative path) in sorted order, skipping symlinks."""
    count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            d for d in dirs
            if d not in SKIP_DIRS and not os.path.islink(os.path.join(current, d))
        )
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            count += 1
            if count > MAX_FILES:
                return
            yield path, path.relative_to(root).as_posix()


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def write_json(result: dict, out: str) -> None:
    output = Path(out).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def resolve_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    return root


def severity_key(item: dict) -> tuple:
    return (SEVERITY_ORDER.get(item.get("severity", "INFO"), 9),
            item.get("file") or item.get("path") or "", item.get("line") or 0, item.get("rule", ""))


# --------------------------------------------------------------------------
# Secret-shaped values (used by history and by the findings hygiene check)
# --------------------------------------------------------------------------

SECRET_RULES = [
    ("AWS_ACCESS_KEY_ID", "HIGH", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GITHUB_PAT", "HIGH", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})")),
    ("GITLAB_PAT", "HIGH", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("SLACK_TOKEN", "HIGH", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("STRIPE_LIVE_SECRET", "HIGH", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}")),
    ("STRIPE_TEST_SECRET", "LOW", re.compile(r"\b(?:sk|rk)_test_[A-Za-z0-9]{16,}")),
    ("AI_PROVIDER_KEY", "HIGH", re.compile(r"\bsk-(?:ant-|proj-)[A-Za-z0-9_-]{20,}")),
    ("SENDGRID_KEY", "HIGH", re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}")),
    ("SUPABASE_SECRET_KEY", "HIGH", re.compile(r"\bsb_secret_[A-Za-z0-9_-]{12,}")),
    ("GOOGLE_API_KEY", "MEDIUM", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("PRIVATE_KEY_BLOCK", "HIGH", re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("PASSWORD_IN_URL", "HIGH", re.compile(r"\b[a-z][a-z0-9+.-]{1,20}://[^\s:/@'\"]+:([^\s@/'\"]{4,})@")),
    ("JWT_LIKE", "MEDIUM", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]
SECRET_NOTES = {
    "STRIPE_TEST_SECRET": "Test-mode key: still a credential for the test account; rotate if the repository is shared.",
    "GOOGLE_API_KEY": "Often a browser key; check its API and referrer restrictions before rating.",
    "JWT_LIKE": "May be a public anon key or a test fixture; decode the claims locally and check role and expiry.",
}
PLACEHOLDER = re.compile(
    r"(?i)^(?:pass(?:word|wd)?|pwd|secret|changeme|example|test|dummy|user|xx+|\*+|<[^>]*>|"
    r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\{\{.*\}\}|%[sd]|%\([a-z_]+\)s)$"
)


def secret_hits(text: str) -> list[tuple[str, str]]:
    hits = []
    for rule, severity, regex in SECRET_RULES:
        for match in regex.finditer(text):
            if rule == "PASSWORD_IN_URL":
                secret = match.group(1)
                if PLACEHOLDER.match(secret) or "${" in secret or "{{" in secret:
                    continue
            hits.append((rule, severity))
            break
    return hits


# --------------------------------------------------------------------------
# map
# --------------------------------------------------------------------------

ENTRY_PATTERNS = [
    re.compile(r"\b(?:app|router|server|fastify|route)\.(?:get|post|put|patch|delete|all|route)\s*\("),
    re.compile(r"export\s+(?:async\s+)?function\s+(?:GET|POST|PUT|PATCH|DELETE)\b"),
    re.compile(r"^\s*['\"]use server['\"]"),
    re.compile(r"@(?:app|bp|blueprint|router|api|\w+_router)\.(?:route|get|post|put|patch|delete|websocket)\s*\("),
    re.compile(r"\b(?:re_)?path\s*\(\s*r?['\"]"),
    re.compile(r"\b(?:http\.)?HandleFunc\s*\(|\.(?:GET|POST|PUT|PATCH|DELETE)\s*\(\s*\""),
    re.compile(r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\b"),
    re.compile(r"\bRoute::(?:get|post|put|patch|delete|any|match|resource)\s*\("),
    re.compile(r"#\[(?:get|post|put|patch|delete)\s*\(|\.route\s*\(\s*\""),
    re.compile(r"\b(?:Query|Mutation)\s*:\s*\{|@(?:Query|Mutation|Resolver)\s*\("),
    re.compile(r"addEventListener\s*\(\s*['\"]message['\"]"),
]
ENTRY_PATH = re.compile(r"(?:^|/)pages/api/|(?:^|/)app/(?:.+/)?route\.(?:js|ts)$|(?:^|/)config/routes\.rb$|webhook", re.I)
SINK_PATTERNS = {
    "sql": re.compile(r"\$(?:query|execute)RawUnsafe|\.raw\s*\(|\.(?:query|execute|exec|Query|Exec|QueryRow)\s*\(\s*"
                      r"(?:`[^`]*\$\{|f['\"]|['\"][^'\"]*['\"]\s*(?:\+|%)|fmt\.Sprintf)|createQuery\s*\(\s*\"[^\"]*\"\s*\+"),
    "command": re.compile(r"\bchild_process\b|\bexecSync\s*\(|\bspawn(?:Sync)?\s*\(|\bsubprocess\.|\bos\.(?:system|popen)\s*\(|"
                          r"Runtime\.getRuntime\(\)\.exec|exec\.Command\s*\(|\bshell_exec\s*\(|\bpassthru\s*\("),
    "code_eval": re.compile(r"\beval\s*\(|new\s+Function\s*\(|\bvm\.run|\bexec\s*\(\s*compile"),
    "deserialization": re.compile(r"\bpickle\.loads?\s*\(|\byaml\.load\s*\((?![^)]*SafeLoader)|ObjectInputStream|"
                                  r"\bunserialize\s*\(|Marshal\.load|BinaryFormatter|jsonpickle\.decode"),
    "file_path": re.compile(r"\bsendFile\s*\(|res\.download\s*\(|\bsend_file\s*\(|send_from_directory\s*\(|"
                            r"(?:readFile|createReadStream|writeFile)(?:Sync)?\s*\([^)]*\b(?:req|request|params|query|body)\b"),
    "outbound_url": re.compile(r"\b(?:fetch|axios(?:\.\w+)?|got|requests\.\w+|httpx\.\w+|urlopen|http\.Get)\s*\(\s*"
                               r"(?:req|request|params|query|body|url|target|link|href)\b"),
    "html": re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*=(?!=)|\bv-html\b|\|\s*safe\b|\bmark_safe\s*\(|"
                       r"\.html_safe\b|bypassSecurityTrust|document\.write\s*\("),
    "redirect": re.compile(r"\bredirect\s*\(\s*(?:req|request)\.(?:query|args|GET|params|body)"),
    "template": re.compile(r"render_template_string\s*\(|\bTemplate\s*\([^)]*request|ejs\.render\s*\(|renderString\s*\("),
    "xml": re.compile(r"DocumentBuilderFactory|XMLInputFactory|SAXParserFactory|etree\.(?:parse|fromstring)\s*\(|"
                      r"\bxml2js\b|libxml_disable_entity_loader"),
    "upload": re.compile(r"\bmulter\b|\bformidable\b|\bbusboy\b|\bUploadFile\b|request\.files\b|MultipartFile"),
    "weak_random": re.compile(r"Math\.random\s*\(\)|\brandom\.(?:random|randint|choice)\s*\(|new\s+Random\s*\("),
    "llm": re.compile(r"\b(?:openai|langchain|llama_index|llamaindex)\b|chat\.completions|messages\.create|"
                      r"\btool_choice\b|\btool_calls\b|\bfunction_call\b"),
}
AUTH_HINT = re.compile(r"\b(?:isAdmin|is_admin|req\.user|request\.user|current_user|getServerSession|auth\(\)|"
                       r"login_required|PreAuthorize|authorize|requireAuth|verifyToken|jwt\.verify|session\[)")

LOCKFILES = {
    "package.json": ("npm", ["package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock"]),
    "pyproject.toml": ("python", ["poetry.lock", "uv.lock", "pdm.lock", "Pipfile.lock"]),
    "Pipfile": ("python", ["Pipfile.lock"]),
    "Cargo.toml": ("cargo", ["Cargo.lock"]),
    "go.mod": ("go", ["go.sum"]),
    "Gemfile": ("ruby", ["Gemfile.lock"]),
    "composer.json": ("php", ["composer.lock"]),
    "mix.exs": ("elixir", ["mix.lock"]),
    "pubspec.yaml": ("dart", ["pubspec.lock"]),
    "Package.swift": ("swift", ["Package.resolved"]),
    "pom.xml": ("maven", []),
    "build.gradle": ("gradle", ["gradle.lockfile"]),
    "build.gradle.kts": ("gradle", ["gradle.lockfile"]),
}
CI_FILES = re.compile(
    r"^\.github/workflows/[^/]+\.ya?ml$|^\.gitlab-ci\.yml$|^\.circleci/config\.ya?ml$|^azure-pipelines\.ya?ml$|"
    r"^Jenkinsfile$|^bitbucket-pipelines\.yml$|^\.buildkite/[^/]+\.ya?ml$|^\.drone\.ya?ml$|^\.travis\.yml$"
)
DOCKER_FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.I)


def manifest_notes(name: str, text: str) -> list[str]:
    notes = []
    if name == "package.json":
        try:
            data = json.loads(text)
        except ValueError:
            return ["package.json is not valid JSON"]
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            for dep, spec in sorted((data.get(section) or {}).items()):
                spec = str(spec)
                if re.match(r"(?:git\+|git:|github:|https?:|file:|link:)", spec) or re.match(r"^[\w.-]+/[\w.-]+(?:#.*)?$", spec):
                    notes.append(f"{section}: {dep} resolves from a URL, Git or local path, not the registry")
                elif spec in ("*", "latest", ""):
                    notes.append(f"{section}: {dep} has no version constraint")
        for hook in ("preinstall", "install", "postinstall", "prepare"):
            if hook in (data.get("scripts") or {}):
                notes.append(f"own lifecycle script '{hook}' runs on install")
    elif name.startswith("requirements") and name.endswith(".txt"):
        reqs = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        if any(l.startswith("--extra-index-url") for l in reqs):
            notes.append("--extra-index-url mixes indexes; check for dependency confusion")
        pkgs = [l for l in reqs if not l.startswith("-")]
        unpinned = [l for l in pkgs if "==" not in l and "@" not in l]
        if unpinned:
            notes.append(f"{len(unpinned)} of {len(pkgs)} requirements are not pinned with ==")
        if pkgs and not any("--hash=" in l for l in reqs):
            notes.append("no --hash entries; installs are not hash-checked")
    return notes


def map_repo(root: Path, top: int = 40) -> dict:
    languages: Counter = Counter()
    ranked, manifests, ci_files, build_inputs = [], [], [], []
    names_by_dir: dict[str, set[str]] = {}
    stats = Counter()
    entries_in_paths = []

    all_files = list(iter_files(root))
    for _, rel in all_files:
        parent, _, base = rel.rpartition("/")
        names_by_dir.setdefault(parent, set()).add(base)

    for path, rel in all_files:
        base = path.name
        if CI_FILES.match(rel):
            ci_files.append(rel)
        if base in LOCKFILES or (base.startswith("requirements") and base.endswith(".txt")):
            ecosystem, locks = LOCKFILES.get(base, ("python", []))
            siblings = names_by_dir.get(rel.rpartition("/")[0], set())
            lock = next((l for l in locks if l in siblings), None)
            text = read_text(path) or ""
            notes = manifest_notes(base, text)
            if locks and lock is None:
                notes.insert(0, "no lockfile next to this manifest")
            manifests.append({"path": rel, "ecosystem": ecosystem,
                              "lockfile": (rel.rpartition("/")[0] + "/" + lock).lstrip("/") if lock else None,
                              "notes": notes})
        if base == "Dockerfile" or base.endswith(".Dockerfile") or base.startswith("Dockerfile."):
            stages = set()
            for n, line in enumerate((read_text(path) or "").splitlines(), start=1):
                m = DOCKER_FROM.match(line)
                if not m:
                    continue
                image, alias = m.group(1), m.group(2)
                if alias:
                    stages.add(alias.lower())
                if image.lower() in stages or image == "scratch" or image.startswith("$"):
                    continue
                if "@sha256:" not in image:
                    tag = image.rsplit("/", 1)[-1]
                    why = "uses the mutable 'latest' tag" if ":" not in tag or tag.endswith(":latest") else "is pinned by tag, not digest"
                    build_inputs.append({"path": rel, "line": n, "rule": "BASE_IMAGE_NOT_DIGEST_PINNED",
                                         "note": f"base image {why}"})

        suffix = path.suffix.lower()
        if suffix not in SOURCE_SUFFIXES:
            continue
        languages[suffix] += 1
        if TEST_PATH.search(rel):
            stats["test_or_example_files_not_ranked"] += 1
            continue
        text = read_text(path)
        if text is None:
            stats["source_files_skipped_large_or_binary"] += 1
            continue
        stats["source_files_ranked"] += 1
        entry_lines, sinks, auth = [], {}, 0
        for n, line in enumerate(text.splitlines(), start=1):
            if any(p.search(line) for p in ENTRY_PATTERNS):
                entry_lines.append(n)
            for cls, regex in SINK_PATTERNS.items():
                if regex.search(line):
                    sinks.setdefault(cls, []).append(n)
            if AUTH_HINT.search(line):
                auth += 1
        path_entry = bool(ENTRY_PATH.search(rel))
        if not (entry_lines or sinks or auth or path_entry):
            continue
        if entry_lines or path_entry:
            entries_in_paths.append(rel)
        sink_total = sum(len(v) for v in sinks.values())
        score = (5 * min(len(entry_lines) + (2 if path_entry else 0), 4) + 3 * len(sinks)
                 + min(sink_total, 10) + (2 if auth else 0))
        ranked.append({
            "path": rel, "score": score,
            "entry_point_lines": entry_lines[:20],
            "entry_point_by_path": path_entry,
            "sink_lines": {k: v[:20] for k, v in sorted(sinks.items())},
            "auth_hint_count": auth,
        })

    ranked.sort(key=lambda r: (-r["score"], r["path"]))
    manifests.sort(key=lambda m: m["path"])
    build_inputs.sort(key=lambda b: (b["path"], b["line"]))
    return {
        "tool": "productcraft-code-audit-map",
        "version": VERSION,
        "root": str(root),
        "result_type": "reading-order-hints-not-findings",
        "warnings": [
            "Hints come from line patterns. They set a reading order; they do not show a vulnerability or its absence.",
            "Test, example and vendored code is not ranked. Review it separately if it ships or runs in CI.",
        ],
        "languages_by_extension": dict(sorted(languages.items())),
        "stats": {
            "source_files_ranked": stats["source_files_ranked"],
            "test_or_example_files_not_ranked": stats["test_or_example_files_not_ranked"],
            "source_files_skipped_large_or_binary": stats["source_files_skipped_large_or_binary"],
            "files_with_entry_point_hints": len(entries_in_paths),
            "files_with_hints": len(ranked),
            "manifests": len(manifests),
            "manifests_without_lockfile": sum(1 for m in manifests if m["lockfile"] is None and LOCKFILES.get(Path(m["path"]).name, ("", []))[1]),
            "ci_files": len(ci_files),
            "file_limit_reached": len(all_files) >= MAX_FILES,
        },
        "ranked_files": ranked[:top],
        "manifests": manifests,
        "ci_files": sorted(ci_files),
        "build_inputs": build_inputs,
    }


# --------------------------------------------------------------------------
# workflows
# --------------------------------------------------------------------------

PRIVILEGED_TRIGGERS = {"pull_request_target", "workflow_run"}
PR_TRIGGERS = {"pull_request", "pull_request_target"}
HEAD_REF = re.compile(r"github\.event\.pull_request\.head\.(?:sha|ref)|github\.head_ref|refs/pull/|"
                      r"github\.event\.workflow_run\.head_(?:sha|branch)|gh\s+pr\s+checkout")
UNTRUSTED_CONTEXT = re.compile(
    r"github\.head_ref|github\.event\.(?:issue|pull_request|comment|review|review_comment|discussion|"
    r"discussion_comment|pages|commits|head_commit|workflow_run)\b[\w.\[\]*'\"-]*?\."
    r"(?:title|body|message|label|name|email|page_name|head_branch|default_branch|ref)\b"
)
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}")
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*['\"]?([^\s'\"#]+)")
SCRIPT_KEY = re.compile(r"^(\s*)(-\s+)?(run|script)\s*:\s*(.*)$")
PIPE_TO_SHELL = re.compile(r"\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b")


def strip_comment(line: str) -> str:
    return re.sub(r"(^|\s)#.*$", r"\1", line)


def workflow_triggers(lines: list[str]) -> set[str]:
    for i, raw in enumerate(lines):
        line = strip_comment(raw).rstrip()
        m = re.match(r"^(?:on|\"on\"|'on')\s*:\s*(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest:
            return set(re.findall(r"[a-z_]+", rest))
        found, child = set(), None
        for raw2 in lines[i + 1:]:
            l2 = strip_comment(raw2).rstrip()
            if not l2.strip():
                continue
            indent = len(l2) - len(l2.lstrip())
            if indent == 0:
                break
            child = indent if child is None else child
            if indent == child:
                m2 = re.match(r"^\s*-?\s*([a-z_]+)", l2)
                if m2:
                    found.add(m2.group(1))
        return found
    return set()


def script_lines(lines: list[str]):
    """Yield (line number, text) for every line inside a run: or script: value."""
    i, n = 0, len(lines)
    while i < n:
        m = SCRIPT_KEY.match(lines[i])
        if not m:
            i += 1
            continue
        key_col = len(m.group(1)) + len(m.group(2) or "")
        rest = m.group(4).strip()
        if rest and not re.match(r"^[|>][-+0-9]*$", strip_comment(rest).strip()):
            yield i + 1, rest
            i += 1
            continue
        j = i + 1
        while j < n:
            if lines[j].strip():
                if len(lines[j]) - len(lines[j].lstrip()) <= key_col:
                    break
                yield j + 1, lines[j]
            j += 1
        i = j


def check_workflow(rel: str, text: str) -> list[dict]:
    lines = text.splitlines()
    out = []

    def add(rule, severity, line, note):
        out.append({"rule": rule, "severity": severity, "file": rel, "line": line, "note": note})

    triggers = workflow_triggers(lines)
    privileged = sorted(triggers & PRIVILEGED_TRIGGERS)
    if privileged:
        add("PRIVILEGED_TRIGGER", "LOW", None,
            f"Trigger {', '.join(privileged)} runs with the base repository's secrets and a write-capable token. "
            "Confirm no untrusted code or data is executed in this workflow.")
        for n, line in enumerate(lines, start=1):
            code = strip_comment(line)
            if HEAD_REF.search(code) and re.search(r"\bref\s*:|checkout|fetch", code):
                add("UNTRUSTED_CHECKOUT_IN_PRIVILEGED_WORKFLOW", "HIGH", n,
                    "Checks out contributor-controlled code in a privileged workflow. Any build, install or test step "
                    "that follows can run that code with the workflow's secrets.")
    if not re.search(r"^\s*permissions\s*:", text, re.M):
        add("NO_PERMISSIONS_BLOCK", "LOW", None,
            "No permissions key: the GITHUB_TOKEN gets the repository or organization default, which may be write access.")
    for n, line in enumerate(lines, start=1):
        code = strip_comment(line)
        if re.match(r"^\s*permissions\s*:\s*write-all\b", code):
            add("WRITE_ALL_PERMISSIONS", "MEDIUM", n, "Token gets write access to every scope; grant only what the jobs use.")
        if re.search(r"^\s*runs-on\s*:.*\bself-hosted\b", code) and triggers & PR_TRIGGERS:
            add("SELF_HOSTED_RUNNER_ON_PULL_REQUESTS", "MEDIUM", n,
                "Pull requests can run code on a self-hosted runner; on a public repository that runner is exposed to anyone.")
        m = USES.match(code)
        if m:
            target = m.group(1)
            if target.startswith("./") or target.startswith("docker://"):
                if target.startswith("docker://") and "@sha256:" not in target:
                    add("UNPINNED_ACTION", "MEDIUM", n, "Container action is not pinned by digest.")
                continue
            ref = target.rsplit("@", 1)[1] if "@" in target else ""
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                owner = target.split("/", 1)[0].lower()
                first_party = owner in ("actions", "github")
                add("UNPINNED_ACTION", "LOW" if first_party else "MEDIUM", n,
                    ("GitHub-owned" if first_party else "Third-party") +
                    " action is referenced by a movable tag or branch, not a full commit SHA.")
    for n, line in script_lines(lines):
        for expr in EXPRESSION.findall(line):
            m = UNTRUSTED_CONTEXT.search(expr)
            if m and ".base." not in m.group(0):
                add("UNTRUSTED_INPUT_IN_SCRIPT", "HIGH", n,
                    "Attacker-controllable event data is expanded directly into a script. Pass it through env: and "
                    "quote the variable instead.")
                break
        if PIPE_TO_SHELL.search(line):
            add("REMOTE_SCRIPT_PIPED_TO_SHELL", "MEDIUM", n,
                "Downloads and executes a script without an integrity check; pin a version and verify a checksum.")
    return out


def check_workflows(root: Path) -> dict:
    wf_dir = root / ".github" / "workflows"
    files = sorted(p for p in wf_dir.glob("*") if p.suffix in (".yml", ".yaml") and p.is_file() and not p.is_symlink()) \
        if wf_dir.is_dir() else []
    results = []
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        results.extend(check_workflow(path.relative_to(root).as_posix(), text))
    results.sort(key=severity_key)
    counts = Counter(r["severity"] for r in results)
    return {
        "tool": "productcraft-code-audit-workflows",
        "version": VERSION,
        "root": str(root),
        "result_type": "candidates-not-findings",
        "warnings": [
            "Line-based checks of GitHub Actions files only. Other CI systems, repository settings, branch protection, "
            "environment protection rules and organization defaults are NOT_VERIFIED.",
        ],
        "stats": {"workflow_files": len(files), "candidate_count": len(results),
                  "by_severity": dict(sorted(counts.items(), key=lambda kv: SEVERITY_ORDER[kv[0]]))},
        "candidates": results[:MAX_RESULTS],
        "truncated": len(results) > MAX_RESULTS,
    }


# --------------------------------------------------------------------------
# history
# --------------------------------------------------------------------------

SENSITIVE_NAME = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\.[\w.-]+)?|[^/]+\.(?:pem|key|p12|pfx|jks|keystore|ppk|kdbx|tfstate)|"
    r"id_(?:rsa|dsa|ecdsa|ed25519)|credentials(?:\.json)?|service[-_]?account[^/]*\.json|"
    r"\.npmrc|\.pypirc|\.netrc|\.htpasswd|\.dev\.vars)$"
)
SAFE_NAMES = {".env.example", ".env.sample", ".env.template", ".env.defaults", ".env.dist"}


def git(root: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = ["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.quotepath=off", "-C", str(root), *args]
    return subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)


def scan_history(root: Path, max_commits: int = 5000, timeout: int = 300) -> dict:
    base = {
        "tool": "productcraft-code-audit-history",
        "version": VERSION,
        "root": str(root),
        "result_type": "candidates-not-findings",
        "warnings": [
            "Covers commits reachable from local refs (branches, tags, stash). Unfetched remote refs, pull request refs "
            "on the host, forks, reflog-only and unreachable objects, CI logs and built artifacts are NOT scanned.",
            "A hit is a secret-shaped value, not proof of a live credential. No value is stored in this output.",
        ],
    }
    try:
        probe = git(root, "rev-parse", "--is-inside-work-tree", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return {**base, "status": "git_unavailable", "stats": {}, "candidates": [], "sensitive_files": []}
    if probe.returncode != 0:
        return {**base, "status": "not_a_git_repository", "stats": {}, "candidates": [], "sensitive_files": []}
    has_commits = git(root, "rev-parse", "--verify", "-q", "HEAD", timeout=15).returncode == 0
    if not has_commits:
        return {**base, "status": "no_commits", "stats": {}, "candidates": [], "sensitive_files": []}

    tracked = set(os.fsdecode(p) for p in git(root, "ls-files", "-z").stdout.split(b"\x00") if p)
    cmd = ["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.quotepath=off", "-C", str(root),
           "log", "--all", "--no-color", "--no-ext-diff", "--no-textconv", "-p", "--unified=0",
           f"--max-count={max_commits}", "--format=%x01%H"]
    total = git(root, "rev-list", "--all", "--count", timeout=timeout).stdout.decode().strip()
    total_commits = int(total) if total.isdigit() else None
    seen, results, commits = set(), [], 0
    truncated = timed_out = False
    deadline = time.monotonic() + timeout
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    commit, current, prev = "", None, ""
    try:
        for raw in proc.stdout:
            if time.monotonic() > deadline:
                timed_out = True
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if line.startswith("\x01"):
                commit, current = line[1:].strip(), None
                commits += 1
            elif line.startswith("+++ ") and prev.startswith("--- "):
                target = line[4:].strip().strip('"')
                current = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
            elif line.startswith("+") and current is not None:
                for rule, severity in secret_hits(line[1:]):
                    key = (rule, current, commit)
                    if key in seen:
                        continue
                    seen.add(key)
                    if len(results) >= MAX_RESULTS:
                        truncated = True
                        continue
                    results.append({"rule": rule, "severity": severity, "commit": commit[:12], "path": current})
            prev = line
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        proc.wait()

    worktree_rules: dict[str, set[str]] = {}
    for item in results:
        path = item["path"]
        if path not in worktree_rules:
            text = read_text(root / path) if path in tracked and (root / path).is_file() else None
            worktree_rules[path] = {r for r, _ in secret_hits_all(text)} if text else set()
        item["tracked_at_head"] = path in tracked
        item["same_rule_matches_current_file"] = item["rule"] in worktree_rules[path]
        item["note"] = SECRET_NOTES.get(item["rule"], "Confirm the credential type and owner; if real, it needs rotation even if later removed.")

    added = git(root, "log", "--all", "--format=", "--name-only", "--diff-filter=A",
                f"--max-count={max_commits}", timeout=timeout)
    sensitive = sorted({p for p in added.stdout.decode("utf-8", errors="replace").splitlines()
                        if p and SENSITIVE_NAME.search(p) and Path(p).name not in SAFE_NAMES})
    sensitive_files = [{"path": p, "tracked_at_head": p in tracked} for p in sensitive]

    results.sort(key=lambda r: (SEVERITY_ORDER[r["severity"]], r["path"], r["rule"], r["commit"]))
    counts = Counter(r["severity"] for r in results)
    return {
        **base,
        "status": "scanned_partial" if (truncated or timed_out or (total_commits or 0) > commits) else "scanned",
        "stats": {
            "commits_scanned": commits, "commits_reachable": total_commits, "max_commits": max_commits,
            "timed_out": timed_out,
            "truncated": truncated, "candidate_count": len(results),
            "by_severity": dict(sorted(counts.items(), key=lambda kv: SEVERITY_ORDER[kv[0]])),
            "sensitive_file_names": len(sensitive_files),
        },
        "candidates": results,
        "sensitive_files": sensitive_files,
    }


def secret_hits_all(text: str) -> list[tuple[str, str]]:
    hits = []
    for line in text.splitlines():
        hits.extend(secret_hits(line))
    return hits


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------

CONFIDENCE = {"CONFIRMED", "LIKELY", "POSSIBLE"}
STATUS = {"OPEN", "FIXED", "ACCEPTED", "FALSE_POSITIVE"}
EVIDENCE = {"TESTED_LOCAL", "TESTED_STAGING", "DEPLOYED_OBSERVED", "STATIC_CONFIRMED", "INFERRED", "NOT_TESTED"}
CELL_STATUS = {"PASS", "FAIL", "NEEDS_REVIEW", "NOT_APPLICABLE", "NOT_VERIFIED"}
REQUIRED = ("id", "title", "class", "file", "confidence", "status", "evidence_type", "evidence_summary")


def walk_strings(value, path=""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk_strings(v, f"{path}[{i}]")


def validate_findings(data) -> dict:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {"errors": ["top level must be a JSON object"], "result": "INVALID"}
    findings = data.get("findings")
    coverage = data.get("coverage", [])
    if not isinstance(findings, list):
        errors.append("'findings' must be a list (use [] when nothing was found)")
        findings = []
    if not isinstance(coverage, list):
        errors.append("'coverage' must be a list")
        coverage = []
    if not isinstance(data.get("audit"), dict):
        errors.append("'audit' object with repository, revision, mode and scope is required")

    by_id: dict[str, dict] = {}
    for i, f in enumerate(findings):
        where = f"findings[{i}]"
        if not isinstance(f, dict):
            errors.append(f"{where}: must be an object")
            continue
        fid = f.get("id")
        where = f"finding {fid}" if fid else where
        for field in REQUIRED:
            if not f.get(field):
                errors.append(f"{where}: missing '{field}'")
        if fid in by_id:
            errors.append(f"{where}: duplicate id")
        if fid:
            by_id[fid] = f
        conf, status, ev, sev = f.get("confidence"), f.get("status"), f.get("evidence_type"), f.get("severity")
        if conf and conf not in CONFIDENCE:
            errors.append(f"{where}: confidence must be one of {sorted(CONFIDENCE)}")
        if status and status not in STATUS:
            errors.append(f"{where}: status must be one of {sorted(STATUS)}")
        if ev and ev not in EVIDENCE:
            errors.append(f"{where}: evidence_type must be one of {sorted(EVIDENCE)}")
        if sev is not None and sev not in SEVERITY_ORDER:
            errors.append(f"{where}: severity must be one of {list(SEVERITY_ORDER)}")
        file = str(f.get("file") or "")
        if file.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", file) or ".." in Path(file).parts:
            errors.append(f"{where}: 'file' must be repository-relative without '..'")
        line = f.get("line")
        if line is not None and (not isinstance(line, int) or isinstance(line, bool) or line < 1):
            errors.append(f"{where}: 'line' must be a positive integer")
        if status == "FALSE_POSITIVE":
            if not f.get("rejection_reason"):
                errors.append(f"{where}: FALSE_POSITIVE needs 'rejection_reason'")
        else:
            if conf in ("CONFIRMED", "LIKELY"):
                if not sev:
                    errors.append(f"{where}: {conf} finding needs 'severity'")
                if not f.get("actor"):
                    errors.append(f"{where}: {conf} finding needs 'actor' (who can trigger it)")
                if not isinstance(f.get("preconditions"), list):
                    errors.append(f"{where}: {conf} finding needs 'preconditions' as a list (empty if none)")
                if not f.get("impact"):
                    errors.append(f"{where}: {conf} finding needs 'impact'")
                if status == "OPEN" and not f.get("fix"):
                    errors.append(f"{where}: open {conf} finding needs a proposed 'fix'")
            if conf == "POSSIBLE" and sev:
                errors.append(f"{where}: POSSIBLE leads carry no severity; confirm first or remove 'severity'")
            if conf == "POSSIBLE" and not f.get("next_check"):
                errors.append(f"{where}: POSSIBLE lead needs 'next_check' (the exact check that would settle it)")
            if conf == "LIKELY" and not f.get("unverified_condition"):
                errors.append(f"{where}: LIKELY finding needs 'unverified_condition' (the fact outside the repository)")
            if conf == "CONFIRMED" and ev in ("INFERRED", "NOT_TESTED"):
                errors.append(f"{where}: CONFIRMED needs an executed test or a complete static trace, not {ev}")
        if status == "FIXED":
            if not f.get("regression_test"):
                errors.append(f"{where}: FIXED needs 'regression_test'")
            if not f.get("verification"):
                errors.append(f"{where}: FIXED needs 'verification' (commands run and their results)")
        if status == "ACCEPTED" and not f.get("accepted_by"):
            errors.append(f"{where}: ACCEPTED needs 'accepted_by' (the accountable owner)")

    cells = Counter()
    for i, c in enumerate(coverage):
        where = f"coverage[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{where}: must be an object")
            continue
        where = f"coverage {c.get('id')}" if c.get("id") else where
        for field in ("id", "surface", "class", "status"):
            if not c.get(field):
                errors.append(f"{where}: missing '{field}'")
        st = c.get("status")
        if st and st not in CELL_STATUS:
            errors.append(f"{where}: status must be one of {sorted(CELL_STATUS)}")
            continue
        cells[st] += 1
        refs = c.get("findings") or []
        for ref in refs:
            if ref not in by_id:
                errors.append(f"{where}: references unknown finding {ref}")
        if st == "PASS" and not c.get("evidence"):
            errors.append(f"{where}: PASS needs 'evidence' (paths read, invariant checked or test run)")
        if st in ("NOT_APPLICABLE", "NOT_VERIFIED") and not c.get("reason"):
            errors.append(f"{where}: {st} needs 'reason'")
        if st == "FAIL" and not refs:
            errors.append(f"{where}: FAIL needs the finding ids in 'findings'")
        if st in ("PASS", "NOT_APPLICABLE"):
            for ref in refs:
                f = by_id.get(ref, {})
                if f.get("confidence") == "CONFIRMED" and f.get("status") in ("OPEN", "ACCEPTED"):
                    errors.append(f"{where}: cannot be {st} while confirmed finding {ref} is {f.get('status')}")

    for path, value in walk_strings(data):
        hits = secret_hits(value)
        if hits:
            errors.append(f"{path}: contains a secret-shaped value ({hits[0][0]}); report type and location only")

    live = [f for f in by_id.values() if f.get("status") != "FALSE_POSITIVE"]
    confirmed_open = [f for f in live if f.get("confidence") == "CONFIRMED" and f.get("status") in ("OPEN", "ACCEPTED")]
    leads_open = [f for f in live if f.get("confidence") in ("LIKELY", "POSSIBLE") and f.get("status") == "OPEN"]
    if confirmed_open:
        worst = min((SEVERITY_ORDER.get(f.get("severity"), 9) for f in confirmed_open), default=9)
        worst_name = next((k for k, v in SEVERITY_ORDER.items() if v == worst), "UNRATED")
        result = f"FAIL (highest open confirmed severity: {worst_name})"
    elif leads_open or cells["NEEDS_REVIEW"] or cells["NOT_VERIFIED"] or cells["FAIL"]:
        result = "NEEDS_REVIEW"
    elif sum(cells.values()) == 0:
        result = "INSUFFICIENT_EVIDENCE"
    else:
        result = "PASS (scoped)"
    if errors:
        result = "INVALID"
    return {
        "errors": errors,
        "result": result,
        "findings_by_confidence": dict(sorted(Counter(f.get("confidence") for f in live).items())),
        "findings_by_status": dict(sorted(Counter(f.get("status") for f in by_id.values()).items())),
        "open_confirmed_by_severity": dict(sorted(Counter(f.get("severity") for f in confirmed_open).items())),
        "coverage_by_status": dict(sorted(cells.items())),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def fail_threshold(items: list[dict], level: str) -> bool:
    if level == "never":
        return False
    limit = SEVERITY_ORDER["HIGH" if level == "high" else "MEDIUM"]
    return any(SEVERITY_ORDER.get(i.get("severity"), 9) <= limit for i in items)


def cmd_map(opts) -> int:
    result = map_repo(resolve_root(opts.root), opts.top)
    s = result["stats"]
    print(f"code_audit map: {s['source_files_ranked']} source files ranked, {s['test_or_example_files_not_ranked']} "
          f"test/example files not ranked, {s['files_with_entry_point_hints']} with entry-point hints, "
          f"{s['manifests']} manifests ({s['manifests_without_lockfile']} without lockfile), {s['ci_files']} CI files.")
    for i, r in enumerate(result["ranked_files"][:15], start=1):
        sinks = ",".join(r["sink_lines"]) or "-"
        print(f"  {i:2}. {r['path']}  score={r['score']} entry={len(r['entry_point_lines'])} sinks={sinks} "
              f"auth_hints={r['auth_hint_count']}")
    print("Hints set a reading order. They are not findings and a missing hint is not a pass.")
    if opts.json_out:
        write_json(result, opts.json_out)
        print(f"JSON written: {opts.json_out}")
    return 0


def cmd_workflows(opts) -> int:
    result = check_workflows(resolve_root(opts.root))
    s = result["stats"]
    print(f"code_audit workflows: {s['workflow_files']} GitHub Actions files, {s['candidate_count']} candidates {s['by_severity']}.")
    for c in result["candidates"][:30]:
        loc = f"{c['file']}:{c['line']}" if c["line"] else c["file"]
        print(f"  [{c['severity']}] {c['rule']} {loc}")
    print("Candidates need confirmation against the workflow's real triggers, permissions and repository settings.")
    if opts.json_out:
        write_json(result, opts.json_out)
        print(f"JSON written: {opts.json_out}")
    return 1 if fail_threshold(result["candidates"], opts.fail_on) else 0


def cmd_history(opts) -> int:
    result = scan_history(resolve_root(opts.root), opts.max_commits, opts.timeout)
    s = result["stats"]
    if result["status"] in ("git_unavailable", "not_a_git_repository", "no_commits"):
        print(f"code_audit history: {result['status']}; Git history is NOT_VERIFIED.")
    else:
        print(f"code_audit history ({result['status']}): {s['commits_scanned']} commits, {s['candidate_count']} "
              f"secret-shaped candidates {s['by_severity']}, {s['sensitive_file_names']} sensitive file names ever added. "
              "No values printed.")
        for c in result["candidates"][:30]:
            state = "still matches current file" if c["same_rule_matches_current_file"] else "not in current file"
            print(f"  [{c['severity']}] {c['rule']} {c['path']} @ {c['commit']} ({state})")
        for f in result["sensitive_files"][:30]:
            print(f"  [FILE] {f['path']} ({'tracked now' if f['tracked_at_head'] else 'only in history'})")
    if opts.json_out:
        write_json(result, opts.json_out)
        print(f"JSON written: {opts.json_out}")
    return 1 if fail_threshold(result["candidates"], opts.fail_on) else 0


def cmd_findings(opts) -> int:
    try:
        data = json.loads(Path(opts.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Error: cannot read findings JSON: {exc}", file=sys.stderr)
        return 2
    report = validate_findings(data)
    for e in report["errors"]:
        print(f"ERROR {e}")
    print(f"Findings by confidence: {report['findings_by_confidence']}; by status: {report['findings_by_status']}")
    print(f"Coverage cells: {report['coverage_by_status']}; open confirmed by severity: {report['open_confirmed_by_severity']}")
    print(f"Audit result: {report['result']}")
    return 1 if report["errors"] else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="code_audit.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("map", help="rank files by entry-point and sink hints; list manifests and CI files")
    p.add_argument("--root", default=".", help="repository root (default: .)")
    p.add_argument("--top", type=int, default=40, help="number of ranked files kept in JSON (default: 40)")
    p.add_argument("--json-out", help="write the full result as JSON (mode 0600)")
    p.set_defaults(func=cmd_map)

    p = sub.add_parser("workflows", help="check .github/workflows for risky CI patterns")
    p.add_argument("--root", default=".", help="repository root (default: .)")
    p.add_argument("--json-out", help="write the full result as JSON (mode 0600)")
    p.add_argument("--fail-on", choices=["never", "high", "medium"], default="never",
                   help="exit 1 when a candidate at or above this severity exists (default: never)")
    p.set_defaults(func=cmd_workflows)

    p = sub.add_parser("history", help="scan local Git history for secret-shaped values; never prints values")
    p.add_argument("--root", default=".", help="repository root (default: .)")
    p.add_argument("--max-commits", type=int, default=5000, help="newest commits to scan across all refs (default: 5000)")
    p.add_argument("--timeout", type=int, default=300, help="seconds before the scan stops and reports partial (default: 300)")
    p.add_argument("--json-out", help="write the full result as JSON (mode 0600)")
    p.add_argument("--fail-on", choices=["never", "high", "medium"], default="never",
                   help="exit 1 when a candidate at or above this severity exists (default: never)")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("findings", help="validate a findings JSON file and print the audit result")
    p.add_argument("--file", required=True, help="path to the findings JSON (e.g. security/code-audit-findings.json)")
    p.set_defaults(func=cmd_findings)
    return ap


def main(argv: list[str] | None = None) -> int:
    opts = build_parser().parse_args(argv)
    try:
        return opts.func(opts)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
