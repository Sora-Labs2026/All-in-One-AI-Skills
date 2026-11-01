# Django: Celery, security hardening and failure fixes

Read this when a Django project adds or debugs Celery tasks and schedules, hardens settings for production, or is blocked by a startup, migration or static-files error. ORM, transactions, migrations, DRF and the general rules for background work (IDs as arguments, idempotency, enqueue after commit) are in `django.md`; review-level Django traps in `../../code-security-review/references/language-pitfalls.md#django`; Python testing in `python-testing.md`.

## Celery

### Configuration that prevents most incidents

Read the Celery version (5.x in 2026) and the broker (Redis or RabbitMQ) before changing anything. With `app.config_from_object("django.conf:settings", namespace="CELERY")`, settings carry the `CELERY_` prefix.

| Setting | Recommended | Why |
|---|---|---|
| `CELERY_TASK_SERIALIZER`, `CELERY_ACCEPT_CONTENT` | `"json"`, `["json"]` | Pickle executes code when a message is loaded; never accept it |
| `CELERY_TASK_ACKS_LATE` | `True` for idempotent tasks | The message is acknowledged after the task finishes, so a crash redelivers it instead of losing it |
| `CELERY_TASK_REJECT_ON_WORKER_LOST` | `True` together with late acks | Redelivers when the worker process is killed; a task that kills its worker (memory) then loops, so cap memory and watch for it |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` for long tasks | Stops one worker from reserving many long tasks while others sit idle |
| `CELERY_TASK_SOFT_TIME_LIMIT`, `CELERY_TASK_TIME_LIMIT` | Soft below hard, both set | The soft limit raises `SoftTimeLimitExceeded` so the task can clean up; the hard limit kills it |
| `CELERY_TASK_IGNORE_RESULT` | `True` unless results are read | Result backends fill up; set `CELERY_RESULT_EXPIRES` when results are kept |
| Redis `visibility_timeout` (in `CELERY_BROKER_TRANSPORT_OPTIONS`) | Longer than the longest task and the longest `countdown` or `eta` | With Redis, an unacknowledged message is redelivered after this timeout, so long or delayed tasks run twice |

- Name tasks explicitly (`@shared_task(name="billing.send_invoice")`). Renaming or moving a task while messages are queued leaves them as unregistered tasks; deploy the new name alongside the old one, drain, then remove.
- Keep task signatures backward compatible across a deploy: workers on the new code receive messages enqueued by the old code, and the other way round during a rolling deploy. Add parameters with defaults; never reorder them.
- Route slow and fast work to separate queues (`-Q default`, `-Q reports`) with separate worker pools, so a backlog of exports does not delay password-reset emails.

### Task design

```python
from celery import shared_task
from django.db import transaction

@shared_task(
    bind=True,
    name="billing.capture_payment",
    autoretry_for=(PaymentGatewayUnavailable,),   # transient errors only
    retry_backoff=True, retry_backoff_max=600, retry_jitter=True, max_retries=5,
    acks_late=True,
)
def capture_payment(self, order_id: int) -> None:
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status != Order.Status.AUTHORIZED:
            return                                    # already captured or cancelled: nothing to do
        order.status = Order.Status.CAPTURING
        order.save(update_fields=["status"])
    # Outside the transaction: never hold a row lock across a network call.
    result = gateway.capture(order.payment_id, idempotency_key=f"capture-{order_id}")
    Order.objects.filter(pk=order_id, status=Order.Status.CAPTURING).update(
        status=Order.Status.CAPTURED, captured_at=result.captured_at,
    )
