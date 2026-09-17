from app.sources.kubernetes_mapping import map_kubernetes_resources
from app.sources.kubernetes_owner_chain import resolve_owner_chains
from app.sources.kubernetes_service_selection import resolve_service_selections
from app.sources.model import DiagnosticCode, IngestionResult, KubernetesResourceEntry

_CLUSTER_UID = "independently-established-cluster-identity"
_NAMESPACE = "checkout"
_OTHER_NAMESPACE = "other"


def _entry(document: dict, *, source_pointer: str = "resources.yaml") -> KubernetesResourceEntry:
    return KubernetesResourceEntry(source_pointer=source_pointer, document=document)


def _owner_ref(*, api_version: str, kind: str, name: str, uid: str) -> dict:
    return {"apiVersion": api_version, "kind": kind, "name": name, "uid": uid, "controller": True}


def _statefulset(name: str, *, uid: str, namespace: str = _NAMESPACE) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": {"name": name, "namespace": namespace, "uid": uid, "resourceVersion": "1"},
    }


def _pod(
    name: str,
    *,
    uid: str,
    namespace: str = _NAMESPACE,
    labels: dict | None = None,
    owner_references: list[dict] | None = None,
) -> dict:
    metadata = {"name": name, "namespace": namespace, "uid": uid, "resourceVersion": "1"}
    if labels is not None:
        metadata["labels"] = labels
    if owner_references is not None:
        metadata["ownerReferences"] = owner_references
    return {"apiVersion": "v1", "kind": "Pod", "metadata": metadata}


def _service(
    name: str,
    *,
    uid: str,
    namespace: str = _NAMESPACE,
    selector: dict | None = None,
    service_type: str | None = None,
) -> dict:
    document = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": namespace, "uid": uid, "resourceVersion": "1"},
    }
    spec: dict = {}
    if selector is not None:
        spec["selector"] = selector
    if service_type is not None:
        spec["type"] = service_type
    if spec:
        document["spec"] = spec
    return document


def _map(documents, *, scope_namespaces=(_NAMESPACE, _OTHER_NAMESPACE)):
    entries = tuple(_entry(doc) for doc in documents)
    result = map_kubernetes_resources(
        entries,
        cluster_uid=_CLUSTER_UID,
        requires_capture_identity=True,
        scope_namespaces=tuple(scope_namespaces),
    )
    assert result.result in (IngestionResult.ACCEPTED, IngestionResult.ACCEPTED_WITH_LIMITATIONS), (
        result.diagnostics
    )
    return result.resources


def _resolve_ownerships(resources):
    result = resolve_owner_chains(
        resources, cluster_uid=_CLUSTER_UID, requires_capture_identity=True
    )
    assert result.result in (IngestionResult.ACCEPTED, IngestionResult.ACCEPTED_WITH_LIMITATIONS)
    return result.resolved_chains


def _resolve(resources, ownerships):
    return resolve_service_selections(resources, ownerships)


_STANDARD_OWNER_REF = [
    _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="sts-uid-1")
]


# --- matching / grouping -------------------------------------------------------------------------


def test_one_pod_one_workload_resolves_one_relation_with_unioned_evidence():
    sts = _statefulset("sts-1", uid="sts-uid-1")
    pod = _pod("pod-1", uid="pod-uid-1", labels={"app": "x"}, owner_references=_STANDARD_OWNER_REF)
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"})
    resources = _map([sts, pod, svc])
    ownerships = _resolve_ownerships(resources)
    result = _resolve(resources, ownerships)
    assert result.result is IngestionResult.ACCEPTED
    [selection] = result.resolved_selections
    assert len(selection.evidence_resource_logical_ids) == 3  # service + pod + workload


def test_many_pods_in_one_workload_yield_one_relation_with_unioned_evidence():
    sts = _statefulset("sts-1", uid="sts-uid-1")
    pod_a = _pod(
        "pod-a", uid="pod-uid-a", labels={"app": "x"}, owner_references=_STANDARD_OWNER_REF
    )
    pod_b = _pod(
        "pod-b", uid="pod-uid-b", labels={"app": "x"}, owner_references=_STANDARD_OWNER_REF
    )
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"})
    resources = _map([sts, pod_a, pod_b, svc])
    ownerships = _resolve_ownerships(resources)
    result = _resolve(resources, ownerships)
    assert result.result is IngestionResult.ACCEPTED
    [selection] = result.resolved_selections
    # service + workload + 2 pods = 4 distinct evidence-bearing resources.
    assert len(selection.evidence_resource_logical_ids) == 4


