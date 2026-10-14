"""v0.7.0 I2.2c: the APISIX measurement source against a real Neo4j - persistence as internal
carriers, the conditional `api_usage_v1` snapshot key, replay as a semantic no-op, authoritative
replacement of the previous window, rejected imports leaving prior state untouched, bounded removal
(including a dropped registration), the duplicate (gateway, environment) conflict through the real
import request, and the amended import report. Independent expected data comes from the I2.1
vectors."""

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.graph.import_runs import run_all_configured_sources
from app.graph.importer import import_apisix_measurement_source
from app.graph.schema import ensure_schema
from app.ingestion.import_report import build_import_report
from app.settings import SourcesConfig
from app.sources.apisix_measurement_contract import (
    END_FILE,
    MANIFEST_FILE,
    MAPPING_FILE,
    START_FILE,
)
from app.sources.model import (
    ApisixMeasurementSourceConfig,
    ApisixSourceConfig,
    FilesystemSourceConfig,
    IngestionResult,
)

DATABASE = "neo4j"
VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i2-vectors"
REPO = Path(__file__).resolve().parents[2]
CANARY = "CANARY-SECRET-VALUE"
CARRIER_LABELS = (
    "MeasurementWindow",
    "MeasurementEvidence",
    "MeasurementSeries",
    "MeasurementLimitation",
    "MeasurementMappingEntry",
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _vectors() -> dict[str, Any]:
    return json.loads((VECTORS / "manifest-rejections.json").read_text(encoding="utf-8"))


def _bytes(lines: list[str]) -> bytes:
    return "".join(f"{line}\n" for line in lines).encode("utf-8")


def _config(
    tmp_path: Path,
    *,
    source_id: str = "metrics-prod",
    gateway: str = "gw-prod-1",
    env: str = "prod",
    start: list[str] | None = None,
    end: list[str] | None = None,
    manifest_patch: dict[str, Any] | None = None,
    mapping: dict[str, Any] | None = None,
) -> ApisixMeasurementSourceConfig:
    doc = _vectors()
    root = tmp_path / f"{source_id}-{gateway}-{env}"
    root.mkdir(exist_ok=True)
    start_b = _bytes(doc["base_start_lines"] if start is None else start)
    end_b = _bytes(doc["base_end_lines"] if end is None else end)
    manifest = {**doc["base_manifest"], "gateway_instance_id": gateway, "environment": env}
    manifest["start_sha256"] = hashlib.sha256(start_b).hexdigest()
    manifest["end_sha256"] = hashlib.sha256(end_b).hexdigest()
    manifest.update(manifest_patch or {})
    (root / START_FILE).write_bytes(start_b)
    (root / END_FILE).write_bytes(end_b)
    (root / MANIFEST_FILE).write_text(json.dumps(manifest))
    if mapping is not None:
        (root / MAPPING_FILE).write_text(json.dumps(mapping))
    return ApisixMeasurementSourceConfig(
        id=source_id, root=root, gateway_instance_id=gateway, environment=env
    )


def _import(driver, config):
    return import_apisix_measurement_source(driver, database=DATABASE, source_config=config)


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]  # pyright: ignore[reportArgumentType]


def _counts(driver) -> dict[str, int]:
    return {
        label: _count(driver, f"MATCH (n:{label}) RETURN count(n) AS c") for label in CARRIER_LABELS
    }


def _state(driver) -> dict:
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        return canonical_snapshot_state(session, coverage_qualification_enabled=True)


def _line(consumer: str, code: str, source: str) -> str:
    return (
        f'apisix_http_status{{code="{code}",consumer="{consumer}",llm_model="",matched_host="",'
        f'matched_uri="/orders",request_llm_model="",request_type="traditional_http",'
        f'response_source="{source}",route="orders-route",service=""}}'
    )


def test_an_accepted_window_persists_internal_carriers_without_relationships_or_evidence(
    driver, tmp_path
) -> None:
    stats = _import(driver, _config(tmp_path))
    assert stats.committed
    assert _counts(driver) == {
        "MeasurementWindow": 1, "MeasurementEvidence": 1, "MeasurementSeries": 2,
        "MeasurementLimitation": 0, "MeasurementMappingEntry": 0,
    }  # fmt: skip
    for label in CARRIER_LABELS:
        assert _count(driver, f"MATCH (n:{label})-[r]-() RETURN count(r) AS c") == 0
    # measurement evidence is an internal carrier, never an :Evidence node (no public/NL exposure)
    assert _count(driver, "MATCH (e:Evidence) RETURN count(e) AS c") == 0
    assert _count(driver, "MATCH (s:Service) RETURN count(s) AS c") == 0


