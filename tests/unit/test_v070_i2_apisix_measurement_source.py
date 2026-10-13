"""v0.7.0 I2.2b: the APISIX measurement source end to end below the graph - ids, the carriers the
production mapping emits from the independent I2.1 vectors, and the production
discoverer/adapter/run path (registration binding, rejection outcomes, bounds, cardinality, replay
determinism). No Docker, no Neo4j."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.canonical.gateway_measurement import (
    measurement_limitation_id,
    measurement_mapping_entry_id,
    measurement_series_id,
)
from app.ingestion.orchestrator import default_registry, run_apisix_measurement_discovery
from app.sources.apisix_measurement_contract import (
    END_FILE,
    MANIFEST_FILE,
    MAPPING_FILE,
    MAX_MANIFEST_BYTES,
    START_FILE,
)
from app.sources.identity import apisix_measurement_source_instance_id
from app.sources.inventory import InventoryStatus
from app.sources.model import ApisixMeasurementSourceConfig, DiagnosticCode, IngestionResult

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i2-vectors"
CANARY = "CANARY-SECRET-VALUE"
GW, ENV = "gw-prod-1", "prod"


def _load(name: str) -> dict[str, Any]:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _bytes(lines: list[str], ending: str = "LF") -> bytes:
    eol = "\r\n" if ending == "CRLF" else "\n"
    return "".join(line + eol for line in lines).encode("utf-8")


def _config(
    tmp_path: Path, *, source_id: str = "apisix-metrics-prod", gateway: str = GW, env: str = ENV
):
    root = tmp_path / f"{source_id}-{gateway}-{env}"
    root.mkdir(exist_ok=True)
    return ApisixMeasurementSourceConfig(
        id=source_id, root=root, gateway_instance_id=gateway, environment=env
    )


def _write_fixture(
    config: ApisixMeasurementSourceConfig,
    *,
    start: list[str] | None = None,
    end: list[str] | None = None,
    manifest_patch: dict[str, Any] | None = None,
    mapping: dict[str, Any] | None = None,
) -> None:
    doc = _load("manifest-rejections.json")
    start_b = _bytes(doc["base_start_lines"] if start is None else start)
    end_b = _bytes(doc["base_end_lines"] if end is None else end)
    manifest = {**doc["base_manifest"]}
    manifest["gateway_instance_id"] = config.gateway_instance_id
    manifest["environment"] = config.environment
    manifest["start_sha256"] = hashlib.sha256(start_b).hexdigest()
    manifest["end_sha256"] = hashlib.sha256(end_b).hexdigest()
    manifest.update(manifest_patch or {})
    (config.root / START_FILE).write_bytes(start_b)
    (config.root / END_FILE).write_bytes(end_b)
    (config.root / MANIFEST_FILE).write_text(json.dumps(manifest))
    if mapping is not None:
        (config.root / MAPPING_FILE).write_text(json.dumps(mapping))


def _run(config: ApisixMeasurementSourceConfig, **kwargs: Any):
    return run_apisix_measurement_discovery(config, **kwargs)


def _only_outcome(run):
    [outcome] = run.source_outcomes.values()
    return outcome.outcome


def _line(consumer: str, code: str, source: str, route: str = "orders-route") -> str:
    return (
        f'apisix_http_status{{code="{code}",consumer="{consumer}",llm_model="",matched_host="",'
        f'matched_uri="/orders",request_llm_model="",request_type="traditional_http",'
        f'response_source="{source}",route="{route}",service=""}}'
    )


# ------------------------------------------------------------------------------------------
# ids (vectors M01, M02, M10-M13)
# ------------------------------------------------------------------------------------------


def test_ids_match_the_frozen_vectors() -> None:
    by_id = {v["id"]: v for v in _load("ids.json")["vectors"]}
    for key in ("M01", "M02"):
        i = by_id[key]["inputs"]
        assert (
            apisix_measurement_source_instance_id(
                configured_source_id=i["source_id"],
                gateway_instance_id=i["gateway_instance_id"],
                environment=i["environment"],
            )
            == by_id[key]["expected"]
        )
    s = by_id["M10"]["inputs"]
    assert measurement_series_id(s["window_id"], s["series_key"]) == by_id["M10"]["expected"]
    li = by_id["M11"]["inputs"]
    assert measurement_limitation_id(**li) == by_id["M11"]["expected"]
    for key in ("M12", "M13"):
        e = by_id[key]["inputs"]
        assert measurement_mapping_entry_id(**e) == by_id[key]["expected"]


# ------------------------------------------------------------------------------------------
# the production run path
# ------------------------------------------------------------------------------------------


def test_the_registry_resolves_the_measurement_adapter_and_the_source_id_is_the_vector(
    tmp_path,
) -> None:
    config = _config(tmp_path)
    _write_fixture(config)
    run = _run(config)
    assert run.commit_eligible and run.inventory_status is InventoryStatus.COMPLETE
    [source_id] = run.source_outcomes
    assert source_id == apisix_measurement_source_instance_id(
        configured_source_id="apisix-metrics-prod", gateway_instance_id=GW, environment=ENV
    )
    assert default_registry().adapter_for


def test_an_accepted_window_maps_the_carriers_and_replays_deterministically(tmp_path) -> None:
    config = _config(tmp_path)
    _write_fixture(config)
    first, second = _run(config), _run(config)
    out1, out2 = _only_outcome(first), _only_outcome(second)
    assert out1.result is IngestionResult.ACCEPTED and out1.diagnostics == ()
    assert out1.model == out2.model and out1.semantic_input_digest == out2.semantic_input_digest
    model = out1.model
    [window] = model.measurement_windows
    [evidence] = model.measurement_evidence
    assert window.evidence_ids == [evidence.id] and window.window_reasons == []
    assert window.start_stable_seconds == 24 and json.loads(window.route_coverage_json) == {
        "orders-route": True
    }
    assert evidence.evidence_type == "OBSERVED"
    by_source = {s.response_source: s for s in model.measurement_series}
    assert (by_source["upstream"].request_count_delta, by_source["upstream"].status) == (3, "DELTA")
    assert by_source["apisix"].request_count_delta == 1
    assert all(
        s.window_id == window.id and s.evidence_ids == [evidence.id] for s in by_source.values()
    )
    assert model.measurement_limitations == [] and model.measurement_mapping_entries == []
    # nothing public: no Service/Operation/Relation/Provenance is emitted
    assert not (model.services or model.operations or model.relations or model.provenance)


def test_a_later_window_has_distinct_ids_and_the_same_bytes_have_identical_ones(tmp_path) -> None:
    config = _config(tmp_path)
    _write_fixture(config)
    base = _only_outcome(_run(config)).model
    _write_fixture(config, manifest_patch={"window_start": "2026-10-13T09:50:00Z"})
    later = _only_outcome(_run(config)).model
    assert {s.id for s in base.measurement_series}.isdisjoint(
        {s.id for s in later.measurement_series}
    )
    assert base.measurement_windows[0].id != later.measurement_windows[0].id


def test_series_without_a_usable_delta_become_route_level_limitations(tmp_path) -> None:
    config = _config(tmp_path)
    start = sorted(
        [
            _line("a", "200", "upstream") + " 5",  # decreased
            _line("b", "200", "upstream") + " 1",  # start only
            _line("c", "200", "upstream") + " 2",  # unchanged: a valid zero delta
        ]
    )
    end = sorted(
        [
            _line("a", "200", "upstream") + " 2",
            _line("c", "200", "upstream") + " 2",
            _line("d", "403", "apisix", "billing-route") + " 3",  # new, but billing is not covered
        ]
    )
    _write_fixture(config, start=start, end=end)
    outcome = _only_outcome(_run(config))
    assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.GWM_MEASUREMENT_LIMITATIONS]
    model = outcome.model
    assert {(s.consumer, s.request_count_delta) for s in model.measurement_series} == {("c", 0)}
    assert {
        (item.code, item.route, item.response_source) for item in model.measurement_limitations
    } == {
        ("GWM_COUNTER_DECREASED", "orders-route", "upstream"),
        ("GWM_SERIES_ONE_BOUNDARY", "orders-route", "upstream"),
        ("GWM_SERIES_ONE_BOUNDARY", "billing-route", "apisix"),
    }
    rendered = repr(outcome.diagnostics)
    assert "spike" not in rendered and "orders-route" not in rendered  # a count only


def test_a_series_first_created_in_a_covered_window_is_a_delta_from_zero(tmp_path) -> None:
    config = _config(tmp_path)
    _write_fixture(config, start=[], end=[_line("a", "200", "upstream") + " 4"])
    [series] = _only_outcome(_run(config)).model.measurement_series
    assert (series.status, series.request_count_delta) == ("DELTA_FIRST_IN_WINDOW", 4)


def test_first_in_window_needs_the_recorded_start_stability(tmp_path) -> None:
    config = _config(tmp_path)
    _write_fixture(
        config,
        start=[],
        end=[_line("a", "200", "upstream") + " 4"],
        manifest_patch={"start_stable_seconds": 19},
    )
    model = _only_outcome(_run(config)).model
    assert model.measurement_series == []
    assert [item.code for item in model.measurement_limitations] == ["GWM_SERIES_ONE_BOUNDARY"]


@pytest.mark.parametrize(
    "case", _load("series-deltas.json")["window_validity"], ids=lambda c: c["id"]
)
def test_window_reasons_are_recorded_and_an_invalid_window_stores_no_series(
    case: dict, tmp_path
) -> None:
    config = _config(tmp_path)
    _write_fixture(config, manifest_patch=case["manifest_patch"])
    outcome = _only_outcome(_run(config))
    [window] = outcome.model.measurement_windows
    assert window.window_reasons == case["expected_reasons"]
    if case["expected_reasons"]:
        assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
        assert (
            outcome.model.measurement_series == [] and outcome.model.measurement_limitations == []
        )
    else:
        assert outcome.result is IngestionResult.ACCEPTED and outcome.model.measurement_series


def test_the_mapping_artifact_is_stored_not_interpreted(tmp_path) -> None:
    config = _config(tmp_path)
    mapping = {
        **_load("manifest-rejections.json")["mapping_base"],
        "route_operation": [
            {"route_id": "r1", "operation_id": "op:a"},
            {"route_id": "r1", "operation_id": "op:b"},  # a disagreement is kept, not resolved
            {"route_id": "r1", "operation_id": "op:a"},  # an exact repeat collapses
        ],
    }
    _write_fixture(config, mapping=mapping)
    entries = _only_outcome(_run(config)).model.measurement_mapping_entries
    assert sorted((e.kind, e.source_id, e.target_id) for e in entries) == [
        ("route_operation", "r1", "op:a"),
        ("route_operation", "r1", "op:b"),
        ("target_service_route", "orders-route", "orders"),
        ("target_service_service", "s1", "billing"),
    ]


# ------------------------------------------------------------------------------------------
# rejections through the production discoverer
# ------------------------------------------------------------------------------------------

_REJECTION_CASES = [
    c for c in _load("manifest-rejections.json")["cases"] if "registrations" not in c
]


@pytest.mark.parametrize("case", _REJECTION_CASES, ids=lambda c: c["id"])
def test_rejection_vectors_through_the_production_discoverer(case: dict, tmp_path) -> None:
    doc = _load("manifest-rejections.json")
    config = _config(tmp_path)
    start = list(case.get("start_lines_replace", doc["base_start_lines"]))
    end = list(doc["base_end_lines"]) + case.get("end_lines_patch", {}).get("append", [])
    ending = case.get("line_ending", "LF")
    start_b, end_b = _bytes(start, ending), _bytes(end, ending)
    manifest = json.loads(json.dumps(doc["base_manifest"]))
    if case.get("hash_policy") != "keep":
        manifest["start_sha256"] = hashlib.sha256(start_b).hexdigest()
        manifest["end_sha256"] = hashlib.sha256(end_b).hexdigest()
    manifest.update(case.get("manifest_patch", {}))
    for name in case.get("manifest_remove", []):
        manifest.pop(name)
    (config.root / START_FILE).write_bytes(start_b)
    (config.root / END_FILE).write_bytes(end_b)
    (config.root / MANIFEST_FILE).write_text(json.dumps(manifest))
    run = _run(config)
    outcome = _only_outcome(run)
    expected = case["expected"]
    assert not run.commit_eligible and run.inventory_status is InventoryStatus.PARTIAL
    assert outcome.result is IngestionResult(expected["result"]), case["id"]
    assert [d.code.value for d in outcome.diagnostics] == [expected["code"]], case["id"]
    assert outcome.model.measurement_windows == [] and outcome.semantic_input_digest is None
    assert CANARY not in repr(outcome.diagnostics) + repr(run.diagnostics)


@pytest.mark.parametrize(
    "case", _load("manifest-rejections.json")["mapping_cases"], ids=lambda c: c["id"]
)
def test_mapping_vectors_through_the_production_discoverer(case: dict, tmp_path) -> None:
    config = _config(tmp_path)
    _write_fixture(
        config, mapping={**_load("manifest-rejections.json")["mapping_base"], **case["patch"]}
    )
    run = _run(config)
    outcome = _only_outcome(run)
    expected = case["expected"]
    if expected["result"] == "ACCEPTED":
        assert outcome.result is IngestionResult.ACCEPTED and run.commit_eligible
        return
    assert not run.commit_eligible
    assert outcome.result is IngestionResult(expected["result"])
    assert [d.code.value for d in outcome.diagnostics] == [expected["code"]]


def test_duplicate_registrations_for_one_gateway_and_environment_are_both_rejected(
    tmp_path,
) -> None:
    for source_id in ("m-a", "m-b"):
        config = _config(tmp_path, source_id=source_id)
        _write_fixture(config)
        run = _run(config, duplicate_measurement_source=True)
        outcome = _only_outcome(run)
        assert not run.commit_eligible and run.inventory_status is InventoryStatus.PARTIAL
        assert outcome.result is IngestionResult.REJECTED_CONFLICT
        assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.GWM_DUPLICATE_SOURCE]


def test_registrations_differing_in_gateway_or_environment_coexist(tmp_path) -> None:
    ids_ = set()
    for gateway, env in ((GW, ENV), (GW, "staging"), ("gw-prod-2", ENV)):
        config = _config(tmp_path, gateway=gateway, env=env)
        _write_fixture(config)
        run = _run(config)
        assert _only_outcome(run).result is IngestionResult.ACCEPTED and run.commit_eligible
        ids_.add(next(iter(run.source_outcomes)))
    assert len(ids_) == 3


def test_missing_oversized_and_escaping_files_are_rejected_not_raised(tmp_path) -> None:
    config = _config(tmp_path)
    outcome = _only_outcome(_run(config))  # nothing written at all
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.GWM_MANIFEST_INVALID]
    _write_fixture(config)
    (config.root / START_FILE).unlink()
    assert [d.code for d in _only_outcome(_run(config)).diagnostics] == [
        DiagnosticCode.GWM_EXTRACT_INVALID
    ]
    _write_fixture(config)
    (config.root / MANIFEST_FILE).write_bytes(b" " * (MAX_MANIFEST_BYTES + 1))
    outcome = _only_outcome(_run(config))
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.GWM_LIMIT_EXCEEDED]
    _write_fixture(config)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"")
    (config.root / END_FILE).unlink()
    (config.root / END_FILE).symlink_to(outside)  # resolves outside the registered root
    assert [d.code for d in _only_outcome(_run(config)).diagnostics] == [
        DiagnosticCode.GWM_EXTRACT_INVALID
    ]


def test_a_missing_root_fails_the_run(tmp_path) -> None:
    config = ApisixMeasurementSourceConfig(
        id="x", root=tmp_path / "does-not-exist", gateway_instance_id=GW, environment=ENV
    )
    run = _run(config)
    assert run.inventory_status is InventoryStatus.FAILED and not run.commit_eligible


def test_a_canary_in_a_rejected_extract_never_reaches_a_diagnostic(tmp_path) -> None:
    config = _config(tmp_path)
    _write_fixture(config, start=[f'apisix_http_status{{consumer="{CANARY}"}} 1'])
    run = _run(config)
    outcome = _only_outcome(run)
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert CANARY not in repr(outcome.diagnostics) + repr(run.diagnostics)
