# Product demo videos of a web interface

Read this to record a walkthrough of a web application: a feature demo for release notes or documentation, an onboarding tour, a stakeholder preview, a tutorial. The method scripts the browser with Playwright so the demo is repeatable: discover the real interface, rehearse every step, then record with a visible cursor and readable pacing, and finish the video in post. Playwright set-up and selectors are in `../../builder-tools/references/playwright-web-testing.md`; editing, captions and export are in `video-editing.md`; animated GIFs in `../../documents/references/animated-media.md`. Examples use Playwright 1.4x and later for Node.js (2024-2025).

Contents: choose the capture method · prepare a demo environment · discover · rehearse · record · pacing · finishing · privacy and secrets · accessibility · checks · done when.

## Choose the capture method

| Need | Method |
|---|---|
| Repeatable demos for docs and release notes, re-recorded every release | Playwright `recordVideo` (this file) |
| Marketing-quality footage with smooth zooms and high bitrate | A native screen recorder at high bitrate, or screenshots of each step animated in Remotion (`remotion-video.md`) |
| A few seconds for a README or a chat message | A short clip or GIF (`../../documents/references/animated-media.md`) |

Playwright records the page only (no browser chrome), at a fixed size, as WebM. Its encoder favors reliability over quality: fine for documentation, soft for a launch film.

## Prepare a demo environment

- **A demo account and seeded data:** fictional but plausible people, companies and figures whose totals add up (`COP-05`), clearly not real customers. Never record production data.
- **Freeze what changes:** fix the clock (`await page.clock.install({ time: new Date("2026-03-02T09:30:00") })`), locale, time zone and color scheme in the browser context, so dates and relative times are stable between recordings.
- **Remove noise:** cookie banners and chat widgets disabled for the demo environment, development overlays off, notifications off, feature flags set to the demoed state.
- **Sign in before recording:** create a saved session (`storageState`) in a setup step, so no password is typed on camera. If sign-in must be shown, use a demo account on a demo environment.

## Discover

Before scripting, open each page of the flow and list what is actually there; assumptions about the interface are the main reason demo scripts fail.

```js
// Lists visible interactive elements with their role and accessible name: the raw material for locators.
const controls = await page.locator("button, a[href], input, select, textarea, [role], [contenteditable=true]")
  .evaluateAll((els) => els.filter((e) => e.checkVisibility?.() ?? e.offsetParent !== null).map((e) => ({
    tag: e.tagName.toLowerCase(), role: e.getAttribute("role") || "", type: e.getAttribute("type") || "",
    name: (e.getAttribute("aria-label") || e.labels?.[0]?.textContent || e.textContent || "").trim().slice(0, 50),
    placeholder: e.getAttribute("placeholder") || "",
  })));
console.table(controls);
```

Note custom dropdowns versus native selects, fields that appear only after others are filled, buttons disabled until input is valid, and select options whose first value is a placeholder.

## Rehearse

Run the whole flow without recording, with every step addressed by role and name (`getByRole`, `getByLabel`), and fail loudly on the first missing element. Only when the rehearsal passes end to end, record.

```js
const steps = [
  { say: "Open the invoices list", act: (p) => p.getByRole("link", { name: "Invoices" }).click() },
  { say: "Create an invoice", act: (p) => p.getByRole("button", { name: "New invoice" }).click() },
  { say: "Choose the customer", act: (p) => p.getByLabel("Customer").selectOption("Harbor Supplies") },
  { say: "Send it", act: (p) => p.getByRole("button", { name: "Send invoice" }).click() },
];
// rehearsal: for (const s of steps) { await s.act(page); }   // throws on the first failing step
```

The same `steps` array drives the recording, so the rehearsal and the video cannot drift apart.

## Record

```js
// demo.mjs  -  node demo.mjs
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";

const W = 1280, H = 720;
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: W, height: H }, recordVideo: { dir: "out/raw", size: { width: W, height: H } },
  storageState: "demo-auth.json", locale: "en-GB", timezoneId: "Europe/London", colorScheme: "light",
});
await context.addInitScript(() => {          // runs in every page before its own scripts, also after navigation
  if (window !== window.top) return;
  addEventListener("DOMContentLoaded", () => {
    const c = document.createElement("div");
    c.setAttribute("aria-hidden", "true");
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2l14 8-6 1.5L8 18z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    c.style.cssText = "position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px)";
    document.documentElement.append(c);
    addEventListener("mousemove", (e) => { c.style.transform = `translate(${e.clientX - 3}px, ${e.clientY - 2}px)`; }, true);
    addEventListener("mousedown", () => c.animate([{ scale: 1 }, { scale: 0.82 }, { scale: 1 }], 180), true);
  });
});
const page = await context.newPage();
const video = page.video();
const t0 = Date.now(), cues = [];            // steps: from the rehearsal; holdFor: see "Pacing"
await page.goto("https://demo.example.test/");
await page.waitForTimeout(1200);
for (const s of steps) {
  const start = (Date.now() - t0) / 1000;
  await s.act(page);
  await page.waitForTimeout(holdFor(s.say));
  cues.push({ start, end: (Date.now() - t0) / 1000, text: s.say });
}
await context.close();                       // the video is finalized when the context closes
await video.saveAs("out/raw.webm");          // a stable name instead of Playwright's generated one
writeFileSync("out/steps.json", JSON.stringify(cues, null, 2));
await browser.close();
```

