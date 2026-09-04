from pathlib import Path

import pytest

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    DeliveryKind,
    DeliveryRef,
    DeliveryRelationType,
    DependencyClaim,
    DependencyPredicate,
    DestinationResolution,
    EntityRef,
    EntityType,
    Limitation,
    LimitationCode,
    ObservationContextRef,
    Outcome,
    Producer,
    Qualification,
    ServiceDependenciesData,
    SnapshotRef,
)
from evaluation.architecture_answers import comparator
from evaluation.architecture_answers.model import Request, Scenario

_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.0", build_revision="f" * 40
)


@pytest.fixture(autouse=True)
def _fixed_candidate_sha(monkeypatch):
    """The comparator independently re-derives the real git SHA to check
    `producer.build_revision` against (I1.4 review finding #1) - pin it to _PRODUCER's own value so
    these tests exercise comparator logic, not this checkout's actual git state."""
    monkeypatch.setattr(comparator, "current_git_sha", lambda: _PRODUCER.build_revision)


_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_CONTEXT = ObservationContextRef(
    context_id="aip:observation-context:v1:" + "b" * 64,
    environment="test",
    window_start="2026-08-26T00:00:00.000000Z",
    window_end="2026-08-27T00:00:00.000000Z",
)
_SUBJECT = EntityRef(id="service:order-service", type=EntityType.SERVICE, name="OrderService")
_OBJECT = EntityRef(id="service:product-service", type=EntityType.SERVICE, name="ProductService")
_VIA = EntityRef(
    id="operation:product-service:GET:/products/{id}",
    type=EntityType.OPERATION,
    name="GET /products/{id}",
    method="GET",
    path="/products/{id}",
)


def _claim(
    *, claim_id_suffix: str, qualification=Qualification.CONFIRMED, evidence_refs=("e1",)
) -> DependencyClaim:
    return DependencyClaim(
        claim_id="aip:claim:v1:" + claim_id_suffix * 64,
        subject=_SUBJECT,
        predicate=DependencyPredicate.DIRECT_DEPENDENCY,
        object=_OBJECT,
        destination_resolution=DestinationResolution.RESOLVED_SERVICE,
        delivery=DeliveryRef(
            kind=DeliveryKind.SYNC_HTTP, relation_type=DeliveryRelationType.CALLS, via=_VIA
        ),
        qualification=qualification,
        coverage=None,
        evidence_refs=sorted(evidence_refs),
        resolution_evidence_refs=["r1"],
    )


def _answer(
    *, claims=(), limitations=(), outcome=Outcome.ANSWERED
) -> ArchitectureAnswer[ServiceDependenciesData]:
    data = (
        None
        if outcome == Outcome.NOT_ANSWERED
        else ServiceDependenciesData(
            service=_SUBJECT, dependency_claim_ids=[c.claim_id for c in claims]
        )
    )
    evidence_refs = sorted(
        {ref for c in claims for ref in (*c.evidence_refs, *c.resolution_evidence_refs)}
    )
    return ArchitectureAnswer[ServiceDependenciesData](
        schema_version="0.4",
        producer=_PRODUCER,
        tool="get_service_dependencies",
        outcome=outcome,
        snapshot=_SNAPSHOT,
        observation_context=_CONTEXT,
        data=data,
        claims=list(claims),
        evidence_refs=evidence_refs,
        limitations=list(limitations),
    )


def _scenario(expected: ArchitectureAnswer[ServiceDependenciesData]) -> Scenario:
    return Scenario(
        id="test-scenario",
        description="test",
        request=Request(service_id="service:order-service"),
        expected=expected,
        path=Path("/nonexistent"),
    )


def test_identical_answers_pass_with_no_mismatches():
    claim = _claim(claim_id_suffix="1")
    answer = _answer(claims=[claim])
    result = comparator.compare(_scenario(answer), answer)

    assert result.passed
    assert result.missing_claim_ids == ()
    assert result.unexpected_claim_ids == ()
    assert result.field_mismatches == ()


