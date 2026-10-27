# Changelog

## ProductCraft 1.8.0 (2026-10-27)

- Ten new modules, each with a `GUIDE.md`, focused references and tested standard-library helpers, reached through the router only when a task needs them:
  - **Stacks:** guides for Python, Django, FastAPI, Go, Rust, Java and Spring, Kotlin, C# and .NET, C++, PHP and Laravel, Ruby and Rails, Swift, React, Next.js, Vue and Nuxt, Angular, NestJS, React Native and Expo, Flutter, GraphQL, realtime, WordPress, Shopify, HTML email, game engines, firmware, Salesforce and CLI tools, plus system design and legacy modernization. `detect_stack.py` reports stacks, versions and the project's own commands.
  - **Cloud infrastructure:** Terraform and OpenTofu, AWS CDK and serverless AWS, Azure modules, machine images, Kubernetes, containers, GPU and static hosting, pipelines, cost, architecture, SRE, monitoring and chaos engineering, under a plan-and-diff-only rule. `plan_review.py` reviews plan JSON.
  - **Data engineering:** SQL tuning, PostgreSQL, MySQL and SQL Server, safe database access, pandas, Polars, DuckDB, Dask and Spark, storage formats, EDA, charts and publication figures, geospatial and graph data, MATLAB interop, Kaggle and public statistics, filings and market data. `csv_profile.py` profiles delimited files offline.
  - **ML engineering:** leakage-safe evaluation, classical and deep learning, explainability, forecasting and time series, graph networks, fine-tuning, reinforcement learning, statistical inference and Bayesian models, MLOps, recommenders, RAG, prompts inside products and LLM evaluation. `split_check.py`, `compare_scores.py` and `rank_metrics.py`.
  - **Scientific computing:** solvers, time integration and stability, meshes, verification and convergence studies, parameter studies, Slurm and profiling, and scientific and quantum-computing libraries. `resource_check.py` and `convergence_order.py`.
  - **Life sciences:** sequences, variants, intervals, single-cell and bulk expression, phylogenetics, proteins, cheminformatics, mass spectrometry and metabolic models; public biological, chemical and clinical databases with their license terms; medical imaging, de-identification, physiological signals, EHR models, clinical document drafts, medical-device quality systems, lab automation and lab data platforms. `interval_check.py`, `counts_check.py`, `bio_id_check.py` and `dicom_phi_check.py`.
  - **Research writing:** literature search and systematic reviews, scholarly APIs, verified citations, appraisal, hypotheses, scientific papers and reporting checklists, peer review, grants, plan stress tests, diagrams, posters, talks, paper pages and everyday writing. `bib_check.py` checks BibTeX.
  - **Creative media:** generative art, posters, infographics, themes, reveal.js, programmatic video, prompting generation models with likeness and labeling rules, image enhancement, EPUB and file and invoice organization. `organize_plan.py` plans moves without touching files.
  - **Integrations:** OAuth and tokens, webhooks, reliability and contract tests, with Stripe, Plaid, Supabase, Google Workspace, Jira, Confluence, Linear, Outline and membership platforms. `integration_scan.py` finds risky integration code.
  - **Blockchain development:** Move on Aptos (language, objects and tokens, tests and the Move Prover, gas, CLI, SDK and wallets, indexer) and Solana RPC. `move_check.py` finds risky packages and key files.
- Engineering workflow: requirements workshops with acceptance criteria, complete deliverables without placeholder code, Markdown task boards, delegating tasks to hosted coding agents with outside-PR review, and grouping related test failures by root cause while debugging.
- Engineering practices: combinatorial and pairwise test design in the advanced-testing reference.
- Builder tools: linting agent configuration and finding, importing and updating skills safely.
- Code security review: authorized dynamic web testing and captured HTTP traffic, with `har_summary.py`, which never prints the values it finds.
- Codebase map: map-reduce over very large repositories with parallel helpers.
- Documents: converting documents to Markdown.
- The router, the package checker and CI cover all 21 guided modules; the suites hold 754 tests.

## ProductCraft 1.7.0 (2026-10-25)

- Code security review:
  - New references: entry points and context notes; static analysis (running Semgrep and CodeQL so results mean something, writing and testing rules and models); variant analysis; triage of outside reports and scanner leads; insecure defaults and misuse-prone APIs; supply-chain review (install-time code, dependency risk cards, compromise response, release integrity); CI workflows that run AI agents or react to outsiders; patch validation. Language pitfalls gain a C# and .NET section.
  - Domain guides, read only for matching code: C and C++ memory safety (bug classes, sanitizer builds, hardened compiler and linker flags and how to see them in a binary), Rust (`unsafe` soundness, FFI, panics, integer behavior, async cancellation), cryptographic implementation (home-made constructions, timing side channels, wiping secrets, randomness), smart contracts (invariants, token integration, upgradeable proxies, Foundry fuzz, invariant and fork tests, other chains), mobile apps and their backends (APK and IPA review, hardcoded keys, Firebase and Supabase rules with emulator tests, deep links) and defensive YARA rule authoring.
  - New helpers: `supply_chain.py` (GitHub Actions trust flows and agent steps, ten lockfile formats), `sarif_triage.py` (SARIF summary, baseline diff, leads in the findings format) and `firebase_rules.py` (open, test-mode, signed-in-only and unvalidated-write rules), with 58 tests.
