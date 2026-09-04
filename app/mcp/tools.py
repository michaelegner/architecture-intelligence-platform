"""v0.4.0 I2.1 - registers the two I2 tools for discovery (spec §9, §19's "deterministic two-tool
discovery").

Both bodies raise `ToolError` here: discoverable via `tools/list`, not yet callable. Mapping to
`ArchitectureIntelligenceService` is out of scope for the "Protocol and Contract Skeleton"
sub-increment - `get_service_dependencies`'s real dispatch lands in I2.2, `get_evidence`'s in I2.3.
Do not add real dispatch logic here.

`register_tools` takes an explicit `MCPServer` rather than registering directly against the
module-level singleton, so tests can build an isolated server (and session manager) per test instead
of sharing `app.mcp.server.mcp_server`'s across an entire event loop/test run.

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

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    EvidenceData,
    ServiceDependenciesData,
)
from app.architecture_intelligence.request import EvidenceRequest, ServiceDependenciesRequest

_READ_ONLY_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def register_tools(server: MCPServer) -> None:
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
        raise ToolError("get_service_dependencies is not yet implemented (lands in I2.2)")

    for tool_name in ("get_evidence", "get_service_dependencies"):
        _close_input_schema(server, tool_name)


def _close_input_schema(server: MCPServer, tool_name: str) -> None:
    tool = server._tool_manager.get_tool(tool_name)
    tool.parameters["additionalProperties"] = False
