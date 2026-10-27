# Python

Read this before writing or changing Python: application code, libraries, scripts, workers. Django and FastAPI have their own references (`django.md`, `fastapi.md`); security traps are in `../../code-security-review/references/language-pitfalls.md#python`.

## Detect the setup before touching anything

| Signal | Meaning | Run commands as |
|---|---|---|
| `uv.lock`, `[tool.uv]` | uv manages the environment and lock | `uv sync`, then `uv run <cmd>` |
| `poetry.lock`, `[tool.poetry]` | Poetry | `poetry install`, `poetry run <cmd>` |
| `pdm.lock` | PDM | `pdm install`, `pdm run <cmd>` |
| `Pipfile.lock` | Pipenv | `pipenv install --dev`, `pipenv run <cmd>` |
| `requirements*.txt` (often compiled from `requirements*.in` by pip-tools) | pip in a virtual environment | `python -m venv .venv`, activate, `pip install -r ...` |
| `tox.ini`, `noxfile.py` | Test matrix runner; CI often calls it | `tox -e <env>`, `nox -s <session>` |
| `.pre-commit-config.yaml` | Hooks that CI may also run | `pre-commit run --files <changed files>` |

- Read `requires-python` in `pyproject.toml` (or `python_requires` in `setup.cfg`) and the CI matrix. That range, not your preference, decides which syntax is allowed.
- Never install into the system interpreter, never `sudo pip`, never add a second lock format. If no environment exists, create `.venv` in the project and say so.
- Look for the configured tools in `pyproject.toml` (`[tool.ruff]`, `[tool.black]`, `[tool.mypy]`, `[tool.pyright]`, `[tool.pytest.ini_options]`) or their own files (`ruff.toml`, `mypy.ini`, `pyrightconfig.json`, `pytest.ini`, `setup.cfg`).

## Syntax by minimum version

Use a feature only when the project's minimum supports it.

| Feature | Needs |
|---|---|
| `match` statements; `X \| Y` unions evaluated at runtime (in `isinstance`, Pydantic fields without postponed annotations) | 3.10 |
| `ExceptionGroup` and `except*`; `asyncio.TaskGroup`; `asyncio.timeout()`; `typing.Self`; `tomllib` | 3.11 |
| `type` aliases and generic syntax (`def first[T](xs: list[T]) -> T`); `typing.override`; `itertools.batched` | 3.12 |
| `warnings.deprecated`; an experimental free-threaded build | 3.13 |
| Free-threaded build officially supported; deferred evaluation of annotations by default; `concurrent.interpreters` | 3.14 (October 2025) |

`from __future__ import annotations` lets annotations use newer syntax on older versions, but anything evaluated at runtime (Pydantic, dataclass field introspection, `typing.get_type_hints`) still needs the real version.

## Tooling

- **Lint and format:** Ruff covers most of flake8, isort, pyupgrade and Black's formatting. If the project uses Black, isort or flake8, keep them; do not migrate as part of a feature. `ruff check --fix` only on files you changed.
- **Types:** run the checker the project configures, mypy or pyright, never both by surprise. A new module goes in at the project's strictness. Do not add `# type: ignore` without a code (`# type: ignore[attr-defined]`) and a reason.
- **Tests:** pytest unless the project uses `unittest` alone. `pytest -x -q path/to/test_file.py::test_name` for the fast loop, then the full suite.

## Idioms that matter

- **Types on every public function and class attribute.** Accept abstract types (`Iterable`, `Mapping`, `Sequence` from `collections.abc`), return concrete ones. Use `Protocol` for structural interfaces instead of base classes nobody needs.
- **Pick the right record type:** `dataclass` (add `frozen=True, slots=True` for value objects) for internal data; Pydantic or attrs-with-validators where input crosses a trust boundary; `TypedDict` for dict-shaped data you do not own (JSON payloads, kwargs); `NamedTuple` only for tuple compatibility.
- **Errors:** raise specific exception types; chain with `raise AppError("...") from err`; catch the narrowest type at the level that can act on it. Never `except:` or `except Exception: pass`. A library defines one base exception so callers can catch everything it raises.
- **Resources:** `with` for files, locks, connections, sessions and temporary directories; `contextlib.contextmanager` or `ExitStack` to build your own.
- **Paths and text:** `pathlib.Path`; always pass `encoding="utf-8"` to `open()` and `Path.read_text()`. Until UTF-8 mode becomes the default (planned for 3.15), the default encoding depends on the platform's locale and breaks on Windows.
- **Time:** use aware datetimes. `datetime.now(timezone.utc)` (or `datetime.UTC` on 3.11+), never `datetime.utcnow()` (deprecated in 3.12, returns a naive value). Store UTC; convert with `zoneinfo` at the edges.
- **Money and exact quantities:** `decimal.Decimal` built from strings, or integer minor units. Never `float`.
- **Logging:** `logger = logging.getLogger(__name__)` per module; pass arguments, not f-strings (`logger.info("charged %s", order_id)`), so formatting is lazy and aggregators can group messages. Libraries never call `logging.basicConfig`.
- **Configuration:** read the environment once at startup into a typed settings object and fail fast when something required is missing.
- **Imports:** no work at import time (network, database, reading large files). Heavy imports inside rarely used functions are fine for CLI startup time.

