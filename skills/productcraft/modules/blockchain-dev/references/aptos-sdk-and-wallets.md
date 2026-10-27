# Aptos TypeScript SDK and wallets

Read this when a script, server or front end reads Aptos state, builds and submits transactions, sponsors gas, connects wallets or signs users in with a wallet. Transaction UI states (pending, confirmed, failed) follow `../../interaction-feedback.md`.

Use `@aptos-labs/ts-sdk`; the older `aptos` npm package is deprecated. The SDK and the wallet adapter release often, and method names have changed; check the installed versions and their docs.

## Client setup

```ts
import { Aptos, AptosConfig, Network } from "@aptos-labs/ts-sdk";

export const aptos = new Aptos(new AptosConfig({ network: Network.TESTNET }));
```

- Read the network from configuration, defaulting to a test network; a build that silently points at mainnet during development is a common and expensive mistake.
- Node and indexer API keys raise rate limits. Keys used in a browser are public; restrict them by origin where the provider allows it, and keep billable keys on your server.

## Reading state

- Prefer `#[view]` functions your module defines: `aptos.view({ payload: { function: `${MODULE}::counter::value`, functionArguments: [address] } })`. They are a stable interface; raw resource layouts are an implementation detail.
- `getAccountResource` returns JSON in which `u64`, `u128` and `u256` values are strings. Convert with `BigInt`, never `Number`, which loses precision above 2^53.
- Fungible balances can live in coin stores, primary fungible stores or both during the coin-to-FA migration. Use SDK or framework functions documented to cover both, or the indexer's current balance tables (`aptos-indexer.md`).

## Writing: build, simulate, sign, submit, confirm

```ts
const transaction = await aptos.transaction.build.simple({
  sender: account.accountAddress,
  data: { function: `${MODULE}::counter::increment`, functionArguments: [] },
});

const [simulation] = await aptos.transaction.simulate.simple({
  signerPublicKey: account.publicKey,
  transaction,
});
if (!simulation.success) throw new Error(`Would fail: ${simulation.vm_status}`);

const pending = await aptos.signAndSubmitTransaction({ signer: account, transaction });
const committed = await aptos.waitForTransaction({ transactionHash: pending.hash });
if (!("success" in committed) || !committed.success) {
  throw new Error(`Failed on chain: ${"vm_status" in committed ? committed.vm_status : "unknown"}`);
}
```

- In scripts and tests on devnet or localnet, `account` is a throwaway `Account.generate()` funded through the faucet (`aptos.fundAccount`). Never print its private key; never use this path for real funds. In dApps the wallet signs instead.
- **Committed is not successful.** A transaction can be committed with `success: false` (it aborted and still paid gas). Check `success` and `vm_status`. When the package's error map is available on chain, an abort status includes the error constant's name and doc comment; either way, map abort codes to user-facing messages in the app.
- **Expiry makes retries safe.** A transaction not committed before its expiration time can never be committed. Until then, do not build a second transaction for the same intent; after expiry, rebuild and resubmit.
- **Sequence numbers** order an account's transactions. Many concurrent submissions from one account collide; use the SDK's batch or worker helpers, or several sender accounts, for high throughput.
- **Arguments** are serialized from the function's on-chain ABI. Pass `u64` and larger as `bigint` or decimal strings; normalize addresses with `AccountAddress.from`. Format amounts for display with integer math and the asset's `decimals`.

## Sponsored transactions

- Build with `withFeePayer: true`; the sender signs, your service signs as fee payer (`aptos.transaction.signAsFeePayer`), and both authenticators are submitted together.
- Before your server signs as fee payer, check the payload: only your module's functions, only expected arguments, within per-user and per-day caps. A sponsor that signs anything pays for anything.
- Multi-agent transactions (several signers) follow the same pattern with additional signer authenticators.

## Wallets

Wallets that implement the Aptos wallet standard (AIP-62) are detected automatically by `@aptos-labs/wallet-adapter-react`; per-wallet plugin packages are legacy.

```tsx
import { AptosWalletAdapterProvider } from "@aptos-labs/wallet-adapter-react";
import { Network } from "@aptos-labs/ts-sdk";

export function WalletProvider({ children }: { children: React.ReactNode }) {
  return (
    <AptosWalletAdapterProvider
      autoConnect
      dappConfig={{ network: Network.TESTNET }}
      onError={(error) => reportWalletError(error)}
    >
      {children}
    </AptosWalletAdapterProvider>
  );
}
```

- `useWallet()` exposes `connected`, `account`, `network`, `wallet`, `signAndSubmitTransaction({ data: { function, functionArguments } })` and `signMessage`.
- **Check the network** the wallet reports against the app's network before submitting, and tell the user plainly when they differ.
- **Explain before asking for a signature:** in plain words, what the transaction does, the amounts with decimals applied, and the recipient. The wallet shows its own summary, but users should not have to decode function IDs.
- **After signing,** show pending until the transaction is committed, then success or the mapped failure. A user rejecting the request is a normal outcome, not an error report. Handle disconnects and account switches by resetting state tied to the old account.
- Account types beyond key-pair wallets (keyless accounts bound to an OpenID provider, passkeys) simplify onboarding and change the recovery model; read the current docs before offering them.

## Signing users in with a wallet

1. The server issues a nonce: random, single use, short expiry, bound to the session.
2. The wallet signs a human-readable message containing your domain, the nonce, the issue time and the network (`signMessage`). Prefer the chain's sign-in standard where the wallet supports it.
3. The server verifies the signature with the account's public key, checks that this key is currently authorized for the address (accounts can rotate keys, so the address is not always derived from the current key), checks domain, nonce and expiry, then consumes the nonce.
4. Never ask users to sign a transaction to log in.

## Security

- Never request, accept or store private keys or seed phrases in an app. A form that asks for them is indistinguishable from phishing.
- Build transactions from constants for your module address and function names; never from URL parameters or on-chain data.
- Treat token names, collection metadata and other on-chain strings as untrusted when rendering.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `Number(balance)` for a `u64` | `BigInt` and integer formatting |
| Treating a committed hash as success | Check `success` and `vm_status` |
| Resubmitting a fresh transaction while the first may still land | Wait for commit or expiry, then rebuild |
| Sponsor signs any payload | Allowlist functions and arguments; cap per user |
| Wallet on another network than the app | Compare networks before submitting; explain the mismatch |
| Login by signing an arbitrary transaction or a message without a nonce | Nonce-based message signing verified on the server |

## Done when

- [ ] Every write is simulated before signing, and success is read from the committed transaction, with failures mapped to messages.
- [ ] Amounts and `u64` values are `bigint` end to end; display formatting uses `decimals`.
- [ ] The app checks the wallet's network, handles rejection, disconnects and account switches, and shows honest pending states.
- [ ] Sponsored transactions and wallet sign-in follow the checks above and are tested on a test network.
