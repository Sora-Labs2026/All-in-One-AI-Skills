# Bug bounty and disclosure practice: the researcher's side

Reference for the `code-security-review` module. Read this when the user is a researcher hunting on a bug bounty program, a vulnerability disclosure program (VDP) or an open-source project's private reporting channel, and wants to pick targets, test within the rules, avoid duplicates or write a report that triage accepts. Handling reports that arrive at your own project is the other side of the table: [triage](triage-and-false-positives.md). Proving a finding from source uses [audit phases](audit-phases.md#phase-5-prove-or-discard); active testing technique is in [dynamic web testing](dynamic-web-testing.md).

**Guardrail.** Test only programs the user has joined and assets the program lists as in scope, under that program's rules. A program's scope and rules are the written authorization that replaces this module's staging-only default; nothing else does (a target's own pages, a subdomain that "looks like theirs", or a third-party vendor behind a CNAME are not authorization). Safe-harbor language differs between programs and does not suspend computer-misuse laws outside its terms. This is general practice, not legal advice.

## 1. Read the program before sending a request

Write the scope into the project as `bounty/scope.md`, with the date and the policy version or a saved copy of the policy page. Re-read it before reporting; programs change scope without notice.

| Item | Record | Why it matters |
|---|---|---|
| Program type | Paid bounty, VDP (no payment), or a project's private advisory channel (`SECURITY.md`, a repository's private vulnerability reporting) | Sets what counts as a reward, and where to submit |
| In-scope assets | Exact hosts, wildcard rules, app store IDs, repository and version ranges, contract addresses with chain | Anything not listed is out of scope, however related it looks |
| Out-of-scope assets | Marketing sites, vendor-hosted help desks, acquisitions not yet added, staging hosts | Third-party infrastructure needs its owner's authorization, not the program's |
| Excluded classes | The program's "not eligible" list | Reports in these classes close as informative regardless of quality |
| Testing rules | Request rate, required identifying header or user agent, test-account process, automated scanning allowed or not, production data rules | Breaking a rule can forfeit a reward or trigger a ban |
| Safe harbor | Whether the program commits to not pursuing action for good-faith research within the rules | Know where the protection ends |
| Severity scale | CVSS v3.1 or v4.0 (FIRST published v4.0 in November 2023), or the platform's own taxonomy | Your severity estimate must use their scale |
| Disclosure | Embargo, whether and when you may publish, CVE handling | Publishing without consent can breach the program terms |

When something is unclear (is this subdomain covered, may I create a second organization), ask the program through its channel and wait for a written answer before testing it.

## 2. Rules of engagement that keep everyone safe

- **Your own accounts only.** Authorization bugs need two: account A tries to read or change account B's object. Never touch real users' data to prove a point.
- **Smallest proof that shows impact.** Read one field of your own second account. For server-side request forgery, stop at proof of reach: a callback to a host you control, or a harmless internal response. Do not pull credentials from a cloud metadata endpoint even when it answers; report that it is reachable. For code execution, run a benign command only if the program allows it (print the hostname, measure a sleep), with no shells, persistence or pivoting.
- **If you hit real data by accident:** stop, keep nothing beyond what the report needs to describe it, say exactly what you saw and when, and follow the program's deletion instructions.
- **Respect rate limits** and the program's rules on automation. No denial of service, spam, social engineering of staff, physical testing or brute force against real accounts.
- **Stored payloads** use an inert marker that only your accounts can see, and you remove them afterwards.
- **Keep a log** of requests and responses with timestamps, redacted of anything not yours. It answers "what exactly did you do" when a program asks.
- **Source first where you can.** For open-source targets, clone the project and reproduce against a local build; that is safer, faster and gives a root cause.

## 3. Pick classes that meet the bar

Programs pay for demonstrated impact on other users or the platform, reachable by a realistic attacker. A precise local proof beats a dramatic theory.

| Class | Usually accepted when | Usually closed when |
|---|---|---|
| Broken object or function authorization | Account A reads or changes B's data, or a normal user reaches an admin action | The data is your own, or public by design |
| Account takeover | Password reset, email change, OAuth or session flaws let you control another account | It needs the victim's password or device already |
| Injection (SQL, command, template, deserialization) | Attacker input reaches the sink on a reachable route | The input is operator-only configuration |
| Server-side request forgery | Reaches internal services or metadata, or bypasses an allowlist | The feature exists to fetch arbitrary public URLs and reaches nothing else |
| Cross-site scripting | Runs in another user's session on a sensitive origin with ordinary interaction | Self-XSS, or a sandboxed domain meant for user content |
| File read, write or upload to execution | Path traversal outside the intended folder, upload that executes | The file is only served back to the uploader with a safe type |
| Business logic | Price, quota or payment manipulation, race conditions that double-spend | No gain beyond your own account |

