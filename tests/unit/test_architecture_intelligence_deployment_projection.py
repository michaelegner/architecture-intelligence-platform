from app.architecture_intelligence.contracts import (
    DEPLOYMENT_RECONCILIATION_RULE_ID,
    DeploymentResolutionMethod,
    DeploymentResolutionStatus,
    LimitationCode,
    WorkloadKind,
)
from app.architecture_intelligence.deployment_projection import (
    CurrentKubernetesWorkload,
    WorkloadContribution,
    compute_deployment_claim_id,
    compute_deployment_group_key,
    compute_deployment_resolution_id,
    compute_service_workload_mapping_evidence_id,
    resolve_path_a,
    resolve_path_b,
)
from app.sources.service_workload_mapping import (
    ServiceWorkloadMappingDocument,
    ServiceWorkloadMappingEntry,
)

SNAPSHOT_ID = "aip:snapshot:v1:" + "a" * 64
CONTEXT_ID = "aip:observation-context:v1:" + "b" * 64


def _workload(
    workload_id="workload:deploy-1",
    kind="Deployment",
    namespace="checkout",
    name="checkout",
    contributions=(),
):
    return CurrentKubernetesWorkload(
        workload_id=workload_id,
        workload_kind=kind,
        namespace=namespace,
        name=name,
        contributions=contributions,
    )


def _service_lookup(services: dict[str, str]):
    return lambda service_id: services.get(service_id)


# ---------------------------------------------------------------------------------------------
# Id/key formula unit tests
# ---------------------------------------------------------------------------------------------


def test_compute_deployment_claim_id_is_deterministic_and_excludes_evidence_method():
    claim_id_1 = compute_deployment_claim_id(service_id="service:checkout", workload_id="w1")
    claim_id_2 = compute_deployment_claim_id(service_id="service:checkout", workload_id="w1")
    assert claim_id_1 == claim_id_2
    assert claim_id_1.startswith("aip:claim:v1:")


def test_compute_deployment_claim_id_differs_by_service_or_workload():
    base = compute_deployment_claim_id(service_id="service:checkout", workload_id="w1")
    different_service = compute_deployment_claim_id(service_id="service:other", workload_id="w1")
    different_workload = compute_deployment_claim_id(
        service_id="service:checkout", workload_id="w2"
    )
    assert len({base, different_service, different_workload}) == 3


def test_compute_deployment_group_key_workload_branch():
    assert compute_deployment_group_key(workload_id="w1") == "workload:w1"


def test_compute_deployment_group_key_mapping_branch_distinct_tuples():
    # §21.2: distinct tuples ("a", "b:c", "d") and ("a:b", "c", "d") must produce distinct keys -
    # exercises the canonical-JSON (not delimiter-concatenation) requirement directly.
    key_1 = compute_deployment_group_key(
        mapping_artifact_id="a", mapping_artifact_revision="b:c", mapping_id="d"
    )
    key_2 = compute_deployment_group_key(
        mapping_artifact_id="a:b", mapping_artifact_revision="c", mapping_id="d"
    )
    assert key_1 != key_2


def test_compute_deployment_resolution_id_deterministic_and_context_sensitive():
    key = compute_deployment_group_key(workload_id="w1")
    id_1 = compute_deployment_resolution_id(
        snapshot_id=SNAPSHOT_ID, context_id=CONTEXT_ID, group_key=key
    )
    id_2 = compute_deployment_resolution_id(
        snapshot_id=SNAPSHOT_ID, context_id=CONTEXT_ID, group_key=key
    )
    assert id_1 == id_2
    assert id_1.startswith("aip:deployment-resolution:v1:")
    other_snapshot = compute_deployment_resolution_id(
        snapshot_id="aip:snapshot:v1:" + "c" * 64, context_id=CONTEXT_ID, group_key=key
    )
    assert other_snapshot != id_1


def test_compute_service_workload_mapping_evidence_id_distinct_delimiter_tuples():
    id_1 = compute_service_workload_mapping_evidence_id(
        artifact_id="a", artifact_revision="b:c", content_digest="d", mapping_id="e"
    )
    id_2 = compute_service_workload_mapping_evidence_id(
        artifact_id="a:b", artifact_revision="c", content_digest="d", mapping_id="e"
    )
    assert id_1 != id_2
    assert id_1.startswith("urn:aip:service-workload-mapping-evidence:v1:")


