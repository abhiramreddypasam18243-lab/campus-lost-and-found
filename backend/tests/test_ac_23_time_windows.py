from datetime import UTC, date, datetime, time

from app.domain.time import compute_time_window


def test_ac_23_asia_kolkata_day_window() -> None:
    # AC-23: For Asia/Kolkata, a day precision on 2026-10-15 gives:
    # 2026-10-14T18:30:00Z to 2026-10-15T18:29:59.999Z
    ref_date = date(2026, 10, 15)
    start, end = compute_time_window(ref_date, "day", tz_name="Asia/Kolkata")

    expected_start = datetime(2026, 10, 14, 18, 30, 0, tzinfo=UTC)
    expected_end = datetime(2026, 10, 15, 18, 29, 59, 999000, tzinfo=UTC)

    assert start == expected_start
    assert end == expected_end


def test_ac_23_asia_kolkata_day_parts() -> None:
    ref_date = date(2026, 10, 15)

    # morning: 06:00 to 12:00 local (Asia/Kolkata UTC+5:30)
    # 06:00 - 5:30 = 00:30 UTC
    # 12:00 - 5:30 = 06:30 UTC
    m_start, m_end = compute_time_window(ref_date, "morning", tz_name="Asia/Kolkata")
    assert m_start == datetime(2026, 10, 15, 0, 30, 0, tzinfo=UTC)
    assert m_end == datetime(2026, 10, 15, 6, 30, 0, tzinfo=UTC)

    # afternoon: 12:00 to 17:00 local
    # 12:00 - 5:30 = 06:30 UTC
    # 17:00 - 5:30 = 11:30 UTC
    a_start, a_end = compute_time_window(ref_date, "afternoon", tz_name="Asia/Kolkata")
    assert a_start == datetime(2026, 10, 15, 6, 30, 0, tzinfo=UTC)
    assert a_end == datetime(2026, 10, 15, 11, 30, 0, tzinfo=UTC)

    # evening: 17:00 to 22:00 local
    # 17:00 - 5:30 = 11:30 UTC
    # 22:00 - 5:30 = 16:30 UTC
    e_start, e_end = compute_time_window(ref_date, "evening", tz_name="Asia/Kolkata")
    assert e_start == datetime(2026, 10, 15, 11, 30, 0, tzinfo=UTC)
    assert e_end == datetime(2026, 10, 15, 16, 30, 0, tzinfo=UTC)

    # night: 22:00 to 06:00 next day (crossing midnight)
    # 22:00 - 5:30 = 16:30 UTC on 2026-10-15
    # 06:00 - 5:30 = 00:30 UTC on 2026-10-16
    n_start, n_end = compute_time_window(ref_date, "night", tz_name="Asia/Kolkata")
    assert n_start == datetime(2026, 10, 15, 16, 30, 0, tzinfo=UTC)
    assert n_end == datetime(2026, 10, 16, 0, 30, 0, tzinfo=UTC)


def test_ac_23_exact_window() -> None:
    ref_date = date(2026, 10, 15)
    exact = time(14, 15, 0)
    # 14:15 - 5:30 = 08:45 UTC
    start, end = compute_time_window(ref_date, "exact", tz_name="Asia/Kolkata", exact_time=exact)
    expected = datetime(2026, 10, 15, 8, 45, 0, tzinfo=UTC)
    assert start == expected
    assert end == expected
    # exact is a zero-length window
    assert (end - start).total_seconds() == 0
