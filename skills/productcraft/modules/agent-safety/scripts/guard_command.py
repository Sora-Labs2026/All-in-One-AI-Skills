#!/usr/bin/env python3
"""ProductCraft Agent Safety command guard.

Reads a proposed shell command and returns ALLOW, ASK or DENY with a reason and
a safer alternative. Input is either a command argument, plain text on stdin,
or a Claude Code PreToolUse hook payload (JSON) on stdin.

This is a seatbelt, not a sandbox. It reads the command text statically and
never runs it. It cannot see inside scripts, aliases, package scripts or
programs the command starts, and a determined process can always get around
it. Use it together with the agent's own permission rules and, for real
isolation, a container, VM or throwaway account.

Python 3 standard library only. No network. The only filesystem access is an
optional read of `.git/HEAD` to learn the current branch for `git push`.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlsplit

VERSION = "1.1.0"
ALLOW, ASK, DENY = "allow", "ask", "deny"
RANK = {ALLOW: 0, ASK: 1, DENY: 2}
EXIT_CODES = {ALLOW: 0, ASK: 1, DENY: 2}
MAX_INPUT = 64 * 1024
MAX_DEPTH = 4

DEFAULT_PROTECTED = frozenset({
    "main", "master", "trunk", "develop", "development", "production", "prod",
    "staging", "stable", "release", "live", "gh-pages",
})


# --------------------------------------------------------------------------
# Results


@dataclass
class Finding:
    decision: str
    rule: str
    reason: str
    safer: str = ""
    prod_sensitive: bool = False


@dataclass
class Result:
    decision: str
    findings: List[Finding]

    def to_dict(self) -> dict:
        return {
            "tool": "guard_command",
            "version": VERSION,
            "decision": self.decision,
            "findings": [
                {"decision": f.decision, "rule": f.rule, "reason": f.reason, "safer": f.safer}
                for f in self.findings
            ],
        }

    def summary(self) -> str:
        if not self.findings:
            return "No guard rule matched."
        top = [f for f in self.findings if f.decision == self.decision] or self.findings
        parts = []
        for f in top[:3]:
            text = f"[{f.rule}] {f.reason}"
            if f.safer:
                text += f" Safer: {f.safer}"
            parts.append(text)
        return " | ".join(parts)


def combine(findings: List[Finding]) -> Result:
    decision = ALLOW
    for f in findings:
        if RANK[f.decision] > RANK[decision]:
            decision = f.decision
    ordered = sorted(findings, key=lambda f: -RANK[f.decision])
    # Drop exact duplicates while keeping order.
    seen, unique = set(), []
    for f in ordered:
        key = (f.decision, f.rule, f.reason)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return Result(decision, unique)


# --------------------------------------------------------------------------
# Tokenizer: a small POSIX-shell lexer that keeps enough structure for
# classification (words, operators, redirects, heredocs, substitutions).


class ParseError(ValueError):
    pass


@dataclass
class Word:
    text: str = ""
    quoted: bool = False
    dynamic: bool = False
    glob: bool = False
    subs: List[str] = field(default_factory=list)


@dataclass
class Redirect:
    op: str
    fd: Optional[str] = None
    target: Optional[Word] = None
    body: Optional[str] = None


@dataclass
class Command:
    words: List[Word]
    redirects: List[Redirect]
    pipeline: int
    position: int
    pipe_out: bool = False


_WORD_END = set(" \t\r\n;&|()<>")


class _Lexer:
    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0
        self.n = len(text)
        self.tokens: list = []
        self.pending: List[Tuple[Redirect, str, bool]] = []

    def run(self) -> list:
        s = self.s
        while self.i < self.n:
            c = s[self.i]
            if c in " \t\r":
                self.i += 1
            elif c == "\n":
                self.i += 1
                self.tokens.append(("op", ";"))
                self._read_heredocs()
            elif c == "#":
                while self.i < self.n and s[self.i] != "\n":
                    self.i += 1
            elif s.startswith("\\\n", self.i):
                self.i += 2
            elif s.startswith("&>", self.i):
                self._read_redirect(None)
            elif c in ";&|()":
                self._read_operator()
            elif c in "<>" and not s.startswith("<(", self.i) and not s.startswith(">(", self.i):
                self._read_redirect(None)
            else:
                word = self._read_word()
                if (word.text.isdigit() and not word.quoted and self.i < self.n
                        and s[self.i] in "<>" and not s.startswith("<(", self.i)
                        and not s.startswith(">(", self.i)):
                    self._read_redirect(word.text)
                else:
                    self.tokens.append(word)
        for redir, _delim, _strip in self.pending:
            redir.body = ""
        return self.tokens

    def _read_operator(self) -> None:
        for op in ("&&", "||", ";;", "|&"):
            if self.s.startswith(op, self.i):
                self.i += 2
                self.tokens.append(("op", op))
                return
        self.tokens.append(("op", self.s[self.i]))
        self.i += 1

    def _skip_blanks(self) -> None:
        while self.i < self.n and self.s[self.i] in " \t":
            self.i += 1

    def _read_redirect(self, fd: Optional[str]) -> None:
        for op in ("&>>", "<<<", "<<-", "&>", "<<", ">>", ">|", ">&", "<&", "<>", ">", "<"):
            if self.s.startswith(op, self.i):
                self.i += len(op)
                break
        else:  # pragma: no cover - guarded by caller
            raise ParseError("bad redirect")
        redir = Redirect(op=op, fd=fd)
        self._skip_blanks()
        if self.i >= self.n or self.s[self.i] in "\n;&|()<>":
            raise ParseError(f"redirect {op} has no target")
        word = self._read_word()
        if op in ("<<", "<<-"):
            redir.target = word
            self.pending.append((redir, word.text, op == "<<-"))
        elif op in (">&", "<&") and (word.text.isdigit() or word.text == "-"):
            redir.target = None
        elif op == "<<<":
            redir.target = word
            redir.body = word.text
        else:
            redir.target = word
        self.tokens.append(redir)

    def _read_heredocs(self) -> None:
        for redir, delim, strip_tabs in self.pending:
            lines = []
            while self.i < self.n:
                nl = self.s.find("\n", self.i)
                end = self.n if nl == -1 else nl
                line = self.s[self.i:end]
                self.i = self.n if nl == -1 else nl + 1
                check = line.lstrip("\t") if strip_tabs else line
                if check == delim:
                    break
                lines.append(line)
            redir.body = "\n".join(lines)
        self.pending = []

    def _capture_parens(self) -> str:
        """self.i points at '('. Returns inner text and moves past the matching ')'."""
        s, depth, start = self.s, 0, self.i
        j = self.i
        while j < self.n:
            c = s[j]
            if c == "\\":
                j += 2
                continue
            if c == "'":
                k = s.find("'", j + 1)
                if k == -1:
                    raise ParseError("unterminated quote in substitution")
                j = k + 1
                continue
            if c == '"':
                j = self._skip_dq(j + 1)
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    self.i = j + 1
                    return s[start + 1:j]
            j += 1
        raise ParseError("unterminated substitution")

    def _skip_dq(self, j: int) -> int:
        s = self.s
        while j < self.n:
            if s[j] == "\\":
                j += 2
                continue
            if s[j] == '"':
                return j + 1
            j += 1
        raise ParseError("unterminated double quote")

    def _read_backtick(self, word: Word) -> None:
        s, j = self.s, self.i + 1
        buf = []
        while j < self.n:
            if s[j] == "\\" and j + 1 < self.n:
                buf.append(s[j + 1])
                j += 2
                continue
            if s[j] == "`":
                inner = "".join(buf)
                word.subs.append(inner)
                word.text += "`" + inner + "`"
                word.dynamic = True
                self.i = j + 1
                return
            buf.append(s[j])
            j += 1
        raise ParseError("unterminated backtick")

    def _read_dollar(self, word: Word, in_dq: bool) -> None:
        s, i = self.s, self.i
        nxt = s[i + 1] if i + 1 < self.n else ""
        if s.startswith("$((", i):
            self.i = i + 1
            inner = self._capture_parens()
            word.text += "$(" + inner + ")"
            word.dynamic = True
        elif nxt == "(":
            self.i = i + 1
            inner = self._capture_parens()
            word.subs.append(inner)
            word.text += "$(" + inner + ")"
            word.dynamic = True
        elif nxt == "{":
            depth, j = 0, i + 1
            while j < self.n:
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            else:
                raise ParseError("unterminated ${")
            word.text += s[i:j + 1]
            word.dynamic = True
            self.i = j + 1
        elif nxt == "'" and not in_dq:
            k = s.find("'", i + 2)
            if k == -1:
                raise ParseError("unterminated $'")
            raw = s[i + 2:k]
            if re.search(r"\\(x|u|U|[0-7])", raw):
                word.dynamic = True
            word.text += raw.replace("\\n", "\n").replace("\\t", "\t").replace("\\'", "'").replace("\\\\", "\\")
            word.quoted = True
            self.i = k + 1
        elif nxt and (nxt.isalnum() or nxt == "_"):
            j = i + 1
            if nxt.isdigit():
                j += 1
            else:
                while j < self.n and (s[j].isalnum() or s[j] == "_"):
                    j += 1
            word.text += s[i:j]
            word.dynamic = True
            self.i = j
        elif nxt and nxt in "@*#?$!-":
            word.text += s[i:i + 2]
            word.dynamic = True
            self.i = i + 2
        else:
            word.text += "$"
            self.i = i + 1

    def _read_word(self) -> Word:
        s = self.s
        word = Word()
        if s.startswith("<(", self.i) or s.startswith(">(", self.i):
            prefix = s[self.i]
            self.i += 1
            inner = self._capture_parens()
            word.subs.append(inner)
            word.text = prefix + "(" + inner + ")"
            word.dynamic = True
            return word
        while self.i < self.n:
            c = s[self.i]
            if c in _WORD_END:
                break
            if c == "'":
                k = s.find("'", self.i + 1)
                if k == -1:
                    raise ParseError("unterminated single quote")
                word.text += s[self.i + 1:k]
                word.quoted = True
                self.i = k + 1
            elif c == '"':
                word.quoted = True
                self.i += 1
                while True:
                    if self.i >= self.n:
                        raise ParseError("unterminated double quote")
                    d = s[self.i]
                    if d == '"':
                        self.i += 1
                        break
                    if d == "\\" and self.i + 1 < self.n:
                        e = s[self.i + 1]
                        if e in '"\\$`':
                            word.text += e
                        elif e != "\n":
                            word.text += "\\" + e
                        self.i += 2
                    elif d == "$":
                        self._read_dollar(word, in_dq=True)
                    elif d == "`":
                        self._read_backtick(word)
                    else:
                        word.text += d
                        self.i += 1
            elif c == "\\":
                if self.i + 1 < self.n:
                    if s[self.i + 1] != "\n":
                        word.text += s[self.i + 1]
                        word.quoted = True
                    self.i += 2
                else:
                    word.text += "\\"
                    self.i += 1
            elif c == "$":
                self._read_dollar(word, in_dq=False)
            elif c == "`":
                self._read_backtick(word)
            else:
                if c in "*?[{":
                    word.glob = True
                word.text += c
                self.i += 1
        return word


def tokenize(text: str) -> list:
    return _Lexer(text).run()


KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time", "fi", "done", "esac", "coproc"}
SKIP_COMMANDS = {"for", "case", "select", "function", "in"}


def parse(tokens: list) -> list:
    """Group tokens into Command objects plus 'push'/'pop' markers for subshells."""
    items: list = []
    words: List[Word] = []
    redirects: List[Redirect] = []
    pipeline, position = 0, 0

    def finish(pipe_out: bool) -> None:
        nonlocal words, redirects
        while words and not words[0].quoted and words[0].text in KEYWORDS:
            words.pop(0)
        if words and not words[0].quoted and words[0].text in SKIP_COMMANDS:
            words = []
        if words or redirects:
            items.append(Command(words, redirects, pipeline, position, pipe_out))
        words, redirects = [], []

    for tok in tokens:
        if isinstance(tok, Word):
            words.append(tok)
        elif isinstance(tok, Redirect):
            redirects.append(tok)
        else:
            op = tok[1]
            if op in ("|", "|&"):
                finish(True)
                position += 1
            elif op in ("(", ")"):
                finish(False)
                items.append("push" if op == "(" else "pop")
                pipeline += 1
                position = 0
            else:
                finish(False)
                pipeline += 1
                position = 0
    finish(False)
    return items


# --------------------------------------------------------------------------
# Paths


TEMP_DEFAULTS = ("/tmp", "/var/tmp", "/private/tmp", "/private/var/folders", "/var/folders")
SYSTEM_DIRS = (
    "/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/libx32", "/opt", "/proc",
    "/root", "/run", "/sbin", "/srv", "/sys", "/usr", "/var", "/snap", "/nix", "/System",
    "/Library", "/Applications", "/private", "/cores", "/home", "/Users",
)
CREDENTIAL_DIRS = (
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store",
    ".config/gcloud", ".config/gh", ".claude", ".local/share/keyrings", "Library/Keychains",
)


def norm(path: str) -> str:
    p = posixpath.normpath(path)
    if p.startswith("//"):
        p = "/" + p.lstrip("/")
    return p


def is_under(path: str, root: Optional[str]) -> bool:
    if not root:
        return False
    return path == root or path.startswith(root.rstrip("/") + "/")


@dataclass
class Context:
    cwd: Optional[str]
    project_root: Optional[str]
    home: str
    temp_roots: Tuple[str, ...]
    protected: frozenset = DEFAULT_PROTECTED
    read_git_head: bool = True


def make_context(cwd: Optional[str] = None, project_root: Optional[str] = None,
                 home: Optional[str] = None, protected: Optional[frozenset] = None,
                 read_git_head: bool = True) -> Context:
    home = norm(home or os.path.expanduser("~"))
    cwd = norm(cwd) if cwd else norm(os.getcwd())
    proj = norm(project_root) if project_root else cwd
    # A "project" equal to /, the home folder or one of its ancestors is no
    # boundary at all, so treat the project as unknown.
    if proj == "/" or proj == home or is_under(home, proj):
        proj = None
    temps = set(TEMP_DEFAULTS)
    for candidate in (os.environ.get("TMPDIR"), tempfile.gettempdir()):
        if candidate:
            temps.add(norm(candidate))
    temps.discard("/")
    return Context(cwd=cwd, project_root=proj, home=home,
                   temp_roots=tuple(sorted(temps)),
                   protected=protected or DEFAULT_PROTECTED,
                   read_git_head=read_git_head)


_PREFIXES = (
    ("$HOME", "home"), ("${HOME}", "home"), ("$PWD", "cwd"), ("${PWD}", "cwd"),
    ("$(pwd)", "cwd"), ("`pwd`", "cwd"), ("$TMPDIR", "tmp"), ("${TMPDIR}", "tmp"),
)


@dataclass
class Target:
    kind: str                 # "path" | "dynamic" | "unknown" | "empty"
    path: Optional[str] = None
    glob: str = ""            # "" | "all" (match-everything) | "some" (filtered)


def resolve(word: Word, ctx: Context, cwd: Optional[str]) -> Target:
    text = word.text
    if not text:
        return Target("dynamic") if word.dynamic else Target("empty")
    base_kind = None
    rest = text
    if text == "~" or text.startswith("~/"):
        base_kind, rest = "home", text[1:]
    elif text.startswith("~") and not word.quoted:
        user = re.match(r"~([A-Za-z0-9._-]+)", text)
        if user:
            return Target("path", norm(posixpath.join(posixpath.dirname(ctx.home), user.group(1))
                                       + text[user.end():]))
    else:
        for prefix, kind in _PREFIXES:
            if text == prefix or text.startswith(prefix + "/"):
                base_kind, rest = kind, text[len(prefix):]
                break
    if "$" in rest or "`" in rest or (word.dynamic and base_kind is None):
        return Target("dynamic")
    if base_kind == "home":
        full = ctx.home + rest
    elif base_kind == "cwd":
        if cwd is None:
            return Target("unknown")
        full = cwd + rest
    elif base_kind == "tmp":
        full = (os.environ.get("TMPDIR") or "/tmp") + rest
    elif rest.startswith("/"):
        full = rest
    else:
        if cwd is None:
            return Target("unknown")
        full = posixpath.join(cwd, rest) if rest else cwd
    glob = ""
    if word.glob and re.search(r"[*?\[{]", full):
        parts = full.split("/")
        for idx, part in enumerate(parts):
            if re.search(r"[*?\[{]", part):
                base = "/".join(parts[:idx]) or "/"
                later = parts[idx:]
                match_all = len(later) == 1 and part in ("*", ".*", "*.*", ".[!.]*", "{*,.*}", "{.*,*}", "**")
                return Target("path", norm(base), "all" if match_all else "some")
    return Target("path", norm(full), glob)


def classify(path: str, ctx: Context) -> str:
    """Return a location class for an absolute normalized path."""
    home, proj = ctx.home, ctx.project_root
    if path == "/":
        return "root"
    if path == home:
        return "home"
    if is_under(home, path) or (proj and is_under(proj, path) and path != proj):
        return "ancestor"
    in_temp = any(is_under(path, t) for t in ctx.temp_roots)
    if "/.git/" in path + "/" and (is_under(path, proj) or not in_temp):
        return "gitdir"
    if proj and path == proj:
        return "project_root"
    if is_under(path, proj):
        return "project"
    if path in ctx.temp_roots:
        return "temp_root"
    if in_temp:
        return "temp"
    for cred in CREDENTIAL_DIRS:
        if is_under(path, home + "/" + cred):
            return "credential"
    if is_under(path, home):
        return "home_child"
    for sysdir in SYSTEM_DIRS:
        if is_under(path, sysdir):
            return "system"
    return "outside"


CATASTROPHIC = {"root", "home", "ancestor", "system", "credential"}


# --------------------------------------------------------------------------
# Secrets


TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".tmpl", ".defaults", ".schema")
KEY_BASENAMES = {
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "id_ecdsa_sk", "id_ed25519_sk",
    ".netrc", "_netrc", ".git-credentials", ".pgpass", "wallet.dat", "key4.db", "logins.json",
}
KEY_EXTENSIONS = (".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx", ".ppk", ".p8")
ENV_BASENAMES = {".envrc", ".npmrc", ".pypirc", ".htpasswd", ".dev.vars", "local.settings.json", "credentials.json"}
BROWSER_HINTS = ("Chrome", "Chromium", "BraveSoftware", "Firefox", ".mozilla", "Microsoft Edge", "Vivaldi")


def secret_class(path: str) -> Optional[str]:
    """'key' for private keys and credential stores, 'env' for dotenv-style files, else None."""
    p = path.replace("\\", "/").rstrip("/")
    base = posixpath.basename(p)
    lower = base.lower()
    if not base:
        return None
    if lower.endswith(".pub") or lower.endswith(TEMPLATE_SUFFIXES):
        return None
    if lower in KEY_BASENAMES:
        return "key"
    if lower.endswith(KEY_EXTENSIONS):
        return "key"
    if lower.endswith(".pem") and ("key" in lower or "priv" in lower):
        return "key"
    segs = "/" + p + "/"
    if "/.ssh/" in segs:
        if lower in ("known_hosts", "known_hosts.old", "authorized_keys", "config"):
            return None
        return "key"
    if "/.aws/" in segs:
        return "env" if lower == "config" else "key"
    for marker in ("/.gnupg/", "/.config/gcloud/", "/.azure/", "/.password-store/",
                   "/.local/share/keyrings/", "/Library/Keychains/"):
        if marker in segs:
            return "key"
    if (segs.endswith("/.kube/config/") or segs.endswith("/.docker/config.json/")
            or segs.endswith("/.config/gh/hosts.yml/") or segs.endswith("/.claude/.credentials.json/")):
        return "key"
    if base in ("Login Data", "Cookies", "Web Data") and any(h in p for h in BROWSER_HINTS):
        return "key"
    if lower == ".env" or lower.startswith(".env.") or (lower.endswith(".env") and len(lower) > 4):
        return "env"
    if lower in ENV_BASENAMES:
        return "env"
    if re.fullmatch(r"secrets?\.(json|ya?ml|toml|env|ini)", lower):
        return "env"
    if re.match(r"(client_secret|service[-_]?account)[^/]*\.json$", lower):
        return "env"
    if lower.endswith((".tfstate", ".tfstate.backup", ".tfvars")):
        return "env"
    return None


SECRET_VAR = re.compile(
    r"(?:^|_)(SECRET|TOKEN|PASSWORD|PASSWD|PASSPHRASE|PRIVATE|CREDENTIALS?|APIKEY|API_KEY|ACCESS_KEY|AUTH|PAT|"
    r"DATABASE_URL|DB_URL|CONNECTION_STRING|DSN|COOKIE|SESSION_KEY|SIGNING_KEY)(?:_|$)")


def secret_var_refs(text: str) -> List[str]:
    names = []
    for m in re.finditer(r"\$(\{)?(#)?([A-Za-z_][A-Za-z0-9_]*)(:?[+])?", text):
        brace, length, name, plus = m.group(1), m.group(2), m.group(3), m.group(4)
        if length or (brace and plus):
            continue  # ${#VAR} and ${VAR:+set} reveal nothing
        if SECRET_VAR.search(name.upper()):
            names.append(name)
    return names


READERS = {
    "cat", "tac", "less", "more", "most", "head", "tail", "bat", "batcat", "nl", "view",
    "strings", "xxd", "hexdump", "od", "base64", "base32", "uuencode", "sed", "awk", "gawk",
    "mawk", "grep", "egrep", "fgrep", "rg", "ag", "ack", "cut", "sort", "uniq", "diff",
    "comm", "jq", "yq", "column", "fold", "fmt", "pr", "iconv", "openssl", "gpg", "pbcopy",
    "xclip", "xsel", "paste", "rev", "tr", "zcat", "vimdiff",
}
COPIERS = {"cp", "mv", "rsync", "tar", "zip", "7z", "gzip", "bzip2", "xz", "install", "ln", "dd", "ditto"}
METADATA = {
    "ls", "stat", "test", "[", "[[", "file", "wc", "du", "touch", "mkdir", "realpath",
    "readlink", "basename", "dirname", "chmod", "chown", "chgrp", "lsattr", "getfacl",
    "shasum", "sha256sum", "sha1sum", "md5sum", "md5", "b2sum", "cksum", "rm", "shred",
    "unlink", "source", ".", "export", "set", "echo", "printf", "true", "false", "type", "which",
    "find", "fd", "tree", "ssh-keyscan",
}
KEY_USERS = {"ssh", "ssh-add", "ssh-keygen", "ssh-copy-id", "sftp", "scp", "sshfs", "mosh", "autossh", "git"}


def _grep_metadata_only(args: List[str]) -> bool:
    for a in args:
        if a in ("--files-with-matches", "--files-without-match", "--count", "--quiet", "--silent", "--files"):
            return True
        if re.fullmatch(r"-[A-Za-z]*[lLcq][A-Za-z]*", a) and not a.startswith("--"):
            return True
    return False


def _names_only_cut(args: List[str]) -> bool:
    joined = " ".join(args)
    return bool(re.search(r"(-d\s*['\"]?=['\"]?|--delimiter=?['\"]?=)", joined)) and bool(
        re.search(r"(-f\s*1\b|--fields=1\b)", joined))


# --------------------------------------------------------------------------
# Command tables

SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "mksh", "ash", "fish"}
INTERPRETERS = {
    "python": ("-c",), "python2": ("-c",), "python3": ("-c",), "pypy3": ("-c",),
    "node": ("-e", "--eval", "-p", "--print"), "bun": ("-e", "--eval"), "deno": ("eval",),
    "perl": ("-e", "-E"), "ruby": ("-e",), "php": ("-r",), "lua": ("-e",),
}
STDIN_INTERPRETERS = {"python", "python2", "python3", "pypy3", "node", "perl", "ruby", "php", "pwsh", "powershell", "lua"}
AWKS = {"awk", "gawk", "mawk", "nawk"}
PARALLEL_SEPARATORS = {":::", "::::", ":::+", "::::+"}
PARALLEL_VALUE_OPTS = {"-j", "-P", "-S", "-a", "-d", "-n", "-N", "-L", "--jobs", "--sshlogin", "--sshloginfile",
                       "--arg-file", "--delimiter", "--max-args", "--max-lines", "--colsep", "--joblog", "--results",
                       "--tmpdir", "--workdir", "--wd", "--halt", "--delay", "--timeout", "--retries", "--block",
                       "--memfree", "--load", "--tagstring", "--basefile", "--bf", "--env"}
PARALLEL_PLACEHOLDER = r"\{\d*(?:\.|/|//|/\.)?\}|\{[#%]\}"
DOWNLOADERS = {"curl", "wget", "fetch", "http", "https", "xh", "aria2c", "lwp-request", "httpie"}
DB_CLIENTS = {
    "psql", "mysql", "mariadb", "sqlite3", "sqlcmd", "mongosh", "mongo", "redis-cli",
    "clickhouse-client", "clickhouse", "cockroach", "duckdb", "snowsql", "bq", "cqlsh",
    "turso", "wrangler", "supabase", "prisma", "pgcli", "mycli", "litecli", "usql",
}
CLOUD_CLIS = {
    "aws", "gcloud", "gsutil", "az", "kubectl", "helm", "doctl", "fly", "flyctl", "heroku",
    "vercel", "netlify", "firebase", "supabase", "pulumi", "terraform", "tofu", "terragrunt",
    "cdk", "serverless", "sls", "wrangler", "railway", "oci", "hcloud", "linode-cli", "scw",
    "eb", "ibmcloud", "gh", "glab", "aliyun", "vultr-cli", "exo", "render", "koyeb",
    "neonctl", "planetscale", "pscale", "atlas", "upstash",
}
DELETE_WORDS = {
    "delete", "destroy", "remove", "rm", "rb", "terminate", "purge", "drop", "uninstall",
    "teardown", "wipe", "deregister", "nuke", "prune", "erase", "reset", "unpublish",
}
DEPLOY = {
    "npm": {"publish", "unpublish", "deprecate"}, "pnpm": {"publish"}, "yarn": {"publish"},
    "bun": {"publish"}, "cargo": {"publish", "yank"}, "twine": {"upload"}, "gem": {"push", "yank"},
    "poetry": {"publish"}, "uv": {"publish"}, "flit": {"publish"}, "hatch": {"publish"},
    "docker": {"push"}, "podman": {"push"}, "vsce": {"publish"}, "ovsx": {"publish"},
    "terraform": {"apply", "import"}, "tofu": {"apply", "import"}, "terragrunt": {"apply"},
    "pulumi": {"up", "update"}, "cdk": {"deploy"}, "serverless": {"deploy"}, "sls": {"deploy"},
    "wrangler": {"deploy", "publish"}, "netlify": {"deploy"}, "firebase": {"deploy"},
    "fly": {"deploy"}, "flyctl": {"deploy"}, "kubectl": {"apply", "create", "replace", "patch", "scale"},
    "helm": {"install", "upgrade", "rollback"}, "gcloud": {"deploy"}, "eb": {"deploy"},
    "railway": {"up"}, "vercel": {"deploy", "--prod", "promote"},
}
POWER = {"shutdown", "reboot", "halt", "poweroff", "init", "telinit"}
DISK_TOOLS = {"wipefs", "sfdisk", "cfdisk", "gdisk", "sgdisk", "blkdiscard", "mkswap"}
PROD_RE = re.compile(r"(?i)(?:^|[^a-z0-9])(prod|production|prd)(?:[^a-z0-9]|$)")
LOCAL_HOSTS = re.compile(r"^(localhost|127(\.\d+){3}|0\.0\.0\.0|\[?::1\]?|host\.docker\.internal|[a-z0-9.-]+\.localhost)$", re.I)
WRITE_OPS = {">", ">>", ">|", "&>", "&>>", "<>"}
DEV_SAFE = re.compile(r"^/dev/(null|zero|stdout|stderr|stdin|tty|random|urandom|fd/\d+|shm/.*)$")
DEV_DISK = re.compile(r"^/dev/(sd[a-z]|hd[a-z]|vd[a-z]|xvd[a-z]|nvme\d|mmcblk\d|disk\d|rdisk\d|md\d|dm-\d|mapper/|loop\d)")


def is_config_target(path: str, ctx: Context) -> bool:
    """Agent settings, shell startup files, SSH access files, git hooks, autostart locations."""
    base = posixpath.basename(path)
    segs = path + "/"
    if re.search(r"/\.claude/(settings[^/]*\.json|hooks/)", segs) or is_under(path, ctx.home + "/.claude"):
        return True
    if base in (".mcp.json", ".claude.json", "CLAUDE.md", "AGENTS.md") and not is_under(path, ctx.project_root):
        return True
    if base in (".bashrc", ".bash_profile", ".bash_login", ".profile", ".zshrc", ".zprofile",
                ".zshenv", ".zlogin", "config.fish", "authorized_keys") or segs.endswith("/.ssh/config/"):
        return True
    if "/.git/hooks/" in segs or segs.endswith("/.git/config/"):
        return True
    for marker in ("/Library/LaunchAgents/", "/Library/LaunchDaemons/", "/.config/autostart/",
                   "/.config/systemd/", "/etc/cron", "/etc/systemd/"):
        if marker in segs:
            return True
    return False


# --------------------------------------------------------------------------
# Analysis


@dataclass
class State:
    cwd: Optional[str]
    depth: int
    pipeline: List[Command]
    earlier: List[Tuple[str, List[str]]]
    position: int = 0


def _f(decision: str, rule: str, reason: str, safer: str = "", prod: bool = False) -> Finding:
    return Finding(decision, rule, reason, safer, prod)


def _basename(text: str) -> str:
    return posixpath.basename(text) if "/" in text else text


def _strip_version(pkg: str) -> str:
    if pkg.startswith("@"):
        scope_end = pkg.find("/")
        at = pkg.find("@", scope_end + 1 if scope_end != -1 else 1)
        return pkg[:at] if at > 0 else pkg
    return re.split(r"[@=<>]", pkg, maxsplit=1)[0]


def unwrap(words: List[Word], findings: List[Finding]) -> Tuple[List[Word], bool, bool]:
    """Strip assignments and transparent wrappers. Returns (words, dynamic_args, env_dump)."""
    dynamic_args = False
    for _ in range(12):
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*\+?=", words[0].text) and not words[0].quoted:
            words = words[1:]
        if not words:
            return words, dynamic_args, False
        name = _basename(words[0].text)
        rest = words[1:]
        if name in ("sudo", "doas", "pkexec", "run0"):
            findings.append(_f(ASK, "PRIV-ESCALATION", f"Runs with elevated privileges ({name}).",
                               "Ask the user first; prefer a user-level install or a project-local tool."))
            i = 0
            while i < len(rest) and rest[i].text.startswith("-"):
                if rest[i].text == "--":
                    i += 1
                    break
                if rest[i].text in ("-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U", "--user", "--group"):
                    i += 1
                i += 1
            words = rest[i:]
            if not words:
                return words, dynamic_args, False
            continue
        if name == "env":
            i = 0
            while i < len(rest):
                t = rest[i].text
                if t in ("-u", "--unset", "-C", "--chdir", "-S", "--split-string"):
                    i += 2
                    continue
                if t.startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
                    i += 1
                    continue
                break
            if i >= len(rest):
                return [], dynamic_args, True
            words = rest[i:]
            continue
        if name in ("command", "builtin", "exec", "nohup", "time", "setsid", "unbuffer", "chronic", "caffeinate"):
            if name == "command" and rest and rest[0].text in ("-v", "-V"):
                return [], dynamic_args, False
            i = 0
            while i < len(rest) and rest[i].text.startswith("-"):
                i += 1
            words = rest[i:]
            continue
        if name in ("nice", "ionice", "timeout", "stdbuf", "chrt", "taskset"):
            i = 0
            while i < len(rest) and rest[i].text.startswith("-"):
                if rest[i].text in ("-n", "-c", "-s", "-k", "-o", "-e", "-i", "--signal", "--kill-after"):
                    i += 1
                i += 1
            if name in ("timeout", "chrt", "taskset") and i < len(rest):
                i += 1  # duration / priority / mask
            words = rest[i:]
            continue
        if name == "xargs":
            i = 0
            while i < len(rest) and rest[i].text.startswith("-"):
                if rest[i].text in ("-I", "-L", "-n", "-P", "-d", "-E", "-s", "-a", "--max-args", "--max-procs"):
                    i += 1
                i += 1
            words = rest[i:]
            dynamic_args = True
            if not words:
                return words, dynamic_args, False
            continue
        if name in ("npx", "bunx", "pnpx", "uvx") or (
                name in ("pnpm", "yarn", "bun") and rest and rest[0].text in ("dlx", "exec", "x")) or (
                name == "pipx" and rest and rest[0].text == "run"):
            if name in ("pnpm", "yarn", "bun", "pipx"):
                rest = rest[1:]
            i = 0
            while i < len(rest) and rest[i].text.startswith("-"):
                if rest[i].text in ("-p", "--package", "--from", "--spec"):
                    i += 1
                i += 1
            if i >= len(rest):
                return [], dynamic_args, False
            pkg = Word(text=_strip_version(rest[i].text))
            words = [pkg] + rest[i + 1:]
            continue
        break
    return words, dynamic_args, False


def analyze_text(text: str, ctx: Context, cwd: Optional[str], depth: int) -> List[Finding]:
    findings: List[Finding] = []
    if depth > MAX_DEPTH:
        return [_f(ASK, "PARSE-LIMIT", "Command nests shells or substitutions too deeply to check.",
                   "Split it into plain, separate commands.")]
    if len(text) > MAX_INPUT:
        return [_f(ASK, "PARSE-LIMIT", "Command is too long to check.", "Split it into smaller commands.")]
    findings.extend(raw_checks(text))
    try:
        items = parse(tokenize(text))
    except ParseError as exc:
        findings.append(_f(ASK, "PARSE-UNCLEAR", f"Command could not be parsed reliably ({exc}).",
                           "Rewrite it as a plain command with balanced quotes."))
        return findings
    pipelines: dict = {}
    for item in items:
        if isinstance(item, Command):
            pipelines.setdefault(item.pipeline, []).append(item)
    stack: List[Optional[str]] = []
    earlier: List[Tuple[str, List[str]]] = []
    for item in items:
        if item == "push":
            stack.append(cwd)
            continue
        if item == "pop":
            cwd = stack.pop() if stack else cwd
            continue
        state = State(cwd=cwd, depth=depth, pipeline=pipelines[item.pipeline], earlier=earlier, position=item.position)
        new_findings, cwd = analyze_command(item, ctx, state)
        findings.extend(new_findings)
        for w in item.words + [r.target for r in item.redirects if r.target is not None]:
            for sub in w.subs:
                findings.extend(analyze_text(sub, ctx, cwd, depth + 1))
        outputs = [x for r in item.redirects if r.op in WRITE_OPS and r.target is not None for x in ("-o", r.target.text)]
        earlier.append((item.words[0].text if item.words else "", [w.text for w in item.words] + outputs))
    return findings


def raw_checks(text: str) -> List[Finding]:
    out = []
    if re.search(r":\s*\(\s*\)\s*\{[^}]*:\s*\|\s*:\s*&[^}]*\}", text):
        out.append(_f(DENY, "PROC-FORK-BOMB", "Fork bomb: exhausts the process table and freezes the machine."))
    if re.search(r"/dev/(tcp|udp)/", text) and re.search(r"\b(ba|z|k)?sh\b[^|;&]*\s-i\b|\bexec\s+\d*<>", text):
        out.append(_f(DENY, "NET-REVERSE-SHELL", "Interactive shell wired to a network socket (reverse shell pattern)."))
    if re.search(r"(?i)\b(iex|invoke-expression)\b", text) and re.search(
            r"(?i)\b(iwr|irm|invoke-webrequest|invoke-restmethod|downloadstring|net\.webclient)\b", text):
        out.append(_f(DENY, "REMOTE-EXEC", "Downloads code and executes it in one step (PowerShell).",
                      "Download to a file, read it, verify its checksum, then run it with the user's OK."))
    return out


def analyze_command(cmd: Command, ctx: Context, st: State) -> Tuple[List[Finding], Optional[str]]:
    findings: List[Finding] = []
    cwd = st.cwd
    findings.extend(check_redirects(cmd, ctx, cwd))
    words, dynamic_args, env_dump = unwrap(list(cmd.words), findings)
    nxt = next((c for c in st.pipeline if c.position == cmd.position + 1), None) if cmd.pipe_out else None
    nxt_words = unwrap(list(nxt.words), [])[0] if nxt else []
    nxt_name = _basename(nxt_words[0].text) if nxt_words else ""
    if env_dump:
        findings.extend(check_env_dump("env", [], nxt_name, nxt))
        return findings, cwd
    if not words:
        return findings, cwd
    head = words[0]
    name = _basename(head.text)
    args = [w.text for w in words[1:]]
    arg_words = words[1:]

    if head.dynamic:
        if any(re.fullmatch(r"-[A-Za-z]*[rRf][A-Za-z]*|--force|--hard|--recursive", a) for a in args):
            findings.append(_f(ASK, "CMD-DYNAMIC", "The command name is computed at runtime and the flags look destructive.",
                               "Write the command name literally so it can be checked."))
        return findings, cwd

    if name in ("cd", "pushd"):
        return findings, change_dir(arg_words, ctx, cwd)

    handler = HANDLERS.get(name)
    if handler is not None:
        findings.extend(handler(name, arg_words, ctx, st, dynamic_args, nxt_name, nxt))
    if name.startswith("mkfs") or name.startswith("newfs") or name == "mke2fs":
        findings.append(_f(DENY, "DISK-DESTROY", f"{name} formats a filesystem and erases the device.",
                           "Never format disks from an agent session; the user must do this by hand."))
    if name in DISK_TOOLS:
        findings.append(_f(DENY, "DISK-DESTROY", f"{name} rewrites partition tables or erases block devices."))
    if name in ("fdisk", "parted") and not any(a in ("-l", "--list", "print") for a in args):
        findings.append(_f(DENY, "DISK-DESTROY", f"{name} edits disk partitions."))
    if name in CLOUD_CLIS:
        findings.extend(check_cloud(name, args))
    if name in DEPLOY or name in ("vercel", "netlify", "gh"):
        findings.extend(check_deploy(name, args))
    upstream = [" ".join(w.text for w in c.words) for c in st.pipeline if c.position < cmd.position]
    findings.extend(check_database(name, args, cmd, upstream))
    names_only_next = nxt_name == "cut" and _names_only_cut([w.text for w in nxt_words[1:]])
    if not names_only_next:  # "grep -v '^#' .env | cut -d= -f1" shows names only
        findings.extend(check_secret_args(name, args, ctx, cwd))
    if name in ("echo", "printf", "print"):
        refs = [r for a in arg_words for r in secret_var_refs(a.text)]
        if refs:
            findings.append(_f(ASK, "SECRET-PRINT", f"Prints the value of {', '.join(sorted(set(refs)))} into the session log.",
                               'Check presence without the value: echo "${NAME:+set}" or echo "${#NAME}".'))
    if name in ("printenv", "set", "export", "declare", "typeset"):
        findings.extend(check_env_dump(name, args, nxt_name, nxt))
    if name in INTERPRETERS:
        findings.extend(check_inline_code(name, words, ctx, cwd, st.depth))
    if name in AWKS:
        findings.extend(check_awk(arg_words, ctx, cwd, st.depth))
    if name == "parallel":
        findings.extend(check_parallel(arg_words, ctx, cwd, st.depth))
    stdin_bodies = [r.body for r in cmd.redirects if r.body and r.op in ("<<", "<<-", "<<<")]
    if (name in SHELLS or name in STDIN_INTERPRETERS) and any(
            r.op == "<<<" and r.target is not None and _fetches(r.target) for r in cmd.redirects):
        findings.append(_f(DENY, "REMOTE-EXEC", f"Feeds code downloaded from the network into {name}.",
                           "Download to a file, read it, verify a checksum, then run it with the user's OK."))
    if stdin_bodies and name in SHELLS and not any(
            a.startswith("-") and not a.startswith("--") and "c" in a[1:] for a in args):
        for body in stdin_bodies:  # a heredoc fed to a shell is a script, not data
            findings.extend(analyze_text(body, ctx, cwd, st.depth + 1))
    elif stdin_bodies and name in STDIN_INTERPRETERS and (not args or args == ["-"]):
        for body in stdin_bodies:
            findings.extend(inline_code_findings(name, body))
    findings.extend(check_write_targets(name, args, ctx, cwd))
    findings.extend(check_download_then_run(name, head.text, args, cmd, st))
    return findings, cwd


def change_dir(arg_words: List[Word], ctx: Context, cwd: Optional[str]) -> Optional[str]:
    targets = [w for w in arg_words if not w.text.startswith("-") or w.text == "-"]
    if not targets:
        return ctx.home
    t = targets[0]
    if t.text == "-":
        return None
    r = resolve(t, ctx, cwd)
    return r.path if r.kind == "path" and not r.glob else None


# ---- individual handlers ---------------------------------------------------


def _positional(arg_words: List[Word]) -> Tuple[List[Word], List[str]]:
    opts, pos, ended = [], [], False
    for w in arg_words:
        if not ended and w.text == "--":
            ended = True
            continue
        if not ended and w.text.startswith("-") and len(w.text) > 1:
            opts.append(w.text)
        else:
            pos.append(w)
    return pos, opts


def _del_rule(cls: str) -> str:
    return {"root": "DEL-ROOT-HOME", "home": "DEL-ROOT-HOME", "ancestor": "DEL-ROOT-HOME",
            "system": "DEL-SYSTEM", "credential": "DEL-CREDENTIALS", "gitdir": "DEL-GIT-HISTORY"}.get(cls, "DEL-OUTSIDE")


def _delete_decision(t: Target, ctx: Context, recursive: bool, what: str) -> Optional[Finding]:
    if t.kind == "empty":
        return None
    if t.kind == "dynamic":
        if recursive:
            return _f(ASK, "DEL-UNVERIFIED", f"{what} target depends on a variable or command output; if it is empty or wrong the delete can hit the wrong place.",
                      "Resolve the path first, print it, and delete the literal path inside the project.")
        return None
    if t.kind == "unknown":
        if recursive:
            return _f(ASK, "DEL-UNVERIFIED", f"{what} target is relative to a directory the guard cannot determine.",
                      "Use an absolute path inside the project or run from the project root.")
        return None
    cls = classify(t.path, ctx)
    label = t.path + ("/*" if t.glob == "all" else "/<pattern>" if t.glob == "some" else "")
    if t.glob == "some":
        if cls in ("credential", "gitdir"):
            return _f(DENY, _del_rule(cls), f"{what} removes entries in {label}, which holds credentials or repository history.")
        if cls in ("project_root", "project", "temp", "temp_root"):
            return None
        return _f(ASK, "DEL-OUTSIDE", f"{what} removes matching entries outside the project ({label}).",
                  "List the matches first (ls or find -print), then delete only the paths the user approved.")
    if not recursive:
        if cls in ("project", "temp", "project_root"):
            return None
        if cls in ("credential",):
            return _f(ASK, "DEL-KEY-FILE", f"{what} deletes a credential or key file ({label}).",
                      "Confirm with the user; keys cannot be recovered after deletion.")
        if cls == "gitdir":
            return _f(ASK, "DEL-GIT-INTERNAL", f"{what} deletes a file inside .git ({label}).",
                      "Prefer git commands; confirm before touching repository internals.")
        return _f(ASK, "DEL-OUTSIDE", f"{what} deletes a file outside the project ({label}).",
                  "Confirm the exact path with the user, or move it to a dated backup folder instead.")
    if t.glob == "all":
        if cls in CATASTROPHIC or cls == "gitdir":
            return _f(DENY, _del_rule(cls), f"{what} deletes everything in {label}.",
                      "Never run this from an agent session.")
        if cls == "project_root":
            return _f(ASK, "DEL-PROJECT-CONTENTS", f"{what} deletes every file in the project root ({label}).",
                      "Delete the specific build or cache folders instead, after git status shows nothing unsaved.")
        if cls in ("project", "temp"):
            return None
        return _f(ASK, "DEL-OUTSIDE", f"{what} deletes everything in {label}, outside the project.",
                  "Confirm the exact path with the user first.")
    if cls in CATASTROPHIC:
        return _f(DENY, _del_rule(cls), f"{what} deletes {label} ({cls.replace('_', ' ')}); this cannot be undone.",
                  "Never run this from an agent session. Delete specific paths inside the project instead.")
    if cls == "gitdir":
        return _f(DENY, "DEL-GIT-HISTORY", f"{what} deletes git internals ({label}); removing .git loses the commit history.",
                  "Use git commands (git gc, git worktree remove) or ask the user.")
    if cls == "project_root":
        return _f(DENY, "DEL-PROJECT-ROOT", f"{what} deletes the whole project directory ({label}).",
                  "Delete specific build or cache folders instead.")
    if cls in ("project", "temp"):
        return None
    if cls == "temp_root":
        return _f(ASK, "DEL-OUTSIDE", f"{what} deletes the shared temp directory {label}.",
                  "Delete only the subfolder this task created.")
    return _f(ASK, "DEL-OUTSIDE", f"{what} deletes {label}, which is outside the project.",
              "Confirm the exact path with the user, or move it to a dated backup folder instead.")


def h_rm(name, arg_words, ctx, st, dynamic_args, nxt_name, nxt):
    out = []
    pos, opts = _positional(arg_words)
    if name == "rimraf":
        recursive = True
    else:
        recursive = any(o in ("--recursive",) or (not o.startswith("--") and re.search(r"[rR]", o)) for o in opts)
    if "--no-preserve-root" in opts:
        out.append(_f(DENY, "DEL-ROOT-HOME", "--no-preserve-root disables the last safety check against deleting /."))
    if not pos and dynamic_args and recursive:
        out.append(_f(ASK, "DEL-UNVERIFIED", "Recursive delete of paths supplied at runtime (xargs).",
                      "Print the list first and delete literal paths inside the project."))
    for w in pos:
        f = _delete_decision(resolve(w, ctx, st.cwd), ctx, recursive, "rm -r" if recursive else "rm")
        if f:
            out.append(f)
        if not recursive and w.text and not w.dynamic:
            t = resolve(w, ctx, st.cwd)
            if t.kind == "path" and is_config_target(t.path, ctx):
                out.append(_f(ASK, "CFG-CHANGE", f"Deletes agent, shell or SSH configuration ({t.path})."))
    return out


def h_shred(name, arg_words, ctx, st, *rest):
    pos, _ = _positional(arg_words)
    out = []
    for w in pos:
        t = resolve(w, ctx, st.cwd)
        if t.kind == "path" and DEV_DISK.match(t.path):
            out.append(_f(DENY, "DISK-DESTROY", f"{name} overwrites the block device {t.path}."))
        else:
            out.append(_f(ASK, "DEL-UNRECOVERABLE", f"{name} overwrites file contents so they cannot be recovered.",
                          "Use a normal delete inside the project, or confirm with the user."))
    return out


def h_unlink(name, arg_words, ctx, st, *rest):
    pos, _ = _positional(arg_words)
    out = []
    for w in pos:
        f = _delete_decision(resolve(w, ctx, st.cwd), ctx, False, name)
        if f:
            out.append(f)
    return out


FIND_FILTERS = {
    "-name", "-iname", "-path", "-ipath", "-regex", "-iregex", "-type", "-mtime", "-mmin",
    "-newer", "-size", "-empty", "-user", "-perm", "-wholename", "-iwholename", "-lname",
    "-samefile", "-inum", "-links", "-atime", "-ctime", "-amin", "-cmin", "-used", "-group",
}


def h_find(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    roots: List[Word] = []
    i = 0
    while i < len(arg_words) and texts[i] in ("-H", "-L", "-P", "-O0", "-O1", "-O2", "-O3"):
        i += 1
    while i < len(arg_words) and not (texts[i].startswith("-") or texts[i] in ("(", "!", ",")):
        roots.append(arg_words[i])
        i += 1
    expr = texts[i:]
    deleting = "-delete" in expr
    sub_findings: List[Finding] = []
    j = 0
    while j < len(expr):
        if expr[j] in ("-exec", "-execdir", "-ok", "-okdir"):
            k = j + 1
            while k < len(expr) and expr[k] not in (";", "+"):
                k += 1
            inner = expr[j + 1:k]
            if inner:
                iname = _basename(inner[0])
                if iname in ("rm", "shred", "unlink", "rimraf"):
                    deleting = True
                elif iname in SHELLS or iname in ("chmod", "chown", "chgrp", "git", "mv"):
                    inner_text = " ".join(_shell_quote(x) for x in inner).replace("{}", "found-path")
                    sub_findings.extend(analyze_text(inner_text, ctx, st.cwd, st.depth + 1))
            j = k
        j += 1
    out = list(sub_findings)
    if not deleting:
        return out
    filtered = any(e in FIND_FILTERS for e in expr)
    if not roots:
        roots = [Word(text=".")]
    for w in roots:
        t = resolve(w, ctx, st.cwd)
        if filtered:
            if t.kind != "path":
                out.append(_f(ASK, "DEL-UNVERIFIED", "find deletes matches under a path computed at runtime."))
                continue
            cls = classify(t.path, ctx)
            if cls in ("project", "project_root", "temp"):
                continue
            if cls in ("credential", "gitdir"):
                out.append(_f(DENY, _del_rule(cls), f"find deletes matches inside {t.path}, which holds credentials or repository history."))
                continue
            out.append(_f(ASK, "DEL-OUTSIDE", f"find deletes matching files under {t.path}, outside the project.",
                          "Run the same find with -print first and show the user the list."))
        else:
            f = _delete_decision(t, ctx, True, "find -delete")
            if f:
                out.append(f)
    return out


def _shell_quote(text: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=@%+,-]+", text or "x"):
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"


def h_mv(name, arg_words, ctx, st, *rest):
    pos, _ = _positional(arg_words)
    out = []
    for w in pos[:-1]:
        t = resolve(w, ctx, st.cwd)
        if t.kind != "path":
            continue
        cls = classify(t.path, ctx)
        if cls in ("root", "home", "ancestor") and t.glob != "some":
            out.append(_f(DENY, "DEL-ROOT-HOME", f"mv moves {t.path} ({cls.replace('_', ' ')}); the filesystem root, home folder and project parents must stay where they are."))
        elif cls == "system" and t.glob != "some":
            out.append(_f(ASK, "DEL-SYSTEM", f"mv relocates the system path {t.path}."))
        elif cls in ("credential", "gitdir"):
            out.append(_f(ASK, _del_rule(cls), f"mv relocates {t.path}, which holds credentials or repository internals."))
    return out


def h_shell(name, arg_words, ctx, st, dynamic_args, nxt_name, nxt):
    out = []
    script: Optional[Word] = None
    has_c = False
    for w in arg_words:
        t = w.text
        if not has_c and t.startswith("-") and not t.startswith("--") and "c" in t[1:]:
            has_c = True
            continue
        if t.startswith("-"):
            continue
        if has_c:
            script = w
        break
    if has_c and script is not None:
        if script.dynamic and any(_basename(s.split()[0]) in DOWNLOADERS for s in script.subs if s.split()):
            out.append(_f(DENY, "REMOTE-EXEC", "Runs a script downloaded from the network without saving or reading it.",
                          "Download to a file, read it, verify a checksum, then run it with the user's OK."))
        out.extend(analyze_text(script.text, ctx, st.cwd, st.depth + 1))
    for w in arg_words:
        if w.text.startswith("<(") and any(s.split() and _basename(s.split()[0]) in DOWNLOADERS for s in w.subs):
            out.append(_f(DENY, "REMOTE-EXEC", "Runs a downloaded script straight from the network (process substitution).",
                          "Download to a file, read it, verify a checksum, then run it with the user's OK."))
    return out


EVAL_SAFE = {"ssh-agent", "pyenv", "rbenv", "nodenv", "direnv", "brew", "conda", "fnm", "mise",
             "starship", "zoxide", "asdf", "goenv", "jenv", "keychain", "dircolors", "rtx"}


def h_eval(name, arg_words, ctx, st, *rest):
    out = []
    for w in arg_words:
        if w.dynamic and any(s.split() and _basename(s.split()[0]) in DOWNLOADERS for s in w.subs):
            out.append(_f(DENY, "REMOTE-EXEC", "Evaluates code fetched from the network.",
                          "Download to a file, read it, then decide with the user."))
    text = " ".join(w.text for w in arg_words)
    subs = [s.split()[0] for w in arg_words for s in w.subs if s.split()]
    known = subs and all(_basename(x) in EVAL_SAFE for x in subs)
    if any(w.dynamic for w in arg_words) and not out and not known:
        out.append(_f(ASK, "CMD-DYNAMIC", "eval runs text that is computed at runtime, so the guard cannot see it.",
                      "Run the intended command directly."))
    out.extend(analyze_text(text, ctx, st.cwd, st.depth + 1))
    return out


def h_source(name, arg_words, ctx, st, *rest):
    out = []
    for w in arg_words:
        if w.text.startswith("<(") and any(s.split() and _basename(s.split()[0]) in DOWNLOADERS for s in w.subs):
            out.append(_f(DENY, "REMOTE-EXEC", "Sources a script straight from the network.",
                          "Download to a file, read it, verify a checksum, then run it with the user's OK."))
    return out


SSH_VALUE_OPTS = set("bcDEeFIiJLlmOoPpQRSWw")
# On a remote host the guard does not know the layout, so most denials become
# questions; these stay denied wherever they run.
REMOTE_KEEP_DENY = {"DEL-ROOT-HOME", "DISK-DESTROY", "PROC-FORK-BOMB", "REMOTE-EXEC", "NET-REVERSE-SHELL",
                    "SECRET-EXFIL", "GIT-FORCE-PROTECTED", "GIT-MIRROR-PUSH", "PROC-KILL-ALL"}


def h_ssh(name, arg_words, ctx, st, *rest):
    exfil = h_sender(name, arg_words, ctx, st)
    if exfil:
        return exfil
    i = 0
    while i < len(arg_words):
        t = arg_words[i].text
        if t == "--":
            i += 1
            break
        if t.startswith("-") and len(t) > 1:
            if t[-1] in SSH_VALUE_OPTS and len(t) == 2:
                i += 1
            i += 1
            continue
        break
    if i >= len(arg_words) - 1:
        return []
    host = arg_words[i].text
    remote_cmd = " ".join(w.text for w in arg_words[i + 1:])
    rctx = Context(cwd=None, project_root=None, home=ctx.home, temp_roots=ctx.temp_roots,
                   protected=ctx.protected, read_git_head=False)
    out = []
    for f in analyze_text(remote_cmd, rctx, None, st.depth + 1):
        decision = f.decision
        if decision == DENY and f.rule not in REMOTE_KEEP_DENY:
            decision = ASK
        out.append(Finding(decision, f.rule, f"On remote host {host}: {f.reason}", f.safer, f.prod_sensitive))
    return out


URL_LIKE = re.compile(r"^(?:[a-z][a-z0-9+.-]*://[^\s/]+|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?(?:/|$)|\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/|$))")
CURL_FILE_OPTS = ("-T", "--upload-file", "--post-file", "--body-file")
CURL_DATA_OPTS = ("-d", "--data", "--data-binary", "--data-raw", "--data-ascii", "--json")


SENDERS = {"curl", "wget", "nc", "ncat", "netcat", "socat", "ssh", "http", "https", "xh", "telnet"}


def _upstream_secret(ctx: Context, st: State) -> Optional[str]:
    """Name of a key file or environment dump earlier in the same pipeline, if any."""
    for c in st.pipeline:
        if c.position >= st.position or not c.words:
            continue
        ws, _d, env_dump = unwrap(list(c.words), [])
        if env_dump or (ws and _basename(ws[0].text) in ("printenv", "env") and len(ws) == 1):
            return "the environment"
        for w in ws[1:]:
            t = resolve(w, ctx, st.cwd)
            if secret_class(t.path if t.kind == "path" else w.text) == "key":
                return w.text
        for r in c.redirects:
            if r.op in ("<", "<&") and r.target is not None and secret_class(r.target.text) == "key":
                return r.target.text
    return None


def h_sender(name, arg_words, ctx, st, *rest):
    """Secrets piped into a network program: cat KEY | curl ..., env | nc host port."""
    source = _upstream_secret(ctx, st)
    if source is None:
        return []
    return [_f(DENY, "SECRET-EXFIL", f"Pipes {source} into {name}, which can send it to another machine.",
               "Never send credentials or the environment off the machine.")]


def h_curl(name, arg_words, ctx, st, *rest):
    """Uploads of local files to hosts other than this machine."""
    exfil = h_sender(name, arg_words, ctx, st)
    if exfil:
        return exfil
    files: List[str] = []
    hosts: List[str] = []
    texts = [w.text for w in arg_words]
    i = 0
    while i < len(texts):
        t = texts[i]
        opt, val = t, None
        if t.startswith("--") and "=" in t:
            opt, val = t.split("=", 1)
        takes = CURL_FILE_OPTS + CURL_DATA_OPTS + ("-F", "--form", "--data-urlencode")
        if opt in takes:
            if val is None and i + 1 < len(texts):
                val = texts[i + 1]
                i += 1
            if val is not None:
                if opt in CURL_FILE_OPTS:
                    files.append(val)
                elif opt in ("-F", "--form"):
                    m = re.match(r"^[^=]*=([@<])([^;]+)", val)
                    if m:
                        files.append(m.group(2))
                elif opt == "--data-urlencode":
                    m = re.match(r"^[^=@]*@(.+)$", val)
                    if m:
                        files.append(m.group(1))
                elif val.startswith("@") and val != "@-":
                    files.append(val[1:])
        elif URL_LIKE.match(t):
            hosts.append(t)
        i += 1
    remote = []
    for h in hosts:
        host = urlsplit(h if "://" in h else "//" + h).hostname or ""
        if host and not LOCAL_HOSTS.match(host):
            remote.append(host)
    if not files or not remote:
        return []
    out = []
    for fpath in files:
        target = resolve(Word(text=fpath), ctx, st.cwd)
        cls = secret_class(target.path if target.kind == "path" else fpath)
        if cls:
            out.append(_f(DENY, "SECRET-EXFIL", f"Uploads a secret file ({fpath}) to {remote[0]}.",
                          "Never send credentials off the machine; ask the user how they want to share them."))
        else:
            out.append(_f(ASK, "DATA-UPLOAD", f"Uploads local file {fpath} to {remote[0]}.",
                          "Confirm the destination and the file with the user first."))
    return out


def _remote_spec(text: str) -> bool:
    return bool(re.match(r"^(?:[^/@:]+@)?[A-Za-z0-9._-]+:(?!//)", text)) or text.startswith(("rsync://", "s3://", "gs://"))


def h_scp(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    pos = []
    i = 0
    while i < len(texts):
        t = texts[i]
        if t.startswith("-") and len(t) > 1:
            if name == "scp" and t in ("-i", "-P", "-o", "-F", "-J", "-l", "-S", "-c", "-D", "-X"):
                i += 1
            elif name == "rsync" and t in ("-e", "--rsh", "--exclude", "--include", "--filter", "-f", "--port"):
                i += 1
            i += 1
            continue
        pos.append(t)
        i += 1
    out = []
    if name == "rsync" and any(t.startswith("--delete") or t == "--remove-source-files" for t in texts) and pos:
        dest = pos[-1]
        t = resolve(Word(text=dest), ctx, st.cwd) if not _remote_spec(dest) else Target("unknown")
        if t.kind != "path" or classify(t.path, ctx) not in ("project", "temp"):
            out.append(_f(ASK, "DEL-SYNC", "rsync with --delete removes files at the destination that are not in the source.",
                          "Run the same command with --dry-run --itemize-changes first and show the user."))
    if len(pos) < 2 or not _remote_spec(pos[-1]):
        return out
    for src in pos[:-1]:
        if _remote_spec(src):
            continue
        cls = secret_class(resolve(Word(text=src), ctx, st.cwd).path or src)
        if cls:
            out.append(_f(DENY, "SECRET-EXFIL", f"Copies a secret file ({src}) to another machine.",
                          "Never move credentials off the machine from an agent session."))
        else:
            out.append(_f(ASK, "DATA-UPLOAD", f"Copies {src} to a remote host ({pos[-1]}).",
                          "Confirm the destination with the user; deployments need explicit permission."))
    return out


def h_nc(name, arg_words, ctx, st, *rest):
    exfil = h_sender(name, arg_words, ctx, st)
    if exfil:
        return exfil
    if name == "socat":
        if any(re.match(r"(?i)(exec|system):", w.text) for w in arg_words):
            return [_f(ASK, "NET-REVERSE-SHELL", "socat connects a program to a socket; confirm this is a local test setup.")]
        return []
    if any(re.fullmatch(r"-[A-Za-z]*[ec][A-Za-z]*", w.text) for w in arg_words):
        return [_f(DENY, "NET-REVERSE-SHELL", f"{name} -e/-c attaches a program to a network socket.")]
    return []


def h_su(name, arg_words, ctx, st, *rest):
    out = [_f(ASK, "PRIV-ESCALATION", "su switches to another user, usually root.",
              "Ask the user first; prefer a user-level install or a project-local tool.")]
    texts = [w.text for w in arg_words]
    for i, t in enumerate(texts):
        if t in ("-c", "--command") and i + 1 < len(texts):
            out.extend(analyze_text(texts[i + 1], ctx, st.cwd, st.depth + 1))
            break
    return out


def h_dd(name, arg_words, ctx, st, *rest):
    out = []
    for w in arg_words:
        if w.text.startswith("of="):
            target = w.text[3:]
            if DEV_DISK.match(target) or (target.startswith("/dev/") and not DEV_SAFE.match(target)):
                out.append(_f(DENY, "DISK-DESTROY", f"dd writes raw data onto the device {target}.",
                              "Never write to block devices from an agent session."))
            else:
                t = resolve(Word(text=target), ctx, st.cwd)
                if t.kind == "path" and classify(t.path, ctx) not in ("project", "temp"):
                    out.append(_f(ASK, "DEL-OUTSIDE", f"dd overwrites {target}, outside the project."))
        if w.text.startswith("if="):
            cls = secret_class(w.text[3:])
            if cls == "key":
                out.append(_f(ASK, "SECRET-READ", f"dd reads key material ({w.text[3:]})."))
    return out


def h_diskutil(name, arg_words, ctx, st, *rest):
    verbs = {"erasedisk", "erasevolume", "partitiondisk", "zerodisk", "randomdisk", "secureerase",
             "reformat", "deletecontainer", "deletevolume", "splitpartition", "mergepartitions"}
    if any(w.text.lower() in verbs for w in arg_words):
        return [_f(DENY, "DISK-DESTROY", "diskutil erases or repartitions a disk.")]
    return []


def h_chmod(name, arg_words, ctx, st, *rest):
    out = []
    opt_re = re.compile(r"-[RfvchHLP]+")
    recursive = False
    pos: List[Word] = []
    for w in arg_words:
        t = w.text
        if t in ("--recursive",) or (opt_re.fullmatch(t) and "R" in t):
            recursive = True
        elif t == "--no-preserve-root":
            out.append(_f(DENY, "PERM-CATASTROPHIC", "--no-preserve-root allows changing permissions on /."))
        elif opt_re.fullmatch(t) or t.startswith("--"):
            continue
        else:
            pos.append(w)
    if not pos:
        return out
    spec, targets = pos[0].text, pos[1:]
    if name == "chmod":
        octal = re.fullmatch(r"0?[0-7]{3,4}", spec)
        world = (octal and int(spec[-1]) & 2) or re.search(r"(^|,)[ugo]*[ao][ugo]*[+=][rwxXst]*w", spec)
        if world:
            out.append(_f(ASK, "PERM-WORLD-WRITABLE", f"chmod {spec} makes files writable by every user on the machine.",
                          "Grant the minimum: 755 for directories and executables, 644 for files, 600 for secrets."))
    for w in targets:
        t = resolve(w, ctx, st.cwd)
        if t.kind != "path":
            if recursive:
                out.append(_f(ASK, "PERM-UNVERIFIED", f"Recursive {name} on a path computed at runtime."))
            continue
        cls = classify(t.path, ctx)
        if recursive:
            if cls in CATASTROPHIC:
                out.append(_f(DENY, "PERM-CATASTROPHIC", f"Recursive {name} on {t.path} ({cls}) can break the system, SSH or the user's account.",
                              "Change only the specific files the task needs."))
            elif cls not in ("project", "project_root", "temp"):
                out.append(_f(ASK, "PERM-OUTSIDE", f"Recursive {name} on {t.path}, outside the project.",
                              "Record current modes first (stat or getfacl -R) and confirm with the user."))
        elif cls == "root":
            out.append(_f(DENY, "PERM-CATASTROPHIC", f"{name} on / changes the root of the filesystem."))
    return out


def h_kill(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    out = []
    if name in ("killall5",):
        return [_f(DENY, "PROC-KILL-ALL", "killall5 signals every process on the machine.")]
    if name in ("pkill", "killall"):
        return [_f(ASK, "PROC-KILL", f"{name} matches processes by name and can stop unrelated programs, including the user's own.",
                   "Find the exact PID you started (ps -p PID -o pid,command or lsof -i :PORT) and stop only that one.")]
    if any(t in ("-l", "-L", "--list", "--table") for t in texts):
        return []
    signal_seen, pids, i = False, [], 0
    while i < len(texts):
        t = texts[i]
        if t == "--":
            pids.extend(texts[i + 1:])
            break
        if not signal_seen and t.startswith("-") and len(t) > 1:
            if t in ("-s", "-n", "--signal"):
                i += 1
            signal_seen = True
        else:
            pids.append(t)
        i += 1
    for p in pids:
        if p in ("-1", "1"):
            out.append(_f(DENY, "PROC-KILL-ALL", "kill on PID 1 or -1 targets init or every process the user owns."))
        elif p.startswith("%") or p == "$!":
            continue
        else:
            out.append(_f(ASK, "PROC-KILL", f"Stops process {p}; the guard cannot tell whether this session started it.",
                          "Confirm the PID belongs to a process this task started (ps -p PID -o pid,ppid,command)."))
    return out[:1] if out and all(f.decision == ASK for f in out) else out


def h_power(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    if name in ("init", "telinit") and not any(t in ("0", "6") for t in texts):
        return []
    if name == "shutdown" and "-c" in texts:
        return []
    return [_f(DENY, "PROC-POWER", f"{name} shuts down or restarts the machine.")]


def h_systemctl(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words if not w.text.startswith("-")]
    verb = texts[0] if texts else ""
    if verb in ("poweroff", "reboot", "halt", "kexec", "suspend", "hibernate", "hybrid-sleep", "soft-reboot"):
        return [_f(DENY, "PROC-POWER", f"systemctl {verb} stops or restarts the machine.")]
    if verb in ("stop", "kill", "disable", "mask", "isolate"):
        return [_f(ASK, "PROC-SERVICE", f"systemctl {verb} stops or disables a system service.",
                   "Confirm the service and the reason with the user.")]
    if verb in ("enable", "link"):
        return [_f(ASK, "CFG-PERSISTENCE", "systemctl enable makes a program start automatically.")]
    return []


def h_launchctl(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    verb = texts[0] if texts else ""
    if verb in ("unload", "bootout", "remove", "disable", "kill"):
        return [_f(ASK, "PROC-SERVICE", f"launchctl {verb} stops or removes a background service.")]
    if verb in ("load", "bootstrap", "enable", "submit"):
        return [_f(ASK, "CFG-PERSISTENCE", f"launchctl {verb} installs a program that starts automatically.")]
    return []


def h_service(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    if len(texts) >= 2 and texts[1] in ("stop", "restart"):
        return [_f(ASK, "PROC-SERVICE", f"Stops or restarts the system service {texts[0]}.")]
    return []


def h_crontab(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    if "-r" in texts:
        return [_f(DENY, "CFG-PERSISTENCE", "crontab -r deletes every scheduled job for the user without confirmation.",
                   "Export first (crontab -l > crontab.backup) and edit only the line that needs to change, with the user's OK.")]
    if not texts or texts == ["-l"] or "-l" in texts:
        return []
    return [_f(ASK, "CFG-PERSISTENCE", "Edits the user's scheduled jobs (crontab).", "Show the user the exact line first.")]


GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env",
                  "--super-prefix", "--attr-source"}


def current_branch(start: Optional[str]) -> Optional[str]:
    if not start:
        return None
    d = start
    head_path = None
    for _ in range(64):
        g = os.path.join(d, ".git")
        try:
            if os.path.isdir(g):
                head_path = os.path.join(g, "HEAD")
                break
            if os.path.isfile(g):
                with open(g, "r", encoding="utf-8", errors="replace") as fh:
                    line = fh.read(4096).strip()
                if line.startswith("gitdir:"):
                    gd = line[len("gitdir:"):].strip()
                    gd = gd if os.path.isabs(gd) else os.path.join(d, gd)
                    head_path = os.path.join(gd, "HEAD")
                break
        except OSError:
            return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    if not head_path:
        return None
    try:
        with open(head_path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(1024).strip()
    except OSError:
        return None
    if head.startswith("ref: refs/heads/"):
        return head[len("ref: refs/heads/"):]
    return None


def _is_protected(branch: str, ctx: Context) -> bool:
    b = branch[len("refs/heads/"):] if branch.startswith("refs/heads/") else branch
    return b in ctx.protected or b.startswith(("release/", "release-", "hotfix/"))


def h_git(name, arg_words, ctx, st, *rest):
    texts = [w.text for w in arg_words]
    git_cwd = st.cwd
    i = 0
    while i < len(texts) and texts[i].startswith("-"):
        t = texts[i]
        if t == "-C" and i + 1 < len(texts):
            r = resolve(arg_words[i + 1], ctx, git_cwd)
            git_cwd = r.path if r.kind == "path" else None
            i += 2
            continue
        if t in GIT_VALUE_OPTS:
            i += 2
            continue
        i += 1
    if i >= len(texts):
        return []
    sub, a = texts[i], texts[i + 1:]
    sub_words = arg_words[i + 1:]
    fn = GIT_SUBS.get(sub)
    return fn(a, sub_words, ctx, st, git_cwd) if fn else []


def g_push(a, words, ctx, st, git_cwd):
    force = lease = mirror = delete = all_ = prune = False
    pos: List[str] = []
    i = 0
    while i < len(a):
        t = a[i]
        if t == "--":
            pos.extend(a[i + 1:])
            break
        if t.startswith("--"):
            opt = t.split("=", 1)[0]
            if opt == "--force":
                force = True
            elif opt == "--force-with-lease":
                lease = True
            elif opt == "--mirror":
                mirror = True
            elif opt == "--delete":
                delete = True
            elif opt in ("--all", "--branches"):
                all_ = True
            elif opt == "--prune":
                prune = True
            elif opt in ("--repo", "--receive-pack", "--exec", "--push-option") and "=" not in t:
                i += 1
        elif t.startswith("-") and len(t) > 1:
            cluster = t[1:]
            for j, ch in enumerate(cluster):
                if ch == "f":
                    force = True
                elif ch == "d":
                    delete = True
                elif ch == "o":
                    if j == len(cluster) - 1:
                        i += 1
                    break
        else:
            pos.append(t)
        i += 1
    out: List[Finding] = []
    if mirror:
        return [_f(DENY, "GIT-MIRROR-PUSH", "git push --mirror overwrites and deletes every branch and tag on the remote to match this clone.",
                   "Push specific branches instead.")]
    refspecs = pos[1:]
    targets: List[Tuple[str, bool, bool]] = []  # (branch or "", plus, deletion)
    for r in refspecs:
        plus = r.startswith("+")
        r2 = r[1:] if plus else r
        if ":" in r2:
            src, dst = r2.split(":", 1)
            targets.append((dst or "", plus, src == "" or delete))
        else:
            targets.append((r2, plus, delete))
    head = None

    def resolve_branch(b: str) -> Optional[str]:
        nonlocal head
        if b in ("", "HEAD", "@"):
            if head is None and ctx.read_git_head:
                head = current_branch(git_cwd) or ""
            return head or None
        return b[len("refs/heads/"):] if b.startswith("refs/heads/") else b

    for b, _plus, deletion in targets:
        if deletion:
            name = resolve_branch(b)
            if name and _is_protected(name, ctx):
                out.append(_f(DENY, "GIT-REMOTE-DELETE", f"Deletes the protected remote branch or tag '{name}'."))
            else:
                out.append(_f(ASK, "GIT-REMOTE-DELETE", f"Deletes the remote branch or tag '{b}'.",
                              "Confirm with the user; other people may depend on it."))
    any_plus = any(p for _b, p, d in targets if not d)
    if force or any_plus or lease:
        push_targets = [resolve_branch(b) for b, p, d in targets if not d and (p or force or lease)]
        if not targets:
            push_targets = [resolve_branch("")]
        if all_:
            push_targets.append(None)
        plain = force or any_plus
        for b in push_targets:
            if b is None:
                out.append(_f(DENY if all_ and plain else ASK, "GIT-FORCE-PUSH",
                              "Force push to a branch the guard cannot determine (it may be a shared branch).",
                              "Name the branch explicitly: git push --force-with-lease origin <your-branch>."))
            elif _is_protected(b, ctx):
                out.append(_f(DENY, "GIT-FORCE-PROTECTED", f"Force push to the protected branch '{b}' rewrites shared history.",
                              "Push to a new branch and open a pull request; never rewrite the main line."))
            elif plain:
                out.append(_f(ASK, "GIT-FORCE-PUSH", f"Plain force push to '{b}' overwrites remote commits you have not fetched.",
                              f"Use git push --force-with-lease --force-if-includes origin {b}."))
    if prune:
        out.append(_f(ASK, "GIT-REMOTE-DELETE", "git push --prune deletes remote branches that do not exist locally."))
    return out


def g_reset(a, words, ctx, st, git_cwd):
    if "--hard" in a or "--merge" in a:
        return [_f(ASK, "GIT-DISCARD", "git reset --hard discards uncommitted changes; they cannot be recovered from git.",
                   "Run git status; save work with git stash push --include-untracked or a backup branch first.")]
    return []


def g_clean(a, words, ctx, st, git_cwd):
    flags = "".join(t[1:] for t in a if t.startswith("-") and not t.startswith("--"))
    longs = [t for t in a if t.startswith("--")]
    if "n" in flags or "--dry-run" in longs:
        return []
    if "f" in flags or "--force" in longs:
        extra = " including ignored files such as .env and local databases" if ("x" in flags or "X" in flags) else ""
        return [_f(ASK, "GIT-DISCARD", f"git clean -f permanently deletes untracked files{extra}.",
                   "Run git clean -n (dry run) first and show the user the list.")]
    return []


def g_checkout(a, words, ctx, st, git_cwd):
    if "-b" in a or "-B" in a or "--orphan" in a:
        return []
    if "--" in a and a.index("--") < len(a) - 1:
        return [_f(ASK, "GIT-DISCARD", "git checkout -- <path> overwrites uncommitted changes in those files.",
                   "Check git diff for the paths first; stash them if they may be needed.")]
    if "-f" in a or "--force" in a or "." in a:
        return [_f(ASK, "GIT-DISCARD", "This git checkout discards local changes.",
                   "Check git status first; stash changes that may be needed.")]
    pos = [t for t in a if not t.startswith("-")]
    if len(pos) >= 2:
        return [_f(ASK, "GIT-DISCARD", "git checkout <ref> <path> overwrites those files with another version.",
                   "Check git diff for the paths first.")]
    return []


def g_restore(a, words, ctx, st, git_cwd):
    staged = any(t in ("--staged", "-S") for t in a)
    worktree = any(t in ("--worktree", "-W") for t in a)
    if staged and not worktree:
        return []
    return [_f(ASK, "GIT-DISCARD", "git restore overwrites uncommitted changes in the working tree.",
               "Check git diff for the paths first; use git restore --staged to only unstage.")]


def g_switch(a, words, ctx, st, git_cwd):
    if any(t in ("-f", "--force", "--discard-changes") for t in a):
        return [_f(ASK, "GIT-DISCARD", "git switch --discard-changes throws away local changes.")]
    return []


def g_branch(a, words, ctx, st, git_cwd):
    flags = "".join(t[1:] for t in a if t.startswith("-") and not t.startswith("--"))
    if "D" in flags or (("d" in flags or "--delete" in a) and ("f" in flags or "--force" in a)):
        return [_f(ASK, "GIT-BRANCH-DELETE", "git branch -D deletes a branch even if its commits are not merged anywhere.",
                   "Use git branch -d, which refuses to delete unmerged work.")]
    return []


def g_stash(a, words, ctx, st, git_cwd):
    if a and a[0] in ("drop", "clear"):
        return [_f(ASK, "GIT-DISCARD", f"git stash {a[0]} deletes saved work.", "List with git stash list and confirm first.")]
    return []


def g_history(a, words, ctx, st, git_cwd):
    return [_f(ASK, "GIT-HISTORY-REWRITE", "Rewrites repository history; every clone and open pull request is affected.",
               "Make a backup (git clone --mirror) and agree the plan with the user before running it.")]


def g_reflog(a, words, ctx, st, git_cwd):
    if a and a[0] in ("expire", "delete"):
        return [_f(ASK, "GIT-HISTORY-REWRITE", "Removes reflog entries, the main way to recover lost commits.")]
    return []


def g_gc(a, words, ctx, st, git_cwd):
    if any(t in ("--prune=now", "--prune=all") for t in a):
        return [_f(ASK, "GIT-HISTORY-REWRITE", "git gc --prune=now deletes unreachable commits immediately, removing the recovery window.")]
    return []


def g_update_ref(a, words, ctx, st, git_cwd):
    if "-d" in a or "--delete" in a:
        return [_f(ASK, "GIT-BRANCH-DELETE", "git update-ref -d deletes a ref directly.")]
    return []


def g_worktree(a, words, ctx, st, git_cwd):
    if a and a[0] == "remove" and any(t in ("-f", "--force") for t in a):
        return [_f(ASK, "GIT-DISCARD", "git worktree remove --force deletes a worktree including uncommitted changes.")]
    return []


def g_rm(a, words, ctx, st, git_cwd):
    if any(t in ("-f", "--force") or re.fullmatch(r"-[a-z]*f[a-z]*", t) for t in a) and "--cached" not in a:
        return [_f(ASK, "GIT-DISCARD", "git rm -f deletes files even when they have uncommitted changes.")]
    return []


def g_config(a, words, ctx, st, git_cwd):
    scope = any(t in ("--global", "--system") for t in a)
    readonly = any(t in ("--get", "--get-all", "--get-regexp", "-l", "--list", "--get-urlmatch") for t in a)
    pos = [t for t in a if not t.startswith("-")]
    if pos and pos[0] in ("get", "list"):
        readonly = True
    if not readonly and pos and pos[0] in ("set", "unset", "edit", "rename-section", "remove-section"):
        readonly = False
    elif not readonly and len(pos) < 2 and not any(t in ("--unset", "--unset-all", "--add", "--replace-all",
                                                           "--remove-section", "--rename-section", "-e", "--edit") for t in a):
        readonly = True
    if readonly:
        return []
    if scope:
        return [_f(ASK, "GIT-GLOBAL-CONFIG", "Changes the user's global git configuration, which affects every repository.",
                   "Use repository-local config (no --global) unless the user asked for a global change.")]
    if any(p.lower() == "core.hookspath" for p in pos):
        return [_f(ASK, "CFG-CHANGE", "Changes which git hooks run for this repository.")]
    return []


def g_add(a, words, ctx, st, git_cwd):
    out = []
    for t in a:
        if not t.startswith("-") and secret_class(t):
            out.append(_f(ASK, "SECRET-COMMIT", f"Stages {t}, which looks like a secrets file, for commit.",
                          "Keep it out of git: add it to .gitignore and commit a .example file with placeholder values."))
    return out


def g_show(a, words, ctx, st, git_cwd):
    out = []
    for t in a:
        target = t.split(":", 1)[1] if ":" in t and not t.startswith("-") else t
        if not t.startswith("-") and secret_class(target):
            out.append(_f(ASK, "SECRET-READ", f"Prints the contents or history of {target}, which looks like a secrets file."))
    return out


GIT_SUBS = {
    "push": g_push, "reset": g_reset, "clean": g_clean, "checkout": g_checkout, "restore": g_restore,
    "switch": g_switch, "branch": g_branch, "stash": g_stash, "filter-branch": g_history,
    "filter-repo": g_history, "reflog": g_reflog, "gc": g_gc, "update-ref": g_update_ref,
    "worktree": g_worktree, "rm": g_rm, "config": g_config, "add": g_add, "show": g_show,
    "diff": g_show, "log": lambda a, *r: g_show(a, *r) if any(x in ("-p", "--patch", "-u") for x in a) else [],
}


def h_bfg(name, arg_words, ctx, st, *rest):
    return g_history([], [], ctx, st, st.cwd)


def h_java(name, arg_words, ctx, st, *rest):
    if any("bfg" in w.text.lower() and w.text.endswith(".jar") for w in arg_words):
        return g_history([], [], ctx, st, st.cwd)
    return []


HANDLERS = {
    "rm": h_rm, "rimraf": h_rm, "shred": h_shred, "srm": h_shred, "wipe": h_shred, "unlink": h_unlink,
    "find": h_find, "mv": h_mv, "eval": h_eval, "source": h_source, ".": h_source,
    "ssh": h_ssh, "curl": h_curl, "wget": h_curl, "http": h_curl, "https": h_curl, "xh": h_curl,
    "scp": h_scp, "rsync": h_scp, "nc": h_nc, "ncat": h_nc, "netcat": h_nc, "socat": h_nc,
    "dd": h_dd, "diskutil": h_diskutil, "chmod": h_chmod, "chown": h_chmod, "chgrp": h_chmod,
    "telnet": h_sender, "kill": h_kill, "pkill": h_kill, "killall": h_kill, "killall5": h_kill,
    "systemctl": h_systemctl, "launchctl": h_launchctl, "service": h_service, "crontab": h_crontab,
    "git": h_git, "bfg": h_bfg, "java": h_java, "su": h_su,
}
for _shell in SHELLS:
    HANDLERS[_shell] = h_shell
for _p in POWER:
    HANDLERS[_p] = h_power


def check_redirects(cmd: Command, ctx: Context, cwd: Optional[str]) -> List[Finding]:
    out = []
    for r in cmd.redirects:
        if r.target is None or r.op in ("<<", "<<-", "<<<"):
            continue
        t = resolve(r.target, ctx, cwd)
        text = r.target.text
        if r.op in WRITE_OPS:
            if DEV_DISK.match(text):
                out.append(_f(DENY, "DISK-DESTROY", f"Redirects output onto the block device {text}, destroying its contents."))
                continue
            if text.startswith("/dev/"):
                continue
            if t.kind == "path":
                if is_config_target(t.path, ctx):
                    out.append(_f(ASK, "CFG-CHANGE", f"Writes to {t.path}, which controls the agent, the shell, SSH access or git hooks.",
                                  "Show the user the exact change first."))
                elif classify(t.path, ctx) not in ("project", "temp", "project_root"):
                    out.append(_f(ASK, "WRITE-OUTSIDE", f"Overwrites or appends to {t.path}, outside the project.",
                                  "Write inside the project or a temp folder, or confirm the path with the user."))
            elif t.kind == "unknown":
                out.append(_f(ASK, "WRITE-OUTSIDE", "Writes to a path relative to a directory the guard cannot determine."))
        elif r.op in ("<", "<&"):
            cls = secret_class(t.path or text) if t.kind == "path" else secret_class(text)
            if cls == "key":
                out.append(_f(DENY, "SECRET-READ", f"Feeds key material ({text}) into a command."))
            elif cls == "env":
                out.append(_f(ASK, "SECRET-READ", f"Feeds a secrets file ({text}) into a command that may print it."))
    return out


def check_write_targets(name: str, args: List[str], ctx: Context, cwd: Optional[str]) -> List[Finding]:
    targets: List[str] = []
    if name == "tee":
        targets = [a for a in args if not a.startswith("-")]
    elif name in ("cp", "mv", "install", "ln", "rsync"):
        pos = [a for a in args if not a.startswith("-")]
        if len(pos) >= 2:
            targets = [pos[-1]]
    elif name in ("sed", "perl") and any(re.fullmatch(r"-[A-Za-z]*i.*", a) or a.startswith("--in-place") for a in args):
        targets = [a for a in args if not a.startswith("-")][1:]
    out = []
    for raw in targets:
        t = resolve(Word(text=raw), ctx, cwd)
        if t.kind == "path" and is_config_target(t.path, ctx):
            out.append(_f(ASK, "CFG-CHANGE", f"{name} changes {t.path}, which controls the agent, the shell, SSH access or git hooks.",
                          "Show the user the exact change first."))
        elif name == "tee" and t.kind == "path" and classify(t.path, ctx) not in ("project", "temp", "project_root") \
                and not t.path.startswith("/dev/"):
            out.append(_f(ASK, "WRITE-OUTSIDE", f"tee writes to {t.path}, outside the project."))
    return out


def check_secret_args(name: str, args: List[str], ctx: Context, cwd: Optional[str]) -> List[Finding]:
    if name in METADATA or name in ("cd", "pushd"):
        return []
    if name in ("grep", "egrep", "fgrep", "rg", "ag", "ack") and _grep_metadata_only(args):
        return []
    if name == "cut" and _names_only_cut(args):
        return []
    if name in ("curl", "wget", "scp", "rsync", "http", "https", "xh"):
        return []  # handled by upload checks
    if name == "git":
        return []  # handled by git subcommands
    if name in ("security",):
        return check_keychain(args)
    if name in ("gh", "gcloud", "az", "aws", "heroku"):
        return check_token_print(name, args)
    category = ("reader" if name in READERS else "copy" if name in COPIERS
                else "keyuser" if name in KEY_USERS else "other")
    out = []
    skip_next = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if category == "keyuser" and a in ("-i", "-f", "-F"):
            skip_next = True
            continue
        if a.startswith("-") and "=" not in a:
            continue
        if any(ch in a for ch in " \n\t") or len(a) > 512:
            continue  # code or prose, not a path
        candidate = a.split("=", 1)[1] if a.startswith("-") else a
        resolved = resolve(Word(text=candidate), ctx, cwd)
        cls = secret_class(resolved.path if resolved.kind == "path" else candidate)
        if not cls:
            continue
        if category == "reader":
            if cls == "key":
                out.append(_f(DENY, "SECRET-READ", f"Prints key or credential material ({candidate}) into the session log.",
                              "Do not read private keys or credential stores; check presence with ls -l or test -f."))
            else:
                out.append(_f(ASK, "SECRET-READ", f"Prints the contents of {candidate}, which holds secret values.",
                              "List variable names only: cut -d= -f1 FILE, or check one with grep -c '^NAME=' FILE."))
        elif category == "copy" and cls == "key":
            out.append(_f(ASK, "SECRET-COPY", f"Copies key or credential material ({candidate}).",
                          "Leave credentials in place; ask the user if a copy is really needed."))
        elif category == "other" and cls == "key":
            out.append(_f(ASK, "SECRET-READ", f"Passes key or credential material ({candidate}) to {name}.",
                          "Confirm with the user why this program needs it."))
    return out


def check_keychain(args: List[str]) -> List[Finding]:
    if args and args[0] == "dump-keychain":
        return [_f(DENY, "SECRET-READ", "Dumps the macOS keychain.")]
    if args and args[0] in ("find-generic-password", "find-internet-password") and any(a in ("-w", "-g") for a in args):
        return [_f(ASK, "SECRET-PRINT", "Prints a password from the macOS keychain into the session log.",
                   "Pass it to the program that needs it without printing, or ask the user.")]
    return []


def check_token_print(name: str, args: List[str]) -> List[Finding]:
    joined = " ".join(args)
    patterns = {
        "gh": r"^auth (token\b|status .*(-t|--show-token))",
        "gcloud": r"auth (application-default )?print-(access|identity)-token",
        "az": r"account get-access-token",
        "aws": r"configure (export-credentials|get .*(secret|token))",
        "heroku": r"auth:token",
    }
    if re.search(patterns[name], joined):
        return [_f(ASK, "SECRET-PRINT", f"Prints an access token for {name} into the session log.",
                   "Let the CLI use its stored login directly instead of printing the token.")]
    return []


def check_env_dump(name: str, args: List[str], nxt_name: str, nxt: Optional[Command]) -> List[Finding]:
    dump = False
    if name in ("env", "set", "export") and (not args or args in (["-p"], ["-0"], ["--null"])):
        dump = True
    if name in ("declare", "typeset") and (not args or args in (["-p"], ["-x"], ["-px"], ["-xp"])):
        dump = True
    if name == "printenv":
        names = [a for a in args if not a.startswith("-")]
        if not names:
            dump = True
        elif any(SECRET_VAR.search(n.upper()) for n in names):
            return [_f(ASK, "SECRET-PRINT", f"Prints the value of {', '.join(names)}.",
                       'Check presence without the value: [ -n "$NAME" ] && echo set.')]
    if not dump:
        return []
    if nxt_name in ("cut", "wc") or (nxt_name in ("grep", "rg") and nxt and _grep_metadata_only([w.text for w in nxt.words[1:]])):
        return []
    return [_f(ASK, "SECRET-ENV-DUMP", f"{name} prints every environment variable, including tokens and keys.",
               "Print names only (env | cut -d= -f1) or check the one variable you need.")]


def check_inline_code(name: str, words: List[Word], ctx: Context, cwd: Optional[str], depth: int) -> List[Finding]:
    flags = INTERPRETERS[name]
    code_word = None
    texts = [w.text for w in words[1:]]
    for i, t in enumerate(texts):
        if t in flags or (name in ("perl", "ruby") and re.fullmatch(r"-[a-zA-Z]*[eE]", t)) or (name == "deno" and t == "eval"):
            if i + 1 < len(texts):
                code_word = words[i + 2]
            break
    if code_word is None:
        return []
    if _fetches(code_word):
        return [_f(DENY, "REMOTE-EXEC", f"{name} runs code fetched from the network without saving or reading it.",
                   "Download to a file, read it, then run it with the user's OK.")]
    return inline_code_findings(name, code_word.text)


def _fetches(word: Word) -> bool:
    """True when a word's command substitutions start with a downloader."""
    return any(s.split() and _basename(s.split()[0]) in DOWNLOADERS for s in word.subs)


