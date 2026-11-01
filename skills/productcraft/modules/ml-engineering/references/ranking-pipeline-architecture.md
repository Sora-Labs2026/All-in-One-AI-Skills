# Ranking pipeline architecture

Read this when you build or restructure the serving code that picks the top items for a user or a context: a feed, recommendations, "related items", notification triage, search re-ranking, task prioritization, or the selection stage of a retrieval system. Models, data splits and offline and online evaluation of recommenders are in `recommender-systems.md`; retrieval for language models in `rag-systems.md`. This file is about the plumbing around the scoring model.

## Six stages

| Stage | Job | Runs | Notes |
|---|---|---|---|
| 1. Sources | Produce candidates: followed or owned items, similar items, trending, a retrieval index, a rules list | In parallel, each with a timeout | Several cheap, high-recall sources beat one clever one |
| 2. Hydration | Attach what later stages need: metadata, eligibility facts, features | In parallel, batched per stage | Fetch once per request, not once per candidate |
| 3. Filters | Remove what must never be shown: blocked, already seen, expired, out of stock, not permitted for this user, legally restricted | In sequence, cheapest and most universal first | Hard constraints live here, never as score penalties |
| 4. Scoring | Model scores, then combiners, diversity adjustments and explicit business rules | In sequence; later scorers may read earlier scores | Each step writes its own named score |
| 5. Selection | Sort by the final score, take the top K, mix sources or apply slot rules | Once | Deterministic given the scores |
| 6. Side effects | Log impressions, remember served items, update counters, emit events | Asynchronously, after the response | Must never block or fail the request |

Why this order: you need to know what exists before paying to enrich it; filters need hydrated facts; scoring is the expensive part, so ineligible items are dropped first; selecting after scoring keeps scoring deterministic and cacheable; and side effects come last because users should not wait for logging.

## A scaffold

```python
import asyncio
from dataclasses import dataclass, field

@dataclass
class Candidate:
    item_id: str
    source: str
    features: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    final: float = 0.0

@dataclass
class Request:
    user_id: str
    context: dict
    k: int = 20

class Pipeline:
    def __init__(self, sources, hydrators, filters, scorers, selector, side_effects, timeout_s=0.08):
        self.sources, self.hydrators, self.filters = sources, hydrators, filters
        self.scorers, self.selector, self.side_effects = scorers, selector, side_effects
        self.timeout_s = timeout_s
        self._background = set()                       # keep references to fire-and-forget tasks
        self.trace = {}                                # per-stage counts for the last request

    async def _guarded(self, coro, default, name):
        try:
            return await asyncio.wait_for(coro, self.timeout_s)
        except Exception:                              # timeout or failure: degrade and record it
            self.trace.setdefault("degraded", []).append(name)
            return default

    async def run(self, req: Request) -> list:
        self.trace = {}
        batches = await asyncio.gather(*(self._guarded(s.fetch(req), [], type(s).__name__) for s in self.sources))
        seen, cands = set(), []
        for c in (c for batch in batches for c in batch):
            if c.item_id not in seen:                  # first source wins; record the others if needed
                seen.add(c.item_id)
                cands.append(c)
        self.trace["candidates"] = len(cands)
        updates = await asyncio.gather(*(self._guarded(h.hydrate(req, cands), {}, type(h).__name__) for h in self.hydrators))
        for update in updates:                         # each hydrator returns {item_id: {feature: value}}
            for c in cands:
                c.features.update(update.get(c.item_id, {}))
        for f in self.filters:
            before = len(cands)
            cands = [c for c in cands if f.keep(req, c)]
            self.trace[f"dropped_by_{type(f).__name__}"] = before - len(cands)
        for scorer in self.scorers:
            scorer.score(req, cands)                   # writes c.scores[name] and may set c.final
        chosen = self.selector.select(req, cands)
        for effect in self.side_effects:
            task = asyncio.get_running_loop().create_task(effect.record(req, chosen))
            self._background.add(task)
            task.add_done_callback(self._background.discard)
        return chosen
```

