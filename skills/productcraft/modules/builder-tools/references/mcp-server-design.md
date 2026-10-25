# Designing an MCP server an agent can use well

Read this before writing or reviewing a Model Context Protocol (MCP) server. Implementation and testing are in `mcp-server-build-and-test.md`.

Contents: decide the surface · tool names · granularity · input schemas · outputs · errors · pagination and size · annotations and side effects · auth and secrets · transports and network safety · review checklist.

## Decide the surface

An MCP server exposes three kinds of things:
- **Tools**: actions the model chooses to call (search, read a record, create a ticket). Most servers are mostly tools.
- **Resources**: read-only content the client application attaches by URI (a file, a schema, a document). Use them when the user or client picks the context, not the model.
- **Prompts**: reusable message templates the user invokes. Optional.

Start from the jobs an agent will do with the service ("find the customer, read their open invoices, add a note"), not from the API reference. Write down 5 to 10 such jobs; every tool should serve at least one, and every job should be doable in a few calls.

## Tool names

- `service_verb_noun` in snake_case: `billing_search_invoices`, `billing_get_invoice`, `billing_create_credit_note`. The prefix keeps names unique when a host loads several servers.
- The protocol allows 1 to 128 characters of letters, digits, `_`, `-` and `.`; some clients are stricter, so stay under 64 characters and avoid dots.
- Use the same verbs across the server: `search` (query, returns summaries), `list` (enumerate, filtered), `get` (one item by id, full detail), `create`, `update`, `delete`.
- The name and description must match what the tool does exactly; a model chooses by them.

## Granularity

- **Not one tool per endpoint.** Agents pay context for every tool description and make more mistakes choosing among near-duplicates. Merge endpoints the agent would always call together (fetch an order with its lines and customer name in one `get`).
- **Not one tool with a `mode` argument** that does unrelated things. Different side effects deserve different tools, so a host can allow reads and confirm writes.
- **Separate read from write.** Never hide a write inside a tool that sounds like a read.
- **Return identifiers that other tools accept.** A search result should carry the id `get` needs, so the agent can chain calls without guessing.
- A small number of well-chosen tools (often under 15) beats full API coverage. Add tools when evaluation shows a job the agent cannot complete.

## Input schemas

The input schema is the contract the model reads, so make it precise:
- Every parameter has a type and a description with an example value and units: "Due date, ISO 8601 date such as 2026-03-31".
- Use enums for closed sets, bounds for numbers (`limit` 1 to 100), patterns or formats for ids, dates and emails, and length limits for free text.
- Required only when truly required; give optional parameters safe defaults and say what the default is.
- Accept what the agent naturally has. If users refer to customers by name, offer search by name instead of requiring an internal id.
- Validate on the server anyway. The schema guides the model; it does not protect you.

## Outputs

- **Return what the next step needs, not the raw API payload.** Drop internal fields, nulls, HTML, tracking metadata. Keep ids, human-readable names, statuses, timestamps (ISO 8601 with time zone) and links.
- **Return structured content** with a declared output schema when the SDK supports it (typed return values in the Python SDK, `outputSchema` plus `structuredContent` in TypeScript), so clients and code can use the data directly. Include a text rendering for clients that only show text.
- **Names next to ids** ("Ada Lovelace (usr_123)") let the model talk to the user without another lookup.
- **Results are untrusted input to the model.** Records can contain text written by anyone, including instructions aimed at the agent. Return them as data, do not add text that looks like instructions, and never let a result alone trigger a privileged action.

## Errors an agent can act on

There are two kinds:
- **Tool errors** (the call ran but failed: not found, invalid value, permission denied, rate limited) are returned as a result marked as an error, with a message for the model. Raise the SDK's tool-error type or return the error flag; the model reads it and can recover.
- **Protocol errors** (unknown tool, malformed request) are for the client; the SDK produces them.

A good tool-error message says what went wrong, why, and what to do next, using the server's own tool and parameter names:
- "No invoice with id 'inv_99'. Call billing_search_invoices with the customer's name to find valid ids."
- "Parameter 'due_date' must be an ISO 8601 date such as 2026-03-31; got '31/03/2026'."
- "Rate limit reached (60 requests per minute). Retry after 20 seconds or narrow the query with 'status'."
- "Permission denied: this API key can read invoices but not create credit notes. Ask the user to grant 'billing:write'."

