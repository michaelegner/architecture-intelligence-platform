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
from app.sources.model import DiagnosticCode, IngestionResult, KubernetesSourceConfig

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

    # I2 §12 slice 4a: this bundle is DECLARED_MANIFEST mode and its Pod has no owner reference,
    # so owner-chain resolution can never apply (§7.3's "declaration-only input" case) - one
    # K8S_OWNER_UNRESOLVED limitation, no WORKLOAD_OWNS_POD claim, but no rejection.
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    owner_diagnostic = next(
        d for d in result.diagnostics if d.code is DiagnosticCode.K8S_OWNER_UNRESOLVED
    )
    # Review round (PR #204): kubernetes_owner_chain.py (like kubernetes_mapping.py/
    # kubernetes_service_selection.py/kubernetes_ingress_backend.py) never sees `loaded.
    # descriptor` and so never sets source_instance_id itself - the adapter backfills it.
    assert owner_diagnostic.source_instance_id is not None
    assert result.semantic_input_digest is not None

    entities_by_kind = {e.entity_kind: e for e in result.model.infrastructure_entities}
    assert set(entities_by_kind) == {
        InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        InfrastructureEntityKind.KUBERNETES_POD,
        InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE,
    }
    workload = entities_by_kind[InfrastructureEntityKind.KUBERNETES_WORKLOAD]
    pod = entities_by_kind[InfrastructureEntityKind.KUBERNETES_POD]
    service = entities_by_kind[InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE]
    # I2 §12 slice 3b: promoted with no fabricated defaults - the bundle declares no
    # spec.type/spec.ports for its Service.
    assert service.service_type is None
    assert service.ports == []

    # One contribution per entity, evidence stamped KUBERNETES_SOURCE_TYPE and resolvable.
    contributions_by_entity = {c.entity_id: c for c in result.model.infrastructure_contributions}
    assert set(contributions_by_entity) == {workload.id, pod.id, service.id}
    provenance_ids = {p.id for p in result.model.provenance}
    for contribution in result.model.infrastructure_contributions:
        assert contribution.evidence_refs
        assert set(contribution.evidence_refs) <= provenance_ids
    assert all(p.source_type == KUBERNETES_SOURCE_TYPE for p in result.model.provenance)
    assert all(p.source_file == "resources.yaml" for p in result.model.provenance)
    assert all(p.source_revision == "snapshot-revision" for p in result.model.provenance)

    # Exactly one WORKLOAD_EXISTS claim, for the Workload only - §7.2 defines no existence claim
    # for KUBERNETES_NETWORK_SERVICE (or any other promoted kind).
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


def test_semantic_digest_changes_when_a_service_selector_value_changes(tmp_path):
    """I2 Draft 0.2 §6/§7.1: a Service selector VALUE change (not just its keys, which already
    drive Pod label retention) must invalidate replay. `selector` is part of the Service's own
    `resource_semantic_digest`/replay input (`MappedResource.projection`), not one of
    `InfrastructureEntity`'s own common persisted fields - so the promoted entity set itself stays
    unchanged even though the source-level digest moves."""
    baseline = _map_bundle(tmp_path, resource_bytes=_deployment_and_pod_yaml())
    changed = _map_bundle(
        tmp_path,
        resource_bytes=_deployment_and_pod_yaml(service_selector_value="a-different-value"),
    )
    assert baseline.semantic_input_digest != changed.semantic_input_digest
    baseline_entities = {e.entity_kind: e for e in baseline.model.infrastructure_entities}
    changed_entities = {e.entity_kind: e for e in changed.model.infrastructure_entities}
    assert baseline_entities.keys() == changed_entities.keys()


