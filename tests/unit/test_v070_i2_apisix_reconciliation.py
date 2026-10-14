"""v0.7.0 I2.3: the production reconciliation against the independent I2.1 vectors J, K and T
(`docs/specifications/0.7.0/i2-vectors/reconciliation.json`). Every vector goes through `reconcile` on
synthetic snapshot rows, so the row reading, the per-window scoping and the outcome rules are all
under test; nothing is imported from the vector-reference test."""

import json
import random
from pathlib import Path
from typing import Any

import pytest

from app.sources.apisix_reconciliation import (
    RECONCILIATION_RULE_ID,
    RECONCILIATION_RULE_VERSION,
    reconcile,
)

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i2-vectors"
GW, ENV = "gw-prod-1", "prod"


def _vectors() -> dict[str, Any]:
    return json.loads((VECTORS / "reconciliation.json").read_text(encoding="utf-8"))


def _window(gateway: str = GW, env: str = ENV) -> dict[str, Any]:
    return {"id": "window-1", "gateway_instance_id": gateway, "environment": env}


def _route_row(route: dict[str, Any], gateway: str = GW, env: str = ENV) -> dict[str, Any]:
    row = {
        "id": f"carrier:route:{route['id']}",
        "gateway_instance_id": gateway,
        "environment": env,
        "route_id": route["id"],
        "uris": route.get("uris", []),
        "methods": route.get("methods", []),
        "labels_json": json.dumps(route.get("labels", {})),
    }
    for key in ("uri", "service_id"):
        if route.get(key):
            row[key] = route[key]
    return row


