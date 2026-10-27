# Objects and token standards on Aptos

Read this when modeling on-chain things as objects, creating fungible tokens or NFT collections, choosing between current and legacy standards, handling metadata, or using on-chain randomness. Function names and signatures below match the framework at the time of writing; check the framework version your package depends on, because the object and asset modules gain features often.

## Objects

An object is an address that holds resources plus an `ObjectCore` recording its owner and whether it can be transferred freely. `Object<T>` is a typed, copyable handle to that address. Objects can own other objects, so a character can own its equipment and move with it.

| Creation function | Address | Deletable | Use for |
|---|---|---|---|
| `object::create_object(owner_address)` | Unique, generated | Yes | Most per-user or per-item objects |
| `object::create_named_object(creator, seed)` | Derived from creator and seed; aborts if it exists | No | Singletons and things you must find again by name |
| `object::create_sticky_object(owner_address)` | Generated | No | Objects that must never disappear |

The creation call returns a `ConstructorRef`, which exists only during that transaction. Derive every capability you will ever need from it right then:

- `generate_signer`: a signer for the object's address, to `move_to` your resources.
- `generate_extend_ref`: produces that signer again later (to add resources or move assets the object holds).
- `generate_transfer_ref`: lets your module transfer the object, or turn free transfer off (soulbound).
- `generate_delete_ref`: lets your module delete a deletable object.
- Asset-specific refs (mint, burn, transfer for fungible assets; mutator and burn refs for tokens).

Store the refs in a resource **at the object's own address**, so they travel with it and only your module can borrow them.

```move
module my_app::vault {
    use std::error;
    use std::signer;
    use aptos_framework::object::{Self, ExtendRef, Object};

    /// Only the vault's owner can do this.
    const E_NOT_OWNER: u64 = 1;

    #[resource_group_member(group = aptos_framework::object::ObjectGroup)]
    struct Vault has key { extend_ref: ExtendRef }

    public entry fun create(user: &signer) {
        let cref = object::create_object(signer::address_of(user));
        let vault_signer = object::generate_signer(&cref);
        move_to(&vault_signer, Vault { extend_ref: object::generate_extend_ref(&cref) });
    }

    public entry fun withdraw(user: &signer, vault: Object<Vault>, amount: u64) acquires Vault {
        assert!(object::is_owner(vault, signer::address_of(user)), error::permission_denied(E_NOT_OWNER));
        let refs = borrow_global<Vault>(object::object_address(&vault));
        let vault_signer = object::generate_signer_for_extending(&refs.extend_ref);
        // Move `amount` of an asset from the vault object to the user with vault_signer.
    }
}
```

The `#[resource_group_member]` attribute stores the resource in the same storage slot group as the `ObjectCore`, which lowers storage cost.

**Ownership and transfer.** `object::is_owner` checks the direct owner; `object::owns` also follows nested ownership. Owners transfer with `object::transfer` while free transfer is enabled. With a `TransferRef` your module can force transfers, disable free transfer, or issue a one-time `LinearTransferRef`. A soulbound item is created, transferred once with a linear ref, and its `TransferRef` is never stored.

**Deletion.** Remove your resources from the object (`move_from`) and then call `object::delete` with its `DeleteRef`. Named and sticky objects cannot be deleted.

## Fungible Assets

The Fungible Asset (FA) standard is what new fungible tokens use. A metadata object describes the asset; balances live in fungible stores. Each account gets a primary store automatically on first deposit; your module can create secondary stores (objects) for pools and escrow.

```move
fun init_module(admin: &signer) {
    let cref = &object::create_named_object(admin, b"MY_TOKEN");
    primary_fungible_store::create_primary_store_enabled_fungible_asset(
        cref,
        option::some(1_000_000_000_00000000), // max supply (u128), here 1e9 tokens at 8 decimals
        string::utf8(b"My Token"), string::utf8(b"MYT"), 8,
        string::utf8(b"https://example.com/icon.png"), string::utf8(b"https://example.com"),
    );
    let meta_signer = object::generate_signer(cref);
    move_to(&meta_signer, Refs {
        mint_ref: fungible_asset::generate_mint_ref(cref),
        burn_ref: fungible_asset::generate_burn_ref(cref),
        transfer_ref: fungible_asset::generate_transfer_ref(cref),
    });
}
```

