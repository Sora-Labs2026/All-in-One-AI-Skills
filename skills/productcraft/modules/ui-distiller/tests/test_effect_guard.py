"""Tests for scripts/effect_guard.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "effect_guard.py"
SPEC = importlib.util.spec_from_file_location("effect_guard", SCRIPT)
eg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eg)


def rules(text, name="page.html"):
    return sorted({f["rule"] for f in eg.find(name, text)})


def scan_rules(files):
    with tempfile.TemporaryDirectory() as d:
        for name, text in files.items():
            (Path(d) / name).write_text(text, encoding="utf-8")
        _, findings = eg.scan([d])
    return sorted({f["rule"] for f in findings})


class FileRuleTests(unittest.TestCase):
    def test_clean_reveal_is_quiet(self):
        css = ".motion-ok [data-enter] { opacity: 0; translate: 0 18px; }"
        self.assertEqual(rules(css, "a.css"), [])

    def test_ungated_reveal_is_flagged(self):
        self.assertIn("HIDDEN-BY-DEFAULT", rules(".reveal { opacity: 0; transform: translateY(20px) }", "a.css"))
        self.assertIn("HIDDEN-BY-DEFAULT", rules("<style>[data-animate]{visibility:hidden}</style>"))

    def test_reveal_inside_no_preference_media_is_gated(self):
        css = "@media (prefers-reduced-motion: no-preference) { .fade-in { opacity: 0 } }"
        self.assertNotIn("HIDDEN-BY-DEFAULT", rules(css, "a.css"))

    def test_partial_opacity_and_unrelated_selectors_pass(self):
        self.assertEqual(rules(".reveal { opacity: 0.5 } .tooltip { opacity: 0 }", "a.css"), [])

    def test_raf_without_stop(self):
        loop = "function tick(){ draw(); requestAnimationFrame(tick); } tick();"
        self.assertIn("RAF-NO-STOP", rules(loop, "fx.js"))
        self.assertNotIn("RAF-NO-STOP", rules(loop + " document.addEventListener('visibilitychange', f)", "fx.js"))

    def test_observer_leak(self):
        self.assertIn("OBSERVER-LEAK", rules("const io = new IntersectionObserver(cb); io.observe(el);", "a.js"))
        self.assertNotIn("OBSERVER-LEAK", rules("const io = new ResizeObserver(cb); return () => io.disconnect();", "a.js"))

    def test_scrolltrigger_cleanup(self):
        self.assertIn("SCROLL-NO-CLEANUP", rules("gsap.to(el, { scrollTrigger: { trigger: el } }); ScrollTrigger.refresh();", "a.js"))
        self.assertNotIn("SCROLL-NO-CLEANUP", rules("const ctx = gsap.context(() => {}); ScrollTrigger.refresh(); ctx.revert();", "a.js"))

    def test_dpr_cap(self):
        self.assertIn("DPR-UNCAPPED", rules("renderer.setPixelRatio(window.devicePixelRatio);", "a.js"))
        self.assertNotIn("DPR-UNCAPPED", rules("renderer.setPixelRatio(Math.min(devicePixelRatio, 2));", "a.js"))
        self.assertNotIn("DPR-UNCAPPED", rules("const dpr = clamp(devicePixelRatio, 1, maxDpr);", "a.js"))

    def test_pointer_gate(self):
        code = "el.addEventListener('pointermove', move);"
        self.assertIn("POINTER-UNGATED", rules(code, "a.js"))
        self.assertNotIn("POINTER-UNGATED", rules("if (matchMedia('(pointer: fine)').matches) " + code, "a.js"))

    def test_canvas_label(self):
        self.assertIn("CANVAS-UNLABELLED", rules("<canvas class='bg'></canvas>"))
        self.assertNotIn("CANVAS-UNLABELLED", rules("<canvas aria-hidden=\"true\"></canvas>"))


class SetRuleTests(unittest.TestCase):
    def test_reduced_motion_missing_across_set(self):
        self.assertIn("NO-REDUCED-MOTION", scan_rules({"a.css": ".x { transition: opacity 200ms }"}))
        self.assertNotIn("NO-REDUCED-MOTION", scan_rules({
            "a.css": ".x { transition: opacity 200ms }",
            "b.css": "@media (prefers-reduced-motion: reduce) { .x { transition: none } }"}))

    def test_loop_needs_pause(self):
        css = "@media (prefers-reduced-motion: reduce){.t{animation:none}} .t { animation: slide 30s linear infinite }"
        self.assertIn("LOOP-NO-PAUSE", scan_rules({"m.css": css}))
        self.assertNotIn("LOOP-NO-PAUSE", scan_rules({"m.css": css + " .t:hover { animation-play-state: paused }"}))


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = eg.main(argv)
        return code, buf.getvalue()

    def test_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            clean = Path(d) / "ok.css"
            clean.write_text("@media (prefers-reduced-motion: reduce){} .a{color:red}", encoding="utf-8")
            self.assertEqual(self.run_main([str(clean)])[0], 0)
            bad = Path(d) / "bad.js"
            bad.write_text("renderer.setPixelRatio(devicePixelRatio)", encoding="utf-8")
            code, out = self.run_main([str(bad), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["counts"].get("DPR-UNCAPPED"), 1)
            self.assertEqual(self.run_main([str(bad), "--ignore", "DPR-UNCAPPED,NO-REDUCED-MOTION"])[0], 0)

    def test_usage_errors(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_main([d])[0], 2)
            (Path(d) / "a.css").write_text(".a{}", encoding="utf-8")
            self.assertEqual(self.run_main([d, "--ignore", "NOT-A-RULE"])[0], 2)

    def test_skips_dependency_folders(self):
        with tempfile.TemporaryDirectory() as d:
            nm = Path(d) / "node_modules"
            nm.mkdir()
            (nm / "lib.js").write_text("setPixelRatio(devicePixelRatio)", encoding="utf-8")
            files, _ = eg.scan([d])
            self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main()
