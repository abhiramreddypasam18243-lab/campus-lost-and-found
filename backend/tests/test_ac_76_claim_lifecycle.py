"""Unit tests for AC-76: Claim Lifecycle (spec section 5.3).
Exhaustive test of all (state, action) pairs.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.claims import (
    CLAIM_TRANSITIONS,
    ClaimAction,
    ClaimStatus,
    InvalidTransitionError,
    calculate_active_claim_limit,
    can_moderator_access_claim,
    check_conflict_of_interest,
    is_claim_active,
    is_claim_escalated,
    is_lock_active,
    transition_claim,
    validate_verification_answers,
)


def test_ac_76_all_legal_transitions_succeed() -> None:
    """AC-76: Every legal transition in the table of section 5.3 succeeds."""
    expected_transitions = {
        ("submitted", "open_review"): "under_review",
        ("submitted", "withdraw"): "withdrawn",
        ("under_review", "approve"): "approved",
        ("under_review", "reject"): "rejected",
        ("under_review", "request_info"): "needs_more_info",
        ("under_review", "withdraw"): "withdrawn",
        ("needs_more_info", "submit_info"): "submitted",
        ("needs_more_info", "withdraw"): "withdrawn",
        ("approved", "complete"): "completed",
        ("approved", "expire"): "expired",
        ("approved", "withdraw"): "withdrawn",
    }

    assert len(CLAIM_TRANSITIONS) == len(expected_transitions)

    for (current, action), expected_target in expected_transitions.items():
        result = transition_claim(current, action)
        assert result == expected_target, (
            f"Failed legal transition {current} --{action}--> {result}"
        )


def test_ac_76_exhaustive_illegal_transitions_fail() -> None:
    """AC-76: Every illegal (state, action) pair raises InvalidTransitionError (tested exhaustively)."""
    legal_pairs = {(status.value, action.value) for (status, action) in CLAIM_TRANSITIONS.keys()}

    all_statuses = [s.value for s in ClaimStatus]
    all_actions = [a.value for a in ClaimAction]

    for status in all_statuses:
        for action in all_actions:
            if (status, action) not in legal_pairs:
                with pytest.raises(InvalidTransitionError) as exc_info:
                    transition_claim(status, action)
                assert exc_info.value.current_status == status
                assert exc_info.value.action == action


def test_ac_76_active_and_terminal_statuses() -> None:
    """Verify active vs terminal status classifications."""
    assert is_claim_active("submitted") is True
    assert is_claim_active("under_review") is True
    assert is_claim_active("needs_more_info") is True
    assert is_claim_active("approved") is True

    assert is_claim_active("rejected") is False
    assert is_claim_active("completed") is False
    assert is_claim_active("expired") is False
    assert is_claim_active("withdrawn") is False


def test_ac_80_conflict_of_interest_domain() -> None:
    """AC-80: Moderator cannot decide if reporter of item or claimant."""
    u1 = uuid.uuid4()
    u2 = uuid.uuid4()
    u3 = uuid.uuid4()

    # Moderator is reporter of found item -> conflict
    assert check_conflict_of_interest(u1, u1, u2) is True
    # Moderator is claimant -> conflict
    assert check_conflict_of_interest(u1, u2, u1) is True
    # Moderator is independent third-party -> no conflict
    assert check_conflict_of_interest(u1, u2, u3) is False


def test_ac_78_lock_domain_rules() -> None:
    """AC-78: 30-minute lock behavior."""
    now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)
    mod1 = uuid.uuid4()
    mod2 = uuid.uuid4()

    # Unlocked
    assert is_lock_active(None, None, now) is False
    assert can_moderator_access_claim(mod1, None, None, now) is True

    # Active lock held by mod1
    exp_future = now + timedelta(minutes=30)
    assert is_lock_active(mod1, exp_future, now) is True
    assert can_moderator_access_claim(mod1, mod1, exp_future, now) is True
    assert can_moderator_access_claim(mod2, mod1, exp_future, now) is False

    # Expired lock held by mod1
    exp_past = now - timedelta(seconds=1)
    assert is_lock_active(mod1, exp_past, now) is False
    assert can_moderator_access_claim(mod2, mod1, exp_past, now) is True


def test_ac_84_active_limit_calculation() -> None:
    """AC-84: 3 rejected claims in 30 days reduces limit to 1 active claim."""
    assert calculate_active_claim_limit(0) == 3
    assert calculate_active_claim_limit(2) == 3
    assert calculate_active_claim_limit(3) == 1
    assert calculate_active_claim_limit(5) == 1


def test_ac_85_escalation_detection() -> None:
    """AC-85: Claim unreviewed after 14 days is escalated."""
    now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)
    sub_10d = now - timedelta(days=10)
    sub_14d = now - timedelta(days=14)
    sub_15d = now - timedelta(days=15)

    assert is_claim_escalated(sub_10d, now, "submitted") is False
    assert is_claim_escalated(sub_14d, now, "submitted") is True
    assert is_claim_escalated(sub_15d, now, "submitted") is True

    # Decided or terminal claim is never escalated
    assert is_claim_escalated(sub_15d, now, "approved") is False
    assert is_claim_escalated(sub_15d, now, "rejected") is False


def test_ac_75_prompt_validation() -> None:
    """AC-75: Every verification prompt must have a non-empty answer."""
    prompts = ["What colour is the keychain?", "What stickers are on it?"]
    answers = {"What colour is the keychain?": "Red", "What stickers are on it?": "RIA sticker"}

    ok, err = validate_verification_answers(prompts, answers)
    assert ok is True
    assert err is None

    # Missing answer
    bad_answers = {"What colour is the keychain?": "Red"}
    ok, err = validate_verification_answers(prompts, bad_answers)
    assert ok is False
    assert "Missing or empty answer" in (err or "")

    # Empty answer
    empty_answers = {"What colour is the keychain?": "Red", "What stickers are on it?": "   "}
    ok, err = validate_verification_answers(prompts, empty_answers)
    assert ok is False
    assert "Missing or empty answer" in (err or "")
