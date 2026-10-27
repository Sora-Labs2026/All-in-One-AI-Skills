# OAuth, scopes and tokens

Read this when code obtains, stores, refreshes or revokes credentials for a third-party API: an OAuth flow, an API key, a personal access token, a service account, or an MCP connector that acts on a user's account. How the agent handles secret values during the work is in `../../agent-safety/references/secrets.md`; this file is about how the application handles them.

## Pick the credential type

| Situation | Use | Watch out for |
|---|---|---|
| Your app acts for a signed-in user at the provider (their mail, calendar, issues) | OAuth 2.0 authorization code with PKCE and `state`; refresh token through the provider's offline-access option | Granted scopes can be fewer than requested; refresh tokens expire or get revoked |
| Your server calls the provider for your own account | The provider's secret or restricted key, or the client credentials grant | One key per service and environment; restricted keys where the provider offers them |
| Google Workspace data across a domain with no user present | Service account with domain-wide delegation, granted by a Workspace admin | Extremely powerful; restrict delegated scopes; avoid downloadable JSON keys (prefer impersonation or workload identity federation) |
| A CLI or desktop tool | Authorization code with PKCE and a loopback redirect (`http://127.0.0.1:<random port>`), or the device authorization grant | Tokens go in the OS keychain, not a dotfile in the repository |
| A personal script | The provider's personal API token (Atlassian API token, Linear personal key, Outline API key) | Tied to one person and all their access; not for multi-user production services |
| An agent operating an account through MCP | The provider's official remote MCP server with OAuth | Vet any third-party server first (`../../agent-safety/references/vetting-extensions.md`) |
| Public data only | An API key restricted by API, referrer, IP or app signature | Still a secret if it carries quota or billing |

Never use the implicit flow, the resource-owner password grant, or a user's password stored by your app. The out-of-band copy-the-code flow for Google is retired; use a loopback redirect.

## Authorization code flow, done right

1. **Start on the server.** Create a random `state` and a PKCE verifier, keep both in the server session (an `HttpOnly`, `Secure`, `SameSite=Lax` cookie or server store), and redirect with the S256 challenge.

```python
import base64, hashlib, secrets

verifier = secrets.token_urlsafe(64)              # 86 characters, inside the 43-128 range
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
state = secrets.token_urlsafe(32)
# Redirect with response_type=code, client_id, redirect_uri, scope, state,
# code_challenge=challenge, code_challenge_method=S256
```

2. **Register exact redirect URIs.** No wildcards, no open redirect after the callback (validate any `next` parameter against an allowlist).
3. **On the callback,** compare `state` with the stored value before anything else, handle `error=access_denied` as a normal outcome, and exchange the code on the server with the verifier (and the client secret for confidential clients).
4. **Read what was granted.** The token response lists the scopes actually granted. Users can untick scopes on granular consent screens; store the granted set and disable features that lack their scope instead of failing later.
5. **If you receive an ID token** (OpenID Connect), verify its signature, `iss`, `aud`, `exp` and `nonce` with a maintained library before trusting any claim.
6. **Bind the connection to the signed-in user** who started the flow, never to an account ID taken from the callback query.

## Scopes

- Write a scope table before coding: scope, feature that needs it, read or write, and whether the provider classes it as sensitive. Keep it in the repository next to the OAuth config.
- Ask for the narrowest scope that works (a per-file Drive scope instead of the whole Drive, send-only mail instead of full mailbox, read-only issue access until writes are needed). See `google-workspace.md` and `work-tracking-and-wikis.md` for concrete choices.
- Use incremental authorization: request extra scopes when the user first uses the feature that needs them, not at sign-up.
- Broad scopes cost more than risk. Google requires app verification for sensitive scopes and a security assessment for restricted ones before a public app can serve many users. Check this before promising a launch date.

## Storing tokens

