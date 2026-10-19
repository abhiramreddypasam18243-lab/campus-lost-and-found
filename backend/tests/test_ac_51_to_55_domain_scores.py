import math
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.matching import (
    calculate_hybrid_score,
    calculate_text_score,
    calculate_time_score,
    determine_image_signal,
)


def test_ac_51_text_score_cosine() -> None:
    """AC-51: The text score is max(0, cosine) of normalized embeddings.

    A cosine of 0.82 gives 0.82 and -0.10 gives 0.
    """
    assert calculate_text_score(0.82) == pytest.approx(0.82, rel=1e-5)
    assert calculate_text_score(-0.10) == 0.0
    assert calculate_text_score(1.0) == 1.0
    assert calculate_text_score(0.0) == 0.0
    assert calculate_text_score(-0.99) == 0.0


def test_ac_52_time_score_asymmetric_decay() -> None:
    """AC-52: Time score with overlapping windows and asymmetric decay.

    - Overlapping windows score 1.0
    - Found 12h after lost window ends scores 0.7788 (exp(-12/48))
    - Found 48h after lost window ends scores 0.3679 (exp(-48/48))
    - Found 12h before lost window starts scores 0.1353 (exp(-12/6))
    - Found 6h before lost window starts scores 0.3679 (exp(-6/6))
    """
    base = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)
    lost_start = base
    lost_end = base + timedelta(hours=2)

    # 1. Overlapping window
    found_start_overlap = base + timedelta(hours=1)
    found_end_overlap = base + timedelta(hours=3)
    score_overlap = calculate_time_score(
        lost_start, lost_end, found_start_overlap, found_end_overlap
    )
    assert score_overlap == 1.0

    # 2. 12 hours after lost window ends
    found_start_12h_after = lost_end + timedelta(hours=12)
    found_end_12h_after = found_start_12h_after + timedelta(hours=1)
    score_12h_after = calculate_time_score(
        lost_start, lost_end, found_start_12h_after, found_end_12h_after
    )
    expected_12h_after = math.exp(-12.0 / 48.0)
    assert score_12h_after == pytest.approx(0.7788, abs=1e-4)
    assert score_12h_after == pytest.approx(expected_12h_after, rel=1e-5)

    # 3. 48 hours after lost window ends
    found_start_48h_after = lost_end + timedelta(hours=48)
    found_end_48h_after = found_start_48h_after + timedelta(hours=1)
    score_48h_after = calculate_time_score(
        lost_start, lost_end, found_start_48h_after, found_end_48h_after
    )
    expected_48h_after = math.exp(-48.0 / 48.0)
    assert score_48h_after == pytest.approx(0.3679, abs=1e-4)
    assert score_48h_after == pytest.approx(expected_48h_after, rel=1e-5)

    # 4. 12 hours before lost window starts
    found_end_12h_before = lost_start - timedelta(hours=12)
    found_start_12h_before = found_end_12h_before - timedelta(hours=1)
    score_12h_before = calculate_time_score(
        lost_start, lost_end, found_start_12h_before, found_end_12h_before
    )
    expected_12h_before = math.exp(-12.0 / 6.0)
    assert score_12h_before == pytest.approx(0.1353, abs=1e-4)
    assert score_12h_before == pytest.approx(expected_12h_before, rel=1e-5)

    # 5. 6 hours before lost window starts
    found_end_6h_before = lost_start - timedelta(hours=6)
    found_start_6h_before = found_end_6h_before - timedelta(hours=1)
    score_6h_before = calculate_time_score(
        lost_start, lost_end, found_start_6h_before, found_end_6h_before
    )
    expected_6h_before = math.exp(-6.0 / 6.0)
    assert score_6h_before == pytest.approx(0.3679, abs=1e-4)
    assert score_6h_before == pytest.approx(expected_6h_before, rel=1e-5)


def test_ac_53_hybrid_example_and_renormalization() -> None:
    """AC-53: Hybrid score calculation and dynamic renormalization with missing signals.

    With weights text 0.40, image 0.35, location 0.15, time 0.10:
    - Signals 0.8, 0.6, 0.7, 0.5 score 0.685.
    - With image signal missing, remaining weights sum to 0.65 and score is 0.7308.
    """
    weights = {"text": 0.40, "image": 0.35, "location": 0.15, "time": 0.10}
    signals_all = {"text": 0.8, "image": 0.6, "location": 0.7, "time": 0.5}

    score, score_bin, contributions = calculate_hybrid_score(signals_all, weights)
    assert score == pytest.approx(0.685, rel=1e-4)
    assert score_bin == "medium"  # >= 0.55 and < 0.75
    assert sum(contributions.values()) == pytest.approx(score, abs=1e-9)

    # Image missing
    signals_no_image = {"text": 0.8, "image": None, "location": 0.7, "time": 0.5}
    score_no_img, bin_no_img, contrib_no_img = calculate_hybrid_score(signals_no_image, weights)
    # (0.40*0.8 + 0.15*0.7 + 0.10*0.5) / 0.65 = (0.32 + 0.105 + 0.05) / 0.65 = 0.475 / 0.65 = 0.730769...
    assert score_no_img == pytest.approx(0.7308, abs=1e-4)
    assert bin_no_img == "medium"
    assert "image" not in contrib_no_img or contrib_no_img["image"] == 0.0
    assert sum(contrib_no_img.values()) == pytest.approx(score_no_img, abs=1e-9)


def test_ac_54_missing_signals_excluded_never_zero() -> None:
    """AC-54: Missing signals are excluded, never counted as zero.

    A pair with only a text signal scores exactly its text score.
    """
    signals = {"text": 0.82, "image": None, "location": None, "time": None}
    score, score_bin, contributions = calculate_hybrid_score(signals)
    assert score == pytest.approx(0.82, rel=1e-5)
    assert score_bin == "high"  # >= 0.75
    assert contributions["text"] == pytest.approx(0.82, rel=1e-5)


def test_ac_55_image_signal_modes() -> None:
    """AC-55: Image signal logic:

    - image-to-image when both reports have photos
    - text-to-image when exactly one report has photos
    - null when neither does
    """
    # 1. Both have photos
    mode_both, is_available = determine_image_signal(lost_has_photo=True, found_has_photo=True)
    assert mode_both == "image_to_image"
    assert is_available is True

    # 2. Only lost has photo
    mode_lost, is_avail_lost = determine_image_signal(lost_has_photo=True, found_has_photo=False)
    assert mode_lost == "text_to_image"
    assert is_avail_lost is True

    # 3. Only found has photo
    mode_found, is_avail_found = determine_image_signal(lost_has_photo=False, found_has_photo=True)
    assert mode_found == "text_to_image"
    assert is_avail_found is True

    # 4. Neither has photo
    mode_none, is_avail_none = determine_image_signal(lost_has_photo=False, found_has_photo=False)
    assert mode_none is None
    assert is_avail_none is False
