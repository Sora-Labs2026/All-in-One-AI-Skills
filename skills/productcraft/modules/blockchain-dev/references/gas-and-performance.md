# Gas and performance on Aptos

Read this when a Move change affects what users pay, how much state a package creates, or how many transactions can run in parallel; when choosing a data structure; or before a launch where throughput matters. Gas schedules and framework data structures change between releases; check current documentation and measure on your own version.

## How fees work

- A transaction's fee is the gas units it uses times the gas unit price, paid in octas (1 APT = 100,000,000 octas). The sender sets a maximum gas amount and a unit price; the network enforces a minimum price, and a higher price gets priority under load.
- Gas has three main parts: **execution** (instructions run), **IO** (state slots and bytes read and written) and the **storage fee** for new state, charged per new slot and per byte. On current networks the per-slot part is refunded when the slot is deleted.
- Creating state (new resources, table entries, objects) is usually the largest cost. Computation is comparatively cheap. Optimize slots first, bytes second, instructions last.

## Measure before changing anything

- Simulate the transaction (`aptos move run` or `aptos move simulate` with the gas-profiling option your CLI version provides; `aptos move run --help` lists it) to get a per-function gas report, or call the SDK's simulation and read `gas_used`.
- Record the same transaction with the same inputs before and after a change. A gas claim without numbers from the same method is not a result.
- Profile the paths users hit most: mint, transfer, deposit, swap, claim.

## Choose data structures by access pattern

| Structure | Storage shape | Good for | Watch out for |
|---|---|---|---|
| `vector<T>` inside a resource | One slot; the whole vector is read and written | Small, bounded lists | Linear search; cost grows with every element |
| `SimpleMap` (legacy) or `OrderedMap` (newer frameworks) | One slot; vector-backed | Small maps inside one resource | Whole map loaded on each access |
| `Table<K, V>` | One slot per entry | Large, sparse maps keyed by address or ID | Not iterable; every new entry pays a slot fee |
| `SmartTable` or `BigOrderedMap` (newer frameworks; check which your version recommends) | Entries packed into a bounded number of slots | Large collections that must be iterated or ordered | More complex; check current guidance before choosing |
| Resources under each user's address or object | One slot group per user | Per-user state | None for parallelism; this is the scalable default |

## Parallel execution

Aptos executes the transactions of a block in parallel and re-executes any transaction whose reads were invalidated by an earlier write in the same block. Transactions that all write the same resource therefore run one after another, whatever their fee.

- **Keep hot writes per user.** A global "total users" counter or a config resource updated by every transaction serializes the whole workload.
- **Use aggregators for shared counters.** `aggregator_v2` counters (`add`, `try_add`, `sub`) can be updated by many transactions in parallel. *Reading* the exact value in a transaction (`read`) brings the conflict back; use aggregator snapshots when you need to embed the value (for example a token's serial number) without reading it.
```move
use aptos_framework::aggregator_v2::{Self, Aggregator};

struct Stats has key { minted: Aggregator<u64> }

fun init_module(admin: &signer) {
    move_to(admin, Stats { minted: aggregator_v2::create_unbounded_aggregator<u64>() });
}

public(package) fun record_mint() acquires Stats {
    let stats = borrow_global_mut<Stats>(@my_app);
    aggregator_v2::add(&mut stats.minted, 1);   // concurrent mints do not conflict
    // Calling aggregator_v2::read(&stats.minted) here would serialize them again.
}
```

- Collections and Fungible Asset supply tracking already use concurrent counters on current frameworks; do not wrap them in your own global counter.
- Reads of shared configuration do not conflict with each other. Only writes do.
- Events never conflict. Emit history as events and keep only current state in storage.

## Cheaper storage

- Mark resources stored at object addresses with `#[resource_group_member(group = aptos_framework::object::ObjectGroup)]` so they share the object's storage group.
- Store current state; put history in events and let the indexer keep it.
- Delete state you no longer need to recover the slot deposit, and design deletion paths for temporary records such as orders and escrows.
- Store a base URI once and derive per-item URIs from IDs instead of storing long strings per item.
- Smaller integer types save a few bytes per value, but the slot count dominates. BCS serialization has no alignment padding, so reordering struct fields saves nothing; do not distort a design for it.

## Execution

- **Bound every loop** whose length users can grow. A loop over all holders or all orders becomes too expensive to run once the data grows past the maximum gas per transaction, and the function is then unusable. Use per-user state, pagination across transactions, or pull-based claims.
- Borrow a resource once outside a loop instead of calling `borrow_global` on each iteration.
- `inline` functions remove call overhead for tiny helpers and are required for functions that take lambdas; overusing them grows bytecode size.
- Batch entry functions reduce per-transaction overhead, but one abort reverts the whole batch; validate inputs first and keep batches bounded.
- Reads that do not need consensus belong in `#[view]` functions called through the API, not in transactions.

## Transaction-level choices

- Let the SDK or wallet estimate gas and the unit price, then cap the maximum gas with a margin over the simulated amount.
- Sponsored (fee-payer) transactions let your service pay users' gas. Rate-limit and cap sponsorship per user and per day, or someone will drain the sponsor account.

## Pitfalls

| Pitfall | Fix |
|---|---|
| One global resource written by every transaction | Per-user state; aggregators for shared counters |
| Reading an aggregator's value on the hot path | Snapshots, or read off-chain through a view function |
| Unbounded loop over user-growable data | Bounded batches, per-user state, pull-based claims |
| History stored in vectors that only grow | Events plus the indexer |
| "Optimizations" without before and after numbers | Profile or simulate the same transaction both ways |
| Field reordering or packing booleans to "save padding" | Not needed: BCS has no padding; reduce slots instead |

## Done when

- [ ] Gas for each changed hot path is measured before and after with the same inputs, and the numbers are in the report.
- [ ] No transaction path writes a shared resource that every user touches, except through aggregators.
- [ ] Every loop has a bound that holds as data grows, or the design avoids the loop.
- [ ] Storage created per user or per item is known, and temporary state has a deletion path.
