"""v0.5.0 I3 slice 5b - REST/service semantic-equivalence tests for the new
`GET /api/services/{service_id}/deployments` view (spec §15). Mirrors
`test_api_architecture_intelligence_equivalence.py`'s `_client`/`_service` pattern; the Path A
fixture builder (`_write_kubernetes_bundle`/`import_kubernetes_source`) is the same one
`test_architecture_intelligence_deployment_repository.py` already established for a real,
end-to-end-resolvable annotated Workload, reused here rather than re-invented.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.architecture_intelligence.contracts import DeploymentResolutionStatus, Producer
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.canonical.model import ArchitectureModel, Service
from app.graph.importer import import_kubernetes_source, import_source
from app.graph.schema import ensure_schema
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import KubernetesSourceConfig

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)

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


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _client(driver, *, service: ArchitectureIntelligenceService | None = None) -> TestClient:
    app = create_app()
    app.state.driver = driver
    app.state.llm_provider = None
    app.state.architecture_intelligence_service = service or _service(driver)
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {
                "sources": {
                    "directories": [
                        {
                            "id": "aip-bundled-examples-v0.5",
                            "root": str(EXAMPLES_DIR),
                            "stable_target_identity": "urn:aip:logical-root:bundled-examples",
                        }
                    ]
                },
                "graph": {"uri": "bolt://ignored:7687", "database": DATABASE},
            }
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored", openai_api_key=None),
    )
    return TestClient(app)


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


def _deployment(name: str, namespace: str, uid: str, *, annotations: dict) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "uid": uid,
            "resourceVersion": "1",
            "annotations": annotations,
        },
    }


def _write_kubernetes_bundle(root: Path, *, resources: list[dict]) -> KubernetesSourceConfig:
    root.mkdir(parents=True, exist_ok=True)
    resource_bytes = yaml.safe_dump_all(resources).encode()
    (root / "resources.yaml").write_bytes(resource_bytes)
    envelope = {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": "i3-rest-deployments-source-snapshot",
            "revision": "i3-rest-deployments-source-revision",
            "producer": "aip-kubernetes-capture-agent",
            "capturedAt": "2026-09-19T10:00:00Z",
        },
        "source": {
            "configuredSourceId": "i3-rest-deployments-source",
            "configuredScopeId": "i3-rest-deployments-scope",
            "clusterUid": "i3-rest-deployments-cluster",
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {
            "namespaces": ["checkout"],
            "resourceTypes": sorted(EXPECTED_RESOURCE_TYPES),
        },
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": "i3-rest-deployments-authority",
            "expectedPriorInventoryRevision": None,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}],
    }
    (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
    return KubernetesSourceConfig(
        id="i3-rest-deployments-source",
        root=root,
        envelope_relative_path="envelope.yaml",
        configured_scope_id="i3-rest-deployments-scope",
        cluster_uid="i3-rest-deployments-cluster",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-kubernetes-capture-agent",
        authority_record="i3-rest-deployments-authority",
    )


def _seed_resolved_explicit_deployment(driver, tmp_path: Path, *, service_id: str) -> None:
    _create_service(driver, service_id=service_id, name="checkout")
    config = _write_kubernetes_bundle(
        tmp_path,
        resources=[
            _deployment(
                "checkout-api",
                "checkout",
                "deploy-uid-rest-deployments",
                annotations={"architecture-intelligence.io/service-id": service_id},
            )
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True


# --- GET /api/services/{id}/deployments -----------------------------------------------------


def test_deployments_rest_matches_service_for_a_resolved_explicit_deployment(driver, tmp_path):
    service_id = ids.service_id("checkout")
    _seed_resolved_explicit_deployment(driver, tmp_path, service_id=service_id)

    service = _service(driver)
    direct = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": service_id,
                "observation_context": {
                    "environment": ENVIRONMENT,
                    "window_start": WINDOW_START,
                    "window_end": WINDOW_END,
                },
            }
        )
    )
    assert direct.data is not None
    assert len(direct.data.deployment_claim_ids) == 1
    [resolution] = direct.data.deployment_resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT

    client = _client(driver, service=service)
    response = client.get(
        f"/api/services/{service_id}/deployments",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 200
    body = response.json()

    assert len(body["deployment_claims"]) == 1
    assert body["deployment_claims"][0]["claim_id"] == direct.data.deployment_claim_ids[0]
    assert [r["resolution_id"] for r in body["deployment_resolutions"]] == [
        r.resolution_id for r in direct.data.deployment_resolutions
    ]
    assert body["snapshot"] == direct.model_dump(mode="json")["snapshot"]
    assert body["observation_context"] == direct.model_dump(mode="json")["observation_context"]
    assert body["service"] == direct.model_dump(mode="json")["data"]["service"]
    assert set(body["evidence_refs"]) <= set(direct.evidence_refs)
    assert body["evidence_refs"]  # the resolved claim's own evidence is present


def test_deployments_rest_matches_service_for_a_known_service_with_no_deployment_data(driver):
    service_id = ids.service_id("checkout")
    _create_service(driver, service_id=service_id, name="checkout")

    client = _client(driver)
    response = client.get(
        f"/api/services/{service_id}/deployments",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_claims"] == []
    assert body["deployment_resolutions"] == []
    assert body["evidence_refs"] == []
    assert body["service"]["id"] == service_id


def test_deployments_rest_unknown_service_is_404(driver):
    """spec §15: unlike `/dependencies`/`/drift` (always 200), an unknown Service on this endpoint
    is a real 404 - the one spec-frozen exception to this router's own "everything stays 200" rule."""
    client = _client(driver)
    response = client.get(
        "/api/services/service:does-not-exist/deployments",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 404


def test_deployments_rest_malformed_window_is_422(driver):
    client = _client(driver)
    response = client.get(
        f"/api/services/{ids.service_id('checkout')}/deployments",
        params={"environment": ENVIRONMENT, "from": "not-a-date", "to": WINDOW_END},
    )
    assert response.status_code == 422


def test_deployments_rest_reversed_window_is_422(driver):
    client = _client(driver)
    response = client.get(
        f"/api/services/{ids.service_id('checkout')}/deployments",
        params={"environment": ENVIRONMENT, "from": WINDOW_END, "to": WINDOW_START},
    )
    assert response.status_code == 422


def test_deployments_rest_missing_required_param_is_422(driver):
    """spec §15: `environment`/`from`/`to` are required, unlike `/dependencies`/`/drift`'s optional
    (refusal-yielding) query params."""
    client = _client(driver)
    response = client.get(f"/api/services/{ids.service_id('checkout')}/deployments")
    assert response.status_code == 422


# --- §14.2 regression: drift stays deployment-agnostic even when a deployment resolves -----------


def test_drift_never_returns_a_deployment_claim_even_when_a_deployment_resolves(driver, tmp_path):
    """spec §14.2: "get_architecture_drift returns only dependency-drift claims and never
    DEPLOYED_AS" - proven here against a service with a real, resolvable Path A deployment (the same
    fixture the deployments-view tests above use), not just the contract-level validator that
    already rejects a `DeploymentClaim` in this answer shape."""
    service_id = ids.service_id("checkout")
    _seed_resolved_explicit_deployment(driver, tmp_path, service_id=service_id)

    service = _service(driver)
    drift = service.get_architecture_drift(
        ArchitectureDriftRequest.model_validate(
            {
                "service_id": service_id,
                "observation_context": {
                    "environment": ENVIRONMENT,
                    "window_start": WINDOW_START,
                    "window_end": WINDOW_END,
                },
            }
        )
    )
    assert all(claim.predicate != "DEPLOYED_AS" for claim in drift.claims)

    client = _client(driver, service=service)
    response = client.get(
        f"/api/services/{service_id}/drift",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 200
    assert all(claim["predicate"] != "DEPLOYED_AS" for claim in response.json()["claims"])
