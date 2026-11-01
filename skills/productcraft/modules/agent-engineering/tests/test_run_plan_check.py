"""Offline tests for run_plan_check.py using synthetic plans only; no network."""
import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_plan_check.py"
EXAMPLE = ROOT / "assets" / "run-plan.example.json"
spec = importlib.util.spec_from_file_location("run_plan_check", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def base_plan():
    return {
        "goal": {"done_when": ["`make test` exits 0"], "must_not": ["delete tests"], "judge": "ci"},
        "budget": {"max_wall_clock_minutes": 30, "max_iterations": 5, "max_tokens": 500000},
        "stop": {"no_progress_checkpoints": 2, "max_same_failure": 2, "stop_file": ".run/STOP"},
        "checkpoints": {"state_file": ".run/state.json", "commit_each_step": True},
        "actions": ["edit_files", "run_tests"],
        "permissions": {"mode": "allowlist", "allowed_tools": ["read", "edit"], "bypass": False},
    }


def ids(plan, severity=None):
    return sorted({f.code for f in module.check_plan(plan) if severity is None or f.severity == severity})


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_plan(tmp, plan, name="plan.json"):
    path = Path(tmp) / name
    path.write_text(json.dumps(plan), encoding="utf-8")
    return str(path)


class CleanPlans(unittest.TestCase):
    def test_base_plan_has_no_findings(self):
        self.assertEqual(ids(base_plan()), [])

    def test_shipped_example_passes(self):
        code, out, _ = run_cli([str(EXAMPLE)])
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_cost_budget_alone_satisfies_money_dimension(self):
        plan = base_plan()
        del plan["budget"]["max_tokens"]
        plan["budget"].update({"max_cost": 10, "currency": "USD"})
        self.assertEqual(ids(plan), [])


class Budgets(unittest.TestCase):
    def test_missing_time_budget_is_error(self):
        plan = base_plan()
        del plan["budget"]["max_wall_clock_minutes"]
        self.assertIn("B01", ids(plan, "ERROR"))

    def test_missing_token_and_money_budget_is_error(self):
        plan = base_plan()
        del plan["budget"]["max_tokens"]
        self.assertIn("B02", ids(plan, "ERROR"))

    def test_non_positive_and_boolean_values_rejected(self):
        for bad in (0, -5, True, "10", float("inf")):
            plan = base_plan()
            plan["budget"]["max_iterations"] = bad
            self.assertIn("B04", ids(plan, "ERROR"), bad)

    def test_missing_iteration_cap_is_warning(self):
        plan = base_plan()
        del plan["budget"]["max_iterations"]
        self.assertEqual(ids(plan), ["B03"])

    def test_cost_without_currency_warns(self):
        plan = base_plan()
        plan["budget"]["max_cost"] = 5
        self.assertIn("B05", ids(plan, "WARN"))


class GoalsAndStops(unittest.TestCase):
    def test_missing_done_when_is_error(self):
        plan = base_plan()
        plan["goal"]["done_when"] = []
        self.assertIn("G01", ids(plan, "ERROR"))

    def test_vague_done_when_warns_but_command_does_not(self):
        plan = base_plan()
        plan["goal"]["done_when"] = ["the code looks clean and well structured", "`pytest` passes"]
        findings = [f for f in module.check_plan(plan) if f.code == "G02"]
        self.assertEqual([f.path for f in findings], ["goal.done_when[0]"])

    def test_missing_boundaries_and_self_judge_warn(self):
        plan = base_plan()
        plan["goal"]["must_not"] = []
        plan["goal"]["judge"] = "self"
        self.assertEqual(ids(plan), ["G03", "G04"])

    def test_no_stop_condition_is_error(self):
        plan = base_plan()
        plan["stop"] = {"stop_file": ".run/STOP"}
        self.assertIn("S01", ids(plan, "ERROR"))

    def test_one_stop_condition_warns(self):
        plan = base_plan()
        del plan["stop"]["max_same_failure"]
        self.assertEqual(ids(plan), ["S02"])

    def test_stop_values_must_be_positive_integers(self):
        plan = base_plan()
        plan["stop"]["max_same_failure"] = 1.5
        self.assertIn("S04", ids(plan, "ERROR"))

    def test_missing_state_file_is_error(self):
        plan = base_plan()
        plan["checkpoints"] = {}
        self.assertEqual(ids(plan, "ERROR"), ["C01"])


class Approvals(unittest.TestCase):
    def test_ungated_consequential_action_is_error(self):
        plan = base_plan()
        plan["actions"].append("merge_pull_request")
        self.assertIn("A01", ids(plan, "ERROR"))

    def test_gated_action_passes_with_stop_on_timeout(self):
        plan = base_plan()
        plan["actions"].append("Deploy-Staging")
        plan["approvals"] = {"required_for": ["deploy-staging"], "approver": "owner", "on_timeout": "stop"}
        self.assertEqual(ids(plan), [])

    def test_plural_and_ing_forms_are_recognized(self):
        for action in ("sending_emails", "post_replies", "pushes_tags", "merging"):
            self.assertTrue(module.is_consequential(action), action)
        for action in ("write_commit_message", "run_acceptance_tests", "edit_files", "redesign_layout"):
            self.assertFalse(module.is_consequential(action), action)

    def test_timeout_that_approves_is_error(self):
        plan = base_plan()
        plan["actions"].append("send_message")
        plan["approvals"] = {"required_for": ["send_message"], "approver": "owner", "on_timeout": "Auto-Approve"}
        self.assertIn("A03", ids(plan, "ERROR"))

    def test_missing_timeout_and_approver_warn(self):
        plan = base_plan()
        plan["actions"].append("publish_package")
        plan["approvals"] = {"required_for": ["publish_package"]}
        self.assertEqual(ids(plan), ["A04", "A05"])

    def test_exemption_needs_reason(self):
        plan = base_plan()
        plan["actions"].append("push_run_branch")
        plan["approvals"] = {"not_required": [{"action": "push_run_branch"}], "on_timeout": "stop"}
        findings = [f for f in module.check_plan(plan) if f.code == "A02"]
        self.assertEqual([f.severity for f in findings], ["ERROR"])
        plan["approvals"]["not_required"][0]["reason"] = "own branch only, owner decision"
        findings = [f for f in module.check_plan(plan) if f.code == "A02"]
        self.assertEqual([f.severity for f in findings], ["WARN"])

    def test_missing_action_list_warns(self):
        plan = base_plan()
        del plan["actions"]
        self.assertEqual(ids(plan), ["A06"])


class PermissionsAndUnattended(unittest.TestCase):
    def test_bypass_is_error(self):
        for perms in ({"mode": "allowlist", "bypass": True}, {"mode": "bypassPermissions"}):
            plan = base_plan()
            plan["permissions"] = perms
            self.assertIn("P01", ids(plan, "ERROR"), perms)

    def test_open_network_warns(self):
        plan = base_plan()
        plan["permissions"]["network"] = "unrestricted"
        self.assertEqual(ids(plan), ["P03"])

    def test_schedule_without_isolation_or_overlap_warns(self):
        plan = base_plan()
        plan["schedule"] = {"cron": "5 3 * * *"}
        self.assertEqual(ids(plan), ["U01", "U02"])
        plan["schedule"]["overlap"] = "skip"
        plan["isolation"] = "container"
        self.assertEqual(ids(plan), [])


class Payments(unittest.TestCase):
    def paying_plan(self):
        plan = base_plan()
        plan["actions"].append("pay_api_invoice")
        plan["approvals"] = {"required_for": ["pay_api_invoice"], "approver": "owner", "on_timeout": "stop"}
        return plan

    def test_payment_without_policy_is_error(self):
        self.assertIn("M01", ids(self.paying_plan(), "ERROR"))

    def test_complete_policy_passes(self):
        plan = self.paying_plan()
        plan["spending"] = {"currency": "USD", "max_per_payment": 50, "max_per_session": 500,
                            "max_per_day": 1000, "allowed_recipients": ["acct_example_vendor"]}
        self.assertEqual(ids(plan), [])

    def test_float_caps_missing_recipients_and_inverted_caps(self):
        plan = self.paying_plan()
        plan["spending"] = {"currency": "USD", "max_per_payment": 0.5, "max_per_session": 100,
                            "max_per_day": 200, "allowed_recipients": []}
        self.assertEqual(ids(plan, "ERROR"), ["M02", "M04"])
        plan["spending"].update({"max_per_payment": 300, "allowed_recipients": ["acct_x"]})
        self.assertEqual(ids(plan, "ERROR"), ["M05"])

    def test_agent_set_policy_is_error(self):
        plan = self.paying_plan()
        plan["spending"] = {"currency": "EUR", "max_per_payment": 1, "max_per_session": 2, "max_per_day": 3,
                            "allowed_recipients": ["x"], "policy_set_by_agent": True}
        self.assertEqual(ids(plan, "ERROR"), ["M06"])


class Secrets(unittest.TestCase):
    def test_secret_values_are_reported_without_printing_them(self):
        plan = base_plan()
        fake = "sk" + "-" + "A1b2C3d4E5f6G7h8I9j0K1l2"  # built at runtime; not a real key
        plan["permissions"]["api_key"] = fake
        plan["notes"] = ["-----BEGIN " + "RSA PRIVATE KEY-----"]
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run_cli([write_plan(tmp, plan)])
        self.assertEqual(code, 1)
        self.assertIn("X01 permissions.api_key", out)
        self.assertIn("X01 notes[0]", out)
        self.assertNotIn(fake, out)

    def test_references_and_numbers_are_not_secrets(self):
        plan = base_plan()
        plan["permissions"]["token"] = "env:CI_BOT_TOKEN"
        plan["permissions"]["password_ref"] = "${DB_PASSWORD}"
        plan["permissions"]["auth_header"] = "VAULT_AUTH_HEADER"
        plan["budget"]["max_tokens"] = 30000000
        plan["token_note"] = "rotate monthly via the vault"
        self.assertEqual(ids(plan), [])


class Cli(unittest.TestCase):
    def test_json_output_and_strict_mode(self):
        plan = base_plan()
        del plan["budget"]["max_iterations"]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_plan(tmp, plan)
            code, out, _ = run_cli([path, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual((data["errors"], data["warnings"]), (0, 1))
            self.assertEqual(data["findings"][0]["id"], "B03")
            code, _, _ = run_cli([path, "--strict"])
            self.assertEqual(code, 1)

    def test_unreadable_and_invalid_plans_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([str(Path(tmp) / "missing.json")])
            self.assertEqual(code, 2)
            self.assertIn("cannot read", err)
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            self.assertEqual(run_cli([str(bad)])[0], 2)
            arr = Path(tmp) / "list.json"
            arr.write_text("[]", encoding="utf-8")
            self.assertEqual(run_cli([str(arr)])[0], 2)

    @unittest.skipUnless(sys.version_info >= (3, 11), "tomllib needs Python 3.11")
    def test_toml_plan(self):
        toml = "\n".join([
            "actions = ['edit_files']",
            "[goal]", "done_when = ['`make test` exits 0']", "must_not = ['delete tests']",
            "[budget]", "max_wall_clock_minutes = 20", "max_iterations = 3", "max_tokens = 100000",
            "[stop]", "no_progress_checkpoints = 2", "max_same_failure = 2", "stop_file = 'STOP'",
            "[checkpoints]", "state_file = 'state.json'", "commit_each_step = true",
            "[permissions]", "mode = 'allowlist'",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.toml"
            path.write_text(toml, encoding="utf-8")
            code, out, _ = run_cli([str(path)])
        self.assertEqual(code, 0, out)

    def test_output_is_deterministic(self):
        plan = copy.deepcopy(base_plan())
        plan["actions"] += ["deploy", "send_email", "merge"]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_plan(tmp, plan)
            first = run_cli([path])[1]
            second = run_cli([path])[1]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
