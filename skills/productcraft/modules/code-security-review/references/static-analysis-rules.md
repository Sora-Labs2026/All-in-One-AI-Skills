# Static analysis: scans that mean something, and rules you can trust

Read this when a scanner is part of the audit (phase 3), when scanner output needs triage, or when a confirmed finding should become a rule that stops it coming back (phase 7). Scanner results are leads. Nothing in this file turns a match into a finding; [triage](triage-and-false-positives.md) and phase 5 do that.

## Pick the tool for the question

| Question | Tool | Why |
|---|---|---|
| Does this exact string, call or name appear anywhere? | `rg` or `git grep` | Seconds, no setup, works on any file |
| Does this call appear with this argument shape (string-built, missing wrapper, wrong flag)? | Semgrep pattern rule | Matches syntax trees, so formatting and names do not matter; works on code that does not build |
| Does a value from a request reach this call inside one function? | Semgrep taint rule | Follows assignments and sanitizers within a function (the open-source engine stops at function boundaries) |
| Does it get there across functions, files and libraries? | CodeQL | Interprocedural data flow with models of common frameworks; needs a database built from the code |
| Is a GitHub Actions workflow unsafe? | `code_audit.py workflows`, `supply_chain.py actions`, actionlint if installed | Workflow-specific checks; see [CI and agent workflows](ci-agent-workflows.md) |

Use them in that order: cheap searches show where to aim, rules confirm the shape, data flow shows reachability. A tool that is not installed makes its check `NOT_VERIFIED`; do not install from the network without approval.

## Before you trust a scan

1. **Keep code on the machine.** Pass `--metrics=off` to every Semgrep command. Registry rule sets (`--config p/...`) are downloaded, which needs the network and approval; local rule files do not. `--config auto` needs metrics and the network, so prefer named rule sets. Never upload code to a hosted analysis service without the owner's approval.
2. **Prove the scan can see.** Before reading "0 results" as good news, check what was analyzed:
   - Semgrep prints how many files it scanned; with `--json` the result lists scanned and skipped paths and parse errors. Files above the size limit (`--max-target-bytes`), `.semgrepignore` and `.gitignore` entries are skipped silently unless you look.
   - CodeQL: compare the extracted source count with the repository (`unzip -l <db>/src.zip | tail -1` against `git ls-files '*.py' | wc -l`), look at `codeql database print-baseline <db>`, and export diagnostics with `codeql database export-diagnostics <db> --format=sarif-latest --output=security/codeql-diagnostics.sarif`. A compiled-language database built from a cached or failed build can contain almost nothing and still analyze without error.
3. **Run a positive control.** Copy one known-bad snippet (a confirmed finding, or a two-line sample of the pattern) into a scratch directory outside the repository and run the same command on it. No hit there means the rule, language detection or configuration is wrong, and every clean result from that run is void.
4. **Record what ran:** tool version (`semgrep --version`, `codeql version`), rule files or query packs and their versions, target paths, flags, files analyzed, and the exit status. These go in the verification log.

## Running Semgrep

```bash
semgrep --version
# Project rules, offline
semgrep scan --metrics=off --config security/semgrep/ --sarif --output security/semgrep.sarif .
# A registry rule set (downloads rules: ask first)
semgrep scan --metrics=off --config p/default --sarif --output security/semgrep-registry.sarif .
# Branch review: only results that are not present at the merge base
semgrep scan --metrics=off --config security/semgrep/ --baseline-commit "$(git merge-base origin/main HEAD)" .
```

## Running CodeQL

```bash
codeql version
codeql resolve languages                      # what this CLI can extract
# Interpreted languages need no build
codeql database create security/codeql-db --language=python --source-root . --overwrite
# Compiled languages: give it the real build, or build-mode=none where your version supports it
codeql database create security/codeql-db --language=java --command "./gradlew --no-daemon clean compileJava" --overwrite
codeql database analyze security/codeql-db \
  codeql/python-queries:codeql-suites/python-security-extended.qls \
  --format=sarif-latest --output=security/codeql.sarif
```

- Query packs such as `codeql/python-queries` ship with the CodeQL bundle; with a bare CLI they must be downloaded (`codeql pack download`), which needs the network.
- Name the suite explicitly. `<lang>-security-extended.qls` runs more security queries than the default suite at the price of more noise; `<lang>-security-and-quality.qls` adds code-quality queries.
- Sources are remote input (HTTP and similar) by default. For CLIs, desktop apps and workers that read files or environment variables an attacker controls, add `--threat-model local` (support grows by language and release; check `codeql database analyze --help`).
- `build-mode=none` (available for some compiled languages in recent releases) extracts without building and misses code generated or selected at build time. Say so in the report.
- Keep databases out of the repository (`security/` should be ignored or local) and delete them when the audit ends; they contain the source.

## From SARIF to leads

