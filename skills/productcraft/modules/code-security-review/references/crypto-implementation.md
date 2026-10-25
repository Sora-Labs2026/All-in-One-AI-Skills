# Cryptographic implementation review

Reference for the `code-security-review` module. Class 9 in `vulnerability-classes.md` lists the misuse signals (weak algorithms, insecure randomness, TLS verification turned off) and their fixes; do not repeat that sweep here. This file goes one level deeper, for code that builds token formats, encrypts or signs data, handles keys, or implements cryptography itself: is the construction sound, does it leak secrets through timing, and do secrets stay in memory after use.

**Contents:** [Do not build it](#do-not-build-it) · [Checks when a library is used](#checks-when-a-library-is-used) · [Timing side channels](#timing-side-channels) · [Secrets in memory](#secrets-in-memory) · [Randomness beyond the API name](#randomness-beyond-the-api-name) · [Confirm and report](#confirm-and-report)

## Do not build it

Treat each of these as home-made cryptography:

- A new cipher, hash, MAC, key-derivation function or random generator.
- A custom protocol or token format: a hand-rolled "signed cookie", a JWT parser written in the project, a bespoke key-exchange handshake.
- Composing primitives by hand: CBC plus a separately computed MAC, `hash(key + message)` as a MAC, a CRC or checksum used for integrity, encrypting blocks one by one.
- Implementing a standard primitive (AES, curve arithmetic, big-number modular math) instead of calling a maintained library, even when following the specification.
- A hand-written constant-time comparison, padding check or encoding routine for secrets.

Replace, do not repair. Maintained high-level options: libsodium (`crypto_secretbox`, `crypto_box`, `crypto_sign`, `crypto_pwhash`), Google Tink, Python `cryptography` (`AESGCM`, `ChaCha20Poly1305`, `Fernet`), Go's `crypto/cipher` with GCM and `golang.org/x/crypto/chacha20poly1305`, .NET `AesGcm`, the Web Crypto API, RustCrypto's AEAD crates, `ring` or `aws-lc-rs`; for protocols, TLS 1.3 and maintained JOSE or PASETO libraries with the algorithm pinned.

A home-made construction protecting something valuable is a finding even before anyone shows a break; rate it by what it protects and recommend the library replacement. A project whose purpose is to implement cryptography (a crypto library, a wallet, a protocol) needs specialist review against published test vectors, and ideally formally verified or formally analyzed implementations. Record that as out of scope for this review rather than approving it.

## Checks when a library is used

| Check | What goes wrong | Look for |
|---|---|---|
| Authenticated encryption | CBC or CTR without a MAC can be modified in transit; padding errors become decryption oracles | AEAD modes (AES-GCM, ChaCha20-Poly1305); decryption that acts on plaintext before the tag is verified |
| Nonce uniqueness | A repeated nonce under one key breaks GCM and ChaCha20-Poly1305 completely: plaintexts leak and tags can be forged | Counters that reset on restart or are shared between instances; random 96-bit nonces used for more than about 2^32 messages per key (NIST SP 800-38D). XChaCha20-Poly1305 takes random nonces safely at scale; AES-GCM-SIV survives a repeat, revealing only whether two messages were equal |
| Context binding | Ciphertext copied from one user's record into another's decrypts fine | The record ID, owner and purpose go in the associated data |
| Key derivation and separation | One key for encryption, signing and tokens; a password used directly as a key | A password KDF (Argon2id, scrypt, PBKDF2 with a high iteration count) for passwords; HKDF with a distinct `info` label per subkey |
| Key storage and rotation | Keys in source, in the same database as the data, or with no identifier, so they cannot be rotated | Keys from a KMS or secrets manager, envelope encryption, a key ID stored with each ciphertext |
| Signature verification | Result ignored; the code verifies one byte string and then parses a different one; the message chooses the algorithm or the key (`alg`, embedded `jwk`, `x5u`); malleable signatures used as identifiers | Verify the exact bytes that are then parsed; pin algorithm and key; see class 3 for JWT |
| RSA | Textbook RSA, PKCS#1 v1.5 encryption padding, short keys | OAEP for encryption, PSS (or PKCS#1 v1.5) for signatures, at least 2048-bit keys, `e = 65537` |
| Elliptic curves | Peer public keys not validated (invalid-curve attacks) | Libraries usually validate; X25519 and Ed25519 APIs avoid the problem; protocols that need contributory key exchange reject an all-zero X25519 result |
| Hash use | Fast hashes for passwords; length extension on `SHA-256(secret \|\| message)`; MACs truncated below 128 bits | LaunchGuard control 10 for passwords; HMAC for keyed hashing |
| Compression | Compressing attacker-influenced data together with a secret before encryption leaks the secret through the ciphertext length (the CRIME and BREACH attacks) | Compression of mixed secret and user content inside encrypted channels |
| Error behavior | Different errors, codes or timings for bad padding and bad MAC give an oracle | One generic failure for every decryption or verification error |
| Test vectors | A wrapper that swaps arguments or encodings passes its own round-trip tests | Known-answer tests from RFCs or NIST CAVP, the Project Wycheproof edge-case suites, and negative tests where a flipped bit in ciphertext, tag or associated data must fail |

## Timing side channels

Comparing a secret against attacker input matters in every application (MACs, API keys, reset tokens, webhook signatures). Computing on keys matters to anyone implementing primitives. Code leaks timing when a secret decides:

1. **When a comparison stops.** `==` on strings or byte arrays, `memcmp`, `strcmp`, `Arrays.equals`, `bytes.Equal` and `===` stop at the first difference.
2. **Which branch runs or how often a loop runs.** `if (bit)`, secret-dependent loop counts, `switch` on secret values.
3. **Which memory is read.** Table lookups indexed by secrets (S-boxes, hex or base64 decoding tables) leak through the cache.
4. **How long an instruction takes.** Integer division and remainder (`div`, `idiv`, `sdiv`, `udiv`) take operand-dependent time on most processors; this was the KyberSlash problem in ML-KEM implementations. Some multiplies on small processors and floating point with subnormal values vary too.
5. **How long the data is.** Early exit on leading zeros, variable-length encodings, big-number normalization. Leaking the bit length of ECDSA nonces was enough to recover keys (the Minerva attacks).

The language's own primitives:

| Language | Constant-time equality | OS-backed random bytes | Best-effort wipe |
|---|---|---|---|
| C, C++ | `CRYPTO_memcmp` (OpenSSL), `sodium_memcmp` | `getrandom()`, `getentropy()`, `randombytes_buf()` | `explicit_bzero`, `memset_explicit` (C23), `sodium_memzero`, `OPENSSL_cleanse`, `SecureZeroMemory` (Windows) |
| Rust | `subtle::ConstantTimeEq` | `getrandom` crate, `rand::rngs::OsRng` | `zeroize` crate |
| Go | `crypto/subtle.ConstantTimeCompare`, `hmac.Equal` | `crypto/rand` | Overwrite the slice; the garbage collector may have copied it |
| Java, Kotlin | `MessageDigest.isEqual` | `SecureRandom` | `Arrays.fill` on `byte[]` or `char[]` |
| C# | `CryptographicOperations.FixedTimeEquals` | `RandomNumberGenerator` | `CryptographicOperations.ZeroMemory` |
| Python | `hmac.compare_digest` | `secrets` | No reliable option; overwrite a `bytearray` |
| JavaScript, TypeScript (Node.js) | `crypto.timingSafeEqual` (equal lengths only) | `crypto.randomBytes`, `crypto.getRandomValues` | `buffer.fill(0)` |
| PHP | `hash_equals` | `random_bytes`, `random_int` | `sodium_memzero` |
| Ruby | `OpenSSL.secure_compare`, `Rack::Utils.secure_compare` | `SecureRandom` | No reliable option |
| Swift | `HMAC.isValidAuthenticationCode` (CryptoKit) | `SecRandomCopyBytes`, `SystemRandomNumberGenerator` | Overwrite through `withUnsafeMutableBytes` |

Compare fixed-length values: HMAC both sides, or compare digests, so the length of the secret does not leak and length-checking APIs do not throw.

**Checking compiled code** (for code that computes on secrets, not for ordinary comparisons):

```sh
# Assembly for the file that handles secrets, at the levels the product might ship with
for o in O0 O2 O3 Os; do gcc -"$o" -S -o "secret-ops-$o.s" src/secret_ops.c; done
grep -nE '\b(i?div[bwlq]?)\b' secret-ops-*.s     # x86-64 divisions
grep -nE '\b(sdiv|udiv)\b' secret-ops-*.s        # AArch64, when built for that target
```

- For each division or conditional jump inside a function that handles secrets, decide where its operands come from. Lengths, block counts and loop bounds are public and harmless; anything computed from key material, nonces, plaintext or tokens makes it a finding.
- Do not count on the optimizer to turn a division into something safe. In a check with GCC 13 on x86-64, a division by a constant became a multiplication at `-O2` and remained an `idiv` at `-Os`. Replace it yourself with a multiplication by a precomputed constant and a shift, and show that the two agree on every possible input (cheap for 16- and 32-bit values); spot checks miss a reciprocal that is off by one.
- Compilers can turn branch-free source into branches and back. Check the shipped compiler, version, flags and target, and repeat after every change.

**Dynamic checks**

- **Valgrind memcheck:** mark the secret as undefined with `VALGRIND_MAKE_MEM_UNDEFINED(key, key_len)` from `<valgrind/memcheck.h>`, run the operation under `valgrind`, and every branch or memory index that depends on the secret is reported as depending on uninitialized data. Mark public outputs defined again (`VALGRIND_MAKE_MEM_DEFINED`) before using them.
- **Statistical timing tests:** time many runs with two input classes (a fixed secret against random secrets) and compare the distributions with Welch's t-test. A |t| that stays above 4.5 as samples grow (the usual leakage-assessment threshold) suggests a leak; some tools wait for 10 before calling it certain. Such tests can show a leak but cannot prove there is none, and noisy shared machines hide small leaks.

Every timing result belongs to one toolchain, flag set and processor family. Write those down with the result, and do not extend a clean result to other builds.

## Secrets in memory

Secrets left in memory reach attackers through memory-disclosure bugs (Heartbleed returned up to 64 KiB of server memory per request), core dumps and crash reports, swap and hibernation files, and debuggers attached to the process. Wipe long-term keys, session keys and seeds, passwords and PINs after use, decrypted sensitive records, and intermediate buffers such as key schedules.

**C and C++**

1. **`memset` before `free` or return is a dead store, and compilers delete it.** In a check with GCC 13 and Clang 18 at `-O2`, `memset(key, 0, sizeof key)` disappeared both for a stack buffer and before `free`, while `explicit_bzero` stayed. Use `explicit_bzero` (glibc 2.25+, the BSDs), `memset_explicit` (C23), `SecureZeroMemory` (Windows), `sodium_memzero` or `OPENSSL_cleanse`. `memset_s` (C11 Annex K) is rarely available.
2. **Wipe the right size:** the object or allocation size, not `sizeof` of a pointer and not `strlen` of a buffer that may contain zero bytes.
3. **Wipe on every exit:** error returns, `goto cleanup` paths, early returns in loops and C++ exceptions. In C++, hold secrets in a type whose destructor wipes.
4. **Track copies:** struct assignment and pass-by-value; `realloc`, which may move the data and free the old block unwiped (allocate, copy, wipe the old block, free it); `std::string` and `std::vector` growth and small-string buffers. Do not keep secrets in `std::string`.
5. **Keep secrets out of swap and dumps when the threat model needs it:** `mlock` (subject to `RLIMIT_MEMLOCK`), `madvise(MADV_DONTDUMP)`, `prctl(PR_SET_DUMPABLE, 0)`, `setrlimit(RLIMIT_CORE, ...)` set to zero, or libsodium's `sodium_malloc` with guard pages.
6. **Know the limits:** copies in registers, spilled stack slots in callees, kernel buffers and library-internal copies are out of reach. Wiping shortens the exposure window; it does not close it. Check the assembly (`-O2 -S`) that the wipe call is still present.

**Rust**

- Use the `zeroize` crate (`Zeroize`, `#[derive(Zeroize, ZeroizeOnDrop)]`, `Zeroizing<T>`) and the `secrecy` crate (`SecretBox`, `SecretString`), which hides values from `Debug` and requires an explicit `expose_secret()`.
- `#[derive(Copy)]` or `Clone` on a key type creates copies nobody wipes; `#[derive(Debug)]` or `Serialize` sends the secret to logs and responses.
- Moves are byte copies that leave the old bytes in place. Keep secrets behind a pointer (`Box<[u8; 32]>` inside `Zeroizing`) so a move copies only the pointer.
- `Vec` and `String` growth reallocates and frees the old buffer unwiped; allocate the final capacity first.
- `mem::forget`, `Box::leak`, `ManuallyDrop`, reference cycles, `std::process::exit` and `panic = "abort"` all skip destructors; secrets in statics are never dropped.
- Other silent copies: a secret held across an `.await` lives in the future's state, which is moved around and freed without wiping unless the type wipes itself; `mem::take`, `mem::swap`, `Cow::into_owned` and `From` conversions into plain `Vec` or `String` move the bytes out of the wiping type.

**Managed runtimes** (Java, Kotlin, C#, Go, JavaScript, Python): the garbage collector moves and copies objects and strings are immutable. Keep secrets in byte or char arrays and overwrite them, prefer keys that never enter the process (KMS, HSM, OS keystore), and state plainly in the report that in-process wiping is best effort.

Searches to start from:

```sh
rg -n -e 'memset\s*\([^;]*(key|secret|passw|seed|priv|token)' -t c -t cpp .
rg -n -B2 -e 'struct\s+\w*(Key|Secret|Password|Seed|Token)\w*' -t rust . | rg 'derive\(.*(Debug|Clone|Copy|Serialize)'
```

## Randomness beyond the API name

Class 9 covers which generator to call. The implementation can still go wrong:

- **Modulo bias:** `random_byte % n` is biased unless `n` divides 256. Use the library's range function: `secrets.randbelow`, `random_int`, `crypto.randomInt`, `SecureRandom.nextInt(bound)`, Go's `rand.Int(rand.Reader, max)`, Rust's `gen_range` on `OsRng`.
- **Seeding:** a user-space generator seeded from the time, the process ID or a constant left over from tests.
- **Fork and snapshot:** a user-space generator's state copied by `fork()` or a virtual-machine snapshot produces the same numbers twice. Ask the operating system for each value, or use a library that reseeds after fork.
- **Ignored failures:** `getrandom()` and `RAND_bytes()` can fail; code that ignores the result, or falls back to `rand()` when `/dev/urandom` cannot be opened, ships predictable keys.
- **Signature nonces:** an ECDSA nonce that repeats, or is biased by even a few bits, reveals the private key. Let the library generate it (RFC 6979 deterministic or hedged nonces); never pass in your own.
- **Token strength:** bearer tokens need at least 128 bits from a CSPRNG. Version 4 UUIDs carry 122 random bits, which is enough only if the implementation uses a CSPRNG; time-based UUIDs (versions 1, 6, 7) are not secrets.

## Confirm and report

- **Timing:** confirmed by a source trace showing a secret operand plus compiled output showing the variable-time instruction or branch in the shipped configuration, or by a statistical test. Say what was shown; do not dismiss a leak because the attacker is remote, since remote timing attacks have been demonstrated many times.
- **Memory:** show the missing or deleted wipe (an assembly excerpt or the source path where the secret survives) and the exposure route assumed (dumps, swap, a disclosure bug). Usually `LOW` or `MEDIUM` alone; higher when combined with a confirmed disclosure bug or crash dumps shipped to a third party.
- **Construction:** name the property lost (confidentiality, integrity, authenticity) and who can exploit it. A local test showing that a modified ciphertext is accepted, or that two records swap without detection, is enough proof.
- Fix by moving to the library primitive or API from the tables above, add the negative test, and search for the same helper elsewhere.
