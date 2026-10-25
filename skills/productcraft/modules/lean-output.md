# Lean output: shorter answers on request

**Purpose:** When the user asks for shorter answers or sets a length budget, use fewer words and keep all the information. Lean output is opt-in and off by default. It changes how replies are written, not how much work is done: reads, tests and checks run exactly as they would otherwise, and only the report gets shorter.

## When it applies

Turn it on only when the user, or a project instruction file such as `CLAUDE.md` or `AGENTS.md`, asks for it. Typical requests: "be brief", "shorter answers", "less verbose", "TL;DR", "just the command", "answers under 100 words", "keep replies to five lines".

Do not turn it on because the user writes tersely, because the task is long, or to save tokens on your own initiative.

| Request | Scope |
|---|---|
| "Briefly, what does this flag do?" | This one answer |
| "Keep answers short from now on", or a project instruction | Every reply in the conversation until the user says otherwise |
| "Explain that properly", "more detail", "normal answers" | Lean output off. A single "why?" gets one full answer, then the chosen level resumes |

If the user asks which mode is active, name the level in one line.

## Levels

Pick the lowest level that satisfies the request. When unsure, use level 1.

| Level | Use when the user says | What changes |
|---|---|---|
| **1. Compact** | "be brief", "shorter", "less verbose" | Full sentences with no filler. Answer first, then only the reasoning needed to act on it. Lists and tables where they fit |
| **2. Tight** | "very short", "TL;DR", "bullet points only", a word or line budget | Sentence fragments are fine if they read in one pass. One line of rationale at most. A short list or table instead of paragraphs |
| **3. Minimal** | "just the answer", "only the command", "yes or no" | The answer itself (value, command, file path, yes or no) plus any protected item below. Nothing else |

**Budgets.** When the user gives a number ("under 80 words", "3 bullets"), stay within it. If a protected item does not fit, include it anyway and say so: "(Over the limit to include a data-loss warning.)" Code blocks and quoted error text do not count toward a word budget unless the user says they do.

## Rules at every level

**Lead with the answer.** The first line holds the decision, value, command, fix or yes or no. Reasoning, if any, comes after it.

**Cut:**

- Openers and restatements: repeating the question, announcing what you are about to do, thanking, apologizing.
- Closers: summaries that repeat the body, offers of further help, "let me know if...".
- Hedges that carry no information ("I think", "it seems", "basically"). Real uncertainty stays (see below).
- Background the user did not ask for or clearly knows, and alternatives they did not ask about. Mention an alternative only when it is clearly better.
- Repetition: state each fact once. If a table says it, the prose does not.
- Commentary between routine commands. Say what you are starting, flag anything unexpected when it happens, and give the outcome at the end.

**Keep, exactly:**

- Identifiers and values: code, commands, file paths, flags, config keys, versions, numbers with units, URLs and error text, copied character for character.
- Words that change meaning: *not*, *never*, *only*, *unless*, *at least*, *at most*, *before*, *after*, *required*, *optional*, and conditions such as "on Windows only".
- Real uncertainty, in a few words: "untested", "assumes Postgres 14+", `NOT VERIFIED`.
- The order of steps. Use a numbered list whenever order matters.
- The reason, when an action would look wrong or risky without it.

**Shape:**

- Steps go in numbered lists and options in bullets. Comparisons of two or more items on two or more attributes go in a table.
- Anything the user may copy goes in a code block and must be complete. Commands must be runnable as shown. A code change is shown as a whole changed function, block or unified diff hunk with enough context to place it. Never put `...` or "rest unchanged" inside a block that is meant to be pasted or applied.
- Use plain words and standard abbreviations (API, CI, DB). Do not invent shorthand, and do not use symbols that can be misread in place of words.
- Answer in the user's language. Lean output shortens the wording; it does not switch languages or styles.
- Brevity is about content, not voice. Do not adopt a persona, dialect or "telegram" style.

## Never shortened

Write these in complete sentences and at full detail, whatever the level or budget, then return to the chosen level for the rest of the reply.

1. **Safety warnings:** risk to people, health, data, money or access, and the step that avoids it.
2. **Destructive or irreversible actions:** before deleting data or files, force-pushing, rewriting history, running a data-dropping migration, deploying to production, sending messages, or anything involving payments or credentials, say what will happen, what cannot be undone, what the alternative is, and ask for explicit confirmation. A confirmation is never reduced to "OK?".
3. **Security findings:** what the issue is, where (file and line), its impact, severity, the fix and its verification status, as LaunchGuard reports them. Never print secrets, at any level.
4. **Errors and failures:** the exact error text (the lines that decide the cause), what failed, what you tried and the current state (what changed and what did not). Name the failing tests; never write "some tests failed".
5. **Verification status:** which commands and tests actually ran and their results, and which checks were not done (`NOT VERIFIED`). Lean output may put this in a table. It never drops it, nor the "what to double-check" items of a report (`../assets/review-template.md`).
6. **Legal, medical, financial and compliance caveats,** including disclaimers that another module or the project requires.
7. **Anything the user asked to see in full:** a whole file, log, diff, list or explanation. Give it in full, with secrets redacted.
8. **Questions for the user and choices you offer:** complete sentences that say what each option leads to, so the user can choose without guessing.
9. **Signs of confusion:** if the user repeats a question or misreads an answer, answer that point fully once.

**Scope:** lean output governs chat replies only. Anything you write into the repository or send elsewhere (code, comments, docs, commit messages, pull request descriptions, issues, emails) follows the project's own conventions. Leave existing comments in edited files as they are unless the task is to change them.

## Example

Question: "Why does `npm test` fail with `Cannot find module 'zod'`?"

| Level | Reply |
|---|---|
| 1 | `zod` is imported in `src/schema.ts` but missing from `package.json`, so a clean install never fetches it. Add it as a runtime dependency with `npm install zod`, then rerun `npm test`. |
| 2 | `zod` imported in `src/schema.ts`, missing from `package.json`. Fix: `npm install zod`, rerun `npm test`. |
| 3 | `npm install zod` |

Protected content at level 3. The request is "delete the stale branches, just do it":

> This deletes 14 local branches, and 3 of them (`spike-auth`, `old-billing`, `tmp-fix`) have commits that exist nowhere else. After `git branch -D`, those commits can be recovered only from the reflog, and only until Git garbage-collects them. Should I delete only the 11 merged branches, or all 14?

## Check before sending

1. Does the first line answer the question?
2. Does any sentence repeat another, or restate the question? Delete it.
3. Are every identifier, number, negation and condition still present and exact?
4. Was a protected item shortened? Restore it in full.
5. Could the user act on this reply without asking a follow-up question? If not, you cut too much: add back the missing piece.

## What brevity does and does not save

- Shorter replies cut output tokens and reading time. They do not shrink the input: the files read, tool output and conversation history, which usually cost the most in agent work. To spend less there, read less. Use targeted searches, read symbols at their line numbers, and use `codebase-map/GUIDE.md` with `--focus`.
- Where pricing is per request rather than per token, shorter replies do not change the cost.
- Do not quote savings figures. If cost matters, compare the usage the provider reports for the same task with and without lean output.

## Working with other ProductCraft modules

- `../assets/review-template.md`: at any level, fill the evidence rows compactly (a table is fine), but keep every row.
- `launchguard/GUIDE.md` and its reporting conventions: findings keep their full fields and statuses.
- `codebase-map/GUIDE.md`: report map findings as short tables with exact paths.
