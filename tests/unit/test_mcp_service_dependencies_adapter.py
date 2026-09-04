"""v0.4.0 I2.2 - `get_service_dependencies`'s real MCP dispatch body (spec §10, §16, §17's
"Dependency Adapter" scenarios 5-8).

Exercised against a stub `ArchitectureIntelligenceService`-shaped object injected via
`register_tools(server, get_service=...)` - no Neo4j, no real driver. Real-service equivalence and
read-only proof (spec §17 items 5, 7, 8, 17, 18, 20) live in
`tests/integration/test_mcp_service_dependencies_equivalence.py`, where a real driver is available to
compare against. Reuses I1's own frozen fixtures (`tests/fixtures/architecture_intelligence/i1/`) for
the returned answers, so a "confirmed"/"safe-refusal" answer here is provably still I1-shaped, not a
hand-rolled approximation.

Same one-test-per-server-lifecycle structure as `test_mcp_discovery.py`, for the same reason
(`MCPServer.session_manager.run()`'s task group must be entered/exited by one asyncio Task).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pydantic
import pytest
from mcp.server import MCPServer
from pydantic import ValidationError

from app.architecture_intelligence.contracts import ArchitectureAnswer, ServiceDependenciesData
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools

_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"
_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "architecture_intelligence" / "i1"
)
_ANSWER_TYPE = ArchitectureAnswer[ServiceDependenciesData]


def _load_answer(name: str) -> ArchitectureAnswer[ServiceDependenciesData]:
    return _ANSWER_TYPE.model_validate(json.loads((_FIXTURES_DIR / name).read_text()))


class _FakeService:
    """Duck-typed stand-in for `ArchitectureIntelligenceService` - the adapter only ever calls
    `.get_service_dependencies(request)`, so nothing else needs implementing."""

    def __init__(self, *, answer=None, raises: Exception | None = None) -> None:
        self._answer = answer
        self._raises = raises
        self.call_count = 0
        self.received_request = None

    def get_service_dependencies(self, request):
        self.call_count += 1
        self.received_request = request
        if self._raises is not None:
            raise self._raises
        return self._answer


def _meta() -> dict[str, object]:
    return {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _headers(*, name: str) -> dict[str, str]:
    return {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
        "mcp-method": "tools/call",
        "mcp-name": name,
        "mcp-protocol-version": "2026-07-28",
    }


def _call_body(arguments: dict[str, object], request_id: int = 1) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": "get_service_dependencies", "arguments": arguments, "_meta": _meta()},
    }


async def _call(client: httpx.AsyncClient, arguments: dict[str, object]) -> dict:
    response = await client.post(
        "/mcp", headers=_headers(name="get_service_dependencies"), json=_call_body(arguments)
    )
    assert response.status_code == 200
    return response.json()["result"]


@pytest.mark.asyncio
async def test_confirmed_answer_round_trips_unchanged() -> None:
    answer = _load_answer("answered_full.json")
    service = _FakeService(answer=answer)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call(client, {"request": {"service_id": "service:order-service"}})
            assert result["isError"] is False
            assert result["structuredContent"] == answer.model_dump(mode="json")
            assert service.call_count == 1
            assert service.received_request.service_id == "service:order-service"


@pytest.mark.asyncio
async def test_safe_refusal_answer_retains_exact_meaning() -> None:
    answer = _load_answer("not_answered_snapshot_not_available.json")
    service = _FakeService(answer=answer)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call(client, {"request": {"service_id": "service:invoice-service"}})
            # spec §10 rule 5: NOT_ANSWERED is a successful tool execution.
            assert result["isError"] is False
            assert result["structuredContent"] == answer.model_dump(mode="json")
            assert result["structuredContent"]["outcome"] == "NOT_ANSWERED"


@pytest.mark.asyncio
async def test_two_identical_calls_produce_identical_structured_content() -> None:
    answer = _load_answer("answered_empty.json")
    service = _FakeService(answer=answer)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            arguments = {"request": {"service_id": "service:invoice-service"}}
            first = await _call(client, arguments)
            second = await _call(client, arguments)
            assert first["structuredContent"] == second["structuredContent"]
            assert service.call_count == 2


@pytest.mark.asyncio
async def test_service_validation_error_surfaces_as_actionable_tool_error() -> None:
    """A malformed observation-context *value* (spec §16's "Invalid tool arguments" raised by the
    service, not the SDK's own schema check - see app.architecture_intelligence.request's docstring)
    must map to isError: true with the validation detail visible, not a generic internal error."""

    class _Probe(pydantic.BaseModel):
        window_end: int

    try:
        _Probe.model_validate({"window_end": "not-an-int"})
        validation_error = None
    except ValidationError as exc:
        validation_error = exc
    assert validation_error is not None
    service = _FakeService(raises=validation_error)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call(client, {"request": {"service_id": "service:order-service"}})
            assert result["isError"] is True
            assert "window_end" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_unexpected_service_failure_is_sanitized_not_leaked() -> None:
    """Regression test for the exact leak this adapter must never reintroduce: a driver-shaped
    exception whose message embeds connection detail must not reach the client (spec §15/§20)."""
    secret_bearing_error = RuntimeError(
        "Failed to establish connection to ('internal-neo4j.example', 7687)"
    )
    service = _FakeService(raises=secret_bearing_error)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call(client, {"request": {"service_id": "service:order-service"}})
            assert result["isError"] is True
            text = result["content"][0]["text"]
            assert "internal-neo4j.example" not in text
            assert "7687" not in text
            assert text == "Error executing tool get_service_dependencies"


@pytest.mark.asyncio
async def test_get_evidence_still_not_implemented() -> None:
    service = _FakeService()
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_evidence",
                    "arguments": {
                        "request": {
                            "evidence_refs": ["x"],
                            "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
                        }
                    },
                    "_meta": _meta(),
                },
            }
            response = await client.post("/mcp", headers=_headers(name="get_evidence"), json=body)
            result = response.json()["result"]
            assert result["isError"] is True
            assert "not yet implemented" in result["content"][0]["text"]
            assert service.call_count == 0
