# Next.js

Read this when you work in a Next.js app: routing, server and client components, data fetching and caching, server actions, route handlers, middleware or proxy, images and fonts, builds, deployment or upgrades. React itself is in `react.md`; cross-framework practice is in `web-frontend-foundations.md`; Next.js security controls in `../../launchguard/references/stack-playbooks.md` apply on top.

## Check the major version first

The caching model changed in every recent major; advice written for one is wrong for the next. Read `next` and `react` in the lockfile.

| Version | What changed |
|---|---|
| 13.4 to 14 (2023) | App Router stable. `fetch` in server components cached by default; GET route handlers static by default |
| 15 (Oct 2024) | `params`, `searchParams`, `cookies()`, `headers()` and `draftMode()` became async (Promises); `fetch` and GET route handlers no longer cached by default; the client router cache no longer reuses page data by default; React 19 |
| 16 (Oct 2025) | Turbopack is the default bundler for dev and build (`--webpack` opts out); `middleware.ts` renamed `proxy.ts` and runs on Node.js; Cache Components (`cacheComponents: true`) with the `"use cache"` directive, `cacheLife` and `cacheTag`; `revalidateTag(tag, profile)` takes a cache profile; `updateTag()` and `refresh()` for server actions; synchronous access to request APIs removed; `next lint` removed; Node.js 20.9 or later |

The Pages Router (`pages/`) is still supported. Do not migrate a Pages Router app unasked; both routers can coexist during an incremental move.

## App Router file conventions

| File | Role |
|---|---|
| `layout.tsx` | Shared shell; persists across navigations between its children |
| `page.tsx` | The route's UI; only routes with a page are reachable |
| `loading.tsx` | Suspense fallback for the segment, shown while it streams |
| `error.tsx` | Error boundary for the segment; must be a client component; offers `reset` |
| `not-found.tsx`, `global-error.tsx` | 404 UI after `notFound()`; root-level error UI including the root layout |
| `route.ts` | HTTP handler (GET, POST, ...) instead of a page |
| `template.tsx` | Like a layout but remounts on navigation |
| `default.tsx` | Fallback for a parallel route slot; required for each slot in 16 |
| `(group)`, `[id]`, `[...slug]`, `@slot`, `(.)segment` | Route groups, dynamic and catch-all segments, parallel routes, intercepting routes |

## Server and client components

- Components are server components by default. They can be `async`, read databases and secrets, and ship no JavaScript.
- `"use client"` marks a boundary: that module and everything it imports become client code. Put it on the smallest interactive leaf, not on a page or layout.
- A client component cannot import a server component, but it can render one passed as `children` or another prop. Use that to keep providers and interactive shells from turning whole subtrees into client code.
- Props crossing the boundary must be serializable: plain data, Dates, Promises (consumed with `use()`), and server actions. Not class instances or ordinary functions.
- Mark modules holding secrets or database access with `import "server-only"` so an accidental client import fails the build.
- Everything passed to a client component is sent to the browser. Map database rows to the fields the UI needs first.

## Fetching data

- Fetch in server components, close to where the data is used, directly from the database or a service; do not call your own route handlers from server components.
- Start independent requests together with `Promise.all`, or let separate `<Suspense>` boundaries stream them in parallel. Sequential awaits in a page add up.
- Deduplicate per request with React `cache()` around data-access functions that several components call.
- Put authorization in a data access layer: each function verifies the session and the caller's right to the specific record before returning it. Pages, layouts, actions and route handlers call that layer.

```ts
// lib/data/invoices.ts
import "server-only";
import { cache } from "react";
import { getSession } from "@/lib/auth";

export const getInvoice = cache(async (id: string) => {
  const session = await getSession();
  if (!session) return null;
  const invoice = await db.invoice.findFirst({
    where: { id, orgId: session.orgId },          // object-level authorization
    select: { id: true, number: true, totalMinor: true, currency: true, status: true },
  });
  return invoice;                                  // only fields the UI shows
});
```

## Caching and revalidation by version

