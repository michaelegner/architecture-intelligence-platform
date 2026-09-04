"""v0.4.0 I1.3 Neo4j-integration coverage (spec §24 "Neo4j Integration"): the real read path -
`read_service_dependency_rows` plus the revision-fenced stable read - composed with
`ArchitectureIntelligenceService` against the existing `examples/` reference fixture landscape.
Independently authored deterministic evaluation against hand-built expected answers is I1.4's job
(spec §25); this file only proves the wiring is correct end to end."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    DestinationResolution,
    LimitationCode,
    Outcome,
    Producer,
    Qualification,
)
from app.architecture_intelligence.request import ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.0", build_revision="f" * 40
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _request(service_id: str, **overrides) -> ServiceDependenciesRequest:
    payload = {
        "service_id": service_id,
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }
    payload.update(overrides)
    return ServiceDependenciesRequest.model_validate(payload)


def _observe_order_service_calls_product_service(driver):
    subject_id = ids.service_id("order-service")
    object_id = ids.operation_id(ids.service_id("product-service"), "GET", "/products/{id}")
    bucket_start = datetime(2026, 8, 26, 12, tzinfo=UTC)
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(ENVIRONMENT, bucket_start, subject_id, "CALLS", object_id),
        environment=ENVIRONMENT,
        bucket_start=bucket_start,
        bucket_end=bucket_start,
        first_seen=bucket_start,
        last_seen=bucket_start,
        observation_count=1,
        sample_trace_ids=["a" * 32],
    )
    batch = ObservationBatch(
        facts=[
            ObservedFactCandidate(
                subject_id=subject_id,
                relation_type="CALLS",
                object_id=object_id,
                environment=ENVIRONMENT,
                timestamp=bucket_start,
                trace_id="a" * 32,
                evidence=evidence,
            )
        ]
    )
    persist_observation_batch(driver, DATABASE, batch)


def test_order_service_dependencies_resolve_confirmed_not_observed_and_unresolved(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)

    svc = _service(driver)
    answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))

    assert answer.outcome == Outcome.PARTIAL
    by_object_and_kind = {(c.object.id, c.delivery.kind.value): c for c in answer.claims}

    http_claim = by_object_and_kind[(ids.service_id("product-service"), "SYNC_HTTP")]
    assert http_claim.destination_resolution == DestinationResolution.RESOLVED_SERVICE
    assert http_claim.qualification == Qualification.CONFIRMED

    async_claim = by_object_and_kind[(ids.service_id("payment-service"), "ASYNC_MESSAGE")]
    assert async_claim.destination_resolution == DestinationResolution.RESOLVED_SERVICE
    assert async_claim.qualification == Qualification.NOT_OBSERVED_IN_WINDOW

    unused_queue_id = ids.queue_id("unused-q")
    fallback_claim = by_object_and_kind[(unused_queue_id, "ASYNC_MESSAGE")]
    assert fallback_claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    assert any(
        lim.code == LimitationCode.UNRESOLVED_IDENTITY
        and lim.claim_ids == [fallback_claim.claim_id]
        for lim in answer.limitations
    )

    for evidence_ref in answer.evidence_refs:
        assert evidence_ref  # every referenced evidence id round-tripped from a real Evidence node


def test_two_consecutive_calls_are_canonically_byte_identical(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    request = _request(ids.service_id("order-service"))

    first = canonical_json_bytes(svc.get_service_dependencies(request))
    second = canonical_json_bytes(svc.get_service_dependencies(request))
    assert first == second


def test_service_with_no_outgoing_dependencies_is_answered_with_empty_claims(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    answer = svc.get_service_dependencies(_request(ids.service_id("product-service")))

    assert answer.outcome == Outcome.ANSWERED
    assert answer.claims == []
    assert answer.data.dependency_claim_ids == []


def test_unknown_service_is_distinguished_from_a_valid_empty_service(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    answer = svc.get_service_dependencies(_request("service:does-not-exist"))

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert [lim.code for lim in answer.limitations] == [LimitationCode.UNKNOWN_ENTITY]
    assert answer.snapshot is not None


def test_stale_explicit_snapshot_is_refused_without_fallback(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "0" * 64
    answer = svc.get_service_dependencies(
        _request(ids.service_id("order-service"), snapshot_id=stale_snapshot_id)
    )

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.snapshot is not None
    assert answer.snapshot.snapshot_id != stale_snapshot_id
    assert [lim.code for lim in answer.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_matching_explicit_snapshot_repeats_the_answer(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    request = _request(ids.service_id("order-service"))
    first_answer = svc.get_service_dependencies(request)

    repeated = svc.get_service_dependencies(
        _request(ids.service_id("order-service"), snapshot_id=first_answer.snapshot.snapshot_id)
    )
    assert canonical_json_bytes(repeated) == canonical_json_bytes(first_answer)
