"""v0.4.0 I3.2 Neo4j-integration coverage: I3 spec §50's "direct drift vs MCP equivalence" and
"drift -> evidence drill-down" items - the parts of the required test matrix that need a real
driver, real imported services, and a real revision fence to mean anything. Adapter-level
dispatch/error-mapping against a stub service is
`tests/unit/test_mcp_architecture_drift_adapter.py`'s job.

Mirrors `tests/integration/test_mcp_service_dependencies_equivalence.py`'s structure exactly, so a
"drift"/"empty drift"/"refusal" answer here is exercising the exact same graph state I1/I3.1's own
suites already qualify against.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import jsonschema
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Outcome, Producer
from app.architecture_intelligence.request import ArchitectureDriftRequest
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
    / "drift-answer.schema.json"
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

DRIFT_ANSWER_SCHEMA = json.loads(SCHEMA_PATH.read_text())


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


def _request(service_id: str, **overrides) -> ArchitectureDriftRequest:
    return ArchitectureDriftRequest.model_validate(_request_payload(service_id, **overrides))


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


def _headers(*, name: str = "get_architecture_drift") -> dict[str, str]:
    return {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
        "mcp-method": "tools/call",
        "mcp-name": name,
        "mcp-protocol-version": "2026-07-28",
    }


def _call_body(name: str, request_payload: dict, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": {"request": request_payload},
            "_meta": _meta(),
        },
    }


async def _call_mcp(client: httpx.AsyncClient, name: str, request_payload: dict) -> dict:
    response = await client.post(
        "/mcp", headers=_headers(name=name), json=_call_body(name, request_payload)
    )
    assert response.status_code == 200
    return response.json()["result"]


async def _call_drift(client: httpx.AsyncClient, request_payload: dict) -> dict:
    return await _call_mcp(client, "get_architecture_drift", request_payload)


@pytest.mark.asyncio
async def test_drift_answer_with_claims_is_identical_direct_vs_mcp(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    direct_json = (
        _service(driver)
        .get_architecture_drift(_request(ids.service_id("order-service")))
        .model_dump(mode="json")
    )
    assert direct_json["outcome"] in (Outcome.PARTIAL.value, Outcome.ANSWERED.value)
    assert direct_json["claims"]
    jsonschema.validate(instance=direct_json, schema=DRIFT_ANSWER_SCHEMA)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(client, _request_payload(ids.service_id("order-service")))
            assert result["isError"] is False
            jsonschema.validate(instance=result["structuredContent"], schema=DRIFT_ANSWER_SCHEMA)
            assert result["structuredContent"] == direct_json


@pytest.mark.asyncio
async def test_empty_drift_answer_is_identical_direct_vs_mcp(driver):
    """`product-service` only provides (I3 spec §18.2's zero-candidate empty-drift case) - a
    different envelope branch than the claim-bearing case above."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    direct_json = (
        _service(driver)
        .get_architecture_drift(_request(ids.service_id("product-service")))
        .model_dump(mode="json")
    )
    assert direct_json["outcome"] == Outcome.ANSWERED.value
    assert direct_json["claims"] == []
    jsonschema.validate(instance=direct_json, schema=DRIFT_ANSWER_SCHEMA)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(client, _request_payload(ids.service_id("product-service")))
            assert result["isError"] is False
            assert result["structuredContent"] == direct_json


@pytest.mark.asyncio
async def test_two_identical_mcp_drift_calls_produce_byte_identical_structured_content(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    server, app = _build_server_and_app(driver)
    payload = _request_payload(ids.service_id("order-service"))
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            first = await _call_drift(client, payload)
            second = await _call_drift(client, payload)
            assert first["structuredContent"] == second["structuredContent"]


@pytest.mark.asyncio
async def test_successful_mcp_drift_call_leaves_revision_fence_unchanged(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(client, _request_payload(ids.service_id("order-service")))
            assert result["isError"] is False

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before


@pytest.mark.asyncio
async def test_refusal_mcp_drift_call_leaves_revision_fence_unchanged(driver):
    """A stale/mismatched snapshot_id forces `NOT_ANSWERED`/`SNAPSHOT_NOT_AVAILABLE` - still zero
    graph writes (I3 spec §25)."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "a" * 64
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(
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
async def test_drift_evidence_refs_resolve_through_mcp_get_evidence_at_the_same_snapshot(driver):
    """I3 spec §22/§63's required drift -> evidence drill-down, proven through the MCP dispatch path
    (mirrors `test_architecture_intelligence_service.py`'s service-level version of this test, which
    already covers the direct-call path)."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            drift_result = await _call_drift(
                client, _request_payload(ids.service_id("order-service"))
            )
            drift_answer = drift_result["structuredContent"]
            assert drift_answer["evidence_refs"]

            evidence_result = await _call_mcp(
                client,
                "get_evidence",
                {
                    "evidence_refs": drift_answer["evidence_refs"],
                    "snapshot_id": drift_answer["snapshot"]["snapshot_id"],
                },
            )
            evidence_answer = evidence_result["structuredContent"]
            assert evidence_answer["outcome"] == "ANSWERED"
            assert evidence_answer["data"]["missing_evidence_refs"] == []
            assert [record["id"] for record in evidence_answer["data"]["records"]] == sorted(
                drift_answer["evidence_refs"]
            )
