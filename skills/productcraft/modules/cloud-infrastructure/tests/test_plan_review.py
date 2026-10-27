"""Offline tests for plan_review.py using synthetic plan JSON only; no Terraform, cloud or network."""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "plan_review.py"
spec = importlib.util.spec_from_file_location("plan_review", SCRIPT)
pr = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pr
spec.loader.exec_module(pr)


def rc(address, rtype, actions, before=None, after=None, mode="managed", **extra):
    change = {"actions": actions, "before": before, "after": after, "after_unknown": extra.pop("after_unknown", {})}
    for key in ("importing", "replace_paths"):
        if key in extra:
            change[key] = extra.pop(key)
    entry = {"address": address, "mode": mode, "type": rtype, "name": address.split(".")[-1], "change": change}
    entry.update(extra)
    return entry


def plan(*changes, drift=(), **top):
    doc = {"format_version": "1.2", "terraform_version": "1.14.0", "resource_changes": list(changes),
           "resource_drift": list(drift), "planned_values": {}}
    doc.update(top)
    return doc


def codes(doc, **kw):
    _, findings, _ = pr.review(doc, **kw)
    return sorted({f.code for f in findings})


def run_cli(doc, *args):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "plan.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle)
        return run_raw(path, *args)


def run_raw(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = pr.main(list(args))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def policy(**statement):
    return json.dumps({"Version": "2012-10-17", "Statement": [dict(Effect="Allow", **statement)]})


class ActionTests(unittest.TestCase):
    def test_plain_create_has_no_findings(self):
        doc = plan(rc("aws_instance.web", "aws_instance", ["create"], None, {"instance_type": "t3.micro"}))
        self.assertEqual(codes(doc), [])
        code, out, _ = run_cli(doc, "--strict")
        self.assertEqual(code, 0)
        self.assertIn("create 1", out)

    def test_stateful_delete_is_high(self):
        doc = plan(rc("aws_db_instance.main", "aws_db_instance", ["delete"], {"identifier": "app"}, None))
        self.assertEqual(codes(doc), ["DELETE_STATEFUL"])
        self.assertEqual(run_cli(doc, "--fail-on", "high")[0], 1)

    def test_ordinary_delete_is_warn_and_passes_high_threshold(self):
        doc = plan(rc("aws_instance.old", "aws_instance", ["delete"], {"ami": "x"}, None))
        self.assertEqual(codes(doc), ["DELETE"])
        self.assertEqual(run_cli(doc, "--fail-on", "high")[0], 0)
        self.assertEqual(run_cli(doc, "--strict")[0], 1)

    def test_container_delete(self):
        doc = plan(rc("azurerm_resource_group.app", "azurerm_resource_group", ["delete"], {"name": "rg"}, None))
        self.assertEqual(codes(doc), ["DELETE_CONTAINER"])

    def test_replace_order_and_forcing_attribute(self):
        doc = plan(rc("aws_s3_bucket.data", "aws_s3_bucket", ["create", "delete"], {"bucket": "a"}, {"bucket": "b"},
                      replace_paths=[["bucket"]], action_reason="replace_because_cannot_update"))
        _, findings, _ = pr.review(doc)
        self.assertEqual([f.code for f in findings], ["REPLACE_STATEFUL"])
        self.assertIn("create-before-destroy", findings[0].detail)
        self.assertIn("forced by bucket", findings[0].detail)

    def test_plain_replace_is_warn(self):
        doc = plan(rc("aws_instance.web", "aws_instance", ["delete", "create"], {"ami": "a"}, {"ami": "b"}))
        _, findings, _ = pr.review(doc)
        self.assertEqual([(f.code, f.severity) for f in findings], [("REPLACE", "WARN")])
        self.assertIn("destroy-before-create", findings[0].detail)

    def test_forget_and_data_sources(self):
        doc = plan(rc("aws_instance.legacy", "aws_instance", ["forget"], {"ami": "a"}, None),
                   rc("data.aws_ami.base", "aws_ami", ["read"], None, {"id": "ami-1"}, mode="data"))
        self.assertEqual(codes(doc), ["FORGET"])

    def test_errored_plan(self):
        self.assertIn("PLAN_ERRORED", codes(plan(errored=True)))


class AccessTests(unittest.TestCase):
    def test_wildcard_action_in_inline_role_policy(self):
        doc = plan(rc("aws_iam_role_policy.app", "aws_iam_role_policy", ["create"], None,
                      {"name": "app", "policy": policy(Action="*", Resource="*")}))
        self.assertEqual(codes(doc), ["IAM_CHANGE", "IAM_WILDCARD"])

    def test_scoped_policy_is_only_iam_change(self):
        doc = plan(rc("aws_iam_policy.read", "aws_iam_policy", ["create"], None,
                      {"policy": policy(Action=["s3:GetObject"], Resource="arn:aws:s3:::b/*")}))
        self.assertEqual(codes(doc), ["IAM_CHANGE"])

    def test_public_principal_without_condition(self):
        doc = plan(rc("aws_s3_bucket_policy.site", "aws_s3_bucket_policy", ["update"], {"policy": "{}"},
                      {"policy": policy(Principal="*", Action="s3:GetObject", Resource="arn:aws:s3:::b/*")}))
        self.assertIn("IAM_WILDCARD", codes(doc))

    def test_unknown_policy_is_noted(self):
        doc = plan(rc("aws_iam_role.app", "aws_iam_role", ["create"], None, {"name": "app"},
                      after_unknown={"assume_role_policy": True}))
        self.assertIn("POLICY_UNKNOWN", codes(doc))

    def test_administrator_attachment(self):
        doc = plan(rc("aws_iam_role_policy_attachment.admin", "aws_iam_role_policy_attachment", ["create"], None,
                      {"policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess", "role": "ci"}))
        self.assertIn("IAM_WILDCARD", codes(doc))

    def test_azure_owner_and_scoped_contributor(self):
        owner = plan(rc("azurerm_role_assignment.o", "azurerm_role_assignment", ["create"], None,
                        {"role_definition_name": "Owner", "scope": "/subscriptions/00000000-0000-0000-0000-000000000000"}))
        self.assertIn("IAM_WILDCARD", codes(owner))
        scoped = plan(rc("azurerm_role_assignment.c", "azurerm_role_assignment", ["create"], None,
                         {"role_definition_name": "Contributor",
                          "scope": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/app"}))
        self.assertEqual(codes(scoped), ["IAM_CHANGE"])

    def test_cluster_admin_binding(self):
        doc = plan(rc("kubernetes_cluster_role_binding.ci", "kubernetes_cluster_role_binding", ["create"], None,
                      {"role_ref": [{"kind": "ClusterRole", "name": "cluster-admin"}]}))
        self.assertIn("IAM_WILDCARD", codes(doc))

    def test_iam_delete_is_flagged(self):
        doc = plan(rc("aws_iam_role.old", "aws_iam_role", ["delete"], {"name": "old"}, None))
        self.assertEqual(codes(doc), ["DELETE", "IAM_CHANGE"])


class NetworkAndDataTests(unittest.TestCase):
    def test_ssh_from_anywhere_vs_https(self):
        doc = plan(rc("aws_security_group.web", "aws_security_group", ["create"], None, {"ingress": [
            {"from_port": 22, "to_port": 22, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"], "ipv6_cidr_blocks": []},
            {"from_port": 443, "to_port": 443, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"], "ipv6_cidr_blocks": []},
        ]}))
        _, findings, _ = pr.review(doc)
        got = {(f.code, f.detail) for f in findings}
        self.assertIn(("PUBLIC_INGRESS", "from 0.0.0.0/0 to ports 22"), got)
        self.assertIn(("PUBLIC_WEB_INGRESS", "from 0.0.0.0/0 to ports 443"), got)

    def test_all_protocols_rule(self):
        doc = plan(rc("aws_vpc_security_group_ingress_rule.all", "aws_vpc_security_group_ingress_rule", ["create"], None,
                      {"ip_protocol": "-1", "cidr_ipv6": "::/0"}))
        self.assertEqual(codes(doc), ["PUBLIC_INGRESS"])

    def test_private_cidr_is_quiet(self):
        doc = plan(rc("aws_security_group_rule.db", "aws_security_group_rule", ["create"], None,
                      {"type": "ingress", "from_port": 5432, "to_port": 5432, "protocol": "tcp", "cidr_blocks": ["10.0.0.0/16"]}))
        self.assertEqual(codes(doc), [])

    def test_azure_nsg_rule_from_internet(self):
        doc = plan(rc("azurerm_network_security_rule.rdp", "azurerm_network_security_rule", ["create"], None,
                      {"direction": "Inbound", "access": "Allow", "source_address_prefix": "Internet",
                       "destination_port_range": "3389"}))
        self.assertEqual(codes(doc), ["PUBLIC_INGRESS"])

    def test_gcp_firewall_without_ports_means_all(self):
        doc = plan(rc("google_compute_firewall.open", "google_compute_firewall", ["create"], None,
                      {"source_ranges": ["0.0.0.0/0"], "allow": [{"protocol": "tcp", "ports": []}]}))
        self.assertEqual(codes(doc), ["PUBLIC_INGRESS"])

    def test_public_bucket_settings(self):
        doc = plan(
            rc("aws_s3_bucket_public_access_block.b", "aws_s3_bucket_public_access_block", ["update"],
               {"block_public_acls": True}, {"block_public_acls": False, "block_public_policy": True,
                                            "ignore_public_acls": True, "restrict_public_buckets": True}),
            rc("google_storage_bucket_iam_member.pub", "google_storage_bucket_iam_member", ["create"], None,
               {"member": "allUsers", "role": "roles/storage.objectViewer"}),
            rc("aws_db_instance.db", "aws_db_instance", ["update"], {"publicly_accessible": False},
               {"publicly_accessible": True}),
        )
        _, findings, _ = pr.review(doc)
        public = sorted(f.address for f in findings if f.code == "PUBLIC_DATA")
        self.assertEqual(public, ["aws_db_instance.db", "aws_s3_bucket_public_access_block.b",
                                  "google_storage_bucket_iam_member.pub"])

    def test_protection_and_encryption(self):
        doc = plan(
            rc("aws_rds_cluster.main", "aws_rds_cluster", ["update"], {"deletion_protection": True, "storage_encrypted": True},
               {"deletion_protection": False, "storage_encrypted": True}),
            rc("aws_s3_bucket.logs", "aws_s3_bucket", ["update"], {"force_destroy": False}, {"force_destroy": True}),
            rc("aws_ebs_volume.scratch", "aws_ebs_volume", ["create"], None, {"encrypted": False}),
        )
        _, findings, _ = pr.review(doc)
        got = {(f.code, f.address) for f in findings}
        self.assertIn(("PROTECTION_OFF", "aws_rds_cluster.main"), got)
        self.assertIn(("PROTECTION_OFF", "aws_s3_bucket.logs"), got)
        self.assertIn(("ENCRYPTION_OFF", "aws_ebs_volume.scratch"), got)


class RefactorAndImportTests(unittest.TestCase):
    def test_import_and_move(self):
        doc = plan(
            rc("aws_sqs_queue.jobs", "aws_sqs_queue", ["no-op"], {"name": "jobs"}, {"name": "jobs"}, importing={"id": "q"}),
            rc("module.net.aws_vpc.main", "aws_vpc", ["no-op"], {}, {}, previous_address="aws_vpc.main"),
        )
        summary, findings, _ = pr.review(doc, expect_no_changes=True)
        self.assertEqual(sorted(f.code for f in findings), ["IMPORT", "MOVE"])
        self.assertEqual((summary["import"], summary["move"]), (1, 1))

    def test_import_with_update_and_unexpected_change(self):
        doc = plan(rc("aws_sqs_queue.jobs", "aws_sqs_queue", ["update"], {"delay_seconds": 0}, {"delay_seconds": 5},
                      importing={"id": "q"}))
        self.assertEqual(codes(doc, expect_no_changes=True), ["IMPORT_WITH_CHANGES", "UNEXPECTED_CHANGE"])

    def test_drift_lists_attribute_names_only(self):
        secret = "pw-" + "q" * 20
        doc = plan(drift=[rc("aws_db_instance.db", "aws_db_instance", ["update"], {"password": "a", "port": 5432},
                             {"password": secret, "port": 5432})])
        code, out, _ = run_cli(doc)
        self.assertEqual(code, 0)
        self.assertIn("DRIFT", out)
        self.assertIn("password", out)
        self.assertNotIn(secret, out)


class OutputAndCliTests(unittest.TestCase):
    def test_values_never_printed_with_show_changes(self):
        secret = "tok-" + "z" * 24
        doc = plan(rc("aws_ssm_parameter.api", "aws_ssm_parameter", ["update"], {"value": "old"}, {"value": secret}))
        for args in (("--show-changes",), ("--show-changes", "--json")):
            code, out, _ = run_cli(doc, *args)
            self.assertEqual(code, 0)
            self.assertIn("value", out)
            self.assertNotIn(secret, out)

    def test_json_report_is_deterministic(self):
        doc = plan(rc("aws_instance.b", "aws_instance", ["delete"], {"a": 1}, None),
                   rc("aws_db_instance.a", "aws_db_instance", ["delete"], {"a": 1}, None))
        first = run_cli(doc, "--json")[1]
        self.assertEqual(first, run_cli(doc, "--json")[1])
        report = json.loads(first)
        self.assertEqual([f["rule"] for f in report["findings"]], ["DELETE_STATEFUL", "DELETE"])
        self.assertIn("not_checked", report)

    def test_input_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as handle:
                handle.write("not json")
            self.assertEqual(run_raw(bad)[0], 2)
            state = os.path.join(tmp, "state.json")
            with open(state, "w", encoding="utf-8") as handle:
                json.dump({"format_version": "1.0", "values": {}}, handle)
            code, _, err = run_raw(state)
            self.assertEqual(code, 2)
            self.assertIn("state, not a plan", err)
        self.assertEqual(run_raw(os.path.join("no", "such", "plan.json"))[0], 2)
        self.assertEqual(run_raw()[0], 2)

    def test_list_rules_and_help(self):
        code, out, _ = run_raw("--list-rules")
        self.assertEqual(code, 0)
        self.assertIn("DELETE_STATEFUL", out)
        self.assertEqual(run_raw("--help")[0], 0)


if __name__ == "__main__":
    unittest.main()
