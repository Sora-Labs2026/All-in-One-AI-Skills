# React performance and testing

Read this when a React screen is slow (first load, typing, scrolling, navigation), when you add or fix React component tests, or when a React build or runtime error blocks you. The basics (rendering rules, effects, when to memoize, React Compiler, the 18 to 19 upgrade) are in `react.md`; the measurement loop and Core Web Vitals in `../../engineering-practices/references/performance.md`; test layers and the MSW setup in `web-frontend-foundations.md`; browser tests in `../../builder-tools/references/playwright-web-testing.md`. This file adds the depth those leave out.

## Find the cost before changing code

1. Reproduce on a production build (`vite build && vite preview`, `next build && next start`). Development builds run extra checks and StrictMode renders twice, so their timings mislead.
2. Throttle the CPU (4x or 6x in the browser Performance panel) to approximate a mid-range phone.
3. Record with the React DevTools Profiler and turn on "Record why each component rendered". On React 19.2 and later the browser Performance panel also shows React's scheduler and component tracks next to network and long tasks.
4. Name the kind of cost, then fix that kind only:

| Symptom | Usual cost | Where to look |
|---|---|---|
| Late first paint or LCP | JavaScript bytes, request waterfalls, render-blocking scripts | Bundle analyzer, network waterfall |
| Typing or clicks lag (poor INP) | Too much re-rendering per update, long tasks | Profiler commit durations, long tasks in the Performance panel |
| Janky scrolling | Too many DOM nodes, layout work per frame | Element count, Layout and Recalculate Style entries |
| Slow navigation | Data fetched in child effects after the parent rendered | Network panel ordering |
| Slow hydration | Large HTML plus many client components hydrating at once | Performance panel during load |

5. Keep the before and after numbers in the report. `<Profiler id="list" onRender={...}>` gives commit durations you can log in a test or field monitoring.

## Re-render costs

A component re-renders when its state changes, its parent re-renders, a context it reads changes, or a store slice it subscribes to changes. Changed props alone are not the trigger; the parent's render is.

Try structural fixes before memoization; they also help when the React Compiler is on:

- **Move state down** into the component that uses it, so a keystroke does not re-render the whole page.
- **Lift expensive content up and pass it as `children`.** A wrapper that holds fast-changing state re-renders, but the `children` element it received was created by the parent and is not re-rendered.
- **Split contexts by update frequency** (theme and session in one, a live cursor position in another), and memoize the provider value object.
- **Subscribe to the narrowest store slice,** preferably a derived primitive: `useCart((s) => s.items.length > 0)` re-renders only when emptiness flips. A value that only a callback needs can be read at call time (`useCart.getState()`, a ref) instead of subscribed to.
- **Never define a component inside another component.** Each render creates a new type, so React unmounts and remounts the subtree and loses its state.
- **Keep keys stable;** a changing key remounts everything below it.

Without the compiler, memoize only what the profile shows is hot:

- `memo` on a component that re-renders often with equal props and renders measurably slowly. Its props must be stable: hoist constant defaults (`const NO_ITEMS: Item[] = []` at module level instead of `items ?? []`), memoize objects and callbacks passed to it.
- `useMemo` for an expensive calculation, or for an object whose identity feeds an effect or a memoized child.
- `useState(() => parse(raw))` (a lazy initializer) for expensive initial values.

With the compiler on, leave existing manual memoization in place unless a profile says otherwise; removing it in bulk can change when effects run.

For updates that do not need to block input, `useTransition` (or `startTransition`) marks the slow update as interruptible and `useDeferredValue` renders a lagging copy of a fast-changing value. They keep typing responsive; they do not reduce the work.

## Long lists and large DOMs

- **Virtualize** when a list renders enough rows that DOM size or render time shows in the profile; there is no universal row count. Common libraries: TanStack Virtual, react-window (version 2, 2025, changed its API), react-virtuoso.
- Virtualization has costs to handle: variable row heights need measuring; browser find-in-page cannot see rows that are not rendered; screen readers need `aria-setsize` and `aria-posinset` (or `aria-rowcount` and `aria-rowindex` on grids) so the list size is announced; scroll position must be restored on back navigation.
- **`content-visibility: auto`** with `contain-intrinsic-size` lets the browser skip rendering off-screen sections while keeping them in the DOM and searchable. It is supported in current major browsers since 2024 and is a lighter first step for long pages of medium-size sections.
- When nobody can use ten thousand rows on one screen, paginate, filter on the server or add "load more" instead of virtualizing.

