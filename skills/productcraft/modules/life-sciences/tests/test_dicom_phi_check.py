"""Tests for dicom_phi_check.py. Standard library only; every DICOM file is synthetic and built here."""

import contextlib
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
SCRIPT = os.path.join(SCRIPTS, "dicom_phi_check.py")
sys.path.insert(0, SCRIPTS)

import dicom_phi_check as dpc  # noqa: E402

IMPLICIT_LE = "1.2.840.10008.1.2"
EXPLICIT_LE = "1.2.840.10008.1.2.1"
DEFLATED_LE = "1.2.840.10008.1.2.1.99"
EXPLICIT_BE = "1.2.840.10008.1.2.2"
JPEG_BASELINE = "1.2.840.10008.1.2.4.50"
CT_STORAGE = "1.2.840.10008.5.1.4.1.1.2"
LONG = {"OB", "OD", "OF", "OL", "OV", "OW", "SQ", "SV", "UC", "UN", "UR", "UT", "UV"}
UNDEF = 0xFFFFFFFF


def _fmt(little):
    return "<" if little else ">"


def pad(value, vr):
    if len(value) % 2:
        value += b"\x00" if vr in ("UI", "OB", "UN", "OW") else b" "
    return value


def el(group, elem, vr, value, explicit=True, little=True, undefined=False):
    """Encode one data element. Sequences pass already-encoded item bytes as value."""
    e = _fmt(little)
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not undefined and vr != "SQ":
        value = pad(value, vr)
    length = UNDEF if undefined else len(value)
    tag = struct.pack(e + "HH", group, elem)
    if explicit:
        if vr in LONG:
            return tag + vr.encode("ascii") + b"\x00\x00" + struct.pack(e + "I", length) + value
        return tag + vr.encode("ascii") + struct.pack(e + "H", length) + value
    return tag + struct.pack(e + "I", length) + value


def item(content, little=True, undefined=False):
    e = _fmt(little)
    if undefined:
        return struct.pack(e + "HHI", 0xFFFE, 0xE000, UNDEF) + content + struct.pack(e + "HHI", 0xFFFE, 0xE00D, 0)
    return struct.pack(e + "HHI", 0xFFFE, 0xE000, len(content)) + content


def seq(group, elem, items, explicit=True, little=True, undefined=True, vr="SQ"):
    body = b"".join(items)
    if undefined:
        body += struct.pack(_fmt(little) + "HHI", 0xFFFE, 0xE0DD, 0)
    return el(group, elem, vr, body, explicit, little, undefined)


def meta(ts):
    body = (el(0x0002, 0x0001, "OB", b"\x00\x01")
            + el(0x0002, 0x0002, "UI", CT_STORAGE)
            + el(0x0002, 0x0003, "UI", "2.25.1001")
            + el(0x0002, 0x0010, "UI", ts)
            + el(0x0002, 0x0012, "UI", "1.2.826.0.1.3680043.9.9999"))
    return el(0x0002, 0x0000, "UL", struct.pack("<I", len(body))) + body


def part10(dataset, ts=EXPLICIT_LE):
    return b"\x00" * 128 + b"DICM" + meta(ts) + dataset


def clean_dataset(explicit=True, little=True, extra=b"", modality="CT"):
    """A de-identified-looking dataset; extra elements are inserted in tag order by the caller."""
    k = dict(explicit=explicit, little=little)
    return (el(0x0008, 0x0016, "UI", CT_STORAGE, **k)
            + el(0x0008, 0x0018, "UI", "2.25.1001", **k)
            + el(0x0008, 0x0060, "CS", modality, **k)
            + el(0x0010, 0x0010, "PN", "", **k)
            + el(0x0010, 0x0020, "LO", "", **k)
            + el(0x0012, 0x0062, "CS", "YES", **k)
            + el(0x0012, 0x0063, "LO", "PS3.15 Basic Profile", **k)
            + el(0x0020, 0x000D, "UI", "2.25.2002", **k)
            + extra)


def run(args):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = dpc.main(list(args))
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def findings(self, path, *extra):
        code, out, _ = run(["--json", path] + list(extra))
        doc = json.loads(out)
        flat = [f for entry in doc["files"] for f in entry["findings"]]
        return code, doc, flat

    def keywords(self, flat, severity=None):
        return {f["keyword"] for f in flat if severity is None or f["severity"] == severity}


