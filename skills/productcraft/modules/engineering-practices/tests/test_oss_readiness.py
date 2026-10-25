"""Offline tests for oss_readiness.py using temporary directories only; no network."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "oss_readiness.py"
spec = importlib.util.spec_from_file_location("oss_readiness", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

MIT_TEXT = """MIT License

Copyright (c) 2026 Example Maintainers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction.
"""
APACHE_TEXT = """
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/
"""
GPL3_TEXT = """                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007
 ... use the GNU Lesser General Public License instead of this License.
"""
LGPL3_TEXT = """                   GNU LESSER GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007
  This version of the GNU Lesser General Public License incorporates
the terms and conditions of version 3 of the GNU General Public License.
"""
AGPL3_TEXT = """                    GNU AFFERO GENERAL PUBLIC LICENSE
                       Version 3, 19 November 2007
"""
BSD3_TEXT = """Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
3. Neither the name of the copyright holder nor the names of its contributors may be used.
"""
BSD2_TEXT = """Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
"""
ISC_TEXT = """Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.
"""
ZERO_BSD_TEXT = """Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.
"""
BUSL_TEXT = "Business Source License 1.1\n\nParameters\n"
README = "# Tool\n\nWhat it does.\n\n## Install\n\npip install tool\n\n## Usage\n\nExample: tool run\n\n## License\n\nMIT\n"
SECURITY = "# Security\n\nReport vulnerabilities to security@example.org.\n"


def write(root, rel, text="", mode="w"):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "wb":
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def complete_repo(root):
    write(root, "README.md", README)
    write(root, "LICENSE", MIT_TEXT)
    write(root, "SECURITY.md", SECURITY)
    write(root, "CONTRIBUTING.md", "# Contributing\n")
    write(root, "CODE_OF_CONDUCT.md", "# Code of conduct\n")
    write(root, "CHANGELOG.md", "# Changelog\n")
    write(root, ".gitignore", "node_modules/\n.env\n")
    write(root, ".github/workflows/ci.yml", "on: [push]\n")
    write(root, ".github/dependabot.yml", "version: 2\n")
    write(root, ".github/ISSUE_TEMPLATE/bug.yml", "name: Bug\n")
    write(root, ".github/pull_request_template.md", "## What\n")
    write(root, "tests/test_tool.py", "def test_ok():\n    assert True\n")
    write(root, "package.json", json.dumps({"name": "tool", "license": "MIT"}))


def codes(report, severity=None):
    return sorted(f["code"] for f in report["findings"] if severity is None or f["severity"] == severity)


def run_cli(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = module.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="oss-readiness-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def analyze(self, **kwargs):
        kwargs.setdefault("use_git", False)
        return module.analyze(self.root, **kwargs)


class LicenseDetectionTests(unittest.TestCase):
    def test_recognizes_common_license_texts(self):
        cases = {
            "MIT": MIT_TEXT, "Apache-2.0": APACHE_TEXT, "GPL-3.0": GPL3_TEXT, "LGPL-3.0": LGPL3_TEXT,
            "AGPL-3.0": AGPL3_TEXT, "BSD-3-Clause": BSD3_TEXT, "BSD-2-Clause": BSD2_TEXT,
            "ISC": ISC_TEXT, "0BSD": ZERO_BSD_TEXT, "BUSL-1.1": BUSL_TEXT,
        }
        for expected, text in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(module.detect_license(text), expected)

    def test_gpl_text_mentioning_lesser_gpl_is_still_gpl(self):
        self.assertEqual(module.detect_license(GPL3_TEXT), "GPL-3.0")

    def test_unknown_text(self):
        self.assertIsNone(module.detect_license("All rights reserved. Internal use only."))

    def test_parses_spdx_expressions_and_aliases(self):
        ids, notes = module.parse_license_expr("MIT OR Apache-2.0")
        self.assertEqual(ids, ["MIT", "Apache-2.0"])
        self.assertEqual(notes, [])
        ids, notes = module.parse_license_expr("Apache-2.0 WITH LLVM-exception")
        self.assertEqual(ids, ["Apache-2.0"])
        ids, notes = module.parse_license_expr("Apache 2.0")
        self.assertEqual(ids, ["Apache-2.0"])
        self.assertTrue(notes)
        ids, notes = module.parse_license_expr("GPL-3.0")
        self.assertEqual(module.family(ids[0]), "GPL-3.0")
        self.assertIn("deprecated", notes[0])
        self.assertEqual(module.family("GPL-3.0-or-later"), "GPL-3.0")


class FrontDoorTests(TempRepo):
    def test_empty_repository_warns_on_the_essentials(self):
        write(self.root, "main.py", "print('hi')\n")
        report = self.analyze()
        self.assertEqual(codes(report, "WARN"), ["NO_LICENSE", "NO_README", "NO_SECURITY_POLICY"])
        for code in ("NO_CI", "NO_TESTS", "NO_CONTRIBUTING", "NO_CHANGELOG", "NO_ISSUE_TEMPLATE"):
            self.assertIn(code, codes(report, "INFO"))

    def test_complete_repository_has_no_findings(self):
        complete_repo(self.root)
        report = self.analyze()
        self.assertEqual(report["findings"], [], report["findings"])
        self.assertEqual(report["licenses"]["files"], {"LICENSE": "MIT"})
        self.assertEqual(report["licenses"]["declared"], {"package.json": ["MIT"]})

    def test_docs_in_dot_github_count(self):
        complete_repo(self.root)
        os.remove(Path(self.root) / "SECURITY.md")
        write(self.root, ".github/SECURITY.md", SECURITY)
        self.assertNotIn("NO_SECURITY_POLICY", codes(self.analyze()))

    def test_security_policy_without_contact(self):
        complete_repo(self.root)
        write(self.root, "SECURITY.md", "# Security\n\nPlease be responsible.\n")
        self.assertIn("SECURITY_POLICY_NO_CONTACT", codes(self.analyze(), "INFO"))

    def test_readme_gaps(self):
        complete_repo(self.root)
        write(self.root, "README.md", "# Tool\n\nIt is a tool.\n")
        findings = [f for f in self.analyze()["findings"] if f["code"] == "README_GAPS"]
        self.assertEqual(len(findings), 1)
        self.assertIn("license", findings[0]["message"])


class LicenseConsistencyTests(TempRepo):
    def test_mismatch_between_license_file_and_manifest(self):
        complete_repo(self.root)
        write(self.root, "package.json", json.dumps({"name": "tool", "license": "Apache-2.0"}))
        report = self.analyze()
        self.assertIn("LICENSE_MISMATCH", codes(report, "WARN"))

    def test_rust_dual_license_layout_agrees(self):
        complete_repo(self.root)
        os.remove(Path(self.root) / "LICENSE")
        os.remove(Path(self.root) / "package.json")
        write(self.root, "LICENSE-MIT", MIT_TEXT)
        write(self.root, "LICENSE-APACHE", APACHE_TEXT)
        write(self.root, "Cargo.toml", '[package]\nname = "tool"\nversion = "0.1.0"\nlicense = "MIT OR Apache-2.0"\n')
        report = self.analyze()
        self.assertEqual(report["findings"], [], report["findings"])

    def test_declared_license_without_text(self):
        complete_repo(self.root)
        write(self.root, "package.json", json.dumps({"name": "tool", "license": "MIT OR Apache-2.0"}))
        self.assertIn("LICENSE_TEXT_MISSING", codes(self.analyze(), "INFO"))

    def test_unlicensed_in_package_json_is_flagged(self):
        complete_repo(self.root)
        write(self.root, "package.json", json.dumps({"name": "tool", "license": "UNLICENSED", "private": True}))
        report = self.analyze()
        self.assertIn("LICENSE_DECLARED_PROPRIETARY", codes(report, "WARN"))
        self.assertIn("PACKAGE_PRIVATE", codes(report, "INFO"))

    @unittest.skipIf(module.tomllib is None, "tomllib needs Python 3.11+")
    def test_pyproject_string_table_and_classifier(self):
        complete_repo(self.root)
        os.remove(Path(self.root) / "package.json")
        write(self.root, "pyproject.toml", '[project]\nname = "tool"\nlicense = "Apache-2.0"\n')
        self.assertIn("LICENSE_MISMATCH", codes(self.analyze()))
        write(self.root, "pyproject.toml", '[project]\nname = "tool"\nlicense = {text = "MIT"}\n')
        self.assertNotIn("LICENSE_MISMATCH", codes(self.analyze()))
        write(self.root, "pyproject.toml",
              '[project]\nname = "tool"\nclassifiers = ["License :: OSI Approved :: MIT License"]\n')
        report = self.analyze()
        self.assertEqual(report["licenses"]["declared"], {"pyproject.toml": ["MIT"]})
        write(self.root, "pyproject.toml", '[project]\nname = "tool"\n')
        self.assertIn("LICENSE_NOT_DECLARED", codes(self.analyze(), "INFO"))

    def test_tool_only_pyproject_is_not_a_manifest(self):
        complete_repo(self.root)
        write(self.root, "pyproject.toml", "[tool.ruff]\nline-length = 100\n")
        self.assertNotIn("LICENSE_NOT_DECLARED", codes(self.analyze()))

    def test_non_open_source_license_text(self):
        complete_repo(self.root)
        write(self.root, "LICENSE", BUSL_TEXT)
        write(self.root, "package.json", json.dumps({"name": "tool", "license": "BUSL-1.1"}))
        self.assertIn("LICENSE_NOT_OPEN_SOURCE", codes(self.analyze(), "WARN"))

    def test_reuse_layout_counts_as_license(self):
        complete_repo(self.root)
        os.remove(Path(self.root) / "LICENSE")
        write(self.root, "LICENSES/MIT.txt", MIT_TEXT)
        report = self.analyze()
        self.assertNotIn("NO_LICENSE", codes(report))
        self.assertEqual(report["licenses"]["files"], {"LICENSES/MIT.txt": "MIT"})

    def test_gemspec_and_composer(self):
        complete_repo(self.root)
        write(self.root, "tool.gemspec", 'Gem::Specification.new do |s|\n  s.licenses = ["Apache-2.0"]\nend\n')
        write(self.root, "composer.json", json.dumps({"name": "x/tool", "license": ["MIT"]}))
        report = self.analyze()
        mismatches = [f["path"] for f in report["findings"] if f["code"] == "LICENSE_MISMATCH"]
        self.assertEqual(mismatches, ["tool.gemspec"])


class ContentTests(TempRepo):
    def test_sensitive_names_flagged_samples_not(self):
        complete_repo(self.root)
        write(self.root, ".env", "SECRET_TOKEN=supersecretvalue123\n")
        write(self.root, ".env.example", "SECRET_TOKEN=\n")
        write(self.root, "deploy/terraform.tfstate", "{}")
        report = self.analyze()
        flagged = sorted(f["path"] for f in report["findings"] if f["code"] == "SENSITIVE_FILE")
        self.assertEqual(flagged, [".env", "deploy/terraform.tfstate"])
        _, text = run_cli(["--root", self.root, "--no-git"])
        _, js = run_cli(["--root", self.root, "--no-git", "--json"])
        self.assertNotIn("supersecretvalue123", text + js)

    def test_pem_only_flagged_with_private_key(self):
        complete_repo(self.root)
        write(self.root, "certs/public.pem", "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
        write(self.root, "certs/server.pem", "-----BEGIN RSA " + "PRIVATE KEY-----\nMIIE\n-----END RSA " + "PRIVATE KEY-----\n")
        flagged = [f["path"] for f in self.analyze()["findings"] if f["code"] == "SENSITIVE_FILE"]
        self.assertEqual(flagged, ["certs/server.pem"])

    def test_npmrc_token_flagged_without_value(self):
        complete_repo(self.root)
        write(self.root, ".npmrc", "//registry.npmjs.org/:_authToken=npm_abcdefghijklmnop\n")
        report = self.analyze()
        self.assertIn("SENSITIVE_FILE", codes(report, "WARN"))
        self.assertNotIn("npm_abcdefghijklmnop", json.dumps(report))

    def test_data_dump_and_large_file(self):
        complete_repo(self.root)
        write(self.root, "backup/prod.sqlite", b"SQLite format 3\0" + b"x" * 3000, mode="wb")
        report = self.analyze(large_file_mb=0.001)
        self.assertIn("DATA_FILE", codes(report, "INFO"))
        self.assertIn("LARGE_FILE", codes(report, "INFO"))

    def test_internal_hosts_reported_without_credentials(self):
        complete_repo(self.root)
        write(self.root, "config/app.yaml",
              "db: postgres://admin:hunter2pass@10.20.30.40:5432/app\n"
              "wiki: https://wiki.corp/page\n"
              "local: http://localhost:8080\n"
              "doc: https://192.0.2.10/\n"
              "meta: http://metadata.google.internal/computeMetadata\n")
        write(self.root, "docs/network.md", "Example: http://192.168.1.10/ and https://build.internal/\n")
        write(self.root, "tests/test_net.py", "URL = 'https://jenkins.corp/job'\n")
        report = self.analyze()
        hits = sorted((f["path"], f["message"].split("'")[1]) for f in report["findings"] if f["code"] == "INTERNAL_HOST")
        self.assertEqual(hits, [("config/app.yaml:1", "10.20.30.40"), ("config/app.yaml:2", "wiki.corp"),
                                ("docs/network.md:1", "build.internal")])
        self.assertNotIn("hunter2pass", json.dumps(report))

    def test_private_registry_in_lockfile(self):
        complete_repo(self.root)
        write(self.root, "package-lock.json", json.dumps({"packages": {
            "node_modules/a": {"resolved": "https://registry.npmjs.org/a/-/a-1.0.0.tgz"},
            "node_modules/b": {"resolved": "https://artifactory.acme-corp.com/api/npm/b-1.0.0.tgz"},
        }}))
        write(self.root, "requirements.txt", "--extra-index-url https://pypi.acme-corp.com/simple\nrequests==2.32.3\n")
        report = self.analyze()
        hosts = sorted(f["message"].split("'")[1] for f in report["findings"] if f["code"] == "NON_PUBLIC_REGISTRY")
        self.assertEqual(hosts, ["artifactory.acme-corp.com", "pypi.acme-corp.com"])

    def test_dependency_outside_repository(self):
        complete_repo(self.root)
        write(self.root, "package.json", json.dumps({
            "name": "tool", "license": "MIT",
            "dependencies": {"shared": "file:../shared", "inner": "file:./packages/inner"}}))
        write(self.root, "service/go.mod", "module github.com/acme/service\n\nreplace github.com/acme/lib => ../../lib\n")
        report = self.analyze()
        paths = sorted(f["path"] for f in report["findings"] if f["code"] == "DEPENDENCY_OUTSIDE_REPO")
        self.assertEqual(paths, ["package.json", "service/go.mod"])

    def test_submodule_host(self):
        complete_repo(self.root)
        write(self.root, ".gitmodules", '[submodule "vendor/x"]\n\tpath = vendor/x\n\turl = git@git.acme.internal:team/x.git\n')
        msgs = [f["message"] for f in self.analyze()["findings"] if f["code"] == "SUBMODULE"]
        self.assertEqual(len(msgs), 1)
        self.assertIn("git.acme.internal", msgs[0])


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class GitModeTests(TempRepo):
    def git(self, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="Dev", GIT_AUTHOR_EMAIL="dev@acme-corp.com",
                   GIT_COMMITTER_NAME="Dev", GIT_COMMITTER_EMAIL="dev@acme-corp.com",
                   GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, HOME=self.root)
        subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + os.devnull, *args],
                       cwd=self.root, env=env, check=True, capture_output=True)

    def test_history_names_email_domains_and_untracked_files(self):
        complete_repo(self.root)
        self.git("init", "-q")
        write(self.root, "config/.env", "TOKEN=abc\n")
        self.git("add", "-A")
        self.git("add", "-f", "config/.env")
        self.git("commit", "-q", "-m", "first")
        self.git("rm", "-q", "config/.env")
        self.git("commit", "-q", "-m", "remove env")
        write(self.root, ".env", "UNTRACKED=1\n")  # ignored by .gitignore, so never published
        report = module.analyze(self.root, use_git=True)
        self.assertEqual(report["mode"], "git")
        self.assertNotIn("SENSITIVE_FILE", codes(report))
        history = [f["path"] for f in report["findings"] if f["code"] == "SENSITIVE_FILE_IN_HISTORY"]
        self.assertEqual(history, ["config/.env"])
        self.assertEqual(report["git"]["commit_email_domains"], {"acme-corp.com": 4})
        self.assertIn("NO_VERSION_TAGS", codes(report, "INFO"))
        self.git("tag", "v1.0.0")
        self.assertNotIn("NO_VERSION_TAGS", codes(module.analyze(self.root, use_git=True)))

    def test_falls_back_to_walk_outside_git(self):
        complete_repo(self.root)
        report = module.analyze(self.root, use_git=True)
        self.assertEqual(report["mode"], "walk")
        self.assertIn("NOT_A_GIT_CHECKOUT", codes(report, "INFO"))


class CliTests(TempRepo):
    def test_strict_exit_codes(self):
        write(self.root, "main.py", "x = 1\n")
        self.assertEqual(run_cli(["--root", self.root, "--no-git"])[0], 0)
        self.assertEqual(run_cli(["--root", self.root, "--no-git", "--strict"])[0], 1)
        complete_repo(self.root)
        self.assertEqual(run_cli(["--root", self.root, "--no-git", "--strict"])[0], 0)

    def test_missing_root_is_an_error(self):
        self.assertEqual(run_cli(["--root", os.path.join(self.root, "nope")])[0], 2)

    def test_json_is_deterministic_and_text_lists_limits(self):
        complete_repo(self.root)
        write(self.root, ".env", "A=1\n")
        first = run_cli(["--root", self.root, "--no-git", "--json"])[1]
        second = run_cli(["--root", self.root, "--no-git", "--json"])[1]
        self.assertEqual(first, second)
        data = json.loads(first)
        self.assertEqual(data["tool"], "oss_readiness")
        self.assertTrue(data["not_checked"])
        text = run_cli(["--root", self.root, "--no-git"])[1]
        self.assertIn("Not checked by this tool", text)
        self.assertIn("[x] LICENSE: LICENSE (MIT)", text)

    def test_help_and_version(self):
        code, out = run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("never prints file contents", out)
        code, out = run_cli(["--version"])
        self.assertEqual(code, 0)

    def test_does_not_modify_the_tree(self):
        complete_repo(self.root)
        write(self.root, ".env", "A=1\n")
        before = sorted((p, p.stat().st_mtime_ns, p.stat().st_size) for p in Path(self.root).rglob("*") if p.is_file())
        run_cli(["--root", self.root, "--no-git", "--json"])
        after = sorted((p, p.stat().st_mtime_ns, p.stat().st_size) for p in Path(self.root).rglob("*") if p.is_file())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
