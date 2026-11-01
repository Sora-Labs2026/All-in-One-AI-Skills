# VLAN segmentation for home, homelab and small-office networks

Read this when a flat network is being split into trust zones (trusted, servers, IoT, guest, management), when trunk and access ports or SSID-to-VLAN mapping need planning, or when devices stop working after segmentation. Plan and readiness come first (`homelab-design.md`); the rules between VLANs are in `home-firewall.md`.

## What a VLAN does and does not do

- A VLAN is a separate layer 2 network on shared switches. 802.1Q adds a tag with the VLAN ID (1 to 4094) to frames on **trunk** links; **access** ports carry one VLAN untagged, so the end device knows nothing about it.
- A VLAN alone does not stop traffic between networks: the gateway routes between them unless firewall rules say otherwise. Segmentation is VLANs plus rules, created together.
- Each VLAN gets its own subnet, gateway address, DHCP scope and firewall policy.

## Design table

Write this before configuring anything:

| VLAN | Name | Subnet | SSID | Wired ports | Purpose and policy |
|---|---|---|---|---|---|
| 10 | trusted | 10.42.10.0/24 | Home | desks | Laptops and phones; may start connections anywhere internal |
| 20 | iot | 10.42.20.0/24 | Things | TVs | Internet plus named exceptions; nothing toward trusted |
| 30 | servers | 10.42.30.0/24 | none | NAS, hosts | Accepts named flows; DNS resolver lives here |
| 40 | guest | 10.42.40.0/24 | Guest | none | Internet only; client isolation on the AP |
| 99 | management | 10.42.99.0/24 | none | infrastructure | Switch, AP and controller management; reachable from admin devices only |
| 999 | parking | none | none | unused ports, trunk native | Carries nothing |

Start with three or four zones and add more only for a reason the owner can state. Every SSID costs airtime (beacons and management frames), so keep SSIDs few and map several device types onto one zone where the policy is the same.

## Ports and tagging

| Link | Mode | Tagged | Untagged (native, PVID) |
|---|---|---|---|
| Switch to gateway | Trunk | All VLANs in use | None, or the parking VLAN |
| Switch to switch | Trunk | Only the VLANs needed beyond it | Parking VLAN, the same on both ends |
| Switch to access point | Trunk | The SSID VLANs | Often the management VLAN, because many APs take their own address untagged; check the AP's documentation |
| Wired client | Access | None | The client's VLAN |
| Unused | Access, shut down | None | Parking VLAN |

- **Native VLAN hygiene:** do not use VLAN 1 for users or management, and make sure no client access port is in a VLAN that is native on any trunk between switches. That combination is what double-tagging VLAN hopping relies on.
- **Unmanaged switches** belong only on access ports, carrying one VLAN. Behind a trunk they mix VLANs or drop tags unpredictably.
- On Cisco IOS switches: `switchport mode access`, `switchport access vlan 20`; trunks with `switchport mode trunk`, `switchport trunk allowed vlan 10,20,30,40,99` and `switchport trunk native vlan 999`. Add VLANs to an existing trunk with `switchport trunk allowed vlan add 50`; without `add`, the command replaces the list (`cisco-ios.md`).

## Wi-Fi

- One SSID per zone, each with its own passphrase. WPA3 where clients support it; a WPA2/WPA3 transition mode or a WPA2-only SSID for IoT devices that cannot join otherwise, on the IoT VLAN only.
- Guest SSID: client isolation on, no access to local networks, ideally a captive or rotating passphrase.
- Do not share the trusted passphrase with IoT setup apps; give them the IoT SSID.

## Devices that rely on discovery

Casting, AirPlay, printers, speakers and many smart-home hubs find each other with mDNS or SSDP, which do not cross VLANs. When the phone is in trusted and the TV in IoT:

1. Enable an mDNS repeater or reflector on the gateway for exactly those two VLANs (many firewalls offer one; on Linux, Avahi's reflector).
2. Allow trusted to the device's address on the ports it needs; replies are allowed by state.
3. If the device must open connections back (some speakers and hubs do), find them in the firewall log and add a narrow rule from that device to the specific host and port.
4. If a device class cannot work across VLANs, decide with the owner: move the controller next to it, or accept it in trusted. Write the decision down.

## Migration without lockout

1. Back up the gateway, switch and AP configurations, and confirm a recovery path (console, or a switch port that stays on today's network).
2. On the gateway, create the VLAN interfaces, addresses and DHCP scopes. Leave the existing untagged network exactly as it is.
3. Tag the new VLANs on the gateway uplink and on AP ports. Nothing moves yet.
4. Create the new SSIDs. Join a test phone; check its lease, gateway, DNS, internet access, and the blocked flows.
5. Move device groups one at a time, lowest risk first (guest, then IoT), adding named exceptions as real needs appear in the logs.
6. Change wired ports to their access VLANs, one at a time.
7. Move management last: create the management VLAN, give each infrastructure device an address there, confirm you can reach every one from an admin device, and only then remove management from the old network.

Platform notes:

- **MikroTik RouterOS:** turning on `vlan-filtering=yes` on the bridge you are connected through cuts you off unless the management VLAN interface and bridge VLAN entries already exist. Use Safe Mode, which reverts if the session drops.
- **OpenWrt** (21.02 and later on DSA hardware): VLANs are bridge VLAN filtering entries on `br-lan`; changes apply when you save and apply, with an automatic rollback prompt in the web interface; keep it enabled.
- **OPNsense and pfSense:** VLAN devices on the LAN parent interface, each assigned as an interface with a static gateway address and its own DHCP range. Rules on a new interface default to block, so nothing works until you add them.
- **Controller-managed systems:** networks, SSIDs and port profiles are created in the controller and pushed to devices. Changing the port profile of the port the controller or your laptop uses is a classic lockout.

## Verify

From a device in each VLAN:

- The lease is in the right subnet, with the right gateway and DNS server.
- The internet works; the local resolver answers.
- Blocked flows fail and appear in the firewall log; named exceptions work.
- Management interfaces answer only from admin devices.
- On the switch, `show interfaces trunk` (or the platform's equivalent) shows only the intended VLANs on each trunk, and `show vlan brief` places each access port correctly.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| New VLAN gets no address | VLAN not tagged on some trunk between client and gateway, or DHCP scope missing | Check tagging hop by hop; check the scope |
| IoT devices can still reach everything | VLANs created, firewall rules not | Add the zone rules (`home-firewall.md`) |
| IoT device has no DNS after blocking private networks | The block caught the resolver or gateway | Allow DNS to the resolver above the block |
| Casting stopped working | Discovery does not cross VLANs | mDNS repeater plus narrow allow rules |
| Locked out of the switch or AP | Management VLAN or native VLAN changed on the port in use | Console or the reserved port; Safe Mode or revert timers next time |
| Guest can open the router's admin page | Firewall's own addresses not protected | Block the "this firewall" addresses except DNS and DHCP |
