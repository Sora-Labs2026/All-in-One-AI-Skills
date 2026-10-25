#!/usr/bin/env python3
"""Read-only pre-delivery inspection of Word, Excel and PowerPoint files (.docx/.xlsx/.pptx).

Opens the file as a ZIP package and reads its XML parts with the Python standard
library. Nothing is written, executed or fetched. It reports facts (counts, sheet
and slide lists) and "attention" items an agent should resolve or confirm before
handing a file over: tracked changes, comments, hidden text, leftover placeholders,
formulas without cached values, cached formula errors, hidden sheets, external
links, macros, off-slide shapes and empty placeholders.

It is a checklist aid, not a validator: a clean report does not prove the file
opens correctly or looks right. Render it as well (see the documents module).
"""
from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_MEMBERS = 20000
MAX_PART_BYTES = 200 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
SAMPLE_LIMIT = 8

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
}
R_ID = "{%s}id" % NS["r"]

PLACEHOLDER_PATTERNS = [
    ("double-brace token", re.compile(r"\{\{[^{}]{0,80}\}\}")),
    ("square-bracket token", re.compile(r"\[\[[^\[\]]{0,80}\]\]")),
    ("TODO/TBD/FIXME marker", re.compile(r"\b(?:TODO|TBD|FIXME)\b")),
    ("XXX marker", re.compile(r"\bXXX+\b")),
    ("lorem ipsum filler", re.compile(r"lorem ipsum", re.IGNORECASE)),
]
EXCEL_ERRORS = ("#DIV/0!", "#REF!", "#NAME?", "#VALUE!", "#N/A", "#NUM!", "#NULL!", "#SPILL!", "#CALC!", "#GETTING_DATA")

KINDS = {
    ".docx": "word", ".docm": "word", ".dotx": "word", ".dotm": "word",
    ".xlsx": "excel", ".xlsm": "excel", ".xltx": "excel", ".xltm": "excel",
    ".pptx": "powerpoint", ".pptm": "powerpoint", ".potx": "powerpoint", ".potm": "powerpoint",
}


class InspectError(Exception):
    """The file cannot be inspected (not a package, unsafe, or unsupported)."""


def q(prefix: str, tag: str) -> str:
    return "{%s}%s" % (NS[prefix], tag)


class Package:
    """Bounded, read-only access to the parts of an OOXML ZIP package."""

    def __init__(self, path: str):
        try:
            self.zf = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise InspectError(f"not a readable ZIP/OOXML package: {exc}") from None
        infos = self.zf.infolist()
        if len(infos) > MAX_MEMBERS:
            raise InspectError(f"package has {len(infos)} parts; limit is {MAX_MEMBERS}")
        total = sum(i.file_size for i in infos)
        if total > MAX_TOTAL_BYTES:
            raise InspectError("declared uncompressed size exceeds the safety limit")
        self.names = sorted(i.filename for i in infos)
        self._name_set = set(self.names)

    def has(self, name: str) -> bool:
        return name in self._name_set

    def read(self, name: str) -> bytes:
        info = self.zf.getinfo(name)
        if info.file_size > MAX_PART_BYTES:
            raise InspectError(f"part {name} exceeds the per-part size limit")
        with self.zf.open(info) as fh:
            data = fh.read(MAX_PART_BYTES + 1)
        if len(data) > MAX_PART_BYTES:
            raise InspectError(f"part {name} exceeds the per-part size limit")
        return data

    def xml(self, name: str):
        if not self.has(name):
            return None
        data = self.read(name)
        if b"<!DOCTYPE" in data[:4096].upper() or b"<!ENTITY" in data.upper():
            raise InspectError(f"part {name} declares a DOCTYPE/ENTITY; refusing to parse")
        try:
            return ET.fromstring(data)
        except ET.ParseError as exc:
            raise InspectError(f"part {name} is not well-formed XML: {exc}") from None

    def rels(self, part: str) -> dict:
        """Relationships of a part: {rId: (type_suffix, target_part_or_url, external)}."""
        folder, base = posixpath.split(part)
        rel_name = posixpath.join(folder, "_rels", base + ".rels")
        root = self.xml(rel_name)
        out = {}
        if root is None:
            return out
        for rel in root.findall(q("rel", "Relationship")):
            rid = rel.get("Id", "")
            rtype = rel.get("Type", "").rsplit("/", 1)[-1]
            target = rel.get("Target", "")
            external = rel.get("TargetMode") == "External"
            if not external:
                target = posixpath.normpath(posixpath.join(folder, target)) if not target.startswith("/") else target.lstrip("/")
            out[rid] = (rtype, target, external)
        return out


