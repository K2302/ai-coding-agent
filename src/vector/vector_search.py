"""
Task 5: Vector search using FAISS.

Embeds a natural language query and retrieves the top-k closest
chunks from the FAISS index.
"""

import logging
from pathlib import Path
from typing import Any

from embeddings.embedding_utils import generate_embedding
from vector.build_faiss import load_faiss_index, load_metadata

logger = logging.getLogger(__name__)

FAISS_DIR = Path("index") / "faiss"
FAISS_INDEX_FILE = FAISS_DIR / "code.index"
METADATA_FILE = Path("index") / "embeddings" / "metadata.json"


def vector_search(
    query: str,
    top_k: int = 50,
    index_path: Path = FAISS_INDEX_FILE,
    metadata_path: Path = METADATA_FILE,
) -> list[dict[str, Any]]:
    """Search the FAISS index with a natural language query.

    Args:
        query: Natural language query string.
        top_k: Maximum number of results. Defaults to 50.
        index_path: Path to the FAISS index file.
        metadata_path: Path to the chunk metadata JSON.

    Returns:
        List of result dicts sorted by descending similarity score.
        Each dict has ``score`` and ``chunk_id`` keys, plus metadata
        fields from the chunk.

    Raises:
        FileNotFoundError: If the index or metadata is missing.
    """
    index = load_faiss_index(index_path)
    metadata = load_metadata(metadata_path)

    # Build id -> metadata lookup
    meta_by_id = {m["faiss_id"]: m for m in metadata}

    # Embed the query
    query_vector = generate_embedding(query)
    import numpy as np
    query_array = np.array([query_vector], dtype=np.float32)

    # Search
    scores, indices = index.search(query_array, top_k)

    results: list[dict[str, Any]] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        meta = meta_by_id.get(int(idx), {})
        results.append({
            "score": round(float(score), 4),
            "chunk_id": meta.get("chunk_id", f"chunk_{idx}"),
            "file": meta.get("file", ""),
            "class_name": meta.get("class_name", ""),
            "method": meta.get("method", ""),
            "signature": meta.get("signature", ""),
            "content": meta.get("content", ""),
        })

    logger.info("Vector search for %r returned %d results", query, len(results))
    return results


def main() -> None:
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m vector.vector_search '<query>' [top_k]")
        sys.exit(1)

    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    results = vector_search(query, top_k=top_k)
    for r in results:
        print(f"  {r['score']:.4f}  {r['chunk_id']}  ({r['file']})")


if __name__ == "__main__":
    main()