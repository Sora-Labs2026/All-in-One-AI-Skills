"""Offline tests for hl7v2_check.py. Synthetic messages only: no real patients, no network."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hl7v2_check.py"
spec = importlib.util.spec_from_file_location("hl7v2_check", SCRIPT)
hc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hc
spec.loader.exec_module(hc)

# Synthetic, clearly fake values. SYNTH markers let tests prove nothing is echoed.
GOOD_ORU = "\r".join([
    "MSH|^~\\&|LAB|SYNTHFAC|EHR|SYNTHFAC|20250301101500-0500||ORU^R01^ORU_R01|SYNTHCTRL1|P|2.5.1",
    "PID|1||SYNTHMRN001^^^SYNTHFAC^MR||SYNTHFAMILY^SYNTHGIVEN||19800101|F",
    "OBR|1||SYNTHACC1|4548-4^HbA1c^LN|||20250301090000-0500",
    "OBX|1|NM|4548-4^HbA1c^LN||6.1|%|4.0-5.6|H|||F|||20250301093000-0500",
    "OBX|2|TX|8251-1^Note^LN||first line\\.br\\second line||||||F",
]) + "\r"


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hc.main(argv)
    return code, out.getvalue(), err.getvalue()


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def file(self, text, name="feed.hl7", raw=None):
        path = self.dir / name
        path.write_bytes(raw if raw is not None else text.encode("utf-8"))
        return str(path)

    def rules(self, text, **kw):
        report = hc.check_inputs([Path(self.file(text, **kw))])
        return {f["rule"] for f in report["findings"]}, report


class CleanMessages(Case):
    def test_clean_message_exit_0(self):
        code, out, _ = run([self.file(GOOD_ORU)])
        self.assertEqual(code, 0, out)
        self.assertIn("ORU^R01 x1", out)
        self.assertIn("2.5.1 x1", out)

    def test_mllp_framing_is_stripped(self):
        framed = b"\x0b" + GOOD_ORU.encode() + b"\x1c\r"
        rules, report = self.rules("", raw=framed)
        self.assertEqual(report["summary"]["messages"], 1)
        self.assertFalse({r for r in rules if hc.RULES[r] == "error"})

    def test_never_prints_values(self):
        bad = GOOD_ORU.replace("|6.1|", "|SYNTHVALUE|")
        for argv in ([], ["--json"]):
            _, out, _ = run([self.file(bad), *argv])
            self.assertNotIn("SYNTH", out)


class Errors(Case):
    def test_missing_msh_first(self):
        rules, _ = self.rules("PID|1||X\rMSH|^~\\&|A|B|C|D|20250101||ADT^A01|1|P|2.5\r")
        self.assertIn("MSH-FIRST", rules)

    def test_bad_encoding_chars(self):
        rules, _ = self.rules("MSH|^^\\&|A|B|C|D|20250101||ADT^A01|1|P|2.5\r")
        self.assertIn("ENCODING-CHARS", rules)

    def test_required_msh_fields(self):
        rules, _ = self.rules("MSH|^~\\&|A|B|C|D|20250101||||P|\r")
        self.assertIn("MSH-REQUIRED", rules)

    def test_timestamp_format_and_offset(self):
        rules, _ = self.rules(GOOD_ORU.replace("20250301101500-0500", "2025-03-01"))
        self.assertIn("TS-FORMAT", rules)
        rules, _ = self.rules(GOOD_ORU.replace("20250301101500-0500", "20250301101500"))
        self.assertIn("TS-NO-OFFSET", rules)

    def test_obx_numeric_value_type_and_units(self):
        text = GOOD_ORU.replace("|6.1|%|", "|high|%|")
        rules, _ = self.rules(text)
        self.assertIn("OBX-NM-NUMERIC", rules)
        rules, _ = self.rules(GOOD_ORU.replace("|6.1|%|", "|6.1||"))
        self.assertIn("OBX-UNITS", rules)
        rules, _ = self.rules(GOOD_ORU.replace("OBX|1|NM|", "OBX|1||"))
        self.assertIn("OBX-VALUE-TYPE", rules)

    def test_segment_id(self):
        rules, _ = self.rules(GOOD_ORU + "obx|3|NM\r")
        self.assertIn("SEGMENT-ID", rules)

    def test_exit_codes(self):
        code, _, _ = run([self.file(GOOD_ORU.replace("|6.1|", "|abc|"))])
        self.assertEqual(code, 1)
        warn_only = GOOD_ORU.replace("|||F|||2025", "||||||2025")
        code, _, _ = run([self.file(warn_only)])
        self.assertEqual(code, 0)
        code, _, _ = run([self.file(warn_only), "--strict"])
        self.assertEqual(code, 1)


class Warnings(Case):
    def test_duplicate_control_ids_and_mixed_processing(self):
        second = GOOD_ORU.replace("|P|2.5.1", "|T|2.5.1")
        rules, _ = self.rules(GOOD_ORU + second)
        self.assertIn("CONTROL-ID-DUP", rules)
        self.assertIn("PROCESSING-MIXED", rules)

    def test_pid_missing_and_authority(self):
        rules, _ = self.rules("MSH|^~\\&|A|B|C|D|20250101||ADT^A01|1|P|2.5\rEVN|A01|20250101\r")
        self.assertIn("PID-MISSING", rules)
        rules, _ = self.rules(GOOD_ORU.replace("SYNTHMRN001^^^SYNTHFAC^MR", "SYNTHMRN001"))
        self.assertIn("PID3-AUTHORITY", rules)

    def test_escape_sequences(self):
        rules, _ = self.rules(GOOD_ORU.replace("\\.br\\", "\\Q\\"))
        self.assertIn("ESCAPE-SEQUENCE", rules)
        rules, _ = self.rules(GOOD_ORU.replace("\\.br\\", "\\F\\"))
        self.assertNotIn("ESCAPE-SEQUENCE", rules)

    def test_lf_terminators_and_charset(self):
        rules, _ = self.rules(GOOD_ORU.replace("\r", "\n"))
        self.assertIn("LF-TERMINATORS", rules)
        rules, _ = self.rules(GOOD_ORU.replace("SYNTHGIVEN", "SYNTHGIVÉN"))
        self.assertIn("NON-ASCII-NO-CHARSET", rules)

    def test_z_segments_counted_once(self):
        rules, report = self.rules(GOOD_ORU + "ZX1|a\rZX2|b\r")
        z = [f for f in report["findings"] if f["rule"] == "Z-SEGMENT"]
        self.assertEqual(len(z), 1)
        self.assertEqual(z[0]["count"], 2)


class Cli(Case):
    def test_usage_errors(self):
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run([str(self.dir / "missing.hl7")])[0], 2)
        self.assertEqual(run([self.file("not hl7 at all\n")])[0], 1)
        self.assertEqual(run([self.file("\n\n")])[0], 2)

    def test_json_and_list_rules(self):
        code, out, _ = run([self.file(GOOD_ORU), "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["summary"]["messages"], 1)
        code, out, _ = run(["--list-rules"])
        self.assertEqual(code, 0)
        self.assertIn("OBX-NM-NUMERIC", out)


if __name__ == "__main__":
    unittest.main()
