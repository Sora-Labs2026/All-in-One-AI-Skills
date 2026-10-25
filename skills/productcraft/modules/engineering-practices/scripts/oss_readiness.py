#!/usr/bin/env python3
"""ProductCraft Engineering Practices: read-only open-source readiness check.

Looks at a repository the way an outsider will see it after it is made
public: front-door documents, license text versus the license declared in
package manifests, tracked files whose names suggest secrets or data dumps,
sensitive file names that only exist in history, internal hostnames and
private package registries a fresh clone cannot reach, local path
dependencies that point outside the repository, and the commit email domains
that will become public.

It never edits files, never uses the network and never prints file contents:
only paths, license identifiers, hostnames, counts and email domains. It does
not scan secret values; use a secret scanner for that.

Findings are prompts to look, not verdicts. The default exit code is 0; pass
--strict to exit 1 when any WARN finding is present.
"""
from __future__ import annotations

import argparse
import configparser
import fnmatch
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Set, Tuple

try:  # Python 3.11+
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover - exercised only on old interpreters
    tomllib = None  # type: ignore

VERSION = "1.0.0"
SEVERITY_ORDER = {"WARN": 0, "INFO": 1}
MAX_TEXT_BYTES = 1_000_000
MAX_LISTED = 50

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "__pycache__", ".tox", ".nox",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", "target", "dist", "build", ".next",
             ".cache", "coverage", ".gradle", ".idea", ".terraform"}

# --- license detection -------------------------------------------------------

# Ordered: the first entry whose phrases all appear wins. GNU texts are matched on their title
# line, because the GPL itself mentions the Lesser GPL and the Lesser GPL mentions the GPL.
LICENSE_FINGERPRINTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("AGPL-3.0", ("gnu affero general public license version 3",)),
    ("LGPL-3.0", ("gnu lesser general public license version 3",)),
    ("LGPL-2.1", ("gnu lesser general public license version 2.1",)),
    ("GPL-3.0", ("gnu general public license version 3",)),
    ("GPL-2.0", ("gnu general public license version 2",)),
    ("MPL-2.0", ("mozilla public license", "2.0")),
    ("Apache-2.0", ("apache license", "version 2.0")),
    ("EPL-2.0", ("eclipse public license", "2.0")),
    ("BSL-1.0", ("boost software license", "version 1.0")),
    ("BUSL-1.1", ("business source license", "1.1")),
    ("SSPL-1.0", ("server side public license",)),
    ("Elastic-2.0", ("elastic license 2.0",)),
    ("Unlicense", ("this is free and unencumbered software released into the public domain",)),
    ("CC0-1.0", ("cc0 1.0 universal",)),
    ("CC-BY-NC-SA-4.0", ("attribution-noncommercial-sharealike 4.0 international",)),
    ("CC-BY-NC-4.0", ("attribution-noncommercial 4.0 international",)),
    ("CC-BY-SA-4.0", ("attribution-sharealike 4.0 international",)),
    ("CC-BY-4.0", ("attribution 4.0 international",)),
    ("MIT", ("permission is hereby granted, free of charge, to any person obtaining a copy",)),
    ("ISC", ("permission to use, copy, modify, and/or distribute this software for any purpose",
             "provided that the above copyright notice")),
    ("ISC", ("permission to use, copy, modify, and distribute this software for any purpose",
             "provided that the above copyright notice")),
    ("0BSD", ("permission to use, copy, modify, and/or distribute this software for any purpose",)),
    ("BSD-3-Clause", ("redistribution and use in source and binary forms", "neither the name")),
    ("BSD-2-Clause", ("redistribution and use in source and binary forms",)),
]
NOT_OPEN_SOURCE = {"BUSL-1.1", "SSPL-1.0", "Elastic-2.0", "CC-BY-NC-SA-4.0", "CC-BY-NC-4.0"}

SPDX_IDS = {
    "MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "MPL-2.0",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
    "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
    "AGPL-3.0-only", "AGPL-3.0-or-later", "EPL-2.0", "BSL-1.0", "Unlicense", "CC0-1.0",
    "CC-BY-4.0", "CC-BY-SA-4.0", "Zlib", "Python-2.0", "Artistic-2.0", "EUPL-1.2",
    "BlueOak-1.0.0", "PostgreSQL", "Unicode-3.0", "BUSL-1.1", "SSPL-1.0", "Elastic-2.0",
    "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "WTFPL", "MPL-1.1", "EPL-1.0", "OFL-1.1",
}
SPDX_DEPRECATED = {"GPL-2.0", "GPL-2.0+", "GPL-3.0", "GPL-3.0+", "LGPL-2.1", "LGPL-2.1+",
                   "LGPL-3.0", "LGPL-3.0+", "AGPL-3.0"}
SPDX_LOOKUP = {x.lower(): x for x in SPDX_IDS | SPDX_DEPRECATED}
LICENSE_ALIASES = {
    "mit license": "MIT", "the mit license": "MIT", "mit/x11": "MIT",
    "apache 2.0": "Apache-2.0", "apache 2": "Apache-2.0", "apache-2": "Apache-2.0", "apache2": "Apache-2.0",
    "apache license 2.0": "Apache-2.0", "apache license, version 2.0": "Apache-2.0",
    "apache license version 2.0": "Apache-2.0", "apache software license": "Apache-2.0", "asl 2.0": "Apache-2.0",
    "bsd": "BSD", "bsd license": "BSD", "new bsd": "BSD-3-Clause", "simplified bsd": "BSD-2-Clause",
    "gplv3": "GPL-3.0", "gpl v3": "GPL-3.0", "gpl-3": "GPL-3.0", "gpl3": "GPL-3.0",
    "gplv2": "GPL-2.0", "gpl v2": "GPL-2.0", "gpl-2": "GPL-2.0", "gpl2": "GPL-2.0",
    "agplv3": "AGPL-3.0", "agpl-3": "AGPL-3.0", "lgplv3": "LGPL-3.0", "lgplv2.1": "LGPL-2.1",
    "mpl 2.0": "MPL-2.0", "mpl-2": "MPL-2.0", "isc license": "ISC", "public domain": "Unlicense",
}
CLASSIFIER_LICENSES = {
    "mit license": "MIT", "apache software license": "Apache-2.0", "bsd license": "BSD",
    "isc license (iscl)": "ISC", "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "gnu general public license v3 (gplv3)": "GPL-3.0", "gnu general public license v2 (gplv2)": "GPL-2.0",
    "gnu general public license v3 or later (gplv3+)": "GPL-3.0",
    "gnu affero general public license v3": "AGPL-3.0",
    "gnu affero general public license v3 or later (agplv3+)": "AGPL-3.0",
    "gnu lesser general public license v3 (lgplv3)": "LGPL-3.0",
    "gnu lesser general public license v2 or later (lgplv2+)": "LGPL-2.1",
    "the unlicense (unlicense)": "Unlicense", "eclipse public license 2.0 (epl-2.0)": "EPL-2.0",
}

