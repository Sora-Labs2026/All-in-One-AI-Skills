# Changelog

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