- Every stage has a small interface (`fetch`, `hydrate`, `keep`, `score`, `select`, `record`) and its own unit tests with fixed inputs.
- The trace (candidates per source, drops per filter, degraded stages) is emitted as metrics and attached to debug responses; it is how you answer "why did I see this?" and "why is the feed empty?".
- Side-effect handlers catch and count their own errors; a bounded queue drops (and counts) work under overload instead of growing without limit.

## Scoring: one score or many

- **Single relevance score:** one model predicts one target. Simple; changing behavior means retraining.
- **Several predicted actions combined with weights:** models predict the probabilities of separate actions (open, save, share, hide, report), and the final score is a weighted sum with negative weights for unwanted actions. Behavior changes by adjusting weights in configuration, without retraining. Each prediction must be calibrated, or the weights mean nothing; weight changes are product decisions, versioned and evaluated like model changes (offline replay, then an online experiment).
- **Score candidates independently** of each other by default: deterministic, cacheable and easy to debug. Put list-aware logic (diversity, de-duplication of near-identical items, author or category caps) in a separate re-ranking step after the model.
- **Business rules are explicit stages** with names in the trace (freshness boosts, contractual placements, editorial pins), never hidden inside model features where nobody can audit them.
- Common re-ranking tools: maximal marginal relevance for diversity, per-category quotas, position caps for repeated sources, and a small randomized exploration share to keep learning (`recommender-systems.md`).

## Online, offline or both

- **Offline:** run the whole pipeline on a schedule and cache results per user; fast and cheap to serve, stale between runs. Good for emails and home pages that change slowly.
- **Online:** run per request within a latency budget (often a few hundred milliseconds end to end); fresh and context-aware, more infrastructure.
- **Hybrid:** precompute candidates offline, filter and rank online. The usual production choice.
- Give each stage a time budget. When a source or scorer times out, degrade (fewer sources, a cached ranking, popularity) and record it, rather than failing the request.

## Logging for learning

Log impressions, not only clicks: request id, user or session id (pseudonymous where possible), item ids in shown order with positions, every named score, model and weight versions, and degraded stages. Without what was shown and where, you cannot correct position bias, build training data with negatives, or replay requests to evaluate a change offline.

## The same shape elsewhere

| Use | Sources | Filters | Scoring | Selection |
|---|---|---|---|---|
| Notification triage | Pending events | Quiet hours, frequency caps, user settings | Predicted open minus predicted annoyance | Top one, or none below a threshold |
| Retrieval for a language model | Dense and keyword search | Permission filters inside the query | Cross-encoder reranker | Fill a token budget |
| Task prioritization | Open tasks | Assignee, blocked, done | Due date, impact, predicted delay | Ordered list with explanations |

## Safety and privacy

- Permission, age, legal and user-block filters run before scoring and are tested with fixtures that must be dropped.
- Avoid sensitive inferences (health, religion, sexuality, finances) as features or explanations without consent and legal review (`../../legal-ready/GUIDE.md`); give users controls ("not interested", reset history).
- Explanations come from the trace (the source and the rules that applied), not from text generated after the fact.

## Checks (done when)

- [ ] Each stage has an interface, tests with fixed inputs, a time budget and a degradation path.
- [ ] Hard constraints are filters with tests; business rules are named, logged stages.
- [ ] Scoring is per candidate; list-aware logic runs in a separate re-ranking step.
- [ ] Combined scores use calibrated predictions and versioned weights; weight changes are evaluated.
- [ ] Impressions, positions, scores and versions are logged asynchronously; side effects never block the response.
- [ ] Per-stage counts are exported as metrics; a replay of logged requests reproduces rankings.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Scoring before filtering | Filter first; score only eligible candidates |
| Blocked items demoted instead of removed | Hard constraints as filters |
| Synchronous impression logging adds latency | Asynchronous side effects with a bounded queue |
| One opaque score nobody can tune | Named per-action predictions and versioned weights |
| Business rules buried in features | Explicit, traced re-ranking stages |
| Empty feed with no explanation | Per-stage trace and degradation metrics |
