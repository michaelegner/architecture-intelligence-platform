"""v0.4.0 I1.3 - `ArchitectureIntelligenceService`, the sole semantic entry point I1 introduces
(spec §7). Implements `get_service_dependencies` per the reference processing flow (spec §22).

v0.4.0 I3.1 adds `get_architecture_drift` (I3 spec §14). Both dependency-answering tools share one
private projection step (`_project_direct_dependencies`, I3 spec §15) so the drift answer is a
bounded *view* of the already-qualified I1 dependency answer rather than a second derivation of it.
"""

from __future__ import annotations

from dataclasses import dataclass

import neo4j

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    DependencyClaim,
    EntityRef,
    EntityType,
    EvidenceData,
    Limitation,
    LimitationCode,
    ObservationContextRef,
    Outcome,
    Producer,
    ServiceDependenciesData,
    SnapshotRef,
)
from app.architecture_intelligence.dependency_projection import (
    ProjectionResult,
    project_service_dependencies,
)
from app.architecture_intelligence.drift_projection import project_architecture_drift
from app.architecture_intelligence.evidence_projection import project_evidence
from app.architecture_intelligence.observation_context import build_observation_context_ref
from app.architecture_intelligence.repository import (
    SnapshotUnstable,
    read_evidence_rows,
    read_service_dependency_rows,
    read_stable_snapshot_from_session,
)
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.graph.repository import open_session

_TOOL_NAME = "get_service_dependencies"
_EVIDENCE_TOOL_NAME = "get_evidence"
_DRIFT_TOOL_NAME = "get_architecture_drift"
_MAX_CLAIMS = 500


def _claim_sort_key(claim: DependencyClaim) -> tuple[str, str, str, str]:
    return (claim.object.id, claim.delivery.kind.value, claim.delivery.via.id, claim.claim_id)


def _limitation_sort_key(limitation: Limitation) -> tuple[str, str]:
    return (limitation.code.value, limitation.message)


@dataclass(frozen=True)
class _SharedProjection:
    """v0.4.0 I3.1 - a successful `_project_direct_dependencies` result (I3 spec §15). `projection`
    is the I1 dependency projection with both lists already in their canonical I1 order, so a
    consumer that filters it (the drift tool) preserves that order for free (I3 spec §20)."""

    snapshot_ref: SnapshotRef
    context_ref: ObservationContextRef
    service_name: str
    projection: ProjectionResult


