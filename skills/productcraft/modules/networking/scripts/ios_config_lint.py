#!/usr/bin/env python3
"""ProductCraft Networking: offline security lint for Cisco IOS and IOS-XE style configurations.

Reads a saved running configuration (or a candidate snippet) and lists the
management-plane weaknesses a reviewer should fix: Telnet on VTY lines, SSH
version 2 not enforced, passwords in clear text or reversible type 7, weak
password hashes, accounts without passwords, missing AAA, remote logging, log
timestamps or NTP, VTY lines without a source ACL or idle timeout, the plain
HTTP management server, SNMP default or writable communities, and physical
interfaces that look unused but are not shut down.

Produce the input with `show running-config` captured to a file. The file
holds password hashes, type 7 strings, keys and SNMP communities: keep it out
of version control and shared tickets, and delete it after the review.

The script never prints a secret value. Each finding shows the line number and
the command with everything after a secret-bearing keyword replaced by
<redacted>. It never connects to a device, never uses the network and never
changes any file. Findings are prompts for review; a clean result does not
make a configuration secure, and pattern checks are not a full IOS parser.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
SEVERITY_ORDER = {"HIGH": 0, "WARN": 1, "INFO": 2}
FAIL_LEVELS = {"high": 0, "warn": 1, "info": 2, "none": -1}


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    title: str


RULE_LIST = [
    Rule("TELNET_ENABLED", "HIGH", "VTY lines accept Telnet, which sends credentials in clear text. Use `transport input ssh`."),
    Rule("SSH_V1", "HIGH", "SSH version 1 is configured; it is broken. Use `ip ssh version 2`."),
    Rule("PLAINTEXT_SECRET", "HIGH", "A password or key is stored in clear text (type 0 or no type). Use a hashed secret or a type 6 key."),
    Rule("TYPE7_SECRET", "HIGH", "A password or key uses type 7, which anyone can reverse. Use `secret` with scrypt (type 9) or type 6 keys."),
    Rule("BROKEN_HASH", "HIGH", "A secret uses type 4, a flawed hash Cisco deprecated. Re-set it with `algorithm-type scrypt`."),
    Rule("NO_PASSWORD_ACCOUNT", "HIGH", "A local account has no password (`nopassword`)."),
    Rule("VTY_NO_LOGIN", "HIGH", "VTY lines have `no login`: remote sessions get a prompt without authentication."),
    Rule("SNMP_DEFAULT_COMMUNITY", "HIGH", "An SNMP community uses a well-known default name (public or private)."),
    Rule("SNMP_RW_COMMUNITY", "HIGH", "An SNMP community has write access (RW); anyone with the string can change the device."),
    Rule("SSH_V2_NOT_SET", "WARN", "`ip ssh version 2` is not set; images that still support SSH version 1 accept it. `show ip ssh` shows the active version."),
    Rule("VTY_TRANSPORT_DEFAULT", "WARN", "VTY lines have no `transport input`; the default differs by platform and release, and older images allow Telnet. Confirm with `show running-config all | section line vty`."),
    Rule("VTY_NO_ACL", "WARN", "VTY lines have no `access-class ... in`; any address that reaches the device can try to log in."),
    Rule("VTY_NO_TIMEOUT", "WARN", "VTY lines have `exec-timeout 0`: idle sessions never close."),
    Rule("MD5_HASH", "WARN", "A secret uses type 5 (salted MD5). Re-set it with `algorithm-type scrypt` (type 9) or sha256 (type 8)."),
    Rule("NO_AAA", "WARN", "`aaa new-model` is absent: no central authentication, per-command authorization or accounting."),
    Rule("NO_REMOTE_LOGGING", "WARN", "No remote syslog server (`logging host`); logs are lost on reload and cannot be correlated."),
    Rule("NO_NTP", "WARN", "No NTP server; log and certificate timestamps cannot be trusted or correlated."),
    Rule("SNMP_V2C", "WARN", "An SNMPv1/v2c community is configured; the string crosses the network in clear text. Prefer SNMPv3 with authPriv."),
    Rule("HTTP_SERVER", "WARN", "The plain HTTP management server is enabled (`ip http server`). Disable it, or use the HTTPS server only where needed."),
    Rule("PORT_NOT_CONNECTED", "WARN", "A physical interface is not connected (per the status file) but is not shut down."),
    Rule("NO_TIMESTAMPS", "INFO", "`service timestamps log datetime` is absent; log lines lack wall-clock time."),
    Rule("AAA_NO_LOCAL_FALLBACK", "INFO", "A login method list uses only servers; if they are unreachable nobody can log in. Add `local` as the last method."),
    Rule("PORT_UNCONFIGURED", "INFO", "A physical interface has no description, address, VLAN or channel settings and is not shut down; confirm with `show interfaces status`."),
]
RULES = {r.code: r for r in RULE_LIST}

# Codes that report something missing; skipped with --snippet.
ABSENCE_CODES = frozenset({
    "SSH_V2_NOT_SET", "VTY_TRANSPORT_DEFAULT", "VTY_NO_ACL", "NO_AAA", "NO_REMOTE_LOGGING",
    "NO_NTP", "NO_TIMESTAMPS", "PORT_NOT_CONNECTED", "PORT_UNCONFIGURED",
})

# Everything after one of these tokens is hidden when a command is printed.
REDACT_AFTER = frozenset({
    "password", "secret", "key", "key-string", "community", "authentication-key", "md5", "sha",
    "sha1", "auth", "priv", "pre-shared-key", "ascii", "hex", "server-key", "encrypted",
    "hmac-sha2-256", "cmac-aes-128", "text",
})

PHYSICAL_TYPES = (
    "FastEthernet", "GigabitEthernet", "TwoGigabitEthernet", "FiveGigabitEthernet",
    "TenGigabitEthernet", "TwentyFiveGigE", "FortyGigabitEthernet", "FiftyGigE",
    "HundredGigE", "TwoHundredGigE", "FourHundredGigE", "Ethernet",
)
# Abbreviations that are ambiguous as plain prefixes, as IOS prints them.
ABBREVIATIONS = {
    "fa": "FastEthernet", "gi": "GigabitEthernet", "tw": "TwoGigabitEthernet",
    "twe": "TwentyFiveGigE", "fi": "FiveGigabitEthernet", "te": "TenGigabitEthernet",
    "fo": "FortyGigabitEthernet", "hu": "HundredGigE", "et": "Ethernet", "eth": "Ethernet",
}
NAME_RE = re.compile(r"^([A-Za-z][A-Za-z\-]*?)(\d[\d/:.]*)$")
HEX_RE = re.compile(r"^[0-9A-Fa-f]{4,}$")
IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
BANNER_RE = re.compile(r"^banner\s+(?:motd|login|exec|incoming|slip-ppp|prompt-timeout|config-save)\s+(.*)$", re.I)
BRIEF_RE = re.compile(
    r"^(?P<name>\S+)\s+\S+\s+(?:YES|NO)\s+\S+\s+(?P<status>administratively\s+down|up|down|deleted)\s+(?:up|down)\b", re.I)
TABLE_RE = re.compile(
    r"^(?P<name>[A-Za-z][\w\-]*\d\S*)\s.*\s(?P<status>connected|notconnect|disabled|err-disabled|monitoring|inactive"
    r"|sfpAbsent|xcvrAbsent|noOperMem|suspended)\s+\S+\s+\S+\s+\S+", re.I)
NOT_CONNECTED = frozenset({"notconnect", "down", "sfpabsent", "xcvrabsent"})
FALLBACK_METHODS = frozenset({"local", "local-case", "enable", "line"})


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    line: int
    context: str
    message: str

    def sort_key(self) -> Tuple[int, int, str]:
        return (SEVERITY_ORDER[self.severity], self.line, self.code)

    def as_dict(self) -> Dict[str, object]:
        return {"severity": self.severity, "code": self.code, "line": self.line,
                "context": self.context, "message": self.message}


@dataclass
class Block:
    line: int
    header: str
    children: List[Tuple[int, str]]


class InputError(Exception):
    pass


def redact(text: str) -> str:
    """Return the command with every token after a secret-bearing keyword hidden."""
    tokens = text.split()
    if len(tokens) >= 3 and tokens[0].lower() == "snmp-server" and tokens[1].lower() == "host":
        return " ".join(tokens[:3] + ["<redacted>"]) if len(tokens) > 3 else " ".join(tokens)
    out: List[str] = []
    for index, token in enumerate(tokens):
        out.append(token)
        if token.lower() in REDACT_AFTER and index + 1 < len(tokens):
            out.append("<redacted>")
            break
    return " ".join(out)


def parse(text: str) -> Tuple[List[Tuple[int, str]], List[Block]]:
    """Split a configuration into top-level lines and blocks, skipping banner bodies."""
    top: List[Tuple[int, str]] = []
    blocks: List[Block] = []
    current: Optional[Block] = None
    delimiter: Optional[str] = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r\n").rstrip()
        if delimiter is not None:
            if delimiter in line:
                delimiter = None
            continue
        if not line.strip() or line.strip().startswith("!"):
            continue
        if line[0] in " \t":
            if current is not None:
                current.children.append((number, line.strip()))
            continue
        current = None
        banner = BANNER_RE.match(line)
        if banner:
            rest = banner.group(1)
            if rest:
                mark = "^C" if rest.startswith("^C") else rest[0]
                if mark not in rest[len(mark):]:
                    delimiter = mark
            continue
        top.append((number, line))
        current = Block(number, line, [])
        blocks.append(current)
    return top, blocks


def typed_value(tokens: Sequence[str], index: int) -> Optional[str]:
    """Classify the value after tokens[index]: 'plain', 'type7', 'ok' or None (nothing to judge)."""
    if index + 1 >= len(tokens):
        return None
    nxt = tokens[index + 1]
    if len(nxt) == 1 and nxt.isdigit():
        if index + 2 >= len(tokens):
            return None
        if nxt == "0":
            return "plain"
        if nxt == "7":
            return "type7"
        return "ok"
    return "plain"


def hash_type(tokens: Sequence[str], index: int) -> Optional[str]:
    """Classify the value after a 'secret' keyword at tokens[index]."""
    if index + 1 >= len(tokens):
        return None
    nxt = tokens[index + 1]
    if len(nxt) == 1 and nxt.isdigit():
        if index + 2 >= len(tokens):
            return None
        return {"0": "PLAINTEXT_SECRET", "4": "BROKEN_HASH", "5": "MD5_HASH", "7": "TYPE7_SECRET"}.get(nxt)
    return "PLAINTEXT_SECRET"


def skip_level(tokens: Sequence[str], index: int) -> int:
    """Return the index of the keyword after an optional 'level N'."""
    if index + 2 < len(tokens) and tokens[index + 1].lower() == "level":
        return index + 2
    return index


VALUE_CODES = {"plain": "PLAINTEXT_SECRET", "type7": "TYPE7_SECRET"}


def secret_codes(tokens: Sequence[str], parent: str) -> List[str]:
    """Return the credential findings for one command (tokens) inside block `parent`."""
    low = [t.lower() for t in tokens]
    codes: List[str] = []
    if not low or low[0] == "no":
        return codes

    def add(kind: Optional[str]) -> None:
        if kind in VALUE_CODES:
            codes.append(VALUE_CODES[kind])
        elif kind in RULES:
            codes.append(kind)

    if low[0] == "enable" and len(low) > 1:
        if low[1] == "password":
            index = skip_level(low, 1)
            kind = typed_value(tokens, index)
            add("type7" if kind == "type7" else "plain" if kind else None)
        elif "secret" in low:
            add(hash_type(tokens, skip_level(low, low.index("secret"))))
        return codes
    if low[0] == "username":
        if "nopassword" in low:
            codes.append("NO_PASSWORD_ACCOUNT")
        if "password" in low:
            add(typed_value(tokens, low.index("password")))
        if "secret" in low:
            add(hash_type(tokens, low.index("secret")))
        return codes
    if low[0] == "snmp-server" and len(low) > 3 and low[1] == "user" and "encrypted" not in low:
        if "auth" in low:
            codes.append("PLAINTEXT_SECRET")
        return codes
    if low[0] == "ntp" and len(low) >= 5 and low[1] == "authentication-key":
        if len(low) > 5 and low[5] == "7":
            codes.append("TYPE7_SECRET")
        elif len(low) == 5:
            codes.append("PLAINTEXT_SECRET")
        return codes

    parent_low = parent.lower()
    in_line = parent_low.startswith("line ")
    in_aaa_server = parent_low.startswith(("tacacs server", "radius server", "aaa server"))
    for index, word in enumerate(low):
        kind: Optional[str] = None
        if word == "password":
            if index + 1 < len(low) and low[index + 1] in ("encryption", "restriction"):
                continue
            if in_line and index == 0:
                kind = typed_value(tokens, index)
            elif low[0] == "neighbor" or (low[0] == "ppp" and index > 0):
                kind = typed_value(tokens, index)
            elif typed_value(tokens, index) in ("type7",) or (index + 1 < len(low) and low[index + 1] == "0"):
                kind = typed_value(tokens, index)
        elif word in ("key-string", "authentication-key"):
            kind = typed_value(tokens, index)
        elif word == "key":
            if (index == 0 and in_aaa_server) or low[:2] in (["tacacs-server", "key"], ["radius-server", "key"]) \
                    or low[:3] == ["crypto", "isakmp", "key"]:
                kind = typed_value(tokens, index)
            elif index + 2 < len(low) and low[index + 1] == "7" and HEX_RE.match(tokens[index + 2]):
                kind = "type7"
        elif word == "server-key" and in_aaa_server:
            kind = typed_value(tokens, index)
        elif word == "pre-shared-key":
            offset = index + 1 if index + 1 < len(low) and low[index + 1] in ("local", "remote") else index
            kind = typed_value(tokens, offset)
        elif word == "md5" and index >= 2 and low[index - 2] == "message-digest-key":
            kind = typed_value(tokens, index)
        elif word in ("ascii", "hex") and index > 0 and low[index - 1] == "wpa-psk":
            kind = typed_value(tokens, index)
        elif word == "7" and index > 0 and index + 1 < len(low) and HEX_RE.match(tokens[index + 1]) \
                and low[index - 1] in ("password", "secret", "key", "key-string", "authentication-key", "md5"):
            kind = "type7"
        if kind in VALUE_CODES and VALUE_CODES[kind] not in codes:
            codes.append(VALUE_CODES[kind])
    return codes


def canonical(name: str) -> str:
    """Expand an interface name such as Gi1/0/1 to GigabitEthernet1/0/1 for matching."""
    match = NAME_RE.match(name.strip())
    if not match:
        return name.strip().lower()
    prefix, rest = match.group(1).lower(), match.group(2)
    full = ABBREVIATIONS.get(prefix)
    if full is None:
        candidates = [t for t in PHYSICAL_TYPES if t.lower().startswith(prefix)]
        full = candidates[0] if len(candidates) == 1 else match.group(1)
    return (full + rest).lower()


def is_physical(name: str) -> bool:
    if "." in name:
        return False
    match = NAME_RE.match(name)
    return bool(match) and match.group(1).lower() in {t.lower() for t in PHYSICAL_TYPES}


def parse_status(text: str) -> Dict[str, str]:
    """Read `show interfaces status` or `show ip interface brief` output into {canonical name: status}."""
    status: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        match = BRIEF_RE.match(line) or TABLE_RE.match(line)
        if match:
            value = re.sub(r"\s+", " ", match.group("status").lower())
            status[canonical(match.group("name"))] = value
    return status


SERVICE_PREFIXES = (
    "description", "ip address", "ipv6 address", "switchport access vlan", "switchport trunk",
    "switchport mode trunk", "channel-group", "vrf forwarding", "ip vrf forwarding", "encapsulation",
    "service-policy", "xconnect", "standby", "vrrp", "ip helper-address", "switchport voice vlan",
    "mpls", "pseudowire", "service instance",
)


def check_interface(block: Block, status: Dict[str, str]) -> Optional[Tuple[str, str]]:
    name = block.header.split(None, 1)[1].strip() if len(block.header.split()) > 1 else ""
    if not is_physical(name):
        return None
    children = [c.lower() for _, c in block.children]
    if "shutdown" in children:
        return None
    state = status.get(canonical(name))
    if state is not None:
        if state in NOT_CONNECTED:
            return ("PORT_NOT_CONNECTED", f"{name} reports '{state}' but is not shut down; shut it down and park it in an unused VLAN.")
        return None
    if any(c.startswith(SERVICE_PREFIXES) for c in children):
        return None
    return ("PORT_UNCONFIGURED", f"{name} has no description, address, VLAN or channel settings and is not shut down.")


def lint(text: str, snippet: bool = False, status: Optional[Dict[str, str]] = None) -> List[Finding]:
    status = status or {}
    top, blocks = parse(text)
    findings: List[Finding] = []
    seen = set()

    def add(code: str, line: int, context: str, message: Optional[str] = None) -> None:
        if snippet and code in ABSENCE_CODES:
            return
        key = (code, line)
        if key in seen:
            return
        seen.add(key)
        rule = RULES[code]
        findings.append(Finding(rule.severity, code, line, redact(context) if context else "(not present)",
                                message or rule.title))

    top_low = [(n, l.strip().lower()) for n, l in top]
    has = lambda pattern: any(re.match(pattern, l) for _, l in top_low)  # noqa: E731

    # Credentials on every line, with the block each line belongs to.
    for number, line in top:
        for code in secret_codes(line.split(), ""):
            add(code, number, line)
    for block in blocks:
        for number, line in block.children:
            for code in secret_codes(line.split(), block.header):
                add(code, number, line)

    # SSH version.
    for number, line in top_low:
        if re.match(r"^ip ssh version 1\b", line):
            add("SSH_V1", number, line)
    if not has(r"^ip ssh version 2\b"):
        add("SSH_V2_NOT_SET", 0, "")

    # VTY lines.
    for block in blocks:
        if not re.match(r"^line vty\b", block.header.strip(), re.I):
            continue
        kids = [(n, c.lower()) for n, c in block.children]
        transport = [(n, c) for n, c in kids if c.startswith("transport input")]
        for number, line in transport:
            words = line.split()[2:]
            if "telnet" in words or "all" in words:
                add("TELNET_ENABLED", number, line)
        if not transport:
            add("VTY_TRANSPORT_DEFAULT", block.line, block.header)
        if not any(re.match(r"^(ipv6 )?access-class \S+ in\b", c) for _, c in kids):
            add("VTY_NO_ACL", block.line, block.header)
        for number, line in kids:
            if line == "no login":
                add("VTY_NO_LOGIN", number, line)
            if re.match(r"^exec-timeout 0(\s+0)?$", line):
                add("VTY_NO_TIMEOUT", number, line)

    # AAA.
    if not has(r"^aaa new-model\b"):
        add("NO_AAA", 0, "")
    for number, line in top_low:
        if line.startswith("aaa authentication login "):
            methods = line.split()[4:]
            if "group" in methods and not FALLBACK_METHODS.intersection(methods):
                add("AAA_NO_LOCAL_FALLBACK", number, line)

    # Logging and time.
    if not has(r"^logging (host \S+|\d{1,3}(\.\d{1,3}){3}\b|[0-9a-f]*:[0-9a-f:]+)"):
        add("NO_REMOTE_LOGGING", 0, "")
    if not has(r"^service timestamps log datetime\b"):
        add("NO_TIMESTAMPS", 0, "")
    if not has(r"^(ntp (server|peer)|sntp server)\b"):
        add("NO_NTP", 0, "")

    # HTTP server.
    for number, line in top_low:
        if line == "ip http server":
            add("HTTP_SERVER", number, line)

    # SNMP communities.
    for number, line in top:
        tokens = line.split()
        low = [t.lower() for t in tokens]
        if len(low) >= 3 and low[:2] == ["snmp-server", "community"]:
            if low[2] in ("public", "private"):
                add("SNMP_DEFAULT_COMMUNITY", number, line)
            rest = low[3:]
            if "rw" in rest:
                add("SNMP_RW_COMMUNITY", number, line)
            remaining: List[str] = []
            skip = False
            for i, word in enumerate(rest):
                if skip:
                    skip = False
                    continue
                if word == "view":
                    skip = True
                    continue
                if word in ("ro", "rw"):
                    continue
                remaining.append(word)
            message = RULES["SNMP_V2C"].title
            if not remaining:
                message += " No ACL limits who may use this community."
            add("SNMP_V2C", number, line, message)
        elif len(low) >= 4 and low[:2] == ["snmp-server", "host"]:
            index = 3
            while index < len(low):
                word = low[index]
                if word in ("vrf",):
                    index += 2
                    continue
                if word in ("informs", "traps"):
                    index += 1
                    continue
                if word == "version":
                    if index + 1 < len(low) and low[index + 1] == "3":
                        index = len(low)
                        break
                    index += 2
                    continue
                break
            if index < len(low) and low[index] in ("public", "private"):
                add("SNMP_DEFAULT_COMMUNITY", number, line)

    # Physical interfaces.
    if not snippet:
        for block in blocks:
            if block.header.lower().startswith("interface "):
                result = check_interface(block, status)
                if result:
                    add(result[0], block.line, block.header, result[1])

    return sorted(findings, key=Finding.sort_key)


def read_text(path: str) -> str:
    try:
        if path == "-":
            data = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as handle:
                data = handle.read()
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
    if b"\x00" in data:
        raise InputError(f"{path} is not a text file")
    text = data.decode("utf-8", errors="replace")
    if not text.strip():
        raise InputError(f"{path} is empty")
    return text


def summarize(findings: Sequence[Finding]) -> Dict[str, int]:
    counts = {"HIGH": 0, "WARN": 0, "INFO": 0}
    for f in findings:
        counts[f.severity] += 1
    return counts


def render_text(results: Sequence[Tuple[str, str, List[Finding]]]) -> str:
    lines: List[str] = []
    for path, mode, findings in results:
        lines.append(f"ios_config_lint {VERSION}: {path} ({mode})")
        if not findings:
            lines.append("  No findings. Pattern checks only: review the configuration itself before calling it secure.")
        for f in findings:
            where = f"line {f.line}" if f.line else "whole file"
            lines.append(f"  {f.severity:<5} {f.code:<22} {where:<10} {f.context}")
            lines.append(f"        {f.message}")
        counts = summarize(findings)
        lines.append(f"  Summary: {counts['HIGH']} HIGH, {counts['WARN']} WARN, {counts['INFO']} INFO.")
    return "\n".join(lines) + "\n"


def render_json(results: Sequence[Tuple[str, str, List[Finding]]]) -> str:
    doc = {"tool": "ios_config_lint", "version": VERSION, "files": [
        {"path": path, "mode": mode, "summary": summarize(findings),
         "findings": [f.as_dict() for f in findings]} for path, mode, findings in results]}
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def list_rules() -> str:
    lines = [f"{r.severity:<5} {r.code:<22} {r.title}" for r in sorted(RULE_LIST, key=lambda r: (SEVERITY_ORDER[r.severity], r.code))]
    lines.append("")
    lines.append("Skipped with --snippet: " + ", ".join(sorted(ABSENCE_CODES)))
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ios_config_lint.py",
        description="Offline security lint for Cisco IOS and IOS-XE style configurations. "
                    "Reads saved files only, never connects to a device and never prints secret values.",
        epilog="Exit codes: 0 report written with no finding at or above --fail-on; 1 findings at or above "
               "--fail-on; 2 usage or input error.")
    parser.add_argument("configs", nargs="*", metavar="CONFIG", help="saved configuration file(s); '-' reads stdin")
    parser.add_argument("--snippet", action="store_true",
                        help="the input is a partial candidate change: skip checks for missing settings and unused ports")
    parser.add_argument("--status", metavar="FILE",
                        help="saved 'show interfaces status' or 'show ip interface brief' output, to confirm unused ports")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--fail-on", choices=sorted(FAIL_LEVELS), default="high",
                        help="lowest severity that makes the exit code 1 (default: high)")
    parser.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if args.list_rules:
        sys.stdout.write(list_rules())
        return 0
    if not args.configs:
        parser.print_usage(sys.stderr)
        sys.stderr.write("ios_config_lint.py: error: give at least one configuration file\n")
        return 2
    try:
        status = parse_status(read_text(args.status)) if args.status else {}
        results = []
        for path in args.configs:
            text = read_text(path)
            mode = "snippet" if args.snippet else "full configuration"
            if not args.snippet and not re.search(r"^hostname\s", text, re.M):
                sys.stderr.write(f"note: {path} has no 'hostname' line; if it is a partial change, use --snippet\n")
            results.append((path, mode, lint(text, snippet=args.snippet, status=status)))
    except InputError as exc:
        sys.stderr.write(f"ios_config_lint.py: error: {exc}\n")
        return 2
    sys.stdout.write(render_json(results) if args.json else render_text(results))
    threshold = FAIL_LEVELS[args.fail_on]
    worst = [SEVERITY_ORDER[f.severity] for _, _, fs in results for f in fs]
    return 1 if threshold >= 0 and any(level <= threshold for level in worst) else 0


if __name__ == "__main__":
    sys.exit(main())
