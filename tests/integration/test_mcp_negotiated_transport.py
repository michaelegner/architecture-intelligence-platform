"""v0.4.2 I1 Neo4j-integration coverage, reworked in v0.5.0 I3 slice 5a: the v0.4.x direct MCP
envelope is retired (spec §14.1, ADR 0016), so `POST /mcp` serves standard negotiated MCP only - this
file's own direct-vs-negotiated equivalence tests are moot (there is only one mode left) and were
removed; what remains is the base negotiated-only contract this project now relies on for every real
client. `docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md` §14/§29 (as amended for v0.5.0) -
the mandatory negotiated flow, and negotiated Origin/Host security, need a real driver and real
imported services to mean anything. The generic routing/rejection behavior itself (HTTP method
contract, malformed-JSON handling, the retired-era rejection) is unit-tested against a stub service
in `tests/unit/test_mcp_discovery.py` - this file only covers what specifically requires real graph
data: that the negotiated path's results are real architecture facts, not just that it's reachable.

Mirrors `tests/integration/test_mcp_architecture_drift_equivalence.py`'s fixture setup so this
exercises the exact same graph state that suite already qualifies against.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.sources.model import FilesystemSourceConfig
from tests.support.negotiated_mcp_client import (
    call_negotiated,
    negotiated_headers,
    negotiated_initialize_body,
    negotiated_tools_list_body,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _build_server_and_app(driver):
    service = _service(driver)
    server = MCPServer(name="test", version="0.5.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    return server, app


def _request_payload(service_id: str) -> dict:
    return {
        "service_id": service_id,
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }


@pytest.mark.asyncio
async def test_mandatory_negotiated_flow_against_real_data(driver):
    """spec §14/§29: initialize -> tools/list -> get_architecture_drift -> get_evidence at the same
    snapshot -> disconnect -> fresh reconnect, all against real imported graph state."""
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-negotiated-transport-examples", root=EXAMPLES_DIR
        ),
    )
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            init_response = await client.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN, protocol_version=None),
                json=negotiated_initialize_body(),
            )
            assert init_response.status_code == 200
            assert init_response.json()["result"]["protocolVersion"] == "2025-11-25"

            list_response = await client.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN),
                json=negotiated_tools_list_body(),
            )
            assert list_response.status_code == 200
            names = [t["name"] for t in list_response.json()["result"]["tools"]]
            assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]

            drift_result = await call_negotiated(
                client,
                origin=_ALLOWED_ORIGIN,
                name="get_architecture_drift",
                arguments={"request": _request_payload(ids.service_id("order-service"))},
            )
            assert drift_result["isError"] is False
            drift_content = drift_result["structuredContent"]
            assert drift_content["claims"]
            snapshot_id = drift_content["snapshot"]["snapshot_id"]
            evidence_id = min(drift_content["claims"][0]["evidence_refs"])

            evidence_result = await call_negotiated(
                client,
                origin=_ALLOWED_ORIGIN,
                name="get_evidence",
                arguments={"request": {"evidence_refs": [evidence_id], "snapshot_id": snapshot_id}},
            )
            assert evidence_result["isError"] is False
            assert evidence_result["structuredContent"]["data"]["missing_evidence_refs"] == []

        # Disconnect (the `async with` above closed the client), then a fresh reconnect - a
        # brand-new client re-negotiating from scratch against the same mounted app.
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client2:
            reinit = await client2.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN, protocol_version=None),
                json=negotiated_initialize_body(),
            )
            assert reinit.status_code == 200
            relist = await client2.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN),
                json=negotiated_tools_list_body(request_id=99),
            )
            assert relist.status_code == 200
            assert len(relist.json()["result"]["tools"]) == 3


@pytest.mark.asyncio
async def test_negotiated_origin_and_host_security_matches_direct_mode(driver):
    """spec §20/§33: Origin/Host protection applies to negotiated POST traffic - the sole remaining
    mode introduces no bypass (name retained from the v0.4.2-era dual-mode test this generalizes;
    "direct mode" is now history, not a live comparison point)."""
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-negotiated-transport-examples", root=EXAMPLES_DIR
        ),
    )
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            allowed = await client.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN),
                json=negotiated_tools_list_body(),
            )
            assert allowed.status_code == 200

            disallowed_headers = dict(
                negotiated_headers(origin=_ALLOWED_ORIGIN), origin="http://evil.example"
            )
            disallowed = await client.post(
                "/mcp", headers=disallowed_headers, json=negotiated_tools_list_body()
            )
            assert disallowed.status_code == 403
