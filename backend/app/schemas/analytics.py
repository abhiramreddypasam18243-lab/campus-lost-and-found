"""Pydantic schemas for analytics dashboard (spec section 15, AC-105 to AC-108)."""

from pydantic import BaseModel, ConfigDict


class DashboardMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_created: int
    open_count: int
    returned_count: int
    unclaimed_expired_count: int
    recovery_rate: float | None
    unclaimed_rate: float | None
    median_time_to_recovery_hours: float | None
    queue_age_median_hours: float | None
    banner_notice: str
    is_synthetic_demo: bool = True
