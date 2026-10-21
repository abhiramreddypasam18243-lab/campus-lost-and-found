"""Seeded synthetic benchmark (spec 7.1; AC-109, AC-110).

300 true items, each with a lost and a found report written with different lexicons, plus 100
background found reports with no owner. Locations live in a campus tree with building
adjacency, and times are windows with a reporting precision, so the benchmark exercises the
same location and time scoring as the application.

What this benchmark does NOT contain (and the results say so): photos, and human-written text.
"""

from __future__ import annotations

import hashlib
import json
import math
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

CAMPUS = "Main Campus"
BUILDINGS = ["Library", "Science Block", "Engineering Center", "Student Union", "Admin Complex"]
FLOORS = ["Floor 1", "Floor 2", "Floor 3", "Floor 4"]
ROOMS = ["Room A", "Room B"]
# Symmetric building adjacency (location score 0.5 instead of 0.2).
ADJACENT_BUILDINGS = [("Library", "Science Block"), ("Engineering Center", "Student Union")]

# 40 leaf locations: building / floor / room
LEAF_LOCATIONS = [f"{b}/{f}/{r}" for b in BUILDINGS for f in FLOORS for r in ROOMS]

# Lost-side and found-side lexicons differ (spec 7.1): ("navy", "dark blue"), ("flask", "bottle").
COLOR_PAIRS = [
    ("navy", "dark blue"),
    ("maroon", "burgundy"),
    ("charcoal", "dark grey"),
    ("silver", "metallic grey"),
    ("teal", "blue-green"),
    ("olive", "khaki green"),
    ("black", "matte black"),
    ("red", "crimson"),
    ("white", "off-white"),
    ("beige", "cream"),
]
ITEM_TERMS = {
    "bottle": ("flask", "water bottle"),
    "bag": ("backpack", "rucksack"),
    "wallet": ("wallet", "card holder"),
    "phone": ("smartphone", "mobile phone"),
    "laptop_tablet": ("laptop", "notebook computer"),
    "earphones": ("earbuds", "wireless earphones"),
    "keys": ("keychain", "bunch of keys"),
    "id_card": ("student ID", "campus card"),
    "clothing": ("hoodie", "sweatshirt"),
    "book": ("textbook", "course book"),
    "accessory": ("sunglasses", "shades"),
    "other": ("umbrella", "folding umbrella"),
}
BRANDS = [
    "HydroFlask",
    "Nike",
    "Dell",
    "Sony",
    "Apple",
    "NorthFace",
    "Moleskine",
    "Anker",
    "Casio",
    "Puma",
]
FEATURES = [
    ("a scratch on the corner", "scratched corner"),
    ("a blue sticker on the back", "sticker on the back"),
    ("a worn lanyard", "frayed lanyard attached"),
    ("engraved initials", "letters engraved on it"),
    ("a yellow zipper pull", "yellow zip tag"),
    ("a cracked edge", "chipped edge"),
]
LOST_TEMPLATES = [
    "Lost my {color} {term}{brand}{feature}.",
    "I left a {color} {term}{brand} somewhere{feature}.",
    "Missing {color} {term}{brand}{feature}, please help.",
]
FOUND_TEMPLATES = [
    "Found a {color} {term}{brand}{feature}.",
    "{Color} {term}{brand} was left behind{feature}.",
    "Picked up a {color} {term}{brand} near the desk{feature}.",
]


@dataclass
class ReportData:
    id: str
    item_id: str
    type: str  # "lost" or "found"
    category: str
    title: str
    description: str
    location: str  # path in the campus tree, e.g. "Library/Floor 2/Room A" or "Library/Floor 2"
    window_start: str  # ISO 8601, UTC
    window_end: str
    has_photo: bool = False

    @property
    def embedding_text(self) -> str:
        """Spec 6.2: the text signal embeds category + title + description."""
        return f"{self.category} {self.title} {self.description}"


@dataclass
class TrueItem:
    item_id: str
    category: str
    lost_report: ReportData
    found_report: ReportData
    split: str = ""  # "dev" or "test" (the leakage guard checks it)


@dataclass
class BenchmarkDataset:
    seed: int
    true_items: list[TrueItem]
    background_reports: list[ReportData]
    dev_items: list[TrueItem]
    test_items: list[TrueItem]
    test_hash: str
    dev_hash: str


def _apply_typos(text: str, rng: random.Random, typo_rate: float = 0.02) -> str:
    """Character-level typos at about 2% of letters (spec 7.1)."""
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch.isalpha() and rng.random() < typo_rate:
            chars[i] = chr(ord(ch) + 1) if ch not in "zZ" else "a"
    return "".join(chars)


def _render(template: str, color: str, term: str, brand: str | None, feature: str | None) -> str:
    text = template.format(
        color=color,
        Color=color[:1].upper() + color[1:],
        term=term,
        brand=f" ({brand})" if brand else "",
        feature=f" with {feature}" if feature else "",
    )
    return text.replace("  ", " ")


def _describe(
    rng: random.Random,
    side: str,
    color: str,
    term: str,
    brand: str,
    feature: str,
) -> tuple[str, str]:
    """Title and description for one side; each side drops at least one attribute."""
    keep = {"color": True, "brand": True, "feature": True}
    droppable = ["color", "brand", "feature"]
    for attr in rng.sample(droppable, k=rng.choice([1, 2])):
        keep[attr] = False
    shown_color = color if keep["color"] else ""
    templates = LOST_TEMPLATES if side == "lost" else FOUND_TEMPLATES
    description = _render(
        rng.choice(templates),
        shown_color or "",
        term,
        brand if keep["brand"] else None,
        feature if keep["feature"] else None,
    )
    description = " ".join(description.split())
    title = " ".join(f"{shown_color} {term}".split())
    return _apply_typos(title, rng), _apply_typos(description, rng)


