# Verification patterns: self-checks, independent judges, reviewer pairs and councils

Read this when an agent's output must be checked by agents before a person sees it or before it ships: a self-check at the end of a task, a generator and evaluator loop, two independent reviewers gating content, or several models consulted on a decision. Each pattern helps only when used for what it can actually do. None of them replaces deterministic checks (tests, builds, schema validation) or a person's sign-off on consequential work.

## The order of evidence

1. **Deterministic checks** run first: tests, builds, type checks, linters, schema and diff checks, reconciliation against external totals. They are cheap and do not share the model's blind spots.
2. **Independent model review** for what code cannot check: factual accuracy against sources, completeness against a spec, policy and tone, design quality.
3. **Human review** for calibration, for anything consequential, and for final acceptance.

A model's verdict is a claim. Treat it like a colleague's review comment: useful, and checked before it is trusted.

## Self-checks: useful as a checklist, weak as a score

Asking the agent that did the work to grade it catches omissions, but models rate their own work generously and share their own blind spots.

Use a self-check like this:

- **Against the request, item by item:** list every explicit requirement and mark each done, not done or out of scope, with where it is satisfied.
- **Against evidence:** every claim of "works" or "passes" cites a command that ran and its result. A claim without a tool result is downgraded to "not verified". If the claim contradicts the tool output, the tool output wins.
- **Find gaps, not grades:** ask "what would the user find missing or wrong?" and fix what can be fixed now; report the rest.
- **Judge the delivered output,** not the effort or the path taken, and only against what was asked; do not penalize the absence of features nobody requested.

Do not gate releases or loops on a self-assigned score, and do not average 1-to-5 scores into a quality number. If the end-of-task report needs a structure, use the reporting format of `../../engineering-workflow/GUIDE.md`: what changed, what ran, what was not verified.

## Generator and evaluator

Separate the agent that produces from the agent that judges. A judge with its own context and a strict brief is easier to make rigorous than a generator that grades itself.

- **The evaluator tests the real thing:** runs the application, clicks through flows in a browser, calls the API, runs the test suite. Reading the code or a screenshot is a weaker mode; if the evaluator could not use its intended tools, it says which mode it actually used, and the report shows the downgrade.
- **The rubric is written before the build** with concrete pass conditions per criterion, and the generator may not edit it.
- **The evaluator critiques; the generator fixes.** An evaluator that proposes fixes and then grades its own fixes is grading itself.
- **Feedback passes as a file** with specific findings (what, where, how to reproduce), and the generator addresses each one or says why not.
- **Stop on a plateau.** Cap the rounds, and stop early when the score or the failing-check count has not improved for two or three rounds; hand over to a person with the last feedback.
- **Expect cost.** Each round costs a full build plus a full evaluation. Measure cost per round in a pilot and agree the budget first (`autonomous-loops.md`).

Fuzzy criteria such as "originality" or "polish" produce noisy scores. Prefer checkable criteria (all flows in the spec work, no console errors, layouts hold at the agreed widths, the accessibility checks pass) and keep taste judgments for a person.

## Two independent reviewers

For output that will be published or acted on without further human review (documentation, customer-facing copy, generated code in a batch), two reviewers with separate contexts can catch more than one.

- **Same inputs, same rubric, no shared context:** each reviewer gets the spec, the output and the rubric, and nothing about the other's review. Fresh contexts every round, so earlier rounds do not anchor them.
- **Structured verdicts:** per criterion, pass or fail with a cited location and reason, plus blocking issues and non-blocking suggestions, as JSON.
- **Verify the findings.** A flag from one reviewer is a lead, not a proven defect: check it against the source, the spec or a test. Drop flags that do not hold, and keep a note of reviewer false positives; many false flags mean the rubric is vague.
- **The gate:** ship only when both reviewers pass and every verified blocking issue is fixed. After fixes, both reviewers re-run on the new version.
- **Cap the rounds** (two or three) and escalate to a person with the open issues. Endless fix rounds usually mean a vague rubric or a spec problem.
- **Know the limit:** two instances of the same model share training and blind spots, so their agreement is weaker evidence than two people agreeing. Use a different model family for one reviewer where data policy allows, and keep human spot checks for high-stakes output.
- **Run deterministic checks first;** never spend reviewer calls on output that fails to build.

### Large batches

Reviewing every item of a large generated batch may be too expensive. Review a random sample, classify the failures, fix the cause across the whole batch, then draw a fresh sample. Be honest about what a clean sample proves: with zero failures in n randomly sampled items, the 95% upper bound on the batch failure rate is roughly 3/n (about 10% for 30 items). For low tolerance, sample more or review everything.

## Councils for decisions

When the question is a decision under uncertainty (ship now or hold, build or buy, which architecture), not whether an output is correct, several independent perspectives can surface trade-offs.

- **State the decision precisely:** what is being decided, the constraints, what success means. Ask one clarifying question if it is vague.
- **Write your own position first,** with reasons and its main risk, before reading the others, so the synthesis does not just echo them.
- **Brief each voice separately** with only the question and the relevant facts, not the whole conversation, and a distinct lens (challenge the premise, optimize for delivery, look for failure modes). Ask for a position, reasons, the biggest risk, and one thing the others may miss, in a bounded length.
- **Synthesize without hiding dissent:** show each position, where they agree, the strongest disagreement, whether the premise was challenged, and say explicitly if a voice changed your recommendation. Do not average conflicting views into a diplomatic middle.
- **The user decides.** A council recommends; it does not approve anything.
- **Persist only what changes something:** record a decision in the project's ADR or tracker when it is durable (`../../engineering-practices/references/docs-and-decisions.md`), not as a running log of every council.

### Bringing in another provider's model

- **Ask first.** Sending context to another provider is a data transfer. Show or summarize the exact packet and get a yes for that packet. Redact secrets and anything personal, proprietary or regulated unless the owner approved that specific transfer.
- **Send the minimum:** the question, the positions and the draft, marked as untrusted data, never repository files or the full history.
- **Run the reviewer without tools:** no shell, no file access, no web, no inherited plugins or servers, in an empty temporary directory, with a size limit and a timeout.
- **Label the relationship honestly:** a second instance from the same provider is not a cross-provider review. If the external call fails, write "external review absent" with the reason; never substitute another model silently or imply that a review happened.
- **Quote the external critique verbatim** next to your synthesis, and explain any change it caused.

A model that only reads and comments is the safe default for any outside reviewer: one agent writes; the others advise.

## Repeated attempts are not proof

Running the same prompt many times and taking the majority, or asking the model to reconsider until it is confident, measures consistency, not correctness. Use repeats to estimate reliability (`agent-evals.md`). For anything consequential (money, production changes, migrations), confidence from repeated rollouts is never approval: stay in dry-run, preview or paper mode until checks pass and the owner approves the live step.

## Done when

- [ ] Deterministic checks ran before any model review.
- [ ] No release or loop gate depends on a self-assigned score.
- [ ] Judges and reviewers have separate contexts, written rubrics with checkable criteria, and verified findings.
- [ ] Fix rounds are capped with escalation to a person.
- [ ] Councils show dissent, and the user made the decision.
- [ ] Any transfer to another provider had explicit consent, minimal content and a tool-less reviewer, and the report labels it accurately.
