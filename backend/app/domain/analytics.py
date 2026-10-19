"""Pure domain calculations for operational analytics (AC-105 to AC-108)."""

from __future__ import annotations

import statistics

SYNTHETIC_DATA_BANNER = (
    "Operational metrics are generated for dashboard demonstration and show system activity, "
    "not verified real-world recovery gains."
)


def calculate_recovery_rate(returned_count: int, unclaimed_expired_count: int) -> float | None:
    """AC-105: recovery rate = returned / (returned + unclaimed_expired).

    Returns None when denominator is 0.
    """
    denominator = returned_count + unclaimed_expired_count
    if denominator == 0:
        return None
    return round(returned_count / denominator, 3)


def calculate_unclaimed_rate(unclaimed_expired_count: int, total_created: int) -> float | None:
    """AC-105: unclaimed rate = unclaimed_expired / total_created.

    Returns None when total_created is 0.
    """
    if total_created == 0:
        return None
    return round(unclaimed_expired_count / total_created, 3)


def calculate_median_duration(durations: list[float]) -> float | None:
    """Calculate median duration in seconds/hours. Returns None if durations list is empty."""
    if not durations:
        return None
    return float(statistics.median(durations))
