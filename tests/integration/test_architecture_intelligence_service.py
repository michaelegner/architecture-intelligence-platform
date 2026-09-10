"""v0.4.0 I1.3 Neo4j-integration coverage (spec §24 "Neo4j Integration"): the real read path -
`read_service_dependency_rows` plus the revision-fenced stable read - composed with
`ArchitectureIntelligenceService` against the existing `examples/` reference fixture landscape.
Independently authored deterministic evaluation against hand-built expected answers is I1.4's job
(spec §25); this file only proves the wiring is correct end to end."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.architecture_intelligence import service as service_module
from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    DestinationResolution,
    LimitationCode,
    Outcome,
    Producer,
    Qualification,
)
from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.graph.revision_fence import bump_revision, read_revision
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.1", build_revision="f" * 40
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


def _fingerprint(driver) -> tuple[str, str]:
    with driver.session(database=DATABASE) as session:
        return snapshot_fingerprint(
            canonical_snapshot_state(session, coverage_qualification_enabled=True)
        )


def test_service_call_performs_zero_graph_writes(driver, monkeypatch):
    """Proven three ways (I1.4 review): the service actually asks for a READ_ACCESS session (Neo4j's
    own access-mode enforcement is a routing hint on a standalone instance, not something this test
    can rely on), the internal revision fence is untouched, and the full canonical fingerprint is
    untouched - a write that incorrectly skipped bump_revision() but touched other state would still
    fail the fingerprint check."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)

    captured_read_only = []
    real_open_session = service_module.open_session

    def spy_open_session(drv, *, database, read_only=False):
        captured_read_only.append(read_only)
        return real_open_session(drv, database=database, read_only=read_only)

    monkeypatch.setattr(service_module, "open_session", spy_open_session)

    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)
    fingerprint_before = _fingerprint(driver)

    svc = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    svc.get_service_dependencies(_request(ids.service_id("order-service")))

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    fingerprint_after = _fingerprint(driver)

    assert captured_read_only == [True]
    assert revision_after == revision_before
    assert fingerprint_after == fingerprint_before


def test_a_concurrent_write_during_the_stable_read_forces_a_retry_through_the_real_service_path(
    driver, monkeypatch
):
    """The concurrent-write retry must be proven through ArchitectureIntelligenceService itself, not
    just app.architecture_intelligence.repository.read_stable_snapshot_from_session directly (I1.4
    review) - a real write is injected from inside the service's own read_extra callback (not a
    thread race, so this is deterministic, not flaky) and the final answer must reflect only the
    post-write state, never a mix.

    The injected write mutates a real canonical field (product-service's declared version) in the
    same transaction as the revision bump, not just the revision alone (I1.4 review, non-blocking
    strengthening) - a revision-only bump can't actually produce a semantically mixed read to
    discard, since revision isn't part of the canonical fingerprint itself. Mutating a real
    allowlisted field is what makes the final fingerprint assertion below meaningfully prove no
    stale-field/bumped-revision mix was ever accepted."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)

    real_read_rows = service_module.read_service_dependency_rows
    calls = {"count": 0}

    def _mutate_and_bump(tx):
        tx.run(
            "MATCH (s:Service {id: $id}) SET s.version = $version",
            id=ids.service_id("product-service"),
            version="mutated-mid-read",
        )
        bump_revision(tx)

    def flaky_read_rows(session, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            with driver.session(database=DATABASE) as write_session:
                write_session.execute_write(_mutate_and_bump)
        return real_read_rows(session, **kwargs)

    monkeypatch.setattr(service_module, "read_service_dependency_rows", flaky_read_rows)

    svc = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))

    expected_snapshot_id, expected_model_revision = _fingerprint(driver)

    assert calls["count"] >= 2  # the first, mid-read-mutated attempt was discarded and retried
    assert answer.snapshot.snapshot_id == expected_snapshot_id
    assert answer.snapshot.model_revision == expected_model_revision


# --- I2.3: get_evidence --------------------------------------------------------------------------


def test_evidence_resolves_declared_observed_and_resolution_evidence_from_a_dependency_answer(
    driver,
):
    """spec §17 scenario 9: every qualification and resolution evidence referenced by a real
    dependency answer resolves using its own snapshot - this is the code-level vertical-slice proof
    (get_service_dependencies -> extract evidence_refs/snapshot_id -> get_evidence); the real
    independent-HTTP-client version of this chain is I2.4's job."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)

    svc = _service(driver)
    dependency_answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))
    http_claim = next(
        claim
        for claim in dependency_answer.claims
        if claim.object.id == ids.service_id("product-service")
        and claim.delivery.kind.value == "SYNC_HTTP"
    )
    assert http_claim.qualification == Qualification.CONFIRMED
    requested_ids = sorted(set(http_claim.evidence_refs) | set(http_claim.resolution_evidence_refs))
    assert len(requested_ids) >= 2  # at least one declared + one observed evidence id

    evidence_answer = svc.get_evidence(
        EvidenceRequest(
            evidence_refs=requested_ids, snapshot_id=dependency_answer.snapshot.snapshot_id
        )
    )

    assert evidence_answer.outcome == Outcome.ANSWERED
    assert evidence_answer.data.missing_evidence_refs == []
    assert {record.id for record in evidence_answer.data.records} == set(requested_ids)
    evidence_types = {record.evidence_type.value for record in evidence_answer.data.records}
    assert "DECLARED" in evidence_types
    assert "OBSERVED" in evidence_types
    for record in evidence_answer.data.records:
        assert record.supports  # every requested id genuinely supports at least one relation fact


