# Product requirements documents and multi-step construction plans

Read this when a request is bigger than one change: a new product or feature whose problem and value are not yet settled (write a PRD), or work that will take several pull requests, sessions or people (write a construction plan). Turning an agreed feature into testable requirements and acceptance criteria is `requirements-and-acceptance.md`; planning a single change is `clarify-and-plan.md`; running a long plan with one fresh helper per step is `parallel-work.md`; tracking many threads on a board is `markdown-task-boards.md`.

The order is: PRD (why and what), then requirements and acceptance criteria (exactly what), then the construction plan (how, in which steps). Skip any stage whose answer is already obvious.

## Part 1: A problem-first PRD

Write one when someone needs to decide *whether* and *what* to build: a new product, a feature with several stakeholders, a bet that costs weeks. Do not write one for a change whose need is plain.

### Rules

- **Problem before solution.** The PRD says what must be true for success and why. Files, libraries, endpoints and task lists belong to the construction plan; if they appear, move them there.
- **Evidence or a label.** Every claim about users or the market is backed by evidence (quotes, support tickets, metrics, observed behavior, failed workarounds) or marked `Assumption: validate by <user interviews | analytics | prototype>`.
- **No invented numbers.** Targets come from the owner. Where none exists yet, write `TBD: needs <who or what>`.
- **No personal data.** Quote research participants anonymously; summarize tickets without names or contact details.

### Ask in three short rounds

Each round is one set of questions; wait for the answers before the next.

1. **Frame:** Who has the problem (a specific role in a specific situation)? What is the observable pain, described as behavior? Why do today's options not solve it? Why now?
2. **Ground:** What evidence shows the problem is real and worth solving? If there is none, the PRD records an assumption and how to test it.
3. **Decide:** The hypothesis, the smallest version that tests it, what is explicitly out of scope, and the open questions that could change the approach.

### Template

```markdown
# <Product or feature>

## Problem
<Two or three sentences: who has which problem, and what leaving it unsolved costs.>

## Evidence
- <quote, ticket summary, metric with its source and date>
- <or: Assumption: validate by <method>>

## Users
- Primary: <role, context, what triggers the need>
- Not for: <who is explicitly excluded, and why>

## Hypothesis
We believe <capability> will <change in behavior or outcome> for <users>.
We will know we are right when <metric> moves from <baseline> to <target> within <period>.

## Success metrics
| Metric | Baseline | Target | How and when measured |
|---|---|---|---|
| <primary> | <value or TBD> | <value or TBD> | <method> |
| Guardrail: <what must not get worse> | | | |

## Scope
- MVP: <the least that tests the hypothesis>
- Must / Should / Could: <capabilities, each with a one-line reason>
- Won't (this time): <item and why deferred>

## Milestones
| # | Outcome a user can see | Status | Plan |
|---|---|---|---|
| 1 | <outcome, not an engineering task> | pending | <link once planned> |

## Open questions
- [ ] <question that could change scope or approach, with owner and needed-by date>

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
```

### Check it before handing it on

- The problem is specific and evidenced, or clearly labeled as an assumption.
- The primary user is a role in a situation, not "users".
- The hypothesis can fail: it names a metric, a baseline, a target, a method and a period, plus at least one guardrail.
- Scope has an MVP and an explicit "won't" list.
- Milestones are outcomes a user would notice, not tasks.
- No implementation detail, and no number without a source or an assumption label.
- The owner has read it and agreed. Do not mark it approved yourself.

## Part 2: A construction plan for multi-step work

Write one when the work needs three or more pull requests, spans sessions, or will run in parallel streams. A single pull request needs only the plan in `clarify-and-plan.md`.

### Research first

Check `git status`, the default branch, the remote, how CI runs and what the project already has: existing plans, ADRs in the area, the codebase map (`../../codebase-map/GUIDE.md`). A plan built on a wrong picture of the repository is wrong in every step.

### Steps that a fresh executor can run cold

- **One pull request per step,** reviewable in one sitting, leaving the default branch green and deployable. Prefer thin vertical slices that work end to end over "all the backend first".
- **Each step is self-contained.** Someone with no access to the conversation, or to earlier steps' reasoning, can execute it from its brief alone.
- **Point, do not paste.** Name existing code to imitate by path and line range instead of copying it into the plan, so the plan does not go stale when that code moves.

