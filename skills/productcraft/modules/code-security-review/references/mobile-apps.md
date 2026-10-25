# Mobile apps and their backends

Reference for the `code-security-review` module. Read it for Android or iOS apps (native, React Native, Flutter, Capacitor or Cordova) and for the backend services they talk to directly: Firebase, Supabase, Amplify and similar. The categories follow OWASP MASVS v2 (STORAGE, CRYPTO, AUTH, NETWORK, PLATFORM, CODE, RESILIENCE, PRIVACY); the OWASP MASTG describes test methods for each.

**One fact drives most findings: everything inside the app package is public.** Anyone can download an APK or IPA and unpack it. Obfuscation, string encryption and "hidden" config files slow people down; they do not keep a secret. The backend must enforce every rule itself.

**Contents:** [Rules of engagement](#rules-of-engagement) · [Get the artifact](#get-the-artifact) · [Hardcoded secrets and backend config](#hardcoded-secrets-and-backend-config) · [Firebase and other direct-to-client backends](#firebase-and-other-direct-to-client-backends) · [Android](#android) · [iOS](#ios) · [Deep links](#deep-links) · [Cross-platform frameworks](#cross-platform-frameworks) · [Confirm and report](#confirm-and-report)

## Rules of engagement

- Review apps the user owns or is authorized to assess. Prefer the source repository and its own build; an app store build is a second source.
- Static review of the package and the backend's rules files needs no live access. Live checks against a backend (reading a database path, calling a function, signing up) touch real systems and real users' data: do them only on the owner's project, with explicit approval, read-only, with benign markers, following [LaunchGuard safe operations](../../launchguard/references/safe-operations.md). Never write to, delete from or enumerate someone else's backend.
- Test rules and app behavior on emulators and local emulators of the backend first.
- Do not upload private builds to online scanners. Run local tools only (for example MobSF in a local container, if installed).

## Get the artifact

```sh
# Android: from a build, a device you own, or an app bundle
aapt2 dump badging app.apk | head -5                      # package, version, min and target SDK
apksigner verify --print-certs app.apk                    # "CN=Android Debug" on a release build is a finding
apkanalyzer manifest print app.apk > manifest.xml         # decoded AndroidManifest.xml
apktool d app.apk -o app-decoded                          # resources, smali, assets
jadx -d app-src app.apk                                   # decompiled Java/Kotlin, resources
bundletool build-apks --bundle=app.aab --output=app.apks --mode=universal  # AAB to a universal APK

# iOS: an IPA is a ZIP archive
unzip -q App.ipa -d ipa && ls ipa/Payload/
plutil -p ipa/Payload/App.app/Info.plist
codesign -d --entitlements - ipa/Payload/App.app          # macOS
security cms -D -i ipa/Payload/App.app/embedded.mobileprovision   # macOS; provisioning profile
```

App Store binaries are encrypted; static analysis of the executable needs a development, ad hoc or enterprise build, or the source. Resources, plists, bundled JavaScript and config files are readable either way.

## Hardcoded secrets and backend config

Search the decompiled output and resources. Print file and line, never the value: `-o -r '<redacted>'` makes ripgrep print only the replacement text.

```sh
rg -n -o -r '<redacted>' --no-ignore \
  -e 'AIza[0-9A-Za-z_-]{35}' -e 'AKIA[0-9A-Z]{16}' -e 'sk_live_[0-9A-Za-z]{10,}' -e 'rk_live_[0-9A-Za-z]{10,}' \
  -e 'xox[abpr]-[0-9A-Za-z-]{10,}' -e 'SG\.[0-9A-Za-z_-]{16,}\.[0-9A-Za-z_-]{16,}' \
  -e '-----BEGIN [A-Z ]*PRIVATE KEY-----' -e '"type"\s*:\s*"service_account"' \
  app-src app-decoded ipa 2>/dev/null
rg -n -o --no-ignore -e 'https://[a-z0-9.-]+\.(firebaseio\.com|firebasedatabase\.app)' \
  -e '[a-z0-9.-]+\.(appspot\.com|firebasestorage\.app)' -e 'https://[a-z0-9]+\.supabase\.co' \
  app-src app-decoded ipa 2>/dev/null | sort -u
```

Sort what you find into two groups:

- **Client identifiers meant to ship:** the Firebase config (`google-services.json` becomes `res/values/strings.xml` entries such as `google_api_key`, `firebase_database_url`, `google_storage_bucket`, `project_id`; `GoogleService-Info.plist` on iOS), the Supabase anon or publishable key, Stripe publishable keys, map SDK keys. They are not findings by themselves. They are safe only when the backend's rules restrict everything they can reach (LaunchGuard control 3) and, for paid APIs, when the key is restricted to the app's package name and signing certificate or bundle ID.
- **Secrets that must never ship:** service-account JSON, server API keys, Supabase service-role keys, Stripe secret or restricted keys, admin keys for search or messaging services, private keys, cloud access keys. Any of these in a package is an exposed credential: `ROTATION REQUIRED`, and follow the [leak response](../../launchguard/references/safe-operations.md#secrets-leak-response). Removing it from the next release does not revoke it; old versions stay downloadable.

## Firebase and other direct-to-client backends

When the app talks to the database directly, the security rules are the authorization layer. Review them from the repository (`firestore.rules`, `storage.rules`, `database.rules.json`, `firebase.json`). For a quick lead list:

```sh
python3 <productcraft>/modules/code-security-review/scripts/firebase_rules.py --root .
```

The script reads those files offline and flags rules that allow access without an effective condition, rules that only require a signed-in user, time-limited "test mode" rules and writes that never inspect the incoming data. Its output is leads; confirm each one with the emulator tests below.

What to look for:

- **Open rules:** Firestore or Storage `allow read, write: if true;` or an `allow` with no condition; Realtime Database `".read": true` or `".write": true`.
- **"Signed in" is not authorization.** `request.auth != null` (Realtime Database: `auth != null`) admits every account. If anonymous sign-in or email sign-up is enabled, anyone can create an account by calling the Auth REST API with the public API key, even when the app has no sign-up screen. Turn off providers the app does not use, and write ownership conditions such as `request.auth.uid == userId`.
- **Test-mode rules** (`request.time < timestamp.date(...)`, or `now < <milliseconds>` in the Realtime Database) are fully open until the date passes, then lock out everyone.
- **Realtime Database rules cascade:** a `.read` or `.write` grant on a parent applies to every child, and child rules cannot take it back.
- **Writes without validation:** an owner who may write their own document can still set `role: "admin"`, `plan: "pro"` or `credits` unless the rule checks the incoming data, for example `request.resource.data.diff(resource.data).affectedKeys().hasOnly(['displayName', 'photoURL'])` (LaunchGuard control 8). Storage uploads need size and content-type limits (`request.resource.size`, `request.resource.contentType`).
- **Wildcards:** `match /{document=**}` applies to every document below it, including collections added later; collection-group queries need their own `match /{path=**}/name/{id}` rules.
- **`list` versus `get`:** `allow read` includes listing whole collections; a rule that only checks the requested document ID does not stop a query.
- **Server code bypasses rules.** The Admin SDK and service accounts ignore security rules, so Cloud Functions must authorize every request themselves. HTTP functions (`onRequest`) are public unless they verify an ID token or are restricted by IAM; callable functions receive the caller's auth context but do not require it.
- **App Check is attestation, not authorization:** it raises the cost of scripted abuse, but a rule still has to decide who may read what.
- **Remote Config and storage download URLs:** client Remote Config values are readable by anyone with the app's config, so never store secrets there. Storage download URLs with a `token` parameter work for anyone who has the link.
- **Other backends:** Supabase tables reachable with the anon key need row-level security with per-operation policies (LaunchGuard control 4 and the Supabase playbook in `../../launchguard/references/stack-playbooks.md`); Amplify GraphQL schemas need `@auth` rules and Cognito identity pools need narrowly scoped unauthenticated roles; S3 buckets and search indexes reachable from the app need public access blocked or search-only keys.

**Prove rules with the emulator.** Rule tests run against the Firebase Local Emulator Suite and never touch a real project (project IDs starting with `demo-` cannot reach production resources):

```js
// test/firestore.rules.test.mjs
// Run: firebase emulators:exec --only firestore "node --test test/"
import { readFileSync } from "node:fs";
import { before, after, test } from "node:test";
import { initializeTestEnvironment, assertFails, assertSucceeds } from "@firebase/rules-unit-testing";
import { doc, getDoc, setDoc, updateDoc } from "firebase/firestore";

let env;
before(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-rules-review",
    firestore: { rules: readFileSync("firestore.rules", "utf8") },
  });
  await env.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), "users/alice"), { displayName: "Alice", role: "member" });
  });
});
after(async () => env.cleanup());

test("a visitor who is not signed in cannot read a profile", async () => {
  await assertFails(getDoc(doc(env.unauthenticatedContext().firestore(), "users/alice")));
});
test("another signed-in user cannot read it", async () => {
  await assertFails(getDoc(doc(env.authenticatedContext("bob").firestore(), "users/alice")));
});
test("the owner can read it", async () => {
  await assertSucceeds(getDoc(doc(env.authenticatedContext("alice").firestore(), "users/alice")));
});
test("the owner cannot promote themselves", async () => {
  const db = env.authenticatedContext("alice").firestore();
  await assertFails(updateDoc(doc(db, "users/alice"), { role: "admin" }));
});
```

Add the same cases for an anonymous account (`env.authenticatedContext("anon", { firebase: { sign_in_provider: "anonymous" } })`), for list queries, and for Storage and Realtime Database rules if the project uses them. Each test that fails before the fix and passes after it is the regression test.

## Android

| Area | Check | Notes |
|---|---|---|
| Debug and backup | `android:debuggable="true"` in a release; `android:allowBackup` and `android:dataExtractionRules` | Backups and device transfers can copy tokens and databases |
| Exported components | Every `<activity>`, `<service>`, `<receiver>` and `<provider>` with `android:exported="true"`, or with an intent filter in apps targeting API 30 or lower (exported by default) | Each is an entry point for other apps; it must check the caller (`android:permission` with a `signature` protection level) and validate every extra |
| Content providers | Exported providers, `grantUriPermissions`, path permissions, `openFile` with caller-supplied paths | SQL injection and path traversal through provider URIs |
| Intents | Implicit intents carrying tokens or personal data; mutable `PendingIntent`s handed to other apps | Explicit intents for internal communication; `FLAG_IMMUTABLE` |
| WebView | `setJavaScriptEnabled(true)` with `addJavascriptInterface` on pages that are not fully trusted; `setAllowFileAccess`, `setAllowUniversalAccessFromFileURLs(true)`; `onReceivedSslError` calling `handler.proceed()` | Any page loaded can call every `@JavascriptInterface` method |
| Network | `android:usesCleartextTraffic="true"`; `network_security_config.xml` with `cleartextTrafficPermitted="true"` or `<certificates src="user"/>` outside `<debug-overrides>`; custom `X509TrustManager` or `HostnameVerifier` that accept everything | User-installed certificates let anyone who can install a CA read the traffic |
| Storage | Tokens in `SharedPreferences`, SQLite or files in plain text; anything sensitive on external storage; tokens or personal data in `Log` calls | Keep keys in the Android Keystore and encrypt local secrets with a Keystore-held key; keep logs free of tokens |
| Biometrics | `BiometricPrompt` used without a `CryptoObject` only toggles a boolean in the app | Bind the secret to a Keystore key that requires user authentication |
| Tools | Android Lint's security checks (`./gradlew lint`), the decompiled source, and the manifest | |

- **Intent redirection:** an intent received from another app and passed on to `startActivity` or `sendBroadcast` reaches components that are not exported; validate or rebuild it first.

## iOS

| Area | Check | Notes |
|---|---|---|
| Transport | `NSAppTransportSecurity` with `NSAllowsArbitraryLoads` or broad exception domains; `URLSession` delegates that accept any server trust | |
| Storage | Tokens in `UserDefaults` or plain files; Keychain items with `kSecAttrAccessibleAlways` (deprecated) instead of a `...ThisDeviceOnly` class; files without a data-protection class | |
| Entitlements | `get-task-allow` set to true in a distribution build; broad `keychain-access-groups` or app groups shared with other apps | |
| URL schemes | `CFBundleURLTypes`: any app can register the same custom scheme | See [deep links](#deep-links) |
| WebViews | `WKWebView` with script message handlers exposed to untrusted pages; deprecated `UIWebView` | |
| Biometrics | `LAContext.evaluatePolicy` used as a boolean gate | Protect the secret with a Keychain access control that requires biometry, such as `.biometryCurrentSet` |
| Leaks | Sensitive screens captured in the app switcher snapshot; secrets on the general pasteboard; personal data in logs | |

- **Script message handlers:** a `WKScriptMessageHandler` exposes native features to every page the web view loads; restrict navigation to the expected origins.
- **Auth callbacks:** any app can register the same custom URL scheme; receive OAuth callbacks on universal links or through `ASWebAuthenticationSession` with PKCE.
- **Logs and crashes:** tokens in `print`, `NSLog` or `os_log` values marked `%{public}`; `try!`, force unwraps and `as!` on decoded data turn bad input into a crash.

## Deep links

- **Find them:** Android intent filters with `android.intent.action.VIEW` and the `BROWSABLE` category; iOS `CFBundleURLTypes` and the `com.apple.developer.associated-domains` entitlement; the routing code (`getIntent().getData()`, `onNewIntent`, `application(_:open:options:)`, `scene(_:continue:)`, React Navigation linking config, Flutter link handlers).
- **Custom schemes can be claimed by any app.** Password-reset, magic-link and OAuth redirect tokens sent to `myapp://` can be intercepted. Use verified HTTPS links: Android App Links with `android:autoVerify="true"` and `/.well-known/assetlinks.json` listing the signing certificate fingerprint, and iOS Universal Links with `apple-app-site-association`. OAuth in native apps uses PKCE and a claimed HTTPS redirect (RFC 8252).
- **Every parameter is untrusted input.** A link must not trigger payments, account changes, sign-in with an embedded token, or file access without the user's confirmation inside the app. Validate host and path against an allowlist before loading a link's URL in a WebView, and never load one into a WebView that exposes a native bridge.

## Cross-platform frameworks

- **React Native:** the JavaScript bundle (`assets/index.android.bundle`, `main.jsbundle`) ships readable source or Hermes bytecode, which can be disassembled. Values from `react-native-config`, `.env` files or Expo `extra` config are compiled into the bundle and are public.
- **Flutter:** `--dart-define` values and string constants are in `libapp.so`; `--obfuscate` renames symbols and hides nothing else.
- **Capacitor and Cordova:** the web app lies in `assets/public` or `assets/www`; review its plugins' native bridges, the allowed navigation list and the content security policy like any web front end.

## Confirm and report

- **Backend rules:** a failing emulator test shows the problem without touching production (`TESTED_LOCAL`). A read-only live check of the owner's own project, made with approval against a marker document the reviewer created, is `DEPLOYED_OBSERVED` (`TESTED_STAGING` on a staging project); never read real users' data to prove a point.
- **Secrets:** report the type, file and line, and the app versions that shipped it, never the value; mark `ROTATION REQUIRED`.
- **App-side issues:** reproduce on an emulator with the project's own debug build (an `adb shell am start` call to an exported activity, a crafted deep link); record the device, OS version and build.
- **Severity** follows what an outside attacker gains: open read of user data or open write anywhere is usually `CRITICAL`; auth-only rules over personal data `HIGH`; client-side storage issues usually need device access first, which lowers them. Root and jailbreak detection, pinning and obfuscation (MASVS-RESILIENCE) are hardening notes, not fixes for server-side gaps.
