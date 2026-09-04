"""Independent re-derivation of `claim_id` (spec §12.1), `context_id` (spec §16.2), and evidence
ids (the formulas documented in `app/canonical/ids.py`'s docstrings) - written directly from the
spec/formula text, not imported from app code. Authoring-time only - see `canonical_json.py`'s
module docstring for why the live evaluation path never imports this module.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from evaluation.architecture_answers.reference.canonical_json import (
    canonical_json_bytes,
    format_utc_timestamp,
)


def claim_id(
    *, subject_id: str, predicate: str, object_id: str, delivery_kind: str, delivery_via_id: str
) -> str:
    """spec §12.1: aip:claim:v1:sha256(canonical-json({subject_id, predicate, object_id,
    delivery_kind, delivery_via_id}))."""
    payload = {
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "delivery_kind": delivery_kind,
        "delivery_via_id": delivery_via_id,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"aip:claim:v1:{digest}"


def context_id(*, environment: str, window_start: datetime, window_end: datetime) -> str:
    """spec §16.2: aip:observation-context:v1:sha256(canonical-json({version: 1, environment,
    window_start_utc, window_end_utc}))."""
    payload = {
        "version": 1,
        "environment": environment,
        "window_start_utc": format_utc_timestamp(window_start),
        "window_end_utc": format_utc_timestamp(window_end),
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"aip:observation-context:v1:{digest}"


def declared_evidence_id(source_type: str, service_slug: str, revision: str | None = None) -> str:
    """Declared evidence carries no hash - a plain formatted string keyed by source type and the
    declaring service's slug (plus an optional revision)."""
    if revision:
        return f"evidence:{source_type.lower()}:{service_slug}:{revision}"
    return f"evidence:{source_type.lower()}:{service_slug}"


def observed_evidence_id(
    *,
    environment: str,
    bucket_start: datetime,
    subject_id: str,
    relation_type: str,
    object_id: str,
) -> str:
    """One id per (fact, day, environment) bucket: a 12-hex-char truncated sha256 of
    `subject_id|relation_type|object_id`, embedded in a formatted string with the environment and
    bucket day."""
    fact_hash = hashlib.sha256(f"{subject_id}|{relation_type}|{object_id}".encode()).hexdigest()[
        :12
    ]
    return f"evidence:otel:{environment}:{bucket_start:%Y-%m-%d}:{fact_hash}"
