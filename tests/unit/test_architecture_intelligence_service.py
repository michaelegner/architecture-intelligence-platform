from datetime import UTC, datetime

from app.analysis.runtime import ServiceTelemetryCoverage
from app.architecture_intelligence import service as service_module
from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    LimitationCode,
    Outcome,
    Producer,
    Qualification,
)
from app.architecture_intelligence.repository import SnapshotUnstable, StableSnapshot
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)

ENVIRONMENT = "demo"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
FAKE_SNAPSHOT_ID = "aip:snapshot:v1:" + "a" * 64
FAKE_MODEL_REVISION = "sha256:" + "a" * 64
OTHER_SNAPSHOT_ID = "aip:snapshot:v1:" + "b" * 64

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.0", build_revision="f" * 40
)

_NO_COVERAGE = ServiceTelemetryCoverage(
    service_id="service:order-service",
    service_name="OrderService",
    environment=ENVIRONMENT,
    since=datetime(2026, 8, 26, tzinfo=UTC),
    http_observed=False,
    messaging_observed=False,
    spans_observed=False,
)

EMPTY_ROWS = {
    "calls": [],
    "provides": [],
    "sends": [],
    "receives": [],
    "evidence": {},
    "coverage": _NO_COVERAGE,
}


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Unset:
    pass


_UNSET = _Unset()


def _make_fake_read_stable_snapshot(
    *, raises: Exception | None = None, snapshot_id: str = FAKE_SNAPSHOT_ID
):
    def fake(session, *, coverage_qualification_enabled, read_extra, max_attempts=3):
        if raises is not None:
            raise raises
        extra = read_extra(session)
        return StableSnapshot(
            snapshot_id=snapshot_id, model_revision=FAKE_MODEL_REVISION, extra=extra
        )

    return fake


def _service(
    monkeypatch,
    *,
    rows=_UNSET,
    raises: Exception | None = None,
    snapshot_id: str = FAKE_SNAPSHOT_ID,
):
    monkeypatch.setattr(
        service_module, "open_session", lambda driver, *, database, read_only: FakeSession()
    )
    monkeypatch.setattr(
        service_module,
        "read_stable_snapshot_from_session",
        _make_fake_read_stable_snapshot(raises=raises, snapshot_id=snapshot_id),
    )
    if rows is not _UNSET:
        monkeypatch.setattr(
            service_module,
            "read_service_dependency_rows",
            lambda session, *, service_id, environment, window_start, window_end: rows,
        )
    return service_module.ArchitectureIntelligenceService(
        driver=object(), database="neo4j", producer=PRODUCER
    )


def _request(**overrides) -> ServiceDependenciesRequest:
    payload = {
        "service_id": "service:order-service",
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }
    payload.update(overrides)
    return ServiceDependenciesRequest.model_validate(payload)


def test_missing_observation_context_yields_observation_context_required(monkeypatch):
    request = ServiceDependenciesRequest.model_validate({"service_id": "service:order-service"})

    def fake_read_stable(session, *, coverage_qualification_enabled, read_extra, max_attempts=3):
        # read_extra must be a safe no-op when context is incomplete - never touches Neo4j.
        assert read_extra(session) is None
        return StableSnapshot(
            snapshot_id=FAKE_SNAPSHOT_ID, model_revision=FAKE_MODEL_REVISION, extra=None
        )

    monkeypatch.setattr(
        service_module, "open_session", lambda driver, *, database, read_only: FakeSession()
    )
    monkeypatch.setattr(service_module, "read_stable_snapshot_from_session", fake_read_stable)
    svc = service_module.ArchitectureIntelligenceService(
        driver=object(), database="neo4j", producer=PRODUCER
    )
    answer = svc.get_service_dependencies(request)

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.observation_context is None
    assert answer.snapshot.snapshot_id == FAKE_SNAPSHOT_ID
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.OBSERVATION_CONTEXT_REQUIRED]


