# Codebase map: output format and queries

Read this when the Markdown summary does not answer the question and you need to query the JSON map, or when you need to know exactly how a field is computed. Paths in the output are relative to the scanned root and use `/` separators. Lists are sorted, so two runs on the same tree produce byte-identical output.

## Top-level keys (`--json`)

| Key | Contents |
|---|---|
| `tool`, `version`, `schema_version` | Producer and format version (`schema_version` changes only when a field is renamed or removed) |
| `root` | Name of the scanned directory (never an absolute path) |
| `focus` | `null`, or `{path, depth, files_in_focus, neighbors}` when `--focus` was used |
| `stats` | Counts for the whole scan: `files`, `lines`, `code_files`, `graph_files`, `edges`, `truncated`, `max_files`, `gitignore`, `ignored_paths`, `exclude` (the `--exclude` patterns as given), `excluded_paths` (files and folders they matched; a folder counts once), `skipped_dirs`, `skipped_dir_examples`, `symlinks_skipped`, `not_opened`, `binary`, `too_large`, `parse_errors` |
| `languages` | `{language, category, files, lines}` sorted by lines. Categories: `code`, `schema`, `markup`, `style`, `config`, `docs` |
| `directories` | First-level folders (`(root files)` for the top level) with files, lines and main code language |
| `entry_points` | See "Entry point kinds" |
| `routes` | `{method, path, handler, file, line, framework}` |
| `hotspots` | `largest`, `most_imported`, `most_dependencies`, `cycles`, `unreferenced`, `unreferenced_total` |
| `external_dependencies` | `{name, ecosystem: python or js, stdlib, files}`. `files` is the number of files that import it |
| `files` | One record per scanned file (see below) |
| `edges` | `{source, target, kinds, line}` for each internal import, `line` being the first import line in `source` |

With `--focus`, `files` and `edges` hold the focus files plus their neighbors (`in_focus` tells them apart). `entry_points`, `routes`, `languages`, `directories` and `hotspots` cover the focus files only. `stats` always describes the whole scan.

## File records

| Field | Meaning |
|---|---|
| `language`, `category`, `bytes`, `lines` | `lines` is `null` for files that were not opened (unknown type, binary, credential-like name) |
| `is_test` | Under a `test`, `tests`, `__tests__`, `spec`, `specs`, `testing`, `e2e` or `cypress` folder, or named `test_*.py`, `*_test.py`, `*_test.go`, `conftest.py` or `*.test.*` / `*.spec.*` |
| `generated` | Contains an `@generated` or `DO NOT EDIT` marker near the top, or is a `.min.js` / `.bundle.js` file. Excluded from the largest-files list |
| `symbols` | Python and JS/TS only: `{name, kind, line, exported}` for top-level classes, functions, constants (Python `UPPER_CASE` names), exported variables, interfaces, types and enums. Python `exported` follows `__all__` when present, otherwise "no leading underscore" |
| `imports`, `imported_by` | Internal files this file imports, and that import it (all edge kinds) |
| `fan_out`, `fan_in` | `len(imports)`, and the number of non-test files in `imported_by` |
| `tested_by` | Test files that import this file directly |
| `external` | Packages imported (Python top-level module, npm package name, `node:` built-ins) |
| `unresolved` | Relative imports or aliases that did not resolve to a scanned file: broken imports, missing alias configuration, or targets outside the scan |
| `entry_point`, `route_file` | The file defines or is named by an entry point, or defines a route |
| `parse_error`, `too_large`, `binary`, `not_opened` | Why a file has no symbols or imports. Files over 1 MB are counted but not parsed |

## Edge kinds

| Kind | Source syntax | Counts toward cycles |
|---|---|---|
| `import` | Python module-level `import` / `from ... import`; JS/TS `import ... from`, side-effect `import 'x'` | Yes |
| `reexport` | `export ... from 'x'`, `export * from 'x'` | Yes |
| `require` | `require('x')`, including TypeScript `import x = require('x')` | Yes |
| `lazy` | Python import inside a function body | No: it runs at call time, not at import time |
| `type` | Python imports under `if TYPE_CHECKING:`; `import type` / `export type`, and imports where every name is marked `type` | No: erased before runtime |
| `dynamic` | `import('x')` with a literal path | No: loaded on demand |

