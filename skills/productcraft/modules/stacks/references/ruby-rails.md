# Ruby and Rails

Read this before writing or changing Ruby, especially Rails applications: models and queries, migrations, controllers, background jobs, Hotwire views, tests, upgrades. Security traps (strong parameters, SQL interpolation, `html_safe`, regex anchors, `constantize`, open redirects) are in `../../code-security-review/references/language-pitfalls.md#ruby-and-rails`.

## Orient first

- **Ruby version:** `.ruby-version`, the `ruby` line in `Gemfile`, and `RUBY VERSION` in `Gemfile.lock`. Use the version manager the team uses (rbenv, asdf, mise, chruby); never the system Ruby.
- **Rails version:** `rails` in `Gemfile.lock`, and `config.load_defaults` in `config/application.rb` (the framework defaults actually in effect, which can lag the installed version during upgrades). Rails 8.0 (November 2024) made the database-backed Solid Queue, Solid Cache and Solid Cable the defaults, added an authentication generator and uses Propshaft and import maps for assets; older apps commonly use Sidekiq, Redis caching and Sprockets or a JavaScript bundler.
- **Always `bundle exec` or the `bin/` binstubs** (`bin/rails`, `bin/rspec`) so the locked gem versions run.
- **Tests:** RSpec (`spec/`, `.rspec`) or Minitest (`test/`). Follow the one present.
- **Lint:** RuboCop (`.rubocop.yml`; Rails 7.2+ generates apps with the `rubocop-rails-omakase` style), or Standard. Brakeman for security scanning.

```bash
bin/rails db:prepare              # local and test databases only
bin/rails test                    # or bundle exec rspec
bundle exec rubocop <changed files>
bundle exec brakeman -q --no-pager
bin/rails zeitwerk:check          # autoloading names match file paths
```

## Ruby idioms that matter

- Constants and file names follow Zeitwerk's rules: `app/services/billing/charge_card.rb` defines `Billing::ChargeCard`. A mismatch fails at boot in production (eager loading) even if it worked in development.
- `# frozen_string_literal: true` if the project uses it; do not mutate strings you did not create.
- Raise specific error classes, rescue specific ones; `rescue => e` catches `StandardError`, which still hides bugs. Never `rescue Exception`.
- Keyword arguments for anything with more than two parameters or any boolean flag.
- Time: `Time.current`, `Time.zone.now` and `Date.current` respect the app's zone; `Time.now` and `Date.today` use the server's.
- Money: `BigDecimal` or integer cents (money-rails if present); never `Float`.

## Active Record

**Loading associations.**

| Method | Behavior | Use when |
|---|---|---|
| `includes(:author)` | Rails picks separate queries or a JOIN | Default for N+1 fixes |
| `preload(:author)` | Always separate queries | Large or polymorphic associations |
| `eager_load(:author)` | Always one `LEFT OUTER JOIN` | You filter or sort on the association |

- Catch N+1 early: `strict_loading` on the model, association or query (or `config.active_record.strict_loading_by_default` in development and test), or the Bullet or Prosopite gems if the project has them.
- Counts: `counter_cache: true` for counts shown often; `size` uses a loaded collection or the counter cache, `count` always queries, `length` loads everything.
- Batches: `find_each`/`in_batches` for large tables; never `Model.all.each`.
- `pluck(:id)` and `select(:id, :name)` when you do not need full objects.

**Integrity.**
- Validations are not guarantees under concurrency. Back `validates :email, uniqueness: true` with a unique index and rescue `ActiveRecord::RecordNotUnique`; back presence with `null: false`.
- Foreign keys in migrations (`references ... foreign_key: true`), check constraints for value ranges.
- `update_all`, `delete_all`, `insert_all` and `upsert_all` skip validations and callbacks; `update_column(s)` skips validations, callbacks and `updated_at`.
- Concurrent edits: optimistic locking (`lock_version` column) or `with_lock` for pessimistic row locks.

**Callbacks.** Keep them for the model's own data (normalizing, defaults). Side effects across models or systems (emails, jobs, API calls) belong in explicit service objects or controllers, where the flow is visible and testable. A job or email sent from `after_save` fires before commit and may see a rolled-back row: use `after_commit`, or rely on `enqueue_after_transaction_commit` (Rails 7.2+) where configured.