## Async

- Use asyncio only when the service is I/O-bound with many concurrent waits and the libraries are async (httpx, asyncpg, aiohttp, SQLAlchemy's async API). Otherwise threads or plain sync code are simpler.
- **Never block the event loop:** `requests`, `time.sleep`, synchronous database drivers, large `json.loads`, CPU-heavy loops. Offload with `await asyncio.to_thread(fn, ...)`, or a process pool for CPU work.
- **Structured concurrency (3.11+):**

```python
async def fetch_all(client: httpx.AsyncClient, urls: list[str]) -> list[bytes]:
    sem = asyncio.Semaphore(10)                      # bound the fan-out
    async def one(url: str) -> bytes:
        async with sem:
            async with asyncio.timeout(5):           # per-call deadline
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
    async with asyncio.TaskGroup() as tg:            # a failure cancels the siblings
        tasks = [tg.create_task(one(u)) for u in urls]
    return [t.result() for t in tasks]
```

- `gather()` without `return_exceptions=True` does not cancel the other tasks when one fails; prefer `TaskGroup`.
- Keep a reference to every task made with `create_task`; the loop holds only weak references, so an unreferenced task can be garbage-collected mid-flight.
- Do not swallow `asyncio.CancelledError`. If you must clean up, do it in `finally` or re-raise.
- One `httpx.AsyncClient` or connection pool per process, created at startup and closed at shutdown, not one per request.

## Concurrency and performance

- The GIL serializes Python bytecode in the default build: threads help with I/O, not CPU. CPU-bound work goes to `ProcessPoolExecutor`, vectorized libraries (NumPy, Polars) or native extensions. The free-threaded build (`python3.14t`) removes the GIL but many C extensions are not yet ready; do not switch a project to it as a side effect.
- Measure before optimizing: `python -m cProfile -o out.prof`, `py-spy top --pid <pid>` or `py-spy record` for running processes, `tracemalloc` for memory. Compare with `pytest-benchmark` or `timeit` under the same conditions.
- Common wins: avoid repeated attribute or global lookups in hot loops, build strings with `"".join`, use `set` and `dict` lookups instead of list scans, stream large files instead of reading them whole, `functools.cache` for pure functions with small key spaces.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Mutable default argument (`def f(items=[])`) shared across calls | Default to `None` and create inside; dataclasses use `field(default_factory=list)` |
| Closures in a loop capture the variable, not its value | Bind it: `lambda x=x: ...`, or `functools.partial` |
| `is` used for value comparison (`x is 1000`, `s is "a"`) | `==`; keep `is` for `None`, sentinels and identity |
| A module named like a standard-library or third-party one (`json.py`, `requests.py`) | Rename it; it shadows the real module |
| `mock.patch("module_a.func")` has no effect | Patch where the name is looked up: `patch("module_b.func")` when `module_b` did `from module_a import func` |
| Circular imports at load time | Move the shared piece to a lower module; import inside the function only as a last resort |
| Catching `Exception` around `await` hides cancellation and bugs | Catch the specific error; let `CancelledError` propagate |
| Floating-point money, naive datetimes | `Decimal` or minor units; aware UTC datetimes |
| `subprocess.run(cmd, shell=True)` with user input | Argument list without a shell; see the security reference |

## Testing

- Arrange tests to match the project (`tests/` mirroring the package, or tests beside modules). Use fixtures for setup, `tmp_path` for files, `monkeypatch` for environment variables, `pytest.mark.parametrize` for tables of cases.
- Mock only what you do not control or what is slow or nondeterministic (network, time, randomness). Use `autospec=True` (or `create_autospec`) so mocks fail when signatures drift. Freeze time with `time-machine` or `freezegun` if the project has one.
- Property-based tests with Hypothesis fit parsers, serializers and calculations (`../../engineering-practices/references/advanced-testing.md`).
- Async tests need the plugin the project uses (`pytest-asyncio` with its mode setting, or `anyio`'s pytest plugin). Do not add a second one.
- Coverage (`pytest --cov=<package> --cov-branch`) shows untested branches; it is a map, not a target to game.

## Packaging and distribution

- Libraries: metadata in `[project]` (PEP 621), a `src/` layout so tests import the installed package, a `py.typed` marker for typed packages, dependency ranges rather than pins. Build with `python -m build` or `uv build`; check with `twine check dist/*`.
- Applications: pin the full dependency tree with the project's lock tool; install from the lock in CI and containers.
- Console commands go in `[project.scripts]`, not hand-written wrapper scripts. Command-line design is in `cli-tools.md`.
- Never publish to PyPI or TestPyPI without explicit permission.

## Done when

- [ ] The change uses only syntax and standard-library features available at the project's minimum Python version.
- [ ] Commands ran through the project's environment manager: tests, the configured linter, formatter check and type checker, each clean or with pre-existing failures listed.
- [ ] No blocking call inside `async def` code paths; every outbound call has a timeout.
- [ ] New dependencies were agreed with the user and recorded in the project's lock file only.
- [ ] `pip-audit` (or the project's audit) ran if dependencies changed, or is marked `NOT VERIFIED`.