```markdown
### Step 3: Server-side price recomputation
Depends on: 1, 2            Can run in parallel with: 4
Goal: the charge endpoint ignores client prices and recomputes the total from the catalog.
Read first: `api/checkout.py:40-95` (request flow), `pricing/rules.py` (discounts), ADR 0012.
Mirror: error handling as in `api/refunds.py:30-58`; tests laid out as in `tests/api/test_refunds.py`.
Change: `api/checkout.py`, `pricing/total.py` (new), `tests/api/test_checkout_total.py` (new).
Not in this step: coupon stacking (step 5), currency conversion (out of scope).
Tasks: 1. failing test for a tampered client price ... 4. remove the client-price read.
Verify: `pytest tests/api -q` all pass, 3 new tests; `ruff check .` clean.
Exit: AC-03 and AC-04 pass; no read of `request.json["price"]` remains (`git grep -n 'json\["price"\]'` is empty).
Rollback: revert the merge commit; no data change.
```

### Dependencies and parallel work

- Give every step a `Depends on` list. A step that uses an interface must come after the step that creates it, or the interface is fixed first in a small step of its own.
- Steps may run in parallel only if they share no files, no schema and no output; each then runs in its own worktree (`parallel-work.md`).
- When the graph is more than a line, draw it (a Mermaid `flowchart` next to the step list, `../../research-writing/references/diagrams-and-mermaid.md`).
- Put judgment-heavy steps (interfaces, schemas, security boundaries) with the strongest reviewer or a person; mechanical steps can go to a cheaper model or a junior contributor with a precise brief.

### Invariants checked after every step

List the few properties that must hold after each step, whoever executes it: the full test suite is green; the public API is unchanged unless the step says otherwise; no imports from the new core into the old adapters; migrations run forward and back on a copy. Each invariant has a command.

### Phase the work so something works early

1. The smallest end-to-end slice that delivers value.
2. The complete main path.
3. Edge cases, errors and polish.
4. Performance, monitoring and analytics.

Each phase ships on its own. Validation, authorization and data integrity belong in the slice that introduces the data path; they are never deferred to "polish".

## Review the plan before executing it

Give the plan and the repository, not the conversation, to a fresh reviewer (a helper or a person) and ask for findings against this list:

- Every requirement or milestone maps to a step; every step has a check that can run here.
- Dependencies are correct and complete; parallel steps really share nothing.
- Each step can merge on its own and keeps the default branch deployable.
- Risky or irreversible steps carry a rollback and wait for the owner's approval.
- No step says "TBD", "handle edge cases" or "add tests" without saying which.
- Names and signatures agree across steps.
- The plan is not longer than the code it describes.

Fix the findings that matter, then get an explicit verdict from the owner (approve, or request changes with comments anchored to the steps they concern) before the first large or irreversible step.

## Change the plan on purpose

Plans meet reality. Change them openly, with a dated line in a short plan log:

| Change | When | Record |
|---|---|---|
| Split | A step turned out too large for one review | New step ids; dependents updated |
| Insert | A missing prerequisite surfaced | Why it was missed; what now depends on it |
| Skip | The step is no longer needed | The reason and who agreed |
| Reorder | A dependency was discovered | The new order and why |
| Abandon | The premise proved wrong | What was learned; what happens to merged steps |

Never rewrite finished steps to match a new plan: they link to their merged commits or pull requests and stay as they were. After a context reset, trust the plan log and `git log` over memory.

## Done when

- [ ] A PRD, if one was needed, states the problem with evidence or labeled assumptions, a falsifiable hypothesis with metrics, and a bounded scope, and the owner agreed to it.
- [ ] Each step of the construction plan has a self-contained brief, dependencies, a verification command, exit criteria and a rollback.
- [ ] A fresh reviewer checked the plan, and the owner approved it before the first irreversible step.
- [ ] Changes to the plan are logged with their reasons; finished steps link to their commits.

## Anti-patterns

- A PRD full of file names and task lists, or a plan that re-argues the product case.
- "Users want this" with no evidence and no assumption label; targets invented to fill the table.
- Steps that only work once every other step has landed.
- Briefs that say "see the discussion above".
- A plan silently rewritten after half the steps have shipped.
