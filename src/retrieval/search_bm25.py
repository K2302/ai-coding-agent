"""
BM25 Search using Whoosh.

Opens a previously built BM25 index and retrieves the top-k results
for a given natural language query.
"""

import logging
from pathlib import Path
from typing import Any

from whoosh.index import open_dir
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.scoring import BM25F

from retrieval.tokenizer import CamelCaseTokenizer  # noqa: F401 — needed for Whoosh pickle resolution

logger = logging.getLogger(__name__)


def search(
    query_str: str,
    index_dir: str | Path = Path("index") / "bm25",
    top_k: int = 70,
) -> list[dict[str, Any]]:
    """Search the BM25 index and return ranked results.

    The query is parsed against the ``name`` and ``content`` fields
    using a ``MultifieldParser``, then scored with Whoosh's default
    BM25F implementation.

    Args:
        query_str: The natural language query string.
        index_dir: Path to the directory containing the Whoosh index.
            Defaults to ``index/bm25``.
        top_k: Maximum number of results to return. Defaults to 10.

    Returns:
        A list of result dictionaries sorted by descending BM25 score.
        Each dictionary contains ``score``, ``file``, ``entity_type``,
        and ``name`` keys.

    Raises:
        FileNotFoundError: If the index directory does not exist.
    """
    index_path = Path(index_dir).resolve()
    if not index_path.is_dir():
        raise FileNotFoundError(
            f"BM25 index not found at {index_path}. "
            "Run build_bm25.py first to create the index."
        )

    ix = open_dir(str(index_path))
    results: list[dict[str, Any]] = []

    with ix.searcher(weighting=BM25F()) as searcher:
        # Parse the query against both name and content fields
        parser = MultifieldParser(
            ["name", "content"], schema=ix.schema, group=OrGroup
        )
        query = parser.parse(query_str)

        hits = searcher.search(query, limit=top_k)

        for hit in hits:
            results.append(
                {
                    "score": round(hit.score, 4),
                    "file": hit["file"],
                    "entity_type": hit["entity_type"],
                    "name": hit["name"],
                    "content": hit.get("content", ""),
                    "class_name": hit.get("class_name", ""),
                }
            )

    logger.info("Search for %r returned %d results", query_str, len(results))
    return results


def main() -> None:
    """CLI entry point for BM25 search.

    Usage::

        python -m retrieval.search_bm25 <query> [top_k]
        python -m retrieval.search_bm25 <query> [index_dir] [top_k]
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python -m retrieval.search_bm25 <query> [top_k]")
        print("       python -m retrieval.search_bm25 <query> [index_dir] [top_k]")
        sys.exit(1)

    query_str = sys.argv[1]

    # Determine index_dir and top_k from positional args
    index_dir = Path("index") / "bm25"
    top_k = 10

    if len(sys.argv) >= 3:
        arg2 = sys.argv[2]
        # If arg2 is a number, treat as top_k; otherwise treat as index_dir
        if arg2.isdigit():
            top_k = int(arg2)
        else:
            index_dir = arg2

    if len(sys.argv) >= 4:
        top_k = int(sys.argv[3])

    try:
        result = search(query_str, index_dir=index_dir)
    except FileNotFoundError as e:
        logger.error(e)
        sys.exit(1)

    print(f"{'Score':>8}  {'Entity Type':<12}  {'Name':<30}  {'File'}")
    print("-" * 80)
    for r in result:
        print(
            f"{r['score']:>8.4f}  {r['entity_type']:<12}  {r['name']:<30}  {r['file']}"
        )


if __name__ == "__main__":
    main()