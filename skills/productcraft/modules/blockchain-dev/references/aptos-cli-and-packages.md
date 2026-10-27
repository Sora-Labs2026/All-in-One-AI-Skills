# Aptos CLI, packages, publishing and upgrades

Read this when installing the Aptos CLI, creating profiles, editing `Move.toml`, compiling, publishing to a network, deploying to an object address, upgrading a package or running a local network. The CLI changes often and has renamed commands before (for example the local network command); check `aptos --version` and `aptos <command> --help` before relying on a flag here.

## Install and pin

- Install with a package manager (for example `brew install aptos`) or a release binary from the official releases, verified against its published checksum. Record the version in the README and CI.
- The official install script works, but read it before running it, and never pipe a downloaded script straight into an interpreter (`../../agent-safety/GUIDE.md`, remote code).
- `aptos update aptos` upgrades the CLI in place; that changes the compiler too, so treat it like a dependency upgrade and ask first.

## Profiles and keys

- `aptos init --network devnet --profile dev` (or `local`, `testnet`) generates a key pair and writes it, **with the private key in plain text**, to `.aptos/config.yaml` in the current folder. Add `.aptos/` to `.gitignore` *before* running it, and never print or open that file.
- To keep keys out of project folders entirely, switch to the global config location (`aptos config set-global-config --config-type global`), which stores profiles in the home folder.
- Refer to accounts by profile name in commands (`--profile dev`). The agent never needs to see a key.
- Funding: `aptos account fund-with-faucet --profile dev` works on devnet and localnet. Testnet funding goes through the web faucet, which the user does. Mainnet funds belong to the user and are never moved by the agent.
- For mainnet authority, use a hardware-wallet profile (`aptos init --ledger`) or the user's wallet, never a key file on a development machine, and hold admin and upgrade rights in an on-chain multisig account the owner sets up.

## `Move.toml`

```toml
[package]
name = "my_app"
version = "1.0.0"
upgrade_policy = "compatible"

[addresses]
my_app = "_"            # filled in at compile or publish time

[dev-addresses]
my_app = "0xCAFE"       # used by tests and dev builds only

[dependencies.AptosFramework]
git = "https://github.com/aptos-labs/aptos-core.git"
rev = "<commit hash>"   # or a release tag; network branch names move
subdir = "aptos-move/framework/aptos-framework"
```

- Use named addresses everywhere in code (`module my_app::counter`), never a literal hex address, so the same source publishes to any account or object.
- Pin `rev` to a commit or tag. Branch names such as `main`, `mainnet` or `devnet` move, so builds stop being reproducible and an audit no longer matches what you deploy. Match the framework revision to the network you deploy to.
- `upgrade_policy` is `compatible` (the default; upgrades must keep compatibility) or `immutable` (no upgrades). A package can move to a stricter policy later, never back.

## Compile, test and publish

```bash
aptos move compile --named-addresses my_app=dev
aptos move test --coverage
aptos move publish --named-addresses my_app=dev --profile dev
```

- Named addresses accept a profile name (`my_app=dev`) or an explicit address.
- Publishing to an account ties the package to that account's key. **Object code deployment** publishes to a fresh object address instead (`aptos move deploy-object --address-name my_app --profile dev`, upgraded later with the matching upgrade command); upgrade rights then follow ownership of that object, which can be transferred to a multisig. Command names have changed between CLI versions; check `aptos move --help`.
- Resource accounts are the older way to get a deterministic protocol address; prefer objects in new code.
- Large packages can exceed the transaction size limit; recent CLIs can split publishing into several transactions. Check for the option in `aptos move publish --help`.
- Call functions with typed arguments: `aptos move run --function-id 'dev::counter::increment' --profile dev`, and read with `aptos move view --function-id 'dev::counter::value' --args address:0x...`. Argument prefixes include `u64:`, `address:`, `string:`, `bool:`, `hex:` and vectors such as `'u64:[1,2,3]'`.
- The CLI asks you to confirm gas before submitting. Do not add `--assume-yes` unless the user asked for that exact command, and never on mainnet.

## Upgrades

- Under the `compatible` policy the network checks each upgrade: existing structs keep their layout, and existing public and entry functions keep their signatures; new modules, structs and functions may be added. Read the current rules in the Aptos documentation before planning a change that is close to the line.
- Compatible does not mean harmless. An upgrade can change what existing functions *do*, so users rely on whoever holds upgrade rights. Put those rights behind a multisig or governance and consider moving to `immutable` once the package is stable.
- `init_module` does not run on upgrade. Add an admin-gated migration entry function and a version field in your configuration resource, and make the migration idempotent.
- Rehearse every upgrade on a test network with state shaped like production's, then run the invariant tests against the migrated state.

## Local network

- `aptos node run-localnet` (older CLIs: `run-local-testnet`) runs a node and faucet; the indexer API option needs Docker. Restart options wipe the local chain, which is fine locally and nowhere else.
- Create a `local` profile with `aptos init --network local --profile local`.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `.aptos/config.yaml` committed or shown | Ignore `.aptos/` first; use the global config location; rotate any exposed key and move funds |
| Framework dependency on a moving branch | Pin a commit or tag that matches the target network |
| Literal hex module addresses | Named addresses with `_` and `[dev-addresses]` |
| Package published under a developer's personal account | Object deployment or a dedicated deployer account controlled by a multisig |
| Expecting `init_module` to run on upgrade | Gated, idempotent migration function |
| `--assume-yes` added to publish or run commands | Let the user confirm; never automatic on mainnet |

## Done when

- [ ] The CLI version is pinned and recorded; `.aptos/` (or the key location in use) is gitignored and no key file is tracked (`move_check.py` clean for key files).
- [ ] `Move.toml` uses named addresses, a pinned framework revision and an explicit upgrade policy.
- [ ] The package was compiled, tested and published on a local or test network, and the commands are written down.
- [ ] The owner has decided who holds upgrade and admin rights for mainnet and how upgrades are rehearsed.
