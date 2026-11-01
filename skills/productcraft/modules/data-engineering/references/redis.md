# Redis and compatible key-value stores

Read this when you add or review a cache, session store, rate limiter, distributed lock, leaderboard, counter or queue built on Redis or a compatible server (Valkey, managed services), or when such a server runs out of memory, slows down or loses data. General caching rules (what to cache, keys that include every input, HTTP caching) are in `../../engineering-practices/references/performance.md`; this file adds what is specific to Redis.

## Versions and licensing

- Redis moved from the BSD license to a dual source-available license (RSALv2 or SSPLv1) with 7.4 in 2024, and added AGPLv3 as a third option with Redis 8 in 2025. Valkey is a BSD-licensed fork started in 2024 under the Linux Foundation; cloud providers offer managed Redis- and Valkey-compatible services. If the user offers a product that runs or embeds the server for others, the license choice matters; flag it and let them decide.
- Redis 8 bundles JSON, search, time-series and probabilistic types that used to be separate modules; Valkey and managed services differ in which of these they offer. Read `INFO server` (version and mode) before relying on a command. Version-dependent commands used below: `EXPIRE ... NX` (7.0), `XAUTOCLAIM` (6.2), hash-field expiry `HEXPIRE` (7.4), ACLs and TLS (6.0).

## When it fits

Use it for data that is derived, short-lived or cheap to rebuild: caches, sessions, rate limits, counters, leaderboards, deduplication sets, short coordination, and work queues with Streams. Do not make it the only copy of data the business cannot lose unless persistence, replication, backups and restore tests are agreed with the owner. It is a poor fit for large blobs (store them in object storage and cache a reference) and for ad hoc queries across many keys.

## Pick the structure

| Need | Structure | Notes |
|---|---|---|
| Cached object, counter, flag | String | `INCR`, `SET ... EX`, `GETEX` |
| Object with fields updated separately | Hash | Small hashes are stored compactly; `HEXPIRE` for per-field TTL on 7.4+ |
| Unique members, membership tests | Set | `SADD` returns whether the member was new: cheap deduplication |
| Ranking, time-ordered index, sliding windows | Sorted set | Score is a float; ties order by member |
| Durable queue with acknowledgements | Stream with consumer groups | Prefer over lists and pub/sub when work must not be lost |
| Fire-and-forget fan-out | Pub/sub | At most once: disconnected subscribers miss messages |
| Approximate distinct count | HyperLogLog | About 0.81% standard error in at most 12 KB |
| Per-day boolean flags for many ids | Bitmap | Ids must be dense integers |

## Key design

- Namespaced, predictable names: `app:v2:user:42:profile`. A version segment lets a schema change start with fresh keys instead of reading old shapes.
- A TTL on every derived key. Keys without a TTL accumulate until memory runs out.
- No unbounded keys: a hash, set or list that grows with traffic becomes a "big key" whose reads and deletes block the server. Find them with `redis-cli --bigkeys` and `--memkeys`, delete them with `UNLINK` (non-blocking), and shard them by time or id.
- Hot keys (one key read or written by most requests) cap throughput on one shard: replicate the value under several keys or cache it in-process for a second.
- In Redis Cluster, multi-key commands, transactions and scripts need all keys in one hash slot; group them with a hash tag, for example `{user:42}:cart` and `{user:42}:profile`. Scripts must pass every key in `KEYS`.

## Caching with Redis

- **Cache-aside, delete on write:** read the cache, on a miss load from the database and set with a TTL; on a write, commit to the database first, then delete the key. Deleting is safer than writing the new value into the cache, which can race with a reader that loaded the old value. A short TTL bounds the damage of the remaining race.
- **Jitter TTLs** so keys written together do not expire together.
- **Stampede protection:** when a hot key expires, let one caller rebuild it while the rest serve the stale value.

```python
import json, random, time
import redis

r = redis.Redis(host="localhost", port=6379, socket_timeout=0.5, decode_responses=True)

def get_or_refresh(key, load, fresh_s=300, keep_s=3600):
    raw = r.get(key)
    if raw is not None:
        entry = json.loads(raw)
        if time.time() < entry["fresh_until"]:
            return entry["value"]
        if not r.set(f"refresh:{key}", "1", nx=True, ex=30):   # someone else is refreshing
            return entry["value"]                               # serve stale meanwhile
    value = load()                                              # cold miss or this caller refreshes
    entry = {"value": value, "fresh_until": time.time() + fresh_s * random.uniform(0.9, 1.1)}
    r.set(key, json.dumps(entry), ex=keep_s)
    return value
```

- Cache "not found" briefly; never cache errors or partial results.
- If Redis is down, the application should fall back to the database with tight timeouts, not fail every request.

## Memory and eviction

- Set `maxmemory` and choose `maxmemory-policy` deliberately. The default `noeviction` rejects writes when memory is full.
- `allkeys-lru` or `allkeys-lfu` suit a pure cache. The `volatile-*` policies evict only keys that have a TTL; if none do, they behave like `noeviction`.
- Eviction policy is per instance, so keep the cache and data that must not be evicted (queues, sessions, locks) on separate instances or databases with different policies.
- Watch `INFO memory` (`used_memory`, `mem_fragmentation_ratio`) and `INFO stats` (`evicted_keys`, `keyspace_hits`, `keyspace_misses`).

