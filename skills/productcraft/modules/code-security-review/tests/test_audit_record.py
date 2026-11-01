"""Offline tests for audit_record.py. Synthetic data only: no network, no real secrets, no live targets."""
import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_record.py"
spec = importlib.util.spec_from_file_location("audit_record", SCRIPT)
ar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ar
spec.loader.exec_module(ar)

REV = "3f2c1ab"


def check(method="read", paths=("src/orders.ts",), **extra):
    item = {"method": method, "paths": list(paths), "invariant": "orders are returned only to their owner",
            "result": "query filters by session user id on every branch"}
    item.update(extra)
    return item


def cell(cid, surface, status="PASS", **extra):
    item = {"id": cid, "surface": surface, "boundary": "user to other users' records", "class": "access control",
            "status": status}
    if status in ("PASS", "FAIL", "NEEDS_REVIEW"):
        item.update({"reviewer": "hunter-a", "revision": REV, "paths": ["src/orders.ts"], "checks": [check()]})
    if status in ("NOT_APPLICABLE", "NOT_VERIFIED", "OUT_OF_SCOPE"):
        item["reason"] = "no such feature in the repository"
    item.update(extra)
    return item


def full_record():
    return {
        "record_version": 1,
        "audit": {"repository": "demo", "revision": REV, "depth": "full", "scope": ["src/"], "out_of_scope": []},
        "cells": [
            cell("C-01", "GET /api/orders/:id", "FAIL", findings=["CSR-001"]),
            cell("C-02", "POST /api/search", "PASS"),
            cell("C-03", "file import", "NOT_APPLICABLE", **{"class": "XML external entities"}),
        ],
        "gap_reviews": [{"id": "G-1", "reviewer": "critic-1", "result": "clean", "added": [], "reopened": []}],
    }


def findings_doc():
    return {
        "audit": {"repository": "demo", "revision": REV, "mode": "full", "scope": ["src/"]},
        "coverage": [],
        "findings": [{
            "id": "CSR-001", "title": "Order read without owner check", "class": "broken object-level authorization",
            "file": "src/orders.ts", "line": 42, "actor": "any signed-in user", "preconditions": [],
            "impact": "reads other customers' orders", "confidence": "CONFIRMED", "severity": "HIGH",
            "status": "OPEN", "evidence_type": "TESTED_LOCAL", "evidence_summary": "two-user test",
            "fix": "scope the query by the session user id",
        }],
    }


def rigorous_finding(**extra):
    item = copy.deepcopy(findings_doc()["findings"][0])
    item.update({
        "root_cause_key": "orders/find-by-id-without-owner",
        "invariant": "an order is returned only to its owner or to staff with orders:read",
        "impact_level": "HIGH",
        "severity_reason": "HIGH: any signed-up user reads any customer's orders; no preconditions.",
        "access_class": "ANY_ACCOUNT",
        "preconditions": [{"kind": "account", "detail": "a free self-registered account"}],
        "reproduction": {"interface": "http", "steps": ["sign in as user A", "GET /api/orders/<B's id>"],
                         "observed": "200 with user B's order"},
    })
    item.update(extra)
    return item


