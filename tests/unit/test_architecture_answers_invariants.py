"""Isolated, stub-service unit tests for `evaluation.architecture_answers.invariants` (I3 spec
§33.1-§33.3).

Deliberately not a real-Neo4j test: proving these two checks fire *specifically because of a real
implementation bug*, rather than because a scenario's own frozen `expected_answer.json` happens to
disagree with reality, is hard to isolate against a live suite - the ordinary per-scenario
comparator already independently catches almost any real regression against a hand-authored
scenario. A stub service lets each test construct a drift answer and a *deliberately inconsistent*
live dependency/evidence answer directly, proving `check_drift_invariants` itself correctly detects
disagreement - independent of whether any scenario's own fixture would also happen to catch it.

Both checks run together inside `check_drift_invariants` (the module's only public entry point), so
every test configures a passing stand-in for whichever half it isn't exercising, and asserts on
`invariant` to isolate the one failure it's proving.
"""

from __future__ import annotations

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    Coverage,
    DeliveryKind,
    DeliveryRef,
    DeliveryRelationType,
    DependencyClaim,
    DependencyPredicate,
    DestinationResolution,
    EntityRef,
    EntityType,
    EvidenceData,
    Outcome,
    Producer,
    Qualification,
    ServiceDependenciesData,
    SnapshotRef,
)
from app.architecture_intelligence.request import EvidenceRequest, ServiceDependenciesRequest
from evaluation.architecture_answers.invariants import check_drift_invariants

_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.0", build_revision="f" * 40
)
_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_CONTEXT = {
    "context_id": "aip:observation-context:v1:" + "b" * 64,
    "environment": "test",
    "window_start": "2026-08-26T00:00:00.000000Z",
    "window_end": "2026-08-27T00:00:00.000000Z",
}
_SUBJECT = EntityRef(id="service:order-service", type=EntityType.SERVICE, name="OrderService")
_PROVIDER = EntityRef(id="service:product-service", type=EntityType.SERVICE, name="ProductService")
_OPERATION = EntityRef(
    id="operation:service:product-service:GET:/products/{id}",
    type=EntityType.OPERATION,
    name="GET /products/{id}",
    method="GET",
    path="/products/{id}",
)


def _claim(**overrides) -> DependencyClaim:
    fields = {
        "claim_id": "aip:claim:v1:" + "d" * 64,
        "subject": _SUBJECT,
        "predicate": DependencyPredicate.DIRECT_DEPENDENCY,
        "object": _PROVIDER,
        "destination_resolution": DestinationResolution.RESOLVED_SERVICE,
        "delivery": DeliveryRef(
            kind=DeliveryKind.SYNC_HTTP, relation_type=DeliveryRelationType.CALLS, via=_OPERATION
        ),
        "qualification": Qualification.NOT_OBSERVED_IN_WINDOW,
        "coverage": Coverage.SUFFICIENT,
        "evidence_refs": ["evidence:declared:" + "e" * 64],
        "resolution_evidence_refs": ["evidence:declared:" + "f" * 64],
    }
    fields.update(overrides)
    return DependencyClaim(**fields)


def _drift_answer(*, claims: list[DependencyClaim]) -> ArchitectureAnswer[ArchitectureDriftData]:
    evidence_refs = sorted(
        {ref for c in claims for ref in (*c.evidence_refs, *c.resolution_evidence_refs)}
    )
    return ArchitectureAnswer[ArchitectureDriftData](
        schema_version="0.4",
        producer=_PRODUCER,
        tool="get_architecture_drift",
        outcome=Outcome.ANSWERED,
        snapshot=_SNAPSHOT,
        observation_context=_CONTEXT,
        data=ArchitectureDriftData(service=_SUBJECT, drift_claim_ids=[c.claim_id for c in claims]),
        claims=claims,
        evidence_refs=evidence_refs,
        limitations=[],
    )


def _dependency_answer(
    *, claims: list[DependencyClaim]
) -> ArchitectureAnswer[ServiceDependenciesData]:
    evidence_refs = sorted(
        {ref for c in claims for ref in (*c.evidence_refs, *c.resolution_evidence_refs)}
    )
    return ArchitectureAnswer[ServiceDependenciesData](
        schema_version="0.4",
        producer=_PRODUCER,
        tool="get_service_dependencies",
        outcome=Outcome.ANSWERED,
        snapshot=_SNAPSHOT,
        observation_context=_CONTEXT,
        data=ServiceDependenciesData(
            service=_SUBJECT, dependency_claim_ids=[c.claim_id for c in claims]
        ),
        claims=claims,
        evidence_refs=evidence_refs,
        limitations=[],
    )


