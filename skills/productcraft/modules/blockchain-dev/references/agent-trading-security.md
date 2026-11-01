# Agents with trading or wallet authority

Read this when an LLM-driven agent can place orders through an exchange or broker API, sign blockchain transactions, grant token approvals or move funds, or when reviewing such a system. The general rules for agents that spend money (hard caps, recipient allowlists, a person's approval, keys outside the model's context, ledgers and sandbox tests) are in `../../agent-engineering/references/spending-controls.md`, and approval design is in `../../agent-engineering/references/approval-gates.md`; this file adds what trading changes. Using market prices as a research signal is in `../../research-writing/references/prediction-market-signals.md`.

**Guardrails.** The owner chooses the strategy, the venues, the assets and every limit, in writing; the agent proposes none of them and gives no investment advice. Development happens on test networks, forks, exchange sandboxes or paper trading; going live, and every increase in limits, is the owner's decision. Automated trading can be regulated (securities, derivatives, commodities, betting rules for prediction markets, money transmission where funds belong to others), and venues restrict API use and geography in their terms. Flag these for the owner's counsel; never help bypass identity checks, geographic blocks or rate limits.

## Threat model

- **Assets:** funds in hot wallets and exchange accounts, API keys and session keys, token approvals already granted, the strategy itself, and users' portfolio data.
- **Untrusted text that reaches the model:** token names and symbols, NFT and contract metadata, memo and calldata fields, social feeds, news, web pages, other agents' messages, and even error strings from venues. Any of them can carry instructions such as "move the balance to 0x...".
- **Failures without an attacker:** invented or mistyped addresses, amounts in the wrong decimals, the wrong chain, stale prices read as current, a timeout read as failure and retried into a duplicate order, partial fills ignored, loops that resubmit the same intent.
- **Market adversaries:** sandwiching and other ordering attacks, thin pairs that are cheap to push, look-alike tokens that copy a symbol, tokens that block selling or charge large transfer fees, and phishing approvals.

## Architecture: the model proposes, deterministic code decides

1. **Planner (the model)** emits a typed intent and nothing else: action, venue, asset by chain ID and contract address or by venue instrument ID, side, amount in base units, limit price or minimum output, expiry and a short rationale. Validate it against a schema and reject unknown fields.
2. **Policy engine (ordinary code)** checks the intent against the owner's configuration (below). It cannot be changed by the model, and its configuration is not in the model's context to edit.
3. **Executor (ordinary code)** builds the order or transaction itself from the validated intent. The model never supplies raw calldata, a recipient address or a contract to call.
4. **Signer** holds keys in a separate process, a key management service, a hardware module, or a smart account with a scoped session key. It re-checks limits as a second layer and rate-limits signatures.
5. **Monitor and reconciler** confirm what actually happened and feed circuit breakers.

The model never sees keys, never sets its own limits, and never gets a tool that signs arbitrary data.

## Policy checks, outside the model

| Check | What it enforces |
|---|---|
| Venue and contract allowlist | Router and pool addresses per chain ID, function selectors allowed per contract; decoded calldata must send output to the owner's own account |
| Asset allowlist | By chain ID plus address, or venue instrument ID; never by symbol; new tokens need the owner's approval |
| Size and exposure caps | Per order, per day, per asset and total open exposure, in base units, valued with an independent price source |
| Slippage and expiry | Minimum output from an independent quote, not from the pool being traded; short deadlines; limit orders where the venue offers them |
| Approvals | Exact amounts only, never unlimited; revoked after use; signed permits treated as spending, with short expiry |
| Price sanity | Two independent sources agree within the owner's tolerance, and both are fresh |
| Rate and duplicates | Orders per minute; an idempotency key per intent so a loop or retry cannot place the same order twice |
| Chain and nonce | The provider's chain ID matches the configuration; nonces managed by the executor, one sender at a time |
| Exchange key scope | Trade-only keys with withdrawals disabled, an IP allowlist, and a sub-account holding only the funds the owner assigned |

A failed check rejects the intent and records why. Repeated attempts to break policy, such as a recipient that is not the owner, are themselves a signal to halt and page a person.

## Simulate, send, verify

