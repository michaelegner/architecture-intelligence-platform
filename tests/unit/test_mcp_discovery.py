"""v0.4.0 I2.1 - MCP protocol/discovery tests (spec §17's "Protocol and Discovery" scenarios 1-4,
plus the request/response contract shape).

v0.5.0 I3 slice 5a retires the v0.4.x AIP-specific "direct mode" envelope (ADR 0016, spec §14.1):
`app.mcp.guard.ModernProtocolGuard` no longer classifies any request as "direct" - every request
that reaches `/mcp` either matches its narrow retained checks (HTTP method, body size, the retired-
era-on-a-markerless-follow-up rejection) or is forwarded to the SDK's own negotiated dispatch
unmodified. Every `mcp-method`/`mcp-name`-header test this file used to run is gone: those headers
are now ordinary, inert HTTP headers the guard never inspects. What remains is this project's own
negotiated-only contract - the routing-truth-table coverage `docs/specifications/0.4.2/
i1-dual-mode-mcp-transport.md` §11.1/§28/§30 originally introduced, minus everything that was
direct-mode-specific.

**Disclosed scope decision, carried over from `app/mcp/guard.py`'s own module docstring**: the
v0.4.2 `_DIRECT_MODE_METHODS` allowlist (protection against a real, verified `subscriptions/listen`
SDK-hang DoS) is retired along with direct-marker classification and is NOT reintroduced for
negotiated traffic. This file deliberately does not exercise `subscriptions/listen` (or any other
non-allowlisted method) at all - doing so could hang the pytest process, exactly the failure mode
`tests/integration/test_mcp_direct_marker_dos_regression.py` (deleted this slice) existed to catch
when this protection still applied to direct-marked traffic.

Two checks below (`_check_unknown_tool_name_is_a_tool_execution_error_not_a_protocol_error`,
`_check_unexpected_top_level_argument_no_longer_fails_before_dispatch`) replace this file's former
guard-level "unknown tool"/"unexpected argument" protocol-error checks: those protections were only
ever applied inside the now-deleted direct-mode branch (confirmed live, `app.mcp.tools`'s own module
docstring names them as SDK gaps the guard corrected "ahead of the SDK's own dispatch" - negotiated
traffic never had this correction). Deleting direct mode does not newly introduce this gap; it
removes the one mode that happened to have it patched. These two tests document the SDK's actual,
unpatched negotiated-mode behavior rather than silently losing coverage of what changed.

Tests against `app.mcp.app.build_mcp_app` directly (not the full `app.main` FastAPI app) with a real
`httpx.AsyncClient`/`ASGITransport` - a real HTTP round trip through the guard and the SDK, not the
SDK's own client, so this doesn't validate the SDK against itself. No Neo4j/settings dependency:
`register_tools(server)` here takes no `get_service` override, so every tool dispatches against the
never-`configure()`-d `app.mcp.wiring` singleton (see the `_check_*_fails_safely_when_wiring_is_
unconfigured` checks - this is deliberate coverage of that path, not an oversight). Real
`ArchitectureIntelligenceService` dispatch against a live Neo4j driver is `tests/integration/
test_mcp_service_dependencies_equivalence.py`'s job.

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

from app.architecture_intelligence import contracts as contracts_module
from app.architecture_intelligence import service as service_module
from app.mcp import server as server_module
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import TOOL_NAMES, register_tools

_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"


def test_tool_names_are_single_sourced() -> None:
    assert contracts_module.TOOL_NAMES is TOOL_NAMES
    assert server_module.TOOL_NAMES is TOOL_NAMES
    assert {
        service_module._DRIFT_TOOL_NAME,
        service_module._EVIDENCE_TOOL_NAME,
        service_module._TOOL_NAME,
    } == set(TOOL_NAMES)


# --- Negotiated-mode request builders (the sole remaining transport, v0.5.0 I3 slice 5a) ----------


def _negotiated_headers(*, protocol_version: str | None = None) -> dict[str, str]:
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


# --- Protocol and Discovery (spec §17 scenarios 1-4) ----------------------------------------------


async def _check_unrelated_path_is_a_normal_404(client: httpx.AsyncClient) -> None:
    """A stray POST to a path the guard doesn't recognize must fall straight through to the inner
    app's own 404, never a synthesized MCP protocol error - the guard only inspects `MCP_PATH`."""
    response = await client.post(
        "/not-mcp",
        headers=_negotiated_headers(protocol_version="2025-11-25"),
        json=_negotiated_tools_list_body(),
    )
    assert response.status_code == 404
    assert "jsonrpc" not in response.text