class CleanAndIdentifiers(Base):
    def test_clean_file_passes_even_strict(self):
        path = self.write("clean.dcm", part10(clean_dataset()))
        code, out, _ = run(["--strict", path])
        self.assertEqual(code, 0, out)
        self.assertIn("Result: PASS", out)
        self.assertIn("Header check only", out)

    def test_identifiers_are_high_and_values_hidden(self):
        ds = (el(0x0008, 0x0060, "CS", "CT")
              + el(0x0010, 0x0010, "PN", "Doe^Jane")
              + el(0x0010, 0x0020, "LO", "MRN12345")
              + el(0x0010, 0x0030, "DA", "19700101"))
        path = self.write("phi.dcm", part10(ds))
        code, out, _ = run([path])
        self.assertEqual(code, 1)
        for kw in ("PatientName", "PatientID", "PatientBirthDate", "PatientIdentityRemoved"):
            self.assertIn(kw, out)
        self.assertNotIn("Doe", out)
        self.assertNotIn("MRN12345", out)
        self.assertNotIn("19700101", out)

    def test_show_values_reveals_values_on_request(self):
        path = self.write("phi.dcm", part10(el(0x0010, 0x0010, "PN", "Doe^Jane")))
        _, _, flat = self.findings(path, "--show-values")
        values = [f.get("value") for f in flat if f["keyword"] == "PatientName"]
        self.assertEqual(values, ["Doe^Jane"])

    def test_empty_person_name_components_count_as_empty(self):
        ds = clean_dataset(extra=el(0x0040, 0xA123, "PN", "^^^"))
        path = self.write("pn.dcm", part10(ds))
        code, _, flat = self.findings(path)
        self.assertEqual(code, 0)
        self.assertNotIn("PersonName", self.keywords(flat))

    def test_staff_site_and_free_text_are_warn(self):
        ds = (el(0x0008, 0x0080, "LO", "General Hospital")
              + el(0x0008, 0x0090, "PN", "Smith^Ann")
              + el(0x0008, 0x1030, "LO", "CT HEAD for J. Doe")
              + el(0x0012, 0x0062, "CS", "YES"))
        path = self.write("warn.dcm", part10(ds))
        code, _, flat = self.findings(path)
        self.assertEqual(code, 0)  # WARN only
        cats = {f["keyword"]: f["category"] for f in flat if f["severity"] == "WARN"}
        self.assertEqual(cats["InstitutionName"], "site")
        self.assertEqual(cats["ReferringPhysicianName"], "staff")
        self.assertEqual(cats["StudyDescription"], "free-text")
        code_strict, _, _ = run(["--strict", path])
        self.assertEqual(code_strict, 1)

    def test_long_value_counts_as_present(self):
        ds = clean_dataset(extra=el(0x0040, 0xA160, "UT", "x" * 70000))
        path = self.write("long.dcm", part10(ds))
        _, _, flat = self.findings(path)
        self.assertIn("TextValue", self.keywords(flat, "WARN"))


