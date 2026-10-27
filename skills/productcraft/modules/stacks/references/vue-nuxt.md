# Vue and Nuxt

Read this when you write or change Vue 3 components, composables, Pinia stores, Vue Router routes or a Nuxt app, including JavaScript-only Vue projects typed with JSDoc. Cross-framework practice (state kinds, data caching, forms, testing layers, builds, service workers, security sinks) is in `web-frontend-foundations.md`. Hybrid mobile shells (Capacitor, Quasar) are in `mobile-cross-platform.md`.

## Versions that change the advice

| Version | What matters |
|---|---|
| Vue 2 | End of life since 31 December 2023. Migrate (see Upgrading); do not start new work on it |
| Vue 3.4 (2023) | `defineModel` stable; faster reactivity |
| Vue 3.5 (2024) | Reactive props destructure stable (defaults via destructuring), `useTemplateRef`, `useId`, `onWatcherCleanup`, lazy hydration strategies for async components, `data-allow-mismatch` |
| Vapor mode (in development, 2025-26) | Opt-in compilation without the virtual DOM; do not adopt in production unless the project already has |
| Pinia 3 (2025) | Vue 3 only; Vuex is in maintenance, so new state goes in Pinia |
| Nuxt 4 (July 2025) | Source moves under `app/`; `useAsyncData` and `useFetch` calls with the same key share state; `data` and `error` default to `undefined`; separate TypeScript projects for app, server and shared code |

Read `vue`, `nuxt`, `pinia` and `vue-router` in the lockfile before relying on any of these.

## Reactivity rules

- Use `ref()` as the default for all state, primitive or object. `reactive()` is fine for a local object you never reassign or destructure.
- Destructuring a `reactive()` object or a store loses reactivity. Use `toRefs()`, or `storeToRefs()` for Pinia stores (actions can be destructured directly).
- Replacing a whole `reactive()` object (`state = reactive({...})`) disconnects every reference to the old one. Mutate its properties or use a `ref`.
- `computed()` is for derived values and must have no side effects. Do not write state inside a computed or a template expression.
- `watch` a specific source when you need the old value, lazy execution or async side effects; `watchEffect` when you want every dependency tracked automatically. Deep watching a large object is expensive; watch a getter of the field you need.
- Large data you replace rather than mutate (API results, chart data) belongs in `shallowRef`. Wrap class instances and third-party objects (map, editor, chart instances) with `markRaw` so Vue does not proxy them.
- The DOM is updated asynchronously; `await nextTick()` before reading layout after a state change.

## Components

- Use `<script setup>`. Declare props with `defineProps<Props>()` and defaults through destructuring (3.5+) or `withDefaults`; never mutate a prop, emit an event or use `defineModel` instead.
- Type emits with `defineEmits<{ (e: "select", id: string): void }>()` or the shorter named-tuple syntax.
- `defineModel()` (3.4+) implements `v-model` on a component, including named models (`v-model:title`).
- `provide`/`inject` with an `InjectionKey<T>` for typed dependency passing; provide a `readonly()` view plus explicit update functions rather than letting consumers mutate shared state.
- Template refs: `useTemplateRef<HTMLInputElement>("input")` (3.5+); the value is `null` until mounted.
- Keys in `v-for` are stable ids from the data. Never use `v-if` and `v-for` on the same element; filter in a computed.

## Composables

- Name them `useX`; call them synchronously in `setup` (not inside callbacks or after an `await` in a plain function), because lifecycle hooks and watchers bind to the active component.
- Accept refs, getters or plain values (`MaybeRefOrGetter<T>`) and read them with `toValue()` so callers can pass any of them.
- Clean up what you start: event listeners, intervals, observers, sockets. Use `onScopeDispose` (also works outside components) or `onUnmounted`; cancel in-flight requests when inputs change.

