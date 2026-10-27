"""v0.8 I2c - REST parity for the experimental `get_binding_picture` (I2 spec §7). Included only with
`experimental.binding-picture` (D11).

`POST /api/binding-picture` is the `mode: "query"` answer and `POST /api/binding-picture/evidence`
the `mode: "evidence"` resolver. The body is the published request minus `mode`, which the route
supplies. Every route calls the service exactly once and returns its answer unchanged: a refusal is
a 200 envelope, and only a body that cannot form a valid request is a 422."""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.request_bodies import closed_body, published_request
from app.architecture_intelligence.binding_picture_contracts import (
    BindingPictureAnswer,
    BindingPictureEvidenceRequest,
    BindingPictureQueryRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service

router = APIRouter(prefix="/api/binding-picture", tags=["architecture-intelligence"])

_ROUTE_SUPPLIED = frozenset({"mode"})
BindingPictureQueryBody = closed_body(
    BindingPictureQueryRequest, "BindingPictureQueryBody", _ROUTE_SUPPLIED
)
BindingPictureEvidenceBody = closed_body(
    BindingPictureEvidenceRequest, "BindingPictureEvidenceBody", _ROUTE_SUPPLIED
)

# As for the 0.7.1 destination-consumer routes, the answer contract is the published JSON Schema
# (and the MCP `outputSchema`), not a FastAPI response model.
_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "The experimental `BindingPictureAnswer` envelope, schema version 0.8.0: "
            "`schemas/architecture_intelligence/v0.8/binding-picture-answer.schema.json`. "
            "Every evaluated or refused answer is a 200; only a malformed request is a 422."
        )
    }
}

__all__ = ["router"]


@router.post("", response_model=None, responses=_RESPONSES)
def get_binding_picture(
    body: BindingPictureQueryBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> BindingPictureAnswer:
    """`POST /api/binding-picture` (`mode: "query"`)."""
    return service.get_binding_picture(
        published_request(BindingPictureQueryRequest, body, mode="query")
    )


@router.post("/evidence", response_model=None, responses=_RESPONSES)
def get_binding_picture_evidence(
    body: BindingPictureEvidenceBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> BindingPictureAnswer:
    """`POST /api/binding-picture/evidence` (`mode: "evidence"`)."""
    return service.get_binding_picture_evidence(
        published_request(BindingPictureEvidenceRequest, body, mode="evidence")
    )
