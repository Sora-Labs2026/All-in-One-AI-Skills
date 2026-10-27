#!/usr/bin/env python3
"""Summarize a captured HTTP session (HAR file) without printing its contents.

Reads an HTTP Archive (.har) file, a JSON format exported by browser dev tools
and intercepting proxies, and prints an aggregate summary: how many requests,
to which hosts, with which methods, status classes and content types, plus a
redaction report that counts where credentials and tokens appear (authorization
headers, cookies, Set-Cookie responses, secret-looking query or body
parameters) WITHOUT ever printing their values.

It never reaches the network, never modifies the input and never writes header
values, cookie values, request or response bodies, or query-string values to
its output. URL query strings are stripped to parameter names, and path
segments that look like a token or key are replaced with <redacted>.

Use it to triage a traffic capture safely before reading individual requests,
and to catch secrets that are travelling in URLs. A clean run is not proof the
capture is safe to share; it means this tool found no signal in the fields it
checks. Standard library only. Exit codes: 0 ok, 1 strict finding, 2 usage or
parse error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from urllib.parse import urlsplit, parse_qsl

# Header names whose presence signals a credential or token on the request/response.
SENSITIVE_HEADERS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie",
    "x-api-key", "api-key", "apikey", "x-auth-token", "x-access-token",
    "x-csrf-token", "x-xsrf-token", "authentication", "x-amz-security-token",
}
# Parameter names (query or body) that should not carry a real value in a URL.
SENSITIVE_PARAMS = {
    "token", "access_token", "refresh_token", "id_token", "auth", "authorization",
    "api_key", "apikey", "key", "secret", "client_secret", "password", "passwd",
    "pwd", "pass", "session", "sessionid", "sid", "code", "otp", "signature",
    "sig", "jwt", "bearer", "x-api-key",
}
# A path segment that looks like a secret rather than a readable route name.
TOKEN_SEGMENT = re.compile(
    r"^(?:[A-Za-z0-9_-]{24,}"            # long opaque strings
    r"|[A-Fa-f0-9]{16,}"                 # long hex
    r"|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)"  # a JWT-shaped segment
    r"\.?$"
)
REDACTED = "<redacted>"


class HarError(Exception):
    pass


def _header_names(headers) -> list:
    out = []
    if isinstance(headers, list):
        for h in headers:
            if isinstance(h, dict) and isinstance(h.get("name"), str):
                out.append(h["name"].lower())
    return out


def _param_names(items) -> list:
    out = []
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and isinstance(it.get("name"), str):
                out.append(it["name"])
    return out


def _redact_path(path: str) -> str:
    parts = path.split("/")
    return "/".join(REDACTED if TOKEN_SEGMENT.match(p) else p for p in parts)


def _status_class(status) -> str:
    try:
        n = int(status)
    except (TypeError, ValueError):
        return "other"
    if 100 <= n < 600:
        return f"{n // 100}xx"
    return "other"


def load_entries(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise HarError(f"file not found: {path}")
    except (OSError, ValueError) as exc:
        raise HarError(f"could not parse HAR JSON: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("log"), dict):
        raise HarError("not a HAR file: top-level 'log' object is missing")
    entries = data["log"].get("entries")
    if not isinstance(entries, list):
        raise HarError("not a HAR file: 'log.entries' is missing or not a list")
    return entries


def summarize(entries: list) -> dict:
    hosts, methods, status_classes, mimes = Counter(), Counter(), Counter(), Counter()
    sensitive_param_names = Counter()
    secret_in_url = []          # indices of requests with a secret-looking query param
    n_auth_header = n_req_cookie = n_set_cookie = n_body = 0
    rows = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        req = entry.get("request") if isinstance(entry.get("request"), dict) else {}
        resp = entry.get("response") if isinstance(entry.get("response"), dict) else {}

        method = str(req.get("method", "")).upper() or "?"
        url = req.get("url", "") if isinstance(req.get("url"), str) else ""
        split = urlsplit(url)
        host = split.netloc or "?"
        status = resp.get("status", "")
        mime = ""
        content = resp.get("content")
        if isinstance(content, dict) and isinstance(content.get("mimeType"), str):
            mime = content["mimeType"].split(";")[0].strip() or ""

        methods[method] += 1
        hosts[host] += 1
        status_classes[_status_class(status)] += 1
        mimes[mime or "(none)"] += 1

        req_header_names = set(_header_names(req.get("headers")))
        resp_header_names = set(_header_names(resp.get("headers")))
        has_auth = bool(req_header_names & {"authorization", "proxy-authorization",
                                            "x-api-key", "api-key", "apikey",
                                            "x-auth-token", "x-access-token", "authentication"})
        if has_auth:
            n_auth_header += 1
        if "cookie" in req_header_names or _param_names(req.get("cookies")):
            n_req_cookie += 1
        if "set-cookie" in resp_header_names or _param_names(resp.get("cookies")):
            n_set_cookie += 1

        # Query parameter names (values never recorded).
        q_names = [k for k, _ in parse_qsl(split.query, keep_blank_values=True)]
        secret_here = False
        for name in q_names:
            if name.lower() in SENSITIVE_PARAMS:
                sensitive_param_names[name.lower()] += 1
                secret_here = True
        if secret_here:
            secret_in_url.append(i)

        # Body parameter names from a form post (values never recorded).
        post = req.get("postData")
        body_present = False
        if isinstance(post, dict):
            if post.get("text") or _param_names(post.get("params")):
                body_present = True
                n_body += 1
            for name in _param_names(post.get("params")):
                if name.lower() in SENSITIVE_PARAMS:
                    sensitive_param_names[name.lower()] += 1

        rows.append({
            "index": i,
            "method": method,
            "status": status if isinstance(status, int) else str(status),
            "host": host,
            "path": _redact_path(split.path) or "/",
            "query_params": len(q_names),
            "mime": mime,
            "auth_header": has_auth,
            "body": body_present,
            "secret_in_url": secret_here,
        })

    return {
        "entries": len(entries),
        "hosts": hosts,
        "methods": methods,
        "status_classes": status_classes,
        "mimes": mimes,
        "auth_header_requests": n_auth_header,
        "cookie_requests": n_req_cookie,
        "set_cookie_responses": n_set_cookie,
        "body_requests": n_body,
        "sensitive_param_names": sensitive_param_names,
        "secret_in_url_count": len(secret_in_url),
        "rows": rows,
    }


def _counter_lines(counter: Counter, top: int) -> list:
    items = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return [f"  {count:>6}  {name}" for name, count in items[:top]]


def format_text(s: dict, top: int, verbose: bool) -> str:
    out = []
    out.append(f"HAR summary: {s['entries']} request(s), {len(s['hosts'])} host(s)")
    out.append("")
    out.append("By host:")
    out += _counter_lines(s["hosts"], top)
    out.append("By method:")
    out += _counter_lines(s["methods"], top)
    out.append("By status class:")
    out += _counter_lines(s["status_classes"], top)
    out.append("By content type:")
    out += _counter_lines(s["mimes"], top)
    out.append("")
    out.append("Sensitive-data signals (names and counts only; no values read):")
    out.append(f"  {s['auth_header_requests']:>6}  requests with an authorization/API-key header")
    out.append(f"  {s['cookie_requests']:>6}  requests carrying cookies")
    out.append(f"  {s['set_cookie_responses']:>6}  responses setting cookies")
    out.append(f"  {s['body_requests']:>6}  requests with a body")
    out.append(f"  {s['secret_in_url_count']:>6}  requests with a secret-looking query parameter")
    if s["sensitive_param_names"]:
        names = ", ".join(sorted(s["sensitive_param_names"]))
        out.append(f"  sensitive parameter names seen: {names}")
    if verbose:
        out.append("")
        out.append("Requests (query values stripped, token-like path segments redacted):")
        for r in s["rows"][: top * 5 if top else len(s["rows"])]:
            flags = "".join([
                "A" if r["auth_header"] else "-",
                "B" if r["body"] else "-",
                "!" if r["secret_in_url"] else "-",
            ])
            out.append(f"  [{flags}] {r['method']:>6} {str(r['status']):>4} "
                       f"{r['host']}{r['path']}")
    out.append("")
    out.append("Values of headers, cookies, bodies and query strings were never read into this output.")
    return "\n".join(out)


def to_json(s: dict) -> dict:
    return {
        "entries": s["entries"],
        "hosts": dict(s["hosts"]),
        "methods": dict(s["methods"]),
        "status_classes": dict(s["status_classes"]),
        "mimes": dict(s["mimes"]),
        "auth_header_requests": s["auth_header_requests"],
        "cookie_requests": s["cookie_requests"],
        "set_cookie_responses": s["set_cookie_responses"],
        "body_requests": s["body_requests"],
        "sensitive_param_names": dict(s["sensitive_param_names"]),
        "secret_in_url_count": s["secret_in_url_count"],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Summarize a HAR capture without printing its contents.")
    p.add_argument("har", help="path to a .har file")
    p.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p.add_argument("--top", type=int, default=15,
                   help="rows per aggregate list (default 15)")
    p.add_argument("--verbose", action="store_true",
                   help="also list each request (redacted)")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 if any secret-looking parameter appears in a URL")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.top < 1:
        print("error: --top must be at least 1", file=sys.stderr)
        return 2
    try:
        entries = load_entries(args.har)
    except HarError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    s = summarize(entries)
    if args.json:
        print(json.dumps(to_json(s), indent=2, sort_keys=True))
    else:
        print(format_text(s, args.top, args.verbose))
    if args.strict and s["secret_in_url_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