@dataclass(frozen=True)
class _SharedRefusal:
    """v0.4.0 I3.1 - a `_project_direct_dependencies` refusal, carrying whatever snapshot/context
    had been resolved before the refusal was decided. Each public tool wraps it in its own typed
    `ArchitectureAnswer[T]` - the shared step never builds an answer envelope itself."""

    snapshot_ref: SnapshotRef | None
    context_ref: ObservationContextRef | None
    code: LimitationCode
    message: str


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

    def _project_direct_dependencies(
        self,
        *,
        service_id: str,
        observation_context: ObservationContextInput | None,
        snapshot_id: str | None,
    ) -> _SharedProjection | _SharedRefusal:
        """v0.4.0 I3.1 - the step `get_service_dependencies` and `get_architecture_drift` share
        (I3 spec §15): stable snapshot acquisition, explicit-snapshot comparison, observation-context
        completeness, the unknown-service check, the dependency repository read, the I1 dependency
        projection and the 500-claim result bound.

        Deliberately private (I3 spec §15: "It SHALL NOT become a new public method") and deliberately
        envelope-free: it returns semantics, and each public tool renders them into its own
        `ArchitectureAnswer[T]`.

        I3 spec §17: the result bound is applied to the underlying supported direct-dependency
        candidates *here*, before any tool-specific filtering. A drift filter that happens to return
        2 claims out of an unbounded underlying set is not a complete drift answer, so the bound must
        never be evaluated after the filter."""
        context_input = observation_context
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
                        service_id=service_id,
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
                return _SharedRefusal(
                    snapshot_ref=None,
                    context_ref=context_ref,
                    code=LimitationCode.SNAPSHOT_NOT_AVAILABLE,
                    message="no consistent current snapshot could be acquired",
                )

            snapshot_ref = SnapshotRef(
                snapshot_id=snapshot.snapshot_id, model_revision=snapshot.model_revision
            )

            if not context_complete:
                return _SharedRefusal(
                    snapshot_ref=snapshot_ref,
                    context_ref=None,
                    code=LimitationCode.OBSERVATION_CONTEXT_REQUIRED,
                    message=(
                        "observation_context.environment/window_start/window_end are all required"
                    ),
                )

            if snapshot_id is not None and snapshot_id != snapshot.snapshot_id:
                return _SharedRefusal(
                    snapshot_ref=snapshot_ref,
                    context_ref=context_ref,
                    code=LimitationCode.SNAPSHOT_NOT_AVAILABLE,
                    message=(
                        f"requested snapshot {snapshot_id} is not the current stable snapshot"
                    ),
                )

            rows = snapshot.extra
            if rows["service_name"] is None:
                return _SharedRefusal(
                    snapshot_ref=snapshot_ref,
                    context_ref=context_ref,
                    code=LimitationCode.UNKNOWN_ENTITY,
                    message=f"{service_id} does not exist in the current snapshot",
                )

            result = project_service_dependencies(
                rows,
                service_id=service_id,
                service_name=rows["service_name"],
                environment=context_ref.environment,
                window_start=context_ref.window_start,
                window_end=context_ref.window_end,
                coverage_enabled=self._coverage_qualification_enabled,
            )

        if len(result.claims) > _MAX_CLAIMS:
            return _SharedRefusal(
                snapshot_ref=snapshot_ref,
                context_ref=context_ref,
                code=LimitationCode.RESULT_LIMIT_EXCEEDED,
                message=(
                    f"{len(result.claims)} unique dependency claims exceed the "
                    f"{_MAX_CLAIMS}-claim result bound"
                ),
            )

        return _SharedProjection(
            snapshot_ref=snapshot_ref,
            context_ref=context_ref,
            service_name=rows["service_name"],
            projection=ProjectionResult(
                claims=sorted(result.claims, key=_claim_sort_key),
                limitations=sorted(result.limitations, key=_limitation_sort_key),
            ),
        )

    def get_service_dependencies(
        self, request: ServiceDependenciesRequest
    ) -> ArchitectureAnswer[ServiceDependenciesData]:
        shared = self._project_direct_dependencies(
            service_id=request.service_id,
            observation_context=request.observation_context,
            snapshot_id=request.snapshot_id,
        )
        if isinstance(shared, _SharedRefusal):
            return self._refusal(
                snapshot_ref=shared.snapshot_ref,
                context_ref=shared.context_ref,
                code=shared.code,
                message=shared.message,
            )

        snapshot_ref = shared.snapshot_ref
        context_ref = shared.context_ref
        claims = shared.projection.claims
        limitations = shared.projection.limitations

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
                    id=request.service_id, type=EntityType.SERVICE, name=shared.service_name
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

    def get_architecture_drift(
        self, request: ArchitectureDriftRequest
    ) -> ArchitectureAnswer[ArchitectureDriftData]:
        """v0.4.0 I3.1 - I3 spec §14. The drift answer is the already-qualified direct-dependency
        answer with everything but the discrepancy-qualified claims filtered out (I3 spec §7.1) - it
        re-derives nothing, so the claims it returns are the same objects, with the same
        `claim_id`s and the same evidence, that `get_service_dependencies` returns for the same
        service, snapshot and observation context (I3 spec §8)."""
        shared = self._project_direct_dependencies(
            service_id=request.service_id,
            observation_context=request.observation_context,
            snapshot_id=request.snapshot_id,
        )
        if isinstance(shared, _SharedRefusal):
            return self._drift_refusal(
                snapshot_ref=shared.snapshot_ref,
                context_ref=shared.context_ref,
                code=shared.code,
                message=shared.message,
            )

        drift = project_architecture_drift(shared.projection)
        claims = drift.claims
        limitations = drift.limitations

        # I3 spec §18. "No drift claims and no retained limitation" means either the service had no
        # applicable outgoing dependency candidates at all or every one of them qualified CONFIRMED,
        # and §18.2 makes both a successful, non-empty-envelope ANSWERED with an empty claim list -
        # empty drift is an answer, not a refusal. "No drift claims but a limitation survived" can
        # only be §19.2's claim-independent INSUFFICIENT_EVIDENCE (a claim-scoped limitation cannot
        # outlive every claim it scopes to), and §18.4 requires that to be NOT_ANSWERED: candidates
        # existed whose evidence was too thin to build a claim from, and "could not establish a
        # claim" must never be reported as "no drift".
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
            data = ArchitectureDriftData(
                service=EntityRef(
                    id=request.service_id, type=EntityType.SERVICE, name=shared.service_name
                ),
                drift_claim_ids=[claim.claim_id for claim in claims],
            )

        # I3 spec §21: the union covers the returned drift claims only - a CONFIRMED claim's
        # evidence is not part of this answer, because that claim is not part of this answer.
        evidence_refs = sorted(
            {
                ref
                for claim in claims
                for ref in (*claim.evidence_refs, *claim.resolution_evidence_refs)
            }
        )

        return ArchitectureAnswer[ArchitectureDriftData](
            schema_version="0.4",
            producer=self._producer,
            tool=_DRIFT_TOOL_NAME,
            outcome=outcome,
            snapshot=shared.snapshot_ref,
            observation_context=shared.context_ref,
            data=data,
            claims=claims,
            evidence_refs=evidence_refs,
            limitations=limitations,
        )

    def _drift_refusal(
        self,
        *,
        snapshot_ref: SnapshotRef | None,
        context_ref: ObservationContextRef | None,
        code: LimitationCode,
        message: str,
    ) -> ArchitectureAnswer[ArchitectureDriftData]:
        return ArchitectureAnswer[ArchitectureDriftData](
            schema_version="0.4",
            producer=self._producer,
            tool=_DRIFT_TOOL_NAME,
            outcome=Outcome.NOT_ANSWERED,
            snapshot=snapshot_ref,
            observation_context=context_ref,
            data=None,
            claims=[],
            evidence_refs=[],
            limitations=[Limitation(code=code, message=message)],
        )

    def get_evidence(self, request: EvidenceRequest) -> ArchitectureAnswer[EvidenceData]:
        # `EvidenceRequest.evidence_refs` is already deduplicated (spec §11.1) - sorting here is
        # what spec §11.1's "requested ids are sorted lexicographically for processing and output"
        # requires; nothing upstream sorts it yet.
        requested_ids = sorted(request.evidence_refs)

        with open_session(self._driver, database=self._database, read_only=True) as session:
            try:
                snapshot = read_stable_snapshot_from_session(
                    session,
                    coverage_qualification_enabled=self._coverage_qualification_enabled,
                    read_extra=lambda s: read_evidence_rows(s, evidence_ids=requested_ids),
                )
            except SnapshotUnstable:
                return self._evidence_refusal(
                    snapshot_ref=None,
                    code=LimitationCode.SNAPSHOT_NOT_AVAILABLE,
                    message="no consistent current snapshot could be acquired",
                )

            snapshot_ref = SnapshotRef(
                snapshot_id=snapshot.snapshot_id, model_revision=snapshot.model_revision
            )

            # `get_evidence` never defaults to the current snapshot when the requested id is stale
            # (spec §11.1/§13) - unlike `get_service_dependencies`, `snapshot_id` is required here,
            # so there is no "omitted snapshot binds to current" case to handle.
            if request.snapshot_id != snapshot.snapshot_id:
                return self._evidence_refusal(
                    snapshot_ref=snapshot_ref,
                    code=LimitationCode.SNAPSHOT_NOT_AVAILABLE,
                    message=(
                        f"requested snapshot {request.snapshot_id} is not the current stable "
                        "snapshot"
                    ),
                )

            rows = snapshot.extra

        result = project_evidence(rows, requested_ids=requested_ids)
        data = EvidenceData(
            requested_evidence_refs=requested_ids,
            records=result.records,
            missing_evidence_refs=result.missing_evidence_refs,
        )

        if not result.missing_evidence_refs:
            outcome = Outcome.ANSWERED
            limitations = []
        else:
            outcome = Outcome.PARTIAL if result.records else Outcome.NOT_ANSWERED
            limitations = [
                Limitation(
                    code=LimitationCode.INSUFFICIENT_EVIDENCE,
                    message=(
                        f"{len(result.missing_evidence_refs)} of {len(requested_ids)} requested "
                        "evidence refs could not be resolved"
                    ),
                )
            ]

        return ArchitectureAnswer[EvidenceData](
            schema_version="0.4",
            producer=self._producer,
            tool=_EVIDENCE_TOOL_NAME,
            outcome=outcome,
            snapshot=snapshot_ref,
            observation_context=None,
            data=data,
            claims=[],
            evidence_refs=[],
            limitations=limitations,
        )

    def _evidence_refusal(
        self, *, snapshot_ref: SnapshotRef | None, code: LimitationCode, message: str
    ) -> ArchitectureAnswer[EvidenceData]:
        return ArchitectureAnswer[EvidenceData](
            schema_version="0.4",
            producer=self._producer,
            tool=_EVIDENCE_TOOL_NAME,
            outcome=Outcome.NOT_ANSWERED,
            snapshot=snapshot_ref,
            observation_context=None,
            data=None,
            claims=[],
            evidence_refs=[],
            limitations=[Limitation(code=code, message=message)],
        )
