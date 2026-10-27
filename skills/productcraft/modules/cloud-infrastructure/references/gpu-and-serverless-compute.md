# GPU and serverless compute platforms

Read this when you run Python or containers on a serverless compute platform (functions or containers that scale from zero, including platforms that offer GPUs per function), size GPUs for inference or training, serve a model behind an autoscaled endpoint, or run batch fan-out or scheduled jobs on such a platform.

This file covers the infrastructure side; training, fine-tuning, evaluation and model release practice are in `../../ml-engineering/GUIDE.md` and `../../ml-engineering/references/mlops.md`. Platforms differ in names and limits, but the decisions are the same. Read the platform's current documentation for its exact API, GPU types, limits and prices; they change often. Authenticating the platform CLI is the user's step (`../../agent-safety/references/guided-setup.md`); the agent never handles the token.

## Choose the runtime

| Workload | Good fit | Poor fit |
|---|---|---|
| Spiky or occasional inference, demos, internal tools | Serverless GPU functions or containers that scale to zero | Steady high load around the clock (a reserved node or managed cluster is cheaper) |
| Large embarrassingly parallel batch jobs | Serverless fan-out (`map` over inputs), cloud batch services | Jobs needing tight multi-node communication |
| Multi-node training | Managed training services or a Kubernetes cluster with fast interconnect | Per-request serverless functions |
| Latency-critical serving with strict p99 | Always-warm replicas (minimum instances or a dedicated deployment) | Pure scale-from-zero, because of cold starts |
| Long-running stateful services | Containers on a managed platform or Kubernetes | Functions with execution time limits |

## Sizing GPUs

- **Memory first.** Weights need roughly parameters times bytes per parameter: 2 bytes in fp16 or bf16, 1 in int8, about 0.5 in 4-bit. A 7-billion-parameter model in bf16 needs about 14 GB for weights alone. Add the KV cache (grows with batch size and context length), activations and framework overhead; leave 20 to 30 percent headroom.
- **Training needs far more**: full fine-tuning with Adam in mixed precision holds weights, gradients and optimizer state, commonly around 16 bytes per parameter before activations. Parameter-efficient methods (LoRA and its quantized variants) cut this sharply.
- **Then throughput.** Measure tokens or items per second per GPU type on the real model and batch size, and compare cost per unit of work, not cost per hour. A pricier GPU that finishes three times faster is cheaper.
- Multi-GPU per container is for models that do not fit one GPU or need the throughput; it brings longer scheduling waits and tensor-parallel configuration. Benchmark a single GPU first.
- Some platforms substitute a newer or larger GPU for the one requested; pin the exact type when benchmarking.

## Cold starts and warm capacity

A cold start downloads the image, starts the runtime, loads weights into GPU memory and warms up. For large models this takes tens of seconds to minutes.

- Keep images small and layered: system packages and Python dependencies in early layers, code last.
- Do not download weights on every start. Bake them into the image for small models, or store them on the platform's persistent volume or object storage close to the compute, and load once per container in a startup hook, not per request.
- Load the model at container start and reuse it across requests; request handlers only run inference.
- Memory or GPU snapshotting, where the platform offers it, can cut start time further; test that restored containers produce correct output and fresh random seeds.
- Warm capacity (minimum containers, idle buffers, keep-alive windows) trades money for latency. Every warm GPU container bills while idle. Set it from the latency objective and traffic pattern, and schedule it down outside working hours where traffic allows.

## Concurrency, batching and limits

- Let one container handle several requests when the model server batches (vLLM, NVIDIA Triton or the framework's dynamic batching); GPUs are underused at one request at a time. Tune the per-container concurrency target with a load test.
- Set a maximum container count. Unbounded autoscaling turns a traffic spike or a retry storm into a large bill and can exhaust downstream databases.
- Set a timeout per function from measured latency, and handle the platform's execution time limit for long jobs by checkpointing and resuming.
- Retries on these platforms re-run the whole function. Make functions idempotent (write outputs to a deterministic key, skip work already done) before enabling automatic retries.

## Data and state

- Containers are ephemeral; local disk disappears. Persist outputs to object storage or a database, and checkpoint long jobs at intervals so preemption or timeout costs minutes, not hours.
- Persistent volumes on serverless platforms often have explicit commit and reload semantics and weaker consistency than a local disk. Read the platform's rules before sharing a volume between concurrent writers.
- Keep data and compute in the same region; cross-region and internet egress for large datasets and model weights add cost and latency.

## Endpoints, schedules and secrets

- Web endpoints are public by default on many platforms. Require authentication (platform tokens, a gateway with auth, or a signed request) before exposing a model, and rate-limit it; an open GPU endpoint is an open invoice.
- Treat model inputs as untrusted: limit payload sizes, validate formats, and keep the endpoint's identity away from data it does not need.
- Scheduled functions need overlap protection and idempotency like any cron job; record the last successful run so missed runs are visible.
- Secrets come from the platform's secret store, injected as environment variables or files at runtime, and are created by the user. Never pass them as function arguments, bake them into images or print them in logs.

## Spot and preemptible GPUs

Preemptible capacity is much cheaper and can be taken back at short notice. Use it for training and batch with checkpointing and automatic resume, never for the only replica of a latency-sensitive endpoint. Test a preemption (kill the worker) and confirm the job resumes from the last checkpoint.

## Cost control

- Set a spending limit or budget alert on the platform account before the first GPU run; many platforms support hard limits.
- Report cost per unit of work (per thousand inferences, per training epoch) from the platform's usage data, not estimates.
- Tear down deployments and warm pools that are no longer needed, with the user's approval. See `cloud-cost.md` for the general method.

## Verify

- A smoke test that calls the deployed function or endpoint with a known input and checks the output, run after every deploy.
- A load test at expected peak (with approval, because it costs money) that records p50, p95 and p99 latency, cold-start time, throughput per container and cost per unit.
- A failure test: kill a container mid-request and preempt a batch worker; confirm retries are safe and checkpoints resume.

## Done when

- [ ] GPU type and count are justified by measured memory and throughput, with the cost per unit of work.
- [ ] Weights load once per container from storage close to the compute; cold-start time is measured.
- [ ] Maximum scale, timeouts, idempotent retries, authentication on endpoints and a spending limit are configured.
- [ ] Deploys, load tests and GPU runs happened only with the user's go-ahead, and idle warm capacity was reviewed.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Every request takes a minute after idle periods | Scale to zero plus weight download at start | Cache weights on a volume or in the image; minimum warm containers if the objective needs it |
| CUDA out-of-memory under load | KV cache grows with batch and context | Cap batch size and context; a larger GPU or quantization |
| Bill much higher than expected | Warm containers or unbounded autoscaling | Maximum container count; scheduled warm capacity; spending limit |
| Duplicate outputs after failures | Automatic retries of a non-idempotent function | Deterministic output keys; skip completed work |
| Concurrent jobs corrupt shared files | Volume consistency weaker than assumed | One writer per file; object storage with unique keys |
