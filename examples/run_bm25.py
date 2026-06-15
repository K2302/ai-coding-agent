#!/usr/bin/env python3
"""
Example usage of the full code retrieval system.

Includes BM25, chunking, embeddings, FAISS, vector search, and hybrid search.

Usage:

    # Build BM25 index
    python examples/run_bm25.py build data/

    # Search BM25
    python examples/run_bm25.py search "applicant status"

    # Build chunks from method metadata
    python examples/run_bm25.py chunks data/

    # Generate embeddings and build FAISS index
    python examples/run_bm25.py index data/

    # Vector search
    python examples/run_bm25.py vector "applicant deep link email"

    # Hybrid search
    python examples/run_bm25.py hybrid "applicant deep link email"

    # Full demo (creates sample data, builds all indexes, runs queries)
    python examples/run_bm25.py demo
"""

import json
import sys
from pathlib import Path

import numpy as np

# Add src to the Python path so we can import the retrieval package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from retrieval.build_bm25 import build_index
from retrieval.search_bm25 import search as bm25_search
from chunking.build_chunks import build_chunks
from embeddings.embed_chunks import embed_chunks
from embeddings.embedding_utils import generate_embedding, build_embedding_text
from vector.build_faiss import build_faiss_index, save_faiss_index
from vector.vector_search import vector_search
from retrieval.hybrid_search import hybrid_search


