# Vite and Bun

Read this when you configure or debug Vite (`vite.config.*`, plugins, the dev server, dependency pre-bundling, library mode, Vitest) or when a project uses Bun as its runtime, package manager, test runner or bundler. Next.js has its own bundler (`nextjs.md`); public environment variables, bundle analysis and service workers are in `web-frontend-foundations.md`; Node.js runtime practice is in `javascript-runtime.md`.

## Vite

### Versions that change the advice

Read `vite` in the lockfile before relying on an option name.

| Version | What matters |
|---|---|
| 5 (Nov 2023) | Rollup 4; Node.js 18 or later |
| 6 (Nov 2024) | Environment API (experimental) for frameworks with several runtimes (client, SSR, edge) |
| Security releases (Jan 2025, 6.0.9, 5.4.12, 4.5.6) | The dev server only accepts expected `Host` headers (`server.allowedHosts`) and restricts cross-origin requests (`server.cors`); later 2025 patches closed several file-read bypasses on dev servers exposed to the network |
| 7 (Jun 2025) | Node.js 20.19+ or 22.12+; default build target `baseline-widely-available`; ships as ESM only |
| 8 (2026) | Rolldown bundles and pre-bundles, Oxc transforms and minifies; `build.rollupOptions` is renamed `build.rolldownOptions` and esbuild-specific options have Oxc or Rolldown equivalents (old names kept as deprecated aliases for a while) |

Use Vite for single-page apps, libraries and the frameworks built on it (Vue, Nuxt, SvelteKit, Astro, Solid, React Router, TanStack Start). Next.js and the Angular CLI wrap their own build pipelines; configure those through the framework.

### Configuration

```ts
// vite.config.ts
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), ["VITE_"]);     // explicit prefix list
  return {
    plugins: [react()],
    base: env.VITE_BASE_PATH ?? "/",                       // subpath deployments
    define: { __APP_VERSION__: JSON.stringify(process.env.npm_package_version) },
    server: command === "serve" ? { port: 5173 } : undefined,
    build: { sourcemap: "hidden" },                        // upload maps, do not serve them
  };
});
```

- **Public variables:** only `VITE_`-prefixed variables (or the configured `envPrefix`) reach client code through `import.meta.env`, and they are inlined at build time. Never set `envPrefix` to `""`.
- **`loadEnv(mode, root, "")` loads every variable**, including server secrets. That is acceptable for values the config itself uses, never for anything passed into `define`, which writes it into the bundle.
- `define` performs text replacement: values must be `JSON.stringify`-ed, and the keys should be unmistakable identifiers.
- `.env.local` and `.env.[mode].local` are for one machine and stay out of version control.
- The config file runs in Node.js at every build. Keep network calls and secrets out of it.
- Path aliases: keep `tsconfig.json` `paths` as the source and mirror them with `vite-tsconfig-paths` or the built-in option where your Vite version has one, rather than a hand-written list that drifts.

### Plugins

- Reach for the framework plugin and a few maintained plugins before writing one. Treat a plugin like any dependency: it runs with full access at build time; check maintenance, license and that its peer range covers your Vite major (`../../engineering-practices/references/dependencies.md`).
- Order matters. `enforce: "pre" | "post"` moves a plugin relative to Vite's core plugins; `apply: "serve" | "build"` limits it to one command.
- When you do write one, start it inline in the config. The hooks you need most: `transform` (change module code), `resolveId` plus `load` (virtual modules: user code imports `virtual:name`, the plugin resolves it to `"\0virtual:name"` so other plugins skip it), `transformIndexHtml`, `configureServer` (dev middleware) and `hotUpdate` (Vite 6 and later; `handleHotUpdate` is the older hook).
- Debug the pipeline with `vite-plugin-inspect` and `vite --debug`; profile a slow dev server with `vite --profile`, which writes a CPU profile you open in the browser's performance tools.
- Type checking is not a plugin's job by default: `vite build` strips types. Run `tsc --noEmit` or `vue-tsc --noEmit` in CI; `vite-plugin-checker` only adds an overlay during development.

### Dev server

- **Proxy** API calls to avoid CORS during development: `server.proxy: { "/api": { target: "http://localhost:8080", changeOrigin: true } }`; add `ws: true` for WebSockets.
- **Containers and remote machines:** `server.host: true` binds all interfaces. Add the hostnames you use to `server.allowedHosts`; setting it to `true` disables the DNS-rebinding protection. Behind a reverse proxy set `server.hmr.clientPort` (and `protocol`) so the browser reaches the HMR socket.
- **Monorepos:** files outside the project root are blocked; widen `server.fs.allow` to the workspace root only.
- **Never expose a dev server to untrusted networks,** and keep Vite on current patch releases; it is not built to be a public server.
- **Speed:** import from defining modules instead of barrel files, write explicit file extensions in large codebases (each omitted extension costs extra file-system checks), and pre-transform entry points with `server.warmup.clientFiles`.

