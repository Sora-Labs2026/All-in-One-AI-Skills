# BGP diagnostics: sessions, missing routes and policy

Read this when a BGP session is down or flapping, a session is up but prefixes are missing or unexpected, traffic takes the wrong exit, or you need before-and-after evidence for a BGP change. Diagnosis is read-only. Clearing sessions, editing policy, timers, authentication or filters, and enabling extra route storage are changes that need the owner's go-ahead and a window.

Commands use IOS-XE syntax; classic IOS also accepts `show ip bgp ...`. NX-OS, IOS XR, Junos and FRR have equivalents with different names, so confirm the platform first.

## 1. Pin down the scope

Before reading any output, write down:

- The local router, the neighbor address, local and remote AS numbers, and whether it is eBGP or iBGP.
- The address family and VRF (`ipv4 unicast`, `ipv6 unicast`, `vpnv4`, `l2vpn evpn`, a VRF name). Most "missing route" confusion is looking at the global IPv4 table when the session lives elsewhere.
- What changed and when: maintenance, a provider notice, a policy edit, a new prefix, a software upgrade.
- The exact prefix that is missing or wrong, and from where it should be visible.

```text
show bgp all summary
show bgp ipv4 unicast summary
show bgp vpnv4 unicast vrf CUST-A summary
show running-config | section router bgp
```

## 2. Read the session state

| State in the summary | What it means | Check first |
|---|---|---|
| A number (prefixes received) | Established | Policy, best-path choice and installation in the routing table |
| `0` | Established, nothing accepted | Inbound policy, what the peer advertises, address family activation, RFC 8212 default deny |
| `Idle` | Not trying, or waiting before retrying | Neighbor configured and activated, address family, no route to the peer, back-off after errors |
| `Idle (Admin)` | `neighbor ... shutdown` | Intended? Find the change record |
| `Idle (PfxCt)` | Maximum-prefix limit exceeded | `maximum-prefix` setting and what the peer started sending |
| `Active` | TCP connection keeps failing (despite the name) | Route to the peer address, update source, ACLs and firewalls on TCP 179, TTL for eBGP, peer configuration |
| `Connect` | TCP connection in progress | Path to the peer and whether it listens |
| `OpenSent`, `OpenConfirm` | TCP works, OPEN negotiation fails | AS numbers, router ID, hold time, capabilities, authentication |

Then the detail and the last reset reason:

```text
show bgp ipv4 unicast neighbors 192.0.2.1 | include BGP state|Last reset|Local host|Foreign host|hold time|Notification
show logging | include BGP|192.0.2.1|BADAUTH
```

Notification codes in logs (RFC 4271 and RFC 4486) narrow the cause quickly:

| Code | Meaning | Usual cause |
|---|---|---|
| 2/2 | OPEN error, bad peer AS | `remote-as` mismatch on one side |
| 2/3 | Bad BGP identifier | Duplicate or invalid router ID |
| 2/6 | Unacceptable hold time | Timer configuration incompatible |
| 4/0 | Hold timer expired | Keepalives lost: congestion, CPU, a link that drops large packets, a one-way path |
| 6/1 | Cease, maximum prefixes reached | Peer leaked a table or the limit is too low |
| 6/2, 6/4 | Administrative shutdown or reset | Someone shut or cleared the session |
| 6/3, 6/6 | Peer deconfigured, other configuration change | Change on the remote side |

`%TCP-6-BADAUTH` messages ("No MD5 digest" or "Invalid MD5 digest") mean the TCP authentication password differs or is missing on one side. Compare by having each side re-enter it in a window; never paste it into chat or a ticket.

## 3. Transport checks for sessions that will not come up

```text
show ip route 192.0.2.1
ping 192.0.2.1 source Loopback0
traceroute 192.0.2.1 source Loopback0
show tcp brief all | include 192.0.2.1
show ip access-lists | include 179|bgp
```

- **Loopback peering** needs `neighbor X update-source Loopback0` on both sides and routes to both loopbacks. eBGP to a loopback also needs `ebgp-multihop 2` (or `disable-connected-check` for one hop), because eBGP defaults to TTL 1.
- **Firewalls and ACLs** in the path must allow TCP 179 in both directions (either side may open the connection). Read counters and logs; do not remove a filter to test.
- **A session that reaches Established, then drops with hold timer expired about three minutes later, repeatedly,** often means large packets are lost on the path (MTU mismatch or a path-MTU black hole). Test with `ping 192.0.2.1 size 1500 df-bit source Loopback0`.