Edges point only to code files. Imports of stylesheets, images and JSON are dropped from the graph.

**Resolution.** Python: relative imports from the importing file's package. Absolute imports are tried from the importer's top-level source root, the repository root, `src/` and `lib/`, then from any unique module of that name in the repository (standard-library names excepted). JS/TS: relative paths with extension and `index` lookup, `.js` written for a `.ts` file, `tsconfig.json` / `jsconfig.json` `paths` and `baseUrl` (nearest config wins, `extends` is not followed), and packages defined in the repository's own `package.json` files (monorepo workspaces), using `exports["."]`, `source`, `module`, `main`, then `src/index`. Bare names that resolve nowhere are external packages. `$lib`, `~/` and `#` aliases that no config resolves are reported as unresolved, not as packages.

## Entry point kinds

| Kind | Detected from | `run` shows |
|---|---|---|
| `docker` | `ENTRYPOINT` and `CMD` in `Dockerfile`, `Containerfile`, `Dockerfile.*`, `*.dockerfile` | The instruction |
| `procfile` | `Procfile` process lines | `name: command` |
| `package-bin`, `package-main` | `bin`, `main` and `module` in `package.json` | Name and target file |
| `npm-script` | `scripts` in `package.json`, common ones first | The runner command (from `packageManager` or the lockfile) and the script; `targets` lists repository files the script names |
| `python-script` | `[project.scripts]`, `[project.gui-scripts]`, `[tool.poetry.scripts]`, `setup.py` `entry_points` and `scripts`, `setup.cfg` `[options.entry_points]` | `name -> module:function` |
| `python-module` | `__main__.py` | `python -m package` |
| `python-main-guard` | `if __name__ == "__main__":` outside test files | `python -m module` inside a package, else `python path` |
| `make-target` | Explicit Makefile targets (not variables, pattern rules or `.PHONY`) | `make target` |
| `go-main`, `rust-main` | `package main` with `func main()`; `fn main` in Rust sources | `go run ./dir`, `cargo run ...` |
| `shebang` | A `#!` first line in a non-test script | `./path` and the interpreter |

Commands are redacted before they are reported: `KEY=value` assignments whose name contains KEY, SECRET, TOKEN, PASSWORD, PWD, AUTH or CREDENTIAL, `--password` / `--token` / `--api-key` flag values, credentials in URLs and well-known token shapes become `<redacted>`.

## Route detection