```bash
python3 <productcraft>/modules/code-security-review/scripts/sarif_triage.py summary \
  --sarif security/semgrep.sarif --sarif security/codeql.sarif --root .
python3 <productcraft>/modules/code-security-review/scripts/sarif_triage.py diff \
  --sarif security/codeql.sarif --baseline security/codeql-main.sarif --root .
python3 <productcraft>/modules/code-security-review/scripts/sarif_triage.py leads \
  --sarif security/semgrep.sarif --sarif security/codeql.sarif --root . \
  --out security/sast-leads.json --repository <name> --revision "$(git rev-parse --short HEAD)"
python3 <productcraft>/modules/code-security-review/scripts/code_audit.py findings --file security/sast-leads.json
```

- `summary` resolves each result's level the way SARIF defines it. CodeQL leaves the level off its results and puts it on the rule; a script that reads only the result's level reports a CodeQL run as clean.
- `diff` shows what a branch added, matching by fingerprint when the tool wrote one.
- `leads` writes one `POSSIBLE` lead per distinct rule, file and line, notes when two tools flagged the same line, and drops suppressed results and paths outside the repository (it counts them). Snippets are never copied and token-shaped strings are redacted.
- Scanner level and the rule's `security-severity` describe the rule, not this occurrence. Severity comes from phase 6 after the lead is confirmed.
- Agreement between two tools raises the priority of a lead. It is not proof.
- On a large result set, take a first pass over what the rules themselves rate highly: `leads --min-level error`, or `--min-security-severity 7` for tools that score their rules (CodeQL does; rules without a score are kept). Import the rest afterwards; a first pass is not coverage.
- Move each confirmed lead into `security/code-audit-findings.json` with full evidence; keep rejected ones as `FALSE_POSITIVE` with `rejection_reason` so the next run does not re-raise them.

## Suppress narrowly, with a reason

| Tool | Narrowest suppression | Use for |
|---|---|---|
| Semgrep | `# nosemgrep: <rule-id>` on the reported line, with a comment saying why | A reviewed false positive at one site |
| Semgrep | `.semgrepignore` path entry | Generated, vendored or fixture code that never ships |
| CodeQL | A model that marks the project's sanitizer or validator (see below), or a suite `exclude` for a query that does not fit the project | Systematic false positives with one cause |
| Both | `FALSE_POSITIVE` entry in the findings file | The audit record, whatever the tool |

Never make CI green by deleting a rule, widening ignore paths over real code, or lowering the gate. A suppression without a reason is a finding for the next reviewer.

## Writing a Semgrep rule

Write one when a confirmed finding has a recognizable shape, when the project has its own unsafe wrapper, when an API must be banned, or when a [variant hunt](variant-analysis.md) needs a structure-aware search.

**1. Write the defect and its safe form in two sentences.** "Request values reach `db.raw()` in string-built SQL. The safe form is `db.query(sql, params)` or an integer conversion first."

**2. Write the test file first.** Semgrep's test format puts an annotation comment on the line directly above the code it labels: `ruleid: <id>` must match, `ok: <id>` must not. Cover at least two vulnerable forms and at least two safe ones, and always include the project's own correct idiom, because that is the false positive a new rule most often produces. Add a constant input, a sanitized input, a call inside a branch or loop, and a look-alike call that is unrelated.

```python
# security/semgrep/shop-raw-sql-from-request.py
from flask import request
import db

def search():
    term = request.args.get("q")
    # ruleid: shop-raw-sql-from-request
    db.raw(f"SELECT * FROM items WHERE name = '{term}'")

def purge():
    body = request.get_json()
    if body:
        # ruleid: shop-raw-sql-from-request
        db.raw("DELETE FROM items WHERE owner = '" + body["owner"] + "'")

def search_bound():
    term = request.args.get("q")
    # ok: shop-raw-sql-from-request
    db.query("SELECT * FROM items WHERE name = %s", [term])

def by_id():
    item_id = int(request.args.get("id"))
    # ok: shop-raw-sql-from-request
    db.raw(f"SELECT * FROM items WHERE id = {item_id}")

def count():
    # ok: shop-raw-sql-from-request
    db.raw("SELECT count(*) FROM items")
```

**3. Look at the tree Semgrep sees** when a pattern does not match as expected: `semgrep --dump-ast --lang python security/semgrep/shop-raw-sql-from-request.py`. Patterns follow the syntax tree, not the text.

**4. Write the rule.** Use taint mode when the question is "does untrusted data get here", and a pattern rule when the shape alone is the defect.

```yaml
# security/semgrep/shop-raw-sql-from-request.yaml
rules:
  - id: shop-raw-sql-from-request
    languages: [python]
    severity: ERROR
    message: >-
      Request data reaches db.raw() in a string-built query. Use db.query() with
      bound parameters, or convert the value to int first.
    metadata:
      cwe: "CWE-89"
      confidence: HIGH
      origin: "CSR-004 in security/code-audit-report.md"
    mode: taint
    pattern-sources:
      - pattern: flask.request.args.get(...)
      - pattern: flask.request.form.get(...)
      - pattern: flask.request.get_json(...)
    pattern-sanitizers:
      - pattern: int(...)
    pattern-sinks:
      - patterns:
          - pattern: db.raw($SQL, ...)
          - focus-metavariable: $SQL
```

