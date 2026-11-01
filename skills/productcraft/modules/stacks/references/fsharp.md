# F# on .NET

Read this before writing or changing F#: domain modeling, project layout, async code, interop with C# libraries, serialization, and tests. The .NET platform itself (SDK and target frameworks, ASP.NET Core, dependency injection lifetimes, EF Core, support dates, package licensing) is in `dotnet.md`, and it all applies to F#; .NET security traps are in `../../code-security-review/references/language-pitfalls.md#c-and-net`.

## Orient first

- **Project file order is compile order.** In an `.fsproj`, `<Compile Include="..."/>` entries are compiled top to bottom, and a file can use only what is defined above it (or earlier in the same file). A new file must be inserted at the right position; "The value or constructor 'X' is not defined" after adding a file usually means it sits too high. Tests that use it come after it, in the test project.
- **Language version** follows the SDK: F# 8 with .NET 8 (November 2023), F# 9 with .NET 9 (November 2024, adds opt-in nullable reference types), F# 10 with .NET 10 (November 2025). `<LangVersion>` can pin it.
- **Formatting:** Fantomas (`dotnet fantomas --check .` in CI, `dotnet fantomas .` to format), configured in `.editorconfig`. Run it as a local tool from `.config/dotnet-tools.json` (`dotnet tool restore`).
- **Scripts:** `.fsx` files run with `dotnet fsi script.fsx` and can reference packages with `#r "nuget: Name, Version"`; pin versions in scripts that others will run.
- Build and test with `dotnet build` and `dotnet test` like any .NET solution.
- **Dependencies:** NuGet `PackageReference` (possibly with central package management) or Paket (`paket.dependencies` and `paket.lock`, run through `dotnet paket`). Use the one the repository has; never add packages through the other.

## Modeling the domain

- **Records** for data with named fields (immutable, structural equality, `{ order with Status = Paid }` for copies); **discriminated unions** for closed sets of cases; `match` expressions over them are checked for completeness. Treat incomplete-match warnings (FS0025) as errors.
- **Wrapper types** for identifiers and units: a single-case union (`type OrderId = OrderId of Guid`) or a `[<Struct>]` variant for hot paths, or units of measure (`decimal<EUR>`) for quantities.
- **Smart constructors:** make the case constructor private and expose `create : string -> Result<Email, EmailError>`, so invalid values cannot exist past the boundary.
- **Option for absence, Result for expected failure,** exceptions for programmer errors and truly exceptional infrastructure failures. `Option.ofObj` and `Option.ofNullable` convert values coming from C# APIs at the boundary.
- `[<RequireQualifiedAccess>]` on unions and modules whose names would collide (`Status.Active` instead of a bare `Active`).
- Prefer modules of functions over classes; use classes and interfaces for interop with .NET frameworks (ASP.NET Core services, EF Core) and where object identity or mutable state is genuinely needed.

## Composing failures

- `Result.bind`, `Result.map` and `Result.mapError` chain fallible steps. A `result { }` computation expression is **not** part of FSharp.Core; it comes from a library such as FsToolkit.ErrorHandling (which also provides `taskResult { }` and validation helpers). Check that the project references it before using one.
- Model error cases as a union per bounded context (`type PlaceOrderError = EmptyCart | OutOfStock of Sku | PaymentDeclined of string`) and translate them to HTTP responses or messages at the edge.
- Do not hide failures in `try ... with _ -> None`; catch specific exception types and keep the cause.

## Async: `task` versus `async`

| | `task { }` | `async { }` |
|---|---|---|
| Produces | `Task<'T>`, started immediately ("hot") | `Async<'T>`, a description that runs when started ("cold") |
| Cancellation | Explicit: pass a `CancellationToken` through every call | Implicit: the token flows through `Async` automatically |
| Use for | ASP.NET Core handlers, EF Core and most .NET library calls | F#-first libraries and workflows that benefit from implicit cancellation |

- Pick one per layer and convert at the boundary (`Async.AwaitTask`, `Async.StartAsTask`).
- Never block on async work in server code: no `.Result`, `.Wait()` or `Async.RunSynchronously` in request paths.
- `let!` and `do!` inside the expression, `use!` for async-disposable resources; `match!` binds and matches in one step.
- A `task { }` that captures a `use` resource and returns a lazy `seq` disposes the resource before the sequence is read; materialize the results (`List.ofSeq`) inside the task.

## Collections and performance

