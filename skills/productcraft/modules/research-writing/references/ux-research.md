# User research: discovery, interviews and synthesis

Read this when a team needs to understand users before or while building: what jobs people are trying to get done, why something is not working, which opportunity to pursue, or whether a direction holds up. It covers framing the question, choosing a method, recruiting, consent, interviewing, synthesis, prototyping at the right fidelity and sharing findings. Testing a specific design with tasks is `usability-testing.md`; writing interface copy is `ux-writing.md`; market sizing and competitor research are `market-research.md`; product requirements are `../../engineering-workflow/references/prds-and-roadmaps.md`.

## Ground rules

- **Research serves a decision.** Write down which decision the findings will change and who will make it. Research with no decision attached becomes a deck nobody opens.
- **Consent before recording, minimum data after.** Participants agree in writing to what is recorded, who sees it, how long it is kept, and how to withdraw. Store recordings and notes where the organization's privacy rules say, pseudonymize participants in notes (P1, P2), and delete raw recordings on schedule.
- **Observed behavior outweighs stated opinion.** What people did last time beats what they say they would do.
- **Do not invent participants, quotes or numbers.** Synthetic or AI-simulated "users" can help draft a guide or rehearse; they are never evidence and never appear in findings.
- **Pay people fairly** for their time and pay no-shows who gave notice under your policy.

## 1. Frame the question

A good research question is specific, open, tied to a decision and answerable by talking to or watching people.

| Weak | Stronger |
|---|---|
| Do users like onboarding? | At which step of onboarding do new users hesitate, and what are they unsure about? |
| What should we build next? | When teams close their month, which tasks take longest and what do they do instead of using our tool? |
| Why is conversion low? | What do visitors expect to find on the pricing page, and where does it differ from what is there? |

Spend real time here with the stakeholders; most failed studies fail at framing. List what is already known (analytics, support tickets, earlier studies) so the study does not rediscover it.

## 2. Choose the method

| Question type | Method | Typical size |
|---|---|---|
| Context, motivation, mental models | In-depth interviews, 45-60 min | 5-12 per segment |
| How work really happens | Contextual inquiry (observe in place, remote screen share counts) | 4-8 |
| Behavior over days or weeks | Diary study with short daily prompts | 8-15, expect dropout |
| Is this concept worth pursuing | Concept test with a description, storyboard or rough prototype | 5-8 per concept |
| How people group content | Open or closed card sort | 15-30 for patterns |
| Can people find things in a structure | Tree test (text-only hierarchy) | 30-50 for reliable success rates |
| How common is something | Survey, ideally after qualitative work defined the options | Depends on the needed precision |
| Can people use this design | Usability test (`usability-testing.md`) | 5-8 per round |

Combine methods across a project: interviews to learn the language and problems, then a survey to size them, then usability tests on the solution.

## 3. Recruit

- **Screen for behavior, not demographics alone:** "reconciled accounts in the last month using a spreadsheet" beats "finance professional, 30-50".
- **Mix experience levels:** active users, lapsed users, people who chose a competitor, people who have never tried a solution.
- **Exclude** colleagues, friends and family, and people who did a study for you in the last six months; limit professional testers.
- **Channels:** in-product invitations, customer lists (with consent to contact), support and sales referrals, research recruiting panels, intercepts.
- **Over-recruit by about a third** for no-shows; confirm a day before and an hour before.
- **Accessibility:** include people who use assistive technology in studies of anything they will use, and offer accommodations (captions, longer sessions, a preferred platform).

## 4. The interview guide

A guide is a plan, not a script; follow interesting threads and return to it.

```text
INTERVIEW GUIDE  (study, version, date)
Goal and decision:  ...
Intro (3 min)        Who I am, why we are talking, no right answers, recording consent repeated,
                     they can skip any question or stop.
Warm-up (5 min)      Role and context; a typical week.
Recent story (20 min) "Tell me about the last time you [did the job]." Walk through it step by step.
                     Probes: what happened next; what did you use; what was hard; what did you try first.
Specific areas (15 min) Two or three topics tied to the decision.
Wrap-up (5 min)      "Anything I should have asked?" Thanks, incentive, how findings will be used.
```

### While interviewing

