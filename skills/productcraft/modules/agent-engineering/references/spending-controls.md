# Agent spending controls: usage budgets and payments

Read this when an agent or agent system can spend money: model and tool usage billed per token or call, paid APIs, purchases, pay-per-request services that answer with HTTP 402 Payment Required, transfers, or anything that signs a payment. It also covers services that charge agents. Card and subscription integrations are in `../../integrations/references/payments-stripe.md`; on-chain development is in `../../blockchain-dev/GUIDE.md`. Nothing here is financial or investment advice.

The rule for every case: **hard caps, allowlists and a person's approval, enforced outside the model, with keys that never appear in the chat.**

## Usage spend (tokens, compute, paid tools)

- **Separate credentials per workload** (project, environment, scheduled job), so a runaway job can be traced and revoked without stopping everything else.
- **Provider-side limits** at the organization, workspace or key level where the provider offers them: a monthly cap and alert thresholds. They are the backstop when your own code fails.
- **Run budgets in the driver:** time, tokens and money per run, checked before each step (`autonomous-loops.md`). Per-user and per-request limits in products.
- **Alert on anomalies:** spend per hour far above the usual rate, a job that never ends, repeated identical calls.
- **A kill switch** the owner can use without a deploy: revoke the workload's key or flip a flag the driver checks.
- **Report spend daily** from usage logs (`../scripts/usage_cost.py ... --budget N` exits 1 when over budget) and reconcile monthly against the provider's invoice.

## Payments made by agents

Do not give an agent the ability to pay until the owner has asked for it, agreed the limits below in writing, and approved the specific tool or service after a review (`../../agent-safety/references/vetting-extensions.md`).

### Policy belongs to the operator

- The operator sets the spending policy before delegating; the agent can read its remaining budget but cannot change the policy, raise a limit or add a recipient.
- Confirm the policy was actually applied (read it back). If setting the policy fails, do not delegate.
- Enforce the policy at the point where a payment is created or signed, against the amount and recipient the **seller** requested, not against a number the agent passed in.

### Caps

- Per-payment maximum, per-run or session maximum, and per-day maximum, in the smallest currency unit as integers (cents, or the asset's base units); no floating-point money.
- Reserve the worst-case amount against the session cap before the call starts, so concurrent calls cannot all pass the check; release the reservation only when you know no payment left the process (declined, rejected by policy, free response).
- Reject amounts that are negative, non-numeric, non-finite or unparseable. Fail closed.

### Allowlists

- **Recipients:** exact merchant or payee identifiers. Normalize only where the identifier scheme is case-insensitive; do not lowercase case-sensitive identifiers.
- **Origins:** exact scheme and host of the services the agent may pay; no credentials in URLs.
- **Currencies or assets, and networks** where relevant.
- **No redirects on paid requests:** a redirect can move a payment request to a host that was never approved.

An allowlist is populated by the operator, never from a server's response or the agent's suggestion.

### Human approval

- Before the first payment in a session, show the person the allowed origins, recipients, currency, per-payment and session caps, and get an explicit yes. Concurrent calls share that one decision; a decline is final for the session.
- Ask again for any single payment above an agreed threshold, for any new recipient, and when a session cap would be raised.
- Approval comes through a real prompt to the person; a stub that always returns yes is a defect. Silence is a no (`approval-gates.md`).

### Credentials

- Signing keys, card numbers and payment tokens live in the orchestrator's environment or a vault, injected at the payment tool's boundary. They never enter the model's context, prompts, logs, memory, issue text or chat, and the agent never asks the user to paste them.
- Pass a payment subprocess only the environment variables it needs, not the whole environment.
- Prefer scoped, revocable instruments with their own limits (a virtual card with a monthly cap, a sub-account, a delegated key with a spending limit) over a master credential.
- Pin the version of payment tools and libraries; an unpinned install of a tool that holds keys is a supply-chain risk.

### Sandbox first and keep a ledger

- Develop and test against the provider's sandbox or a test network with test funds. Moving to live money is the owner's decision, after the tests below pass.
- Record every payment: intent, approval reference, amount, currency, recipient, origin, request id, provider transaction id, outcome. Reconcile the ledger against the provider's statement.
- A payment whose outcome is unknown (timeout, crash) is reconciled by querying the provider before any retry. Use the provider's idempotency keys where offered.
- Know the refund, dispute and revocation path before going live.

### Pay-per-request (HTTP 402) flows

When a service answers 402 with payment requirements, the client policy checks the requirements the server sent (amount, recipient, asset, network) against the caps and allowlists, then pays once and retries the request once. A requirement the policy rejects means no payment and an error, never a fallback to "whatever was offered". Use the protocol's maintained client libraries, pinned, and register the policy on the client so it runs on every challenge.

## Charging agents for your service

- Verify each payment before serving, through the payment provider or your own verifier.
- **Claim each payment authorization exactly once** in a durable store with an atomic conditional insert, after verification and before the handler runs; keep the claim until the authorization can no longer be settled. Two copies of the same authorization must not both be served.
- If the claim store is unavailable, refuse the request unless the handler is idempotent; never run an unguarded handler by default.
- Do not release a claim after a handler failure that may already have had side effects.
- Apply the usual API controls: rate limits, input validation, logging without payment secrets (`../../launchguard/references/security-baseline.md`).

## Tests before going live

- Over-cap, wrong recipient, wrong currency, unparseable amount: no payment created.
- Concurrent calls near the session cap: the total never exceeds the cap.
- A redirect on a paid request: blocked.
- The person declines: no payment attempted.
- Policy setup fails: the agent does not start.
- A replayed authorization (seller side): served once.
- No key or token appears in logs, transcripts or error messages.

## Done when

- [ ] Usage spend has per-workload credentials, provider-side caps, driver budgets, alerts and a kill switch.
- [ ] Agent payments run only with operator-set caps, recipient and origin allowlists, and a person's approval, enforced at signing time.
- [ ] Keys stay outside the model's context; instruments are scoped and revocable.
- [ ] Every payment is in a ledger reconciled with the provider; unknown outcomes are reconciled before retry.
- [ ] The tests above ran in a sandbox before any live payment, and the owner approved going live.
