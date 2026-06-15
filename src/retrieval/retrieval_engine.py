"""
Retrieval Fusion Engine — combines BM25, vector, symbol, and graph signals.

Usage:
    python -m retrieval.retrieval_engine "<query>" [top_k]
"""

import logging
import re
from typing import Any

from retrieval.explainability import build_report, generate_reasons
from retrieval.fusion import _parallel_retrieve, merge_results
from retrieval.graph_expansion import expand, find_callers, find_callees, compute_graph_boost

logger = logging.getLogger(__name__)


def _class_from_id(entity_id: str) -> str:
    """Extract the simple class name from a fused result ID.

    Handles formats:
      - ``ClassName.methodName`` → ``ClassName``
      - ``ClassName`` → ``ClassName``
    """
    parts = entity_id.split(".")
    if len(parts) >= 2 and parts[-1][0].islower():
        return parts[-2]
    return parts[-1]


def retrieve(
    query: str,
    top_k: int = 20,
    bm25_k: int = 200,
    vector_k: int = 200,
    symbol_k: int = 100,
) -> dict[str, Any]:
    """Full retrieval pipeline: parallel search → fusion → graph → rank.

    Args:
        query: Natural language query string.
        top_k: Maximum number of final results. Defaults to 20.
        bm25_k: Pool size for BM25. Defaults to 200.
        vector_k: Pool size for vector search. Defaults to 200.
        symbol_k: Pool size for symbol search. Defaults to 100.

    Returns:
        Report dict with ``query``, ``results``, and hit counts.
    """
    # 1. Parallel retrieval
    bm25_results, vector_results, symbol_results = _parallel_retrieve(
        query, bm25_k=bm25_k, vector_k=vector_k, symbol_k=symbol_k,
    )

    # 2. Merge and weighted fusion
    merged = merge_results(bm25_results, vector_results, symbol_results)

    bm25_hits = len(bm25_results)
    vector_hits = len(vector_results)
    symbol_hits = len(symbol_results)

    # 3. Graph expansion on top 50 fused results
    #    Extract class names from fused IDs for matching against the dependency graph
    top_fused = merged[:50]
    top_class_names = {_class_from_id(m["id"]) for m in top_fused}
    discovered = expand(list(top_class_names))
    graph_expansions = len(discovered)

    # 4. Graph boosting
    result_map: dict[str, dict[str, Any]] = {m["id"]: m for m in merged}

    for class_name in discovered:
        # Find any merged result whose class name matches
        matched = False
        for mid, entry in result_map.items():
            if mid == class_name or _class_from_id(mid) == class_name:
                matched = True
                caller_hits = sum(1 for c in find_callers(class_name) if c in top_class_names)
                callee_hits = sum(1 for c in find_callees(class_name) if c in top_class_names)
                entry["graph_boost"] = compute_graph_boost(
                    class_name, caller_hits=caller_hits, callee_hits=callee_hits,
                )
                break

        if not matched:
            # New graph-only entry
            boost = compute_graph_boost(class_name, endpoint_hits=1)
            result_map[class_name] = {
                "id": class_name,
                "retrieval_score": 0,
                "graph_boost": boost,
                "bm25_score": 0,
                "vector_score": 0,
                "symbol_score": 0,
            }

    # 5. Final ranking
    for entry in result_map.values():
        entry["score"] = round(
            entry.get("retrieval_score", 0) + entry.get("graph_boost", 0), 4
        )

    ranked = sorted(result_map.values(), key=lambda x: x["score"], reverse=True)

    # 6. Explainability for top results
    for entry in ranked[:top_k]:
        entry["reasons"] = generate_reasons(entry, entry["id"])

    final_results = ranked[:top_k]

    # 7. Build report
    report = build_report(
        query=query,
        results=final_results,
        bm25_hits=bm25_hits,
        vector_hits=vector_hits,
        symbol_hits=symbol_hits,
        graph_expansions=graph_expansions,
    )

    return report


def main() -> None:
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python -m retrieval.retrieval_engine '<query>' [top_k]")
        sys.exit(1)

    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    report = retrieve(query, top_k=top_k)

    print(f"\nQuery: {report['query']}")
    print(f"BM25 hits: {report['bm25_hits']}")
    print(f"Vector hits: {report['vector_hits']}")
    print(f"Symbol hits: {report['symbol_hits']}")
    print(f"Graph expansions: {report['graph_expansions']}")
    print(f"\n{'Score':>8}  {'ID'}")
    print("-" * 80)
    for r in report["results"]:
        score = r.get("score", 0)
        reasons = r.get("reasons", [])
        print(f"{score:>8.4f}  {r['id']}")
        for reason in reasons[:3]:
            print(f"          - {reason}")
        if reasons:
            print()


if __name__ == "__main__":
    main()