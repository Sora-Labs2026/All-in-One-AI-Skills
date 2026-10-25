# UI Distiller: Quality gate

Use after editing. This is a completion checklist, not a substitute for human testing.

## Functional and design checks

- [ ] The user's primary task is visible and actionable early.
- [ ] The strongest visual element corresponds to the most important fact or action.
- [ ] Every retained section has a distinct purpose and meaningful label.
- [ ] No decorative hero, generic copy, card wrapper, border, icon, or divider remains without a reason.
- [ ] Essential warnings, units, limitations, labels, errors, and secondary workflows are accessible.
- [ ] Typography, spacing, colors, surface treatments, and states are consistent with the brand.
- [ ] The screen feels distinctive to its real use case, not restyled using a universal preset.
- [ ] Content is data-faithful, no invented metrics or placeholder production claims.

## Accessibility and interaction

- [ ] Keyboard focus is visible and follows logical order.
- [ ] Text/background contrast is checked against WCAG 2.2 AA guidelines when possible.
- [ ] Functional icon-only controls have accessible names.
- [ ] Form fields retain persistent labels, helpful validation, and error associations.
- [ ] Links/buttons are semantically correct and distinguishable.
- [ ] Mobile targets are sufficiently large or appropriately spaced; no hover-only critical features.
- [ ] Changes respect reduced motion and any existing dark/light modes.
- [ ] Important content works at mobile widths and 200% zoom without unintended loss.

## Engineering and verification

- [ ] Existing routes, API calls, state, permissions, i18n, analytics and real interactions still work.
- [ ] Existing tests, lint, typecheck and build run as appropriate for the project; failures documented.
- [ ] Before/after visual inspection done if a working browser/screenshot environment exists.
- [ ] Verify representative loading, empty, error, and populated states if practicable.
- [ ] Only files in relevant scope are changed; no unrelated changes overwritten.

## Design self-critique

Ask yourself, in order:

1. What would a first-time user look at first? Is that the correct thing?
2. What would an experienced user look for? Can they reach it rapidly?
3. Can the user complete the main task faster than before?
4. What remains purely because it looks like a trendy UI template? (Detectors and replacements: `taste.md`.)
5. What can be removed without removing meaning, capability, trust or clarity?
6. Have I accidentally confused minimalism with hiding useful information?

If the interface is beautiful but answers these badly, iterate again.

## Reporting template

Use this compact format, grounded in what actually happened:

Changed: [routes/components, concrete hierarchy and visual improvements]
Removed/demoted: [substantive clutter]
Verified: [commands, viewports, interaction checks actually run]
Limitations: [only if tests or visual/interactive verification were not possible]
