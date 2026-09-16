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
        ports=[
            InfrastructurePort(name="http", protocol="TCP", port=8080),
            InfrastructurePort(name=None, protocol="TCP", port=9090),
        ],
    )
    assert entity.service_type == "ClusterIP"
    assert [p.port for p in entity.ports] == [8080, 9090]
    assert entity.ports[1].name is None


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
