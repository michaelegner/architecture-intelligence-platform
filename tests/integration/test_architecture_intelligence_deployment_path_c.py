"""v0.5.0 I3 slice 4 end-to-end: a real Kubernetes owner-chain import (Deployment/StatefulSet/
DaemonSet) combined with a real OTel runtime identity observation, read back through
`app.architecture_intelligence.deployment_repository` and reduced by
`app.architecture_intelligence.deployment_projection.resolve_path_c` - proving the whole Path C
pipeline against a real Neo4j instance. No existing test combines a real OTLP ingest with a real I2
Kubernetes import; this is the first.

OTel data is persisted directly through `app.telemetry.adapter.adapt`/
`app.telemetry.aggregator.persist_observation_batch` over hand-built `RuntimeSpan` objects, not
through the HTTP/protobuf `/v1/traces` layer - the point of these tests is Path C's own resolution,
not the OTLP wire format, and slice 3's own precedent (`test_architecture_intelligence_deployment_
repository.py`) already establishes calling real ingestion entry points directly rather than through
FastAPI.
"""

import hashlib
from datetime import UTC, datetime

import yaml

from app.architecture_intelligence import deployment_repository
from app.architecture_intelligence.contracts import (
    DeploymentResolutionMethod,
    DeploymentResolutionStatus,
)
from app.architecture_intelligence.deployment_projection import resolve_path_c
from app.architecture_intelligence.observation_context import build_observation_context_ref
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.canonical.model import ArchitectureModel, Service
from app.graph.importer import import_kubernetes_source, import_source
from app.graph.schema import ensure_schema
from app.sources.model import KubernetesSourceConfig
from app.telemetry.adapter import adapt
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import RuntimeSpan
from app.telemetry.operation_resolver import fetch_operation_candidates
from app.telemetry.queue_resolver import fetch_queue_candidates
from app.telemetry.service_resolver import fetch_candidates

DATABASE = "neo4j"
SNAPSHOT_ID = "aip:snapshot:v1:" + "a" * 64
CONTEXT_ID = "aip:observation-context:v1:" + "b" * 64
ENVIRONMENT = "prod"
WINDOW_START = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 19, 23, 59, 59, tzinfo=UTC)
SPAN_TIME = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)
CAPTURED_AT = "2026-09-19T12:00:00Z"

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


def _workload_resource(kind: str, name: str, *, uid: str, namespace: str) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": kind,
        "metadata": {"name": name, "namespace": namespace, "uid": uid, "resourceVersion": "1"},
    }


def _pod_resource(
    name: str, *, uid: str, namespace: str, owner_kind: str, owner_name: str, owner_uid: str
) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "uid": uid,
            "resourceVersion": "1",
            "ownerReferences": [
                {
                    "apiVersion": "apps/v1",
                    "kind": owner_kind,
                    "name": owner_name,
                    "uid": owner_uid,
                    "controller": True,
                }
            ],
        },
    }


def _replica_set_resource(
    name: str, *, uid: str, namespace: str, owner_name: str, owner_uid: str
) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "uid": uid,
            "resourceVersion": "1",
            "ownerReferences": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": owner_name,
                    "uid": owner_uid,
                    "controller": True,
                }
            ],
        },
    }