def _captured_deployment_outcome(tmp_path, *, uid: str, resource_version: str):
    documents = [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "checkout-api",
                "namespace": _NAMESPACE,
                "uid": uid,
                "resourceVersion": resource_version,
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
    return KubernetesSourceAdapter().map(
        loaded,
        service_identity=None,
        shared_identity=None,
        upstream_model=None,
        mapping_context_digest="a" * 64,
    )


def test_captured_resource_uid_is_carried_onto_the_contribution(tmp_path):
    result = _captured_deployment_outcome(tmp_path, uid="deploy-uid-1", resource_version="1")
    assert result.result is IngestionResult.ACCEPTED
    [contribution] = result.model.infrastructure_contributions
    assert contribution.captured_resource_uid == "deploy-uid-1"


def test_service_id_annotation_is_carried_onto_the_workload_contribution_only(tmp_path):
    """I2 Draft 0.2 §9 (slice 6): the retained `architecture-intelligence.io/service-id` annotation
    must be queryable as its own unqualified value, not only folded into the opaque
    `resource_semantic_digest` - mirrors `captured_resource_uid`'s own additive-field precedent
    (§5 retains this annotation "on supported Workloads" only, so Pod/Service contributions from
    this same bundle must never carry it)."""
    result = _map_bundle(
        tmp_path, resource_bytes=_deployment_and_pod_yaml(service_id_annotation="service:checkout")
    )
    entities_by_kind = {e.entity_kind: e for e in result.model.infrastructure_entities}
    contributions_by_entity = {c.entity_id: c for c in result.model.infrastructure_contributions}
    workload = entities_by_kind[InfrastructureEntityKind.KUBERNETES_WORKLOAD]
    pod = entities_by_kind[InfrastructureEntityKind.KUBERNETES_POD]
    service = entities_by_kind[InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE]

    assert contributions_by_entity[workload.id].service_id_annotation == "service:checkout"
    assert contributions_by_entity[pod.id].service_id_annotation is None
    assert contributions_by_entity[service.id].service_id_annotation is None


def test_absent_service_id_annotation_is_none_not_a_fabricated_default(tmp_path):
    result = _map_bundle(tmp_path, resource_bytes=_deployment_and_pod_yaml())
    entities_by_kind = {e.entity_kind: e for e in result.model.infrastructure_entities}
    contributions_by_entity = {c.entity_id: c for c in result.model.infrastructure_contributions}
    workload = entities_by_kind[InfrastructureEntityKind.KUBERNETES_WORKLOAD]
    assert contributions_by_entity[workload.id].service_id_annotation is None


def test_captured_uid_replacement_changes_the_semantic_digest(tmp_path):
    """Review round (PR #200): `resource_semantic_digest` deliberately excludes capture-only UID
    (§7.1), but the SOURCE-level `semantic_input_digest` must still react to a same-source UID
    replacement (§6: "any changed UID... MUST trigger owner-chain reevaluation") - otherwise a
    same-source capture of a new physical resource under the same logical name would be classified
    a no-op replay, silently rewriting the contribution's captured UID without advancing the graph
    revision fence.
    """
    first = _captured_deployment_outcome(tmp_path, uid="uid-a", resource_version="1")
    second = _captured_deployment_outcome(tmp_path, uid="uid-b", resource_version="1")
    assert first.semantic_input_digest != second.semantic_input_digest


def test_resource_version_only_change_does_not_change_the_semantic_digest(tmp_path):
    """§6: "A resourceVersion-only change with identical semantic structure/incarnations is an
    audit capture change, not a graph-revision change" - unlike a UID change, this must NOT move
    the digest."""
    first = _captured_deployment_outcome(tmp_path, uid="uid-a", resource_version="1")
    second = _captured_deployment_outcome(tmp_path, uid="uid-a", resource_version="2")
    assert first.semantic_input_digest == second.semantic_input_digest


def _captured_resources_outcome(tmp_path, documents: list[dict]):
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
    return KubernetesSourceAdapter().map(
        loaded,
        service_identity=None,
        shared_identity=None,
        upstream_model=None,
        mapping_context_digest="a" * 64,
    )


def test_a_resolved_owner_chain_and_service_selection_produce_both_relational_claims(tmp_path):
    """I2 §12 slice 4b, end-to-end: a real Deployment -> ReplicaSet -> Pod chain plus a matching
    Service selector produce both WORKLOAD_OWNS_POD and NETWORK_SERVICE_SELECTS_WORKLOAD claims
    from the same real adapter run, with the selection's evidence unioning the Service, Pod,
    Workload, and bridging ReplicaSet."""
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
        {
            "apiVersion": "apps/v1",
            "kind": "ReplicaSet",
            "metadata": {
                "name": "checkout-api-rs",
                "namespace": _NAMESPACE,
                "uid": "rs-uid-1",
                "resourceVersion": "1",
                "ownerReferences": [
                    {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": "checkout-api",
                        "uid": "deploy-uid-1",
                        "controller": True,
                    }
                ],
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "checkout-api-abc123",
                "namespace": _NAMESPACE,
                "uid": "pod-uid-1",
                "resourceVersion": "1",
                "labels": {"app": "checkout-api"},
                "ownerReferences": [
                    {
                        "apiVersion": "apps/v1",
                        "kind": "ReplicaSet",
                        "name": "checkout-api-rs",
                        "uid": "rs-uid-1",
                        "controller": True,
                    }
                ],
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "checkout-svc",
                "namespace": _NAMESPACE,
                "uid": "svc-uid-1",
                "resourceVersion": "1",
            },
            "spec": {"selector": {"app": "checkout-api"}},
        },
    ]
    result = _captured_resources_outcome(tmp_path, documents)
    assert result.result is IngestionResult.ACCEPTED

    entities_by_kind = {e.entity_kind: e for e in result.model.infrastructure_entities}
    workload = entities_by_kind[InfrastructureEntityKind.KUBERNETES_WORKLOAD]
    pod = entities_by_kind[InfrastructureEntityKind.KUBERNETES_POD]
    service = entities_by_kind[InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE]

    claims_by_kind = {c.kind: c for c in result.model.infrastructure_claims}
    assert set(claims_by_kind) == {
        InfrastructureClaimKind.WORKLOAD_EXISTS,
        InfrastructureClaimKind.WORKLOAD_OWNS_POD,
        InfrastructureClaimKind.NETWORK_SERVICE_SELECTS_WORKLOAD,
    }

    ownership = claims_by_kind[InfrastructureClaimKind.WORKLOAD_OWNS_POD]
    assert ownership.subject_id == workload.id
    assert ownership.object_id == pod.id

    selection = claims_by_kind[InfrastructureClaimKind.NETWORK_SERVICE_SELECTS_WORKLOAD]
    assert selection.subject_id == service.id
    assert selection.object_id == workload.id
    # Evidence unions the Service, the Pod, the Workload, and the bridging ReplicaSet (which has
    # no InfrastructureContribution of its own - §7.1 keeps ReplicaSet permanently unpromoted).
    provenance_ids = {p.id for p in result.model.provenance}
    assert set(selection.evidence_refs) <= provenance_ids
    assert set(selection.evidence_refs) >= set(ownership.evidence_refs)
    contributions_by_entity = {c.entity_id: c for c in result.model.infrastructure_contributions}
    assert set(contributions_by_entity[service.id].evidence_refs) <= set(selection.evidence_refs)


