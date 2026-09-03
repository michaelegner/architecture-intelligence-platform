"""v0.4.0 I1.2 - observation-context normalization and `context_id` computation (spec §16).

`ObservationContextRef` (I1.1, `app.architecture_intelligence.contracts`) validates only the
*shape* of `context_id` and its own fields. This module is the single place that computes a real
`context_id` from raw request fields and builds a validated `ObservationContextRef` from it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from app.architecture_intelligence.canonical_json import canonical_json_bytes, format_utc_timestamp
from app.architecture_intelligence.contracts import ObservationContextRef

_CONTEXT_ID_VERSION = 1


def compute_context_id(environment: str, window_start: datetime, window_end: datetime) -> str:
    """`aip:observation-context:v1:sha256(canonical-json({version, environment, window_start_utc,
    window_end_utc}))` (spec §16.2). Equivalent-offset timestamps normalize to the same UTC string
    and therefore the same id."""
    payload = {
        "version": _CONTEXT_ID_VERSION,
        "environment": environment,
        "window_start_utc": format_utc_timestamp(window_start),
        "window_end_utc": format_utc_timestamp(window_end),
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"aip:observation-context:v1:{digest}"


def build_observation_context_ref(
    environment: str, window_start: datetime, window_end: datetime
) -> ObservationContextRef:
    """Computes `context_id` and constructs the validated `ObservationContextRef`.

    `ObservationContextRef`'s own validators (environment shape, explicit UTC offset, window
    bounds) are the single source of truth for rejecting bad input - this function does not
    duplicate them. If `window_start`/`window_end`/`environment` are invalid, construction raises
    `pydantic.ValidationError` and the computed `context_id` (which may have been computed from a
    best-effort, not-yet-validated normalization) never escapes, since the object never comes into
    being.
    """
    context_id = compute_context_id(environment, window_start, window_end)
    return ObservationContextRef(
        context_id=context_id,
        environment=environment,
        window_start=window_start,
        window_end=window_end,
    )
