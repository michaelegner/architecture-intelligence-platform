import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.sources.model import DiagnosticCode, IngestionDiagnostic
from app.sources.pointers import pointer_prefix_matches

# I1 spec §4.1:
#   service:<service-segment>
#   service:<namespace-segment>:<service-segment>
#   segment = [a-z0-9][a-z0-9._-]*
# No whitespace, empty segment, additional colon, case folding, or implicit slug conversion.
_SERVICE_ID_RE = re.compile(r"^service:[a-z0-9][a-z0-9._-]*(?::[a-z0-9][a-z0-9._-]*)?$")


def is_valid_service_id(value: str) -> bool:
    """I1 spec §4.1's canonical Service-ID grammar."""
    return bool(_SERVICE_ID_RE.fullmatch(value))


class ServiceIdentityPath(StrEnum):
    EXTENSION = "extension"
    CONFIGURED_MAPPING = "configured_mapping"
    MANIFEST_BINDING = "manifest_binding"


@dataclass(frozen=True)
class PointerBinding:
    source_instance_id: str
    pointer_prefix: str
    service_id: str
    path: ServiceIdentityPath


class ServiceIdentityOutcome(StrEnum):
    RESOLVED = "RESOLVED"
    REJECTED_UNSUPPORTED = "REJECTED_UNSUPPORTED"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"
    REJECTED_INVALID = "REJECTED_INVALID"


@dataclass(frozen=True)
class ServiceIdentityResolution:
    outcome: ServiceIdentityOutcome
    service_id: str | None
    diagnostics: tuple[IngestionDiagnostic, ...]


def resolve_service_identity(
    *,
    source_instance_id: str,
    construct_pointer: str,
    extension_value: str | None,
    configured_mappings: Sequence[PointerBinding],
    manifest_bindings: Sequence[PointerBinding],
) -> ServiceIdentityResolution:
    """I1 spec §4.1, per-construct resolution over the three accepted evidence paths:

        all applicable paths agree
          -> RESOLVED; union identity evidence

        missing identity for any emitted construct
          -> REJECTED_UNSUPPORTED + SERVICE_IDENTITY_UNRESOLVED

        multiple applicable identities disagree
          -> REJECTED_CONFLICT + SERVICE_IDENTITY_CONFLICT

        malformed x-aip-service-id or mapping target
          -> REJECTED_INVALID + SERVICE_IDENTITY_INVALID

    This function is explicitly per-construct. Escalating a per-construct conflict into "emit
    nothing from the whole discovery run" is orchestration that belongs to a later increment.
    """
    if extension_value is not None and not is_valid_service_id(extension_value):
        return ServiceIdentityResolution(
            outcome=ServiceIdentityOutcome.REJECTED_INVALID,
            service_id=None,
            diagnostics=(
                IngestionDiagnostic(
                    code=DiagnosticCode.SERVICE_IDENTITY_INVALID,
                    message=f"malformed x-aip-service-id: {extension_value!r}",
                    source_pointer=construct_pointer,
                    source_instance_id=source_instance_id,
                ),
            ),
        )

    applicable: list[PointerBinding] = []
    if extension_value is not None:
        applicable.append(
            PointerBinding(
                source_instance_id=source_instance_id,
                pointer_prefix="",
                service_id=extension_value,
                path=ServiceIdentityPath.EXTENSION,
            )
        )

    for candidate in (*configured_mappings, *manifest_bindings):
        if not is_valid_service_id(candidate.service_id):
            return ServiceIdentityResolution(
                outcome=ServiceIdentityOutcome.REJECTED_INVALID,
                service_id=None,
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.SERVICE_IDENTITY_INVALID,
                        message=f"malformed mapping target: {candidate.service_id!r}",
                        source_pointer=construct_pointer,
                        source_instance_id=candidate.source_instance_id,
                    ),
                ),
            )
        if candidate.source_instance_id == source_instance_id and pointer_prefix_matches(
            prefix=candidate.pointer_prefix, candidate=construct_pointer
        ):
            applicable.append(candidate)

    distinct_ids = {candidate.service_id for candidate in applicable}

    if len(distinct_ids) == 0:
        return ServiceIdentityResolution(
            outcome=ServiceIdentityOutcome.REJECTED_UNSUPPORTED,
            service_id=None,
            diagnostics=(
                IngestionDiagnostic(
                    code=DiagnosticCode.SERVICE_IDENTITY_UNRESOLVED,
                    message=f"no Service identity resolves for construct {construct_pointer!r}",
                    source_pointer=construct_pointer,
                    source_instance_id=source_instance_id,
                ),
            ),
        )

    if len(distinct_ids) > 1:
        return ServiceIdentityResolution(
            outcome=ServiceIdentityOutcome.REJECTED_CONFLICT,
            service_id=None,
            diagnostics=(
                IngestionDiagnostic(
                    code=DiagnosticCode.SERVICE_IDENTITY_CONFLICT,
                    message=(
                        f"conflicting Service identities for construct {construct_pointer!r}: "
                        f"{sorted(distinct_ids)}"
                    ),
                    source_pointer=construct_pointer,
                    source_instance_id=source_instance_id,
                ),
            ),
        )

    return ServiceIdentityResolution(
        outcome=ServiceIdentityOutcome.RESOLVED,
        service_id=next(iter(distinct_ids)),
        diagnostics=(),
    )