class Report:
    def __init__(self, path: str, kind: str):
        self.path = path
        self.kind = kind
        self.facts: dict = {}
        self.attention: list = []
        self.info: list = []

    def flag(self, code: str, message: str):
        self.attention.append({"code": code, "message": message})

    def note(self, code: str, message: str):
        self.info.append({"code": code, "message": message})

    def as_dict(self) -> dict:
        return {"path": self.path, "kind": self.kind, "facts": self.facts,
                "attention": self.attention, "info": self.info}


def sample(items, limit=SAMPLE_LIMIT) -> str:
    items = list(items)
    shown = ", ".join(items[:limit])
    return shown + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def scan_placeholders(report: Report, texts, where: str):
    hits = {}
    for text in texts:
        for label, pattern in PLACEHOLDER_PATTERNS:
            for m in pattern.finditer(text):
                hits.setdefault(label, [])
                if m.group(0) not in hits[label]:
                    hits[label].append(m.group(0))
    for label in sorted(hits):
        report.flag("placeholder", f"{label} left in {where}: {sample(hits[label])}")


def common_checks(pkg: Package, report: Report, macro_part: str):
    if any(n.endswith("vbaProject.bin") for n in pkg.names) or pkg.has(macro_part):
        report.flag("macros", "package contains a VBA project (macros); confirm the recipient expects a macro-enabled file")
    external = []
    for name in pkg.names:
        if not name.endswith(".rels"):
            continue
        root = pkg.xml(name)
        for rel in root.findall(q("rel", "Relationship")) if root is not None else []:
            if rel.get("TargetMode") == "External":
                external.append((rel.get("Type", "").rsplit("/", 1)[-1], rel.get("Target", "")))
    links = sorted({t for kind, t in external if kind == "hyperlink"})
    other = sorted({f"{kind} -> {t}" for kind, t in external if kind != "hyperlink"})
    if links:
        report.facts["external_hyperlinks"] = len(links)
        risky = [t for t in links if not re.match(r"^(https?|mailto):", t, re.IGNORECASE)]
        if risky:
            report.flag("local-link", f"hyperlinks to local or non-web targets: {sample(risky)}")
    if other:
        report.flag("external-reference", f"external (non-hyperlink) references: {sample(other)}")
    embedded = [n for n in pkg.names if "/embeddings/" in n]
    if embedded:
        report.note("embedded-objects", f"{len(embedded)} embedded object(s): {sample(embedded)}")
    core = pkg.xml("docProps/core.xml")
    if core is not None:
        people = {}
        for tag, label in ((q("dc", "creator"), "creator"), (q("cp", "lastModifiedBy"), "last modified by")):
            el = core.find(tag)
            if el is not None and (el.text or "").strip():
                people[label] = el.text.strip()
        title = core.find(q("dc", "title"))
        if title is not None and (title.text or "").strip():
            report.facts["title"] = title.text.strip()
        if people:
            report.note("metadata", "document properties name people: " + "; ".join(f"{k}: {v}" for k, v in sorted(people.items())))


# ---------------------------------------------------------------- Word
def para_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(q("w", "t")))


