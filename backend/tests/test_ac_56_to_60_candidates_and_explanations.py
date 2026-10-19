import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.matching import (
    calculate_hybrid_score,
    generate_explanation,
    is_valid_candidate_pair,
    sort_candidates_deterministically,
)


def test_ac_56_candidate_filtering_rules() -> None:
    """AC-56: Candidates are only lost-to-found pairs meeting all strict criteria:

    - Both reports must be 'open'
    - Reporters differ
    - Pair not dismissed
    - Found item not reserved or returned
    - Found time between 6 hours before lost window start and 30 days after lost window end
    Each exclusion has its own fixture check.
    """
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    base_time = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

    valid_lost = {
        "id": uuid.uuid4(),
        "status": "open",
        "reporter_id": user_a,
        "window_start": base_time,
        "window_end": base_time + timedelta(hours=2),
    }

    valid_found = {
        "id": uuid.uuid4(),
        "status": "open",
        "reporter_id": user_b,
        "window_start": base_time + timedelta(hours=4),
        "window_end": base_time + timedelta(hours=5),
        "disposition": None,
    }

    # 1. Base valid pair
    assert is_valid_candidate_pair(valid_lost, valid_found, dismissed_pairs=set()) is True

    # 2. Exclusion: Lost report not open
    lost_closed = dict(valid_lost, status="closed")
    assert is_valid_candidate_pair(lost_closed, valid_found, dismissed_pairs=set()) is False

    # 3. Exclusion: Found report not open (e.g. pending_review)
    found_pending = dict(valid_found, status="pending_review")
    assert is_valid_candidate_pair(valid_lost, found_pending, dismissed_pairs=set()) is False

    # 4. Exclusion: Same reporter
    found_same_user = dict(valid_found, reporter_id=user_a)
    assert is_valid_candidate_pair(valid_lost, found_same_user, dismissed_pairs=set()) is False

    # 5. Exclusion: Pair was dismissed
    dismissed = {(valid_lost["id"], valid_found["id"])}
    assert is_valid_candidate_pair(valid_lost, valid_found, dismissed_pairs=dismissed) is False

    # 6. Exclusion: Found item reserved or returned
    found_returned = dict(valid_found, status="returned")
    assert is_valid_candidate_pair(valid_lost, found_returned, dismissed_pairs=set()) is False
    found_reserved = dict(valid_found, disposition="reserved")
    assert is_valid_candidate_pair(valid_lost, found_reserved, dismissed_pairs=set()) is False

    # 7. Exclusion: Found time > 6 hours before lost window start
    found_too_early = dict(
        valid_found,
        window_start=base_time - timedelta(hours=6, minutes=1),
        window_end=base_time - timedelta(hours=6, seconds=1),
    )
    assert is_valid_candidate_pair(valid_lost, found_too_early, dismissed_pairs=set()) is False

    # 8. Borderline valid: Found time exactly 6 hours before lost window start
    found_border_early = dict(
        valid_found,
        window_start=base_time - timedelta(hours=6),
        window_end=base_time - timedelta(hours=5, minutes=30),
    )
    assert is_valid_candidate_pair(valid_lost, found_border_early, dismissed_pairs=set()) is True

    # 9. Exclusion: Found time > 30 days after lost window end
    found_too_late = dict(
        valid_found,
        window_start=valid_lost["window_end"] + timedelta(days=30, seconds=1),
        window_end=valid_lost["window_end"] + timedelta(days=30, hours=1),
    )
    assert is_valid_candidate_pair(valid_lost, found_too_late, dismissed_pairs=set()) is False

    # 10. Borderline valid: Found time within 30 days
    found_border_late = dict(
        valid_found,
        window_start=valid_lost["window_end"] + timedelta(days=29),
        window_end=valid_lost["window_end"] + timedelta(days=29, hours=2),
    )
    assert is_valid_candidate_pair(valid_lost, found_border_late, dismissed_pairs=set()) is True


def test_ac_57_deterministic_candidate_ordering() -> None:
    """AC-57: Order candidates by score descending, then older found report first, then ID."""
    t0 = datetime(2026, 10, 10, 10, 0, tzinfo=UTC)
    t1 = datetime(2026, 10, 11, 10, 0, tzinfo=UTC)

    id_1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    id_2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
    id_3 = uuid.UUID("33333333-3333-3333-3333-333333333333")
    id_4 = uuid.UUID("44444444-4444-4444-4444-444444444444")

    candidates = [
        {"found_id": id_4, "score": 0.70, "found_created_at": t1},
        {"found_id": id_1, "score": 0.85, "found_created_at": t1},
        {"found_id": id_3, "score": 0.70, "found_created_at": t0},  # Older than id_4, same score
        {
            "found_id": id_2,
            "score": 0.70,
            "found_created_at": t0,
        },  # Same score and date as id_3, smaller UUID
    ]

    sorted_list = sort_candidates_deterministically(candidates)
    # Expected order:
    # 1. id_1 (score 0.85)
    # 2. id_2 (score 0.70, older t0, id_2 < id_3)
    # 3. id_3 (score 0.70, older t0, id_3 > id_2)
    # 4. id_4 (score 0.70, newer t1)
    sorted_ids = [c["found_id"] for c in sorted_list]
    assert sorted_ids == [id_1, id_2, id_3, id_4]


def test_ac_59_explanation_exact_additivity_and_values() -> None:
    """AC-59: Explanation contributions sum exactly to the combined score (within 1e-9).

    Lists signals contributing >= 10% of score (or top 3).
    For the example of AC-53 without an image:
    text: 0.4923, location: 0.1615, time: 0.0769.
    """
    weights = {"text": 0.40, "image": 0.35, "location": 0.15, "time": 0.10}
    signals_no_image = {"text": 0.8, "image": None, "location": 0.7, "time": 0.5}

    score, score_bin, contributions = calculate_hybrid_score(signals_no_image, weights)
    assert score == pytest.approx(0.7308, abs=1e-4)

    # Check contributions from AC-53 / AC-59
    assert contributions["text"] == pytest.approx(0.4923, abs=1e-4)
    assert contributions["location"] == pytest.approx(0.1615, abs=1e-4)
    assert contributions["time"] == pytest.approx(0.0769, abs=1e-4)

    # Contributions sum exactly to score within 1e-9
    total_contrib = sum(contributions.values())
    assert abs(total_contrib - score) < 1e-9

    # Generate explanations
    explanations = generate_explanation(
        signals=signals_no_image,
        contributions=contributions,
        combined_score=score,
    )
    assert len(explanations) >= 2
    # Verify explanations describe the main contributors
    explanation_text = " ".join(explanations).lower()
    assert "description" in explanation_text or "text" in explanation_text
    assert "location" in explanation_text or "building" in explanation_text
