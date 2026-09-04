"""Independent re-derivation of the canonical-JSON serialization rule (spec
docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md §16.2/§18), written
directly from the spec text - deliberately NOT importing app.architecture_intelligence.canonical_json.

This module exists only for the authoring-time reference tool
(`evaluation.architecture_answers.reference`): a scenario author runs it once against a prepared
fixture to derive the literal identities that get frozen into `expected_answer.json`. The live
loader/runner/comparator never import this module - reusing it there would let a shared defect in
the canonicalization rule pass its own grading (I1.4 review finding #1).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    normalized = _normalize(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return format_utc_timestamp(value)
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def format_utc_timestamp(value: datetime) -> str:
    """UTC, `Z` suffix, exactly six fractional-second digits (spec §16.2)."""
    utc_value = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return utc_value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc_value.microsecond:06d}Z"
