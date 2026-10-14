"""v0.7.0 I1.4: the APISIX gateway source end to end below the graph - ids, the ConfiguredAccess
interpretation against the independent I1.1 vectors, and the production discoverer/adapter/run path
(registration binding, rejection outcomes, bounds, replay determinism). No Docker, no Neo4j."""

import copy
import json
from pathlib import Path

import pytest

from app.canonical import ids
from app.canonical.gateway import (
    configured_access_id,
    gateway_consumer_id,
    gateway_route_id,
    gateway_service_id,
    gateway_source_evidence_id,
)
from app.ingestion.apisix_discoverer import MAX_CAPTURE_BYTES, MAX_RESOURCE_OBJECTS
from app.ingestion.orchestrator import default_registry, run_apisix_discovery
from app.sources.apisix_contract import ApisixCaptureEnvelope, source_revision
from app.sources.apisix_mapping import map_capture
from app.sources.identity import apisix_source_instance_id
from app.sources.inventory import InventoryStatus
from app.sources.model import ApisixSourceConfig, DiagnosticCode, IngestionResult

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i1-vectors"
CANARY = "CANARY-SECRET-VALUE"


def _load(name: str) -> dict:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _full_document(patch: dict | None = None, *, case_capture: dict | None = None) -> dict:
    document: dict = copy.deepcopy(_load("configured-access.json")["base_capture"])
    document.update(
        consumers=[], routes=[], services=[], upstreams=[], plugin_configs=[],
        consumer_groups=[], global_rules=[],
    )  # fmt: skip
    for name, value in (case_capture or {}).items():
        document[name] = copy.deepcopy(value)
    for name, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(document.get(name), dict):
            document[name].update(value)
        else:
            document[name] = value
    return document


def _config(tmp_path: Path, *, instance: str = "gw-prod-1", source_id: str = "apisix-prod"):
    root = tmp_path / source_id
    root.mkdir(exist_ok=True)
    return ApisixSourceConfig(id=source_id, root=root, gateway_instance_id=instance)


def _write(config: ApisixSourceConfig, document: object) -> None:
    (config.root / config.capture_relative_path).write_text(json.dumps(document))


def _run(config: ApisixSourceConfig, **kwargs):
    return run_apisix_discovery(config, **kwargs)


def _only_outcome(run):
    [outcome] = run.source_outcomes.values()
    return outcome.outcome


# ------------------------------------------------------------------------------------------
# ids (vectors V01-V07, V13)
# ------------------------------------------------------------------------------------------


def test_ids_match_the_frozen_vectors() -> None:
    by_id = {v["id"]: v for v in _load("ids.json")["vectors"]}
    v1, v2 = by_id["V01"], by_id["V02"]
    assert gateway_consumer_id(**v1["inputs"]) == v1["expected"]
    assert gateway_consumer_id(**v2["inputs"]) == v2["expected"] != v1["expected"]
    v3, v4, v5 = by_id["V03"], by_id["V04"], by_id["V05"]
    assert gateway_route_id(**v3["inputs"]) == v3["expected"]
    assert gateway_service_id(**v4["inputs"]) == v4["expected"]
    assert gateway_route_id("gw-prod-1", "orders") == v5["expected"]["route"]
    assert gateway_service_id("gw-prod-1", "orders") == v5["expected"]["service"]
    assert v5["expected"]["route"] != v5["expected"]["service"]
    v6 = by_id["V06"]
    assert configured_access_id(**v6["inputs"]) == v6["expected"]
    v7 = by_id["V07"]
    assert (
        apisix_source_instance_id(
            configured_apisix_source_id=v7["inputs"]["configured_source_id"],
            gateway_instance_id=v7["inputs"]["gateway_instance_id"],
        )
        == v7["expected"]
    )
    v13 = by_id["V13"]["expected"]
    assert [
        gateway_source_evidence_id("gw-prod-1", revision) for revision in v13["revisions"]
    ] == v13["evidence_ids"]
    assert source_revision("3.19.0", 18) == v13["revisions"][0]


