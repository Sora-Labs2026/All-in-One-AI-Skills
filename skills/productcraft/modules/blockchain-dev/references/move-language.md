# Move on Aptos: the language

Read this when writing or changing Move modules for Aptos: types and abilities, global storage, signers and authorization, visibility, errors, arithmetic, generics and the common patterns. Objects and token standards are in `objects-and-tokens.md`; tests and specifications in `testing-and-prover.md`.

**Versions.** Aptos compiles Move 2 (compiler v2), and each language release (2.0, 2.1, 2.2, ...) adds syntax. Check `aptos --version`, the language version your CLI uses by default, and the release notes before using a recent feature. **Sui Move is a different dialect** (objects with `UID`, `TxContext`, programmable transaction blocks, its own naming checklist). Do not apply Sui conventions or code to Aptos, or the reverse.

## A small module

```move
module my_app::counter {
    use std::error;
    use std::signer;

    /// The account has no counter yet.
    const E_NO_COUNTER: u64 = 1;
    /// The account already has a counter.
    const E_ALREADY_EXISTS: u64 = 2;

    struct Counter has key { value: u64 }

    #[event]
    struct Incremented has drop, store { owner: address, value: u64 }

    public entry fun create(owner: &signer) {
        let addr = signer::address_of(owner);
        assert!(!exists<Counter>(addr), error::already_exists(E_ALREADY_EXISTS));
        move_to(owner, Counter { value: 0 });
    }

    public entry fun increment(owner: &signer) acquires Counter {
        let addr = signer::address_of(owner);
        assert!(exists<Counter>(addr), error::not_found(E_NO_COUNTER));
        let counter = borrow_global_mut<Counter>(addr);
        counter.value = counter.value + 1;
        aptos_framework::event::emit(Incremented { owner: addr, value: counter.value });
    }

    #[view]
    public fun value(addr: address): u64 acquires Counter {
        assert!(exists<Counter>(addr), error::not_found(E_NO_COUNTER));
        borrow_global<Counter>(addr).value
    }
}
```

`my_app` is a named address assigned in `Move.toml` or on the command line (`aptos-cli-and-packages.md`). `#[view]` functions can be called from the SDK without a transaction.

## Abilities

| Ability | Allows | Leave it off when |
|---|---|---|
| `copy` | Duplicating a value | The value represents something scarce: an asset, a receipt, a capability |
| `drop` | Discarding a value implicitly | The value must be consumed by a specific function (a receipt or obligation) |
| `store` | Storing the value inside other structs in global storage | The value must never leave your module's own resources |
| `key` | Being a top-level resource under an address | The type is only ever nested |

A struct can have an ability only if all its fields do. Give each type the fewest abilities that work: abilities are how Move enforces that assets are not copied and obligations are not ignored. Type parameters that only tag a type (`Pool<phantom CoinType>`) are declared `phantom` so they do not need the abilities themselves.

## Global storage

- Resources live under account or object addresses: `move_to`, `move_from`, `borrow_global`, `borrow_global_mut`, `exists`. Move 2 adds index notation (`Counter[addr].value`, `&mut Counter[addr]`).
- Only the module that declares a type can create, read, change or destroy it in storage. Other modules go through your public functions, so those functions *are* your access control.
- Functions that touch storage declare `acquires` for the types they borrow (recent compilers can infer it; follow what your compiler version requires).
- Prefer data under each user's own address or object over one global table: it scales and lets transactions run in parallel (`gas-and-performance.md`).

## Signers and authorization

- A `&signer` reaches your code only as a transaction argument (or from a stored capability such as an `ExtendRef`). It proves who authorized the transaction; it does not prove they may do *this*. Compare `signer::address_of(s)` with the owner or admin stored in your state, or check object ownership.
- `init_module(deployer: &signer)` runs once, when the module is first published. It does not run on upgrades. Store the admin address and configuration there; a later upgrade that needs new initialization requires a separately gated entry function.
- Keep admin rights transferable with a two-step handover (propose, then accept by the new address), and emit an event on every privileged change.
- A `public fun` that takes an `address` and changes the state stored there, without a signer or ownership check, lets anyone change anyone's state. Every mutating path needs an authorization check.

## Visibility

