# Swift

Read this before writing or changing Swift: packages, iOS and macOS app code, SwiftUI views, server-side Swift. Concerns every mobile app shares (configuration, offline sync, deep links, push, store releases) are in `mobile-cross-platform.md`; mobile security review is in `../../code-security-review/references/mobile-apps.md`; interface quality and accessibility go through ProductCraft's UI modules.

## Orient first

- **Package or Xcode project:** `Package.swift` (Swift Package Manager; its first line, `// swift-tools-version:6.0`, sets the minimum toolchain), or an `.xcodeproj`/`.xcworkspace` (build settings live in the project file or `.xcconfig` files). Many apps are an Xcode project plus local packages.
- **Toolchain and language mode:** `swift --version` and the Xcode version in CI. Swift 6 (September 2024) introduced the Swift 6 language mode with complete data-race checking; projects can stay in Swift 5 mode per target (`swiftLanguageModes` in packages, `SWIFT_VERSION` in Xcode) and enable checks gradually (`StrictConcurrency`, upcoming-feature flags). Swift 6.2 (September 2025) added options that change defaults, such as main-actor isolation by default for app targets. Read the target's settings before reasoning about isolation.
- **Deployment targets** (`platforms:` in `Package.swift`, `IPHONEOS_DEPLOYMENT_TARGET`) decide which APIs exist: for example the Observation framework (`@Observable`) needs iOS 17 and macOS 14. Guard newer APIs with `if #available`.
- **Lint and format:** SwiftLint (`.swiftlint.yml`) or swift-format (`.swift-format`; shipped with Swift 6 toolchains as `swift format`).

```bash
swift build
swift test                                    # SwiftPM packages
xcodebuild -list                              # schemes in an Xcode project
xcodebuild test -scheme App -destination 'platform=iOS Simulator,name=<installed simulator>'
swiftlint lint --strict <changed files>       # if configured
```

## Language idioms

- Value types (`struct`, `enum`) by default; classes for identity, shared mutable state behind an actor, or framework requirements. Standard collections are copy-on-write, so passing them around is cheap.
- Enums with associated values for closed sets of states, handled with exhaustive `switch`.
- Optionals: `guard let` for early exit, `if let` for scoped use, `??` for defaults. Force unwrap (`!`) and `try!` only for programmer errors that cannot happen at runtime, such as a literal URL.
- Errors: `throws` with specific error enums; typed throws (`throws(ParseError)`, Swift 6) where callers benefit from an exhaustive catch. Do not convert errors to optionals (`try?`) where the reason matters.
- Protocols with generics: prefer `some Protocol` (opaque, statically dispatched) for parameters and returns; use `any Protocol` (an existential box) only for heterogeneous storage.
- `Codable` for JSON with explicit `CodingKeys` or decoder strategies (`keyDecodingStrategy`, `dateDecodingStrategy`) matching the API; decode into DTOs, not directly into view models.
- Access control: `private` and `fileprivate` by default for helpers, `internal` within a module, `public` only for a package's API.

## Concurrency

- `async`/`await` for asynchronous work; wrap callback APIs once with `withCheckedThrowingContinuation`, and resume the continuation exactly once on every path (resuming twice crashes, never resuming leaks the task).
- **Isolation:** UI state and UIKit or SwiftUI calls are `@MainActor`. Mutable shared state lives in an `actor` (or behind a lock in a `final class` marked `@unchecked Sendable` with a comment saying why). Types crossing isolation boundaries are `Sendable`.
- **Actor reentrancy:** inside an actor method, state can change across every `await`. Re-check assumptions after awaiting, or complete the state change before the first `await`.
- **Structured concurrency:** `async let` for a fixed number of parallel calls, `withThrowingTaskGroup` for a dynamic number; child tasks are cancelled when the parent fails. `Task { }` inherits the current actor; `Task.detached` does not, and is rarely needed.
- **Cancellation is cooperative:** long loops call `try Task.checkCancellation()`; keep a handle to unstructured tasks and cancel them when their owner goes away. SwiftUI's `.task { }` modifier cancels automatically when the view disappears.
- Fix concurrency warnings by modeling ownership (move state into an actor, make a type `Sendable`, mark main-actor code), not by adding `@preconcurrency`, `nonisolated(unsafe)` or `@unchecked Sendable` everywhere. Each such escape needs a comment explaining why it is safe.

