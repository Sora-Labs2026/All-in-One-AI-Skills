# Standards and vendor documentation

Consult these for current guidance. Check current editions and provider entitlements before implementing; do not treat this module as a compliance certification.

1. OWASP Credential Stuffing Prevention Cheat Sheet:
   https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html
   Layered mitigations, password spraying, bot protection, MFA/passkeys and careful challenges.
2. OWASP Authentication Cheat Sheet:
   https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
   Login throttling, account lockout tradeoffs, enumeration prevention, adaptive auth.
3. OWASP Multifactor Authentication Cheat Sheet:
   https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html
   Independent authenticators, step-up, passkeys, anti-downgrade.
4. OWASP Top 10 2025, A07 Authentication Failures:
   https://top10.owasp.org/2025/A07_2025-Authentication_Failures/
   Common authentication weaknesses and protections.
5. NIST SP 800-63B-4 (July 2025 final):
   https://pages.nist.gov/800-63-4/sp800-63b.html
   Authentication, rate limiting, identity protection, user experience.
6. Cloudflare JA4 Signals overview:
   https://blog.cloudflare.com/ja4-signals/
   Fingerprint spoofability, aggregate context and limitations.

Practical caveat: security guidance evolves; verified vendor constraints and contemporary OWASP/NIST recommendations take precedence over hypothetical examples in this module.
