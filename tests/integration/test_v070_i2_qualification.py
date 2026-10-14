"""v0.7.0 I2.4: coverage, interactions and the configured-vs-observed qualification rows derived
into `api_usage_v1` against a real Neo4j - an APISIX configuration source, the bundled OpenAPI
examples and a measurement source in one real import request. The expected rows come from the I2
spec §9.3 (P1, P2, N1-N4) and the I2.1 contract §7, not from the code under test."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.graph.import_runs import run_all_configured_sources
from app.graph.schema import ensure_schema
from app.settings import SourcesConfig
from app.sources.apisix_measurement_contract import (
    END_FILE,
    MANIFEST_FILE,
    START_FILE,
)
from app.sources.model import (
    ApisixMeasurementSourceConfig,
    ApisixSourceConfig,
    FilesystemSourceConfig,
)

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
VECTORS = REPO / "docs/specifications/0.7.0"
GW, ENV = "gw-prod-1", "prod"


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _state(driver) -> dict:
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        return canonical_snapshot_state(session, coverage_qualification_enabled=True)


def _line(consumer: str, route: str, code: str = "200", source: str = "upstream") -> str:
    return (
        f'apisix_http_status{{code="{code}",consumer="{consumer}",llm_model="",matched_host="",'
        f'matched_uri="/x",request_llm_model="",request_type="traditional_http",'
        f'response_source="{source}",route="{route}",service=""}}'
    )


def _gateway(tmp_path: Path, *, routes: list[dict], gateway: str = GW, env: str = ENV):
    base = json.loads((VECTORS / "i1-vectors/configured-access.json").read_text())["base_capture"]
    document = {
        **base,
        "gateway_instance_id": gateway,
        "environment": env,
        "consumers": [
            {"username": name, "credential_ids": []} for name in ("alice", "bob", "carol")
        ],
        "routes": routes,
        "services": [],
        "upstreams": [],
        "plugin_configs": [],
        "consumer_groups": [],
        "global_rules": [],
    }
    root = tmp_path / f"gateway-{gateway}-{env}"
    root.mkdir(exist_ok=True)
    config = ApisixSourceConfig(
        id=f"apisix-{gateway}-{env}", root=root, gateway_instance_id=gateway
    )
    (root / config.capture_relative_path).write_text(json.dumps(document))
    return config


def _route(route_id: str, whitelist: list[str]) -> dict[str, Any]:
    return {
        "id": route_id,
        "uri": f"/{route_id}",
        "plugins": {"key-auth": {}, "consumer-restriction": {"whitelist": whitelist}},
    }


def _measurement(
    tmp_path: Path,
    *,
    gateway: str = GW,
    env: str = ENV,
    start: list[str] | None = None,
    end: list[str] | None = None,
    patch: dict[str, Any] | None = None,
    sha_end: str | None = None,
) -> ApisixMeasurementSourceConfig:
    base = json.loads((VECTORS / "i2-vectors/manifest-rejections.json").read_text())
    root = tmp_path / f"metrics-{gateway}-{env}"
    root.mkdir(exist_ok=True)
    start_b = "".join(f"{x}\n" for x in sorted(start or [])).encode()
    end_b = "".join(f"{x}\n" for x in sorted(end or [])).encode()
    manifest = {
        **base["base_manifest"],
        "gateway_instance_id": gateway,
        "environment": env,
        "route_coverage": {"orders-route": True, "billing-route": True},
        "start_sha256": hashlib.sha256(start_b).hexdigest(),
        "end_sha256": sha_end or hashlib.sha256(end_b).hexdigest(),
        **(patch or {}),
    }
    (root / START_FILE).write_bytes(start_b)
    (root / END_FILE).write_bytes(end_b)
    (root / MANIFEST_FILE).write_text(json.dumps(manifest))
    return ApisixMeasurementSourceConfig(
        id=f"metrics-{gateway}-{env}", root=root, gateway_instance_id=gateway, environment=env
    )


def _run(driver, *, gateways, measurements) -> dict:
    examples = FilesystemSourceConfig(id="pin", root=REPO / "examples")
    run_all_configured_sources(
        SourcesConfig(directories=[examples], gateways=gateways, gateway_measurements=measurements),
        driver=driver,
        database=DATABASE,
    )
    return _state(driver)


def _gateway_default(tmp_path: Path):
    return _gateway(
        tmp_path,
        routes=[_route("orders-route", ["alice", "bob"]), _route("billing-route", ["alice"])],
    )


def _spec_cases_measurement(tmp_path: Path, **extra: Any) -> ApisixMeasurementSourceConfig:
    return _measurement(
        tmp_path,
        start=[
            _line("alice", "orders-route") + " 1",
            _line("bob", "billing-route") + " 2",
            _line("", "billing-route") + " 1",
            _line("carol", "orders-route", "401", "apisix") + " 1",
        ],
        end=[
            _line("alice", "orders-route") + " 4",
            _line("bob", "billing-route") + " 5",
            _line("", "billing-route") + " 2",
            _line("carol", "orders-route", "401", "apisix") + " 3",
        ],
        **extra,
    )


def _rows(block: dict) -> dict[tuple[str, str], dict]:
    return {(r["consumer"], r["route"]): r for r in block["qualification_rows"]}


def _summary(row: dict) -> tuple:
    return (
        row["configured_status"],
        row["usage_status"],
        row["coverage"],
        row.get("upstream_request_count"),
        row.get("rejected_attempt_count"),
        row["limitations"],
    )


def test_the_frozen_spec_cases_p1_p2_n1_to_n4_through_a_real_request(driver, tmp_path) -> None:
    state = _run(
        driver,
        gateways=[_gateway_default(tmp_path)],
        measurements=[_spec_cases_measurement(tmp_path)],
    )
    block = state["api_usage_v1"]
    assert block["qualification_rule"] == {
        "rule_id": "apisix-configured-vs-observed-qualification",
        "rule_version": "1",
    }
    configured = "CONFIGURED_ACCESS_ESTABLISHED"
    none = "NO_MATCHING_CONFIGURED_ACCESS_FACT"
    sufficient, unknown = "SUFFICIENT_FOR_ZERO", "UNKNOWN_COVERAGE"
    unattributed = ["GWM_UNATTRIBUTED_UPSTREAM"]
    assert {key: _summary(row) for key, row in _rows(block).items()} == {
        # N1/N3: configured, nothing used, but unattributed upstream traffic on the Route
        ("alice", "billing-route"): (configured, "USAGE_UNESTABLISHED", unknown, 0, 0, unattributed),
        # P1: configured plus an attributed upstream delta
        ("alice", "orders-route"): (configured, "OBSERVED_USAGE", sufficient, 3, 0, []),
        # N4: configured on orders, observed on billing - billing's use does not touch orders
        ("bob", "billing-route"): (none, "OBSERVED_USAGE", unknown, 3, 0, unattributed),
        # P2: configured, no series, closed-world coverage
        ("bob", "orders-route"): (configured, "MEASURED_ZERO", sufficient, 0, 0, []),
        # N2: a rejected attempt invents neither access nor usage
        ("carol", "orders-route"): (none, "USAGE_UNESTABLISHED", sufficient, 0, 2, []),
    }  # fmt: skip
    # the unattributed series made no interaction and no row of its own
    assert {(i["consumer"], i["route"]) for i in block["interactions"]} == {
        ("alice", "orders-route"),
        ("bob", "billing-route"),
        ("carol", "orders-route"),
    }
    window = block["windows"][0]
    assert all(row["evidence_ids"] == window["evidence_ids"] for row in block["qualification_rows"])
    evidence_ids = {e["id"] for e in block["evidence"]}
    assert set(window["evidence_ids"]) <= evidence_ids  # every claim resolves to internal evidence
    assert {(c["route_id"], c["coverage"]) for c in block["coverage"]} == {
        (r["id"], unknown if r["route_id"] == "billing-route" else sufficient)
        for r in state["gateway_configuration_v1"]["routes"]
    }


def test_an_invalid_window_qualifies_the_pairs_without_counts_or_zero(driver, tmp_path) -> None:
    measurement = _spec_cases_measurement(tmp_path, patch={"start_settled": False})
    block = _run(driver, gateways=[_gateway_default(tmp_path)], measurements=[measurement])[
        "api_usage_v1"
    ]
    rows = _rows(block)
    assert {k for k in rows} == {
        ("alice", "orders-route"),
        ("alice", "billing-route"),
        ("bob", "orders-route"),
        ("bob", "billing-route"),
        ("carol", "orders-route"),
    }
    for row in rows.values():
        assert row["usage_status"] == "USAGE_UNESTABLISHED"
        assert row["coverage"] == "UNKNOWN_COVERAGE"
        assert row["limitations"] == ["GWM_WINDOW_NOT_SETTLED"]
        assert "upstream_request_count" not in row and "rejected_attempt_count" not in row


def test_a_measurement_for_another_gateway_or_environment_qualifies_nothing(
    driver, tmp_path
) -> None:
    gateway = _gateway_default(tmp_path)
    for other_gateway, other_env in (("gw-prod-2", ENV), (GW, "staging")):
        measurement = _measurement(
            tmp_path,
            gateway=other_gateway,
            env=other_env,
            end=[_line("alice", "orders-route") + " 3"],
        )
        block = _run(driver, gateways=[gateway], measurements=[measurement])["api_usage_v1"]
        assert block["qualification_rows"] == [] and block["interactions"] == []
        assert block["coverage"] == []


def test_a_replay_is_a_no_op_and_a_later_window_replaces_the_rows(driver, tmp_path) -> None:
    gateway = _gateway_default(tmp_path)
    first = _run(driver, gateways=[gateway], measurements=[_spec_cases_measurement(tmp_path)])
    replay = _run(driver, gateways=[gateway], measurements=[_spec_cases_measurement(tmp_path)])
    assert snapshot_fingerprint(replay)[0] == snapshot_fingerprint(first)[0]

    later = _measurement(
        tmp_path,
        start=[_line("alice", "orders-route") + " 4"],
        end=[_line("alice", "orders-route") + " 4"],
        patch={"window_start": "2026-10-13T11:00:00Z", "window_end": "2026-10-13T11:10:00Z"},
    )
    second = _run(driver, gateways=[gateway], measurements=[later])["api_usage_v1"]
    assert len(second["windows"]) == 1  # replaced, not appended
    assert _summary(_rows(second)[("alice", "orders-route")])[:2] == (
        "CONFIGURED_ACCESS_ESTABLISHED",
        "MEASURED_ZERO",  # a zero-delta series with closed-world coverage
    )
    assert not {r["id"] for r in second["qualification_rows"]} & {
        r["id"] for r in first["api_usage_v1"]["qualification_rows"]
    }  # ids carry the window: no cross-window identity


def test_a_rejected_import_keeps_the_previous_rows(driver, tmp_path) -> None:
    gateway = _gateway_default(tmp_path)
    good = _run(driver, gateways=[gateway], measurements=[_spec_cases_measurement(tmp_path)])
    bad = _spec_cases_measurement(tmp_path, sha_end="0" * 64)
    after = _run(driver, gateways=[gateway], measurements=[bad])
    assert snapshot_fingerprint(after)[0] == snapshot_fingerprint(good)[0]
    assert after["api_usage_v1"]["qualification_rows"] == good["api_usage_v1"]["qualification_rows"]


def test_dropping_the_measurement_registration_removes_only_the_usage_state(
    driver, tmp_path
) -> None:
    gateway = _gateway_default(tmp_path)
    _run(driver, gateways=[gateway], measurements=[_spec_cases_measurement(tmp_path)])
    state = _run(driver, gateways=[gateway], measurements=[])
    assert "api_usage_v1" not in state
    assert state["gateway_configuration_v1"]["configured_access"]  # I1 state stays
    assert "api_contracts_v1" in state
