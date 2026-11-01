# Android, Jetpack Compose and Kotlin Multiplatform

Read this before building or changing a native Android app or a Kotlin Multiplatform (KMP) project: module layout, layers, Compose UI, state with Flow, persistence, Gradle builds, platform requirements, and Compose Multiplatform. Kotlin idioms and coroutine basics are in `kotlin.md`; what every mobile app shares (configuration, offline sync, deep links, push, store releases) is in `mobile-cross-platform.md`; reviewing a built app for security is `../../code-security-review/references/mobile-apps.md`; touch, safe-area and accessibility rules are in ProductCraft's UI modules.

## Orient first

- **Build files:** `settings.gradle.kts` (modules), `gradle/libs.versions.toml` (versions), convention plugins in `build-logic/` or `buildSrc/`. Add dependencies through the catalog and the convention plugins, not ad hoc in one module.
- **SDK levels:** `minSdk` (oldest device supported), `targetSdk` (behavior the app opts into), `compileSdk` (APIs visible at compile time). Raising `targetSdk` changes runtime behavior and is its own change with testing.
- **Toolchain alignment:** the Android Gradle Plugin (AGP), Gradle, the JDK running Gradle (AGP 8 needs JDK 17 or later), Kotlin, and KSP must be versions documented as compatible. Most "it broke after an upgrade" builds are a mismatch here (`build-failures.md`).
- **Compose compiler:** since Kotlin 2.0 the Compose compiler ships with Kotlin; apply the `org.jetbrains.kotlin.plugin.compose` plugin at the Kotlin version instead of pinning a separate compiler version.
- **Commands:** `./gradlew assembleDebug`, `./gradlew testDebugUnitTest`, `./gradlew lint`, `./gradlew connectedDebugAndroidTest` (needs an emulator or device the user provides), plus the project's ktlint or detekt tasks.

## Architecture and modules

Follow the layering the project has. For new code, the widely used shape is:

| Layer | Holds | Depends on |
|---|---|---|
| UI | Composables, `ViewModel`s, UI state classes, navigation | Domain (or data, in small apps) |
| Domain (optional) | Use cases for logic shared by several screens; plain Kotlin | Nothing Android-specific |
| Data | Repositories, data sources (Room, DataStore, network), mappers | Platform and library APIs |

- **Unidirectional data flow:** state flows down from the `ViewModel` as one immutable UI state object; events flow up as function calls. Composables do not reach into repositories.
- **Repositories are the single source of truth** for their data. For offline-first screens, the UI observes the local database and the repository refreshes it from the network; it does not merge two sources in the UI.
- **Map at the boundaries:** network DTOs and database entities are converted to domain or UI models in the data layer; Room entities and serialization annotations do not reach composables.
- **Modules:** split by feature (`:feature:orders`) plus shared `:core:*` modules once build times or team boundaries call for it. No cycles; a feature module never depends on another feature module directly.
- A use-case class for each repository call adds ceremony without value. Add one when logic combines repositories or is reused across screens.

## Dependency injection

- **Hilt** (Android-only) or **Koin** (also multiplatform); follow the project. With Hilt, use KSP rather than kapt where the versions allow; kapt is in maintenance mode and slows builds.
- Scope deliberately: singletons for repositories and clients, `ViewModel` scope for screen state. Never inject an `Activity` or `Fragment` into something that outlives it; use the application `Context` for long-lived objects.

## State and events with Flow

- Expose `StateFlow<UiState>` from the `ViewModel`, built with `stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), initial)`. The five-second window keeps the upstream alive across a configuration change without collecting while the app sits in the background.
- Collect in Compose with `collectAsStateWithLifecycle()`; in views, inside `repeatOnLifecycle(Lifecycle.State.STARTED)`. Plain `collectAsState()` keeps collecting in the background.
- Update with `_state.update { it.copy(...) }`, which is atomic; `_state.value = _state.value.copy(...)` loses concurrent updates.
- `StateFlow` drops values equal to the current one. Emitting a copy of the same data class does not notify collectors; a mutable list mutated in place never notifies anyone. Keep state immutable.
- **One-off events** (navigate, show a message): prefer modeling them as state that the UI consumes and then reports back ("message shown"). A `SharedFlow` without replay drops events emitted while nobody collects (during rotation or in the background). If the project uses a `Channel` with `receiveAsFlow()`, collect it in a lifecycle-aware way.
- Operators that matter in screens: `debounce` plus `distinctUntilChanged` for search input; `flatMapLatest` to cancel the previous query; `combine` to merge several sources into one state.

