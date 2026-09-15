from app.sources.model import DiagnosticCode
from app.sources.tombstones import (
    Tombstone,
    TombstoneRejectionReason,
    validate_tombstone_against_committed_inventory,
)

SOURCE = "urn:aip:source:filesystem:" + "a" * 64
SCOPE_ID = "urn:aip:discovery-scope:" + "b" * 64
SCOPE_DIGEST = "c" * 64
REVISION = "urn:aip:inventory-revision:" + "d" * 64


def _tombstone(**overrides) -> Tombstone:
    fields = {
        "target_source_instance_id": SOURCE,
        "discovery_scope_id": SCOPE_ID,
        "expected_prior_inventory_revision": REVISION,
        "scope_definition_digest": SCOPE_DIGEST,
        "actor": "operator@example.com",
        "reason": "source decommissioned",
        "tombstone_revision": "1",
    }
    fields.update(overrides)
    return Tombstone(**fields)


def test_matching_prior_revision_is_accepted():
    result = validate_tombstone_against_committed_inventory(
        tombstone=_tombstone(),
        committed_discovery_scope_id=SCOPE_ID,
        committed_scope_definition_digest=SCOPE_DIGEST,
        committed_inventory_revision=REVISION,
    )
    assert result.accepted is True
    assert result.rejection_reason is None
    assert result.diagnostic is None


def test_mismatched_prior_revision_is_stale():
    result = validate_tombstone_against_committed_inventory(
        tombstone=_tombstone(),
        committed_discovery_scope_id=SCOPE_ID,
        committed_scope_definition_digest=SCOPE_DIGEST,
        committed_inventory_revision="urn:aip:inventory-revision:" + "e" * 64,
    )
    assert result.accepted is False
    assert result.rejection_reason is TombstoneRejectionReason.STALE_PRIOR_REVISION
    assert result.diagnostic.code is DiagnosticCode.TOMBSTONE_STALE


def test_no_committed_inventory_is_rejected():
    result = validate_tombstone_against_committed_inventory(
        tombstone=_tombstone(),
        committed_discovery_scope_id=None,
        committed_scope_definition_digest=None,
        committed_inventory_revision=None,
    )
    assert result.accepted is False
    assert result.rejection_reason is TombstoneRejectionReason.NO_COMMITTED_INVENTORY
    assert result.diagnostic.code is DiagnosticCode.TOMBSTONE_STALE


def test_scope_id_mismatch_is_rejected_even_with_matching_revision():
    result = validate_tombstone_against_committed_inventory(
        tombstone=_tombstone(),
        committed_discovery_scope_id="urn:aip:discovery-scope:" + "f" * 64,
        committed_scope_definition_digest=SCOPE_DIGEST,
        committed_inventory_revision=REVISION,
    )
    assert result.accepted is False
    assert result.rejection_reason is TombstoneRejectionReason.SCOPE_MISMATCH
    assert result.diagnostic.code is DiagnosticCode.TOMBSTONE_SCOPE_MISMATCH


def test_scope_digest_mismatch_is_rejected_even_with_matching_revision():
    result = validate_tombstone_against_committed_inventory(
        tombstone=_tombstone(),
        committed_discovery_scope_id=SCOPE_ID,
        committed_scope_definition_digest="g" * 64,
        committed_inventory_revision=REVISION,
    )
    assert result.accepted is False
    assert result.rejection_reason is TombstoneRejectionReason.SCOPE_MISMATCH
