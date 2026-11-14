# UI Distiller: Running a design system

Read this once a token file and core components exist ([design-system-construction.md](design-system-construction.md)) and the system has to live: a new brand foundation generated from a brief, tokens built for several platforms, tokens kept in step with the design tool, changes versioned and deprecated without breaking teams, a migration to or from another component library, or a written direction file that a person or an AI design tool can follow. Component specifications and quality gates are [component-specs-and-design-qa.md](component-specs-and-design-qa.md).

## 1. A brand foundation from a brief

When there is no system yet, generate one deliberately rather than picking values ad hoc.

1. **Write the brief in four lines:** the domain, the audience, the single mood word the result must earn ("assured", "playful", "exacting"), and how much motion the product should have (none, functional, expressive). Pick a direction from [style-catalog.md](style-catalog.md) to anchor the decisions.
2. **Color ramps in OKLCH.** For the brand hue and a neutral, generate 10 to 12 steps with lightness spread from about 0.98 to 0.18, a chroma curve that peaks in the middle steps and falls at both ends (very light and very dark steps cannot hold high chroma inside sRGB), and a constant hue (shift it a few degrees toward yellow in light steps and toward blue in dark steps if the ramp looks muddy). Gamut-map each step to sRGB and record both values.
3. **Pick the action color by contrast, not by look.** The step used for primary buttons must reach 4.5:1 with its label; the step used for borders and focus rings must reach 3:1 against the surfaces it sits on. Usually the 600 or 700 step works on white; recheck on dark surfaces separately.
4. **Semantic roles:** page, surface, raised surface; text primary, secondary, disabled, on-action, link; action primary, hover, pressed, destructive; border default and strong; focus; success, warning, danger, info each with a fill and an on-fill. Dark mode remaps these roles to other steps (`DRK-01`); it is a second design, not an inversion.
5. **Scales:** a type scale with a ratio between 1.2 and 1.333 for product UI (larger for editorial display), a 4 px spacing scale, three or four radii, three elevation levels, duration and easing tokens by role ([motion-engineering.md](motion-engineering.md)).
6. **Emit** the token file and one theme stylesheet, then run the contrast check over every approved pair in both themes before anyone builds a screen.

```css
/* one generated ramp step, written with a fallback for older engines */
:root {
  --color-brand-600: #0f6e66;                      /* sRGB fallback */
  --color-brand-600: oklch(0.50 0.10 186);
}
```

## 2. Building tokens for every platform

Keep the DTCG token files as the single source and generate everything else. Style Dictionary (version 4 and later reads DTCG `$value` and `$type`) is the usual tool; a short script is enough for a web-only system.

```js
// style-dictionary.config.mjs  (npx style-dictionary build --config style-dictionary.config.mjs)
export default {
  source: ["tokens/primitive/**/*.json", "tokens/semantic/**/*.json", "tokens/component/**/*.json"],
  platforms: {
    css: {
      transformGroup: "css", buildPath: "build/css/",
      files: [{ destination: "tokens.css", format: "css/variables", options: { outputReferences: true },
                filter: (t) => !t.filePath.includes("/primitive/") }],
    },
    js: { transformGroup: "js", buildPath: "build/js/", files: [{ destination: "tokens.js", format: "javascript/es6" }] },
    ios: { transformGroup: "ios-swift", buildPath: "build/ios/",
           files: [{ destination: "Tokens.swift", format: "ios-swift/class.swift", options: { className: "Tokens" } }] },
    android: { transformGroup: "android", buildPath: "build/android/",
               files: [{ destination: "colors.xml", format: "android/colors", filter: (t) => t.$type === "color" }] },
  },
};
```

Rules that keep the outputs trustworthy:

- **Resolve aliases per platform**, but keep references in CSS (`outputReferences`) so a semantic variable visibly points at its primitive in devtools.
- **Expose semantic and component tokens; keep primitives internal** where the platform allows, so product code cannot reach around the roles. (Primitives still need to exist in the CSS output if semantic variables reference them; then lint against their direct use.)
- **Themes as deltas:** the dark, high-contrast, brand-b or compact output contains only the tokens that change, under its own selector (`[data-theme="dark"]`) or mode file. A full duplicate per theme drifts.
- **Platform conventions:** iOS asset catalogs or Swift constants with light and dark appearances; Android color resources plus a Compose theme object; Tailwind CSS 4 reads the CSS variables through `@theme` so utilities and tokens share names.
- **Generated files are never edited by hand.** Commit them only if consumers need them in the repository, and then fail CI when regenerating produces a diff:

```bash
npx style-dictionary build --config style-dictionary.config.mjs
git diff --exit-code build/ || { echo "Generated tokens are stale: rebuild and commit"; exit 1; }
```

- **Validate before building:** valid JSON, every alias resolves, no cycles, every token has a `$type` (inherited or own), names follow the convention. Fail the build on any error.

## 3. Keeping the design tool in step

Choose one direction of authority and generate the other side:

