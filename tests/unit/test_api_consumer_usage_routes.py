"""v0.7.0 I3.3: the two API usage REST routes (I3 decision record D1).

- The route supplies `mode`; the body is closed and never repeats it.
- A body that cannot form a valid published request is a 422 that never reaches the service.
- Every answer the service returns, refusal or not, is a 200 with that answer unchanged.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import api_consumer_usage, errors
from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
    ApiUsageLimitationCode,
)
from app.architecture_intelligence.api_usage_projection import refusal_answer
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.deps import get_architecture_intelligence_service

_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.7.0", build_revision="f" * 40
)
_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_QUERY_PATH = "/api/api-consumer-usage"
_EVIDENCE_PATH = _QUERY_PATH + "/evidence"
_CONTEXT = {
    "target": {"kind": "GATEWAY_ROUTE", "id": "gateway-route:owned:" + "b" * 64},
    "gateway_instance_id": "gw-prod-1",
    "environment": "prod",
    "window_start": "2026-10-13T10:00:00Z",
    "window_end": "2026-10-13T10:10:00Z",
}
_QUERY_BODY = {**_CONTEXT, "limit": 50}
_EVIDENCE_BODY = {
    **_CONTEXT,
    "snapshot_id": _SNAPSHOT.snapshot_id,
    "evidence_refs": ["api-evidence:" + "1" * 64],
}


class _FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def get_api_consumer_usage(self, request) -> ApiConsumerUsageAnswer:
        self.calls.append(("query", request))
        return refusal_answer(
            _PRODUCER, _SNAPSHOT, ApiUsageLimitationCode.MEASUREMENT_WINDOW_NOT_AVAILABLE
        )

    def get_api_consumer_usage_evidence(self, request) -> ApiConsumerUsageAnswer:
        self.calls.append(("evidence", request))
        return refusal_answer(
            _PRODUCER, _SNAPSHOT, ApiUsageLimitationCode.SNAPSHOT_NOT_AVAILABLE, mode="evidence"
        )


def _client(service: _FakeService) -> TestClient:
    app = FastAPI()
    app.include_router(api_consumer_usage.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "body", "mode", "request_type"),
    [
        (_QUERY_PATH, _QUERY_BODY, "query", ApiConsumerUsageQueryRequest),
        (_EVIDENCE_PATH, _EVIDENCE_BODY, "evidence", ApiConsumerUsageEvidenceRequest),
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
        service.get_api_consumer_usage(request)
        if mode == "query"
        else service.get_api_consumer_usage_evidence(request)
    )
    # The service's own answer, a refusal here, is returned unchanged as a 200 (D1).
    assert response.json() == answer.model_dump(mode="json")


@pytest.mark.parametrize(
    ("path", "body"),
    [
        # Closed body: the route supplies the mode (D1).
        (_QUERY_PATH, {**_QUERY_BODY, "mode": "query"}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "mode": "evidence"}),
        (_QUERY_PATH, {**_QUERY_BODY, "cypher": "MATCH (n) RETURN n"}),
        # Malformed per the request model's own field rules.
        (_QUERY_PATH, {**_QUERY_BODY, "limit": 0}),
        (_QUERY_PATH, {**_QUERY_BODY, "limit": 201}),
        (_QUERY_PATH, {**_QUERY_BODY, "target": {"kind": "API_OPERATION", "id": "Orders API"}}),
        (_QUERY_PATH, {**_QUERY_BODY, "consumer_id": "spike-alpha"}),
        (
            _QUERY_PATH,
            {**_QUERY_BODY, "cursor": "not-a-cursor", "snapshot_id": _SNAPSHOT.snapshot_id},
        ),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "evidence_refs": []}),
        (_EVIDENCE_PATH, {**_EVIDENCE_BODY, "limit": 10}),
        # Malformed per the request model's cross-field rule (D3: a cursor needs its snapshot).
        (_QUERY_PATH, {**_QUERY_BODY, "cursor": "e30"}),
    ],
)
def test_a_malformed_body_is_a_422_that_never_reaches_the_service(path, body):
    service = _FakeService()

    response = _client(service).post(path, json=body)

    assert response.status_code == 422
    assert service.calls == []
