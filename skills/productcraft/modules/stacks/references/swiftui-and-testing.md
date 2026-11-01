# SwiftUI architecture and testable Swift

Read this when building or reviewing SwiftUI screens beyond the basics: Observation-based models, view identity, navigation, performance, previews, and making Swift code testable with protocol-based dependency injection and Swift Testing. The state-wrapper table, language idioms and basic test frameworks are in `swift.md`; concurrency diagnostics and actors in `swift-concurrency.md`; design, interaction and accessibility rules in ProductCraft's UI modules.

## Models with Observation (iOS 17 and later)

- An `@Observable` class tracks reads per property: a view re-evaluates only when a property it read in `body` changes. Properties read only in event handlers do not create a dependency.
- **Mark UI models `@MainActor`** (or rely on main-actor default isolation, see `swift-concurrency.md`). An `@Observable` class is not `Sendable`; mutating it from a background task is a data race.
- **Ownership:** the view that creates the model holds it in `@State private var model = OrderListModel(...)`; children receive it as a plain property (read-only), `@Bindable` (to bind controls), or through `@Environment(OrderListModel.self)`.
- **`@State` initial values are evaluated every time the view struct is initialized,** even though SwiftUI keeps the first instance. An expensive initializer (loading files, starting work) therefore runs repeatedly and its results are thrown away. Keep initializers cheap and start work in `.task { await model.load() }`.
- `@ObservationIgnored` for stored properties that must not trigger updates (caches, injected services).
- `@Environment(SomeModel.self)` traps at runtime if no ancestor injected it. Inject at the root (`.environment(model)`) and in every preview.
- Outside SwiftUI, observe changes with the `Observations` async sequence (iOS 26 and later) or `withObservationTracking`; avoid rebuilding a Combine pipeline on top of an `@Observable` model.
- Projects targeting iOS 16 or earlier keep `ObservableObject`, `@Published`, `@StateObject` and `@ObservedObject`. A mixed codebase is fine; migrate a screen at a time, not as a side effect.

## View identity and lifetime

SwiftUI decides whether a view is "the same view" by its position in the hierarchy (structural identity) or by an explicit `id`. Identity decides when `@State` resets and when `.task` and `.onAppear` run again.

- `if condition { A() } else { A() }` produces two different identities: toggling the condition destroys one view's state and animates as remove-and-insert. To change appearance of the same view, use a conditional modifier value (`.opacity(isHidden ? 0 : 1)`, `.foregroundStyle(isError ? .red : .primary)`).
- `.id(value)` resets the view and its state whenever `value` changes. Use it on purpose (reset a form when the edited item changes), never as a "force refresh".
- `ForEach` needs stable identities from the data (`Identifiable` with a real ID). Array indices or `UUID()` created in `body` cause wrong animations and lost row state.
- `.task(id: query) { }` cancels and restarts the task when `query` changes, which is the cleanest search-as-you-type loop.
- `AnyView` erases the type and defeats SwiftUI's diffing; use `@ViewBuilder`, `Group` or generics.

## Composition and performance

- Split large bodies into small `View` structs that take only the data they show; a change then re-evaluates only the subviews that read it. Private `some View` computed properties do not create that boundary.
- `body` stays cheap: no sorting or filtering of large collections, no formatter creation, no I/O. Precompute in the model.
- `List` and `LazyVStack` create rows on demand; a plain `VStack` inside a `ScrollView` builds every row at once.
- Expensive effects (`.shadow`, `.blur`, masks) in scrolling rows cost frame time; measure with the SwiftUI template in Instruments before and after changing them.
- Conforming a view to `Equatable` can skip re-evaluation for expensive leaf views; use it only where Instruments shows a benefit.

## Navigation

- `NavigationStack(path:)` with a typed array (`[Route]`) or `NavigationPath`, and `.navigationDestination(for: Route.self)` placed on the stack's root content, not inside a lazy container (where it may not be registered). `NavigationSplitView` for sidebar layouts on iPad and Mac.
- Keep the path in a router model owned at the root; deep links and notification taps parse into `Route` values and set the path. Validate those values as untrusted input (`mobile-cross-platform.md`).
- Make routes `Codable` if the path must survive app relaunch through scene storage.
- Sheets and alerts driven by optional item state (`.sheet(item: $editingOrder)`) avoid "boolean plus separate selection" mismatches.

## Previews