def test_evidence_with_one_unknown_ref_yields_partial_insufficient_evidence(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    dependency_answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))
    known_id = min(dependency_answer.evidence_refs)
    unknown_id = "evidence:declared:does-not-exist"

    evidence_answer = svc.get_evidence(
        EvidenceRequest(
            evidence_refs=[known_id, unknown_id],
            snapshot_id=dependency_answer.snapshot.snapshot_id,
        )
    )

    assert evidence_answer.outcome == Outcome.PARTIAL
    assert evidence_answer.data.missing_evidence_refs == [unknown_id]
    assert [record.id for record in evidence_answer.data.records] == [known_id]
    assert [lim.code for lim in evidence_answer.limitations] == [
        LimitationCode.INSUFFICIENT_EVIDENCE
    ]


def test_evidence_with_all_unknown_refs_yields_not_answered_with_data_present(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    dependency_answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))

    evidence_answer = svc.get_evidence(
        EvidenceRequest(
            evidence_refs=["evidence:declared:does-not-exist"],
            snapshot_id=dependency_answer.snapshot.snapshot_id,
        )
    )

    assert evidence_answer.outcome == Outcome.NOT_ANSWERED
    assert evidence_answer.data is not None
    assert evidence_answer.data.records == []
    assert evidence_answer.data.missing_evidence_refs == ["evidence:declared:does-not-exist"]
    assert [lim.code for lim in evidence_answer.limitations] == [
        LimitationCode.INSUFFICIENT_EVIDENCE
    ]


def test_evidence_stale_explicit_snapshot_is_refused_without_fallback(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "0" * 64

    evidence_answer = svc.get_evidence(
        EvidenceRequest(
            evidence_refs=["evidence:declared:does-not-exist"], snapshot_id=stale_snapshot_id
        )
    )

    assert evidence_answer.outcome == Outcome.NOT_ANSWERED
    assert evidence_answer.data is None
    assert evidence_answer.snapshot is not None
    assert evidence_answer.snapshot.snapshot_id != stale_snapshot_id
    assert [lim.code for lim in evidence_answer.limitations] == [
        LimitationCode.SNAPSHOT_NOT_AVAILABLE
    ]


def test_evidence_two_consecutive_calls_are_canonically_byte_identical(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    dependency_answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))
    known_id = min(dependency_answer.evidence_refs)
    request = EvidenceRequest(
        evidence_refs=[known_id], snapshot_id=dependency_answer.snapshot.snapshot_id
    )

    first = canonical_json_bytes(svc.get_evidence(request))
    second = canonical_json_bytes(svc.get_evidence(request))
    assert first == second


