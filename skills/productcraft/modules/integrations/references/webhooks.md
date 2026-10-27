# Receiving webhooks

Read this when your code receives event callbacks from a provider: payment events, bank-data updates, issue or page changes, membership changes, chain activity from an RPC provider. Sending webhooks from your own API is covered in `../../engineering-practices/references/api-contracts.md`.

Treat a webhook as an unauthenticated HTTP request that *claims* something happened. It becomes trustworthy only after its signature is verified, and even then it may be late, repeated or out of order.

## The handler in five steps

1. **Read the raw body bytes** before any JSON parsing. Providers sign the exact bytes they sent; re-serialized JSON differs in whitespace, key order and number formatting.
2. **Verify signature and timestamp** with the provider's SDK helper when one exists, otherwise with the code below. Compare in constant time. Reject with 400 or 401 and a generic message.
3. **Deduplicate by event ID.** Insert the ID under a unique constraint; if the insert affects zero rows, it is a duplicate: return 2xx and stop.
4. **Record or enqueue, then acknowledge.** Return 2xx within a few seconds; providers time out quickly and retry.
5. **Process idempotently in a worker.** Re-fetch the object from the API when the decision matters (money, access, deletion), and apply a guarded state transition.

Where frameworks hide the raw body:

| Framework | Raw body |
|---|---|
| Express | `express.raw({ type: "application/json" })` on the webhook route, registered before any global `express.json()` |
| Next.js route handler | `await request.text()` (do not call `request.json()` first) |
| FastAPI / Starlette | `await request.body()` |
| Flask | `request.get_data()` |
| Django | `request.body`, with the view exempt from CSRF |
| Rails | `request.raw_post` |
| Go `net/http` | `io.ReadAll(http.MaxBytesReader(w, r.Body, limit))` |

API gateways, middleware that decompresses or re-encodes JSON, and serverless adapters can also change the bytes. If verification fails only in one environment, compare the received byte length with the provider's delivery log.

## Signature schemes you will meet

| Scheme | What arrives | What is signed | Examples |
|---|---|---|---|
| HMAC of the body | One header with a hex or base64 digest, sometimes prefixed `sha256=` | The raw body | Linear, many membership and SaaS platforms, Jira webhooks configured with a secret |
| Timestamped HMAC | A header such as `t=<unix>,v1=<hex>` | `"<t>.<raw body>"`, so the timestamp is covered | Stripe (`Stripe-Signature`; several `v1` values during secret rotation) |
| Standard Webhooks | `webhook-id`, `webhook-timestamp`, `webhook-signature: v1,<base64>` | `"<id>.<timestamp>.<raw body>"` with a base64 secret | Providers that adopt the open Standard Webhooks specification |
| Signed JWT | A header carrying a JWT whose claims include a hash of the body | The body hash inside a token signed with the provider's key | Plaid (`Plaid-Verification`, ES256, key fetched by key ID) |
| Google-signed bearer token | `Authorization: Bearer <ID token>` | The request's audience and issuer | Google Chat app endpoints, Pub/Sub push subscriptions |
| Static shared token | A fixed header or URL token | Nothing | Weak: compare in constant time, use the provider's published IP ranges if any, and always re-fetch data |

Each provider's details (header names, encoding, tolerance) differ and change. Use the provider's library or follow its current documentation exactly.

## Provider-neutral verification

```ts
import { createHmac, timingSafeEqual } from "node:crypto";

export function verifyTimestampedHmac(
  rawBody: Buffer, signatureHex: string, timestamp: string, secret: string, toleranceSec = 300,
): boolean {
  const ts = Number(timestamp);
  if (!Number.isInteger(ts) || Math.abs(Date.now() / 1000 - ts) > toleranceSec) return false;
  const expected = createHmac("sha256", secret).update(`${timestamp}.`).update(rawBody).digest();
  const given = Buffer.from(signatureHex, "hex");
  return given.length === expected.length && timingSafeEqual(given, expected);
}
```

```python
import hashlib, hmac, time

def verify_timestamped_hmac(raw_body: bytes, signature_hex: str, timestamp: str,
                            secret: bytes, tolerance: int = 300) -> bool:
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > tolerance:
        return False
    expected = hmac.new(secret, timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), signature_hex.strip().lower().encode())
```

