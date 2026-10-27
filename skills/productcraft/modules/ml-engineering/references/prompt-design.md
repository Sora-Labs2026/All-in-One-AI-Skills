# Prompt design for product features

Read this when you write or change the prompts, tool definitions or output schemas inside an application: classification, extraction, summarization, drafting, assistants, RAG answers, agents. Prompts for Agent Skills are in `../../builder-tools/references/skill-authoring.md`. Measuring whether a prompt is better is in `llm-evaluation.md`; do that before and after every change.

## Principles

1. **Write the task down as a spec first:** inputs, the exact output, what counts as correct, what to do with bad or missing input, and what is out of scope. If you cannot write it, the model cannot follow it.
2. **Clear, direct instructions** in plain language beat clever tricks. Say what to do, not only what to avoid, and give the reason when a rule is not obvious; models generalize better from reasons.
3. **Separate instructions from data.** Put user input, documents and tool results in clearly delimited sections or separate message parts, and say they are data.
4. **Constrain the output** with a schema the code validates, not with hopes about wording.
5. **Evaluate every change** on a fixed set; prompt edits that feel better are often neutral or worse on cases you did not look at.

## Structure of an application prompt

```text
System / developer message (stable, versioned in code):
  Role and goal: who the assistant serves and what outcome matters.
  Context: product facts the model needs (short; long references go through retrieval).
  Rules: scope, safety and policy constraints, with reasons.
  Process: steps for non-trivial tasks (for example: identify the request type, find supporting sources, answer, cite).
  Output contract: format, schema, length, language, citation style; what to return when unable.
  Examples: a few varied input/output pairs, including an edge case and a refusal or "not found".

User message (per request):
  <document id="..."> ... </document>   retrieved or user-provided material, marked as data
  <question> ... </question>             the user's actual request
```

- Keep stable content first and per-request content last. Many providers cache an unchanged prompt prefix, which cuts cost and latency; timestamps or user ids early in the prompt defeat the cache.
- Put long documents before the question about them; models handle that order well.
- Use consistent tags or headings and refer to them by name in the instructions ("answer only from the material inside the document tags").

## Few-shot examples

- Use 2 to 5 examples that differ in the ways real inputs differ (length, edge cases, the "none" answer). Examples that all look alike teach the model to copy their surface form.
- Examples must obey every rule in the prompt; one inconsistent example outweighs a paragraph of instructions.
- For classification, include examples of each class, roughly balanced, and of the hardest confusions.
- Dynamic examples (retrieve the most similar labeled examples per request) help when inputs vary widely; evaluate against fixed examples.

## Structured outputs and tools

- Prefer the provider's structured-output or schema-constrained mode where available; otherwise ask for JSON matching a schema and validate it.
- Validate every response in code (Pydantic, JSON Schema, Zod). On failure, retry once with the validation error, then fail gracefully; do not loop.
- Design schemas for the model: descriptive field names, enums for closed sets, an explicit `null` or `"unknown"` option so the model is not forced to invent a value, and a field for the evidence or source id when the value must be grounded.
- Put a short reasoning or evidence field before the answer field if the task benefits from deliberation, or use the model's built-in reasoning mode where offered; do not ask for hidden reasoning you then parse.
- Tool definitions are prompts too: precise names, one-line purpose, when to use and when not to, parameter descriptions with formats and limits, and actionable error messages. MCP-specific tool design is in `../../builder-tools/references/mcp-server-design.md`.
- Parse tool arguments with a JSON parser; never pattern-match on serialized text.

## Grounding and honesty

- For answers from documents: answer only from the provided material, cite source ids per claim, and say clearly when the material does not contain the answer.
- Give the model an explicit way out ("If the request is outside X, reply with ..."). Without one it guesses.
- Never instruct the model to claim certainty, invent statistics, or present generated text as human-written or verified.
- Do not ask the model for a confidence percentage and show it to users as a probability; such numbers are not calibrated unless you calibrated them.

## Security in prompts

The security review of LLM features, including prompt injection, output handling and excessive agency, is in `../../code-security-review/references/vulnerability-classes.md` (section "LLM and agent risks"). In prompt design terms:
- Nothing secret goes in a prompt: assume users can extract it. Authorization rules live in code, not in the system prompt.
- Untrusted text (user input, web pages, emails, documents, tool results) can contain instructions. Mark it as data, and make sure an injected instruction cannot reach anything harmful: tools act with the end user's permissions, destructive or outbound actions need confirmation in the interface.
- Model output is untrusted input to the rest of the system: validate, escape and parameterize before it reaches HTML, SQL, shells or file paths.

## Model and parameter choices

- Use the model the evaluation says is good enough at the lowest cost and latency; re-run the evaluation when switching models or versions, because prompts do not transfer perfectly.
- Sampling parameters: low randomness for extraction and classification, more for creative drafting. Some current models fix or reject sampling parameters such as temperature; check the provider's documentation for the model you use.
- Some current models no longer support prefilling the start of the assistant's reply; use structured outputs or instructions instead of prefill tricks.
- Reasoning or "thinking" modes and effort settings trade cost and latency for quality on hard tasks; measure per route rather than enabling them everywhere.
- Set an output token limit that fits the longest valid answer, and detect truncation (the stop reason) instead of parsing a cut-off response.

## Versioning and change control

- Prompts live in the repository as files or constants with a version, reviewed like code; no editing prompts in a production console without a record.
- Each change records: the problem, the hypothesis, the diff, evaluation results before and after on the same set, and a rollback path.
- Change one thing at a time when diagnosing; bundle changes only after each is understood.
- Log the prompt version and model id with every production request.

## Cost and latency

- Count tokens with the provider's tokenizer or token-counting endpoint, not by characters.
- Trim instructions and examples that evaluation shows do not help; keep the ones that do even if long.
- Cache stable prefixes; batch non-interactive work through batch endpoints where offered; stream long responses to users.
- Put per-user and per-request limits on tokens, tool calls and steps.

## Debugging a prompt

1. Collect failing cases from the evaluation or logs and group them by failure type (missed instruction, wrong format, hallucinated fact, wrong refusal, ambiguity in the task).
2. Check whether the spec itself is ambiguous; fix the spec before the wording.
3. Change one thing aimed at the largest group; re-run the development set; check the held-out set before shipping.
4. If the same failure persists across several clear prompt variants, the fix is probably elsewhere: retrieval, tools, model choice, or the task needs to be split into steps.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Untrusted text concatenated into the system message | Separate, delimited data sections; permissions in code |
| Output parsed with regex from prose | Structured output plus schema validation |
| Examples that contradict the rules | Review examples against every rule |
| Prompt edited without re-running the evaluation | Evaluation before and after, held-out confirmation |
| Secrets or authorization logic in the prompt | Keep them in code and configuration |
| Timestamp or user data at the start of a long stable prompt | Stable prefix first, variable content last |
| Same prompt assumed to work on a new model | Re-evaluate on every model or version change |

## Done when

- [ ] The task spec, output schema and out-of-scope behavior are written down.
- [ ] Untrusted input is delimited as data, outputs are validated in code, and nothing secret is in the prompt.
- [ ] The prompt is versioned in the repository with its evaluation results and the model id it was tested on.
- [ ] Changes were measured on the development set and confirmed on the held-out set, with cost and latency recorded.
