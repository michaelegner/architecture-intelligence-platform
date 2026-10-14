"""v0.7.0 I3.3: the fifth tool's MCP dispatch (I3 decision record D1).

The tool dispatches on `request.mode` to exactly one `ArchitectureIntelligenceService` method and
returns its `ApiConsumerUsageAnswer` unchanged as `structuredContent`. A stub service is injected
through `register_tools(server, get_service=...)`; real-service parity over the real transport is
`tests/integration/test_api_usage_surface_parity.py`.
"""

import httpx
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.api_usage_contracts import (
    API_USAGE_TOOL_NAME,
    ApiConsumerUsageAnswer,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
    ApiUsageLimitationCode,
)
from app.architecture_intelligence.api_usage_projection import refusal_answer
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.support.negotiated_mcp_client import call_negotiated

_ORIGIN = "http://localhost"
_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.7.0", build_revision="f" * 40
)
_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_CONTEXT = {
    "target": {"kind": "GATEWAY_ROUTE", "id": "gateway-route:owned:" + "b" * 64},
    "gateway_instance_id": "gw-prod-1",
    "environment": "prod",
    "window_start": "2026-10-13T10:00:00Z",
    "window_end": "2026-10-13T10:10:00Z",
}
_QUERY = {"mode": "query", **_CONTEXT}
_EVIDENCE = {
    "mode": "evidence",
    "snapshot_id": _SNAPSHOT.snapshot_id,
    "evidence_refs": ["api-evidence:" + "1" * 64],
    **_CONTEXT,
}


class _FakeService:
    """Records which method was called with what, and answers with a fixed refusal."""

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
            _PRODUCER,
            _SNAPSHOT,
            ApiUsageLimitationCode.SNAPSHOT_NOT_AVAILABLE,
            mode="evidence",
        )


async def _call(service: _FakeService, arguments: dict[str, object]) -> dict:
    server = MCPServer(name="test", version="0.7.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(allowed_origins=[_ORIGIN], allowed_hosts=["localhost"], server=server)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
            return await call_negotiated(
                client, origin=_ORIGIN, name=API_USAGE_TOOL_NAME, arguments=arguments
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_body", "mode", "request_type", "method"),
    [
        (_QUERY, "query", ApiConsumerUsageQueryRequest, "get_api_consumer_usage"),
        (_EVIDENCE, "evidence", ApiConsumerUsageEvidenceRequest, "get_api_consumer_usage_evidence"),
    ],
)
async def test_each_mode_reaches_exactly_its_own_service_method(
    request_body, mode, request_type, method
):
    service = _FakeService()

    result = await _call(service, {"request": request_body})

    assert result["isError"] is False
    assert [(called, type(request)) for called, request in service.calls] == [(mode, request_type)]
    expected = getattr(service, method)(request_type.model_validate(request_body))
    assert result["structuredContent"] == expected.model_dump(mode="json")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "request_body",
    [
        {**_QUERY, "mode": "graph"},
        {**_QUERY, "limit": 0},
        {**_QUERY, "cypher": "MATCH (n) RETURN n"},
        {**_EVIDENCE, "evidence_refs": []},
    ],
)
async def test_a_malformed_request_never_reaches_the_service(request_body):
    service = _FakeService()

    result = await _call(service, {"request": request_body})

    assert result["isError"] is True
    assert service.calls == []


@pytest.mark.asyncio
async def test_an_unexpected_top_level_argument_never_reaches_the_service():
    """Rejected by the closed argument model before dispatch (D1)."""
    service = _FakeService()

    result = await _call(service, {"request": _QUERY, "junk": 1})

    assert result["isError"] is True
    assert service.calls == []


@pytest.mark.asyncio
async def test_an_unexpected_service_failure_is_sanitized():
    class Failing(_FakeService):
        def get_api_consumer_usage(self, request):
            raise RuntimeError("bolt://secret-host:7687 refused")

    result = await _call(Failing(), {"request": _QUERY})

    assert result["isError"] is True
    assert "secret-host" not in str(result)
