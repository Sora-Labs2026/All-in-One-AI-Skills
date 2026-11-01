# Network automation over SSH and APIs: Netmiko, NAPALM, Nornir, Ansible

Read this when you write or review code that logs in to network devices: collecting `show` output across many devices, parsing it, auditing configuration, or pushing a change. The default code path is read-only. A path that changes configuration is separate, off by default, produces a diff first, and runs against a lab before it ever touches a live device.

## Pick the tool

| Tool (licence) | Use when | Not when |
|---|---|---|
| Netmiko 4.x (MIT) | A script needs to run commands over SSH on many vendors' CLIs, with prompt handling done for you | You need idempotent, declarative configuration state |
| NAPALM (Apache-2.0) | You want vendor-neutral getters (`get_facts`, `get_interfaces_counters`, `get_bgp_neighbors`) and a candidate, diff, commit or discard workflow | The platform has no NAPALM driver, or the driver lacks the feature you need |
| Nornir 3.x (Apache-2.0) | Python inventory, filtering and concurrency around Netmiko or NAPALM tasks, with per-host results | A two-device one-off; plain Netmiko is simpler |
| Ansible with the `cisco.ios` collection (GPL-3.0) | The team already runs Ansible; resource modules with `--check --diff`; changes reviewed as playbooks | Complex parsing or branching logic, which is awkward in YAML |
| NETCONF or RESTCONF with YANG (IOS-XE 16.x and later) | Structured data without screen scraping; candidate datastore and confirmed commit where the platform enables them | Mixed older estates without model support |

Pin versions in a lock or requirements file and read the changelog before upgrading: Netmiko 4 (2022) replaced delay-factor tuning with `read_timeout`, and NAPALM drivers move between packages over time.

## Credentials, host keys and accounts

- **Secrets by name.** Code reads `NET_USERNAME`, `NET_PASSWORD` and `NET_ENABLE_SECRET` from the environment, a secret store or an interactive `getpass()` prompt. The agent never asks for the values in chat, never writes them to files, command lines, logs or exception messages, and checks presence only (`echo "${NET_PASSWORD:+set}"`). For first-time setup, give the user a guided script (`../../agent-safety/references/guided-setup.md`).
- **Prefer per-person or per-tool accounts** from TACACS+ or RADIUS. A collection account should be authorized for `show` commands only (command authorization on the AAA server); a change account is separate and used only in windows.
- **Verify host keys.** Netmiko's default accepts unknown host keys. For anything beyond a lab, pre-populate `known_hosts` and pass `ssh_strict=True, system_host_keys=True`, or `alt_host_keys=True, alt_key_file=...`. A changed host key is a stop-and-ask event, not something to auto-accept.
- **Old devices with legacy SSH algorithms:** do not weaken the client globally. Allow the old algorithm for that one host in an SSH config file (`ssh_config_file=`), record it as a risk, and plan the upgrade.
- **Jump hosts:** use `ProxyJump` in the SSH config file rather than custom tunnels.

## Read-only collection with Netmiko

```python
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException, ReadTimeout

def device(host: str) -> dict:
    return {
        "device_type": "cisco_xe",            # cisco_ios for classic IOS
        "host": host,
        "username": os.environ["NET_USERNAME"],
        "password": os.environ["NET_PASSWORD"],
        "conn_timeout": 10, "auth_timeout": 20, "banner_timeout": 15,
        "ssh_strict": True, "system_host_keys": True,
    }

def collect(host: str, commands: list[str]) -> dict:
    try:
        with ConnectHandler(**device(host)) as conn:
            return {"host": host, "ok": True,
                    "output": {c: conn.send_command(c, read_timeout=60) for c in commands}}
    except (NetmikoAuthenticationException, NetmikoTimeoutException, ReadTimeout) as exc:
        return {"host": host, "ok": False, "error": type(exc).__name__}   # never str(exc) with secrets

hosts = [h.strip() for h in open("inventory.txt") if h.strip()]          # reviewed list, not a CIDR sweep
with ThreadPoolExecutor(max_workers=8) as pool:
    results = [f.result() for f in as_completed(pool.submit(collect, h, ["show version", "show ip interface brief"]) for h in hosts)]
```

- **Inventory is explicit.** A reviewed file or a source of truth, never a range scan; scanning address space you were not asked about is out of scope.
- **Concurrency is modest.** One session per device, a handful of workers to start (devices have a small number of VTY lines, and AAA servers throttle). Raise it only with evidence that devices and AAA cope.
- **Timeouts on every call.** `conn_timeout`, `auth_timeout`, `banner_timeout` on connect; `read_timeout` per command, longer for `show tech-support` or large tables. Use `expect_string` when the prompt changes.
- **Per-device failure isolation.** One unreachable device is a row in the report, not a crashed run. Report counts of succeeded, failed and skipped devices.
- **Outputs are sensitive.** Configuration output contains hashes, type 7 strings, keys and communities. Write it to a private directory (`umask 077`), never to shared logs or tickets without redaction. Netmiko masks the password it was given in its session log, but not what the device prints.

