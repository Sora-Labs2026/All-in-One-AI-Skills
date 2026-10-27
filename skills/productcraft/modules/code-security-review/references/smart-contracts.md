# Smart-contract security review

Reference for the `code-security-review` module. Read [Solidity basics in language pitfalls](language-pitfalls.md#solidity-basics) first: it covers reentrancy, access control, `tx.origin`, arithmetic, unchecked calls, `delegatecall`, oracles, front-running, signatures, randomness and loops, and this file does not repeat those items. Here: how to scope a contract review, the bug classes beyond that list, upgradeable contracts, token integration, testing with Foundry, and short notes on non-EVM chains.

The safety rules from that section apply throughout. Work on local chains and forks only (Foundry's Anvil, Hardhat Network). Never sign or broadcast a transaction to a live network, never handle real private keys or seed phrases, use the local chain's well-known test accounts, and treat RPC URLs as secrets because they usually embed an API key. Recommend an independent audit before value-bearing contracts are deployed or upgraded.

**Contents:** [Scope](#scope) · [Invariants first](#invariants-first) · [Classes beyond the basics](#classes-beyond-the-basics) · [Token integration](#token-integration) · [Upgradeable contracts](#upgradeable-contracts) · [Testing with Foundry](#testing-with-foundry) · [Other chains](#other-chains) · [Ready for an external audit](#ready-for-an-external-audit)

## Scope

Record before reading code:

- **Build settings:** exact compiler version, optimizer runs, `via_ir`, `evm_version` (`foundry.toml` or `hardhat.config.*`), and the commit under review.
- **Chains:** every network the contracts will run on. Layer-2 and sidechain behavior differs (see [chain differences](#classes-beyond-the-basics)).
- **Deployment:** addresses, whether contracts sit behind proxies, who can upgrade them.
- **Roles:** every privileged role (owner, admin, minter, pauser, keeper, oracle updater), what it can do in the worst case, and who holds it (one key, a multisig, a timelock, governance).
- **External dependencies:** tokens accepted, price feeds, bridges, DEXes, other protocols called, and whether each is trusted or arbitrary.
- **Baseline:** `forge build`, `forge test`, `forge coverage --report summary` and `forge build --sizes` (the 24,576-byte EIP-170 limit) must run before the review; record failures as `NOT_VERIFIED`.

## Invariants first

Write the protocol's invariants in plain language before hunting. They are the threat model, the review checklist and later the test suite. Examples for a lending vault:

- The sum of all users' balances equals `totalSupply`.
- The vault's token balance is never below what it owes depositors.
- Only the owner can change fees, and fees never exceed the documented maximum.
- A user can always withdraw their own funds unless the protocol is paused, and pausing never lets anyone else move them.
- The share price does not decrease except through a documented loss event.
- Every privileged change emits an event.

Each invariant becomes a Foundry invariant test (below). An invariant nobody can state is a design finding.

## Classes beyond the basics

| Class | What goes wrong | Look for and fix |
|---|---|---|
| Share and rounding math | First-depositor inflation on ERC-4626-style vaults: the first depositor donates tokens so later deposits round down to zero shares | Virtual shares and assets or a decimals offset (OpenZeppelin's ERC4626 has one), dead shares minted at deployment, minimum deposits; rounding that always favors the protocol (round shares down on deposit, up on withdrawal) with an explicit-rounding `mulDiv` |
| Decimals | Mixing 6-, 8- and 18-decimal amounts; low-decimal tokens where small amounts round to zero | Normalize at the boundary; tests with 2-, 6- and 24-decimal mocks |
| `msg.value` reuse | `msg.value` read inside a loop, or `multicall` that `delegatecall`s payable functions, counts the same ETH several times | Track ETH spent per call; non-payable multicall |
| Packed-hash collisions | `abi.encodePacked` with two or more dynamic arguments: `("ab","c")` and `("a","bc")` hash the same | `abi.encode`, or one dynamic argument only |
| Contract checks | `extcodesize(addr) == 0` (or `addr.code.length == 0`) is also true for a contract under construction; a low-level `call` to an address with no code returns success | Do not use "is not a contract" as security; check `code.length > 0` before low-level calls to tokens |
| Gas behavior | `transfer` and `send` forward 2,300 gas and fail for smart-contract wallets; a callee returns huge data that the caller copies; a relayer passes just enough gas that an inner call fails while the outer one succeeds (the 63/64 rule) | `call` plus reentrancy protection; bound the returned data copied from untrusted callees; check `gasleft()` where an inner failure is tolerated |
| Price feeds | A stale, zero or negative answer accepted; feed decimals assumed; on layer 2, prices used while the sequencer is down | Check `answer > 0`, `updatedAt` against the feed's heartbeat, `decimals()`, and the sequencer-uptime feed with a grace period on layer 2 |
| Cross-chain replay | Signatures valid on another chain or on a fork; a domain separator cached at deployment never changes after a fork | EIP-712 domain separator recomputed when `block.chainid` changes (OpenZeppelin's EIP712 does), plus nonce and deadline |
| Chain differences | `block.number` and `block.timestamp` mean different things on some layer-2 networks; compilers from 0.8.20 emit `PUSH0` by default, which some chains rejected; since EIP-6780 (Cancun) `selfdestruct` only deletes a contract created in the same transaction | Set `evm_version` per target chain; test on a fork of every target chain |
| Centralization | One externally owned key can upgrade, mint, pause forever or sweep funds; an ownership transfer to a typo address; `renounceOwnership` called by accident | Multisig plus timelock for privileged roles, two-step ownership (`Ownable2Step`), documented emergency powers, events on every privileged change; check `DEFAULT_ADMIN_ROLE`, which can grant every other role |
| Ordering (MEV) | Liquidations, auctions, first-come rewards and oracle updates can be raced or sandwiched | Slippage limits and deadlines (basics), commit-reveal, batch auctions; private transaction relays do not fix a design that leaks value to ordering |
| Denial of service | One reverting recipient, a blocklisted token holder, or an unbounded array blocks everyone (basics); griefing by dust deposits that make loops long | Pull payments, bounded batches, minimum amounts |

## Token integration

Decide which tokens the protocol supports. "Any ERC-20" is a claim that every behavior below is handled.

| Token behavior | What breaks | Handling |
|---|---|---|
| Fee on transfer, rebasing balances | Credited amount differs from the transferred amount; stored balances drift from real ones | Credit `balanceAfter - balanceBefore`; do not support rebasing tokens without a wrapper |
| Missing return value or `false` instead of a revert | `require(token.transfer(...))` reverts on success or ignores failure | `SafeERC20` (`safeTransfer`, `safeTransferFrom`) |
| Approval quirks | Some tokens require setting the allowance to zero before changing it; some revert on zero-value approvals or very large ones | `forceApprove` from `SafeERC20`; approve exact amounts |
| Zero-value or zero-address transfers revert | Batch payouts revert on a zero amount | Skip zero amounts |
| Blocklists and pausing | The token's admin freezes an address or the whole token, so a push payment reverts and blocks a loop | Pull payments; plan for frozen funds |
| Transfer hooks (ERC-777, ERC-721 and ERC-1155 receive hooks) | Reentrancy through the recipient | Checks-effects-interactions and `nonReentrant` (basics) |
| Upgradeable tokens | Behavior can change after integration | Monitor; limit exposure |
| Flash-mintable supply | Total supply and balances can be huge for one transaction | Never use balances or supply as governance or price inputs without time weighting |
| `permit` that silently does nothing | Some tokens have a fallback that accepts a `permit` call without effect | Check the allowance after `permit`, or use Permit2-style flows with explicit checks |
| Unusual decimals (below 6 or above 18) | Precision loss or overflow in scaling | Tests with such mocks |
| Several addresses for one token | `tokenA != tokenB` checks pass for the same asset | Allowlist tokens |
| Non-string metadata, long names | Front ends and off-chain indexers mis-parse or render injected content | Treat `name()` and `symbol()` as untrusted input off-chain |

Test integrations against mock tokens with each behavior, and against the real tokens on a fork.

## Upgradeable contracts

| Pattern | Where the upgrade logic lives | Main risks |
|---|---|---|
| Transparent proxy | Proxy, controlled by an admin contract | Admin key custody; the admin cannot call the implementation through the proxy |
| UUPS (ERC-1822 style, OpenZeppelin `UUPSUpgradeable`) | Implementation | `_authorizeUpgrade` without access control lets anyone upgrade; a new implementation without upgrade logic ends upgradeability |
| Beacon proxy | One beacon for many proxies | One upgrade changes every instance at once |
| Diamond (EIP-2535) | Facets and a selector table | Selector collisions and storage shared between facets |
| Minimal clone (EIP-1167) | None | Not upgradeable; initialization of each clone |

Check each of these:

1. **Initialization.** Constructors do not run for the proxy's storage. Every initializer has the `initializer` modifier (later versions use `reinitializer(n)`), every parent initializer runs exactly once, and the implementation's constructor calls `_disableInitializers()` (basics). Deployment and initialization happen in one transaction, or an attacker can initialize first.
2. **Storage layout.** Never reorder, remove or retype existing state variables, and never change the order of inherited contracts; only append. Older code reserves `uint256[50] private __gap` slots; current OpenZeppelin uses namespaced storage (ERC-7201). Compare layouts mechanically: run `forge inspect <Contract> storageLayout` on the deployed and the new version and diff the slots, or use the OpenZeppelin Upgrades plugins (`validateUpgrade` for Hardhat or Foundry), which also reject unsafe constructs.
3. **Implementation hygiene.** No `selfdestruct` or `delegatecall` to arbitrary targets in implementations; `immutable` variables live in the implementation's code and are shared by every proxy, which must be intended.
4. **Selector clashes** between proxy and implementation functions (the transparent pattern routes the admin separately to avoid them).
5. **Upgrade authority.** Who can upgrade, after what delay, and how users can exit before an upgrade they reject.
6. **Test the upgrade itself:** on a fork pinned to a block, deploy the new implementation, upgrade the real proxy, then run the invariant suite against the migrated state.

## Testing with Foundry

- **Unit tests** cover the failure cases as well as the happy path: `vm.expectRevert(Vault.NotOwner.selector)`, `vm.prank(attacker)`, `vm.startPrank` and `vm.stopPrank`, `vm.deal` for ETH, forge-std's `deal(address(token), user, amount)` for ERC-20 balances, `vm.warp` and `vm.roll` for time and blocks.
- **Fuzz tests** take parameters; Foundry generates values and shrinks failures to a minimal case. Constrain inputs with `bound(x, min, max)` rather than `vm.assume`, which discards runs and fails when too many are rejected. Set `[fuzz] runs = 1000` or more in `foundry.toml` for review runs.
- **Invariant tests** call a handler's functions in random sequences and check `invariant_*` functions after each call. The handler keeps inputs in valid ranges and records expected totals in "ghost" variables:

```solidity
// test/VaultInvariant.t.sol (Vault and MockToken stand in for the project's contracts)
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";
import {MockToken} from "./mocks/MockToken.sol";

contract VaultHandler is Test {
    Vault internal immutable vault;
    MockToken internal immutable token;
    address[3] internal users = [address(0x1001), address(0x1002), address(0x1003)];
    uint256 public depositedTotal;
    uint256 public withdrawnTotal;

    constructor(Vault vault_, MockToken token_) {
        vault = vault_;
        token = token_;
    }

    function deposit(uint256 who, uint256 amount) external {
        address user = users[who % users.length];
        amount = bound(amount, 1, 1e30);
        token.mint(user, amount);
        vm.startPrank(user);
        token.approve(address(vault), amount);
        vault.deposit(amount);
        vm.stopPrank();
        depositedTotal += amount;
    }

    function withdraw(uint256 who, uint256 amount) external {
        address user = users[who % users.length];
        amount = bound(amount, 0, vault.balanceOf(user));
        if (amount == 0) return;
        vm.prank(user);
        vault.withdraw(amount);
        withdrawnTotal += amount;
    }
}

contract VaultInvariantTest is Test {
    Vault internal vault;
    MockToken internal token;
    VaultHandler internal handler;

    function setUp() public {
        token = new MockToken();
        vault = new Vault(token);
        handler = new VaultHandler(vault, token);
        targetContract(address(handler)); // only the handler's functions are called
    }

    function invariant_vaultCoversDeposits() public view {
        assertGe(token.balanceOf(address(vault)), vault.totalDeposits());
    }

    function invariant_bookkeepingMatchesHistory() public view {
        assertEq(vault.totalDeposits(), handler.depositedTotal() - handler.withdrawnTotal());
    }
}
```

  Configure depth and runs in `foundry.toml` (`[invariant] runs = 256`, `depth = 100`, `fail_on_revert = false` while handlers still revert on edge cases). Add handler functions for every state-changing entry point an attacker can reach, including donations straight to the vault, and add one invariant per statement from [invariants first](#invariants-first).
- **Fork tests** run against real deployed state: `vm.createSelectFork(vm.rpcUrl("mainnet"), 19_000_000)` with `[rpc_endpoints] mainnet = "${MAINNET_RPC_URL}"` in `foundry.toml`. Pin the block number so results repeat, and keep the RPC URL in the environment, never in the repository.
- **Coverage and gas:** `forge coverage --report lcov` shows untested lines (lines, not properties); `forge snapshot` records gas per test, which catches loops growing toward the block gas limit.
- **Static analysis and proofs:** run the Solidity analyzers and linters the project already configures (Aderyn, Mythril, solhint, Semgrep rules) and triage each hit as a lead. The compiler's built-in SMTChecker, symbolic execution tools that reuse Foundry tests, and commercial provers can prove properties for all inputs. A proof covers exactly the property written down, so review the property with the same care as the code.

## Other chains

Each platform has its own failure modes; use a chain-specific checklist and, for value-bearing code, a specialist.

- **Solana (Anchor or native):** missing signer checks (`Signer<'info>`, `is_signer`); missing owner checks on accounts (Anchor's `Account<'info, T>` checks the owner and discriminator, `UncheckedAccount` and `AccountInfo` do not); one account type passed where another is expected; PDAs derived without the canonical bump (store the bump, use `seeds` and `bump` constraints); cross-program invocations to a program ID the caller supplied (use `Program<'info, T>`); spoofed sysvar accounts (use `Clock::get()` and the typed sysvars); release builds that wrap integers unless `overflow-checks = true`; closed accounts that can be revived or reinitialized (Anchor's `close` constraint); the same mutable account passed twice.
- **Move (Aptos and Sui):** `public` or `entry` functions that change state at a caller-supplied address or object without checking the signer or object ownership; refs, capabilities or signers (`ExtendRef`, `TransferRef`, `MintRef`, `SignerCapability`) reachable through public functions; generic functions that trust their type argument, so an attacker can pass an asset type of their own; randomness reachable from public functions, or outcome branches with unequal gas (test-and-abort and undergasing); unbounded loops over vectors users can grow; and upgrades that change behavior users relied on. Aptos and Sui differ in object and visibility models, so use the matching chain's rules. Build-side guidance and the `move_check.py` lead finder: `../../blockchain-dev/GUIDE.md`.

- **Cosmos SDK modules and CosmWasm:** non-determinism that halts or forks the chain (map iteration order, floats, local time, randomness), panics or unbounded loops in begin- and end-block logic, unvalidated messages, and IBC packet and timeout handling.
- **StarkNet (Cairo):** `felt252` arithmetic wraps modulo a prime, so use bounded integer types for amounts; validate layer-1 to layer-2 message senders and handle failed messages.
- **Algorand (TEAL, PyTeal):** unchecked `RekeyTo`, `CloseRemainderTo` and `AssetCloseTo` fields and unbounded fees in transactions a contract approves.
- **TON (FunC, Tact):** bounced-message handling, gas for forwarded messages, and verifying that a token wallet sender is the genuine one.
- **Substrate pallets:** arithmetic overflow, panics in runtime code, weights that undercharge expensive calls, and wrong origin checks.

## Ready for an external audit

Before auditors start, a project should have: a frozen commit; a written specification with roles and invariants; NatSpec comments on external functions; passing unit, fuzz and invariant tests with coverage reported; analyzer output triaged; a list of known issues and accepted risks; deployment, initialization and upgrade scripts in scope; and dead code removed. Missing items are hardening notes in the report, not findings.
