# Shopify themes, apps and headless storefronts

Read this when you build or change a Shopify theme (Liquid, sections, blocks), a Shopify app (Admin API, webhooks, extensions, Functions), a checkout customization, or a headless storefront on the Storefront API. GraphQL client practice is in `graphql.md`; payments and webhooks at launch in `../../launchguard/references/stack-playbooks.md`; honest pricing and claims in `../../legal-ready/GUIDE.md`.

## Pick the surface

| Need | Surface |
|---|---|
| Change the storefront's look and layout for one shop | Theme (Liquid, JSON templates, sections and blocks) |
| An app that adds UI to merchants' storefronts | Theme app extension (app blocks and app embeds); never edit the merchant's theme code |
| Merchant-facing tools in the admin | Embedded app (App Bridge, Polaris) using the GraphQL Admin API; admin UI extensions |
| Change checkout, thank-you or order-status pages | Checkout UI extensions and the checkout branding API (checkout extensibility) |
| Custom discount, shipping, payment or cart validation logic | Shopify Functions |
| A storefront the theme system cannot deliver | Headless: Hydrogen (hosted on Oxygen or elsewhere) or any framework on the Storefront API |

Headless moves performance, SEO, analytics, consent and accessibility from Shopify to you. Choose it for real requirements, not by default.

## Platform changes to know (2024-2026; check current docs)

- **API versions** are released quarterly (`2025-10`, `2026-01`, ...) and each is supported for at least 12 months. Pin the version in config, upgrade at least once a year, and watch deprecation notices in the Partner Dashboard and the `X-Shopify-API-Deprecated-Reason` header.
- **The REST Admin API is legacy** (since October 2024). New public apps must use the GraphQL Admin API (since April 2025).
- **`checkout.liquid` is retired:** for information, shipping and payment pages since August 2024 and for thank-you and order-status pages in 2025. Shopify Scripts are being replaced by Functions (2026). Rebuild customizations as extensions and Functions.
- **App template:** the Remix-based template moved to React Router 7 in 2025, following the Remix and React Router merge; Hydrogen moved too.
- **UI extensions and admin UI** are moving to Polaris web components; check which component model your API version uses before writing UI.

## Themes

- Structure: `layout/`, `templates/` (JSON templates for Online Store 2.0), `sections/`, `blocks/` (theme blocks), `snippets/`, `assets/`, `config/` (`settings_schema.json`, `settings_data.json`), `locales/`.
- JSON templates list sections that merchants arrange in the theme editor. Each section declares its settings and blocks in `{% schema %}`; include `{"type": "@app"}` in a section's blocks so app blocks can be added there.
- Use `{% render 'snippet' %}` (isolated scope), not the deprecated `{% include %}`.
- Content: section and block settings for layout choices; metafields and metaobjects for structured product or shop data; translations in `locales/`.
- **Images:** `image_url` with a width, then `image_tag` with `widths` and `sizes` for responsive `srcset`. Lazy-load below the fold; load the largest above-the-fold image eagerly with high fetch priority.
- **Liquid cost:** avoid nested loops over large collections, paginate collection pages (`{% paginate %}`), and remember `all_products` lookups are limited per page. Profile slow templates with the Shopify Theme Inspector browser extension.
- **JavaScript:** small, deferred, progressively enhanced (web components work well). Update parts of the page with the Section Rendering API instead of re-rendering in JavaScript. The AJAX Cart API (`/cart/add.js`, `/cart/change.js`) can return re-rendered sections in the same response; handle 422 responses (out of stock, quantity limits) with a visible message.
- Apps' embeds and third-party scripts are the usual cause of slow themes; measure each one (`../../engineering-practices/references/performance.md`).

### Theme workflow

- `shopify theme dev` serves a development theme with hot reload; `shopify theme check` lints Liquid and theme structure; run it in CI.
- Never edit the live theme directly. Preview changes on an unpublished theme (`shopify theme push --unpublished`), or deploy through the GitHub integration with a branch per theme.
- Merchants change JSON templates and `settings_data.json` in the theme editor. Pull those files before pushing (`shopify theme pull --only templates/*.json --only config/settings_data.json`) or a push overwrites their work. Publishing a theme is a production action for the owner.

## Apps

- Scaffold with `shopify app init`; `shopify.app.toml` declares scopes, URLs and webhook subscriptions; `shopify app dev` runs against a development store through a tunnel; `shopify app deploy` releases a new app version with its extensions and configuration (a production action).
- **Auth for embedded apps:** Shopify-managed installation plus session tokens from App Bridge, exchanged for API access tokens on the server. Store offline tokens encrypted; never expose them to the browser.
- **Least privilege:** request only the scopes the features need. Customer personal data (names, emails, addresses) is protected customer data that needs approval levels; request the minimum and document why.
- **Billing:** the Billing API for charges; test charges on development stores.

