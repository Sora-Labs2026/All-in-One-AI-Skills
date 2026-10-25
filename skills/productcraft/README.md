# ProductCraft

**A Sora Labs Agent Skill** · version 1.6.0 · MIT License · part of [All-in-One AI Skills](../../README.md)

ProductCraft is one installable skill that teaches a coding agent to build, harden and ship software that **shows the important thing first, behaves honestly, is proven by checks that actually ran, works on every device, and is secure and lawful where it matters**. It routes each task to only the modules that task needs: a bug fix reads the engineering workflow, a table change reads the table guidance, an auth change reads the auth-defense module, a destructive command triggers the agent-safety stop-check, and a launch reads the security and legal-readiness reviews.

It is a working skill for real codebases, not a theme pack, legal service or security certification. Its reference screens are code to learn from, not a component kit to paste. The agent changes your real codebase and reports what it actually tested.

## What's inside

| Module | Use it for | Entry file |
|---|---|---|
| **Engineering workflow** | Any non-trivial code change: Quick/Standard/Deep tracks, done-when checks, planning, test-first, root-cause debugging, small diffs, verification, review, finishing a branch | `modules/engineering-workflow/GUIDE.md` |
| **Engineering practices** | API contracts, data and safe migrations, resilience, performance, observability, CI/CD and releases, dependencies, docs and ADRs, large refactors, TypeScript, git and PRs, session handoff | `modules/engineering-practices/GUIDE.md` |
| **UI Distiller** | New screens, redesigns, cleaning up cluttered or "AI-looking" frontends, with taste detectors and a catalog of visual directions with contrast-checked palettes | `modules/ui-distiller/GUIDE.md` |
| **Product design** | Information hierarchy, tokens, spacing, density, Keep/Promote/Compress/Demote/Remove audits | `modules/product-design.md` |
| **Interaction & feedback** | Buttons, switches, sliders, drag and drop, modals, toasts, motion, optimistic vs. verified state | `modules/interaction-feedback.md` |
| **Forms & conversion** | Signup, OTP, passwords, search, uploads, checkout and payment UI | `modules/forms-conversion.md` |
| **Data & product surfaces** | Tables, dashboards, calendars, Kanban, chat, command palettes | `modules/data-and-product-surfaces.md` |
| **Responsive & accessibility** | Mobile layouts, touch targets, sheets vs. dialogs, keyboard, screen readers, i18n and RTL | `modules/responsive-accessibility.md` |
| **Ethical persuasion** | Funnels, copy and engagement without fake urgency, fake social proof or hidden fees | `modules/ethical-persuasion.md` |
| **Credential Shield** | Login, OTP/MFA, password reset, credential stuffing and password spraying defense | `modules/credential-shield/GUIDE.md` |
| **Code security review** | Multi-phase code audit: threat model, vulnerability classes mapped to OWASP and CWE, bugs typical of AI-written code, language pitfalls, secrets and dependencies, proven findings and tested fixes | `modules/code-security-review/GUIDE.md` |
| **LaunchGuard** | Pre-launch five-gate security review plus a 20-control security baseline: secrets, user data, authorization, payments, release go/no-go | `modules/launchguard/GUIDE.md` |
| **Legal ready** | 20 launch legal-readiness items: privacy, terms, refund and cookie policies, consent, data minimization, trackers, dark patterns, hidden fees, fake reviews, unsupported claims, accessibility, business details, children's data, unsubscribe, asset licenses, data deletion. General guidance, not legal advice | `modules/legal-ready/GUIDE.md` |
| **Agent safety** | Stop-check before destructive commands, secrets handled by name only, vetting third-party skills, plugins, MCP servers and hooks; optional command guard | `modules/agent-safety/GUIDE.md` |
| **Codebase map** | Getting oriented in unfamiliar repositories: entry points, routes, import graph, symbols, hotspots | `modules/codebase-map/GUIDE.md` |
| **Documents** | Word, Excel, PowerPoint and PDF: create, edit with formatting intact, extract, convert, fill forms, verified by rendering | `modules/documents/GUIDE.md` |
| **Builder tools** | Authoring and evaluating Agent Skills, designing and testing MCP servers, Playwright browser tests | `modules/builder-tools/GUIDE.md` |
| **UI rules** | A rulebook of screen-level rules with IDs (spacing, type, color, dark mode, buttons, forms, navigation, touch, feedback, components, icons, copy, screens, motion, front-end engineering, brand identity) | `modules/ui-rules.md` |
| **Language choice** | Offers Rust for new projects, services or performance-critical components, with honest trade-offs, and remembers the answer | `modules/language-choice.md` |
| **Lean output** | Opt-in shorter answers that never shorten safety warnings, security findings, errors or legal caveats | `modules/lean-output.md` |
| **Pattern library** | One principle, one implementation rule and one guardrail for each UI/UX pattern | `references/pattern-library.md` |
| **Reference screens** | 44 original HTML pages with 165 screens: 16 dashboards plus auth, settings, navigation, search, charts, cards, tables, forms, overlays, feedback, commerce, pricing, landing pages, mobile, messaging, onboarding and brand | `examples/README.md` |

