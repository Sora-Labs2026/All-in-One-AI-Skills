# Hexagonal architecture (ports and adapters) and error mapping across stacks

Read this when business rules are tangled with HTTP handlers, ORM models or vendor SDKs; when the same use case must run from several entry points (HTTP, a queue consumer, a CLI, a scheduled job); when an infrastructure dependency is about to be replaced; or when you need one consistent way to turn domain errors into responses in a given framework. System-level boundaries (services, data ownership, sagas) are in `architecture-and-services.md`; interface design in general is in `../../engineering-practices/references/api-contracts.md#in-process-interfaces`; enforcing module boundaries with tools is in `../../engineering-practices/references/large-refactors.md#module-boundaries`.

## When it pays, and when it does not

| Use it | Skip it |
|---|---|
| Rules worth protecting: pricing, eligibility, state machines, ledgers | CRUD screens that map a form to a table and back |
| Two or more entry points share a use case | One entry point, and the framework's conventions already keep code testable |
| A dependency is likely to change or must be faked in tests (payment provider, search engine, message broker) | A dependency used in one place, unlikely to change, that tests can run for real (a database in a container) |
| Tests are slow or brittle because logic runs only through HTTP and a real database | The team is small and the codebase follows Rails, Laravel or Django conventions well |

The cost is real: more files, mapping code at every boundary, and indirection a newcomer must learn. Introduce a port when there is a second implementation (the production adapter plus an in-memory fake counts) or a concrete change coming, not in case one appears (`../../engineering-workflow/references/change-discipline.md`). Apply it to the parts of the system that earn it; a mixed codebase is normal.

## Vocabulary and the dependency rule

- **Domain:** entities, value objects and rules. Plain language code: no framework, ORM, HTTP or SDK imports.
- **Application (use cases):** one object or function per operation (`PlaceOrder`, `ApproveRefund`). It loads what it needs through ports, applies domain rules, saves through ports and returns a plain result.
- **Ports:** interfaces owned by the application. Outbound ports describe what the core needs (`Orders`, `PaymentGateway`, `Clock`, `EventPublisher`); inbound ports are the use cases' own signatures.
- **Adapters:** code at the edge that implements outbound ports with real technology (a PostgreSQL repository, a provider client) or calls inbound ports from a delivery mechanism (an HTTP controller, a queue consumer, a CLI command).
- **Composition root:** the one place that constructs adapters and passes them to use cases.

Dependencies point inward only: adapters import the application and domain; the application imports the domain and its own port definitions; the domain imports nothing outside itself. Framework annotations on domain classes (ORM mappings, validation decorators, serializer fields) break the rule; map at the adapter instead.

## Designing ports

- Name ports after the capability the core needs, in domain language: `PaymentGateway.authorize(order, amount)`, not `StripeClient` or `HttpPost`.
- Shape them by what the use cases need, not by what the database offers. A repository with `get(id)`, `save(order)` and the few queries the use cases run beats a generic `find(where)` that leaks the query language.
- Pass and return domain types or plain data, never ORM rows, HTTP requests or SDK response objects.
- Keep them coarse: one call per business intent. A chatty port mirrors the implementation and gives nothing to fake.
- Infrastructure details (retries, timeouts, idempotency keys, pagination tokens) live in the adapter; the port states the guarantee (`authorize` is safe to retry with the same order).

## A use case with its ports (TypeScript)

```ts
// application/ports.ts
export interface Orders { get(id: OrderId): Promise<Order | null>; save(order: Order): Promise<void>; }
export interface PaymentGateway {
  // Idempotent per order: calling twice for the same order returns the same authorization.
  authorize(orderId: OrderId, amount: Money): Promise<{ authorizationId: string }>;
}

// application/authorize-order.ts
export class AuthorizeOrder {
  constructor(private readonly orders: Orders, private readonly payments: PaymentGateway) {}

  async execute(orderId: OrderId): Promise<AuthorizeResult> {
    const order = await this.orders.get(orderId);
    if (!order) return { ok: false, error: "not_found" };
    if (!order.canBeAuthorized()) return { ok: false, error: "invalid_state" };

    const pending = order.markPendingPayment();                  // a visible intermediate state first
    await this.orders.save(pending);
    const { authorizationId } = await this.payments.authorize(pending.id, pending.total);
    await this.orders.save(pending.markAuthorized(authorizationId));
    return { ok: true, authorizationId };
  }
}
```

The order is saved as pending before the external call, and the gateway call is idempotent per order, so a crash between the two steps can be retried without a second charge. Order the steps so that every intermediate state is valid and recoverable (`../../engineering-practices/references/resilience.md`).

In Python, ports are `typing.Protocol` classes and use cases are plain classes or functions that receive them; in Go, small interfaces declared in the consuming package; in Java and Kotlin, interfaces in an `application.port` package with Spring or another container only in the composition root.

## Transactions

- A use case usually is one unit of work. Expose it through a port (`UnitOfWork` with `run(fn)`), or let the inbound adapter open the transaction around the use case call (a Spring `@Transactional` service facade, a Django `transaction.atomic()` around the call, a NestJS interceptor).
- Never hold a database transaction open across a slow external call; split the work into steps with recorded intermediate states, as above.
- Publishing events and writing data must not diverge: put an outbox behind the `EventPublisher` port when both must happen (`../../engineering-practices/references/resilience.md`).

## Composition root per stack