def inline_code_findings(name: str, code: str) -> List[Finding]:
    out = []
    if re.search(r"\brm\s+-[a-zA-Z]*[rR]|\bgit\s+push\b[^'\"]*(--force\b|\s-f\b)|\bgit\s+reset\s+--hard|\bmkfs\b|"
                 r"\bdd\s+[^'\"]*of=/dev/|(?i:\bdrop\s+(table|database|schema)\b)|(curl|wget)[^|'\"]*\|\s*(ba)?sh\b", code):
        out.append(_f(ASK, "INLINE-DESTRUCTIVE", f"Inline {name} code runs a destructive shell or SQL operation the guard cannot check in place.",
                      "Run the operation as a plain shell command so it can be checked, or confirm with the user."))
    if re.search(r"rmtree|rmSync|rimraf|remove_dir_all|rm_rf|unlinkSync|os\.remove|os\.unlink|\.unlink\(|fs\.rm\(|"
                 r"fs\.promises\.rm|FileUtils\.rm|File\.delete|shutil\.move", code) and re.search(
            r"expanduser|Path\.home|homedir|ENV\[['\"]HOME|environ\[['\"]HOME|getenv\(['\"]HOME|['\"]~|['\"]/['\"]", code):
        out.append(_f(ASK, "INLINE-DESTRUCTIVE", f"Inline {name} code deletes files relative to the home folder or filesystem root.",
                      "Delete explicit paths inside the project instead."))
    for lit in re.findall(r"['\"]([^'\"\n]{2,200})['\"]", code):
        if secret_class(lit) == "key":
            out.append(_f(ASK, "SECRET-READ", f"Inline {name} code references key or credential material ({lit})."))
            break
    return out


