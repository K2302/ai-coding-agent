"""
Score normalization and weighted fusion for multi-signal retrieval.

Normalizes scores from different retrievers to [0, 1] range,
then applies weighted fusion.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Weights for each retrieval signal
BM25_WEIGHT = 0.30
VECTOR_WEIGHT = 0.15
SYMBOL_WEIGHT = 0.35


def normalize_scores(results: list[dict[str, Any]], score_key: str = "score") -> list[dict[str, Any]]:
    """Min-max normalize scores to [0, 1].

    Args:
        results: List of dicts, each containing ``score_key``.
        score_key: The key holding the raw score.

    Returns:
        Same list with scores normalized in-place.
    """
    if not results:
        return results

    scores = [r.get(score_key, 0) or 0 for r in results]
    min_s = min(scores)
    max_s = max(scores)
    delta = max_s - min_s

    if delta == 0:
        for r in results:
            r[score_key] = 1.0
        return results

    for r in results:
        raw = r.get(score_key, 0) or 0
        r[score_key] = round((raw - min_s) / delta, 4)

    return results


def compute_final_score(entry: dict[str, Any]) -> float:
    """Weighted fusion of BM25, vector, and symbol scores.

    Args:
        entry: A merged entry with ``bm25_score``, ``vector_score``,
            and ``symbol_score`` keys (each optional).

    Returns:
        Combined score in [0, 1].
    """
    score = 0.0
    score += BM25_WEIGHT * entry.get("bm25_score", 0)
    score += VECTOR_WEIGHT * entry.get("vector_score", 0)
    score += SYMBOL_WEIGHT * entry.get("symbol_score", 0)
    return round(score, 4)