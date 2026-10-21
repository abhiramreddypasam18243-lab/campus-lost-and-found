"""Retrieval systems compared in the benchmark (spec 7.2; AC-116, AC-119).

A: BM25 keyword search over title + description
B: text embedding (the text signal alone)
C: image similarity -- not evaluated: the benchmark has no photos (see results.not_evaluated)
D: hand-weighted hybrid (spec 6.4), weights tuned on the development split
E: learned fusion, logistic regression over the signals, trained on the development split
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from eval.bm25 import BM25Index
from eval.generator import ReportData, TrueItem
from eval.signals import SignalMatrices

SIGNALS = ("text", "location", "time")


def bm25_matrix(queries: list[ReportData], pool: list[ReportData]) -> np.ndarray:
    """System A: BM25 over title and description (no embeddings, no metadata)."""
    index = BM25Index([f"{c.title} {c.description}" for c in pool])
    return np.array(
        [[index.score(f"{q.title} {q.description}", j) for j in range(len(pool))] for q in queries]
    )


def hybrid_matrix(signals: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    """System D: sum(w_i * s_i) / sum(w_i) over the signals present (spec 6.4).

    Vectorised form of app.domain.matching.calculate_hybrid_score: a missing signal (NaN) is
    excluded from both sums, never counted as zero. A test checks the two agree.
    """
    num = np.zeros_like(next(iter(signals.values())), dtype=float)
    den = np.zeros_like(num)
    for name, s in signals.items():
        w = weights.get(name, 0.0)
        present = ~np.isnan(s)
        num += np.where(present, w * np.nan_to_num(s), 0.0)
        den += np.where(present, w, 0.0)
    combined: np.ndarray = np.divide(num, den, out=np.zeros_like(num), where=den > 0)
    return combined


@dataclass
class LogisticModel:
    """System E. Scores are the logit, which ranks identically to the probability."""

    features: tuple[str, ...]
    coef: list[float]
    intercept: float
    mean: list[float]
    std: list[float]

    def score(self, signals: dict[str, np.ndarray]) -> np.ndarray:
        z = np.full_like(signals[self.features[0]], self.intercept, dtype=float)
        for k, name in enumerate(self.features):
            z += self.coef[k] * (signals[name] - self.mean[k]) / self.std[k]
        return z

    def to_dict(self) -> dict[str, object]:
        return {
            "model_type": "logistic_regression",
            "features": list(self.features),
            "coef_standardised": [round(c, 6) for c in self.coef],
            "intercept": round(self.intercept, 6),
            "feature_mean": [round(m, 6) for m in self.mean],
            "feature_std": [round(s, 6) for s in self.std],
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> LogisticModel:
        return LogisticModel(
            features=tuple(d["features"]),  # type: ignore[arg-type]
            coef=list(d["coef_standardised"]),  # type: ignore[call-overload]
            intercept=float(d["intercept"]),  # type: ignore[arg-type]
            mean=list(d["feature_mean"]),  # type: ignore[call-overload]
            std=list(d["feature_std"]),  # type: ignore[call-overload]
        )


def train_logistic(
    signals: dict[str, np.ndarray],
    labels: np.ndarray,
    features: tuple[str, ...] = SIGNALS,
    l2: float = 1e-3,
    iterations: int = 3000,
    learning_rate: float = 0.5,
) -> LogisticModel:
    """Class-balanced logistic regression by full-batch gradient descent (deterministic).

    Every signal is always present in this benchmark (no photos), so no missing-value
    indicators are needed; the image signal is absent for every pair and carries no information.
    """
    x = np.stack([signals[f].ravel() for f in features], axis=1)
    y = labels.ravel().astype(float)
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0] = 1.0
    xs = (x - mean) / std
    pos = y.sum()
    sample_w = np.where(y == 1, (len(y) - pos) / pos, 1.0)
    sample_w = sample_w / sample_w.mean()

    w = np.zeros(xs.shape[1])
    b = 0.0
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-(xs @ w + b)))
        g = sample_w * (p - y)
        w -= learning_rate * (xs.T @ g / len(y) + l2 * w)
        b -= learning_rate * g.mean()
    return LogisticModel(features, w.tolist(), float(b), mean.tolist(), std.tolist())


def ranks_from_scores(
    items: list[TrueItem], pool: list[ReportData], scores: np.ndarray
) -> list[int]:
    """1-based rank of each query's true found report; ties broken by candidate id."""
    ids = [c.id for c in pool]
    order_key = np.argsort(np.argsort(ids))  # position of each id in sorted order
    ranks: list[int] = []
    for i, item in enumerate(items):
        target = ids.index(item.found_report.id)
        row = scores[i]
        better = np.sum(row > row[target])
        tied_before = np.sum((row == row[target]) & (order_key < order_key[target]))
        ranks.append(int(better + tied_before + 1))
    return ranks


def labels_for(items: list[TrueItem], pool: list[ReportData]) -> np.ndarray:
    ids = [c.id for c in pool]
    y = np.zeros((len(items), len(pool)))
    for i, item in enumerate(items):
        y[i, ids.index(item.found_report.id)] = 1.0
    return y


def all_system_scores(
    items: list[TrueItem],
    sig: SignalMatrices,
    weights: dict[str, float],
    model: LogisticModel,
) -> dict[str, np.ndarray]:
    signals = sig.by_name()
    return {
        "A": bm25_matrix(sig.queries, sig.pool),
        "B": sig.text,
        "D": hybrid_matrix(signals, weights),
        "E": model.score(signals),
    }
