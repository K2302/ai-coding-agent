"""
Task 3 (CLI): Load chunks, build embedding text, generate and persist embeddings.

Process:
    1. Load chunks.json
    2. Build enriched embedding text per chunk
    3. Generate embeddings via sentence-transformers
    4. Save embeddings as numpy array + metadata
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

from embeddings.embedding_utils import build_embedding_text, generate_embeddings_batch

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CHUNKS_FILE = DATA_DIR / "chunks.json"
EMBEDDINGS_DIR = Path("index") / "embeddings"
EMBEDDINGS_FILE = EMBEDDINGS_DIR / "embeddings.npy"
METADATA_FILE = EMBEDDINGS_DIR / "metadata.json"


def load_chunks(path: Path) -> list[dict[str, Any]]:
    """Load chunks from a JSON file."""
    if not path.exists():
        logger.error("Chunks file not found: %s", path)
        return []
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, list):
        logger.error("Expected a JSON list in %s", path)
        return []
    return data


def embed_chunks(
    chunks_path: Path,
    output_embeddings: Path,
    output_metadata: Path,
    batch_size: int = 256,
) -> int:
    """Generate embeddings for all chunks and persist them.

    Args:
        chunks_path: Path to chunks.json.
        output_embeddings: Path to save .npy embeddings array.
        output_metadata: Path to save metadata JSON.
        batch_size: Batch size for embedding generation.

    Returns:
        Number of chunks embedded.
    """
    chunks = load_chunks(chunks_path)
    if not chunks:
        logger.error("No chunks to embed.")
        return 0

    logger.info("Building embedding text for %d chunks...", len(chunks))
    texts = [build_embedding_text(chunk) for chunk in chunks]

    logger.info("Generating embeddings (batch_size=%d)...", batch_size)
    embeddings = generate_embeddings_batch(texts, batch_size=batch_size)

    # Save embeddings as numpy array
    output_embeddings.parent.mkdir(parents=True, exist_ok=True)
    emb_array = np.array(embeddings, dtype=np.float32)
    np.save(str(output_embeddings), emb_array)
    logger.info("Saved embeddings shape %s to %s", emb_array.shape, output_embeddings)

    # Save metadata: chunk_id -> chunk mapping
    metadata = []
    for i, chunk in enumerate(chunks):
        metadata.append({
            "faiss_id": i,
            "chunk_id": chunk.get("chunk_id", f"chunk_{i}"),
            "file": chunk.get("file", ""),
            "class_name": chunk.get("class_name", ""),
            "method": chunk.get("method", ""),
            "signature": chunk.get("signature", ""),
        })

    with output_metadata.open("w", encoding="utf-8") as fp:
        json.dump(metadata, fp, indent=2)
    logger.info("Saved metadata for %d chunks to %s", len(metadata), output_metadata)

    return len(chunks)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR
    chunks_path = data_dir / "chunks.json"

    embed_chunks(
        chunks_path=chunks_path,
        output_embeddings=EMBEDDINGS_FILE,
        output_metadata=METADATA_FILE,
    )


if __name__ == "__main__":
    main()