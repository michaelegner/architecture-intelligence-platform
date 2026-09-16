import pytest
from pydantic import ValidationError

from app.canonical.infrastructure import (
    InfrastructureClaim,
    InfrastructureClaimKind,
    InfrastructureContribution,
    InfrastructureEntity,
    InfrastructureEntityKind,
    InfrastructurePort,
    KubernetesEvidenceMode,
)
from app.canonical.model import ArchitectureModel


def test_entity_kind_enum_values():
    assert InfrastructureEntityKind.KUBERNETES_WORKLOAD == "KUBERNETES_WORKLOAD"
    assert InfrastructureEntityKind.KUBERNETES_POD == "KUBERNETES_POD"
    assert InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE == "KUBERNETES_NETWORK_SERVICE"
    assert InfrastructureEntityKind.KUBERNETES_INGRESS == "KUBERNETES_INGRESS"


def test_claim_kind_enum_values():
    assert InfrastructureClaimKind.WORKLOAD_EXISTS == "WORKLOAD_EXISTS"
    assert InfrastructureClaimKind.WORKLOAD_OWNS_POD == "WORKLOAD_OWNS_POD"
    assert (
        InfrastructureClaimKind.NETWORK_SERVICE_SELECTS_WORKLOAD
        == "NETWORK_SERVICE_SELECTS_WORKLOAD"
    )
    assert (
        InfrastructureClaimKind.INGRESS_ROUTES_TO_NETWORK_SERVICE
        == "INGRESS_ROUTES_TO_NETWORK_SERVICE"
    )


def test_evidence_mode_enum_values():
    assert KubernetesEvidenceMode.DECLARED_MANIFEST == "DECLARED_MANIFEST"
    assert KubernetesEvidenceMode.CAPTURED_RESOURCE == "CAPTURED_RESOURCE"


def test_workload_entity_has_no_service_specific_fields_set():
    entity = InfrastructureEntity(
        id="urn:aip:k8s-resource:deadbeef",
        entity_kind=InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        cluster_uid="cluster-1",
        api_group="apps",
        resource_kind="Deployment",
        namespace="default",
        name="order-service",
    )
    assert entity.service_type is None
    assert entity.ports == []


def test_network_service_entity_carries_sorted_ports():
    entity = InfrastructureEntity(
        id="urn:aip:k8s-resource:cafef00d",
        entity_kind=InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE,
        cluster_uid="cluster-1",
        api_group="",
        resource_kind="Service",
        namespace="default",
        name="order-service",
        service_type="ClusterIP",
        # A null name sorts as the empty string, so it precedes the named port.
        ports=[
            InfrastructurePort(name=None, protocol="TCP", port=9090),
            InfrastructurePort(name="http", protocol="TCP", port=8080),
        ],
    )
    assert entity.service_type == "ClusterIP"
    assert [p.port for p in entity.ports] == [9090, 8080]
    assert entity.ports[0].name is None


def test_namespace_is_empty_string_for_a_cluster_scoped_resource():
    entity = InfrastructureEntity(
        id="urn:aip:k8s-resource:abc123",
        entity_kind=InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        cluster_uid="cluster-1",
        api_group="apps",
        resource_kind="DaemonSet",
        namespace="",
        name="node-agent",
    )
    assert entity.namespace == ""


def test_contribution_carries_the_exact_frozen_fields():
    contribution = InfrastructureContribution(
        entity_id="urn:aip:k8s-resource:deadbeef",
        source_instance_id="urn:aip:source:kubernetes:feedface",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        resource_semantic_digest="digest-1",
        evidence_refs=["evidence:kubernetes:1"],
        mapping_rule_id="kubernetes-adapter@1",
        mapping_rule_version="v1",
    )
    assert contribution.evidence_mode is KubernetesEvidenceMode.CAPTURED_RESOURCE
    assert contribution.evidence_refs == ["evidence:kubernetes:1"]


