"""v0.6.0 I3.3b: the two locality REST routes (I3 decision record D1, D9, D16.2).

- The path supplies the Service, and the route supplies `mode`.
- The body is closed and never repeats either of them.
- A body that cannot form a valid published request is a 422 that never reaches the service.
- Every answer the service returns, refusal or not, is a 200 with that answer unchanged.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import architecture_intelligence, errors
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityEvidenceRequest,
    LocalityLimitationCode,
    LocalityQueryRequest,
)
from app.architecture_intelligence.locality_projection import refusal_answer
from app.deps import get_architecture_intelligence_service

_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)
_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_QUERY_PATH = "/api/services/service:orders/dependencies/by-locality"
_EVIDENCE_PATH = _QUERY_PATH + "/evidence"
_QUERY_BODY = {
    "environment": "production",
    "first_day": "2026-09-28",
    "last_day": "2026-09-28",
}
_EVIDENCE_BODY = {
    "snapshot_id": _SNAPSHOT.snapshot_id,
    "refs": ["evidence:otel:calls-scoped:v2:" + "1" * 64],
}
_WORKLOAD = {"cluster_uid": "k1", "namespace": "shop", "kind": "Deployment"}


class _FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def get_service_dependencies_by_locality(self, request) -> LocalityAnswer:
        self.calls.append(("query", request))
        return refusal_answer(_PRODUCER, _SNAPSHOT, LocalityLimitationCode.SNAPSHOT_NOT_AVAILABLE)

    def resolve_scoped_locality_evidence(self, request) -> LocalityAnswer:
        self.calls.append(("evidence", request))
        return refusal_answer(
            _PRODUCER, _SNAPSHOT, LocalityLimitationCode.SNAPSHOT_NOT_AVAILABLE, mode="evidence"
        )


def _client(service: _FakeService) -> TestClient:
    app = FastAPI()
    app.include_router(architecture_intelligence.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "body", "mode", "request_type"),
    [
        (_QUERY_PATH, _QUERY_BODY, "query", LocalityQueryRequest),
        (_EVIDENCE_PATH, _EVIDENCE_BODY, "evidence", LocalityEvidenceRequest),
    ],
)
def test_a_valid_body_becomes_the_full_published_request(path, body, mode, request_type):
    service = _FakeService()

    response = _client(service).post(path, json=body)

    assert response.status_code == 200
    [(called, request)] = service.calls
    assert called == mode
    assert request == request_type.model_validate(
        {**body, "mode": mode, "subject_service_id": "service:orders"}
    )
    # The service's own answer, a refusal here, is returned unchanged as a 200 (D9).
    answer = (
        service.get_service_dependencies_by_locality(request)
        if mode == "query"
        else service.resolve_scoped_locality_evidence(request)
    )
    assert response.json() == answer.model_dump(mode="json")


@pytest.mark.parametrize(
    ("path", "body"),
    [
        # Closed body: the path and the route supply these (D1, D16.2).
        (_QUERY_PATH, {**_QUERY_BODY, "subject_service_id": "service:orders"}),
        (_QUERY_PATH, {**_QUERY_BODY, "mode": "query"}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "subject_service_id": "service:orders"}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "mode": "evidence"}),
        (_QUERY_PATH, {**_QUERY_BODY, "junk": 1}),
        # Malformed per the request model's own field rules.
        (_QUERY_PATH, {**_QUERY_BODY, "first_day": "2026-02-30"}),
        (_QUERY_PATH, {**_QUERY_BODY, "first_day": "2026-09-29"}),
        (_QUERY_PATH, {**_QUERY_BODY, "dimensions": ["workload", "cluster"]}),
        (_QUERY_PATH, {**_QUERY_BODY, "cursor": "not-a-cursor"}),
        # Malformed per the request model's cross-field rule (D3: compare within caller_localities).
        (
            _QUERY_PATH,
            {
                **_QUERY_BODY,
                "caller_localities": [{**_WORKLOAD, "uid": "w1"}],
                "compare": [{**_WORKLOAD, "uid": "w1"}, {**_WORKLOAD, "uid": "w2"}],
            },
        ),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "refs": [f"evidence:x{n:02d}" for n in range(21)]}),
        (_EVIDENCE_PATH, {"refs": _EVIDENCE_BODY["refs"]}),
    ],
)
def test_a_body_that_cannot_form_a_valid_request_is_a_422_before_the_service(path, body):
    service = _FakeService()

    response = _client(service).post(path, json=body)

    assert response.status_code == 422
    assert service.calls == []


def test_a_well_formed_but_unsupported_query_is_answered_not_rejected():
    """D9: an unsupported relation is a well-formed request; the service decides the refusal."""
    service = _FakeService()

    response = _client(service).post(_QUERY_PATH, json={**_QUERY_BODY, "relation_type": "SENDS"})

    assert response.status_code == 200
    assert [called for called, _ in service.calls] == ["query"]
