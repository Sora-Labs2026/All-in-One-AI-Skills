# C# and .NET

Read this before writing or changing C# on .NET: ASP.NET Core APIs, workers, libraries, EF Core data access, tests, Blazor. Security traps (deserialization, raw SQL, authorization attributes, antiforgery) are in `../../code-security-review/references/language-pitfalls.md#c-and-net`.

## Orient first

- **Target framework:** `<TargetFramework>` in each `.csproj` (`net8.0`, `net9.0`, `net10.0`; `net4x` means .NET Framework, a different runtime with different APIs). `global.json` pins the SDK and its `rollForward` policy; use the SDK it names.
- **Support dates (as published in 2026; check Microsoft's support policy page):** .NET 10 is the current long-term-support release (November 2025, supported to November 2028). Both .NET 8 (LTS) and .NET 9 (STS) reach end of support in November 2026. Flag an upgrade to the user rather than doing it inside a feature change.
- **Language version** follows the framework (C# 12 with .NET 8, 13 with .NET 9, 14 with .NET 10) unless `<LangVersion>` overrides it.
- **Shared build settings** live in `Directory.Build.props` (nullable, warnings as errors, analyzers) and package versions in `Directory.Packages.props` when central package management is on. Add a package version there, not in the project file.
- Solution: `.sln` or the newer `.slnx`. Run commands at the solution level unless the project says otherwise.

```bash
dotnet restore --locked-mode        # if packages.lock.json exists
dotnet build -warnaserror           # match CI; analyzers run during build
dotnet test --no-build
dotnet format --verify-no-changes
dotnet list package --vulnerable --include-transitive
```

## Language idioms

- **Nullable reference types on** (`<Nullable>enable</Nullable>`). Fix warnings instead of sprinkling `!`; validate at boundaries so the inside works with non-null types.
- Records for DTOs and value objects; `required` members and `init` setters for construction without long constructors; primary constructors (C# 12) for simple dependency injection, keeping in mind their parameters are mutable captures, not readonly fields.
- Pattern matching (`switch` expressions, property and list patterns) for branching on shape; exhaustive handling of closed hierarchies via a `default` that throws.
- File-scoped namespaces and global usings if the project uses them.
- Time: `DateTimeOffset` for instants; inject `TimeProvider` (.NET 8+) instead of reading `DateTime.UtcNow` directly, so tests control time.
- Money: `decimal`, never `double`.
- String comparison for identifiers: `StringComparison.Ordinal` or `OrdinalIgnoreCase`.

## Async

- Async all the way: no `.Result`, `.Wait()` or `GetAwaiter().GetResult()` on tasks in application code. They block threads and can deadlock in UI or legacy ASP.NET contexts.
- `async void` only for event handlers; everything else returns `Task` or `ValueTask`.
- Accept a `CancellationToken` in every async method that does I/O and pass it to every call beneath (ASP.NET Core binds one to `HttpContext.RequestAborted`).
- `ConfigureAwait(false)` in libraries that might run under a synchronization context; ASP.NET Core application code has none and does not need it.
- A `ValueTask` must be awaited exactly once; when in doubt, return `Task`.
- `IAsyncEnumerable<T>` with `await foreach` for streaming results.

## ASP.NET Core

- **Minimal APIs or controllers:** follow the project. Minimal APIs: group routes with `MapGroup("/orders")`, attach `RequireAuthorization()` to the group, return `TypedResults` so the OpenAPI document knows the response types.
- **Validation:** data annotations or FluentValidation in controllers; minimal APIs get built-in validation in .NET 10 (`AddValidation()`); on older versions use an endpoint filter or validator library the project has.
- **Errors:** `AddProblemDetails()` plus `UseExceptionHandler()` and an `IExceptionHandler` (.NET 8+) that maps domain exceptions to Problem Details. No stack traces outside Development.
- **Middleware order matters:** exception handling first, then HTTPS redirection, static files, routing, CORS, authentication, authorization, then endpoints. Middleware added after `MapControllers` or the endpoint mapping runs for nothing.
- **OpenAPI:** .NET 9+ templates use `Microsoft.AspNetCore.OpenApi` (`AddOpenApi()`, `MapOpenApi()`); older projects use Swashbuckle or NSwag. Keep whatever the project has.
- **Options pattern:** bind configuration sections to classes with `AddOptions<T>().Bind(...).ValidateDataAnnotations().ValidateOnStart()` so bad settings fail at startup. `IOptions<T>` is read once, `IOptionsSnapshot<T>` per request, `IOptionsMonitor<T>` sees reloads.

## Dependency injection lifetimes

| Lifetime | Use for | Trap |
|---|---|---|
| Singleton | Stateless services, caches, `HttpClient` factories, configuration | Capturing a scoped service (a "captive dependency"): the scoped one lives forever and is shared across requests and threads |
| Scoped | `DbContext`, unit-of-work services, anything per request | Resolving it from the root provider in a background service; create a scope with `IServiceScopeFactory` instead |
| Transient | Lightweight, stateless helpers | Disposable transients resolved from the root are kept until shutdown |

Development builds validate scopes by default; keep `ValidateScopes` and `ValidateOnBuild` on in tests too.

## Outbound HTTP and background work

- Never `new HttpClient()` per call (socket exhaustion) or one static client without `PooledConnectionLifetime` (stale DNS). Use `IHttpClientFactory` with named or typed clients, with a timeout and, on .NET 8+, `Microsoft.Extensions.Http.Resilience` (`AddStandardResilienceHandler()`) for retries with backoff and circuit breaking, consistent with `../../engineering-practices/references/resilience.md`.
- `BackgroundService`: an unhandled exception stops the host (.NET 6+ default). Catch and log per work item, honor the stopping token, and create a DI scope per unit of work.
- Logging: `ILogger<T>` with message templates (`logger.LogInformation("Charged {OrderId}", id)`), not string interpolation, so properties stay structured; `[LoggerMessage]` source-generated methods for hot paths.

## Entity Framework Core

- `DbContext` is scoped and **not thread-safe**: never run two queries on the same context concurrently (`Task.WhenAll` over one context fails or corrupts state). Use separate contexts (`IDbContextFactory<T>`) for parallel work.
- Reads: `AsNoTracking()` and projections (`Select(o => new OrderDto(...))`) so only needed columns load and nothing is tracked.
- Related data: `Include`/`ThenInclude` for what you need. Several collection includes multiply rows (cartesian explosion); use `AsSplitQuery()` there.
- Watch for N+1 through lazy-loading proxies; if the project enabled them, check query counts in tests.
- Set-based writes: `ExecuteUpdateAsync`/`ExecuteDeleteAsync` (EF Core 7+) run one statement and bypass the change tracker, so tracked entities in the same context go stale.
- Concurrency: a concurrency token (`[Timestamp]` row version on SQL Server, `xmin` on PostgreSQL via Npgsql) on aggregates edited concurrently; handle `DbUpdateConcurrencyException`.
- **Migrations:**
  - Generate with `dotnet ef migrations add <Name>`, read the generated code and the SQL (`dotnet ef migrations script --idempotent`), and apply the rules in `../../engineering-practices/references/data-and-migrations.md`.
  - Do not call `Database.Migrate()` at startup when several instances start at once; apply migrations as a deployment step (script or migration bundle) that the user runs.
- Raw SQL only through `FromSql`/`FromSqlInterpolated` or explicit parameters.
- The in-memory provider does not behave like a relational database (no transactions, no constraints, different query translation); test data access against SQLite in-memory at minimum, or the real engine in a container.

## Testing

- Use the framework the project has (xUnit, including v3; NUnit; MSTest). Name tests by behavior.
- Integration tests: `WebApplicationFactory<Program>` with `ConfigureTestServices` to swap dependencies, Testcontainers for the database. If the test project cannot see the top-level `Program` class, add `public partial class Program { }` to the web project.
- Inject `TimeProvider` and use `FakeTimeProvider` instead of sleeping.
- **Licensing check before adding test or utility libraries:** several popular .NET packages moved newer major versions to commercial licenses in 2025 (for example FluentAssertions from version 8, MediatR and AutoMapper). Keep the version the project already uses, and ask before adding or upgrading one.

## Blazor (brief)

- .NET 8+ render modes: static server rendering, Interactive Server (a SignalR circuit per user, holding state on the server), Interactive WebAssembly (code and data downloaded to the browser, so no secrets and server-side authorization for every call) and Interactive Auto.
- Server mode: plan for reconnection and per-circuit memory; WebAssembly mode: watch download size and use trimming.
- Components receive parameters and raise `EventCallback`s; keep business logic in injected services.
- Visual quality and accessibility go through ProductCraft's UI modules.

## Performance

- Measure with BenchmarkDotNet for code paths, `dotnet-counters` and `dotnet-trace` for running processes.
- Common wins: avoid LINQ allocation in hot loops, `Span<T>`/`ArrayPool<T>` for buffers, `StringBuilder` for concatenation, `HybridCache` (.NET 9+) or `IMemoryCache` for repeated reads, compiled queries for very hot EF queries.
- Native AOT shortens startup and memory but restricts reflection and dynamic code; adopt it only for a measured need and with the AOT analyzers clean.

## Done when

- [ ] `dotnet build` (with the project's warnings-as-errors and analyzers), `dotnet test` and `dotnet format --verify-no-changes` pass.
- [ ] No sync-over-async; cancellation tokens flow through new async paths.
- [ ] No captive dependencies; background services create scopes; outbound HTTP goes through the client factory with timeouts.
- [ ] EF changes use projections or no-tracking for reads, migrations were reviewed as SQL, and nothing runs migrations at startup in multi-instance deployments.
- [ ] New packages were checked for license and support status, and versions were added centrally if the project uses central package management.
