from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

TimePrecision = Literal["day", "morning", "afternoon", "evening", "night", "exact"]


def compute_time_window(
    ref_date: date,
    precision: TimePrecision,
    tz_name: str = "Asia/Kolkata",
    exact_time: time | None = None,
) -> tuple[datetime, datetime]:
    """AC-23: Compute UTC time window for a given reference date, precision, and timezone.

    - 'day': 00:00:00 to 23:59:59.999 local
    - 'morning': 06:00 to 12:00 local
    - 'afternoon': 12:00 to 17:00 local
    - 'evening': 17:00 to 22:00 local
    - 'night': 22:00 local to 06:00 local next day (crossing midnight)
    - 'exact': exact timestamp (zero-length window)
    """
    tz = ZoneInfo(tz_name)

    if precision == "day":
        start_local = datetime.combine(ref_date, time(0, 0, 0), tzinfo=tz)
        end_local = datetime.combine(ref_date, time(23, 59, 59, 999000), tzinfo=tz)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    if precision == "morning":
        start_local = datetime.combine(ref_date, time(6, 0, 0), tzinfo=tz)
        end_local = datetime.combine(ref_date, time(12, 0, 0), tzinfo=tz)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    if precision == "afternoon":
        start_local = datetime.combine(ref_date, time(12, 0, 0), tzinfo=tz)
        end_local = datetime.combine(ref_date, time(17, 0, 0), tzinfo=tz)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    if precision == "evening":
        start_local = datetime.combine(ref_date, time(17, 0, 0), tzinfo=tz)
        end_local = datetime.combine(ref_date, time(22, 0, 0), tzinfo=tz)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    if precision == "night":
        start_local = datetime.combine(ref_date, time(22, 0, 0), tzinfo=tz)
        end_local = datetime.combine(ref_date + timedelta(days=1), time(6, 0, 0), tzinfo=tz)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    if precision == "exact":
        t = exact_time or time(0, 0, 0)
        dt_local = datetime.combine(ref_date, t, tzinfo=tz)
        dt_utc = dt_local.astimezone(UTC)
        return dt_utc, dt_utc

    raise ValueError(f"Unknown precision: {precision}")
