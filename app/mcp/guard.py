"""v0.4.2 I1 - dual-mode ingress guard in front of the SDK's mounted MCP app.

Preserves the `v0.4.0`/`v0.4.1` strict direct `2026-07-28` per-request envelope contract (see
below) while adding a second, negotiated path so a standard MCP client's `initialize`/session
handshake reaches the pinned SDK instead of being rejected. Governing invariant (spec
`docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md` and its parent `specification.md`):

    Transport negotiation may differ; architecture meaning must not.

## Direct mode (unchanged from v0.4.0/v0.4.1)

Corrects two verified gaps between the installed MCP SDK's default behavior and spec
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

## Negotiated mode (new in v0.4.2 I1)

A request is routed to direct-mode validation above when it carries at least one AIP-specific
direct-envelope marker: the `mcp-method`/`mcp-name` HTTP headers, or `params._meta`'s
`io.modelcontextprotocol/protocolVersion`/`clientCapabilities` keys in the body. `MCP-Protocol-
Version` alone, and an MCP session identifier alone, are deliberately NOT direct-mode markers - both
are legitimate on ordinary negotiated SDK traffic. AIP does not run a second general MCP
protocol-era classifier: it only decides "does this request carry an AIP-specific direct marker or
not" and otherwise defers entirely to the pinned SDK's own `initialize`/negotiation/session
machinery, importing `MODERN_PROTOCOL_VERSIONS` (the same constant `classify_inbound_request` uses)
rather than hard-coding `"2026-07-28"` to recognize the one case that must still be rejected: a
non-`initialize`, markerless request whose `MCP-Protocol-Version` names the direct/single-exchange
era - that combination must never be silently served as negotiated follow-up traffic. Once a request
is classified as direct (by header OR body marker), that classification is sticky even if the body
turns out to be malformed - the direct path owns the failure response rather than falling through to
the SDK's negotiated parse handler.

Every non-POST method (`GET`, `DELETE`, `HEAD`, and everything else) is rejected with HTTP 405
before the SDK is invoked at all, since this stateless release advertises no SSE stream or session
lifecycle on any of them - see spec §8/§30 for the exact per-method contract.

Everything else (per-tool argument-schema validation once inside a recognized tool, Origin/Host
allow-listing) is the SDK's own verified, spec-conformant behavior and is not duplicated here.

Only requests to `MCP_PATH` are inspected at all - anything else passes straight through to the
inner app unmodified, so an unrelated path (e.g. a stray `POST` the outer FastAPI app didn't claim)
gets a normal 404, never a synthesized MCP protocol error.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mcp.shared.inbound import (
    ERROR_CODE_HTTP_STATUS,
    MCP_METHOD_HEADER,
    MCP_NAME_HEADER,
    MCP_PROTOCOL_VERSION_HEADER,
    InboundLadderRejection,
    classify_inbound_request,
)
from mcp_types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY
from mcp_types.jsonrpc import INVALID_PARAMS, INVALID_REQUEST, PARSE_ERROR
from mcp_types.version import MODERN_PROTOCOL_VERSIONS
from starlette.types import ASGIApp, Receive, Scope, Send

from app.mcp.server import TOOL_NAMES

MCP_PATH = "/mcp"
_EXPECTED_ARGUMENT_KEY = "request"
_DEFAULT_HTTP_STATUS = 400
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


def _has_direct_header_marker(headers: Mapping[str, str]) -> bool:
    return MCP_METHOD_HEADER in headers or MCP_NAME_HEADER in headers


def _has_direct_body_marker(parsed: Mapping[str, Any]) -> bool:
    try:
        meta = parsed["params"]["_meta"]
    except (KeyError, TypeError):
        return False
    if not isinstance(meta, Mapping):
        return False
    return PROTOCOL_VERSION_META_KEY in meta or CLIENT_CAPABILITIES_META_KEY in meta


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
        has_header_marker = _has_direct_header_marker(headers)

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
            if has_header_marker:
                # Direct ownership is sticky even over a malformed body: a client that sent
                # mcp-method/mcp-name does not silently fall through to the SDK's negotiated
                # parse handler - the direct path owns the failure response.
                await _send_json_error(
                    send,
                    _DEFAULT_HTTP_STATUS,
                    _error_body(None, PARSE_ERROR, "Malformed JSON body"),
                )
                return
            # No direct marker - not this guard's concern; let the SDK's own parse-error
            # handling respond. No valid method has been extracted, so the negotiated
            # follow-up header check below does not apply either.
            await self._app(scope, replay_receive, send)
            return

        request_id = parsed.get("id")
        has_direct_marker = has_header_marker or _has_direct_body_marker(parsed)

        if has_direct_marker:
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
                arguments = (
                    params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
                )
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
            return

        # No AIP direct-envelope marker at all: this is negotiated-mode traffic. Only
        # `initialize` may be markerless - every other method needs a MCP-Protocol-Version
        # header that does not itself name the direct/single-exchange era. The pinned SDK
        # owns everything else from here: negotiation, session lifecycle, and dispatch,
        # including rejecting a version it does not recognize.
        if parsed.get("method") == "initialize":
            await self._app(scope, replay_receive, send)
            return

        version_header = headers.get(MCP_PROTOCOL_VERSION_HEADER)
        if version_header is None:
            await _send_json_error(
                send,
                _DEFAULT_HTTP_STATUS,
                _error_body(
                    request_id,
                    INVALID_REQUEST,
                    "A negotiated follow-up request requires an MCP-Protocol-Version header",
                ),
            )
            return
        if version_header in MODERN_PROTOCOL_VERSIONS:
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