def test_evidence_call_performs_zero_graph_writes(driver, monkeypatch):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    dependency_answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))
    known_id = min(dependency_answer.evidence_refs)

    captured_read_only = []
    real_open_session = service_module.open_session

    def spy_open_session(drv, *, database, read_only=False):
        captured_read_only.append(read_only)
        return real_open_session(drv, database=database, read_only=read_only)

    monkeypatch.setattr(service_module, "open_session", spy_open_session)

    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)
    fingerprint_before = _fingerprint(driver)

    svc.get_evidence(
        EvidenceRequest(
            evidence_refs=[known_id], snapshot_id=dependency_answer.snapshot.snapshot_id
        )
    )

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    fingerprint_after = _fingerprint(driver)

    assert captured_read_only == [True]
    assert revision_after == revision_before
    assert fingerprint_after == fingerprint_before


def test_a_concurrent_evidence_write_during_the_stable_read_forces_a_retry_and_a_safe_refusal(
    driver, monkeypatch
):
    """spec §17 scenario 19 ("Concurrent evidence writes force retry or safe refusal, never a mixed
    response"), the get_evidence counterpart to the dependency-side proof above (PR #80 review
    finding: neither the dependency-side test - which mutates a Service version - nor the unit-level
    instability test, which substitutes an exception for the stable read, exercises a concurrent
    mutation between the fingerprint projection and the requested-evidence read).

    The injected write mutates a real, *requested* Evidence node's own metadata in the same
    transaction as the revision bump - not a revision-counter bump alone, which could not produce a
    semantically mixed read to discard in the first place. The mutation lands between the attempt's
    fingerprint projection and its evidence read, so a missing fence would pair a pre-mutation
    snapshot_id with post-mutation evidence data. Because the caller pinned the pre-mutation
    snapshot, the only safe outcome after the retry is an explicit refusal bound to the *current*
    (post-mutation) snapshot, with no records returned."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    dependency_answer = svc.get_service_dependencies(_request(ids.service_id("order-service")))
    requested_id = min(dependency_answer.evidence_refs)
    pinned_snapshot_id = dependency_answer.snapshot.snapshot_id

    real_read_rows = service_module.read_evidence_rows
    calls = {"count": 0}

    def _mutate_requested_evidence_and_bump(tx):
        tx.run(
            "MATCH (e:Evidence {id: $id}) SET e.source_revision = $revision",
            id=requested_id,
            revision="mutated-mid-read",
        )
        bump_revision(tx)

    def flaky_read_rows(session, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            with driver.session(database=DATABASE) as write_session:
                write_session.execute_write(_mutate_requested_evidence_and_bump)
        return real_read_rows(session, **kwargs)

    monkeypatch.setattr(service_module, "read_evidence_rows", flaky_read_rows)

    evidence_answer = svc.get_evidence(
        EvidenceRequest(evidence_refs=[requested_id], snapshot_id=pinned_snapshot_id)
    )

    expected_snapshot_id, expected_model_revision = _fingerprint(driver)

    assert calls["count"] >= 2  # the first, mid-read-mutated attempt was discarded and retried
    assert evidence_answer.outcome == Outcome.NOT_ANSWERED
    assert evidence_answer.data is None  # no records escaped from the discarded mixed attempt
    assert [lim.code for lim in evidence_answer.limitations] == [
        LimitationCode.SNAPSHOT_NOT_AVAILABLE
    ]
    # The refusal is bound to the real post-mutation state, never the stale pre-mutation fingerprint
    # the caller pinned - proving the accepted attempt observed one committed state throughout.
    assert evidence_answer.snapshot.snapshot_id == expected_snapshot_id
    assert evidence_answer.snapshot.model_revision == expected_model_revision
    assert evidence_answer.snapshot.snapshot_id != pinned_snapshot_id


# --- I3.1: get_architecture_drift -----------------------------------------------------------------


def _drift_request(service_id: str, **overrides) -> ArchitectureDriftRequest:
    payload = {
        "service_id": service_id,
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }
    payload.update(overrides)
    return ArchitectureDriftRequest.model_validate(payload)


def test_drift_returns_only_discrepancy_qualified_claims_of_a_real_service(driver):
    """The `examples/` landscape gives OrderService one CONFIRMED sync dependency (observed below)
    alongside async dependencies with no matching observation - so the drift answer is exactly the
    dependency answer minus the CONFIRMED claim (I3 spec §7.1)."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)
    svc = _service(driver)

    dependencies = svc.get_service_dependencies(_request(ids.service_id("order-service")))
    drift = svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))

    assert drift.tool == "get_architecture_drift"
    assert {claim.qualification for claim in drift.claims} <= {
        Qualification.OBSERVED_ONLY,
        Qualification.NOT_OBSERVED_IN_WINDOW,
    }
    assert Qualification.CONFIRMED in {claim.qualification for claim in dependencies.claims}
    assert [claim.claim_id for claim in drift.claims] == [
        claim.claim_id
        for claim in dependencies.claims
        if claim.qualification != Qualification.CONFIRMED
    ]
    assert drift.data.drift_claim_ids == [claim.claim_id for claim in drift.claims]


