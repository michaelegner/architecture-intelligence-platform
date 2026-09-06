"""v0.4.0 I3.2 - `get_architecture_drift`'s real MCP dispatch body (I3 spec §23, §46, §49's "MCP"
unit-test list).

Exercised against a stub `ArchitectureIntelligenceService`-shaped object injected via
`register_tools(server, get_service=...)` - no Neo4j, no real driver. Same structure as
`tests/unit/test_mcp_service_dependencies_adapter.py`; real-service equivalence and read-only proof
live in `tests/integration/test_mcp_architecture_drift_equivalence.py`, where a real driver is
available. Reuses `tests/fixtures/architecture_intelligence/i3/`'s fixtures, which are themselves
derived from the frozen I1 dependency fixtures by running the real `project_architecture_drift`
(I3.1) - so a "drift"/"empty"/"refusal" answer here is provably still I3-shaped, not a hand-rolled
approximation.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pydantic
import pytest
from mcp.server import MCPServer
from pydantic import ValidationError

from app.architecture_intelligence.contracts import ArchitectureAnswer, ArchitectureDriftData
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools

_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"
_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "architecture_intelligence" / "i3"
)
_ANSWER_TYPE = ArchitectureAnswer[ArchitectureDriftData]


def _load_answer(name: str) -> ArchitectureAnswer[ArchitectureDriftData]:
    return _ANSWER_TYPE.model_validate(json.loads((_FIXTURES_DIR / name).read_text()))


class _FakeService:
    """Duck-typed stand-in for `ArchitectureIntelligenceService` - the adapter only ever calls
    `.get_architecture_drift(request)`, so nothing else needs implementing."""

    def __init__(self, *, answer=None, raises: Exception | None = None) -> None:
        self._answer = answer
        self._raises = raises
        self.call_count = 0
        self.received_request = None

    def get_architecture_drift(self, request):
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
        "params": {"name": "get_architecture_drift", "arguments": arguments, "_meta": _meta()},
    }


async def _call(client: httpx.AsyncClient, arguments: dict[str, object]) -> dict:
    response = await client.post(
        "/mcp", headers=_headers(name="get_architecture_drift"), json=_call_body(arguments)
    )
    assert response.status_code == 200
    return response.json()["result"]


@pytest.mark.asyncio
async def test_drift_answer_round_trips_unchanged() -> None:
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
async def test_empty_drift_answer_round_trips_unchanged() -> None:
    """I3 spec §18.2: empty drift is a successful answer, not a refusal - the adapter must not
    special-case it."""
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
            result = await _call(client, {"request": {"service_id": "service:invoice-service"}})
            assert result["isError"] is False
            assert result["structuredContent"] == answer.model_dump(mode="json")
            assert result["structuredContent"]["outcome"] == "ANSWERED"
            assert result["structuredContent"]["claims"] == []


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
            result = await _call(client, {"request": {"service_id": "service:order-service"}})
            # I3 spec §23 rule 4/spec §10 rule 5 (shared envelope): NOT_ANSWERED is a successful
            # tool execution, not isError.
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
async def test_reversed_observation_window_is_caught_before_dispatch() -> None:
    """A malformed observation-context *value* (I3 spec §46's "Invalid tool arguments") is
    pre-validated by the adapter itself, before calling the service at all - proves the shared
    `app.mcp.tools._reject_malformed_observation_context` helper fires for the drift tool too, not
    only `get_service_dependencies`."""
    service = _FakeService()
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call(
                client,
                {
                    "request": {
                        "service_id": "service:order-service",
                        "observation_context": {
                            "environment": "demo",
                            "window_start": "2026-08-27T00:00:00.000000Z",
                            "window_end": "2026-08-26T00:00:00.000000Z",
                        },
                    }
                },
            )
            assert result["isError"] is True
            assert "window_start" in result["content"][0]["text"]
            assert service.call_count == 0


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
            assert text == "Error executing tool get_architecture_drift"


@pytest.mark.asyncio
async def test_unexpected_validation_error_from_service_is_sanitized_not_leaked() -> None:
    """Regression test mirroring the dependency adapter's own: a `pydantic.ValidationError` raised
    from *inside* the service (a corrupted internal model, not the caller's own observation-context
    input) must be sanitized like any other unexpected failure, not echoed back verbatim."""

    class _InternalModel(pydantic.BaseModel):
        internal_field: int

    try:
        _InternalModel.model_validate({"internal_field": "sk-internal-secret-do-not-leak"})
        validation_error = None
    except ValidationError as exc:
        validation_error = exc
    assert validation_error is not None
    assert "sk-internal-secret-do-not-leak" in str(validation_error)

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
            text = result["content"][0]["text"]
            assert "sk-internal-secret-do-not-leak" not in text
            assert text == "Error executing tool get_architecture_drift"
