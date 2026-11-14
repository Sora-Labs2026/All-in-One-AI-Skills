#!/usr/bin/env python3
"""Find overlap leads between a site's files and its reference material.

Read-only and offline. Compares a site folder (source or built output) with one or
more reference files or folders and reports:

  * exact file matches (same SHA-256), for images, video, fonts, documents and code;
  * reused file names with different content (a weaker lead: renamed or edited copies);
  * shared runs of words (default 8 words) in visible text, merged into passages;
  * distinctive numbers that appear in both (prices, percentages, long figures).

Results are leads for a human review, never a verdict of copying.

Exit codes: 0 no leads, 1 leads found, 2 usage or input error.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

TEXT_EXT = {".html", ".htm", ".md", ".mdx", ".txt", ".json", ".js", ".mjs", ".cjs", ".jsx", ".ts",
            ".tsx", ".vue", ".svelte", ".astro", ".css", ".svg", ".xml", ".yml", ".yaml", ".csv"}
MARKUP_EXT = {".html", ".htm", ".svg", ".xml", ".vue", ".svelte", ".astro", ".jsx", ".tsx", ".mdx"}
SKIP_DIRS = {".git", "node_modules", ".next", ".cache", "__pycache__", ".venv", "venv"}
MAX_TEXT_BYTES = 2_000_000

SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
ATTR_TEXT = re.compile(r"\b(?:alt|title|aria-label|placeholder|content)\s*=\s*\"([^\"]*)\"", re.I)
TAG = re.compile(r"<[^>]+>")
WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.U)
NUMBER = re.compile(r"(?<![\w.])(?:[$€£]\s?)?\d{1,3}(?:[, ]\d{3})+(?:\.\d+)?%?|(?<![\w.])(?:[$€£]\s?)?\d+(?:\.\d+)?%?(?![\w])")


def iter_files(root: Path, excludes: list[str]):
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and d not in excludes)
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if any(part in excludes for part in p.parts):
                continue
            if p.is_file() and not p.is_symlink():
                yield p


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def visible_text(path: Path) -> str:
    if path.suffix.lower() not in TEXT_EXT or path.stat().st_size > MAX_TEXT_BYTES:
        return ""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in MARKUP_EXT:
        attrs = " ".join(ATTR_TEXT.findall(raw))
        body = TAG.sub(" ", COMMENT.sub(" ", SCRIPT_STYLE.sub(" ", raw)))
        raw = html.unescape(body + " " + attrs)
    return raw


def words(text: str) -> list[str]:
    return [w.lower().replace("’", "'") for w in WORD.findall(text)]


def ngrams(tokens: list[str], n: int) -> dict[tuple[str, ...], int]:
    out: dict[tuple[str, ...], int] = {}
    for i in range(len(tokens) - n + 1):
        out.setdefault(tuple(tokens[i:i + n]), i)
    return out


def merge_passages(tokens: list[str], starts: list[int], n: int) -> list[str]:
    passages, run_start, run_end = [], None, None
    for s in sorted(starts):
        if run_start is None:
            run_start, run_end = s, s + n
        elif s <= run_end:
            run_end = max(run_end, s + n)
        else:
            passages.append(" ".join(tokens[run_start:run_end]))
            run_start, run_end = s, s + n
    if run_start is not None:
        passages.append(" ".join(tokens[run_start:run_end]))
    return passages


def distinctive_numbers(text: str) -> set[str]:
    found = set()
    for m in NUMBER.finditer(text):
        tok = m.group(0).replace(" ", ",").replace(" ", "")
        digits = re.sub(r"\D", "", tok)
        if tok.endswith("%") or tok[0] in "$€£" or "." in tok or len(digits) >= 4:
            if not re.fullmatch(r"(19|20)\d\d", tok):          # bare years are too common to matter
                found.add(tok)
    return found


def collect(roots: list[Path], excludes: list[str]):
    files = []
    for root in roots:
        for p in iter_files(root, excludes):
            files.append(p)
    return files


def analyze(site: Path, refs: list[Path], n: int, excludes: list[str]) -> dict:
    site_files = collect([site], excludes)
    ref_files = collect(refs, excludes)

    ref_hash: dict[str, list[str]] = {}
    ref_names: dict[str, list[str]] = {}
    for p in ref_files:
        ref_hash.setdefault(sha256(p), []).append(str(p))
        ref_names.setdefault(p.name.lower(), []).append(str(p))

    exact, same_name = [], []
    for p in site_files:
        h = sha256(p)
        if h in ref_hash:
            exact.append({"site": str(p), "references": ref_hash[h], "sha256": h})
        elif p.name.lower() in ref_names and p.stat().st_size > 0:
            same_name.append({"site": str(p), "references": ref_names[p.name.lower()]})

    ref_grams: dict[tuple[str, ...], str] = {}
    ref_numbers: dict[str, set[str]] = {}
    for p in ref_files:
        text = visible_text(p)
        if not text:
            continue
        for g in ngrams(words(text), n):
            ref_grams.setdefault(g, str(p))
        for num in distinctive_numbers(text):
            ref_numbers.setdefault(num, set()).add(str(p))

    text_hits, number_hits = [], []
    for p in site_files:
        text = visible_text(p)
        if not text:
            continue
        toks = words(text)
        shared, sources = [], set()
        for g, start in ngrams(toks, n).items():
            if g in ref_grams:
                shared.append(start)
                sources.add(ref_grams[g])
        if shared:
            text_hits.append({"site": str(p), "references": sorted(sources),
                              "passages": merge_passages(toks, shared, n)})
        nums = sorted(num for num in distinctive_numbers(text) if num in ref_numbers)
        if nums:
            number_hits.append({"site": str(p), "numbers": nums,
                                "references": sorted(set().union(*(ref_numbers[x] for x in nums)))})

    return {"site": str(site), "references": [str(r) for r in refs], "ngram": n,
            "files_scanned": {"site": len(site_files), "references": len(ref_files)},
            "exact_files": exact, "same_name_different_content": same_name,
            "shared_text": text_hits, "shared_numbers": number_hits}


def leads(report: dict) -> int:
    return sum(len(report[k]) for k in ("exact_files", "same_name_different_content", "shared_text", "shared_numbers"))


def print_text(report: dict) -> None:
    fs = report["files_scanned"]
    print(f"Scanned {fs['site']} site files against {fs['references']} reference files (runs of {report['ngram']} words).")
    sections = [
        ("EXACT FILE MATCHES (strong lead)", "exact_files", lambda r: f"{r['site']}  ==  {', '.join(r['references'])}"),
        ("SAME NAME, DIFFERENT CONTENT (weak lead)", "same_name_different_content",
         lambda r: f"{r['site']}  ~  {', '.join(r['references'])}"),
        ("SHARED TEXT", "shared_text",
         lambda r: f"{r['site']}  <-  {', '.join(r['references'])}\n" + "\n".join(f'    "{x}"' for x in r["passages"][:10])),
        ("SHARED DISTINCTIVE NUMBERS", "shared_numbers", lambda r: f"{r['site']}: {', '.join(r['numbers'])}"),
    ]
    for title, key, fmt in sections:
        rows = report[key]
        print(f"\n{title}: {len(rows)}")
        for r in rows:
            print("  " + fmt(r))
    print(f"\n{leads(report)} lead(s). Leads need a human comparison; see reference-originality-audit.md.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Read-only overlap finder: exact files, reused names, shared word runs and numbers "
                    "between a site and its references. Exit 0 no leads, 1 leads, 2 usage error.")
    ap.add_argument("--site", required=True, help="site folder or file (source or built output)")
    ap.add_argument("--reference", action="append", required=True,
                    help="reference file or folder; repeat for several")
    ap.add_argument("--ngram", type=int, default=8, help="words per shared run (default 8, minimum 4)")
    ap.add_argument("--exclude", action="append", default=[], help="folder or file name to skip; repeatable")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 2
    if args.ngram < 4:
        print("error: --ngram must be at least 4", file=sys.stderr)
        return 2
    site = Path(args.site)
    refs = [Path(r) for r in args.reference]
    missing = [str(p) for p in [site, *refs] if not p.exists()]
    if missing:
        print(f"error: not found: {', '.join(missing)}", file=sys.stderr)
        return 2
    report = analyze(site, refs, args.ngram, args.exclude)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report)
    return 1 if leads(report) else 0


if __name__ == "__main__":
    sys.exit(main())
