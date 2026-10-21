"""Retrieval latency in PostgreSQL + pgvector (spec 7.3; AC-120).

Random unit vectors (synthetic, no user data) are loaded into a scratch schema at each size.
For each query we time a top-10 cosine search twice: exact (index scans disabled, so a full
scan) and approximate (the HNSW index, as the service uses). We also report HNSW recall@10
against the exact result. The scratch schema is dropped afterwards.
"""

from __future__ import annotations

import os
import statistics
import time
from typing import Any

import numpy as np

SCHEMA = "latency_bench"


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _unit(rng: np.random.Generator, n: int, dim: int) -> np.ndarray:
    v = rng.standard_normal((n, dim)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def measure_latency(
    sizes: tuple[int, ...] = (1_000, 10_000, 100_000),
    dimension: int = 384,
    queries: int = 50,
    seed: int = 7,
    dsn: str | None = None,
) -> dict[str, Any]:
    dsn = dsn or os.environ.get("SYNC_DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")
    if not dsn:
        return {"status": "not_measured", "reason": "No database configured (SYNC_DATABASE_URL)."}

    import psycopg
    from pgvector.psycopg import register_vector

    rng = np.random.default_rng(seed)
    results: dict[str, Any] = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        conn.execute(f"CREATE SCHEMA {SCHEMA}")
        try:
            for n in sizes:
                table = f"{SCHEMA}.v{n}"
                conn.execute(f"CREATE UNLOGGED TABLE {table} (id int PRIMARY KEY, v vector({dimension}))")
                data = _unit(rng, n, dimension)
                with conn.cursor().copy(f"COPY {table} (id, v) FROM STDIN WITH (FORMAT BINARY)") as copy:
                    copy.set_types(["int4", "vector"])
                    for i in range(n):
                        copy.write_row([i, data[i]])
                t0 = time.perf_counter()
                conn.execute(f"CREATE INDEX ON {table} USING hnsw (v vector_cosine_ops)")
                build_s = time.perf_counter() - t0
                conn.execute(f"ANALYZE {table}")

                qs = _unit(rng, queries, dimension)
                sql = f"SELECT id FROM {table} ORDER BY v <=> %s LIMIT 10"
                exact_ms: list[float] = []
                hnsw_ms: list[float] = []
                recalls: list[float] = []
                for q in qs:
                    # Force each plan: a full scan for exact, the HNSW index for approximate.
                    conn.execute("SET enable_indexscan = off; SET enable_seqscan = on")
                    t = time.perf_counter()
                    exact = [r[0] for r in conn.execute(sql, (q,)).fetchall()]
                    exact_ms.append((time.perf_counter() - t) * 1000)
                    conn.execute("SET enable_indexscan = on; SET enable_seqscan = off")
                    t = time.perf_counter()
                    approx = [r[0] for r in conn.execute(sql, (q,)).fetchall()]
                    hnsw_ms.append((time.perf_counter() - t) * 1000)
                    recalls.append(len(set(exact) & set(approx)) / 10)
                conn.execute("RESET enable_indexscan; RESET enable_seqscan")
                results[str(n)] = {
                    "exact_ms": {"p50": round(_percentile(exact_ms, 0.5), 3), "p95": round(_percentile(exact_ms, 0.95), 3)},
                    "hnsw_ms": {"p50": round(_percentile(hnsw_ms, 0.5), 3), "p95": round(_percentile(hnsw_ms, 0.95), 3)},
                    "hnsw_recall_at_10": round(statistics.mean(recalls), 4),
                    "index_build_seconds": round(build_s, 2),
                    "queries": queries,
                }
        finally:
            conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    return {
        "status": "measured",
        "dimension": dimension,
        "method": "client-side wall time per top-10 query over one local connection; exact = index scans disabled",
        "sizes": results,
    }