# --- files that matter ---------------------------------------------------------

DOC_DIRS = ("", ".github/", "docs/")
DOC_EXTS = ("", ".md", ".markdown", ".rst", ".txt", ".adoc")
CI_PATTERNS = (".github/workflows/*.yml", ".github/workflows/*.yaml", ".gitlab-ci.yml", ".circleci/config.yml",
               "azure-pipelines.yml", "Jenkinsfile", ".buildkite/*", "bitbucket-pipelines.yml",
               ".woodpecker.yml", ".woodpecker/*", ".drone.yml", ".travis.yml", "appveyor.yml",
               ".forgejo/workflows/*", ".gitea/workflows/*")
DEP_UPDATE_FILES = ("renovate.json", ".github/renovate.json", ".gitlab/renovate.json", "renovate.json5",
                    ".github/renovate.json5", ".renovaterc", ".renovaterc.json", ".github/dependabot.yml",
                    ".github/dependabot.yaml")
ISSUE_TEMPLATE_PATTERNS = (".github/ISSUE_TEMPLATE/*", ".github/issue_template.md", "issue_template.md",
                           "docs/issue_template.md", ".gitlab/issue_templates/*")
PR_TEMPLATE_PATTERNS = (".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE/*",
                        "pull_request_template.md", "docs/pull_request_template.md",
                        ".gitlab/merge_request_templates/*")
TEST_DIR_NAMES = {"test", "tests", "spec", "specs", "__tests__", "testing"}
TEST_FILE_PATTERNS = ("*_test.go", "test_*.py", "*_test.py", "*.test.js", "*.test.ts", "*.test.jsx",
                      "*.test.tsx", "*.test.mjs", "*.spec.js", "*.spec.ts", "*.spec.tsx", "*_spec.rb",
                      "*Test.java", "*Tests.cs", "*_test.exs")

SAFE_MARKERS = (".example", ".sample", ".template", ".dist", ".tmpl", ".defaults", ".schema")
SECRET_NAME_PATTERNS = (".env", ".env.*", "*.p12", "*.pfx", "*.jks", "*.keystore", "*.kdbx", "id_rsa",
                        "id_dsa", "id_ecdsa", "id_ed25519", "*.tfstate", "*.tfstate.backup", "*.tfvars",
                        "credentials", "credentials.json", "*credentials*.json", "service-account*.json",
                        "*serviceaccount*.json", ".pypirc", ".netrc", ".htpasswd", ".git-credentials",
                        "secrets.yml", "secrets.yaml", "*.secret", "*.secrets")
KEY_NAME_PATTERNS = ("*.pem", "*.key")
DATA_NAME_PATTERNS = ("*.sqlite", "*.sqlite3", "*.db", "*.dump", "*.sql.gz", "*.bak", "*.mdb")

PUBLIC_HOSTS = {
    "registry.npmjs.org", "registry.npmjs.com", "registry.yarnpkg.com", "repo.yarnpkg.com",
    "pypi.org", "pypi.python.org", "files.pythonhosted.org", "index.crates.io", "crates.io",
    "static.crates.io", "github.com", "codeload.github.com", "objects.githubusercontent.com",
    "gitlab.com", "bitbucket.org", "codeberg.org", "rubygems.org", "index.rubygems.org",
    "proxy.golang.org", "download.pytorch.org", "conda.anaconda.org", "repo.anaconda.com",
    "repo.maven.apache.org", "repo1.maven.org", "plugins.gradle.org", "npm.jsr.io",
}
GO_PUBLIC_PREFIXES = ("github.com/", "gitlab.com/", "bitbucket.org/", "codeberg.org/", "golang.org/",
                      "google.golang.org/", "gopkg.in/", "go.googlesource.com/", "cloud.google.com/",
                      "go.opentelemetry.io/", "k8s.io/", "sigs.k8s.io/")
INTERNAL_SUFFIXES = (".internal", ".corp", ".local", ".lan", ".intranet", ".intra", ".home.arpa",
                     ".localdomain", ".private")
# Well-known names that look internal but are the same for everyone.
GENERIC_INTERNAL_NAMES = {"metadata.google.internal", "host.docker.internal", "gateway.docker.internal",
                          "kubernetes.docker.internal"}
GENERIC_INTERNAL_SUFFIXES = (".svc.cluster.local", ".cluster.local")
RESERVED_SUFFIXES = (".example", ".invalid", ".test", ".localhost")
RESERVED_NAMES = {"localhost", "example.com", "example.net", "example.org"}
# RFC 1918, shared address space (RFC 6598) and IPv6 unique local addresses. Documentation,
# benchmark and link-local ranges are left out: they reveal nothing about anyone's network.
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(n) for n in
                         ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7"))
