# Testing web apps with Playwright

Read this to check a web app in a real browser: start and stop its server, drive it with robust selectors, wait correctly, take screenshots, and fail on console and network errors. Examples use Playwright Test (JavaScript/TypeScript, version 1.56); a Python equivalent follows.

Contents: choose the setup · start and stop the server · selectors · waiting · screenshots · console and network errors · simulating failures · signed-in tests · debugging and flakiness · Python · done when.

## Choose the setup

| Situation | Use |
|---|---|
| The project has, or should have, an end-to-end suite | Playwright Test: `playwright.config` + `tests/*.spec.ts`, run with `npx playwright test` |
| Python project with pytest | `pytest-playwright` (`page` fixture) |
| One-off check: does the page load cleanly, what does it look like at 390 px | A short standalone script (below), deleted or kept under `scripts/` |
| A static HTML file with no build or server | `page.goto('file:///absolute/path/index.html')`; serve it over HTTP instead if it fetches data or uses modules |

Check before installing: `npx playwright --version` (or `python3 -c "import playwright"`) and whether browsers are present. Installing Playwright and its browsers downloads large binaries; ask first, and use the project's package manager and lock file.

## Start and stop the server

Let the runner own the server, so it is started once, awaited until it answers, and always stopped:

```javascript
// playwright.config.js
const { defineConfig, devices } = require('@playwright/test');
const PORT = Number(process.env.PORT || 4173);

module.exports = defineConfig({
  testDir: './tests',
  forbidOnly: !!process.env.CI,                 // a stray test.only fails CI
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,   // the project's real dev or preview command
    url: `http://127.0.0.1:${PORT}/`,           // polled until it answers; better than waiting for a port
    reuseExistingServer: !process.env.CI,       // reuse a server you already started locally
    timeout: 120_000,
  },
});
```

- Use the command the project documents (`npm run dev`, `npm run preview` after a build, `python manage.py runserver`). A production build (`build` then `preview`) catches more real problems than a dev server.
- Pass a fixed port and make the server fail if it is taken (`--strictPort` for Vite), so tests never hit a different app on a fallback port.
- For several services, `webServer` accepts an array (API and frontend), each with its own `url`.
- Point tests at local or test data only: a test database, seeded fixtures, fake payment and email providers. Never run end-to-end tests against production or real customer accounts.

Standalone script with a manual lifecycle (start in its own process group so child processes die too, wait for HTTP, always clean up):

```javascript
// quick-check.mjs  (node quick-check.mjs; exits 1 when the page logs errors)
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';

const URL_ = 'http://127.0.0.1:4174/';
const server = spawn('npm', ['run', 'preview', '--', '--port', '4174', '--strictPort'], { stdio: 'ignore', detached: true });

async function waitForHttp(url, ms = 30_000) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    try { if ((await fetch(url)).status < 500) return; } catch {}
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`no answer from ${url} within ${ms} ms`);
}

const errors = [];
let browser;
try {
  await waitForHttp(URL_);
  browser = await chromium.launch();
  for (const [name, viewport] of [['desktop', { width: 1280, height: 800 }], ['mobile', { width: 390, height: 844 }]]) {
    const page = await browser.newPage({ viewport });
    page.on('console', (m) => m.type() === 'error' && errors.push(`${name} console: ${m.text()}`));
    page.on('pageerror', (e) => errors.push(`${name} exception: ${e.message}`));
    page.on('response', (r) => r.status() >= 400 && errors.push(`${name} HTTP ${r.status()} ${r.url()}`));
    await page.goto(URL_);
    await page.getByRole('heading', { level: 1 }).first().waitFor();
    await page.screenshot({ path: `shot-${name}.png`, fullPage: true });
    await page.close();
  }
} finally {
  await browser?.close();
  try { process.kill(-server.pid, 'SIGTERM'); } catch {}   // negative pid: the whole process group
}
console.log(errors.length ? errors.join('\n') : 'no errors');
process.exitCode = errors.length ? 1 : 0;
```

`npm run dev` starts a shell and a node process; killing only the parent leaves the server running and the port busy. After the run, confirm the port is free, for example `curl -s -o /dev/null http://127.0.0.1:4174/ && echo still running || echo stopped`.

