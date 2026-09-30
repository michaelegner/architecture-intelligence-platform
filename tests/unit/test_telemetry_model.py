from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.telemetry.model import day_bucket


def test_day_bucket_preserves_utc_calendar_day():
    start, end = day_bucket(datetime(2026, 9, 29, 1, 30, tzinfo=UTC))
    assert start == datetime(2026, 9, 29, tzinfo=UTC)
    assert end == datetime(2026, 9, 30, tzinfo=UTC)


def test_day_bucket_converts_offset_timestamp_before_truncating():
    plus_two = timezone(timedelta(hours=2))
    start, end = day_bucket(datetime(2026, 9, 29, 1, 30, tzinfo=plus_two))
    assert start == datetime(2026, 9, 28, tzinfo=UTC)
    assert end == datetime(2026, 9, 29, tzinfo=UTC)


def test_day_bucket_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="offset-aware"):
        day_bucket(datetime(2026, 9, 29, 1, 30))
