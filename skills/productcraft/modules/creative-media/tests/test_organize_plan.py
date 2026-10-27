"""Tests for scripts/organize_plan.py (standard library only)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "organize_plan.py"
SPEC = importlib.util.spec_from_file_location("organize_plan", SCRIPT)
organize_plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(organize_plan)


def stamp(year, month=6, day=15, hour=12):
    return datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp()


def write(path: Path, text: str = "x", year: int | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if year is not None:
        ts = stamp(year)
        os.utime(path, (ts, ts))
    return path


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = organize_plan.main([str(a) for a in argv])
    return code, out.getvalue()


def plan(*argv):
    code, text = run(*argv, "--format", "json")
    return code, json.loads(text)


def snapshot(root: Path):
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            p = Path(dirpath) / name
            st = p.lstat()
            if p.is_dir() and not p.is_symlink():
                rows.append((str(p.relative_to(root)), "dir"))  # folder times change when entries move
            else:
                rows.append((str(p.relative_to(root)), st.st_size, st.st_mtime_ns, p.is_symlink()))
    return rows


def case_insensitive_fs(folder: Path) -> bool:
    probe = folder / "CaseProbe.tmp"
    probe.write_text("p")
    try:
        return (folder / "caseprobe.tmp").exists()
    finally:
        probe.unlink()


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "inbox"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def moves(self, data):
        return {m["from"]: m for m in data["moves"]}

    def test_name_date_wins_over_mtime(self):
        write(self.root / "report 2024-03-15.pdf", year=2019)
        write(self.root / "IMG_20230701_1200.JPG", year=2019)
        code, data = plan(self.root)
        self.assertEqual(code, 0)
        moves = self.moves(data)
        self.assertEqual(moves["report 2024-03-15.pdf"]["to"], "Documents/2024/report 2024-03-15.pdf")
        self.assertEqual(moves["report 2024-03-15.pdf"]["date_from"], "name")
        self.assertEqual(moves["IMG_20230701_1200.JPG"]["to"], "Images/2023/IMG_20230701_1200.JPG")

    def test_mtime_fallback_is_utc(self):
        path = write(self.root / "notes.txt")
        ts = datetime(2021, 12, 31, 23, 30, tzinfo=timezone.utc).timestamp()
        os.utime(path, (ts, ts))
        code, data = plan(self.root)
        move = self.moves(data)["notes.txt"]
        self.assertEqual(move["to"], "Documents/2021/notes.txt")
        self.assertEqual(move["date_from"], "mtime")
        self.assertEqual(move["date"], "2021-12-31")

    def test_impossible_date_in_name_is_ignored(self):
        write(self.root / "scan_20240230.pdf", year=2020)
        _, data = plan(self.root)
        move = self.moves(data)["scan_20240230.pdf"]
        self.assertEqual(move["to"], "Documents/2020/scan_20240230.pdf")
        self.assertEqual(move["date_from"], "mtime")

    def test_date_source_name_only_uses_undated(self):
        write(self.root / "plain.pdf", year=2020)
        _, data = plan(self.root, "--date-source", "name")
        self.assertEqual(self.moves(data)["plain.pdf"]["to"], "Documents/Undated/plain.pdf")

    def test_by_date_and_month_depth(self):
        write(self.root / "a.png", year=2022)
        _, data = plan(self.root, "--by", "date")
        self.assertEqual(self.moves(data)["a.png"]["to"], "2022/2022-06/a.png")
        _, data = plan(self.root, "--date-depth", "month")
        self.assertEqual(self.moves(data)["a.png"]["to"], "Images/2022/2022-06/a.png")
        _, data = plan(self.root, "--by", "type")
        self.assertEqual(self.moves(data)["a.png"]["to"], "Images/a.png")

    def test_collision_with_existing_file_ignores_case_by_default(self):
        write(self.root / "Documents" / "2024" / "Report.pdf", "old")
        write(self.root / "report.pdf", "new", year=2024)
        code, data = plan(self.root)
        self.assertEqual(code, 1)
        move = self.moves(data)["report.pdf"]
        self.assertEqual(move["to"], "Documents/2024/report (2).pdf")
        self.assertTrue(any("collision" in note for note in move["review"]))

    def test_case_sensitive_flag(self):
        if case_insensitive_fs(self.root):
            self.skipTest("file system ignores case")
        write(self.root / "Documents" / "2024" / "Report.pdf", "old")
        write(self.root / "report.pdf", "new", year=2024)
        code, data = plan(self.root, "--case-sensitive")
        self.assertEqual(code, 0)
        self.assertEqual(self.moves(data)["report.pdf"]["to"], "Documents/2024/report.pdf")

    def test_two_sources_planned_to_same_target(self):
        write(self.root / "x.txt", "1", year=2023)
        write(self.root / "sub" / "x.txt", "2", year=2023)
        code, data = plan(self.root, "--recursive")
        self.assertEqual(code, 1)
        targets = sorted(m["to"] for m in data["moves"])
        self.assertEqual(targets, ["Documents/2023/x (2).txt", "Documents/2023/x.txt"])
        self.assertEqual(self.moves(data)["x.txt"]["to"], "Documents/2023/x (2).txt")

    def test_double_extension_keeps_suffix_together(self):
        write(self.root / "Archives" / "2022" / "backup.tar.gz", "old")
        write(self.root / "backup.tar.gz", "new", year=2022)
        _, data = plan(self.root)
        move = self.moves(data)["backup.tar.gz"]
        self.assertEqual(move["category"], "Archives")
        self.assertEqual(move["to"], "Archives/2022/backup (2).tar.gz")

    def test_skipped_entries(self):
        write(self.root / ".hidden.txt", year=2020)
        write(self.root / ".DS_Store")
        write(self.root / "Thumbs.db")
        write(self.root / "movie.mp4.crdownload")
        write(self.root / "draft.tmp")
        write(self.root / "keep-out.log", year=2020)
        target = write(self.root / "real.txt", year=2020)
        try:
            os.symlink(target, self.root / "alias.txt")
            has_link = True
        except (OSError, NotImplementedError):
            has_link = False
        code, data = plan(self.root, "--exclude", "*.log")
        reasons = {s["path"]: s["reason"] for s in data["skipped"]}
        self.assertEqual(reasons[".hidden.txt"], "hidden")
        self.assertEqual(reasons[".DS_Store"], "system file")
        self.assertEqual(reasons["Thumbs.db"], "system file")
        self.assertIn("unfinished download", reasons["movie.mp4.crdownload"])
        self.assertIn("temporary", reasons["draft.tmp"])
        self.assertEqual(reasons["keep-out.log"], "excluded by --exclude")
        if has_link:
            self.assertIn("symbolic link", reasons["alias.txt"])
        self.assertEqual([m["from"] for m in data["moves"]], ["real.txt"])
        self.assertEqual(code, 0)
        _, data = plan(self.root, "--include-hidden")
        self.assertIn(".hidden.txt", self.moves(data))

    def test_projects_and_bundles_are_kept_whole(self):
        write(self.root / "my-app" / "package.json", "{}")
        write(self.root / "my-app" / "index.js", year=2020)
        write(self.root / "repo" / ".git" / "HEAD", "ref")
        write(self.root / "repo" / "README.md", year=2020)
        write(self.root / "Holiday.photoslibrary" / "db.sqlite", year=2020)
        write(self.root / "loose" / "song.mp3", year=2020)
        _, data = plan(self.root, "--recursive")
        kept = {k["path"] for k in data["kept_folders"]}
        self.assertEqual(kept, {"my-app/", "repo/", "Holiday.photoslibrary/"})
        self.assertEqual([m["from"] for m in data["moves"]], ["loose/song.mp3"])

    def test_top_level_only_leaves_subfolders(self):
        write(self.root / "sub" / "inner.md", year=2020)
        write(self.root / "top.md", year=2020)
        _, data = plan(self.root)
        self.assertEqual([m["from"] for m in data["moves"]], ["top.md"])
        self.assertEqual(data["folders_left"], ["sub/"])

    def test_files_already_in_place_are_unchanged(self):
        write(self.root / "Documents" / "2024" / "minutes-2024-01-05.pdf", year=2019)
        code, data = plan(self.root, "--recursive")
        self.assertEqual(code, 0)
        self.assertEqual(data["moves"], [])
        self.assertEqual(data["unchanged"], ["Documents/2024/minutes-2024-01-05.pdf"])

    def test_destination_inside_root_is_not_scanned(self):
        write(self.root / "Sorted" / "Images" / "2020" / "old.png", year=2020)
        write(self.root / "new.png", year=2021)
        _, data = plan(self.root, "--recursive", "--dest", self.root / "Sorted")
        self.assertEqual([m["from"] for m in data["moves"]], ["new.png"])
        self.assertEqual(data["moves"][0]["to"], "Images/2021/new.png")

    def test_root_inside_destination_still_scans_subfolders(self):
        write(self.root / "sub" / "deep.csv", year=2020)
        _, data = plan(self.root, "--recursive", "--dest", self.root.parent)
        self.assertEqual(self.moves(data)["sub/deep.csv"]["to"], "Spreadsheets/2020/deep.csv")

    def test_extension_override(self):
        write(self.root / "IMG_1.HEIC", year=2020)
        _, data = plan(self.root, "--ext", ".heic=Photos")
        self.assertEqual(self.moves(data)["IMG_1.HEIC"]["to"], "Photos/2020/IMG_1.HEIC")

    def test_hash_duplicates_flags_identical_content_only(self):
        write(self.root / "a.txt", "same", year=2020)
        write(self.root / "b.txt", "same", year=2020)
        write(self.root / "c.txt", "diff", year=2020)
        code, data = plan(self.root, "--hash-duplicates")
        self.assertEqual(code, 1)
        self.assertEqual(data["duplicates"], [{"path": "b.txt", "same_content_as": "a.txt", "bytes": 4}])

    def test_json_is_deterministic(self):
        for i in range(6):
            write(self.root / f"file-{i}.txt", str(i), year=2020 + i % 3)
        self.assertEqual(run(self.root, "--format", "json"), run(self.root, "--format", "json"))

    def test_never_touches_the_tree(self):
        write(self.root / "a.pdf", year=2020)
        write(self.root / "sub" / "b.png", year=2021)
        write(self.root / "Documents" / "2020" / "a.pdf", "other")
        (self.root / "map.csv").write_text("source,target\na.pdf,renamed/a.pdf\n", encoding="utf-8")
        before = snapshot(self.root)
        for fmt in ("text", "json", "sh", "undo-sh"):
            run(self.root, "--recursive", "--hash-duplicates", "--format", fmt)
            run(self.root, "--from-csv", self.root / "map.csv", "--format", fmt)
        self.assertEqual(before, snapshot(self.root))


class CsvModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root, self.dest = base / "in", base / "out"
        self.root.mkdir()
        self.csv = base / "renames.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def plan_csv(self, rows: str):
        self.csv.write_text(rows, encoding="utf-8")
        return plan(self.root, "--from-csv", self.csv, "--dest", self.dest)

    def test_rows_are_cleaned_checked_and_resolved(self):
        write(self.root / "inv1.pdf", "1")
        write(self.root / "inv2.pdf", "2")
        write(self.root / "inv3.pdf", "3")
        write(self.root / "scan.jpg", "4")
        write(self.dest / "2024" / "taken.pdf", "existing")
        code, data = self.plan_csv(
            "Source,Target\n"
            "inv1.pdf,2024/2024-01-31 Acme: invoice?7.pdf\n"
            "inv2.pdf,2024/taken.pdf\n"
            "inv3.pdf,../outside.pdf\n"
            "missing.pdf,2024/m.pdf\n"
            "scan.jpg,2024/con.pdf\n"
            "inv1.pdf,2024/again.pdf\n"
        )
        self.assertEqual(code, 1)
        moves = {m["from"]: m for m in data["moves"]}
        self.assertEqual(moves["inv1.pdf"]["to"], "2024/2024-01-31 Acme- invoice-7.pdf")
        self.assertEqual(moves["inv2.pdf"]["to"], "2024/taken (2).pdf")
        self.assertEqual(moves["scan.jpg"]["to"], "2024/_con.pdf")
        self.assertTrue(any("extension differs" in n for n in moves["scan.jpg"]["review"]))
        reasons = sorted(e["reason"].split(":")[0] for e in data["errors"])
        self.assertEqual(reasons, ["source is not a regular file", "source listed twice",
                                   "unsafe or empty target path"])

    def test_header_is_required(self):
        write(self.root / "a.pdf")
        self.csv.write_text("from,to\na.pdf,b.pdf\n", encoding="utf-8")
        code, _ = run(self.root, "--from-csv", self.csv)
        self.assertEqual(code, 2)


@unittest.skipUnless(shutil.which("sh") and os.name == "posix", "needs a POSIX shell")
class ShellScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "inbox"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def script(self, fmt: str) -> Path:
        _, text = run(self.root, "--recursive", "--format", fmt)
        path = self.base / f"{fmt}.sh"
        path.write_text(text, encoding="utf-8")
        return path

    def test_apply_then_undo_restores_the_tree(self):
        names = ["it's $HOME `x`.png", "-dash.txt", "space name.pdf", "sub/inner 2024-02-03.md"]
        for name in names:
            write(self.root / name, name, year=2020)
        before = snapshot(self.root)
        apply_script, undo_script = self.script("sh"), self.script("undo-sh")
        subprocess.run(["sh", str(apply_script)], check=True, capture_output=True)
        self.assertTrue((self.root / "Images" / "2020" / "it's $HOME `x`.png").is_file())
        self.assertTrue((self.root / "Documents" / "2020" / "-dash.txt").is_file())
        self.assertTrue((self.root / "Documents" / "2024" / "inner 2024-02-03.md").is_file())
        self.assertFalse((self.root / "space name.pdf").exists())
        subprocess.run(["sh", str(undo_script)], check=True, capture_output=True)
        self.assertEqual(before, snapshot(self.root))

    def test_apply_never_overwrites_a_target_that_appeared_later(self):
        write(self.root / "a.txt", "mine", year=2020)
        apply_script = self.script("sh")
        late = write(self.root / "Documents" / "2020" / "a.txt", "arrived later")
        result = subprocess.run(["sh", str(apply_script)], capture_output=True, text=True)
        self.assertIn("skip, target exists", result.stderr)
        self.assertEqual(late.read_text(encoding="utf-8"), "arrived later")
        self.assertEqual((self.root / "a.txt").read_text(encoding="utf-8"), "mine")


class CommandLineTests(unittest.TestCase):
    def test_help_and_usage_errors(self):
        ok = subprocess.run([sys.executable, "-I", str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0)
        self.assertIn("Never touches files", ok.stdout)
        missing = subprocess.run([sys.executable, "-I", str(SCRIPT), "/no/such/folder/here"],
                                 capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            bad = subprocess.run([sys.executable, "-I", str(SCRIPT), tmp, "--ext", "jpg=a/b"],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            text = subprocess.run([sys.executable, "-I", str(SCRIPT), tmp], capture_output=True, text=True)
            self.assertEqual(text.returncode, 0)
            self.assertIn("dry run", text.stdout)


if __name__ == "__main__":
    unittest.main()