## 4. Established but routes are missing or wrong

Walk the route from the originator to the router that lacks it, one stage at a time:

| Stage | Command | What can stop it |
|---|---|---|
| Originated | `show bgp ipv4 unicast 198.51.100.0/24` on the originator | `network` statement needs an exact prefix and mask in the routing table; redistribution filtered |
| Advertised | `show bgp ipv4 unicast neighbors 192.0.2.1 advertised-routes` | Outbound route-map or prefix-list; iBGP-learned routes are not re-advertised to other iBGP peers; `no-export` or `no-advertise` communities |
| Received | `... neighbors 192.0.2.2 received-routes` (needs `soft-reconfiguration inbound`, which costs memory; do not add it during an incident without approval) | Peer never sent it |
| Accepted | `... neighbors 192.0.2.2 routes` | Inbound policy, maximum-prefix, AS-path loop detection, RFC 8212 default deny |
| Best path | `show bgp ipv4 unicast 198.51.100.0/24` | Another path wins: weight, local preference, AS-path length, origin, MED, eBGP over iBGP, IGP cost to the next hop |
| Installed | `show ip route 198.51.100.0`, `show bgp ipv4 unicast rib-failure` | Next hop unreachable (iBGP needs `next-hop-self` or the next hop in the IGP); a route with a better administrative distance |

- **RFC 8212:** IOS XR and recent FRR releases accept and send nothing on an eBGP session without explicit import and export policy. A session with zero prefixes on those platforms often just lacks policy.
- **Missing from the internet but fine locally:** check RPKI route-origin validation (a ROA whose origin AS or maximum length does not cover the announcement makes it invalid, and many networks drop invalids), the IRR objects your provider filters on, and prefix length (more specific than /24 for IPv4 or /48 for IPv6 is widely filtered). Public looking glasses and route collectors show what others see; querying them is read-only.

Read policy objects in full rather than guessing:

```text
show route-map RM-ISP-IN
show ip prefix-list PL-CUSTOMER
show ip community-list
show ip as-path-access-list
```

## AS-path regular expressions

`_` matches any delimiter (space, start, end, braces), so it anchors whole AS numbers.

| Expression | Matches |
|---|---|
| `_65001_` | Paths that contain AS 65001 anywhere |
| `^65001_` | Learned directly from neighbor AS 65001 |
| `_65001$` | Originated by AS 65001 |
| `^65001$` | Originated by and learned directly from 65001 |
| `^$` | Originated locally |

`show bgp ipv4 unicast regexp _65001$` lists matching paths. A bare `65001` also matches 165001 and 650010.

## Changes that belong in a window

- `clear bgp ipv4 unicast 192.0.2.1 soft in` asks the peer to resend (route refresh) and `soft out` resends your updates. They do not tear down the session but they do re-run policy, so they still need the go-ahead. A hard `clear` drops the session and every route through it.
- Policy edits: build the new route-map or prefix-list under a new name, review it, and swap the reference in one command; editing a live policy line by line applies each half-finished state.
- Planned maintenance: tag routes with the graceful shutdown community (RFC 8326, `65535:0`) or raise the AS path, wait for traffic to move, then shut the session.
- Add `maximum-prefix` with a warning threshold on every external session, sized from today's count plus headroom agreed with the owner.

## Automation and parsing

Parse `show bgp ... summary` with a maintained template (TextFSM, Genie) or NAPALM's `get_bgp_neighbors`, and keep the raw output with the result: summary formats change with the address family, long AS numbers wrap lines, and the last column holds either a count or a state. Treat a numeric last column as Established with that many prefixes, anything else as the state.

## Report

```text
Session:     <local> -> <neighbor> AS <n>, <afi/safi>, <vrf>
State:       <state, uptime, last reset reason, notification code>
Evidence:    <command> -> <what it showed>
Cause:       <one sentence that explains every observation>
Proposed:    <change, rollback, window> (not applied)
Verify with: <commands and the expected output>
```

## Pitfalls

- Reading `Active` as "the remote router is down". It means TCP keeps failing, from either side.
- Looking in the wrong address family or VRF.
- Hard-resetting a session before reading the last reset reason and the logs.
- Treating empty `received-routes` output as proof that nothing arrived when inbound soft reconfiguration is not configured.
- Fixing a missing route by loosening filters instead of finding the stage that drops it.
