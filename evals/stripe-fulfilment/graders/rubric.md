---
type: llm
weight: 2
---
PASS only if the answer does all of the following:
- Fulfils in a webhook handler that verifies the Stripe signature against the raw request body.
- Handles `checkout.session.completed`, plus the asynchronous-payment events if delayed payment methods are enabled.
- Makes fulfilment idempotent (keyed by event or session id), so retries and duplicates do not double-grant.
- Does not rely on the success-page redirect alone.
FAIL if the role is granted only from the success page or redirect, or if signature verification is missing.
