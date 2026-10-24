#!/usr/bin/env node
// Regenerate the README screenshots of the ProductCraft example screens.
//
//   node scripts/screenshots.cjs                 # every example
//   node scripts/screenshots.cjs dashboard-v1    # only the named examples
//
// Requires Playwright with Chromium. Each example can set capture options in
//   <meta name="screenshot" content="width=1440,height=900,dpr=1,full=true,scheme=light,focus=#selector">
// Output: docs/screens/<name>.jpg (full page) and docs/screens/thumbs/<name>.jpg (top 4:3 crop at half size,
// used by the README galleries)

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const examples = path.join(root, "skills", "productcraft", "examples");
const out = path.join(root, "docs", "screens");
const thumbs = path.join(out, "thumbs");

function options(html) {
  const m = html.match(/<meta name="screenshot" content="([^"]*)"/);
  const pairs = (m ? m[1] : "").split(",").map((s) => s.trim()).filter(Boolean);
  return Object.fromEntries(pairs.map((kv) => kv.split("=").map((s) => s.trim())));
}

(async () => {
  const wanted = process.argv.slice(2);
  const files = fs
    .readdirSync(examples)
    .filter((f) => f.endsWith(".html"))
    .filter((f) => !wanted.length || wanted.includes(f.replace(/\.html$/, "")))
    .sort();
  if (!files.length) throw new Error("No matching examples in " + examples);
  fs.mkdirSync(thumbs, { recursive: true });

  const browser = await chromium.launch();
  async function open(file, opts, scale, minHeight = 0) {
    const page = await browser.newPage({
      viewport: { width: Number(opts.width || 1440), height: Math.max(Number(opts.height || 900), minHeight) },
      deviceScaleFactor: scale,
      colorScheme: opts.scheme || "light",
      reducedMotion: "reduce",
    });
    await page.goto("file://" + path.join(examples, file));
    await page.evaluate(() => document.fonts.ready);
    if (opts.focus) await page.focus(opts.focus);
    await page.waitForTimeout(150);
    return page;
  }

  for (const file of files) {
    const opts = options(fs.readFileSync(path.join(examples, file), "utf8"));
    const name = file.replace(/\.html$/, ".jpg");
    const width = Number(opts.width || 1440);

    const page = await open(file, opts, Number(opts.dpr || 1));
    await page.screenshot({ path: path.join(out, name), type: "jpeg", quality: 90, fullPage: opts.full !== "false" });
    await page.close();

    const small = await open(file, opts, 0.5, Math.round(width * 0.75));
    const height = Math.min(Math.round(width * 0.75), await small.evaluate(() => document.documentElement.scrollHeight));
    await small.screenshot({ path: path.join(thumbs, name), type: "jpeg", quality: 85, clip: { x: 0, y: 0, width, height } });
    await small.close();
    console.log("saved docs/screens/" + name + " and thumbs/" + name);
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