class Encodings(Base):
    def test_nested_sequences_with_undefined_lengths(self):
        request = item(el(0x0008, 0x0050, "SH", "ACC123"), undefined=True)
        other_ids = item(el(0x0010, 0x0020, "LO", "OLD-42"))
        ds = (el(0x0008, 0x0060, "CS", "CT")
              + seq(0x0010, 0x1002, [other_ids], undefined=False)
              + el(0x0012, 0x0062, "CS", "YES")
              + seq(0x0040, 0x0275, [request], undefined=True))
        path = self.write("nested.dcm", part10(ds))
        code, _, flat = self.findings(path)
        self.assertEqual(code, 1)
        paths = {f["path"] for f in flat if f["severity"] == "HIGH"}
        self.assertIn("RequestAttributesSequence[0].AccessionNumber", paths)
        self.assertIn("OtherPatientIDsSequence[0].PatientID", paths)
        self.assertIn("OtherPatientIDsSequence", paths)

    def test_implicit_vr_little_endian(self):
        k = dict(explicit=False)
        inner = item(el(0x0010, 0x0020, "LO", "OLD-1", **k))
        ds = (el(0x0008, 0x0020, "DA", "20240115", **k)
              + el(0x0008, 0x0060, "CS", "MR", **k)
              + el(0x0010, 0x0010, "PN", "Roe^Rick", **k)
              + seq(0x0010, 0x1002, [inner], undefined=False, **k)
              + el(0x0012, 0x0062, "CS", "YES", **k))
        path = self.write("implicit.dcm", part10(ds, IMPLICIT_LE))
        code, _, flat = self.findings(path)
        self.assertEqual(code, 1)
        self.assertIn("PatientName", self.keywords(flat, "HIGH"))
        self.assertIn("OtherPatientIDsSequence[0].PatientID", {f["path"] for f in flat})
        self.assertIn("StudyDate", self.keywords(flat, "WARN"))

    def test_implicit_unknown_sequence_detected_by_item_tag(self):
        k = dict(explicit=False)
        inner = item(el(0x0040, 0xA123, "PN", "Observer^One", **k))
        ds = clean_dataset(**k) + seq(0x0040, 0xA375, [inner], undefined=False, **k)
        path = self.write("unknownsq.dcm", part10(ds, IMPLICIT_LE))
        _, _, flat = self.findings(path)
        self.assertIn("(0040,A375)[0].PersonName", {f["path"] for f in flat if f["severity"] == "HIGH"})

    def test_explicit_big_endian(self):
        k = dict(little=False)
        ds = (el(0x0008, 0x0060, "CS", "CT", **k)
              + el(0x0010, 0x0010, "PN", "Big^Endian", **k)
              + seq(0x0040, 0x0275, [item(el(0x0008, 0x0050, "SH", "A1", **k), little=False, undefined=True)],
                    undefined=True, **k)
              + el(0x7FE0, 0x0010, "OW", b"\x00\x01" * 8, **k))
        path = self.write("be.dcm", part10(ds, EXPLICIT_BE))
        code, _, flat = self.findings(path)
        self.assertEqual(code, 1)
        self.assertIn("PatientName", self.keywords(flat, "HIGH"))
        self.assertIn("RequestAttributesSequence[0].AccessionNumber", {f["path"] for f in flat})

    def test_deflated_dataset(self):
        ds = el(0x0008, 0x0060, "CS", "CT") + el(0x0010, 0x0010, "PN", "Deflate^Me")
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        packed = comp.compress(ds) + comp.flush()
        path = self.write("deflated.dcm", part10(packed, DEFLATED_LE))
        code, _, flat = self.findings(path)
        self.assertEqual(code, 1)
        self.assertIn("PatientName", self.keywords(flat, "HIGH"))

    def test_deflate_limit(self):
        ds = el(0x0010, 0x0010, "PN", "A^B") + el(0x0011, 0x0010, "LO", "BIG") + el(0x0011, 0x1001, "OB", b"\x00" * (3 * 1024 * 1024))
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        path = self.write("bomb.dcm", part10(comp.compress(ds) + comp.flush(), DEFLATED_LE))
        code, out, _ = run(["--max-inflate", "1", path])
        self.assertEqual(code, 2)
        self.assertIn("--max-inflate", out)

    def test_encapsulated_pixel_data_then_private_group(self):
        frags = item(b"") + item(b"\xff\xd8\xff\xd9") + item(b"\x01\x02\x03\x04")
        pixel = el(0x7FE0, 0x0010, "OB", frags + struct.pack("<HHI", 0xFFFE, 0xE0DD, 0), undefined=True)
        private = el(0x7FE1, 0x0010, "LO", "VENDOR X") + el(0x7FE1, 0x1001, "OB", b"\x00\x00")
        path = self.write("jpeg.dcm", part10(clean_dataset() + pixel + private, JPEG_BASELINE))
        code, _, flat = self.findings(path)
        self.assertEqual(code, 0)
        priv = [f for f in flat if f["category"] == "private"]
        self.assertEqual(len(priv), 1)
        self.assertEqual(priv[0]["tag"], "(7FE1,xxxx)")
        self.assertIn("2 private element(s)", priv[0]["message"])

    def test_un_with_undefined_length_is_read_as_implicit_sequence(self):
        inner = item(el(0x0040, 0xA123, "PN", "Hidden^Name", explicit=False), undefined=True)
        ds = clean_dataset() + seq(0x0040, 0xA730, [inner], undefined=True, vr="UN")
        path = self.write("un.dcm", part10(ds))
        _, _, flat = self.findings(path)
        self.assertIn("ContentSequence[0].PersonName", {f["path"] for f in flat if f["severity"] == "HIGH"})

    def test_raw_dataset_needs_force(self):
        raw = el(0x0008, 0x0060, "CS", "CT", explicit=False) + el(0x0010, 0x0010, "PN", "Raw^Data", explicit=False)
        path = self.write("raw.dcm", raw + b"\x00" * 200)
        code, out, _ = run([path])
        self.assertEqual(code, 2)
        self.assertIn("no DICOM Part 10 files found", out)

    def test_raw_dataset_with_force(self):
        raw = el(0x0008, 0x0060, "CS", "CT", explicit=False) + el(0x0010, 0x0010, "PN", "Raw^Data", explicit=False)
        path = self.write("raw.dcm", raw)
        code, _, flat = self.findings(path, "--force")
        self.assertEqual(code, 1)
        self.assertIn("PatientName", self.keywords(flat, "HIGH"))


