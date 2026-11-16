# Cache invalidation: keeping cached data honest

Read this when a cache shows old data after a change ("I updated the price and the app still shows the old one"), when you design how a new cache stays fresh, or when you review code that writes to a database and a cache. The short version of caching layers, HTTP headers and stampedes is in [performance.md](performance.md); Redis mechanics are in `../../data-engineering/references/redis.md`; content-hash keys for derived files are in `../../data-engineering/references/content-hash-caching.md`.

## The problem in one picture

A cache keeps a copy so reads are fast. The moment the source of truth changes, every copy of the old value is wrong, and nothing tells the cache by itself. Every invalidation strategy is a way of bounding *how wrong* and *for how long*. Decide that bound before writing code:

- **Staleness budget:** how many seconds of old data can users see for this value? Write it next to the cache key. A product description might tolerate minutes; stock at checkout, a balance, a permission or a security decision tolerates zero, and does not belong in a cache that can be stale (read it from the source of truth).
- **Blast radius:** which keys, pages and services hold a copy, directly or inside something derived (a listing page, a search index, a CDN response, a mobile app's local store)?

## The two basic exits

| | Expiry time (TTL) | Delete on change |
|---|---|---|
| How | Every entry lives N seconds, then the next read reloads it | The code path that changes the data deletes (or updates) the cached copies |
| Staleness | Up to N seconds, every time | Close to zero, when it works |
| Effort | One line per key | Must find every writer and every copy |
| Fails when | N is longer than the staleness budget | A writer forgets, a delete fails, a copy is missed, or a race repopulates old data |

Use both: delete on change for freshness, and a TTL on every key as a backstop that bounds the damage when the delete is missed. A TTL alone is fine only when the staleness budget is at least the TTL.

## Making delete-on-change correct

**Order: commit, then delete.** Write to the database, wait for the commit, then delete the key. Deleting before the commit lets a concurrent reader reload the old value into the cache and keep it there until the TTL.

**Delete, do not overwrite.** Writing the new value into the cache can race with a reader who loaded the old value a moment earlier and sets it after you. A delete lets the next read load the current value. Write-through (update the cache in the same operation) is safe only when one writer owns the key or writes carry a version (below).

**The remaining race.** Even with commit-then-delete, a slow reader can load the old row before the commit and write it into the cache after your delete. Close it with one of these:

- a short TTL as the backstop (simplest; bounds the window);
- a delayed second delete a little after the first (covers most slow readers, adds a job);
- versioned values: store the row's version or update timestamp with the cached value and refuse to set an entry older than what the cache already holds (a compare-and-set in the cache);
- leases: on a miss the cache hands the reader a token, and a delete invalidates outstanding tokens, so a set with a stale token is rejected.

**A delete that fails.** The cache can be unreachable at the moment of the write. Retry with backoff, and if it still fails, record the key in a durable "to invalidate" table or queue that a worker drains. Never let a failed delete roll back a committed database write, and never swallow the error silently.

**Do it from the data, not from every code path.** Writers multiply: an admin screen, a bulk import, a migration, a support script, another service. Hooking deletes into each one guarantees a miss. Prefer one of these:

- **Transactional outbox:** in the same transaction as the change, insert an "invalidate these keys" row; a worker reads the outbox and deletes. The change and the intent to invalidate commit together.
- **Change data capture:** a consumer reads the database's change stream (for example PostgreSQL logical replication) and invalidates keys for every changed row, whoever wrote it.

**Find every copy.** A price lives in the product key, but also in the category listing, the search index, the cart summary, a CDN-cached page and the mobile app's offline store. For each source table, keep a short list of the keys and derived artifacts that embed it, and invalidate all of them. When the list gets long, switch to one of the approaches below.

## Approaches that avoid hunting for keys

- **Versioned keys (generations).** Keep a version number per entity or per group (`product:42:v17`, or a namespace counter `catalog:gen`). On change, increment the version; readers build keys from the current version, so old entries are never read again and age out by TTL. One increment invalidates any number of derived keys.
- **Tags.** Store the set of tags each entry depends on (`product:42`, `category:7`) and delete by tag on change. Many CDNs and frameworks support tag- or key-based purge.
- **Content-addressed keys.** Key by a hash of every input (see `content-hash-caching.md`). A new input is a new key; nothing needs invalidating. Ideal for derived files and build outputs.
- **Short TTL plus revalidation.** For HTTP, `Cache-Control: max-age=60, stale-while-revalidate=300` with an `ETag` keeps responses fresh within a minute while staying fast.

## Layers beyond your own cache

- **CDN and edge:** purge by URL or tag on change, or keep HTML short-lived and cache only content-hashed assets for a year (`immutable`). Purges are asynchronous and can take seconds to propagate; check the provider's documented time.
- **Browsers:** you cannot purge them. Long-lived caching is safe only for content-hashed URLs; anything else needs a short `max-age` or `no-cache` with validation.
- **Multiple regions or replicas:** a delete in one region does not reach the others unless you publish it; reads from a lagging database replica can repopulate the cache with old data right after your delete. Read from the primary when refilling a just-invalidated key, or wait out replica lag.
- **In-process caches:** each server holds its own copy. Broadcast invalidations (pub/sub) or keep TTLs short enough to meet the budget.
- **Clients and offline stores:** send a version or an `updated_at` with responses so clients can detect and refresh old records.

## Prices, stock and money

Show a cached price for browsing if the budget allows, but recompute everything that is charged from the source of truth at the moment of the decision: the price, discounts, tax and stock when the order is placed. If the shown and charged price differ, tell the user before charging. Consumer law in many places requires the charged price to match the price displayed (`../../legal-ready/references/honest-commerce.md`).

## Testing and monitoring

- **Tests:** for each writer, assert that after the write the next read returns the new value. Add a concurrency test that interleaves a slow reader with a writer (inject a pause between "load from database" and "set in cache") and checks the final cached value.
- **Staleness metric:** sample keys, compare the cached value or version with the source of truth, and alert when mismatches exceed the budget.
- **Logs:** count invalidation failures and outbox backlog; a growing backlog means stale data is accumulating.
- **Runbook:** a safe way to purge a key, a tag or a namespace, with a note on the load a full purge puts on the database.

## Done when

- [ ] Each cache states its key, staleness budget, invalidation method and TTL backstop.
- [ ] Writes commit before they delete; deletes (not overwrites) are the default; failed deletes are retried durably.
- [ ] Invalidation hangs off the data (outbox or change stream) or a version, not off individual code paths, when more than one writer exists.
- [ ] Every derived copy (listings, search, CDN, other regions, clients) is on the invalidation list or covered by versions or tags.
- [ ] Anything charged, authorized or counted is read from the source of truth at decision time.
- [ ] Tests cover read-after-write and the slow-reader race; staleness is measured in production.
