from datetime import UTC, datetime

import pytest

from app.analysis.runtime import ServiceTelemetryCoverage
from app.architecture_intelligence import dependency_projection as proj
from app.architecture_intelligence.contracts import (
    Coverage,
    DeliveryKind,
    DependencyClaim,
    DependencyPredicate,
    DestinationResolution,
    EntityRef,
    EntityType,
    LimitationCode,
    Qualification,
)

ENVIRONMENT = "demo"
WINDOW_START = datetime(2026, 8, 26, tzinfo=UTC)
WINDOW_END = datetime(2026, 8, 27, tzinfo=UTC)
INSIDE_WINDOW = datetime(2026, 8, 26, 12, tzinfo=UTC)
OUTSIDE_WINDOW = datetime(2026, 8, 28, tzinfo=UTC)


def _declared(eid: str) -> dict:
    return {eid: {"evidence_type": "DECLARED", "environment": None, "last_seen": None}}


def _observed(
    eid: str, *, environment: str = ENVIRONMENT, last_seen: datetime = INSIDE_WINDOW
) -> dict:
    return {eid: {"evidence_type": "OBSERVED", "environment": environment, "last_seen": last_seen}}


def _coverage(*, http=False, messaging=False) -> ServiceTelemetryCoverage:
    return ServiceTelemetryCoverage(
        service_id="service:order-service",
        service_name="OrderService",
        environment=ENVIRONMENT,
        since=WINDOW_START,
        http_observed=http,
        messaging_observed=messaging,
        spans_observed=http or messaging,
    )


def _project(rows: dict, *, coverage_enabled: bool = True) -> proj.ProjectionResult:
    base_rows = {
        "calls": [],
        "provides": [],
        "sends": [],
        "receives": [],
        "evidence": {},
        "coverage": _coverage(),
    }
    base_rows.update(rows)
    return proj.project_service_dependencies(
        base_rows,
        service_id="service:order-service",
        service_name="OrderService",
        environment=ENVIRONMENT,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        coverage_enabled=coverage_enabled,
    )


# --- Synchronous dependencies (spec §23 "Synchronous Dependencies") ----------------------------


def test_one_call_with_one_evidenced_provider_resolves_service_destination():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/products/{id}",
                    "evidence_ids": ["e1", "e2"],
                }
            ],
            "provides": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "provider_id": "service:product-service",
                    "provider_name": "ProductService",
                    "evidence_ids": ["e3"],
                }
            ],
            "evidence": {**_declared("e1"), **_observed("e2"), **_declared("e3")},
        }
    )
    assert result.limitations == []
    [claim] = result.claims
    assert claim.destination_resolution == DestinationResolution.RESOLVED_SERVICE
    assert claim.object == EntityRef(
        id="service:product-service", type=EntityType.SERVICE, name="ProductService"
    )
    assert claim.qualification == Qualification.CONFIRMED
    assert claim.evidence_refs == ["e1", "e2"]
    assert claim.resolution_evidence_refs == ["e3"]


def test_operation_without_provider_stays_operation_with_unresolved_identity():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:internal:GET:/internal/reconcile",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/internal/reconcile",
                    "evidence_ids": ["e1"],
                }
            ],
            "evidence": _declared("e1"),
        }
    )
    [claim] = result.claims
    assert claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    assert claim.object.type == EntityType.OPERATION
    assert claim.object.id == "operation:internal:GET:/internal/reconcile"
    assert claim.resolution_evidence_refs == []
    [limitation] = result.limitations
    assert limitation.code == LimitationCode.UNRESOLVED_IDENTITY
    assert limitation.claim_ids == [claim.claim_id]


def test_multiple_evidenced_providers_are_not_guessed():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/products/{id}",
                    "evidence_ids": ["e1"],
                }
            ],
            "provides": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "provider_id": "service:product-service",
                    "provider_name": "ProductService",
                    "evidence_ids": ["e2"],
                },
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "provider_id": "service:legacy-product-service",
                    "provider_name": "LegacyProductService",
                    "evidence_ids": ["e3"],
                },
            ],
            "evidence": {**_declared("e1"), **_declared("e2"), **_declared("e3")},
        }
    )
    [claim] = result.claims
    assert claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    assert claim.object.type == EntityType.OPERATION
    [limitation] = result.limitations
    assert limitation.code == LimitationCode.UNRESOLVED_IDENTITY


