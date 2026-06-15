#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Install dependencies if not already installed
pip install -r requirements.txt > /dev/null 2>&1

usage() {
    echo "Usage:"
    echo "  ./search.sh '<query>'                Run original keyword search (old pipeline)"
    echo "  ./search.sh bm25 '<query>' [top_k]   Run BM25 search on the Whoosh index"
    echo "  ./search.sh vector '<query>' [top_k] Run vector search on the FAISS index"
    echo "  ./search.sh hybrid '<query>' [top_k] Run hybrid BM25 + vector search"
    echo "  ./search.sh fusion '<query>' [top_k] Run retrieval fusion engine (BM25 + vector + symbol + graph)"
    echo ""
    echo "Examples:"
    echo "  ./search.sh \"applicant deep link\""
    echo "  ./search.sh bm25 \"applicant status\""
    echo "  ./search.sh bm25 \"update status\" 20"
    echo "  ./search.sh vector \"applicant deep link email\""
    echo "  ./search.sh hybrid \"applicant deep link email\""
    echo "  ./search.sh fusion \"applicant deep link email\""
    exit 1
}

detect_glued_mode() {
    local arg="$1"
    for mode in bm25 vector hybrid; do
        if [[ "$arg" == "$mode"* ]] && [[ "$arg" != "$mode" ]]; then
            echo "Error: mode and query must be separated by a space."
            echo "Try: ./search.sh $mode \"your query\" [top_k]"
            exit 1
        fi
    done
}

if [ $# -eq 0 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    usage
fi

detect_glued_mode "$1"

if [ "$1" = "bm25" ]; then
    QUERY="${2:-}"
    TOP_K="${3:-10}"
    if [ -z "$QUERY" ]; then
        echo "Error: missing query argument"
        usage
    fi
    echo "BM25 search for: $QUERY (top_k=$TOP_K)"
    echo "------------------------------------------------------------"
    PYTHONPATH=src python3 -m retrieval.search_bm25 "$QUERY" "$TOP_K"
elif [ "$1" = "vector" ]; then
    QUERY="${2:-}"
    TOP_K="${3:-50}"
    if [ -z "$QUERY" ]; then
        echo "Error: missing query argument"
        usage
    fi
    echo "Vector search for: $QUERY (top_k=$TOP_K)"
    echo "------------------------------------------------------------"
    PYTHONPATH=src python3 -m vector.vector_search "$QUERY" "$TOP_K"
elif [ "$1" = "hybrid" ]; then
    QUERY="${2:-}"
    TOP_K="${3:-50}"
    if [ -z "$QUERY" ]; then
        echo "Error: missing query argument"
        usage
    fi
    echo "Hybrid search for: $QUERY (top_k=$TOP_K)"
    echo "------------------------------------------------------------"
    PYTHONPATH=src python3 -m retrieval.hybrid_search "$QUERY" "$TOP_K"
elif [ "$1" = "fusion" ]; then
    QUERY="${2:-}"
    TOP_K="${3:-20}"
    if [ -z "$QUERY" ]; then
        echo "Error: missing query argument"
        usage
    fi
    echo "Retrieval fusion for: $QUERY (top_k=$TOP_K)"
    echo "------------------------------------------------------------"
    PYTHONPATH=src python3 -m retrieval.retrieval_engine "$QUERY" "$TOP_K"
else
    if [ $# -eq 1 ]; then
        echo "Legacy search for: $1"
        echo "------------------------------------------------------------"
        python3 src/search.py "$1"
    else
        echo "Error: unknown mode '$1'"
        usage
    fi
fi