def _write_kubernetes_bundle(
    root,
    *,
    source_id: str,
    scope_id: str,
    cluster_uid: str,
    namespaces: list[str],
    resources: list[dict],
    captured_at: str = CAPTURED_AT,
    expected_prior_inventory_revision: str | None = None,
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
            "capturedAt": captured_at,
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
            "expectedPriorInventoryRevision": expected_prior_inventory_revision,
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
    """Declare a Service through the real source-owned importer path (not a raw `MERGE`) - the
    `owner_source_ids`-based declared-Service gate `deployment_repository.read_declared_service_
    identity` applies needs a real canonical-import owner, mirroring slice 3's own precedent."""
    with driver.session(database=DATABASE) as session:
        import_source(
            session,
            source_instance_id=f"declared-source:{service_id}",
            locator=f"{service_id}.yaml",
            model=ArchitectureModel(services=[Service(id=service_id, name=name, version="1")]),
            semantic_input_digest=hashlib.sha256(f"{service_id}:{name}".encode()).hexdigest(),
            discovery_scope_id=f"declared-scope:{service_id}",
            scope_definition_digest=hashlib.sha256(service_id.encode()).hexdigest(),
        )


def _runtime_span(**overrides) -> RuntimeSpan:
    defaults = {
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "span_id": "00f067aa0ba902b7",
        "span_name": "GET /health",
        "span_kind": "SERVER",
        "service_name": "checkout",
        "environment": ENVIRONMENT,
        "k8s_pod_uid": "pod-uid-1",
        "start_time": SPAN_TIME,
        "end_time": SPAN_TIME,
    }
    defaults.update(overrides)
    return RuntimeSpan(**defaults)


def _persist_spans(driver, spans: list[RuntimeSpan]) -> None:
    with driver.session(database=DATABASE) as session:
        service_candidates = fetch_candidates(session)
        operation_candidates = fetch_operation_candidates(session)
        queue_candidates = fetch_queue_candidates(session)
    batch = adapt(
        spans,
        service_candidates=service_candidates,
        operation_candidates=operation_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )
    persist_observation_batch(driver, DATABASE, batch)


def _run_resolve_path_c(driver):
    observation_context = build_observation_context_ref(ENVIRONMENT, WINDOW_START, WINDOW_END)
    with driver.session(database=DATABASE) as session:
        observations = deployment_repository.read_runtime_identity_observations_in_window(
            session, environment=ENVIRONMENT, window_start=WINDOW_START, window_end=WINDOW_END
        )
        declared_candidates = fetch_candidates(session)
        return resolve_path_c(
            observations=observations,
            observation_context=observation_context,
            lookup_pods_by_uid=lambda uid: deployment_repository.read_captured_pods_by_uid(
                session, pod_uid=uid
            ),
            lookup_workload_ids_owning_pod=(
                lambda pod_id: deployment_repository.read_workload_ids_owning_pod(
                    session, pod_id=pod_id
                )
            ),
            resolve_workload=lambda wid: deployment_repository.read_current_kubernetes_workload(
                session, entity_id=wid
            ),
            declared_service_candidates=declared_candidates,
            service_aliases={},
            lookup_declared_service=(
                lambda sid: deployment_repository.read_declared_service_identity(
                    session, service_id=sid
                )
            ),
            snapshot_id=SNAPSHOT_ID,
            context_id=CONTEXT_ID,
        )


def test_path_c_resolves_deployment_end_to_end(driver, tmp_path):
    _reset_graph(driver)
    _create_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-c-deploy-source",
        scope_id="i3-path-c-deploy-scope",
        cluster_uid="i3-path-c-deploy-cluster",
        namespaces=["checkout"],
        resources=[
            _workload_resource(
                "Deployment", "checkout-api", uid="deploy-uid-1", namespace="checkout"
            ),
            _replica_set_resource(
                "checkout-api-rs",
                uid="rs-uid-1",
                namespace="checkout",
                owner_name="checkout-api",
                owner_uid="deploy-uid-1",
            ),
            _pod_resource(
                "checkout-api-pod",
                uid="pod-uid-1",
                namespace="checkout",
                owner_kind="ReplicaSet",
                owner_name="checkout-api-rs",
                owner_uid="rs-uid-1",
            ),
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    _persist_spans(driver, [_runtime_span(k8s_pod_uid="pod-uid-1")])

    result = _run_resolve_path_c(driver)
    assert len(result.resolutions) == 1
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_OBSERVED
    assert resolution.service_id == "service:checkout"
    assert resolution.workload.name == "checkout-api"
    assert resolution.supporting_methods == [DeploymentResolutionMethod.RESOLVED_OBSERVED]
    [claim] = result.claims
    assert claim.claim_id == resolution.claim_id


def test_path_c_resolves_statefulset_end_to_end(driver, tmp_path):
    _reset_graph(driver)
    _create_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-c-sts-source",
        scope_id="i3-path-c-sts-scope",
        cluster_uid="i3-path-c-sts-cluster",
        namespaces=["checkout"],
        resources=[
            _workload_resource("StatefulSet", "checkout-db", uid="sts-uid-1", namespace="checkout"),
            _pod_resource(
                "checkout-db-0",
                uid="pod-uid-2",
                namespace="checkout",
                owner_kind="StatefulSet",
                owner_name="checkout-db",
                owner_uid="sts-uid-1",
            ),
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    _persist_spans(driver, [_runtime_span(k8s_pod_uid="pod-uid-2")])

    result = _run_resolve_path_c(driver)
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_OBSERVED
    assert resolution.workload.name == "checkout-db"


def test_path_c_resolves_daemonset_end_to_end(driver, tmp_path):
    _reset_graph(driver)
    _create_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-c-ds-source",
        scope_id="i3-path-c-ds-scope",
        cluster_uid="i3-path-c-ds-cluster",
        namespaces=["checkout"],
        resources=[
            _workload_resource("DaemonSet", "checkout-agent", uid="ds-uid-1", namespace="checkout"),
            _pod_resource(
                "checkout-agent-xyz",
                uid="pod-uid-3",
                namespace="checkout",
                owner_kind="DaemonSet",
                owner_name="checkout-agent",
                owner_uid="ds-uid-1",
            ),
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    _persist_spans(driver, [_runtime_span(k8s_pod_uid="pod-uid-3")])

    result = _run_resolve_path_c(driver)
    [resolution] = result.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_OBSERVED
    assert resolution.workload.name == "checkout-agent"


def test_path_c_pod_replacement_preserves_claim_id(driver, tmp_path):
    # §21.5: capture N (Pod P1 -> Workload W, OTel P1 -> Service S) resolves S DEPLOYED_AS W;
    # capture N+1 (P1 replaced by P2, same Workload, same Service) resolves the *same* claim id,
    # and the old Pod UID no longer resolves at all.
    _reset_graph(driver)
    _create_service(driver, service_id="service:checkout", name="checkout")

    config = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-c-replace-source",
        scope_id="i3-path-c-replace-scope",
        cluster_uid="i3-path-c-replace-cluster",
        namespaces=["checkout"],
        resources=[
            _workload_resource(
                "Deployment", "checkout-api", uid="deploy-uid-1", namespace="checkout"
            ),
            _replica_set_resource(
                "checkout-api-rs",
                uid="rs-uid-1",
                namespace="checkout",
                owner_name="checkout-api",
                owner_uid="deploy-uid-1",
            ),
            _pod_resource(
                "checkout-api-pod-1",
                uid="pod-uid-p1",
                namespace="checkout",
                owner_kind="ReplicaSet",
                owner_name="checkout-api-rs",
                owner_uid="rs-uid-1",
            ),
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True
    _persist_spans(driver, [_runtime_span(k8s_pod_uid="pod-uid-p1")])

    first_result = _run_resolve_path_c(driver)
    [first_resolution] = first_result.resolutions
    assert first_resolution.status == DeploymentResolutionStatus.RESOLVED_OBSERVED
    first_claim_id = first_resolution.claim_id

    with driver.session(database=DATABASE) as session:
        prior_revision = session.run(
            "MATCH (i:CurrentInventory) RETURN i.inventory_revision AS r"
        ).single()["r"]

    # Reimport the same source with P1 replaced by P2 (same physical root/source id, so the
    # importer's own ownership/expiry machinery actually retires P1's contribution).
    config_v2 = _write_kubernetes_bundle(
        tmp_path,
        source_id="i3-path-c-replace-source",
        scope_id="i3-path-c-replace-scope",
        cluster_uid="i3-path-c-replace-cluster",
        namespaces=["checkout"],
        expected_prior_inventory_revision=prior_revision,
        resources=[
            _workload_resource(
                "Deployment", "checkout-api", uid="deploy-uid-1", namespace="checkout"
            ),
            _replica_set_resource(
                "checkout-api-rs",
                uid="rs-uid-1",
                namespace="checkout",
                owner_name="checkout-api",
                owner_uid="deploy-uid-1",
            ),
            _pod_resource(
                "checkout-api-pod-2",
                uid="pod-uid-p2",
                namespace="checkout",
                owner_kind="ReplicaSet",
                owner_name="checkout-api-rs",
                owner_uid="rs-uid-1",
            ),
        ],
    )
    stats_v2 = import_kubernetes_source(driver, database=DATABASE, source_config=config_v2)
    assert stats_v2.committed is True

    with driver.session(database=DATABASE) as session:
        assert deployment_repository.read_captured_pods_by_uid(session, pod_uid="pod-uid-p1") == []

    _persist_spans(driver, [_runtime_span(k8s_pod_uid="pod-uid-p2", span_id="00f067aa0ba902c8")])

    second_result = _run_resolve_path_c(driver)
    resolved = [
        r
        for r in second_result.resolutions
        if r.status == DeploymentResolutionStatus.RESOLVED_OBSERVED
    ]
    assert len(resolved) == 1
    assert resolved[0].claim_id == first_claim_id