The pattern library covers foundations, feedback, forms, interaction, navigation, responsive layout, data views, conversion, safety and advanced patterns such as live presence, chat and view transitions. A machine-readable version is in `references/pattern-index.json`.

## How it activates

`SKILL.md` is the single entry point. Its router picks modules from what the task actually touches:

| The task involves | ProductCraft reads |
|---|---|
| Any non-trivial code change in any language | Engineering workflow |
| A bug, a failing or flaky test, a regression | Engineering workflow's debugging loop |
| APIs, schemas and migrations, performance, observability, CI/CD, dependencies, large refactors | The matching engineering-practices topic |
| A new UI, a redesign, or decluttering | UI Distiller + product design + UI rules |
| Spacing, type, color, dark mode, buttons, form fields, navigation, icons, microcopy | The matching UI rules categories |
| Controls, motion, toasts, modals | Interaction & feedback |
| Forms, signup, OTP, checkout, search | Forms & conversion |
| Tables, dashboards, calendars, Kanban, chat, uploads | Data & product surfaces |
| Mobile layout, translation, RTL | Responsive & accessibility |
| Funnels, conversion copy, engagement | Ethical persuasion |
| A security review or audit of code, including AI-written code | Code security review |
| Login abuse, MFA, password reset | Credential Shield |
| API routes, data access, queries, uploads, cookies, headers, dependencies | The matching LaunchGuard security-baseline controls |
| Launch, payments, user data, privileged operations | LaunchGuard |
| Launch legal readiness: policies, consent, trackers, prices and claims, email, children's data, licenses, data deletion | Legal ready |
| Destructive commands, secrets on disk, installing third-party skills, plugins, MCP servers or hooks | Agent safety |
| An unfamiliar or large repository | Codebase map |
| Word, Excel, PowerPoint or PDF files | Documents |
| Writing a skill, building an MCP server, Playwright tests | Builder tools |
| A new project, service or performance-critical component with no language fixed | Language choice (asks once about Rust) |
| A broad, ambiguous product task | Product design + interaction, then only what is relevant |

The security and legal modules are conditional. A copy or CSS tweak does not trigger a full audit, and a one-line fix stays on the Quick track.

## Install

### Claude Code (plugin marketplace)

```text
/plugin marketplace add Sora-Labs2026/All-in-One-AI-Skills
/plugin install productcraft@sora-labs-skills
```

### Copy into a project

```bash
git clone --depth 1 https://github.com/Sora-Labs2026/All-in-One-AI-Skills.git /tmp/sora-skills

# Claude Code
mkdir -p .claude/skills && cp -R /tmp/sora-skills/skills/productcraft .claude/skills/

# Codex and other agents that read .agents/skills
mkdir -p .agents/skills && cp -R /tmp/sora-skills/skills/productcraft .agents/skills/
```

