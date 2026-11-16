# Session brief: frame every coding session before the first edit

Read this when starting work with a coding agent on a repository, especially when sessions keep producing rework: code in the wrong style, guessed requirements, sweeping rewrites, or a big diff to throw away. A short brief, written once and kept in the repository, sets four things before any code is touched:

- the role the agent plays;
- the project facts it needs;
- the rules it follows;
- the shape of what it hands back.

It complements:

- [clarify-and-plan.md](clarify-and-plan.md), on how to plan;
- [delegating-to-coding-agents.md](delegating-to-coding-agents.md), on briefs for hosted, unsupervised agents;
- `../../builder-tools/references/agent-config-linting.md`, on checking the instruction file itself.

## The four parts

Keep each part to one or two lines. A brief that grows past a screen stops being read, by people and by agents.

| Part | What it says | Weak version | Strong version |
|---|---|---|---|
| **Role** | Who the agent is on *this* codebase | "You are a helpful assistant" | "You are a senior engineer who maintains this service and owns its quality" |
| **Context** | The facts a newcomer would otherwise guess | "It's a web app" | Stack and versions, where code lives (`src/api`, `src/web`, `migrations/`), how to run tests, the house conventions |
| **Rules** | How to behave when unsure | "Be careful" | "Ask before assuming. Plan before code. Touch only what the task needs. Never weaken a test to pass it" |
| **Output** | What a finished answer looks like | "Fix it" | "A small diff I can review, with the commands you ran and their results; no unrelated rewrites" |

## Why the rules matter most

**Plan first.** A plan is a few lines that name the files to change, the approach, the risks and the checks. Correcting a plan takes seconds. Unwinding a few hundred lines written on a wrong assumption takes an hour, and some of the damage (deleted tests, renamed APIs) is easy to miss. Ask for the plan, read it, fix it, and only then let the agent write code. For a one-line, obvious change, skip the plan; the brief should say so, or every typo fix becomes a ceremony.

**Ask, don't assume.** Models fill gaps with confident guesses by default. One precise question, asked before the work starts, costs less than any of those guesses. Good questions name the options and a default: "Should the export include archived rows? I'll exclude them unless you say otherwise." Search the code before asking; never ask what the repository already answers.

**A reviewable diff, not a rewrite.** Small, scoped changes can be read, tested and reverted. A rewrite hides its mistakes in its size. Ask for the smallest change that does the job, and a list of anything left for later.

## Keep it in a file, not in your memory

Pasting a brief from memory drifts: lines get dropped, and every session behaves a little differently. Put the brief in the instruction file the agent reads automatically at the start of each session:

- `CLAUDE.md` for Claude Code;
- `AGENTS.md` for agents that read that convention;
- the repository's equivalent for other tools.

The same rules then apply to every session and every teammate, and changes to them go through review like code.

- Start from [the template](../assets/session-brief.template.md) and fill in real facts. A placeholder left in the file is worse than no line at all.
- Keep facts true: when the stack, layout or test command changes, update the file in the same pull request.
- Keep it short and specific. Put long references (architecture notes, API conventions) in their own documents and link them from the brief.
- Never put secrets, tokens or personal data in it; the file is committed and read by tools.
- Check it with `../../builder-tools/references/agent-config-linting.md` when it grows or when several instruction files overlap.

## Using it in a session

1. The agent reads the brief (automatic when it lives in the instruction file).
2. State the task in one or two sentences, with the outcome and how you will know it is done.
3. The agent asks its questions, if any, and proposes a plan.
4. You correct the plan; it implements the smallest diff.
5. It reports the checks it ran and their results. You review the diff before merging.

## Signs the brief needs work

- The same correction comes up in more than one session: turn it into a rule ("Use the existing `Money` type for amounts").
- The agent asks something the repository could answer: add that fact to Context.
- Diffs keep touching unrelated files: tighten Output ("only files the plan names").
- Plans are skipped on risky work: say which changes always need a plan (migrations, auth, money, public APIs).

## Done when

- [ ] The repository has an instruction file with Role, Context, Rules and Output, each filled with true, specific facts and no placeholders.
- [ ] Rules include "ask before assuming" and "plan before code", with a stated exception for trivial edits.
- [ ] Output asks for a reviewable diff plus the checks run, and no unrelated rewrites.
- [ ] The file holds no secrets, and changes to it go through review.
