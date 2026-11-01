# Laravel security, testing and verification

Read this when you harden a Laravel application, add authorization or authentication, accept uploads, write PHPUnit or Pest tests, or verify a Laravel change before merge or deploy. Everyday Laravel and PHP practice (versions, Eloquent, queues, configuration caching, Octane, Livewire) is in `php-laravel.md`; review-level PHP and Laravel traps are in `../../code-security-review/references/language-pitfalls.md#php`; the general controls are in `../../launchguard/references/security-baseline.md`.

Laravel 11 (March 2024) moved middleware, exception and routing setup into `bootstrap/app.php`; older applications use HTTP and console kernels and an `AuthServiceProvider`. Follow the structure the project has.

## Production configuration

| Setting | Production value | Why |
|---|---|---|
| `APP_DEBUG` | `false` | Debug pages show environment variables, queries and stack traces |
| `APP_KEY` | Random, from the secret store, never committed | It signs and encrypts cookies, sessions, signed URLs and encrypted casts. A leak lets attackers forge them |
| `APP_PREVIOUS_KEYS` (11+) | Old keys during a rotation | Lets data encrypted with the previous key still decrypt while new data uses the new key |
| `SESSION_SECURE_COOKIE` | `true` | Session cookie only over HTTPS |
| `SESSION_SAME_SITE` | `lax` (or `strict`) | Reduces cross-site request forgery |
| Trusted proxies | The load balancer's address ranges, not `*` | With `*`, any client can spoof `X-Forwarded-For` and `X-Forwarded-Proto`, which breaks rate limits, logs, HTTPS detection and signed URLs |
| `LOG_LEVEL` | `info` or higher | Debug logs tend to capture request bodies |

- Rotate `APP_KEY` with the user's go-ahead: it logs everyone out and invalidates outstanding signed URLs unless the previous key is kept in `APP_PREVIOUS_KEYS`.
- Run `php artisan config:cache` in the deploy and in CI. It catches `env()` calls outside `config/*.php`, which return `null` once the configuration is cached.
- Keep the web server's document root at `public/`; `.env`, `storage/` and `vendor/` must never be reachable over HTTP.

## Authentication

- Use the starter kit or library the project already has (Breeze, Jetstream, Fortify, Sanctum, Passport). Do not hand-roll login, password reset or remember-me.
- Regenerate the session after login (`$request->session()->regenerate()`) and invalidate it on logout (`invalidate()` plus `regenerateToken()`); the starter kits do this, custom flows must too.
- Throttle login, registration, password reset and verification by account and by IP with a named limiter (`RateLimiter::for('login', ...)` and `throttle:login`). Account-recovery design belongs to `../../credential-shield/GUIDE.md`.
- Passwords: the `hashed` cast (Laravel 10+) or `Hash::make`; never store or log plain passwords. Validate with `Password::min(12)->uncompromised()`. Length plus a breach check follows current guidance better than composition rules (upper, lower, symbol). `uncompromised()` calls an external breach-range API, so fake HTTP in tests.
- **Sanctum API tokens:** create them with the narrowest abilities (`createToken('ci', ['reports:read'])`), check them on routes (`abilities:` or `ability:` middleware, or `tokenCan()`), and set `sanctum.expiration`; the default is `null`, which means tokens never expire. Prune expired tokens on a schedule.
- **Sanctum SPA authentication** uses session cookies: the SPA's domain must be listed as stateful, it must fetch `/sanctum/csrf-cookie` first, and CSRF protection stays on. Do not exclude `api/*` from CSRF for a cookie-authenticated SPA.

## Authorization

- Put object-level rules in policies, one per model, and call them on every action: `Gate::authorize('update', $post)` or `$this->authorize(...)`, the `can:update,post` middleware, or `authorize()` in a Form Request. Route middleware such as `auth` says who is signed in, not what they may touch.
- Scope queries by owner or tenant as well (`$request->user()->projects()->findOrFail($id)`), so a missed policy call still cannot return another tenant's row.
- **Nested routes:** `Route::scopeBindings()` (or a custom key such as `{post:slug}`) makes `{project}` in `/accounts/{account}/projects/{project}` resolve only within `{account}`. It does not check that the user may see `{account}`; authorize the parent too.
- `Gate::before` for super-admins is convenient and easy to over-grant. Return `null` (not `false`) for everyone else so normal checks still run, and log uses of the override if the business needs an audit trail.
- Policies return `Response::denyAsNotFound()` where the existence of a record must stay hidden.

