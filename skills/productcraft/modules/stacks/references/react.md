# React

Read this when you write or change React components, hooks, state or tests, upgrade React, or migrate class components. Next.js specifics are in `nextjs.md`, React Native in `react-native-expo.md`. Cross-framework practice (state kinds, data caching, forms, testing layers, builds, security sinks) is in `web-frontend-foundations.md`.

## Versions that change the advice (check `react` in the lockfile)

| Version | What matters |
|---|---|
| 18 (2022) | Concurrent rendering, automatic batching, `createRoot`, transitions, `useId`, `useSyncExternalStore`; StrictMode runs effects twice in development |
| 19 (Dec 2024) | Actions (`useActionState`, `useFormStatus`, `useOptimistic`, `<form action>`), `use()`, `ref` as a normal prop, `<Context>` as its own provider, ref cleanup functions, `<title>` and `<meta>` hoisting; removed legacy APIs (see Upgrading) |
| 19.2 (Oct 2025) | `<Activity>` to hide UI while keeping its state, `useEffectEvent`, new DevTools performance tracks |
| React Compiler 1.0 (Oct 2025) | Build-time automatic memoization; works with 17 and 18 through a runtime package |

Create React App is deprecated (2025). New apps start from a framework (Next.js, React Router in framework mode, Expo for native) or from Vite for a client-only app.

## Rendering rules that prevent most bugs

- **Render is a pure function of props and state.** No fetches, subscriptions, timers, random ids or writes to outside variables during render. StrictMode double-renders in development to expose violations; never remove StrictMode to silence them.
- **Never mutate state.** Replace objects and arrays (`[...items, next]`, `items.map(...)`, `structuredClone` for deep copies, or Immer). Mutation skips re-renders and breaks memoization.
- **Derive, do not sync.** If a value can be computed from props or state, compute it during render. `useEffect(() => setFullName(first + " " + last), [first, last])` is a bug factory.
- **Keys are stable ids from the data.** Index keys mix up row state (inputs, expanded rows, focus) when items are inserted, removed or reordered. To reset a component's state on purpose, change its `key`.
- **State lives in the lowest common owner** of the components that use it. Lift it only as far as needed.
- **Controlled inputs stay controlled:** `value` must never switch between `undefined` and a string. Initialize with `""`.

## Effects: only for synchronizing with something outside React

Before writing `useEffect`, check the alternatives:

| You want to | Do this instead |
|---|---|
| Compute a value from props or state | Compute it during render; `useMemo` only if a profile shows it is slow |
| Respond to a click, submit or keypress | Put the logic in the event handler |
| Fetch data | A data library or the framework's loader or server component |
| Reset state when a prop changes | Change the component's `key`, or store the previous prop and adjust during render |
| Notify a parent about a change | Call the parent's callback in the same event handler |

When an effect is right (subscriptions, timers, DOM integration, a non-React widget, a socket):

- List every reactive value it reads in the dependency array. Keep `eslint-plugin-react-hooks` on and do not silence `exhaustive-deps`; restructure instead.
- Return a cleanup that undoes what the effect did. In development StrictMode runs mount, cleanup, mount; an effect that breaks under that is broken in production too, just less often.
- Guard async work against races and unmounts:

```tsx
useEffect(() => {
  const controller = new AbortController();
  setStatus("loading");
  fetch(`/api/search?q=${encodeURIComponent(query)}`, { signal: controller.signal })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .then((data) => { setResults(data); setStatus("done"); })
    .catch((e) => { if (e.name !== "AbortError") setStatus("error"); });
  return () => controller.abort(); // the previous query's response can no longer land
}, [query]);
```

- To read the latest props inside an effect without re-running it, use `useEffectEvent` (19.2+) for the non-reactive part rather than leaving a dependency out.
- Stale closures: a callback created in an earlier render sees that render's values. Fix with functional updates (`setCount((c) => c + 1)`), correct dependencies, `useEffectEvent`, or a ref for values that must not trigger renders.

## State and data