## Memory

- ARC frees objects when the last strong reference goes. Cycles leak: a class holding a closure that captures `self` strongly, delegates held strongly, timers and notification observers retaining their targets.
- Capture `[weak self]` in escaping closures stored by the object or a long-lived service, then `guard let self else { return }`. `unowned` only when the captured object provably outlives the closure.
- Delegate properties are `weak var delegate: SomeDelegate?` (the protocol must be class-constrained).
- Find leaks with Xcode's Memory Graph debugger or Instruments' Leaks and Allocations templates.

## SwiftUI state

| Wrapper | Owns or references | Use for |
|---|---|---|
| `@State` | Owns, private to the view | Simple view-local values; also owning an `@Observable` model the view creates |
| `@Binding` | References a parent's value | Child controls that edit parent state |
| `@Observable` class (iOS 17+) | Model object; views track only the properties they read | Screen and app models |
| `@Bindable` | Bindings into an `@Observable` object | Forms editing a model |
| `@Environment` | Shared values injected from above | App-wide services, settings, observable models passed down |
| `@StateObject` / `@ObservedObject` with `ObservableObject` | Pre-iOS 17 equivalents | Projects targeting older systems |

- A view's `body` is called often: no heavy work, no side effects, no network calls in it. Load data in `.task { }` or in the model.
- Give list rows stable identities (`Identifiable` with a real ID, not array indices), or rows animate and keep state incorrectly.
- Keep business logic in models or services that unit tests can drive without the UI.
- Previews use sample data and in-memory services; never live credentials.

## Testing

- XCTest or Swift Testing (`import Testing`, `@Test`, `#expect`, `#require`; included with Xcode 16 and Swift 6 toolchains). Follow the framework the target uses; both can coexist in one target.
- Async tests are `async` functions; await the result instead of sleeping or using expectations with arbitrary timeouts.
- Inject dependencies through protocols or closures so tests replace network, storage and clocks.
- UI tests (XCUITest) are slow and flaky by nature; cover critical flows only, with accessibility identifiers rather than labels.
- Snapshot tests if the project already has a library for them; review image diffs, never re-record blindly.

## Server-side Swift

- Vapor and Hummingbird run on SwiftNIO event loops: never block them with synchronous I/O, `sleep` or heavy CPU work. Use async database drivers and offload CPU work.
- Database access through the framework's ORM or driver (Fluent, PostgresNIO) with migrations reviewed like any other (`../../engineering-practices/references/data-and-migrations.md`).
- Build release binaries in a container that matches the deployment OS. The Foundation library on Linux differs from Apple's in places, so run tests on Linux in CI.

## Distribution notes

- Signing, provisioning profiles, App Store Connect uploads and TestFlight releases are the user's steps; prepare the build and the notes, and do not submit.
- Apps that use certain system APIs need a privacy manifest (`PrivacyInfo.xcprivacy`) and usage descriptions in `Info.plist`; App Store review checks them. Data collection must match the privacy declarations (`../../legal-ready/GUIDE.md`).

## Done when

- [ ] `swift build`/`swift test` or the scheme's `xcodebuild test` passed on an available simulator or platform, and SwiftLint or swift-format passed where configured.
- [ ] No new concurrency warnings in the target's language mode; every `@unchecked Sendable`, `nonisolated(unsafe)` or `@preconcurrency` has a written justification.
- [ ] Newer APIs are guarded for the deployment target.
- [ ] Escaping closures and delegates do not create retain cycles.
- [ ] Nothing was signed, uploaded or submitted without the user.