def has(messages, text):
    return any(text in m for m in messages)


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ar.main(list(args))
        except SystemExit as exc:  # argparse usage errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class CoverageStructureTests(unittest.TestCase):
    def test_complete_record_supports_full_claim(self):
        report = ar.check_coverage(full_record(), findings_doc())
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["supported_claim"], "full")
        self.assertEqual(report["counts"], {"FAIL": 1, "NOT_APPLICABLE": 1, "PASS": 1})

    def test_duplicate_id_and_same_identity_are_errors(self):
        record = full_record()
        record["cells"].append(cell("C-02", "PATCH /api/orders/:id"))
        record["cells"].append(cell("C-09", "  post   /API/search ", "PASS"))
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "duplicate id"))
        self.assertTrue(has(errors, "same surface, boundary and class"))

    def test_unknown_status_and_missing_fields(self):
        record = full_record()
        record["cells"][1]["status"] = "LOOKS_FINE"
        del record["cells"][1]["boundary"]
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "'status' must be one of"))
        self.assertTrue(has(errors, "'boundary' is required"))

    def test_pass_without_checks_reviewer_or_revision(self):
        record = full_record()
        record["cells"][1] = {"id": "C-02", "surface": "POST /api/search", "boundary": "anonymous to database",
                              "class": "SQL injection", "status": "PASS"}
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "PASS needs at least one check"))
        self.assertTrue(has(errors, "PASS needs the 'reviewer'"))
        self.assertTrue(has(errors, "PASS needs the source 'revision'"))

    def test_paths_must_match_the_checks(self):
        record = full_record()
        record["cells"][1]["paths"] = ["src/orders.ts", "src/export.ts"]
        record["cells"][1]["checks"].append(check(paths=["src/db.ts"]))
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "'src/export.ts' is listed as reviewed but no check covers it"))
        self.assertTrue(has(errors, "check path 'src/db.ts' is missing"))

    def test_test_and_tool_checks_need_a_command(self):
        record = full_record()
        record["cells"][1]["checks"] = [check(method="test")]
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "a test check needs the 'command'"))
        record["cells"][1]["checks"] = [check(method="test", command="npm test -- orders.authz",
                                              artifact="security/evidence/c-02.txt")]
        self.assertEqual(ar.check_coverage(record)["errors"], [])

    def test_unsafe_paths_are_rejected(self):
        for bad in ("/etc/passwd", "../other/repo.ts", "C:\\src\\a.ts", "~/notes.md"):
            record = full_record()
            record["cells"][1]["paths"] = [bad]
            record["cells"][1]["checks"] = [check(paths=[bad])]
            self.assertTrue(has(ar.check_coverage(record)["errors"], "repository-relative"), bad)

    def test_bad_artifact_and_check_method(self):
        record = full_record()
        record["cells"][1]["checks"] = [check(method="glance", artifact="/tmp/out.txt")]
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "'method' must be one of"))
        self.assertTrue(has(errors, "'artifact' must be a relative path"))

    def test_stale_revision_needs_carried_evidence(self):
        record = full_record()
        record["cells"][1]["revision"] = "0aa11bb"
        self.assertTrue(has(ar.check_coverage(record)["errors"], "re-examine it or record 'carried'"))
        record["cells"][1]["carried"] = {"from_revision": "0aa11bb", "unchanged": True,
                                         "how": "git diff --quiet 0aa11bb 3f2c1ab -- src/orders.ts"}
        self.assertEqual(ar.check_coverage(record)["errors"], [])
        record["cells"][1]["carried"]["unchanged"] = "yes"
        self.assertTrue(has(ar.check_coverage(record)["errors"], "'carried.unchanged': true"))

    def test_status_specific_requirements(self):
        record = full_record()
        record["cells"][0]["findings"] = []
        del record["cells"][2]["reason"]
        record["cells"].append(cell("C-04", "webhooks", "PLANNED", checks=[check()]))
        record["cells"].append(cell("C-05", "cron", "IN_PROGRESS"))
        record["cells"].append(cell("C-06", "admin", "NEEDS_REVIEW"))
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "FAIL needs the finding ids"))
        self.assertTrue(has(errors, "NOT_APPLICABLE needs a 'reason'"))
        self.assertTrue(has(errors, "PLANNED cell carries checks"))
        self.assertTrue(has(errors, "IN_PROGRESS needs the 'reviewer'"))
        self.assertTrue(has(errors, "NEEDS_REVIEW needs a linked lead"))

    def test_top_level_shape(self):
        self.assertEqual(ar.check_coverage([])["supported_claim"], "none")
        record = full_record()
        record["record_version"] = 2
        record["audit"]["depth"] = "deep"
        record["audit"]["scope"] = []
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "'record_version' must be 1"))
        self.assertTrue(has(errors, "'depth' must be one of"))
        self.assertTrue(has(errors, "'scope' must be a non-empty list"))


