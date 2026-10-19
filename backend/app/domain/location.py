import uuid
from dataclasses import dataclass
from typing import Literal

LocationKind = Literal["campus", "building", "floor", "room", "area"]


@dataclass(frozen=True)
class LocationNode:
    id: uuid.UUID
    name: str
    kind: LocationKind
    parent: "LocationNode | None" = None


def _get_ancestor_chain(node: LocationNode) -> list[LocationNode]:
    """Return the chain of nodes from the current node up to the root."""
    chain: list[LocationNode] = []
    curr: LocationNode | None = node
    while curr is not None:
        chain.append(curr)
        curr = curr.parent
    return chain


def calculate_location_score(
    loc_a: LocationNode | None,
    loc_b: LocationNode | None,
    adjacency_set: set[tuple[uuid.UUID, uuid.UUID]] | None = None,
) -> float | None:
    """[LEARN] Pure domain location scoring function per Spec 6.3 and AC-18.

    Scores the relationship between two locations in a campus tree:
    - 1.0: Identical location
    - 0.8: One is an ancestor of the other
    - 0.7: Share a floor or an area (LCA is floor or area)
    - 0.6: Share a building only (LCA is building)
    - 0.5: Different buildings that are adjacent
    - 0.2: Same campus, not adjacent
    - 0.0: Different campuses
    - None (null): Either location is missing
    """
    if loc_a is None or loc_b is None:
        return None

    # 1. Identical location
    if loc_a.id == loc_b.id:
        return 1.0

    chain_a = _get_ancestor_chain(loc_a)
    chain_b = _get_ancestor_chain(loc_b)

    # 2. One is an ancestor of the other
    ancestor_ids_a = {node.id for node in chain_a[1:]}
    ancestor_ids_b = {node.id for node in chain_b[1:]}

    if loc_a.id in ancestor_ids_b or loc_b.id in ancestor_ids_a:
        return 0.8

    # 3. Find Lowest Common Ancestor (LCA)
    ids_b = {node.id for node in chain_b}
    lca: LocationNode | None = None
    for node in chain_a:
        if node.id in ids_b:
            lca = node
            break

    # If roots differ (no common ancestor or different campus roots)
    if lca is None:
        return 0.0

    # Share a floor or an area (LCA is floor or area)
    if lca.kind in ("floor", "area", "room"):
        return 0.7

    # Share a building only (LCA is building)
    if lca.kind == "building":
        return 0.6

    # LCA is campus: check building adjacency
    if lca.kind == "campus":
        # Find building ancestor for loc_a and loc_b
        bldg_a = next((node for node in chain_a if node.kind == "building"), None)
        bldg_b = next((node for node in chain_b if node.kind == "building"), None)

        if bldg_a is not None and bldg_b is not None and bldg_a.id != bldg_b.id:
            adj = adjacency_set or set()
            is_adjacent = (bldg_a.id, bldg_b.id) in adj or (bldg_b.id, bldg_a.id) in adj
            if is_adjacent:
                return 0.5

        return 0.2

    return 0.0
