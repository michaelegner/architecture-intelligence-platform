"""Execute the frozen I4.1 gaps. Synthetic worlds, never the I5 capture."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from google.protobuf import json_format
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import Span

from app.architecture_intelligence.request import (
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.importer import import_all_sources, import_kubernetes_source
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import FilesystemSourceConfig, KubernetesSourceConfig
from app.sources.service_workload_mapping import (
    ServiceWorkloadMappingDocument,
    ServiceWorkloadMappingEntry,
    load_service_workload_mapping,
)
from evaluation.fixture_setup import _test_client
from evaluation.loader import discover_scenarios, load_scenario
from evaluation.runner import run_scenario
from tests.integration.locality_oracle import world
from tests.integration.test_locality_oracle import CASES, K_REQUEST, _ask, _service
from tests.integration.test_locality_rehearsal_replay import _hex_ids_to_base64
from tests.integration.test_qsh_demo_smoke import _check_ready
from tests.integration.test_scoped_applicability import _import

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((ROOT / "docs/specifications/0.6.0/i4-vectors/expected-i4.json").read_text())
BRIDGES = {case["id"]: case for case in VECTORS["cases"]}


def _assessments(answer):
    return [
        (locality, assessment)
        for locality in (answer.get("data") or {}).get("localities", [])
        for assessment in locality["assessments"]
    ]


def _scoped_client(driver):
    client = _test_client(driver, database=world.DATABASE)
    client.app.state.settings = Settings(
        config=AppConfig.model_validate(
            {
                "graph": {"database": world.DATABASE},
                "telemetry": {
                    "http-correlation": {"enabled": True},
                    "scoped-evidence": {"enabled": True},
                    "coverage": {"qualification-enabled": True},
                },
            }
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored"),
    )
    return client


def _assert_p3(case, steps):
    """Every B01 assertion is checked, including the scoped forbidden-lineage assertions."""
    for check in case["assert"]:
        answer = steps[check["step"]]
        kind = check["kind"]
        if kind == "positive":
            matches = [
                a
                for loc, a in _assessments(answer)
                if loc["workload"]["uid"] == check["workload_uid"]
                and a["object_operation_id"] == check["operation"]
            ]
            assert len(matches) == 1, check
            assessment = matches[0]
            assert assessment["applicability"] == "APPLICABLE"
            assert assessment["qualification"] in {"CONFIRMED", "OBSERVED_ONLY"}
            assert set(assessment["observation"]["evidence_ids"]) == set(
                check["evidence_ids_exactly"]
            )
            if "capture_revisions_exactly" in check:
                assert {c["revision"] for c in assessment["selected_captures"]} == set(
                    check["capture_revisions_exactly"]
                )
        elif kind == "unresolved":
            candidates = [
                c
                for c in answer["data"]["candidates"]
                if c["v2_evidence_id"] == check["v2_evidence_id"]
            ]
            assert len(candidates) == 1
            assert candidates[0]["disposition"] in {"UNRESOLVED", "INAPPLICABLE"}
            assert all(p["disposition"] != "APPLICABLE" for p in candidates[0]["pairs"])
            assert all(
                check["v2_evidence_id"] not in a["observation"]["evidence_ids"]
                for _, a in _assessments(answer)
            )
        elif kind == "localities_exactly":
            assert {loc["workload"]["uid"] for loc in answer["data"]["localities"]} == set(
                check["workload_uids"]
            )
        elif kind == "compare_only_in":
            comparison = answer["data"]["comparison"]
            side = next(
                i
                for i, scope in enumerate(comparison["scopes"])
                if scope["workload"]["uid"] == check["workload_uid"]
            )
            own, other = (
                ("only_in_first", "only_in_second")
                if side == 0
                else ("only_in_second", "only_in_first")
            )
            assert check["operation"] in {m["operation_id"] for m in comparison[own]}
            assert check["operation"] not in {
                m["operation_id"] for m in comparison[other] + comparison["in_both"]
            }
        elif kind == "refusal":
            assert answer["data"] is None
            assert [l["code"] for l in answer["limitations"]] == [check["code"]]
        elif kind == "snapshot_differs_from_step":
            assert (
                answer["snapshot"]["snapshot_id"]
                != steps[check["other"]]["snapshot"]["snapshot_id"]
            )
        elif kind == "evidence_refs_resolve":
            entries = answer["data"]["entries"]
            assert entries and all(e["status"] == "RESOLVED" for e in entries)
            resolved = {e["ref"] for e in entries if e["ref_kind"] == "SCOPED_V2"}
            assert resolved == set(check["resolve_to"])
            assert not any(eid in json.dumps(entries) for eid in check["never_resolve_to"])
        elif kind == "forbidden":
            if "v2_evidence_id" in check:
                operation = check["scope"].removeprefix("assessment of ")
                op_id = case["inputs"]["v2"]["P3" if operation == "O2" else "P1"]["object_id"]
                for locality, assessment in _assessments(answer):
                    if assessment["object_operation_id"] == op_id:
                        assert check["v2_evidence_id"] not in json.dumps(assessment)
                        if operation == "O1":
                            assert (
                                steps["p3_capture_ref"] not in assessment["capture_evidence_refs"]
                            )
                        groups = [
                            g for g in locality["provider_groups"] if op_id in g["operation_ids"]
                        ]
                        assert all(check["v2_evidence_id"] not in json.dumps(g) for g in groups)
            elif "compare" in check:
                operation = case["inputs"]["v2"]["P1"]["object_id"]
                assert operation not in {
                    m["operation_id"] for m in answer["data"]["comparison"]["in_both"]
                }
                current = case["steps"][2]["request"]["caller_localities"][0]["uid"]
                assert not any(
                    loc["workload"]["uid"] == current and a["object_operation_id"] == operation
                    for loc, a in _assessments(answer)
                )
            elif "workload_uid" in check:
                assert not any(
                    loc["workload"]["uid"] == check["workload_uid"]
                    and a["object_operation_id"] == check["operation"]
                    for loc, a in _assessments(answer)
                )
            else:
                assert (
                    check["what"]
                    == "NOT_OBSERVED_IN_WINDOW or verified absence for any Workload-local O1 or O2"
                )
                assert "NOT_OBSERVED_IN_WINDOW" not in json.dumps(answer)
        else:
            raise AssertionError(f"unimplemented frozen assertion: {check}")


@pytest.mark.parametrize("case_id", ["B01a", "B01b"])
def test_p3_bridge(driver, tmp_path, case_id):
    case = BRIDGES[case_id]
    inputs = case["inputs"]
    world.clean(driver)
    world._declare(driver, inputs["declarations"])

    def capture(index):
        cap = inputs["captures"][index]
        # Both stages deliberately use ONE configured source and physical root.
        spec = world._spec(cap, cap["pods"])
        spec["source_id"] = "i4-p3"
        return _import(driver, tmp_path, **spec)

    capture(0)
    world._persist(driver, {"v2": [inputs["v2"]["P1"], inputs["v2"]["P2"]]}, reverse=False)
    steps = {1: _ask(driver, case["steps"][0]["request"])}
    selected = capture(1)
    world._persist(driver, {"v2": [inputs["v2"]["P3"]]}, reverse=False)
    for step in case["steps"][1:4]:
        steps[step["step"]] = _ask(driver, step["request"])
    p3 = inputs["v2"]["P3"]
    assessment = next(
        a for _, a in _assessments(steps[2]) if p3["id"] in a["observation"]["evidence_ids"]
    )
    capture_ref = world._pod_capture_ref(
        driver, inputs, {"SOURCE:C2": selected.source_instance_id}, "C2/P3"
    )
    assert capture_ref in assessment["capture_evidence_refs"]
    steps["p3_capture_ref"] = capture_ref
    evidence_request = copy.deepcopy(case["steps"][4]["request"])
    evidence_request["refs"] = sorted([p3["id"], capture_ref])
    evidence_request["snapshot_id"] = steps[2]["snapshot"]["snapshot_id"]
    steps[5] = _ask(driver, evidence_request)
    stale_request = copy.deepcopy(case["steps"][5]["request"])
    stale_request["snapshot_id"] = steps[1]["snapshot"]["snapshot_id"]
    steps[6] = _ask(driver, stale_request)
    _assert_p3(case, steps)


def test_b02_mapping_and_unscoped_observation_mint_no_local_calls(driver, tmp_path):
    inputs = copy.deepcopy(CASES["X04"]["inputs"])
    inputs["v2"] = []
    world.build(driver, tmp_path, inputs)
    client = _scoped_client(driver)
    # Frozen synthetic CLIENT/SERVER pair, deliberately without caller Pod identity.
    from tests.integration.test_telemetry_api import _client_resource_spans, _server_resource_spans

    request = ExportTraceServiceRequest(
        resource_spans=[
            _client_resource_spans(client_service="orders", method="GET", route="/prices"),
            _server_resource_spans(server_service="pricing", method="GET", route="/prices"),
        ]
    )
    from datetime import UTC, datetime

    timestamp = int(datetime(2026, 9, 28, 9, tzinfo=UTC).timestamp()) * 1_000_000_000
    for resource in request.resource_spans:
        for scope in resource.scope_spans:
            for span in scope.spans:
                span.start_time_unix_nano = timestamp
                span.end_time_unix_nano = timestamp + 1_000_000
    assert (
        client.post(
            "/v1/traces",
            content=request.SerializeToString(),
            headers={"Content-Type": "application/x-protobuf"},
        ).status_code
        == 200
    )
    separate_identity = copy.deepcopy(request.resource_spans[0])
    separate_identity.scope_spans[0].spans[0].kind = Span.SPAN_KIND_INTERNAL
    pod = inputs["captures"][0]["pods"][0]
    separate_identity.resource.attributes.extend(
        [
            KeyValue(key=key, value=AnyValue(string_value=value))
            for key, value in {
                "deployment.environment.name": "production",
                "k8s.pod.uid": pod["uid"],
                "k8s.pod.name": pod["name"],
                "k8s.namespace.name": "shop",
                "k8s.cluster.uid": inputs["captures"][0]["cluster_uid"],
            }.items()
        ]
    )
    identity_request = ExportTraceServiceRequest(resource_spans=[separate_identity])
    assert (
        client.post(
            "/v1/traces",
            content=identity_request.SerializeToString(),
            headers={"Content-Type": "application/x-protobuf"},
        ).status_code
        == 200
    )
    with driver.session(database=world.DATABASE) as session:
        assert (
            session.run("MATCH (n:RuntimeIdentityObservation) RETURN count(n) AS c").single()["c"]
            == 1
        )
    mapping = ServiceWorkloadMappingDocument(
        artifact_id="i4-b02",
        artifact_revision="1",
        locator="i4/mapping.yaml",
        content_digest=hashlib.sha256(b"i4-b02").hexdigest(),
        entries=(
            ServiceWorkloadMappingEntry(
                "i4-b02-orders",
                "service:orders",
                world._source_id(inputs["captures"][0]["label"]),
                inputs["captures"][0]["cluster_uid"],
                "apps",
                "Deployment",
                "shop",
                "orders",
            ),
        ),
    )
    service = ArchitectureIntelligenceService(
        driver,
        database=world.DATABASE,
        producer=_service(driver)._producer,
        service_workload_mapping_document=mapping,
        configured_kubernetes_sources=(
            (mapping.entries[0].kubernetes_source_id, mapping.entries[0].cluster_uid),
        ),
    )
    local = _ask(driver, BRIDGES["B02"]["steps"][0]["request"], service=service)
    assert local["data"]["localities"] == []
    assert local["data"]["candidates"] == []
    legacy = service.get_service_dependencies(
        ServiceDependenciesRequest(
            service_id="service:orders",
            observation_context=ObservationContextInput(
                environment="production",
                window_start="2026-09-28T00:00:00Z",
                window_end="2026-09-28T23:59:59Z",
            ),
        )
    ).model_dump(mode="json")
    assert local["snapshot"] == legacy["snapshot"]
    assert any(c["predicate"] == "DEPLOYED_AS" for c in legacy["claims"])


def test_b03_service_declaration_creates_no_regional_assertion(driver, tmp_path):
    world.build(driver, tmp_path, CASES["X04"]["inputs"])
    answer = _ask(driver, BRIDGES["B03"]["steps"][0]["request"])
    assert answer["data"]["localities"]
    assert not ({"region", "tenant"} & _keys(answer))
    for _, assessment in _assessments(answer):
        assert assessment["observation"]["evidence_ids"]
        assert assessment["applicability"] == "APPLICABLE"


def _keys(value):
    if isinstance(value, dict):
        return set(value).union(*(_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(v) for v in value))
    return set()


def test_b04_independent_edges_do_not_establish_target_placement_or_flow(driver, tmp_path):
    inputs = copy.deepcopy(CASES["X04"]["inputs"])
    second = copy.deepcopy(inputs["v2"][0])
    second["subject_id"] = "service:pricing"
    second["object_id"] = "operation:service:tax:GET:/tax"
    # A captured caller for pricing, without linking it to orders' target Operation.
    pod = copy.deepcopy(inputs["captures"][0]["pods"][0])
    pod["uid"] = "bbbbbbbb-0000-4000-8000-000000000099"
    pod["name"] = "pricing-p99"
    pod["owner"] = {
        "kind": "Deployment",
        "name": "pricing",
        "uid": "aaaaaaaa-0000-4000-8000-000000000099",
    }
    inputs["captures"][0]["pods"].append(pod)
    second["caller_pod_uid"] = pod["uid"]
    second["client_resource"] = {
        "k8s.namespace.name": "shop",
        "k8s.pod.name": pod["name"],
        "k8s.deployment.name": "pricing",
    }
    second["id"] = world.v2_id(second)
    inputs["v2"].append(second)
    inputs["declarations"]["services"].append("service:tax")
    inputs["declarations"]["declared_operations"].append(
        {"id": second["object_id"], "provider": "service:tax"}
    )
    world.build(driver, tmp_path, inputs)
    answer = _ask(driver, BRIDGES["B04"]["steps"][0]["request"])
    pricing = _ask(driver, {**K_REQUEST, "subject_service_id": "service:pricing"})
    assert pricing["data"]["localities"]
    assert answer["data"]["localities"]
    assert all(loc["target_runtime_scope"] == "UNKNOWN" for loc in answer["data"]["localities"])
    assert not (
        {"path", "flow", "business_outcome", "target_locality", "target_workload"} & _keys(answer)
    )
    assert second["object_id"] not in {a["object_operation_id"] for _, a in _assessments(answer)}


def test_b05_narrative_and_intent_cannot_change_current_state(driver, tmp_path):
    from app.architecture_intelligence.canonical_json import canonical_json_bytes
    from app.ingestion.orchestrator import run_filesystem_discovery

    world.build(driver, tmp_path, CASES["X04"]["inputs"])
    before = _ask(driver, BRIDGES["B05"]["steps"][0]["request"])
    root = tmp_path / "narrative"
    directory = root / "orders"
    directory.mkdir(parents=True)
    text = "# Architecture intent\norders must call tax. Agent narrative: orders calls tax.\n"
    (directory / "intent.md").write_text(text)
    (directory / "narrative.md").write_text(text)
    config = FilesystemSourceConfig(id="i4-b05", root=root)
    assert run_filesystem_discovery(config).source_outcomes == {}
    # A discoverable filename still cannot give narrative semantic authority.
    (directory / "architecture.yaml").write_text(json.dumps({"intent": text, "narrative": text}))
    rejected = import_all_sources(driver, database=world.DATABASE, source_config=config)
    assert not rejected.committed
    after = _ask(driver, BRIDGES["B05"]["steps"][2]["request"])
    assert canonical_json_bytes(before) == canonical_json_bytes(after)


def test_b06_frozen_quarkus_replay_has_no_locality_or_kafka_observation(driver):
    world.clean(driver)
    dossier = ROOT / "docs/real-world-validation/v0.5.0/quarkus-super-heroes/runtime"
    demo = ROOT / "examples/quarkus-super-heroes-demo"
    for source_id, root in [
        ("qsh-v0.5-declarations", dossier / "declarations"),
        ("qsh-demo-overlay", demo / "overlay"),
    ]:
        assert import_all_sources(
            driver,
            database=world.DATABASE,
            source_config=FilesystemSourceConfig(id=source_id, root=root),
        ).committed
    cluster = KubernetesSourceConfig(
        id="qsh-k8s-namespaced",
        root=dossier / "k8s/namespaced",
        envelope_relative_path="envelope.yaml",
        configured_scope_id="qsh-k8s-namespaced-scope",
        cluster_uid="qsh-i5-declared-deployment-target",
        evidence_mode="DECLARED_MANIFEST",
        authorized_producer="aip-i5-quarkus-dossier",
        authority_record="qsh-i5-dossier-freeze-authority",
    )
    assert import_kubernetes_source(
        driver, database=world.DATABASE, source_config=cluster
    ).committed
    client = _scoped_client(driver)
    payload = json.loads((demo / "otlp.json").read_text())
    _hex_ids_to_base64(payload)
    request = json_format.ParseDict(payload, ExportTraceServiceRequest())
    assert (
        client.post(
            "/v1/traces",
            content=request.SerializeToString(),
            headers={"Content-Type": "application/x-protobuf"},
        ).status_code
        == 200
    )
    mapping, diagnostics = load_service_workload_mapping(dossier / "mapping.yaml")
    assert not diagnostics
    service = ArchitectureIntelligenceService(
        driver,
        database=world.DATABASE,
        producer=_service(driver)._producer,
        service_workload_mapping_document=mapping,
        configured_kubernetes_sources=((cluster.id, cluster.cluster_uid),),
    )
    answer = _ask(driver, BRIDGES["B06"]["steps"][0]["request"], service=service)
    assert answer["data"]["localities"] == []
    with driver.session(database=world.DATABASE) as session:
        assert session.run("MATCH (n:ScopedObservedCallV2) RETURN count(n) AS c").single()["c"] == 0
    checker = _check_ready()
    legacy = service.get_service_dependencies(
        ServiceDependenciesRequest(
            service_id=checker.SERVICE_ID,
            observation_context=ObservationContextInput.model_validate(checker.CONTEXT),
        )
    ).model_dump(mode="json")
    assert checker.check_answer(legacy) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id", [f"Q{i:02}" for i in range(1, 9)])
async def test_frozen_invalid_requests_are_rejected_by_both_adapters(driver, case_id):
    from tests.integration.test_locality_surface_parity import _mcp, _rest

    request = CASES[case_id]["request"]
    service = _service(driver)
    assert _rest(service, request).status_code == 422
    assert (await _mcp(service, request))["isError"] is True


@pytest.mark.parametrize(
    "scenario_path", discover_scenarios(ROOT / "evaluation/scenarios"), ids=lambda path: path.name
)
def test_legacy_relation_evaluator(driver, scenario_path):
    scenario = load_scenario(scenario_path)
    result = run_scenario(driver, database=world.DATABASE, scenario=scenario)
    assert result.passed, result.mismatches
