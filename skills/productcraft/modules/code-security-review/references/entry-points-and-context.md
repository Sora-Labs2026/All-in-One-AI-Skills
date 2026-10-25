# Entry points, access levels and context notes

Phase 1 needs every entry point; phase 2 needs to know who can reach each one; phase 3 sometimes needs a careful reading of unfamiliar code before any judgment. This file covers all three. [Threat modeling](threat-modeling.md#step-4-entry-points-and-trust-boundaries) lists the entry points teams forget; the [codebase map](../../codebase-map/GUIDE.md) and `code_audit.py map` find common route registrations. Here: how to get a complete list, how to classify access, the surfaces web checklists skip, and how to write down what code assumes.

## 1. Ask the framework for its route table

A search finds the routes you thought to search for. The framework's own table lists everything registered, including routes added by plugins, decorators and generated code. These commands start the application, so read what they load first, give it dummy secrets and a local database, and run them only with the user's go-ahead ([audit phases](audit-phases.md#phase-0-scope-and-rules-of-engagement)).

| Stack | Command or source |
|---|---|
| Rails | `bin/rails routes --expanded` |
| Django | `python manage.py show_urls` (from django-extensions, if installed), or walk `django.urls.get_resolver().url_patterns` in a shell |
| Flask | `flask --app <module> routes` |
| FastAPI | `/openapi.json` from a local run. Routes declared with `include_in_schema=False` are missing from it, so search for those too |
| Laravel | `php artisan route:list -v` (shows middleware per route) |
| Spring Boot | `/actuator/mappings` on a local run with that endpoint enabled; otherwise search `@RequestMapping` and its variants |
| ASP.NET Core | Search for `MapGet`, `MapPost` and the other `Map*` calls, `MapControllers`, `[Http*]` and `[Route]` attributes; list endpoints in a local debug session |
| Next.js | `next build` prints the route list; also every `app/**/route.ts` or `.js`, `pages/api/**`, every file with `"use server"`, and the `matcher` of the middleware file |
| GraphQL | The schema (SDL files or local introspection): every query, mutation and subscription field, and nested resolvers that load other objects |
| gRPC, Thrift | Every service method in the `.proto` or IDL files |
| Express, Koa, Fastify, Go routers and others | `code_audit.py map`, then read the router setup files |

Compare the result with any OpenAPI specification in the repository. Routes in the code but not in the spec are the ones nobody reviews.

## 2. Surfaces outside the web routes

| Surface | Where entries are declared | What the outsider controls |
|---|---|---|
| Command-line tools | Argument parsers (argparse, click, cobra, clap), environment variables, config files read at start, stdin | Everything, if anyone but the owner can run it, or if it is invoked through `sudo` or setuid |
| Electron apps | `ipcMain.handle` / `ipcMain.on` handlers, APIs exposed with `contextBridge.exposeInMainWorld`, `webPreferences` (`nodeIntegration`, `contextIsolation`, `sandbox`), `shell.openExternal` calls, custom protocol handlers, `will-navigate` and `setWindowOpenHandler` | Any page or script running in a renderer, including injected content |
| Tauri apps | Functions marked `#[tauri::command]` and the capability files that expose them | The web view's content |
| Browser extensions | `runtime.onMessage`, `runtime.onMessageExternal` with `externally_connectable`, content scripts listening to `window` `message` events (check `event.origin` and `event.source`), `web_accessible_resources` | Every web page the extension runs on |
| Mobile apps | Android exported components, intent filters and deep links; iOS URL schemes, universal links and app extensions; push notification payloads ([mobile apps and their backends](mobile-apps.md)) | Other apps on the device, links, notifications |
| Libraries and SDKs | Every exported function, class, method and option, and every parser or deserializer in the public API | Whatever callers pass; the library cannot assume its callers validated anything it does not document |
| Plugins and extension points | Plugin loaders, template helpers, user scripts, webhook "transform" fields | Plugin authors and tenants who configure them |
| Internal services | HTTP or gRPC endpoints that other services call | Anyone on the network path, unless the caller is authenticated (mutual TLS, signed service tokens). "Internal" is a network location, not an identity |
| Smart contracts | Section 4 | Any account on the chain |

## 3. Classify access for every entry point

| Class | Meaning | Evidence |
|---|---|---|
| **Open** | No identity needed | The full middleware or guard chain read, with nothing on the path |
| **Any account** | Any authenticated identity. With free signup, treat it as Open for risk | Where identity is established |
| **Role or ownership** | A role, permission or ownership condition | The check's code, the identity it uses, and where that identity comes from |
| **Service only** | Only another service or contract can call it, and the caller is verified | The verifying check (mutual TLS, a signed token, a `msg.sender` compared with an address that is itself established) |
| **Operator only** | Needs shell, deploy or console access | The deployment fact, or `NOT_VERIFIED` |
| **Unclear** | A guard exists but its logic, identity source or configured values are not settled | Goes to the review list with the open question |

Rules:

- **Read the guard, not its name.** `requireAdmin` that reads `role` from a token claim the client can edit, or `onlyOwner` comparing with an owner variable that an unprotected setter can change, protects nothing.
- **Find inherited guards and where they stop.** A base controller, a router group, a decorator stack or a parent contract may apply a guard; note which entries it covers and which sit outside the group.
- **Callbacks and webhooks are Open** until they verify the caller: a signature check, a shared secret compared in constant time, or a caller-address check. A name like `onPaymentSucceeded` is not access control.
- **Setup paths are often Open once.** Installers, `/setup` routes, "first user becomes admin" flows and upgradeable-contract `initialize` functions; check what happens if an attacker calls them first or calls them again.
- **Rank state-changing entries first**, without dropping reads of sensitive data or reads other code trusts.

Record the classification in one table; it feeds threat-model step 4 and the coverage matrix:

| Entry | File:line | Access class | Guard (file:line) | Identity from | Changes state? | Open question |
|---|---|---|---|---|---|---|
| `POST /api/projects/:id/archive` | `src/routes/projects.ts:88` | Role or ownership | `assertMember` at `src/auth/members.ts:21` | session cookie | yes | does `assertMember` check the role, or only membership? |

## 4. Smart-contract entry points

Externally callable functions that change state come first, because they can move value. Read-only functions matter when other contracts rely on their answers (oracles, share prices, read-only reentrancy). Work only on local chains and forks, as [language pitfalls](language-pitfalls.md#solidity-basics) requires; [smart contracts](smart-contracts.md) covers the review itself.

| Platform | Entry points | Access checks to read |
|---|---|---|
| Solidity | `external` and `public` functions that are not `view` or `pure`, `receive()`, `fallback()`, functions inherited from base contracts (ownership transfer, role grants, upgrade functions), `initialize` and `reinitializer` | Modifiers (`onlyOwner`, `onlyRole`), inline `require(msg.sender == ...)`, signature checks, whether the owner or role variable can be changed by someone else |
| Vyper | `@external` functions without `@view` or `@pure`, `__default__` | `assert msg.sender == ...` and the variables compared against |
| Solana (Anchor) | Functions in the `#[program]` module; for native programs, the instruction dispatch in `process_instruction` | Account constraints in `#[derive(Accounts)]`: `Signer`, `has_one`, `constraint`, `seeds` and `bump`, account owner checks. Missing signer, owner or PDA checks are the common gaps |
| Move (Aptos, Sui) | `public entry fun` and `public fun` (callable from transaction scripts or programmable transactions) | `signer` arguments, capability objects, object ownership, `public(package)` and `friend` limits |
| CosmWasm | `instantiate`, `execute` (each `ExecuteMsg` variant), `migrate`, `sudo` (chain governance only), `reply` | `info.sender` checks against stored admin or owner addresses |
| TON | FunC `recv_internal` and `recv_external` (external messages need replay protection before `accept_message()`); Tact `receive` handlers | Sender address checks, message op codes |

```bash
# State-changing external and public Solidity functions, including signatures split over several lines
rg -n -U -P --glob '*.sol' \
  'function\s+\w+\s*\([^)]*\)(?:(?!\b(?:view|pure)\b)[^{;])*\b(?:external|public)\b(?:(?!\b(?:view|pure)\b)[^{;])*[{;]' .
```

Add `receive`, `fallback` and inherited functions by hand; a search sees only what this repository declares.

For each entry, record its access class, the check, the value it can move, and the external calls it makes (each one is a reentrancy and callback surface).

## 5. Context notes before judging unfamiliar code

Write these when the code is critical (authentication, money, tenant isolation, parsers, cryptography) and unfamiliar, or when a candidate depends on what another function guarantees. They describe the code; verdicts come later, in phase 5.

```text
parse_frame (src/proto.c:120)
  Needs on entry:   len <= 512                        established by: UNCHECKED (caller read_packet:88 passes the header value)
  Ensures on exit:  out holds len - 8 bytes           only when len >= 16 (early return at :118)
  Relies on:        read_header() rejects len > 4096  verified at src/proto.c:61, on the main path only; error path at :70 skips it
  State touched:    conn->buf, conn->state
  Open questions:   can conn->state be READY when read_header failed?
```

- **Follow every call into the callee,** and every path through it: error branches, early returns, flags and alternate modes, not only the path that succeeds. A limit often looks enforced only because the value came back from a function whose name suggests it was checked.
- **A name is not evidence.** `validated_input`, `safe_path` and `sanitize()` are claims until you have read what they do.
- **Mark every assumption that nothing enforces with the same marker,** `UNCHECKED`, and cite the line where the check should be. Then `rg -n UNCHECKED security/context/` lists every gap for the hunt, and each one becomes a candidate.
- **Treat code you cannot read as untrusted:** a closed-source library, a binary, an external contract, a remote API, a model's output. Assume only what its documentation promises for the pinned version.
- **When two notes disagree, keep both** and add an open question; the disagreement is a fact about the code.
- **After the notes for one flow, write the rules that span functions,** such as "every write to `balances` follows a debit in the same transaction" or "every query on tenant tables passes through `scoped()`". Each rule becomes a coverage cell.
- Keep notes in `security/context/` with the other local audit outputs, and ask before committing them. Skip this for code that is small or already understood; it costs time.

## Done when

- The entry-point list comes from the framework's own table where one exists, cross-checked against searches and any API specification, plus every non-web surface in section 2 that the project has.
- Every entry has an access class backed by the guard's code (or Unclear with the question), and the identity source for each guard is recorded.
- Contract entries, where present, list the access check, value moved and external calls.
- Critical unfamiliar code has context notes, and every `UNCHECKED` assumption is on the hunt list.
