"""Tests for scripts/motion_contract_check.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "motion_contract_check.py"
SPEC = importlib.util.spec_from_file_location("motion_contract_check", SCRIPT)
mcc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mcc)

GOOD = """<!doctype html><html><head><link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet"></head>
<body><script>
const tl = gsap.timeline({ paused: true });
tl.to(".a", { x: 100, duration: 1 });
window.renderFrame = async (n) => { await document.fonts.ready; tl.seek(n / 30); };
</script></body></html>
"""


class LintTests(unittest.TestCase):
    def write(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return root

    def rules(self, files):
        _, findings = mcc.check([str(self.write(files))])
        return sorted({f["rule"] for f in findings}), findings

    def run_main(self, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = mcc.main(args)
        return code, out.getvalue()

    def test_clean_page(self):
        rules, _ = self.rules({"index.html": GOOD})
        self.assertEqual(rules, [])

    def test_wall_clock_and_random_are_errors(self):
        js = GOOD.replace("tl.seek(n / 30);", "tl.seek(Date.now() / 1000 + Math.random());")
        _, findings = self.rules({"index.html": js})
        sev = {f["rule"]: f["severity"] for f in findings}
        self.assertEqual(sev.get("CLOCK"), "error")
        self.assertEqual(sev.get("RANDOM"), "error")

    def test_new_date_with_argument_is_allowed(self):
        rules, _ = self.rules({"a.js": "const d = new Date(2026, 0, 1);\nwindow.renderFrame = (n) => n;\n"})
        self.assertNotIn("CLOCK", rules)

    def test_performance_now_and_crypto(self):
        rules, _ = self.rules({"a.ts": "const a = performance.now();\nconst id = crypto.randomUUID();\nuseCurrentFrame();\n"})
        self.assertIn("CLOCK", rules)
        self.assertIn("RANDOM", rules)

    def test_timers_delta_clock_and_autoplay(self):
        html = GOOD.replace("<body>", '<body><video src="a.mp4" autoplay muted></video>').replace(
            "</script>", "setInterval(step, 16);\nconst c = new THREE.Clock(); c.getDelta();\n</script>")
        rules, _ = self.rules({"index.html": html})
        for rule in ("TIMER", "DELTA-CLOCK", "AUTOPLAY"):
            self.assertIn(rule, rules)

    def test_motion_ok_and_comments_are_skipped(self):
        js = "// Date.now() only in a comment\nconst p = performance.now(); // motion-ok profiling\nuseCurrentFrame();\n"
        rules, _ = self.rules({"a.js": js})
        self.assertEqual(rules, [])

    def test_css_transition_flagged_but_none_allowed(self):
        rules, _ = self.rules({"a.css": ".a { transition: opacity 0.3s; }\n", "b.js": "useCurrentFrame();\n"})
        self.assertIn("CSS-TRANSITION", rules)
        rules, _ = self.rules({"a.css": ".a { transition: none; }\n", "b.js": "useCurrentFrame();\n"})
        self.assertNotIn("CSS-TRANSITION", rules)

    def test_gsap_without_seek(self):
        rules, _ = self.rules({"a.js": 'gsap.to(".a", { x: 1 });\nwindow.renderFrame = (n) => n;\n'})
        self.assertIn("GSAP-UNSEEKED", rules)

    def test_gsap_seek_in_another_file_counts(self):
        rules, _ = self.rules({"a.js": 'gsap.to(".a", { x: 1 });\n',
                               "b.js": "gsap.globalTimeline.pause();\nwindow.renderFrame = (n) => n;\n"})
        self.assertNotIn("GSAP-UNSEEKED", rules)

    def test_font_wait_and_frame_hook(self):
        html = '<style>@font-face { font-family: X; src: url(x.woff2); }</style><script>const a = 1;</script>'
        rules, _ = self.rules({"index.html": html})
        self.assertIn("FONT-WAIT", rules)
        self.assertIn("NO-FRAME-HOOK", rules)

    def test_query_parameter_counts_as_frame_hook(self):
        js = 'const t = Number(new URL(location.href).searchParams.get("t"));\n'
        rules, _ = self.rules({"a.js": js})
        self.assertNotIn("NO-FRAME-HOOK", rules)

    def test_skips_node_modules(self):
        rules, _ = self.rules({"node_modules/lib/x.js": "Math.random();\n", "a.js": "useCurrentFrame();\n"})
        self.assertEqual(rules, [])

    def test_exit_codes_and_json(self):
        root = self.write({"a.js": "Math.random();\nuseCurrentFrame();\n"})
        code, out = self.run_main([str(root), "--json"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["errors"], 1)
        self.assertEqual(data["findings"][0]["rule"], "RANDOM")
        clean = self.write({"a.js": "useCurrentFrame();\n"})
        self.assertEqual(self.run_main([str(clean)])[0], 0)
        self.assertEqual(self.run_main(["/nonexistent/path"])[0], 2)

    def test_errors_only(self):
        root = self.write({"a.js": "setTimeout(f, 1);\n"})
        code, out = self.run_main([str(root), "--errors-only"])
        self.assertEqual(code, 0)
        self.assertIn("0 error(s), 0 warning(s)", out)

    def test_output_is_deterministic(self):
        root = self.write({"b.js": "Math.random();\n", "a.js": "Date.now();\n"})
        first = self.run_main([str(root)])[1]
        self.assertEqual(first, self.run_main([str(root)])[1])
        self.assertLess(first.index("a.js"), first.index("b.js"))


if __name__ == "__main__":
    unittest.main()
