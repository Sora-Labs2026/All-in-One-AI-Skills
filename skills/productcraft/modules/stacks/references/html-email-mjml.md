# HTML email and MJML

Read this when you build or change an HTML email (transactional or marketing), a template system for emails, or the code that renders and sends them. Legal duties for marketing email (consent, unsubscribe, sender identity) are in `../../legal-ready/GUIDE.md` (items 16 and 18) and `../../legal-ready/references/business-children-email-assets-rights.md`; copy and tone in `../../ui-rules.md`.

## Why email is different

- **Classic Outlook for Windows** renders with Word's engine: no flexbox, grid, `float` layouts or reliable `max-width`; background images need VML; margins and padding behave oddly. Microsoft has said it is supported until at least 2029. The new Outlook for Windows and Outlook on the web use a browser engine.
- **Gmail** limits CSS support, drops `<style>` blocks in some contexts (for example non-Google accounts in its mobile apps), and clips messages whose HTML exceeds about 102 KB behind a "View entire message" link. A clipped footer can hide the unsubscribe link.
- **No JavaScript** runs in any mainstream client. Forms are unreliable. Web fonts work only in some clients (Apple Mail, iOS Mail, some Android clients); always provide a font stack.
- **Images are often blocked** until the user allows them; the email must make sense with images off.
- **Dark mode** differs per client: no change, partial inversion of light backgrounds, or full inversion.

Layout therefore uses tables with inline styles. Authoring that by hand is error-prone; generate it.

## Pick the authoring tool

- **MJML** (default here): a markup language that compiles to table-based, client-tested HTML. MJML 4 is the long-standing stable line; a version 5 has been in pre-release, so check `npx mjml --version` and the changelog before relying on specific options.
- **React Email or similar component libraries:** fit teams that render emails from TypeScript with props; the same client rules apply.
- **Templates provided by the email service:** fine for marketing teams editing in a visual builder; developers then own only the data and the sending code.
- Install MJML as a project dev dependency and run it with `npx mjml` or the Node API; do not rely on a global install.

## MJML structure and idioms