AWK_STRING = r'"((?:[^"\\]|\\.)*)"'


def _awk_unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), text)


def _call_args(code: str, func: str) -> List[str]:
    """Argument text of every func(...) call in awk code, respecting strings and nesting."""
    out = []
    for m in re.finditer(r"\b" + func + r"\s*\(", code):
        i, level, in_string = m.end(), 1, False
        while i < len(code) and level:
            ch = code[i]
            if in_string:
                if ch == "\\":
                    i += 1
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "(":
                level += 1
            elif ch == ")":
                level -= 1
            i += 1
        out.append(code[m.end():i - 1] if level == 0 else code[m.end():])
    return out


def check_awk(arg_words: List[Word], ctx: Context, cwd: Optional[str], depth: int) -> List[Finding]:
    """awk runs shell commands through system() and command pipes: check those written literally."""
    texts = [w.text for w in arg_words]
    i = 0
    while i < len(texts) and texts[i].startswith("-") and texts[i] != "-":
        t = texts[i]
        if t == "--":
            i += 1
            break
        if t in ("-f", "--file") or t.startswith("--file=") or (t.startswith("-f") and len(t) > 2):
            return []  # the program is in a file, which the guard cannot see
        i += 2 if t in ("-F", "-v", "--assign", "--field-separator") else 1
    if i >= len(texts):
        return []
    program = texts[i]
    out: List[Finding] = []
    for arg in _call_args(program, "system"):
        literal = re.fullmatch(r"\s*" + AWK_STRING + r"\s*", arg)
        if literal:
            out.extend(analyze_text(_awk_unescape(literal.group(1)), ctx, cwd, depth + 1))
        else:
            out.append(_f(ASK, "AWK-EXEC", "awk runs a shell command built at runtime, which the guard cannot check.",
                          "Run the command as a plain shell command, or confirm with the user."))
    piped = re.findall(r"\|&?\s*" + AWK_STRING, program) + re.findall(AWK_STRING + r"\s*\|&?\s*getline", program)
    for text in piped:
        out.extend(analyze_text(_awk_unescape(text), ctx, cwd, depth + 1))
    return out


