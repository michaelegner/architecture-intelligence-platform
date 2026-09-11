"""v0.4.0 I2.1 - MCP protocol/discovery tests (spec §17's "Protocol and Discovery" scenarios 1-4,
plus the two verified SDK gaps `app.mcp.guard` corrects and the request/response contract shape).

v0.4.2 I1 adds the dual-mode transport routing-truth-table coverage from
`docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md` §11.1/§28/§30: every request-shape
row that must route to negotiated SDK handling vs. be rejected before SDK dispatch, plus the
per-HTTP-method contract for `/mcp`. All direct-mode tests above are unchanged and untouched by
that increment - every one of them sends the `mcp-method` header via `_headers()`, which is
itself an AIP direct-envelope marker, so they all still take the pre-I1 `classify_inbound_request`
path byte-for-byte.

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


async def _check_tools_list_returns_exactly_three_tools_in_lexicographic_order(
    client: httpx.AsyncClient,
) -> None:
    """v0.4.0 I3.2 - I3 spec §24/§45: `tools/list` count moves 2 -> 3 for the still-unreleased
    v0.4.0 line; no existing tool name/schema meaning changes to make room for the third."""
    response = await client.post(
        "/mcp", headers=_headers(method="tools/list"), json=_tools_list_body()
    )
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    names = [tool["name"] for tool in result["tools"]]
    assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]


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
            if definition.get("title") in {
                "ServiceDependenciesRequest",
                "EvidenceRequest",
                "ArchitectureDriftRequest",
            }:
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


async def _check_get_evidence_fails_safely_when_wiring_is_unconfigured(
    client: httpx.AsyncClient,
) -> None:
    """v0.4.0 I2.3 - `get_evidence` is discoverable via `tools/list` and, once dispatched, follows
    the same default-sanitization path `get_service_dependencies` already proves below: this test's
    server is registered via `register_tools(server)` with no `get_service` override, so
    `wiring.get_service()` is never `configure()`-d, and the SDK sanitizes the resulting
    `RuntimeError` into a generic `UnexpectedToolError`, never leaking "not configured"."""
    body = _tools_call_body(
        "get_evidence",
        {"request": {"evidence_refs": ["x"], "snapshot_id": "aip:snapshot:v1:" + "a" * 64}},
    )
    headers = _headers(method="tools/call", name="get_evidence")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert text == "Error executing tool get_evidence"
    assert "not configured" not in text


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


async def _check_get_architecture_drift_fails_safely_when_wiring_is_unconfigured(
    client: httpx.AsyncClient,
) -> None:
    """v0.4.0 I3.2 - `get_architecture_drift` is discoverable via `tools/list` and, once dispatched,
    follows the same default-sanitization path the other two tools already prove above: this test's
    server is registered via `register_tools(server)` with no `get_service` override, so
    `wiring.get_service()` is never `configure()`-d, and the SDK sanitizes the resulting
    `RuntimeError` into a generic `UnexpectedToolError`, never leaking "not configured"."""
    body = _tools_call_body(
        "get_architecture_drift", {"request": {"service_id": "service:order-service"}}
    )
    headers = _headers(method="tools/call", name="get_architecture_drift")
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert text == "Error executing tool get_architecture_drift"
    assert "not configured" not in text


async def _check_disallowed_origin_is_rejected(client: httpx.AsyncClient) -> None:
    headers = dict(_headers(method="tools/list"), origin="http://evil.example")
    response = await client.post("/mcp", headers=headers, json=_tools_list_body())
    assert response.status_code == 403


# --- Dual-mode transport routing (v0.4.2 I1, spec §11.1/§28/§30) ----------------------------------


def _negotiated_headers(*, protocol_version: str | None = None) -> dict[str, str]:
    """A markerless request: no `mcp-method`/`mcp-name` - the only headers a genuine negotiated SDK
    client would send. `protocol_version`, when given, is the *only* AIP-adjacent header present."""
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
    }
    if protocol_version is not None:
        headers["mcp-protocol-version"] = protocol_version
    return headers


def _negotiated_initialize_body(request_id: int = 1) -> dict[str, object]:
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


def _negotiated_tools_list_body(request_id: int = 1) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}


def _negotiated_tools_call_body(
    name: str, arguments: dict[str, object], request_id: int = 1
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


async def _check_markerless_initialize_reaches_negotiated_sdk_path(
    client: httpx.AsyncClient,
) -> None:
    """Only `initialize` may be markerless - it must reach the pinned SDK's own negotiation, not
    the guard's direct-mode ladder, even with no `MCP-Protocol-Version` header at all."""
    response = await client.post(
        "/mcp", headers=_negotiated_headers(), json=_negotiated_initialize_body()
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["protocolVersion"] == "2025-11-25"
    assert "error" not in response.json()


async def _check_negotiated_mode_issues_no_session_id(client: httpx.AsyncClient) -> None:
    """spec §15/§34's conditional session-behavior determination: SESSION_BEHAVIOR =
    NOT_APPLICABLE for this release candidate, because the pinned SDK's stateless handler never
    issues an `Mcp-Session-Id` - confirmed here across successful `initialize`, `tools/list`, and
    `tools/call` operations, not just the single call `_check_no_initialize_handshake_or_session_id_
    required` already checks for direct mode. Each non-`initialize` request must carry a recognized
    handshake-era `MCP-Protocol-Version` header so it actually reaches the SDK's negotiated dispatch
    (`_negotiated_headers()`'s own default omits the header entirely, which would otherwise make
    this assertion vacuous - both requests would be guard-rejected before ever reaching the SDK, so
    trivially carry no session header either; PR review finding on this file's first draft)."""
    init_response = await client.post(
        "/mcp",
        headers=_negotiated_headers(protocol_version=None),
        json=_negotiated_initialize_body(),
    )
    assert init_response.status_code == 200
    assert init_response.json()["result"]["protocolVersion"] == "2025-11-25"

    list_response = await client.post(
        "/mcp",
        headers=_negotiated_headers(protocol_version="2025-11-25"),
        json=_negotiated_tools_list_body(),
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["result"]["tools"]) == 3

    call_body = _negotiated_tools_call_body(
        "get_evidence",
        {"request": {"evidence_refs": ["x"], "snapshot_id": "aip:snapshot:v1:" + "a" * 64}},
    )
    call_response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=call_body
    )
    assert call_response.status_code == 200
    # Wiring is unconfigured in this unit-test harness (see e.g.
    # _check_get_evidence_fails_safely_when_wiring_is_unconfigured above) - isError: true here means
    # the call *reached* negotiated tool dispatch and was sanitized normally, the same successful
    # dispatch outcome direct mode gets from this same harness, not a rejection before dispatch.
    assert call_response.json()["result"]["isError"] is True

    for response in (init_response, list_response, call_response):
        assert "mcp-session-id" not in {k.lower() for k in response.headers}


