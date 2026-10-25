# Threat modeling for a code audit

A threat model tells the hunt where to look and tells severity rating what matters. For a typical web app it fits in one to three pages. Write it to `security/threat-model.md` during a full audit; for a diff or focused review, keep a five-line version in your notes.

## Threats and vulnerabilities are different things

- A **threat** is an outcome someone wants, written so it stays true after any single patch: "a signed-in customer reads another customer's invoices".
- A **vulnerability** is one way the code allows that today: "`GET /invoices/:id` loads the row by ID without comparing its owner to the session user".
- Fixing a vulnerability lowers a threat's likelihood. It does not delete the threat. Past vulnerabilities are evidence that a threat is live and that siblings may exist.

Check every threat row by asking whether it would still be true once the bug you have in mind is fixed. If not, you have written down a vulnerability: move it to the findings and write the broader outcome it serves as the threat.

## Sources, and how far to trust them

| Source | Authoritative for | Caution |
|---|---|---|
| Code and configuration in the repository | What the system does | Deployed settings may differ; mark those facts `NOT_VERIFIED` |
| The owner | Intent: roles, what is public, what must never happen, business rules | Confirm every claim about code in the code |
| Docs, `SECURITY.md`, API specs, design notes | Declared scope and assumptions | Often stale |
| Git history, advisories, earlier reports | Where bugs happened before | Shows only the bugs someone already noticed; use it to find more like them, not to limit the search |

If an owner is available, show them a draft built from the code and ask what is wrong or missing; correcting a draft is quicker for them than explaining the system from nothing. The four questions of the Threat Modeling Manifesto are a good frame for that conversation: what are we working on, what can go wrong, what are we going to do about it, and did we do a good enough job?

## Step 1. System context

Two or three sentences: what the product does, who uses it, where it runs, and which parts are in scope. Name the deployment platform, the identity provider and every service that holds user data or money.

## Step 2. Assets

| Asset | Where it lives | Sensitivity | Why it matters |
|---|---|---|---|
| Session tokens and refresh tokens | Cookie `sid`, table `sessions` | critical | Account takeover |

Sensitivity is `critical`, `high`, `medium` or `low`. Assets to look for:

- Credentials, sessions, API tokens, password reset and invitation tokens.
- Signing keys, webhook secrets, provider and cloud credentials, CI secrets.
- Personal data, health, financial or government identifiers, private files and messages.
- Payment state, entitlements, credits, coupons, balances.
- Data of other tenants or organizations.
- Admin and support functions, feature flags, configuration.
- Control of the servers: anything that lets input run code on a host.
- The build and release pipeline: whoever controls it ships code to every user.
- For LLM features: the tools and data the model can reach on a user's behalf.
- Availability of shared components when one user's input can stall them for everyone.

## Step 3. Actors

| Actor | How they get in | Starting capability |
|---|---|---|
| Anonymous visitor | Public internet | Any unauthenticated route |
| Self-registered user | Open signup | Everything a free account can do. If signup is open and free, treat this actor as nearly anonymous |
| Paying customer, member of another tenant, tenant admin | Login | Their own data and role |
| Support or staff | Admin login, internal network | Elevated functions; insider risk only if in scope |
| Operator | Shell, environment variables, deploy access | Trusted. Settings they control are not attacker input unless the owner says otherwise |
| Contributor | Opens a pull request or issue | Content that CI may process |
| Dependency or action author | Publishes a package or CI action you use | Code that runs at install, build or runtime |
| Content author | Writes a document, email or web page the system ingests | Text an LLM may read and act on |

## Step 4. Entry points and trust boundaries

| Entry point | File | Who can reach it | Authentication | Boundary crossed | Assets reachable |
|---|---|---|---|---|---|
| `POST /api/orders/:id/refund` | `src/api/orders.ts` | any signed-in user | session cookie | user to another user's order | payment state |

List the obvious routes, then search for the entry points teams forget:

- Webhooks and OAuth or SSO callbacks.
- Queue consumers and cron jobs that act on data users wrote earlier.
- File imports, uploads processed later, document and image parsers, archive extraction.
- Server actions, GraphQL resolvers (each field can need its own check), RPC handlers, WebSocket messages.
- Admin panels, debug, health, metrics and documentation routes.
- Inbound email or SMS handlers, mobile deep links, browser `postMessage` listeners.
- CI workflows triggered by pull requests, issues or comments; package install scripts; migration and seed scripts.
- Prompts, retrieved documents and tool results flowing into an LLM that can call tools.

To make the list complete, use the framework's own route table and the access classes in [entry points and context](entry-points-and-context.md).

Name each boundary by what changes across it: "anonymous to application", "user A to user B's records", "tenant 1 to tenant 2", "user to admin function", "uploaded bytes to parser memory", "pull request author to CI secrets", "retrieved text to tool calls", "browser to server-only secrets".