## Selectors that survive redesigns

Prefer what a user perceives, in this order:
1. `page.getByRole('button', { name: 'Create account' })`: role plus accessible name; also checks the element is exposed to assistive technology.
2. `page.getByLabel('Email')` for form fields; `getByPlaceholder` only when there is no label (and add the label).
3. `page.getByText('Account created')` for non-interactive text.
4. `page.getByTestId('invoice-total')` when nothing user-visible is stable; agree on the attribute (`data-testid`) with the team.
5. CSS or XPath only as a last resort, and never long chains tied to layout (`div > div:nth-child(3) span`).

Scope instead of indexing: `page.getByRole('row', { name: /Acme/ }).getByRole('button', { name: 'Delete' })` rather than `.nth(4)`. Locators are strict: an action on a locator that matches two elements fails, which is what you want.

To discover names on an unfamiliar page without a display, print its accessibility tree: `console.log(await page.locator('main').ariaSnapshot())` gives lines such as `- button "Create account"` and `- textbox "Email"` that map directly to `getByRole`. If an element has no usable role or name, that is an accessibility defect to report (`../../responsive-accessibility.md`), not just a testing inconvenience.

## Waiting correctly

- Actions (`click`, `fill`, `check`) already wait for the element to be attached, visible, stable, enabled and able to receive events.
- Assert with web-first assertions, which retry until true or timeout: `await expect(page.getByRole('status')).toHaveText('Account created')`, `toBeVisible()`, `toHaveURL(/dashboard/)`, `toHaveCount(3)`.
- Do not sleep (`waitForTimeout`, `time.sleep`): it is slow when the app is fast and flaky when it is slow. Do not read a value once and compare it (`expect(await locator.textContent()).toBe(...)` does not retry).
- Avoid waiting for `networkidle` as a general "page ready" signal: apps with polling, analytics or websockets may never go idle, and an idle network does not mean the UI has rendered. Wait for the element or state the test needs.
- Wait for a specific request when the test is about it: `const resp = page.waitForResponse((r) => r.url().endsWith('/api/orders') && r.request().method() === 'POST');` before the click, then `await resp`.
- For conditions outside the DOM, poll: `await expect.poll(() => errors.length).toBe(0)`.
- Assert intermediate states that matter to users (a pending label before the result), so honest loading feedback stays tested.

## Screenshots