```ts
// composables/useSearch.ts (Vue 3.5+)
import { ref, watch, toValue, onWatcherCleanup, type MaybeRefOrGetter } from "vue";

export function useSearch(query: MaybeRefOrGetter<string>) {
  const results = ref<Hit[]>([]);
  const status = ref<"idle" | "loading" | "error">("idle");

  watch(() => toValue(query), async (q) => {
    if (!q) { results.value = []; status.value = "idle"; return; }
    const controller = new AbortController();
    onWatcherCleanup(() => controller.abort());     // a newer query cancels this one
    status.value = "loading";
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`, { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      results.value = await res.json();
      status.value = "idle";
    } catch (e) {
      if ((e as Error).name !== "AbortError") status.value = "error";
    }
  }, { immediate: true });

  return { results, status };
}
```

For most server data, prefer a query library (TanStack Vue Query, Pinia Colada) or Nuxt's `useFetch` over hand-written composables like this one.

## Pinia

- Prefer setup stores (`defineStore("cart", () => { ... })`): refs are state, computeds are getters, functions are actions. Return every piece of state, or SSR hydration and devtools miss it.
- Keep server data in a query cache; use Pinia for client state that is really shared (session-derived flags, cart before checkout, multi-step drafts).
- In server-side rendering, state must be created per request. Never keep state in module-level variables in code that runs on the server; one user's data leaks into another's response. Nuxt and `@pinia/nuxt` handle the store instance; your own singletons are your problem.
- Persisting a store to `localStorage` is a convenience for non-sensitive state only.

## Vue Router

- Lazy-load route components (`component: () => import("./views/Invoice.vue")`).
- Navigation guards return a value (`false`, a route location, or nothing) instead of calling the older `next()` callback. Guards are UX; the API authorizes.
- Validate `route.params` and `route.query` before use; they are strings from the URL.
- Typed routes come from file-based routing (Nuxt pages, or `unplugin-vue-router`).

## Nuxt

- **`useFetch` and `useAsyncData`** run on the server during SSR, send the result in the payload and reuse it during hydration. Give `useAsyncData` an explicit, unique key that includes its inputs; pass reactive inputs so it refetches when they change.
- **`$fetch` directly in `setup`** runs twice (server and client) and is not transferred in the payload. Use `$fetch` in event handlers and inside `useAsyncData`.
- **Server routes** in `server/api` (Nitro and h3) are public endpoints: validate bodies and queries (`readValidatedBody`, `getValidatedQuery` with a schema), check the session and the specific record on every handler.
- **`runtimeConfig`** keeps secrets server-only; only keys under `runtimeConfig.public` reach the browser. They can be overridden at runtime with `NUXT_` environment variables.
- **`useState`** creates SSR-safe shared state keyed by name; plain `ref` at module level is shared across requests on the server.
- **Route middleware** (`middleware/`) runs on server and client navigation: UX only. Server middleware (`server/middleware/`) runs on every request; keep it light.
- `<ClientOnly>` wraps components that need the browser; prefer rendering a placeholder of the same size to avoid layout shift.
- Typecheck with `nuxi typecheck` (it runs `vue-tsc`).
- Evaluate modules before adding them: maintenance, Nuxt major compatibility, and what they inject into every page.

## JavaScript-only projects with JSDoc

Teams that do not use TypeScript syntax can still get type checking:

- Add `// @ts-check` to files, or `"checkJs": true, "allowJs": true, "noEmit": true` in a `jsconfig.json` or `tsconfig.json`, and run `vue-tsc --noEmit` in CI.
- Annotate with `@typedef`, `@param`, `@returns`, `@type`, and import shared types with `import("./types.js").User`. Keep shared shapes in one `.js` (or `.d.ts`) file.
- Runtime prop declarations (`defineProps({ name: { type: String, required: true } })`) are type-checked; add `/** @type {import("vue").PropType<User>} */` for object props.
- The rules in this file apply unchanged; only the annotation syntax differs. General JavaScript practice is in `javascript-runtime.md`.

## Testing

- Vitest with `@vue/test-utils` or `@testing-library/vue`. Query by role and text, trigger events with `await`, and `await flushPromises()` after async work.
- Stub stores with `createTestingPinia()` from `@pinia/testing` (actions are stubbed unless `stubActions: false`).
- Test composables with logic as plain functions; when they use lifecycle hooks, mount a tiny host component or use `effectScope`.
- Nuxt: `@nuxt/test-utils` with the Nuxt Vitest environment and `mountSuspended` for components that use Nuxt composables; Playwright for full flows.

## Performance

- Profile with Vue Devtools (component render timeline) and the browser Performance panel before changing anything (`../../engineering-practices/references/performance.md`).
- Big lists: virtualize; `v-memo` skips re-rendering rows whose listed dependencies did not change; `v-once` for static content.
- Split heavy components with `defineAsyncComponent`; in SSR apps use lazy hydration (`hydrateOnVisible()`, `hydrateOnIdle()`) or Nuxt's lazy components for below-the-fold widgets.
- `KeepAlive` caches tab views; bound it with `max`.

## Security hooks

- `v-html` is an HTML sink: only sanitized content (`web-frontend-foundations.md`).
- Never compile templates from user input; ship the runtime-only build.
- Secrets only in server `runtimeConfig` or server-side environment variables; `VITE_` and `NUXT_PUBLIC_` values are public.

## Upgrading

- **Vue 2 to 3:** use the migration build (`@vue/compat`) to run the app with deprecation warnings, fix them module by module, replace Vuex with Pinia and filters with functions, then remove the compat build. Third-party Vue 2 component libraries are usually the blocker; check replacements first.
- **Nuxt 3 to 4:** on the latest Nuxt 3, set `future: { compatibilityVersion: 4 }` and fix what breaks before switching; then `npx nuxi upgrade`. Review data-fetching code for key collisions and `null` checks that should now test `undefined`.
- Follow `../../engineering-practices/references/large-refactors.md` for both.

## Common breakages

| Symptom | Cause | Fix |
|---|---|---|
| UI does not update after assignment | Destructured reactive object or store, or replaced `reactive` object | `toRefs`, `storeToRefs`, or a `ref` |
| "Hydration ... mismatch" warnings | Browser-only values or random ids in SSR render | `useId`, render browser values after `onMounted`, `<ClientOnly>` with a same-size placeholder |
| Data fetched twice in Nuxt | `$fetch` in `setup` | `useFetch` or `useAsyncData` with a key |
| One user's data shown to another under SSR | Module-level state on the server | Per-request state (`useState`, Pinia via Nuxt) |
| Infinite update loop warning | A watcher or computed writes the state it depends on | Separate source and derived state |
| Prop mutation warning | Child writes a prop | `defineModel` or emit an event |

## Done when

- [ ] `vue-tsc --noEmit` (or `nuxi typecheck`), lint, tests and the production build pass.
- [ ] SSR pages load with no hydration warnings in the browser console.
- [ ] New server routes validate input and authorize the specific record.
- [ ] No secret in public runtime config or `VITE_` variables (searched in the build output).
- [ ] New async UI covers loading, empty, error and success.
