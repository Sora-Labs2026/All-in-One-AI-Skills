# Stacks

> ProductCraft module. Reach it through the router in `../../SKILL.md`; it is not a separate skill.

**Purpose:** Write code that a maintainer of *this* stack would accept. Detect the language, framework and versions from the repository, follow the project's own conventions, and prove the change with the ecosystem's own build, test, lint and format tools. Each reference holds the idioms, version notes and pitfalls for one stack or a group of related ones. Read only the one the change is written in.

How the work is done (tracks, done-when checks, test-first, debugging, review) lives in `../engineering-workflow/GUIDE.md`. Cross-cutting shape (API contracts, migrations, resilience, performance, observability, dependencies, large refactors) lives in `../engineering-practices/GUIDE.md`. Security traps per language live in `../code-security-review/references/language-pitfalls.md`, `../code-security-review/references/rust.md` and `../code-security-review/references/c-and-cpp.md`. Choosing a language for a new project is `../language-choice.md`. This module does not repeat any of them.

## When to activate

- You are about to write or change code in a language or framework you have not worked in during this session, or the change depends on framework behavior (ORM loading, transactions, dependency injection, async runtimes, build plugins).
- The task sets up or repairs a project's toolchain: build, test runner, linter, formatter, type checker, package manager.
- The task is a runtime, framework or major dependency upgrade, a legacy system that needs a safety net before it can change, or recovering what an undocumented system does.
- The task designs a system or splits one into services.
- Firmware, Salesforce org code or a command-line tool is involved.
- **Not for** a trivial edit where the surrounding code already shows the pattern. Follow the Quick track and match the neighbors.

## Ground rules

1. **The repository decides.** Versions, tools, layout, naming, error style and test style come from the project. Before writing, read two or three neighboring files of the same kind (a handler next to the handlers, a test next to the tests) and match them. Propose a different convention only with a reason, and ask first.
2. **Detect before assuming.** Read the manifests, lockfiles and version pins in the table below, or run `scripts/detect_stack.py`. In a monorepo every subproject has its own stack and its own commands.
3. **Write for the oldest supported version.** The language level is the project's minimum (`requires-python`, the `go` line in `go.mod`, `rust-version`, `maven.compiler.release`, `TargetFramework`, the PHP constraint in `composer.json`), not the newest release you know. Newer syntax breaks older supported runtimes.
4. **Use the project's wrapper and package manager:** `./mvnw` or `./gradlew`, `uv run` or `poetry run`, `bundle exec`, `composer`, `dotnet`, `cargo`, `go` with the toolchain `go.mod` names. Never mix package managers, never create a second lockfile, never install globally or with `sudo`.
5. **No new tools by stealth.** Do not add a framework, library, linter, formatter or build tool without asking. Run formatters on the files you changed unless the project formats everything in CI.
6. **No upgrades as a side effect.** A version bump is its own change with its own checks (`references/legacy-modernization.md`, `../engineering-practices/references/dependencies.md`).
7. **Generated code is regenerated, never hand-edited.** Change the source (protobuf, OpenAPI, GraphQL schema, ORM model, `.ioc` file) and run the project's generator.
8. **Prove it with the ecosystem's tools,** the same commands CI runs: compile or type-check, tests, lint, format check. Report what ran and what it showed; mark the rest `NOT VERIFIED` with the reason.
9. **Hands off shared and physical targets.** No deploys to orgs, app stores, package registries, clusters or production. Flashing firmware or driving real hardware needs the user's go-ahead, after a host test or simulation. A Salesforce production org is production.
10. **Version facts expire.** Statements in the references carry the version or year they apply to. Check the installed version (`<tool> --version`, the lockfile) before relying on one, and say which version you assumed when you could not check.

## Detect the stack