class CoverageClaimTests(unittest.TestCase):
    def test_working_and_unverified_cells_make_it_partial(self):
        record = full_record()
        record["cells"].append(cell("C-04", "POST /webhooks/payments", "PLANNED"))
        record["cells"].append(cell("C-05", "GET /api/export", "NOT_VERIFIED"))
        report = ar.check_coverage(record)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["supported_claim"], "partial")
        self.assertTrue(has(report["claim_blockers"], "1 PLANNED"))
        self.assertTrue(has(report["claim_blockers"], "1 NOT_VERIFIED"))

    def test_needs_review_without_lead_blocks_claims(self):
        record = full_record()
        record["cells"].append(cell("C-04", "admin", "NEEDS_REVIEW", reason="guard reads a config value we lack"))
        report = ar.check_coverage(record)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["supported_claim"], "partial")

    def test_out_of_scope_or_partial_depth_make_it_scoped(self):
        record = full_record()
        record["cells"].append(cell("C-04", "infra/terraform", "OUT_OF_SCOPE"))
        self.assertEqual(ar.check_coverage(record)["supported_claim"], "scoped")
        record = full_record()
        record["audit"]["depth"] = "diff"
        report = ar.check_coverage(record)
        self.assertEqual(report["supported_claim"], "scoped")
        self.assertTrue(has(report["claim_blockers"], "audit depth is diff"))

    def test_gap_reviews_gate_any_claim(self):
        record = full_record()
        record["gap_reviews"] = []
        self.assertEqual(ar.check_coverage(record)["supported_claim"], "partial")
        record["gap_reviews"] = [{"id": "G-1", "reviewer": "critic-1", "result": "gaps_found",
                                  "added": ["C-03"], "reopened": []}]
        report = ar.check_coverage(record)
        self.assertEqual(report["supported_claim"], "partial")
        self.assertTrue(has(report["claim_blockers"], "last gap review found gaps"))

    def test_gap_review_consistency(self):
        record = full_record()
        record["gap_reviews"] = [
            {"id": "G-1", "reviewer": "critic-1", "result": "clean", "added": ["C-03"], "reopened": []},
            {"id": "G-2", "reviewer": "critic-2", "result": "gaps_found", "added": ["C-99"], "reopened": []},
            {"id": "G-3", "reviewer": "critic-3", "result": "gaps_found", "added": [], "reopened": []},
            {"id": "G-4", "result": "maybe"},
        ]
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "a clean review cannot add or reopen"))
        self.assertTrue(has(errors, "unknown cell 'C-99'"))
        self.assertTrue(has(errors, "must name the cells it added or reopened"))
        self.assertTrue(has(errors, "'reviewer' is required"))
        self.assertTrue(has(errors, "'result' must be"))

    def test_reopened_cell_needs_attempts_and_fresh_reviewer(self):
        record = full_record()
        record["gap_reviews"].insert(0, {"id": "G-0", "reviewer": "critic-0", "result": "gaps_found",
                                         "added": [], "reopened": ["C-02"]})
        self.assertTrue(has(ar.check_coverage(record)["errors"], "reopened by a gap review"))
        record["cells"][1]["attempts"] = [{"status": "PASS", "reviewer": "hunter-a", "checks": [check()],
                                           "reopen_reason": "export route was never read"}]
        report = ar.check_coverage(record)
        self.assertEqual(report["errors"], [])
        self.assertTrue(has(report["warnings"], "a fresh reviewer is preferred"))
        record["cells"][1]["attempts"] = [{"status": "LOOKED", "checks": "none"}]
        errors = ar.check_coverage(record)["errors"]
        self.assertTrue(has(errors, "attempt 1: 'status' must be one of"))
        self.assertTrue(has(errors, "'reopen_reason' is required"))
        self.assertTrue(has(errors, "'checks' must be a list"))

    def test_final_reviewer_should_not_have_examined_cells(self):
        record = full_record()
        record["gap_reviews"][0]["reviewer"] = "hunter-a"
        self.assertTrue(has(ar.check_coverage(record)["warnings"], "use a reviewer who did not"))


