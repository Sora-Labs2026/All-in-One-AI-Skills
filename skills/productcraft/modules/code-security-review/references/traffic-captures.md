# Analyzing captured HTTP traffic

Read this when the evidence for a review is a capture of HTTP traffic: a HAR file from browser developer tools, or a session exported from an intercepting proxy. A capture shows what a client and server actually exchanged, which is useful for finding secrets in transit, over-returned data, missing security headers, and authorization that depends on the client. It is also a dense pile of someone's real session, so the first job is to handle it without leaking what it contains.

A capture is a static artifact. Reading it sends no traffic and needs no live target, so it does not carry the authorization rules of `dynamic-web-testing.md`. What it does carry is other people's secrets and personal data, so treat the whole file as sensitive input.

## Treat the capture as secret input

A capture routinely contains live session cookies, bearer tokens, API keys, CSRF tokens, passwords in form posts, and personal data in bodies. Before anything else:

- **Keep it out of the repository and out of chat.** Store it in a scratch or temporary location, never commit it, and never paste its raw contents into a reply. A session cookie in a capture is a working credential until it expires.
- **Confirm it is yours to analyze.** A capture of your own test session is fine. A capture of another person's session, or of a third-party service you do not own, is personal data you should not be handling without their consent and a reason.
- **Summarize before you read.** Get the shape of the capture (hosts, methods, status codes, where credentials appear) from the summarizer below before opening individual requests, so you read the few that matter rather than scrolling through everyone's tokens.
- **Redact anything you quote.** When a finding needs an example, cite the request by method, host and path with the value removed (`Authorization: <redacted>`, `?token=<redacted>`), and report a credential by type and location, never by value (`../../agent-safety/references/secrets.md`). If a real credential is exposed, it is `ROTATION REQUIRED`; the owner must rotate it, because it was transmitted and may be logged elsewhere.

## The summarizer

`scripts/har_summary.py` reads a HAR file and prints an aggregate summary and a redaction report without printing any header value, cookie value, body or query-string value. It is standard-library only, read-only and never touches the network.

```bash
python3 <productcraft>/modules/code-security-review/scripts/har_summary.py capture.har
python3 <productcraft>/modules/code-security-review/scripts/har_summary.py --verbose --top 30 capture.har
python3 <productcraft>/modules/code-security-review/scripts/har_summary.py --strict capture.har   # exit 1 if a secret-looking parameter rides in a URL
```

`<productcraft>` is the folder where the ProductCraft skill is installed. It reports the request count, the breakdown by host, method, status class and content type, and a signals block: how many requests carried an authorization or API-key header, how many carried cookies, how many responses set cookies, how many had a body, and how many had a secret-looking parameter in the URL (with the parameter names, never their values). Query strings are stripped to parameter names and token-shaped path segments are replaced with `<redacted>`. The signals are leads to confirm, not findings; a clean run means only that the fields it checks held no signal.

For a proxy-session export in another format, convert it to HAR (most proxies and browsers export HAR) and summarize it the same way, or apply the same discipline by hand: never read values into your output, aggregate first, quote redacted.

## What a capture is good for

Once you know the shape, read the requests that matter and look for:

- **Secrets in the wrong place.** A token or key in a URL query string or path ends up in server logs, browser history, referrer headers and proxy logs; it belongs in a header or body. The `--strict` flag catches the query case. Also check for long-lived tokens where short-lived ones are expected.
- **Plain HTTP.** Any request on `http://` rather than `https://` exposes everything in it. Note the host and the data it carried.
- **Over-returned data.** A response that includes password hashes, internal IDs, other users' records, full objects where the client needs two fields, or stack traces. Map this to baseline #17 (trim API responses) and the over-return class in `vulnerability-classes.md`.
- **Cookie flags.** Session cookies set without `HttpOnly`, `Secure` or an appropriate `SameSite`, visible in `Set-Cookie` responses. Confirm against the app's intent: a deliberately client-readable non-secret cookie is fine (baseline #9).
- **Missing security headers** on HTML responses (content security policy, HSTS where HTTPS is established, nosniff, frame policy), consistent with LaunchGuard gate 3. A capture shows the *effective* headers the client received, which source configuration alone does not.
- **Authorization that lives in the client.** A request that carries the role, price, tenant or `isAdmin` as a parameter the server appears to trust, or an object reference that could be changed to another user's. These are leads to confirm in the code.
- **CORS and third-party calls.** Responses with permissive `Access-Control-Allow-Origin`, and requests sending the app's data to analytics or other third-party hosts you did not expect (map third-party data flows for the privacy review).

## From capture to finding

A capture shows what happened once; it does not prove why. Every signal is a lead that you confirm in the source the module's way (phase 5): find the code that set the cookie, built the response, or read the client-supplied value, and show the path. A secret in a URL is confirmed from the capture alone (it is right there); an authorization gap seen in one request needs the source trace plus, where justified and authorized, the dynamic check in `dynamic-web-testing.md`. Rate severity from impact and reach, fix with a regression test (`fix-and-verify.md`), and cite the baseline control or vulnerability class each finding breaks.

## Done when

- The capture was stored outside the repository, confirmed as yours to analyze, and never pasted or committed in raw form.
- It was summarized before individual requests were read, and every quoted request has its credential and personal-data values redacted.
- Each signal (secret in a URL, plain HTTP, over-return, weak cookie flag, missing header, client-trusted authorization) was confirmed in the source before being reported, and any exposed real credential is marked `ROTATION REQUIRED`.