def test_many_resolved_workloads_yield_distinct_relations():
    sts_a = _statefulset("sts-a", uid="sts-uid-a")
    sts_b = _statefulset("sts-b", uid="sts-uid-b")
    pod_a = _pod(
        "pod-a",
        uid="pod-uid-a",
        labels={"app": "x"},
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-a", uid="sts-uid-a")
        ],
    )
    pod_b = _pod(
        "pod-b",
        uid="pod-uid-b",
        labels={"app": "x"},
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-b", uid="sts-uid-b")
        ],
    )
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"})
    resources = _map([sts_a, sts_b, pod_a, pod_b, svc])
    ownerships = _resolve_ownerships(resources)
    result = _resolve(resources, ownerships)
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resolved_selections) == 2
    workloads = {s.workload_logical_id for s in result.resolved_selections}
    assert len(workloads) == 2


def test_pod_in_a_different_namespace_does_not_match():
    sts = _statefulset("sts-1", uid="sts-uid-1", namespace=_OTHER_NAMESPACE)
    pod = _pod(
        "pod-1",
        uid="pod-uid-1",
        namespace=_OTHER_NAMESPACE,
        labels={"app": "x"},
        owner_references=[
            _owner_ref(api_version="apps/v1", kind="StatefulSet", name="sts-1", uid="sts-uid-1")
        ],
    )
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"})
    resources = _map([sts, pod, svc])
    ownerships = _resolve_ownerships(resources)
    result = _resolve(resources, ownerships)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_selections == ()
    assert result.diagnostics[0].code is DiagnosticCode.NO_QUALIFIED_POD_MATCH


# --- limitations -----------------------------------------------------------------------------


def test_no_matching_pod_at_all_is_a_limitation():
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"})
    resources = _map([svc])
    ownerships = _resolve_ownerships(resources)
    result = _resolve(resources, ownerships)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_selections == ()
    assert result.diagnostics[0].code is DiagnosticCode.NO_QUALIFIED_POD_MATCH


def test_a_matching_pod_with_unresolved_ownership_is_a_limitation_and_does_not_block_others():
    sts = _statefulset("sts-1", uid="sts-uid-1")
    resolved_pod = _pod(
        "pod-resolved", uid="pod-uid-1", labels={"app": "x"}, owner_references=_STANDARD_OWNER_REF
    )
    unresolved_pod = _pod("pod-unresolved", uid="pod-uid-2", labels={"app": "x"})
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"})
    resources = _map([sts, resolved_pod, unresolved_pod, svc])
    ownerships = _resolve_ownerships(resources)
    result = _resolve(resources, ownerships)
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    # The proven relation is still emitted...
    assert len(result.resolved_selections) == 1
    # ...alongside a limitation for the unresolved Pod - neither suppresses the other.
    assert any(d.code is DiagnosticCode.NO_QUALIFIED_POD_MATCH for d in result.diagnostics)


def test_declaration_only_source_has_no_resolved_ownerships_so_every_match_is_unresolved():
    sts = _statefulset("sts-1", uid="sts-uid-1")
    pod = _pod("pod-1", uid="pod-uid-1", labels={"app": "x"}, owner_references=_STANDARD_OWNER_REF)
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"})
    resources = _map([sts, pod, svc])
    # No ResolvedOwnership results at all - as a DECLARED_MANIFEST source's owner-chain resolution
    # always produces.
    result = _resolve(resources, ())
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_selections == ()
    assert result.diagnostics[0].code is DiagnosticCode.NO_QUALIFIED_POD_MATCH


# --- no-op cases -------------------------------------------------------------------------------


def test_absent_selector_emits_nothing():
    svc = _service("svc-1", uid="svc-uid-1")
    resources = _map([svc])
    result = _resolve(resources, ())
    assert result.result is IngestionResult.ACCEPTED
    assert result.resolved_selections == ()
    assert result.diagnostics == ()


def test_empty_selector_emits_nothing():
    svc = _service("svc-1", uid="svc-uid-1", selector={})
    resources = _map([svc])
    result = _resolve(resources, ())
    assert result.result is IngestionResult.ACCEPTED
    assert result.resolved_selections == ()
    assert result.diagnostics == ()


def test_external_name_service_emits_nothing_even_with_a_matching_selector():
    sts = _statefulset("sts-1", uid="sts-uid-1")
    pod = _pod("pod-1", uid="pod-uid-1", labels={"app": "x"}, owner_references=_STANDARD_OWNER_REF)
    svc = _service("svc-1", uid="svc-uid-1", selector={"app": "x"}, service_type="ExternalName")
    resources = _map([sts, pod, svc])
    ownerships = _resolve_ownerships(resources)
    result = _resolve(resources, ownerships)
    assert result.result is IngestionResult.ACCEPTED
    assert result.resolved_selections == ()
    assert result.diagnostics == ()
