#!/usr/bin/env python3
"""bib_check.py - offline, read-only checker for BibTeX and biblatex files.

Reports problems that break or weaken a bibliography: unbalanced braces,
unterminated quotes, missing commas, missing or invalid citation keys,
duplicate keys, duplicate DOIs and likely duplicate entries, fields the
entry type requires, malformed DOIs, years, dates, arXiv identifiers, ISBNs
and PMIDs, author lists separated by commas, undefined @string macros and
missing crossref parents. With --cited-in it also compares the keys cited
in .tex, .aux or Markdown files with the entries that exist.

It uses only the Python standard library, never touches the network and
never writes files. It cannot tell whether a DOI exists or whether the
metadata matches the real publication: verify identifiers separately
(see the research-writing module's citations reference).

Exit codes: 0 no ERROR findings (WARN allowed unless --strict),
1 ERROR findings (or WARN findings with --strict), 2 usage error or
unreadable input.
"""
from __future__ import annotations

import argparse
import bisect
import datetime
import json
import os
import re
import sys
from dataclasses import dataclass, field

VERSION = "1.0.0"

LEVEL_RANK = {"INFO": 1, "WARN": 2, "ERROR": 3}

RULES = {
    "UNBALANCED_BRACES": ("ERROR", "An entry is not closed, closes too early, or a closing brace stands outside any entry"),
    "UNTERMINATED_QUOTE": ("ERROR", 'A "quoted" field value has no closing quote'),
    "SYNTAX": ("ERROR", "Text inside an entry that is not a 'name = value' field"),
    "MISSING_COMMA": ("ERROR", "Two fields are not separated by a comma"),
    "MISSING_KEY": ("ERROR", "An entry has no citation key"),
    "INVALID_KEY": ("ERROR", "A citation key contains whitespace or a character BibTeX cannot handle"),
    "DUPLICATE_KEY": ("ERROR", "The same citation key is defined more than once"),
    "DUPLICATE_KEY_CASE": ("WARN", "Two keys differ only in letter case; BibTeX treats them as one key"),
    "MISSING_FIELD": ("ERROR", "A field the entry type requires is missing ('type' and 'note' are WARN)"),
    "UNKNOWN_TYPE": ("WARN", "The entry type is not a standard type of the dialect in use"),
    "MISSING_CROSSREF": ("WARN", "A crossref or xdata parent key is not defined in the files checked"),
    "DUPLICATE_FIELD": ("WARN", "A field appears twice in one entry; only the first is used"),
    "EMPTY_FIELD": ("WARN", "A field has an empty value"),
    "UNDEFINED_STRING": ("WARN", "A field uses an @string macro that is not defined before use"),
    "MALFORMED_DOI": ("ERROR", "The doi field is not a single DOI of the form 10.<prefix>/<suffix>"),
    "DOI_BACKSLASH": ("WARN", "The DOI contains a backslash (for example an escaped underscore)"),
    "DOI_TRAILING_PUNCT": ("WARN", "The DOI ends with punctuation that is probably not part of it"),
    "DOI_AS_URL": ("INFO", "The doi field holds a URL or a 'doi:' prefix instead of the bare DOI"),
    "DOI_IN_URL": ("INFO", "The url field points to doi.org but there is no doi field"),
    "DUPLICATE_DOI": ("WARN", "Two entries carry the same DOI"),
    "POSSIBLE_DUPLICATE": ("WARN", "Two entries have the same normalized title and year"),
    "MALFORMED_YEAR": ("ERROR", "The year is not a four-digit year"),
    "YEAR_SUFFIX": ("WARN", "The year carries a letter suffix such as 2020a; let the style add it"),
    "YEAR_NOT_NUMERIC": ("INFO", "The year is a word such as 'in press' or a range"),
    "YEAR_IN_FUTURE": ("WARN", "The year is later than --max-year"),
    "MALFORMED_DATE": ("ERROR", "The biblatex date field is not an ISO 8601 date or date range"),
    "YEAR_DATE_MISMATCH": ("WARN", "The year and date fields disagree"),
    "AUTHOR_SEPARATOR": ("WARN", "Names in author or editor look separated by commas or semicolons instead of ' and '"),
    "ET_AL": ("WARN", "The name list contains 'et al.'; write 'and others' instead"),
    "UNPROTECTED_CAPS": ("INFO", "The title has words with inner capitals (DNA, mRNA) that sentence-casing styles lowercase unless braced"),
    "PAGES_SINGLE_HYPHEN": ("INFO", "A page range uses a single hyphen; '--' gives an en dash"),
    "MALFORMED_ARXIV": ("WARN", "The arXiv identifier in eprint has neither the new nor the old format"),
    "MALFORMED_ISBN": ("WARN", "An ISBN has the wrong length or check digit"),
    "MALFORMED_PMID": ("WARN", "The pmid field is not a positive integer"),
    "MISSING_ENTRY": ("ERROR", "A key cited in a document has no entry"),
    "CITE_KEY_CASE": ("WARN", "A cited key matches an entry only when letter case is ignored"),
    "UNCITED_ENTRY": ("INFO", "An entry is never cited in the documents given with --cited-in"),
    "ENCODING": ("WARN", "The file is not valid UTF-8 and was read as Latin-1"),
}

