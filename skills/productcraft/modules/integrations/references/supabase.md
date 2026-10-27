# Supabase

Read this when building on Supabase: Postgres with row-level security, Auth, Storage, Realtime and Edge Functions, through the client libraries and the Supabase CLI. Reviewing an existing project for exploitable rules is covered by LaunchGuard's Supabase playbook (`../../launchguard/references/stack-playbooks.md`) and by `../../code-security-review/references/mobile-apps.md` for apps that talk to Supabase directly; this file is the build side. Schema changes also follow `../../engineering-practices/references/data-and-migrations.md`.

Supabase moves quickly (new API key formats, JWT signing keys, client helpers). Check the installed `@supabase/supabase-js`, `@supabase/ssr` and CLI versions and the current docs before relying on a detail here.

## Keys and clients

| Key | Where it may go | What it can do |
|---|---|---|
| Publishable key (`sb_publishable_...`) or the legacy `anon` key | Browsers and mobile apps | Whatever RLS policies allow the `anon` and `authenticated` roles |
| Secret key (`sb_secret_...`) or the legacy `service_role` key | Server code only | Bypasses RLS entirely |

- Build the admin (secret-key) client in a server-only module (in Next.js, a file that imports `server-only`) and use it only for jobs that genuinely need to bypass RLS. Every such path checks ownership itself.
- For user requests on the server, create a client per request carrying the user's session, so RLS applies to the query.
- Legacy and new keys can coexist during migration; rotating or disabling the legacy keys is a dashboard step for the owner.

## Local development with the CLI

- `supabase init` creates `supabase/` (config, migrations, seed, tests). `supabase start` runs the full stack locally in Docker and prints local URLs and keys; `supabase stop` stops it.
- The user runs `supabase login` and `supabase link --project-ref <ref>` themselves; linking gives the CLI access to the remote project.
- Work locally first. Anything that touches the linked remote project (`supabase db push`, `supabase functions deploy`, `supabase secrets set`, dashboard changes) needs the user's explicit permission and, for production, a backup and rollback plan.

## Schema and migrations

- Create migrations with `supabase migration new <name>` and write the SQL, or make changes in local Studio and capture them with `supabase db diff -f <name>`; review the generated SQL before committing.
- `supabase db reset` rebuilds the *local* database from migrations and `supabase/seed.sql`. It is destructive locally and must never be pointed at a remote project.
- Run `../../engineering-practices/scripts/migration_check.py --dialect postgres` on new migration files.
- Generate types from the schema (`supabase gen types typescript --local > src/lib/database.types.ts`) and pass them to the client; regenerate in CI and fail when the committed file differs.

## Row-level security

Enable RLS on every table in an exposed schema (by default `public`) in the same migration that creates it, then add one policy per operation and role.

```sql
alter table public.documents enable row level security;

create policy "members read org documents"
  on public.documents for select to authenticated
  using (exists (
    select 1 from public.memberships m
    where m.org_id = documents.org_id and m.user_id = (select auth.uid())
  ));

create policy "members create documents they own"
  on public.documents for insert to authenticated
  with check (
    owner_id = (select auth.uid())
    and exists (select 1 from public.memberships m
                where m.org_id = documents.org_id and m.user_id = (select auth.uid()))
  );

create index on public.memberships (user_id, org_id);
```

- `using` filters rows that can be read, updated or deleted; `with check` validates rows being written. Updates usually need both, or a user can move a row into another tenant.
- Write `(select auth.uid())` rather than `auth.uid()` so Postgres evaluates it once per statement, and index every column a policy filters on.
- Authorize from your own tables or from `app_metadata` set by the server. `user_metadata` is editable by the user and must not grant anything.
- Helper functions marked `security definer` run with their owner's rights: keep them in a schema that is not exposed through the API, set `search_path = ''`, and qualify every name.
- Views run with their creator's rights and skip RLS unless created `with (security_invoker = true)` (Postgres 15 and later).

**Test policies** with pgTAP through `supabase test db`, impersonating users inside a rolled-back transaction:

