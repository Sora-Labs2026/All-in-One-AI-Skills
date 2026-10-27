# Reliability and testing for third-party APIs

Read this when code creates objects at a provider, hits rate limits, pages through lists, keeps a local copy in sync, upgrades an API version, or needs tests that do not depend on the live provider. Timeouts, retry classification, backoff with jitter, circuit breakers and the server side of idempotency keys are in `../../engineering-practices/references/resilience.md` and `../../engineering-practices/references/api-contracts.md`; this file covers being the *client* of someone else's API.

## Idempotency on outbound calls

- **Use the provider's idempotency key when it has one** (Stripe's `Idempotency-Key`, exposed as an SDK option). Derive the key from your own record and intent, for example `order_8412:charge`, so every retry of that intent sends the same key. A key minted per attempt protects nothing.
- **Same key, same parameters.** Providers reject or ignore a reused key with a different body. When the user genuinely changes the request, it is a new intent with a new key.
- **No idempotency support?** Write your intent row first (`pending`, with your reference), put the reference in the provider's metadata or external-ID field, and after a timeout *look it up* by that reference instead of creating again.
- **Recover stuck intents.** A scheduled job finds rows left in `pending` past a deadline, queries the provider by reference, and completes or fails them. The outcome after a timeout is unknown, not failed.

## Rate limits

- **Learn the shape** from the provider's docs: per key, per user, per project or per tenant; requests per second or per minute; cost or complexity points (common for GraphQL APIs); concurrent-request caps.
- **Read the signals.** `429` with `Retry-After` (seconds or an HTTP date), provider headers such as `X-RateLimit-Remaining` and `X-RateLimit-Reset`, or the IETF `RateLimit` headers. Some Google APIs answer `403` with reason `rateLimitExceeded` or `userRateLimitExceeded`; treat those as retryable.
- **Throttle before you are throttled.** When several workers share one key, use a shared token bucket (for example in Redis) sized below the limit, and give each tenant a fair share so one large account cannot starve the rest.
- **Spend fewer calls:** request only needed fields, use batch endpoints, cache with a TTL where the provider's terms allow it, use conditional requests (`ETag`, `If-None-Match`) where supported, and replace polling with webhooks or change feeds.

## Pagination

| Style | Iterate with | Stop when | Watch out for |
|---|---|---|---|
| Opaque page token or cursor (Google `pageToken`, Jira `nextPageToken`, Confluence v2 `_links.next`, Stripe `starting_after` with `has_more`) | The token from the previous response | No next token, or `has_more` is false | Tokens expire; changing filters between pages is undefined |
| GraphQL connections (Linear and most GraphQL APIs) | `first` and `after: endCursor` | `pageInfo.hasNextPage` is false | Page size caps; nested connections paginate separately |
| Offset and limit (Outline, older REST endpoints) | `offset += limit` | A short page | Inserts and deletes shift rows: order by a stable key and dedupe by ID |
| `Link` header (RFC 8288) | The `rel="next"` URL | No `next` link | Do not rebuild the URL yourself |

Prefer the SDK's auto-pagination helper when it exists (Stripe's auto-paging iterators, `list_next` in Google's Python client), but bound the total and guard against a provider returning the same cursor twice:

```ts
async function* paginate<T>(
  fetchPage: (cursor?: string) => Promise<{ items: T[]; next?: string | null }>,
  maxPages = 10_000,
): AsyncGenerator<T> {
  const seen = new Set<string>();
  let cursor: string | undefined;
  for (let page = 0; page < maxPages; page++) {
    const { items, next } = await fetchPage(cursor);
    yield* items;
    if (!next) return;
    if (seen.has(next)) throw new Error("Provider returned a repeated cursor");
    seen.add(next);
    cursor = next;
  }
  throw new Error(`Stopped after ${maxPages} pages`);
}
```

## Keeping a local copy in sync

1. **Initial sync:** page through everything, committing each page and its checkpoint together so the job can resume.
2. **Incremental sync:** use the provider's change mechanism (sync tokens, history IDs, change feeds, `updated_since` filters, webhooks). Save the new cursor only in the same transaction as the records it covers.
3. **Expired cursors:** Google returns `410 Gone` for an invalid sync token; Plaid asks you to restart a sync loop when data changes mid-pagination. Restart that resource from a full sync rather than guessing.
4. **Deletions:** use tombstones from the change feed; with full scans, mark records seen in this run and remove the rest only after a complete, successful pass.
5. **Time windows:** filter by the provider's timestamps, overlap each window slightly, and dedupe by ID.
6. **Reconcile on a schedule:** compare counts and checksums of key fields with the provider and repair through the normal code path.

## Errors and API versions

- **Map provider errors in the adapter** to a small set your code understands: `reconnect_needed`, `missing_scope`, `invalid_request`, `not_found`, `conflict`, `rate_limited`, `transient`, `unknown`. Keep the provider's request ID in logs for support tickets.
- **GraphQL reports failures inside a 200 response.** Check the `errors` array and any `success` flag in mutation payloads before treating a call as done.
- **Pin API versions** where the provider supports it (Stripe pins a dated version per client and per webhook endpoint). Upgrade on purpose: read the changelog, run the contract tests against the sandbox on the new version, then upgrade webhook endpoints separately.
- **Watch for retirement:** subscribe to the provider's changelog, log `Deprecation` and `Sunset` headers and warning fields, and record the replacement endpoint before the removal date.

## Testing without the live provider

| Layer | What it proves | Tools |
|---|---|---|
| Unit tests with a fake adapter | Business logic: entitlements, sync decisions, error handling | An in-memory implementation of your adapter interface |
| Adapter tests with mocked HTTP | Requests are built correctly; responses and errors are parsed | `responses` or `respx` (Python), `nock` or MSW (Node), recorded cassettes (vcrpy, Polly.js) |
| Contract tests | Recorded or sandbox responses still match the provider's published schema | The provider's OpenAPI or discovery documents with a schema validator |
| Sandbox smoke tests | The real API accepts your calls in test mode | A few scripted flows run on demand or nightly with test credentials from the CI secret store |
| Failure injection | Timeouts, 429, 5xx, malformed and partial pages are survived | The mocked transport or a local fault-injecting proxy |

- Mock at your adapter boundary, not deep inside business code.
- Scrub tokens, cookies and personal data from recorded cassettes before committing them, and re-record on a schedule so they do not drift from reality.
- Do not run sandbox tests on pull requests from forks; they would expose CI secrets.
- Freeze time in tests that involve token expiry, webhook timestamps or sync windows.

## Observability

- Log each call with provider, operation, status, latency, retry count and provider request ID. Never log tokens, full bodies or personal data.
- Track error rate by class, 429 rate, webhook lag (event created to processed), sync cursor age and the number of connections in `reconnect_needed`.
- Alert on sustained webhook failures, growing sync lag and spikes in reconnect states; each alert links to a runbook.

## Done when

- [ ] Every create that moves money or makes a user-visible object is idempotent, tested with a repeated call and with a timeout followed by a retry.
- [ ] Rate-limit responses are honored, and a shared throttle exists when workers share a key.
- [ ] Pagination reaches the last page in a test with at least three pages and stops on a repeated cursor.
- [ ] Incremental sync saves cursors atomically with data and recovers from an expired cursor (tested).
- [ ] The adapter has a fake for unit tests; recorded fixtures are scrubbed; sandbox smoke tests are documented and run only with the owner's test credentials.