class Checks(Base):
    def test_age_over_89(self):
        ds_old = (el(0x0008, 0x0060, "CS", "CT") + el(0x0010, 0x1010, "AS", "092Y") + el(0x0012, 0x0062, "CS", "YES"))
        ds_young = (el(0x0008, 0x0060, "CS", "CT") + el(0x0010, 0x1010, "AS", "045Y") + el(0x0012, 0x0062, "CS", "YES"))
        old = self.write("old.dcm", part10(ds_old))
        young = self.write("young.dcm", part10(ds_young))
        code, _, flat = self.findings(old)
        self.assertEqual(code, 1)
        self.assertIn("age", {f["category"] for f in flat if f["severity"] == "HIGH"})
        code, _, flat = self.findings(young)
        self.assertEqual(code, 0)
        self.assertNotIn("age", {f["category"] for f in flat})

    def test_burned_in_annotation(self):
        us = self.write("us.dcm", part10(clean_dataset(modality="US")))
        _, _, flat = self.findings(us)
        self.assertIn("BurnedInAnnotation", self.keywords(flat, "WARN"))
        yes = self.write("us_yes.dcm", part10(clean_dataset(modality="US", extra=el(0x0028, 0x0301, "CS", "YES"))))
        code, _, flat = self.findings(yes)
        self.assertEqual(code, 1)
        self.assertIn("BurnedInAnnotation", self.keywords(flat, "HIGH"))
        no = self.write("us_no.dcm", part10(clean_dataset(modality="US", extra=el(0x0028, 0x0301, "CS", "NO"))))
        _, _, flat = self.findings(no)
        self.assertNotIn("BurnedInAnnotation", self.keywords(flat))

    def test_head_volume_overlay_and_embedded_document(self):
        ds = (el(0x0008, 0x0060, "CS", "CT")
              + el(0x0012, 0x0062, "CS", "YES")
              + el(0x0018, 0x0015, "CS", "HEAD")
              + el(0x0042, 0x0011, "OB", b"%PDF")
              + el(0x6000, 0x3000, "OW", b"\x00\x00"))
        path = self.write("head.dcm", part10(ds))
        _, _, flat = self.findings(path)
        self.assertTrue({"BodyPartExamined", "EncapsulatedDocument", "OverlayData"} <= self.keywords(flat, "WARN"))

    def test_uid_root(self):
        ds = clean_dataset(extra=el(0x0020, 0x000E, "UI", "1.2.3.4.5"))
        path = self.write("uid.dcm", part10(ds))
        _, _, flat = self.findings(path, "--uid-root", "2.25")
        uid_findings = [f for f in flat if f["category"] == "uid"]
        self.assertEqual([f["keyword"] for f in uid_findings], ["SeriesInstanceUID"])
        _, _, flat = self.findings(path)
        self.assertFalse([f for f in flat if f["category"] == "uid"])

    def test_private_tags_warn_then_allowed(self):
        ds = clean_dataset(extra=el(0x0029, 0x0010, "LO", "SIEMENS CSA HEADER") + el(0x0029, 0x1010, "OB", b"\x01\x02"))
        path = self.write("priv.dcm", part10(ds))
        code, _, _ = run(["--strict", path])
        self.assertEqual(code, 1)
        code, _, flat = self.findings(path, "--strict", "--allow-category", "private")
        self.assertEqual(code, 0)
        self.assertTrue(all(f["allowed"] for f in flat if f["category"] == "private"))

    def test_allow_pattern_and_allow_keyword(self):
        good = self.write("good.dcm", part10(clean_dataset().replace(
            el(0x0010, 0x0020, "LO", ""), el(0x0010, 0x0020, "LO", "SUBJ-0001"))))
        bad = self.write("bad.dcm", part10(clean_dataset().replace(
            el(0x0010, 0x0020, "LO", ""), el(0x0010, 0x0020, "LO", "MRN99"))))
        code, _, flat = self.findings(good, "--allow-pattern", "PatientID=SUBJ-[0-9]{4}")
        self.assertEqual(code, 0)
        self.assertIn("PatientID", self.keywords(flat, "INFO"))
        code, _, flat = self.findings(bad, "--allow-pattern", "PatientID=SUBJ-[0-9]{4}")
        self.assertEqual(code, 1)
        msg = [f["message"] for f in flat if f["keyword"] == "PatientID"][0]
        self.assertIn("does not match", msg)
        code, _, _ = self.findings(bad, "--allow", "PatientID")
        self.assertEqual(code, 0)

    def test_bad_allow_pattern_is_usage_error(self):
        path = self.write("x.dcm", part10(clean_dataset()))
        self.assertEqual(run(["--allow-pattern", "PatientID", path])[0], 2)
        self.assertEqual(run(["--allow-pattern", "PatientID=(", path])[0], 2)
        self.assertEqual(run(["--uid-root", "abc", path])[0], 2)


