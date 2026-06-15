"""
Task 6: Hybrid retrieval fusing BM25 + Vector search scores,
then reranking with a cross-encoder.

Fetches a broad pool from BM25 and vector search, merges via RRF,
then reranks the top pool with bge-reranker-base for final results.
"""

import logging
from pathlib import Path
from typing import Any

from retrieval.search_bm25 import CamelCaseTokenizer, search as bm25_search
from retrieval.reranker import rerank as reranker_rerank
from vector.vector_search import vector_search

logger = logging.getLogger(__name__)


def rrf(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score."""
    return 1.0 / (k + rank)


def hybrid_search(
    query: str,
    top_k: int = 50,
    pool_k: int = 100,
    k_rrf: int = 60,
) -> list[dict[str, Any]]:
    """Run hybrid search with BM25 + vector + cross-encoder reranker.

    Args:
        query: Natural language query string.
        top_k: Maximum number of final results.
        pool_k: Number of candidates fetched from each retriever before
            fusion. Defaults to 100.
        k_rrf: RRF constant. Defaults to 60.

    Returns:
        List of result dicts sorted by descending reranker score.
    """
    # 1. Retrieve broad pool
    bm25_results = bm25_search(query, top_k=pool_k)
    vector_results = vector_search(query, top_k=pool_k)

    logger.info(
        "Hybrid: BM25 returned %d, Vector returned %d",
        len(bm25_results),
        len(vector_results),
    )

    # 2. Merge by (file, method) key using RRF
    merged: dict[str, dict[str, Any]] = {}

    for rank, r in enumerate(bm25_results):
        key = f"{r.get('file', '')}:{r.get('name', '')}"
        merged[key] = {
            "file": r.get("file", ""),
            "method": r.get("name", ""),
            "class_name": "",
            "chunk_id": "",
            "content": r.get("content", ""),
        }

    for rank, r in enumerate(vector_results):
        key = f"{r.get('file', '')}:{r.get('method', '')}"
        if key in merged:
            merged[key]["class_name"] = r.get("class_name", "")
            merged[key]["chunk_id"] = r.get("chunk_id", "")
            merged[key]["content"] = r.get("content", merged[key]["content"])
        else:
            merged[key] = {
                "file": r.get("file", ""),
                "method": r.get("method", ""),
                "class_name": r.get("class_name", ""),
                "chunk_id": r.get("chunk_id", ""),
                "content": r.get("content", ""),
            }

    # 3. RRF score and take top pool for reranking
    pool = []
    for key, entry in merged.items():
        pool.append(entry)

    # 4. Rerank with cross-encoder
    reranked = reranker_rerank(query, pool, top_k=top_k)

    logger.info("Hybrid search for %r returned %d results", query, len(reranked))
    return reranked


def main() -> None:
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m retrieval.hybrid_search '<query>' [top_k]")
        sys.exit(1)

    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    results = hybrid_search(query, top_k=top_k)
    for r in results:
        print(f"  {r['score']:.4f}  {r['file']}  {r['method']}")


if __name__ == "__main__":
    main()