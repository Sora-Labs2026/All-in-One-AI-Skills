# Realtime: WebSockets, Server-Sent Events and live updates

Read this when you build or change server push, chat, presence, live dashboards, collaborative editing, notifications, streamed responses or multiplayer web features. GraphQL subscriptions add the rules in `graphql.md`; game networking is in `game-development.md`; the user-facing connection states follow `../../interaction-feedback.md`.

## Choose the transport

| Transport | Direction | Fits | Watch for |
|---|---|---|---|
| Polling | Client pulls | Updates every 30 s or slower, simple infrastructure | Wasted requests; latency equals the interval |
| Server-Sent Events (`EventSource`) | Server to client over HTTP | Notifications, feeds, progress, streamed AI output | Text only; automatic reconnect with `Last-Event-ID`; browsers allow about 6 connections per origin over HTTP/1.1, so serve it over HTTP/2 |
| WebSocket (RFC 6455) | Both ways, one long connection | Chat, collaboration, live trading views, browser games | Stateful servers, proxies and load balancers to configure, your own reconnect and resume logic |
| WebRTC | Peer to peer, media and data channels | Calls, screen sharing, low-latency peer data | Signaling server, STUN and TURN for NAT traversal |
| WebTransport (HTTP/3) | Both ways, reliable streams and unreliable datagrams | Latency-sensitive data where loss is acceptable | Browser support is incomplete; check targets |

Choose SSE when the client only needs to receive; it works through ordinary HTTP infrastructure and reconnects by itself. Choose WebSockets when the client sends frequent messages over the same channel. A managed realtime service is often cheaper than running a fleet of socket servers; compare before building.

## Libraries

- Node.js: `ws` (plain WebSocket), uWebSockets.js (high connection counts), Socket.IO (its own protocol over WebSocket with HTTP long-polling fallback, rooms and acknowledgements; both ends must use Socket.IO).
- Framework gateways: NestJS gateways, Django Channels, Phoenix Channels, Rails Action Cable, Starlette and FastAPI websockets, Go `coder/websocket` or `gorilla/websocket`.
- Collaborative editing: use a CRDT library (Yjs, Automerge) or an operational-transform service. Do not hand-roll merge logic.

## Protocol facts that matter in code

- The connection starts as an HTTP `Upgrade` request: cookies, headers and the `Origin` arrive there, and that is where authentication belongs.
- TCP can stay "open" after the peer vanished (sleeping laptop, dropped mobile network). Send pings from the server on an interval and terminate connections that miss a pong.
- Close codes: 1000 normal, 1001 going away (server shutdown, page navigation), 1008 policy violation, 1009 message too big, 1011 server error, 1012 service restart, 1013 try again later; 4000 to 4999 are yours (for example 4401 for an expired session). 1006 is never sent; it means the connection dropped.
- Set a maximum message size; library defaults are often far larger than any legitimate message.
- `permessage-deflate` compression costs memory and CPU per connection. Enable it only if measurements show bandwidth matters more.

## Message design

- Wrap every message in an envelope: `type`, a message `id`, a per-channel sequence number `seq` where order matters, and a schema `version`.
- Validate every inbound message against a schema and reject unknown types. A socket is an API endpoint without HTTP's middleware.
- Make handlers idempotent: deduplicate by message id, because clients resend after reconnects.
- For state that matters, use snapshot plus deltas: on (re)connect the client receives the current state (or fetches it over HTTP), then applies deltas in `seq` order. If it detects a gap, it requests a fresh snapshot. Resuming from the last `seq` needs a durable log (Redis Streams, Kafka, NATS JetStream or a database table), not plain pub/sub.
- Acknowledge messages whose loss the user would notice (a sent chat message); fire-and-forget is fine for cursor positions and typing indicators.

## Server sketch (Node.js, `ws`)

```js
import { WebSocketServer } from "ws";

const wss = new WebSocketServer({ noServer: true, maxPayload: 64 * 1024 });
const ALLOWED_ORIGINS = new Set(["https://app.example.com"]);

httpServer.on("upgrade", async (req, socket, head) => {
  // Cookie sessions: a cross-site page can open a socket with the user's cookies,
  // so check Origin (cross-site WebSocket hijacking).
  if (!ALLOWED_ORIGINS.has(req.headers.origin ?? "")) return reject(socket, 403);
  const user = await sessionFromCookie(req.headers.cookie);
  if (!user) return reject(socket, 401);
  wss.handleUpgrade(req, socket, head, (ws) => wss.emit("connection", ws, req, user));
});

wss.on("connection", (ws, _req, user) => {
  ws.isAlive = true;
  ws.on("pong", () => { ws.isAlive = true; });
  ws.on("message", async (raw) => {
    const msg = parseEnvelope(raw);                   // schema validation; null if invalid
    if (!msg) return ws.close(1008, "invalid message");
    if (!rateLimiter.allow(user.id)) return ws.close(1008, "rate limited");
    if (msg.type === "subscribe" && !(await canRead(user, msg.channel))) {
      return send(ws, { type: "error", code: "FORBIDDEN", ref: msg.id });
    }
    await handle(user, ws, msg);
  });
});

// Heartbeat: drop connections that did not answer the previous ping.
setInterval(() => {
  for (const ws of wss.clients) {
    if (!ws.isAlive) { ws.terminate(); continue; }
    ws.isAlive = false;
    ws.ping();
  }
}, 30_000).unref();

function send(ws, payload) {
  if (ws.bufferedAmount > 1_000_000) return ws.close(1013, "slow consumer"); // backpressure
  ws.send(JSON.stringify(payload));
}

function reject(socket, status) {               // refuse the upgrade with a plain HTTP response
  socket.write(`HTTP/1.1 ${status} ${status === 401 ? "Unauthorized" : "Forbidden"}\r\n\r\n`);
  socket.destroy();
}
```

