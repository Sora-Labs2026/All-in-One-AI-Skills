"""Offline tests for migration_check.py using synthetic SQL only; no database or network."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migration_check.py"
spec = importlib.util.spec_from_file_location("migration_check", SCRIPT)
mc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mc
spec.loader.exec_module(mc)


def codes(sql, dialect="postgres", status="open"):
    findings, _ = mc.check_sql(sql, "m.sql", dialect)
    return sorted({f.code for f in findings if f.status == status})


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = mc.main(list(args))
        except SystemExit as exc:  # argparse --help / --version
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class ParsingTests(unittest.TestCase):
    def test_comments_strings_and_dollar_quotes_are_ignored(self):
        sql = (
            "-- DROP TABLE users;\n"
            "/* TRUNCATE accounts; */\n"
            "INSERT INTO notes (body) VALUES ('drop table x; truncate y');\n"
            "CREATE FUNCTION f() RETURNS void AS $fn$ BEGIN DELETE FROM t; END $fn$ LANGUAGE plpgsql;\n"
        )
        self.assertEqual(codes(sql), [])

    def test_quoted_identifier_does_not_match_keywords(self):
        sql = 'CREATE INDEX "concurrently" ON "orders" (id);'
        self.assertIn("INDEX_LOCKS_WRITES", codes(sql))

    def test_statement_lines_are_reported(self):
        sql = "SET lock_timeout = '5s';\n\nALTER TABLE users\n  DROP COLUMN legacy;\n"
        findings, count = mc.check_sql(sql, "m.sql", "postgres")
        self.assertEqual(count, 2)
        self.assertEqual([(f.code, f.line) for f in findings], [("DROP_COLUMN", 3)])

    def test_mysql_hash_comment(self):
        sql = "# DROP TABLE users;\nALTER TABLE t ADD COLUMN c int NULL, ALGORITHM=INSTANT;\n"
        self.assertEqual(codes(sql, "mysql"), ["NO_LOCK_TIMEOUT"])


class RuleTests(unittest.TestCase):
    def test_destructive_statements(self):
        self.assertIn("DROP_TABLE", codes("DROP TABLE IF EXISTS users;"))
        self.assertIn("TRUNCATE", codes("TRUNCATE audit_log;"))
        self.assertIn("FULL_TABLE_DELETE", codes("DELETE FROM sessions;"))
        self.assertIn("DROP_SCHEMA_OR_DATABASE", codes("DROP SCHEMA reporting CASCADE;"))

    def test_multiple_alter_actions(self):
        found = codes("ALTER TABLE users ADD COLUMN nickname text, DROP COLUMN legacy;")
        self.assertIn("DROP_COLUMN", found)
        self.assertNotIn("NOT_NULL_NO_DEFAULT", found)

    def test_drop_constraint_and_default_are_not_column_drops(self):
        found = codes("ALTER TABLE users DROP CONSTRAINT users_fk, ALTER COLUMN a DROP DEFAULT;")
        self.assertNotIn("DROP_COLUMN", found)

    def test_rename_column_and_table(self):
        self.assertIn("RENAME", codes("ALTER TABLE users RENAME COLUMN name TO full_name;"))
        self.assertIn("RENAME", codes("ALTER TABLE users RENAME TO members;"))
        self.assertNotIn("RENAME", codes("ALTER TABLE users RENAME CONSTRAINT a TO b;"))

    def test_not_null_column(self):
        self.assertIn("NOT_NULL_NO_DEFAULT", codes("ALTER TABLE users ADD COLUMN plan text NOT NULL;"))
        self.assertNotIn("NOT_NULL_NO_DEFAULT", codes("ALTER TABLE users ADD COLUMN plan text NOT NULL DEFAULT 'free';"))
        self.assertNotIn("NOT_NULL_NO_DEFAULT", codes("ALTER TABLE users ADD COLUMN plan text;"))

    def test_rewrite_defaults(self):
        self.assertIn("ADD_COLUMN_REWRITE", codes("ALTER TABLE users ADD COLUMN token uuid DEFAULT gen_random_uuid();"))
        self.assertIn("ADD_COLUMN_REWRITE", codes("ALTER TABLE users ADD COLUMN seq bigserial;"))
        self.assertNotIn("ADD_COLUMN_REWRITE", codes("ALTER TABLE users ADD COLUMN created_at timestamptz DEFAULT now();"))

    def test_type_change_and_set_not_null(self):
        self.assertIn("ALTER_COLUMN_TYPE", codes("ALTER TABLE users ALTER COLUMN id TYPE bigint;"))
        self.assertIn("ALTER_COLUMN_TYPE", codes("ALTER TABLE users MODIFY COLUMN id bigint;", "mysql"))
        self.assertIn("SET_NOT_NULL", codes("ALTER TABLE users ALTER COLUMN email SET NOT NULL;"))
        self.assertNotIn("SET_NOT_NULL", codes("ALTER TABLE users ALTER COLUMN email SET NOT NULL;", "generic"))

    def test_constraints(self):
        self.assertIn("FK_VALIDATES_NOW", codes("ALTER TABLE a ADD CONSTRAINT a_b FOREIGN KEY (b_id) REFERENCES b (id);"))
        self.assertNotIn("FK_VALIDATES_NOW", codes("ALTER TABLE a ADD CONSTRAINT a_b FOREIGN KEY (b_id) REFERENCES b (id) NOT VALID;"))
        self.assertIn("CHECK_VALIDATES_NOW", codes("ALTER TABLE a ADD CONSTRAINT pos CHECK (n > 0);"))
        self.assertIn("UNIQUE_OR_PK_LOCKS", codes("ALTER TABLE a ADD CONSTRAINT a_email UNIQUE (email);"))
        self.assertNotIn("UNIQUE_OR_PK_LOCKS", codes("ALTER TABLE a ADD CONSTRAINT a_email UNIQUE USING INDEX a_email_idx;"))

    def test_index_rules(self):
        self.assertIn("INDEX_LOCKS_WRITES", codes("CREATE INDEX users_email ON users (email);"))
        self.assertNotIn("INDEX_LOCKS_WRITES", codes("CREATE INDEX CONCURRENTLY users_email ON users (email);"))
        self.assertIn("DROP_INDEX_LOCKS", codes("DROP INDEX users_email;"))
        self.assertNotIn("INDEX_LOCKS_WRITES", codes("CREATE INDEX users_email ON users (email);", "mysql"))

    def test_new_table_in_same_file_is_not_flagged(self):
        sql = (
            "CREATE TABLE invoices (id bigint PRIMARY KEY, total numeric NOT NULL);\n"
            "CREATE INDEX invoices_total ON invoices (total);\n"
            "ALTER TABLE invoices ADD CONSTRAINT inv_org FOREIGN KEY (org_id) REFERENCES orgs (id);\n"
        )
        self.assertEqual(codes(sql), [])

    def test_concurrently_inside_transaction(self):
        sql = "BEGIN;\nCREATE INDEX CONCURRENTLY a_b ON a (b);\nCOMMIT;\n"
        self.assertIn("CONCURRENTLY_IN_TRANSACTION", codes(sql))
        self.assertNotIn("CONCURRENTLY_IN_TRANSACTION", codes("CREATE INDEX CONCURRENTLY a_b ON a (b);"))

    def test_updates(self):
        self.assertIn("FULL_TABLE_UPDATE", codes("UPDATE users SET active = true;"))
        self.assertEqual(codes("UPDATE users SET active = true WHERE id = 1;"), ["DATA_BACKFILL"])

    def test_lock_timeout(self):
        self.assertIn("NO_LOCK_TIMEOUT", codes("ALTER TABLE users DROP COLUMN a;"))
        self.assertNotIn("NO_LOCK_TIMEOUT", codes("SET lock_timeout = '5s';\nALTER TABLE users DROP COLUMN a;"))
        self.assertNotIn("NO_LOCK_TIMEOUT", codes("ALTER TABLE users DROP COLUMN a;", "generic"))

    def test_mysql_algorithm(self):
        self.assertIn("MYSQL_NO_ALGORITHM", codes("ALTER TABLE t ADD COLUMN c int NULL;", "mysql"))
        self.assertNotIn("MYSQL_NO_ALGORITHM", codes("ALTER TABLE t ADD COLUMN c int NULL;", "postgres"))


class AllowTests(unittest.TestCase):
    def test_allow_above_statement(self):
        sql = "SET lock_timeout = '5s';\n-- migration-check: allow DROP_COLUMN reads removed in 4.2\nALTER TABLE u DROP COLUMN a;\n"
        findings, _ = mc.check_sql(sql, "m.sql", "postgres")
        self.assertEqual([(f.code, f.status, f.ack_reason) for f in findings],
                         [("DROP_COLUMN", "acknowledged", "reads removed in 4.2")])

    def test_trailing_allow_applies_to_its_own_statement_only(self):
        sql = (
            "SET lock_timeout = '5s';\n"
            "ALTER TABLE u DROP COLUMN a; -- migration-check: allow DROP_COLUMN\n"
            "ALTER TABLE u DROP COLUMN b;\n"
        )
        findings, _ = mc.check_sql(sql, "m.sql", "postgres")
        by_line = {f.line: f.status for f in findings}
        self.assertEqual(by_line, {2: "acknowledged", 3: "open"})

    def test_allow_file(self):
        sql = "-- migration-check: allow-file NO_LOCK_TIMEOUT tool sets it\nALTER TABLE u ADD COLUMN c int;\n"
        self.assertEqual(codes(sql), [])
        self.assertEqual(codes(sql, status="acknowledged"), ["NO_LOCK_TIMEOUT"])


class CliTests(unittest.TestCase):
    def test_help_and_list_rules(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("Read-only", out)
        code, out, _ = run_cli("--list-rules")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), len(mc.RULE_LIST))

    def test_strict_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            risky = Path(d) / "002_drop.sql"
            risky.write_text("SET lock_timeout = '5s';\nALTER TABLE u DROP COLUMN a;\n")
            code, out, _ = run_cli("--strict", "--format", "json", d)
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["summary"]["HIGH"], 1)
            self.assertEqual(data["findings"][0]["code"], "DROP_COLUMN")
            risky.write_text("SET lock_timeout = '5s';\nALTER TABLE u ADD COLUMN c int;\n")
            code, out, _ = run_cli("--strict", d)
            self.assertEqual(code, 0)
            self.assertIn("No findings", out)

    def test_missing_down_and_pairing(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "0001_init.up.sql").write_text("CREATE TABLE a (id int);\n")
            _, out, _ = run_cli("--format", "json", d)
            self.assertEqual([f["code"] for f in json.loads(out)["findings"]], ["MISSING_DOWN"])
            (Path(d) / "0001_init.down.sql").write_text("DROP TABLE a; -- migration-check: allow DROP_TABLE down path\n")
            _, out, _ = run_cli("--format", "json", d)
            data = json.loads(out)
            self.assertEqual(data["summary"]["acknowledged"], 1)
            self.assertNotIn("MISSING_DOWN", [f["code"] for f in data["findings"]])

    def test_path_errors(self):
        code, _, _ = run_cli("does-not-exist.sql")
        self.assertEqual(code, 2)
        with tempfile.TemporaryDirectory() as d:
            code, _, err = run_cli(d)
            self.assertEqual(code, 2)
            self.assertIn("no .sql files", err)
        code, _, _ = run_cli()
        self.assertEqual(code, 2)

    def test_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "b.sql").write_text("DROP TABLE b;\n")
            (Path(d) / "a.sql").write_text("TRUNCATE a;\n")
            first = run_cli("--format", "json", d)[1]
            second = run_cli("--format", "json", d)[1]
            self.assertEqual(first, second)
            files = [f["file"] for f in json.loads(first)["findings"]]
            self.assertEqual(files, sorted(files))


if __name__ == "__main__":
    unittest.main()
