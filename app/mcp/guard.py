"""v0.5.0 I3 slice 5a - negotiated-only ingress guard in front of the SDK's mounted MCP app.

The v0.4.x AIP-specific "direct mode" envelope (`mcp-method`/`mcp-name` headers, or `params._meta`'s
`io.modelcontextprotocol/protocolVersion`|`clientCapabilities` body markers) is retired per ADR 0016
and spec §14.1: `ArchitectureIntelligenceService` now has exactly two public adapters (REST, standard
negotiated MCP), and the deterministic evaluator already invokes the service directly - direct MCP
had no remaining distinct responsibility once REST exists. `POST /mcp` now serves standard negotiated
MCP only; this guard's only remaining job is:

1. Reject every non-POST method (`GET`, `DELETE`, `HEAD`, and everything else) with HTTP 405 before
   the SDK is invoked at all - this stateless release advertises no SSE stream or session lifecycle
   on any of them (spec §8/§30's per-method contract, unchanged from v0.4.x).
2. Bound request body size (413 over `_MAX_REQUEST_BODY_BYTES`).
3. Reject a markerless follow-up that *explicitly* names the retired direct/single-exchange
   `2026-07-28` era via the `MCP-Protocol-Version` header - that specific contradiction (claims the
   retired era, behaves like ordinary negotiated follow-up traffic) is never forwarded, matching this
   guard's v0.4.2 negotiated-mode behavior unchanged. A *missing* `MCP-Protocol-Version` header, or
   one naming any other version, is not rejected here - the pinned SDK's own negotiation/session
   machinery is authoritative for everything else, including its own graceful missing-header default
   (`DEFAULT_NEGOTIATED_VERSION` in `mcp.server.streamable_http`) and rejecting a version it does not
   itself recognize.

Everything else (`initialize`/session negotiation, per-tool argument-schema validation, Origin/Host
allow-listing) is the SDK's own verified, spec-conformant behavior and is not duplicated here.

**Disclosed scope decision** (v0.5.0 I3 slice 5a plan, "Open Questions" #1 - explicit spec-author
sign-off, 2026-09-22): the v0.4.2 `_DIRECT_MODE_METHODS` allowlist that protected against a real,
verified SDK-hang DoS (`subscriptions/listen`'s long-lived-notification handling hangs indefinitely
under AIP's stateless single-worker deployment - the exact incident `tests/integration/
test_mcp_direct_marker_dos_regression.py` used to reproduce, before this slice deleted that test) is
retired along with direct-marker classification and is **not** generalized to negotiated-mode
traffic. That protection only ever covered requests carrying a direct-mode marker; it is not
reintroduced here. A negotiated client that sends a non-`initialize` JSON-RPC method this guard
doesn't otherwise reject reaches the SDK's own dispatch unfiltered - exactly as markerless traffic
always has. This is an explicit, disclosed gap, not an oversight: closing it (e.g. a negotiated-mode
method allowlist, or an upstream SDK fix) is tracked as separate follow-up work outside this slice.

Only requests to `MCP_PATH` are inspected at all - anything else passes straight through to the
inner app unmodified, so an unrelated path (e.g. a stray `POST` the outer FastAPI app didn't claim)
gets a normal 404, never a synthesized MCP protocol error.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.shared.inbound import MCP_PROTOCOL_VERSION_HEADER
from mcp_types.jsonrpc import INVALID_REQUEST
from mcp_types.version import MODERN_PROTOCOL_VERSIONS
from starlette.types import ASGIApp, Receive, Scope, Send

MCP_PATH = "/mcp"
_DEFAULT_HTTP_STATUS = 400
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


class ModernProtocolGuard:
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

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}

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

        async def replay_receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None

        if not isinstance(parsed, dict):
            # No AIP-proprietary envelope classification left to do here - let the SDK's own
            # negotiated parse-error handling respond.
            await self._app(scope, replay_receive, send)
            return

        request_id = parsed.get("id")

        # Only a follow-up that *explicitly* names the retired direct/single-exchange `2026-07-28`
        # era is rejected here - that specific contradiction (claims the retired era, behaves like
        # ordinary negotiated follow-up traffic) is never delegated. A *missing*
        # MCP-Protocol-Version header is not that contradiction (the pinned SDK's own
        # DEFAULT_NEGOTIATED_VERSION fallback handles it), so it is not rejected.
        if parsed.get("method") == "initialize":
            await self._app(scope, replay_receive, send)
            return

        version_header = headers.get(MCP_PROTOCOL_VERSION_HEADER)
        if version_header is not None and version_header in MODERN_PROTOCOL_VERSIONS:
            await _send_json_error(
                send,
                _DEFAULT_HTTP_STATUS,
                _error_body(
                    request_id,
                    INVALID_REQUEST,
                    "The direct protocol era cannot be used for a negotiated follow-up request",
                ),
            )
            return

        await self._app(scope, replay_receive, send)