def check_parallel(arg_words: List[Word], ctx: Context, cwd: Optional[str], depth: int) -> List[Finding]:
    """GNU parallel runs its command template once per input value: check the template."""
    texts = [w.text for w in arg_words]
    cut = next((k for k, t in enumerate(texts) if t in PARALLEL_SEPARATORS), len(texts))
    marker = PARALLEL_PLACEHOLDER
    i = 0
    while i < cut and texts[i].startswith("-"):
        t = texts[i]
        if t == "--":
            i += 1
            break
        if t in ("-I", "--replace") and i + 1 < cut:
            marker = re.escape(texts[i + 1]) + "|" + marker
            i += 2
            continue
        i += 2 if t in PARALLEL_VALUE_OPTS else 1
    template = texts[i:cut]
    if not template:  # each input value is a whole command
        return [f for t in texts[cut + 1:] if t not in PARALLEL_SEPARATORS
                for f in analyze_text(t, ctx, cwd, depth + 1)]
    if len(template) == 1 and " " in template[0]:
        text = template[0]  # one quoted string, which parallel hands to a shell
        found = re.search(marker, text) is not None
        text = re.sub(marker, '"$PARALLEL_INPUT"', text)
    else:
        parts, found = [], False
        for t in template:
            if re.search(marker, t):
                found = True
                esc = [p.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
                       for p in re.split(marker, t)]
                parts.append('"' + "${PARALLEL_INPUT}".join(esc) + '"')
            else:
                parts.append(_shell_quote(t))
        text = " ".join(parts)
    if not found:
        text += ' "$PARALLEL_INPUT"'  # inputs are appended as the last arguments
    return analyze_text(text, ctx, cwd, depth + 1)


