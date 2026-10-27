# Solana RPC and webhooks

Read this when an app reads Solana state, sends and confirms transactions, sets priority fees, subscribes to account or program changes, receives webhooks from a Solana RPC provider, credits deposits, or queries NFTs and tokens through the Digital Asset Standard API. Security review of on-chain programs (signer, owner and PDA checks, overflow, account confusion) is in the Solana notes of `../../code-security-review/references/smart-contracts.md#other-chains`; this file does not cover writing programs.

## Endpoints and libraries

- The public cluster endpoints are rate-limited and unsuitable for production. Use a Solana RPC provider or your own node, with separate endpoints per cluster (localnet, devnet, testnet, mainnet-beta).
- Provider URLs usually carry an API key in the path or query string. Treat the full URL as a secret: keep it on the server, or use the provider's domain-restricted keys for browser traffic.
- `solana-test-validator` runs a local cluster for tests and can clone accounts and programs from another cluster (`--clone` with `--url`).
- TypeScript: `@solana/kit` (the successor to web3.js 2.x) or `@solana/web3.js` 1.x (in maintenance, still common, and what many framework clients build on). Use one per code path. Rust: the `solana-client` crates; Python: `solana-py` with `solders`.
- 1 SOL is 1,000,000,000 lamports. Lamports and token amounts are `u64`; use `bigint` (native in `@solana/kit`).

## Commitment

| Level | Meaning | Use for |
|---|---|---|
| `processed` | Seen by the node; can still be dropped | Nothing that matters |
| `confirmed` | Voted on by a supermajority; reverting is very rare | UI feedback, non-critical reads |
| `finalized` | Rooted; will not be reverted | Crediting deposits, releasing goods, anything irreversible off chain |

Read with the same or a stronger commitment than you wrote with; reading at `finalized` right after a `confirmed` write returns stale data.

## Sending transactions that land

1. **Fetch a recent blockhash** with `getLatestBlockhash`, keeping its `lastValidBlockHeight`. A blockhash is valid for about 150 blocks, roughly a minute or two.
2. **Simulate** (`simulateTransaction`, with `replaceRecentBlockhash` and without signature verification for unsigned drafts) to get errors and the compute units consumed.
3. **Set the compute budget**: a `setComputeUnitLimit` instruction at the simulated units plus a margin of 10 to 20 percent, and a `setComputeUnitPrice` from a current fee estimate (below). Put both first in the transaction.
4. **Sign** (in apps, the wallet signs), then send the serialized transaction with `maxRetries: 0` so you control retries.
5. **Rebroadcast the same signed bytes** every couple of seconds while polling `getSignatureStatuses`, until the status reaches your commitment, it reports an error, or the current block height passes `lastValidBlockHeight`.
6. **Only after expiry** rebuild with a new blockhash and sign again. A signed transaction can execute at most once, so rebroadcasting it is safe; signing a second transaction before the first expires can execute both.

```ts
import { Connection, VersionedTransaction } from "@solana/web3.js";

export async function sendUntilConfirmed(conn: Connection, tx: VersionedTransaction, lastValidBlockHeight: number) {
  const raw = tx.serialize();
  const signature = await conn.sendRawTransaction(raw, { skipPreflight: true, maxRetries: 0 }); // simulated beforehand
  for (;;) {
    const status = (await conn.getSignatureStatuses([signature])).value[0];
    if (status?.err) throw new Error(`Transaction failed: ${JSON.stringify(status.err)}`);
    if (status?.confirmationStatus === "confirmed" || status?.confirmationStatus === "finalized") return signature;
    if ((await conn.getBlockHeight("confirmed")) > lastValidBlockHeight) {
      throw new Error("Blockhash expired without landing; safe to rebuild and sign again");
    }
    await conn.sendRawTransaction(raw, { skipPreflight: true, maxRetries: 0 }).catch(() => undefined);
    await new Promise((resolve) => setTimeout(resolve, 2_000));
  }
}
```

For signing flows that take longer than a blockhash lives (offline or multi-party signing), use a durable nonce account instead of a recent blockhash.

## Priority fees and compute

- Fee = base fee (5,000 lamports per signature) + priority fee (compute-unit limit times compute-unit price in micro-lamports).
- Fee markets are local to the accounts a transaction writes. Estimate the price from `getRecentPrioritizationFees` for those accounts, or from your provider's estimate, choose a percentile, and cap it. Never hard-code a price.
- A tight compute-unit limit from simulation both lowers the fee and helps scheduling; the default limit per instruction is far above what most need.

## Reading accounts and history

