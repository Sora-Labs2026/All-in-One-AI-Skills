# Web front-end foundations

Read this first for any browser front-end work in a component framework (React, Next.js, Vue, Nuxt, Angular, Svelte, Solid) or in plain TypeScript. It covers what holds across frameworks: rendering modes, kinds of state, fetching and caching server data, wiring forms, routing, testing, builds, service workers, upgrades and the security hooks specific to front ends. Each framework reference adds only what differs.

Design and UX rules live in other modules. Link to them; do not restate them here:

- Visual direction, layout and priorities: `../../ui-distiller/GUIDE.md` and `../../ui-rules.md`
- Pending, success and error states, toasts, modals, motion: `../../interaction-feedback.md`
- Form UX, validation timing, checkout, OTP: `../../forms-conversion.md`
- Responsive layout, accessibility, translation and RTL: `../../responsive-accessibility.md`
- Types, `tsconfig`, parsing untrusted data: `../../engineering-practices/references/typescript.md`
- Core Web Vitals, re-render profiling, budgets: `../../engineering-practices/references/performance.md`
- Browser tests with Playwright: `../../builder-tools/references/playwright-web-testing.md`

## Start from the project

- Read `package.json` and the lockfile: framework and its major version, meta-framework, router, data library, form library, styling system, test runner. The lockfile names the package manager (`package-lock.json` npm, `pnpm-lock.yaml` pnpm, `yarn.lock` Yarn, `bun.lock` or `bun.lockb` Bun). Use that one; never create a second lockfile.
- Read the Node version the project expects (`.nvmrc`, `.node-version`, `engines`, `.tool-versions`, `volta` in `package.json`, the CI matrix) before installing anything.
- Use the scripts CI runs (`lint`, `typecheck`, `test`, `build`, `e2e`) as the done-when checks. In a monorepo (pnpm workspaces, Turborepo, Nx), run them for the affected package, the way CI does (`pnpm --filter <pkg> test`, `nx affected -t test`).
- Match the existing layout (feature folders or type folders), component library and state and data libraries. Do not add a second library for a job one already does.

## Choose the rendering mode per route

| Mode | Fits | Watch for |
|---|---|---|
| Static at build time | Marketing pages, docs, content that changes with deploys | A rebuild or revalidation is needed to change anything |
| Static with revalidation (ISR, stale-while-revalidate) | Catalogs, blogs, listings edited often | A staleness window; invalidate on write |
| Server-rendered per request, streamed | Personalized or fresh pages that need fast first paint or SEO | Server cost; each un-streamed slow query delays the page |
| Client-rendered single-page app | Tools behind a login where SEO does not matter | Large JavaScript; blank screen until it loads unless the shell is server-rendered |
| Islands or server components with small client parts | Mostly static pages with a few interactive widgets | Discipline at every server/client boundary |

- Decide per route, not once for the whole app.
- A personalized response must never land in a shared cache (CDN, ISR, full-route cache) unless the cache key includes the viewer.
- Everything serialized to the browser is readable by that user: props passed to client components, hydration payloads, `__NEXT_DATA__`, the Nuxt payload, Angular transfer state. Send only the fields the view needs.

## Keep each kind of state in its place

| State | Where it lives |
|---|---|
| Server data (owned by the backend) | A query cache: TanStack Query, SWR, RTK Query, Apollo or urql for GraphQL, Nuxt `useFetch`, Angular `resource`/`httpResource` or a service |
| Shareable view state (filters, sort, tab, page, selected id) | The URL, so reload, back and share work |
| Form input | The form library or the native form and `FormData` |
| Purely local UI state (open, hovered, draft text) | The component |
| Client state shared across distant parts of the app (theme, wizard spanning routes, offline queue) | A small store (Zustand, Pinia, NgRx SignalStore, Redux Toolkit), only when it is really shared |
| Values computed from other state | Computed at render (`useMemo`, `computed`), never stored as a second copy |

The most common breakage is copying server data into a global store and then hand-syncing it after every mutation. Keep server data in the query cache and invalidate it.

## Fetch and cache server data

These hold in every query library:

- **The key contains every input that changes the result:** ids, filters, page or cursor, locale, and the user or tenant when responses differ per viewer. A missing input serves stale or another user's data.
- **Choose staleness on purpose.** A stale time of zero everywhere causes refetch storms on focus and remount; infinity everywhere shows stale data.
- **After a mutation**, update the cache from the response or invalidate the affected keys. Use optimistic updates only for low-impact, reversible actions, with rollback on failure (`../../interaction-feedback.md`).
- **Cancel or ignore stale responses.** Pass the library's `AbortSignal` to `fetch`; out-of-order responses in search-as-you-type are a classic bug.
- **Avoid waterfalls.** Start independent requests together, and load in the route loader or server component rather than in a child's effect after the parent rendered.
- **Retry only idempotent reads,** never on 4xx.
- **Render four states:** no data yet, empty, error, and data that is stale while a refresh failed.

