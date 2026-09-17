from app.sources.kubernetes_mapping import map_kubernetes_resources
from app.sources.kubernetes_owner_chain import resolve_owner_chains
from app.sources.model import DiagnosticCode, IngestionResult, KubernetesResourceEntry

_CLUSTER_UID = "independently-established-cluster-identity"
_NAMESPACE = "checkout"
_OTHER_NAMESPACE = "other"


def _entry(document: dict, *, source_pointer: str = "resources.yaml") -> KubernetesResourceEntry:
    return KubernetesResourceEntry(source_pointer=source_pointer, document=document)


def _owner_ref(
    *, api_version: str, kind: str, name: str, uid: str, controller: bool = True
) -> dict:
    return {
        "apiVersion": api_version,
        "kind": kind,
        "name": name,
        "uid": uid,
        "controller": controller,
    }


def _workload(
    kind: str, name: str, *, uid: str, namespace: str = _NAMESPACE, resource_version: str = "1"
) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": kind,
        "metadata": {
            "name": name,
            "namespace": namespace,
            "uid": uid,
            "resourceVersion": resource_version,
        },
    }


def _pod(
    name: str = "pod-1",
    *,
    uid: str = "pod-uid-1",
    namespace: str = _NAMESPACE,
    resource_version: str = "1",
    owner_references: list[dict] | None = None,
) -> dict:
    metadata = {
        "name": name,
        "namespace": namespace,
        "uid": uid,
        "resourceVersion": resource_version,
    }
    if owner_references is not None:
        metadata["ownerReferences"] = owner_references
    return {"apiVersion": "v1", "kind": "Pod", "metadata": metadata}


def _replica_set(
    name: str = "rs-1",
    *,
    uid: str = "rs-uid-1",
    namespace: str = _NAMESPACE,
    resource_version: str = "1",
    owner_references: list[dict] | None = None,
) -> dict:
    metadata = {
        "name": name,
        "namespace": namespace,
        "uid": uid,
        "resourceVersion": resource_version,
    }
    if owner_references is not None:
        metadata["ownerReferences"] = owner_references
    return {"apiVersion": "apps/v1", "kind": "ReplicaSet", "metadata": metadata}


def _map_with_entries(
    entries,
    *,
    requires_capture_identity: bool = True,
    scope_namespaces=(_NAMESPACE, _OTHER_NAMESPACE),
):
    result = map_kubernetes_resources(
        tuple(entries),
        cluster_uid=_CLUSTER_UID,
        requires_capture_identity=requires_capture_identity,
        scope_namespaces=tuple(scope_namespaces),
    )
    assert result.result in (IngestionResult.ACCEPTED, IngestionResult.ACCEPTED_WITH_LIMITATIONS), (
        result.diagnostics
    )
    return result.resources


def _map(
    documents,
    *,
    requires_capture_identity: bool = True,
    scope_namespaces=(_NAMESPACE, _OTHER_NAMESPACE),
):
    return _map_with_entries(
        (_entry(doc) for doc in documents),
        requires_capture_identity=requires_capture_identity,
        scope_namespaces=scope_namespaces,
    )


def _resolve(resources, *, requires_capture_identity: bool = True):
    return resolve_owner_chains(
        resources, cluster_uid=_CLUSTER_UID, requires_capture_identity=requires_capture_identity
    )


# --- accepted chains ---------------------------------------------------------------------------


