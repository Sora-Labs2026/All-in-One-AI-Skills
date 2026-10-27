# JavaScript in the browser and on Node.js

Read this when you write or review plain JavaScript or TypeScript runtime code: language features and their availability, async control flow, ES modules and CommonJS, Node.js services and scripts, browser APIs, and JSDoc-typed JavaScript projects. Type-system practice is in `../../engineering-practices/references/typescript.md`; framework code is in the framework references.

## Know the targets before using a feature

- **Node.js:** read `engines`, `.nvmrc` or the CI matrix. Use an even-numbered LTS line. Node.js 20 reached end of life in April 2026; 22 and 24 are the LTS lines in late 2026.
- **Browsers:** read `browserslist` (in `package.json` or `.browserslistrc`) or the framework default. Check features on Baseline status or caniuse before using them without a polyfill.
- Newer syntax is fine when the targets support it or the build transpiles it. Runtime APIs (`Object.groupBy`, iterator helpers, `Temporal`) are not transpiled; they need target support or a polyfill.

| Year | Features worth using |
|---|---|
| ES2022 | Class fields and `#private`, top-level `await` (modules only), `.at()`, `Object.hasOwn`, `Error` `cause` |
| ES2023 | `findLast`, non-mutating `toSorted`, `toReversed`, `toSpliced`, `with` |
| ES2024 | `Object.groupBy`, `Map.groupBy`, `Promise.withResolvers`, RegExp `v` flag |
| ES2025 | Iterator helpers (`.map`, `.filter`, `.take` on iterators), Set methods (`union`, `intersection`, `difference`), `Promise.try`, JSON modules with import attributes, `RegExp.escape` |

`Temporal` (dates and times without the `Date` pitfalls) began shipping in engines in 2025; use the polyfill or a date library until all targets have it.

## Language pitfalls that still bite

- `??` for defaults when `0`, `""` or `false` are valid; `||` replaces them.
- Numbers are binary floating point: money in integer minor units or a decimal library; identifiers above 2^53 - 1 as strings or `BigInt` (`../../engineering-practices/references/spec-and-units.md`).
- `===` everywhere; `==` only for the deliberate `x == null` check, if the project allows it.
- `sort()` without a comparator sorts by string: `[10, 9, 1].sort()` gives `[1, 10, 9]`. Use `(a, b) => a - b`, or `localeCompare` and `Intl.Collator` for text.
- Dates: `new Date("2026-03-01")` is UTC midnight, `new Date(2026, 2, 1)` is local midnight. Store and send ISO 8601 with an offset; format with `Intl.DateTimeFormat` at display time.
- `structuredClone` for deep copies of plain data; spread is shallow.

## Async control flow

- **Every promise is awaited, returned or explicitly handled.** A floating promise loses its error. With TypeScript, enable `@typescript-eslint/no-floating-promises`.
- **Catch where you can act** (retry, map to an error response, show an error state), not in every function. Do not turn failures into `null` silently; the caller then cannot tell "not found" from "broken".
- **`fetch` resolves on HTTP errors.** Check `response.ok` (or the status) before reading the body.
- **Combinators:** `Promise.all` fails fast and suits all-or-nothing work; `Promise.allSettled` suits independent tasks whose failures you report one by one; `Promise.any` takes the first success.
- **Independent awaits in sequence add up their latency.** Start them together. `array.forEach(async ...)` does not wait for anything; use `for ... of` with `await` for sequential work or `Promise.all` for parallel.
- **Bound concurrency** when mapping over large inputs; an unbounded `Promise.all` over thousands of items exhausts sockets, rate limits and memory.

```js
// Run fn over items with at most `limit` in flight; results keep input order.
export async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
```

- **Timeouts and cancellation:** `fetch(url, { signal: AbortSignal.timeout(5000) })`; combine a user cancel and a timeout with `AbortSignal.any([a, b])`. Pass signals down through your own async functions. See `../../engineering-practices/references/resilience.md` for retry policy.
- **The event loop:** promise callbacks (microtasks) run before timers and I/O callbacks. A long synchronous loop blocks everything, rendering in the browser and every request in Node.js. Split work, yield (`await scheduler.yield()` where supported, otherwise `setTimeout`), or move it to a worker.

## Modules

- New code uses ES modules (`"type": "module"`, or `.mjs`). `.cjs` marks CommonJS files inside an ESM package.
- Since Node.js 22.12 and 20.19, `require()` can load synchronous ES modules, which eases mixed codebases. ESM can `import` CommonJS; named imports from CJS work only when Node.js can detect them statically.
- Libraries declare entry points in `exports` with conditions; list `types` first:

```json
{
  "type": "module",
  "exports": {
    ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js", "require": "./dist/index.cjs" }
  },
  "sideEffects": false
}
```

- Shipping both ESM and CJS builds can load two copies of the package (the dual package hazard), breaking `instanceof` and module-level state. Prefer ESM-only when consumers allow it; check the published package with `npx publint` and `npx @arethetypeswrong/cli --pack`.
- ESM has no `__dirname`; use `import.meta.dirname` and `import.meta.filename` (Node.js 20.11+) or `fileURLToPath(import.meta.url)`.
- Circular imports surface as "Cannot access X before initialization". Move shared code into a third module.
- Barrel files (`index.js` re-exporting a folder) slow builds and tests and defeat tree shaking; import from the defining module.

