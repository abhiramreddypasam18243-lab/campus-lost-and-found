from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from typing import Any

DEFAULT_WEIGHTS = {
    "text": 0.40,
    "image": 0.35,
    "location": 0.15,
    "time": 0.10,
}


def calculate_text_score(cosine_similarity: float) -> float:
    """AC-51: Text score is max(0, cosine) of normalized embeddings."""
    return max(0.0, float(cosine_similarity))


def calculate_time_score(
    lost_start: datetime,
    lost_end: datetime,
    found_start: datetime,
    found_end: datetime,
) -> float:
    """AC-52: Time score with overlapping windows and asymmetric decay.

    - Overlapping windows score 1.0
    - If found after lost: exp(-gap / 48)
    - If found before lost: exp(-gap / 6)
    """
    # Check if windows overlap
    if max(lost_start, found_start) <= min(lost_end, found_end):
        return 1.0

    # Found is strictly after lost
    if found_start > lost_end:
        gap_hours = (found_start - lost_end).total_seconds() / 3600.0
        return math.exp(-gap_hours / 48.0)

    # Found is strictly before lost
    gap_hours = (lost_start - found_end).total_seconds() / 3600.0
    return math.exp(-gap_hours / 6.0)


def determine_image_signal(lost_has_photo: bool, found_has_photo: bool) -> tuple[str | None, bool]:
    """AC-55: Image signal mode determination:

    - 'image_to_image' when both reports have photos
    - 'text_to_image' when exactly one report has photos
    - None when neither has photos
    """
    if lost_has_photo and found_has_photo:
        return "image_to_image", True
    if lost_has_photo or found_has_photo:
        return "text_to_image", True
    return None, False


def calculate_hybrid_score(
    signals: dict[str, float | None],
    weights: dict[str, float] | None = None,
) -> tuple[float, str, dict[str, float]]:
    """AC-53, AC-54, AC-65: Calculate weighted hybrid score with dynamic renormalization.

    Missing signals are excluded, never counted as zero.
    Returns (score, bin, contributions).
    Bins: >= 0.75 'high', >= 0.55 'medium', else 'low'.
    """
    active_weights = weights or DEFAULT_WEIGHTS
    available_signals = {k: v for k, v in signals.items() if v is not None}

    if not available_signals:
        return 0.0, "low", {}

    total_available_weight = sum(active_weights[k] for k in available_signals)
    if total_available_weight <= 0.0:
        return 0.0, "low", {}

    contributions: dict[str, float] = {}
    for k, s in available_signals.items():
        contributions[k] = (active_weights[k] * s) / total_available_weight

    combined_score = sum(contributions.values())

    if combined_score >= 0.75:
        score_bin = "high"
    elif combined_score >= 0.55:
        score_bin = "medium"
    else:
        score_bin = "low"

    return combined_score, score_bin, contributions


def generate_explanation(
    signals: dict[str, float | None],
    contributions: dict[str, float],
    combined_score: float,
    image_mode: str | None = None,
    time_gap_hours: float | None = None,
    is_time_after: bool = True,
    location_score: float | None = None,
) -> list[str]:
    """AC-59, AC-60: Generate plain-English explanation of matching signals.

    Lists signals contributing at least 10% of score (or top 3).
    Guarantees no private details or evidence are included.
    """
    if combined_score <= 0.0 or not contributions:
        return ["Potential match based on campus criteria"]

    threshold = 0.10 * combined_score
    sorted_contribs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

    significant = [k for k, v in sorted_contribs if v >= threshold]
    if not significant:
        significant = [k for k, _ in sorted_contribs[:3]]

    explanations: list[str] = []
    for sig in significant:
        if sig == "text":
            explanations.append("Similar description")
        elif sig == "image":
            if image_mode == "image_to_image":
                explanations.append("Visually similar photo")
            else:
                explanations.append("Description visually matches photo")
        elif sig == "location":
            loc_s = location_score if location_score is not None else signals.get("location")
            if loc_s is not None and loc_s >= 0.8:
                explanations.append("Reported in the same location")
            else:
                explanations.append("Reported in a nearby building")
        elif sig == "time":
            time_s = signals.get("time")
            if time_s == 1.0:
                explanations.append("Reported within the same time window")
            elif time_gap_hours is not None:
                rel = "after" if is_time_after else "before"
                hours_str = f"{int(round(time_gap_hours))}"
                explanations.append(f"Found {hours_str} hours {rel} you reported it lost")
            else:
                explanations.append("Reported around the same time")

    return explanations or ["Potential match based on campus criteria"]


def is_valid_candidate_pair(
    lost_report: dict[str, Any],
    found_report: dict[str, Any],
    dismissed_pairs: set[tuple[uuid.UUID, uuid.UUID]],
) -> bool:
    """AC-56: Validate candidate pair criteria:

    - Both reports must be 'open'
    - Reporters differ
    - Pair not dismissed
    - Found item not reserved or returned
    - Found time between 6 hours before lost window starts and 30 days after it ends
    """
    if lost_report.get("status") != "open":
        return False
    if found_report.get("status") != "open":
        return False

    lost_id = lost_report["id"]
    found_id = found_report["id"]

    if lost_report.get("reporter_id") == found_report.get("reporter_id"):
        return False

    if (lost_id, found_id) in dismissed_pairs:
        return False

    if found_report.get("disposition") in ("reserved", "returned"):
        return False

    lost_start = lost_report["window_start"]
    lost_end = lost_report["window_end"]
    found_start = found_report["window_start"]
    found_end = found_report["window_end"]

    lower_bound = lost_start - timedelta(hours=6)
    upper_bound = lost_end + timedelta(days=30)

    # Found window must overlap with [lost_start - 6h, lost_end + 30d]
    if found_end < lower_bound or found_start > upper_bound:
        return False

    return True


def sort_candidates_deterministically(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """AC-57: Order candidates by score descending, then older found report first, then ID."""
    return sorted(
        candidates,
        key=lambda c: (-c["score"], c["found_created_at"], str(c["found_id"])),
    )
