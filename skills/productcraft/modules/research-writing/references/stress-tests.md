# Stress tests for plans and decisions: devil's advocate, assumption audit, pre-mortem, red team

Read this when the user asks to challenge a plan, decision, proposal, strategy, design or argument: "poke holes in this", "play devil's advocate", "what could go wrong", "red-team this", "test my assumptions", "is this a good idea". Branching what-if scenarios and multi-perspective panels are in `scenarios-and-panels.md`; auditing the evidence behind a claim is in `critical-thinking-and-bias.md`.

These are established decision-review techniques. Their value comes from structure: they make people look for failure on purpose, which optimism and momentum otherwise prevent.

## Pick the technique

| Situation or phrasing | Technique | What the user gets |
|---|---|---|
| "Is this the right approach?", early idea, vague consensus | Assumption audit | The assumptions it rests on, ranked by risk, and the cheapest test of the riskiest |
| "We're about to commit to X", a choice between options | Devil's advocate (strongest counter-case) | The best argument against, the real trade-off, a revised position |
| "What could go wrong?", a plan with a launch or deadline | Pre-mortem | Ranked failure stories, early warning signs, mitigations |
| "Could someone abuse or game this?", incentives, security, competition | Red team | Adversaries, attack paths, perverse incentives, defenses |
| "The data shows...", "studies say..." | Evidence audit (`critical-thinking-and-bias.md`) | Claims, how each could be falsified, evidence strength |
| High stakes and time allows | Two in sequence: assumptions, then devil's advocate; or pre-mortem, then red team | Broader coverage |

If the user does not say which they want, propose one with a one-line reason and let them choose.

## Rules for every stress test

1. **Steelman first.** Restate the user's position in its strongest form, including the best evidence for it, and ask whether that is fair. Attacking a weaker version wastes everyone's time.
2. **Depth over volume.** Present the three to five strongest challenges, ranked. A long list of small objections creates a false impression of weakness.
3. **Be concrete.** Name the mechanism, the number, the actor and the trigger. "It might not scale" is not a challenge; "at 3,000 concurrent sessions the single queue consumer falls behind and checkout times out" is.
4. **Concede what holds.** Say plainly which parts survived the challenge.
5. **No fake precision.** Rate likelihood and impact as high, medium or low with a reason, or give ranges you can defend. Invented percentages are worse than none.
6. **Respect expertise.** Do not override the user's domain facts with generic skepticism; ask where the facts are uncertain.
7. **End with something usable:** a changed plan, a test to run, a decision rule or an explicit trade-off. The user decides; stop after the synthesis unless asked for another pass.

## Assumption audit

1. List the assumptions, stated and unstated. Phrases that hide them: "obviously", "users want", "it's simple", "we always", "there's no other way", "the standard approach".
2. For each, rate confidence (how sure are we, and based on what) and impact (what breaks if it is false).
3. Probe the high-impact, low-confidence ones with questions of five kinds: definition ("what exactly does 'real-time' mean here?"), evidence ("what shows customers want this?"), logic ("does adding the cache necessarily help the slow path?"), perspective ("how does the on-call engineer see this?"), consequence ("what becomes harder later?").
4. Propose the cheapest test for the riskiest assumption: a prototype, five customer calls, a load test, a query against existing data.

Output: an assumption table (assumption, stated or not, confidence, impact, test), then the questions grouped by theme.

## Devil's advocate: the strongest counter-case

1. Steelman the thesis (above).
2. Build the strongest opposing case a well-informed person would make. Good sources: the hidden cost (migration, training, operations), a cheaper option that solves most of the same problem, precedent from similar attempts, the stakeholder the plan does not serve, irreversibility, timing.
3. Lay out where thesis and counter-case genuinely conflict (speed against maintainability, cost now against cost later) and where they only seem to.
4. Propose a synthesis, if one exists:
   - **Conditional:** X when condition A holds, Y when B holds.
   - **Split scope:** X for this part, Y for that one.
   - **Staged:** start with X, switch to Y when a named trigger occurs.
   - **Proceed with safeguards:** X, with a specific hedge taken from the counter-case.
