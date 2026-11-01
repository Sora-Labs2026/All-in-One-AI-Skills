# Firewall basics for home and small-office networks

Read this when you write or review firewall rules for a home, homelab or small office: between VLANs, from the internet, for port forwards, for DNS control, or on a Linux host acting as a router. Rules are written as a plan and a diff first; applying them on the live gateway follows the owner's go-ahead with a way back that does not depend on the new rules working.

## How a stateful firewall thinks

- It tracks connections. Write rules for **who may start** a connection; replies to an allowed connection pass automatically. "Trusted may reach IoT, IoT may not reach trusted" is two lines of intent, not four rules.
- Every gateway already blocks unsolicited inbound traffic from the internet. Keep it that way: no "allow any" from WAN, no DMZ host pointing at a PC.
- Most firewalls evaluate rules in order and stop at the first match (pfSense and OPNsense per interface, on traffic entering it; iptables and nftables per chain). Specific allows go above broad blocks. Read the platform's documentation for its order before writing rules.

## Intent first: a zone matrix

Write the policy as a matrix of initiator (row) to destination (column) before touching any interface:

| From \ To | Trusted | Servers | IoT | Guest | Management | Gateway services | Internet |
|---|---|---|---|---|---|---|---|
| Trusted | yes | yes | yes | no | admin devices only | yes | yes |
| Servers | no | yes | named flows | no | no | DNS, NTP | updates only, if possible |
| IoT | no | named flows (for example the home automation hub) | no | no | no | DNS, DHCP, NTP | yes |
| Guest | no | no | no | no | no | DNS, DHCP | yes |
| Management | no | no | no | no | yes | yes | firmware updates |
| VPN clients | like Trusted or narrower | as needed | no | no | admin peers only | DNS | per tunnel mode |

Translate each cell into rules on the interface where that traffic enters, then add a final block for everything else between internal networks.

## Rules people forget

- **The gateway is a destination too.** Each network's gateway address is the firewall itself, and so is its WAN address. A rule that blocks "all private networks" also blocks DNS, DHCP and NTP to the gateway, and may still leave the admin page reachable on the WAN address. Allow DNS, DHCP and NTP to the gateway explicitly, then block every other port on the firewall's own addresses (on pfSense and OPNsense, the "This Firewall" alias) from IoT, guest and server networks.
- **Anti-lockout.** Open-source firewall distributions ship a rule that keeps the web interface reachable from LAN. Leave it until a replacement management path has been tested from another device.
- **IPv6.** Mirror every IPv4 rule for IPv6 (private ranges are `fc00::/7` for ULA plus each VLAN's /64), and allow the ICMPv6 that neighbor discovery and path MTU need. Inbound IPv6 from the internet is blocked by a stateful firewall without NAT; keep it that way except for deliberate pinholes.
- **UPnP and NAT-PMP** let any device open inbound ports without asking. Turn them off, or allow them only for one network and specific devices (a game console) if the owner accepts the risk.
- **Temporary allow rules** get a comment with a date and a reason, and a reminder to remove them.

## Port forwards: avoid them

Prefer a VPN (`wireguard-vpn.md`) to exposing services. If a forward is unavoidable: one port to one host, a service that is patched and has authentication of its own, sources restricted where possible, and logging on. Never forward router or NAS admin pages, SSH with password login, SMB, RDP, databases, hypervisor consoles or DNS (an open resolver is abused for amplification attacks).

## DNS control (optional, networks you administer)

- Allow DNS from each network only to the local resolver. Block outbound TCP and UDP 53 and TCP 853 (DNS over TLS) to anything else, or redirect plain port 53 to the resolver with a NAT rule on the gateway for devices with hard-coded resolvers.
- This cannot stop DNS over HTTPS to arbitrary servers. Tell household members or staff that DNS is filtered and logged (`pihole-dns.md`, privacy).

## A Linux router example (nftables)

```text
table inet filter {
  chain input {
    type filter hook input priority filter; policy drop;
    ct state established,related accept
    ct state invalid drop
    iifname "lo" accept
    meta l4proto { icmp, ipv6-icmp } accept
    iifname { "trusted", "iot", "guest" } udp dport { 53, 67, 123 } accept
    iifname { "trusted", "iot", "guest" } tcp dport 53 accept
    iifname "mgmt" tcp dport { 22, 443 } accept
  }
  chain forward {
    type filter hook forward priority filter; policy drop;
    ct state established,related accept
    ct state invalid drop
    iifname "trusted" accept
    iifname "iot" ip daddr 10.42.30.20 tcp dport 8123 accept        # home automation hub
    iifname { "iot", "guest" } oifname "wan" accept
    limit rate 10/minute log prefix "fw-forward-drop: "
  }
}
```

Interface names, addresses and ports are examples. NAT (masquerade on `wan`) lives in a separate `nat` table.

Applying rules to a remote router without locking yourself out:

```bash
nft -c -f /etc/nftables.d/candidate.nft                     # syntax check only, changes nothing
{ echo "flush ruleset"; nft list ruleset; } > /root/nft-before.nft
systemd-run --on-active=300 --unit=nft-rollback /usr/sbin/nft -f /root/nft-before.nft
nft -f /etc/nftables.d/candidate.nft                       # only with the owner's go-ahead
# verify from each network, then cancel the rollback:
systemctl stop nft-rollback.timer
```

The candidate file should start with `flush ruleset` (or delete only its own table) so that loading it replaces rather than adds rules. Make the change persistent through the distribution's nftables service only after verification.

## Test every rule from both sides

From a test device in each network:

```bash
nc -vz -w 3 10.42.10.15 22               # expect: refused or timed out from IoT
nc -vz -w 3 10.42.30.20 8123             # expect: open from IoT (named exception)
dig @10.42.30.2 example.com              # expect: answer from every network
nmap -Pn -p 22,53,80,443,445 10.42.40.1  # from guest, its own gateway: only 53 open
```

Then confirm the matching block line in the firewall log, so you know the right rule did the work. Check the public side from outside the network (a phone on mobile data) for any open port you did not intend. Scan only networks and addresses the owner controls.

## Done when

- The zone matrix is written down and every rule maps to one cell or one named exception.
- Allowed and blocked flows were tested from each network, for IPv4 and IPv6, with log lines for the blocks.
- No admin interface, resolver or NAS console answers from guest, IoT or the internet; UPnP is off or deliberately limited; temporary rules are gone.
