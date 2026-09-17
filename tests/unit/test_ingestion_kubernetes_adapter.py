import hashlib

import yaml

from app.canonical.infrastructure import (
    KUBERNETES_SOURCE_TYPE,
    InfrastructureClaimKind,
    InfrastructureEntityKind,
    KubernetesEvidenceMode,
)
from app.ingestion.kubernetes_adapter import KubernetesSourceAdapter
from app.ingestion.kubernetes_discoverer import KubernetesSourceDiscoverer
from app.sources.model import IngestionResult, KubernetesSourceConfig

_MATCHING_CONFIG_KWARGS = {
    "id": "configured-kubernetes-source",
    "envelope_relative_path": "envelope.yaml",
    "configured_scope_id": "configured-kubernetes-scope",
    "cluster_uid": "independently-established-cluster-identity",
    "evidence_mode": KubernetesEvidenceMode.DECLARED_MANIFEST,
    "authorized_producer": "attributable-producer",
    "authority_record": "configured-authority-record",
}

_NAMESPACE = "checkout"


def _envelope_dict(*, revision: str = "snapshot-revision") -> dict:
    return {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": "snapshot-example",
            "revision": revision,
            "producer": "attributable-producer",
            "capturedAt": "2026-09-15T10:00:00Z",
        },
        "source": {
            "configuredSourceId": "configured-kubernetes-source",
            "configuredScopeId": "configured-kubernetes-scope",
            "clusterUid": "independently-established-cluster-identity",
            "clusterIdentityEvidenceRef": "retained-identity-evidence",
            "mode": "DECLARED_MANIFEST",
        },
        "scope": {
            "namespaces": [_NAMESPACE],
            "resourceTypes": [
                "v1/Namespace",
                "v1/Pod",
                "v1/Service",
                "apps/v1/Deployment",
                "apps/v1/StatefulSet",
                "apps/v1/DaemonSet",
                "apps/v1/ReplicaSet",
                "networking.k8s.io/v1/Ingress",
            ],
        },
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": "configured-authority-record",
            "expectedPriorInventoryRevision": None,
        },
        "files": [],
    }


def _deployment_and_pod_yaml(
    *, service_id_annotation: str | None = None, service_selector_value: str = "checkout-api"
) -> bytes:
    labels = {"app": "checkout-api"}
    deployment_metadata = {"name": "checkout-api", "namespace": _NAMESPACE}
    if service_id_annotation is not None:
        deployment_metadata["annotations"] = {
            "architecture-intelligence.io/service-id": service_id_annotation
        }
    documents = [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": deployment_metadata,
        },
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "checkout-api-abc123",
                "namespace": _NAMESPACE,
                "labels": labels,
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "checkout-svc", "namespace": _NAMESPACE},
            "spec": {"selector": {"app": service_selector_value}},
        },
    ]
    return yaml.safe_dump_all(documents).encode()


