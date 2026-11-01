"""Tests for scripts/token_inventory.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "token_inventory.py"
SPEC = importlib.util.spec_from_file_location("token_inventory", SCRIPT)
token_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(token_inventory)


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = token_inventory.main([str(a) for a in argv])
    return code, out.getvalue()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def report(self, *extra):
        code, out = run(self.root, "--json", *extra)
        return code, json.loads(out)

    def test_clean_project_exits_zero(self):
        self.write("a.css", ".a { padding: 8px 16px; color: var(--text); transition: opacity 150ms; }\n")
        code, rep = self.report()
        self.assertEqual(code, 0)
        self.assertEqual(rep["summary"]["spacing_off_scale"], 0)
        self.assertEqual(rep["summary"]["var_uses"], 1)

    def test_colors_normalized_and_near_duplicates_clustered(self):
        self.write("a.css", ".a { color: #1B6EF3; background: rgb(26 109 242); border-color: #fff; }\n"
                            ".b { color: hsl(0, 0%, 100%); }\n")
        code, rep = self.report()
        values = {c["value"]: c["count"] for c in rep["colors"]}
        self.assertEqual(values["#ffffff"], 2)          # #fff and hsl white are the same color
        self.assertIn("#1b6ef3", values)
        self.assertEqual(rep["summary"]["near_duplicate_clusters"], 1)
        self.assertEqual(sorted(rep["near_duplicate_colors"][0]["members"]), ["#1a6df2", "#1b6ef3"])
        self.assertEqual(code, 1)

    def test_alpha_colors_keep_alpha_and_are_not_clustered(self):
        self.write("a.css", ".a { box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); color: #000; }\n")
        _, rep = self.report()
        self.assertIn("#00000033", {c["value"] for c in rep["colors"]})
        self.assertEqual(rep["summary"]["near_duplicate_clusters"], 0)

    def test_comments_selectors_and_urls_ignored(self):
        self.write("a.css", "/* color: #123456 */\n#add-button:hover { margin: 8px; }\n")
        self.write("b.tsx", "// color: #abcdef\nconst l = { href: \"/page#add\" };\n")
        _, rep = self.report()
        self.assertEqual(rep["summary"]["raw_colors"], 0)

    def test_spacing_scale_optical_and_rem(self):
        self.write("a.scss", ".a { padding: 13px 1rem; margin: 2px; gap: calc(1rem + 3px); }\n")
        _, rep = self.report()
        self.assertEqual([x["value"] for x in rep["spacing_off_scale"]], ["13px"])
        self.assertEqual([x["value"] for x in rep["spacing_optical"]], ["2px"])

    def test_spacing_base_option(self):
        self.write("a.css", ".a { padding: 12px; }\n")
        code, rep = self.report("--spacing-base", "8")
        self.assertEqual([x["value"] for x in rep["spacing_off_scale"]], ["12px"])
        self.assertEqual(code, 1)

    def test_flags_transition_all_and_will_change(self):
        self.write("a.css", ".a { transition: all .2s ease; }\n.b { will-change: all; }\n")
        code, rep = self.report()
        self.assertEqual({f["value"] for f in rep["flags"]}, {"transition: all", "will-change: all"})
        self.assertEqual(code, 1)
        self.assertIn("200", {d["value"] for d in rep["durations_ms"]})

    def test_script_objects_and_template_css(self):
        self.write("Button.tsx",
                   'const s = { fontSize: 14, paddingTop: "10px", zIndex: 30, color: "#1B6EF3" };\n'
                   "const Box = styled.div`\n  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);\n  margin: 6px;\n`;\n")
        _, rep = self.report()
        self.assertEqual([f["value"] for f in rep["font_sizes"]], ["14px"])
        self.assertEqual({x["value"] for x in rep["spacing_off_scale"]}, {"10px", "6px"})
        self.assertEqual([z["value"] for z in rep["z_index"]], ["30"])
        self.assertEqual([s["value"] for s in rep["shadows"]], ["0 2px 4px rgba(0, 0, 0, 0.3)"])

    def test_tailwind_arbitrary_values(self):
        self.write("Card.jsx", '<div className="bg-[#1a2b3c] p-[13px] m-[16px]" />\n')
        _, rep = self.report()
        self.assertIn("#1a2b3c", {c["value"] for c in rep["colors"]})
        self.assertEqual([x["value"] for x in rep["spacing_off_scale"]], ["13px (arbitrary class)"])

    def test_token_files_count_definitions_not_findings(self):
        self.write("tokens.css", ":root { --accent: #0F766E; --space-3: 13px; }\n.x { color: #123456; }\n")
        self.write("vars.scss", "$brand: #ff0000;\n")
        code, rep = self.report()
        self.assertEqual(rep["summary"]["token_definitions"], 3)
        self.assertEqual(rep["summary"]["raw_colors"], 0)
        self.assertEqual(code, 0)

    def test_skips_dependency_and_hidden_folders(self):
        self.write("node_modules/lib/a.css", ".a { color: #000; }\n")
        self.write(".storybook/b.css", ".b { color: #000; }\n")
        _, rep = self.report()
        self.assertEqual(rep["summary"]["files_scanned"], 0)

    def test_baseline_ratchet(self):
        self.write("a.css", ".a { color: #111111; }\n")
        _, before = self.report()
        base = self.root / "base.json"
        base.write_text(json.dumps(before), encoding="utf-8")
        self.write("b.css", ".b { color: #222222; }\n")
        code, rep = run(self.root / "a.css", self.root / "b.css", "--baseline", base, "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(rep)["baseline_growth"], ["raw_colors: 1 -> 2"])

    def test_output_is_deterministic(self):
        self.write("a.css", ".a { color: #333; padding: 7px; }\n.b { color: #444; }\n")
        self.assertEqual(run(self.root, "--json")[1], run(self.root, "--json")[1])

    def test_text_output_and_usage_errors(self):
        self.write("a.css", ".a { padding: 13px; }\n")
        code, out = run(self.root)
        self.assertEqual(code, 1)
        self.assertIn("Off-scale spacing", out)
        self.assertEqual(run(self.root / "missing")[0], 2)
        self.assertEqual(run(self.root, "--spacing-base", "0")[0], 2)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            token_inventory.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
