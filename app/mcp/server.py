"""v0.4.0 I2.1 - the `MCPServer` instance (spec `docs/specifications/0.4.0/
i2-mcp-vertical-slice-and-evidence-drill-down.md` §4, §9).

Built on the official `mcp` SDK (pinned `mcp==2.1.1`). The following was verified directly against
the installed package - it isn't documented on the SDK's own doc pages - and shapes this module and
`app.mcp.guard`:

- `MCPServer.streamable_http_app(json_response=True, stateless_http=True, transport_security=...)`
  is the ASGI app to mount. `transport_security=TransportSecuritySettings(allowed_origins=[...])`
  is the SDK's own Origin-validation mechanism (spec §15) - confirmed live (a disallowed Origin is
  rejected before reaching any handler); no custom code needed for that.
- A tool body raises `mcp.server.mcpserver.exceptions.ToolError` for an anticipated failure; the
  SDK turns it into a normal `CallToolResult(is_error=True, ...)` - confirmed live. This is exactly
  spec §16's "Invalid tool arguments -> Tool execution error with isError: true" row, and the SDK
  already applies it automatically to arguments that fail a tool's input schema.
- A single Pydantic `BaseModel`-typed parameter (e.g. `request: EvidenceRequest`) is NOT flattened:
  the SDK synthesizes a wrapper argument model whose one property is the parameter name, `$ref`-ing
  the real model's own schema (so the model's own `extra=forbid`/patterns/cross-field validators
  are preserved faithfully). A `BaseModel`-typed *return* value, by contrast, is used directly as
  `structuredContent` (not wrapped in `{"result": ...}`) - confirmed live against
  `ArchitectureAnswer[ServiceDependenciesData]`. Both tools below take a single `request` parameter
  for this reason: `{"request": {...}}` is what a caller sends, and it's a clean, well-defined
  isomorphism to the wrapped request type (spec §10 rule 1), not a byte-identical top-level schema.
- `MCPServer(cache_hints={...})` takes a `CacheHint(scope, ttl_ms)` per `CacheableMethod`, and
  `"tools/list"` is one - this is what spec §9's "required cache metadata SHALL be deterministic"
  refers to. Confirmed live: without an explicit hint the SDK defaults `tools/list`'s `cacheScope`
  to `"private"`, which is a odd default given I2 has no authorization (spec §15) to scope by -
  `"public"` is supplied explicitly below instead. `ttl_ms=0` ("immediately stale") is a deliberate,
  conservative choice for a skeleton increment: the tools/list content is genuinely static, but nothing
  here invalidates a longer-lived client-side cache if the process is redeployed with a schema change.
- Routing between the 2026-07-28 "modern" single-exchange path and the legacy `initialize`/session
  path is header-driven inside the SDK and is NOT controlled by `stateless_http`: confirmed live that
  a request whose `MCP-Protocol-Version` header is absent, or names a pre-2026-07-28 handshake
  version, is still served (with a normal 200 response) by the legacy path. Per spec §4/§20
  ("implementation requires initialize while claiming MCP 2026-07-28" is a release blocker),
  `app.mcp.guard` rejects that case in front of the mounted app.
- Confirmed live that the SDK's own `tools/call` dispatch turns an unknown tool name into
  `ToolError("Unknown tool: ...")` -> `is_error=True` inside a normal 200 result, not a JSON-RPC
  protocol error. Spec §16's table requires "unknown method/tool" to be a JSON-RPC protocol error,
  distinct from "invalid tool arguments". `app.mcp.guard` corrects this one case too, ahead of the
  SDK's own dispatch, and also closes a related gap: the SDK's synthesized argument wrapper does not
  reject an unexpected top-level key (e.g. `{"request": {...}, "junk": 1}`) - confirmed live - so the
  guard also enforces that a `tools/call`'s `arguments` contain only the expected `request` key.
"""

from __future__ import annotations

from mcp.server import CacheHint, MCPServer

from app.mcp.tools import register_tools

TOOL_NAMES = ("get_evidence", "get_service_dependencies")

_TOOLS_LIST_CACHE_HINT = CacheHint(scope="public", ttl_ms=0)

mcp_server: MCPServer = MCPServer(
    name="architecture-intelligence-platform",
    version="0.4.0",
    cache_hints={"tools/list": _TOOLS_LIST_CACHE_HINT},
)
register_tools(mcp_server)
