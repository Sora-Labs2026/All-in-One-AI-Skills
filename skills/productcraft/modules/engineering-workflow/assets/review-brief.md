# Review request: <change name>

**Goal:** <one sentence>
**Done when:** <copy the checks from the plan>
**Range:** base `<commit>` to head `<commit>` (inspect with `git diff <base>...<head>`, or read the diff file at `<path>`)

**What changed and why:**
<three to six lines>

**Where I am least sure:**
- <area or decision, and why>

**Verified:**
- `<command>` -> <result>

**Not verified:**
- <check> - <why>

**Constraints:** <behavior, interfaces or data that must not change>

---

## Instructions for the reviewer

- Review read-only. Inspect with `git show`, `git diff` and `git log`. To run code, use a separate worktree or copy; do not change this checkout.
- Read the code around the diff (callers, callees and tests), not only the changed lines.
- For each finding give: severity (blocker, should fix, optional), file and line, the concrete input or situation that goes wrong, why it matters, and the smallest fix.
- Report only findings you can back with a concrete case. No style preferences unless the project's conventions are broken.
- List anything you could not check, and why.
- End with a verdict: ready, ready once the blockers are fixed, or not ready, with one sentence of reasoning.
- Do the review yourself; do not start additional reviewers.
