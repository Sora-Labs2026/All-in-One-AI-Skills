# Configuration validation and drift

Read this when you review a router or switch configuration, check a candidate change before a window, gate an automation run, or find out whether devices still match their intended configuration. Validation produces findings and diffs; it changes nothing on any device.

## Validate in layers

Each layer catches what the one before cannot. Regular expressions and linters are pre-flight warnings, not a parser; the final call needs a person who knows the intent, the platform and the rollback.

| Layer | What it catches | How |
|---|---|---|
| 1. Hygiene lint | Telnet, SSH version, clear-text and type 7 secrets, missing AAA, logging or NTP, open VTY lines, SNMP communities, unused ports left up | `python3 <productcraft>/modules/networking/scripts/ios_config_lint.py running.cfg` (`--snippet` for a partial change) |
| 2. Risky commands in the candidate | Outages and lockouts from single lines | The table below, read line by line against the exact text to be pasted |
| 3. Reference integrity | ACLs, route-maps, prefix-lists, class-maps and VRFs that are referenced but not defined, or defined but unused | Script or parser (example below) |
| 4. Addressing | Duplicate addresses, overlapping subnets, wrong masks and wildcards | Python `ipaddress` (example below) |
| 5. Behavior | Reachability, ACL effect, BGP session compatibility, routing loops, across the whole network | Batfish (Apache-2.0) on the saved configurations, offline |
| 6. Intent | Device differs from the source of truth or golden template | Render the intended configuration, then a hierarchical diff |
| 7. Lab | Syntax the platform rejects, ordering effects, real convergence | Apply the exact candidate to a lab device of the same family and release |

## Risky lines in a candidate change

| Line | Why it is risky | Require |
|---|---|---|
| `reload`, `write erase`, `erase startup-config`, `format`, `delete` | Outage or loss of saved configuration | Explicit owner approval; never inside an automated push |
| `no router bgp`, `no router ospf`, `no ip routing` | Removes routing for everything | Rollback file and out-of-band access |
| `no interface ...`, `default interface ...` | Deletes or resets the whole interface | Confirm the interface carries nothing; capture its config first |
| `switchport trunk allowed vlan 30` | Replaces the allowed list on the trunk (use `allowed vlan add 30` to append) | Read the current list; use `add` or `remove` |
| `shutdown` on an uplink or the management interface | Cuts off downstream users or your own session | Confirm the path you are connected through |
| `aaa new-model`, method list edits, `access-class` on VTY | Lockout | Local fallback, a second open session, revert timer |
| `no ip access-list ...` on an applied ACL, or re-creating it | Permit-all, then deny-all while rebuilding | Edit by sequence number or swap to a new named ACL |
| `crypto key zeroize`, `crypto key generate` | Breaks SSH sessions and anything trusting the old key | Window plus console access; tell clients the new fingerprint |
| `vtp` changes, `no vlan ...` | VLAN loss across a domain | VTP transparent; confirm VLAN usage first |
| `ip default-gateway`, management address or VRF changes | Device becomes unreachable | Out-of-band path and revert timer |
| `spanning-tree` priority or mode changes | Topology change, flooding, possible loop | Window; verify root placement before and after |

## Reference integrity and addressing checks

A minimal integrity check for IOS-style text, to run in tests or CI on configuration files you hold:

