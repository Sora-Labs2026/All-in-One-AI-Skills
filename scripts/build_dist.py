#!/usr/bin/env python3
"""Build or verify the uploadable skill bundles in dist/.

    python3 scripts/build_dist.py          # rebuild dist/ from skills/
    python3 scripts/build_dist.py --check  # exit 1 if dist/ is out of date

Each bundle is a ZIP with a single top-level <skill>/ folder plus the skill's
WORKSPACE-SETUP-PROMPT.txt copied alongside it. The check compares member names
and bytes, not ZIP bytes, so it is stable across zlib versions.
"""
import argparse
import pathlib
import sys
import zipfile

REPO = pathlib.Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
# skill folder -> (zip name, standalone setup prompt name)
BUNDLES = {
    "productcraft": ("productcraft.zip", "PRODUCTCRAFT-WORKSPACE-SETUP-PROMPT.txt"),
}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store"}
ZIP_DATE = (2026, 10, 23, 0, 0, 0)


def source_files(skill):
    root = REPO / "skills" / skill
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and not SKIP_PARTS.intersection(rel.parts) and path.suffix != ".pyc":
            files[f"{skill}/{rel.as_posix()}"] = path.read_bytes()
    return files


def build(skill, zip_name, prompt_name):
    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(DIST / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in source_files(skill).items():
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data, compresslevel=9)
    prompt = REPO / "skills" / skill / "WORKSPACE-SETUP-PROMPT.txt"
    (DIST / prompt_name).write_bytes(prompt.read_bytes())
    print(f"built dist/{zip_name} and dist/{prompt_name}")


def check(skill, zip_name, prompt_name):
    problems = []
    zip_path = DIST / zip_name
    if not zip_path.is_file():
        problems.append(f"dist/{zip_name} missing")
    else:
        with zipfile.ZipFile(zip_path) as zf:
            packed = {n: zf.read(n) for n in zf.namelist()}
        expected = source_files(skill)
        for name in sorted(expected.keys() | packed.keys()):
            if expected.get(name) != packed.get(name):
                problems.append(f"dist/{zip_name}: {name} differs from skills/")
    prompt = REPO / "skills" / skill / "WORKSPACE-SETUP-PROMPT.txt"
    out = DIST / prompt_name
    if not out.is_file() or out.read_bytes() != prompt.read_bytes():
        problems.append(f"dist/{prompt_name} differs from skills/{skill}/WORKSPACE-SETUP-PROMPT.txt")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify dist/ instead of rebuilding it")
    args = parser.parse_args()
    if not args.check:
        for skill, names in BUNDLES.items():
            build(skill, *names)
        return 0
    problems = [p for skill, names in BUNDLES.items() for p in check(skill, *names)]
    for p in problems:
        print("FAIL", p)
    if problems:
        print("Run: python3 scripts/build_dist.py")
        return 1
    print("PASS: dist/ matches skills/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