`timingSafeEqual` throws on different lengths, hence the length check; comparing bytes in Python avoids the `TypeError` that `compare_digest` raises for non-ASCII strings. Other languages: Go `hmac.Equal`, Ruby `ActiveSupport::SecurityUtils.secure_compare` or `Rack::Utils.secure_compare`, PHP `hash_equals`, Java `MessageDigest.isEqual`, .NET `CryptographicOperations.FixedTimeEquals`.

## Deduplication, ordering and state

- Keep a table such as `webhook_events(provider, event_id, type, received_at, processed_at, status)` with a unique key on `(provider, event_id)`, and insert with `ON CONFLICT DO NOTHING` (or the database's equivalent). A read-then-insert check races under concurrent retries.
- Keep event IDs longer than the provider's retry window. Stripe, for example, retries live-mode deliveries for up to three days.
- Deduplicating deliveries is not enough when the provider can emit two *different* events for one business fact. Make the effect idempotent too: a unique constraint on `(order_id, grant_type)`, an upsert of the subscription row, a state transition that is a no-op when already applied.
- Order is not guaranteed. A cancellation can arrive before the update it follows. Either re-fetch the object and apply its current state, or compare the object's version or timestamp with what you stored and ignore older ones.
- Treat payloads as hints. Some providers send only IDs ("thin" events) and expect you to fetch. Even with full snapshots, re-fetch before granting access, moving money or deleting data, and confirm the object belongs to the customer or tenant you are about to change (LaunchGuard's payment playbook).

## Responding

- Return 2xx only after the event is durably recorded or enqueued. Return 5xx when you could not record it, so the provider retries.
- Return 2xx for event types you do not handle; log them at debug level. Repeated failures make providers disable the endpoint.
- Do slow work (emails, other API calls, fulfillment) in the worker, not in the request.
- Limit body size, require the expected content type, and exempt the route from CSRF and session middleware without exempting it from verification.

## Secrets, endpoints and environments

- Every endpoint has its own signing secret, and test and live modes have different ones. A secret that verifies in test mode will fail in live mode; that is a configuration step for the owner, not a bug to code around.
- Support two secrets during rotation and remove the old one after the provider stops using it.
- An unguessable URL is not authentication. Verify anyway.

## Missed events and reconciliation

- Monitor delivery failures in the provider's dashboard and alert on your handler's 4xx and 5xx rates.
- Backfill from the provider's event list (where offered) or by listing objects changed since your last cursor.
- Run a scheduled reconciliation that compares your records (subscriptions, payments, memberships, synced issues) with the provider's and repairs differences through the same idempotent code path.

## Local development and tests

- Use the provider's CLI to forward and trigger test events where one exists (for example Stripe's `stripe listen --forward-to` and `stripe trigger`). A public tunnel exposes the developer's machine; it is the user's decision to run one.
- Unit tests sign fixture payloads with a secret generated at runtime and cover: valid delivery processed; tampered body rejected; stale timestamp rejected; the same event twice produces one effect; an unknown type returns 2xx; a worker failure is retried without a duplicate effect.

```python
import hashlib, hmac, os, time

def signed_headers(body: bytes, secret: bytes) -> dict:
    ts = str(int(time.time()))
    sig = hmac.new(secret, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"X-Webhook-Timestamp": ts, "X-Webhook-Signature": sig}

TEST_SECRET = os.urandom(32)   # never a real secret in fixtures
```

## Pitfalls

| Pitfall | Fix |
|---|---|
| A global JSON parser runs first, verification "never works", and someone disables it | Raw body on the webhook route; never ship with verification off |
| Digest compared with `==` | Constant-time comparison after a length check |
| No timestamp check | Reject outside the tolerance; dedupe IDs as the second line of defense |
| Fulfillment only on the browser's success redirect | Fulfill from the webhook and, idempotently, on the redirect |
| 500 for unknown event types | 2xx and ignore |
| Trusting the payload's customer, amount or plan | Re-fetch and check ownership against your records |

## Done when

- [ ] Verification runs on the raw body with constant-time comparison and a timestamp tolerance, using the provider's helper where one exists.
- [ ] Duplicate and out-of-order deliveries are tested and produce one correct effect.
- [ ] The handler acknowledges quickly and slow work runs in a retried worker.
- [ ] Unknown events return 2xx; invalid signatures return 4xx without details.
- [ ] Separate secrets per endpoint and environment are configured by the owner; rotation is documented.
- [ ] A backfill or reconciliation path exists for missed events.