def inspect_word(pkg: Package, report: Report):
    doc = pkg.xml("word/document.xml")
    if doc is None:
        raise InspectError("word/document.xml not found; not a Word document")
    body = doc.find(q("w", "body"))
    paragraphs = list(body.iter(q("w", "p"))) if body is not None else []
    report.facts["paragraphs"] = len(paragraphs)
    report.facts["tables"] = len(list(doc.iter(q("w", "tbl"))))
    report.facts["sections"] = len(list(doc.iter(q("w", "sectPr"))))
    report.facts["images"] = len([n for n in pkg.names if n.startswith("word/media/")])
    headings = []
    for p in paragraphs:
        style = p.find("./%s/%s" % (q("w", "pPr"), q("w", "pStyle")))
        val = style.get(q("w", "val"), "") if style is not None else ""
        if re.match(r"^(Title|Heading\d)$", val):
            text = para_text(p).strip()
            if text:
                headings.append(f"{val}: {text[:60]}")
    report.facts["headings"] = headings[:20]

    parts = ["word/document.xml"] + [n for n in pkg.names if re.match(r"word/(header|footer|footnotes|endnotes)\d*\.xml$", n)]
    counts = {"insertion(s)": 0, "deletion(s)": 0, "move(s)": 0, "formatting change(s)": 0}
    authors = set()
    hidden_runs = 0
    texts = []
    for part in parts:
        root = doc if part == "word/document.xml" else pkg.xml(part)
        for tag, key in (("ins", "insertion(s)"), ("del", "deletion(s)"), ("moveFrom", "move(s)"),
                         ("rPrChange", "formatting change(s)"), ("pPrChange", "formatting change(s)")):
            for el in root.iter(q("w", tag)):
                counts[key] += 1
                if el.get(q("w", "author")):
                    authors.add(el.get(q("w", "author")))
        hidden_runs += sum(1 for rpr in root.iter(q("w", "rPr")) if rpr.find(q("w", "vanish")) is not None)
        texts += [para_text(p) for p in root.iter(q("w", "p"))]
    total_changes = sum(counts.values())
    report.facts["tracked_changes"] = total_changes
    if total_changes:
        detail = ", ".join(f"{v} {k}" for k, v in counts.items() if v)
        who = f" by {sample(sorted(authors))}" if authors else ""
        report.flag("tracked-changes", f"{total_changes} tracked change(s) ({detail}){who}; accept/reject them or confirm the redline is the deliverable")
    if hidden_runs:
        report.flag("hidden-text", f"{hidden_runs} run(s) formatted as hidden text; check they hold nothing that must not be shared")

    comments = pkg.xml("word/comments.xml")
    n_comments = len(comments.findall(q("w", "comment"))) if comments is not None else 0
    report.facts["comments"] = n_comments
    if n_comments:
        c_authors = sorted({c.get(q("w", "author"), "") for c in comments.findall(q("w", "comment"))} - {""})
        report.flag("comments", f"{n_comments} comment(s)" + (f" by {sample(c_authors)}" if c_authors else "") + "; remove or resolve them unless the reviewer should see them")

    instr = " ".join((t.text or "") for t in doc.iter(q("w", "instrText")))
    instr += " " + " ".join(f.get(q("w", "instr"), "") for f in doc.iter(q("w", "fldSimple")))
    if re.search(r"\bTOC\b", instr):
        report.note("toc-field", "contains a table-of-contents field; its entries and page numbers refresh only when an editor updates fields")
    scan_placeholders(report, texts, "the text")
    common_checks(pkg, report, "word/vbaProject.bin")


