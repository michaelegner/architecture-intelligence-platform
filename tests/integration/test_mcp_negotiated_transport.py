"""v0.4.2 I1 Neo4j-integration coverage: `docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md`
§14/§18/§29/§31/§32 - the mandatory negotiated flow, direct-vs-negotiated semantic equivalence, and
cross-mode snapshot interoperability, all of which need a real driver and real imported services to
mean anything. The generic routing/rejection behavior itself (the routing truth table, HTTP method
contract, malformed-JSON ownership) is unit-tested against a stub service in
`tests/unit/test_mcp_discovery.py` - this file only covers what specifically requires real graph
data: that the negotiated path's results are the *same architecture facts* the direct path returns,
not just that it's reachable.

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

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.2", build_revision="f" * 40
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
    server = MCPServer(name="test", version="0.4.2")
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


# --- Direct-mode request builders (unchanged v0.4.0/v0.4.1 envelope) ------------------------------


def _direct_meta() -> dict[str, object]:
    return {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _direct_headers(*, name: str) -> dict[str, str]:
    return {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
        "mcp-method": "tools/call",
        "mcp-name": name,
        "mcp-protocol-version": "2026-07-28",
    }


def _direct_call_body(name: str, arguments: dict, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments, "_meta": _direct_meta()},
    }


async def _call_direct(client: httpx.AsyncClient, name: str, arguments: dict) -> dict:
    response = await client.post(
        "/mcp", headers=_direct_headers(name=name), json=_direct_call_body(name, arguments)
    )
    assert response.status_code == 200
    return response.json()["result"]


# --- Negotiated-mode request builders (v0.4.2 I1, no AIP direct-envelope markers) -----------------


def _negotiated_headers(*, protocol_version: str | None = "2025-11-25") -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
    }
    if protocol_version is not None:
        headers["mcp-protocol-version"] = protocol_version
    return headers


def _negotiated_initialize_body(request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test-negotiated-client", "version": "0.0.0"},
        },
    }


def _negotiated_tools_list_body(request_id: int = 2) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}


def _negotiated_call_body(name: str, arguments: dict, request_id: int = 3) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


async def _call_negotiated(client: httpx.AsyncClient, name: str, arguments: dict) -> dict:
    response = await client.post(
        "/mcp", headers=_negotiated_headers(), json=_negotiated_call_body(name, arguments)
    )
    assert response.status_code == 200
    return response.json()["result"]


@pytest.mark.asyncio
async def test_mandatory_negotiated_flow_against_real_data(driver):
    """spec §14/§29: initialize -> tools/list -> get_architecture_drift -> get_evidence at the same
    snapshot -> disconnect -> fresh reconnect, all against real imported graph state."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            init_response = await client.post(
                "/mcp",
                headers=_negotiated_headers(protocol_version=None),
                json=_negotiated_initialize_body(),
            )
            assert init_response.status_code == 200
            assert init_response.json()["result"]["protocolVersion"] == "2025-11-25"

            list_response = await client.post(
                "/mcp", headers=_negotiated_headers(), json=_negotiated_tools_list_body()
            )
            assert list_response.status_code == 200
            names = [t["name"] for t in list_response.json()["result"]["tools"]]
            assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]

            drift_result = await _call_negotiated(
                client,
                "get_architecture_drift",
                {"request": _request_payload(ids.service_id("order-service"))},
            )
            assert drift_result["isError"] is False
            drift_content = drift_result["structuredContent"]
            assert drift_content["claims"]
            snapshot_id = drift_content["snapshot"]["snapshot_id"]
            evidence_id = min(drift_content["claims"][0]["evidence_refs"])

            evidence_result = await _call_negotiated(
                client,
                "get_evidence",
                {"request": {"evidence_refs": [evidence_id], "snapshot_id": snapshot_id}},
            )
            assert evidence_result["isError"] is False
            assert evidence_result["structuredContent"]["data"]["missing_evidence_refs"] == []

        # Disconnect (the `async with` above closed the client), then a fresh reconnect - a
        # brand-new client re-negotiating from scratch against the same mounted app.
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client2:
            reinit = await client2.post(
                "/mcp",
                headers=_negotiated_headers(protocol_version=None),
                json=_negotiated_initialize_body(),
            )
            assert reinit.status_code == 200
            relist = await client2.post(
                "/mcp",
                headers=_negotiated_headers(),
                json=_negotiated_tools_list_body(request_id=99),
            )
            assert relist.status_code == 200
            assert len(relist.json()["result"]["tools"]) == 3


