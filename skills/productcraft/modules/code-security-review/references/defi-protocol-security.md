# DeFi protocol security: AMMs, oracles, flash loans and rounding

Reference for the `code-security-review` module. Read it after [Solidity basics](language-pitfalls.md#solidity-basics) and [smart contracts](smart-contracts.md), which already cover reentrancy, access control, first-depositor inflation, price-feed staleness checks, token quirks, upgrades and Foundry testing. This file adds depth for protocols that price, swap, lend or account for shares: the single-transaction attacker, AMM invariants, oracle design, lending and liquidation, rounding direction, governance and MEV, and how to prove an economic exploit on a fork. Off-chain amount and hashing bugs are in `../../blockchain-dev/references/evm-units-and-hashing.md`.

Same safety rules as the contract references: local chains and forks only, never sign or broadcast to a live network, never handle real keys, RPC URLs are secrets, and recommend an independent audit before value-bearing deployment. Nothing here is investment advice.

## The attacker to design against

Inside one transaction an attacker can borrow almost any amount (flash loans, flash swaps, flash mints), call public functions in any order, receive callbacks, and repay at the end. If anything fails, the whole transaction reverts and costs only gas. So:

- Any value read from on-chain state that capital can move within the same transaction is attacker-controlled for that transaction: pool spot prices and reserves, `balanceOf(address(this))`, `totalSupply`, a vault's exchange rate, LP token value, governance token balances.
- Across blocks, block builders and validators choose transaction order; searchers sandwich and back-run. Validators who know they propose consecutive blocks can hold a manipulated price for more than one block with little arbitrage risk.
- Callbacks (token hooks, flash-loan receivers, ETH transfers) hand control to the attacker in the middle of your function.

For every external or public function, answer three questions in the review notes: which state does it read that capital or ordering can move; can a caller profit by calling it at a manipulated moment; and is any state half-updated when control leaves the contract?

## AMM invariants

| Design | Invariant to check | Typical defects |
|---|---|---|
| Constant product (v2 style) | After a swap, fee-adjusted balances satisfy `(b0*1000 - in0*3) * (b1*1000 - in1*3) >= r0 * r1 * 1000**2` for a 0.3% fee, using actual balances measured after transfers | Fee applied to the output instead of the input; invariant checked on reserves instead of balances; `sync` and `skim` let anyone align reserves with balances, so a donation changes the price |
| Concentrated liquidity (v3 style) | Amounts owed to the pool round up, amounts paid out round down; tick crossing updates liquidity exactly once | Rounding in the user's favor at tick boundaries; wrong sign handling for negative ticks |
| Stable swap (invariant solved iteratively) | Newton iterations converge within the loop bound, and failure reverts | Silent non-convergence returning a stale value; amplification changes applied instantly instead of ramped |
| Weighted and custom curves | Invariant never decreases except by documented fees | Precision loss in exponentiation; extreme weights; zero balances |

Integrations that swap through a router need the caller's own limits: `amountOutMin` derived from an off-chain quote or an independent oracle, and a real deadline. Computing `amountOutMin` on-chain from the same pool you are about to trade in protects nothing, and `deadline = block.timestamp` is always satisfied.

**Pricing LP tokens.** Never value an LP token as `reserve * spotPrice / supply`: reserves move with a flash swap. For a constant-product pair, value it from the invariant and independent prices: `2 * sqrt(r0 * r1) * sqrt(p0 * p1) / totalSupply`, with `p0` and `p1` from manipulation-resistant feeds, so moving the reserves does not move the result.

## Oracles

| Source | What it costs to move | Failure modes | Use for |
|---|---|---|---|
| Pool spot price (`getReserves`, `slot0`) | One flash loan plus fees | Moved and restored within one transaction | Nothing that values collateral or mints shares |
| Pool time-weighted average (cumulative prices, `observe`) | Grows with window length and pool liquidity | Thin pools are cheap to hold off-price; multi-block manipulation by validators; lags real moves, so it is stale in a crash; too few stored observations makes reads revert | Secondary or sanity source; primary only for deep pools with a window sized to the pool's liquidity |
| Push feeds from an oracle network | Corrupting the network or its sources | Stale or zero answers, wrong decimals, sequencer downtime on layer 2 (see smart-contracts.md); some aggregators clamp at configured bounds, so the reported price stops while the market moves on | Primary valuation, with freshness, bounds and decimals checks |
| Pull feeds (signed updates submitted with the transaction) | Corrupting the publishers | The caller chooses which valid update to submit, so they can pick a favorable one inside the freshness window; confidence intervals ignored | Primary valuation with a tight staleness limit and confidence checks |
| A vault's own exchange rate (`convertToAssets`, `getRate`) | A donation to the vault | Donation inflates the rate; read-only reentrancy during the vault's own callbacks | Only with donation-resistant accounting and a reentrancy check |

Implementation checks:

- Time-weighted average ticks: Solidity integer division rounds toward zero, so for a negative tick delta that does not divide evenly, subtract one to round toward negative infinity, as the reference oracle library does. Make sure the pool stores enough observations for the window (increase the observation cardinality ahead of time) and handle the "too old" revert.
- Compare two independent sources; beyond a deviation limit the owner sets, pause the affected actions or fall back to the safer source rather than averaging a broken value in.
- Do not let one transaction both update a price and consume it (update-then-liquidate in a single call).
- Treat a price at or beyond your own sanity bounds as invalid, not as the bound.

## Read-only reentrancy

A pool that sends ETH or calls a token hook before it finishes updating its own state exposes view functions (virtual price, share price, reserves) that return inconsistent values during the callback. A lending protocol that reads that view as a price during the callback can be drained. Check every external view you consume: does the source protocol expose a reentrancy-lock status you can query, or offer a function that reverts while locked? Call it before reading the price.

## Lending and liquidation

- **Accrue first.** Interest accrual must run before any action that reads balances, debt or the exchange rate.
- **Rounding against the borrower:** debt rounds up, collateral value rounds down, health checks use the rounded values.
- **Liquidations must stay profitable** after gas at the smallest allowed position, or small positions accumulate bad debt. Enforce a minimum position size and state who absorbs bad debt (reserves, a backstop, socialized loss).
- **Close factor and bonus:** make sure a liquidation cannot leave the borrower less healthy than before (bonus larger than the remaining collateral margin), and that self-liquidation is not a profit loop.
- **Empty or newly listed markets:** an exchange-rate market with near-zero supply can have its rate inflated by a donation, after which rounding on redeem or borrow lets an attacker take more than they put in, often draining other markets through cross-collateral. Mint unrecoverable seed supply at listing, list with a zero collateral factor until the market is seeded, or use virtual shares.
- **Pause design:** decide action by action. Pausing liquidations or repayments while prices move creates bad debt; pausing new borrows usually does not.
- **Collateral that is itself a share or LP token** must be priced through its underlying assets with the manipulation-resistant methods above.

## Rounding and precision

Every rounding step favors the protocol, which means against the caller. Write the direction for each function into the review and test it.

| Quantity | Direction | ERC-4626 equivalent |
|---|---|---|
| Shares minted for assets deposited | Down | `previewDeposit`, `convertToShares` |
| Assets required to mint shares | Up | `previewMint` |
| Shares burned to withdraw assets | Up | `previewWithdraw` |
| Assets paid for shares redeemed | Down | `previewRedeem`, `convertToAssets` |
| Debt recorded, fees charged | Up | |
| Collateral value, rewards paid | Down | |

- Multiply before dividing; use a full-precision `mulDiv` with an explicit rounding mode (`Math.mulDiv(x, y, d, Math.Rounding.Ceil)` in OpenZeppelin Contracts 5.x; the 4.x name is `Rounding.Up`); accumulate and divide once rather than rounding inside a loop.
- An operation that would round a non-zero input to zero output (zero shares for a deposit, zero assets for a burn) must revert, not succeed.
- One-unit rounding errors matter when an attacker can repeat the operation thousands of times in one transaction, or when a unit is valuable (8-decimal tokens, inflated exchange rates).
- Test rounding with exact integer inequalities rather than a second floating-point implementation. For "shares round down": `shares * totalAssets <= assets * totalShares` and `(shares + 1) * totalAssets > assets * totalShares`, with fuzzed inputs bounded so the products cannot overflow.

## Governance and admin

- Voting power comes from a snapshot taken before the proposal (`getPastVotes` at the proposal's snapshot block), never from current balances, which a flash loan can inflate.
- A timelock sits between a passed proposal and its execution, long enough for users to exit; quorum uses past total supply.
- Review proposal payloads as code: a proposal that upgrades a contract or adds a minter is the attack.
- Parameter setters have hard upper and lower bounds in code (fee caps, collateral factors, oracle addresses changed only through the timelock).

## MEV-aware design

- Operations that leak value to ordering: swaps, liquidations, harvests that realize profit in one step, rebalances, oracle updates followed by actions.
- Defenses: caller-set slippage and deadlines from off-chain quotes; profit unlocked linearly over time instead of in one harvest; batch auctions or commit-reveal where fairness matters; private submission for the protocol's own keeper transactions. Private submission does not fix a design that leaks value; it only hides it from some searchers.

## Prove it on a fork

Reproduce economic findings on a local fork pinned to a block. The test below is a sketch with placeholder interfaces; `deal` stands in for a flash loan, so subtract the real loan fee when you report profit.

```solidity
// test/PriceManipulation.t.sol (IPool, ILender and Attacker stand in for the protocol's contracts)
function test_spotPriceManipulationDrainsLender() public {
    vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK); // RPC URL comes from the environment
    Attacker attacker = new Attacker(pool, lender, tokenA, tokenB);
    deal(address(tokenA), address(attacker), 5_000_000e18);  // capital a flash loan would provide
    uint256 before = tokenA.balanceOf(address(attacker));

    attacker.run(); // swap to move the pool, borrow against inflated collateral, swap back

    uint256 profit = tokenA.balanceOf(address(attacker)) - before;
    assertGt(profit, LOAN_FEE, "manipulation is not profitable at this block");
}
```

- Keep the passing exploit test as evidence, then turn it into a regression test that asserts no profit once the fix is in.
- Extend the invariant handler from smart-contracts.md with DeFi moves: large swaps against the pool, donations to the vault and the pool, oracle updates, time warps, and a handler function that runs a whole borrow-manipulate-act-restore sequence in one call.
- Report the block number, the capital assumed, fees and the profit, and mark anything you could not run on a fork `NOT_VERIFIED`.

## Done when

- [ ] Every price, balance, supply and exchange-rate read is classified as movable within a transaction, movable across blocks, or a trusted feed, with the defense written next to it.
- [ ] Oracle reads check freshness, bounds, decimals and deviation from a second source, plus sequencer status on layer 2.
- [ ] The rounding table is filled for each value-moving function, zero-output cases revert, and rounding properties are fuzzed.
- [ ] Slippage limits and deadlines come from the caller, not from the pool being traded.
- [ ] Each valuation path has a flash-loan scenario test on a pinned fork, or is marked `NOT_VERIFIED` with the reason.
- [ ] Liquidations stay profitable at the minimum position size, and the bad-debt path is defined.
- [ ] Governance uses past snapshots and a timelock; privileged setters are bounded in code.