def test_compute_service_workload_mapping_evidence_id_changes_with_content_digest():
    # §21.2: "mapping-content change changes reconciliation context/snapshot" - the digest-changes
    # -> evidence-id-changes primitive.
    id_1 = compute_service_workload_mapping_evidence_id(
        artifact_id="a", artifact_revision="rev", content_digest="digest-1", mapping_id="m"
    )
    id_2 = compute_service_workload_mapping_evidence_id(
        artifact_id="a", artifact_revision="rev", content_digest="digest-2", mapping_id="m"
    )
    assert id_1 != id_2


# ---------------------------------------------------------------------------------------------
# Path A (spec §21.1)
# ---------------------------------------------------------------------------------------------


def test_path_a_valid_annotation_for_each_supported_kind():
    workloads = [
        _workload(
            workload_id="w-deploy",
            kind="Deployment",
            contributions=(
                WorkloadContribution(annotation="service:checkout", evidence_refs=("ev1",)),
            ),
        ),
        _workload(
            workload_id="w-sts",
            kind="StatefulSet",
            contributions=(
                WorkloadContribution(annotation="service:checkout", evidence_refs=("ev2",)),
            ),
        ),
        _workload(
            workload_id="w-ds",
            kind="DaemonSet",
            contributions=(
                WorkloadContribution(annotation="service:checkout", evidence_refs=("ev3",)),
            ),
        ),
    ]
    result = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    assert len(result.resolutions) == 3
    assert len(result.claims) == 3
    for resolution in result.resolutions:
        assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
        assert resolution.service_id == "service:checkout"
        assert resolution.supporting_methods == [DeploymentResolutionMethod.RESOLVED_EXPLICIT]
        assert resolution.reconciliation_rule_id == DEPLOYMENT_RECONCILIATION_RULE_ID
    assert {r.workload.workload_kind for r in result.resolutions} == {
        WorkloadKind.DEPLOYMENT,
        WorkloadKind.STATEFULSET,
        WorkloadKind.DAEMONSET,
    }


