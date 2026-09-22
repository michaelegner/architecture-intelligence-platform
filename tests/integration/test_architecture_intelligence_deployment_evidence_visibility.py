"""v0.5.0 I3 slice 5b: spec §16.1/§16.2 evidence exposure, proven against a real Neo4j instance
with real Kubernetes-adapter-committed evidence - not the pure-function reachability tests already
covering `deployment_reconciliation.reachable_deployment_evidence_ids`/`deployed_as_supported_facts`
in `tests/unit/test_architecture_intelligence_deployment_reconciliation.py`.

Reuses `test_architecture_intelligence_deployment_repository.py`'s own fixture helpers
(`_write_kubernetes_bundle`/`import_kubernetes_source`, `_create_service`,
`_create_observed_only_service`) rather than re-deriving Kubernetes-bundle construction.
"""

from __future__ import annotations

import hashlib

import pytest
import yaml

from app.architecture_intelligence.contracts import DeploymentResolutionStatus, Producer
from app.architecture_intelligence.request import EvidenceRequest, ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.canonical.model import ArchitectureModel, Service
from app.graph.importer import import_kubernetes_source, import_source
from app.graph.schema import ensure_schema
from app.sources.model import KubernetesSourceConfig

DATABASE = "neo4j"
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

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _create_service(driver, *, service_id: str, name: str) -> None:
    with driver.session(database=DATABASE) as session:
        stats = import_source(
            session,
            source_instance_id=f"declared-source:{service_id}",
            locator=f"{service_id}.yaml",
            model=ArchitectureModel(services=[Service(id=service_id, name=name, version="1")]),
            semantic_input_digest=hashlib.sha256(f"{service_id}:{name}".encode()).hexdigest(),
            discovery_scope_id=f"declared-scope:{service_id}",
            scope_definition_digest=hashlib.sha256(service_id.encode()).hexdigest(),
        )
    assert stats.graph_revision_advanced is True


def _create_observed_only_service(driver, *, service_id: str, name: str) -> None:
    with driver.session(database=DATABASE) as session:
        session.run(
            "MERGE (s:Service {id: $id}) SET s.name = $name, s.discovery_status = 'OBSERVED_ONLY'",
            id=service_id,
            name=name,
        )


def _deployment(name: str, namespace: str, uid: str, *, annotations: dict | None = None) -> dict:
    metadata = {"name": name, "namespace": namespace, "uid": uid, "resourceVersion": "1"}
    if annotations:
        metadata["annotations"] = annotations
    return {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": metadata}


def _write_kubernetes_bundle(
    root, *, resources: list[dict], source_id: str = "i3-evidence-visibility-source"
) -> KubernetesSourceConfig:
    root.mkdir(parents=True, exist_ok=True)
    resource_bytes = yaml.safe_dump_all(resources).encode()
    (root / "resources.yaml").write_bytes(resource_bytes)
    scope_id = f"{source_id}-scope"
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
            # Shared across every call so two differently-`source_id`d imports of the same
            # cluster/namespace/name/uid resource still resolve to the SAME `InfrastructureEntity`,
            # each contributing its own separate `InfrastructureContribution`.
            "clusterUid": "i3-evidence-visibility-cluster",
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {
            "namespaces": ["checkout"],
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
        cluster_uid="i3-evidence-visibility-cluster",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-kubernetes-capture-agent",
        authority_record=f"{source_id}-authority",
    )


def _contribution_evidence_refs(driver, *, workload_name: str) -> list[str]:
    """The union of every current contribution's own `evidence_refs` for this Workload - a Workload
    scanned by more than one source (the CONFLICT fixture below) has more than one contribution,
    and `deployment_projection.resolve_path_a` itself unions all of them the same way."""
    with driver.session(database=DATABASE) as session:
        records = session.run(
            "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_WORKLOAD', name: $name}) "
            "MATCH (c:InfrastructureContribution {entity_id: e.id}) "
            "RETURN coalesce(c.evidence_refs, []) AS evidence_refs",
            name=workload_name,
        )
        rows = list(records)
    assert rows
    return sorted({ref for row in rows for ref in row["evidence_refs"]})


def test_resolved_explicit_deployment_evidence_resolves_and_carries_deployed_as(driver, tmp_path):
    """§16.1/§16.2: a `RESOLVED_EXPLICIT` claim's own Kubernetes evidence becomes resolvable via
    `get_evidence`, and carries a computed `DEPLOYED_AS` `SupportedFact` - the relation is never a
    real graph edge, so this can only come from the reconciliation-owned augmentation."""
    _create_service(driver, service_id="service:checkout", name="checkout")
    config = _write_kubernetes_bundle(
        tmp_path,
        resources=[
            _deployment(
                "checkout-api",
                "checkout",
                "deploy-uid-resolved",
                annotations={"architecture-intelligence.io/service-id": "service:checkout"},
            )
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    [evidence_id] = _contribution_evidence_refs(driver, workload_name="checkout-api")

    service = _service(driver)
    answer = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": "service:checkout",
                "observation_context": {
                    "environment": "test",
                    "window_start": "2026-08-26T00:00:00Z",
                    "window_end": "2026-08-27T00:00:00Z",
                },
            }
        )
    )
    assert answer.snapshot is not None
    snapshot_id = answer.snapshot.snapshot_id

    resolved = service.get_evidence(
        EvidenceRequest.model_validate({"evidence_refs": [evidence_id], "snapshot_id": snapshot_id})
    )
    assert resolved.data is not None
    assert resolved.data.missing_evidence_refs == []
    [record] = resolved.data.records
    assert record.id == evidence_id
    assert record.source_type == "KUBERNETES"
    deployed_as_facts = [f for f in record.supports if f.relation_type == "DEPLOYED_AS"]
    assert len(deployed_as_facts) == 1
    assert deployed_as_facts[0].source_id == "service:checkout"


