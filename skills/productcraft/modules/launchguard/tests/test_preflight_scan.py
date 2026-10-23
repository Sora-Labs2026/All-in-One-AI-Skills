"""Offline tests with synthetic strings only; no network, secrets or live target."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preflight_scan.py"
spec = importlib.util.spec_from_file_location("preflight_scan", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class PreflightScanTests(unittest.TestCase):
    def test_secret_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.ts"
            synthetic = "sk_live_" + ("a" * 23)
            p.write_text(f'const secret = "{synthetic}";\n')
            result = module.scan(Path(d))
            self.assertTrue(any(x["rule_id"] == "SECRET_LIKE_LITERAL" for x in result["findings"]))
            self.assertNotIn(synthetic, json.dumps(result))
            self.assertTrue(all("matched_text" not in f for f in result["findings"]))

    def test_public_privileged_env_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.ts").write_text("const key = process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY;\n")
            result = module.scan(Path(d))
            self.assertTrue(any(x["rule_id"] == "PUBLIC_SECRET_NAMING" for x in result["findings"]))

    def test_public_publishable_key_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.ts").write_text("const key = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;\n")
            result = module.scan(Path(d))
            self.assertEqual(result["stats"]["finding_count"], 0)

    def test_patterns_and_skip_generated(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "app.py").write_text("app.debug = True\nrequests.get(url, verify=False)\n")
            generated = Path(d) / "node_modules"
            generated.mkdir()
            (generated / "secret.js").write_text('const x = "sk_live_' + ('x' * 25) + '";')
            result = module.scan(Path(d))
            rules = {x["rule_id"] for x in result["findings"]}
            self.assertIn("DEBUG_ENABLED", rules)
            self.assertIn("TLS_VERIFICATION_DISABLED", rules)
            self.assertNotIn("SECRET_LIKE_LITERAL", rules)


    def test_tracked_env_detected_without_reading_value(self):
        if not shutil.which("git"):
            self.skipTest("git unavailable")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / ".env.production").write_text("JUST_FAKE_PLACEHOLDER=unused\n")
            subprocess.run(["git", "-C", str(root), "add", ".env.production"], check=True, capture_output=True)
            result = module.scan(root)
            self.assertTrue(any(x["rule_id"] == "TRACKED_ENV_FILE" for x in result["findings"]))
            self.assertNotIn("JUST_FAKE_PLACEHOLDER=unused", json.dumps(result))
            self.assertTrue(any("NOT scanned" in w for w in result["warnings"]))

    def test_cors_candidate_not_certainty(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cors.ts").write_text("const corsOptions = { origin: '*' };\n")
            result = module.scan(Path(d))
            hits = [x for x in result["findings"] if x["rule_id"] == "PERMISSIVE_CORS"]
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["classification"], "CANDIDATE_NOT_CONFIRMED")

    def test_no_source_lines_in_report(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "app.ts").write_text("element.innerHTML = input;\n")
            result = module.scan(Path(d))
            item = result["findings"][0]
            self.assertEqual(item["file"], "app.ts")
            self.assertEqual(item["line"], 1)
            self.assertNotIn("element.innerHTML = input;", json.dumps(result))
            self.assertEqual(item["classification"], "CANDIDATE_NOT_CONFIRMED")


if __name__ == "__main__":
    unittest.main()
