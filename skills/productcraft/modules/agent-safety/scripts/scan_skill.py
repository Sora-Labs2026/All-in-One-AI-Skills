#!/usr/bin/env python3
"""ProductCraft Agent Safety extension scanner.

Statically flags risky patterns in a third-party skill, plugin, MCP server or
hook folder before it is installed: instructions that try to override the
user, hidden text, download-and-run, credential paths, data-capture
endpoints, install-time scripts, automatic hooks, broad permissions,
persistence, unpinned sources, embedded secrets, obfuscation, binaries and
symlinks that point outside the folder.

Read-only: files are opened for reading only, symlinks are never followed,
nothing is executed and nothing touches the network. Output is advisory. A
clean scan is not approval, and a finding is a reason to read the code, not a
verdict. Evidence is quoted from untrusted files, redacted and truncated.
"""
from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional

VERSION = "1.0.0"
SEVERITIES = ["low", "medium", "high", "critical"]
RANK = {s: i for i, s in enumerate(SEVERITIES)}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 10000
MAX_FINDINGS = 500
EVIDENCE_CHARS = 120

CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".fish", ".ps1",
            ".rb", ".pl", ".php", ".go", ".rs", ".lua", ".java", ".kt", ".swift", ".cs", ".bat", ".cmd"}
SHELL_EXT = {".sh", ".bash", ".zsh"}
DOC_EXT = {".md", ".mdx", ".markdown", ".txt", ".rst", ".html", ".htm", ".adoc"}
CONFIG_EXT = {".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".xml", ".plist"}
CODE_NAMES = {"Makefile", "Dockerfile", "Justfile", "Rakefile", "Procfile"}
ASSET_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".svgz", ".woff", ".woff2", ".ttf",
             ".otf", ".eot", ".pdf", ".mp3", ".mp4", ".wav", ".ogg", ".webm", ".mov"}
ARCHIVE_EXT = (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".whl", ".egg",
               ".nupkg", ".crx", ".vsix", ".dmg", ".pkg", ".deb", ".rpm", ".apk", ".xpi")
