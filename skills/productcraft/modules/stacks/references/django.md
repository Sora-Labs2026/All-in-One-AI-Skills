# Django and Django REST Framework

Read this when the project has `manage.py` and a settings module: models, queries, migrations, views, DRF APIs, admin, background tasks. General Python practice is in `python.md`; Django security settings and traps are in `../../code-security-review/references/language-pitfalls.md#django`; migration safety in general is in `../../engineering-practices/references/data-and-migrations.md`.

## Orient first

- **Version:** read Django's version from the lock file. 4.2 and 5.2 are long-term-support releases; 6.0 (December 2025) needs Python 3.12 or later. Check the release notes of the installed version before using an API you remember from another one.
- **Settings:** find `DJANGO_SETTINGS_MODULE` (in `manage.py`, `wsgi.py`/`asgi.py`, `pytest.ini` or the environment) and whether settings are split per environment. Secrets and hosts come from the environment, never from committed values.
- **Serving:** WSGI (Gunicorn, uWSGI) or ASGI (Uvicorn, Daphne, Channels). Async views only pay off under ASGI.
- **Apps:** `INSTALLED_APPS` shows the project's own apps and the third-party ones in play (DRF, django-filter, Celery, django-storages, Channels). Put new code in the app that owns the concept, not in a new catch-all app.
- **User model:** check `AUTH_USER_MODEL`. Swapping to a custom user model after the first migration is a painful data migration; if a new project has none, create one before the first `migrate`, and always refer to it through `get_user_model()` or `settings.AUTH_USER_MODEL`.

Useful read-only commands:

```bash
python manage.py check                       # system checks
python manage.py check --deploy              # production settings audit (run with production settings)
python manage.py showmigrations              # applied and pending
python manage.py makemigrations --check --dry-run   # fails if models and migrations disagree (good CI gate)
python manage.py sqlmigrate <app> <number>   # the SQL a migration will run
```

## The ORM

**QuerySets are lazy.** Nothing hits the database until iteration, `len()`, slicing with a step, `list()`, `bool()` or a method such as `get()`, `first()`, `count()`, `exists()`. Build queries freely; evaluate once.

**N+1 is the default failure.** Every attribute that follows a relation in a loop is a query.

| Relation used in the loop | Load with |
|---|---|
| Foreign key or one-to-one, forward | `select_related("author")` (one JOIN) |
| Reverse foreign key, many-to-many | `prefetch_related("tags")` (one extra query per relation) |
| Filtered or ordered related set | `prefetch_related(Prefetch("comments", queryset=Comment.objects.filter(visible=True)))` |
| Only counts or sums | `annotate(n=Count("comments"))` instead of loading rows |

- Pin query counts in tests with `self.assertNumQueries(n)` (or `django_assert_num_queries` in pytest-django) on list endpoints, so a later change cannot reintroduce N+1 silently.
- Fetch less: `only()`/`defer()` for wide rows, `values()`/`values_list(flat=True)` when you do not need model instances, `exists()` instead of `count() > 0`, `iterator(chunk_size=...)` for large scans.
- **Atomic updates without races:** `Product.objects.filter(pk=pk).update(stock=F("stock") - 1)` instead of read, modify, `save()`. For read-then-decide logic, lock the row inside a transaction: `select_for_update()`. Work queues can use `select_for_update(skip_locked=True)`.
- **Invariants belong in the database:** `UniqueConstraint` (including conditional ones), `CheckConstraint`, `NOT NULL`, foreign keys. Model validation (`full_clean`) does not run on `save()`, and `get_or_create`/`update_or_create` only stay race-free when a unique constraint backs the lookup.
- **Bulk operations skip model logic:** `bulk_create`, `bulk_update`, `QuerySet.update()` and `QuerySet.delete()` do not call `save()`, do not send `pre_save`/`post_save` signals, and `update()` does not touch `auto_now` fields. Use them deliberately and set such fields yourself.
- Index what you filter, order and join on (`Meta.indexes`, `db_index=True`); confirm with `QuerySet.explain()` on a copy of realistic data, never against production.
- Connection reuse: set `CONN_MAX_AGE` (and `CONN_HEALTH_CHECKS`) or, on Django 5.1+ with psycopg 3, the built-in pool (`"OPTIONS": {"pool": True}`). Do not combine with an external pooler in transaction mode without reading its caveats.

## Transactions and side effects

- Wrap multi-step writes in `transaction.atomic()`. `ATOMIC_REQUESTS = True` wraps every view; check which the project uses before adding your own.
- **Side effects after commit:** sending email, enqueueing a task or calling a webhook inside a transaction can act on data that is later rolled back, or run before the row is visible to the worker. Use `transaction.on_commit(lambda: send_receipt.delay(order.pk))`.
- Signals run synchronously in the same transaction and hide control flow. Prefer explicit service functions for business logic; keep signals for decoupled, non-critical hooks.

## Migrations

