#!/usr/bin/env python3
"""ProductCraft supply-chain helper. Offline, read-only, deterministic.

Subcommands:
  actions    Map who can start each GitHub Actions workflow and where text an
             outsider wrote can flow: into the prompt or environment of an AI
             agent step, into GITHUB_ENV / GITHUB_PATH / GITHUB_OUTPUT, into
             scripts of composite actions and reusable workflows, and into
             shell commands built from agent output. Also reports which token
             scopes, secrets and settings each agent step can reach, and
             conditions that are always true or easy to spoof.
             It complements `code_audit.py workflows` and does not repeat it.
  lockfiles  Read lockfiles (npm, Yarn, pnpm, uv, Poetry, Pipenv, Cargo, Go
             modules, Bundler, Composer) for packages that run code at install
             time, sources outside the registry, plain-HTTP transport, missing
             integrity hashes, mixed registries and credentials inside URLs.

Results are candidates to confirm by reading the file, never findings.
Nothing is fetched, installed or executed. The output never contains matched
source text, prompt text, full URLs or secret values: only rule names,
locations, identifiers (job, step, variable and package names) and hosts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on old Pythons
    tomllib = None

VERSION = "1.0.0"
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".agents", ".claude", ".venv", "venv", "env",
    "node_modules", "bower_components", ".next", ".nuxt", ".svelte-kit",
    "dist", "build", "out", "coverage", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".tox", "vendor", "third_party", "target", ".turbo",
    ".cache", ".angular", ".idea", ".gradle", "Pods", "DerivedData",
}
MAX_YAML_BYTES = 2_000_000
MAX_LOCK_BYTES = 80_000_000
MAX_FILES = 50_000
MAX_RESULTS = 500
MAX_LISTED = 200


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def iter_files(root: Path):
    """Yield (path, posix relative path) in sorted order, skipping symlinks and SKIP_DIRS."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            count += 1
            if count > MAX_FILES:
                return
            yield path, path.relative_to(root).as_posix()


def read_text(path: Path, limit: int) -> str | None:
    try:
        if path.stat().st_size > limit:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def write_json(result: dict, out: str) -> None:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=False)
        handle.write("\n")


def resolve_root(value: str) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    return root


def severity_key(item: dict) -> tuple:
    return (SEVERITY_ORDER.get(item.get("severity", "INFO"), 9), item.get("file") or "",
            item.get("line") or 0, item.get("rule", ""), item.get("job") or "", item.get("step") or "")


def fail_threshold(items: list[dict], level: str) -> bool:
    if level == "never":
        return False
    limit = SEVERITY_ORDER["HIGH" if level == "high" else "MEDIUM"]
    return any(SEVERITY_ORDER.get(i.get("severity"), 9) <= limit for i in items)


def by_severity(items: list[dict]) -> dict:
    counts = Counter(i["severity"] for i in items)
    return dict(sorted(counts.items(), key=lambda kv: SEVERITY_ORDER[kv[0]]))


# --------------------------------------------------------------------------
# A small YAML reader for GitHub Actions files
#
# It understands block mappings and sequences, plain and quoted scalars,
# literal and folded block scalars, simple flow collections, comments,
# anchors, aliases and merge keys, and keeps line numbers. It is tolerant:
# lines it does not understand are skipped, so results are leads.
# --------------------------------------------------------------------------


class Node:
    __slots__ = ("kind", "value", "line", "lines", "style")

    def __init__(self, kind: str, value, line: int, lines=None, style: str | None = None):
        self.kind = kind          # "map", "seq" or "scalar"
        self.value = value        # dict, list, or str / None
        self.line = line          # 1-based line where the node starts
        self.lines = lines or []  # scalars: [(line, source text)] for every line of the value
        self.style = style        # block scalars: "|", "|-", ">", ...

    def get(self, key: str, default=None):
        if self.kind == "map":
            return self.value.get(key, default)
        return default

    def items(self):
        return list(self.value.items()) if self.kind == "map" else []

    def seq(self):
        return list(self.value) if self.kind == "seq" else []


_KEY = re.compile(r"""^(?P<key>"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s#'"\[\]{},&*!|>%@`-][^#]*?|<<)\s*:(?:[ \t]+(?P<rest>.*))?$""")
_BLOCK_HEADER = re.compile(r"^[|>](?:[1-9][-+]?|[-+][1-9]?)?$")