## Mass assignment and input

- List writable attributes in `$fillable`; never `$guarded = []`. Pass `$request->validated()` or `$request->safe()->only([...])` to `create` and `update`, never `$request->all()` or `$request->input()`.
- Turn on `Model::shouldBeStrict(! app()->isProduction())`. Among other things it throws when code fills an attribute that is not fillable, instead of silently dropping it.
- Never put `role`, `is_admin`, `tenant_id`, `user_id` or verification flags in `$fillable` for user-facing forms; set them explicitly from the authenticated context.
- Validate arrays and nested input explicitly (`'tags' => ['array', 'max:20']`, `'tags.*' => ['integer', 'exists:tags,id']`). A bare `'meta' => 'array'` returns the whole array, every nested key included, from `validated()`; give nested keys their own rules or restrict them with `array:allowed,keys`.
- Raw expressions (`DB::raw`, `whereRaw`, `orderByRaw`, `selectRaw`) take bindings: `whereRaw('lower(email) = ?', [$email])`. Sort and filter columns from the request go through an allowlist.

## Output, URLs and files

- Blade `{{ }}` escapes; `{!! !!}` does not and needs content you control or that went through an allowlist sanitizer (HTML Purifier). For data in JavaScript use `@js($value)` or `Js::from()`, not `{{ json_encode(...) }}`.
- Markdown from users: `Str::markdown($text, ['html_input' => 'strip', 'allow_unsafe_links' => false])`.
- Redirects to a URL from input (`?redirect=`) only to relative paths or an allowlist; `redirect()->intended()` already restricts to the session's intended URL.
- **Uploads:** validate type and size (`File::types(['pdf', 'png'])->max('10mb')` or `mimes:` plus `max:`; newer releases also have an `extensions:` rule that pins the client extension), store under a generated name (`store()` and `hashName()`), and keep private files on a private disk. Serve them through a controller that authorizes the model that owns the file, or a short-lived `Storage::temporaryUrl()` created after that check; never accept a storage path from the request.
- **Signed URLs** (`URL::temporarySignedRoute()` with the `signed` middleware) for unsubscribe links, downloads and invitations. Behind a proxy they validate only when trusted proxies are configured correctly.
- Encrypt sensitive columns with the `encrypted` or `encrypted:array` casts, and queued jobs that carry sensitive data with `ShouldBeEncrypted`. Hide secrets from serialization with `$hidden`, and return API Resources rather than models.
- Excluding routes from CSRF is for signed webhooks only; verify the provider's signature on the raw body before doing anything else.
- CORS (`config/cors.php`): list exact origins; `supports_credentials` only with explicit origins, never with `*`.

## Testing

### Test environment

- Configure tests in `phpunit.xml` and `.env.testing`: `APP_ENV=testing`, a low `BCRYPT_ROUNDS` for speed, `array` mail, cache and session drivers, and the queue connection the tests expect.
- An in-memory SQLite database is fast but differs from MySQL and PostgreSQL in types, JSON functions, locking, constraint enforcement and case sensitivity. When queries matter, test against the production engine in a container.
- `RefreshDatabase` migrates once and wraps each test in a transaction; `LazilyRefreshDatabase` migrates only if a test touches the database; `DatabaseTruncation` is for browser tests where a transaction cannot span processes. Code that relies on commits (after-commit dispatch, `DB::afterCommit`) needs care inside transaction-wrapped tests; assert on the dispatched jobs rather than on post-commit side effects.

### What every change gets

