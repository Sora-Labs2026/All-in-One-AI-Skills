# ProductCraft reference screens

Original example screens that show ProductCraft's UI rules applied to real product surfaces. Each page is plain HTML and CSS with a little JavaScript for real behavior (switches, segmented controls, code entry, collapsing sidebars). There are no external requests. Each page cites the rule IDs it demonstrates, in its top comment and under every version.

Use these pages as **reference code, not as a theme**:

- Read the version that matches the task, then rebuild the pattern with the project's own components and tokens.
- Swap `tokens.css` values for the project's tokens and replace the sample data. Keep the semantics, states and rule-driven details: labels, roles, `aria-*` attributes, focus rings, tabular numbers, signed deltas and status words.
- Never ship the "Sora" sample brand, the sample people or the sample numbers in a real product.
- Open any page directly in a browser. `gallery.css` holds only the sheet chrome (version labels, phone and window frames) and is not part of the patterns.

All names, companies, prices and data are fictional. Emails use `example.com` and phone numbers use the `555-01xx` range.

## Pages

| Page | Versions | Main rules |
|---|---|---|
| `dashboard-v1.html` | Light analytics dashboard: sidebar, KPI tiles, bar chart with tooltip, channel donut, order table with status tabs | SCR-01, CMP-17, CMP-18, CMP-19, NAV-08 |
| `dashboard-v2.html` | Dark operations dashboard: collapsed rail, live KPIs, throughput chart against target, zone capacity, exception queue | SCR-01, DRK-01..04, DRK-09, FBK-18, NAV-13 |
| `dashboard-v3.html` | Teal bento overview: top navigation, goal ring, sparkline tiles, ranked bars, checklist, activity feed | LAY-14, CMP-26, CMP-31, CMP-29, FBK-06 |
| `charts.html` | v1 highlighted bar chart · v2 area chart with range and crosshair · v3 donut with value legend · v4 score gauge · v5 ranked bars · v6 dark KPI sparklines | CMP-18, CMP-17, COL-07, TYP-09 |
| `cards.html` | v1 KPI tiles · v2 list rows by date · v3 feed post · v4 product cards · v5 carousel · v6 dark notifications | CMP-17, CMP-20, CMP-21, CMP-22, CMP-29 |
| `calendar.html` | v1 week strip with slots · v2 month range · v3 two-thumb time window · v4 dark agenda · v5 booking bar | FRM-24, FRM-08, CMP-16, COL-14 |
| `navigation.html` | v1 expanded sidebar · v2 collapsed rail with tooltips · v3 top bar with dropdown and in-place search · v4 dark sidebar with promo card · v5 breadcrumbs, tabs and pagination | NAV-03, NAV-08, NAV-12, NAV-13, NAV-15, NAV-17 |
| `tab-bars.html` | v1 classic · v2 floating · v3 detached create button · v4 sliding indicator · v5 dark expanding pill · anatomy spec | NAV-11, NAV-02, MOB-01, MOB-04 |
| `settings.html` | Security settings: grouped switch rows, sessions, checkup progress, danger zone | SCR-03, FRM-22, FBK-08, NAV-14 |
| `sign-in.html` | Split-screen sign-in with SSO and passkey | SCR-12, FRM-18, FRM-19, BTN-13 |
| `auth.html` | v1 centered card · v2 mobile · v3 sign-up with live password rules · v4 password reset · v5 dark returning account | SCR-12, FRM-18, FRM-19, COP-07 |
| `otp.html` | v1 live code entry · v2 checking · v3 verified · v4 wrong code · v5 mobile SMS · v6 PIN create and confirm | FRM-17, FBK-13, FRM-20, COP-07 |
| `buttons.html` | v1 hierarchy light and dark · v2 every state · v3 async purchase · v4 download progress · v5 delete with undo · v6 icon, split and provider buttons | BTN-01, BTN-02, FBK-10, FBK-11, FBK-15, ENG-03 |
| `form-controls.html` | v1 field states · v2 dark switch rows · v3 sliders with inputs · v4 segmented control and chips · v5 swatches and stepper · v6 plan tiles and checkboxes | FRM-10, FRM-22, FRM-08, CMP-23, CMP-24, FRM-09 |
| `feedback.html` | v1 banners · v2 toasts · v3 upload states · v4 progress and loaders · v5 skeleton and loaded card · v6 notifications panel | FBK-03, FBK-04, FRM-21, FBK-12, FBK-14 |
| `commerce.html` | v1 product grid · v2 buy box · v3 bag drawer · v4 one-page checkout · v5 order confirmation | CMP-21, SCR-15, SCR-16, SCR-21, BTN-14 |
| `pricing.html` | v1 three-tier pricing · v2 mobile paywall · v3 comparison table · v4 in-app upgrade card | BTN-06, SCR-17, COP-11, NAV-10 |
| `mobile-apps.html` | v1 wallet · v2 ride with bottom sheet · v3 health summary · v4 habit tracker · v5 music player | SCR-20, SCR-23, CMP-30, CMP-31, NAV-11 |
| `messaging.html` | v1 desktop chat · v2 assistant empty state · v3 mobile chat with tap options · v4 assistant docked beside a dashboard | SCR-19, SCR-24, MOB-11, FBK-09 |
| `onboarding.html` | v1 welcome · v2 one question per step · v3 personalized result · v4 empty states · v5 404 · v6 403 with request access | SCR-10, SCR-14, FBK-09, SCR-18 |
| `brand.html` | v1 mark on a grid · v2 clear space and misuse · v3 lockups · v4 app icon sizes · v5 palette with measured pairs · v6 tone and type | BRD-01..05, COL-01, COL-11 |

Shared files:

- `tokens.css`: spacing, radius, type and color tokens for light, dark and a teal accent, plus base button, pill, delta, avatar, card and segmented styles. Every text and background pair is contrast-checked.
- `gallery.css`: sheet layout, version labels and generic phone and window frames.

## Screenshots

Screenshots of every page live in the repository at `docs/screens/`, outside the skill package. To regenerate them after editing a page, run `node scripts/screenshots.cjs [page...]` from the repository root; this needs Playwright with Chromium. A page sets its capture size in `<meta name="screenshot" content="width=1440,...">`.