Install it in one location only, so the skill doesn't trigger twice.

### ZIP upload to any coding-agent workspace

1. Download [`dist/productcraft.zip`](../../dist/productcraft.zip) and [`dist/PRODUCTCRAFT-WORKSPACE-SETUP-PROMPT.txt`](../../dist/PRODUCTCRAFT-WORKSPACE-SETUP-PROMPT.txt).
2. Upload the ZIP to your agent's workspace.
3. Paste the contents of the setup prompt. The agent inspects the archive, extracts it safely, installs it in the project-local skill directory, runs the package checks and adds the project rule below.

## Using it

Once installed, ProductCraft triggers on relevant work. You can also call it directly:

```text
Use productcraft to redesign the billing dashboard so the overdue invoices and the
"Send reminder" action are visible first on mobile and desktop.

Use productcraft to polish the settings screen: apply the UI rules for spacing, labels,
icons and navigation, and list the rule IDs you used.

Use productcraft on the signup and OTP flow: keep codes as strings, support paste and
autofill, and consult Credential Shield for the resend and verify endpoints.

Use productcraft to check this pull request against the security baseline and fix
any control it fails.

Use productcraft to prepare this app for launch. Run the LaunchGuard five gates and
write the report with PASS / FAIL / NOT_VERIFIED evidence.

Use productcraft to find out why the nightly export test fails only in CI, fix the
root cause and add a regression test.

Use productcraft to run a security review of the payments service and the code our
assistant generated last week; prove each finding before fixing it.

Use productcraft to get this store legally ready to launch in the EU and the US: cookie
consent, policies, unsubscribe links and a data deletion option.

Use productcraft to turn this CSV into a formatted Excel report with totals, then a
one-page PDF summary, and show me the rendered pages.

Use productcraft to build an MCP server for our ticketing API and test it.
```

### Optional persistent project rule

Add this to your project's `CLAUDE.md` or `AGENTS.md` so the agent keeps using ProductCraft on future work:

> For significant frontend creation/redesign, UI interaction changes, complex forms, tables, dashboards, mobile layouts, or workflow UX, invoke the project-local ProductCraft skill and selectively read the matching design and interaction modules. Prioritize essential content, remove unnecessary visual noise, preserve accessible keyboard/touch behavior and real async/error handling. Use ethically transparent conversion techniques only; never fake scarcity, typing, fees, progress, social proof or server confirmations. For changes to auth/OTP/password recovery, consult its bundled Credential Shield module. For release preparation and changes to privileged operations, money, user data or production security, consult its bundled LaunchGuard module and check the matching security-baseline controls, or run the full five-gate review when shipping. Never apply the whole pattern library or run a full security audit on trivial copy/CSS edits. Keep reports honest and do not modify production secrets, cloud policy, live data or deployments without explicit authorization. For a new project, service or performance-critical component whose language is not yet fixed, ask once whether to write it in Rust, stating the trade-offs (faster runtime, slower compiles, more AI tokens, no automatic page-load gain) per its language-choice module. For any non-trivial code change, follow its engineering-workflow module (done-when checks, test-first where it fits, root-cause debugging, verification before claiming done). Before destructive commands or installing third-party skills, plugins, MCP servers or hooks, follow its agent-safety module. Before launch, also work through its legal-ready module as general guidance, not legal advice.

## Built-in guardrails

- **Verified over optimistic.** Payments, bookings, deletions, privileged changes and entitlements show *pending* until the server or provider confirms them.
- **Honest persuasion only.** Fake scarcity, phantom typing, artificial countdowns, hidden fees and hard-to-cancel flows are treated as anti-patterns to remove.
- **Accessibility first.** Semantic elements, keyboard and touch parity, reduced motion and visible focus outrank aesthetic formulas such as 60/30/10 or the golden ratio.
- **No false passes.** Scanners are advisory. Security checks report `PASS`, `FAIL`, `NEEDS_REVIEW`, `NOT_APPLICABLE` or `NOT_VERIFIED`, and secrets are never printed.
- **Hands off production.** No changes to real secrets, live data, payment provider settings or deployments without explicit permission.