```sql
begin;
select plan(2);
set local role authenticated;
set local request.jwt.claims = '{"sub": "00000000-0000-0000-0000-0000000000a1"}';
select is((select count(*) from public.documents where org_id = '00000000-0000-0000-0000-0000000000b2'),
          0::bigint, 'user A sees no documents of org B');
select throws_ok($$ insert into public.documents (org_id, owner_id, title)
                    values ('00000000-0000-0000-0000-0000000000b2', '00000000-0000-0000-0000-0000000000a1', 'x') $$,
                 '42501', null, 'user A cannot write into org B');
select * from finish();
rollback;
```

Cover the anonymous role, two users in two tenants, and every operation, including updates that try to change `org_id` or `owner_id`.

## Auth

- Use `@supabase/ssr` for server-rendered frameworks; it keeps the session in cookies and refreshes it in middleware.
- On the server, authorize with a verified identity: `supabase.auth.getUser()` (asks the Auth server) or, in recent versions with asymmetric JWT signing keys, `getClaims()` (verifies the token locally). `getSession()` returns what the cookie says without verifying it; fine for UI hints in the browser, never for server-side decisions.
- Configure the redirect URL allowlist precisely; wildcards invite open redirects.
- The built-in email sender is for development and is heavily rate-limited; production needs a custom SMTP provider. Login abuse defenses belong to `../../credential-shield/GUIDE.md`.

## Edge Functions

- Deno runtime. `supabase functions new <name>`, `supabase functions serve` locally; deploying is a remote change that needs permission.
- JWT verification is on by default. Turn it off only for endpoints that verify something else, such as a provider webhook signature (`webhooks.md`).
- Inside a function, create the Supabase client with the caller's `Authorization` header so RLS applies; use the secret key only where bypassing RLS is the point.
- Secrets are set with `supabase secrets set` from an env file the user prepares (values never on the command line or in chat) and read with `Deno.env.get`.

## Storage and Realtime

- Keep user files in private buckets with policies on `storage.objects`, typically scoping the first path segment to the user or tenant: `(storage.foldername(name))[1] = (select auth.uid())::text`. Serve them with short-lived signed URLs. Set per-bucket size and MIME limits. Public buckets are for genuinely public assets only.
- Postgres Changes subscriptions respect the subscriber's RLS but evaluate it for every change and subscriber, which gets expensive at scale; prefer Broadcast for high-volume updates. Use private channels with RLS on `realtime.messages` for Broadcast and Presence that are not public. Unsubscribe when components unmount.

## Connecting from servers

- Serverless and edge runtimes connect through the connection pooler in transaction mode, which does not support session features such as prepared statements; disable them in the ORM or driver. Migrations and long-lived workers use session mode or a direct connection. Check the project's connection settings for ports and IPv4 or IPv6 availability.
- Set statement timeouts for roles used by the API; long queries from clients otherwise hold connections.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Table created without RLS, or RLS enabled with no policies tested | RLS in the same migration; pgTAP tests for each operation |
| Secret or `service_role` key in a browser, mobile app or `NEXT_PUBLIC_` variable | Server-only module; rotate a leaked key (LaunchGuard leak response) |
| `getSession()` trusted on the server | `getUser()` or `getClaims()` |
| Authorization based on `user_metadata` | Tables or `app_metadata` set by the server |
| Policy calls `auth.uid()` per row and filters unindexed columns | `(select auth.uid())` and indexes |
| `security definer` function in `public` without a fixed `search_path` | Private schema, `search_path = ''`, qualified names |
| `supabase db push` or dashboard edits made by the agent on its own | Prepare the command; the user runs or approves it |

## Done when

- [ ] Every exposed table has RLS and per-operation policies, with pgTAP or integration tests covering anonymous access, two users and two tenants.
- [ ] Secret keys appear only in server-only modules; server code authorizes with a verified identity.
- [ ] Migrations are created with the CLI, checked with `migration_check.py`, and generated types match the schema in CI.
- [ ] Storage buckets holding user files are private with path-scoped policies; Edge Functions either verify the JWT or a provider signature.
- [ ] Every remote change (push, deploy, secrets) is listed for the user with its rollback.
