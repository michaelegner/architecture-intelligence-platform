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
from app.architecture_intelligence.observation_context import build_observation_context_ref
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

        A supplied `observation_context`'s *values* (bad offset, reversed/excessive window, invalid
        environment) are pre-validated here, before dispatch, by calling the exact same
        `build_observation_context_ref` helper the service itself calls internally - not a
        reimplementation, the same pure function, called once more for its side-effect-free
        `pydantic.ValidationError`. This is deliberate, not redundant: a first review round of this
        file caught that catching `pydantic.ValidationError` broadly *around the service call*
        conflates two very different things. `ArchitectureIntelligenceService.get_service_dependencies`
        documents that a malformed *caller-supplied* context value raises `ValidationError` - safe to
        echo back, it only describes the caller's own field/value. But `SnapshotRef`,
        `DependencyClaim`/`EntityRef`, `ServiceDependenciesData`, and the final `ArchitectureAnswer`
        are *also* Pydantic models, constructed from real graph data *after* that point - a
        (hypothetical, bug-indicating) `ValidationError` from any of those would carry a Pydantic
        `input_value` built from internal graph/output data, and passing that error's `str()` through
        to the client the same way would defeat the SDK's own sanitization for exactly the class of
        failure it exists to catch (spec §15/§20's "raw ... values outside the public contract are
        never returned"). Pre-validating here means the service call below is never wrapped in a
        `pydantic.ValidationError` handler at all: if a `ValidationError` somehow still escapes the
        service (it shouldn't, once the context is already known-valid), it is *supposed* to fall
        through uncaught into the SDK's own generic sanitization - see the next paragraph.

        Confirmed live (`mcp.server.mcpserver.tools.base.Tool.run`) that the SDK itself already
        sanitizes any uncaught tool-body exception (this one included) into
        `UnexpectedToolError("Error executing tool get_service_dependencies")` - by design, never
        interpolating `str(exc)` - and separately logs the real exception and traceback server-side
        (`mcp.server.mcpserver.server._handle_call_tool`'s `logger.exception(...)`). That already
        satisfies spec §16's "Unexpected internal/driver failure -> Sanitized tool execution error"
        row and the same release blocker with no adapter code needed for that class of failure.

        Every other outcome (`ANSWERED`/`PARTIAL`/`NOT_ANSWERED`, including a
        `SNAPSHOT_NOT_AVAILABLE`/`UNKNOWN_ENTITY`/etc. refusal) is a normal *returned*
        `ArchitectureAnswer`, never an exception - the SDK's default "no exception raised" path
        already gives `isError: false` for those, satisfying spec §10 rule 5 with no code needed
        here.
        """
        context = request.observation_context
        if context is not None and context.is_complete:
            try:
                build_observation_context_ref(
                    context.environment, context.window_start, context.window_end
                )
            except pydantic.ValidationError as exc:
                raise ToolError(str(exc)) from exc

        return get_service().get_service_dependencies(request)

    for tool_name in ("get_evidence", "get_service_dependencies"):
        _close_input_schema(server, tool_name)


def _close_input_schema(server: MCPServer, tool_name: str) -> None:
    tool = server._tool_manager.get_tool(tool_name)
    tool.parameters["additionalProperties"] = False