| Declaration | Callable from | Notes |
|---|---|---|
| `fun` | This module | Default; keep logic here and test it directly |
| `public(package) fun` (Move 2) or `public(friend) fun` with `friend` declarations | Modules in the same package, or named friends | Prefer package visibility in new code |
| `public fun` | Any module and any script | Signature is frozen by compatible upgrades; anyone can call it with any arguments they can construct |
| `entry fun` | Transactions only | Not composable from other modules; required for randomness |
| `public entry fun` | Both | Convenient, but composable by others |
| `#[view] public fun` | Off-chain reads | Must not change state |

Expose the smallest public surface. Every `public` function is an API other modules will call in ways you did not plan, and it cannot be removed in a compatible upgrade.

## Errors

- One `const E_...: u64` per failure reason, each with a `///` doc comment. Aptos tooling shows the comment as the error's description, so users and front ends get a readable message.
- Wrap reasons in `std::error` categories (`invalid_argument`, `out_of_range`, `invalid_state`, `permission_denied`, `not_found`, `already_exists`, ...). The resulting abort code is `category << 16 | reason`: `error::permission_denied(1)` aborts with `0x50001`. Tests must expect that full value.
- Abort early with `assert!` before any state change; Move rolls back the whole transaction on abort, but early checks keep gas low and code readable.

## Integers and arithmetic

- Unsigned integers from `u8` to `u256`. Overflow, underflow and division by zero abort; there is no silent wraparound. A cast such as `(x as u64)` aborts when the value does not fit.
- Multiply before dividing, and do it in a wider type: `((a as u128) * (b as u128) / (c as u128) as u64)`, or the framework's `mul_div` helpers. Decide the rounding direction explicitly so it favors the protocol (round shares down on deposit, up on withdrawal).
- There are no floats. Use basis points or the fixed-point modules in `aptos_std` for fractions.

## Generics and type arguments

- An entry function generic over a type (`deposit<CoinType>`) can be called with *any* type that satisfies the constraints, including one an attacker defines. If your logic assumes a particular asset, store the expected type or metadata object at initialization and check it on every call.
- Use `phantom` type parameters to keep, for example, pools for different assets apart at compile time.

## Patterns

- **Capability:** possession of a struct grants a permission (`MintCap has store`). Keep capabilities inside your module's resources; never return them from `public` functions.
- **Hot potato:** a struct with no abilities must be passed to a specific function before the transaction ends. Flash loans use this: `borrow` returns a receipt that only `repay` can consume.
- **Two-step ownership transfer** and **pause switch**, both emitting events.
- **Witness types** (a type only your module can construct, passed as proof) appear in some Aptos registration APIs; they are far more central in Sui Move.

## Style

- Name error constants consistently (`E_NOT_OWNER` or the framework's `ENOT_OWNER`), events in the past tense (`Deposited`), capabilities with a `Cap` suffix, and getters after the field they return.
- Keep entry functions thin: parse arguments, check authorization, call an internal function that does the work and is easy to test.
- Use the CLI's formatter and linter where your version provides them (`aptos move fmt`, `aptos move lint`; check `aptos move --help`), and treat new compiler warnings as failures in CI.
- Use the editor extension and language server that the Aptos documentation currently recommends. Language servers built for core Move or for Sui Move report false errors on Aptos syntax and framework code; when the editor and `aptos move compile` disagree, the compiler is right.
- Document every public function with `///`: who may call it, what it changes, when it aborts.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Mutating state at a caller-supplied address with no authorization | Require a signer or verify object ownership on every mutating path |
| Refs, signers or capabilities reachable through a `public` function | Keep them inside resources; expose narrow, checked operations instead |
| Expecting `init_module` to run on upgrade | A separate, admin-gated migration entry function |
| Generic entry function trusts its type argument | Check the type or metadata against stored configuration |
| Divide before multiply; `u64` intermediate overflow | Widen to `u128`, multiply first, choose rounding |
| Looping over a vector users can grow | Bounded batches, tables, or per-user storage |
| `timestamp` or block data used as randomness | The randomness API in a private entry function (`objects-and-tokens.md` covers mint use) |
| Bare numeric abort codes | Named constants with doc comments and error categories |

## Done when

- [ ] The package compiles on the pinned CLI with no new warnings; formatter and linter (where available) are clean.
- [ ] Every mutating function checks authorization; no public function exposes refs, signers or capabilities.
- [ ] Abilities are minimal and justified; every abort uses a named, documented constant.
- [ ] Arithmetic that can overflow or round is tested at its bounds.