| Stack | Where wiring lives |
|---|---|
| Node.js, Express, Fastify | One `buildApp(deps)` or container module; no module-level singletons in the core |
| NestJS | Module `providers` with tokens: `{ provide: PAYMENT_GATEWAY, useClass: StripeGateway }`; inject with `@Inject(PAYMENT_GATEWAY)` (`nestjs.md`) |
| FastAPI | Dependencies that build use cases from adapters; tests swap them with `app.dependency_overrides` (`fastapi.md`) |
| Django | A small `services` or `wiring` module per app that constructs use cases; views call it. Keep models as the persistence adapter |
| Laravel | Service provider bindings: `$this->app->bind(PaymentGateway::class, StripePaymentGateway::class)` |
| Spring | `@Configuration` classes that create beans for adapters and use cases; domain classes without annotations |
| Go | `main.go` or a `wire` package constructs everything explicitly with `New...` functions |

## Errors across boundaries

The rules (classify failures, never swallow, keep the cause, log once at the boundary) are in `../../engineering-practices/references/resilience.md`; the response shape is Problem Details from `../../engineering-practices/references/api-contracts.md`. In a ports-and-adapters design they fall into three layers:

1. **Outbound adapters translate infrastructure errors** into the port's terms: a unique-constraint violation becomes `DuplicateEmail`, a provider's declined code becomes `PaymentDeclined`, a timeout becomes `PaymentGatewayUnavailable`. The core never sees SQL states or SDK exceptions.
2. **Use cases return expected business outcomes** as typed results or domain exceptions with stable codes, and let unexpected failures propagate.
3. **Inbound adapters map once** to the transport: one central handler per application, not a `try` in every controller.

| Stack | Central mapping hook |
|---|---|
| Express 5 | Error-handling middleware `(err, req, res, next)`; Express 5 forwards rejected promises from async handlers |
| NestJS | A global exception filter (`app.useGlobalFilters` or `APP_FILTER`) |
| FastAPI | `@app.exception_handler(DomainError)` plus a handler for `RequestValidationError` |
| Django REST Framework | `EXCEPTION_HANDLER` in `REST_FRAMEWORK` settings |
| Laravel 11+ | `->withExceptions(fn (Exceptions $e) => $e->render(...))` in `bootstrap/app.php`, or a `render()` method on the exception class |
| Rails | `rescue_from DomainError, with: :render_problem` in `ApplicationController` |
| Spring Boot 3 | `@RestControllerAdvice` returning `ProblemDetail` |
| ASP.NET Core 8+ | `IExceptionHandler` with `AddProblemDetails()` |
| Go `net/http` | One helper that maps with `errors.Is` and `errors.As` to status and code |

Queue consumers and CLIs map the same domain errors to their own outcomes: acknowledge and record, retry later, dead-letter, or a non-zero exit code. Front ends map error codes, not message text, to user-facing copy and keep a generic fallback (`../../interaction-feedback.md`).

## Testing per boundary

- **Domain:** plain unit tests, no fakes needed.
- **Use cases:** in-memory fakes for outbound ports (a map-backed `Orders`, a scripted `PaymentGateway`, a fixed `Clock`). Assert outcomes and state, not call sequences.
- **Port contract suites:** write one test suite per outbound port and run it against both the fake and the real adapter (the real one against a database or a provider sandbox in a container). This keeps the fake honest; a fake that diverges from the adapter makes the use-case tests lie.
- **Inbound adapters:** test the mapping: request to use-case input, each result and error to status and body.
- **End to end:** a few critical flows through the real wiring.

## Enforce the dependency rule

Write the rule down as a tool check so it survives the next deadline: `import-linter` contracts (Python), dependency-cruiser or ESLint boundary rules (TypeScript), ArchUnit (Java), Konsist (Kotlin), Pest `arch()` tests or Deptrac (PHP), `internal/` packages and import checks (Go). Prove each rule fails on a deliberate violation once (`../../engineering-practices/references/large-refactors.md#module-boundaries`).

## Moving an existing codebase toward it

1. Pick one use case with frequent change pain and a small blast radius.
2. Pin its current behavior with characterization tests at the HTTP or job level (`legacy-modernization.md`).
3. Extract the use case with explicit input and output types; the controller calls it.
4. Introduce outbound ports around the infrastructure calls it makes, with the existing code as the first adapter.
5. Add fakes and use-case tests; keep the characterization tests until the slice is stable.
6. Repeat slice by slice. No big-bang rewrite, and no new layers in code that nobody is changing.

## Pitfalls

- Ports that mirror the ORM (`findWhere`, `update(fields)`) or one interface per class: indirection without a boundary.
- Domain objects carrying ORM annotations or serializer decorators "to save mapping code".
- Adapters calling other adapters directly, bypassing the use case.
- Use cases reading framework objects (`request`, `session`, job envelopes).
- A transaction opened in the controller and committed in a repository, or held across a network call.
- Wiring spread across files through service locators and global singletons.
- Folders named `domain`, `application` and `adapters` while imports still run in every direction; only the enforced rule makes it hexagonal.

## Done when

- [ ] The decision to use ports for this area has a stated reason (second implementation, entry points, testability).
- [ ] Domain and use-case code import no framework, ORM or SDK types, and a tool check enforces it.
- [ ] Each outbound port has a fake and a contract suite that also runs against the real adapter.
- [ ] Infrastructure errors are translated in adapters, and one central handler per entry point maps domain errors to the transport.
- [ ] Wiring lives in one composition root per application, and the migrated slice passes its characterization tests.
