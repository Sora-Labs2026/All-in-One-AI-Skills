"""Offline tests for rls_check.py. Synthetic migrations only: no database, no network, no real projects."""
import contextlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rls_check.py"
spec = importlib.util.spec_from_file_location("rls_check", SCRIPT)
rc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rc
spec.loader.exec_module(rc)

OWNED = """
create table public.notes (id uuid primary key, user_id uuid not null, body text);
alter table public.notes enable row level security;
create policy "notes read own" on public.notes for select to authenticated using ((select auth.uid()) = user_id);
create policy "notes insert own" on public.notes for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "notes update own" on public.notes for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "notes delete own" on public.notes for delete to authenticated using ((select auth.uid()) = user_id);
"""


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rc.main(["--root", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def leads(self, sql, *args, name="supabase/migrations/20260101000000_init.sql"):
        write(self.root, name, sql)
        code, out, _ = self.run_tool("--json", *args)
        self.assertEqual(code, 0)
        return json.loads(out)["leads"]

    def ids(self, sql, *args):
        return sorted(d["id"] for d in self.leads(sql, *args) if d["level"] != "info")


class TableRules(Base):
    def test_owner_policies_give_no_leads(self):
        self.assertEqual(self.ids(OWNED), [])

    def test_table_without_rls(self):
        leads = self.leads("create table public.orders (id int, user_id uuid);")
        self.assertEqual([(d["id"], d["level"], d["line"]) for d in leads], [("RLS-DISABLED", "high", 1)])

    def test_rls_disabled_in_a_later_migration_points_at_the_disable(self):
        write(self.root, "supabase/migrations/1_a.sql", OWNED)
        write(self.root, "supabase/migrations/2_b.sql", "\n\nalter table public.notes disable row level security;")
        _, out, _ = self.run_tool("--json")
        lead = [d for d in json.loads(out)["leads"] if d["id"] == "RLS-DISABLED"][0]
        self.assertEqual((lead["file"], lead["line"]), ("supabase/migrations/2_b.sql", 3))

    def test_migration_order_follows_file_names(self):
        write(self.root, "supabase/migrations/1_create.sql", "create table public.t (id int);")
        write(self.root, "supabase/migrations/2_enable.sql", "alter table public.t enable row level security;\n"
                                                              "create policy p on public.t for select to anon using (id > 0);")
        _, out, _ = self.run_tool("--json")
        self.assertEqual([d["id"] for d in json.loads(out)["leads"]], [])

    def test_rls_without_any_client_policy_is_low(self):
        leads = self.leads("create table public.jobs (id int);\nalter table public.jobs enable row level security;\n"
                           "create policy svc on public.jobs to service_role using (true);")
        self.assertEqual([(d["id"], d["level"]) for d in leads], [("RLS-NO-POLICY", "low")])

    def test_restrictive_only_counts_as_no_policy(self):
        ids = self.ids("create table public.t (id int); alter table public.t enable row level security;\n"
                       "create policy r on public.t as restrictive for select to authenticated using (id > 0);")
        self.assertEqual(ids, ["RLS-NO-POLICY"])

    def test_private_schema_is_ignored_unless_exposed(self):
        sql = "create table private.audit (id int);"
        self.assertEqual(self.ids(sql), [])
        self.assertEqual(self.ids(sql, "--exposed-schema", "private"), ["RLS-DISABLED"])

    def test_temp_tables_are_ignored(self):
        self.assertEqual(self.ids("create temp table scratch (id int);\ncreate temporary table s2 (id int);"), [])

    def test_quoted_names_only_and_several_actions(self):
        sql = ('create table if not exists "public"."Orders" (id int);\n'
               'alter table only public."Orders" enable row level security, force row level security;\n'
               'create policy "o" on public."Orders" for select to authenticated using ((select auth.uid()) is not null and id > 0);')
        write(self.root, "m.sql", sql)
        _, out, _ = self.run_tool("--json")
        result = json.loads(out)
        self.assertEqual([d["id"] for d in result["leads"]], [])
        self.assertEqual(result["tables"], [{"table": "public.Orders", "rls": True, "force": True, "policies": 1}])

    def test_rename_keeps_rls_and_policies(self):
        sql = OWNED + "\nalter table public.notes rename to memos;"
        write(self.root, "m.sql", sql)
        _, out, _ = self.run_tool("--json")
        result = json.loads(out)
        self.assertEqual(result["leads"], [])
        self.assertEqual(result["tables"][0]["table"], "public.memos")
        self.assertEqual(result["tables"][0]["policies"], 4)

    def test_rename_column_is_not_a_table_rename(self):
        write(self.root, "m.sql", OWNED + "\nalter table public.notes rename column body to text;")
        _, out, _ = self.run_tool("--json")
        self.assertEqual(json.loads(out)["tables"][0]["table"], "public.notes")

    def test_dropped_table_has_no_leads(self):
        self.assertEqual(self.ids("create table public.old (id int);\ndrop table if exists public.old cascade;"), [])


class PolicyRules(Base):
    def table(self, policies):
        return "create table public.t (id int, user_id uuid);\nalter table public.t enable row level security;\n" + policies

    def test_select_true_for_anon_is_medium_read(self):
        leads = self.leads(self.table("create policy p on public.t for select to anon using (true);"))
        self.assertEqual([(d["id"], d["level"]) for d in leads], [("POLICY-TRUE-READ", "medium")])
        self.assertIn("anyone holding the public key", leads[0]["message"])

    def test_policy_without_to_applies_to_public(self):
        self.assertEqual(self.ids(self.table("create policy p on public.t for select using (true);")), ["POLICY-TRUE-READ"])

    def test_policy_without_for_applies_to_all_and_writes(self):
        self.assertEqual(self.ids(self.table("create policy p on public.t to authenticated using (true);")),
                         ["POLICY-TRUE-READ", "POLICY-TRUE-WRITE"])

    def test_with_check_true_on_update_is_high(self):
        leads = self.leads(self.table(
            "create policy p on public.t for update to authenticated using ((select auth.uid()) = user_id) with check (true);"))
        self.assertEqual([(d["id"], d["level"]) for d in leads], [("POLICY-TRUE-WRITE", "high")])

    def test_insert_with_check_true_is_high(self):
        self.assertEqual(self.ids(self.table("create policy p on public.t for insert to authenticated with check (true);")),
                         ["POLICY-TRUE-WRITE"])

    def test_messages_distinguish_using_from_with_check(self):
        delete_all = self.leads(self.table("create policy p on public.t for delete to authenticated using (true);"))
        self.assertIn("may delete every row", delete_all[0]["message"])
        check_only = self.leads(self.table(
            "create policy p on public.t for update to authenticated using ((select auth.uid()) = user_id) with check (true);"))
        self.assertIn("into the rows its USING allows", check_only[0]["message"])
        insert_any = self.leads(self.table("create policy p on public.t for insert to anon with check (true);"))
        self.assertIn("another user's id", insert_any[0]["message"])

    def test_all_with_using_true_and_no_with_check_is_one_write_lead(self):
        leads = self.leads(self.table("create policy p on public.t for all to authenticated using (true);"))
        self.assertEqual(sorted(d["id"] for d in leads), ["POLICY-TRUE-READ", "POLICY-TRUE-WRITE"])

    def test_update_without_with_check_reuses_using_and_is_quiet(self):
        sql = self.table("create policy p on public.t for update to authenticated using ((select auth.uid()) = user_id);")
        self.assertEqual(self.ids(sql), [])

    def test_insert_without_with_check_admits_nothing_and_is_quiet(self):
        self.assertEqual(self.ids(self.table("create policy p on public.t for insert to authenticated;")), [])

    def test_true_forms_are_recognized(self):
        for expr in ("(true)", "1 = 1", "'t'::boolean", "TRUE"):
            with self.subTest(expr=expr):
                self.assertEqual(self.ids(self.table(f"create policy p on public.t for delete to anon using ({expr});")),
                                 ["POLICY-TRUE-WRITE"])

    def test_service_role_policies_are_ignored(self):
        self.assertEqual(self.ids(self.table(
            "create policy svc on public.t to service_role using (true) with check (true);\n"
            "create policy own on public.t for select to authenticated using ((select auth.uid()) = user_id);")), [])

    def test_signed_in_only(self):
        for expr in ("auth.uid() is not null", "(select auth.role()) = 'authenticated'", "auth.role() = 'authenticated'::text"):
            with self.subTest(expr=expr):
                self.assertEqual(self.ids(self.table(f"create policy p on public.t for select to authenticated using ({expr});")),
                                 ["POLICY-SIGNED-IN"])

    def test_signed_in_combined_with_an_owner_check_is_quiet(self):
        sql = self.table("create policy p on public.t for select to authenticated "
                         "using (auth.uid() is not null and (select auth.uid()) = user_id);")
        self.assertEqual(self.ids(sql), [])

    def test_user_metadata_is_high_even_for_restrictive_policies(self):
        sql = self.table("create policy p on public.t as restrictive for select to authenticated "
                         "using ((auth.jwt() -> 'user_metadata' ->> 'role') = 'admin');")
        self.assertIn("POLICY-USER-METADATA", self.ids(sql))

    def test_dropped_policy_has_no_leads(self):
        sql = self.table("create policy p on public.t for select to anon using (true);\n"
                         "create policy own on public.t for select to authenticated using ((select auth.uid()) = user_id);\n"
                         "drop policy if exists p on public.t;")
        self.assertEqual(self.ids(sql), [])

    def test_alter_policy_updates_expressions_and_roles(self):
        sql = self.table("create policy p on public.t for select to anon using (true);\n"
                         "alter policy p on public.t to authenticated using ((select auth.uid()) = user_id);")
        self.assertEqual(self.ids(sql), [])

    def test_unwrapped_uid_is_info_only(self):
        leads = self.leads(self.table("create policy p on public.t for select to authenticated using (auth.uid() = user_id);"))
        self.assertEqual([(d["id"], d["level"]) for d in leads], [("POLICY-UID-PERF", "info")])

    def test_storage_objects_policies_are_checked(self):
        sql = "create policy up on storage.objects for insert to authenticated with check (true);"
        self.assertEqual(self.ids(sql), ["POLICY-TRUE-WRITE"])

    def test_expression_text_does_not_set_roles(self):
        sql = self.table("create policy p on public.t for select using (status = 'sent to anon');")
        leads = self.leads(sql)
        self.assertEqual(leads, [])


class ViewAndFunctionRules(Base):
    def test_view_without_invoker_is_high(self):
        self.assertEqual(self.ids("create view public.v as select 1;"), ["VIEW-BYPASSES-RLS"])

    def test_view_with_invoker_is_quiet(self):
        for opts in ("with (security_invoker = true)", "with (security_invoker=on)", "with (security_barrier, security_invoker)"):
            with self.subTest(opts=opts):
                self.assertEqual(self.ids(f"create or replace view public.v {opts} as select 1;"), [])

    def test_alter_view_set_invoker(self):
        self.assertEqual(self.ids("create view public.v as select 1;\nalter view public.v set (security_invoker = true);"), [])

    def test_revoking_client_roles_closes_a_view(self):
        sql = "create view public.v as select 1;\nrevoke all on public.v from anon, authenticated;"
        self.assertEqual(self.ids(sql), [])
        self.assertEqual(self.ids("create view public.v as select 1;\nrevoke all on public.v from anon;"),
                         ["VIEW-BYPASSES-RLS"])

    def test_materialized_view(self):
        self.assertEqual(self.ids("create materialized view public.mv as select 1;"), ["MATVIEW-EXPOSED"])

    def test_security_definer_function(self):
        sql = ("create or replace function public.is_admin() returns boolean language sql security definer\n"
               "as $$ select exists (select 1 from public.admins where id = auth.uid()) $$;")
        self.assertEqual(self.ids(sql), ["SECDEF-EXPOSED", "SECDEF-SEARCH-PATH"])

    def test_security_definer_in_private_schema_with_search_path_is_quiet(self):
        sql = ("create function private.is_admin() returns boolean language sql security definer set search_path = ''\n"
               "as $fn$ select true $fn$;")
        self.assertEqual(self.ids(sql), [])

    def test_revoking_execute_needs_public_too(self):
        base = ("create function public.f() returns int language sql security definer set search_path = '' as $$ select 1 $$;\n")
        self.assertEqual(self.ids(base + "revoke execute on function public.f() from anon, authenticated;"), ["SECDEF-EXPOSED"])
        self.assertEqual(self.ids(base + "revoke execute on function public.f() from public, anon, authenticated;"), [])

    def test_invoker_function_is_quiet(self):
        self.assertEqual(self.ids("create function public.f() returns int language sql as $$ select 1 $$;"), [])


class Parsing(Base):
    def test_comments_and_bodies_are_not_statements(self):
        sql = ("-- create table public.ghost (id int);\n/* create table public.ghost2 (id int); /* nested */ */\n"
               "create function public.g() returns void language plpgsql security invoker as $$\n"
               "begin create table public.inside (id int); end $$;\n")
        self.assertEqual(self.ids(sql), [])

    def test_semicolons_inside_strings(self):
        sql = ("create table public.t (id int, note text default 'a; create table public.x (id int);');\n"
               "alter table public.t enable row level security;\n"
               "create policy p on public.t for select to authenticated using ((select auth.uid()) is not null and id > 0);")
        self.assertEqual(self.ids(sql), [])

    def test_line_numbers(self):
        statements = rc.split_statements("\n\n  create table a (id int);\n-- c\ncreate table b (\n id int);")
        self.assertEqual([s["line"] for s in statements], [3, 5])

    def test_do_block_changing_rls_is_reported_as_info(self):
        leads = self.leads("do $$ begin execute 'alter table public.x enable row level security'; end $$;")
        self.assertEqual([(d["id"], d["level"]) for d in leads], [("DYNAMIC-SQL", "info")])


class EnvScan(Base):
    def test_public_secret_env_reports_name_not_value(self):
        value = "eyJ" + "x" * 40
        write(self.root, ".env.local", f"NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY={value}\nNEXT_PUBLIC_SUPABASE_URL=http://localhost\n")
        write(self.root, "src/lib/db.ts", "const k = import.meta.env.VITE_SUPABASE_SECRET_KEY;\n")
        code, out, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIn("NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY", out)
        self.assertIn("VITE_SUPABASE_SECRET_KEY", out)
        self.assertNotIn(value, out)
        self.assertNotIn("NEXT_PUBLIC_SUPABASE_URL", out)

    def test_no_env_flag_and_node_modules_are_skipped(self):
        write(self.root, "node_modules/x/index.js", "process.env.NEXT_PUBLIC_SERVICE_ROLE_KEY")
        _, out, _ = self.run_tool("--json")
        self.assertEqual(json.loads(out)["leads"], [])
        write(self.root, "app.ts", "process.env.NEXT_PUBLIC_SERVICE_ROLE_KEY")
        _, out, _ = self.run_tool("--json", "--no-env")
        self.assertEqual(json.loads(out)["leads"], [])


class Cli(Base):
    def test_not_applicable_without_sql(self):
        code, out, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertIn("NOT_APPLICABLE", out)

    def test_fail_on(self):
        write(self.root, "m.sql", "create table public.t (id int);")
        self.assertEqual(self.run_tool("--fail-on", "high")[0], 1)
        write(self.root, "m.sql", OWNED)
        self.assertEqual(self.run_tool("--fail-on", "low")[0], 0)

    def test_file_mode_uses_given_order_and_skips_env(self):
        a = write(self.root, "b_second.sql", "alter table public.t enable row level security;\n"
                                             "create policy p on public.t for select to anon using (id > 0);")
        b = write(self.root, "a_first.sql", "create table public.t (id int);")
        write(self.root, ".env", "NEXT_PUBLIC_SERVICE_ROLE_KEY=x")
        code, out, _ = self.run_tool("--json", "--file", str(b), "--file", str(a))
        self.assertEqual(json.loads(out)["leads"], [])

    def test_bad_arguments(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(rc.main(["--root", str(self.root / "missing")]), 2)
            self.assertEqual(rc.main(["--root", str(self.root), "--file", str(self.root / "nope.sql")]), 2)

    def test_json_out_is_private(self):
        write(self.root, "m.sql", OWNED)
        target = self.root / "report.json"
        self.run_tool("--json-out", str(target))
        self.assertEqual(json.loads(target.read_text())["status"], "NO_LEADS")
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_output_is_deterministic(self):
        write(self.root, "m.sql", "create table public.b (id int);\ncreate table public.a (id int);\ncreate view public.v as select 1;")
        first = self.run_tool("--json")[1]
        self.assertEqual(first, self.run_tool("--json")[1])
        self.assertEqual([d["object"] for d in json.loads(first)["leads"]], ["public.b", "public.a", "public.v"])


if __name__ == "__main__":
    unittest.main()