READ_VERBS = {"plan", "preview", "show", "describe", "get", "list", "ls", "status", "logs", "validate",
              "fmt", "init", "output", "version", "help", "whoami", "diff", "view", "explain", "top", "graph"}


def _dry_run(args: List[str]) -> bool:
    return any(a in ("--dry-run", "--dryrun", "--what-if", "--preview") or
               (a.startswith("--dry-run=") and a != "--dry-run=none") for a in args)


def check_cloud(name: str, args: List[str]) -> List[Finding]:
    if _dry_run(args):
        return []
    positional = [a for a in args if not a.startswith("-")]
    if positional and positional[0] in READ_VERBS:
        return []
    if name == "gh":
        if args[:2] == ["repo", "edit"] and any("visibility" in a for a in args):
            return [_f(ASK, "ACCOUNT-EXPOSURE", "Changes repository visibility; making a private repository public exposes its code and history.")]
        if args[:1] in (["secret"], ["variable"]) and len(args) > 1 and args[1] in ("set", "delete", "remove"):
            return [_f(ASK, "ACCOUNT-CHANGE", f"Changes repository {args[0]}s used by CI and deployments.")]
    hits = []
    for a in args:
        if a in ("--delete-branch", "--remove-orphans", "--rm"):
            continue
        low = a.lower()
        parts = re.split(r"[-:_]", low)
        if low in DELETE_WORDS or any(p in DELETE_WORDS for p in parts if p):
            hits.append(a)
    if name == "gh" and any(a.upper() == "DELETE" for a in args):
        hits.append("DELETE")
    if not hits:
        return []
    return [_f(ASK, "CLOUD-DELETE", f"{name} {hits[0]} deletes or resets live resources; most cloud deletions cannot be undone.",
               "Run the provider's dry run or plan first, snapshot or back up data, and get the user's explicit OK.",
               prod=True)]


