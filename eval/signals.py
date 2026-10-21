"""Signal matrices for the benchmark, computed with the application's own domain functions.

Location uses `app.domain.location.calculate_location_score` on a campus tree with adjacency,
time uses `app.domain.matching.calculate_time_score`, and text is max(0, cosine) of embeddings
of category + title + description (spec 6.2). So the benchmark measures the scoring code the
service actually runs, not a re-implementation of it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from app.domain.location import LocationNode, calculate_location_score
from app.domain.matching import calculate_text_score, calculate_time_score
from eval.generator import ADJACENT_BUILDINGS, BUILDINGS, CAMPUS, FLOORS, ROOMS, ReportData

# Embeds a batch of texts into L2-normalised vectors.
TextEmbedder = Callable[[Sequence[str]], np.ndarray]

_NS = uuid.UUID("6f1c3b2e-9d7a-4c55-9a51-0e3c2b1d4f60")


def _node_id(path: str) -> uuid.UUID:
    return uuid.uuid5(_NS, path)


def build_campus_tree() -> tuple[dict[str, LocationNode], set[tuple[uuid.UUID, uuid.UUID]]]:
    """Every location path (campus, building, floor, room) mapped to a LocationNode."""
    nodes: dict[str, LocationNode] = {}
    campus = LocationNode(id=_node_id(CAMPUS), name=CAMPUS, kind="campus")
    nodes[CAMPUS] = campus
    for b in BUILDINGS:
        bn = LocationNode(id=_node_id(b), name=b, kind="building", parent=campus)
        nodes[b] = bn
        for f in FLOORS:
            fn = LocationNode(id=_node_id(f"{b}/{f}"), name=f, kind="floor", parent=bn)
            nodes[f"{b}/{f}"] = fn
            for r in ROOMS:
                nodes[f"{b}/{f}/{r}"] = LocationNode(
                    id=_node_id(f"{b}/{f}/{r}"), name=r, kind="room", parent=fn
                )
    adjacency: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for a, b in ADJACENT_BUILDINGS:
        adjacency.add((_node_id(a), _node_id(b)))
        adjacency.add((_node_id(b), _node_id(a)))
    return nodes, adjacency


@dataclass
class SignalMatrices:
    """Per (query, candidate) signals in [0, 1]; rows follow `queries`, columns `pool`."""

    queries: list[ReportData]
    pool: list[ReportData]
    text: np.ndarray
    location: np.ndarray
    time: np.ndarray

    def by_name(self) -> dict[str, np.ndarray]:
        return {"text": self.text, "location": self.location, "time": self.time}


def location_matrix(queries: list[ReportData], pool: list[ReportData]) -> np.ndarray:
    nodes, adjacency = build_campus_tree()
    cache: dict[tuple[str, str], float] = {}
    out = np.zeros((len(queries), len(pool)))
    for i, q in enumerate(queries):
        for j, c in enumerate(pool):
            key = (q.location, c.location)
            if key not in cache:
                score = calculate_location_score(nodes[q.location], nodes[c.location], adjacency)
                cache[key] = 0.0 if score is None else score
            out[i, j] = cache[key]
    return out


def time_matrix(queries: list[ReportData], pool: list[ReportData]) -> np.ndarray:
    def parse(s: str) -> datetime:
        return datetime.fromisoformat(s)

    out = np.zeros((len(queries), len(pool)))
    for i, q in enumerate(queries):
        ls, le = parse(q.window_start), parse(q.window_end)
        for j, c in enumerate(pool):
            out[i, j] = calculate_time_score(ls, le, parse(c.window_start), parse(c.window_end))
    return out


def text_matrix(
    queries: list[ReportData], pool: list[ReportData], embed: TextEmbedder
) -> np.ndarray:
    q = embed([r.embedding_text for r in queries])
    c = embed([r.embedding_text for r in pool])
    cos = q @ c.T
    scores: np.ndarray = np.vectorize(calculate_text_score)(cos).astype(float)
    return scores


def compute_signals(
    queries: list[ReportData], pool: list[ReportData], embed: TextEmbedder
) -> SignalMatrices:
    return SignalMatrices(
        queries=queries,
        pool=pool,
        text=text_matrix(queries, pool, embed),
        location=location_matrix(queries, pool),
        time=time_matrix(queries, pool),
    )


def model_text_embedder(model_dir: str, model_name: str) -> TextEmbedder:
    """The pinned sentence-embedding model baked into the backend image (spec 6.1)."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(f"{model_dir}/{model_name}", device="cpu")

    def embed(texts: Sequence[str]) -> np.ndarray:
        vecs = model.encode(list(texts), normalize_embeddings=True, batch_size=64)
        return np.asarray(vecs, dtype=float)

    return embed


def standin_text_embedder(dimension: int = 384) -> TextEmbedder:
    """Deterministic hash vectors for fast tests. Carries no meaning; never used for results."""
    from app.services.embeddings import generate_standin_text_embedding

    def embed(texts: Sequence[str]) -> np.ndarray:
        return np.asarray(
            [generate_standin_text_embedding(t, dimension=dimension) for t in texts], dtype=float
        )

    return embed
