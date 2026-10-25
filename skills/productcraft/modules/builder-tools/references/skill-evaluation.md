# Evaluating a skill

Read this before releasing a new skill, after changing one, or when someone asks whether a skill helps. A skill has to pass two separate tests: it is **loaded when it should be** (and not otherwise), and it **makes the result better** once loaded.

Contents: the test set · checks that discriminate · with and without runs · reading results · trigger tests · instruction read-through · iterating · what to record.

## The test set

Write 3 to 10 task prompts that a real user would send, with the files they would attach. Good prompts are specific and a little messy: real file names, column names, a deadline, a typo, an unstated assumption. Cover:
- the main use, in two or three phrasings;
- one or two edge cases the skill claims to handle (an empty input, an unusual format, a conflicting instruction);
- one prompt where the skill should change nothing or step aside (the task is adjacent but different).

For each prompt write the expected outcome in observable terms before you run anything, so results cannot redefine success.

```json
{
  "skill": "invoice-maker",
  "cases": [
    {
      "id": "single-order-eur",
      "prompt": "need an invoice for order 1042 (attached csv), customer is in Germany, our usual layout pls",
      "files": ["fixtures/order-1042.csv"],
      "checks": [
        "outputs/invoice-1042.pdf exists and has exactly 1 page",
        "pdftotext output contains 'Invoice 1042' and the total '1.234,50 €'",
        "VAT line shows 19%",
        "no '{{' tokens in the text"
      ]
    }
  ]
}
```

Keep fixtures small, synthetic and free of personal data. Keep expected answers where the agent under test cannot read them (outside the folder it works in).

## Checks that discriminate

A check is useful only if a wrong result would fail it.
- Check content, not existence: "the PDF exists" passes for an empty PDF; "the PDF's text contains the order total" does not.
- Prefer a script to judgment for anything mechanical (page counts, totals, field values, schema validity, test suite results). Scripts are repeatable across runs and versions.
- For qualities that need judgment (tone, layout, clarity), write a short rubric with concrete criteria and compare outputs side by side, ideally without the judge knowing which configuration produced which.
- Check claims against evidence. An agent's final message saying "all fields filled" is a claim; the re-read fields are evidence. Grade from the outputs and the transcript.
- After a round, review the checks themselves: one that passes in every configuration, or that a clearly wrong output would pass, measures nothing. Replace it.

## With and without runs

Run every prompt in at least two configurations:
- **New skill:** with the skill versus without any skill.
- **Changed skill:** new version versus a snapshot of the previous version (copy the old folder before editing).

Rules that keep the comparison fair:
1. Each run starts fresh: a new agent session or subagent that sees only the prompt and files, not this conversation. Use the same model and settings for all configurations.
2. Each run writes to its own output folder (`runs/<round>/<case-id>/<config>/<repeat>/`).
3. Run each prompt several times per configuration (three is a practical minimum): agent output varies, and one run proves little.
4. Record per run: checks passed, wall time and tokens or cost if the host reports them, and the transcript.
5. Launch the configurations together or interleaved, so a change in the environment does not land on one side only.

## Reading the results

- **Pass rate per check and configuration**, with the spread across repeats. A difference smaller than the run-to-run spread is not an improvement yet; add repeats or cases before concluding.
- **Checks that pass everywhere** do not show the skill's value; checks that fail everywhere point to a task the skill does not address or a broken check.
- **Cost:** a skill that adds a little quality for double the time or tokens may not be worth loading for that task; say so.
- **Transcripts** show what the numbers hide: instructions skipped or misread, time spent on detours the skill caused, and helper code written from scratch in every run. The last one is a signal to bundle that helper as a script.

## Trigger tests

The description decides loading, so test it on its own.
1. Write 16 to 24 realistic requests: about half that should load the skill and half that should not. The useful negatives are near misses: same vocabulary, different job (for an invoice skill: "draft a quote", "explain this invoice to me", "fix the invoice table in our React app").
2. Make them substantive. Trivial requests ("open this PDF") often load no skill at all, so they test nothing.
3. Run each request several times in a fresh session with the skill installed among the others the user really has, and record whether the skill was loaded.
4. Split the set before tuning: tune the description on one part, and judge the final wording only on the held-back part, which you never read failures from while editing. Otherwise you fit the description to the test.
5. Report the loaded rate for should-load and should-not-load requests separately.

## Instruction read-through

Before or alongside task runs, give only `SKILL.md` (and the files it links) to a fresh agent and ask it questions the skill must answer: "What do you do first?", "What if the input has no header row?", "Which file do you read for a German customer?", "When do you stop?". Wrong or hesitant answers locate ambiguous or missing instructions faster than full runs do.

## Iterating

- **One idea per round.** Change one thing (the description, one rule, one reference split), rerun, compare. Bundled changes hide which part helped or hurt.
- **Fix the cause, not the case.** Change the instruction behind a whole class of mistakes; do not add a rule that names a test prompt. A skill tuned to its test set fails on the next real request.
- **Remove as readily as you add.** If deleting a paragraph does not change results, delete it; shorter skills load faster and are followed more closely.
- **Involve the user** on subjective outputs: show the outputs per case with a place for comments, and treat silence on a case as acceptance.
- **Stop** when the checks pass reliably across repeats, when two rounds bring no improvement beyond the noise, or when the user is satisfied. Say which.

## What to record

Keep an `evals/` folder next to the skill (or in the project that owns it), outside the installed package if the package must stay small:
- `cases.json` (prompts, files, checks) and `triggers.json` (`[{"query": "...", "expect": "load" | "skip"}]`);
- the check scripts;
- a short results log per round: date, model, skill version, configurations, pass rates with spread, cost, and the one change made.

Report results with their limits: number of cases and repeats, the model used, and what was judged by script versus by a person or a model.
