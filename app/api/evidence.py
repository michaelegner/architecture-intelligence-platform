"""v0.5.0 I3 slice 5a reworks this module from raw, unfenced Cypher (pre-I3) to a thin wrapper over
`ArchitectureIntelligenceService` (spec §14.5/§16.3, ADR 0016).

`POST /resolve` is the real REST parity operation for `get_evidence` (spec §14.5): it accepts the
existing `EvidenceRequest` shape and returns the complete `ArchitectureAnswer[EvidenceData]`
unchanged, preserving the 1-20-ref bound, missing-ref reporting, and same-snapshot semantics MCP
already has.

`GET ""`/`GET /{evidence_id}` are the pre-existing REST "convenience" forms (spec §16.3) - they
predate I3, and I3 makes them snapshot-aware rather than replacing them. `snapshot_id` becomes a
REQUIRED query parameter on both, and the response is bound to one stable snapshot rather than an
unfenced live read. The frozen status-code table (spec §16.3):

    missing/malformed snapshot_id                          -> 422
    current stable snapshot cannot be acquired              -> 503 SNAPSHOT_NOT_AVAILABLE
    supplied snapshot_id != current stable snapshot id      -> 409 SNAPSHOT_NOT_AVAILABLE
    found and publicly reachable at that snapshot           -> 200
    not reachable / doesn't exist at that snapshot          -> 404 (lookup only; list never 404s)

Public evidence visibility for these two convenience forms is unchanged from pre-I3 (spec §16.2's
`DEPLOYED_AS`-reachability widening is structurally inapplicable until I3 slice 5b creates a public
`DeploymentClaim`/`DeploymentResolution` to reach evidence from) - see
`app.architecture_intelligence.repository.read_public_evidence_list_rows`/`read_public_evidence_row`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.architecture_intelligence.contracts import ArchitectureAnswer, EvidenceData
from app.architecture_intelligence.repository import SnapshotUnstable
from app.architecture_intelligence.request import EvidenceRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

_SNAPSHOT_UNSTABLE_DETAIL = {
    "code": "SNAPSHOT_NOT_AVAILABLE",
    "message": "no consistent current snapshot could be acquired",
}


def _stale_snapshot_detail(*, requested: str, current: str) -> dict:
    return {
        "code": "SNAPSHOT_NOT_AVAILABLE",
        "message": f"requested snapshot {requested} is not the current stable snapshot {current}",
    }


@router.post("/resolve")
def resolve_evidence(
    request: EvidenceRequest,
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> ArchitectureAnswer[EvidenceData]:
    """`POST /api/evidence/resolve` (spec §14.5): calls
    `ArchitectureIntelligenceService.get_evidence` exactly once and returns its answer unchanged."""
    return service.get_evidence(request)


@router.get("")
def list_evidence(
    snapshot_id: str = Query(...),
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> list[dict]:
    try:
        current_snapshot_id, rows = service.list_public_evidence()
    except SnapshotUnstable as exc:
        raise HTTPException(status_code=503, detail=_SNAPSHOT_UNSTABLE_DETAIL) from exc
    if snapshot_id != current_snapshot_id:
        raise HTTPException(
            status_code=409,
            detail=_stale_snapshot_detail(requested=snapshot_id, current=current_snapshot_id),
        )
    return rows


@router.get("/{evidence_id}")
def get_evidence(
    evidence_id: str,
    snapshot_id: str = Query(...),
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> dict:
    try:
        current_snapshot_id, row = service.get_public_evidence(evidence_id)
    except SnapshotUnstable as exc:
        raise HTTPException(status_code=503, detail=_SNAPSHOT_UNSTABLE_DETAIL) from exc
    if snapshot_id != current_snapshot_id:
        raise HTTPException(
            status_code=409,
            detail=_stale_snapshot_detail(requested=snapshot_id, current=current_snapshot_id),
        )
    if row is None:
        raise HTTPException(status_code=404, detail=f"evidence not found: {evidence_id}")
    return row
