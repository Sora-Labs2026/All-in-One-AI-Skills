# Build failures by ecosystem

Read this when a build, dependency resolution, code generation or packaging step fails: after a pull, an upgrade, a merge, a new dependency, or on CI only. It lists the failures that recur in each ecosystem with their usual cause and fix. The general method (reproduce, isolate, fix at the source, stop after three failed attempts, triage many failures by group) is in `../../engineering-workflow/references/debugging.md`; per-stack idioms are in the matching reference.

## Rules for fixing a build

1. **Reproduce with the project's own command** (the wrapper, the CI step), not a command you composed. Note the tool versions it ran with.
2. **Read the first error, not the last.** Later errors are usually consequences. Find which phase failed: configuration (the build tool cannot even load the project), dependency resolution, code generation, compilation, tests, packaging.
3. **Change one thing, rebuild, look again.** Keep a list of what you tried.
4. **Make the smallest fix at the cause.** Do not refactor, rename or reformat while fixing a build.
5. **Never make the build pass by hiding the problem:** no new suppressions (`@SuppressWarnings`, `// ignore:`, `#[allow(...)]`, `//nolint`, `#pragma` warning pragmas, `@unchecked Sendable`), no `!!` or force unwraps to satisfy the type checker, no `dynamic` or `Any` to dodge types, no skipped or deleted tests, no lowered warning levels, unless the user agrees and the reason is written next to it.
6. **No dependency upgrades or downgrades as a silent fix.** If the fix is a version change, say which version, why, and what else it changes; ask first when it is more than a patch release (`../../engineering-practices/references/dependencies.md`).
7. **Do not delete lockfiles, caches or generated directories wholesale** as a first step. Clear the specific stale cache when the evidence points to it, and say so.
8. **Credentials:** a private registry failure needs the user's credentials configured by the user. Never ask for tokens in the chat or write them into build files.
9. **Stop and report** after three failed attempts, when the fix needs a design change, a new dependency, a toolchain installation, or signing material only the user has.

## Java: Maven and Gradle

| Symptom | Usual cause | Fix |
|---|---|---|
| `release version 21 not supported`, `invalid target release` | The JDK running the build is older than the configured release | Use the JDK the project names (`JAVA_HOME`, Gradle toolchains, `.sdkmanrc`, CI config); do not lower the release level |
| `Unsupported class file major version 65` (or another number) | A build tool or plugin too old for the JDK it runs on (for example an old Gradle on a new JDK) | Check the Gradle or plugin compatibility matrix; run the build on a supported JDK, or upgrade the tool as its own change |
| `cannot find symbol` for Lombok-generated getters or builders; MapStruct mappers missing | Annotation processor not on the processor path, or a Lombok version older than the JDK supports | Maven `annotationProcessorPaths`, Gradle `annotationProcessor`; align the Lombok version with the JDK |
| `package javax.persistence does not exist` after an upgrade | `javax` to `jakarta` namespace change (Spring Boot 3, Quarkus 3, Jakarta EE 9 and later) | Migrate imports to `jakarta.*` with the framework's migration tooling; do not add old `javax` artifacts back |
| `NoSuchMethodError` or `NoClassDefFoundError` at runtime or in tests | Two versions of a library on the classpath; the wrong one won | `./mvnw dependency:tree -Dverbose` or `./gradlew dependencyInsight --dependency <name>`; align through the BOM or a constraint |
| `Could not resolve` / `artifacts could not be resolved` | Missing repository, wrong version, private registry without credentials, offline sandbox | Check the coordinates and repositories; credentials come from the user's `settings.xml` or Gradle properties outside the repository |
| Gradle configuration-cache or "Configuration on demand" errors | A build script reads mutable state at configuration time | Fix the script as the message suggests; do not turn the cache off in the shared properties without asking |
| Spring: `No qualifying bean of type` | Class outside the component-scan packages, a missing `@Configuration` import, or an auto-configuration condition not met | Run with `--debug` to print the condition evaluation report; fix the package or the condition |
| Spring: `Failed to configure a DataSource` | A JDBC starter on the classpath without connection properties, or the driver missing | Add the properties for the profile, or the driver; in tests, a Testcontainers `@ServiceConnection` |
| Spring: "The dependencies of some of the beans form a cycle" | Constructor injection cycle (prohibited by default since Boot 2.6) | Break the cycle by moving the shared logic into a third bean; do not set `spring.main.allow-circular-references` |
| Quarkus: `UnsatisfiedResolutionException` | No bean-defining annotation, a missing extension, or a bean in a dependency without a Jandex index | Add the scope annotation or extension, or index the dependency (`quarkus.md`) |
| Quarkus: `BlockingOperationNotAllowedException` | Blocking call on the event loop | Change the method signature or add `@Blocking`, or use the reactive client |
| Native image: `ClassNotFoundException`, missing resources | Reflection or resources the native build did not see | `@RegisterForReflection`, `quarkus.native.resources.includes`, or the library's extension |