def test_the_snapshot_gains_the_conditional_usage_key_with_the_vector_content(
    driver, tmp_path
) -> None:
    before = _state(driver)
    assert "api_usage_v1" not in before
    _import(driver, _config(tmp_path))
    state = _state(driver)
    block = state["api_usage_v1"]
    [window] = block["windows"]
    assert window["window_reasons"] == [] and window["start_stable_seconds"] == 24
    assert json.loads(window["route_coverage_json"]) == {"orders-route": True}
    [evidence] = block["evidence"]
    assert window["evidence_ids"] == [evidence["id"]] and evidence["evidence_type"] == "OBSERVED"
    deltas = {s["response_source"]: s["request_count_delta"] for s in block["series"]}
    assert deltas == {"upstream": 3, "apisix": 1}
    assert block["limitations"] == [] and block["mapping_entries"] == []
    for rows in block.values():
        assert rows == sorted(rows, key=lambda row: row["id"])
    # no other key appears, and a graph without the block keeps its exact pre-I2.2 bytes
    without = {k: v for k, v in state.items() if k != "api_usage_v1"}
    assert snapshot_fingerprint(without)[0] == snapshot_fingerprint(before)[0]
    assert "gateway_configuration_v1" not in state and "api_contracts_v1" not in state


def test_a_replay_of_the_same_fixture_is_a_semantic_no_op(driver, tmp_path) -> None:
    config = _config(tmp_path)
    _import(driver, config)
    first = snapshot_fingerprint(_state(driver))[0]
    stats = _import(driver, config)
    assert stats.committed
    assert all(not s.graph_revision_advanced for s in stats.per_source.values())
    assert snapshot_fingerprint(_state(driver))[0] == first


def test_a_later_window_authoritatively_replaces_the_previous_one(driver, tmp_path) -> None:
    config = _config(tmp_path)
    _import(driver, config)
    first_ids = {
        r["id"]
        for r in driver.session(database=DATABASE).run(
            "MATCH (n:MeasurementSeries) RETURN n.id AS id"
        )
    }
    later = _config(
        tmp_path,
        manifest_patch={
            "window_start": "2026-10-13T10:05:00Z",
            "window_end": "2026-10-13T10:15:00Z",
        },
        start=[],
        end=[_line("spike-beta", "200", "upstream") + " 7"],
    )
    assert _import(driver, later).committed
    block = _state(driver)["api_usage_v1"]
    assert [s["consumer"] for s in block["series"]] == ["spike-beta"]
    assert block["series"][0]["status"] == "DELTA_FIRST_IN_WINDOW"
    assert block["series"][0]["request_count_delta"] == 7
    assert first_ids.isdisjoint({s["id"] for s in block["series"]})  # nothing of window 1 remains
    assert _counts(driver)["MeasurementWindow"] == 1 and _counts(driver)["MeasurementEvidence"] == 1


@pytest.mark.parametrize(
    "bad",
    [
        {"manifest_patch": {"start_sha256": "0" * 64}},  # binding mismatch
        {"manifest_patch": {"gateway_instance_id": "gw-other"}},  # registration mismatch
        {"start": ["not a sample"]},  # extract not normalized
    ],
    ids=["binding", "instance", "extract"],
)
def test_a_rejected_fixture_commits_nothing_and_removes_nothing(driver, tmp_path, bad) -> None:
    good = _config(tmp_path)
    _import(driver, good)
    before = (_counts(driver), snapshot_fingerprint(_state(driver))[0])
    stats = _import(driver, _config(tmp_path, **bad))
    assert not stats.committed
    assert (_counts(driver), snapshot_fingerprint(_state(driver))[0]) == before


