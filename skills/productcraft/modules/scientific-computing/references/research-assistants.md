# Autonomous research assistants

Read this when an LLM-driven pipeline is asked to generate research ideas from data, design methods, run analyses, search literature or draft papers with little human input, or when the user wants to set up or evaluate such a system. Writing, citation management and literature search practice live in `../../research-writing/GUIDE.md`.

## What they are, and what they are not

Multi-agent research assistants chain language-model agents: one proposes a question, another drafts a method, another writes and runs code, another searches literature, another writes a manuscript. They are useful for brainstorming, scaffolding analyses and producing first drafts.

They are not reliable scientists. Known failure modes: citations that do not exist or do not say what is claimed, numbers that no code produced, analyses that run but compute the wrong quantity, iteration over many analyses until something looks significant, overstated conclusions, and methods sections describing steps the code never took. The human researcher owns the question, the method, every claim and the decision to share or publish.

## Ground rules

1. **Every number traces to code that ran.** Each figure and statistic in a draft maps to a script, its inputs and its log. Numbers without that trail are removed.
2. **Every citation is verified.** Look up each reference by DOI or another identifier, confirm it exists, and confirm it supports the sentence citing it. Unverifiable references are removed, never "fixed" by guessing.
3. **Plan before exploring.** Write the analysis plan (hypothesis, primary outcome, test, exclusions) before the assistant iterates over the data, and keep a log of every analysis tried. Report the number of analyses, or hold out data for confirmation.
4. **Sandbox execution.** Generated code runs in an isolated environment with no credentials, no access to unrelated files, network only where needed and resource limits (`../../agent-safety/references/isolation.md`).
5. **Budget and keys.** Agree a spending limit per run; API keys are set by the user in the environment; record model names and versions, prompts and settings, so a run can be audited.
6. **Data protection.** Do not send confidential, unpublished or human-subject data to external model APIs without the owner's approval and the data agreements that apply (consent terms, GDPR, HIPAA where relevant).
7. **Disclosure.** Follow the venue's and funder's policies on AI assistance. Most major publishers do not accept AI tools as authors and require disclosure of their use; check the specific policy.
8. **Licenses.** Check the assistant's own license (some are copyleft, which matters if you distribute modified versions) and the licenses of code it reuses.

## A workflow with human checkpoints

| Stage | Assistant produces | Human checks before moving on |
|---|---|---|
| Idea | Candidate questions from a data description | Novelty against a literature search with verified sources; feasibility with the data available |
| Method | Analysis plan and code outline | Statistical design (power, controls, confounders), pre-registration where appropriate |
| Results | Code, logs, figures | Re-run from a clean environment by the human; inspect intermediate outputs; check the computation answers the planned question |
| Manuscript | Draft text | Claim-by-claim audit against results and verified citations |
| Release | Final package | Human sign-off on every claim; disclosure statement |

Keep an audit table beside the draft:

| Claim | Evidence (file, figure, log) | Citation (verified identifier) | Checked by | Status |
|---|---|---|---|---|

## Evaluate the assistant before trusting it with real work

- **Planted effect:** give it synthetic data with a known effect of known size. Does it find the effect and estimate its size within the expected error?
- **Null data:** give it data with no effect (for example, permuted labels). Count how often it reports a "finding" anyway.
- **Known result:** a published, independently replicated finding with public data. Compare its analysis and conclusion with the published ones.
- **Citation audit:** sample its references and verify each one; record the rate of nonexistent or misattributed citations.
- Record the configuration of every evaluation run (model and version, temperature, tools enabled, iteration limits, cost) so later runs can be compared with it.

## Configure runs defensively

- Mount raw data read-only; write outputs to a fresh directory per run.
- Cap iterations, wall time and spend; stop on the first authentication or quota error.
- Keep the complete log of prompts, responses, code executed and outputs; it is the audit trail for every claim.
- Pin package versions in the sandbox and record them with the results.

## Red flags

- Results cleaner than the data plausibly allow, or p-values clustered just below 0.05.
- Plausible-looking references without identifiers, or with identifiers that resolve to different papers.
- Methods that describe preprocessing, controls or tests absent from the code.
- Figures that cannot be regenerated from saved data and scripts.
- Conclusions that generalize beyond the data's population, period or conditions.

## Checks (done when)

- [ ] Every number in the output maps to code that ran, with inputs and logs.
- [ ] Every reference was verified to exist and to support its claim.
- [ ] The analysis plan predates the results; the log of analyses tried is kept.
- [ ] Code ran sandboxed within an agreed budget; keys never appeared in output.
- [ ] A human re-ran the analysis from a clean environment and signed off on each claim.
- [ ] AI use is disclosed according to the venue's policy.

## Anti-patterns

- Publishing or sharing an assistant's draft without a claim-by-claim audit.
- Letting the assistant "fix" a missing citation by finding something similar.
- Running generated code on a workstation with credentials and personal files in reach.
