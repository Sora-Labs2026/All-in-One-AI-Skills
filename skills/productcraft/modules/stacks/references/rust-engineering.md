# Rust engineering

Read this before writing or changing Rust: services, libraries, CLIs, WebAssembly modules. It covers how to build Rust well. Reviewing Rust for vulnerabilities (unsafe soundness, FFI, panics as denial of service, integer casts, supply chain) is `../../code-security-review/references/rust.md`; whether to choose Rust at all is `../../language-choice.md`; fuzzing is `../../engineering-practices/references/fuzzing.md`.

## Orient first

- **`Cargo.toml`:** `edition` (2015, 2018, 2021 or 2024; 2024 needs Rust 1.85, February 2025), `rust-version` (the minimum supported Rust version, MSRV), `[workspace]` members and `[workspace.dependencies]`, `[features]`, and any `build.rs`.
- **`rust-toolchain.toml`** pins the channel and components; `rustup` honors it automatically. Do not change it to get a newer feature.
- **`Cargo.lock`** is committed for binaries, and current Cargo guidance is to commit it for libraries too. Never delete it to "fix" a build.
- Lints and style: `[lints]` tables in `Cargo.toml` (Rust 1.74+), `clippy.toml`, `rustfmt.toml`, `deny.toml` for cargo-deny. Follow what is there.
- Building runs `build.rs` and procedural macros, which execute arbitrary code. Read them before building an untrusted repository.

## Commands

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings   # match the flags CI uses
cargo test --workspace            # or cargo nextest run, if the project uses it
cargo doc --no-deps               # broken intra-doc links show here
cargo +<msrv> check               # when the project declares rust-version and CI tests it
cargo deny check                  # or cargo audit, if configured
```

Use `cargo check` in the inner loop; full builds and `--release` only for tests that need them and for measurements.

## Ownership idioms

- **Borrow in parameters, own in results.** Take `&str`, `&[T]`, `&Path` or `impl AsRef<Path>`; return `String`, `Vec<T>`, `PathBuf`. Take ownership (`String`, `Vec<T>`) only when the function stores the value.
- Clone deliberately at a boundary, not to silence the borrow checker in the middle of an algorithm. A clone of an `Arc` is cheap; a clone of a large `Vec` is not.
- When the borrow checker objects, restructure before reaching for `Rc<RefCell<T>>`: shorten the borrow's scope, split a struct so disjoint fields are borrowed separately, store indices into a `Vec` instead of references, or pass the data in instead of holding it.
- `Cow<'_, str>` for functions that usually return their input unchanged.
- A `T: 'static` bound means "owns its data or holds only static references", not "lives forever"; owned types such as `String` satisfy it.
- Shared state across threads: `Arc<Mutex<T>>` or `Arc<RwLock<T>>`; global lazily initialized values with `std::sync::LazyLock` (1.80) or `OnceLock` (1.70) instead of `lazy_static`.

## Errors

| Crate kind | Error style |
|---|---|
| Library | A public error enum with `thiserror`, one variant per failure a caller can act on, `#[non_exhaustive]` so adding variants is not breaking; preserve sources with `#[source]` or `#[from]` |
| Application or binary | `anyhow` or `eyre` with `.context("loading config from {path}")` at each layer; convert to user-facing messages at the top |

- Propagate with `?`; add context where the call site knows something the error does not (which file, which ID).
- `unwrap()` belongs in tests and in places where failure is impossible by construction; there use `expect("why this cannot fail")`. In request paths, a panic is an outage for that request or the whole task.
- Do not use `Box<dyn Error>` in a library's public API; callers cannot match on it.

## Traits, generics and API design

- Generic parameters (`fn f<T: Read>(r: T)` or `impl Read`) are monomorphized: fast, larger binaries, longer compiles. Trait objects (`&dyn Read`, `Box<dyn Read>`) use a vtable: one copy of the code, a pointer indirection. Use trait objects for heterogeneous collections, plugin points and to cut compile time in big generic code.
- A trait used as `dyn` must be dyn-compatible (formerly "object safe"): no generic methods, no `Self` by value in signatures unless `where Self: Sized`.
- Public types implement the common traits that make sense: `Debug`, `Clone`, `PartialEq`/`Eq`, `Hash`, `Default`, `Display` for user-facing values, `serde` derives behind a feature flag in libraries.
- Use newtypes for identifiers and units (`struct UserId(Uuid)`, `struct Cents(i64)`) so they cannot be swapped by accident (`../../engineering-practices/references/spec-and-units.md`).
- Make invalid states unrepresentable with enums; prefer a builder or a constructor that validates over public fields with invariants.
- Features are additive: enabling a feature must never remove API or change behavior for other users of the crate. Test the combinations CI cares about (`cargo hack --feature-powerset check` if available).
- Published crates follow semver; `cargo semver-checks` catches accidental breaking changes before a release.

