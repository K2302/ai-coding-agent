# Import retrieval_engine lazily to avoid circular import with __main__
from retrieval.fusion import _parallel_retrieve, merge_results
from retrieval.scoring import compute_final_score, normalize_scores

__all__ = ["_parallel_retrieve", "merge_results", "compute_final_score", "normalize_scores"]