- **Authorization matrix** for each new route or action: guest (401 for JSON, redirect for web), another user or tenant (403, or 404 if existence is hidden), owner or permitted role (2xx). Test the policy directly too, for the edge cases.
- **Validation:** one test with an empty payload (`assertInvalid([...])` or `assertJsonValidationErrors([...])`), and boundary values for each important rule.
- **Response shape:** `assertJsonPath`, `assertJsonStructure`, and a check that hidden fields are absent.
- **Side effects through fakes:** `Queue::fake()` or `Bus::fake()`, `Mail::fake()`, `Notification::fake()`, `Storage::fake('s3')`, and `Http::fake()` together with `Http::preventStrayRequests()` so an unmocked outbound call fails the test.
- `Event::fake()` with no arguments also silences model event listeners and observers, which can break factories that rely on them (UUIDs or slugs set in `creating`). Pass the event classes to fake: `Event::fake([OrderShipped::class])`.
- Time: `$this->freezeTime()` or `$this->travelTo(...)`; never `sleep()`.

### Factories

- Keep `definition()` minimal and valid; express scenarios as states (`->suspended()`), relationships with `for()` and `has()`, and variations with `sequence()`. `recycle($team)` reuses one parent across a graph instead of creating a new one per child.
- Hash a known password once in the factory (`static::$password ??= Hash::make('password')`) to keep suites fast.

### Pest

- Follow the style present: Pest and PHPUnit run on the same engine and can coexist, but new tests match their neighbors.
- Datasets (`->with([...])`) replace copy-pasted tests for tables of inputs.
- Architecture tests (Pest 3, 2024) state rules the code must keep: `arch()->expect('App\Models')->not->toUse('Illuminate\Http\Request')`, `arch()->preset()->security()`, and a rule against `dd`, `dump` and `ray` in `App`. Run them in CI like other tests.
- Pest 3 added mutation testing (`pest --mutate`) and Pest 4 (2025) browser testing; adopt either only with the user's agreement, scoped to the code under change.

### Running the suite

- `php artisan test --parallel` creates one database per process; tests that share files or fixed ports must be made independent first.
- Coverage needs Xdebug or PCOV (`XDEBUG_MODE=coverage`). Use it to find untested branches; thresholds belong in CI only if the team set them.

## Verification before merge or deploy

Run what the project's CI runs; when it defines nothing, this order catches most problems cheaply:

```bash
composer validate --strict
vendor/bin/pint --test                    # or php-cs-fixer --dry-run
vendor/bin/phpstan analyse                # Larastan level from the config
php artisan test                          # or vendor/bin/pest
composer audit
php artisan migrate --pretend             # SQL of pending migrations, against a non-production database
php artisan config:cache && php artisan route:cache && php artisan view:cache && php artisan optimize:clear
```

- Read every new migration's `--pretend` output; destructive or locking statements on large tables follow `../../engineering-practices/references/data-and-migrations.md`. Running migrations against shared databases is the user's step.
- Check queues and the scheduler on staging only: `php artisan schedule:list`, `php artisan queue:failed`, `php artisan queue:monitor <queue> --max=<n>`.
- Report what ran and what failed or could not run, as `NOT VERIFIED` with the reason.

## Choosing a package

Before adding a Composer package: check its supported Laravel and PHP versions against `composer.json` (`composer why-not vendor/package <version>` explains conflicts), the release history and open security issues, whether Packagist marks it abandoned, its license, and how much it registers globally (service providers, middleware, routes, migrations). Prefer first-party or widely used packages, add it with the user's agreement, and run `composer audit` afterwards.

## Done when

- [ ] `APP_DEBUG` is off, secrets come from the environment, trusted proxies are explicit, and `config:cache` succeeds in CI.
- [ ] Every new action authorizes the specific record through a policy or gate, nested bindings are scoped, and the parent is authorized too.
- [ ] Writes use validated data only; `$fillable` excludes privilege and ownership columns; strict mode is on outside production.
- [ ] Uploads are validated, stored privately under generated names and served after authorization.
- [ ] Tests cover guest, other-user and owner cases, validation failures and side effects through fakes, with stray HTTP requests blocked.
- [ ] Pint, PHPStan, tests, `composer audit` and `migrate --pretend` ran, with results reported.
