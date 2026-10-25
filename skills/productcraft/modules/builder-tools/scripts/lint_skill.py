#!/usr/bin/env python3
"""Static, read-only checks for an Agent Skill folder.

Checks the SKILL.md frontmatter against the published Agent Skills limits
(name and description format and length), the size of the instruction body,
relative links and file references between the skill's Markdown files,
reference files nothing points to, and files that should not ship in a skill
(credentials, caches, nested SKILL.md files).

Standard library only. It never executes the skill's scripts and never writes.
Passing it means the package is well-formed; it says nothing about whether the
skill triggers on the right requests or improves results. Evaluate that with
test prompts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KNOWN_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
TRIGGER_HINTS = re.compile(r"\b(use (?:it |this )?(?:when|for|whenever|if)|when (?:the )?(?:user|you|a |an |asked|working)|triggers? (?:on|when)|whenever)\b", re.IGNORECASE)
FIRST_PERSON = re.compile(r"^\s*(?:I|I'm|I am|I can|I will|We|You can|You should)\b")
PATH_PREFIXES = ("references/", "scripts/", "assets/", "modules/", "examples/", "templates/", "agents/", "tests/", "./", "../")
PATH_SUFFIXES = (".md", ".py", ".json", ".sh", ".js", ".mjs", ".ts", ".txt", ".html", ".css", ".yaml", ".yml", ".toml", ".csv", ".xml")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache"}
JUNK = {
    ".env": "environment file (may hold credentials)",
    ".DS_Store": "OS metadata file",
    "id_rsa": "private key",
    "id_ed25519": "private key",
    "Thumbs.db": "OS metadata file",
}
JUNK_SUFFIXES = {".pem": "key or certificate", ".key": "private key", ".p12": "key store", ".pfx": "key store", ".pyc": "compiled Python cache"}
JUNK_DIRS = {"__pycache__": "Python cache directory", "node_modules": "installed dependencies", ".pytest_cache": "test cache"}


class Finding:
    def __init__(self, level: str, code: str, path: str, message: str, line: int | None = None):
        self.level, self.code, self.path, self.message, self.line = level, code, path, message, line

    def as_dict(self):
        d = {"level": self.level, "code": self.code, "path": self.path, "message": self.message}
        if self.line:
            d["line"] = self.line
        return d

    def __str__(self):
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.level.upper():7} {self.code} {loc}: {self.message}"


class FrontmatterError(Exception):
    def __init__(self, message, line):
        super().__init__(message)
        self.line = line


def _scalar(raw: str):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        inner = raw[1:-1]
        return inner.replace("''", "'") if raw[0] == "'" else inner.replace('\\"', '"')
    if raw.startswith("[") and raw.endswith("]"):
        return [_scalar(x) for x in raw[1:-1].split(",") if x.strip()]
    if " #" in raw:
        raw = raw.split(" #", 1)[0].rstrip()
    return raw


def parse_frontmatter(lines: list[str], first_line: int = 2) -> dict:
    """Parse the YAML subset used by skill frontmatter.

    Supports `key: value`, quoted values, `>`/`|` block scalars, one level of
    nested `key: value` mappings, `- item` lists and `[a, b]` flow lists.
    Anything else raises FrontmatterError so the author can simplify it.
    """
    data: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = first_line + i
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            raise FrontmatterError("unexpected indentation", lineno)
        m = re.match(r"^([A-Za-z0-9_-]+):(?:\s+(.*)|\s*)$", line)
        if not m:
            raise FrontmatterError(f"cannot parse line: {line.strip()[:60]!r}", lineno)
        key, rest = m.group(1), (m.group(2) or "").strip()
        if key in data:
            raise FrontmatterError(f"duplicate key '{key}'", lineno)
        i += 1
        block = []
        while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
            block.append(lines[i])
            i += 1
        while block and not block[-1].strip():
            block.pop()
        if rest in (">", "|", ">-", "|-", ">+", "|+"):
            texts = [b.strip() for b in block]
            data[key] = (" ".join(t for t in texts if t) if rest.startswith(">") else "\n".join(texts)).strip()
        elif rest:
            if block:
                # plain multi-line scalar continues on indented lines
                data[key] = " ".join([str(_scalar(rest))] + [b.strip() for b in block if b.strip()])
            else:
                data[key] = _scalar(rest)
        elif not block:
            data[key] = ""
        elif all(b.strip().startswith("- ") or not b.strip() for b in block):
            data[key] = [_scalar(b.strip()[2:]) for b in block if b.strip()]
        else:
            sub = {}
            for j, b in enumerate(block):
                if not b.strip() or b.lstrip().startswith("#"):
                    continue
                sm = re.match(r"^\s+([A-Za-z0-9_.-]+):\s*(.*)$", b)
                if not sm:
                    raise FrontmatterError(f"cannot parse nested line: {b.strip()[:60]!r}", lineno + 1 + j)
                sub[sm.group(1)] = _scalar(sm.group(2))
            data[key] = sub
    return data


def split_frontmatter(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, lines, 1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx], lines[idx + 1:], idx + 2
    return "unterminated", lines, 1


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        for d in sorted(dirnames):
            if d in JUNK_DIRS:
                yield "junkdir", rel_dir / d
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            yield "file", rel_dir / f


LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CODE_RE = re.compile(r"`([^`\n]+)`")


def referenced_paths(text: str):
    """Yield (line_number, path, kind) for relative links and path-like code spans."""
    in_fence = False
    for n, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in LINK_RE.finditer(line):
            target = m.group(1).split("#", 1)[0]
            if target and not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) and not target.startswith("/"):
                yield n, target, "link"
        for m in CODE_RE.finditer(line):
            token = m.group(1).strip()
            if any(ch in token for ch in " <>*{}$|\\") or "://" in token:
                continue
            if token.startswith(PATH_PREFIXES) and "/" in token and token.rstrip("/").split("/")[-1]:
                if token.endswith("/") or token.lower().endswith(PATH_SUFFIXES) or "." not in token.split("/")[-1]:
                    yield n, token.rstrip("/"), "code"


def lint(skill_dir: str, max_body_lines: int = 500, max_ref_lines: int = 300) -> list[Finding]:
    root = Path(skill_dir)
    out: list[Finding] = []
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        return [Finding("error", "SK001", "SKILL.md", "SKILL.md not found at the skill root")]
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm_lines, body_lines, body_start = split_frontmatter(text)
    meta: dict = {}
    if fm_lines is None:
        out.append(Finding("error", "SK002", "SKILL.md", "no YAML frontmatter: the file must start with a '---' line", 1))
    elif fm_lines == "unterminated":
        out.append(Finding("error", "SK002", "SKILL.md", "frontmatter is not closed with a '---' line", 1))
    else:
        try:
            meta = parse_frontmatter(fm_lines)
        except FrontmatterError as exc:
            out.append(Finding("error", "SK003", "SKILL.md", f"frontmatter: {exc}", exc.line))

    if fm_lines not in (None, "unterminated") and not any(f.code == "SK003" for f in out):
        name = meta.get("name")
        if not isinstance(name, str) or not name.strip():
            out.append(Finding("error", "SK010", "SKILL.md", "'name' is required"))
        else:
            if len(name) > 64 or not NAME_RE.match(name):
                out.append(Finding("error", "SK011", "SKILL.md", f"name '{name}' must be 1-64 characters of lowercase letters, digits and single hyphens, not starting or ending with a hyphen"))
            if name != root.resolve().name:
                out.append(Finding("warning", "SK012", "SKILL.md", f"name '{name}' differs from the folder name '{root.resolve().name}'; the open format expects them to match"))
        desc = meta.get("description")
        if not isinstance(desc, str) or not desc.strip():
            out.append(Finding("error", "SK020", "SKILL.md", "'description' is required and must be non-empty"))
        else:
            if len(desc) > 1024:
                out.append(Finding("error", "SK021", "SKILL.md", f"description is {len(desc)} characters; the limit is 1024"))
            if "<" in desc or ">" in desc:
                out.append(Finding("warning", "SK022", "SKILL.md", "description contains angle brackets; some hosts reject them, so use plain words"))
            if not TRIGGER_HINTS.search(desc):
                out.append(Finding("warning", "SK023", "SKILL.md", "description does not say when to use the skill (for example 'Use when ...'); the description is what decides whether it is loaded"))
            if len(desc) < 80:
                out.append(Finding("info", "SK024", "SKILL.md", f"description is only {len(desc)} characters; name the tasks, inputs and phrases that should trigger it"))
            if FIRST_PERSON.match(desc):
                out.append(Finding("info", "SK025", "SKILL.md", "description is written in first or second person; describe the skill in the third person"))
        comp = meta.get("compatibility")
        if comp is not None and (not isinstance(comp, str) or len(comp) > 500):
            out.append(Finding("error", "SK030", "SKILL.md", "'compatibility' must be a string of at most 500 characters"))
        if "metadata" in meta and not isinstance(meta["metadata"], dict):
            out.append(Finding("error", "SK031", "SKILL.md", "'metadata' must be a mapping of string keys to string values"))
        for key in sorted(set(meta) - KNOWN_KEYS):
            out.append(Finding("info", "SK032", "SKILL.md", f"frontmatter key '{key}' is not in the open format; hosts that do not support it ignore or reject it"))

    body = "\n".join(body_lines)
    if not body.strip():
        out.append(Finding("error", "SK041", "SKILL.md", "instruction body after the frontmatter is empty"))
    elif len(body_lines) > max_body_lines:
        out.append(Finding("warning", "SK040", "SKILL.md", f"body is {len(body_lines)} lines; keep it under {max_body_lines} and move detail into reference files"))

    files, junk_dirs = [], []
    for kind, rel in iter_files(root):
        (junk_dirs if kind == "junkdir" else files).append(rel)
    for d in junk_dirs:
        out.append(Finding("warning", "SK070", str(d), f"{JUNK_DIRS[d.name]} should not ship in the skill"))
    for rel in files:
        reason = JUNK.get(rel.name) or JUNK_SUFFIXES.get(rel.suffix.lower())
        if rel.name.startswith(".env.") and rel.name not in (".env.example", ".env.sample"):
            reason = "environment file (may hold credentials)"
        if reason:
            out.append(Finding("warning", "SK070", str(rel), f"{reason} should not ship in the skill"))
        if rel.name == "SKILL.md" and rel != Path("SKILL.md"):
            out.append(Finding("warning", "SK071", str(rel), "nested SKILL.md; hosts may register it as a second skill"))

    md_files = [rel for rel in files if rel.suffix.lower() == ".md"]
    reached, reached_dirs, named = set(), set(), set()
    root_resolved = root.resolve()
    for rel in md_files:
        path = root / rel
        content = path.read_text(encoding="utf-8", errors="replace")
        offset = body_start - 1 if rel == Path("SKILL.md") else 0
        scan_text = body if rel == Path("SKILL.md") else content
        named.update(m.group(1) for m in re.finditer(r"`([\w.-]+\.[A-Za-z0-9]+)`", scan_text))
        bases = [path.parent] + [a for a in path.parent.parents if root_resolved in (a.resolve(), *a.resolve().parents)]
        for n, target, kind in referenced_paths(scan_text):
            # a path may be written relative to the file, to an enclosing module folder, or to the skill root
            hit = next((b / target for b in bases if (b / target).exists()), None)
            if hit is None:
                level = "error" if kind == "link" else "warning"
                out.append(Finding(level, "SK050", str(rel), f"{'link' if kind == 'link' else 'path'} '{target}' does not exist", n + offset))
            else:
                try:
                    target_rel = hit.resolve().relative_to(root_resolved)
                except ValueError:
                    out.append(Finding("info", "SK052", str(rel), f"'{target}' points outside the skill folder; it will not resolve when the skill is installed on its own", n + offset))
                    continue
                (reached_dirs if hit.is_dir() else reached).add(target_rel)
        for n, line in enumerate(scan_text.splitlines(), start=1):
            if re.search(r"(?<![\w.])(/home/|/Users/|[A-Z]:\\\\)", line):
                out.append(Finding("warning", "SK051", str(rel), "absolute machine-specific path; use paths relative to the skill", n + offset))
        if rel != Path("SKILL.md"):
            n_lines = content.count("\n") + 1
            head = "\n".join(content.splitlines()[:40]).lower()
            if n_lines > max_ref_lines and "contents" not in head:
                out.append(Finding("info", "SK061", str(rel), f"{n_lines} lines without a contents list near the top; add one so a reader can jump to the right section"))

    for rel in files:
        if rel.parts and rel.parts[0] in ("references", "assets", "scripts") or (len(rel.parts) > 2 and rel.parts[-2] == "references"):
            listed = rel.parent in reached_dirs and rel.name in named  # folder referenced and file named in a table or list
            if rel not in reached and not listed and rel.suffix.lower() in (".md", ".py", ".json", ".sh", ".js", ".txt", ".html"):
                out.append(Finding("info", "SK060", str(rel), "no Markdown file in the skill points to this file, so an agent may never read or run it"))

    order = {"error": 0, "warning": 1, "info": 2}
    out.sort(key=lambda f: (order[f.level], f.path, f.line or 0, f.code))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only checks for an Agent Skill folder (frontmatter, size, links, packaging). "
                    "Exit 0 = no errors, 1 = errors (or warnings with --strict), 2 = folder not found.")
    parser.add_argument("skill_dir", help="folder that contains SKILL.md")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--max-body-lines", type=int, default=500, help="warn when the SKILL.md body is longer (default 500)")
    parser.add_argument("--max-ref-lines", type=int, default=300, help="suggest a contents list above this many lines (default 300)")
    args = parser.parse_args(argv)
    if not Path(args.skill_dir).is_dir():
        print(f"error: {args.skill_dir} is not a directory", file=sys.stderr)
        return 2
    findings = lint(args.skill_dir, args.max_body_lines, args.max_ref_lines)
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in ("error", "warning", "info")}
    if args.json:
        print(json.dumps({"skill": str(Path(args.skill_dir)), "counts": counts, "findings": [f.as_dict() for f in findings]}, indent=2, sort_keys=True))
    else:
        for f in findings:
            print(f)
        print(f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info")
    failed = counts["error"] or (args.strict and counts["warning"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
