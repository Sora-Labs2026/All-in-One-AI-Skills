# Remote access with WireGuard

Read this when someone wants to reach a home or small-office network from outside: a WireGuard server on the gateway or a Linux host, peer configurations for phones and laptops, split or full tunnel, dynamic DNS, CGNAT, or a tunnel that connects but passes no traffic. WireGuard is in the Linux kernel since 5.6 (2020) and built into the common open-source firewall distributions; the tools are `wg` and `wg-quick`.

## Decide before generating keys

| Question | Why it matters |
|---|---|
| What must remote devices reach? One server, a few services, every internal network, or the internet through home? | Sets client `AllowedIPs` and the firewall rules for the VPN zone |
| Where does the tunnel end? The gateway, or a host behind it? | On the gateway, the VPN is just another firewall zone; on a host it needs a port forward and routing |
| Is the home connection reachable inbound? | CGNAT or no public address means a different design (below) |
| Do the address ranges collide? | A home `192.168.1.0/24` collides with many hotels and offices; renumber or route around it (`homelab-design.md`) |
| Who are the peers? | One key pair per device, named after the device and person, so one can be revoked alone |

**Inbound reachability check:** compare the WAN address shown on the gateway with the public address seen from outside. If they differ, or the WAN address is in `100.64.0.0/10`, the connection is behind CGNAT and inbound port forwarding cannot work. Options: ask the provider for a public IPv4 address, use IPv6 end to end where both sides have it, run the hub on a small rented server that both sides connect out to, or use a managed WireGuard-based mesh service, accepting its account and trust model.

## Modes

| Mode | Client `AllowedIPs` | Use when | Watch for |
|---|---|---|---|
| Split, one service | `10.42.30.10/32` | Reach one NAS or host | Simplest firewall rule |
| Split, internal networks | `10.42.10.0/24, 10.42.30.0/24, 10.42.200.0/24` | Admin access and home services | The DNS server must be inside these ranges if `DNS =` is set |
| Full tunnel | `0.0.0.0/0, ::/0` | Untrusted Wi-Fi, home filtering everywhere | Home upload speed limits everything; include `::/0` or IPv6 leaks around the tunnel |

## Server on a Linux host

Generate keys on the machine that will use them, with private permissions from the start, and never print private keys into the session:

```bash
sudo install -d -m 700 /etc/wireguard
sudo sh -c 'umask 077; wg genkey > /etc/wireguard/server.key; wg pubkey < /etc/wireguard/server.key > /etc/wireguard/server.pub'
```

`/etc/wireguard/wg0.conf` (mode 600). Use `PostUp` to read the key file rather than pasting the key into the config:

```ini
[Interface]
Address    = 10.42.200.1/24
ListenPort = 51820
PostUp     = wg set %i private-key /etc/wireguard/server.key

[Peer]
# alice-phone
PublicKey  = <alice-phone public key>
AllowedIPs = 10.42.200.10/32

[Peer]
# bob-laptop
PublicKey  = <bob-laptop public key>
AllowedIPs = 10.42.200.11/32
```

- On the server, a peer's `AllowedIPs` is both the route to that peer and the list of source addresses accepted from it. Keep it to the peer's tunnel address (`/32`, plus a `/128` for IPv6). Because the key binds the address, firewall rules can safely name peers by tunnel address.
- Enable forwarding (`net.ipv4.ip_forward = 1`, and `net.ipv6.conf.all.forwarding = 1` for IPv6) in a file under `/etc/sysctl.d/`.
- Prefer **routing** to NAT: add a static route on the gateway for `10.42.200.0/24` via the server's LAN address, so internal hosts see real client addresses and the firewall can apply per-peer rules. Masquerading the VPN behind the server's LAN address is the fallback when the gateway cannot hold a static route.
- Forwarding rules are scoped: allow `wg0` to the internal networks the plan names, allow established return traffic, drop the rest (`home-firewall.md` has an nftables layout). Never a blanket forward-accept.
- Do not set `SaveConfig = true` on a hand-edited file: `wg-quick` overwrites the file on shutdown and loses edits.
- Start with `sudo wg-quick up wg0`; enable at boot with `systemctl enable wg-quick@wg0`. Both are changes on the owner's host: ask first.

