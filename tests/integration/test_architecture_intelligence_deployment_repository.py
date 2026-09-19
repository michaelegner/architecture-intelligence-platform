"""v0.5.0 I3 slice 3 end-to-end: real I2 Kubernetes facts and a real configured mapping artifact,
read back through `app.architecture_intelligence.deployment_repository` and reduced by
`app.architecture_intelligence.deployment_projection.resolve_path_a`/`resolve_path_b` - proving the
whole Path A/B pipeline against a real Neo4j instance, not just the pure-function fakes
`test_architecture_intelligence_deployment_projection.py` already covers.
"""

import hashlib

import yaml

from app.architecture_intelligence import deployment_repository
from app.architecture_intelligence.contracts import DeploymentResolutionStatus
from app.architecture_intelligence.deployment_projection import resolve_path_a, resolve_path_b
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.graph.importer import import_kubernetes_source
from app.graph.schema import ensure_schema
from app.sources.model import KubernetesSourceConfig
from app.sources.service_workload_mapping import load_service_workload_mapping

DATABASE = "neo4j"
SNAPSHOT_ID = "aip:snapshot:v1:" + "a" * 64
CONTEXT_ID = "aip:observation-context:v1:" + "b" * 64
EXPECTED_RESOURCE_TYPES = frozenset(
    {
        "v1/Namespace",
        "v1/Pod",
        "v1/Service",
        "apps/v1/Deployment",
        "apps/v1/StatefulSet",
        "apps/v1/DaemonSet",
        "apps/v1/ReplicaSet",
        "networking.k8s.io/v1/Ingress",
    }
)


def _deployment(name: str, namespace: str, uid: str, *, annotations: dict | None = None) -> dict:
    metadata = {"name": name, "namespace": namespace, "uid": uid, "resourceVersion": "1"}
    if annotations:
        metadata["annotations"] = annotations
    return {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": metadata}


def _write_kubernetes_bundle(
    root,
    *,
    source_id: str,
    scope_id: str,
    cluster_uid: str,
    namespaces: list[str],
    resources: list[dict],
) -> KubernetesSourceConfig:
    root.mkdir(parents=True, exist_ok=True)
    resource_bytes = yaml.safe_dump_all(resources).encode()
    (root / "resources.yaml").write_bytes(resource_bytes)
    envelope = {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": f"{source_id}-snapshot",
            "revision": f"{source_id}-revision",
            "producer": "aip-kubernetes-capture-agent",
            "capturedAt": "2026-09-19T10:00:00Z",
        },
        "source": {
            "configuredSourceId": source_id,
            "configuredScopeId": scope_id,
            "clusterUid": cluster_uid,
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {
            "namespaces": sorted(namespaces),
            "resourceTypes": sorted(EXPECTED_RESOURCE_TYPES),
        },
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": f"{source_id}-authority",
            "expectedPriorInventoryRevision": None,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}],
    }
    (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
    return KubernetesSourceConfig(
        id=source_id,
        root=root,
        envelope_relative_path="envelope.yaml",
        configured_scope_id=scope_id,
        cluster_uid=cluster_uid,
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-kubernetes-capture-agent",
        authority_record=f"{source_id}-authority",
    )


def _reset_graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)


def _create_service(driver, *, service_id: str, name: str):
    with driver.session(database=DATABASE) as session:
        session.run(
            "MERGE (s:Service {id: $id}) SET s.name = $name, s.version = '1'",
            id=service_id,
            name=name,
        )


def _create_observed_only_service(driver, *, service_id: str, name: str):
    with driver.session(database=DATABASE) as session:
        session.run(
            "MERGE (s:Service {id: $id}) SET s.name = $name, s.discovery_status = 'OBSERVED_ONLY'",
            id=service_id,
            name=name,
        )


