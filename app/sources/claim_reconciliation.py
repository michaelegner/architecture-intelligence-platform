from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from app.sources.model import SourceInstanceId


@dataclass(frozen=True)
class SourceClaimReconciliationPlan:
    expired_claim_keys: frozenset[str]
    ownership_removed_claim_keys: frozenset[str]
    newly_owned_claim_keys: frozenset[str]
    retained_claim_keys: frozenset[str]

    @property
    def is_semantic_no_op(self) -> bool:
        return not (
            self.expired_claim_keys
            or self.ownership_removed_claim_keys
            or self.newly_owned_claim_keys
        )


def plan_source_claim_reconciliation(
    *,
    source_instance_id: SourceInstanceId,
    committed_claim_owners: Mapping[str, AbstractSet[SourceInstanceId]],
    newly_emitted_claim_keys: AbstractSet[str],
) -> SourceClaimReconciliationPlan:
    """I1 spec §6, closing paragraph: "A claim expires only when its latest successful same-scope
    import no longer emits it (or the source has an authoritative removal decision), no other
    source owns it, and the complete reconciliation commits."

    `committed_claim_owners` maps every claim key currently committed to the *full set* of
    `SourceInstanceId`s currently attributed as owning it - the multi-owner model
    `app.graph.reconciliation` does not have today, since it only diffs one flat id set for one
    service. A claim this source stops emitting expires only if this source was its sole owner;
    otherwise it survives (moved to `ownership_removed_claim_keys`), directly proving "shared claims
    survive removal of one source."

    Whole-source removal (either `app.sources.removal_authority` path) is modeled by calling this
    with `newly_emitted_claim_keys=frozenset()` - the *authorization* to do that is a precondition
    this function does not itself re-verify.
    """
    previously_owned = frozenset(
        key for key, owners in committed_claim_owners.items() if source_instance_id in owners
    )
    no_longer_emitted = previously_owned - newly_emitted_claim_keys
    expired = frozenset(
        key for key in no_longer_emitted if committed_claim_owners[key] <= {source_instance_id}
    )
    ownership_removed = no_longer_emitted - expired
    newly_owned = frozenset(newly_emitted_claim_keys - previously_owned)
    retained = frozenset(newly_emitted_claim_keys & previously_owned)

    return SourceClaimReconciliationPlan(
        expired_claim_keys=expired,
        ownership_removed_claim_keys=ownership_removed,
        newly_owned_claim_keys=newly_owned,
        retained_claim_keys=retained,
    )
