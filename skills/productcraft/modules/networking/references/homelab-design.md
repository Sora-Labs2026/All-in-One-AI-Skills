# Home and small-office networks: readiness and design

Read this when someone plans a new home, homelab or small-office network, wants to grow beyond the internet provider's router, asks for an IP plan, DHCP and DNS layout, or is about to change VLANs, DNS, firewall rules or remote access and needs to know whether the setup is ready. The first answer is a plan: inventory, capability check, risks, a staged order of changes with validation and rollback. Platform-specific steps come only once the platform, current topology and recovery path are known.

## Inventory before advice

| Area | Ask |
|---|---|
| Internet edge | Modem or fiber terminal? Does the provider's box route (NAT, Wi-Fi) or is it bridged? Public IPv4, CGNAT, IPv6 prefix size? |
| Gateway | Which device routes, firewalls, serves DHCP and DNS, and could terminate a VPN? Model and firmware version |
| Switching | Managed (802.1Q VLANs) or unmanaged? Which ports go where? PoE budget? |
| Wi-Fi | Access points or mesh? Wired backhaul? Can each SSID map to a VLAN? |
| Addressing | Current subnets and DHCP ranges; ranges used by work VPNs or other sites the owner connects to |
| Services | NAS, hypervisor, home automation, cameras, printers, game consoles, anything with a fixed address or port forward |
| Management | How will the owner reach the gateway, switch and APs if something breaks? Is there a console port or a spare wired port? |
| People | Who depends on the network (remote work, school, medical or security devices) and when an outage is acceptable |
| Experience | Beginner, comfortable or advanced; this sets how much is explained and how much is automated |

## Capability check

| Goal | Needs | If missing |
|---|---|---|
| Segmentation (trusted, IoT, guest, servers) | Gateway with VLAN interfaces and inter-VLAN firewall rules; managed switch; APs with SSID-to-VLAN mapping | Guest Wi-Fi isolation on the AP is the stopgap; plan hardware upgrades in stages |
| Network-wide DNS filtering | An always-on host with a reserved address; the gateway or DHCP server able to hand out its address | Filter per device until a host exists |
| Remote access | Inbound reachability (public IPv4 or IPv6) or a relay; a VPN-capable gateway or host | Under CGNAT, see `wireguard-vpn.md` for relay options |
| Reliable services | Wired connections, address reservations, a UPS for the core devices | Fix these before adding services |

Say plainly when the hardware cannot do what is asked, and propose the smallest upgrade that unlocks it.

## Roles and layout

```text
Internet
  |
Modem / fiber terminal      (bridge mode where possible: one router, one NAT)
  |
Gateway / firewall          routing between networks, NAT, firewall, DHCP, DNS forwarder, VPN
  |
Managed switch              trunks to gateway and APs; access ports for wired devices
  |-- Access points         Wi-Fi only, wired backhaul preferred, one SSID per trust zone
  |-- Servers and NAS       reserved addresses, names, backups, monitoring
  |-- Clients, IoT          DHCP pools per network
```

Gateway choices, by the operator rather than the feature list:

| Option | Fits | Watch for |
|---|---|---|
| Provider's router | Internet only | Little control; VLAN and DNS options often missing |
| Integrated home or prosumer system with a controller | Managed home network, clear interface | Controller dependence; features vary by model and firmware |
| Open-source firewall distribution (OPNsense, pfSense) on a small appliance | Flexible VLANs, firewall, VPN and DNS | Needs reading and a rollback habit |
| OpenWrt on supported hardware | Capable routers and APs, scripting | Check the hardware support list first |
| MikroTik RouterOS | Advanced users, low cost | Very flexible and easy to misconfigure; use Safe Mode while editing |
| A Linux host as router | Learning and tinkering | Not the only path to the internet until it has proven itself |

**Double NAT** (provider router plus your own router) breaks inbound VPNs and some games and calls. Put the provider's box in bridge or passthrough mode, or failing that, give your router the provider router's DMZ or exposed-host setting, and write down which one you did.

## Addressing