## Jetpack Compose

- **State hoisting:** screen-level composables take the state and callbacks; small composables stay stateless and previewable. Local UI state (expanded, text field) uses `remember { mutableStateOf(...) }`, or `rememberSaveable` when it must survive process death and rotation.
- **Side effects** run in effect handlers, never directly in the composable body: `LaunchedEffect(key)` for suspending work tied to a key; `DisposableEffect` for listeners that need cleanup; `rememberUpdatedState` for callbacks captured by long-running effects; `SideEffect` to publish state to non-Compose code.
- **Recomposition and stability:**
  - Since the Kotlin 2.0.20 Compose compiler, strong skipping is on by default: composables with unstable parameters can still be skipped when the instances are identical.
  - Still pass immutable data. Prefer immutable collections or stable wrappers for list parameters, and mark genuinely immutable classes from modules without the Compose compiler with `@Immutable`, or list them in a stability configuration file.
  - Measure before optimizing: Layout Inspector recomposition counts and the Compose compiler reports.
- **Reading state late:** read fast-changing values (scroll offset, animation progress) inside lambdas (`Modifier.offset { }`, `graphicsLayer { }`) or through `derivedStateOf`, so only layout or drawing reruns, not the whole composition.
- **Lazy lists:** `LazyColumn` with `key = { it.id }` so item state and animations follow the item, and `contentType` for mixed rows. Never put a lazy list inside a vertically scrolling parent without a bounded height.
- **Modifiers:** order changes the result (padding before `clickable` shrinks the touch area; `clip` before `background` clips the background). Accept a `modifier: Modifier = Modifier` parameter and apply it to the root element.
- **Navigation:** Navigation Compose 2.8+ supports type-safe routes as `@Serializable` classes; pass IDs, not whole objects, and load data in the destination's `ViewModel`. Pass navigation lambdas into screens rather than the `NavController`. Navigation 3, a newer library that models the back stack as state, appeared in 2025; check which one the project uses.
- **Previews** use fake data and fixed themes; they must not call repositories or the network.

## Data and background work

- **Room** for relational data: DAOs return `Flow` for observed queries and `suspend` functions for one-shot calls. Write migrations for every schema change and test them with `MigrationTestHelper`; destructive fallback migration erases user data and needs the user's agreement. Room also supports Kotlin Multiplatform from 2.7 (2025).
- **DataStore** replaces `SharedPreferences` for settings. For secrets, the Jetpack Security crypto library (`EncryptedSharedPreferences`) was deprecated in 2025; in new code keep keys in the Android Keystore and encrypt with them (for example with Tink), or follow what the project already uses.
- **WorkManager** for deferrable work that must survive process death (uploads, sync), with constraints (network, charging) and unique work names to avoid duplicates. Not for work the user is waiting on.

## Platform requirements that change code

| Requirement | Effect |
|---|---|
| Target API 35 (Android 15) | Edge-to-edge is enforced: draw behind system bars and handle insets (`WindowInsets`, `Modifier.safeDrawingPadding()`); Google Play has required API 35 for new apps and updates since August 2025, and the level rises each August |
| Target API 36 (Android 16) | The edge-to-edge opt-out no longer works; predictive back is on, so `onBackPressed()` is no longer called (use `OnBackPressedDispatcher` or `BackHandler`); on large screens, orientation and resizability restrictions are ignored |
| 16 KB memory pages | Since November 2025, Google Play requires new apps and updates that target Android 15 or later and ship native libraries to support 16 KB page sizes; rebuild native code and update libraries that bundle `.so` files |
| Runtime permissions | Request at the moment of use, handle "denied" and "don't ask again"; notification permission since Android 13 |

