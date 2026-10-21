"""Benchmark runner (spec 7; AC-116 to AC-121).

Two stages, run inside the backend image so the pinned models are available offline:

    python -m eval.runner tune      # development split only -> eval/results/frozen_config.json
    python -m eval.runner final     # test split, once, from the frozen config -> results JSON/CSV
    python -m eval.runner final --reproduce   # re-run and check the saved numbers are identical

`final` refuses to overwrite results already produced from the same frozen configuration, and
verifies that neither the configuration nor the dataset changed since tuning.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from eval.generator import BenchmarkDataset, ReportData, TrueItem, generate_benchmark_dataset
from eval.latency import measure_latency
from eval.metrics import compute_retrieval_metrics, mrr
from eval.protocol import TuningHarness, load_frozen_config
from eval.signals import (
    TextEmbedder,
    compute_signals,
    location_matrix,
    model_text_embedder,
    standin_text_embedder,
    time_matrix,
)
from eval.stats import bootstrap_ci, paired_bootstrap_ci
from eval.systems import LogisticModel, all_system_scores, hybrid_matrix, ranks_from_scores

RESULTS_DIR = Path(__file__).resolve().parent / "results"
BOOTSTRAP_RESAMPLES = 1000

SYSTEM_INFO = {
    "A": ("A: BM25 keyword", "BM25 over title and description"),
    "B": ("B: text embedding", "max(0, cosine) of all-MiniLM-L6-v2 embeddings of category + title + description"),
    "D": ("D: hand-weighted hybrid", "Spec 6.4 hybrid of text, location and time with dev-tuned weights"),
    "E": ("E: learned fusion", "Logistic regression over text, location and time, trained on dev pairs"),
}

NOT_EVALUATED = [
    {
        "system": "C: image similarity",
        "reason": "The benchmark contains no photos. The spec's real-photo subset (60+ items photographed twice by different people) has not been collected, so no image result is reported.",
    },
    {
        "system": "Real-photo subset (AC-121)",
        "reason": "Not collected. No photo, consent record or licence exists for it.",
    },
    {
        "system": "Human-written text subset (spec 7.1)",
        "reason": "Not collected. All benchmark text comes from the seeded templates.",
    },
]

LIMITATIONS = [
    "All text is template-generated; lost and found sides use different lexicons and 2% typos, but real reports are more varied.",
    "Location and time are generated with the same assumptions the scoring functions encode (60/30/10 location noise, a log-normal delay with a 6-hour median), so part of any hybrid advantage is by construction.",
    "No photos: the image signal, which carries the largest initial weight in production, is not evaluated.",
    "These are retrieval metrics on a synthetic benchmark; they say nothing about real-world recovery rates, which only a pilot could show.",
    "Latency uses random vectors on one machine with one connection; it excludes embedding time.",
]


def pools(dataset: BenchmarkDataset) -> tuple[list[ReportData], list[ReportData]]:
    """Each split's candidate pool: its own true found reports plus the background reports."""
    dev_pool = [it.found_report for it in dataset.dev_items] + dataset.background_reports
    test_pool = [it.found_report for it in dataset.test_items] + dataset.background_reports
    return dev_pool, test_pool