```

- Arguments are IDs and plain values; the task re-reads current state.
- Make the effect idempotent: a status guard under `select_for_update` (which only works inside `transaction.atomic()`), a unique constraint, or an idempotency key the external provider honors. Retrying a charge or an email without one duplicates it.
- Retry only transient failures, with backoff, jitter and a cap; let validation and permission errors fail permanently (`../../engineering-practices/references/resilience.md`).
- Enqueue after commit: `transaction.on_commit(lambda: send_receipt.delay(order.pk))`, or `send_receipt.delay_on_commit(order.pk)` where the project's Celery (5.4 and later) and task class provide it.
- Split large jobs into chunks of a bounded size, each its own task, rather than one task that runs for an hour.
- Canvas: a `chord` needs a result backend, and one failed member blocks the callback; for large fan-outs, a parent record that tracks completed chunks is easier to monitor and resume.
- After the last retry, record the failure somewhere a person sees it (a failed-jobs table, an alert) rather than catching every exception and returning.

### Periodic tasks

- Run exactly one beat scheduler. Two beat processes enqueue every periodic task twice. In containers, give beat its own single-replica deployment.
- With `django-celery-beat`'s database scheduler, schedules live in the database and are editable in the admin; restrict who can edit them.
- Guard periodic tasks that may outlast their interval with a lock (a cache lock with a timeout, or a database advisory lock), so runs do not overlap.
- Set `CELERY_TIMEZONE` (or keep UTC) deliberately; daylight-saving changes skip or repeat local-time schedules.

### Operating and observing

- Monitor queue length per queue, task failure rate and task duration. `celery -A <proj> inspect active` and `inspect reserved` show what workers hold.
- Flower and similar dashboards show task arguments and can revoke tasks or shut workers down. Put them behind authentication and keep them off the public internet.
- Restart workers on deploy so they load the new code, with a warm shutdown that lets running tasks finish (`SIGTERM`, within the time limit).

### Testing tasks

- Call the task directly (`capture_payment(order.pk)` runs it in the test process) for unit tests of its logic, with the external client faked.
- `CELERY_TASK_ALWAYS_EAGER` runs tasks inline. It hides serialization errors, routing, retries and transaction timing, and Celery's own documentation calls it unsuitable for unit tests. Prefer direct calls plus one integration test with a real worker (`celery.contrib.pytest` fixtures or `pytest-celery` with a broker in a container).
- Assert enqueueing after commit with `TestCase.captureOnCommitCallbacks(execute=True)` (or the `django_capture_on_commit_callbacks` fixture in pytest-django).
- Django 6.0's tasks framework has development and test backends only; production work still needs a real worker (`django.md`).

## Security hardening

Run `python manage.py check --deploy` with production settings and resolve every warning or record why it does not apply.

| Setting | Production value | Note |
|---|---|---|
| `DEBUG` | `False` | Debug pages leak settings and code |
| `SECRET_KEY` | From the environment or a secret store | Rotate with `SECRET_KEY_FALLBACKS` (4.1+) so existing sessions and signed values survive the change |
| `ALLOWED_HOSTS` | Exact hostnames | `["*"]` enables host-header attacks on password-reset links |
| `CSRF_TRUSTED_ORIGINS` | Full origins with scheme (`https://app.example.com`) | Required for cross-origin HTTPS posts; the scheme became mandatory in 4.0 |
| `SECURE_PROXY_SSL_HEADER` | `("HTTP_X_FORWARDED_PROTO", "https")` only behind a proxy that sets or strips that header | Otherwise clients can claim HTTPS |
| `SECURE_SSL_REDIRECT` | `True`, unless the proxy already redirects | |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | `True` | |
| `SESSION_COOKIE_HTTPONLY` | `True` (default) | `CSRF_COOKIE_HTTPONLY` stays `False` if JavaScript reads the token from the cookie |
| `SECURE_HSTS_SECONDS` | Start small (an hour), raise to a year after verifying every subdomain serves HTTPS | Preload and long values are hard to undo; ask before `SECURE_HSTS_PRELOAD` and `INCLUDE_SUBDOMAINS` |
| `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY` | Defaults (`True`, `"DENY"`, `"same-origin"`, `"same-origin"`) | Do not weaken them without a reason |
| Content Security Policy | Django 6.0: `ContentSecurityPolicyMiddleware` with `SECURE_CSP` (start with `SECURE_CSP_REPORT_ONLY`); earlier versions: the `django-csp` package | Use nonces for inline scripts instead of `'unsafe-inline'` |

