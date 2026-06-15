
# Senior SDE Code Retrieval MVP

Multi-stage code intelligence pipeline for Java repositories — from raw AST parsing to fused retrieval with graph expansion.

## Dataset

| Metric | Value |
|---|---|
| Java files indexed | 8,921 |
| Classes | 9,175 |
| Methods | 227,693 |
| Entry points (EJB + Spring) | 29,273 |
| SQL queries | 2,341 |
| Dependency graph edges | 53,296 |
| FAISS vector dimensions | 384 (BGE-small) |
| Vectors in index | 27,773 |

## Pipeline Overview

```
Java Source
    ↓
AST Parser (build_index.py)  ──→  BM25 Index (Whoosh)
    ↓                                 ↓
JSON Metadata                     Vector Index (FAISS)
    ↓                                 ↓
Chunks (build_chunks.py)  ──→     Embeddings (BGE-small)
    ↓                                 ↓
Symbol Index ←───              Fusion Engine
                                    ↓
                              BM25 + Vector + Symbol
                                    ↓
                              Graph Expansion (callers/callees/endpoints)
                                    ↓
                              Ranked Results + Explainability
```

## Version History & Metrics

### V0 — Keyword Search (Baseline)

Simple term-frequency counting over symbol names.

| Metric | Value |
|---|---|
| Search method | `str.count()` per symbol |
| Latency | ~50ms |
| Precision | Low — no ranking, no NLP |
| Index size | N/A (no index) |

**Limitations:** No BM25, no embeddings, no symbol awareness, no graph.

---

### V1 — BM25 Index (Whoosh)

Replaced raw keyword matching with full-text BM25 using Whoosh. Custom CamelCase tokenizer for Java identifiers.

| Metric | Value |
|---|---|
| Index backend | Whoosh (BM25F) |
| Indexed fields | `name`, `content` (class + method names + imports + endpoints + SQL tables) |
| Index size | 77 MB |
| Latency (top-200) | ~3.8s cold / ~0.5s warm |
| Entities indexed | 9,175 classes + 227,693 methods + 6,056 imports + 28,724 endpoints + 2,341 tables |

**Improvement over V0:** BM25 ranking with IDF weighting, fast indexed search, CamelCase-aware tokenization.

---

### V2 — Vector Search (FAISS + BGE Embeddings)

Added dense retrieval via SentenceTransformer (BGE-small-en-v1.5) + FAISS flat index. Enabled semantic similarity search.

| Metric | Value |
|---|---|
| Embedding model | BAAI/bge-small-en-v1.5 (384-dim) |
| Index backend | FAISS (flat L2) |
| Vectors | 27,773 |
| Index size | 41 MB |
| Latency (top-200) | ~2.5s (embedding + search) |

**Improvement over V1:** Captures semantic similarity beyond keyword matching.

---

### V3 — Hybrid Search (BM25 + Vector + RRF + Reranker)

Fused BM25 and vector results via Reciprocal Rank Fusion, then reranked with cross-encoder.

| Metric | Value |
|---|---|
| Fusion method | RRF (k=60) |
| Reranker | SentenceTransformer bi-encoder (cosine) |
| Pool size | 100 per retriever |
| Final results | Top 50 |

**Improvement over V2:** Combines keyword precision + semantic recall, cross-encoder reranking improves top-result relevance.

---

### V4 — Retrieval Fusion Engine (Current)

Full pipeline: BM25 + Vector + Symbol + Graph expansion + Boosting + Explainability.

| Metric | Value |
|---|---|
| Retrieval signals | BM25 (200) + Vector (200) + Symbol (100) |
| Fusion weights | 0.30 BM25 + 0.15 Vector + 0.35 Symbol |
| Graph expansion depth | 1 (callers + callees + endpoints) |
| Graph cache size | 5,416 caller entries, 5,419 callee entries |
| Graph boost weights | +0.20/caller + 0.20/callee + 0.10/endpoint |
| Retrieval latency | ~2.9s (3 retrievers + graph cache) |
| Symbol index size | ~50 MB |
| BM25 index size | 77 MB |
| FAISS index size | 41 MB |
| **Total index size** | **~168 MB** |
| Graph expansions (per query) | 365–467 typical |
| Final ranking formula | `score = retrieval_score + graph_boost` |

