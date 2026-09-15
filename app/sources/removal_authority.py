from dataclasses import dataclass
from enum import StrEnum

from app.sources.inventory import InventoryStatus
from app.sources.tombstones import TombstoneValidation


class RemovalAuthorityDenialReason(StrEnum):
    # No separate "tombstone invalid/absent" member: the function always falls through to the
    # enumeration-path checks below, which produce a concrete reason for every denial regardless of
    # tombstone state - a distinct tombstone-only reason would be unreachable dead API surface.
    ENUMERATION_NOT_COMPLETE = "ENUMERATION_NOT_COMPLETE"
    ENUMERATION_SCOPE_MISMATCH = "ENUMERATION_SCOPE_MISMATCH"
    SOURCE_STILL_PRESENT_IN_ENUMERATION = "SOURCE_STILL_PRESENT_IN_ENUMERATION"


@dataclass(frozen=True)
class RemovalAuthorityDecision:
    authorized: bool
    reason: RemovalAuthorityDenialReason | None


def authorize_source_removal(
    *,
    tombstone_validation: TombstoneValidation | None,
    enumeration_status: InventoryStatus,
    enumeration_discovery_scope_id: str,
    enumeration_scope_definition_digest: str,
    committed_discovery_scope_id: str,
    committed_scope_definition_digest: str,
    source_absent_from_enumeration: bool,
) -> RemovalAuthorityDecision:
    """I1 spec §6: "Whole-source expiration is authorized only by either: (1) a versioned
    desired-source inventory explicitly tombstoning the source; or (2) a COMPLETE authoritative
    enumeration with the same scope ID and scope digest that confirms the source is absent."

    The two paths are independent alternatives - either one alone suffices. Takes an
    already-computed `TombstoneValidation` (from `app.sources.tombstones`) rather than re-deriving
    staleness, so that logic lives in exactly one place. `tombstone_validation=None` means no
    tombstone was presented at all for this decision.
    """
    if tombstone_validation is not None and tombstone_validation.accepted:
        return RemovalAuthorityDecision(authorized=True, reason=None)

    if enumeration_status is not InventoryStatus.COMPLETE:
        return RemovalAuthorityDecision(
            authorized=False, reason=RemovalAuthorityDenialReason.ENUMERATION_NOT_COMPLETE
        )

    if (enumeration_discovery_scope_id, enumeration_scope_definition_digest) != (
        committed_discovery_scope_id,
        committed_scope_definition_digest,
    ):
        return RemovalAuthorityDecision(
            authorized=False, reason=RemovalAuthorityDenialReason.ENUMERATION_SCOPE_MISMATCH
        )

    if not source_absent_from_enumeration:
        return RemovalAuthorityDecision(
            authorized=False,
            reason=RemovalAuthorityDenialReason.SOURCE_STILL_PRESENT_IN_ENUMERATION,
        )

    return RemovalAuthorityDecision(authorized=True, reason=None)