EXAMPLE_DIR_NAMES = {"test", "tests", "spec", "specs", "__tests__", "testing", "testdata", "fixtures",
                     "fixture", "examples", "example", "samples", "sample", "mocks", "__mocks__", "evals", "e2e"}
DOC_FILE_EXTS = (".md", ".markdown", ".rst", ".txt", ".adoc", ".html")
URL_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://(?:[^\s/@'\"<>]*@)?([A-Za-z0-9][A-Za-z0-9.-]*)")
SCP_RE = re.compile(r"\bgit@([A-Za-z0-9][A-Za-z0-9.-]*):")
SEMVER_TAG_RE = re.compile(r"^v?\d+\.\d+\.\d+")
PRIVATE_KEY_RE = re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
NPMRC_AUTH_RE = re.compile(rb"(?im)^\s*[^#;\n]*(?:_authToken|_auth|_password)\s*=")
LOCKFILE_URL_RULES = {
    "package-lock.json": re.compile(r'"resolved"\s*:\s*"([^"]+)"'),
    "npm-shrinkwrap.json": re.compile(r'"resolved"\s*:\s*"([^"]+)"'),
    "yarn.lock": re.compile(r'^\s*resolved\s+"?([^"\s]+)', re.M),
    "pnpm-lock.yaml": re.compile(r"tarball:\s*'?\"?([^\s'\"}]+)"),
    "poetry.lock": re.compile(r'^\s*url\s*=\s*"([^"]+)"', re.M),
    "uv.lock": re.compile(r'(?:registry|url)\s*=\s*"([^"]+)"'),
    "pipfile.lock": re.compile(r'"url"\s*:\s*"([^"]+)"'),
    "pipfile": re.compile(r'^\s*url\s*=\s*"([^"]+)"', re.M),
    "cargo.lock": re.compile(r'^source\s*=\s*"(?:registry\+|sparse\+|git\+)?([^"]+)"', re.M),
    "gemfile": re.compile(r'^\s*source\s+["\']([^"\']+)', re.M),
    "gemfile.lock": re.compile(r"^\s*remote:\s*(\S+)", re.M),
    ".npmrc": re.compile(r"(?im)^\s*(?:@[\w.-]+:)?registry\s*=\s*(\S+)"),
    ".yarnrc": re.compile(r'(?im)^\s*registry\s+"?([^"\s]+)'),
    ".yarnrc.yml": re.compile(r'(?im)^\s*npmRegistryServer:\s*"?([^"\s]+)'),
    "pip.conf": re.compile(r"(?im)^\s*(?:extra-)?index-url\s*=\s*(\S+)"),
    "pip.ini": re.compile(r"(?im)^\s*(?:extra-)?index-url\s*=\s*(\S+)"),
}
REQ_INDEX_RE = re.compile(r"(?im)^\s*(?:--index-url|--extra-index-url|-i)[ =]\s*(\S+)")
CARGO_CONFIG_RE = re.compile(r'(?:index|registry)\s*=\s*"(?:sparse\+)?([^"]+)"')
TOML_INDEX_SECTIONS = {"[[tool.uv.index]]", "[[tool.poetry.source]]", "[[tool.pdm.source]]", "[[tool.rye.sources]]"}
TOML_PATH_RE = re.compile(r'\bpath\s*=\s*"([^"]+)"')
FILE_URL_RE = re.compile(r"@\s*file://([^\s\"',]+)")


class Report:
    def __init__(self) -> None:
        self.findings: List[Dict] = []

    def add(self, code: str, severity: str, path: str, message: str) -> None:
        self.findings.append({"code": code, "severity": severity, "path": path, "message": message})


# --- helpers -----------------------------------------------------------------