- Do not add the deprecated `X-XSS-Protection` header; modern browsers ignore it.
- **Passwords:** keep `AUTH_PASSWORD_VALIDATORS` on (minimum length, common-password and similarity checks). To prefer Argon2, install `argon2-cffi` (`django[argon2]`) and put `Argon2PasswordHasher` first while keeping the PBKDF2 hashers listed, so existing hashes upgrade on next login.
- **Default deny:** Django 5.1 added `LoginRequiredMiddleware`; views that must be public opt out with `@login_not_required`. In DRF, set `DEFAULT_PERMISSION_CLASSES` (the default is `AllowAny`).
- **Brute force:** throttle login and password reset by account and IP (a maintained package such as django-axes, or rate limiting at the proxy). DRF throttling is for fair use; its documentation says not to rely on it against brute force.
- **Admin:** restrict to staff accounts with two-factor authentication, keep it off the public network or behind extra controls where possible; moving the URL only reduces noise.
- **Uploads:** cap request sizes (`DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE`, `DATA_UPLOAD_MAX_NUMBER_FIELDS`), check content and extension, store under generated names, and serve user files from a separate domain or as attachments.
- **Logs and errors:** configure an error tracker that scrubs request bodies, cookies and authorization headers; never log passwords, tokens or full payment data.
- Run `pip-audit` and `bandit -r <package>` (or the project's equivalents) when dependencies or security-relevant code change.

## Startup, migration and static-files failures

Fix the cause the message names, one error at a time, rerun `python manage.py check`, then the tests. Stop and ask before anything that changes shared data or history.

| Message | Cause | Fix |
|---|---|---|
| `ImproperlyConfigured` or "settings are not configured" | `DJANGO_SETTINGS_MODULE` unset or a required setting missing | Set the variable the way `manage.py` and the test config do; add the setting from the environment |
| `AppRegistryNotReady: Apps aren't loaded yet` | Models imported at module level before `django.setup()`, often in a script or settings | Call `django.setup()` first in standalone scripts, or import inside functions |
| `RuntimeError: Model class ... doesn't declare an explicit app_label` | App missing from `INSTALLED_APPS`, or imported under two paths | Add the app; import it by one dotted path |
| `DisallowedHost` | Request host not in `ALLOWED_HOSTS` | Add the real hostname; never `*` in production |
| `SynchronousOnlyOperation` | Sync ORM call inside async code | `sync_to_async` around the sync function, or the async ORM methods (`django.md`) |
| "Conflicting migrations detected; multiple leaf nodes" | Two branches each added a migration to one app | `python manage.py makemigrations --merge`, read the merge migration, run the tests |
| `InconsistentMigrationHistory` | A migration is recorded as applied before one it depends on | Compare `showmigrations` with the files; repair on local databases only, and ask before touching a shared one |
| "relation ... already exists" during `migrate` | The schema was changed outside Django | `migrate --fake <app> <migration>` only after confirming the real schema matches that migration, and only with the user's go-ahead on shared databases |
| `ValueError: Missing staticfiles manifest entry` | `ManifestStaticFilesStorage` with `collectstatic` not run, or a template references a missing file | Run `collectstatic` in the build; fix the reference |
| `collectstatic` fails on a missing referenced file | A CSS `url()` points to a file that does not exist | Fix or remove the reference; `collectstatic --dry-run` shows it early |

Never delete applied migration files or reset an app's migrations on a database other people use; on a local throwaway database, `migrate <app> zero` and regenerating is acceptable when the user agrees.

## Done when

- [ ] Celery uses JSON, late acks only for idempotent tasks, time limits, a Redis visibility timeout longer than the longest task and delay, and one beat scheduler.
- [ ] Each new task takes IDs, is idempotent, retries only transient failures with backoff and a cap, is enqueued after commit, and has a direct unit test.
- [ ] `check --deploy` passes with production settings, or each remaining warning is explained.
- [ ] Secrets come from the environment, hosts and trusted origins are exact, cookies are secure, and HSTS changes were agreed.
- [ ] Error fixes changed only what the message required, `manage.py check` and the tests pass, and no shared migration history was rewritten.