- `<mjml lang="...">` with an `<mj-head>` (`mj-title`, `mj-preview`, `mj-attributes`, `mj-font`, `mj-style`, `mj-breakpoint`) and an `<mj-body width="600px">`.
- Content sits in `mj-column` inside `mj-section`. Sections cannot nest; group them in `mj-wrapper` for a shared background or border.
- Columns stack on narrow screens. `mj-group` keeps columns side by side (logo rows, social icons).
- Set defaults once in `mj-attributes` (`mj-all`, per-component defaults, `mj-class`) instead of repeating attributes.
- Critical styles go in component attributes (`color`, `font-size`, `padding`), which MJML inlines. Class-based CSS in `mj-style` may be dropped by some clients; add `inline="inline"` to inline it, and keep media queries and dark-mode rules in a non-inlined `mj-style` as progressive enhancement.
- Background images work in Outlook only on `mj-section` and `mj-hero` (MJML generates VML there). Always set a fallback `background-color`.
- `mj-button` produces a table-based button that renders everywhere; never use an image as the only button.
- Avoid `mj-carousel` and `mj-accordion`: many clients show only a fallback, hiding content.
- `mj-include` shares headers and footers across templates.
- Template variables (Handlebars, Liquid, the email service's syntax) can confuse the MJML parser inside attributes; put complex logic in `mj-raw` or keep variables in text content, and compile first, render variables later.

```xml
<mjml lang="en">
  <mj-head>
    <mj-title>Your receipt for order {{orderNumber}}</mj-title>
    <mj-preview>Order {{orderNumber}}: {{total}} paid. Delivery details inside.</mj-preview>
    <mj-attributes>
      <mj-all font-family="Helvetica, Arial, sans-serif" />
      <mj-text font-size="16px" line-height="24px" color="#1f2328" />
      <mj-button background-color="#0b5cad" color="#ffffff" font-size="16px" border-radius="6px" />
    </mj-attributes>
    <mj-raw><meta name="color-scheme" content="light dark"></mj-raw>
  </mj-head>
  <mj-body width="600px" background-color="#f4f5f7">
    <mj-section background-color="#ffffff" padding="24px">
      <mj-column>
        <mj-image src="https://cdn.example.com/email/logo@2x.png" width="120px" alt="Example Store" />
        <mj-text font-size="22px" font-weight="700">Thanks, {{firstName}}. Your order is confirmed.</mj-text>
        <mj-text>Order {{orderNumber}} · Total {{total}} · Paid with {{paymentMethod}}</mj-text>
        <mj-button href="{{orderUrl}}">View your order</mj-button>
      </mj-column>
    </mj-section>
    <mj-include path="./partials/footer.mjml" />
  </mj-body>
</mjml>
```

## Compile in the build, fail on errors

```js
// scripts/build-emails.mjs
import mjml2html from "mjml";
import { readFile, writeFile } from "node:fs/promises";

for (const name of ["receipt", "password-reset", "welcome"]) {
  const src = await readFile(`emails/${name}.mjml`, "utf8");
  // Strict validation throws on invalid markup; `await` also covers releases that return a promise.
  let result;
  try {
    result = await mjml2html(src, { validationLevel: "strict", filePath: `emails/${name}.mjml` });
  } catch (err) {
    console.error(`${name}: ${err.message}`);
    process.exit(1);
  }
  const { html } = result;
  if (Buffer.byteLength(html) > 95_000) throw new Error(`${name}: ${Buffer.byteLength(html)} bytes risks Gmail clipping`);
  await writeFile(`dist/emails/${name}.html`, html);
}
```

- Use strict validation so invalid nesting or attributes fail the build.
- Compile once at build time and fill variables at send time; compiling MJML per message is slow.
- Minify or strip whitespace to stay under the clipping limit and to stop whitespace gaps between inline-block columns.

## Content rules that are engineering rules

- **Width** 600 to 640 px, one column on phones.
- **Images:** absolute HTTPS URLs on a CDN, explicit `width`, served at twice the display size for sharp screens, and `alt` text that carries the meaning (decorative images get `alt=""`). No text baked into images.
- **Preheader** text through `mj-preview`, so the inbox preview is not "View in browser".
- **Accessibility:** `lang` on the root, `mj-title`, real text with at least 4.5:1 contrast, descriptive link text, body text of 14 to 16 px, headings marked up (`mj-html-attributes` can add `role="heading"` and `aria-level` under strict validation). MJML marks layout tables `role="presentation"`.
- **Dark mode:** declare `color-scheme`, add `prefers-color-scheme` rules for clients that honor them, and design so forced inversion stays legible (logos on transparent backgrounds get a light outline or padding; avoid pure black text on pure white if inversion makes it harsh).
- **Plain-text part:** always send `multipart/alternative` with a real text version; generate it from the same data, not by stripping tags blindly.
- **Links:** absolute, tracked only as the owner decided, no URL shorteners. Phone numbers and dates may be auto-linked by iOS; style or neutralize them where that breaks the design.
- **Personal data:** only what the recipient needs; no secrets, full card numbers or reset tokens that never expire.

## Sending pipeline

- Render with data, then check for unreplaced placeholders (`{{`) before sending.
- Send through the provider's API or SMTP from a background job, with a per-message idempotency or deduplication key so retries do not send twice; retry transient failures with backoff (`../../engineering-practices/references/resilience.md`).
- Handle bounce and complaint webhooks (verify their signatures) and suppress hard-bounced and complaining addresses.
- **Authentication:** SPF, DKIM and DMARC aligned with the From domain. Gmail and Yahoo (2024) and Outlook.com (2025) require them, plus one-click unsubscribe (`List-Unsubscribe` and `List-Unsubscribe-Post`, RFC 8058) for bulk marketing mail. Changing DNS is a production action for the owner.
- Separate transactional and marketing traffic (subdomain or stream) so marketing reputation does not delay password resets.

## Testing

- Local development sends to a mail catcher (for example Mailpit) and never to real recipients (`../../legal-ready/GUIDE.md`, ground rule 6).
- Unit-test rendering with fixture data: required fields present, placeholders replaced, links absolute, size under budget. Snapshot the compiled HTML only if reviewers will read the diffs.
- Check rendering on real clients before release: classic Outlook for Windows, Outlook on the web, Gmail web and app, Apple Mail and iOS Mail, one Android client; with images off, in dark mode and on a phone. A rendering-preview service speeds this up; test accounts on each client work too.
- Click every link in the rendered email.

## Common breakages

| Symptom | Cause | Fix |
|---|---|---|
| Columns stack on desktop or sit side by side with gaps | Whitespace between inline-block columns, or a missing `mj-group` | Minify output; use `mj-group` where columns must stay together |
| Times New Roman in Outlook | Web font without a fallback stack applied to Outlook | Font stack in `mj-attributes`; load web fonts with `mj-font` |
| Background image missing in Outlook | Background on a component that gets no VML | Move it to `mj-section` or `mj-hero`; set a fallback color |
| "View entire message" in Gmail | HTML over about 102 KB | Remove unused CSS, minify, shorten repeated markup |
| Logo vanishes in dark mode | Dark logo on transparent background inverted to dark on dark | Outline or padded light background on the logo; test in dark mode |
| MJML errors on template tags | Placeholders inside attributes the parser validates | Move logic to `mj-raw` or text; compile before rendering variables |

## Done when

- [ ] Templates compile with strict validation in the build, and the build fails on errors or size over budget.
- [ ] Every image has width and suitable `alt`; the email reads correctly with images off.
- [ ] A plain-text part is sent; no unreplaced placeholders reach a recipient (tested).
- [ ] Rendering was checked on the client list above, or the report marks the unchecked clients `NOT VERIFIED`.
- [ ] Marketing email meets the legal-ready items for consent and unsubscribe; sending was tested against a mail catcher only.
