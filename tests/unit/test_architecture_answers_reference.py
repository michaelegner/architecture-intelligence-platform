"""Cross-checks the evaluator-owned reference implementation (authoring-time only, never imported
by the live loader/runner/comparator) against the real production functions it must independently
agree with - not because the live path calls it, but because a scenario author trusts its printed
literals when freezing expected_answer.json (I1.4 review finding #1)."""

from datetime import UTC, datetime

from app.architecture_intelligence import observation_context as real_observation_context
from app.architecture_intelligence.dependency_projection import compute_claim_id as real_claim_id
from app.canonical import ids as real_ids
from evaluation.architecture_answers.reference import canonical_json, identities

_ENVIRONMENT = "test"
_WINDOW_START = datetime(2026, 8, 26, tzinfo=UTC)
_WINDOW_END = datetime(2026, 8, 27, tzinfo=UTC)


def test_context_id_matches_the_real_implementation():
    real = real_observation_context.compute_context_id(_ENVIRONMENT, _WINDOW_START, _WINDOW_END)
    reference = identities.context_id(
        environment=_ENVIRONMENT, window_start=_WINDOW_START, window_end=_WINDOW_END
    )
    assert reference == real


def test_declared_evidence_id_matches_the_real_implementation():
    assert identities.declared_evidence_id("OPENAPI", "product-service") == real_ids.evidence_id(
        "OPENAPI", "product-service"
    )
    assert identities.declared_evidence_id(
        "MANIFEST", "order-service", "rev1"
    ) == real_ids.evidence_id("MANIFEST", "order-service", "rev1")


def test_observed_evidence_id_matches_the_real_implementation():
    bucket_start = datetime(2026, 8, 26, tzinfo=UTC)
    real = real_ids.observed_evidence_id(
        "test", bucket_start, "service:order-service", "CALLS", "operation:x:GET:/x"
    )
    reference = identities.observed_evidence_id(
        environment="test",
        bucket_start=bucket_start,
        subject_id="service:order-service",
        relation_type="CALLS",
        object_id="operation:x:GET:/x",
    )
    assert reference == real


def test_claim_id_matches_the_real_implementation():
    real = real_claim_id(
        subject_id="service:order-service",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:product-service",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:product-service:GET:/products/{id}",
    )
    reference = identities.claim_id(
        subject_id="service:order-service",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:product-service",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:product-service:GET:/products/{id}",
    )
    assert reference == real


def test_canonical_json_bytes_sorts_keys_and_formats_utc_timestamps():
    payload = {"b": 1, "a": datetime(2026, 8, 26, 12, 30, tzinfo=UTC)}
    encoded = canonical_json.canonical_json_bytes(payload).decode()
    assert encoded == '{"a":"2026-08-26T12:30:00.000000Z","b":1}'