| Where the code runs | Store refresh tokens in | Never in |
|---|---|---|
| Server | A dedicated table, encrypted with a managed key (envelope encryption through a KMS), keyed by user or tenant, provider and provider account | Logs, error trackers, analytics, plain columns, the session cookie |
| Browser app | Nowhere: keep provider tokens on your backend and give the browser your own session | `localStorage`, `sessionStorage`, readable cookies |
| CLI or desktop | The OS keychain (macOS Keychain, Windows Credential Manager, Secret Service on Linux; Python `keyring`) | Dotfiles in the project, shell profiles, command arguments |
| Mobile | iOS Keychain or Android Keystore-backed storage | Shared preferences or plain files |

Store alongside the token: granted scopes, expiry, status (`active`, `needs_reconnect`, `revoked`), and the provider account identity. Cache access tokens in memory until a minute before expiry.

## Refresh, expiry and revocation

- **Refresh before expiry**, with a small clock skew. Allow only one refresh per connection at a time (a lock or single-flight); two workers refreshing at once is the usual cause of "random" logouts.
- **Rotating refresh tokens** (Atlassian and others return a new refresh token on each refresh): persist the new token in the same transaction that marks the old one used. Losing it means the user must reconnect.
- **Classify refresh errors.** `invalid_grant` means the grant is gone (revoked, expired, password changed, too many tokens issued): set `needs_reconnect`, notify the user, stop retrying. `invalid_client` means your client secret or configuration is wrong: alert the owner. Timeouts and 5xx: retry later with backoff.
- **Known expiry causes at Google:** refresh tokens of external apps still in "Testing" status expire after 7 days; tokens unused for six months lapse; a per-account limit on live refresh tokens per client silently invalidates the oldest; a password change revokes tokens holding Gmail scopes. Check the current list in Google's OAuth documentation.
- **Disconnect properly.** When the user disconnects or deletes their account, call the provider's revocation endpoint, delete the stored tokens, and delete or schedule deletion of synced data according to your retention policy.
- **Rotate client secrets** with overlap: support two valid secrets during the change, then remove the old one.

## Multi-tenant installations

- One connection record per installation (workspace, site, organization, project). Every call names the tenant; never fall back to "the first token we have".
- Some providers route by a tenant identifier you must fetch after consent (Atlassian's cloud ID from the accessible-resources endpoint); store it with the token.
- Uninstall or deauthorization webhooks must disable the connection and stop jobs for it.

## Agents operating accounts

- Prefer the provider's official remote MCP server or CLI with OAuth over community servers that ask for a pasted token. Read the tool list, choose read-only modes where offered, and keep write tools behind the user's confirmation.
- A tool whose token refresh goes through someone else's server lets that party see or mint your tokens. Treat it as a third-party data processor or reject it.
- Pass tokens through the environment or the tool's own login flow, never as command arguments.

## Pitfalls

| Pitfall | Consequence | Fix |
|---|---|---|
| No `state`, or not compared | Login or account-linking CSRF | Random `state` stored server-side and compared first |
| Wildcard redirect URI or open redirect after callback | Authorization codes stolen | Exact URIs; allowlisted `next` targets |
| Assuming every requested scope was granted | Features fail later with 403 | Store granted scopes; gate features on them |
| Refresh token in `localStorage` | Any XSS takes over the provider account | Backend-held tokens |
| Logging the token response or the `Authorization` header | Tokens in log storage and vendors | Redact in the HTTP client's logging hook |
| Concurrent refresh with rotating tokens | Users disconnected at random | Single-flight refresh; transactional save |
| Personal API token in a production service | Access tied to one employee; breaks when they leave | OAuth app or a service account |
| Service account JSON key committed or shared | Long-lived domain-wide access leaked | Keyless impersonation; org policy blocking key creation; rotation |

## Done when

- [ ] The scope table exists and each scope maps to a feature; nothing broader than needed.
- [ ] The flow uses PKCE and `state`, exact redirect URIs, and server-side code exchange; denial and partial consent are handled.
- [ ] Tokens are encrypted at rest (or in the OS keychain) and absent from logs, URLs and fixtures (checked by test or inspection).
- [ ] Refresh is single-flight, rotation is persisted, and `invalid_grant` leads to a reconnect state with a user-facing message (tested with a fake).
- [ ] Disconnect revokes at the provider and deletes stored tokens; the deletion path for synced data is written down.