def _operation_rows(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": o["id"], "method": o["method"], "path": o["path"]} for o in operations]


def _association_rows(by_operation: dict[str, list[str]]) -> list[dict[str, Any]]:
    return [
        {"kind": "OPERATION_IN_CONTRACT_VERSION", "target_id": op, "contract_version_id": cv}
        for op, versions in by_operation.items()
        for cv in versions
    ]


def _mapping_rows(
    route_operation: list[dict[str, Any]],
    target_service: list[dict[str, Any]],
    gateway: str = GW,
    env: str = ENV,
) -> list[dict[str, Any]]:
    scope = {"gateway_instance_id": gateway, "environment": env}
    return [
        {**scope, "kind": "route_operation", "source_id": m["route_id"], "target_id": m["operation_id"]}
        for m in route_operation
    ] + [
        {
            **scope,
            "kind": "target_service_route" if m["kind"] == "route" else "target_service_service",
            "source_id": m["id"],
            "target_id": m["service_id"],
        }
        for m in target_service
    ]  # fmt: skip


def _route_operation(case: dict[str, Any]) -> dict[str, Any]:
    inputs = case["inputs"]
    result = reconcile(
        windows=[_window()],
        consumers=[],
        routes=[_route_row(inputs["route"])],
        services=[],
        series=[],
        mapping_entries=_mapping_rows(inputs["explicit_route_operation"], []),
        operations=_operation_rows(inputs["operations"]),
        associations=_association_rows(inputs["operation_contract_versions"]),
        canonical_services=[],
    )
    [row] = result["route_operation"]
    return {
        "operation": row["operation"],
        "operation_id": row.get("operation_id"),
        "contract_version": row.get("contract_version"),
        "contract_version_id": row.get("contract_version_id"),
    }


def _target_service(inputs: dict[str, Any]) -> dict[str, Any]:
    route = inputs["route"]
    services = [
        {
            "id": f"carrier:service:{s['id']}",
            "gateway_instance_id": GW,
            "environment": ENV,
            "service_id": s["id"],
            "labels_json": json.dumps(s["labels"]),
        }
        for s in inputs["gateway_services"]
    ]
    result = reconcile(
        windows=[_window()],
        consumers=[],
        routes=[_route_row(route)],
        services=services,
        series=[],
        mapping_entries=_mapping_rows([], inputs["explicit_target_service"]),
        operations=[],
        associations=[],
        canonical_services=[{"id": sid} for sid in inputs["canonical_service_ids"]],
    )
    [row] = result["target_service"]
    return {"target": row["target"], "service_id": row.get("service_id")}


def _runtime_join(inputs: dict[str, Any]) -> dict[str, str]:
    inventory, measurement = inputs["inventory"], inputs["measurement"]
    result = reconcile(
        windows=[_window(measurement["gateway_instance_id"], measurement["environment"])],
        consumers=[
            {
                "id": f"carrier:consumer:{name}",
                "gateway_instance_id": inventory["gateway_instance_id"],
                "environment": inventory["environment"],
                "username": name,
            }
            for name in inventory["consumers"]
        ],
        routes=[
            _route_row({"id": r}, inventory["gateway_instance_id"], inventory["environment"])
            for r in inventory["routes"]
        ],
        services=[],
        series=[
            {"window_id": "window-1", "consumer": inputs["consumer"], "route": inputs["route"]}
        ],
        mapping_entries=[],
        operations=[],
        associations=[],
        canonical_services=[],
    )
    [row] = result["attributions"]
    return {"consumer": row["consumer_outcome"], "route": row["route_outcome"]}


_CASES = _vectors()["cases"]


@pytest.mark.parametrize(
    "case", [c for c in _CASES if c["kind"] == "runtime-join"], ids=lambda c: c["id"]
)
def test_runtime_join_vectors(case: dict[str, Any]) -> None:
    assert _runtime_join(case["inputs"]) == case["expected"]


@pytest.mark.parametrize(
    "case", [c for c in _CASES if c["kind"] == "route-operation"], ids=lambda c: c["id"]
)
def test_route_operation_vectors(case: dict[str, Any]) -> None:
    got = _route_operation(case)
    expected = case["expected"]
    assert {k: got[k] for k in expected} == expected


@pytest.mark.parametrize(
    "case", [c for c in _CASES if c["kind"] == "target-service"], ids=lambda c: c["id"]
)
def test_target_service_vectors(case: dict[str, Any]) -> None:
    assert _target_service(case["inputs"]) == case["expected"]


@pytest.mark.parametrize(
    "case", [c for c in _CASES if c["kind"] == "independence"], ids=lambda c: c["id"]
)
def test_the_two_chains_are_independent(case: dict[str, Any]) -> None:
    inputs, expected = case["inputs"], case["expected"]
    target = _target_service(inputs["target_service"])
    operation = _route_operation({"inputs": inputs["route_operation"], "expected": {}})
    assert operation["operation"] == expected["operation"]
    assert target["target"] == expected["target"]
    assert target["service_id"] == expected["service_id"]
    if "operation_id" in expected:
        assert operation["operation_id"] == expected["operation_id"]


def test_every_outcome_value_is_exercised() -> None:
    seen: set[str] = set()
    for case in _CASES:
        seen.update(v for v in case["expected"].values() if isinstance(v, str))
    assert {"RESOLVED", "UNRESOLVED", "AMBIGUOUS", "CONFLICT"} <= seen


def test_the_rule_id_and_version_are_part_of_the_output() -> None:
    result = reconcile(
        windows=[], consumers=[], routes=[], services=[], series=[], mapping_entries=[],
        operations=[], associations=[], canonical_services=[],
    )  # fmt: skip
    assert result["reconciliation_rule"] == {
        "rule_id": RECONCILIATION_RULE_ID,
        "rule_version": RECONCILIATION_RULE_VERSION,
    }
    assert result["attributions"] == result["route_operation"] == result["target_service"] == []


def _scenario() -> dict[str, Any]:
    routes = [
        _route_row({"id": "orders-route", "uri": "/orders", "methods": ["GET"]}),
        _route_row(
            {"id": "billing-route", "uri": "/invoices", "labels": {"aip/service": "billing"}}
        ),
        _route_row({"id": "ghost-route", "uri": "/nothing"}),
    ]
    return {
        "windows": [_window(), {**_window("gw-prod-2"), "id": "window-2"}],
        "consumers": [
            {"id": "c-alice", "gateway_instance_id": GW, "environment": ENV, "username": "alice"},
            {"id": "c-bob", "gateway_instance_id": GW, "environment": ENV, "username": "bob"},
        ],
        "routes": routes,
        "services": [],
        "series": [
            {"window_id": "window-1", "consumer": "alice", "route": "orders-route"},
            {"window_id": "window-1", "consumer": "", "route": "orders-route"},
            {"window_id": "window-1", "consumer": "mallory", "route": "unknown-route"},
            {"window_id": "window-1", "consumer": "bob", "route": "billing-route"},
            {"window_id": "window-2", "consumer": "alice", "route": "orders-route"},
        ],
        "mapping_entries": _mapping_rows(
            [{"route_id": "ghost-route", "operation_id": "op:orders:get:/orders"}], []
        ),
        "operations": [
            {"id": "op:orders:get:/orders", "method": "GET", "path": "/orders"},
            {"id": "op:billing:get:/invoices", "method": "GET", "path": "/invoices"},
        ],
        "associations": _association_rows({"op:orders:get:/orders": ["cv:orders:1.0"]}),
        "canonical_services": [{"id": "orders"}, {"id": "billing"}],
    }


def test_the_output_is_independent_of_input_order() -> None:
    scenario = _scenario()
    expected = reconcile(**scenario)
    rng = random.Random(7)
    for _ in range(5):
        shuffled = {k: rng.sample(v, len(v)) for k, v in scenario.items()}
        assert reconcile(**shuffled) == expected


def test_a_scenario_resolves_each_window_against_its_own_gateway_and_environment() -> None:
    result = reconcile(**_scenario())
    by_key = {(r["window_id"], r["consumer"], r["route"]): r for r in result["attributions"]}
    alice = by_key[("window-1", "alice", "orders-route")]
    assert (alice["consumer_outcome"], alice["route_outcome"]) == ("RESOLVED", "RESOLVED")
    assert alice["consumer_id"] == "c-alice" and alice["route_id"] == "carrier:route:orders-route"
    assert by_key[("window-1", "", "orders-route")]["consumer_outcome"] == "UNRESOLVED"
    unknown = by_key[("window-1", "mallory", "unknown-route")]
    assert (unknown["consumer_outcome"], unknown["route_outcome"]) == ("UNRESOLVED", "UNRESOLVED")
    # another gateway instance never joins the first one's inventory
    other = by_key[("window-2", "alice", "orders-route")]
    assert (other["consumer_outcome"], other["route_outcome"]) == ("UNRESOLVED", "UNRESOLVED")
    assert "consumer_id" not in other and "route_id" not in other
    # window-2 has no inventory, so it produces no Route rows
    assert {r["window_id"] for r in result["route_operation"]} == {"window-1"}
    operations = {r["route_id"]: r for r in result["route_operation"]}
    orders = operations["carrier:route:orders-route"]
    assert (orders["operation"], orders["operation_id"], orders["contract_version"]) == (
        "RESOLVED", "op:orders:get:/orders", "RESOLVED",
    )  # fmt: skip
    assert orders["contract_version_id"] == "cv:orders:1.0"
    billing = operations["carrier:route:billing-route"]
    assert billing["contract_version"] == "UNRESOLVED" and billing["operation"] == "RESOLVED"
    ghost = operations["carrier:route:ghost-route"]
    assert ghost["operation_id"] == "op:orders:get:/orders"  # the explicit mapping is authoritative
    targets = {r["route_id"]: r for r in result["target_service"]}
    assert targets["carrier:route:billing-route"]["service_id"] == "billing"
    assert targets["carrier:route:orders-route"]["target"] == "UNRESOLVED"  # no statement


def test_names_hosts_and_neighbourhood_never_resolve_anything() -> None:
    """A Route called like a Service, an upstream host named like a Service, and an Operation on a
    similar path resolve nothing: only explicit statements and the exact fallback do."""
    route = _route_row({"id": "orders", "uri": "/order", "service_id": "orders"})
    route["upstream_nodes"] = ["orders:80"]
    result = reconcile(
        windows=[_window()], consumers=[], routes=[route], services=[], series=[],
        mapping_entries=[],
        operations=[{"id": "op:o", "method": "GET", "path": "/orders"}],
        associations=[], canonical_services=[{"id": "orders"}],
    )  # fmt: skip
    assert result["route_operation"][0]["operation"] == "UNRESOLVED"
    assert result["target_service"][0]["target"] == "UNRESOLVED"


def test_a_wildcard_uri_is_a_pattern_even_when_an_operation_path_spells_it_literally() -> None:
    """Contract §6: a `*` uri is never compared (K10's vector has no such Operation, so it cannot tell
    a skipped comparison from a failed one)."""
    result = reconcile(
        windows=[_window()],
        consumers=[],
        routes=[_route_row({"id": "r1", "uri": "/orders/*"})],
        services=[],
        series=[],
        mapping_entries=[],
        operations=[{"id": "op:literal", "method": "GET", "path": "/orders/*"}],
        associations=[],
        canonical_services=[],
    )
    assert result["route_operation"][0]["operation"] == "UNRESOLVED"


def test_two_statements_conflict_even_when_one_of_them_matches_the_exact_fallback() -> None:
    result = reconcile(
        windows=[_window()],
        consumers=[],
        routes=[_route_row({"id": "r1", "uri": "/orders", "methods": ["GET"]})],
        services=[],
        series=[],
        mapping_entries=_mapping_rows(
            [
                {"route_id": "r1", "operation_id": "op:a"},
                {"route_id": "r1", "operation_id": "op:b"},
            ],
            [],
        ),
        operations=[
            {"id": "op:a", "method": "GET", "path": "/x"},
            {"id": "op:b", "method": "GET", "path": "/y"},
            {"id": "op:orders", "method": "GET", "path": "/orders"},
        ],
        associations=[],
        canonical_services=[],
    )
    row = result["route_operation"][0]
    assert row["operation"] == "CONFLICT" and "operation_id" not in row
