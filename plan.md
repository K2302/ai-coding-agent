You are a senior Staff Software Engineer.

Build a Retrieval Fusion Engine for a Java Code Intelligence Platform.

Current repository scale:

Files: 8921
Classes: 9175
Methods: 227693
Graph Nodes: 246276
Graph Edges: 283330

Existing systems already implemented:

1. BM25 Search
2. Vector Search (BGE embeddings)
3. Symbol Search
4. Dependency Graph
5. Endpoint Extraction

Goal:

Combine all retrieval signals into a single ranked result set.

---

# Existing APIs

BM25

```python
bm25_search(
    query: str,
    top_k: int
)
Returns:

[
  {
    "id":"ApplicantService.generateDeepLink",
    "score":0.92
  }
]
Vector

vector_search(
    query: str,
    top_k: int
)

Returns:

[
  {
    "id":"ApplicantService.generateDeepLink",
    "score":0.88
  }
]

Symbol

search_symbols(
    query: str,
    limit: int
)

Returns:

[
  {
    "id":"ApplicantService.generateDeepLink",
    "score":1.0
  }
]

Graph

find_callers(symbol)
find_callees(symbol)
find_related_endpoints(symbol)
find_implementations(symbol)
Objective

Implement:

retrieve(
    query: str,
    top_k: int = 20
)

Pipeline:

Query
↓
BM25
↓
Vector
↓
Symbol
↓
Merge
↓
Score Fusion
↓
Graph Expansion
↓
Graph Boosting
↓
Ranking
↓
Top Results

Task 1: Parallel Retrieval

Run:

bm25_search(query, 200)

vector_search(query, 200)

search_symbols(query, 100)

in parallel.

Use:

concurrent.futures.ThreadPoolExecutor

Target:

< 500ms

for retrieval phase.

Task 2: Score Normalization

Normalize all scores to:

0 → 1

Implement:

normalize_scores(results)

Example:

Input:

[
  {"score":15},
  {"score":8},
  {"score":3}
]

Output:

[
  {"score":1.0},
  {"score":0.53},
  {"score":0.20}
]
Task 3: Result Merge

Deduplicate using:

id

Example:

ApplicantService.generateDeepLink

may appear in:

BM25
Vector
Symbol

Store:

{
  "id":"ApplicantService.generateDeepLink",

  "bm25_score":0.92,

  "vector_score":0.88,

  "symbol_score":1.0
}
Task 4: Weighted Fusion

Implement:

compute_final_score()

Formula:

score = (
    0.30 * bm25_score +
    0.15 * vector_score +
    0.35 * symbol_score
)

Reason:

Symbol matches are strongest.

BM25 is second.

Embeddings are supporting signal.

Task 5: Graph Expansion

Take Top 50 fused results.

For each result:

Expand:

find_callers()

find_callees()

find_related_endpoints()

find_implementations()

Depth:

1

Store graph candidates.

Example:

ApplicantService.generateDeepLink

expands to:

ApplicantController.createApplicant

NotificationService.sendEmail

EmailTemplateService.buildTemplate
Task 6: Graph Boosting

If candidate discovered via graph:

Apply:

graph_score = 0.20

If multiple graph paths reach same node:

Accumulate score.

Example:

graph_boost =
0.20 * caller_hits +
0.20 * callee_hits +
0.10 * endpoint_hits
Task 7: Final Ranking

Final formula:

final_score =
retrieval_score +
graph_boost

Sort descending.

Return:

top_k
Task 8: Explainability

For every result generate:

{
  "id":"ApplicantService.generateDeepLink",

  "score":1.15,

  "reasons":[
    "BM25 match",
    "Symbol match",
    "Called by NotificationService.sendEmail",
    "Used by POST /applicant endpoint"
  ]
}

This explanation is mandatory.

Task 9: Retrieval Report

Return:

{
  "query":"applicant deep link email",

  "results":[...]

}

Include:

{
  "bm25_hits":200,
  "vector_hits":200,
  "symbol_hits":34,
  "graph_expansions":182
}
Task 10: Project Structure

Create:

src/retrieval/

    fusion.py

    graph_expansion.py

    scoring.py

    retrieval_engine.py

    explainability.py
Requirements

Use:

pathlib
dataclasses
type hints
logging

Avoid:

global variables
full scans
duplicated logic