| `framework` | Pattern | `method` |
|---|---|---|
| `python-decorator` | `@<obj>.get/post/put/patch/delete/head/options/route/api_route/websocket("/path")` | The verb; for `route` the `methods=[...]` list, or `DEFAULT` when absent (the framework's default, usually GET); `WS` for websockets |
| `django` | `path()`, `re_path()`, `url()` calls in a file named `urls.py` | `ANY`; the path is shown without the prefix of any `include()` |
| `express-style` | `app`, `server`, `fastify`, `router` or `*Router` objects calling `.get/.post/.../.all/.use/.route('/path', ...)` | The verb; `USE` for mounted routers, `ANY` for `all` and `route` |
| `nextjs-app` | `page.*` and `route.*` under `app/` or `src/app/` next to a `next.config.*` or a `package.json` that depends on `next`; `(group)` and `@slot` folders are dropped | `PAGE`, or the exported `GET`, `POST` and other handler names |
| `nextjs-pages` | Files under `pages/` or `src/pages/` (not `_app`, `_document`) | `PAGE`, or `ANY` under `pages/api/` |
| `sveltekit` | `+page.*` and `+server.*` under `src/routes/` | `PAGE`, or the exported handler names |

HTTP client calls such as `axios.get('/x')` or `client.get("/x")` are not routes and are not reported.

## Query recipes

Save the map once to a temporary file, then run small queries instead of loading the whole JSON into context.

```bash
MAP=/tmp/repo-map.json
python3 <productcraft>/modules/codebase-map/scripts/map_codebase.py . --json > "$MAP"
```

Who imports a module, and which tests cover it:

```bash
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); f={x["path"]:x for x in m["files"]}[sys.argv[2]]; print("imported by:", *f["imported_by"], sep="\n  "); print("tests:", *f["tested_by"], sep="\n  ")' "$MAP" src/billing/invoice.py
```

Every edge into a directory from outside it (the directory's public surface):

```bash
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); d=sys.argv[2].rstrip("/")+"/"; [print(e["source"], "->", e["target"], e["kinds"]) for e in m["edges"] if e["target"].startswith(d) and not e["source"].startswith(d)]' "$MAP" src/billing
```

Routes under a prefix:

```bash
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); [print(r["method"], r["path"], r["file"]+":"+str(r["line"])) for r in m["routes"] if r["path"].startswith(sys.argv[2])]' "$MAP" /api
```

Files that use a given package:

```bash
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); [print(f["path"]) for f in m["files"] if sys.argv[2] in f.get("external", [])]' "$MAP" requests
```

Compare two maps after a refactor (cycles and edges added or removed):

```bash
python3 -c '
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
edges = lambda m: {(e["source"], e["target"]) for e in m["edges"]}
cycles = lambda m: {tuple(c["files"]) for c in m["hotspots"]["cycles"]}
print("edges added:", sorted(edges(b) - edges(a)))
print("edges removed:", sorted(edges(a) - edges(b)))
print("cycles added:", sorted(cycles(b) - cycles(a)))
print("cycles removed:", sorted(cycles(a) - cycles(b)))
' /tmp/map-before.json /tmp/map-after.json
```

How one file reaches another (the shortest import chain, with the kind of each hop). Useful for "why does the CLI load the database layer?" A `type` or `lazy` hop means the chain does not exist at import time:

```bash
python3 -c '
import json, sys
from collections import deque
m = json.load(open(sys.argv[1])); start, goal = sys.argv[2], sys.argv[3]
kinds, nxt = {}, {}
for e in m["edges"]:
    kinds[e["source"], e["target"]] = "+".join(e["kinds"])
    nxt.setdefault(e["source"], []).append(e["target"])
prev, todo = {start: None}, deque([start])
while todo and goal not in prev:
    cur = todo.popleft()
    for t in sorted(nxt.get(cur, [])):
        if t not in prev:
            prev[t] = cur
            todo.append(t)
if goal not in prev:
    sys.exit(f"no import path from {start} to {goal}")
hops, cur = [], goal
while prev[cur]:
    hops.append(f"{prev[cur]} -[{kinds[prev[cur], cur]}]-> {cur}")
    cur = prev[cur]
print("\n".join(reversed(hops)))
' "$MAP" bin/cli.js src/db/pool.ts
```

A directory-level dependency diagram as Mermaid text, for a design doc or pull request (tests and type-only imports left out; the second argument is how many folder levels to group by):

```bash
python3 -c '
import json, sys
m = json.load(open(sys.argv[1])); depth = int(sys.argv[2])
group = lambda p: "/".join(p.split("/")[:-1][:depth]) or "(root)"
tests = {f["path"] for f in m["files"] if f["is_test"]}
counts = {}
for e in m["edges"]:
    a, b = group(e["source"]), group(e["target"])
    if a != b and e["source"] not in tests and set(e["kinds"]) - {"type"}:
        counts[a, b] = counts.get((a, b), 0) + 1
ids = {g: f"n{i}" for i, g in enumerate(sorted({g for pair in counts for g in pair}))}
print("flowchart LR")
for g, i in ids.items():
    print(f"  {i}[\"{g}\"]")
for (a, b), n in sorted(counts.items()):
    print(f"  {ids[a]} -->|{n}| {ids[b]}")
' "$MAP" 2
```

Edge labels count the file-level imports between two folders. If the diagram is empty or unreadable, change the depth. Draw what the reader needs, not every folder (`../../engineering-practices/references/docs-and-decisions.md`, runbooks and diagrams).

If `jq` is installed, the same queries are one-liners, for example `jq -r '.files[] | select(.path=="src/app.py") | .imported_by[]' "$MAP"`.
