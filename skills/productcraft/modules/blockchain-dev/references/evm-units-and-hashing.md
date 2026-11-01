# EVM client code: units, decimals, hashing and encoding

Read this when writing or reviewing off-chain code (TypeScript, JavaScript or Python) that reads from or writes to Ethereum and other EVM chains: balances and amounts, token decimals, prices, Keccak hashes, function selectors and event topics, addresses, ABI encoding and signed messages. Contract-side bugs are in `../../code-security-review/references/smart-contracts.md` and `../../code-security-review/references/defi-protocol-security.md`. The module guardrails apply: test networks first, no keys in the chat, no investment advice.

Library versions this file assumes (check the project's lockfile): ethers v6 (since 2023; v5 used `BigNumber` and `ethers.utils.*`, v6 uses native `bigint` and top-level functions), viem 2.x, web3.py 6 or 7. Node 18 or later.

## Amounts are integers in base units

- 1 ether is 10^18 wei, 1 gwei is 10^9 wei. ERC-20 balances are integers in the token's base unit; `decimals()` only tells user interfaces where to put the point. It is optional metadata in the ERC-20 standard, and contracts never use it.
- Keep amounts as integers end to end, and convert to and from display strings only at the edge (user input, rendering). Serialize them as decimal strings in JSON and databases; `JSON.stringify` throws on `bigint`, and JSON numbers lose precision above 2^53.
- JavaScript numbers are exact only up to 2^53 - 1 (about 9 x 10^15), smaller than one ether in wei. `parseFloat`, `Number()`, `1e18`, `Math.pow(10, d)` and `toFixed` on amounts are bugs. Use `bigint`: `10n ** BigInt(decimals)`.
- Python `int` is exact. `Decimal` uses 28 significant digits by default, so `Decimal(2**256 - 1) / Decimal(10**18)` silently rounds; raise the context precision (`getcontext().prec = 80`) or format from integers with `divmod`.

| Task | ethers v6 | viem 2.x | web3.py |
|---|---|---|---|
| Display string to base units | `parseUnits("1.5", 6)` returns `1500000n` | `parseUnits("1.5", 6)` | `int(Decimal("1.5") * 10**6)` after checking the digit count; `Web3.to_wei(Decimal("1.5"), "ether")` for ether units only |
| Base units to display string | `formatUnits(1500000n, 6)` returns `"1.5"` | `formatUnits(1500000n, 6)` | `Web3.from_wei(v, "ether")` returns a `Decimal`; for tokens, use `divmod(v, 10**d)` |
| Ether shortcuts | `parseEther`, `formatEther` | `parseEther`, `formatEther` | `to_wei`, `from_wei` |

Input with more fractional digits than the token supports is rejected by some libraries and rounded by others. Test what yours does, and reject such input in the UI rather than rounding silently. `../scripts/evm_check.py units` converts exactly and refuses to round.

## Decimals: read them, key them, test them

- Read `decimals()` per `(chainId, tokenAddress)`, never per symbol. The same symbol can have different decimals on different chains (USDC has 6 on Ethereum mainnet, while some bridged or pegged versions elsewhere use 18), and one chain can host several tokens with the same symbol (a native and a bridged version).
- A token whose `decimals()` reverts or returns something odd (old pre-standard tokens; some return `bytes32` for `name` and `symbol`) is an unknown, not 18. Exclude it from totals or require a value set by the operator, and log it.
- Prices from feeds have their own decimals (many USD feeds use 8). Compute value in integers: `amount * price / 10**(tokenDecimals + feedDecimals - outDecimals)`, rounding down when crediting a user and up when charging one.
- Know the fixed-point convention in the contract you call: WAD is 10^18, RAY is 10^27, and some protocols use 10^6 or basis points.
- Test with tokens of 0, 2, 6, 8, 18 and 24 decimals, and with balances near `2**256 - 1`.

## Keccak-256 is not SHA3-256

Ethereum hashes with the original Keccak-256. The NIST FIPS 202 standard, SHA3-256, changed the padding, so every output differs. Node's `crypto.createHash('sha3-256')` and Python's `hashlib.sha3_256` are FIPS SHA3 and wrong for selectors, topics, storage slots, typed-data hashes and addresses. Nothing warns you.

| Language | Correct Keccak-256 |
|---|---|
| TypeScript or JavaScript | `keccak256` from ethers or viem; `keccak_256` from `@noble/hashes/sha3` |
| Python | `eth_utils.keccak` or `eth_hash`; `Crypto.Hash.keccak.new(digest_bits=256)` from pycryptodome |

Test vector to put in the project's tests: Keccak-256 of the empty input is `0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470`; SHA3-256 of the empty input is `0xa7ffc6f8...f8434a`. `python3 ../scripts/evm_check.py hash "" --expect <digest>` tells you which one a codebase produced.

Text and bytes are different inputs. In ethers v6, `keccak256` takes bytes, so hash text with `keccak256(toUtf8Bytes("hello"))` or `id("hello")`; a `0x`-prefixed string is read as bytes. In viem, use `keccak256(toBytes("hello"))` or `keccak256(toHex("hello"))`.

## Selectors, topics and errors

- A function selector is the first 4 bytes of the Keccak-256 of the canonical signature: no spaces, no parameter names, full type names (`uint256`, not `uint`), tuples written as `(type,type)`. `transfer(address,uint256)` is `0xa9059cbb`, `balanceOf(address)` is `0x70a08231`, `approve(address,uint256)` is `0x095ea7b3`.
- An event's topic 0 is the full hash: `Transfer(address,address,uint256)` is `0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef`. ERC-20 and ERC-721 `Transfer` share topic 0; ERC-721 has the token ID indexed, so its log has four topics instead of three. Decode by ABI and topic count.
- Indexed `string`, `bytes` and array parameters appear in topics as their hash; the original value cannot be read back from the log.
- Revert data starts with `0x08c379a0` for `Error(string)`, `0x4e487b71` for `Panic(uint256)`, or a custom error's selector. Decode with the contract's ABI.
- Four bytes collide. Never treat a selector as proof of which function or contract you are talking to.

`../scripts/evm_check.py selector` and `topic` canonicalize a signature and print the hash offline, so hard-coded constants can be checked.

## ABI encoding and storage slots

- `abi.encode` pads each static value to 32 bytes; `abi.encodePacked` concatenates tightly and collides when there are two dynamic arguments. Off-chain code must use the same one as the contract: ethers `AbiCoder.defaultAbiCoder().encode` versus `solidityPacked`, viem `encodeAbiParameters` versus `encodePacked`.
- A mapping value with a value-type key lives at `keccak256(abi.encode(key, slot))`; with a `string` or `bytes` key the key is not padded: `keccak256(bytes(key) ++ uint256(slot))`. A dynamic array's elements start at `keccak256(slot)`.
- Namespaced storage (ERC-7201) uses `keccak256(abi.encode(uint256(keccak256(id)) - 1)) & ~bytes32(uint256(0xff))`.
- Read raw storage with `eth_getStorageAt` (or `cast storage`) on a test network to confirm a computed slot before relying on it.

## Addresses

- An address is the last 20 bytes of the Keccak-256 of the uncompressed public key without its `0x04` prefix. `CREATE` addresses come from the sender and nonce; `CREATE2` addresses from `keccak256(0xff ++ sender ++ salt ++ keccak256(initCode))`.
- EIP-55 checksums encode a check in the letter case. Validate mixed-case input and reject a mismatch; all-lower or all-upper input carries no checksum, so decide whether you accept it and always display the checksummed form. `../scripts/evm_check.py checksum` checks both.
- Compare addresses as bytes or lowercase strings, never by raw string equality.
- The same address can hold different contracts, or none, on different chains. Key every address by chain ID.

## Signed messages and chain IDs

- Personal messages (EIP-191) are hashed as `"\x19Ethereum Signed Message:\n" + byteLength + message`; use `hashMessage` and `verifyMessage` from the library.
- Typed data (EIP-712): build the domain (name, version, chain ID, verifying contract) and types with the library (`TypedDataEncoder` in ethers, `hashTypedData` or `verifyTypedData` in viem); never hand-roll the encoding. Include a nonce and an expiry, and check both on the server.
- Smart-contract wallets sign through ERC-1271: verify with `isValidSignature`, which returns `0x1626ba7e` when valid; viem's `verifyMessage` on a public client handles both kinds.
- Sign-in with Ethereum (EIP-4361) messages are checked server-side for domain, nonce, issued-at and expiry.
- Never ask a user to sign opaque hex. Show what is being signed.
- Before sending, compare the provider's `eth_chainId` with the configured chain; EIP-155 signatures bind a transaction to one chain, but a client pointed at the wrong RPC still sends to the wrong one.

## Helper script

`../scripts/evm_check.py` is standard-library only, offline and read-only, and never prints file contents.

```bash
python3 <productcraft>/modules/blockchain-dev/scripts/evm_check.py hash "" --expect 0xa7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a
python3 <productcraft>/modules/blockchain-dev/scripts/evm_check.py selector "function approve(address spender, uint amount)"
python3 <productcraft>/modules/blockchain-dev/scripts/evm_check.py topic "event Transfer(address indexed from, address indexed to, uint256 value)"
python3 <productcraft>/modules/blockchain-dev/scripts/evm_check.py checksum 0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed
python3 <productcraft>/modules/blockchain-dev/scripts/evm_check.py units 1.5 --decimals 6
python3 <productcraft>/modules/blockchain-dev/scripts/evm_check.py scan --root . --fail-on medium
```

`scan` lists leads in JavaScript, TypeScript and Python: FIPS SHA3 where Keccak is needed, float conversions and float scale factors on amounts, and hard-coded decimals. Leads are not findings; read the code and add a test. Exit codes: 0 success, 1 invalid checksum, refused conversion or a lead at or above `--fail-on`, 2 usage error.

## Done when

- [ ] No floating-point arithmetic touches amounts; amounts are stored and sent as integer strings.
- [ ] Decimals are read per chain and token address, unknowns are handled explicitly, and tests cover several decimal values.
- [ ] The project's hash helper passes the empty-input Keccak vector, and `evm_check.py scan` shows no high leads.
- [ ] Hard-coded selectors and topics match `evm_check.py` output.
- [ ] Addresses are validated with EIP-55 and compared by value; typed-data signing goes through the library with nonce, expiry and chain ID checked.