## Node.js essentials

- **Use built-ins before dependencies:** `fetch`, `node:test` with `--test`, `--watch`, `--env-file=.env`, `util.parseArgs`, `util.styleText`, `crypto.randomUUID`. Node.js 22.18 and later run TypeScript files by stripping types, for erasable syntax only (no `enum`, no namespaces with values, no parameter properties); type-check separately.
- **Streams:** use `pipeline` from `node:stream/promises`; it propagates errors and backpressure and closes every stream. Bare `.pipe()` leaks file handles on error.
- **CPU-heavy work** (image processing, large JSON, hashing) blocks the event loop; move it to `worker_threads` or another service.
- **Child processes:** `execFile` or `spawn` with an argument array. Never pass interpolated user input to `exec` or `shell: true`; that is command injection.
- **File paths from users:** `path.resolve(base, input)` and confirm the result still starts with `base + path.sep` before reading or writing.
- **EventEmitter:** an unhandled `error` event crashes the process; attach an `error` listener. The "possible memory leak detected" warning usually means listeners are added per request and never removed.
- **Unhandled rejections terminate the process** (default since Node.js 15). Keep it that way; log, flush and exit, and let the supervisor restart.
- **Graceful shutdown:** on `SIGTERM`, stop accepting connections, finish in-flight requests within a deadline, close pools, then exit.

```js
const server = app.listen(port);
process.on("SIGTERM", () => {
  server.close(async () => {            // stops new connections, waits for open ones
    await db.end();
    process.exit(0);
  });
  setTimeout(() => process.exit(1), 10_000).unref(); // hard deadline
});
```

- **Memory leaks:** compare heap snapshots (`node --inspect`, Chrome DevTools) taken some minutes apart under steady load; look for growing maps, caches without limits, closures held by timers or listeners.

## Browser APIs worth knowing

| Need | API | Note |
|---|---|---|
| Cancel or time out requests | `AbortController`, `AbortSignal.timeout` | Pass the signal to `fetch` and your own functions |
| Heavy computation off the main thread | Web Workers (with `postMessage` or a wrapper such as Comlink) | Data is copied unless transferred |
| Structured client storage | IndexedDB (through a small wrapper such as `idb`) | Asynchronous, large quotas, can be evicted |
| Small preferences | `localStorage` | Synchronous, strings only, a few MB, readable by any script on the origin: never tokens or personal data |
| Lazy loading, infinite scroll | `IntersectionObserver` | Disconnect when done |
| Element size changes | `ResizeObserver` | Avoid writing layout inside the callback in a loop |
| Sync across tabs | `BroadcastChannel`, the `storage` event | For sign-out in all tabs |
| Pause work in background tabs | `document.visibilityState`, `visibilitychange` | Timers are throttled in hidden tabs anyway |
| Measure | `performance.mark`, `performance.measure`, `PerformanceObserver` | Long tasks and long animation frames for INP work |

`navigator.onLine` only says whether a network interface exists; treat failed requests as the real offline signal.

## JSDoc-typed JavaScript

For projects that keep `.js` files but want type checking:

- Add `"allowJs": true, "checkJs": true, "noEmit": true, "strict": true` to `jsconfig.json` or `tsconfig.json` (or `// @ts-check` per file) and run `tsc --noEmit` in CI.
- Annotate public functions and shared shapes; inference covers most locals.

```js
/** @typedef {{ id: string, email: string, role: "admin" | "member" }} User */

/**
 * @param {User[]} users
 * @param {User["role"]} role
 * @returns {User[]}
 */
export function byRole(users, role) {
  return users.filter((u) => u.role === role);
}

/** @type {import("./config.js").AppConfig} */
const config = loadConfig();
```

- Reuse types across files with `import("./file.js").TypeName` or a `.d.ts` file; `@template` for generics; `@satisfies` (TypeScript 5.0+) to check an object literal against a type.
- The same boundary rule applies: parse external data with a schema, do not cast it with `@type`.

## Tooling

- ESLint 9 and later use flat config (`eslint.config.js`). Formatting belongs to Prettier or the project's formatter, not lint rules.
- Tests: the project's runner (Vitest, Jest or `node:test`). Use fake timers for time-dependent code and `await expect(promise).rejects.toThrow(...)` for async errors.

## Common breakages

| Symptom | Cause | Fix |
|---|---|---|
| `ERR_REQUIRE_ESM`, "Cannot use import statement outside a module" | Module system mismatch | Align `"type"`, file extensions and `exports`; upgrade Node.js for `require(esm)` |
| Process exits on an unrelated error | Unhandled promise rejection | Await or handle the promise at its source |
| Code after a loop runs before the loop's work finishes | `forEach` with an async callback | `for ... of` with `await`, or `Promise.all` |
| Page freezes during processing | Long synchronous task | Chunk and yield, or a Web Worker |
| Too many open files, socket errors under load | Unbounded concurrency | Limit concurrency; reuse connections |

## Done when

- [ ] Features used are supported by the declared Node.js and browser targets, or polyfilled.
- [ ] No floating promises; errors are handled where something can be done about them.
- [ ] Outbound calls have timeouts; long work does not block the event loop.
- [ ] Lint, type check (TypeScript or `checkJs`) and tests pass with the project's commands.
