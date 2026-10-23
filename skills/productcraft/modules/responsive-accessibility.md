# Responsive behavior, accessibility and internationalization

Related patterns in `../references/pattern-library.md`: 10-11, 15-17, 21, 27, 32, 39, 41-42, 45, 48, 50-51, 54, 60, 64-66. Touch targets, safe areas and contrast values: `MOB` and `COL` rules in `../references/ui-rules/`.

- Use semantic HTML and proper ARIA only when native elements cannot represent the interaction. Separate focused, hovered, pressed, selected and disabled semantics.
- Test pointer, touch, keyboard, screen reader, reduced motion, zoom, high-contrast/light/dark where applicable; do not put essential information behind hover.
- Make mobile hit areas generously sized with sufficient spacing, accessible names and visible tap response. Reachability matters more than animation.
- Choose dialogs for interruptive decisions and bottom sheets for contextual tasks when device conventions favor them. Close behavior must not discard unsaved work silently.
- Responsive grids and tables reorganize meaningful content rather than simply hiding columns. At narrow widths ensure primary action, table identifiers and dates stay visible.
- Make validation messages announced, preserve label text and reserve space for error messages.
- Localize beyond translated strings: accommodate 30-50% expansion where relevant, RTL logical properties, mixed-direction text and calendar locale. Avoid mirroring icons whose meaning is directional only in one semantic context.
- View transitions and other newer browser APIs are progressive enhancements with reduced-motion and no-support fallback.

Useful acceptance tests: 320px width without clipped primary tasks; tab through entire flow; VoiceOver/TalkBack or another accessible testing route; `prefers-reduced-motion`; German-length labels and Arabic/RTL stress where applicable.
