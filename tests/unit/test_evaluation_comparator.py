from pathlib import Path

from evaluation.comparator import MISSING, SEMANTIC_MISMATCH, compare
from evaluation.model import Observation, RelationFact, Scenario, ScenarioScope

_EXPECTED_FACT = RelationFact(
    type="CALLS",
    source="service:order-service",
    target="operation:service:product-service:GET:/products/{id}",
    status="CONFIRMED",
    declared_evidence=True,
    observed_evidence=True,
)


def _scenario(*expected: RelationFact) -> Scenario:
    return Scenario(
        id="test-scenario",
        description="test",
        scope=ScenarioScope(entities=("service:order-service",)),
        observation=Observation(environment="test"),
        expected_relations=expected,
        path=Path("/dev/null"),
    )


def test_exact_match_passes():
    result = compare(_scenario(_EXPECTED_FACT), {_EXPECTED_FACT})

    assert result.passed
    assert result.mismatches == ()
    assert result.unexpected_count == 0


def test_missing_fact_fails():
    result = compare(_scenario(_EXPECTED_FACT), set())

    assert not result.passed
    assert len(result.mismatches) == 1
    assert result.mismatches[0].kind == MISSING
    assert result.mismatches[0].expected == _EXPECTED_FACT
    assert result.mismatches[0].actual is None


def test_wrong_status_fails_as_a_semantic_mismatch_not_a_missing_fact():
    actual = RelationFact(**{**_EXPECTED_FACT.__dict__, "status": "OBSERVED_ONLY"})

    result = compare(_scenario(_EXPECTED_FACT), {actual})

    assert not result.passed
    assert len(result.mismatches) == 1
    assert result.mismatches[0].kind == SEMANTIC_MISMATCH
    assert result.mismatches[0].actual == actual


def test_wrong_declared_evidence_fails():
    actual = RelationFact(**{**_EXPECTED_FACT.__dict__, "declared_evidence": False})

    result = compare(_scenario(_EXPECTED_FACT), {actual})

    assert not result.passed
    assert result.mismatches[0].kind == SEMANTIC_MISMATCH


def test_wrong_observed_evidence_fails():
    actual = RelationFact(**{**_EXPECTED_FACT.__dict__, "observed_evidence": False})

    result = compare(_scenario(_EXPECTED_FACT), {actual})

    assert not result.passed
    assert result.mismatches[0].kind == SEMANTIC_MISMATCH


def test_unset_expected_fields_are_not_asserted():
    unspecified = RelationFact(
        type="CALLS", source=_EXPECTED_FACT.source, target=_EXPECTED_FACT.target
    )
    actual = _EXPECTED_FACT  # any status/evidence combination should satisfy an unset expectation

    result = compare(_scenario(unspecified), {actual})

    assert result.passed


def test_unexpected_in_scope_facts_are_counted_but_do_not_fail_i1():
    other_fact = RelationFact(
        type="CALLS",
        source="service:order-service",
        target="operation:service:other-service:GET:/other",
        status="CONFIRMED",
        declared_evidence=True,
        observed_evidence=True,
    )

    result = compare(_scenario(_EXPECTED_FACT), {_EXPECTED_FACT, other_fact})

    assert result.passed
    assert result.unexpected_count == 1
