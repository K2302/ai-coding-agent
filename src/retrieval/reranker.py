"""
Step 9: Rerank merged results using a local bi-encoder.

Takes the union of BM25 + vector results, embeds the query and each
candidate's full text, then reranks by cosine similarity.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

RERANKER_MODEL = str(Path.home() / "bge-small-en-v1.5")


def _load_reranker():
    """Lazy-load the SentenceTransformer model."""
    from sentence_transformers import SentenceTransformer
    logger.info("Loading reranker model: %s", RERANKER_MODEL)
    return SentenceTransformer(RERANKER_MODEL)


_model = None


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Rerank candidate results by query–document cosine similarity.

    Args:
        query: Original search query.
        candidates: List of result dicts, each with at least ``file``,
            ``method``, and optionally ``class_name`` / ``content``.
        top_k: Final number of results to keep.

    Returns:
        Reranked list of result dicts with updated ``score``.
    """
    if not candidates:
        return []

    global _model
    if _model is None:
        _model = _load_reranker()

    # Build passage texts
    passages = []
    for c in candidates:
        text = f"File: {c.get('file', '')}"
        if c.get("class_name"):
            text += f"\nClass: {c['class_name']}"
        if c.get("method"):
            text += f"\nMethod: {c['method']}"
        content = c.get("content", "")
        if content:
            text += f"\n\n{content}"
        passages.append(text)

    # Encode query and all passages
    query_emb = _model.encode(query, normalize_embeddings=True)
    doc_embs = _model.encode(passages, normalize_embeddings=True)

    # Cosine similarity (dot product on unit vectors)
    scores = doc_embs @ query_emb

    # Reassign scores
    for c, s in zip(candidates, scores):
        c["score"] = round(float(s), 4)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    logger.info("Reranker: %d candidates reranked, returning top %d", len(candidates), top_k)
    return candidates[:top_k]