SOFT_REQUIRED = {"type", "note"}

BIBTEX_REQUIRED = {
    "article": [("author",), ("title",), ("journal",), ("year",)],
    "book": [("author", "editor"), ("title",), ("publisher",), ("year",)],
    "booklet": [("title",)],
    "conference": [("author",), ("title",), ("booktitle",), ("year",)],
    "inbook": [("author", "editor"), ("title",), ("chapter", "pages"), ("publisher",), ("year",)],
    "incollection": [("author",), ("title",), ("booktitle",), ("publisher",), ("year",)],
    "inproceedings": [("author",), ("title",), ("booktitle",), ("year",)],
    "manual": [("title",)],
    "mastersthesis": [("author",), ("title",), ("school",), ("year",)],
    "misc": [],
    "phdthesis": [("author",), ("title",), ("school",), ("year",)],
    "proceedings": [("title",), ("year",)],
    "techreport": [("author",), ("title",), ("institution",), ("year",)],
    "unpublished": [("author",), ("title",), ("note",)],
}

_AE = ("author", "editor")
_YD = ("year", "date")
_INBOOK = [("author",), ("title",), ("booktitle",), _YD]
_COLL = [("editor",), ("title",), _YD]
_MISC = [_AE, ("title",), _YD]
_THESIS_ALIAS = [("author",), ("title",), ("institution", "school"), _YD]
BIBLATEX_REQUIRED = {
    "article": [("author",), ("title",), ("journaltitle", "journal"), _YD],
    "book": [("author",), ("title",), _YD],
    "mvbook": [("author",), ("title",), _YD],
    "inbook": _INBOOK, "bookinbook": _INBOOK, "suppbook": _INBOOK,
    "booklet": [_AE, ("title",), _YD],
    "collection": _COLL, "mvcollection": _COLL, "reference": _COLL, "mvreference": _COLL,
    "incollection": _INBOOK, "suppcollection": _INBOOK, "inreference": _INBOOK,
    "dataset": _MISC, "manual": _MISC, "misc": _MISC, "software": _MISC,
    "online": [_AE, ("title",), _YD, ("doi", "eprint", "url")],
    "electronic": [_AE, ("title",), _YD, ("doi", "eprint", "url")],
    "www": [_AE, ("title",), _YD, ("doi", "eprint", "url")],
    "patent": [("author",), ("title",), ("number",), _YD],
    "periodical": [("editor",), ("title",), _YD],
    "suppperiodical": [("author",), ("title",), ("journaltitle", "journal"), _YD],
    "proceedings": [("title",), _YD], "mvproceedings": [("title",), _YD],
    "inproceedings": _INBOOK, "conference": _INBOOK,
    "report": [("author",), ("title",), ("type",), ("institution",), _YD],
    "techreport": [("author",), ("title",), ("institution",), _YD],
    "thesis": [("author",), ("title",), ("type",), ("institution", "school"), _YD],
    "mastersthesis": _THESIS_ALIAS, "phdthesis": _THESIS_ALIAS,
    "unpublished": [("author",), ("title",), _YD],
    "set": [], "xdata": [],
}
# Recognized by biblatex but rendered as @misc by the standard styles.
for _t in ("artwork", "audio", "bibnote", "commentary", "image", "jurisdiction", "legislation",
           "legal", "letter", "movie", "music", "performance", "review", "standard", "video"):
    BIBLATEX_REQUIRED[_t] = []

BIBLATEX_ONLY_TYPES = {
    "online", "report", "thesis", "dataset", "software", "collection", "mvbook", "mvcollection",
    "mvproceedings", "mvreference", "bookinbook", "suppbook", "suppcollection", "suppperiodical",
    "reference", "inreference", "periodical", "set", "xdata",
}
BIBLATEX_ONLY_FIELDS = {
    "journaltitle", "date", "eprinttype", "location", "maintitle", "eventtitle", "langid",
    "origdate", "xdata", "related", "entryset", "shorthand", "sortname",
}
CHILD_TYPES = {"inbook", "incollection", "inproceedings", "conference", "bookinbook", "suppbook",
               "suppcollection", "inreference"}
MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}

