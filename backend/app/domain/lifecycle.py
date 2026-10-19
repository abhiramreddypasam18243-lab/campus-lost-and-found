from typing import Literal

FoundReportState = Literal[
    "pending_review",
    "open",
    "reserved",
    "returned",
    "unclaimed_expired",
    "closed",
    "removed",
]

LostReportState = Literal[
    "open",
    "resolved",
    "closed",
    "removed",
    "expired",
]

# (current_state, action) -> (next_state, allowed_roles)
# actions: approve, reject_remove, reserve, return_item, cancel_reservation, close, expire, resolve
FOUND_TRANSITIONS: dict[tuple[str, str], str] = {
    ("pending_review", "approve"): "open",
    ("pending_review", "remove"): "removed",
    ("open", "reserve"): "reserved",
    ("open", "close"): "closed",
    ("open", "remove"): "removed",
    ("open", "expire"): "unclaimed_expired",
    ("reserved", "complete_handover"): "returned",
    ("reserved", "cancel_handover"): "open",
}

LOST_TRANSITIONS: dict[tuple[str, str], str] = {
    ("open", "resolve"): "resolved",
    ("open", "close"): "closed",
    ("open", "remove"): "removed",
    ("open", "expire"): "expired",
}

ALL_FOUND_STATES: set[str] = {
    "pending_review",
    "open",
    "reserved",
    "returned",
    "unclaimed_expired",
    "closed",
    "removed",
}

ALL_FOUND_ACTIONS: set[str] = {
    "approve",
    "remove",
    "reserve",
    "close",
    "expire",
    "complete_handover",
    "cancel_handover",
}

ALL_LOST_STATES: set[str] = {
    "open",
    "resolved",
    "closed",
    "removed",
    "expired",
}

ALL_LOST_ACTIONS: set[str] = {
    "resolve",
    "close",
    "remove",
    "expire",
}


def transition_found_report(current_state: str, action: str) -> str:
    """Transition found report to next state or raise ValueError if invalid."""
    key = (current_state, action)
    if key in FOUND_TRANSITIONS:
        return FOUND_TRANSITIONS[key]
    raise ValueError(f"invalid_transition: cannot perform '{action}' on state '{current_state}'")


def transition_lost_report(current_state: str, action: str) -> str:
    """Transition lost report to next state or raise ValueError if invalid."""
    key = (current_state, action)
    if key in LOST_TRANSITIONS:
        return LOST_TRANSITIONS[key]
    raise ValueError(f"invalid_transition: cannot perform '{action}' on state '{current_state}'")
