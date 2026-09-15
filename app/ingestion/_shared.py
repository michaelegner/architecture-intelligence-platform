"""Small helpers shared by the concrete SourceAdapter implementations in this package. Not part of
the public seam (app.sources.registry) - just avoids duplicating the same few lines across
openapi_adapter.py/asyncapi_adapter.py/manifest_adapter.py.
"""

from app.canonical.model import ArchitectureModel
from app.sources.model import IngestionResult
from app.sources.registry import AdapterOutcome
from app.sources.service_identity import ServiceIdentityOutcome, ServiceIdentityResolution

# I1 spec §8.1: "The canonical projection excludes only description, summary, example, examples,
# and externalDocs." Applied at the top level of each named-component schema/message only (today's
# parsing fidelity - no recursive/inline/composition handling; that's 3b).
EXCLUDED_SCHEMA_FIELDS = frozenset(
    {"description", "summary", "example", "examples", "externalDocs"}
)

_IDENTITY_OUTCOME_TO_RESULT = {
    ServiceIdentityOutcome.REJECTED_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    ServiceIdentityOutcome.REJECTED_CONFLICT: IngestionResult.REJECTED_CONFLICT,
    ServiceIdentityOutcome.REJECTED_INVALID: IngestionResult.REJECTED_INVALID,
}


def strip_excluded_schema_fields(definition: dict) -> dict:
    return {key: value for key, value in definition.items() if key not in EXCLUDED_SCHEMA_FIELDS}


def rejected_outcome_for_identity(resolution: ServiceIdentityResolution) -> AdapterOutcome:
    return AdapterOutcome(
        result=_IDENTITY_OUTCOME_TO_RESULT[resolution.outcome],
        model=ArchitectureModel(),
        diagnostics=tuple(resolution.diagnostics),
        semantic_input_digest=None,
    )