- `await page.screenshot({ path: testInfo.outputPath('checkout.png'), fullPage: true })` per state you need to see; `locator.screenshot()` for one component. Run the same test in desktop and mobile projects to get both widths.
- Look at them. A screenshot nobody opened verifies nothing; UI work in ProductCraft requires looking at real screenshots (`../../ui-distiller/GUIDE.md`).
- Visual regression (`await expect(page).toHaveScreenshot()`) compares against stored baselines. Baselines differ by browser, OS and fonts, so generate and compare them in the same environment (usually CI's container), mask dynamic regions (`mask: [page.getByTestId('clock')]`), and review every baseline update as a code change.

## Console and network errors

Make every test fail on unexpected browser errors with an automatic fixture:

```javascript
// tests/fixtures.js
const base = require('@playwright/test');

exports.test = base.test.extend({
  pageErrors: [async ({ page, baseURL }, use) => {
    const errors = [];
    page.on('console', (msg) => { if (msg.type() === 'error') errors.push(`console: ${msg.text()}`); });
    page.on('pageerror', (err) => errors.push(`exception: ${err.message}`));
    page.on('requestfailed', (req) => errors.push(`request failed: ${req.method()} ${req.url()} ${req.failure()?.errorText}`));
    page.on('response', (res) => {
      if (res.status() >= 400 && res.url().startsWith(baseURL)) errors.push(`HTTP ${res.status()}: ${res.url()}`);
    });
    await use(errors);
  }, { auto: true }],
});
exports.expect = base.expect;
```

```javascript
// tests/signup.spec.js
const { test, expect } = require('./fixtures');

test('creates an account', async ({ page, pageErrors }, testInfo) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('ada@example.com');
  await page.getByRole('checkbox', { name: 'I accept the terms' }).check();
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('status')).toHaveText('Account created');
  await page.screenshot({ path: testInfo.outputPath('after-signup.png'), fullPage: true });
  expect(pageErrors).toEqual([]);
});
```

Chromium also logs failed resource loads as console errors ("Failed to load resource ... 404"), so one broken request may appear twice. If third-party noise is unavoidable, filter it by an explicit, commented allowlist, never by ignoring all console output.

## Simulating failures and slow paths

- Mock or break an endpoint: `await page.route('**/api/stats', (route) => route.fulfill({ status: 503, body: 'down' }))`; then assert the error message and retry control the user sees.
- Slow it down: `await page.route('**/api/orders', async (route) => { await new Promise((r) => setTimeout(r, 2000)); await route.continue(); })`; assert the pending state.
- Offline: `await context.setOffline(true)` makes the page's requests fail and `navigator.onLine` false; assert the app's offline message, then restore with `setOffline(false)`.
- Block third-party scripts that make tests slow or flaky (`route.abort()` for analytics domains), and say so in the test.

## Signed-in tests

Log in once in a setup project with a test account (credentials from environment variables, never committed), save `await page.context().storageState({ path: 'playwright/.auth/user.json' })`, and give other projects `use: { storageState: 'playwright/.auth/user.json' }`. Add the `.auth` folder to `.gitignore`: it holds live session cookies.

## Debugging and flakiness

- Run one test: `npx playwright test tests/signup.spec.js -g "creates" --project=desktop`.
- Failures keep a trace (`trace: 'retain-on-failure'`), a screenshot and an `error-context.md` under `test-results/`. `npx playwright show-trace <trace.zip>` opens the timeline (needs a display; otherwise read the error context and screenshot).
- Check a new or fixed test for flakiness with `--repeat-each=10 --workers=4` before calling it stable. Fix the cause (a missing assertion on a state, shared data between tests, a race with an animation) instead of adding retries or timeouts.
- Keep tests independent: each creates its own data or uses isolated fixtures, so they can run in parallel and in any order.

## Python

```python
# test_signup.py  (pytest --base-url http://127.0.0.1:4173 ; pytest-playwright provides `page`)
import re
from playwright.sync_api import Page, expect

def test_creates_account(page: Page):
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("/")
    page.get_by_label("Email").fill("ada@example.com")
    page.get_by_role("checkbox", name="I accept the terms").check()
    page.get_by_role("button", name="Create account").click()
    expect(page.get_by_role("status")).to_have_text("Account created")
    page.screenshot(path="test-results/after-signup.png", full_page=True)
    assert errors == []
```

pytest-playwright does not start servers. Start one in a session fixture with `subprocess.Popen(cmd, start_new_session=True)`, poll its URL with `urllib.request` until it answers, and in the fixture's teardown stop the group with `os.killpg(proc.pid, signal.SIGTERM)` followed by `proc.wait(timeout=10)`.

## Done when

- The server starts from the documented command, is awaited by URL, and is stopped after the run (port free).
- Tests use role, label, text or test-id locators, contain no sleeps, and assert user-visible outcomes, including pending and error states where they matter.
- The error fixture is on, and the run shows no unexpected console errors, page exceptions or failed same-origin requests.
- Screenshots for the changed screens exist at the widths that matter, and you have looked at them.
- New tests passed repeatedly (`--repeat-each`), and the report states the command run, browsers and projects, pass and fail counts, and anything not covered.