## UI rules

`modules/ui-rules.md` routes to a rulebook in `references/ui-rules/`, one file per category. Every rule has an ID such as `BTN-02` with why it matters, what to do and what to avoid, so change reports can cite exactly which rules were applied. Rules are expressed through the project's existing tokens and components, accessibility and platform guidelines always win, and the optional style treatments are used only when asked for.

| Prefix | Covers |
|---|---|
| `LAY` | Layout and spacing |
| `TYP` | Typography |
| `COL` | Color and contrast |
| `DRK` | Dark mode |
| `BTN` | Buttons and calls to action |
| `FRM` | Forms and inputs |
| `NAV` | Navigation |
| `MOB` | Mobile and touch |
| `FBK` | Feedback, loading and empty states |
| `CMP` | Components and design system |
| `ICO` | Icons and imagery |
| `COP` | Copy and microcopy |
| `PRN` | UX principles |
| `SCR` | Screen patterns |
| `STY` | Style options |
| `MOT` | Motion and animation |
| `ENG` | Front-end engineering |
| `BRD` | Brand identity |

## Reference screens

`examples/` holds 44 original reference pages with 165 screens, including 16 dashboards. Each page is plain HTML and CSS with no external requests, cites the rule IDs it demonstrates and passes a WCAG AA contrast check. The router points an agent at the page that matches its task. The agent studies the semantics, states and details, then rebuilds the pattern with the project's own components and tokens. [`examples/README.md`](examples/README.md) lists every page and version.

### Dashboards v1–v16

|   |   |   |   |
|---|---|---|---|
| <a href="../../docs/screens/dashboard-v1.jpg"><img src="../../docs/screens/thumbs/dashboard-v1.jpg" alt="v1 example screen"></a><br><b>v1</b> · Analytics · <a href="examples/dashboard-v1.html">HTML</a> | <a href="../../docs/screens/dashboard-v2.jpg"><img src="../../docs/screens/thumbs/dashboard-v2.jpg" alt="v2 example screen"></a><br><b>v2</b> · Operations (dark) · <a href="examples/dashboard-v2.html">HTML</a> | <a href="../../docs/screens/dashboard-v3.jpg"><img src="../../docs/screens/thumbs/dashboard-v3.jpg" alt="v3 example screen"></a><br><b>v3</b> · Store bento · <a href="examples/dashboard-v3.html">HTML</a> | <a href="../../docs/screens/dashboard-v4.jpg"><img src="../../docs/screens/thumbs/dashboard-v4.jpg" alt="v4 example screen"></a><br><b>v4</b> · Personal finance · <a href="examples/dashboard-v4.html">HTML</a> |
| <a href="../../docs/screens/dashboard-v5.jpg"><img src="../../docs/screens/thumbs/dashboard-v5.jpg" alt="v5 example screen"></a><br><b>v5</b> · Sales CRM · <a href="examples/dashboard-v5.html">HTML</a> | <a href="../../docs/screens/dashboard-v6.jpg"><img src="../../docs/screens/thumbs/dashboard-v6.jpg" alt="v6 example screen"></a><br><b>v6</b> · Learning · <a href="examples/dashboard-v6.html">HTML</a> | <a href="../../docs/screens/dashboard-v7.jpg"><img src="../../docs/screens/thumbs/dashboard-v7.jpg" alt="v7 example screen"></a><br><b>v7</b> · Property · <a href="examples/dashboard-v7.html">HTML</a> | <a href="../../docs/screens/dashboard-v8.jpg"><img src="../../docs/screens/thumbs/dashboard-v8.jpg" alt="v8 example screen"></a><br><b>v8</b> · Workspace admin · <a href="examples/dashboard-v8.html">HTML</a> |
| <a href="../../docs/screens/dashboard-v9.jpg"><img src="../../docs/screens/thumbs/dashboard-v9.jpg" alt="v9 example screen"></a><br><b>v9</b> · Credit score (dark) · <a href="examples/dashboard-v9.html">HTML</a> | <a href="../../docs/screens/dashboard-v10.jpg"><img src="../../docs/screens/thumbs/dashboard-v10.jpg" alt="v10 example screen"></a><br><b>v10</b> · Creator (dark) · <a href="examples/dashboard-v10.html">HTML</a> | <a href="../../docs/screens/dashboard-v11.jpg"><img src="../../docs/screens/thumbs/dashboard-v11.jpg" alt="v11 example screen"></a><br><b>v11</b> · Fitness · <a href="examples/dashboard-v11.html">HTML</a> | <a href="../../docs/screens/dashboard-v12.jpg"><img src="../../docs/screens/thumbs/dashboard-v12.jpg" alt="v12 example screen"></a><br><b>v12</b> · Smart home (dark) · <a href="examples/dashboard-v12.html">HTML</a> |
| <a href="../../docs/screens/dashboard-v13.jpg"><img src="../../docs/screens/thumbs/dashboard-v13.jpg" alt="v13 example screen"></a><br><b>v13</b> · Logistics · <a href="examples/dashboard-v13.html">HTML</a> | <a href="../../docs/screens/dashboard-v14.jpg"><img src="../../docs/screens/thumbs/dashboard-v14.jpg" alt="v14 example screen"></a><br><b>v14</b> · Grid forecast · <a href="examples/dashboard-v14.html">HTML</a> | <a href="../../docs/screens/dashboard-v15.jpg"><img src="../../docs/screens/thumbs/dashboard-v15.jpg" alt="v15 example screen"></a><br><b>v15</b> · Accounts payable · <a href="examples/dashboard-v15.html">HTML</a> | <a href="../../docs/screens/dashboard-v16.jpg"><img src="../../docs/screens/thumbs/dashboard-v16.jpg" alt="v16 example screen"></a><br><b>v16</b> · Clinic monitoring · <a href="examples/dashboard-v16.html">HTML</a> |