- `list` for small immutable sequences built by prepending; `array` for indexed access and hot loops; `seq` for lazy pipelines. A `seq` is re-evaluated every time it is enumerated, so materialize it once before enumerating repeatedly or across a resource's lifetime.
- `Map` and `Set` are immutable trees with logarithmic access; use `Dictionary` or `HashSet` inside a function when profiling shows the difference matters, and keep the mutation local.
- Structural equality on large records compares every field; for frequently compared keys use a small wrapper type, or `[<CustomEquality>]` with care.

## Interop with C# and .NET libraries

- **Nulls:** values from C# APIs can be null even when typed as non-nullable in F# signatures. Check at the boundary, or enable F# 9 nullable reference types (`<Nullable>enable</Nullable>`) so `string | null` is explicit and the compiler warns.
- **Frameworks that need setters or parameterless constructors** (EF Core entities, some serializers, options binding) need `[<CLIMutable>]` on records, or dedicated classes. Keep domain records separate from persistence models.
- **Serialization:** System.Text.Json (since .NET 6) handles F# records, options and collections but not discriminated unions; add FSharp.SystemTextJson (`JsonFSharpConverter`) or a hand-written encoder, and fix the union encoding format so the JSON contract stays stable.
- **Exposing F# to C#:** use classes, `Task`-returning methods and .NET collection interfaces in the public API; options, unions and curried functions are awkward from C#.
- **Web stacks:** ASP.NET Core directly (minimal APIs work from F#), or an F# layer such as Giraffe. The middleware order and authorization rules of `dotnet.md` apply unchanged.

## Testing

- **Runner:** xUnit is common (functions in modules marked `[<Fact>]`, named with double-backtick identifiers that read as sentences); Expecto is an F#-native alternative where tests are values (`testList`, `testCase`) run from a console entry point; NUnit also works. Follow the project.
- **Assertions:** Unquote (`test <@ total = 25m @>`) prints the evaluated expression on failure; FsUnit offers `should equal` style. Pick one per project.
- **Async tests:** return `task { ... }` from xUnit tests (or `async` in Expecto); never block on results inside the test.
- **Dependencies:** pass functions or a record of functions (`{ LoadOrder: OrderId -> Task<Order option>; SaveOrder: Order -> Task<unit> }`) and supply stubs in tests. Use a mocking library (NSubstitute, Foq) only for .NET interfaces you do not own.
- **Property-based tests with FsCheck** fit F# well: round-trips (serialize then deserialize), invariants (totals never negative, sorting is idempotent), and model-based tests of state machines. Write custom generators (`Arb`) that produce valid domain values through the smart constructors. FsCheck 3 reorganized its API into separate F# and C#-style namespaces, so check the installed major version before copying examples.
- **Integration tests:** `WebApplicationFactory` and Testcontainers as in `dotnet.md`; avoid the EF Core in-memory provider for anything relational.
- Test projects list their files in compile order too; shared fixtures and generators go above the tests that use them.

## Compiler messages that trip people up

| Message | Usual cause | Fix |
|---|---|---|
| FS0039 "The value, namespace, type or module 'X' is not defined" | File order in the `.fsproj`, a missing `open`, or a missing reference | Move the defining file above its users; add the `open` |
| FS0001 "This expression was expected to have type 'float' but here has type 'int'" | No implicit numeric widening in most positions | Convert explicitly (`float n`, `decimal n`) |
| FS0025 "Incomplete pattern matches" | A union case is not handled | Handle the case; avoid a wildcard in domain logic |
| FS0058 "Possible incorrect indentation" | Offside rule; a continuation line is indented less than its context | Re-indent, or let Fantomas format the file |
| FS0064 "This construct causes code to be less generic" | A type annotation or usage fixed a generic parameter | Usually harmless; remove the annotation if genericity was intended |

## Review checklist

- [ ] No incomplete pattern matches; no wildcard `_` case that would silently absorb a new union case in business logic.
- [ ] Domain types use wrappers or units for identifiers and quantities; invalid values are rejected at construction.
- [ ] Expected failures are `Result` values; exceptions are not caught and discarded.
- [ ] No blocking on `Task` or `Async` in server code; cancellation tokens are passed in `task` code.
- [ ] Nulls from .NET APIs are handled at the boundary; persistence and wire formats are separate from domain records.
- [ ] Union serialization has a fixed, tested format.

## Done when

- [ ] `dotnet build` with warnings as errors where configured, `dotnet test`, and `dotnet fantomas --check .` passed.
- [ ] New files are placed correctly in the compile order of both the main and test projects.
- [ ] Logic changes have unit tests, and invariants have property tests where they exist.
- [ ] Libraries used (FsToolkit.ErrorHandling, FSharp.SystemTextJson, FsCheck) are already project dependencies, or their addition was agreed.
