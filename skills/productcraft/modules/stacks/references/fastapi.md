# FastAPI

Read this when the project builds an HTTP API with FastAPI: routers, Pydantic models, dependencies, database sessions, tests, deployment. General Python practice is in `python.md`; FastAPI security traps (opt-in auth, docs endpoints, CORS) are in `../../code-security-review/references/language-pitfalls.md#fastapi`; API shape (errors, pagination, idempotency) is in `../../engineering-practices/references/api-contracts.md`.

## Orient first

- **Pydantic major version decides the API.** v1 and v2 differ in almost every method name. Check the lock file before writing a model.

| Pydantic v1 | Pydantic v2 |
|---|---|
| `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)` |
| `.dict()`, `.json()`, `.parse_obj()` | `.model_dump()`, `.model_dump_json()`, `.model_validate()` |
| `@validator`, `@root_validator` | `@field_validator`, `@model_validator` |
| `BaseSettings` in `pydantic` | `BaseSettings` in the separate `pydantic-settings` package |

- **SQLAlchemy 1.4 or 2.0?** 2.0 style uses `select()` with `session.execute()`/`session.scalars()` and typed `Mapped[...]` columns; the legacy `session.query()` still works but do not mix styles in new code. Migrations are usually Alembic (`alembic/`, `alembic.ini`).
- **How it runs:** `uvicorn app.main:app`, Gunicorn with Uvicorn workers, or the `fastapi run` command (FastAPI 0.111+). Behind a proxy, configure forwarded headers (`--proxy-headers` and `--forwarded-allow-ips`) so client IPs and schemes are right.
- Find where the app is created, how routers are included, and where shared dependencies (database session, current user, settings) live. New endpoints reuse them.

## Structure

- One `APIRouter` per domain area, included in the app with a prefix and tags. Attach authentication at the router level (`APIRouter(dependencies=[Depends(require_user)])`) so new routes inherit it.
- Keep path functions thin: parse, call a service function, return a response model. Business rules live in plain functions or classes that tests can call without HTTP.
- Settings: a `pydantic-settings` class read once (a cached `get_settings()` dependency), failing at startup if something required is missing.
- **Lifespan, not startup events.** Create pools and clients in a lifespan context manager and close them on exit; `@app.on_event` is deprecated.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=10)
    yield
    await app.state.http.aclose()
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

## `def` or `async def`

