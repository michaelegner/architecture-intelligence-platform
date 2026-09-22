"""v0.4.2 I3 - closes a real gap found while writing the retrospective I1 completion record (spec
`docs/specifications/0.4.2/i3-client-qualification-and-release-preparation.md` §3.1/§3.3/§8.3
"automated zero-write result"): zero-write evidence is real but split across three per-tool files
(`test_mcp_service_dependencies_equivalence.py`, `test_mcp_architecture_drift_equivalence.py`,
`test_mcp_evidence_equivalence.py`), each proving one tool leaves the revision fence unchanged. None
of them - nor any other file - proves "zero graph writes across every routing path" (all three
tools, including malformed/rejected requests) in one consolidated run, which is exactly what the I1
completion record needs to cite as evidence.

v0.5.0 I3 slice 5a retires the v0.4.x direct MCP envelope (ADR 0016, spec §14.1) - `POST /mcp` now
serves standard negotiated MCP only, so this file's own former "direct mode" success/rejection
sections are gone; what remains is one consolidated negotiated-only run (a real `initialize`
handshake, all three tools' success path, and the malformed-body/bad-protocol-version/unsupported-
HTTP-method rejection paths), still bracketed by one `read_revision` before/after.
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
from app.sources.model import FilesystemSourceConfig
from tests.support.negotiated_mcp_client import (
    call_negotiated,
    negotiated_call_body,
    negotiated_headers,
    negotiated_initialize_body,
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
async def test_zero_graph_writes_across_every_routing_path(driver):
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-i1-zero-write-completion-gate-examples", root=EXAMPLES_DIR
        ),
    )
    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)

    server, app = _build_server_and_app(driver)
    service_id = ids.service_id("order-service")
    payload = {"request": _request_payload(service_id)}

    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            # --- success: real initialize handshake, all three tools -------------------------
            init_response = await client.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN, protocol_version=None),
                json=negotiated_initialize_body(),
            )
            assert init_response.status_code == 200

            drift = await call_negotiated(
                client, origin=_ALLOWED_ORIGIN, name="get_architecture_drift", arguments=payload
            )
            assert drift["isError"] is False
            drift_content = drift["structuredContent"]
            snapshot_id = drift_content["snapshot"]["snapshot_id"]
            evidence_id = min(drift_content["claims"][0]["evidence_refs"])
            evidence_payload = {
                "request": {"evidence_refs": [evidence_id], "snapshot_id": snapshot_id}
            }

            deps = await call_negotiated(
                client,
                origin=_ALLOWED_ORIGIN,
                name="get_service_dependencies",
                arguments=payload,
            )
            assert deps["isError"] is False

            evidence = await call_negotiated(
                client, origin=_ALLOWED_ORIGIN, name="get_evidence", arguments=evidence_payload
            )
            assert evidence["isError"] is False

            # --- rejection: malformed body, unsupported protocol version, bad HTTP method -----
            malformed = await client.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN),
                content=b"{not valid json",
            )
            assert malformed.status_code == 400

            bad_protocol_version = await client.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN, protocol_version="garbage-2099"),
                json=negotiated_call_body("get_service_dependencies", payload),
            )
            assert bad_protocol_version.status_code == 400

            method_rejected = await client.get("/mcp", headers={"origin": _ALLOWED_ORIGIN})
            assert method_rejected.status_code == 405

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    assert revision_after == revision_before