# ------------------------------------------------------------------------------------------
# ConfiguredAccess interpretation against the independent vectors (C01-C15)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _load("configured-access.json")["cases"], ids=lambda c: c["id"])
def test_configured_access_vectors(case: dict) -> None:
    envelope = ApisixCaptureEnvelope.model_validate(_full_document(case_capture=case["capture"]))
    mapping = map_capture(envelope)
    instance = envelope.gateway_instance_id
    username_by_id = {
        gateway_consumer_id(instance, c.username): c.username for c in envelope.consumers
    }
    route_by_id = {gateway_route_id(instance, r.id): r.id for r in envelope.routes}
    got_access = sorted(
        (username_by_id[a.consumer_id], route_by_id[a.route_id], a.rule_kind)
        for a in mapping.accesses
    )
    expected = case["expected"]
    assert got_access == sorted(
        (a["consumer"], a["route"], a["rule_kind"]) for a in expected["configured_access"]
    )
    assert sorted((item.code, item.subject) for item in mapping.limitations) == sorted(
        (item["code"], item["subject"]) for item in expected["limitations"]
    )
    assert all(a.evidence_ids == [mapping.source_evidence.id] for a in mapping.accesses)


def test_gateway_entities_are_distinct_from_application_services_and_infer_nothing() -> None:
    case = next(c for c in _load("configured-access.json")["cases"] if c["id"] == "C09")
    document = _full_document(case_capture=case["capture"])
    document["services"] = [
        {"id": "orders", "plugins": {}}
    ]  # a name an application Service may share
    model_services = map_capture(ApisixCaptureEnvelope.model_validate(document)).services
    [service] = model_services
    assert service.id.startswith("gateway-service:owned:")
    assert service.id != ids.service_id("orders") != "orders"
    # the mapping produces carriers only: no Route<->Operation or gateway<->Service association
    assert not hasattr(map_capture(ApisixCaptureEnvelope.model_validate(document)), "relations")


# ------------------------------------------------------------------------------------------
# the production discoverer / adapter / run
# ------------------------------------------------------------------------------------------


def test_the_registry_resolves_exactly_one_adapter_for_a_gateway_source(tmp_path) -> None:
    config = _config(tmp_path)
    _write(config, _full_document())
    run = _run(config)
    assert run.commit_eligible and run.inventory_status is InventoryStatus.COMPLETE
    [source_id] = run.source_outcomes
    assert source_id == apisix_source_instance_id(
        configured_apisix_source_id="apisix-prod", gateway_instance_id="gw-prod-1"
    )
    assert default_registry().adapter_for  # registered alongside the other declared-source adapters


def test_an_accepted_capture_maps_and_replays_deterministically(tmp_path) -> None:
    config = _config(tmp_path)
    case = next(c for c in _load("configured-access.json")["cases"] if c["id"] == "C14")
    _write(config, _full_document(case_capture=case["capture"]))
    first, second = _run(config), _run(config)
    out1, out2 = _only_outcome(first), _only_outcome(second)
    assert out1.result is IngestionResult.ACCEPTED
    assert out1.model == out2.model and out1.semantic_input_digest == out2.semantic_input_digest
    assert len(out1.model.gateway_configured_accesses) == 3
    assert out1.model.gateway_source_evidence[0].source_revision == "apisix:3.19.0+etcd:18"
    # nothing public: no Service/Operation/Relation/Provenance is emitted
    assert not (out1.model.services or out1.model.operations or out1.model.relations)
    assert not out1.model.provenance


def test_limitations_make_the_source_accepted_with_limitations(tmp_path) -> None:
    config = _config(tmp_path)
    case = next(c for c in _load("configured-access.json")["cases"] if c["id"] == "C05")
    _write(config, _full_document(case_capture=case["capture"]))
    run = _run(config)
    outcome = _only_outcome(run)
    assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.GW_CONFIGURATION_LIMITATIONS]
    assert run.commit_eligible  # limitations never block a commit


def _expected_result(name: str) -> IngestionResult:
    return IngestionResult(name)


