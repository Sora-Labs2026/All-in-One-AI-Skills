# DNS filtering with Pi-hole

Read this when a network-wide DNS filter is being installed, moved, made redundant or debugged: Pi-hole on a small Linux host or in a container, blocklists and allowlists, upstream resolvers (plain, encrypted or local recursive), local names, DHCP integration, or devices that lose name resolution after the switch. The same rollout rules apply to other filtering resolvers.

Facts below match Pi-hole v6 (released February 2025), which moved settings into `/etc/pihole/pihole.toml`, built the web server into `pihole-FTL`, renamed the Docker environment variables (`FTLCONF_...`) and changed several CLI commands. Check `pihole -v` and the release notes for the installed version before giving commands.

## Before installing

- An always-on host with a reserved address (a DHCP reservation or a static address), preferably wired. Pi-hole needs little CPU or memory.
- Decide where it lives: in the servers network, with a firewall rule allowing DNS to it from every network that uses it (`home-firewall.md`).
- Decide who will be told: query logs show every name each device looks up. Household members or staff should know the network filters and logs DNS.
- Keep the gateway's own DNS as the documented fallback during rollout.

## Installing

**Container (pin the version):**

```yaml
services:
  pihole:
    image: pihole/pihole:<date-based release tag>   # pin; read the release notes before changing
    network_mode: host                              # real client addresses; needed if Pi-hole serves DHCP
    environment:
      TZ: "Europe/Berlin"
      FTLCONF_dns_listeningMode: "all"              # queries arrive from other VLANs; protect with the firewall
      FTLCONF_webserver_port: "8080"                # keep port 80 free on the host if needed
    volumes:
      - ./etc-pihole:/etc/pihole
    restart: unless-stopped
```

Set the admin password interactively after the first start, so it never sits in a file or the chat: `docker exec -it pihole pihole setpassword`. In bridge networking, publish port 53 on the host's LAN address only (`"10.42.30.2:53:53/udp"` and the same for TCP); this also avoids the clash with `systemd-resolved`, which listens on `127.0.0.53:53` on many Linux distributions. Bridge mode can make every query appear to come from the container gateway, which breaks per-client statistics and rules.

**Directly on the host:** follow Pi-hole's documented install method for that operating system. If it is a downloaded script, save it, read it, and let the owner run it; do not pipe a URL into a shell (`../../agent-safety/GUIDE.md`).

## Upstream resolvers: pick one and say why

| Option | Who sees the queries | Notes |
|---|---|---|
| The provider's or a public resolver, plain DNS | That resolver, and anyone on the path | Simplest; pick one with a privacy policy the owner accepts |
| Encrypted forwarding (DNS over TLS or HTTPS) through a local forwarder such as Unbound with TLS upstreams or dnscrypt-proxy | The chosen resolver only | The DNS proxy mode of `cloudflared`, long used for this, was deprecated by its maintainer in 2025; do not build new setups on it |
| Unbound as a local recursive resolver (Pi-hole's guide uses `127.0.0.1#5335`) | Each authoritative server sees its own part; the provider can see the unencrypted queries | No single third party sees everything; Unbound validates DNSSEC |

Validate DNSSEC in one place. Never point Pi-hole's upstream at the gateway while the gateway forwards to Pi-hole: that is a loop and resolution stops.

## Rolling out

1. Test on one device by setting its DNS server by hand. Check public names, local names and a known blocked domain.
2. Point one network's DHCP DNS option at Pi-hole; renew a lease and test again from that network.
3. Watch the query log for a few days for breakage (banking apps, work VPN portals, captive portals, firmware updates, medical or security devices), then move the next network.
4. For redundancy, run a second Pi-hole with the same lists and settings and hand out both. Clients use either server, not "primary first", so a public resolver as the second entry bypasses filtering for part of the traffic.
5. If Pi-hole serves DHCP itself, turn off the gateway's DHCP for that network first; two DHCP servers hand out conflicting leases. Otherwise enable conditional forwarding (reverse lookups to the gateway) so the dashboard shows hostnames.

## Leaks that bypass the filter

- **IPv6:** if the gateway advertises its own or the provider's IPv6 DNS server in router advertisements or DHCPv6, clients use it. Advertise Pi-hole's IPv6 address (a ULA works) or stop the gateway from advertising DNS.
- **Hard-coded resolvers:** some devices ignore DHCP and ask public resolvers directly. On networks the owner administers, block outbound port 53 and 853 except from Pi-hole, or redirect port 53 to Pi-hole at the gateway (`home-firewall.md`).
- **DNS over HTTPS in browsers and operating systems:** Pi-hole answers the Mozilla canary domain and the iCloud Private Relay domains by default so that clients fall back to network DNS; other DoH clients cannot be fully stopped at DNS level.

## Lists

- Start with the default list. Add only a few well-maintained lists, one at a time, and watch for breakage; more lists mean more false positives, not proportionally more protection.
- Allow a wrongly blocked domain with `pihole allow <domain>` (v6; v5 used `pihole -w`) and a comment saying why. Use `pihole -q <domain>` to see which list blocks a domain.
- The installer schedules a weekly list update; `pihole -g` updates on demand.

## Local names

Create local records for services under `home.arpa` or a subdomain you own (Settings, Local DNS Records, or `dns.hosts` in `pihole.toml`), CNAMEs for aliases, and keep the list in the network document. Avoid `.local`, which belongs to mDNS.

## Security, privacy and backups

- Never expose port 53 or the web interface to the internet: an open resolver is used in amplification attacks. With listening mode `all`, the firewall is what keeps it private.
- Restrict the web interface to admin devices; keep the admin password strong and in a password manager.
- Set a privacy level and log retention the owner agrees to (v6 keeps the long-term database for 91 days by default, `database.maxDBdays`).
- `pihole -d` builds a debug log and offers to upload it to Pi-hole's servers. It contains network details; upload only with the owner's consent.
- Back up with Teleporter (web interface or `pihole-FTL --teleporter`). The archive contains settings and the password hash; store it privately.
- Update deliberately: `pihole -up` on a host install, a new pinned tag for containers, after reading the release notes.

## Troubleshooting

```bash
pihole status                         # are DNS service and blocking active?
dig @10.42.30.2 example.com           # direct answer from Pi-hole
dig @10.42.30.2 <a domain on your blocklist>   # expect 0.0.0.0 or :: (default blocking mode)
pihole -q example.com                 # which list, if any, blocks it
pihole -t                             # live query log
pihole reloaddns                      # reload lists and flush the cache
```

| Symptom | Likely cause |
|---|---|
| Nothing resolves after a reboot | Host got a new address (no reservation), container did not start, port 53 taken by another service |
| Some devices are not filtered | IPv6 DNS advertised by the gateway, hard-coded resolvers, a public secondary DNS |
| Queries from other VLANs refused | Listening mode only accepts local requests; set `all` and rely on the firewall |
| All clients show one address | Container bridge networking; use host networking or macvlan |
| A site or app broke | A list entry; find it with `pihole -q`, allow it with a reason |

## Done when

- Every network that should use Pi-hole receives it by DHCP (IPv4 and IPv6), and a test client in each gets filtered and unfiltered answers as expected.
- Fallback, redundancy choice, upstream choice, privacy settings and the backup location are written down.
- Port 53 and the web interface are unreachable from guest networks where intended and from the internet.