- **15, or 16 without Cache Components:** data is fetched per request unless you opt in. Opt in per call (`fetch(url, { cache: "force-cache" })` or `{ next: { revalidate: 300, tags: ["products"] } }`) or per segment (`export const revalidate = 300`). Non-fetch data (ORM calls) is cached with `unstable_cache` or, where enabled, `"use cache"`.
- **16 with `cacheComponents: true`:** mark cacheable functions or components with `"use cache"`, set lifetime with `cacheLife("hours")` and tags with `cacheTag("product-42")`. Uncached dynamic work must sit inside `<Suspense>`; the build reports what blocks prerendering.
- **14:** `fetch` is cached by default; opt out with `cache: "no-store"` or `export const dynamic = "force-dynamic"`.
- **Invalidate after writes:** `revalidatePath("/products")` or `revalidateTag("products")` (16 expects a profile argument, for example `revalidateTag("products", "max")`). In 16, `updateTag()` inside a server action makes the next read see the write immediately.
- Anything that reads `cookies()`, `headers()` or the session is per user. Never place it in a cached scope; Next.js throws for `cookies()` inside `"use cache"`.
- Read the build output: each route is marked static or dynamic. A route you expected to be static that shows as dynamic usually reads a request API somewhere in its tree.
- Self-hosting several instances: the default cache is per instance on local disk, so revalidation reaches one instance only. Configure a shared `cacheHandler` or route all traffic through a CDN that honors the revalidation.

## Server actions

A server action is a public HTTP endpoint that anyone can call with any arguments, whatever the UI shows.

- Authenticate and authorize inside every action, through the data access layer.
- Parse arguments and `FormData` with a schema; return field errors as data for `useActionState`.
- Revalidate or update tags after the write; `redirect()` throws, so call it after the work, outside `try`.
- Use actions for mutations. Reads from client components go through server components, route handlers or a query library; actions run sequentially and use POST.
- Uploads over 1 MB need `serverActions.bodySizeLimit`; prefer direct-to-storage uploads with signed URLs for large files.

```ts
"use server";
import { z } from "zod";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";

const Rename = z.object({ id: z.string().uuid(), name: z.string().trim().min(1).max(80) });

export async function renameProject(_prev: unknown, formData: FormData) {
  const user = await requireUser();                     // throws or redirects when signed out
  const parsed = Rename.safeParse(Object.fromEntries(formData));
  if (!parsed.success) return { ok: false, errors: parsed.error.flatten().fieldErrors };

  const updated = await db.project.updateMany({
    where: { id: parsed.data.id, ownerId: user.id },    // scoped to the caller
    data: { name: parsed.data.name },
  });
  if (updated.count === 0) return { ok: false, errors: { id: ["Project not found"] } };

  revalidatePath("/projects");
  return { ok: true, errors: {} };
}
```

## Route handlers, middleware and proxy

- Route handlers serve webhooks, public APIs, files and non-React clients. For signed webhooks read the raw body (`await request.text()`) and verify the signature before parsing.
- Middleware (`proxy.ts` in 16) runs before matched requests. Keep it to cheap work: redirects, rewrites, locale, headers, a coarse "has a session cookie" check. Limit it with `config.matcher`.
- **Middleware is not the authorization boundary.** In March 2025, CVE-2025-29927 let a crafted `x-middleware-subrequest` header skip middleware entirely on self-hosted apps (fixed in 15.2.3, 14.2.25, 13.5.9 and 12.3.5). Check authorization again in the data access layer.

## Metadata, images, fonts and scripts

- Use the `metadata` export or `generateMetadata` for titles, descriptions, canonical URLs and Open Graph; `sitemap.ts` and `robots.ts` generate those files.
- `next/image` needs `width` and `height` (or `fill` with a sized parent) and a correct `sizes` for responsive images. Mark the LCP image for preloading (`priority`; check the prop name in the image docs for your major) and never lazy-load it. Restrict remote images with `images.remotePatterns`; an open optimizer can be abused to fetch anything.
- `next/font` self-hosts fonts and removes layout shift from font swaps.
- `next/script` with `strategy="afterInteractive"` or `"lazyOnload"` for third-party scripts.

## Environment and configuration