def test_path_a_missing_annotation_produces_no_resolution():
    workloads = [
        _workload(contributions=(WorkloadContribution(annotation=None, evidence_refs=("ev1",)),))
    ]
    result = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_service_lookup({}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    assert result.resolutions == []
    assert result.claims == []


def test_path_a_annotation_naming_a_missing_service_is_unresolved():
    workloads = [
        _workload(
            contributions=(
                WorkloadContribution(annotation="service:ghost", evidence_refs=("ev1",)),
            )
        )
    ]
    result = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_service_lookup({}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.service_id is None
    assert resolution.candidate_service_ids == ["service:ghost"]
    assert resolution.claim_id is None
    assert resolution.limitation_codes == [LimitationCode.DEPLOYMENT_IDENTITY_UNRESOLVED]
    assert result.claims == []


def test_path_a_two_contributions_same_annotation_agree():
    workloads = [
        _workload(
            contributions=(
                WorkloadContribution(annotation="service:checkout", evidence_refs=("ev1",)),
                WorkloadContribution(annotation="service:checkout", evidence_refs=("ev2",)),
            )
        )
    ]
    result = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
    assert resolution.supporting_evidence_refs == ["ev1", "ev2"]


def test_path_a_two_contributions_different_annotations_conflict():
    workloads = [
        _workload(
            contributions=(
                WorkloadContribution(annotation="service:checkout", evidence_refs=("ev1",)),
                WorkloadContribution(annotation="service:other", evidence_refs=("ev2",)),
            )
        )
    ]
    result = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_service_lookup(
            {"service:checkout": "checkout", "service:other": "other"}
        ),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.CONFLICT
    assert resolution.candidate_service_ids == ["service:checkout", "service:other"]
    assert resolution.conflicting_evidence_refs == ["ev1", "ev2"]
    assert resolution.claim_id is None
    assert result.claims == []


def test_path_a_annotation_exact_case_requirement():
    # A differently-cased annotation is a distinct string, never folded to match.
    workloads = [
        _workload(
            contributions=(
                WorkloadContribution(annotation="service:Checkout", evidence_refs=("ev1",)),
            )
        )
    ]
    result = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.candidate_service_ids == ["service:Checkout"]


def test_path_a_annotation_similarity_only_is_never_fuzzy_matched():
    workloads = [
        _workload(
            contributions=(
                WorkloadContribution(annotation="service:checkout-v2", evidence_refs=("ev1",)),
            )
        )
    ]
    result = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.candidate_service_ids == ["service:checkout-v2"]


# ---------------------------------------------------------------------------------------------
# Path B (spec §21.2)
# ---------------------------------------------------------------------------------------------

CURRENT_SOURCE = ("checkout-cluster", "599e90a5-7ab8-426f-807f-92a65dcc8822")


def _mapping_document(
    entries, artifact_id="v0.5.0-service-workload-identities", revision="v1", digest="digest-1"
):
    return ServiceWorkloadMappingDocument(
        artifact_id=artifact_id,
        artifact_revision=revision,
        locator="mappings.yaml",
        content_digest=digest,
        entries=tuple(entries),
    )


def _mapping_entry(
    mapping_id="checkout-runtime",
    service_id="service:checkout",
    kubernetes_source_id="checkout-cluster",
    cluster_uid="599e90a5-7ab8-426f-807f-92a65dcc8822",
    api_group="apps",
    workload_kind="Deployment",
    namespace="checkout",
    name="checkout",
):
    return ServiceWorkloadMappingEntry(
        mapping_id=mapping_id,
        service_id=service_id,
        kubernetes_source_id=kubernetes_source_id,
        cluster_uid=cluster_uid,
        api_group=api_group,
        workload_kind=workload_kind,
        namespace=namespace,
        name=name,
    )


def _workload_resolver(workloads_by_entity_id: dict[str, CurrentKubernetesWorkload]):
    return lambda entity_id: workloads_by_entity_id.get(entity_id)


def test_path_b_valid_mapping_for_each_supported_kind():
    entries = [
        _mapping_entry(mapping_id="a", workload_kind="Deployment", name="deploy"),
        _mapping_entry(mapping_id="b", workload_kind="StatefulSet", name="sts"),
        _mapping_entry(mapping_id="c", workload_kind="DaemonSet", name="ds"),
    ]
    document = _mapping_document(entries)

    from app.sources.identity import kubernetes_logical_resource_id

    workloads_by_entity_id = {}
    for entry in entries:
        entity_id = kubernetes_logical_resource_id(
            cluster_uid=entry.cluster_uid,
            api_group=entry.api_group,
            kind=entry.workload_kind,
            namespace=entry.namespace,
            name=entry.name,
        )
        workloads_by_entity_id[entity_id] = _workload(
            workload_id=entity_id,
            kind=entry.workload_kind,
            namespace=entry.namespace,
            name=entry.name,
        )

    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=_workload_resolver(workloads_by_entity_id),
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    assert len(result.resolutions) == 3
    assert len(result.claims) == 3
    for resolution in result.resolutions:
        assert resolution.status == DeploymentResolutionStatus.RESOLVED_CONFIGURED
        assert resolution.supporting_methods == [DeploymentResolutionMethod.RESOLVED_CONFIGURED]


def test_path_b_mapping_to_missing_service_is_unresolved():
    entry = _mapping_entry()
    document = _mapping_document([entry])

    from app.sources.identity import kubernetes_logical_resource_id

    entity_id = kubernetes_logical_resource_id(
        cluster_uid=entry.cluster_uid,
        api_group=entry.api_group,
        kind=entry.workload_kind,
        namespace=entry.namespace,
        name=entry.name,
    )
    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=_workload_resolver({entity_id: _workload(workload_id=entity_id)}),
        lookup_service_name=_service_lookup({}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.workload is not None
    assert resolution.candidate_service_ids == ["service:checkout"]
    assert result.claims == []


def test_path_b_mapping_to_missing_workload_is_unresolved_with_null_workload():
    document = _mapping_document([_mapping_entry()])
    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=_workload_resolver({}),
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.workload is None
    assert result.claims == []


def test_path_b_wrong_configured_kubernetes_source_id_is_unresolved_with_null_workload():
    document = _mapping_document([_mapping_entry(kubernetes_source_id="other-cluster")])
    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=lambda entity_id: (_ for _ in ()).throw(
            AssertionError("resolve_workload must not be called for a non-current source")
        ),
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.workload is None


def test_path_b_wrong_cluster_uid_is_unresolved_with_null_workload():
    document = _mapping_document([_mapping_entry(cluster_uid="a-different-cluster-uid")])
    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=lambda entity_id: (_ for _ in ()).throw(
            AssertionError("resolve_workload must not be called for a non-current source")
        ),
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.workload is None


def test_path_b_same_names_different_namespaces_are_independent():
    from app.sources.identity import kubernetes_logical_resource_id

    entry_a = _mapping_entry(mapping_id="a", namespace="ns-a", service_id="service:a")
    entry_b = _mapping_entry(mapping_id="b", namespace="ns-b", service_id="service:b")
    document = _mapping_document([entry_a, entry_b])

    workloads = {}
    for entry in (entry_a, entry_b):
        entity_id = kubernetes_logical_resource_id(
            cluster_uid=entry.cluster_uid,
            api_group=entry.api_group,
            kind=entry.workload_kind,
            namespace=entry.namespace,
            name=entry.name,
        )
        workloads[entity_id] = _workload(workload_id=entity_id, namespace=entry.namespace)

    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=_workload_resolver(workloads),
        lookup_service_name=_service_lookup({"service:a": "a", "service:b": "b"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    assert len(result.resolutions) == 2
    assert {r.status for r in result.resolutions} == {
        DeploymentResolutionStatus.RESOLVED_CONFIGURED
    }
    assert {r.service_id for r in result.resolutions} == {"service:a", "service:b"}


def test_path_b_same_names_different_clusters_are_independent():
    from app.sources.identity import kubernetes_logical_resource_id

    entry_a = _mapping_entry(
        mapping_id="a",
        kubernetes_source_id="cluster-a",
        cluster_uid="00000000-0000-0000-0000-000000000001",
        service_id="service:a",
    )
    entry_b = _mapping_entry(
        mapping_id="b",
        kubernetes_source_id="cluster-b",
        cluster_uid="00000000-0000-0000-0000-000000000002",
        service_id="service:b",
    )
    document = _mapping_document([entry_a, entry_b])

    workloads = {}
    for entry in (entry_a, entry_b):
        entity_id = kubernetes_logical_resource_id(
            cluster_uid=entry.cluster_uid,
            api_group=entry.api_group,
            kind=entry.workload_kind,
            namespace=entry.namespace,
            name=entry.name,
        )
        workloads[entity_id] = _workload(workload_id=entity_id)

    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[
            ("cluster-a", "00000000-0000-0000-0000-000000000001"),
            ("cluster-b", "00000000-0000-0000-0000-000000000002"),
        ],
        resolve_workload=_workload_resolver(workloads),
        lookup_service_name=_service_lookup({"service:a": "a", "service:b": "b"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    assert len(result.resolutions) == 2
    assert {r.service_id for r in result.resolutions} == {"service:a", "service:b"}


def test_path_b_two_mappings_same_workload_different_services_conflict():
    from app.sources.identity import kubernetes_logical_resource_id

    entry_a = _mapping_entry(mapping_id="a", service_id="service:checkout")
    entry_b = _mapping_entry(mapping_id="b", service_id="service:other")
    document = _mapping_document([entry_a, entry_b])

    entity_id = kubernetes_logical_resource_id(
        cluster_uid=entry_a.cluster_uid,
        api_group=entry_a.api_group,
        kind=entry_a.workload_kind,
        namespace=entry_a.namespace,
        name=entry_a.name,
    )
    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=_workload_resolver({entity_id: _workload(workload_id=entity_id)}),
        lookup_service_name=_service_lookup(
            {"service:checkout": "checkout", "service:other": "other"}
        ),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.CONFLICT
    assert resolution.candidate_service_ids == ["service:checkout", "service:other"]
    assert result.claims == []


def test_path_b_evidence_id_reflects_artifact_identity_and_mapping_id():
    from app.sources.identity import kubernetes_logical_resource_id

    entry = _mapping_entry()
    document = _mapping_document([entry], artifact_id="art-1", revision="rev-1", digest="digest-1")
    entity_id = kubernetes_logical_resource_id(
        cluster_uid=entry.cluster_uid,
        api_group=entry.api_group,
        kind=entry.workload_kind,
        namespace=entry.namespace,
        name=entry.name,
    )
    result = resolve_path_b(
        documents=[document],
        configured_kubernetes_sources=[CURRENT_SOURCE],
        resolve_workload=_workload_resolver({entity_id: _workload(workload_id=entity_id)}),
        lookup_service_name=_service_lookup({"service:checkout": "checkout"}),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    [resolution] = result.resolutions
    expected_evidence_id = compute_service_workload_mapping_evidence_id(
        artifact_id="art-1",
        artifact_revision="rev-1",
        content_digest="digest-1",
        mapping_id="checkout-runtime",
    )
    assert resolution.supporting_evidence_refs == [expected_evidence_id]
