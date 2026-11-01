# RPC, message queues, webhooks and WebSockets

Read this when services talk to each other or to clients without plain request-response HTTP: gRPC or Thrift, GraphQL over HTTP or WebSockets, brokers and queues (Kafka, RabbitMQ, SQS, Google Pub/Sub, NATS, MQTT, Redis streams), event buses, inbound webhooks and push subscriptions, WebSocket and server-sent event channels. Entry points for these are listed in [entry points and context](entry-points-and-context.md#1-ask-the-framework-for-its-route-table). Outbound webhooks are an SSRF surface ([vulnerability classes](vulnerability-classes.md#4-server-side-request-forgery)). Volume and poison-message effects are in [availability](availability-and-resource-limits.md).

## Map every hop first

For each message family, draw producer, transport, gateway, consumer and store. Fill in one row per hop:

| Hop | Peer identity established by | Fields treated as principal, tenant or resource | Validation | Side effect | Delivery guarantee |
|---|---|---|---|---|---|
| `billing-api -> orders.paid topic` | Broker credentials of billing-api | `tenantId`, `orderId` in the body | Schema only | none | at least once |
| `orders.paid -> fulfillment worker` | Consumer group ACL | same | none | ships goods | at least once, no ordering |

Two rules come out of almost every map:

- **"Internal" is a network location, not an identity.** A message is as trustworthy as the least trusted producer allowed to write to its topic, queue or endpoint. If a less trusted service, a tenant-controlled integration or a public webhook relay can publish there, body fields like `tenantId`, `userId`, `role` or `type: "admin.grant"` are attacker input.
- **Schema validation proves shape, not provenance or authority.** A well-formed message can still name another tenant's resource. The consumer must tie the resource to an identity it can trust: the authenticated producer for system events, or a re-check of current permissions for user-initiated work.

## gRPC and other RPC frameworks

- **Interceptor coverage.** In Go, `grpc.UnaryInterceptor` or `ChainUnaryInterceptor` does not cover streaming methods. Those need `StreamInterceptor` or `ChainStreamInterceptor`. In Java, an interceptor attached to one service through `ServerInterceptors.intercept` does not protect services registered without it. List every registered service and method, and show which authentication and authorization code runs for each.
- **Default deny for unknown methods.** Authorization maps keyed by the full method name (`/pkg.Service/Method`) must refuse names they do not list. A new method added without a map entry must fail closed.
- **Identity in metadata.** Values such as `x-user-id` or `x-tenant` in request metadata are client-supplied unless a trusted proxy sets them and strips incoming copies. With mutual TLS, the certificate identifies the calling service. The user that service acts for must come from a token the callee verifies, or from a deterministic mapping, not from a free-form field.
- **Extra doors.** A REST gateway (grpc-gateway, Envoy transcoding) adds HTTP paths to the same methods. Auth placed only on the HTTP side, or only on the gRPC side, leaves the other open. Server reflection and health services in production disclose the schema; that is usually a hardening note.
- **Streams.** Authorize each message that names a resource, not only the stream's opening. Long streams outlive the token that opened them: re-check on revocation or close the stream.
- **Limits.** The main gRPC implementations limit received messages to 4 MiB by default. Look for overrides that raise it far beyond need, and for missing deadlines on outgoing calls.
- **Protobuf semantics.** In proto3, an unset scalar reads as its zero value and an unset enum as its first value (number 0). If `0` means `ADMIN` or `ALLOW`, every message that omits the field grants it. Make the zero value `UNSPECIFIED` and treat it as the least privilege. Unknown fields are kept and forwarded by default, so a proxy can pass along fields it never validated. In the JSON mapping, 64-bit integers travel as strings, and JavaScript numbers lose precision above 2^53.

## GraphQL as a transport

Per-field authorization is in the entry-point guide. Transport-level issues to add:

- **Batching and aliases.** An array of operations in one request (where the server enables batching), or one field repeated under many aliases, multiplies work and attempts inside a single HTTP request. Per-request rate limits and lockouts then count one attempt where there were hundreds.
- **Subscriptions.** Authorize at subscribe time and again for each event, with the tenant filter on the event path (a `withFilter`-style predicate), and end subscriptions when membership is revoked.
- **Introspection and errors.** Introspection and detailed errors in production disclose schema and internals. That is usually hardening. Persisted or allowlisted queries remove the arbitrary-query surface entirely for first-party clients.

## Brokers and queues

| Check | What goes wrong |
|---|---|
| Who may publish to each topic or queue: Kafka ACLs, RabbitMQ vhost permissions, SQS queue policies, Pub/Sub IAM, NATS accounts | A lower-trust producer emits events that a consumer treats as control-plane instructions |
| Topic names built from input: `orders.${tenant}` | Wildcards (`*`, `#` in AMQP topic exchanges; `*`, `>` in NATS; `+`, `#` in MQTT) or separators in the tenant value subscribe to or publish into other tenants' topics |
| Authority carried in the message | The permission was checked when the message was queued; by processing time the member was removed or the token revoked. Re-check current authorization for consequential actions |
| Duplicate delivery | SQS standard queues, Pub/Sub by default, and Kafka consumers that crash before committing all deliver at least once. A payment, email, grant or ledger write without an idempotency key repeats. Deduplicate before the side effect, with a unique constraint on the key, scoped per tenant |
| Ordering | Ordering is not guaranteed across partitions, standard SQS queues, or Pub/Sub without ordering keys. A stale "role granted" arriving after "role revoked" re-grants. Compare versions or sequence numbers before applying state |
| Acknowledge and commit order | Committing an offset or acknowledging before the work is durable loses it on a crash. Committing work before the acknowledgment duplicates it. Use a transactional outbox or inbox for state changes that must happen exactly once |
| Dead-letter and error queues | Failed messages with personal data or secrets land where a wider operator group, or another tenant's tooling, can read them |
| Replay and backfill tools | Re-running old messages applies yesterday's authority and yesterday's data to today's state. Replays need the same checks as live traffic |
| Reply queues and correlation IDs | Predictable or shared reply queues let one caller receive or answer another's response. Bind each pending request to its caller and use unguessable IDs |

## Inbound webhooks and push subscriptions

[AIG-07](ai-generated-code-bugs.md#aig-07-unverified-webhooks) covers the basic signature checks. Beyond it:

- **Verify the raw bytes.** Verify the exact body bytes received, in constant time, before parsing. Then check a timestamp tolerance and deduplicate by event ID. The Standard Webhooks specification (`webhook-id`, `webhook-timestamp`, `webhook-signature`) is a good reference shape.
- **Multi-tenant receivers.** Pick the tenant from the endpoint (a per-tenant URL or ID), then verify with that tenant's secret. Never read the tenant from the unverified body to choose the secret. Never accept a signature that verifies under any tenant's secret.
- **Prefer a lookup to the payload.** Where the provider offers it, fetch the object (payment, subscription, repository event) by ID from the provider's API instead of trusting amounts or states in the body. Allowlist the event types you handle.
- **Cloud push subscriptions.** For Amazon SNS, use the SDK's message validator, which checks the signature and that the signing certificate URL is an SNS host over HTTPS. Fetching whatever URL the message names is SSRF. For Google Pub/Sub push with authentication, verify the OIDC token's signature, its `aud` against the audience you configured, and its `email` against the push service account. Other providers have equivalents: find the documented verification and check it runs before any side effect.
- **Process asynchronously.** Return success quickly and process idempotently, so a provider's retries do not repeat effects.

## WebSockets and server-sent events

- **Origin at upgrade.** The browser sends cookies with the upgrade request and does not apply the same-origin policy to WebSockets. A cookie-authenticated socket that does not check `Origin` against an exact allowlist lets any website act as the visitor (cross-site WebSocket hijacking). Alternatively, authenticate with a token the page must send explicitly.
- **Authorization per message.** Every message that names a channel, room, document or record needs an authorization check. Handlers that join whatever room name the client sends (a common Socket.IO pattern) let clients listen to other tenants. Check membership on join, and on broadcast where rooms mix tenants.
- **Lifetime.** Connections outlive sessions. Close them on logout, password change and membership removal, or re-validate periodically. A revoked user's open socket must stop receiving data.
- **Limits.** Set message size, rate and connection-count limits per user. The Node `ws` library accepts messages up to 100 MiB by default (`maxPayload`).

## Parser and schema disagreements

When two components decode the same bytes differently, a check in one does not protect the other. Look for:

- **Duplicate JSON keys.** Most parsers keep the last value, some the first, some reject the document. A gateway that validates `{"role":"user","role":"admin"}` one way and a service that reads it the other way see two different requests.
- **Case-insensitive field matching.** Go's `encoding/json` (v1) matches object keys to struct fields case-insensitively, so `"Role"` fills `role` while a validator in another language ignores it.
- **Other mismatches:** unknown fields forwarded by one hop and read by the next; large integers rounded in JavaScript; Unicode normalization or case folding applied by one side only; envelope versus body precedence (a routing header says tenant A, the body says tenant B).

A disagreement becomes a finding when you name both components, the divergent decoded value, and the security decision it changes.

## Confirm safely

Prefer in-process fakes and the framework's test servers: an in-memory gRPC server, a fake broker client, a recorded webhook with a test secret. Feed the same fixture to every consumer and schema version in the repository. Send duplicated, reordered, replayed, oversized and unknown-field messages, and assert the side effects. A local broker in a container needs the user's approval like any other service started for the audit. Never publish to a shared, staging or production broker, topic or webhook endpoint without explicit scope. Record broker ACLs, service-mesh identity and topic attachment that live outside the repository as `NOT_VERIFIED`, with the owner check that settles them.

## Done when

- Every message family has a hop map, with the producer identity and authoritative fields named at each hop.
- Every RPC service and method has its authentication and authorization code cited, including streams, gateways and reflection.
- Consumers of consequential messages have idempotency, ordering and current-authorization checks cited, or a finding.
- Webhook and push receivers verify raw bytes, timestamps, event IDs and per-tenant secrets before side effects.
- WebSocket upgrades check `Origin` or use an explicit token, and per-message authorization is cited.
- Broker-side facts the repository cannot show are listed for the owner.