### GraphQL Admin API

- Rate limits are cost-based: each query has a calculated cost drawn from a bucket that refills per second. Read `extensions.cost` (`requestedQueryCost`, `actualQueryCost`, `throttleStatus`) and back off on `THROTTLED` errors.
- Paginate connections with cursors (`first` at most 250). For full exports use bulk operations (`bulkOperationRunQuery`) and download the JSONL result; for large imports, `bulkOperationRunMutation`.
- Mutations report failures in `userErrors` with HTTP 200. Always check them.
- Guard retried creates against duplicates with your own deduplication key.

### Webhooks

- Verify the HMAC on the raw body before parsing: base64 HMAC-SHA256 with the app's client secret, compared in constant time.
- Respond 200 quickly (within a few seconds) and process in a background job. Delivery is at least once and not ordered: deduplicate by the event id header (`X-Shopify-Event-Id`, or `X-Shopify-Webhook-Id` on older setups) and fetch current state when order matters.
- Public apps must handle the mandatory privacy webhooks (`customers/data_request`, `customers/redact`, `shop/redact`) and clean up on `app/uninstalled`.

```ts
import { createHmac, timingSafeEqual } from "node:crypto";

export async function verifyShopifyWebhook(request: Request, secret: string): Promise<string | null> {
  const raw = await request.text();                                 // raw body, before JSON.parse
  const header = request.headers.get("x-shopify-hmac-sha256") ?? "";
  const expected = createHmac("sha256", secret).update(raw, "utf8").digest();
  const received = Buffer.from(header, "base64");
  if (received.length !== expected.length || !timingSafeEqual(received, expected)) return null;
  return raw;                                                        // caller parses and enqueues
}
```

(When the app uses the official app package, its `authenticate.webhook` helper does this; do not verify twice with different body handling.)

## Checkout extensions and Functions

- Checkout UI extensions render in Shopify's sandbox at defined extension targets. They cannot read or change arbitrary page content, and the merchant places them in the checkout editor after deploy.
- Functions run your logic as WebAssembly inside Shopify (written in Rust or JavaScript) under strict limits on instructions, input size and output, and without general network access. The input GraphQL query defines the data the Function receives; keep it minimal. Rust suits heavy logic; JavaScript Functions hit limits sooner.
- Test Functions with fixture inputs (`shopify app function run`) and unit tests, covering empty carts, many lines, missing metafields and currency differences.

## Headless storefronts

- Storefront API tokens: the public token can sit in the browser; the private token stays on the server, which forwards the buyer's IP as Shopify documents.
- Hydrogen provides cart, caching helpers per query (short and long cache strategies) and analytics wiring; any framework works with the Storefront API and the Cart API.
- Checkout is Shopify-hosted: redirect to the cart's `checkoutUrl`. Do not build your own payment page.
- Markets and localization: query with `@inContext(country: ..., language: ...)` and pass currency and language through the whole session.
- Customer accounts use the Customer Account API (OAuth with PKCE).

## Testing

- Development stores with test data; test orders through the test payment gateway or test mode. Never test on a live merchant store without the owner's permission.
- `shopify theme check` and the app's lint, type check and unit tests in CI; webhook verification tested with a correct and a tampered signature.
- End-to-end tests (Playwright) against a development theme preview or development store, including the storefront password page if enabled.

## Common breakages

| Symptom | Cause | Fix |
|---|---|---|
| App block cannot be added to a section | Section schema lacks `@app` blocks, or the theme is not Online Store 2.0 | Add `{"type": "@app"}`; app embeds for vintage themes |
| Merchant's homepage layout reset after a deploy | JSON templates pushed over editor changes | Pull editor-owned files before pushing; ignore them in CI deploys |
| Webhook HMAC never matches | Body parsed or re-serialized before verification | Verify the raw bytes |
| `THROTTLED` errors | Query cost too high or too many requests | Reduce selected fields and page size; back off by `throttleStatus`; bulk operations |
| Mutation "succeeded" but nothing changed | `userErrors` ignored | Check and surface them |
| Errors after an API version leaves support | Version pinned too long | Upgrade one version at a time and fix deprecations |
| Checkout customization disappeared | `checkout.liquid` retired | Rebuild with checkout UI extensions and Functions |

## Done when

- [ ] `shopify theme check` (themes) or the app's lint, type check and tests pass.
- [ ] Theme changes were previewed on an unpublished theme, and editor-owned JSON was pulled first.
- [ ] Apps request minimal scopes, check `userErrors`, respect cost limits, verify webhook HMACs on raw bodies and handle the privacy webhooks.
- [ ] Functions and extensions are tested with fixtures covering edge cases.
- [ ] Publishing themes, deploying app versions and changing live store settings were left to the owner or done with explicit approval.