## Migrations

- Generate, read, and run locally; check `db/schema.rb` (or `db/structure.sql`) changes into the same commit.
- Production-safe steps follow `../../engineering-practices/references/data-and-migrations.md`: add columns nullable then backfill in batches outside the migration, add indexes with `algorithm: :concurrently` plus `disable_ddl_transaction!` on PostgreSQL, rename by adding and backfilling, and ignore a column (`self.ignored_columns += ["old"]`) for one deploy before dropping it.
- The `strong_migrations` gem enforces much of this; use it if the project has it.
- Never edit a migration that has run in a shared environment. Data fixes do not belong in schema migrations; use a one-off task the user runs.

## Controllers and views

- Strong parameters with explicit `permit` lists; scope lookups through the current user or account (`current_account.projects.find(params[:id])`) so authorization is part of the query. Use the project's authorization library (Pundit, Action Policy, CanCanCan) consistently.
- Keep controllers to parsing, authorization, calling a model or service, and rendering.
- **Hotwire** (Turbo and Stimulus): Turbo Frames replace one region per request, so match frame IDs between the page and the response; Turbo Streams broadcast changes; forms that fail validation must render with status 422 (`:unprocessable_entity`) for Turbo to display the errors. Stimulus controllers stay small and declarative.
- API-only apps: serializers or Jbuilder views with explicit attributes, never `render json: @model` with all columns.

## Background jobs

- Arguments are IDs and simple values; Active Job serializes records through GlobalID, and a deleted record raises on deserialization (`discard_on ActiveJob::DeserializationError` if acceptable).
- Jobs are idempotent: Sidekiq retries failed jobs many times (25 attempts over about three weeks by default), and every retry reruns `perform` from the top.
- Set `retry_on` with a bounded attempt count for transient errors and `discard_on` for permanent ones. Use `limits_concurrency` (Solid Queue) or a uniqueness mechanism where duplicates would hurt.
- Enqueue after commit (see Callbacks).
- Long jobs check for shutdown and work in resumable batches.

## Testing

- Request specs or integration tests over controller specs; system tests (Capybara) for the few flows that need a browser.
- Factories (FactoryBot) with the minimum valid attributes; traits for variations; `build` or `build_stubbed` when the database is not needed. Fixtures if the project uses Minitest fixtures.
- RSpec: `let` is lazy, `let!` runs before each example; avoid deep nesting of shared contexts that hide setup.
- Time with `travel_to`; external HTTP with WebMock or VCR (recorded cassettes reviewed for secrets).
- Jobs: `have_enqueued_job` or `assert_enqueued_with`, plus a direct `perform_now` test of the job itself.
- `bin/rails test --seed <n>` or `rspec --seed <n>` reproduces order-dependent failures.

## Performance

- Find the slow path with `rack-mini-profiler`, the log's query counts and timings, or APM traces; then fix N+1, missing indexes and over-fetching before caching.
- Caching: fragment and Russian-doll caching keyed by `cache_key_with_version`; low-level `Rails.cache.fetch` with explicit expiry.
- Puma: threads times processes times database pool must stay within the database's connection limit; `pool` in `database.yml` at least the thread count.
- Avoid class-level mutable state; Puma threads share it.

## Upgrades

- Upgrade one minor version at a time (7.0, 7.1, 7.2, 8.0), on a green suite with no deprecation warnings left from the previous step.
- Run `bin/rails app:update`, review each config diff, then flip `config.load_defaults` one version at a time, using the generated `new_framework_defaults_*.rb` file to enable defaults individually.
- Dual-booting (running the suite against current and next Rails from one branch) reduces the size of the final switch; the general approach is in `legacy-modernization.md`.

## Done when

- [ ] Tests, RuboCop on changed files and Brakeman pass through `bundle exec` or binstubs; `zeitwerk:check` passes for new files.
- [ ] Changed queries have no N+1 (strict loading or query assertions) and uniqueness or presence rules have database constraints.
- [ ] Side effects run after commit; jobs take IDs, are idempotent and have bounded retries.
- [ ] Migrations are safe for a live table and `schema.rb` or `structure.sql` is committed with them.
- [ ] Code uses APIs available in the installed Rails version and the active `load_defaults`.
