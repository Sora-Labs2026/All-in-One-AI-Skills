# Required security and usability verification

## Automated verification table

| Scenario | Expected result |
|---|---|
| 30,000 distinct IPs target a modest set of identifiers | Cross-IP per-identifier/campaign signals register; no reliance on per-IP threshold alone |
| 30,000 IPs attempt many usernames at low per-IP rates | Cohort and global campaign telemetry can detect distribution without indiscriminate global blocking |
| Attacker floods one victim's identifier | Account still has safe login/recovery alternative; no permanent attacker-induced lockout |
| Many legitimate users behind same NAT/office VPN | Low-risk users can authenticate, not blanket-challenged based on shared IP |
| Common UA/JA4 among real browsers | No denial based on shared fingerprint alone |
| Forged IP/JA4/bot-score headers from public clients | Not trusted or rejected; tests assert ingress provenance |
| JA4 missing from provider/plan | Security remains functional using verified available signals; no fabricated JA4 |
| User with no account vs known account, same bad password | Non-enumerating client-visible responses; review timing and challenge differences |
| Password hash workload during suspicious high volume | Admission bounds prevent resource exhaustion while preserving legitimate access |
| Storage temporarily unavailable/timeouts | Documented degradation behavior; auth never bypasses required MFA/session safeguards |
| Repeated parallel requests at counter boundary | Atomic correct limits under concurrency; TTL/window reset correct |
| Multiple regions/nodes | Shared state consistency aligned to stated threat model |
| Challenge replay, tampering, wrong action or expiry | Server rejects invalid challenges, does not grant session |
| MFA not complete after valid password | No full session before step-up satisfied |
| Alternate auth path (mobile/API/SSO/recovery/OTP) | Applicable controls cannot be bypassed via another path |
| Passkey login and secure account recovery | Keep available and protected; known-good success maintained |
| Metrics/logs captured during login | No password, token, OTP, cookies or raw identity identifiers leaked |
| Legitimate mobile roam/new device/assistive tech | Appropriate recovery or step-up, minimal friction and accessible flow |
| Large random username spray | Storage bounded/expiring, no unbounded key explosion |
| Security flag toggled or rollback executed | New enforcement is disabled predictably; existing auth remains intact |

## Testing protocol

1. Identify existing test framework and add **unit tests** for risk scoring, TTL windows, atomic counters, identifier normalization and no-enumeration boundaries.
2. Add **integration tests** for login/IdP adaptation, challenge callbacks, MFA session gating, proxy provenance, and protected auxiliary endpoints.
3. Add **load tests** with offline generated/synthetic identities and authorized staging environments. Never use real breach corpuses or third-party sites; no actual credential stuffing.
4. Compare against baseline median and tail auth latencies and resource use, including password hash capacity. Failing gracefully under load matters more than apparent bot-detection success.
5. Record specific test commands, assertions, environment and failures. A passing standalone demonstration is not evidence that application middleware is protected.

## Local simulator

Run `python scripts/simulate_policy.py` to see small deterministic example risk evaluations. Run `python -m unittest discover -s tests -v` for its self-tests. This is an **offline teaching harness**, not a defense to deploy. Its thresholds should never silently become production values.
