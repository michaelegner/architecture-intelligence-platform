"""v0.7.0 I2.3: the reconciliation derived into `api_usage_v1` against a real Neo4j - an APISIX
configuration source, the bundled OpenAPI examples and a measurement source in one real import
request. The expected outcomes come from the I2.1 contract §6 and vectors, not from the code under
test."""

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
    MAPPING_FILE,
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
        "consumers": [{"username": "alice", "credential_ids": []}],
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


def _route(route_id: str, uri: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": route_id,
        "uri": uri,
        "plugins": {"key-auth": {}, "consumer-restriction": {"whitelist": ["alice"]}},
        **extra,
    }


def _measurement(
    tmp_path: Path,
    *,
    gateway: str = GW,
    env: str = ENV,
    start: list[str] | None = None,
    end: list[str] | None = None,
    mapping: dict[str, Any] | None = None,
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
        "route_coverage": {"products-route": True, "orders-route": True, "none-route": True},
        "start_sha256": hashlib.sha256(start_b).hexdigest(),
        "end_sha256": hashlib.sha256(end_b).hexdigest(),
    }
    (root / START_FILE).write_bytes(start_b)
    (root / END_FILE).write_bytes(end_b)
    (root / MANIFEST_FILE).write_text(json.dumps(manifest))
    if mapping is not None:
        (root / MAPPING_FILE).write_text(json.dumps({"gateway_instance_id": gateway, **mapping}))
    return ApisixMeasurementSourceConfig(
        id=f"metrics-{gateway}-{env}", root=root, gateway_instance_id=gateway, environment=env
    )


def _mapping(**sections: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema": "aip-apisix-mapping/1",
        "route_operation": [],
        "target_service": [],
        **sections,
    }


def _run(driver, tmp_path, *, gateways, measurements) -> dict:
    examples = FilesystemSourceConfig(id="pin", root=REPO / "examples")
    run_all_configured_sources(
        SourcesConfig(directories=[examples], gateways=gateways, gateway_measurements=measurements),
        driver=driver,
        database=DATABASE,
    )
    return _state(driver)


def _service_id(state: dict, service_id: str) -> str:
    assert service_id in {s["id"] for s in state["services"]}  # declared by x-aip-service-id
    return service_id


def _operation_id(state: dict, method: str, path: str) -> str:
    return next(o["id"] for o in state["operations"] if (o["method"], o["path"]) == (method, path))


def _products_service(driver, tmp_path) -> str:
    """The canonical id of the example product service, read from a first, plain import."""
    run_all_configured_sources(
        SourcesConfig(directories=[FilesystemSourceConfig(id="pin", root=REPO / "examples")]),
        driver=driver,
        database=DATABASE,
    )
    return _service_id(_state(driver), "service:product-service")


def test_reconciliation_outcomes_are_derived_into_the_usage_block(driver, tmp_path) -> None:
    product_service = _products_service(driver, tmp_path)
    gateway = _gateway(
        tmp_path,
        routes=[
            _route("products-route", "/products/{id}", methods=["GET"], labels={"aip/service": product_service}),
            _route("orders-route", "/orders"),
            _route("none-route", "/nothing"),
        ],
    )  # fmt: skip
    measurement = _measurement(
        tmp_path,
        start=[_line("alice", "products-route") + " 1", _line("alice", "orders-route") + " 1"],
        end=[
            _line("alice", "products-route") + " 4",
            _line("alice", "orders-route") + " 2",
            _line("", "products-route", "401", "apisix") + " 1",
            _line("mallory", "ghost-route") + " 1",
        ],
    )
    state = _run(driver, tmp_path, gateways=[gateway], measurements=[measurement])
    block = state["api_usage_v1"]
    assert block["reconciliation_rule"] == {
        "rule_id": "apisix-api-usage-reconciliation",
        "rule_version": "1",
    }
    routes = {r["route_id"]: r["id"] for r in state["gateway_configuration_v1"]["routes"]}
    consumers = {c["username"]: c["id"] for c in state["gateway_configuration_v1"]["consumers"]}
    window_id = block["windows"][0]["id"]
    attributions = {(a["consumer"], a["route"]): a for a in block["attributions"]}
    alice = attributions[("alice", "products-route")]
    assert alice == {
        "window_id": window_id, "consumer": "alice", "route": "products-route",
        "consumer_outcome": "RESOLVED", "consumer_id": consumers["alice"],
        "route_outcome": "RESOLVED", "route_id": routes["products-route"],
    }  # fmt: skip
    assert attributions[("", "products-route")]["consumer_outcome"] == "UNRESOLVED"
    assert attributions[("", "products-route")]["route_outcome"] == "RESOLVED"
    ghost = attributions[("mallory", "ghost-route")]
    assert (ghost["consumer_outcome"], ghost["route_outcome"]) == ("UNRESOLVED", "UNRESOLVED")

    by_route = {row["route_id"]: row for row in block["route_operation"]}
    product_op = by_route[routes["products-route"]]
    assert product_op["operation"] == "RESOLVED"  # exact path + method, nothing else
    assert product_op["operation_id"] == _operation_id(state, "GET", "/products/{id}")
    assert product_op["contract_version"] in {"RESOLVED", "UNRESOLVED"}
    # POST /orders exists, the Route lists no methods: exactly one Operation on the exact path
    orders_op = by_route[routes["orders-route"]]
    assert orders_op["operation"] == "RESOLVED"
    assert orders_op["operation_id"] == _operation_id(state, "POST", "/orders")
    assert by_route[routes["none-route"]]["operation"] == "UNRESOLVED"

    targets = {row["route_id"]: row for row in block["target_service"]}
    assert targets[routes["products-route"]]["target"] == "RESOLVED"
    assert targets[routes["products-route"]]["service_id"] == product_service
    assert targets[routes["orders-route"]]["target"] == "UNRESOLVED"  # a name is not a statement


