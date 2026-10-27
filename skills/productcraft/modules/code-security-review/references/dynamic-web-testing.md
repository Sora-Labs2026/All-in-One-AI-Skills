# Authorized dynamic web testing: content discovery and fuzzing

Read this only when active, request-sending testing of a running web target is in scope: content and endpoint discovery (finding paths, files and parameters that are reachable but undocumented) and input fuzzing (sending many crafted values to one input to find one the application mishandles). Most of this module is static and read-only; this is the exception, and it carries the heaviest rules, because it sends traffic at a live system.

The default is still static. Reach for dynamic testing only when a reachability question cannot be answered from the code and the result matters: is this admin path actually exposed, does this parameter reach a sink unescaped, is this endpoint really unauthenticated. Prefer confirming a finding from the source trace (phase 5) when you can; send traffic when the code alone cannot settle it.

## Authorization comes first, in writing

Content discovery and fuzzing are active testing. Under [LaunchGuard safe operations](../../launchguard/references/safe-operations.md) they need explicit approval and a scoped authorization before a single request goes out. Get, in writing from someone who can grant it:

- **What** may be tested: exact hostnames, IP ranges, paths and parameters that are in scope, and what is out of scope.
- **Where:** a staging or test environment that mirrors production, never production itself and never a system you do not own or are not authorized to test. Third-party services, shared infrastructure and other tenants are out unless the owner of each has authorized it.
- **When and how hard:** a window, and a rate ceiling the owner accepts.
- **Who to contact** if something breaks, and the agreement to stop on their word.

Testing a system without this is not a technique choice, it is unauthorized access. If the scope is unclear, stop and ask; do not assume. Keep the written scope with the test output.

## Set up against staging, with real limits

- **Point at the test environment.** Use the staging URL, test accounts and synthetic data. Production user data must never be a test target or appear in results.
- **Rate-limit every run.** Cap requests per second and concurrency low enough that the service stays healthy; add a small delay between requests. The goal is to find issues, not to load-test or trip the owner's abuse defenses. A discovery run that knocks a shared staging box over is a failure even if it finds something.
- **Use the tool the project or team already has,** installed locally. Do not fetch a new scanner from the network mid-task without approval (that falls under the same safe-operations rule as any `curl | sh`). A missing tool makes the check `NOT_VERIFIED`, not skippable another way.
- **Record the exact invocation** (target, wordlist or input set, rate, filters) so the run is reproducible and auditable.

## Content and endpoint discovery

The aim is to enumerate reachable paths, files and parameters the documentation does not list, then decide which matter.

- **Calibrate against the target's "not found" response first.** Many apps answer a missing path with 200 and a soft-error page, or a consistent size. Establish that baseline and filter it out, or every run drowns in false hits. Tools with an auto-calibration mode do this for you; turn it on.
- **Filter by response, not by guesswork:** status code, response size, word or line count, or a regex on the body. Start permissive, see the shape of the responses, then tighten.
- **Authenticated discovery** finds more. Drive it with a captured authenticated request (headers, cookies, tokens) and put the fuzz marker only in the part you are varying. This is how object-reference checks are probed: vary an ID in an authenticated request and watch for another account's data coming back. Handle any captured credentials as secrets (`../../agent-safety/references/secrets.md`); never commit them or print them in results.
- **Triage the hits.** A reachable path is a lead, not a finding. Interesting ones: administrative and debug endpoints, backup and configuration files, version-control or dependency metadata, anything that returns data for an identity that should not see it. Confirm each the module's way (phase 5) before it becomes a finding.

## Input fuzzing

Fuzzing here means sending many values to one input to find one the application handles unsafely (an error that leaks internals, an injection that reaches a sink, an authorization gap on a varied identifier).

- **Fuzz one position at a time** so you can attribute a result to a cause. Mark exactly the field, header or path segment under test.
- **Watch for anomalies, not just error codes:** a different status, a response size or timing that stands out, a stack trace, a database or framework error, data that belongs to another user. The outlier is the lead.
- **Stay non-destructive.** Discovery and probing send reads and bounded, reversible requests. Do not run destructive payloads, create persistence, exfiltrate data in bulk, or attempt real account takeover or payment charges. One request that demonstrates the flaw is enough; proving it twice adds risk, not evidence (the "least possible effect" rule in the module guide).
- **Prefer the smallest demonstration.** For an injection, a marker that comes back unescaped or a benign value that reaches the sink proves it without a weaponized payload.

## From a lead to a finding

A tool hit is where confirmation starts, not ends. Take each candidate through the module's prove-or-discard step (phase 5): write who triggers it, what they send, which check should have stopped it and what they gain, then trace it in the source to the exact line. Rate severity from demonstrated impact and who can reach it, never from the tool's label. Fixes and regression tests follow [fix and verify](fix-and-verify.md); a dynamic finding also gets, where possible, an automated test at the HTTP layer so it cannot regress.

Many findings from dynamic testing map straight to the baseline or a vulnerability class: an exposed debug route ([AI-generated code bugs](ai-generated-code-bugs.md), leftover debug routes), an object-reference gap (baseline #7, lock record access), an input that reaches a sink ([vulnerability classes](vulnerability-classes.md)). Cite the control or class rather than re-deriving it.

## Report honestly

- State the scope tested and, as plainly, what was **out** of scope and therefore unexamined. A discovery run proves nothing about paths it did not request or an environment it did not touch.
- Give the exact commands, rate and filters, and the number of requests sent.
- Keep secrets, tokens and captured session data out of the output; even redacted results reveal reachable endpoints, so write them to a private location and ask before sharing (safe-operations).

## Done when

- Written, scoped authorization exists, the target was staging or an owned test system, and the run stayed within the agreed rate.
- Every tool hit was triaged, and the ones that mattered were confirmed by a source trace and rated on demonstrated impact.
- Confirmed issues have a fix and a regression test; the report lists commands, scope, what was out of scope, and nothing destructive was run.
