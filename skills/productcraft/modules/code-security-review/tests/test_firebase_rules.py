"""Offline tests for firebase_rules.py. Synthetic rules files only: no network, no real projects."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "firebase_rules.py"
spec = importlib.util.spec_from_file_location("firebase_rules", SCRIPT)
fr = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fr
spec.loader.exec_module(fr)


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def firestore(body: str, functions: str = "") -> str:
    return (
        "rules_version = '2';\n"
        "service cloud.firestore {\n"
        "  match /databases/{database}/documents {\n"
        f"{functions}\n{body}\n"
        "  }\n"
        "}\n"
    )


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = fr.main(argv)
    return code, out.getvalue()


def leads_for(root: Path):
    code, out = run(["--root", str(root), "--json"])
    return code, json.loads(out)


class ClassifyTests(unittest.TestCase):
    def test_open_forms(self):
        for expr in ("", "true", "(true)", "request.auth.uid==uid||true"):
            self.assertEqual(fr.classify(expr, "rules")[0], "open", expr)

    def test_signed_in_forms(self):
        for expr in ("request.auth!=null", "null!=request.auth", "(request.auth.uid!=null)",
                     "request.auth!=null&&request.auth.token.email_verified",
                     "resource.data.owner==request.auth.uid||request.auth!=null"):
            self.assertEqual(fr.classify(expr, "rules")[0], "signed_in", expr)

    def test_conditional_and_deny(self):
        self.assertEqual(fr.classify("request.auth.uid==userId", "rules")[0], "conditional")
        self.assertEqual(fr.classify("request.auth!=null&&request.auth.uid==userId", "rules")[0], "conditional")
        self.assertEqual(fr.classify("false", "rules")[0], "deny")
        self.assertEqual(fr.classify("request.auth!=null&&false", "rules")[0], "deny")

    def test_test_mode_dates(self):
        self.assertEqual(fr.classify("request.time<timestamp.date(2026,12,1)", "rules"), ("test_mode", "2026-12-01"))
        self.assertEqual(fr.classify("now<1767225600000", "database"), ("test_mode", "2026-01-01"))
        kind, expiry = fr.classify("request.auth!=null&&request.time<timestamp.date(2027,1,15)", "rules")
        self.assertEqual((kind, expiry), ("signed_in", "2027-01-15"))

    def test_database_dialect(self):
        self.assertEqual(fr.classify("auth!=null", "database")[0], "signed_in")
        self.assertEqual(fr.classify("$uid==auth.uid", "database")[0], "conditional")


class FirestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def ids(self, data):
        return [(d["id"], d["line"]) for d in data["leads"]]

    def test_open_rule_and_recursive_wildcard(self):
        write(self.tmp, "firestore.rules", firestore("    match /{document=**} {\n      allow read, write: if true;\n    }"))
        code, data = leads_for(self.tmp)
        self.assertEqual(code, 0)
        self.assertEqual(self.ids(data), [("FB-OPEN", 6)])
        lead = data["leads"][0]
        self.assertEqual(lead["level"], "high")
        self.assertEqual(lead["path"], "/{document=**}")
        self.assertEqual(lead["methods"], ["read", "write"])
        self.assertIn("every path below", lead["message"])

    def test_allow_without_condition(self):
        write(self.tmp, "firestore.rules", firestore("    match /posts/{id} {\n      allow read;\n    }"))
        _, data = leads_for(self.tmp)
        self.assertEqual(self.ids(data), [("FB-OPEN", 6)])

    def test_helper_function_is_inlined(self):
        funcs = "    function isSignedIn() {\n      return request.auth != null;\n    }"
        body = "    match /profiles/{uid} {\n      allow read: if isSignedIn();\n      allow write: if isSignedIn();\n    }"
        write(self.tmp, "firestore.rules", firestore(body, funcs))
        _, data = leads_for(self.tmp)
        got = {(d["id"], d["level"], tuple(d["methods"])) for d in data["leads"]}
        self.assertEqual(got, {("FB-SIGNED-IN", "medium", ("read",)), ("FB-SIGNED-IN", "high", ("write",))})

    def test_owner_rule_without_validation_is_low_lead(self):
        body = ("    match /users/{userId} {\n"
                "      allow read, delete: if request.auth.uid == userId;\n"
                "      allow create: if request.auth.uid == userId;\n"
                "    }")
        write(self.tmp, "firestore.rules", firestore(body))
        _, data = leads_for(self.tmp)
        self.assertEqual([(d["id"], d["level"], d["methods"]) for d in data["leads"]],
                         [("FB-UNVALIDATED", "low", ["create"])])

    def test_validation_through_function_with_parameters_counts(self):
        funcs = ("    function owns(uid) { return request.auth.uid == uid; }\n"
                 "    function onlyName(uid) {\n"
                 "      return request.resource.data.diff(resource.data).affectedKeys().hasOnly(['displayName']);\n"
                 "    }")
        body = "    match /users/{userId} {\n      allow update: if owns(userId) && onlyName(userId);\n    }"
        write(self.tmp, "firestore.rules", firestore(body, funcs))
        _, data = leads_for(self.tmp)
        self.assertEqual(data["leads"], [])
        self.assertEqual(data["status"], "NO_LEADS")

    def test_test_mode_rule(self):
        body = "    match /{document=**} {\n      allow read, write: if request.time < timestamp.date(2026, 11, 20);\n    }"
        write(self.tmp, "firestore.rules", firestore(body))
        _, data = leads_for(self.tmp)
        self.assertEqual(data["leads"][0]["id"], "FB-TEST-MODE")
        self.assertIn("2026-11-20", data["leads"][0]["message"])

    def test_comments_and_strings_are_not_rules(self):
        body = ("    // allow read, write: if true;\n"
                "    /* match /x/{y} { allow read; } */\n"
                "    match /links/{id} {\n"
                "      allow get: if resource.data.url == 'https://example.com//path' && request.auth.uid == resource.data.owner;\n"
                "    }")
        write(self.tmp, "firestore.rules", firestore(body))
        _, data = leads_for(self.tmp)
        self.assertEqual(data["leads"], [])
        self.assertEqual(data["files"][0]["rules"], 1)

    def test_block_brace_without_space(self):
        write(self.tmp, "firestore.rules", firestore("    match /open/{id}{\n      allow read: if true;\n    }"))
        _, data = leads_for(self.tmp)
        self.assertEqual(data["leads"][0]["path"], "/open/{id}")

    def test_storage_rules(self):
        text = ("rules_version = '2';\nservice firebase.storage {\n  match /b/{bucket}/o {\n"
                "    match /uploads/{uid}/{name} {\n      allow write: if request.auth.uid == uid;\n"
                "      allow read: if request.auth.uid == uid && request.resource == null;\n    }\n  }\n}\n")
        write(self.tmp, "storage.rules", text)
        _, data = leads_for(self.tmp)
        self.assertEqual([(d["id"], d["service"], d["path"]) for d in data["leads"]],
                         [("FB-UNVALIDATED", "storage", "/uploads/{uid}/{name}")])
        self.assertIn("size and content type", data["leads"][0]["message"])

    def test_parse_error_is_reported_not_raised(self):
        write(self.tmp, "firestore.rules", "service cloud.firestore {\n  match /x/{y} {\n    allow read: if true\n  }\n")
        _, data = leads_for(self.tmp)
        self.assertEqual(data["leads"][0]["id"], "FB-PARSE-ERROR")
        self.assertIsNone(data["files"][0]["rules"])

    def test_unknown_method_is_a_parse_error(self):
        write(self.tmp, "firestore.rules", firestore("    match /x/{y} {\n      allow reed: if true;\n    }"))
        _, data = leads_for(self.tmp)
        self.assertEqual(data["leads"][0]["id"], "FB-PARSE-ERROR")


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_database_rules(self):
        write(self.tmp, "database.rules.json", """{
  // comments are allowed in these files
  "rules": {
    ".read": false,
    "public": { ".read": true },
    "users": {
      "$uid": {
        ".read": "auth !== null",
        ".write": "$uid === auth.uid",
        ".validate": "newData.hasChildren(['name'])"
      }
    },
    "inbox": { ".write": "auth != null" },
    "beta": { ".read": "now < 1767225600000", ".indexOn": ["ts"] }
  }
}
""")
        _, data = leads_for(self.tmp)
        got = [(d["id"], d["line"], d["path"], d["level"]) for d in data["leads"]]
        self.assertEqual(got, [
            ("RTDB-OPEN", 5, "/public", "high"),
            ("RTDB-SIGNED-IN", 8, "/users/$uid", "medium"),
            ("RTDB-SIGNED-IN", 13, "/inbox", "high"),
            ("RTDB-TEST-MODE", 14, "/beta", "high"),
        ])
        self.assertEqual(data["files"], [{"file": "database.rules.json", "service": "database", "rules": 6}])
        self.assertIn("cascade", data["leads"][0]["message"])

    def test_invalid_json(self):
        write(self.tmp, "database.rules.json", '{ "rules": { ".read": true, } }')
        _, data = leads_for(self.tmp)
        self.assertEqual(data["leads"][0]["id"], "FB-PARSE-ERROR")


class DiscoveryAndCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_firebase_json_paths_missing_files_and_skipped_dirs(self):
        write(self.tmp, "firebase.json", json.dumps({
            "firestore": [{"database": "(default)", "rules": "config/main.rules"}],
            "storage": {"rules": "config/missing-storage.rules"},
        }))
        write(self.tmp, "config/main.rules", firestore("    match /a/{b} {\n      allow read: if true;\n    }"))
        write(self.tmp, "node_modules/pkg/firestore.rules", firestore("    match /z/{b} {\n      allow read;\n    }"))
        _, data = leads_for(self.tmp)
        self.assertEqual([f["file"] for f in data["files"]], ["config/main.rules"])
        ids = sorted(d["id"] for d in data["leads"])
        self.assertEqual(ids, ["FB-MISSING-FILE", "FB-OPEN"])
        missing = next(d for d in data["leads"] if d["id"] == "FB-MISSING-FILE")
        self.assertEqual((missing["level"], missing["file"]), ("info", "firebase.json"))

    def test_other_rules_file_detected_by_service_line(self):
        write(self.tmp, "infra/prod.rules", firestore("    match /a/{b} {\n      allow read;\n    }"))
        write(self.tmp, "infra/notes.rules", "not a firebase file")
        _, data = leads_for(self.tmp)
        self.assertEqual([f["file"] for f in data["files"]], ["infra/prod.rules"])

    def test_no_rules_is_not_applicable(self):
        code, data = leads_for(self.tmp)
        self.assertEqual((code, data["status"], data["files"]), (0, "NOT_APPLICABLE", []))
        code, out = run(["--root", str(self.tmp)])
        self.assertIn("NOT_APPLICABLE", out)

    def test_fail_on_and_exit_codes(self):
        write(self.tmp, "firestore.rules", firestore("    match /a/{b} {\n      allow create: if request.auth.uid == b;\n    }"))
        self.assertEqual(run(["--root", str(self.tmp), "--fail-on", "high"])[0], 0)
        self.assertEqual(run(["--root", str(self.tmp), "--fail-on", "low"])[0], 1)
        self.assertEqual(run(["--root", str(self.tmp / "nope")])[0], 2)
        self.assertEqual(run(["--file", str(self.tmp / "nope.rules")])[0], 2)

    def test_explicit_file_and_json_out_mode(self):
        path = write(self.tmp, "x.rules", firestore("    match /a/{b} {\n      allow read;\n    }"))
        out_file = self.tmp / "out" / "result.json"
        out_file.parent.mkdir()
        code, text = run(["--file", str(path), "--json-out", str(out_file)])
        self.assertEqual(code, 0)
        self.assertIn("FB-OPEN", text)
        saved = json.loads(out_file.read_text())
        self.assertEqual(saved["leads"][0]["id"], "FB-OPEN")
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(out_file.stat().st_mode), 0o600)

    def test_output_is_deterministic_and_hides_conditions(self):
        body = "    match /a/{b} {\n      allow read: if request.auth.token.secretMarker123 != null || true;\n    }"
        write(self.tmp, "firestore.rules", firestore(body))
        first = run(["--root", str(self.tmp), "--json"])[1]
        second = run(["--root", str(self.tmp), "--json"])[1]
        self.assertEqual(first, second)
        self.assertNotIn("secretMarker123", first)
        self.assertNotIn("secretMarker123", run(["--root", str(self.tmp)])[1])

    def test_help_runs_as_a_script(self):
        proc = subprocess.run([sys.executable, "-I", str(SCRIPT), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("FB-SIGNED-IN", proc.stdout)


if __name__ == "__main__":
    unittest.main()