| Files present | Stack | Version pin to read | Packages locked by |
|---|---|---|---|
| `pyproject.toml`, `requirements*.txt`, `setup.cfg`, `Pipfile` | Python; `manage.py` means Django, a `FastAPI()` app means FastAPI | `requires-python`, `.python-version` | `uv.lock`, `poetry.lock`, `pdm.lock`, `Pipfile.lock`, pinned requirements |
| `go.mod`, `go.work` | Go | `go` and `toolchain` lines | `go.sum`, `vendor/modules.txt` |
| `Cargo.toml` | Rust | `edition`, `rust-version`, `rust-toolchain.toml` | `Cargo.lock` |
| `pom.xml`, `build.gradle(.kts)`, `settings.gradle(.kts)` | Java or Kotlin on the JVM; Spring Boot if its parent or plugin is present | `maven.compiler.release`, Gradle `toolchain`, Kotlin plugin version | Maven or Gradle wrapper, `gradle/libs.versions.toml`, `gradle.lockfile` |
| `*.sln`, `*.slnx`, `*.csproj`, `global.json`, `Directory.Build.props` | C# and .NET | `TargetFramework`, `LangVersion`, `global.json` SDK | `packages.lock.json`, `Directory.Packages.props` |
| `CMakeLists.txt`, `CMakePresets.json`, `meson.build`, `MODULE.bazel`, a hand-written `Makefile` | C or C++ | `CMAKE_CXX_STANDARD`, compiler in presets or toolchain file | `vcpkg.json`, `conanfile.*`, submodules |
| `composer.json`, `artisan` | PHP; Laravel or Symfony | `require.php`, `config.platform.php` | `composer.lock` |
| `Gemfile`, `bin/rails` | Ruby; Rails | `.ruby-version`, `ruby` in `Gemfile` | `Gemfile.lock` |
| `Package.swift`, `*.xcodeproj`, `*.xcworkspace` | Swift | `swift-tools-version`, Xcode version in CI | `Package.resolved` |
| `platformio.ini`, `west.yml` and `prj.conf`, `sdkconfig`, `*.ioc`, `*.ld`, `memory.x` | Embedded firmware (PlatformIO, Zephyr, ESP-IDF, STM32Cube, embedded Rust) | Toolchain and SDK versions in the config | The framework's own manifest |
| `sfdx-project.json`, `force-app/` | Salesforce | `sourceApiVersion` | `package.json` for LWC tooling |
| `package.json` with `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock` or `bun.lock` | JavaScript or TypeScript; framework from dependencies and configs (`next.config.*`, `nuxt.config.*`, `angular.json`, `vite.config.*`, `nest-cli.json`, `svelte.config.*`) | `engines`, `packageManager`, `.nvmrc`, `.node-version` | The lockfile present (one only) |
| `app.json` or `app.config.*` with an `expo` key, `eas.json`, `metro.config.js`, `ios/` and `android/` | React Native (Expo when `expo` is a dependency) | `expo` and `react-native` versions | JavaScript lockfile, `ios/Podfile.lock` |
| `pubspec.yaml` | Dart or Flutter | `environment: sdk`, `flutter` constraint, `.fvmrc` | `pubspec.lock` |
| Plugin header in a root PHP file, `style.css` theme header, `block.json`, `.wp-env.json`, `wp-config.php` | WordPress plugin, theme or site | `Requires at least`, `Requires PHP` headers | `composer.lock`, JavaScript lockfile |
| `shopify.app.toml`; or `layout/theme.liquid` with `config/settings_schema.json` | Shopify app; Shopify theme | `api_version` in the app TOML | JavaScript lockfile |
| `*.mjml` files, `mjml` in `package.json` | MJML email templates | `mjml` version | JavaScript lockfile |
| `ProjectSettings/ProjectVersion.txt`, `*.uproject`, `project.godot` | Unity, Unreal Engine, Godot | Editor or engine version in those files | `Packages/packages-lock.json` (Unity) |
| `.tool-versions`, `mise.toml`, `.nvmrc`, `.devcontainer/`, `Dockerfile` `FROM`, CI matrices | Any | Versions the team actually runs | |

When sources disagree (for example `.python-version` says 3.12 and CI tests 3.10 to 3.13), the CI matrix and the declared minimum win for what code may use; ask if it matters.

