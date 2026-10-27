#!/usr/bin/env python3
"""ProductCraft Cloud Infrastructure: read-only review of a Terraform or OpenTofu plan.

Reads the JSON form of a saved plan and lists the changes a human must look at
before anyone applies it: deletions and replacements (with extra weight for
resources that hold data or contain other resources), protection switched off,
identity and access changes, wildcard grants, inbound access from anywhere,
publicly readable data, storage without encryption, imports that also change
the resource, state-only removals and drift detected outside Terraform.

Produce the input with:

    terraform plan -out=tfplan
    terraform show -json tfplan > plan.json      # or: tofu show -json tfplan

The JSON contains sensitive values in clear text. Keep it out of version
control and public CI artifacts, and delete it after the review. This script
never prints attribute values except network ranges, ports and role names.

It never runs Terraform, never contacts a cloud and never uses the network.
Findings are prompts for review, not verdicts, and a clean result does not make
a plan safe to apply.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
SEVERITY_ORDER = {"HIGH": 0, "WARN": 1, "INFO": 2}
LEVELS = {"high": "HIGH", "warn": "WARN", "info": "INFO"}


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    title: str


RULE_LIST = [
    Rule("PLAN_ERRORED", "HIGH", "The plan reports errors or is incomplete; only the listed changes were reviewed."),
    Rule("UNEXPECTED_CHANGE", "HIGH", "--expect-no-changes was given, but the plan changes real infrastructure."),
    Rule("DELETE_CONTAINER", "HIGH", "Deletes a container (resource group, project, namespace, account) and everything in it."),
    Rule("DELETE_STATEFUL", "HIGH", "Deletes a resource that holds data, keys or identity; the loss is usually permanent."),
    Rule("REPLACE_STATEFUL", "HIGH", "Destroys and recreates a resource that holds data, keys or identity."),
    Rule("PROTECTION_OFF", "HIGH", "Switches off deletion protection, allows force-destroy or skips the final snapshot."),
    Rule("IAM_WILDCARD", "HIGH", "Grants a wildcard action, a public principal or an administrator-level role."),
    Rule("PUBLIC_INGRESS", "HIGH", "Opens inbound access from anywhere on ports other than 80 and 443."),
    Rule("PUBLIC_DATA", "HIGH", "Makes stored data or a database reachable by anyone."),
    Rule("DELETE", "WARN", "Deletes a resource."),
    Rule("REPLACE", "WARN", "Replaces a resource; expect downtime and new identifiers unless it is create-before-destroy."),
    Rule("IAM_CHANGE", "WARN", "Changes identity, roles or access policy; this needs the owner's explicit approval."),
    Rule("ENCRYPTION_OFF", "WARN", "Storage is created or changed with encryption at rest switched off."),
    Rule("IMPORT_WITH_CHANGES", "WARN", "Imports a resource and changes it in the same apply; align the configuration first."),
    Rule("FORGET", "WARN", "Removes a resource from state without destroying it; Terraform stops managing it."),
    Rule("DRIFT", "WARN", "The real resource changed outside Terraform since the last apply."),
    Rule("POLICY_UNKNOWN", "INFO", "An access policy is only known after apply; review its source configuration."),
    Rule("PUBLIC_WEB_INGRESS", "INFO", "Opens port 80 or 443 to anywhere; confirm this is the intended public entry point."),
    Rule("IMPORT", "INFO", "Imports an existing resource into state without changing it."),
    Rule("MOVE", "INFO", "Moves a resource to a new address in state."),
]
RULES = {r.code: r for r in RULE_LIST}

# Resources whose deletion or replacement loses data, keys or identity.
STATEFUL_TYPES = frozenset({
    # AWS
    "aws_db_instance", "aws_rds_cluster", "aws_rds_cluster_instance", "aws_dynamodb_table",
    "aws_s3_bucket", "aws_ebs_volume", "aws_efs_file_system", "aws_kms_key",
    "aws_elasticache_cluster", "aws_elasticache_replication_group", "aws_memorydb_cluster",
    "aws_route53_zone", "aws_secretsmanager_secret", "aws_sqs_queue", "aws_kinesis_stream",
    "aws_cognito_user_pool", "aws_docdb_cluster", "aws_neptune_cluster", "aws_redshift_cluster",
    "aws_opensearch_domain", "aws_elasticsearch_domain", "aws_msk_cluster", "aws_backup_vault",
    "aws_ecr_repository", "aws_cloudwatch_log_group", "aws_glacier_vault", "aws_fsx_lustre_file_system",
    # Azure
    "azurerm_storage_account", "azurerm_storage_container", "azurerm_key_vault", "azurerm_key_vault_key",
    "azurerm_key_vault_secret", "azurerm_mssql_server", "azurerm_mssql_database",
    "azurerm_postgresql_flexible_server", "azurerm_mysql_flexible_server", "azurerm_cosmosdb_account",
    "azurerm_managed_disk", "azurerm_redis_cache", "azurerm_container_registry",
    "azurerm_log_analytics_workspace", "azurerm_recovery_services_vault", "azurerm_dns_zone",
    "azurerm_servicebus_namespace", "azurerm_eventhub_namespace",
    # Google Cloud
    "google_sql_database_instance", "google_sql_database", "google_storage_bucket", "google_compute_disk",
    "google_kms_crypto_key", "google_kms_key_ring", "google_bigquery_dataset", "google_bigquery_table",
    "google_spanner_instance", "google_spanner_database", "google_bigtable_instance", "google_redis_instance",
    "google_filestore_instance", "google_dns_managed_zone", "google_secret_manager_secret",
    "google_artifact_registry_repository",
    # Kubernetes and generated secrets
    "kubernetes_persistent_volume_claim", "kubernetes_persistent_volume_claim_v1",
    "kubernetes_persistent_volume", "kubernetes_persistent_volume_v1",
    "random_password", "tls_private_key",
})

CONTAINER_TYPES = frozenset({
    "azurerm_resource_group", "azurerm_subscription", "azurerm_management_group",
    "google_project", "google_folder", "aws_organizations_account",
    "kubernetes_namespace", "kubernetes_namespace_v1",
})

IAM_EXACT = frozenset({
    "azurerm_role_assignment", "azurerm_role_definition",
    "kubernetes_cluster_role", "kubernetes_cluster_role_v1", "kubernetes_cluster_role_binding",
    "kubernetes_cluster_role_binding_v1", "kubernetes_role", "kubernetes_role_v1",
    "kubernetes_role_binding", "kubernetes_role_binding_v1",
    "aws_s3_bucket_policy", "aws_sqs_queue_policy", "aws_sns_topic_policy", "aws_lambda_permission",
    "aws_kms_key_policy", "aws_ecr_repository_policy", "aws_secretsmanager_secret_policy",
})
IAM_PREFIXES = ("aws_iam_", "azuread_")

PROTECTION_FLAGS = ("deletion_protection", "deletion_protection_enabled", "enable_deletion_protection",
                    "disable_api_termination")
POLICY_ATTRS = ("policy", "assume_role_policy")
ADMIN_AZURE_ROLES = frozenset({"owner", "user access administrator", "role based access control administrator"})
ADMIN_GOOGLE_ROLES = frozenset({"roles/owner", "roles/editor"})
PUBLIC_MEMBERS = frozenset({"allusers", "allauthenticatedusers"})
ANYWHERE = frozenset({"0.0.0.0/0", "::/0", "*", "internet", "any"})
WEB_PORTS = frozenset({80, 443})


@dataclass
class Finding:
    severity: str
    code: str
    address: str
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"severity": self.severity, "rule": self.code, "address": self.address,
                "title": RULES[self.code].title, "detail": self.detail}


class InputError(Exception):
    pass


def classify(actions: Sequence[str]) -> str:
    acts = list(actions or [])
    if acts in (["delete", "create"], ["create", "delete"]):
        return "replace"
    if len(acts) == 1 and acts[0] in ("create", "update", "delete", "read", "no-op", "forget"):
        return acts[0]
    if not acts:
        return "no-op"
    return "+".join(acts)


def is_stateful(rtype: str) -> bool:
    return rtype in STATEFUL_TYPES


def is_iam(rtype: str) -> bool:
    return (rtype in IAM_EXACT or rtype.startswith(IAM_PREFIXES)
            or (rtype.startswith("google_") and "_iam_" in rtype))


def truthy(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.lower() == "true")


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def changed_attributes(before: Any, after: Any, after_unknown: Any) -> List[str]:
    names = set()
    b = before if isinstance(before, dict) else {}
    a = after if isinstance(after, dict) else {}
    for key in set(b) | set(a):
        if b.get(key) != a.get(key):
            names.add(key)
    if isinstance(after_unknown, dict):
        names.update(k for k, v in after_unknown.items() if v)
    return sorted(names)


# ---------------------------------------------------------------- policy checks

def policy_statements(raw: Any) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(doc, dict):
        return None
    return [s for s in as_list(doc.get("Statement")) if isinstance(s, dict)]


def wildcard_reasons(statements: Iterable[Dict[str, Any]]) -> List[str]:
    reasons = []
    for st in statements:
        if str(st.get("Effect", "")).lower() != "allow":
            continue
        actions = [str(a) for a in as_list(st.get("Action"))]
        if "*" in actions:
            reasons.append('Allow with Action "*"')
        if "NotAction" in st:
            reasons.append("Allow with NotAction")
        principal = st.get("Principal")
        public = principal == "*" or (isinstance(principal, dict) and "*" in as_list(principal.get("AWS")))
        if public and not st.get("Condition"):
            reasons.append('Principal "*" without a Condition')
    return reasons


def check_iam(addr: str, rtype: str, after: Dict[str, Any], unknown: Dict[str, Any], out: List[Finding]) -> None:
    reasons: List[str] = []
    for attr in POLICY_ATTRS:
        if unknown.get(attr):
            out.append(Finding("INFO", "POLICY_UNKNOWN", addr, f"attribute {attr}"))
        sts = policy_statements(after.get(attr))
        if sts:
            reasons += [f"{attr}: {r}" for r in wildcard_reasons(sts)]
    for item in as_list(after.get("inline_policy")):
        if isinstance(item, dict):
            sts = policy_statements(item.get("policy"))
            if sts:
                reasons += [f"inline_policy: {r}" for r in wildcard_reasons(sts)]
    policy_arn = str(after.get("policy_arn") or "")
    if policy_arn.endswith(":policy/AdministratorAccess"):
        reasons.append("attaches AdministratorAccess")
    for arn in as_list(after.get("managed_policy_arns")):
        if str(arn).endswith(":policy/AdministratorAccess"):
            reasons.append("attaches AdministratorAccess")
    if rtype == "azurerm_role_assignment":
        role = str(after.get("role_definition_name") or "").lower()
        scope = str(after.get("scope") or "")
        broad_scope = "/resourcegroups/" not in scope.lower()
        if role in ADMIN_AZURE_ROLES:
            reasons.append(f"role {after.get('role_definition_name')}")
        elif role == "contributor" and broad_scope:
            reasons.append("role Contributor at subscription or wider scope")
    if rtype.startswith("google_") and "_iam_" in rtype:
        role = str(after.get("role") or "").lower()
        if role in ADMIN_GOOGLE_ROLES:
            reasons.append(f"role {after.get('role')}")
    if rtype.startswith("kubernetes_cluster_role") and "binding" not in rtype:
        for rule in as_list(after.get("rule")):
            if isinstance(rule, dict) and "*" in as_list(rule.get("verbs")) and "*" in as_list(rule.get("resources")):
                reasons.append('rule with verbs "*" on resources "*"')
    if rtype.startswith("kubernetes_cluster_role_binding"):
        for ref in as_list(after.get("role_ref")):
            if isinstance(ref, dict) and str(ref.get("name")) == "cluster-admin":
                reasons.append("binds cluster-admin")
    for reason in sorted(set(reasons)):
        out.append(Finding("HIGH", "IAM_WILDCARD", addr, reason))


# ---------------------------------------------------------------- network checks

def port_span(lo: Any, hi: Any) -> Tuple[int, int]:
    try:
        return int(lo), int(hi)
    except (TypeError, ValueError):
        return 0, 65535


def web_only(spans: List[Tuple[int, int]]) -> bool:
    return bool(spans) and all(a == b and a in WEB_PORTS for a, b in spans)


def parse_port_text(text: Any) -> List[Tuple[int, int]]:
    spans = []
    for part in as_list(text):
        p = str(part).strip()
        if not p or p in ("*", "any"):
            return [(0, 65535)]
        if "-" in p:
            lo, _, hi = p.partition("-")
            spans.append(port_span(lo, hi))
        else:
            spans.append(port_span(p, p))
    return spans or [(0, 65535)]


def report_ingress(addr: str, sources: Iterable[Any], spans: List[Tuple[int, int]], out: List[Finding]) -> None:
    open_from = sorted({str(s) for s in sources if str(s).strip().lower() in ANYWHERE})
    if not open_from:
        return
    ports = ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in sorted(set(spans)))
    code = "PUBLIC_WEB_INGRESS" if web_only(spans) else "PUBLIC_INGRESS"
    out.append(Finding(RULES[code].severity, code, addr, f"from {', '.join(open_from)} to ports {ports}"))


def all_protocols(proto: Any) -> bool:
    return str(proto).lower() in ("-1", "all", "*")


def check_network(addr: str, rtype: str, after: Dict[str, Any], out: List[Finding]) -> None:
    if rtype == "aws_security_group":
        for rule in as_list(after.get("ingress")):
            if isinstance(rule, dict):
                spans = [(0, 65535)] if all_protocols(rule.get("protocol")) else [port_span(rule.get("from_port"), rule.get("to_port"))]
                report_ingress(addr, as_list(rule.get("cidr_blocks")) + as_list(rule.get("ipv6_cidr_blocks")), spans, out)
    elif rtype == "aws_security_group_rule" and after.get("type") == "ingress":
        spans = [(0, 65535)] if all_protocols(after.get("protocol")) else [port_span(after.get("from_port"), after.get("to_port"))]
        report_ingress(addr, as_list(after.get("cidr_blocks")) + as_list(after.get("ipv6_cidr_blocks")), spans, out)
    elif rtype == "aws_vpc_security_group_ingress_rule":
        spans = [(0, 65535)] if all_protocols(after.get("ip_protocol")) else [port_span(after.get("from_port"), after.get("to_port"))]
        report_ingress(addr, [after.get("cidr_ipv4"), after.get("cidr_ipv6")], spans, out)
    elif rtype in ("azurerm_network_security_rule", "azurerm_network_security_group"):
        rules = [after] if rtype == "azurerm_network_security_rule" else as_list(after.get("security_rule"))
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if str(rule.get("direction", "")).lower() != "inbound" or str(rule.get("access", "")).lower() != "allow":
                continue
            sources = [rule.get("source_address_prefix")] + as_list(rule.get("source_address_prefixes"))
            ports = as_list(rule.get("destination_port_range")) + as_list(rule.get("destination_port_ranges"))
            report_ingress(addr, sources, parse_port_text([p for p in ports if p not in (None, "")]), out)
    elif rtype == "google_compute_firewall":
        if str(after.get("direction") or "INGRESS").upper() != "INGRESS":
            return
        spans: List[Tuple[int, int]] = []
        for allow in as_list(after.get("allow")):
            if isinstance(allow, dict):
                ports = as_list(allow.get("ports"))
                spans += parse_port_text(ports) if ports else [(0, 65535)]
        if spans:
            report_ingress(addr, as_list(after.get("source_ranges")), spans, out)


# ---------------------------------------------------------------- data exposure and protection

def check_data(addr: str, rtype: str, before: Dict[str, Any], after: Dict[str, Any], out: List[Finding]) -> None:
    if rtype in ("aws_db_instance", "aws_rds_cluster_instance") and truthy(after.get("publicly_accessible")):
        out.append(Finding("HIGH", "PUBLIC_DATA", addr, "publicly_accessible = true"))
    if rtype == "aws_s3_bucket_public_access_block":
        off = [k for k in ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets")
               if k in after and not truthy(after.get(k))]
        if off:
            out.append(Finding("HIGH", "PUBLIC_DATA", addr, "public access block off: " + ", ".join(off)))
    if rtype == "aws_s3_bucket_acl" and str(after.get("acl", "")) in ("public-read", "public-read-write", "authenticated-read"):
        out.append(Finding("HIGH", "PUBLIC_DATA", addr, f"acl {after.get('acl')}"))
    if rtype == "azurerm_storage_account" and truthy(after.get("allow_nested_items_to_be_public")):
        out.append(Finding("HIGH", "PUBLIC_DATA", addr, "allow_nested_items_to_be_public = true"))
    if rtype == "azurerm_storage_container" and str(after.get("container_access_type", "")).lower() in ("blob", "container"):
        out.append(Finding("HIGH", "PUBLIC_DATA", addr, f"container_access_type {after.get('container_access_type')}"))
    if rtype.startswith("google_") and "_iam_" in rtype:
        members = as_list(after.get("member")) + as_list(after.get("members"))
        public = sorted({str(m) for m in members if str(m).lower() in PUBLIC_MEMBERS})
        if public:
            out.append(Finding("HIGH", "PUBLIC_DATA", addr, "grants to " + ", ".join(public)))
    if rtype == "google_sql_database_instance":
        for settings in as_list(after.get("settings")):
            for ipc in as_list(settings.get("ip_configuration") if isinstance(settings, dict) else None):
                for net in as_list(ipc.get("authorized_networks") if isinstance(ipc, dict) else None):
                    if isinstance(net, dict) and str(net.get("value")) in ("0.0.0.0/0", "::/0"):
                        out.append(Finding("HIGH", "PUBLIC_DATA", addr, "authorized network 0.0.0.0/0"))
    encryption = {"aws_db_instance": "storage_encrypted", "aws_rds_cluster": "storage_encrypted",
                  "aws_ebs_volume": "encrypted", "aws_efs_file_system": "encrypted"}
    attr = encryption.get(rtype)
    if attr and attr in after and after.get(attr) is False:
        out.append(Finding("WARN", "ENCRYPTION_OFF", addr, f"{attr} = false"))
    for flag in PROTECTION_FLAGS:
        if truthy(before.get(flag)) and flag in after and not truthy(after.get(flag)):
            out.append(Finding("HIGH", "PROTECTION_OFF", addr, f"{flag}: true -> false"))
    if truthy(after.get("force_destroy")) and not truthy(before.get("force_destroy")):
        out.append(Finding("HIGH", "PROTECTION_OFF", addr, "force_destroy set to true"))
    if rtype in ("aws_db_instance", "aws_rds_cluster") and truthy(after.get("skip_final_snapshot")) \
            and not truthy(before.get("skip_final_snapshot")) and before:
        out.append(Finding("HIGH", "PROTECTION_OFF", addr, "skip_final_snapshot set to true"))


# ---------------------------------------------------------------- driver

def load_plan(path: str) -> Dict[str, Any]:
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}")
    try:
        plan = json.loads(text)
    except ValueError as exc:
        raise InputError(f"{path} is not JSON ({exc}). Pass the output of 'terraform show -json PLANFILE'.")
    if not isinstance(plan, dict) or "format_version" not in plan:
        raise InputError(f"{path} is not a Terraform JSON document (no format_version).")
    if "resource_changes" not in plan and "planned_values" not in plan:
        raise InputError(f"{path} looks like state, not a plan. Run 'terraform show -json' on a saved plan file.")
    return plan


def review(plan: Dict[str, Any], expect_no_changes: bool = False) -> Tuple[Dict[str, int], List[Finding], List[Dict[str, Any]]]:
    summary = {k: 0 for k in ("create", "update", "replace", "delete", "forget", "read", "no-op", "import", "move")}
    findings: List[Finding] = []
    changes: List[Dict[str, Any]] = []
    if plan.get("errored") is True or plan.get("complete") is False:
        findings.append(Finding("HIGH", "PLAN_ERRORED", "(plan)", "errored or incomplete plan"))
    for rc in plan.get("resource_changes") or []:
        if not isinstance(rc, dict):
            continue
        addr = str(rc.get("address", "?"))
        if rc.get("deposed"):
            addr = f"{addr} (deposed {rc.get('deposed')})"
        rtype = str(rc.get("type", ""))
        change = rc.get("change") or {}
        kind = classify(change.get("actions") or [])
        summary[kind] = summary.get(kind, 0) + 1
        if rc.get("mode") == "data":
            continue
        before = change.get("before") if isinstance(change.get("before"), dict) else {}
        after = change.get("after") if isinstance(change.get("after"), dict) else {}
        unknown = change.get("after_unknown") if isinstance(change.get("after_unknown"), dict) else {}
        importing = change.get("importing")
        moved_from = rc.get("previous_address")
        if importing:
            summary["import"] += 1
        if moved_from:
            summary["move"] += 1
            findings.append(Finding("INFO", "MOVE", addr, f"from {moved_from}"))
        if kind != "no-op" or importing or moved_from:
            changes.append({"address": addr, "action": kind, "imported": bool(importing),
                            "moved_from": moved_from,
                            "attributes": changed_attributes(before, after, unknown) if kind == "update" else []})
        reason = rc.get("action_reason")
        why = f"reason {reason}" if reason else ""
        if importing:
            if kind == "no-op":
                findings.append(Finding("INFO", "IMPORT", addr, ""))
            else:
                findings.append(Finding("WARN", "IMPORT_WITH_CHANGES", addr, f"import plus {kind}"))
        if kind == "delete":
            if rtype in CONTAINER_TYPES:
                findings.append(Finding("HIGH", "DELETE_CONTAINER", addr, why))
            elif is_stateful(rtype):
                findings.append(Finding("HIGH", "DELETE_STATEFUL", addr, why))
            else:
                findings.append(Finding("WARN", "DELETE", addr, why))
        elif kind == "replace":
            order = "create-before-destroy" if change.get("actions") == ["create", "delete"] else "destroy-before-create"
            paths = change.get("replace_paths") or []
            forced = sorted({str(p[0]) for p in paths if isinstance(p, list) and p})
            detail = order + (f"; forced by {', '.join(forced)}" if forced else "") + (f"; {why}" if why else "")
            code = "REPLACE_STATEFUL" if (is_stateful(rtype) or rtype in CONTAINER_TYPES) else "REPLACE"
            findings.append(Finding(RULES[code].severity, code, addr, detail))
        elif kind == "forget":
            findings.append(Finding("WARN", "FORGET", addr, ""))
        if kind in ("create", "update", "replace") or (importing and kind != "delete"):
            if is_iam(rtype):
                findings.append(Finding("WARN", "IAM_CHANGE", addr, kind))
                check_iam(addr, rtype, after, unknown, findings)
            check_network(addr, rtype, after, findings)
            check_data(addr, rtype, before, after, findings)
        elif kind == "delete" and is_iam(rtype):
            findings.append(Finding("WARN", "IAM_CHANGE", addr, "delete"))
        if expect_no_changes and kind in ("create", "update", "replace", "delete", "forget"):
            findings.append(Finding("HIGH", "UNEXPECTED_CHANGE", addr, kind))
    for rd in plan.get("resource_drift") or []:
        if not isinstance(rd, dict) or rd.get("mode") == "data":
            continue
        ch = rd.get("change") or {}
        kind = classify(ch.get("actions") or [])
        if kind == "no-op":
            continue
        attrs = changed_attributes(ch.get("before"), ch.get("after"), None)
        detail = "deleted outside Terraform" if kind == "delete" else ("changed: " + ", ".join(attrs[:12]) if attrs else kind)
        findings.append(Finding("WARN", "DRIFT", str(rd.get("address", "?")), detail))
    findings = dedupe(findings)
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.address, f.code, f.detail))
    return summary, findings, changes


def dedupe(findings: List[Finding]) -> List[Finding]:
    seen = set()
    result = []
    for f in findings:
        key = (f.severity, f.code, f.address, f.detail)
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


NOT_CHECKED = [
    "values of sensitive attributes (never printed)",
    "settings that only exist in configuration, such as lifecycle prevent_destroy",
    "provider defaults that do not appear in the plan, and resource types outside the built-in lists",
    "cost of the change",
    "whether the plan was made against the intended account, subscription, project or workspace",
]


def render_text(plan: Dict[str, Any], summary: Dict[str, int], findings: List[Finding],
                changes: List[Dict[str, Any]], show_changes: bool) -> str:
    lines = [f"plan_review {VERSION}: Terraform {plan.get('terraform_version', 'unknown')}, "
             f"format {plan.get('format_version')}"]
    lines.append("Summary: " + ", ".join(f"{k} {summary[k]}" for k in
                                       ("create", "update", "replace", "delete", "forget", "import", "move", "read")))
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER}
    lines.append(f"Findings: HIGH {counts['HIGH']}, WARN {counts['WARN']}, INFO {counts['INFO']}")
    for f in findings:
        detail = f" ({f.detail})" if f.detail else ""
        lines.append(f"  {f.severity:<4} {f.code:<19} {f.address}{detail}")
        lines.append(f"       {RULES[f.code].title}")
    if show_changes and changes:
        lines.append("Changes:")
        for c in changes:
            extra = []
            if c["moved_from"]:
                extra.append(f"moved from {c['moved_from']}")
            if c["imported"]:
                extra.append("import")
            if c["attributes"]:
                extra.append("attributes: " + ", ".join(c["attributes"]))
            lines.append(f"  {c['action']:<8} {c['address']}" + (f" [{'; '.join(extra)}]" if extra else ""))
    lines.append("Not checked: " + "; ".join(NOT_CHECKED) + ".")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plan_review.py",
        description="Read-only review of a Terraform or OpenTofu plan in JSON form "
                    "(terraform show -json PLANFILE). Never runs Terraform and never uses the network.",
        epilog="Exit codes: 0 report written and no finding at or above --fail-on; "
               "1 findings at or above --fail-on (or HIGH/WARN with --strict); 2 usage or input error.")
    p.add_argument("plan", nargs="?", help="path to the plan JSON, or - for stdin")
    p.add_argument("--json", action="store_true", help="print a JSON report instead of text")
    p.add_argument("--fail-on", choices=sorted(LEVELS), help="exit 1 when a finding at this level or above exists")
    p.add_argument("--strict", action="store_true", help="same as --fail-on warn")
    p.add_argument("--expect-no-changes", action="store_true",
                   help="treat any create, update, replace, delete or forget as HIGH (for refactors and imports)")
    p.add_argument("--show-changes", action="store_true",
                   help="also list every changed resource with the names (not values) of changed attributes")
    p.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_rules:
        for r in RULE_LIST:
            print(f"{r.code:<19} {r.severity:<4} {r.title}")
        return 0
    if not args.plan:
        parser.print_usage(sys.stderr)
        print("plan_review.py: error: a plan JSON path (or -) is required", file=sys.stderr)
        return 2
    try:
        plan = load_plan(args.plan)
    except InputError as exc:
        print(f"plan_review.py: error: {exc}", file=sys.stderr)
        return 2
    summary, findings, changes = review(plan, expect_no_changes=args.expect_no_changes)
    if args.json:
        print(json.dumps({"tool": "plan_review", "version": VERSION,
                          "terraform_version": plan.get("terraform_version"),
                          "summary": summary, "findings": [f.as_dict() for f in findings],
                          "changes": changes if args.show_changes else None,
                          "not_checked": NOT_CHECKED}, indent=2, sort_keys=True))
    else:
        print(render_text(plan, summary, findings, changes, args.show_changes))
    threshold = "warn" if args.strict and not args.fail_on else args.fail_on
    if threshold:
        limit = SEVERITY_ORDER[LEVELS[threshold]]
        if any(SEVERITY_ORDER[f.severity] <= limit for f in findings):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