```python
import ipaddress, re

DEFINES = {
    "acl": re.compile(r"^ip access-list (?:standard|extended) (\S+)|^access-list (\S+) ", re.M),
    "route-map": re.compile(r"^route-map (\S+)", re.M),
    "prefix-list": re.compile(r"^ip prefix-list (\S+)", re.M),
}
USES = {
    "acl": re.compile(r"(?:ip access-group|access-class|match ip address) (\S+)", re.M),
    "route-map": re.compile(r"route-map (\S+) (?:in|out)\b", re.M),
    "prefix-list": re.compile(r"(?:prefix-list|match ip address prefix-list) (\S+)", re.M),
}

def dangling(config: str) -> dict[str, set[str]]:
    out = {}
    for kind, pattern in USES.items():
        defined = {g for m in DEFINES[kind].finditer(config) for g in m.groups() if g}
        used = {m.group(1) for m in pattern.finditer(config)} - {"prefix-list"}
        out[kind] = used - defined
    return out

def interface_networks(config: str) -> list[tuple[str, ipaddress.IPv4Interface]]:
    result, current = [], None
    for line in config.splitlines():
        if line.startswith("interface "):
            current = line.split(None, 1)[1]
        elif current and (m := re.match(r"\s+ip address (\S+) (\S+)(?: secondary)?$", line)):
            result.append((current, ipaddress.IPv4Interface(f"{m.group(1)}/{m.group(2)}")))
        elif line and not line.startswith(" "):
            current = None
    return result

def overlaps(config: str) -> list[tuple[str, str]]:
    nets = interface_networks(config)
    return [(a, b) for i, (a, x) in enumerate(nets) for b, y in nets[i + 1:]
            if x.network.overlaps(y.network)]
```

Treat this as a starting point with tests of its own: real configurations have more reference forms (`match ip address` on class-maps, `distribute-list`, `neighbor ... prefix-list`, VRF-aware addresses, IPv6). Across devices, collect every interface address first, then check duplicates and overlaps for the whole estate; the conflicts that hurt are usually between devices. Batfish does these checks with a real parser and should be preferred where it is available.

## Drift: three comparisons

| Comparison | Answers | How |
|---|---|---|
| Running vs startup | Are there unsaved changes that a reload would lose? | `show archive config differences nvram:startup-config system:running-config` |
| Running vs last backup | Did anyone change the device outside a window? | Scheduled read-only backups into a private Git repository, diffed per run; `show archive log config all` for who and when |
| Running vs intended | Does the device match the source of truth? | Render the intended configuration (templates plus inventory data), then diff by hierarchy |

- **Diff by hierarchy, not by line order.** Plain text diffs report noise when sections move. Use a parser-aware comparison (Batfish, a configuration-parsing library, `show archive config incremental-diffs`, or NAPALM `compare_config()`).
- **Mask volatile lines** before diffing: `! Last configuration change at ...`, `! NVRAM config last updated ...`, `ntp clock-period`, certificate blocks that regenerate, and counters inside `show` output.
- **Backups contain secrets.** Restrict the repository, encrypt at rest, and never publish it. Redact before attaching a diff to a ticket.
- **Never auto-correct drift by default.** An unexpected difference may be an emergency fix. Report it, ask the owner which side is right, and then either update the source of truth or schedule a change.

## Before-and-after state snapshots

A change is verified by state, not by "the commands were accepted". Capture the same structured state before and after: interfaces and their counters, neighbors (CDP or LLDP, OSPF, BGP with prefix counts), the routing table size and key prefixes, ARP and MAC tables for the affected VLANs, ACL hit counts. NAPALM getters or pyATS and Genie `learn` and `diff` produce comparable snapshots; plain `show` output saved per device works too. Unexplained differences are findings.

## Review report

```text
Device:    <hostname, platform, release> (or "unknown")
Scope:     <full configuration | candidate change CHG-...>
Checks:    lint (ios_config_lint.py: N HIGH, N WARN) / risky lines / references / addressing / behavior / lab
Findings:
  [BLOCK-1] <title>  Section: <block or line>  Evidence: <redacted line>  Risk: <...>  Fix: <...>
  [FIX-1]   ...
  [NOTE-1]  ...
Verdict:   BLOCK | FIX FIRST | READY FOR WINDOW
Not verified: <what could not be checked offline>
```

Use **BLOCK** for clear-text or default credentials, Telnet or unrestricted management access exposed to untrusted networks, risky lines without a rollback, and dangling references in the candidate. Use **FIX FIRST** for hygiene gaps the change touches. **READY FOR WINDOW** means the review found nothing blocking; it does not mean the change is approved, which is the owner's decision.

## Done when

- The exact candidate text, not a paraphrase, went through every layer that applies, and each layer's result is in the report.
- Every HIGH lint finding and every risky line has a fix or an owner-accepted exception.
- Drift findings are reported with the evidence and left for the owner to resolve.