def test_drift_not_observed_in_window_claims_carry_their_coverage_and_evidence(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)

    drift = svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))

    not_observed = [
        claim
        for claim in drift.claims
        if claim.qualification == Qualification.NOT_OBSERVED_IN_WINDOW
    ]
    assert not_observed
    for claim in not_observed:
        assert claim.coverage is not None
        assert claim.evidence_refs


def test_drift_observed_only_claim_appears_for_an_undeclared_observed_dependency(driver):
    """OBSERVED_ONLY is the "undocumented observed dependency" half of I3 spec §7.2: an observation
    of a call that the manifest never declared."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    subject_id = ids.service_id("invoice-service")
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
        sample_trace_ids=["b" * 32],
    )
    persist_observation_batch(
        driver,
        DATABASE,
        ObservationBatch(
            facts=[
                ObservedFactCandidate(
                    subject_id=subject_id,
                    relation_type="CALLS",
                    object_id=object_id,
                    environment=ENVIRONMENT,
                    timestamp=bucket_start,
                    trace_id="b" * 32,
                    evidence=evidence,
                )
            ]
        ),
    )
    svc = _service(driver)

    drift = svc.get_architecture_drift(_drift_request(subject_id))

    observed_only = [
        claim for claim in drift.claims if claim.qualification == Qualification.OBSERVED_ONLY
    ]
    assert [claim.object.id for claim in observed_only] == [ids.service_id("product-service")]


def test_drift_claims_are_byte_identical_to_their_dependency_counterparts(driver):
    """I3 spec §8's exact claim-reuse invariant against real Neo4j: same claim_id, and every field
    of the claim identical - no drift-specific id namespace, evidence list or destination."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)
    svc = _service(driver)

    dependencies = svc.get_service_dependencies(_request(ids.service_id("order-service")))
    drift = svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))

    by_id = {claim.claim_id: claim for claim in dependencies.claims}
    assert drift.claims
    for claim in drift.claims:
        assert claim.model_dump(mode="json") == by_id[claim.claim_id].model_dump(mode="json")
    assert drift.snapshot == dependencies.snapshot
    assert drift.observation_context == dependencies.observation_context