def test_an_explicit_mapping_is_authoritative_and_a_disagreement_is_a_conflict(
    driver, tmp_path
) -> None:
    product_service = _products_service(driver, tmp_path)
    state0 = _state(driver)
    get_product = _operation_id(state0, "GET", "/products/{id}")
    create_order = _operation_id(state0, "POST", "/orders")
    gateway = _gateway(
        tmp_path,
        routes=[
            _route("products-route", "/anything", labels={"aip/service": product_service}),
            _route("orders-route", "/orders"),
        ],
    )
    measurement = _measurement(
        tmp_path,
        end=[_line("alice", "products-route") + " 1"],
        mapping=_mapping(
            route_operation=[
                {"route_id": "products-route", "operation_id": get_product},
                {"route_id": "orders-route", "operation_id": get_product},
                {"route_id": "orders-route", "operation_id": create_order},
            ],
            target_service=[
                {"kind": "route", "id": "products-route", "service_id": _service_id(state0, "service:order-service")},
            ],
        ),
    )  # fmt: skip
    block = _run(driver, tmp_path, gateways=[gateway], measurements=[measurement])["api_usage_v1"]
    routes = {r["route_id"]: r["id"] for r in _state(driver)["gateway_configuration_v1"]["routes"]}
    by_route = {row["route_id"]: row for row in block["route_operation"]}
    assert by_route[routes["products-route"]]["operation"] == "RESOLVED"
    assert by_route[routes["products-route"]]["operation_id"] == get_product  # not the uri
    assert by_route[routes["orders-route"]]["operation"] == "CONFLICT"
    assert "operation_id" not in by_route[routes["orders-route"]]
    targets = {row["route_id"]: row for row in block["target_service"]}
    # the mapping names order-service, the label names product-service: a CONFLICT, not a pick
    assert targets[routes["products-route"]]["target"] == "CONFLICT"


def test_a_measurement_for_another_gateway_or_environment_joins_nothing(driver, tmp_path) -> None:
    gateway = _gateway(tmp_path, routes=[_route("products-route", "/products/{id}")])
    for other_gateway, other_env in (("gw-prod-2", ENV), (GW, "staging")):
        measurement = _measurement(
            tmp_path,
            gateway=other_gateway,
            env=other_env,
            end=[_line("alice", "products-route") + " 1"],
        )
        block = _run(driver, tmp_path, gateways=[gateway], measurements=[measurement])[
            "api_usage_v1"
        ]
        [row] = block["attributions"]
        assert (row["consumer_outcome"], row["route_outcome"]) == ("UNRESOLVED", "UNRESOLVED")
        assert block["route_operation"] == [] and block["target_service"] == []


def test_the_derived_sections_follow_the_inputs_and_the_snapshot_binds_them(
    driver, tmp_path
) -> None:
    gateway = _gateway(tmp_path, routes=[_route("orders-route", "/orders")])
    measurement = _measurement(tmp_path, end=[_line("alice", "orders-route") + " 1"])
    first = _run(driver, tmp_path, gateways=[gateway], measurements=[measurement])
    again = _state(driver)
    assert snapshot_fingerprint(again)[0] == snapshot_fingerprint(first)[0]  # stable
    orders_id = first["api_usage_v1"]["route_operation"][0]["route_id"]
    assert first["api_usage_v1"]["route_operation"][0]["operation"] == "RESOLVED"
    # adding an explicit mapping for the target changes the derived rows and the snapshot id
    mapped = _measurement(
        tmp_path,
        end=[_line("alice", "orders-route") + " 1"],
        mapping=_mapping(target_service=[{"kind": "route", "id": "orders-route", "service_id": "ghost"}]),
    )  # fmt: skip
    second = _run(driver, tmp_path, gateways=[gateway], measurements=[mapped])
    row = next(r for r in second["api_usage_v1"]["target_service"] if r["route_id"] == orders_id)
    assert row["target"] == "UNRESOLVED"  # the stated Service does not exist
    assert snapshot_fingerprint(second)[0] != snapshot_fingerprint(first)[0]


def test_a_graph_without_a_measurement_source_has_no_usage_block(driver, tmp_path) -> None:
    gateway = _gateway(tmp_path, routes=[_route("orders-route", "/orders")])
    state = _run(driver, tmp_path, gateways=[gateway], measurements=[])
    assert "api_usage_v1" not in state and "gateway_configuration_v1" in state