### Components and flows

|   |   |   |   |
|---|---|---|---|
| <a href="../../docs/screens/sign-in.jpg"><img src="../../docs/screens/thumbs/sign-in.jpg" alt="Sign-in example screen"></a><br><b>Sign-in</b> · split screen · <a href="examples/sign-in.html">HTML</a> | <a href="../../docs/screens/auth.jpg"><img src="../../docs/screens/thumbs/auth.jpg" alt="Account access example screen"></a><br><b>Account access</b> · v1–v5 · <a href="examples/auth.html">HTML</a> | <a href="../../docs/screens/auth-2.jpg"><img src="../../docs/screens/thumbs/auth-2.jpg" alt="Account access example screen"></a><br><b>Account access</b> · v6–v11 · <a href="examples/auth-2.html">HTML</a> | <a href="../../docs/screens/otp.jpg"><img src="../../docs/screens/thumbs/otp.jpg" alt="Codes and PINs example screen"></a><br><b>Codes and PINs</b> · 6 versions · <a href="examples/otp.html">HTML</a> |
| <a href="../../docs/screens/settings.jpg"><img src="../../docs/screens/thumbs/settings.jpg" alt="Settings example screen"></a><br><b>Settings</b> · security page · <a href="examples/settings.html">HTML</a> | <a href="../../docs/screens/navigation.jpg"><img src="../../docs/screens/thumbs/navigation.jpg" alt="Navigation example screen"></a><br><b>Navigation</b> · 5 versions · <a href="examples/navigation.html">HTML</a> | <a href="../../docs/screens/tab-bars.jpg"><img src="../../docs/screens/thumbs/tab-bars.jpg" alt="Tab bars example screen"></a><br><b>Tab bars</b> · 5 + spec · <a href="examples/tab-bars.html">HTML</a> | <a href="../../docs/screens/search.jpg"><img src="../../docs/screens/thumbs/search.jpg" alt="Search example screen"></a><br><b>Search</b> · 6 versions · <a href="examples/search.html">HTML</a> |
| <a href="../../docs/screens/charts.jpg"><img src="../../docs/screens/thumbs/charts.jpg" alt="Charts example screen"></a><br><b>Charts</b> · v1–v6 · <a href="examples/charts.html">HTML</a> | <a href="../../docs/screens/charts-2.jpg"><img src="../../docs/screens/thumbs/charts-2.jpg" alt="Charts example screen"></a><br><b>Charts</b> · v7–v12 · <a href="examples/charts-2.html">HTML</a> | <a href="../../docs/screens/cards.jpg"><img src="../../docs/screens/thumbs/cards.jpg" alt="Cards example screen"></a><br><b>Cards</b> · v1–v6 · <a href="examples/cards.html">HTML</a> | <a href="../../docs/screens/cards-2.jpg"><img src="../../docs/screens/thumbs/cards-2.jpg" alt="Cards example screen"></a><br><b>Cards</b> · v7–v12 · <a href="examples/cards-2.html">HTML</a> |
| <a href="../../docs/screens/tables.jpg"><img src="../../docs/screens/thumbs/tables.jpg" alt="Data tables example screen"></a><br><b>Data tables</b> · 6 versions · <a href="examples/tables.html">HTML</a> | <a href="../../docs/screens/calendar.jpg"><img src="../../docs/screens/thumbs/calendar.jpg" alt="Calendars example screen"></a><br><b>Calendars</b> · 5 versions · <a href="examples/calendar.html">HTML</a> | <a href="../../docs/screens/buttons.jpg"><img src="../../docs/screens/thumbs/buttons.jpg" alt="Buttons example screen"></a><br><b>Buttons</b> · v1–v6 · <a href="examples/buttons.html">HTML</a> | <a href="../../docs/screens/buttons-2.jpg"><img src="../../docs/screens/thumbs/buttons-2.jpg" alt="Buttons example screen"></a><br><b>Buttons</b> · v7–v12 · <a href="examples/buttons-2.html">HTML</a> |
| <a href="../../docs/screens/form-controls.jpg"><img src="../../docs/screens/thumbs/form-controls.jpg" alt="Form controls example screen"></a><br><b>Form controls</b> · v1–v6 · <a href="examples/form-controls.html">HTML</a> | <a href="../../docs/screens/form-controls-2.jpg"><img src="../../docs/screens/thumbs/form-controls-2.jpg" alt="Form controls example screen"></a><br><b>Form controls</b> · v7–v12 · <a href="examples/form-controls-2.html">HTML</a> | <a href="../../docs/screens/overlays.jpg"><img src="../../docs/screens/thumbs/overlays.jpg" alt="Menus and overlays example screen"></a><br><b>Menus and overlays</b> · 6 versions · <a href="examples/overlays.html">HTML</a> | <a href="../../docs/screens/feedback.jpg"><img src="../../docs/screens/thumbs/feedback.jpg" alt="Feedback example screen"></a><br><b>Feedback</b> · 6 versions · <a href="examples/feedback.html">HTML</a> |
| <a href="../../docs/screens/commerce.jpg"><img src="../../docs/screens/thumbs/commerce.jpg" alt="Commerce example screen"></a><br><b>Commerce</b> · 5 versions · <a href="examples/commerce.html">HTML</a> | <a href="../../docs/screens/pricing.jpg"><img src="../../docs/screens/thumbs/pricing.jpg" alt="Pricing example screen"></a><br><b>Pricing</b> · 4 versions · <a href="examples/pricing.html">HTML</a> | <a href="../../docs/screens/landing.jpg"><img src="../../docs/screens/thumbs/landing.jpg" alt="Landing pages example screen"></a><br><b>Landing pages</b> · 6 versions · <a href="examples/landing.html">HTML</a> | <a href="../../docs/screens/onboarding.jpg"><img src="../../docs/screens/thumbs/onboarding.jpg" alt="Onboarding and errors example screen"></a><br><b>Onboarding and errors</b> · v1–v6 · <a href="examples/onboarding.html">HTML</a> |
| <a href="../../docs/screens/onboarding-2.jpg"><img src="../../docs/screens/thumbs/onboarding-2.jpg" alt="Onboarding example screen"></a><br><b>Onboarding</b> · v7–v12 · <a href="examples/onboarding-2.html">HTML</a> | <a href="../../docs/screens/mobile-apps.jpg"><img src="../../docs/screens/thumbs/mobile-apps.jpg" alt="Mobile apps example screen"></a><br><b>Mobile apps</b> · 5 versions · <a href="examples/mobile-apps.html">HTML</a> | <a href="../../docs/screens/messaging.jpg"><img src="../../docs/screens/thumbs/messaging.jpg" alt="Messaging and assistant example screen"></a><br><b>Messaging and assistant</b> · 4 versions · <a href="examples/messaging.html">HTML</a> | <a href="../../docs/screens/brand.jpg"><img src="../../docs/screens/thumbs/brand.jpg" alt="Brand guidelines example screen"></a><br><b>Brand guidelines</b> · 6 versions · <a href="examples/brand.html">HTML</a> |

