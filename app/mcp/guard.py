"""v0.4.0 I2.1 - the thin ingress guard in front of the SDK's mounted MCP app.

Corrects two verified gaps between the installed `mcp==2.1.1` SDK's default behavior and spec
`docs/specifications/0.4.0/i2-mcp-vertical-slice-and-evidence-drill-down.md` (see `app.mcp.server`'s
module docstring for exactly what was verified live and why):

1. A request whose `MCP-Protocol-Version` header is missing, or names a pre-2026-07-28 handshake
   version, is otherwise silently served by the SDK's legacy `initialize`/session path. Spec §4/§20
   treats "implementation requires initialize while claiming MCP 2026-07-28" as a release blocker,
   so this guard rejects that case in front of the mounted app instead.
2. The SDK's own `tools/call` dispatch turns an unknown tool name into a normal `isError: true` tool
   result, and does not reject an unexpected top-level argument key. Spec §16 requires "unknown
   method/tool" to be a JSON-RPC protocol error, distinct from "invalid tool arguments" - this guard
   makes that distinction ahead of the SDK's own dispatch.

Everything else (required `_meta` fields, header/body agreement, unsupported-version rejection with
`{"supported": [...], "requested": ...}`, per-tool argument-schema validation once inside a
recognized tool) is the SDK's own verified, spec-conformant behavior and is not duplicated here.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.streamable_http_manager import HANDSHAKE_PROTOCOL_VERSIONS
from mcp_types.jsonrpc import INVALID_PARAMS, UNSUPPORTED_PROTOCOL_VERSION
from mcp_types.version import MODERN_PROTOCOL_VERSIONS
from starlette.types import ASGIApp, Receive, Scope, Send

from app.mcp.server import TOOL_NAMES

_PROTOCOL_VERSION_HEADER = "mcp-protocol-version"
_EXPECTED_ARGUMENT_KEY = "request"


def _json_rpc_error_body(
    request_id: Any, code: int, message: str, data: dict[str, Any] | None = None
) -> bytes:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": error}).encode("utf-8")


async def _send_json_error(send: Send, body: bytes) -> None:
    # Every code this guard emits (-32602, -32022) maps to HTTP 400 per the SDK's own
    # mcp.shared.inbound.ERROR_CODE_HTTP_STATUS table - matched here rather than imported so this
    # module doesn't depend on that table covering exactly these two codes forever.
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class ModernProtocolGuard:
    """ASGI middleware wrapping the SDK's mounted MCP app. See module docstring."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self._app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        protocol_version = headers.get(_PROTOCOL_VERSION_HEADER)

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        request_id = parsed.get("id") if isinstance(parsed, dict) else None

        if protocol_version is None or protocol_version in HANDSHAKE_PROTOCOL_VERSIONS:
            await _send_json_error(
                send,
                _json_rpc_error_body(
                    request_id,
                    UNSUPPORTED_PROTOCOL_VERSION,
                    "mcp-protocol-version header missing or unsupported; this server implements "
                    "MCP 2026-07-28 only and does not serve the legacy initialize handshake",
                    {"supported": list(MODERN_PROTOCOL_VERSIONS), "requested": protocol_version},
                ),
            )
            return

        if isinstance(parsed, dict) and parsed.get("method") == "tools/call":
            params = parsed.get("params") if isinstance(parsed.get("params"), dict) else {}
            name = params.get("name")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            if name not in TOOL_NAMES:
                await _send_json_error(
                    send, _json_rpc_error_body(request_id, INVALID_PARAMS, f"Unknown tool: {name}")
                )
                return
            unexpected = set(arguments) - {_EXPECTED_ARGUMENT_KEY}
            if unexpected:
                await _send_json_error(
                    send,
                    _json_rpc_error_body(
                        request_id,
                        INVALID_PARAMS,
                        f"Unexpected argument(s): {', '.join(sorted(unexpected))}",
                    ),
                )
                return

        async def replay_receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        await self._app(scope, replay_receive, send)
