"""Compare the old and shared RFC 3339 parsing implementations."""

from datetime import datetime
from timeit import timeit

from app.common.rfc3339 import _parse_rfc3339

VALUE = "2026-08-26T12:00:00+02:00"
ITERATIONS = 100_000


def parse_inline() -> datetime:
    return datetime.fromisoformat(VALUE)


def parse_shared() -> datetime | None:
    return _parse_rfc3339(VALUE)


old_time = timeit(parse_inline, number=ITERATIONS)
new_time = timeit(parse_shared, number=ITERATIONS)

print(f"Parsing {ITERATIONS:,} iterations of {VALUE!r}")
print(f"Old datetime.fromisoformat(): {old_time:.6f} seconds")
print(f"New _parse_rfc3339():        {new_time:.6f} seconds")
