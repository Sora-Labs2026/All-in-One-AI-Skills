# React Native and Expo

Read this when you build or change a React Native app, with or without Expo: navigation, lists, animations, platform differences, storage, native modules, debugging, builds, over-the-air updates and upgrades. React itself is in `react.md`; what every mobile app shares (secrets, offline, deep links, push, releases, store rules) is in `mobile-cross-platform.md`.

## Versions that change the advice

| Version | What matters |
|---|---|
| React Native 0.76 (Oct 2024) | New Architecture (Fabric renderer, TurboModules, JSI, bridgeless) on by default; React Native DevTools replaces the older debugging tools |
| 0.81 (2025) | Built-in `SafeAreaView` deprecated in favor of `react-native-safe-area-context`; Android 16 support |
| 0.82 (Oct 2025) | Runs only on the New Architecture; the legacy architecture can no longer be enabled |
| Expo SDK 53 to 54 (2025) | New Architecture default; SDK 54 announced as the last SDK supporting the legacy architecture |

Hermes is the default JavaScript engine. Each Expo SDK pins one React Native version; read `expo` and `react-native` in the lockfile, and check library compatibility with the New Architecture (React Native Directory lists it) before adding a dependency.

## Expo or bare React Native

- The React Native docs recommend starting with a framework, and Expo is the common choice: prebuild (native projects generated from `app.config.ts` and config plugins), Expo Router, EAS Build and EAS Update, and a large set of maintained native modules.
- Custom native code works in Expo through development builds and the Expo Modules API. Expo Go only runs code with the modules it ships; once you add a native library, build a development client.
- With prebuild (continuous native generation), do not edit `ios/` and `android/` by hand; express native changes as config plugins so they survive regeneration. In a bare project that commits `ios/` and `android/`, edits there are normal.
- Install packages with `npx expo install <pkg>` so versions match the SDK, and run `npx expo-doctor` after dependency changes.

## Project layout and configuration

- Feature folders for screens, components, hooks and API code; the `app/` directory belongs to Expo Router routes only.
- `app.config.ts` holds app id, version, plugins and per-environment values. `EXPO_PUBLIC_` variables are inlined into the bundle and readable by anyone who unpacks the app.
- TypeScript with `strict`; path aliases configured for both TypeScript and the bundler.

## Navigation

- **Expo Router** (file-based, on top of React Navigation): `_layout.tsx` files define stacks and tabs; typed routes catch broken links at compile time; deep linking is configured from the file tree.
- **React Navigation** directly in projects that already use it; type the param lists.
- Protected routes (Expo Router `Stack.Protected` or conditional navigators) hide screens from signed-out users. That is UX; the API authorizes every request.
- Route params arrive from deep links too; validate them before use.
- Android's back button follows the navigation stack; intercept it (`BackHandler`, `usePreventRemove`) only to protect unsaved work.

## Lists and images

- Never render a long list with `ScrollView` and `map`; use `FlatList`, `SectionList` or FlashList (major 2 requires the New Architecture and needs no size estimate).
- Give items a stable `keyExtractor`, keep row components memoized and their props stable, and supply `getItemLayout` for fixed-height rows in `FlatList`.
- Tune `initialNumToRender` and `windowSize` only after measuring; the defaults are reasonable.
- Use `expo-image` (or another caching image component) and request thumbnails sized for the display, not originals.

```tsx
const Row = memo(function Row({ item, onOpen }: { item: Order; onOpen: (id: string) => void }) {
  return (
    <Pressable onPress={() => onOpen(item.id)} accessibilityRole="button"
               accessibilityLabel={`Order ${item.number}, ${item.statusLabel}`}>
      <Text>{item.number}</Text>
      <Text>{item.statusLabel}</Text>
    </Pressable>
  );
});

export function OrderList({ orders }: { orders: Order[] }) {
  const router = useRouter();
  const onOpen = useCallback((id: string) => router.push(`/orders/${id}`), [router]);
  return (
    <FlashList
      data={orders}
      keyExtractor={(o) => o.id}
      renderItem={({ item }) => <Row item={item} onOpen={onOpen} />}
      ListEmptyComponent={<EmptyOrders />}
    />
  );
}
```

## Animation and gestures

- Run animations on the UI thread with Reanimated and gestures with React Native Gesture Handler. Animating through React state on the JavaScript thread stutters whenever JavaScript is busy.
- Reanimated 4 requires the New Architecture and moved worklets into `react-native-worklets` (its Babel plugin is added by `babel-preset-expo`; bare projects add it themselves).
- Respect the system reduce-motion setting (`useReducedMotion`).

## Platform differences

- `Platform.select` for small differences; `.ios.tsx` and `.android.tsx` files for larger ones.
- Safe areas: `react-native-safe-area-context` (`SafeAreaProvider` at the root, `useSafeAreaInsets` or its `SafeAreaView`). Android 15 and later enforce edge-to-edge drawing for apps targeting API 35, so handle insets on Android too.
- Keyboard: `KeyboardAvoidingView` behaves differently per platform (`padding` on iOS, often nothing or `height` on Android); a keyboard-controller library gives consistent behavior for complex forms. Keep focused fields visible (`MOB-09`).
- Text scales with the system font size; layouts must survive the largest setting. Do not disable font scaling globally.