def check_deploy(name: str, args: List[str]) -> List[Finding]:
    verbs = DEPLOY.get(name, set())
    if _dry_run(args):
        return []
    if name in ("docker", "podman"):
        out = []
        words = [a for a in args if not a.startswith("-")]  # option values may slip in; membership checks tolerate that
        volume_delete = "volume" in words and ("rm" in words or "prune" in words)
        system_prune = "system" in words and "prune" in words
        compose_down = "compose" in words and "down" in words and any(a in ("-v", "--volumes") for a in args)
        if volume_delete or system_prune or compose_down:
            what = "volume rm/prune" if volume_delete else "system prune" if system_prune else "compose down -v"
            out.append(_f(ASK, "DATA-DELETE", f"{name} {what} deletes volumes or cached data that may hold databases.",
                          f"Check {name} system df and {name} volume ls first, and confirm with the user.", prod=True))
        if words[:1] == ["push"] or words[:2] == ["image", "push"]:
            out.append(_f(ASK, "PUBLISH", f"{name} push publishes an image to a registry."))
        return out
    if name == "vercel":
        pos = [a for a in args if not a.startswith("-")]
        if not pos or pos[0] in ("deploy", "promote") or "--prod" in args:
            return [_f(ASK, "DEPLOY", "Deploys to Vercel.", "Deployments need the user's explicit permission.")]
        return []
    if name == "gh":
        if args[:2] == ["release", "create"]:
            return [_f(ASK, "PUBLISH", "Creates a public GitHub release.")]
        return []
    if name == "yarn" and args[:2] == ["npm", "publish"]:
        return [_f(ASK, "PUBLISH", "Publishes a package to the npm registry.")]
    pos = [a for a in args if not a.startswith("-") or a in verbs]
    window = pos[:5] if name == "gcloud" else pos[:3]
    found = [v for v in window if v in verbs]
    if found:
        first = found[0]
        kind = "PUBLISH" if first in ("publish", "unpublish", "deprecate", "yank", "push", "upload") else "DEPLOY"
        return [_f(ASK, kind, f"{name} {first} changes something other people or production systems use.",
                   "Deployments and publishing need the user's explicit permission for this run.")]
    return []


