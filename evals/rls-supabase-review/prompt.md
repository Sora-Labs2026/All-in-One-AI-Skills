---
description: Finds row-level security holes in a Supabase migration
tags: [smoke, security, core]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
plugins: ["../.."]
---

Review this Supabase migration before we ship it. Can one signed-in user read or change another user's data, or give themselves something they did not pay for? List each problem with the fix.

```sql
create table public.profiles (
  id uuid primary key references auth.users,
  full_name text,
  plan text not null default 'free'
);
alter table public.profiles enable row level security;
create policy "read profiles" on public.profiles for select using (true);
create policy "edit own profile" on public.profiles for update using (auth.uid() = id);

create table public.invoices (
  id bigserial primary key,
  user_id uuid not null references auth.users,
  amount_cents integer not null
);
alter table public.invoices enable row level security;
create policy "add invoices" on public.invoices for insert to authenticated with check (true);

create view public.invoice_totals as
  select user_id, sum(amount_cents) as total from public.invoices group by user_id;
```