def test_a_placeholder_build_revision_is_caught_even_though_it_is_not_the_frozen_literal(
    monkeypatch,
):
    """producer.build_revision is deliberately NOT compared against the frozen expected literal
    (I1.4 review finding #1) - it's compared against the independently re-derived real candidate
    SHA. So an actual answer whose build_revision doesn't match the *real* SHA is caught even when
    it happens to equal whatever the frozen fixture's own (unused) build_revision literal is."""
    monkeypatch.setattr(comparator, "current_git_sha", lambda: "1" * 40)
    claim = _claim(claim_id_suffix="1")
    # Both expected and actual carry the same _PRODUCER (build_revision "f" * 40) - if the
    # comparator naively compared literal-vs-literal here, this would wrongly pass.
    expected = _answer(claims=[claim])
    actual = _answer(claims=[claim])
    result = comparator.compare(_scenario(expected), actual)

    assert not result.passed
    build_revision_mismatches = [
        m for m in result.field_mismatches if m.field == "producer.build_revision"
    ]
    assert len(build_revision_mismatches) == 1
    assert build_revision_mismatches[0].expected == repr("1" * 40)


def test_missing_claim_is_reported():
    claim = _claim(claim_id_suffix="1")
    expected = _answer(claims=[claim])
    actual = _answer(claims=[])
    result = comparator.compare(_scenario(expected), actual)

    assert not result.passed
    assert result.missing_claim_ids == (claim.claim_id,)
    assert result.unexpected_claim_ids == ()


def test_unexpected_claim_is_reported():
    claim = _claim(claim_id_suffix="1")
    expected = _answer(claims=[])
    actual = _answer(claims=[claim])
    result = comparator.compare(_scenario(expected), actual)

    assert not result.passed
    assert result.unexpected_claim_ids == (claim.claim_id,)
    assert result.missing_claim_ids == ()


def test_a_field_level_mismatch_on_a_matched_claim_is_reported():
    expected_claim = _claim(claim_id_suffix="1", qualification=Qualification.CONFIRMED)
    actual_claim = _claim(claim_id_suffix="1", qualification=Qualification.OBSERVED_ONLY)
    expected = _answer(claims=[expected_claim])
    actual = _answer(claims=[actual_claim])
    result = comparator.compare(_scenario(expected), actual)

    assert not result.passed
    mismatch_fields = {
        m.field for m in result.field_mismatches if m.claim_id == expected_claim.claim_id
    }
    assert "qualification" in mismatch_fields


def test_a_wrong_but_existing_evidence_reference_is_a_real_mismatch():
    """I1.4 review finding #2: exact evidence-ref comparison, not just existence."""
    expected_claim = _claim(claim_id_suffix="1", evidence_refs=("e1",))
    actual_claim = _claim(claim_id_suffix="1", evidence_refs=("e2",))
    expected = _answer(claims=[expected_claim])
    actual = _answer(claims=[actual_claim])
    result = comparator.compare(_scenario(expected), actual)

    assert not result.passed
    assert any(m.field == "evidence_refs" for m in result.field_mismatches)


def test_outcome_mismatch_is_reported_as_answer_level():
    expected = _answer(claims=[], outcome=Outcome.ANSWERED)
    actual = _answer(
        claims=[],
        outcome=Outcome.NOT_ANSWERED,
    )
    result = comparator.compare(_scenario(expected), actual)

    assert not result.passed
    outcome_mismatches = [m for m in result.field_mismatches if m.field == "outcome"]
    assert len(outcome_mismatches) == 1
    assert outcome_mismatches[0].claim_id is None


def test_limitations_mismatch_is_reported():
    limitation = Limitation(
        code=LimitationCode.UNKNOWN_ENTITY, message="x does not exist", claim_ids=[]
    )
    expected = _answer(claims=[], outcome=Outcome.NOT_ANSWERED, limitations=[limitation])
    actual = _answer(claims=[], outcome=Outcome.NOT_ANSWERED, limitations=[])
    result = comparator.compare(_scenario(expected), actual)

    assert not result.passed
    assert any(m.field == "limitations" for m in result.field_mismatches)


def test_broken_evidence_refs_fail_the_scenario_even_with_a_perfect_semantic_match():
    claim = _claim(claim_id_suffix="1")
    answer = _answer(claims=[claim])
    result = comparator.compare(_scenario(answer), answer, broken_evidence_refs=("evidence:ghost",))

    assert not result.passed
    assert result.broken_evidence_refs == ("evidence:ghost",)
    assert result.field_mismatches == ()