**5. Test until every case passes, then simplify and test again.**

```bash
semgrep scan --metrics=off --validate --config security/semgrep/shop-raw-sql-from-request.yaml
semgrep --test security/semgrep/                     # rule and test file share a base name
semgrep scan --metrics=off --dataflow-traces --config security/semgrep/shop-raw-sql-from-request.yaml \
  security/semgrep/shop-raw-sql-from-request.py      # why taint did or did not flow
```

"Missed" lines mean the rule is narrower than the defect; "incorrect" lines mean it is broader. Change the rule, never the expected annotations, unless the test case itself was wrong. Pass means all cases pass, not most.

**6. Measure precision on the real repository.** Run the rule over the whole tree and read every hit. Write down hits, true and false. A rule may block merges only if every hit you checked was real and you checked all of them (or a large sample); a rule with occasional noise can run as an advisory comment; a noisy rule stays a search tool for audits.

**7. Finish the rule.** The message says what is wrong and what to do, and contains no metavariable that the pattern does not bind. Metadata carries the CWE, confidence and the finding that motivated it. Keep rules and their tests under `security/semgrep/` (or the project's existing folder) and run `semgrep --test` in CI so rules do not rot. Propose the CI change; do not push it.

### Porting a rule to another language

1. Confirm the defect exists there: is there an equivalent source, sink and sanitizer? (`fmt.Sprintf` into `db.Query` in Go: yes. Prototype pollution in Go: no.) A port of a construct that has no risk in the target language is noise.
2. Write the target language's test file first, starting with its idiomatic safe form (`db.Query("... WHERE id = $1", id)`).
3. Dump the target's syntax tree and write patterns against it; do not transliterate the original's patterns.
4. Give the port its own id (`shop-raw-sql-from-request-go`) and a `ported-from` metadata entry, and run `semgrep --test` with the same Semgrep version as the original.
5. If Semgrep cannot parse the language well enough to run the tests, record the port as `NOT_VERIFIED`, not as done.

## Teaching CodeQL about the project

**Prefer models to new queries.** Most missed flows come from project wrappers the shipped models do not know: a custom request object, a database helper, a command runner. Describe them as data extensions and the built-in queries start covering them. Java and C# models list package, type, method and the argument or return value; Python, JavaScript and Ruby use a shorter access-path form. Copy the column layout from the CodeQL documentation for your version.

```yaml
# security/codeql/models/shop.model.yml  (Java)
extensions:
  - addsTo:
      pack: codeql/java-all
      extensible: sourceModel
    data:
      - ["com.shop.http", "Req", true, "param", "(String)", "", "ReturnValue", "remote", "manual"]
  - addsTo:
      pack: codeql/java-all
      extensible: sinkModel
    data:
      - ["com.shop.db", "RawSql", true, "execute", "(String)", "", "Argument[0]", "sql-injection", "manual"]
```

```yaml
# security/codeql/qlpack.yml
name: shop/java-models
version: 0.0.1
library: true
extensionTargets:
  codeql/java-all: "*"
dataExtensions:
  - models/*.model.yml
```

```bash
codeql database analyze security/codeql-db codeql/java-queries:codeql-suites/java-security-extended.qls \
  --additional-packs=security/codeql --model-packs=shop/java-models \
  --format=sarif-latest --output=security/codeql.sarif
```

Before writing models, see what CodeQL already recognizes: a three-line query in a small pack that depends on `codeql/python-all` (or the language's library pack) lists every remote source in the database, and a project wrapper missing from that list needs a model.

```ql
import python
import semmle.python.dataflow.new.RemoteFlowSources
from RemoteFlowSource src select src, src.getSourceType()
```

Run it with `codeql query run --database=security/codeql-db list-sources.ql`. Check a model with a positive control: the confirmed finding that motivated it must now appear in the results.

**Write a query** only for a property models cannot express (an authorization rule, a forbidden call order). Give it metadata (`@kind`, `@id`, `@precision`, `@tags security external/cwe/cwe-NNN`) and a test directory containing sample code with good and bad cases, a `.qlref` file naming the query, and the expected results file. `codeql test run <test-dir>` compiles the sample, runs the query and shows the difference from the expected file. Accept new output (`codeql test accept`) only after reading every changed line.

## Done when

- Every scan in the report names the tool and rule versions, the target, the files analyzed, and whether a positive control matched.
- A zero-result scan states what it could see; a scan that could not see the code is `NOT_VERIFIED`.
- Every scanner result is a lead in `security/sast-leads.json` or the findings file, or is counted as suppressed with a recorded reason.
- Each new rule has at least two matching and two non-matching test cases, including the project's safe idiom; its tests pass; its precision on the repository is written down; and its CI use matches that precision.
