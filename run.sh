#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Install dependencies if not already installed
pip install -r requirements.txt > /dev/null 2>&1

usage() {
    echo "Usage:"
    echo "  ./run.sh <repo_path>              Run original AST indexer (old pipeline)"
    echo "  ./run.sh bm25 <data_dir>          Build BM25 index from JSON data files"
    echo "  ./run.sh chunks <data_dir>        Build chunks from methods + deps JSON"
    echo "  ./run.sh embed <data_dir>         Generate embeddings from chunks"
    echo "  ./run.sh faiss                    Build FAISS index from embeddings"
    echo ""
    echo "Examples:"
    echo "  ./run.sh /path/to/java/repo"
    echo "  ./run.sh bm25 data/"
    echo "  ./run.sh chunks data/"
    echo "  ./run.sh embed data/"
    echo "  ./run.sh faiss"
    exit 1
}

detect_glued_mode() {
    local arg="$1"
    for mode in bm25 chunks embed faiss; do
        if [[ "$arg" == "$mode"* ]] && [[ "$arg" != "$mode" ]]; then
            echo "Error: mode and argument must be separated by a space."
            echo "Try: ./run.sh $mode <arg>"
            exit 1
        fi
    done
}

if [ $# -eq 0 ]; then
    usage
fi

detect_glued_mode "$1"

if [ "$1" = "bm25" ]; then
    DATA_DIR="${2:-data}"
    echo "Building BM25 index from $DATA_DIR ..."
    START_TOTAL=$(date +%s%N)
    PYTHONPATH=src python3 -m retrieval.build_bm25 "$DATA_DIR"
    END_TOTAL=$(date +%s%N)
    ELAPSED_TOTAL=$(echo "scale=2; ($END_TOTAL - $START_TOTAL) / 1000000000" | bc)
    echo "===================================="
    echo "Total time: ${ELAPSED_TOTAL}s"
    echo "========================================"
elif [ "$1" = "chunks" ]; then
    DATA_DIR="${2:-data}"
    echo "Building chunks from $DATA_DIR ..."
    START_TOTAL=$(date +%s%N)
    PYTHONPATH=src python3 -m chunking.build_chunks "$DATA_DIR"
    END_TOTAL=$(date +%s%N)
    ELAPSED_TOTAL=$(echo "scale=2; ($END_TOTAL - $START_TOTAL) / 1000000000" | bc)
    echo "========================================"
    echo "Total time: ${ELAPSED_TOTAL}s"
    echo "========================================"
elif [ "$1" = "embed" ]; then
    DATA_DIR="${2:-data}"
    echo "Generating embeddings from $DATA_DIR/chunks.json ..."
    START_TOTAL=$(date +%s%N)
    PYTHONPATH=src python3 -m embeddings.embed_chunks "$DATA_DIR"
    END_TOTAL=$(date +%s%N)
    ELAPSED_TOTAL=$(echo "scale=2; ($END_TOTAL - $START_TOTAL) / 1000000000" | bc)
    echo "========================================"
    echo "Total time: ${ELAPSED_TOTAL}s"
    echo "========================================"
elif [ "$1" = "faiss" ]; then
    echo "Building FAISS index from embeddings ..."
    START_TOTAL=$(date +%s%N)
    PYTHONPATH=src python3 -m vector.build_faiss
    END_TOTAL=$(date +%s%N)
    ELAPSED_TOTAL=$(echo "scale=2; ($END_TOTAL - $START_TOTAL) / 1000000000" | bc)
    echo "========================================"
    echo "Total time: ${ELAPSED_TOTAL}s"
    echo "========================================"
else
    if [ -e "$1" ]; then
        START_TOTAL=$(date +%s%N)
        python3 src/build_index.py "$1"
        END_TOTAL=$(date +%s%N)
        ELAPSED_TOTAL=$(echo "scale=2; ($END_TOTAL - $START_TOTAL) / 1000000000" | bc)
        echo "========================================"
        echo "Total time: ${ELAPSED_TOTAL}s"
        echo "========================================"
    else
        echo "Error: unknown mode or missing repository path '$1'"
        usage
    fi
fi