def test_unary_claim_has_no_object_id_and_needs_no_sentinel():
    claim = InfrastructureClaim(
        kind=InfrastructureClaimKind.WORKLOAD_EXISTS,
        subject_id="urn:aip:k8s-resource:deadbeef",
        evidence_refs=["evidence:kubernetes:1"],
        mapping_rule_id="kubernetes-adapter@1",
        mapping_rule_version="v1",
    )
    assert claim.object_id is None
    # Round-trips through Pydantic's own (de)serialization without inventing a placeholder value.
    assert InfrastructureClaim.model_validate(claim.model_dump()).object_id is None


def test_binary_claim_carries_both_subject_and_object():
    claim = InfrastructureClaim(
        kind=InfrastructureClaimKind.WORKLOAD_OWNS_POD,
        subject_id="urn:aip:k8s-resource:workload",
        object_id="urn:aip:k8s-resource:pod",
        evidence_refs=["evidence:kubernetes:1"],
        mapping_rule_id="kubernetes-adapter@1",
        mapping_rule_version="v1",
    )
    assert claim.subject_id == "urn:aip:k8s-resource:workload"
    assert claim.object_id == "urn:aip:k8s-resource:pod"


def test_architecture_model_defaults_to_empty_infrastructure_lists():
    model = ArchitectureModel()
    assert model.infrastructure_entities == []
    assert model.infrastructure_contributions == []
    assert model.infrastructure_claims == []


def test_architecture_model_carries_infrastructure_facts_alongside_application_ones():
    entity = InfrastructureEntity(
        id="urn:aip:k8s-resource:deadbeef",
        entity_kind=InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        cluster_uid="cluster-1",
        api_group="apps",
        resource_kind="Deployment",
        namespace="default",
        name="order-service",
    )
    claim = InfrastructureClaim(
        kind=InfrastructureClaimKind.WORKLOAD_EXISTS,
        subject_id=entity.id,
        evidence_refs=["evidence:kubernetes:1"],
        mapping_rule_id="kubernetes-adapter@1",
        mapping_rule_version="v1",
    )
    model = ArchitectureModel(infrastructure_entities=[entity], infrastructure_claims=[claim])
    assert model.infrastructure_entities == [entity]
    assert model.infrastructure_claims == [claim]
    assert model.services == []


# I2 Draft 0.2 §7's frozen invariants, enforced rather than left to an adapter's good behavior.


def _entity(**overrides) -> dict:
    return {
        "id": "urn:aip:k8s-resource:deadbeef",
        "entity_kind": InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        "cluster_uid": "cluster-1",
        "api_group": "apps",
        "resource_kind": "Deployment",
        "namespace": "default",
        "name": "order-service",
        **overrides,
    }


def _claim_fields(**overrides) -> dict:
    return {
        "kind": InfrastructureClaimKind.WORKLOAD_EXISTS,
        "subject_id": "urn:aip:k8s-resource:deadbeef",
        "evidence_refs": ["evidence:kubernetes:1"],
        "mapping_rule_id": "kubernetes-adapter@1",
        "mapping_rule_version": "v1",
        **overrides,
    }


def _contribution_fields(**overrides) -> dict:
    return {
        "entity_id": "urn:aip:k8s-resource:deadbeef",
        "source_instance_id": "urn:aip:source:kubernetes:1",
        "evidence_mode": KubernetesEvidenceMode.CAPTURED_RESOURCE,
        "resource_semantic_digest": "digest-1",
        "evidence_refs": ["evidence:kubernetes:1"],
        "mapping_rule_id": "kubernetes-adapter@1",
        "mapping_rule_version": "v1",
        **overrides,
    }


def test_unary_claim_with_an_object_id_is_rejected():
    with pytest.raises(ValidationError, match="unary claim"):
        InfrastructureClaim(**_claim_fields(object_id="urn:aip:k8s-resource:pod"))


def test_binary_claim_without_an_object_id_is_rejected():
    with pytest.raises(ValidationError, match="binary claim"):
        InfrastructureClaim(
            **_claim_fields(kind=InfrastructureClaimKind.WORKLOAD_OWNS_POD, object_id=None)
        )


