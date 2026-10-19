"""Pure domain logic for claim lifecycle, locks, conflict of interest, and limits.
Zero external framework, database, or clock dependencies (SEC4, FR-11, FR-12).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any


class ClaimStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    NEEDS_MORE_INFO = "needs_more_info"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class ClaimAction(StrEnum):
    OPEN_REVIEW = "open_review"
    REQUEST_INFO = "request_info"
    SUBMIT_INFO = "submit_info"
    APPROVE = "approve"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    COMPLETE = "complete"
    EXPIRE = "expire"


class InvalidTransitionError(Exception):
    """Raised when an illegal lifecycle transition is attempted."""

    def __init__(self, current_status: str, action: str) -> None:
        super().__init__(
            f"Invalid claim transition from status '{current_status}' via action '{action}'"
        )
        self.current_status = current_status
        self.action = action


# Spec section 5.3 transition table: (current_status, action) -> new_status
CLAIM_TRANSITIONS: dict[tuple[ClaimStatus, ClaimAction], ClaimStatus] = {
    # submitted
    (ClaimStatus.SUBMITTED, ClaimAction.OPEN_REVIEW): ClaimStatus.UNDER_REVIEW,
    (ClaimStatus.SUBMITTED, ClaimAction.WITHDRAW): ClaimStatus.WITHDRAWN,
    # under_review
    (ClaimStatus.UNDER_REVIEW, ClaimAction.APPROVE): ClaimStatus.APPROVED,
    (ClaimStatus.UNDER_REVIEW, ClaimAction.REJECT): ClaimStatus.REJECTED,
    (ClaimStatus.UNDER_REVIEW, ClaimAction.REQUEST_INFO): ClaimStatus.NEEDS_MORE_INFO,
    (ClaimStatus.UNDER_REVIEW, ClaimAction.WITHDRAW): ClaimStatus.WITHDRAWN,
    # needs_more_info
    (ClaimStatus.NEEDS_MORE_INFO, ClaimAction.SUBMIT_INFO): ClaimStatus.SUBMITTED,
    (ClaimStatus.NEEDS_MORE_INFO, ClaimAction.WITHDRAW): ClaimStatus.WITHDRAWN,
    # approved
    (ClaimStatus.APPROVED, ClaimAction.COMPLETE): ClaimStatus.COMPLETED,
    (ClaimStatus.APPROVED, ClaimAction.EXPIRE): ClaimStatus.EXPIRED,
    (ClaimStatus.APPROVED, ClaimAction.WITHDRAW): ClaimStatus.WITHDRAWN,
}

ACTIVE_CLAIM_STATUSES: set[str] = {
    ClaimStatus.SUBMITTED.value,
    ClaimStatus.UNDER_REVIEW.value,
    ClaimStatus.NEEDS_MORE_INFO.value,
    ClaimStatus.APPROVED.value,
}

TERMINAL_CLAIM_STATUSES: set[str] = {
    ClaimStatus.REJECTED.value,
    ClaimStatus.COMPLETED.value,
    ClaimStatus.EXPIRED.value,
    ClaimStatus.WITHDRAWN.value,
}


def transition_claim(current_status: str, action: str) -> str:
    """Validate and perform claim status transition per AC-76 and spec 5.3."""
    try:
        status_enum = ClaimStatus(current_status)
        action_enum = ClaimAction(action)
    except ValueError as err:
        raise InvalidTransitionError(current_status, action) from err

    key = (status_enum, action_enum)
    if key not in CLAIM_TRANSITIONS:
        raise InvalidTransitionError(current_status, action)

    return CLAIM_TRANSITIONS[key].value


def is_claim_active(status: str) -> bool:
    """Return True if claim is in an active (non-terminal) state."""
    return status in ACTIVE_CLAIM_STATUSES


def check_conflict_of_interest(
    moderator_id: uuid.UUID,
    found_reporter_id: uuid.UUID,
    claimant_id: uuid.UUID,
) -> bool:
    """AC-80: A moderator cannot decide a claim on an item they reported,

    or a claim they made themselves.
    Returns True if a conflict exists.
    """
    if moderator_id == found_reporter_id:
        return True
    if moderator_id == claimant_id:
        return True
    return False


def is_lock_active(
    locked_by_id: uuid.UUID | None,
    lock_expires_at: datetime | None,
    now: datetime,
) -> bool:
    """AC-78: Return True if a lock is currently valid."""
    if locked_by_id is None or lock_expires_at is None:
        return False
    return lock_expires_at > now


def can_moderator_access_claim(
    moderator_id: uuid.UUID,
    locked_by_id: uuid.UUID | None,
    lock_expires_at: datetime | None,
    now: datetime,
) -> bool:
    """AC-78: A moderator can access/decide a claim if it is unlocked,

    or if the lock has expired, or if they own the active lock.
    """
    if not is_lock_active(locked_by_id, lock_expires_at, now):
        return True
    return locked_by_id == moderator_id


def calculate_active_claim_limit(rejected_claims_count_last_30d: int) -> int:
    """AC-84: A user with 3 rejected claims in 30 days is limited to 1 active claim (normally 3)."""
    if rejected_claims_count_last_30d >= 3:
        return 1
    return 3


def is_claim_escalated(
    submitted_at: datetime,
    now: datetime,
    status: str,
    threshold_days: int = 14,
) -> bool:
    """AC-85: A claim unreviewed (submitted / not approved/rejected) after 14 days is escalated."""
    if status not in (ClaimStatus.SUBMITTED.value, ClaimStatus.NEEDS_MORE_INFO.value):
        return False
    return (now - submitted_at) >= timedelta(days=threshold_days)


def validate_verification_answers(
    required_prompts: list[str],
    submitted_answers: dict[str, Any],
) -> tuple[bool, str | None]:
    """AC-75: Every verification prompt on the found item must have a non-empty answer."""
    for prompt in required_prompts:
        prompt_clean = prompt.strip()
        if not prompt_clean:
            continue
        # Answer must exist and be non-empty
        ans = submitted_answers.get(prompt_clean)
        if ans is None or not str(ans).strip():
            return False, f"Missing or empty answer for prompt: '{prompt_clean}'"
    return True, None
