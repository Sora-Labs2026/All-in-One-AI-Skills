# Data-dense and application-specific surfaces

Read only the relevant entries in `../references/pattern-library.md`. Related patterns: 1, 26-28, 31-34, 36, 41, 47, 49, 53-54, 56-57, 62-64, 69.

## Tables and dashboards

Right-align numeric values and use tabular numerals, left-align labels, state units/currency/date meaning and align sortable headings. Choose row density from tasks; make keyboard actions discoverable, not hover-only. On narrow screens use labeled rows or intentional horizontal scrolling with sticky identifiers. For changing feeds, stable sorts plus cursor pagination prevent duplicates; preserve active page/filter in URL where appropriate. Prefer meaningful current task/KPI over generic metric mosaics.

## Scheduling/calendar

7-column (or configured locale week) grids, time labels, event vertical position and height correspond to start/end, stable collision layout. Support overlap, all-day events, timezone/DST, unavailable periods, clear event tooltips and keyboard-accessible list view. For date selection, preserve cross-month ranges and consistent inclusive/exclusive semantics.

## Kanban and drag

Show lifted preview, placement placeholder, reversible actions and unambiguous column ownership. Track item ordering server-side and handle concurrent updates; distinguish board snap zones from free-canvas drop locations. Keep columns manageable (collapse/compact before making them unintelligible) and support keyboard move.

## Chat/collaborative editing

Group consecutive sender messages, meaningful timestamps and date boundaries; scroll anchor on new messages, distinct unread indicator, proper multiline composer. Do not fake presence/typing. AI edit proposals should be labeled, attributable and reversible; preserve version history, sources and user choice.

## Command/search/context menus

Rank exact/recent commands and result relevance above decoration; mark shortcut hints and destructive operations. Restore focus after close; do not expose privileged command effects without server authorization. Menus fit viewport and have keyboard/touch equivalents.

## Uploads, voice and responsive mobile sheets

Per-file queue, retries and independent failures. Recording state is truthful and consented. Sheet/overlay scroll coordination must not cause accidental close of critical task. Link toast feedback to real async responses.

## Verify

Bulk data, empty results, changed data while paging, RTL, long strings, concurrent updates, disconnected/slow backend, zoom and at least one mobile viewport. Guard financial, medical and admin data carefully.
