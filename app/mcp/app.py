"""v0.4.0 I2.1 - assembles the mounted `/mcp` ASGI app: the SDK's streamable HTTP app, wrapped by
`ModernProtocolGuard`, configured for JSON-only stateless responses and Origin allow-listing (spec
§15).

Both functions default to the shared `app.mcp.server.mcp_server` singleton (with both tools already
registered) for real production use via `app.main`. Tests pass an isolated `server` explicitly
(`MCPServer(...)` + `register_tools(server)`) rather than sharing the singleton, since its session
manager's task group must be entered and exited on one event loop - reusing the module-level
singleton across independently loop-scoped tests raises anyio's cross-task cancel scope error.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp

from app.mcp.guard import ModernProtocolGuard
from app.mcp.server import mcp_server as _default_mcp_server


def build_mcp_app(
    *, allowed_origins: list[str], allowed_hosts: list[str], server: MCPServer | None = None
) -> ASGIApp:
    """Returns the ASGI app to mount at Starlette prefix `/` (not `/mcp`) in the host FastAPI app.

    Keeps the SDK's own default `streamable_http_path="/mcp"`, so `app.main` must mount this at `/`,
    registered after every other router, so it only ever receives requests no other route claimed
    (in practice, exactly `POST /mcp`, spec §9's one endpoint). Mounting it at an outer `/mcp` prefix
    instead (keeping the SDK's own internal `/mcp` route) would need `streamable_http_path="/"` to
    avoid doubling to `/mcp/mcp` - but that makes the *sub-app's* route path `/`, and a request to
    the outer prefix `/mcp` (no trailing slash) doesn't match Starlette's mounted `/` route, so
    Starlette 307-redirects it to `/mcp/` first - confirmed live. A plain `POST /mcp` must work
    without a redirect, so this mounts at `/` instead and lets the sub-app's own `/mcp` route match
    directly.
    """
    server = server or _default_mcp_server
    inner = server.streamable_http_app(
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            allowed_origins=allowed_origins, allowed_hosts=allowed_hosts
        ),
    )
    return ModernProtocolGuard(inner)


@asynccontextmanager
async def mcp_session_manager_lifespan(server: MCPServer | None = None) -> AsyncIterator[None]:
    """`MCPServer.session_manager` must run for the lifetime of the process (it owns the
    stateless-mode task group); fold this into `app.main`'s existing lifespan."""
    server = server or _default_mcp_server
    async with server.session_manager.run():
        yield
