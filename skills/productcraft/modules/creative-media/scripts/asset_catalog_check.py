#!/usr/bin/env python3
"""ProductCraft Xcode asset catalog checker. Read-only: it reads files and prints findings.

Checks every *.appiconset and *.imageset inside the given .xcassets folders (or
inside any .xcassets folder found under a project directory):

  errors    Contents.json missing or not valid JSON; an image entry naming a file
            that does not exist; a PNG whose pixel size does not match the entry's
            size x scale; a non-square app icon; the default-appearance 1024x1024
            App Store icon carrying an alpha channel (App Store submission rejects
            it); image-set scales whose pixel sizes are not 1x : 2x : 3x
  warnings  files in a set that no entry references; an iOS app icon set without
            a 1024x1024 entry; an entry without a filename (an empty slot)
  info      dark and tinted app icon appearances present or absent; vector images
            and Icon Composer (.icon) files found but not measured

PNG facts come from the file header (IHDR) and the presence of a tRNS chunk; no
image library is needed and pixels are not decoded.

Exit codes: 0 clean; 1 errors or warnings; 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys

VERSION = "1.0.0"
PNG_SIG = b"\x89PNG\r\n\x1a\n"
SIZE = re.compile(r"^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)$")
SCALE = re.compile(r"^(\d)x$")
VECTOR_EXT = {".pdf", ".svg"}
IGNORED = {"Contents.json", ".DS_Store"}


def png_info(path: str):
    """Return (width, height, has_alpha) or None if the file is not a readable PNG."""
    try:
        with open(path, "rb") as fh:
            if fh.read(8) != PNG_SIG:
                return None
            width = height = None
            alpha = False
            for _ in range(10_000):
                head = fh.read(8)
                if len(head) < 8:
                    break
                length, ctype = struct.unpack(">I4s", head)
                if ctype == b"IHDR":
                    data = fh.read(length)
                    width, height, _depth, color_type = struct.unpack(">IIBB", data[:10])
                    alpha = color_type in (4, 6)
                    fh.seek(4, os.SEEK_CUR)
                    continue
                if ctype == b"tRNS":
                    alpha = True
                if ctype in (b"IDAT", b"IEND"):
                    break
                fh.seek(length + 4, os.SEEK_CUR)
            if width is None:
                return None
            return width, height, alpha
    except OSError:
        return None


def find_catalogs(paths):
    found = []
    for p in paths:
        if p.rstrip("/").endswith(".xcassets"):
            found.append(p.rstrip("/"))
            continue
        for dirpath, dirnames, _ in os.walk(p):
            dirnames[:] = sorted(d for d in dirnames if d not in {".git", "node_modules", "DerivedData", "Pods", "build"})
            for d in list(dirnames):
                if d.endswith(".xcassets"):
                    found.append(os.path.join(dirpath, d))
                    dirnames.remove(d)
    return sorted(set(found))


class Checker:
    def __init__(self):
        self.findings = []
        self.sets = 0
        self.images = 0

    def add(self, level, where, message):
        self.findings.append({"level": level, "where": where, "message": message})

    def load(self, set_dir):
        path = os.path.join(set_dir, "Contents.json")
        if not os.path.isfile(path):
            self.add("error", set_dir, "Contents.json missing")
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            self.add("error", path, f"Contents.json is not valid JSON ({exc.__class__.__name__})")
            return None
        images = data.get("images")
        if not isinstance(images, list):
            self.add("error", path, "Contents.json has no images list")
            return None
        return images

    def common(self, set_dir, images):
        on_disk = {f for f in os.listdir(set_dir) if f not in IGNORED and not f.startswith(".")}
        referenced = set()
        for entry in images:
            name = entry.get("filename")
            if not name:
                self.add("warning", set_dir, f"empty slot ({describe(entry)}): no file assigned")
                continue
            referenced.add(name)
            if name not in on_disk:
                self.add("error", os.path.join(set_dir, name), "referenced file does not exist")
        for extra in sorted(on_disk - referenced):
            if not os.path.isdir(os.path.join(set_dir, extra)):
                self.add("warning", os.path.join(set_dir, extra), "file is not referenced by Contents.json")
        return on_disk

    def appiconset(self, set_dir):
        images = self.load(set_dir)
        if images is None:
            return
        self.sets += 1
        on_disk = self.common(set_dir, images)
        has_1024 = False
        appearances = set()
        ios = any(e.get("platform") == "ios" or e.get("idiom") in ("iphone", "ipad", "ios-marketing")
                  for e in images)
        for entry in images:
            name = entry.get("filename")
            app = {a.get("value") for a in entry.get("appearances", []) if isinstance(a, dict)}
            appearances |= app
            m = SIZE.match(str(entry.get("size", "")))
            if not m:
                continue
            w_pt, h_pt = float(m.group(1)), float(m.group(2))
            scale_m = SCALE.match(str(entry.get("scale", "1x")))
            scale = int(scale_m.group(1)) if scale_m else 1
            exp_w, exp_h = round(w_pt * scale), round(h_pt * scale)
            if exp_w == 1024 and exp_h == 1024:
                has_1024 = True
            if not name or name not in on_disk:
                continue
            where = os.path.join(set_dir, name)
            if os.path.splitext(name)[1].lower() != ".png":
                self.add("info", where, "not a PNG; size not checked")
                continue
            info = png_info(where)
            self.images += 1
            if info is None:
                self.add("error", where, "not a readable PNG")
                continue
            w, h, alpha = info
            if w != h:
                self.add("error", where, f"app icon is {w}x{h}, not square")
            if (w, h) != (exp_w, exp_h):
                self.add("error", where, f"is {w}x{h} px, expected {exp_w}x{exp_h} for {entry.get('size')} @{scale}x")
            marketing = (exp_w == 1024 and not app) or entry.get("idiom") == "ios-marketing"
            if marketing and alpha:
                self.add("error", where, "App Store icon has an alpha channel; export it opaque (no alpha)")
        if ios and not has_1024:
            self.add("warning", set_dir, "no 1024x1024 entry; Xcode 14 and later can generate all sizes from one")
        if ios:
            for look in ("dark", "tinted"):
                state = "present" if look in appearances else "absent"
                self.add("info", set_dir, f"{look} appearance {state}")

    def imageset(self, set_dir):
        images = self.load(set_dir)
        if images is None:
            return
        self.sets += 1
        on_disk = self.common(set_dir, images)
        groups = {}
        for entry in images:
            name = entry.get("filename")
            if not name or name not in on_disk:
                continue
            where = os.path.join(set_dir, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in VECTOR_EXT:
                self.add("info", where, "vector image; renders at any scale")
                continue
            if ext != ".png":
                continue
            info = png_info(where)
            self.images += 1
            if info is None:
                self.add("error", where, "not a readable PNG")
                continue
            scale_m = SCALE.match(str(entry.get("scale", "")))
            if scale_m:
                key = (entry.get("idiom", ""), tuple(sorted(a.get("value", "") for a in entry.get("appearances", [])
                                                            if isinstance(a, dict))))
                groups.setdefault(key, []).append((int(scale_m.group(1)), info[0], info[1], where))
        for members in groups.values():
            members.sort()
            base_scale, bw, bh, _ = members[0]
            for scale, w, h, where in members[1:]:
                ew, eh = bw * scale / base_scale, bh * scale / base_scale
                if abs(w - ew) > 1 or abs(h - eh) > 1:
                    self.add("error", where, f"@{scale}x is {w}x{h} px; expected about {ew:g}x{eh:g} from @{base_scale}x")


def describe(entry):
    parts = [str(entry.get(k)) for k in ("idiom", "size", "scale") if entry.get(k)]
    return " ".join(parts) or "unnamed entry"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only check of Xcode asset catalogs: app icon sizes, "
                                 "App Store icon alpha, missing and unreferenced files, image-set scales.")
    ap.add_argument("paths", nargs="+", help=".xcassets folders, or project folders to search")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--quiet-info", action="store_true", help="omit info lines from text output")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    for p in args.paths:
        if not os.path.isdir(p):
            print(f"error: not a folder: {p}", file=sys.stderr)
            return 2
    catalogs = find_catalogs(args.paths)
    if not catalogs:
        print("error: no .xcassets folder found", file=sys.stderr)
        return 2
    chk = Checker()
    for cat in catalogs:
        for dirpath, dirnames, filenames in os.walk(cat):
            dirnames.sort()
            for d in list(dirnames):
                full = os.path.join(dirpath, d)
                if d.endswith(".appiconset"):
                    chk.appiconset(full)
                    dirnames.remove(d)
                elif d.endswith(".imageset"):
                    chk.imageset(full)
                    dirnames.remove(d)
                elif d.endswith(".icon"):
                    chk.add("info", full, "Icon Composer file; check it in Xcode's preview")
                    dirnames.remove(d)
    counts = {lvl: sum(1 for f in chk.findings if f["level"] == lvl) for lvl in ("error", "warning", "info")}
    report = {"tool": "asset_catalog_check", "version": VERSION, "catalogs": catalogs, "sets_checked": chk.sets,
              "pngs_measured": chk.images, "counts": counts, "findings": chk.findings}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{len(catalogs)} catalog(s), {chk.sets} set(s), {chk.images} PNG(s) measured: "
              f"{counts['error']} error(s), {counts['warning']} warning(s)")
        for f in chk.findings:
            if f["level"] == "info" and args.quiet_info:
                continue
            print(f"  {f['level'].upper():7} {f['where']}: {f['message']}")
    return 1 if counts["error"] or counts["warning"] else 0


if __name__ == "__main__":
    sys.exit(main())
