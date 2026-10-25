# API and interface contracts

Read this when you add or change an HTTP endpoint, a GraphQL schema, an RPC service, a webhook or event payload, a function exported from a library, or a boundary between modules that other code depends on.

## Find the contract and its consumers first

- **Source of truth.** Locate it: an OpenAPI or JSON Schema file, `.graphql` SDL, `.proto` files, exported types, or, if nothing else exists, the handler code. Keep exactly one source of truth checked in and derive the rest (generated types, generated docs, or a schema generated from code).
- **Consumers.** List them: web and mobile clients (installed mobile apps stay on old versions for months), other services, partner integrations, scripts, scheduled jobs, analytics exports. Search the repository; ask the user whether external consumers exist.
- **Observable equals promised.** Field names and types, nullability, ordering, defaults, status and error codes, pagination behavior, rate limits and rough latency are all relied on by someone. Do not expose what you are not prepared to support.

## Compatible and breaking changes

| Usually compatible | Breaking |
|---|---|
| New endpoint, operation, query field or event type | Removing or renaming an endpoint, field, parameter, enum value or event |
| New optional input with a default that keeps today's behavior | New required input, or an optional input made required |
| New output field | Changing a field's type, format, unit or meaning (cents to dollars, local time to UTC) |
| Relaxed validation | Tightened validation on existing input (shorter limit, new required format) |
| New enum value, **if** clients were told to accept unknown values | Changed defaults, sort order, page size or pagination style |
| New error code within an existing class (still 4xx, still retry-safe or not) | Changed status or error codes that clients branch on |
| | Changed authentication, authorization or rate-limit requirements |

- Ship a breaking change only as a new version, a new field or a new operation, alongside the old one, with a deprecation period.
- Tell clients to be tolerant readers: ignore unknown fields, map unknown enum values to a safe fallback, never depend on field order. Write this in the API docs.
- When unsure whether something breaks a consumer, treat it as breaking.

## HTTP conventions

- **Methods follow RFC 9110.** `GET` and `HEAD` are safe (no side effects). `PUT` and `DELETE` are idempotent. `POST` is neither. `PATCH` is a partial update; choose JSON Merge Patch (RFC 7396) or JSON Patch (RFC 6902) and document which.
- **Paths** use the project's existing style. Resources are nouns; an action that is not create, read, update or delete becomes a sub-resource or a command endpoint used consistently (`POST /invoices/{id}/send`).
- **Status codes:**

| Code | Use |
|---|---|
| 200 / 204 | Success with / without a body |
| 201 | Created; include `Location` |
| 202 | Accepted for asynchronous processing; return a status resource to poll |
| 400 | Malformed request (unparseable body, wrong types) |
| 401 | Not authenticated (missing or invalid credentials) |
| 403 | Authenticated but not allowed; use 404 instead when existence itself must stay hidden |
| 404 | No such resource for this caller |
| 409 | Conflicts with current state (duplicate, invalid transition, in-flight duplicate request) |
| 412 | `If-Match` precondition failed (stale version) |
| 415 | Unsupported content type |
| 422 | Well-formed but semantically invalid |
| 429 | Rate limited; include `Retry-After` |
| 500 | Unexpected server fault |
| 502 / 503 / 504 | Upstream failure / temporarily unavailable or overloaded (send `Retry-After`) / upstream timeout |