### Dependency pre-bundling and CommonJS

Vite converts dependencies to ESM once and caches the result in `node_modules/.vite`.

- "new dependencies optimized, reloading" during navigation means a dependency was found late; add it to `optimizeDeps.include`.
- CommonJS-only packages that fail with "does not provide an export named ..." or "require is not defined": add them to `optimizeDeps.include`, switch between default and named imports, and check whether the package ships an ESM build.
- Linked workspace packages are not pre-bundled; they must be valid ESM or be listed in `include`.
- After changing dependencies, switching branches or patching a package, a stale cache causes phantom errors: run once with `vite --force` (or delete `node_modules/.vite`).
- Development and production are bundled differently, so interop problems can appear in only one of them. Run `vite build && vite preview` before calling a change done.

### SSR and library mode

- In SSR builds, `ssr.noExternal` bundles a package that breaks when loaded from `node_modules` (ESM-only or CSS-importing packages); `ssr.external` keeps native or Node-only packages out of the bundle.
- **Library mode** (`build.lib`): list every peer dependency (and `react/jsx-runtime` for React libraries) as external, or consumers get two copies of the framework. Types are not emitted; generate them with a declaration plugin or `tsc --emitDeclarationOnly`. Declare entry points in `exports` and check the package with `publint` and `@arethetypeswrong/cli` (`javascript-runtime.md`).

### Production builds

- `vite preview` serves the build for a smoke test. It is not a production server; deploy `dist/` to a static host or a real server.
- Default chunking (one chunk per dynamic import plus shared chunks) is usually right. Add manual vendor chunks only with analyzer evidence; one chunk per package produces hundreds of requests. Chunking options differ between Rollup (Vite 7 and earlier) and Rolldown (Vite 8).
- **Stale chunks after a deploy:** open tabs request old hashed files. Keep the previous build's assets available for a while, and handle the `vite:preloadError` window event by reloading the page once (guard against reload loops).
- Add `@vitejs/plugin-legacy` only when analytics show real users on browsers that need it; it adds a second build and larger bundles.

### Vitest in a Vite project

- Vitest reads the Vite config (or `vitest.config.ts`); the `test` block sets `environment` (`jsdom`, `happy-dom`), setup files and coverage. Projects (`test.projects` in recent versions) separate unit, component and browser runs.
- Browser mode runs tests in a real browser engine (stable in Vitest 4, October 2025).
- Do not keep Jest and Vitest side by side for the same code; migrate deliberately or stay.

### Common Vite failures

| Symptom | Cause | Fix |
|---|---|---|
| Blank page after deploy to a subpath, 404 on assets | `base` not set | Set `base` to the deployed path |
| "Blocked request. This host is not allowed" | Host check | Add the hostname to `server.allowedHosts` |
| HMR does not connect behind a proxy or in a container | Wrong HMR client port or protocol | `server.hmr.clientPort`, `server.hmr.protocol` |
| `process is not defined` | A library expects Node.js globals | Replace with `import.meta.env`, `define` only the specific key, or choose a browser build of the library |
| Works in dev, fails after build | CJS interop or tree-shaken side effects | Test with `vite preview`; fix `optimizeDeps` or `sideEffects` |
| Type errors shipped to production | Build does not type-check | Add the type checker to CI |
| Every request slow in a large app | Barrel imports, implicit extensions, a slow plugin hook | Direct imports, explicit extensions, `vite --profile` |

## Bun

Bun is four tools: a JavaScript runtime (built on JavaScriptCore rather than V8), a package manager, a test runner and a bundler. Adopt them separately; using Bun only to install packages or run tests while production stays on Node.js is the lowest-risk start.

### Versions

1.0 (September 2023); 1.1 (April 2024) added Windows; 1.2 (January 2025) made the text lockfile `bun.lock` the default (older projects have the binary `bun.lockb`) and added built-in PostgreSQL (`Bun.sql`) and S3 clients; 1.3 (October 2025) continued Node.js compatibility work and built-in clients. Releases add Node.js APIs often: read `bun --version`, the `packageManager` field and the CI image, and check the release notes before relying on a behavior.

### When to use it, and when not