Never put stack traces, SQL, internal hostnames, tokens or other users' data in messages. Depending on the SDK version, an unexpected exception reaches the model either as a generic failure or with its raw message, so catch expected failures and raise deliberate messages, and log the details server-side (to stderr for stdio servers).

## Pagination and response size

- Any tool that can return many items takes a `limit` (with a default such as 20 and a maximum) and returns a continuation token: `{"items": [...], "total": 143, "next_cursor": "..."}`, with `next_cursor` null on the last page.
- Make cursors opaque (encode the offset or upstream token) and reject malformed ones with a message saying to pass the previous `next_cursor` unchanged.
- Offer filters that shrink results at the source (status, date range, owner) rather than relying on the agent to page through everything.
- Cap the size of any single result. When content is too large (a long document, a big log), return the first part plus how to get more (`offset`, a section name, a narrower query) and say it was truncated. A silent cut looks like the whole answer.
- Summaries in search, detail in `get`: list results carry a few fields per item; the full record comes from the detail tool.

## Annotations and side effects

Declare behavior hints on each tool: read-only, destructive, idempotent, and open world (talks to systems outside the server's own data). Clients use them to decide when to ask the user for confirmation. They are hints from the server, not a security boundary: enforce permissions in the server and in the upstream API.

For tools that change things:
- Require explicit identifiers, never a search query, for update and delete.
- Make creates safe to retry (accept an idempotency key or check for an existing equivalent).
- Offer a `dry_run` or preview for bulk or irreversible operations, and report exactly what changed.
- Never expose arbitrary command execution, raw SQL or unrestricted file or URL access as a convenience tool.

## Auth and secrets

- **Local (stdio) servers:** read credentials from environment variables or the OS keychain, provided through the client's server configuration. Fail at startup with a clear message naming the missing variable. Never accept secrets as tool arguments, return them in results, or write them to logs.
- **Remote (HTTP) servers:** follow the protocol's authorization model (OAuth 2.1-based): the server validates access tokens issued for it (check issuer, audience or resource, expiry and scopes), publishes its protected-resource metadata, and maps scopes to tools. Do not forward the client's token to upstream APIs; obtain upstream credentials separately for the server.
- **Least privilege:** request the narrowest upstream scopes; consider separate read-only and read-write deployments.
- Apply the matching controls from `../../launchguard/references/security-baseline.md` (secrets, server-side authorization, input validation, rate limits) to any server that touches user data.

## Transports and network safety

- **stdio** for local tools launched by the client. stdout carries the protocol only: any stray print corrupts the message stream. Log to stderr.
- **Streamable HTTP** for remote or shared servers. Bind to `127.0.0.1` when it is meant to be local, validate the `Origin` and `Host` headers to block DNS rebinding, require authentication, and put it behind TLS when remote. The older SSE transport is deprecated; support it only for old clients.
- Tools that touch files resolve paths and refuse anything outside an allowed root (no `..` escapes, no symlinks out). Tools that fetch URLs use an allowlist and block private and link-local addresses (SSRF, CWE-918). Tools that run programs pass argument lists, never shell strings built from input (CWE-78).
- Bound everything: request timeouts upstream, maximum result sizes, maximum page sizes, and per-client rate limits.

## Review checklist

- [ ] Each tool maps to a written agent job; no near-duplicate tools; reads and writes separated.
- [ ] Names prefixed and consistent; descriptions say when to use the tool and what it returns.
- [ ] Every parameter typed, described with an example, bounded; server-side validation present.
- [ ] Outputs trimmed, structured, with ids and names; large results paginated or truncated with a note.
- [ ] Error messages tell the model what to do next; no internals or secrets in messages or logs.
- [ ] Annotations set; destructive tools need ids, support preview or idempotency, and are enforced server-side.
- [ ] Credentials from environment or a token validated for this server; nothing secret in arguments, results or logs.
- [ ] stdio servers never write to stdout; HTTP servers check Origin, require auth and bind narrowly.
