"""v0.5.0 I3 slice 5a - REST/service semantic-equivalence tests (spec §14.1, ADR 0016 decision #7:
"REST == ArchitectureIntelligenceService semantics"). PR #221 review finding: the retained plan
explicitly called for this module and it was missing from the original diff - the three new REST
parity operations (`GET /api/services/{id}/dependencies`, `GET /api/services/{id}/drift`,
`POST /api/evidence/resolve`) were otherwise never exercised through REST at all.

Mirrors `tests/integration/test_mcp_service_dependencies_equivalence.py`'s structure (real driver,
real imported `examples/` graph, direct-service-call vs adapter-call comparison, frozen-schema
validation) and `tests/integration/test_api.py`'s `_build_app` pattern for a real
`fastapi.testclient.TestClient` wired to the same `ArchitectureIntelligenceService` instance the
direct calls below use - so REST/service equivalence is definitional (same instance), and what this
file actually proves is that the REST *route* (query-param parsing, status-code mapping) preserves
that instance's answer unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from fastapi.testclient import TestClient

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.repository import SnapshotUnstable
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.canonical.model import ArchitectureModel, Service
from app.graph.importer import import_all_sources, import_kubernetes_source, import_source
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import FilesystemSourceConfig, KubernetesSourceConfig

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SCHEMAS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "schemas" / "architecture_intelligence" / "v0.5"
)
DEPENDENCY_ANSWER_SCHEMA = json.loads((SCHEMAS_DIR / "architecture-answer.schema.json").read_text())
DRIFT_ANSWER_SCHEMA = json.loads((SCHEMAS_DIR / "drift-answer.schema.json").read_text())
EVIDENCE_ANSWER_SCHEMA = json.loads((SCHEMAS_DIR / "evidence-answer.schema.json").read_text())

DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
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


def _import_examples(driver) -> None:
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="aip-bundled-examples-v0.5",
            root=EXAMPLES_DIR,
            stable_target_identity="urn:aip:logical-root:bundled-examples",
        ),
    )


class _SnapshotUnstableService:
    """A fake service double proving the REST route's own 503 mapping (spec §16.3) - deterministically
    triggering `SnapshotUnstable` against a real Neo4j container is inherently racy (this slice's plan
    flagged this in its own Open Questions #5), so this double raises it directly rather than trying
    to force three inconsistent reads for real."""

    def list_public_evidence(self):
        raise SnapshotUnstable("no consistent snapshot after 3 attempts")

    def get_public_evidence(self, evidence_id: str):
        raise SnapshotUnstable("no consistent snapshot after 3 attempts")


# --- GET /api/services/{id}/dependencies -----------------------------------------------------


def test_dependencies_rest_matches_service_for_a_confirmed_answer(driver):
    _import_examples(driver)
    service = _service(driver)
    direct = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": ids.service_id("order-service"),
                "observation_context": {
                    "environment": ENVIRONMENT,
                    "window_start": WINDOW_START,
                    "window_end": WINDOW_END,
                },
            }
        )
    ).model_dump(mode="json")
    assert direct["claims"]
    jsonschema.validate(instance=direct, schema=DEPENDENCY_ANSWER_SCHEMA)

    client = _client(driver, service=service)
    response = client.get(
        f"/api/services/{ids.service_id('order-service')}/dependencies",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 200
    jsonschema.validate(instance=response.json(), schema=DEPENDENCY_ANSWER_SCHEMA)
    assert response.json() == direct


def test_dependencies_rest_unknown_service_is_200_with_unknown_entity_limitation(driver):
    """Plan Open Questions #2: an unknown service stays a semantic refusal inside a 200 body, never
    a synthesized 404 - unlike the slice-5b-only deployments endpoint."""
    _import_examples(driver)
    client = _client(driver)
    response = client.get(
        "/api/services/service:does-not-exist/dependencies",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "NOT_ANSWERED"
    assert body["limitations"][0]["code"] == "UNKNOWN_ENTITY"


def test_dependencies_rest_stale_snapshot_id_is_200_with_snapshot_not_available_limitation(driver):
    """Plan Open Questions #2: unlike the evidence surface's own frozen 409, a stale `snapshot_id`
    on the dependencies/drift routes stays inside a 200 body."""
    _import_examples(driver)
    client = _client(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "0" * 64
    response = client.get(
        f"/api/services/{ids.service_id('order-service')}/dependencies",
        params={
            "environment": ENVIRONMENT,
            "from": WINDOW_START,
            "to": WINDOW_END,
            "snapshot_id": stale_snapshot_id,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "NOT_ANSWERED"
    assert body["limitations"][0]["code"] == "SNAPSHOT_NOT_AVAILABLE"


def test_dependencies_rest_malformed_window_is_422(driver):
    _import_examples(driver)
    client = _client(driver)
    response = client.get(
        f"/api/services/{ids.service_id('order-service')}/dependencies",
        params={"environment": ENVIRONMENT, "from": "not-a-date", "to": WINDOW_END},
    )
    assert response.status_code == 422


def test_dependencies_rest_reversed_window_is_422(driver):
    """A well-formed but semantically invalid window (end before start) is caught by
    `reject_malformed_observation_context` before dispatch, same as the MCP adapter."""
    _import_examples(driver)
    client = _client(driver)
    response = client.get(
        f"/api/services/{ids.service_id('order-service')}/dependencies",
        params={"environment": ENVIRONMENT, "from": WINDOW_END, "to": WINDOW_START},
    )
    assert response.status_code == 422


def test_dependencies_rest_malformed_snapshot_id_is_422(driver):
    _import_examples(driver)
    client = _client(driver)
    response = client.get(
        f"/api/services/{ids.service_id('order-service')}/dependencies",
        params={
            "environment": ENVIRONMENT,
            "from": WINDOW_START,
            "to": WINDOW_END,
            "snapshot_id": "not-a-real-snapshot-id",
        },
    )
    assert response.status_code == 422


# --- GET /api/services/{id}/drift -------------------------------------------------------------


def test_drift_rest_matches_service_for_a_confirmed_answer(driver):
    _import_examples(driver)
    service = _service(driver)
    direct = service.get_architecture_drift(
        ArchitectureDriftRequest.model_validate(
            {
                "service_id": ids.service_id("order-service"),
                "observation_context": {
                    "environment": ENVIRONMENT,
                    "window_start": WINDOW_START,
                    "window_end": WINDOW_END,
                },
            }
        )
    ).model_dump(mode="json")
    jsonschema.validate(instance=direct, schema=DRIFT_ANSWER_SCHEMA)

    client = _client(driver, service=service)
    response = client.get(
        f"/api/services/{ids.service_id('order-service')}/drift",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 200
    jsonschema.validate(instance=response.json(), schema=DRIFT_ANSWER_SCHEMA)
    assert response.json() == direct


def test_drift_rest_never_returns_a_dependency_claim(driver):
    """spec §14.3: `get_architecture_drift` remains deployment-agnostic and dependency-agnostic -
    every returned claim's `predicate` is the drift-qualified subset, never a plain confirmed one."""
    _import_examples(driver)
    client = _client(driver)
    response = client.get(
        f"/api/services/{ids.service_id('order-service')}/drift",
        params={"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END},
    )
    assert response.status_code == 200
    for claim in response.json()["claims"]:
        assert claim["qualification"] != "CONFIRMED"


# --- POST /api/evidence/resolve -----------------------------------------------------------------


def test_evidence_resolve_rest_matches_service(driver):
    _import_examples(driver)
    service = _service(driver)
    dependency_answer = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": ids.service_id("order-service"),
                "observation_context": {
                    "environment": ENVIRONMENT,
                    "window_start": WINDOW_START,
                    "window_end": WINDOW_END,
                },
            }
        )
    )
    evidence_request = EvidenceRequest.model_validate(
        {
            "evidence_refs": sorted(dependency_answer.evidence_refs),
            "snapshot_id": dependency_answer.snapshot.snapshot_id,
        }
    )
    direct = service.get_evidence(evidence_request).model_dump(mode="json")
    assert direct["data"]["missing_evidence_refs"] == []
    jsonschema.validate(instance=direct, schema=EVIDENCE_ANSWER_SCHEMA)

    client = _client(driver, service=service)
    response = client.post(
        "/api/evidence/resolve",
        json={
            "evidence_refs": sorted(dependency_answer.evidence_refs),
            "snapshot_id": dependency_answer.snapshot.snapshot_id,
        },
    )
    assert response.status_code == 200
    jsonschema.validate(instance=response.json(), schema=EVIDENCE_ANSWER_SCHEMA)
    assert response.json() == direct