async def _check_protocol_version_header_alone_does_not_select_direct_mode(
    client: httpx.AsyncClient,
) -> None:
    """`MCP-Protocol-Version` by itself (no `mcp-method`/`mcp-name`, no `_meta`) must NOT be treated
    as a direct-envelope marker: a handshake-era value on a markerless non-`initialize` follow-up
    reaches the pinned SDK's own stateless negotiated dispatch (confirmed live: the SDK answers a
    standalone `tools/list` statelessly, with no prior `initialize` needed on the same connection) -
    it must not fall into the guard's `classify_inbound_request` ladder, which would reject it for
    missing `_meta` instead of returning a real tool list."""
    headers = _negotiated_headers(protocol_version="2025-11-25")
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 200
    names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]


async def _check_markerless_tools_list_without_header_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    """A markerless non-`initialize` request with no `MCP-Protocol-Version` header at all must be
    rejected before SDK tool dispatch, not silently answered."""
    response = await client.post(
        "/mcp", headers=_negotiated_headers(), json=_negotiated_tools_list_body()
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == -32600
    assert "result" not in response.json()


async def _check_markerless_tools_call_without_header_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    body = _negotiated_tools_call_body("get_evidence", {})
    response = await client.post("/mcp", headers=_negotiated_headers(), json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32600
    assert "result" not in response.json()


async def _check_direct_era_header_without_marker_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    """A markerless follow-up naming the direct/single-exchange `2026-07-28` era must never become
    negotiated traffic - that combination is rejected outright, not delegated to the SDK."""
    headers = _negotiated_headers(protocol_version="2026-07-28")
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32600
    assert "result" not in response.json()


async def _check_session_id_header_alone_is_not_a_direct_marker(
    client: httpx.AsyncClient,
) -> None:
    """An MCP session identifier by itself is also not a direct-mode discriminator - a markerless
    request carrying only a (fabricated, unrecognized) session id and no protocol-version header
    fails the same way a bare markerless request does, not differently."""
    headers = dict(_negotiated_headers(), **{"mcp-session-id": "not-a-real-session"})
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32600


async def _check_unrecognized_protocol_version_is_handled_by_sdk_without_dispatch(
    client: httpx.AsyncClient,
) -> None:
    """A `MCP-Protocol-Version` value that is neither the direct era nor a known handshake era is
    still delegated to the pinned SDK rather than guard-rejected (spec: "use pinned SDK
    recognition/error semantics") - confirmed live that the SDK's own streamable-HTTP dispatch
    produces a real JSON-RPC error and never reaches tool dispatch for this case on its own."""
    headers = _negotiated_headers(protocol_version="garbage-2099")
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 400
    assert "result" not in response.json()


async def _check_malformed_json_without_direct_header_reaches_sdk_parse_handler(
    client: httpx.AsyncClient,
) -> None:
    """Malformed/non-object JSON with no direct-specific header must be owned by the pinned SDK's
    own parse handler, not the guard's negotiated-header precheck - no valid method has been
    extracted yet, so that check does not apply."""
    response = await client.post("/mcp", headers=_negotiated_headers(), content=b"{not valid json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == -32700
    assert (
        error["message"] != "Malformed JSON body"
    )  # this is the SDK's own message, not the guard's


async def _check_malformed_json_with_direct_header_is_owned_by_direct_path(
    client: httpx.AsyncClient,
) -> None:
    """Malformed/non-object JSON WITH a direct-specific header (`mcp-method`) stays sticky to the
    direct path - it must not fall through to the SDK's negotiated parse handler."""
    headers = dict(_negotiated_headers(), **{"mcp-method": "tools/list"})
    response = await client.post("/mcp", headers=headers, content=b"{not valid json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == -32700
    assert error["message"] == "Malformed JSON body"


async def _check_negotiated_tools_call_shares_the_direct_tool_implementation(
    client: httpx.AsyncClient,
) -> None:
    """A negotiated `tools/call` must dispatch to the exact same tool implementation as direct mode
    - proven here by getting the identical sanitized-error shape the direct-mode equivalents above
    get from this same unconfigured-wiring test harness, not a negotiated-only code path."""
    headers = _negotiated_headers(protocol_version="2025-11-25")
    body = _negotiated_tools_call_body(
        "get_architecture_drift", {"request": {"service_id": "service:order-service"}}
    )
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Error executing tool get_architecture_drift"


async def _check_get_is_rejected_with_405_before_sdk_invocation(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/mcp", headers={"origin": _ALLOWED_ORIGIN})
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert len(response.content) <= 512
    assert response.json() == {
        "error": {
            "code": "METHOD_NOT_ALLOWED",
            "message": "Only POST /mcp is supported in stateless mode.",
        }
    }


async def _check_delete_is_rejected_with_405_before_sdk_invocation(
    client: httpx.AsyncClient,
) -> None:
    response = await client.delete("/mcp", headers={"origin": _ALLOWED_ORIGIN})
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert len(response.content) <= 512


async def _check_head_is_rejected_with_405_and_empty_body(client: httpx.AsyncClient) -> None:
    response = await client.head("/mcp", headers={"origin": _ALLOWED_ORIGIN})
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert response.content == b""


async def _check_other_non_post_methods_are_rejected_with_405(
    client: httpx.AsyncClient,
) -> None:
    for verb in ("PUT", "PATCH", "OPTIONS"):
        response = await client.request(verb, "/mcp", headers={"origin": _ALLOWED_ORIGIN})
        assert response.status_code == 405, verb
        assert response.headers["allow"] == "POST", verb
        assert len(response.content) <= 512, verb


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
            await _check_tools_list_returns_exactly_three_tools_in_lexicographic_order(client)
            await _check_tools_list_schemas_are_closed(client)
            await _check_unknown_tool_name_fails_as_protocol_error_without_reaching_a_handler(
                client
            )
            await _check_unexpected_top_level_argument_fails_as_protocol_error(client)
            await _check_malformed_nested_arguments_are_a_tool_execution_error(client)
            await _check_get_evidence_fails_safely_when_wiring_is_unconfigured(client)
            await _check_get_service_dependencies_fails_safely_when_wiring_is_unconfigured(client)
            await _check_get_architecture_drift_fails_safely_when_wiring_is_unconfigured(client)
            await _check_disallowed_origin_is_rejected(client)
            await _check_markerless_initialize_reaches_negotiated_sdk_path(client)
            await _check_negotiated_mode_issues_no_session_id(client)
            await _check_protocol_version_header_alone_does_not_select_direct_mode(client)
            await _check_markerless_tools_list_without_header_is_rejected(client)
            await _check_markerless_tools_call_without_header_is_rejected(client)
            await _check_direct_era_header_without_marker_is_rejected(client)
            await _check_session_id_header_alone_is_not_a_direct_marker(client)
            await _check_unrecognized_protocol_version_is_handled_by_sdk_without_dispatch(client)
            await _check_malformed_json_without_direct_header_reaches_sdk_parse_handler(client)
            await _check_malformed_json_with_direct_header_is_owned_by_direct_path(client)
            await _check_negotiated_tools_call_shares_the_direct_tool_implementation(client)
            await _check_get_is_rejected_with_405_before_sdk_invocation(client)
            await _check_delete_is_rejected_with_405_before_sdk_invocation(client)
            await _check_head_is_rejected_with_405_and_empty_body(client)
            await _check_other_non_post_methods_are_rejected_with_405(client)
