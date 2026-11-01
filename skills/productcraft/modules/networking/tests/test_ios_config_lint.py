"""Offline tests for ios_config_lint.py using synthetic configurations only; no device, SSH or network."""
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ios_config_lint.py"
spec = importlib.util.spec_from_file_location("ios_config_lint", SCRIPT)
lint_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lint_mod
spec.loader.exec_module(lint_mod)


def fake(tag, hexadecimal=False):
    """A deterministic stand-in secret built at runtime, so no secret-shaped literal sits in the file."""
    digest = hashlib.sha256(("fixture-" + tag).encode()).hexdigest()
    return digest[:16].upper() if hexadecimal else "Fx" + digest[:14]


def base_config(extra_top="", vty_extra=None, interfaces=""):
    """A configuration with every baseline control present; tests add one weakness at a time."""
    vty = vty_extra if vty_extra is not None else [" access-class MGMT in", " exec-timeout 10 0", " transport input ssh"]
    lines = [
        "version 17.9",
        "service timestamps log datetime msec localtime show-timezone",
        "hostname edge-sw1",
        "aaa new-model",
        "aaa authentication login default group tacacs+ local",
        "enable secret 9 " + "$9$" + fake("enable"),
        "username netops privilege 15 secret 9 " + "$9$" + fake("netops"),
        "ip ssh version 2",
        "no ip http server",
        "ip http secure-server",
        "logging host 192.0.2.50",
        "ntp server 192.0.2.123",
    ]
    if extra_top:
        lines.extend(extra_top.strip("\n").splitlines())
    lines.append("!")
    if interfaces:
        lines.extend(interfaces.strip("\n").splitlines())
    lines.extend(["!", "line con 0", " exec-timeout 5 0", "line vty 0 4", " login authentication default"])
    lines.extend(vty)
    lines.append("end")
    return "\n".join(lines) + "\n"


def codes(text, **kw):
    return sorted({f.code for f in lint_mod.lint(text, **kw)})


