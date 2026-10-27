# Documentation and decision records

Read this when you write or update a README, an architecture decision record (ADR), API reference, code comments, a changelog, a runbook or an agent instruction file (`AGENTS.md`, `CLAUDE.md`), when you draft a design doc, spec or proposal with the user, when the user asks what to improve in the project's setup after a session, or when a change makes existing documentation wrong.

Documentation earns its place by answering a question a reader will actually have. Write only what you have verified, and say plainly what you have not.

## Match the project first

Look for existing documentation conventions before writing: a `docs/` tree, an ADR folder and its numbering, a docs site generator, a changelog format, comment style for public APIs. Continue them. Do not introduce a second ADR scheme or a parallel docs folder.

## What kind of document is it?

Keep these four kinds apart; mixing them makes each one worse:

| Kind | Reader's question | Example |
|---|---|---|
| Tutorial | "Teach me from zero" | Getting started: clone to first running request |
| How-to guide | "How do I do this specific task?" | Rotate the signing key; add a new locale |
| Reference | "What exactly does this accept and return?" | API reference generated from the schema; CLI flags |
| Explanation | "Why is it built this way?" | Architecture overview; ADRs |

## README

A README lets a newcomer run, test and change the project without asking anyone.

- What the project is and who it is for, in two or three sentences.
- Prerequisites with versions (runtime, package manager, database, services).
- Setup from a clean clone, as commands in order: install, copy the example environment file, start dependencies, run migrations, start the app.
- How to run tests, lint, type check and build; the exact commands CI runs.
- Configuration: environment variable **names** with a description and an example placeholder value, never real values.
- Where to go next: architecture overview, ADRs, contributing guide, runbooks.
- **Verify it:** run the documented commands yourself, ideally in a clean checkout or container. Commands that fail in the README are worse than none.
- A repository about to go public also needs `LICENSE`, `SECURITY.md` and `CONTRIBUTING.md`; see `open-sourcing.md`.

## Architecture decision records

**Write one when** a decision is costly to reverse, there were real alternatives, and a future reader would otherwise wonder why. Typical cases: choosing a datastore, queue, framework or hosting platform; an integration style between services; a data ownership boundary; a deliberate deviation from the obvious approach; a constraint not visible in code (regulation, contractual latency, a customer requirement); an option rejected for non-obvious reasons that people will keep proposing.

**Skip it** for easily reversed choices, library picks that take an afternoon to swap, and decisions with no real alternative.

**Format.** Use the project's template if it has one; otherwise `../assets/adr-template.md`. Keep it short: one page is normal, one paragraph can be enough.

- Title stating the decision, a number continuing the existing sequence, date and status (proposed, accepted, superseded by ADR-NNNN, deprecated).
- Context: the forces at play, constraints and requirements, with numbers where they exist.
- Decision: what was chosen, stated so it can be checked against the code.
- Options considered, each with the main reason it lost.
- Consequences: what becomes easier, what becomes harder, follow-up work, and what would make you revisit the decision.

**Lifecycle.** An accepted ADR is not rewritten. When the decision changes, write a new ADR that supersedes it and update the old one's status line only. Link ADRs from the code or config where the decision bites (`// See docs/adr/0007-outbox-for-order-events.md`).

**Agents.** Read the ADRs in the area you are changing before proposing structural changes, and do not re-propose a rejected option unless the context in the ADR has changed. Draft ADRs for the user's review; do not mark one accepted on your own.

## Code comments

- Comment **why**, not what: the constraint, the invariant, the unit, the non-obvious consequence, the link to the issue or ADR. The code already says what it does.
- Document hazards where they bite: "must run before the first render", "amount is in minor units", "the provider sends this webhook twice".
- Public functions and types get API documentation in the language's convention (JSDoc or TSDoc, Python docstrings, Rustdoc, Godoc): purpose, parameters, return value, errors raised, and a short example for non-trivial APIs.

- Generate reference documentation and run its examples with the tool the project already uses (Sphinx or MkDocs with doctests, Go `Example` tests, rustdoc doctests, Javadoc or Dokka, .NET XML documentation, DocC, YARD); `../../stacks/GUIDE.md` lists the toolchain per stack.
- Delete commented-out code; version control keeps history.
- A `TODO` carries an owner or issue reference; otherwise do the work now or file the issue.

## API reference

- Generate reference documentation from the contract (OpenAPI, GraphQL SDL, protobuf, type declarations) rather than writing it twice.
- Include working examples for each operation, including an error example. Where tooling allows, test examples in CI (doctests, compiled snippets, recorded request examples validated against the schema).
- Document behavior the schema cannot express: rate limits, idempotency, pagination, ordering, retry guidance, deprecation dates.

## Changelog and release notes

- Write for consumers: what changed for them and what they must do. Group entries (for example Added, Changed, Deprecated, Removed, Fixed, Security) with the newest release on top.
- Add the entry in the same pull request as the change, while the impact is fresh.
- Breaking changes get a migration note; deprecations get their removal date.
- Generated notes from commit or PR titles are a draft to edit, not the final text.

