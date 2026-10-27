# Running a requirements workshop and writing acceptance criteria

Read this when the request is a *feature* rather than a change to known code: the user describes an outcome they want but the behavior, the boundaries and the "done" are not pinned down yet. The goal is a short specification the user agrees to and an implementer could build from without guessing, not a long document nobody reads.

This extends `clarify-and-plan.md`. That reference turns a known change into done-when checks; this one is for the earlier step, when what to build is still open. For a costly-to-reverse design choice inside the work, write an ADR (`../../engineering-practices/references/docs-and-decisions.md`).

## When a workshop is worth it

Hold one when two or more hold: the feature touches several screens or services, more than one person has a stake in it, it changes data other code depends on, or a wrong guess is expensive to undo. For a one-screen addition with an obvious shape, skip straight to done-when checks and build.

Keep it proportional. A workshop is a focused set of questions and a one-page spec, not a project phase. If the spec grows longer than the code it describes, it has turned into the code; cut it back.

## 1. Frame the problem before the solution

Start from the user's need, not the feature they named. Capture, in a line or two each:

- **The problem and who has it.** What is hard or impossible today, for which users, how often.
- **The outcome that would count as success.** An observable change in what a user can do, stated without naming a mechanism.
- **Who decides.** The person who settles scope and sign-off, and anyone whose constraint the feature must respect (a security, legal or operations owner).

Wear two hats while you ask: the product hat (what the user gains, what success looks like) and the engineering hat (what it touches, what can fail, what it costs). A question from one hat that the other cannot answer is the one worth asking the user.

## 2. Interview in a few rounds

Ask in small batches, each question with your proposed default and what the answer changes, so the user can confirm quickly (the question style is in `clarify-and-plan.md`). Cover:

| Area | What to settle |
|---|---|
| Scope | Which users, records, platforms and cases are in, and which are explicitly out |
| Rules | The conditions that drive behavior: limits, thresholds, who may do what, what each state allows |
| Failure | Fail closed or degrade; all-or-nothing or partial; what the user sees when a dependency is down |
| Data | What is stored, who may read it, how long it is kept, whether deletion is needed |
| Scale | Expected volume, rate and size, so the design is not built for the wrong order of magnitude |
| Non-functional | Response-time, security and accessibility expectations that the feature must meet |

Search the code and the existing product for answers before asking; most scope questions are already settled somewhere. When a question needs a third party (a load target only operations knows, a retention period set by legal), use the questionnaire pattern in `clarify-and-plan.md` and mark the blocked decision in the spec.

## 3. Write functional requirements as testable statements

Write each requirement as one checkable sentence with a stable identifier (`FR-01`), in a form that names the trigger or state, the system and the required response. A widely used template set (often called EARS, the easy approach to requirements syntax) keeps them unambiguous:

- **Always true:** *The system shall store passwords only as a slow salted hash.*
- **Event-driven:** *When a valid file is uploaded, the system shall create one record per row.*
- **State-driven:** *While an import is running, the system shall reject a second import for the same account.*
- **Conditional (state plus trigger):** *While the cart has items, when the user confirms checkout, the system shall charge the saved payment method.*
- **Optional feature:** *Where two-factor is enabled, the system shall require a second factor at sign-in.*

Rules that keep them useful:

- One response per requirement. Split "expire after 10 minutes and are single-use" into two.
- Use concrete values (`10 MB`, `3 attempts`, `HTTP 409`), not "fast" or "reasonable". A requirement no implementation could be checked against is a defect of the spec.
- Say what must *stay* true as well as what changes, so a later change cannot quietly break it.
- Note strength where a bound applies: mandatory, recommended with a documented exception, or optional.

Add non-functional requirements the same way, with numbers: a latency target at a named percentile, the authorization each new route enforces, the accessibility bar, retention and deletion.

## 4. Turn each requirement into acceptance criteria

Acceptance criteria are the concrete scenarios that prove a requirement holds. Write them in a given/when/then shape so each maps to a test:

```text
AC-01  Valid login
  Given a registered user with the correct password
  When they submit the sign-in form
  Then they reach the dashboard and a session cookie is set with HttpOnly and Secure.

AC-02  Locked out after repeated failures
  Given five consecutive failed sign-ins for one account
  When a sixth is attempted with the correct password
  Then it is rejected and the user is sent to account recovery.
```

Cover, for each requirement: the main path, the error paths (invalid input, missing permission, a dependency down), and the edges (empty, one, many, boundary values, duplicate submit, two actors at once). Each criterion should be independent, valuable, small enough to check in one test, and objectively pass-or-fail. Vague outcomes ("works", "is fast") are not criteria; name the observable result.

These criteria become the done-when checks the workflow pins in phase 1 and the tests written in phase 3. Keep the identifiers so the plan, the tests and the report can cite them.

## 5. Record error behavior and open questions

- **Error table:** condition, what the user sees, and the status code or outcome, for every failure the criteria mention. This stops error handling from being an afterthought.
- **Out of scope:** list what the feature deliberately will not do, so scope creep is visible when it arrives.
- **Open questions:** decisions still waiting on the user or a third party, each with the default you will build against meanwhile and the date it is needed.

## 6. Validate before building

Give the spec back to the user and confirm it reads the way they meant. A good check: hand the spec alone to a fresh reader (a colleague or a helper with no context) and ask what the feature does, what happens when input is invalid, and when it is done. Wrong or hesitant answers mark the gaps to fix. Do not mark the spec accepted on your own.

## Done when

- Every requirement is one testable statement with an identifier and concrete values.
- Every requirement has at least one acceptance criterion covering its main path, and error and edge criteria exist for the ones that can fail.
- Error behavior, out-of-scope items and open questions are written down, each open question with a working default.
- The user agreed to the spec, and the acceptance criteria are carried into the plan as done-when checks.

## Anti-patterns

- A spec of adjectives: "intuitive", "robust", "scalable", with no number anyone can check.
- Criteria that only restate the happy path, so the first malformed input is undefined behavior.
- Writing the whole thing before asking one question, then defending it instead of the user's need.
- A document so long it is never read, or kept so far from the code that it drifts out of date. Keep it short and near the work.
