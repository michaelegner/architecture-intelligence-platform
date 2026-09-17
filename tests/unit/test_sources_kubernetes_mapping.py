from app.canonical.infrastructure import InfrastructureEntityKind, InfrastructurePort
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


# --- review round: all admitted resources participate in digest/duplicate coverage, not just
# entity-promoted kinds (I2 §6/§5, PR #200 review) --------------------------------------------


def test_non_entity_admitted_kinds_are_included_in_resources_with_no_entity():
    """Namespace and ReplicaSet are the two admitted kinds §7.1 keeps permanently unpromoted -
    Service/Ingress moved out of this test once slice 3b promoted them (I2 §12 slice 3b)."""
    namespace_doc = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": _NAMESPACE}}
    replica_set_doc = {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {"name": "checkout-api-1", "namespace": _NAMESPACE},
    }
    result = _map([_entry(namespace_doc), _entry(replica_set_doc)])
    assert result.result is IngestionResult.ACCEPTED
    assert result.entities == ()
    assert len(result.resources) == 2
    assert all(resource.entity is None for resource in result.resources)


def test_service_selector_value_change_changes_the_resource_semantic_digest():
    first = _map([_entry(_service(selector={"app": "checkout-api"}))])
    second = _map([_entry(_service(selector={"app": "different-value"}))])
    [service_a] = first.resources
    [service_b] = second.resources
    assert service_a.resource_semantic_digest != service_b.resource_semantic_digest


def test_service_projection_retains_selector_values_type_and_sorted_ports():
    service = _service(selector={"app": "checkout-api", "tier": "backend"})
    service["spec"]["type"] = "ClusterIP"
    service["spec"]["ports"] = [
        {"protocol": "UDP", "port": 9090},
        {"name": "http", "port": 8080},
    ]
    result = _map([_entry(service)])
    projection = result.resources[0].projection
    assert projection["selector"] == {"app": "checkout-api", "tier": "backend"}
    assert projection["serviceType"] == "ClusterIP"
    assert projection["ports"] == [
        {"name": None, "protocol": "UDP", "port": 9090},
        {"name": "http", "protocol": "TCP", "port": 8080},
    ]


def test_ingress_projection_retains_rules_and_backend_service_refs():
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": "checkout-ingress", "namespace": _NAMESPACE},
        "spec": {
            "rules": [
                {
                    "host": "checkout.example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/api",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {"name": "checkout-svc", "port": {"number": 80}}
                                },
                            }
                        ]
                    },
                }
            ]
        },
    }
    result = _map([_entry(ingress)])
    assert result.result is IngestionResult.ACCEPTED
    projection = result.resources[0].projection
    assert projection["rules"] == [
        {
            "host": "checkout.example.com",
            "paths": [
                {
                    "path": "/api",
                    "pathType": "Prefix",
                    "backend": {
                        "serviceName": "checkout-svc",
                        "servicePortName": None,
                        "servicePortNumber": 80,
                    },
                }
            ],
        }
    ]


def test_malformed_ingress_backend_rejects_the_source():
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": "checkout-ingress", "namespace": _NAMESPACE},
        "spec": {"defaultBackend": {"service": {"name": "checkout-svc"}}},
    }
    result = _map([_entry(ingress)])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_a_resource_backend_accepts_with_a_distinct_projection_marker():
    """Review-of-§7.5 prerequisite fix (slice 4c): a backend naming `resource` instead of
    `service` is "unsupported", not malformed - it must not reject the source."""
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": "checkout-ingress", "namespace": _NAMESPACE},
        "spec": {
            "defaultBackend": {
                "resource": {"apiGroup": "k8s.example.com", "kind": "StorageBucket", "name": "x"}
            }
        },
    }
    result = _map([_entry(ingress)])
    assert result.result is IngestionResult.ACCEPTED
    [mapped] = result.entities
    assert mapped.projection["defaultBackend"] == {"resourceBackend": True}


def test_a_backend_with_neither_service_nor_resource_still_rejects_the_source():
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": "checkout-ingress", "namespace": _NAMESPACE},
        "spec": {"defaultBackend": {}},
    }
    result = _map([_entry(ingress)])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_duplicate_service_with_conflicting_selector_rejects_the_source():
    first = _service(selector={"app": "checkout-api"})
    second = _service(selector={"app": "different"})
    result = _map([_entry(first, source_pointer="a.yaml"), _entry(second, source_pointer="b.yaml")])
    assert result.result is IngestionResult.REJECTED_CONFLICT
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_CONFLICT


def test_identical_duplicate_namespace_across_files_merges_source_pointers():
    namespace_doc = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": _NAMESPACE}}
    result = _map(
        [
            _entry(dict(namespace_doc), source_pointer="a.yaml"),
            _entry(dict(namespace_doc), source_pointer="b.yaml"),
        ]
    )
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resources) == 1
    assert result.resources[0].source_pointers == ("a.yaml", "b.yaml")


def test_captured_resources_with_differing_uid_under_one_logical_id_conflict():
    first = _pod(uid="uid-a", resource_version="1")
    second = _pod(uid="uid-b", resource_version="1")
    result = _map(
        [_entry(first, source_pointer="a.yaml"), _entry(second, source_pointer="b.yaml")],
        requires_capture_identity=True,
    )
    assert result.result is IngestionResult.REJECTED_CONFLICT
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_CONFLICT


def test_captured_resources_with_same_uid_and_differing_resource_version_merge():
    first = _pod(uid="uid-a", resource_version="1")
    second = _pod(uid="uid-a", resource_version="2")
    result = _map(
        [_entry(first, source_pointer="a.yaml"), _entry(second, source_pointer="b.yaml")],
        requires_capture_identity=True,
    )
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resources) == 1
    assert result.resources[0].captured_uid == "uid-a"


