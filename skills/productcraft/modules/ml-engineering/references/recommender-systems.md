# Recommendation systems

Read this when you build or improve a feature that ranks items for a user: product, content, job or listing recommendations, "related items", personalized search ranking, or an assistant that recommends things in conversation. Ranking metrics come from `../scripts/rank_metrics.py`; evaluation rules from `evaluation-and-leakage.md`.

## Start from the product question

- What is recommended, to whom, where on the screen, and what the user does next (click, buy, watch to the end, apply, ignore).
- Which outcome matters to the owner: long-term satisfaction, purchases, retention, diversity of exposure. Clicks are an easy proxy that can reward clickbait.
- Hard constraints: availability, region, age ratings, inventory, legal restrictions, user-blocked items. These are filters, enforced outside the model.
- Cold start: how many new users and new items appear per day.

## Baselines first

| Baseline | What it is | Why it matters |
|---|---|---|
| Popularity | Most interacted items in a recent window, per segment if useful | Surprisingly hard to beat on accuracy metrics; the floor every model must clear |
| Recently viewed / repeat | Items the user already engaged with | Strong for repeat-purchase and re-watch domains |
| Item-to-item co-occurrence | "People who interacted with X also interacted with Y" | Simple, explainable, good for related-item widgets |
| Content similarity | Items similar in text, category or embedding to what the user liked | Works for new items with no interactions |

## Model families

| Family | Tools | Good for | Watch out |
|---|---|---|---|
| Matrix factorization for implicit feedback (ALS, BPR) | `implicit`, Spark MLlib ALS | Medium to large interaction data, fast candidate generation | Cold start; needs confidence weighting of implicit signals |
| Item-based nearest neighbors | Sparse similarity, approximate nearest neighbor search | Related items, explainable | Popularity bias |
| Two-tower retrieval | User and item encoders (PyTorch, TensorFlow Recommenders, TorchRec), vectors in an ANN index (Faiss, ScaNN, a vector database) | Large catalogs, features for cold start | Negative sampling choices dominate quality |
| Learning-to-rank re-ranker | Gradient boosting with ranking objectives (LightGBM `lambdarank`, XGBoost `rank:ndcg`), or a neural ranker | Second stage over a few hundred candidates, rich features | Needs logged impressions, not only clicks |
| Sequential models | Transformer or RNN over the interaction sequence | Session-based and next-item prediction | Data-hungry; compare with co-occurrence and recency baselines |
| LLM-assisted recommendation | Language model for conversational preference elicitation, explanations, or re-ranking a small candidate list | Conversational products, cold start with rich text | Cost, latency, hallucinated items; never let it invent catalog entries |

Production systems usually have stages: **candidate generation** (cheap, high recall, several sources) then **ranking** (expensive, precise) then **business rules and diversity** (filters, deduplication, freshness, fairness of exposure).

## Data and splits

- Implicit feedback (views, clicks, purchases) is positive-only and biased by what was shown. Non-interaction is not dislike. Log impressions so you know what the user saw and skipped.
- **Split by time:** train on interactions before a cut-off, evaluate on later interactions. Random splits leak the future (the model sees later behavior of the same user) and inflate scores.
- Leave-last-out per user is acceptable for sequential tasks if every training interaction precedes the test one in time.
- Remove from the candidate list items the user already interacted with in training, unless repeats are a legitimate recommendation in the domain; say which choice you made.
- Filter bots, test accounts and duplicated events before training.

## Offline evaluation

- Metrics: recall@k and nDCG@k for ranking quality, hit rate@k, MRR for single-target tasks, plus **coverage** (share of the catalog ever recommended), **novelty** or popularity of recommended items, and **diversity** within lists.
- Rank against the **full catalog** (or all eligible items). Metrics computed against a small random sample of negatives can rank models differently from full-catalog metrics; if sampling is unavoidable for cost, say so and use many negatives.
- Evaluate by segment: new versus returning users, heavy versus light users, new versus old items. Averages are dominated by heavy users.
- Report intervals over users (bootstrap) and compare systems with paired tests on per-user scores.