- `useState` for independent values; `useReducer` when several values change together or transitions have rules (it also makes the logic testable without rendering).
- Context suits low-frequency values (theme, locale, the current user). Every consumer re-renders when the value changes: split contexts by update frequency, memoize the value object, or use a store with selectors.
- External stores (Zustand, Redux Toolkit, Jotai): subscribe to the narrowest slice (`useStore((s) => s.cart.count)`), never the whole store. With Redux Toolkit, use RTK Query or TanStack Query for server data instead of hand-written thunks.
- Server data belongs in a query cache, not in context or a global store (`web-frontend-foundations.md`).

## React 19 actions and forms

- `useActionState(action, initialState)` returns `[state, formAction, isPending]`. The action receives the previous state and the `FormData`; return field errors as data rather than throwing.
- `useFormStatus()` (from `react-dom`) reads the pending state of the enclosing form; it works only in a component rendered inside that `<form>`.
- `useOptimistic` shows an expected result while an action runs and reverts when the action settles. Use it only for low-impact, reversible actions (`../../interaction-feedback.md`).
- `use(promise)` suspends until a promise resolves. The promise must come from outside render (a server component, a loader, a cache); a promise created during render is recreated on every render.

```tsx
"use client";
import { useActionState } from "react";
import { saveProfile, type SaveResult } from "./actions"; // validates on the server, returns field errors

const initial: SaveResult = { ok: false, errors: {} };

export function ProfileForm({ name }: { name: string }) {
  const [state, formAction, isPending] = useActionState(saveProfile, initial);
  return (
    <form action={formAction} noValidate>
      <label htmlFor="name">Display name</label>
      <input id="name" name="name" defaultValue={name} aria-invalid={!!state.errors.name}
             aria-describedby={state.errors.name ? "name-error" : undefined} />
      {state.errors.name && <p id="name-error">{state.errors.name}</p>}
      <button type="submit" disabled={isPending}>{isPending ? "Saving" : "Save"}</button>
      {state.ok && <p role="status">Saved</p>}
    </form>
  );
}
```

## Suspense and error boundaries

