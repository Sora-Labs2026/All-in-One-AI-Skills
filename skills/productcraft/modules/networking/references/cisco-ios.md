# Cisco IOS and IOS-XE: reading, hardening and changing configuration

Read this when you read, write or review IOS or IOS-XE configuration, choose `show` commands for evidence, check ACLs and wildcard masks, harden the management plane, or prepare a change window. Syntax below holds for classic IOS 15.x and IOS-XE 16.x and 17.x unless a line says otherwise; NX-OS and IOS XR differ, so check the platform before reusing a command.

## Know the platform first

```text
show version                         ! image, release, uptime, reload reason, config register
show inventory                       ! chassis, modules, optics, serial numbers
show running-config | include ^hostname|^version
show platform                        ! IOS-XE: slots and state (output differs by family)
```

Write down the hostname, the platform family and the release before giving any syntax. Defaults change between releases (VTY transport, SSH versions, HTTP server, password types), and the same feature can need different commands on a Catalyst switch, an ISR router and a virtual router.

## Modes and the two configurations

| Prompt | Mode | What it is for |
|---|---|---|
| `R1>` | User EXEC | Limited `show` commands |
| `R1#` | Privileged EXEC | All `show`, `debug`, `copy`, `reload`; reached with `enable` |
| `R1(config)#` | Global configuration | `configure terminal`; every command takes effect immediately |
| `R1(config-if)#`, `(config-line)#`, `(config-router)#` | Sub-modes | Interface, line and routing process settings |

- `running-config` is what the device is doing now. `startup-config` is what it loads after a reload. Nothing is saved until someone runs `copy running-config startup-config` (or `write memory`).
- A change that is accepted is not a change that works. Verify behavior first, then save. Keeping the change unsaved until it is verified is a rollback path in its own right: a reload returns to the saved state.
- Read without paging and only the part you need: `terminal length 0`, then `show running-config | section ^interface GigabitEthernet1/0/1`, `| include`, `| begin`, or `show running-config interface Gi1/0/1`. `show running-config all` adds the defaults when you need to know what an absent line means.

## Read-only evidence

| Question | Commands |
|---|---|
| Health | `show processes cpu sorted`, `show processes cpu history`, `show memory statistics`, `show logging`, `show environment` |
| Interfaces | `show ip interface brief`, `show interfaces status`, `show interfaces <if>`, `show interfaces counters errors` |
| Layer 2 | `show vlan brief`, `show interfaces trunk`, `show spanning-tree summary`, `show mac address-table address <mac>`, `show etherchannel summary`, `show cdp neighbors detail` or `show lldp neighbors detail` |
| Layer 3 | `show ip route <prefix>`, `show ip protocols`, `show ip arp <ip>`, `show ip ospf neighbor`, `show bgp ipv4 unicast summary` |
| Policy | `show ip access-lists <name>`, `show route-map <name>`, `show ip prefix-list <name>`, `show policy-map interface <if>` |
| Management | `show users`, `show ip ssh`, `show ssh`, `show line`, `show archive`, `show archive log config all` |

`debug` commands are not read-only in effect: on a busy device they can saturate the CPU. Treat them as a change: narrow them with a condition or ACL, send output to the buffer rather than the console, set `undebug all` ready, and ask first.

Configuration and `show tech-support` output contain password hashes, type 7 strings, keys, SNMP communities and internal addressing. Collect the section you need, keep files private, and redact before anything leaves the team (`../../agent-safety/references/secrets.md`).

## Wildcard masks and ACLs

ACLs, OSPF `network` statements and some other commands take a wildcard mask, the bitwise inverse of the subnet mask: `/24` is `0.0.0.255`, `/30` is `0.0.0.3`, a single host is `0.0.0.0` (or the keyword `host`). A subnet mask typed where a wildcard belongs matches a very different set of addresses; recompute every mask in review.

```text
ip access-list extended EDGE-IN
 remark CHG-1042 allow HTTPS to the web tier only
 10 permit tcp any 198.51.100.0 0.0.0.255 eq 443
 20 permit icmp any 198.51.100.0 0.0.0.255 echo-reply
 900 deny ip any any log
interface GigabitEthernet0/0/0
 ip access-group EDGE-IN in
```

- Every ACL ends with an implicit `deny any`. The explicit logged deny makes misses visible; check that log volume is acceptable (`logging rate-limit`).
- **Direction:** `in` filters traffic arriving on that interface, `out` traffic leaving it. Draw the flow and name the interface and direction before writing the rule. Extended ACLs usually sit close to the source, standard ACLs close to the destination.
- **Edit by sequence number** (`15 permit ...`, `no 20`) inside the named ACL. Do not delete and re-create an applied ACL: on IOS an interface that references a missing ACL permits everything, and the moment the first entry is added again the implicit deny applies to all other traffic, including your own session.
- Prove the effect with hit counters: `show ip access-lists EDGE-IN` before and after a test from a known source. Counters are evidence; a generic ping is not.

## Management-plane baseline

