"""
Multi-retrieval, merge, and weighted fusion of BM25 + vector + symbol signals.

BM25 (Whoosh) and vector (FAISS) are called sequentially because Whoosh uses
pickle internally for its tokenizer, which breaks under ThreadPoolExecutor.
"""

import logging
import time
from typing import Any

from retrieval.search_bm25 import search as bm25_search
from retrieval.scoring import compute_final_score, normalize_scores
from symbols.symbol_search import search_symbols
from vector.vector_search import vector_search

logger = logging.getLogger(__name__)


def _normalize_id(r: dict[str, Any]) -> str:
    """Build a stable method-level ID from any result dict.

    Returns IDs in ``ClassName.methodName`` format when possible,
    or a plain class/qualified name as fallback.
    """
    cls = r.get("class_name", "") or ""

    # BM25 uses 'name' for method name
    name = r.get("name", "") or ""
    if cls and name:
        return f"{cls}.{name}"

    # Vector uses 'method' for method name
    method = r.get("method", "") or ""
    if cls and method:
        return f"{cls}.{method}"

    # Symbol search: extract simple class name from qualified_name
    qn = r.get("qualified_name") or r.get("symbol_id") or ""
    if qn:
        # Return just the simple class name for class-level symbol matches
        parts = qn.split(".")
        return parts[-1] if parts else qn

    # Fallback
    return r.get("id", "") or name or method or r.get("chunk_id", "")


def _parallel_retrieve(
    query: str,
    bm25_k: int = 200,
    vector_k: int = 200,
    symbol_k: int = 100,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run BM25, vector, and symbol searches.

    Returns:
        Tuple of (bm25_results, vector_results, symbol_results).
    """
    t0 = time.perf_counter()

    bm25 = bm25_search(query, top_k=bm25_k)
    vector = vector_search(query, top_k=vector_k)
    symbol = search_symbols(query, limit=symbol_k)

    elapsed = time.perf_counter() - t0

    logger.info(
        "Retrieval: BM25=%d, Vector=%d, Symbol=%d (%.0fms)",
        len(bm25), len(vector), len(symbol), elapsed * 1000,
    )

    # Normalize each result set independently
    normalize_scores(bm25)
    normalize_scores(vector)
    normalize_scores(symbol)

    return bm25, vector, symbol


def merge_results(
    bm25: list[dict[str, Any]],
    vector: list[dict[str, Any]],
    symbol: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate and merge results by normalized ID.

    Each merged entry stores per-signal scores for weighted fusion.

    Returns:
        List of merged entries sorted by combined retrieval score descending.
    """
    merged: dict[str, dict[str, Any]] = {}

    for r in bm25:
        rid = _normalize_id(r)
        merged.setdefault(rid, {"id": rid, "bm25_score": 0})
        merged[rid]["bm25_score"] = r.get("score", 0)

    for r in vector:
        rid = _normalize_id(r)
        if rid not in merged:
            merged[rid] = {"id": rid, "bm25_score": 0}
        merged[rid]["vector_score"] = r.get("score", 0)

    for r in symbol:
        rid = _normalize_id(r)
        if rid not in merged:
            merged[rid] = {"id": rid, "bm25_score": 0}
        merged[rid]["symbol_score"] = r.get("score", 0)

    # Compute fused score
    for entry in merged.values():
        entry.setdefault("bm25_score", 0)
        entry.setdefault("vector_score", 0)
        entry.setdefault("symbol_score", 0)
        entry["retrieval_score"] = compute_final_score(entry)

    return sorted(merged.values(), key=lambda x: x["retrieval_score"], reverse=True)