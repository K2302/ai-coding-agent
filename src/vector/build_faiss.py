"""
Task 4: Build and manage FAISS index from embeddings.

Functions:
    - build_faiss_index(embeddings)
    - save_faiss_index(index, path)
    - load_faiss_index(path)
"""

import json
import logging
from pathlib import Path
from typing import Any

import faiss
import numpy as np

logger = logging.getLogger(__name__)

FAISS_DIR = Path("index") / "faiss"
FAISS_INDEX_FILE = FAISS_DIR / "code.index"
METADATA_FILE = Path("index") / "embeddings" / "metadata.json"
EMBEDDINGS_FILE = Path("index") / "embeddings" / "embeddings.npy"


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """Build a FAISS IndexFlatIP index from embedding vectors.

    Uses IndexFlatIP (inner product) because embeddings are L2-normalized,
    making inner product equivalent to cosine similarity.

    Args:
        embeddings: Numpy array of shape (n_chunks, embedding_dim).

    Returns:
        FAISS index with vectors added.
    """
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    logger.info("Built FAISS index with %d vectors, dimension %d", index.ntotal, dim)
    return index


def save_faiss_index(index: faiss.Index, path: Path) -> None:
    """Save a FAISS index to disk.

    Args:
        index: FAISS index to save.
        path: File path for the saved index.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(path))
    logger.info("FAISS index saved to %s", path)


def load_faiss_index(path: Path) -> faiss.Index:
    """Load a FAISS index from disk.

    Args:
        path: File path to the saved index.

    Returns:
        Loaded FAISS index.

    Raises:
        FileNotFoundError: If the index file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"FAISS index not found at {path}. Run build_faiss.py first.")
    index = faiss.read_index(str(path))
    logger.info("Loaded FAISS index with %d vectors from %s", index.ntotal, path)
    return index


def load_metadata(path: Path) -> list[dict[str, Any]]:
    """Load chunk metadata from metadata JSON.

    Args:
        path: Path to metadata.json.

    Returns:
        List of metadata dicts with faiss_id, chunk_id, file, etc.
    """
    if not path.exists():
        raise FileNotFoundError(f"Metadata not found at {path}. Run embed_chunks.py first.")
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def build_from_embeddings(
    embeddings_path: Path,
    metadata_path: Path,
    output_path: Path,
) -> faiss.Index:
    """Load saved embeddings, build FAISS index, and save it.

    Args:
        embeddings_path: Path to embeddings.npy.
        metadata_path: Path to metadata.json.
        output_path: Path to save code.index.

    Returns:
        Built FAISS index.
    """
    if not embeddings_path.exists():
        raise FileNotFoundError(
            f"Embeddings not found at {embeddings_path}. Run embed_chunks.py first."
        )

    embeddings = np.load(str(embeddings_path))
    logger.info("Loaded embeddings shape: %s", embeddings.shape)

    index = build_faiss_index(embeddings)
    save_faiss_index(index, output_path)

    # Verify metadata exists (it should have been created by embed_chunks.py)
    if metadata_path.exists():
        meta = load_metadata(metadata_path)
        logger.info("Metadata has %d entries", len(meta))
    else:
        logger.warning("Metadata file not found at %s", metadata_path)

    return index


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    build_from_embeddings(
        embeddings_path=EMBEDDINGS_FILE,
        metadata_path=METADATA_FILE,
        output_path=FAISS_INDEX_FILE,
    )


if __name__ == "__main__":
    main()