- Place `<Suspense>` where a loading state makes sense to the user (a panel, a list), not around the whole app and not around every component. Suspense only works with a source that suspends: a framework loader, a server component, `use()`, or a suspense-mode query hook.
- Error boundaries catch render errors below them, not errors in event handlers or async callbacks; catch those yourself and set error state. Boundaries are still class components; the `react-error-boundary` package wraps them.
- Put a boundary at each route and around independent widgets so one failure does not blank the page. Log caught errors to the error tracker (React 19's `onCaughtError` and `onUncaughtError` root options help).

## Performance

- Profile first with React DevTools Profiler ("highlight updates") and the browser Performance panel; React 19.2 adds React tracks there. Follow `../../engineering-practices/references/performance.md`.
- With React Compiler enabled, do not add `useMemo`, `useCallback` or `memo` by hand; check that a component compiled (DevTools marks it) before blaming memoization. Code that breaks the rules of React is skipped by the compiler, so fix lint errors from `eslint-plugin-react-hooks` (v6+ includes compiler rules).
- Without the compiler, memoize only components the profile shows are hot, and stabilize the props passed to them; a `memo` component that receives a new object every render does nothing.
- `useTransition` and `useDeferredValue` keep typing responsive while a heavy list re-renders. They do not make the work cheaper.
- Virtualize long lists (TanStack Virtual, react-window). Split rarely used screens with `lazy()` and `Suspense`.
- `<Activity mode="hidden">` (19.2) keeps a tab's state and can pre-render it; hidden trees still use memory.

## Typing React (beyond `../../engineering-practices/references/typescript.md`)

- Type props with an interface or type alias; take children as `React.ReactNode`. Extend native element props with `React.ComponentProps<"button">` and spread the rest.
- Event types: `React.ChangeEvent<HTMLInputElement>`, `React.FormEvent<HTMLFormElement>`; let inference type inline handlers.
- Generic components (`function Select<T>(props: SelectProps<T>)`) keep option types linked to `onChange`.
- `@types/react` 19: `useRef` requires an argument, `ref` callbacks must not return a value except a cleanup, and the global `JSX` namespace moved to `React.JSX`. Run `npx types-react-codemod@latest preset-19 ./src`.
- Parse API responses with a schema before they reach components; component props are not a validation layer.

## Testing

- React Testing Library with `user-event`: query by role and accessible name, await async UI with `findBy*`, assert visible results. Avoid `container.querySelector` and testing hook internals.
- Wrap renders in the providers the component needs (router, a fresh `QueryClient` with retries off, theme) through one `TestProviders` helper.
- `act(...)` warnings mean an update happened after the test stopped waiting; await the resulting UI instead of wrapping more code in `act`.
- `renderHook` tests custom hooks with logic; test simple hooks through the component that uses them.
- Mock the network with MSW (`web-frontend-foundations.md`), not `fetch` by hand.

## Migrating class components

| Class | Function component |
|---|---|
| `this.state`, `setState` (merges) | `useState` per value or `useReducer` (does not merge objects) |
| `componentDidMount` plus `componentWillUnmount` | One `useEffect` with cleanup |
| `componentDidUpdate` comparing props | Effect with those dependencies, or derive during render |
| `shouldComponentUpdate`, `PureComponent` | `memo` (or nothing with React Compiler) |
| Instance fields not used for rendering | `useRef` |
| Higher-order components, render props | Custom hooks |
| `componentDidCatch`, `getDerivedStateFromError` | Keep a class error boundary or use `react-error-boundary` |

Migrate leaf components first, one per commit, with tests pinned before the change. Mixing class and function components in one tree is fine; there is no need to convert everything.

## Upgrading 18 to 19

1. Upgrade to 18.3 first: it warns about every API 19 removes.
2. Run the codemods: `npx codemod@latest react/19/migration-recipe` and the types codemod above.
3. Replace removed APIs: `ReactDOM.render` and `hydrate` (use `createRoot`, `hydrateRoot`), `unmountComponentAtNode`, `findDOMNode`, string refs, legacy context (`contextTypes`), `propTypes` and `defaultProps` on function components (use TypeScript and default parameters), `react-test-renderer/shallow`; import `act` from `react`.
4. Upgrade libraries that pin React peer versions (router, data, form, UI kits, testing library) in the same change.
5. Render errors are no longer re-thrown to `window.onerror`; wire `onUncaughtError` and `onCaughtError` if error reporting relied on that.

## Security hooks

Review-level traps for React code are in the React section of `../../code-security-review/references/language-pitfalls.md`. While writing:

- `dangerouslySetInnerHTML` only with sanitized content (`web-frontend-foundations.md`).
- Validate URL schemes before binding user data to `href` and `src`.
- Server components and server functions run on the server: patch React and the framework promptly. The December 2025 critical remote-code-execution advisory for React Server Components (CVE-2025-55182) affected 19.0 to 19.2.0 server packages; check that `react-server-dom-*` and the framework are on patched releases (`nextjs.md`).

## Common breakages

| Message or symptom | Cause | Fix |
|---|---|---|
| "Too many re-renders" | `setState` called during render, often `onClick={setOpen(true)}` | Pass a function: `onClick={() => setOpen(true)}` |
| "Rendered more hooks than during the previous render" | A hook inside a condition, loop or after an early return | Call hooks unconditionally at the top level |
| "Cannot update a component while rendering a different component" | A child sets parent state during render | Move the update into an effect or event handler, or lift the computation |
| Effect runs in a loop | An object, array or function dependency recreated every render | Move it inside the effect, memoize it, or depend on primitives |
| List rows swap their input values | Index keys | Use stable ids |
| "A component is changing an uncontrolled input to be controlled" | `value` started as `undefined` | Initialize with `""` |
| Double requests in development | StrictMode remounting effects | Make the effect safe to run twice (abort or ignore stale results); keep StrictMode |

## Done when

- [ ] `tsc --noEmit`, the hooks lint rules, tests and the build pass.
- [ ] No effect exists that only derives state or reacts to a user event.
- [ ] New async UI shows pending, error and success, and tests cover error and success.
- [ ] Performance changes come with profiler evidence; no blanket memoization.
- [ ] An upgrade leaves no React deprecation warnings in the console or test output.