def test_drift_retains_the_unresolved_limitation_of_a_returned_fallback_claim(driver):
    """`unused-q` has a sender but no consumer, so its claim stays a DIRECT_TARGET_FALLBACK with an
    UNRESOLVED_IDENTITY limitation - and it drifts, so the limitation travels with it (§19.1)."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)

    drift = svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))

    fallback = [
        claim
        for claim in drift.claims
        if claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    ]
    assert [claim.object.id for claim in fallback] == [ids.queue_id("unused-q")]
    returned_ids = {claim.claim_id for claim in drift.claims}
    unresolved = [
        lim for lim in drift.limitations if lim.code == LimitationCode.UNRESOLVED_IDENTITY
    ]
    assert unresolved
    for limitation in unresolved:
        assert limitation.claim_ids
        assert set(limitation.claim_ids) <= returned_ids


def test_drift_for_a_service_with_no_outgoing_dependencies_is_answered_empty(driver):
    """I3 spec §18.2's second half: a service with zero applicable outgoing dependency claims is an
    ANSWERED empty drift, not a refusal. ProductService only *provides*."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)
    svc = _service(driver)

    drift = svc.get_architecture_drift(_drift_request(ids.service_id("product-service")))

    assert drift.outcome == Outcome.ANSWERED
    assert drift.data is not None
    assert drift.data.drift_claim_ids == []
    assert drift.claims == []
    assert drift.evidence_refs == []
    assert drift.limitations == []


def test_drift_for_a_fully_confirmed_service_is_answered_empty(driver):
    """I3 spec §18.2's first half, and the sharper of the two: PaymentService has exactly one
    supported outgoing dependency (it sends to `invoice-q`), so observing that send makes every one
    of its dependencies CONFIRMED. Empty drift is then a successful answer about a service that
    genuinely has dependencies - not the trivially-empty zero-candidate case above."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    subject_id = ids.service_id("payment-service")
    object_id = ids.queue_id("invoice-q")
    bucket_start = datetime(2026, 8, 26, 12, tzinfo=UTC)
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(ENVIRONMENT, bucket_start, subject_id, "SENDS", object_id),
        environment=ENVIRONMENT,
        bucket_start=bucket_start,
        bucket_end=bucket_start,
        first_seen=bucket_start,
        last_seen=bucket_start,
        observation_count=1,
        sample_trace_ids=["c" * 32],
    )
    persist_observation_batch(
        driver,
        DATABASE,
        ObservationBatch(
            facts=[
                ObservedFactCandidate(
                    subject_id=subject_id,
                    relation_type="SENDS",
                    object_id=object_id,
                    environment=ENVIRONMENT,
                    timestamp=bucket_start,
                    trace_id="c" * 32,
                    evidence=evidence,
                )
            ]
        ),
    )
    svc = _service(driver)

    dependencies = svc.get_service_dependencies(_request(subject_id))
    drift = svc.get_architecture_drift(_drift_request(subject_id))

    assert dependencies.claims
    assert {claim.qualification for claim in dependencies.claims} == {Qualification.CONFIRMED}
    assert drift.outcome == Outcome.ANSWERED
    assert drift.data is not None
    assert drift.data.drift_claim_ids == []
    assert drift.claims == []
    assert drift.evidence_refs == []
    assert drift.limitations == []


def _strip_evidence_from_relation(driver, *, relation_type: str, subject_id: str, object_id: str):
    """Leaves the relation in place but points it at an Evidence id that no Evidence node carries.
    This is the real shape of `_qualify(...) is None`: a candidate dependency path exists in the
    graph, yet nothing in the accepted snapshot supports it, so no dependency claim may be built for
    it (I1 spec §14/§15). Doing it through Cypher rather than a doctored fixture keeps the rest of
    the landscape - and the snapshot fingerprint the read fences against - genuinely real."""
    with driver.session(database=DATABASE) as session:
        summary = session.run(
            f"MATCH (s:Service {{id: $subject_id}})-[r:{relation_type}]->(t {{id: $object_id}}) "
            "SET r.evidence_ids = ['evidence:declared:no-longer-in-snapshot'] "
            "RETURN count(r) AS updated",
            subject_id=subject_id,
            object_id=object_id,
        ).single()
    assert summary["updated"] == 1  # the candidate path this test needs really exists


def test_drift_retains_a_claim_independent_insufficient_evidence_limitation(driver):
    """I3 spec §19.2 against real Neo4j: OrderService keeps drifting dependencies, but one of its
    outgoing paths can no longer be qualified at all. "No safe claim" is not "proved non-drift", so
    that claim-independent limitation must survive the drift filter and make the answer PARTIAL -
    silently dropping it would understate the drift result as complete."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _strip_evidence_from_relation(
        driver,
        relation_type="SENDS",
        subject_id=ids.service_id("order-service"),
        object_id=ids.queue_id("unused-q"),
    )
    svc = _service(driver)

    drift = svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))

    assert drift.outcome == Outcome.PARTIAL
    assert drift.claims
    assert ids.queue_id("unused-q") not in {claim.object.id for claim in drift.claims}
    insufficient = [
        lim for lim in drift.limitations if lim.code == LimitationCode.INSUFFICIENT_EVIDENCE
    ]
    assert [lim.claim_ids for lim in insufficient] == [[]]
    assert ids.queue_id("unused-q") in insufficient[0].message
    # §19.1's other half in the same run: the fallback claim is gone, so is its scoped limitation.
    assert not [lim for lim in drift.limitations if lim.code == LimitationCode.UNRESOLVED_IDENTITY]