def test_declared_manifest_mode_never_sets_captured_uid():
    result = _map([_entry(_pod())])
    assert result.resources[0].captured_uid is None


def test_owner_reference_with_non_boolean_controller_flag_rejects_the_source():
    owner_refs = [
        {
            "apiVersion": "apps/v1",
            "kind": "ReplicaSet",
            "name": "rs",
            "uid": "rs-uid",
            "controller": "false",
        }
    ]
    result = _map([_entry(_deployment(owner_references=owner_refs))])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_owner_reference_with_a_non_object_entry_rejects_the_source():
    result = _map([_entry(_deployment(owner_references=[42]))])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_owner_reference_missing_a_required_field_rejects_the_source():
    owner_refs = [{"apiVersion": "apps/v1", "kind": "ReplicaSet", "name": "rs"}]  # no uid
    result = _map([_entry(_deployment(owner_references=owner_refs))])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_non_mapping_service_selector_rejects_the_source():
    service = _service(selector={"app": "checkout-api"})
    service["spec"]["selector"] = ["not", "a", "mapping"]
    result = _map([_entry(service)])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_non_mapping_pod_labels_rejects_the_source():
    pod = _pod()
    pod["metadata"]["labels"] = ["not", "a", "mapping"]
    result = _map([_entry(pod)])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


# --- review round (2nd pass): malformed shapes must reject deterministically, never raise -------


def test_service_with_a_non_mapping_spec_rejects_the_source_without_raising():
    service = _service(selector={"app": "checkout-api"})
    service["spec"] = ["not", "a", "mapping"]
    result = _map([_entry(service)])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID


def test_non_mapping_metadata_rejects_the_source_without_raising():
    document = {"apiVersion": "v1", "kind": "Pod", "metadata": ["not", "a", "mapping"]}
    result = _map([_entry(document, source_pointer="a.yaml")])
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_RESOURCE_INVALID
    assert result.diagnostics[0].source_pointer == "a.yaml:v1/Pod//<missing>"


# --- review round (2nd pass): captured UID replacement must invalidate source-level replay -----


def test_captured_uid_replacement_changes_the_resource_semantic_digest_input():
    """`resource_semantic_digest` itself stays UID-free (§7.1) - the digest INPUT the adapter
    folds `captured_uid` into is a separate, adapter-level concern, not this module's job. This
    test only pins `MappedResource.captured_uid` itself changing, which is what the adapter reads.
    """
    first = _map([_entry(_pod(uid="uid-a", resource_version="1"))], requires_capture_identity=True)
    second = _map([_entry(_pod(uid="uid-b", resource_version="1"))], requires_capture_identity=True)
    assert first.resources[0].captured_uid == "uid-a"
    assert second.resources[0].captured_uid == "uid-b"
    # The allowlisted projection - and therefore resource_semantic_digest - is unaffected by a
    # UID-only change, exactly as §7.1 requires.
    assert (
        first.resources[0].resource_semantic_digest == second.resources[0].resource_semantic_digest
    )


# --- slice 3b: Service/Ingress entity promotion --------------------------------------------


def test_service_is_promoted_with_service_type_and_sorted_ports():
    service = _service(selector={"app": "checkout-api"})
    service["spec"]["type"] = "ClusterIP"
    service["spec"]["ports"] = [
        {"protocol": "UDP", "port": 9090},
        {"name": "http", "port": 8080},
    ]
    result = _map([_entry(service)])
    assert result.result is IngestionResult.ACCEPTED
    [mapped] = result.entities
    assert mapped.entity.entity_kind is InfrastructureEntityKind.KUBERNETES_NETWORK_SERVICE
    assert mapped.entity.service_type == "ClusterIP"
    assert mapped.entity.ports == [
        InfrastructurePort(name=None, protocol="UDP", port=9090),
        InfrastructurePort(name="http", protocol="TCP", port=8080),
    ]
    # The entity's own fields are exactly the hashed projection's own values - never re-derived.
    assert mapped.entity.service_type == mapped.projection["serviceType"]
    assert [p.model_dump() for p in mapped.entity.ports] == mapped.projection["ports"]


def test_service_with_no_declared_type_or_ports_promotes_without_fabricated_defaults():
    service = _service(selector={"app": "checkout-api"})
    result = _map([_entry(service)])
    [mapped] = result.entities
    assert mapped.entity.service_type is None
    assert mapped.entity.ports == []


def test_ingress_is_promoted_with_no_additional_fields():
    ingress = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": "checkout-ingress", "namespace": _NAMESPACE},
    }
    result = _map([_entry(ingress)])
    assert result.result is IngestionResult.ACCEPTED
    [mapped] = result.entities
    assert mapped.entity.entity_kind is InfrastructureEntityKind.KUBERNETES_INGRESS
    assert mapped.entity.service_type is None
    assert mapped.entity.ports == []


def test_namespace_and_replica_set_remain_unpromoted_alongside_promoted_kinds():
    namespace_doc = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": _NAMESPACE}}
    replica_set_doc = {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {"name": "checkout-api-1", "namespace": _NAMESPACE},
    }
    result = _map(
        [_entry(_deployment()), _entry(namespace_doc), _entry(replica_set_doc)],
    )
    assert result.result is IngestionResult.ACCEPTED
    entity_kinds = {e.entity.entity_kind for e in result.entities}
    assert entity_kinds == {InfrastructureEntityKind.KUBERNETES_WORKLOAD}
    assert len(result.resources) == 3
