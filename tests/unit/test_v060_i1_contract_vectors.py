"""Recomputes the frozen v0.6.0 I1 contract vectors (docs/specifications/0.6.0/i1-vectors/).

The vectors are authored by hand from the I1 support matrix. This module checks them with the
standard library only and deliberately imports nothing from `app/`: it is an independent reference
for the frozen contract, not a test of AIP's implementation (I1 §13, §14).
"""

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "docs" / "specifications" / "0.6.0"
VECTORS = SPEC_DIR / "i1-vectors"

_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _load(name: str) -> dict:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _serialize(value: datetime) -> str:
    utc_value = value.astimezone(UTC)
    return utc_value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc_value.microsecond:06d}Z"


def _parse_day(value: str) -> date | None:
    if not _DAY.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _window(first: str, last: str) -> tuple[datetime, datetime] | None:
    first_day, last_day = _parse_day(first), _parse_day(last)
    if first_day is None or last_day is None or first_day > last_day:
        return None
    start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
    # Normalized end: (last_day + 1 day) at midnight UTC minus 1 µs. The offset is summed first so
    # 9999-12-31 (whose next midnight is not representable) does not overflow.
    last_midnight = datetime(last_day.year, last_day.month, last_day.day, tzinfo=UTC)
    end = last_midnight + (timedelta(days=1) - timedelta(microseconds=1))
    return start, end


def _parse_instant(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


DAY_WINDOW = _load("utc-day-window.json")
WINDOWS = {w["id"]: w for w in DAY_WINDOW["windows"]}


@pytest.mark.parametrize("vector", DAY_WINDOW["windows"], ids=lambda v: v["id"])
def test_day_window_normalization(vector: dict) -> None:
    bounds = _window(vector["first_day"], vector["last_day"])
    if not vector["valid"]:
        assert bounds is None
        return
    assert bounds is not None
    assert (_serialize(bounds[0]), _serialize(bounds[1])) == (vector["start"], vector["end"])


@pytest.mark.parametrize("vector", DAY_WINDOW["membership"], ids=lambda v: v["id"])
def test_day_window_membership_is_inclusive(vector: dict) -> None:
    window = WINDOWS[vector["window"]]
    bounds = _window(window["first_day"], window["last_day"])
    instant = _parse_instant(vector["instant"])
    assert bounds is not None and instant is not None
    assert (bounds[0] <= instant <= bounds[1]) is vector["included"]


@pytest.mark.parametrize("vector", DAY_WINDOW["utc_day_assignment"], ids=lambda v: v["id"])
def test_utc_day_assignment(vector: dict) -> None:
    instant = _parse_instant(vector["instant"])
    assert instant is not None
    assert instant.astimezone(UTC).date().isoformat() == vector["utc_day"]


@pytest.mark.parametrize("vector", DAY_WINDOW["capture_instant_parsing"], ids=lambda v: v["id"])
def test_capture_instant_requires_explicit_offset(vector: dict) -> None:
    assert (_parse_instant(vector["value"]) is not None) is vector["parsable"]


def _utc_day(value: str) -> str:
    instant = _parse_instant(value)
    assert instant is not None
    return instant.astimezone(UTC).date().isoformat()


@pytest.mark.parametrize("vector", DAY_WINDOW["timestamp_roles"], ids=lambda v: v["id"])
def test_timestamp_roles(vector: dict) -> None:
    client_day, fact_day = _utc_day(vector["client_timestamp"]), _utc_day(vector["fact_timestamp"])
    # v1 is always bucketed by the accepted fact timestamp; ingestion guard I-4 compares UTC days.
    assert fact_day == vector["v1_bucket_day"]
    assert (client_day == fact_day) is vector["i4_passes"]
    if not vector["i4_passes"]:
        assert vector["reason"] == "LOCALITY_CLIENT_FACT_DAY_MISMATCH"
        assert "v2_bucket_utc_day" not in vector
        return
    # v2 takes its day and first/last_seen from the accepted fact timestamp, never the CLIENT's.
    assert vector["v2_bucket_utc_day"] == fact_day
    fact = _parse_instant(vector["fact_timestamp"])
    assert fact is not None
    assert vector["v2_first_seen"] == vector["v2_last_seen"] == _serialize(fact)


def test_vector_ids_are_unique() -> None:
    ids = [
        v["id"]
        for group in ("windows", "membership", "utc_day_assignment")
        for v in DAY_WINDOW[group]
    ]
    ids += [v["id"] for v in DAY_WINDOW["capture_instant_parsing"]]
    ids += [v["id"] for v in DAY_WINDOW["timestamp_roles"]]
    assert len(ids) == len(set(ids))


def _spec_reason_codes() -> set[str]:
    spec = (SPEC_DIR / "i1-locality-and-evidence-applicability.md").read_text(encoding="utf-8")
    block = spec.split("Internal diagnostic codes", 1)[1].split("```", 2)[1]
    return set(re.findall(r"LOCALITY_[A-Z0-9_]+", block))


def test_support_matrix_uses_only_frozen_reason_codes() -> None:
    frozen = _spec_reason_codes()
    assert len(frozen) == 23
    matrix = (SPEC_DIR / "i1-locality-support-matrix.md").read_text(encoding="utf-8")
    used = set(re.findall(r"LOCALITY_[A-Z0-9_]+", matrix))
    assert used <= frozen, sorted(used - frozen)