def test_path_a_resolves_a_real_annotated_workload_end_to_end(driver, tmp_path):
    _reset_graph(driver)
    _create_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-a-source",
        scope_id="i3-path-a-scope",
        cluster_uid="i3-path-a-cluster",
        namespaces=["checkout"],
        resources=[
            _deployment(
                "checkout-api",
                "checkout",
                "deploy-uid-path-a",
                annotations={"architecture-intelligence.io/service-id": "service:checkout"},
            )
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    with driver.session(database=DATABASE) as session:
        workloads = deployment_repository.iter_current_kubernetes_workloads(session)
        result = resolve_path_a(
            workloads=workloads,
            lookup_service_name=lambda service_id: deployment_repository.read_service_name(
                session, service_id=service_id
            ),
            snapshot_id=SNAPSHOT_ID,
            context_id=CONTEXT_ID,
        )

    assert len(result.resolutions) == 1
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
    assert resolution.service_id == "service:checkout"
    assert resolution.workload.name == "checkout-api"
    [claim] = result.claims
    assert claim.claim_id == resolution.claim_id


def test_path_a_annotation_naming_a_missing_service_is_unresolved_end_to_end(driver, tmp_path):
    _reset_graph(driver)

    config = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-a-unresolved-source",
        scope_id="i3-path-a-unresolved-scope",
        cluster_uid="i3-path-a-unresolved-cluster",
        namespaces=["checkout"],
        resources=[
            _deployment(
                "checkout-api",
                "checkout",
                "deploy-uid-path-a-unresolved",
                annotations={"architecture-intelligence.io/service-id": "service:ghost"},
            )
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    with driver.session(database=DATABASE) as session:
        workloads = deployment_repository.iter_current_kubernetes_workloads(session)
        result = resolve_path_a(
            workloads=workloads,
            lookup_service_name=lambda service_id: deployment_repository.read_service_name(
                session, service_id=service_id
            ),
            snapshot_id=SNAPSHOT_ID,
            context_id=CONTEXT_ID,
        )

    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.candidate_service_ids == ["service:ghost"]
    assert result.claims == []


def test_path_a_annotation_naming_an_observed_only_service_is_unresolved_end_to_end(
    driver, tmp_path
):
    # PR #215 review (spec §3/§7/§29): a telemetry-minted OBSERVED_ONLY Service stub must never
    # qualify deployment identity - treated identically to a genuinely missing Service.
    _reset_graph(driver)
    _create_observed_only_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-a-observed-only-source",
        scope_id="i3-path-a-observed-only-scope",
        cluster_uid="i3-path-a-observed-only-cluster",
        namespaces=["checkout"],
        resources=[
            _deployment(
                "checkout-api",
                "checkout",
                "deploy-uid-path-a-observed-only",
                annotations={"architecture-intelligence.io/service-id": "service:checkout"},
            )
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    with driver.session(database=DATABASE) as session:
        workloads = deployment_repository.iter_current_kubernetes_workloads(session)
        result = resolve_path_a(
            workloads=workloads,
            lookup_service_name=lambda service_id: deployment_repository.read_service_name(
                session, service_id=service_id
            ),
            snapshot_id=SNAPSHOT_ID,
            context_id=CONTEXT_ID,
        )

    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.candidate_service_ids == ["service:checkout"]
    assert result.claims == []


def test_path_b_resolves_a_real_configured_mapping_end_to_end(driver, tmp_path):
    _reset_graph(driver)
    _create_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path / "cluster",
        source_id="i3-path-b-source",
        scope_id="i3-path-b-scope",
        cluster_uid="i3-path-b-cluster-uid",
        namespaces=["checkout"],
        resources=[_deployment("checkout-api", "checkout", "deploy-uid-path-b")],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "aip.dev/v1",
                "kind": "ServiceWorkloadIdentityMappings",
                "metadata": {"id": "i3-path-b-mappings", "revision": "v1"},
                "mappings": [
                    {
                        "mappingId": "checkout-runtime",
                        "serviceId": "service:checkout",
                        "kubernetesSourceId": "i3-path-b-source",
                        "clusterUid": "i3-path-b-cluster-uid",
                        "workload": {
                            "apiGroup": "apps",
                            "kind": "Deployment",
                            "namespace": "checkout",
                            "name": "checkout-api",
                        },
                    }
                ],
            }
        )
    )
    document, diagnostics = load_service_workload_mapping(mapping_path)
    assert diagnostics == ()

    with driver.session(database=DATABASE) as session:
        result = resolve_path_b(
            document=document,
            configured_kubernetes_sources=[("i3-path-b-source", "i3-path-b-cluster-uid")],
            resolve_workload=lambda entity_id: (
                deployment_repository.read_current_kubernetes_workload(session, entity_id=entity_id)
            ),
            lookup_service_name=lambda service_id: deployment_repository.read_service_name(
                session, service_id=service_id
            ),
            snapshot_id=SNAPSHOT_ID,
            context_id=CONTEXT_ID,
        )

    assert len(result.resolutions) == 1
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_CONFIGURED
    assert resolution.service_id == "service:checkout"
    assert resolution.workload.name == "checkout-api"
    [claim] = result.claims
    assert claim.claim_id == resolution.claim_id


