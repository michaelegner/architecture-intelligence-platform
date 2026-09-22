"""v0.4.0 I1.3 - `ArchitectureIntelligenceService`, the sole semantic entry point I1 introduces
(spec §7). Implements `get_service_dependencies` per the reference processing flow (spec §22).

v0.4.0 I3.1 adds `get_architecture_drift` (I3 spec §14). Both dependency-answering tools share one
private projection step (`_project_direct_dependencies`, I3 spec §15) so the drift answer is a
bounded *view* of the already-qualified I1 dependency answer rather than a second derivation of it.

v0.5.0 I3 slice 5b wires the cross-path deployment reducer (`deployment_reconciliation.py`) into
`get_service_dependencies` only - never into `_project_direct_dependencies`/`get_architecture_drift`,
which must stay deployment-agnostic (spec §14.2).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import neo4j

from app.architecture_intelligence.contracts import (
    ARCHITECTURE_SCHEMA_VERSION,
    TOOL_NAMES,
    ArchitectureAnswer,
    ArchitectureDriftData,
    DependencyClaim,
    DeploymentClaim,
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
from app.architecture_intelligence.contracts import _claim_sort_key as _polymorphic_claim_sort_key
from app.architecture_intelligence.dependency_projection import (
    ProjectionResult,
    project_service_dependencies,
)
from app.architecture_intelligence.deployment_reconciliation import (
    EVIDENCE_VISIBILITY_CONTEXT_ID,
    WholeGraphReconciliation,
    check_result_bounds,
    deployed_as_supported_facts,
    filter_for_service,
    run_whole_graph_reconciliation,
)
from app.architecture_intelligence.drift_projection import project_architecture_drift
from app.architecture_intelligence.evidence_projection import (
    EvidenceProjectionResult,
    project_evidence,
)
from app.architecture_intelligence.observation_context import build_observation_context_ref
from app.architecture_intelligence.repository import (
    SnapshotUnstable,
    canonical_snapshot_state,
    read_evidence_rows,
    read_public_evidence_list_rows,
    read_public_evidence_row,
    read_service_dependency_rows,
    read_stable_snapshot,
    snapshot_fingerprint,
)
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.graph.repository import open_session
from app.graph.revision_fence import read_revision
from app.sources.service_workload_mapping import ServiceWorkloadMappingDocument

_DRIFT_TOOL_NAME, _EVIDENCE_TOOL_NAME, _TOOL_NAME = TOOL_NAMES
_MAX_CLAIMS = 500


def _claim_sort_key(claim: DependencyClaim) -> tuple[str, str, str, str]:
    return (claim.object.id, claim.delivery.kind.value, claim.delivery.via.id, claim.claim_id)


def _limitation_sort_key(limitation: Limitation) -> tuple[str, str]:
    return (limitation.code.value, limitation.message)


def _supported_fact_sort_key(fact) -> tuple[str, str, str]:
    return (fact.relation_type.value, fact.source_id, fact.target_id)


def _synthetic_evidence_to_public_dict(record) -> dict:
    """v0.5.0 I3 slice 5b - converts a Path B/C synthetic `EvidenceRecord` into the same ad hoc
    dict shape `read_public_evidence_list_rows`/`read_public_evidence_row` already return for a
    real `:Evidence` node (`app.api.evidence`'s REST convenience shape, unchanged since slice 5a -
    `source_file` is that shape's own key name for what `EvidenceRecord` itself calls
    `source_locator`)."""
    return {
        "id": record.id,
        "source_type": record.source_type.value,
        "source_file": record.source_locator,
        "source_revision": record.source_revision,
        "evidence_type": record.evidence_type.value,
    }


def _apply_deployed_as_evidence(
    result: EvidenceProjectionResult, *, reconciliation: WholeGraphReconciliation
) -> EvidenceProjectionResult:
    """v0.5.0 I3 slice 5b (spec §16.1/§16.2): augments `project_evidence`'s already-built records
    with a `DEPLOYED_AS` `SupportedFact` wherever a returned `DeploymentClaim` names that evidence
    id (real `:Evidence`-backed Path A records included - `DEPLOYED_AS` is never written to the
    graph, so `evidence_projection`'s own relation-matching `supports` never finds it on its own),
    and resolves any still-missing id against Path B/C's synthetic evidence records - the only
    ids these can ever be, since a real `:Evidence` node's own absence was already final."""
    supports_by_id = deployed_as_supported_facts(reconciliation.reduced.claims)

    records = [
        record.model_copy(
            update={
                "supports": sorted(
                    {*record.supports, *supports_by_id[record.id]}, key=_supported_fact_sort_key
                )
            }
        )
        if record.id in supports_by_id
        else record
        for record in result.records
    ]

    still_missing: list[str] = []
    extra_records = []
    for evidence_id in result.missing_evidence_refs:
        # Reachability (spec §16.2), not mere presence, gates exposure - `synthetic_evidence_
        # records` holds every Path B/C record regardless of whether any current claim/resolution
        # actually reaches it (an unmatched mapping entry's own evidence must stay as hidden as an
        # unreferenced Kubernetes `:Evidence` node already is).
        synthetic = reconciliation.synthetic_evidence_records.get(evidence_id)
        if synthetic is None or evidence_id not in reconciliation.reachable_evidence_ids:
            still_missing.append(evidence_id)
            continue
        extra_records.append(
            synthetic.model_copy(update={"supports": supports_by_id.get(evidence_id, [])})
        )

    return EvidenceProjectionResult(
        records=sorted([*records, *extra_records], key=lambda record: record.id),
        missing_evidence_refs=sorted(still_missing),
    )


@dataclass(frozen=True)
class _SharedProjection:
    """v0.4.0 I3.1 - a successful `_project_direct_dependencies` result (I3 spec §15). `projection`
    is the I1 dependency projection with both lists already in their canonical I1 order, so a
    consumer that filters it (the drift tool) preserves that order for free (I3 spec §20).

    `deployment` (v0.5.0 I3 slice 5b) is populated only when the caller passes
    `include_deployment=True` (`get_service_dependencies` only - never `get_architecture_drift`,
    which must stay deployment-agnostic per spec §14.2)."""

    snapshot_ref: SnapshotRef
    context_ref: ObservationContextRef
    service_name: str
    projection: ProjectionResult
    deployment: WholeGraphReconciliation | None = None


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
        service_workload_mapping_document: ServiceWorkloadMappingDocument | None = None,
        configured_kubernetes_sources: Sequence[tuple[str, str]] = (),
        service_aliases: dict[str, str] | None = None,
    ) -> None:
        self._driver = driver
        self._database = database
        self._producer = producer
        self._coverage_qualification_enabled = coverage_qualification_enabled
        # v0.5.0 I3 slice 5b: the configured Path B artifact, currently-configured Kubernetes
        # sources, and OTel service-name aliases - all default to "nothing configured" so every
        # pre-existing direct-construction caller/test keeps working unchanged (mirrors
        # `coverage_qualification_enabled`'s own default-value precedent).
        self._service_workload_mapping_document = service_workload_mapping_document
        self._configured_kubernetes_sources = tuple(configured_kubernetes_sources)
        self._service_aliases = dict(service_aliases) if service_aliases else {}

    def _project_direct_dependencies(
        self,
        *,
        service_id: str,
        observation_context: ObservationContextInput | None,
        snapshot_id: str | None,
        include_deployment: bool = False,
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
        never be evaluated after the filter.

        v0.5.0 I3 slice 5b: `include_deployment=True` (only `get_service_dependencies` passes it)
        also runs the whole-graph deployment reconciliation inside this same stable-read attempt.
        This uses `read_stable_snapshot` directly (not the `read_stable_snapshot_from_session`
        convenience wrapper) because deployment `resolution_id`/`claim_id` values are themselves
        hashed from `snapshot_id` (spec §13.2) - a real circularity, since `snapshot_id` is only
        known once `canonical_snapshot_state()` has already been fingerprinted. `fingerprint_holder`
        is a plain closure-shared cell `read_state` populates and `read_extra` then reads - safe
        because `read_stable_snapshot`'s own algorithm always calls `read_state()` strictly before
        `read_extra()` within one attempt, so no synchronization beyond that existing call order is
        needed, and a discarded (revision-mismatched) attempt discards this cell's value too."""
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
            fingerprint_holder: dict[str, str] = {}

            def read_state() -> dict:
                state = canonical_snapshot_state(
                    session,
                    coverage_qualification_enabled=self._coverage_qualification_enabled,
                    service_workload_mapping_document=self._service_workload_mapping_document,
                )
                fingerprint_holder["snapshot_id"] = snapshot_fingerprint(state)[0]
                return state

            def read_extra() -> dict:
                dependency_rows = (
                    read_service_dependency_rows(
                        session,
                        service_id=service_id,
                        environment=context_ref.environment,
                        window_start=context_ref.window_start,
                        window_end=context_ref.window_end,
                    )
                    if context_complete
                    else None
                )
                deployment = (
                    run_whole_graph_reconciliation(
                        session,
                        snapshot_id=fingerprint_holder["snapshot_id"],
                        context_id=context_ref.context_id,
                        observation_context=context_ref,
                        document=self._service_workload_mapping_document,
                        configured_kubernetes_sources=self._configured_kubernetes_sources,
                        service_aliases=self._service_aliases,
                    )
                    if include_deployment and context_complete
                    else None
                )
                return {"dependency_rows": dependency_rows, "deployment": deployment}

            try:
                snapshot = read_stable_snapshot(
                    read_revision_fn=lambda: read_revision(session),
                    read_state=read_state,
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

            rows = snapshot.extra["dependency_rows"]
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
            deployment = snapshot.extra["deployment"]

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
            deployment=deployment,
        )

    def get_service_dependencies(
        self, request: ServiceDependenciesRequest
    ) -> ArchitectureAnswer[ServiceDependenciesData]:
        shared = self._project_direct_dependencies(
            service_id=request.service_id,
            observation_context=request.observation_context,
            snapshot_id=request.snapshot_id,
            include_deployment=True,
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
        dependency_claims = shared.projection.claims
        limitations = list(shared.projection.limitations)

        # v0.5.0 I3 slice 5b: deployment is a separate sibling projection (spec §14.2), filtered to
        # this request's own Service (spec §13.4) and bounded (spec §20).
        assert shared.deployment is not None  # include_deployment=True above guarantees this
        deployment_claims, deployment_resolutions = filter_for_service(
            shared.deployment.reduced, service_id=request.service_id
        )
        bound_exceeded = check_result_bounds(deployment_claims, deployment_resolutions)
        if bound_exceeded is not None:
            deployment_claims = []
            deployment_resolutions = []
            limitations.append(
                Limitation(
                    code=bound_exceeded,
                    message=(
                        f"deployment claims/resolutions for {request.service_id} exceed the "
                        "result bounds"
                    ),
                )
            )
        deployment_resolutions = sorted(deployment_resolutions, key=lambda r: r.resolution_id)

        all_claims = sorted(
            [*dependency_claims, *deployment_claims], key=_polymorphic_claim_sort_key
        )
        limitations = sorted(limitations, key=_limitation_sort_key)
        # Real content exists either as a claim (dependency or deployment) or as a non-resolved
        # DeploymentResolution (spec §13.3: "inspectable without fabricating a claim") - a
        # dependency-side-only refusal must not silently drop otherwise-real deployment resolution
        # content, so this generalizes the original dependency-only "claims empty" check rather than
        # reusing it unchanged.
        has_any_content = bool(all_claims) or bool(deployment_resolutions)

        if not has_any_content and not limitations:
            outcome = Outcome.ANSWERED
        elif not has_any_content:
            outcome = Outcome.NOT_ANSWERED
        elif limitations:
            outcome = Outcome.PARTIAL
        else:
            outcome = Outcome.ANSWERED

        if outcome == Outcome.NOT_ANSWERED:
            data = None
            all_claims = []
            deployment_resolutions = []
        else:
            data = ServiceDependenciesData(
                service=EntityRef(
                    id=request.service_id, type=EntityType.SERVICE, name=shared.service_name
                ),
                dependency_claim_ids=[
                    claim.claim_id for claim in all_claims if isinstance(claim, DependencyClaim)
                ],
                deployment_claim_ids=[
                    claim.claim_id for claim in all_claims if isinstance(claim, DeploymentClaim)
                ],
                deployment_resolutions=deployment_resolutions,
            )

        evidence_refs = sorted(
            {
                ref
                for claim in all_claims
                for ref in (
                    (*claim.evidence_refs, *claim.resolution_evidence_refs)
                    if isinstance(claim, DependencyClaim)
                    else claim.evidence_refs
                )
            }
        )

        return ArchitectureAnswer[ServiceDependenciesData](
            schema_version=ARCHITECTURE_SCHEMA_VERSION,
            producer=self._producer,
            tool=_TOOL_NAME,
            outcome=outcome,
            snapshot=snapshot_ref,
            observation_context=context_ref,
            data=data,
            claims=all_claims,
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
            schema_version=ARCHITECTURE_SCHEMA_VERSION,
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
            schema_version=ARCHITECTURE_SCHEMA_VERSION,
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
            schema_version=ARCHITECTURE_SCHEMA_VERSION,
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

    def _read_stable_snapshot_with_deployment_evidence[T](
        self,
        session: neo4j.Session,
        *,
        build_extra: Callable[[neo4j.Session, WholeGraphReconciliation], T],
    ):
        """v0.5.0 I3 slice 5b - shared by `get_evidence`/`list_public_evidence`/
        `get_public_evidence`: runs one stable-read attempt that also computes the whole-graph
        deployment reconciliation these three need for §16.1/§16.2 evidence visibility, using
        `EVIDENCE_VISIBILITY_CONTEXT_ID` (no real observation context - see
        `run_whole_graph_reconciliation`'s own docstring for why Path C is skipped here).
        `build_extra` receives the reconciliation result so it can build a *widened* read (e.g. the
        reachable-Kubernetes-evidence-id-aware query) - reconciliation necessarily runs before
        `build_extra`, not after, since the widened read depends on its output. Uses
        `read_stable_snapshot` directly (not the convenience wrapper) for the same
        fingerprint-before-reconciliation reason `_project_direct_dependencies` does - see that
        method's own docstring."""
        fingerprint_holder: dict[str, str] = {}

        def read_state() -> dict:
            state = canonical_snapshot_state(
                session,
                coverage_qualification_enabled=self._coverage_qualification_enabled,
                service_workload_mapping_document=self._service_workload_mapping_document,
            )
            fingerprint_holder["snapshot_id"] = snapshot_fingerprint(state)[0]
            return state

        def read_extra():
            reconciliation = run_whole_graph_reconciliation(
                session,
                snapshot_id=fingerprint_holder["snapshot_id"],
                context_id=EVIDENCE_VISIBILITY_CONTEXT_ID,
                observation_context=None,
                document=self._service_workload_mapping_document,
                configured_kubernetes_sources=self._configured_kubernetes_sources,
                service_aliases=self._service_aliases,
            )
            return build_extra(session, reconciliation), reconciliation

        return read_stable_snapshot(
            read_revision_fn=lambda: read_revision(session),
            read_state=read_state,
            read_extra=read_extra,
        )

    def get_evidence(self, request: EvidenceRequest) -> ArchitectureAnswer[EvidenceData]:
        # `EvidenceRequest.evidence_refs` is already deduplicated (spec §11.1) - sorting here is
        # what spec §11.1's "requested ids are sorted lexicographically for processing and output"
        # requires; nothing upstream sorts it yet.
        requested_ids = sorted(request.evidence_refs)

        with open_session(self._driver, database=self._database, read_only=True) as session:
            try:
                snapshot = self._read_stable_snapshot_with_deployment_evidence(
                    session,
                    build_extra=lambda s, reconciliation: read_evidence_rows(
                        s,
                        evidence_ids=requested_ids,
                        reachable_kubernetes_evidence_ids=reconciliation.reachable_evidence_ids,
                    ),
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

            rows, reconciliation = snapshot.extra

        result = project_evidence(rows, requested_ids=requested_ids)
        result = _apply_deployed_as_evidence(result, reconciliation=reconciliation)
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
            schema_version=ARCHITECTURE_SCHEMA_VERSION,
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
            schema_version=ARCHITECTURE_SCHEMA_VERSION,
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

    def list_public_evidence(self) -> tuple[str, list[dict]]:
        """v0.5.0 I3 slice 5a - REST-only convenience capability backing `GET /api/evidence` (spec
        §16.3). `EvidenceRequest`/`get_evidence` above only resolve a caller-supplied bounded 1-20-
        ref id list; this method has no bounded id set to key off, so it is deliberately not
        `ArchitectureAnswer`-shaped and lets `SnapshotUnstable` propagate uncaught - the REST route
        maps it to its own 503 `SNAPSHOT_NOT_AVAILABLE` response (spec §16.3's frozen status table),
        which does not fit a semantic `ArchitectureAnswer` refusal envelope the way `get_evidence`'s
        bounded-lookup refusals do.

        v0.5.0 I3 slice 5b: also includes every reachable Path B/C synthetic evidence record (spec
        §16.2) - real Kubernetes `:Evidence` reachability is handled by
        `read_public_evidence_list_rows`'s own widened predicate; Path B/C has no backing graph
        node at all, so it's appended here from the reconciliation's own in-memory map."""
        with open_session(self._driver, database=self._database, read_only=True) as session:
            snapshot = self._read_stable_snapshot_with_deployment_evidence(
                session,
                build_extra=lambda s, r: read_public_evidence_list_rows(
                    s, reachable_kubernetes_evidence_ids=r.reachable_evidence_ids
                ),
            )
            snapshot_id = snapshot.snapshot_id
            rows, reconciliation = snapshot.extra
            synthetic_rows = [
                _synthetic_evidence_to_public_dict(record)
                for evidence_id, record in reconciliation.synthetic_evidence_records.items()
                if evidence_id in reconciliation.reachable_evidence_ids
            ]
            return snapshot_id, sorted([*rows, *synthetic_rows], key=lambda row: row["id"])

    def get_public_evidence(self, evidence_id: str) -> tuple[str, dict | None]:
        """v0.5.0 I3 slice 5a - the `GET /api/evidence/{evidence_id}` counterpart to
        `list_public_evidence` above. Returns `None` for the row when `evidence_id` doesn't exist or
        isn't publicly visible - the REST route decides the 404, this method only reports raw
        presence/absence bound to one stable snapshot. v0.5.0 I3 slice 5b: falls back to a reachable
        Path B/C synthetic record when no real `:Evidence` node matched - see `list_public_evidence`
        above."""
        with open_session(self._driver, database=self._database, read_only=True) as session:
            snapshot = self._read_stable_snapshot_with_deployment_evidence(
                session,
                build_extra=lambda s, r: read_public_evidence_row(
                    s,
                    evidence_id=evidence_id,
                    reachable_kubernetes_evidence_ids=r.reachable_evidence_ids,
                ),
            )
            snapshot_id = snapshot.snapshot_id
            row, reconciliation = snapshot.extra
            if row is not None:
                return snapshot_id, row
            synthetic = reconciliation.synthetic_evidence_records.get(evidence_id)
            if synthetic is not None and evidence_id in reconciliation.reachable_evidence_ids:
                return snapshot_id, _synthetic_evidence_to_public_dict(synthetic)
            return snapshot_id, None