def _one_level_off(rng: random.Random, leaf: str) -> str:
    """Approximate reporting: the floor instead of the room, or a sibling room."""
    building, floor, room = leaf.split("/")
    if rng.random() < 0.5:
        return f"{building}/{floor}"
    sibling = rng.choice([r for r in ROOMS if r != room])
    return f"{building}/{floor}/{sibling}"


def _lost_window(rng: random.Random, actual: datetime) -> tuple[datetime, datetime]:
    """The owner reports a window containing the true time: exact, a period, or the day."""
    roll = rng.random()
    if roll < 0.4:
        return actual, actual
    if roll < 0.8:
        offset = timedelta(hours=rng.uniform(0, 5))
        start = actual - offset
        return start, start + timedelta(hours=5)
    day_start = actual.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start, day_start + timedelta(hours=24) - timedelta(microseconds=1)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def generate_benchmark_dataset(seed: int = 42) -> BenchmarkDataset:
    """AC-109: deterministic for a seed; 300 true items plus 100 background found reports.

    AC-110: stratified 30% development (90) / 70% test (210) split by category, with content
    hashes of both splits.
    """
    rng = random.Random(seed)
    base_time = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    true_items: list[TrueItem] = []
    per_category = 300 // len(CATEGORIES)

    counter = 0
    for category in CATEGORIES:
        for _ in range(per_category):
            counter += 1
            item_id = f"item_{counter:04d}"
            color_lost, color_found = rng.choice(COLOR_PAIRS)
            term_lost, term_found = ITEM_TERMS[category]
            brand = rng.choice(BRANDS)
            feature_lost, feature_found = rng.choice(FEATURES)

            # Location: 60% exact, 30% one level off, 10% anywhere on campus (spec 7.1)
            true_leaf = rng.choice(LEAF_LOCATIONS)
            roll = rng.random()
            if roll < 0.6:
                found_loc = true_leaf
            elif roll < 0.9:
                found_loc = _one_level_off(rng, true_leaf)
            else:
                found_loc = rng.choice(LEAF_LOCATIONS)

            # Time: log-normal delay with a median of 6 hours (spec 7.1)
            lost_actual = base_time + timedelta(hours=rng.uniform(0, 24 * 60))
            delay = timedelta(hours=rng.lognormvariate(math.log(6), 0.8))
            found_at = lost_actual + delay
            lost_start, lost_end = _lost_window(rng, lost_actual)

            lost_title, lost_desc = _describe(
                rng, "lost", color_lost, term_lost, brand, feature_lost
            )
            found_title, found_desc = _describe(
                rng, "found", color_found, term_found, brand, feature_found
            )
            lost = ReportData(
                id=f"rep_lost_{counter:04d}",
                item_id=item_id,
                type="lost",
                category=category,
                title=lost_title,
                description=lost_desc,
                location=true_leaf,
                window_start=_iso(lost_start),
                window_end=_iso(lost_end),
            )
            found = ReportData(
                id=f"rep_found_{counter:04d}",
                item_id=item_id,
                type="found",
                category=category,
                title=found_title,
                description=found_desc,
                location=found_loc,
                window_start=_iso(found_at),
                window_end=_iso(found_at),
            )
            true_items.append(TrueItem(item_id, category, lost, found))

    # Background: unclaimed found reports written exactly like real found reports.
    background: list[ReportData] = []
    for i in range(1, 101):
        category = rng.choice(CATEGORIES)
        _, term = ITEM_TERMS[category]
        _, color = rng.choice(COLOR_PAIRS)
        _, feature = rng.choice(FEATURES)
        title, desc = _describe(rng, "found", color, term, rng.choice(BRANDS), feature)
        at = base_time + timedelta(hours=rng.uniform(0, 24 * 60))
        background.append(
            ReportData(
                id=f"rep_bg_{i:04d}",
                item_id=f"bg_item_{i:04d}",
                type="found",
                category=category,
                title=title,
                description=desc,
                location=rng.choice(LEAF_LOCATIONS),
                window_start=_iso(at),
                window_end=_iso(at),
            )
        )

    # AC-110: stratified split. 25 items per category -> 8 dev in six categories and 7 in the
    # other six, so the development split is exactly 90 items (30%).
    dev_items: list[TrueItem] = []
    test_items: list[TrueItem] = []
    for idx, category in enumerate(CATEGORIES):
        items = [it for it in true_items if it.category == category]
        rng.shuffle(items)
        n_dev = 8 if idx % 2 == 0 else 7
        for it in items[:n_dev]:
            it.split = "dev"
            dev_items.append(it)
        for it in items[n_dev:]:
            it.split = "test"
            test_items.append(it)

    return BenchmarkDataset(
        seed=seed,
        true_items=true_items,
        background_reports=background,
        dev_items=dev_items,
        test_items=test_items,
        test_hash=content_hash(test_items),
        dev_hash=content_hash(dev_items),
    )


def content_hash(items: list[TrueItem]) -> str:
    payload = json.dumps([asdict(it) for it in items], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
