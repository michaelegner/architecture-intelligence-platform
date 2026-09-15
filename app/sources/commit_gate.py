from collections.abc import Sequence

from app.sources.inventory import InventoryStatus
from app.sources.model import IngestionResult

_REJECTED_RESULTS = frozenset(
    {
        IngestionResult.REJECTED_INVALID,
        IngestionResult.REJECTED_UNSUPPORTED,
        IngestionResult.REJECTED_CONFLICT,
    }
)


def classify_inventory_status(
    *,
    source_results: Sequence[IngestionResult],
    discoverer_enumeration_complete: bool,
) -> InventoryStatus:
    """I1 spec §6: "If any discovered source fails validation/load, the run is PARTIAL or FAILED;
    no source reconciliation, COMPLETE inventory, or tombstone from that run may commit."

    The spec does not itself draw the PARTIAL/FAILED line. This PR's choice: the discoverer itself
    failing to produce a trustworthy enumeration at all (missing root, auth failure, timeout,
    truncation, pagination error - §6's own list) is FAILED; enumeration succeeding but at least one
    individually discovered source resolving REJECTED_* is PARTIAL; otherwise COMPLETE. Both PARTIAL
    and FAILED are equally commit-ineligible (see `run_is_eligible_to_commit`) - this classification
    only affects the recorded status, not commit behavior.
    """
    if not discoverer_enumeration_complete:
        return InventoryStatus.FAILED
    if any(result in _REJECTED_RESULTS for result in source_results):
        return InventoryStatus.PARTIAL
    return InventoryStatus.COMPLETE


def run_is_eligible_to_commit(status: InventoryStatus) -> bool:
    """I1 spec §6: only a COMPLETE run may commit a reconciliation, inventory, or tombstone; PARTIAL
    and FAILED runs commit nothing and preserve prior state.
    """
    return status is InventoryStatus.COMPLETE
