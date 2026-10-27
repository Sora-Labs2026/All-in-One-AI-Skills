# AWS serverless and event-driven design

Read this when you build or change Lambda functions, API Gateway APIs, SQS, SNS, EventBridge, Kinesis, DynamoDB Streams or Step Functions, design an asynchronous workflow on AWS, or host an AI agent on AWS managed services.

General failure handling (timeouts, retries with backoff and jitter, idempotency, transactional outbox, dead-letter queues) is in `../../engineering-practices/references/resilience.md`. This file adds what is specific to AWS services. Infrastructure code for these services follows `aws-cdk.md` or the Terraform references.

## Choose the integration by the guarantee you need

| Need | Use | Delivery and ordering |
|---|---|---|
| Synchronous request and response | API Gateway HTTP API (cheaper, JWT and IAM auth), REST API (usage plans, request validation, WAF, private APIs), Lambda function URL (simplest, IAM or none), ALB | Caller retries; the handler must tolerate duplicates |
| Buffer work and absorb spikes | SQS standard | At least once, no ordering |
| Ordered work per key | SQS FIFO with a message group ID per entity | Ordered per group; deduplication window of five minutes |
| One event, many independent consumers | SNS topic fanning out to one SQS queue per consumer, or EventBridge rules | At least once per subscriber |
| Route by event content across teams or accounts | EventBridge bus with rules and event patterns | At least once; retries up to 24 hours per target |
| Ordered stream with replay | Kinesis Data Streams, DynamoDB Streams | Ordered per shard; a failing record blocks its shard until handled |
| Multi-step workflow with waits, branches, compensation | Step Functions | Standard: exactly-once steps, up to a year; Express: at-least-once (async) or at-most-once (sync), up to five minutes |
| Point-to-point source to target with filtering | EventBridge Pipes | Inherits the source's guarantees |
| Schedules | EventBridge Scheduler (time zones, one-off schedules, retries, DLQ) | At least once |

Check current quotas and limits (payload sizes, timeouts, throughput) in the service documentation before designing around them; several have changed in recent years.

## Lambda function design

- One function, one job. Do the expensive setup (SDK clients, connection pools, configuration fetch) outside the handler so warm invocations reuse it.
- Set the timeout from observed latency plus margin, never the maximum by default. Give every downstream call its own shorter timeout.
- Memory also sets CPU share. Measure duration and cost across memory sizes before choosing; arm64 is usually cheaper for the same work once native dependencies are verified.
- **Concurrency is shared per account and region.** One runaway function can starve the rest. Use reserved concurrency to cap a function that hits a fragile database or third-party API, and SQS event source maximum concurrency to limit a consumer without throttling the queue.
- **Do not chain functions synchronously** (Lambda invoking Lambda and waiting). You pay twice and lose error handling; use a queue, an event or Step Functions.
- **Avoid recursive loops** (a function writing to the bucket or queue that triggers it). Lambda detects and stops some loops, but design them out: separate input and output prefixes or queues.
- Cold starts matter mostly for synchronous, latency-sensitive paths. Measure first. Options: smaller packages and lazy imports, SnapStart (Java, Python, .NET; check runtime support and the uniqueness caveats for random seeds and connections), and provisioned concurrency, which bills while idle.
- Functions in a VPC need NAT or VPC endpoints for AWS APIs and the internet; NAT data processing is often the largest line on a small serverless bill.

## Event source specifics

**SQS to Lambda**
- Set the queue's visibility timeout to at least six times the function timeout, or messages reappear while still being processed.
- Turn on partial batch responses (`ReportBatchItemFailures`) and return only failed message IDs; otherwise one bad message retries the whole batch.
- Configure the dead-letter queue as a redrive policy on the source queue (`maxReceiveCount` around 3 to 5), alarm on its depth, and document how to redrive after a fix.

```python
def handler(event, context):
    failures = []
    for record in event["Records"]:
        try:
            process(json.loads(record["body"]))
        except TransientError:
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}   # requires ReportBatchItemFailures on the mapping
```

**Asynchronous invocation** (S3, SNS, EventBridge invoking Lambda): Lambda retries failed events twice by default. Set maximum retry attempts and maximum event age deliberately, and send failures to an on-failure destination (SQS, SNS, EventBridge, S3) that records the error context.

**Kinesis and DynamoDB Streams**: one poison record stops its shard. Set `bisectBatchOnFunctionError`, a bounded `maximumRetryAttempts`, `maximumRecordAgeInSeconds` and an on-failure destination, and alarm on iterator age. Stream retention is limited (24 hours for DynamoDB Streams), so a long outage loses data unless consumers catch up.

**EventBridge**: give each target a retry policy and a dead-letter queue. Archive and replay redeliver old events, so consumers must be idempotent. Keep personal data out of event payloads unless every subscriber is allowed to see it; events fan out to targets you may not control.

## Idempotency on AWS

At-least-once delivery means every consumer sees duplicates. Claim the work atomically with a conditional write before doing it; a read-then-write check races under concurrency.

```python
try:
    table.put_item(
        Item={"pk": f"payment#{payment_id}", "status": "IN_PROGRESS", "expires": now + 86400},
        ConditionExpression="attribute_not_exists(pk)",
    )
except table.meta.client.exceptions.ConditionalCheckFailedException:
    return previous_result(payment_id)   # already claimed or done
```