ENTRY_START = re.compile(r"@[ \t]*([A-Za-z][A-Za-z0-9_-]*)[ \t\r\n]*([{(])")
NEXT_ENTRY = re.compile(r"\n[ \t]*@[ \t]*[A-Za-z][A-Za-z0-9_-]*[ \t]*[{(]")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_:+./-]*")
NUMBER = re.compile(r"[0-9]+")
BAD_KEY_CHARS = re.compile(r"[\s,{}()\"#%~\\=]")
DOI_RE = re.compile(r"^10\.\d{4,9}(?:\.\d+)*/\S+$")
DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)
ISO_DATE = r"\d{4}(?:-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?)?"
DATE_RE = re.compile(r"^(?:%s)(?:/(?:%s|\.\.)?)?$|^\.\./%s$" % (ISO_DATE, ISO_DATE, ISO_DATE))
ARXIV_NEW = re.compile(r"^(?:arXiv:)?\d{4}\.\d{4,5}(?:v\d+)?$", re.I)
ARXIV_OLD = re.compile(r"^(?:arXiv:)?[a-z][a-z-]*(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?$")
WORDS_YEAR = {"in press", "inpress", "forthcoming", "submitted", "to appear", "n.d.", "nd", "accepted"}


@dataclass
class FieldVal:
    name: str
    value: str
    line: int
    undefined: list = field(default_factory=list)


@dataclass
class Entry:
    path: str
    file_index: int
    line: int
    etype: str
    key: str
    fields: dict
    closed: bool


@dataclass
class Finding:
    path: str
    file_index: int
    line: int
    level: str
    code: str
    key: str
    message: str

    def as_dict(self):
        return {"file": self.path, "line": self.line, "level": self.level, "code": self.code,
                "key": self.key, "message": self.message}