- `NEXT_PUBLIC_` variables are inlined at build time and visible to everyone. Server variables are read at runtime only in dynamically rendered code; in statically rendered code they are fixed at build.
- Validate environment variables at startup in one module (`../../engineering-practices/references/typescript.md`).
- `next.config.ts` is supported since 15. The `env` key in the config embeds values into the client bundle even without the public prefix; avoid it for secrets.

## Builds and deployment

- `next build` type-checks and fails on type errors unless `typescript.ignoreBuildErrors` is set; do not set it to get green. In 16 run ESLint through its own CLI, since `next lint` is gone.
- Self-hosting: `output: "standalone"` produces a minimal Node.js server; copy `.next/static` and `public` next to it. Run behind a reverse proxy, handle SIGTERM, and set `HOSTNAME=0.0.0.0` in containers.
- `output: "export"` produces static files and drops server features (server actions, ISR, request-time rendering, image optimization by default).
- Deploying a new build invalidates client bundles that open tabs still reference; Next.js hard-navigates on a missing chunk. Keep previous static assets available during rollout when using several instances.

## Testing

- Client components: Vitest or Jest with React Testing Library.
- Async server components are not well supported by unit renderers. Test the data access layer and server actions as plain functions (with a test database or mocked session), and cover pages with Playwright against `next build && next start`.
- Mock `next/navigation` (`useRouter`, `usePathname`) in component tests, or wrap with a test router.

## Upgrading

1. Run `npx @next/codemod@canary upgrade latest`, or the specific codemods (for example `next-async-request-api` for 15).
2. Upgrade React and `@types/react` in the same change, and libraries with Next.js or React peer ranges.
3. Rebuild and compare the route table (static versus dynamic) with the previous build; caching defaults changed in 15 and 16.
4. For 16: rename `middleware.ts` to `proxy.ts` (and its exported function), add `default.tsx` to parallel route slots, replace `images.domains` with `remotePatterns`, and move off `serverRuntimeConfig` and `publicRuntimeConfig`.

## Security hooks

Review-level traps (caching per-user data, CSRF on route handlers, image and redirect options) are in the Next.js section of `../../code-security-review/references/language-pitfalls.md`. While writing:

- Patch promptly. The December 2025 React Server Components remote-code-execution advisory (CVE-2025-55182, with follow-up fixes the same month) affected App Router apps on 15 and 16; compare your `next` and `react-server-dom-*` versions with the current advisories.
- Every server action and route handler authorizes on its own; layouts do not protect the pages below them on every request path.
- Never pass secrets or whole records into client components; return only displayable fields.
- Allowlist redirect targets in auth callbacks; set a nonce-based CSP in middleware or proxy if the app needs one (`web-frontend-foundations.md`).

## Common breakages

| Message or symptom | Cause | Fix |
|---|---|---|
| "You're importing a component that needs useState" | Hook used in a server component | Move the interactive part into a `"use client"` leaf |
| "Functions cannot be passed directly to Client Components" | A plain function prop across the boundary | Pass a server action or move the logic to the client |
| "Dynamic server usage" or a static route turned dynamic | A request API (`cookies`, `headers`, `searchParams`) read in the tree | Read it lower, inside `<Suspense>`, or accept dynamic rendering |
| Type errors on `params` after upgrading to 15 | `params` is a Promise | `const { id } = await params` (or `use(params)` in client components); run the codemod |
| Stale page after a mutation | No revalidation, or the client router cache | `revalidatePath`, `revalidateTag` or `updateTag`; `router.refresh()` for client-side refresh |
| `window is not defined` | Browser API used during server render | Use it in an effect or a client-only dynamic import |
| Works on Vercel, stale data when self-hosted on several instances | Per-instance cache | Shared `cacheHandler` |

## Done when

- [ ] `next build` passes without ignored type errors, and the route table shows the intended static and dynamic routes.
- [ ] Every new server action and route handler authenticates, authorizes the specific record and validates input with a schema.
- [ ] No secret or unneeded field reaches a client component or the client bundle (searched).
- [ ] Mutations revalidate the right paths or tags, checked by reloading after the change.
- [ ] Changed flows pass Playwright against a production build, or the report marks it `NOT VERIFIED`.