| Endpoint declared as | Runs | Use when |
|---|---|---|
| `def` | In a thread pool (AnyIO's default limit is 40 threads) | The code calls blocking libraries: a sync database driver, `requests`, file I/O, CPU work |
| `async def` | On the event loop | Every I/O call inside is awaited from an async library |

- One blocking call inside an `async def` endpoint stalls every request in that worker. When in doubt, use `def`, or offload with `await anyio.to_thread.run_sync(fn)`.
- Sync endpoints compete for the thread pool; a burst of slow sync endpoints queues the rest. Measure before raising the limit.

## Dependencies

```python
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]

@router.get("/orders/{order_id}", response_model=OrderRead)
async def read_order(order_id: UUID, session: SessionDep, user: UserDep) -> Order:
    order = await session.get(Order, order_id)
    if order is None or order.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
```

- Use `Annotated[..., Depends(...)]` aliases so signatures stay readable and dependencies are reused consistently.
- Dependencies that `yield` run their cleanup after the response is built; use them for sessions and locks. A dependency is cached per request, so two parameters that depend on `get_session` share one session.
- Tests swap dependencies with `app.dependency_overrides[get_session] = override` and clear the overrides afterwards.

## Models and validation

- Separate models per direction: `OrderCreate` (input), `OrderUpdate` (all fields optional, for PATCH), `OrderRead` (output). Never accept or return ORM objects directly as the schema.
- Input models forbid unknown fields when the API should be strict: `model_config = ConfigDict(extra="forbid")`.
- `response_model` (or the return annotation) filters output to the declared fields; that is what keeps internal columns out of responses. Output models reading ORM objects need `from_attributes=True`.
- PATCH: apply only what the client sent, `payload.model_dump(exclude_unset=True)`.
- Constrain at the edge: `Annotated[str, Field(min_length=1, max_length=200)]`, `Annotated[int, Field(ge=1, le=100)]`, enums for closed sets, `EmailStr` (needs `email-validator`), `AnyHttpUrl`. Query parameters take the same constraints through `Query(ge=1, le=100)`.
- Money: `Decimal` fields, serialized as strings if clients are JavaScript.
- Validation errors return 422 in FastAPI's own shape. If the API has a single error format, register exception handlers for `RequestValidationError` and your domain errors that map to it.

## Database access with SQLAlchemy 2.0

- One engine per process, created at startup. Sessions from `async_sessionmaker(engine, expire_on_commit=False)`, one per request through a `yield` dependency; commit or roll back explicitly in the service layer or the dependency, consistently.
- **No lazy loading in async code.** Touching an unloaded relationship raises `MissingGreenlet`. Load what you need in the query: `select(Order).options(selectinload(Order.items))`, or `joinedload` for many-to-one. Setting `lazy="raise"` on relationships turns accidental lazy loads into errors in tests.
- Pool size times worker count must stay under the database's connection limit; with many workers, put a pooler (for example PgBouncer) in front and read its prepared-statement caveats for asyncpg.
- Alembic autogenerate is a draft: read every generated migration, check renames (autogenerate sees drop plus add), server defaults and indexes, and apply the rules in `../../engineering-practices/references/data-and-migrations.md`. Review the SQL with `alembic upgrade <rev> --sql`.

## Background work

- `BackgroundTasks` run in the same process after the response is sent. They are lost if the process restarts and they share the worker's resources. Use them only for small, best-effort work such as a cache warm-up.
- Anything that must happen (emails, payments, exports) goes to a real queue (Celery, arq, RQ, Dramatiq) with idempotent tasks and retries.

## Testing

- `TestClient` (sync, based on httpx) is the simplest. Use it as a context manager (`with TestClient(app) as client:`) so the lifespan runs.
- For async tests use `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`; that transport does not run the lifespan, so start it with a helper such as `asgi-lifespan`'s `LifespanManager` or create the resources in fixtures.
- Database isolation: run each test inside a transaction that is rolled back, or use a fresh schema per test session against a real database in a container. SQLite does not behave like PostgreSQL for locking, JSON or constraints.
- Use the async test plugin the project already has (`pytest-asyncio` or AnyIO's plugin), with its configured mode.
- Assert status, body and headers; include one test per permission rule (owner, other user, anonymous).

## Deployment notes

- Workers: for CPU-light async APIs, roughly one worker per core; measure. Set `--timeout-graceful-shutdown` (Uvicorn) or Gunicorn's `graceful_timeout` so in-flight requests finish on deploy.
- Disable or protect `/docs`, `/redoc` and `/openapi.json` for internal APIs; keep the schema in CI to detect breaking changes (`oasdiff` or similar).
- Return large payloads as streams (`StreamingResponse`) and paginate lists.

## Moving endpoints from Django or DRF

| Django or DRF | FastAPI equivalent |
|---|---|
| Serializer | Pydantic input and output models |
| ViewSet and router | `APIRouter` with explicit path functions |
| `permission_classes`, authentication classes | Dependencies at router or route level |
| Django ORM | SQLAlchemy 2.0 (or keep Django's ORM in a sync service and call it from `def` endpoints) |
| `settings.py` | `pydantic-settings` class |
| Middleware | ASGI middleware or dependencies |
| `manage.py test` with `APIClient` | pytest with `TestClient` |

Move one route group at a time behind the same public paths, with both stacks reading the same database during the transition; the incremental approach is in `legacy-modernization.md`. Keep response bodies and error shapes byte-for-byte compatible unless the API is versioned, and compare old and new responses on recorded requests before switching traffic.

## Done when

- [ ] Code matches the installed Pydantic and SQLAlchemy major versions.
- [ ] No blocking calls in `async def` paths; outbound clients and pools are created in the lifespan and closed.
- [ ] Every new route has input and output models, authentication from the router, and an ownership check where it returns user data.
- [ ] New Alembic migrations were read and their SQL reviewed.
- [ ] Tests ran through the project's environment, covering success, validation failure and permission cases.
