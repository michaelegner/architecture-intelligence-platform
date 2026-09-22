"""v0.5.0 I3 slice 5a - REST parity for the pre-I3 Architecture Knowledge `ArchitectureIntelligenceService`
already exposes over MCP (spec §14.5, ADR 0016). Every route here constructs the existing request
model and calls the corresponding service method exactly once, returning the complete
`ArchitectureAnswer` unchanged - it never queries Neo4j or re-derives Architecture Knowledge
independently (spec §14.1).

Status-code split (spec §14.5's own text, and this slice's plan Open Questions #2): only a request
whose query params cannot even form a valid request model (malformed `from`/`to`, a `snapshot_id`
that fails its pattern, ...) is an HTTP 422 input error. Every other outcome - including
`NOT_ANSWERED`/`PARTIAL` refusals such as `UNKNOWN_ENTITY` or `SNAPSHOT_NOT_AVAILABLE` - stays inside
the returned `ArchitectureAnswer` as an ordinary 200 body, exactly as MCP already returns it. This
deliberately differs from the evidence surface (`app.api.evidence`, spec §16.3's own frozen
422/503/409/404/200 table) and the slice-5b-only deployments endpoint (spec §15's explicit 404 for an
unknown Service) - those two get their own different, spec-frozen treatment; these two do not.
"""

from __future__ import annotations

from datetime import datetime

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    ArchitectureSchemaVersion,
    DeploymentClaim,
    DeploymentResolution,
    EntityRef,
    Limitation,
    LimitationCode,
    ObservationContextRef,
    ServiceDependenciesData,
    SnapshotRef,
)
from app.architecture_intelligence.observation_context import reject_malformed_observation_context
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service

router = APIRouter(prefix="/api/services", tags=["architecture-intelligence"])


class ServiceDeploymentsView(BaseModel):
    """v0.5.0 I3 spec §15: the REST-only projection `GET /{service_id}/deployments` returns - not a
    public MCP contract type (there is no matching MCP tool for this view), so it lives here rather
    than in `contracts.py`. Every field is extracted from one already-computed
    `get_service_dependencies` answer (spec §15: "MUST NOT invoke deployment reconciliation, Neo4j
    queries, or qualification logic independently") - this model has no validators of its own beyond
    shape, since the answer it projects is already fully validated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: ArchitectureSchemaVersion
    snapshot: SnapshotRef | None
    observation_context: ObservationContextRef | None
    # PR #222 review finding (round 2): null, like `snapshot`/`observation_context`, for a
    # NOT_ANSWERED refusal - the underlying `ServiceDependenciesData.service` field itself doesn't
    # exist when `data is None`, so fabricating an `EntityRef` here (even from the request's own
    # `service_id`) would invent Architecture Knowledge the service answer never confirmed,
    # contradicting spec §15's "preserve the service answer semantics."
    service: EntityRef | None
    deployment_claims: list[DeploymentClaim]
    deployment_resolutions: list[DeploymentResolution]
    evidence_refs: list[str]
    limitations: list[Limitation]


def _observation_context_input(
    environment: str | None, window_start: datetime | None, window_end: datetime | None
) -> ObservationContextInput:
    # All-None (a caller supplied none of the three query params) and "some supplied, some not" are
    # semantically identical downstream (both yield `.is_complete is False`) - no branching needed
    # here, `ArchitectureIntelligenceService` itself decides `OBSERVATION_CONTEXT_REQUIRED`.
    return ObservationContextInput(
        environment=environment, window_start=window_start, window_end=window_end
    )


@router.get("/{service_id}/dependencies")
def get_service_dependencies(
    service_id: str,
    environment: str | None = Query(None),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    snapshot_id: str | None = Query(None),
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> ArchitectureAnswer[ServiceDependenciesData]:
    """`GET /api/services/{service_id}/dependencies` (spec §14.5)."""
    try:
        request = ServiceDependenciesRequest(
            service_id=service_id,
            observation_context=_observation_context_input(environment, from_, to),
            snapshot_id=snapshot_id,
        )
        reject_malformed_observation_context(request.observation_context)
    except pydantic.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return service.get_service_dependencies(request)


@router.get("/{service_id}/drift")
def get_architecture_drift(
    service_id: str,
    environment: str | None = Query(None),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    snapshot_id: str | None = Query(None),
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> ArchitectureAnswer[ArchitectureDriftData]:
    """`GET /api/services/{service_id}/drift` (spec §14.5)."""
    try:
        request = ArchitectureDriftRequest(
            service_id=service_id,
            observation_context=_observation_context_input(environment, from_, to),
            snapshot_id=snapshot_id,
        )
        reject_malformed_observation_context(request.observation_context)
    except pydantic.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return service.get_architecture_drift(request)


@router.get("/{service_id}/deployments")
def get_service_deployments(
    service_id: str,
    environment: str = Query(...),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> ServiceDeploymentsView:
    """`GET /api/services/{service_id}/deployments` (spec §15). Unlike `/dependencies`/`/drift`,
    `environment`/`from`/`to` are required (FastAPI's own required `Query(...)` gives 422 for a
    missing one for free), and an `UNKNOWN_ENTITY` limitation becomes a real 404 - the one spec-frozen
    exception to this file's "everything else stays 200" rule (see the module docstring)."""
    try:
        request = ServiceDependenciesRequest(
            service_id=service_id,
            observation_context=_observation_context_input(environment, from_, to),
            snapshot_id=None,
        )
        reject_malformed_observation_context(request.observation_context)
    except pydantic.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    answer = service.get_service_dependencies(request)

    if any(limitation.code == LimitationCode.UNKNOWN_ENTITY for limitation in answer.limitations):
        raise HTTPException(status_code=404, detail=f"unknown service: {service_id}")

    # PR #222 review finding: `data` is null for every NOT_ANSWERED outcome (ArchitectureAnswer's
    # own envelope invariant), not just UNKNOWN_ENTITY - a known service_id can also refuse with
    # e.g. SNAPSHOT_NOT_AVAILABLE. That must stay a 200 body with `limitations[]`, matching this
    # file's own "everything but UNKNOWN_ENTITY stays 200" rule, never a 500.
    if answer.data is None:
        return ServiceDeploymentsView(
            schema_version=answer.schema_version,
            snapshot=answer.snapshot,
            observation_context=answer.observation_context,
            service=None,
            deployment_claims=[],
            deployment_resolutions=[],
            evidence_refs=[],
            limitations=answer.limitations,
        )

    deployment_claims = [claim for claim in answer.claims if isinstance(claim, DeploymentClaim)]
    deployment_resolutions = answer.data.deployment_resolutions
    evidence_refs = sorted(
        {
            *(ref for claim in deployment_claims for ref in claim.evidence_refs),
            *(
                ref
                for resolution in deployment_resolutions
                for ref in (
                    *resolution.supporting_evidence_refs,
                    *resolution.conflicting_evidence_refs,
                )
            ),
        }
    )

    return ServiceDeploymentsView(
        schema_version=answer.schema_version,
        snapshot=answer.snapshot,
        observation_context=answer.observation_context,
        service=answer.data.service,
        deployment_claims=deployment_claims,
        deployment_resolutions=deployment_resolutions,
        evidence_refs=evidence_refs,
        limitations=answer.limitations,
    )