class Checker:
    def __init__(self, ignore=(), max_year=None, dialect="auto"):
        self.ignore = set(ignore)
        self.max_year = max_year
        self.dialect = dialect
        self.macros = {m: m for m in MONTHS}
        self.entries = []
        self.findings = []
        self.files = []

    # -- reporting -------------------------------------------------------
    def add(self, path, file_index, line, code, key, message, level=None):
        if code in self.ignore:
            return
        self.findings.append(Finding(path, file_index, line, level or RULES[code][0], code, key, message))

    # -- parsing ---------------------------------------------------------
    def parse_file(self, path, text):
        index = len(self.files)
        self.files.append(path)
        _FileParser(self, path, index, text).parse()

    # -- checks ----------------------------------------------------------
    def resolve_dialect(self):
        if self.dialect != "auto":
            return self.dialect
        for e in self.entries:
            if e.etype in BIBLATEX_ONLY_TYPES or BIBLATEX_ONLY_FIELDS.intersection(e.fields):
                return "biblatex"
        return "bibtex"

    def check(self, cited=None):
        dialect = self.resolve_dialect()
        self.dialect_used = dialect
        table = BIBLATEX_REQUIRED if dialect == "biblatex" else BIBTEX_REQUIRED
        by_key = {}
        for e in self.entries:
            if e.key:
                by_key.setdefault(e.key, e)
        for e in self.entries:
            self._check_entry(e, table, dialect, by_key)
        self._check_duplicates()
        if cited is not None:
            self._check_citations(cited)

    def _check_entry(self, e, table, dialect, by_key):
        f = e.fields
        p, i, k = e.path, e.file_index, e.key
        for name, fv in f.items():
            for macro in fv.undefined:
                self.add(p, i, fv.line, "UNDEFINED_STRING", k,
                         "field '%s' uses undefined macro '%s' (defined later, or expected from the .bst?)" % (name, macro))
            if not fv.value.strip() and not fv.undefined:
                self.add(p, i, fv.line, "EMPTY_FIELD", k, "field '%s' is empty" % name)
        if not e.closed:
            return
        if e.etype not in table:
            self.add(p, i, e.line, "UNKNOWN_TYPE", k,
                     "@%s is not a standard %s type; most styles render it as @misc" % (e.etype, dialect))
        else:
            present = set(n for n, fv in f.items() if fv.value.strip() or fv.undefined)
            present |= self._inherited(e, by_key)
            for group in table[e.etype]:
                if not present.intersection(group):
                    level = "WARN" if set(group) <= SOFT_REQUIRED else None
                    self.add(p, i, e.line, "MISSING_FIELD", k,
                             "@%s lacks %s" % (e.etype, " or ".join(group)), level=level)
        if "doi" in f:
            self._check_doi(e, f["doi"])
        elif "url" in f and re.search(r"doi\.org/10\.", f["url"].value, re.I):
            self.add(p, i, f["url"].line, "DOI_IN_URL", k, "url is a doi.org link; add a doi field with the bare DOI")
        if "year" in f:
            self._check_year(e, f["year"])
        if "date" in f:
            self._check_date(e, f["date"])
        for name in ("author", "editor"):
            if name in f:
                self._check_names(e, f[name])
        if "title" in f:
            caps = inner_caps_words(f["title"].value)
            if caps:
                self.add(p, i, f["title"].line, "UNPROTECTED_CAPS", k,
                         "title words %s lose their capitals in sentence-case styles; wrap them in braces" % ", ".join(caps[:3]))
        if "pages" in f and re.fullmatch(r"\s*[0-9A-Za-z]+\s*-\s*[0-9A-Za-z]+\s*", f["pages"].value):
            self.add(p, i, f["pages"].line, "PAGES_SINGLE_HYPHEN", k, "pages '%s': use '--' for a range" % f["pages"].value.strip())
        prefix = (f.get("archiveprefix") or f.get("eprinttype"))
        if prefix and prefix.value.strip().lower() == "arxiv" and "eprint" in f:
            ident = f["eprint"].value.strip()
            if not (ARXIV_NEW.match(ident) or ARXIV_OLD.match(ident)):
                self.add(p, i, f["eprint"].line, "MALFORMED_ARXIV", k, "eprint '%s' is not an arXiv identifier" % ident)
        if "isbn" in f:
            for isbn in re.split(r"[,;]\s*|\s{2,}", f["isbn"].value.strip()):
                if isbn and not isbn_ok(isbn):
                    self.add(p, i, f["isbn"].line, "MALFORMED_ISBN", k, "ISBN '%s' has a wrong length or check digit" % isbn)
        if "pmid" in f and not re.fullmatch(r"\s*[1-9][0-9]*\s*", f["pmid"].value):
            self.add(p, i, f["pmid"].line, "MALFORMED_PMID", k, "pmid '%s' is not a positive integer" % f["pmid"].value.strip())

    def _inherited(self, e, by_key):
        names = set()
        parents = []
        if "crossref" in e.fields:
            parents.append(("crossref", e.fields["crossref"]))
        if "xdata" in e.fields:
            parents.append(("xdata", e.fields["xdata"]))
        for kind, fv in parents:
            keys = [x.strip() for x in fv.value.split(",")] if kind == "xdata" else [fv.value.strip()]
            for pk in keys:
                if not pk:
                    continue
                parent = by_key.get(pk)
                if parent is None:
                    self.add(e.path, e.file_index, fv.line, "MISSING_CROSSREF", e.key,
                             "%s parent '%s' is not defined in the files checked" % (kind, pk))
                    continue
                names |= set(parent.fields)
                if "title" in parent.fields and e.etype in CHILD_TYPES:
                    names.add("booktitle")
        return names

    def _check_doi(self, e, fv):
        raw = fv.value.strip()
        p, i, k = e.path, e.file_index, e.key
        if DOI_PREFIX.match(raw):
            self.add(p, i, fv.line, "DOI_AS_URL", k, "store the bare DOI, not '%s'" % raw)
        doi = normalize_doi(raw)
        if not DOI_RE.match(doi):
            hint = " (one DOI per entry)" if re.search(r"\s", doi) else ""
            self.add(p, i, fv.line, "MALFORMED_DOI", k, "'%s' is not a DOI%s" % (raw, hint))
            return
        if "\\" in doi:
            self.add(p, i, fv.line, "DOI_BACKSLASH", k, "DOI '%s' contains a backslash; store it unescaped" % doi)
        if doi[-1] in ".,;:":
            self.add(p, i, fv.line, "DOI_TRAILING_PUNCT", k, "DOI '%s' ends with '%s'" % (doi, doi[-1]))

    def _check_year(self, e, fv):
        v = strip_braces(fv.value).strip()
        p, i, k = e.path, e.file_index, e.key
        if re.fullmatch(r"\d{4}", v):
            if self.max_year is not None and int(v) > self.max_year:
                self.add(p, i, fv.line, "YEAR_IN_FUTURE", k, "year %s is later than %d" % (v, self.max_year))
        elif re.fullmatch(r"\d{4}[a-z]", v):
            self.add(p, i, fv.line, "YEAR_SUFFIX", k, "year '%s' has a letter suffix" % v)
        elif v.lower() in WORDS_YEAR or re.fullmatch(r"\d{4}\s*(?:-|--|/)\s*\d{2,4}", v):
            self.add(p, i, fv.line, "YEAR_NOT_NUMERIC", k, "year '%s' is not a single year" % v)
        else:
            self.add(p, i, fv.line, "MALFORMED_YEAR", k, "year '%s' is not a four-digit year" % v)

    def _check_date(self, e, fv):
        v = strip_braces(fv.value).strip()
        p, i, k = e.path, e.file_index, e.key
        if not DATE_RE.match(v):
            self.add(p, i, fv.line, "MALFORMED_DATE", k, "date '%s' is not YYYY, YYYY-MM, YYYY-MM-DD or a range with '/'" % v)
            return
        y = e.fields.get("year")
        first = re.search(r"\d{4}", v)
        if y and first and re.fullmatch(r"\d{4}", strip_braces(y.value).strip()) and strip_braces(y.value).strip() != first.group(0):
            self.add(p, i, fv.line, "YEAR_DATE_MISMATCH", k, "year %s but date %s" % (strip_braces(y.value).strip(), v))

    def _check_names(self, e, fv):
        top = top_level(fv.value)
        p, i, k = e.path, e.file_index, e.key
        if re.search(r"\bet\.?\s*al\b", top, re.I):
            self.add(p, i, fv.line, "ET_AL", k, "%s contains 'et al.'" % fv.name)
        names = re.split(r"\s+and\s+", top, flags=re.I)

        def suffix_form(n):
            parts = [x.strip().rstrip(".").lower() for x in n.split(",")]
            return len(parts) == 3 and parts[1] in ("jr", "sr", "ii", "iii", "iv")

        if any(n.count(",") > 2 or ";" in n or (n.count(",") == 2 and not suffix_form(n)) for n in names):
            self.add(p, i, fv.line, "AUTHOR_SEPARATOR", k,
                     "%s looks like a comma- or semicolon-separated list; separate names with ' and '" % fv.name)

    def _check_duplicates(self):
        seen = {}
        folded = {}
        dois = {}
        titles = {}
        for e in self.entries:
            if not e.key:
                continue
            if e.key in seen:
                first = seen[e.key]
                self.add(e.path, e.file_index, e.line, "DUPLICATE_KEY", e.key,
                         "key also defined at %s:%d" % (first.path, first.line))
                continue
            seen[e.key] = e
            low = e.key.lower()
            if low in folded and folded[low].key != e.key:
                first = folded[low]
                self.add(e.path, e.file_index, e.line, "DUPLICATE_KEY_CASE", e.key,
                         "differs only in case from '%s' at %s:%d" % (first.key, first.path, first.line))
            folded.setdefault(low, e)
            if "doi" in e.fields:
                doi = normalize_doi(e.fields["doi"].value.strip()).lower()
                if DOI_RE.match(doi):
                    if doi in dois:
                        first = dois[doi]
                        self.add(e.path, e.file_index, e.fields["doi"].line, "DUPLICATE_DOI", e.key,
                                 "DOI %s is also used by '%s' at %s:%d" % (doi, first.key, first.path, first.line))
                        continue
                    dois[doi] = e
            t = normalize_title(e.fields["title"].value) if "title" in e.fields else ""
            y = strip_braces(e.fields["year"].value).strip() if "year" in e.fields else ""
            if not y and "date" in e.fields:
                m = re.search(r"\d{4}", e.fields["date"].value)
                y = m.group(0) if m else ""
            if len(t) >= 12:
                tk = (t, y)
                if tk in titles:
                    first = titles[tk]
                    self.add(e.path, e.file_index, e.line, "POSSIBLE_DUPLICATE", e.key,
                             "same title and year as '%s' at %s:%d" % (first.key, first.path, first.line))
                else:
                    titles[tk] = e

    def _check_citations(self, cited):
        keys, all_cited = cited
        defined = {e.key for e in self.entries if e.key}
        folded = {}
        for e in self.entries:
            if e.key:
                folded.setdefault(e.key.lower(), e.key)
        idx = {path: n for n, path in enumerate(self.files)}
        base = len(self.files)
        for key in sorted(keys, key=lambda x: (keys[x][0], keys[x][1], x)):
            path, line = keys[key]
            fi = idx.get(path, base)
            if key in defined:
                continue
            if key.lower() in folded:
                self.add(path, fi, line, "CITE_KEY_CASE", key, "cited as '%s' but defined as '%s'" % (key, folded[key.lower()]))
            else:
                self.add(path, fi, line, "MISSING_ENTRY", key, "cited but not defined in any .bib file checked")
        if not all_cited:
            cited_folded = {x.lower() for x in keys}
            for e in self.entries:
                if e.key and e.key not in keys and e.key.lower() not in cited_folded:
                    self.add(e.path, e.file_index, e.line, "UNCITED_ENTRY", e.key, "never cited in the documents given")