- Avoid the most common defaults (`192.168.0.0/24`, `192.168.1.0/24`, `10.0.0.0/24`) when remote access is planned: hotels, offices and other homes use them, and overlapping ranges break VPN routing.
- Pick one block and carve it predictably, so the third octet names the network:

```text
10.42.10.0/24   trusted      (VLAN 10)
10.42.20.0/24   IoT          (VLAN 20)
10.42.30.0/24   servers      (VLAN 30)
10.42.40.0/24   guest        (VLAN 40)
10.42.99.0/24   management   (VLAN 99)
10.42.200.0/24  VPN clients
Per network: .1 gateway, .2-.49 reservations, .100-.250 DHCP pool
```

- **IPv6:** if the provider delegates a prefix (a /56 or /60 is common), give each network its own /64; SLAAC needs a /64. Firewall rules must cover IPv6 as well, or segmentation leaks around them.
- **Local names:** use `home.arpa` (RFC 8375) or a subdomain of a domain you own (the best choice when you want trusted TLS certificates for internal services). ICANN reserved `.internal` for private use in 2024. Avoid `.local`, which belongs to mDNS (RFC 6762), and invented top-level names that may later be delegated.

## DHCP and DNS basics

- Exactly one DHCP server per network. A second router reused as an access point must run in AP or bridge mode with its DHCP server off.
- Reserve addresses for everything you log in to, bookmark, monitor or forward ports to. Reservations live on the DHCP server, so devices keep working if they are replaced.
- Hand out the gateway as DNS until a local resolver is deliberately introduced, and introduce it as described in `pihole-dns.md`, one network at a time.

## Cabling, power and documentation

- Wire the access points where you can; wireless backhaul halves capacity and adds failure points.
- Check the switch's PoE budget against APs and cameras.
- Put the modem, gateway, core switch and DNS host on a UPS if outages are common.
- Keep a short document: the address plan, VLAN table, port map (label both cable ends), SSID mapping, reservations, where backups are and how to restore them. Credentials go in a password manager, never in this document.

## Readiness checklist before a disruptive change

- [ ] Current configuration of the gateway, switch, APs and DNS host exported and stored off the device.
- [ ] A recovery path that does not depend on the change: console cable, a spare switch port that stays on the management network, or a laptop plan with a static address on that network.
- [ ] The factory-reset and restore procedure for each device is known.
- [ ] Provider sign-in details (for example PPPoE) are available to the owner, held in their password manager.
- [ ] A window agreed with everyone who depends on the network, and a test client ready.
- [ ] Rollback steps written in the platform's own vocabulary (menu names or CLI) before starting.
- [ ] No management interface, DNS resolver or NAS console is or will be reachable from the internet.

## Change sequence

1. Snapshot and document the current state.
2. Reserve infrastructure addresses (gateway, switch, APs, resolver, NAS, VPN endpoint).
3. Create the new network or VLAN without moving anything critical (`vlan-segmentation.md`).
4. Move one test client; check lease, gateway, DNS, internet, and that blocked flows are blocked (`home-firewall.md`).
5. Move low-risk device groups one at a time; add narrow firewall exceptions as real needs appear.
6. Introduce the local resolver per network (`pihole-dns.md`), then remote access with the narrowest routes (`wireguard-vpn.md`).
7. Move management last, from a connection that the move cannot cut.
8. Update the document; remove temporary rules.

## Plan format

```text
Home network plan: <name>
Goal:            <isolation, ad blocking, remote access, reliability, learning>
Hardware roles:  | Device | Role | Notes |
Capability check:| Goal | Possible now? | Needed |
Networks:        | Name | VLAN | Subnet | Purpose | Allowed flows |
DNS and DHCP:    <resolver, reservations, fallback>
Firewall intent: <plain-language rules, default deny between zones>
Steps:           1. <step> - check: <test> - rollback: <how>
Risks:           <what can lock the owner out and how to recover>
Later:           <optional phases>
```

Explain terms the first time for beginners; keep it compact for experienced operators.

## Done when

- The owner has a plan that matches their hardware and skills, with each step's test and rollback.
- After each step, the test client shows the expected address, gateway, DNS answers and allowed and blocked flows.
- The documentation matches the final state, and no temporary allow rule remains.
