"""v0.4.0 I2.3 - `get_evidence`'s real MCP dispatch body (spec §11, §16, §17's "Evidence
Drill-Down" scenarios 9-16, minus the Neo4j-only ones).

Exercised against a stub `ArchitectureIntelligenceService`-shaped object injected via
`register_tools(server, get_service=...)` - no Neo4j, no real driver. Same structure as
`tests/unit/test_mcp_service_dependencies_adapter.py`; real-service equivalence and read-only proof
live in `tests/integration/test_mcp_evidence_equivalence.py`, where a real driver is available.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import ArchitectureAnswer, EvidenceData
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.support.negotiated_mcp_client import call_negotiated

_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"
_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "architecture_intelligence" / "i2"
)
_ANSWER_TYPE = ArchitectureAnswer[EvidenceData]
_VALID_SNAPSHOT_ID = "aip:snapshot:v1:" + "a" * 64


def _load_answer(name: str) -> ArchitectureAnswer[EvidenceData]:
    return _ANSWER_TYPE.model_validate(json.loads((_FIXTURES_DIR / name).read_text()))


class _FakeService:
    """Duck-typed stand-in for `ArchitectureIntelligenceService` - the adapter only ever calls
    `.get_evidence(request)`, so nothing else needs implementing."""

    def __init__(self, *, answer=None, raises: Exception | None = None) -> None:
        self._answer = answer
        self._raises = raises
        self.call_count = 0
        self.received_request = None

    def get_evidence(self, request):
        self.call_count += 1
        self.received_request = request
        if self._raises is not None:
            raise self._raises
        return self._answer


async def _call(client: httpx.AsyncClient, arguments: dict[str, object]) -> dict:
    return await call_negotiated(
        client, origin=_ALLOWED_ORIGIN, name="get_evidence", arguments=arguments
    )


@pytest.mark.asyncio
async def test_answered_evidence_round_trips_unchanged() -> None:
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
            result = await _call(
                client,
                {
                    "request": {
                        "evidence_refs": answer.data.requested_evidence_refs,
                        "snapshot_id": _VALID_SNAPSHOT_ID,
                    }
                },
            )
            assert result["isError"] is False
            assert result["structuredContent"] == answer.model_dump(mode="json")
            assert service.call_count == 1
            assert service.received_request.snapshot_id == _VALID_SNAPSHOT_ID


@pytest.mark.asyncio
async def test_stale_snapshot_refusal_retains_exact_meaning() -> None:
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
            result = await _call(
                client,
                {
                    "request": {
                        "evidence_refs": ["evidence:declared:a"],
                        "snapshot_id": _VALID_SNAPSHOT_ID,
                    }
                },
            )
            # spec §10 rule 5 (reused for get_evidence): NOT_ANSWERED is a successful tool execution.
            assert result["isError"] is False
            assert result["structuredContent"] == answer.model_dump(mode="json")
            assert result["structuredContent"]["outcome"] == "NOT_ANSWERED"


@pytest.mark.asyncio
async def test_two_identical_calls_produce_identical_structured_content() -> None:
    answer = _load_answer("partial_insufficient_evidence.json")
    service = _FakeService(answer=answer)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            arguments = {
                "request": {
                    "evidence_refs": answer.data.requested_evidence_refs,
                    "snapshot_id": _VALID_SNAPSHOT_ID,
                }
            }
            first = await _call(client, arguments)
            second = await _call(client, arguments)
            assert first["structuredContent"] == second["structuredContent"]
            assert service.call_count == 2


@pytest.mark.asyncio
async def test_malformed_arguments_are_caught_before_dispatch() -> None:
    """Empty/duplicate/oversized/missing-snapshot inputs fail at the closed input schema, never
    reaching the service (spec §17 scenario 15)."""
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
                client, {"request": {"evidence_refs": [], "snapshot_id": _VALID_SNAPSHOT_ID}}
            )
            assert result["isError"] is True
            assert service.call_count == 0

            result = await _call(
                client,
                {
                    "request": {
                        "evidence_refs": ["evidence:declared:a", "evidence:declared:a"],
                        "snapshot_id": _VALID_SNAPSHOT_ID,
                    }
                },
            )
            assert result["isError"] is True
            assert service.call_count == 0

            result = await _call(client, {"request": {"evidence_refs": ["evidence:declared:a"]}})
            assert result["isError"] is True
            assert service.call_count == 0


@pytest.mark.asyncio
async def test_unexpected_service_failure_is_sanitized_not_leaked() -> None:
    """Regression test mirroring the dependency adapter's: a driver-shaped exception whose message
    embeds connection detail must not reach the client (spec §15/§20)."""
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
            result = await _call(
                client,
                {
                    "request": {
                        "evidence_refs": ["evidence:declared:a"],
                        "snapshot_id": _VALID_SNAPSHOT_ID,
                    }
                },
            )
            assert result["isError"] is True
            text = result["content"][0]["text"]
            assert "internal-neo4j.example" not in text
            assert "7687" not in text
            assert text == "Error executing tool get_evidence"
