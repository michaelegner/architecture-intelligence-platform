import pytest

from app.sources.claim_reconciliation import plan_source_claim_reconciliation
from app.sources.inventory import InventoryStatus
from app.sources.removal_authority import RemovalAuthorityDenialReason, authorize_source_removal
from app.sources.replay import (
    InconsistentReplayStateError,
    ReplayCase,
    classify_replay_case,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
SCOPE_A = "c" * 64
SCOPE_B = "d" * 64
SOURCE = "urn:aip:source:filesystem:" + "e" * 64


def test_same_digest_same_scope_is_no_op():
    decision = classify_replay_case(
        load_or_reevaluation_successful=True,
        committed_semantic_input_digest=DIGEST_A,
        new_semantic_input_digest=DIGEST_A,
        committed_scope_definition_digest=SCOPE_A,
        new_scope_definition_digest=SCOPE_A,
    )
    assert decision.case is ReplayCase.REPLAY_NO_OP
    assert decision.graph_revision_advance_possible is False


def test_changed_digest_same_scope_is_reconcile():
    decision = classify_replay_case(
        load_or_reevaluation_successful=True,
        committed_semantic_input_digest=DIGEST_A,
        new_semantic_input_digest=DIGEST_B,
        committed_scope_definition_digest=SCOPE_A,
        new_scope_definition_digest=SCOPE_A,
    )
    assert decision.case is ReplayCase.RECONCILE_SAME_SCOPE_CHANGED_SEMANTIC_DIGEST
    assert decision.graph_revision_advance_possible is True


def test_same_digest_changed_scope_beats_no_op():
    decision = classify_replay_case(
        load_or_reevaluation_successful=True,
        committed_semantic_input_digest=DIGEST_A,
        new_semantic_input_digest=DIGEST_A,
        committed_scope_definition_digest=SCOPE_A,
        new_scope_definition_digest=SCOPE_B,
    )
    assert decision.case is ReplayCase.SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE
    # Eligible, not forced: §5.4 only guards EXPIRATION of claims absent from the new scope, it
    # does not forbid reconciling this source's own (unchanged) claims. Since nothing this source
    # emits actually changed, the downstream reconciliation plan below is still a no-op in practice.
    assert decision.graph_revision_advance_possible is True

    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE,
        committed_claim_owners={"claim:existing": {SOURCE}},
        newly_emitted_claim_keys={"claim:existing"},
    )
    assert plan.is_semantic_no_op is True


def test_changed_digest_changed_scope_beats_reconcile():
    # The most consequential priority-ordering proof: even though the semantic digest also
    # changed, a scope-digest change routes here per §5.4's "same completed scope_definition_digest"
    # qualifier on the reconcile case.
    decision = classify_replay_case(
        load_or_reevaluation_successful=True,
        committed_semantic_input_digest=DIGEST_A,
        new_semantic_input_digest=DIGEST_B,
        committed_scope_definition_digest=SCOPE_A,
        new_scope_definition_digest=SCOPE_B,
    )
    assert decision.case is ReplayCase.SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE
    assert decision.graph_revision_advance_possible is True


def test_scope_changed_with_added_claims_is_eligible_and_reconciliation_reflects_addition():
    # I1 §5.4's scope-changed case only guards expiration of claims absent from the new scope; it
    # does not prohibit adding newly emitted claims or reconciling changed evidence for retained
    # ones. A scope expansion that successfully emits {existing, added} against a committed
    # {existing} must be eligible to advance the graph, and the reconciliation plan must reflect
    # the addition rather than being suppressed.
    decision = classify_replay_case(
        load_or_reevaluation_successful=True,
        committed_semantic_input_digest=DIGEST_A,
        new_semantic_input_digest=DIGEST_B,
        committed_scope_definition_digest=SCOPE_A,
        new_scope_definition_digest=SCOPE_B,
    )
    assert decision.graph_revision_advance_possible is True

    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE,
        committed_claim_owners={"claim:existing": {SOURCE}},
        newly_emitted_claim_keys={"claim:existing", "claim:added"},
    )
    assert plan.newly_owned_claim_keys == {"claim:added"}
    assert plan.expired_claim_keys == frozenset()
    assert plan.is_semantic_no_op is False


