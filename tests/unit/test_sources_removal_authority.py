from app.sources.inventory import InventoryStatus
from app.sources.removal_authority import (
    RemovalAuthorityDenialReason,
    authorize_source_removal,
)
from app.sources.tombstones import TombstoneRejectionReason, TombstoneValidation

SCOPE_ID = "urn:aip:discovery-scope:" + "a" * 64
SCOPE_DIGEST = "b" * 64
OTHER_SCOPE_ID = "urn:aip:discovery-scope:" + "c" * 64

VALID_TOMBSTONE = TombstoneValidation(accepted=True, rejection_reason=None, diagnostic=None)
INVALID_TOMBSTONE = TombstoneValidation(
    accepted=False, rejection_reason=TombstoneRejectionReason.STALE_PRIOR_REVISION, diagnostic=None
)


def _base_kwargs(**overrides):
    fields = {
        "tombstone_validation": None,
        "enumeration_status": InventoryStatus.COMPLETE,
        "enumeration_discovery_scope_id": SCOPE_ID,
        "enumeration_scope_definition_digest": SCOPE_DIGEST,
        "committed_discovery_scope_id": SCOPE_ID,
        "committed_scope_definition_digest": SCOPE_DIGEST,
        "source_absent_from_enumeration": True,
    }
    fields.update(overrides)
    return fields


def test_valid_tombstone_authorizes_regardless_of_enumeration_state():
    decision = authorize_source_removal(
        **_base_kwargs(
            tombstone_validation=VALID_TOMBSTONE,
            enumeration_status=InventoryStatus.FAILED,
            source_absent_from_enumeration=False,
        )
    )
    assert decision.authorized is True
    assert decision.reason is None


def test_complete_enumeration_same_scope_absent_authorizes():
    decision = authorize_source_removal(**_base_kwargs())
    assert decision.authorized is True
    assert decision.reason is None


def test_source_still_present_in_enumeration_denies():
    decision = authorize_source_removal(**_base_kwargs(source_absent_from_enumeration=False))
    assert decision.authorized is False
    assert decision.reason is RemovalAuthorityDenialReason.SOURCE_STILL_PRESENT_IN_ENUMERATION


def test_partial_enumeration_denies_regardless_of_absence():
    decision = authorize_source_removal(**_base_kwargs(enumeration_status=InventoryStatus.PARTIAL))
    assert decision.authorized is False
    assert decision.reason is RemovalAuthorityDenialReason.ENUMERATION_NOT_COMPLETE


def test_failed_enumeration_denies_regardless_of_absence():
    decision = authorize_source_removal(**_base_kwargs(enumeration_status=InventoryStatus.FAILED))
    assert decision.authorized is False
    assert decision.reason is RemovalAuthorityDenialReason.ENUMERATION_NOT_COMPLETE


def test_scope_mismatch_denies():
    decision = authorize_source_removal(
        **_base_kwargs(enumeration_discovery_scope_id=OTHER_SCOPE_ID)
    )
    assert decision.authorized is False
    assert decision.reason is RemovalAuthorityDenialReason.ENUMERATION_SCOPE_MISMATCH


def test_invalid_tombstone_with_valid_complete_enumeration_path_still_authorizes():
    # The two authorization paths are independent alternatives - an invalid tombstone does not
    # block the enumeration-based path from succeeding on its own.
    decision = authorize_source_removal(**_base_kwargs(tombstone_validation=INVALID_TOMBSTONE))
    assert decision.authorized is True
    assert decision.reason is None
