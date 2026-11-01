"""Tests for scripts/asset_catalog_check.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "asset_catalog_check.py"
SPEC = importlib.util.spec_from_file_location("asset_catalog_check", SCRIPT)
asset_catalog_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(asset_catalog_check)


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png(width: int, height: int, color_type: int = 2, trns: bool = False) -> bytes:
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    raw = b"".join(b"\x00" + b"\x00" * (width * channels) for _ in range(height))
    body = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    if trns:
        body += chunk(b"tRNS", b"\x00\x00\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + body + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cat = self.root / "App" / "Assets.xcassets"
        self.cat.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def make_set(self, name, contents, files):
        d = self.cat / name
        d.mkdir(parents=True)
        (d / "Contents.json").write_text(json.dumps(contents) if not isinstance(contents, str) else contents,
                                         encoding="utf-8")
        for fname, data in files.items():
            (d / fname).write_bytes(data)
        return d

    def run_json(self, *paths):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = asset_catalog_check.main([str(p) for p in paths] + ["--json"])
        return code, (json.loads(out.getvalue()) if out.getvalue() else None)

    def messages(self, rep, level):
        return [f["message"] for f in rep["findings"] if f["level"] == level]

    def single_size_icon(self, data, extra=None):
        images = [{"filename": "icon.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}]
        images += extra or []
        return {"images": images, "info": {"author": "xcode", "version": 1}}

    def test_valid_single_size_icon_is_clean(self):
        self.make_set("AppIcon.appiconset", self.single_size_icon(None), {"icon.png": png(1024, 1024)})
        code, rep = self.run_json(self.root)
        self.assertEqual(code, 0, rep["findings"])
        self.assertEqual(rep["pngs_measured"], 1)
        self.assertIn("dark appearance absent", self.messages(rep, "info"))

    def test_store_icon_with_alpha_is_an_error(self):
        self.make_set("AppIcon.appiconset", self.single_size_icon(None), {"icon.png": png(1024, 1024, 6)})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 1)
        self.assertTrue(any("alpha channel" in m for m in self.messages(rep, "error")))

    def test_trns_chunk_counts_as_alpha(self):
        self.make_set("AppIcon.appiconset", self.single_size_icon(None), {"icon.png": png(1024, 1024, 2, trns=True)})
        _, rep = self.run_json(self.cat)
        self.assertTrue(any("alpha channel" in m for m in self.messages(rep, "error")))

    def test_dark_variant_may_have_alpha_and_is_reported(self):
        dark = {"filename": "dark.png", "idiom": "universal", "platform": "ios", "size": "1024x1024",
                "appearances": [{"appearance": "luminosity", "value": "dark"}]}
        self.make_set("AppIcon.appiconset", self.single_size_icon(None, [dark]),
                      {"icon.png": png(1024, 1024), "dark.png": png(1024, 1024, 6)})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 0, rep["findings"])
        self.assertIn("dark appearance present", self.messages(rep, "info"))

    def test_legacy_sizes_checked_against_scale(self):
        contents = {"images": [
            {"filename": "i60@3x.png", "idiom": "iphone", "size": "60x60", "scale": "3x"},
            {"filename": "i29@2x.png", "idiom": "iphone", "size": "29x29", "scale": "2x"},
            {"filename": "store.png", "idiom": "ios-marketing", "size": "1024x1024", "scale": "1x"}]}
        self.make_set("AppIcon.appiconset", contents,
                      {"i60@3x.png": png(180, 180), "i29@2x.png": png(60, 60), "store.png": png(1024, 1024)})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 1)
        errors = self.messages(rep, "error")
        self.assertEqual(len(errors), 1)
        self.assertIn("expected 58x58", errors[0])

    def test_missing_and_unreferenced_files(self):
        self.make_set("AppIcon.appiconset", self.single_size_icon(None), {"old-icon.png": png(1024, 1024)})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 1)
        self.assertIn("referenced file does not exist", self.messages(rep, "error"))
        self.assertIn("file is not referenced by Contents.json", self.messages(rep, "warning"))

    def test_icon_set_without_1024_warns(self):
        contents = {"images": [{"filename": "i60@2x.png", "idiom": "iphone", "size": "60x60", "scale": "2x"}]}
        self.make_set("AppIcon.appiconset", contents, {"i60@2x.png": png(120, 120)})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 1)
        self.assertTrue(any("1024x1024" in m for m in self.messages(rep, "warning")))

    def test_imageset_scale_consistency(self):
        contents = {"images": [
            {"filename": "r.png", "idiom": "universal", "scale": "1x"},
            {"filename": "r@2x.png", "idiom": "universal", "scale": "2x"},
            {"filename": "r@3x.png", "idiom": "universal", "scale": "3x"}]}
        self.make_set("Receipt.imageset", contents,
                      {"r.png": png(24, 24), "r@2x.png": png(48, 48), "r@3x.png": png(70, 72)})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 1)
        errors = self.messages(rep, "error")
        self.assertEqual(len(errors), 1)
        self.assertIn("@3x is 70x72", errors[0])

    def test_vector_imageset_is_info_only(self):
        contents = {"images": [{"filename": "r.svg", "idiom": "universal"}],
                    "properties": {"preserves-vector-representation": True}}
        self.make_set("Receipt.imageset", contents, {"r.svg": b"<svg xmlns='http://www.w3.org/2000/svg'/>"})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 0)
        self.assertIn("vector image; renders at any scale", self.messages(rep, "info"))

    def test_invalid_json_and_not_png(self):
        self.make_set("Bad.imageset", "{not json", {})
        self.make_set("AppIcon.appiconset", self.single_size_icon(None), {"icon.png": b"JPEG?"})
        code, rep = self.run_json(self.cat)
        self.assertEqual(code, 1)
        errors = self.messages(rep, "error")
        self.assertTrue(any("not valid JSON" in m for m in errors))
        self.assertIn("not a readable PNG", errors)

    def test_usage_errors_and_text_output(self):
        self.assertEqual(self.run_json(self.root / "missing")[0], 2)
        empty = self.root / "empty"
        empty.mkdir()
        self.assertEqual(self.run_json(empty)[0], 2)
        self.make_set("AppIcon.appiconset", self.single_size_icon(None), {"icon.png": png(1024, 1024)})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = asset_catalog_check.main([str(self.root), "--quiet-info"])
        self.assertEqual(code, 0)
        self.assertIn("0 error(s), 0 warning(s)", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            asset_catalog_check.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
