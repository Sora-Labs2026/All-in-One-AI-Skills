"""Offline tests for move_check.py. Synthetic packages only: no network, no CLI, no real keys."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "move_check.py"
spec = importlib.util.spec_from_file_location("move_check", SCRIPT)
mc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mc
spec.loader.exec_module(mc)

MOVE_TOML = """[package]
name = "demo"
version = "1.0.0"

[addresses]
demo = "_"

[dependencies.AptosFramework]
git = "https://github.com/aptos-labs/aptos-core.git"
rev = "{rev}"
subdir = "aptos-move/framework/aptos-framework"
"""


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mc.main(argv)
    return code, out.getvalue(), err.getvalue()


def fake_private_key() -> str:
    return "ed25519-priv-0x" + "5" * 64          # built at runtime; not a real key


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def package(self, source: str, rev: str = "0123abcd", tests: bool = True) -> None:
        write(self.root, "Move.toml", MOVE_TOML.format(rev=rev))
        write(self.root, "sources/demo.move", source)
        if tests:
            write(self.root, "tests/demo_tests.move",
                  "#[test_only]\nmodule demo::demo_tests {\n    #[test]\n    fun works() {}\n}\n")

    def leads(self, **kwargs):
        return [(d["rule"], d["file"], d["line"]) for d in mc.scan(self.root, **kwargs)["leads"]]


class MoveSourceTests(Case):
    def test_public_function_returning_refs(self):
        self.package(
            "module demo::vault {\n"                                         # 1
            "    use aptos_framework::object::{ExtendRef, TransferRef, ConstructorRef, Object};\n"
            "    public fun leak(v: &Vault): ExtendRef { v.extend_ref }\n"    # 3
            "    public(friend) fun friend_ok(v: &Vault): ExtendRef { v.extend_ref }\n"
            "    fun private_ok(v: &Vault): TransferRef { v.transfer_ref }\n"
            "    public fun handle(addr: address): Object<Vault> { object::address_to_object(addr) }\n"
            "    public fun create(\n"                                       # 7
            "        creator: &signer,\n"
            "        seed: vector<u8>,\n"
            "    ): (ConstructorRef, u64) acquires Registry {\n"
            "        (object::create_named_object(creator, seed), 1)\n"
            "    }\n"
            "}\n")
        self.assertEqual(self.leads(), [
            ("PUBLIC-RETURNS-REF", "sources/demo.move", 3),
            ("PUBLIC-RETURNS-REF", "sources/demo.move", 7),
        ])

    def test_signer_from_stored_ref(self):
        self.package(
            "module demo::vault {\n"
            "    public entry fun drain(user: &signer, vault: Object<Vault>) acquires Vault {\n"   # 2
            "        let refs = borrow_global<Vault>(object::object_address(&vault));\n"
            "        let s = object::generate_signer_for_extending(&refs.extend_ref);\n"
            "    }\n"
            "    public entry fun withdraw(user: &signer, vault: Object<Vault>) acquires Vault {\n"
            "        assert!(object::is_owner(vault, signer::address_of(user)), 1);\n"
            "        let refs = borrow_global<Vault>(object::object_address(&vault));\n"
            "        let s = object::generate_signer_for_extending(&refs.extend_ref);\n"
            "    }\n"
            "    fun internal(refs: &Vault): signer {\n"
            "        object::generate_signer_for_extending(&refs.extend_ref)\n"
            "    }\n"
            "}\n")
        self.assertEqual(self.leads(), [("SIGNER-FROM-REF-UNCHECKED", "sources/demo.move", 2)])

    def test_randomness_visibility(self):
        self.package(
            "module demo::dice {\n"
            "    #[randomness]\n"
            "    public entry fun roll_public(user: &signer) { let n = randomness::u64_range(0, 6); }\n"   # 3
            "    #[randomness]\n"
            "    entry fun roll(user: &signer) { let n = randomness::u64_range(0, 6); }\n"
            "    public fun helper(): u64 { randomness::u64_integer() }\n"   # 6
            "    #[randomness]\n"
            "    fun not_entry() {}\n"                                         # 8
            "    fun private_helper(): u64 { randomness::u64_integer() }\n"
            "}\n")
        self.assertEqual(self.leads(), [
            ("RANDOMNESS-EXPOSED", "sources/demo.move", 3),
            ("RANDOMNESS-EXPOSED", "sources/demo.move", 6),
            ("RANDOMNESS-EXPOSED", "sources/demo.move", 8),
        ])

    def test_timestamp_debug_and_test_context(self):
        self.package(
            "module demo::raffle {\n"
            "    use std::debug;\n"
            "    fun pick(n: u64): u64 {\n"
            "        debug::print(&n);\n"                                       # 4
            "        timestamp::now_microseconds() % n\n"                     # 5
            "    }\n"
            "    // debug::print(&n);  commented out\n"
            "    fun label(): vector<u8> { b\"debug::print\" }\n"
            "    #[test]\n"
            "    fun t() { debug::print(&1); }\n"
            "}\n")
        write(self.root, "sources/helpers.move",
              "#[test_only]\nmodule demo::helpers {\n    fun h() { debug::print(&2); }\n}\n")
        self.assertEqual(self.leads(), [
            ("DEBUG-PRINT", "sources/demo.move", 4),
            ("TIMESTAMP-RANDOMNESS", "sources/demo.move", 5),
        ])

    def test_hardcoded_address_and_legacy_coin(self):
        self.package(
            "module 0xcafe::my_coin {\n"
            "    struct MyCoin {}\n"
            "    fun init_module(s: &signer) {\n"
            "        let (b, f, m) = coin::initialize<MyCoin>(s, name, symbol, 8, true);\n"
            "    }\n"
            "}\n")
        self.assertEqual(self.leads(), [
            ("HARDCODED-ADDRESS", "sources/demo.move", 1),
            ("LEGACY-COIN", "sources/demo.move", 4),
        ])

    def test_acknowledged_line(self):
        self.package(
            "module demo::m {\n"
            "    // move-check: ignore DEBUG-PRINT kept for a localnet demo, removed before publish\n"
            "    fun f() { debug::print(&1); }\n"
            "}\n")
        result = mc.scan(self.root)
        self.assertEqual(result["leads"], [])
        self.assertEqual(result["suppressed"], 1)


class PackageTests(Case):
    def test_moving_branch(self):
        self.package("module demo::m {}\n", rev="mainnet")
        write(self.root, "other/Move.toml",
              '[dependencies]\nAptosStdlib = { git = "https://example.invalid/x.git", rev = "main", subdir = "s" }\n'
              '# rev = "devnet" in a comment is ignored\n')
        write(self.root, "other/sources/a.move", "module other::a {\n    #[test]\n    fun t() {}\n}\n")
        self.assertEqual(self.leads(), [
            ("DEP-MOVING-BRANCH", "Move.toml", 10),
            ("DEP-MOVING-BRANCH", "other/Move.toml", 2),
        ])

    def test_package_without_tests(self):
        self.package("module demo::m { fun f() {} }\n", tests=False)
        self.assertEqual(self.leads(), [("NO-TESTS", "Move.toml", 1)])

    def test_build_folder_skipped(self):
        self.package("module demo::m {}\n")
        write(self.root, "build/demo/sources/dependencies/AptosFramework/object.move",
              "module aptos_framework::object {\n    public fun leak(): ExtendRef { abort 0 }\n}\n")
        self.assertEqual(self.leads(), [])


class KeyFileTests(Case):
    def key_files(self):
        write(self.root, ".aptos/config.yaml",
              "---\nprofiles:\n  dev:\n    private_key: \"" + fake_private_key() + "\"\n    network: Devnet\n")
        write(self.root, "keys/devnet.json", json.dumps([7] * 64))
        write(self.root, "package.json", json.dumps({"name": "dapp", "version": "1.0.0"}))
        write(self.root, "numbers.json", json.dumps(list(range(10))))

    def test_without_git(self):
        self.key_files()
        leads = self.leads(use_git=False)
        self.assertEqual(leads, [
            ("KEY-FILE-UNIGNORED", ".aptos/config.yaml", 1),
            ("KEY-FILE-UNIGNORED", "keys/devnet.json", 1),
        ])
        code, out, _ = run(["--root", str(self.root), "--no-git"])
        self.assertEqual(code, 1)
        self.assertNotIn(fake_private_key(), out)
        self.assertNotIn("5555555555", out)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_with_git_status(self):
        self.key_files()
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, env=env)
        write(self.root, ".gitignore", ".aptos/\n")
        subprocess.run(["git", "-C", str(self.root), "add", "keys/devnet.json"], check=True, env=env)
        write(self.root, "scratch/id.json", json.dumps([9] * 64))
        self.assertEqual(self.leads(), [
            ("KEY-FILE-TRACKED", "keys/devnet.json", 1),
            ("KEY-FILE-UNIGNORED", "scratch/id.json", 1),
        ])


class CliTests(Case):
    def test_exit_codes(self):
        self.assertEqual(run(["--root", str(self.root)])[0], 0)
        self.package("module demo::m { fun f() { debug::print(&1); } }\n")
        self.assertEqual(run(["--root", str(self.root)])[0], 0, "low leads pass the default medium threshold")
        self.assertEqual(run(["--root", str(self.root), "--fail-on", "low"])[0], 1)
        self.assertEqual(run(["--root", str(self.root / "missing")])[0], 2)
        self.assertEqual(run(["--bogus"])[0], 2)
        self.assertEqual(run(["--help"])[0], 0)
        code, out, _ = run(["--list-rules"])
        self.assertEqual(code, 0)
        for rule in mc.RULES:
            self.assertIn(rule, out)

    def test_json_is_deterministic(self):
        self.package("module 0x1234::m {\n    public fun f(): signer { abort 0 }\n}\n", rev="devnet", tests=False)
        first = run(["--root", str(self.root), "--json", "--no-git"])[1]
        second = run(["--root", str(self.root), "--json", "--no-git"])[1]
        self.assertEqual(first, second)
        data = json.loads(first)
        self.assertEqual(data["counts"], {"high": 1, "medium": 0, "low": 3})


if __name__ == "__main__":
    unittest.main()