def test_scope_changed_absent_claim_is_not_authorized_for_removal_on_eligibility_alone():
    # A claim newly absent under a changed scope must not be auto-expired just because the replay
    # decision says a graph-revision advance is *eligible*: claim_reconciliation still computes it
    # as an expiration candidate (sole-owned, not re-emitted), but committing that expiration
    # requires removal_authority's separate, explicit authorization - which an incomplete
    # enumeration and no tombstone does not grant.
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE,
        committed_claim_owners={"claim:now-absent": {SOURCE}},
        newly_emitted_claim_keys=frozenset(),
    )
    assert plan.expired_claim_keys == {"claim:now-absent"}

    decision = authorize_source_removal(
        tombstone_validation=None,
        enumeration_status=InventoryStatus.PARTIAL,
        enumeration_discovery_scope_id="scope-x",
        enumeration_scope_definition_digest=SCOPE_B,
        committed_discovery_scope_id="scope-x",
        committed_scope_definition_digest=SCOPE_A,
        source_absent_from_enumeration=True,
    )
    assert decision.authorized is False
    assert decision.reason is RemovalAuthorityDenialReason.ENUMERATION_NOT_COMPLETE


def test_failed_load_wins_over_everything_else():
    decision = classify_replay_case(
        load_or_reevaluation_successful=False,
        committed_semantic_input_digest=DIGEST_A,
        new_semantic_input_digest=DIGEST_B,
        committed_scope_definition_digest=SCOPE_A,
        new_scope_definition_digest=SCOPE_B,
    )
    assert decision.case is ReplayCase.FAILED_LOAD_PRESERVE_PRIOR
    assert decision.graph_revision_advance_possible is False


def test_failed_load_with_no_prior_state_is_still_failed_not_first_load():
    decision = classify_replay_case(
        load_or_reevaluation_successful=False,
        committed_semantic_input_digest=None,
        new_semantic_input_digest=DIGEST_A,
        committed_scope_definition_digest=None,
        new_scope_definition_digest=SCOPE_A,
    )
    assert decision.case is ReplayCase.FAILED_LOAD_PRESERVE_PRIOR


def test_no_prior_state_successful_load_is_first_successful_load():
    decision = classify_replay_case(
        load_or_reevaluation_successful=True,
        committed_semantic_input_digest=None,
        new_semantic_input_digest=DIGEST_A,
        committed_scope_definition_digest=None,
        new_scope_definition_digest=SCOPE_A,
    )
    assert decision.case is ReplayCase.FIRST_SUCCESSFUL_LOAD
    assert decision.graph_revision_advance_possible is True


def test_partial_committed_digest_state_raises():
    with pytest.raises(InconsistentReplayStateError):
        classify_replay_case(
            load_or_reevaluation_successful=True,
            committed_semantic_input_digest=DIGEST_A,
            new_semantic_input_digest=DIGEST_A,
            committed_scope_definition_digest=None,
            new_scope_definition_digest=SCOPE_A,
        )


def test_successful_load_missing_new_semantic_digest_raises():
    with pytest.raises(InconsistentReplayStateError):
        classify_replay_case(
            load_or_reevaluation_successful=True,
            committed_semantic_input_digest=DIGEST_A,
            new_semantic_input_digest=None,
            committed_scope_definition_digest=SCOPE_A,
            new_scope_definition_digest=SCOPE_A,
        )


def test_successful_load_missing_new_scope_digest_raises():
    with pytest.raises(InconsistentReplayStateError):
        classify_replay_case(
            load_or_reevaluation_successful=True,
            committed_semantic_input_digest=DIGEST_A,
            new_semantic_input_digest=DIGEST_A,
            committed_scope_definition_digest=SCOPE_A,
            new_scope_definition_digest=None,
        )


def test_failed_load_does_not_require_new_digests():
    # The invariant check for new digests only applies to a *successful* load - a failed load may
    # never have produced comparable digests at all, so None is legitimate here.
    decision = classify_replay_case(
        load_or_reevaluation_successful=False,
        committed_semantic_input_digest=DIGEST_A,
        new_semantic_input_digest=None,
        committed_scope_definition_digest=SCOPE_A,
        new_scope_definition_digest=None,
    )
    assert decision.case is ReplayCase.FAILED_LOAD_PRESERVE_PRIOR