async def _check_tools_list_returns_exactly_three_tools_in_lexicographic_order(
    client: httpx.AsyncClient,
) -> None:
    """v0.4.0 I3.2 - I3 spec §24/§45: `tools/list` count moves 2 -> 3 for the still-unreleased
    v0.4.0 line; no existing tool name/schema meaning changes to make room for the third."""
    response = await client.post(
        "/mcp",
        headers=_negotiated_headers(protocol_version="2025-11-25"),
        json=_negotiated_tools_list_body(),
    )
    result = response.json()["result"]
    # `resultType` is only stamped onto the wire when the negotiated protocol era requires it
    # (confirmed live in `mcp.server.runner`: only for the `2026-07-28`-and-later modern era this
    # project's negotiated tests deliberately don't negotiate - `MODERN_PROTOCOL_VERSIONS`); absence
    # is spec-equivalent to "complete" (`mcp_types._types`'s own docstring), not a missing field.
    assert result.get("resultType", "complete") == "complete"
    names = [tool["name"] for tool in result["tools"]]
    assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]


async def _check_tools_list_schemas_are_closed(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/mcp",
        headers=_negotiated_headers(protocol_version="2025-11-25"),
        json=_negotiated_tools_list_body(),
    )
    evidence_request_schema = None
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
            if definition.get("title") == "EvidenceRequest":
                evidence_request_schema = definition
        assert tool["outputSchema"]["title"].startswith("ArchitectureAnswer[")

    assert evidence_request_schema is not None
    evidence_refs_schema = evidence_request_schema["properties"]["evidence_refs"]
    assert evidence_refs_schema["minItems"] == 1
    assert evidence_refs_schema["maxItems"] == 20
    assert evidence_refs_schema["uniqueItems"] is True
    evidence_items = evidence_refs_schema["items"]
    assert evidence_items["type"] == "string"
    assert evidence_items["pattern"] == r"^evidence:"
    assert evidence_items["maxLength"] == 512


async def _check_unknown_tool_name_is_a_tool_execution_error_not_a_protocol_error(
    client: httpx.AsyncClient,
) -> None:
    """See module docstring: no adapter-level protection remains for this case after direct-mode's
    retirement - this documents the SDK's own actual (unpatched) negotiated-mode behavior."""
    body = _negotiated_tools_call_body("does_not_exist", {})
    response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=body
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True


async def _check_unexpected_top_level_argument_no_longer_fails_before_dispatch(
    client: httpx.AsyncClient,
) -> None:
    """See module docstring: no adapter-level protection remains for this case after direct-mode's
    retirement - confirmed live, the SDK's synthesized argument wrapper model (`extra="ignore"` by
    default, `app.mcp.tools`'s own docstring) silently drops the unrecognized `junk` key rather than
    rejecting it, so dispatch proceeds exactly as if `junk` had never been sent - `isError: true`
    here comes from the unconfigured-wiring harness (same shape as the checks below), not from the
    extra key."""
    body = _negotiated_tools_call_body(
        "get_evidence",
        {
            "request": {
                "evidence_refs": ["evidence:missing"],
                "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
            },
            "junk": 1,
        },
    )
    response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=body
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Error executing tool get_evidence"


async def _check_malformed_nested_arguments_are_a_tool_execution_error(
    client: httpx.AsyncClient,
) -> None:
    """Argument-schema validation is the SDK's own verified behavior (spec §16: "Invalid tool
    arguments -> Tool execution error with isError: true") and is unaffected by the guard's
    direct-mode retirement. `snapshot_id` is required on `EvidenceRequest` and omitted here."""
    body = _negotiated_tools_call_body(
        "get_evidence", {"request": {"evidence_refs": ["evidence:missing"]}}
    )
    response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=body
    )
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
    body = _negotiated_tools_call_body(
        "get_evidence",
        {
            "request": {
                "evidence_refs": ["evidence:missing"],
                "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
            }
        },
    )
    response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=body
    )
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
    body = _negotiated_tools_call_body(
        "get_service_dependencies", {"request": {"service_id": "service:order-service"}}
    )
    response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=body
    )
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
    body = _negotiated_tools_call_body(
        "get_architecture_drift", {"request": {"service_id": "service:order-service"}}
    )
    response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=body
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert text == "Error executing tool get_architecture_drift"
    assert "not configured" not in text


async def _check_disallowed_origin_is_rejected(client: httpx.AsyncClient) -> None:
    headers = dict(_negotiated_headers(protocol_version="2025-11-25"), origin="http://evil.example")
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 403


# --- Negotiated-only transport contract (retained/reworked from v0.4.2 I1's routing truth table) ---