# --- §21.6: POST /api/evidence/resolve with real deployment (Path A) evidence, not just I1's --------
# dependency evidence - the deployment-evidence round-trip tests in
# `test_architecture_intelligence_deployment_evidence_visibility.py` all call
# `ArchitectureIntelligenceService.get_evidence` directly; this proves the same real deployment
# evidence ref resolves identically through the REST adapter specifically.


def _deployment_resource(name: str, namespace: str, uid: str, *, annotations: dict) -> dict:
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
            "id": "rest-evidence-deployment-snapshot",
            "revision": "rest-evidence-deployment-revision",
            "producer": "aip-kubernetes-capture-agent",
            "capturedAt": "2026-08-26T10:00:00Z",
        },
        "source": {
            "configuredSourceId": "rest-evidence-deployment-source",
            "configuredScopeId": "rest-evidence-deployment-scope",
            "clusterUid": "rest-evidence-deployment-cluster",
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {
            "namespaces": ["checkout"],
            "resourceTypes": sorted(
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
            ),
        },
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": "rest-evidence-deployment-authority",
            "expectedPriorInventoryRevision": None,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}],
    }
    (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
    return KubernetesSourceConfig(
        id="rest-evidence-deployment-source",
        root=root,
        envelope_relative_path="envelope.yaml",
        configured_scope_id="rest-evidence-deployment-scope",
        cluster_uid="rest-evidence-deployment-cluster",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-kubernetes-capture-agent",
        authority_record="rest-evidence-deployment-authority",
    )


def test_evidence_resolve_rest_matches_service_for_real_deployment_evidence(driver, tmp_path):
    service_id = ids.service_id("checkout")
    with driver.session(database=DATABASE) as session:
        import_source(
            session,
            source_instance_id=f"declared-source:{service_id}",
            locator=f"{service_id}.yaml",
            model=ArchitectureModel(
                services=[Service(id=service_id, name="checkout", version="1")]
            ),
            semantic_input_digest=hashlib.sha256(service_id.encode()).hexdigest(),
            discovery_scope_id=f"declared-scope:{service_id}",
            scope_definition_digest=hashlib.sha256(service_id.encode()).hexdigest(),
        )
    config = _write_kubernetes_bundle(
        tmp_path,
        resources=[
            _deployment_resource(
                "checkout-api",
                "checkout",
                "deploy-uid-rest-evidence",
                annotations={"architecture-intelligence.io/service-id": service_id},
            )
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    service = _service(driver)
    dependency_answer = service.get_service_dependencies(
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
    assert dependency_answer.data.deployment_claim_ids != []
    assert any(ref.startswith("evidence:kubernetes:") for ref in dependency_answer.evidence_refs)

    evidence_request = EvidenceRequest.model_validate(
        {
            "evidence_refs": sorted(dependency_answer.evidence_refs),
            "snapshot_id": dependency_answer.snapshot.snapshot_id,
        }
    )
    direct = service.get_evidence(evidence_request).model_dump(mode="json")
    assert direct["data"]["missing_evidence_refs"] == []

    client = _client(driver, service=service)
    response = client.post(
        "/api/evidence/resolve",
        json={
            "evidence_refs": sorted(dependency_answer.evidence_refs),
            "snapshot_id": dependency_answer.snapshot.snapshot_id,
        },
    )
    assert response.status_code == 200
    assert response.json() == direct


def test_evidence_resolve_rest_malformed_body_is_422(driver):
    _import_examples(driver)
    client = _client(driver)
    response = client.post(
        "/api/evidence/resolve",
        json={"evidence_refs": [], "snapshot_id": "aip:snapshot:v1:" + "a" * 64},
    )
    assert response.status_code == 422


def test_evidence_resolve_rest_missing_snapshot_id_is_422(driver):
    _import_examples(driver)
    client = _client(driver)
    response = client.post("/api/evidence/resolve", json={"evidence_refs": ["evidence:declared:a"]})
    assert response.status_code == 422


# --- GET /api/evidence[/{id}] 503 path (spec §16.3) ----------------------------------------------


def test_list_evidence_returns_503_when_snapshot_is_unstable(driver):
    client = _client(driver, service=_SnapshotUnstableService())
    response = client.get("/api/evidence", params={"snapshot_id": "aip:snapshot:v1:" + "a" * 64})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SNAPSHOT_NOT_AVAILABLE"


def test_get_evidence_returns_503_when_snapshot_is_unstable(driver):
    client = _client(driver, service=_SnapshotUnstableService())
    response = client.get(
        "/api/evidence/evidence:declared:a", params={"snapshot_id": "aip:snapshot:v1:" + "a" * 64}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SNAPSHOT_NOT_AVAILABLE"
