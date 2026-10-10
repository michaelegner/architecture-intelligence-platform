"""v0.6.0 I3.3b: the fourth tool's MCP dispatch (I3 decision record D1, D12).

The tool dispatches on `request.mode` to exactly one `ArchitectureIntelligenceService` method and
returns its `LocalityAnswer` unchanged as `structuredContent`. A stub service is injected through
`register_tools(server, get_service=...)`; real-service parity over the real transport is I3.3c.
"""

from __future__ import annotations

import httpx
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityEvidenceRequest,
    LocalityLimitationCode,
    LocalityQueryRequest,
)
from app.architecture_intelligence.locality_projection import refusal_answer
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.support.negotiated_mcp_client import call_negotiated

_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"
_TOOL = "get_service_dependencies_by_locality"
_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)
_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_QUERY = {
    "mode": "query",
    "subject_service_id": "service:orders",
    "environment": "production",
    "first_day": "2026-09-28",
    "last_day": "2026-09-28",
}
_EVIDENCE = {
    "mode": "evidence",
    "subject_service_id": "service:orders",
    "snapshot_id": _SNAPSHOT.snapshot_id,
    "refs": ["evidence:otel:calls-scoped:v2:" + "1" * 64],
}


class _FakeService:
    """Records which method was called with what, and answers with a fixed refusal."""

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


async def _call(service: _FakeService, arguments: dict[str, object]) -> dict:
    server = MCPServer(name="test", version="0.6.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            return await call_negotiated(
                client, origin=_ALLOWED_ORIGIN, name=_TOOL, arguments=arguments
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_body", "mode", "request_type", "method"),
    [
        (_QUERY, "query", LocalityQueryRequest, "get_service_dependencies_by_locality"),
        (_EVIDENCE, "evidence", LocalityEvidenceRequest, "resolve_scoped_locality_evidence"),
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
async def test_a_request_with_an_unknown_mode_never_reaches_the_service():
    service = _FakeService()

    result = await _call(service, {"request": {**_QUERY, "mode": "graph"}})

    assert result["isError"] is True
    assert service.calls == []


@pytest.mark.asyncio
async def test_an_unexpected_top_level_argument_never_reaches_the_service():
    """D12 over the negotiated transport: rejected by the closed argument model before dispatch."""
    service = _FakeService()

    result = await _call(service, {"request": _QUERY, "junk": 1})

    assert result["isError"] is True
    assert service.calls == []