def test_drift_is_not_answered_when_every_candidate_path_lacks_evidence(driver):
    """I3 spec §18.4 against real Neo4j: PaymentService's only outgoing dependency is its send to
    `invoice-q`, so unqualifiable evidence there leaves zero drift claims *and* zero confirmed ones.
    That must not be reported as the §18.2 empty-drift success - "could not establish a claim" is
    not "no drift"."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _strip_evidence_from_relation(
        driver,
        relation_type="SENDS",
        subject_id=ids.service_id("payment-service"),
        object_id=ids.queue_id("invoice-q"),
    )
    svc = _service(driver)

    dependencies = svc.get_service_dependencies(_request(ids.service_id("payment-service")))
    drift = svc.get_architecture_drift(_drift_request(ids.service_id("payment-service")))

    assert dependencies.claims == []  # the candidate produced no dependency claim to filter
    assert drift.outcome == Outcome.NOT_ANSWERED
    assert drift.data is None
    assert drift.claims == []
    assert drift.evidence_refs == []
    assert [lim.code for lim in drift.limitations] == [LimitationCode.INSUFFICIENT_EVIDENCE]
    assert drift.snapshot is not None
    assert drift.observation_context is not None


def test_drift_unknown_service_is_refused(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)

    drift = svc.get_architecture_drift(_drift_request("service:does-not-exist"))

    assert drift.outcome == Outcome.NOT_ANSWERED
    assert drift.data is None
    assert [lim.code for lim in drift.limitations] == [LimitationCode.UNKNOWN_ENTITY]


def test_drift_stale_explicit_snapshot_is_refused_without_fallback(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "0" * 64

    drift = svc.get_architecture_drift(
        _drift_request(ids.service_id("order-service"), snapshot_id=stale_snapshot_id)
    )

    assert drift.outcome == Outcome.NOT_ANSWERED
    assert drift.snapshot is not None
    assert drift.snapshot.snapshot_id != stale_snapshot_id
    assert [lim.code for lim in drift.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_drift_two_consecutive_calls_are_canonically_byte_identical(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    svc = _service(driver)
    request = _drift_request(ids.service_id("order-service"))

    first = canonical_json_bytes(svc.get_architecture_drift(request))
    second = canonical_json_bytes(svc.get_architecture_drift(request))
    assert first == second


def test_drift_evidence_refs_all_resolve_through_the_evidence_tool_at_the_same_snapshot(driver):
    """I3 spec §22's required drill-down: drift answer -> snapshot_id + evidence_refs -> get_evidence
    at that same snapshot, resolving every reference."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)
    svc = _service(driver)

    drift = svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))
    assert drift.evidence_refs

    evidence = svc.get_evidence(
        EvidenceRequest(evidence_refs=drift.evidence_refs, snapshot_id=drift.snapshot.snapshot_id)
    )

    assert evidence.outcome == Outcome.ANSWERED
    assert evidence.data.missing_evidence_refs == []
    assert [record.id for record in evidence.data.records] == sorted(drift.evidence_refs)