- Key on the business identifier (order ID, payment ID, the client's idempotency key), not the transport message ID, because producers can resend the same business event with a new message ID.
- Powertools for AWS Lambda (Python, TypeScript, Java, .NET) has an idempotency utility built on this pattern, plus structured logging, metrics and tracing helpers. Prefer it to hand-rolled versions.
- **Do not write to DynamoDB and then publish an event** as two independent calls. Write the state change (and an event record) in one transaction, and publish from DynamoDB Streams, directly or through EventBridge Pipes. That is the transactional outbox on AWS.

## Step Functions

- Use direct service integrations (DynamoDB, SQS, SNS, EventBridge, ECS, other state machines) instead of Lambda functions that only call one API.
- Give every Task a `Retry` with backoff, a cap and jitter (`JitterStrategy: FULL`) for transient errors, and a `Catch` that routes to compensation or a failure state.
- Sagas: each step that changes another service has a compensating step; run compensations in reverse order on failure and make them idempotent too.
- State payloads are size-limited; pass references to S3 objects rather than large data. For large fan-out use the distributed Map state.
- Use `.waitForTaskToken` for human approval or external callbacks, always with a heartbeat or timeout.
- Standard workflows bill per state transition, Express per duration and memory. High-volume short workflows usually belong on Express.

## APIs and security

- Authorize at the edge: IAM for service-to-service, JWT authorizers (Cognito or another OIDC provider) for users, Lambda authorizers only for custom logic, with result caching. Check object-level permissions in the handler as well (`../../launchguard/references/security-baseline.md`, controls 6 and 7).
- Set stage or route throttling, request size limits and, for REST APIs and CloudFront, AWS WAF where abuse is likely.
- One IAM role per function with only the actions and resources it uses. Grant through IaC grant helpers, review every `*`.
- Secrets live in Secrets Manager or SSM Parameter Store (SecureString), fetched at init and cached with a TTL. Environment variables are encrypted at rest, but anyone with read access to the function configuration can read them.
- Verify webhook signatures over the raw request body before parsing, and acknowledge quickly by queueing the work.

## Observability

- Structured JSON logs (Lambda's JSON log format or Powertools Logger) with the request ID and a correlation ID carried through queue messages and events; set log retention on every log group.
- Alarms that matter: function errors and throttles, duration near the timeout, SQS age of oldest message, DLQ depth above zero, stream iterator age, Step Functions failed or timed-out executions, API 5xx rate and latency against the objective. Design follows `../../engineering-practices/references/observability.md`; alarm mechanics are in `monitoring-stack.md`.
- Trace across services with X-Ray or OpenTelemetry (the AWS Distro for OpenTelemetry), propagating context through message attributes.

## Testing and deployment

- Unit-test handlers with recorded sample events and fakes for AWS clients. Local emulation (`sam local invoke`, container-based emulators) helps with packaging but does not reproduce IAM, quotas or service behavior.
- Integration tests run in an ephemeral stack per branch or developer, created only with the user's approval and destroyed afterwards; they cost real money.
- Contract-test event schemas between producers and consumers (EventBridge schema registry or JSON Schema in the repository), and version events additively.
- Release functions through versions and aliases with gradual traffic shifting (CodeDeploy canary or linear, with alarms that roll back), as described in `../../engineering-practices/references/ci-and-release.md`.

## Hosting AI agents on AWS (Bedrock AgentCore)

Amazon Bedrock AgentCore (launched 2025) is a set of managed services for running agents: a runtime that hosts agent containers with an isolated environment per session, a gateway that exposes APIs and Lambda functions as MCP tools, identity for inbound authentication and outbound credentials, memory, sandboxed code interpreter and browser tools, and observability. Service names, limits and regional availability are still changing; read the current documentation and `aws bedrock-agentcore-control help` for the installed CLI.

- Creating or updating runtimes, endpoints, gateways, targets or credential providers is a deployment. Prepare the commands or IaC and run them only with the user's go-ahead, after confirming the account with `aws sts get-caller-identity`.
- Never pass an API key on a command line (it lands in shell history and process lists) or in the chat. Have the user create credential providers through a guided script (`../../agent-safety/references/guided-setup.md`) or the console, and reference them by ARN.
- Separate credentials and execution roles per environment; a shared key across development and production makes every rotation an outage and every leak a production incident.
- Each tool exposed to an agent is a capability a model can invoke with attacker-influenced input. Scope its IAM role and outbound credentials narrowly, rate-limit it, log every call, and treat tool output as untrusted data. Designing the tool interface itself is covered in `../../builder-tools/GUIDE.md`.
- Inbound access uses IAM (SigV4) or OAuth/JWT; never leave an agent endpoint callable without authentication.
- Use runtime versions and named endpoints to roll out and roll back agent changes, and budget for per-session compute: idle sessions and long-running agents cost money until they time out.

## Done when

- [ ] Each integration's delivery guarantee is written down and every consumer is idempotent through an atomic claim.
- [ ] Every queue and async source has a bounded retry policy, a dead-letter queue or failure destination, and an alarm on it.
- [ ] Visibility timeouts, function timeouts and downstream timeouts are consistent; concurrency is capped where a dependency is fragile.
- [ ] Roles are per function and least privilege; secrets come from a secret store; log retention is set.
- [ ] Nothing was deployed, invoked against production or given credentials without the user's go-ahead.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Messages processed twice or out of order | At-least-once delivery, visibility timeout too short | Idempotent claim; visibility timeout at least six times the function timeout |
| Whole SQS batch retried for one bad message | Partial batch responses not enabled | `ReportBatchItemFailures` plus per-record handling |
| Stream consumer stalls for hours | Poison record blocks the shard | Bisect on error, bounded retries, on-failure destination, iterator age alarm |
| Database connection exhaustion during spikes | Unbounded Lambda concurrency | Reserved or maximum concurrency, RDS Proxy, or queue buffering |
| Events lost when the function crashed after the database write | Dual write to database and bus | Publish from DynamoDB Streams or an outbox table |
| Surprise bill on a quiet service | Provisioned concurrency, NAT data processing, never-expiring logs | Remove idle provisioned concurrency, VPC endpoints, log retention |
