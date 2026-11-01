# Python testing with pytest

Read this when you write, organize, speed up or debug pytest suites: fixtures and their scopes, parametrization, mocking, time and randomness, async tests, database isolation, parallel runs and flaky tests. The short version is in `python.md`; Django, FastAPI and Celery specifics are in `django.md`, `fastapi.md` and `django-celery-and-security.md`; property-based, mutation and differential testing are in `../../engineering-practices/references/advanced-testing.md`; the test-first loop is in `../../engineering-workflow/references/test-first.md`.

## Configuration worth having

Read the existing config first (`[tool.pytest.ini_options]` in `pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini`) and change it only with a reason.

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config", "-ra", "--import-mode=importlib"]
markers = ["slow: takes more than a few seconds", "integration: needs a database or another service"]
filterwarnings = ["error", "ignore::DeprecationWarning:some_third_party_pkg.*"]
xfail_strict = true
```

- `--strict-markers` turns a typo in `@pytest.mark.intergration` into an error instead of a silently unselected test.
- `filterwarnings = ["error"]` makes new deprecation warnings fail the run, which is the cheapest early warning of the next upgrade. Ignore third-party warnings narrowly, by module.
- `xfail_strict = true` makes a test marked `xfail` that starts passing fail, so stale markers get removed.
- pytest recommends `--import-mode=importlib` for new projects; it avoids clashes between test files with the same name. Existing suites may rely on the older mode; do not switch as a side effect.
- With a `src/` layout, test the installed package (`pip install -e .` or `uv sync`) rather than adding `src` to `sys.path` by hand.

## Fixtures

- **Scope** sets how often a fixture is built: `function` (default), `class`, `module`, `package`, `session`. Use wider scopes only for expensive, read-only resources (a database engine, a container, a compiled schema). Mutable state in a wide-scope fixture makes tests depend on order.
- **Teardown** goes after `yield`; it runs even when the test fails. Several resources in one fixture: use `contextlib.ExitStack` so each is released if a later one fails.
- **Factory fixtures** return a function, so each test builds exactly the data it needs:

```python
import pytest

@pytest.fixture
def make_invoice(db_session):
    created = []
    def _make(*, status="draft", total_minor=1_000, currency="EUR", **overrides):
        invoice = Invoice(status=status, total_minor=total_minor, currency=currency, **overrides)
        db_session.add(invoice)
        db_session.flush()
        created.append(invoice)
        return invoice
    yield _make
    # rows disappear with the per-test transaction rollback; nothing else to clean

def test_overdue_invoices_are_flagged(make_invoice, clock):
    overdue = make_invoice(status="sent", due_date=clock.today() - timedelta(days=1))
    current = make_invoice(status="sent", due_date=clock.today())
    assert flag_overdue([overdue, current]) == [overdue.id]
```

- **`conftest.py` placement** decides visibility: fixtures in `tests/conftest.py` serve the whole suite, `tests/api/conftest.py` only that folder. Keep shared fixtures at the lowest level that serves all their users. `pytest_plugins` is allowed only in the root `conftest.py`.
- `autouse=True` fixtures run for every test in scope and hide setup from the reader. Reserve them for global safety (blocking real network calls, resetting a registry).
- Builtin fixtures cover most needs: `tmp_path` (a fresh directory), `monkeypatch` (environment variables, attributes, `sys.path`; undone after the test), `capsys` and `capfd` (output), `caplog` (log records), `recwarn`.
- Data builders: `factory_boy` for ORM models, `polyfactory` for dataclasses and Pydantic models, or plain functions. Keep defaults minimal and valid; set in the test only what the test is about.

## Parametrization

```python
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("12.50", Decimal("12.50"), id="two-decimals"),
        pytest.param("12", Decimal("12"), id="integer"),
        pytest.param(" 7.1 ", Decimal("7.1"), id="surrounding-space"),
        pytest.param("1e3", None, id="exponent-rejected"),
        pytest.param("12,50", None, id="comma-decimal", marks=pytest.mark.xfail(reason="locale parsing not built yet")),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected
