# Auditing installed skills and keeping them portable across hosts

Read this when the question is about the skills a person or team already has: which ones are worth keeping, which overlap or have gone stale, why the agent seems to pick the wrong one, or whether a skill written for one agent host will work in another. Finding, importing and updating a single skill is `skill-housekeeping.md`; package checks are `scripts/lint_skill.py`; whether a skill helps is `skill-evaluation.md`. Cleaning up the rest of the configuration (hooks, permissions, MCP servers) is `workspace-config-audit.md`.

Contents: inventory · per-skill review · verdicts · large inventories and re-audits · consolidation · health over time · portability across hosts · done when.

## 1. Inventory every skill root

List the roots the host loads and say which exist. For Claude Code that is the user folder (`~/.claude/skills/`), the project folder (`.claude/skills/`) and skills shipped inside enabled plugins; other hosts use other folders, so check the host's documentation. Skip archive folders that the host does not load.

```bash
for root in ~/.claude/skills .claude/skills; do
  if [ ! -d "$root" ]; then echo "absent:  $root"; continue; fi
  echo "scanned: $root"
  find "$root" -name SKILL.md -not -path '*/.trash/*' -not -path '*/_archive/*' | sort | while read -r f; do
    dir=$(dirname "$f")
    digest=$(find "$dir" -type f ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12)
    printf '%s\t%s lines\t%s\n' "$digest" "$(wc -l < "$f" | tr -d ' ')" "$dir"
  done
done
python3 <productcraft>/modules/builder-tools/scripts/lint_skill.py --json path/to/skill    # per skill
```

Record for each skill: path, name, description, size, a digest of the whole folder (not only `SKILL.md`; references and scripts change too), and where it came from (self-written, team, third party with version). If usage is measured in the host's logs, record it; if not, write **unmeasured**. Missing usage data is never evidence that a skill is unused.

## 2. Review each skill

Read each skill in full and check:

| Check | Question | Typical evidence |
|---|---|---|
| Overlap | Does another skill, the instruction file or saved memory already cover this? | Same nouns in two descriptions; the same steps in two bodies |
| Trigger fit | Do the name, description and body describe the same job? | A description promising more than the body delivers, or the reverse |
| Currency | Do tool names, CLI flags, API names and versions still match what is installed? | `<tool> --help`, the lockfile, the tool's current documentation |
| Integrity | Do links resolve, do bundled scripts exist and pass their tests? | `lint_skill.py` findings; the skill's own test suite |
| Actionability | Does it give steps, commands or checks the agent can act on, or general advice it already knows? | Paragraphs that could be deleted without changing a run |
| Safety | Has a third-party skill changed since it was vetted? | Digest differs from the recorded one (`../../agent-safety/references/vetting-extensions.md`) |

## 3. Verdicts with reasons that stand alone

| Verdict | Meaning |
|---|---|
| Keep | Useful, current, no material overlap |
| Improve | Worth keeping; a named section needs a named change |
| Update | References outdated tools, flags or APIs; list them with the current equivalents |
| Retire | Low value, broken or fully covered elsewhere; name what covers it |
| Merge into X | Substantial overlap; name the target and what to move |

Each reason must let someone decide without re-reading the skill:
- Weak: "Overlaps with deploy-checklist." Strong: "Steps 2 to 5 repeat deploy-checklist's pre-flight section word for word; its only unique content is the rollback table, which should move into deploy-checklist under 'Rollback'. Then retire this skill."
- Weak: "Too long." Strong: "410 lines; the 'Framework comparison' section (lines 80 to 160) is general background the agent already knows. Delete it to reach about 250 lines; keep the migration steps."
- Weak: "Unchanged." Strong (re-audit of a skill whose content did not change): "Content identical to the last review; still the only skill covering the label printer's protocol, used in the warehouse repository."

## 4. Large inventories and re-audits

