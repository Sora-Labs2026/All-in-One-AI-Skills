# LaunchGuard release checklist

- [ ] Inventory routes, roles, tenants, assets, trust boundaries and actual vendors.
- [ ] Gate 1 secrets checked in source/client bundles/Git history, rotation actions recorded.
- [ ] Gate 2 personal-data flow mapped and minimized; logs/responses/session/deletion reviewed.
- [ ] Gate 3 production variables, debug, errors, headers, CORS, cookies, TLS, dependencies checked.
- [ ] Gate 4 server authz/owner/tenant access, payments, webhook verification and business logic reviewed.
- [ ] Gate 5 safe synthetic negative tests written/executed for relevant misuse scenarios.
- [ ] All 20 security baseline controls marked PASS / FAIL / NEEDS_REVIEW / NOT_APPLICABLE / NOT_VERIFIED with evidence.
- [ ] Required code changes have regression tests and actual test results recorded.
- [ ] Provider/dashboard/deployment checks distinguished from source-only checks.
- [ ] Remaining risks have owner, severity, verification status and follow-up.
- [ ] Report excludes raw credentials, personal data and executable exploit details.
- [ ] Explicit scoped GO / CONDITIONAL GO / NO-GO decision recorded.
