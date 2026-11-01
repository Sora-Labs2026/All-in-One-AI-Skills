# Swift concurrency in depth: Swift 6 and 6.2

Read this when Swift code hits data-race diagnostics, a target moves to the Swift 6 language mode, a project adopts the Swift 6.2 "approachable concurrency" settings, or you design shared mutable state (caches, stores, persistence) with actors. The concurrency basics (async/await, `@MainActor`, task groups, cancellation, reentrancy in one paragraph) are in `swift.md`; SwiftUI state and tests are in `swiftui-and-testing.md`.

## Versions and settings

| Release | What changed |
|---|---|
| Swift 5.10 (March 2024) | Complete strict-concurrency checking available as warnings (`-strict-concurrency=complete`) |
| Swift 6.0 (September 2024) | Swift 6 language mode: data-race safety errors; region-based isolation lets non-`Sendable` values cross boundaries when the compiler proves no sharing; `sending` parameters and results; typed throws; `Mutex` and `Atomic` in the Synchronization module (iOS 18, macOS 15 and later runtimes) |
| Swift 6.1 (March 2025) | `nonisolated` allowed on types and extensions |
| Swift 6.2 (September 2025, Xcode 26) | Opt-in defaults: main-actor isolation by default per module; `nonisolated async` functions run on the caller's actor (`nonisolated(nonsending)` by default) with `@concurrent` to request the global executor; isolated conformances (`extension Model: @MainActor Exportable`); isolated `deinit`; `Task.immediate`; task names |

The language mode and every upcoming feature are **per target**:

- **SwiftPM:** `swiftLanguageModes: [.v6]` in the package, and per target `swiftSettings: [.defaultIsolation(MainActor.self), .enableUpcomingFeature("NonisolatedNonsendingByDefault"), .enableUpcomingFeature("InferIsolatedConformances")]` (tools version 6.2 for `defaultIsolation`).
- **Xcode:** the Swift Language Version, Strict Concurrency Checking, Default Actor Isolation and Approachable Concurrency build settings. New app projects created with Xcode 26 turn on main-actor default isolation and approachable concurrency; older projects do not.

Before reasoning about where code runs, read these settings for the target. The same source means different things under different settings: with default main-actor isolation, an unannotated class is `@MainActor`; without it, it is nonisolated.

## Choosing settings for a target

| Target | Recommended |
|---|---|
| App or UI target, mostly single-threaded | Main-actor default isolation plus approachable concurrency; opt specific work out with `nonisolated` and `@concurrent` |
| Library or package used by others | Keep nonisolated by default; mark only UI-facing API `@MainActor`; enable `NonisolatedNonsendingByDefault` deliberately, since it changes where your async functions run for callers |
| Server-side Swift | Nonisolated default; actors for shared state; never block event-loop threads |

Change one setting at a time, build, fix, commit. Ask before switching a shared package's isolation defaults: it is a source-compatibility change for its users.

## Migration path

1. Turn on complete checking as warnings in the Swift 5 mode for one target. Fix warnings module by module, leaf modules first.
2. Annotate the obvious: UI types and their models `@MainActor`; value types `Sendable` (often inferred for non-public structs and enums whose stored properties are `Sendable`); shared mutable reference types become actors or main-actor types.
3. Use `@preconcurrency import` for dependencies that have not adopted `Sendable` yet; remove it when they do.
4. Switch the target to the Swift 6 language mode once it builds without warnings.
5. Where available, Swift 6.2's `swift package migrate --to-feature <Feature>` applies fix-its for an upcoming feature; review its diff like any other change.

## Diagnostics and the fix that matches

| Diagnostic (wording varies by version) | Usual cause | Fix |
|---|---|---|
| "Sending 'x' risks causing data races" | A non-`Sendable` value passed to another isolation domain while the sender keeps using it | Stop using it after sending (the compiler accepts a value it can prove is no longer shared); make the type `Sendable`; or keep the work in one isolation domain |
| "Main actor-isolated property 'x' can not be referenced from a nonisolated context" | Nonisolated code touching UI state | Make the caller `@MainActor`, or `await` the access from async code; `MainActor.assumeIsolated { }` only where the code provably already runs on the main thread (a UIKit callback), since it traps otherwise |
| "Static property 'shared' is not concurrency-safe because it is nonisolated global shared mutable state" | A `static var`, or a `static let` of a non-`Sendable` class | Isolate it (`@MainActor static let shared`), make the type an actor or `Sendable`, or use `let` for an immutable `Sendable` value |
| "Capture of 'self' with non-sendable type in a `@Sendable` closure" | Escaping closures run concurrently with the owner | Capture the needed `Sendable` values instead of `self`; make the owner main-actor isolated |
| "Conformance of 'Model' to protocol 'P' crosses into main actor-isolated code" | A main-actor type conforming to a nonisolated protocol | Swift 6.2 isolated conformance (`extension Model: @MainActor P`), or make the requirement `nonisolated` if it touches no isolated state |
| "Expression is 'async' but is not marked with 'await'" after adding an actor | Calls into an actor from outside are asynchronous | Add `await` and make the caller `async`; reconsider whether the state belongs on the caller's actor instead |

