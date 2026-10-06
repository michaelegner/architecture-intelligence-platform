"""v0.4.0 I2.1/I2.2/I2.3 - registers the two I2 tools for discovery (spec §9, §19's "deterministic
two-tool discovery") and gives both `get_service_dependencies` and `get_evidence` their real
dispatch bodies (spec §10, §11).

v0.4.0 I3.2 adds a third tool, `get_architecture_drift` (I3 spec §23), registered first so
`tools/list`'s now-three-tool discovery stays lexicographic (I3 spec §24). Its `ArchitectureDriftRequest`
carries the identical `observation_context` shape `ServiceDependenciesRequest` does (I3.1 pinned
this field-validation equivalence), so the pre-dispatch context check below is factored into
`_reject_malformed_observation_context` and shared by both tools rather than duplicated.

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
.ArgModelBase` has no `extra="forbid"`), which would leave the *advertised* `inputSchema` open. Spec §9
requires a genuinely closed `inputSchema`, so `_close_input_schema` mutates each registered tool's
`Tool.parameters` (the dict `tools/list` serializes) after registration. At runtime, the SDK's
wrapper still drops an unexpected top-level key for the three v0.5 tools (nothing in front of the
SDK rejects it since v0.5.0 I3 slice 5a; `tests/unit/test_mcp_discovery.py` documents this). For
the fourth tool, v0.6.0 I3.3b (I3 decision record D12) closes the runtime too:
`_reject_unexpected_arguments` replaces its argument model with a closed one.
"""

from __future__ import annotations

from collections.abc import Callable

