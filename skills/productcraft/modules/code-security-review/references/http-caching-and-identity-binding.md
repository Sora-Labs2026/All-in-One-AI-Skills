# HTTP caching, proxies and identity binding

Read this when a web target has a cache or proxy in front of it, builds URLs or picks tenants from request headers, sits behind an authenticating proxy, or implements federated sign-in, passkeys, MFA, recovery, account linking or API keys. It also covers browser-side state the server never sees. The basics are elsewhere:

- JWT verification, sessions, CSRF, XSS and CORS: [vulnerability classes](vulnerability-classes.md);
- OAuth client flows and token storage: [OAuth and tokens](../../integrations/references/oauth-and-tokens.md);
- abuse of login and recovery (stuffing, spraying, OTP guessing): Credential Shield.

This file covers the places where two components disagree about which request, which user or which level of assurance an operation belongs to.

## Caches and request framing

**Cache deception.** A shared cache stores a private page because its URL looks static. A typical case is `/account/settings/x.css`: the app routes it to the settings page, ignoring the suffix, while a CDN rule caches by extension. Delimiters (`;`, encoded `?` or `#`) and path normalization (`%2F`, dot segments) can differ between cache and app in the same way.
- Personalized responses send `Cache-Control: no-store` (or `private`).
- Cache rules honor the origin's headers instead of overriding them by extension.
- The app returns 404 for paths it does not recognize instead of falling back to a parent route.
- Do not rely on `Vary: Cookie`: many shared caches ignore or limit `Vary`.

**Cache poisoning.** A request value changes the response but is not part of the cache key, so one attacker's response is served to everyone. Typical unkeyed inputs are `X-Forwarded-Host`, `X-Forwarded-Scheme`, `X-Original-URL` and similar override headers, a parameter the cache and the app parse differently, and a body on a GET. Do not build responses, redirects or asset URLs from headers the cache does not key on. Strip such headers at the edge, or add them to the key.

**Request smuggling.** This is in scope when the repository contains a proxy, gateway, load balancer configuration or custom HTTP parser, or when its server sits behind one with reused back-end connections. The front end and the back end split the same bytes into different requests. Typical causes:
- both `Content-Length` and `Transfer-Encoding` on one request;
- duplicate or malformed length headers;
- bare line feeds or obsolete header folding;
- HTTP/2 to HTTP/1.1 downgrade with header values containing CR or LF.

RFC 9112 lets a server reject a request that carries both length headers, and requires it to close the connection after such a request; rejecting is the safer choice. Use maintained servers and proxies, reject ambiguous framing, and prefer HTTP/2 end to end. Reproduce only with a local front end and back end fed raw bytes from a script, never against shared infrastructure.

To confirm any cache or framing claim, name both components and the exact value each one sees, then show the cross-user or private-response effect locally. A cache that lives only in the CDN dashboard is `NOT_VERIFIED`, with the owner check named: which cache rule applies to the path, and what the key includes.

## Host and forwarded headers

Find every place the code reads `Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`, `Forwarded`, `X-Forwarded-For` or `X-Real-IP`, and ask what depends on it:

- **Absolute URLs** in password-reset, invitation and verification emails, OAuth redirect URIs, and links in webhooks. An attacker who sets the header receives the victim's token. Build these from a configured base URL.
- **Tenant selection by subdomain or host.** The session must belong to the tenant the host selects. A global session plus a host-chosen tenant is a cross-tenant path.
- **Client IP** for rate limits, allowlists and audit logs. Trust forwarded addresses only from known proxy hops ([language pitfalls](language-pitfalls.md) covers Express `trust proxy`).
- **Host validation** should be on: Django `ALLOWED_HOSTS`, Rails `config.hosts`, ASP.NET Core `AllowedHosts`. Many Node and Go stacks have no equivalent unless you add one.

## Identity set by a proxy

