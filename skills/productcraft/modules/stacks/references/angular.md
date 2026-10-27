# Angular

Read this when you write or change Angular components, services, signals, RxJS streams, routing, forms, NgRx state, server-side rendering or tests, or upgrade Angular. Cross-framework practice (state kinds, data caching, forms, testing layers, builds, security sinks) is in `web-frontend-foundations.md`.

## Versions that change the advice

Angular ships a major every six months, each supported for 18 months. Read `@angular/core` in the lockfile; follow the update guide at update.angular.dev for the exact path.

| Version | What matters |
|---|---|
| 17 (Nov 2023) | Built-in control flow (`@if`, `@for` with required `track`, `@switch`), `@defer`, esbuild-based application builder, standalone projects by default |
| 18 (May 2024) | Experimental zoneless change detection; stable signal inputs, outputs and queries arrived over 17.x to 19 |
| 19 (Nov 2024) | Components are standalone unless `standalone: false`; `linkedSignal`; experimental `resource`; incremental hydration preview |
| 20 (May 2025) | `effect`, `linkedSignal` and `toSignal` stable; zoneless stable during 20.x; experimental `httpResource`; `*ngIf`, `*ngFor` and `*ngSwitch` deprecated |
| 21 (Nov 2025) | New projects are zoneless and use Vitest as the test runner; experimental signal forms |

Experimental and developer-preview APIs can change between minors. Use them only when the project already does or the user accepts the churn.

## Components

- Standalone components, `ChangeDetectionStrategy.OnPush`, and dependencies through `inject()`.
- Signal-based APIs: `input()`, `input.required()`, `output()`, `model()` for two-way binding, `viewChild()` and `contentChildren()` for queries.
- Built-in control flow in templates. `@for` needs `track item.id` (a stable id); tracking by `$index` causes the same row-state bugs as index keys elsewhere.
- Keep components presentational where possible: inputs in, outputs out, data access in services.

