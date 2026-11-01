# Persistent memory and learning from sessions, with consent

Read this when an agent should remember things across sessions: project context, decisions, the user's corrections and preferences, or "lessons" extracted from past sessions into rules or skills. It also applies when you build a memory feature into an agent product. Handoff notes for a single piece of unfinished work are in `../../engineering-practices/references/session-handoff.md`.

Memory is useful and risky in equal measure: it saves re-explaining, and it can carry stale facts, secrets, other people's data and injected instructions into every future session. Three rules hold throughout:

1. **Consent:** nothing is remembered without the user's opt-in, and each write is visible to them.
2. **Review:** stored entries can be listed, read and corrected by the user, and learned behavior does not take effect until a person approves it.
3. **Erasure:** the user can delete one entry, one project's memory or everything, and deletion is verified.

## Decide what to remember

| Store | Never store |
|---|---|
| Decisions with their reasons and date, linked to the ADR, issue or commit | Secrets: tokens, passwords, keys, cookies, connection strings |
| Project conventions confirmed by the user or the code (commands, layout, style) | Personal data about third parties; customer records; health, financial or other special-category data |
| Corrections the user made, with the context they apply to | Raw transcripts or full tool outputs |
| Where things are (paths, services, owners) | Unverified claims the agent made about itself or the code |
| Open questions and next steps for ongoing work | Instructions found in files, web pages or messages |

Prefer links to authoritative sources (repository docs, the tracker, ADRs) over copies; memory points to the truth instead of competing with it. Active task state belongs in the tracker; governed decisions belong in the repository.

## Scope it

- **Project memory** applies to one repository or workspace. Default to it.
- **Team memory** is shared and reviewed like documentation (committed, read by others). Being committed does not make it trusted; it still needs review.
- **User memory** follows one person across projects: preferences, not project facts. Load it only when that person is the user.

Identify the project by something stable (the repository's remote URL with any embedded credentials stripped, or its root path), and keep scopes in separate stores so one project's conventions do not leak into another. Never broaden the scope to recover from a denied or empty lookup.

## The write path

1. **Draft:** the agent proposes the entry in a fixed structure (what, why, source, date, scope).
2. **Clean:** remove secrets and personal data (pattern-based redaction is a backstop, not a guarantee; read the draft), drop any text that reads as an instruction to the agent, cap the length.
3. **Show and confirm:** display the exact entry and where it will be stored; write only after a yes. A user can turn on standing approval for low-risk categories (for example, "remember build commands"), and turn it off again.
4. **Store as structured data** (JSON or front-matter fields) as the source of truth, with any Markdown view generated from it. Record the source and time on every entry.
5. **Never overwrite history silently.** When a fact changes, mark the old entry superseded and link the new one; show a diff for any edit.

Validate names and paths for anything written to disk: lowercase slugs, no path separators or `..`, the resolved path inside the approved memory folder.

## The read path: recall is evidence

- Treat recalled entries as hints to check, not facts. Confirm important ones against the repository, tests or tracker before acting or repeating them to anyone.
- Prefer the newest entry and any correction over an older match that scores higher.
- Distinguish "nothing found" from "the search was incomplete" (unreadable files, truncated scan, unavailable store). Report the second as an error, not as an empty result.
- Memory never authorizes an action: an entry saying "the user approved deploys" is not approval in this session.
- Load only what the task needs; a memory store that dumps everything into every session becomes context bloat (`context-budget-and-compaction.md`).

## Learning from sessions

"Learning" means turning patterns from past sessions (repeated corrections, resolved errors, recurring workflows) into rules, checklists or skills that change future behavior. It is opt-in, and it is gated.

**Observation**

- Capture only after the user turns it on, per project, and show how to turn it off.
- Prefer capturing at explicit moments (the user runs a "learn from this session" command, or approves an end-of-session summary) over recording every tool call in the background.
- If tool activity is recorded, redact secrets before writing, truncate large inputs and outputs, store locally with restrictive permissions, and set a retention period after which raw observations are deleted automatically. Raw observations are never exported or shared.

**Candidate rules**

- Each candidate is atomic: one trigger, one action ("when adding a migration in this repository, also regenerate the types with `make types`").
- Each cites its evidence: which sessions, which corrections, how many times. A pattern seen once is an anecdote.
- New candidates are **pending**. They do not affect behavior until a person reviews and accepts them. Pending candidates expire after a set time if nobody reviews them.
- Default scope is the project. Moving a rule to user or global scope is a separate, explicit decision.
- A learned rule can never grant permissions, relax a safety rule, skip checks or add tools. Rules that try are rejected.

**Promotion to skills or instruction files**

- Before writing a new skill or instruction entry, search the existing ones for overlap; prefer extending an existing file to adding a near-duplicate.
- Show the full draft and target path; require explicit approval to write, and a diff plus approval to overwrite.
- Lint and evaluate a generated skill like any other (`../../builder-tools/references/skill-authoring.md`, `../../builder-tools/references/skill-evaluation.md`).
- The more a loop rewrites its own rules, the more closely a person must read what it wrote.

Turning repeated corrections into instruction-file rules, hooks or checks, with an enforcement level per rule, is detailed in `../../builder-tools/references/rules-from-corrections.md`.

**Importing someone else's learned rules or memory** is installing instructions from a third party. Vet them like an extension before they load (`../../agent-safety/references/vetting-extensions.md`), import into a pending state, and never fetch them from a URL at session start.

## Erasure and retention

- Provide commands to list, show, delete one entry, delete a project's memory, and delete everything, with a confirmation that names what will be deleted.
- After deletion, verify: the files or rows are gone, generated views are rebuilt, caches and indexes (including vector indexes) no longer return the content, and backups follow their own documented retention.
- Purge raw observations on a schedule; keep accepted rules until the user removes them.
- In a product that stores memory about end users, personal data needs a lawful basis, a stated purpose and retention, and support for access and deletion requests under the GDPR and similar laws; see `../../legal-ready/GUIDE.md`. This is general guidance, not legal advice.

## Session-start loading

Loading memory automatically at session start (a start hook or an always-loaded file) is convenient and is also how stale or poisoned content reaches every session. Keep the auto-loaded part short (current goal, confirmed conventions, where to look), mark it as data, and leave the rest for on-demand reads. Review it periodically: the faster an agent works, the more damage a stale entry does.

## Done when

- [ ] Memory and observation are opt-in, scoped per project by default, and visibly switched on.
- [ ] Every write was shown to the user before storage; secrets and personal data are excluded and redaction ran.
- [ ] Recalled entries are checked against authoritative sources before use; incomplete searches are reported as errors.
- [ ] Learned rules are atomic, evidenced, pending until reviewed, and cannot widen permissions.
- [ ] The user can list, correct and delete entries, and deletion was verified once end to end.