`sessionFromCookie`, `parseEnvelope`, `rateLimiter`, `canRead` and `handle` stand for the project's own session, schema, rate-limit and authorization code.

## Client behavior

- Reconnect with capped exponential backoff and full jitter, and reset the backoff only after the connection has been stable for a while. Without jitter, a server restart causes every client to reconnect at the same instant.
- After reconnecting, re-authenticate, resubscribe, and resynchronize state (snapshot or resume from the last `seq`) before showing live data as current.
- Stop retrying on authentication failures (your 44xx codes): refresh the session or send the user to sign in.
- Queue outgoing messages while disconnected only when resending is safe (they carry ids for deduplication), bound the queue, and show the user what is pending.
- Show connection state honestly ("Reconnecting", "Offline, changes will sync") per `../../interaction-feedback.md`.
- Pause non-essential streams while the tab is hidden; browsers throttle background timers anyway.

```js
function connect(url, { onOpen, onMessage }, attempt = 0) {
  const ws = new WebSocket(url);
  let stableTimer;
  ws.onopen = () => { stableTimer = setTimeout(() => (attempt = 0), 10_000); onOpen(ws); };
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onclose = (e) => {
    clearTimeout(stableTimer);
    if (e.code >= 4400 && e.code < 4500) return handleAuthFailure(e.code); // do not retry
    const delay = Math.random() * Math.min(30_000, 500 * 2 ** attempt);  // full jitter, 30 s cap
    setTimeout(() => connect(url, { onOpen, onMessage }, attempt + 1), delay);
  };
}
```

## Security

- **Authenticate at the upgrade.** With cookies, check `Origin` against an allowlist. With tokens, prefer a short-lived ticket obtained over authenticated HTTP and sent in the first message; tokens in query strings end up in proxy and server logs.
- **Authorize every subscription and every message,** not only the connection. Joining a room or channel is an access decision against the record it represents.
- **Sessions expire while sockets stay open.** Re-check at an interval or on token expiry, and close with your auth code when access ends (sign-out, role removal, account deletion).
- Rate-limit messages per connection and per user; cap connections per user and per IP.
- Escape message content where it is rendered (chat is a classic stored-XSS path).
- `wss://` only. Log connection and authorization events with user and connection ids, without message bodies containing personal data.

## Scaling and operations

- **Fan-out across instances:** a user connected to instance A must receive events produced on instance B. Publish through a broker (Redis pub/sub for at-most-once, Streams, NATS or Kafka for durable delivery). The Socket.IO Redis adapter does this for Socket.IO.
- **Sticky sessions** are required for Socket.IO's long-polling fallback, and for any protocol that keeps per-connection state across HTTP requests. Plain WebSockets do not need them once connected.
- **Proxies and load balancers:** forward `Upgrade` and `Connection` headers (nginx: `proxy_http_version 1.1`, `proxy_set_header Upgrade $http_upgrade`, `proxy_set_header Connection "upgrade"`), and set idle timeouts above the heartbeat interval. Many cloud load balancers close idle connections after about 60 seconds by default.
- **Capacity:** each connection holds a file descriptor and memory. Raise `ulimit -n`, measure memory per connection under realistic subscriptions, and scale on connection count and event-loop lag as well as CPU.
- **Deploys:** on shutdown stop accepting upgrades, close existing sockets with 1001 or 1012, and let clients reconnect with jitter to other instances. Roll instances gradually so the reconnect wave is spread out.
- **Presence:** track it with heartbeats and expiring keys; disconnect events are lost when an instance crashes.
- **Slow consumers:** watch `bufferedAmount`; coalesce updates where only the latest value matters (prices, positions) and disconnect consumers that stay behind.
- **Metrics:** open connections, connects and disconnects per second by close code, inbound and outbound message rates, send-buffer sizes, fan-out latency, authorization failures (`../../engineering-practices/references/observability.md`).

## Testing

- Unit-test message handlers as plain functions with parsed envelopes.
- Integration-test with a real client (`ws` in Node.js tests, Playwright for browser flows): authentication rejection, forbidden subscription, invalid message, reconnect and resync, duplicate message ids.
- Simulate failure: kill the server mid-session, drop the network, throttle the client, restart all instances at once and watch the reconnect curve.
- Load tests (k6 or Artillery WebSocket support) run only against your own staging environment, with permission.

## Done when

- [ ] The transport choice is written down with its reason (SSE versus WebSocket versus a managed service).
- [ ] Authentication happens at the upgrade; every subscription and message is authorized; `Origin` is checked with cookie auth.
- [ ] Inbound messages are schema-validated and size-limited; handlers deduplicate by id.
- [ ] Heartbeats, backpressure handling and graceful shutdown exist and were exercised in a test.
- [ ] Clients reconnect with jittered backoff, resynchronize state and show connection status.
