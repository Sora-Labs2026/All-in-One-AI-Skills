# Audit phases in detail

Read the section for the phase you are in. Phase 2 (threat model) is in [threat-modeling.md](threat-modeling.md), phase 4 (secrets, dependencies, CI) in [secrets-and-dependencies.md](secrets-and-dependencies.md), and phases 7 and 8 (fix, verify, report) in [fix-and-verify.md](fix-and-verify.md).

## Phase 0. Scope and rules of engagement

Write the scope before reading code in depth:

```text
Repository: <name>   Commit: <short sha> (+ N uncommitted files)   Depth: full | diff <base>...<head> | focused <target>
In scope: <paths, services>          Out of scope: <paths, services, reason>
May run: <read-only only | project tests locally | local dev server on localhost with a test database>
Owner contact for questions: <name or "none">     Earlier audits used: <paths or "none">
```

```bash
git rev-parse --short HEAD
git status --porcelain            # do not overwrite or stash the user's uncommitted work
git log --oneline -20             # recent activity and who is changing what
ls security/ 2>/dev/null          # earlier reports and findings to re-verify
```

What may run without asking, and what needs approval, follows [LaunchGuard safe operations](../../launchguard/references/safe-operations.md). Specific to code audits:

- **Before running any project command**, read what it does: `package.json` scripts, `Makefile`, `conftest.py`, test setup files, `docker-compose.yml`. Lifecycle scripts and test setup can call real services or delete data.
- **Run target code with dummy secrets.** Give every credential the code reads a fake value, point databases at a local test instance, and keep real keys out of the environment of any process that runs target code.
- **No new tools from the network without approval.** Use what is installed. A missing scanner makes that check `NOT_VERIFIED`; it does not justify `curl | sh`.
- **Earlier findings are input, not output.** Re-check each against the current code before carrying it forward. An area an earlier run covered is not skipped unless its code is unchanged.

## Phase 1. Inventory

Find the stack and the entry points before reading handlers in depth. Useful searches (ripgrep shown; adapt globs to the stack):

```bash
git ls-files | sed -n 's/.*\.\([A-Za-z0-9]*\)$/\1/p' | sort | uniq -c | sort -rn | head -15
rg -n --glob '!**/{node_modules,vendor,dist,build}/**' \
  -e '(app|router)\.(get|post|put|patch|delete|all)\(' -e '@(app|router|bp)\.(route|get|post|put|delete)\(' \
  -e '@(Get|Post|Put|Patch|Delete|Request)Mapping' -e 'Route::(get|post|put|patch|delete)' -e 'HandleFunc\(' .
rg -l "^['\"]use server['\"]" .                   # Next.js server actions
rg -i -l -e 'webhook' -e 'cron' -e 'consumer' -e 'subscribe\(' .
rg -o --no-filename -e 'process\.env\.[A-Z0-9_]+' -e "os\.environ(?:\.get)?\(?\[?['\"][A-Z0-9_]+" \
  -e 'getenv\("[A-Z0-9_]+' . | sort -u          # names only, never values
```

Then run the bundled map for a ranked reading order:

```bash
python3 <productcraft>/modules/code-security-review/scripts/code_audit.py map --root . --json-out security/code-audit-map.json
```

Record for each entry point: file, who can reach it, how identity is established, the identity the code runs as (database role, service account, API key), and the assets it touches. Note the tests that exist; untested surfaces are where scans most often miss things.

## Phase 3. Hunt by vulnerability class

### Order of work

Read first where an attacker needs the least and gains the most. A quick score per cell:

- **Reach:** 3 if no account is needed, 2 if any self-registered account will do, 1 if a privileged role or internal access is needed, 0 if only the operator can reach it.
- **Asset:** 3 critical, 2 high, 1 medium, 0 low, from the threat model's asset table.

Work from the highest `reach x asset` down. Break ties in favor of code that changed recently, code that needed security fixes before, and code with no tests.

### Method for one coverage cell

1. **Write the rule** the code must keep, in one sentence: "an order is returned only to its owner or to staff with the `orders:read` permission".
2. **Find where the rule is enforced** and which identity the check uses. That identity must come from the verified session or token, never from the request body, query or a client-editable header.
3. **Follow the input** from the entry point through parsing, normalization, storage and every transformation to the place it is used. Read the code; names and comments are not behavior.
4. **List the other routes to the same outcome** and read each one: the other HTTP methods on the resource, bulk and batch endpoints, exports and reports, search, GraphQL fields and nested resolvers, older API versions, admin and import tools, background jobs. For each, check three things: the condition is the same, the identity comes from the same trusted place, and the check runs before the side effect.
5. **Feed it awkward input** that the interface accepts:
   - *Shape:* arrays where a scalar is expected, objects where a string is expected, duplicated or extra keys.
   - *Size:* empty, zero, negative, enormous.
   - *Text:* other encodings, Unicode look-alikes, changed case, trailing dots and slashes.
   - *Time and state:* expired or revoked tokens, steps done out of order, two requests at the same moment.
