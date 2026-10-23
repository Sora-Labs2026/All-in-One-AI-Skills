#!/usr/bin/env python3
"""ProductCraft LaunchGuard bounded, read-only, redacted heuristic scanner.

NOT a vulnerability verifier, Git history scanner, RLS audit, SAST replacement,
or production-security certification. Never prints matching source text/secrets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".agents", ".claude", ".venv", "venv",
    "node_modules", ".next", ".nuxt", ".svelte-kit", "dist", "build",
    "coverage", "__pycache__", ".pytest_cache", ".mypy_cache", "vendor",
    "target", ".turbo", ".cache", "out", ".angular", ".idea",
}
SUFFIXES = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".rb",
    ".go", ".rs", ".php", ".java", ".kt", ".swift", ".vue", ".svelte",
    ".json", ".jsonc", ".toml", ".yaml", ".yml", ".sh", ".sql",
    ".env", ".properties", ".tf", ".hcl", ".xml", ".config",
}
EXTRA_NAMES = {"Dockerfile", "Procfile", "wrangler.toml", "next.config.js", "next.config.mjs"}
MAX_SIZE = 1024 * 1024
MAX_FILES = 20000
MAX_FINDINGS = 250

RULES = [
    (
        "SECRET_LIKE_LITERAL", "HIGH", "LIKELY",
        re.compile(r"(?:sk_(?:live|test)_[A-Za-z0-9]{16,}|sk-proj-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{20,}|sb_secret_[A-Za-z0-9_-]{12,})"),
        "Credential-shaped literal. Confirm whether real/active and whether exposure occurred; never report its bytes.",
    ),
    (
        "PUBLIC_SECRET_NAMING", "HIGH", "POSSIBLE",
        re.compile(r"\b(?:NEXT_PUBLIC_|VITE_|REACT_APP_)[A-Z0-9_]*(?:SECRET|SERVICE_ROLE|PRIVATE_KEY|DATABASE_URL|PASSWORD)[A-Z0-9_]*\b", re.I),
        "Variable name suggests a privileged credential may be embedded in a client bundle. Verify its semantics and actual value origin.",
    ),
    (
        "TLS_VERIFICATION_DISABLED", "HIGH", "LIKELY",
        re.compile(r"\brejectUnauthorized\s*:\s*false\b|\bverify\s*=\s*False\b|\bCERT_NONE\b", re.I),
        "Transport certificate verification appears disabled. Inspect context and environment.",
    ),
    (
        "PERMISSIVE_CORS", "MEDIUM", "POSSIBLE",
        re.compile(r"\ballow_origins\s*=\s*\[\s*['\"]\*['\"]|\b(?:origin|Access-Control-Allow-Origin)\s*:\s*['\"]\*['\"]", re.I),
        "Potential wildcard CORS. Assess credential handling, intended public API access and actual response headers.",
    ),
    (
        "DEBUG_ENABLED", "MEDIUM", "POSSIBLE",
        re.compile(r"\bapp\.debug\s*=\s*True\b|\bDEBUG\s*[:=]\s*(?:true|True|1)\b", re.I),
        "Possible enabled debug configuration. Verify deployed environment and whether this is test-only.",
    ),
    (
        "UNTRUSTED_HTML_SINK", "MEDIUM", "POSSIBLE",
        re.compile(r"\bdangerouslySetInnerHTML\b|\binnerHTML\s*=(?!=)", re.I),
        "HTML sink needs review of input trust and context-aware sanitization; not automatically a vulnerability.",
    ),
    (
        "POSSIBLE_SENSITIVE_LOG", "MEDIUM", "POSSIBLE",
        re.compile(r"\b(?:console\.(?:log|error|warn|debug)|logger\.(?:debug|info|error|warn)|print)\s*\([^\n]*(?:password|secret|token|authorization|cookie)", re.I),
        "Logging statement may include sensitive material. Inspect whether only redacted metadata is logged.",
    ),
]


def candidate_file(name: str, path: Path) -> bool:
    return (path.suffix.lower() in SUFFIXES or name in EXTRA_NAMES
            or name.startswith(".env") or name.endswith(".config.js"))


def tracked_env(root: Path) -> tuple[list[str], str]:
    """Return tracked env paths without reading or displaying contents."""
    try:
        p = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached"],
            capture_output=True, timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [], "Git index check unavailable. Git history was not scanned."
    if p.returncode != 0:
        return [], "Git index check unavailable (not a Git repo or Git error). Git history was not scanned."
    paths = []
    for raw in p.stdout.split(b"\x00"):
        if not raw:
            continue
        rel = os.fsdecode(raw).replace("\\", "/")
        file_name = Path(rel).name.lower()
        if file_name == ".env" or file_name.startswith(".env."):
            if file_name not in {".env.example", ".env.sample", ".env.template", ".env.defaults"}:
                paths.append(rel)
    return sorted(set(paths)), "Git INDEX only; commit history and remote repository were NOT scanned."


def scan(root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    results: list[dict] = []
    scanned = 0
    skipped_large = 0
    truncated = False

    def add(rule_id: str, severity: str, confidence: str, path: str, line: int | None, note: str) -> None:
        nonlocal truncated
        if len(results) >= MAX_FINDINGS:
            truncated = True
            return
        results.append({
            "rule_id": rule_id,
            "severity": severity,
            "confidence": confidence,
            "classification": "CANDIDATE_NOT_CONFIRMED",
            "file": path,
            "line": line,
            "note": note,
            # NO matched source, no values and no context snippets.
        })

    git_env_paths, git_status = tracked_env(root)
    for rel in git_env_paths:
        add("TRACKED_ENV_FILE", "HIGH", "LIKELY", rel, None,
            "An environment-value file is in Git index. Check whether it contains real secrets and assess rotation/history.")

    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(current) / d).is_symlink())
        for name in sorted(files):
            if scanned >= MAX_FILES:
                truncated = True
                break
            path = Path(current) / name
            if path.is_symlink() or not candidate_file(name, path) or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel.endswith("/launchguard-scan.json"):
                continue
            try:
                size = path.stat().st_size
                if size > MAX_SIZE:
                    skipped_large += 1
                    continue
                data = path.read_bytes()
                if b"\x00" in data[:4096]:
                    continue
                source = data.decode("utf-8", errors="replace")
            except (PermissionError, OSError):
                continue
            scanned += 1
            for n, line in enumerate(source.splitlines(), start=1):
                for rule_id, severity, confidence, regex, note in RULES:
                    if regex.search(line):
                        add(rule_id, severity, confidence, rel, n, note)
        if scanned >= MAX_FILES:
            break

    counts = Counter(x["severity"] for x in results)
    return {
        "tool": "launchguard-heuristic-preflight",
        "version": "1.0.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "scope": "bounded local text scan + Git INDEX paths (not Git history)",
        "result_type": "potential-indicators-only",
        "warnings": [
            "A finding is not a verified vulnerability. A clean scan is NOT a security pass.",
            "No database policies, source-to-sink analysis, runtime/deployed configuration, Git history, payment or authorization tested.",
            git_status,
        ],
        "stats": {
            "files_scanned": scanned,
            "files_skipped_too_large": skipped_large,
            "finding_count": len(results),
            "truncated": truncated,
            "findings_by_severity": dict(sorted(counts.items())),
        },
        "findings": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="Local project root")
    ap.add_argument("--json-out", help="Write redacted machine-readable summary to this path")
    ap.add_argument("--fail-on", choices=["never", "high", "medium"], default="never",
                    help="CI heuristic threshold; no vulnerability is confirmed by this scan")
    opts = ap.parse_args()
    try:
        result = scan(Path(opts.root))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    s = result["stats"]
    print(f"LaunchGuard heuristic scan: {s['files_scanned']} files, {s['finding_count']} candidates "
          f"(truncated={s['truncated']}); no secret values printed.")
    print("This does not establish security or launch readiness. See modules/launchguard/GUIDE.md for five-gate verification.")
    if opts.json_out:
        output = Path(opts.json_out).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(output, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Redacted report written: {output}")
    severities = {f["severity"] for f in result["findings"]}
    if opts.fail_on == "high" and "HIGH" in severities:
        return 1
    if opts.fail_on == "medium" and ("HIGH" in severities or "MEDIUM" in severities):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
