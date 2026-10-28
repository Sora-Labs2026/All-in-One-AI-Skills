# ProductCraft reference screens

These are original example screens showing ProductCraft's UI rules applied to real product surfaces. There are 49 pages and 170 screens: 21 dashboards and 28 pages of component and flow versions.

Each page is plain HTML and CSS. A little JavaScript adds real behavior: switches, sorting, segmented controls, code entry, command palettes, dialogs, drawers and collapsing sidebars. No page makes external requests. Every page cites the rule IDs it demonstrates, in its top comment and under each version.

Use these pages as **reference code, not as a theme**:

- Read the version that matches the task, then rebuild the pattern with the project's own components and tokens.
- Swap `tokens.css` values for the project's tokens and replace the sample data. Keep the semantics, states and rule-driven details: labels, roles, `aria-*` attributes, focus rings, tabular numbers, signed deltas and status words.
- Never ship the "Sora" sample brand, the sample people or the sample numbers in a real product.
- Open any page directly in a browser. `gallery.css` holds only the sheet chrome (version labels, phone and window frames) and is not part of the patterns. Some pages set a page-level accent in their own `<style>`, and every pair they add is contrast-checked.

All names, companies, prices, patients and data are fictional. Emails use `example.com`, phone numbers use the `555-01xx` range, and none of the figures are advice.

## Dashboards

Every dashboard leads with the decision it supports (SCR-01) and keeps one focal point (LAY-05). Charts answer one question and reveal exact values (CMP-18), and status always shows in words as well as color (COL-07).

| Page | Domain and main question | Notable patterns |
|---|---|---|
| `dashboard-v1.html` | Light analytics: how is revenue doing? | Sidebar, KPI tiles, bar chart with tooltip, channel donut, order table with status tabs |
| `dashboard-v2.html` | Dark operations: what needs action on the floor? | Collapsed rail, live KPIs, throughput vs target, zone capacity, exception queue |
| `dashboard-v3.html` | Bento store overview: will we hit the monthly goal? | Top navigation, goal ring, sparkline tiles, ranked bars, checklist, activity feed |
| `dashboard-v4.html` | Personal finance: am I on budget this month? | Spend vs even pace, categories against budget, card controls, upcoming bills |
| `dashboard-v5.html` | Sales CRM: will we hit the quarter? | Highlighted forecast tile, quota bullet chart, stage funnel, leaderboard, sortable deals |
| `dashboard-v6.html` | Learning: what should I study next? | "Up next" with a reason, course progress, skill levels, calm study rhythm, deadlines |
| `dashboard-v7.html` | Property management: which buildings need attention? | Occupancy gauges, rent collected vs due, docked assistant with period and source, maintenance triage |
| `dashboard-v8.html` | Workspace admin: who has access and what changed? | Seats meter, filter chips, people cards, pending invites, audit panel |
| `dashboard-v9.html` | Credit health (dark): what moves my score? | Banded score with meaning, history with range control, factor impacts, one recommended action |
| `dashboard-v10.html` | Creator analytics (dark): what content is working? | Daily views vs last month, retention bars against channel average, earnings that sum |
| `dashboard-v11.html` | Fitness coaching: am I on track this week? | Goal rings, week strip, today's schedule, body trends with units, coach note |
| `dashboard-v12.html` | Smart home (dark): is the house OK and what uses energy? | Attention card with a fix, room tabs with real switches, thermostat stepper, live power use |
| `dashboard-v13.html` | Logistics dispatch: which deliveries are late and why? | Abstract route map with numbered late stops, causes, ETA vs promised window, vehicle load |
| `dashboard-v14.html` | Grid load forecast: will demand exceed capacity? | Answer tile, forecast band vs capacity line, peak-risk alerts, generation mix |
| `dashboard-v15.html` | Accounts payable: what do I approve and pay? | Master-detail bills, line items that add up, approval steps, cash out by week |
| `dashboard-v16.html` | Clinic monitoring: which patients need attention now? | Urgency-sorted patients, out-of-range flags with ranges, vitals band chart, care tasks |
| `dashboard-v17.html` | People operations: what needs HR action this week? | Scope bar with entity, location and period; deadline strip; leave approvals with day-by-day coverage against minimum staffing; payroll run that adds up, with blockers; onboarding checklist that clears payroll blockers live |
| `dashboard-v18.html` | Security operations: what needs a human security decision right now? | Production scope bar with a hazard-striped edge, approval cards with evidence, blast radius and undoable automatic steps, calibrated confidence with its basis, live feed that holds new events behind a button, attack-path lanes, rates with denominators, playbook audit trail |
| `dashboard-v19.html` | Wind farm: which turbines are losing energy and why? | Lost energy against expected with causes that add up, turbines sorted by lost MWh with automated-stop evidence, power curve with bin averages, direction bars instead of a wind rose, stops matched to a low-wind forecast with a work-limit slider and a confirm dialog |
| `dashboard-v20.html` | Small-business cash: how much cash do we have, and what is coming in and going out? | Scope strip with entity, currency and period, total cash split by account with runway and its basis, money in vs out by month with net values, masked company cards with freeze confirmation, filterable transactions, revenue by year as bars, report named for scope and period |
| `dashboard-v21.html` | Smart-home wall panel: what is on, and what is using power right now? | Live watts with ranked loads that sum to the total and cost per hour, device tiles with switch, slider and temperature stepper, scene radios, unlock dialog that restates door and home, hourly energy bars with a table, opt-in Home or Away presence |