def test_an_evidenceless_provides_relation_does_not_count_as_a_supported_provider():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/products/{id}",
                    "evidence_ids": ["e1"],
                }
            ],
            "provides": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "provider_id": "service:product-service",
                    "provider_name": "ProductService",
                    "evidence_ids": [],
                }
            ],
            "evidence": _declared("e1"),
        }
    )
    [claim] = result.claims
    assert claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK


def test_two_operations_to_one_service_remain_two_delivery_claims():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/products/{id}",
                    "evidence_ids": ["e1"],
                },
                {
                    "operation_id": "operation:product-service:GET:/products",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/products",
                    "evidence_ids": ["e2"],
                },
            ],
            "provides": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "provider_id": "service:product-service",
                    "provider_name": "ProductService",
                    "evidence_ids": ["e3"],
                },
                {
                    "operation_id": "operation:product-service:GET:/products",
                    "provider_id": "service:product-service",
                    "provider_name": "ProductService",
                    "evidence_ids": ["e4"],
                },
            ],
            "evidence": {
                **_declared("e1"),
                **_declared("e2"),
                **_declared("e3"),
                **_declared("e4"),
            },
        }
    )
    assert len(result.claims) == 2
    assert result.claims[0].claim_id != result.claims[1].claim_id
    assert {c.object.id for c in result.claims} == {"service:product-service"}


# --- Asynchronous dependencies (spec §23 "Asynchronous Dependencies") --------------------------


def test_one_sender_one_consumer_resolves_service_destination_through_a_queue():
    result = _project(
        {
            "sends": [
                {
                    "queue_id": "queue:asb:commerce:payment-q",
                    "queue_name": "payment-q",
                    "protocol": "amqp",
                    "namespace": "commerce",
                    "evidence_ids": ["e1"],
                }
            ],
            "receives": [
                {
                    "queue_id": "queue:asb:commerce:payment-q",
                    "consumer_id": "service:payment-service",
                    "consumer_name": "PaymentService",
                    "evidence_ids": ["e2"],
                }
            ],
            "evidence": {**_declared("e1"), **_declared("e2")},
        }
    )
    [claim] = result.claims
    assert claim.destination_resolution == DestinationResolution.RESOLVED_SERVICE
    assert claim.object.id == "service:payment-service"
    assert claim.delivery.kind == DeliveryKind.ASYNC_MESSAGE
    assert result.limitations == []


def test_one_queue_with_two_consumers_yields_two_claims():
    result = _project(
        {
            "sends": [
                {
                    "queue_id": "queue:asb:commerce:payment-q",
                    "queue_name": "payment-q",
                    "protocol": "amqp",
                    "namespace": "commerce",
                    "evidence_ids": ["e1"],
                }
            ],
            "receives": [
                {
                    "queue_id": "queue:asb:commerce:payment-q",
                    "consumer_id": "service:payment-service",
                    "consumer_name": "PaymentService",
                    "evidence_ids": ["e2"],
                },
                {
                    "queue_id": "queue:asb:commerce:payment-q",
                    "consumer_id": "service:audit-service",
                    "consumer_name": "AuditService",
                    "evidence_ids": ["e3"],
                },
            ],
            "evidence": {**_declared("e1"), **_declared("e2"), **_declared("e3")},
        }
    )
    assert result.limitations == []
    assert {c.object.id for c in result.claims} == {
        "service:payment-service",
        "service:audit-service",
    }
    assert len({c.claim_id for c in result.claims}) == 2


def test_queue_without_a_consumer_remains_a_queue_with_unresolved_identity():
    result = _project(
        {
            "sends": [
                {
                    "queue_id": "queue:asb:commerce:unused-q",
                    "queue_name": "unused-q",
                    "protocol": "amqp",
                    "namespace": "commerce",
                    "evidence_ids": ["e1"],
                }
            ],
            "evidence": _declared("e1"),
        }
    )
    [claim] = result.claims
    assert claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    assert claim.object.type == EntityType.QUEUE
    assert claim.object.id == "queue:asb:commerce:unused-q"
    [limitation] = result.limitations
    assert limitation.code == LimitationCode.UNRESOLVED_IDENTITY


