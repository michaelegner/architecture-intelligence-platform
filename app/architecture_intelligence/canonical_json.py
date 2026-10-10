"""Deterministic canonical-serialization rule shared by the v0.4 answer contract (I1.1) and, from
I1.2 onward, snapshot fingerprinting: sorted object keys, no insignificant whitespace, UTF-8, and
timestamps normalized to UTC with exactly six fractional-second digits (spec §16.2/§18)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


def canonical_json_bytes(value: BaseModel | dict[str, Any] | list[Any]) -> bytes:
    normalized = _normalize(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def canonical_digest(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    """Lowercase hex SHA-256 of `canonical_json_bytes(value)` - the digest behind the
    `aip:claim:v1:`, snapshot, observation-context and local-assessment ids. Not RFC 8785: never
    interchangeable with `app.common.jcs.canonical_sha256_hex`."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python"))
    if isinstance(value, datetime):
        return format_utc_timestamp(value)
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def format_utc_timestamp(value: datetime) -> str:
    """Normalizes a datetime to UTC with a `Z` suffix and exactly six fractional-second digits
    (spec §16.2). Shared by canonical serialization and observation-context id hashing
    (`app.architecture_intelligence.observation_context.compute_context_id`)."""
    utc_value = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return utc_value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc_value.microsecond:06d}Z"