```ts
// TanStack Query v5 (2023+): key factory, cancellation, cache update after a mutation
export const invoiceKeys = {
  all: ["invoices"] as const,
  list: (f: InvoiceFilters) => [...invoiceKeys.all, "list", f] as const,
  detail: (id: string) => [...invoiceKeys.all, "detail", id] as const,
};

export function useInvoices(filters: InvoiceFilters) {
  return useQuery({
    queryKey: invoiceKeys.list(filters),
    queryFn: ({ signal }) => api.listInvoices(filters, { signal }),
    staleTime: 30_000,
    placeholderData: keepPreviousData, // keep the previous page on screen while the next loads
  });
}

export function useMarkPaid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.markPaid(id),
    onSuccess: (invoice) => {
      qc.setQueryData(invoiceKeys.detail(invoice.id), invoice);
      return qc.invalidateQueries({ queryKey: invoiceKeys.all });
    },
  });
}
```

Version notes for TanStack Query v5: object syntax only; `status: "pending"` and `isPending` mean "no data yet" (v4 called it loading); `gcTime` replaced `cacheTime`; `keepPreviousData` became the `placeholderData` helper shown above.

## Wire forms

- One schema (Zod, Valibot or the project's choice) validates on the client for convenience and on the server for real. The server re-validates every submission.
- A native `<form>` with `FormData` and server-side validation covers many forms. Reach for a form library (React Hook Form, TanStack Form, VeeValidate, Angular reactive or signal forms) for large, dynamic or heavily validated forms.
- Map server field errors back onto fields. With Problem Details errors (`../../engineering-practices/references/api-contracts.md`), each `errors[].pointer` names the field.
- Prevent double submission while pending, and send an idempotency key with creates and payments.
- Where the framework supports it, let the form work before JavaScript loads (server actions, React Router actions, SvelteKit form actions, Nuxt server routes).

## Share types with the server

- Generate client types from the contract instead of copying them by hand: OpenAPI generators (for example `openapi-typescript` with a typed fetch client), GraphQL Code Generator (`graphql.md`), or protobuf generators. Regenerate in CI and fail on a diff.
- In a TypeScript monorepo where client and server always deploy together, an RPC layer that infers types end to end (tRPC, server functions in the meta-framework) removes the contract file. It also couples deploys; public or mobile clients that update slowly still need a versioned contract (`../../engineering-practices/references/api-contracts.md`).
- Shared validation schemas live in a package both sides import. Generated or inferred types do not replace runtime validation of responses from services you do not control.

## Routing and URLs

- Parse and validate route and query parameters in one place; they are untrusted input.
- Lazy-load route code and prefetch on intent (hover, viewport) where the router supports it.
- Give every route a loading state, an error state and a not-found state.
- Router guards are UX. The server authorizes every request for data or actions (`../../launchguard/references/security-baseline.md`, controls 6 and 7).
- After client-side navigation, move focus to the new page heading or announce the change, and restore scroll on back (`../../responsive-accessibility.md`).
- Allow redirect targets from query strings (`?next=`, `?returnTo=`) only as relative paths on an allowlist; anything else is an open redirect.

## Test in layers

- **Unit:** pure functions, reducers, stores, hooks and composables with real logic. Use the runner the project has (Vitest or Jest).
- **Component:** render with the Testing Library variant for the framework, query by role and accessible name, drive input with `user-event`, assert what a user would see. Mock the network at the HTTP layer with MSW instead of mocking your own API module.
- **End to end:** Playwright against a production build for the flows that matter (`../../builder-tools/references/playwright-web-testing.md`).
- **Accessibility:** run axe in component or end-to-end tests (`vitest-axe`, `jest-axe`, `@axe-core/playwright`). It finds only part of the problems; keyboard and screen-reader checks remain manual.
- Test loading, empty, error and success states. Do not snapshot whole component trees, and do not assert on internal state or private methods.

```ts
// MSW v2 (2023+) with Vitest and Testing Library
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const server = setupServer(
  http.get("/api/invoices", () => HttpResponse.json({ data: [], nextCursor: null })),
);
// setup file: beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
//             afterEach(() => server.resetHandlers()); afterAll(() => server.close());

test("shows an error with a retry when loading fails", async () => {
  server.use(http.get("/api/invoices", () => new HttpResponse(null, { status: 500 })));
  render(<InvoicesPage />, { wrapper: TestProviders }); // fresh QueryClient per test, retries off
  expect(await screen.findByRole("alert")).toHaveTextContent(/could not load invoices/i);
  expect(screen.getByRole("button", { name: /retry/i })).toBeEnabled();
});
```

## Builds and environment variables

- Bundlers strip types without checking them. Run the type checker separately (`tsc --noEmit`, `vue-tsc --noEmit`, `svelte-check`); `ng build` and `next build` type-check as part of the build.
- **Variables with a public prefix are compiled into the bundle and readable by anyone:** `VITE_`, `NEXT_PUBLIC_`, `NUXT_PUBLIC_`, `PUBLIC_`, `EXPO_PUBLIC_`, `REACT_APP_`. Never put a secret behind one. After a production build, search the output for the names and known prefixes of server-side secrets (`grep -rE "sk_live|SERVICE_ROLE|PRIVATE_KEY" dist/ .next/static/`). See LaunchGuard control 1.
- Public variables are fixed at build time. A prebuilt image cannot change them per environment unless the app reads runtime config from the server.
- Produce source maps for error tracking and upload them to the tracker; do not serve them publicly unless the project intends to (Vite `build.sourcemap: "hidden"`).
- Inspect the bundle when size grows: `rollup-plugin-visualizer` or `vite-bundle-visualizer`, `@next/bundle-analyzer`, `ng build --stats-json` with an esbuild analyzer. Usual finds: duplicate copies of a package, whole-library imports (date, utility and icon libraries), polyfills the browser targets do not need.
- Treat production-only failures as configuration first: a variable missing at build time, a side-effect import removed by tree shaking (`sideEffects` in `package.json`), file-name case that works on macOS and fails on Linux CI.

## Service workers and progressive web apps

- Use a maintained tool (Workbox, `vite-plugin-pwa`, `@angular/service-worker`) rather than hand-written caching.
- Cache-first suits content-hashed static assets. API data that tolerates staleness can use stale-while-revalidate; everything else goes network-first or is not cached. Never cache authenticated responses where another account on the device can read them, and clear caches on sign-out.
- The classic breakage is users stuck on an old version. Version the caches, detect a waiting worker, and ask the user to reload instead of swapping assets under a running page.
- Service workers are usually off in development. Test install, offline and update in a production build.
- Keep a kill switch: a no-op worker that unregisters itself and deletes caches, ready to deploy at the same URL.

## Upgrades

- One major version at a time. Read the migration guide, run the official codemods (`npx @next/codemod`, `ng update`, `npx nuxi upgrade`, `npx types-react-codemod`), and upgrade tightly coupled packages together (router, data library, test utilities, type packages).
- After each step: type check, unit and component tests, build, end-to-end smoke. Commit each green step on its own (`../../engineering-practices/references/large-refactors.md`, `../../engineering-practices/references/dependencies.md`).
- Deprecation warnings in the console and test output are the work list for the next upgrade. Fix them before they become removals.

## Front-end security hooks

The general controls are in `../../launchguard/references/security-baseline.md` and `../../launchguard/references/stack-playbooks.md`; review-level traps per language and framework are in `../../code-security-review/references/language-pitfalls.md`. These are the places front ends get them wrong while code is being written:

- **HTML sinks:** React `dangerouslySetInnerHTML`, Vue `v-html`, Angular `[innerHTML]` combined with `DomSanitizer.bypassSecurityTrust*`, Svelte `{@html}`, and `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`. Sanitize user or AI-generated content with a maintained sanitizer (DOMPurify) or render Markdown with raw HTML disabled.
- **URL sinks:** user-supplied `href` or `src` can carry `javascript:` or `data:` URLs. Allow only `http:`, `https:` and `mailto:` before binding; frameworks differ in what they block.
- **Never compile templates from user input** (Vue runtime template compilation, Angular JIT, `new Function`, `eval`).
- **Session tokens:** prefer `HttpOnly`, `Secure`, `SameSite` cookies over `localStorage`, which any injected script can read. With cookie sessions, protect state-changing requests against CSRF (SameSite plus a token or an `Origin` check).
- **Content Security Policy:** server-rendered frameworks need per-request nonces for their inline bootstrap scripts; avoid `'unsafe-inline'` for scripts.
- **Third-party scripts** run with full access to the page. Load only reviewed ones; pin static files with Subresource Integrity.
- **`postMessage`:** send with an explicit target origin and check `event.origin` on receipt.
- Hiding a button is UX. The server enforces every permission.

## Common breakages

| Symptom | Usual cause | Fix |
|---|---|---|
| Hydration mismatch warning, flicker on load | Server and client render differ: time, random values, locale formatting, `window` checks in render, invalid nesting (`<div>` inside `<p>`), browser extensions | Render deterministic markup on the server; read browser-only values after mount; fix the nesting; use the framework's id helper (`useId`) |
| Another user's data visible after switching accounts | Query cache or store not cleared; shared cache stored a personalized response | Clear client caches on sign-in and sign-out; send `Cache-Control: private` or `no-store` |
| Data stale after a save | No invalidation; query key misses an input | Invalidate by key prefix; fix the key |
| Fine in development, broken in production | Build-time variable missing; tree-shaken side effect; case-sensitive path | Check the build environment; declare side effects; fix the import casing |
| CORS error in the console | The server did not allow the origin | Fix the server's allowlist or proxy same-origin; never `*` with credentials |
| Memory grows during long sessions | Listeners, intervals, observers or subscriptions not cleaned up | Clean up in the effect return, `onUnmounted`, or `DestroyRef` |

## Done when

- [ ] Type check, lint, unit and component tests and the production build pass with the project's own commands.
- [ ] Every new data view handles no-data-yet, empty, error and success, and tests cover at least error and success.
- [ ] No secret sits behind a public variable prefix or in the built output (searched).
- [ ] New routes have error and not-found handling, and the server authorizes their data and actions.
- [ ] Performance claims follow `../../engineering-practices/references/performance.md` with before and after numbers.
- [ ] The touched flow passes the project's end-to-end suite, or the report marks it `NOT VERIFIED` with the reason.
