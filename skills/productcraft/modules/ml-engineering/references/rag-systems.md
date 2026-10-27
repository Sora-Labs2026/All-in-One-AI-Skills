# Retrieval-augmented generation (RAG): architecture

Read this when an application answers questions or drafts text from a body of documents (help center, policies, code, contracts, tickets, research) by retrieving passages and passing them to a language model. Evaluation is in `llm-evaluation.md`, prompt writing in `prompt-design.md`, and the security review of LLM features in `../../code-security-review/references/vulnerability-classes.md` (section "LLM and agent risks").

## Decide what you are building

- **Does it need retrieval?** If the knowledge fits comfortably in the model's context window, changes rarely and is shared by all users, putting it in the prompt (with prompt caching where the provider supports it) is simpler. Retrieval earns its complexity when the corpus is large, changes often, is permissioned per user, or answers must cite sources.
- **What does a good answer look like?** Collect 50 to 200 real questions with the documents that answer them and reference answers before building. This set drives every later choice (`llm-evaluation.md`).
- **Who can see what?** Write down the access model (tenants, roles, document ACLs) first; it shapes the index design.

## Reference architecture

```
Ingestion:  source connectors -> parse and clean -> chunk -> enrich metadata -> embed -> index (vector + keyword)
Query:      user question -> (rewrite) -> filtered hybrid retrieval -> fuse -> rerank -> select context
            -> prompt with citations -> generate -> validate (citations, format, policy) -> answer + sources
Feedback:   logs of queries, retrieved ids, answers, user ratings -> evaluation set growth
```

Start with the simplest version that meets the evaluation target: good parsing, structure-aware chunks, hybrid retrieval and a reranker cover most needs. Add query rewriting, multi-step retrieval or agents only when evaluation shows the simple path fails on a class of questions.

## Ingestion

**Parsing** decides quality more than any later step. Extract text with structure (headings, lists, tables, code blocks, page numbers). Check a sample of parsed output by eye, especially PDFs with columns, tables and scanned pages (scans need OCR). Office and PDF tooling is covered in `../../documents/GUIDE.md`.

**Chunking:**
- Split on document structure first (sections, headings, paragraphs, functions for code), then by size. A starting point is 200 to 500 tokens with 10% to 20% overlap; tune on the evaluation set, not by intuition.
- Prepend context that the chunk lacks on its own: document title, section path, product or version. A chunk saying "it expires after 30 days" is useless without knowing what "it" is.
- Keep tables whole when possible (or row groups with the header repeated) and code blocks intact.
- Store a stable chunk id derived from (document id, document version, chunk position), not from the text alone; identical text in two tenants' documents must not collide.

**Metadata** on every chunk: source id and URL, title, section, timestamps (created, updated, effective dates), language, tenant and access-control fields, document version, embedding model and version.

**Freshness and deletion:** re-index changed documents incrementally (content hashes per document), remove chunks of deleted or access-revoked documents promptly, and be able to prove deletion for privacy requests.

## Embeddings

- Choose with your own evaluation set. Public leaderboards (such as MTEB) are a shortlist, not a decision: domain, language and query style change the ranking.
- Follow the model card's input conventions (query and passage prefixes or instructions); skipping them silently degrades recall.
- Normalize vectors for cosine similarity; use the same model for queries and documents.
- Record the embedding model name and revision with the index. Changing the model means re-embedding everything into a new index and switching over after evaluation; vectors from different models are not comparable.
- Hosted embedding APIs send document text to a third party: check data terms and residency with the owner. Open models (sentence-transformers family) run locally.
- Dimension reduction (Matryoshka-style truncation where the model supports it, or quantization) saves storage; measure the recall cost.

## Indexes and stores

| Option | Fits when |
|---|---|
| PostgreSQL with pgvector (HNSW or IVFFlat) plus Postgres full-text search | Data already in Postgres, up to millions of chunks, strong need for transactional consistency and SQL filters |
| OpenSearch or Elasticsearch (BM25 plus vector fields) | Existing search infrastructure, strong keyword search, large scale |
| Dedicated vector databases (Qdrant, Weaviate, Milvus and others) | Large vector workloads, built-in hybrid search and filtering, horizontal scale |
| Embedded libraries (FAISS, LanceDB, Chroma) | Prototypes, single-node or offline use |