- Engineering practices:
  - Advanced testing (property-based and model-based tests with shrinking and replay; mutation testing with mutmut, Stryker, cargo-mutants and PIT; differential and metamorphic checks; known-answer vectors), fuzzing parsers and native code (Go's built-in fuzzing, cargo-fuzz, Atheris, libFuzzer and AFL++ with sanitizers), and specification compliance and unit-of-measure checks.
  - Preparing a repository for public release, repository and issue hygiene, and `oss_readiness.py`, a read-only open-source readiness check with 33 tests.
  - A whole-repository health audit with proven, ranked findings and no code changes; design docs, specs and proposals written with the user; improving the project's setup after a session; request chains and component re-renders in the performance reference.
- Engineering workflow: a reference for reviewing someone else's change; long plans can run one fresh helper per step, with a review after each step and one whole-branch review; questions only a third party can answer go into a short questionnaire.
- Reports on consequential work end with up to three specific things for the user to double-check (an assumption, a fact that could not be confirmed, a check only the user can do), each with how to confirm it. `assets/review-template.md` gains the section, and lean output keeps it.
- Agent safety: isolating the agent in a devcontainer, container or VM (`references/isolation.md`) and guided setup scripts the user runs, so secret values never pass through the conversation (`references/guided-setup.md`). `guard_command.py` 1.1.0 checks literal commands inside awk `system()` calls and command pipes (new rule `AWK-EXEC` asks about commands built at runtime) and GNU `parallel` templates and command inputs.
- Codebase map: `map_codebase.py` 1.1.0 adds a repeatable `--exclude PATTERN`; the JSON `stats` gain `exclude` and `excluded_paths` (schema version unchanged). New query recipes: the import chain between two files and a directory-level Mermaid diagram.
- Documents: animated GIFs and short clips with Pillow and ffmpeg (`references/animated-media.md`), including size budgets, a flash-rate check and accessibility rules.
- Builder tools: skill descriptions without procedures, instructions written against the failure seen in a baseline run, pressure and missing-detail prompts, cheap wording samples with a no-instruction control, and a check for web fonts that failed to load before screenshots.
- Data surfaces: choose the chart form from the question it answers.
- Legal ready: an example offline end-to-end test that fails when a non-essential third party, cookie or storage key appears before consent or after "Reject all".
- The router reaches every new reference; the suites hold 342 tests in total.

## ProductCraft 1.6.0 (2026-10-25)

- UI rulebook: 294 rules (9 new), with 165 existing rules made more concrete or corrected. Existing rule IDs are unchanged; four titles were corrected (FBK-11, ICO-03, ICO-08, COP-08).
  - Concrete defaults throughout: one timing scale for feedback (about 100 ms, 300-400 ms, 1 s), press feedback within about 100 ms, spring damping guidance, hit-area math, contrast floors for inactive labels, icons, input borders and status text, and paired fill and text tokens.
  - Corrections include: password checklists cover only length and breached-password checks (NIST SP 800-63B); one-time codes prefer a single real input; dark-mode text tiers are white alpha over the surface; tooltips follow WCAG 1.4.13 and use long press or a toggletip on touch; optimistic updates are allowed for low-risk actions with visible rollback; top-level tabs switch instantly or fade through; numbers never count up from zero; sign-in errors use one generic message.
  - New rules: LAY-17 translation and right-to-left, NAV-18 keep the user's place in long lists, FBK-21 optimistic updates with rollback, FBK-22 lost connections and retry, FBK-23 time-limited decisions, CMP-33 drag and drop, ICO-12 no emoji as interface icons, SCR-26 inline AI output, MOT-21 flash limits (WCAG 2.3.1).
- Pattern library: all 69 patterns gain a "Specifics" list with default values, keyboard and screen-reader behavior, reduced-motion handling and edge cases; two patterns get corrected rule or guardrail text.

## ProductCraft 1.5.0 (2026-10-25)

- New modules, each with a `GUIDE.md`, focused references and tested standard-library scripts:
  - **Engineering workflow**: Quick, Standard and Deep tracks; done-when checks, planning, test-first, root-cause debugging, change discipline, verification, review, parallel work and finishing a branch. `diff_scope.py` self-checks a diff.
  - **Engineering practices**: API contracts, data and safe migrations, resilience, performance, observability, CI/CD and releases, dependencies, docs and ADRs, large refactors, TypeScript, git and pull requests, session handoff. `migration_check.py` flags risky SQL migrations.
  - **Code security review**: a multi-phase audit with threat modeling, vulnerability classes mapped to OWASP Top 10 and CWE, bugs typical of AI-written code, language pitfalls, secrets and dependencies, and fix-and-verify. `code_audit.py` ranks files, scans history for secrets without printing them and validates findings.
  - **Legal ready**: 20 launch legal-readiness items with concrete implementation steps, an owner questionnaire and a report template; general guidance, not legal advice. `legal_scan.py` checks a project for signals.
  - **Agent safety**: a stop-check before destructive commands, secrets by name only, and vetting of third-party skills, plugins, MCP servers and hooks. `guard_command.py` works as an opt-in pre-tool hook; `scan_skill.py` scans extensions before install.
  - **Codebase map**: `map_codebase.py` maps entry points, routes, the import graph, symbols and hotspots of an unfamiliar repository.
  - **Documents**: Word, Excel, PowerPoint and PDF work with open-source tools and render-based verification. `ooxml_inspect.py` checks Office files.
  - **Builder tools**: authoring and evaluating Agent Skills, designing and testing MCP servers, Playwright browser tests. `lint_skill.py` checks a skill folder.
  - **Lean output**: opt-in shorter answers that never shorten safety warnings, security findings, errors or legal caveats.
- UI Distiller gains taste detectors against generic generated-looking UI and a catalog of 14 visual directions with contrast-checked palettes and freely licensed font pairings.
- Reference screens grow to 44 pages with 165 screens: dashboards v4 to v16 (finance, CRM, learning, property, admin, credit, creator, fitness, smart home, logistics, energy, accounts payable, clinical monitoring), new landing, search, data table and menu/overlay pages, and v7 to v12 of cards, charts, buttons, form controls, sign-in and onboarding. The README galleries show all 16 dashboards in their own section.
- The example tokens move from a stock indigo to the Sora brand blues, and two purple gradients are replaced; every page still passes the contrast audit.
- `SKILL.md` routes to all new modules; the package checker requires every guided module, and CI runs every module's tests (231 tests in total).

## ProductCraft 1.4.0 (2026-10-24)

- Added reference screens in `examples/`: 21 original pages with 92 screens covering dashboards (three versions), sign-in and account access, verification codes and PINs, security settings, navigation, tab bars, charts, cards, calendars, buttons, form controls, feedback, commerce, pricing, mobile apps, messaging and assistants, onboarding and error states, and brand guidelines. Each page is self-contained HTML and CSS with shared `tokens.css`, cites the rule IDs it applies and passes a WCAG AA contrast check. `examples/README.md` indexes every version.
- The router and `modules/ui-rules.md` point agents at the matching reference screen as code to adapt with the project's own components and tokens, not as a theme to copy.
- `check_package.py` and a new test verify that every page is listed in the index, has `lang`, a title and a viewport, loads nothing external and cites only real rule IDs.
- The repository README and the ProductCraft README show a gallery of the screens. `scripts/screenshots.cjs` regenerates the screenshots in `docs/screens/`.

## ProductCraft 1.3.0 (2026-10-24)

- Expanded the UI rulebook to 285 rules in 18 categories. New categories: `MOT` motion and animation, `ENG` front-end engineering and `BRD` brand identity. Existing categories gained rules for one-time codes, sign-in fields, uploads, async button states, honest progress, KPI tiles, charts, tables, carousels, expandable search, collapsible sidebars, checkout, paywalls, error pages and more. Existing rule IDs are unchanged.
- Added `modules/language-choice.md`: for a new project, service or performance-critical component whose language is not fixed, ProductCraft asks once whether to use Rust, states the trade-offs (faster runtime, slower compiles, more AI tokens, no automatic page-load gain), and remembers the answer.

## ProductCraft 1.2.0 (2026-10-23)

- Added the UI rulebook: `modules/ui-rules.md` routes to 146 screen-level rules in 15 category files under `references/ui-rules/`, with a machine-readable index. Every rule has an ID (for example `BTN-02`), why it matters, what to do and what to avoid.
- The router sends screen-level visual work (spacing, type, color, dark mode, buttons, form fields, navigation, icons, microcopy, settings, dashboards) to the matching rule categories, and change reports cite UI rule IDs.
- `check_package.py` validates the rulebook (unique, consecutive IDs, required fields, every rule present in its category file).

## ProductCraft 1.1.0 (2026-10-23)

- Added the LaunchGuard 20-control security baseline (`modules/launchguard/references/security-baseline.md`). Each control lists its gate, what to do, the common trap and how to verify it.
- The router now runs a scoped check of the matching baseline controls when a change touches API routes, data access, queries, uploads, cookies, headers or dependencies, without a full launch review.
- The LaunchGuard report template and release checklist include a status table for all 20 controls.
- Scanner 1.1.0 adds two rules, `INSECURE_COOKIE_FLAG` and `WEAK_PASSWORD_HASH`, with tests.

## ProductCraft 1.0.0 (2026-10-23)

- First release: router, six design and UX modules, UI/UX pattern library, and the UI Distiller, Credential Shield and LaunchGuard modules.
- Released under the MIT License.
