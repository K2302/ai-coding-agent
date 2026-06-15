"""
Explainability for retrieval fusion results.

Generates human-readable reasons for why each result was ranked
as it was — covering retrieval signals and graph connections.
"""

import logging
from typing import Any

from retrieval.graph_expansion import find_callers, find_callees, find_related_endpoints

logger = logging.getLogger(__name__)


def _class_from_id(entity_id: str) -> str:
    """Extract the simple class name from a fused result ID."""
    parts = entity_id.split(".")
    if len(parts) >= 2 and parts[-1][0].islower():
        return parts[-2]
    return parts[-1]


def generate_reasons(entry: dict[str, Any], entity_id: str) -> list[str]:
    """Generate explanation strings for a single result.

    Args:
        entry: A merged result entry with score keys and graph info.
        entity_id: The result ID (e.g. ``ApplicantService.generateDeepLink``).

    Returns:
        List of human-readable reason strings.
    """
    reasons: list[str] = []

    if entry.get("bm25_score", 0) > 0:
        reasons.append("BM25 match")
    if entry.get("vector_score", 0) > 0:
        reasons.append("Vector similarity")
    if entry.get("symbol_score", 0) > 0:
        reasons.append("Symbol match")

    # Graph-based reasons — extract class name for graph API
    class_name = _class_from_id(entity_id)
    callers = find_callers(class_name)
    callees = find_callees(class_name)
    endpoints = find_related_endpoints(class_name)

    for caller in callers[:3]:
        reasons.append(f"Called by {caller}")
    for callee in callees[:3]:
        reasons.append(f"Calls {callee}")
    for ep in endpoints[:3]:
        reasons.append(f"Used by {ep['method']} {ep['endpoint']} endpoint")

    return reasons


def build_report(
    query: str,
    results: list[dict[str, Any]],
    bm25_hits: int,
    vector_hits: int,
    symbol_hits: int,
    graph_expansions: int,
) -> dict[str, Any]:
    """Build the full retrieval report.

    Args:
        query: Original search query.
        results: Final ranked result list.
        bm25_hits: Number of BM25 results retrieved.
        vector_hits: Number of vector results retrieved.
        symbol_hits: Number of symbol results retrieved.
        graph_expansions: Number of graph-expanded candidates.

    Returns:
        Report dict with query, results, and metadata.
    """
    return {
        "query": query,
        "results": results,
        "bm25_hits": bm25_hits,
        "vector_hits": vector_hits,
        "symbol_hits": symbol_hits,
        "graph_expansions": graph_expansions,
    }