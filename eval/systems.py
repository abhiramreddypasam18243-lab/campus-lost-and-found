"""Retrieval systems and ablation evaluation implementations (AC-116, AC-119)."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime
from typing import Any

from eval.bm25 import BM25Index
from eval.generator import ReportData, TrueItem


def _cosine_similarity(vec_a: list[float] | None, vec_b: list[float] | None) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, (dot / (norm_a * norm_b) + 1.0) / 2.0))


def _location_score(loc_a: str, loc_b: str) -> float:
    if loc_a == loc_b:
        return 1.0
    bldg_a = loc_a.split(" - ")[0]
    bldg_b = loc_b.split(" - ")[0]
    if bldg_a == bldg_b:
        return 0.60
    return 0.0


def _time_score(time_str_a: str, time_str_b: str) -> float:
    try:
        t_a = datetime.fromisoformat(time_str_a)
        t_b = datetime.fromisoformat(time_str_b)
        diff_hours = abs((t_b - t_a).total_seconds()) / 3600.0
        # 48-hour half-life exponential decay
        return round(math.exp(-0.0144 * diff_hours), 4)
    except Exception:
        return 0.50


def score_system_a_bm25(query: ReportData, candidates: list[ReportData]) -> list[float]:
    """System A: BM25 keyword search over title and description."""
    corpus = [f"{c.title} {c.description}" for c in candidates]
    index = BM25Index(corpus)
    q_text = f"{query.title} {query.description}"
    return [index.score(q_text, i) for i in range(len(candidates))]


def score_system_b_text_embeddings(query: ReportData, candidates: list[ReportData]) -> list[float]:
    """System B: Text embedding semantic similarity."""
    # Deterministic simulated semantic similarity based on category and shared tokens
    q_tokens = set(query.title.lower().split() + query.description.lower().split())
    scores = []
    for c in candidates:
        c_tokens = set(c.title.lower().split() + c.description.lower().split())
        cat_match = 0.50 if c.category == query.category else 0.05
        jaccard = len(q_tokens & c_tokens) / max(1, len(q_tokens | c_tokens))
        scores.append(round(0.6 * cat_match + 0.4 * jaccard, 4))
    return scores


def score_system_c_image(query: ReportData, candidates: list[ReportData]) -> list[float]:
    """System C: Image similarity on reports with photos."""
    if not query.has_photo or not query.photo_descriptor:
        return [0.0] * len(candidates)
    scores = []
    for c in candidates:
        if c.has_photo and c.photo_descriptor:
            scores.append(_cosine_similarity(query.photo_descriptor, c.photo_descriptor))
        else:
            scores.append(0.0)
    return scores


def score_system_d_hybrid(
    query: ReportData,
    candidates: list[ReportData],
    weights: dict[str, float] | None = None,
    drop_signal: str | None = None,
) -> list[float]:
    """System D: Hand-weighted hybrid retrieval with dynamic weight normalization."""
    w = weights or {"w_text": 0.40, "w_photo": 0.30, "w_location": 0.20, "w_time": 0.10}

    s_bm25 = score_system_a_bm25(query, candidates)
    s_text = score_system_b_text_embeddings(query, candidates)
    s_photo = score_system_c_image(query, candidates)

    # Normalize BM25 scores
    max_bm25 = max(s_bm25) if s_bm25 and max(s_bm25) > 0 else 1.0
    s_bm25_norm = [s / max_bm25 for s in s_bm25]

    scores = []
    for i, c in enumerate(candidates):
        text_signal = 0.5 * s_bm25_norm[i] + 0.5 * s_text[i]
        photo_signal = s_photo[i]
        loc_signal = _location_score(query.location, c.location)
        time_signal = _time_score(query.timestamp, c.timestamp)

        active_weights = dict(w)
        if drop_signal == "text":
            active_weights["w_text"] = 0.0
        elif drop_signal == "photo" or not (query.has_photo and c.has_photo):
            active_weights["w_photo"] = 0.0
        elif drop_signal == "location":
            active_weights["w_location"] = 0.0
        elif drop_signal == "time":
            active_weights["w_time"] = 0.0

        total_weight = sum(active_weights.values())
        if total_weight > 0:
            combined = (
                active_weights.get("w_text", 0.0) * text_signal
                + active_weights.get("w_photo", 0.0) * photo_signal
                + active_weights.get("w_location", 0.0) * loc_signal
                + active_weights.get("w_time", 0.0) * time_signal
            ) / total_weight
        else:
            combined = 0.0
        scores.append(round(combined, 4))
    return scores


def score_system_e_learned_fusion(
    query: ReportData,
    candidates: list[ReportData],
    fusion_params: dict[str, Any] | None = None,
) -> list[float]:
    """System E: Learned fusion hybrid (logistic regression over per-signal features)."""
    coefs = (fusion_params or {}).get("weights", {
        "text_coef": 2.85,
        "photo_coef": 2.45,
        "location_coef": 1.65,
        "time_coef": 1.10,
        "has_photo_bias": 0.15,
        "intercept": -3.20,
    })

    s_text = score_system_b_text_embeddings(query, candidates)
    s_photo = score_system_c_image(query, candidates)

    scores = []
    for i, c in enumerate(candidates):
        loc_s = _location_score(query.location, c.location)
        time_s = _time_score(query.timestamp, c.timestamp)
        has_p = 1.0 if (query.has_photo and c.has_photo) else 0.0

        logit = (
            coefs["text_coef"] * s_text[i]
            + coefs["photo_coef"] * s_photo[i]
            + coefs["location_coef"] * loc_s
            + coefs["time_coef"] * time_s
            + coefs["has_photo_bias"] * has_p
            + coefs["intercept"]
        )
        prob = 1.0 / (1.0 + math.exp(-max(-15.0, min(15.0, logit))))
        scores.append(round(prob, 4))
    return scores


def evaluate_system_ranks(
    items: list[TrueItem],
    candidate_pool: list[ReportData],
    score_fn: Callable[[ReportData, list[ReportData]], list[float]],
) -> list[int]:
    """Evaluate retrieval ranks for a set of query items across candidate pool."""
    ranks: list[int] = []

    for item in items:
        target_id = item.found_report.id
        # Ensure candidate pool contains target item
        pool = list(candidate_pool)
        if not any(c.id == target_id for c in pool):
            pool.append(item.found_report)

        scores = score_fn(item.lost_report, pool)
        scored_candidates = list(zip(pool, scores, strict=False))
        # Sort descending by score; break ties deterministically by candidate ID
        scored_candidates.sort(key=lambda x: (x[1], x[0].id), reverse=True)

        # Find 1-based rank of target
        rank = -1
        for r_idx, (cand, _) in enumerate(scored_candidates, 1):
            if cand.id == target_id:
                rank = r_idx
                break
        ranks.append(rank if rank > 0 else len(pool))

    return ranks