6. **Record the result.** The cell becomes `PASS` with the paths read and the invariant that holds, a candidate (go to phase 5), `NOT_APPLICABLE` with a reason, or `NOT_VERIFIED` with the missing fact.

The class guides say what to look for per class and stack: [vulnerability classes](vulnerability-classes.md), [AI-generated code bugs](ai-generated-code-bugs.md) and [language pitfalls](language-pitfalls.md).

### Where controls usually diverge

- A middleware or route matcher that protects `/api/*` but not server actions, RPC handlers, file routes or a newly added path.
- A validation schema applied to the create endpoint but not to update, import or the admin form that writes the same table.
- An ownership check on read but not on update or delete, or on the item route but not the list or export route.
- A check performed after the side effect (the email is sent, the file is written, the job is queued) instead of before it.
- A client-side check with no server-side twin.
- A sanitizer applied on input in one path, while another path stores raw data that a different renderer outputs.

### Variant hunting

When a candidate looks real, search the rest of the code for its relatives before moving on: other callers of the same unsafe helper or API, queries built the same way, handlers next to it that skip the same check, and copies of the same block. Give each relative its own location and conditions; keep them under one finding when a single change would close them all.

## Diff reviews

```bash
git diff --name-only <base>...HEAD
git diff <base>...HEAD -- <file>
git log --oneline <base>..HEAD
```

Read every changed file in full, plus the callers of changed functions and the callees they now rely on. Ask of the change:

- Does it add an entry point, a route, a job, a webhook or a new input field?
- Does it remove, weaken, reorder or bypass a check? Did tests change to accommodate that?
- Does it change where user, tenant or role comes from?
- Does it add raw SQL, HTML rendering, shell calls, file paths, outbound requests, deserialization or `eval`?
- Does it widen a query, a serializer or an API response?
- Does it add a dependency, change a lockfile, touch CI, Docker or infrastructure files?

A diff review reports findings in the changed code and in old code the change newly exposes. It does not certify the rest of the repository.

## Large codebases and limited time

- **Partition.** Split the work by subsystem or entry surface, not by file count. Each partition has its own slice of the coverage matrix.
- **Write a short attacker's note per component** (what enters it, what it trusts, what it could leak or run), then read the notes side by side to spot chains that cross components.
- **Rank files** with `code_audit.py map` and read in that order; parsers, auth, handlers and anything that touches untrusted input come first.
- **With sub-agents,** give each one a distinct partition and the threat model, never the same slice twice. Merge their candidates by root cause.
- **Iterate.** After the confirmed issues are fixed, review the same scope again; with the known bugs out of the way, attention lands on new ones.
- **Say what was not reached.** Cells you did not get to are `NOT_VERIFIED` with "not reviewed in this pass". Never present a partial pass as full coverage.

## Phase 5. Prove or discard

### Write the claim

Fill in the same card for every candidate before judging it:

| Question | Example |
|---|---|
| Who triggers it, and what can they already do? | Any self-registered user, member of tenant A |
| What do they send or do? | `PATCH /api/projects/:id` with a project ID that belongs to tenant B |
| Which check should have stopped it? | `assertMember(projectId, session.user)`, which this route never calls |
| What do they end up with? | Tenant B's project settings changed; response 200 with B's data |
| Where does it happen? | `routes/projects.ts:41`, `services/projects.ts:88`, `db/projects.ts:12` |

If you cannot say who is harmed and what concretely happens, it is not a finding yet. Good practice that is missing but lets nobody cross a boundary belongs in the hardening notes.

### Evidence that confirms

| Class of bug | Best evidence | Acceptable static evidence |
|---|---|---|
| Access control, IDOR, tenant isolation, mass assignment | Local test with two synthetic users or tenants | Complete trace showing no check on the path and identity from the request |
| Injection (SQL, NoSQL, command, template, header) | Unit test that passes a marker payload and asserts the built query or argument list, or the marker effect in a test database | Complete source-to-sink trace with no binding, escaping or allowlist on any branch |
| XSS and unsafe rendering | Render test asserting the marker is not escaped | Trace into a raw-HTML sink with no sanitizer |
| Path traversal, SSRF, open redirect | Test asserting the resolved path, host or redirect target falls outside the allowed set | Trace with no normalization or allowlist |
| Memory corruption (native code, `unsafe`, FFI) | Sanitizer build (AddressSanitizer, UndefinedBehaviorSanitizer) crash in project code on a small input | Static reasoning alone is weak here; prefer `LIKELY` |
| Races and double spend | Deterministic test that runs the two operations concurrently against a local database | Trace showing check and use in separate transactions with no lock or unique constraint |
| ReDoS, algorithmic blowup, decompression bombs | Bounded timing or memory measurement as input size grows, in a local process with a time limit | Pattern analysis of the regex or algorithm |
| Crypto and token handling | Negative tests: expired, wrong audience, wrong algorithm, reused token are rejected | Trace showing the missing check |
| Behavior that depends on deployment or provider settings | Owner-observed check in an authorized environment | Record as `LIKELY` with the exact `unverified_condition` |

