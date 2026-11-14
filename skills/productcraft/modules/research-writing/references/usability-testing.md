# Usability testing

Read this when a design, prototype or live flow needs to be tested with real people doing real tasks: before launching a flow, after a redesign, when analytics show drop-off without a reason, when support tickets cluster around one area, or when choosing between two directions. Discovery research is `ux-research.md`; production experiments (A/B tests) are `../../ml-engineering/GUIDE.md`; accessibility conformance is `../../engineering-practices/references/accessibility-audit.md`, although testing with disabled participants belongs here too.

## Ground rules

- **Test tasks, not the product.** "Explore and tell us what you think" produces opinions; a goal with a clear end produces evidence.
- **The participant is never wrong.** Struggles are findings about the design. Do not defend, explain or rescue early.
- **Consent and privacy** as in `ux-research.md`: written consent for recording, test accounts and fictional data in the prototype, no real customer data on screen.
- **Report what happened,** with counts, clips and severities. Participant suggestions are data about their problem, not a feature spec.

## 1. Plan

```text
TEST PLAN  (flow, build or prototype version, date)
Decision:        What will change based on the results.
Participants:    Who, screener criteria, how many per segment, devices, assistive technology users.
Format:          Moderated or unmoderated; remote or in person; session length.
Tasks:           3-5, each with scenario, start state, success criterion, time limit.
Measures:        Completion, time on task, errors, post-task ease rating, post-test questionnaire.
Setup:           Prototype link or build, test accounts, recording tool, note template.
Pilot:           Date of the pilot session.
```

### Writing tasks

- State the goal and the context, not the interface action: "Your team of twelve needs a plan that includes single sign-on. Find the right plan and what it would cost per year." Not "Click Pricing and compare plans".
- Avoid words that appear on the button or menu you are testing; they turn the task into a word-matching game.
- Give a clear end ("when you have the yearly price, tell me") and the data the participant needs (a fake card number, an address).
- Each task takes 2 to 10 minutes. Put an easy one first.
- Pick tasks that are frequent, strategic or known to be problematic.

## 2. Moderated or unmoderated

| | Moderated | Unmoderated |
|---|---|---|
| Best for | Early prototypes, complex or novel tasks, understanding why | Stable designs, simple tasks, benchmarks, more participants |
| Sample per round | 5-8 per segment | 15-30 per segment |
| Cost per session | Higher | Lower |
| Risk | Moderator influence | No follow-up questions; participants may rush |

About five participants per segment surface most of the frequent problems in a round; several small rounds with fixes between them beat one large round. Use larger samples when you need numbers (benchmarks, comparing designs).

## 3. Run a moderated session

| Part | Time | Content |
|---|---|---|
| Welcome | 3 min | Purpose, recording consent repeated, "we are testing the design, not you", they can stop at any time |
| Background | 5 min | Their context and current tools for this job |
| Tasks | 30-40 min | Read the task aloud and also show it in writing; ask them to think aloud |
| After each task | 1-2 min | Ease rating (1 very difficult to 7 very easy) and "what, if anything, was confusing?" |
| Debrief | 5-10 min | Overall impressions, comparison with what they use today, anything else |
| Close | 2 min | Thanks and incentive |

**Moderation:**

- Prompt thinking aloud neutrally: "What are you looking for?", "What do you expect to happen?"
- Answer questions with questions: "What would you do if I were not here?"
- Let silence and struggle run. Intervene only when the participant is stuck for a set time (about two minutes) or distressed; note that the task was assisted.
- Note hesitation, backtracking, scrolling past the target, wrong guesses and the words people use for things.
- Talk for about a fifth of the session at most.

Have one note-taker, or record and note time stamps. Use one row per observation: participant, task, time, what happened, quote.

## 4. Unmoderated tests

- Write tasks so they are unambiguous without a moderator; pilot with two people.
- Include a success check: a question with a verifiable answer ("What is the yearly price?") or a destination page the tool can detect.
- Screen out low-effort sessions (too fast, no audio, random clicking) by rules set before you look at results.
- Watch the recordings for the failing sessions, not just the numbers.

## 5. Measures

| Measure | How | Report as |
|---|---|---|
| Task success | Completed without help, completed with help, failed or gave up | Counts per task ("4 of 6 unaided") and, for larger samples, a proportion with a confidence interval (adjusted Wald) |
| Time on task | Successful attempts only | Median and range (times are skewed) |
| Errors | Wrong paths, form errors, dead ends | Count per task, with the main error types |
| Ease | Single post-task question, 1-7 | Median per task |
| Overall usability | System Usability Scale (10 items, 1-5) at the end | Score 0-100 |

SUS scoring: for odd items subtract 1 from the answer; for even items subtract the answer from 5; sum the ten results and multiply by 2.5. Scores around 68 are average; treat differences of a few points between small samples as noise.

## 6. Synthesis and severity

1. **List every issue** with participant, task and evidence.
2. **Merge** issues with the same cause.
3. **Rate severity** by impact and frequency:

| Severity | Definition |
|---|---|
| Critical | Prevents task completion for some participants, or causes a harmful error (wrong payment, data loss) |
| Major | Causes long delays or repeated errors for many participants |
| Minor | Small friction with an easy recovery |
| Cosmetic | Noticed but no effect on the task |

4. **Recommend specific fixes** for each issue, with the evidence and an effort estimate.
5. **Record what worked** so it is not changed by accident.

## 7. Report

```markdown
# Usability test: plan selection (moderated, 6 participants, prototype v3, 12 May)
Summary: 2 of 6 found the yearly price unaided; the plan table hides SSO under "More features".
Top three changes: 1) show SSO in the comparison rows, 2) yearly/monthly toggle above the table, 3) ...

## Critical
### C1. SSO availability not found (Task 2; 4 of 6 failed)
Evidence: P1 "I assume it's enterprise only?" (clip 1, 04:12); P3 and P5 left the page.
Fix: add an "SSO" row to the comparison table; mention it in the Business plan summary.
## Major ... ## Minor ... ## Cosmetic ...
## What worked
## Measures (per task: success, median time, ease)
## Method, participants, limitations
## Next round: re-test tasks 2 and 4 after fixes, week of 26 May
```

Show clips in a short walkthrough meeting; written reports alone rarely change priorities. Every critical and major issue gets an owner and a date, and the fixes are re-tested with the same tasks.

## Testing with disabled participants

- Recruit people who use screen readers, magnification, switch access, voice control or keyboard only, and people with cognitive or learning disabilities, for flows they will use.
- Let them use their own device and settings; a lab machine without their configuration measures the lab.
- Allow longer sessions and fewer tasks; pay at least the same rate.
- Expect findings that automated checks miss: confusing announcements, lost focus after updates, time pressure, unclear instructions.

## Pitfalls

- Tasks that name the button to press; testing only the happy path.
- Colleagues, friends or the design team as participants.
- Rescuing participants early, or explaining the design when they struggle.
- One vivid participant treated as a pattern; severity skipped so everything looks equally urgent.
- Never re-testing, so fixes that create new problems go unnoticed.

## Done when

- [ ] A plan names the decision, participants, format, 3-5 goal-based tasks with success criteria, measures and a pilot.
- [ ] Sessions were recorded with consent on fictional data; observations are time-stamped per participant and task.
- [ ] Results report success counts, median times, ease ratings and SUS where used, with small-sample caution.
- [ ] Issues are merged, rated by severity with evidence, and have specific fixes, owners and dates.
- [ ] A re-test of the fixed tasks is scheduled or done.
