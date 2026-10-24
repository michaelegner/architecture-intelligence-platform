"""v0.7.1 I3.2: the two destination-consumer REST routes (I3 spec §5).

- The route supplies `mode`; the body is closed and never repeats it.
- A body that cannot form a valid published request is a 422 that never reaches the service.
- Every answer the service returns, refusal or not, is a 200 with that answer unchanged.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import destination_consumers, errors
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.architecture_intelligence.destination_consumer_contracts import (
    DestinationConsumersAnswer,
    DestinationConsumersEvidenceRequest,
    DestinationConsumersQueryRequest,
    LimitationCode,
)
from app.architecture_intelligence.destination_consumer_projection import refusal_answer
from app.deps import get_architecture_intelligence_service

_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.7.1", build_revision="f" * 40
)
_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_QUERY_PATH = "/api/destination-consumers"
_EVIDENCE_PATH = _QUERY_PATH + "/evidence"
_CONTEXT = {
    "destination_id": "topic:owned:" + "b" * 64,
    "broker_id": "kafka:cluster-a",
    "environment": "prod",
}
_QUERY_BODY = {**_CONTEXT, "limit": 50}
_EVIDENCE_BODY = {
    **_CONTEXT,
    "snapshot_id": _SNAPSHOT.snapshot_id,
    "evidence_refs": ["destination-evidence:" + "1" * 64],
}


class _FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def get_destination_consumers(self, request) -> DestinationConsumersAnswer:
        self.calls.append(("query", request))
        return refusal_answer(_PRODUCER, _SNAPSHOT, LimitationCode.NO_ACCEPTED_CAPTURE)

    def get_destination_consumer_evidence(self, request) -> DestinationConsumersAnswer:
        self.calls.append(("evidence", request))
        return refusal_answer(
            _PRODUCER, _SNAPSHOT, LimitationCode.SNAPSHOT_NOT_AVAILABLE, mode="evidence"
        )


def _client(service: _FakeService) -> TestClient:
    app = FastAPI()
    app.include_router(destination_consumers.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "body", "mode", "request_type"),
    [
        (_QUERY_PATH, _QUERY_BODY, "query", DestinationConsumersQueryRequest),
        (_EVIDENCE_PATH, _EVIDENCE_BODY, "evidence", DestinationConsumersEvidenceRequest),
    ],
)
def test_a_valid_body_becomes_the_full_published_request(path, body, mode, request_type):
    service = _FakeService()
    response = _client(service).post(path, json=body)
    assert response.status_code == 200
    [(called, request)] = service.calls
    assert called == mode
    assert request == request_type.model_validate({**body, "mode": mode})
    answer = (
        service.get_destination_consumers(request)
        if mode == "query"
        else service.get_destination_consumer_evidence(request)
    )
    assert response.json() == answer.model_dump(mode="json")


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (_QUERY_PATH, {**_QUERY_BODY, "mode": "query"}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "mode": "evidence"}),
        (_QUERY_PATH, {**_QUERY_BODY, "cypher": "MATCH (n) RETURN n"}),
        (_QUERY_PATH, {**_QUERY_BODY, "limit": 0}),
        (_QUERY_PATH, {**_QUERY_BODY, "limit": 201}),
        (_QUERY_PATH, {key: value for key, value in _QUERY_BODY.items() if key != "broker_id"}),
        (_QUERY_PATH, {**_QUERY_BODY, "cursor": "e30"}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "evidence_refs": []}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "evidence_refs": ["kafka-attachment:owned:x"]}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "limit": 10}),
    ],
)
def test_a_malformed_body_is_a_422_that_never_reaches_the_service(path, body):
    service = _FakeService()
    response = _client(service).post(path, json=body)
    assert response.status_code == 422
    assert service.calls == []