class Robustness(Base):
    def test_truncated_file_is_an_error(self):
        data = part10(clean_dataset(extra=el(0x0040, 0xA160, "UT", "y" * 400)))
        path = self.write("trunc.dcm", data[:-100])
        code, out, _ = run([path])
        self.assertEqual(code, 2)
        self.assertIn("ERROR", out)

    def test_deep_nesting_is_refused(self):
        inner = el(0x0010, 0x0010, "PN", "Deep^Name")
        for _ in range(40):
            inner = seq(0x0040, 0xA730, [item(inner, undefined=True)], undefined=True)
        path = self.write("deep.dcm", part10(inner))
        code, out, _ = run([path])
        self.assertEqual(code, 2)
        self.assertIn("nesting", out)

    def test_directory_scan_skips_other_files_and_aggregates(self):
        sub = os.path.join(self.dir, "series")
        os.makedirs(sub)
        for i in range(3):
            with open(os.path.join(sub, "IM%03d" % i), "wb") as fh:
                fh.write(part10(el(0x0010, 0x0010, "PN", "Same^Patient")))
        with open(os.path.join(sub, "notes.txt"), "w") as fh:
            fh.write("not a dicom file\n" * 20)
        code, out, _ = run([self.dir])
        self.assertEqual(code, 1)
        self.assertIn("3 file(s) scanned, 1 skipped", out)
        row = [line for line in out.splitlines() if "PatientName" in line][0]
        self.assertIn(" 3 ", row)
        code, doc, _ = self.findings(self.dir)
        self.assertEqual(doc["files_scanned"], 3)
        self.assertEqual(len(doc["files_skipped"]), 1)
        name_rows = [r for r in doc["summary"] if r["keyword"] == "PatientName"]
        self.assertEqual(name_rows[0]["files"], 3)

    def test_missing_path_is_an_error(self):
        code, out, _ = run([os.path.join(self.dir, "nope.dcm")])
        self.assertEqual(code, 2)

    def test_json_output_is_deterministic(self):
        path = self.write("phi.dcm", part10(el(0x0010, 0x0010, "PN", "Doe^Jane") + el(0x0029, 0x0010, "LO", "V")))
        first = run(["--json", path])[1]
        second = run(["--json", path])[1]
        self.assertEqual(first, second)
        doc = json.loads(first)
        self.assertEqual(doc["result"], "FAIL")
        self.assertNotIn("Doe", first)

    def test_file_is_not_modified(self):
        data = part10(el(0x0010, 0x0010, "PN", "Doe^Jane"))
        path = self.write("ro.dcm", data)
        run([path])
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), data)

    def test_cli_help_and_list_checks(self):
        res = subprocess.run([sys.executable, "-I", SCRIPT, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Exit codes", res.stdout)
        res = subprocess.run([sys.executable, "-I", SCRIPT, "--list-checks"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("(0010,0010)  PatientName", res.stdout)
        res = subprocess.run([sys.executable, "-I", SCRIPT], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)


if __name__ == "__main__":
    unittest.main()
