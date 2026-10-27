# Mobile apps across platforms

Read this when you start, build or release a mobile app, whatever the framework: choosing between React Native, Flutter, a web-in-native shell or native code, and the engineering every mobile app shares (configuration, secure storage, offline sync, deep links, push, releases, over-the-air updates, device testing). Framework specifics are in `react-native-expo.md` and `flutter.md`; native Swift and Kotlin in `swift.md` and `kotlin.md`. Security review of a built app is `../../code-security-review/references/mobile-apps.md`; touch, safe-area and keyboard rules are the `MOB` rules in `../../../references/ui-rules/mobile-touch.md`.

## Choose the approach

| Approach | Fits | Costs |
|---|---|---|
| React Native with Expo | Teams with React and TypeScript skills; sharing logic (not UI) with a web app; native UI components | Native modules for anything unusual; JavaScript and native upgrade cadence |
| Flutter | One pixel-consistent UI on iOS, Android, desktop and web from Dart; heavy custom UI and animation | Dart skills; platform look must be built deliberately; larger base app size |
| Capacitor (or Ionic) | An existing web app that needs store presence and some device APIs | Web performance and feel inside a WebView; plugin quality varies |
| Progressive web app | Content and tools that need install and offline but few device APIs | iOS limits on background work and some APIs; no store discovery |
| Native (Swift and SwiftUI, Kotlin and Jetpack Compose) | Deep platform integration, best performance, platform-first UX | Two codebases; Kotlin Multiplatform can share business logic |

Ask before choosing for the user; the decision is expensive to reverse. Record it as an ADR (`../../engineering-practices/references/docs-and-decisions.md`).

## Configuration and secrets

- Keep separate builds for development, staging and production with different bundle or application ids, so they install side by side and never send test data to production.
- Everything compiled into the app is public: environment values, API keys, feature flags, the JavaScript bundle or Dart snapshot. Only publishable keys belong there (`../../code-security-review/references/mobile-apps.md`). Anything secret stays on your server.
- Store tokens in the platform keystore (iOS Keychain, Android Keystore) through a secure-storage library, not in plain key-value storage, files or logs.

## Networking and offline

- Every request has a timeout; retry only idempotent requests, with backoff (`../../engineering-practices/references/resilience.md`).
- Mobile networks drop, change and lie about connectivity. Treat a failed request as the offline signal, not the OS reachability flag.
- **Offline-first apps:** keep a local database (SQLite through the framework's wrapper), queue writes with client-generated ids and idempotency keys, sync when online, and define a conflict rule per entity (last write wins, server wins, or merge) before building. Show pending and failed sync honestly.
- **Certificate pinning** can brick every installed copy when certificates rotate. Pin only with a backup key, a rotation plan and a remote way to disable it; for most apps standard TLS validation is the right choice.

## Deep links

- Use verified HTTPS links: iOS Universal Links (`apple-app-site-association`) and Android App Links (`assetlinks.json` with the signing certificate fingerprint). Custom URL schemes can be claimed by other apps.
- Handle both cold start (app launched by the link) and warm start (app already running); test both.
- Treat every link parameter as untrusted input. A link never performs a payment, account change or sign-in by itself without confirmation inside the app.

## Push notifications

- APNs for iOS and FCM for Android (FCM can also deliver to iOS). Register the device token after sign-in, send it to your server, refresh it when the platform rotates it, and remove it on sign-out.
- Ask for permission when the user can see why, not at first launch (`MOB-08`).
- Notification taps route through the same deep-link handler as links.
- Do not put personal or sensitive content in the notification payload; it shows on the lock screen and passes through the push provider.

## Performance

- Measure release builds on a low-end Android device and the oldest supported iPhone. Debug builds are much slower and mislead.
- Watch cold start time, dropped frames during scrolling and animations, memory on long sessions, and app download size.
- Large lists are virtualized; images are downscaled to display size and cached.

## Testing matrix

- Unit tests for logic, component or widget tests for UI, and end-to-end tests on emulators in CI (Maestro, Detox, Flutter `integration_test`, Appium).
- Before release, check on real devices: smallest and largest supported screens, oldest supported OS, low-end Android, dark mode, the largest system font size, a right-to-left language, offline and flaky network, the app killed in the background and restored, permissions denied, and an interrupted flow (incoming call, app switch).

## Releases

- Version name follows semantic versioning; the build number (`CFBundleVersion`, `versionCode`) increases with every upload.
- Upload crash-report symbols with every build: dSYMs for iOS, R8 or ProGuard mapping files for Android, plus the framework's own (JavaScript source maps for Hermes, Flutter `--split-debug-info` symbols). Without them, crash reports are unreadable.
- Roll out in stages (Play staged rollout, App Store phased release) and watch crash-free sessions before widening.
- Store requirements change yearly; check them before each release cycle. Examples: Google Play requires targeting a recent Android API level (API 35 for new apps and updates from August 2025, rising each year); Apple requires privacy manifests for apps and SDKs that use listed APIs (since May 2024) and a minimum Xcode and SDK version each spring.
- Signing keys and store credentials never enter the repository or the chat; they live in the CI secret store or the build service (`../../agent-safety/GUIDE.md`). Submitting to a store, promoting a release or changing a rollout percentage is a production action: prepare it and let the user run or approve it.

## Over-the-air updates

- JavaScript and asset updates (Expo Updates for React Native; code-push services exist for Flutter) can ship fixes without store review. Microsoft's App Center, which hosted the original CodePush service, was retired in March 2025.
- An update must target binaries with the same native code; use a runtime-version or fingerprint policy so incompatible updates never reach old builds.
- Stay within store rules: fixes and small changes are fine; changing the app's primary purpose or adding features that need review is not.
- Keep a rollback path (republish the previous update) and roll out to a percentage first.

## Web-in-native shells (Capacitor)

- The app is your web build plus native plugins. Review each plugin's native code and permissions; prefer official or well-maintained ones.
- Set a content security policy and restrict navigation to your own origins; never load remote pages into the WebView that hosts your plugin bridge.
- Use live reload against a development server only in development builds.
- Everything in `web-frontend-foundations.md` applies; add device testing for keyboard, safe areas and back-button behavior.

## Done when

- [ ] Development, staging and production builds are distinct, and no secret is compiled into any of them.
- [ ] Tokens live in secure storage; deep links are verified and their parameters validated.
- [ ] The touched flows pass on at least one iOS and one Android target, including offline and a killed-and-restored app where relevant.
- [ ] Crash symbols are uploaded by the build pipeline.
- [ ] Store submissions, rollouts and over-the-air publishes are left to the user or done only with explicit approval.