- Ask about specific past events, not general habits or hypothetical futures ("Would you use..." predicts little).
- One question at a time, open first ("How did you decide?"), then narrower.
- Use silence; count to five before filling a pause.
- Ask "why" through the story ("What made that matter?") rather than as a repeated interrogation.
- Notice workarounds, spreadsheets, sticky notes and emotion; they mark unmet needs.
- Do not pitch, defend or explain the product. If asked, say you will answer at the end.
- Have a note-taker, or record and take sparse time-stamped notes.

Avoid leading questions ("Isn't that frustrating?"), double questions, and interviewing your own hypothesis (asking only what would confirm it).

## 5. Synthesis

1. **Capture observations** as single, atomic notes: a quote, a behavior, a moment, with participant and time stamp. Keep raw notes separate from interpretation.
2. **Cluster** notes into themes (affinity mapping), bottom up. Start after the first few sessions, not at the end.
3. **Count across participants:** a theme seen in one session is a lead; one seen in most is a pattern. Report "6 of 8 participants" rather than percentages for small samples.
4. **Write insights,** not themes. An insight explains a why and implies a so-what: "Teams re-key bank data into a spreadsheet because they do not trust automated matching for partial payments, so any automation must show its reasoning per line."
5. **Challenge each insight** against the data: who contradicts it, and what else could explain it? An insight that fits only some sessions is a hypothesis to test.
6. **Link to decisions:** each insight gets an implication and a suggested next step (design change, experiment, further research).

Useful artifacts when they help a decision: a jobs-to-be-done statement per key job ("When [situation], I want to [motivation], so I can [outcome]"), a journey map of the current experience (stages, actions, thoughts, feelings, pain points, opportunities) built from observed stories, and two or three behavior-based archetypes. Do not make demographic personas with invented names and hobbies.

## 6. Prototyping at the right fidelity

Choose the lowest fidelity that answers the current question, and move up only when the question changes:

| Fidelity | Answers | Typical artifact |
|---|---|---|
| Content | What information and actions users need, in what order | A list or outline per screen |
| Wireframe | Layout, navigation and flow | Grey boxes, real labels |
| Low-fidelity interactive | Can people complete the task | Clickable wireframes |
| High-fidelity | Comprehension of visual hierarchy, trust, accessibility of the real look | Designed screens in the design system |
| Code | Feasibility, performance, real data and edge cases | A working build behind a flag |

Every prototype covers decision points and failure paths, not only the happy path: empty data, errors, slow loading, long names, permissions denied. Each level ends with a named validation step (tasks and success criteria), never "test later". High-fidelity and code prototypes use the real tokens and components (`../../ui-distiller/references/design-system-construction.md`).

## 7. Share and track

- **Top-line findings first:** five to ten insights, each one sentence, with supporting evidence and implication.
- **Clips persuade:** a few short, consented clips of participants say more than pages of text. Blur or crop personal data.
- **Walk stakeholders through the synthesis** in a session where they sort or challenge evidence; they act on what they helped conclude.
- **Tailor:** leadership wants the decision and risk; designers want problems and quotes; engineers want scenarios and edge cases.
- **Keep a research repository** of findings with dates, methods and links to the raw (access-controlled) data, so later teams build on it instead of repeating it. Mark findings older than about a year as needing a refresh.
- **Track impact:** which decisions changed because of the study. If none did, ask why before running the next one.

```markdown
# Findings: month-end reconciliation (interviews, 8 participants, 3-14 March)
Decision informed: whether to automate partial-payment matching in Q3.
1. Partial payments are reconciled by hand in 7 of 8 teams. Evidence: P2, P3, P5 (clips 1-3).
   Implication: automation must show its match reasoning per line; test an "explain match" panel.
2. ...
Not answered: how often matches are later reversed (needs product analytics).
```

## Done when

- [ ] A research question tied to a named decision and owner is written, with prior knowledge listed.
- [ ] Method and sample fit the question; recruiting screened for behavior; consent, storage and deletion are recorded.
- [ ] The guide was piloted once and revised.
- [ ] Synthesis separates raw notes from insights; every insight has evidence counts, a challenge pass and an implication.
- [ ] Prototypes were at the lowest useful fidelity with failure paths and a named validation step.
- [ ] Findings were shared in forms each audience uses, stored in the repository, and their effect on decisions recorded.