def test_an_invalid_window_keeps_the_window_and_series_identities_without_deltas(
    driver, tmp_path
) -> None:
    config = _config(tmp_path, manifest_patch={"no_restart": False})
    assert _import(driver, config).committed
    block = _state(driver)["api_usage_v1"]
    [window] = block["windows"]
    assert window["window_reasons"] == ["GWM_WINDOW_RESTART"]
    assert {s["status"] for s in block["series"]} == {"WINDOW_INVALID"}
    # a null property is omitted from the projection (no delta key at all)
    assert all("request_count_delta" not in s for s in block["series"])
    assert block["limitations"] == []


def test_series_without_a_usable_delta_persist_their_identity_and_a_route_limitation(
    driver, tmp_path
) -> None:
    config = _config(
        tmp_path,
        start=[_line("mallory-free", "200", "upstream") + " 5"],
        end=[_line("mallory-free", "200", "upstream") + " 2"],
    )
    assert _import(driver, config).committed
    block = _state(driver)["api_usage_v1"]
    [series] = block["series"]
    assert (series["consumer"], series["status"]) == ("mallory-free", "DECREASED")
    assert "request_count_delta" not in series
    [limitation] = block["limitations"]
    assert (limitation["code"], limitation["route"]) == ("GWM_COUNTER_DECREASED", "orders-route")


def test_the_mapping_artifact_persists_as_entries(driver, tmp_path) -> None:
    mapping = {**_vectors()["mapping_base"]}
    _import(driver, _config(tmp_path, mapping=mapping))
    entries = _state(driver)["api_usage_v1"]["mapping_entries"]
    assert sorted((e["kind"], e["source_id"], e["target_id"]) for e in entries) == [
        ("route_operation", "orders-route", "op:orders:get:/orders"),
        ("target_service_route", "orders-route", "orders"),
        ("target_service_service", "s1", "billing"),
    ]


def test_a_canary_in_a_fixture_is_rejected_and_never_reaches_the_graph_or_stats(
    driver, tmp_path
) -> None:
    config = _config(tmp_path, start=[f'apisix_http_status{{consumer="{CANARY}"}} 1'])
    stats = _import(driver, config)
    assert not stats.committed
    assert CANARY not in repr(stats)
    assert _counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)


def test_the_same_username_in_two_windows_of_different_gateways_stays_separate(
    driver, tmp_path
) -> None:
    for gateway in ("gw-a", "gw-b"):
        assert _import(
            driver, _config(tmp_path, source_id=f"src-{gateway}", gateway=gateway)
        ).committed
    assert _count(driver, "MATCH (w:MeasurementWindow) RETURN count(w) AS c") == 2
    assert (
        _count(driver, "MATCH (s:MeasurementSeries {consumer: 'spike-alpha'}) RETURN count(s) AS c")
        == 4  # two series (upstream and the rejected attempt) per window
    )


def test_duplicate_gateway_and_environment_registrations_are_both_rejected_through_the_request(
    driver, tmp_path
) -> None:
    measurements = [
        _config(tmp_path, source_id="metrics-a"),
        _config(tmp_path, source_id="metrics-b"),  # same (gateway_instance_id, environment)
    ]
    _, runs = run_all_configured_sources(
        SourcesConfig(directories=[], gateway_measurements=measurements),
        driver=driver,
        database=DATABASE,
    )
    assert [r.kind for r in runs] == ["apisix-measurement", "apisix-measurement"]
    for run in runs:
        assert not run.stats.committed
        assert {s.result for s in run.stats.source_results} == {IngestionResult.REJECTED_CONFLICT}
    assert _counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)


def test_registrations_for_distinct_pairs_coexist_through_the_request(driver, tmp_path) -> None:
    measurements = [
        _config(tmp_path, source_id="m-a"),
        _config(tmp_path, source_id="m-b", env="staging"),
        _config(tmp_path, source_id="m-c", gateway="gw-prod-2"),
    ]
    _, runs = run_all_configured_sources(
        SourcesConfig(directories=[], gateway_measurements=measurements),
        driver=driver,
        database=DATABASE,
    )
    assert all(r.stats.committed for r in runs)
    assert _counts(driver)["MeasurementWindow"] == 3