def test_conflicting_deployment_resolutions_evidence_still_resolves_without_deployed_as(
    driver, tmp_path
):
    """§16.2: "This includes non-resolved CONFLICT, AMBIGUOUS, and UNRESOLVED resolutions: evidence
    refs returned to a client MUST NOT become dead/non-drillable references merely because no claim
    was established." Two Kubernetes sources scanning the same Workload (same cluster/namespace/
    name - `kubernetes_logical_resource_id` is independent of `source_id`/`uid`) disagree on its
    `service-id` annotation -> `CONFLICT` (spec §7: "more than one distinct annotation is CONFLICT").
    One of the two candidate ids is a real declared Service, so this resolution's evidence is
    reachable (spec §16.2) even though no claim was established."""
    _create_service(driver, service_id="service:checkout", name="checkout")
    first = _write_kubernetes_bundle(
        tmp_path / "source-a",
        source_id="i3-evidence-visibility-source-a",
        resources=[
            _deployment(
                "checkout-api",
                "checkout",
                "deploy-uid-conflict-a",
                annotations={"architecture-intelligence.io/service-id": "service:checkout"},
            )
        ],
    )
    second = _write_kubernetes_bundle(
        tmp_path / "source-b",
        source_id="i3-evidence-visibility-source-b",
        resources=[
            _deployment(
                "checkout-api",
                "checkout",
                "deploy-uid-conflict-b",
                annotations={"architecture-intelligence.io/service-id": "service:other"},
            )
        ],
    )
    assert import_kubernetes_source(driver, database=DATABASE, source_config=first).committed
    assert import_kubernetes_source(driver, database=DATABASE, source_config=second).committed

    evidence_ids = _contribution_evidence_refs(driver, workload_name="checkout-api")
    assert len(evidence_ids) == 2

    service = _service(driver)
    answer = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": "service:checkout",
                "observation_context": {
                    "environment": "test",
                    "window_start": "2026-08-26T00:00:00Z",
                    "window_end": "2026-08-27T00:00:00Z",
                },
            }
        )
    )
    assert answer.data is not None
    assert answer.data.deployment_claim_ids == []
    [resolution] = answer.data.deployment_resolutions
    assert resolution.status == DeploymentResolutionStatus.CONFLICT
    assert set(resolution.conflicting_evidence_refs) == set(evidence_ids)

    resolved = service.get_evidence(
        EvidenceRequest.model_validate(
            {"evidence_refs": evidence_ids, "snapshot_id": answer.snapshot.snapshot_id}
        )
    )
    assert resolved.data is not None
    assert resolved.data.missing_evidence_refs == []
    assert len(resolved.data.records) == 2
    for record in resolved.data.records:
        assert not any(f.relation_type == "DEPLOYED_AS" for f in record.supports)


def test_unreferenced_kubernetes_evidence_stays_hidden(driver, tmp_path):
    """§16.2: an unannotated Workload produces no Path A resolution at all, so its own Kubernetes
    evidence is never reachable from any DEPLOYED_AS claim/resolution and must stay exactly as
    hidden as before I3 (I2 Draft 0.2 §9's original boundary)."""
    _create_service(driver, service_id="service:checkout", name="checkout")
    config = _write_kubernetes_bundle(
        tmp_path,
        resources=[_deployment("unrelated-worker", "checkout", "deploy-uid-unreferenced")],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    [evidence_id] = _contribution_evidence_refs(driver, workload_name="unrelated-worker")

    service = _service(driver)
    answer = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": "service:checkout",
                "observation_context": {
                    "environment": "test",
                    "window_start": "2026-08-26T00:00:00Z",
                    "window_end": "2026-08-27T00:00:00Z",
                },
            }
        )
    )
    assert answer.snapshot is not None

    resolved = service.get_evidence(
        EvidenceRequest.model_validate(
            {"evidence_refs": [evidence_id], "snapshot_id": answer.snapshot.snapshot_id}
        )
    )
    assert resolved.data is not None
    assert resolved.data.records == []
    assert resolved.data.missing_evidence_refs == [evidence_id]