@pytest.mark.asyncio
async def test_direct_and_negotiated_structured_content_are_semantically_equivalent(driver):
    """spec §17/§31: equivalent direct and negotiated calls return the same `ArchitectureAnswer` -
    zero semantic mismatches - for all three tools."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            service_id = ids.service_id("order-service")
            payload = {"request": _request_payload(service_id)}

            for tool_name in ("get_architecture_drift", "get_service_dependencies"):
                direct = await _call_direct(client, tool_name, payload)
                negotiated = await _call_negotiated(client, tool_name, payload)
                assert direct["isError"] is False
                assert negotiated["isError"] is False
                assert direct["structuredContent"] == negotiated["structuredContent"]

            drift_content = (await _call_direct(client, "get_architecture_drift", payload))[
                "structuredContent"
            ]
            snapshot_id = drift_content["snapshot"]["snapshot_id"]
            evidence_id = min(drift_content["claims"][0]["evidence_refs"])
            evidence_payload = {
                "request": {"evidence_refs": [evidence_id], "snapshot_id": snapshot_id}
            }

            direct_evidence = await _call_direct(client, "get_evidence", evidence_payload)
            negotiated_evidence = await _call_negotiated(client, "get_evidence", evidence_payload)
            assert direct_evidence["structuredContent"] == negotiated_evidence["structuredContent"]


@pytest.mark.asyncio
async def test_cross_mode_snapshot_interoperability_both_directions(driver):
    """spec §11/§18/§32/§35: a claim/evidence pair obtained via one mode resolves successfully
    through `get_evidence` called via the *other* mode, at the same `snapshot_id`, in both
    directions - connection mode never creates a separate consistency domain."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            payload = {"request": _request_payload(ids.service_id("order-service"))}

            # Case A: negotiated claim, direct evidence.
            negotiated_drift = await _call_negotiated(client, "get_architecture_drift", payload)
            drift_content_a = negotiated_drift["structuredContent"]
            snapshot_a = drift_content_a["snapshot"]["snapshot_id"]
            evidence_id_a = min(drift_content_a["claims"][0]["evidence_refs"])
            evidence_a = await _call_direct(
                client,
                "get_evidence",
                {"request": {"evidence_refs": [evidence_id_a], "snapshot_id": snapshot_a}},
            )
            assert evidence_a["isError"] is False
            assert evidence_a["structuredContent"]["data"]["missing_evidence_refs"] == []

            # Case B: direct claim, negotiated evidence.
            direct_drift = await _call_direct(client, "get_architecture_drift", payload)
            drift_content_b = direct_drift["structuredContent"]
            snapshot_b = drift_content_b["snapshot"]["snapshot_id"]
            evidence_id_b = min(drift_content_b["claims"][0]["evidence_refs"])
            evidence_b = await _call_negotiated(
                client,
                "get_evidence",
                {"request": {"evidence_refs": [evidence_id_b], "snapshot_id": snapshot_b}},
            )
            assert evidence_b["isError"] is False
            assert evidence_b["structuredContent"]["data"]["missing_evidence_refs"] == []

            assert snapshot_a == snapshot_b


@pytest.mark.asyncio
async def test_negotiated_origin_and_host_security_matches_direct_mode(driver):
    """spec §20/§33: existing Origin/Host protection applies to negotiated POST traffic exactly as
    it already does to direct traffic - the negotiated path introduces no bypass."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            allowed = await client.post(
                "/mcp", headers=_negotiated_headers(), json=_negotiated_tools_list_body()
            )
            assert allowed.status_code == 200

            disallowed_headers = dict(_negotiated_headers(), origin="http://evil.example")
            disallowed = await client.post(
                "/mcp", headers=disallowed_headers, json=_negotiated_tools_list_body()
            )
            assert disallowed.status_code == 403