def test_the_request_runs_filesystem_and_measurement_sources_and_the_report_validates(
    driver, tmp_path
) -> None:
    examples = FilesystemSourceConfig(id="pin", root=REPO / "examples")
    measurement = _config(tmp_path)
    import_id, runs = run_all_configured_sources(
        SourcesConfig(directories=[examples], gateway_measurements=[measurement]),
        driver=driver,
        database=DATABASE,
    )
    assert [r.kind for r in runs] == ["filesystem", "apisix-measurement"]
    assert all(r.stats.committed for r in runs)
    report = build_import_report(import_id, runs)
    schema = json.loads((REPO / "schemas/import/v0.5/import-report.schema.json").read_text())
    jsonschema.validate(json.loads(report.model_dump_json()), schema)
    assert any(run.kind == "apisix-measurement" for run in report.runs)
    assert _counts(driver)["MeasurementSeries"] == 2
    # configuring only a measurement source does not turn the OpenAPI contract carriers on
    assert _count(driver, "MATCH (c:ApiContract) RETURN count(c) AS c") == 0


def test_dropping_the_registration_removes_its_carriers_and_the_snapshot_key(
    driver, tmp_path
) -> None:
    examples = FilesystemSourceConfig(id="pin", root=REPO / "examples")
    measurement = _config(tmp_path)
    run_all_configured_sources(
        SourcesConfig(directories=[examples], gateway_measurements=[measurement]),
        driver=driver,
        database=DATABASE,
    )
    assert _counts(driver)["MeasurementSeries"] == 2 and "api_usage_v1" in _state(driver)
    run_all_configured_sources(
        SourcesConfig(directories=[examples], gateway_measurements=[]),
        driver=driver,
        database=DATABASE,
    )
    assert _counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)
    assert "api_usage_v1" not in _state(driver)


def test_dropping_one_of_two_registrations_keeps_the_other(driver, tmp_path) -> None:
    keep = _config(tmp_path, source_id="m-a")
    drop = _config(tmp_path, source_id="m-b", env="staging")
    run_all_configured_sources(
        SourcesConfig(directories=[], gateway_measurements=[keep, drop]),
        driver=driver,
        database=DATABASE,
    )
    assert _counts(driver)["MeasurementWindow"] == 2
    run_all_configured_sources(
        SourcesConfig(directories=[], gateway_measurements=[keep]), driver=driver, database=DATABASE
    )
    assert _counts(driver)["MeasurementWindow"] == 1
    assert [w["environment"] for w in _state(driver)["api_usage_v1"]["windows"]] == ["prod"]


def test_removing_measurement_leaves_the_gateway_configuration_untouched_and_vice_versa(
    driver, tmp_path
) -> None:
    gateway_root = tmp_path / "gateway"
    gateway_root.mkdir()
    capture = json.loads(
        (REPO / "docs/specifications/0.7.0/i1-vectors/configured-access.json").read_text()
    )
    case = next(c for c in capture["cases"] if c["id"] == "C14")
    document = {
        **capture["base_capture"],
        "consumers": [], "routes": [], "services": [], "upstreams": [], "plugin_configs": [],
        "consumer_groups": [], "global_rules": [], **case["capture"],
    }  # fmt: skip
    gateway = ApisixSourceConfig(
        id="apisix-prod", root=gateway_root, gateway_instance_id="gw-prod-1"
    )
    (gateway_root / gateway.capture_relative_path).write_text(json.dumps(document))
    measurement = _config(tmp_path)
    run_all_configured_sources(
        SourcesConfig(directories=[], gateways=[gateway], gateway_measurements=[measurement]),
        driver=driver,
        database=DATABASE,
    )
    access = "MATCH (a:GatewayConfiguredAccess) RETURN count(a) AS c"
    assert _count(driver, access) == 3 and _counts(driver)["MeasurementSeries"] == 2
    state = _state(driver)
    assert "gateway_configuration_v1" in state and "api_usage_v1" in state

    run_all_configured_sources(
        SourcesConfig(directories=[], gateways=[gateway], gateway_measurements=[]),
        driver=driver,
        database=DATABASE,
    )
    assert _count(driver, access) == 3 and _counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)

    run_all_configured_sources(
        SourcesConfig(directories=[], gateways=[], gateway_measurements=[measurement]),
        driver=driver,
        database=DATABASE,
    )
    assert _count(driver, access) == 0 and _counts(driver)["MeasurementSeries"] == 2
