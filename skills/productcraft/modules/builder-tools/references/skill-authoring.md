# Authoring an Agent Skill

Read this when creating or restructuring a skill. Evaluation (does it trigger, does it help) is in `skill-evaluation.md`.

Contents: what a skill is · folder layout · frontmatter rules · the description · the body · progressive disclosure · bundled scripts · worked example: ProductCraft · pre-release checklist.

## What a skill is, and when one is worth it

A skill is a folder an agent can load on demand: a `SKILL.md` with a short machine-read header and instructions, plus optional files the instructions point to. Only the header (name and description) is in the agent's context all the time; the body is read when the agent decides the skill applies; other files are read or run only when the body sends the agent there.

Write a skill when a task recurs and the agent, unaided, gets it wrong or slow in the same ways: a house format, a multi-step workflow with a fixed order, a domain rule set, a fragile tool sequence. Do not write one for something the agent already does well from a one-line instruction (put that line in the project's agent instructions file instead), or for a one-off task.

## Folder layout

```text
invoice-maker/                  # folder name = skill name
├── SKILL.md                    # required: frontmatter + instructions
├── references/                 # read on demand: detailed rules, formats, examples
│   ├── layout-rules.md
│   └── tax-by-country.md
├── scripts/                    # run, not read: deterministic or fragile steps
│   └── build_invoice.py
├── assets/                     # used in outputs: templates, fonts, logos
│   └── invoice-template.docx
└── tests/                      # for the scripts; not loaded by the agent
    └── test_build_invoice.py
```

- One `SKILL.md` per skill. A second `SKILL.md` deeper in the tree may be registered as another skill by some hosts. A large skill with several areas uses one entry file and module guides (see the worked example), not nested skills.
- Paths inside the skill are relative to the file that mentions them, or to the skill root; say which convention you use and keep to it. No absolute paths, no machine-specific locations.
- Ship nothing secret or generated: no `.env` files, keys, caches (`__pycache__`, `node_modules`) or large binaries the instructions do not use.

## Frontmatter rules

The header is YAML between `---` lines at the very top of `SKILL.md`. The open Agent Skills format defines:

| Field | Required | Rule |
|---|---|---|
| `name` | yes | 1-64 characters; lowercase letters, digits and hyphens; no leading, trailing or doubled hyphen; matches the folder name |
| `description` | yes | 1-1024 characters; what the skill does and when to use it |
| `license` | no | license name or a pointer to a bundled license file |
| `compatibility` | no | up to 500 characters: required tools, runtimes or network access |
| `metadata` | no | map of string keys to string values (author, version) |
| `allowed-tools` | no | experimental; pre-approved tools, support varies by host |

Hosts may add their own optional keys and may enforce extra rules (some reject angle brackets in descriptions or reserved vendor words in names). Keep the header plain: single-line values or a folded `>` block, no anchors, no complex YAML. Check it with `scripts/lint_skill.py`.

```yaml
---
name: invoice-maker
description: >
  Builds invoice and receipt PDFs from order data using the company layout, tax rules and numbering.
  Use when the user asks for an invoice, a receipt, a billing PDF or a credit note for an order or
  customer, or wants an existing invoice corrected, even if they do not say "invoice".
license: MIT
metadata:
  version: "1.0.0"
---
```

## The description decides whether the skill is used

An agent sees many skill descriptions at once and picks by matching the request against them. Write it for that decision:
- **Say what it does and when to use it**, in the third person, with the concrete nouns and verbs users type: file types, tools, task names, synonyms ("receipt", "billing PDF", "credit note").
- **Name the boundaries** when a neighbor skill exists: "Not for quotes or purchase orders; use procurement-docs."
- **Lead with the distinctive part.** Hosts may truncate long lists of descriptions; the first sentence must carry the decision.
- **Keep the procedure out of it.** Describe the scope and the triggers, not the steps. An agent that finds a step list in the description may act on that summary and never open the body, skipping the checks only the body holds.
- Avoid vague value words ("powerful", "best practices", "helps with documents"): they match everything and decide nothing.
- Simple, one-step requests often do not trigger any skill, because the agent handles them directly. Judge triggering on realistic, multi-step requests (`skill-evaluation.md`).
- Change the description only against trigger tests: wording that reads better can trigger worse.

## The body: instructions an agent can follow

- **Open with the job and the outcome**: what a finished result looks like and how the agent will know it is done.
- **Give the workflow as ordered steps**, each with a check ("**Done when:** the PDF has one page per order and the totals match the CSV"). Agents follow sequences well and skip unstated checks.
- **Explain why** a rule exists when the reason is not obvious. An agent that knows the reason handles cases the rule did not foresee; a bare "ALWAYS" or "NEVER" is followed literally and fails at the edges. Reserve absolute rules for safety and irreversible actions.

- **Write against the failure you observed** in a run without the instruction (the baseline in `skill-evaluation.md`), and choose the kind of instruction that fixes that kind of failure:
  - The agent knows a step but skips it when hurried: state it as a firm requirement where it applies, say what breaks without it, and answer the specific excuses the baseline transcripts showed.
  - The result is complete but laid out wrong: show the output itself, as a filled-in example or a skeleton. Agents copy a shape more reliably than they avoid a list of mistakes.
  - Something is regularly missing: make it a labeled field in the output template, so an empty field is visible.
  - The right behavior depends on the situation: tie it to something the agent can test ("if the repository has a `migrations/` folder, ..."), not to a general rule with exceptions.

  Qualifiers such as "unless it matters" give the agent a reason to skip a rule. Turn a real exception into its own testable condition, then try the wording (`skill-evaluation.md`, iterating).
- **Prefer specifics to adjectives**: exact commands, file names, formats, thresholds, and an example of the output.
- **Write for an agent that has not seen this conversation.** No references to "the issue above", no unstated context, no assumptions about tools that may be missing; say what to do when a tool is absent.
- **Keep safety rules near the action** they govern, not in a distant section.
- **Cut what the agent already knows.** General programming advice, motivational text and long background cost context on every use. Test whether removing a paragraph changes results; if not, remove it.
- Keep `SKILL.md` well under 500 lines. When it grows, move detail into references and leave a one-line pointer.

## Progressive disclosure

Three layers, each loaded only when needed:
1. **Header** (always loaded): name and description, a few dozen words.
2. **Body** (loaded when the skill is chosen): routing, workflow, rules that apply to every use.
3. **Files** (loaded or run when the body points to them): references per topic or variant, scripts, templates.

Make the routing explicit so the agent reads only what the task needs: a table of "if the task involves X, read Y". Split references by the decision the agent makes (one file per format, provider, framework or task type), not by your own writing order. Keep links one level deep from the body where possible; a chain of references pointing to references gets skipped. Give files over about 300 lines a contents list at the top.

## Bundled scripts

Bundle a script when every run would otherwise re-derive the same code, when the step must be exact (parsing, validation, file formats, calculations), or when doing it by hand burns context.

- The body says when to run it, with the exact command, and what its output means. The agent should not have to read the source to use it; a clear `--help` is the interface.
- Make scripts deterministic, non-interactive, safe by default (read-only, or writing only to a named output), with meaningful exit codes and errors that say how to fix the input.
- State dependencies. Prefer the standard library; if a package is required, check for it at start and print the install command instead of a traceback.
- Test them (`tests/`), and run the tests before release. A broken bundled script is worse than none: the agent trusts it.
- Never fetch and execute remote code from a skill, and never hide network access or writes outside the working directory. State every side effect in the body, so whoever installs the skill can see what it will do.

## Worked example: ProductCraft

ProductCraft is itself a skill built this way; reading its files is the quickest way to see the patterns in practice.
- **One entry point.** `SKILL.md` holds the frontmatter, a router table (trigger in the task, files to read, typical execution), always-on behavior, safety overrides and an execution priority. Modules are not separate skills, so the host registers one skill and the router decides depth.
- **Description.** It states what the skill covers, lists the task types that should trigger it and ends with a scope rule ("do not run every module on every task"). At about 650 characters it is inside the 1024 limit with room for new trigger words; when modules are added, add their trigger nouns rather than adjectives.
- **Modules.** Small topics are single files (`modules/language-choice.md`); large ones are folders with a `GUIDE.md`, `references/` read selectively, and `scripts/` with `tests/` (`modules/launchguard/`). Each guide starts by saying it is reached through the router.
- **Scripts.** Standard library only, read-only, with `--help`, and unit tests run by `python3 -m unittest discover -s <dir>/tests -v`.
- **Package checks.** `scripts/check_package.py` verifies the package structure; `scripts/lint_skill.py` from this module adds generic checks. Run on a working tree, the linter reports no errors; it warns about local `__pycache__` folders (ignored by Git and absent from the release zip), notes that the README's links to the surrounding repository will not resolve in a standalone install (acceptable for a human-facing README), and suggests a contents list for the longest reference file.
- **Adding a module** follows the same path every time (steps in `../GUIDE.md`): write the module, add one router row and one bundled-guides line to `SKILL.md`, extend the package checker's module list, update the README and changelog, then run the package checks, all test suites and the trigger tests.

## Pre-release checklist

1. `python3 <productcraft>/modules/builder-tools/scripts/lint_skill.py <skill-dir>` reports no errors; warnings are fixed or explained.
2. Every file the body mentions exists, and every reference file is mentioned somewhere.
3. Bundled script tests pass; each script's `--help` matches what the body says.
4. Trigger tests and with/without comparisons from `skill-evaluation.md` have run on the final description and body, with results recorded.
5. Version and changelog updated; license present; no secrets, caches or personal paths in the package.
6. Installed in one place only, so it does not load twice.