## Bundle size and loading

- Route-level code splitting comes from the framework or router. Add `lazy()` with `<Suspense>` for heavy, rarely used parts: rich-text editors, charts, maps, admin panels. In Next.js use `next/dynamic`; since Next.js 15, `ssr: false` is allowed only inside client components.
- Keep dynamic import paths statically analyzable: `import("./charts/" + name)` defeats chunking and file tracing; write one `import("./charts/line")` per branch.
- Import from the module that defines the symbol, not from a barrel that re-exports a folder or a whole library. Next.js `experimental.optimizePackageImports` rewrites barrel imports for listed packages. Confirm the effect in the analyzer rather than assuming it.
- Start loading on intent: call the `import()` on hover or focus of the link or button, so the chunk is cached by the time of the click.
- Load analytics, chat and support widgets after hydration (`next/script` with `afterInteractive` or `lazyOnload`, or an idle callback).
- **Remove waterfalls on the server too.** Start independent requests together; when a later step needs only some results, start every promise first and await each where it is needed. In server components, split slow sections into sibling async components under their own `<Suspense>`; siblings render in parallel and stream separately.
- Data passed from server to client components is serialized into the page. Pass only the fields the view needs; the same large object passed to several client components is serialized for each.

## Hydration

- Hydration cost grows with the HTML size and the number of client components. Move interactivity to small leaves (`nextjs.md`), and wrap independent widgets in `<Suspense>` so React can hydrate them selectively and prioritize the one the user interacts with.
- For values the first paint needs that only the browser knows (theme, a saved preference), set them with a small inline script before React loads, rather than rendering a default and flipping after mount.
- `suppressHydrationWarning` belongs only on a leaf whose text legitimately differs, such as a formatted local time; never on a container.

## Testing: choose the layer

| What you need to prove | Layer | Tool |
|---|---|---|
| Pure logic, reducers, selectors | Unit | Vitest or Jest |
| A hook with real logic | Hook test | `renderHook` from Testing Library |
| Rendering, interaction, async states, form behavior | Component test in jsdom or happy-dom | React Testing Library with `user-event` |
| Layout, focus order, `IntersectionObserver`, clipboard, drag and drop, real CSS | Component test in a real browser | Vitest browser mode (stable since Vitest 4, October 2025) or Playwright component testing (still experimental) |
| A flow across pages with the real server | End to end | Playwright |

jsdom has no layout engine: sizes are zero, and `IntersectionObserver`, `ResizeObserver` and `matchMedia` are missing unless mocked. When a test needs more than a couple of such mocks, move it to the browser layer.

## Queries and interactions

- Query in this order: role with accessible name (`getByRole("button", { name: /save/i })`), label, visible text, alt text, and `getByTestId` only as a last resort. If an element cannot be found by role or label, the markup is usually inaccessible; fix the markup.
- `getBy*` asserts presence, `queryBy*` asserts absence (returns `null`), `findBy*` waits for async appearance. Scope with `within(region)` when the same label appears twice.
- Create `const user = userEvent.setup()` once per test and `await` every call. Use `fireEvent` only for events `user-event` does not simulate.
- **Fake timers:** pass the clock to `user-event`, `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })` (Jest: `jest.advanceTimersByTime`). Testing Library's async utilities poll on timers, so with Vitest fake timers either use `vi.useFakeTimers({ shouldAdvanceTime: true })` or advance the clock yourself; restore real timers in `afterEach`.
- An `act(...)` warning means state changed after the test stopped waiting. Await the resulting UI (`findBy*`, `waitFor`); wrapping more code in `act` hides the bug.

## Network mocking with MSW

The setup (`setupServer`, `onUnhandledRequest: "error"`, reset after each test) is in `web-frontend-foundations.md`. Patterns that keep MSW tests honest:

```ts
import { http, HttpResponse, delay } from "msw";

test("sends the edited name and shows the saved state", async () => {
  let sent: unknown;
  server.use(
    http.patch("/api/projects/:id", async ({ request, params }) => {
      sent = await request.json();                      // capture, assert after the UI settles
      await delay(50);                                  // exercise the pending state
      return HttpResponse.json({ id: params.id, name: "Atlas" });
    }),
  );
  const user = userEvent.setup();
  render(<ProjectSettings id="p1" />, { wrapper: TestProviders });

  await user.clear(screen.getByLabelText(/project name/i));
  await user.type(screen.getByLabelText(/project name/i), "Atlas");
  await user.click(screen.getByRole("button", { name: /save/i }));

  expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled();
  expect(await screen.findByRole("status")).toHaveTextContent(/saved/i);
  expect(sent).toEqual({ name: "Atlas" });
});
```