## Security baseline

LaunchGuard ships a 20-control baseline in `modules/launchguard/references/security-baseline.md`. Each control lists what to do, the common trap and how to verify it. A security-sensitive change gets a scoped check of the controls it touches; a launch review reports all 20.

| Area | Controls |
|---|---|
| Secrets and keys | 1. Hide API keys · 2. Purge Git secrets (rotate first) · 3. Use only the public database key in the client |
| Data access | 4. Enable row-level security · 5. Encrypt sensitive data · 6. Enforce server-side auth · 7. Lock record access · 8. Block field tampering |
| Sessions and login | 9. Secure session cookies · 10. Hash passwords · 11. Rate-limit login · 12. Add bot protection |
| Input and output | 13. Parameterize queries · 14. Validate all input · 15. Escape user content · 16. Restrict file uploads · 17. Trim API responses |
| Platform | 18. Add security headers · 19. Force HTTPS · 20. Scan dependencies |

## Bundled tools

| Tool | What it does |
|---|---|
| `scripts/check_package.py` | Checks package integrity: one `SKILL.md`, a valid pattern library and UI rulebook, all modules present, and reference screens that are listed, self-contained and cite only real rule IDs |
| `modules/launchguard/scripts/preflight_scan.py` | Read-only, redacted heuristic scan for secret-shaped literals, public secret env names, disabled TLS verification, wildcard CORS, debug flags, HTML sinks, sensitive logging, cookies with HttpOnly or Secure disabled, and fast hashes used on passwords |
| `modules/credential-shield/scripts/simulate_policy.py` | Offline, synthetic demonstration of how distributed credential-stuffing campaigns become visible through combined signals |
| `modules/engineering-workflow/scripts/diff_scope.py` | Self-check of a diff: out-of-scope files, whitespace churn, debug leftovers, focused or skipped tests, removed assertions, lockfile churn. Never prints changed lines |
| `modules/engineering-practices/scripts/migration_check.py` | Flags SQL migrations likely to lock tables or lose data (drops, in-place renames, blocking index builds, full-table updates, missing lock timeouts) |
| `modules/code-security-review/scripts/code_audit.py` | Ranks files to read first, scans local git history for secrets without printing values, checks CI workflow files, validates the findings JSON |
| `modules/legal-ready/scripts/legal_scan.py` | Scans a project for legal-readiness signals: policy pages, consent mechanism, third-party trackers, images without alt text, pre-ticked consent, unsubscribe links, a data deletion route |
| `modules/agent-safety/scripts/guard_command.py` | Classifies a shell command as allow, ask or deny with a reason and a safer alternative; usable as an opt-in pre-tool hook |
| `modules/agent-safety/scripts/scan_skill.py` | Read-only static scan of a third-party skill, plugin, MCP server or hook folder before installation |
| `modules/codebase-map/scripts/map_codebase.py` | Maps a repository: entry points, routes, Python and JS/TS import graph, top-level symbols and hotspots; never opens credential files |
| `modules/documents/scripts/ooxml_inspect.py` | Inspects Word, Excel and PowerPoint files for tracked changes, comments, hidden content, leftover placeholders, uncalculated formulas and off-slide shapes |
| `modules/builder-tools/scripts/lint_skill.py` | Lints an Agent Skill folder: frontmatter limits, broken file references, oversized files without contents lists, stray caches |
| `assets/review-template.md` | Template for the agent's change report |

