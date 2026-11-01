# Network troubleshooting: layer by layer, with evidence

Read this when something cannot reach something else, is slow, drops intermittently, or resolves the wrong address, on a campus, a data center edge, a small office or a home network. Diagnosis is read-only. Every fix is a proposal until the owner approves it; nothing is disabled to "see if it helps". The general debugging discipline (reproduce, isolate, hypothesize, verify) is in `../../engineering-workflow/references/debugging.md`; this file adds the network-specific steps.

## 1. Define the failure precisely

Write one line per item before running anything:

- **What fails:** source host and address, destination name and address, protocol and port, and the exact error ("TLS handshake timeout", "no route to host", "NXDOMAIN"), not "the network is down".
- **Who and where:** one host, one VLAN, one site, one application, or everyone. A working counterpart (a host that succeeds) is the most valuable thing you can find.
- **Since when, and what changed:** changes, maintenance, provider notices, new devices, certificate expiry, an upgrade. On IOS, `show archive log config all` shows recent configuration changes if config logging is on.
- **Steady or intermittent:** for intermittent problems, measure a rate (for example, 12 failures in 500 attempts) so a fix can be judged.

## 2. Choose a path through the layers

| Approach | Use when |
|---|---|
| Bottom-up (physical first) | Link lights, new cabling, a whole port or closet affected |
| Top-down (application first) | One application fails while others work |
| Follow the packet | A known path through several devices; check each hop's forwarding decision |
| Divide and conquer | Start in the middle (can the host reach its gateway?), then go up or down |
| Compare working and failing | A counterpart exists; diff addresses, VLANs, routes, DNS, firewall zone |

## 3. Layer checks

**Layer 1: link.** Link state, speed and duplex, error and drop rates on both ends (`interface-health.md`).

**Layer 2: switching.**

```text
show interfaces status | include <port>
show vlan brief
show interfaces trunk
show mac address-table address <host-mac>
show spanning-tree vlan <id>
show logging | include MACFLAP|NATIVE_VLAN_MISMATCH|err-disable|DUPADDR
```

Wrong access VLAN, a VLAN missing from a trunk's allowed list, native VLAN mismatch, a port blocked by spanning tree, MAC flapping (a loop or a duplicated MAC), or a duplicate IP address (`%IP-4-DUPADDR`, or `arping -D -I eth0 <ip>` on Linux).

**Layer 3: addressing and routing.**

```text
show ip interface brief
show ip arp <host-ip>
show ip route <destination>
show ip cef exact-route <source> <destination>     ! which path a flow takes with load sharing
ping <destination> source <interface>
traceroute <destination> source <interface>
```

Wrong mask or gateway on the host, a missing or more specific route, a wrong next hop, a default route to the wrong upstream, NAT that does not match, and asymmetric return paths through a stateful firewall (the return traffic arrives on a firewall that never saw the connection open).

**Layer 4 and policy.** Is anything listening, and does policy allow the flow?

```text
show ip access-lists <name>                        ! hit counters before and after a test
show running-config interface <if> | include access-group|service-policy
show logging | include DENY|denied|<host-ip>
```

When a deny counter rises for the failing flow, propose a narrow allow rule (source, destination, protocol, port, direction), with its rollback. Never remove or disable an ACL, firewall rule, authentication or management restriction to test a theory.

**DNS.** IP works but names fail, or names resolve differently in different places.

```bash
dig example.com                    # the host's own resolver
dig @192.0.2.53 example.com        # the local resolver directly
dig @<public resolver> example.com # compare with an outside view
dig +trace example.com             # walk the delegation
```

If the public answer is right and the local one is wrong or empty, look at the local resolver, its upstreams, local zones, filtering lists, the DHCP-provided DNS option, and firewall rules for UDP and TCP 53 (`pihole-dns.md` for a local filtering resolver).

**Application and TLS.** `curl -v https://host/`, `openssl s_client -connect host:443 -servername host`, the application's logs. A path that passes small packets but stalls on large transfers usually has an MTU problem: `ping -M do -s 1472 <host>` on Linux, `ping -D -s 1472` on macOS, `ping -f -l 1472` on Windows, then lower the size until it passes.

## 4. Host-side commands

| Question | Linux | macOS | Windows |
|---|---|---|---|
| Addresses and gateway | `ip -br addr`, `ip route` | `ifconfig`, `route -n get default` | `ipconfig /all`, `route print` |
| Path for one destination | `ip route get <ip>` | `route -n get <ip>` | `Find-NetRoute -RemoteIPAddress <ip>` |
| Neighbors | `ip neigh` | `arp -an` | `arp -a` |
| DNS configuration | `resolvectl status` | `scutil --dns` | `Get-DnsClientServerAddress` |
| TCP port test | `nc -vz <host> 443` | `nc -vz <host> 443` | `Test-NetConnection <host> -Port 443` |
| Path quality | `mtr -rwbzc 100 <host>`, `tracepath <host>` | `traceroute <host>` | `pathping <host>`, `tracert -d <host>` |

Reading path tools: loss shown at one middle hop but not at later hops is that router rate-limiting replies to probes, not loss on the path. ICMP is often filtered, so a failed ping proves little on its own; test the real protocol and port.

## 5. Packet captures

A capture settles arguments, but it holds payloads, credentials of clear-text protocols and personal data. Capture only with the owner's approval, on the narrowest filter, for the shortest time, and store the file privately; delete it when the case closes.

```bash
sudo tcpdump -ni eth0 -c 500 -w /tmp/case.pcap 'host 198.51.100.10 and tcp port 443'
```

On IOS-XE, Embedded Packet Capture (`monitor capture ...`) and on switches SPAN sessions consume device resources and change configuration; treat them as changes with a defined stop.

## 6. Prove the cause, then propose the fix

- A hypothesis must explain every observation, including what still works. Write it as "Cause: X. Evidence: Y. Prediction: if X, then test Z shows W."
- Change one thing at a time, and only in an approved window; re-run the exact failing test after each change.
- Record the evidence as you go: the command, when it ran, on which device, and what it proved or ruled out.

## Report

```text
Diagnosis: <one-line root cause>
Symptom:   <precise failing test>         Scope: <host, VLAN, site>
Layer:     <where the fault was found>
Evidence:
  - <command on device, time> -> <what it showed>
  - <command> -> <what it ruled out>
Root cause: <explanation that covers all symptoms>
Proposed fix (not applied): <change, rollback, window, owner>
Verify with: <the failing test and expected result; counters or logs that should change>
Still unknown: <what needs more access, logs or time>
```

## Pitfalls

- Starting at the layer you suspect and never checking the one below it.
- Trusting the host's view only: check the gateway's ARP, MAC and route tables too.
- Calling a cause after one supporting observation; look for the observation that would disprove it.
- "Temporary" allow-all rules or disabled filters that stay forever.
- Fixing several things at once, which hides the real cause and invites the next outage.
