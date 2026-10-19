import re

# Email pattern
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Phone pattern matching country codes or explicit phone formatting with separators
PHONE_REGEX = re.compile(r"\+\d{1,4}[-.\s]+\d{3,5}[-.\s]+\d{3,6}")

# Potential card / long number runs (allowing spaces and hyphens)
DIGIT_RUN_REGEX = re.compile(r"(?:\d[-.\s]*){9,19}\d")


def luhn_check(digits_str: str) -> bool:
    """Validate a string of digits using Luhn algorithm."""
    if not digits_str.isdigit():
        return False
    digits = [int(d) for d in digits_str]
    # Reverse digits
    digits.reverse()
    total = 0
    for idx, d in enumerate(digits):
        if idx % 2 == 1:
            doubled = d * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += d
    return total % 10 == 0


def scan_pii(text: str) -> str | None:
    """AC-28: Scan text for PII patterns.

    Returns the kind of PII detected ('card_number', 'long_number', 'phone', 'email')
    or None if clean.
    """
    if not text:
        return None

    # 1. Email Check
    if EMAIL_REGEX.search(text):
        return "email"

    # 2. Phone Number Check with explicit phone markers
    if PHONE_REGEX.search(text):
        return "phone"

    # 3. Card Number and Long Number Check
    digit_matches = list(DIGIT_RUN_REGEX.finditer(text))
    for match in digit_matches:
        digits_only = re.sub(r"\D", "", match.group(0))
        length = len(digits_only)

        # Credit cards: 13 to 19 digits and pass Luhn
        if 13 <= length <= 19 and luhn_check(digits_only):
            return "card_number"

    # 4. Long number: any run of 9 or more digits (that fails Luhn or is 9-12 digits)
    for match in digit_matches:
        digits_only = re.sub(r"\D", "", match.group(0))
        if len(digits_only) >= 9:
            return "long_number"

    return None