class _FileParser:
    def __init__(self, checker, path, index, text):
        self.c = checker
        self.path = path
        self.index = index
        self.text = text
        self.n = len(text)
        self.newlines = [m.start() for m in re.finditer("\n", text)]

    def line(self, pos):
        return bisect.bisect_left(self.newlines, pos) + 1

    def err(self, pos, code, key, message, level=None):
        self.c.add(self.path, self.index, self.line(pos), code, key, message, level)

    def parse(self):
        t, pos = self.text, 0
        while pos < self.n:
            at = t.find("@", pos)
            self._scan_outside(pos, self.n if at == -1 else at)
            if at == -1:
                break
            m = ENTRY_START.match(t, at)
            if not m:
                pos = at + 1
                continue
            etype = m.group(1).lower()
            end, closed, next_line = self._find_end(m.end(), m.group(2))
            if not closed:
                where = "before the next entry at line %d" % next_line if next_line else "before the end of the file"
                self.err(at, "UNBALANCED_BRACES", "", "@%s entry is not closed %s (missing '}'?)" % (etype, where))
            body_start, body = m.end(), t[m.end():end]
            if etype == "string":
                self._parse_fields(body, body_start, "", None, string_mode=True)
            elif etype not in ("comment", "preamble"):
                self._parse_entry(etype, body, body_start, at, closed)
            pos = end + 1 if closed else end

    def _scan_outside(self, a, b):
        depth = 0
        before = self.text[self.text.rfind("\n", 0, a) + 1:a].strip()
        line_start = before == ""
        skipping = before.startswith("%")
        for j in range(a, b):
            ch = self.text[j]
            if ch == "\n":
                line_start, skipping = True, False
                continue
            if skipping:
                continue
            if line_start and ch in " \t":
                continue
            if line_start and ch == "%":
                skipping = True
                continue
            line_start = False
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    self.err(j, "UNBALANCED_BRACES", "",
                             "closing brace outside any entry (did an earlier entry close too early?)")
                    return
                depth -= 1

    def _find_end(self, start, opener):
        t, depth, j = self.text, 0, start
        while j < self.n:
            ch = t[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    if opener == "{":
                        return j, True, None
                    self.err(j, "UNBALANCED_BRACES", "", "unmatched '}' inside a parenthesized entry")
                else:
                    depth -= 1
            elif ch == ")" and opener == "(" and depth == 0:
                return j, True, None
            elif ch == "\n":
                m = NEXT_ENTRY.match(t, j)
                if m:
                    return j, False, self.line(m.end() - 1)
            j += 1
        return self.n, False, None

    def _parse_entry(self, etype, body, body_start, at, closed):
        p = len(body) - len(body.lstrip())
        comma = body.find(",", p)
        chunk = body[p:comma] if comma != -1 else body[p:]
        if "=" in chunk:
            key, fields_from = "", p
        else:
            key, fields_from = chunk.strip(), (comma + 1 if comma != -1 else len(body))
        if not key:
            self.err(at, "MISSING_KEY", "", "@%s entry has no citation key" % etype)
        elif BAD_KEY_CHARS.search(key):
            self.err(at, "INVALID_KEY", key, "key '%s' contains whitespace or one of , { } ( ) \" # %% ~ \\ =" % key)
        entry = Entry(self.path, self.index, self.line(at), etype, key, {}, closed)
        self._parse_fields(body, body_start, key, entry, start=fields_from, report_syntax=closed)
        self.c.entries.append(entry)

    def _parse_fields(self, s, base, key, entry, start=0, string_mode=False, report_syntax=True):
        j, n = start, len(s)
        while True:
            while j < n and (s[j].isspace() or s[j] == ","):
                j += 1
            if j >= n:
                return
            m = NAME.match(s, j)
            if not m:
                if report_syntax:
                    hint = " (BibTeX does not treat % as a comment inside an entry)" if s[j] == "%" else ""
                    self.err(base + j, "SYNTAX", key, "unexpected text %r%s" % (s[j:j + 20].split("\n")[0], hint))
                return
            name, name_pos = m.group(0).lower(), j
            j = m.end()
            while j < n and s[j].isspace():
                j += 1
            if j >= n or s[j] != "=":
                if report_syntax:
                    self.err(base + name_pos, "SYNTAX", key, "expected '=' after '%s'" % m.group(0))
                return
            j += 1
            value, undefined, j, ok = self._read_value(s, j, base, key)
            if not ok:
                return
            if string_mode:
                self.c.macros[name] = value
            elif entry is not None:
                if name in entry.fields:
                    self.err(base + name_pos, "DUPLICATE_FIELD", key, "field '%s' appears more than once" % name)
                else:
                    entry.fields[name] = FieldVal(name, value, self.line(base + name_pos), undefined)
            k = j
            while k < n and s[k].isspace():
                k += 1
            if k < n and s[k] not in ",":
                if report_syntax:
                    self.err(base + k, "MISSING_COMMA", key, "missing comma after field '%s'" % name)
            j = k

    def _read_value(self, s, j, base, key):
        n, parts, undefined = len(s), [], []
        while True:
            while j < n and s[j].isspace():
                j += 1
            if j >= n:
                self.err(base + j - 1, "SYNTAX", key, "field value missing")
                return "", undefined, j, False
            ch = s[j]
            if ch == "{":
                depth, k = 0, j
                while k < n:
                    if s[k] == "{":
                        depth += 1
                    elif s[k] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    k += 1
                parts.append(s[j + 1:k])
                j = k + 1
            elif ch == '"':
                depth, k = 0, j + 1
                while k < n and not (s[k] == '"' and depth == 0):
                    depth += {"{": 1, "}": -1}.get(s[k], 0)
                    k += 1
                if k >= n:
                    self.err(base + j, "UNTERMINATED_QUOTE", key, "quoted value has no closing quote")
                    return "", undefined, n, False
                parts.append(s[j + 1:k])
                j = k + 1
            elif ch.isdigit():
                m = NUMBER.match(s, j)
                parts.append(m.group(0))
                j = m.end()
            else:
                m = NAME.match(s, j)
                if not m:
                    self.err(base + j, "SYNTAX", key, "unexpected character %r in a field value" % ch)
                    return "", undefined, j, False
                macro = m.group(0).lower()
                if macro in self.c.macros:
                    parts.append(self.c.macros[macro])
                else:
                    undefined.append(m.group(0))
                j = m.end()
            k = j
            while k < n and s[k].isspace():
                k += 1
            if k < n and s[k] == "#":
                j = k + 1
                continue
            return "".join(parts), undefined, j, True


# -- helpers ------------------------------------------------------------------

def normalize_doi(raw):
    return DOI_PREFIX.sub("", raw.strip())


def strip_braces(s):
    return s.replace("{", "").replace("}", "")


def top_level(s):
    """Text of s with every braced group removed (used for name lists)."""
    out, depth = [], 0
    for ch in s:
        if ch == "{":
            depth += 1
            out.append(" " if depth == 1 else "")
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def inner_caps_words(title):
    text = re.sub(r"\\[A-Za-z]+", " ", top_level(title))
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", text)
    found = []
    for w in words:
        if any(c.isupper() for c in w[1:]) and w not in found:
            found.append(w)
    return found


def normalize_title(s):
    s = re.sub(r"\\[A-Za-z]+", " ", s)
    return re.sub(r"[^a-z0-9]", "", strip_braces(s).lower())


def isbn_ok(raw):
    s = re.sub(r"[\s-]", "", raw).upper()
    if s.startswith("ISBN"):
        s = s[4:].lstrip(":")
    if re.fullmatch(r"\d{9}[\dX]", s):
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s))
        return total % 11 == 0
    if re.fullmatch(r"\d{13}", s):
        total = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(s))
        return total % 10 == 0
    return False


# -- citations in documents ---------------------------------------------------

TEX_CMD = re.compile(r"\\([A-Za-z@]*(?i:cite)[A-Za-z@]*|nocite|citation)\*?")
ABX_CITE = re.compile(r"\\abx@aux@cite\{[^}]*\}\{([^}]*)\}")
MD_KEY = re.compile(r"(?<![\w@.\\])-?@(\{[^}]+\}|[A-Za-z0-9_][\w:.#$%&+?<>~/-]*)")
MD_SKIP_PREFIXES = ("fig:", "tbl:", "sec:", "eq:", "lst:")


def collect_citations(paths, read):
    keys, all_cited = {}, False
    for path in paths:
        text = read(path)
        lower = path.lower()
        if lower.endswith((".md", ".markdown", ".qmd", ".rmd")):
            found, star = _md_citations(text)
        else:
            found, star = _tex_citations(text)
        all_cited = all_cited or star
        for key, line in found:
            keys.setdefault(key, (path, line))
    return keys, all_cited


def _tex_citations(text):
    found, star = [], False
    lines = text.split("\n")
    clean = "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in lines)
    nl = [m.start() for m in re.finditer("\n", clean)]
    for m in ABX_CITE.finditer(clean):
        found.append((m.group(1).strip(), bisect.bisect_left(nl, m.start()) + 1))
    for m in TEX_CMD.finditer(clean):
        name = m.group(1)
        if name.startswith("abx@") or name.endswith("style") or name.startswith(("def", "set")):
            continue
        j, n, groups = m.end(), len(clean), 0
        multi = name.endswith("cites")
        while j < n:
            while j < n and clean[j] in " \t\r\n":
                j += 1
            if j < n and clean[j] in "[(":
                close = "]" if clean[j] == "[" else ")"
                k = clean.find(close, j)
                if k == -1:
                    break
                j = k + 1
                continue
            if j < n and clean[j] == "{":
                k = clean.find("}", j)
                if k == -1:
                    break
                line = bisect.bisect_left(nl, j) + 1
                for key in clean[j + 1:k].split(","):
                    key = key.strip()
                    if key == "*":
                        star = True
                    elif key:
                        found.append((key, line))
                groups += 1
                j = k + 1
                if multi:
                    continue
            break
    return found, star


def _md_citations(text):
    found = []
    out_lines, fence = [], None
    for ln in text.split("\n"):
        stripped = ln.lstrip()
        if fence:
            if stripped.startswith(fence):
                fence = None
            out_lines.append("")
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            out_lines.append("")
            continue
        out_lines.append(re.sub(r"`[^`]*`", "", ln))
    for number, ln in enumerate(out_lines, 1):
        for m in MD_KEY.finditer(ln):
            key = m.group(1)
            if key.startswith("{"):
                key = key[1:-1].strip()
            else:
                key = key.rstrip(".:,;?#$%&+<>~/-")
            if key and not key.lower().startswith(MD_SKIP_PREFIXES):
                found.append((key, number))
    return found, False


# -- command line -------------------------------------------------------------

def read_text(path, checker=None, index=None):
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        if checker is not None:
            checker.add(path, index if index is not None else len(checker.files), 1, "ENCODING", "",
                        "file is not valid UTF-8; read as Latin-1")
        return data.decode("latin-1")


def expand_bib_paths(args):
    out = []
    for a in args:
        if os.path.isdir(a):
            for root, dirs, files in os.walk(a):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                out.extend(os.path.join(root, f) for f in sorted(files) if f.lower().endswith(".bib"))
        else:
            out.append(a)
    return out


def build_parser():
    ap = argparse.ArgumentParser(
        prog="bib_check.py",
        description="Offline, read-only checker for BibTeX and biblatex files. It never uses the network; "
                    "verify that DOIs exist and metadata matches with a separate lookup.",
        epilog="Exit codes: 0 no ERROR findings, 1 ERROR findings (or WARN with --strict), 2 usage error or unreadable input.")
    ap.add_argument("paths", nargs="*", help=".bib files or folders (searched recursively for *.bib)")
    ap.add_argument("--cited-in", action="append", default=[], metavar="FILE",
                    help="a .tex, .aux or Markdown file whose citations are compared with the entries (repeatable)")
    ap.add_argument("--dialect", choices=("auto", "bibtex", "biblatex"), default="auto",
                    help="required-field rules to apply (auto: biblatex when biblatex-only types or fields appear)")
    ap.add_argument("--max-year", type=int, default=None,
                    help="flag years later than this (default: the current year plus 1)")
    ap.add_argument("--ignore", action="append", default=[], metavar="CODE", help="rule code to skip (repeatable or comma-separated)")
    ap.add_argument("--min-level", choices=("info", "warn", "error"), default="info", help="lowest level to print")
    ap.add_argument("--strict", action="store_true", help="exit 1 when WARN findings remain")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--list-ids", action="store_true",
                    help="print key, DOI, arXiv id and PMID of each entry as tab-separated values, for a separate verification step")
    ap.add_argument("--list-rules", action="store_true", help="print the rule codes and exit")
    ap.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.list_rules:
        for code in sorted(RULES):
            print("%-20s %-5s %s" % (code, RULES[code][0], RULES[code][1]))
        return 0
    if not args.paths:
        ap.print_usage(sys.stderr)
        print("bib_check.py: error: give at least one .bib file or folder", file=sys.stderr)
        return 2
    ignore = set()
    for item in args.ignore:
        ignore.update(x.strip().upper() for x in item.split(",") if x.strip())
    unknown = sorted(ignore - set(RULES))
    if unknown:
        print("bib_check.py: error: unknown rule code(s): %s" % ", ".join(unknown), file=sys.stderr)
        return 2
    max_year = args.max_year if args.max_year is not None else datetime.date.today().year + 1
    checker = Checker(ignore=ignore, max_year=max_year, dialect=args.dialect)
    bib_paths = expand_bib_paths(args.paths)
    if not bib_paths:
        print("bib_check.py: error: no .bib files found", file=sys.stderr)
        return 2
    try:
        for path in bib_paths:
            checker.parse_file(path, read_text(path, checker, len(checker.files)))
        cited = collect_citations(args.cited_in, read_text) if args.cited_in else None
    except OSError as exc:
        print("bib_check.py: error: cannot read %s: %s" % (exc.filename, exc.strerror), file=sys.stderr)
        return 2
    checker.check(cited)

    if args.list_ids:
        print("key\tdoi\tarxiv\tpmid")
        for e in checker.entries:
            f = e.fields
            doi = normalize_doi(f["doi"].value) if "doi" in f else ""
            prefix = (f.get("archiveprefix") or f.get("eprinttype"))
            arxiv = f["eprint"].value.strip() if "eprint" in f and prefix and prefix.value.strip().lower() == "arxiv" else ""
            pmid = f["pmid"].value.strip() if "pmid" in f else ""
            if e.key and (doi or arxiv or pmid):
                print("%s\t%s\t%s\t%s" % (e.key, doi, arxiv, pmid))
        return 0

    floor = LEVEL_RANK[args.min_level.upper()]
    findings = sorted(checker.findings, key=lambda x: (x.file_index, x.path, x.line, x.code, x.key))
    shown = [x for x in findings if LEVEL_RANK[x.level] >= floor]
    counts = {lvl: sum(1 for x in findings if x.level == lvl) for lvl in LEVEL_RANK}
    summary = {"files": len(bib_paths), "entries": len(checker.entries), "dialect": checker.dialect_used,
               "errors": counts["ERROR"], "warnings": counts["WARN"], "info": counts["INFO"]}
    if args.json:
        print(json.dumps({"tool": "bib_check", "version": VERSION, "summary": summary,
                          "findings": [x.as_dict() for x in shown]}, indent=2, sort_keys=True))
    else:
        for x in shown:
            key = " %s:" % x.key if x.key else ""
            print("%s:%d: %s %s%s %s" % (x.path, x.line, x.level, x.code, key, x.message))
        print("bib_check: %d file(s), %d entries (dialect: %s); %d error(s), %d warning(s), %d note(s)"
              % (summary["files"], summary["entries"], summary["dialect"], counts["ERROR"], counts["WARN"], counts["INFO"]))
    if counts["ERROR"] or (args.strict and counts["WARN"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
