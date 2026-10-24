# ProductCraft

**A Sora Labs Agent Skill** · version 1.4.0 · MIT License · part of [All-in-One AI Skills](../../README.md)

ProductCraft is one installable skill that teaches a coding agent to build product interfaces that **show the important thing first, respond honestly, work on every device, and are secured where it matters**. It routes each task to only the modules that task needs, so a table change reads the table guidance, an auth change reads the auth-defense module, and a launch reads the five-gate security review.

It is a coding skill, not a theme pack or security certification. Its reference screens are code to learn from, not a component kit to paste. The agent changes your real codebase and reports what it actually tested.

## What's inside

| Module | Use it for | Entry file |
|---|---|---|
| **UI Distiller** | New screens, redesigns, cleaning up cluttered or "AI-looking" frontends | `modules/ui-distiller/GUIDE.md` |
| **Product design** | Information hierarchy, tokens, spacing, density, Keep/Promote/Compress/Demote/Remove audits | `modules/product-design.md` |
| **Interaction & feedback** | Buttons, switches, sliders, drag and drop, modals, toasts, motion, optimistic vs. verified state | `modules/interaction-feedback.md` |
| **Forms & conversion** | Signup, OTP, passwords, search, uploads, checkout and payment UI | `modules/forms-conversion.md` |
| **Data & product surfaces** | Tables, dashboards, calendars, Kanban, chat, command palettes | `modules/data-and-product-surfaces.md` |
| **Responsive & accessibility** | Mobile layouts, touch targets, sheets vs. dialogs, keyboard, screen readers, i18n and RTL | `modules/responsive-accessibility.md` |
| **Ethical persuasion** | Funnels, copy and engagement without fake urgency, fake social proof or hidden fees | `modules/ethical-persuasion.md` |
| **Credential Shield** | Login, OTP/MFA, password reset, credential stuffing and password spraying defense | `modules/credential-shield/GUIDE.md` |
| **LaunchGuard** | Pre-launch five-gate security review plus a 20-control security baseline: secrets, user data, authorization, payments, release go/no-go | `modules/launchguard/GUIDE.md` |
| **UI rules** | A rulebook of screen-level rules with IDs (spacing, type, color, dark mode, buttons, forms, navigation, touch, feedback, components, icons, copy, screens, motion, front-end engineering, brand identity) | `modules/ui-rules.md` |
| **Language choice** | Offers Rust for new projects, services or performance-critical components, with honest trade-offs, and remembers the answer | `modules/language-choice.md` |
| **Pattern library** | One principle, one implementation rule and one guardrail for each UI/UX pattern | `references/pattern-library.md` |
| **Reference screens** | 21 original HTML pages with 92 screens (dashboards, auth, settings, navigation, charts, cards, forms, feedback, commerce, pricing, mobile, messaging, onboarding, brand) that show the rules applied | `examples/README.md` |

The pattern library covers foundations, feedback, forms, interaction, navigation, responsive layout, data views, conversion, safety and advanced patterns such as live presence, chat and view transitions. A machine-readable version is in `references/pattern-index.json`.

## How it activates

`SKILL.md` is the single entry point. Its router picks modules from what the task actually touches:

| The task involves | ProductCraft reads |
|---|---|
| A new UI, a redesign, or decluttering | UI Distiller + product design + UI rules |
| Spacing, type, color, dark mode, buttons, form fields, navigation, icons, microcopy | The matching UI rules categories |
| Controls, motion, toasts, modals | Interaction & feedback |
| Forms, signup, OTP, checkout, search | Forms & conversion |
| Tables, dashboards, calendars, Kanban, chat, uploads | Data & product surfaces |
| Mobile layout, translation, RTL | Responsive & accessibility |
| Funnels, conversion copy, engagement | Ethical persuasion |
| Login abuse, MFA, password reset | Credential Shield |
| API routes, data access, queries, uploads, cookies, headers, dependencies | The matching LaunchGuard security-baseline controls |
| Launch, payments, user data, privileged operations | LaunchGuard |
| A new project, service or performance-critical component with no language fixed | Language choice (asks once about Rust) |
| A broad, ambiguous product task | Product design + interaction, then only what is relevant |

