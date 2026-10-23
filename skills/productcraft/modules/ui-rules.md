# UI rules

Screen-level rules for the details that make an interface feel finished: spacing, type, color, dark mode, buttons, forms, navigation, touch, feedback, components, icons, copy and common screens. Each rule has an ID (for example `BTN-02`) and states why it matters, what to do and what to avoid. Rules live in `../references/ui-rules/`, one file per category; `../references/ui-rules-index.json` is the machine-readable index.

Use this module together with [product-design.md](product-design.md) (what to show and in what order) and [interaction-feedback.md](interaction-feedback.md) (how controls behave). This module supplies the exact values and conventions.

## How to apply

1. List the elements the change touches and pick the matching categories below. Open **only** those files.
2. Map rules onto the project's existing design system. If the project already defines tokens, type scale, radius or components, express the rule through them; example values in the rules are defaults, not replacements for brand values.
3. Implement in code, then verify what applies: contrast with a tool, the narrowest supported width, keyboard focus, touch target size, dark mode if the product has it, reduced motion.
4. Report the rule IDs applied, and any rule deliberately not applied with the reason.

## Categories

| Prefix | File | Use it for |
|---|---|---|
| `LAY` | `layout-spacing.md` | Spacing scale, grouping, alignment, focal point, grids, long content |
| `TYP` | `typography.md` | Typefaces, type scale, weight, mobile sizes, line length, tracking |
| `COL` | `color-contrast.md` | Contrast minimums, palette discipline, emphasis, status colors, text on images |
| `DRK` | `dark-mode.md` | Dark palettes, elevation, text tiers, accents, theme choice |
| `BTN` | `buttons-cta.md` | Button hierarchy, states, sizing, placement, labels with icons |
| `FRM` | `forms-inputs.md` | Labels, layout, input types, selection controls, validation, multi-step forms |
| `NAV` | `navigation.md` | Navigation patterns, active states, sidebars, breadcrumbs, tab bars |
| `MOB` | `mobile-touch.md` | Touch targets, thumb reach, safe areas, margins, device sizes, notifications |
| `FBK` | `feedback-states.md` | Responsiveness, loading, status messages, toasts, steppers, empty states |
| `CMP` | `components.md` | Foundations, tokens, core components, radius, elevation, menus, cards |
| `ICO` | `icons-imagery.md` | Icon consistency, metaphors, accessible names, image use and cropping |
| `COP` | `copy-microcopy.md` | Button labels, plain language, confirmations, casing |
| `PRN` | `principles.md` | Choice load, ordering, chunking, conventions, enough detail |
| `SCR` | `screen-patterns.md` | Dashboards, settings, search, onboarding, welcome and hero sections |
| `STY` | `style-options.md` | Optional visual treatments, only when the brand or request asks for them |

## Baseline for almost every screen

When a change touches a screen and nothing narrower applies, check at least: `LAY-01` spacing scale, `LAY-02` grouping by spacing, `LAY-05` one focal point, `TYP-02` type scale, `TYP-04` readable sizes, `COL-01` contrast, `COL-07` no color-only meaning, `BTN-01` one primary action, `BTN-02` button states, `MOB-01` touch targets, `FRM-01` visible labels, `FRM-11` inline errors, `FBK-01` immediate feedback and `COP-01` outcome labels.

## Precedence

1. Accessibility (contrast, target size, focus visibility, reduced motion, semantics) and the target platform's guidelines.
2. The project's existing design system, brand and product requirements.
3. These rules and their example values.
4. Style options (`STY`), only when explicitly wanted, and never at the expense of 1-3.

Several conventions legitimately differ by platform, such as dialog button order and whether to mark required or optional fields. Where a rule says so, follow the platform and stay consistent within the product.
