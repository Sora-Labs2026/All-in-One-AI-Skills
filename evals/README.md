# ProductCraft eval suite

These cases measure three things:

- **Triggering:** does the skill load on a natural request that should use it, and stay out of one that should not?
- **Progressive disclosure:** does the agent then read the matching module?
- **Uplift:** are answers better with the plugin than without it?

Each case is a folder with a `prompt.md` and a `graders/` folder, run by `claude plugin eval` (Claude Code 2.1.269 or later).

## What each case checks
- `skill-fired`: a `tool_used: Skill` grader. Under the default two-arm run it is reported as a plugin-fired indicator and is not scored. In `off-topic-trivia` the grader is inverted (`max: 0`, `arm: both`) to catch false triggers.
- `read-module`: a with-only `tool_used: Read` grader on the module the router should open.
- `regex` graders: cheap checks for a fact a correct answer must contain.
- `rubric`: an `llm` grader with PASS and FAIL conditions. It is scored in both arms, so it drives the uplift (Δ).

Every case lists only read-only tools and inlines its inputs, so no `--scaffold`, `--allow-tools` or `--mocks off` is needed.

## Run it
From the repository root:

```bash
python3 scripts/check_evals.py                       # free: static check of every case

# Cheap iteration: one run per case, one arm, hard cost cap
claude plugin eval . --runs 1 --ablation none --max-cost-usd 3 --threshold 0 \
  --no-publish --json evals/results/quick.json

# Measurement: three runs per case, with and without the plugin
claude plugin eval . --runs 3 --max-cost-usd 20 --threshold 0.8 \
  --no-publish --json evals/results/full.json

python3 scripts/eval_summary.py evals/results/full.json --min-trigger 0.8 --max-false-trigger 0
```

- **Selecting cases:** use `--tag core` (or `security`, `ui`, `negative`, `new-domains`), or `--case <glob>`, to run a subset.
- **Cost:** it scales with cases × runs × arms, plus three judge calls per `llm` grader per run. Start with the cheap command.
- **Noise:** single runs are noisy, so confirm any change with `--runs 3`.
- **Results:** they are written under `evals/results/`, which git ignores.

## Reading the summary
`eval_summary.py` prints one row per case:

- **Loaded (or wrongly loaded):** for normal cases, the share of with-plugin runs that loaded the skill; for negative cases, the share that wrongly loaded it.
- **Module read:** the share of with-plugin runs that read the expected module.
- **Scores and Δ:** the score with the plugin, the score without it, and the difference.

The totals give:

- the trigger rate;
- the false-trigger rate;
- the mean score and mean Δ;
- the list-price cost estimate.

### What to do with weak results
- **Low trigger rate:** the agent is answering from memory. Tighten the `description` in `skills/productcraft/SKILL.md`, which is limited to 1,024 characters.
- **Low module-read rate:** the router row for that task is unclear.
- **Δ near zero when the skill did load:** the module adds nothing the model doesn't already know. Deepen it or cut it.

## Adding a case
1. Copy a folder and write a realistic prompt that never names the skill.
2. Keep one `skill-fired` grader, one `read-module` grader that points at the module the router should open, at least one `regex` grader, and one `rubric`.
3. Run `python3 scripts/check_evals.py`, then a single cheap run of the new case with `--case <name>`.
