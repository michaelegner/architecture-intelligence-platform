import pytest

from app.sources.commit_gate import classify_inventory_status, run_is_eligible_to_commit
from app.sources.inventory import InventoryStatus
from app.sources.model import IngestionResult


def test_all_accepted_with_complete_enumeration_is_complete_and_eligible():
    status = classify_inventory_status(
        source_results=[IngestionResult.ACCEPTED, IngestionResult.ACCEPTED_WITH_LIMITATIONS],
        discoverer_enumeration_complete=True,
    )
    assert status is InventoryStatus.COMPLETE
    assert run_is_eligible_to_commit(status) is True


@pytest.mark.parametrize(
    "rejected_result",
    [
        IngestionResult.REJECTED_INVALID,
        IngestionResult.REJECTED_UNSUPPORTED,
        IngestionResult.REJECTED_CONFLICT,
    ],
)
def test_any_rejected_result_among_accepted_is_partial_and_not_eligible(rejected_result):
    status = classify_inventory_status(
        source_results=[IngestionResult.ACCEPTED, rejected_result],
        discoverer_enumeration_complete=True,
    )
    assert status is InventoryStatus.PARTIAL
    assert run_is_eligible_to_commit(status) is False


def test_incomplete_enumeration_is_failed_even_with_zero_source_results():
    status = classify_inventory_status(
        source_results=[],
        discoverer_enumeration_complete=False,
    )
    assert status is InventoryStatus.FAILED
    assert run_is_eligible_to_commit(status) is False


def test_incomplete_enumeration_is_failed_even_with_all_accepted_results():
    status = classify_inventory_status(
        source_results=[IngestionResult.ACCEPTED],
        discoverer_enumeration_complete=False,
    )
    assert status is InventoryStatus.FAILED


def test_empty_source_list_with_complete_enumeration_is_complete():
    status = classify_inventory_status(
        source_results=[],
        discoverer_enumeration_complete=True,
    )
    assert status is InventoryStatus.COMPLETE
    assert run_is_eligible_to_commit(status) is True