```bash
python3 <productcraft>/modules/ml-engineering/scripts/rank_metrics.py run.jsonl --k 10,50 --catalog-size 120000 --ci
python3 <productcraft>/modules/ml-engineering/scripts/rank_metrics.py base.jsonl --k 10 --per-query > base.csv
python3 <productcraft>/modules/ml-engineering/scripts/rank_metrics.py new.jsonl --k 10 --per-query > new.csv
python3 <productcraft>/modules/ml-engineering/scripts/compare_scores.py bootstrap --a-csv base.csv --b-csv new.csv --key query --value ndcg@10
```

Each JSONL line holds one user (or query) with `relevant` (held-out interactions) and `retrieved` (the ranked list).

Offline gains predict online gains only loosely. Treat offline evaluation as a filter and confirm with an online experiment.

## Online evaluation

- A/B test with user-level randomization and a pre-registered primary metric (for example purchases or long-term engagement per user) plus guardrails (complaints, returns, unsubscribes, latency). Follow `statistical-inference.md` on sample size and peeking.
- Interleaving (mixing two rankers' results in one list) detects ranking preferences with fewer users than A/B tests; use it for ranker comparisons, then confirm impact with an A/B test.
- Position bias: items shown higher get more clicks regardless of quality. Account for it when learning from logs (randomized positions on a small share of traffic, or position-aware models), and never compare click-through rates of items shown in different positions without correction.

## Feedback loops and responsibility

- Recommenders shape the data they learn from: popular items get more exposure and more interactions. Keep a small exploration share, cap repeated exposure, and monitor catalog coverage over time.
- Avoid engagement traps: optimizing pure time-on-site or click rate can promote low-quality or harmful content. Agree with the owner on quality signals and guardrails (see `../../ethical-persuasion.md` for honest persuasion in product surfaces).
- Sensitive inferences: recommendations can reveal or infer health, religion, sexuality or finances. Avoid using or exposing such signals without explicit consent and legal review (`../../legal-ready/GUIDE.md`).
- Give users controls: "not interested", remove from history, reset, and a non-personalized option where regulations require one.

## Explanations and conversational recommendation

- Explanations must be true to the system: "because you watched X" only if X actually drove the recommendation (co-occurrence or nearest-neighbor provenance). Do not generate plausible-sounding reasons after the fact.
- In a conversational recommender, collect preferences, hard constraints (budget, dietary needs, location, dates) and dislikes explicitly; confirm hard constraints before recommending; treat them as filters, not hints.
- Retrieve candidates from the real catalog and let the language model choose and explain among them. Never present an item that is not in the catalog, and never present a model's confidence number as a calibrated probability unless it has been calibrated.
- When nothing fits the constraints, say so and offer which constraint to relax.
- Third-party recommendation APIs: check data-sharing terms before sending user profiles, send the minimum, and handle rate limits and errors (see `../../engineering-practices/references/resilience.md`).

## Serving and scale

- Precompute candidates for batch-friendly surfaces (email, home page) and refresh on a schedule; compute online only what must react to the session.
- ANN indexes (HNSW, IVF-PQ) trade recall for speed; measure recall@k of the index against exact search on a sample when tuning.
- Cache per-user results with a short TTL keyed by user and context; invalidate on strong signals (purchase, "not interested").
- Latency budget per stage; degrade to popularity or cached lists when a stage times out, and log the fallback.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Random split of interactions | Time-based split |
| Sampled-negative metrics reported as if full-catalog | Full-catalog ranking, or state the sampling |
| Only accuracy metrics | Add coverage, novelty, diversity and segment results |
| Clicks optimized, satisfaction ignored | Agreed quality signals and guardrails |
| Language model recommends items not in the catalog | Retrieve from the catalog; validate every returned id |
| Explanations invented after the fact | Explanations from the actual provenance |

## Done when

- [ ] Popularity and co-occurrence baselines are reported on a time-based split.
- [ ] Metrics include ranking quality, coverage and segment breakdowns, with intervals and paired comparisons.
- [ ] Hard constraints are enforced as filters outside the model and tested.
- [ ] Online evaluation design (or shadow plan) and guardrails are written down.
- [ ] Privacy, sensitive inference and user controls were reviewed with the owner.