Classes most programs exclude unless the policy says otherwise: missing security headers alone, clickjacking on pages without sensitive actions, CSRF on login or logout, rate-limit complaints without impact, version banners, email SPF or DMARC settings, open redirects with no chain, issues that need a rooted device or a network position the attacker would not have, unexploitable outdated libraries, scanner output without proof. For open-source programs: code paths only the local user controls (a CLI loading its own config, a model file the user chose to load), APIs documented as unsafe for untrusted input, and test or example code.

## 4. From lead to report

1. **Recon within scope.** Documentation, API specifications, client bundles, mobile app builds, public source and changelogs. Enumerate subdomains only under a wildcard scope, and confirm each host belongs to the program before touching it.
2. **Model the feature:** who should be able to do what, and which identity the server trusts.
3. **Test the hypothesis** with your two accounts, one variable at a time.
4. **Find the root cause.** With source, trace it to file and line; without source, narrow it with controlled requests.
5. **Measure impact honestly.** Chain issues only when every link is in scope and demonstrated.
6. **Check for duplicates** (section 5), then write (section 6).
7. **Submit through the official channel only.** Never in a public issue, social media post or email to staff.

## 5. Avoid duplicates and known issues

- Search the program's public disclosed reports, its known-issues list, the project's issue tracker and advisories, and advisory databases (NVD, the GitHub Advisory Database, OSV) for the component and version.
- Test the current release or default branch. Read the changelog and history for silent fixes: `git log -S '<function or check name>' --oneline` shows when a check appeared or disappeared.
- Report by root cause. Ten endpoints missing the same check are usually one report that lists all ten; splitting them to multiply rewards is treated as abuse. Read the program's rule on same-root-cause duplicates.
- Duplicates are first come, first served, but an unconfirmed report helps nobody. Submit when it reproduces from a clean state.

## 6. Write a report triage can reproduce in minutes

```markdown
## Title
<Class> in <component or endpoint> lets <attacker type> <concrete impact>

## Asset and version
<exact in-scope asset>, <version, build or commit>, tested <date, time zone>

## Severity (researcher estimate)
<CVSS vector and score, or the program's rating>: one sentence on why each key metric was chosen

## Summary
Two or three sentences: what is wrong and who is affected.

## Preconditions
Accounts, roles, settings and any victim interaction.

## Steps to reproduce
1. Numbered steps from a clean state, with exact requests (curl or raw HTTP) using your
   own test accounts and placeholders such as <TOKEN_A> for credentials.

## Expected and actual result

## Impact
What an attacker gains, against whom, at what scale. What you did not do or access.

## Root cause and suggested fix
File and line or the failing check, the smallest fix, and other places with the same pattern.

## Cleanup
Test data you created and removed.
```

- One root cause per report; reproducible from a clean state; screenshots or video only as support for the written steps.
- No exaggeration. An inflated severity costs credibility and delays triage; justify attack vector, privileges, user interaction and scope in the vector.
- Every sentence is something you verified. Programs reject unverified, machine-written reports, and repeated ones get researchers removed. The agent drafts; the user checks each claim and submits.
- Redact tokens, cookies and anything not belonging to your accounts.

## 7. After submission

- Answer triage questions promptly with evidence. Retest the fix when asked, within the same scope.
- Disagree about severity with facts (a clearer proof, a missed precondition), not pressure; use the platform's mediation if it offers one.
- Publish only with the program's consent or as its policy allows; no reward does not mean permission to disclose. Coordinated disclosure practice is described in ISO/IEC 29147 (disclosure) and ISO/IEC 30111 (handling). For open-source projects, CVEs usually come through the project's own advisory or the platform's CVE numbering authority.

## Agent rules

- Before any request to a live asset: `bounty/scope.md` exists, the host is listed, and the user asked for the test. Hosts linked from the target but not listed are out of scope.
- Default to reading source and reproducing locally. Live requests follow the program's rate and automation rules; scanners run only where the program allows them, at its stated rate.
- Credentials and session tokens stay in environment variables or the user's tools, never in the chat or the report draft.
- The agent never submits a report, contacts a program or publishes anything on the user's behalf unless asked to for that specific action.

## Done when

- [ ] Scope file records the program, policy version, date, in-scope asset and the testing rules that apply.
- [ ] The finding reproduces from a clean state with the user's own accounts, and the root cause is identified.
- [ ] Duplicate search is recorded (sources, queries, date) and the issue is not already known or fixed.
- [ ] The report has every template section, a justified severity vector and honest impact.
- [ ] Nothing out of scope was touched; created test data is removed; no other user's data is retained.