def _git(root: str, args: List[str]) -> str:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    proc = subprocess.run(["git", "-c", "core.quotepath=off", "-C", root] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False, env=env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def list_files(root: str, use_git: bool) -> Tuple[List[str], str, str]:
    """Return (posix relative paths, mode, note)."""
    note = ""
    if use_git:
        try:
            if _git(root, ["rev-parse", "--is-inside-work-tree"]).strip() == "true":
                out = _git(root, ["ls-files", "-z"])
                files = sorted(p for p in out.split("\0") if p and os.path.isfile(os.path.join(root, p)))
                return files, "git", note
            note = "not inside a git work tree"
        except (OSError, RuntimeError) as exc:
            note = f"git unavailable: {str(exc).splitlines()[0][:160]}"
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            found.append(PurePosixPath(Path(rel)).as_posix())
    return sorted(found), "walk", note


def read_bytes(root: str, rel: str, limit: int = MAX_TEXT_BYTES) -> Optional[bytes]:
    try:
        path = os.path.join(root, rel)
        if os.path.getsize(path) > limit:
            return None
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def read_text(root: str, rel: str, limit: int = MAX_TEXT_BYTES) -> Optional[str]:
    data = read_bytes(root, rel, limit)
    if data is None or b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def matches(name: str, patterns: Iterable[str]) -> bool:
    low = name.lower()
    return any(fnmatch.fnmatchcase(low, p.lower()) for p in patterns)


def find_doc(files: Set[str], lower_map: Dict[str, str], stems: Iterable[str]) -> Optional[str]:
    for d in DOC_DIRS:
        for stem in stems:
            for ext in DOC_EXTS:
                hit = lower_map.get(f"{d}{stem}{ext}".lower())
                if hit:
                    return hit
    return None


def any_match(files: Iterable[str], patterns: Iterable[str]) -> Optional[str]:
    pats = [p.lower() for p in patterns]
    for f in files:
        low = f.lower()
        if any(fnmatch.fnmatchcase(low, p) for p in pats):
            return f
    return None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()


def detect_license(text: str) -> Optional[str]:
    norm = normalize_text(text)
    for spdx, phrases in LICENSE_FINGERPRINTS:
        if all(p in norm for p in phrases):
            return spdx
    return None


def family(spdx: str) -> str:
    base = spdx[:-1] if spdx.endswith("+") else spdx
    for suffix in ("-only", "-or-later"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base


def families_match(a: str, b: str) -> bool:
    if a == b:
        return True
    bsd = {"BSD-2-Clause", "BSD-3-Clause", "0BSD"}
    return (a == "BSD" and b in bsd) or (b == "BSD" and a in bsd)


def parse_license_expr(expr: str) -> Tuple[List[str], List[str]]:
    """Return (normalized ids, notes). Unknown names are kept as given with a note."""
    notes: List[str] = []
    raw = expr.strip()
    if not raw:
        return [], notes
    alias = LICENSE_ALIASES.get(raw.lower())
    if alias:
        notes.append(f"'{raw}' is not an SPDX expression; use '{alias if alias != 'BSD' else 'BSD-3-Clause or BSD-2-Clause'}'")
        return [alias], notes
    parts = [p for p in re.split(r"\s+(?:OR|AND|WITH)\s+|[()]|\s*/\s*", raw) if p and p.strip()]
    if "/" in raw:
        notes.append(f"'{raw}' uses '/'; SPDX expressions join licenses with OR or AND")
    ids: List[str] = []
    for part in (p.strip() for p in parts):
        low = part.lower()
        if low in SPDX_LOOKUP:
            ident = SPDX_LOOKUP[low]
            if ident in SPDX_DEPRECATED:
                notes.append(f"'{ident}' is a deprecated SPDX identifier; use '{ident.rstrip('+')}-only' or "
                             f"'{ident.rstrip('+')}-or-later'")
            ids.append(ident)
        elif low.startswith("licenseref-") or low.startswith("exception") or low.endswith("-exception"):
            continue
        elif low in LICENSE_ALIASES:
            ids.append(LICENSE_ALIASES[low])
            notes.append(f"'{part}' is not an SPDX identifier; use '{LICENSE_ALIASES[low]}'")
        else:
            ids.append(part)
            notes.append(f"'{part}' is not a recognized SPDX identifier")
    return ids, notes


def load_toml(text: str) -> Optional[dict]:
    if tomllib is None:
        return None
    try:
        return tomllib.loads(text)
    except Exception:  # noqa: BLE001 - malformed manifests are reported, not fatal
        return None


def toml_string_fallback(text: str, key: str) -> Optional[str]:
    m = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


# --- checks ------------------------------------------------------------------

def declared_licenses(root: str, lower_map: Dict[str, str], report: Report) -> Dict[str, List[str]]:
    """Return {manifest path: [declared ids]} for root-level manifests."""
    declared: Dict[str, List[str]] = {}

    def record(path: str, expr: Optional[str]) -> None:
        if expr is None:
            report.add("LICENSE_NOT_DECLARED", "INFO", path,
                       "no license declared in this manifest; package indexes will show none")
            return
        if expr.strip().upper() == "UNLICENSED":
            report.add("LICENSE_DECLARED_PROPRIETARY", "WARN", path,
                       "license is 'UNLICENSED', which in npm means not licensed for others to use "
                       "(not the same as 'Unlicense'); set the SPDX identifier of the chosen license")
            declared[path] = []
            return
        if expr.strip().upper().startswith("SEE LICENSE IN"):
            declared[path] = []
            return
        ids, notes = parse_license_expr(expr)
        for note in notes:
            report.add("LICENSE_NOT_SPDX", "INFO", path, note)
        declared[path] = ids

    pkg = lower_map.get("package.json")
    if pkg:
        text = read_text(root, pkg)
        try:
            data = json.loads(text) if text else None
        except ValueError:
            data = None
        if isinstance(data, dict):
            lic = data.get("license")
            if isinstance(lic, dict):
                lic = lic.get("type")
            if lic is None and isinstance(data.get("licenses"), list):
                types = [x.get("type") for x in data["licenses"] if isinstance(x, dict) and x.get("type")]
                lic = " OR ".join(types) if types else None
            record(pkg, lic if isinstance(lic, str) else None)
            if data.get("private") is True:
                report.add("PACKAGE_PRIVATE", "INFO", pkg,
                           "\"private\": true blocks publishing to npm; remove it if the package will be published")
            check_package_json_paths(root, pkg, data, report)

    py = lower_map.get("pyproject.toml")
    py_has_project = False
    if py:
        text = read_text(root, py) or ""
        data = load_toml(text)
        expr: Optional[str] = None
        if data is not None:
            project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
            lic = project.get("license")
            if isinstance(lic, str):
                expr = lic
            elif isinstance(lic, dict) and isinstance(lic.get("text"), str):
                expr = lic["text"]
            elif isinstance(lic, dict) and isinstance(lic.get("file"), str):
                expr = "SEE LICENSE IN " + lic["file"]
            if expr is None:
                poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
                if isinstance(poetry, dict) and isinstance(poetry.get("license"), str):
                    expr = poetry["license"]
            if expr is None:
                for classifier in project.get("classifiers", []) or []:
                    if isinstance(classifier, str) and classifier.lower().startswith("license ::"):
                        tail = classifier.split("::")[-1].strip().lower()
                        if tail in CLASSIFIER_LICENSES:
                            expr = CLASSIFIER_LICENSES[tail]
                            break
            has_project = bool(project) or "poetry" in (data.get("tool") or {})
        else:
            expr = toml_string_fallback(text, "license")
            has_project = "[project]" in text or "[tool.poetry]" in text
        if has_project:
            py_has_project = True
            record(py, expr)

    cargo = lower_map.get("cargo.toml")
    if cargo:
        text = read_text(root, cargo) or ""
        data = load_toml(text)
        expr = None
        is_package = "[package]" in text
        if data is not None:
            package = data.get("package") if isinstance(data.get("package"), dict) else None
            is_package = package is not None
            if package:
                lic = package.get("license")
                if isinstance(lic, dict) and lic.get("workspace"):
                    lic = (data.get("workspace", {}).get("package", {}) or {}).get("license")
                if isinstance(lic, str):
                    expr = lic
                elif isinstance(package.get("license-file"), str):
                    expr = "SEE LICENSE IN " + package["license-file"]
        else:
            expr = toml_string_fallback(text, "license")
        if is_package:
            record(cargo, expr)

    composer = lower_map.get("composer.json")
    if composer:
        text = read_text(root, composer)
        try:
            data = json.loads(text) if text else None
        except ValueError:
            data = None
        if isinstance(data, dict):
            lic = data.get("license")
            if isinstance(lic, list):
                lic = " OR ".join(x for x in lic if isinstance(x, str)) or None
            record(composer, lic if isinstance(lic, str) else None)

    setup_cfg = lower_map.get("setup.cfg")
    if setup_cfg and not py_has_project:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(read_text(root, setup_cfg) or "")
            if parser.has_section("metadata"):
                record(setup_cfg, parser.get("metadata", "license", fallback=None))
        except configparser.Error:
            pass

    for rel in sorted(lower_map.values()):
        if "/" not in rel and rel.lower().endswith(".gemspec"):
            text = read_text(root, rel) or ""
            m = re.search(r"\.licenses?\s*=\s*(\[[^\]]*\]|\"[^\"]*\"|'[^']*')", text)
            if m:
                names = re.findall(r"[\"']([^\"']+)[\"']", m.group(1))
                record(rel, " OR ".join(names) if names else None)
            else:
                record(rel, None)
    return declared


def check_licenses(root: str, files: List[str], lower_map: Dict[str, str], report: Report,
                   present: Dict) -> Dict:
    license_files = [f for f in files if "/" not in f and re.match(
        r"(?i)^(licen[cs]e|copying|unlicense)([-._].*)?$", f)]
    if not license_files:  # REUSE layout keeps license texts in LICENSES/
        license_files = [f for f in files if f.lower().startswith("licenses/") and f.count("/") == 1]
    detected: Dict[str, Optional[str]] = {}
    for rel in license_files:
        text = read_text(root, rel)
        detected[rel] = detect_license(text) if text else None
    present["license"] = license_files
    if not license_files:
        report.add("NO_LICENSE", "WARN", "",
                   "no LICENSE file at the root: without one, nobody may legally use, copy or change the code; "
                   "the owner chooses the license")
    for rel, ident in sorted(detected.items()):
        if ident is None:
            report.add("LICENSE_UNRECOGNIZED", "INFO", rel,
                       "license text not recognized; confirm it is a standard license and name it in the README")
        elif ident in NOT_OPEN_SOURCE:
            report.add("LICENSE_NOT_OPEN_SOURCE", "WARN", rel,
                       f"text looks like {ident}, which is not an OSI-approved open-source license; "
                       "confirm with the owner that this is intended")

    declared = declared_licenses(root, lower_map, report)
    file_ids = sorted({family(x) for x in detected.values() if x})
    for manifest, ids in sorted(declared.items()):
        fams = sorted({family(x) for x in ids})
        if not fams or not file_ids:
            continue
        overlap = [f for f in fams if any(families_match(f, g) for g in file_ids)]
        if not overlap:
            report.add("LICENSE_MISMATCH", "WARN", manifest,
                       f"declares {', '.join(fams)} but the LICENSE text is {', '.join(file_ids)}; make them agree")
            continue
        missing = [f for f in fams if not any(families_match(f, g) for g in file_ids)]
        if missing:
            report.add("LICENSE_TEXT_MISSING", "INFO", manifest,
                       f"declares {', '.join(missing)} but no license file contains that text")
        extra = [g for g in file_ids if not any(families_match(f, g) for f in fams)]
        if extra:
            report.add("LICENSE_UNDECLARED_TEXT", "INFO", manifest,
                       f"license text for {', '.join(extra)} is present but this manifest does not declare it")
    return {"files": {k: v for k, v in sorted(detected.items())},
            "declared": {k: v for k, v in sorted(declared.items())}}


def check_docs(root: str, files: List[str], lower_map: Dict[str, str], report: Report, present: Dict) -> None:
    readme = find_doc(set(files), lower_map, ("readme",))
    present["readme"] = readme
    if not readme:
        report.add("NO_README", "WARN", "", "no README: outsiders cannot tell what the project is or how to use it")
    else:
        text = (read_text(root, readme) or "").lower()
        gaps = []
        if not re.search(r"\binstall|\bsetup\b|getting started|quick ?start|\bbuild", text):
            gaps.append("installation or setup")
        if not re.search(r"\busage\b|\bexample|how to use|quick ?start|getting started", text):
            gaps.append("usage example")
        if not re.search(r"licen[cs]e", text):
            gaps.append("license")
        if gaps:
            report.add("README_GAPS", "INFO", readme, "README does not seem to cover: " + ", ".join(gaps))

    security = find_doc(set(files), lower_map, ("security",))
    present["security_policy"] = security
    if not security:
        report.add("NO_SECURITY_POLICY", "WARN", "",
                   "no SECURITY.md: say how to report a vulnerability privately before the repository is public")
    else:
        text = (read_text(root, security) or "").lower()
        if not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+|https?://|security/advisories|private vulnerability report", text):
            report.add("SECURITY_POLICY_NO_CONTACT", "INFO", security,
                       "security policy names no contact address, URL or private reporting channel")

    for key, stems, code, message in (
        ("contributing", ("contributing",), "NO_CONTRIBUTING",
         "no CONTRIBUTING guide: development setup, test commands and how changes are reviewed"),
        ("code_of_conduct", ("code_of_conduct", "code-of-conduct"), "NO_CODE_OF_CONDUCT",
         "no code of conduct; add one if outside contributors are expected"),
        ("changelog", ("changelog", "changes", "history", "news", "releases"), "NO_CHANGELOG",
         "no changelog; users need to see what changed between releases"),
    ):
        hit = find_doc(set(files), lower_map, stems)
        present[key] = hit
        if not hit:
            report.add(code, "INFO", "", message)

    present["gitignore"] = lower_map.get(".gitignore")
    if not present["gitignore"]:
        report.add("NO_GITIGNORE", "INFO", "", "no .gitignore; build output and local files may get committed")
    present["ci"] = any_match(files, CI_PATTERNS)
    if not present["ci"]:
        report.add("NO_CI", "INFO", "", "no CI configuration found; outside pull requests need automated checks")
    present["dependency_updates"] = next((lower_map[p.lower()] for p in DEP_UPDATE_FILES if p.lower() in lower_map), None)
    if not present["dependency_updates"]:
        report.add("NO_DEPENDENCY_UPDATES", "INFO", "", "no Dependabot or Renovate configuration")
    present["issue_templates"] = any_match(files, ISSUE_TEMPLATE_PATTERNS)
    if not present["issue_templates"]:
        report.add("NO_ISSUE_TEMPLATE", "INFO", "", "no issue templates; reports will arrive without versions or steps")
    present["pr_template"] = any_match(files, PR_TEMPLATE_PATTERNS)
    if not present["pr_template"]:
        report.add("NO_PR_TEMPLATE", "INFO", "", "no pull request template")
    tests = next((f for f in files if any(part.lower() in TEST_DIR_NAMES for part in f.split("/")[:-1])
                  or matches(f.rsplit("/", 1)[-1], TEST_FILE_PATTERNS)), None)
    present["tests"] = tests
    if not tests:
        report.add("NO_TESTS", "INFO", "", "no test files found; contributors need a way to check their changes")


def is_safe_sample(name: str) -> bool:
    low = name.lower()
    return any(marker in low for marker in SAFE_MARKERS)


def sensitive_kind(name: str) -> Optional[str]:
    base = name.rsplit("/", 1)[-1]
    if is_safe_sample(base):
        return None
    if matches(base, SECRET_NAME_PATTERNS):
        return "secret"
    if matches(base, KEY_NAME_PATTERNS):
        return "key"
    if base.lower() == ".npmrc":
        return "npmrc"
    if matches(base, DATA_NAME_PATTERNS):
        return "data"
    return None


def check_sensitive(root: str, files: List[str], report: Report) -> None:
    for rel in files:
        kind = sensitive_kind(rel)
        if kind == "secret":
            report.add("SENSITIVE_FILE", "WARN", rel,
                       "tracked file whose name suggests secrets; it would be published (contents not read)")
        elif kind == "key":
            data = read_bytes(root, rel) or b""
            if PRIVATE_KEY_RE.search(data):
                report.add("SENSITIVE_FILE", "WARN", rel, "tracked file contains a private key block (value not shown)")
        elif kind == "npmrc":
            data = read_bytes(root, rel) or b""
            if NPMRC_AUTH_RE.search(data):
                report.add("SENSITIVE_FILE", "WARN", rel, ".npmrc sets an auth token or password (value not shown)")
        elif kind == "data":
            report.add("DATA_FILE", "INFO", rel, "database, dump or backup file; check it holds no real or customer data")


def check_large(root: str, files: List[str], limit_mb: float, report: Report) -> None:
    if limit_mb <= 0:
        return
    for rel in files:
        try:
            size = os.path.getsize(os.path.join(root, rel))
        except OSError:
            continue
        if size > limit_mb * 1024 * 1024:
            report.add("LARGE_FILE", "INFO", rel,
                       f"{size / (1024 * 1024):.1f} MB tracked file; check it is needed and may be redistributed")


def is_reserved_host(host: str) -> bool:
    return host in RESERVED_NAMES or host.endswith(RESERVED_SUFFIXES) or \
        any(host.endswith("." + n) for n in RESERVED_NAMES)


def is_test_or_example(rel: str) -> bool:
    parts = rel.lower().split("/")
    return any(p in EXAMPLE_DIR_NAMES for p in parts[:-1]) or matches(parts[-1], TEST_FILE_PATTERNS)


def host_is_internal(host: str) -> Optional[str]:
    """Return 'ip' for a private network address, 'name' for an internal-looking hostname, else None."""
    host = host.lower().rstrip(".")
    if is_reserved_host(host) or host in GENERIC_INTERNAL_NAMES or host.endswith(GENERIC_INTERNAL_SUFFIXES):
        return None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        return "ip" if any(ip in net for net in PRIVATE_NETWORKS if net.version == ip.version) else None
    if host.endswith(INTERNAL_SUFFIXES):
        return "name"
    return None


def check_internal_hosts(root: str, files: List[str], report: Report) -> None:
    """Internal hostnames anywhere outside tests and examples; private addresses only in code and config."""
    seen: Set[Tuple[str, str]] = set()
    count = 0
    for rel in files:
        if is_test_or_example(rel):
            continue
        is_doc = rel.lower().endswith(DOC_FILE_EXTS)
        text = read_text(root, rel)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "://" not in line and "git@" not in line:
                continue
            for m in list(URL_RE.finditer(line)) + list(SCP_RE.finditer(line)):
                host = m.group(1).rstrip(".-").lower()
                kind = host_is_internal(host)
                if not kind or (kind == "ip" and is_doc) or (rel, host) in seen:
                    continue
                why = "private network address" if kind == "ip" else "internal hostname"
                seen.add((rel, host))
                count += 1
                if count > MAX_LISTED:
                    continue
                report.add("INTERNAL_HOST", "INFO", f"{rel}:{lineno}",
                           f"{why} '{host}' will be visible and unreachable for outsiders")
    if count > MAX_LISTED:
        report.add("INTERNAL_HOST", "INFO", "", f"{count - MAX_LISTED} more internal host references not listed")


def url_host(url: str) -> Optional[str]:
    m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^/@\s]*@)?([^/:\s?#]+)", url.strip().strip("'\""), re.I)
    return m.group(1).lower() if m else None


def check_registries(root: str, files: List[str], report: Report) -> None:
    for rel in files:
        base = rel.rsplit("/", 1)[-1].lower()
        rule = LOCKFILE_URL_RULES.get(base)
        hosts: Set[str] = set()
        text: Optional[str] = None
        if rule is not None or (base.startswith("requirements") and base.endswith(".txt")) or \
                base == "pyproject.toml" or rel.lower().endswith(".cargo/config.toml") or \
                rel.lower().endswith(".cargo/config"):
            text = read_text(root, rel, limit=20_000_000)
        if text is None:
            continue
        urls: List[str] = []
        if rule is not None:
            urls = rule.findall(text)
        elif base.startswith("requirements"):
            urls = REQ_INDEX_RE.findall(text)
        elif base == "pyproject.toml":
            section = ""
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("["):
                    section = stripped
                elif section in TOML_INDEX_SECTIONS:
                    m = re.match(r'url\s*=\s*"([^"]+)"', stripped)
                    if m:
                        urls.append(m.group(1))
        else:
            urls = CARGO_CONFIG_RE.findall(text)
        for url in urls:
            host = url_host(url)
            if host and host not in PUBLIC_HOSTS:
                hosts.add(host)
        for host in sorted(hosts):
            report.add("NON_PUBLIC_REGISTRY", "INFO", rel,
                       f"packages or indexes come from '{host}', not a default public registry; check that "
                       "outsiders can install from it without credentials")


def _outside(root: str, base_rel: str, target: str) -> bool:
    if target.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", target):
        return True
    start = os.path.dirname(os.path.join(root, base_rel))
    resolved = os.path.normpath(os.path.join(start, target))
    root_abs = os.path.normpath(os.path.abspath(root))
    return not os.path.abspath(resolved).startswith(root_abs + os.sep) and os.path.abspath(resolved) != root_abs


def check_package_json_paths(root: str, rel: str, data: dict, report: Report) -> None:
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name, spec in sorted(deps.items()):
            if isinstance(spec, str):
                m = re.match(r"^(?:file|link|portal):(.+)$", spec.strip())
                if m and _outside(root, rel, m.group(1)):
                    report.add("DEPENDENCY_OUTSIDE_REPO", "WARN", rel,
                               f"{section}.{name} points to a path outside the repository; a fresh clone cannot build")


def check_local_paths(root: str, files: List[str], report: Report) -> None:
    for rel in files:
        base = rel.rsplit("/", 1)[-1].lower()
        if base in ("cargo.toml", "pyproject.toml"):
            text = read_text(root, rel) or ""
            targets = TOML_PATH_RE.findall(text) + FILE_URL_RE.findall(text)
        elif base == "go.mod":
            text = read_text(root, rel) or ""
            targets = re.findall(r"=>\s*(\.{1,2}/\S*|/\S+)", text)
            m = re.search(r"(?m)^module\s+(\S+)", text)
            module_host = m.group(1).split("/")[0].lower() if m else ""
            if m and "." in module_host and not m.group(1).startswith(GO_PUBLIC_PREFIXES) \
                    and not is_reserved_host(module_host) and not is_test_or_example(rel):
                report.add("MODULE_PATH_HOST", "INFO", rel,
                           f"module path host '{m.group(1).split('/')[0]}' must serve public `go get` requests "
                           "(a vanity domain is fine if it does)")
        elif base.startswith("requirements") and base.endswith(".txt"):
            text = read_text(root, rel) or ""
            targets = re.findall(r"(?m)^\s*(?:-e\s+)?(\.{1,2}/\S+|/\S+)", text) + FILE_URL_RE.findall(text)
            targets += re.findall(r"(?m)^\s*(?:-e\s+)?file://(\S+)", text)
        else:
            continue
        for target in sorted(set(targets)):
            if _outside(root, rel, target):
                report.add("DEPENDENCY_OUTSIDE_REPO", "WARN", rel,
                           "a dependency or replacement points to a path outside the repository; "
                           "a fresh clone cannot build")
                break


def check_submodules(root: str, lower_map: Dict[str, str], report: Report) -> None:
    rel = lower_map.get(".gitmodules")
    if not rel:
        return
    text = read_text(root, rel) or ""
    for m in re.finditer(r"(?m)^\s*url\s*=\s*(\S+)", text):
        url = m.group(1)
        host = url_host(url) or (SCP_RE.search(url).group(1) if SCP_RE.search(url) else "local path")
        report.add("SUBMODULE", "INFO", rel, f"submodule from '{host}': it must be public too, or outsiders cannot clone it")


def check_git(root: str, files: List[str], report: Report, history: bool) -> Dict:
    info: Dict = {}
    head = set(files)
    if history:
        try:
            added = _git(root, ["log", "--all", "--diff-filter=A", "--name-only", "--relative", "--format="])
            past = sorted({p for p in added.splitlines() if p and p not in head and sensitive_kind(p) in ("secret", "key")})
            for p in past[:MAX_LISTED]:
                report.add("SENSITIVE_FILE_IN_HISTORY", "WARN", p,
                           "a file with a sensitive name existed in history; it is published with the history "
                           "unless the repository starts fresh (scan values with a secret scanner)")
            if len(past) > MAX_LISTED:
                report.add("SENSITIVE_FILE_IN_HISTORY", "WARN", "", f"{len(past) - MAX_LISTED} more not listed")
        except (OSError, RuntimeError):
            pass
        try:
            emails = _git(root, ["log", "--all", "--format=%ae%n%ce"]).split()
            domains: Dict[str, int] = {}
            for email in emails:
                domain = email.rsplit("@", 1)[-1].lower() if "@" in email else "(no domain)"
                domains[domain] = domains.get(domain, 0) + 1
            info["commit_email_domains"] = dict(sorted(domains.items(), key=lambda kv: (-kv[1], kv[0])))
            if domains:
                shown = ", ".join(f"{d} ({n})" for d, n in list(info["commit_email_domains"].items())[:10])
                report.add("COMMIT_EMAIL_DOMAINS", "INFO", "",
                           "author and committer emails become public with the history; domains: " + shown)
        except (OSError, RuntimeError):
            pass
    try:
        tags = [t for t in _git(root, ["tag", "--list"]).splitlines() if t]
        info["version_tags"] = sum(1 for t in tags if SEMVER_TAG_RE.match(t))
        if not info["version_tags"]:
            report.add("NO_VERSION_TAGS", "INFO", "", "no version tags (vX.Y.Z); releases will be hard to reference")
    except (OSError, RuntimeError):
        pass
    return info


def analyze(root: str, use_git: bool = True, history: bool = True, large_file_mb: float = 5.0) -> Dict:
    files, mode, note = list_files(root, use_git)
    lower_map: Dict[str, str] = {}
    for f in files:
        lower_map.setdefault(f.lower(), f)
    report = Report()
    present: Dict = {}
    if use_git and mode == "walk":
        report.add("NOT_A_GIT_CHECKOUT", "INFO", "", f"listed files from disk ({note}); history was not checked")
    check_docs(root, files, lower_map, report, present)
    licenses = check_licenses(root, files, lower_map, report, present)
    check_sensitive(root, files, report)
    check_large(root, files, large_file_mb, report)
    check_internal_hosts(root, files, report)
    check_registries(root, files, report)
    check_local_paths(root, files, report)
    check_submodules(root, lower_map, report)
    git_info = check_git(root, files, report, history) if mode == "git" else {}
    report.findings.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["code"], x["path"], x["message"]))
    not_checked = [
        "secret values in files and history (use a secret scanner, for example code_audit.py history or Gitleaks)",
        "licenses of dependencies and vendored code",
        "CI workflow security for public forks (for example code_audit.py workflows)",
        "issues, wiki, CI logs, releases and artifacts on the hosting platform",
        "whether the README instructions work from a clean clone",
    ]
    return {
        "tool": "oss_readiness",
        "version": VERSION,
        "mode": mode,
        "summary": {
            "files": len(files),
            "warn": sum(1 for x in report.findings if x["severity"] == "WARN"),
            "info": sum(1 for x in report.findings if x["severity"] == "INFO"),
        },
        "present": dict(sorted(present.items())),
        "licenses": licenses,
        "git": git_info,
        "findings": report.findings,
        "not_checked": not_checked,
    }


