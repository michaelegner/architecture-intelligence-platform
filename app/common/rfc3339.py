"""Shared helpers for parsing RFC 3339 timestamps."""

from datetime import datetime


def _parse_rfc3339(value: str | None) -> datetime | None:
    """Parse an RFC 3339 value, returning ``None`` when it is absent or unusable."""
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed
