#!/usr/bin/env python3
"""ProductCraft file-organization planner. Dry run only: it never moves, renames,
creates or deletes anything.

Reads a folder and prints a plan that sorts its files into folders by type, by
date, or both, or checks an explicit rename list (CSV with source,target
columns, for example names built from invoice data). Every name collision is
resolved with a " (2)", " (3)" suffix, on case-insensitive rules by default,
because the default file systems on macOS and Windows treat "A.pdf" and
"a.pdf" as the same file.

Left alone and reported: symbolic links (never followed), hidden entries,
system files, unfinished downloads, excluded globs, and folders that must stay
whole (git repositories, code projects, application and library bundles).

Output formats:
  text     human-readable plan (default)
  json     machine-readable plan; keep it as the undo log
  sh       POSIX shell script that creates folders and moves files, skipping
           any target that exists when it runs; never overwrites or deletes
  undo-sh  shell script that moves files back and removes only the folders the
           plan created, and only if they are empty

Dates come from the file name (2024-03-15, 20240315, 2024-03) when present,
otherwise from the modification time in UTC, so output does not depend on the
machine's time zone.

Exit codes: 0 plan has nothing that needs review, 1 plan has items that need
review (renamed for a collision, duplicate content, sanitized or unsafe names,
unreadable entries, bad CSV rows), 2 usage error.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import json
import os
import re
import shlex
import stat
import sys
from datetime import datetime, timezone
from pathlib import PurePosixPath

VERSION = "1.0.0"

CATEGORIES = {
    "Documents": "pdf doc docx odt rtf txt md markdown pages epub tex",
    "Spreadsheets": "xls xlsx xlsm ods csv tsv numbers",
    "Presentations": "ppt pptx odp key",
    "Images": "jpg jpeg png gif webp heic heif tif tiff bmp svg avif raw cr2 cr3 nef arw dng orf rw2 psd",
    "Audio": "mp3 wav flac aac m4a ogg opus aiff aif wma",
    "Video": "mp4 mov mkv avi webm m4v wmv mpg mpeg",
    "Archives": "zip tar gz tgz bz2 xz zst 7z rar",
    "Installers": "dmg pkg exe msi deb rpm appimage apk",
    "Code": "py js mjs cjs ts tsx jsx json yaml yml toml html htm css scss sh ps1 ipynb sql java go rs rb php c h cpp hpp swift kt",
    "Fonts": "ttf otf woff woff2",
    "Calendar-and-contacts": "ics vcf",
    "Ebooks": "mobi azw azw3",
}
EXT_TO_CATEGORY = {ext: cat for cat, exts in CATEGORIES.items() for ext in exts.split()}
DOUBLE_EXTS = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")
OTHER = "Other"

SYSTEM_FILES = {".ds_store", "thumbs.db", "desktop.ini", "icon\r", ".localized", "ehthumbs.db"}
PARTIAL_SUFFIXES = (".crdownload", ".part", ".partial", ".download", ".opdownload", ".tmp", ".temp")
PROJECT_MARKERS = (".git", ".hg", ".svn", "package.json", "pyproject.toml", "setup.py", "Cargo.toml",
                   "go.mod", "pom.xml", "build.gradle", "Gemfile", "composer.json")
BUNDLE_SUFFIXES = (".app", ".bundle", ".framework", ".photoslibrary", ".musiclibrary", ".fcpbundle",
                   ".logicx", ".band", ".xcodeproj", ".xcworkspace", ".lrdata", ".pages", ".numbers",
                   ".key", ".rtfd", ".playground", ".sparsebundle", ".imovielibrary")

DATE_FULL = re.compile(r"(?<!\d)((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)")
DATE_MONTH = re.compile(r"(?<!\d)((?:19|20)\d{2})[-_.](0[1-9]|1[0-2])(?![-_.]?\d)")
UNSAFE_CHARS = re.compile(r'[<>:"\\|?*\x00-\x1f]')
RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)


class UsageError(Exception):
    pass


def split_ext(name: str) -> tuple[str, str]:
    lower = name.lower()
    for double in DOUBLE_EXTS:
        if lower.endswith(double) and len(name) > len(double):
            return name[: -len(double)], name[-len(double):]
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem:
        return name, ""
    return stem, "." + ext


def category_for(name: str, overrides: dict[str, str]) -> str:
    _, ext = split_ext(name)
    ext = ext.lower().lstrip(".")
    if ext in overrides:
        return overrides[ext]
    if "." in ext:  # double extension such as tar.gz
        return overrides.get(ext.rsplit(".", 1)[-1], "Archives")
    return EXT_TO_CATEGORY.get(ext, OTHER)


def date_from_name(name: str):
    for pattern in (DATE_FULL, DATE_MONTH):
        for match in pattern.finditer(name):
            year, month = int(match.group(1)), int(match.group(2))
            day = int(match.group(3)) if pattern is DATE_FULL else 1
            try:
                return datetime(year, month, day)
            except ValueError:
                continue
    return None


def sanitize_component(part: str) -> str:
    cleaned = UNSAFE_CHARS.sub("-", part).rstrip(" .")
    if RESERVED.match(cleaned):
        cleaned = "_" + cleaned
    return cleaned


def unsafe_relative(text: str) -> bool:
    if not text or text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", text):
        return True
    return any(part in ("..", "") for part in text.replace("\\", "/").split("/"))


def is_kept_folder(path: str, name: str):
    if name.lower().endswith(BUNDLE_SUFFIXES):
        return "application, library or document bundle"
    for marker in PROJECT_MARKERS:
        if os.path.lexists(os.path.join(path, marker)):
            return f"project folder ({marker} present)"
    return None


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Planner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.root = os.path.abspath(args.root)
        self.dest = os.path.abspath(args.dest or args.root)
        self.fold = (lambda s: s) if args.case_sensitive else (lambda s: s.casefold())
        self.overrides = parse_overrides(args.ext or [])
        self.moves: list[dict] = []
        self.unchanged: list[str] = []
        self.skipped: list[dict] = []
        self.kept: list[dict] = []
        self.left: list[str] = []
        self.errors: list[dict] = []
        self.duplicates: list[dict] = []
        self.taken: set[str] = set()
        self.listing_cache: dict[str, set[str]] = {}

    # ---- discovery -------------------------------------------------------
    def rel(self, path: str) -> str:
        return PurePosixPath(os.path.relpath(path, self.root).replace(os.sep, "/")).as_posix()

    def excluded(self, rel_path: str, name: str) -> bool:
        return any(fnmatch.fnmatch(rel_path, g) or fnmatch.fnmatch(name, g) for g in self.args.exclude or [])

    def inside_dest(self, path: str) -> bool:
        """True for folders inside a destination that itself lies inside the root."""
        if self.dest == self.root or os.path.commonpath([self.dest, self.root]) != self.root:
            return False
        return os.path.commonpath([path, self.dest]) == self.dest

    def scan(self) -> list[tuple[str, os.stat_result]]:
        found: list[tuple[str, os.stat_result]] = []
        stack = [self.root]
        while stack:
            folder = stack.pop()
            try:
                entries = sorted(os.scandir(folder), key=lambda e: e.name)
            except OSError as exc:
                self.errors.append({"path": self.rel(folder) + "/", "reason": f"cannot read folder: {exc.strerror}"})
                continue
            subfolders = []
            for entry in entries:
                rel_path = self.rel(entry.path)
                name = entry.name
                if name.startswith(".") and not self.args.include_hidden and name.lower() not in SYSTEM_FILES:
                    self.skipped.append({"path": rel_path, "reason": "hidden"})
                    continue
                if self.excluded(rel_path, name):
                    self.skipped.append({"path": rel_path, "reason": "excluded by --exclude"})
                    continue
                try:
                    if entry.is_symlink():
                        self.skipped.append({"path": rel_path, "reason": "symbolic link (not followed)"})
                        continue
                    info = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    self.errors.append({"path": rel_path, "reason": f"cannot read: {exc.strerror}"})
                    continue
                if stat.S_ISDIR(info.st_mode):
                    if self.inside_dest(entry.path):
                        continue
                    reason = is_kept_folder(entry.path, name)
                    if reason:
                        self.kept.append({"path": rel_path + "/", "reason": reason})
                    elif self.args.recursive:
                        subfolders.append(entry.path)
                    else:
                        self.left.append(rel_path + "/")
                    continue
                if not stat.S_ISREG(info.st_mode):
                    self.skipped.append({"path": rel_path, "reason": "not a regular file"})
                    continue
                if name.lower() in SYSTEM_FILES:
                    self.skipped.append({"path": rel_path, "reason": "system file"})
                    continue
                if name.lower().endswith(PARTIAL_SUFFIXES):
                    self.skipped.append({"path": rel_path, "reason": "unfinished download or temporary file"})
                    continue
                found.append((entry.path, info))
            stack.extend(reversed(subfolders))
        found.sort(key=lambda item: self.rel(item[0]))
        return found

    # ---- collision handling ---------------------------------------------
    def existing_names(self, folder: str) -> set[str]:
        if folder not in self.listing_cache:
            try:
                self.listing_cache[folder] = {self.fold(n) for n in os.listdir(folder)}
            except OSError:
                self.listing_cache[folder] = set()
        return self.listing_cache[folder]

    def occupied(self, target_abs: str, source_abs: str) -> str | None:
        key = self.fold(target_abs)
        if key in self.taken:
            return "planned for another file"
        folder, name = os.path.split(target_abs)
        if self.fold(name) in self.existing_names(folder):
            if self.fold(target_abs) == self.fold(source_abs):
                return None
            return "a file with this name already exists there"
        return None

    def resolve(self, source_abs: str, target_rel: str):
        """Return (final_rel, note) with a free name, or (None, None) when unchanged."""
        target_abs = os.path.join(self.dest, *target_rel.split("/"))
        if os.path.normcase(os.path.abspath(target_abs)) == os.path.normcase(source_abs) or (
            self.fold(target_abs) == self.fold(source_abs) and os.path.exists(target_abs)
            and os.path.samefile(target_abs, source_abs)
        ):
            return None, None
        clash = self.occupied(target_abs, source_abs)
        note = None
        if clash:
            parent, name = target_rel.rpartition("/")[0], target_rel.rpartition("/")[2]
            stem, ext = split_ext(name)
            counter = 2
            while True:
                candidate = f"{stem} ({counter}){ext}"
                candidate_rel = f"{parent}/{candidate}" if parent else candidate
                candidate_abs = os.path.join(self.dest, *candidate_rel.split("/"))
                if not self.occupied(candidate_abs, source_abs):
                    break
                counter += 1
            note = f"renamed to avoid a collision with {target_rel} ({clash})"
            target_rel, target_abs = candidate_rel, candidate_abs
        self.taken.add(self.fold(target_abs))
        return target_rel, note

    # ---- planning --------------------------------------------------------
    def target_for(self, path: str, info: os.stat_result, name: str):
        when, source = None, None
        if self.args.date_source in ("auto", "name"):
            when = date_from_name(name)
            source = "name" if when else None
        if when is None and self.args.date_source in ("auto", "mtime"):
            when = datetime.fromtimestamp(info.st_mtime, tz=timezone.utc)
            source = "mtime"
        parts: list[str] = []
        category = category_for(name, self.overrides)
        if self.args.by in ("type", "type-date"):
            parts.append(category)
        if self.args.by in ("date", "type-date"):
            if when is None:
                parts.append("Undated")
            else:
                parts.append(f"{when.year:04d}")
                if self.args.date_depth == "month" or self.args.by == "date":
                    parts.append(f"{when.year:04d}-{when.month:02d}")
        parts.append(name)
        date_text = when.strftime("%Y-%m-%d") if when else None
        return "/".join(parts), category, date_text, source

    def plan_by_rule(self) -> None:
        for path, info in self.scan():
            name = os.path.basename(path)
            target_rel, category, date_text, source = self.target_for(path, info, name)
            final_rel, note = self.resolve(path, target_rel)
            if final_rel is None:
                self.unchanged.append(self.rel(path))
                continue
            move = {"from": self.rel(path), "to": final_rel, "category": category,
                    "date": date_text, "date_from": source, "review": [note] if note else []}
            self.moves.append(move)

    def plan_from_csv(self, csv_path: str) -> None:
        try:
            handle = open(csv_path, newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise UsageError(f"cannot read {csv_path}: {exc.strerror}")
        with handle:
            reader = csv.DictReader(handle)
            fields = {(f or "").strip().lower(): f for f in reader.fieldnames or []}
            if "source" not in fields or "target" not in fields:
                raise UsageError("the CSV needs a header row with 'source' and 'target' columns")
            seen_sources: set[str] = set()
            rows = []
            for number, row in enumerate(reader, start=2):
                rows.append((number, (row.get(fields["source"]) or "").strip(), (row.get(fields["target"]) or "").strip()))
        rows.sort(key=lambda r: (r[1], r[0]))
        for number, source_text, target_text in rows:
            if unsafe_relative(source_text):
                self.errors.append({"row": number, "reason": f"unsafe or empty source path: {source_text!r}"})
                continue
            if unsafe_relative(target_text):
                self.errors.append({"row": number, "reason": f"unsafe or empty target path: {target_text!r}"})
                continue
            source_abs = os.path.join(self.root, *source_text.replace("\\", "/").split("/"))
            if os.path.islink(source_abs) or not os.path.isfile(source_abs):
                self.errors.append({"row": number, "reason": f"source is not a regular file: {source_text}"})
                continue
            key = self.fold(os.path.abspath(source_abs))
            if key in seen_sources:
                self.errors.append({"row": number, "reason": f"source listed twice: {source_text}"})
                continue
            seen_sources.add(key)
            notes = []
            parts = [sanitize_component(p) for p in target_text.replace("\\", "/").split("/")]
            if any(not p for p in parts):
                self.errors.append({"row": number, "reason": f"target has an empty part after cleaning: {target_text!r}"})
                continue
            target_rel = "/".join(parts)
            if target_rel != target_text.replace("\\", "/"):
                notes.append(f"target cleaned for portable names: {target_text!r}")
            if split_ext(os.path.basename(source_text))[1].lower() != split_ext(parts[-1])[1].lower():
                notes.append("target extension differs from the source")
            final_rel, note = self.resolve(os.path.abspath(source_abs), target_rel)
            if final_rel is None:
                self.unchanged.append(self.rel(source_abs))
                continue
            if note:
                notes.append(note)
            self.moves.append({"from": self.rel(source_abs), "to": final_rel, "category": None,
                               "date": None, "date_from": None, "review": notes})

    def find_duplicates(self) -> None:
        paths = [os.path.join(self.root, *m["from"].split("/")) for m in self.moves]
        paths += [os.path.join(self.root, *u.split("/")) for u in self.unchanged]
        by_size: dict[int, list[str]] = {}
        for path in sorted(paths, key=self.rel):
            try:
                by_size.setdefault(os.path.getsize(path), []).append(path)
            except OSError:
                continue
        for size, group in sorted(by_size.items()):
            if len(group) < 2:
                continue
            first_by_hash: dict[str, str] = {}
            for path in group:
                try:
                    digest = sha256(path)
                except OSError as exc:
                    self.errors.append({"path": self.rel(path), "reason": f"cannot read for hashing: {exc.strerror}"})
                    continue
                if digest in first_by_hash:
                    self.duplicates.append({"path": self.rel(path), "same_content_as": first_by_hash[digest],
                                            "bytes": size})
                else:
                    first_by_hash[digest] = self.rel(path)

    def run(self) -> dict:
        if self.args.from_csv:
            self.plan_from_csv(self.args.from_csv)
        else:
            self.plan_by_rule()
        if self.args.hash_duplicates:
            self.find_duplicates()
        review = sum(1 for m in self.moves if m["review"]) + len(self.duplicates) + len(self.errors)
        rule = ({"from_csv": os.path.basename(self.args.from_csv)} if self.args.from_csv else
                {"by": self.args.by, "date_depth": self.args.date_depth, "date_source": self.args.date_source,
                 "recursive": self.args.recursive})
        rule["case_sensitive"] = self.args.case_sensitive
        return {
            "tool": "organize_plan", "version": VERSION, "dry_run": True,
            "root": self.root, "dest": self.dest, "rule": rule,
            "moves": self.moves, "unchanged": self.unchanged, "skipped": self.skipped,
            "kept_folders": self.kept, "folders_left": self.left, "duplicates": self.duplicates,
            "errors": self.errors,
            "summary": {"move": len(self.moves), "unchanged": len(self.unchanged), "skipped": len(self.skipped),
                        "kept_folders": len(self.kept), "folders_left": len(self.left),
                        "duplicates": len(self.duplicates), "errors": len(self.errors), "review": review},
        }


def parse_overrides(items: list[str]) -> dict[str, str]:
    result = {}
    for item in items:
        ext, sep, category = item.partition("=")
        ext = ext.strip().lower().lstrip(".")
        category = category.strip()
        if (not sep or not ext or not category or "/" in category or sanitize_component(category) != category
                or category in (".", "..")):
            raise UsageError(f"--ext expects EXT=Category with a plain folder name, got {item!r}")
        result[ext] = category
    return result


# ---- rendering -------------------------------------------------------------
def render_text(plan: dict) -> str:
    s = plan["summary"]
    rule = plan["rule"]
    if "from_csv" in rule:
        rule_text = f"explicit targets from {rule['from_csv']}"
    else:
        depth = "year and month" if rule["date_depth"] == "month" or rule["by"] == "date" else "year"
        sources = {"auto": "file name, else modification time (UTC)", "name": "file name only",
                   "mtime": "modification time (UTC)"}[rule["date_source"]]
        rule_text = f"by {rule['by']}" + ("" if rule["by"] == "type" else f" ({depth}; dates from {sources})")
        rule_text += ", recursive" if rule["recursive"] else ", top level only"
    lines = ["Organization plan (dry run: nothing has been moved, renamed or deleted)",
             f"root: {plan['root']}", f"dest: {plan['dest']}", f"rule: {rule_text}", ""]
    for move in plan["moves"]:
        lines.append(f"MOVE   {move['from']}  ->  {move['to']}")
        lines.extend(f"       ! {note}" for note in move["review"])
    lines.extend(f"SAME   {path}" for path in plan["unchanged"])
    lines.extend(f"KEEP   {k['path']}  ({k['reason']}; left whole)" for k in plan["kept_folders"])
    lines.extend(f"LEAVE  {path}  (subfolder; --recursive includes its files)" for path in plan["folders_left"])
    lines.extend(f"SKIP   {k['path']}  ({k['reason']})" for k in plan["skipped"])
    lines.extend(f"DUP    {d['path']}  ! same content as {d['same_content_as']} ({d['bytes']} bytes); nothing is deleted"
                 for d in plan["duplicates"])
    for err in plan["errors"]:
        where = err.get("path") or f"CSV row {err.get('row')}"
        lines.append(f"ERROR  {where}  ! {err['reason']}")
    lines.append("")
    lines.append(f"Summary: move {s['move']}, already in place {s['unchanged']}, skipped {s['skipped']}, "
                 f"folders kept whole {s['kept_folders']}, subfolders left {s['folders_left']}, "
                 f"duplicates {s['duplicates']}, errors {s['errors']}. Need review: {s['review']}.")
    return "\n".join(lines) + "\n"


def _abs(base: str, rel: str) -> str:
    return os.path.join(base, *rel.split("/"))


def created_folders(plan: dict) -> list[str]:
    created: set[str] = set()
    dest = plan["dest"]
    for move in plan["moves"]:
        folder = os.path.dirname(_abs(dest, move["to"]))
        while folder != dest and os.path.commonpath([folder, dest]) == dest and not os.path.isdir(folder):
            created.add(folder)
            folder = os.path.dirname(folder)
    if plan["moves"] and not os.path.isdir(dest):
        created.add(dest)
    return sorted(created)


def render_sh(plan: dict) -> str:
    q = shlex.quote
    lines = ["#!/bin/sh", f"# Plan from organize_plan.py {VERSION}. Review it before running.",
             "# Creates folders and moves files. Skips any target that already exists; never overwrites or deletes.",
             "set -u", "moved=0; skipped=0",
             "move() {  # move SOURCE TARGET",
             '  if [ -e "$2" ] || [ -L "$2" ]; then echo "skip, target exists: $2" >&2; skipped=$((skipped+1))',
             '  elif [ ! -f "$1" ] || [ -L "$1" ]; then echo "skip, source missing: $1" >&2; skipped=$((skipped+1))',
             '  else mv -- "$1" "$2" && moved=$((moved+1)); fi',
             "}"]
    lines.extend(f"mkdir -p -- {q(folder)}" for folder in created_folders(plan))
    for move in plan["moves"]:
        lines.append(f"move {q(_abs(plan['root'], move['from']))} {q(_abs(plan['dest'], move['to']))}")
    lines.append('echo "moved $moved, skipped $skipped"')
    return "\n".join(lines) + "\n"


def render_undo_sh(plan: dict) -> str:
    q = shlex.quote
    lines = ["#!/bin/sh", f"# Undo for a plan from organize_plan.py {VERSION}. Moves files back to where they were.",
             "# Skips a file whose original path is taken again; removes only empty folders the plan created.",
             "set -u", "restored=0; skipped=0",
             "back() {  # back CURRENT ORIGINAL",
             '  if [ -e "$2" ] || [ -L "$2" ]; then echo "skip, original path taken: $2" >&2; skipped=$((skipped+1))',
             '  elif [ ! -f "$1" ] || [ -L "$1" ]; then echo "skip, not found: $1" >&2; skipped=$((skipped+1))',
             '  else mkdir -p -- "$(dirname -- "$2")" && mv -- "$1" "$2" && restored=$((restored+1)); fi',
             "}"]
    for move in reversed(plan["moves"]):
        lines.append(f"back {q(_abs(plan['dest'], move['to']))} {q(_abs(plan['root'], move['from']))}")
    for folder in sorted(created_folders(plan), key=lambda p: (-p.count(os.sep), p)):
        lines.append(f"rmdir -- {q(folder)} 2>/dev/null || true")
    lines.append('echo "restored $restored, skipped $skipped"')
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organize_plan.py",
        description="Dry-run planner for organizing files by type and date, or for checking an explicit "
                    "rename list. Never touches files; prints a plan with collisions resolved.",
        epilog="Exit codes: 0 nothing needs review, 1 some items need review, 2 usage error.")
    parser.add_argument("root", help="folder to organize")
    parser.add_argument("--dest", help="destination root for the new folders (default: the root itself)")
    parser.add_argument("--by", choices=("type", "date", "type-date"), default="type-date",
                        help="folder scheme: Category/, YYYY/YYYY-MM/, or Category/YYYY/ (default)")
    parser.add_argument("--date-depth", choices=("year", "month"), default="year",
                        help="for type-date: add a YYYY-MM level under the year (default: year only)")
    parser.add_argument("--date-source", choices=("auto", "name", "mtime"), default="auto",
                        help="auto: date in the file name, else modification time in UTC (default)")
    parser.add_argument("--recursive", action="store_true", help="include files in subfolders")
    parser.add_argument("--include-hidden", action="store_true", help="include names that start with a dot")
    parser.add_argument("--ext", action="append", metavar="EXT=CATEGORY",
                        help="map an extension to a folder name, for example --ext heic=Photos (repeatable)")
    parser.add_argument("--exclude", action="append", metavar="GLOB",
                        help="skip paths or names matching the glob (repeatable)")
    parser.add_argument("--hash-duplicates", action="store_true",
                        help="flag files with identical content (SHA-256); reads every same-size file")
    parser.add_argument("--from-csv", metavar="FILE",
                        help="CSV with source,target columns (relative to root and dest) instead of the type/date rule")
    parser.add_argument("--case-sensitive", action="store_true",
                        help="treat names that differ only in case as different (default: treat them as the same)")
    parser.add_argument("--format", choices=("text", "json", "sh", "undo-sh"), default="text")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not os.path.isdir(args.root):
            raise UsageError(f"not a folder: {args.root}")
        if args.dest and os.path.exists(args.dest) and not os.path.isdir(args.dest):
            raise UsageError(f"--dest exists and is not a folder: {args.dest}")
        plan = Planner(args).run()
    except UsageError as exc:
        print(f"organize_plan.py: error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        sys.stdout.write(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    elif args.format == "sh":
        sys.stdout.write(render_sh(plan))
    elif args.format == "undo-sh":
        sys.stdout.write(render_undo_sh(plan))
    else:
        sys.stdout.write(render_text(plan))
    return 1 if plan["summary"]["review"] else 0


if __name__ == "__main__":
    sys.exit(main())