def test_empty_evidence_refs_are_rejected():
    with pytest.raises(ValidationError, match="non-empty"):
        InfrastructureClaim(**_claim_fields(evidence_refs=[]))
    with pytest.raises(ValidationError, match="non-empty"):
        InfrastructureContribution(**_contribution_fields(evidence_refs=[]))


def test_unsorted_evidence_refs_are_rejected():
    with pytest.raises(ValidationError, match="sorted"):
        InfrastructureClaim(**_claim_fields(evidence_refs=["evidence:b", "evidence:a"]))
    with pytest.raises(ValidationError, match="sorted"):
        InfrastructureContribution(
            **_contribution_fields(evidence_refs=["evidence:b", "evidence:a"])
        )


def test_duplicate_evidence_refs_are_rejected():
    with pytest.raises(ValidationError, match="duplicate-free"):
        InfrastructureClaim(**_claim_fields(evidence_refs=["evidence:a", "evidence:a"]))


def test_service_only_fields_on_a_non_service_entity_are_rejected():
    with pytest.raises(ValidationError, match="KUBERNETES_NETWORK_SERVICE-only"):
        InfrastructureEntity(**_entity(service_type="ClusterIP"))
    with pytest.raises(ValidationError, match="KUBERNETES_NETWORK_SERVICE-only"):
        InfrastructureEntity(
            **_entity(ports=[InfrastructurePort(name="http", protocol="TCP", port=8080)])
        )


def test_unsorted_ports_are_rejected():
    with pytest.raises(ValidationError, match="ports must be sorted"):
        InfrastructureEntity(
            **_entity(
                entity_kind=InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE,
                resource_kind="Service",
                api_group="",
                service_type="ClusterIP",
                ports=[
                    InfrastructurePort(name="http", protocol="TCP", port=8080),
                    InfrastructurePort(name="admin", protocol="TCP", port=9090),
                ],
            )
        )


def test_identifying_fields_must_be_non_empty():
    with pytest.raises(ValidationError):
        InfrastructureEntity(**_entity(name=""))
    with pytest.raises(ValidationError):
        InfrastructureEntity(**_entity(cluster_uid=""))
    with pytest.raises(ValidationError):
        InfrastructureClaim(**_claim_fields(subject_id=""))


def test_empty_namespace_and_api_group_remain_legal():
    """§6: "The core API group is the empty string. Namespace objects have an empty namespace
    component." - those two fields alone may legitimately be empty."""
    entity = InfrastructureEntity(**_entity(api_group="", namespace=""))
    assert entity.api_group == ""
    assert entity.namespace == ""


def test_claim_identity_is_the_hash_of_kind_subject_and_object():
    """§7.2: "Claim identity is the hash of kind, subject, and object (empty for a unary claim)."."""
    unary = InfrastructureClaim(**_claim_fields())
    same_unary = InfrastructureClaim(**_claim_fields())
    other_subject = InfrastructureClaim(**_claim_fields(subject_id="urn:aip:k8s-resource:other"))
    binary = InfrastructureClaim(
        **_claim_fields(
            kind=InfrastructureClaimKind.WORKLOAD_OWNS_POD, object_id="urn:aip:k8s-resource:pod"
        )
    )

    assert unary.id == same_unary.id
    assert unary.id != other_subject.id
    assert unary.id != binary.id
    assert unary.id.startswith("urn:aip:infra-claim:")


def test_contribution_identity_is_per_entity_and_source():
    first = InfrastructureContribution(**_contribution_fields())
    same = InfrastructureContribution(**_contribution_fields(resource_semantic_digest="digest-2"))
    other_source = InfrastructureContribution(
        **_contribution_fields(source_instance_id="urn:aip:source:kubernetes:2")
    )
    other_entity = InfrastructureContribution(
        **_contribution_fields(entity_id="urn:aip:k8s-resource:other")
    )

    # Identity is (entity, source) only - a changed digest is the *conflict* signal, not a new
    # contribution, so it must not change the id.
    assert first.id == same.id
    assert first.id != other_source.id
    assert first.id != other_entity.id
    assert first.id.startswith("urn:aip:infra-contribution:")
