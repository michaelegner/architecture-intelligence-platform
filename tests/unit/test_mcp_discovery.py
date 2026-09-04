"""v0.4.0 I2.1 - MCP protocol/discovery tests (spec §17's "Protocol and Discovery" scenarios 1-4,
plus the two verified SDK gaps `app.mcp.guard` corrects and the request/response contract shape).

Tests against `app.mcp.app.build_mcp_app` directly (not the full `app.main` FastAPI app) with a real
`httpx.AsyncClient`/`ASGITransport` - a real HTTP round trip through the guard and the SDK, not the
SDK's own client, so this doesn't validate the SDK against itself. No Neo4j/settings dependency:
`get_evidence` has no working body until I2.3, and `register_tools(server)` here takes no
`get_service` override, so `get_service_dependencies` dispatches against the never-`configure()`-d
`app.mcp.wiring` singleton (see `_check_get_service_dependencies_fails_safely_when_wiring_is_
unconfigured` - this is deliberate coverage of that path, not an oversight). Real
`ArchitectureIntelligenceService` dispatch against a live Neo4j driver is
`tests/integration/test_mcp_service_dependencies_equivalence.py`'s job (I2.2).

All scenarios run inside one test function rather than one-test-per-scenario: `MCPServer.
session_manager.run()` owns an anyio task group whose cancel scope must be entered and exited by the
same asyncio Task - confirmed live that splitting that across a pytest-asyncio fixture's setup and
its (separately scheduled) teardown trips anyio's cross-task cancel-scope check, even with a single
module-scoped loop. Keeping one client/session-manager lifecycle inside one test body's one task
avoids it. Each scenario is still its own private `_check_*` helper for readability and independent
failure attribution in the traceback.
"""

from __future__ import annotations

import httpx
import pytest
from mcp.server import MCPServer

from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools

_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"


def _headers(
    *, method: str, name: str | None = None, protocol_version: str | None = "2026-07-28"
) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
        "mcp-method": method,
    }
    if protocol_version is not None:
        headers["mcp-protocol-version"] = protocol_version
    if name is not None:
        headers["mcp-name"] = name
    return headers


def _meta(protocol_version: str = "2026-07-28") -> dict[str, object]:
    return {
        "io.modelcontextprotocol/protocolVersion": protocol_version,
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _tools_list_body(
    request_id: int = 1, *, protocol_version: str = "2026-07-28"
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/list",
        "params": {"_meta": _meta(protocol_version)},
    }


def _tools_call_body(
    name: str, arguments: dict[str, object], request_id: int = 1
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments, "_meta": _meta()},
    }


# --- Protocol and Discovery (spec §17 scenarios 1-4) ----------------------------------------------


async def _check_valid_protocol_metadata_is_accepted(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/mcp", headers=_headers(method="tools/list"), json=_tools_list_body()
    )
    assert response.status_code == 200
    assert "error" not in response.json()


async def _check_missing_protocol_version_header_is_rejected(client: httpx.AsyncClient) -> None:
    """A *missing* required header is HEADER_MISMATCH (-32020), not UNSUPPORTED_PROTOCOL_VERSION
    (-32022, reserved for a *present* but unsupported value) - per `mcp.shared.inbound.
    classify_inbound_request`'s own rung 2, which the guard delegates to directly rather than
    reimplementing."""
    headers = _headers(method="tools/list", protocol_version=None)
    response = await client.post("/mcp", headers=headers, json=_tools_list_body())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32020


async def _check_mcp_method_header_mismatch_is_rejected(client: httpx.AsyncClient) -> None:
    headers = dict(_headers(method="tools/list"), **{"mcp-method": "tools/call"})
    response = await client.post("/mcp", headers=headers, json=_tools_list_body())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32020