## Storage

| Need | Use |
|---|---|
| Tokens and secrets | `expo-secure-store` or another Keychain/Keystore-backed library |
| Small preferences, persisted client state | MMKV (synchronous, fast; current majors require the New Architecture) or AsyncStorage |
| Relational or offline data | SQLite (`expo-sqlite`, or another SQLite binding) |
| Server data | TanStack Query or the project's data library, optionally persisted |

AsyncStorage and MMKV are not encrypted by default. Never store tokens there.

Wire the data library to app state so it refetches on resume and knows when the device is offline:

```ts
import { AppState } from "react-native";
import NetInfo from "@react-native-community/netinfo";
import { focusManager, onlineManager } from "@tanstack/react-query";

onlineManager.setEventListener((setOnline) =>
  NetInfo.addEventListener((s) => setOnline(!!s.isConnected)),
);
AppState.addEventListener("change", (status) => focusManager.setFocused(status === "active"));
```

## Native code

- Write new native modules with the Expo Modules API (Swift and Kotlin) or as TurboModules with codegen. The old bridge-based module APIs are gone with the legacy architecture.
- Keep native modules thin: platform calls in, plain data out. Business logic stays in TypeScript where it is tested.
- Native code reached from JavaScript is a trust boundary; validate arguments there.

## Performance and debugging

- Measure in release builds on a low-end Android device. Profile JavaScript with React Native DevTools (press `j` in the Metro terminal) and the Hermes profiler; profile native with Xcode Instruments and Android Studio.
- Common costs: re-renders of large screens (see `react.md`), unvirtualized lists, oversized images, synchronous storage reads of large values at startup, heavy work in the JavaScript thread during navigation.
- Logs: Metro terminal for JavaScript, `adb logcat` and the Xcode console for native crashes.

## Testing

- Jest with the `jest-expo` preset (or `react-native` preset) and React Native Testing Library: query by role, label and text, fire events, await async UI.
- Mock native modules at the module boundary; many libraries ship Jest mocks.
- End-to-end on emulators in CI with Maestro or Detox, covering sign-in, the main flow, deep-link entry and offline behavior.

## Builds, updates and upgrades

- **EAS Build** profiles (`development`, `preview`, `production`) in `eas.json`; credentials managed by EAS or supplied from the CI secret store. Local builds use `npx expo run:ios` and `run:android` (or Xcode and Gradle in bare projects).
- **EAS Update** ships JavaScript and assets to binaries with the same `runtimeVersion`. Use the `fingerprint` runtime policy so a native change automatically gets a new runtime version. Publishing an update to production is a release; get approval.
- **Upgrading:** one SDK (or React Native minor) at a time. `npx expo install expo@^<sdk> --fix`, then `npx expo-doctor`, then rebuild development clients. Bare projects compare their native files with the React Native Upgrade Helper diff for the two versions. Upgrade native libraries in the same change and read their New Architecture notes.

## Security hooks

- The JavaScript bundle ships in the app as readable source or Hermes bytecode; no secrets in it (`../../code-security-review/references/mobile-apps.md`).
- WebViews: allow only your own origins, keep JavaScript off for untrusted content, and never expose a native bridge to pages you do not control.
- Deep-link and notification payloads are untrusted input.

## Common breakages

| Symptom | Cause | Fix |
|---|---|---|
| "requireNativeComponent: X was not found" or "Cannot find native module" | Native library added without rebuilding the app, or running in Expo Go | Build a development client; `npx expo prebuild --clean` if native projects are generated |
| Red screen after changing dependencies | Stale Metro cache or mismatched versions | `npx expo start --clear`; `npx expo install --fix`; check for duplicate `react` copies |
| iOS build fails after adding a library | CocoaPods out of date | `npx pod-install` (or `cd ios && pod install --repo-update`) |
| Android build fails with Gradle or JDK errors | Wrong JDK or Gradle plugin version | Use the JDK version the React Native release requires (17 for current releases); clean with `./gradlew clean` |
| Library crashes on the New Architecture | Library not updated | Upgrade it, find a maintained replacement, or report it; the legacy architecture is no longer an option from 0.82 |
| Content under the notch or navigation bar | Missing safe-area handling or edge-to-edge on Android | `SafeAreaProvider` and insets |

## Done when

- [ ] Type check, lint and Jest tests pass; `npx expo-doctor` (Expo) reports no problems.
- [ ] The change runs in a development or release build on one iOS and one Android target.
- [ ] Long lists are virtualized; tokens are in secure storage; no secret is in `EXPO_PUBLIC_` values.
- [ ] Builds, store submissions and production updates were prepared, not published, unless the user approved.
