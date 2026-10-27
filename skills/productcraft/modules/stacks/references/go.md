# Go

Read this before writing or changing Go: services, workers, libraries, command-line tools. Security traps (templates, SQL, timeouts, paths, integer conversion) are in `../../code-security-review/references/language-pitfalls.md#go`; fuzzing is in `../../engineering-practices/references/fuzzing.md`; CLI design is in `cli-tools.md`.

## Orient first

- **`go.mod`:** the `go` line is the minimum language version and changes semantics (see the table). A `toolchain` line asks for a newer toolchain; with the default `GOTOOLCHAIN=auto` the `go` command downloads it, which needs network access. In an offline sandbox, use the installed toolchain and report the mismatch.
- `go.work` means a multi-module workspace; run commands from the module you change, and do not commit a `go.work` the project does not already track.
- A `vendor/` directory means builds use vendored code (`-mod=vendor` is automatic when `vendor/modules.txt` matches). After changing dependencies, run `go mod vendor` as the project does.
- Tools: a `tool` block in `go.mod` (Go 1.24+) or a `tools.go` file pins generator and linter versions; run them with `go tool <name>` or `go run <module>@<version>` as the project does. golangci-lint v2 (2025) uses a new config format (`version: "2"` in `.golangci.yml`); do not rewrite the config to another version.

| Language change | From |
|---|---|
| Generics | 1.18 |
| `slices`, `maps`, `cmp` packages; `min`, `max`, `clear` builtins; `log/slog`; `toolchain` directive | 1.21 |
| Each loop iteration gets a fresh variable; `for i := range 10`; method and wildcard patterns in `http.ServeMux` (`"GET /items/{id}"`, `r.PathValue("id")`) | 1.22 |
| Range over function iterators (`iter.Seq`) | 1.23 |
| `tool` directive; `os.Root` for confined file access; `testing.B.Loop`; `omitzero` JSON tag | 1.24 |
| `sync.WaitGroup.Go`; `testing/synctest` for concurrent code with fake time; GOMAXPROCS that respects container CPU limits | 1.25 (August 2025) |

## Commands

```bash
gofmt -l .                  # must print nothing (or goimports, if the project uses it)
go vet ./...
go build ./...
go test -race -count=1 ./...   # -count=1 bypasses the test cache
golangci-lint run           # if configured; otherwise staticcheck ./... if installed
govulncheck ./...           # reports vulnerabilities in functions you actually call
go mod tidy && git diff --exit-code go.mod go.sum   # dependency files consistent
```

## Layout and naming

- `cmd/<binary>/main.go` for each executable, kept small: parse configuration, wire dependencies, run. Logic lives in packages.
- `internal/` for packages no other module may import. Add a top-level `pkg/` only if the project already uses one.
- Package names are short, lowercase, singular and say what the package provides (`invoice`, `postgres`, `httpapi`). Avoid `util`, `common`, `helpers`. Names do not stutter: `invoice.Service`, not `invoice.InvoiceService`.
- Organize by domain, not by layer, unless the project already layers. Avoid import cycles by moving shared types down, not by adding interfaces everywhere.

## Errors

- Return `error` as the last result and check it at once. Add context while returning: `fmt.Errorf("load invoice %s: %w", id, err)`. Use `%w` once per wrap so `errors.Is` and `errors.As` see through it.
- Sentinel errors (`var ErrNotFound = errors.New("not found")`) for conditions callers test; typed errors (`*ValidationError`) when callers need fields. Compare with `errors.Is`/`errors.As`, never by string.
- Handle or return, not both: logging and then returning the same error produces duplicate log lines. Log once at the boundary (handler, job runner).
- `panic` only for programmer errors and impossible states; recover only at goroutine and request boundaries, converting to an error and a log line.
- `errors.Join` (1.20) combines independent failures, for example from cleanup.

## Context

- `ctx context.Context` is the first parameter of every function that does I/O or may block. Pass it down; do not store it in structs.
- Derive deadlines with `context.WithTimeout(ctx, d)` and always `defer cancel()`.
- Context values carry request-scoped data only (request ID, authenticated principal), with unexported key types. Never optional parameters.
- Stop work when `ctx.Done()` closes; return `ctx.Err()` (or `context.Cause(ctx)`).

## Concurrency

- **Every goroutine has an owner and an exit.** Before writing `go`, know who waits for it and what makes it stop. Leaked goroutines are the Go version of a memory leak.
- Prefer `golang.org/x/sync/errgroup` for a group of tasks that can fail: the first error cancels the shared context and `Wait` returns it. `SetLimit(n)` bounds the fan-out.

