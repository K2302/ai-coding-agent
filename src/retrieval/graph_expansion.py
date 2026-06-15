"""
Graph expansion and boosting for retrieval fusion.

Builds callers/callees/endpoint relationships from the dependency graph,
then boosts results discovered via graph traversal.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Boost weights per graph relationship type
CALLER_BOOST = 0.20
CALLEE_BOOST = 0.20
ENDPOINT_BOOST = 0.10

# Lazy-loaded caches
_graph_edges: list[dict[str, str]] | None = None
_caller_cache: dict[str, list[str]] | None = None   # simple class → callers
_callee_cache: dict[str, list[str]] | None = None   # simple class → callees
_file_to_classes: dict[str, list[str]] | None = None
_endpoints_cache: list[dict[str, str]] | None = None
_endpoint_controller_index: dict[str, list[dict[str, str]]] | None = None  # class → endpoints


def _load_graph_edges() -> list[dict[str, str]]:
    global _graph_edges
    if _graph_edges is None:
        with open(DATA_DIR / "dependency_graph.json") as f:
            _graph_edges = json.load(f)
    return _graph_edges


def _load_file_to_classes() -> dict[str, list[str]]:
    """Build mapping: file path → list of class names in that file."""
    global _file_to_classes
    if _file_to_classes is not None:
        return _file_to_classes

    try:
        with open(DATA_DIR / "classes.json") as f:
            classes = json.load(f)
    except FileNotFoundError:
        _file_to_classes = {}
        return _file_to_classes

    mapping: dict[str, list[str]] = defaultdict(list)
    for entry in classes:
        file_path = entry.get("file", "")
        class_name = entry.get("class_name", "")
        if file_path and class_name:
            mapping[file_path].append(class_name)

    _file_to_classes = dict(mapping)
    return _file_to_classes


def _build_graph_caches() -> None:
    """Pre-build caller/callee caches from the full dependency graph.

    Populates:
      - _caller_cache: simple class name → list of classes that depend on it
      - _callee_cache: simple class name → list of classes it depends on
    """
    global _caller_cache, _callee_cache
    if _caller_cache is not None and _callee_cache is not None:
        return

    edges = _load_graph_edges()
    file_to_classes = _load_file_to_classes()

    # Build inverted indices
    callee_tmp: dict[str, list[str]] = defaultdict(list)
    caller_tmp: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        src_file = edge["source"]
        tgt = edge["target"]
        if tgt.startswith("java.") or tgt.startswith("javax."):
            continue
        # Simple class name of target
        tgt_simple = tgt.rsplit(".", 1)[-1]

        # For each source file, get classes in it
        for src_class in file_to_classes.get(src_file, []):
            callee_tmp[src_class].append(tgt_simple)
            caller_tmp[tgt_simple].append(src_class)

    _caller_cache = {k: list(set(v)) for k, v in caller_tmp.items()}
    _callee_cache = {k: list(set(v)) for k, v in callee_tmp.items()}
    logger.info(
        "Graph caches built: %d caller entries, %d callee entries",
        len(_caller_cache), len(_callee_cache),
    )


def _load_endpoints() -> list[dict[str, str]]:
    global _endpoints_cache
    if _endpoints_cache is None:
        with open(DATA_DIR / "endpoints.json") as f:
            _endpoints_cache = json.load(f)
    return _endpoints_cache


def find_callers(class_name: str) -> list[str]:
    """Find all classes that depend on ``class_name``.

    Args:
        class_name: A simple class name (e.g. ``ApplicantService``).

    Returns:
        List of class names that depend on the given class.
    """
    _build_graph_caches()
    return _caller_cache.get(class_name, [])


def find_callees(class_name: str) -> list[str]:
    """Find all classes that ``class_name`` depends on.

    Args:
        class_name: A simple class name (e.g. ``ApplicantService``).

    Returns:
        List of class names that the given class depends on.
    """
    _build_graph_caches()
    return _callee_cache.get(class_name, [])


def find_related_endpoints(class_name: str) -> list[dict[str, str]]:
    """Find REST endpoints handled by the controller related to ``class_name``.

    Args:
        class_name: A class name (e.g. ``ApplicantService``).

    Returns:
        List of endpoint dicts with ``endpoint``, ``method``, ``controller``.
    """
    _load_endpoints()
    if _endpoint_controller_index is None:
        return []
    related = []
    cn_lower = class_name.lower()
    for ctrl_lower, eps in _endpoint_controller_index.items():
        if cn_lower in ctrl_lower or ctrl_lower in cn_lower:
            related.extend(eps)
    return related


def find_implementations(symbol: str) -> list[str]:
    """Find related classes via endpoint data.

    Args:
        symbol: A class name.

    Returns:
        List of related class names.
    """
    _load_endpoints()
    if _endpoint_controller_index is None:
        return []
    results = []
    for ctrl_lower, eps in _endpoint_controller_index.items():
        if symbol.lower() in ctrl_lower:
            results.append(eps[0]["controller"])
    return list(set(results))


def expand(graph_candidates: list[str]) -> set[str]:
    """Expand a list of candidate class names to depth 1 using the graph.

    For each candidate, fetches callers, callees, and related endpoints.

    Args:
        graph_candidates: List of class names to expand.

    Returns:
        Set of discovered class names from graph traversal.
    """
    discovered: set[str] = set()

    for class_name in graph_candidates:
        if not class_name:
            continue
        for caller in find_callers(class_name):
            discovered.add(caller)
        for callee in find_callees(class_name):
            discovered.add(callee)
        for ep in find_related_endpoints(class_name):
            controller = ep.get("controller", "")
            if controller:
                discovered.add(controller)

    return discovered


def compute_graph_boost(
    symbol: str,
    caller_hits: int = 0,
    callee_hits: int = 0,
    endpoint_hits: int = 0,
) -> float:
    """Compute graph boost score for a candidate.

    Args:
        symbol: The candidate symbol name.
        caller_hits: Number of callers that matched the original set.
        callee_hits: Number of callees that matched.
        endpoint_hits: Number of related endpoints found.

    Returns:
        Boost score to add to the retrieval score.
    """
    boost = 0.0
    boost += CALLER_BOOST * caller_hits
    boost += CALLEE_BOOST * callee_hits
    boost += ENDPOINT_BOOST * endpoint_hits
    return round(boost, 4)