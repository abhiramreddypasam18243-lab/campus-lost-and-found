import uuid

import pytest

from app.domain.location import LocationNode, calculate_location_score


@pytest.fixture
def sample_campus_tree() -> dict[str, LocationNode]:
    """Build the exact campus tree from spec AC-18.

    Tree:
    Main Campus (campus)
      ├── Library (building)
      │     ├── Floor 1 (floor)
      │     └── Floor 2 (floor)
      │           ├── Reading Room (room)
      │           └── Study Pod (area)
      ├── Student Center (building)
      └── Gym (building)
    North Campus (campus)
      └── Tech Center (building)
    """
    main_campus = LocationNode(id=uuid.uuid4(), name="Main Campus", kind="campus", parent=None)

    library = LocationNode(id=uuid.uuid4(), name="Library", kind="building", parent=main_campus)
    floor_1 = LocationNode(id=uuid.uuid4(), name="Floor 1", kind="floor", parent=library)
    floor_2 = LocationNode(id=uuid.uuid4(), name="Floor 2", kind="floor", parent=library)
    reading_room = LocationNode(id=uuid.uuid4(), name="Reading Room", kind="room", parent=floor_2)
    study_pod = LocationNode(id=uuid.uuid4(), name="Study Pod", kind="area", parent=floor_2)

    student_center = LocationNode(
        id=uuid.uuid4(), name="Student Center", kind="building", parent=main_campus
    )
    gym = LocationNode(id=uuid.uuid4(), name="Gym", kind="building", parent=main_campus)

    north_campus = LocationNode(id=uuid.uuid4(), name="North Campus", kind="campus", parent=None)
    tech_center = LocationNode(
        id=uuid.uuid4(), name="Tech Center", kind="building", parent=north_campus
    )

    return {
        "main_campus": main_campus,
        "library": library,
        "floor_1": floor_1,
        "floor_2": floor_2,
        "reading_room": reading_room,
        "study_pod": study_pod,
        "student_center": student_center,
        "gym": gym,
        "north_campus": north_campus,
        "tech_center": tech_center,
    }


@pytest.fixture
def sample_adjacencies(
    sample_campus_tree: dict[str, LocationNode],
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Library and Student Center are adjacent."""
    lib_id = sample_campus_tree["library"].id
    sc_id = sample_campus_tree["student_center"].id
    return {(lib_id, sc_id)}


def test_ac_18_identical_location(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # Reading Room against Reading Room scores 1.0
    rr = sample_campus_tree["reading_room"]
    assert calculate_location_score(rr, rr, sample_adjacencies) == 1.0


def test_ac_18_ancestor_location(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # Library against Reading Room scores 0.8 (and vice versa)
    lib = sample_campus_tree["library"]
    rr = sample_campus_tree["reading_room"]
    assert calculate_location_score(lib, rr, sample_adjacencies) == 0.8
    assert calculate_location_score(rr, lib, sample_adjacencies) == 0.8


def test_ac_18_share_floor_or_area(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # Reading Room against Study Pod scores 0.7 (LCA is Floor 2)
    rr = sample_campus_tree["reading_room"]
    sp = sample_campus_tree["study_pod"]
    assert calculate_location_score(rr, sp, sample_adjacencies) == 0.7
    assert calculate_location_score(sp, rr, sample_adjacencies) == 0.7


def test_ac_18_share_building_only(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # Reading Room against Floor 1 scores 0.6 (LCA is Library)
    rr = sample_campus_tree["reading_room"]
    f1 = sample_campus_tree["floor_1"]
    assert calculate_location_score(rr, f1, sample_adjacencies) == 0.6
    assert calculate_location_score(f1, rr, sample_adjacencies) == 0.6


def test_ac_18_adjacent_buildings(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # Library against Student Center scores 0.5 (different buildings that are adjacent)
    lib = sample_campus_tree["library"]
    sc = sample_campus_tree["student_center"]
    assert calculate_location_score(lib, sc, sample_adjacencies) == 0.5
    assert calculate_location_score(sc, lib, sample_adjacencies) == 0.5


def test_ac_18_same_campus_not_adjacent(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # Library against Gym scores 0.2 (same campus, not adjacent)
    lib = sample_campus_tree["library"]
    gym = sample_campus_tree["gym"]
    assert calculate_location_score(lib, gym, sample_adjacencies) == 0.2
    assert calculate_location_score(gym, lib, sample_adjacencies) == 0.2


def test_ac_18_different_campus(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # A location in another campus scores 0.0
    lib = sample_campus_tree["library"]
    tech = sample_campus_tree["tech_center"]
    assert calculate_location_score(lib, tech, sample_adjacencies) == 0.0
    assert calculate_location_score(tech, lib, sample_adjacencies) == 0.0


def test_ac_18_missing_location(
    sample_campus_tree: dict[str, LocationNode],
    sample_adjacencies: set[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    # A missing location gives null (None)
    lib = sample_campus_tree["library"]
    assert calculate_location_score(lib, None, sample_adjacencies) is None
    assert calculate_location_score(None, lib, sample_adjacencies) is None
    assert calculate_location_score(None, None, sample_adjacencies) is None
