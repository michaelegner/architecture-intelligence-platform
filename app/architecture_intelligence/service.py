"""v0.4.0 I1.3 - `ArchitectureIntelligenceService`, the sole semantic entry point I1 introduces
(spec §7). Implements `get_service_dependencies` per the reference processing flow (spec §22).
"""

from __future__ import annotations

import neo4j

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    DependencyClaim,
    EntityRef,
    EntityType,
    Limitation,
    LimitationCode,
    ObservationContextRef,
    Outcome,
    Producer,
    ServiceDependenciesData,
    SnapshotRef,
)
from app.architecture_intelligence.dependency_projection import project_service_dependencies
from app.architecture_intelligence.observation_context import build_observation_context_ref
from app.architecture_intelligence.repository import (
    SnapshotUnstable,
    read_service_dependency_rows,
    read_stable_snapshot_from_session,
)
from app.architecture_intelligence.request import ServiceDependenciesRequest
from app.graph.repository import open_session

_TOOL_NAME = "get_service_dependencies"
_MAX_CLAIMS = 500


def _claim_sort_key(claim: DependencyClaim) -> tuple[str, str, str, str]:
    return (claim.object.id, claim.delivery.kind.value, claim.delivery.via.id, claim.claim_id)


def _limitation_sort_key(limitation: Limitation) -> tuple[str, str]:
    return (limitation.code.value, limitation.message)


class ArchitectureIntelligenceService:
    """The only semantic entry point I1 introduces (spec §7). Opens its own `READ_ACCESS` session
    for every call - no caller (the I1 evaluator today; a future MCP/REST adapter) is ever handed a
    session, a Cypher expression or a graph record, and `dependency_projection` never touches Neo4j
    at all - only the plain rows `repository.read_service_dependency_rows` already projected."""

    def __init__(
        self,
        driver: neo4j.Driver,
        *,
        database: str,
        producer: Producer,
        coverage_qualification_enabled: bool = True,
    ) -> None:
        self._driver = driver
        self._database = database
        self._producer = producer
        self._coverage_qualification_enabled = coverage_qualification_enabled

    def get_service_dependencies(
        self, request: ServiceDependenciesRequest
    ) -> ArchitectureAnswer[ServiceDependenciesData]:
        context_input = request.observation_context
        context_complete = context_input is not None and context_input.is_complete
        # Malformed values inside a *supplied* context (bad offset, reversed/excessive window,
        # invalid environment) raise pydantic.ValidationError here - an input-schema error, not a
        # semantic refusal (spec §21) - and are expected to propagate out of this call uncaught.
        context_ref = (
            build_observation_context_ref(
                context_input.environment, context_input.window_start, context_input.window_end
            )
            if context_complete
            else None
        )

        with open_session(self._driver, database=self._database, read_only=True) as session:
            read_extra = (
                (
                    lambda s: read_service_dependency_rows(
                        s,
                        service_id=request.service_id,
                        environment=context_ref.environment,
                        window_start=context_ref.window_start,
                        window_end=context_ref.window_end,
                    )
                )
                if context_complete
                else (lambda _s: None)
            )
            try:
                snapshot = read_stable_snapshot_from_session(
                    session,
                    coverage_qualification_enabled=self._coverage_qualification_enabled,
                    read_extra=read_extra,
                )
            except SnapshotUnstable:
                return self._refusal(
                    snapshot_ref=None,
                    context_ref=context_ref,
                    code=LimitationCode.SNAPSHOT_NOT_AVAILABLE,
                    message="no consistent current snapshot could be acquired",
                )

            snapshot_ref = SnapshotRef(
                snapshot_id=snapshot.snapshot_id, model_revision=snapshot.model_revision
            )

            if not context_complete:
                return self._refusal(
                    snapshot_ref=snapshot_ref,
                    context_ref=None,
                    code=LimitationCode.OBSERVATION_CONTEXT_REQUIRED,
                    message=(
                        "observation_context.environment/window_start/window_end are all required"
                    ),
                )

            if request.snapshot_id is not None and request.snapshot_id != snapshot.snapshot_id:
                return self._refusal(
                    snapshot_ref=snapshot_ref,
                    context_ref=context_ref,
                    code=LimitationCode.SNAPSHOT_NOT_AVAILABLE,
                    message=(
                        f"requested snapshot {request.snapshot_id} is not the current stable "
                        "snapshot"
                    ),
                )

            rows = snapshot.extra
            if rows["service_name"] is None:
                return self._refusal(
                    snapshot_ref=snapshot_ref,
                    context_ref=context_ref,
                    code=LimitationCode.UNKNOWN_ENTITY,
                    message=f"{request.service_id} does not exist in the current snapshot",
                )

            result = project_service_dependencies(
                rows,
                service_id=request.service_id,
                service_name=rows["service_name"],
                environment=context_ref.environment,
                window_start=context_ref.window_start,
                window_end=context_ref.window_end,
                coverage_enabled=self._coverage_qualification_enabled,
            )

        if len(result.claims) > _MAX_CLAIMS:
            return self._refusal(
                snapshot_ref=snapshot_ref,
                context_ref=context_ref,
                code=LimitationCode.RESULT_LIMIT_EXCEEDED,
                message=(
                    f"{len(result.claims)} unique dependency claims exceed the "
                    f"{_MAX_CLAIMS}-claim result bound"
                ),
            )

        claims = sorted(result.claims, key=_claim_sort_key)
        limitations = sorted(result.limitations, key=_limitation_sort_key)

        # Every candidate outgoing CALLS/SENDS relation either produced a claim (possibly a
        # DIRECT_TARGET_FALLBACK one, flagged with UNRESOLVED_IDENTITY) or an INSUFFICIENT_EVIDENCE
        # limitation with no claim (dependency_projection never emits any other limitation shape
        # here) - so "claims empty and limitations empty" can only mean zero candidates existed.
        if not claims and not limitations:
            outcome = Outcome.ANSWERED
        elif not claims:
            outcome = Outcome.NOT_ANSWERED
        elif limitations:
            outcome = Outcome.PARTIAL
        else:
            outcome = Outcome.ANSWERED

        if outcome == Outcome.NOT_ANSWERED:
            data = None
            claims = []
        else:
            data = ServiceDependenciesData(
                service=EntityRef(
                    id=request.service_id, type=EntityType.SERVICE, name=rows["service_name"]
                ),
                dependency_claim_ids=[claim.claim_id for claim in claims],
            )

        evidence_refs = sorted(
            {
                ref
                for claim in claims
                for ref in (*claim.evidence_refs, *claim.resolution_evidence_refs)
            }
        )

        return ArchitectureAnswer[ServiceDependenciesData](
            schema_version="0.4",
            producer=self._producer,
            tool=_TOOL_NAME,
            outcome=outcome,
            snapshot=snapshot_ref,
            observation_context=context_ref,
            data=data,
            claims=claims,
            evidence_refs=evidence_refs,
            limitations=limitations,
        )

    def _refusal(
        self,
        *,
        snapshot_ref: SnapshotRef | None,
        context_ref: ObservationContextRef | None,
        code: LimitationCode,
        message: str,
    ) -> ArchitectureAnswer[ServiceDependenciesData]:
        return ArchitectureAnswer[ServiceDependenciesData](
            schema_version="0.4",
            producer=self._producer,
            tool=_TOOL_NAME,
            outcome=Outcome.NOT_ANSWERED,
            snapshot=snapshot_ref,
            observation_context=context_ref,
            data=None,
            claims=[],
            evidence_refs=[],
            limitations=[Limitation(code=code, message=message)],
        )
