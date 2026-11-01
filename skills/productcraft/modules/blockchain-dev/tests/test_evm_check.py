"""Offline tests for evm_check.py. Published test vectors and synthetic files only: no network, no keys."""
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evm_check.py"
spec = importlib.util.spec_from_file_location("evm_check", SCRIPT)
ec = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ec
spec.loader.exec_module(ec)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ec.main(argv)
    return code, out.getvalue(), err.getvalue()


class KeccakTests(unittest.TestCase):
    def test_empty_and_abc_vectors(self):
        self.assertEqual(ec.keccak256(b"").hex(), "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(ec.keccak256(b"abc").hex(), "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45")

    def test_sponge_matches_hashlib_sha3_across_block_boundaries(self):
        for n in (0, 1, 55, 135, 136, 137, 271, 272, 273, 500):
            data = bytes((i * 7) % 256 for i in range(n))
            self.assertEqual(ec.sha3_256_reference(data), hashlib.sha3_256(data).digest(), n)

    def test_keccak_differs_from_sha3(self):
        self.assertNotEqual(ec.keccak256(b"hello"), hashlib.sha3_256(b"hello").digest())

    def test_hash_command_identifies_digest(self):
        code, out, _ = run(["hash", "", "--expect", "0xa7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["expect_matches"], "sha3_256_fips")

    def test_hash_hex_input(self):
        code, out, _ = run(["hash", "0x616263", "--hex"])
        self.assertEqual(code, 0)
        self.assertIn("4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45", out)

    def test_hash_bad_hex_is_usage_error(self):
        code, _, err = run(["hash", "0xabc", "--hex"])
        self.assertEqual(code, 2)
        self.assertIn("even number", err)


class SignatureTests(unittest.TestCase):
    def test_known_selectors(self):
        cases = {
            "transfer(address,uint256)": "0xa9059cbb",
            "balanceOf(address)": "0x70a08231",
            "approve(address,uint256)": "0x095ea7b3",
            "transferFrom(address,address,uint256)": "0x23b872dd",
            "totalSupply()": "0x18160ddd",
            "Error(string)": "0x08c379a0",
            "Panic(uint256)": "0x4e487b71",
        }
        code, out, _ = run(["selector", *cases, "--json"])
        self.assertEqual(code, 0)
        got = {row["canonical"]: row["selector"] for row in json.loads(out)}
        self.assertEqual(got, cases)

    def test_canonicalization(self):
        self.assertEqual(ec.canonical_signature("function approve(address spender, uint amount) external returns (bool)"), "approve(address,uint256)")
        self.assertEqual(ec.canonical_signature("f(uint[] memory xs, (address a, int b)[2] calldata ps)"), "f(uint256[],(address,int256)[2])")
        self.assertEqual(ec.canonical_signature("g(address payable to)"), "g(address)")

    def test_event_topics(self):
        code, out, _ = run(["topic", "event Transfer(address indexed from, address indexed to, uint256 value)", "Approval(address,address,uint256)"])
        self.assertEqual(code, 0)
        self.assertIn("0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", out)
        self.assertIn("0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925", out)

    def test_malformed_signature(self):
        code, _, _ = run(["selector", "transfer(address,uint256"])
        self.assertEqual(code, 2)


class ChecksumTests(unittest.TestCase):
    VALID = [
        "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
        "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
        "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
        "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
        "0x52908400098527886E0F7030069857D2E4169EE7",
        "0xde709f2102306220921060314715629080e2fb77",
    ]

    def test_eip55_vectors_are_valid(self):
        for addr in self.VALID:
            self.assertEqual(ec.check_address(addr)["status"], "valid", addr)

    def test_lowercase_is_unchecked(self):
        result = ec.check_address(self.VALID[0].lower())
        self.assertEqual(result["status"], "unchecked")
        self.assertEqual(result["checksummed"], self.VALID[0])

    def test_wrong_case_is_invalid_and_exit_1(self):
        bad = self.VALID[0][:-1] + "D"
        code, out, _ = run(["checksum", bad])
        self.assertEqual(code, 1)
        self.assertIn("invalid", out)

    def test_malformed_exit_2(self):
        code, _, _ = run(["checksum", "0x1234"])
        self.assertEqual(code, 2)


class UnitsTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(ec.to_base("1.5", 6), 1_500_000)
        self.assertEqual(ec.to_display("1500000", 6), "1.5")
        self.assertEqual(ec.to_base("1", 18), 10**18)
        self.assertEqual(ec.to_display("1", 18), "0.000000000000000001")
        self.assertEqual(ec.to_base("2.50", 1), 25)

    def test_excess_precision_refused(self):
        code, _, err = run(["units", "0.1234567", "--decimals", "6"])
        self.assertEqual(code, 1)
        self.assertIn("refusing to round", err)

    def test_exponent_and_sign_are_usage_errors(self):
        for amount in ("1e18", "-1", "1,5", ""):
            code, _, _ = run(["units", amount, "--decimals", "18"])
            self.assertEqual(code, 2, amount)

    def test_uint256_overflow(self):
        code, _, _ = run(["units", str(2**256), "--decimals", "0"])
        self.assertEqual(code, 1)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def rules(self):
        return [(d["rule"], d["file"], d["line"]) for d in ec.scan(self.root)]

    def test_js_rules(self):
        self.write("src/a.ts", "const h = createHash('sha3-256');\nconst v = parseFloat(formatUnits(balance, 18));\nconst s = 1e18;\nconst ok = 10n ** 18n;\nconst d = 10 ** decimals;\n")
        found = self.rules()
        self.assertIn(("NODE-SHA3", "src/a.ts", 1), found)
        self.assertIn(("JS-FLOAT-AMOUNT", "src/a.ts", 2), found)
        self.assertIn(("JS-FLOAT-SCALE", "src/a.ts", 3), found)
        self.assertIn(("JS-FLOAT-SCALE", "src/a.ts", 5), found)
        self.assertNotIn(("JS-FLOAT-SCALE", "src/a.ts", 4), found)

    def test_python_sha3_needs_ethereum_context(self):
        self.write("plain.py", "import hashlib\nd = hashlib.sha3_256(b'x')\n")
        self.write("eth.py", "from web3 import Web3\nimport hashlib\nd = hashlib.sha3_256(b'x')\nusd = float(balance) / 1e18\n")
        found = self.rules()
        self.assertIn(("PY-SHA3", "eth.py", 3), found)
        self.assertIn(("PY-FLOAT-AMOUNT", "eth.py", 4), found)
        self.assertFalse([r for r in found if r[1] == "plain.py"])

    def test_ignore_comment_skipped_dirs_and_comments(self):
        self.write("src/b.js", "// evm-check: ignore JS-FLOAT-SCALE reviewed\nconst x = Math.pow(10, 6);\n// createHash('sha3-256') in a comment\n")
        self.write("node_modules/dep/index.js", "createHash('sha3-256')\n")
        self.assertEqual(self.rules(), [])

    def test_fail_on_threshold_and_json(self):
        self.write("cfg.ts", "export const decimals = 6;\n")
        code, out, _ = run(["scan", "--root", str(self.root), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["counts"]["low"], 1)
        code, _, _ = run(["scan", "--root", str(self.root), "--fail-on", "low"])
        self.assertEqual(code, 1)

    def test_output_never_contains_source_text(self):
        self.write("leak.ts", "const secretish = parseFloat(balanceOfTreasury); // marker-text-xyz\n")
        _, out, _ = run(["scan", "--root", str(self.root)])
        self.assertNotIn("marker-text-xyz", out)

    def test_missing_root_is_usage_error(self):
        code, _, _ = run(["scan", "--root", str(self.root / "nope")])
        self.assertEqual(code, 2)


class CliTests(unittest.TestCase):
    def test_help_and_list_rules(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Keccak-256", out)
        code, out, _ = run(["list-rules", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(set(json.loads(out)), set(ec.RULES))

    def test_no_command_is_usage_error(self):
        code, _, _ = run([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