## Persistence and durability

- RDB snapshots fork the process; on write-heavy servers copy-on-write can need up to twice the memory during the snapshot.
- AOF with `appendfsync everysec` can lose about a second of writes on a crash; `always` is safer and much slower.
- Replication is asynchronous: a write acknowledged by the primary can vanish when a replica is promoted. `WAIT` narrows the window but does not make Redis strongly consistent.
- Back up snapshot files off the host and test a restore before calling the data protected.

## Locks done right

A Redis lock is fine for efficiency (avoiding duplicate work). It is not safe on its own for correctness (preventing double payment), because a process can pause (garbage collection, a stalled VM) past the lock's TTL and keep writing after another holder took over.

```python
import secrets

RELEASE = r.register_script(
    "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0")

def acquire(name, ttl_ms):
    token = secrets.token_hex(16)
    return token if r.set(f"lock:{name}", token, nx=True, px=ttl_ms) else None

def release(name, token):
    return RELEASE(keys=[f"lock:{name}"], args=[token]) == 1
```

- A random token per holder, and release only through the compare-and-delete script; a plain `DEL` can remove someone else's lock.
- TTL longer than the longest expected hold, renewed by the holder for long work, and work aborted when renewal fails.
- For correctness, add a **fencing token**: an increasing number (`INCR lock:name:fence`) issued with the lock, which the protected resource checks and rejects when older than the last one it saw. Or use the database itself: a unique constraint, `SELECT ... FOR UPDATE`, or an advisory lock. Multi-node lock algorithms do not remove the need for fencing.

## Rate limiting

```python
def allow(user_id, limit=100, window_s=60):
    key = f"rl:{user_id}:{int(time.time() // window_s)}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_s, nx=True)       # set the TTL once (Redis 7.0+)
    count, _ = pipe.execute()
    return count <= limit
```

Fixed windows allow up to twice the limit across a window boundary. For smoother limits use a token bucket or a sorted-set sliding log in a Lua script, and take the time from one clock (the server's `TIME` inside the script, or a single application clock) to avoid skew between app servers. Account-aware abuse controls belong in `../../credential-shield/GUIDE.md`.

## Streams as a work queue

- Producers `XADD stream MAXLEN ~ 1000000 * field value`; the approximate trim keeps memory bounded.
- Consumers in a group read with `XREADGROUP ... >`, process, then `XACK`. Unacknowledged messages stay in the pending list; reclaim them from dead consumers with `XAUTOCLAIM` after an idle time.
- Delivery is at least once: make handlers idempotent (deduplicate by message id or business key).
- Move a message that keeps failing (its delivery count in `XPENDING`) to a dead-letter stream and alert, instead of retrying forever.

## Clients and operations

- One connection pool per process, with connect and read timeouts. Retry only idempotent commands, with backoff.
- Pipeline batches of commands to save round trips; keep blocking commands (`BLPOP`, `XREAD BLOCK`) on their own connections.
- Diagnostics that are safe on a live server: `INFO`, `SLOWLOG GET 20`, `LATENCY DOCTOR`, `CLIENT LIST`, `MEMORY USAGE key`, `SCAN 0 MATCH prefix:* COUNT 1000`.
- Never on shared or production servers without the user's go-ahead: `KEYS *` (blocks the server), `FLUSHALL` and `FLUSHDB`, `DEBUG`, `CONFIG SET`, and `MONITOR` (heavy, and prints every value including secrets and personal data).

## Security

- Bind to private interfaces only; never expose the port to the internet. Keep protected mode on.
- ACL users per application with only the command categories they need (for example `-@dangerous`), TLS between hosts, and passwords from a secret store by name.
- Patch promptly. Lua scripting has had critical flaws (for example CVE-2025-49844, disclosed in October 2025); restrict `EVAL` and `FUNCTION` to trusted users.
- Values often hold session tokens and personal data: treat dumps and backups as sensitive.

## Checks (done when)

- [ ] Server, version and license noted; the data's durability needs agreed and matched by persistence and replication settings.
- [ ] Every derived key has a TTL; no unbounded keys; cache keys include every input that changes the value.
- [ ] `maxmemory` and the eviction policy suit what the instance stores.
- [ ] Locks use tokens and safe release, and correctness-critical paths have fencing or a database guarantee.
- [ ] Stream consumers acknowledge, reclaim and dead-letter; handlers are idempotent.
- [ ] No blocking or destructive command ran on a shared server without permission.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Writes fail with OOM errors | `noeviction`, or `volatile-*` with no TTLs | Right policy per instance; TTLs |
| Latency spikes every few minutes | Snapshot fork on a large instance, big-key deletes, `KEYS` | Schedule or tune persistence; `UNLINK`; `SCAN` |
| Stale data after an update | Cache written instead of deleted on write; no TTL | Delete after commit; TTL as backstop |
| Two workers ran the same job | Lock expired mid-job or released with `DEL` | Token release, renewal, fencing |
| Lost messages | Pub/sub used as a queue | Streams with consumer groups |
| `CROSSSLOT` errors in cluster | Multi-key command across slots | Hash tags |