## Components and flows

| Page | Versions | Main rules |
|---|---|---|
| `sign-in.html` | Split-screen sign-in with SSO and passkey | SCR-12, FRM-18, FRM-19, BTN-13 |
| `auth.html` | v1 centered card · v2 mobile · v3 sign-up with live password rules · v4 password reset · v5 dark returning account | SCR-12, FRM-18, FRM-19, COP-07 |
| `auth-2.html` | v6 magic link · v7 passkey first · v8 email first with SSO routing · v9 two-step setup and recovery codes · v10 account picker · v11 mobile biometrics with PIN fallback | SCR-12, FRM-18, BTN-13, COP-12 |
| `otp.html` | v1 live code entry · v2 checking · v3 verified · v4 wrong code · v5 mobile SMS · v6 PIN create and confirm | FRM-17, FBK-13, FRM-20, COP-07 |
| `settings.html` | Security settings: grouped switch rows, sessions, checkup progress, danger zone | SCR-03, FRM-22, FBK-08, NAV-14 |
| `navigation.html` | v1 expanded sidebar · v2 collapsed rail with tooltips · v3 top bar with dropdown and in-place search · v4 dark sidebar with promo card · v5 breadcrumbs, tabs and pagination | NAV-03, NAV-08, NAV-12, NAV-13, NAV-15, NAV-17 |
| `tab-bars.html` | v1 classic · v2 floating · v3 detached create button · v4 sliding indicator · v5 dark expanding pill · anatomy spec | NAV-11, NAV-02, MOB-01, MOB-04 |
| `search.html` | v1 command palette · v2 results with facets · v3 grouped results with highlights · v4 no results with a way forward · v5 mobile recents and suggestions · v6 inline autocomplete | NAV-12, SCR-07, FRM-26, CMP-25 |
| `charts.html` | v1 highlighted bar chart · v2 area chart with range and crosshair · v3 donut with value legend · v4 score gauge · v5 ranked bars · v6 dark KPI sparklines | CMP-18, CMP-17, COL-07, TYP-09 |
| `charts-2.html` | v7 stacked columns · v8 forecast band with annotation · v9 calendar heatmap · v10 conversion funnel · v11 bullet charts in a table · v12 sparkline table on a shared scale | CMP-18, CMP-19, COP-10, ENG-07 |
| `cards.html` | v1 KPI tiles · v2 list rows by date · v3 feed post · v4 product cards · v5 carousel · v6 dark notifications | CMP-17, CMP-20, CMP-21, CMP-22, CMP-29 |
| `cards-2.html` | v7 contact card · v8 flight fare with conditions · v9 weather with units · v10 task with checklist · v11 dark podcast player · v12 stats against a benchmark | CMP-15, CMP-30, CMP-31, COP-11 |
| `tables.html` | v1 sortable with sticky header · v2 selection and bulk actions · v3 inline edit with validation · v4 dark expandable rows · v5 density and column menu · v6 phone cards | CMP-19, ENG-06, FRM-11, SCR-02 |
| `calendar.html` | v1 week strip with slots · v2 month range · v3 two-thumb time window · v4 dark agenda · v5 booking bar | FRM-24, FRM-08, CMP-16, COL-14 |
| `buttons.html` | v1 hierarchy light and dark · v2 every state · v3 async purchase · v4 download progress · v5 delete with undo · v6 icon, split and provider buttons | BTN-01, BTN-02, FBK-10, FBK-11, FBK-15, ENG-03 |
| `buttons-2.html` | v7 toggle buttons and groups · v8 like, save and follow · v9 copy with confirmation · v10 mobile speed dial · v11 dialog button order and typed delete · v12 pagination and load more | CMP-23, BTN-15, ENG-03, COP-09 |
| `form-controls.html` | v1 field states · v2 dark switch rows · v3 sliders with inputs · v4 segmented control and chips · v5 swatches and stepper · v6 plan tiles and checkboxes | FRM-10, FRM-22, FRM-08, CMP-23, CMP-24, FRM-09 |
| `form-controls-2.html` | v7 searchable combobox · v8 tag input · v9 star rating as radios · v10 image upload with preview · v11 phone and address with autocomplete · v12 multi-step form with review | FRM-07, FRM-27, FRM-05, FRM-14 |
| `overlays.html` | v1 dropdown menu · v2 dark context menu · v3 destructive dialog · v4 side drawer with inert page · v5 filter popover · v6 phone bottom sheet | CMP-12, CMP-14, ENG-05, FBK-08, SCR-20 |
| `feedback.html` | v1 banners · v2 toasts · v3 upload states · v4 progress and loaders · v5 skeleton and loaded card · v6 notifications panel | FBK-03, FBK-04, FRM-21, FBK-12, FBK-14 |
| `commerce.html` | v1 product grid · v2 buy box · v3 bag drawer · v4 one-page checkout · v5 order confirmation | CMP-21, SCR-15, SCR-16, SCR-21, BTN-14 |
| `pricing.html` | v1 three-tier pricing · v2 mobile paywall · v3 comparison table · v4 in-app upgrade card | BTN-06, SCR-17, COP-11, NAV-10 |
| `landing.html` | v1 product hero with preview · v2 dark split hero with signup · v3 bento features · v4 honest social proof · v5 pricing teaser and FAQ · v6 closing CTA and footer | SCR-22, LAY-14, COP-13, BTN-01 |
| `onboarding.html` | v1 welcome · v2 one question per step · v3 personalized result · v4 empty states · v5 404 · v6 403 with request access | SCR-10, SCR-14, FBK-09, SCR-18 |
| `onboarding-2.html` | v7 setup checklist · v8 tour step popover · v9 CSV import with column mapping · v10 invite teammates · v11 notification priming · v12 first success with next step | SCR-09, SCR-14, CMP-31, FBK-07 |
| `mobile-apps.html` | v1 wallet · v2 ride with bottom sheet · v3 health summary · v4 habit tracker · v5 music player | SCR-20, SCR-23, CMP-30, CMP-31, NAV-11 |
| `messaging.html` | v1 desktop chat · v2 assistant empty state · v3 mobile chat with tap options · v4 assistant docked beside a dashboard | SCR-19, SCR-24, MOB-11, FBK-09 |
| `brand.html` | v1 mark on a grid · v2 clear space and misuse · v3 lockups · v4 app icon sizes · v5 palette with measured pairs · v6 tone and type | BRD-01..05, COL-01, COL-11 |

Shared files:

- `tokens.css`: spacing, radius, type and color tokens for light, dark and a teal accent, plus base button, pill, delta, avatar, card and segmented styles. Every text and background pair is contrast-checked.
- `gallery.css`: sheet layout, version labels and generic phone and window frames.

## Screenshots

Screenshots of every page live in the repository at `docs/screens/`, outside the skill package, with half-size thumbnails in `docs/screens/thumbs/`. To regenerate them after editing a page, run `node scripts/screenshots.cjs [page...]` from the repository root; this needs Playwright with Chromium. A page sets its capture size in `<meta name="screenshot" content="width=1440,...">`.