## Find the commands the project uses

Look in this order and stop at the first that answers: CI workflow files (what must pass to merge), task runners (`Makefile`, `justfile`, `Taskfile.yml`, `package.json` scripts, `tox.ini` or `noxfile.py`, `composer.json` scripts, Gradle tasks, `Rakefile`), then `CONTRIBUTING.md` and the README. Use the defaults below only when the project defines nothing, and say so.

| Stack | Compile or build | Test | Lint | Format check | Types | Dependency audit |
|---|---|---|---|---|---|---|
| Python | (none) | `pytest` | `ruff check` | `ruff format --check` or `black --check` | `mypy` or `pyright` | `pip-audit` |
| Go | `go build ./...` | `go test -race ./...` | `go vet ./...`, `golangci-lint run` | `gofmt -l .` | compiler | `govulncheck ./...` |
| Rust | `cargo check --all-targets` | `cargo test` | `cargo clippy --all-targets` | `cargo fmt --check` | compiler | `cargo audit` or `cargo deny check` |
| JVM (Maven) | `./mvnw -q compile` | `./mvnw verify` | configured plugins (Checkstyle, SpotBugs, PMD, detekt) | `./mvnw spotless:check` if configured | compiler | dependency-check plugin if configured |
| JVM (Gradle) | `./gradlew assemble` | `./gradlew test` | `./gradlew check` | `spotlessCheck` or `ktlintCheck` if configured | compiler | as configured |
| .NET | `dotnet build` | `dotnet test` | analyzers in the build | `dotnet format --verify-no-changes` | compiler with nullable on | `dotnet list package --vulnerable --include-transitive` |
| C and C++ | `cmake --preset <name>` then `cmake --build` | `ctest --output-on-failure` | `clang-tidy` | `clang-format --dry-run -Werror` | compiler warnings | (manual) |
| PHP | `composer validate` | `vendor/bin/phpunit`, `vendor/bin/pest` or `php artisan test` | `vendor/bin/phpstan analyse` | `vendor/bin/pint --test` or `php-cs-fixer fix --dry-run` | PHPStan or Psalm | `composer audit` |
| Ruby | (none) | `bin/rails test` or `bundle exec rspec` | `bundle exec rubocop` | same | Sorbet or Steep if present | `bundle exec bundle-audit check`, Brakeman |
| Swift | `swift build` | `swift test`, or `xcodebuild test -scheme <s>` | SwiftLint if configured | `swift format lint -r .` if configured | compiler | (manual) |
| Firmware | `pio run`, `west build`, `idf.py build`, or the cross build | host unit tests (`pio test -e native`, Unity, CppUTest) | `cppcheck`, `clang-tidy`, MISRA checker if licensed | `clang-format` | compiler `-Wall -Wextra` | (manual) |
| Salesforce | LWC: `npm run lint` | LWC: `npm run test:unit`; Apex tests need an org | Code Analyzer (PMD rules) | Prettier with the Apex plugin | compiler on deploy | (manual) |
| JavaScript and TypeScript (web, Node.js, NestJS) | the `build` script | the `test` script (Vitest or Jest), `e2e` with Playwright | the `lint` script (ESLint) | `prettier --check .` if configured | `tsc --noEmit`, `vue-tsc --noEmit`, `svelte-check`; `ng build` and `next build` type-check | `npm audit --omit=dev` or the pnpm and Yarn equivalents |
| React Native and Expo | `npx expo export` or the native builds | the `test` script (`jest-expo`) | the `lint` script | Prettier if configured | `tsc --noEmit` | `npx expo-doctor`, `npm audit --omit=dev` |
| Flutter | `flutter build <target>` | `flutter test` | `flutter analyze` | `dart format --output=none --set-exit-if-changed .` | analyzer | `flutter pub outdated` (no advisory audit) |
| WordPress | `npm run build` (`@wordpress/scripts`) | `vendor/bin/phpunit`; `wp-scripts test-unit-js` | `vendor/bin/phpcs --standard=WordPress` | same | PHPStan if configured | `composer audit`, `npm audit` |
| Shopify theme | (none) | Playwright against a development theme if present | `shopify theme check` | Prettier with the Liquid plugin if configured | (none) | (none) |
| Unity, Godot | Unity `-batchmode -quit -executeMethod <BuildMethod>`; Godot `--headless --export-release <preset>` | Unity `-batchmode -runTests -testPlatform EditMode`; GUT or gdUnit4 | analyzers if configured | `dotnet format` for C# if configured | compiler | (manual) |