## Release builds

- **R8** shrinks and obfuscates release builds (full mode by default since AGP 8). Classes reached by reflection (serialization models, some DI and networking libraries) need keep rules, usually shipped by the library; add your own only for your reflective code. Always test the release build: R8 problems never show in debug.
- Upload the R8 mapping file with each build so crash reports are readable.
- **Baseline profiles** (generated with Macrobenchmark) improve startup and scrolling; measure with Macrobenchmark on a real device before and after.
- `versionCode` increases with every upload; signing keys stay in CI secrets. Store submission and rollout changes are the user's steps (`mobile-cross-platform.md`).

## Kotlin Multiplatform and Compose Multiplatform

- **Source sets:** `commonMain` holds shared logic; `androidMain`, `iosMain` and others hold platform code. A dependency must be declared in the source set that uses it; an "unresolved reference" in `commonMain` often means it was added only to `androidMain`.
- **Platform APIs** go behind interfaces injected per platform, or `expect`/`actual` declarations for small pieces. Every `expect` needs an `actual` in each target.
- **Shared libraries:** kotlinx.coroutines, kotlinx.serialization, kotlinx-datetime, the Ktor client (with an engine per platform), SQLDelight or Room, and the multiplatform builds of `ViewModel` and Navigation for Compose Multiplatform.
- **Dispatchers:** `Dispatchers.IO` exists on JVM, Android and Native (kotlinx.coroutines 1.7+) but not on JavaScript or Wasm targets; inject dispatchers into shared code.
- **iOS interop:** suspend functions and `Flow`s reach Swift through Objective-C headers as completion handlers and opaque types. Wrap them in a small Swift-friendly API, or use the bridging approach the project has chosen; do not expose deep generic hierarchies to Swift. Build the iOS framework in CI (`./gradlew :shared:linkDebugFrameworkIosSimulatorArm64` or the project's task) because Android builds do not compile Native code.
- **Compose Multiplatform** shares Compose UI across Android, iOS, desktop and web. iOS support was declared stable in 1.8 (May 2025) and web went to beta in 1.9 (September 2025); check the release notes for the version in use. Resources live in `composeResources` and are accessed through the generated `Res` class. Platform look and accessibility on iOS need deliberate testing on devices, not only previews.

## Testing

- **ViewModels:** unit tests with fakes for repositories, `runTest`, and `Dispatchers.setMain(StandardTestDispatcher())` (reset in teardown). Collect `StateFlow`s with Turbine or in `backgroundScope` so the test does not hang on an infinite flow.
- **Compose UI:** `createComposeRule()` with semantics matchers (`onNodeWithText`, `onNodeWithTag`) and assertions on what the user sees; prefer testing a stateless screen composable with fake state.
- **Robolectric** runs Android-dependent unit tests on the JVM; instrumented tests on an emulator cover what it cannot (real rendering, system integration).
- **Room:** in-memory database tests for DAOs; migration tests for every version step.
- **Screenshot tests** only with the project's existing tool; review diffs, never re-record blindly.

## Review checklist

- [ ] No `Context`, `Activity` or `View` held by a `ViewModel` or singleton.
- [ ] UI state is one immutable object per screen; flows are collected lifecycle-aware.
- [ ] No side effects in composable bodies; effect keys are correct.
- [ ] Lazy lists have stable keys; heavy work stays out of composition.
- [ ] Network and database calls are off the main thread and behind repositories.
- [ ] Exported components, deep links and WebViews follow `../../code-security-review/references/mobile-apps.md`.
- [ ] Release build tested with R8; keep rules justified.

## Done when

- [ ] `assembleDebug`, unit tests, `lint` and the configured style checks passed; the release variant builds.
- [ ] Changed screens were exercised on an emulator or device, including rotation, dark mode, the largest font size and process death where state matters, or the report marks this `NOT VERIFIED`.
- [ ] Schema changes have Room migrations with tests.
- [ ] For KMP changes, every affected target compiled and its tests ran (`./gradlew allTests` or per-target tasks).
- [ ] Nothing was published to a store or rollout changed without the user.
