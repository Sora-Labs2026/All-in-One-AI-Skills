# Language choice: offering Rust

Some work is a good fit for Rust: it runs fast, uses little memory and catches many bugs at compile time. It also costs more to write: compiles are slower, the code is longer, and an AI agent usually needs more fix-and-compile rounds, which means more tokens and more time. The user should make that trade knowingly, so ProductCraft asks before choosing it.

## When to ask

Ask **once** when all of these hold:

1. The task starts a new project, a new service or backend, or a new performance-critical component (for example image or video processing, parsing, search and indexing, cryptography, simulation, real-time data).
2. The language is not already fixed by the existing codebase, the project instructions or the user.
3. The user has not answered this already in this session, and no answer is recorded in `CLAUDE.md` or `AGENTS.md`.

Do **not** ask for edits to existing code, small features, styling or copy changes, or quick prototypes. If an existing app in another language has a measured performance problem in one hot path, you may offer Rust for that path only.

## How to ask

Ask before writing code, in one short message, with the benefit stated for this specific case. Use the client's question tool if it has one. Template:

> Do you want **[component]** written in Rust?
> - **Faster at runtime:** [the concrete benefit here, such as lower latency and memory for this API, or faster image processing in the browser via WebAssembly].
> - **Slower to build:** Rust compiles more slowly and takes longer to write, so each change takes longer to try.
> - **More AI usage:** Rust code is longer and usually needs more compile-and-fix rounds, so expect more tokens and time.
> - **Page load:** Rust does not make pages load faster by itself; that depends mostly on image and script size, caching and the network.
>
> Options: **Rust for [component]** · **Keep [current or simpler stack]** · **Decide later**

Recommend the option that fits. Recommend Rust when the benefit is real and measurable. Recommend the simpler stack when the work is bound by the network or database, or is mostly UI.

## Where Rust helps and where it rarely does

| Usually worth it | Rarely worth it |
|---|---|
| High-traffic or latency-sensitive APIs and services (for example Axum or Actix Web on Tokio) | Interface code that mostly manipulates the DOM; JavaScript and TypeScript frameworks have far larger ecosystems |
| CPU-heavy work in the browser through WebAssembly (`wasm-bindgen`, `wasm-pack`) | CRUD apps whose time is spent waiting on the database or network |
| Background workers, CLIs and data pipelines | Static or marketing sites, where load speed comes from assets, caching and a CDN |
| Desktop apps that need small, fast binaries (for example Tauri) | Prototypes and experiments, where iteration speed matters most |
| Edge functions on platforms that run Rust or WebAssembly | Teams that will maintain the code without Rust experience |

To make a site **load** faster, first apply the usual levers: smaller images in modern formats, code splitting, caching and a CDN, server rendering and fewer third-party scripts.

## If the answer is Rust

- Keep Rust where it pays. Put the hot path in a separate service or a WebAssembly module behind a small interface, and keep the UI in the project's existing framework unless the user wants everything in Rust.
- Use established crates (for example `tokio`, `axum`, `serde`, `sqlx`, `wasm-bindgen`) and the standard tooling: `cargo fmt`, `cargo clippy`, `cargo test`.
- Keep the development loop fast. Use `cargo check` while iterating, split code into smaller crates, and build `--release` only for measurements and production.
- For WebAssembly, keep the bundle small (`wasm-opt`, lazy loading) so the module does not slow the first page load.
- Measure before and after with real workloads, and report the numbers and the build-time cost honestly.

## If the answer is no

Continue with the existing or simpler stack, apply the normal performance guidance, and do not ask again in this project.

## Remember the answer

Keep the answer for the rest of the session. Offer to record it in the project's `CLAUDE.md` or `AGENTS.md` (for example "Language: TypeScript; do not offer Rust" or "Use Rust for the image pipeline"), so future sessions follow it without asking again.
