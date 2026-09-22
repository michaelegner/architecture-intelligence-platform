"""v0.5.0 I3 slice 5a - shared standard-negotiated-MCP test-call helpers.

Promoted out of `test_mcp_negotiated_transport.py`'s own private builders so every other test file
this slice's MCP direct-envelope retirement touches (equivalence/adapter/parity/zero-write tests)
can drive the guard's sole remaining mode without re-deriving these request/header shapes. `mcp/tools`
dispatch here reuses the exact same tool bodies the retired direct mode used - only the transport
envelope changes.
"""

from __future__ import annotations

import httpx

DEFAULT_NEGOTIATED_PROTOCOL_VERSION = "2025-11-25"


def negotiated_headers(
    *, origin: str, protocol_version: str | None = DEFAULT_NEGOTIATED_PROTOCOL_VERSION
) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": origin,
    }
    if protocol_version is not None:
        headers["mcp-protocol-version"] = protocol_version
    return headers


def negotiated_initialize_body(request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "initialize",
        "params": {
            "protocolVersion": DEFAULT_NEGOTIATED_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "test-negotiated-client", "version": "0.0.0"},
        },
    }


def negotiated_tools_list_body(request_id: int = 2) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}


def negotiated_call_body(name: str, arguments: dict, request_id: int = 3) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


async def call_negotiated(
    client: httpx.AsyncClient, *, origin: str, name: str, arguments: dict
) -> dict:
    """Stateless single-shot `tools/call` - no prior `initialize` handshake is required, since this
    project's mounted MCP app runs the SDK's session manager in `stateless_http=True` mode
    (confirmed live by the pre-existing `test_direct_and_negotiated_structured_content_are_
    semantically_equivalent` test, which already called negotiated `tools/call` with no preceding
    `initialize`)."""
    response = await client.post(
        "/mcp",
        headers=negotiated_headers(origin=origin),
        json=negotiated_call_body(name, arguments),
    )
    assert response.status_code == 200
    return response.json()["result"]