```

- Give cases readable ids; failures then name the case, and `-k exponent` selects it.
- Stacking two `parametrize` decorators runs the cartesian product. Use it on purpose, not by accident; use a list of tuples when only some combinations matter.
- `indirect=["db"]` passes the parameter to a fixture instead of the test, for example to run the same tests against two database engines.
- Parametrize over inputs and expected results, not over code paths with `if` branches inside the test; a test with conditionals hides which case failed.
- When the rule matters more than the examples, a property test (Hypothesis) generates the cases; see the advanced-testing reference. Hypothesis does not reset function-scoped fixtures between generated examples, so build per-example state inside the test.

## Exceptions, warnings and logs

- `with pytest.raises(PaymentDeclined, match=r"card .* expired"):` checks the type and the message; inspect attributes through `excinfo.value`.
- `pytest.warns(DeprecationWarning)` asserts a warning; `caplog.at_level(logging.WARNING, logger="billing")` captures logs for assertions on what was logged (and that secrets were not).
- Never catch exceptions in a test to assert on them by hand, and never `assert True` in an `except` branch.

## Mocking without lying

- Fake what you do not control, what is slow, or what is nondeterministic: outbound HTTP, the clock, randomness, email, payment providers. Use real objects for your own code where practical.
- Patch the name where it is looked up (`python.md`). Use `autospec=True` or `create_autospec(Client, instance=True)` so calls with wrong arguments fail; use `AsyncMock` (autospec produces it for `async def`) and assert with `assert_awaited_once_with`.
- Prefer a small fake with real behavior (an in-memory repository, a fake clock) over a mock with a script of return values; fakes survive refactors, scripted mocks pin implementation details.
- HTTP: `respx` for httpx, `responses` for requests, or a local test server. Block real network access in the test run so a forgotten mock fails loudly rather than calling production.
- If the project uses `pytest-mock`, its `mocker` fixture undoes patches automatically; do not mix it with decorator-style patches in the same file.

## Time and randomness

- Inject a clock (a function or object returning the current time) where you can; otherwise freeze time with the library the project has (`time-machine` or `freezegun`).
- Seed randomness explicitly, or use `pytest-randomly`, which shuffles test order and reseeds `random` per test, printing the seed at the top of the run. Reproduce an order-dependent failure with `--randomly-seed=<seed>`, or disable shuffling with `-p no:randomly` while you bisect.

## Async tests

- Use the plugin the project already has: `pytest-asyncio` (with its `asyncio_mode` setting) or AnyIO's pytest plugin (`@pytest.mark.anyio`). Do not add a second one.
- pytest-asyncio 1.0 (2025) removed the `event_loop` fixture; event-loop scope is set with `loop_scope=` on markers and fixtures and the `asyncio_default_fixture_loop_scope` option. Session-scoped async fixtures (an engine, a client) need a session-scoped loop.
- "Event loop is closed" or "attached to a different loop" usually means a client or engine created in one loop is used in another: give the fixture and the tests the same loop scope, or create the resource per test.
- Close async clients and engines in fixture teardown; unclosed resources show up as `ResourceWarning` and, with warnings as errors, failed tests.

## Databases

- Run tests against the same engine as production (PostgreSQL in a container through the CI service or Testcontainers). SQLite differs in types, constraints, JSON, locking and case sensitivity.
- Isolate each test in a transaction that is rolled back. With SQLAlchemy, bind the session to a connection with an outer transaction and use savepoints (`join_transaction_mode="create_savepoint"` in SQLAlchemy 2.0) so code under test may call `commit()`.
- Code that depends on real commits (after-commit hooks, a second connection, `LISTEN`/`NOTIFY`) needs a truncating fixture instead; mark those tests and keep them few.
- Create the schema once per session from migrations, not from `metadata.create_all()`, so migration bugs show up in tests.

## Speed and parallelism

- `pytest --durations=15` lists the slowest tests and fixtures; fix setup cost before adding workers.
- `pytest-xdist` (`-n auto`) runs tests in parallel processes. Each worker needs its own database or schema (suffix names with the `worker_id` fixture), its own temporary directories and free ports. Session-scoped fixtures run once per worker, not once overall.
- Keep the fast loop fast: `pytest -x --lf` reruns last failures and stops at the first; `-k` and node ids (`tests/test_billing.py::test_refund`) select precisely; `--pdb` drops into the debugger at the failure.
- Mark slow and integration tests and run `-m "not slow"` locally if the project does; CI still runs everything.

## Flaky tests

A test that passes on rerun has a cause; find it before marking anything. Usual causes: shared state between tests (module globals, caches, singletons, environment variables), order dependence (find with `pytest-randomly` seeds), real time and timezones, unordered collections compared as lists, real network, and asynchronous work not awaited. Quarantining with a skip needs the user's agreement and a tracked issue; retry plugins that rerun until green hide real bugs.

## Coverage

`pytest --cov=<package> --cov-branch --cov-report=term-missing` shows untested lines and branches. Use it to find what a change left untested. Enforce a threshold (`fail_under`) only where the project already does.

## Common failures

| Message or symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` for your own package | Package not installed in the test environment, or relying on the current directory | Install it (`pip install -e .`, `uv sync`); use the `importlib` import mode or the `pythonpath` option deliberately |
| "import file mismatch" | Two test files with the same name in different folders under the older import mode | `--import-mode=importlib`, or unique names, or `__init__.py` files |
| "fixture 'x' not found" | `conftest.py` in a folder the test cannot see, or a misspelled name | Move the fixture up a level; `pytest --fixtures` lists what is visible |
| Tests pass alone, fail together | Shared mutable state or order dependence | Reset state in fixtures; reproduce with a fixed random seed |
| `PytestUnraisableExceptionWarning`, `ResourceWarning` | Unclosed files, sockets or clients | Close them in fixture teardown or with context managers |
| "Event loop is closed" | Loop scope mismatch | Align `loop_scope` of fixtures and tests |
| A patch has no effect | Patched where defined, not where looked up | Patch the importing module's name |

## Done when

- [ ] New behavior has tests at the lowest useful level, with readable parametrized cases for boundaries and invalid input.
- [ ] Fixtures build only what each test needs, clean up after `yield`, and wide scopes hold only read-only resources.
- [ ] Mocks are autospecced or replaced by fakes; real network access is blocked; time and randomness are controlled.
- [ ] Database tests use the production engine and are isolated per test.
- [ ] The suite passes with warnings as errors (if configured), in random order, and in parallel if the project runs it that way.
