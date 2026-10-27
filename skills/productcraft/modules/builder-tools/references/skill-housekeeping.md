# Finding, importing and updating skills safely

Read this when the task is not to author a skill but to manage ones that already exist: find whether a skill for a job already exists before building one, bring a third-party skill into a project, or update an installed skill to a newer version. Authoring is `skill-authoring.md`; evaluating is `skill-evaluation.md`; the security verdict on anything third-party is `../../agent-safety/references/vetting-extensions.md`. This reference is the workflow that ties them together, and its first rule is that installing a skill gives someone else's instructions and code the agent's permissions, so nothing third-party is trusted before it is read.

## Find before you build

Before writing a new skill, check whether the capability already exists:

- **In this project and the agent's own skills.** List the installed skills and read their descriptions; the job may already be covered, or covered by a one-line instruction that belongs in the agent instruction file rather than a new skill (`skill-authoring.md` on when a skill is worth it).
- **In a trusted source** the user already relies on, by the concrete nouns of the task (file types, tool names, the task verb).

Prefer extending or configuring an existing skill over adding a parallel one. Two skills for the same job trigger against each other and confuse the agent's choice. If a search tool or marketplace is available, use it to locate candidates, but treat every result as a candidate to vet, not to install: a listing's name, stars or description are marketing, not a review.

## Import a third-party skill safely

Bringing in a skill from outside follows one order, and the order is the safety:

1. **Identify exactly what would be installed:** the source and exact version or commit, the type (a bare skill, or a plugin bundling hooks, commands and MCP servers), where it would install, and everything that would run automatically.
2. **Fetch without running it.** Clone or download into an empty folder outside the project. Do not run its installer or build, and do not open its folder as the working project, because its settings, hooks and MCP config could load. The commands are in `../../agent-safety/references/vetting-extensions.md`.
3. **Pull the whole skill, not just `SKILL.md`.** Recurse into the folder and fetch every file the skill references: `references/`, `scripts/`, `assets/`, any host metadata file (a `skill.json` or plugin manifest), and anything a file links to. A skill delivered with missing files is broken; a half-downloaded one can behave unpredictably. After fetching, list the folder and confirm the files are present and non-empty before going on.
4. **Vet it.** Run `../../agent-safety/scripts/scan_skill.py` for leads, then read every instruction file, script, hook and manifest and compare what it can do against what it claims to do, writing the verdict in the format that reference defines. A clean scan is not approval.
5. **Lint the package** with `scripts/lint_skill.py` for structural problems (broken links, oversized files, stray caches) and, for its configuration, `agent-config-linting.md`.
6. **Install only with the user's explicit OK**, in one location (so it does not load twice), pinned to the reviewed version or commit, with the narrowest permissions. Record a digest or commit of exactly what you reviewed, so a later change is visible.

Never install, enable or edit agent settings to load a skill without the user's agreement after they have seen the verdict.

## Update an installed skill

An update is a fresh import of a new version, reviewed as a diff against the one you already trust:

1. **Find the version in use and the upstream source.** Note the installed version or commit and where it came from.
2. **Fetch the new version into a staging folder,** the same fetch-without-running way as an import. Convert a web view of a file to its raw form so you get source, not rendered HTML.
3. **Diff against what you have.** Compare the new files with the installed ones (`git diff OLD_COMMIT NEW_COMMIT`, or a file-by-file compare). The diff is the review: read changed instructions, scripts, hooks and permissions, not just the version number. An update is a common way for a once-safe extension to gain a hook, a network call or a credential read, so re-vet every change with `scan_skill.py` and the checklist.
4. **Verify completeness before overwriting.** Confirm the staged files are present and non-empty. Never overwrite a working skill with an empty or partially downloaded file; a failed fetch that silently leaves a zero-byte file is a real failure mode. Keep the old version until the new one is verified.
5. **Re-run the package checks** (`lint_skill.py`) and, if the skill ships scripts with tests, run them. A skill whose bundled script broke is worse than none, because the agent trusts it.
6. **Swap in the new version with the user's OK,** record the new reviewed commit, and note in the report what changed between versions, especially any new capability or permission.

## Removing a skill

When removing a skill, also remove what it added elsewhere: hook entries, MCP server declarations, permission rules and any files it wrote outside its own folder. A skill folder deleted while its hook entry remains leaves a dangling command.

## Done when

- A search confirmed no existing skill or one-line instruction already covers the job before a new skill was proposed.
- Every third-party skill was fetched without running, pulled complete, vetted with a written verdict, linted, and installed only with the user's OK, pinned, in one place.
- Every update was reviewed as a diff against the trusted version, re-vetted, and verified complete before overwriting, with the old version kept until the new one passed.
- The report records the reviewed version or commit and any new capability an update introduced.