- **Move before clicking:** Playwright's `click()` moves the mouse instantly. For visible motion, get the element's box and call `page.mouse.move(x, y, { steps: 20 })` first, pause about 300ms, then click.
- **Type visibly** with `locator.pressSequentially(text, { delay: 40 })` instead of `fill()`.
- **Scroll smoothly:** `page.mouse.wheel(0, 400)` in a few steps, or `scrollIntoView({ behavior: "smooth" })`, followed by a pause.
- **Pop-ups and new tabs** record to separate files; capture them explicitly or keep the flow in one tab.
- The cursor overlay uses `innerHTML`; on pages with a strict Trusted Types policy, build the SVG with `document.createElementNS` instead.

## Pacing

- Hold each new state about one second plus the time to read the new text at a relaxed pace (roughly three words per second): `const holdFor = (t) => 1000 + (t.split(" ").length / 3) * 1000;`.
- Pause about two seconds after a page loads and three after the final result, so viewers see the outcome.
- One action at a time; the cursor travels at a speed the eye can follow.
- Keep the whole demo short: a single feature in under a minute or two; split longer tours into chapters.

## Finishing

```bash
ffmpeg -ss 0.8 -i out/raw.webm -c:v libx264 -crf 18 -pix_fmt yuv420p -r 30 -movflags +faststart -an out/demo.mp4
```

- Trim the blank frames before the first page paints (the `-ss` above), and cut dead waits.
- **Captions from the step log:** turn `steps.json` into WebVTT (shift the times by the trim), check the alignment by eye, and adjust.

```python
import json
cues, trim = json.load(open("out/steps.json")), 0.8
ts = lambda s: f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:06.3f}"
with open("out/demo.vtt", "w") as f:
    f.write("WEBVTT\n\n")
    for i, c in enumerate(cues, 1):
        f.write(f"{i}\n{ts(max(0, c['start'] - trim))} --> {ts(max(0, c['end'] - trim))}\n{c['text']}\n\n")
```

- **Zoom in** on small controls in post (an editor or a Remotion composition that crops and scales the recording over time), rather than recording at a zoomed browser level that changes the layout.
- **Narration** can be recorded or synthesized afterwards from the same step texts (`hosted-media-generation.md` for synthetic voices and their disclosure); add music only at a low level under it.
- Name files with the app version and date: `invoices-send-v2.14-2026-03-02.mp4`.

## Privacy and secrets

- Demo accounts and demo data only; no real names, emails, addresses or customer records anywhere in frame, including autocomplete suggestions and notifications.
- No credentials typed on camera; tokens and API keys never visible (developer tools closed, query strings without tokens).
- Before publishing, step through the video for anything sensitive in corners: browser autofill, account menus, URLs, toasts.

## Accessibility

- Captions for every narrated or labeled step, delivered as a sidecar file and burned in for feeds that autoplay muted.
- Narration describes what happens on screen (audio description); a step list or written tutorial accompanies the video.
- No flashing, fast cursor whips or rapid zoom changes (`MOT-21`); keep zoom moves slow.

## Checks

1. The rehearsal passes end to end immediately before recording.
2. `ffprobe` confirms duration, size, frame rate and codec of the final file.
3. Watch the whole video at 100%: every step visible, the cursor never jumps, no spinner left on screen.
4. Captions are in sync and spelled correctly.
5. A privacy pass found no real data, credentials or tokens.
6. The demo matches the current release: re-run the script after interface changes rather than editing an old video.

## Done when

- The demo is generated by a script that rehearses and records from the same steps, against a demo environment with fixed data and time.
- The video is trimmed, captioned, exported to the destination's format, and named with the app version and date.
- Privacy and accessibility checks passed, and the script is kept next to the video for the next release.