A tool the project does not configure is not added; run what exists and list the gap in the report. Documentation tools (Sphinx or MkDocs with doctests, Go `Example` tests, rustdoc doctests, Javadoc, Dokka, .NET XML docs, DocC, YARD) and OpenAPI generators follow the same rule; `../engineering-practices/references/docs-and-decisions.md` covers what to write.

## Working in an unfamiliar stack

Answer these from the code before writing the first line:

| Question | Typical answers |
|---|---|
| How are errors reported? | Exceptions; returned errors (`error`, `Result`); error codes; a project-wide error type or problem-details mapper |
| How is absence modeled? | `None` or `null` with type checking; `Optional`; nullable types (`T?`); zero values; sentinels |
| How are resources released? | `with`, `defer`, RAII and destructors, `using`, try-with-resources, `ensure` |
| What is the concurrency model? | Threads, an event loop, goroutines, coroutines, actors, tasks; what must never block it |
| How are dependencies wired? | Constructor injection through a container, module-level singletons, function parameters, framework conventions |
| How are tests organized? | Location, naming, fixtures or factories, what is faked and what runs for real |
| How are logging and configuration done? | Which logger, structured or not; environment variables, settings classes, config files |

Then write the thinnest slice, compile or type-check it at once, and let the compiler, linter and tests correct you early.

- **Translate intent, not syntax.** Do not carry idioms across languages: getters and setters in Python, exceptions for control flow in Go, deep inheritance in Rust, checked-exception wrapping in Kotlin.
- **Traps that recur in every stack:** blocking calls inside an async runtime; N+1 queries behind an ORM (`../engineering-practices/references/performance.md`); naive date-times and local time zones; binary floating point for money (`../engineering-practices/references/spec-and-units.md`); unbounded concurrency or queues; mutable global state in long-lived workers; outbound calls without timeouts (`../engineering-practices/references/resilience.md`).

## References

### Back-end languages and frameworks

| Stack | Read | Read when |
|---|---|---|
| Python | `references/python.md` | Any Python: environments and package managers, typing, async, packaging, pytest |
| Django and Django REST Framework | `references/django.md` | Models and the ORM, migrations, transactions, DRF serializers and permissions, Celery tasks |
| FastAPI | `references/fastapi.md` | FastAPI with Pydantic v2 and SQLAlchemy 2.0, dependencies, lifespan, async database access, moving endpoints from Django |
| Go | `references/go.md` | Modules and layout, errors, context, goroutines, HTTP servers, testing, profiling |
| Rust | `references/rust-engineering.md` | Cargo workspaces, ownership idioms, error types, traits, Tokio, testing, compile times (security review of Rust: `../code-security-review/references/rust.md`) |
| Java and Spring Boot | `references/java-spring.md` | Modern Java by version, Spring Boot configuration, transactions, JPA and Hibernate, Spring tests, virtual threads |
| Kotlin | `references/kotlin.md` | Kotlin on the server (Spring, Ktor), coroutines and Flow, Java interop, Android and multiplatform pointers |
| C# and .NET | `references/dotnet.md` | ASP.NET Core, dependency injection lifetimes, EF Core, async, testing, Blazor, library licensing changes |
| C++ | `references/cpp.md` | CMake and package managers, ownership and lifetimes, modern standard features, concurrency, sanitizers in the dev loop (memory-safety review: `../code-security-review/references/c-and-cpp.md`) |
| PHP, Laravel and Symfony | `references/php-laravel.md` | Modern PHP, Composer, Eloquent, queues, configuration caching, Octane, Pest and PHPUnit, Doctrine and Messenger |
| Ruby and Rails | `references/ruby-rails.md` | Active Record, migrations, callbacks, background jobs, Hotwire, RSpec and Minitest, Rails upgrades |
| Swift | `references/swift.md` | Swift Package Manager and Xcode projects, Swift 6 concurrency, ARC, protocols and generics, Swift Testing, SwiftUI state, server-side Swift |