def test_unstable_snapshot_yields_snapshot_not_available_without_snapshot_ref(monkeypatch):
    svc = _service(monkeypatch, raises=SnapshotUnstable("boom"))
    answer = svc.get_service_dependencies(_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.snapshot is None
    assert answer.observation_context is not None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_stale_explicit_snapshot_is_refused_with_the_current_snapshot_attached(monkeypatch):
    svc = _service(monkeypatch, rows={**EMPTY_ROWS, "service_name": "OrderService"})
    answer = svc.get_service_dependencies(_request(snapshot_id=OTHER_SNAPSHOT_ID))

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.snapshot.snapshot_id == FAKE_SNAPSHOT_ID
    assert answer.observation_context is not None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_matching_explicit_snapshot_repeats_the_answer(monkeypatch):
    svc = _service(monkeypatch, rows={**EMPTY_ROWS, "service_name": "OrderService"})
    answer = svc.get_service_dependencies(_request(snapshot_id=FAKE_SNAPSHOT_ID))

    assert answer.outcome == Outcome.ANSWERED
    assert answer.data.dependency_claim_ids == []


def test_unknown_service_yields_unknown_entity(monkeypatch):
    svc = _service(monkeypatch, rows={**EMPTY_ROWS, "service_name": None})
    answer = svc.get_service_dependencies(_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.UNKNOWN_ENTITY]


def test_known_service_with_zero_candidates_is_answered_with_empty_claims(monkeypatch):
    svc = _service(monkeypatch, rows={**EMPTY_ROWS, "service_name": "OrderService"})
    answer = svc.get_service_dependencies(_request())

    assert answer.outcome == Outcome.ANSWERED
    assert answer.data.dependency_claim_ids == []
    assert answer.claims == []
    assert answer.limitations == []


def test_all_resolved_claims_yield_answered(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
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
        "evidence": {
            "e1": {"evidence_type": "DECLARED", "environment": None, "last_seen": None},
            "e2": {"evidence_type": "DECLARED", "environment": None, "last_seen": None},
        },
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_service_dependencies(_request())

    assert answer.outcome == Outcome.ANSWERED
    assert len(answer.claims) == 1
    assert answer.data.dependency_claim_ids == [answer.claims[0].claim_id]
    assert answer.evidence_refs == ["e1", "e2"]


def test_mixed_resolved_and_unresolved_paths_produce_partial(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "calls": [
            {
                "operation_id": "operation:product-service:GET:/products/{id}",
                "operation_name": None,
                "method": "GET",
                "path": "/products/{id}",
                "evidence_ids": ["e1"],
            },
            {
                "operation_id": "operation:internal:GET:/internal/reconcile",
                "operation_name": None,
                "method": "GET",
                "path": "/internal/reconcile",
                "evidence_ids": ["e3"],
            },
        ],
        "provides": [
            {
                "operation_id": "operation:product-service:GET:/products/{id}",
                "provider_id": "service:product-service",
                "provider_name": "ProductService",
                "evidence_ids": ["e2"],
            }
        ],
        "evidence": {
            "e1": {"evidence_type": "DECLARED", "environment": None, "last_seen": None},
            "e2": {"evidence_type": "DECLARED", "environment": None, "last_seen": None},
            "e3": {"evidence_type": "DECLARED", "environment": None, "last_seen": None},
        },
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_service_dependencies(_request())

    assert answer.outcome == Outcome.PARTIAL
    assert len(answer.claims) == 2
    assert [lim.code for lim in answer.limitations] == [LimitationCode.UNRESOLVED_IDENTITY]


def test_all_candidates_lacking_evidence_yield_not_answered_insufficient_evidence(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
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
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_service_dependencies(_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.data is None
    assert answer.claims == []
    assert [lim.code for lim in answer.limitations] == [LimitationCode.INSUFFICIENT_EVIDENCE]


def test_result_limit_exceeded_is_reported_without_truncation(monkeypatch):
    calls = [
        {
            "operation_id": f"operation:x:GET:/x{i}",
            "operation_name": None,
            "method": "GET",
            "path": f"/x{i}",
            "evidence_ids": [f"e{i}"],
        }
        for i in range(501)
    ]
    evidence = {
        f"e{i}": {"evidence_type": "DECLARED", "environment": None, "last_seen": None}
        for i in range(501)
    }
    rows = {**EMPTY_ROWS, "service_name": "OrderService", "calls": calls, "evidence": evidence}
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_service_dependencies(_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.claims == []
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.RESULT_LIMIT_EXCEEDED]


def test_two_consecutive_calls_are_canonically_byte_identical(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
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
        "evidence": {
            "e1": {"evidence_type": "DECLARED", "environment": None, "last_seen": None},
            "e2": {"evidence_type": "DECLARED", "environment": None, "last_seen": None},
        },
    }
    svc = _service(monkeypatch, rows=rows)

    first = canonical_json_bytes(svc.get_service_dependencies(_request()))
    second = canonical_json_bytes(svc.get_service_dependencies(_request()))
    assert first == second


# --- I2.3: get_evidence -------------------------------------------------------------------------

DECLARED_EVIDENCE_ID = "evidence:declared:order-service"
OBSERVED_EVIDENCE_ID = "evidence:observed:order-service"
MISSING_EVIDENCE_ID = "evidence:declared:missing"

_DECLARED_ROW = {
    "id": DECLARED_EVIDENCE_ID,
    "evidence_type": "DECLARED",
    "source_type": "MANIFEST",
    "source_file": "architecture.yaml",
    "source_revision": None,
}
_OBSERVED_ROW = {
    "id": OBSERVED_EVIDENCE_ID,
    "evidence_type": "OBSERVED",
    "source_type": "OPENTELEMETRY",
    "source_file": "opentelemetry",
    "source_revision": None,
    "environment": ENVIRONMENT,
    "bucket_start": datetime(2026, 8, 26, tzinfo=UTC),
    "bucket_end": datetime(2026, 8, 26, tzinfo=UTC),
    "first_seen": datetime(2026, 8, 26, tzinfo=UTC),
    "last_seen": datetime(2026, 8, 26, tzinfo=UTC),
    "observation_count": 3,
    "service_version": None,
    "correlation_mode": None,
}

EMPTY_EVIDENCE_ROWS = {"evidence": {}, "relations": []}


def _evidence_service(
    monkeypatch,
    *,
    rows=_UNSET,
    raises: Exception | None = None,
    snapshot_id: str = FAKE_SNAPSHOT_ID,
):
    monkeypatch.setattr(
        service_module, "open_session", lambda driver, *, database, read_only: FakeSession()
    )
    monkeypatch.setattr(
        service_module,
        "read_stable_snapshot_from_session",
        _make_fake_read_stable_snapshot(raises=raises, snapshot_id=snapshot_id),
    )
    if rows is not _UNSET:
        monkeypatch.setattr(
            service_module, "read_evidence_rows", lambda session, *, evidence_ids: rows
        )
    return service_module.ArchitectureIntelligenceService(
        driver=object(), database="neo4j", producer=PRODUCER
    )


def _evidence_request(**overrides) -> EvidenceRequest:
    payload = {"evidence_refs": [DECLARED_EVIDENCE_ID], "snapshot_id": FAKE_SNAPSHOT_ID}
    payload.update(overrides)
    return EvidenceRequest.model_validate(payload)


def test_evidence_unstable_snapshot_yields_snapshot_not_available_without_snapshot_ref(
    monkeypatch,
):
    svc = _evidence_service(monkeypatch, raises=SnapshotUnstable("boom"))
    answer = svc.get_evidence(_evidence_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.snapshot is None
    assert answer.observation_context is None
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_evidence_stale_explicit_snapshot_is_refused_without_fallback(monkeypatch):
    svc = _evidence_service(monkeypatch, rows=EMPTY_EVIDENCE_ROWS)
    answer = svc.get_evidence(_evidence_request(snapshot_id=OTHER_SNAPSHOT_ID))

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.snapshot.snapshot_id == FAKE_SNAPSHOT_ID
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_evidence_all_resolved_yields_answered_with_declared_and_observed_records(monkeypatch):
    rows = {
        "evidence": {DECLARED_EVIDENCE_ID: _DECLARED_ROW, OBSERVED_EVIDENCE_ID: _OBSERVED_ROW},
        "relations": [],
    }
    svc = _evidence_service(monkeypatch, rows=rows)
    request = _evidence_request(evidence_refs=[DECLARED_EVIDENCE_ID, OBSERVED_EVIDENCE_ID])
    answer = svc.get_evidence(request)

    assert answer.outcome == Outcome.ANSWERED
    assert answer.observation_context is None
    assert answer.claims == []
    assert answer.evidence_refs == []
    assert answer.limitations == []
    assert answer.data.missing_evidence_refs == []
    assert [record.id for record in answer.data.records] == [
        DECLARED_EVIDENCE_ID,
        OBSERVED_EVIDENCE_ID,
    ]
    declared, observed = answer.data.records
    assert declared.observation is None
    assert observed.observation is not None
    assert observed.observation.observation_count == 3


def test_evidence_mixed_resolved_and_missing_yields_partial(monkeypatch):
    rows = {"evidence": {DECLARED_EVIDENCE_ID: _DECLARED_ROW}, "relations": []}
    svc = _evidence_service(monkeypatch, rows=rows)
    request = _evidence_request(evidence_refs=[DECLARED_EVIDENCE_ID, MISSING_EVIDENCE_ID])
    answer = svc.get_evidence(request)

    assert answer.outcome == Outcome.PARTIAL
    assert [record.id for record in answer.data.records] == [DECLARED_EVIDENCE_ID]
    assert answer.data.missing_evidence_refs == [MISSING_EVIDENCE_ID]
    assert [lim.code for lim in answer.limitations] == [LimitationCode.INSUFFICIENT_EVIDENCE]


def test_evidence_all_missing_yields_not_answered_insufficient_evidence_with_data_present(
    monkeypatch,
):
    svc = _evidence_service(monkeypatch, rows=EMPTY_EVIDENCE_ROWS)
    answer = svc.get_evidence(_evidence_request(evidence_refs=[MISSING_EVIDENCE_ID]))

    assert answer.outcome == Outcome.NOT_ANSWERED
    # Spec §12: "No record resolves -> NOT_ANSWERED/INSUFFICIENT_EVIDENCE; empty records plus
    # missing refs" - unlike get_service_dependencies' NOT_ANSWERED refusals, data stays non-null.
    assert answer.data is not None
    assert answer.data.records == []
    assert answer.data.missing_evidence_refs == [MISSING_EVIDENCE_ID]
    assert [lim.code for lim in answer.limitations] == [LimitationCode.INSUFFICIENT_EVIDENCE]


def test_evidence_requested_ids_are_sorted_for_processing_and_output(monkeypatch):
    rows = {
        "evidence": {DECLARED_EVIDENCE_ID: _DECLARED_ROW, OBSERVED_EVIDENCE_ID: _OBSERVED_ROW},
        "relations": [],
    }
    svc = _evidence_service(monkeypatch, rows=rows)
    request = _evidence_request(evidence_refs=[OBSERVED_EVIDENCE_ID, DECLARED_EVIDENCE_ID])
    answer = svc.get_evidence(request)

    assert answer.data.requested_evidence_refs == sorted(
        [OBSERVED_EVIDENCE_ID, DECLARED_EVIDENCE_ID]
    )


def test_evidence_two_consecutive_calls_are_canonically_byte_identical(monkeypatch):
    rows = {"evidence": {DECLARED_EVIDENCE_ID: _DECLARED_ROW}, "relations": []}
    svc = _evidence_service(monkeypatch, rows=rows)
    from app.architecture_intelligence.canonical_json import canonical_json_bytes

    first = canonical_json_bytes(svc.get_evidence(_evidence_request()))
    second = canonical_json_bytes(svc.get_evidence(_evidence_request()))
    assert first == second


# --- I3.1: get_architecture_drift ----------------------------------------------------------------

INSIDE_WINDOW = datetime(2026, 8, 26, 12, tzinfo=UTC)

_OBSERVED_COVERAGE = ServiceTelemetryCoverage(
    service_id="service:order-service",
    service_name="OrderService",
    environment=ENVIRONMENT,
    since=datetime(2026, 8, 26, tzinfo=UTC),
    http_observed=True,
    messaging_observed=False,
    spans_observed=True,
)


def _drift_request(**overrides) -> ArchitectureDriftRequest:
    payload = {
        "service_id": "service:order-service",
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }
    payload.update(overrides)
    return ArchitectureDriftRequest.model_validate(payload)


def _call(operation: str, *evidence_ids: str) -> dict:
    return {
        "operation_id": f"operation:{operation}",
        "operation_name": None,
        "method": "GET",
        "path": f"/{operation}",
        "evidence_ids": list(evidence_ids),
    }


def _provides(operation: str, provider: str, *evidence_ids: str) -> dict:
    return {
        "operation_id": f"operation:{operation}",
        "provider_id": f"service:{provider}",
        "provider_name": provider,
        "evidence_ids": list(evidence_ids),
    }


def _declared_row() -> dict:
    return {"evidence_type": "DECLARED", "environment": None, "last_seen": None}


def _observed_row() -> dict:
    return {
        "evidence_type": "OBSERVED",
        "environment": ENVIRONMENT,
        "last_seen": INSIDE_WINDOW,
    }


def test_drift_known_service_with_a_not_observed_dependency_is_answered(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "calls": [_call("product-service:GET:/products", "e1")],
        "provides": [_provides("product-service:GET:/products", "product-service", "e2")],
        "evidence": {"e1": _declared_row(), "e2": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.tool == "get_architecture_drift"
    assert answer.outcome == Outcome.ANSWERED
    assert [claim.qualification for claim in answer.claims] == [
        Qualification.NOT_OBSERVED_IN_WINDOW
    ]
    assert answer.data.drift_claim_ids == [answer.claims[0].claim_id]
    assert answer.data.service.id == "service:order-service"
    assert answer.evidence_refs == ["e1", "e2"]
    assert answer.limitations == []


def test_drift_known_service_with_an_observed_only_dependency_is_answered(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "coverage": _OBSERVED_COVERAGE,
        "calls": [_call("product-service:GET:/products", "e1")],
        "provides": [_provides("product-service:GET:/products", "product-service", "e2")],
        "evidence": {"e1": _observed_row(), "e2": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.ANSWERED
    assert [claim.qualification for claim in answer.claims] == [Qualification.OBSERVED_ONLY]


def test_drift_omits_confirmed_dependencies(monkeypatch):
    """I3 spec §7.1: CONFIRMED claims MUST NOT appear in the drift answer, even though they are part
    of the same underlying dependency projection."""
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "coverage": _OBSERVED_COVERAGE,
        "calls": [
            _call("confirmed-service:GET:/c", "e1", "e2"),
            _call("drifting-service:GET:/d", "e3"),
        ],
        "provides": [
            _provides("confirmed-service:GET:/c", "confirmed-service", "e4"),
            _provides("drifting-service:GET:/d", "drifting-service", "e5"),
        ],
        "evidence": {
            "e1": _declared_row(),
            "e2": _observed_row(),
            "e3": _declared_row(),
            "e4": _declared_row(),
            "e5": _declared_row(),
        },
    }
    svc = _service(monkeypatch, rows=rows)
    dependencies = svc.get_service_dependencies(_request())
    drift = svc.get_architecture_drift(_drift_request())

    assert sorted(claim.qualification for claim in dependencies.claims) == sorted(
        [Qualification.CONFIRMED, Qualification.NOT_OBSERVED_IN_WINDOW]
    )
    assert [claim.object.id for claim in drift.claims] == ["service:drifting-service"]
    # I3 spec §21: a CONFIRMED claim's evidence is not part of this answer either.
    assert "e2" not in drift.evidence_refs


def test_drift_claims_are_identical_to_their_dependency_counterparts(monkeypatch):
    """I3 spec §8's exact claim-reuse invariant, at the service boundary."""
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "calls": [_call("product-service:GET:/products", "e1")],
        "provides": [_provides("product-service:GET:/products", "product-service", "e2")],
        "evidence": {"e1": _declared_row(), "e2": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    dependencies = svc.get_service_dependencies(_request())
    drift = svc.get_architecture_drift(_drift_request())

    by_id = {claim.claim_id: claim for claim in dependencies.claims}
    assert drift.claims
    for claim in drift.claims:
        assert claim == by_id[claim.claim_id]


def test_drift_preserves_the_dependency_claim_ordering(monkeypatch):
    """I3 spec §20: filtering must not resort - the surviving claims keep their I1 relative order."""
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "coverage": _OBSERVED_COVERAGE,
        "calls": [
            _call("a-service:GET:/a", "e1"),
            _call("m-service:GET:/m", "e2", "e3"),
            _call("z-service:GET:/z", "e4"),
        ],
        "provides": [
            _provides("a-service:GET:/a", "a-service", "e5"),
            _provides("m-service:GET:/m", "m-service", "e6"),
            _provides("z-service:GET:/z", "z-service", "e7"),
        ],
        "evidence": {
            "e1": _declared_row(),
            "e2": _declared_row(),
            "e3": _observed_row(),
            "e4": _observed_row(),
            "e5": _declared_row(),
            "e6": _declared_row(),
            "e7": _declared_row(),
        },
    }
    svc = _service(monkeypatch, rows=rows)
    dependencies = svc.get_service_dependencies(_request())
    drift = svc.get_architecture_drift(_drift_request())

    drift_ids = [claim.claim_id for claim in drift.claims]
    dependency_order = [
        claim.claim_id for claim in dependencies.claims if claim.claim_id in set(drift_ids)
    ]
    assert drift_ids == dependency_order
    assert [claim.object.id for claim in drift.claims] == ["service:a-service", "service:z-service"]


def test_drift_with_no_drifting_dependency_is_answered_empty(monkeypatch):
    """I3 spec §18.2: empty drift is a successful answer, not NOT_ANSWERED."""
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "coverage": _OBSERVED_COVERAGE,
        "calls": [_call("product-service:GET:/products", "e1", "e2")],
        "provides": [_provides("product-service:GET:/products", "product-service", "e3")],
        "evidence": {"e1": _declared_row(), "e2": _observed_row(), "e3": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.ANSWERED
    assert answer.data is not None
    assert answer.data.drift_claim_ids == []
    assert answer.claims == []
    assert answer.evidence_refs == []
    assert answer.limitations == []


def test_drift_for_a_service_with_zero_candidates_is_answered_empty(monkeypatch):
    svc = _service(monkeypatch, rows={**EMPTY_ROWS, "service_name": "OrderService"})
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.ANSWERED
    assert answer.data.drift_claim_ids == []
    assert answer.limitations == []


def test_drift_with_a_surviving_unresolved_claim_is_partial(monkeypatch):
    """I3 spec §18.3/§19.1: the claim-scoped limitation of a *returned* drift claim is retained."""
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "calls": [_call("unowned:GET:/u", "e1")],
        "evidence": {"e1": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.PARTIAL
    assert len(answer.claims) == 1
    assert [lim.code for lim in answer.limitations] == [LimitationCode.UNRESOLVED_IDENTITY]
    assert answer.limitations[0].claim_ids == [answer.claims[0].claim_id]


def test_drift_drops_the_unresolved_limitation_of_an_omitted_confirmed_claim(monkeypatch):
    """I3 spec §19.1's worked example, end to end through the service."""
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "coverage": _OBSERVED_COVERAGE,
        "calls": [_call("unowned:GET:/u", "e1", "e2")],
        "evidence": {"e1": _declared_row(), "e2": _observed_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    dependencies = svc.get_service_dependencies(_request())
    drift = svc.get_architecture_drift(_drift_request())

    assert [lim.code for lim in dependencies.limitations] == [LimitationCode.UNRESOLVED_IDENTITY]
    assert drift.outcome == Outcome.ANSWERED
    assert drift.claims == []
    assert drift.limitations == []


def test_drift_retains_a_claim_independent_insufficient_evidence_limitation(monkeypatch):
    """I3 spec §19.2/§18.4: candidates existed whose evidence could not support a claim, so the drift
    result is incomplete - "could not establish a claim" must never be reported as "no drift"."""
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "coverage": _OBSERVED_COVERAGE,
        "calls": [
            _call("confirmed-service:GET:/c", "e1", "e2"),
            _call("evidenceless:GET:/e"),
        ],
        "provides": [_provides("confirmed-service:GET:/c", "confirmed-service", "e3")],
        "evidence": {"e1": _declared_row(), "e2": _observed_row(), "e3": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.data is None
    assert answer.claims == []
    assert [lim.code for lim in answer.limitations] == [LimitationCode.INSUFFICIENT_EVIDENCE]
    assert answer.limitations[0].claim_ids == []


def test_drift_with_a_drift_claim_and_an_insufficient_evidence_limitation_is_partial(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "calls": [
            _call("product-service:GET:/products", "e1"),
            _call("evidenceless:GET:/e"),
        ],
        "provides": [_provides("product-service:GET:/products", "product-service", "e2")],
        "evidence": {"e1": _declared_row(), "e2": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.PARTIAL
    assert len(answer.claims) == 1
    assert [lim.code for lim in answer.limitations] == [LimitationCode.INSUFFICIENT_EVIDENCE]


def test_drift_unknown_service_yields_unknown_entity(monkeypatch):
    svc = _service(monkeypatch, rows={**EMPTY_ROWS, "service_name": None})
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.UNKNOWN_ENTITY]


def test_drift_missing_observation_context_yields_observation_context_required(monkeypatch):
    request = ArchitectureDriftRequest.model_validate({"service_id": "service:order-service"})

    def fake_read_stable(session, *, coverage_qualification_enabled, read_extra, max_attempts=3):
        assert read_extra(session) is None
        return StableSnapshot(
            snapshot_id=FAKE_SNAPSHOT_ID, model_revision=FAKE_MODEL_REVISION, extra=None
        )

    monkeypatch.setattr(
        service_module, "open_session", lambda driver, *, database, read_only: FakeSession()
    )
    monkeypatch.setattr(service_module, "read_stable_snapshot_from_session", fake_read_stable)
    svc = service_module.ArchitectureIntelligenceService(
        driver=object(), database="neo4j", producer=PRODUCER
    )
    answer = svc.get_architecture_drift(request)

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.observation_context is None
    assert answer.snapshot.snapshot_id == FAKE_SNAPSHOT_ID
    assert [lim.code for lim in answer.limitations] == [LimitationCode.OBSERVATION_CONTEXT_REQUIRED]


def test_drift_stale_explicit_snapshot_is_refused_without_fallback(monkeypatch):
    svc = _service(monkeypatch, rows={**EMPTY_ROWS, "service_name": "OrderService"})
    answer = svc.get_architecture_drift(_drift_request(snapshot_id=OTHER_SNAPSHOT_ID))

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.snapshot.snapshot_id == FAKE_SNAPSHOT_ID
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_drift_unstable_snapshot_yields_snapshot_not_available(monkeypatch):
    svc = _service(monkeypatch, raises=SnapshotUnstable("boom"))
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.snapshot is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.SNAPSHOT_NOT_AVAILABLE]


def test_drift_uses_the_stable_read_retry_path(monkeypatch):
    """I3 spec §26: the drift path goes through the same bounded stable-read retry as I1, rather
    than a second read boundary of its own."""
    calls = []

    def recording_read_stable(session, *, coverage_qualification_enabled, read_extra, **kwargs):
        calls.append(kwargs)
        return StableSnapshot(
            snapshot_id=FAKE_SNAPSHOT_ID,
            model_revision=FAKE_MODEL_REVISION,
            extra=read_extra(session),
        )

    monkeypatch.setattr(
        service_module, "open_session", lambda driver, *, database, read_only: FakeSession()
    )
    monkeypatch.setattr(service_module, "read_stable_snapshot_from_session", recording_read_stable)
    monkeypatch.setattr(
        service_module,
        "read_service_dependency_rows",
        lambda session, *, service_id, environment, window_start, window_end: {
            **EMPTY_ROWS,
            "service_name": "OrderService",
        },
    )
    svc = service_module.ArchitectureIntelligenceService(
        driver=object(), database="neo4j", producer=PRODUCER
    )
    svc.get_architecture_drift(_drift_request())

    assert len(calls) == 1


def test_drift_result_limit_is_enforced_before_the_drift_filter(monkeypatch):
    """I3 spec §17: an underlying dependency result over the safe bound is refused even though the
    drift filter would have returned a small, deceptively "complete"-looking subset. The two
    OBSERVED_ONLY candidates below are exactly that subset - the other 499 are CONFIRMED (declared
    plus a matching in-window observation) and would have been filtered away."""
    drifting, confirmed = 2, 499
    calls = [_call(f"x:GET:/x{i}", f"o{i}") for i in range(drifting)]
    calls += [
        _call(f"x:GET:/x{i}", f"d{i}", f"o{i}") for i in range(drifting, drifting + confirmed)
    ]
    provides = [_provides(f"x:GET:/x{i}", f"p{i}", f"pd{i}") for i in range(drifting + confirmed)]
    evidence = {f"o{i}": _observed_row() for i in range(drifting + confirmed)}
    evidence.update({f"d{i}": _declared_row() for i in range(drifting, drifting + confirmed)})
    evidence.update({f"pd{i}": _declared_row() for i in range(drifting + confirmed)})
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "coverage": _OBSERVED_COVERAGE,
        "calls": calls,
        "provides": provides,
        "evidence": evidence,
    }
    svc = _service(monkeypatch, rows=rows)

    # Lifting the bound first proves the fixture really is the §17 shape - 501 underlying
    # candidates of which only 2 drift - so the refusal below is the bound firing on the underlying
    # result, not an artefact of a fixture that happens to drift in full.
    real_max = service_module._MAX_CLAIMS
    monkeypatch.setattr(service_module, "_MAX_CLAIMS", drifting + confirmed)
    unbounded = svc.get_service_dependencies(_request())
    assert len(unbounded.claims) == drifting + confirmed
    assert (
        sum(claim.qualification != Qualification.CONFIRMED for claim in unbounded.claims)
        == drifting
    )
    assert len(svc.get_architecture_drift(_drift_request()).claims) == drifting

    monkeypatch.setattr(service_module, "_MAX_CLAIMS", real_max)
    answer = svc.get_architecture_drift(_drift_request())

    assert answer.outcome == Outcome.NOT_ANSWERED
    assert answer.claims == []
    assert answer.data is None
    assert [lim.code for lim in answer.limitations] == [LimitationCode.RESULT_LIMIT_EXCEEDED]


def test_drift_two_consecutive_calls_are_canonically_byte_identical(monkeypatch):
    rows = {
        **EMPTY_ROWS,
        "service_name": "OrderService",
        "calls": [_call("product-service:GET:/products", "e1")],
        "provides": [_provides("product-service:GET:/products", "product-service", "e2")],
        "evidence": {"e1": _declared_row(), "e2": _declared_row()},
    }
    svc = _service(monkeypatch, rows=rows)

    first = canonical_json_bytes(svc.get_architecture_drift(_drift_request()))
    second = canonical_json_bytes(svc.get_architecture_drift(_drift_request()))
    assert first == second
