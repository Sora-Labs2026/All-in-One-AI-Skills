# NestJS

Read this when you build or change a NestJS service: modules and dependency injection, controllers, validation, guards and authorization, configuration, persistence, errors, tests, or a migration from Express. GraphQL resolvers are in `graphql.md`, gateways and websockets in `realtime-websockets.md`; API contract rules are in `../../engineering-practices/references/api-contracts.md`; runtime practice in `javascript-runtime.md`.

## Versions and fit

- **NestJS 11 (January 2025):** Express 5 is the default HTTP adapter, Node.js 20 or later, a JSON mode for the built-in logger. Express 5 changed route path syntax: wildcards must be named (`/files/*path`), optional segments use braces (`/items{/:id}`), and regular-expression characters in paths are gone. Check routes after upgrading.
- Read `@nestjs/core` and the adapter (`@nestjs/platform-express` or `@nestjs/platform-fastify`) in the lockfile.
- NestJS fits services with many modules and a team that wants enforced structure and dependency injection. For a small service or an edge runtime, a lighter framework (Fastify, Hono) is simpler; do not introduce Nest into a project that does not use it without asking.

## Structure

- One module per feature (`InvoicesModule`) with its controller, service and data access. Export only what other modules need; a module that exports everything is a global in disguise.
- Controllers are thin: parse the request (through DTOs and pipes), call one service method, return a response DTO. Business rules live in services; data access in repositories or the ORM layer behind them.
- `forwardRef()` to break a circular dependency is a design smell. Extract the shared part into its own provider or communicate through events.
- Avoid a "shared" or "common" module that accumulates unrelated providers.

## The request pipeline

| Stage | Order | Use for |
|---|---|---|
| Middleware | First | Express- or Fastify-level concerns: request ids, raw body capture, CORS, helmet |
| Guards | After middleware | Authentication and coarse authorization; return `false` or throw to stop |
| Interceptors (before) | After guards | Timing, logging context, caching, transforming the call |
| Pipes | Before the handler | Validating and transforming parameters and bodies |
| Handler | | Controller method |
| Interceptors (after) | After the handler | Mapping responses, serialization |
| Exception filters | On any thrown error | Mapping errors to the response format |

## Validation

Enable one global pipe so no endpoint is left unvalidated:

```ts
// main.ts
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,              // strip properties without decorators
  forbidNonWhitelisted: true,   // or reject them outright (clearer for clients)
  transform: true,              // build DTO instances, convert path and query params
}));
```

- DTOs must be classes (interfaces vanish at runtime, so nothing gets validated).
- Nested objects need `@ValidateNested()` plus `@Type(() => Child)`; arrays of primitives `@IsString({ each: true })`, with `@ArrayMaxSize` to bound them.
- `transformOptions: { enableImplicitConversion: true }` converts by the TypeScript type: the string `"false"` becomes the boolean `true`. Convert booleans explicitly with `@Transform`.
- Projects using Zod can validate with a Zod pipe instead; do not mix both styles in one module.

## Responses

- Return response DTOs or explicit mappings, never ORM entities: an entity serialized as-is leaks password hashes, internal flags and relations (LaunchGuard control 17). `ClassSerializerInterceptor` with `@Exclude()` works, but an allowlist mapping is harder to get wrong.
- Use one error shape across the API, set in a global exception filter (Problem Details per `../../engineering-practices/references/api-contracts.md`). Never send stack traces or database errors to clients.
- `@nestjs/swagger` with its CLI plugin generates the OpenAPI document from DTOs with few manual decorators. Commit or check the generated spec in CI so contract changes show up in review.

## Authentication and authorization

- Make authentication global and opt out explicitly, so a new controller is protected by default:

```ts
// app.module.ts
providers: [{ provide: APP_GUARD, useClass: JwtAuthGuard }]

// public.decorator.ts
export const IS_PUBLIC = "isPublic";
export const Public = () => SetMetadata(IS_PUBLIC, true);

// jwt-auth.guard.ts
@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(private reflector: Reflector, private tokens: TokenVerifier) {}
  async canActivate(ctx: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC, [ctx.getHandler(), ctx.getClass()]);
    if (isPublic) return true;
    const req = ctx.switchToHttp().getRequest();
    req.user = await this.tokens.verify(req.headers.authorization); // throws UnauthorizedException
    return true;
  }
}
```

- Token verification pins the algorithm and checks issuer, audience and expiry. Do not hand-roll JWT parsing.
- Role guards answer "may this kind of user call this endpoint". They do not answer "may this user touch this record": check ownership or tenancy in the service query (`where: { id, orgId: user.orgId }`) for every object-level operation (LaunchGuard controls 6 and 7).
- Login throttling and account-recovery abuse belong to `../../credential-shield/GUIDE.md`. `@nestjs/throttler` covers general rate limits; behind a proxy, configure trusted proxy settings so it sees client addresses, not the proxy's.