### Systems, platforms and tools

| Stack | Read | Read when |
|---|---|---|
| Embedded firmware | `references/embedded.md` | Microcontrollers, interrupts, RTOS tasks, memory budgets, bus protocols, power, watchdogs, host and hardware-in-the-loop tests |
| Salesforce | `references/salesforce.md` | Apex, triggers, governor limits, SOQL, asynchronous Apex, Lightning Web Components, integrations, `sf` CLI deployments |
| Command-line tools | `references/cli-tools.md` | Designing or changing a CLI in any language: arguments, output streams, exit codes, configuration, signals, tests, distribution |

### Architecture and modernization

| Topic | Read | Read when |
|---|---|---|
| System design and services | `references/architecture-and-services.md` | Designing a system, sizing it, choosing a datastore, drawing service boundaries, sagas, multi-tenancy, deciding whether to split a monolith |
| Legacy modernization | `references/legacy-modernization.md` | Assessing an old system, recovering its specification from code, characterization and golden-master tests, shadow traffic, data cutover, runtime and framework upgrades |

## Front-end, web and mobile

Read `references/web-frontend-foundations.md` first for any browser front end; the framework references add only what differs. Design, interaction, forms UX and accessibility rules stay in `../ui-distiller/GUIDE.md`, `../ui-rules.md`, `../interaction-feedback.md`, `../forms-conversion.md` and `../responsive-accessibility.md`.

| Stack | Read | Read when |
|---|---|---|
| Any browser front end | `references/web-frontend-foundations.md` | First, for any front-end framework task: rendering modes, kinds of state, data fetching and caching, forms wiring, shared types, routing, test layers, builds and public environment variables, service workers, upgrades, front-end security sinks |
| React | `references/react.md` | Components, hooks and effects, state, React 19 actions and forms, Suspense and error boundaries, React Compiler, typing, testing, class-component migration, the 18 to 19 upgrade |
| Next.js | `references/nextjs.md` | App Router conventions, server and client components, data access layer, caching by major version (14, 15, 16), server actions, route handlers, middleware or proxy, images and fonts, self-hosting, upgrades |
| Vue and Nuxt | `references/vue-nuxt.md` | Reactivity rules, components and composables, Pinia, Vue Router, Nuxt data fetching, server routes and runtime config, JSDoc-typed Vue, Vue 2 and Nuxt 3 upgrades |
| Angular | `references/angular.md` | Standalone components, signals versus RxJS, HTTP and interceptors, NgRx, routing, typed forms, SSR and hydration, zoneless change detection, testing, `ng update` migrations |
| JavaScript and Node.js runtime | `references/javascript-runtime.md` | Plain JavaScript or Node.js: feature availability by target, async control flow and concurrency limits, ESM and CommonJS, streams, child processes, graceful shutdown, browser APIs, JSDoc type checking |
| NestJS | `references/nestjs.md` | Modules and dependency injection, the request pipeline, DTO validation, default-deny guards and object-level authorization, configuration, uniqueness races, testing, migration from Express, Nest 11 changes |
| GraphQL | `references/graphql.md` | Server choice, schema idioms, resolvers with per-request DataLoaders, error masking, depth, cost and alias limits, subscriptions, federation, client caches and code generation (contract rules stay in `../engineering-practices/references/api-contracts.md`) |
| Realtime | `references/realtime-websockets.md` | Choosing polling, SSE, WebSockets or WebRTC; message envelopes and resync, heartbeats, backpressure, reconnect with jitter, authorization per message, fan-out, proxies and deploys |
| Mobile apps, any framework | `references/mobile-cross-platform.md` | Choosing React Native, Flutter, Capacitor, PWA or native; configuration and secrets, offline sync, deep links, push, device test matrix, releases and store rules, over-the-air updates |
| React Native and Expo | `references/react-native-expo.md` | Expo or bare, New Architecture, navigation, lists, Reanimated, platform differences, storage, native modules, EAS Build and Update, upgrades |
| Flutter | `references/flutter.md` | Dart 3 idioms, widgets and disposal, Riverpod or Bloc, go_router, isolates and platform channels, profiling, widget and golden tests, release builds and symbols |
| HTML email | `references/html-email-mjml.md` | MJML templates, client constraints (classic Outlook, Gmail clipping, dark mode), build-time compilation, sending pipeline, sender authentication, rendering tests |
| WordPress and WooCommerce | `references/wordpress.md` | Plugins and hooks, blocks and themes, REST routes, capabilities, nonces and escaping, query performance, object cache and WP-Cron, HPOS and block checkout, licensing |
| Shopify | `references/shopify.md` | Themes and Liquid, theme app extensions, Admin API apps, cost-based limits, webhooks, checkout extensions and Functions, headless storefronts, API version upgrades |
| Game development | `references/game-development.md` | Engine choice, fixed-step loop, frame budgets and profiling, Unity, Unreal and Godot specifics, multiplayer authority and prediction, save data, builds |

