from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.architecture_intelligence.contracts import ObservationContextRef
from app.architecture_intelligence.observation_context import (
    build_observation_context_ref,
    compute_context_id,
)

_WINDOW_END = datetime(2026, 8, 27, tzinfo=UTC)


def test_context_id_normalizes_equivalent_utc_offsets():
    offset_start = datetime(2026, 8, 26, 2, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    utc_start = datetime(2026, 8, 26, 0, 0, 0, tzinfo=UTC)
    assert compute_context_id("demo", offset_start, _WINDOW_END) == compute_context_id(
        "demo", utc_start, _WINDOW_END
    )


def test_context_id_is_case_sensitive_on_environment():
    start = datetime(2026, 8, 26, tzinfo=UTC)
    assert compute_context_id("demo", start, _WINDOW_END) != compute_context_id(
        "Demo", start, _WINDOW_END
    )


def test_context_id_changes_when_window_changes():
    start = datetime(2026, 8, 26, tzinfo=UTC)
    other_end = datetime(2026, 8, 28, tzinfo=UTC)
    assert compute_context_id("demo", start, _WINDOW_END) != compute_context_id(
        "demo", start, other_end
    )


def test_build_observation_context_ref_matches_independent_computation():
    start = datetime(2026, 8, 26, tzinfo=UTC)
    ref = build_observation_context_ref("demo", start, _WINDOW_END)
    assert isinstance(ref, ObservationContextRef)
    assert ref.context_id == compute_context_id("demo", start, _WINDOW_END)
    assert ref.environment == "demo"
    assert ref.window_start == start
    assert ref.window_end == _WINDOW_END


def test_build_observation_context_ref_normalizes_offset_windows_to_utc():
    # spec §16.1/§16.2: the *returned* context, not just the context_id hash input, must be UTC.
    offset_start = datetime(2026, 8, 26, 2, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    offset_end = datetime(2026, 8, 27, 2, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    ref = build_observation_context_ref("demo", offset_start, offset_end)

    utc_start = datetime(2026, 8, 26, 0, 0, 0, tzinfo=UTC)
    utc_end = datetime(2026, 8, 27, 0, 0, 0, tzinfo=UTC)
    assert (ref.window_start, ref.window_end) == (utc_start, utc_end)
    assert ref.window_start.utcoffset() == timedelta(0)
    assert ref.window_end.utcoffset() == timedelta(0)

    # equivalent-offset inputs must now produce identical materialized fields, not just the same id
    utc_ref = build_observation_context_ref("demo", utc_start, utc_end)
    assert ref.window_start == utc_ref.window_start
    assert ref.window_end == utc_ref.window_end
    assert ref.context_id == utc_ref.context_id


def test_build_observation_context_ref_rejects_naive_window_start():
    with pytest.raises(ValidationError):
        build_observation_context_ref("demo", datetime(2026, 8, 26), _WINDOW_END)  # noqa: DTZ001


def test_build_observation_context_ref_rejects_reversed_window():
    start = datetime(2026, 8, 26, tzinfo=UTC)
    with pytest.raises(ValidationError):
        build_observation_context_ref("demo", _WINDOW_END, start)


def test_build_observation_context_ref_rejects_window_over_31_days():
    start = datetime(2026, 8, 26, tzinfo=UTC)
    too_far = start + timedelta(days=32)
    with pytest.raises(ValidationError):
        build_observation_context_ref("demo", start, too_far)


def test_build_observation_context_ref_rejects_invalid_environment():
    start = datetime(2026, 8, 26, tzinfo=UTC)
    with pytest.raises(ValidationError):
        build_observation_context_ref("", start, _WINDOW_END)
