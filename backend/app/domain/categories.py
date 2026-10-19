from typing import Final

ALLOWED_CATEGORIES: Final[list[str]] = [
    "bottle",
    "bag",
    "wallet",
    "phone",
    "laptop_tablet",
    "earphones",
    "keys",
    "id_card",
    "clothing",
    "book",
    "accessory",
    "other",
]

SENSITIVE_CATEGORIES: Final[set[str]] = {
    "id_card",
    "wallet",
}


def is_valid_category(category: str) -> bool:
    return category in ALLOWED_CATEGORIES


def is_sensitive_category(category: str) -> bool:
    return category in SENSITIVE_CATEGORIES
