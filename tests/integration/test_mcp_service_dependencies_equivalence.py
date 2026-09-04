"""v0.4.0 I2.2 Neo4j-integration coverage: spec §17's "Dependency Adapter" scenarios 5, 7, 8 and
"Read-Only and Independent Client" scenarios 17, 18, 20 - the parts of the required test matrix that
need a real driver, real imported services, and a real revision fence to mean anything. Adapter-level
dispatch/error-mapping against a stub service is
`tests/unit/test_mcp_service_dependencies_adapter.py`'s job.

Mirrors `tests/integration/test_architecture_intelligence_service.py`'s fixture setup (the
`examples/` reference landscape via `import_all_sources`, the shared `driver` fixture, an autouse
`clean_database`) so a "confirmed"/"safe-refusal" answer here is exercising the exact same graph
state I1's own suite already qualifies against.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import jsonschema
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Outcome, Producer
from app.architecture_intelligence.request import ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.graph.revision_fence import read_revision
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.4"
    / "architecture-answer.schema.json"
)
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.0", build_revision="f" * 40
)

DEPENDENCY_ANSWER_SCHEMA = json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _request_payload(service_id: str, **overrides) -> dict:
    payload = {
        "service_id": service_id,
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }
    payload.update(overrides)
    return payload


def _request(service_id: str, **overrides) -> ServiceDependenciesRequest:
    return ServiceDependenciesRequest.model_validate(_request_payload(service_id, **overrides))


def _build_server_and_app(driver) -> tuple[MCPServer, object]:
    service = _service(driver)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    return server, app


def _meta() -> dict[str, object]:
    return {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _headers() -> dict[str, str]:
    return {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
        "mcp-method": "tools/call",
        "mcp-name": "get_service_dependencies",
        "mcp-protocol-version": "2026-07-28",
    }


def _call_body(request_payload: dict, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "get_service_dependencies",
            "arguments": {"request": request_payload},
            "_meta": _meta(),
        },
    }


async def _call_mcp(client: httpx.AsyncClient, request_payload: dict) -> dict:
    response = await client.post("/mcp", headers=_headers(), json=_call_body(request_payload))
    assert response.status_code == 200
    return response.json()["result"]


@pytest.mark.asyncio
async def test_confirmed_dependency_answer_is_identical_direct_vs_mcp(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    direct_json = (
        _service(driver)
        .get_service_dependencies(_request(ids.service_id("order-service")))
        .model_dump(mode="json")
    )
    assert direct_json["outcome"] in (Outcome.PARTIAL.value, Outcome.ANSWERED.value)
    jsonschema.validate(instance=direct_json, schema=DEPENDENCY_ANSWER_SCHEMA)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(client, _request_payload(ids.service_id("order-service")))
            assert result["isError"] is False
            jsonschema.validate(
                instance=result["structuredContent"], schema=DEPENDENCY_ANSWER_SCHEMA
            )
            assert result["structuredContent"] == direct_json


@pytest.mark.asyncio
async def test_provider_only_service_refusal_is_identical_direct_vs_mcp(driver):
    """`product-service` only provides, never calls/sends (see CLAUDE.md's `examples/` fixture
    description) - an ANSWERED-with-empty-claims outcome, not a claim-bearing one, exercising a
    different branch of the envelope invariants than the confirmed-answer case above."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    direct_json = (
        _service(driver)
        .get_service_dependencies(_request(ids.service_id("product-service")))
        .model_dump(mode="json")
    )
    assert direct_json["outcome"] == Outcome.ANSWERED.value
    assert direct_json["claims"] == []
    jsonschema.validate(instance=direct_json, schema=DEPENDENCY_ANSWER_SCHEMA)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(client, _request_payload(ids.service_id("product-service")))
            assert result["isError"] is False
            assert result["structuredContent"] == direct_json


@pytest.mark.asyncio
async def test_two_identical_mcp_calls_produce_byte_identical_structured_content(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    server, app = _build_server_and_app(driver)
    payload = _request_payload(ids.service_id("order-service"))
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            first = await _call_mcp(client, payload)
            second = await _call_mcp(client, payload)
            assert first["structuredContent"] == second["structuredContent"]


@pytest.mark.asyncio
async def test_successful_mcp_call_leaves_revision_fence_unchanged(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(client, _request_payload(ids.service_id("order-service")))
            assert result["isError"] is False

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before


@pytest.mark.asyncio
async def test_refusal_mcp_call_leaves_revision_fence_unchanged(driver):
    """A stale/mismatched snapshot_id forces `NOT_ANSWERED`/`SNAPSHOT_NOT_AVAILABLE` (spec §12) -
    still zero graph writes."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "a" * 64
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(
                client,
                _request_payload(ids.service_id("order-service"), snapshot_id=stale_snapshot_id),
            )
            assert result["isError"] is False
            assert result["structuredContent"]["outcome"] == "NOT_ANSWERED"
            assert result["structuredContent"]["limitations"][0]["code"] == "SNAPSHOT_NOT_AVAILABLE"

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before


@pytest.mark.asyncio
async def test_service_validation_error_leaves_revision_fence_unchanged(driver):
    """A reversed observation window raises `pydantic.ValidationError` deep inside the service
    (`app.architecture_intelligence.service`'s documented behavior) - `app.mcp.tools` maps this to
    `isError: true` (see `tests/unit/test_mcp_service_dependencies_adapter.py` for that mapping in
    isolation); here it must still leave the graph untouched end to end through the real MCP path."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    reversed_window_payload = _request_payload(
        ids.service_id("order-service"),
        observation_context={
            "environment": ENVIRONMENT,
            "window_start": WINDOW_END,
            "window_end": WINDOW_START,
        },
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(client, reversed_window_payload)
            assert result["isError"] is True

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before