async def _check_markerless_initialize_reaches_negotiated_sdk_path(
    client: httpx.AsyncClient,
) -> None:
    """`initialize` is always delegated to the pinned SDK's own negotiation, even with no
    `MCP-Protocol-Version` header at all."""
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
    `tools/call` operations. Each non-`initialize` request must carry a recognized handshake-era
    `MCP-Protocol-Version` header so it actually reaches the SDK's negotiated dispatch
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
        {
            "request": {
                "evidence_refs": ["evidence:missing"],
                "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
            }
        },
    )
    call_response = await client.post(
        "/mcp", headers=_negotiated_headers(protocol_version="2025-11-25"), json=call_body
    )
    assert call_response.status_code == 200
    # Wiring is unconfigured in this unit-test harness (see e.g.
    # _check_get_evidence_fails_safely_when_wiring_is_unconfigured above) - isError: true here means
    # the call *reached* negotiated tool dispatch and was sanitized normally.
    assert call_response.json()["result"]["isError"] is True

    for response in (init_response, list_response, call_response):
        assert "mcp-session-id" not in {k.lower() for k in response.headers}


async def _check_protocol_version_header_alone_reaches_negotiated_dispatch(
    client: httpx.AsyncClient,
) -> None:
    """`MCP-Protocol-Version` by itself (no prior `initialize` on this connection) reaches the
    pinned SDK's own stateless negotiated dispatch (confirmed live: the SDK answers a standalone
    `tools/list` statelessly, with no prior `initialize` needed on the same connection)."""
    headers = _negotiated_headers(protocol_version="2025-11-25")
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 200
    names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]


async def _check_markerless_tools_list_without_header_falls_back_to_sdk(
    client: httpx.AsyncClient,
) -> None:
    """A request with no `MCP-Protocol-Version` header at all is forwarded to the pinned SDK, not
    rejected (v0.4.2 I1 amendment, I3.4 VS Code finding) - the SDK's own `DEFAULT_NEGOTIATED_VERSION`
    fallback answers it normally, matching the MCP spec's backward-compatibility clause for a
    missing header."""
    response = await client.post(
        "/mcp", headers=_negotiated_headers(), json=_negotiated_tools_list_body()
    )
    assert response.status_code == 200
    names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]


async def _check_markerless_tools_call_without_header_falls_back_to_sdk(
    client: httpx.AsyncClient,
) -> None:
    """Same fallback as tools/list above, for tools/call - dispatches to the real tool
    implementation rather than being rejected for the missing header."""
    body = _negotiated_tools_call_body(
        "get_architecture_drift", {"request": {"service_id": "service:order-service"}}
    )
    response = await client.post("/mcp", headers=_negotiated_headers(), json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Error executing tool get_architecture_drift"


async def _check_retired_era_header_on_a_follow_up_is_rejected(client: httpx.AsyncClient) -> None:
    """A follow-up naming the retired direct/single-exchange `2026-07-28` era must never be served
    as negotiated traffic - that combination is rejected outright, not delegated to the SDK."""
    headers = _negotiated_headers(protocol_version="2026-07-28")
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32600
    assert "result" not in response.json()


async def _check_session_id_header_alone_does_not_change_routing(
    client: httpx.AsyncClient,
) -> None:
    """An MCP session identifier by itself does not change routing - a request carrying only a
    (fabricated, unrecognized) session id and no protocol-version header is treated the same way a
    bare request is (falls back to the SDK), not differently."""
    headers = dict(_negotiated_headers(), **{"mcp-session-id": "not-a-real-session"})
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 200
    names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]


async def _check_unrecognized_protocol_version_is_handled_by_sdk_without_dispatch(
    client: httpx.AsyncClient,
) -> None:
    """A `MCP-Protocol-Version` value that is neither the retired era nor a known handshake era is
    still delegated to the pinned SDK rather than guard-rejected (spec: "use pinned SDK
    recognition/error semantics") - confirmed live that the SDK's own streamable-HTTP dispatch
    produces a real JSON-RPC error and never reaches tool dispatch for this case on its own."""
    headers = _negotiated_headers(protocol_version="garbage-2099")
    response = await client.post("/mcp", headers=headers, json=_negotiated_tools_list_body())
    assert response.status_code == 400
    assert "result" not in response.json()