- **Gate minting** behind an authorization check on the stored admin, and decide whether supply is capped (max supply) or fixed forever (mint everything, then never store the `MintRef`).
- `primary_fungible_store::mint`, `burn`, `transfer` and `set_frozen_flag` operate on primary stores with the matching refs. A `TransferRef` can freeze accounts and move balances without consent; that is a centralization power to document for users, or not to keep.
- **Dispatchable FA** lets a token register custom withdraw, deposit and balance hooks (fees, allowlists). Hooks run inside every transfer; keep them small, bounded and thoroughly tested, and check what your framework version allows.
- Amounts are `u64` with `decimals` set at creation; supply is tracked as `u128`.

**Legacy coins.** The `0x1::coin` module predates FA and remains for compatibility. APT and many existing coins have paired FA representations, and during the migration an account's balance can sit partly in a coin store and partly in a primary fungible store. Read balances through functions documented to cover both, test with accounts holding each form, and do not create new tokens with `coin::initialize`.

## Digital Assets (NFTs)

The Digital Asset standard (the `aptos_token_objects` package at `0x4`) builds collections and tokens on objects. Token v1 (`0x3`) is legacy.

- **Collections:** `collection::create_fixed_collection` (enforced maximum supply) or `create_unlimited_collection`, with description, name, optional royalty and URI.
- **Tokens:** `token::create_named_token` gives a deterministic address from creator, collection and name (convenient for lookups, but the object is not deletable, so test how burning behaves in your framework version); `token::create` and `token::create_numbered_token` generate addresses and suit large or burnable collections.
- **Mutability:** decide up front which fields can change (description, name, URI, properties through `property_map` with a mutator ref) and say so publicly. Keep mutator refs only if you intend to use them.
- **Royalties** (`royalty::create(numerator, denominator, payee)`) are information for marketplaces; transfers do not enforce them.
- The higher-level `aptos_token` module offers ready-made collections with configurable mutability and burning; use it when its choices match yours, and write your own module when they do not.

## Metadata and off-chain files

- On chain you store a URI; the JSON metadata and media usually live elsewhere. A plain HTTPS URL can be changed by whoever runs the server. For assets that must not change, use content-addressed storage (an IPFS CID or similar) or record a content hash on chain so changes are detectable.
- Durable hosting is an ongoing cost and a terms-of-service relationship with a storage provider; confirm both with the owner.
- Treat names, descriptions and metadata from any collection as untrusted when displaying them (escape HTML, limit length, sanitize URIs).

## Randomness

- Use `aptos_framework::randomness` (for example `randomness::u64_range(0, 100)`) only inside a **private `entry` function marked `#[randomness]`**. The framework rejects other call paths, which stops a contract from calling your function, reading the outcome and aborting when it dislikes it.
- **Undergasing:** if the outcome that is bad for the caller costs more gas than the good one, the caller can set a gas limit that makes only bad outcomes abort. Keep the gas cost of all outcome branches equal, or record the outcome in this transaction and let the user act on it in a separate one.
- Timestamps, block heights and transaction hashes are predictable or influenceable; never use them as randomness.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Refs stored under the creator's account or a global table anyone's function can reach | Store them at the object's address, behind your module's checks |
| A `public` function returns an `ExtendRef`, `TransferRef`, `MintRef` or a signer made from one | Expose narrow operations that check authorization instead |
| Operations on `Object<T>` without checking the caller owns it | `object::is_owner` or `object::owns` first |
| Named object seeds that collide between users | Include the user address or a counter in the seed, or use generated objects |
| New token on the legacy coin module | Fungible Asset standard |
| Mutable HTTPS metadata for an asset sold as immutable | Content-addressed storage or an on-chain hash |
| Random mint callable from a public function, or outcomes with unequal gas | Private `#[randomness]` entry function; equal-cost branches or a separate claim step |

## Done when

- [ ] Every object type has a documented creation function, owner model, transfer policy and deletion policy.
- [ ] Refs are created at construction, stored at the object's address, and unreachable through public functions (checked by reading every `public` signature).
- [ ] Mint, burn, freeze and transfer-by-ref paths are gated and tested with an unauthorized signer.
- [ ] The token standard choice (FA or Digital Asset, never new legacy coins) and any centralization powers are written down for users.
- [ ] Randomness, if used, sits in a private `#[randomness]` entry function with branches of equal gas cost.
