# Tenant isolation and the data lifecycle

Read this for multi-user or multi-tenant systems that keep copies of protected data (caches, search indexes, object storage, analytics, exports, backups, replicas), and for products that promise deletion, revocation or retention. Endpoint-level object authorization (IDOR) is in [vulnerability classes](vulnerability-classes.md#2-broken-access-control-and-idor). Building deletion and export features to meet privacy law is in Legal Ready ([data deletion, access and export](../../legal-ready/references/business-children-email-assets-rights.md#20-data-deletion-access-and-export)). This file follows one record through every copy and state change, looking for the path where its owner or tenant stops being enforced.

## Follow one record

Pick each protected record type that matters (invoice, message, document, membership, API key) and draw its lineage:

```text
create/update -> primary store -> caches -> search or vector index -> object storage (files, thumbnails)
  -> events and queues -> analytics, logs, traces, error tracker -> exports and reports
  -> replicas and backups -> deletion or revocation -> restore, import, undelete
```

On each edge, write which principal and tenant scope the operation, and where that scope is enforced: in the query, in a scoped repository or client extension, by row-level security, or by a separate database or schema. Edges without an answer are candidates. Most findings here are not a missing check on the main route. They are a copy, a background job or a lifecycle step that never received the tenant at all.

## Where isolation is enforced, and how it is bypassed

A `tenant_id` column is not isolation. Find the control that applies it on each read and write path, then look for the clients that skip it:

| Mechanism | Bypass to look for |
|---|---|
| ORM default scopes and global filters | Laravel `withoutGlobalScopes()`; Rails `unscoped`; Django related-object access, which uses the model's base manager and so skips a custom default manager that hides soft-deleted or other-tenant rows; Hibernate `@Filter`, which applies only where a session enables it; raw SQL helpers (`$queryRaw`, `execute`, `connection.cursor()`) |
| Scoped clients and repositories | Admin, batch, reporting, migration and job code that builds its own client; a "system" client reused in a user request |
| PostgreSQL row-level security | Table owners skip policies unless the table has `FORCE ROW LEVEL SECURITY`. Superusers and roles with `BYPASSRLS` always skip them. Views run with their owner's rights unless created with `security_invoker` (PostgreSQL 15+). `SECURITY DEFINER` functions run as their owner. More in [PostgreSQL](../../data-engineering/references/postgresql.md) |
| A tenant setting read by policies (`current_setting('app.tenant_id')`) | Under transaction pooling, a session-level `SET` leaks to the next client on that connection. Use `SET LOCAL` or `set_config(..., true)` inside the transaction. When the setting is missing, `current_setting('app.tenant_id', true)` returns NULL and the policy matches nothing (safe); code that substitutes a default tenant is not safe |
| Separate database or schema per tenant | Connection selection from a request value (subdomain, header) not tied to the session; shared tables for "global" data that turn out to hold tenant data |
| Backend-as-a-service rules | [Mobile apps](mobile-apps.md#firebase-and-other-direct-to-client-backends) and `firebase_rules.py` |

Also look for keys and names that omit the tenant:

- **Cache keys:** `report:<name>`, `settings`, `user:<email>` where emails are unique only within a tenant.
- **Object paths:** `uploads/<filename>` with no tenant or random prefix lets one tenant overwrite or fetch another's files.
- **Global unique constraints:** a constraint on a name or slug tells tenant A that tenant B already uses a value. That is an existence oracle; it matters when names are confidential.
- **Search document IDs, temporary file names, idempotency keys and rate-limit keys** shared across tenants.

## Derived copies

- **Search and vector indexes.** Filter by the caller's tenant and current permissions at query time, not only when indexing; an index built under yesterday's ACL serves yesterday's readers. Re-index or invalidate on ACL change. Vector stores add the risks in [LLM and agent risks](vulnerability-classes.md#15-llm-and-agent-risks).
- **Caches and CDNs.** Personalized responses cached under a shared key, and cache entries that survive a permission change or logout ([HTTP caching](http-caching-and-identity-binding.md#caches-and-request-framing)).
- **Files, thumbnails, previews.** A generated thumbnail or preview stored at a public or guessable URL while the original is private.
- **Analytics, logs, traces and error trackers.** These have wider access and longer retention than the primary store. Private content or credentials there are a finding when a less trusted reader can reach them ([AIG-23](ai-generated-code-bugs.md#aig-23-sensitive-data-in-logs-analytics-and-prompts)).
- **Signed URLs and share links.** Bind each to one object, one version and one operation, with a short expiry. A presigned object-storage URL keeps working until it expires even when the object's permissions change; it stops only if the signer's credentials expire or lose access. Revocable share links are stored tokens checked against current ACLs on every use.

## Lifecycle transitions

**Soft delete**
- Every read path must apply the deleted-state predicate: direct lookups, joins and relations, search, exports, background jobs, admin screens and counts.
- A membership row marked deleted that a join ignores still grants access.

**Identifier reuse**
- When a username, email, organization slug, custom domain or external account ID is freed and someone else claims it, they can inherit old references: share links, invitations, mentions, webhook targets, SSO mappings, password-reset routing.
- A tenant's custom domain or a DNS record left pointing at a released resource can be claimed by another customer of the same provider.
- Bind references to immutable internal IDs, keep freed identifiers in a tombstone list for a period, and re-verify domain ownership. For federated logins, key accounts on issuer plus subject, never on email alone.

**Revocation**
- Removing a member, downgrading a role, revoking an API key or changing a password must also end, or re-check:
  - sessions and refresh tokens;
  - cached permission sets;
  - open WebSockets and subscriptions ([RPC and messaging](rpc-and-messaging.md#websockets-and-server-sent-events));
  - scheduled jobs and automations owned by that user;
  - OAuth grants the user gave to integrations;
  - materialized share access.
- Test immediately after the change and again after any cache lifetime.

**Deletion completeness**
- Queued jobs, retries and syncs from third parties can recreate deleted records.
- Derived copies keep the data.
- Look for idempotent deletion that walks every store in the lineage, and for a list of deleted IDs that is re-applied after any restore.

**Export**
- Authorize each item after selection: the export query is often not the UI query.
- Exclude hidden fields, internal notes, soft-deleted rows and other members' private data.
- Authorize the download itself; a link alone is a bearer token. Store export files privately and expire them.

**Import and restore**
- Treat the archive as untrusted input ([path traversal and archives](vulnerability-classes.md#6-path-traversal-and-archive-extraction)).
- Never take IDs, owners or tenant fields from the file as-is: an imported ID can overwrite another tenant's record.
- Re-authorize the restored state against current policy. A backup taken before a member was removed, a key was revoked or a permission was narrowed brings those grants back.
- Undelete must check the current caller's rights, not the original owner's.

**Migrations**
- Backfills that leave `tenant_id` NULL, or set a default tenant.
- Dual-read or dual-write windows where the old code path lacks the new check.
- A new permission model behind a flag that falls back to the old one on error.
- A rollback that reopens what the migration closed.

**Retention**
- Data kept longer than promised in logs, backups or tools is a privacy and compliance issue; hand it to Legal Ready.
- It becomes a security finding when a less trusted reader can reach the retained copy, for example a support tool that shows deleted messages to agents who should not see them.

## Prove it

Use two tenants and two users per tenant, with synthetic records placed in every store the lineage touches: local database, local cache, local search instance or fake, local object storage emulator. Run the operation as the other tenant and look in each store. Then repeat after the transitions that matter: an ACL change, a member removal, a deletion, an export, a restore. A finding is the smallest observation: tenant A's request returns or changes one of tenant B's synthetic records, or a deleted record reappears.

External storage policy, replica access, backup access and retention settings are `NOT_VERIFIED`, each with the owner check that settles it (a bucket policy, a backup role, a retention setting in a console). Cross-tenant read or write of sensitive data starts at `HIGH` under the [severity rules](audit-phases.md#phase-6-rate-severity).

## Fixes that hold

- Enforce the tenant once, at the lowest shared layer every path uses (a scoped client or repository, or row-level security with `FORCE`), and make the unscoped client hard to reach from request code.
- Put the tenant in every composite key: cache, object path, unique constraint, idempotency key, search document ID.
- Make lifecycle changes propagate: deletion and revocation publish an event that every copy's owner handles, with a test per store.
- Re-authorize on restore, import and undelete; never trust provenance carried in the data.

## Done when

- Each protected record type has a lineage with the enforcing control named on every edge, or a candidate where there is none.
- Bypass clients, raw queries, background jobs and migrations that touch tenant data are listed, each with its scope check cited.
- Composite keys (cache, object path, unique constraints, idempotency, search) include the tenant, or there is a finding.
- Soft delete, revocation, deletion, export, import, restore and migration paths each have a two-tenant test or a cited trace.
- Retention gaps without a less trusted reader are handed to Legal Ready rather than reported as vulnerabilities.
