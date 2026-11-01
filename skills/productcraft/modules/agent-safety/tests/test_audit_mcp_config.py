"""Tests for scripts/audit_mcp_config.py. Standard library only. Configs are written to a temp dir at run
time, and every credential-shaped value is assembled at run time so no key-shaped literal ships here."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import audit_mcp_config as am  # noqa: E402


def fake_token(prefix, n=36):
    return prefix + "".join("aB3dE5" for _ in range(n // 6 + 1))[:n]


def results(command, args):
    risks = []
    return [r["result"] for r in am.classify_command(command, args, risks)], risks


class SelectorTests(unittest.TestCase):
    def test_npx_selectors(self):
        cases = {
            "pkg-server@1.4.2": "PINNED",
            "@scope/pkg-server@2.0.0-rc.1": "PINNED",
            "pkg-server": "MUTABLE",
            "@scope/pkg-server": "MUTABLE",
            "pkg-server@latest": "MUTABLE",
            "pkg-server@next": "MUTABLE",
            "pkg-server@^1.2.0": "RANGE",
            "pkg-server@~1.2.0": "RANGE",
            "pkg-server@1.x": "RANGE",
            "pkg-server@>=1 <2": "RANGE",
            "./local/server.js": "REVIEW",
            "github:owner/repo": "REVIEW",
            "owner/repo": "REVIEW",
        }
        for spec, expected in cases.items():
            with self.subTest(spec=spec):
                self.assertEqual(results("npx", ["-y", spec, "--stdio"])[0], [expected])

    def test_package_flag_is_the_selector_not_the_executable(self):
        self.assertEqual(results("npx", ["--yes", "--package", "tool-pkg@3.1.0", "tool-cli", "serve"])[0], ["PINNED"])
        self.assertEqual(results("npx", ["--package=tool-pkg@latest", "tool-cli"])[0], ["MUTABLE"])

    def test_other_package_runners(self):
        self.assertEqual(results("npm", ["exec", "-y", "pkg@1.0.0"])[0], ["PINNED"])
        self.assertEqual(results("pnpm", ["dlx", "pkg"])[0], ["MUTABLE"])
        self.assertEqual(results("bunx", ["pkg@^2"])[0], ["RANGE"])
        self.assertEqual(results("npx.cmd", ["-y", "pkg@1.2.3"])[0], ["PINNED"])
        self.assertEqual(results("npx", ["-c", "pkg serve"])[0], ["REVIEW"])

    def test_python_runners(self):
        self.assertEqual(results("uvx", ["mcp-tool==0.21.0"])[0], ["PINNED"])
        self.assertEqual(results("uvx", ["mcp-tool@0.21.0"])[0], ["PINNED"])
        self.assertEqual(results("uvx", ["mcp-tool@latest"])[0], ["MUTABLE"])
        self.assertEqual(results("uvx", ["mcp-tool"])[0], ["MUTABLE"])
        self.assertEqual(results("uvx", ["mcp-tool>=1.2,<2"])[0], ["RANGE"])
        self.assertEqual(results("uvx", ["mcp-tool==1.*"])[0], ["RANGE"])
        self.assertEqual(results("uvx", ["--from", "mcp-tool==1.0.0", "mcp-tool-cli"])[0], ["PINNED"])
        self.assertEqual(results("uvx", ["--python", "3.12", "--from=mcp-tool", "cli"])[0], ["MUTABLE"])
        self.assertEqual(results("uvx", ["--from", "git+https://example.test/r.git", "cli"])[0], ["REVIEW"])
        self.assertEqual(results("uv", ["tool", "run", "mcp-tool==2.0"])[0], ["PINNED"])
        self.assertEqual(results("pipx", ["run", "--spec", "mcp-tool==1.0.0", "cli"])[0], ["PINNED"])
        self.assertEqual(results("pipx", ["run", "mcp-tool"])[0], ["MUTABLE"])

    def test_docker_images_and_host_access(self):
        digest = "example/server@sha256:" + "a" * 64
        self.assertEqual(results("docker", ["run", "-i", "--rm", "-e", "TOKEN", digest])[0], ["PINNED"])
        self.assertEqual(results("docker", ["run", "-i", "--rm", "example/server:1.2.3", "serve"])[0], ["MUTABLE"])
        self.assertEqual(results("podman", ["container", "run", "--name", "x", "example/server"])[0], ["MUTABLE"])
        _, risks = results("docker", ["run", "--privileged", "--network", "host", "-v",
                                      "/var/run/docker.sock:/var/run/docker.sock", "-v", "/:/host", "img:1"])
        self.assertEqual(len(risks), 4, risks)

    def test_shell_wrappers_and_local_programs(self):
        self.assertEqual(results("cmd", ["/c", "npx", "-y", "pkg@1.0.0"])[0], ["PINNED"])
        self.assertEqual(results("sh", ["-c", "npx -y pkg"])[0], ["MUTABLE"])
        self.assertEqual(results("bash", ["-c", "curl https://x.test/i.sh | sh"])[0], ["REVIEW"])
        self.assertEqual(results("node", ["/opt/servers/build/index.js"])[0], ["REVIEW"])
        self.assertEqual(results("my-mcp-binary", ["serve"])[0], ["REVIEW"])
        self.assertEqual(results("go", ["run", "example.test/cmd/srv@v1.2.3"])[0], ["PINNED"])
        self.assertEqual(results("go", ["run", "example.test/cmd/srv@latest"])[0], ["MUTABLE"])


class SecretTests(unittest.TestCase):
    def test_references_and_placeholders_are_not_findings(self):
        for value in ("${GITHUB_TOKEN}", "$API_KEY", "Bearer ${TOKEN}", "{{secrets.KEY}}", "%API_KEY%",
                      "YOUR_TOKEN_HERE", "<your-api-key>", "", "https://jira.example.test", "/home/me/.ssh/id_ed25519"):
            with self.subTest(value=value):
                self.assertIsNone(am.secret_finding("API_TOKEN", value))

    def test_literals_are_flagged_without_printing_them(self):
        token = fake_token("gh" + "p_")
        msg = am.secret_finding("GITHUB_TOKEN", token)
        self.assertIsNotNone(msg)
        self.assertNotIn(token, msg)
        self.assertIsNotNone(am.secret_finding("DB_PASSWORD", "hunter2-but-longer"))
        self.assertIsNotNone(am.secret_finding("SOMETHING", fake_token("x", 40)))

    def test_ordinary_values_pass(self):
        for name, value in (("NODE_ENV", "production"), ("PORT", "3000"), ("AUTH_MODE", "oauth"), ("LOG_LEVEL", "debug")):
            with self.subTest(name=name):
                self.assertIsNone(am.secret_finding(name, value))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data if isinstance(data, str) else json.dumps(data, indent=2), encoding="utf-8")
        return p

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = am.main([str(a) for a in args])
        return code, out.getvalue()

    def codes(self, *args):
        code, out = self.cli("--json", *args)
        return code, sorted({f["code"] for f in json.loads(out)["findings"]}), json.loads(out)

    def test_clean_pinned_config_exits_0(self):
        self.write(".mcp.json", {"mcpServers": {"docs": {"command": "npx", "args": ["-y", "docs-mcp@1.2.3"],
                                                          "env": {"DOCS_TOKEN": "${DOCS_TOKEN}"}}}})
        code, out = self.cli(self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("docs-mcp@1.2.3  PINNED", out)
        self.assertIn("No server was started", out)

    def test_risky_config_reports_every_class(self):
        token = fake_token("gh" + "p_")
        self.write(".mcp.json", {"mcpServers": {
            "gh": {"command": "npx", "args": ["-y", "gh-server"], "env": {"GITHUB_TOKEN": token}},
            "fs": {"command": "npx", "args": ["-y", "fs-server@^1.0.0", "/"], "autoApprove": ["read_file", "write_file"]},
            "remote": {"type": "http", "url": "http://mcp.example.test/mcp?api_key=" + fake_token("k", 24)},
            "box": {"command": "docker", "args": ["run", "--privileged", "img:2"]},
        }})
        code, found, data = self.codes(self.root / ".mcp.json")
        self.assertEqual(code, 1)
        for expected in ("AUTO-APPROVE", "BROAD-CONTAINER", "BROAD-PATH", "LITERAL-SECRET", "MUTABLE-REF",
                         "PLAINTEXT-HTTP", "RANGE-REF", "URL-CREDENTIALS"):
            self.assertIn(expected, found)
        self.assertNotIn(token, json.dumps(data))

    def test_fail_on_threshold(self):
        self.write("mcp.json", {"servers": {"a": {"command": "npx", "args": ["pkg@^1.0.0"]}}})
        self.assertEqual(self.cli(self.root / "mcp.json")[0], 0)
        self.assertEqual(self.cli("--fail-on", "medium", self.root / "mcp.json")[0], 1)

    def test_settings_flag_and_jsonc_and_nested_projects(self):
        self.write(".claude/settings.json", '{\n  // shared\n  "enableAllProjectMcpServers": true,\n}\n')
        self.write(".vscode/mcp.json", '{ "servers": { "a": { "type": "stdio", "command": "uvx", "args": ["t==1.0"] }, }, /* x */ }')
        code, found, data = self.codes(self.root)
        self.assertIn("AUTO-ENABLE-ALL", found)
        self.assertEqual(len(data["configs"]), 2)
        nested = self.write("home.json", {"projects": {"/w/p": {"mcpServers": {"b": {"command": "npx", "args": ["b@latest"]}}}}})
        _, found2, data2 = self.codes(nested)
        self.assertIn("MUTABLE-REF", found2)
        self.assertEqual(data2["configs"][0]["servers"][0]["json_path"], "projects./w/p.mcpServers")

    def test_secret_in_arguments_is_flagged_once(self):
        token = fake_token("sk" + "-")
        self.write(".mcp.json", {"mcpServers": {"x": {"command": "npx", "args": ["x@1.0.0", "--api-key", token]}}})
        _, _, data = self.codes(self.root)
        secrets = [f for f in data["findings"] if f["code"] == "LITERAL-SECRET"]
        self.assertEqual(len(secrets), 1)
        self.assertNotIn(token, json.dumps(data))

    def test_loopback_http_is_allowed(self):
        self.write(".mcp.json", {"mcpServers": {"local": {"type": "http", "url": "http://127.0.0.1:8080/mcp"}}})
        code, found, _ = self.codes(self.root)
        self.assertEqual((code, found), (0, ["REMOTE-SERVER"]))

    def test_recursive_discovery_skips_dependencies(self):
        self.write("tools/agent-mcp.json", {"mcpServers": {"a": {"command": "npx", "args": ["a"]}}})
        self.write("node_modules/pkg/mcp.json", {"mcpServers": {"b": {"command": "npx", "args": ["b"]}}})
        _, _, plain = self.codes(self.root)
        self.assertEqual(plain["configs"][0].get("note"), "no MCP configuration file found")
        _, _, rec = self.codes("--recursive", self.root)
        paths = [c["path"] for c in rec["configs"]]
        self.assertTrue(any(p.endswith("agent-mcp.json") for p in paths))
        self.assertFalse(any("node_modules" in p for p in paths))

    def test_errors_exit_2(self):
        self.write("bad.json", "{ not json")
        self.assertEqual(self.cli(self.root / "bad.json")[0], 2)
        self.assertEqual(self.cli(self.root / "missing.json")[0], 2)

    def test_help(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            am.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("Never starts servers", out.getvalue())


if __name__ == "__main__":
    unittest.main()