SKIP_DIRS = {".git", ".hg", ".svn"}
BUNDLED_DIRS = {"node_modules", "vendor", ".venv", "venv", "site-packages", "__pypackages__", "bower_components"}
EXEC_MAGIC = (b"\x7fELF", b"MZ", b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe",
              b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\x00asm")

I = re.IGNORECASE


def rx(pattern: str, flags: int = 0) -> "re.Pattern":
    return re.compile(pattern, flags)


# (rule, severity, scope, regex, message). Scope: all | code | text (docs+config).
LINE_RULES = [
    ("PROMPT-OVERRIDE", "high", "all",
     rx(r"\b(ignore|disregard|forget|override|bypass)\b[^.!?\n]{0,40}\b(previous|prior|above|earlier|preceding|all|any|"
        r"other|existing|system|developer|user'?s?)\b[^.!?\n]{0,25}\b(instructions?|prompts?|rules|guidelines|directions|"
        r"guardrails|policies)\b", I),
     "Text tells the agent to set aside its existing instructions."),
    ("PROMPT-OVERRIDE", "high", "all",
     rx(r"\b(do not|don'?t|never)\s+(tell|inform|notify|alert)\s+(the\s+)?(user|human|operator|owner)s?\s+(about|that\s+"
        r"(you|this|we|it)\b|what\s+(you|this)|where|how\s+you)|\b(do not|don'?t|never)\s+(mention|reveal|disclose|show)\s+"
        r"(this|these|it|that|the\s+\w+)\s+to\s+the\s+(user|human|operator|owner)|\b(hide|conceal)\b[^.!?\n]{0,30}\bfrom\s+"
        r"the\s+(user|human|operator|owner)", I),
     "Text asks the agent to hide something from the user."),
    ("PROMPT-OVERRIDE", "high", "all",
     rx(r"\bwithout\s+(asking|telling|informing|notifying|alerting)\b[^.!?\n]{0,15}\b(the\s+)?(user|human|operator|owner|"
        r"them|anyone)\b|\bwithout\s+(the\s+)?(user|human)'?s?\s+(knowledge|consent|permission|approval)", I),
     "Text asks the agent to act without the user's knowledge or consent."),
    ("PROMPT-OVERRIDE", "high", "all",
     rx(r"\b(silently|secretly|quietly|covertly|stealthily)\s+(run|execute|install|send|upload|delete|remove|copy|"
        r"post|download|modify|forward|exfiltrate)\b", I),
     "Text asks for a hidden action."),
    ("PROMPT-OVERRIDE", "high", "all",
     rx(r"\b(you are now|from now on,? you are|enter|switch to)\b[^.!?\n]{0,30}\b(unrestricted|jailbroken|developer mode|"
        r"god mode|no (rules|restrictions|limits))", I),
     "Text tries to switch the agent into an unrestricted role."),
    ("PROMPT-OVERRIDE", "high", "all",
     rx(r"^\s*(<\|?(system|im_start)\|?>|\[/?system\]|</?system>|#+\s*system\s*(prompt)?\s*:)", I),
     "Text imitates a system-message marker."),
    ("PROMPT-OVERRIDE", "medium", "all",
     rx(r"\b(new|updated|real|true|actual|hidden)\s+(system\s+)?instructions?\s*:", I),
     "Text announces replacement instructions."),
    ("PROMPT-OVERRIDE", "medium", "all",
     rx(r"\bnever\s+ask\s+(the\s+user\s+)?(for\s+)?(permission|confirmation|approval)\b|\bauto[- ]?approve\s+(all|every)\b", I),
     "Text tells the agent to stop asking for approval."),
    ("REMOTE-EXEC", "critical", "all",
     rx(r"\b(curl|wget)\b[^\n|]*?(https?://|\$\{?\w|\b[\w-]+\.[a-z]{2,}\b)[^\n|]*\|\s*(sudo\s+)?(-\S+\s+)*(ba|z|da|k)?sh\b"),
     "Downloads code and pipes it straight into a shell."),
    ("REMOTE-EXEC", "critical", "all",
     rx(r"(\b(ba|z)?sh\s+<\(|\b(ba|z)?sh\s+-c\s+[\"']?\$\(|\bsource\s+<\(|\beval\s+[\"']?\$\()\s*(curl|wget)\b[^)\n]*"
        r"(https?://|\$\{?\w|\b[\w-]+\.[a-z]{2,}\b)"),
     "Runs a downloaded script without saving it."),
    ("REMOTE-EXEC", "critical", "all",
     rx(r"\b(exec|eval)\s*\(\s*(requests\.get|urllib\.request\.urlopen|urlopen|httpx\.get)\b|\beval\s*\(\s*(await\s+)?"
        r"(fetch|axios)\b|\bimport\s*\(\s*['\"`]https?://"),
     "Fetches code from the network and executes it at runtime."),
    ("REMOTE-EXEC", "critical", "all",
     rx(r"(?=.*(https?://|\$\w))(\b(iex|invoke-expression)\b.*\b(iwr|irm|invoke-webrequest|invoke-restmethod|downloadstring)\b|"
        r"\b(iwr|irm|invoke-webrequest|invoke-restmethod|downloadstring)\b.*\|\s*(iex|invoke-expression)\b)", I),
     "Downloads and executes code (PowerShell)."),
    ("DECODE-EXEC", "high", "all",
     rx(r"base64\s+(-d|--decode|-D)\b[^\n|]*\|\s*(ba|z)?sh\b|\b(exec|eval)\s*\(\s*(base64\.b64decode|codecs\.decode|"
        r"bytes\.fromhex|zlib\.decompress|marshal\.loads|bz2\.decompress|lzma\.decompress)|\beval\s*\(\s*(atob|"
        r"Buffer\.from|unescape)\s*\(|\bnew\s+Function\s*\(\s*(atob|Buffer\.from)"),
     "Decodes hidden data and executes it."),
    ("DYNAMIC-EVAL", "medium", "code",
     rx(r"(?<![\w.$])eval\s*\(|\bnew\s+Function\s*\(|\b__import__\s*\(|importlib\.import_module\s*\(\s*[^'\"\s)]|"
        r"\brequire\s*\(\s*[^'\"`\s)]"),
     "Builds or loads code at runtime; check where the input comes from."),
    ("EXFIL-ENDPOINT", "high", "all",
     rx(r"webhook\.site|requestbin|pipedream\.net|beeceptor|hookbin|interact\.sh|\boast\.(fun|me|pro|live|site|online)\b|"
        r"burpcollaborator|canarytokens|ngrok(-free)?\.(io|app|dev)|trycloudflare\.com|\bloca\.lt\b|localtunnel\.me|"
        r"serveo\.net|localhost\.run|discord(app)?\.com/api/webhooks|api\.telegram\.org/bot|hooks\.slack\.com/"
        r"(services|workflows)|pastebin\.com|paste\.ee|hastebin|rentry\.(co|org)|ghostbin|transfer\.sh|\b0x0\.st\b|"
        r"\bfile\.io\b|\btemp\.sh\b|bashupload", I),
     "Mentions a data-capture, tunnel, paste or file-drop service often used to move data off a machine."),
    ("NETWORK-SEND", "medium", "code",
     rx(r"\b(requests|httpx|session|client)\.(post|put|patch)\s*\(|urllib\.request\.Request\s*\([^)]*data\s*=|"
        r"\bfetch\s*\([^)]*\{[^}]*method\s*:\s*['\"](POST|PUT|PATCH)|\baxios\.(post|put|patch)\s*\(|"
        r"\bcurl\b[^\n]*\s(-d|--data\S*|-F|--form|-T|--upload-file)\s|\bwget\b[^\n]*--post-(data|file)|"
        r"\bsocket\.(connect|create_connection)\s*\(|\bnet\.connect\s*\(", I),
     "Sends data over the network; confirm the destination and what is sent."),
    ("CREDENTIAL-ACCESS", "high", "all",
     rx(r"\.ssh/id_(rsa|dsa|ecdsa|ed25519)(_sk)?\b(?!\.pub)|\.aws/credentials|\.config/gcloud|application_default_"
        r"credentials\.json|\.azure/|\.kube/config|\.docker/config\.json|\.netrc\b|\.git-credentials|\.gnupg\b|"
        r"\.password-store|Library/Keychains|security\s+(find-(generic|internet)-password|dump-keychain)|"
        r"secret-tool\s+lookup|keyring\.get_password|wallet\.dat|\.electrum\b|solana/id\.json|\.claude/\.credentials\.json|"
        r"\.codex/auth\.json|\.config/github-copilot", I),
     "References a credential store, key file, wallet or the agent's own login or session data."),
    ("CREDENTIAL-ACCESS", "high", "all",
     rx(r"(Login Data|Cookies|Local State|key4\.db|logins\.json).{0,80}(Chrome|Chromium|Brave|Firefox|\.mozilla|Edge)|"
        r"(Chrome|Chromium|Brave|Firefox|\.mozilla|Edge).{0,80}(Login Data|Cookies|Local State|key4\.db|logins\.json)"),
     "References browser password or cookie stores."),
    ("CREDENTIAL-ACCESS", "medium", "all",
     rx(r"~/\.ssh\b|\$HOME/\.ssh\b|\.npmrc\b|\.pypirc\b|\bprintenv\b|os\.environ\.items\s*\(|\.claude/projects\b|"
        r"\.claude\.json\b", I),
     "Touches SSH settings, registry tokens, the full environment or the agent's session history; check why."),
    ("ENV-HARVEST", "medium", "code",
     rx(r"JSON\.stringify\s*\(\s*process\.env\s*\)|Object\.(entries|keys|values)\s*\(\s*process\.env\s*\)|"
        r"\bdict\s*\(\s*os\.environ\s*\)|json\.dumps\s*\(\s*(dict\s*\()?\s*os\.environ|\benv\s*>\s*\S|\bprintenv\s*[>|]"),
     "Collects the whole environment, which usually holds tokens and keys."),
    ("PERSISTENCE", "medium", "all",
     rx(r"\.(bashrc|bash_profile|zshrc|zprofile|zshenv|profile)\b|\bcrontab\b|LaunchAgents|LaunchDaemons|"
        r"systemctl\s+(--user\s+)?enable|\.config/autostart|authorized_keys|core\.hooksPath|"
        r"\.claude/settings(\.local)?\.json|\.git/hooks/", I),
     "Mentions a location that makes code run automatically or changes agent settings."),
    ("BROAD-PERMISSION", "high", "all",
     rx(r"--dangerously-skip-permissions|\"defaultMode\"\s*:\s*\"bypassPermissions\"|\"enableAllProjectMcpServers\"\s*:\s*true"),
     "Grants the agent unrestricted command execution or skips permission prompts."),
    ("BROAD-PERMISSION", "medium", "all",
     rx(r"^\s*allowed-tools\s*:.*\bBash\b(?!\()|^\s*allowed-tools\s*:.*\bBash\(\*(:\*)?\)", I),
     "Skill frontmatter allows every shell command."),
    ("BROAD-PERMISSION", "medium", "all",
     rx(r"\"(autoApprove|alwaysAllow)\"\s*:\s*\[\s*\"|--privileged\b|-v\s+/:/|-v\s+(~|\$HOME):/"),
     "Auto-approves tools or gives a container broad host access."),
    ("UNPINNED-SOURCE", "medium", "text",
     rx(r"@latest\b|\bpip3?\s+install\s+(-U\s+)?git\+https?://(?!\S*@[0-9a-f]{7,})\S+", I),
     "Installs whatever version is current at run time, so the code reviewed today may not be the code that runs."),
    ("EMBEDDED-SECRET", "high", "all",
     rx(r"-----BEGIN ((RSA|EC|DSA|OPENSSH|ENCRYPTED|PGP) )?PRIVATE KEY( BLOCK)?-----"),
     "Contains a private key."),
    ("EMBEDDED-SECRET", "medium", "all",
     rx(r"\bsk-(proj-|ant-)?[A-Za-z0-9_-]{20,}|\bsk_live_[0-9a-zA-Z]{16,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}|"
        r"\bgithub_pat_[A-Za-z0-9_]{30,}|\bxox[abprs]-[A-Za-z0-9-]{10,}|\bAIza[0-9A-Za-z_-]{35}\b|\bglpat-[A-Za-z0-9_-]{20}"),
     "Contains something shaped like an API token."),
    ("OBFUSCATED", "medium", "all",
     rx(r"(?<![A-Za-z0-9+/])(?<!base64,)[A-Za-z0-9+/]{300,}={0,2}|(\\x[0-9a-fA-F]{2}){20,}|(\\u[0-9a-fA-F]{4}){20,}|"
        r"fromCharCode\s*\(\s*\d+(\s*,\s*\d+){15,}"),
     "Long encoded or escaped data that hides what the file does."),
]
NEGATED = rx(r"\b(not|never|no|don'?t|do not|must not|cannot|can'?t|won'?t|avoid|refuse to)\b[^.!?]{0,30}$", I)
NEGATABLE = {"Text tells the agent to set aside its existing instructions.",
             "Text asks the agent to act without the user's knowledge or consent.",
             "Text asks for a hidden action.", "Text tries to switch the agent into an unrestricted role."}
DEFENSIVE = rx(r"\b(embedded|injected|untrusted|external|third-party|malicious|hidden|planted)\s+(instructions?|prompts?|"
               r"commands?|text)\b|\binstructions?\s+(that\s+(are|were)\s+)?(embedded|injected|hidden|found|contained|planted)\b|"
               r"\binstructions?\s+(found\s+)?(in|inside|within)\s+(the\s+)?(file|files|issues?|content|data|web\s?pages?|"
               r"repository|repo|tool\s+output|source|comments?|code|strings|documents?|pages?|emails?|messages?|results?|output)", I)
COMMENT_LINE = rx(r"^\s*(#(?!!)|//|/\*|\*|--\s|;)")
COMMENT_EXEMPT = {"CREDENTIAL-ACCESS", "PERSISTENCE", "NETWORK-SEND", "ENV-HARVEST", "DYNAMIC-EVAL", "UNPINNED-SOURCE"}
WRITE_CONTEXT = rx(r">>|>\s*~|tee\s+-a|appendFile|open\s*\([^)]*['\"]a\+?['\"]|write_text|writeFile|\bcrontab\s+(-(\s|$)|[^-\s`])|\|\s*crontab\b", I)
HIDDEN_CHARS = rx("[\u200b\u200c\u200e\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\U000e0000-\U000e007f]")
REORDER_CHARS = rx("[\u202a-\u202e\u2066-\u2069\U000e0000-\U000e007f]")  # bidi controls and tag characters
ZWJ_IN_TEXT = rx("(?<=[A-Za-z0-9 ])\u200d(?=[A-Za-z0-9 ])")
HTML_COMMENT = rx(r"<!--(.*?)-->", re.S)
COMMENT_INSTRUCTION = rx(r"\b(ignore|disregard|instructions?|system prompt|do not tell|don'?t tell|you (must|should|are)|"
                         r"execute|exfiltrate|curl|wget|secret|token|password)\b|\b(assistant|agent|ai|model)\s*:", I)
RAW_IP_URL = rx(r"\b(?:https?|ftp|tcp|udp|wss?)://(\d{1,3}(?:\.\d{1,3}){3})")
REDACT = rx(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|(?=[A-Za-z0-9+=_-]*\d)(?=[A-Za-z0-9+=_-]*[A-Za-z])[A-Za-z0-9+=_-]{40,}|\bsk-[A-Za-z0-9_-]{8,}|\bsk_(live|test)_[0-9a-zA-Z]{8,}|\bAKIA[0-9A-Z]{8,}|"
            r"\bgh[pousr]_[A-Za-z0-9]{8,}|\bgithub_pat_[A-Za-z0-9_]{8,}|\bxox[abprs]-[A-Za-z0-9-]{6,}|\bAIza[0-9A-Za-z_-]{10,}|"
            r"\bglpat-[A-Za-z0-9_-]{8,}|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}")
HOOK_EVENTS = {"PreToolUse", "PostToolUse", "SessionStart", "SessionEnd", "UserPromptSubmit", "Stop", "SubagentStop",
               "Notification", "PreCompact", "PostToolUseFailure", "PermissionRequest"}
LIFECYCLE_SCRIPTS = {"preinstall", "install", "postinstall", "prepare", "preprepare", "postprepare", "prepublish",
                     "prepack", "postpack"}
RUNNERS = {"npx", "uvx", "bunx", "pnpx"}
SHELL_FENCE = rx(r"^\s*(```|~~~)\s*(bash|sh|shell|zsh|console|terminal|shell-session)\s*$", I)
FENCE = rx(r"^\s*(```|~~~)")
NETWORK_HINT = rx(r"\b(curl|wget|nc|ncat|netcat|Invoke-WebRequest)\b|https?://", I)
CAPABILITIES = {
    "shell": rx(r"\bsubprocess\.|\bos\.system\s*\(|\bos\.popen\s*\(|child_process|\bexecSync\s*\(|\bspawn(Sync)?\s*\(|"
                r"Runtime\.getRuntime\(\)\.exec|shell\s*=\s*True|\bexec\.Command\s*\("),
    "network": rx(r"\brequests\.|\bhttpx\.|\burllib\b|\bfetch\s*\(|\baxios\b|\bhttps?\.request\s*\(|\bWebSocket\s*\(|"
                  r"\bsocket\.|\bnet\.connect\s*\(|\baiohttp\b|\bcurl\b|\bwget\b"),
    "file-write": rx(r"\bopen\s*\([^)]*['\"][wa]\+?b?['\"]|\bwrite_text\s*\(|\bwriteFile(Sync)?\s*\(|\bappendFile(Sync)?\s*\(|"
                     r"\bfs\.(rm|unlink|rename)|\bshutil\.(rmtree|move|copy)|\bos\.(remove|unlink|rename)\s*\("),
    "environment": rx(r"\bos\.environ\b|\bos\.getenv\s*\(|\bprocess\.env\b|\bgetenv\s*\("),
}


def load_guard():
    path = Path(__file__).resolve().parent / "guard_command.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("agent_safety_guard_command", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sanitize(text: str) -> str:
    out = []
    for ch in text:
        if HIDDEN_CHARS.match(ch) or ch in "\u200d\ufeff":
            out.append(f"<U+{ord(ch):04X}>")
        elif ch == "\t":
            out.append(" ")
        elif ord(ch) < 32 or ord(ch) == 127:
            continue
        else:
            out.append(ch)
    clean = REDACT.sub("[REDACTED]", "".join(out).strip())
    return clean if len(clean) <= EVIDENCE_CHARS else clean[:EVIDENCE_CHARS - 3] + "..."


class Scan:
    def __init__(self, root: Path, guard=None) -> None:
        self.root = root
        self.real_root = os.path.realpath(root)
        self.guard = guard
        self.findings: List[dict] = []
        self.dropped = 0
        self.files_scanned = 0
        self.skipped: List[dict] = []
        self.capabilities: Dict[str, set] = {k: set() for k in
                                             ("shell", "network", "file-write", "environment", "credentials",
                                              "hooks", "install-scripts")}
        self.purpose: Optional[str] = None
        self.guard_ctx = None
        if guard is not None:
            self.guard_ctx = guard.make_context(cwd=self.real_root, project_root=self.real_root,
                                                home="/nonexistent-home", read_git_head=False)

    def add(self, rule: str, severity: str, rel: str, line: int, message: str, evidence: str = "") -> None:
        if len(self.findings) >= MAX_FINDINGS:
            self.dropped += 1
            return
        for f in self.findings[-30:]:
            if (f["rule"], f["path"], f["line"]) == (rule, rel, line):
                if RANK[severity] > RANK[f["severity"]]:
                    f["severity"], f["message"] = severity, message
                elif message != f["message"] and message not in f["message"] and RANK[severity] == RANK[f["severity"]]:
                    f["message"] += " " + message
                return
        self.findings.append({"rule": rule, "severity": severity, "path": rel, "line": line,
                              "message": message, "evidence": sanitize(evidence)})

    # -- walking ---------------------------------------------------------
    def run(self) -> None:
        if self.root.is_file():
            self.scan_file(self.root, self.root.name)
            return
        count = 0
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames.sort()
            rel_dir = os.path.relpath(dirpath, self.root)
            keep = []
            for d in dirnames:
                full = os.path.join(dirpath, d)
                rel = os.path.normpath(os.path.join(rel_dir, d))
                if os.path.islink(full):
                    self.check_symlink(full, rel)
                elif d in SKIP_DIRS:
                    continue
                elif d in BUNDLED_DIRS:
                    self.add("NOT-SCANNED", "medium", rel, 0,
                             "Bundled dependency folder was not scanned; its code runs too. Prefer installing "
                             "dependencies from a lockfile you can audit.")
                    self.skipped.append({"path": rel, "reason": "bundled dependencies"})
                else:
                    keep.append(d)
            dirnames[:] = keep
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                rel = os.path.normpath(os.path.join(rel_dir, name))
                if os.path.islink(full):
                    self.check_symlink(full, rel)
                    continue
                count += 1
                if count > MAX_FILES:
                    self.skipped.append({"path": rel, "reason": "file limit reached"})
                    self.add("NOT-SCANNED", "medium", rel, 0, f"Stopped after {MAX_FILES} files; the rest was not scanned.")
                    return
                self.scan_file(Path(full), rel)

    def check_symlink(self, full: str, rel: str) -> None:
        try:
            target = os.readlink(full)
        except OSError:
            return
        resolved = os.path.realpath(os.path.join(os.path.dirname(full), target))
        if not (resolved == self.real_root or resolved.startswith(self.real_root.rstrip(os.sep) + os.sep)):
            self.add("SYMLINK-ESCAPE", "high", rel, 0,
                     "Symlink points outside the folder; reading it would read another part of the machine.",
                     f"-> {target}")
        self.skipped.append({"path": rel, "reason": "symlink not followed"})

    # -- files -----------------------------------------------------------
    def scan_file(self, path: Path, rel: str) -> None:
        name = path.name
        ext = path.suffix.lower()
        try:
            size = path.stat().st_size
        except OSError:
            return
        if ext in ASSET_EXT:
            return
        if name.lower().endswith(ARCHIVE_EXT):
            self.add("ARCHIVE-FILE", "medium", rel, 0, "Archive inside the extension; its contents were not reviewed.")
            return
        if ext in (".pyc", ".pyo", ".class"):
            source = path.parent.parent / (name.split(".", 1)[0] + ".py")
            if path.parent.name == "__pycache__" and source.is_file():
                self.add("BINARY-FILE", "low", rel, 0, "Python bytecode cache next to its source; Python may load it instead of the "
                         "source you read. Delete the cache before installing.")
            else:
                self.add("BINARY-FILE", "medium", rel, 0, "Compiled code without the reviewed source; it may differ from any source shown.")
            return
        if size > MAX_FILE_BYTES:
            self.add("NOT-SCANNED", "low", rel, 0, f"File larger than {MAX_FILE_BYTES // (1024 * 1024)} MB was not scanned.")
            self.skipped.append({"path": rel, "reason": "too large"})
            return
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            self.skipped.append({"path": rel, "reason": f"unreadable ({type(exc).__name__})"})
            return
        head = data[:8192]
        if head.startswith(EXEC_MAGIC) and (head.startswith(b"\x7fELF") or b"\x00" in head):
            self.add("BINARY-FILE", "high", rel, 0, "Executable binary: it cannot be reviewed as text. Ask where it was built from.")
            return
        if b"\x00" in head:
            self.add("BINARY-FILE", "medium", rel, 0, "Binary file that cannot be reviewed as text.")
            return
        text = data.decode("utf-8", errors="replace")
        self.files_scanned += 1
        first = text.split("\n", 1)[0]
        kind = ("code" if ext in CODE_EXT or name in CODE_NAMES or first.startswith("#!")
                else "text" if ext in DOC_EXT or ext in CONFIG_EXT or name.upper().startswith(("SKILL", "README", "AGENTS", "CLAUDE"))
                else "text")
        self.scan_lines(text, rel, kind, ext)
        if ext in (".md", ".mdx", ".markdown"):
            self.scan_html_comments(text, rel)
        if name == "package.json":
            self.scan_package_json(text, rel)
        if ext in (".json", ".jsonc"):
            self.scan_json_config(text, rel)
        if name == "setup.py" and "cmdclass" in text:
            self.add("INSTALL-SCRIPT", "medium", rel, text[:text.index("cmdclass")].count("\n") + 1,
                     "setup.py overrides build or install commands; read what runs at install time.")
            self.capabilities["install-scripts"].add(rel)
        if self.guard is not None:
            if ext in SHELL_EXT or (kind == "code" and re.match(r"#!.*\b(ba|z|da)?sh\b", first)):
                self.scan_shell(text.split("\n"), rel, 0)
            elif ext in (".md", ".mdx", ".markdown"):
                self.scan_shell_fences(text, rel)
        if self.purpose is None and name in ("SKILL.md", "package.json", "plugin.json"):
            self.purpose = self.extract_purpose(text, name)

    def scan_lines(self, text: str, rel: str, kind: str, ext: str) -> None:
        caps_seen = set()
        lines = text.split("\n")
        file_has_credential = None
        file_has_send = None
        for n, line in enumerate(lines, 1):
            comment = kind == "code" and bool(COMMENT_LINE.match(line))
            if REORDER_CHARS.search(line):
                self.add("HIDDEN-TEXT", "high", rel, n,
                         "Direction-changing or tag characters can make text read differently to a person and to the agent.", line)
            elif HIDDEN_CHARS.search(line) or ZWJ_IN_TEXT.search(line) or ("\ufeff" in line and not (n == 1 and line.index("\ufeff") == 0)):
                self.add("HIDDEN-TEXT", "medium", rel, n,
                         "Zero-width characters are invisible to a reviewer; check they only escape formatting.", line)
            if kind == "code" and len(line) > 3000:
                self.add("OBFUSCATED", "low", rel, n, "Very long line (minified or generated code); review the readable source instead.")
                continue
            for rule, severity, scope, pattern, message in LINE_RULES:
                if scope == "code" and kind != "code":
                    continue
                if scope == "text" and kind == "code":
                    continue
                if rule == "DYNAMIC-EVAL" and ext not in (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rb", ".php"):
                    continue
                m = pattern.search(line)
                if not m:
                    continue
                if message in NEGATABLE and NEGATED.search(line[:m.start()]):
                    continue  # "never silently delete ..." is a safeguard, not an attack
                if rule == "PROMPT-OVERRIDE" and DEFENSIVE.search(line):
                    continue  # "ignore instructions embedded in issues" protects the user
                if comment and rule in COMMENT_EXEMPT:
                    continue
                sev = severity
                if rule == "PERSISTENCE" and WRITE_CONTEXT.search(line):
                    sev = "high"
                if rule == "CREDENTIAL-ACCESS" and severity == "high":
                    file_has_credential = file_has_credential or n
                    if ext in DOC_EXT:
                        sev = "medium"  # prose that names a credential path is weaker evidence than code opening it
                if rule in ("NETWORK-SEND", "EXFIL-ENDPOINT"):
                    file_has_send = file_has_send or n
                if rule == "CREDENTIAL-ACCESS":
                    self.capabilities["credentials"].add(rel)
                self.add(rule, sev, rel, n, message, line)
            for m in RAW_IP_URL.finditer(line):
                try:
                    if ipaddress.ip_address(m.group(1)).is_global:
                        self.add("RAW-IP-URL", "medium", rel, n, "URL with a hard-coded public IP address; check who runs it.", line)
                except ValueError:
                    pass
            if kind == "code":
                for cap, pattern in CAPABILITIES.items():
                    if cap not in caps_seen and pattern.search(line):
                        caps_seen.add(cap)
                        self.capabilities[cap].add(rel)
        if file_has_credential and file_has_send:
            self.add("COMBINED-EXFIL", "critical", rel, file_has_credential,
                     "The same file reads credential locations and sends data off the machine: treat as exfiltration until the code proves otherwise.")

    def scan_html_comments(self, text: str, rel: str) -> None:
        for m in HTML_COMMENT.finditer(text):
            body = m.group(1)
            if COMMENT_INSTRUCTION.search(body):
                line = text[:m.start()].count("\n") + 1
                self.add("HIDDEN-TEXT", "medium", rel, line,
                         "HTML comment with instruction-like words: hidden from rendered views but read by agents.", body)

    def scan_package_json(self, text: str, rel: str) -> None:
        try:
            data = json.loads(text)
        except ValueError:
            return
        scripts = data.get("scripts") if isinstance(data, dict) else None
        if not isinstance(scripts, dict):
            return
        for key in sorted(scripts):
            if key in LIFECYCLE_SCRIPTS and isinstance(scripts[key], str):
                self.capabilities["install-scripts"].add(rel)
                self.add("INSTALL-SCRIPT", "high", rel, self.line_of(text, f'"{key}"'),
                         f"npm runs the '{key}' script automatically during install; read exactly what it does.",
                         f"{key}: {scripts[key]}")

    def scan_json_config(self, text: str, rel: str) -> None:
        try:
            data = json.loads(text)
        except ValueError:
            return
        for hook_cmd in self.find_hook_commands(data):
            sev = "high" if NETWORK_HINT.search(hook_cmd) else "medium"
            self.capabilities["hooks"].add(rel)
            self.add("AUTO-RUN-HOOK", sev, rel, self.line_of(text, json.dumps(hook_cmd)[1:31]),
                     "Hook command runs automatically on agent events with the user's permissions.", hook_cmd)
        for allowed in self.find_allow_lists(data):
            broad = [a for a in allowed if a in ("Bash", "Bash(*)", "Bash(*:*)", "*")]
            if broad:
                self.add("BROAD-PERMISSION", "high", rel, self.line_of(text, json.dumps(broad[0])),
                         "Permission list allows every shell command without a prompt.", json.dumps(broad[0]))
        for server in self.find_launchers(data):
            command, args = server
            pkg = next((a for a in args if isinstance(a, str) and not a.startswith("-")), "")
            if command in RUNNERS and pkg and not re.search(r"(@|==)\d", pkg.lstrip("@").split("/", 1)[-1]):
                self.add("UNPINNED-SOURCE", "medium", rel, self.line_of(text, pkg),
                         f"Launches '{pkg}' through {command} without a fixed version; every start may fetch new code.",
                         f"{command} {' '.join(str(a) for a in args)}")
            if command in ("docker", "podman") and "run" in args:
                image = next((a for a in args[args.index("run") + 1:] if isinstance(a, str) and not a.startswith("-")), "")
                if image and ("@sha256:" not in image) and (":" not in image.split("/")[-1] or image.endswith(":latest")):
                    self.add("UNPINNED-SOURCE", "medium", rel, self.line_of(text, image),
                             f"Runs container image '{image}' without a fixed tag or digest.", image)

    @staticmethod
    def find_hook_commands(data) -> List[str]:
        found: List[str] = []

        def collect_commands(node) -> None:
            if isinstance(node, dict):
                cmd = node.get("command")
                if isinstance(cmd, str):
                    found.append(cmd)
                for v in node.values():
                    collect_commands(v)
            elif isinstance(node, list):
                for v in node:
                    collect_commands(v)

        def walk(node) -> None:
            if isinstance(node, dict):
                hooks = node.get("hooks")
                if isinstance(hooks, dict) and any(k in HOOK_EVENTS for k in hooks):
                    collect_commands(hooks)
                for k, v in node.items():
                    if k != "hooks":
                        walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)
        return found

    @staticmethod
    def find_allow_lists(data) -> List[list]:
        found = []

        def walk(node) -> None:
            if isinstance(node, dict):
                perms = node.get("permissions")
                if isinstance(perms, dict) and isinstance(perms.get("allow"), list):
                    found.append([a for a in perms["allow"] if isinstance(a, str)])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)
        return found

    @staticmethod
    def find_launchers(data) -> List[tuple]:
        found = []

        def walk(node) -> None:
            if isinstance(node, dict):
                cmd, args = node.get("command"), node.get("args")
                if isinstance(cmd, str) and isinstance(args, list):
                    found.append((os.path.basename(cmd), args))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)
        return found

    def scan_shell_fences(self, text: str, rel: str) -> None:
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            m = SHELL_FENCE.match(lines[i])
            if m:
                console = m.group(2).lower() in ("console", "terminal", "shell-session")
                j = i + 1
                block = []
                while j < len(lines) and not FENCE.match(lines[j]):
                    block.append(lines[j])
                    j += 1
                if console:
                    block = [re.sub(r"^\s*[$#]\s?", "", b) if re.match(r"^\s*[$#]\s", b) else "" for b in block]
                self.scan_shell(block, rel, i + 1)
                i = j + 1
            else:
                i += 1

    def scan_shell(self, lines: List[str], rel: str, offset: int) -> None:
        g = self.guard
        logical, start, heredoc = "", 0, None
        for idx, raw in enumerate(lines, 1):
            if heredoc is not None:
                if raw.strip() == heredoc:
                    heredoc = None
                continue
            stripped = raw.strip()
            if not logical and (not stripped or stripped.startswith("#")):
                continue
            if not logical:
                start = idx
            if stripped.endswith("\\"):
                logical += stripped[:-1] + " "
                continue
            logical += stripped
            m = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", logical)
            if m:
                heredoc = m.group(1)
            if re.search(r"<[A-Za-z][\w./-]*>", logical):
                logical = ""
                continue  # documentation placeholder such as <skill-root>, not a runnable command
            try:
                result = g.evaluate_command(logical, self.guard_ctx)
            except Exception:  # pragma: no cover - the guard is defensive; never let it stop a scan
                result = None
            if result is not None:
                for f in result.findings:
                    if f.rule.startswith(("PARSE", "PRIV", "DEPLOY", "PUBLISH", "REMOTE-EXEC")) or f.rule == "GUARD-ERROR":
                        continue
                    sev = "high" if f.decision == "deny" else "medium"
                    self.add("DESTRUCTIVE-SHELL", sev, rel, offset + start,
                             f"Shell command the guard rates {f.decision.upper()} ({f.rule}): {f.reason}", logical)
            logical = ""

    @staticmethod
    def line_of(text: str, needle: str) -> int:
        pos = text.find(needle)
        return text[:pos].count("\n") + 1 if pos >= 0 else 0

    @staticmethod
    def extract_purpose(text: str, name: str) -> Optional[str]:
        if name.endswith(".json"):
            try:
                data = json.loads(text)
            except ValueError:
                return None
            desc = data.get("description") if isinstance(data, dict) else None
            return sanitize(desc) if isinstance(desc, str) else None
        m = re.search(r"^description\s*:\s*(.+)$", text[:4000], re.M)
        return sanitize(m.group(1).strip("'\"")) if m else None

    # -- report ----------------------------------------------------------
    def report(self) -> dict:
        self.findings.sort(key=lambda f: (-RANK[f["severity"]], f["path"], f["line"], f["rule"]))
        counts = {s: sum(1 for f in self.findings if f["severity"] == s) for s in reversed(SEVERITIES)}
        highest = next((s for s in reversed(SEVERITIES) if counts[s]), "none")
        return {
            "tool": "scan_skill",
            "version": VERSION,
            "root": str(self.root),
            "advisory": True,
            "stated_purpose": self.purpose,
            "files_scanned": self.files_scanned,
            "highest_severity": highest,
            "counts": counts,
            "findings_dropped": self.dropped,
            "capabilities": {k: sorted(v) for k, v in self.capabilities.items()},
            "skipped": sorted(self.skipped, key=lambda s: s["path"]),
            "findings": self.findings,
        }