Back ends behind an authenticating proxy, a mutual-TLS terminator or a service mesh often read identity from headers: `X-Forwarded-User`, `X-Auth-Request-Email`, `Remote-User`, `X-Client-Cert`, `X-SSL-Client-S-DN`. That is safe only when all of the following hold:

- only the proxy can reach the back end: no published port, no other ingress path, no health or debug listener on another interface;
- the proxy overwrites or removes incoming copies of those headers rather than appending;
- the back end maps the header to an account deterministically, and fails closed when it is missing.

Check alternate routes: a second ingress, a legacy port, the service's own public URL on the platform, and other pods or functions on the internal network. A repository-visible route that bypasses the proxy is confirmable. Network policy kept outside the repository is `NOT_VERIFIED`.

## Federated sign-in: OIDC and SAML

**OIDC relying parties**, beyond `state` and PKCE:
- The ID token is verified with the provider's published keys.
- `iss` equals the issuer of the provider this login started with. With several providers, a mix-up sends one provider's response to another's handler; RFC 9207 adds an `iss` parameter to the authorization response for exactly this.
- `aud` contains your client ID (and `azp` is checked when there are several audiences).
- `exp` is in the future, and `nonce` matches the value stored in the session.
- The account key is issuer plus `sub`. Trust `email` for linking only when `email_verified` is true and the provider is authoritative for that address.

