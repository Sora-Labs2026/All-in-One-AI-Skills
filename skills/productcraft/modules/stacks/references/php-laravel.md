# PHP, Laravel and Symfony

Read this before writing or changing PHP: Laravel or Symfony applications, packages, queues, tests. Security traps (loose comparison, file inclusion, unserialize, mass assignment, `APP_KEY`, Blade raw output) are in `../../code-security-review/references/language-pitfalls.md#php`. WordPress plugins, themes and WooCommerce are in `wordpress.md`.

## Orient first

- **PHP version:** `require.php` in `composer.json` is the supported range; `config.platform.php` tells Composer which version to resolve dependencies for. Write for the lowest supported version. In 2026, 8.4 and 8.5 are actively supported, 8.2 and 8.3 receive security fixes only (8.2 until the end of 2026), and 8.1 reached end of life at the end of 2025; check php.net's supported-versions page.
- **Framework:** `laravel/framework` (with `artisan` in the root) or `symfony/framework-bundle` (`bin/console`). Read the installed major version from `composer.lock`.
- **Composer:** `composer install` installs exactly what `composer.lock` says; `composer update` changes the lock and is a dependency change in its own right (`../../engineering-practices/references/dependencies.md`). Production installs use `--no-dev --optimize-autoloader`.
- **Tools present:** PHPStan (`phpstan.neon`, Larastan for Laravel) or Psalm; Laravel Pint (`pint.json`) or PHP-CS-Fixer; PHPUnit (`phpunit.xml`) or Pest (`tests/Pest.php`); Rector (`rector.php`) for automated upgrades.

```bash
composer validate --strict
vendor/bin/phpstan analyse --memory-limit=1G     # level from the config, not raised on the fly
vendor/bin/pint --test                            # or vendor/bin/php-cs-fixer fix --dry-run --diff
php artisan test                                  # or vendor/bin/pest / vendor/bin/phpunit
composer audit
```

## Modern PHP that matters

- `declare(strict_types=1);` at the top of every file the project writes. It applies to calls made *from* that file, so mixing strict and non-strict files changes behavior at call sites.
- Types on every parameter, return and property; `readonly` properties and classes for value objects and DTOs; constructor property promotion.
- Backed enums (`enum Status: string`) instead of class constants for closed sets; `match` (strict comparison, throws on no match) instead of `switch` (loose comparison).
- Named arguments make parameter names part of the public API: renaming a parameter in a library is a breaking change.
- `#[\Override]` (8.3) catches methods that no longer override anything. PHP 8.4 adds property hooks and asymmetric visibility, and deprecates implicitly nullable parameters (`function f(Foo $x = null)` must become `?Foo $x = null`).
- Money: integer minor units or a decimal library (brick/money, moneyphp); never floats.
- Dates: `DateTimeImmutable` or Carbon's immutable variant, stored in UTC.

## Laravel

**Versions.** Laravel releases one major a year (11 in March 2024, 12 in February 2025, 13 in 2026). From Laravel 11 the application skeleton is slimmer: middleware, exception handling and routing are configured in `bootstrap/app.php` instead of HTTP and console kernels. Follow the structure the project actually has.

**Eloquent.**
- Turn on strictness in local and test environments: `Model::shouldBeStrict(! app()->isProduction())` (prevents lazy loading, silently discarded attributes and access to missing attributes). Lazy loading in a loop is the usual N+1.
- Eager-load what a view or resource uses: `Post::with(['author', 'tags'])`, `withCount('comments')`. Constrain eager loads with closures when only some related rows are needed.
- Mass assignment: list `$fillable`; never `$guarded = []` with `$request->all()`. Pass `$request->validated()` or a DTO.
- Large datasets: `chunkById()` (not `chunk()`, which skips rows when the loop updates the filtered column), `lazyById()` or `cursor()`; `->toBase()` or `DB::table()` for reports that do not need models.
- Model events and observers run on `save()`, not on query-builder `update()`/`delete()` or `upsert`; be explicit about which one the code relies on.
- Casts (`casts()` method in Laravel 11+, `$casts` before) for enums, dates, JSON and encrypted attributes.
- Unique rules and `firstOrCreate` are not race-free; back them with a unique index and handle the duplicate-key exception.