| Control | Configuration | Why |
|---|---|---|
| SSH only | `ip ssh version 2`; RSA keys of 2048 bits or more (`crypto key generate rsa modulus 2048`); on every `line vty` range: `transport input ssh` | Telnet and SSH version 1 expose credentials |
| Restrict who can log in | `access-class MGMT in` on every VTY range, permitting the management subnet or jump hosts only | Login attempts only from known sources |
| Close idle sessions | `exec-timeout 10 0` on VTY and console | Abandoned sessions stay authenticated |
| Strong local secrets | `enable algorithm-type scrypt secret ...`, `username NAME privilege 15 algorithm-type scrypt secret ...` | Type 9 (scrypt) or 8 (PBKDF2-SHA-256). Type 5 is salted MD5, type 4 is broken, type 7 is reversible by anyone, type 0 is clear text |
| Reversible keys only where needed | `key config-key password-encrypt` (entered interactively) plus `password encryption aes` stores keys as type 6 | Protocol keys (TACACS+, RADIUS, routing authentication) cannot be hashed |
| Central AAA | `aaa new-model`, TACACS+ or RADIUS for login, exec and command authorization, accounting of commands; `local` as the last login method | Per-person accounts, least privilege, an audit trail, a way in when the servers are down |
| Brute-force throttling | `login block-for 120 attempts 5 within 60`, `security passwords min-length 12` | Slows password guessing |
| Logging | `service timestamps log datetime msec localtime show-timezone`, `logging buffered 64000`, `logging host <syslog>`, `logging source-interface <mgmt>` | Evidence survives a reload and lines up across devices |
| Time | `ntp server <a>` and `ntp server <b>`, with NTP authentication where the servers support it | Logs, certificates and change records need correct time |
| SNMP | SNMPv3 `authPriv` groups and users with an ACL; no `snmp-server community`, never `public`, `private` or `RW` | Communities travel in clear text; write access is device control |
| Web server | `no ip http server`; `ip http secure-server` only if a feature needs it, with an access class | Plain HTTP management |
| Unused ports | `shutdown`, `switchport access vlan <parking VLAN>`, `description UNUSED` | Nothing gets plugged in and works by accident |

`service password-encryption` only turns clear text into type 7. It hides passwords from someone glancing at a screen and nothing more.

**Lockout risk:** `aaa new-model` changes authentication on all lines the moment it is entered. Before typing it, confirm a local account with a strong secret exists, that the method lists end in `local`, and that a console or out-of-band path is open. The same goes for adding an `access-class` to VTY lines: permit your own source first.

## Layer 2 hygiene (switches)

- Access ports: `switchport mode access`, `switchport nonegotiate`, `spanning-tree portfast`, `spanning-tree bpduguard enable`. Port security or 802.1X where the environment uses them.
- Trunks: `switchport mode trunk`, an explicit `switchport trunk allowed vlan` list, and a native VLAN that carries no user traffic (`switchport trunk native vlan 999`), matched on both ends.
- VTP: `vtp mode transparent` (or `off` where supported) unless the team deliberately runs VTP version 3. A switch with a higher revision number joining the domain can overwrite the VLAN database.
- DHCP snooping and dynamic ARP inspection on user VLANs stop rogue DHCP servers and ARP spoofing; roll them out in a lab first, since trust settings on uplinks must be right.

## Change windows: preview, rollback armed, verify, save

Arm a rollback before touching a live device. The archive feature gives you diffs and timed rollback:

```text
archive
 path flash:archive-$h-
 maximum 14
 write-memory
 log config
  logging enable
  hidekeys
```

| Need | Command |
|---|---|
| Diff startup and running | `show archive config differences nvram:startup-config system:running-config` |
| Lines in a file that the running configuration lacks | `show archive config incremental-diffs flash:candidate.cfg` |
| Timed auto-rollback for manual changes | `configure terminal revert timer 10`, make the change, verify, then `configure confirm` |
| Replace the whole configuration, with preview and timer | `configure replace flash:candidate.cfg list time 10`, verify, then `configure confirm` |
| Return to a known file | `configure replace flash:archive-R1-3` |
| Who changed what | `show archive log config all` (needs `log config` above) |
| Last resort on old images | `reload in 15` before the change, `reload cancel` after verification; unsaved changes are lost on reload and the reload itself is an outage |

Copy candidate files with SCP over the management network; `ip scp server enable` is itself a change. `configure replace` needs a complete configuration file, not a snippet, and some lines (for example certain line and crypto settings) behave differently on replace; test the exact file on a lab device of the same family and release first.

The change itself, in order:

1. Capture the baseline: the affected sections of the running configuration, plus the state the change should alter (routes, neighbors, counters, ACL hits).
2. Lint and review the exact candidate text (`../scripts/ios_config_lint.py --snippet candidate.txt`, then `config-validation-and-drift.md`).
3. Confirm a console or out-of-band path and the rollback command.
4. With the owner's go-ahead and inside the window: arm the revert timer, apply the smallest change, and re-run the baseline commands.
5. Confirm the change, then save. Record before and after output in the change ticket.

## Pitfalls

| Symptom | Likely cause | Fix |
|---|---|---|
| Change works, then vanishes after a power cut | Never saved | Save after verification; check `show archive config differences` before closing the window |
| Session drops right after an ACL edit | Re-created ACL without a permit for your source, or `access-class` added before the permit | Edit by sequence number; arm `revert timer`; permit management first |
| ACL matches far more than intended | Subnet mask used as wildcard | Recompute masks; test with `show ip access-lists` counters |
| Everyone locked out after enabling AAA | No local fallback, servers unreachable | `local` last in every method list; test from a second session before closing the first |
| VLANs disappeared across the campus | VTP revision overwrite | VTP transparent or off; reset the revision before connecting a used switch |
| `show` output differs from documentation | Different family or release | Check `show version`; read the documentation for that release |
