#!/usr/bin/env python3
"""ProductCraft integration lead finder. Offline, read-only, deterministic.

Walks a project and lists leads in code that talks to third-party APIs:

  WEBHOOK-REPARSED-BODY       high    webhook signature checked against re-serialized JSON
  HMAC-PLAIN-COMPARE          high    digest or signature compared with == or !=
  CLIENT-SERVER-SDK           high    server SDK or server secret used in a 'use client' module
  WEBHOOK-NO-VERIFY           medium  webhook handler with no visible signature verification
  STRIPE-NO-IDEMPOTENCY       medium  Stripe create that moves money without an idempotency key
  SECRET-IN-URL               medium  credential-like query parameter in a URL
  BROAD-OAUTH-SCOPE           medium  full-access Google scope or admin-level Atlassian scope
  SUPABASE-GETSESSION-SERVER  medium  auth.getSession() trusted in server-side code
  WEBHOOK-NO-DEDUP            low     webhook handler with no visible event-ID deduplication
  SHEETS-USER-ENTERED         low     Sheets write that parses input as typed (formula injection)
  RETIRED-API                 low     endpoint, environment or library the provider retired

Leads are not findings: read the code and confirm each with a test. The tool
reads local files only, never contacts a provider, never modifies anything and
never prints matched source text. A line can be acknowledged with a comment on
the same line or the line above:  integration-scan: ignore RULE-ID <reason>

Exit codes: 0 no lead at or above --fail-on, 1 at least one, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"
LEVELS = ("high", "medium", "low")
LEVEL_RANK = {name: rank for rank, name in enumerate(LEVELS)}

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", ".venv", "venv", "env",
    "__pycache__", "dist", "build", "out", "coverage", ".next", ".nuxt", ".svelte-kit",
    ".cache", ".turbo", "vendor", "Pods", "DerivedData", ".gradle", ".idea", "target",
    ".pytest_cache", ".mypy_cache", ".tox", ".terraform",
}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "__mocks__", "e2e", "fixtures"}
TEST_FILE_RE = re.compile(r"(?:\.(?:test|spec)\.[^.]+$|^test_.*\.py$|_test\.(?:py|go)$|Tests?\.(?:java|kt|cs)$)")
CODE_SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".php", ".java",
    ".kt", ".cs", ".vue", ".svelte", ".rs", ".swift",
}
CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml"}
MAX_FILE_BYTES = 1_000_000

RULES = {
    "WEBHOOK-REPARSED-BODY": ("high", "Signature is checked against re-serialized JSON; providers sign the exact raw bytes. Verify against the raw request body."),
    "HMAC-PLAIN-COMPARE": ("high", "Signature or digest compared with == or !=; use a constant-time comparison after a length check."),
    "CLIENT-SERVER-SDK": ("high", "Client module imports a server SDK or reads a server secret; move the call behind a server endpoint."),
    "WEBHOOK-NO-VERIFY": ("medium", "Webhook handler with no visible signature verification; confirm it is verified (it may happen in middleware)."),
    "STRIPE-NO-IDEMPOTENCY": ("medium", "Stripe create that moves money without an idempotency key (unless passed through an options object built elsewhere); a retry after a timeout can repeat it."),
    "SECRET-IN-URL": ("medium", "Credential-like query parameter in a URL; query strings reach logs, proxies and browser history. Send it in a header or body."),
    "BROAD-OAUTH-SCOPE": ("medium", "Broad OAuth scope; confirm the feature needs it."),
    "SUPABASE-GETSESSION-SERVER": ("medium", "auth.getSession() in server-side code returns unverified cookie data; authorize with getUser() or getClaims()."),
    "WEBHOOK-NO-DEDUP": ("low", "Webhook handler with no visible event-ID deduplication; duplicates and retries may repeat effects."),
    "SHEETS-USER-ENTERED": ("low", "Sheets write uses USER_ENTERED; untrusted text starting with = becomes a formula. Use RAW for such values."),
    "RETIRED-API": ("low", "Retired or legacy provider API."),
}

COMMENT_RE = re.compile(r"^\s*(?://|#|\*|/\*|--)")
IGNORE_RE = re.compile(r"integration-scan:\s*ignore\s+([A-Z0-9-]+|all)", re.I)

# Webhook handler detection
WEBHOOK_ROUTE_RE = re.compile(
    r"""(?:\.(?:post|route|all|use)\s*\(|@\w+(?:\.\w+)*\.(?:post|route|api_route)\s*\(|\b(?:re_)?path\s*\(|HandleFunc\s*\(|\bpost\s+)\s*['"`][^'"`\n]*webhook""",
    re.I,
)
HANDLER_RE = re.compile(
    r"""\b(?:req|request|ctx\.request|event)\.(?:body|text\(\)|json\(\)|data|get_data\(|raw_post|rawBody)"""
    r"""|export\s+(?:async\s+)?function\s+POST\b|\bdef\s+post\s*\(|\br\.Body\b|request\.body\b""",
)
VERIFY_RE = re.compile(
    r"constructEvent|construct_event|\bverify\w*\s*\(|\.verify\s*\(|timingSafeEqual|compare_digest|hmac\.Equal"
    r"|secure_compare|hash_equals|MessageDigest\.isEqual|FixedTimeEquals|createHmac|hmac\.new\s*\(|jwtVerify"
    r"|webhook_verification_key|validateRequest|validate_request|check_signature|checkSignature",
)
DEDUP_RE = re.compile(
    r"event[._]?id|evt\.id|webhook[-_]?id|delivery[-_]?id|idempot|on\s+conflict|on_conflict|upsert|dedup"
    r"|already[_ ]?processed|processed_events|insert\s+or\s+ignore|get_or_create|findOrCreate|setnx|\.exists\(",
    re.I,
)

# Re-serialized body near signature code
REPARSE_RE = re.compile(
    r"JSON\.stringify\(\s*(?:await\s+)?(?:req|request|ctx\.request|ctx\.req|event)\b(?:\.body|\.json\(\))"
    r"|json\.dumps\(\s*(?:await\s+)?request\.(?:json|get_json\(\)|data|body)"
)
SIG_CONTEXT_RE = re.compile(r"sig|hmac|digest|constructEvent|construct_event|verify", re.I)

# Plain comparison of digests
HMAC_FILE_RE = re.compile(r"createHmac|hmac\.new\s*\(|hmac\.New\s*\(|\bHMAC\s*\(|Mac\.getInstance|OpenSSL::HMAC|hash_hmac\s*\(|HMACSHA256|crypto\.subtle\.sign")
CMP_RE = re.compile(r"(?:===|!==|==|!=)")
SIGLIKE_RE = re.compile(r"digest|signature|\bsig\b|hmac|\bexpected\b|\bcomputed\b", re.I)
SAFE_CMP_RE = re.compile(r"timingSafeEqual|compare_digest|hmac\.Equal|secure_compare|hash_equals|isEqual|FixedTimeEquals|ConstantTimeCompare")
NULLISH_RE = re.compile(
    r"(?:===|!==|==|!=)\s*(?:null|None|undefined|nil|''|\"\"|0|false|true|False|True)\b"
    r"|\b(?:null|None|undefined|nil)\s*(?:===|!==|==|!=)"
    r"|\.length\b|\blen\s*\(|\bsize\s*\(|typeof|instanceof|\.count\b|\.startsWith\(|\.startswith\(",
)

# Stripe creates that move money
STRIPE_FILE_RE = re.compile(r"stripe", re.I)
STRIPE_CREATE_RE = re.compile(
    r"(?:\.|::|->)(?:paymentIntents|payment_intents|PaymentIntent|charges|Charge|refunds|Refund|transfers|Transfer"
    r"|payouts|Payout|subscriptions|Subscription)(?:\.|->)create\s*\("
)
IDEMPOTENCY_RE = re.compile(r"idempotency", re.I)

SECRET_URL_RE = re.compile(
    r"[?&](?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|license[_-]?key|secret[_-]?key|private[_-]?key)=",
    re.I,
)
URL_CONTEXT_RE = re.compile(r"https?://|\$\{|\{[A-Za-z_]|\+\s*['\"]|['\"]\s*\+|%s|\.format\(")

SCOPE_RULES = [
    (re.compile(r"https://mail\.google\.com/?(?![\w.])"), "Full Gmail access including permanent deletion; prefer gmail.send, gmail.compose or gmail.readonly."),
    (re.compile(r"googleapis\.com/auth/drive(?![.\w-])"), "Whole Drive; prefer drive.file with the Picker, or drive.readonly."),
    (re.compile(r"googleapis\.com/auth/calendar(?![.\w-])"), "Full Calendar including settings and sharing; prefer calendar.events or calendar.readonly."),
    (re.compile(r"googleapis\.com/auth/(?:spreadsheets|documents|presentations)(?![.\w-])"), "Every file of this type the user can open; prefer drive.file with the Picker, or the .readonly scope."),
    (re.compile(r"googleapis\.com/auth/cloud-platform(?![.\w-])"), "Full Google Cloud access; prefer service-specific scopes and narrow IAM roles."),
    (re.compile(r"googleapis\.com/auth/admin\.directory\.user(?![.\w-])"), "Write access to Workspace users; prefer admin.directory.user.readonly."),
    (re.compile(r"\bmanage:jira-configuration\b"), "Jira administration scope; most integrations need only read:jira-work or write:jira-work."),
    (re.compile(r"\bmanage:jira-project\b"), "Jira project administration scope; confirm the feature needs it."),
]

USE_CLIENT_RE = re.compile(r"""^\s*['"]use client['"]\s*;?\s*$""")
SERVER_SDK_RE = re.compile(
    r"""(?:from\s+|require\(\s*|import\s+)['"](?:stripe|plaid|googleapis|google-auth-library|@googleapis/[\w-]+)['"]"""
)
SERVER_SECRET_ENV_RE = re.compile(r"process\.env\.(?!NEXT_PUBLIC_)\w*(?:SECRET|SERVICE_ROLE|PRIVATE)\w*")

GETSESSION_RE = re.compile(r"\.auth\.getSession\s*\(")
SERVER_PATH_RE = re.compile(
    r"(?:^|/)(?:api|server|actions?)(?:/|$)|(?:^|/)(?:route|middleware|hooks\.server|\+server|\+page\.server|\+layout\.server)\.[jt]s$|\.server\.[jt]sx?$"
)
SERVER_MARKER_RE = re.compile(r"""['"]use server['"]|import\s+['"]server-only['"]|createServerClient""")

SHEETS_RE = re.compile(r"""value_?input_?option['"]?\s*[:=]\s*['"]?USER_ENTERED|valueInputOption=USER_ENTERED""", re.I)

RETIRED = [
    (re.compile(r"PlaidEnvironments\.development|plaid\.Environment\.Development|development\.plaid\.com"), "Plaid's Development environment was retired; use Sandbox or Production."),
    (re.compile(r"\btransactions(?:Get|_get)\s*\(|/transactions/get\b"), "Plaid date-range transactions/get; prefer /transactions/sync with a stored cursor."),
    (re.compile(r"/rest/api/[23]/search(?![/\w])"), "Jira's old search endpoint is deprecated and being removed; use /rest/api/3/search/jql with nextPageToken."),
    (re.compile(r"urn:ietf:wg:oauth:2\.0:oob"), "Google's out-of-band OAuth flow is retired; use a loopback redirect."),
    (re.compile(r"^\s*(?:from|import)\s+oauth2client\b"), "oauth2client is deprecated; use google-auth and google-auth-oauthlib."),
    (re.compile(r"@supabase/auth-helpers-"), "Supabase auth helpers are replaced by @supabase/ssr."),
    (re.compile(r"\.charges\.create\s*\(|stripe\.Charge\.create\s*\(|Stripe::Charge\.create\s*\("), "Stripe Charges API is legacy; PaymentIntents or Checkout handle Strong Customer Authentication."),
]


def is_test_path(rel: Path) -> bool:
    if any(part.lower() in TEST_DIRS for part in rel.parts[:-1]):
        return True
    return bool(TEST_FILE_RE.search(rel.name))


def discover(root: Path, include_tests: bool, max_files: int) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".env"))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            suffix = path.suffix.lower()
            if suffix not in CODE_SUFFIXES and suffix not in CONFIG_SUFFIXES:
                continue
            if name.startswith(".env") or path.is_symlink():
                continue
            rel = path.relative_to(root)
            if not include_tests and is_test_path(rel):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            files.append(path)
            if len(files) >= max_files:
                return files, True
    return files, truncated


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def call_text(text: str, start: int, limit: int = 4000) -> str:
    """Text of a call from its opening parenthesis to the matching close, bounded."""
    i = text.find("(", start)
    if i < 0:
        return ""
    depth, quote, escape = 0, "", False
    end = min(len(text), i + limit)
    for j in range(i, end):
        c = text[j]
        if quote:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                quote = ""
            continue
        if c in "'\"`":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return text[i:end]


def suppressed(lines: list[str], idx: int, rule: str) -> bool:
    for k in (idx, idx - 1):
        if 0 <= k < len(lines):
            for m in IGNORE_RE.finditer(lines[k]):
                if m.group(1).upper() in (rule, "ALL"):
                    return True
    return False


def scan_text(text: str, rel: str) -> list[dict]:
    """Return raw leads for one file: dicts with rule, line (1-based) and optional hint."""
    lines = text.splitlines()
    leads: list[dict] = []
    is_code = Path(rel).suffix.lower() in CODE_SUFFIXES
    rel_lower = rel.lower()

    def add(rule: str, line: int, hint: str = "") -> None:
        leads.append({"rule": rule, "line": line, "hint": hint})

    for i, line in enumerate(lines):
        n = i + 1
        for pattern, hint in SCOPE_RULES:
            if pattern.search(line):
                add("BROAD-OAUTH-SCOPE", n, hint)
        if not is_code:
            continue
        for pattern, hint in RETIRED:
            if pattern.search(line):
                add("RETIRED-API", n, hint)
        if SECRET_URL_RE.search(line) and URL_CONTEXT_RE.search(line):
            add("SECRET-IN-URL", n)
        if SHEETS_RE.search(line):
            add("SHEETS-USER-ENTERED", n)
        if REPARSE_RE.search(line):
            window = "\n".join(lines[max(0, i - 3): i + 4])
            if SIG_CONTEXT_RE.search(window):
                add("WEBHOOK-REPARSED-BODY", n)

    if not is_code:
        return leads

    if HMAC_FILE_RE.search(text):
        for i, line in enumerate(lines):
            if COMMENT_RE.match(line) or not CMP_RE.search(line):
                continue
            if SIGLIKE_RE.search(line) and not SAFE_CMP_RE.search(line) and not NULLISH_RE.search(line):
                add("HMAC-PLAIN-COMPARE", i + 1)

    if STRIPE_FILE_RE.search(text):
        for m in STRIPE_CREATE_RE.finditer(text):
            if not IDEMPOTENCY_RE.search(call_text(text, m.end() - 1)):
                add("STRIPE-NO-IDEMPOTENCY", text.count("\n", 0, m.start()) + 1)

    head = [ln for ln in lines[:8] if ln.strip() and not COMMENT_RE.match(ln)]
    if head and USE_CLIENT_RE.match(head[0]):
        for i, line in enumerate(lines):
            if SERVER_SDK_RE.search(line) or SERVER_SECRET_ENV_RE.search(line):
                add("CLIENT-SERVER-SDK", i + 1)

    if SERVER_PATH_RE.search(rel_lower) or SERVER_MARKER_RE.search(text):
        for i, line in enumerate(lines):
            if GETSESSION_RE.search(line) and not COMMENT_RE.match(line):
                add("SUPABASE-GETSESSION-SERVER", i + 1)

    route_hits = [i for i, line in enumerate(lines) if WEBHOOK_ROUTE_RE.search(line)]
    if ("webhook" in rel_lower or route_hits) and HANDLER_RE.search(text):
        anchor = (route_hits[0] + 1) if route_hits else 1
        if not VERIFY_RE.search(text):
            add("WEBHOOK-NO-VERIFY", anchor)
        if not DEDUP_RE.search(text):
            add("WEBHOOK-NO-DEDUP", anchor)
    return leads


def scan(root: Path, include_tests: bool = False, max_files: int = 50_000) -> dict:
    files, truncated = discover(root, include_tests, max_files)
    leads: list[dict] = []
    ignored = 0
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        rel = path.relative_to(root).as_posix()
        lines = text.splitlines()
        seen = set()
        for raw in scan_text(text, rel):
            key = (raw["rule"], raw["line"], raw["hint"])
            if key in seen:
                continue
            seen.add(key)
            if suppressed(lines, raw["line"] - 1, raw["rule"]):
                ignored += 1
                continue
            level, message = RULES[raw["rule"]]
            if raw["hint"]:
                message = f"{message} {raw['hint']}"
            leads.append({"rule": raw["rule"], "level": level, "file": rel, "line": raw["line"], "message": message})
    leads.sort(key=lambda d: (d["file"], d["line"], LEVEL_RANK[d["level"]], d["rule"], d["message"]))
    counts = {level: sum(1 for d in leads if d["level"] == level) for level in LEVELS}
    return {
        "tool": "integration_scan.py", "version": VERSION, "files_scanned": len(files),
        "truncated": truncated, "counts": counts, "suppressed": ignored, "leads": leads,
        "note": "Leads, not findings. Read the code and confirm each with a test before reporting it.",
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Offline, read-only lead finder for third-party API integration code (webhooks, idempotency, scopes, retired APIs).",
    )
    p.add_argument("--root", default=".", help="project folder to scan (default: current folder)")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p.add_argument("--fail-on", choices=("high", "medium", "low", "never"), default="medium",
                   help="exit 1 when a lead at or above this level exists (default: medium)")
    p.add_argument("--include-tests", action="store_true", help="also scan test folders and test files")
    p.add_argument("--max-files", type=int, default=50_000, help="stop after this many files (default: 50000)")
    p.add_argument("--list-rules", action="store_true", help="list rule IDs, levels and meanings, then exit")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if args.list_rules:
        for rule, (level, message) in RULES.items():
            print(f"{rule:<28} {level:<7} {message}")
        return 0
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: --root {args.root} is not a folder", file=sys.stderr)
        return 2
    if args.max_files < 1:
        print("error: --max-files must be at least 1", file=sys.stderr)
        return 2
    result = scan(root.resolve(), args.include_tests, args.max_files)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        counts = result["counts"]
        summary = ", ".join(f"{lvl} {counts[lvl]}" for lvl in LEVELS if counts[lvl])
        print(f"integration_scan.py {VERSION}: {len(result['leads'])} lead(s) in {result['files_scanned']} file(s)"
              + (f" ({summary})" if summary else "")
              + (f", {result['suppressed']} acknowledged" if result["suppressed"] else ""))
        for d in result["leads"]:
            print(f"{d['level'].upper():<7} {d['rule']:<27} {d['file']}:{d['line']}  {d['message']}")
        if result["truncated"]:
            print(f"note: stopped after --max-files {args.max_files}; later files were not scanned")
        print(result["note"])
    if args.fail_on != "never":
        limit = LEVEL_RANK[args.fail_on]
        if any(LEVEL_RANK[d["level"]] <= limit for d in result["leads"]):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
