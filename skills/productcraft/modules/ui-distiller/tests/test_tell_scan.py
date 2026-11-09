"""Tests for scripts/tell_scan.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "tell_scan.py"
SPEC = importlib.util.spec_from_file_location("tell_scan", SCRIPT)
ts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ts)


def rules(text, name="page.html", **kw):
    return sorted({f["rule"] for f in ts.find(name, text, kw.get("max_ms", 500), kw.get("caps_max", 3))})


class TellScanTests(unittest.TestCase):
    def test_clean_page(self):
        html = "<h1>Ship invoices in a minute</h1><p>Plain copy.</p><button class='btn'>Start</button>"
        self.assertEqual(rules(html), [])

    def test_gradient_css_and_tailwind(self):
        self.assertIn("GRADIENT-BG", rules(".hero { background: linear-gradient(90deg, #7c3aed, #2563eb); }", "a.css"))
        self.assertIn("GRADIENT-BG", rules('<div className="bg-gradient-to-r from-purple-500 to-indigo-500">'))

    def test_headline_periods_need_two(self):
        self.assertNotIn("HEADLINE-PERIOD", rules("<h1>Small studio.</h1>"))
        self.assertIn("HEADLINE-PERIOD", rules("<h1>Small studio.</h1>\n<h2>Big <em>ideas</em>.</h2>"))
        self.assertNotIn("HEADLINE-PERIOD", rules("<h1>Wait...</h1><h2>More...</h2>"))

    def test_headline_emoji(self):
        self.assertIn("HEADLINE-EMOJI", rules("<h2>Welcome back! \U0001F44B</h2>"))

    def test_caps_threshold(self):
        css = "\n".join(".a{text-transform:uppercase}" for _ in range(4))
        self.assertIn("ALL-CAPS", rules(css, "a.css"))
        self.assertNotIn("ALL-CAPS", rules(css, "a.css", caps_max=4))

    def test_code_eyebrow_section_number_and_ai_label(self):
        found = rules("<span>// data products</span>\n<p>01 / Features</p>\n<small>Powered by AI</small>")
        for rule in ("CODE-EYEBROW", "SECTION-NUMBER", "AI-LABEL"):
            self.assertIn(rule, found)

    def test_code_comment_is_not_an_eyebrow(self):
        self.assertNotIn("CODE-EYEBROW", rules("// a real comment\nconst a = 1;", "a.ts"))

    def test_scale_zero_and_bounce(self):
        found = rules(".pop{transform:scale(0); transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1)}", "a.css")
        self.assertIn("SCALE-ZERO", found)
        self.assertIn("BOUNCE-EASING", found)
        self.assertNotIn("BOUNCE-EASING", rules(".a{transition: opacity 200ms cubic-bezier(0.22, 1, 0.36, 1)}", "a.css"))
        self.assertNotIn("SCALE-ZERO", rules(".a{transform:scale(0.95)}", "a.css"))

    def test_slow_motion(self):
        self.assertIn("SLOW-MOTION", rules(".menu{transition: opacity 0.6s ease}", "a.css"))
        self.assertIn("SLOW-MOTION", rules('<div class="transition duration-700">'))
        self.assertNotIn("SLOW-MOTION", rules(".menu{transition: opacity 200ms ease}", "a.css"))

    def test_split_otp_and_autocomplete(self):
        boxes = "".join('<input maxlength="1">' for _ in range(6))
        self.assertIn("SPLIT-OTP", rules(boxes))
        self.assertIn("OTP-AUTOCOMPLETE", rules('<input name="otp" inputmode="numeric">'))
        self.assertNotIn("OTP-AUTOCOMPLETE", rules('<input name="code" autocomplete="one-time-code">'))

    def test_main_exit_codes_json_and_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "x.css").write_text(".a{background:linear-gradient(red,blue)}")
            (root / "ok.html").write_text("<h1>Clear</h1>")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ts.main([tmp]), 0)
            (root / "bad.css").write_text(".a{background:radial-gradient(red,blue)}")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ts.main([tmp, "--json"]), 1)
            data = json.loads(out.getvalue())
            self.assertEqual(data["counts"], {"GRADIENT-BG": 1})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ts.main(["/nonexistent/x"]), 2)


if __name__ == "__main__":
    unittest.main()
