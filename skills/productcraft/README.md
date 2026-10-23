# ProductCraft

**A Sora Labs Agent Skill** · version 1.0.0 · part of [All-in-One AI Skills](../../README.md)

ProductCraft is one installable skill that teaches a coding agent to build product interfaces that **show the important thing first, respond honestly, work on every device, and are secured where it matters**. It routes each task to only the modules that task needs, so a table change reads the table guidance, an auth change reads the auth-defense module, and a launch reads the five-gate security review.

It is a coding skill, not a theme pack, component gallery or security certification. The agent changes your real codebase and reports what it actually tested.

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
| **LaunchGuard** | Pre-launch security review, secrets, user data, authorization, payments, release go/no-go | `modules/launchguard/GUIDE.md` |
| **Pattern library** | One principle, one implementation rule and one guardrail for each UI/UX pattern | `references/pattern-library.md` |

The pattern library covers foundations, feedback, forms, interaction, navigation, responsive layout, data views, conversion, safety and advanced patterns such as live presence, chat and view transitions. A machine-readable version is in `references/pattern-index.json`.

## How it activates

`SKILL.md` is the single entry point. Its router picks modules from what the task actually touches:

| The task involves | ProductCraft reads |
|---|---|
| A new UI, a redesign, or decluttering | UI Distiller + product design |
| Controls, motion, toasts, modals | Interaction & feedback |
| Forms, signup, OTP, checkout, search | Forms & conversion |
| Tables, dashboards, calendars, Kanban, chat, uploads | Data & product surfaces |
| Mobile layout, translation, RTL | Responsive & accessibility |
| Funnels, conversion copy, engagement | Ethical persuasion |
| Login abuse, MFA, password reset | Credential Shield |
| Launch, payments, user data, privileged operations | LaunchGuard |
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

Use productcraft on the signup and OTP flow: keep codes as strings, support paste and
autofill, and consult Credential Shield for the resend and verify endpoints.

Use productcraft to prepare this app for launch. Run the LaunchGuard five gates and
write the report with PASS / FAIL / NOT_VERIFIED evidence.
```

### Optional persistent project rule

Add this to your project's `CLAUDE.md` or `AGENTS.md` so the agent keeps using ProductCraft on future work:

> For significant frontend creation/redesign, UI interaction changes, complex forms, tables, dashboards, mobile layouts, or workflow UX, invoke the project-local ProductCraft skill and selectively read the matching design and interaction modules. Prioritize essential content, remove unnecessary visual noise, preserve accessible keyboard/touch behavior and real async/error handling. Use ethically transparent conversion techniques only; never fake scarcity, typing, fees, progress, social proof or server confirmations. For changes to auth/OTP/password recovery, consult its bundled Credential Shield module. For release preparation and changes to privileged operations, money, user data or production security, consult its bundled LaunchGuard module and perform scoped or five-gate verification as appropriate. Never apply the whole pattern library or run a full security audit on trivial copy/CSS edits. Keep reports honest and do not modify production secrets, cloud policy, live data or deployments without explicit authorization.

## Built-in guardrails

- **Verified over optimistic.** Payments, bookings, deletions, privileged changes and entitlements show *pending* until the server or provider confirms them.
- **Honest persuasion only.** Fake scarcity, phantom typing, artificial countdowns, hidden fees and hard-to-cancel flows are treated as anti-patterns to remove.
- **Accessibility first.** Semantic elements, keyboard and touch parity, reduced motion and visible focus outrank aesthetic formulas such as 60/30/10 or the golden ratio.
- **No false passes.** Scanners are advisory. Security checks report `PASS`, `FAIL`, `NEEDS_REVIEW`, `NOT_APPLICABLE` or `NOT_VERIFIED`, and secrets are never printed.
- **Hands off production.** No changes to real secrets, live data, payment provider settings or deployments without explicit permission.

## Bundled tools

| Tool | What it does |
|---|---|
| `scripts/check_package.py` | Checks package integrity: one `SKILL.md`, a valid pattern library, all modules present |
| `modules/launchguard/scripts/preflight_scan.py` | Read-only, redacted heuristic scan for secret-shaped literals, public secret env names, disabled TLS verification, wildcard CORS, debug flags, HTML sinks and sensitive logging |
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

The suites hold 15 tests in total. They validate the package and its helper scripts, not the security or design of any particular application.

## Package layout

```text
productcraft/
├── SKILL.md                     # single entry point and router
├── README.md                    # this file
├── WORKSPACE-SETUP-PROMPT.txt   # paste-in installer prompt for ZIP uploads
├── assets/review-template.md
├── modules/
│   ├── product-design.md
│   ├── interaction-feedback.md
│   ├── forms-conversion.md
│   ├── data-and-product-surfaces.md
│   ├── responsive-accessibility.md
│   ├── ethical-persuasion.md
│   ├── ui-distiller/            # guide + design rules, patterns, quality gate
│   ├── credential-shield/       # guide, references, policy example, simulator, tests
│   └── launchguard/             # guide, references, scanner, tests, report templates
├── references/
│   ├── pattern-library.md       # UI/UX patterns with rules and guardrails
│   └── pattern-index.json
├── scripts/check_package.py
└── tests/test_package.py
```

## Limitations

- Pattern rules are heuristics, not mandatory design laws. Security, accessibility, facts and user consent always take precedence.
- ProductCraft is a build guide. It does not guarantee security, accessibility compliance or a correct implementation in your app.
- For apps that handle substantial money or sensitive data, arrange a qualified human security review before launch.

---

© 2026 Sora Labs
