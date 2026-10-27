# Organizing files safely

Read this to tidy a Downloads folder, sort a dump of documents and photos into folders by type and date, rename files to a consistent pattern, find duplicate copies, or restructure an archive. The user's files are the priority: nothing is lost, nothing is overwritten, nothing is deleted by the agent, and every change can be undone. The bundled planner (`../scripts/organize_plan.py`) proposes the moves without touching anything.

Contents: ground rules · scope · look before planning · choose a scheme · make the plan · review it with the user · apply · verify and undo · duplicates · names that travel · photos and media · done when.

## Ground rules

1. **Plan first, apply only after the user approves the plan.** Show counts, a sample of moves, and every item that needs a decision.
2. **Move, never delete.** Duplicates, junk and "old stuff" go to a review folder or stay where they are. Deleting is the user's act, after the stop-check in `../../agent-safety/GUIDE.md`, and through the system trash where there is one.
3. **Never overwrite.** Every name collision gets a new name (`report (2).pdf`), and the apply step re-checks just before each move.
4. **Keep an undo log.** The plan in JSON is the record of every move; keep it next to the folder until the user is satisfied.
5. **Stay inside the scope.** Only the folder the user named. Leave alone: code projects and git repositories, application bundles, photo and music libraries managed by an app, cloud-sync roots unless the user means them, system and hidden files, and anything still downloading.
6. **Stop on surprises.** Unreadable files, permission errors, far more files than expected, or files in active use mean pause and ask.

## Scope

