from pathlib import Path

import pytest
import yaml

from app.canonical.infrastructure import (
    InfrastructureClaim,
    InfrastructureClaimKind,
    InfrastructureContribution,
    InfrastructureEntity,
    InfrastructureEntityKind,
    KubernetesEvidenceMode,
)
from app.canonical.model import (
    ArchitectureModel,
    Message,
    Operation,
    Queue,
    Relation,
    Service,
)
from app.provenance.model import Provenance
from app.validation.canonical_validation import CanonicalValidationError, validate_canonical_model

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "example_architecture.yaml"


def test_valid_iteration1_fixture_passes():
    data = yaml.safe_load(FIXTURE_PATH.read_text())
    model = ArchitectureModel(**data)
    validate_canonical_model(model)  # must not raise


def test_v1_duplicate_service_id():
    model = ArchitectureModel(
        services=[Service(id="service:a", name="A"), Service(id="service:a", name="A2")]
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "Service id is not unique" in str(exc.value)


def test_v2_operation_without_provider():
    model = ArchitectureModel(
        services=[Service(id="service:a", name="A")],
        operations=[
            Operation(id="operation:a:GET:/x", service_id="service:a", method="GET", path="/x")
        ],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "exactly one PROVIDES" in str(exc.value)


def test_v2_operation_with_two_providers():
    model = ArchitectureModel(
        services=[Service(id="service:a", name="A"), Service(id="service:b", name="B")],
        operations=[
            Operation(id="operation:a:GET:/x", service_id="service:a", method="GET", path="/x")
        ],
        relations=[
            Relation(type="PROVIDES", source_id="service:a", target_id="operation:a:GET:/x"),
            Relation(type="PROVIDES", source_id="service:b", target_id="operation:a:GET:/x"),
        ],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "exactly one PROVIDES" in str(exc.value)


def test_v2_provider_mismatch_with_declared_service_id():
    model = ArchitectureModel(
        services=[Service(id="service:a", name="A"), Service(id="service:b", name="B")],
        operations=[
            Operation(id="operation:a:GET:/x", service_id="service:a", method="GET", path="/x")
        ],
        relations=[
            Relation(type="PROVIDES", source_id="service:b", target_id="operation:a:GET:/x")
        ],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "declares service_id" in str(exc.value)


def test_v3_duplicate_queue_id():
    model = ArchitectureModel(
        queues=[Queue(id="queue:a", name="a"), Queue(id="queue:a", name="a2")]
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "Queue id is not unique" in str(exc.value)


def test_v4_duplicate_message_id():
    model = ArchitectureModel(
        messages=[Message(id="message:a", name="a"), Message(id="message:a", name="a2")]
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "Message id is not unique" in str(exc.value)


def test_v5_calls_unknown_operation():
    model = ArchitectureModel(
        services=[Service(id="service:a", name="A")],
        relations=[Relation(type="CALLS", source_id="service:a", target_id="operation:missing")],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "unknown operation" in str(exc.value)


def test_v6_response_schema_relation_unknown_schema():
    model = ArchitectureModel(
        services=[Service(id="service:a", name="A")],
        operations=[
            Operation(
                id="operation:a:GET:/x",
                service_id="service:a",
                method="GET",
                path="/x",
                response_schema_ids=["schema:missing"],
            )
        ],
        relations=[
            Relation(type="PROVIDES", source_id="service:a", target_id="operation:a:GET:/x"),
            Relation(
                type="RESPONSE_SCHEMA", source_id="operation:a:GET:/x", target_id="schema:missing"
            ),
        ],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "unknown schema" in str(exc.value)


def test_v6_message_schema_id_unknown():
    model = ArchitectureModel(
        messages=[Message(id="message:a", name="a", schema_id="schema:missing")]
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "unknown schema" in str(exc.value)


def test_v7_dlq_self_reference():
    model = ArchitectureModel(
        queues=[Queue(id="queue:a", name="a")],
        relations=[Relation(type="DEAD_LETTERS_TO", source_id="queue:a", target_id="queue:a")],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "cannot be its own DLQ" in str(exc.value)


def test_v8_relation_unknown_source_and_target():
    model = ArchitectureModel(
        relations=[Relation(type="SENDS", source_id="service:missing", target_id="queue:missing")],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "unknown source" in str(exc.value)
    assert "unknown target" in str(exc.value)


def test_relation_with_known_evidence_id_passes():
    model = ArchitectureModel(
        queues=[Queue(id="queue:a", name="a")],
        services=[Service(id="service:a", name="A")],
        relations=[
            Relation(
                type="SENDS",
                source_id="service:a",
                target_id="queue:a",
                evidence_ids=["evidence:asyncapi:a"],
            )
        ],
        provenance=[
            Provenance(
                id="evidence:asyncapi:a", source_type="ASYNCAPI", source_file="a/asyncapi.yaml"
            )
        ],
    )
    validate_canonical_model(model)  # must not raise


def test_relation_with_unknown_evidence_id_rejected():
    model = ArchitectureModel(
        queues=[Queue(id="queue:a", name="a")],
        services=[Service(id="service:a", name="A")],
        relations=[
            Relation(
                type="SENDS",
                source_id="service:a",
                target_id="queue:a",
                evidence_ids=["evidence:asyncapi:missing"],
            )
        ],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert "unknown evidence" in str(exc.value)


def test_multiple_errors_are_all_reported():
    model = ArchitectureModel(
        services=[Service(id="service:a", name="A"), Service(id="service:a", name="A2")],
        queues=[Queue(id="queue:a", name="a"), Queue(id="queue:a", name="a2")],
    )
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    assert len(exc.value.errors) == 2


# I2 Draft 0.2 §3 item 6: infrastructure facts pass through the same validation path as every other
# canonical fact - §7.2's "resolve within the selected snapshot" / "both referenced entity IDs must
# resolve in the canonical model".


def _infra_entity(entity_id: str = "urn:aip:k8s-resource:workload") -> InfrastructureEntity:
    return InfrastructureEntity(
        id=entity_id,
        entity_kind=InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        cluster_uid="cluster-1",
        api_group="apps",
        resource_kind="Deployment",
        namespace="default",
        name="order-service",
    )


def _infra_evidence(evidence_id: str = "evidence:kubernetes:1") -> Provenance:
    return Provenance(
        id=evidence_id,
        source_type="KUBERNETES",
        source_file="snapshot.yaml",
    )


def test_infrastructure_model_with_resolving_references_passes():
    entity = _infra_entity()
    model = ArchitectureModel(
        provenance=[_infra_evidence()],
        infrastructure_entities=[entity],
        infrastructure_contributions=[
            InfrastructureContribution(
                entity_id=entity.id,
                source_instance_id="urn:aip:source:kubernetes:1",
                evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
                resource_semantic_digest="digest-1",
                evidence_refs=["evidence:kubernetes:1"],
                mapping_rule_id="kubernetes-adapter@1",
                mapping_rule_version="v1",
            )
        ],
        infrastructure_claims=[
            InfrastructureClaim(
                kind=InfrastructureClaimKind.WORKLOAD_EXISTS,
                subject_id=entity.id,
                evidence_refs=["evidence:kubernetes:1"],
                mapping_rule_id="kubernetes-adapter@1",
                mapping_rule_version="v1",
            )
        ],
    )
    validate_canonical_model(model)


def test_contribution_referencing_an_unknown_entity_is_rejected():
    model = ArchitectureModel(
        provenance=[_infra_evidence()],
        infrastructure_contributions=[
            InfrastructureContribution(
                entity_id="urn:aip:k8s-resource:missing",
                source_instance_id="urn:aip:source:kubernetes:1",
                evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
                resource_semantic_digest="digest-1",
                evidence_refs=["evidence:kubernetes:1"],
                mapping_rule_id="kubernetes-adapter@1",
                mapping_rule_version="v1",
            )
        ],
    )
    with pytest.raises(CanonicalValidationError, match="unknown entity"):
        validate_canonical_model(model)


def test_binary_claim_referencing_an_unknown_object_is_rejected():
    entity = _infra_entity()
    model = ArchitectureModel(
        provenance=[_infra_evidence()],
        infrastructure_entities=[entity],
        infrastructure_claims=[
            InfrastructureClaim(
                kind=InfrastructureClaimKind.WORKLOAD_OWNS_POD,
                subject_id=entity.id,
                object_id="urn:aip:k8s-resource:missing-pod",
                evidence_refs=["evidence:kubernetes:1"],
                mapping_rule_id="kubernetes-adapter@1",
                mapping_rule_version="v1",
            )
        ],
    )
    with pytest.raises(CanonicalValidationError, match="unknown object"):
        validate_canonical_model(model)


def test_claim_referencing_an_unknown_subject_is_rejected():
    model = ArchitectureModel(
        provenance=[_infra_evidence()],
        infrastructure_claims=[
            InfrastructureClaim(
                kind=InfrastructureClaimKind.WORKLOAD_EXISTS,
                subject_id="urn:aip:k8s-resource:missing",
                evidence_refs=["evidence:kubernetes:1"],
                mapping_rule_id="kubernetes-adapter@1",
                mapping_rule_version="v1",
            )
        ],
    )
    with pytest.raises(CanonicalValidationError, match="unknown subject"):
        validate_canonical_model(model)


def test_infrastructure_evidence_refs_must_resolve_to_a_provenance_record():
    entity = _infra_entity()
    model = ArchitectureModel(
        infrastructure_entities=[entity],
        infrastructure_claims=[
            InfrastructureClaim(
                kind=InfrastructureClaimKind.WORKLOAD_EXISTS,
                subject_id=entity.id,
                evidence_refs=["evidence:kubernetes:never-declared"],
                mapping_rule_id="kubernetes-adapter@1",
                mapping_rule_version="v1",
            )
        ],
    )
    with pytest.raises(CanonicalValidationError, match="unknown evidence"):
        validate_canonical_model(model)


def test_duplicate_infrastructure_entity_ids_are_rejected():
    model = ArchitectureModel(infrastructure_entities=[_infra_entity(), _infra_entity()])
    with pytest.raises(CanonicalValidationError, match="Infrastructure entity id is not unique"):
        validate_canonical_model(model)
