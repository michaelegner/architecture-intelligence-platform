from app.sources.inventory import (
    InventoryStatus,
    inventory_capture_id,
    inventory_event_id,
    inventory_revision,
)
from app.sources.model import DiscoveryScopeId
from app.sources.tombstones import Tombstone

SCOPE_ID = DiscoveryScopeId("urn:aip:discovery-scope:" + "a" * 64)
SCOPE_DIGEST = "b" * 64


def _tombstone(revision: str, source: str = "urn:aip:source:filesystem:" + "c" * 64) -> Tombstone:
    return Tombstone(
        target_source_instance_id=source,
        discovery_scope_id=SCOPE_ID,
        expected_prior_inventory_revision="urn:aip:inventory-revision:" + "d" * 64,
        scope_definition_digest=SCOPE_DIGEST,
        actor="operator@example.com",
        reason="decommissioned",
        tombstone_revision=revision,
    )


def test_inventory_revision_stable_under_permuted_source_ids():
    ids = ["urn:aip:source:filesystem:" + "a" * 64, "urn:aip:source:filesystem:" + "b" * 64]
    forward = inventory_revision(
        discovery_scope_id=SCOPE_ID,
        scope_definition_digest=SCOPE_DIGEST,
        source_instance_ids=ids,
        tombstones=[],
        status=InventoryStatus.COMPLETE,
    )
    backward = inventory_revision(
        discovery_scope_id=SCOPE_ID,
        scope_definition_digest=SCOPE_DIGEST,
        source_instance_ids=list(reversed(ids)),
        tombstones=[],
        status=InventoryStatus.COMPLETE,
    )
    assert forward == backward


def test_inventory_revision_stable_under_permuted_tombstones():
    tombstones = [_tombstone("1"), _tombstone("2")]
    forward = inventory_revision(
        discovery_scope_id=SCOPE_ID,
        scope_definition_digest=SCOPE_DIGEST,
        source_instance_ids=[],
        tombstones=tombstones,
        status=InventoryStatus.COMPLETE,
    )
    backward = inventory_revision(
        discovery_scope_id=SCOPE_ID,
        scope_definition_digest=SCOPE_DIGEST,
        source_instance_ids=[],
        tombstones=list(reversed(tombstones)),
        status=InventoryStatus.COMPLETE,
    )
    assert forward == backward


def test_inventory_revision_changes_with_status():
    kwargs = {
        "discovery_scope_id": SCOPE_ID,
        "scope_definition_digest": SCOPE_DIGEST,
        "source_instance_ids": [],
        "tombstones": [],
    }
    complete = inventory_revision(status=InventoryStatus.COMPLETE, **kwargs)
    partial = inventory_revision(status=InventoryStatus.PARTIAL, **kwargs)
    failed = inventory_revision(status=InventoryStatus.FAILED, **kwargs)
    assert len({complete, partial, failed}) == 3


def test_inventory_revision_changes_with_tombstone_set():
    kwargs = {
        "discovery_scope_id": SCOPE_ID,
        "scope_definition_digest": SCOPE_DIGEST,
        "source_instance_ids": [],
        "status": InventoryStatus.COMPLETE,
    }
    without = inventory_revision(tombstones=[], **kwargs)
    with_one = inventory_revision(tombstones=[_tombstone("1")], **kwargs)
    assert without != with_one


def test_inventory_capture_id_distinct_across_capture_time_with_no_provider_revision():
    revision = "urn:aip:inventory-revision:" + "a" * 64
    first = inventory_capture_id(
        inventory_revision=revision, normalized_provider_revision=None, capture_time="t1"
    )
    second = inventory_capture_id(
        inventory_revision=revision, normalized_provider_revision=None, capture_time="t2"
    )
    assert first != second
    assert first.startswith("urn:aip:inventory-capture:")


def test_inventory_capture_id_distinct_across_provider_revisions():
    revision = "urn:aip:inventory-revision:" + "a" * 64
    first = inventory_capture_id(
        inventory_revision=revision, normalized_provider_revision="1", capture_time="t1"
    )
    second = inventory_capture_id(
        inventory_revision=revision, normalized_provider_revision="2", capture_time="t1"
    )
    assert first != second


def test_inventory_event_id_genesis_is_stable():
    capture_id = "urn:aip:inventory-capture:" + "a" * 64
    first = inventory_event_id(previous_event_id=None, inventory_capture_id=capture_id)
    second = inventory_event_id(previous_event_id=None, inventory_capture_id=capture_id)
    assert first == second
    assert first.startswith("urn:aip:inventory-event:")


def test_inventory_event_id_chains_on_previous_event():
    capture_id = "urn:aip:inventory-capture:" + "a" * 64
    genesis = inventory_event_id(previous_event_id=None, inventory_capture_id=capture_id)
    chained = inventory_event_id(previous_event_id=genesis, inventory_capture_id=capture_id)
    assert genesis != chained
