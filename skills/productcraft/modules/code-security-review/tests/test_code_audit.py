"""Offline tests for code_audit.py. Synthetic data only: no network, no real secrets, no live targets."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "code_audit.py"
spec = importlib.util.spec_from_file_location("code_audit", SCRIPT)
ca = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ca
spec.loader.exec_module(ca)

# Built at runtime so no credential-shaped literal sits in this file.
FAKE_AWS = "AKIA" + "Q" * 16
FAKE_STRIPE = "sk_" + "live_" + "z" * 24
SHA = "0" * 40


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def valid_findings() -> dict:
    return {
        "audit": {"repository": "demo", "revision": "abc1234", "mode": "full", "scope": ["src/"]},
        "coverage": [
            {"id": "C-01", "surface": "GET /api/orders/:id", "boundary": "user A -> user B orders",
             "class": "access control", "status": "FAIL", "findings": ["CSR-001"]},
            {"id": "C-02", "surface": "POST /api/search", "class": "SQL injection", "status": "PASS",
             "evidence": "src/search.ts:10-40 uses bound parameters on every branch"},
            {"id": "C-03", "surface": "file import", "class": "XXE", "status": "NOT_APPLICABLE",
             "reason": "no XML parsing in the repository"},
        ],
        "findings": [{
            "id": "CSR-001", "title": "Order read without owner check", "class": "broken object-level authorization",
            "cwe": "CWE-639", "file": "src/api/orders.ts", "line": 42, "actor": "any signed-in user",
            "preconditions": [], "impact": "reads other customers' orders and addresses",
            "confidence": "CONFIRMED", "severity": "HIGH", "status": "OPEN", "evidence_type": "TESTED_LOCAL",
            "evidence_summary": "two-user test returns user B's order to user A",
            "fix": "scope the query by the session user id",
        }],
    }


class MapTests(unittest.TestCase):
    def test_ranks_entry_and_sink_file_first_and_skips_tests(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root, "src/routes/orders.js",
                  "router.get('/orders/:id', async (req, res) => {\n"
                  "  const rows = await db.raw(`select * from orders where id = ${req.params.id}`);\n"
                  "  res.sendFile(req.query.name);\n});\n")
            write(root, "src/util/format.js", "export const pad = (s) => s.padStart(2, '0');\n")
            write(root, "tests/orders.test.js", "router.get('/x', () => db.raw('1'));\n")
            result = ca.map_repo(root)
            paths = [r["path"] for r in result["ranked_files"]]
            self.assertEqual(paths[0], "src/routes/orders.js")
            self.assertNotIn("src/util/format.js", paths)
            self.assertNotIn("tests/orders.test.js", paths)
            self.assertEqual(result["stats"]["test_or_example_files_not_ranked"], 1)
            self.assertIn("sql", result["ranked_files"][0]["sink_lines"])
            self.assertIn("file_path", result["ranked_files"][0]["sink_lines"])
            self.assertNotIn("select * from orders", json.dumps(result))

    def test_manifests_lockfiles_and_notes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root, "web/package.json", json.dumps({
                "dependencies": {"left": "github:someone/left", "ok": "^1.0.0", "any": "*"},
                "scripts": {"postinstall": "node setup.js"}}))
            write(root, "api/package.json", json.dumps({"dependencies": {"ok": "1.0.0"}}))
            write(root, "api/package-lock.json", "{}")
            write(root, "requirements.txt", "--extra-index-url https://pkgs.example.invalid/simple\nflask\nrequests==2.32.3\n")
            result = ca.map_repo(root)
            by_path = {m["path"]: m for m in result["manifests"]}
            self.assertIsNone(by_path["web/package.json"]["lockfile"])
            self.assertEqual(by_path["api/package.json"]["lockfile"], "api/package-lock.json")
            web_notes = " ".join(by_path["web/package.json"]["notes"])
            self.assertIn("no lockfile", web_notes)
            self.assertIn("left resolves from a URL", web_notes)
            self.assertIn("any has no version constraint", web_notes)
            self.assertIn("postinstall", web_notes)
            req_notes = " ".join(by_path["requirements.txt"]["notes"])
            self.assertIn("--extra-index-url", req_notes)
            self.assertIn("1 of 2 requirements are not pinned", req_notes)
            self.assertEqual(result["stats"]["manifests_without_lockfile"], 1)

    def test_docker_base_images(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root, "Dockerfile",
                  "FROM node:latest AS build\nFROM build\nFROM python:3.12-slim\n"
                  f"FROM alpine@sha256:{'a' * 64}\nFROM scratch\n")
            result = ca.map_repo(root)
            lines = [b["line"] for b in result["build_inputs"]]
            self.assertEqual(lines, [1, 3])

    def test_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root, "b.py", "@app.route('/b')\ndef b():\n    return eval(request.args['x'])\n")
            write(root, "a.py", "@app.route('/a')\ndef a():\n    return eval(request.args['x'])\n")
            first = json.dumps(ca.map_repo(root), sort_keys=False)
            second = json.dumps(ca.map_repo(root), sort_keys=False)
            self.assertEqual(first, second)
            ranked = ca.map_repo(root)["ranked_files"]
            self.assertEqual([r["path"] for r in ranked], ["a.py", "b.py"])


class WorkflowTests(unittest.TestCase):
    def run_checks(self, text: str) -> list:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write(root, ".github/workflows/ci.yml", text)
            return ca.check_workflows(root)["candidates"]

    def rules(self, candidates) -> set:
        return {c["rule"] for c in candidates}

    def test_privileged_trigger_with_head_checkout(self):
        found = self.run_checks(
            "on:\n  pull_request_target:\n    types: [opened]\npermissions:\n  contents: read\njobs:\n  t:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            f"      - uses: actions/checkout@{SHA}\n        with:\n"
            "          ref: ${{ github.event.pull_request.head.sha }}\n      - run: npm ci && npm test\n")
        rules = self.rules(found)
        self.assertIn("PRIVILEGED_TRIGGER", rules)
        self.assertIn("UNTRUSTED_CHECKOUT_IN_PRIVILEGED_WORKFLOW", rules)
        high = [c for c in found if c["rule"] == "UNTRUSTED_CHECKOUT_IN_PRIVILEGED_WORKFLOW"][0]
        self.assertEqual((high["severity"], high["line"]), ("HIGH", 12))
        self.assertNotIn("UNPINNED_ACTION", rules)
        self.assertNotIn("NO_PERMISSIONS_BLOCK", rules)

    def test_script_injection_flagged_but_env_indirection_is_not(self):
        found = self.run_checks(
            "on: [issues]\npermissions: read-all\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: |\n          echo \"${{ github.event.issue.title }}\"\n"
            "      - env:\n          TITLE: ${{ github.event.issue.title }}\n        run: echo \"$TITLE\"\n"
            "      - run: echo ${{ github.event.pull_request.base.ref }} ${{ github.sha }}\n")
        injected = [c for c in found if c["rule"] == "UNTRUSTED_INPUT_IN_SCRIPT"]
        self.assertEqual([c["line"] for c in injected], [8])

    def test_unpinned_actions_permissions_and_remote_scripts(self):
        found = self.run_checks(
            "on:\n  push:\n  pull_request:\njobs:\n  t:\n    runs-on: [self-hosted, linux]\n"
            "    permissions: write-all\n    steps:\n"
            "      - uses: actions/checkout@v4\n      - uses: someone/deploy-action@main\n"
            "      - uses: ./.github/actions/local\n      - run: curl -fsSL https://get.example.invalid | sh\n")
        by_rule = {}
        for c in found:
            by_rule.setdefault(c["rule"], []).append(c)
        self.assertEqual(sorted(c["severity"] for c in by_rule["UNPINNED_ACTION"]), ["LOW", "MEDIUM"])
        self.assertIn("WRITE_ALL_PERMISSIONS", by_rule)
        self.assertIn("SELF_HOSTED_RUNNER_ON_PULL_REQUESTS", by_rule)
        self.assertIn("REMOTE_SCRIPT_PIPED_TO_SHELL", by_rule)
        self.assertNotIn("PRIVILEGED_TRIGGER", by_rule)

    def test_event_expression_is_not_mistaken_for_trigger(self):
        found = self.run_checks(
            "on: push\npermissions:\n  contents: read\njobs:\n  t:\n    runs-on: self-hosted\n    steps:\n"
            "      - run: echo ${{ github.event.pull_request.number }}\n")
        self.assertEqual(self.rules(found), set())

    def test_no_permissions_block_and_no_workflows(self):
        found = self.run_checks("on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n")
        self.assertEqual(self.rules(found), {"NO_PERMISSIONS_BLOCK"})
        with tempfile.TemporaryDirectory() as d:
            result = ca.check_workflows(Path(d))
            self.assertEqual(result["stats"]["workflow_files"], 0)


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class HistoryTests(unittest.TestCase):
    def git(self, root: Path, *args: str) -> None:
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(root.parent), "GIT_CONFIG_GLOBAL": os.devnull}
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, env=env)

    def test_removed_secret_still_found_in_history_without_value(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            root.mkdir()
            self.git(root, "init", "-q")
            write(root, "config.js", f"const aws = '{FAKE_AWS}';\nconst stripe = '{FAKE_STRIPE}';\n")
            write(root, ".env", "TOKEN=abc\n")
            write(root, ".env.example", "TOKEN=\n")
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "add config")
            write(root, "config.js", "const aws = process.env.AWS_KEY;\n")
            self.git(root, "rm", "-q", "--cached", ".env")
            (root / ".env").unlink()
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "move to env")
            result = ca.scan_history(root)
            self.assertEqual(result["status"], "scanned")
            self.assertEqual(result["stats"]["commits_scanned"], 2)
            rules = {c["rule"] for c in result["candidates"]}
            self.assertEqual(rules, {"AWS_ACCESS_KEY_ID", "STRIPE_LIVE_SECRET"})
            for c in result["candidates"]:
                self.assertTrue(c["tracked_at_head"])
                self.assertFalse(c["same_rule_matches_current_file"])
            self.assertEqual(result["sensitive_files"], [{"path": ".env", "tracked_at_head": False}])
            dumped = json.dumps(result)
            self.assertNotIn(FAKE_AWS, dumped)
            self.assertNotIn(FAKE_STRIPE, dumped)

    def test_not_a_repository(self):
        with tempfile.TemporaryDirectory() as d:
            result = ca.scan_history(Path(d))
            self.assertIn(result["status"], {"not_a_git_repository", "git_unavailable"})
            self.assertEqual(result["candidates"], [])


class SecretRuleTests(unittest.TestCase):
    def test_placeholders_in_urls_are_ignored(self):
        self.assertEqual(ca.secret_hits("postgres://user:password@localhost/db"), [])
        self.assertEqual(ca.secret_hits("postgres://app:${DB_PASS}@db/app"), [])
        self.assertEqual(ca.secret_hits("redis://default:" + "Xy7" + "qq92Lm@cache:6379"),
                         [("PASSWORD_IN_URL", "HIGH")])


class FindingsTests(unittest.TestCase):
    def errors(self, data) -> list:
        return ca.validate_findings(data)["errors"]

    def test_valid_file_reports_fail_for_open_confirmed(self):
        report = ca.validate_findings(valid_findings())
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["result"], "FAIL (highest open confirmed severity: HIGH)")

    def test_evidence_rules(self):
        cases = [
            (lambda f: f.update(confidence="POSSIBLE", next_check="run two-user test"), "carry no severity"),
            (lambda f: f.update(evidence_type="INFERRED"), "CONFIRMED needs an executed test"),
            (lambda f: f.update(confidence="LIKELY"), "unverified_condition"),
            (lambda f: f.update(status="FALSE_POSITIVE"), "rejection_reason"),
            (lambda f: f.update(status="FIXED"), "regression_test"),
            (lambda f: f.update(status="ACCEPTED"), "accepted_by"),
            (lambda f: f.pop("actor"), "needs 'actor'"),
            (lambda f: f.pop("fix"), "proposed 'fix'"),
            (lambda f: f.update(file="/srv/app/orders.ts"), "repository-relative"),
            (lambda f: f.update(file="../other/x.ts"), "repository-relative"),
            (lambda f: f.update(evidence_summary="key " + FAKE_AWS), "secret-shaped"),
        ]
        for mutate, expected in cases:
            data = valid_findings()
            mutate(data["findings"][0])
            errs = self.errors(data)
            self.assertTrue(any(expected in e for e in errs), f"{expected!r} not in {errs}")
            self.assertNotIn(FAKE_AWS, json.dumps(errs))

    def test_coverage_rules(self):
        data = valid_findings()
        data["coverage"][1].pop("evidence")
        data["coverage"][2].pop("reason")
        data["coverage"].append({"id": "C-04", "surface": "x", "class": "y", "status": "PASS",
                                 "evidence": "read", "findings": ["CSR-001", "CSR-404"]})
        data["findings"].append(copy.deepcopy(data["findings"][0]))
        errs = self.errors(data)
        for expected in ("PASS needs 'evidence'", "NOT_APPLICABLE needs 'reason'", "unknown finding CSR-404",
                         "cannot be PASS while confirmed finding CSR-001 is OPEN", "duplicate id"):
            self.assertTrue(any(expected in e for e in errs), f"{expected!r} not in {errs}")

    def test_results(self):
        data = valid_findings()
        f = data["findings"][0]
        f.update(status="FIXED", regression_test="tests/orders.test.ts::cross-user read is 404",
                 verification="npm test: 1 new test failed before the fix and passes after")
        data["coverage"][0].update(status="PASS", evidence="fixed by CSR-001; regression test passes")
        self.assertEqual(ca.validate_findings(data)["result"], "PASS (scoped)")
        data["coverage"].append({"id": "C-05", "surface": "webhook", "class": "signature", "status": "NOT_VERIFIED",
                                 "reason": "provider secret configuration not visible in the repository"})
        self.assertEqual(ca.validate_findings(data)["result"], "NEEDS_REVIEW")
        empty = {"audit": {"repository": "demo"}, "coverage": [], "findings": []}
        self.assertEqual(ca.validate_findings(empty)["result"], "INSUFFICIENT_EVIDENCE")


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60)

    def test_help_for_every_subcommand(self):
        for sub in ([], ["map"], ["workflows"], ["history"], ["findings"]):
            proc = self.run_cli(*sub, "--help")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("usage:", proc.stdout)

    def test_findings_exit_codes_and_json_out(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "good.json"
            good.write_text(json.dumps(valid_findings()))
            bad_data = valid_findings()
            bad_data["findings"][0]["confidence"] = "SURE"
            bad = Path(d) / "bad.json"
            bad.write_text(json.dumps(bad_data))
            self.assertEqual(self.run_cli("findings", "--file", str(good)).returncode, 0)
            self.assertEqual(self.run_cli("findings", "--file", str(bad)).returncode, 1)
            self.assertEqual(self.run_cli("findings", "--file", str(Path(d) / "missing.json")).returncode, 2)
            out = Path(d) / "out" / "map.json"
            proc = self.run_cli("map", "--root", d, "--json-out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(out.read_text())["tool"], "productcraft-code-audit-map")
            self.assertEqual(oct(out.stat().st_mode & 0o777), "0o600")

    def test_workflows_fail_on_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            write(Path(d), ".github/workflows/x.yml",
                  "on: issue_comment\npermissions: {}\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
                  "      - run: echo \"${{ github.event.comment.body }}\"\n")
            self.assertEqual(self.run_cli("workflows", "--root", d).returncode, 0)
            self.assertEqual(self.run_cli("workflows", "--root", d, "--fail-on", "high").returncode, 1)

    def test_bad_root(self):
        proc = self.run_cli("map", "--root", "/nonexistent/path/for/test")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
