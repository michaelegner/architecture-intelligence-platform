from app.canonical.infrastructure import InfrastructureEntityKind
from app.sources.kubernetes_mapping import (
    SERVICE_ID_ANNOTATION,
    map_kubernetes_resources,
)
from app.sources.model import DiagnosticCode, IngestionResult, KubernetesResourceEntry

_CLUSTER_UID = "independently-established-cluster-identity"
_NAMESPACE = "checkout"


def _entry(document: dict, *, source_pointer: str = "resources.yaml") -> KubernetesResourceEntry:
    return KubernetesResourceEntry(source_pointer=source_pointer, document=document)


def _deployment(
    name: str = "checkout-api",
    *,
    namespace: str = _NAMESPACE,
    annotations: dict | None = None,
    owner_references: list | None = None,
) -> dict:
    metadata = {"name": name, "namespace": namespace}
    if annotations is not None:
        metadata["annotations"] = annotations
    if owner_references is not None:
        metadata["ownerReferences"] = owner_references
    return {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": metadata}


def _pod(
    name: str = "checkout-api-abc123",
    *,
    namespace: str = _NAMESPACE,
    labels: dict | None = None,
    owner_references: list | None = None,
    uid: str | None = None,
    resource_version: str | None = None,
) -> dict:
    metadata = {"name": name, "namespace": namespace}
    if labels is not None:
        metadata["labels"] = labels
    if owner_references is not None:
        metadata["ownerReferences"] = owner_references
    if uid is not None:
        metadata["uid"] = uid
    if resource_version is not None:
        metadata["resourceVersion"] = resource_version
    return {"apiVersion": "v1", "kind": "Pod", "metadata": metadata}


def _service(name: str = "checkout-svc", *, selector: dict, namespace: str = _NAMESPACE) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"selector": selector},
    }


def _map(resources, *, requires_capture_identity: bool = False, scope_namespaces=(_NAMESPACE,)):
    return map_kubernetes_resources(
        tuple(resources),
        cluster_uid=_CLUSTER_UID,
        requires_capture_identity=requires_capture_identity,
        scope_namespaces=tuple(scope_namespaces),
    )


# --- classification -------------------------------------------------------------------------


def test_unsupported_resource_kind_is_omitted_with_a_pointer_diagnostic():
    config_map = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "settings", "namespace": _NAMESPACE},
    }
    result = _map([_entry(config_map, source_pointer="cm.yaml")])
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.entities == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code is DiagnosticCode.K8S_RESOURCE_UNSUPPORTED
    assert diagnostic.source_pointer == "cm.yaml:v1/ConfigMap"


def test_admitted_deployment_and_pod_are_mapped_to_the_correct_entity_kinds():
    result = _map([_entry(_deployment()), _entry(_pod())])
    assert result.result is IngestionResult.ACCEPTED
    kinds = {entity.entity.entity_kind for entity in result.entities}
    assert kinds == {
        InfrastructureEntityKind.KUBERNETES_WORKLOAD,
        InfrastructureEntityKind.KUBERNETES_POD,
    }


# --- validation ------------------------------------------------------------------------------


def test_missing_metadata_name_rejects_the_source():
    document = _pod()
    del document["metadata"]["name"]
    result = _map([_entry(document, source_pointer="a.yaml")])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID
    assert result.diagnostics[0].source_pointer == "a.yaml:v1/Pod/checkout/<missing>"


def test_missing_metadata_namespace_on_a_namespaced_kind_rejects_the_source():
    document = _pod()
    del document["metadata"]["namespace"]
    result = _map([_entry(document)])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_out_of_scope_namespace_rejects_the_source_with_the_reused_snapshot_invalid_code():
    result = _map([_entry(_pod(namespace="other-namespace"))])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_namespace_object_not_in_declared_scope_rejects_the_source():
    namespace_doc = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "other"}}
    result = _map([_entry(namespace_doc)])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_namespace_object_in_declared_scope_is_valid_but_not_promoted_to_an_entity():
    namespace_doc = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": _NAMESPACE}}
    result = _map([_entry(namespace_doc)])
    assert result.result is IngestionResult.ACCEPTED
    assert result.entities == ()