import pydantic
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.architecture_intelligence.broker_contracts import EvidenceAnswer, ServiceDependenciesAnswer
from app.architecture_intelligence.contracts import (
    TOOL_NAMES,
    ArchitectureAnswer,
    ArchitectureDriftData,
)
from app.architecture_intelligence.locality_contracts import (
    LOCALITY_TOOL_NAME,
    LocalityAnswer,
    LocalityQueryRequest,
    ServiceDependenciesByLocalityRequest,
)
from app.architecture_intelligence.observation_context import reject_malformed_observation_context
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ObservationContextInput,
    ServiceDependenciesRequest,
)
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
    registration order, not sorted. I3 spec §24 requires lexicographic order:
    `get_architecture_drift`, `get_evidence`, `get_service_dependencies`, and since v0.6.0 I3.3b
    the fourth tool `get_service_dependencies_by_locality` (I3 decision record D1) - registered in
    that order below. Do not reorder without re-checking tests/unit/test_mcp_discovery.py's
    exact-order assertion."""

    @server.tool(
        name="get_architecture_drift",
        description=(
            "Direct service dependencies whose current evidence qualification shows a "
            "declared-versus-observed discrepancy, bound to the same stable snapshot."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    def get_architecture_drift(
        request: ArchitectureDriftRequest,
    ) -> ArchitectureAnswer[ArchitectureDriftData]:
        """I3 spec §23: constructs no new semantics - calls
        `ArchitectureIntelligenceService.get_architecture_drift` exactly once and returns its answer
        unchanged as `structuredContent`. Follows the exact same input-error-mapping split as
        `get_service_dependencies` below (I3 spec §46): only the caller's own `observation_context`
        *values* are pre-validated here, via the shared `_reject_malformed_observation_context`;
        every other outcome, including any refusal, is a normal returned `ArchitectureAnswer`, and
        any unexpected internal/driver failure falls through uncaught into the same SDK sanitization
        `get_service_dependencies` relies on.
        """
        _reject_malformed_observation_context(request.observation_context)
        return get_service().get_architecture_drift(request)

    @server.tool(
        name="get_evidence",
        description=(
            "Resolves 1..20 opaque evidence references to bounded, sanitized provenance for one "
            "explicit snapshot."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=False,  # `_advertise_version_union` below publishes the real contract
    )
    def get_evidence(request: EvidenceRequest) -> EvidenceAnswer:
        """Spec §11: constructs no new semantics - calls
        `ArchitectureIntelligenceService.get_evidence` exactly once and returns its answer
        unchanged as `structuredContent`. Unlike `get_service_dependencies`, `EvidenceRequest` has
        no observation-context values to pre-validate before dispatch - `evidence_refs`/
        `snapshot_id` are already fully validated by the closed `inputSchema`/Pydantic model before
        this body runs, so there is nothing left to check here. Any unexpected internal/driver
        failure still falls through uncaught into the SDK's own generic sanitization, same as
        `get_service_dependencies` below.
        """
        return get_service().get_evidence(request)

    @server.tool(
        name="get_service_dependencies",
        description=(
            "One-hop direct dependencies of a service, qualified against declared and observed "
            "evidence and bound to a stable snapshot. Also returns the service's Service-Workload "
            "deployment claims and resolutions (explicit annotation, configured mapping, or "
            "observed OpenTelemetry/Kubernetes linkage), reconciled across all applicable methods."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=False,  # `_advertise_version_union` below publishes the real contract
    )
    def get_service_dependencies(
        request: ServiceDependenciesRequest,
    ) -> ServiceDependenciesAnswer:
        """Spec §10: constructs no new semantics - calls
        `ArchitectureIntelligenceService.get_service_dependencies` exactly once and returns its
        answer unchanged as `structuredContent` (confirmed live in I2.1: a `BaseModel`-typed return
        value is used directly, not wrapped).

        A supplied `observation_context`'s *values* (bad offset, reversed/excessive window, invalid
        environment) are pre-validated here, before dispatch, by the shared
        `_reject_malformed_observation_context` helper, which calls the exact same
        `build_observation_context_ref` the service itself calls internally - not a
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
        _reject_malformed_observation_context(request.observation_context)
        return get_service().get_service_dependencies(request)

    @server.tool(
        name=LOCALITY_TOOL_NAME,
        description=(
            "Discovers evidenced caller-Workload localities of a service and returns its positively "
            "established HTTP dependencies per locality, with an optional same-snapshot comparison "
            "of two localities. The results are not an exhaustive partition of the service's "
            "dependencies: a missing relationship does not establish local absence, and unknown, "
            "unresolved, excluded and unscanned items stay explicit. With request.mode "
            '"evidence", the same tool resolves exact scoped evidence refs from such an answer at '
            "the supplied snapshot, without widening get_evidence."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
    )
    def get_service_dependencies_by_locality(
        request: ServiceDependenciesByLocalityRequest,
    ) -> LocalityAnswer:
        """v0.6.0 I3.3b (I3 decision record D1): constructs no new semantics. It dispatches on
        `request.mode` to exactly one service method and returns that answer unchanged as
        `structuredContent`. Every refusal is a normal returned `LocalityAnswer`; an unexpected
        internal failure falls through to the SDK's own sanitization, as for the other tools."""
        parsed = request.root
        if isinstance(parsed, LocalityQueryRequest):
            return get_service().get_service_dependencies_by_locality(parsed)
        return get_service().resolve_scoped_locality_evidence(parsed)

    _advertise_version_union(server, "get_evidence", EvidenceAnswer)
    _advertise_version_union(server, "get_service_dependencies", ServiceDependenciesAnswer)
    for tool_name in (*TOOL_NAMES, LOCALITY_TOOL_NAME):
        _close_input_schema(server, tool_name)
    _reject_unexpected_arguments(server, LOCALITY_TOOL_NAME)


def _reject_malformed_observation_context(context: ObservationContextInput | None) -> None:
    """Shared by `get_architecture_drift` and `get_service_dependencies` (I3 spec §23/§46): the only
    two tools whose request carries an `observation_context` to pre-validate. MCP-specific
    translation of the shared cross-adapter check (v0.5.0 I3 slice 5a,
    `app.architecture_intelligence.observation_context.reject_malformed_observation_context` - also
    used by the REST adapter) into `ToolError` for a malformed *caller-supplied* value (bad offset,
    reversed/excessive window, invalid environment) - see `get_service_dependencies`'s docstring
    above for why this must happen before, not around, the service call itself."""
    try:
        reject_malformed_observation_context(context)
    except pydantic.ValidationError as exc:
        raise ToolError(str(exc)) from exc


def _advertise_version_union(server: MCPServer, tool_name: str, answer_union: object) -> None:
    """v0.6.1 I2b (spec §5.2): publish a `oneOf` output schema discriminated by `schema_version`
    (the released v0.5 answer plus the Broker-aware v0.6 answer) while keeping `structuredContent`
    the bare answer envelope.

    A union return annotation cannot do this by itself: the SDK wraps any non-model return value as
    `{"result": ...}` (confirmed live), which would change the v0.5 `structuredContent` shape for
    every existing client. So the tools are registered with `structured_output=False` and this step
    sets the output fields the SDK reads live on every call (`FuncMetadata.output_model`,
    `.output_schema`, `.wrap_output`): results are validated against the union and dumped through
    the returned instance, exactly like a single `BaseModel` return, and `tools/list` advertises
    the union schema. `"type": "object"` is added at the root because every branch is an object."""
    tool = server._tool_manager.get_tool(tool_name)
    assert tool is not None  # register_tools registered it just above
    adapter: pydantic.TypeAdapter = pydantic.TypeAdapter(answer_union)
    schema = adapter.json_schema()
    schema["type"] = "object"
    metadata = tool.fn_metadata
    metadata.output_model = answer_union
    metadata.output_schema = schema
    metadata.wrap_output = False


def _close_input_schema(server: MCPServer, tool_name: str) -> None:
    tool = server._tool_manager.get_tool(tool_name)
    assert tool is not None  # register_tools registers every TOOL_NAMES entry before calling this
    tool.parameters["additionalProperties"] = False


def _reject_unexpected_arguments(server: MCPServer, tool_name: str) -> None:
    """D12 (I3 decision record): the new tool rejects every top-level argument other than
    `request` before dispatch. The SDK's synthesized argument model ignores unknown keys, so this
    tool's model is replaced by a closed subclass. The SDK reads `fn_metadata.arg_model` on every
    call, so an extra key now fails the SDK's own argument validation, as an `isError` result like
    any other schema failure. The three v0.5 tools keep their existing behaviour (I3 spec §2)."""
    tool = server._tool_manager.get_tool(tool_name)
    assert tool is not None
    base = tool.fn_metadata.arg_model

    class ClosedArguments(base):
        model_config = pydantic.ConfigDict(**{**base.model_config, "extra": "forbid"})

    ClosedArguments.__name__ = base.__name__
    tool.fn_metadata.arg_model = ClosedArguments
