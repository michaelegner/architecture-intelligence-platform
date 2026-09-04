from real_world_validation.comparator import compare
from real_world_validation.model import (
    ExpectedDocument,
    ExpectedRelation,
    InsufficientEvidenceItem,
    RelationFact,
    ScopeDeclaration,
    UnresolvedIdentityItem,
    UnsupportedItem,
)

_FACT = RelationFact(
    type="CALLS",
    source="service:rest-fights",
    target="operation:service:rest-heroes:GET:/api/heroes",
    status="CONFIRMED",
    declared_evidence=True,
    observed_evidence=True,
)


def _document(**overrides) -> ExpectedDocument:
    defaults = {
        "system": "quarkus-super-heroes",
        "upstream_revision": "abc123",
        "scope": ScopeDeclaration(entities=("service:rest-fights",), relation_types=("CALLS",)),
        "expected_relations": (ExpectedRelation(id="qsh-1", fact=_FACT),),
    }
    defaults.update(overrides)
    return ExpectedDocument(**defaults)


def test_matching_fact_is_correct():
    findings = compare(_document(), actual=[_FACT])

    assert len(findings) == 1
    assert findings[0].classification == "CORRECT"
    assert findings[0].id == "qsh-1"


def test_missing_fact_is_missing_supported():
    findings = compare(_document(), actual=[])

    assert len(findings) == 1
    assert findings[0].classification == "MISSING_SUPPORTED"
    assert findings[0].actual is None


def test_wrong_status_is_incorrect_supported():
    actual = RelationFact(**{**_FACT.__dict__, "status": "OBSERVED_ONLY"})

    findings = compare(_document(), actual=[actual])

    assert findings[0].classification == "INCORRECT_SUPPORTED"
    assert findings[0].expected == _FACT
    assert findings[0].actual == actual


def test_wrong_evidence_is_incorrect_supported():
    actual = RelationFact(**{**_FACT.__dict__, "declared_evidence": False})

    findings = compare(_document(), actual=[actual])

    assert findings[0].classification == "INCORRECT_SUPPORTED"


def test_unasserted_field_is_not_compared():
    # expected.yaml only asserts fields it actually sets; a None field is not part of the
    # assertion (I1 §13.3 - no fuzzy matching, but also no over-matching).
    loose_fact = RelationFact(type="CALLS", source=_FACT.source, target=_FACT.target)
    doc = _document(expected_relations=(ExpectedRelation(id="qsh-1", fact=loose_fact),))

    findings = compare(doc, actual=[_FACT])

    assert findings[0].classification == "CORRECT"


def test_unexpected_in_scope_actual_fact_is_incorrect_supported():
    invented = RelationFact(
        type="CALLS", source="service:rest-fights", target="operation:service:x:GET:/y"
    )

    findings = compare(_document(), actual=[_FACT, invented])

    assert len(findings) == 2
    invented_finding = next(f for f in findings if f.actual == invented)
    assert invented_finding.classification == "INCORRECT_SUPPORTED"
    assert invented_finding.expected is None


def test_out_of_scope_actual_fact_is_not_reported():
    out_of_scope = RelationFact(
        type="CALLS", source="service:rest-villains", target="operation:service:x:GET:/y"
    )

    findings = compare(_document(), actual=[_FACT, out_of_scope])

    assert len(findings) == 1


def test_unsupported_unresolved_and_insufficient_pass_through():
    doc = _document(
        unsupported=(UnsupportedItem(id="qsh-grpc", mechanism="grpc", description="d"),),
        unresolved_identity=(UnresolvedIdentityItem(id="qsh-worker-01", description="d"),),
        insufficient_evidence=(InsufficientEvidenceItem(id="qsh-unclear", description="d"),),
    )

    findings = compare(doc, actual=[_FACT])
    classifications = {f.id: f.classification for f in findings}

    assert classifications["qsh-grpc"] == "UNSUPPORTED"
    assert classifications["qsh-worker-01"] == "UNRESOLVED_IDENTITY"
    assert classifications["qsh-unclear"] == "INSUFFICIENT_EVIDENCE"


def test_output_is_deterministically_sorted_by_classification_then_identity():
    missing_fact = RelationFact(
        type="CALLS", source="service:rest-fights", target="operation:service:a:GET:/a"
    )
    doc = _document(
        expected_relations=(
            ExpectedRelation(id="qsh-b", fact=_FACT),
            ExpectedRelation(id="qsh-a", fact=missing_fact),
        )
    )

    findings = compare(doc, actual=[_FACT])

    # MISSING_SUPPORTED (rank 1) sorts before CORRECT (rank 5) regardless of input order.
    assert [f.classification for f in findings] == ["MISSING_SUPPORTED", "CORRECT"]

    # Running again on identical input produces the identical ordered result.
    assert compare(doc, actual=[_FACT]) == findings
