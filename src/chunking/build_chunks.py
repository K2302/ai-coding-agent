"""
Task 1: Build method chunks from parsed metadata.

Reads methods.json, classes.json, and dependencies.json,
creates one chunk per method with metadata and dependency info.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CHUNKS_FILE = DATA_DIR / "chunks.json"


@dataclass
class Chunk:
    chunk_id: str
    file: str
    class_name: str
    method: str
    signature: str
    content: str
    dependencies: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0


def load_json(path: Path) -> list[dict[str, Any]]:
    """Load JSON list from a file path."""
    if not path.exists():
        logger.warning("File not found: %s", path)
        return []
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
            if not isinstance(data, list):
                logger.warning("Expected a JSON list in %s", path)
                return []
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load %s: %s", path, e)
        return []


def build_dependency_map(deps_path: Path) -> dict[str, list[str]]:
    """Build mapping from source class to list of target dependencies."""
    deps = load_json(deps_path)
    dep_map: dict[str, list[str]] = {}
    for d in deps:
        source = d.get("source", "")
        target = d.get("target", "")
        if source and target:
            dep_map.setdefault(source, []).append(target)
    return dep_map


def build_class_to_file(classes_path: Path) -> dict[str, str]:
    """Build mapping from class name to source file path."""
    classes = load_json(classes_path)
    return {c.get("class_name", ""): c.get("file", "") for c in classes if c.get("class_name")}


def should_skip_method(method: dict[str, Any]) -> bool:
    """Return True if the method is trivial boilerplate that should be excluded from chunks.

    Skipped when:
      1. Name is exactly ``toString``, ``equals``, or ``hashCode``.
      2. Name starts with ``get``, ``set``, or ``is`` AND the method is trivial
         (calls list empty, or body < 300 chars, or body < 80 chars with no calls).

    Service methods, controller methods, and utility methods with real logic
    (calls, loops, conditions, etc.) are always kept.
    """
    name = method.get("method", "")
    calls = method.get("calls", [])
    body = method.get("body", "")
    body_len = len(body)
    calls_empty = not calls

    # Rule 1 – canonical boilerplate
    if name in {"toString", "equals", "hashCode"}:
        return True

    # Rules 4-6 + AND conditions – simple getter/setter/boolean-accessor
    if name.startswith("get") or name.startswith("set") or name.startswith("is"):
        if calls_empty or body_len < 300:
            return True

    return False


def build_chunks(
    methods_path: Path,
    deps_path: Path,
    classes_path: Path,
    output_path: Path,
) -> list[dict[str, Any]]:
    """Read methods and enrich with dependencies to produce chunks.

    Each method becomes exactly one chunk with a stable chunk_id
    in the format ``ClassName.methodName``.

    Args:
        methods_path: Path to methods.json.
        deps_path: Path to dependencies.json.
        classes_path: Path to classes.json.
        output_path: Path to write chunks.json.

    Returns:
        List of chunk dictionaries written to disk.
    """
    methods = load_json(methods_path)
    if not methods:
        logger.error("No methods found in %s", methods_path)
        return []

    dep_map = build_dependency_map(deps_path)
    class_file_map = build_class_to_file(classes_path)

    chunks: list[dict[str, Any]] = []
    total = 0
    skipped = 0

    for m in methods:
        total += 1
        if should_skip_method(m):
            skipped += 1
            continue

        method_name = m.get("method", "unknown")
        class_name = m.get("class", "Unknown")
        source_file = m.get("file", class_file_map.get(class_name, ""))

        chunk_id = f"{class_name}.{method_name}"
        params = m.get("parameters", [])
        ret_type = m.get("return_type", "void")
        param_str = ", ".join(params) if params else "..."
        signature = f"{ret_type} {method_name}({param_str})"

        # Resolve dependencies from dep_map
        deps = sorted(set(dep_map.get(class_name, [])))
        calls = m.get("calls", [])

        # Build content: with body, include structural context for embedding signal
        body = m.get("body", "")
        if body:
            parts = [
                f"File: {source_file}",
                f"Class: {class_name}",
                f"Method: {method_name}",
                f"Signature: {signature}",
            ]
            if deps:
                parts.append("Dependencies:\n" + "\n".join(deps))
            if calls:
                parts.append("Calls:\n" + "\n".join(sorted(set(calls))))
            parts.append("Code:\n" + body)
            content = "\n\n".join(parts)
        else:
            content_parts = [f"File: {source_file}", f"Class: {class_name}", f"Method: {method_name}"]
            if params:
                content_parts.append(f"Parameters: {', '.join(params)}")
            if ret_type:
                content_parts.append(f"Returns: {ret_type}")
            content = "\n".join(content_parts)

        start_line = m.get("start_line", 0)
        end_line = m.get("end_line", 0)

        chunk = Chunk(
            chunk_id=chunk_id,
            file=source_file,
            class_name=class_name,
            method=method_name,
            signature=signature,
            content=content,
            dependencies=deps,
            calls=calls,
            start_line=start_line,
            end_line=end_line,
        )
        chunks.append(asdict(chunk))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(chunks, fp, indent=2)

    retained = total - skipped
    logger.info("Chunk summary: %d total methods, %d skipped, %d retained -> %s", total, skipped, retained, output_path)
    return chunks


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    import sys
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR
    build_chunks(
        methods_path=data_dir / "methods.json",
        deps_path=data_dir / "dependencies.json",
        classes_path=data_dir / "classes.json",
        output_path=data_dir / "chunks.json",
    )


if __name__ == "__main__":
    main()