| Fits | Be careful |
|---|---|
| New TypeScript services, scripts and CLIs where the team accepts the runtime | A production service that depends on Node.js APIs Bun only partly implements |
| Faster installs and tests in CI | Native addons built against V8 internals, profilers and monitoring agents that hook V8 |
| Single-file executables (`bun build --compile`) | Platforms without a Bun runtime (some serverless and PaaS offerings) |
| Projects that want one tool for run, install and test | Teams without anyone to own runtime upgrades and incidents |

Do not switch an existing project's runtime or package manager as a side effect of another change; it is its own change, agreed with the user.

### Package manager

- Commit `bun.lock`; keep one lockfile. When moving a project to Bun, the first `bun install` can import an existing lockfile (check which formats your version reads), then remove the old lockfile, update CI, Dockerfiles and `packageManager` in the same reviewed change.
- CI installs with `bun install --frozen-lockfile`, which fails instead of changing the lock.
- **Lifecycle scripts:** Bun does not run dependencies' `postinstall` and similar scripts unless the package is listed in `trustedDependencies` in `package.json` (a small built-in list of popular packages is trusted by default). This blocks a common supply-chain attack path, and it is also why a package that downloads a binary or generates code at install fails under Bun. `bun pm untrusted` lists blocked scripts; trust a package deliberately, after reviewing what its script does.
- Workspaces use the `workspaces` array; run a script in one package with `bun run --filter <name> <script>`. `bun outdated` lists updates; recent versions include `bun audit` for advisories.

### Runtime

- **Node.js compatibility** is broad but incomplete. Check Bun's compatibility page for each `node:` module the code uses and run the real test suite under Bun before switching. Node-API addons usually work; code using V8-specific APIs (`node:v8` heap snapshots, some APM agents) often does not.
- **Shebangs:** `bun run dev` runs a tool whose binary starts with `#!/usr/bin/env node` under Node.js. `bun --bun run dev` forces Bun; use it deliberately and test.
- **`.env` files load automatically** (`.env`, `.env.<NODE_ENV>`, `.env.local`), unlike Node.js. Secrets in those files reach every script and test; `bun test` sets `NODE_ENV=test`, so `.env.test` applies there.
- **TypeScript runs without type checking.** Run `tsc --noEmit` in CI with `@types/bun` installed.
- **Bun-only APIs** (`Bun.serve`, `Bun.file`, `bun:sqlite`, `Bun.sql`, `Bun.password`) are fast and convenient but tie the code to Bun. If the code may need to run on Node.js, keep them behind one module with a Node.js implementation or tests that run on both.
- Containers: use the official image with a pinned version tag, run as a non-root user, and handle `SIGTERM` for graceful shutdown as on Node.js (`javascript-runtime.md`).

### Test runner

- `bun test` uses a Jest-like API from `bun:test`. Differences that bite during migration: module mocking uses `mock.module()` and does not hoist like `jest.mock`; there is no DOM, so component tests need a DOM library preloaded through `bunfig.toml` (`[test] preload = ["./happydom.ts"]` with happy-dom's global registrator); test files share more process state than Jest's per-file workers, so reset globals and module-level state.
- Keep one test runner per package. If component tests depend on Jest-specific transforms or environments, keep Jest or move to Vitest rather than half-migrating.

### Bundler

`bun build` suits servers, libraries and CLIs. For browser applications that rely on framework plugins, HMR and CSS handling, keep Vite or the framework's bundler.

### Common Bun failures

| Symptom | Cause | Fix |
|---|---|---|
| A package works with npm but its binary or generated files are missing | Lifecycle script blocked | Review the script, then add the package to `trustedDependencies` |
| `Cannot find module 'node:...'` or a missing method | Unimplemented Node.js API | Check the compatibility page and the Bun version; keep that code on Node.js |
| Different behavior between `bun run` and `node` | Script ran under Node.js through its shebang, or the other way round | Make the runtime explicit (`bun --bun`, or call `node`) |
| Tests pick up unexpected configuration | Automatic `.env` loading | Use `.env.test`, or pass explicit environment variables |
| CI changes the lockfile | Install without `--frozen-lockfile` | Use frozen installs; commit lockfile updates deliberately |

## Done when

- [ ] Build, type check (`tsc --noEmit` or `vue-tsc --noEmit`), tests and lint pass with the project's commands, and a production build was smoke-tested.
- [ ] No secret reaches the bundle through `VITE_` variables, `define` or `loadEnv` with an empty prefix (searched in the build output).
- [ ] The dev server is not exposed beyond the hosts the team needs, and Vite is on a current patch release.
- [ ] Library builds externalize every peer dependency and ship types that pass `publint` and `@arethetypeswrong/cli`.
- [ ] Bun adoption was agreed, covers runtime, package manager and tests separately, keeps one lockfile with frozen installs, and trusts lifecycle scripts only after review.
