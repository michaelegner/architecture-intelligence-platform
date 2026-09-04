from datetime import UTC, datetime

from app.analysis.runtime import ServiceTelemetryCoverage
from app.architecture_intelligence import service as service_module
from app.architecture_intelligence.contracts import LimitationCode, Outcome, Producer
from app.architecture_intelligence.repository import SnapshotUnstable, StableSnapshot
from app.architecture_intelligence.request import ServiceDependenciesRequest

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
    from app.architecture_intelligence.canonical_json import canonical_json_bytes

    first = canonical_json_bytes(svc.get_service_dependencies(_request()))
    second = canonical_json_bytes(svc.get_service_dependencies(_request()))
    assert first == second
