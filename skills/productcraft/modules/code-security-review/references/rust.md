# Rust security review

Reference for the `code-security-review` module. Read it when the scope contains Rust: services, libraries published for others, command-line tools, FFI layers, WebAssembly modules. Safe Rust rules out use after free, data races and unchecked indexing, but not logic flaws, panics, silent integer wraparound, deadlocks, or undefined behavior hidden behind `unsafe` and FFI. General classes are in `vulnerability-classes.md`; comparing secrets and wiping keys are in `crypto-implementation.md`.

Tools named here are optional. Run them only on the local checkout. Building or checking a crate runs its build scripts and procedural macros, so treat an untrusted repository as code that will execute (see [supply chain](#supply-chain)).

**Contents:** [What the compiler proves](#what-the-compiler-proves) · [Map the crate](#map-the-crate) · [Unsafe code](#unsafe-code) · [FFI](#ffi) · [Panics](#panics) · [Integers and casts](#integers-and-casts) · [Concurrency and async](#concurrency-and-async) · [Other traps](#other-traps) · [Supply chain](#supply-chain) · [Confirm and fix](#confirm-and-fix)

## What the compiler proves

| Proven for safe code | Not proven |
|---|---|
| No use after free, double free or dangling references | That `unsafe` blocks keep the invariants safe code relies on |
| No data races on shared memory | Deadlocks, lock ordering, atomics used with the wrong ordering |
| Every index is bounds-checked | That an out-of-bounds index, `unwrap` or overflow does not panic and take down a request or the process |
| Values are initialized before use | That integer arithmetic does not wrap in release builds |
| | That FFI declarations match the foreign code |
| | Authorization, validation and business logic |

Decide the attacker. For a network service, any panic reachable from a request is a denial-of-service candidate. For a library, the public safe API must be sound for every input any safe caller can supply, including strange trait implementations. For a CLI, the inputs are files and arguments.

## Map the crate

```sh
rg -c -t rust '\bunsafe\b' . | sort -t: -k2 -nr | head -20          # where unsafe concentrates
rg -n -t rust -e 'unsafe\s+impl' -e 'extern\s+"C' -e '#\[(unsafe\()?no_mangle' \
  -e '\btransmute' -e 'from_raw_parts' -e '\.set_len\(' -e 'MaybeUninit' -e 'static\s+mut' -e 'get_unchecked' .
rg -c -t rust -e '\.unwrap\(\)' -e '\.expect\(' -e 'panic!\(' -e 'unreachable!\(' -e 'todo!\(' src/
rg -n -e 'overflow-checks' -e '^panic\s*=' -e '^edition' -g 'Cargo.toml' .
rg -n -e 'forbid\(unsafe_code\)' -e 'deny\(unsafe_op_in_unsafe_fn\)' -t rust .
```

- `#![forbid(unsafe_code)]` in a crate root means that crate has no `unsafe`; dependencies may still have it. `cargo geiger`, if installed, counts `unsafe` across the dependency tree.
- Note the edition (2024 makes several unsafe operations explicit), the release profile's `overflow-checks` and `panic` settings, and the minimum supported Rust version.

## Unsafe code

**Soundness rule.** A safe function must not be able to cause undefined behavior for any argument a safe caller can pass, including panicking closures, inconsistent `Ord` or `Hash` implementations, iterators whose `size_hint` lies and `Read` implementations that return wrong counts. An `unsafe fn` must state what callers have to guarantee in a `# Safety` doc section. Each `unsafe { }` block should carry a `// SAFETY:` comment explaining why those conditions hold. A missing comment is a lead; a comment that does not match the code is a candidate finding.

For each `unsafe` block: write the invariant down, find where it is established, and look for every way it can be broken before it is relied on, including a panic in between and a caller-supplied trait method.

| Pattern | What goes wrong | Check |
|---|---|---|
| `mem::uninitialized()`, `mem::zeroed()`, `MaybeUninit::assume_init()` | Undefined behavior when the value is not valid for its type (references, `NonNull`, `Box`, function pointers and enums without a zero discriminant are never valid as all zeros) or not fully written | Every byte is initialized before `assume_init`; zeroed only for types where all-zero is valid |
| `Vec::with_capacity` then `set_len` | Elements exposed before they are written; a panic in between drops garbage | Write first, then `set_len`; or use `spare_capacity_mut` |
| `get_unchecked`, pointer `add` or `offset` | Out of bounds; pointer arithmetic past the allocation is undefined even without a read | The index is proven in range on every path |
| `slice::from_raw_parts(ptr, len)` | Wrong length, misaligned or NULL pointer (undefined even for length 0), lifetime longer than the owner | Pointer, length, alignment and lifetime all come from the same live allocation |
| Unbounded lifetimes | `&*ptr` gets whatever lifetime inference picks, often `'static` | Tie the lifetime to the owner in the signature |
| Aliasing | `&mut` created from `&` (`&mut *(r as *const T as *mut T)`), or two live `&mut` to the same data | Interior mutability goes through `UnsafeCell` (or `Cell`, `RefCell`, atomics, locks) |
| `ptr::read`, `Box::from_raw`, `Vec::from_raw_parts` | Double drop when the original is also dropped; wrong capacity or allocator | Ownership moves exactly once; `mem::forget` or `ManuallyDrop` the original |
| `transmute` | Different size, alignment or validity; `repr(Rust)` layouts are unspecified; `&T` to `&mut T`; integers to `bool`, `char` or enums with invalid values | Use `from_ne_bytes`, `TryFrom`, or the checked casts of `bytemuck` or `zerocopy` |
| `#[repr(packed)]` | References to unaligned fields | Rejected by current compilers (E0793); read with `ptr::read_unaligned` or copy the field out |
| `union` | Reading a field that was not the last one written, when it is invalid for that type | A tag or invariant decides which field is active |
| Panic safety | A panic while an invariant is temporarily broken, inside unsafe code that calls user code (`clone`, comparators, callbacks) | A guard type restores the invariant in its `Drop` |
| `unsafe impl Send` or `Sync` | The type holds `Rc`, `Cell`, raw pointers to thread-unsafe data; a generic `unsafe impl<T> Send for W<T>` without a `T: Send` bound | Each impl states why sharing across threads is sound |
| `static mut` | Unsynchronized global state | Rust 2024 denies references to it (`static_mut_refs`); use atomics, `Mutex`, `OnceLock` or `LazyLock` |

**Tools**

- **Miri** runs tests in an interpreter that detects undefined behavior: out-of-bounds access, use after free, invalid values, aliasing violations, some data races, memory leaks. `rustup +nightly component add miri`, then `cargo +nightly miri test`. It is slow and cannot run most foreign function calls, so point it at the unit tests of the unsafe modules.
- **Sanitizers** (nightly): `RUSTFLAGS="-Zsanitizer=address" cargo +nightly test --target x86_64-unknown-linux-gnu`; the explicit `--target` is required.
- **Fuzzing:** `cargo fuzz` harnesses for every parser or decoder reachable from untrusted input; setup, structured inputs and crash triage are in `../../engineering-practices/references/fuzzing.md`. Record run time and coverage; a short clean run is weak evidence.
- **Clippy:** `cargo clippy --all-targets -- -W clippy::undocumented_unsafe_blocks -W clippy::multiple_unsafe_ops_per_block -W clippy::unwrap_used -W clippy::indexing_slicing -W clippy::arithmetic_side_effects -W clippy::cast_possible_truncation`. On a large crate, run the restriction lints only on the modules in scope.
- **`loom`** model-checks concurrent code when the project already uses it.

## FFI

- **Declarations must match the foreign headers exactly.** C `long` is 32 bits on 64-bit Windows; use `core::ffi::c_long` and friends, `usize` for `size_t`, and generated bindings (`bindgen`) kept in sync with the headers. Rust 2024 requires `unsafe extern` blocks, which makes this surface easy to find.
- **No Rust enums for values from C.** C can pass any integer, and an invalid discriminant is undefined behavior. Take the integer and convert with a `match` or `TryFrom`.
- **Layout:** every shared struct is `#[repr(C)]`; padding bytes may carry stale data when a struct is copied out to C.
- **Strings:** `CString::new(s)` fails on an interior NUL, so `unwrap` turns user input into a panic. `CString::new(s)?.as_ptr()` in one expression dangles as soon as the temporary is dropped; current compilers warn (`dangling_pointers_from_temporaries`). `CStr::from_ptr` needs a valid, NUL-terminated pointer for as long as it is used. C strings are not UTF-8: `to_str()` can fail and `to_string_lossy()` changes the data, so security comparisons on lossy strings can disagree with what C sees.
- **Ownership and allocators:** memory allocated in Rust is freed in Rust (`Box::into_raw` paired with `Box::from_raw` in an exported `*_free` function), memory from C is freed with the C library's `free`. Never mix allocators. Check every pointer C hands over for NULL and every length for range.
- **Panics at the boundary:** since Rust 1.81, a panic unwinding out of an `extern "C"` function aborts the whole process; older compilers had undefined behavior. A library embedded in another program should wrap each exported function in `std::panic::catch_unwind` and return an error code. Use `extern "C-unwind"` only when the foreign side is built to handle unwinding.
- **Callbacks:** nullable C function pointers are `Option<extern "C" fn(...)>`. A closure passed through a `*mut c_void` user-data pointer must outlive every call (`Box::into_raw`, freed on unregister). Trait objects are fat pointers and cannot cross as a single `void *`; box them twice.
- **Thread safety:** a wrapper around a C object that is not thread-safe must not be `Send` or `Sync`.
- **Descriptors:** `from_raw_fd` takes ownership, so two owners close twice; use `OwnedFd` and `BorrowedFd`.

## Panics

A panic reachable from untrusted input is a denial-of-service candidate. Severity depends on what it kills:

- **The process:** `panic = "abort"` in the release profile, a panic in the main thread or in a thread nobody joins and restarts, a panic while already panicking, a panic in `Drop` during unwinding, a panic across FFI, stack overflow from deep recursion, and allocation failure (all abort and cannot be caught).
- **A task or request:** Tokio catches a panic at the task boundary and returns it as a `JoinError`, but a `std::sync::Mutex` held during the panic is poisoned, and later `lock().unwrap()` calls panic in turn.
- **A library caller:** a library that panics on bad input forces its users to treat every call as a crash risk. Return `Result`, and document intentional panics under `# Panics`.

Look for these on paths from untrusted input:

- `unwrap()` and `expect()` on parsing and conversion: `str::parse`, `from_utf8`, `serde_json::from_slice`, `try_into`, `CString::new`.
- Indexing and slicing with input-derived values: `v[i]`, `&buf[start..end]`, and string slices that cut through a multi-byte UTF-8 character.
- Division or remainder by an input-derived zero; `RefCell` borrowed twice through re-entrant calls; `Instant + Duration` and `Duration` arithmetic overflow (use `checked_add`).
- Sizes from input: `Vec::with_capacity(n)`, `vec![0; n]`, `String::with_capacity(n)` with an attacker's `n`. Cap the size before allocating.
- Recursion over nested input (custom parsers, tree walkers, recursive `Drop` of long linked structures, `Debug` printing of deep trees). `serde_json` limits nesting to 128 levels by default; check that the limit is not disabled and that other parsers have one.
- `assert!` on input-derived conditions. Conversely, `debug_assert!` disappears in release builds, so it must never be the only guard for a security check.
- Sorting with a comparator that is not a total order, such as `partial_cmp(...).unwrap()` over floats that can be NaN. Since Rust 1.81 the standard sorts may panic when the comparator is inconsistent.

## Integers and casts

- **Overflow:** debug builds panic, release builds wrap silently unless `[profile.release] overflow-checks = true`. Tests that run in debug therefore pass while production wraps; an optimized build turns `255u8 + 1` into `0`. Lengths, offsets, balances, quotas and timestamps use `checked_*` (handle `None`), `saturating_*` where clamping is the right answer, or `wrapping_*` where wrap is intended (hashes, sequence numbers). For services, consider turning `overflow-checks` on in release: a panic is better than a wrong balance.
- **`as` never fails:** `300i32 as u8` is `44`, `-1i32 as u32` is `4294967295`, `f64::NAN as u8` is `0`, and out-of-range floats saturate. Use `u8::try_from(x)?` for narrowing and `u64::from(x)` for lossless widening. Flag `as usize`, `as u32` and `as i32` applied to values that come from input.
- **Pointer width:** `usize` is 32 bits on 32-bit and `wasm32` targets; a 64-bit length from a wire format truncates there.

## Concurrency and async

- **Deadlocks:** locks taken in different orders on different paths; locking a `std::sync::Mutex` again on the same thread (it is not re-entrant); a guard living longer than it looks because it sits in a `match` scrutinee. Drop guards explicitly before calling out.
- **Blocking in async code:** `std::fs`, `std::thread::sleep`, synchronous database drivers and CPU-heavy work such as password hashing inside an async task stall a runtime worker for everyone. Move them to `spawn_blocking` or a dedicated pool.
- **Guards across `.await`:** holding a `std::sync::Mutex` guard across an `.await` can deadlock the executor; use `tokio::sync::Mutex` when a lock must be held across awaits, or restructure.
- **Cancellation:** `tokio::select!`, timeouts and dropped connections drop futures at any `.await`. A handler cancelled after debiting and before crediting, or after reading a length and before reading the body, leaves state half-done. Check every branch inside `select!` for cancel safety (the Tokio documentation marks which methods are cancel-safe), and keep multi-step state changes in a transaction or a spawned task that runs to completion.
- **Atomics:** a `Relaxed` store of a flag that publishes other data needs `Release` on the writer and `Acquire` on the reader. Load-then-store sequences race; use `compare_exchange` or `fetch_*`.

## Other traps

- **Paths:** `Path::new("/srv/uploads").join(name)` returns `name` itself when `name` is absolute, and `..` is not resolved. Accept only `Component::Normal` parts, or open files relative to a directory handle; `canonicalize` plus `starts_with` still races (class 6).
- **Check-then-use on files:** `path.exists()` followed by `File::create` races; use `OpenOptions::new().write(true).create_new(true)`. Rust 1.58.1 fixed a symlink race in `std::fs::remove_dir_all` (CVE-2022-21658); check the toolchain version for programs that delete directories as a privileged user.
- **Serde input types:** add `#[serde(deny_unknown_fields)]` to request structs and keep privileged fields out of them (class 11); `#[serde(default)]` can silently fill a missing security field; `#[serde(untagged)]` enums may match an unexpected variant.
- **Map order:** `HashMap` iteration order is random per process. Hashing, signing or comparing data built by iterating a `HashMap` gives different bytes on each run; use `BTreeMap` or sort first.
- **`Hash`, `Eq` and `Ord` must agree.** Inconsistent implementations, or keys mutated through interior mutability after insertion, make lookups miss, which matters for allow-lists and permission caches.
- **Dropped errors:** `let _ = ...` on `send`, `flush`, `sync_all` or a verification call; `BufWriter` dropped without `flush()`, which loses the error. Treat silenced `#[must_use]` warnings as leads.
- **Environment:** `std::env::set_var` and `remove_var` are `unsafe` in Rust 2024 because they race with C code reading the environment; in older editions the race still exists.
- **Addresses in output:** printing pointers (`{:p}`, `as usize`) in errors or responses hands attackers memory addresses, which helps them bypass address randomization when a memory bug exists elsewhere in the process.
- **Shell through Command:** `Command::new("sh").arg("-c").arg(format!(...))` brings shell injection back; call the real program and pass each argument separately.
- **Decoders that trust length prefixes:** binary formats such as `bincode` allocate whatever a length field claims; set size limits, and cap nesting depth for recursive formats.

## Supply chain

- `build.rs` scripts and procedural macros run arbitrary code at build time. `cargo build`, `cargo check`, `cargo test` and IDE analysis by rust-analyzer all execute them. Build untrusted crates only in isolation (`../../agent-safety/references/isolation.md`).
- For each new dependency, read its `build.rs` and proc-macro crates, check how much `unsafe` it adds, and look at its maintainers and release history (`secrets-and-dependencies.md`).
- `cargo audit` (RustSec advisories; fetching the database needs network access) and `cargo deny check` (advisories, yanked versions, licenses, sources, duplicates), if installed. Binaries commit `Cargo.lock`; `cargo install --locked` uses it.

## Confirm and fix

- **Unsound API:** a small test that uses only safe code and makes Miri report undefined behavior confirms it (`TESTED_LOCAL`). Quote the Miri error.
- **Panic:** an integration test that sends the crafted input and asserts an error response instead of a crash, red before the fix.
- **Overflow:** test boundary values with `cargo test --release`, because debug builds panic where release builds wrap.
- **Fix patterns:** validate before entering `unsafe`; keep `unsafe` in small modules whose invariants are documented and tested under Miri; replace `unwrap` with `?` and typed errors; checked arithmetic and `TryFrom`; limits on sizes and depth; `catch_unwind` at FFI entry points. Then search for the same pattern across the crate and its workspace.
