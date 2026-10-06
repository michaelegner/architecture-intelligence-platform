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
from typing import Any

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Query

from app.architecture_intelligence.broker_contracts import ServiceDependenciesAnswer
from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    LimitationCode,
)
from app.architecture_intelligence.deployments_view import (
    ServiceDeploymentsView,
    project_service_deployments,
)
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityEvidenceRequest,
    LocalityQueryRequest,
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

__all__ = ["ServiceDeploymentsView", "router"]


def _observation_context_input(
    environment: str | None, window_start: datetime | None, window_end: datetime | None
) -> ObservationContextInput:
    # All-None (a caller supplied none of the three query params) and "some supplied, some not" are
    # semantically identical downstream (both yield `.is_complete is False`) - no branching needed
    # here, `ArchitectureIntelligenceService` itself decides `OBSERVATION_CONTEXT_REQUIRED`.
    return ObservationContextInput(
        environment=environment, window_start=window_start, window_end=window_end
    )


def _validated_request[R: (ServiceDependenciesRequest, ArchitectureDriftRequest)](
    request_type: type[R],
    *,
    service_id: str,
    environment: str | None,
    window_start: datetime | None,
    window_end: datetime | None,
    snapshot_id: str | None,
) -> R:
    """Builds the request model from the route's query params. Only a request that cannot even form
    a valid model (malformed window or `snapshot_id`, ...) is an HTTP 422 - every other outcome stays
    inside the returned answer (see the module docstring)."""
    try:
        request = request_type(
            service_id=service_id,
            observation_context=_observation_context_input(environment, window_start, window_end),
            snapshot_id=snapshot_id,
        )
        reject_malformed_observation_context(request.observation_context)
    except pydantic.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return request


@router.get("/{service_id}/dependencies")
def get_service_dependencies(
    service_id: str,
    environment: str | None = Query(None),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    snapshot_id: str | None = Query(None),
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> ServiceDependenciesAnswer:
    """`GET /api/services/{service_id}/dependencies` (spec §14.5). Data-dependent version (v0.6.1
    spec §5.2): the released v0.5 answer, or the Broker-aware v0.6 answer."""
    request = _validated_request(
        ServiceDependenciesRequest,
        service_id=service_id,
        environment=environment,
        window_start=from_,
        window_end=to,
        snapshot_id=snapshot_id,
    )
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
    request = _validated_request(
        ArchitectureDriftRequest,
        service_id=service_id,
        environment=environment,
        window_start=from_,
        window_end=to,
        snapshot_id=snapshot_id,
    )
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
    request = _validated_request(
        ServiceDependenciesRequest,
        service_id=service_id,
        environment=environment,
        window_start=from_,
        window_end=to,
        snapshot_id=None,
    )
    answer = service.get_service_dependencies(request)
    if any(limitation.code == LimitationCode.UNKNOWN_ENTITY for limitation in answer.limitations):
        raise HTTPException(status_code=404, detail=f"unknown service: {service_id}")
    return project_service_deployments(answer)


# --- v0.6.0 I3.3b: the locality answer (I3 decision record D1, D9, D16.2) -----------------------
#
# Both routes are POST reads with zero graph writes. The Service comes from the path, and the body
# carries every other field of the published request (D16.2: the MCP `request` argument, minus
# `subject_service_id` and `mode`, which the path and the route supply). The bodies are derived
# from the request models' own fields rather than restated, and they are closed. Only a body that
# cannot form a valid request is a 422; every evaluated or refused answer is a 200 envelope (D9).

_PATH_SUPPLIED = frozenset({"subject_service_id", "mode"})


def _locality_body(request_type: type[pydantic.BaseModel], name: str) -> type[pydantic.BaseModel]:
    fields: dict[str, Any] = {
        field: (info.annotation, info)
        for field, info in request_type.model_fields.items()
        if field not in _PATH_SUPPLIED
    }
    return pydantic.create_model(
        name, __config__=pydantic.ConfigDict(extra="forbid", frozen=True), **fields
    )


LocalityQueryBody = _locality_body(LocalityQueryRequest, "LocalityQueryBody")
LocalityEvidenceBody = _locality_body(LocalityEvidenceRequest, "LocalityEvidenceBody")


def _locality_request[R: (LocalityQueryRequest, LocalityEvidenceRequest)](
    request_type: type[R], *, service_id: str, body: pydantic.BaseModel
) -> R:
    """The full published request: the body's own fields plus the path's Service and the route's
    mode. The request model's validators (sorted lists, cursor form, `compare` within
    `caller_localities`, ...) run here, so a body that fails them is a 422 like a malformed one."""
    mode = "query" if request_type is LocalityQueryRequest else "evidence"
    try:
        return request_type.model_validate(
            {**body.model_dump(exclude_unset=True), "mode": mode, "subject_service_id": service_id}
        )
    except pydantic.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{service_id}/dependencies/by-locality")
def get_service_dependencies_by_locality(
    service_id: str,
    body: LocalityQueryBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> LocalityAnswer:
    """`POST /api/services/{service_id}/dependencies/by-locality` (D1, `mode: "query"`)."""
    request = _locality_request(LocalityQueryRequest, service_id=service_id, body=body)
    return service.get_service_dependencies_by_locality(request)


@router.post("/{service_id}/dependencies/by-locality/evidence")
def resolve_scoped_locality_evidence(
    service_id: str,
    body: LocalityEvidenceBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> LocalityAnswer:
    """`POST /api/services/{service_id}/dependencies/by-locality/evidence` (D1, D11,
    `mode: "evidence"`)."""
    request = _locality_request(LocalityEvidenceRequest, service_id=service_id, body=body)
    return service.resolve_scoped_locality_evidence(request)