def format_text(report: Dict) -> str:
    s = report["summary"]
    out = [f"oss_readiness {report['version']}: {s['files']} file(s) ({report['mode']} mode), "
           f"{s['warn']} warn, {s['info']} info", ""]
    out.append("Front door")
    labels = [("readme", "README"), ("license", "LICENSE"), ("security_policy", "Security policy"),
              ("contributing", "Contributing guide"), ("code_of_conduct", "Code of conduct"),
              ("changelog", "Changelog"), ("ci", "CI configuration"), ("dependency_updates", "Dependency updates"),
              ("issue_templates", "Issue templates"), ("pr_template", "PR template"), ("tests", "Tests")]
    for key, label in labels:
        value = report["present"].get(key)
        if key == "license":
            lic = report["licenses"]["files"]
            value = ", ".join(f"{k} ({v or 'unrecognized'})" for k, v in lic.items()) or None
        out.append(f"  [{'x' if value else ' '}] {label}" + (f": {value}" if value else ""))
    declared = report["licenses"]["declared"]
    if declared:
        out.append("  Declared in manifests: " + "; ".join(f"{k}: {' OR '.join(v) or '(see file)'}" for k, v in declared.items()))
    out.append("")
    if report["findings"]:
        out.append("Findings")
        for x in report["findings"]:
            out.append(f"  {x['severity']:<4}  {x['code']:<29} {x['path'] or '(repository)'}")
            out.append(f"        {x['message']}")
    else:
        out.append("Findings: none")
    out.append("")
    out.append("Not checked by this tool:")
    out.extend(f"  - {item}" for item in report["not_checked"])
    out.append("")
    out.append("Advisory only: each finding is a prompt to check, not a verdict. The owner decides what ships.")
    return "\n".join(out) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="oss_readiness.py",
        description=(
            "Read-only open-source readiness check: README, LICENSE, SECURITY.md and other\n"
            "front-door files; LICENSE text versus licenses declared in package.json,\n"
            "pyproject.toml, Cargo.toml, composer.json, setup.cfg and gemspecs; tracked files\n"
            "with secret-like names; sensitive names in history; internal hostnames, private\n"
            "registries and path dependencies outside the repository; commit email domains.\n"
            "Never edits files or uses the network; never prints file contents."
        ),
        epilog=(
            "Examples:\n"
            "  python3 oss_readiness.py                      # current directory, tracked files via git\n"
            "  python3 oss_readiness.py --root ../service --json\n"
            "  python3 oss_readiness.py --no-git --large-file-mb 2\n\n"
            "In a git checkout only tracked files are checked, because those are what gets published.\n"
            "Exit codes: 0 report written; 1 with --strict when a WARN finding exists; 2 usage or input error."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--root", default=".", help="repository directory (default: .)")
    p.add_argument("--no-git", action="store_true", help="walk the directory instead of asking git for tracked files")
    p.add_argument("--no-history", action="store_true", help="skip the history checks (sensitive names, email domains)")
    p.add_argument("--large-file-mb", type=float, default=5.0,
                   help="flag tracked files larger than this many MB; 0 disables (default: 5)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.add_argument("--strict", action="store_true", help="exit 1 when any WARN finding is present")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not os.path.isdir(args.root):
        print(f"oss_readiness: error: not a directory: {args.root}", file=sys.stderr)
        return 2
    report = analyze(args.root, use_git=not args.no_git, history=not args.no_history,
                     large_file_mb=args.large_file_mb)
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(format_text(report))
    if args.strict and report["summary"]["warn"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