## Parsing

- TextFSM templates (the `ntc-templates` collection, Apache-2.0) via `send_command(..., use_textfsm=True)`, Genie parsers (`use_genie=True`, from the free pyATS ecosystem; check its licence terms), or TTP templates. When no template matches, Netmiko returns the raw string, so check the type before using the result.
- Keep the raw output next to the parsed result whenever a decision depends on it. Parsers lag new releases and break silently on format changes.
- Write your own parser only for output you can test: fixtures from real devices (redacted), one test per format variant, and block boundaries taken from headers rather than character offsets.

## Changing configuration: candidate, diff, approval, apply

The change path is a separate entry point or an explicit flag, refuses to run without a named change ticket and target list, and prints the diff before anything is sent.

**NAPALM** gives the cleanest diff-first flow:

```python
import os
from napalm import get_network_driver

host, change_id = "lab-sw1", "CHG-1042"
driver = get_network_driver("ios")
with driver(host, os.environ["NET_USERNAME"], os.environ["NET_PASSWORD"],
            optional_args={"secret": os.environ.get("NET_ENABLE_SECRET", "")}) as dev:
    dev.load_merge_candidate(filename=f"changes/{host}.cfg")
    diff = dev.compare_config()
    print(diff or "no change")
    if diff and os.environ.get("APPLY_CHANGE_ID") == change_id:   # set by the operator for this window
        dev.commit_config()
    else:
        dev.discard_config()
```

The IOS driver stages candidates over SCP and uses `configure replace` for full replacement; read the driver notes for its device prerequisites and test them in the lab.

**Ansible** with check mode:

```bash
ansible-playbook change.yml --limit lab-sw1 --check --diff     # dry run against the lab
ansible-playbook change.yml --limit lab-sw1 --diff             # apply in the lab
ansible-playbook change.yml --limit core-sw1 --check --diff    # dry run on the live target; show the diff to the owner
```

Use resource modules (`cisco.ios.ios_interfaces`, `ios_vlans`, `ios_acls`) with `state: merged` or `replaced`; `state: rendered` produces configuration offline and `state: gathered` reads current state. Reserve `state: overridden` for a reviewed change, because it removes everything not listed. Set `backup: true` on `ios_config` tasks. Connection variables: `ansible_connection: ansible.netcommon.network_cli`, `ansible_network_os: cisco.ios.ios`; secrets come from Ansible Vault or the environment, never from the inventory in plain text.

**Netmiko** for small pushes: capture `show running-config | section <block>` before, `send_config_set(lines)`, capture after, compare, and call `save_config()` only after verification and as its own approved step.

**Nornir** wraps any of these with inventory and concurrency:

```python
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command

nr = InitNornir(config_file="nornir.yaml")              # runner num_workers set here
nr.inventory.defaults.username = os.environ["NET_USERNAME"]
nr.inventory.defaults.password = os.environ["NET_PASSWORD"]
result = nr.filter(role="access").run(task=netmiko_send_command,
                                      command_string="show interfaces status", use_textfsm=True)
print(sorted(result.failed_hosts))
```

Roll out changes in waves: lab, one canary device, a small group, then the rest, with a verification gate and a stop rule between waves (stop on the first unexpected diff or failed check).

## Labs

Test automation and candidate configurations against virtual devices before live ones: Cisco Modeling Labs, containerlab with vendor images, or GNS3 and EVE-NG. Use only images you are licensed to run, obtained from the vendor; do not download images from unofficial sources. Match the family and release of the production devices as closely as you can, and note where the lab differs.

## Done when

- Inventory, credentials by name, host-key verification and timeouts are in place; a dry run lists every target and command.
- Read-only runs produce per-device results with failures isolated and no secret in output or logs.
- Any change path printed a diff, ran in the lab, and is gated by an explicit approval for a named change; saving is a separate step after verification.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `ReadTimeout` on long commands | Output larger than the default wait | Raise `read_timeout` for that command; use `expect_string` |
| Parsed result is a string | No template matched | Treat as unparsed; store raw; add or fix the template with a test |
| AAA lockouts during a run | Too many parallel logins, or a wrong password retried per device | Lower concurrency; stop the run on the first authentication failure |
| Silent man-in-the-middle exposure | Unknown host keys auto-accepted | Strict host-key checking with a maintained `known_hosts` |
| Config pushed to the wrong devices | Inventory filter typo | Print and confirm the resolved target list before any change |
| Secrets in Git | Inventory or vars files with passwords | Vault or environment variables; scan history (`../../launchguard/references/safe-operations.md` for leaks) |