@pytest.mark.parametrize("case", _load("capture-rejections.json")["cases"], ids=lambda c: c["id"])
def test_rejection_vectors_through_the_production_discoverer(case: dict, tmp_path) -> None:
    expected = case["expected"]
    config = _config(tmp_path)
    if case["spec_case"] == "duplicate-instance":
        other = _config(tmp_path, source_id="apisix-dr")  # same gateway_instance_id
        _write(config, _full_document())
        _write(other, _full_document())
        for cfg in (config, other):
            run = _run(cfg, duplicate_gateway_instance=True)
            assert not run.commit_eligible and run.inventory_status is InventoryStatus.PARTIAL
            outcome = _only_outcome(run)
            assert outcome.result is IngestionResult.REJECTED_CONFLICT
            assert [d.code.value for d in outcome.diagnostics] == [expected["code"]]
        return
    patch = case["capture_patch"]
    document = _full_document(patch)
    _write(config, document)
    run = _run(config)
    outcome = _only_outcome(run)
    assert not run.commit_eligible and run.inventory_status is InventoryStatus.PARTIAL
    assert outcome.result is _expected_result(expected["result"])
    assert [d.code.value for d in outcome.diagnostics] == [expected["code"]]
    assert outcome.model.gateway_consumers == [] and outcome.semantic_input_digest is None
    rendered = repr(outcome.diagnostics) + repr(run.diagnostics)
    for forbidden in expected.get("diagnostic_must_not_contain", []):
        assert forbidden not in rendered
    assert CANARY not in rendered


def test_a_capture_for_another_gateway_instance_is_rejected(tmp_path) -> None:
    config = _config(tmp_path, instance="gw-prod-1")
    _write(config, _full_document({"gateway_instance_id": "gw-other"}))
    outcome = _only_outcome(_run(config))
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.GW_INSTANCE_MISMATCH]


def test_same_username_on_two_instances_gives_distinct_consumers(tmp_path) -> None:
    ids_ = set()
    for instance in ("gw-prod-1", "gw-prod-2"):
        config = _config(tmp_path, instance=instance, source_id=f"src-{instance}")
        _write(
            config,
            _full_document(
                {
                    "gateway_instance_id": instance,
                    "consumers": [{"username": "alice", "credential_ids": []}],
                }
            ),
        )
        [consumer] = _only_outcome(_run(config)).model.gateway_consumers
        ids_.add(consumer.id)
    assert len(ids_) == 2


def test_missing_invalid_and_oversized_captures_are_rejected_not_raised(tmp_path) -> None:
    config = _config(tmp_path)
    run = _run(config)  # no capture file at all
    assert _only_outcome(run).result is IngestionResult.REJECTED_INVALID
    (config.root / config.capture_relative_path).write_text("{not json")
    assert _only_outcome(_run(config)).result is IngestionResult.REJECTED_INVALID
    (config.root / config.capture_relative_path).write_text('{"schema": 1, "schema": 2}')
    assert _only_outcome(_run(config)).result is IngestionResult.REJECTED_INVALID  # duplicate key
    big = _full_document()
    big["consumers"] = [
        {"username": f"u{i}", "credential_ids": []} for i in range(MAX_RESOURCE_OBJECTS + 1)
    ]
    _write(config, big)
    outcome = _only_outcome(_run(config))
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.GW_CAPTURE_LIMIT_EXCEEDED]
    deep: object = "x"
    for _ in range(80):
        deep = {"a": deep}
    (config.root / config.capture_relative_path).write_text(json.dumps(deep))
    assert _only_outcome(_run(config)).result is IngestionResult.REJECTED_UNSUPPORTED
    (config.root / config.capture_relative_path).write_bytes(b" " * (MAX_CAPTURE_BYTES + 1))
    assert _only_outcome(_run(config)).result is IngestionResult.REJECTED_UNSUPPORTED


def test_a_missing_root_fails_the_run_and_a_traversing_path_is_rejected(tmp_path) -> None:
    config = ApisixSourceConfig(
        id="x", root=tmp_path / "does-not-exist", gateway_instance_id="gw-prod-1"
    )
    run = _run(config)
    assert run.inventory_status is InventoryStatus.FAILED and not run.commit_eligible
    escaping = _config(tmp_path, source_id="esc")
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(_full_document()))
    escaping = escaping.model_copy(update={"capture_relative_path": "../outside.json"})
    assert _only_outcome(_run(escaping)).result is IngestionResult.REJECTED_INVALID