```ts
@Component({
  selector: "app-invoice-row",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span>{{ invoice().number }}</span>
    <span>{{ total() }}</span>
    @if (invoice().status === "overdue") { <strong>Overdue</strong> }
    <button type="button" (click)="paid.emit(invoice().id)">Mark paid</button>
  `,
})
export class InvoiceRow {
  invoice = input.required<Invoice>();
  paid = output<string>();
  private fmt = inject(MoneyFormatter);
  total = computed(() => this.fmt.format(this.invoice().totalMinor, this.invoice().currency));
}
```

## Signals or RxJS

- **Signals for state:** `signal()` holds it, `computed()` derives it, `linkedSignal()` is a writable value that resets when its source changes (a selection that resets when the list changes).
- **`effect()` only to push state out to non-signal APIs** (localStorage, a chart library, logging). Propagating state from one signal to another inside an effect causes glitches and loops; use `computed` or `linkedSignal`. `untracked()` reads a signal without subscribing.
- **RxJS for event streams and async coordination:** debouncing input, cancelling stale requests, websockets, retries, combining streams. Convert at the edges with `toSignal()` and `toObservable()`.
- Pick the flattening operator by what should happen to the previous inner request:

| Operator | Previous inner work | Use for |
|---|---|---|
| `switchMap` | Cancelled | Search-as-you-type, loading by route parameter |
| `concatMap` | Queued, run in order | Ordered writes that must not overlap |
| `mergeMap` | Runs in parallel | Independent requests; cap with the `concurrent` argument |
| `exhaustMap` | New events ignored while busy | Submit and login buttons |

- Put `catchError` inside the inner observable so one failed request does not complete the outer stream.
- Unsubscribe automatically: the `async` pipe, `toSignal()`, or `takeUntilDestroyed()`. Avoid nested `subscribe` calls.
- `shareReplay({ bufferSize: 1, refCount: true })` to share one request among subscribers without keeping it alive forever.

```ts
export class CustomerSearch {
  private api = inject(CustomerApi);
  query = signal("");
  results = toSignal(
    toObservable(this.query).pipe(
      debounceTime(250),
      distinctUntilChanged(),
      switchMap((q) => q.length < 2 ? of([]) : this.api.search(q).pipe(catchError(() => of(null)))),
    ),
    { initialValue: [] as Customer[] | null },   // null renders the error state
  );
}
```

## Data access

- Configure HTTP once: `provideHttpClient(withFetch(), withInterceptors([authInterceptor, errorInterceptor]))`. Functional interceptors add credentials, map errors and log; they never swallow errors silently.
- Services own API calls and expose observables or signals. Components do not build URLs.
- `resource()` and `httpResource()` turn requests into signals with loading and error state; check their status in your version before relying on them.
- With SSR, the HTTP transfer cache (`provideClientHydration(withHttpTransferCacheOptions(...))`) reuses server responses during hydration. Requests carrying authorization headers are excluded by default; keep it that way for per-user data.

## State

- Services with private signals and public read-only views cover most apps.
- NgRx SignalStore (`@ngrx/signals`) suits feature stores with computed views and methods.
- Classic NgRx Store (actions, reducers, effects, selectors, entity adapter) suits large apps that benefit from an event log and devtools time travel. Reducers stay pure, effects handle side effects, and components select narrow slices.
- Do not mirror server data into a store when a request-level cache would do.

## Routing

- `provideRouter(routes, withComponentInputBinding())` binds route params to component inputs.
- Lazy-load with `loadComponent` and `loadChildren`; choose a preloading strategy deliberately.
- Functional guards (`CanActivateFn`, `CanMatchFn`) are UX; the API authorizes.
- Resolvers block navigation until data arrives. Prefer loading states inside the component unless the page is useless without the data.

## Forms

- Typed reactive forms (`NonNullableFormBuilder`) for anything non-trivial; template-driven forms for small ones.
- Map server validation errors onto controls with `setErrors`, and keep the submit button state honest while pending (`../../forms-conversion.md`, `../../interaction-feedback.md`).
- Signal forms (21) are experimental; do not migrate production forms to them without agreement.

## Server-side rendering and hydration

- `@angular/ssr` with `provideClientHydration(withEventReplay())` replays clicks that happen before hydration.
- Do not touch `window`, `document` or `localStorage` during server rendering. Use `afterNextRender()` or `afterRenderEffect()` for DOM work, and `isPlatformBrowser()` sparingly.
- Hydration errors (NG05xx) usually come from DOM manipulation outside Angular or invalid HTML nesting. `ngSkipHydration` is a last resort for a third-party component, not a fix.
- Incremental hydration with `@defer (hydrate on viewport)` keeps heavy widgets inert until needed.

## Performance

- OnPush plus signals means only components whose inputs or read signals changed re-render. Zoneless apps update only through signals, the `async` pipe, `markForCheck()` or events; a plain field changed in a `setTimeout` will not render.
- `@defer (on viewport)` for heavy, below-the-fold components.
- Template function calls are fine when they read signals; otherwise use pure pipes or `computed`.
- Keep `budgets` in `angular.json` and treat a budget error as a failed build.
- `NgOptimizedImage` (`ngSrc`, `priority` on the LCP image) for images.
- Profile with Angular DevTools before optimizing (`../../engineering-practices/references/performance.md`).

## Testing

- TestBed with standalone imports; `provideHttpClient()` plus `provideHttpClientTesting()` and `HttpTestingController` to assert requests; `httpTesting.verify()` in `afterEach`.
- Component harnesses from `@angular/cdk/testing` for Material and your own reusable components.
- `await fixture.whenStable()` instead of `fakeAsync` in zoneless tests; set signal inputs with `fixture.componentRef.setInput()`.
- Marble tests (`TestScheduler`) for non-trivial RxJS pipelines.
- Karma is deprecated. New projects use Vitest (21); existing projects migrate deliberately. End-to-end tests use Playwright (`../../builder-tools/references/playwright-web-testing.md`).

## Security hooks

- Angular escapes interpolation and sanitizes `[innerHTML]`, `[href]` and `[src]`. `DomSanitizer.bypassSecurityTrust*` turns that off; use it only on constants you control, never on user or AI-generated content.
- Never compile templates at runtime from user input.
- With cookie sessions, `HttpClient`'s XSRF support (`withXsrfConfiguration`) adds the token header to same-origin mutating requests; the server must issue and check the token.
- Consider Trusted Types in the CSP; Angular supports them.

## Upgrading

1. One major at a time: `ng update @angular/core@<n> @angular/cli@<n>`, then the other `@angular/*` packages and third-party libraries with Angular peer ranges.
2. Run the optional migrations once the app is green: `ng generate @angular/core:control-flow`, `@angular/core:standalone`, `@angular/core:signal-input-migration`, `@angular/core:output-migration`, `@angular/core:signal-queries-migration`, `@angular/core:inject`.
3. Library peer dependencies (Material, NgRx, component kits) are the usual blocker; check their release for your target major first.

## Common breakages

| Message or symptom | Cause | Fix |
|---|---|---|
| `NG0100: ExpressionChangedAfterItHasBeenChecked` (development) | State changed during change detection, often in a lifecycle hook or a child writing parent state | Derive with `computed`, move the write to an event, restructure ownership; never wrap in `setTimeout` |
| `NullInjectorError: No provider for X` | Service not provided where it is injected | `providedIn: "root"`, or provide it in the route or component |
| View does not update (zoneless or OnPush) | Plain mutable field or mutated object | Signals, immutable updates, the `async` pipe |
| `@for` loop error about tracking | Missing `track` | `track item.id` |
| Memory grows on navigation | Manual subscriptions without teardown | `takeUntilDestroyed`, `toSignal`, the `async` pipe |
| Hydration mismatch errors | DOM touched outside Angular, invalid nesting | `afterNextRender`, fix markup |

## Done when

- [ ] `ng build` (production configuration) passes within budgets; `ng test` and lint pass.
- [ ] No new manual subscription without automatic teardown; no `bypassSecurityTrust*` on untrusted data.
- [ ] New async UI shows loading, error and success; tests cover error and success.
- [ ] SSR pages hydrate with no console errors.
- [ ] Experimental APIs used only with the user's agreement, noted in the report.
