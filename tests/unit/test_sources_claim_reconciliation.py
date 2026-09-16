from app.sources.claim_reconciliation import plan_source_claim_reconciliation

SOURCE_A = "urn:aip:source:filesystem:" + "a" * 64
SOURCE_B = "urn:aip:source:filesystem:" + "b" * 64


def test_sole_owner_claim_dropped_is_expired():
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE_A,
        committed_claim_owners={"claim:1": {SOURCE_A}},
        newly_emitted_claim_keys=frozenset(),
    )
    assert plan.expired_claim_keys == {"claim:1"}
    assert plan.ownership_removed_claim_keys == frozenset()
    assert plan.is_semantic_no_op is False


def test_shared_claim_dropped_by_one_owner_survives():
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE_A,
        committed_claim_owners={"claim:1": {SOURCE_A, SOURCE_B}},
        newly_emitted_claim_keys=frozenset(),
    )
    assert plan.expired_claim_keys == frozenset()
    assert plan.ownership_removed_claim_keys == {"claim:1"}
    assert plan.is_semantic_no_op is False


def test_new_claim_is_newly_owned():
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE_A,
        committed_claim_owners={},
        newly_emitted_claim_keys={"claim:1"},
    )
    assert plan.newly_owned_claim_keys == {"claim:1"}
    assert plan.is_semantic_no_op is False


def test_unchanged_claim_is_retained_and_plan_is_no_op():
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE_A,
        committed_claim_owners={"claim:1": {SOURCE_A}},
        newly_emitted_claim_keys={"claim:1"},
    )
    assert plan.retained_claim_keys == {"claim:1"}
    assert plan.expired_claim_keys == frozenset()
    assert plan.ownership_removed_claim_keys == frozenset()
    assert plan.newly_owned_claim_keys == frozenset()
    assert plan.is_semantic_no_op is True


def test_whole_source_removal_shared_claim_survives_sole_owned_claim_expires():
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE_A,
        committed_claim_owners={
            "claim:shared": {SOURCE_A, SOURCE_B},
            "claim:sole": {SOURCE_A},
        },
        newly_emitted_claim_keys=frozenset(),
    )
    assert plan.expired_claim_keys == {"claim:sole"}
    assert plan.ownership_removed_claim_keys == {"claim:shared"}
    assert plan.is_semantic_no_op is False


def test_claim_owned_by_other_source_only_is_unaffected():
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE_A,
        committed_claim_owners={"claim:1": {SOURCE_B}},
        newly_emitted_claim_keys=frozenset(),
    )
    assert plan.expired_claim_keys == frozenset()
    assert plan.ownership_removed_claim_keys == frozenset()
    assert plan.is_semantic_no_op is True


def test_is_semantic_no_op_true_only_when_all_three_mutation_sets_empty():
    plan = plan_source_claim_reconciliation(
        source_instance_id=SOURCE_A,
        committed_claim_owners={"claim:1": {SOURCE_A}},
        newly_emitted_claim_keys={"claim:1", "claim:2"},
    )
    assert plan.newly_owned_claim_keys == {"claim:2"}
    assert plan.is_semantic_no_op is False
