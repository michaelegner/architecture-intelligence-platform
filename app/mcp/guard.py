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

A request is routed to direct-mode validation above when it carries at least one of these header/body
markers: the `mcp-method`/`mcp-name` HTTP headers, or `params._meta`'s
`io.modelcontextprotocol/protocolVersion`/`clientCapabilities` keys in the body. `MCP-Protocol-
Version` alone, and an MCP session identifier alone, are deliberately NOT direct-mode markers - both
are legitimate on ordinary negotiated SDK traffic. AIP does not run a second general MCP
protocol-era classifier: it only decides "does this request carry a direct marker or not" and
otherwise defers entirely to the pinned SDK's own `initialize`/negotiation/session machinery,
importing `MODERN_PROTOCOL_VERSIONS` (the same constant `classify_inbound_request` uses) rather than
hard-coding `"2026-07-28"` to recognize the one case that must still be rejected: a non-`initialize`,
markerless request whose `MCP-Protocol-Version` names the direct/single-exchange era - that
combination must never be silently served as negotiated follow-up traffic. Once a request is
classified as direct (by header OR body marker), that classification is sticky even if the body turns
out to be malformed - the direct path owns the failure response rather than falling through to the
SDK's negotiated parse handler.

**These markers are not AIP-proprietary** - `MCP_METHOD_HEADER`/`MCP_NAME_HEADER` are the pinned SDK's
own header names (imported from `mcp.shared.inbound`, not invented here), and real MCP clients can
legitimately send them for their own SDK-native purposes unrelated to AIP's historical `tools/list`/
`tools/call`-only hero-demo envelope (v0.4.2 I3.3 actual-client-qualification finding: Claude Code's own MCP client
sends `mcp-method: server/discover` and `mcp-method: subscriptions/listen` as part of its ordinary
capability-discovery/notification-subscription handshake under protocol era `2026-07-28`). A request
carrying a direct marker is therefore validated against `_DIRECT_MODE_METHODS` - the closed set of
methods direct mode has ever actually implemented (`tools/list`, `tools/call`) - and anything else is
rejected with a fast, deterministic `METHOD_NOT_FOUND` **before** ever reaching `self._app`, rather
than being forwarded on the assumption that "carries a direct marker" implies "is safe to dispatch
into the mounted SDK app unmodified". Forwarding an unrecognized-but-SDK-native method blindly is
exactly how a real client's ordinary traffic previously reached an SDK code path
(`subscriptions/listen`'s long-lived-notification handling) that hangs indefinitely under AIP's
stateless single-worker deployment - a single such request pegged the process and made it unresponsive
to every other client, including its own health check. This is a closed allowlist by design, not a
per-method denylist: any future SDK-native method this guard has not been taught about is rejected the
same way, never blindly trusted.

A markerless negotiated follow-up with **no** `MCP-Protocol-Version` header at all is forwarded to the
pinned SDK, not rejected (v0.4.2 I1 amendment, I3.4 VS Code actual-client-qualification finding). Only
a markerless follow-up that *explicitly* names the direct/single-exchange `2026-07-28` era is still
rejected outright - that specific contradiction (claims the direct era, behaves like negotiated
traffic) is never delegated. A missing header is a different case, governed by two distinct MCP
specification statements: the client MUST include this header on every subsequent request (a client
omitting it is not itself spec-conformant), and *separately*, a server that receives no such header
and has no other way to identify the version SHOULD assume protocol version 2025-03-26 rather than
reject - a backward-compatibility allowance for exactly this non-conformant-but-real traffic, not a
license authorizing clients to omit the header. The pinned SDK already implements that server-side
fallback (`DEFAULT_NEGOTIATED_VERSION` in `mcp.server.streamable_http`). Before this amendment, AIP's
guard enforced only the client-side MUST, as a hard rejection, with no allowance at all for the
server-side SHOULD: it hard-rejected every markerless follow-up missing the header, which is precisely
how GitHub Copilot Chat's real MCP client in VS Code was directly observed to behave on
`notifications/initialized` even after correctly negotiating a current protocol version (the client's
own trace log shows no `MCP-Protocol-Version` header on that request; its queued `prompts/list`/
`tools/list` calls never completed once the connection died there, so their headers were never
observed - the fix's coverage of all markerless follow-ups is a general contract requirement, not a
claim that those two calls were confirmed headerless too) - the strict check made VS Code unable to
connect to AIP at all, not merely on some inputs, regardless of whose spec obligation was technically
at issue.

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
from mcp_types.jsonrpc import INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR
from mcp_types.version import MODERN_PROTOCOL_VERSIONS
from starlette.types import ASGIApp, Receive, Scope, Send

from app.mcp.tools import TOOL_NAMES

MCP_PATH = "/mcp"
_EXPECTED_ARGUMENT_KEY = "request"
_DEFAULT_HTTP_STATUS = 400
_MAX_REQUEST_BODY_BYTES = 1024 * 1024
_PAYLOAD_TOO_LARGE_STATUS = 413

# The closed set of methods direct mode has ever actually implemented (see module docstring's
# "These markers are not AIP-proprietary" section for why this allowlist exists at all - a
# real client's own SDK-native, non-AIP method reaching this guard's direct-marked path must
# never be blindly forwarded into the mounted SDK app on the assumption that "carries a direct
# marker" implies "is a method direct mode actually supports").
_DIRECT_MODE_METHODS = frozenset({"tools/list", "tools/call"})
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

            method = parsed.get("method")
            if method not in _DIRECT_MODE_METHODS:
                # A direct-marked request naming a method direct mode has never implemented -
                # e.g. a real client's own SDK-native `server/discover`/`subscriptions/listen`
                # traffic that happens to carry the same header names AIP's own hero-demo script
                # uses. Reject fast and deterministically rather than forwarding into the mounted
                # SDK app on a hope-it-works basis (see module docstring).
                await _send_json_error(
                    send,
                    ERROR_CODE_HTTP_STATUS.get(METHOD_NOT_FOUND, _DEFAULT_HTTP_STATUS),
                    _error_body(request_id, METHOD_NOT_FOUND, "Method not found", method),
                )
                return

            if method == "tools/call":
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

        # No AIP direct-envelope marker at all: this is negotiated-mode traffic. Only a
        # markerless follow-up that explicitly names the direct/single-exchange era is rejected
        # here - that specific contradiction (claims the direct era, behaves like negotiated
        # traffic) is never delegated. A *missing* MCP-Protocol-Version header is not that
        # contradiction, but it is not spec-conformant client behavior either: the MCP spec's
        # client-side rule says the client MUST include this header on every follow-up. What the
        # spec ALSO says, separately, is a server-side backward-compatibility rule: if the server
        # receives no such header and has no other way to identify the version, it SHOULD assume
        # protocol version 2025-03-26 rather than reject (basic/transports#protocol-version-header)
        # - tolerance for exactly this non-conformant-but-real traffic, not a license to omit the
        # header. The pinned SDK already implements that server-side fallback
        # (`DEFAULT_NEGOTIATED_VERSION`, `mcp.server.streamable_http`). Real-client finding (I3.4
        # VS Code + GitHub Copilot Chat qualification, `mcp==2.2.0`-negotiated
        # `protocolVersion: "2025-11-25"`): VS Code's own MCP client was directly observed sending
        # `notifications/initialized` with no MCP-Protocol-Version header at all - rejecting that
        # killed the connection outright before its queued `prompts/list`/`tools/list` could
        # complete (their own headers were never observed as a result), regardless of whether VS
        # Code's own omission was itself spec-conformant. The pinned SDK owns everything else
        # from here: negotiation, session lifecycle, and dispatch, including its own graceful
        # missing-header default and rejecting a version it does not recognize.
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