## Step 5. Data flows

For each critical asset and each high-risk entry point, write the path:

```text
source (request field, file, message, webhook body)
  -> validation and normalization
  -> where identity and tenant come from (session or request?)
  -> stores (database, cache, queue, search index, logs, analytics)
  -> sinks (query, shell, template, file path, outbound request, response body, LLM prompt, tool call)
```

Mark three places where bugs cluster:

- **Second-order paths.** A value validated on the way in, stored, and later read back by a job or admin screen that trusts it.
- **Identity from the wrong place.** User, tenant or role taken from the body, query, a header or a client-editable token claim instead of the verified session.
- **Copies.** Exports, search indexes, caches, logs and backups that hold the data under weaker access rules than the primary store.

## Step 6. Threats

Walk STRIDE for every entry point. Ask the question in the right column for that entry point specifically.

| Category | Question for this entry point |
|---|---|
| Spoofing | Which identities does it accept (session, API key, webhook signature, service token), and can any of them be forged, replayed or borrowed? |
| Tampering | Which values that the server should own (price, role, owner, status, tenant) can the caller set or change? |
| Repudiation | If this action were abused, would the logs show who did it and when? |
| Information disclosure | What do the response, the error, the logs or the timing reveal beyond what this caller may see? |
| Denial of service | What is the most expensive work one request can trigger, and what bounds it? |
| Elevation of privilege | Is there any route from here to an admin function, another tenant or code execution? |

For CI jobs, cloud roles and service accounts, fill in a small table instead:

| Identity | Used for | Allowed to do | Who or what can obtain it | Where the grant is defined |
|---|---|---|---|---|

Flag every gap between "used for" and "allowed to do", every way an untrusted party can obtain the identity, and every grant defined outside the repository (`NOT_VERIFIED` until the owner confirms it).

**Use history as evidence.** Search commit messages for past security work and read each hit's diff: what was fixed, where, and how it was reachable. Fixes that share a surface and a bug type usually describe one threat; write it once and cite the commits as its evidence. Then look for unfixed code shaped like each fix; the more you find, the higher the likelihood.

```bash
git log --all -i -E --oneline \
  --grep='secur|vuln|CVE-|GHSA-|exploit|xss|csrf|ssrf|inject|travers|idor|bypass|escape|sanitiz|overflow|leak'
git show --stat <hash>     # then read the diff of each relevant hit
```

**Rank** each threat by impact (`critical`, `high`, `medium`, `low`) and likelihood (`likely`, `possible`, `unlikely`). Likelihood rises when the entry point is reachable without an account, the technique is well known, the same area had fixes before, or many siblings exist. It falls only for a control verified on every path, not for a control that merely exists.

Keep two more lists: **parked threats** (considered and set aside, each with its reason, such as "no multi-user data" or "actor out of scope") and **open questions** for the owner (facts the code cannot answer).

## Step 7. Coverage matrix

Turn the model into the work list for hunting. One cell is one entry surface, one boundary and one vulnerability class that applies to it.

| ID | Surface | Boundary | Class | Status | Evidence or reason | Findings |
|---|---|---|---|---|---|---|
| C-01 | `GET /api/orders/:id` | user to other users' orders | access control | FAIL | two-user test | CSR-001 |
| C-02 | `POST /api/search` | anonymous to database | SQL injection | PASS | `src/search.ts:10-40` binds every value, including sort | |
| C-03 | file import | upload to parser | XML external entities | NOT_APPLICABLE | no XML parsing in repo | |

- Group many similar routes into one surface when they share the same handler code and checks; split them when their checks differ.
- Add a class to a surface only when the surface does what that class needs: builds queries, touches files, renders HTML, fetches URLs. A route that never touches the filesystem gets no path traversal cell.
- Only cells with recorded evidence count as covered. A general remark that an area "looks fine" covers nothing.

## Template for `security/threat-model.md`

```markdown
# Threat model: <system>
Date, commit, scope, sources used (code, owner, docs, history)

## 1. Context
## 2. Assets            (table)
## 3. Actors            (table)
## 4. Entry points and trust boundaries   (table)
## 5. Data flows        (one block per critical asset or risky entry point)
## 6. Threats           (ID | outcome the actor wants | actor | via which entry points | rank: impact / likelihood | what stops it today | evidence: commits, findings)
## 7. Parked threats    (threat, reason)
## 8. Open questions
## 9. Coverage matrix   (or a pointer to security/code-audit-findings.json)
```

## Done when

- Every entry point from the inventory appears in the table, including the forgotten kinds above.
- Every entry point has at least one threat, or a parked entry with its reason.
- Each threat names an actor, an asset and an outcome, and would still be true after any single bug is fixed.
- History was searched, or the reason it could not be is recorded.
- The coverage matrix exists and every cell has a status by the end of the audit.
- Open questions are listed for the owner instead of being guessed.