def test_a_resolved_ingress_backend_produces_the_routing_claim(tmp_path):
    """I2 §12 slice 4c, end-to-end: a real Ingress backending to a real Service's declared port
    produces a real INGRESS_ROUTES_TO_NETWORK_SERVICE claim from the same real adapter run."""
    documents = [
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "checkout-svc",
                "namespace": _NAMESPACE,
                "uid": "svc-uid-1",
                "resourceVersion": "1",
            },
            "spec": {"ports": [{"name": "http", "port": 80}]},
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": "checkout-ingress",
                "namespace": _NAMESPACE,
                "uid": "ingress-uid-1",
                "resourceVersion": "1",
            },
            "spec": {
                "defaultBackend": {"service": {"name": "checkout-svc", "port": {"name": "http"}}}
            },
        },
    ]
    result = _captured_resources_outcome(tmp_path, documents)
    assert result.result is IngestionResult.ACCEPTED

    entities_by_kind = {e.entity_kind: e for e in result.model.infrastructure_entities}
    service = entities_by_kind[InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE]
    ingress = entities_by_kind[InfrastructureEntityKind.KUBERNETES_INGRESS]

    [claim] = result.model.infrastructure_claims
    assert claim.kind is InfrastructureClaimKind.INGRESS_ROUTES_TO_NETWORK_SERVICE
    assert claim.subject_id == ingress.id
    assert claim.object_id == service.id
    provenance_ids = {p.id for p in result.model.provenance}
    assert set(claim.evidence_refs) <= provenance_ids
    contributions_by_entity = {c.entity_id: c for c in result.model.infrastructure_contributions}
    assert set(contributions_by_entity[service.id].evidence_refs) <= set(claim.evidence_refs)
    assert set(contributions_by_entity[ingress.id].evidence_refs) <= set(claim.evidence_refs)


def test_an_unresolved_ingress_backend_carries_the_complete_diagnostic_payload(tmp_path):
    """Review round (PR #204, 2nd pass): a real K8S_BACKEND_UNRESOLVED diagnostic from a real
    adapter run must carry the source instance ID (adapter-backfilled), the logical Ingress
    resource ID, a real file source pointer, and the affected claim kind - not just some of them."""
    documents = [
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": "checkout-ingress",
                "namespace": _NAMESPACE,
                "uid": "ingress-uid-1",
                "resourceVersion": "1",
            },
            "spec": {
                "defaultBackend": {"service": {"name": "nonexistent-svc", "port": {"number": 80}}}
            },
        },
    ]
    result = _captured_resources_outcome(tmp_path, documents)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.model.infrastructure_claims == []

    [ingress] = result.model.infrastructure_entities
    [diagnostic] = [
        d for d in result.diagnostics if d.code is DiagnosticCode.K8S_BACKEND_UNRESOLVED
    ]
    assert diagnostic.source_instance_id is not None
    assert ingress.id in diagnostic.message
    assert "INGRESS_ROUTES_TO_NETWORK_SERVICE" in diagnostic.message
    assert "checkout-ingress" in diagnostic.source_pointer