def _write_bundle(tmp_path, *, resource_bytes: bytes, revision: str = "snapshot-revision") -> None:
    doc = _envelope_dict(revision=revision)
    doc["files"] = [
        {"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}
    ]
    (tmp_path / "envelope.yaml").write_bytes(yaml.safe_dump(doc).encode())
    (tmp_path / "resources.yaml").write_bytes(resource_bytes)


def _config(tmp_path, **overrides) -> KubernetesSourceConfig:
    kwargs = {**_MATCHING_CONFIG_KWARGS, "root": tmp_path, **overrides}
    return KubernetesSourceConfig(**kwargs)


def _map_bundle(tmp_path, *, resource_bytes: bytes, revision: str = "snapshot-revision"):
    _write_bundle(tmp_path, resource_bytes=resource_bytes, revision=revision)
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    loaded = outcome.loaded_sources[0]
    assert loaded.diagnostics == []
    adapter = KubernetesSourceAdapter()
    return adapter.map(
        loaded,
        service_identity=None,
        shared_identity=None,
        upstream_model=None,
        mapping_context_digest="a" * 64,
    )


def test_a_deployment_and_pod_bundle_produces_the_expected_canonical_facts(tmp_path):
    result = _map_bundle(tmp_path, resource_bytes=_deployment_and_pod_yaml())

    assert result.result is IngestionResult.ACCEPTED
    assert result.semantic_input_digest is not None

    entities_by_kind = {e.entity_kind: e for e in result.model.infrastructure_entities}
    assert set(entities_by_kind) == {
        InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        InfrastructureEntityKind.KUBERNETES_POD,
    }
    workload = entities_by_kind[InfrastructureEntityKind.KUBERNETES_WORKLOAD]
    pod = entities_by_kind[InfrastructureEntityKind.KUBERNETES_POD]

    # One contribution per entity, evidence stamped KUBERNETES_SOURCE_TYPE and resolvable.
    contributions_by_entity = {c.entity_id: c for c in result.model.infrastructure_contributions}
    assert set(contributions_by_entity) == {workload.id, pod.id}
    provenance_ids = {p.id for p in result.model.provenance}
    for contribution in result.model.infrastructure_contributions:
        assert contribution.evidence_refs
        assert set(contribution.evidence_refs) <= provenance_ids
    assert all(p.source_type == KUBERNETES_SOURCE_TYPE for p in result.model.provenance)
    assert all(p.source_file == "resources.yaml" for p in result.model.provenance)
    assert all(p.source_revision == "snapshot-revision" for p in result.model.provenance)

    # Exactly one WORKLOAD_EXISTS claim, for the Workload only.
    assert len(result.model.infrastructure_claims) == 1
    claim = result.model.infrastructure_claims[0]
    assert claim.kind is InfrastructureClaimKind.WORKLOAD_EXISTS
    assert claim.subject_id == workload.id
    assert claim.object_id is None
    assert claim.evidence_refs == contributions_by_entity[workload.id].evidence_refs


def test_semantic_digest_changes_when_an_allowlisted_field_changes(tmp_path):
    baseline = _map_bundle(tmp_path, resource_bytes=_deployment_and_pod_yaml())
    changed = _map_bundle(
        tmp_path, resource_bytes=_deployment_and_pod_yaml(service_id_annotation="service:checkout")
    )
    assert baseline.semantic_input_digest != changed.semantic_input_digest


def test_semantic_digest_is_stable_across_yaml_document_order(tmp_path):
    documents = list(yaml.safe_load_all(_deployment_and_pod_yaml()))
    reordered_bytes = yaml.safe_dump_all(list(reversed(documents))).encode()

    forward = _map_bundle(tmp_path, resource_bytes=_deployment_and_pod_yaml())
    reordered = _map_bundle(tmp_path, resource_bytes=reordered_bytes)
    assert forward.semantic_input_digest == reordered.semantic_input_digest


def test_semantic_digest_changes_when_a_non_promoted_service_selector_value_changes(tmp_path):
    """Review round (PR #200): a Service is never promoted to an entity by this slice, but its
    selector VALUE (not just its keys, which already drive Pod label retention) must still
    invalidate replay per I2 Draft 0.2 §6/§7.1 - no entity's own projection changes here."""
    baseline = _map_bundle(tmp_path, resource_bytes=_deployment_and_pod_yaml())
    changed = _map_bundle(
        tmp_path,
        resource_bytes=_deployment_and_pod_yaml(service_selector_value="a-different-value"),
    )
    assert baseline.semantic_input_digest != changed.semantic_input_digest
    # Neither promoted entity's own projection changed - only the untouched Service resource's did.
    baseline_entities = {e.entity_kind: e for e in baseline.model.infrastructure_entities}
    changed_entities = {e.entity_kind: e for e in changed.model.infrastructure_entities}
    assert baseline_entities.keys() == changed_entities.keys()


def test_captured_resource_uid_is_carried_onto_the_contribution(tmp_path):
    documents = [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "checkout-api",
                "namespace": _NAMESPACE,
                "uid": "deploy-uid-1",
                "resourceVersion": "1",
            },
        },
    ]
    resource_bytes = yaml.safe_dump_all(documents).encode()
    doc = _envelope_dict()
    doc["source"]["mode"] = "CAPTURED_RESOURCE"
    doc["files"] = [
        {"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}
    ]
    (tmp_path / "envelope.yaml").write_bytes(yaml.safe_dump(doc).encode())
    (tmp_path / "resources.yaml").write_bytes(resource_bytes)

    config = _config(tmp_path, evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE)
    outcome = KubernetesSourceDiscoverer(config).discover()
    loaded = outcome.loaded_sources[0]
    assert loaded.diagnostics == []
    result = KubernetesSourceAdapter().map(
        loaded,
        service_identity=None,
        shared_identity=None,
        upstream_model=None,
        mapping_context_digest="a" * 64,
    )
    assert result.result is IngestionResult.ACCEPTED
    [contribution] = result.model.infrastructure_contributions
    assert contribution.captured_resource_uid == "deploy-uid-1"