class CoverageCrossCheckTests(unittest.TestCase):
    def test_unknown_and_unlinked_findings(self):
        record = full_record()
        record["cells"][0]["findings"] = ["CSR-404"]
        doc = findings_doc()
        doc["findings"].append(dict(doc["findings"][0], id="CSR-002", confidence="POSSIBLE", severity=None,
                                    next_check="read the guard"))
        report = ar.check_coverage(record, doc)
        self.assertTrue(has(report["errors"], "links finding 'CSR-404'"))
        self.assertTrue(has(report["errors"], "finding 'CSR-001': CONFIRMED but no coverage cell links it"))
        self.assertTrue(has(report["warnings"], "finding 'CSR-002': lead not linked"))

    def test_pass_cannot_hold_an_open_confirmed_finding(self):
        record = full_record()
        record["cells"][1]["findings"] = ["CSR-001"]
        self.assertTrue(has(ar.check_coverage(record, findings_doc())["errors"], "is PASS while CONFIRMED"))

    def test_fail_needs_a_standing_finding(self):
        doc = findings_doc()
        doc["findings"][0].update(status="FALSE_POSITIVE", rejection_reason="guard at src/auth.ts:12")
        errors = ar.check_coverage(full_record(), doc)["errors"]
        self.assertTrue(has(errors, "FAIL links no CONFIRMED or LIKELY finding that still stands"))

    def test_report_coverage_must_mirror_the_record(self):
        doc = findings_doc()
        doc["coverage"] = [{"id": "C-01", "status": "FAIL"}, {"id": "C-02", "status": "NOT_VERIFIED"},
                           {"id": "C-77", "status": "PASS"}]
        errors = ar.check_coverage(full_record(), doc)["errors"]
        self.assertTrue(has(errors, "record says PASS, findings file says 'NOT_VERIFIED'"))
        self.assertTrue(has(errors, "cell 'C-03': missing from the findings file"))
        self.assertTrue(has(errors, "coverage 'C-77': not in the coverage record"))

    def test_revision_mismatch(self):
        doc = findings_doc()
        doc["audit"]["revision"] = "9999999"
        self.assertTrue(has(ar.check_coverage(full_record(), doc)["errors"], "differs from the record's"))

    def test_findings_file_shape(self):
        self.assertTrue(has(ar.check_coverage(full_record(), [])["errors"], "top level must be a JSON object"))
        self.assertTrue(has(ar.check_coverage(full_record(), {"findings": {}})["errors"],
                            "'findings' must be a list"))


