"""v0.4.0 I2.1/I2.2 - registers the two I2 tools for discovery (spec §9, §19's "deterministic
two-tool discovery") and gives `get_service_dependencies` its real dispatch body (spec §10).

`get_evidence` still raises `ToolError` here: discoverable via `tools/list`, not yet callable -
its service logic lands in I2.3. Do not add real dispatch logic for it here.

`register_tools` takes an explicit `MCPServer` rather than registering directly against the
module-level singleton, so tests can build an isolated server (and session manager) per test instead
of sharing `app.mcp.server.mcp_server`'s across an entire event loop/test run. It also takes an
explicit `get_service` callable (defaulting to `app.mcp.wiring.get_service`, the real lazy production
lookup - see that module's docstring for why the lookup must be lazy) for the same reason: a test
closes over its own real-or-stub `ArchitectureIntelligenceService` instead of mutating the shared
production wiring singleton. `get_service` is called once per `get_service_dependencies` dispatch,
never at registration time.

Each tool takes one `request` parameter typed as the real I1/I2 request model, so the SDK derives
`inputSchema` from that model's own (already frozen/tested) schema, nested under a `request` key
(confirmed live: the SDK always synthesizes a wrapper argument model for a function's parameters,
never uses a single `BaseModel`-typed parameter's schema directly) - `outputSchema`, by contrast, IS
used directly for a `BaseModel`-typed return value (confirmed live), so `structuredContent` is the
bare `ArchitectureAnswer` envelope per spec §10 rule 3. That wrapper argument model does not itself
declare `additionalProperties: false` (confirmed live - `mcp.server.mcpserver.utilities.func_metadata
.ArgModelBase` has no `extra="forbid"`), which would leave the *advertised* `inputSchema` open even
though `app.mcp.guard` already rejects an unexpected top-level argument key at runtime. Spec §9
requires a genuinely closed `inputSchema`, so `_close_input_schema` mutates each registered tool's
`Tool.parameters` (the dict `tools/list` serializes) after registration to match the behavior the
guard already enforces - the schema and the runtime agree either way; this makes the *advertised*
contract say so too.
"""

from __future__ import annotations

from collections.abc import Callable

import pydantic
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    EvidenceData,
    ServiceDependenciesData,
)
from app.architecture_intelligence.request import EvidenceRequest, ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.mcp import wiring

_READ_ONLY_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def register_tools(
    server: MCPServer,
    *,
    get_service: Callable[[], ArchitectureIntelligenceService] = wiring.get_service,
) -> None:
    """Registration order IS `tools/list` order - confirmed live that the SDK reports tools in
    registration order, not sorted. Spec §9 requires exactly `get_evidence`,
    `get_service_dependencies` (lexicographic) - `get_evidence` is registered first for that
    reason. Do not reorder without re-checking tests/unit/test_mcp_discovery.py's exact-order
    assertion."""

    @server.tool(
        name="get_evidence",
        description=(
            "Resolves 1..20 opaque evidence references to bounded, sanitized provenance for one "
            "explicit snapshot."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    def get_evidence(request: EvidenceRequest) -> ArchitectureAnswer[EvidenceData]:
        raise ToolError("get_evidence is not yet implemented (lands in I2.3)")

    @server.tool(
        name="get_service_dependencies",
        description=(
            "One-hop direct dependencies of a service, qualified against declared and observed "
            "evidence and bound to a stable snapshot."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    def get_service_dependencies(
        request: ServiceDependenciesRequest,
    ) -> ArchitectureAnswer[ServiceDependenciesData]:
        """Spec §10: constructs no new semantics - calls
        `ArchitectureIntelligenceService.get_service_dependencies` exactly once and returns its
        answer unchanged as `structuredContent` (confirmed live in I2.1: a `BaseModel`-typed return
        value is used directly, not wrapped).

        Only one exception is caught here. `pydantic.ValidationError` is
        `ArchitectureIntelligenceService.get_service_dependencies`'s own documented, deliberate
        signal for a malformed *value* inside a supplied `observation_context` (bad offset,
        reversed/excessive window, invalid environment) - spec §16's "Invalid tool arguments" row,
        just raised by the service instead of the SDK's own argument-schema check. Its message only
        describes the caller's own submitted field/value, never server internals, so it is
        deliberately re-raised as a `ToolError` (not left to fall into the generic crash path below)
        so the caller gets that actionable detail instead of a generic internal-error message.

        Nothing else needs to be caught. Confirmed live (`mcp.server.mcpserver.tools.base.Tool.run`)
        that the SDK itself already sanitizes any *other* uncaught tool-body exception into
        `UnexpectedToolError("Error executing tool get_service_dependencies")` - by design, never
        interpolating `str(exc)` - and separately logs the real exception and traceback server-side
        (`mcp.server.mcpserver.server._handle_call_tool`'s `logger.exception(...)`). That already
        satisfies spec §16's "Unexpected internal/driver failure -> Sanitized tool execution error"
        row and the §15/§20 "connection strings, server paths ... never returned" release blocker
        (e.g. a Neo4j connectivity failure's message, which can embed the bolt URI/host) with no
        adapter code - duplicating it here would be redundant, not additionally safe.

        Every other outcome (`ANSWERED`/`PARTIAL`/`NOT_ANSWERED`, including a
        `SNAPSHOT_NOT_AVAILABLE`/`UNKNOWN_ENTITY`/etc. refusal) is a normal *returned*
        `ArchitectureAnswer`, never an exception - the SDK's default "no exception raised" path
        already gives `isError: false` for those, satisfying spec §10 rule 5 with no code needed
        here.
        """
        try:
            return get_service().get_service_dependencies(request)
        except pydantic.ValidationError as exc:
            raise ToolError(str(exc)) from exc

    for tool_name in ("get_evidence", "get_service_dependencies"):
        _close_input_schema(server, tool_name)


def _close_input_schema(server: MCPServer, tool_name: str) -> None:
    tool = server._tool_manager.get_tool(tool_name)
    tool.parameters["additionalProperties"] = False