def run_cli(text, *args, status=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "device.cfg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        extra = []
        if status is not None:
            spath = os.path.join(tmp, "status.txt")
            with open(spath, "w", encoding="utf-8") as handle:
                handle.write(status)
            extra = ["--status", spath]
        return run_raw(*args, *extra, path)


def run_raw(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = lint_mod.main(list(args))
    return code, out.getvalue(), err.getvalue()


class BaselineTests(unittest.TestCase):
    def test_hardened_config_has_no_findings(self):
        self.assertEqual(codes(base_config()), [])

    def test_hardened_config_exits_zero(self):
        code, out, _ = run_cli(base_config())
        self.assertEqual(code, 0)
        self.assertIn("No findings", out)


class ManagementPlaneTests(unittest.TestCase):
    def test_telnet_in_transport_input(self):
        cfg = base_config(vty_extra=[" access-class MGMT in", " transport input telnet ssh"])
        self.assertIn("TELNET_ENABLED", codes(cfg))

    def test_transport_input_all_counts_as_telnet(self):
        cfg = base_config(vty_extra=[" access-class MGMT in", " transport input all"])
        self.assertIn("TELNET_ENABLED", codes(cfg))

    def test_missing_transport_input_warns(self):
        cfg = base_config(vty_extra=[" access-class MGMT in"])
        self.assertIn("VTY_TRANSPORT_DEFAULT", codes(cfg))
        self.assertNotIn("TELNET_ENABLED", codes(cfg))

    def test_ssh_version_1(self):
        cfg = base_config().replace("ip ssh version 2", "ip ssh version 1")
        found = codes(cfg)
        self.assertIn("SSH_V1", found)
        self.assertIn("SSH_V2_NOT_SET", found)

    def test_ssh_version_2_missing(self):
        cfg = base_config().replace("ip ssh version 2\n", "")
        self.assertEqual(codes(cfg), ["SSH_V2_NOT_SET"])

    def test_vty_without_access_class(self):
        cfg = base_config(vty_extra=[" transport input ssh"])
        self.assertEqual(codes(cfg), ["VTY_NO_ACL"])

    def test_ipv6_access_class_is_accepted(self):
        cfg = base_config(vty_extra=[" ipv6 access-class MGMT6 in", " transport input ssh"])
        self.assertEqual(codes(cfg), [])

    def test_exec_timeout_zero(self):
        cfg = base_config(vty_extra=[" access-class MGMT in", " exec-timeout 0 0", " transport input ssh"])
        self.assertEqual(codes(cfg), ["VTY_NO_TIMEOUT"])

    def test_no_login_on_vty(self):
        cfg = base_config(vty_extra=[" access-class MGMT in", " no login", " transport input ssh"])
        self.assertIn("VTY_NO_LOGIN", codes(cfg))

    def test_plain_http_server(self):
        cfg = base_config().replace("no ip http server", "ip http server")
        self.assertEqual(codes(cfg), ["HTTP_SERVER"])

    def test_missing_aaa(self):
        cfg = base_config().replace("aaa new-model\n", "")
        self.assertIn("NO_AAA", codes(cfg))

    def test_server_only_login_list(self):
        cfg = base_config().replace("group tacacs+ local", "group tacacs+")
        self.assertEqual(codes(cfg), ["AAA_NO_LOCAL_FALLBACK"])

    def test_missing_logging_ntp_and_timestamps(self):
        cfg = (base_config().replace("logging host 192.0.2.50\n", "logging buffered 64000\n")
               .replace("ntp server 192.0.2.123\n", "")
               .replace("service timestamps log datetime msec localtime show-timezone\n", ""))
        self.assertEqual(codes(cfg), ["NO_NTP", "NO_REMOTE_LOGGING", "NO_TIMESTAMPS"])

    def test_legacy_logging_address_form(self):
        cfg = base_config().replace("logging host 192.0.2.50", "logging 192.0.2.50")
        self.assertEqual(codes(cfg), [])


class CredentialTests(unittest.TestCase):
    def test_enable_password(self):
        cfg = base_config("enable password " + fake("en-plain"))
        self.assertIn("PLAINTEXT_SECRET", codes(cfg))

    def test_enable_password_type7(self):
        cfg = base_config("enable password 7 " + fake("en7", True))
        self.assertIn("TYPE7_SECRET", codes(cfg))

    def test_enable_secret_types(self):
        self.assertEqual(codes(base_config("enable secret 5 $1$" + fake("md5"))), ["MD5_HASH"])
        self.assertEqual(codes(base_config("enable secret 4 " + fake("t4"))), ["BROKEN_HASH"])
        self.assertEqual(codes(base_config("enable secret level 15 5 $1$" + fake("lvl"))), ["MD5_HASH"])
        self.assertEqual(codes(base_config("enable secret 8 $8$" + fake("t8"))), [])

    def test_username_password_forms(self):
        self.assertEqual(codes(base_config("username ops password 7 " + fake("u7", True))), ["TYPE7_SECRET"])
        self.assertEqual(codes(base_config("username ops password 0 " + fake("u0"))), ["PLAINTEXT_SECRET"])
        self.assertEqual(codes(base_config("username ops privilege 15 password " + fake("u"))), ["PLAINTEXT_SECRET"])
        self.assertEqual(codes(base_config("username ops algorithm-type scrypt secret " + fake("in"))), ["PLAINTEXT_SECRET"])

    def test_account_without_password(self):
        self.assertEqual(codes(base_config("username guest nopassword")), ["NO_PASSWORD_ACCOUNT"])

    def test_line_password(self):
        cfg = base_config(vty_extra=[" access-class MGMT in", " password 7 " + fake("vty", True), " transport input ssh"])
        self.assertEqual(codes(cfg), ["TYPE7_SECRET"])
        cfg = base_config(vty_extra=[" access-class MGMT in", " password " + fake("vtyp"), " transport input ssh"])
        self.assertEqual(codes(cfg), ["PLAINTEXT_SECRET"])

    def test_server_and_routing_keys(self):
        top = "\n".join([
            "tacacs server ISE1",
            " address ipv4 192.0.2.10",
            " key 7 " + fake("tac", True),
            "key chain OSPF-KEYS",
            " key 1",
            "  key-string " + fake("kc"),
            "router bgp 65010",
            " neighbor 198.51.100.1 password " + fake("bgp"),
            "ntp authentication-key 1 md5 " + fake("ntp", True) + " 7",
        ])
        found = lint_mod.lint(base_config(top))
        by_code = sorted((f.code, f.context.split()[0]) for f in found)
        self.assertEqual(by_code, [
            ("PLAINTEXT_SECRET", "key-string"),
            ("PLAINTEXT_SECRET", "neighbor"),
            ("TYPE7_SECRET", "key"),
            ("TYPE7_SECRET", "ntp"),
        ])

    def test_type6_and_hashed_values_are_accepted(self):
        top = "\n".join([
            "password encryption aes",
            "crypto isakmp key 6 " + fake("ike") + " address 203.0.113.9",
            "service password-encryption",
            "security passwords min-length 12",
            "crypto key generate rsa modulus 2048",
        ])
        self.assertEqual(codes(base_config(top)), [])

    def test_snmpv3_user_in_file(self):
        cfg = base_config("snmp-server user mon MONGRP v3 auth sha " + fake("a") + " priv aes 128 " + fake("p"))
        self.assertEqual(codes(cfg), ["PLAINTEXT_SECRET"])


class SnmpTests(unittest.TestCase):
    def test_default_community_and_rw(self):
        found = codes(base_config("snmp-server community public RW"))
        self.assertEqual(found, ["SNMP_DEFAULT_COMMUNITY", "SNMP_RW_COMMUNITY", "SNMP_V2C"])

    def test_private_community_on_trap_host(self):
        self.assertIn("SNMP_DEFAULT_COMMUNITY", codes(base_config("snmp-server host 192.0.2.60 version 2c private")))

    def test_v3_trap_host_not_flagged(self):
        self.assertEqual(codes(base_config("snmp-server host 192.0.2.60 version 3 priv public")), [])

    def test_custom_community_with_acl(self):
        found = lint_mod.lint(base_config("snmp-server community " + fake("snmp") + " RO SNMP-ACL"))
        self.assertEqual([f.code for f in found], ["SNMP_V2C"])
        self.assertNotIn("No ACL", found[0].message)

    def test_custom_community_without_acl(self):
        found = lint_mod.lint(base_config("snmp-server community " + fake("snmp2") + " RO"))
        self.assertIn("No ACL", found[0].message)


class InterfaceTests(unittest.TestCase):
    PORTS = "\n".join([
        "interface GigabitEthernet1/0/1",
        " description UPLINK-CORE",
        " switchport mode trunk",
        "interface GigabitEthernet1/0/2",
        " switchport access vlan 20",
        "interface GigabitEthernet1/0/3",
        "interface GigabitEthernet1/0/4",
        " shutdown",
        "interface Vlan10",
        "interface Loopback0",
        "interface GigabitEthernet0/0.10",
    ])

    def test_unconfigured_port_heuristic(self):
        found = [f for f in lint_mod.lint(base_config(interfaces=self.PORTS)) if f.code.startswith("PORT_")]
        self.assertEqual([(f.code, f.context) for f in found], [("PORT_UNCONFIGURED", "interface GigabitEthernet1/0/3")])

    def test_status_file_confirms_not_connected(self):
        status = "\n".join([
            "Port         Name               Status       Vlan       Duplex  Speed Type",
            "Gi1/0/1      UPLINK-CORE        connected    trunk      a-full a-1000 10/100/1000BaseTX",
            "Gi1/0/2                         notconnect   20           auto   auto 10/100/1000BaseTX",
            "Gi1/0/3                         connected    1          a-full a-1000 10/100/1000BaseTX",
            "Gi1/0/4                         disabled     1            auto   auto 10/100/1000BaseTX",
        ])
        code, out, _ = run_cli(base_config(interfaces=self.PORTS), "--json", "--fail-on", "warn", status=status)
        self.assertEqual(code, 1)
        ports = [f for f in json.loads(out)["files"][0]["findings"] if f["code"].startswith("PORT_")]
        self.assertEqual([(f["code"], f["context"]) for f in ports], [("PORT_NOT_CONNECTED", "interface GigabitEthernet1/0/2")])

    def test_brief_status_format(self):
        status = "\n".join([
            "Interface              IP-Address      OK? Method Status                Protocol",
            "GigabitEthernet1/0/3   unassigned      YES unset  down                  down",
            "GigabitEthernet1/0/4   unassigned      YES unset  administratively down down",
        ])
        parsed = lint_mod.parse_status(status)
        self.assertEqual(parsed["gigabitethernet1/0/3"], "down")
        self.assertEqual(parsed["gigabitethernet1/0/4"], "administratively down")

    def test_canonical_names(self):
        self.assertEqual(lint_mod.canonical("Gi1/0/1"), "gigabitethernet1/0/1")
        self.assertEqual(lint_mod.canonical("Te1/1/1"), "tengigabitethernet1/1/1")
        self.assertEqual(lint_mod.canonical("Twe1/0/1"), "twentyfivegige1/0/1")
        self.assertEqual(lint_mod.canonical("Gig1/0/1"), "gigabitethernet1/0/1")


class ParsingAndSafetyTests(unittest.TestCase):
    def test_banner_text_is_ignored(self):
        cfg = base_config("banner motd ^C\nAuthorized use only. password 0 is not a command here\ntransport input telnet\n^C")
        self.assertEqual(codes(cfg), [])

    def test_crlf_line_endings(self):
        cfg = base_config("enable password 7 " + fake("crlf", True)).replace("\n", "\r\n")
        self.assertIn("TYPE7_SECRET", codes(cfg))

    def test_snippet_mode_skips_absence_checks(self):
        snippet = "line vty 0 4\n transport input telnet\nusername tmp password 0 " + fake("snip") + "\n"
        self.assertEqual(codes(snippet, snippet=True), ["PLAINTEXT_SECRET", "TELNET_ENABLED"])
        self.assertIn("NO_AAA", codes(snippet))

    def test_no_secret_value_is_printed(self):
        values = [fake("s1"), fake("s2", True), fake("s3"), fake("s4", True), fake("s5"), fake("s6")]
        top = "\n".join([
            "enable password " + values[0],
            "username ops password 7 " + values[1],
            "snmp-server community " + values[2] + " RW",
            "tacacs-server key 7 " + values[3],
            "snmp-server host 192.0.2.60 version 2c " + values[4],
            "snmp-server user mon G v3 auth sha " + values[5] + " priv aes 128 " + values[5],
        ])
        cfg = base_config(top)
        for args in ((), ("--json",)):
            code, out, err = run_cli(cfg, *args)
            self.assertEqual(code, 1)
            for value in values:
                self.assertNotIn(value, out)
                self.assertNotIn(value, err)
            self.assertIn("<redacted>", out)

    def test_redact(self):
        secret = fake("r")
        self.assertEqual(lint_mod.redact("username ops privilege 15 secret 5 " + secret),
                         "username ops privilege 15 secret <redacted>")
        self.assertEqual(lint_mod.redact("snmp-server host 192.0.2.1 version 2c " + secret),
                         "snmp-server host 192.0.2.1 <redacted>")


class CliTests(unittest.TestCase):
    def test_exit_codes_and_fail_on(self):
        cfg = base_config(vty_extra=[" transport input ssh"])  # one WARN only
        self.assertEqual(run_cli(cfg)[0], 0)
        self.assertEqual(run_cli(cfg, "--fail-on", "warn")[0], 1)
        weak = base_config("snmp-server community public RO")
        self.assertEqual(run_cli(weak)[0], 1)
        self.assertEqual(run_cli(weak, "--fail-on", "none")[0], 0)

    def test_missing_file_is_usage_error(self):
        code, _, err = run_raw(os.path.join(tempfile.gettempdir(), "does-not-exist-ios.cfg"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_empty_file_and_no_arguments(self):
        self.assertEqual(run_cli("   \n")[0], 2)
        self.assertEqual(run_raw()[0], 2)

    def test_help_version_and_rules(self):
        self.assertEqual(run_raw("--help")[0], 0)
        self.assertEqual(run_raw("--version")[0], 0)
        code, out, _ = run_raw("--list-rules")
        self.assertEqual(code, 0)
        for rule in lint_mod.RULE_LIST:
            self.assertIn(rule.code, out)

    def test_bad_option_is_usage_error(self):
        self.assertEqual(run_raw("--fail-on", "sometimes", "x.cfg")[0], 2)

    def test_output_is_deterministic(self):
        cfg = base_config("snmp-server community public RW\nenable password " + fake("det"),
                          vty_extra=[" transport input all"])
        first = json.loads(run_cli(cfg, "--json")[1])["files"][0]
        second = json.loads(run_cli(cfg, "--json")[1])["files"][0]
        self.assertEqual((first["findings"], first["summary"]), (second["findings"], second["summary"]))
        doc = {"files": [first]}
        severities = [f["severity"] for f in doc["files"][0]["findings"]]
        order = {"HIGH": 0, "WARN": 1, "INFO": 2}
        self.assertEqual(severities, sorted(severities, key=order.get))

    def test_missing_hostname_note(self):
        _, _, err = run_cli("line vty 0 4\n transport input ssh\n")
        self.assertIn("--snippet", err)


if __name__ == "__main__":
    unittest.main()