class RigorTests(unittest.TestCase):
    def doc(self, *findings):
        return {"audit": {"revision": REV}, "findings": list(findings)}

    def test_rigorous_finding_passes_and_reports_ceiling(self):
        report = ar.check_rigor(self.doc(rigorous_finding()))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["ratings"][0]["ceiling"], "HIGH")
        self.assertEqual(report["checked"], {"CONFIRMED": 1})

    def test_required_fields(self):
        finding = rigorous_finding()
        for field in ("invariant", "impact_level", "severity_reason", "root_cause_key", "reproduction"):
            del finding[field]
        errors = ar.check_rigor(self.doc(finding))["errors"]
        for text in ("'invariant' is required", "'impact_level' must be one of", "'severity_reason' is required",
                     "'root_cause_key' is required", "needs a 'reproduction'"):
            self.assertTrue(has(errors, text), text)

    def test_severity_cannot_exceed_impact_or_drop_below_low(self):
        errors = ar.check_rigor(self.doc(rigorous_finding(impact_level="MEDIUM")))["errors"]
        self.assertTrue(has(errors, "above the demonstrated impact level MEDIUM"))
        errors = ar.check_rigor(self.doc(rigorous_finding(impact_level="LOW", severity="INFO")))["errors"]
        self.assertTrue(has(errors, "rated at least LOW"))

    def test_preconditions_must_be_typed(self):
        errors = ar.check_rigor(self.doc(rigorous_finding(
            preconditions=["needs an account", {"kind": "luck", "detail": "x"}, {"kind": "role"}])))["errors"]
        self.assertTrue(has(errors, "precondition 1: type it as an object"))
        self.assertTrue(has(errors, "precondition 2: 'kind' must be one of"))
        self.assertTrue(has(errors, "precondition 3: 'detail' is required"))

    def test_ceiling_rules(self):
        self.assertEqual(ar.severity_ceiling("HIGH", ["role"]), "MEDIUM")
        self.assertEqual(ar.severity_ceiling("CRITICAL", ["local_access", "role"]), "MEDIUM")
        self.assertEqual(ar.severity_ceiling("MEDIUM", ["local_access"]), "LOW")
        self.assertEqual(ar.severity_ceiling("CRITICAL", ["user_action", "timing", "configuration"]), "MEDIUM")
        self.assertEqual(ar.severity_ceiling("HIGH", ["account", "data_state"]), "HIGH")
        self.assertEqual(ar.severity_ceiling("INFO", ["role"]), "INFO")

    def test_rating_above_ceiling_is_a_warning(self):
        finding = rigorous_finding(preconditions=[{"kind": "role", "detail": "tenant admin"}])
        report = ar.check_rigor(self.doc(finding))
        self.assertEqual(report["errors"], [])
        self.assertTrue(has(report["warnings"], "above the ceiling MEDIUM"))

    def test_trace_rules(self):
        finding = rigorous_finding(evidence_type="STATIC_CONFIRMED")
        del finding["reproduction"]
        self.assertTrue(has(ar.check_rigor(self.doc(finding))["errors"], "needs a 'trace'"))
        finding["trace"] = [
            {"step": "hop", "file": "src/routes.ts", "line": 10, "note": "route"},
            {"step": "sink", "file": "/abs/db.ts", "line": 0, "note": ""},
        ]
        errors = ar.check_rigor(self.doc(finding))["errors"]
        self.assertTrue(has(errors, "trace step 1: expected 'source'"))
        self.assertTrue(has(errors, "trace step 2: 'file' must be repository-relative"))
        self.assertTrue(has(errors, "'line' must be a positive integer"))
        self.assertTrue(has(errors, "'note' must say"))
        finding["trace"] = [
            {"step": "source", "file": "src/routes.ts", "line": 10, "note": "id from the path"},
            {"step": "hop", "file": "src/orders.ts", "line": 42, "note": "passed through unchanged"},
            {"step": "sink", "file": "src/db/orders.ts", "line": 12, "note": "findUnique by id only"},
        ]
        self.assertEqual(ar.check_rigor(self.doc(finding))["errors"], [])

    def test_reproduction_fields(self):
        finding = rigorous_finding(reproduction={"interface": "carrier pigeon", "steps": [], "observed": " "})
        errors = ar.check_rigor(self.doc(finding))["errors"]
        self.assertTrue(has(errors, "'reproduction.interface' must be one of"))
        self.assertTrue(has(errors, "'reproduction.steps' must list"))
        self.assertTrue(has(errors, "'reproduction.observed' must state"))

    def test_likely_needs_trace_and_owner_check(self):
        finding = rigorous_finding(confidence="LIKELY", evidence_type="STATIC_CONFIRMED",
                                   unverified_condition="production sets AUTH_REQUIRED")
        del finding["reproduction"]
        errors = ar.check_rigor(self.doc(finding))["errors"]
        self.assertTrue(has(errors, "needs an 'owner_check'"))
        self.assertTrue(has(errors, "needs a 'trace'"))

    def test_root_cause_key_rules(self):
        a = rigorous_finding(root_cause_key="orders/find-by-id:42")
        errors = ar.check_rigor(self.doc(a))["errors"]
        self.assertTrue(has(errors, "must not end in a line number"))
        b = rigorous_finding(id="CSR-002")
        c = rigorous_finding(id="CSR-003")
        self.assertTrue(has(ar.check_rigor(self.doc(b, c))["errors"], "repeats"))
        d = rigorous_finding(root_cause_key="has space")
        self.assertTrue(has(ar.check_rigor(self.doc(d))["errors"], "'root_cause_key' must match"))

    def test_leads_and_false_positives_are_skipped(self):
        lead = {"id": "CSR-009", "confidence": "POSSIBLE", "status": "OPEN", "next_check": "read the guard"}
        refuted = rigorous_finding(id="CSR-010", status="FALSE_POSITIVE", root_cause_key="x/y")
        del refuted["invariant"]
        report = ar.check_rigor(self.doc(lead, refuted))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["checked"], {})

    def test_access_class_values(self):
        report = ar.check_rigor(self.doc(rigorous_finding(access_class="OPERATOR_ONLY")))
        self.assertTrue(has(report["warnings"], "operators are trusted"))
        report = ar.check_rigor(self.doc(rigorous_finding(access_class="EVERYONE")))
        self.assertTrue(has(report["errors"], "'access_class' must be one of"))

    def test_bad_document(self):
        self.assertTrue(has(ar.check_rigor([])["errors"], "expected an object with a 'findings' list"))
        self.assertTrue(has(ar.check_rigor(self.doc("text"))["errors"], "must be an object"))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, data, raw=False):
        path = self.dir / name
        path.write_text(data if raw else json.dumps(data), encoding="utf-8")
        return str(path)

    def test_claims_and_exit_codes(self):
        record = self.put("record.json", full_record())
        findings = self.put("findings.json", findings_doc())
        code, out, _ = run_cli("coverage", "--record", record, "--findings", findings, "--claim", "full")
        self.assertEqual(code, 0, out)
        self.assertIn("Supported claim: full", out)
        scoped = full_record()
        scoped["cells"].append(cell("C-04", "infra", "OUT_OF_SCOPE"))
        path = self.put("scoped.json", scoped)
        self.assertEqual(run_cli("coverage", "--record", path, "--claim", "scoped")[0], 0)
        code, out, _ = run_cli("coverage", "--record", path, "--claim", "full")
        self.assertEqual(code, 1)
        self.assertIn("Requested claim 'full' is not supported", out)

    def test_errors_exit_one(self):
        record = full_record()
        record["cells"][1]["checks"] = []
        code, out, _ = run_cli("coverage", "--record", self.put("r.json", record))
        self.assertEqual(code, 1)
        self.assertIn("ERROR cell 'C-02'", out)
        self.assertIn("Supported claim: none", out)

    def test_input_errors_exit_two(self):
        self.assertEqual(run_cli("coverage", "--record", str(self.dir / "missing.json"))[0], 2)
        self.assertEqual(run_cli("coverage", "--record", self.put("bad.json", "{not json", raw=True))[0], 2)
        dup = self.put("dup.json", '{"record_version": 1, "record_version": 2}', raw=True)
        code, _, err = run_cli("coverage", "--record", dup)
        self.assertEqual(code, 2)
        self.assertIn("duplicate key", err)
        self.assertEqual(run_cli("coverage")[0], 2)
        self.assertEqual(run_cli("unknown")[0], 2)

    def test_secret_values_are_flagged_never_printed(self):
        fake = "AKIA" + "Z" * 16
        record = full_record()
        record["cells"][1]["checks"][0]["result"] = f"found key {fake} in config"
        code, out, err = run_cli("coverage", "--record", self.put("s.json", record))
        self.assertEqual(code, 1)
        self.assertIn("cloud access key id", out)
        self.assertNotIn(fake, out + err)
        code, out, _ = run_cli("coverage", "--record", self.put("s.json", record), "--json")
        self.assertNotIn(fake, out)

    def test_json_output_is_deterministic(self):
        record = full_record()
        record["cells"].append(cell("C-04", "cron", "PLANNED"))
        path = self.put("r.json", record)
        first = run_cli("coverage", "--record", path, "--json")[1]
        second = run_cli("coverage", "--record", path, "--json")[1]
        self.assertEqual(first, second)
        data = json.loads(first)
        self.assertEqual(data["supported_claim"], "partial")
        self.assertTrue(data["claim_supported"])

    def test_rigor_cli(self):
        good = self.put("good.json", {"findings": [rigorous_finding()]})
        code, out, _ = run_cli("rigor", "--findings", good)
        self.assertEqual(code, 0, out)
        self.assertIn("ceiling HIGH, rated HIGH", out)
        bad_finding = rigorous_finding()
        del bad_finding["invariant"]
        bad = self.put("bad.json", {"findings": [bad_finding]})
        code, out, _ = run_cli("rigor", "--findings", bad, "--json")
        self.assertEqual(code, 1)
        self.assertTrue(has(json.loads(out)["errors"], "'invariant' is required"))

    def test_help_exits_zero(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("coverage", out)


if __name__ == "__main__":
    unittest.main()
