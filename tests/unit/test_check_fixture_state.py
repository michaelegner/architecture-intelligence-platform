"""v0.4.2 I2 - unit coverage for `examples/runtime-demo/check_fixture_state.py`'s pure
EMPTY/COMPLETE/PARTIAL_OR_INCOMPATIBLE classifier (spec
`docs/specifications/0.4.2/i2-client-ready-demo-and-documentation.md` §15/§45).

`examples/runtime-demo/` is not a Python package (it is invoked as a standalone script inside the
demo container, not imported), so the module under test is loaded here by file path rather than by
a normal `import`. Only `classify()` and `project_drift_claims()` are exercised - both are pure
functions with no Neo4j dependency; the Neo4j-backed half (`classify_fixture`/`run`) is covered by
`tests/integration/test_check_fixture_state_classification.py` against a real database instead.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import Outcome

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "examples"
    / "runtime-demo"
    / "check_fixture_state.py"
)
_spec = importlib.util.spec_from_file_location("check_fixture_state", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
check_fixture_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_fixture_state)

WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_FIRST_SEEN = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)
_LAST_SEEN = datetime(2026, 8, 26, 12, 0, 5, tzinfo=UTC)


def _evidence_row(
    evidence_id: str,
    evidence_type: str,
    *,
    source_type: str = "ASYNCAPI",
    source_file: str = "order-service/asyncapi.yaml",
    observation_count: int | None = None,
    first_seen: datetime | None = None,
    last_seen: datetime | None = None,
    sample_trace_ids: list[str] | None = None,
) -> dict:
    row = {
        "id": evidence_id,
        "source_type": source_type,
        "source_file": source_file,
        "evidence_type": evidence_type,
    }
    if observation_count is not None:
        row["observation_count"] = observation_count
    if first_seen is not None:
        row["first_seen"] = first_seen
    if last_seen is not None:
        row["last_seen"] = last_seen
    if sample_trace_ids is not None:
        row["sample_trace_ids"] = sample_trace_ids
    return row


def _base_state() -> dict:
    """A small but structurally real canonical state: one declared SENDS relation and one
    OBSERVED-only CALLS relation, so declared/observed relation mismatches can be tested
    independently of each other."""
    return {
        "version": 1,
        "services": [{"id": "service:order-service", "name": "OrderService"}],
        "operations": [],
        "queues": [{"id": "queue:unused-q", "name": "unused-q"}],
        "messages": [],
        "schemas": [],
        "evidence": [
            _evidence_row("evidence:asyncapi:order-service", "DECLARED"),
            _evidence_row(
                "evidence:otel:demo:1",
                "OBSERVED",
                source_type="OPENTELEMETRY",
                source_file="opentelemetry",
                observation_count=1,
                first_seen=_FIRST_SEEN,
                last_seen=_LAST_SEEN,
                sample_trace_ids=["aaaa"],
            ),
        ],
        "relations": [
            {
                "type": "SENDS",
                "source_id": "service:order-service",
                "target_id": "queue:unused-q",
                "evidence_ids": ["evidence:asyncapi:order-service"],
            },
            {
                "type": "CALLS",
                "source_id": "service:order-service",
                "target_id": "operation:legacy:GET:/pricing/{sku}",
                "evidence_ids": ["evidence:otel:demo:1"],
            },
        ],
        "semantic_config": {"coverage_qualification_enabled": True},
    }


def _node_relationship_counts(state: dict) -> tuple[int, int]:
    node_count = sum(
        len(state[key])
        for key in ("services", "operations", "queues", "messages", "schemas", "evidence")
    )
    return node_count, len(state["relations"])


def _build_manifest(state: dict, *, expected_drift_claims: list[dict] | None = None) -> dict:
    snapshot_id, _ = check_fixture_state.snapshot_fingerprint(state)
    node_count, relationship_count = _node_relationship_counts(state)
    return {
        "manifest_version": 1,
        "fixture_id": "test-fixture",
        "service_id": "service:order-service",
        "environment": "demo",
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "seed_timestamp": "2026-08-26T12:00:00.000000Z",
        "expected_snapshot_id": snapshot_id,
        "total_node_count": node_count,
        "total_relationship_count": relationship_count,
        "expected_drift_claims": expected_drift_claims or [],
        "canonical_state": json.loads(canonical_json_bytes(state)),
    }


def _classify_complete(manifest: dict, state: dict, drift_claims: list[dict] | None = None):
    node_count, relationship_count = _node_relationship_counts(state)
    return check_fixture_state.classify(
        manifest,
        state,
        drift_claims or [],
        whole_database_node_count=node_count,
        whole_database_relationship_count=relationship_count,
    )


def _mismatch_codes(result: dict) -> set[str]:
    return {m["code"] for m in result["mismatches"]}


def test_empty_requires_zero_whole_database_counts():
    manifest = _build_manifest(_base_state())
    result = check_fixture_state.classify(
        manifest,
        _base_state(),
        [],
        whole_database_node_count=0,
        whole_database_relationship_count=0,
    )
    assert result == {
        "classification": "EMPTY",
        "expected_snapshot_id": manifest["expected_snapshot_id"],
        "actual_snapshot_id": None,
        "mismatches": [],
    }


def test_complete_matches_an_identical_state():
    state = _base_state()
    manifest = _build_manifest(state)
    result = _classify_complete(manifest, state)
    assert result["classification"] == "COMPLETE"
    assert result["mismatches"] == []
    assert result["actual_snapshot_id"] == manifest["expected_snapshot_id"]


def test_node_count_mismatch_from_a_stray_node():
    state = _base_state()
    manifest = _build_manifest(state)
    node_count, relationship_count = _node_relationship_counts(state)
    result = check_fixture_state.classify(
        manifest,
        state,
        [],
        whole_database_node_count=node_count + 1,
        whole_database_relationship_count=relationship_count,
    )
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert check_fixture_state._NODE_COUNT_MISMATCH in _mismatch_codes(result)


def test_relationship_count_mismatch_from_a_missing_relation():
    state = _base_state()
    manifest = _build_manifest(state)
    node_count, _ = _node_relationship_counts(state)
    del state["relations"][1]  # drop the OBSERVED-only CALLS relation
    result = check_fixture_state.classify(
        manifest,
        state,
        [],
        whole_database_node_count=node_count,
        whole_database_relationship_count=1,
    )
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    codes = _mismatch_codes(result)
    assert check_fixture_state._RELATIONSHIP_COUNT_MISMATCH in codes
    assert check_fixture_state._OBSERVED_RELATION_MISMATCH in codes


def test_unexpected_graph_data_from_an_extra_service():
    state = _base_state()
    manifest = _build_manifest(state)
    state["services"] = [*state["services"], {"id": "service:extra", "name": "Extra"}]
    node_count, relationship_count = _node_relationship_counts(state)
    result = check_fixture_state.classify(
        manifest,
        state,
        [],
        whole_database_node_count=node_count,
        whole_database_relationship_count=relationship_count,
    )
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert check_fixture_state._UNEXPECTED_GRAPH_DATA in _mismatch_codes(result)


def test_declared_relation_mismatch_when_a_declared_relation_disappears():
    state = _base_state()
    manifest = _build_manifest(state)
    del state["relations"][0]  # drop the DECLARED-only SENDS relation
    node_count, _ = _node_relationship_counts(state)
    result = check_fixture_state.classify(
        manifest,
        state,
        [],
        whole_database_node_count=node_count,
        whole_database_relationship_count=1,
    )
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert check_fixture_state._DECLARED_RELATION_MISMATCH in _mismatch_codes(result)


def test_observed_relation_mismatch_when_an_observed_relation_disappears():
    state = _base_state()
    manifest = _build_manifest(state)
    del state["relations"][1]  # drop the OBSERVED-only CALLS relation
    node_count, _ = _node_relationship_counts(state)
    result = check_fixture_state.classify(
        manifest,
        state,
        [],
        whole_database_node_count=node_count,
        whole_database_relationship_count=1,
    )
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert check_fixture_state._OBSERVED_RELATION_MISMATCH in _mismatch_codes(result)


def test_evidence_field_mismatches_use_specific_codes():
    field_and_code = {
        "observation_count": check_fixture_state._OBSERVATION_COUNT_MISMATCH,
        "first_seen": check_fixture_state._FIRST_SEEN_MISMATCH,
        "last_seen": check_fixture_state._LAST_SEEN_MISMATCH,
        "sample_trace_ids": check_fixture_state._TRACE_SAMPLE_MISMATCH,
    }
    for field, expected_code in field_and_code.items():
        state = _base_state()
        manifest = _build_manifest(state)
        otel_evidence = next(e for e in state["evidence"] if e["id"] == "evidence:otel:demo:1")
        if field == "sample_trace_ids":
            otel_evidence[field] = ["bbbb"]
        elif field in ("first_seen", "last_seen"):
            otel_evidence[field] = datetime(2026, 8, 26, 13, 0, 0, tzinfo=UTC)
        else:
            otel_evidence[field] = 99

        result = _classify_complete(manifest, state)
        assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE", field
        assert expected_code in _mismatch_codes(result), field


def test_evidence_mismatch_for_a_missing_evidence_record():
    state = _base_state()
    manifest = _build_manifest(state)
    # Drop the OBSERVED evidence record but keep the relation referencing it, so only the
    # evidence-set comparison (not the relation comparison) should fail.
    state["evidence"] = [e for e in state["evidence"] if e["id"] != "evidence:otel:demo:1"]
    node_count, relationship_count = _node_relationship_counts(state)
    result = check_fixture_state.classify(
        manifest,
        state,
        [],
        whole_database_node_count=node_count,
        whole_database_relationship_count=relationship_count,
    )
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert check_fixture_state._EVIDENCE_MISMATCH in _mismatch_codes(result)


def test_drift_claim_mismatch_when_the_claim_set_differs():
    state = _base_state()
    expected_claims = [
        {
            "subject": "service:order-service",
            "target": "LegacyPricingService",
            "via": "GET /pricing/{sku}",
            "qualification": "OBSERVED_ONLY",
            "evidence_refs": ["evidence:otel:demo:1"],
        }
    ]
    manifest = _build_manifest(state, expected_drift_claims=expected_claims)
    result = _classify_complete(manifest, state, drift_claims=[])
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert check_fixture_state._DRIFT_CLAIM_MISMATCH in _mismatch_codes(result)


def test_drift_claim_match_stays_complete():
    state = _base_state()
    expected_claims = [
        {
            "subject": "service:order-service",
            "target": "LegacyPricingService",
            "via": "GET /pricing/{sku}",
            "qualification": "OBSERVED_ONLY",
            "evidence_refs": ["evidence:otel:demo:1"],
        }
    ]
    manifest = _build_manifest(state, expected_drift_claims=expected_claims)
    result = _classify_complete(manifest, state, drift_claims=expected_claims)
    assert result["classification"] == "COMPLETE"
    assert result["mismatches"] == []


def test_project_drift_claims_returns_empty_for_not_answered():
    answer = SimpleNamespace(outcome=Outcome.NOT_ANSWERED, claims=[])
    assert check_fixture_state.project_drift_claims(answer) == []


def test_project_drift_claims_projects_and_sorts_claims():
    def _claim(target: str, qualification: str, evidence_refs: list[str]):
        return SimpleNamespace(
            subject=SimpleNamespace(id="service:order-service"),
            object=SimpleNamespace(name=target),
            delivery=SimpleNamespace(via=SimpleNamespace(name=target)),
            qualification=SimpleNamespace(value=qualification),
            evidence_refs=evidence_refs,
        )

    answer = SimpleNamespace(
        outcome=Outcome.ANSWERED,
        claims=[
            _claim("unused-q", "NOT_OBSERVED_IN_WINDOW", ["evidence:asyncapi:order-service"]),
            _claim("LegacyPricingService", "OBSERVED_ONLY", ["evidence:otel:demo:1"]),
        ],
    )

    projected = check_fixture_state.project_drift_claims(answer)

    assert projected == [
        {
            "subject": "service:order-service",
            "target": "LegacyPricingService",
            "via": "LegacyPricingService",
            "qualification": "OBSERVED_ONLY",
            "evidence_refs": ["evidence:otel:demo:1"],
        },
        {
            "subject": "service:order-service",
            "target": "unused-q",
            "via": "unused-q",
            "qualification": "NOT_OBSERVED_IN_WINDOW",
            "evidence_refs": ["evidence:asyncapi:order-service"],
        },
    ]
