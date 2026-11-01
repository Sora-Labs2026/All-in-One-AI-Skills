# Interface health: errors, drops, duplex, optics and flaps

Read this when users report loss, slowness or intermittent reachability that may come from a link; when a switch, router or Linux host shows CRCs, drops, resets or flaps; when monitoring alerts on interface error or discard counters; or when a change needs before-and-after link evidence.

## Rates, not totals

A counter is a total since the last clear or reload. A large number may be years old. What matters is how fast it grows now.

1. Note when counters were last cleared: the `Last clearing of "show interface" counters` line, or uptime.
2. Capture the counters, wait a fixed interval under normal load (5 to 15 minutes is typical), capture again, and compute the increase per minute and as a share of packets.
3. Capture **both ends** of the link the same way. Receive errors describe the signal arriving at that port, so the fault is often the cable, optic or far-end transmitter, not the port that reports it.

Prefer deltas to `clear counters`: clearing destroys evidence that others, and the monitoring system, may rely on. If clearing helps, record the baseline first and ask.

```text
show interfaces GigabitEthernet1/0/24
show interfaces GigabitEthernet1/0/24 counters errors
show interfaces status | include 1/0/24
show interfaces GigabitEthernet1/0/24 transceiver detail     ! optics with digital monitoring
show logging | include 1/0/24|changed state|line protocol|err-disable
show interfaces status err-disabled
```

Linux hosts:

```bash
ip -s -s link show dev eth0          # rx/tx errors, dropped, overrun, carrier
ethtool eth0                         # speed, duplex, auto-negotiation, link detected
ethtool -S eth0                      # driver counters (names differ by driver)
ethtool -m eth0                      # optic module data, if supported
ethtool -a eth0                      # pause frames
```

SNMP pollers should use the 64-bit counters (`ifHCInOctets`, `ifHCOutOctets`): a 32-bit octet counter wraps in about 34 seconds at 1 Gbit/s, which makes rates meaningless.

## What each counter points to

| Counter | Meaning | Common causes |
|---|---|---|
| CRC, FCS-Err | Frame arrived with a bad checksum | Damaged or poor cable, dirty fiber or connector, failing optic, electrical noise, duplex mismatch (on the full-duplex side) |
| Input errors | Sum of receive-side errors | Read the sub-counters (CRC, frame, overrun, ignored) before concluding |
| Runts | Frames shorter than 64 bytes | Duplex mismatch, collisions, faulty NIC |
| Giants | Frames longer than the MTU allows | MTU mismatch between the two ends or along the path |
| Overrun, ignored | The port could not move frames to memory fast enough | Bursts beyond hardware capacity, CPU-bound software platforms |
| Input queue drops | Packets for the CPU were dropped | Control-plane or punted traffic load; check `show processes cpu sorted` |
| Output drops (total output drops) | Egress queue full | Congestion, microbursts, QoS policy, a smaller downstream link |
| Late collisions | Collision after the first 64 bytes | Duplex mismatch (on the half-duplex side) or cable too long |
| Collisions | Normal only in half duplex | A link that negotiated half duplex |
| Interface resets, carrier transitions | The link went down and up | Flapping cable or optic, power save, keepalive failure, the far end rebooting |

## Diagnosis by symptom

**CRCs or input errors rising**
1. Confirm they rise now (deltas), and on which end.
2. Check speed and duplex on both ends: `show interfaces Gi1/0/24 | include duplex|speed` and `ethtool eth0`.
3. For fiber, read optic levels with `transceiver detail` and compare receive power with the module's own warning and alarm thresholds shown in the same output, not with a number from memory. Clean connectors with proper tools, then reseat or replace the patch cord, then the optic.
4. For copper, replace the patch cord before anything else. Cable diagnostics (`test cable-diagnostics tdr interface ...` where supported) can bring the link down briefly on some platforms; treat it as a change.
5. Re-measure after each single change, so you know which one fixed it.

**Drops**
1. Separate input drops from output drops.
2. Compare the interface rate with its capacity. The default `load-interval` averages over five minutes and hides bursts; output drops with low average use usually mean microbursts (many senders into one port, or a fast link feeding a slower one).
3. Look at the QoS policy and queue counters (`show policy-map interface Gi1/0/24`).
4. Fix congestion with capacity, link aggregation or QoS designed for the traffic. Buffer tuning is a last resort with platform-specific trade-offs and needs a window.

**Duplex and speed**
- Keep auto-negotiation on both ends; 1000BASE-T and faster copper require it.
- If one end must be fixed, fix both ends to the same values and document why. Forcing one end while the other auto-negotiates makes the auto end fall back to half duplex: the half-duplex side logs late collisions, the full-duplex side logs CRCs and runts, and throughput collapses under load.

**Flapping and err-disabled ports**
- `show logging` around the flap times, then the reason in `show interfaces status err-disabled` (BPDU guard, port security, link-flap detection, UDLD).
- Fix the cause first. Re-enabling the port (`shutdown` then `no shutdown`) is a change; automatic err-disable recovery hides repeat offenders.

**Slow internet, LAN fine (small sites and homes)**
- Check WAN interface errors and drops, then LAN uplink use and output drops, then the gateway's CPU during a transfer.
- Compare wired and wireless tests from the same host before blaming the provider. A gateway that cannot route or inspect at line rate often shows high CPU with clean counters.

## Parsing counters in automation

Split `show interfaces` output into one block per interface at each header line (`<name> is <state>, line protocol is <state>`), and parse counters only within that block. Fixed-size text windows misattribute counters between ports. Prefer structured sources where available: TextFSM templates, NAPALM `get_interfaces_counters`, SNMP or streaming telemetry. Store raw output alongside parsed values for anything that drives a decision.

## Report

```text
Link:      <device A port> <-> <device B port>, <medium, optic type>
Window:    <start, end, interval>
A side:    CRC +n, input errors +n, output drops +n, resets +n, duplex/speed
B side:    ...
Optics:    rx/tx power vs module thresholds (or "not available")
Cause:     <one sentence that explains both ends>
Proposed:  <cable, optic, negotiation or capacity change, with window and rollback>
Verify:    deltas over the same interval after the change are zero or near zero
```

## Pitfalls

- Judging a link by counters from one end.
- Treating historical totals as an active fault.
- Clearing counters before saving a baseline.
- Treating output drops as a cable problem before checking congestion.
- Mixing forced and auto-negotiated settings on one link.
- Several fixes at once, so nobody knows which one worked.