def _evidence_answer(*, missing: list[str]) -> ArchitectureAnswer[EvidenceData]:
    """Only `data.missing_evidence_refs` matters to `check_drift_invariants` - `requested_evidence_
    refs` is set equal to it (trivially satisfying `EvidenceData`'s own partition invariant, since
    `records` stays empty), not to some independently realistic request list."""
    return ArchitectureAnswer[EvidenceData](
        schema_version="0.4",
        producer=_PRODUCER,
        tool="get_evidence",
        outcome=Outcome.ANSWERED if not missing else Outcome.PARTIAL,
        snapshot=_SNAPSHOT,
        observation_context=None,
        data=EvidenceData(
            requested_evidence_refs=sorted(missing), records=[], missing_evidence_refs=missing
        ),
        claims=[],
        evidence_refs=[],
        limitations=(
            []
            if not missing
            else [
                {
                    "code": "INSUFFICIENT_EVIDENCE",
                    "message": f"{len(missing)} of {len(missing)} requested evidence refs "
                    "could not be resolved",
                    "claim_ids": [],
                }
            ]
        ),
    )


class _StubService:
    """Duck-typed stand-in for `ArchitectureIntelligenceService` - records the request it was
    called with so tests can also assert the invariant pinned the right snapshot/service/context
    rather than querying something else."""

    def __init__(self, *, dependency_answer=None, evidence_answer=None):
        self._dependency_answer = dependency_answer
        self._evidence_answer = evidence_answer
        self.received_dependency_request: ServiceDependenciesRequest | None = None
        self.received_evidence_request: EvidenceRequest | None = None

    def get_service_dependencies(self, request: ServiceDependenciesRequest):
        self.received_dependency_request = request
        return self._dependency_answer

    def get_evidence(self, request: EvidenceRequest):
        self.received_evidence_request = request
        return self._evidence_answer


def test_a_fully_consistent_drift_answer_passes_both_invariants():
    confirmed = _claim(
        claim_id="aip:claim:v1:" + "1" * 64, qualification=Qualification.CONFIRMED, coverage=None
    )
    drifting = _claim(claim_id="aip:claim:v1:" + "2" * 64)
    drift_answer = _drift_answer(claims=[drifting])
    service = _StubService(
        dependency_answer=_dependency_answer(claims=[confirmed, drifting]),
        evidence_answer=_evidence_answer(missing=[]),
    )

    failures = check_drift_invariants(drift_answer, service=service)

    assert failures == []
    assert service.received_dependency_request.service_id == "service:order-service"
    assert service.received_dependency_request.snapshot_id == _SNAPSHOT.snapshot_id
    assert service.received_evidence_request.snapshot_id == _SNAPSHOT.snapshot_id


def test_non_drift_answer_is_a_no_op():
    """Neither check applies to a get_service_dependencies/get_evidence answer - only
    get_architecture_drift answers carry this invariant."""
    dependency_answer = _dependency_answer(claims=[_claim()])
    service = _StubService()

    failures = check_drift_invariants(dependency_answer, service=service)

    assert failures == []
    assert service.received_dependency_request is None
    assert service.received_evidence_request is None


def test_drift_answer_missing_a_claim_the_live_filter_would_include_is_caught():
    """The exact regression class §33.1 exists for: the drift tool's own answer silently drops a
    claim that filtering a live dependency call would have kept."""
    drifting = _claim()
    drift_answer = _drift_answer(claims=[])  # wrongly claims to have found no drift
    service = _StubService(
        # ...even though the live dependency answer has one NOT_OBSERVED_IN_WINDOW claim, which the
        # real filter would have kept.
        dependency_answer=_dependency_answer(claims=[drifting]),
        evidence_answer=_evidence_answer(missing=[]),
    )

    failures = check_drift_invariants(drift_answer, service=service)

    assert [f.invariant for f in failures] == ["dependency_to_drift"]


def test_refusal_drift_answer_skips_the_dependency_check():
    """A drift refusal (`data is None`) names no service to compare against."""
    refusal = ArchitectureAnswer[ArchitectureDriftData](
        schema_version="0.4",
        producer=_PRODUCER,
        tool="get_architecture_drift",
        outcome=Outcome.NOT_ANSWERED,
        snapshot=_SNAPSHOT,
        observation_context=None,
        data=None,
        claims=[],
        evidence_refs=[],
        limitations=[{"code": "OBSERVATION_CONTEXT_REQUIRED", "message": "x", "claim_ids": []}],
    )
    service = _StubService()

    failures = check_drift_invariants(refusal, service=service)

    assert failures == []
    assert service.received_dependency_request is None
    assert service.received_evidence_request is None


def test_a_drift_evidence_ref_that_does_not_resolve_is_caught():
    """The exact regression class §33.3 exists for: a drift answer names an evidence ref that does
    not actually resolve through get_evidence at its own snapshot."""
    drifting = _claim()
    drift_answer = _drift_answer(claims=[drifting])
    missing_ref = min(drift_answer.evidence_refs)
    service = _StubService(
        dependency_answer=_dependency_answer(claims=[drifting]),
        evidence_answer=_evidence_answer(missing=[missing_ref]),
    )

    failures = check_drift_invariants(drift_answer, service=service)

    assert [f.invariant for f in failures] == ["drift_to_evidence"]


def test_drift_answer_with_no_evidence_refs_skips_the_evidence_check():
    drift_answer = _drift_answer(claims=[])
    service = _StubService(dependency_answer=_dependency_answer(claims=[]), evidence_answer=None)

    failures = check_drift_invariants(drift_answer, service=service)

    assert failures == []
    assert service.received_evidence_request is None