**Improvement over V3:**
- Symbol search adds exact/prefix/substring class matches
- Graph expansion discovers relevant code outside the initial retrieval pool
- Explainability shows *why* each result was ranked (multi-signal reasons)
- ID normalization cross-links results across all 3 retrievers

### Build Index Benchmarks

Optimizations applied to `build_index.py` (see [`improvement.md`](improvement.md) for details):

#### altrecruitrpservice (558 files)

| Step | Time |
|---|---|
| `parse_java` (sequential) | 32.2s |
| `write_json` | 0.57s |
| Others | < 0.11s |
| **TOTAL** | **32.98s** |

#### altcommon (8,921 files, 228k methods)

| Version | `parse_java` | Total | Speedup |
|---|---|---|---|
| Sequential | 364.7s (97%) | 375.5s | 1× |
| **ProcessPoolExecutor** | **21.9s** | **26.7s** | **~14×** |

**Key optimization:** Parallel AST parsing via `ProcessPoolExecutor` reduces `parse_java` from 364.7s → 21.9s (~16.6× per-file speedup).

## Usage

### Build

```bash
# Full AST index (original)
./run.sh /path/to/java/repo

# Build BM25 index from JSON metadata
./run.sh bm25 data/

# Build chunks for embeddings
./run.sh chunks data/

# Generate embeddings
./run.sh embed data/

# Build FAISS index
./run.sh faiss
```

### Search

```bash
# Original keyword search
./search.sh "applicant deep link"

# BM25
./search.sh bm25 "applicant status" 20

# Vector
./search.sh vector "applicant deep link email"

# Hybrid (BM25 + Vector + RRF + reranker)
./search.sh hybrid "applicant deep link email"

# Full Fusion (BM25 + Vector + Symbol + Graph)
./search.sh fusion "candidate search" 10
```

### Fusion Output Example

```
Query: candidate search
BM25 hits: 200
Vector hits: 200
Symbol hits: 100
Graph expansions: 365

   Score  ID
   ------ --------------------------------------------------
  2.0964  CandidateService.deleteCandidateSearch
          - BM25 match
          - Vector similarity
          - Called by AssessmentFacade
  1.9500  CandidateException
          - Symbol match
          - Called by AltOneCPRecruitDS
          - Called by CandidateRESTService
```

## Project Structure

```
src/
├── build_index.py              # Java AST parser + index builder
├── search.py                   # V0 keyword search (legacy)
├── ranker.py                   # V0 hybrid ranking formula
├── jira_mapper.py              # Git → Jira mapping
├── chunking/
│   ├── build_chunks.py         # Chunk builder for embedding
├── embeddings/
│   ├── embed_chunks.py         # Embedding generation
│   ├── embedding_utils.py      # BGE model wrapper
├── retrieval/
│   ├── build_bm25.py           # BM25 index builder
│   ├── search_bm25.py          # BM25 search
│   ├── hybrid_search.py        # V3 hybrid (BM25 + Vector + RRF)
│   ├── reranker.py             # Bi-encoder reranker
│   ├── tokenizer.py            # CamelCase tokenizer (shared)
│   ├── scoring.py              # Score normalization + fusion (V4)
│   ├── fusion.py               # Multi-retrieval + merge (V4)
│   ├── graph_expansion.py      # Caller/callee/endpoint expansion (V4)
│   ├── explainability.py       # Result reason generation (V4)
│   ├── retrieval_engine.py     # Main retrieve() pipeline (V4)
├── symbols/
│   ├── build_symbol_index.py   # Symbol index builder
│   ├── symbol_search.py        # Symbol search (V4 enhanced)
│   ├── symbol_navigation.py    # Symbol definition lookup
├── vector/
│   ├── build_faiss.py          # FAISS index builder
│   ├── vector_search.py        # FAISS vector search
```

## Indexes

| Path | Type | Size |
|---|---|---|
| `index/bm25/` | Whoosh (BM25F) | 77 MB |
| `index/faiss/code.index` | FAISS (flat L2) | 41 MB |
| `index/embeddings/` | Embeddings + metadata | 42 MB |
| `data/` | JSON metadata | ~200 MB |
# ai-coding-agent