SQL_RULES = [
    (re.compile(r"(?i)\bdrop\s+(database|schema|table|collection|keyspace)\b"), "drops a database, schema or table"),
    (re.compile(r"(?i)\btruncate\s+(table\s+)?[\w.\"`]+"), "truncates a table"),
    (re.compile(r"(?i)\balter\s+table\s+\S+\s+drop\b"), "drops a column or constraint"),
    (re.compile(r"(?i)\b(flushall|flushdb)\b"), "flushes a Redis database"),
    (re.compile(r"dropDatabase\s*\(|\.drop\s*\(\s*\)|deleteMany\s*\(\s*\{\s*\}\s*\)"), "drops or empties a collection"),
]


def _sql_findings(text: str) -> List[str]:
    hits = [desc for rx, desc in SQL_RULES if rx.search(text)]
    for stmt in re.split(r";", text):
        if re.search(r"(?i)\bdelete\s+from\s+\S+", stmt) and not re.search(r"(?i)\bwhere\b", stmt):
            hits.append("deletes every row of a table (DELETE without WHERE)")
        if re.search(r"(?i)\bupdate\s+\S+\s+set\b", stmt) and not re.search(r"(?i)\bwhere\b", stmt):
            hits.append("updates every row of a table (UPDATE without WHERE)")
    return hits


