# UI Distiller: Building and auditing a design system

Read this when a product needs a design system it does not have, when one must be extracted from an existing codebase, or when an interface "looks off" and you need evidence of inconsistency before a redesign. The rules for foundations, token tiers, core components and documentation are `CMP-01` to `CMP-04` in `../../../references/ui-rules/components.md`; this file is the procedure, the file formats and the enforcement that keep a system alive.

## Scope it to the product

Build the smallest system that serves the product in front of you:

| Situation | Build |
|---|---|
| One app, inconsistent values | Tokens and a migration of raw values; no new component library |
| One app, repeated hand-built controls | Tokens plus the core components the app actually uses (`CMP-03`) |
| Several apps or teams sharing a look | A versioned token package, a component package, a preview page and documentation |

Do not adopt a new component framework to fix spacing or color (`../GUIDE.md`, step 5). Build from the real screens, not from an empty canvas or from other companies' sites: their values fit their products, not this one.

## 1. Inventory what exists (read-only)

Measure the codebase before proposing anything:

```bash
python3 <productcraft>/modules/ui-distiller/scripts/token_inventory.py src/ --json > inventory-before.json
python3 <productcraft>/modules/ui-distiller/scripts/token_inventory.py src/ --spacing-base 4
```

The script counts raw colors (and clusters near-duplicates), font sizes, spacing values off the scale, radii, shadows, durations and z-index values, counts custom-property definitions and `var()` uses, and flags `transition: all` and `will-change: all`, each with file and line. It reads files and writes nothing. Also collect what the project already treats as tokens: CSS custom properties, the Tailwind theme, SCSS variables, a theme object in a component library, the design file's styles.

Then look at rendered screens with the measurement snippet in [taste.md](taste.md) at 390px and 1440px: source counts show what was written, computed styles show what users see.

## 2. Consolidate into scales

- **Colors.** Group near-duplicates (the script uses a distance of 0.02 in OKLab, the just-noticeable difference used by CSS Color 4 gamut mapping). Each cluster becomes one primitive, or a deliberate pair with different roles. Build tonal ramps for the brand hue and a neutral (`CMP-01`); status colors keep their meaning (`COL-06`).
- **Spacing.** Snap values to the 4/8 scale (`LAY-01`). Keep exceptions only where they are real: 1px borders, focus outline widths, 1-2px optical nudges.
- **Type.** Map every size onto a five- or six-step scale (`TYP-02`); sizes that are hard to tell apart become one.
- **Radius and elevation.** One small radius scale fitted to the brand (`CMP-05`), nested radii concentric (`CMP-06`), a few elevation levels used for floating surfaces only (`CMP-07`).
- **Motion.** Duration and easing tokens by role ([motion-engineering.md](motion-engineering.md)).
- **Layers.** A named z-index scale (base, dropdown, sticky, overlay, modal, toast) instead of ever-larger numbers.

Treat every merge as a proposal. Show before and after screenshots for anything that changes visibly, and keep a mapping table (old value, new token, files affected).

## 3. Write the tokens as data

Three tiers (`CMP-02`): primitives, semantic tokens named by purpose, component tokens only where a component truly differs. Keep them in one source file and generate every platform output from it.

The common interchange format is the Design Tokens Community Group format (a W3C community group report; its first stable version was published in October 2025). Tokens are JSON objects with `$value`, `$type` and optional `$description`; groups nest; aliases reference other tokens with curly braces. The sketch below uses the string values that most tools accepted through 2025; the stable format writes colors and dimensions as objects (a color space with components; a value with a unit), so use the shape your build tool reads and validate it.

```json
{
  "color": {
    "$type": "color",
    "teal": { "600": { "$value": "#0F766E" }, "700": { "$value": "#115E59" } },
    "neutral": { "0": { "$value": "#FFFFFF" }, "900": { "$value": "#1C1F22" } },
    "action": {
      "primary": { "$value": "{color.teal.700}", "$description": "Primary buttons, links, current item" },
      "on-primary": { "$value": "{color.neutral.0}", "$description": "Text and icons on action.primary" }
    },
    "text": { "default": { "$value": "{color.neutral.900}" } }
  },
  "space": { "$type": "dimension", "1": { "$value": "4px" }, "2": { "$value": "8px" }, "4": { "$value": "16px" } },
  "radius": { "$type": "dimension", "control": { "$value": "6px" }, "card": { "$value": "10px" } }
}
```

- **Build:** a token transformer (Style Dictionary 4 and later reads this format; Apache-2.0) emits CSS custom properties, a JavaScript or TypeScript module, and iOS and Android resources. For CSS only, a 30-line script is enough. Generated files are build output; never edit them by hand.
- **Themes:** remap the semantic tier per theme (`[data-theme="dark"]` or `@media (prefers-color-scheme: dark)`), set `color-scheme: light dark` so native controls follow, and consider `light-dark()` for paired values. Dark mode is its own palette, not an inversion (`DRK-01`).
- **Pairs:** every fill token has an on-color token (`CMP-02`). Test every approved text-on-fill pair for contrast in CI with the luminance check in [style-catalog.md](style-catalog.md); a failing pair fails the build.
- **Tailwind projects:** express tokens in the theme (Tailwind 4 declares them as CSS variables in `@theme`) and remove arbitrary values such as `p-[13px]` or `bg-[#1a2b3c]` as you migrate; the inventory script counts them.