def create_sample_data(data_dir: Path) -> None:
    """Create sample JSON data files for demonstration purposes.

    Args:
        data_dir: Directory where sample data files will be created.
    """
    data_dir.mkdir(parents=True, exist_ok=True)

    # Sample classes
    classes = [
        {"class_name": "ApplicantService", "package": "com.company.service", "file": "ApplicantService.java"},
        {"class_name": "CandidateController", "package": "com.company.controller", "file": "CandidateController.java"},
        {"class_name": "ApplicantDAO", "package": "com.company.dao", "file": "ApplicantDAO.java"},
    ]
    (data_dir / "classes.json").write_text(json.dumps(classes, indent=2))

    # Sample methods
    methods = [
        {"method": "updateStatus", "class": "ApplicantService", "file": "ApplicantService.java"},
        {"method": "findById", "class": "ApplicantDAO", "file": "ApplicantDAO.java"},
        {"method": "getCandidate", "class": "CandidateController", "file": "CandidateController.java"},
    ]
    (data_dir / "methods.json").write_text(json.dumps(methods, indent=2))

    # Sample dependencies
    dependencies = [
        {"source": "ApplicantService", "target": "ApplicantDAO", "type": "IMPORT"},
        {"source": "CandidateController", "target": "ApplicantService", "type": "IMPORT"},
    ]
    (data_dir / "dependencies.json").write_text(json.dumps(dependencies, indent=2))

    # Sample endpoints
    endpoints = [
        {"endpoint": "/candidate/{id}", "method": "GET", "controller": "CandidateController"},
        {"endpoint": "/applicant/status", "method": "POST", "controller": "ApplicantController"},
    ]
    (data_dir / "endpoints.json").write_text(json.dumps(endpoints, indent=2))

    # Sample SQL tables
    tables = [
        {"table": "Candidate", "file": "CandidateDAO.java"},
        {"table": "ApplicantStatus", "file": "ApplicantDAO.java"},
    ]
    (data_dir / "sql.json").write_text(json.dumps(tables, indent=2))

    print(f"Sample data created in {data_dir}")

    # Symlink or copy sample data into data/ for other tools to use
    retrieval_dir = Path("data")
    retrieval_dir.mkdir(parents=True, exist_ok=True)
    for name in ("classes.json", "methods.json", "dependencies.json", "endpoints.json", "sql.json"):
        (retrieval_dir / name).write_text((data_dir / name).read_text())
    print(f"Sample data also copied to {retrieval_dir}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "build":
        data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data")
        index_dir = Path("index") / "bm25"

        if not data_dir.exists():
            print(f"Data directory '{data_dir}' not found. Creating sample data...")
            create_sample_data(data_dir)

        print(f"Building BM25 index from {data_dir}...")
        build_index(data_dir, index_dir)
        print(f"Index written to {index_dir}")

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python examples/run_bm25.py search <query>")
            sys.exit(1)
        query = sys.argv[2]
        index_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("index") / "bm25"

        print(f"BM25 Search for: {query!r}")
        print()
        results = bm25_search(query, index_dir=index_dir, top_k=10)
        print(f"{'Score':>8}  {'Entity Type':<12}  {'Name':<35}  {'File'}")
        print("-" * 85)
        for r in results:
            print(f"{r['score']:>8.4f}  {r['entity_type']:<12}  {r['name']:<35}  {r['file']}")

    elif command == "chunks":
        data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data")
        print(f"Building chunks from {data_dir}...")
        build_chunks(
            methods_path=data_dir / "methods.json",
            deps_path=data_dir / "dependencies.json",
            classes_path=data_dir / "classes.json",
            output_path=data_dir / "chunks.json",
        )

    elif command == "index":
        """Build embeddings + FAISS index from chunks."""
        data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data")
        embeddings_dir = Path("index") / "embeddings"
        faiss_dir = Path("index") / "faiss"

        print("Step 1: Building chunks...")
        build_chunks(
            methods_path=data_dir / "methods.json",
            deps_path=data_dir / "dependencies.json",
            classes_path=data_dir / "classes.json",
            output_path=data_dir / "chunks.json",
        )
        print()

        print("Step 2: Generating embeddings...")
        embed_chunks(
            chunks_path=data_dir / "chunks.json",
            output_embeddings=embeddings_dir / "embeddings.npy",
            output_metadata=embeddings_dir / "metadata.json",
        )
        print()

        print("Step 3: Building FAISS index...")
        embeddings = np.load(str(embeddings_dir / "embeddings.npy"))
        index = build_faiss_index(embeddings)
        save_faiss_index(index, faiss_dir / "code.index")
        print(f"FAISS index saved to {faiss_dir / 'code.index'}")

    elif command == "vector":
        if len(sys.argv) < 3:
            print("Usage: python examples/run_bm25.py vector <query> [top_k]")
            sys.exit(1)
        query = sys.argv[2]
        top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 50

        print(f"Vector search for: {query!r} (top_k={top_k})")
        print()
        results = vector_search(query, top_k=top_k)
        print(f"{'Score':>8}  {'Chunk ID':<45}  {'File'}")
        print("-" * 85)
        for r in results:
            print(f"{r['score']:>8.4f}  {r['chunk_id']:<45}  {r['file']}")

    elif command == "hybrid":
        if len(sys.argv) < 3:
            print("Usage: python examples/run_bm25.py hybrid <query> [top_k]")
            sys.exit(1)
        query = sys.argv[2]
        top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 50

        print(f"Hybrid search for: {query!r} (top_k={top_k})")
        print()
        results = hybrid_search(query, top_k=top_k)
        print(f"{'Score':>8}  {'File':<35}  {'Method'}")
        print("-" * 85)
        for r in results:
            print(f"{r['score']:>8.4f}  {r['file']:<35}  {r['method']}")

    elif command == "demo":
        """Full demo: create sample data, build all indexes, run queries."""
        data_dir = Path("_sample_data")
        index_dir = Path("index") / "bm25"
        embeddings_dir = Path("index") / "embeddings"
        faiss_dir = Path("index") / "faiss"

        create_sample_data(data_dir)
        print()

        # BM25
        build_index(data_dir, index_dir)
        print()

        # Chunks + Embeddings + FAISS
        print("Building chunks, embeddings, and FAISS index...")
        build_chunks(
            methods_path=data_dir / "methods.json",
            deps_path=data_dir / "dependencies.json",
            classes_path=data_dir / "classes.json",
            output_path=data_dir / "chunks.json",
        )
        embed_chunks(
            chunks_path=data_dir / "chunks.json",
            output_embeddings=embeddings_dir / "embeddings.npy",
            output_metadata=embeddings_dir / "metadata.json",
        )
        embeddings = np.load(str(embeddings_dir / "embeddings.npy"))
        index = build_faiss_index(embeddings)
        save_faiss_index(index, faiss_dir / "code.index")
        print()

        queries = ["applicant status", "candidate", "ApplicantService"]
        for q in queries:
            print(f"\n{'='*60}")
            print(f"BM25 Query: {q!r}")
            print(f"{'='*60}")
            results = bm25_search(q, index_dir=index_dir, top_k=5)
            if not results:
                print("  (no results)")
            else:
                print(f"{'Score':>8}  {'Type':<10}  {'Name':<35}  {'File'}")
                print("-" * 85)
                for r in results:
                    print(f"{r['score']:>8.4f}  {r['entity_type']:<10}  {r['name']:<35}  {r['file']}")

        for q in queries:
            print(f"\n{'='*60}")
            print(f"Hybrid Query: {q!r}")
            print(f"{'='*60}")
            results = hybrid_search(q, top_k=5)
            if not results:
                print("  (no results)")
            else:
                print(f"{'Score':>8}  {'File':<35}  {'Method'}")
                print("-" * 85)
                for r in results:
                    print(f"{r['score']:>8.4f}  {r['file']:<35}  {r['method']}")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