5. Give a verdict in one of four forms: proceed; proceed with these changes; test this first; reconsider, because the counter-case is stronger. "It depends" is only acceptable with the exact conditions named.

## Pre-mortem

1. **Set the scene:** "It is [date, after the outcome would be clear]. This failed unmistakably." Failure as a given frees people to name causes they would otherwise soften.
2. **Generate failure stories independently.** With a group, each person writes their own before any discussion, to avoid anchoring on the first idea. Alone, generate across categories: people (key person leaves, no buy-in), process (no rollback, big-bang release), technology (untested at scale, hidden dependency), data (migration loses records, quality unknown), market or users (nobody adopts, a competitor moves first), timeline (external dependency slips), money (operating cost underestimated).
3. **Make each story specific:** trigger, chain of events, how and when it was detected, the consequence, and the assumption that turned out false.
4. **Follow consequences two steps:** first-order effect, then what that causes (the slip extends the overlap with the old system, which doubles running costs, which triggers a budget review).
5. **Rank** by likelihood and impact, each high, medium or low, with the reason.
6. **Early warning signs:** for the top failures, an observable signal, who watches it and how often ("support tickets mentioning import errors above 20 a week, product lead, weekly").
7. **Mitigations** that prevent, detect sooner, or limit the damage, each with an owner and an effort estimate.
8. **Inversion check:** what would guarantee failure? Does any of it exist today (no rollback plan, no success metric, one person who understands the system)?

## Red team

1. **Define the asset and the adversary's goal:** what is being protected (a system, a pricing scheme, a policy, a negotiation position, a dataset) and what would winning look like for an attacker.
2. **Profile adversaries,** each with motivation, capability, existing access and constraints. Look beyond attackers: competitors, users gaming incentives, careless insiders, partners with diverging interests, regulators, critics who will read the plan uncharitably.
3. **Map attack paths** as a tree from the goal down to concrete steps, and rank them by likelihood and impact.
4. **Look for perverse incentives:** what behaviour does the plan reward that nobody wants? What is the cheapest way to get the reward without the intended effort? What gets sacrificed when this metric becomes a target?
5. **Defenses:** for the top paths, specific countermeasures with effort and priority, plus how you would notice an attempt.

For software, route the security part through `../../code-security-review/references/threat-modeling.md` and the controls in `../../launchguard/references/security-baseline.md`; this reference covers the plan-level view. Red-team plans and systems the user owns or is responsible for. Do not produce step-by-step operational instructions for harming third parties.

## Output shape

```markdown
## Position as understood
<steelmanned restatement; confirmed by the user: yes/no>

## Strongest challenges (ranked)
1. <challenge> - likelihood/impact: <H/M/L, reason> - evidence or mechanism
2. ...

## What holds up
- ...

## Recommended changes or tests
| Change or test | Addresses | Effort | Owner |

## Verdict
<proceed / proceed with changes / test first / reconsider>, and the decision rule or trigger to revisit
```

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Disagreeing for its own sake | Every challenge names a mechanism and a consequence |
| False balance ("both sides have a point") | Say which side is stronger, or name the condition that decides it |
| A synthesis that is just "do both" | Name the trade-off it resolves and what it gives up |
| Scary but impossible scenarios | Each failure story must be plausible with today's facts |
| Percentages pulled from the air | Qualitative ratings with reasons, or defended ranges |
| Leaving a pile of problems | End with changes, tests and a verdict |

## Checks (done when)

- [ ] The position was steelmanned and confirmed before challenging.
- [ ] Three to five ranked, concrete challenges, with what holds up stated.
- [ ] Ratings are qualitative with reasons; no invented probabilities.
- [ ] The output ends with changes or tests, owners, and a verdict or decision rule.
