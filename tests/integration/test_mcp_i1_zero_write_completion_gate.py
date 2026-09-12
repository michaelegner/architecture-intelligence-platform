"""v0.4.2 I3 - closes a real gap found while writing the retrospective I1 completion record (spec
`docs/specifications/0.4.2/i3-client-qualification-and-release-preparation.md` §3.1/§3.3/§8.3
"automated zero-write result"): today's zero-write evidence is real but split across three per-tool,
**direct-mode-only** files (`test_mcp_service_dependencies_equivalence.py`,
`test_mcp_architecture_drift_equivalence.py`, `test_mcp_evidence_equivalence.py`), each proving one
tool leaves the revision fence unchanged. None of them - nor any other file - proves "zero graph
writes across *all* I1 routing paths" (direct AND negotiated, all three tools, including
malformed/rejected requests) in one consolidated run, which is exactly what the I1 completion record
needs to cite as evidence.

This file complements those three rather than duplicating their broader semantic-equivalence
assertions: it brackets one `read_revision` before/after a single sequence exercising every I1 routing
path - direct-mode success (all three tools) and rejection (malformed body, unsupported HTTP method),
negotiated-mode success (all three tools, via a real `initialize` handshake) and rejection (malformed
body, unsupported protocol version) - and asserts the fence never advanced across the whole run.
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
from app.graph.revision_fence import read_revision
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
async def test_zero_graph_writes_across_every_i1_routing_path(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)

    server, app = _build_server_and_app(driver)
    service_id = ids.service_id("order-service")
    payload = {"request": _request_payload(service_id)}

    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            # --- direct mode: success (all three tools) --------------------------------------
            drift = await _call_direct(client, "get_architecture_drift", payload)
            assert drift["isError"] is False
            drift_content = drift["structuredContent"]
            snapshot_id = drift_content["snapshot"]["snapshot_id"]
            evidence_id = min(drift_content["claims"][0]["evidence_refs"])
            evidence_payload = {
                "request": {"evidence_refs": [evidence_id], "snapshot_id": snapshot_id}
            }

            deps = await _call_direct(client, "get_service_dependencies", payload)
            assert deps["isError"] is False

            direct_evidence = await _call_direct(client, "get_evidence", evidence_payload)
            assert direct_evidence["isError"] is False

            # --- direct mode: rejection (malformed body, unsupported HTTP method) ------------
            malformed_direct = await client.post(
                "/mcp",
                headers=dict(_negotiated_headers(), **{"mcp-method": "tools/list"}),
                content=b"{not valid json",
            )
            assert malformed_direct.status_code == 400

            method_rejected = await client.get("/mcp", headers={"origin": _ALLOWED_ORIGIN})
            assert method_rejected.status_code == 405

            # --- negotiated mode: success (real initialize handshake, all three tools) -------
            init_response = await client.post(
                "/mcp",
                headers=_negotiated_headers(protocol_version=None),
                json=_negotiated_initialize_body(),
            )
            assert init_response.status_code == 200

            negotiated_drift = await _call_negotiated(client, "get_architecture_drift", payload)
            assert negotiated_drift["isError"] is False

            negotiated_deps = await _call_negotiated(client, "get_service_dependencies", payload)
            assert negotiated_deps["isError"] is False

            negotiated_evidence = await _call_negotiated(client, "get_evidence", evidence_payload)
            assert negotiated_evidence["isError"] is False

            # --- negotiated mode: rejection (malformed body, unsupported protocol version) ---
            malformed_negotiated = await client.post(
                "/mcp", headers=_negotiated_headers(), content=b"{not valid json"
            )
            assert malformed_negotiated.status_code == 400

            bad_protocol_version = await client.post(
                "/mcp",
                headers=_negotiated_headers(protocol_version="garbage-2099"),
                json=_negotiated_call_body("get_service_dependencies", payload),
            )
            assert bad_protocol_version.status_code == 400

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    assert revision_after == revision_before