The security modules are conditional. A copy or CSS tweak does not trigger a full audit.

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
```

### Optional persistent project rule

Add this to your project's `CLAUDE.md` or `AGENTS.md` so the agent keeps using ProductCraft on future work:

> For significant frontend creation/redesign, UI interaction changes, complex forms, tables, dashboards, mobile layouts, or workflow UX, invoke the project-local ProductCraft skill and selectively read the matching design and interaction modules. Prioritize essential content, remove unnecessary visual noise, preserve accessible keyboard/touch behavior and real async/error handling. Use ethically transparent conversion techniques only; never fake scarcity, typing, fees, progress, social proof or server confirmations. For changes to auth/OTP/password recovery, consult its bundled Credential Shield module. For release preparation and changes to privileged operations, money, user data or production security, consult its bundled LaunchGuard module and check the matching security-baseline controls, or run the full five-gate review when shipping. Never apply the whole pattern library or run a full security audit on trivial copy/CSS edits. Keep reports honest and do not modify production secrets, cloud policy, live data or deployments without explicit authorization. For a new project, service or performance-critical component whose language is not yet fixed, ask once whether to write it in Rust, stating the trade-offs (faster runtime, slower compiles, more AI tokens, no automatic page-load gain) per its language-choice module.

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

`examples/` holds 21 original reference pages with 92 screens. Each page is plain HTML and CSS with no external requests, cites the rule IDs it demonstrates and passes a WCAG AA contrast check. The router points an agent at the page that matches its task. The agent studies the semantics, states and details, then rebuilds the pattern with the project's own components and tokens. [`examples/README.md`](examples/README.md) lists every page and version.

| | | |
|---|---|---|
| <a href="../../docs/screens/dashboard-v1.jpg"><img src="../../docs/screens/thumbs/dashboard-v1.jpg" alt="Dashboard v1 example screen"></a><br><b>Dashboard v1</b> · light analytics · <a href="examples/dashboard-v1.html">HTML</a> | <a href="../../docs/screens/dashboard-v2.jpg"><img src="../../docs/screens/thumbs/dashboard-v2.jpg" alt="Dashboard v2 example screen"></a><br><b>Dashboard v2</b> · dark operations · <a href="examples/dashboard-v2.html">HTML</a> | <a href="../../docs/screens/dashboard-v3.jpg"><img src="../../docs/screens/thumbs/dashboard-v3.jpg" alt="Dashboard v3 example screen"></a><br><b>Dashboard v3</b> · bento overview · <a href="examples/dashboard-v3.html">HTML</a> |
| <a href="../../docs/screens/sign-in.jpg"><img src="../../docs/screens/thumbs/sign-in.jpg" alt="Sign-in example screen"></a><br><b>Sign-in</b> · split screen · <a href="examples/sign-in.html">HTML</a> | <a href="../../docs/screens/auth.jpg"><img src="../../docs/screens/thumbs/auth.jpg" alt="Account access example screen"></a><br><b>Account access</b> · 5 versions · <a href="examples/auth.html">HTML</a> | <a href="../../docs/screens/otp.jpg"><img src="../../docs/screens/thumbs/otp.jpg" alt="Codes and PINs example screen"></a><br><b>Codes and PINs</b> · 6 versions · <a href="examples/otp.html">HTML</a> |
| <a href="../../docs/screens/settings.jpg"><img src="../../docs/screens/thumbs/settings.jpg" alt="Settings example screen"></a><br><b>Settings</b> · security page · <a href="examples/settings.html">HTML</a> | <a href="../../docs/screens/navigation.jpg"><img src="../../docs/screens/thumbs/navigation.jpg" alt="Navigation example screen"></a><br><b>Navigation</b> · 5 versions · <a href="examples/navigation.html">HTML</a> | <a href="../../docs/screens/tab-bars.jpg"><img src="../../docs/screens/thumbs/tab-bars.jpg" alt="Tab bars example screen"></a><br><b>Tab bars</b> · 5 versions + spec · <a href="examples/tab-bars.html">HTML</a> |
| <a href="../../docs/screens/charts.jpg"><img src="../../docs/screens/thumbs/charts.jpg" alt="Charts example screen"></a><br><b>Charts</b> · 6 versions · <a href="examples/charts.html">HTML</a> | <a href="../../docs/screens/cards.jpg"><img src="../../docs/screens/thumbs/cards.jpg" alt="Cards example screen"></a><br><b>Cards</b> · 6 versions · <a href="examples/cards.html">HTML</a> | <a href="../../docs/screens/calendar.jpg"><img src="../../docs/screens/thumbs/calendar.jpg" alt="Calendars example screen"></a><br><b>Calendars</b> · 5 versions · <a href="examples/calendar.html">HTML</a> |
| <a href="../../docs/screens/buttons.jpg"><img src="../../docs/screens/thumbs/buttons.jpg" alt="Buttons example screen"></a><br><b>Buttons</b> · 6 versions · <a href="examples/buttons.html">HTML</a> | <a href="../../docs/screens/form-controls.jpg"><img src="../../docs/screens/thumbs/form-controls.jpg" alt="Form controls example screen"></a><br><b>Form controls</b> · 6 versions · <a href="examples/form-controls.html">HTML</a> | <a href="../../docs/screens/feedback.jpg"><img src="../../docs/screens/thumbs/feedback.jpg" alt="Feedback example screen"></a><br><b>Feedback</b> · 6 versions · <a href="examples/feedback.html">HTML</a> |
| <a href="../../docs/screens/commerce.jpg"><img src="../../docs/screens/thumbs/commerce.jpg" alt="Commerce example screen"></a><br><b>Commerce</b> · 5 versions · <a href="examples/commerce.html">HTML</a> | <a href="../../docs/screens/pricing.jpg"><img src="../../docs/screens/thumbs/pricing.jpg" alt="Pricing example screen"></a><br><b>Pricing</b> · 4 versions · <a href="examples/pricing.html">HTML</a> | <a href="../../docs/screens/mobile-apps.jpg"><img src="../../docs/screens/thumbs/mobile-apps.jpg" alt="Mobile apps example screen"></a><br><b>Mobile apps</b> · 5 versions · <a href="examples/mobile-apps.html">HTML</a> |
| <a href="../../docs/screens/messaging.jpg"><img src="../../docs/screens/thumbs/messaging.jpg" alt="Messaging and assistant example screen"></a><br><b>Messaging and assistant</b> · 4 versions · <a href="examples/messaging.html">HTML</a> | <a href="../../docs/screens/onboarding.jpg"><img src="../../docs/screens/thumbs/onboarding.jpg" alt="Onboarding and errors example screen"></a><br><b>Onboarding and errors</b> · 6 versions · <a href="examples/onboarding.html">HTML</a> | <a href="../../docs/screens/brand.jpg"><img src="../../docs/screens/thumbs/brand.jpg" alt="Brand guidelines example screen"></a><br><b>Brand guidelines</b> · 6 versions · <a href="examples/brand.html">HTML</a> |

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
| `assets/review-template.md` | Template for the agent's change report |

Everything uses the Python 3 standard library only. Nothing touches the network.

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
python3 -m unittest discover -s modules/credential-shield/tests -v
python3 -m unittest discover -s modules/launchguard/tests -v
```

The suites hold 19 tests in total. They validate the package and its helper scripts, not the security or design of any particular application.

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
│   ├── ui-distiller/            # guide + design rules, patterns, quality gate
│   ├── credential-shield/       # guide, references, policy example, simulator, tests
│   └── launchguard/             # guide, security baseline, references, scanner, tests, report templates
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

## License

Released under the [MIT License](LICENSE). Anyone can use, copy, modify and share ProductCraft, including for commercial work, as long as the copyright and license notice stay with the copies.

© 2026 Sora Labs