def git_commit() -> str:
    env = os.environ.get("EVAL_GIT_COMMIT")
    if env:
        return env
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def hardware() -> dict[str, Any]:
    return {
        "machine": platform.machine(),
        "system": platform.system(),
        "release": platform.release(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "numpy": np.__version__,
    }


def model_identity(backend: str) -> dict[str, Any]:
    if backend == "standin":
        return {"text_embedding": "standin-hash-vectors", "image_embedding": None, "backend": "standin"}
    from app.core.config import get_settings

    s = get_settings()
    return {
        "text_embedding": f"{s.TEXT_MODEL_NAME}@{s.TEXT_MODEL_VERSION}",
        "image_embedding": None,
        "backend": "model",
    }


def make_embedder(backend: str) -> TextEmbedder:
    if backend == "standin":
        return standin_text_embedder()
    from app.core.config import get_settings

    s = get_settings()
    return model_text_embedder(s.MODEL_DIR, s.TEXT_MODEL_NAME)


# ---------------------------------------------------------------- tuning (dev only)


def tune(dataset: BenchmarkDataset, embed: TextEmbedder, backend: str, out_dir: Path) -> dict[str, Any]:
    dev_pool, _ = pools(dataset)
    harness = TuningHarness("dev", dataset.dev_items, dev_pool, embed=embed)
    tuning = harness.tune_weights_grid(step=0.05)
    fusion = harness.train_learned_fusion()
    frozen, _ = TuningHarness.freeze_and_hash_config(
        tuning, fusion, dataset, model_identity(backend), out_dir / "frozen_config.json"
    )
    return frozen


# ---------------------------------------------------------------- final (test, once)


def _system_result(key: str, ranks: list[int], seed: int) -> dict[str, Any]:
    name, description = SYSTEM_INFO[key]
    return {
        "name": name,
        "description": description,
        "metrics": compute_retrieval_metrics(ranks),
        "mrr_ci": list(bootstrap_ci(ranks, mrr, n_resamples=BOOTSTRAP_RESAMPLES, seed=seed)),
        "n_queries": len(ranks),
    }


def _metric_block(ranks: list[int], seed: int) -> dict[str, Any]:
    return {
        "metrics": compute_retrieval_metrics(ranks),
        "mrr_ci": list(bootstrap_ci(ranks, mrr, n_resamples=BOOTSTRAP_RESAMPLES, seed=seed)),
    }


def _parent_location(path: str) -> str:
    parts = path.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else path


def _noisy_pool(
    items: list[TrueItem], pool: list[ReportData], fraction: float, kind: str, seed: int
) -> list[ReportData]:
    """Perturb `fraction` of the true found reports: one level up, or 24 hours later."""
    rng = random.Random(seed)
    target_ids = {it.found_report.id for it in items}
    chosen = set(rng.sample(sorted(target_ids), k=round(len(target_ids) * fraction)))
    out: list[ReportData] = []
    for r in pool:
        if r.id not in chosen:
            out.append(r)
            continue
        if kind == "location":
            out.append(ReportData(**{**r.__dict__, "location": _parent_location(r.location)}))
        else:
            shift = timedelta(hours=24)
            start = datetime.fromisoformat(r.window_start) + shift
            end = datetime.fromisoformat(r.window_end) + shift
            out.append(ReportData(**{**r.__dict__, "window_start": start.isoformat(), "window_end": end.isoformat()}))
    return out


def evaluate_test(
    dataset: BenchmarkDataset,
    embed: TextEmbedder,
    frozen: dict[str, Any],
    latency_sizes: tuple[int, ...],
) -> dict[str, Any]:
    seed = dataset.seed
    _, test_pool = pools(dataset)
    items = dataset.test_items
    weights = frozen["weights"]
    model = LogisticModel.from_dict(frozen["learned_fusion"])

    sig = compute_signals([it.lost_report for it in items], test_pool, embed)
    scores = all_system_scores(items, sig, weights, model)
    ranks = {k: ranks_from_scores(items, test_pool, s) for k, s in scores.items()}
    systems = {k: _system_result(k, ranks[k], seed) for k in ("A", "B", "D", "E")}

    # H1 (pre-registered in eval/HYPOTHESES.md): D vs the better of the single-signal baselines.
    base_key = "B" if systems["B"]["metrics"]["mrr"] >= systems["A"]["metrics"]["mrr"] else "A"
    diff, lo, hi = paired_bootstrap_ci(ranks["D"], ranks[base_key], mrr, n_resamples=BOOTSTRAP_RESAMPLES, seed=seed)
    supported = lo > 0
    hypothesis = {
        "statement": "H1: The hand-weighted hybrid (D) has a higher MRR than the best single-signal baseline.",
        "registered_in": "eval/HYPOTHESES.md (committed before the test run)",
        "best_baseline": SYSTEM_INFO[base_key][0],
        "hybrid_system": SYSTEM_INFO["D"][0],
        "mean_mrr_difference": diff,
        "difference_95_ci": [lo, hi],
        "is_supported": supported,
        "outcome": (
            f"Supported: the 95% interval of the MRR difference [{lo}, {hi}] excludes 0."
            if supported
            else f"Not supported: the 95% interval of the MRR difference [{lo}, {hi}] does not lie above 0."
        ),
    }
    e_diff, e_lo, e_hi = paired_bootstrap_ci(ranks["E"], ranks[base_key], mrr, n_resamples=BOOTSTRAP_RESAMPLES, seed=seed)
    exploratory = {
        "note": "Exploratory, not pre-registered.",
        "learned_fusion_vs_best_baseline": {"mean_mrr_difference": e_diff, "difference_95_ci": [e_lo, e_hi]},
    }

    # Ablations: remove one signal from the hybrid (spec 7.6)
    signals = sig.by_name()
    signal_removal: dict[str, Any] = {}
    for name in ("text", "location", "time"):
        w = {**weights, name: 0.0}
        if sum(w.values()) == 0:
            w = {k: (1.0 if k != name else 0.0) for k in weights}
        r = ranks_from_scores(items, test_pool, hybrid_matrix(signals, w))
        signal_removal[f"drop_{name}"] = _metric_block(r, seed)

    # Robustness: noise on 0, 25, 50% of the true found reports (spec 7.6)
    def noisy(kind: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for pct in (0, 25, 50):
            noisy_pool = _noisy_pool(items, test_pool, pct / 100, kind, seed + pct)
            queries = [it.lost_report for it in items]
            s = dict(signals)
            if kind == "location":
                s["location"] = location_matrix(queries, noisy_pool)
            else:
                s["time"] = time_matrix(queries, noisy_pool)
            r = ranks_from_scores(items, noisy_pool, hybrid_matrix(s, weights))
            out[f"{pct}%"] = _metric_block(r, seed)
        return out

    ablations = {
        "signal_removal": signal_removal,
        "location_noise": noisy("location"),
        "time_noise": noisy("time"),
        "missing_photos": {"status": "not_evaluated", "reason": "No photos in the benchmark, so there is nothing to remove."},
    }

    latency = (
        measure_latency(latency_sizes)
        if latency_sizes
        else {"status": "not_measured", "reason": "Latency measurement was not requested for this run."}
    )

    return {
        "status": "complete",
        "timestamp": datetime.now(UTC).isoformat(),
        "seed": seed,
        "dataset_hash": dataset.test_hash,
        "dev_hash": dataset.dev_hash,
        "config_hash": frozen["config_hash"],
        "git_commit": git_commit(),
        "hardware": hardware(),
        "models": frozen["models"],
        "weights": weights,
        "tuning": frozen["tuning"],
        "systems": systems,
        "not_evaluated": NOT_EVALUATED,
        "hypothesis_h1": hypothesis,
        "exploratory": exploratory,
        "real_photo_subset": {"status": "not_collected", "sample_count": 0, "reason": NOT_EVALUATED[1]["reason"]},
        "ablations": ablations,
        "latency_benchmark": latency,
        "limitations": LIMITATIONS,
        "pool": {"test_queries": len(items), "candidates_per_query": len(test_pool)},
    }


def write_results(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmark_results.json").write_text(json.dumps(report, indent=2) + "\n")
    with open(out_dir / "benchmark_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "MRR", "MRR_CI_low", "MRR_CI_high", "Recall@1", "Recall@3", "Recall@5", "Recall@10", "nDCG@10", "Precision@5"])

        def row(label: str, block: dict[str, Any]) -> None:
            m, ci = block["metrics"], block["mrr_ci"]
            w.writerow([label, m["mrr"], ci[0], ci[1], m["recall_at_1"], m["recall_at_3"], m["recall_at_5"], m["recall_at_10"], m["ndcg_at_10"], m["precision_at_5"]])

        for s in report["systems"].values():
            row(s["name"], s)
        for group in ("signal_removal", "location_noise", "time_noise"):
            for key, block in report["ablations"][group].items():
                row(f"D {group} {key}", block)


def _comparable(report: dict[str, Any]) -> dict[str, Any]:
    keys = ("systems", "hypothesis_h1", "ablations", "weights", "dataset_hash", "config_hash")
    return {k: report[k] for k in keys}


def run_full_evaluation(
    seed: int = 42,
    output_dir: Path | None = None,
    backend: str = "standin",
    latency_sizes: tuple[int, ...] = (),
) -> dict[str, Any]:
    """Tune, freeze and evaluate in one call (used by tests with stand-in embeddings)."""
    out_dir = output_dir or RESULTS_DIR
    dataset = generate_benchmark_dataset(seed=seed)
    embed = make_embedder(backend)
    frozen = tune(dataset, embed, backend, out_dir)
    frozen = load_frozen_config(out_dir / "frozen_config.json")
    report = evaluate_test(dataset, embed, frozen, latency_sizes)
    write_results(report, out_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.runner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tune", help="tune on the development split and freeze the configuration")
    t.add_argument("--seed", type=int, default=42)
    f = sub.add_parser("final", help="evaluate the test split once from the frozen configuration")
    f.add_argument("--reproduce", action="store_true", help="re-run and compare with the saved results")
    f.add_argument("--latency-sizes", default="1000,10000,100000")
    for p in (t, f):
        p.add_argument("--backend", choices=["model", "standin"], default="model")
        p.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    if args.cmd == "tune":
        dataset = generate_benchmark_dataset(seed=args.seed)
        frozen = tune(dataset, make_embedder(args.backend), args.backend, args.out)
        print(json.dumps({"weights": frozen["weights"], "tuning": frozen["tuning"], "config_hash": frozen["config_hash"]}, indent=2))
        return 0

    frozen = load_frozen_config(args.out / "frozen_config.json")
    if frozen["models"]["backend"] != args.backend:
        print("Backend differs from the frozen configuration.", file=sys.stderr)
        return 2
    dataset = generate_benchmark_dataset(seed=frozen["seed"])
    if (dataset.dev_hash, dataset.test_hash) != (frozen["dev_hash"], frozen["test_hash"]):
        print("The dataset changed since tuning (hash mismatch); re-run tune first.", file=sys.stderr)
        return 2
    results_path = args.out / "benchmark_results.json"
    previous = json.loads(results_path.read_text()) if results_path.exists() else None
    if previous and previous.get("config_hash") == frozen["config_hash"] and not args.reproduce:
        print("Test results for this frozen configuration already exist; the test split is evaluated once. Use --reproduce to check them.", file=sys.stderr)
        return 3

    sizes = tuple(int(x) for x in args.latency_sizes.split(",") if x)
    report = evaluate_test(dataset, make_embedder(args.backend), frozen, () if args.reproduce else sizes)
    if args.reproduce:
        same = previous is not None and _comparable(previous) == _comparable(report)
        print("REPRODUCED: identical numbers" if same else "DIFFERENT from the saved results")
        return 0 if same else 1
    write_results(report, args.out)
    print(json.dumps({k: report["systems"][k]["metrics"]["mrr"] for k in report["systems"]}, indent=2))
    print(report["hypothesis_h1"]["outcome"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
