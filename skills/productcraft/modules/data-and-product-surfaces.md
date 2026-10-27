# Data-dense and application-specific surfaces

Read only the relevant entries in `../references/pattern-library.md`. Related patterns: 1, 26-28, 31-34, 36, 41, 47, 49, 53-54, 56-57, 62-64, 69. Dashboard, settings and search screens: `SCR` rules in `../references/ui-rules/screen-patterns.md`.

## Tables and dashboards

Right-align numeric values and use tabular numerals, left-align labels, state units/currency/date meaning and align sortable headings. Choose row density from tasks; make keyboard actions discoverable, not hover-only. On narrow screens use labeled rows or intentional horizontal scrolling with sticky identifiers. For changing feeds, stable sorts plus cursor pagination prevent duplicates; preserve active page/filter in URL where appropriate. Prefer meaningful current task/KPI over generic metric mosaics.

## Charts: pick the form from the question

Start from the question the chart answers. A single number that matters on its own is a KPI tile (`CMP-17`), and values people look up or compare exactly belong in a table (`CMP-19`). Every chart then follows `CMP-18`: a title, a one-line summary, labeled axes, exact values on hover and keyboard focus, and a table alternative.

| Question | Form | Change the form when |
|---|---|---|
| How did it change over time? | Line chart; one to four series, the key one highlighted | Only a few points: show the numbers. So many series that the lines tangle: small multiples, or a picker with one series highlighted |
| Which is largest, and how do they rank? | Bar chart sorted by value; horizontal when labels are long | A long tail of categories: the top ten plus "Other", or a sortable table |
| What share of the whole? | One stacked bar, or a donut with five parts at most, each labeled with its value | More parts, or shares compared across groups: 100% stacked bars |
| How are values spread? | Histogram; box plots to compare groups | Few values: a dot or strip plot that shows every point |
| Do two measures move together? | Scatter plot; a fitted line only if you computed the fit | Thousands of overlapping points: transparency, hexagonal bins or a density plot |
| Where does activity cluster across two dimensions (day by hour)? | Heatmap with a sequential color scale and a legend | Exact comparison needed: small multiples of bars |
| How close is it to the target? | Progress bar or bullet chart with the target marked, plus the number | Avoid gauge dials, which take space and are hard to read precisely |
| Where do people drop out of a sequence of steps? | Horizontal bars per step, labeled with step-to-step conversion | Paths that branch: a table of steps with counts and conversion |

Rules that keep charts honest:
- Bars and areas start at zero, because their length or area is the value. A line chart may zoom into a range if the axis labels make the zoom obvious.
- No dual y-axes; they suggest a relationship the data may not have. Use two charts that share the x-axis.
- No 3D, no pie with many slices, no gradients or shadows on data marks.
- Neutral color for context and one accent for the point (`COL-02`); a sequential palette for magnitude; a diverging palette only around a meaningful midpoint such as zero or the target; never color as the only encoding (`COL-07`).
- A logarithmic axis only when it is labeled as such and the audience reads one.
- Large series: aggregate on the server to what the chart can show (about one point per pixel column), and draw thousands of marks on a canvas rather than as SVG elements.

- Charts made in analysis code (notebooks, reports, shared HTML, papers) rather than in the product UI: `data-engineering/references/plotting.md` and `data-engineering/references/publication-figures.md`, which apply these same honesty rules.

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