async def _check_mcp_name_header_mismatch_is_rejected(client: httpx.AsyncClient) -> None:
    headers = _headers(method="tools/call", name="get_evidence")
    body = _tools_call_body(
        "get_evidence",
        {"request": {"evidence_refs": ["x"], "snapshot_id": "aip:snapshot:v1:" + "a" * 64}},
    )
    response = await client.post(
        "/mcp", headers=dict(headers, **{"mcp-name": "get_service_dependencies"}), json=body
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32020


async def _check_header_mismatch_takes_priority_over_unknown_tool(
    client: httpx.AsyncClient,
) -> None:
    """A request that is simultaneously an Mcp-Name/body mismatch AND names an unknown tool must
    report the header mismatch (-32020), not the guard's own unknown-tool check (-32602) - the
    guard only runs its tool-name/argument checks after `classify_inbound_request` has already
    accepted the request, matching the SDK's own rung ordering."""
    headers = _headers(method="tools/call", name="does_not_exist")
    body = _tools_call_body("does_not_exist", {})
    response = await client.post(
        "/mcp", headers=dict(headers, **{"mcp-name": "something_else"}), json=body
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32020


async def _check_unrelated_path_is_a_normal_404(client: httpx.AsyncClient) -> None:
    """A stray POST to a path the guard doesn't recognize must fall straight through to the inner
    app's own 404, never a synthesized MCP protocol error - the guard only inspects `MCP_PATH`."""
    response = await client.post(
        "/not-mcp", headers=_headers(method="tools/list"), json=_tools_list_body()
    )
    assert response.status_code == 404
    assert "jsonrpc" not in response.text


async def _check_legacy_handshake_version_is_rejected_not_silently_served(
    client: httpx.AsyncClient,
) -> None:
    """A pre-2026-07-28 handshake version must be rejected, not served by the SDK's legacy
    initialize/session path (spec §4/§20's "implementation requires initialize while claiming MCP
    2026-07-28" release blocker) - confirmed live that without app.mcp.guard, this is exactly what
    the SDK does instead."""
    headers = _headers(method="tools/list", protocol_version="2025-06-18")
    body = _tools_list_body(protocol_version="2025-06-18")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32022


async def _check_missing_required_meta_field_is_rejected(client: httpx.AsyncClient) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    response = await client.post("/mcp", headers=_headers(method="tools/list"), json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32602


async def _check_unsupported_protocol_version_is_rejected(client: httpx.AsyncClient) -> None:
    headers = _headers(method="tools/list", protocol_version="2099-01-01")
    body = _tools_list_body(protocol_version="2099-01-01")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == -32022
    assert error["data"] == {"supported": ["2026-07-28"], "requested": "2099-01-01"}


async def _check_no_initialize_handshake_or_session_id_required(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/mcp", headers=_headers(method="tools/list"), json=_tools_list_body()
    )
    assert response.status_code == 200
    assert "mcp-session-id" not in {k.lower() for k in response.headers}


async def _check_tools_list_returns_exactly_two_tools_in_lexicographic_order(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/mcp", headers=_headers(method="tools/list"), json=_tools_list_body()
    )
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    names = [tool["name"] for tool in result["tools"]]
    assert names == ["get_evidence", "get_service_dependencies"]


async def _check_tools_list_schemas_are_closed(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/mcp", headers=_headers(method="tools/list"), json=_tools_list_body()
    )
    for tool in response.json()["result"]["tools"]:
        input_schema = tool["inputSchema"]
        assert input_schema["type"] == "object"
        # The outer wrapper (the SDK's synthesized argument model) is explicitly closed by
        # app.mcp.tools._close_input_schema - the SDK doesn't do this itself (confirmed live).
        assert input_schema["additionalProperties"] is False
        # The request type is nested one level in ($ref'd, per app.mcp.server's verified findings)
        # and keeps its own extra=forbid closure - checked on both request models below.
        for definition in input_schema.get("$defs", {}).values():
            if definition.get("title") in {"ServiceDependenciesRequest", "EvidenceRequest"}:
                assert definition["additionalProperties"] is False
        assert tool["outputSchema"]["title"].startswith("ArchitectureAnswer[")


async def _check_unknown_tool_name_fails_as_protocol_error_without_reaching_a_handler(
    client: httpx.AsyncClient,
) -> None:
    body = _tools_call_body("does_not_exist", {})
    headers = _headers(method="tools/call", name="does_not_exist")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == -32602
    assert error["message"] == "Unknown tool: does_not_exist"
    assert "result" not in response.json()


async def _check_unexpected_top_level_argument_fails_as_protocol_error(
    client: httpx.AsyncClient,
) -> None:
    body = _tools_call_body(
        "get_evidence",
        {
            "request": {"evidence_refs": ["x"], "snapshot_id": "aip:snapshot:v1:" + "a" * 64},
            "junk": 1,
        },
    )
    headers = _headers(method="tools/call", name="get_evidence")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32602


async def _check_malformed_nested_arguments_are_a_tool_execution_error(
    client: httpx.AsyncClient,
) -> None:
    """Distinct from the guard-level corrections above: once a tools/call names a real tool and
    only the expected top-level key, argument-schema validation is the SDK's own verified behavior
    (spec §16: "Invalid tool arguments -> Tool execution error with isError: true") and must not be
    intercepted by the guard. `snapshot_id` is required on `EvidenceRequest` and omitted here."""
    body = _tools_call_body("get_evidence", {"request": {"evidence_refs": ["x"]}})
    headers = _headers(method="tools/call", name="get_evidence")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True


async def _check_get_evidence_is_discoverable_but_not_yet_implemented(
    client: httpx.AsyncClient,
) -> None:
    body = _tools_call_body(
        "get_evidence",
        {"request": {"evidence_refs": ["x"], "snapshot_id": "aip:snapshot:v1:" + "a" * 64}},
    )
    headers = _headers(method="tools/call", name="get_evidence")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert "not yet implemented" in result["content"][0]["text"]


async def _check_get_service_dependencies_fails_safely_when_wiring_is_unconfigured(
    client: httpx.AsyncClient,
) -> None:
    """v0.4.0 I2.2 - this test's server is registered via `register_tools(server)` with no
    `get_service` override, so it defaults to `app.mcp.wiring.get_service`, which is never
    `configure()`-d here (no Neo4j/settings in this test's minimal harness). `app.mcp.tools` doesn't
    catch this `RuntimeError` itself - the SDK's own `Tool.run` sanitizes it into a generic
    `UnexpectedToolError` (see `app.mcp.tools.get_service_dependencies`'s docstring for the verified
    live behavior this relies on). This proves that default sanitization actually fires end to end,
    not just that the adapter's own code never leaks anything."""
    body = _tools_call_body(
        "get_service_dependencies", {"request": {"service_id": "service:order-service"}}
    )
    headers = _headers(method="tools/call", name="get_service_dependencies")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert text == "Error executing tool get_service_dependencies"
    assert "not configured" not in text


async def _check_disallowed_origin_is_rejected(client: httpx.AsyncClient) -> None:
    headers = dict(_headers(method="tools/list"), origin="http://evil.example")
    response = await client.post("/mcp", headers=headers, json=_tools_list_body())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mcp_protocol_and_discovery() -> None:
    server = MCPServer(name="architecture-intelligence-platform-test", version="0.4.0")
    register_tools(server)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            await _check_valid_protocol_metadata_is_accepted(client)
            await _check_missing_protocol_version_header_is_rejected(client)
            await _check_mcp_method_header_mismatch_is_rejected(client)
            await _check_mcp_name_header_mismatch_is_rejected(client)
            await _check_header_mismatch_takes_priority_over_unknown_tool(client)
            await _check_legacy_handshake_version_is_rejected_not_silently_served(client)
            await _check_missing_required_meta_field_is_rejected(client)
            await _check_unsupported_protocol_version_is_rejected(client)
            await _check_no_initialize_handshake_or_session_id_required(client)
            await _check_unrelated_path_is_a_normal_404(client)
            await _check_tools_list_returns_exactly_two_tools_in_lexicographic_order(client)
            await _check_tools_list_schemas_are_closed(client)
            await _check_unknown_tool_name_fails_as_protocol_error_without_reaching_a_handler(
                client
            )
            await _check_unexpected_top_level_argument_fails_as_protocol_error(client)
            await _check_malformed_nested_arguments_are_a_tool_execution_error(client)
            await _check_get_evidence_is_discoverable_but_not_yet_implemented(client)
            await _check_get_service_dependencies_fails_safely_when_wiring_is_unconfigured(client)
            await _check_disallowed_origin_is_rejected(client)
