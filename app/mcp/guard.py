"""v0.4.0 I2.1 - the thin ingress guard in front of the SDK's mounted MCP app.

Corrects two verified gaps between the installed `mcp==2.1.1` SDK's default behavior and spec
`docs/specifications/0.4.0/i2-mcp-vertical-slice-and-evidence-drill-down.md` (see `app.mcp.server`'s
module docstring for exactly what was verified live and why):

1. A request whose `MCP-Protocol-Version` header is missing, or names a pre-2026-07-28 handshake
   version, is otherwise silently served by the SDK's legacy `initialize`/session path. Spec §4/§20
   treats "implementation requires initialize while claiming MCP 2026-07-28" as a release blocker,
   so this guard rejects that case in front of the mounted app instead - delegated entirely to
   `mcp.shared.inbound.classify_inbound_request`, the SDK's own pure validation-ladder function (the
   same one its "modern" request path uses internally), rather than a hand-rolled reimplementation:
   that keeps the exact rung order and error codes it decides on (rung 1 `_meta` presence -> INVALID_
   PARAMS, rung 2 header/body agreement, INCLUDING a *missing* header, -> HEADER_MISMATCH, rung 3
   unsupported version -> UNSUPPORTED_PROTOCOL_VERSION) authoritative in one place instead of two.
2. The SDK's own `tools/call` dispatch turns an unknown tool name into a normal `isError: true` tool
   result, and does not reject an unexpected top-level argument key. Spec §16 requires "unknown
   method/tool" to be a JSON-RPC protocol error, distinct from "invalid tool arguments" - this guard
   makes that distinction ahead of the SDK's own dispatch, but only after `classify_inbound_request`
   has already accepted the request, so a header/body mismatch or missing `_meta` field always takes
   priority over a tool-name/argument correction (matching the SDK's own rung ordering).

Everything else (per-tool argument-schema validation once inside a recognized tool, Origin/Host
allow-listing) is the SDK's own verified, spec-conformant behavior and is not duplicated here.

Only requests to `MCP_PATH` are inspected at all - anything else passes straight through to the
inner app unmodified, so an unrelated path (e.g. a stray `POST` the outer FastAPI app didn't claim)
gets a normal 404, never a synthesized MCP protocol error.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.shared.inbound import (
    ERROR_CODE_HTTP_STATUS,
    InboundLadderRejection,
    classify_inbound_request,
)
from mcp_types.jsonrpc import INVALID_PARAMS
from starlette.types import ASGIApp, Receive, Scope, Send

from app.mcp.server import TOOL_NAMES

MCP_PATH = "/mcp"
_EXPECTED_ARGUMENT_KEY = "request"
_DEFAULT_HTTP_STATUS = 400


def _error_body(request_id: Any, code: int, message: str, data: Any = None) -> bytes:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": error}).encode("utf-8")


async def _send_json_error(send: Send, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class ModernProtocolGuard:
    """ASGI middleware wrapping the SDK's mounted MCP app. See module docstring."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != MCP_PATH:
            await self._app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        async def replay_receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict):
            # Malformed/non-object body - not this guard's concern; let the SDK's own parse-error
            # handling respond.
            await self._app(scope, replay_receive, send)
            return
        request_id = parsed.get("id")

        route = classify_inbound_request(parsed, headers=headers)
        if isinstance(route, InboundLadderRejection):
            status = ERROR_CODE_HTTP_STATUS.get(route.code, _DEFAULT_HTTP_STATUS)
            await _send_json_error(
                send, status, _error_body(request_id, route.code, route.message, route.data)
            )
            return

        if parsed.get("method") == "tools/call":
            params = parsed.get("params") if isinstance(parsed.get("params"), dict) else {}
            name = params.get("name")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            if name not in TOOL_NAMES:
                await _send_json_error(
                    send,
                    _DEFAULT_HTTP_STATUS,
                    _error_body(request_id, INVALID_PARAMS, f"Unknown tool: {name}"),
                )
                return
            unexpected = set(arguments) - {_EXPECTED_ARGUMENT_KEY}
            if unexpected:
                await _send_json_error(
                    send,
                    _DEFAULT_HTTP_STATUS,
                    _error_body(
                        request_id,
                        INVALID_PARAMS,
                        f"Unexpected argument(s): {', '.join(sorted(unexpected))}",
                    ),
                )
                return

        await self._app(scope, replay_receive, send)
