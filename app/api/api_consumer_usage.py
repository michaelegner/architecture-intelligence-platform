"""v0.7.0 I3.3 - REST parity for `get_api_consumer_usage` (I3 decision record D1).

`POST /api/api-consumer-usage` is the `mode: "query"` answer and `POST /api/api-consumer-usage/evidence`
the `mode: "evidence"` resolver. The path is top-level because the operation has three peer target
kinds (I3 spec §10). The body is the published request minus `mode`, which the route supplies. Every
route calls the service exactly once and returns its answer unchanged: a refusal is a 200 envelope,
and only a body that cannot form a valid request is a 422."""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.request_bodies import closed_body, published_request
from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service

router = APIRouter(prefix="/api/api-consumer-usage", tags=["architecture-intelligence"])

_ROUTE_SUPPLIED = frozenset({"mode"})
ApiConsumerUsageQueryBody = closed_body(
    ApiConsumerUsageQueryRequest, "ApiConsumerUsageQueryBody", _ROUTE_SUPPLIED
)
ApiConsumerUsageEvidenceBody = closed_body(
    ApiConsumerUsageEvidenceRequest, "ApiConsumerUsageEvidenceBody", _ROUTE_SUPPLIED
)

# The 0.7 answer models share class names with the 0.5/0.6 ones (`Coverage`, `RuleRef`,
# `EvidenceEntry`, ...). Declaring one as a FastAPI response model would make the generator rename
# those existing components in the OpenAPI document, silently changing the documented surface of
# routes that did not change. The answer contract is the published JSON Schema (and the MCP
# `outputSchema`); the route therefore documents its 200 by pointing at it.
_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "The `ApiConsumerUsageAnswer` envelope, schema version 0.7: "
            "`schemas/architecture_intelligence/v0.7/api-consumer-usage-answer.schema.json`. "
            "Every evaluated or refused answer is a 200; only a malformed request is a 422."
        )
    }
}

__all__ = ["router"]


@router.post("", response_model=None, responses=_RESPONSES)
def get_api_consumer_usage(
    body: ApiConsumerUsageQueryBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> ApiConsumerUsageAnswer:
    """`POST /api/api-consumer-usage` (D1, `mode: "query"`)."""
    return service.get_api_consumer_usage(
        published_request(ApiConsumerUsageQueryRequest, body, mode="query")
    )


@router.post("/evidence", response_model=None, responses=_RESPONSES)
def get_api_consumer_usage_evidence(
    body: ApiConsumerUsageEvidenceBody,  # pyright: ignore[reportInvalidTypeForm]
    service: ArchitectureIntelligenceService = Depends(get_architecture_intelligence_service),
) -> ApiConsumerUsageAnswer:
    """`POST /api/api-consumer-usage/evidence` (D1, D9, `mode: "evidence"`)."""
    return service.get_api_consumer_usage_evidence(
        published_request(ApiConsumerUsageEvidenceRequest, body, mode="evidence")
    )
