"""I2 Draft 0.2 §11 "Surface": "Internal claims absent from REST/MCP answers; no CALLS/SENDS/
RECEIVES_FROM/DEPLOYED_AS/locality claim from Kubernetes alone." §9 (as amended): Kubernetes
evidence/provenance is itself internal-only and "SHALL NOT appear on any public evidence surface -
neither the REST evidence endpoints nor the canonical snapshot projection."

`tests/integration/test_importer.py::
test_persisted_infrastructure_facts_do_not_leak_into_the_public_snapshot` already proves this
generically, directly against `canonical_snapshot_state()` with a hand-built model. This module
upgrades that proof to the real surface a client actually uses - real REST `TestClient` requests and
real MCP JSON-RPC calls over the real ASGI transport (mirroring `test_mcp_evidence_equivalence.py`/
`test_mcp_service_dependencies_equivalence.py`/`test_mcp_architecture_drift_equivalence.py`'s own
established pattern) - against a real, committed Kubernetes bundle (the checked-in
`tests/fixtures/kubernetes/i2/` fixture, already proven correct by slices 3-5) alongside real
application-layer facts.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import jsonschema
import pytest
from fastapi.testclient import TestClient
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.graph.importer import import_all_sources, import_kubernetes_source
from app.main import create_app
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import FilesystemSourceConfig, KubernetesSourceConfig
from tests.support.negotiated_mcp_client import call_negotiated

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
KUBERNETES_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "kubernetes" / "i2"
SCHEMAS_DIR = REPO_ROOT / "schemas" / "architecture_intelligence" / "v0.5"
ARCHITECTURE_ANSWER_SCHEMA = json.loads(
    (SCHEMAS_DIR / "architecture-answer.schema.json").read_text()
)
EVIDENCE_ANSWER_SCHEMA = json.loads((SCHEMAS_DIR / "evidence-answer.schema.json").read_text())
DRIFT_ANSWER_SCHEMA = json.loads((SCHEMAS_DIR / "drift-answer.schema.json").read_text())

DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)

# The Kubernetes-specific markers that must never appear anywhere in a public REST/MCP payload.
_INTERNAL_MARKERS = (
    "KUBERNETES_WORKLOAD",
    "KUBERNETES_POD",
    "KUBERNETES_NETWORK_SERVICE",
    "KUBERNETES_INGRESS",
    "WORKLOAD_EXISTS",
    "WORKLOAD_OWNS_POD",
    "NETWORK_SERVICE_SELECTS_WORKLOAD",
    "INGRESS_ROUTES_TO_NETWORK_SERVICE",
    "urn:aip:k8s-resource:",
    # ids.evidence_id() lowercases source_type - a Kubernetes evidence id is
    # "evidence:kubernetes:...", not "evidence:KUBERNETES:..." (PR #209 review finding: the
    # original denylist only had the entity/claim-id prefix, missing this lowercase evidence-id
    # form the module's own docstring claims to cover).
    "evidence:kubernetes:",
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _kubernetes_config() -> KubernetesSourceConfig:
    return KubernetesSourceConfig(
        id="checkout-cluster",
        root=KUBERNETES_FIXTURE_DIR,
        envelope_relative_path="envelope.yaml",
        configured_scope_id="checkout-cluster-namespaces",
        cluster_uid="d3adbeef-0000-4000-8000-000000000001",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-kubernetes-capture-agent",
        authority_record="checkout-cluster-capture-authority",
    )


def _import_application_facts(driver) -> None:
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="aip-bundled-examples-v0.5",
            root=EXAMPLES_DIR,
            stable_target_identity="urn:aip:logical-root:bundled-examples",
        ),
    )


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _observation_context() -> dict:
    return {"environment": ENVIRONMENT, "window_start": WINDOW_START, "window_end": WINDOW_END}


def _rest_client(driver) -> TestClient:
    app = create_app()
    app.state.driver = driver
    app.state.llm_provider = None
    app.state.architecture_intelligence_service = _service(driver)
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


def _build_mcp_server_and_app(driver) -> tuple[MCPServer, object]:
    service = _service(driver)
    server = MCPServer(name="test", version="0.5.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    return server, app


async def _call_mcp_tool(client: httpx.AsyncClient, tool_name: str, request_payload: dict) -> dict:
    return await call_negotiated(
        client, origin=_ALLOWED_ORIGIN, name=tool_name, arguments={"request": request_payload}
    )


def _assert_no_internal_markers(serialized: str) -> None:
    for marker in _INTERNAL_MARKERS:
        assert marker not in serialized, f"internal marker {marker!r} leaked into a public payload"


def test_kubernetes_evidence_is_absent_from_the_rest_evidence_list_and_lookup(driver):
    _import_application_facts(driver)
    kubernetes_stats = import_kubernetes_source(
        driver, database=DATABASE, source_config=_kubernetes_config()
    )
    assert kubernetes_stats.committed is True

    with driver.session(database=DATABASE) as session:
        kubernetes_evidence_ids = [
            record["id"]
            for record in session.run(
                "MATCH (e:Evidence {source_type: 'KUBERNETES'}) RETURN e.id AS id"
            )
        ]
    # The Kubernetes source really did write real Evidence nodes - the leakage claim below is
    # meaningful only because there is genuinely something that COULD leak.
    assert kubernetes_evidence_ids

    client = _rest_client(driver)
    snapshot_id, _rows = _service(driver).list_public_evidence()
    list_response = client.get("/api/evidence", params={"snapshot_id": snapshot_id})
    assert list_response.status_code == 200
    listed_ids = {e["id"] for e in list_response.json()}
    assert not listed_ids & set(kubernetes_evidence_ids)
    assert all(e["source_type"] != "KUBERNETES" for e in list_response.json())

    for evidence_id in kubernetes_evidence_ids:
        lookup_response = client.get(
            f"/api/evidence/{evidence_id}", params={"snapshot_id": snapshot_id}
        )
        assert lookup_response.status_code == 404


def test_kubernetes_facts_do_not_leak_into_real_mcp_answers(driver):
    _import_application_facts(driver)
    kubernetes_stats = import_kubernetes_source(
        driver, database=DATABASE, source_config=_kubernetes_config()
    )
    assert kubernetes_stats.committed is True

    dependency_answer = _service(driver).get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": ids.service_id("order-service"),
                "observation_context": _observation_context(),
            }
        )
    )
    dependency_json = dependency_answer.model_dump(mode="json")
    jsonschema.validate(instance=dependency_json, schema=ARCHITECTURE_ANSWER_SCHEMA)
    _assert_no_internal_markers(json.dumps(dependency_json))
    # §11 "Surface": no CALLS/SENDS/RECEIVES_FROM/DEPLOYED_AS/locality claim from Kubernetes alone -
    # every claim in a real dependency answer must trace to a real (non-Kubernetes) evidence ref.
    assert dependency_json["claims"], (
        "expected a real dependency claim to check for leakage against"
    )

    evidence_request = {
        "evidence_refs": sorted(dependency_answer.evidence_refs),
        "snapshot_id": dependency_answer.snapshot.snapshot_id,
    }
    evidence_json = (
        _service(driver).get_evidence(EvidenceRequest.model_validate(evidence_request))
    ).model_dump(mode="json")
    jsonschema.validate(instance=evidence_json, schema=EVIDENCE_ANSWER_SCHEMA)
    assert evidence_json["data"]["missing_evidence_refs"] == []
    _assert_no_internal_markers(json.dumps(evidence_json))

    drift_answer = _service(driver).get_architecture_drift(
        ArchitectureDriftRequest.model_validate(
            {
                "service_id": ids.service_id("order-service"),
                "observation_context": _observation_context(),
            }
        )
    )
    drift_json = drift_answer.model_dump(mode="json")
    jsonschema.validate(instance=drift_json, schema=DRIFT_ANSWER_SCHEMA)
    _assert_no_internal_markers(json.dumps(drift_json))


@pytest.mark.asyncio
async def test_kubernetes_facts_do_not_leak_through_the_real_mcp_transport(driver):
    _import_application_facts(driver)
    kubernetes_stats = import_kubernetes_source(
        driver, database=DATABASE, source_config=_kubernetes_config()
    )
    assert kubernetes_stats.committed is True

    dependency_request = {
        "service_id": ids.service_id("order-service"),
        "observation_context": _observation_context(),
    }
    server, app = _build_mcp_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            dependency_result = await _call_mcp_tool(
                client, "get_service_dependencies", dependency_request
            )
            assert dependency_result["isError"] is False
            jsonschema.validate(
                instance=dependency_result["structuredContent"], schema=ARCHITECTURE_ANSWER_SCHEMA
            )
            _assert_no_internal_markers(json.dumps(dependency_result["structuredContent"]))

            evidence_refs = sorted(dependency_result["structuredContent"]["evidence_refs"])
            evidence_request = {
                "evidence_refs": evidence_refs,
                "snapshot_id": dependency_result["structuredContent"]["snapshot"]["snapshot_id"],
            }
            evidence_result = await _call_mcp_tool(client, "get_evidence", evidence_request)
            assert evidence_result["isError"] is False
            jsonschema.validate(
                instance=evidence_result["structuredContent"], schema=EVIDENCE_ANSWER_SCHEMA
            )
            assert evidence_result["structuredContent"]["data"]["missing_evidence_refs"] == []
            _assert_no_internal_markers(json.dumps(evidence_result["structuredContent"]))

            drift_result = await _call_mcp_tool(
                client, "get_architecture_drift", dependency_request
            )
            assert drift_result["isError"] is False
            jsonschema.validate(
                instance=drift_result["structuredContent"], schema=DRIFT_ANSWER_SCHEMA
            )
            _assert_no_internal_markers(json.dumps(drift_result["structuredContent"]))


def test_configuring_a_kubernetes_source_does_not_change_the_public_snapshot_fingerprint(driver):
    """§9's Draft 0.2 amendment: "merely *configuring* a Kubernetes source [must not] change the
    public snapshot fingerprint every MCP answer's snapshot identity is computed from." Proven here
    against the real committed bundle, not a hand-built model."""
    _import_application_facts(driver)
    with driver.session(database=DATABASE) as session:
        before = canonical_snapshot_state(session, coverage_qualification_enabled=True)
        before_id, _ = snapshot_fingerprint(before)

    kubernetes_stats = import_kubernetes_source(
        driver, database=DATABASE, source_config=_kubernetes_config()
    )
    assert kubernetes_stats.committed is True

    with driver.session(database=DATABASE) as session:
        after = canonical_snapshot_state(session, coverage_qualification_enabled=True)
        after_id, _ = snapshot_fingerprint(after)

    assert after == before
    assert after_id == before_id
