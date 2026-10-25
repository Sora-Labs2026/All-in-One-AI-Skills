"""Tests for scripts/ooxml_inspect.py. Standard library only; fixtures are built in a temp dir."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import ooxml_inspect as oi  # noqa: E402

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
P = ('xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
     'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
     'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
RELS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"


def rels(*items):
    body = "".join(
        f'<Relationship Id="{rid}" Type="{RT}{kind}" Target="{target}"' + (' TargetMode="External"' if ext else "") + "/>"
        for rid, kind, target, ext in items)
    return f'<?xml version="1.0"?><Relationships {RELS}>{body}</Relationships>'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, name, parts):
        path = os.path.join(self.tmp.name, name)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            for part, data in parts.items():
                zf.writestr(part, data)
        return path

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = oi.main(list(args))
        return code, out.getvalue()

    @staticmethod
    def codes(report):
        return sorted(a["code"] for a in report.attention)


class WordTests(Fixture):
    def docx(self, body, extra=None):
        parts = {"word/document.xml": f'<?xml version="1.0"?><w:document {W}><w:body>{body}<w:sectPr/></w:body></w:document>'}
        parts.update(extra or {})
        return self.make("doc.docx", parts)

    def test_clean_document_has_no_attention(self):
        path = self.docx('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Scope</w:t></w:r></w:p>'
                         '<w:p><w:r><w:t>Plain text.</w:t></w:r></w:p>')
        rep = oi.inspect(path)
        self.assertEqual(rep.attention, [])
        self.assertEqual(rep.facts["paragraphs"], 2)
        self.assertEqual(rep.facts["headings"], ["Heading1: Scope"])

    def test_tracked_changes_counted_with_authors(self):
        path = self.docx(
            '<w:p><w:r><w:t>Due in </w:t></w:r>'
            '<w:del w:id="1" w:author="Kim"><w:r><w:delText>30</w:delText></w:r></w:del>'
            '<w:ins w:id="2" w:author="Lee"><w:r><w:t>45</w:t></w:r></w:ins>'
            '<w:r><w:t> days</w:t></w:r></w:p>')
        rep = oi.inspect(path)
        self.assertEqual(rep.facts["tracked_changes"], 2)
        msg = rep.attention[0]["message"]
        self.assertEqual(rep.attention[0]["code"], "tracked-changes")
        self.assertIn("Kim", msg)
        self.assertIn("Lee", msg)

    def test_comments_hidden_text_and_placeholders(self):
        path = self.docx(
            '<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>internal note</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Dear {{client</w:t></w:r><w:r><w:t>_name}}, TODO add date</w:t></w:r></w:p>',
            {"word/comments.xml": f'<?xml version="1.0"?><w:comments {W}><w:comment w:id="0" w:author="Ana"><w:p/></w:comment></w:comments>'})
        rep = oi.inspect(path)
        self.assertEqual(self.codes(rep), ["comments", "hidden-text", "placeholder", "placeholder"])
        joined = " ".join(a["message"] for a in rep.attention)
        self.assertIn("{{client_name}}", joined)  # found even though split across runs
        self.assertIn("TODO", joined)

    def test_headers_are_scanned_too(self):
        path = self.docx('<w:p/>', {"word/header1.xml": f'<?xml version="1.0"?><w:hdr {W}><w:p><w:r><w:t>[[LOGO]]</w:t></w:r></w:p></w:hdr>'})
        rep = oi.inspect(path)
        self.assertEqual(self.codes(rep), ["placeholder"])

    def test_external_and_macro_flags(self):
        path = self.docx('<w:p/>', {
            "word/_rels/document.xml.rels": rels(("rId1", "hyperlink", "https://example.com", True),
                                                 ("rId2", "hyperlink", "file:///C:/secret/plan.xlsx", True),
                                                 ("rId3", "attachedTemplate", "file:///templates/x.dotm", True)),
            "word/vbaProject.bin": b"\x00",
        })
        rep = oi.inspect(path)
        self.assertEqual(self.codes(rep), ["external-reference", "local-link", "macros"])
        self.assertEqual(rep.facts["external_hyperlinks"], 2)

    def test_doctype_is_refused(self):
        path = self.docx('<w:p/>')
        with zipfile.ZipFile(path, "a") as zf:
            zf.writestr("word/comments.xml", '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>')
        with self.assertRaises(oi.InspectError):
            oi.inspect(path)


class ExcelTests(Fixture):
    def xlsx(self, sheet_xml, hidden=False, extra=None):
        state = ' state="hidden"' if hidden else ""
        parts = {
            "xl/workbook.xml": f'<?xml version="1.0"?><workbook {S}><sheets>'
                               f'<sheet name="Data" sheetId="1" r:id="rId1"/>'
                               f'<sheet name="Internal" sheetId="2" r:id="rId2"{state}/></sheets>'
                               f'<definedNames><definedName name="Old">#REF!</definedName></definedNames></workbook>',
            "xl/_rels/workbook.xml.rels": rels(("rId1", "worksheet", "worksheets/sheet1.xml", False),
                                               ("rId2", "worksheet", "worksheets/sheet2.xml", False)),
            "xl/worksheets/sheet1.xml": f'<?xml version="1.0"?><worksheet {S}><sheetData>{sheet_xml}</sheetData></worksheet>',
            "xl/worksheets/sheet2.xml": f'<?xml version="1.0"?><worksheet {S}><sheetData/></worksheet>',
            "xl/sharedStrings.xml": f'<?xml version="1.0"?><sst {S}><si><t>Region</t></si><si><t>Lorem ipsum</t></si></sst>',
        }
        parts.update(extra or {})
        return self.make("book.xlsx", parts)

    def test_formulas_without_cache_errors_hidden_and_names(self):
        rows = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                '<row r="2"><c r="A2"><v>3</v></c><c r="B2"><f>A2*2</f><v>6</v></c>'
                '<c r="C2"><f>A2/0</f></c><c r="D2" t="e"><f>A2/0</f><v>#DIV/0!</v></c></row>')
        rep = oi.inspect(self.xlsx(rows, hidden=True))
        self.assertEqual(self.codes(rep), ["broken-names", "formula-errors", "hidden-sheet", "no-cached-values", "placeholder"])
        self.assertEqual(rep.facts["formulas"], 3)
        msgs = {a["code"]: a["message"] for a in rep.attention}
        self.assertIn("Data!C2", msgs["no-cached-values"])
        self.assertIn("Data!D2=#DIV/0!", msgs["formula-errors"])
        self.assertEqual(rep.facts["sheets"][1]["state"], "hidden")

    def test_external_workbook_links(self):
        rep = oi.inspect(self.xlsx('<row r="1"><c r="A1"><v>1</v></c></row>',
                                   extra={"xl/externalLinks/externalLink1.xml": "<x/>"}))
        self.assertIn("external-workbooks", self.codes(rep))


class PowerPointTests(Fixture):
    def pptx(self, shapes, show=True, notes=False):
        slide_rels = [("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml", False)]
        if notes:
            slide_rels.append(("rId2", "notesSlide", "../notesSlides/notesSlide1.xml", False))
        show_attr = "" if show else ' show="0"'
        return self.make("deck.pptx", {
            "ppt/presentation.xml": f'<?xml version="1.0"?><p:presentation {P}><p:sldIdLst><p:sldId id="256" r:id="rId7"/></p:sldIdLst>'
                                    f'<p:sldSz cx="12192000" cy="6858000"/></p:presentation>',
            "ppt/_rels/presentation.xml.rels": rels(("rId7", "slide", "slides/slide1.xml", False)),
            "ppt/slides/slide1.xml": f'<?xml version="1.0"?><p:sld {P}{show_attr}><p:cSld><p:spTree>{shapes}</p:spTree></p:cSld></p:sld>',
            "ppt/slides/_rels/slide1.xml.rels": rels(*slide_rels),
        })

    @staticmethod
    def shape(name, x, y, cx, cy, text="", ph=None):
        ph_xml = f'<p:ph type="{ph}"/>' if ph else ""
        body = f'<p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody>' if text else '<p:txBody><a:p/></p:txBody>'
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="2" name="{name}"/><p:cNvSpPr/><p:nvPr>{ph_xml}</p:nvPr></p:nvSpPr>'
                f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm></p:spPr>{body}</p:sp>')

    def test_clean_slide(self):
        rep = oi.inspect(self.pptx(self.shape("Title 1", 100, 100, 5000000, 800000, "Plan", ph="title"), notes=True))
        self.assertEqual(rep.attention, [])
        self.assertEqual(rep.facts["slide_count"], 1)
        self.assertEqual(rep.facts["slides"][0]["title"], "Plan")
        self.assertTrue(rep.facts["slides"][0]["notes"])
        self.assertEqual(rep.facts["slide_size_in"], "13.33 x 7.50")

    def test_off_slide_empty_placeholder_and_hidden(self):
        shapes = (self.shape("Title 1", 0, 0, 5000000, 800000, "", ph="title")
                  + self.shape("Wide box", 9000000, 1000000, 4000000, 1000000, "Overflows {{x}}"))
        rep = oi.inspect(self.pptx(shapes, show=False))
        self.assertEqual(self.codes(rep), ["empty-placeholder", "off-slide", "placeholder"])
        self.assertIn("Wide box", next(a["message"] for a in rep.attention if a["code"] == "off-slide"))
        self.assertIn("hidden-slides", [i["code"] for i in rep.info])


class CliTests(Fixture):
    def test_not_a_zip_exits_2(self):
        path = os.path.join(self.tmp.name, "fake.docx")
        with open(path, "w") as fh:
            fh.write("not a zip")
        code, out = self.run_cli(path)
        self.assertEqual(code, 2)
        self.assertIn("ERROR", out)

    def test_unsupported_extension_exits_2(self):
        path = os.path.join(self.tmp.name, "a.pdf")
        open(path, "wb").close()
        self.assertEqual(self.run_cli(path)[0], 2)

    def test_fail_on_attention_and_json_is_deterministic(self):
        path = self.make("d.docx", {"word/document.xml": f'<?xml version="1.0"?><w:document {W}><w:body><w:p><w:r><w:t>TBD</w:t></w:r></w:p></w:body></w:document>'})
        self.assertEqual(self.run_cli(path)[0], 0)
        self.assertEqual(self.run_cli("--fail-on", "attention", path)[0], 1)
        code1, out1 = self.run_cli("--json", path)
        code2, out2 = self.run_cli("--json", path)
        self.assertEqual(out1, out2)
        data = json.loads(out1)
        self.assertEqual(data["files"][0]["attention"][0]["code"], "placeholder")

    def test_file_is_not_modified(self):
        path = self.make("d.docx", {"word/document.xml": f'<?xml version="1.0"?><w:document {W}><w:body><w:p/></w:body></w:document>'})
        def content():
            with open(path, "rb") as fh:
                return fh.read()
        before = content()
        self.run_cli(path)
        self.assertEqual(content(), before)


if __name__ == "__main__":
    unittest.main()