- Simulate a dropped connection with `HttpResponse.error()` and slow responses with `delay()`; test both the error state and the retry control.
- Type handler responses with types generated from the API contract so mocks cannot drift from the real shape (`../../engineering-practices/references/api-contracts.md`).
- Keep shared handlers in one module that tests, Storybook and local development can all use.
- Do not mock your own API client module; that skips URL building, headers, parsing and error mapping, which is where bugs live.

## Providers and isolation

- Render through one wrapper with the providers production uses: a fresh `QueryClient` per test with `retry: false`, a memory router with `initialEntries`, theme, translations. Create the client inside the test (or the wrapper factory), never at module level, or cached data leaks between tests.
- Reset external stores between tests; module-level stores (Zustand and similar) keep state across tests in the same file.
- Testing Library cleans up automatically only when the runner exposes `afterEach` globally. With Vitest and `globals: false`, call `cleanup()` in a setup file's `afterEach`.
- In Next.js component tests, mock `next/navigation` or wrap with a test router (`nextjs.md`).

## Hooks, error boundaries and Suspense

- Test hooks with logic through `renderHook`; when a hook needs providers, pass a `wrapper` that closes over a client created once per test.
- Error boundary: render a child that throws, assert the fallback, and silence the expected `console.error` with a spy that you restore in `finally` or `afterEach`, so real errors in other tests stay visible.
- Suspense: assert the fallback first, then `await screen.findBy...` for the content.

## Accessibility checks in tests

`jest-axe` or `vitest-axe` in component tests catches missing names, invalid ARIA and some structure problems. jsdom cannot compute layout or most colors, so contrast, focus visibility and reflow need browser tests and manual keyboard and screen-reader checks (`../../responsive-accessibility.md`).

## Snapshots

Avoid snapshots of whole component trees: they break on any markup change and get approved without reading. Small inline snapshots of serialized output (a formatter, a generated config) are fine. For visual regressions, use screenshot comparison in a real browser.

## Build and runtime failures specific to React

Fix one error at a time, rebuild after each change, and stop and report when the same error survives a few attempts or the fix needs a design change (for example a database client imported into a client component). Never disable type checking or lint rules to get a green build. Common causes not covered in `react.md`:

| Message | Cause | Fix |
|---|---|---|
| "Invalid hook call" | Two copies of React in the bundle, often from a linked or monorepo package | `npm ls react` (or the pnpm and Yarn equivalents) must show one version; dedupe, align peer ranges, or set `resolve.dedupe: ["react", "react-dom"]` in Vite |
| "Element type is invalid: expected a string ... but got: undefined" | Default versus named import mismatch, or a circular import returning `undefined` at load time | Match the export style; break the cycle |
| "'React' is not defined" or "React must be in scope" | Classic JSX transform configured | `"jsx": "react-jsx"` in `tsconfig.json` and the matching bundler setting |
| Type errors after an upgrade (`JSX` namespace, `ref` types) | `@types/react` major differs from `react` | Upgrade the types with React; run the types codemod (`react.md`) |
| "Unexpected token '<'" or "Failed to parse source" | JSX in a file the bundler does not transform (for example `.js` in Vite) | Rename to `.jsx` or `.tsx`, or configure the framework plugin to include it |
| "Objects are not valid as a React child" | Rendering an object, a `Date` or a promise | Render a field or a formatted string |
| A CommonJS package fails only in development | Dependency pre-bundling or interop | See the Vite section in `vite-and-bun.md` |

## Done when

- [ ] Each performance change names the measured cost, with before and after numbers from a production build.
- [ ] Structural fixes were tried before memoization; no memoization was added without profiler evidence.
- [ ] Long lists are virtualized or paginated, with announced list size and keyboard access checked.
- [ ] Bundle changes were confirmed in the analyzer, not assumed.
- [ ] Component tests query by role or label, await every interaction, mock the network at the HTTP layer and fail on unhandled requests.
- [ ] Tests cover loading, empty, error and success states; no new whole-tree snapshots.
- [ ] Build fixes changed only what the error required, and the build, type check and tests pass.