async def _check_malformed_json_reaches_sdk_parse_handler(client: httpx.AsyncClient) -> None:
    """Malformed/non-object JSON is always owned by the pinned SDK's own parse handler now - there
    is no longer a sticky "direct ownership" branch to compare against."""
    response = await client.post("/mcp", headers=_negotiated_headers(), content=b"{not valid json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == -32700


async def _check_tools_call_dispatches_to_the_real_tool_implementation(
    client: httpx.AsyncClient,
) -> None:
    """A negotiated `tools/call` dispatches to the real tool implementation - proven here by the
    same sanitized-error shape this unconfigured-wiring test harness produces everywhere else in
    this file."""
    headers = _negotiated_headers(protocol_version="2025-11-25")
    body = _negotiated_tools_call_body(
        "get_architecture_drift", {"request": {"service_id": "service:order-service"}}
    )
    response = await client.post("/mcp", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Error executing tool get_architecture_drift"


async def _check_vscode_full_sequence_without_protocol_header_is_accepted(
    client: httpx.AsyncClient,
) -> None:
    """One dedicated scenario (v0.4.2 I1 amendment, I3.4 VS Code actual-client-qualification
    finding), not spread across the aggregate test's other unrelated requests. Only the first two
    steps are the directly-observed real-world reproduction: GitHub Copilot Chat's MCP client, in
    VS Code 1.137.0, negotiated `protocolVersion: "2025-11-25"` via `initialize`, then sent
    `notifications/initialized` with no `MCP-Protocol-Version` header at all (confirmed in the
    client's own trace log). Before this fix, that notification was a hard 400 (`"A negotiated
    follow-up request requires an MCP-Protocol-Version header"`), which killed the connection
    outright before its queued `prompts/list`/`tools/list` calls could complete - so their own
    headers were never observed, and this test's headerless `tools/list` step is deliberate,
    broader contract coverage for the general fallback rule, not a claim that VS Code's own
    `tools/list` was confirmed headerless too. `notifications/initialized` is a JSON-RPC
    *notification* (no `id` field), which is exactly why the real error response VS Code received
    carried `"id": null`; per the transport spec, an accepted notification returns exactly
    `202 Accepted` with an empty body - not "200 or something", asserted precisely here."""
    init_response = await client.post(
        "/mcp", headers=_negotiated_headers(), json=_negotiated_initialize_body()
    )
    assert init_response.status_code == 200
    assert init_response.json()["result"]["protocolVersion"] == "2025-11-25"

    notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    notif_response = await client.post("/mcp", headers=_negotiated_headers(), json=notification)
    assert notif_response.status_code == 202
    assert notif_response.content == b""

    tools_response = await client.post(
        "/mcp", headers=_negotiated_headers(), json=_negotiated_tools_list_body()
    )
    assert tools_response.status_code == 200
    names = [tool["name"] for tool in tools_response.json()["result"]["tools"]]
    assert names == ["get_architecture_drift", "get_evidence", "get_service_dependencies"]


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
    server = MCPServer(name="architecture-intelligence-platform-test", version="0.5.0")
    register_tools(server)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            await _check_unrelated_path_is_a_normal_404(client)
            await _check_tools_list_returns_exactly_three_tools_in_lexicographic_order(client)
            await _check_tools_list_schemas_are_closed(client)
            await _check_unknown_tool_name_is_a_tool_execution_error_not_a_protocol_error(client)
            await _check_unexpected_top_level_argument_no_longer_fails_before_dispatch(client)
            await _check_malformed_nested_arguments_are_a_tool_execution_error(client)
            await _check_get_evidence_fails_safely_when_wiring_is_unconfigured(client)
            await _check_get_service_dependencies_fails_safely_when_wiring_is_unconfigured(client)
            await _check_get_architecture_drift_fails_safely_when_wiring_is_unconfigured(client)
            await _check_disallowed_origin_is_rejected(client)
            await _check_markerless_initialize_reaches_negotiated_sdk_path(client)
            await _check_negotiated_mode_issues_no_session_id(client)
            await _check_protocol_version_header_alone_reaches_negotiated_dispatch(client)
            await _check_markerless_tools_list_without_header_falls_back_to_sdk(client)
            await _check_markerless_tools_call_without_header_falls_back_to_sdk(client)
            await _check_retired_era_header_on_a_follow_up_is_rejected(client)
            await _check_session_id_header_alone_does_not_change_routing(client)
            await _check_unrecognized_protocol_version_is_handled_by_sdk_without_dispatch(client)
            await _check_malformed_json_reaches_sdk_parse_handler(client)
            await _check_tools_call_dispatches_to_the_real_tool_implementation(client)
            await _check_vscode_full_sequence_without_protocol_header_is_accepted(client)
            await _check_get_is_rejected_with_405_before_sdk_invocation(client)
            await _check_delete_is_rejected_with_405_before_sdk_invocation(client)
            await _check_head_is_rejected_with_405_and_empty_body(client)
            await _check_other_non_post_methods_are_rejected_with_405(client)