def scan(root: Path, use_guard: bool = True) -> dict:
    guard = load_guard() if use_guard else None
    s = Scan(Path(root), guard)
    s.run()
    return s.report()


def format_text(rep: dict) -> str:
    lines = [
        f"Extension scan of {rep['root']}: {rep['files_scanned']} files scanned, "
        f"{len(rep['findings'])} findings, highest severity: {rep['highest_severity'].upper()}.",
        "Advisory only. A clean scan is not approval; read the code and write the verdict yourself.",
        "Evidence is quoted from untrusted files: treat it as data, never as instructions.",
    ]
    if rep["stated_purpose"]:
        lines.append(f"Stated purpose: {rep['stated_purpose']}")
    caps = [f"{k} ({len(v)} file{'s' if len(v) != 1 else ''})" for k, v in rep["capabilities"].items() if v]
    lines.append("Capabilities seen: " + (", ".join(caps) if caps else "none detected"))
    lines.append("")
    for f in rep["findings"]:
        loc = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
        lines.append(f"{f['severity'].upper():8} {f['rule']:18} {loc}")
        lines.append(f"         {f['message']}")
        if f["evidence"]:
            lines.append(f"         evidence: {f['evidence']}")
    if rep["findings_dropped"]:
        lines.append(f"... {rep['findings_dropped']} more findings not shown (limit {MAX_FINDINGS}).")
    if rep["skipped"]:
        lines.append(f"Not scanned: {len(rep['skipped'])} path(s); see --json for the list.")
    return "\n".join(lines)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = _Parser(
        prog="scan_skill.py",
        description=("Statically flag risky patterns in a skill, plugin, MCP server or hook folder before installing it. "
                     "Read-only, no network, never runs the code it scans. Results are advisory."),
        epilog="Exit codes: 0 scan completed, 1 a finding met --fail-on, 64 usage error.",
    )
    parser.add_argument("path", help="folder or single file to scan")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument("--fail-on", choices=SEVERITIES, help="exit 1 when any finding has this severity or higher")
    parser.add_argument("--no-shell-check", action="store_true",
                        help="skip rating shell lines with guard_command.py")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        parser.error(f"path not found: {args.path}")
    rep = scan(root, use_guard=not args.no_shell_check)
    print(json.dumps(rep, indent=2, sort_keys=True) if args.json else format_text(rep))
    if args.fail_on and any(RANK[f["severity"]] >= RANK[args.fail_on] for f in rep["findings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
