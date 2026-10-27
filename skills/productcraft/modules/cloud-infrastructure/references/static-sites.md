# Deploying static sites and front-end builds

Read this when the user wants to deploy, upload, publish or host a static site or front-end build output (Vite, Next.js static export, Astro, Hugo, plain HTML), on object storage with a CDN, a static hosting platform, GitHub Pages or a content-addressed network.

Publishing a site makes its files available to everyone, immediately. Build and check locally, then deploy only when the user asked for that release, to the target they named.

## Before anything leaves the machine

1. **Find the real output directory** from the build configuration, not by guessing: `dist/` (Vite), `build/` (Create React App and others), `out/` (Next.js static export), `public/` (Hugo output, but also the source folder in many other tools). Run the project's build command and confirm the directory has an `index.html` and the expected assets.
2. **Check what is in it.** Build output often includes more than intended:
   - environment values embedded at build time (anything prefixed `VITE_`, `NEXT_PUBLIC_`, `REACT_APP_`, or injected through a define plugin) are public once deployed; confirm none is a secret (`../../launchguard/references/security-baseline.md`, control 1);
   - source maps (`*.map`) expose original source; publish them only if the user wants that, or upload them privately to an error tracker;
   - stray files: `.env`, backups, test fixtures, drafts.

```bash
find dist -type f | sort | head -100
grep -rIl --exclude='*.map' -E '(sk_live|PRIVATE KEY|secret|password)' dist || echo "no obvious secrets"
find dist -name '*.map' | head
```

3. **Preview locally** with the framework's preview server (`npm run preview`, `npx serve dist`) and click through the main routes, including a deep link and a missing page.

## Hosting choices

| Target | Notes |
|---|---|
| Object storage plus CDN (S3 with CloudFront, Azure Storage with Front Door, Google Cloud Storage with Cloud CDN) | Keep the bucket private and let the CDN read it (CloudFront origin access control, for example); manage it as IaC; invalidate the CDN cache for HTML after deploys |
| Static hosting platforms (Netlify, Vercel, Cloudflare Pages, Azure Static Web Apps, Firebase Hosting) | Preview deploys per branch, built-in TLS and redirects; production promotion is a separate, explicit step |
| GitHub Pages | Simple for public documentation; everything published is public even if the repository is private on some plans; check the plan |
| Content-addressed networks (IPFS and similar) | Content is public and addressed by hash; once others have copied or pinned it, it cannot be withdrawn. Never publish anything private, personal or unreleased this way |

Use the project's existing target and tooling. Third-party deploy CLIs are dependencies and extensions: install them only with the user's agreement, pinned, and never through `curl | sh` (`../../agent-safety/GUIDE.md`).

## Framework notes

- **Base path:** a site served from a subpath (GitHub Pages project sites, `example.com/docs/`) needs the framework's base setting (`base` in Vite, `basePath` and `assetPrefix` in Next.js, `baseURL` in Hugo), or assets load from the wrong place.
- **Next.js static export** (`output: "export"`) drops server features: API routes, middleware, server actions, incremental regeneration and the default image optimizer. If the app uses them, it needs a server or edge runtime, not static hosting.
- **Client-side environment switching** does not exist in a static build: each environment needs its own build, or a small runtime config file fetched at start that holds only public values.
- **Pre-rendered pages** contain whatever data was fetched at build time; make sure nothing private was fetched with build credentials and baked into HTML.

## Configuration that matters

- **Caching:** files with content hashes in their names (`app.3f9a1c.js`) get `Cache-Control: public, max-age=31536000, immutable`; `index.html` and other un-hashed entry points get `no-cache` (revalidate every time). Otherwise users keep old HTML that points to deleted assets.
- **Single-page app routing:** rewrite unknown paths to `index.html` with status 200, but keep real 404s for missing assets and keep a proper 404 page for unknown routes where the framework supports it.
- **Security headers** (Content-Security-Policy, Strict-Transport-Security when HTTPS is final, X-Content-Type-Options, frame policy) set in the platform's headers configuration or CDN response policy; fit them to what the site loads (`../../launchguard/references/security-baseline.md`, control 18).
- **HTTPS everywhere** with managed certificates; redirect HTTP to HTTPS.
- **Custom domains:** DNS changes affect live traffic and email if done carelessly; prepare the records, lower TTLs ahead of a cutover, and let the user apply them.
- **Compression** (Brotli or gzip) is usually automatic on CDNs; confirm for large assets.

## Deploying

- Prefer a preview or staging deploy first and give the user its URL to check.
- Production deploys and promotions run only with the user's go-ahead, through the project's pipeline where one exists (`../../engineering-practices/references/ci-and-release.md`). Keep the previous deployment available for instant rollback (platform rollback or the previous object-storage prefix).
- For object storage, sync with deletion only after a dry run: `aws s3 sync dist/ s3://BUCKET/ --delete --dryrun` shows what would be removed. Upload hashed assets before HTML so a visitor never gets HTML that references files not yet uploaded.

## Verify after deploy

```bash
curl -sI https://example.com/ | grep -iE 'http/|cache-control|content-security-policy|strict-transport'
curl -sI https://example.com/assets/app.3f9a1c.js | grep -i cache-control
curl -s -o /dev/null -w '%{http_code}\n' https://example.com/some/deep/link
curl -s -o /dev/null -w '%{http_code}\n' https://example.com/definitely-missing.png
```

Check the main routes in a browser, the console for errors, and that no source maps or secrets are reachable unless intended.

## Done when

- [ ] The build output was inspected: no secrets, no unintended source maps or stray files.
- [ ] Caching, SPA routing, HTTPS and security headers are configured and were checked with requests against the deployed URL.
- [ ] A preview was offered first; the production deploy ran only with the user's go-ahead and a rollback path exists.
- [ ] Nothing private was published to a public or content-addressed target.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Users see a blank page after a deploy | Cached old `index.html` references deleted assets | `no-cache` on HTML; keep previous assets for a while |
| Deep links return 404 | No SPA fallback rewrite | Rewrite unknown routes to `index.html` |
| API key found in the bundle | Secret placed in a public build-time variable | Move the call server-side; rotate the key |
| Site publicly readable from the bucket URL | Public bucket instead of CDN-only access | Private bucket with origin access control |
| Old content still online after "deleting" it | Content-addressed or cached copies | Treat publication as permanent; rotate anything sensitive |
