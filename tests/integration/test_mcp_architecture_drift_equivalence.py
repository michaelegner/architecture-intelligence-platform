"""v0.4.0 I3.2 Neo4j-integration coverage: I3 spec §50's "direct drift vs MCP equivalence" and
"drift -> evidence drill-down" items - the parts of the required test matrix that need a real
driver, real imported services, and a real revision fence to mean anything. Adapter-level
dispatch/error-mapping against a stub service is
`tests/unit/test_mcp_architecture_drift_adapter.py`'s job.

Mirrors `tests/integration/test_mcp_service_dependencies_equivalence.py`'s structure exactly, so a
"drift"/"empty drift"/"refusal" answer here is exercising the exact same graph state I1/I3.1's own
suites already qualify against.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import jsonschema
import pytest
import yaml
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Outcome, Producer
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.canonical.model import ArchitectureModel, Service
from app.graph.importer import import_all_sources, import_kubernetes_source, import_source
from app.graph.revision_fence import read_revision
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.sources.model import FilesystemSourceConfig, KubernetesSourceConfig
from tests.support.negotiated_mcp_client import call_negotiated

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.5"
    / "drift-answer.schema.json"
)
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.1", build_revision="f" * 40
)

DRIFT_ANSWER_SCHEMA = json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _request_payload(service_id: str, **overrides) -> dict:
    payload = {
        "service_id": service_id,
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }
    payload.update(overrides)
    return payload


def _request(service_id: str, **overrides) -> ArchitectureDriftRequest:
    return ArchitectureDriftRequest.model_validate(_request_payload(service_id, **overrides))


def _build_server_and_app(driver) -> tuple[MCPServer, object]:
    service = _service(driver)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    return server, app


async def _call_mcp(client: httpx.AsyncClient, name: str, request_payload: dict) -> dict:
    return await call_negotiated(
        client, origin=_ALLOWED_ORIGIN, name=name, arguments={"request": request_payload}
    )


async def _call_drift(client: httpx.AsyncClient, request_payload: dict) -> dict:
    return await _call_mcp(client, "get_architecture_drift", request_payload)


@pytest.mark.asyncio
async def test_drift_answer_with_claims_is_identical_direct_vs_mcp(driver):
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-architecture-drift-equivalence-examples", root=EXAMPLES_DIR
        ),
    )
    direct_json = (
        _service(driver)
        .get_architecture_drift(_request(ids.service_id("order-service")))
        .model_dump(mode="json")
    )
    assert direct_json["outcome"] in (Outcome.PARTIAL.value, Outcome.ANSWERED.value)
    assert direct_json["claims"]
    jsonschema.validate(instance=direct_json, schema=DRIFT_ANSWER_SCHEMA)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(client, _request_payload(ids.service_id("order-service")))
            assert result["isError"] is False
            jsonschema.validate(instance=result["structuredContent"], schema=DRIFT_ANSWER_SCHEMA)
            assert result["structuredContent"] == direct_json


@pytest.mark.asyncio
async def test_empty_drift_answer_is_identical_direct_vs_mcp(driver):
    """`product-service` only provides (I3 spec §18.2's zero-candidate empty-drift case) - a
    different envelope branch than the claim-bearing case above."""
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-architecture-drift-equivalence-examples", root=EXAMPLES_DIR
        ),
    )
    direct_json = (
        _service(driver)
        .get_architecture_drift(_request(ids.service_id("product-service")))
        .model_dump(mode="json")
    )
    assert direct_json["outcome"] == Outcome.ANSWERED.value
    assert direct_json["claims"] == []
    jsonschema.validate(instance=direct_json, schema=DRIFT_ANSWER_SCHEMA)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(client, _request_payload(ids.service_id("product-service")))
            assert result["isError"] is False
            assert result["structuredContent"] == direct_json


@pytest.mark.asyncio
async def test_two_identical_mcp_drift_calls_produce_byte_identical_structured_content(driver):
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-architecture-drift-equivalence-examples", root=EXAMPLES_DIR
        ),
    )
    server, app = _build_server_and_app(driver)
    payload = _request_payload(ids.service_id("order-service"))
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            first = await _call_drift(client, payload)
            second = await _call_drift(client, payload)
            assert first["structuredContent"] == second["structuredContent"]


@pytest.mark.asyncio
async def test_successful_mcp_drift_call_leaves_revision_fence_unchanged(driver):
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-architecture-drift-equivalence-examples", root=EXAMPLES_DIR
        ),
    )
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(client, _request_payload(ids.service_id("order-service")))
            assert result["isError"] is False

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before


@pytest.mark.asyncio
async def test_refusal_mcp_drift_call_leaves_revision_fence_unchanged(driver):
    """A stale/mismatched snapshot_id forces `NOT_ANSWERED`/`SNAPSHOT_NOT_AVAILABLE` - still zero
    graph writes (I3 spec §25)."""
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-architecture-drift-equivalence-examples", root=EXAMPLES_DIR
        ),
    )
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "a" * 64
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(
                client,
                _request_payload(ids.service_id("order-service"), snapshot_id=stale_snapshot_id),
            )
            assert result["isError"] is False
            assert result["structuredContent"]["outcome"] == "NOT_ANSWERED"
            assert result["structuredContent"]["limitations"][0]["code"] == "SNAPSHOT_NOT_AVAILABLE"

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before


@pytest.mark.asyncio
async def test_drift_evidence_refs_resolve_through_mcp_get_evidence_at_the_same_snapshot(driver):
    """I3 spec §22/§63's required drift -> evidence drill-down, proven through the MCP dispatch path
    (mirrors `test_architecture_intelligence_service.py`'s service-level version of this test, which
    already covers the direct-call path)."""
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="test-mcp-architecture-drift-equivalence-examples", root=EXAMPLES_DIR
        ),
    )
    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            drift_result = await _call_drift(
                client, _request_payload(ids.service_id("order-service"))
            )
            drift_answer = drift_result["structuredContent"]
            assert drift_answer["evidence_refs"]

            evidence_result = await _call_mcp(
                client,
                "get_evidence",
                {
                    "evidence_refs": drift_answer["evidence_refs"],
                    "snapshot_id": drift_answer["snapshot"]["snapshot_id"],
                },
            )
            evidence_answer = evidence_result["structuredContent"]
            assert evidence_answer["outcome"] == "ANSWERED"
            assert evidence_answer["data"]["missing_evidence_refs"] == []
            assert [record["id"] for record in evidence_answer["data"]["records"]] == sorted(
                drift_answer["evidence_refs"]
            )


# --- §21.6 regression: drift stays deployment-agnostic over the MCP transport specifically -------
# (the direct-service-call and REST variants already exist in
# `test_api_architecture_intelligence_deployments.py::test_drift_never_returns_a_deployment_claim_
# even_when_a_deployment_resolves` - this is the same proof, over negotiated MCP specifically).


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
            "id": "mcp-drift-deployment-snapshot",
            "revision": "mcp-drift-deployment-revision",
            "producer": "aip-kubernetes-capture-agent",
            "capturedAt": "2026-08-26T10:00:00Z",
        },
        "source": {
            "configuredSourceId": "mcp-drift-deployment-source",
            "configuredScopeId": "mcp-drift-deployment-scope",
            "clusterUid": "mcp-drift-deployment-cluster",
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
            "authorityRef": "mcp-drift-deployment-authority",
            "expectedPriorInventoryRevision": None,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}],
    }
    (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
    return KubernetesSourceConfig(
        id="mcp-drift-deployment-source",
        root=root,
        envelope_relative_path="envelope.yaml",
        configured_scope_id="mcp-drift-deployment-scope",
        cluster_uid="mcp-drift-deployment-cluster",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-kubernetes-capture-agent",
        authority_record="mcp-drift-deployment-authority",
    )


def _declare_service(driver, *, service_id: str, name: str) -> None:
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


@pytest.mark.asyncio
async def test_drift_never_returns_deployed_as_over_mcp_even_when_a_deployment_resolves(
    driver, tmp_path
):
    service_id = ids.service_id("checkout")
    _declare_service(driver, service_id=service_id, name="checkout")
    config = _write_kubernetes_bundle(
        tmp_path,
        resources=[
            _deployment_resource(
                "checkout-api",
                "checkout",
                "deploy-uid-mcp-drift",
                annotations={"architecture-intelligence.io/service-id": service_id},
            )
        ],
    )
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is True

    # Confirm the deployment genuinely resolves first, so a passing assertion below means
    # "drift correctly omits a real DEPLOYED_AS claim," not "there was never one to omit."
    direct_dependencies = _service(driver).get_service_dependencies(
        ServiceDependenciesRequest.model_validate(_request_payload(service_id))
    )
    assert direct_dependencies.data.deployment_claim_ids != []

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift(client, _request_payload(service_id))
            assert result["isError"] is False
            claims = result["structuredContent"]["claims"]
            assert all(claim["predicate"] != "DEPLOYED_AS" for claim in claims)
