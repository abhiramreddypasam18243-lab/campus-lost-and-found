"""Evaluation protocol and leakage control (spec 7.5; AC-111, AC-117).

Everything that chooses a number -- the hybrid weights and the learned-fusion model -- runs
inside TuningHarness, which accepts development items only. The chosen configuration is
written to a file and hashed before the test split is ever scored.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from itertools import product
from pathlib import Path
from typing import Any

from eval.generator import BenchmarkDataset, ReportData, TrueItem
from eval.metrics import mrr
from eval.signals import TextEmbedder, compute_signals
from eval.systems import SIGNALS, hybrid_matrix, labels_for, ranks_from_scores, train_logistic

# Spec 6.4 initial weights, renormalised without the image signal (the benchmark has no photos).
INITIAL_WEIGHTS = {"text": 0.40 / 0.65, "location": 0.15 / 0.65, "time": 0.10 / 0.65}


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


class DataLeakageError(Exception):
    """Raised when tuning or training code is given test-set data (AC-111)."""


def assert_not_test_set(split_name: str, items: list[TrueItem] | None = None) -> None:
    """AC-111: refuse the test split by name and by any item labelled as test."""
    if split_name.lower() in ("test", "test_set", "testing"):
        raise DataLeakageError("Tuning code cannot access the test split.")
    for it in items or []:
        if getattr(it, "split", "") != Split.DEV:
            raise DataLeakageError(
                f"Tuning code was given item {it.item_id} from split '{it.split}'; only dev is allowed."
            )


def weight_grid(step: float = 0.05) -> list[dict[str, float]]:
    """All (text, location, time) weights in steps of `step` that sum to 1 (AC-117)."""
    n = round(1 / step)
    grid = []
    for t, loc in product(range(n + 1), repeat=2):
        tm = n - t - loc
        if tm < 0:
            continue
        grid.append({"text": t / n, "location": loc / n, "time": tm / n})
    return grid


class TuningHarness:
    """Chooses the hybrid weights and trains learned fusion on the development split only."""

    def __init__(
        self,
        split: Split | str,
        dev_items: list[TrueItem],
        candidate_pool: list[ReportData],
        embed: TextEmbedder | None = None,
    ) -> None:
        split_str = split.value if isinstance(split, Split) else str(split)
        assert_not_test_set(split_str, dev_items)
        self.items = dev_items
        self.pool = candidate_pool
        self._embed = embed
        self._signals: dict[str, Any] | None = None

    def _dev_signals(self) -> dict[str, Any]:
        if self._signals is None:
            if self._embed is None:
                raise ValueError("TuningHarness needs a text embedder to compute signals.")
            sig = compute_signals([it.lost_report for it in self.items], self.pool, self._embed)
            self._signals = sig.by_name()
        return self._signals

    def tune_weights_grid(self, step: float = 0.05) -> dict[str, Any]:
        """Grid search in steps of 0.05, selected by development MRR (AC-117).

        Ties are broken by the smallest distance to the spec's initial weights, so the choice
        is deterministic and moves away from the initial weights only when MRR improves.
        """
        signals = self._dev_signals()
        best: tuple[float, float, dict[str, float]] | None = None
        evaluated = 0
        for w in weight_grid(step):
            if sum(w.values()) == 0:
                continue
            ranks = ranks_from_scores(self.items, self.pool, hybrid_matrix(signals, w))
            score = mrr(ranks)
            evaluated += 1
            distance = sum((w[k] - INITIAL_WEIGHTS[k]) ** 2 for k in w)
            key = (score, -distance)
            if best is None or key > (best[0], -best[1]):
                best = (score, distance, w)
        assert best is not None
        initial_mrr = mrr(ranks_from_scores(self.items, self.pool, hybrid_matrix(signals, INITIAL_WEIGHTS)))
        return {
            "weights": {k: round(v, 2) for k, v in best[2].items()},
            "dev_mrr": best[0],
            "dev_mrr_initial_weights": initial_mrr,
            "grid_points": evaluated,
            "step": step,
        }

    def train_learned_fusion(self) -> dict[str, Any]:
        """Logistic regression over the signals, trained on development pairs only (AC-117)."""
        signals = self._dev_signals()
        model = train_logistic(signals, labels_for(self.items, self.pool), SIGNALS)
        ranks = ranks_from_scores(self.items, self.pool, model.score(signals))
        return {
            **model.to_dict(),
            "training_pairs": int(len(self.items) * len(self.pool)),
            "positive_pairs": len(self.items),
            "dev_mrr": mrr(ranks),
            "split": "dev",
        }

    @staticmethod
    def freeze_and_hash_config(
        tuning: dict[str, Any],
        learned_fusion: dict[str, Any],
        dataset: BenchmarkDataset,
        models: dict[str, Any],
        output_path: Path | None = None,
    ) -> tuple[dict[str, Any], str]:
        """AC-117: write the chosen configuration and its SHA-256 before the test run."""
        payload = {
            "weights": tuning["weights"],
            "tuning": tuning,
            "learned_fusion": learned_fusion,
            "models": models,
            "seed": dataset.seed,
            "dev_hash": dataset.dev_hash,
            "test_hash": dataset.test_hash,
            "dev_items": len(dataset.dev_items),
            "test_items": len(dataset.test_items),
            "protocol_version": "2.0",
        }
        config_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        frozen = {**payload, "config_hash": config_hash}
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
        return frozen, config_hash


def load_frozen_config(path: Path) -> dict[str, Any]:
    """Load the frozen configuration and verify its hash has not been edited."""
    frozen = json.loads(path.read_text())
    stated = frozen.pop("config_hash")
    actual = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
    if stated != actual:
        raise ValueError("frozen_config.json was modified after it was frozen (hash mismatch).")
    frozen["config_hash"] = stated
    return frozen