def check_database(name: str, args: List[str], cmd: Command, upstream: List[str]) -> List[Finding]:
    hits: List[str] = []
    joined = " ".join(args)
    if name == "dropdb":
        hits.append("drops a PostgreSQL database")
    if name == "mysqladmin" and "drop" in args:
        hits.append("drops a MySQL database")
    if name == "prisma" and (joined.startswith("migrate reset") or (
            "db push" in joined and ("--force-reset" in args or "--accept-data-loss" in args))):
        hits.append("resets the database and deletes its data")
    if name in ("rails", "rake") and any(a in ("db:drop", "db:reset", "db:purge", "db:schema:load", "db:truncate_all") for a in args):
        hits.append("drops or reloads the database")
    if (name.endswith("manage.py") or name == "django-admin" or any(a.endswith("manage.py") for a in args[:1])) \
            and any(a in ("flush", "reset_db", "sqlflush") for a in args):
        hits.append("deletes all data from the database")
    if name == "artisan" or "artisan" in args[:1]:
        if any(a in ("migrate:fresh", "migrate:reset", "db:wipe") for a in args):
            hits.append("drops all tables")
    if name == "alembic" and args[:2] == ["downgrade", "base"]:
        hits.append("rolls every migration back")
    if name in ("supabase",) and args[:2] == ["db", "reset"]:
        hits.append("resets the database")
    if any(a in ("db:drop", "schema:drop", "migrate:fresh") for a in args):
        hits.append("drops the database or schema")
    if name in DB_CLIENTS:
        texts = [joined] + [r.body for r in cmd.redirects if r.body] + upstream
        for t in texts:
            hits.extend(_sql_findings(t))
    if not hits:
        return []
    return [_f(ASK, "DB-DESTRUCTIVE", f"{name}: {hits[0]}; the data is gone unless a backup exists.",
               "Back up first (pg_dump, mysqldump or sqlite3 .backup), run the statement inside a transaction where the database supports it, and confirm with the user.",
               prod=True)]


def check_download_then_run(name: str, raw: str, args: List[str], cmd: Command, st: State) -> List[Finding]:
    """curl -o x.sh URL && bash x.sh, or a downloader piped into a shell."""
    out = []
    reads_stdin = False
    if name in SHELLS and not any(a.startswith("-") and not a.startswith("--") and "c" in a[1:] for a in args):
        reads_stdin = not [a for a in args if not a.startswith("-")] or "-s" in args or "-" in args
    elif name in STDIN_INTERPRETERS:
        reads_stdin = not args or args == ["-"]
    if reads_stdin:
        names = []
        for c in st.pipeline:
            if c.position >= cmd.position or not c.words:
                continue
            ws, _d, _e = unwrap(list(c.words), [])
            if ws:
                names.append(_basename(ws[0].text))
        if any(n in DOWNLOADERS for n in names):
            out.append(_f(DENY, "REMOTE-EXEC", "Pipes a script from the network straight into an interpreter, so nobody reads it before it runs.",
                          "Download to a file (curl -fsSLo install.sh URL), read it, verify a published checksum, then run it with the user's OK; prefer a package manager."))
    downloaded = set()
    for ename, eargs in st.earlier:
        if _basename(ename) in ("curl", "wget"):
            for j, a in enumerate(eargs):
                if a in ("-o", "--output", "-O", "--output-document") and j + 1 < len(eargs):
                    downloaded.add(posixpath.basename(eargs[j + 1]))
                elif a.startswith(("--output=", "--output-document=")):
                    downloaded.add(posixpath.basename(a.split("=", 1)[1]))
            urls = [a for a in eargs if a.startswith(("http://", "https://"))]
            if "-O" in eargs or _basename(ename) == "wget":
                downloaded.update(posixpath.basename(urlsplit(u).path) for u in urls if urlsplit(u).path)
    downloaded.discard("")
    if downloaded:
        runs = (name in SHELLS or name in STDIN_INTERPRETERS or name in ("chmod", "source", ".")) and any(
            posixpath.basename(a) in downloaded for a in args)
        runs = runs or posixpath.basename(raw) in downloaded
        if runs:
            out.append(_f(ASK, "REMOTE-EXEC-FILE", "Runs a script that was downloaded earlier in the same command, before anyone has read it.",
                          "Split the steps: download, read the script and verify its checksum, then run it with the user's OK."))
    return out


# --------------------------------------------------------------------------
# Public API


def evaluate_command(command: str, ctx: Optional[Context] = None) -> Result:
    ctx = ctx or make_context()
    findings = analyze_text(command, ctx, ctx.cwd, 0)
    text_for_prod = command
    for f in findings:
        if f.prod_sensitive and f.decision == ASK and PROD_RE.search(text_for_prod):
            f.decision = DENY
            f.reason += " The command names a production target."
    return combine(findings)


FILE_READ_TOOLS = {"Read", "Grep", "NotebookRead"}
FILE_WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def evaluate_file_tool(tool: str, path: str, ctx: Context) -> Result:
    t = resolve(Word(text=path), ctx, ctx.cwd)
    full = t.path if t.kind == "path" else path
    cls = secret_class(full)
    findings: List[Finding] = []
    if tool in FILE_READ_TOOLS:
        if cls == "key":
            findings.append(_f(DENY, "SECRET-READ", f"{tool} would put key or credential material ({path}) into the session log.",
                               "Check presence with ls -l; never read private keys or credential stores."))
        elif cls == "env":
            findings.append(_f(ASK, "SECRET-READ", f"{tool} would show the values in {path}.",
                               "List names only (cut -d= -f1) unless the user asked for the values."))
    if tool in FILE_WRITE_TOOLS:
        if cls == "key":
            findings.append(_f(ASK, "SECRET-WRITE", f"{tool} would modify key or credential material ({path})."))
        if t.kind == "path" and is_config_target(t.path, ctx):
            findings.append(_f(ASK, "CFG-CHANGE", f"{tool} would change {t.path}, which controls the agent, the shell, SSH access or git hooks.",
                               "Show the user the exact change first."))
    return combine(findings)


def evaluate_payload(payload: dict, ask_as_deny: bool = False,
                     protected: Optional[frozenset] = None) -> Optional[Result]:
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) and payload.get("cwd") else os.getcwd()
    project = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    ctx = make_context(cwd=cwd, project_root=project, protected=protected)
    if tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return combine([_f(ASK, "PARSE-UNCLEAR", "Hook payload has no command string.")])
        result = evaluate_command(command, ctx)
    elif tool in FILE_READ_TOOLS or tool in FILE_WRITE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("notebook_path")
        if not isinstance(path, str) or not path:
            return None
        result = evaluate_file_tool(tool, path, ctx)
    else:
        return None
    unattended = ask_as_deny or payload.get("permission_mode") in ("bypassPermissions", "dontAsk")
    if unattended and result.decision == ASK:
        for f in result.findings:
            if f.decision == ASK:
                f.decision = DENY
                f.reason += " (Converted from ask: no person is prompted in this session mode.)"
        result = combine(result.findings)
    return result


def hook_output(result: Optional[Result]) -> Optional[dict]:
    if result is None or result.decision == ALLOW:
        return None  # stay silent so the normal permission rules still apply
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": result.decision,
            "permissionDecisionReason": "agent-safety guard: " + result.summary(),
        }
    }


def format_text(result: Result) -> str:
    lines = [result.decision.upper()]
    for f in result.findings:
        lines.append(f"  {f.decision.upper():5} {f.rule}: {f.reason}")
        if f.safer:
            lines.append(f"        safer: {f.safer}")
    if not result.findings:
        lines.append("  No guard rule matched. Normal permission rules still apply.")
    return "\n".join(lines)


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # exit 64 so usage errors never look like "deny" (2)
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = _Parser(
        prog="guard_command.py",
        description=("Classify a proposed shell command as ALLOW, ASK or DENY. Reads the command "
                     "from the argument, or from stdin as plain text or a Claude Code PreToolUse JSON payload. "
                     "Never runs the command. A seatbelt, not a sandbox."),
        epilog=("Exit codes without --hook: 0 allow, 1 ask, 2 deny, 64 usage error. "
                "With --hook: always 0; ask/deny are printed as hookSpecificOutput JSON and allow prints nothing."),
    )
    parser.add_argument("command", nargs="?", help="shell command to check (omit to read stdin)")
    parser.add_argument("--hook", action="store_true", help="read a PreToolUse JSON payload on stdin and answer in hook format")
    parser.add_argument("--json", action="store_true", help="print a JSON result instead of text")
    parser.add_argument("--cwd", help="directory the command would run in (default: current directory)")
    parser.add_argument("--project-root", help="project boundary (default: --cwd)")
    parser.add_argument("--protected-branch", action="append", default=[], metavar="NAME",
                        help="extra branch name to treat as protected (repeatable)")
    parser.add_argument("--ask-as-deny", action="store_true", help="unattended mode: turn every ask into deny")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    protected = DEFAULT_PROTECTED | frozenset(args.protected_branch)
    if args.hook:
        try:
            raw = sys.stdin.read(MAX_INPUT * 4 + 1)
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            result = evaluate_payload(payload, ask_as_deny=args.ask_as_deny, protected=protected)
        except Exception as exc:  # fail toward a person, never toward silent approval
            decision = DENY if args.ask_as_deny else ASK
            result = combine([_f(decision, "GUARD-ERROR", f"The guard could not read the hook payload ({type(exc).__name__}).")])
        out = hook_output(result)
        if out is not None:
            sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
        return 0

    command = args.command
    if command is None:
        data = sys.stdin.read(MAX_INPUT * 4 + 1)
        try:
            maybe = json.loads(data)
        except ValueError:
            maybe = None
        if isinstance(maybe, dict) and "tool_input" in maybe:
            result = evaluate_payload(maybe, ask_as_deny=args.ask_as_deny, protected=protected) or combine([])
            print(json.dumps(result.to_dict(), sort_keys=True) if args.json else format_text(result))
            return EXIT_CODES[result.decision]
        command = data.rstrip("\n")
    ctx = make_context(cwd=args.cwd, project_root=args.project_root or args.cwd, protected=protected)
    result = evaluate_command(command, ctx)
    if args.ask_as_deny and result.decision == ASK:
        for f in result.findings:
            if f.decision == ASK:
                f.decision = DENY
        result = combine(result.findings)
    print(json.dumps(result.to_dict(), sort_keys=True) if args.json else format_text(result))
    return EXIT_CODES[result.decision]


if __name__ == "__main__":
    sys.exit(main())
