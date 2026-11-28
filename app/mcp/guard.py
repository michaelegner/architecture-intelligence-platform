"""v0.5.0 I3 slice 5a, amended by v0.8.1 I1 (ADR 0018) - the ingress guard in front of the SDK's
mounted MCP app.

The v0.4.x AIP-specific "direct mode" envelope is retired (ADR 0016): `POST /mcp` serves the
standard MCP protocol through the pinned SDK. Since v0.8.1 (ADR 0018, spec D3) that includes the
`2026-07-28` era as well as the negotiated `initialize` era (`2025-11-25`). The SDK routes a
request to its modern or legacy path by the `MCP-Protocol-Version` header. This guard no longer
rejects a request that names `2026-07-28`; it keeps two jobs:

1. Reject every non-POST method (`GET`, `DELETE`, `HEAD`, and everything else) with HTTP 405 before
   the SDK is invoked at all - this stateless release advertises no SSE stream or session lifecycle
   on any of them (spec §8/§30's per-method contract, unchanged from v0.4.x).
2. Bound request body size (413 over `_MAX_REQUEST_BODY_BYTES`).

Everything else (era routing, `initialize` negotiation, per-tool argument-schema validation,
Origin/Host allow-listing, rejecting a version the SDK does not recognize) is the SDK's own
behavior and is not duplicated here.

`subscriptions/listen` is not served on any era (v0.8.1 D9: `MCPServer(subscriptions=False)` in
`app.mcp.server`), so the SDK answers it with `METHOD_NOT_FOUND` and never opens the long-lived
stream that once hung AIP's stateless single-worker deployment.

Only requests to `MCP_PATH` are inspected at all - anything else passes straight through to the
inner app unmodified, so an unrelated path (e.g. a stray `POST` the outer FastAPI app didn't claim)
gets a normal 404, never a synthesized MCP protocol error.
"""

from __future__ import annotations

import json
from typing import Any

from mcp_types.jsonrpc import INVALID_REQUEST
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MCP_PATH = "/mcp"
_MAX_REQUEST_BODY_BYTES = 1024 * 1024
_PAYLOAD_TOO_LARGE_STATUS = 413
_METHOD_NOT_ALLOWED_STATUS = 405
_METHOD_NOT_ALLOWED_BODY = json.dumps(
    {
        "error": {
            "code": "METHOD_NOT_ALLOWED",
            "message": "Only POST /mcp is supported in stateless mode.",
        }
    }
).encode("utf-8")


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


async def _send_method_not_allowed(send: Send, *, empty_body: bool) -> None:
    headers = [(b"allow", b"POST")]
    if not empty_body:
        headers.append((b"content-type", b"application/json"))
    await send(
        {"type": "http.response.start", "status": _METHOD_NOT_ALLOWED_STATUS, "headers": headers}
    )
    await send(
        {"type": "http.response.body", "body": b"" if empty_body else _METHOD_NOT_ALLOWED_BODY}
    )


class McpIngressGuard:
    """ASGI middleware wrapping the SDK's mounted MCP app. See module docstring."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != MCP_PATH:
            await self._app(scope, receive, send)
            return

        http_method = scope["method"]
        if http_method == "HEAD":
            await _send_method_not_allowed(send, empty_body=True)
            return
        if http_method != "POST":
            await _send_method_not_allowed(send, empty_body=False)
            return

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > _MAX_REQUEST_BODY_BYTES:
                await _send_json_error(
                    send,
                    _PAYLOAD_TOO_LARGE_STATUS,
                    _error_body(
                        None,
                        INVALID_REQUEST,
                        "Request body exceeds the maximum allowed size",
                    ),
                )
                return
            body += chunk
            more_body = message.get("more_body", False)

        replayed = False

        async def replay_receive() -> Message:
            # Replay the buffered body once, then defer to the server's own `receive`, which waits
            # for `http.disconnect`. Returning the body again would never suspend: the SDK's
            # disconnect watcher on its SSE path would then spin and block the event loop.
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self._app(scope, replay_receive, send)
