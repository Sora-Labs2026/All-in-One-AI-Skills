"""Offline tests for detect_stack.py using temporary directories only; no network, no project code run."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_stack.py"
spec = importlib.util.spec_from_file_location("detect_stack", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

HAS_TOML = module.tomllib is not None


def write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = module.main(argv)
        except SystemExit as exc:  # argparse usage errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def report(root: Path, *extra):
    code, out, _ = run([str(root), "--json", *extra])
    return code, json.loads(out) if out.strip() else None


def project(rep, path, stack_prefix):
    for p in rep["projects"]:
        if p["path"] == path and p["stack"].startswith(stack_prefix):
            return p
    raise AssertionError(f"no {stack_prefix} project at {path}: {[(p['path'], p['stack']) for p in rep['projects']]}")


def versions(p):
    return {v["name"]: v["value"] for v in p["versions"]}


class PythonTests(unittest.TestCase):
    @unittest.skipUnless(HAS_TOML, "tomllib needed for full pyproject parsing")
    def test_uv_django_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pyproject.toml", '[project]\nname = "shop"\nrequires-python = ">=3.12"\n'
                  'dependencies = ["Django>=5.2", "celery"]\n\n[tool.ruff]\nline-length = 100\n\n'
                  '[tool.mypy]\nstrict = true\n\n[tool.pytest.ini_options]\naddopts = "-q"\n')
            write(root, "uv.lock", "version = 1\n")
            write(root, "manage.py", "# entry\n")
            write(root, ".python-version", "3.12.7\n")
            code, rep = report(root)
            self.assertEqual(code, 0)
            p = project(rep, ".", "Python")
            self.assertEqual(p["package_manager"], "uv")
            self.assertIn("Django", p["frameworks"])
            self.assertIn("Celery", p["frameworks"])
            self.assertEqual(versions(p)["requires-python"], ">=3.12")
            self.assertEqual(versions(p)[".python-version"], "3.12.7")
            for tool in ("ruff", "mypy", "pytest"):
                self.assertIn(tool, p["tools"])
            self.assertIn("uv run pytest", p["defaults"])
            self.assertIn("uv run python manage.py makemigrations --check --dry-run", p["defaults"])

    def test_two_lockfiles_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pyproject.toml", '[project]\nname = "x"\n')
            write(root, "uv.lock", "")
            write(root, "poetry.lock", "")
            _, rep = report(root)
            p = project(rep, ".", "Python")
            self.assertTrue(any("several Python lockfiles" in n for n in p["notes"]))

    def test_requirements_pinning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a/requirements.txt", "flask==3.0.3\nrequests==2.32.3\n")
            write(root, "b/requirements.txt", "fastapi>=0.110\n")
            _, rep = report(root)
            a, b = project(rep, "a", "Python"), project(rep, "b", "Python")
            self.assertIn("requirements.txt", a["lockfiles"])
            self.assertIn("Flask", a["frameworks"])
            self.assertTrue(any("not fully pinned" in n for n in b["notes"]))
            self.assertIn("FastAPI", b["frameworks"])

    def test_workspace_lock_found_in_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pyproject.toml", '[project]\nname = "root"\n')
            write(root, "uv.lock", "")
            write(root, "packages/lib/pyproject.toml", '[project]\nname = "lib"\n')
            _, rep = report(root)
            lib = project(rep, "packages/lib", "Python")
            self.assertEqual(lib["package_manager"], "uv")
            self.assertIn("uv.lock (workspace root)", lib["lockfiles"])


class CompiledLanguageTests(unittest.TestCase):
    def test_go_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "go.mod", "module example.com/api\n\ngo 1.23\n\ntoolchain go1.24.1\n\n"
                  "require github.com/gin-gonic/gin v1.10.0\n")
            write(root, "go.sum", "")
            write(root, ".golangci.yml", 'version: "2"\nlinters:\n  default: standard\n')
            _, rep = report(root)
            p = project(rep, ".", "Go")
            self.assertEqual(versions(p)["go"], "1.23")
            self.assertEqual(versions(p)["toolchain"], "go1.24.1")
            self.assertIn("Gin", p["frameworks"])
            self.assertIn("golangci-lint v2 config", p["tools"])
            self.assertIn("golangci-lint run", p["defaults"])
            self.assertTrue(any("GOTOOLCHAIN" in n for n in p["notes"]))

    @unittest.skipUnless(HAS_TOML, "tomllib needed for Cargo workspace parsing")
    def test_rust_workspace_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Cargo.toml", '[workspace]\nmembers = ["crates/app"]\n\n[workspace.package]\nedition = "2024"\n'
                  'rust-version = "1.85"\n')
            write(root, "Cargo.lock", "")
            write(root, "deny.toml", "")
            write(root, "crates/app/Cargo.toml", '[package]\nname = "app"\nedition.workspace = true\n\n'
                  '[dependencies]\ntokio = { version = "1", features = ["full"] }\naxum = "0.8"\n')
            _, rep = report(root)
            ws = project(rep, ".", "Rust")
            self.assertEqual(versions(ws)["workspace edition"], "2024")
            self.assertIn("cargo deny check", ws["defaults"])
            app = project(rep, "crates/app", "Rust")
            self.assertIn("Tokio", app["frameworks"])
            self.assertIn("Axum", app["frameworks"])
            self.assertIn("Cargo.lock (workspace root)", app["lockfiles"])
            self.assertNotIn("edition", versions(app))

    def test_cmake_presets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "CMakeLists.txt", "cmake_minimum_required(VERSION 3.25)\nproject(engine CXX)\n"
                  "set(CMAKE_CXX_STANDARD 20)\nenable_testing()\nfind_package(GTest REQUIRED)\n")
            write(root, "CMakePresets.json", json.dumps({"version": 6, "configurePresets": [
                {"name": "base", "hidden": True}, {"name": "dev", "inherits": "base"}]}))
            write(root, ".clang-format", "BasedOnStyle: LLVM\n")
            _, rep = report(root)
            p = project(rep, ".", "C/C++")
            self.assertEqual(versions(p)["CMAKE_CXX_STANDARD"], "20")
            self.assertEqual(p["defaults"][0], "cmake --preset dev")
            self.assertIn("googletest", p["tools"])
            self.assertIn("clang-format --dry-run -Werror <changed files>", p["defaults"])

    def test_dotnet_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Api.csproj", '<Project Sdk="Microsoft.NET.Sdk.Web">\n  <PropertyGroup>\n'
                  "    <TargetFramework>net10.0</TargetFramework>\n    <Nullable>enable</Nullable>\n"
                  '  </PropertyGroup>\n  <ItemGroup><PackageReference Include="Microsoft.EntityFrameworkCore" /></ItemGroup>\n</Project>\n')
            write(root, "global.json", json.dumps({"sdk": {"version": "10.0.100", "rollForward": "latestFeature"}}))
            write(root, "Directory.Packages.props", "<Project/>")
            _, rep = report(root)
            p = project(rep, ".", ".NET")
            v = versions(p)
            self.assertEqual(v["TargetFramework"], "net10.0")
            self.assertEqual(v["sdk"], "10.0.100")
            self.assertIn("ASP.NET Core", p["frameworks"])
            self.assertIn("EF Core", p["frameworks"])
            self.assertTrue(any("central package management" in n for n in p["notes"]))


class JvmTests(unittest.TestCase):
    def test_maven_spring_boot_with_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pom = ("<project><parent><groupId>org.springframework.boot</groupId>"
                   "<artifactId>spring-boot-starter-parent</artifactId><version>3.4.1</version></parent>"
                   "<properties><java.version>21</java.version></properties></project>")
            write(root, "pom.xml", pom)
            write(root, "mvnw", "#!/bin/sh\n")
            write(root, "orders/pom.xml", "<project><artifactId>orders</artifactId></project>")
            _, rep = report(root)
            top = project(rep, ".", "JVM (Maven)")
            self.assertIn("Spring Boot", top["frameworks"])
            self.assertEqual(versions(top)["spring-boot-starter-parent"], "3.4.1")
            self.assertEqual(versions(top)["java.version"], "21")
            self.assertEqual(top["defaults"][0], "./mvnw -q verify")
            mod = project(rep, "orders", "JVM (Maven)")
            self.assertIn("-pl orders -am verify", mod["defaults"][0])
            self.assertEqual(mod["notes"], [])

    def test_gradle_kotlin_without_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "build.gradle.kts", 'plugins {\n    kotlin("jvm") version "2.1.0"\n'
                  '    id("org.springframework.boot") version "3.5.0"\n    id("io.gitlab.arturbosch.detekt")\n}\n'
                  "kotlin { jvmToolchain(21) }\n")
            _, rep = report(root)
            p = project(rep, ".", "JVM (Gradle)")
            v = versions(p)
            self.assertEqual(v["kotlin plugin"], "2.1.0")
            self.assertEqual(v["spring boot plugin"], "3.5.0")
            self.assertEqual(v["java toolchain"], "21")
            self.assertIn("Kotlin", p["frameworks"])
            self.assertIn("detekt", p["tools"])
            self.assertTrue(any("no Gradle wrapper" in n for n in p["notes"]))


class ScriptingStackTests(unittest.TestCase):
    def test_laravel_without_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "composer.json", json.dumps({
                "require": {"php": "^8.3", "laravel/framework": "^12.0"},
                "require-dev": {"larastan/larastan": "^3.0", "pestphp/pest": "^3.0", "laravel/pint": "^1.0"},
                "scripts": {"test": "pest", "post-autoload-dump": "x"}}))
            write(root, "artisan", "#!/usr/bin/env php\n")
            _, rep = report(root)
            p = project(rep, ".", "PHP")
            self.assertIn("Laravel", p["frameworks"])
            self.assertEqual(versions(p)["require php"], "^8.3")
            self.assertIn("php artisan test", p["defaults"])
            self.assertIn("vendor/bin/pint --test", p["defaults"])
            self.assertIn({"command": "composer run test", "source": "composer.json"}, p["commands"])
            self.assertFalse(any("post-autoload-dump" in c["command"] for c in p["commands"]))
            self.assertTrue(any("without composer.lock" in n for n in p["notes"]))

    def test_rails_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Gemfile", 'source "https://rubygems.org"\nruby "3.3.6"\ngem "rails", "~> 8.0.1"\n'
                  'group :test do\n  gem "rspec-rails"\nend\ngem "rubocop-rails-omakase"\ngem "brakeman"\n')
            write(root, "Gemfile.lock", "GEM\n  specs:\n    rails (8.0.1)\n\nRUBY VERSION\n   ruby 3.3.6p108\n")
            write(root, "config/application.rb", "config.load_defaults 8.0\n")
            write(root, ".rubocop.yml", "inherit_gem: {}\n")
            _, rep = report(root)
            p = project(rep, ".", "Ruby")
            v = versions(p)
            self.assertEqual(v["rails (lock)"], "8.0.1")
            self.assertEqual(v["ruby (lock)"], "3.3.6p108")
            self.assertEqual(v["config.load_defaults"], "8.0")
            self.assertIn("Rails", p["frameworks"])
            self.assertIn("bundle exec rspec", p["defaults"])
            self.assertIn("bundle exec brakeman -q --no-pager", p["defaults"])

    def test_swift_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Package.swift", "// swift-tools-version:6.0\nimport PackageDescription\n"
                  'let package = Package(name: "Kit", platforms: [.iOS(.v17), .macOS(.v14)])\n')
            _, rep = report(root)
            p = project(rep, ".", "Swift")
            v = versions(p)
            self.assertEqual(v["swift-tools-version"], "6.0")
            self.assertEqual(v["platform iOS"], "17")
            self.assertEqual(p["defaults"][:2], ["swift build", "swift test"])

    def test_node_lockfile_conflict_and_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "package.json", json.dumps({"scripts": {"test": "vitest", "lint": "eslint ."},
                                                    "devDependencies": {"typescript": "5.6.0"}}))
            write(root, "package-lock.json", "{}")
            write(root, "yarn.lock", "")
            _, rep = report(root)
            p = project(rep, ".", "JavaScript")
            self.assertTrue(any("several package managers" in n for n in p["notes"]))
            self.assertEqual(p["defaults"], [])
            self.assertIn("TypeScript", p["frameworks"])


class PlatformTests(unittest.TestCase):
    def test_platformio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "platformio.ini", "[env:esp32dev]\nplatform = espressif32\nboard = esp32dev\nframework = arduino\n\n"
                  "[env:native]\nplatform = native\n")
            _, rep = report(root)
            p = project(rep, ".", "Embedded (PlatformIO)")
            self.assertIn("pio run -e esp32dev", p["defaults"])
            self.assertIn("pio test -e native", p["defaults"])
            self.assertTrue(any("flashing" in n for n in p["notes"]))

    def test_salesforce_absorbs_lwc_tooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "sfdx-project.json", json.dumps({"sourceApiVersion": "62.0",
                                                         "packageDirectories": [{"path": "force-app", "default": True}]}))
            write(root, "package.json", json.dumps({"scripts": {"lint": "eslint **/lwc/**", "test:unit": "sfdx-lwc-jest"}}))
            _, rep = report(root)
            self.assertEqual([p["stack"] for p in rep["projects"]], ["Salesforce"])
            p = rep["projects"][0]
            self.assertEqual(versions(p)["sourceApiVersion"], "62.0")
            self.assertIn("npm run test:unit", [c["command"] for c in p["commands"]])
            self.assertTrue(any("scratch orgs or sandboxes" in n for n in p["notes"]))


class WebPlatformTests(unittest.TestCase):
    def test_flutter_shopify_wordpress_unity_signals(self):
        db_password = "pw_" + "z" * 20
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "app/pubspec.yaml", "name: app\nenvironment:\n  sdk: '>=3.4.0 <4.0.0'\ndependencies:\n  flutter:\n    sdk: flutter\n")
            write(root, "shop/shopify.app.toml", 'name = "x"\n[webhooks]\napi_version = "2025-07"\n')
            write(root, "plugin/my-plugin.php", "<?php\n/**\n * Plugin Name: My Plugin\n */\n")
            write(root, "site/wp-config.php", f"<?php define('DB_PASSWORD', '{db_password}');\n")
            write(root, "game/ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.0.23f1\n")
            write(root, "web/package.json", json.dumps({"dependencies": {"nuxt": "4.0.0", "vue": "3.5.0"}}))
            code, out, _ = run([str(root)])
            self.assertEqual(code, 0)
            self.assertNotIn(db_password, out)
            _, rep = report(root)
            self.assertEqual(project(rep, "app", "Dart")["stack"], "Dart (Flutter)")
            self.assertIn("flutter test", project(rep, "app", "Dart")["defaults"])
            self.assertEqual(versions(project(rep, "shop", "Shopify app"))["api_version"], "2025-07")
            project(rep, "plugin", "WordPress plugin")
            self.assertEqual(versions(project(rep, "game", "Unity"))["editor"], "6000.0.23f1")
            self.assertIn("Nuxt", project(rep, "web", "JavaScript")["frameworks"])
            self.assertFalse(any(p["path"] == "site" for p in rep["projects"]))


class CiAndRunnerTests(unittest.TestCase):
    def test_github_workflow_commands_versions_and_redaction(self):
        token = "ghp_" + "A1b2C3d4" * 5
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "go.mod", "module x\n\ngo 1.24\n")
            write(root, ".github/workflows/ci.yml",
                  "jobs:\n  test:\n    steps:\n      - uses: actions/setup-go@v5\n        with:\n"
                  "          go-version: '1.24'\n      - run: go test ./...\n      - name: lint\n        run: |\n"
                  "          golangci-lint run\n          go vet ./...\n"
                  f"      - run: curl -H 'Authorization: x' --data token={token} https://example.invalid\n"
                  f"      - run: ./deploy.sh {token}\n"
                  "      - run: echo ${{ secrets.API_TOKEN }}\n")
            code, out, _ = run([str(root)])
            self.assertEqual(code, 0)
            self.assertNotIn(token, out)
            _, rep = report(root)
            ci = rep["ci"][0]
            self.assertEqual(ci["file"], ".github/workflows/ci.yml")
            self.assertIn({"name": "go-version", "value": "1.24"}, ci["versions"])
            for cmd in ("go test ./...", "golangci-lint run", "go vet ./..."):
                self.assertIn(cmd, ci["commands"])
            self.assertIn("echo ${{ secrets.API_TOKEN }}", ci["commands"])
            self.assertNotIn(token, json.dumps(rep))

    def test_gitlab_jenkins_and_task_runners(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, ".gitlab-ci.yml", "test:\n  image: python:3.12\n  script:\n    - pip install -r requirements.txt\n    - pytest -q\n")
            write(root, "Jenkinsfile", "pipeline { stages { stage('t') { steps { sh 'make test' } } } }\n")
            write(root, "Makefile", ".PHONY: test lint\ntest:\n\tpytest\nlint: deps\n\truff check .\n%.o: %.c\n\tcc $<\nVAR := 1\n")
            write(root, "justfile", "set shell := [\"bash\", \"-c\"]\nbuild:\n    cargo build\ntest target='all':\n    cargo test\n")
            write(root, "Taskfile.yml", "version: '3'\ntasks:\n  build:\n    cmds:\n      - go build\n  test:\n    cmds:\n      - go test\n")
            code, rep = report(root)
            self.assertEqual(code, 1)  # no manifest, but CI and runners are still reported
            by_file = {c["file"]: c for c in rep["ci"]}
            self.assertIn("pytest -q", by_file[".gitlab-ci.yml"]["commands"])
            self.assertIn({"name": "image", "value": "python:3.12"}, by_file[".gitlab-ci.yml"]["versions"])
            self.assertIn("make test", by_file["Jenkinsfile"]["commands"])
            runner_cmds = [c["command"] for c in rep["task_runners_outside_projects"][0]["commands"]]
            self.assertEqual(runner_cmds, ["make test", "make lint", "just build", "just test", "task build", "task test"])

    def test_runner_commands_attach_to_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "go.mod", "module x\n\ngo 1.22\n")
            write(root, "Makefile", "check:\n\tgo vet ./...\n")
            _, rep = report(root)
            p = project(rep, ".", "Go")
            self.assertEqual(p["commands"][0], {"command": "make check", "source": "Makefile"})
            self.assertEqual(rep["task_runners_outside_projects"], [])


class SafetyAndCliTests(unittest.TestCase):
    def test_skips_dependency_folders_and_sensitive_files(self):
        secret = "sk_live_" + "x" * 24
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "go.mod", "module x\n\ngo 1.22\n")
            write(root, "node_modules/left-pad/package.json", json.dumps({"name": "left-pad"}))
            write(root, "vendor/lib/composer.json", json.dumps({"require": {"php": "^7.4"}}))
            write(root, ".env", f"STRIPE_KEY={secret}\n")
            write(root, ".venv/lib/pyproject.toml", "[project]\n")
            code, out, _ = run([str(root)])
            self.assertEqual(code, 0)
            self.assertNotIn(secret, out)
            _, rep = report(root)
            self.assertEqual([(p["path"], p["stack"]) for p in rep["projects"]], [(".", "Go")])

    def test_max_depth_limits_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "services/billing/go.mod", "module billing\n\ngo 1.22\n")
            code, rep = report(root, "--max-depth", "1")
            self.assertEqual(code, 1)
            self.assertEqual(rep["projects"], [])
            code, rep = report(root, "--max-depth", "2")
            self.assertEqual(code, 0)
            self.assertEqual(rep["projects"][0]["path"], "services/billing")

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run([tmp])
            self.assertEqual(code, 1)
            self.assertIn("No known manifest", out)
            code, _, err = run([os.path.join(tmp, "missing")])
            self.assertEqual(code, 2)
            self.assertIn("not a directory", err)
            code, _, _ = run([tmp, "--no-such-flag"])
            self.assertEqual(code, 2)
            code, _, _ = run([tmp, "--max-depth", "-1"])
            self.assertEqual(code, 2)

    def test_json_is_deterministic_and_uses_given_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "go.mod", "module x\n\ngo 1.22\n")
            write(root, "web/package.json", json.dumps({"scripts": {"build": "vite build"}}))
            first = run([str(root), "--json"])[1]
            second = run([str(root), "--json"])[1]
            self.assertEqual(first, second)
            self.assertEqual(json.loads(first)["root"], str(root))

    def test_help_runs_as_a_script(self):
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Exit status", result.stdout)


if __name__ == "__main__":
    unittest.main()
