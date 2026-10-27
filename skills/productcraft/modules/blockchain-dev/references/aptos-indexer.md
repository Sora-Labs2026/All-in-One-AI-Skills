# Aptos indexer and chain data

Read this when an app lists tokens, balances, activity or history; queries the Aptos indexer's GraphQL API; builds a custom processor for its own events; or consumes a third-party chain-data API. Provider habits (keys, rate limits, pagination, metered pricing) are in `../../integrations/references/reliability-and-testing.md` and `../../integrations/references/memberships-and-digital-products.md`.

## Pick the data source

| Need | Use | Why |
|---|---|---|
| A current value that gates a write, an authorization or a payment | Fullnode API or your module's `#[view]` functions | Exact at a known ledger version |
| Lists and history across accounts: tokens owned, balances across assets, activity feeds | The indexer GraphQL API | Indexed, filterable, paginated |
| Aggregates specific to your module (leaderboards, order books, stats) | A custom processor writing to your database | Shaped for your queries; you control retention |
| Portfolios and analytics across many chains | A third-party chain-data API | Coverage, at a metered price and with its own freshness |

## The indexer GraphQL API

- Aptos Labs hosts an indexer per network (`https://api.<network>.aptoslabs.com/v1/graphql`, for example `testnet`). It is rate-limited; an API key from the developer portal raises the limits. Browse the schema in the portal's explorer, because table names and fields change between versions.
- Commonly used tables include `current_fungible_asset_balances`, `fungible_asset_activities`, `current_token_ownerships_v2`, `current_token_datas_v2`, `current_collections_v2`, `token_activities_v2`, `account_transactions` and `processor_status`.
- Always pass values as GraphQL variables, never by string interpolation.
- Addresses are stored in their full 64-hex-digit form. Normalize input (`AccountAddress.from(x).toStringLong()` in the SDK) before using it in a filter, or short addresses match nothing.

```graphql
query OwnedTokens($owner: String!, $limit: Int!, $offset: Int!) {
  current_token_ownerships_v2(
    where: { owner_address: { _eq: $owner }, amount: { _gt: "0" } }
    order_by: [{ last_transaction_version: desc }, { token_data_id: asc }]
    limit: $limit
    offset: $offset
  ) {
    token_data_id
    amount
    current_token_data { token_name collection_id token_uri }
  }
}
```

- **Pagination:** order by a stable key with a unique tiebreaker (as above), and respect the server's maximum `limit`. For long histories, page by `transaction_version` ranges instead of large offsets.
- The SDK wraps common queries (`getAccountOwnedTokens`, `getAccountTransactions`, fungible-asset balance helpers) and exposes `queryIndexer` for your own.

## Lag and consistency

- The indexer trails the ledger, usually by seconds and sometimes by much more. After your app submits a transaction, either read the result from the fullnode, or ask the SDK to wait until the indexer has processed that ledger version (indexer helpers accept a minimum ledger version option), or check `processor_status` for the processor you depend on.

```ts
import { AccountAddress } from "@aptos-labs/ts-sdk";

const data = await aptos.queryIndexer<{ current_token_ownerships_v2: Ownership[] }>({
  query: {
    query: OWNED_TOKENS,   // the GraphQL document above
    variables: { owner: AccountAddress.from(owner).toStringLong(), limit: 50, offset: 0 },
  },
  minimumLedgerVersion: BigInt(committed.version),   // wait until the indexer has seen our write
});
```
- Never base authorization, payouts or balance checks before a write on indexer data.
- Aptos has deterministic finality: a committed transaction is final, so there are no reorgs to unwind. Indexers can still be backfilled or reprocessed; write consumers idempotently.

## Custom processors

- For module-specific data, consume the Transaction Stream Service (a gRPC stream of transactions starting at a version) with the indexer SDK or processor framework, and write to your own Postgres.
- Store the last processed version in the same transaction as the rows it produced. Make writes idempotent, keyed by transaction version and event index, so a restart or backfill does not double count.
- Backfill from the version at which your package was first published.
- At low volume, reading your module's events through the indexer API on a schedule can be enough; measure before building a stream processor.
- Emit events with everything consumers need (IDs, amounts, actors); a processor cannot recover data that was never emitted.

## Third-party chain-data APIs

- Multi-chain balance, portfolio and history APIs save building your own indexers, at a per-call or per-credit price. Check coverage of the chains and assets you need, freshness, rate limits and the data terms before choosing one, and cap spend.
- Cross-check numbers that drive money movement against the chain itself.
- Present balances, positions and prices neutrally. Do not turn them into recommendations (`../GUIDE.md`, guardrail 3).

## Privacy

On-chain data is public, but linking an address to a person in your database creates personal data. Store that link only when needed, protect it like other personal data, disclose it in the privacy notice (`../../legal-ready/GUIDE.md`), and do not share it with data providers.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Short-form addresses in indexer filters | Normalize to the full 64-hex-digit form |
| Reading the indexer immediately after a write | Read from the fullnode, or wait for the ledger version |
| Offset pagination without a stable order | Order by version plus a unique key; page by version ranges |
| Query strings built by interpolation | GraphQL variables |
| Processor cursor saved separately from its rows | One transaction for rows and cursor; idempotent keys |
| Indexer data used for authorization | Fullnode or view functions |

## Done when

- [ ] Each read uses the right source: fullnode or view functions for decisions, the indexer for lists and history.
- [ ] Indexer queries use variables, normalized addresses and stable ordering, and paginate to the end (tested against a mocked response with several pages).
- [ ] Post-write reads handle indexer lag.
- [ ] Custom processors are idempotent, resumable from a stored version and backfilled from the deployment version.