## Configuration

- `@nestjs/config` with a validation schema (Zod or Joi) evaluated at startup; the app refuses to boot with missing or malformed settings.
- Inject a typed config object; do not read `process.env` throughout the code.
- Secrets come from the environment or a secret manager, never from committed files (`../../agent-safety/GUIDE.md`).

## Persistence

- The ORM is the project's choice (Prisma, TypeORM, MikroORM, Drizzle). Wrap multi-step writes in one transaction.
- **Uniqueness is enforced by the database, not by a lookup first.** "Find by email, then insert" races under concurrent requests. Insert and translate the unique-violation error:

```ts
async register(dto: RegisterDto): Promise<UserView> {
  const passwordHash = await this.hasher.hash(dto.password);  // never store the plain password
  try {
    const user = await this.prisma.user.create({ data: { email: dto.email.toLowerCase(), passwordHash } });
    return toUserView(user);
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2002") {
      throw new ConflictException({ code: "EMAIL_TAKEN" });
    }
    throw e;
  }
}
```

- Watch for N+1 queries in relation loading (`../../engineering-practices/references/performance.md`).
- Migrations follow `../../engineering-practices/references/data-and-migrations.md`; do not use ORM schema synchronization (`synchronize: true`) outside throwaway local databases.

## Providers and scope

- Providers are singletons by default. `Scope.REQUEST` makes the provider and everything that injects it be created per request, which costs throughput and surprises people. Pass request context explicitly or use `AsyncLocalStorage` (for example through a CLS module) instead.
- Lifecycle: `onModuleInit` for warm-up, `app.enableShutdownHooks()` so `onApplicationShutdown` runs on `SIGTERM` and connections close cleanly.

## Testing

- **Unit:** `Test.createTestingModule({ providers: [Service, { provide: Repo, useValue: fake }] })`; test services with fakes of their collaborators.
- **End to end:** boot the real application module against a real database in a container (Testcontainers or the CI service), call it with `supertest(app.getHttpServer())`, and close the app in `afterAll`. Mocking the ORM in end-to-end tests hides the bugs that matter (constraints, transactions, query shape).
- Replace external clients with `overrideProvider(...)`; replace authentication in tests with `overrideGuard(...)` or by issuing real test tokens.
- Test authorization explicitly: one user must not read or change another tenant's record.

## Microservices, GraphQL and events

- `@nestjs/microservices` transports (Redis, NATS, Kafka, RabbitMQ, gRPC) follow the event rules in `../../engineering-practices/references/api-contracts.md`: ids, versions, deduplication, at-least-once delivery.
- `@nestjs/graphql` resolvers follow `graphql.md`; `@nestjs/websockets` gateways follow `realtime-websockets.md` (authenticate on connection, authorize every subscription and message).

## Migrating from Express

1. Pin behavior with end-to-end tests against the existing Express app first (`../../engineering-practices/references/large-refactors.md`).
2. Nest can run on the existing Express instance (`ExpressAdapter`) or mount the old router, so routes can move one at a time.
3. Map concepts: route handlers to controllers, `express-validator` to DTOs and pipes, auth middleware to guards, logging middleware to interceptors, error middleware to exception filters, manual singletons to providers.
4. Move one route group per change and keep the tests green between steps.

## Common breakages

| Message or symptom | Cause | Fix |
|---|---|---|
| "Nest can't resolve dependencies of X (?, Y)" | The provider at `?` is not in this module, not exported by its module, or that module is not imported | Provide, export and import correctly; check for a cycle |
| The same error but the provider exists | The class was imported with `import type` (or an auto-fixer converted it), so no runtime metadata | Use a value import for injected classes; exclude them from type-only import rules |
| DTO validation does nothing | Global pipe missing, or the parameter type is an interface | Register the pipe; use classes |
| Query `?active=false` treated as true | Implicit conversion of strings to booleans | Explicit `@Transform` |
| Routes 404 after upgrading to 11 | Express 5 path syntax | Rename wildcards and optional segments |
| Throughput drops after adding a provider | Request-scoped provider in a hot path | Singleton plus explicit context |

## Done when

- [ ] Build, lint, unit and end-to-end tests pass; end-to-end tests run against a real database.
- [ ] Every new endpoint validates input through DTOs and is protected unless explicitly marked public.
- [ ] Object-level authorization is in the service query and covered by a cross-tenant test.
- [ ] Responses are DTOs or mappings, with no entity serialized whole.
- [ ] The OpenAPI document reflects the change and breaking changes are classified.