- **Batches:** review in groups of related skills (by theme, around twenty at a time), giving each batch the full inventory so overlap with skills outside the batch is still visible. Key every result by path, not by name; two skills can share a name in different roots.
- **Resume:** save results after each batch with the digest that was reviewed. An interrupted audit resumes with the skills that have no result for their current digest.
- **Re-audit by content, not timestamp:** re-review only skills whose digest changed or that are new. Carry forward the rest with their reasons restated, and drop results for skills that no longer exist.

## 5. Consolidation

1. For every Retire or Merge, show the evidence, what covers the need instead, and what depends on the skill (other skills that link to it, instruction-file lines, hooks or commands that call its scripts).
2. The user confirms each one separately.
3. Act reversibly: disable or move the folder to a dated archive outside the loaded roots rather than deleting it, and log what moved and how to restore it (`workspace-config-audit.md`, section 5).
4. Apply Improve and Update changes as normal edits, then re-run `lint_skill.py` and the skill's own tests.

## 6. Health over time

Where the host or a hook records skill use and failures (only with the user's consent, stored locally), useful signals are: skills that fail to load, bundled scripts that exit with errors, and skills never loaded over a period that matters for them. Treat them as leads for the next audit, not verdicts: a skill used once a quarter for a tax filing or a release is not dead.

## 7. Portability across agent hosts

Several agent hosts read the open Agent Skills format, but they differ at the edges. When a skill must work in more than one (for example Claude Code plus another vendor's CLI or an editor agent), check these:

- **Frontmatter keys.** The open format defines `name`, `description`, `license`, `compatibility`, `metadata` and the experimental `allowed-tools`. Hosts add their own optional keys (argument hints, model choice, invocation controls); another host may ignore or reject them. Keep host-specific keys out of copies meant for other hosts, or confirm the target accepts them. `lint_skill.py` reports keys outside the open format (SK032).
- **Substituted variables.** Some hosts replace variables in skill or command text before the agent sees it, or set environment variables for plugin files (in Claude Code, `$ARGUMENTS` in commands and plugin-root and project-directory variables). Elsewhere the same text arrives literally or as an unset variable, so `"${PLUGIN_ROOT_VAR}/scripts/check.py"` becomes `/scripts/check.py`. In shared skills, refer to files relative to the skill folder and say so, or give a fallback (`"${PROJECT_DIR_VAR:-$(pwd)}"`). Find candidates with `grep -rnE '\$\{?(CLAUDE_[A-Z_]+|ARGUMENTS)\b' path/to/skill`.
- **Tool names.** "Use the Read tool" or `allowed-tools: Bash(git:*)` names one host's tools. Write instructions at the level of the capability ("read the file", "run `git status`") and keep host-specific tool names to the places that need them.
- **Discovery folders and names.** Each host loads skills from its own folders, and the folder name must match `name` in every copy. Keep one canonical source and generate the copies with a script, with a CI check that fails when a copy differs from what the generator produces. Hand-maintained duplicates drift.
- **Shell and OS.** Bash snippets break on Windows shells; GNU and BSD tools differ (`sed -i`, `date -d` versus `date -v`, `stat -c` versus `stat -f`). Put logic that must run everywhere in a standard-library Python script with `--help`.
- **Instruction files.** Several hosts read `AGENTS.md`; Claude Code reads `CLAUDE.md`, which can import another file with an `@path` line. Keep one source of truth and import or generate the other, rather than two files that disagree.

## Done when

- Every loaded skill root is listed as scanned or absent, and each skill has a digest, origin and usage figure or "unmeasured".
- Each skill has a verdict with a stand-alone reason; Retire and Merge verdicts name what covers the need and what depends on the skill.
- Removals and merges were confirmed one by one, done reversibly and logged; changed skills pass `lint_skill.py` and their tests.
- Skills meant for several hosts have been checked for host-only keys, variables, tool names and shell syntax, and copies are generated from one source with a drift check.
