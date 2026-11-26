import pytest

from app.sources.import_stats import ClaimEffectSet, SourceClaimEffects


def test_claim_effect_set_is_empty_by_default():
    assert ClaimEffectSet().is_empty is True


def test_claim_effect_set_is_non_empty_with_public_node_ids_only():
    effects = ClaimEffectSet(public_node_ids=("node-1",))

    assert effects.is_empty is False


def test_claim_effect_set_is_non_empty_with_relation_keys_only():
    effects = ClaimEffectSet(relation_keys=("relation-1",))

    assert effects.is_empty is False


def test_claim_effect_set_is_non_empty_with_internal_count_only():
    effects = ClaimEffectSet(internal_count=1)

    assert effects.is_empty is False


def test_source_claim_effects_is_empty_by_default():
    assert SourceClaimEffects().is_empty is True


@pytest.mark.parametrize(
    "effects",
    [
        pytest.param(
            SourceClaimEffects(added=ClaimEffectSet(public_node_ids=("node-1",))),
            id="added",
        ),
        pytest.param(
            SourceClaimEffects(changed=ClaimEffectSet(public_node_ids=("node-1",))),
            id="changed",
        ),
        pytest.param(
            SourceClaimEffects(expired=ClaimEffectSet(public_node_ids=("node-1",))),
            id="expired",
        ),
        pytest.param(
            SourceClaimEffects(ownership_removed=ClaimEffectSet(public_node_ids=("node-1",))),
            id="ownership_removed",
        ),
    ],
)
def test_source_claim_effects_is_non_empty_with_single_category(effects: SourceClaimEffects):
    assert effects.is_empty is False
