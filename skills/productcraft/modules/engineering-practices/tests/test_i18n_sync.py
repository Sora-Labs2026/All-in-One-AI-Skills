"""Offline tests for i18n_sync.py using small synthetic catalogs; no network."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "i18n_sync.py"
spec = importlib.util.spec_from_file_location("i18n_sync", SCRIPT)
sync = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sync
spec.loader.exec_module(sync)


class Workspace:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def write(self, name, content):
        path = self.root / name
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def close(self):
        self._tmp.cleanup()


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = sync.main(list(args))
        except SystemExit as exc:  # --help and --version
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def findings(source, target, fmt="json", syntax="auto", ignore=(), changed=None):
    src = sync.parse_json(json.dumps(source), "en.json", fmt)
    tgt = sync.parse_json(json.dumps(target), "xx.json", fmt)
    return {(f.check, f.key): f for f in sync.compare(src, tgt, syntax, list(ignore), changed)}


class JsonStructureTests(unittest.TestCase):
    def test_missing_empty_and_extra_keys(self):
        result = findings({"a": "One", "b": "Two", "c": "Three"}, {"a": "Eins", "b": " ", "z": "Zett"})
        self.assertEqual(result[("missing", "c")].level, "WARN")
        self.assertEqual(result[("empty", "b")].level, "WARN")
        self.assertEqual(result[("extra", "z")].level, "INFO")

    def test_nested_keys_are_flattened_with_dots_and_indexes(self):
        result = findings({"menu": {"items": ["Home", "Help"]}}, {"menu": {"items": ["Start"]}})
        self.assertIn(("missing", "menu.items[1]"), result)

    def test_type_mismatch_in_both_directions(self):
        result = findings({"cart": {"empty": "Empty"}, "title": "T"}, {"cart": "Leer", "title": {"x": "y"}})
        self.assertEqual(result[("type", "cart")].level, "WARN")
        self.assertEqual(result[("type", "title")].level, "WARN")
        self.assertNotIn(("missing", "cart.empty"), result)
        self.assertNotIn(("extra", "title.x"), result)

    def test_non_string_values_compare_types(self):
        result = findings({"n": 3, "m": True}, {"n": "3", "m": False})
        self.assertIn(("type", "n"), result)
        self.assertNotIn(("type", "m"), result)

    def test_duplicate_keys_are_reported(self):
        catalog = sync.parse_json('{"a": "x", "a": "y"}', "dup.json", "json")
        self.assertEqual(catalog.duplicates, ["a"])
        source = sync.parse_json('{"a": "x"}', "en.json", "json")
        keys = {(f.check, f.key) for f in sync.compare(source, catalog, "auto", [])}
        self.assertIn(("duplicate-key", "a"), keys)

    def test_arb_metadata_is_skipped(self):
        src = {"@@locale": "en", "hello": "Hello {name}", "@hello": {"placeholders": {"name": {}}}}
        tgt = {"@@locale": "de", "hello": "Hallo {name}"}
        self.assertEqual(findings(src, tgt, fmt="arb"), {})

    def test_identical_value_is_info_only_when_it_has_letters(self):
        result = findings({"brand": "Acme", "sep": "-"}, {"brand": "Acme", "sep": "-"})
        self.assertEqual(result[("identical", "brand")].level, "INFO")
        self.assertNotIn(("identical", "sep"), result)

    def test_ignore_key_glob(self):
        result = findings({"brand.name": "Acme", "x": "X"}, {"x": "Y"}, ignore=["brand.*"])
        self.assertNotIn(("missing", "brand.name"), result)


class PlaceholderTests(unittest.TestCase):
    def test_icu_argument_renamed(self):
        result = findings({"k": "{count} items"}, {"k": "{anzahl} Artikel"})
        self.assertIn("missing {count}", result[("placeholders", "k")].detail)
        self.assertIn("extra {anzahl}", result[("placeholders", "k")].detail)

    def test_icu_plural_branches_may_differ_but_need_other(self):
        ok = findings({"k": "{n, plural, one {# file} other {# files}}"},
                      {"k": "{n, plural, one {# plik} few {# pliki} many {# plików} other {# pliku}}"})
        self.assertEqual(ok, {})
        bad = findings({"k": "{n, plural, one {# file} other {# files}}"}, {"k": "{n, plural, one {# Datei}}"})
        self.assertIn(("icu-other", "k"), bad)

    def test_icu_nested_argument_and_quoted_braces(self):
        src = {"k": "{n, plural, one {{name} has # item} other {{name} has # items}} '{literal}'"}
        self.assertEqual(findings(src, {"k": "{n, plural, other {{name} hat # Dinge}} '{literal}'"}), {})
        result = findings(src, {"k": "{n, plural, other {hat # Dinge}}"})
        self.assertIn("missing {name}", result[("placeholders", "k")].detail)

    def test_icu_syntax_error(self):
        result = findings({"k": "Hi {name}"}, {"k": "Hallo {name"})
        self.assertIn(("syntax", "k"), result)

    def test_i18next_ruby_and_python_named(self):
        src = {"a": "Hi {{name}}", "b": "Pay %{amount}", "c": "Hello %(user)s"}
        tgt = {"a": "Hallo {{ name }}", "b": "Zahle %{betrag}", "c": "Bonjour %(nom)s"}
        result = findings(src, tgt)
        self.assertNotIn(("placeholders", "a"), result)
        self.assertIn(("placeholders", "b"), result)
        self.assertIn(("placeholders", "c"), result)

    def test_unnumbered_printf_order_and_count(self):
        reordered = findings({"k": "%s of %d"}, {"k": "%d von %s"})
        self.assertIn("different order", reordered[("placeholders", "k")].detail)
        numbered = findings({"k": "%1$s of %2$d"}, {"k": "%2$d von %1$s"})
        self.assertEqual(numbered, {})
        lost = findings({"k": "%s and %s"}, {"k": "%s"})
        self.assertIn("missing %s x1", lost[("placeholders", "k")].detail)

    def test_percent_in_ordinary_text_is_not_a_placeholder(self):
        self.assertEqual(findings({"k": "50% off, 100%% sure"}, {"k": "50 % de rabais, 100%% sûr"}), {})

    def test_markup_tags_must_match(self):
        result = findings({"k": "Read <b>this</b> and <0>terms</0>"}, {"k": "Lies das und <0>AGB</0>"})
        detail = result[("markup", "k")].detail
        self.assertIn("<b>", detail)
        self.assertIn("</b>", detail)
        self.assertNotIn("<0>", detail)

    def test_explicit_printf_syntax_reads_flags(self):
        result = findings({"k": "%5.2f%%"}, {"k": "%.2f %%"}, syntax="printf")
        self.assertNotIn(("placeholders", "k"), result)
        self.assertEqual(sync.extract("%-5d", "printf").ordered, ("%d",))


class PluralKeyTests(unittest.TestCase):
    def test_missing_one_form_is_info_missing_other_is_warn(self):
        src = {"items_one": "{count} item", "items_other": "{count} items"}
        only_other = findings(src, {"items_other": "{count} 個"})
        self.assertEqual(only_other[("plural-form", "items_one")].level, "INFO")
        only_one = findings(src, {"items_one": "{count} Artikel"})
        self.assertEqual(only_one[("missing", "items_other")].level, "WARN")

    def test_extra_categories_are_checked_against_other(self):
        src = {"items_one": "{count} item", "items_other": "{count} items"}
        result = findings(src, {"items_one": "{count} a", "items_few": "{count} b", "items_many": "c",
                                "items_other": "{count} d"})
        self.assertNotIn(("extra", "items_few"), result)
        self.assertIn(("placeholders", "items_many"), result)


PO_SOURCE = r'''# header comment
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"

#, python-format
msgid "Hello %(name)s"
msgstr ""

msgid "One file"
msgid_plural "%d files"
msgstr[0] ""
msgstr[1] ""

msgctxt "menu"
msgid "Open"
msgstr ""

msgid "Line one\n"
"line two"
msgstr ""
'''

PO_TARGET = r'''msgid ""
msgstr ""
"Language: fr\n"

#, fuzzy, python-format
msgid "Hello %(name)s"
msgstr "Bonjour %(name)s"

msgid "One file"
msgid_plural "%d files"
msgstr[0] "Un fichier"
msgstr[1] "%d fichiers"

msgctxt "menu"
msgid "Open"
msgstr ""

#~ msgid "Gone"
#~ msgstr "Parti"
'''


class PoTests(unittest.TestCase):
    def setUp(self):
        self.src = sync.parse_po(PO_SOURCE, "messages.pot")
        self.tgt = sync.parse_po(PO_TARGET, "fr.po")
        self.result = {(f.check, f.key): f for f in sync.compare(self.src, self.tgt, "auto", [])}

    def test_header_skipped_and_continuations_joined(self):
        self.assertNotIn("", self.src.entries)
        self.assertIn("Line one\nline two", self.src.entries)

    def test_fuzzy_untranslated_missing_and_obsolete(self):
        self.assertIn(("fuzzy", "Hello %(name)s"), self.result)
        self.assertIn(("untranslated", "menu | Open"), self.result)
        self.assertIn(("missing", "Line one\\nline two"), self.result)
        self.assertEqual(self.tgt.obsolete, 1)
        self.assertIn(("obsolete", "-"), self.result)

    def test_plural_singular_may_drop_the_number(self):
        self.assertNotIn(("placeholders", "One file"), self.result)

    def test_po_placeholder_mismatch(self):
        tgt = sync.parse_po('msgid "Hello %(name)s"\nmsgstr "Bonjour %(nom)s"\n', "fr.po")
        keys = {(f.check, f.key) for f in sync.compare(self.src, tgt, "auto", [])}
        self.assertIn(("placeholders", "Hello %(name)s"), keys)

    def test_bad_po_line_is_an_input_error(self):
        with self.assertRaises(sync.InputError):
            sync.parse_po('msgid "a"\nnonsense here\n', "bad.po")


ANDROID_SOURCE = '''<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">
  <string name="app_name" translatable="false">Acme</string>
  <string name="welcome">Welcome, <xliff:g id="name">%1$s</xliff:g>!</string>
  <plurals name="songs"><item quantity="one">%d song</item><item quantity="other">%d songs</item></plurals>
  <string-array name="days"><item>Mon</item><item>Tue</item></string-array>
</resources>'''

ANDROID_TARGET = '''<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">
  <string name="welcome">Witaj, %1$s!</string>
  <plurals name="songs"><item quantity="one">%d utwór</item><item quantity="few">%d utwory</item>
  <item quantity="other">%d utworu</item></plurals>
  <string-array name="days"><item>Pon</item></string-array>
</resources>'''


class AndroidTests(unittest.TestCase):
    def test_android_catalogs(self):
        src = sync.parse_android(ANDROID_SOURCE, "values/strings.xml")
        tgt = sync.parse_android(ANDROID_TARGET, "values-pl/strings.xml")
        self.assertNotIn("app_name", src.entries)
        result = {(f.check, f.key): f for f in sync.compare(src, tgt, "auto", [])}
        self.assertIn("xliff:g", result[("markup", "welcome")].detail)
        self.assertIn(("missing", "days[1]"), result)
        self.assertNotIn(("extra", "songs_few"), result)
        self.assertNotIn(("placeholders", "songs_few"), result)

    def test_wrong_root_is_an_input_error(self):
        with self.assertRaises(sync.InputError):
            sync.parse_android("<root/>", "x.xml")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.en = self.ws.write("en.json", {"a": "Hi {name}", "b": "Bye"})
        self.de = self.ws.write("de.json", {"a": "Hallo {nom}"})

    def tearDown(self):
        self.ws.close()

    def test_exit_codes_and_strict(self):
        code, out, _ = run_cli(self.en, self.de)
        self.assertEqual(code, 0)
        self.assertIn("WARN  missing", out)
        code, _, _ = run_cli(self.en, self.de, "--strict")
        self.assertEqual(code, 1)
        clean = self.ws.write("fr.json", {"a": "Salut {name}", "b": "Au revoir"})
        code, _, _ = run_cli(self.en, clean, "--strict")
        self.assertEqual(code, 0)

    def test_input_errors_exit_2(self):
        broken = self.ws.write("broken.json", "{not json")
        code, _, err = run_cli(self.en, broken)
        self.assertEqual(code, 2)
        self.assertIn("invalid JSON", err)
        code, _, _ = run_cli(self.en, str(self.ws.root / "absent.json"))
        self.assertEqual(code, 2)
        po = self.ws.write("de.po", 'msgid "a"\nmsgstr "b"\n')
        code, _, err = run_cli(self.en, po)
        self.assertEqual(code, 2)
        unknown = self.ws.write("de.yaml", "a: b")
        code, _, _ = run_cli(self.en, unknown)
        self.assertEqual(code, 2)

    def test_help_and_version(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("Read-only", out)
        code, out, _ = run_cli("--version")
        self.assertEqual(code, 0)

    def test_json_output_is_deterministic_and_has_no_translations(self):
        first = run_cli(self.en, self.de, "--json")[1]
        second = run_cli(self.en, self.de, "--json")[1]
        self.assertEqual(first, second)
        data = json.loads(first)
        self.assertEqual(data["summary"]["warn"], 2)
        self.assertNotIn("Hallo", first)

    def test_previous_source_flags_changed_keys(self):
        old = self.ws.write("en.old.json", {"a": "Hi {name}", "b": "Goodbye"})
        target = self.ws.write("fr.json", {"a": "Salut {name}", "b": "Au revoir"})
        code, out, _ = run_cli(self.en, target, "--previous-source", old)
        self.assertEqual(code, 0)
        self.assertIn("source-changed", out)
        self.assertIn("1 key(s) changed", out)

    def test_hide_info(self):
        target = self.ws.write("fr.json", {"a": "Salut {name}", "b": "Bye", "zz": "x"})
        out = run_cli(self.en, target, "--hide-info")[1]
        self.assertNotIn("INFO  ", out)


if __name__ == "__main__":
    unittest.main()
