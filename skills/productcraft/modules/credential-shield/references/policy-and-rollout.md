# Policy, control flow, and rollout

## Decision policy

Keep policy small and explainable. Configuration values in `assets/risk-policy.example.json` are **illustrative**, not defaults approved for production. Select thresholds from real capacity, traffic distribution, known-good baselines and abuse patterns.

Take care that attackers may manipulate anonymous activity. A single-target flood may not prove the real account holder is risky. Attack-derived score should often target the suspicious *request/source/campaign* rather than globally degrading the victim's account. Security outcome updates should be atomic, expire predictably, and not perform linear scans at request time.

- **Allow:** normal processing for benign/recognized behavior.
- **Observe:** suspicious but uncertain behavior, log metrics only.
- **Step up:** prefer non-disruptive server-verified challenges for risky automation; after correct credentials, use existing robust MFA/passkeys before session creation when needed. A CAPTCHA is not an independent authentication factor.
- **Throttle:** small, capped, retryable server-side delays or attempt budgets. Never hold 30k requests sleeping in server workers or saturate hash pools; use admission queue/backpressure/rejections.
- **Deny:** short, high-confidence correlation-backed action with monitored rollback; don't globally disable legitimate accounts based solely on attacker-generated failures.

## Storage and concurrency correctness

1. Use atomic increment/TTL and sliding/tumbling window behavior as supported by storage; include exact boundaries in tests.
2. Keep rolling key generations bounded and expire old keys; avoid unbounded arbitrary-identifier cardinality under a spraying attack.
3. Limit the risk store's own work and request budget; include retry/timeout logic and an explicit degradation mode.
4. Where email/OTP sends are costly, rate limit send *operations* and deduplicate requests safely without exposing whether an account exists.
5. Avoid synchronous global scans. Batch or stream aggregated campaign detection.
6. Do not fail-open universally under an active large-scale attack nor fail-closed universally for all legitimate users. Decide action per endpoint, risk, and availability, and document tradeoffs.
7. Make challenges time-limited, tied to the correct request/action/context, and replay-resistant under provider contract. Do not accept a client bool like `captchaPassed=true`.

## Rollout stages

- **Stage 0, audit:** identify endpoints and measure current failed login rates, p95/p99 login latency, challenge/OTP use, and known-good conversion.
- **Stage 1, shadow:** integrate counters and risk decisions without enforcement; validate accuracy, privacy, resource usage, and trusted provenance.
- **Stage 2, limited controls:** activate per-source/identifier admission safeguards and low-friction challenges on a small cohort, under feature flag and explicit approval.
- **Stage 3, tune:** adjust false-positive rates against legitimate cohorts (mobile roaming, VPN, enterprise NAT, accessibility clients, new devices) and capacity.
- **Stage 4, full release:** retain emergency disable/rollback; alert on unacceptable friction or changed success rates. Keep versioned rules.

## Rollback

Rollback does not mean removing all baseline rate limits and security monitoring. Disable only the newly introduced, harmful rule or flip enforcement to observe-only. Keep independent auth controls and incident alerts. Document which flag, dashboard, or config revision controls each rule, who owns it, and how to verify the result.

## False positive discipline

Treat new device, privacy browser, VPN, shared TLS fingerprint, country changes, and unknown ASN as context rather than conclusive maliciousness. Prefer remembered trustworthy proof or WebAuthn/MFA alternatives over an inaccessible CAPTCHA-only gate. Never use behavior or fingerprints as a replacement for authentication.

## Security tradeoffs to explicitly report

- What a compromised single client could still do.
- Whether a provider-hosted login is outside your application middleware.
- Whether cross-IP correlations run fast enough and are bounded under 30k+ sources.
- Cost and resource impact when the risk store is under attack.
- Unknown-account enumeration exposure via response status/body/timing/challenge variation.
- Accessibility and genuine-user dropout due to challenges.