Settle in one short exchange:
- which folder, and whether subfolders are included;
- what to leave alone (current projects, a "keep" folder, files modified in the last few days);
- the scheme (by type, by date, both, or the user's own) and the destination (inside the same folder or elsewhere);
- what to do with duplicates (list them, or move extra copies to a review folder);
- whether names may change, or only locations.

## Look before planning

Read-only commands that summarize without changing anything:

```bash
find ~/Downloads -maxdepth 1 -type f | wc -l                               # how many files at the top level
find ~/Downloads -type f -name '*.*' | sed 's/.*\.//' | tr 'A-Z' 'a-z' | sort | uniq -c | sort -rn | head -20
du -sh ~/Downloads; du -ah ~/Downloads | sort -rh | head -15                # where the space goes
find ~/Downloads -type f -mtime -3 | head                                   # recently changed: maybe in use
```

Report the totals, the type mix, the date range, the largest items and anything odd (thousands of files in one place, an unexpected repository, files without extensions).

## Choose a scheme

- **Shallow beats deep.** Two levels (`Documents/2025/`) are easy to browse; five levels hide files.
- **By type, then year** suits mixed downloads. **By year, then month** suits photos and scans. **By project or client** suits work files, but needs the user's knowledge; propose it, do not guess it.
- **Dates:** a date in the file name (a scan or camera name such as `IMG_20250314_...`) is usually the real date. A file's modification time is often the download or copy date, and copying without preserving times resets it. For photos, the capture date in EXIF is better than either (see below).
- **Category names:** plain words in the user's language; the planner's defaults (`Documents`, `Images`, `Spreadsheets`, `Archives`, ...) can be overridden per extension with `--ext heic=Photos`.

## Make the plan

```bash
P=<productcraft>/modules/creative-media/scripts/organize_plan.py
python3 "$P" ~/Downloads                                   # text plan, top level, Category/YYYY/
python3 "$P" ~/Downloads --by date --recursive --exclude 'Keep/*'
python3 "$P" ~/Scans --dest ~/Archive --date-depth month --hash-duplicates --format json > plan.json
python3 "$P" ~/Invoices/inbox --from-csv renames.csv --dest ~/Invoices/2025   # explicit names, checked
```

What it does: reads the folder (it never writes), skips hidden entries, system files, symbolic links, unfinished downloads and excluded globs, keeps project folders and app bundles whole, takes dates from file names or else modification time in UTC, resolves every collision against existing files and other planned moves (ignoring case by default, as macOS and Windows do), and with `--hash-duplicates` flags files with identical content. `--from-csv` checks a list of `source,target` pairs instead: it rejects paths that escape the folder, cleans characters that are invalid on common file systems, and flags extension changes. Exit code 0 means nothing needs review, 1 means some items do, 2 is a usage error.

## Review it with the user

Show the summary line, ten or so representative moves, and every line marked for review: renamed for a collision, duplicates, cleaned names, errors. Ask the decisions that remain (keep both copies? a different folder for installers?). Adjust options and re-plan rather than editing the plan by hand.

## Apply

After an explicit yes:

```bash
python3 "$P" ~/Downloads --format json    > ~/Downloads-plan.json      # the undo log; keep it
python3 "$P" ~/Downloads --format sh      > ~/Downloads-apply.sh
python3 "$P" ~/Downloads --format undo-sh > ~/Downloads-undo.sh
sh ~/Downloads-apply.sh                                                # prints "moved N, skipped M"
```

The apply script creates folders and moves each file only if the target is still free and the source still exists; anything that changed since planning is skipped and listed, never overwritten. Generate all three files from the same state of the folder, right before applying. Moves within one file system keep timestamps. Across disks, a move is a copy plus delete: for those, copy with times preserved (`cp -p` or `rsync -a`), verify the copies, and let the user remove the originals.

For cloud-synced folders, check that files are fully downloaded and not placeholders, and expect the sync client to upload every moved file again. Pause syncing for large reorganizations if the user agrees.

## Verify and undo

- Count files before and after (the same number, at new paths), and compare total size.
- Spot-check a few moved files open correctly.
- Confirm the skipped and kept items are where they were.
- To undo: `sh ~/Downloads-undo.sh` moves every file back if its original path is free, then removes only the empty folders the plan created.

## Duplicates

- Same name does not mean same file, and different names can hide identical files. Compare size first, then a content hash (SHA-256); the planner does both with `--hash-duplicates`.
- Decide which copy to keep by location and name, not modification time alone. Keep the one in the most meaningful place.
- Move extra copies to a review folder (for example `_duplicates-to-review/`) with the plan, or just list them. Deleting them is the user's decision, one set at a time or after reviewing the folder.
- Near-duplicates (resized photos, re-exported PDFs) have different hashes; finding them needs perceptual hashing or manual review and is a separate, optional task.

## Names that travel

When renaming, produce names that work on every common system and sort well:
- Dates as `YYYY-MM-DD` at the start for chronological sorting.
- No `< > : " / \ | ? *` or control characters; no trailing spaces or dots; avoid reserved Windows names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`) even with an extension.
- Keep paths well under 260 characters for Windows tools that do not support long paths.
- Names that differ only in case collide on macOS and Windows; names that look identical can differ in Unicode normalization (macOS often stores decomposed accents). Normalize generated names to NFC.
- Keep the original extension, lowercased only if the user wants that.

## Photos and media

Use the capture date for photos and videos, not the file time. exiftool reads it and can show a renaming plan without moving anything:

```bash
cd ~/Pictures/import && exiftool -r -d '%Y/%Y-%m/%Y%m%d_%H%M%S%%-c.%%e' '-testname<DateTimeOriginal' .   # dry run only
```

`-testname` prints what would happen; relative target folders are created under the current directory, hence the `cd`. The same command with `-filename` instead performs the moves, so run that only after approval, on a copy or with the undo log of the plan. Files without the tag keep their place and are listed. Photo libraries managed by an app (`.photoslibrary` and similar) are never reorganized from outside the app.

## Done when

- The user approved a written plan, and every review item has a decision.
- Nothing was deleted or overwritten; the count of files is the same before and after.
- The JSON plan and the undo script are saved next to the folder, and the user knows how to undo.
- Skipped, kept and unreadable items are listed in the report with the reason.