def test_drift_call_performs_zero_graph_writes(driver, monkeypatch):
    """I3 spec §25: same three-way proof as the I1 dependency path - a READ_ACCESS session, an
    untouched revision fence, and an untouched canonical fingerprint."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)

    captured_read_only = []
    real_open_session = service_module.open_session

    def spy_open_session(drv, *, database, read_only=False):
        captured_read_only.append(read_only)
        return real_open_session(drv, database=database, read_only=read_only)

    monkeypatch.setattr(service_module, "open_session", spy_open_session)

    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)
    fingerprint_before = _fingerprint(driver)

    svc = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    fingerprint_after = _fingerprint(driver)

    assert captured_read_only == [True]
    assert revision_after == revision_before
    assert fingerprint_after == fingerprint_before


def test_drift_refusal_paths_perform_zero_graph_writes(driver, monkeypatch):
    """I3 spec §25 requires the write-free proof for the refusal paths too, not only for ANSWERED."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)

    captured_read_only = []
    real_open_session = service_module.open_session

    def spy_open_session(drv, *, database, read_only=False):
        captured_read_only.append(read_only)
        return real_open_session(drv, database=database, read_only=read_only)

    monkeypatch.setattr(service_module, "open_session", spy_open_session)

    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)
    fingerprint_before = _fingerprint(driver)

    svc = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    refusals = [
        svc.get_architecture_drift(_drift_request("service:does-not-exist")),
        svc.get_architecture_drift(
            _drift_request(
                ids.service_id("order-service"), snapshot_id="aip:snapshot:v1:" + "0" * 64
            )
        ),
        svc.get_architecture_drift(
            ArchitectureDriftRequest.model_validate({"service_id": ids.service_id("order-service")})
        ),
    ]

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    fingerprint_after = _fingerprint(driver)

    assert [answer.outcome for answer in refusals] == [Outcome.NOT_ANSWERED] * 3
    assert [lim.code for answer in refusals for lim in answer.limitations] == [
        LimitationCode.UNKNOWN_ENTITY,
        LimitationCode.SNAPSHOT_NOT_AVAILABLE,
        LimitationCode.OBSERVATION_CONTEXT_REQUIRED,
    ]
    assert captured_read_only == [True, True, True]
    assert revision_after == revision_before
    assert fingerprint_after == fingerprint_before


def test_a_concurrent_write_during_a_drift_stable_read_forces_a_retry(driver, monkeypatch):
    """I3 spec §26: the drift path reuses the I1 revision fence and stable-read retry rather than
    introducing a second read boundary - so it can never mix claims from state A with a snapshot
    fingerprint from state B. Same deterministic injection as the I1 dependency test."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)

    real_read_rows = service_module.read_service_dependency_rows
    calls = {"count": 0}

    def _mutate_and_bump(tx):
        tx.run(
            "MATCH (s:Service {id: $id}) SET s.version = $version",
            id=ids.service_id("product-service"),
            version="mutated-mid-drift-read",
        )
        bump_revision(tx)

    def flaky_read_rows(session, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            with driver.session(database=DATABASE) as write_session:
                write_session.execute_write(_mutate_and_bump)
        return real_read_rows(session, **kwargs)

    monkeypatch.setattr(service_module, "read_service_dependency_rows", flaky_read_rows)

    svc = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    answer = svc.get_architecture_drift(_drift_request(ids.service_id("order-service")))

    expected_snapshot_id, expected_model_revision = _fingerprint(driver)

    assert calls["count"] >= 2
    assert answer.snapshot.snapshot_id == expected_snapshot_id
    assert answer.snapshot.model_revision == expected_model_revision