- `getAccountInfo` and `getMultipleAccounts` (up to 100 per call) with base64 encoding, decoded with the program's layout (an IDL or Borsh schema); `jsonParsed` works for the token programs.
- `getProgramAccounts` scans every account of a program. Always pass `filters` (`dataSize`, `memcmp` at a known offset) and a `dataSlice`; providers often restrict the method, and at scale you need your own index.
- **Two token programs:** SPL Token and Token-2022 (Token Extensions) have different program IDs, and the associated token account address depends on which one owns the mint. Token-2022 mints can carry extensions (transfer fees, transfer hooks, non-transferability) that change what a transfer does. Read the mint's owner program and extensions before building transfers.
- **History:** `getSignaturesForAddress` returns at most 1,000 signatures per call; page backwards with `before`. Fetch each with `getTransaction` and `maxSupportedTransactionVersion: 0`, or version-0 transactions fail to load. Version-0 transactions can reference accounts through address lookup tables; resolve them from `meta.loadedAddresses`.

## Digital assets (DAS API)

- The Digital Asset Standard API is an RPC extension implemented by several providers: `getAsset`, `getAssetsByOwner`, `getAssetsByGroup` (by collection), `searchAssets`, and `getAssetProof` for compressed NFTs. Pagination uses `page` and `limit` or cursors; support and limits differ by provider.
- Compressed NFTs live as leaves in Merkle trees; their ownership comes from indexers, and transfers need a proof. For decisions that move value, verify the proof against the on-chain tree root rather than trusting an indexer response.

## Subscriptions and streams

- WebSocket subscriptions (`accountSubscribe`, `programSubscribe`, `logsSubscribe`, `signatureSubscribe`) drop without warning. Send heartbeats, reconnect with backoff, resubscribe, and backfill the gap with `getSignaturesForAddress` from the last signature you processed.
- High-volume consumers use Geyser-based gRPC streams from providers or their own nodes; the same reconnect and backfill discipline applies.

## Provider webhooks

- Verify each delivery as the provider specifies (a signature, or at least a shared secret header compared in constant time); see `../../integrations/references/webhooks.md`. When the provider offers only a static token, re-fetch the transaction by signature from RPC before acting.
- Deliveries are at least once and unordered. Deduplicate by transaction signature (plus instruction index when one transaction carries several relevant instructions).
- Know which commitment the provider delivers at. Before crediting value, re-check the transaction's status at `finalized`.
- Provider-parsed ("enhanced") payloads are an interpretation. For money, parse the raw transaction yourself.
- Reconcile on a schedule from `getSignaturesForAddress` since the last processed signature; webhooks get missed.

## Crediting deposits

1. Detect the transaction (webhook, subscription or polling).
2. Fetch it at `finalized` and require `meta.err` to be null.
3. Compute the amount from balance deltas (`meta.preTokenBalances` and `meta.postTokenBalances`, or lamport balances), checking the exact mint address and token program, and that the receiving token account is owned by your deposit address. Lookalike mints with the same symbol are common.
4. Credit idempotently under a unique constraint on the signature (and instruction index), then reconcile.

## Keys

- Keypair files (`~/.config/solana/id.json` and similar JSON arrays of 64 numbers) are private keys. Never read, print or commit them; the user creates them with `solana-keygen`. Agent-run scripts use throwaway devnet or localnet keys only.
- Apps connect wallets through the Wallet Standard (for example the Solana wallet adapter) and never ask for seed phrases.
- Devnet SOL comes from `solana airdrop` (rate-limited) or a web faucet.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Resigning with a fresh blockhash while the first transaction may still land | Rebroadcast the same bytes until the block height passes `lastValidBlockHeight` |
| Hard-coded priority fee or no compute limit | Simulate, set the limit with a margin, estimate the price, cap it |
| Crediting at `processed` or `confirmed` | Re-check at `finalized` before irreversible effects |
| `getTransaction` without `maxSupportedTransactionVersion` | Pass `0` |
| Unfiltered `getProgramAccounts` | Filters, data slices, or your own index |
| Assuming one token program | Check the mint's owner program and extensions |
| Trusting a webhook's parsed amount and mint | Fetch and parse the raw transaction; verify mint, owner and amount |
| RPC URL with an embedded key shipped to browsers | Server-side proxy or domain-restricted keys |

## Done when

- [ ] Sends simulate first, set the compute budget from the simulation, and follow the block-height expiry loop (tested against a local validator).
- [ ] Commitment levels are chosen per use; credits happen only at `finalized`.
- [ ] Webhooks and subscriptions are verified, deduplicated by signature, and backed by a reconciliation job.
- [ ] Token handling checks the token program, mint and owner; amounts are `bigint`.
- [ ] No keypair file or keyed RPC URL is committed or exposed to clients.