## 4. Build the core components

Start with the components the screens use most (`CMP-03`), complete in every state.

- **API:** `variant`, `size` and `tone` props with a closed set of values; `disabled` and `loading` handled inside the component (`ENG-03`); a `ref` forwarded to the native element.
- **Native first** (`ENG-01`): a button is a `<button>`, a link is an `<a>`. For complex widgets (combobox, dialog, menu, tabs, date picker) build on an accessible headless library (for example React Aria, Radix Primitives or Headless UI) rather than writing focus management from scratch.
- **No outer margin on components.** Spacing between components belongs to the layout that places them (`gap`, stack and grid components); a button with built-in margin breaks every layout it lands in.
- **Tokens only inside components.** No raw hex, pixel or duration values in component code.

## 5. A preview page generated from the tokens

Generate one self-contained HTML page from the token file and the components: every color swatch with its name, value and the contrast ratio of each approved pair; the type scale with real copy; the spacing ruler; radius and elevation samples; motion samples that respect reduced motion; and every component in every variant, size and state, in light and dark. Because it is generated, it cannot drift from the code. If the project already uses Storybook or a similar workshop, generate stories there instead of a second page.

Snapshot the page in a browser test (`toHaveScreenshot` in Playwright, `../../builder-tools/references/playwright-web-testing.md`) so token changes show up as visual diffs in review.

## 6. Document decisions

Keep a short `DESIGN.md` next to the tokens: the direction and why it fits the product (one paragraph, see [style-catalog.md](style-catalog.md)), the scales with the reason for each base value, the color roles and approved pairs with ratios, and what is deliberately not in the system. Give each component one page as in `CMP-04`, with measured accessibility facts rather than checkmarks.

## 7. Enforce, or it decays

- **Lint:** forbid raw color literals outside the token files (Stylelint's `color-no-hex` with an override for token files, or a plugin that requires variables for chosen properties), and disallow `transition: all` with `declaration-property-value-disallowed-list`. In CSS-in-JS, a restricted-syntax lint rule does the same.
- **Ratchet in CI:** run `token_inventory.py --baseline inventory-before.json`; it exits 1 when any count grew. Counts may only go down; update the baseline when they do.
- **Review:** new tokens and component variants go through a short proposal (need, alternatives, screens affected) with an owner who decides.

## 8. Migrate incrementally

1. Replace exact matches with tokens mechanically (a codemod or a scripted search and replace), one category per pull request.
2. Resolve near-duplicates by hand with screenshots, screen by screen.
3. Rename or remove tokens through deprecation: keep the old name as an alias that warns at build time for one release, then remove it. Version a shared token package with semantic versioning (a removed or renamed token is a breaking change) and keep a changelog (`CMP-04`).

## Audit report format

Report counts with locations rather than scores out of ten; counts are reproducible and show progress.

| Area | Evidence (before → after) | Worst examples | Fix |
|---|---|---|---|
| Color | 47 raw colors, 9 near-duplicate clusters → 14 tokens | `src/cart.css:12` `#1b6ef3` vs `#1a6df2` | Merge into `color.blue.600` |
| Spacing | 31 off-scale values → 3 documented exceptions | `padding: 13px 18px` in 6 files | Snap to `space.3`/`space.4` |
| Type | 13 sizes → 6 | 15px and 16px both used for body | One body size |
| States | Buttons lack loading and focus-visible states | `Button.tsx` | Complete per `CMP-03` |
| Contrast | 3 approved pairs below 4.5:1 | `on-accent` on `accent-400` | Darker fill or dark on-color |
| Motion | 12 durations, `transition: all` in 9 places | `Card.css:40` | Tokens; explicit properties |

## Pitfalls

- Tokens named by appearance (`blue-button`), which break on the first rebrand.
- A tier for everything: component tokens that only alias semantic ones add names without meaning.
- Design file and code each holding their own values; keep one source and sync from it.
- Declaring the system done when the files exist: without lint and a ratchet, raw values return within weeks.
- Copying another company's system wholesale; take structure and method, not their brand values.

## Done when

- The inventory was run before and after, and the counts went down in every category you touched.
- One token file generates every output; themes remap the semantic tier; every approved pair passes contrast in CI.
- Core components exist in every state, use tokens only, and carry no outer margin.
- A generated preview page or workshop shows all tokens and components and is covered by a screenshot test.
- Lint rules and the baseline ratchet run in CI; `DESIGN.md` records the decisions.