## Stack detector

`scripts/detect_stack.py` is a read-only, standard-library helper. It walks the repository to a bounded depth, reads only known manifest, lockfile, tool-config and CI files, and prints for each subproject the stack, the version pins with the file each came from, the package manager, the tools configured, the commands defined in task runners and CI, and conflicts such as two lockfiles for one ecosystem. It covers the back-end stacks above and also recognizes JavaScript frameworks, Flutter, WordPress, Shopify and game engines. It never runs project code, never uses the network and never opens `.env` files or other credential-like names.

```bash
python3 <productcraft>/modules/stacks/scripts/detect_stack.py .
python3 <productcraft>/modules/stacks/scripts/detect_stack.py services/billing --json
python3 <productcraft>/modules/stacks/scripts/detect_stack.py . --max-depth 2
```

`<productcraft>` is the folder where the ProductCraft skill is installed. Commands it lists under "defaults" were not found in the project; confirm them before relying on them. Exit status: 0 when at least one stack was found, 1 when none was, 2 for a bad argument or a missing root. The report is a starting point; the files it cites are the evidence.

## What to report

Add these to the workflow module's report:

- The stack and versions detected, with the file each came from, and any version you assumed.
- The commands that ran (build, tests, lint, format, types) with their results, and the ones the project lacks or that could not run, with the reason.
- Version-sensitive behavior the change relies on (for example "needs Python 3.11 for `TaskGroup`", "Spring Boot 3.4 or later for `@MockitoBean`").
- Anything only the user can do: deploying to an org or device, flashing hardware, publishing a package, approving an upgrade.

## Working with other ProductCraft modules

- `../engineering-workflow/GUIDE.md`: how the change is planned, made and verified. This module tells it which commands prove the change in this stack.
- `../engineering-practices/GUIDE.md`: API contracts, data and migrations, resilience, performance, observability, CI and release, dependencies, docs and ADRs, large refactors, TypeScript.
- `../code-security-review/references/language-pitfalls.md`, `../code-security-review/references/rust.md`, `../code-security-review/references/c-and-cpp.md`: security traps per language and framework; read the matching section when the change touches input, auth, queries or files.
- `../codebase-map/GUIDE.md`: entry points, routes and the import graph of an unfamiliar repository; pair it with the stack detector.
- `../language-choice.md`: a new project or component whose language is not fixed yet.
- `../agent-safety/GUIDE.md`: the stop-check before destructive commands, and secrets in build or deploy configuration.
