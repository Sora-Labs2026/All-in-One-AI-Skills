"""Offline tests for map_codebase.py on small synthetic fixture trees; no network.

Each test copies a fixture from tests/fixtures/ into a temporary directory first,
so the committed fixtures are never scanned in place. Files that must not live in
the package (a .gitignore that would affect the host repository, a syntax-error
Python file, vendored and build directories, an .env file) are created in the copy.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPT = HERE.parents[0] / "scripts" / "map_codebase.py"
spec = importlib.util.spec_from_file_location("map_codebase", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def materialize(name, tmp):
    """Copy fixture `name` into `tmp` and add the files that are created at test time."""
    dest = Path(tmp) / name
    shutil.copytree(FIXTURES / name, dest)
    gi = dest / "_gitignore"
    if gi.exists():
        gi.rename(dest / ".gitignore")
    for vendor in ("node_modules/leftpad/index.js", "dist/bundle.js", ".venv/lib/site.py"):
        target = dest / vendor
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("module.exports = 1;\n")
    custom_env = dest / "envs" / "py311"
    custom_env.mkdir(parents=True)
    (custom_env / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (custom_env / "inside.py").write_text("import os\n")
    if name == "pyproj":
        (dest / ".env").write_text("SECRET_VALUE=do-not-read\n")
        (dest / "src" / "app" / "broken.py").write_text("def broken(:\n    pass\n")
        (dest / "data.bin").write_bytes(b"\x00\x01\x02binary")
    return dest


def full_map(root, **kwargs):
    top = kwargs.pop("top", 10)
    focus = kwargs.pop("focus", None)
    depth = kwargs.pop("depth", 1)
    return module.finalize(module.build_map(str(root), **kwargs), top=top, focus=focus, depth=depth)


def by_path(m):
    return {f["path"]: f for f in m["files"]}


def edge_set(m):
    return {(e["source"], e["target"]): tuple(e["kinds"]) for e in m["edges"]}


class FixtureCase(unittest.TestCase):
    fixture = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = materialize(self.fixture, self._tmp.name)
        self.map = full_map(self.root)
        self.files = by_path(self.map)

    def tearDown(self):
        self._tmp.cleanup()


class WalkTests(FixtureCase):
    fixture = "pyproj"

    def test_vendor_build_and_env_dirs_skipped(self):
        for path in self.files:
            self.assertFalse(path.startswith(("node_modules/", "dist/", ".venv/", "envs/py311/")), path)
        self.assertGreaterEqual(self.map["stats"]["skipped_dirs"], 4)

    def test_gitignore_rules(self):
        self.assertNotIn("generated/skip.py", self.files)   # directory rule
        self.assertNotIn("debug.log", self.files)           # glob rule
        self.assertIn("keep.log", self.files)               # negated rule
        self.assertNotIn("local_only.py", self.files)       # anchored to the root
        self.assertIn("src/local_only.py", self.files)      # ...so not ignored deeper
        self.assertGreaterEqual(self.map["stats"]["ignored_paths"], 3)

    def test_no_gitignore_flag(self):
        m = full_map(self.root, use_gitignore=False)
        self.assertIn("generated/skip.py", by_path(m))
        self.assertNotIn("node_modules/leftpad/index.js", by_path(m))

    def test_credential_like_and_binary_files_not_read(self):
        env = self.files[".env"]
        self.assertEqual(env["not_opened"], "credential-like name")
        self.assertIsNone(env["lines"])
        self.assertTrue(self.files["data.bin"].get("binary") or self.files["data.bin"]["lines"] is None)
        self.assertNotIn("do-not-read", json.dumps(self.map))

    def test_languages(self):
        langs = {x["language"]: x for x in self.map["languages"]}
        self.assertIn("Python", langs)
        self.assertEqual(langs["Python"]["category"], "code")
        self.assertEqual(self.files["scripts/tool"]["language"], "Python")  # extensionless shebang script

    def test_parse_error_is_reported_not_fatal(self):
        self.assertIn("src/app/broken.py", self.map["stats"]["parse_errors"])
        self.assertTrue(self.files["src/app/broken.py"]["parse_error"])

    def test_max_files_truncates_deterministically(self):
        a = full_map(self.root, max_files=5)
        b = full_map(self.root, max_files=5)
        self.assertTrue(a["stats"]["truncated"])
        self.assertEqual(len(a["files"]), 5)
        self.assertEqual([f["path"] for f in a["files"]], [f["path"] for f in b["files"]])


class GitignoreMatcherTests(unittest.TestCase):
    def ignored(self, patterns, path, is_dir=False, base=""):
        rules = module.parse_gitignore("\n".join(patterns), base)
        return module.is_ignored(path, is_dir, rules)

    def test_patterns(self):
        self.assertTrue(self.ignored(["*.pyc"], "a/b/c.pyc"))
        self.assertTrue(self.ignored(["/build"], "build", True))
        self.assertFalse(self.ignored(["/build"], "src/build", True))
        self.assertTrue(self.ignored(["logs/"], "x/logs", True))
        self.assertFalse(self.ignored(["logs/"], "x/logs", False))
        self.assertTrue(self.ignored(["**/cache/*.tmp"], "a/b/cache/x.tmp"))
        self.assertTrue(self.ignored(["docs/**"], "docs/a/b.md"))
        self.assertTrue(self.ignored(["a/**/z"], "a/z"))
        self.assertTrue(self.ignored(["a/**/z"], "a/b/c/z"))
        self.assertFalse(self.ignored(["*.log", "!keep.log"], "keep.log"))
        self.assertTrue(self.ignored(["# comment", "", "file[0-9].txt"], "file7.txt"))
        self.assertFalse(self.ignored(["*.md"], "pkg/x.md", base="other"))
        self.assertTrue(self.ignored(["*.md"], "pkg/x.md", base="pkg"))

    def test_outer_gitignore_applies_to_subdirectory_scan(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".git").mkdir()
            (repo / ".gitignore").write_text("svc/tmp/\n*.secret.py\n")
            (repo / "svc" / "tmp").mkdir(parents=True)
            (repo / "svc" / "tmp" / "x.py").write_text("X = 1\n")
            (repo / "svc" / "keep.py").write_text("Y = 1\n")
            (repo / "svc" / "a.secret.py").write_text("Z = 1\n")
            paths = by_path(full_map(repo / "svc"))
            self.assertIn("keep.py", paths)
            self.assertNotIn("tmp/x.py", paths)
            self.assertNotIn("a.secret.py", paths)


class PythonGraphTests(FixtureCase):
    fixture = "pyproj"

    def test_imports_resolved(self):
        edges = edge_set(self.map)
        self.assertIn(("src/app/cli.py", "src/app/core.py"), edges)        # from . import core
        self.assertIn(("src/app/cli.py", "src/app/models.py"), edges)      # from .models import Item
        self.assertIn(("src/app/models.py", "src/app/core.py"), edges)     # absolute, src layout
        self.assertIn(("src/django_site/urls.py", "src/django_site/views.py"), edges)
        self.assertIn(("tests/test_core.py", "src/app/core.py"), edges)    # test outside the package
        self.assertEqual(edges[("src/app/core.py", "src/app/models.py")], ("type",))
        self.assertEqual(edges[("src/app/core.py", "src/app/heavy.py")], ("lazy",))

    def test_externals_and_stdlib(self):
        core = self.files["src/app/core.py"]
        self.assertIn("requests", core["external"])
        deps = {(d["ecosystem"], d["name"]): d for d in self.map["external_dependencies"]}
        self.assertFalse(deps[("python", "requests")]["stdlib"])
        if hasattr(sys, "stdlib_module_names"):
            self.assertTrue(deps[("python", "os")]["stdlib"])

    def test_cycles_exclude_type_only_and_lazy_imports(self):
        cycles = self.map["hotspots"]["cycles"]
        self.assertEqual([c["files"] for c in cycles], [["src/app/ring_a.py", "src/app/ring_b.py"]])
        self.assertEqual(cycles[0]["example"], ["src/app/ring_a.py", "src/app/ring_b.py", "src/app/ring_a.py"])

    def test_symbols(self):
        syms = {(s["name"], s["kind"]) for s in self.files["src/app/core.py"]["symbols"]}
        self.assertTrue({("Runner", "class"), ("run", "function"), ("fetch", "async function"),
                         ("MAX_ITEMS", "constant")} <= syms)
        init = {s["name"]: s for s in self.files["src/app/__init__.py"]["symbols"]}
        self.assertTrue(init["VERSION"]["exported"])
        self.assertFalse(init["_INTERNAL"]["exported"])

    def test_fan_in_excludes_tests_and_lists_them(self):
        core = self.files["src/app/core.py"]
        self.assertEqual(core["fan_in"], 3)  # cli, models, heavy
        self.assertEqual(core["tested_by"], ["tests/test_core.py"])
        top = self.map["hotspots"]["most_imported"][0]
        self.assertEqual(top["path"], "src/app/core.py")

    def test_unreferenced(self):
        unref = {u["path"] for u in self.map["hotspots"]["unreferenced"]}
        self.assertIn("src/app/orphan.py", unref)
        self.assertNotIn("src/app/__main__.py", unref)
        self.assertNotIn("src/app/web.py", unref)  # route file
        self.assertNotIn("tests/test_core.py", unref)

    def test_entry_points(self):
        runs = {(e["kind"], e["run"]) for e in self.map["entry_points"]}
        self.assertIn(("python-script", "demo -> app.cli:main"), runs)
        self.assertIn(("python-module", "python -m app"), runs)
        self.assertIn(("python-main-guard", "python -m app.cli"), runs)
        self.assertIn(("docker", 'ENTRYPOINT ["python", "-m", "app"]'), runs)
        self.assertIn(("docker", 'CMD ["--help"]'), runs)
        self.assertIn(("make-target", "make test"), runs)
        self.assertIn(("shebang", "./scripts/tool"), runs)
        self.assertNotIn(("make-target", "make PYTHON"), runs)
        kinds = [e["kind"] for e in self.map["entry_points"]]
        self.assertNotIn("tests/test_core.py", [e["file"] for e in self.map["entry_points"]])
        self.assertEqual(kinds[0], "docker")

    def test_commands_are_redacted(self):
        worker = [e for e in self.map["entry_points"] if e["kind"] == "procfile" and e["name"] == "worker"][0]
        self.assertIn("API_TOKEN=<redacted>", worker["command"])
        self.assertNotIn("abc123", json.dumps(self.map))

    def test_routes(self):
        routes = {(r["method"], r["path"], r["handler"]) for r in self.map["routes"]}
        self.assertIn(("GET", "/items/{item_id}", "read_item"), routes)
        self.assertIn(("POST", "/login", "login"), routes)
        self.assertIn(("DEFAULT", "/logout", "logout"), routes)
        self.assertIn(("ANY", "health/", "views.health"), routes)
        self.assertFalse(any(p == "/elsewhere" for _, p, _ in routes))


class JavaScriptGraphTests(FixtureCase):
    fixture = "jsproj"

    def test_import_forms_resolved(self):
        edges = edge_set(self.map)
        self.assertIn(("src/index.ts", "src/lib/util.ts"), edges)    # extensionless relative
        self.assertIn(("src/index.ts", "src/lib/index.ts"), edges)   # directory index
        self.assertIn(("src/index.ts", "src/lib/dates.ts"), edges)   # multi-line, tsconfig alias
        self.assertIn(("src/index.ts", "src/lib/esm.ts"), edges)     # './x.js' written for x.ts
        self.assertIn(("bin/cli.js", "src/index.ts"), edges)         # require with ../
        self.assertIn(("app/dashboard/page.tsx", "packages/ui/src/index.ts"), edges)   # workspace package
        self.assertIn(("app/dashboard/page.tsx", "packages/ui/src/button.ts"), edges)  # workspace subpath
        self.assertNotIn("@demo/ui", self.files["app/dashboard/page.tsx"]["external"])
        self.assertEqual(edges[("src/lib/index.ts", "src/lib/util.ts")], ("reexport",))
        self.assertEqual(edges[("src/index.ts", "src/types.ts")], ("type",))
        self.assertEqual(edges[("src/index.ts", "src/lazy.ts")], ("dynamic",))
        self.assertFalse(any("ghost" in t for _, t in edges))       # commented-out imports
        self.assertFalse(any(t.endswith(".css") for _, t in edges))  # assets are not graph nodes

    def test_minified_and_compact_syntax(self):
        found = module.parse_js('import{a}from"./a";export*from"./b";import type{T}from"./t";x=require("./c")')["imports"]
        self.assertEqual([(i["kind"], i["spec"]) for i in found],
                         [("import", "./a"), ("reexport", "./b"), ("require", "./c"), ("type", "./t")])

    def test_externals(self):
        ext = set(self.files["src/index.ts"]["external"])
        self.assertEqual(ext, {"react", "node:fs", "node:path", "@scope/pkg"})

    def test_cycles(self):
        self.assertEqual([c["files"] for c in self.map["hotspots"]["cycles"]], [["src/a.js", "src/b.js"]])

    def test_symbols(self):
        syms = {(s["name"], s["kind"], s["exported"]) for s in self.files["src/index.ts"]["symbols"]}
        for expected in [("VERSION", "variable", True), ("start", "function", True), ("App", "class", True),
                         ("Options", "interface", True), ("Mode", "type", True), ("localHelper", "function", False)]:
            self.assertIn(expected, syms)

    def test_entry_points(self):
        runs = {(e["kind"], e["run"]) for e in self.map["entry_points"]}
        self.assertIn(("npm-script", "pnpm run dev"), runs)
        self.assertIn(("package-bin", "demo-cli -> bin/cli.js"), runs)
        self.assertIn(("package-main", "main: src/index.ts"), runs)
        self.assertIn(("shebang", "./bin/cli.js"), runs)
        scripts = [e["name"] for e in self.map["entry_points"] if e["kind"] == "npm-script"]
        self.assertEqual(scripts[:3], ["dev", "build", "test"])
        deploy = [e for e in self.map["entry_points"] if e.get("name") == "deploy"][0]
        self.assertEqual(deploy["command"], "DEPLOY_TOKEN=<redacted> node scripts/deploy.js")
        self.assertEqual(deploy["targets"], ["scripts/deploy.js"])
        self.assertTrue(self.files["scripts/deploy.js"]["entry_point"])

    def test_routes(self):
        routes = {(r["method"], r["path"], r["framework"]) for r in self.map["routes"]}
        self.assertIn(("GET", "/health", "express-style"), routes)
        self.assertIn(("POST", "/users", "express-style"), routes)
        self.assertIn(("USE", "/api", "express-style"), routes)
        self.assertIn(("PAGE", "/", "nextjs-app"), routes)
        self.assertIn(("PAGE", "/dashboard", "nextjs-app"), routes)
        self.assertIn(("PAGE", "/about", "nextjs-app"), routes)        # route group dropped
        self.assertIn(("GET,POST", "/api/items", "nextjs-app"), routes)
        self.assertIn(("ANY", "/api/hello", "nextjs-pages"), routes)
        self.assertFalse(any(p == "/not-a-route" for _, p, _ in routes))

    def test_unreferenced_and_tests(self):
        unref = {u["path"] for u in self.map["hotspots"]["unreferenced"]}
        self.assertEqual(unref, {"src/orphan.ts"})
        self.assertEqual(self.files["src/server.js"]["tested_by"], ["src/server.test.js"])
        self.assertTrue(self.files["src/server.test.js"]["is_test"])


class MixedProjectTests(FixtureCase):
    fixture = "mixed"

    def test_setup_go_rust_and_svelte(self):
        runs = {(e["kind"], e["run"]) for e in self.map["entry_points"]}
        self.assertIn(("python-script", "legacy-tool -> legacy.main:run"), runs)
        self.assertIn(("python-script", "legacy-admin -> legacy.admin:main"), runs)
        self.assertIn(("go-main", "go run ./cmd/server"), runs)
        self.assertIn(("rust-main", "cargo run --manifest-path crates/tool/Cargo.toml"), runs)
        routes = {(r["method"], r["path"], r["framework"]) for r in self.map["routes"]}
        self.assertIn(("PAGE", "/blog", "sveltekit"), routes)
        self.assertIn(("GET", "/api/posts", "sveltekit"), routes)
        blog = self.files["site/src/routes/blog/+page.svelte"]
        self.assertIn("$lib/Header.svelte", blog.get("unresolved", []))
        self.assertEqual(blog["external"], [])

    def test_pyproject_fallback_parser(self):
        text = '[project.scripts]\nmytool = "pkg.cli:main"\n\n[tool.poetry.scripts]\nother = "pkg.other:run"\n'
        tables = module._pyproject_scripts_fallback(text)
        self.assertEqual(tables["project.scripts"], {"mytool": "pkg.cli:main"})
        self.assertEqual(tables["tool.poetry.scripts"], {"other": "pkg.other:run"})


class FocusTests(FixtureCase):
    fixture = "pyproj"

    def test_focus_file_with_neighbors(self):
        m = full_map(self.root, focus="src/app/models.py", depth=1)
        paths = {f["path"]: f["in_focus"] for f in m["files"]}
        self.assertEqual(paths["src/app/models.py"], True)
        self.assertEqual(paths["src/app/core.py"], False)   # imported by models, and imports it (type)
        self.assertEqual(paths["src/app/cli.py"], False)    # imports models
        self.assertNotIn("src/app/ring_a.py", paths)         # two hops away
        self.assertEqual(m["focus"]["files_in_focus"], 1)
        self.assertTrue(all(e["source"] in paths and e["target"] in paths for e in m["edges"]))

    def test_focus_directory_depth_zero(self):
        m = full_map(self.root, focus="src/django_site", depth=0)
        self.assertEqual(sorted(f["path"] for f in m["files"]),
                         ["src/django_site/__init__.py", "src/django_site/urls.py", "src/django_site/views.py"])
        self.assertEqual([r["handler"] for r in m["routes"]], ["views.health"])
        self.assertEqual(m["entry_points"], [])

    def test_focus_without_match_raises(self):
        with self.assertRaises(ValueError):
            full_map(self.root, focus="generated")

    def test_markdown_focus_section(self):
        md = module.render_markdown(full_map(self.root, focus="src/app/models.py"))
        self.assertIn("## Focus files (1)", md)
        self.assertIn("### `src/app/models.py`", md)
        self.assertIn("Imported by: `src/app/cli.py`", md)


class OutputAndSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = materialize("pyproj", self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, timeout=120)

    def snapshot(self):
        out = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            for name in filenames:
                p = os.path.join(dirpath, name)
                st = os.stat(p)
                out[p] = (st.st_size, st.st_mtime_ns)
            out[dirpath] = tuple(sorted(dirnames))
        return out

    def test_help(self):
        res = self.run_cli("--help")
        self.assertEqual(res.returncode, 0)
        for flag in ("--json", "--md", "--focus", "--max-files", "--depth", "--top", "--no-gitignore"):
            self.assertIn(flag, res.stdout)

    def test_json_and_markdown_cli(self):
        res = self.run_cli(str(self.root), "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data["schema_version"], 1)
        for key in ("stats", "languages", "directories", "entry_points", "routes", "hotspots",
                    "external_dependencies", "files", "edges"):
            self.assertIn(key, data)
        res = self.run_cli(str(self.root), "--md", "--top", "3")
        self.assertEqual(res.returncode, 0, res.stderr)
        for heading in ("# Codebase map: pyproj", "## Languages", "## Entry points", "## Routes", "## Hotspots"):
            self.assertIn(heading, res.stdout)
        self.assertIn("Import cycles (1", res.stdout)

    def test_deterministic(self):
        a = self.run_cli(str(self.root), "--json").stdout
        b = self.run_cli(str(self.root), "--json").stdout
        self.assertEqual(a, b)
        self.assertNotIn(str(self.root), a)  # no absolute paths in the output

    def test_read_only(self):
        before = self.snapshot()
        self.run_cli(str(self.root), "--json")
        self.run_cli(str(self.root), "--focus", "src/app")
        self.assertEqual(before, self.snapshot())

    def test_bad_arguments(self):
        self.assertEqual(self.run_cli(str(self.root / "missing")).returncode, 2)
        self.assertEqual(self.run_cli(str(self.root), "--focus", "nope").returncode, 2)
        self.assertEqual(self.run_cli(str(self.root), "--focus", "..").returncode, 2)
        self.assertEqual(self.run_cli(str(self.root), "--max-files", "0").returncode, 2)
        res = self.run_cli(str(self.root), "--json", "--md")
        self.assertEqual(res.returncode, 2)

    def test_redact(self):
        self.assertEqual(module.redact("STRIPE_SECRET_KEY=abc node x.js"), "STRIPE_SECRET_KEY=<redacted> node x.js")
        self.assertEqual(module.redact("psql postgres://u:pw@db/x"), "psql postgres://<redacted>@db/x")
        self.assertEqual(module.redact("tool --token abc --port 80"), "tool --token <redacted> --port 80")
        self.assertEqual(module.redact("NODE_ENV=production next start"), "NODE_ENV=production next start")


if __name__ == "__main__":
    unittest.main()
