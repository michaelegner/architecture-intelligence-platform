"""v0.7.1 I3.2 - REST parity for `get_destination_consumers` (I3 spec §5).

`POST /api/destination-consumers` is the `mode: "query"` answer and
`POST /api/destination-consumers/evidence` the `mode: "evidence"` resolver. The body is the published
request minus `mode`, which the route supplies. Every route calls the service exactly once and
returns its answer unchanged: a refusal is a 200 envelope, and only a body that cannot form a valid
request is a 422."""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.request_bodies import closed_body, published_request
from app.architecture_intelligence.destination_consumer_contracts import (
    DestinationConsumersAnswer,
    DestinationConsumersEvidenceRequest,
    DestinationConsumersQueryRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service

router = APIRouter(prefix="/api/destination-consumers", tags=["architecture-intelligence"])

_ROUTE_SUPPLIED = frozenset({"mode"})
DestinationConsumersQueryBody = closed_body(
    DestinationConsumersQueryRequest, "DestinationConsumersQueryBody", _ROUTE_SUPPLIED
)
DestinationConsumersEvidenceBody = closed_body(
    DestinationConsumersEvidenceRequest, "DestinationConsumersEvidenceBody", _ROUTE_SUPPLIED
)

# As for the 0.7 API-usage routes: declaring the answer as a FastAPI response model would rename
# same-named components (`Limitation`, `Page`, `EvidenceEntry`, ...) of unchanged routes in the
# OpenAPI document. The answer contract is the published JSON Schema (and the MCP `outputSchema`).
_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "The `DestinationConsumersAnswer` envelope, schema version 0.7.1: "
            "`schemas/architecture_intelligence/v0.7.1/destination-consumers-answer.schema.json`. "
            "Every evaluated or refused answer is a 200; only a malformed request is a 422."
        )
    }
}

__all__ = ["router"]


@router.post("", response_model=None, responses=_RESPONSES)
def get_destination_consumers(
    body: DestinationConsumersQueryBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> DestinationConsumersAnswer:
    """`POST /api/destination-consumers` (`mode: "query"`)."""
    return service.get_destination_consumers(
        published_request(DestinationConsumersQueryRequest, body, mode="query")
    )


@router.post("/evidence", response_model=None, responses=_RESPONSES)
def get_destination_consumer_evidence(
    body: DestinationConsumersEvidenceBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> DestinationConsumersAnswer:
    """`POST /api/destination-consumers/evidence` (`mode: "evidence"`)."""
    return service.get_destination_consumer_evidence(
        published_request(DestinationConsumersEvidenceRequest, body, mode="evidence")
    )
