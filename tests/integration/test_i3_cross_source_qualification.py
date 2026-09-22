"""v0.5.0 I3 slice 6: the spec §22 "one frozen cross-source fixture" qualification suite.

`tests/fixtures/deployment/i3-cross-source/` reuses I2's real, independently captured Kubernetes
bundle (`tests/fixtures/kubernetes/i2-independent-capture/` - see that directory's own PROVENANCE.md,
and this fixture's own `PROVENANCE.md` for exactly what's real vs. authored here) combined with an
authored Path B mapping artifact and authored Path C OTel observations, to exercise real Path A +
Path B + Path C data together in one graph - a combination no earlier I3 test exercises (every
earlier integration test proves at most two paths at once).

This file also anchors the §21.7 byte-repeatability and resource/OTel-batch ordering-invariance
cases, and the §21.6 "DEPLOYED_AS creates no CALLS/SENDS/RECEIVES_FROM" and deployment-specific
zero-graph-write cases.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import (
    DeploymentClaim,
    DeploymentResolutionMethod,
    DeploymentResolutionStatus,
    Outcome,
    Producer,
)
from app.architecture_intelligence.request import (
    EvidenceRequest,
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.canonical.model import ArchitectureModel, Service
from app.graph.importer import import_kubernetes_source, import_source
from app.graph.revision_fence import read_revision
from app.graph.schema import ensure_schema
from app.main import create_app
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import KubernetesSourceConfig
from app.sources.service_workload_mapping import load_service_workload_mapping
from app.telemetry.adapter import adapt
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import RuntimeSpan
from app.telemetry.operation_resolver import fetch_operation_candidates
from app.telemetry.queue_resolver import fetch_queue_candidates
from app.telemetry.service_resolver import fetch_candidates
from tests.support.negotiated_mcp_client import call_negotiated

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

DATABASE = "neo4j"
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "deployment" / "i3-cross-source"
KUBERNETES_FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "kubernetes" / "i2-independent-capture"
)
KUBERNETES_SOURCE_ID = "aip-i2-independent-capture"
CLUSTER_UID = "599e90a5-7ab8-426f-807f-92a65dcc8822"
REAL_POD_UID = "658bd464-c78f-4ca2-b7e4-2b04e158f4ee"
ENVIRONMENT = "prod"
# The real captured bundle's own envelope.yaml pins `capturedAt: "2026-09-18T07:38:45Z"` - the
# window below must cover it, since Path C's §9.7 applicability checks the Pod's real captured_at
# alongside the OTel observation's own last_seen.
WINDOW_START = datetime(2026, 9, 18, 0, 0, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 18, 23, 59, 59, tzinfo=UTC)
SPAN_TIME = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC)

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)


def _kubernetes_config() -> KubernetesSourceConfig:
    return KubernetesSourceConfig(
        id=KUBERNETES_SOURCE_ID,
        root=KUBERNETES_FIXTURE_DIR,
        envelope_relative_path="envelope.yaml",
        configured_scope_id="aip-i2-independent-capture-scope",
        cluster_uid=CLUSTER_UID,
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-i2-independent-capture-runbook",
        authority_record="aip-i2-independent-capture-self-declared-authority",
    )


def _reset_graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)


def _import_real_kubernetes_bundle(driver):
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=_kubernetes_config())
    assert stats.committed is True


def _declare_service(driver, *, service_id: str, name: str):
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


def _runtime_demo_span(*, service_name: str, **overrides) -> RuntimeSpan:
    defaults = {
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "span_id": "00f067aa0ba902b7",
        "span_name": "GET /health",
        "span_kind": "SERVER",
        "service_name": service_name,
        "environment": ENVIRONMENT,
        "k8s_pod_uid": REAL_POD_UID,
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


def _load_mapping(name: str):
    document, diagnostics = load_service_workload_mapping(FIXTURE_DIR / name)
    assert diagnostics == ()
    return document


def _service(driver, *, document=None) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(
        driver,
        database=DATABASE,
        producer=PRODUCER,
        service_workload_mapping_document=document,
        configured_kubernetes_sources=[(KUBERNETES_SOURCE_ID, CLUSTER_UID)],
    )


def _dependencies_request(service_id: str) -> ServiceDependenciesRequest:
    return ServiceDependenciesRequest(
        service_id=service_id,
        observation_context=ObservationContextInput(
            environment=ENVIRONMENT, window_start=WINDOW_START, window_end=WINDOW_END
        ),
    )


def _rest_client(driver, *, service: ArchitectureIntelligenceService) -> TestClient:
    app = create_app()
    app.state.driver = driver
    app.state.llm_provider = None
    app.state.architecture_intelligence_service = service
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


def _build_mcp_server_and_app(service: ArchitectureIntelligenceService) -> tuple[MCPServer, object]:
    server = MCPServer(name="test", version="0.5.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    return server, app


async def _call_mcp_get_evidence(client: httpx.AsyncClient, request_payload: dict) -> dict:
    return await call_negotiated(
        client, origin=_ALLOWED_ORIGIN, name="get_evidence", arguments={"request": request_payload}
    )


def test_cross_source_all_three_paths_agree_produces_one_resolved_explicit_claim(driver):
    _reset_graph(driver)
    _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    _import_real_kubernetes_bundle(driver)
    _persist_spans(driver, [_runtime_demo_span(service_name="runtime-demo")])

    service = _service(driver, document=_load_mapping("service-workload-mapping-agree.yaml"))
    answer = service.get_service_dependencies(_dependencies_request("service:runtime-demo"))

    assert answer.outcome == Outcome.ANSWERED
    assert answer.data is not None
    assert len(answer.data.deployment_claim_ids) == 1
    [resolution] = answer.data.deployment_resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
    assert resolution.service_id == "service:runtime-demo"
    assert resolution.workload is not None
    assert resolution.workload.name == "runtime-demo"

    [deployment_claim] = [c for c in answer.claims if isinstance(c, DeploymentClaim)]
    assert deployment_claim.resolution_method == DeploymentResolutionMethod.RESOLVED_EXPLICIT
    # All three paths genuinely contributed - the real annotation (A), the authored mapping (B),
    # and the authored OTel observation (C) - not just the strongest one.
    assert deployment_claim.supporting_methods == [
        DeploymentResolutionMethod.RESOLVED_EXPLICIT,
        DeploymentResolutionMethod.RESOLVED_CONFIGURED,
        DeploymentResolutionMethod.RESOLVED_OBSERVED,
    ]
    # Each path's own evidence is genuinely present in the union - not just the strongest path's.
    # Path A's real captured bundle names the annotation on both the Deployment and its ReplicaSet,
    # so more than one "evidence:kubernetes:" ref is expected; Path B/C each contribute exactly one.
    assert any(ref.startswith("evidence:kubernetes:") for ref in deployment_claim.evidence_refs)
    assert any(ref.startswith("evidence:mapping:") for ref in deployment_claim.evidence_refs)
    assert any(ref.startswith("evidence:otel:") for ref in deployment_claim.evidence_refs)

    # §21.6: DEPLOYED_AS creates no CALLS/SENDS/RECEIVES_FROM - no dependency claim exists for this
    # Kubernetes-only-derived data (no HTTP/messaging spans were ever persisted).
    assert answer.data.dependency_claim_ids == []


def test_cross_source_path_a_vs_path_b_contradiction_produces_conflict(driver):
    _reset_graph(driver)
    _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    _declare_service(driver, service_id="service:runtime-demo-alt", name="runtime-demo-alt")
    _import_real_kubernetes_bundle(driver)

    service = _service(driver, document=_load_mapping("service-workload-mapping-conflict.yaml"))
    answer_a = service.get_service_dependencies(_dependencies_request("service:runtime-demo"))
    answer_b = service.get_service_dependencies(_dependencies_request("service:runtime-demo-alt"))

    for answer in (answer_a, answer_b):
        assert answer.outcome == Outcome.ANSWERED
        assert answer.data is not None
        assert answer.data.deployment_claim_ids == []
        [resolution] = answer.data.deployment_resolutions
        assert resolution.status == DeploymentResolutionStatus.CONFLICT
        assert resolution.candidate_service_ids == [
            "service:runtime-demo",
            "service:runtime-demo-alt",
        ]
    assert [c for c in answer_a.claims if isinstance(c, DeploymentClaim)] == []


def test_cross_source_path_a_vs_path_c_contradiction_produces_conflict(driver):
    """PR #224 review (Copilot): this fixture's own PROVENANCE.md discloses an authored OTel
    observation naming a *disagreeing* `service.name` (`runtime-demo-alt`) specifically to exercise
    a real contradictory Path C case - `test_cross_source_path_a_vs_path_b_contradiction_produces_
    conflict` above never actually persists any OTel span, so that disclosure was inaccurate until
    this test exists. Real Path A (the captured annotation, naming `service:runtime-demo`) vs. real
    Path C (an OTel observation of the real captured Pod, naming `service:runtime-demo-alt`)."""
    _reset_graph(driver)
    _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    _declare_service(driver, service_id="service:runtime-demo-alt", name="runtime-demo-alt")
    _import_real_kubernetes_bundle(driver)
    _persist_spans(driver, [_runtime_demo_span(service_name="runtime-demo-alt")])

    service = _service(driver)
    answer_a = service.get_service_dependencies(_dependencies_request("service:runtime-demo"))
    answer_alt = service.get_service_dependencies(_dependencies_request("service:runtime-demo-alt"))

    for answer in (answer_a, answer_alt):
        assert answer.outcome == Outcome.ANSWERED
        assert answer.data is not None
        assert answer.data.deployment_claim_ids == []
        [resolution] = answer.data.deployment_resolutions
        assert resolution.status == DeploymentResolutionStatus.CONFLICT
        assert resolution.candidate_service_ids == [
            "service:runtime-demo",
            "service:runtime-demo-alt",
        ]
    assert [c for c in answer_a.claims if isinstance(c, DeploymentClaim)] == []


def test_cross_source_byte_repeatability_of_deployment_reconciliation(driver):
    """§21.7: two clean runs against identical persisted graph+mapping+OTel state produce
    byte-identical deployment semantics - modeled on I2's own `test_kubernetes_two_clean_discovery_
    runs_produce_byte_identical_semantic_reports`, but exercised here for I3's own computed
    `DeploymentClaim`/`DeploymentResolution` output, which no pre-existing byte-identical test does
    (the existing generic ones use fixtures with no Kubernetes source at all)."""
    _reset_graph(driver)
    _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    _import_real_kubernetes_bundle(driver)
    _persist_spans(driver, [_runtime_demo_span(service_name="runtime-demo")])

    service = _service(driver, document=_load_mapping("service-workload-mapping-agree.yaml"))
    request = _dependencies_request("service:runtime-demo")
    first = service.get_service_dependencies(request)
    second = service.get_service_dependencies(request)

    assert first.model_dump_json() == second.model_dump_json()
    assert len(first.data.deployment_resolutions) == 1


def test_cross_source_otel_batch_ordering_has_no_effect_on_path_c_resolution(driver):
    """§21.7: reordering spans within one ingested OTLP batch must not change the resulting
    deployment resolution. Two observations of the same real Pod (one exact, one carrying an
    agreeing `k8s.pod.name` consistency attribute) are persisted in each order across two
    independently reset graphs, and the resulting resolutions are compared."""
    span_1 = _runtime_demo_span(service_name="runtime-demo", span_id="00f067aa0ba902b7")
    span_2 = _runtime_demo_span(
        service_name="runtime-demo",
        span_id="00f067aa0ba902b8",
        k8s_pod_name="runtime-demo-real-pod",
    )

    def _run(spans: list[RuntimeSpan]):
        _reset_graph(driver)
        _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
        _import_real_kubernetes_bundle(driver)
        _persist_spans(driver, spans)
        service = _service(driver, document=_load_mapping("service-workload-mapping-agree.yaml"))
        return service.get_service_dependencies(_dependencies_request("service:runtime-demo"))

    forward = _run([span_1, span_2])
    reversed_order = _run([span_2, span_1])
    assert forward.data.deployment_resolutions == reversed_order.data.deployment_resolutions
    assert forward.model_dump_json() == reversed_order.model_dump_json()


def test_cross_source_resource_ordering_has_no_effect_on_deployment_resolution(driver, tmp_path):
    """§21.7: reordering the Kubernetes resource documents in the imported bundle must not change
    the resulting deployment resolution. Parses and reorders the real captured bundle's own resource
    list, but writes it to a fresh temp directory with its own freshly computed envelope digest -
    never mutating the checked-in frozen fixture file itself, which this fixture's own PROVENANCE.md
    requires to stay byte-identical to its own real capture."""
    raw = (KUBERNETES_FIXTURE_DIR / "resources.yaml").read_bytes()
    documents = list(yaml.safe_load_all(raw))

    def _run(root: Path, ordered_documents: list) -> dict:
        _reset_graph(driver)
        _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
        root.mkdir(parents=True, exist_ok=True)
        resource_bytes = yaml.safe_dump_all(ordered_documents).encode()
        (root / "resources.yaml").write_bytes(resource_bytes)
        envelope = {
            "apiVersion": "aip.dev/v1",
            "kind": "KubernetesSourceSnapshot",
            "metadata": {
                "id": "i3-resource-ordering-snapshot",
                "revision": "i3-resource-ordering-revision",
                "producer": "aip-kubernetes-capture-agent",
                "capturedAt": "2026-09-18T07:38:45Z",
            },
            "source": {
                "configuredSourceId": KUBERNETES_SOURCE_ID,
                "configuredScopeId": "aip-i2-independent-capture-scope",
                "clusterUid": CLUSTER_UID,
                "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
                "mode": "CAPTURED_RESOURCE",
            },
            "scope": {
                "namespaces": ["aip-runtime-demo"],
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
                "authorityRef": "i3-resource-ordering-authority",
                "expectedPriorInventoryRevision": None,
            },
            "files": [
                {"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}
            ],
        }
        (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
        config = KubernetesSourceConfig(
            id=KUBERNETES_SOURCE_ID,
            root=root,
            envelope_relative_path="envelope.yaml",
            configured_scope_id="aip-i2-independent-capture-scope",
            cluster_uid=CLUSTER_UID,
            evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
            authorized_producer="aip-kubernetes-capture-agent",
            authority_record="i3-resource-ordering-authority",
        )
        stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
        assert stats.committed is True
        service = _service(driver)
        answer = service.get_service_dependencies(_dependencies_request("service:runtime-demo"))
        return answer.model_dump(mode="json")

    forward = _run(tmp_path / "forward", documents)
    reversed_answer = _run(tmp_path / "reversed", list(reversed(documents)))
    # Full-answer equality (PR #224 review, user's own review round 1): comparing only
    # `resolution.status` let a reordering-induced change to ids/workload/methods/evidence pass
    # unnoticed - this now matches the PR's own reconciliation claim of whole-answer comparison.
    assert forward == reversed_answer
    [resolution] = forward["data"]["deployment_resolutions"]
    assert resolution["status"] == DeploymentResolutionStatus.RESOLVED_EXPLICIT.value
    # The checked-in frozen fixture itself must remain untouched by this test.
    assert (KUBERNETES_FIXTURE_DIR / "resources.yaml").read_bytes() == raw


def test_cross_source_deployment_resolving_read_causes_zero_graph_writes(driver):
    """§21.6: a real Path A/B/C-resolving `get_service_dependencies` read leaves the revision fence
    unchanged - deployment-specific version of the generic gate
    `test_mcp_i1_zero_write_completion_gate.py` proves, which uses no Kubernetes source and so never
    actually exercises a deployment-resolving read."""
    _reset_graph(driver)
    _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    _import_real_kubernetes_bundle(driver)
    _persist_spans(driver, [_runtime_demo_span(service_name="runtime-demo")])

    service = _service(driver, document=_load_mapping("service-workload-mapping-agree.yaml"))
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)
    answer = service.get_service_dependencies(_dependencies_request("service:runtime-demo"))
    assert answer.outcome == Outcome.ANSWERED
    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert before == after


# --- PR #224 review (user's own review): §21.6 requires Path B/Path C deployment evidence to -----
# round-trip through the public adapters (REST + negotiated MCP), not just Path A (the only path
# `test_api_architecture_intelligence_equivalence.py`/`test_mcp_evidence_equivalence.py`'s own
# deployment-evidence tests cover).


def test_cross_source_evidence_resolve_rest_matches_service_for_path_b_and_c_evidence(driver):
    _reset_graph(driver)
    _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    _import_real_kubernetes_bundle(driver)
    _persist_spans(driver, [_runtime_demo_span(service_name="runtime-demo")])

    service = _service(driver, document=_load_mapping("service-workload-mapping-agree.yaml"))
    dependency_answer = service.get_service_dependencies(
        _dependencies_request("service:runtime-demo")
    )
    [deployment_claim] = [c for c in dependency_answer.claims if isinstance(c, DeploymentClaim)]
    path_b_and_c_refs = sorted(
        ref
        for ref in deployment_claim.evidence_refs
        if ref.startswith(("evidence:mapping:", "evidence:otel:"))
    )
    assert any(ref.startswith("evidence:mapping:") for ref in path_b_and_c_refs)
    assert any(ref.startswith("evidence:otel:") for ref in path_b_and_c_refs)

    evidence_request = EvidenceRequest.model_validate(
        {
            "evidence_refs": path_b_and_c_refs,
            "snapshot_id": dependency_answer.snapshot.snapshot_id,
        }
    )
    direct = service.get_evidence(evidence_request).model_dump(mode="json")
    assert direct["data"]["missing_evidence_refs"] == []

    client = _rest_client(driver, service=service)
    response = client.post(
        "/api/evidence/resolve",
        json={
            "evidence_refs": path_b_and_c_refs,
            "snapshot_id": dependency_answer.snapshot.snapshot_id,
        },
    )
    assert response.status_code == 200
    assert response.json() == direct


@pytest.mark.asyncio
async def test_cross_source_evidence_resolve_mcp_matches_service_for_path_b_and_c_evidence(driver):
    _reset_graph(driver)
    _declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    _import_real_kubernetes_bundle(driver)
    _persist_spans(driver, [_runtime_demo_span(service_name="runtime-demo")])

    service = _service(driver, document=_load_mapping("service-workload-mapping-agree.yaml"))
    dependency_answer = service.get_service_dependencies(
        _dependencies_request("service:runtime-demo")
    )
    [deployment_claim] = [c for c in dependency_answer.claims if isinstance(c, DeploymentClaim)]
    path_b_and_c_refs = sorted(
        ref
        for ref in deployment_claim.evidence_refs
        if ref.startswith(("evidence:mapping:", "evidence:otel:"))
    )

    evidence_request = EvidenceRequest.model_validate(
        {
            "evidence_refs": path_b_and_c_refs,
            "snapshot_id": dependency_answer.snapshot.snapshot_id,
        }
    )
    direct_json = service.get_evidence(evidence_request).model_dump(mode="json")
    assert direct_json["data"]["missing_evidence_refs"] == []

    server, app = _build_mcp_server_and_app(service)
    payload = {
        "evidence_refs": path_b_and_c_refs,
        "snapshot_id": dependency_answer.snapshot.snapshot_id,
    }
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp_get_evidence(client, payload)
            assert result["isError"] is False
            assert result["structuredContent"] == direct_json
