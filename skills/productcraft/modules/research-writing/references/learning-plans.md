# Learning plans built from material

Read this when the user wants to turn an article, talk transcript, course, book or set of notes into something they will practice, or wants a study plan for a skill; also when they want questions answered from their own collection of documents. Getting the text of an article or talk is in `web-research-and-extraction.md`.

## What works, and what does not

Use the practices with solid evidence behind them:

- **Retrieval practice:** recalling without looking (self-tests, explaining from memory) beats rereading.
- **Spacing:** reviews spread over days and weeks beat massed sessions.
- **Interleaving:** mixing problem types once the basics are in place.
- **Deliberate practice with feedback:** working at the edge of current ability on specific sub-skills, with quick feedback on errors.
- **Worked examples, then fading:** study solved examples, then solve with less and less support.
- **Producing things:** building, writing, shipping, teaching.

Do not plan around "learning styles" (matching material to a visual or auditory preference); matching has not held up in controlled studies.

## Extract what can be practiced

Read the material and pull out:

- **Actionable principles,** each rewritten as something to do ("open every cold email with the recipient's problem", not "personalization matters").
- **Skills involved,** broken into sub-skills that can be practiced separately.
- **Examples worth replicating,** with the location in the material (section, page, timestamp) for later reference.
- **Claims to check:** statistics, causal claims and "studies show" statements in the material are unverified until checked (`appraising-evidence.md`); mark them.

Leave out anecdotes and theory that do not change what the learner will do, unless the user wants a summary as well.

## Define the outcome

Agree on a concrete, observable goal with a horizon, usually four to eight weeks:

- Good: "Send 20 tailored outreach emails and get at least two replies by 15 December"; "Solve 30 dynamic-programming problems at medium difficulty without hints"; "Deploy a small app with authentication and tests".
- Too vague: "learn sales", "get better at algorithms".

Record a baseline: what the learner can do today, measured the same way as the goal.

## Plan in short cycles

Each cycle is do, reflect, adjust.

**First cycle:** the smallest version that produces a real artifact within one to seven days. It is small enough to start today and large enough to teach something. Learn only what this cycle needs.

**Each later cycle** adds one new element (a harder case, a new sub-skill, a real audience) and adjusts difficulty based on the last result: repeat at the same level after a miss, step up after a clear success.

```markdown
## Goal
<observable outcome, date, baseline>

## Lessons from the material
1. <principle as an action> (source: <section or timestamp>)

## Cycle 1: <artifact>
- Done when: <checkable criteria>
- Practices: <which lessons>
- Steps: 1. ... 2. ... 3. ...
- Only resources needed now: <minimal list>
- Deadline: <date>

## After each cycle
- What happened (facts, results)?
- What worked, what did not, what surprised you?
- One thing to change next time.

## Cycles 2-5 (sketch; revise after each cycle)
```

**Spaced review:** turn facts and definitions into flashcards (Anki or similar) and schedule short self-tests; turn procedures into practice problems rather than cards.

Keep the plan in a file the user owns. Check in on results rather than adding more material; more reading is the most common way plans stall.

## Answering questions from the user's own material

When the user has a collection of documents (papers, course notes, transcripts, reports) and wants to ask questions of it:

- Answer from the documents and cite the passage (file, section or page, timestamp). If the material does not cover the question, say so instead of filling the gap from general knowledge; offer general knowledge separately and labeled.
- For a few documents, read them directly. For many, build or use a retrieval index (`../../ml-engineering/references/rag-systems.md`) and quote retrieved passages.
- Prefer local or self-hosted tools for private material, or services whose data terms the user has accepted. Do not automate a consumer web app's login and interface with a browser bot when its terms forbid it; use official APIs or exports.
- Quiz mode: generate questions from the material, let the learner answer from memory, then show the source passage.

## Copyright

Summaries, notes and quizzes for personal study are fine. Do not republish full transcripts, chapters or course material; link to the source instead.

## Checks (done when)

- [ ] Lessons extracted as actions with locations in the material; unverified claims marked.
- [ ] Goal is observable, dated and has a baseline.
- [ ] First cycle produces an artifact within a week and has done-when criteria; later cycles add one element each.
- [ ] Reflection questions and spaced review are built in.
- [ ] Answers from the user's material cite passages and say when the material is silent.
