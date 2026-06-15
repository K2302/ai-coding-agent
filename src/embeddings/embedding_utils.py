"""
Task 2 & 3: Build enriched embedding text and generate embeddings.

Functions:
    - build_embedding_text(chunk) -> str
    - generate_embedding(text) -> list[float]
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Model path and dimension
MODEL_NAME = str(Path.home() / "bge-small-en-v1.5")
EMBEDDING_DIM = 384

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        logger.info("Loading model: %s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def build_embedding_text(chunk: dict[str, Any]) -> str:
    """Create enriched embedding text from a chunk dictionary.

    Combines file, class, method, dependencies, method calls, and body code
    into a structured text for embedding.

    Args:
        chunk: A chunk dictionary with keys: chunk_id, file, class_name,
            method, signature, content, dependencies, calls.

    Returns:
        Enriched text string suitable for embedding.
    """
    lines: list[str] = []

    lines.append(f"File: {chunk.get('file', '')}")
    lines.append("")
    lines.append(f"Class: {chunk.get('class_name', '')}")
    lines.append("")
    lines.append(f"Method: {chunk.get('method', '')}")
    lines.append("")

    deps = chunk.get("dependencies", [])
    if deps:
        lines.append("Dependencies:")
        lines.extend(f"  {d}" for d in deps)
        lines.append("")

    calls = chunk.get("calls", [])
    if calls:
        lines.append("Calls:")
        lines.extend(f"  {c}" for c in calls)
        lines.append("")

    lines.append("Code:")
    lines.append(chunk.get("content", ""))

    return "\n".join(lines)


def generate_embedding(text: str) -> list[float]:
    """Generate a normalized embedding vector for the input text.

    Args:
        text: Input text to embed.

    Returns:
        A list of floats of length EMBEDDING_DIM (384).
    """
    model = _get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    # Convert numpy array to list of Python floats
    if isinstance(embedding, np.ndarray):
        return embedding.tolist()
    return list(embedding)


def generate_embeddings_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of input strings to embed.
        batch_size: Number of texts to process at once.

    Returns:
        List of embedding vectors (list[float] each).
    """
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=batch_size)
    return [emb.tolist() for emb in embeddings]