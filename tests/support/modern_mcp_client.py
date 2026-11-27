"""v0.8.1 I1 - request builders for the MCP `2026-07-28` era (ADR 0018).

These reproduce the modern requests that Claude Code 2.1.332 sent in the I0 spike
(`docs/specifications/0.8.1/i0-protocol-spike-record.md`): each request names its era in the
`MCP-Protocol-Version` header and carries `_meta` with the protocol version, client info and client
capabilities. The pinned SDK (`mcp==2.3.0`) also requires two routing headers, confirmed against
it in I1:

- `mcp-method` on every request: without it the SDK returns `-32020` (header mismatch);
- `mcp-name` on `tools/call` (the tool name) and `resources/read` (the resource URI), with the
  same `-32020` otherwise. No other method needs it.
"""

from __future__ import annotations

import httpx

MODERN_PROTOCOL_VERSION = "2026-07-28"

_MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": MODERN_PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientInfo": {"name": "test-modern-client", "version": "0.0.0"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


def modern_headers(*, origin: str, method: str, name: str | None = None) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": origin,
        "mcp-protocol-version": MODERN_PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    return headers


def modern_body(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {**(params or {}), "_meta": _MODERN_META},
    }


async def post_modern(
    client: httpx.AsyncClient,
    *,
    origin: str,
    method: str,
    params: dict | None = None,
    name: str | None = None,
) -> httpx.Response:
    return await client.post(
        "/mcp",
        headers=modern_headers(origin=origin, method=method, name=name),
        json=modern_body(method, params),
    )


async def call_modern(
    client: httpx.AsyncClient, *, origin: str, name: str, arguments: dict
) -> dict:
    """A modern `tools/call`; the counterpart of `negotiated_mcp_client.call_negotiated`."""
    response = await post_modern(
        client,
        origin=origin,
        method="tools/call",
        params={"name": name, "arguments": arguments},
        name=name,
    )
    assert response.status_code == 200
    return response.json()["result"]