def test_path_b_mapping_to_a_real_missing_workload_is_unresolved_end_to_end(driver, tmp_path):
    _reset_graph(driver)
    _create_service(driver, service_id="service:checkout", name="checkout")

    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "aip.dev/v1",
                "kind": "ServiceWorkloadIdentityMappings",
                "metadata": {"id": "i3-path-b-missing-mappings", "revision": "v1"},
                "mappings": [
                    {
                        "mappingId": "checkout-runtime",
                        "serviceId": "service:checkout",
                        "kubernetesSourceId": "i3-path-b-missing-source",
                        "clusterUid": "i3-path-b-missing-cluster-uid",
                        "workload": {
                            "apiGroup": "apps",
                            "kind": "Deployment",
                            "namespace": "checkout",
                            "name": "checkout-api",
                        },
                    }
                ],
            }
        )
    )
    document, diagnostics = load_service_workload_mapping(mapping_path)
    assert diagnostics == ()

    with driver.session(database=DATABASE) as session:
        result = resolve_path_b(
            document=document,
            configured_kubernetes_sources=[
                ("i3-path-b-missing-source", "i3-path-b-missing-cluster-uid")
            ],
            resolve_workload=lambda entity_id: (
                deployment_repository.read_current_kubernetes_workload(session, entity_id=entity_id)
            ),
            lookup_service_name=lambda service_id: deployment_repository.read_service_name(
                session, service_id=service_id
            ),
            snapshot_id=SNAPSHOT_ID,
            context_id=CONTEXT_ID,
        )

    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.workload is None
    assert result.claims == []


def test_path_b_mapping_to_an_observed_only_service_is_unresolved_end_to_end(driver, tmp_path):
    # PR #215 review (spec §3/§8.2/§29): a configured mapping naming an OBSERVED_ONLY Service stub
    # must resolve the Workload but still refuse to mint a claim.
    _reset_graph(driver)
    _create_observed_only_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path / "cluster",
        source_id="i3-path-b-observed-only-source",
        scope_id="i3-path-b-observed-only-scope",
        cluster_uid="i3-path-b-observed-only-cluster-uid",
        namespaces=["checkout"],
        resources=[_deployment("checkout-api", "checkout", "deploy-uid-path-b-observed-only")],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "aip.dev/v1",
                "kind": "ServiceWorkloadIdentityMappings",
                "metadata": {"id": "i3-path-b-observed-only-mappings", "revision": "v1"},
                "mappings": [
                    {
                        "mappingId": "checkout-runtime",
                        "serviceId": "service:checkout",
                        "kubernetesSourceId": "i3-path-b-observed-only-source",
                        "clusterUid": "i3-path-b-observed-only-cluster-uid",
                        "workload": {
                            "apiGroup": "apps",
                            "kind": "Deployment",
                            "namespace": "checkout",
                            "name": "checkout-api",
                        },
                    }
                ],
            }
        )
    )
    document, diagnostics = load_service_workload_mapping(mapping_path)
    assert diagnostics == ()

    with driver.session(database=DATABASE) as session:
        result = resolve_path_b(
            document=document,
            configured_kubernetes_sources=[
                ("i3-path-b-observed-only-source", "i3-path-b-observed-only-cluster-uid")
            ],
            resolve_workload=lambda entity_id: (
                deployment_repository.read_current_kubernetes_workload(session, entity_id=entity_id)
            ),
            lookup_service_name=lambda service_id: deployment_repository.read_service_name(
                session, service_id=service_id
            ),
            snapshot_id=SNAPSHOT_ID,
            context_id=CONTEXT_ID,
        )

    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.workload is not None  # the Workload itself resolved
    assert resolution.candidate_service_ids == ["service:checkout"]
    assert result.claims == []
