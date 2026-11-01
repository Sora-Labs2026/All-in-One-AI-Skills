#!/usr/bin/env python3
"""ProductCraft EVM client helper. Offline, read-only, deterministic, standard library only.

Commands:

  hash TEXT [--hex]        Keccak-256 (Ethereum) and FIPS SHA3-256 of TEXT, side by side,
                           so a wrong hash in a codebase can be identified. --hex treats TEXT
                           as 0x-prefixed bytes instead of UTF-8 text. --expect HEX names
                           which algorithm produced a given digest.
  selector SIG [SIG ...]   4-byte function or error selector of each signature. Parameter
                           names, data locations and `indexed` are dropped; uint and int
                           become uint256 and int256; the canonical form is printed.
  topic SIG [SIG ...]      Event topic 0 (full Keccak-256 of the canonical signature).
  checksum ADDR [ADDR ...] EIP-55 check. Input equal to its checksummed form is valid; other
                           mixed-case input is invalid; other all-lower or all-upper input
                           carries no checksum and is reported as unchecked.
  units AMOUNT --decimals N [--to base|display]
                           Exact conversion between a display amount ("1.5") and integer
                           base units ("1500000" for 6 decimals). Excess precision and
                           values outside uint256 are errors, never rounded.
  scan --root DIR          Lead finder for JavaScript, TypeScript and Python client code:

    NODE-SHA3            high    Node crypto sha3-256 (FIPS SHA3) where Ethereum needs Keccak-256
    PY-SHA3              high    hashlib sha3_256 in a file that also handles Ethereum data
    JS-FLOAT-AMOUNT      medium  parseFloat or Number() on a line that handles token amounts
    JS-FLOAT-SCALE       medium  1e18-style literals, Math.pow(10, ...) or 10 ** n without bigint
    PY-FLOAT-AMOUNT      medium  float() or division by 1e18-style literals on token amounts
    HARDCODED-DECIMALS   low     decimals fixed to 6, 8 or 18 in code instead of read per token

Leads are not findings: read the code and confirm each one with a test. The tool
never uses the network, never modifies files and never prints file contents.
Acknowledge a reviewed line with a comment on the same line or the line above:
evm-check: ignore RULE-ID <reason>

Exit codes: 0 success or no lead at or above --fail-on; 1 invalid checksum, precision
loss, value out of range or a lead at or above --fail-on; 2 usage or input error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"
UINT256_MAX = 2**256 - 1
LEVELS = ("high", "medium", "low")
LEVEL_RANK = {name: rank for rank, name in enumerate(LEVELS)}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "build", "dist", "out", ".venv", "venv", "__pycache__",
    ".next", ".cache", ".turbo", "coverage", "vendor", "artifacts", "cache", "typechain-types", "lib",
}
JS_EXT = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx"}
PY_EXT = {".py"}
MAX_FILE_BYTES = 2_000_000

# --------------------------------------------------------------------------- Keccak sponge

_MASK = (1 << 64) - 1


def _round_constants() -> list[int]:
    def rc_bit(t: int) -> int:
        r = 1
        for _ in range(t % 255):
            r <<= 1
            if r & 0x100:
                r ^= 0x171
        return r & 1

    out = []
    for rnd in range(24):
        value = 0
        for j in range(7):
            value |= rc_bit(j + 7 * rnd) << ((1 << j) - 1)
        out.append(value)
    return out


def _rotation_offsets() -> list[int]:
    rot = [0] * 25
    x, y = 1, 0
    for t in range(24):
        rot[x + 5 * y] = ((t + 1) * (t + 2) // 2) % 64
        x, y = y, (2 * x + 3 * y) % 5
    return rot


_RC = _round_constants()
_ROT = _rotation_offsets()


def _rol(value: int, shift: int) -> int:
    shift %= 64
    return ((value << shift) | (value >> (64 - shift))) & _MASK if shift else value


def _keccak_f(a: list[int]) -> list[int]:
    for rnd in range(24):
        c = [a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [a[i] ^ d[i % 5] for i in range(25)]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol(a[x + 5 * y], _ROT[x + 5 * y])
        a = [b[i] ^ ((~b[(i % 5 + 1) % 5 + 5 * (i // 5)]) & b[(i % 5 + 2) % 5 + 5 * (i // 5)]) for i in range(25)]
        a[0] ^= _RC[rnd]
    return a


def _sponge(data: bytes, pad_byte: int, rate: int = 136, out_len: int = 32) -> bytes:
    padded = bytearray(data)
    padded.append(pad_byte)
    while len(padded) % rate:
        padded.append(0)
    padded[-1] |= 0x80
    state = [0] * 25
    for off in range(0, len(padded), rate):
        block = padded[off:off + rate]
        for i in range(rate // 8):
            state[i] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        state = _keccak_f(state)
    out = b"".join(lane.to_bytes(8, "little") for lane in state)
    return out[:out_len]


def keccak256(data: bytes) -> bytes:
    """Original Keccak-256 as used by Ethereum (padding byte 0x01)."""
    return _sponge(data, 0x01)


def sha3_256_reference(data: bytes) -> bytes:
    """FIPS 202 SHA3-256 through the same sponge (padding byte 0x06); used to self-check."""
    return _sponge(data, 0x06)


# --------------------------------------------------------------------------- signatures

_LOCATIONS = {"memory", "calldata", "storage", "indexed", "payable"}
_INT_ALIAS = re.compile(r"^(u?int)(\[.*\])?$")


class SigError(ValueError):
    pass


def _split_top(params: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in params:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise SigError("unbalanced parentheses")
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if depth != 0:
        raise SigError("unbalanced parentheses")
    tail = "".join(cur)
    if parts or tail.strip():
        parts.append(tail)
    return parts


def _canon_type(param: str) -> str:
    param = param.strip()
    if not param:
        raise SigError("empty parameter")
    if param.startswith("tuple("):
        param = param[5:]
    if param.startswith("("):
        depth = 0
        for idx, ch in enumerate(param):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0:
                break
        inner, rest = param[1:idx], param[idx + 1:]
        arrays = re.match(r"^\s*((?:\[\d*\])*)", rest).group(1).replace(" ", "")
        return "(" + ",".join(_canon_type(p) for p in _split_top(inner)) + ")" + arrays
    tokens = param.split()
    head = tokens[0]
    for tok in tokens[1:]:
        if tok.startswith("[") and re.fullmatch(r"(\[\d*\])+", tok):
            head += tok
        else:
            break
    match = _INT_ALIAS.match(head)
    if match:
        head = match.group(1) + "256" + (match.group(2) or "")
    if head in _LOCATIONS or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\[\d*\])*", head):
        raise SigError(f"cannot read a type from parameter '{param}'")
    return head


def canonical_signature(sig: str) -> str:
    text = sig.strip().rstrip(";")
    text = re.sub(r"^(function|event|error)\s+", "", text)
    match = re.match(r"^([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", text)
    if not match:
        raise SigError("expected name(type,...)")
    name, start = match.group(1), match.end() - 1
    depth = 0
    for idx in range(start, len(text)):
        depth += text[idx] == "("
        depth -= text[idx] == ")"
        if depth == 0:
            break
    else:
        raise SigError("unbalanced parentheses")
    inner = text[start + 1:idx]
    return name + "(" + ",".join(_canon_type(p) for p in _split_top(inner)) + ")"


# --------------------------------------------------------------------------- addresses

_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def to_checksum(address: str) -> str:
    body = address[2:].lower()
    digest = keccak256(body.encode("ascii")).hex()
    return "0x" + "".join(ch.upper() if ch.isalpha() and int(digest[i], 16) >= 8 else ch for i, ch in enumerate(body))


def check_address(address: str) -> dict:
    if not _ADDR_RE.match(address):
        return {"input": address, "status": "malformed", "checksummed": None}
    expected = to_checksum(address)
    body = address[2:]
    if address == expected:
        status = "valid"
    elif body == body.lower() or body == body.upper():
        status = "unchecked"
    else:
        status = "invalid"
    return {"input": address, "status": status, "checksummed": expected}


# --------------------------------------------------------------------------- units

_DISPLAY_RE = re.compile(r"^(\d+)(?:\.(\d+))?$")


class UnitsError(ValueError):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def to_base(amount: str, decimals: int) -> int:
    text = amount.strip().replace("_", "")
    match = _DISPLAY_RE.match(text)
    if not match:
        raise UnitsError("amount must be a plain non-negative decimal such as 1.5 (no exponent, sign or separators)", 2)
    whole, frac = match.group(1), match.group(2) or ""
    stripped = frac.rstrip("0")
    if len(stripped) > decimals:
        raise UnitsError(f"{len(stripped)} significant fractional digits but the token has {decimals} decimals; refusing to round", 1)
    value = int(whole) * 10**decimals + (int(stripped.ljust(decimals, "0")) if decimals else 0)
    if value > UINT256_MAX:
        raise UnitsError("value exceeds uint256", 1)
    return value


def to_display(base: str, decimals: int) -> str:
    text = base.strip().replace("_", "")
    if not text.isascii() or not text.isdigit():
        raise UnitsError("base units must be a non-negative integer", 2)
    value = int(text)
    if value > UINT256_MAX:
        raise UnitsError("value exceeds uint256", 1)
    if decimals == 0:
        return str(value)
    whole, frac = divmod(value, 10**decimals)
    frac_text = str(frac).rjust(decimals, "0").rstrip("0")
    return f"{whole}.{frac_text}" if frac_text else str(whole)


# --------------------------------------------------------------------------- scan

RULES = {
    "NODE-SHA3": ("high", "Node's sha3-256 is FIPS SHA3, not Ethereum's Keccak-256; selectors, topics, slots and addresses come out wrong. Use keccak256 from ethers, viem or @noble/hashes."),
    "PY-SHA3": ("high", "hashlib.sha3_256 is FIPS SHA3, not Keccak-256. Use eth_hash or eth_utils keccak, or Crypto.Hash.keccak with digest_bits=256."),
    "JS-FLOAT-AMOUNT": ("medium", "Token amounts exceed 2**53; parseFloat and Number() lose precision. Keep base units as bigint and convert with parseUnits or formatUnits at the edges."),
    "JS-FLOAT-SCALE": ("medium", "Floating-point scale factor; 1e18 or Math.pow(10, d) mixes floats into integer amounts. Use 10n ** BigInt(decimals)."),
    "PY-FLOAT-AMOUNT": ("medium", "float() or division by a float literal on token amounts loses precision. Use int for base units and Decimal with enough precision for display."),
    "HARDCODED-DECIMALS": ("low", "Decimals fixed in code; the same symbol has different decimals on different chains. Read decimals() per chain and token address, or document why this is fixed."),
}
_AMOUNT_WORDS = r"(?:wei|gwei|balance|amount|allowance|reserve|supply|decimals|formatUnits|formatEther|parseUnits|parseEther|toWei|fromWei)"
_PATTERNS = {
    "NODE-SHA3": (JS_EXT, re.compile(r"createHash\(\s*['\"`]sha3-256['\"`]")),
    "PY-SHA3": (PY_EXT, re.compile(r"hashlib\.sha3_256\b|hashlib\.new\(\s*['\"]sha3[_-]256['\"]")),
    "JS-FLOAT-AMOUNT": (JS_EXT, re.compile(r"\b(?:parseFloat|Number)\s*\((?=[^\n]*" + _AMOUNT_WORDS + r")", re.I)),
    "JS-FLOAT-SCALE": (JS_EXT, re.compile(r"(?<![\w.])1e(?:6|8|9|18)(?![\w.])|Math\.pow\(\s*10\s*,|(?<![\w.])10\s*\*\*\s*(?:\d+|decimals)\b(?!n)")),
    "PY-FLOAT-AMOUNT": (PY_EXT, re.compile(r"\bfloat\s*\((?=[^\n]*" + _AMOUNT_WORDS + r")|/\s*1e(?:6|8|9|18)\b", re.I)),
    "HARDCODED-DECIMALS": (JS_EXT | PY_EXT, re.compile(r"\bdecimals\s*[:=]\s*(?:6|8|18)\b(?!\s*[*/+-])", re.I)),
}
_ETH_CONTEXT = re.compile(r"\b(?:web3|eth_|keccak|solidity|abi|ethers|viem|evm)\b", re.I)
_IGNORE_RE = re.compile(r"evm-check:\s*ignore\s+([A-Z0-9-]+|all)", re.I)


def _iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix in JS_EXT | PY_EXT and not name.endswith((".min.js", ".d.ts")):
                yield path


def _ignored(lines: list[str], idx: int, rule: str) -> bool:
    for j in (idx, idx - 1):
        if 0 <= j < len(lines):
            m = _IGNORE_RE.search(lines[j])
            if m and m.group(1).upper() in (rule, "ALL"):
                return True
    return False


def scan(root: Path) -> list[dict]:
    leads = []
    for path in _iter_files(root):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        eth_file = bool(_ETH_CONTEXT.search(text))
        rel = path.relative_to(root).as_posix()
        for rule, (exts, pattern) in _PATTERNS.items():
            if path.suffix not in exts or (rule == "PY-SHA3" and not eth_file):
                continue
            for idx, line in enumerate(lines):
                stripped = line.lstrip()
                if stripped.startswith(("//", "#", "*")) and "evm-check" not in stripped:
                    continue
                if pattern.search(line) and not _ignored(lines, idx, rule):
                    leads.append({"rule": rule, "level": RULES[rule][0], "file": rel, "line": idx + 1})
    leads.sort(key=lambda d: (LEVEL_RANK[d["level"]], d["file"], d["line"], d["rule"]))
    return leads


# --------------------------------------------------------------------------- CLI

def _emit(obj, as_json: bool, text_lines: list[str]) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, sort_keys=True))
    else:
        print("\n".join(text_lines))


def _hex_bytes(value: str) -> bytes:
    if not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})*", value):
        raise ValueError("--hex input must be 0x followed by an even number of hex digits")
    return bytes.fromhex(value[2:])


def cmd_hash(args) -> int:
    try:
        data = _hex_bytes(args.text) if args.hex else args.text.encode("utf-8")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = {"input_bytes": len(data), "keccak256": "0x" + keccak256(data).hex(), "sha3_256_fips": "0x" + hashlib.sha3_256(data).hexdigest()}
    lines = [f"keccak256 (Ethereum): {result['keccak256']}", f"sha3-256 (FIPS 202):  {result['sha3_256_fips']}"]
    if args.expect:
        want = args.expect.lower().removeprefix("0x")
        match = "keccak256" if want == result["keccak256"][2:] else "sha3_256_fips" if want == result["sha3_256_fips"][2:] else "neither"
        result["expect_matches"] = match
        lines.append(f"expected digest matches: {match}")
    _emit(result, args.json, lines)
    return 0


def _sig_command(args, full: bool) -> int:
    out, lines, code = [], [], 0
    for sig in args.signatures:
        try:
            canon = canonical_signature(sig)
        except SigError as exc:
            out.append({"input": sig, "error": str(exc)})
            lines.append(f"error: {sig!r}: {exc}")
            code = 2
            continue
        digest = keccak256(canon.encode("ascii")).hex()
        value = "0x" + (digest if full else digest[:8])
        out.append({"input": sig, "canonical": canon, "topic" if full else "selector": value})
        lines.append(f"{value}  {canon}")
    _emit(out, args.json, lines)
    return code


def cmd_checksum(args) -> int:
    results = [check_address(a.strip()) for a in args.addresses]
    lines = [f"{r['status']:<10} {r['checksummed'] or r['input']}" for r in results]
    _emit(results, args.json, lines)
    if any(r["status"] == "malformed" for r in results):
        return 2
    return 1 if any(r["status"] == "invalid" for r in results) else 0


def cmd_units(args) -> int:
    if not 0 <= args.decimals <= 77:
        print("error: --decimals must be between 0 and 77", file=sys.stderr)
        return 2
    try:
        value = str(to_base(args.amount, args.decimals)) if args.to == "base" else to_display(args.amount, args.decimals)
    except UnitsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    _emit({"input": args.amount, "decimals": args.decimals, "to": args.to, "value": value}, args.json, [value])
    return 0


def cmd_scan(args) -> int:
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: not a directory: {args.root}", file=sys.stderr)
        return 2
    leads = scan(root)
    threshold = LEVEL_RANK[args.fail_on]
    failing = [d for d in leads if LEVEL_RANK[d["level"]] <= threshold]
    counts = {lvl: sum(1 for d in leads if d["level"] == lvl) for lvl in LEVELS}
    if args.json:
        print(json.dumps({"version": VERSION, "leads": leads, "counts": counts, "fail_on": args.fail_on}, indent=2, sort_keys=True))
    else:
        for d in leads:
            print(f"{d['level'].upper():<6} {d['rule']:<19} {d['file']}:{d['line']}")
        print(f"leads: {len(leads)} (high {counts['high']}, medium {counts['medium']}, low {counts['low']}); leads are not findings")
    return 1 if failing else 0


def cmd_list_rules(args) -> int:
    if args.json:
        print(json.dumps({k: {"level": v[0], "advice": v[1]} for k, v in RULES.items()}, indent=2, sort_keys=True))
    else:
        for key, (level, advice) in RULES.items():
            print(f"{key:<19} {level:<6} {advice}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evm_check.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("hash", help="Keccak-256 and SHA3-256 of text or bytes")
    p.add_argument("text")
    p.add_argument("--hex", action="store_true", help="treat TEXT as 0x-prefixed bytes")
    p.add_argument("--expect", help="digest to identify (keccak256, sha3-256 or neither)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_hash)

    for name, full, helptext in (("selector", False, "4-byte function or error selectors"), ("topic", True, "event topic 0 hashes")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("signatures", nargs="+")
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=lambda a, f=full: _sig_command(a, f))

    p = sub.add_parser("checksum", help="EIP-55 address checksums")
    p.add_argument("addresses", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_checksum)

    p = sub.add_parser("units", help="exact display <-> base unit conversion")
    p.add_argument("amount")
    p.add_argument("--decimals", type=int, required=True)
    p.add_argument("--to", choices=("base", "display"), default="base")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_units)

    p = sub.add_parser("scan", help="lead finder for hashing and amount bugs in client code")
    p.add_argument("--root", default=".")
    p.add_argument("--fail-on", choices=LEVELS, default="medium")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("list-rules", help="print scan rules")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list_rules)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
