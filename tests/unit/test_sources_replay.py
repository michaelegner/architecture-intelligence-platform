from app.sources.replay import ReplayCase, classify_replay_case

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
SCOPE_A = "c" * 64
SCOPE_B = "d" * 64


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
    assert decision.graph_revision_advance_possible is False


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
    assert decision.graph_revision_advance_possible is False


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