Every script uses the Python 3 standard library only, is read-only toward the project it inspects and never touches the network.

Run the scanner against an app:

```bash
python3 <skill-root>/modules/launchguard/scripts/preflight_scan.py \
  --root . --json-out security/launchguard-scan.json
```

## Validate the package

From inside this folder:

```bash
python3 scripts/check_package.py --root .
python3 -m unittest discover -s tests -v
for t in modules/*/tests; do python3 -m unittest discover -s "$t" -v; done
```

The suites hold 231 tests in total. They validate the package and its helper scripts, not the security or design of any particular application.

## Package layout

```text
productcraft/
├── SKILL.md                     # single entry point and router
├── README.md                    # this file
├── LICENSE                      # MIT
├── WORKSPACE-SETUP-PROMPT.txt   # paste-in installer prompt for ZIP uploads
├── assets/review-template.md
├── modules/
│   ├── product-design.md
│   ├── interaction-feedback.md
│   ├── forms-conversion.md
│   ├── data-and-product-surfaces.md
│   ├── responsive-accessibility.md
│   ├── ethical-persuasion.md
│   ├── ui-rules.md              # routes to the UI rulebook
│   ├── language-choice.md       # when and how to offer Rust
│   ├── lean-output.md           # opt-in shorter answers
│   ├── engineering-workflow/    # tracks, planning, test-first, debugging, review; diff self-check
│   ├── engineering-practices/   # APIs, migrations, resilience, performance, observability, CI/CD; migration check
│   ├── ui-distiller/            # guide + design rules, patterns, quality gate, taste, style catalog
│   ├── code-security-review/    # audit phases, threat modeling, vulnerability classes, audit helper
│   ├── credential-shield/       # guide, references, policy example, simulator, tests
│   ├── launchguard/             # guide, security baseline, references, scanner, tests, report templates
│   ├── legal-ready/             # 20 legal-readiness items, owner questionnaire, scanner
│   ├── agent-safety/            # stop-check, secrets, extension vetting, command guard, scanner
│   ├── codebase-map/            # repository mapper and how to use it
│   ├── documents/               # Word, Excel, PowerPoint and PDF guides, OOXML inspector
│   └── builder-tools/           # Agent Skills, MCP servers, Playwright; skill linter
├── examples/                    # reference screens: HTML pages, tokens.css, gallery.css, README index
├── references/
│   ├── ui-rules/                # UI rulebook, one file per category
│   ├── ui-rules-index.json
│   ├── pattern-library.md       # UI/UX patterns with rules and guardrails
│   └── pattern-index.json
├── scripts/check_package.py
└── tests/test_package.py
```

## Limitations

- Pattern rules are heuristics, not mandatory design laws. Security, accessibility, facts and user consent always take precedence.
- ProductCraft is a build guide. It does not guarantee security, accessibility compliance or a correct implementation in your app.
- For apps that handle substantial money or sensitive data, arrange a qualified human security review before launch.
- Legal Ready is general guidance, not legal advice. Have a qualified lawyer review policies and obligations for your business and markets.
- The agent-safety command guard is a seatbelt, not a sandbox. For real isolation, run agents in a container or VM without production credentials.

## License

Released under the [MIT License](LICENSE). Anyone can use, copy, modify and share ProductCraft, including for commercial work, as long as the copyright and license notice stay with the copies.

© 2026 Sora Labs