| Authority | Flow | Fits |
|---|---|---|
| Code is the source | Token files publish into the design tool's variables (a plugin or script) | Engineering-led teams, several platforms |
| Design file is the source | Variables export to token JSON (a token plugin or the tool's API), committed through a pull request that runs the validators | Design-led teams with one product |

Never let both sides accept hand edits; the second edit silently wins.

**Mapping to Figma variables.** Three collections mirror the three tiers: primitives, semantic (aliasing primitives), component (aliasing semantic). Themes, brands and densities become modes on the semantic collection, so switching a frame's mode previews the theme. Hide primitives from publishing so designers pick roles. Use variable scoping (fill, stroke, text, gap, radius) so a spacing token cannot be applied as a color. Text styles and effect styles cover what variables cannot yet express well (composite typography, multi-layer shadows); keep their names identical to the token names.

**Access.** The design tool's REST endpoints for reading and writing variables have been limited to some plans; check before planning an automated sync. Plugins and an exported JSON file are the fallback. When the design tool's MCP server is connected to the agent, use it to read frames, variables and screenshots instead of guessing from images.

**Component parity.** For each component, compare the design-file variant properties with the code props: every variant, size and state in code exists in the file and the reverse. Link design components to their code files (the tool's code-linking feature) so developers land on the real implementation. Report drift as a table: component, missing in design, missing in code, value mismatches.

**Drift check:** every color, number and text style used in the design file resolves to a variable or style; raw values ("detached" fills) are findings.

## 4. Versioning and change

Treat the token package and component library as public APIs with semantic versioning:

| Change | Level | Examples |
|---|---|---|
| Breaking | Major | Token renamed or removed; prop removed or renamed; default variant changed; component anatomy changed so overrides break; a value change outside the agreed tolerance |
| Additive | Minor | New token, component, variant, size or optional prop; new theme |
| Fix | Patch | Contrast fix within tolerance, bug fix, documentation, a value nudge no consumer would notice |

**Contribution path.** A pattern starts local in one product. It becomes a candidate when at least two products need it, with a written proposal (problem, screens, alternatives considered, accessibility notes). It becomes core only after it meets the full component bar in [component-specs-and-design-qa.md](component-specs-and-design-qa.md). One owner, or a small rotating group, decides; decisions are written down with reasons.

**Deprecation.** Mark the token or prop deprecated with the reason, the replacement and the removal version (DTCG allows `$deprecated` with an explanatory string); keep it working for at least one minor release while builds warn on use; publish a migration table (old name, new name, notes) and a codemod where the change is mechanical; remove only in a major release.

```json
{ "color": { "text": { "subtle": { "$value": "{color.text.secondary}", "$deprecated": "Use color.text.secondary. Removed in 4.0." } } } }
```

**Communication.** Every release has a changelog grouped by breaking, added, fixed and deprecated, with before and after screenshots for visible changes. Announce majors ahead of time with the migration guide; give teams a window to upgrade.

## 5. Migrating to or from another system

Map by role, not by name, across six axes: color roles, type scale, spacing unit, radius, elevation and motion.

1. **Audit** both sides: list each system's roles and values (the other library's theme file or documented tokens).
2. **Map:** a crosswalk table with your token, their token, and a note (exact, approximate, no equivalent). Where they lack a role you need, add a component token rather than overloading one of theirs.
3. **Choose the direction:**
   - *Adopt their look:* point your semantic tier at values matching theirs; your components stay.
   - *Build on their components:* theme their primitives with your tokens (most libraries expose a theme object or CSS variables; shadcn/ui components read CSS variables you define).
   - *Migrate between libraries:* add an alias layer so old and new names resolve to the same values, move screen by screen, then remove the alias layer.
4. **Verify** every mapped text pair for contrast in each theme, and confirm all states and dark mode survive the mapping: libraries often express hover and focus differently.

Headless libraries (behavior without styles) are the easiest base for a custom look; styled libraries are faster when their look is close to yours and slower to bend when it is not.

## 6. The direction file

Give people and AI design or coding tools a short `DESIGN.md` they can follow, next to the tokens:

```markdown
# Direction: assured, quiet, exact
Audience: finance teams reconciling accounts daily, on large monitors.
Mood word: assured. Motion: functional only (150-250 ms, no ambient loops).
Type: neutral grotesque for UI; tabular numerals on all figures; scale 12/14/16/20/24/32.
Color: cool neutral ground, one teal action color, status colors only for status.
Layout: 12-column grid, 1280 px max content width, dense tables before cards.
Shape: radius 6 for controls, 10 for panels; borders over shadows.
Never: gradients on surfaces, pill badges on headings, emoji icons, centered body text.
Tokens: tokens/*.json is the source; never write raw values.
```

When a request says "make it look like [a well-known company]", do not reproduce that company's system. Translate the request into traits ("near-black text on warm off-white, one saturated accent, generous whitespace, large tight headings, small uppercase labels avoided") and write those traits into the direction file. Mixing two looks is fine if the file says which source of traits owns which dimension.

## Done when

- [ ] A generated foundation has OKLCH ramps with sRGB fallbacks, semantic roles for light and dark, and every approved pair passing contrast before screens are built.
- [ ] One DTCG source builds every platform output; theme outputs are deltas; CI fails on unresolved aliases and on stale generated files.
- [ ] One direction of authority between code and the design tool is documented; design variables mirror the three tiers with modes; parity and drift reports exist.
- [ ] Every release has a version level and changelog; deprecations carry reason, replacement, removal version and a migration table.
- [ ] Migrations have a role-based crosswalk with contrast and state checks; a `DESIGN.md` records the direction in traits, not in another company's name.