Stop at the smallest proof. For command injection, assert the argument list contains the marker or stub the process call; do not run destructive commands. For SSRF, assert the URL the code would fetch; do not fetch internal addresses.

### Argue against it

A candidate is kept only if it survives five questions, answered from the code:

1. **Does it exist?** The cited file and line contain the code described, and that code behaves as claimed in the library version the lockfile pins. Check framework behavior in that version's documentation; "the framework handles it" is a claim, not an answer.
2. **Does untrusted input really get there?** Name the entry point and cite every hop from it to the vulnerable line. Most false positives fall here: the code exists, but nothing an outsider controls reaches it.
3. **What stands in the way?** List each guard on that route: validation, types, parameter binding, escaping, middleware, database policies, feature flags, configuration.
4. **Is there another road?** For each guard, look for a route, method, encoding or job that reaches the same line without passing it.
5. **What does the attacker actually gain?** Restate the result in terms of an asset from the threat model. If the answer is "nothing they could not already do", drop it.

### Drop a candidate when

- the code is not there, or does something other than what the claim says;
- only trusted parties control the input: it is dead code, runs only in tests, runs only from an operator's script or setting, or has become a constant, enum or bounded number before it is used;
- a guard holds on every road to the line;
- the actor is allowed to do this anyway: they only affect themselves, or an admin is doing an admin's job;
- the class cannot happen there, for example a buffer overflow in safe Rust or in Go without `unsafe` or cgo, or a predictable value used where predictability does not matter.

### Do not drop a candidate just because

- exploitation needs several steps or another finding; record the chain instead;
- the frontend prevents it; attackers call the API directly;
- IDs are UUIDs; unguessable IDs reduce discovery but are not an authorization check, and IDs leak through URLs, logs and shared links;
- the framework "probably" protects it, without a check of the version's documentation;
- it needs an account, when anyone can sign up.

### Independence and duplicates

- Let someone other than the finder judge. With sub-agents, hand the claim card and the repository path to one that has not seen the hunt and ask it to knock the claim down; settle disagreements by reading the code again, not by counting opinions. Without sub-agents, do the five questions only after hunting is over, working from the code instead of your notes.
- Candidates that share a root cause, so that one code change would close all of them, become one finding. Keep the clearest trace and list every location.

### Outcome

- `CONFIRMED`: executed test (`TESTED_LOCAL`) or complete static trace (`STATIC_CONFIRMED`) with no unresolved condition.
- `LIKELY`: complete trace, but one decisive fact is outside the repository; name it in `unverified_condition` and say how the owner can check it.
- `POSSIBLE`: a lead; record `next_check`, the exact test or read that would settle it. Never presented as a vulnerability and never given a severity.
- `FALSE_POSITIVE`: keep it with `rejection_reason`, so the next run does not raise it again without new evidence.

## Phase 6. Rate severity

Rate from what was demonstrated, not from the class name. Not every SQL injection is critical and not every XSS is minor.

**1. Start from the impact the evidence shows.**

| Impact | Typical demonstrated results | Starting severity |
|---|---|---|
| Severe | Running commands on a server; dumping or rewriting the main database; logging in as any user; obtaining signing keys or privileged provider secrets; moving money | CRITICAL |
| Major | Reading or changing other users' or tenants' sensitive data; becoming an admin; running script in other users' browsers; getting paid features or credits without paying | HIGH |
| Moderate | Limited data exposure; actions on a narrow set of resources; a component stalled for other users | MEDIUM |
| Minor | Non-sensitive internals disclosed; weaknesses that only matter as part of a chain | LOW |
| Negligible | A confirmed observation with no direct consequence | INFO |

**2. Adjust for reach.** Lower one level if only privileged roles, staff or the internal network can trigger it. Lower two levels if it needs local or physical access to a machine. An open, free signup counts as no barrier.

**3. Adjust for conditions the attacker does not control,** such as a non-default setting, a narrow timing window or a specific action by the victim. Lower one level when exploitation depends on one of them, two levels when it needs several. Do not go below LOW for a confirmed boundary crossing.

**4. Apply the caps.** Do not rate above what the evidence shows the attacker gets. A chain is rated by what the whole chain achieves; record each link as its own finding and list the links in each one's `chain` field. `POSSIBLE` leads have no severity. `LIKELY` findings are rated as if the unverified condition holds, and the report says so.

**5. Write the reason.** One sentence: "HIGH: any signed-up user reads any customer's invoices; no preconditions."

If the organization requires CVSS, write the vector string (CVSS v3.1 or v4.0) from the evidence and compute the score with the FIRST calculator or a maintained library, never by mental arithmetic. Map scores to the five labels only if the organization has a policy for it.

Treat severity above MEDIUM as a recommendation for a human to confirm, especially when it drives a launch decision in LaunchGuard.