**SAML service providers:**
- Use a maintained library. Several shipped signature-wrapping and parser-differential bypasses in recent years, so check the pinned version's advisories.
- The element whose signature was verified must be the element whose identity you use. Read the NameID and attributes through the library's API for the validated assertion, never by searching the document again.
- Require signed assertions, or a signed response containing exactly one assertion.
- Check `Audience`, `Recipient` or `Destination`, `NotBefore` and `NotOnOrAfter` with a small clock skew, and `InResponseTo` against the stored request ID. Keep a replay cache of assertion IDs.
- Disable DTDs ([XML external entities](vulnerability-classes.md#13-xml-external-entities)).
- Decide explicitly whether IdP-initiated login is allowed, because it has no request to bind to.
- In a multi-tenant SP, the assertion's issuer must be the IdP configured for the tenant being logged into, verified with that tenant's certificate. Accepting any configured IdP's assertion for any tenant lets one customer's IdP sign in as another customer's users.

## Passkeys and WebAuthn

Use a maintained server library (SimpleWebAuthn, py_webauthn, webauthn4j, go-webauthn, webauthn-rs) and check that the code passes it the right expectations:

- the challenge comes from the server-side session, is single-use and expires;
- the expected origin is exact, including scheme and port, and the expected RP ID is your registrable domain (the library checks the RP ID hash against it);
- user presence is required, and user verification is required where policy says so;
- at authentication, the credential belongs to the account being signed into. For discoverable credentials, `userHandle` maps to that account;
- registration happens only from an authenticated session, with step-up where policy requires it, and binds the credential to that session's user;
- the signature counter is treated as a clone signal only if the product decided to; synced passkeys typically report 0.

## MFA, step-up and recovery

- **No full session before the second factor.** A half-authenticated state must not reach any API besides completing the challenge.
- **Enrollment and removal.** Adding, replacing or removing a factor, regenerating recovery codes, and creating "remember this device" tokens each need recent authentication and the existing factor when one exists.
- **Step-up binding.** A completed challenge raises assurance for this session, for this action or resource where policy requires, and for a limited time. Compare every route to the protected operation: UI, API, mobile, batch, legacy. If assurance comes from the IdP, request it (`max_age`, `acr_values`) and check `auth_time` and `acr` in the ID token.
- **Recovery is an authentication path.** Reset tokens, recovery codes (hashed, single-use), email or phone change, device migration and support-assisted recovery are often the weakest door. An email or phone change confirms through the new address and notifies the old one. Recovery invalidates other sessions and outstanding reset tokens.

## Account linking

- Link a new identity (IdP, passkey, email, phone) only from a current session, after proving control of the new identity, with step-up where policy requires, and with callback state bound to the account that started linking.
- **Pre-hijacking.** An attacker registers with the victim's unverified email before the victim arrives. Later, the victim signs in through a provider and the accounts merge, or the attacker's session survives. Do not merge into an account whose email was never verified, and end its other sessions when it is claimed.
- Unlink and relink, invitation acceptance and domain-based auto-join need the same scrutiny for identifier collisions across tenants.

## API keys

- Store a hash of each key; for long random keys a fast hash such as SHA-256 is fine. Show the key once, and use a non-secret prefix for lookup and display.
- Compare in constant time.
- Enforce scopes server-side on every route, including bulk and export.
- Separate test keys from live keys and publishable keys from secret keys, and reject a key used outside its environment or type.
- Revoke immediately, keeping any cache lifetime short.

## Browser-side state

**Service workers**
- A worker controls its scope. The `Service-Worker-Allowed` response header can widen that scope.
- Register only a fixed script path. User uploads served from the app's origin with a JavaScript content type can be registered as a worker and persist across visits; serve uploads from another origin.
- `importScripts` has no integrity check, so keep imports same-origin.
- Workers that cache authenticated responses must key or partition by user. On logout, clear them (`caches.delete`, and `Clear-Site-Data: "cache", "storage"` where supported). Make sure offline fallbacks never serve the previous user's pages.

**Storage across account switches**
- Tokens, drafts and API responses in `localStorage`, IndexedDB or Cache Storage outlive logout and appear to the next account in the same browser profile. So do authorization decisions cached on the client.
- Tabs on different accounts can overwrite each other through `storage` events or `BroadcastChannel`.
- It is a finding when another account, or a less trusted script on the same origin, can read or reuse the data.

**Cross-site leaks**
- An attacker's page can sometimes learn a yes-or-no fact about the victim's state on your site. It watches load and error events, frame counts in a window it opened, redirects, timing or cache state while the browser attaches the victim's cookies.
- Report one only with a concrete secret predicate, such as "the private search for X has results". General timing noise is not a finding.
- Defenses: `SameSite` cookies; a Fetch Metadata policy that rejects cross-site `Sec-Fetch-Site` requests except top-level navigations; `Cross-Origin-Opener-Policy: same-origin`; `Cross-Origin-Resource-Policy: same-origin`; `frame-ancestors`.

**DOM clobbering**
- Sanitized HTML that keeps `id` and `name` attributes can define globals (`window.config`, `document.x`) that later code trusts.
- DOMPurify's default (`SANITIZE_DOM`) protects built-in document and form properties but not your own globals. Its `SANITIZE_NAMED_PROPS` option prefixes ids and names.
- Do not read configuration from globals or named DOM properties; use module-scoped values.

## Confirm safely

- Use local components only: the proxy and app from the repository, a local identity provider with dummy users, and two browser profiles or two local host names for cross-site and cross-account tests (driven with Playwright, for example).
- Record the proxy and framework versions, because framing and cache behavior changes between releases.
- Facts that live in a CDN dashboard, an IdP console or network policy are `NOT_VERIFIED`, each with the owner check that settles it.
- Rate with the [severity rules](audit-phases.md#phase-6-rate-severity). Signing in as another user, or serving one user's private page to others, starts at the top of the table.

## Done when

- Every cache in front of the app has its key and its rules for personalized responses recorded, and every header-derived URL, tenant or client IP is traced to a configured base or a trusted hop.
- Proxy-set identity headers are shown unreachable except through the proxy, or the gap is a finding or `NOT_VERIFIED`.
- OIDC, SAML and WebAuthn verification code is cited for each binding listed above.
- MFA enrollment, step-up, recovery and linking routes are compared side by side.
- API-key storage, comparison, scope and revocation are cited.
- Service-worker scope and cache keys, storage cleanup on logout, cross-site leak defenses and clobbering-safe globals are recorded for browser clients that hold private data.