- **Data formats.** Timestamps as RFC 3339 with an explicit offset, normally UTC (`2026-10-25T09:30:00Z`). Durations with the unit in the name (`timeoutMs`) or as ISO 8601 durations. Money as integer minor units or a decimal string, plus an ISO 4217 currency code; never binary floating point. Identifiers as strings (JavaScript numbers lose precision above 2^53 - 1). Document the difference between an absent field and `null`.
- **Responses expose only what the caller may see.** Serialize through an allowlist, never a raw ORM entity (LaunchGuard baseline #17), and accept only allowlisted writable fields (#8).

## Errors

- One shape for every error. Default to Problem Details (RFC 9457, `application/problem+json`): `type` (a URI naming the problem kind), `title`, `status`, `detail`, `instance`, plus extension members.

```json
{
  "type": "https://api.example.com/problems/validation",
  "title": "Request has invalid fields",
  "status": 422,
  "code": "VALIDATION_FAILED",
  "errors": [
    { "pointer": "/email", "code": "FORMAT", "message": "Enter an email address like name@example.com" },
    { "pointer": "/quantity", "code": "MIN", "message": "Must be at least 1" }
  ],
  "requestId": "01JB7Q3W5K6X"
}
```

- The machine-readable `code` is the contract. Human text may change at any time; clients must not parse it.
- Report every invalid field at once, located by JSON Pointer (RFC 6901) or a field path.
- Never return stack traces, SQL, internal hostnames, file paths or secrets. Log them server-side under the request ID and return only the ID.
- Make retryability explicit: document which codes are safe to retry and send `Retry-After` with 429 and 503.
- Do not return `200` with `{"success": false}`.

## Lists: pagination, filtering, sorting

- Every list endpoint paginates from the first release, with a server-enforced default and maximum page size (for example default 50, maximum 200).
- **Cursor (keyset) pagination** for large or frequently changing collections. The cursor encodes the last row's sort values plus a unique tiebreaker and is opaque to clients (for example base64 of JSON):

```sql
SELECT id, created_at, title
FROM tasks
WHERE tenant_id = $1
  AND (created_at, id) < ($2, $3)      -- values decoded from the cursor
ORDER BY created_at DESC, id DESC
LIMIT $4 + 1;                          -- one extra row tells you whether a next page exists
```

- Back it with a matching index, here `(tenant_id, created_at DESC, id DESC)`.
- **Offset pagination** (`?page=7`) only for small or rarely changing data, or when users must jump to a page number. It slows down with depth and skips or repeats rows when data changes between requests.
- Always order by something unique (append the primary key). Make total counts optional or approximate on large tables.
- Use one envelope everywhere, for example `{"data": [...], "nextCursor": "..." }` with `null` on the last page, or `Link` headers (RFC 8288).
- Allowlist filterable and sortable fields; never interpolate raw sort or filter strings into SQL (LaunchGuard #13).

## Idempotency and concurrency

Clients, proxies, SDKs and queues retry, and they retry most when your system is already struggling. Design state-changing operations so that a duplicate request cannot cause a duplicate effect.

- **Make it naturally idempotent where you can:** `PUT` of a full representation, "set status to X" instead of "toggle", `DELETE` that returns the same result whether or not the record still exists.
- **Idempotency keys for creates and charges.** Accept an `Idempotency-Key` request header (the IETF HTTP API working group has a draft standard for it) and handle it like this:
  1. The client creates one key per user intent and reuses it for every retry of that intent. A key minted per attempt protects nothing.
  2. The server inserts a record of (caller, key, request fingerprint, state = in progress) **before** doing the work, guarded by a unique constraint on (caller, key). The constraint decides which concurrent request wins, not a lookup beforehand.
  3. Completed key with the same fingerprint: return the stored status and body. Same key with a different body: reject with 422. Key still in progress: respond 409 so the client retries later, or wait for a bounded time.
  4. Keep records longer than the longest path that can redeliver the request: client retry windows, queue redelivery and dead-letter replays.
  5. Scope keys per caller or tenant so callers cannot collide or read each other's stored responses.
- **Unknown outcomes.** After a timeout the server may or may not have done the work. The client retries with the same key or checks status; it never creates again with a new key.
- **Lost updates.** For resources edited concurrently, return an `ETag` and require `If-Match` on `PUT`, `PATCH` and `DELETE` (412 when stale), or keep a `version` column and update with `WHERE id = $1 AND version = $2`, treating zero affected rows as a conflict.
- **Long operations** return 202 with a status resource rather than holding the connection open.

## Versioning and deprecation

- Evolve one version additively for as long as possible. Create a new major version only for a change that cannot be made additively.
- Pick one version mechanism and keep it: a path prefix (`/v2/`, simplest to route and cache) or a header or media type. Some APIs pin a dated version per client account; that also works if applied consistently.
- **Deprecation sequence:** mark it in the schema (OpenAPI `deprecated: true`, GraphQL `@deprecated(reason: "...")`, protobuf `[deprecated = true]`), document the replacement, send `Deprecation` (RFC 9745) and `Sunset` (RFC 8594) headers on HTTP responses, measure remaining use per consumer, announce a date, and remove only when use is zero or the date has passed with the owner's approval.
- **Libraries** follow semantic versioning: mark deprecated exports (`@deprecated` in JSDoc, `warnings.warn(..., DeprecationWarning, stacklevel=2)` in Python), keep them working until the next major, and list them in the changelog.

## GraphQL specifics

- Evolve the schema instead of versioning it. Add fields, deprecate old ones with a reason, remove them after field-level usage reaches zero.
- Nullability changes: an output field going from nullable to non-null is safe for clients, non-null to nullable is breaking. An argument going from optional to required is breaking.
- Paginate with cursor-based connections (`edges`, `node`, `pageInfo { hasNextPage endCursor }`) and a maximum `first`.
- Batch per-request loads with a DataLoader-style batcher so nested resolvers do not issue one query per parent.
- Protect the server: depth and cost limits, pagination limits, timeouts, and persisted (allowlisted) operations for first-party clients where practical.
- Give each mutation its own input and payload types. Return expected business failures as typed results in the payload (for example a union of the success type and `EmailAlreadyUsed`), and keep the top-level `errors` array for unexpected faults.
- Check authorization in the business layer for each object a resolver returns, not only at the gateway.

## gRPC and protobuf specifics

- Never reuse or renumber a field number. When removing a field, list its number and name under `reserved`.
- Adding fields is compatible; changing a field's type or number is not, unless the protobuf language guide lists the change as wire-compatible and every consumer has been checked.
- Enums start with `<NAME>_UNSPECIFIED = 0`; clients handle unknown values.
- Set a deadline on every call and propagate it. Use the canonical status codes (`INVALID_ARGUMENT`, `NOT_FOUND`, `ALREADY_EXISTS`, `FAILED_PRECONDITION`, `PERMISSION_DENIED`, `UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`). `UNAVAILABLE` is the usual retryable code, and only for idempotent calls or calls carrying an idempotency key.
- Run a breaking-change check in CI, for example `buf breaking --against '.git#branch=main'`.

## Events, webhooks and messages

- Each payload carries an event ID, event type, schema version, occurred-at timestamp and the ID of the entity it describes.
- Consumers deduplicate by event ID. Delivery is at least once; order is not guaranteed unless the broker guarantees per-key ordering and you publish with that key.
- Outgoing webhooks: sign the raw body with HMAC-SHA256 over a timestamp plus the body, reject old timestamps to prevent replay, retry non-2xx deliveries with backoff, and let receivers see delivery history. Verifying incoming webhooks is covered by LaunchGuard.
- Schema evolution follows the API rules: add optional fields, never change meaning in place, publish a new event type or version for a breaking change.

## In-process interfaces

The same thinking applies to modules, packages, components and classes.

- Aim for a small interface with substantial behavior behind it. Callers should learn a few functions or props and get real work done; a wrapper whose interface mirrors its implementation adds a layer without hiding anything.
- Hide storage, transport and vendor SDK types behind your own types, so replacing a vendor is a change in one place.
- Pass dependencies in (parameters or constructor arguments) instead of constructing them inside, and return results instead of mutating arguments. Both make the interface testable without patching internals.
- Introduce an abstraction for a dependency only when there are at least two real implementations, such as the production adapter and an in-memory test version.
- Validate where untrusted data enters (HTTP handlers, queue consumers, file and CLI parsers, environment variables, third-party responses); code behind that boundary works with parsed, typed values. See `typescript.md`.
- Before committing to an interface that will be expensive to change, sketch two genuinely different designs with a short usage example each, compare them on how much callers must know, and choose deliberately.

## Contract-first workflow

1. Update the schema with an example request and response, including at least one error, before writing the handler.
2. Generate or derive types from the source of truth; never maintain two hand-written copies.
3. Validate requests at runtime against the schema with the project's validator.
4. Add or run a breaking-change check in CI if the toolchain has one (for example `oasdiff breaking`, `buf breaking`, `graphql-inspector diff`).
5. For important consumers, add contract tests (consumer-driven contracts or schema-based tests) so a provider change that breaks them fails before release.

## Checks (done when)

- [ ] Schema and implementation agree: generated types compile, or tests validate responses against the schema.
- [ ] Every change is classified compatible or breaking; each breaking change has a version or deprecation plan the user approved.
- [ ] Every list endpoint has a default and maximum page size and a deterministic order.
- [ ] Every non-idempotent create or charge honors an idempotency key, tested with a repeated request and with a same-key, different-body request, or is documented as unsafe to retry.
- [ ] Errors use the single documented shape; tests cover at least one validation error and one not-found.
- [ ] Error bodies contain no internal details (test or inspection).
- [ ] Object-level authorization is enforced server-side (LaunchGuard #6 and #7).

## Anti-patterns

- Different error shapes per endpoint; clients matching on message text.
- Unbounded lists; offset pagination over a large, busy table; ordering by a non-unique column.
- An idempotency guard that reads first and inserts later; keys generated per attempt.
- Renaming a field because it "looks internal" without searching for consumers.
- Exposing ORM entities or database column names directly as the public contract.
- A boolean that clearly wants to be a status (`isActive`, then `isSuspended`, then `isPending`).
- A new major version for every small change, or never deprecating anything.