def test_pod_to_statefulset_resolves():
    sts = _workload("StatefulSet", "sts-1", uid="sts-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="sts-uid-1")
        ]
    )
    resources = _map([sts, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED
    [chain] = result.resolved_chains
    assert len(chain.evidence_resource_logical_ids) == 2


def test_pod_to_daemonset_resolves():
    ds = _workload("DaemonSet", "ds-1", uid="ds-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="DaemonSet", name="ds-1", uid="ds-uid-1")
        ]
    )
    resources = _map([ds, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED
    [chain] = result.resolved_chains
    assert len(chain.evidence_resource_logical_ids) == 2


def test_pod_to_replicaset_to_deployment_resolves():
    dep = _workload("Deployment", "dep-1", uid="dep-uid-1")
    rs = _replica_set(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="Deployment", name="dep-1", uid="dep-uid-1")
        ]
    )
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-1", uid="rs-uid-1")
        ]
    )
    resources = _map([dep, rs, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED
    [chain] = result.resolved_chains
    assert len(chain.evidence_resource_logical_ids) == 3
    workload_by_id = {r.logical_id: r for r in resources if r.resource_kind == "Deployment"}
    assert chain.workload_logical_id in workload_by_id


# --- limitations (no claim, no rejection) -------------------------------------------------------


def test_pod_with_no_owner_reference_is_a_limitation():
    pod = _pod()
    resources = _map([pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_pod_with_only_a_non_controller_owner_reference_is_a_limitation():
    sts = _workload("StatefulSet", "sts-1", uid="sts-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(
                api_version="apps/v1",
                kind="StatefulSet",
                name="sts-1",
                uid="sts-uid-1",
                controller=False,
            )
        ]
    )
    resources = _map([sts, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_stale_uid_reference_is_a_limitation():
    sts = _workload("StatefulSet", "sts-1", uid="sts-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="a-stale-uid")
        ]
    )
    resources = _map([sts, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_cross_namespace_named_owner_does_not_resolve():
    sts = _workload("StatefulSet", "sts-1", uid="sts-uid-1", namespace=_OTHER_NAMESPACE)
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="sts-uid-1")
        ]
    )
    resources = _map([sts, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_unsupported_chain_shape_pod_to_deployment_directly_is_a_limitation():
    dep = _workload("Deployment", "dep-1", uid="dep-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="Deployment", name="dep-1", uid="dep-uid-1")
        ]
    )
    resources = _map([dep, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_replica_set_with_no_controller_owner_is_a_limitation_for_the_pod():
    rs = _replica_set()
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-1", uid="rs-uid-1")
        ]
    )
    resources = _map([rs, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_replica_set_owner_resolving_to_a_non_deployment_is_a_limitation():
    other_rs = _replica_set(name="rs-2", uid="rs-uid-2")
    rs = _replica_set(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-2", uid="rs-uid-2")
        ]
    )
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-1", uid="rs-uid-1")
        ]
    )
    resources = _map([other_rs, rs, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_declared_manifest_source_never_resolves_ownership():
    sts = _workload("StatefulSet", "sts-1", uid="sts-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="sts-uid-1")
        ]
    )
    resources = _map([sts, pod], requires_capture_identity=False)
    result = _resolve(resources, requires_capture_identity=False)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_UNRESOLVED


def test_declared_manifest_pod_with_multiple_controllers_still_rejects_the_source():
    """Review round (PR #202): the multiple-controllers check must run before the
    declaration-only gate - an earlier fix reordered these and silently downgraded this case to
    an ACCEPTED_WITH_LIMITATIONS/K8S_OWNER_UNRESOLVED limitation instead of rejecting."""
    sts = _workload("StatefulSet", "sts-1", uid="sts-uid-1")
    ds = _workload("DaemonSet", "ds-1", uid="ds-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="sts-uid-1"),
            _owner_ref(api_version="apps/v1", kind="DaemonSet", name="ds-1", uid="ds-uid-1"),
        ]
    )
    resources = _map([sts, ds, pod], requires_capture_identity=False)
    result = _resolve(resources, requires_capture_identity=False)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_INVALID


def test_standalone_captured_pod_with_no_owner_is_a_limitation_not_a_new_workload():
    pod = _pod()
    resources = _map([pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_chains == ()


# --- rejections (whole source discarded) --------------------------------------------------------


def test_pod_with_multiple_controller_owner_references_rejects_the_source():
    sts = _workload("StatefulSet", "sts-1", uid="sts-uid-1")
    ds = _workload("DaemonSet", "ds-1", uid="ds-uid-1")
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="sts-uid-1"),
            _owner_ref(api_version="apps/v1", kind="DaemonSet", name="ds-1", uid="ds-uid-1"),
        ]
    )
    resources = _map([sts, ds, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_INVALID


def test_replica_set_with_multiple_controller_owner_references_rejects_the_source():
    dep = _workload("Deployment", "dep-1", uid="dep-uid-1")
    ds = _workload("DaemonSet", "ds-1", uid="ds-uid-1")
    rs = _replica_set(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="Deployment", name="dep-1", uid="dep-uid-1"),
            _owner_ref(api_version="apps/v1", kind="DaemonSet", name="ds-1", uid="ds-uid-1"),
        ]
    )
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-1", uid="rs-uid-1")
        ]
    )
    resources = _map([dep, ds, rs, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_INVALID


def test_self_referencing_replica_set_is_a_cycle_and_rejects_the_source():
    rs = _replica_set(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-1", uid="rs-uid-1")
        ]
    )
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-1", uid="rs-uid-1")
        ]
    )
    resources = _map([rs, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_INVALID


def test_a_multi_resource_cycle_beyond_two_hops_rejects_the_source():
    """Review round (PR #202): Pod -> ReplicaSet A -> ReplicaSet B -> ReplicaSet A is a real cycle
    that only manifests on the *third* hop - an earlier version of this module stopped following
    references after two hops and misclassified this as an ordinary "unsupported chain" limitation
    instead of rejecting per §7.3's own distinct "cyclic references" outcome.
    """
    rs_a = _replica_set(
        name="rs-a",
        uid="rs-uid-a",
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-b", uid="rs-uid-b")
        ],
    )
    rs_b = _replica_set(
        name="rs-b",
        uid="rs-uid-b",
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-a", uid="rs-uid-a")
        ],
    )
    pod = _pod(
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="ReplicaSet", name="rs-a", uid="rs-uid-a")
        ]
    )
    resources = _map([rs_a, rs_b, pod])
    result = _resolve(resources)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.resolved_chains == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_OWNER_INVALID


def test_diagnostics_carry_a_real_file_source_pointer_not_the_logical_id_hash():
    """Review round (PR #202): §10 requires diagnostics to carry source pointers, not only a
    resource id hash an operator can't trace back to a YAML file."""
    pod = _pod()
    resources = _map_with_entries([_entry(pod, source_pointer="pods.yaml")])
    result = _resolve(resources)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    pointer = result.diagnostics[0].source_pointer
    assert pointer.startswith("pods.yaml:")
    assert "urn:aip:k8s-resource:" not in pointer


def test_multiple_duplicate_source_pointers_are_all_preserved_in_the_diagnostic():
    """An identical-duplicate Pod merged across two files (I2 §5/§6) must not lose either
    contributing file's pointer when its ownership diagnostic is built."""
    pod = _pod()
    resources = _map_with_entries(
        [_entry(pod, source_pointer="a.yaml"), _entry(pod, source_pointer="b.yaml")]
    )
    result = _resolve(resources)
    pointer = result.diagnostics[0].source_pointer
    assert pointer.startswith("a.yaml,b.yaml:")