## Async with Tokio

- **Never block a runtime worker:** `std::thread::sleep`, synchronous file or network I/O, a blocking database client, CPU-heavy loops. Use `tokio::time::sleep`, async libraries, `tokio::task::spawn_blocking` for blocking calls and `rayon` (via `spawn_blocking` or a channel) for CPU work.
- **Locks across `.await`:** holding a `std::sync::Mutex` guard across an `.await` makes the future non-`Send` and can deadlock. Scope the guard so it drops before the await, or use `tokio::sync::Mutex` when the lock must be held across awaits.
- **Cancellation is dropping.** Any future can be dropped at an `.await`, for example by `tokio::select!` or a timeout. Code between awaits that leaves state half-updated is a bug under cancellation; check the "cancel safety" notes of methods used in `select!` loops.
- Many tasks: `tokio::task::JoinSet`; bound concurrency with a `Semaphore`; every task either ends on its own or listens to a `tokio_util::sync::CancellationToken` for shutdown.
- Timeouts on every outbound call: `tokio::time::timeout(dur, fut).await`.
- `async fn` in traits is stable since 1.75 for static dispatch; for `dyn Trait` with async methods, the `async-trait` crate (boxing) is still the usual answer.
- Do not create a runtime inside library code; let the application own it.

## Testing

- Unit tests in a `#[cfg(test)] mod tests` beside the code; integration tests in `tests/` against the public API; doc examples in `///` comments run as doctests, so keep them compiling.
- `#[tokio::test]` for async tests; `tokio::time::pause()` with `start_paused = true` makes timer-driven code deterministic.
- Property tests with `proptest` for parsers, encoders and arithmetic; snapshot tests with `insta` for large structured output, reviewed with `cargo insta review`.
- Benchmarks with `criterion` (or `divan`), compared across runs, never a single number.
- Unsafe code gets Miri runs on its unit tests (`cargo +nightly miri test`), as described in the security reference.

## Performance and compile times

- Measure in `--release`. Profile with `cargo flamegraph` or `perf`; check allocations with a heap profiler such as `dhat`.
- Common wins: avoid needless `clone()` and `collect()` in hot paths, preallocate with `with_capacity`, pass slices instead of `Vec`, use `&str` keys or interned IDs, and pick a faster hasher only for trusted keys (the default SipHash resists hash flooding).
- Release profile knobs, measured one at a time: `lto = "thin"` or `"fat"`, `codegen-units = 1`, `panic = "abort"` (changes unwinding behavior), `opt-level`.
- Compile time: split large crates, trim heavy generic or macro use in hot spots, use `cargo build --timings` to find slow crates, `sccache` for CI caching, and a faster linker (mold or lld) on Linux.

## Unsafe and FFI

- Crates that need no `unsafe` declare `#![forbid(unsafe_code)]`.
- Keep `unsafe` in small modules with a safe API, a `// SAFETY:` comment on every block and tests under Miri. The review checklist is in the security reference.
- Bindings: `bindgen` (C to Rust), `cbindgen` (Rust to C headers), `cxx` for C++ with a checked bridge, PyO3 or napi-rs for Python and Node extensions.

## Edition 2024 notes

Migrate with `cargo fix --edition`, then set `edition = "2024"` and review the diff. Changes most likely to need hand edits: `extern` blocks become `unsafe extern`, attributes such as `no_mangle` are written `#[unsafe(no_mangle)]`, references to `static mut` are denied, the scope of temporaries in `if let` and tail expressions shrinks, return-position `impl Trait` captures all in-scope lifetimes, and `gen` is reserved. Cargo's resolver 3 prefers dependency versions compatible with `rust-version`.

## Done when

- [ ] `cargo fmt --check`, `cargo clippy` with the CI flags, and `cargo test` pass for the workspace members touched.
- [ ] Code compiles at the declared `rust-version` when the project tests its MSRV.
- [ ] No `unwrap()` in non-test paths without an `expect` message stating why it cannot fail; library errors are typed.
- [ ] Async code has no blocking calls on runtime threads and no lock guards held across `.await`.
- [ ] New `unsafe` has a `SAFETY` comment, a safe wrapper and the security reference's checks; dependency changes passed `cargo deny` or `cargo audit`, or are marked `NOT VERIFIED`.
