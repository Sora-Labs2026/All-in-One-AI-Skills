# Changelog

## ProductCraft 1.1.0 (2026-10-23)

- Added the LaunchGuard 20-control security baseline (`modules/launchguard/references/security-baseline.md`). Each control lists its gate, what to do, the common trap and how to verify it.
- The router now runs a scoped check of the matching baseline controls when a change touches API routes, data access, queries, uploads, cookies, headers or dependencies, without a full launch review.
- The LaunchGuard report template and release checklist include a status table for all 20 controls.
- Scanner 1.1.0 adds two rules, `INSECURE_COOKIE_FLAG` and `WEAK_PASSWORD_HASH`, with tests.

## ProductCraft 1.0.0 (2026-10-23)

- First release: router, six design and UX modules, UI/UX pattern library, and the UI Distiller, Credential Shield and LaunchGuard modules.
- Released under the MIT License.