def test_sync_and_async_paths_to_the_same_service_both_survive():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/products/{id}",
                    "evidence_ids": ["e1"],
                }
            ],
            "provides": [
                {
                    "operation_id": "operation:product-service:GET:/products/{id}",
                    "provider_id": "service:product-service",
                    "provider_name": "ProductService",
                    "evidence_ids": ["e2"],
                }
            ],
            "sends": [
                {
                    "queue_id": "queue:asb:commerce:product-events-q",
                    "queue_name": "product-events-q",
                    "protocol": "amqp",
                    "namespace": "commerce",
                    "evidence_ids": ["e3"],
                }
            ],
            "receives": [
                {
                    "queue_id": "queue:asb:commerce:product-events-q",
                    "consumer_id": "service:product-service",
                    "consumer_name": "ProductService",
                    "evidence_ids": ["e4"],
                }
            ],
            "evidence": {
                **_declared("e1"),
                **_declared("e2"),
                **_declared("e3"),
                **_declared("e4"),
            },
        }
    )
    assert {c.object.id for c in result.claims} == {"service:product-service"}
    assert {c.delivery.kind for c in result.claims} == {
        DeliveryKind.SYNC_HTTP,
        DeliveryKind.ASYNC_MESSAGE,
    }
    assert len({c.claim_id for c in result.claims}) == 2


# --- Qualification and evidence (spec §23 "Qualification and Evidence") -----------------------


def test_declared_plus_matching_observed_yields_confirmed_with_both_evidence_classes():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["e1", "e2"],
                }
            ],
            "evidence": {**_declared("e1"), **_observed("e2")},
        }
    )
    [claim] = result.claims
    assert claim.qualification == Qualification.CONFIRMED
    assert claim.coverage is None
    assert claim.evidence_refs == ["e1", "e2"]


def test_matching_observed_only_yields_observed_only():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["e1"],
                }
            ],
            "evidence": _observed("e1"),
        }
    )
    [claim] = result.claims
    assert claim.qualification == Qualification.OBSERVED_ONLY
    assert claim.coverage is None
    assert claim.evidence_refs == ["e1"]


def test_declared_without_matching_observation_yields_not_observed_in_window_with_coverage():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["e1"],
                }
            ],
            "evidence": _declared("e1"),
            "coverage": _coverage(http=True),
        }
    )
    [claim] = result.claims
    assert claim.qualification == Qualification.NOT_OBSERVED_IN_WINDOW
    assert claim.coverage == Coverage.SUFFICIENT
    assert claim.evidence_refs == ["e1"]


@pytest.mark.parametrize(
    ("http_observed", "spans_observed", "expected"),
    [
        (True, True, Coverage.SUFFICIENT),
        (False, True, Coverage.PARTIAL),
        (False, False, Coverage.NONE),
    ],
)
def test_not_observed_in_window_coverage_classification(http_observed, spans_observed, expected):
    coverage = ServiceTelemetryCoverage(
        service_id="s",
        service_name="S",
        environment=ENVIRONMENT,
        since=WINDOW_START,
        http_observed=http_observed,
        messaging_observed=False,
        spans_observed=spans_observed,
    )
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["e1"],
                }
            ],
            "evidence": _declared("e1"),
            "coverage": coverage,
        }
    )
    assert result.claims[0].coverage == expected


def test_coverage_is_unknown_when_qualification_is_disabled():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["e1"],
                }
            ],
            "evidence": _declared("e1"),
            "coverage": _coverage(http=True),
        },
        coverage_enabled=False,
    )
    assert result.claims[0].coverage == Coverage.UNKNOWN


def test_observation_from_another_environment_does_not_qualify():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["e1", "e2"],
                }
            ],
            "evidence": {**_declared("e1"), **_observed("e2", environment="staging")},
        }
    )
    [claim] = result.claims
    assert claim.qualification == Qualification.NOT_OBSERVED_IN_WINDOW
    assert claim.evidence_refs == ["e1"]


