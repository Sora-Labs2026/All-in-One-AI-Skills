# All-in-One AI Skills

**By Sora Labs.** Production-minded Agent Skills for coding agents such as Claude Code and Codex.

Each skill in this repository is a folder of instructions, references, scripts and tests that a coding agent loads when a task calls for it. The skills change real code and report what was actually verified. They are not themes, templates or certifications.

[![Validate skills](https://github.com/Sora-Labs2026/All-in-One-AI-Skills/actions/workflows/validate.yml/badge.svg)](https://github.com/Sora-Labs2026/All-in-One-AI-Skills/actions/workflows/validate.yml)

## Skills

| Skill | Version | What it does |
|---|---|---|
| [**ProductCraft**](skills/productcraft/README.md) | 1.0.0 | Builds and hardens app UIs with one routed skill: design hierarchy, honest interaction feedback, forms and checkout, data views, mobile and accessibility, ethical conversion, auth-abuse defense and pre-launch security review, backed by a UI/UX pattern library. |

## ProductCraft

ProductCraft helps an agent build interfaces that show the important thing first, respond honestly, work on every device and are secured where it matters. It reads only the modules a task needs:

- **UI Distiller and product design**: decluttering, information hierarchy, tokens, spacing and density
- **Interaction and feedback**: buttons, switches, sliders, drag and drop, modals, toasts and motion, with verified rather than faked success states
- **Forms and conversion**: signup, OTP, passwords, search, uploads and checkout
- **Data and product surfaces**: tables, dashboards, calendars, Kanban, chat and command palettes
- **Responsive and accessibility**: touch targets, sheets vs. dialogs, keyboard, screen readers, i18n and RTL
- **Ethical persuasion**: conversion without fake urgency, fake social proof or hidden fees
- **Credential Shield**: defense against credential stuffing and password spraying on login, OTP, MFA and reset flows
- **LaunchGuard**: five-gate pre-launch security review with a PASS / FAIL / NOT_VERIFIED evidence report
- **Pattern library**: UI/UX patterns, each with a principle, an implementation rule and a guardrail

Full details, example prompts and limitations are in the [ProductCraft README](skills/productcraft/README.md).

## Install

### Claude Code

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

### ZIP upload to any coding-agent workspace

1. Download [`dist/productcraft.zip`](dist/productcraft.zip) and [`dist/PRODUCTCRAFT-WORKSPACE-SETUP-PROMPT.txt`](dist/PRODUCTCRAFT-WORKSPACE-SETUP-PROMPT.txt).
2. Upload the ZIP to your agent's workspace.
3. Paste the contents of the setup prompt. The agent extracts the ZIP safely, installs the skill locally to the project, runs the package checks and adds a short project rule so ProductCraft keeps applying to future work.

## Repository layout

```text
.
├── .claude-plugin/marketplace.json   # Claude Code plugin marketplace entry
├── .github/workflows/validate.yml    # runs package checks and tests on every push and PR
├── dist/                             # ready-to-upload ZIP + setup prompt for each skill
├── scripts/build_dist.py             # rebuilds or verifies dist/ from skills/
└── skills/
    └── productcraft/                 # the ProductCraft skill (SKILL.md is the entry point)
```

## Validate

```bash
cd skills/productcraft
python3 scripts/check_package.py --root .
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s modules/credential-shield/tests -v
python3 -m unittest discover -s modules/launchguard/tests -v
cd ../..
python3 scripts/build_dist.py --check
```

All of it uses the Python 3 standard library only. CI runs the same checks.

## Updating a skill

1. Edit files under `skills/<skill>/`.
2. Run `python3 scripts/build_dist.py` to rebuild the downloadable bundle in `dist/`.
3. Run the validation commands above and commit `skills/` and `dist/` together.

## Principles

Every Sora Labs skill follows the same rules:

- Read the real project before changing it, and respect existing branding, conventions and uncommitted work.
- Use only the modules the task needs.
- Show *pending*, not *done*, until the server or provider has confirmed money, bookings, deletions or permission changes.
- Never fake scarcity, typing, progress, social proof or fees.
- Report only checks that actually ran. Scanners are advisory, and a clean scan is not a security pass.
- Leave production secrets, live data and deployments alone unless explicitly authorized.

## License

No open-source license has been chosen yet. Until one is added, all rights are reserved by Sora Labs.

© 2026 Sora Labs