- Generate with `makemigrations`, read the file and the SQL (`sqlmigrate`), commit it with the model change. Never edit a migration that has been applied anywhere shared; add a new one.
- **Data migrations** use `RunPython(forward, reverse)` with historical models from `apps.get_model("app", "Model")`, never imports of the current model class. Provide a reverse function or `RunPython.noop` with a written reason.
- Large tables: the expand, migrate, contract sequence and batched backfills from `../../engineering-practices/references/data-and-migrations.md` apply. On PostgreSQL, build indexes with `AddIndexConcurrently` from `django.contrib.postgres.operations` in a migration with `atomic = False`. Renames that must not lock or break running code use `SeparateDatabaseAndState` or a new column plus backfill.
- Run `../../engineering-practices/scripts/migration_check.py` on the SQL of new migrations (`sqlmigrate` output saved to a scratch file).
- Squash only when the team agrees; squashing rewrites what new environments run.

## Views, forms and templates

- Follow the project's style: function-based or class-based views. Validate input with forms or serializers, never by reading `request.POST` keys directly into models.
- Every view that returns user-owned data filters by the requesting user or tenant in the queryset, not after loading.
- Templates auto-escape; do not reach for `mark_safe` or `|safe` with user data.
- Static files: `collectstatic` at build time; WhiteNoise or a CDN in front; `ManifestStaticFilesStorage` (configured through `STORAGES` since 4.2) for cache-busting names.

## Django REST Framework

- **Serializers:** list `fields` explicitly; never `fields = "__all__"` or `exclude` on writable serializers, since new model columns become writable. Mark server-owned fields `read_only_fields`. Validate per field (`validate_<field>`) and across fields (`validate`). Use separate serializers for input and output when they differ.
- **Nested writes** are not automatic; write `create()`/`update()` explicitly, or accept IDs (`PrimaryKeyRelatedField` scoped with a `queryset` the user may see).
- **ViewSets:** override `get_queryset()` to scope by `request.user` and to add `select_related`/`prefetch_related`; detail, update and delete routes inherit the scoping. Use `perform_create` to set the owner from the request, not from the payload.
- **Defaults to set project-wide:** `DEFAULT_PERMISSION_CLASSES` (DRF's default is `AllowAny`), `DEFAULT_AUTHENTICATION_CLASSES`, `DEFAULT_PAGINATION_CLASS` with `PAGE_SIZE` (and `CursorPagination` for large or busy tables), throttling for public endpoints, `DEFAULT_SCHEMA_CLASS` if the project generates OpenAPI with drf-spectacular.
- **Errors:** one exception handler (`EXCEPTION_HANDLER`) that maps domain errors to the API's single error shape (`../../engineering-practices/references/api-contracts.md`).
- Filtering and ordering with `django-filter` and `OrderingFilter`; allowlist `ordering_fields` so clients cannot sort by hidden columns.

## Async

- Async views work under ASGI. The ORM has async methods (`aget`, `acreate`, `afilter().aexists()`, `async for` over a queryset) since 4.1, but as of Django 5.x they run the database work in a thread, and transactions are not supported in async code: put transactional logic in a sync function and call it with `sync_to_async`.
- Never call sync ORM methods directly in an async view (`SynchronousOnlyOperation`), and never block the loop with sync HTTP clients.
- Choose async for long-polling, streaming and many concurrent outbound calls; ordinary CRUD is simpler and as fast in sync views.

## Background work

- Use the queue the project has (Celery, RQ, Dramatiq, Huey). Django 6.0 adds a tasks API, but its bundled backends are for development and tests; production still needs a worker backend, so do not swap an existing queue for it.
- Task arguments are primary keys and plain values, never model instances or request objects. Re-read state in the task.
- Tasks are idempotent: a retry or a duplicate delivery must not charge, email or create twice (an idempotency key, a unique constraint, or a status check under `select_for_update`).
- Set time limits and bounded retries with backoff. With `acks_late`, a task that crashes is redelivered, which is only safe when the task is idempotent.
- Enqueue after commit (`transaction.on_commit`).

## Caching and admin

- Low-level cache (`cache.get_or_set`) with explicit keys that include a version or the object's `updated_at`; per-view caching only for responses that are identical for every user who can see them.
- The admin is an internal tool. Restrict it to staff, keep it off the public path or behind extra protection, and set `list_select_related`, `raw_id_fields` or `autocomplete_fields` so its pages do not run thousands of queries.

## Testing

- `TestCase` wraps each test in a transaction (fast, isolated); `TransactionTestCase` is needed only for code that depends on commits (`on_commit` callbacks, or use `self.captureOnCommitCallbacks(execute=True)` in `TestCase`).
- With pytest-django: `@pytest.mark.django_db`, the `client`/`admin_client` fixtures, `settings` for overrides. Build data with factory_boy or model-bakery if the project uses them; keep factories minimal and set only what the test is about.
- DRF: `APIClient` with `force_authenticate`; assert status, body shape and the query count.
- Test permissions explicitly: another user's object returns 404 (or 403 per the project's convention), anonymous gets 401.

## Done when

- [ ] `python manage.py check` passes, and `makemigrations --check --dry-run` shows no missing migrations.
- [ ] New migrations were read, their SQL reviewed, and the migration checker run on that SQL.
- [ ] List and detail endpoints touched by the change have a pinned query count and scoped querysets.
- [ ] Side effects run after commit; background tasks take IDs and are idempotent.
- [ ] Tests ran with the project's runner (`pytest` or `python manage.py test`), plus its linter and type checker.