def strip_comment(text: str) -> str:
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"') and (i == 0 or text[i - 1] in " \t[{,:"):
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1].replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n").replace("\\t", "\t")
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    return text


def _flow_balanced(text: str) -> bool:
    depth, quote = 0, None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth <= 0


def _parse_flow(text: str, line: int) -> Node:
    pos = 0

    def ws():
        nonlocal pos
        while pos < len(text) and text[pos] in " \t\r\n":
            pos += 1

    def scalar_until(stops: str) -> str:
        nonlocal pos
        ws()
        if pos < len(text) and text[pos] in "'\"":
            q = text[pos]
            end = pos + 1
            while end < len(text):
                if text[end] == q:
                    if q == "'" and end + 1 < len(text) and text[end + 1] == "'":
                        end += 2
                        continue
                    if q == '"' and text[end - 1] == "\\":
                        end += 1
                        continue
                    break
                end += 1
            raw = text[pos:end + 1]
            pos = end + 1
            return unquote(raw)
        start = pos
        while pos < len(text) and text[pos] not in stops:
            pos += 1
        return text[start:pos].strip()

    def value() -> Node:
        nonlocal pos
        ws()
        if pos < len(text) and text[pos] == "[":
            pos += 1
            items = []
            while True:
                ws()
                if pos >= len(text):
                    raise ValueError("unterminated flow sequence")
                if text[pos] == "]":
                    pos += 1
                    return Node("seq", items, line)
                items.append(value())
                ws()
                if pos < len(text) and text[pos] == ",":
                    pos += 1
        if pos < len(text) and text[pos] == "{":
            pos += 1
            mapping = {}
            while True:
                ws()
                if pos >= len(text):
                    raise ValueError("unterminated flow mapping")
                if text[pos] == "}":
                    pos += 1
                    return Node("map", mapping, line)
                key = scalar_until(":,}")
                ws()
                if pos < len(text) and text[pos] == ":":
                    pos += 1
                    mapping[key] = value()
                else:
                    mapping[key] = Node("scalar", None, line, [(line, "")])
                ws()
                if pos < len(text) and text[pos] == ",":
                    pos += 1
        raw = scalar_until(",]}")
        return Node("scalar", raw, line, [(line, raw)])

    try:
        node = value()
        return node
    except (ValueError, IndexError):
        return Node("scalar", text, line, [(line, text)])


def _fold(texts: list[str]) -> str:
    """Folded block scalar: single line breaks become spaces, blank lines and indented lines keep breaks."""
    out, prev = "", None
    for t in texts:
        if prev is None:
            out = t
        elif t == "":
            out += "\n"
        elif prev == "":
            out += t
        elif t[:1] in (" ", "\t") or prev[:1] in (" ", "\t"):
            out += "\n" + t
        else:
            out += " " + t
        prev = t
    return out


class _Reader:
    def __init__(self, text: str):
        self.raw = text.splitlines()
        self.i = 0
        self.pending: list[tuple[int, int, str]] = []
        self.anchors: dict[str, Node] = {}

    def peek(self):
        if self.pending:
            return self.pending[0]
        while self.i < len(self.raw):
            raw = self.raw[self.i]
            stripped = raw.strip()
            if not stripped or stripped.startswith("#") or stripped in ("---", "...") or stripped.startswith("--- "):
                self.i += 1
                continue
            lineno = self.i + 1
            self.i += 1
            indent = len(raw) - len(raw.lstrip(" "))
            content = raw.strip()
            entries = []
            while content == "-" or content.startswith("- "):
                entries.append((lineno, indent, "-"))
                rest = content[1:]
                indent += 1 + (len(rest) - len(rest.lstrip(" ")))
                content = rest.strip()
            if content:
                entries.append((lineno, indent, content))
            self.pending = entries
            return self.pending[0]
        return None

    def next(self):
        entry = self.peek()
        if self.pending:
            self.pending.pop(0)
        return entry

    def node(self, indent: int) -> Node:
        e = self.peek()
        if e is None or e[1] < indent:
            return Node("scalar", None, e[0] if e else 0, [(e[0] if e else 0, "")])
        if e[2] == "-":
            return self.sequence(e[1])
        if _KEY.match(e[2]):
            return self.mapping(e[1])
        self.next()
        return self.inline_value(strip_comment(e[2]), e[0], e[1] - 1, e[2])

    def inline_value(self, content: str, lineno: int, threshold: int, source: str) -> Node:
        anchor = None
        m = re.match(r"^&([^\s]+)\s*(.*)$", content)
        if m:
            anchor, content = m.group(1), m.group(2)
        content = re.sub(r"^!!?[^\s]*\s*", "", content) if content.startswith("!") else content
        if content.startswith("*"):
            target = self.anchors.get(content[1:].strip())
            return target if target is not None else Node("scalar", content, lineno, [(lineno, source)])
        if _BLOCK_HEADER.match(content):
            node = self.block(threshold, content, lineno)
        elif content.startswith(("[", "{")):
            text = content
            while not _flow_balanced(text) and self.i < len(self.raw) and not self.pending:
                nxt = self.raw[self.i]
                if nxt.strip() and len(nxt) - len(nxt.lstrip(" ")) <= threshold:
                    break
                text += " " + strip_comment(nxt.strip())
                self.i += 1
            node = _parse_flow(text, lineno)
        elif content == "" and anchor:
            nxt = self.peek()
            node = self.node(nxt[1]) if nxt and nxt[1] > threshold else Node("scalar", None, lineno, [(lineno, "")])
        elif content in ("~", "null", "Null", "NULL"):
            node = Node("scalar", None, lineno, [(lineno, source)])
        else:
            node = Node("scalar", unquote(content), lineno, [(lineno, source)])
        if anchor:
            self.anchors[anchor] = node
        return node

    def block(self, threshold: int, header: str, keyline: int) -> Node:
        explicit = next((int(c) for c in header if c.isdigit()), 0)
        lines: list[tuple[int, str]] = []
        content_indent = None
        while self.i < len(self.raw):
            raw = self.raw[self.i]
            if not raw.strip():
                lines.append((self.i + 1, ""))
                self.i += 1
                continue
            ind = len(raw) - len(raw.lstrip(" "))
            if content_indent is None:
                if ind <= threshold:
                    break
                content_indent = (threshold + explicit) if explicit else ind
            if ind < content_indent:
                break
            lines.append((self.i + 1, raw[content_indent:]))
            self.i += 1
        while lines and lines[-1][1] == "":
            lines.pop()
        while lines and lines[0][1] == "":
            lines.pop(0)
        text = "\n".join(t for _, t in lines) if header[0] == "|" else _fold([t for _, t in lines])
        chomp = "-" if "-" in header else ("+" if "+" in header else "")
        if lines and chomp != "-":
            text += "\n"
        return Node("scalar", text, lines[0][0] if lines else keyline, lines or [(keyline, "")], style=header[0] + chomp)

    def mapping(self, indent: int) -> Node:
        first = self.peek()
        node = Node("map", {}, first[0])
        last: Node | None = None
        while True:
            e = self.peek()
            if e is None or e[1] < indent:
                break
            if e[1] > indent or e[2] == "-":
                if e[2] == "-" and e[1] == indent:
                    break
                self.next()
                if last is not None and last.kind == "scalar" and last.style is None and last.value is not None:
                    last.value += " " + strip_comment(e[2])
                    last.lines.append((e[0], e[2]))
                continue
            m = _KEY.match(e[2])
            if not m:
                self.next()
                continue
            self.next()
            key = unquote(m.group("key"))
            rest = strip_comment(m.group("rest") or "")
            if rest == "":
                nxt = self.peek()
                if nxt is not None and nxt[1] > indent:
                    value = self.node(nxt[1])
                elif nxt is not None and nxt[1] == indent and nxt[2] == "-":
                    value = self.sequence(indent)
                else:
                    value = Node("scalar", None, e[0], [(e[0], e[2])])
            else:
                value = self.inline_value(rest, e[0], indent, e[2])
                if rest.startswith("&") and value.kind == "scalar" and value.value is None:
                    nxt = self.peek()
                    if nxt is not None and nxt[1] == indent and nxt[2] == "-":
                        value = self.sequence(indent)
                        self.anchors[rest[1:].split()[0]] = value
            if key == "<<" and value.kind == "map":
                for k, v in value.value.items():
                    node.value.setdefault(k, v)
                last = None
                continue
            node.value[key] = value
            last = value
        return node

    def sequence(self, indent: int) -> Node:
        first = self.peek()
        node = Node("seq", [], first[0])
        while True:
            e = self.peek()
            if e is None or e[1] < indent:
                break
            if e[1] > indent:
                self.next()
                continue
            if e[2] != "-":
                break
            self.next()
            nxt = self.peek()
            if nxt is not None and nxt[1] > indent:
                node.value.append(self.node(nxt[1]))
            else:
                node.value.append(Node("scalar", None, e[0], [(e[0], "")]))
        return node


def parse_yaml(text: str) -> Node:
    reader = _Reader(text)
    first = reader.peek()
    if first is None:
        return Node("map", {}, 1)
    return reader.node(first[1])


def scalar(node: Node | None) -> str:
    if node is None or node.kind != "scalar" or node.value is None:
        return ""
    return str(node.value)


def all_text(node: Node | None) -> str:
    """Every scalar inside a node, joined with newlines (for searching)."""
    if node is None:
        return ""
    if node.kind == "scalar":
        return scalar(node)
    parts = []
    if node.kind == "map":
        for k, v in node.value.items():
            parts.append(f"{k}: {all_text(v)}" if v is not None and v.kind == "scalar" else k)
            if v is not None and v.kind != "scalar":
                parts.append(all_text(v))
    else:
        parts.extend(all_text(v) for v in node.value)
    return "\n".join(p for p in parts if p)


def scalar_lines(node: Node | None):
    """Yield (line, text) for every source line of every scalar inside a node."""
    if node is None:
        return
    if node.kind == "scalar":
        if node.style:
            yield from node.lines
        else:
            yield (node.line, scalar(node))
        return
    children = node.value.values() if node.kind == "map" else node.value
    for child in children:
        yield from scalar_lines(child)


# --------------------------------------------------------------------------
# actions
# --------------------------------------------------------------------------

EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
UNTRUSTED = re.compile(
    r"\bgithub\.head_ref\b"
    r"|\bgithub\.event\.(?:issue|pull_request|comment|review|review_comment|discussion|discussion_comment|"
    r"pages|commits|head_commit|workflow_run|merge_group)\b[\w.\[\]*'\"-]*?\."
    r"(?:title|body|message|name|email|page_name|head_branch|head_ref|ref|label|display_title|description|"
    r"default_branch)\b"
    r"|\btoJSON\(\s*github\.event\b"
)
INPUT_REF = re.compile(r"\b(?:inputs|github\.event\.inputs)\.([A-Za-z_][\w-]*)")
SECRET_REF = re.compile(r"\bsecrets\.([A-Za-z_][\w]*)")
STEP_OUTPUT = re.compile(r"\bsteps\.([A-Za-z_][\w-]*)\.outputs\b")
NEEDS_OUTPUT = re.compile(r"\bneeds\.([A-Za-z_][\w-]*)\.outputs\.([A-Za-z_][\w-]*)")
HEAD_REF = re.compile(
    r"github\.event\.pull_request\.head\.(?:sha|ref|repo\.full_name)|github\.head_ref|refs/pull/|"
    r"\bpull/[^\s/'\"]+/(?:head|merge)\b|github\.event\.workflow_run\.head_(?:sha|branch|repository)|"
    r"\bgh\s+pr\s+checkout\b"
)
ENV_FILE = re.compile(r"\bGITHUB_(ENV|PATH|OUTPUT)\b")
PROMPT_KEY = re.compile(r"(?i)^(?:[\w-]*[_-])?prompts?(?:[_-][\w-]*)?$|^(?:custom|system|extra|additional)[_-]instructions$")
AGENT_TOKENS = {"ai", "genai", "llm", "llms", "agent", "agents", "agentic", "gpt", "copilot", "assistant", "inference"}
PROMPT_FLAG = re.compile(r"(?i)(?:^|\s)--(?:[a-z]+-)*prompt(?:-file)?(?:[=\s'\"]|$)")
DANGER_FLAG = re.compile(
    r"(?i)(?:^|[\s'\"=,\[])--?(?:yolo|dangerously[\w-]*|allow-all[\w-]*|skip-permissions[\w-]*|"
    r"bypass[\w-]*permissions[\w-]*|no-sandbox|full-auto)\b|\bdanger[\w-]*full[\w-]*access\b"
)
DANGER_KEY = re.compile(r"(?i)sandbox|safety|approval|permission[_-]?mode|permissions?$")
DANGER_VALUE = re.compile(r"(?i)^(?:unsafe|none|off|disabled?|false|bypass[\w-]*|danger[\w-]*|full[-_]?access|never|yolo)$")
WILDCARD_KEY = re.compile(r"(?i)allow[\w-]*(?:user|actor|bot|author|member|login)s?\b")
SHELL_TOOL = re.compile(r"(?i)\b(?:bash|shell|sh|zsh|run_shell_command|terminal|exec)\s*\(")
FETCH_HINT = re.compile(r"(?i)\bgh\s+(?:issue|pr)\s+(?:view|diff|list)\b|\bgh\s+api\b|\b(?:curl|wget)\s")
GATE_IF = re.compile(r"author_association|github\.(?:actor|triggering_actor)\b|\.user\.login\b|sender\.login\b|"
                     r"repository_owner\b|fromJSON\(|permission|collaborator|membership", re.I)
GATE_STEP = re.compile(r"getCollaboratorPermissionLevel|/collaborators/|author_association|\.permission\b|"
                       r"permission\s*[!=]=|checkMembership|/members/|team-membership|check-user-permission", re.I)
BOT_ACTOR = re.compile(r"github\.(?:actor|triggering_actor)\s*[!=]=\s*['\"][^'\"]*\[bot\]['\"]|"
                       r"['\"][^'\"]*\[bot\]['\"]\s*[!=]=\s*github\.(?:actor|triggering_actor)")

# Events an outsider can cause on a public repository, run with the base
# repository's secrets and a token that may be write-capable.
OUTSIDER_PRIVILEGED = {"pull_request_target", "issue_comment", "issues", "discussion", "discussion_comment",
                       "workflow_run", "fork", "watch", "gollum"}
# Events an outsider can cause where fork runs get no secrets and a read-only token.
OUTSIDER_UNPRIVILEGED = {"pull_request", "pull_request_review", "pull_request_review_comment"}
COMMENT_LIKE = {"issue_comment", "issues", "discussion", "discussion_comment", "pull_request_target"}
SAFE_INPUT_TYPES = {"boolean", "number", "choice", "environment"}


def untrusted_in(text: str, tainted_inputs: set[str] | None = None) -> bool:
    for expr in EXPRESSION.findall(text or ""):
        m = UNTRUSTED.search(expr)
        if m and ".base." not in m.group(0):
            return True
        if tainted_inputs:
            for name in INPUT_REF.findall(expr):
                if name in tainted_inputs:
                    return True
    return False


def trigger_map(doc: Node) -> dict[str, Node | None]:
    on = doc.get("on")
    if on is None:
        on = doc.get("true")
    if on is None:
        return {}
    if on.kind == "scalar":
        return {scalar(on): None} if scalar(on) else {}
    if on.kind == "seq":
        return {scalar(i): None for i in on.value if scalar(i)}
    return dict(on.value)


def permission_writes(node: Node | None) -> tuple[str, set[str]]:
    """Return (kind, scopes with write) where kind is unset, read-all, write-all or map."""
    if node is None:
        return "unset", set()
    if node.kind == "scalar":
        value = scalar(node).strip()
        if value == "write-all":
            return "write-all", {"*"}
        if value in ("read-all", "", "{}"):
            return "read-all" if value == "read-all" else "map", set()
        return "map", set()
    if node.kind == "map":
        return "map", {k for k, v in node.value.items() if scalar(v).strip() == "write"}
    return "map", set()


def env_names_with_untrusted(env: Node | None, tainted_inputs: set[str]) -> dict[str, int]:
    out = {}
    if env is not None and env.kind == "map":
        for name, value in env.value.items():
            if untrusted_in(all_text(value), tainted_inputs):
                out[name] = value.line if value is not None else env.line
    return out


def env_names_matching(env: Node | None, regex: re.Pattern) -> dict[str, int]:
    out = {}
    if env is not None and env.kind == "map":
        for name, value in env.value.items():
            if regex.search(all_text(value)):
                out[name] = value.line if value is not None else env.line
    return out


def var_used(name: str, text: str) -> bool:
    return re.search(r"\$\{?" + re.escape(name) + r"\b|\benv\." + re.escape(name) + r"\b", text or "") is not None


def step_label(step: Node, index: int) -> str:
    return scalar(step.get("name")) or scalar(step.get("id")) or f"step {index + 1}"


def is_checkout(step: Node) -> bool:
    return scalar(step.get("uses")).lower().startswith("actions/checkout@") or \
        scalar(step.get("uses")).lower() == "actions/checkout"


def checks_out_head(step: Node) -> bool:
    if is_checkout(step):
        with_ = step.get("with")
        return bool(HEAD_REF.search(all_text(with_.get("ref") if with_ else None) + "\n" +
                                    all_text(with_.get("repository") if with_ else None)))
    run = scalar(step.get("run"))
    return bool(run and HEAD_REF.search(run) and re.search(r"\b(?:checkout|fetch|switch|worktree)\b", run))


def agent_signals(step: Node, opts) -> tuple[list[str], list[str]]:
    """Return (signals, prompt input names) for a step that looks like an AI agent or model call."""
    signals, prompt_keys = [], []
    uses = scalar(step.get("uses"))
    with_ = step.get("with")
    if with_ is not None and with_.kind == "map":
        prompt_keys = sorted(k for k in with_.value if PROMPT_KEY.match(k))
        if prompt_keys:
            signals.append("prompt input")
    repo = uses.split("@", 1)[0]
    tokens = set(re.split(r"[/_.@-]+", repo.lower())) if repo and not repo.startswith("./") else set()
    if tokens & AGENT_TOKENS and not (tokens & {"agent", "agents"} and tokens & {"ssh", "gpg"}):
        signals.append("action name")
    if repo and opts.agent_uses and re.search(opts.agent_uses, repo):
        signals.append("--agent-uses")
    run = scalar(step.get("run"))
    if run and PROMPT_FLAG.search(run):
        signals.append("prompt flag in run")
    if run and opts.agent_run and re.search(opts.agent_run, run):
        signals.append("--agent-run")
    return signals, prompt_keys


class _FileContext:
    def __init__(self, rel: str, kind: str, triggers: set[str], tainted_inputs: set[str], input_types: dict[str, str]):
        self.rel = rel
        self.kind = kind                      # "workflow" or "composite"
        self.triggers = triggers
        self.tainted_inputs = tainted_inputs
        self.input_types = input_types
        self.privileged = triggers & OUTSIDER_PRIVILEGED
        self.unprivileged = triggers & OUTSIDER_UNPRIVILEGED


def _input_types(triggers: dict[str, Node | None], action_doc: Node | None = None) -> dict[str, str]:
    types: dict[str, str] = {}
    sources = []
    for event in ("workflow_dispatch", "workflow_call"):
        cfg = triggers.get(event)
        if cfg is not None and cfg.kind == "map" and cfg.get("inputs") is not None:
            sources.append(cfg.get("inputs"))
    if action_doc is not None and action_doc.get("inputs") is not None:
        sources.append(action_doc.get("inputs"))
    for inputs in sources:
        if inputs.kind != "map":
            continue
        for name, spec in inputs.value.items():
            types[name] = scalar(spec.get("type")).lower() if spec is not None and spec.kind == "map" else ""
    return types


def analyze_steps(ctx: _FileContext, job_id: str, job: Node, steps: list[Node], wf_env: Node | None,
                  perms: tuple[str, set[str]], opts, add, inventory: list, job_agent_outputs: dict) -> None:
    job_env = job.get("env") if job is not None else None
    tainted = ctx.tainted_inputs
    wf_tainted = env_names_with_untrusted(wf_env, tainted)
    job_tainted = env_names_with_untrusted(job_env, tainted)
    shared_secret_env = {**env_names_matching(wf_env, SECRET_REF), **env_names_matching(job_env, SECRET_REF)}
    outsider = ctx.privileged
    perm_kind, writes = perms
    head_checkout_line = None
    agent_ids: set[str] = set()
    agent_output_env: dict[str, int] = {}
    job_if = all_text(job.get("if")) if job is not None else ""
    step_ifs = " ".join(all_text(s.get("if")) for s in steps)
    gated = bool(GATE_IF.search(job_if + " " + step_ifs)) or any(
        GATE_STEP.search(scalar(s.get("uses")) + " " + scalar(s.get("run")) + " " +
                         all_text((s.get("with") or Node("map", {}, 0)).get("script"))) for s in steps)
    has_agent = False
    has_cache = False

    for index, step in enumerate(steps):
        if step is None or step.kind != "map":
            continue
        label = step_label(step, index)
        uses = scalar(step.get("uses"))
        with_ = step.get("with")
        step_env = step.get("env")
        run_node = step.get("run")
        script_node = with_.get("script") if with_ is not None else None
        step_tainted = {**wf_tainted, **job_tainted, **env_names_with_untrusted(step_env, tainted)}

        if checks_out_head(step) and head_checkout_line is None and (outsider & {"pull_request_target", "workflow_run", "issue_comment"}):
            head_checkout_line = step.line
        if uses.lower().startswith("actions/cache") or (with_ is not None and with_.get("cache") is not None and
                                                         uses.lower().startswith("actions/setup-")):
            has_cache = True

        # Environment files written with outsider text.
        for line, text in scalar_lines(run_node):
            m = ENV_FILE.search(text)
            if not m or (">>" not in text and "tee" not in text):
                continue
            target = m.group(1)
            direct = untrusted_in(text, tainted)
            via_var = sorted(n for n in step_tainted if var_used(n, text))
            if direct and target in ("ENV", "PATH"):
                add("EVENT_TEXT_TO_ENV_FILE", "HIGH", line, job_id, label,
                    f"Outsider text is written to GITHUB_{target}. A newline in it defines new variables (or PATH "
                    "entries) for every later step. Validate the value, or use a random heredoc delimiter.")
            elif via_var:
                add("EVENT_TEXT_TO_ENV_FILE", "HIGH" if target in ("ENV", "PATH") else "MEDIUM", line, job_id, label,
                    f"Variable(s) {', '.join(via_var)} hold outsider text and are written to GITHUB_{target}. Passing "
                    "the value through env: prevents script injection but not newline injection into this file; "
                    "use a random heredoc delimiter or validate the value.")
        if step_env is not None and step_env.kind == "map":
            for name, value in step_env.value.items():
                text = all_text(value)
                if any(sid in agent_ids for sid in STEP_OUTPUT.findall(text)) or any(
                        o in job_agent_outputs.get(j, set()) for j, o in NEEDS_OUTPUT.findall(text)):
                    agent_output_env[name] = value.line if value is not None else step.line
        # eval of outsider text or agent output held in variables.
        for line, text in scalar_lines(run_node):
            for name in sorted(set(step_tainted) | set(agent_output_env)):
                if re.search(r"(?:\beval\b|\b(?:ba|z|da)?sh\s+-c\b|\bpython3?\s+-c\b|\bnode\s+-e\b)[^\n]*\$\{?" +
                             re.escape(name) + r"\b", text):
                    kind = "agent output" if name in agent_output_env else "outsider text"
                    add("EVENT_TEXT_EVALUATED" if kind == "outsider text" else "AGENT_OUTPUT_TO_SHELL", "HIGH",
                        line, job_id, label,
                        f"Variable {name} holds {kind} and is evaluated as code. Treat it as data: validate it "
                        "against an allowlist instead of executing it.")
        # Inputs of reusable workflows and composite actions expanded into scripts.
        for line, text in list(scalar_lines(run_node)) + list(scalar_lines(script_node)):
            for expr in EXPRESSION.findall(text):
                for name in INPUT_REF.findall(expr):
                    if ctx.input_types.get(name, "") in SAFE_INPUT_TYPES:
                        continue
                    if name in tainted:
                        add("INPUT_EXPANDED_IN_SCRIPT", "HIGH", line, job_id, label,
                            f"Input '{name}' receives outsider text from a caller and is expanded into a script. "
                            "Pass it through env: and quote the variable.")
                    elif ctx.kind == "composite" or "workflow_call" in ctx.triggers:
                        add("INPUT_EXPANDED_IN_SCRIPT", "MEDIUM", line, job_id, label,
                            f"Input '{name}' is expanded into a script. Any caller that passes outsider text "
                            "makes this a script injection; pass it through env: and quote the variable.")
                    elif "workflow_dispatch" in ctx.triggers:
                        add("INPUT_EXPANDED_IN_SCRIPT", "LOW", line, job_id, label,
                            f"Dispatch input '{name}' is expanded into a script. Only users with write access can "
                            "dispatch, but a crafted value still runs as code; prefer env: and a quoted variable.")
        # Agent output expanded into later scripts.
        for line, text in list(scalar_lines(run_node)) + list(scalar_lines(script_node)):
            for expr in EXPRESSION.findall(text):
                hit = [sid for sid in STEP_OUTPUT.findall(expr) if sid in agent_ids]
                hit += [f"{j}.{o}" for j, o in NEEDS_OUTPUT.findall(expr) if o in job_agent_outputs.get(j, set())]
                if hit:
                    add("AGENT_OUTPUT_TO_SHELL", "HIGH", line, job_id, label,
                        f"Output of agent step {', '.join(sorted(set(hit)))} is expanded directly into a script. Model "
                        "output is attacker-influenced text: pass it through env:, quote it, and never execute it.")

        signals, prompt_keys = agent_signals(step, opts)
        if not signals:
            continue
        has_agent = True
        sid = scalar(step.get("id"))
        if sid:
            agent_ids.add(sid)
        prompt_text = "\n".join(all_text(with_.get(k)) for k in prompt_keys) if with_ is not None else ""
        if not prompt_keys:
            prompt_text = scalar(run_node)
        config_values = {}
        if with_ is not None and with_.kind == "map":
            config_values = {k: v for k, v in with_.value.items() if k not in prompt_keys}
        config_text = "\n".join(f"{k}={all_text(v)}" for k, v in config_values.items()) + "\n" + scalar(run_node)
        step_secrets = sorted(set(SECRET_REF.findall(all_text(with_) + "\n" + all_text(step_env))) - {"GITHUB_TOKEN"})
        inventory.append({
            "file": ctx.rel, "job": job_id, "step": label, "line": step.line, "uses": uses.split("@", 1)[0] or None,
            "detected_by": signals, "prompt_inputs": prompt_keys,
            "outsider_triggers": sorted(outsider | ctx.unprivileged),
            "token_write_scopes": sorted(writes) if perm_kind != "unset" else ["unknown (repository default)"],
            "secrets_referenced": len(set(step_secrets) | (set(SECRET_REF.findall(all_text(wf_env) + "\n" +
                                                                       all_text(job_env))) - {"GITHUB_TOKEN"})),
        })
        trig = ", ".join(sorted(outsider)) if outsider else ""
        if outsider:
            add("AGENT_ON_OUTSIDER_TRIGGER", "MEDIUM", step.line, job_id, label,
                f"An AI agent or model step runs on {trig}, which anyone who can open an issue, comment or pull "
                "request can cause. Assume text they wrote reaches the model; the impact is whatever the step's "
                "tools, token and secrets allow.")
        elif ctx.unprivileged:
            add("AGENT_ON_OUTSIDER_TRIGGER", "LOW", step.line, job_id, label,
                f"An AI agent or model step runs on {', '.join(sorted(ctx.unprivileged))}. Fork runs get no secrets "
                "and a read-only token, but same-repository branches do; outsider text can still reach the model.")
        if untrusted_in(prompt_text, tainted):
            add("AGENT_PROMPT_HAS_EVENT_TEXT", "HIGH" if outsider else "MEDIUM", step.line, job_id, label,
                "Outsider-written event text is expanded straight into the prompt. Anything it says competes with "
                "your instructions; keep privileged actions out of this step.")
        visible = sorted(step_tainted)
        if visible:
            referenced = [n for n in visible if re.search(r"\b" + re.escape(n) + r"\b", prompt_text)]
            add("AGENT_ENV_HAS_EVENT_TEXT", "HIGH" if (outsider and referenced) else "MEDIUM", step.line, job_id, label,
                f"Environment variable(s) {', '.join(visible)} carry outsider text into the agent step"
                + (f"; the prompt points the model at {', '.join(referenced)}" if referenced else "")
                + ". The env: indirection that stops script injection does not stop prompt injection.")
        if outsider and FETCH_HINT.search(prompt_text):
            add("AGENT_FETCHES_OUTSIDER_TEXT", "MEDIUM", step.line, job_id, label,
                "The prompt tells the agent to fetch issue, pull request or web content at run time, so text "
                "the YAML never shows reaches the model.")
        if head_checkout_line is not None:
            add("AGENT_AFTER_UNTRUSTED_CHECKOUT", "HIGH", step.line, job_id, label,
                f"The agent runs in a privileged workflow after contributor code was checked out (line "
                f"{head_checkout_line}). Agent instruction files, settings, hooks and tool definitions in that "
                "branch can steer or reconfigure the agent while secrets are available.")
        danger = bool(DANGER_FLAG.search(config_text)) or any(
            DANGER_KEY.search(k) and DANGER_VALUE.match(unquote(scalar(v)).strip()) for k, v in config_values.items())
        if danger:
            add("AGENT_UNSAFE_MODE", "HIGH" if outsider else "LOW", step.line, job_id, label,
                "A setting or flag turns off the agent's approval or sandbox controls. Combined with outsider "
                "text this lets injected instructions run any command with the job's token and secrets.")
        for key, value in config_values.items():
            if WILDCARD_KEY.search(key) and "*" in [p.strip().strip("'\"") for p in re.split(r"[,\s]+", all_text(value))]:
                add("AGENT_ANY_USER_ALLOWED", "MEDIUM" if (outsider or ctx.unprivileged) else "LOW", value.line,
                    job_id, label,
                    f"Input '{key}' allows every user. Anyone, not just collaborators, can make the agent act.")
        if SHELL_TOOL.search("\n".join(all_text(v) for v in config_values.values())) and (outsider or ctx.unprivileged):
            add("AGENT_SHELL_ALLOWLIST", "LOW", step.line, job_id, label,
                "A shell tool is allowed by command name. Name-based allowlists do not stop command substitution "
                "($(...), backticks) or chained commands inside an allowed command's arguments.")
        if outsider and (perm_kind == "unset" or writes):
            scopes = "the repository default token permissions" if perm_kind == "unset" else \
                "write access to " + ", ".join(sorted(writes))
            add("AGENT_WITH_WRITE_TOKEN", "MEDIUM", step.line, job_id, label,
                f"The agent's job runs with {scopes} on an outsider-triggered event. Grant read-only scopes and "
                "move writes into a separate job that treats the agent's output as data.")
        if outsider and (shared_secret_env or len(step_secrets) > 1):
            names = sorted(set(shared_secret_env) | ({"(step inputs)"} if len(step_secrets) > 1 else set()))
            add("AGENT_SHARES_SECRETS", "MEDIUM", step.line, job_id, label,
                f"Secrets beyond the model credential are visible to the agent step ({', '.join(names)}). "
                "An injected agent can read environment variables; scope each secret to the step that needs it.")
        if outsider & COMMENT_LIKE and not gated:
            add("AGENT_NO_ACTOR_GATE", "MEDIUM", step.line, job_id, label,
                "No condition checks who triggered the event (author association, permission or login). The "
                "action may check this itself; confirm in its documentation for the pinned version.")

    # Token persisted by checkout in jobs where an agent runs or the workspace is uploaded.
    uploads_workspace = any(
        "upload-artifact" in scalar(s.get("uses")).lower() and s.get("with") is not None and
        re.search(r"(?m)^\s*(?:\.|\./|\.git\b.*|\$\{\{\s*github\.workspace\s*\}\}/?|\*\*?)\s*$",
                  all_text(s.get("with").get("path")))
        for s in steps if s is not None and s.kind == "map")
    for index, step in enumerate(steps):
        if step is None or step.kind != "map" or not is_checkout(step):
            continue
        with_ = step.get("with")
        persist = scalar(with_.get("persist-credentials")).strip().lower() if with_ is not None else ""
        if persist == "false":
            continue
        if has_agent:
            add("CHECKOUT_TOKEN_PERSISTED", "MEDIUM", step.line, job_id, step_label(step, index),
                "Checkout keeps the job token in the repository's Git configuration, where an agent's file or "
                "shell tools can read it. Set persist-credentials: false.")
        elif uploads_workspace:
            add("CHECKOUT_TOKEN_PERSISTED", "MEDIUM", step.line, job_id, step_label(step, index),
                "Checkout keeps the job token in .git/config and a later step uploads the workspace as an "
                "artifact. Set persist-credentials: false and upload only build outputs.")
    if head_checkout_line is not None and has_cache:
        add("CACHE_AFTER_UNTRUSTED_CHECKOUT", "MEDIUM", head_checkout_line, job_id, None,
            "A privileged job checks out contributor code and also uses a cache. Code from the pull request can "
            "write cache entries that trusted workflows on the base branch later restore.")
    if not has_agent and ctx.privileged & COMMENT_LIKE and not gated and steps and \
            any(s is not None and s.kind == "map" and s.get("run") is not None for s in steps) and \
            (perm_kind == "unset" or writes) and (shared_secret_env or SECRET_REF.search(all_text(job))):
        add("PRIVILEGED_JOB_NO_ACTOR_GATE", "LOW", job.line if job is not None else 0, job_id, None,
            "A job with secrets and a write-capable token runs on an outsider-triggered event without checking "
            "who triggered it. Confirm that nothing in it acts on the event's text or runs contributor code.")


def agent_job_outputs(jobs: Node, opts) -> dict[str, set[str]]:
    """Job outputs that carry an agent step's output, so other jobs' use of needs.<job>.outputs can be traced."""
    found: dict[str, set[str]] = {}
    for job_id, job in jobs.items():
        if job is None or job.kind != "map" or job.get("outputs") is None or job.get("outputs").kind != "map":
            continue
        ids = {scalar(s.get("id")) for s in (job.get("steps") or Node("seq", [], 0)).seq()
               if s.kind == "map" and scalar(s.get("id")) and agent_signals(s, opts)[0]}
        names = {k for k, v in job.get("outputs").value.items() if any(i in ids for i in STEP_OUTPUT.findall(all_text(v)))}
        if names:
            found[job_id] = names
    return found


def check_actions_file(rel: str, text: str, kind: str, opts, tainted_inputs: set[str],
                       inherited_triggers: set[str]) -> tuple[list[dict], list[dict], dict]:
    doc = parse_yaml(text)
    candidates: list[dict] = []
    inventory: list[dict] = []

    def add(rule, severity, line, job, step, note):
        candidates.append({"rule": rule, "severity": severity, "file": rel, "line": line or None,
                           "job": job, "step": step, "note": note})

    if doc.kind != "map":
        return candidates, inventory, {"file": rel, "kind": kind, "parse_error": "top level is not a mapping"}
    if kind == "composite":
        runs = doc.get("runs")
        using = scalar(runs.get("using")) if runs is not None else ""
        ctx = _FileContext(rel, kind, set(inherited_triggers), tainted_inputs, _input_types({}, doc))
        summary = {"file": rel, "kind": kind, "using": using or None,
                   "inherited_triggers": sorted(inherited_triggers), "parse_error": None}
        if using != "composite" or runs.get("steps") is None:
            return candidates, inventory, summary
        analyze_steps(ctx, "(composite)", None, runs.get("steps").seq(), None, ("unset", set()), opts, add,
                      inventory, {})
        summary["agent_steps"] = len(inventory)
        return candidates, inventory, summary

    triggers = trigger_map(doc)
    names = set(triggers) | set(inherited_triggers)
    ctx = _FileContext(rel, kind, names, tainted_inputs, _input_types(triggers))
    wf_perm = doc.get("permissions")
    wf_env = doc.get("env")
    jobs = doc.get("jobs")
    summary = {"file": rel, "kind": kind, "triggers": sorted(triggers), "inherited_triggers": sorted(inherited_triggers),
               "outsider_triggers": sorted(names & (OUTSIDER_PRIVILEGED | OUTSIDER_UNPRIVILEGED)),
               "permissions": permission_writes(wf_perm)[0], "parse_error": None}
    if jobs is None or jobs.kind != "map":
        summary["parse_error"] = "no jobs mapping found" if not triggers else None
        return candidates, inventory, summary

    if ctx.privileged:
        _, writes = permission_writes(wf_perm)
        if "id-token" in writes or "*" in writes:
            add("ID_TOKEN_ON_OUTSIDER_TRIGGER", "MEDIUM", wf_perm.line if wf_perm else None, None, None,
                "The workflow can mint cloud identity tokens (id-token: write) on an outsider-triggered event. "
                "Restrict the cloud trust policy's subject and keep untrusted code out of this workflow.")
    job_agent_outputs = agent_job_outputs(jobs, opts)
    for job_id, job in jobs.items():
        if job is None or job.kind != "map":
            continue
        perms = permission_writes(job.get("permissions")) if job.get("permissions") is not None else permission_writes(wf_perm)
        if ctx.privileged and job.get("permissions") is not None and ("id-token" in perms[1] or "*" in perms[1]):
            add("ID_TOKEN_ON_OUTSIDER_TRIGGER", "MEDIUM", job.get("permissions").line, job_id, None,
                "This job can mint cloud identity tokens (id-token: write) on an outsider-triggered event.")
        secrets = job.get("secrets")
        if secrets is not None and scalar(secrets).strip() == "inherit":
            target = scalar(job.get("uses"))
            remote = bool(target) and not target.startswith("./")
            add("SECRETS_INHERIT", "MEDIUM" if remote else "LOW", secrets.line, job_id, None,
                "secrets: inherit passes every repository and organization secret to the called workflow"
                + (", which lives in another repository" if remote else "") + ". Pass only the secrets it needs.")
        for if_node, step_name in [(job.get("if"), None)] + [
                (s.get("if"), step_label(s, i)) for i, s in enumerate((job.get("steps") or Node("seq", [], 0)).seq())
                if s is not None and s.kind == "map"]:
            if if_node is None or if_node.kind != "scalar":
                continue
            value = scalar(if_node)
            stripped = value.strip()
            if "${{" in value and (
                    (if_node.style and not if_node.style.endswith("-")) or
                    not (stripped.startswith("${{") and stripped.endswith("}}") and stripped.count("${{") == 1)):
                add("ALWAYS_TRUE_IF", "MEDIUM", if_node.line, job_id, step_name,
                    "This if: mixes ${{ }} with other text (or keeps a trailing newline from a block scalar), so it "
                    "evaluates to a non-empty string, which is always true. Write the whole condition as one "
                    "expression.")
            if BOT_ACTOR.search(value) and names & {"pull_request_target", "workflow_run", "pull_request"}:
                add("SPOOFABLE_BOT_CHECK", "MEDIUM", if_node.line, job_id, step_name,
                    "github.actor names whoever caused the latest event, which a contributor can arrange to be a "
                    "bot. Check the pull request author (github.event.pull_request.user.login) instead.")
        steps = (job.get("steps") or Node("seq", [], 0)).seq()
        if "workflow_run" in names:
            for i, s in enumerate(steps):
                if s is None or s.kind != "map":
                    continue
                if "download-artifact" in scalar(s.get("uses")).lower() or re.search(r"\bgh\s+run\s+download\b",
                                                                                      scalar(s.get("run"))):
                    add("ARTIFACT_FROM_TRIGGERING_RUN", "MEDIUM", s.line, job_id, step_label(s, i),
                        "A workflow_run job downloads artifacts from the run that triggered it, which may have run "
                        "pull-request code. Extract them outside the workspace, treat them as data and never "
                        "execute or source them.")
        analyze_steps(ctx, job_id, job, steps, wf_env, perms, opts, add, inventory, job_agent_outputs)
    summary["agent_steps"] = len(inventory)
    return candidates, inventory, summary


def _local_targets(root: Path, rel: str, doc: Node) -> tuple[list[tuple[str, set[str]]], list[tuple[str, set[str]]]]:
    """Return local reusable-workflow and composite-action calls with input names that receive outsider text."""
    workflows, actions = [], []
    jobs = doc.get("jobs") if doc.kind == "map" else None
    if jobs is None or jobs.kind != "map":
        return workflows, actions
    for _, job in jobs.items():
        if job is None or job.kind != "map":
            continue
        target = scalar(job.get("uses"))
        if target.startswith("./"):
            with_ = job.get("with")
            names = {k for k, v in (with_.items() if with_ is not None else []) if untrusted_in(all_text(v))}
            workflows.append((target[2:].split("@", 1)[0], names))
        for step in (job.get("steps") or Node("seq", [], 0)).seq():
            if step is None or step.kind != "map":
                continue
            target = scalar(step.get("uses"))
            if target.startswith("./"):
                with_ = step.get("with")
                names = {k for k, v in (with_.items() if with_ is not None else []) if untrusted_in(all_text(v))}
                base = target[2:].rstrip("/")
                for fname in ("action.yml", "action.yaml"):
                    if (root / base / fname).is_file():
                        actions.append((f"{base}/{fname}".lstrip("/"), names))
                        break
    return workflows, actions


def check_actions(root: Path, opts) -> dict:
    files: dict[str, tuple[str, str]] = {}
    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir():
        for path in sorted(wf_dir.iterdir()):
            if path.suffix in (".yml", ".yaml") and path.is_file() and not path.is_symlink():
                text = read_text(path, MAX_YAML_BYTES)
                if text is not None:
                    files[path.relative_to(root).as_posix()] = ("workflow", text)
    for path, rel in iter_files(root):
        if path.name in ("action.yml", "action.yaml"):
            text = read_text(path, MAX_YAML_BYTES)
            if text is not None:
                files[rel] = ("composite", text)

    tainted: dict[str, set[str]] = {rel: set() for rel in files}
    inherited: dict[str, set[str]] = {rel: set() for rel in files}
    parse_errors = []
    for rel, (kind, text) in sorted(files.items()):
        if kind != "workflow":
            continue
        try:
            doc = parse_yaml(text)
        except RecursionError:
            parse_errors.append(rel)
            continue
        triggers = set(trigger_map(doc)) if doc.kind == "map" else set()
        calls = _local_targets(root, rel, doc)
        for target, names in calls[0] + calls[1]:
            if target in files:
                tainted[target] |= names
                inherited[target] |= triggers & (OUTSIDER_PRIVILEGED | OUTSIDER_UNPRIVILEGED)
    # One more round so composite actions called from reusable workflows inherit the callers' events.
    for rel, (kind, text) in sorted(files.items()):
        if kind == "workflow" and inherited[rel]:
            for target, names in _local_targets(root, rel, parse_yaml(text))[1]:
                if target in files:
                    inherited[target] |= inherited[rel]

    candidates, inventory, summaries = [], [], []
    for rel, (kind, text) in sorted(files.items()):
        if rel in parse_errors:
            summaries.append({"file": rel, "kind": kind, "parse_error": "nesting too deep"})
            continue
        c, inv, summary = check_actions_file(rel, text, kind, opts, tainted[rel], inherited[rel])
        if kind == "composite" and summary.get("using") != "composite":
            continue
        candidates.extend(c)
        inventory.extend(inv)
        summaries.append(summary)
    seen, unique = set(), []
    for c in sorted(candidates, key=severity_key):
        key = (c["rule"], c["file"], c["line"], c["job"], c["step"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return {
        "tool": "productcraft-supply-chain-actions",
        "version": VERSION,
        "root": str(root),
        "result_type": "candidates-not-findings",
        "warnings": [
            "Structural reading of GitHub Actions YAML with a small built-in parser. Anything it could not parse "
            "is skipped, so read each workflow yourself before calling it clean.",
            "Agent steps are recognized by prompt-like inputs, prompt flags and generic action names. Add your "
            "agent's action or command with --agent-uses / --agent-run if it is not listed in agent_steps.",
            "Repository and organization settings (default token permissions, fork pull request approval, "
            "environment protection, which users the agent action accepts by default) are NOT_VERIFIED.",
            "Run code_audit.py workflows as well: it covers direct script injection, unpinned actions, missing "
            "permissions blocks and untrusted checkouts, which this command does not repeat.",
        ],
        "stats": {"workflow_files": sum(1 for k, _ in files.values() if k == "workflow"),
                  "composite_actions": sum(1 for s in summaries if s.get("kind") == "composite"),
                  "agent_steps": len(inventory), "candidate_count": len(unique),
                  "by_severity": by_severity(unique)},
        "files": summaries,
        "agent_steps": inventory,
        "candidates": unique[:MAX_RESULTS],
        "truncated": len(unique) > MAX_RESULTS,
    }


# --------------------------------------------------------------------------
# lockfiles
# --------------------------------------------------------------------------

PUBLIC_HOSTS = {
    "npm": {"registry.npmjs.org": "npm", "registry.yarnpkg.com": "npm"},
    "python": {"pypi.org": "pypi", "files.pythonhosted.org": "pypi"},
    "cargo": {"github.com": "crates.io", "index.crates.io": "crates.io", "static.crates.io": "crates.io"},
    "ruby": {"rubygems.org": "rubygems", "index.rubygems.org": "rubygems"},
    "php": {"api.github.com": "vcs-host", "codeload.github.com": "vcs-host", "github.com": "vcs-host",
            "gitlab.com": "vcs-host", "bitbucket.org": "vcs-host", "repo.packagist.org": "packagist",
            "packagist.org": "packagist"},
}
GIT_URL = re.compile(r"^(?:git\+|git:|github:|gitlab:|bitbucket:|ssh://git@)|\.git(?:#|$)|#commit=", re.I)
FULL_SHA = re.compile(r"(?:#|commit=|rev=|[?&]rev=)([0-9a-f]{40})\b")
CRED_IN_URL = re.compile(r"://(?:[^/@\s:]+:[^/@\s]+|[^/@\s:]{20,})@([^/:@\s?#]+)")


def safe_label(label: str | None) -> str | None:
    """Package labels can embed a resolution URL; keep the name and drop anything URL-like."""
    if label is None:
        return None
    label = re.sub(r"(?i)@?(?:[a-z][a-z0-9+.-]*:)?//\S*", "@<url>", str(label))
    return label[:160]


class _LockReport:
    def __init__(self, rel: str, ecosystem: str, expected_hosts: set[str]):
        self.rel = rel
        self.ecosystem = ecosystem
        self.expected = expected_hosts
        self.packages = 0
        self.install_code: list[str] | None = []
        self.install_note = None
        self.from_source: list[str] = []
        self.registries: Counter = Counter()
        self.missing_integrity: list[str] = []
        self.other_hosts: Counter = Counter()
        self.candidates: list[dict] = []

    def add(self, rule, severity, line, package, note):
        self.candidates.append({"rule": rule, "severity": severity, "file": self.rel, "line": line,
                                "package": safe_label(package), "note": note})

    def url(self, url: str, package: str, line=None, registry=True) -> None:
        """Check one resolved URL. Never records the URL itself, only its host."""
        if not url:
            return
        url = url.strip().strip("'\"")
        cred = CRED_IN_URL.search(url)
        if cred:
            self.add("CREDENTIAL_IN_URL", "HIGH", line, package,
                     f"A resolved URL for host {cred.group(1).lower()} embeds credentials. Remove them from the "
                     "lockfile, rotate them, and configure registry authentication outside the repository.")
        if GIT_URL.search(url):
            pinned = bool(FULL_SHA.search(url))
            self.add("NON_REGISTRY_SOURCE", "LOW" if pinned else "MEDIUM", line, package,
                     "Resolved from a Git repository" + (" at a full commit SHA" if pinned else
                                                         " without a full commit SHA, so the code can change")
                     + "; the registry's integrity checks and advisories do not cover it.")
            return
        if url.startswith(("file:", "link:", "portal:", "workspace:", "./", "../", "/")):
            return
        try:
            parts = urlsplit(url)
        except ValueError:
            return
        host = (parts.hostname or "").lower()
        if parts.scheme == "http" and host not in ("localhost", "127.0.0.1"):
            self.add("INSECURE_TRANSPORT", "HIGH", line, package,
                     f"Downloaded over plain HTTP from {host}; anyone on the network path can swap the package.")
        if not registry or not host:
            return
        known = PUBLIC_HOSTS.get(self.ecosystem, {})
        group = known.get(host) or ("expected:" + host if host in self.expected else host)
        self.registries[group] += 1
        if host not in known and host not in self.expected:
            self.other_hosts[host] += 1

    def finish(self) -> dict:
        for host, count in sorted(self.other_hosts.items()):
            self.add("OTHER_REGISTRY", "LOW", None, None,
                     f"{count} package(s) resolve from {host}, which is not the public registry for this ecosystem. "
                     "If it is your internal registry, pass --registry " + host + ".")
        if len(self.registries) > 1:
            self.add("MIXED_REGISTRIES", "LOW", None, None,
                     "Packages resolve from more than one registry (" + ", ".join(sorted(self.registries)) + "). "
                     "Check that every internal package name is scoped or reserved on the public registry and that "
                     "each scope maps to exactly one registry (dependency confusion).")
        if self.missing_integrity:
            self.add("MISSING_INTEGRITY", "LOW", None, None,
                     f"{len(self.missing_integrity)} package(s) have no integrity hash recorded, so a changed "
                     "download would not be detected. Regenerate the lockfile with a current package manager.")
        if self.install_code:
            self.add("INSTALL_TIME_CODE", "INFO", None, None,
                     f"{len(self.install_code)} package(s) run code during install. Review them, and install with "
                     "scripts disabled where the build allows it.")
        if self.from_source:
            self.add("BUILDS_FROM_SOURCE", "INFO", None, None,
                     f"{len(self.from_source)} package(s) have only a source distribution, so installing runs "
                     "their build backend.")
        return {
            "path": self.rel, "ecosystem": self.ecosystem, "packages": self.packages,
            "install_time_code": ({"recorded": False, "note": self.install_note} if self.install_code is None else
                                  {"recorded": True, "count": len(self.install_code),
                                   "packages": [safe_label(p) for p in self.install_code[:MAX_LISTED]]}),
            "builds_from_source": [safe_label(p) for p in self.from_source[:MAX_LISTED]],
            "registries": dict(sorted(self.registries.items())),
            "missing_integrity": {"count": len(self.missing_integrity),
                                  "packages": [safe_label(p) for p in self.missing_integrity[:MAX_LISTED]]},
        }


def _npm(rep: _LockReport, text: str) -> None:
    data = json.loads(text)
    pkgs = data.get("packages")
    if isinstance(pkgs, dict) and len(pkgs) > 1:
        for key, meta in sorted(pkgs.items()):
            if not key or not isinstance(meta, dict) or meta.get("link"):
                continue
            rep.packages += 1
            name = meta.get("name") or key.rsplit("node_modules/", 1)[-1]
            label = f"{name}@{meta.get('version', '?')}"
            if meta.get("hasInstallScript"):
                rep.install_code.append(label + (" (dev)" if meta.get("dev") else ""))
            resolved = meta.get("resolved") or ""
            if not resolved and str(meta.get("version", "")).startswith(("git", "http", "github:")):
                resolved = str(meta.get("version"))
            rep.url(resolved, label)
            if resolved and not GIT_URL.search(resolved) and not resolved.startswith("file:") and not meta.get("integrity"):
                rep.missing_integrity.append(label)
        return
    rep.install_code = None
    rep.install_note = "lockfileVersion 1 does not record install scripts"

    def walk(deps: dict, prefix=""):
        for name, meta in sorted((deps or {}).items()):
            if not isinstance(meta, dict):
                continue
            rep.packages += 1
            label = f"{name}@{meta.get('version', '?')}"
            resolved = meta.get("resolved") or ""
            version = str(meta.get("version", ""))
            if not resolved and version.startswith(("git", "http", "github:")):
                resolved = version
            rep.url(resolved, label)
            if resolved and not GIT_URL.search(resolved) and not resolved.startswith("file:") and not meta.get("integrity"):
                rep.missing_integrity.append(label)
            walk(meta.get("dependencies"))
    walk(data.get("dependencies"))


def _yarn(rep: _LockReport, text: str) -> None:
    berry = "__metadata:" in text
    rep.install_code = None
    rep.install_note = "yarn.lock does not record which packages run install scripts"
    entry, fields, start = None, {}, 0

    def flush():
        if entry is None or entry.startswith("__metadata"):
            return
        rep.packages += 1
        label = entry.split(",")[0].strip().strip('"')
        if berry:
            resolution = fields.get("resolution", "").strip('"')
            m = re.match(r"^(@?[^@]+)@([a-z+]+):(.*)$", resolution)
            protocol = m.group(2) if m else ""
            if protocol in ("workspace", "link", "portal", "file", "patch", "exec"):
                return
            if protocol == "npm":
                if "checksum" not in fields:
                    rep.missing_integrity.append(resolution or label)
                rep.registries["npm (registry from .yarnrc.yml)"] += 1
                return
            rep.url(resolution.split("@", 1)[-1] if m is None else m.group(2) + ":" + m.group(3), label, start)
        else:
            resolved = fields.get("resolved", "").strip('"')
            rep.url(resolved.split("#", 1)[0] if not GIT_URL.search(resolved) else resolved, label, start)
            if resolved and not GIT_URL.search(resolved) and "integrity" not in fields:
                rep.missing_integrity.append(label)

    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            flush()
            entry, fields, start = line.rstrip(":").strip(), {}, n
            continue
        m = re.match(r"^  ([\w-]+):?\s+(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    flush()


def _pnpm(rep: _LockReport, text: str) -> None:
    in_packages, current, start = False, None, 0
    v9 = re.search(r"(?m)^lockfileVersion:\s*'?9", text) is not None
    if v9:
        rep.install_note = "lockfile v9 does not record which packages run install scripts"
    for n, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^\S", line):
            in_packages = line.startswith("packages:")
            current = None
            continue
        if not in_packages:
            continue
        m = re.match(r"^  (['\"]?)(/?[^\s'\"]+?)\1:\s*$", line)
        if m:
            current, start = m.group(2), n
            rep.packages += 1
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("resolution:"):
            body = stripped[len("resolution:"):]
            if "tarball:" in body:
                rep.url(re.search(r"tarball:\s*['\"]?([^,'\"}\s]+)", body).group(1), current, n)
            elif "repo:" in body or "type: git" in body:
                commit = re.search(r"commit:\s*['\"]?([0-9a-f]{40})", body)
                rep.url("git+repo" + ("#" + commit.group(1) if commit else ""), current, n)
            elif "directory:" in body:
                pass
            elif "integrity:" not in body:
                rep.missing_integrity.append(current)
        elif stripped == "requiresBuild: true" and rep.install_code is not None:
            rep.install_code.append(current)
    if v9:
        rep.install_code = None


def _toml(text: str):
    if tomllib is None:
        raise ValueError("TOML lockfiles need Python 3.11 or later (tomllib)")
    return tomllib.loads(text)


def _uv(rep: _LockReport, text: str) -> None:
    data = _toml(text)
    rep.install_code = None
    rep.install_note = "Python lockfiles do not record install scripts; see builds_from_source"
    for pkg in data.get("package", []):
        rep.packages += 1
        label = f"{pkg.get('name')}@{pkg.get('version', '?')}"
        source = pkg.get("source") or {}
        if "registry" in source:
            rep.url(source["registry"], label, registry=True)
        elif "git" in source:
            rep.url("git+" + source["git"], label)
        elif "url" in source:
            rep.url(source["url"], label, registry=False)
            rep.add("NON_REGISTRY_SOURCE", "MEDIUM", None, label, "Installed from a direct URL, not an index.")
        elif "path" in source or "directory" in source or "editable" in source:
            target = str(source.get("path") or source.get("directory") or source.get("editable"))
            if target.startswith(".."):
                rep.add("LOCAL_PATH_OUTSIDE_REPO", "LOW", None, label,
                        "Built from a directory outside this repository, which this review cannot see.")
            continue
        else:
            continue
        sdist, wheels = pkg.get("sdist"), pkg.get("wheels") or []
        for artifact in ([sdist] if sdist else []) + wheels:
            rep.url(artifact.get("url", ""), label, registry=False)
            if "url" in artifact and not artifact.get("hash"):
                rep.missing_integrity.append(label)
                break
        if sdist and not wheels and "registry" in source:
            rep.from_source.append(label)


def _poetry(rep: _LockReport, text: str) -> None:
    data = _toml(text)
    rep.install_code = None
    rep.install_note = "Python lockfiles do not record install scripts; see builds_from_source"
    legacy_files = (data.get("metadata") or {}).get("files") or {}
    for pkg in data.get("package", []):
        rep.packages += 1
        name = pkg.get("name")
        label = f"{name}@{pkg.get('version', '?')}"
        source = pkg.get("source") or {}
        stype = source.get("type")
        if stype == "git":
            rep.url("git+" + str(source.get("url", "")) + "#" + str(source.get("resolved_reference", "")), label)
            continue
        if stype in ("directory", "file"):
            continue
        if stype == "url":
            rep.url(str(source.get("url", "")), label, registry=False)
            rep.add("NON_REGISTRY_SOURCE", "MEDIUM", None, label, "Installed from a direct URL, not an index.")
            continue
        if stype == "legacy":
            rep.url(str(source.get("url", "")), label)
        else:
            rep.registries["pypi"] += 1
        files = pkg.get("files")
        if files is None:
            files = legacy_files.get(name, [])
        if not files or any(not f.get("hash") for f in files):
            rep.missing_integrity.append(label)
        names = [str(f.get("file", "")) for f in files]
        if names and not any(n.endswith(".whl") for n in names):
            rep.from_source.append(label)


def _pipenv(rep: _LockReport, text: str) -> None:
    data = json.loads(text)
    rep.install_code = None
    rep.install_note = "Python lockfiles do not record install scripts"
    for src in (data.get("_meta") or {}).get("sources", []):
        rep.url(str(src.get("url", "")), f"index {src.get('name', '?')}")
        if src.get("verify_ssl") is False:
            rep.add("INSECURE_TRANSPORT", "HIGH", None, f"index {src.get('name', '?')}",
                    "TLS verification is disabled for this package index.")
    for section in ("default", "develop"):
        for name, meta in sorted((data.get(section) or {}).items()):
            if not isinstance(meta, dict):
                continue
            rep.packages += 1
            label = f"{name}{meta.get('version', '')}"
            if "git" in meta:
                rep.url("git+" + str(meta["git"]) + "#" + str(meta.get("ref", "")), label)
            elif "file" in meta:
                rep.url(str(meta["file"]), label, registry=False)
            elif "path" in meta or meta.get("editable"):
                continue
            elif not meta.get("hashes"):
                rep.missing_integrity.append(label)


def _cargo(rep: _LockReport, text: str) -> None:
    data = _toml(text)
    rep.install_code = None
    rep.install_note = "Cargo.lock does not record build scripts or procedural macros"
    meta_checksums = {k for k in (data.get("metadata") or {}) if str(k).startswith("checksum ")}
    for pkg in data.get("package", []):
        source = pkg.get("source")
        if not source:
            continue
        rep.packages += 1
        label = f"{pkg.get('name')}@{pkg.get('version', '?')}"
        if source.startswith("git+"):
            rep.url(source, label)
            continue
        url = source.split("+", 1)[-1]
        rep.url(url, label)
        if not pkg.get("checksum") and not any(label.replace("@", " ") in k for k in meta_checksums):
            rep.missing_integrity.append(label)


def _gomod(rep: _LockReport, text: str) -> None:
    rep.install_code = None
    rep.install_note = "Go modules do not run code at download; cgo and go generate run only when invoked"
    block = None
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^(require|replace|exclude|retract)\s*\($", line)
        if m:
            block = m.group(1)
            continue
        if block and line == ")":
            block = None
            continue
        if block:
            kind, body = block, line
        else:
            m = re.match(r"^(require|replace)\s+(.*)$", line)
            if not m:
                continue
            kind, body = m.group(1), m.group(2)
        if kind == "require" and re.match(r"^\S+\s+v\S+", body):
            rep.packages += 1
        elif kind == "replace" and "=>" in body:
            left, right = [p.strip() for p in body.split("=>", 1)]
            module = left.split()[0] if left else ""
            target = right.split()[0] if right else ""
            if target.startswith(("./", "../", "/")):
                rep.add("LOCAL_REPLACE", "LOW", n, module,
                        "Replaced with a local directory; go.sum does not cover it and the build uses whatever "
                        "is there.")
            elif target and target != module:
                rep.add("FORK_REPLACE", "LOW", n, module,
                        f"Replaced with a different module path ({target}). Confirm the fork is intended and "
                        "maintained.")


def _bundler(rep: _LockReport, text: str) -> None:
    rep.install_code = None
    rep.install_note = "Gemfile.lock does not record which gems build native extensions"
    sections: list[tuple[str, int, dict]] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^[A-Z][A-Z ]*$", line):
            sections.append((line.strip(), n, {"remotes": [], "revision": ""}))
            continue
        if not sections:
            continue
        name, _, info = sections[-1]
        m = re.match(r"^  remote:\s*(\S+)", line)
        if m:
            info["remotes"].append((n, m.group(1)))
        elif line.startswith("  revision:"):
            info["revision"] = line.split(":", 1)[1].strip()
        elif name in ("GEM", "GIT", "PATH") and re.match(r"^    \S+ \(", line):
            rep.packages += 1
    for name, _, info in sections:
        for n, remote in info["remotes"]:
            if name == "GEM":
                rep.url(remote, "GEM remote", n)
            elif name == "GIT":
                rep.url("git+" + remote + ("#" + info["revision"] if info["revision"] else ""), "GIT source", n)


def _composer(rep: _LockReport, text: str) -> None:
    data = json.loads(text)
    for section in ("packages", "packages-dev"):
        for pkg in data.get(section) or []:
            rep.packages += 1
            label = f"{pkg.get('name')}@{pkg.get('version', '?')}"
            if pkg.get("type") == "composer-plugin":
                rep.install_code.append(label + (" (dev)" if section == "packages-dev" else ""))
            dist = pkg.get("dist") or {}
            source = pkg.get("source") or {}
            if dist.get("type") == "path":
                continue
            if dist.get("url"):
                rep.url(str(dist["url"]), label)
            elif source.get("type") == "git":
                rep.url("git+" + str(source.get("url", "")) + "#" + str(source.get("reference", "")), label)


LOCK_PARSERS = {
    "package-lock.json": ("npm", _npm), "npm-shrinkwrap.json": ("npm", _npm), "yarn.lock": ("npm", _yarn),
    "pnpm-lock.yaml": ("npm", _pnpm), "uv.lock": ("python", _uv), "poetry.lock": ("python", _poetry),
    "Pipfile.lock": ("python", _pipenv), "Cargo.lock": ("cargo", _cargo), "go.mod": ("go", _gomod),
    "Gemfile.lock": ("ruby", _bundler), "composer.lock": ("php", _composer),
}


def configured_hosts(root: Path) -> set[str]:
    """Registry hosts declared in .npmrc and .yarnrc.yml files (never their tokens)."""
    hosts = set()
    for path, rel in iter_files(root):
        if path.name not in (".npmrc", ".yarnrc.yml", ".yarnrc"):
            continue
        text = read_text(path, 200_000) or ""
        for m in re.finditer(r"(?m)^\s*(?:@[\w.-]+:)?registry\s*=\s*(\S+)|(?:npmRegistryServer|registry)\s*:?\s*[\"']?(https?://[^\s\"']+)", text):
            url = m.group(1) or m.group(2)
            try:
                host = (urlsplit(url.strip("\"'")).hostname or "").lower()
            except ValueError:
                host = ""
            if host:
                hosts.add(host)
    return hosts


def check_lockfiles(root: Path, extra_hosts: list[str]) -> dict:
    expected = {h.lower() for h in extra_hosts} | configured_hosts(root)
    reports, errors = [], []
    for path, rel in iter_files(root):
        spec = LOCK_PARSERS.get(path.name)
        if not spec:
            continue
        text = read_text(path, MAX_LOCK_BYTES)
        if text is None:
            errors.append({"path": rel, "error": "too large or binary"})
            continue
        rep = _LockReport(rel, spec[0], expected)
        try:
            spec[1](rep, text)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append({"path": rel, "error": f"could not parse: {type(exc).__name__}"})
            continue
        reports.append((rep.finish(), rep.candidates))
    candidates = sorted((c for _, cs in reports for c in cs), key=severity_key)
    return {
        "tool": "productcraft-supply-chain-lockfiles",
        "version": VERSION,
        "root": str(root),
        "result_type": "candidates-not-findings",
        "warnings": [
            "Offline reading of lockfiles only. Advisories, maintainers, deprecation and package age need the "
            "registry or an audit tool (see the supply-chain reference); this command does not contact them.",
            "Install-time code is listed only where the lockfile format records it.",
            "Registry hosts from .npmrc and .yarnrc.yml are treated as expected; tokens in them are never read out.",
        ],
        "stats": {"lockfiles": len(reports), "packages": sum(r["packages"] for r, _ in reports),
                  "candidate_count": len(candidates), "by_severity": by_severity(candidates),
                  "unreadable": len(errors)},
        "lockfiles": [r for r, _ in reports],
        "errors": errors,
        "candidates": candidates[:MAX_RESULTS],
        "truncated": len(candidates) > MAX_RESULTS,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _where(c: dict) -> str:
    loc = f"{c['file']}:{c['line']}" if c.get("line") else c["file"]
    extra = "/".join(x for x in (c.get("job"), c.get("step")) if x) or c.get("package") or ""
    return f"{loc} ({extra})" if extra else loc


def cmd_actions(opts) -> int:
    for name in ("agent_uses", "agent_run"):
        value = getattr(opts, name)
        if value:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(f"--{name.replace('_', '-')} is not a valid regular expression: {exc}")
    result = check_actions(resolve_root(opts.root), opts)
    s = result["stats"]
    print(f"supply_chain actions: {s['workflow_files']} workflows, {s['composite_actions']} composite actions, "
          f"{s['agent_steps']} agent steps, {s['candidate_count']} candidates {s['by_severity']}.")
    for a in result["agent_steps"][:20]:
        print(f"  [AGENT] {a['file']}:{a['line']} ({a['job']}/{a['step']}) via {', '.join(a['detected_by'])}; "
              f"outsider events: {', '.join(a['outsider_triggers']) or 'none'}")
    for c in result["candidates"][:30]:
        print(f"  [{c['severity']}] {c['rule']} {_where(c)}")
    print("Candidates need confirmation against the workflow, the actions' documentation and repository settings.")
    if opts.json_out:
        write_json(result, opts.json_out)
        print(f"JSON written: {opts.json_out}")
    return 1 if fail_threshold(result["candidates"], opts.fail_on) else 0


def cmd_lockfiles(opts) -> int:
    result = check_lockfiles(resolve_root(opts.root), opts.registry or [])
    s = result["stats"]
    print(f"supply_chain lockfiles: {s['lockfiles']} lockfiles, {s['packages']} packages, "
          f"{s['candidate_count']} candidates {s['by_severity']}.")
    for r in result["lockfiles"]:
        ic = r["install_time_code"]
        install = f"{ic['count']} run install code" if ic["recorded"] else "install code not recorded"
        print(f"  {r['path']} ({r['ecosystem']}): {r['packages']} packages, {install}, "
              f"registries {r['registries'] or '{}'}, {r['missing_integrity']['count']} without integrity hash")
    for e in result["errors"]:
        print(f"  [SKIPPED] {e['path']}: {e['error']}")
    for c in result["candidates"][:30]:
        print(f"  [{c['severity']}] {c['rule']} {_where(c)}")
    print("Lockfile signals are leads. Check advisories and maintainers separately before rating anything.")
    if opts.json_out:
        write_json(result, opts.json_out)
        print(f"JSON written: {opts.json_out}")
    return 1 if fail_threshold(result["candidates"], opts.fail_on) else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="supply_chain.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("actions", help="trace outsider text and agent steps through GitHub Actions files")
    p.add_argument("--root", default=".", help="repository root (default: .)")
    p.add_argument("--agent-uses", help="extra regex for 'uses:' values that are AI agent actions")
    p.add_argument("--agent-run", help="extra regex for 'run:' scripts that start an AI agent CLI")
    p.add_argument("--json-out", help="write the full result as JSON (mode 0600)")
    p.add_argument("--fail-on", choices=["never", "high", "medium"], default="never",
                   help="exit 1 when a candidate at or above this severity exists (default: never)")
    p.set_defaults(func=cmd_actions)

    p = sub.add_parser("lockfiles", help="read lockfiles for install-time code and risky sources")
    p.add_argument("--root", default=".", help="repository root (default: .)")
    p.add_argument("--registry", action="append", metavar="HOST",
                   help="an expected internal registry host (repeatable)")
    p.add_argument("--json-out", help="write the full result as JSON (mode 0600)")
    p.add_argument("--fail-on", choices=["never", "high", "medium"], default="never",
                   help="exit 1 when a candidate at or above this severity exists (default: never)")
    p.set_defaults(func=cmd_lockfiles)
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