```go
g, ctx := errgroup.WithContext(ctx)
g.SetLimit(8)
for _, id := range ids {
	g.Go(func() error { return sync(ctx, id) })   // Go 1.22+: id is per-iteration
}
if err := g.Wait(); err != nil {
	return fmt.Errorf("sync batch: %w", err)
}
```

- Channels: the sender closes, never the receiver; a nil channel blocks forever (useful in `select` to disable a case); every blocking send or receive sits in a `select` with `<-ctx.Done()`.
- Shared state: a `sync.Mutex` next to the fields it guards, never copied (`go vet` checks); `sync/atomic` types (`atomic.Int64`) for counters. Maps are not safe for concurrent writes.
- Before Go 1.22 semantics (a `go` line below 1.22), loop variables are shared across iterations; copy them (`id := id`) before capturing.
- Test concurrent code with `-race`; check for leaks with `go.uber.org/goleak` if available, or `testing/synctest` on 1.25+.

## Interfaces and generics

- Define interfaces where they are used, small (one to three methods), and accept them as parameters; return concrete types. A constructor that returns an interface hides useful methods and makes mocks mandatory.
- A nil pointer stored in an interface is not a nil interface: `var p *MyErr = nil; var err error = p; err != nil` is true. Return a literal `nil` for "no error".
- Generics fit containers and algorithms over many types (`slices.SortFunc`, a typed cache). Do not genericize code with one caller; an interface or a concrete type reads better.

## HTTP services

- Construct `http.Server` with `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout` and `IdleTimeout`, limit bodies with `http.MaxBytesReader`, and give every `http.Client` a `Timeout`. One client per process, reused; always `defer resp.Body.Close()` and drain the body before closing if you want connection reuse.
- Graceful shutdown:

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
go func() { _ = srv.ListenAndServe() }()   // returns http.ErrServerClosed on Shutdown
<-ctx.Done()
shutdownCtx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
defer cancel()
_ = srv.Shutdown(shutdownCtx)              // stops accepting, waits for in-flight requests
```

- Structured logs with `log/slog`, a request ID in every line through a handler or middleware.
- `net/http/pprof` only on an internal listener, never on the public mux.

## Databases

- `database/sql` or `pgx` hold a pool: set `SetMaxOpenConns`, `SetMaxIdleConns` and `SetConnMaxLifetime` to fit the database's limits. Use the `...Context` methods.
- Always `defer rows.Close()` and check `rows.Err()` after the loop; an unchecked `Scan` error turns into zero values.
- Generated query code (sqlc) or a query builder are both common; follow the project. Placeholders only, never `fmt.Sprintf` into SQL.

## Testing

- Table-driven tests with `t.Run(tc.name, ...)`; `t.Helper()` in helpers; `t.Cleanup` and `t.TempDir()` for teardown; `t.Setenv` for environment variables (not allowed with `t.Parallel`).
- Golden files in `testdata/`, regenerated behind an `-update` flag and reviewed in the diff.
- `httptest.NewRecorder` for handlers, `httptest.NewServer` for clients.
- Fakes over mocks: a small in-memory implementation of the interface the code consumes. Containers (Testcontainers for Go) for real database behavior.
- `go test -shuffle=on` exposes order dependence; `-run` and `-count` narrow and repeat.
- Benchmarks: `for b.Loop() { ... }` on 1.24+, otherwise `for i := 0; i < b.N; i++`; compare runs with `benchstat` over several `-count` repetitions, never a single run.
- `Example` functions double as documentation and tests when they have an `// Output:` comment.

## Performance

- Profile first: `go test -cpuprofile cpu.out -bench .` or a pprof endpoint, then `go tool pprof -http=:0 cpu.out`. Use `-memprofile` and the `alloc_space` view for allocation pressure.
- Common wins: preallocate slices and maps when the size is known (`make([]T, 0, n)`), `strings.Builder` for concatenation, avoid converting between `[]byte` and `string` in hot loops, reuse buffers. Check escapes with `go build -gcflags=-m`.
- `sync.Pool` helps only for short-lived, frequently allocated objects under measured GC pressure; it adds complexity.

## Building and shipping

- Reproducible binaries: `CGO_ENABLED=0` where cgo is not needed, `-trimpath`, version injected with `-ldflags "-X main.version=..."`. Cross-compile with `GOOS` and `GOARCH`.
- Containers: multi-stage build to a minimal or distroless image running as non-root.

## Done when

- [ ] `gofmt`, `go vet`, the configured linter and `go test -race ./...` pass.
- [ ] Code uses only features of the `go` version in `go.mod`.
- [ ] Every new goroutine has an owner, a cancellation path and a test that would catch a leak or race.
- [ ] Every outbound call and server has timeouts; errors carry context and are logged once.
- [ ] `go mod tidy` leaves no diff; `govulncheck` ran if dependencies changed, or is marked `NOT VERIFIED`.