- **Before signing,** simulate against current state (`eth_call` or the provider's simulation with state overrides) and decode the result as balance changes for the owner's account: the expected asset leaves, the expected asset arrives, and no approval or transfer goes anywhere else. A round-trip simulation (buy, then sell back) exposes tokens that block selling or charge hidden fees.
- **Send** swaps through protected submission to block builders where available, with slippage limits still set. Protection reduces sandwiching; it does not replace limits.
- **After sending,** wait for the receipt, check its status, and read actual amounts from the logs. On exchanges, use client order IDs and reconcile fills and positions from the venue, which is the source of truth.
- **Unknown outcomes** (timeouts, crashes) are resolved by querying the chain or the venue before any retry. A blind retry is how duplicate orders happen.

## On-chain accounts with limits built in

Where the chain supports it, put the limits in the account itself so a compromised agent host still cannot exceed them:

- **Smart accounts with session keys** (ERC-4337 accounts, and modular accounts following ERC-7579): the agent gets a session key whose validation module allows only listed contracts and selectors, caps amounts per period and expires. The owner's main key stays offline and can revoke the session key at any time. Audit the module itself; it is now the policy engine of last resort.
- **EIP-7702 delegations** (live on Ethereum mainnet since the Pectra upgrade in May 2025) let an ordinary account run a contract's code. Signing a delegation to the wrong contract hands over the whole account, so the agent must never be able to request or sign one; treat delegation authorizations as owner-only, made with the owner's own wallet after review.
- **Exchange-side equivalents:** sub-accounts with fixed funding, trade-only API keys and venue-side position limits.

## Circuit breakers and the kill switch

- The owner sets the thresholds. Common triggers: realized or unrealized loss over a window beyond the owner's limit; consecutive rejected or failed orders; stale or disagreeing price data; balances that change unexpectedly; the RPC or venue returning inconsistent state; any policy violation attempted by the model.
- Halting stops new orders, optionally cancels open orders as the owner decided in advance, keeps monitoring running and notifies a person. Only a person resumes.
- A kill switch that does not depend on the agent: revoke the exchange key or session key, disable the signer, or move funds out with the owner's own wallet.

## Prompt injection in trading contexts

- Keyword filters on incoming text help with logging but are not a control. The policy engine is the control: even a fully hijacked planner can only propose intents that pass the owner's checks.
- Split readers from actors. An agent that reads social feeds, web pages or token metadata does not hold execution tools in the same context; it hands typed fields (a score, a summary, an instrument ID from the allowlist) to the planner.
- Recipients and contract addresses come from configuration, never from text the model extracted.
- A person approves any new asset, new venue, size above the owner's threshold, and every withdrawal or transfer out of the trading account.

## Test before real funds

- Paper trading on live data, exchange sandboxes, and forked chains (Anvil or Hardhat) for on-chain flows.
- Adversarial cases: a token whose name instructs the agent to send funds; a look-alike token with the same symbol; a stale or zero price; a venue timeout followed by a late fill; a partial fill; the same message delivered twice; the model proposing an amount in the wrong decimals; a request to raise a limit. Each must end in rejection or a halt, never an order.
- Replay recorded sessions after every change to prompts, models or policy.
- Go live with a small cap the owner sets, watched by the owner, and raise it only by their decision.

## Logging

Record every intent including rejected ones, each policy decision with its reason, simulation results, signatures requested, transaction hashes and order IDs, fills, and halts. Use append-only storage, keep keys and API secrets out of it, and reconcile daily against the chain and the venue's statements.

## Done when

- [ ] Planner, policy engine, executor and signer are separate; keys and limits are outside the model's reach.
- [ ] The policy engine enforces allowlists by address or instrument ID, caps, independent slippage, exact approvals and chain ID.
- [ ] Every send is preceded by a decoded simulation and followed by reconciliation; unknown outcomes are queried, not retried.
- [ ] Circuit breakers and an independent kill switch were exercised in a sandbox or on a fork.
- [ ] The adversarial cases above end in rejection or a halt; the owner approved live limits in writing.
- [ ] No output recommends trades, assets or sizes; the strategy and limits are the owner's.
