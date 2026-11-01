#!/usr/bin/env python3
"""ProductCraft Engineering Practices: read-only check that translation catalogs match their source.

Compares one source-language catalog with one or more target-language catalogs
and reports, per target: missing keys, keys the source no longer has, empty
values, placeholders and markup that differ from the source, keys whose type
differs (text in one file, a nested group in the other), duplicate keys, fuzzy
or untranslated gettext entries, ICU plural or select arguments without an
`other` branch, and values identical to the source (possibly untranslated).
With --previous-source it also lists keys whose source text changed, so their
existing translations can be reviewed.

Formats: JSON (nested or flat, including i18next plural suffixes), ARB
(metadata entries skipped), gettext PO/POT and Android strings.xml.

It never edits files, never uses the network and never prints translated
text; findings show keys and placeholder tokens only. A clean result says the
catalogs are structurally in step. It does not say the translations are good:
that takes a fluent reviewer looking at the strings in the running product.

Exit status: 0 on success (findings may exist), 1 with --strict when any WARN
finding remains, 2 for a usage error or a file that cannot be read or parsed.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
MAX_SIZE = 20 * 1024 * 1024
LEVEL_ORDER = {"WARN": 0, "INFO": 1}
PLURAL_CATEGORIES = ("zero", "one", "two", "few", "many", "other")
FORMATS = ("auto", "json", "arb", "po", "android")
SYNTAXES = ("auto", "icu", "i18next", "printf", "ruby")

# Placeholder patterns. "auto" keeps printf narrow (no flags or width) so that
# ordinary text such as "50% off" is not mistaken for a conversion.
RE_DOUBLE_BRACE = re.compile(r"\{\{\s*-?\s*([^{}]*?)\s*\}\}")
RE_RUBY = re.compile(r"%\{\s*([A-Za-z0-9_.]+)\s*\}")
RE_NESTING = re.compile(r"\$t\(\s*([^()]+?)\s*\)")
RE_PY_NAMED = re.compile(r"%\(([A-Za-z0-9_]+)\)[-+ 0#]*\d*(?:\.\d+)?[sdifrxXeEgGc]")
RE_PRINTF_NARROW = re.compile(r"%(?:(\d+)\$)?(?:\.\d+)?(?:ll|l|h|L|z)?([sdifuxX@])")
RE_PRINTF_FULL = re.compile(
    r"%(?:(\d+)\$)?[-+ 0#']*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|L|q|j|z|t)?([diouxXeEfFgGaAcsp@])"
)
RE_TAG = re.compile(r"<(/?)([A-Za-z0-9_][A-Za-z0-9_:.-]*)[^<>]*?(/?)\s*>")


@dataclass
class Entry:
    """One translatable unit. `forms` holds plural forms for PO and Android."""

    text: Optional[str]
    forms: List[str] = field(default_factory=list)
    kind: str = "text"  # text | other (number, bool, null)
    fuzzy: bool = False
    source_forms: List[str] = field(default_factory=list)  # PO: msgid and msgid_plural


@dataclass
class Catalog:
    path: str
    fmt: str
    entries: Dict[str, Entry]
    duplicates: List[str] = field(default_factory=list)
    obsolete: int = 0
    group_prefixes: set = field(default_factory=set)


@dataclass(frozen=True)
class Finding:
    level: str
    check: str
    key: str
    detail: str = ""

    def as_dict(self) -> dict:
        return {"level": self.level, "check": self.check, "key": self.key, "detail": self.detail}


class InputError(Exception):
    """A file that cannot be read or parsed."""


# ---------------------------------------------------------------- loading


def read_text(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise InputError(f"{path}: cannot read ({exc.strerror or exc})") from None
    if size > MAX_SIZE:
        raise InputError(f"{path}: larger than {MAX_SIZE // (1024 * 1024)} MB")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InputError(f"{path}: cannot read ({exc.strerror or exc})") from None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{path}: not UTF-8 text") from None


def detect_format(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    suffix = path.suffix.lower()
    if suffix == ".arb":
        return "arb"
    if suffix in (".po", ".pot"):
        return "po"
    if suffix == ".xml":
        return "android"
    if suffix == ".json":
        return "json"
    raise InputError(f"{path}: unknown format; pass --format")


def load_catalog(path: Path, requested: str) -> Catalog:
    fmt = detect_format(path, requested)
    text = read_text(path)
    if fmt in ("json", "arb"):
        return parse_json(text, str(path), fmt)
    if fmt == "po":
        return parse_po(text, str(path))
    return parse_android(text, str(path))


def parse_json(text: str, path: str, fmt: str) -> Catalog:
    duplicates: List[str] = []

    def pairs_hook(pairs):
        seen = set()
        for key, _ in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        return dict(pairs)

    try:
        data = json.loads(text, object_pairs_hook=pairs_hook)
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}") from None
    if not isinstance(data, dict):
        raise InputError(f"{path}: top level must be a JSON object")
    entries: Dict[str, Entry] = {}
    groups: set = set()

    def walk(value, key: str) -> None:
        if isinstance(value, dict):
            if key:
                groups.add(key)
            for child, inner in value.items():
                if fmt == "arb" and not key and child.startswith("@"):
                    continue  # ARB metadata such as @@locale and @key descriptions
                walk(inner, f"{key}.{child}" if key else child)
        elif isinstance(value, list):
            if key:
                groups.add(key)
            for index, inner in enumerate(value):
                walk(inner, f"{key}[{index}]")
        elif isinstance(value, str):
            entries[key] = Entry(text=value)
        else:
            entries[key] = Entry(text=None, kind="other")

    walk(data, "")
    return Catalog(path, fmt, entries, sorted(set(duplicates)), group_prefixes=groups)


def _unescape_po(value: str) -> str:
    out, i = [], 0
    mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            out.append(mapping.get(value[i + 1], value[i + 1]))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


RE_PO_LINE = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+"(.*)"\s*$')
RE_PO_CONT = re.compile(r'^"(.*)"\s*$')


def parse_po(text: str, path: str) -> Catalog:
    entries: Dict[str, Entry] = {}
    duplicates: List[str] = []
    obsolete = 0
    blocks: List[List[str]] = [[]]
    for line in text.splitlines():
        if not line.strip():
            if blocks[-1]:
                blocks.append([])
            continue
        blocks[-1].append(line.strip())
    for number, block in enumerate(blocks, 1):
        if not block:
            continue
        if all(line.startswith("#") for line in block):
            if any(line.startswith("#~") for line in block):
                obsolete += 1
            continue  # comment-only block, or an obsolete entry kept with #~
        fuzzy = any(line.startswith("#,") and "fuzzy" in line for line in block)
        fields: Dict[str, str] = {}
        forms: Dict[int, str] = {}
        current: Optional[Tuple[str, Optional[int]]] = None
        for line in block:
            if line.startswith("#"):
                continue
            match = RE_PO_LINE.match(line)
            if match:
                name, index, value = match.group(1), match.group(2), match.group(3)
                if index is not None:
                    current = ("msgstr", int(index))
                    forms[int(index)] = _unescape_po(value)
                else:
                    current = (name, None)
                    fields[name] = _unescape_po(value)
                continue
            cont = RE_PO_CONT.match(line)
            if cont and current is not None:
                name, index = current
                if index is not None:
                    forms[index] += _unescape_po(cont.group(1))
                else:
                    fields[name] += _unescape_po(cont.group(1))
                continue
            raise InputError(f"{path}: cannot parse PO entry {number}: unexpected line")
        if "msgid" not in fields:
            raise InputError(f"{path}: PO entry {number} has no msgid")
        msgid = fields["msgid"]
        if msgid == "" and "msgctxt" not in fields:
            continue  # header entry
        key = msgid if "msgctxt" not in fields else f"{fields['msgctxt']}\u0004{msgid}"
        if key in entries:
            duplicates.append(key)
        if "msgid_plural" in fields:
            entries[key] = Entry(text=msgid, forms=[forms[i] for i in sorted(forms)], fuzzy=fuzzy,
                                 source_forms=[msgid, fields["msgid_plural"]])
        else:
            entries[key] = Entry(text=msgid, forms=[fields.get("msgstr", "")], fuzzy=fuzzy,
                                 source_forms=[msgid])
    return Catalog(path, "po", entries, sorted(set(duplicates)), obsolete=obsolete)


def _inner_xml(element: ET.Element) -> str:
    parts = [element.text or ""]
    for child in element:
        parts.append(ET.tostring(child, encoding="unicode"))
    return "".join(parts)


def parse_android(text: str, path: str) -> Catalog:
    ET.register_namespace("xliff", "urn:oasis:names:tc:xliff:document:1.2")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise InputError(f"{path}: invalid XML: {exc}") from None
    if root.tag != "resources":
        raise InputError(f"{path}: expected a <resources> root element")
    entries: Dict[str, Entry] = {}
    duplicates: List[str] = []
    groups: set = set()

    def add(key: str, entry: Entry) -> None:
        if key in entries:
            duplicates.append(key)
        entries[key] = entry

    for element in root:
        name = element.get("name")
        if not name or element.get("translatable") == "false":
            continue
        if element.tag == "string":
            add(name, Entry(text=_inner_xml(element)))
        elif element.tag == "plurals":
            groups.add(name)
            for item in element.findall("item"):
                quantity = item.get("quantity") or "other"
                add(f"{name}_{quantity}", Entry(text=_inner_xml(item)))
        elif element.tag == "string-array":
            groups.add(name)
            for index, item in enumerate(element.findall("item")):
                add(f"{name}[{index}]", Entry(text=_inner_xml(item)))
    return Catalog(path, "android", entries, sorted(set(duplicates)), group_prefixes=groups)


# ---------------------------------------------------------------- placeholders


@dataclass
class Tokens:
    named: set = field(default_factory=set)
    ordered: Tuple[str, ...] = ()
    markup: Counter = field(default_factory=Counter)
    errors: List[str] = field(default_factory=list)
    missing_other: List[str] = field(default_factory=list)


def _skip_quoted(text: str, i: int) -> int:
    """ICU apostrophe quoting: '{...}' is literal text. Returns index after the quote."""
    end = text.find("'", i + 1)
    return len(text) if end < 0 else end + 1


def parse_icu(text: str, tokens: Tokens) -> None:
    """Collect ICU MessageFormat argument names; flag plural/select without `other`."""

    def message(i: int, depth: int) -> int:
        while i < len(text):
            ch = text[i]
            if ch == "'" and i + 1 < len(text) and text[i + 1] in "{}#|":
                i = _skip_quoted(text, i)
                continue
            if ch == "'" and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            if ch == "{":
                i = argument(i + 1, depth)
                continue
            if ch == "}":
                if depth == 0:
                    raise ValueError("unbalanced '}'")
                return i
            i += 1
        if depth:
            raise ValueError("unclosed '{'")
        return i

    def argument(i: int, depth: int) -> int:
        end = i
        while end < len(text) and text[end] not in ",}{":
            end += 1
        if end >= len(text) or text[end] == "{":
            raise ValueError("unclosed '{'")
        name = text[i:end].strip()
        tokens.named.add("{" + name + "}")
        if text[end] == "}":
            return end + 1
        type_start = end + 1
        type_end = type_start
        while type_end < len(text) and text[type_end] not in ",}":
            type_end += 1
        if type_end >= len(text):
            raise ValueError("unclosed '{'")
        kind = text[type_start:type_end].strip()
        if kind in ("plural", "select", "selectordinal") and text[type_end] == ",":
            return options(type_end + 1, depth, name, kind)
        # number, date, time and custom styles: skip to the matching brace
        level, j = 1, type_end
        while j < len(text):
            if text[j] == "{":
                level += 1
            elif text[j] == "}":
                level -= 1
                if level == 0:
                    return j + 1
            j += 1
        raise ValueError("unclosed '{'")

    def options(i: int, depth: int, name: str, kind: str) -> int:
        selectors = []
        while i < len(text):
            while i < len(text) and text[i].isspace():
                i += 1
            if i < len(text) and text[i] == "}":
                if "other" not in selectors:
                    tokens.missing_other.append(f"{name} ({kind})")
                return i + 1
            start = i
            while i < len(text) and not text[i].isspace() and text[i] not in "{}":
                i += 1
            selector = text[start:i]
            if selector.startswith("offset:"):
                continue
            while i < len(text) and text[i].isspace():
                i += 1
            if i >= len(text) or text[i] != "{" or not selector:
                raise ValueError(f"malformed {kind} options")
            selectors.append(selector)
            i = message(i + 1, depth + 1)
            if i >= len(text) or text[i] != "}":
                raise ValueError("unclosed '{'")
            i += 1
        raise ValueError("unclosed '{'")

    message(0, 0)


def extract(text: str, syntax: str) -> Tokens:
    tokens = Tokens()
    rest = text
    for match in RE_TAG.finditer(text):
        closing, name, self_closing = match.groups()
        tokens.markup["<" + closing + name + ("/" if self_closing else "") + ">"] += 1
    if syntax in ("auto", "i18next"):
        for match in RE_DOUBLE_BRACE.finditer(rest):
            name = match.group(1).split(",")[0].strip()
            tokens.named.add("{{" + name + "}}")
        for match in RE_NESTING.finditer(rest):
            tokens.named.add("$t(" + match.group(1).split(",")[0].strip() + ")")
        rest = RE_DOUBLE_BRACE.sub(" ", rest)
    if syntax in ("auto", "ruby"):
        for match in RE_RUBY.finditer(rest):
            tokens.named.add("%{" + match.group(1) + "}")
        rest = RE_RUBY.sub(" ", rest)
    if syntax in ("auto", "printf"):
        work = rest.replace("%%", "  ")
        for match in RE_PY_NAMED.finditer(work):
            tokens.named.add("%(" + match.group(1) + ")")
        work = RE_PY_NAMED.sub(" ", work)
        pattern = RE_PRINTF_FULL if syntax == "printf" else RE_PRINTF_NARROW
        ordered = []
        for match in pattern.finditer(work):
            position, conversion = match.group(1), match.group(2)
            if position:
                tokens.named.add(f"%{position}${conversion}")
            else:
                ordered.append("%" + conversion)
        tokens.ordered = tuple(ordered)
        rest = pattern.sub(" ", work)
    if syntax in ("auto", "icu") and ("{" in rest or "}" in rest):
        icu_text = RE_TAG.sub(" ", rest)
        try:
            parse_icu(icu_text, tokens)
        except ValueError as exc:
            tokens.errors.append(str(exc))
    return tokens


def describe_difference(source: Tokens, target: Tokens) -> List[Tuple[str, str]]:
    problems: List[Tuple[str, str]] = []
    missing = sorted(source.named - target.named)
    extra = sorted(target.named - source.named)
    if source.ordered != target.ordered:
        if Counter(source.ordered) != Counter(target.ordered):
            missing += [f"{t} x{n}" for t, n in sorted((Counter(source.ordered) - Counter(target.ordered)).items())]
            extra += [f"{t} x{n}" for t, n in sorted((Counter(target.ordered) - Counter(source.ordered)).items())]
        else:
            problems.append(("placeholders", "unnumbered conversions in a different order; use numbered ones (%1$s)"))
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if extra:
            parts.append("extra " + ", ".join(extra))
        problems.append(("placeholders", "; ".join(parts)))
    if source.markup != target.markup:
        lost = sorted((source.markup - target.markup).elements())
        added = sorted((target.markup - source.markup).elements())
        parts = []
        if lost:
            parts.append("missing " + " ".join(lost))
        if added:
            parts.append("extra " + " ".join(added))
        problems.append(("markup", "; ".join(parts)))
    return problems


# ---------------------------------------------------------------- comparison


def plural_base(key: str) -> Optional[Tuple[str, str]]:
    for category in PLURAL_CATEGORIES:
        suffix = "_" + category
        if key.endswith(suffix) and len(key) > len(suffix):
            return key[: -len(suffix)], category
    return None


def plural_groups(entries: Dict[str, Entry]) -> Dict[str, set]:
    """Bases that have an `_other` key, mapped to the categories present."""
    found: Dict[str, set] = {}
    for key in entries:
        split = plural_base(key)
        if split:
            found.setdefault(split[0], set()).add(split[1])
    return {base: cats for base, cats in found.items() if "other" in cats}


def text_parent(key: str, entries: Dict[str, Entry]) -> Optional[str]:
    """The nearest enclosing key of `key` that is a plain value in `entries`, if any."""
    for index in range(len(key) - 1, 0, -1):
        if key[index] in ".[" and key[:index] in entries:
            return key[:index]
    return None


def is_ignored(key: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(key, pattern) for pattern in patterns)


def display_key(key: str) -> str:
    shown = key.replace("\u0004", " | ").replace("\n", "\\n")
    return shown if len(shown) <= 80 else shown[:77] + "..."


def has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def compare(source: Catalog, target: Catalog, syntax: str, ignore: Sequence[str],
            changed: Optional[set] = None) -> List[Finding]:
    findings: List[Finding] = []
    add = findings.append
    for key in target.duplicates:
        add(Finding("WARN", "duplicate-key", display_key(key), "the last value wins; earlier ones are silently dropped"))
    src_plurals = plural_groups(source.entries)
    tgt_prefixes = target.group_prefixes
    reported_parents: set = set()

    for key in sorted(source.entries):
        if is_ignored(key, ignore):
            continue
        src = source.entries[key]
        shown = display_key(key)
        split = plural_base(key)
        in_plural = split is not None and split[0] in src_plurals
        tgt = target.entries.get(key)
        if tgt is None:
            parent = text_parent(key, target.entries)
            if parent is not None:
                if parent not in reported_parents:
                    reported_parents.add(parent)
                    add(Finding("WARN", "type", display_key(parent), "a nested group in the source, text in the target"))
            elif key in tgt_prefixes or any(k.startswith(key + ".") or k.startswith(key + "[") for k in target.entries):
                add(Finding("WARN", "type", shown, "text in the source, a nested group in the target"))
            elif in_plural and split[1] != "other":
                add(Finding("INFO", "plural-form", shown,
                            f"'{split[1]}' form absent; correct only if the target language does not use it"))
            else:
                add(Finding("WARN", "missing", shown))
            continue
        if src.kind == "other" or tgt.kind == "other":
            if src.kind != tgt.kind:
                add(Finding("WARN", "type", shown, "value types differ between source and target"))
            continue
        if source.fmt == "po":
            findings.extend(compare_po_entry(key, src, tgt, syntax))
            continue
        target_text = tgt.text or ""
        if not target_text.strip():
            if (src.text or "").strip():
                add(Finding("WARN", "empty", shown))
            continue
        for check, detail in describe_difference(extract(src.text or "", syntax), extract(target_text, syntax)):
            add(Finding("WARN", check, shown, detail))
        tokens = extract(target_text, syntax)
        for error in tokens.errors:
            add(Finding("WARN", "syntax", shown, error))
        for item in tokens.missing_other:
            add(Finding("WARN", "icu-other", shown, f"{item} has no 'other' branch"))
        if changed and key in changed:
            add(Finding("WARN", "source-changed", shown, "source text changed since the previous version; review this translation"))
        if target_text == src.text and has_letters(target_text):
            add(Finding("INFO", "identical", shown, "same as the source; untranslated, or a name that stays as is"))

    for key in sorted(target.entries):
        if key in source.entries or is_ignored(key, ignore):
            continue
        split = plural_base(key)
        if split and split[0] in src_plurals:
            other = source.entries.get(split[0] + "_other")
            tgt = target.entries[key]
            if other is not None and other.text is not None and tgt.text:
                for check, detail in describe_difference(extract(other.text, syntax), extract(tgt.text, syntax)):
                    add(Finding("WARN", check, display_key(key), detail + " (compared with the source 'other' form)"))
            continue
        if key in source.group_prefixes or text_parent(key, source.entries) is not None:
            continue  # reported as a type mismatch from the source side
        add(Finding("INFO", "extra", display_key(key), "not in the source; stale unless something still reads it"))
    if target.obsolete:
        add(Finding("INFO", "obsolete", "-", f"{target.obsolete} obsolete (#~) entries kept in the file"))
    return sorted(findings, key=lambda f: (LEVEL_ORDER[f.level], f.check, f.key, f.detail))


def compare_po_entry(key: str, src: Entry, tgt: Entry, syntax: str) -> List[Finding]:
    shown = display_key(key)
    out: List[Finding] = []
    forms = [form for form in tgt.forms]
    if not forms or all(not form.strip() for form in forms):
        return [Finding("WARN", "untranslated", shown)]
    if any(not form.strip() for form in forms):
        out.append(Finding("WARN", "empty", shown, "one or more plural forms are empty"))
    if tgt.fuzzy:
        out.append(Finding("WARN", "fuzzy", shown, "marked fuzzy: needs review before it is used"))
    source_forms = src.source_forms or [src.text or ""]
    src_tokens = Tokens()
    for text in source_forms:
        part = extract(text, syntax)
        src_tokens.named |= part.named
        src_tokens.markup |= part.markup
        if len(part.ordered) > len(src_tokens.ordered):
            src_tokens.ordered = part.ordered
    tgt_tokens = Tokens()
    for text in forms:
        part = extract(text, syntax)
        tgt_tokens.named |= part.named
        tgt_tokens.markup |= part.markup
        tgt_tokens.errors += part.errors
        if len(part.ordered) > len(tgt_tokens.ordered):
            tgt_tokens.ordered = part.ordered
    # Plural entries are compared as a whole: a singular form may legitimately
    # drop the number, so the forms together must lose no token and add none.
    for check, detail in describe_difference(src_tokens, tgt_tokens):
        out.append(Finding("WARN", check, shown, detail))
    for error in tgt_tokens.errors:
        out.append(Finding("WARN", "syntax", shown, error))
    if len(source_forms) == 1 and forms[0] == src.text and has_letters(forms[0]):
        out.append(Finding("INFO", "identical", shown, "same as the source; untranslated, or a name that stays as is"))
    return out


def changed_keys(previous: Catalog, current: Catalog) -> set:
    return {
        key for key, entry in current.entries.items()
        if key in previous.entries and entry.kind == "text" and previous.entries[key].text != entry.text
    }


# ---------------------------------------------------------------- output


def render_text(source: Catalog, results: List[Tuple[Catalog, List[Finding]]], hide_info: bool,
                notes: List[str]) -> str:
    lines = [f"i18n_sync {VERSION}: source {source.path} ({len(source.entries)} keys, {source.fmt})"]
    for note in notes:
        lines.append(f"note: {note}")
    for key in source.duplicates:
        lines.append(f"  WARN  duplicate-key (source)  {display_key(key)}")
    total = Counter()
    for catalog, findings in results:
        counts = Counter(f.level for f in findings)
        total.update(counts)
        lines.append(f"{catalog.path}: {len(catalog.entries)} keys | WARN {counts['WARN']} | INFO {counts['INFO']}")
        for finding in findings:
            if hide_info and finding.level == "INFO":
                continue
            detail = f": {finding.detail}" if finding.detail else ""
            lines.append(f"  {finding.level:<5} {finding.check:<15} {finding.key}{detail}")
    total["WARN"] += len(source.duplicates)
    lines.append(f"Summary: {len(results)} target(s), WARN {total['WARN']}, INFO {total['INFO']}")
    lines.append("Structure only: have a fluent reviewer read the strings in the running product.")
    return "\n".join(lines)


def render_json(source: Catalog, results: List[Tuple[Catalog, List[Finding]]], notes: List[str]) -> str:
    payload = {
        "tool": "i18n_sync",
        "version": VERSION,
        "source": {"file": source.path, "format": source.fmt, "keys": len(source.entries),
                   "duplicates": [display_key(k) for k in source.duplicates]},
        "notes": notes,
        "targets": [
            {"file": catalog.path, "format": catalog.fmt, "keys": len(catalog.entries),
             "findings": [f.as_dict() for f in findings]}
            for catalog, findings in results
        ],
    }
    warn = sum(1 for _, fs in results for f in fs if f.level == "WARN") + len(source.duplicates)
    info = sum(1 for _, fs in results for f in fs if f.level == "INFO")
    payload["summary"] = {"targets": len(results), "warn": warn, "info": info}
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="i18n_sync.py",
        description="Read-only check that translation catalogs (JSON, ARB, gettext PO, Android strings.xml) "
                    "match their source-language catalog: missing, stale and empty keys, placeholder and "
                    "markup drift, plural and ICU problems. Never edits files or prints translated text.",
        epilog="Example: i18n_sync.py locales/en.json locales/de.json locales/fr.json --strict",
    )
    parser.add_argument("source", help="source-language catalog (the reference)")
    parser.add_argument("targets", nargs="+", help="target-language catalogs to compare")
    parser.add_argument("--format", choices=FORMATS, default="auto",
                        help="file format; auto uses the extension (.json, .arb, .po/.pot, .xml)")
    parser.add_argument("--syntax", choices=SYNTAXES, default="auto",
                        help="placeholder syntax; auto recognizes ICU {x}, {{x}}, %%{x}, %%(x)s and simple printf")
    parser.add_argument("--previous-source", metavar="FILE",
                        help="an older copy of the source catalog; keys whose text changed are flagged for review")
    parser.add_argument("--ignore-key", action="append", default=[], metavar="GLOB",
                        help="skip keys matching this glob (repeatable), e.g. 'brand.*'")
    parser.add_argument("--hide-info", action="store_true", help="print only WARN findings")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any WARN finding remains")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    notes: List[str] = []
    try:
        source = load_catalog(Path(args.source), args.format)
        targets = [load_catalog(Path(path), args.format) for path in args.targets]
        changed: Optional[set] = None
        if args.previous_source:
            previous = load_catalog(Path(args.previous_source), args.format)
            if source.fmt == "po":
                notes.append("--previous-source ignored for PO: msgid is the key, so changed text is a new entry")
            else:
                changed = changed_keys(previous, source)
                notes.append(f"{len(changed)} key(s) changed since {args.previous_source}")
    except InputError as exc:
        print(f"i18n_sync: error: {exc}", file=sys.stderr)
        return 2
    for catalog in targets:
        if catalog.fmt != source.fmt and {catalog.fmt, source.fmt} != {"json", "arb"}:
            print(f"i18n_sync: error: {catalog.path} is {catalog.fmt}, source is {source.fmt}", file=sys.stderr)
            return 2
    results = [(catalog, compare(source, catalog, args.syntax, args.ignore_key, changed)) for catalog in targets]
    if args.json:
        print(render_json(source, results, notes))
    else:
        print(render_text(source, results, args.hide_info, notes))
    warn = len(source.duplicates) + sum(1 for _, fs in results for f in fs if f.level == "WARN")
    return 1 if args.strict and warn else 0


if __name__ == "__main__":
    sys.exit(main())