On a gateway (OPNsense, pfSense, OpenWrt, RouterOS), the same pieces exist in the interface: an instance with a listen port and tunnel address, one peer per device, a WAN rule allowing UDP to the listen port, and rules on the WireGuard interface for what peers may reach.

## Client configuration

```ini
[Interface]
PrivateKey = <generated on this device; never leaves it>
Address    = 10.42.200.10/32
DNS        = 10.42.30.2

[Peer]
PublicKey  = <server public key>
Endpoint   = vpn.example.org:51820
AllowedIPs = 10.42.10.0/24, 10.42.30.0/24, 10.42.200.0/24
PersistentKeepalive = 25
```

- Phone and desktop apps can generate the key pair on the device; only the public key goes to the server. When a configuration must be built elsewhere, a QR code (`qrencode -t ansiutf8 < alice-phone.conf`) shown on the local screen is the transfer; it contains the private key, so do not screenshot, email or paste it, and delete the file after import.
- `PersistentKeepalive = 25` keeps NAT mappings open for clients behind NAT that must stay reachable; it costs a little battery on phones.
- An optional preshared key per peer (`wg genpsk`) adds a symmetric layer, a hedge against future attacks on the key exchange.

## Exposure, DNS name and keys

- Forward only the WireGuard UDP port, only to the WireGuard endpoint. WireGuard does not answer unauthenticated packets, so scans see nothing, but never forward management pages alongside it.
- A dynamic address needs dynamic DNS. Use the gateway's built-in client or a scoped API token for one record; the token lives in a mode-600 file or the gateway's settings and is entered by the owner, never in chat (`../../agent-safety/references/guided-setup.md`).
- Revoke a lost device at once: `sudo wg set wg0 peer <public key> remove` and delete its block from the file (or edit the file and run `sudo wg syncconf wg0 <(wg-quick strip wg0)`, which applies changes without dropping other peers).
- Keys do not expire. Rotate a key when a device is lost, replaced or suspected, and review the peer list periodically.

## Troubleshooting

```bash
sudo wg show                      # per peer: endpoint, latest handshake, transfer
ip route get 10.42.30.10          # on the client: is the destination routed into the tunnel?
sysctl net.ipv4.ip_forward        # on the server: 1
ping -M do -s 1372 10.42.30.10    # through the tunnel: large packets with don't-fragment
```

| Symptom | Likely cause | Fix |
|---|---|---|
| No handshake ever | UDP port not forwarded or blocked, wrong endpoint or DDNS name, wrong server public key, CGNAT | Check each from outside; compare public keys (public keys may be shown) |
| Handshake, but no traffic to the LAN | Forwarding off, firewall drops, no return route (routed mode) or no masquerade (NAT mode), destination outside client `AllowedIPs` | Check in that order |
| Names fail, addresses work | `DNS =` server not reachable through the tunnel | Include the resolver's address in `AllowedIPs`; allow DNS from the VPN zone |
| Small pings work, web pages and copies stall | MTU: `wg-quick` sets 80 bytes below the outgoing interface; PPPoE or nested tunnels need less | Set `MTU = 1380` (or lower) on the client and retest with don't-fragment pings |
| Works on Wi-Fi, not on mobile data or the reverse | One network's address range overlaps a home range, or the network blocks UDP | Renumber the home side; try another port only if the owner agrees |

A healthy tunnel with traffic shows a recent handshake (WireGuard re-keys every two minutes while traffic flows).

## Done when

- Each device has its own key pair, named peer entry and the narrowest `AllowedIPs` that meets the need.
- From outside (mobile data), each client reaches what the plan allows and is blocked from the rest, names resolve, and large transfers work.
- Only the WireGuard port is forwarded; no private key appeared in chat, logs, tickets or version control; the revocation steps are written down.