- `#Preview` with fake services and fixed sample data, one preview per meaningful state (empty, loading, error, long content, large Dynamic Type, dark mode). `@Previewable @State` (Xcode 16 and later) declares preview-only state inline.
- Previews never hit the network, the keychain or live accounts.

## Testable design: protocols at the boundaries

Put each external dependency behind a small protocol owned by the code that uses it, and inject it.

```swift
protocol OrderFetching: Sendable {
    func orders(for customer: CustomerID) async throws -> [Order]
}

struct LiveOrderClient: OrderFetching {
    let session: URLSession
    func orders(for customer: CustomerID) async throws -> [Order] { /* URLSession call */ }
}

@MainActor @Observable
final class OrderListModel {
    private(set) var state: LoadState<[Order]> = .idle
    private let fetcher: any OrderFetching
    init(fetcher: any OrderFetching) { self.fetcher = fetcher }

    func load(for customer: CustomerID) async {
        state = .loading
        do { state = .loaded(try await fetcher.orders(for: customer)) }
        catch { state = .failed(error) }
    }
}
```

- **Boundaries only:** network, persistence, file system, clock (`any Clock<Duration>` or an injected `now` closure), randomness, notifications, location. Pure logic needs no protocol.
- **Small protocols:** one concern each. A single protocol for "all I/O" forces every test double to implement everything.
- **`Sendable` protocols** when implementations cross isolation boundaries; test doubles that record calls then need a lock or an actor (or main-actor isolation), not `@unchecked Sendable` without synchronization.
- **Production defaults** belong at the composition root (the `App` struct or a dependency container), not as default arguments scattered through initializers; scattered defaults make it easy to ship a test with live services wired in.
- **Closures** (`let fetchOrders: @Sendable (CustomerID) async throws -> [Order]`) work as lighter alternatives to protocols for one-function dependencies.
- Avoid `#if DEBUG` branches that swap implementations inside production code; inject instead.

## Swift Testing

- `@Test` functions, `#expect` for checks that continue, `#require` for preconditions that stop the test (`let order = try #require(orders.first)`).
- **Parameterized tests:** `@Test(arguments: [...])` runs each argument as its own case; zip two collections for paired inputs.
- **Errors:** `#expect(throws: OrderError.notFound) { try await model.open(id) }`, or `#expect(throws: OrderError.self)` for any case of a type.
- **Events:** `await confirmation("delegate called") { confirm in ... }` asserts that a callback happened (an expected count is possible).
- **Parallel by default:** tests run concurrently, including across suites. Shared mutable fixtures (static caches, singletons, files at fixed paths) make results order-dependent; give each test its own instances, or mark a suite `.serialized` as a last resort.
- **Main-actor code:** annotate the test or suite `@MainActor` to call main-actor models directly.
- **Traits:** `.tags(...)` to group, `.disabled("reason")` with a reason, `.timeLimit(.minutes(1))`, and `withKnownIssue { }` for a documented known failure instead of deleting the test.
- Swift Testing and XCTest coexist in one target; UI tests (XCUITest) and performance tests stay on XCTest.

## What to test in a SwiftUI app

- **Models:** drive them through their public API with fake dependencies and assert on state transitions (idle, loading, loaded, failed) and on calls made to the fakes.
- **Formatting and mapping** (DTO to model, model to display strings) with parameterized tests, including locales and time zones you support.
- **Views:** snapshot tests only with the library the project already uses; review image diffs. Logic does not live in views, so most behavior is covered without rendering.
- **UI tests** for a few critical flows, located by `accessibilityIdentifier`; launch arguments switch the app to fake services and fixed data.

## Review checklist

- [ ] Each model has one owner; no model is created in a child view's `@State` when the parent owns the data.
- [ ] No heavy work in initializers or `body`; async work starts in `.task` and is cancellable.
- [ ] Identities are stable; no `.id(UUID())` or index-based `ForEach` over changing data.
- [ ] Every `@Environment(Type.self)` dependency is injected at the root and in previews.
- [ ] External dependencies sit behind small injected protocols or closures; tests run with no network.
- [ ] Tests do not share mutable state across parallel runs.

## Done when

- [ ] `swift test` or the scheme's `xcodebuild test` passed on an available simulator; the report names the destination.
- [ ] Changed screens were checked in previews or on a simulator in light and dark mode and at a large Dynamic Type size, or the report marks this `NOT VERIFIED`.
- [ ] New models have state-transition tests with fake dependencies.
