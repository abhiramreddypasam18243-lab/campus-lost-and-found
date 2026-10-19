"""Pure domain logic for handover verification codes (spec section 5.4, AC-86 to AC-96).
Zero external framework, database, or network dependencies.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

# AC-86: 32-character alphabet (40 bits of entropy for 8 chars)
HANDOVER_ALPHABET: str = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DEFAULT_CODE_LENGTH: int = 8
MAX_ATTEMPTS: int = 5  # AC-91: Guessing bound 5 / 2^40 ≈ 4.5e-12
MAX_REISSUES: int = 3  # AC-92: At most 3 reissues
VALID_HOURS: int = 48  # AC-89: 48-hour validity


def generate_handover_code(length: int = DEFAULT_CODE_LENGTH) -> str:
    """AC-86: Generate a cryptographically secure random code from the 32-char alphabet."""
    return "".join(secrets.choice(HANDOVER_ALPHABET) for _ in range(length))


def normalize_handover_code(raw: str) -> str:
    """AC-88: Normalise code by uppercasing, dropping spaces and hyphens,

    and mapping 'O' -> '0', 'I' -> '1', 'L' -> '1'.
    """
    cleaned = re.sub(r"[\s\-]+", "", raw.strip()).upper()
    # Apply substitutions
    cleaned = cleaned.replace("O", "0")
    cleaned = cleaned.replace("I", "1")
    cleaned = cleaned.replace("L", "1")
    return cleaned


def compute_code_hmac(secret: str, normalized_code: str) -> str:
    """AC-87: Compute HMAC-SHA-256 hex digest of the normalized code."""
    key_bytes = secret.encode("utf-8")
    msg_bytes = normalized_code.encode("utf-8")
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest()


def verify_code_constant_time(
    secret: str,
    raw_input_code: str,
    stored_hmac: str,
) -> bool:
    """AC-95: Constant-time HMAC comparison using hmac.compare_digest."""
    normalized = normalize_handover_code(raw_input_code)
    candidate_hmac = compute_code_hmac(secret, normalized)
    return hmac.compare_digest(stored_hmac, candidate_hmac)


def is_code_valid_at_time(
    issued_at: datetime,
    check_time: datetime,
    valid_hours: int = VALID_HOURS,
) -> bool:
    """AC-89: A code issued at T is valid at T + 47:59:59 and invalid at T + 48:00:00."""
    expiry_time = issued_at + timedelta(hours=valid_hours)
    return check_time < expiry_time


def can_attempt_verification(attempts: int, max_attempts: int = MAX_ATTEMPTS) -> bool:
    """AC-91: Handover locks after 5 wrong attempts; 6th attempt is blocked."""
    return attempts < max_attempts


def can_reissue_code(reissue_count: int, max_reissues: int = MAX_REISSUES) -> bool:
    """AC-92: Moderator can reissue at most 3 times."""
    return reissue_count < max_reissues