# ---------------------------------------------------------------- Excel
def col_row(ref: str):
    m = re.match(r"^([A-Z]+)(\d+)$", ref or "")
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def inspect_excel(pkg: Package, report: Report):
    wb = pkg.xml("xl/workbook.xml")
    if wb is None:
        raise InspectError("xl/workbook.xml not found; not an Excel workbook")
    rels = pkg.rels("xl/workbook.xml")
    shared = []
    sst = pkg.xml("xl/sharedStrings.xml")
    if sst is not None:
        for si in sst.findall(q("s", "si")):
            shared.append("".join(t.text or "" for t in si.iter(q("s", "t"))))
    calc = wb.find(q("s", "calcPr"))
    if calc is not None and calc.get("fullCalcOnLoad") in ("1", "true"):
        report.note("recalc-on-load", "workbook asks spreadsheet apps to recalculate on open (fullCalcOnLoad); tools that read cached values still see the stored values")

    sheets_out = []
    no_cache, errors = [], []
    texts = list(shared)
    for sheet in wb.iter(q("s", "sheet")):
        name = sheet.get("name", "?")
        state = sheet.get("state", "visible")
        target = rels.get(sheet.get(R_ID, ""), ("", "", False))[1]
        root = pkg.xml(target) if target else None
        entry = {"name": name, "state": state, "cells": 0, "formulas": 0}
        if root is not None:
            dim = root.find(q("s", "dimension"))
            entry["range"] = dim.get("ref", "") if dim is not None else ""
            for c in root.iter(q("s", "c")):
                entry["cells"] += 1
                f = c.find(q("s", "f"))
                v = c.find(q("s", "v"))
                ref = c.get("r", "?")
                if f is not None:
                    entry["formulas"] += 1
                    if v is None or (v.text or "") == "":
                        no_cache.append(f"{name}!{ref}")
                if c.get("t") == "e" and v is not None:
                    errors.append(f"{name}!{ref}={v.text}")
                if c.get("t") == "inlineStr":
                    texts.append("".join(t.text or "" for t in c.iter(q("s", "t"))))
            merged = root.find(q("s", "mergeCells"))
            entry["merged_ranges"] = len(merged) if merged is not None else 0
            entry["conditional_formats"] = len(root.findall(q("s", "conditionalFormatting")))
            dvs = root.find(q("s", "dataValidations"))
            entry["data_validations"] = len(dvs) if dvs is not None else 0
        sheets_out.append(entry)
        if state != "visible":
            report.flag("hidden-sheet", f"sheet '{name}' is {state}; confirm it holds nothing the recipient must not see")
    report.facts["sheets"] = sheets_out
    report.facts["formulas"] = sum(s["formulas"] for s in sheets_out)
    if no_cache:
        report.flag("no-cached-values", f"{len(no_cache)} formula cell(s) have no cached value ({sample(no_cache)}); readers that do not calculate (pandas, previews, data_only loads) see blanks; recalculate before delivery")
    if errors:
        report.flag("formula-errors", f"{len(errors)} cell(s) hold cached formula errors: {sample(errors)}")

    names = wb.find(q("s", "definedNames"))
    if names is not None:
        broken = [n.get("name", "?") for n in names if "#REF!" in (n.text or "")]
        report.facts["defined_names"] = len(names)
        if broken:
            report.flag("broken-names", f"defined names pointing at #REF!: {sample(broken)}")
    ext = [n for n in pkg.names if n.startswith("xl/externalLinks/") and n.endswith(".xml")]
    if ext:
        report.flag("external-workbooks", f"{len(ext)} link(s) to external workbooks; values may be stale or unavailable to the recipient")
    if any(n.startswith("xl/pivotTables/") for n in pkg.names):
        report.note("pivots", "contains pivot tables; their caches refresh only in a spreadsheet app")
    scan_placeholders(report, texts, "cell text")
    common_checks(pkg, report, "xl/vbaProject.bin")


# ---------------------------------------------------------------- PowerPoint
def xfrm_box(el):
    """(x, y, cx, cy) of a top-level shape, or None if it inherits its position."""
    for path in ("./p:spPr/a:xfrm", "./p:grpSpPr/a:xfrm", "./p:xfrm"):
        x = el.find(path, NS)
        if x is not None:
            off, ext = x.find("a:off", NS), x.find("a:ext", NS)
            if off is not None and ext is not None:
                return (int(off.get("x", 0)), int(off.get("y", 0)), int(ext.get("cx", 0)), int(ext.get("cy", 0)))
    return None


