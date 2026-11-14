"""Tests for scripts/landing_check.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "landing_check.py"
SPEC = importlib.util.spec_from_file_location("landing_check", SCRIPT)
lc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lc)

CLEAN = """<!doctype html>
<html lang="en"><head>
<title>Ledger sync for small shops</title>
<meta name="description" content="Match card payouts to orders every night.">
<meta property="og:title" content="Ledger sync"><meta property="og:image" content="/share.jpg">
<style>.r{transition: opacity 600ms} @media (prefers-reduced-motion: reduce){.r{transition:none}}</style>
</head><body>
<a href="#main">Skip to content</a>
<main id="main">
<h1>Close the books in ten minutes</h1>
<img src="hero.jpg" alt="Payout matching screen" width="1200" height="800">
<a href="/trial">Start a 14-day trial</a>
<button type="button">Book a demo</button>
</main></body></html>"""


def rules(html, **kw):
    return sorted({f["rule"] for f in lc.check("page.html", html, kw.get("extra", ""), kw.get("max_words", 10))})


class LandingCheckTests(unittest.TestCase):
    def test_clean_page(self):
        self.assertEqual(rules(CLEAN), [])

    def test_missing_head_tags(self):
        html = "<html><body><main><h1>Hi</h1></main></body></html>"
        found = rules(html)
        for rule in ("LANG", "TITLE", "META-DESC", "SOCIAL", "SKIP-LINK"):
            self.assertIn(rule, found)

    def test_noindex_reported(self):
        html = CLEAN.replace("<head>", '<head><meta name="robots" content="noindex, follow">')
        self.assertIn("NOINDEX", rules(html))

    def test_h1_count_and_length(self):
        self.assertIn("H1-COUNT", rules(CLEAN.replace("</h1>", "</h1><h1>Second</h1>")))
        self.assertIn("H1-COUNT", rules(CLEAN.replace("<h1>Close the books in ten minutes</h1>", "")))
        long_h1 = CLEAN.replace("Close the books in ten minutes",
                                "The all in one platform that helps every growing team close their books faster")
        self.assertIn("H1-LENGTH", rules(long_h1))
        self.assertNotIn("H1-LENGTH", rules(long_h1, max_words=20))

    def test_vague_labels_with_nested_markup(self):
        html = CLEAN.replace("Book a demo", "<span>Learn more</span> →")
        self.assertIn("VAGUE-CTA", rules(html))
        self.assertIn("VAGUE-CTA", rules(CLEAN.replace("</main>", '<input type="submit"></main>')))
        self.assertNotIn("VAGUE-CTA", rules(CLEAN))

    def test_hash_link(self):
        self.assertIn("HASH-LINK", rules(CLEAN.replace('href="/trial"', 'href="#"')))

    def test_images(self):
        self.assertIn("IMG-ALT", rules(CLEAN.replace(' alt="Payout matching screen"', "")))
        self.assertNotIn("IMG-ALT", rules(CLEAN.replace('alt="Payout matching screen"', 'alt=""')))
        self.assertIn("IMG-SIZE", rules(CLEAN.replace(' width="1200" height="800"', "")))
        self.assertNotIn("IMG-SIZE", rules(CLEAN.replace(' width="1200" height="800"', ' style="aspect-ratio: 3/2"')))

    def test_video_autoplay(self):
        bad = CLEAN.replace("</main>", '<video src="a.mp4" autoplay loop></video></main>')
        good = CLEAN.replace("</main>", '<video src="a.mp4" autoplay muted playsinline loop></video></main>')
        self.assertIn("VIDEO-AUTOPLAY", rules(bad))
        self.assertNotIn("VIDEO-AUTOPLAY", rules(good))

    def test_reduced_motion_pooled_with_assets(self):
        no_rm = CLEAN.replace("@media (prefers-reduced-motion: reduce){.r{transition:none}}", "")
        self.assertIn("REDUCED-MOTION", rules(no_rm))
        self.assertNotIn("REDUCED-MOTION", rules(no_rm, extra="@media (prefers-reduced-motion: reduce){*{animation:none}}"))
        static = no_rm.replace(".r{transition: opacity 600ms} ", "")
        self.assertNotIn("REDUCED-MOTION", rules(static))

    def test_cli_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d, "good.html"); good.write_text(CLEAN, encoding="utf-8")
            bad = Path(d, "bad.html"); bad.write_text("<html><body><a href='#'>Submit</a></body></html>", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(lc.main([str(good)]), 0)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(lc.main([str(bad), "--json"]), 1)
            data = json.loads(out.getvalue())
            self.assertEqual(data["pages"], 1)
            self.assertIn("HASH-LINK", {f["rule"] for f in data["findings"]})
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(lc.main([str(Path(d, "missing.html"))]), 2)
                self.assertEqual(lc.main([str(good), "--max-words", "0"]), 2)

    def test_deterministic(self):
        self.assertEqual(lc.check("p.html", CLEAN + "<img src=x>"), lc.check("p.html", CLEAN + "<img src=x>"))


if __name__ == "__main__":
    unittest.main()
