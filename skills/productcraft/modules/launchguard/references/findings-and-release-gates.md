# Reporting, prioritization and release gates

## Status vocabulary

- `PASS`: actual control and sufficient scoped evidence verified.
- `FAIL`: confirmed defect or configuration vulnerability. Always severity, priority, owner, fix and verification step.
- `NEEDS_REVIEW`: suspicious indicator, potentially unsafe assumption or sensitive design decision.
- `NOT_VERIFIED`: cannot determine without runtime, secrets rotation, production access, tests, configured tools, vendor dashboard or authorization.
- `NOT_APPLICABLE`: this product lacks the feature; prove absence with an inventory reference.

## Finding metadata

`id`, `gate` (1-5), `title`, `severity` (CRITICAL/HIGH/MEDIUM/LOW/INFO), `confidence` (CONFIRMED/LIKELY/POSSIBLE), `status` (OPEN/FIXED/ACCEPTED/FALSE_POSITIVE), `file`, `line`, `affected_assets`, `threat_scenario` (non-weaponized), `impact`, `evidence_type`, `evidence_summary` (redacted), `fix`, `verification`, `owner`, `manual_actions` and `remaining_risk`.

Severity is context-sensitive. Examples:
- Critical/high: live privileged key publicly exposed; exploitable IDOR exposing PII; unauthenticated admin mutation; demonstrable payment entitlement bypass; leakage of an entire user database.
- Medium: missing CSRF protection on relevant state-changing cookie-authenticated route; overly verbose production errors revealing internal paths; exploitable low-impact XSS; permissive CORS with actual risk.
- Low/info: missing defense-in-depth header in narrowly scoped app, undocumented retention, an unused example file pattern.

Not every scanner hit is a vulnerability. Report tool-only hints as `NEEDS_REVIEW` without fabricated severity. Low-risk gaps can be blockers if combined with an exploitable chain.

## Launch decision

- **NO-GO**: unresolved confirmed critical/high account takeover, data disclosure, authorization/billing bypass, secret exposure without revocation, or any credible severe issue with significant unmitigated impact. A risk owner may expressly accept risk but review must keep factual issue OPEN/ACCEPTED and never relabel it PASS; recommendation may remain NO-GO.
- **CONDITIONAL GO**: tested core flows; no confirmed unresolved severe issue; some medium/low or deployment-specific `NOT_VERIFIED` items remain with owner, deadline and documented acceptance/mitigation. Conditional does not mean safe to deploy if the unverified component is a core auth/payment control.
- **GO (scoped)**: critical flows and five gates verified for the reviewed code/environment, blockers resolved, tests passing, deployed-only checks either observed or explicitly excluded from the scope; no unowned critical unknowns. This is a recommendation, never a security guarantee.

A mostly untested repository should be `INSUFFICIENT EVIDENCE / NO-GO RECOMMENDATION`, not a false PASS or automatic failure. This is distinct from a proven vulnerability.

## Output conventions

`security/launchguard-report.md` sections: scope/date/commit, stack/services, summary, 5-gate status matrix, risk register with location and redacted evidence, what was changed, test commands + actual results, deployment-only/manual tasks, explicit release decision and rationale, residual risks, post-launch monitoring.

`security/launchguard-findings.json` is optional for machine-readable records. Avoid dumping tokens, PII, stack dumps or request bodies. Keep scanner's heuristic JSON separate from confirmed finding JSON.

Follow the report template in `assets/SECURITY-REVIEW-REPORT.template.md` and workflow checklist `assets/RELEASE-CHECKLIST.md`.
