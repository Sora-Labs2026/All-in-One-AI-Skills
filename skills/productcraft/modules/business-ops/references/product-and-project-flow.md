# Product lenses, capability contracts and project flow

Read this when the task is deciding whether something is worth building, choosing between features, auditing how fast a new user gets value, turning product intent into a contract engineering can build against, or keeping a public tracker and an internal one in step. Requirements workshops and acceptance criteria are `../../engineering-workflow/references/requirements-and-acceptance.md`; design docs and ADRs are `../../engineering-practices/references/docs-and-decisions.md`; issue and pull-request triage is `../../engineering-practices/references/repository-hygiene.md`; tracker APIs are `../../integrations/references/work-tracking-and-wikis.md`; stress-testing a plan is `../../research-writing/references/stress-tests.md`.

## Ground rules

- **Do not invent product truth.** Users, usage numbers, revenue, customer quotes and business rules come from the owner or from data; unknowns are listed as open questions.
- **The owner decides.** Lenses and scores inform a decision; they do not make it.
- **Evidence over opinion.** Journey audits are run, timed and recorded; retention and usage claims cite the query or dashboard and its date.

## Product lens: should we build this?

Ask, one at a time, and write the answers into a short product brief:

1. Who exactly is it for? A specific person in a specific situation, not "developers".
2. What is the pain, how often does it occur, how bad is it, and what do they do today?
3. Why now? What changed that makes it possible or necessary?
4. What is the smallest thing that would prove or disprove the idea (the minimum viable test)?
5. What are we explicitly not building (anti-goals)?
6. How will we know it works: which metric, by when, compared with what baseline?
7. What would make us stop?

End the brief with a recommendation (build, test first, do not build), the risks, and what evidence would change the recommendation.

```markdown
# Product brief: [name]   (as of [date], owner [name])
For:            [person and situation]
Pain:           [frequency, severity, current workaround; source]
Why now:        [what changed]
Smallest test:  [what we will build or try first, and how long it takes]
Not building:   [anti-goals]
Success:        [metric, baseline, target, date]
Stop if:        [the result that ends the idea]
Recommendation: build / test first / do not build, because ...
Open questions: [question, owner, due date]
```

## Journey audit: time to first value

1. Start as a new user on a clean machine or account, following only public instructions.
2. Record every step with a timestamp, every error, confusing instruction or missing piece, and screenshots where the interface is involved.
3. Mark the moment the user first gets the promised outcome; time to that point is the headline.
4. Optionally run a competitor's onboarding the same way for comparison, within its terms of service.
5. Recommend the top fixes ranked by time saved or drop-off avoided.

Report only steps that were actually run; never estimate a journey you did not walk.

## Prioritisation

Scoring frameworks (ICE: impact, confidence, ease; RICE adds reach) structure a conversation; their numbers are guesses. Use them to surface disagreements ("why do you rate impact 5?"), then check constraints the scores ignore: dependencies, team capacity, runway, commitments already made, and risk. Present the ranked list with the reasoning, not just the totals.

## Capability contract: what must be true before building

When the question is no longer whether but what exactly, turn product intent into a contract that survives review:

| Section | Content |
|---|---|
| Capability | One paragraph: who the actor is, what they can do after this ships, what outcome changes |
| Constraints | Business rules, invariants that must always hold, trust boundaries, data ownership, regulatory and billing rules; each marked as fixed policy, preference, or open |
| Actors and surfaces | Users, operators, systems; where each interacts (UI, API, job, email) |
| States and transitions | The lifecycle of the main objects, including failure, cancellation and recovery |
| Interfaces and data | Inputs, outputs, schema implications, migrations, backward compatibility |
| Operations | What operators must see and do; observability; support playbooks |
| Non-goals | What this work deliberately does not cover |
| Open questions | Blockers with owners and dates |
| Handoff | Ready to implement, needs architecture review, or needs product clarification |

Keep the contract in the repository's product documentation (or the place the team already uses), update it rather than starting a new one each time, and turn its requirements into acceptance criteria with the requirements reference.

## Project flow across trackers

Many teams keep a public tracker (issues and pull requests in the code host, visible to the community) and an internal one (planning, owners, priorities).

- **One canonical status per item.** Decide which system is the truth for what: public discussion and resolution in the public tracker; internal ownership, priority and scheduling in the internal one.
- **Mirror only active work.** Create an internal item when the work is scheduled, delegated, cross-team or part of a larger programme, not for every public issue.
- **Classify open contributions** as merge (self-contained, reviewed, passing checks), rebuild (good idea, re-implement in-house), close (wrong direction, stale, unsafe or duplicate, with a courteous explanation) or park (useful, not scheduled). Review the full diff before any merge decision; follow the triage and approval steps in the repository-hygiene reference.
- **Close the loop publicly:** when work ships or is declined, post the outcome where the requester will see it.
- **Changes in either tracker are visible writes:** propose the list of creations, transitions and comments, get approval, then apply in a small batch first.

## Checks (done when)

- [ ] The product brief answers who, pain, why now, smallest test, anti-goals, success metric and stop condition, with sources for every fact.
- [ ] Journey audits report only steps actually run, with timings and evidence.
- [ ] Prioritisation shows reasoning and constraints, not just scores.
- [ ] The capability contract marks each constraint as fixed, preferred or open and ends with a clear handoff.
- [ ] Tracker changes were proposed, approved and applied in a small batch first; public items show their resolution.
