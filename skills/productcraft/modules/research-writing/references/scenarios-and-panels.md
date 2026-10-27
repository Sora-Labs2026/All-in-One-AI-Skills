# What-if scenarios and multi-perspective panels

Read this when the user asks "what if...", wants best, likely and worst cases, contingency plans or strategic options under uncertainty, or wants a question examined from several viewpoints ("how would different people see this", "give me a panel or board discussion"). Attacking a single plan is in `stress-tests.md`.

Both techniques organize judgment; they do not predict. Say so in the output, and keep numbers you did not compute out of it.

## What-if scenario branches

### 1. Sharpen the question

A vague question ("what if things go wrong?") produces vague branches. Pin down:

- **The change:** one variable at a time (a supplier raises prices, a key person leaves, a regulation passes, demand drops).
- **The size:** by how much (a 30 % price rise, not "a price rise").
- **The time frame:** over what period, and when it would be visible.
- **The baseline:** the current state the change acts on (revenue, runway, team, contracts, architecture).

Show the sharpened question to the user and agree on it before branching.

### 2. Map the branches

Four to six branches usually cover the space. Pick the ones that fit:

| Branch | Definition | Why include it |
|---|---|---|
| Expected | The most plausible path given current evidence | Anchors planning |
| Upside | Key assumptions hold and some luck arrives | Shows what to be ready to exploit |
| Downside | Key assumptions fail, two problems arrive together | Sets the floor; tests resilience |
| Surprise driver | A factor nobody is tracking enters (a new entrant, a supply shock, a legal change) | Tests robustness to the unexpected |
| Consensus wrong | The common view turns out to be false | Exposes shared assumptions |
| Knock-on | First-order effects trigger second- and third-order ones | Finds cascades and feedback loops |

For each branch write:

- **Story:** three to five sentences on how it unfolds, step by step.
- **What must be true:** the assumptions behind it.
- **Signposts:** observable early signals that this branch is happening, with where to look.
- **Consequences:** immediate, within a month, within six months (adjust the horizons to the question).
- **Response:** what to do if the signposts appear.

### 3. Likelihood without fake precision

Rate each branch as more or less likely with the reason. If the user wants numbers, give ranges and say they are judgments. Probabilities only need to sum to 100 % when the branches are mutually exclusive and exhaustive, which hand-made branches rarely are. When the question is quantitative and data exist, build a model instead: a sensitivity table or tornado chart over the uncertain inputs, a break-even point, or a Monte Carlo simulation, kept as code with every assumption labeled (`../../data-engineering/GUIDE.md`, `../../ml-engineering/GUIDE.md`).

### 4. Synthesize into decisions

- **No-regret moves:** actions that help in most branches. Do these now.
- **Hedges:** cheap protections against the worst branches that cost little upside.
- **Options:** small investments that keep a choice open (a second supplier qualified, a feature flag, a pilot contract).
- **Triggers:** decision rules agreed in advance ("if two signposts of the downside appear in one quarter, we pause hiring").
- **What we would watch:** the signpost list with an owner and a review date.

### Variants

- **Branch within a branch:** take one branch and run the method again inside it, only when the stakes justify the depth.
- **Backcasting:** start from a desired end state and work backward: what must be true at each earlier point, and what is the first step?
- **Stakeholder view:** run the same change from several parties' positions (your organization, a competitor, customers, a regulator); differences reveal moves and counter-moves.

### Scenario planning for strategy

For long-range strategy, choose two driving forces that are both high-impact and highly uncertain and independent of each other; their extremes form a 2 by 2 grid of four worlds. Describe each world, then test the current strategy in each ("wind-tunnelling"): where does it break, and what would make it robust across all four? Avoid naming one world "the plan"; the point is preparing for several.

## Multi-perspective panels

A panel simulates the questions different stakeholders or thinking styles would raise. It is a way to generate considerations a single frame misses, not a substitute for asking real people. For consequential decisions, recommend checking the panel's main points with the actual stakeholders.

### Choose the lenses

Pick three to six lenses whose priorities genuinely conflict for this question. Agreement among lenses chosen to agree is worthless.

| Lens | Asks | Typical blind spot |
|---|---|---|
| End user or customer | Does this make my task easier, today? | Long-term cost and maintainability |
| Operator or on-call engineer | What pages me at 3 am? How do we roll back? | User value of new features |
| Finance | What does it cost, when does it pay back, what is the downside exposure? | Hard-to-quantify benefits |
| Security and privacy | What can be abused, leaked or misused? | Usability and speed |
| Legal and compliance | Which obligations apply; what must be documented? | Business opportunity |
| Long-term maintainer or architect | What does this commit us to in three years? | Present deadlines |
| Skeptic | What if the opposite of the popular view is true? | Can oppose by reflex |
| Newcomer or outsider | Why does everyone assume that? | Lacks domain depth |
| Ethicist | Who benefits, who bears the cost, who was not asked? | Can stall action |
| Pragmatist | What can we actually do with this team by next month? | Sacrifices the long term |

Suggested sets: product decisions (user, operator, finance, skeptic); architecture (operator, maintainer, security, pragmatist); people decisions (affected employee, manager, fairness, legal); research directions (domain expert, methodologist, funder, outsider).

Use role lenses, not real named people. Do not put words in the mouths of real individuals or caricature groups.

### Run the panel

1. State the question and the decision it serves.
2. Each lens gives: its position in one sentence, the reasoning in two to four sentences, the risk it sees that others may miss, and what would change its mind.
3. Require real disagreement: every lens must dispute at least one other on substance. If they all agree, the lenses were badly chosen or the question is settled; say which.
4. Optionally run a second round in which lenses respond to each other's strongest point.
5. Keep each voice short and distinct.

### Synthesize

- **Convergence:** points most lenses accept; these are the safest conclusions.
- **Core tension:** the real trade-off the disagreement reveals, stated plainly. This is usually the most useful line in the output.
- **Blind spot:** what no lens raised.
- **Recommendation:** a path that respects the tension (often a staged or conditional choice), with confidence in words and the reason.
- **Open question:** the one question the user should answer, or ask real stakeholders, before deciding.

If the question is factual, trivial or already decided, say so and offer a short two-sided contrast instead of a full panel.

## Checks (done when)

- [ ] The what-if question names one change, its size, its time frame and the baseline, agreed with the user.
- [ ] Each branch has a story, assumptions, signposts, consequences and a response.
- [ ] Likelihoods are qualitative or defended ranges; any numbers come from a model kept as code.
- [ ] The synthesis lists no-regret moves, hedges, options and triggers.
- [ ] Panel lenses conflict, are roles rather than real people, and the synthesis names the core tension and the open question.
- [ ] The output says it is structured judgment, and recommends real-stakeholder checks for consequential decisions.