def test_observation_outside_window_does_not_qualify():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["e1", "e2"],
                }
            ],
            "evidence": {**_declared("e1"), **_observed("e2", last_seen=OUTSIDE_WINDOW)},
        }
    )
    [claim] = result.claims
    assert claim.qualification == Qualification.NOT_OBSERVED_IN_WINDOW
    assert claim.evidence_refs == ["e1"]


def test_missing_evidence_cannot_create_a_claim():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": [],
                }
            ],
        }
    )
    assert result.claims == []
    [limitation] = result.limitations
    assert limitation.code == LimitationCode.INSUFFICIENT_EVIDENCE
    assert limitation.claim_ids == []


def test_evidence_id_referencing_a_row_absent_from_the_evidence_map_cannot_qualify():
    result = _project(
        {
            "calls": [
                {
                    "operation_id": "operation:x:GET:/x",
                    "operation_name": None,
                    "method": "GET",
                    "path": "/x",
                    "evidence_ids": ["ghost"],
                }
            ],
            "evidence": {},
        }
    )
    assert result.claims == []
    assert result.limitations[0].code == LimitationCode.INSUFFICIENT_EVIDENCE


# --- Claim identity and determinism -------------------------------------------------------------


def test_claim_id_is_stable_for_identical_inputs():
    first = proj.compute_claim_id(
        subject_id="service:a",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:b",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:b:GET:/x",
    )
    second = proj.compute_claim_id(
        subject_id="service:a",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:b",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:b:GET:/x",
    )
    assert first == second
    assert first.startswith("aip:claim:v1:")


def test_claim_id_changes_when_resolved_object_changes():
    fallback_id = proj.compute_claim_id(
        subject_id="service:a",
        predicate="DIRECT_DEPENDENCY",
        object_id="operation:b:GET:/x",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:b:GET:/x",
    )
    resolved_id = proj.compute_claim_id(
        subject_id="service:a",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:b",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:b:GET:/x",
    )
    assert fallback_id != resolved_id


def _minimal_claim(
    claim_id: str, evidence_refs: list[str], resolution_evidence_refs: list[str]
) -> DependencyClaim:
    entity = EntityRef(id="service:a", type=EntityType.SERVICE, name="A")
    from app.architecture_intelligence.contracts import DeliveryRef, DeliveryRelationType

    return DependencyClaim(
        claim_id=claim_id,
        subject=entity,
        predicate=DependencyPredicate.DIRECT_DEPENDENCY,
        object=EntityRef(id="service:b", type=EntityType.SERVICE, name="B"),
        destination_resolution=DestinationResolution.RESOLVED_SERVICE,
        delivery=DeliveryRef(
            kind=DeliveryKind.SYNC_HTTP,
            relation_type=DeliveryRelationType.CALLS,
            via=EntityRef(
                id="operation:b:GET:/x",
                type=EntityType.OPERATION,
                name="GET /x",
                method="GET",
                path="/x",
            ),
        ),
        qualification=Qualification.CONFIRMED,
        coverage=None,
        evidence_refs=evidence_refs,
        resolution_evidence_refs=resolution_evidence_refs,
    )


def test_merge_duplicate_claims_unions_and_sorts_evidence():
    claim_id = "aip:claim:v1:" + "0" * 64
    first = _minimal_claim(claim_id, ["e2"], ["r1"])
    second = _minimal_claim(claim_id, ["e1"], ["r2"])
    [merged] = proj._merge_duplicate_claims([first, second])
    assert merged.evidence_refs == ["e1", "e2"]
    assert merged.resolution_evidence_refs == ["r1", "r2"]


def test_merge_duplicate_claims_leaves_distinct_claims_untouched():
    first = _minimal_claim("aip:claim:v1:" + "1" * 64, ["e1"], ["r1"])
    second = _minimal_claim("aip:claim:v1:" + "2" * 64, ["e2"], ["r2"])
    merged = proj._merge_duplicate_claims([first, second])
    assert {c.claim_id for c in merged} == {first.claim_id, second.claim_id}
