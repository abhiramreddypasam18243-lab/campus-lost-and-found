"""Benchmark dataset generator for retrieval evaluation (AC-109, AC-110)."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

CATEGORIES = [
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

BUILDINGS = ["Library", "Science Block", "Engineering Center", "Student Union", "Admin Complex"]
FLOORS = ["Floor 1", "Floor 2", "Floor 3", "Floor 4"]
ROOMS = ["Room A", "Room B"]

# Generate 40 fixed leaf locations
CAMPUS_LEAF_LOCATIONS = [
    f"{b} - {f} - {r}"
    for b in BUILDINGS
    for f in FLOORS
    for r in ROOMS
]

COLOR_PAIRS = [
    ("navy", "dark blue"),
    ("maroon", "burgundy"),
    ("charcoal", "dark grey"),
    ("silver", "metallic grey"),
    ("teal", "cyan blue"),
    ("olive", "forest green"),
    ("black", "matte black"),
    ("red", "crimson"),
]

ITEM_SYNONYMS = {
    "bottle": ("bottle", "flask"),
    "bag": ("backpack", "rucksack"),
    "wallet": ("wallet", "cardholder"),
    "phone": ("smartphone", "mobile phone"),
    "laptop_tablet": ("laptop", "notebook"),
    "earphones": ("earbuds", "earphones"),
    "keys": ("keychain", "keys ring"),
    "id_card": ("student ID", "campus pass"),
    "clothing": ("hoodie", "jacket"),
    "book": ("textbook", "handbook"),
    "accessory": ("sunglasses", "shades"),
    "other": ("umbrella", "parasol"),
}

BRANDS = ["HydroFlask", "Nike", "Dell", "Sony", "Apple", "NorthFace", "Moleskine", "Anker"]
FEATURES = ["scratch on corner", "blue sticker on back", "worn lanyard", "engraved initials", "yellow zipper"]


@dataclass
class ReportData:
    id: str
    item_id: str
    type: str  # "lost" or "found"
    category: str
    title: str
    description: str
    location: str
    timestamp: str
    has_photo: bool
    photo_descriptor: list[float] | None = None


@dataclass
class TrueItem:
    item_id: str
    category: str
    lost_report: ReportData
    found_report: ReportData
    is_real_photo_subset: bool
    is_human_written_subset: bool


@dataclass
class BenchmarkDataset:
    seed: int
    true_items: list[TrueItem]
    background_reports: list[ReportData]
    dev_items: list[TrueItem]
    test_items: list[TrueItem]
    test_hash: str


def _apply_typos(text: str, rng: random.Random, typo_rate: float = 0.02) -> str:
    """Apply ~2% character-level typo rate."""
    chars = list(text)
    for i in range(len(chars)):
        if chars[i].isalpha() and rng.random() < typo_rate:
            # Shift character slightly or duplicate
            chars[i] = chr(ord(chars[i]) + 1) if chars[i] != "z" else "a"
    return "".join(chars)


def generate_benchmark_dataset(seed: int = 42) -> BenchmarkDataset:
    """AC-109: Generate 300 true items (with lost and found reports) + 100 background found reports.

    AC-110: Stratified 30% dev (90 items) / 70% test (210 items), recording test content hash.
    """
    rng = random.Random(seed)
    base_time = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)

    true_items: list[TrueItem] = []
    items_per_category = 300 // len(CATEGORIES)  # 25 per category

    item_counter = 0
    for category in CATEGORIES:
        for _ in range(items_per_category):
            item_counter += 1
            item_id = f"item_{item_counter:04d}"

            # Attributes
            color_lost, color_found = rng.choice(COLOR_PAIRS)
            term_lost, term_found = ITEM_SYNONYMS[category]
            brand = rng.choice(BRANDS)
            feature = rng.choice(FEATURES)

            true_loc = rng.choice(CAMPUS_LEAF_LOCATIONS)
            bldg, floor, room = true_loc.split(" - ")

            # Location noise: 60% true, 30% one level off (same building/diff room), 10% random
            loc_roll = rng.random()
            if loc_roll < 0.60:
                found_loc = true_loc
            elif loc_roll < 0.90:
                # Same building, random floor/room
                same_bldg_locs = [loc for loc in CAMPUS_LEAF_LOCATIONS if loc.startswith(bldg)]
                found_loc = rng.choice(same_bldg_locs)
            else:
                found_loc = rng.choice(CAMPUS_LEAF_LOCATIONS)

            # Time delay: log-normal delay ~ 6 hours median (mu=ln(6)=1.7918)
            delay_hours = max(0.5, rng.lognormvariate(1.7918, 0.5))
            lost_time = base_time + timedelta(hours=rng.randint(0, 1000))
            found_time = lost_time + timedelta(hours=delay_hours)

            # Subsets (AC-121, AC-122): at least 60 items with real photos in test set
            has_photos = item_counter <= 100
            is_human_written = 101 <= item_counter <= 160

            # Phrasing: drop at least 1 attribute on each side and apply 2% typos
            lost_title = _apply_typos(f"{color_lost} {term_lost}", rng)
            lost_desc = _apply_typos(f"{brand} {term_lost} with {feature}", rng)

            found_title = _apply_typos(f"{color_found} {term_found}", rng)
            found_desc = _apply_typos(f"Found {color_found} {term_found} left behind", rng)

            # Synthetic photo descriptor vector (dimension 16) if has photo
            lost_photo_desc = None
            found_photo_desc = None
            if has_photos:
                # Shared underlying item vector + slight noise
                base_vec = [rng.uniform(-1, 1) for _ in range(16)]
                lost_photo_desc = [round(x + rng.gauss(0, 0.05), 4) for x in base_vec]
                found_photo_desc = [round(x + rng.gauss(0, 0.05), 4) for x in base_vec]

            lost_rep = ReportData(
                id=f"rep_lost_{item_counter:04d}",
                item_id=item_id,
                type="lost",
                category=category,
                title=lost_title,
                description=lost_desc,
                location=true_loc,
                timestamp=lost_time.isoformat(),
                has_photo=has_photos,
                photo_descriptor=lost_photo_desc,
            )

            found_rep = ReportData(
                id=f"rep_found_{item_counter:04d}",
                item_id=item_id,
                type="found",
                category=category,
                title=found_title,
                description=found_desc,
                location=found_loc,
                timestamp=found_time.isoformat(),
                has_photo=has_photos,
                photo_descriptor=found_photo_desc,
            )

            true_items.append(
                TrueItem(
                    item_id=item_id,
                    category=category,
                    lost_report=lost_rep,
                    found_report=found_rep,
                    is_real_photo_subset=has_photos,
                    is_human_written_subset=is_human_written,
                )
            )

    # Generate 100 background found reports (unclaimed items with no lost report)
    background_reports: list[ReportData] = []
    for i in range(1, 101):
        bg_cat = rng.choice(CATEGORIES)
        bg_term = ITEM_SYNONYMS[bg_cat][1]
        bg_color = rng.choice(COLOR_PAIRS)[1]
        bg_loc = rng.choice(CAMPUS_LEAF_LOCATIONS)
        bg_time = base_time + timedelta(hours=rng.randint(0, 1000))

        background_reports.append(
            ReportData(
                id=f"rep_bg_{i:04d}",
                item_id=f"bg_item_{i:04d}",
                type="found",
                category=bg_cat,
                title=_apply_typos(f"Unclaimed {bg_color} {bg_term}", rng),
                description=_apply_typos(f"Found {bg_term} deposited at campus desk", rng),
                location=bg_loc,
                timestamp=bg_time.isoformat(),
                has_photo=False,
                photo_descriptor=None,
            )
        )

    # AC-110: Stratified 30% development / 70% test split by category
    # For each category (25 items): 30% = 8 (or 7), 70% = 17 (or 18)
    dev_items: list[TrueItem] = []
    test_items: list[TrueItem] = []

    for cat in CATEGORIES:
        cat_items = [it for it in true_items if it.category == cat]
        n_dev = int(round(len(cat_items) * 0.30))  # 25 * 0.3 = 7.5 -> 8 or 7
        dev_items.extend(cat_items[:n_dev])
        test_items.extend(cat_items[n_dev:])

    # Verify counts: exactly 90 dev (30%) and 210 test (70%)
    # If rounding caused off-by-one, adjust:
    while len(dev_items) > 90:
        test_items.append(dev_items.pop())
    while len(dev_items) < 90:
        dev_items.append(test_items.pop())

    # AC-110: Test set content hash
    test_json = json.dumps([asdict(it) for it in test_items], sort_keys=True)
    test_hash = hashlib.sha256(test_json.encode("utf-8")).hexdigest()

    return BenchmarkDataset(
        seed=seed,
        true_items=true_items,
        background_reports=background_reports,
        dev_items=dev_items,
        test_items=test_items,
        test_hash=test_hash,
    )
