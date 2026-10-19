"""Evaluation metrics for lost-item retrieval benchmark (AC-112).

Calculates Recall@K, MRR, nDCG@K, and Precision@K for first-correct ranks.
"""

from __future__ import annotations

import math


def recall_at_k(ranks: list[int], k: int) -> float:
    """AC-112: Recall@K (equal to hit rate for single relevant document).

    Fraction of queries where the relevant item rank <= k.
    """
    if not ranks:
        return 0.0
    hits = sum(1 for r in ranks if 1 <= r <= k)
    return round(hits / len(ranks), 4)


def mrr(ranks: list[int]) -> float:
    """AC-112: Mean Reciprocal Rank (MRR).

    Average of 1 / rank for each query.
    """
    if not ranks:
        return 0.0
    reciprocal_sum = sum(1.0 / r for r in ranks if r > 0)
    return round(reciprocal_sum / len(ranks), 4)


def ndcg_at_k(ranks: list[int], k: int) -> float:
    """AC-112: Normalized Discounted Cumulative Gain at K (nDCG@K).

    For binary relevance with 1 relevant item, IDCG = 1 / log2(1 + 1) = 1.0.
    DCG = 1 / log2(rank + 1) if rank <= k else 0.0.
    """
    if not ranks:
        return 0.0
    idcg = 1.0  # 1.0 / math.log2(2) == 1.0
    dcg_sum = 0.0
    for r in ranks:
        if 1 <= r <= k:
            dcg_sum += (1.0 / math.log2(r + 1)) / idcg
    return round(dcg_sum / len(ranks), 4)


def precision_at_k(ranks: list[int], k: int) -> float:
    """AC-112: Precision@K.

    For binary relevance with 1 relevant item, if rank <= k precision is 1/k,
    else 0.0. (Capped at 1/K).
    """
    if not ranks or k <= 0:
        return 0.0
    precisions = [1.0 / k if 1 <= r <= k else 0.0 for r in ranks]
    return round(sum(precisions) / len(ranks), 4)


def compute_retrieval_metrics(ranks: list[int]) -> dict[str, float]:
    """Calculate standard benchmark metrics dictionary."""
    return {
        "recall_at_1": recall_at_k(ranks, 1),
        "recall_at_3": recall_at_k(ranks, 3),
        "recall_at_5": recall_at_k(ranks, 5),
        "recall_at_10": recall_at_k(ranks, 10),
        "mrr": mrr(ranks),
        "ndcg_at_10": round(ndcg_at_k(ranks, 10), 3),
        "precision_at_5": precision_at_k(ranks, 5),
    }
