"""Tests for AC-109 to AC-123: Retrieval Evaluation Framework (spec section 7)."""

import json
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from eval.bm25 import BM25Index
from eval.generator import generate_benchmark_dataset
from eval.metrics import (
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from eval.protocol import DataLeakageError, TuningHarness, load_frozen_config, weight_grid
from eval.runner import evaluate_test, make_embedder, pools, run_full_evaluation
from eval.signals import compute_signals, standin_text_embedder
from eval.stats import bootstrap_ci, paired_bootstrap_ci
from eval.systems import hybrid_matrix, ranks_from_scores
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import admin as admin_api
from app.core.security import hash_token
from app.domain.matching import calculate_hybrid_score
from app.models.user import Session, User


async def create_user_and_cookie(
    db_session: AsyncSession,
    email: str,
    role: str = "user",
) -> tuple[User, dict[str, str], str]:
    now = datetime.now(UTC)
    user = User(
        email=email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        role=role,
        status="active",
        email_verified_at=now,
    )
    db_session.add(user)
    await db_session.flush()

    raw_sid = f"sess_{uuid.uuid4()}"
    raw_csrf = f"csrf_{uuid.uuid4()}"
    sess = Session(
        user_id=user.id,
        token_hash=hash_token(raw_sid),
        csrf_token_hash=hash_token(raw_csrf),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db_session.add(sess)
    await db_session.commit()

    return user, {"session_id": raw_sid}, raw_csrf


def test_ac_109_benchmark_generator_deterministic() -> None:
    """AC-109: Deterministic generator produces 300 true items (lost + found reports)

    plus 100 background found reports.
    """
    ds1 = generate_benchmark_dataset(seed=42)
    ds2 = generate_benchmark_dataset(seed=42)

    assert len(ds1.true_items) == 300
    assert len(ds1.background_reports) == 100

    # Verify each true item has a lost and found report
    for item in ds1.true_items:
        assert item.lost_report.type == "lost"
        assert item.found_report.type == "found"
        assert item.lost_report.item_id == item.found_report.item_id

    # Determinism: same seed produces identical dataset hashes and item IDs
    assert ds1.test_hash == ds2.test_hash
    assert ds1.true_items[0].lost_report.title == ds2.true_items[0].lost_report.title


def test_ac_110_stratified_split_and_content_hash() -> None:
    """AC-110: 30% development (90 items) / 70% test (210 items), stratified by category,

    no overlap, content hash recorded.
    """
    ds = generate_benchmark_dataset(seed=42)

    assert len(ds.dev_items) == 90
    assert len(ds.test_items) == 210

    dev_ids = {it.item_id for it in ds.dev_items}
    test_ids = {it.item_id for it in ds.test_items}
    assert dev_ids.isdisjoint(test_ids)

    # Stratified: all 12 categories represented in both splits
    dev_cats = {it.category for it in ds.dev_items}
    test_cats = {it.category for it in ds.test_items}
    assert len(dev_cats) == 12
    assert len(test_cats) == 12

    assert len(ds.test_hash) == 64  # SHA-256


def test_ac_111_data_leakage_guard() -> None:
    """AC-111: Tuning code cannot access test-set labels; raises DataLeakageError."""
    ds = generate_benchmark_dataset(seed=42)

    # Pointing tuning harness at test split must raise DataLeakageError
    with pytest.raises(DataLeakageError):
        TuningHarness(
            split="test",
            dev_items=ds.test_items,
            candidate_pool=[],
        )

    # Test items smuggled in under the "dev" name are refused too, item by item.
    with pytest.raises(DataLeakageError):
        TuningHarness(split="dev", dev_items=ds.dev_items + ds.test_items[:1], candidate_pool=[])

    # Every item carries its split label, and the splits do not overlap.
    assert {it.split for it in ds.dev_items} == {"dev"}
    assert {it.split for it in ds.test_items} == {"test"}


def test_ac_112_metric_fixture() -> None:
    """AC-112: Metric fixture with first-correct ranks [1, 3, 2, 10]:

    Recall@1 = 0.25, Recall@3 = 0.75, Recall@5 = 0.75,
    MRR = 0.4833, nDCG@10 = 0.605 (+-0.001), Precision@5 = 0.15.
    """
    ranks = [1, 3, 2, 10]

    assert recall_at_k(ranks, 1) == 0.25
    assert recall_at_k(ranks, 3) == 0.75
    assert recall_at_k(ranks, 5) == 0.75
    assert mrr(ranks) == 0.4833
    assert abs(ndcg_at_k(ranks, 10) - 0.605) <= 0.001
    assert precision_at_k(ranks, 5) == 0.15


def test_ac_113_bm25_toy_corpus() -> None:
    """AC-113: Toy corpus ("blue water bottle", "red backpack", "blue backpack")

    with BM25 query "blue bottle" ranks first document first.
    """
    corpus = ["blue water bottle", "red backpack", "blue backpack"]
    index = BM25Index(corpus)
    ranked = index.rank("blue bottle")

    # Document 0 must be rank 1 with highest score
    assert ranked[0][0] == 0
    assert ranked[0][1] > ranked[1][1]


def test_ac_114_bootstrap_confidence_interval() -> None:
    """AC-114: Bootstrap CI for MRR is deterministic; for all ranks=1 it is [1.0, 1.0];

    and covers true value in >=90 out of 100 simulations.
    """
    # 1. Determinism
    ci1 = bootstrap_ci([1, 2, 3, 4], mrr, n_resamples=200, seed=123)
    ci2 = bootstrap_ci([1, 2, 3, 4], mrr, n_resamples=200, seed=123)
    assert ci1 == ci2

    # 2. For all ranks = 1, interval is exactly [1.0, 1.0]
    ci_perfect = bootstrap_ci([1, 1, 1, 1], mrr, n_resamples=200, seed=123)
    assert ci_perfect == (1.0, 1.0)

    # 3. 100 simulations coverage test on known population mean
    true_mean = 0.50
    covered_count = 0
    rng = random.Random(42)

    for sim in range(100):
        # Draw sample of size 30 with known mean 0.50
        sample = [1 if rng.random() < 0.50 else 0 for _ in range(30)]

        def mean_fn(s: list[int]) -> float:
            return sum(s) / len(s) if s else 0.0

        low, high = bootstrap_ci(sample, mean_fn, n_resamples=200, ci=0.95, seed=sim)
        if low <= true_mean <= high:
            covered_count += 1

    assert covered_count >= 90


def test_ac_115_paired_bootstrap() -> None:
    """AC-115: Paired bootstrap for ranks A = [1,1,1,1] and B = [2,2,2,2]

    gives difference in MRR of 0.5 with interval excluding 0.
    """
    ranks_a = [1, 1, 1, 1]  # MRR = 1.0
    ranks_b = [2, 2, 2, 2]  # MRR = 0.5

    mean_diff, low, high = paired_bootstrap_ci(ranks_a, ranks_b, mrr, n_resamples=200, seed=42)

    assert mean_diff == 0.5
    assert low == 0.5
    assert high == 0.5
    assert low > 0.0


def test_ac_117_hybrid_matrix_matches_domain_function() -> None:
    """The vectorised hybrid used by the benchmark equals app.domain calculate_hybrid_score,
    including renormalisation when a signal is missing (AC-53, AC-54)."""
    rng = np.random.default_rng(3)
    signals = {k: rng.random((6, 7)) for k in ("text", "location", "time")}
    signals["location"][0, 0] = np.nan  # a missing signal
    weights = {"text": 0.55, "location": 0.3, "time": 0.15}
    vec = hybrid_matrix(signals, weights)
    for i in range(6):
        for j in range(7):
            pair = {k: (None if np.isnan(v[i, j]) else float(v[i, j])) for k, v in signals.items()}
            expected, _, _ = calculate_hybrid_score(pair, weights)
            assert vec[i, j] == pytest.approx(expected, abs=1e-12)


def test_ac_117_grid_search_selects_best_dev_mrr() -> None:
    """Weights are chosen by development MRR over the whole 0.05 grid, on dev data only."""
    ds = generate_benchmark_dataset(seed=42)
    dev_pool, _ = pools(ds)
    embed = standin_text_embedder()
    harness = TuningHarness("dev", ds.dev_items, dev_pool, embed=embed)
    tuned = harness.tune_weights_grid(step=0.05)

    grid = weight_grid(0.05)
    assert tuned["grid_points"] == len(grid) == 231
    sig = compute_signals([it.lost_report for it in ds.dev_items], dev_pool, embed).by_name()
    best = max(mrr(ranks_from_scores(ds.dev_items, dev_pool, hybrid_matrix(sig, w))) for w in grid)
    assert tuned["dev_mrr"] == best
    assert abs(sum(tuned["weights"].values()) - 1.0) < 1e-9


def test_ac_116_to_121_evaluation_runner(tmp_path: Path) -> None:
    """AC-116 to AC-121 with stand-in embeddings: systems, ablations, noise sweeps, H1, frozen
    configuration, honest reporting of what is not evaluated, and reproducibility.

    Changed on 2026-10-21: the previous version asserted an image system and a 60-item real-photo
    subset; neither exists (the benchmark has no photos), so the runner now reports them as not
    evaluated and this test checks that it says so.
    """
    report = run_full_evaluation(seed=42, output_dir=tmp_path, backend="standin")

    # AC-116: systems evaluated, with confidence intervals
    assert set(report["systems"]) == {"A", "B", "D", "E"}
    for result in report["systems"].values():
        low, high = result["mrr_ci"]
        assert low <= result["metrics"]["mrr"] <= high
        assert result["n_queries"] == 210
    assert any(n["system"].startswith("C: image") for n in report["not_evaluated"])
    assert report["real_photo_subset"] == {
        "status": "not_collected",
        "sample_count": 0,
        "reason": report["real_photo_subset"]["reason"],
    }

    # AC-117 / AC-118: frozen, hashed configuration; JSON and CSV saved
    frozen = load_frozen_config(tmp_path / "frozen_config.json")
    assert frozen["config_hash"] == report["config_hash"]
    assert frozen["test_hash"] == report["dataset_hash"]
    assert (tmp_path / "benchmark_results.json").exists()
    assert (tmp_path / "benchmark_results.csv").exists()
    tampered = json.loads((tmp_path / "frozen_config.json").read_text())
    tampered["weights"]["text"] = 0.99
    (tmp_path / "tampered.json").write_text(json.dumps(tampered))
    with pytest.raises(ValueError):
        load_frozen_config(tmp_path / "tampered.json")

    # AC-119: ablations and robustness sweeps with confidence intervals
    abl = report["ablations"]
    assert set(abl["signal_removal"]) == {"drop_text", "drop_location", "drop_time"}
    assert set(abl["location_noise"]) == {"0%", "25%", "50%"}
    assert set(abl["time_noise"]) == {"0%", "25%", "50%"}
    assert abl["missing_photos"]["status"] == "not_evaluated"
    # With no noise, the noisy-pool path reproduces the plain hybrid exactly.
    assert abl["location_noise"]["0%"]["metrics"] == report["systems"]["D"]["metrics"]

    # AC-121: pre-registered H1 with an outcome either way, and stated limits
    h1 = report["hypothesis_h1"]
    assert h1["statement"].startswith("H1:")
    assert h1["is_supported"] == (h1["difference_95_ci"][0] > 0)
    assert len(report["limitations"]) >= 3

    # AC-118: re-running from the same frozen configuration reproduces identical numbers
    ds = generate_benchmark_dataset(seed=42)
    again = evaluate_test(ds, make_embedder("standin"), frozen, latency_sizes=())
    for key in ("systems", "hypothesis_h1", "ablations"):
        assert again[key] == report[key]


def test_ac_122_dataset_card_exists() -> None:
    """AC-122: DATA_CARD.md exists and documents privacy, no faces/PII, EXIF removal, and consent."""
    candidate_paths = [
        Path("/app/eval/DATA_CARD.md"),
        Path("eval/DATA_CARD.md"),
        Path(__file__).resolve().parent.parent.parent / "eval" / "DATA_CARD.md",
    ]
    card_path = next((p for p in candidate_paths if p.exists()), None)
    assert card_path is not None, "DATA_CARD.md not found"
    content = card_path.read_text(encoding="utf-8").lower()
    assert "faces" in content
    assert "exif" in content
    assert "consent" in content
    assert "300" in content


@pytest.mark.asyncio
async def test_ac_123_admin_evaluation_endpoint(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC-123: Admin evaluation page shows latest saved results and never evaluates on live private data."""
    # 1. Unauthenticated request -> 401 or 404
    resp_anon = await async_client.get("/api/admin/evaluation")
    assert resp_anon.status_code in (401, 404)

    # 2. Regular user request -> 404 anti-enumeration
    _, user_cookies, _ = await create_user_and_cookie(
        db_session, f"student_{uuid.uuid4().hex[:6]}@campus.edu", role="user"
    )
    resp_user = await async_client.get("/api/admin/evaluation", cookies=user_cookies)
    assert resp_user.status_code == 404

    # 3. Admin user request -> 200 OK
    _, admin_cookies, _ = await create_user_and_cookie(
        db_session, f"admin_{uuid.uuid4().hex[:6]}@campus.edu", role="admin"
    )
    # No saved results: the endpoint says so and never runs an evaluation itself.
    monkeypatch.setattr(admin_api, "_results_path", lambda: None)
    resp_none = await async_client.get("/api/admin/evaluation", cookies=admin_cookies)
    assert resp_none.status_code == 404
    assert "no_results" in resp_none.text

    run_full_evaluation(seed=42, output_dir=tmp_path, backend="standin")
    monkeypatch.setattr(admin_api, "_results_path", lambda: tmp_path / "benchmark_results.json")
    resp_admin = await async_client.get("/api/admin/evaluation", cookies=admin_cookies)
    assert resp_admin.status_code == 200, resp_admin.text
    data = resp_admin.json()

    assert "models" in data
    assert "weights" in data
    assert "systems" in data
    assert "hypothesis_h1" in data
    assert "latency_benchmark" in data