def inspect_powerpoint(pkg: Package, report: Report):
    pres = pkg.xml("ppt/presentation.xml")
    if pres is None:
        raise InspectError("ppt/presentation.xml not found; not a PowerPoint presentation")
    size = pres.find(q("p", "sldSz"))
    width = int(size.get("cx")) if size is not None else None
    height = int(size.get("cy")) if size is not None else None
    if width and height:
        report.facts["slide_size_in"] = f"{width / 914400:.2f} x {height / 914400:.2f}"
    rels = pkg.rels("ppt/presentation.xml")
    slides = []
    off_slide, empty_ph, hidden, texts = [], [], [], []
    lst = pres.find(q("p", "sldIdLst"))
    for n, sid in enumerate(lst if lst is not None else [], start=1):
        part = rels.get(sid.get(R_ID, ""), ("", "", False))[1]
        root = pkg.xml(part) if part else None
        if root is None:
            continue
        if root.get("show") == "0":
            hidden.append(str(n))
        slide_rels = pkg.rels(part)
        has_notes = any(t == "notesSlide" for t, _, _ in slide_rels.values())
        tree = root.find("./p:cSld/p:spTree", NS)
        shapes = [el for el in (tree if tree is not None else []) if el.tag in (q("p", "sp"), q("p", "pic"), q("p", "graphicFrame"), q("p", "grpSp"), q("p", "cxnSp"))]
        slide_text = []
        title = ""
        for el in shapes:
            text = " ".join("".join(t.text or "" for t in para.iter(q("a", "t"))) for para in el.iter(q("a", "p"))).strip()
            ph = el.find("./p:nvSpPr/p:nvPr/p:ph", NS)
            name_el = el.find(".//p:cNvPr", NS)
            shape_name = name_el.get("name", "?") if name_el is not None else "?"
            if ph is not None and ph.get("type") in ("title", "ctrTitle") and text:
                title = text
            if ph is not None and not text and el.find("p:txBody", NS) is not None and ph.get("type") not in ("dt", "ftr", "sldNum"):
                empty_ph.append(f"slide {n}: {shape_name}")
            box = xfrm_box(el)
            if box and width and height:
                x, y, cx, cy = box
                if x < 0 or y < 0 or x + cx > width or y + cy > height:
                    off_slide.append(f"slide {n}: {shape_name}")
            if text:
                slide_text.append(text)
        texts += slide_text
        slides.append({"number": n, "title": title[:80], "shapes": len(shapes), "notes": has_notes,
                       "pictures": len(root.findall(".//p:pic", NS)),
                       "charts": sum(1 for t, _, _ in slide_rels.values() if t == "chart")})
    report.facts["slides"] = slides
    report.facts["slide_count"] = len(slides)
    if off_slide:
        report.flag("off-slide", f"shape(s) extend beyond the slide edge: {sample(off_slide)}")
    if empty_ph:
        report.flag("empty-placeholder", f"empty placeholder(s) that show prompt text while editing: {sample(empty_ph)}")
    if hidden:
        report.note("hidden-slides", f"hidden slide(s): {', '.join(hidden)}")
    if any(n.startswith("ppt/comments/") or n.startswith("ppt/commentAuthors") for n in pkg.names):
        report.flag("comments", "presentation contains review comments; remove or resolve them unless the reviewer should see them")
    scan_placeholders(report, texts, "slide text")
    common_checks(pkg, report, "ppt/vbaProject.bin")


INSPECTORS = {"word": inspect_word, "excel": inspect_excel, "powerpoint": inspect_powerpoint}


def inspect(path: str) -> Report:
    ext = posixpath.splitext(path.lower())[1]
    kind = KINDS.get(ext)
    if kind is None:
        raise InspectError(f"unsupported extension '{ext}'; expected one of {', '.join(sorted(KINDS))}")
    pkg = Package(path)
    report = Report(path, kind)
    try:
        INSPECTORS[kind](pkg, report)
    finally:
        pkg.zf.close()
    return report


def render_text(reports, failures) -> str:
    lines = []
    for rep in reports:
        lines.append(f"{rep.path} ({rep.kind})")
        for key in sorted(rep.facts):
            value = rep.facts[key]
            if isinstance(value, list) and value and isinstance(value[0], dict):
                lines.append(f"  {key}:")
                for item in value:
                    lines.append("    - " + ", ".join(f"{k}={v}" for k, v in item.items()))
            elif isinstance(value, list):
                lines.append(f"  {key}: " + ("; ".join(value) if value else "none"))
            else:
                lines.append(f"  {key}: {value}")
        lines.append(f"  attention ({len(rep.attention)}):" if rep.attention else "  attention: none")
        lines += [f"    ! [{a['code']}] {a['message']}" for a in rep.attention]
        if rep.info:
            lines.append(f"  info ({len(rep.info)}):")
            lines += [f"    i [{i['code']}] {i['message']}" for i in rep.info]
    for path, msg in failures:
        lines.append(f"{path}: ERROR {msg}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only inspection of .docx/.xlsx/.pptx files before delivery. "
                    "Exit 0 = inspected, 1 = attention items with --fail-on attention, 2 = a file could not be inspected.")
    parser.add_argument("files", nargs="+", metavar="FILE", help="Office Open XML files to inspect")
    parser.add_argument("--json", action="store_true", help="print a JSON report instead of text")
    parser.add_argument("--fail-on", choices=("never", "attention"), default="never",
                        help="exit 1 when any attention item is found (default: never)")
    args = parser.parse_args(argv)

    reports, failures = [], []
    for path in args.files:
        try:
            reports.append(inspect(path))
        except InspectError as exc:
            failures.append((path, str(exc)))
        except (OSError, KeyError) as exc:
            failures.append((path, f"cannot read: {exc}"))
    if args.json:
        out = {"files": [r.as_dict() for r in reports], "errors": [{"path": p, "error": m} for p, m in failures]}
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(render_text(reports, failures))
    if failures:
        return 2
    if args.fail_on == "attention" and any(r.attention for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