## Agent instruction files

`AGENTS.md`, `CLAUDE.md` and similar files are loaded at the start of every session, so every line costs attention on every task.

- Keep them short and concrete: build, test, lint and run commands; conventions that are not obvious from the code; boundaries (what never to touch, what to ask about first).
- Point to deeper documents with a line that says when to read them ("Before changing the billing schema, read `docs/billing.md`"), instead of pasting them in.
- Keep them true: update them in the same change that changes a command or convention.
- Never put secrets, tokens or personal data in them.
- Record standing decisions the user made (for example "Use pnpm", "Do not add new runtime dependencies without asking") when the user agrees.

## Improving the setup after a session

When the user asks for a retrospective, or a session needed the same correction more than once, propose changes to the project's setup rather than to its code. Tie each proposal to something that happened in the session:

| What happened | Propose |
|---|---|
| A mistake a tool could have caught (a banned API, an import that crosses a boundary, a file in the wrong folder, a forgotten migration) | A lint rule, pre-commit hook or CI step in the tooling the project already uses, rather than a sentence of prose. First check whether such a check exists but is not wired into CI or fails silently |
| A judgment call that went wrong (layering, naming, how errors are reported) | One sentence in the coding standards or the agent instruction file, next to the related text |
| Information that took long to find | A one-line pointer in the agent instruction file, for example "Payment webhooks: `services/billing/webhooks/`; read `docs/billing.md` first" |
| Instructions the session shows were ignored or that restate defaults | Deleting them: every line is read on every task |
| Something the agent could not see (server logs, a local service, test data) | A read-only way to reach it, such as a log file the dev server writes or a seeded test database |

List each proposal with its evidence from the session and the exact text or configuration change. Apply only what the user approves, and never put secrets, personal data or one-off task details into instruction files.

## Domain vocabulary

When a project has domain terms that are easy to confuse (customer, account, user, member, tenant), keep one agreed word per concept and use it in code, APIs and docs. If the project keeps a glossary, update it when a term is introduced or sharpened; if it does not, suggest one only when confusion has actually caused problems.

## Runbooks and diagrams

- Runbooks for alerts and operational tasks live next to the code; their minimum content is in `observability.md`.
- Keep diagrams as text (for example Mermaid) next to the documents that use them, so they are reviewed and updated with the code. Draw the level the reader needs: system context, deployable parts, or internals of one part, not all at once.

- Choosing the diagram type, Mermaid syntax and its pitfalls, accessible titles and descriptions, and rendering checks are in `../../research-writing/references/diagrams-and-mermaid.md`.

## Design docs, specs and proposals written with the user

For a longer document the user will circulate (a design doc, spec, RFC or proposal):

1. **Gather before drafting.** Ask who will read it and which decision it serves. Then collect the material: invite the user to tell you everything relevant in any order, and read the linked issues, code and earlier documents as data. Turn conflicts between sources into questions.
2. **Agree the outline first.** Derive the sections from the questions readers will bring (the problem, the options, the proposal, cost, risk, rollout, open questions) or use the project's template. Confirm the outline before writing prose.
3. **Draft one section at a time,** starting with the one that carries the decision or the most uncertainty. List what it must say, draft it, and let the user correct it before moving on. Mark unknowns `[[OPEN: ...]]` instead of filling them with plausible guesses.
4. **Test it on a cold reader.** Give only the document to a fresh helper (or ask the user to send it to a colleague) together with the questions its readers will ask. Every question answered wrongly or not at all marks a gap. Check that each number and claim has a source.
5. **Final pass:** one term per concept (see "Domain vocabulary"), no sections that repeat or contradict each other, a summary at the top that matches the body, and every `[[OPEN]]` either resolved or listed at the end.


Documents outside engineering (articles, newsletters, status updates, research papers, grant proposals) use the same gather, outline, section-by-section and cold-reader method; `../../research-writing/GUIDE.md` adds source verification, citations and the formats for those documents.

## Writing style

- Plain language, short sentences, task-oriented headings, numbered steps for procedures.
- Real commands and paths that you ran; placeholders clearly marked (`<your-region>`).
- State limits and uncertainty; never upgrade "should" to "guarantees". Date time-sensitive statements.
- When editing someone else's text for clarity, keep every fact, number, condition and caveat, and check the edited version against the original.

## Checks (done when)

- [ ] Documentation affected by the change was updated in the same change.
- [ ] Every command in new or edited docs was run, or is marked as not run with the reason.
- [ ] A costly-to-reverse decision has an ADR draft for the user's review, following the project's existing scheme.
- [ ] Public APIs have reference docs with examples; comments explain why.
- [ ] No secrets or real environment values in docs or agent instruction files.

## Anti-patterns

- READMEs whose setup steps no longer work.
- Comments that restate the code; commented-out code; ownerless TODOs.
- Rewriting an accepted ADR instead of superseding it.
- Copying large documents into agent instruction files.
- Changelogs that are raw commit logs.
- Documentation that promises behavior nobody tested.