Escape hatches exist; each needs a comment saying why it is safe:

- `@unchecked Sendable` on a class whose state is guarded by a lock;
- `nonisolated(unsafe)` on a global or static that is set once before any concurrency;
- `@preconcurrency` on a conformance or import.

Adding them to silence errors moves the data race from compile time to production.

## Where code runs under 6.2 approachable concurrency

- An `async` function that is `nonisolated` runs on the caller's actor (no hop). Calling it from the main actor keeps it on the main actor, so its CPU work blocks the UI.
- Mark CPU-heavy functions `@concurrent` (they must be `nonisolated` and `async`) to run them on the global concurrent executor, and pass only `Sendable` values in and out:

```swift
nonisolated struct ThumbnailRenderer {
    @concurrent
    func render(_ original: Data, maxPixelSize: Int) async throws -> Data {
        // decoding, scaling and re-encoding run off the main actor
        try downscaledPNG(from: original, maxPixelSize: maxPixelSize)
    }
}
```

- Synchronous code never hops: a blocking call (file I/O, a large `JSONDecoder` pass, a synchronous network API) inside a main-actor function blocks the UI no matter what the settings are. Move it into a `@concurrent` async function or an actor.
- `Task { }` inherits the current actor and its priority; `Task.detached { }` inherits neither and is rarely the right tool. `Task.immediate { }` (6.2) starts running synchronously on the current actor until its first suspension.

## Actors for shared state and persistence

An actor serializes access to its state, so a cache or store becomes race-free by construction. Design points:

- **Keep the actor's API about the domain** (`save(_:)`, `item(id:)`, `all()`), not about storage, and return `Sendable` values (structs), never references to its internal collections.
- **Reentrancy:** at every `await` inside an actor method, other calls can run and change state. Complete the state change before the first suspension, or re-check after it; for "load once" logic, store the in-flight `Task` so concurrent callers await the same work:

```swift
actor ProfileStore {
    private var cache: [UserID: Profile] = [:]
    private var inFlight: [UserID: Task<Profile, Error>] = [:]

    func profile(for id: UserID, using api: ProfileAPI) async throws -> Profile {
        if let cached = cache[id] { return cached }
        if let running = inFlight[id] { return try await running.value }
        let task = Task { try await api.fetchProfile(id) }
        inFlight[id] = task
        defer { inFlight[id] = nil }
        let profile = try await task.value
        cache[id] = profile
        return profile
    }
}
```

- **Durable writes:** write files with `Data.write(to:options: .atomic)` so a crash never leaves a half-written file; decode with `try` and report failures instead of `try?`, which silently replaces a corrupt or newer-format file with empty data. Building dictionaries with `Dictionary(uniqueKeysWithValues:)` traps on duplicate keys from disk; use `Dictionary(_:uniquingKeysWith:)`.
- **Blocking I/O inside an actor** occupies a thread of the shared cooperative pool while it runs. Small files are fine; large reads and writes belong in a dedicated serial context or are split into chunks.
- **Not everything needs an actor:** a `Sendable` value type, a main-actor model, or a `Mutex` (Synchronization module, iOS 18 and later) around a small piece of state is simpler when no `await` is needed. Actors also make every call asynchronous, which spreads `async` through callers.
- **Persistence frameworks** have their own rules: SwiftData `ModelContext` and Core Data contexts are bound to one actor or queue; pass identifiers (`PersistentIdentifier`, `NSManagedObjectID`), not model objects, across isolation boundaries.

## Testing concurrent code

- Test actors through their public async API in `async` tests; assert on results, not on timing.
- Reproduce reentrancy and duplicate-work bugs by starting several calls together (`async let` or a task group) and checking the outcome (one network call made, consistent state).
- Run the tests with the Thread Sanitizer enabled in the scheme for code that still uses locks, GCD or `@unchecked Sendable`.
- Never `sleep` to wait for work; await the task, use a continuation or the testing framework's confirmation API.

## Done when

- [ ] The target builds in its configured language mode with no new concurrency warnings, and the report states the mode and the isolation settings.
- [ ] Every `@unchecked Sendable`, `nonisolated(unsafe)` and `@preconcurrency` added has a comment explaining why it is safe.
- [ ] CPU-heavy or blocking work does not run on the main actor; under 6.2 settings, it is in `@concurrent` functions or an actor.
- [ ] Actor methods do not assume state is unchanged across `await`; concurrent-call tests cover the critical paths.
- [ ] Persistence code fails loudly on decode errors and writes atomically.
