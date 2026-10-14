"""v0.7.0 I3.3: the independent I3 oracle executed through the REST and MCP adapters (matrix §7).

A stub service that answers from the case's world (no Neo4j: the projection over the world's
`snapshot_state` with the injected snapshot) stands behind the real REST router and the real
negotiated MCP tool. Every answer case must come back unchanged and equal to the expected answer
through both transports (the matrix §2 rules), every request case must be rejected by both, and the
credential canary (C01) must appear in no transport transcript. A real-Neo4j run of the same adapters
is `tests/integration/test_api_usage_surface_parity.py`."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import MCPServer

from app.api import api_consumer_usage, errors
from app.architecture_intelligence.api_usage_contracts import (
    API_USAGE_TOOL_NAME,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.api_usage_evidence import resolve_api_consumer_usage_evidence
from app.architecture_intelligence.api_usage_projection import project_api_consumer_usage
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.deps import get_architecture_intelligence_service
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.api_usage_oracle.matcher import first_difference
from tests.support.negotiated_mcp_client import call_negotiated

ORACLE = (
    Path(__file__).resolve().parents[2]
    / "docs/specifications/0.7.0/i3-vectors/expected-answers.json"
)
DOC = json.loads(ORACLE.read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in DOC["cases"]}
ANSWER_CASES = sorted(c for c, case in CASES.items() if case["kind"] == "answer")
REQUEST_CASES = sorted(c for c, case in CASES.items() if case["kind"] == "request")
CANARY = DOC["worlds"]["base"]["internal_only"]["credential_canary"]
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.0", build_revision="t")
ORIGIN = "http://localhost"
ROUTES = {"query": "/api/api-consumer-usage", "evidence": "/api/api-consumer-usage/evidence"}


class _WorldService:
    """The service contract over one oracle world; `use(case_id)` selects world and snapshot."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}
        self.snapshot: SnapshotRef | None = None
        self.calls = 0

    def use(self, case_id: str) -> None:
        case = CASES[case_id]
        self.state = DOC["worlds"][case["inputs"]["world"]]["snapshot_state"]
        self.snapshot = SnapshotRef(**DOC["snapshots"][case["inputs"]["current_snapshot"]])

    def get_api_consumer_usage(self, request: ApiConsumerUsageQueryRequest):
        self.calls += 1
        assert self.snapshot is not None
        return project_api_consumer_usage(
            request, self.state, snapshot=self.snapshot, producer=PRODUCER
        )

    def get_api_consumer_usage_evidence(self, request: ApiConsumerUsageEvidenceRequest):
        self.calls += 1
        assert self.snapshot is not None
        return resolve_api_consumer_usage_evidence(
            request, self.state, snapshot=self.snapshot, producer=PRODUCER
        )


SERVICE = _WorldService()


def _rest_client() -> TestClient:
    app = FastAPI()
    app.include_router(api_consumer_usage.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: SERVICE
    return TestClient(app)


def _body(request: dict) -> dict:
    return {key: value for key, value in request.items() if key != "mode"}


@pytest.mark.parametrize("case_id", ANSWER_CASES)
def test_rest_returns_the_expected_answer(case_id):
    case = CASES[case_id]
    SERVICE.use(case_id)

    response = _rest_client().post(ROUTES[case["request"]["mode"]], json=_body(case["request"]))

    assert response.status_code == 200
    assert first_difference(case["expected"], response.json()) is None


@pytest.mark.parametrize(
    "case_id", [c for c in REQUEST_CASES if CASES[c]["request"]["mode"] in ROUTES]
)
def test_rest_rejects_every_invalid_request_before_the_service(case_id):
    SERVICE.calls = 0
    request = CASES[case_id]["request"]

    response = _rest_client().post(ROUTES[request["mode"]], json=_body(request))

    assert response.status_code == 422
    assert SERVICE.calls == 0


@pytest.mark.asyncio
async def test_mcp_returns_the_expected_answers_and_rejects_the_invalid_requests():
    server = MCPServer(name="test", version="0.7.0")
    register_tools(server, get_service=lambda: SERVICE)
    app = build_mcp_app(allowed_origins=[ORIGIN], allowed_hosts=["localhost"], server=server)
    transcript: list[str] = []
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            for case_id in ANSWER_CASES:
                case = CASES[case_id]
                SERVICE.use(case_id)
                result = await call_negotiated(
                    client,
                    origin=ORIGIN,
                    name=API_USAGE_TOOL_NAME,
                    arguments={"request": case["request"]},
                )
                transcript.append(json.dumps(result))
                assert result["isError"] is False, case_id
                difference = first_difference(case["expected"], result["structuredContent"])
                assert difference is None, (case_id, difference)
            for case_id in REQUEST_CASES:
                SERVICE.calls = 0
                result = await call_negotiated(
                    client,
                    origin=ORIGIN,
                    name=API_USAGE_TOOL_NAME,
                    arguments={"request": CASES[case_id]["request"]},
                )
                transcript.append(json.dumps(result))
                assert result["isError"] is True and SERVICE.calls == 0, case_id
    assert CANARY not in "\n".join(transcript), "C01 over the MCP transcript"


def test_the_canary_is_in_no_rest_transcript():
    transcript = []
    for case_id in ANSWER_CASES:
        case = CASES[case_id]
        SERVICE.use(case_id)
        response = _rest_client().post(ROUTES[case["request"]["mode"]], json=_body(case["request"]))
        transcript.append(response.text)
    assert transcript and CANARY not in "\n".join(transcript)
