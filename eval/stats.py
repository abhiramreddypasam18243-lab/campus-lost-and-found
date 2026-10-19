"""Statistical bootstrap methods for evaluation confidence intervals (AC-114, AC-115)."""

from __future__ import annotations

import random
from collections.abc import Callable


def _percentile(sorted_data: list[float], p: float) -> float:
    """Compute empirical percentile on sorted float list."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    d = k - f
    return sorted_data[f] * (1.0 - d) + sorted_data[c] * d


def bootstrap_ci[T](
    data: list[T],
    metric_fn: Callable[[list[T]], float],
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """AC-114: Compute bootstrap confidence interval for a metric over queries.

    Deterministic for a given seed. If all samples give identical metric,
    the interval is exactly [val, val].
    """
    if not data:
        return 0.0, 0.0

    rng = random.Random(seed)
    n = len(data)
    resampled_estimates: list[float] = []

    for _ in range(n_resamples):
        sample = [data[rng.randrange(n)] for _ in range(n)]
        resampled_estimates.append(metric_fn(sample))

    resampled_estimates.sort()
    alpha = (1.0 - ci) / 2.0
    low = _percentile(resampled_estimates, alpha)
    high = _percentile(resampled_estimates, 1.0 - alpha)

    # If identical values throughout, return exact bounds
    if all(x == resampled_estimates[0] for x in resampled_estimates):
        return round(resampled_estimates[0], 4), round(resampled_estimates[0], 4)

    return round(low, 4), round(high, 4)


def paired_bootstrap_ci(
    ranks_a: list[int],
    ranks_b: list[int],
    metric_fn: Callable[[list[int]], float],
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """AC-115: Paired bootstrap on identical queries for system A vs system B.

    Returns (mean_difference, ci_lower, ci_upper).
    """
    if len(ranks_a) != len(ranks_b) or not ranks_a:
        raise ValueError("Ranks lists must have identical non-zero length")

    n = len(ranks_a)
    rng = random.Random(seed)
    diffs: list[float] = []

    for _ in range(n_resamples):
        indices = [rng.randrange(n) for _ in range(n)]
        sample_a = [ranks_a[i] for i in indices]
        sample_b = [ranks_b[i] for i in indices]
        diffs.append(metric_fn(sample_a) - metric_fn(sample_b))

    mean_diff = sum(diffs) / len(diffs)
    diffs.sort()

    if all(d == diffs[0] for d in diffs):
        exact = round(diffs[0], 4)
        return exact, exact, exact

    alpha = (1.0 - ci) / 2.0
    low = _percentile(diffs, alpha)
    high = _percentile(diffs, 1.0 - alpha)

    return round(mean_diff, 4), round(low, 4), round(high, 4)