def test_captured_resource_mode_requires_uid_and_resource_version():
    result = _map([_entry(_pod())], requires_capture_identity=True)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_captured_resource_mode_accepts_a_resource_with_uid_and_resource_version():
    document = _pod(uid="pod-uid", resource_version="42")
    result = _map([_entry(document)], requires_capture_identity=True)
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.entities) == 1


# --- within-bundle duplicates ------------------------------------------------------------------


def test_identical_duplicate_resources_across_files_merge_into_one_entity():
    document = _deployment()
    result = _map(
        [
            _entry(document, source_pointer="a.yaml"),
            _entry(dict(document), source_pointer="b.yaml"),
        ]
    )
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.entities) == 1
    assert result.entities[0].source_pointers == ("a.yaml", "b.yaml")


def test_conflicting_duplicate_resources_reject_the_source():
    first = _deployment(annotations={SERVICE_ID_ANNOTATION: "service:checkout"})
    second = _deployment()
    result = _map(
        [
            _entry(first, source_pointer="a.yaml"),
            _entry(second, source_pointer="b.yaml"),
        ]
    )
    assert result.result is IngestionResult.REJECTED_CONFLICT
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_CONFLICT


# --- label filtering --------------------------------------------------------------------------


def test_pod_labels_are_filtered_to_only_service_selector_needed_keys():
    pod = _pod(labels={"app": "checkout-api", "irrelevant": "value"})
    service = _service(selector={"app": "checkout-api"})
    result = _map([_entry(pod), _entry(service)])
    assert result.result is IngestionResult.ACCEPTED
    pod_entity = next(
        e
        for e in result.entities
        if e.entity.entity_kind is InfrastructureEntityKind.KUBERNETES_POD
    )
    assert pod_entity.projection["labels"] == {"app": "checkout-api"}
    # No Service entity is emitted by this slice - only its selector keys are read.
    assert all(
        e.entity.entity_kind is not InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE
        for e in result.entities
    )


def test_pod_with_no_matching_service_selector_retains_no_labels():
    pod = _pod(labels={"app": "checkout-api"})
    result = _map([_entry(pod)])
    pod_entity = result.entities[0]
    assert pod_entity.projection["labels"] == {}


# --- projection content ------------------------------------------------------------------------


def test_workload_projection_retains_owner_references_and_service_id_annotation():
    owner_refs = [
        {
            "apiVersion": "apps/v1",
            "kind": "ReplicaSet",
            "name": "checkout-api-1",
            "uid": "rs-uid",
            "controller": True,
        }
    ]
    document = _deployment(
        annotations={SERVICE_ID_ANNOTATION: "service:checkout"}, owner_references=owner_refs
    )
    result = _map([_entry(document)])
    projection = result.entities[0].projection
    assert projection["serviceIdAnnotation"] == "service:checkout"
    assert projection["ownerReferences"] == [
        {
            "apiVersion": "apps/v1",
            "kind": "ReplicaSet",
            "name": "checkout-api-1",
            "uid": "rs-uid",
            "controller": True,
        }
    ]
    assert "uid" not in projection
    assert "resourceVersion" not in projection


def test_pod_projection_excludes_uid_and_resource_version_but_retains_owner_reference_uid():
    owner_refs = [
        {
            "apiVersion": "apps/v1",
            "kind": "ReplicaSet",
            "name": "rs",
            "uid": "rs-uid",
            "controller": True,
        }
    ]
    document = _pod(uid="pod-own-uid", resource_version="7", owner_references=owner_refs)
    result = _map([_entry(document)], requires_capture_identity=True)
    projection = result.entities[0].projection
    assert "uid" not in projection
    assert "resourceVersion" not in projection
    assert projection["ownerReferences"][0]["uid"] == "rs-uid"


# --- ordering --------------------------------------------------------------------------------


def test_entities_are_ordered_by_logical_resource_id_deterministically():
    result_forward = _map([_entry(_deployment(name="b")), _entry(_deployment(name="a"))])
    result_reversed = _map([_entry(_deployment(name="a")), _entry(_deployment(name="b"))])
    forward_ids = [e.entity.id for e in result_forward.entities]
    reversed_ids = [e.entity.id for e in result_reversed.entities]
    assert forward_ids == reversed_ids
