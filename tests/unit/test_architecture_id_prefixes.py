import re
from datetime import UTC, datetime

from app.architecture_intelligence.contracts import (
    _CLAIM_ID_PATTERN,
    _CONTEXT_ID_PATTERN,
    _SNAPSHOT_ID_PATTERN,
)
from app.architecture_intelligence.dependency_projection import compute_claim_id
from app.architecture_intelligence.observation_context import compute_context_id
from app.architecture_intelligence.repository import snapshot_fingerprint


def test_snapshot_id_round_trips_through_contract_pattern() -> None:
    snapshot_id, _revision = snapshot_fingerprint({"services": []})
    assert re.fullmatch(_SNAPSHOT_ID_PATTERN, snapshot_id)


def test_observation_context_id_round_trips_through_contract_pattern() -> None:
    context_id = compute_context_id(
        "prod",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert re.fullmatch(_CONTEXT_ID_PATTERN, context_id)


def test_claim_id_round_trips_through_contract_pattern() -> None:
    claim_id = compute_claim_id(
        subject_id="service:a",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:b",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:get-b",
    )
    assert re.fullmatch(_CLAIM_ID_PATTERN, claim_id)
