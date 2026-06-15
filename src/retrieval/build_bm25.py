"""
BM25 Index Builder using Whoosh.

Builds a searchable BM25 index from code metadata JSON files.
Indexes class names, method names, import targets, endpoints, and SQL tables.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

from whoosh.fields import ID, TEXT, Schema
from whoosh.index import create_in

from retrieval.tokenizer import CamelCaseTokenizer, camel_case_analyzer  # noqa: F401

logger = logging.getLogger(__name__)


def load_json(path: Path) -> list[dict[str, Any]]:
    """Load and return JSON data from a file path.

    Args:
        path: Path to the JSON file.

    Returns:
        List of dictionaries parsed from the JSON file.
        Returns an empty list if the file does not exist or is invalid.
    """
    if not path.exists():
        logger.warning("File not found: %s", path)
        return []
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
            if not isinstance(data, list):
                logger.warning("Expected a JSON list in %s, got %s", path, type(data).__name__)
                return []
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load %s: %s", path, e)
        return []


def create_schema() -> Schema:
    """Create the Whoosh schema for the BM25 index.

    Returns:
        Schema with fields: file, entity_type, name, content.
    """
    analyzer = camel_case_analyzer()
    return Schema(
        file=ID(stored=True),
        entity_type=TEXT(stored=True),
        name=TEXT(stored=True, analyzer=analyzer),
        content=TEXT(stored=True, analyzer=analyzer),
    )


def _build_class_to_file(classes: list[dict[str, Any]]) -> dict[str, str]:
    """Build a mapping from simple class name to file path.

    Args:
        classes: List of class metadata dictionaries.

    Returns:
        Dict mapping class name → file path.
    """
    mapping: dict[str, str] = {}
    for entry in classes:
        name = (entry.get("class_name") or "").strip()
        file_path = (entry.get("file") or "").strip()
        if name and file_path:
            mapping[name] = file_path
    return mapping


def index_classes(
    writer: "whoosh.writing.IndexWriter",
    classes: list[dict[str, Any]],
) -> None:
    """Index class name entries into the Whoosh index.

    Each entry's ``class_name`` is stored as both ``name`` and ``content``
    so that BM25 can match against it.

    Args:
        writer: Whoosh IndexWriter instance.
        classes: List of class metadata dictionaries.
    """
    count = 0
    for entry in classes:
        class_name = (entry.get("class_name") or "").strip()
        file_name = (entry.get("file") or "").strip()
        if not class_name:
            continue
        writer.add_document(
            file=file_name,
            entity_type="CLASS",
            name=class_name,
            content=class_name,
        )
        count += 1
    logger.info("Indexed %d classes", count)


def index_methods(
    writer: "whoosh.writing.IndexWriter",
    methods: list[dict[str, Any]],
    class_to_file: dict[str, str],
) -> None:
    """Index method name entries into the Whoosh index.

    Resolves the file path from the method's enclosing class via
    *class_to_file*.

    Args:
        writer: Whoosh IndexWriter instance.
        methods: List of method metadata dictionaries
            with keys ``method``, ``class``.
        class_to_file: Mapping of class name to file path.
    """
    count = 0
    for entry in methods:
        method_name = (entry.get("method") or "").strip()
        class_name = (entry.get("class") or "").strip()
        if not method_name:
            continue
        file_name = class_to_file.get(class_name, "")
        writer.add_document(
            file=file_name,
            entity_type="METHOD",
            name=method_name,
            content=method_name,
        )
        count += 1
    logger.info("Indexed %d methods", count)


def _extract_short_name(qualified_name: str) -> str:
    """Extract the simple class name from a fully qualified Java name.

    Examples::

        "com.talentpact.ats.to.social.SocialAppSetting" → "SocialAppSetting"
        "java.io.Serializable" → "Serializable"
        "ApplicantDAO" → "ApplicantDAO"
    """
    parts = qualified_name.rsplit(".", 1)
    return parts[-1]


def index_imports(
    writer: "whoosh.writing.IndexWriter",
    dependencies: list[dict[str, Any]],
) -> None:
    """Index import/dependency target entries into the Whoosh index.

    Deduplicates targets and extracts the short class name from fully
    qualified imports for better searchability.

    Args:
        writer: Whoosh IndexWriter instance.
        dependencies: List of dependency graph dictionaries
            with keys ``source``, ``target``.
    """
    seen: set[str] = set()
    count = 0
    for entry in dependencies:
        target = (entry.get("target") or "").strip()
        if not target or target in seen:
            continue
        seen.add(target)
        source_file = (entry.get("source") or "").strip()

        short_name = _extract_short_name(target)
        writer.add_document(
            file=source_file,
            entity_type="IMPORT",
            name=short_name,
            content=f"{short_name} {target}",
        )
        count += 1
    logger.info("Indexed %d unique imports", count)


def index_endpoints(
    writer: "whoosh.writing.IndexWriter",
    entrypoints: list[dict[str, Any]],
) -> None:
    """Index endpoint / entry-point entries into the Whoosh index.

    Handles the actual entry-point schemas produced by the static analysis
    layer: EJB ``{type, name, method}``, SERVLET ``{type, servlet,
    url_pattern}``, and JSP ``{type, page}``.

    Args:
        writer: Whoosh IndexWriter instance.
        entrypoints: List of entry-point metadata dictionaries.
    """
    count = 0
    for entry in entrypoints:
        ep_type = (entry.get("type") or "").strip()
        file_name = (entry.get("source_file") or "").strip()

        # Build a descriptive name based on entry-point type
        if ep_type == "EJB":
            name = (entry.get("name") or "").strip()
            method = (entry.get("method") or "").strip()
            endpoint_name = f"{name}.{method}" if method else name
        elif ep_type == "SERVLET":
            servlet = (entry.get("servlet") or "").strip()
            url = (entry.get("url_pattern") or "").strip()
            endpoint_name = f"{servlet} {url}" if url else servlet
        elif ep_type == "JSP":
            endpoint_name = entry.get("page") or ""
        else:
            endpoint_name = (
                entry.get("endpoint")
                or entry.get("path")
                or entry.get("name")
                or ""
            ).strip()

        if not endpoint_name:
            continue

        writer.add_document(
            file=file_name,
            entity_type="ENDPOINT",
            name=endpoint_name,
            content=endpoint_name,
        )
        count += 1
    logger.info("Indexed %d endpoints", count)


def index_tables(
    writer: "whoosh.writing.IndexWriter",
    tables: list[dict[str, Any]],
) -> None:
    """Index SQL table name entries into the Whoosh index.

    Args:
        writer: Whoosh IndexWriter instance.
        tables: List of SQL table metadata dictionaries.
    """
    count = 0
    for entry in tables:
        table_name = (entry.get("table") or "").strip()
        file_name = (entry.get("file") or "").strip()
        if not table_name:
            continue
        writer.add_document(
            file=file_name,
            entity_type="TABLE",
            name=table_name,
            content=table_name,
        )
        count += 1
    logger.info("Indexed %d tables", count)


def build_index(data_dir: Path, index_dir: Path) -> None:
    """Build the complete BM25 Whoosh index from all data sources.

    Loads each JSON file from *data_dir* and indexes its entries under the
    appropriate entity type.  The resulting index is written to *index_dir*.

    The loader looks for the following files (aliases in parentheses are
    also checked)::

        classes.json
        methods.json
        dependency_graph.json (also: dependencies.json)
        entrypoints.json     (also: endpoints.json)
        sql.json

    Args:
        data_dir: Directory containing the input JSON files.
        index_dir: Directory where the Whoosh index will be written.
    """
    index_dir.mkdir(parents=True, exist_ok=True)

    schema = create_schema()
    ix = create_in(str(index_dir), schema)
    writer = ix.writer()

    # ---- Classes ----
    classes = load_json(data_dir / "classes.json")
    index_classes(writer, classes)
    class_to_file = _build_class_to_file(classes)

    # ---- Methods ----
    methods = load_json(data_dir / "methods.json")
    index_methods(writer, methods, class_to_file)

    # ---- Dependencies ----
    dependencies = load_json(data_dir / "dependency_graph.json")
    if not dependencies:
        dependencies = load_json(data_dir / "dependencies.json")
    index_imports(writer, dependencies)

    # ---- Entrypoints / Endpoints ----
    entrypoints = load_json(data_dir / "entrypoints.json")
    if not entrypoints:
        entrypoints = load_json(data_dir / "endpoints.json")
    index_endpoints(writer, entrypoints)

    # ---- SQL tables ----
    tables = load_json(data_dir / "sql.json")
    index_tables(writer, tables)

    # Persist the index -------------------------------------------------------
    writer.commit()
    logger.info("BM25 index built successfully at %s", index_dir)


def main() -> None:
    """CLI entry point for the BM25 index builder.

    Usage::

        python src/retrieval/build_bm25.py <data_dir> [index_dir]
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python build_bm25.py <data_dir> [index_dir]")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).resolve()
    index_dir = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) > 2
        else Path("index") / "bm25"
    )

    if not data_dir.is_dir():
        logger.error("Data directory does not exist: %s", data_dir)
        sys.exit(1)

    build_index(data_dir, index_dir)


if __name__ == "__main__":
    main()