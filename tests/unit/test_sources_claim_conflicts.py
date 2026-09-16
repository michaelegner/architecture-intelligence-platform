from app.canonical.infrastructure import InfrastructureContribution, KubernetesEvidenceMode
from app.canonical.model import ArchitectureModel, Message, Schema
from app.sources.claim_conflicts import (
    detect_infrastructure_entity_content_conflicts,
    detect_shared_claim_content_conflicts,
)
from app.sources.model import DiagnosticCode


def _model(*, schemas=(), messages=(), infrastructure_contributions=()) -> ArchitectureModel:
    return ArchitectureModel(
        schemas=list(schemas),
        messages=list(messages),
        infrastructure_contributions=list(infrastructure_contributions),
    )


def _contribution(*, entity_id: str, digest: str) -> InfrastructureContribution:
    return InfrastructureContribution(
        entity_id=entity_id,
        source_instance_id="urn:aip:source:kubernetes:1",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        resource_semantic_digest=digest,
        evidence_refs=["evidence:kubernetes:1"],
        mapping_rule_id="kubernetes-adapter@1",
        mapping_rule_version="v1",
    )


def test_no_conflict_when_only_one_source_claims_a_schema():
    model = _model(schemas=[Schema(id="schema:owned:x", name="X", canonical_hash="h1")])
    assert detect_shared_claim_content_conflicts([model]) == ()


def test_identical_hashes_across_sources_merge_silently():
    a = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    b = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    assert detect_shared_claim_content_conflicts([a, b]) == ()


def test_different_hashes_across_sources_conflict():
    a = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    b = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h2")])
    diagnostics = detect_shared_claim_content_conflicts([a, b])
    assert len(diagnostics) == 1
    assert diagnostics[0].code is DiagnosticCode.SCHEMA_CONTENT_CONFLICT
    assert diagnostics[0].source_pointer == "schema:X"


def test_identical_contract_digests_across_sources_merge_silently():
    a = _model(messages=[Message(id="message:X", name="X", contract_digest="d1")])
    b = _model(messages=[Message(id="message:X", name="X", contract_digest="d1")])
    assert detect_shared_claim_content_conflicts([a, b]) == ()


def test_different_contract_digests_across_sources_conflict():
    a = _model(messages=[Message(id="message:X", name="X", contract_digest="d1")])
    b = _model(messages=[Message(id="message:X", name="X", contract_digest="d2")])
    diagnostics = detect_shared_claim_content_conflicts([a, b])
    assert len(diagnostics) == 1
    assert diagnostics[0].code is DiagnosticCode.MESSAGE_CONTENT_CONFLICT


def test_result_order_is_independent_of_input_model_order():
    a = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")])
    b = _model(schemas=[Schema(id="schema:X", name="X", canonical_hash="h2")])
    forward = detect_shared_claim_content_conflicts([a, b])
    backward = detect_shared_claim_content_conflicts([b, a])
    assert forward == backward


def test_unrelated_schemas_and_messages_do_not_cross_contaminate():
    a = _model(
        schemas=[Schema(id="schema:X", name="X", canonical_hash="h1")],
        messages=[Message(id="message:X", name="X", contract_digest="d1")],
    )
    b = _model(
        schemas=[Schema(id="schema:Y", name="Y", canonical_hash="h2")],
        messages=[Message(id="message:Y", name="Y", contract_digest="d2")],
    )
    assert detect_shared_claim_content_conflicts([a, b]) == ()


# I2 Draft 0.2 §3 prerequisite slice (PR B), §7.1: the infrastructure-entity equivalent of the
# Schema/Message content-conflict checks above.


def test_no_conflict_when_only_one_source_claims_an_infrastructure_entity():
    model = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d1")
        ]
    )
    assert detect_infrastructure_entity_content_conflicts([model]) == ()


def test_identical_semantic_digests_across_sources_merge_silently():
    a = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d1")
        ]
    )
    b = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d1")
        ]
    )
    assert detect_infrastructure_entity_content_conflicts([a, b]) == ()


def test_different_semantic_digests_across_sources_conflict():
    a = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d1")
        ]
    )
    b = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d2")
        ]
    )
    diagnostics = detect_infrastructure_entity_content_conflicts([a, b])
    assert len(diagnostics) == 1
    assert diagnostics[0].code is DiagnosticCode.INFRASTRUCTURE_ENTITY_CONTENT_CONFLICT
    assert diagnostics[0].source_pointer == "urn:aip:k8s-resource:x"


def test_infrastructure_conflict_result_order_is_independent_of_input_model_order():
    a = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d1")
        ]
    )
    b = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d2")
        ]
    )
    forward = detect_infrastructure_entity_content_conflicts([a, b])
    backward = detect_infrastructure_entity_content_conflicts([b, a])
    assert forward == backward


def test_unrelated_infrastructure_entities_do_not_cross_contaminate():
    a = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:x", digest="d1")
        ]
    )
    b = _model(
        infrastructure_contributions=[
            _contribution(entity_id="urn:aip:k8s-resource:y", digest="d2")
        ]
    )
    assert detect_infrastructure_entity_content_conflicts([a, b]) == ()