**Validation and HTTP.**
- Form Requests for validation and authorization (`authorize()` with policies); controllers stay thin and call actions or services.
- API Resources for output, so internal columns never reach responses. One error shape across the API (`../../engineering-practices/references/api-contracts.md`).
- Authorize with policies and gates (`$this->authorize()`, `Gate::authorize()`, the `can` middleware); route middleware alone is not object-level authorization.

**Configuration.**
- Call `env()` only inside `config/*.php`. After `php artisan config:cache` (every production deploy should run it), `env()` returns null everywhere else. Application code reads `config('services.stripe.key')`.
- Deploy steps the project likely needs: `config:cache`, `route:cache`, `view:cache`, `event:cache`, `migrate --force` (the user runs migrations against shared databases).

**Queues.**
- Jobs are idempotent and safe to run twice: delivery is at least once, and retries rerun the whole `handle()`.
- Dispatch after commit: `->afterCommit()`, the `ShouldQueueAfterCommit` interface, or the connection's `after_commit` option, so workers never see rows that were rolled back.
- `SerializesModels` stores model IDs and refetches on execution; a deleted model fails the job (set `$deleteWhenMissingModels` if that is acceptable).
- Set `$tries` or `retryUntil()`, `$backoff`, and `$timeout` smaller than the queue connection's `retry_after`, otherwise a slow job runs twice in parallel. `ShouldBeUnique` and `WithoutOverlapping` middleware prevent duplicates where needed.
- Failed jobs go to the failed-jobs table; monitor it (Horizon for Redis queues). Workers must restart on deploy (`queue:restart`) to load new code.

**Long-lived workers.** Laravel Octane (on Swoole, RoadRunner or FrankenPHP), queue workers and other persistent PHP runtimes keep the application in memory between requests. Static properties, singletons holding request data and growing arrays leak across requests and users. Bind request-specific services as scoped, and test under the persistent runtime if the project uses one.

**Livewire.** Public component properties travel to the browser and back, so users can change them. Validate and authorize inside every action method, mark properties that must not change with `#[Locked]` (Livewire 3), and never put secrets or other users' data in public properties.

**Testing.**
- Feature tests through HTTP (`$this->postJson(...)->assertCreated()`), with `RefreshDatabase` (or `LazilyRefreshDatabase`) against the same database engine as production when queries matter.
- Factories with states for scenarios; `actingAs($user)` for authentication; fakes for side effects: `Queue::fake()`, `Bus::fake()`, `Mail::fake()`, `Event::fake()`, `Http::fake()` with `Http::preventStrayRequests()`.
- Assert authorization: another user's resource returns 403 or 404 per the project's convention.
- Pest and PHPUnit share the same engine; follow the style present. `php artisan test --parallel` if the suite supports it.

## Symfony

- Services are autowired from `config/services.yaml`; prefer constructor injection and small invokable services. Do not fetch services from the container at runtime.
- Doctrine ORM: entities mapped with attributes; repositories for queries; N+1 fixed with `JOIN` plus `addSelect` or batch fetching; migrations generated with `doctrine:migrations:diff` and read before running. Flush once per unit of work, not inside loops.
- Validation with constraints on DTOs (`#[MapRequestPayload]` in Symfony 6.3+), security with voters for object-level checks.
- Messenger for asynchronous work: idempotent handlers, retry strategy per transport, a failure transport that is monitored.
- `php bin/console lint:container`, `debug:router` and `cache:clear` help confirm wiring.

## Upgrades

- One framework major at a time, after reading the official upgrade guide; Rector rule sets automate many PHP and framework changes, and the output is reviewed like any other diff.
- PHP version upgrades: run the test suite and PHPStan under the new version in CI before switching production; deprecation notices in logs list what breaks next.
- The incremental approach and safety nets are in `legacy-modernization.md`.

## Done when

- [ ] Code runs on the lowest PHP version in `require.php`, with `strict_types` and full type declarations.
- [ ] PHPStan or Psalm at the configured level, the formatter check and the test suite pass.
- [ ] No N+1 in changed Eloquent or Doctrine code (strict mode or query counts in tests); no mass assignment of unvalidated input.
- [ ] Jobs are idempotent, dispatched after commit, with tries, backoff and a timeout below `retry_after`.
- [ ] `env()` appears only in config files; `composer audit` ran if dependencies changed, or is marked `NOT VERIFIED`.