## Kotlin, Android and Kotlin Multiplatform

| Symptom | Usual cause | Fix |
|---|---|---|
| "Starting in Kotlin 2.0, the Compose Compiler Gradle plugin is required" | Kotlin upgraded to 2.x without the Compose compiler plugin | Apply `org.jetbrains.kotlin.plugin.compose` at the Kotlin version; remove the old `kotlinCompilerExtensionVersion` setting |
| "Smart cast to 'X' is impossible, because 'y' is a mutable property" | The compiler cannot prove the value did not change | Copy into a local `val`, or use `?.let { }` |
| `Unresolved reference` in `commonMain` | Dependency declared only in a platform source set, or an Android-only API in shared code | Declare it in `commonMain.dependencies`; move platform code behind `expect`/`actual` or an interface |
| "Expected declaration has no actual" | A target lacks an `actual` | Add the `actual` in each target's source set |
| KSP or kapt failures; "KSP version mismatch" | KSP version not matching the Kotlin version, or kapt and KSP processors mixed | Align KSP with Kotlin per its release notes; use one processor mechanism per library |
| `Android Gradle plugin requires Java 17 to run` | Gradle running on an older JDK | Set the JDK for Gradle (`org.gradle.java.home` or the IDE's Gradle JDK) as the project documents |
| `Namespace not specified` | AGP 8 requires `namespace` in each module's build file | Add `android { namespace = "..." }` matching the old manifest package |
| `Duplicate class ... found in modules` | Two artifacts ship the same classes (old and new library generations) | Find them with `./gradlew :app:dependencies`; exclude or align versions |
| Manifest merger: "minSdkVersion X cannot be smaller than version Y declared in library" | A dependency needs a higher `minSdk` | Raising `minSdk` drops devices; ask, or pick a library version that supports the current minimum |
| `checkDebugAarMetadata` failures | A dependency needs a higher `compileSdk` or AGP | Raise `compileSdk` (no runtime effect), or the AGP version as its own change |
| Release build crashes or `Missing class` warnings from R8 | Reflection-based code stripped or renamed | Keep rules from the library's documentation, then test the release build |

## Swift, Xcode and Swift Package Manager

| Symptom | Usual cause | Fix |
|---|---|---|
| Data-race errors after moving to Swift 6 mode ("Sending 'x' risks causing data races", main-actor isolation errors, global state not concurrency-safe) | Strict concurrency is now enforced | Fix ownership as in `swift-concurrency.md`; do not revert the language mode without asking |
| `No such module 'X'` | Package product not linked to the target, wrong scheme, or stale derived data | Add the product to the target; clean the build folder; resolve packages again (`swift package resolve` or File > Packages > Reset Package Caches) |
| `'X' is only available in iOS 17.0 or newer` | Using an API above the deployment target | Guard with `if #available` and provide a fallback; raising the deployment target is the user's decision |
| Package resolution conflicts | Two packages require incompatible versions of a third | Read `Package.resolved`; adjust version requirements; do not edit the resolved file by hand |
| `Macro "X" must be enabled before it can be used` | Xcode requires trust for macro packages | The user approves the macro in Xcode; in CI, skipping macro validation is acceptable only for packages the team trusts |
| Signing and provisioning errors | Certificates and profiles belong to the user's account | Build for the simulator or with signing disabled for verification (`CODE_SIGNING_ALLOWED=NO`); signing is the user's step |
| Tools-version errors in `Package.swift` | The manifest needs a newer Swift than the toolchain in use | Use the Xcode or toolchain the project names; do not lower the tools version |

## Dart and Flutter

| Symptom | Usual cause | Fix |
|---|---|---|
| "Because X depends on Y ... version solving failed" | Incompatible constraints | `dart pub deps` to see the chain; adjust constraints deliberately; `dependency_overrides` only as a temporary, commented workaround |
| "The current Dart SDK version is X. Because app requires SDK version >=Y" | Local SDK older than the project needs | Use the pinned Flutter version (FVM or CI config) |
| Missing `*.g.dart` or `*.freezed.dart`, "part of" errors | Generated code stale or absent | `dart run build_runner build --delete-conflicting-outputs` |
| Android build fails after a Flutter upgrade | AGP, Gradle, Kotlin or JDK outside the range the Flutter release supports | Align them with the release notes; `flutter clean` |
| A plugin needs a higher `minSdkVersion` or iOS platform version | Plugin requirements | Raising minimums drops devices; ask |
| iOS: CocoaPods errors after adding a plugin | Pods not installed or repo stale | `cd ios && pod install` (with `--repo-update` if a spec is missing) |

## Go

| Symptom | Usual cause | Fix |
|---|---|---|
| `missing go.sum entry` | Module added without updating `go.sum` | `go mod tidy` (or `go mod download <module>`), then commit both files |
| `go.mod requires go >= 1.24 (running go 1.22)` | Toolchain older than the `go` line | Use the required toolchain; in an offline sandbox, report the mismatch (`go.md`) |
| `import cycle not allowed` | Two packages import each other | Move the shared types into a lower package |
| `checksum mismatch` / `SECURITY ERROR` | The downloaded module differs from the checksum database | Stop and report; never disable the checksum database to get past it |
| `inconsistent vendoring` | `vendor/` out of date with `go.mod` | `go mod vendor` |
| cgo: C compiler not found | A dependency uses cgo | Install the toolchain, or `CGO_ENABLED=0` if the project builds without cgo |

## Rust

| Symptom | Usual cause | Fix |
|---|---|---|
| E0502, E0499 (conflicting borrows), E0597 ("does not live long enough") | Borrow scope overlaps a mutation or outlives the owner | Shorten the borrow, restructure ownership (`rust-engineering.md`); not `unsafe`, and not blanket `.clone()` |
| "future cannot be sent between threads safely" | A non-`Send` value (`Rc`, a `std::sync::MutexGuard`) held across `.await` | Drop it before the await, or use `Arc` and `tokio::sync::Mutex` |
| "expected struct `X`, found struct `X`" | Two versions of the same crate in the graph | `cargo tree -d`; align versions |
| `package requires rustc 1.xx` | A dependency's MSRV exceeds the toolchain | Use the pinned toolchain, or `cargo update -p <crate> --precise <older>` within the lockfile policy |
| Linker or `*-sys` crate build errors (`openssl`, `pkg-config`) | Native library or headers missing | Install the system development package, or switch to a pure-Rust feature (for example `rustls`) with agreement |

## C and C++ with CMake

| Symptom | Usual cause | Fix |
|---|---|---|
| `undefined reference to` / `unresolved external symbol` | Source not in the target, library not linked, C and C++ name mangling (`extern "C"` missing), or static library order | Add the source or `target_link_libraries`; check `extern "C"` in shared headers |
| `multiple definition of` | A non-`inline` function or variable defined in a header | Mark it `inline`, or move the definition into one `.cpp` |
| `incomplete type` | Only a forward declaration is visible where the full type is needed | Include the defining header in the `.cpp` |
| `Could not find a package configuration file provided by "X"` | Package not installed or not on `CMAKE_PREFIX_PATH`; package-manager toolchain file not used | Configure with the project's preset or the vcpkg or Conan toolchain file |
| Strange errors after changing compilers or options | Stale CMake cache | `cmake --fresh --preset <name>` (CMake 3.24 and later) or a new build directory |
| Template error pages | One wrong argument deep in an instantiation | Read the first "required from here" line in your code; constrain templates with concepts (`cpp.md`) |

## .NET

| Symptom | Usual cause | Fix |
|---|---|---|
| `NETSDK1045` (SDK does not support the target framework) | Installed SDK older than the target, or `global.json` pins a different SDK | Install or select the SDK named in `global.json` |
| `NU1605` (package downgrade), `NU1107` (version conflict) | Transitive version disagreement | Reference the higher version explicitly, or align versions centrally |
| `NU1008` | A version on a `PackageReference` while central package management is on | Move the version to `Directory.Packages.props` |
| `NU1004` in locked mode | `packages.lock.json` out of date | Restore without locked mode, review and commit the updated lock file |
| `CS8618` and other nullable warnings failing the build | Warnings as errors with nullable enabled | Initialize or make the member nullable deliberately; no blanket `!` |

## Report

State the failing command, the first error, the cause you found, the change you made (file and line), the command that now passes, and anything left for the user (toolchain installation, credentials, signing, a version decision).