- Approximate indexes trade recall for speed: tune HNSW `ef_search` (or the equivalent) by measuring recall against exact search on a sample.
- Filtering: prefer engines that apply filters during the vector search. Post-filtering a top-k list can return few or zero results for selective filters.
- Plan capacity from chunk count x vector size x index overhead, plus replicas.

## Retrieval

**Hybrid search.** Dense vectors capture meaning; keyword search (BM25) catches exact terms, codes, names and rare words. Run both and fuse with reciprocal rank fusion, which needs no score calibration:

```python
def rrf(result_lists, k=60, top_n=50):
    """result_lists: ranked lists of chunk ids, best first. Returns fused ids."""
    scores = {}
    for ranked in result_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)[:top_n]

candidates = rrf([dense_search(q, filters, 100), keyword_search(q, filters, 100)])
```

Do not add raw cosine similarities to raw BM25 scores; they are on different scales.

**Reranking.** A cross-encoder reranker (open cross-encoder models such as the BGE rerankers, or a hosted rerank API) scores each (question, chunk) pair jointly and usually gives the largest quality gain after hybrid search. Rerank 50 to 100 candidates, keep the top 5 to 10. Measure the latency it adds.

**Query transformation** (use when evaluation shows the need):
- Rewrite conversational follow-ups into standalone questions using the chat history.
- Decompose multi-part questions into sub-queries.
- Hypothetical-answer embedding (generate a draft answer, embed it, search with it) can help short or vague queries; it can also drift, so measure.

**Context selection:** deduplicate overlapping chunks, merge neighbors from the same section, order by relevance or by document order, and stay within a token budget. More context is not always better: irrelevant passages distract the model and raise cost.

## Access control and multi-tenancy

- Apply the caller's tenant and permission filters **inside the retrieval query**, every time, from server-side identity, never from text the user or model supplies.
- Separate indexes or namespaces per tenant for strong isolation; a shared index with mandatory filters for many small tenants. Test cross-tenant leakage explicitly with a query that matches another tenant's document.
- Caches (of retrieval results or answers) must be keyed by everything that changes the result, including the permission scope.

## Generation

- The prompt states: answer only from the provided sources, cite source ids for each claim, say when the sources do not contain the answer, and how to handle conflicting sources (prefer newer or authoritative ones as defined by the owner). Details in `prompt-design.md`.
- Mark retrieved text clearly as data (delimiters, a separate message or content block). Retrieved documents can contain instructions written to manipulate the model (prompt injection); they must never change the system's behavior or permissions.
- Validate outputs: every cited id must be one of the provided chunks; citations should support the sentence (sample-check with an evaluator); structured outputs validated against a schema.
- Return sources to the user with links, so answers can be verified.
- Abstain when retrieval finds nothing relevant (a reranker score threshold calibrated on the evaluation set) rather than letting the model answer from memory.

## Operations

- Log per request: query, filters applied, retrieved ids with scores, reranked ids, prompt version, model, token counts, latency per stage, answer and citations, user feedback. Redact personal data in logs per the owner's policy.
- Watch cost per answer (embedding, reranking, generation tokens) and latency per stage; set timeouts and fallbacks per dependency (`../../engineering-practices/references/resilience.md`).
- Re-run the evaluation set on every change to chunking, embeddings, retrieval, prompts or models, and before switching model versions.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Garbage parsing of PDFs and tables | Inspect parsed samples; structure-aware parsing; OCR for scans |
| Chunks without context ("it", "this plan") | Prepend title and section path |
| Content-hash ids that collide across tenants or versions | Ids from document id, version and position |
| Dense-only retrieval misses codes and names | Hybrid search with RRF |
| Raw scores from different retrievers added together | Rank fusion |
| Permission filter applied after top-k or taken from model output | Server-side filters inside the query; cross-tenant tests |
| Model answers from memory when retrieval fails | Relevance threshold and explicit abstention |
| Embedding model changed in place | New index, evaluation, switch-over |

## Done when

- [ ] An evaluation set with questions, relevant sources and reference answers exists and is versioned.
- [ ] Retrieval recall@k and answer quality meet agreed targets (`llm-evaluation.md`), compared with a BM25-only baseline.
- [ ] Access filters are enforced server-side in every retrieval and covered by cross-tenant tests.
- [ ] Answers cite real retrieved sources, abstain when unsupported, and treat retrieved text as data.
- [ ] Ingestion handles updates and deletions; embedding model and versions are recorded with the index.
