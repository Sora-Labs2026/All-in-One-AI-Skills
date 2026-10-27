# Flutter and Dart

Read this when you build or change a Flutter app: widgets, state management, navigation, data and platform integration, performance, tests, builds and upgrades. What every mobile app shares (secrets, offline, deep links, push, releases, store rules) is in `mobile-cross-platform.md`.

## Versions that change the advice

| Version | What matters |
|---|---|
| Dart 3 (2023) | Sound null safety is mandatory; records, patterns, `switch` expressions, `sealed` classes and class modifiers |
| Flutter 3.x (2024-26) | Impeller is the default renderer on iOS and on Android (API 29 and later); on the web, CanvasKit or the WebAssembly renderer (skwasm), with the older HTML renderer deprecated |
| Dart macros | Cancelled in January 2025; JSON and data-class generation still use `build_runner` (`json_serializable`, `freezed`) |
| Riverpod 3 (2025) | `Notifier` and `AsyncNotifier` are the main APIs; `StateNotifier` and `StateProvider` moved to a legacy import |

Read the Flutter SDK constraint in `pubspec.yaml`, the version pinned for the team (FVM's `.fvmrc`, CI config) and `pubspec.lock`. `flutter upgrade` changes the SDK for every project on the machine; prefer a pinned SDK per project.

## Dart idioms

- Prefer `final` and immutable data. Model states and results with `sealed` classes so `switch` is checked for exhaustiveness:

```dart
sealed class OrdersState {}
final class OrdersLoading extends OrdersState {}
final class OrdersLoaded extends OrdersState { OrdersLoaded(this.orders); final List<Order> orders; }
final class OrdersFailed extends OrdersState { OrdersFailed(this.message); final String message; }

Widget build(BuildContext context) => switch (state) {
  OrdersLoading() => const Center(child: CircularProgressIndicator()),
  OrdersLoaded(:final orders) when orders.isEmpty => const EmptyOrders(),
  OrdersLoaded(:final orders) => OrderList(orders: orders),
  OrdersFailed(:final message) => ErrorRetry(message: message, onRetry: reload),
};
```

- Records for small multi-value returns (`(int, String)`); classes once the shape has a name and meaning.
- Avoid `!` on nullable values unless a preceding check proves them; prefer pattern matching or early returns.
- Parse JSON into typed models at the boundary (generated `fromJson` or hand-written with validation); never pass `Map<String, dynamic>` through the app.

## Widgets

- Split UI into small widget classes, not helper methods that return widgets. Classes get their own element and can be `const`, so Flutter skips rebuilding them.
- Use `const` constructors wherever the inputs are constant; the analyzer's `prefer_const_constructors` lint finds them.
- Local, ephemeral state (a toggle, an animation, a text field) belongs in a `StatefulWidget` with `setState`. App-wide or shared state belongs in the chosen state-management approach. Both are correct in their place.
- Dispose what you create: `TextEditingController`, `AnimationController`, `ScrollController`, `FocusNode`, `StreamSubscription`, timers.
- After an `await`, check `context.mounted` (or `mounted` in a `State`) before using `context` or calling `setState`.
- Keys: `ValueKey(item.id)` for list items that can be reordered or removed; `GlobalKey` rarely, because it is expensive and global.

## State management

Use what the project uses. For new projects, pick one and document it.

- **Riverpod:** `ref.watch` in `build`, `ref.read` in callbacks, `ref.listen` for side effects such as navigation or snackbars, `select` to rebuild only on the field you use. `AsyncNotifier` for async state, rendered through `AsyncValue` (`when` or pattern matching).
- **Bloc or Cubit:** events in, states out; `BlocBuilder` with `buildWhen` for UI, `BlocListener` for side effects; `bloc_test` for tests. Cubits for simple state, Blocs when event transformations (debounce, drop while busy) matter.
- **Provider, `ChangeNotifier`, `ValueNotifier`:** fine for small apps; the Flutter team's architecture guide uses view models with `ChangeNotifier` plus repositories and services.
- Whatever the tool: business logic lives outside widgets and is tested without them, and state is replaced, not mutated in place.

```dart
// Riverpod 3 without code generation
final ordersProvider = AsyncNotifierProvider<OrdersNotifier, List<Order>>(OrdersNotifier.new);

class OrdersNotifier extends AsyncNotifier<List<Order>> {
  @override
  Future<List<Order>> build() => ref.watch(orderRepositoryProvider).fetchOrders();

  Future<void> markShipped(String id) async {
    await ref.read(orderRepositoryProvider).markShipped(id);  // errors surface to the caller
    ref.invalidateSelf();                                      // refetch instead of patching locally
  }
}
```

## Navigation

- `go_router` (maintained by the Flutter team) for declarative routes, deep links and web URLs. `StatefulShellRoute` keeps each bottom-tab stack alive.
- `redirect` sends signed-out users to sign-in. That is UX; the API authorizes every request.
- Path and query parameters arrive from deep links; parse and validate them. `go_router_builder` generates typed routes.

## Data, isolates and platform code

- HTTP with `http` or `dio`, behind repositories; timeouts on every call.
- Decode large JSON payloads off the UI isolate (`Isolate.run` or `compute`); the UI isolate has one frame budget for everything.
- Local persistence: `drift` or `sqflite` for relational data, `shared_preferences` for small settings, `flutter_secure_storage` for tokens.
- Platform channels for native calls; generate type-safe channels with Pigeon rather than passing untyped maps. `dart:ffi` with `ffigen` for C libraries.
- Check a plugin's maintenance, platform support and federated implementations on pub.dev before adding it; an abandoned plugin blocks future upgrades.

## Performance

- Profile in profile mode on a real device (`flutter run --profile`), with DevTools: the frame chart separates UI-thread and raster-thread time; rebuild tracking shows which widgets rebuild.
- Usual fixes: `const` widgets; splitting a large `build` so only the changing part rebuilds; `ListView.builder` or slivers for long lists; `RepaintBoundary` around a frequently repainting region (verify with the repaint overlay); avoiding `Opacity` and `ClipRRect` over large subtrees in animations (use `FadeTransition`, pre-clipped assets); decoding images at display size (`cacheWidth`, `cacheHeight`); heavy work in isolates.
- App size: `flutter build appbundle --analyze-size` and `flutter build ipa --analyze-size`.

## Testing

- **Unit tests** (`package:test`) for models, repositories and notifiers or blocs, with fakes or `mocktail`.
- **Widget tests** (`testWidgets`): `pumpWidget`, then `pump()` for a frame or `pumpAndSettle()` until animations finish. `pumpAndSettle` times out with endless animations (spinners); pump a fixed duration instead. Override providers with `ProviderScope(overrides: [...])`.
- **Golden tests** catch visual regressions but differ across operating systems and fonts; generate and compare them on one CI platform with bundled fonts.
- **Integration tests** with `integration_test` on emulators or devices for the main flows.
- Run `flutter analyze` and `dart format --output=none --set-exit-if-changed .` in CI; use `flutter_lints` or a stricter set the project chose.

## Builds and releases

- Flavors (`--flavor`) and per-environment values (`--dart-define-from-file=env/prod.json`). Defines are compiled into the binary and are public.
- Release builds: `flutter build appbundle` and `flutter build ipa`, with `--obfuscate --split-debug-info=build/symbols`; upload the symbols to the crash reporter. Obfuscation renames symbols and hides nothing else.
- `version: 1.4.0+57` in `pubspec.yaml` sets the version name and build number; the build number must rise with every store upload.
- Signing keys and keystore passwords stay out of the repository and the chat.

## Upgrades

- Upgrade the SDK on a branch, then `flutter pub outdated` and upgrade packages deliberately (`flutter pub upgrade --major-versions` changes constraints; review the diff).
- `dart fix --apply` applies automated migrations for deprecated APIs.
- Android: keep the Android Gradle Plugin, Gradle, Kotlin and the declarative `plugins {}` block in line with what the Flutter release documents. iOS: run `pod repo update` and `pod install` after plugin changes.

## Security hooks

- Nothing secret in Dart code or defines; tokens in `flutter_secure_storage` (`../../code-security-review/references/mobile-apps.md`).
- WebViews (`webview_flutter`): restrict navigation to your origins and do not expose JavaScript channels to untrusted pages.
- Validate deep-link and notification parameters.

## Common breakages

| Message or symptom | Cause | Fix |
|---|---|---|
| `setState() called after dispose()` | Async work finished after the widget left the tree | Check `mounted`; cancel subscriptions and timers in `dispose` |
| "Looking up a deactivated widget's ancestor is unsafe" | `context` used after an `await` | Check `context.mounted`, or capture what you need before awaiting |
| "A RenderFlex overflowed by N pixels" | Content larger than its row or column | `Expanded`, `Flexible`, wrapping text, or a scroll view; test with large fonts |
| "Vertical viewport was given unbounded height" | A `ListView` inside a `Column` | Wrap it in `Expanded`; `shrinkWrap` only for short lists |
| Hot reload does not show the change | Change in `initState`, globals or `main` | Hot restart |
| Build fails after a Flutter upgrade | Android Gradle Plugin, Gradle or Kotlin versions out of range; stale pods | Align versions per the release notes; `flutter clean`; reinstall pods |

## Done when

- [ ] `flutter analyze` is clean, formatting check passes and `flutter test` passes.
- [ ] Changes to platform code or plugins run on at least one Android and one iOS target.
- [ ] Performance work shows profile-mode frame times before and after on a real device.
- [ ] Controllers and subscriptions are disposed; `context` is not used across async gaps without a `mounted` check.
- [ ] Release builds upload debug symbols; no secret is in Dart code or defines.
