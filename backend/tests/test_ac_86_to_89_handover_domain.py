"""Unit tests for AC-86, AC-87, AC-88, AC-89, AC-91, AC-92, AC-95: Handover domain logic."""

from datetime import UTC, datetime, timedelta

from app.domain.handover import (
    HANDOVER_ALPHABET,
    can_attempt_verification,
    can_reissue_code,
    compute_code_hmac,
    generate_handover_code,
    is_code_valid_at_time,
    normalize_handover_code,
    verify_code_constant_time,
)


def test_ac_86_code_length_and_alphabet() -> None:
    """AC-86: 8 characters from 32-character alphabet (40 bits)."""
    assert len(HANDOVER_ALPHABET) == 32
    # Verify no ambiguous characters in alphabet
    assert "O" not in HANDOVER_ALPHABET
    assert "I" not in HANDOVER_ALPHABET
    assert "L" not in HANDOVER_ALPHABET
    assert "U" not in HANDOVER_ALPHABET

    # Generate 100 codes to check length and character set
    for _ in range(100):
        code = generate_handover_code()
        assert len(code) == 8
        for ch in code:
            assert ch in HANDOVER_ALPHABET


def test_ac_87_hmac_storage_properties() -> None:
    """AC-87: Only HMAC-SHA-256 of code is stored; changes with code or secret."""
    secret = "test-secret-key-9988"
    code1 = "A1B2C3D4"
    code2 = "A1B2C3D5"

    h1 = compute_code_hmac(secret, code1)
    h2 = compute_code_hmac(secret, code2)

    assert len(h1) == 64  # SHA-256 hex is 64 characters
    assert h1 != h2
    assert code1 not in h1  # One-way HMAC


def test_ac_88_code_normalization() -> None:
    """AC-88: abcd-1234, ABCD 1234 and ABCD1234 are the same code;

    O -> 0, I -> 1, L -> 1.
    """
    assert normalize_handover_code("abcd-1234") == "ABCD1234"
    assert normalize_handover_code("ABCD 1234") == "ABCD1234"
    assert normalize_handover_code("ABCD1234") == "ABCD1234"

    # Substitutions
    # O -> 0
    assert normalize_handover_code("open-room") == "0PENR00M"
    # I -> 1 and L -> 1
    assert normalize_handover_code("item-lost") == "1TEM10ST"

    # End-to-end verification with normalization
    secret = "server-key-123"
    canonical = "ABCD1234"
    stored_hmac = compute_code_hmac(secret, canonical)

    assert verify_code_constant_time(secret, "abcd-1234", stored_hmac) is True
    assert verify_code_constant_time(secret, "ABCD 1234", stored_hmac) is True
    assert verify_code_constant_time(secret, "ABCD1234", stored_hmac) is True
    assert verify_code_constant_time(secret, "wrong-code", stored_hmac) is False


def test_ac_89_injected_clock_expiry() -> None:
    """AC-89: Valid at T + 47:59:59 and invalid at T + 48:00:00."""
    t = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)

    # Valid right before 48h
    valid_time = t + timedelta(hours=47, minutes=59, seconds=59)
    assert is_code_valid_at_time(t, valid_time) is True

    # Invalid at exact 48h
    exact_expiry = t + timedelta(hours=48)
    assert is_code_valid_at_time(t, exact_expiry) is False

    # Invalid after 48h
    past_expiry = t + timedelta(hours=48, seconds=1)
    assert is_code_valid_at_time(t, past_expiry) is False


def test_ac_91_attempts_lockout_bound() -> None:
    """AC-91: Guessing bound 5 / 2^40 ≈ 4.5e-12. 5 attempts allowed, 6th locked."""
    assert can_attempt_verification(0) is True
    assert can_attempt_verification(4) is True
    assert can_attempt_verification(5) is False
    assert can_attempt_verification(6) is False


def test_ac_92_reissue_bounds() -> None:
    """AC-92: At most 3 reissues."""
    assert can_reissue_code(0) is True
    assert can_reissue_code(1) is True
    assert can_reissue_code(2) is True
    assert can_reissue_code(3) is False
    assert can_reissue_code(4) is False
