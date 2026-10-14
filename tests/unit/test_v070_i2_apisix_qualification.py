"""v0.7.0 I2.4: the production qualification against the independent I2.1 vectors Q01-Q30
(`docs/specifications/0.7.0/i2-vectors/qualification.json`) and the id vectors M06-M09. Every vector
goes through `qualify` on synthetic snapshot rows shaped like the I2.2 carriers (window reasons and
per-series statuses come from the production measurement contract) and the I2.3 `reconcile`
attributions, so the row reading, scoping, coverage and precedence rules are all under test."""

import json
import random
from pathlib import Path
from typing import Any

import pytest

from app.canonical.gateway_measurement import (
    observed_consumer_interaction_id,
    usage_qualification_id,
)
from app.sources.apisix_measurement_contract import (
    Manifest,
    first_in_window_allowed,
    series_status,
    window_reasons,
)
from app.sources.apisix_qualification import (
    QUALIFICATION_RULE_ID,
    QUALIFICATION_RULE_VERSION,
    qualify,
)
from app.sources.apisix_reconciliation import reconcile

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i2-vectors"
GW, ENV = "gw-prod-1", "prod"
ROW_FIELDS = (
    "consumer",
    "route",
    "configured_status",
    "usage_status",
    "coverage",
    "upstream_request_count",
    "rejected_attempt_count",
    "limitations",
)


def _vectors(name: str) -> dict[str, Any]:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _manifest(document: dict[str, Any]) -> Manifest:
    return Manifest(
        gateway_instance_id=GW,
        environment=ENV,
        apisix_version=document["apisix_version"],
        window_start=document["window_start"],
        window_end=document["window_end"],
        start_settled=document["start_settled"],
        end_settled=document["end_settled"],
        start_scrape_count=2,
        end_scrape_count=2,
        start_stable_seconds=document["start_stable_seconds"],
        end_stable_seconds=document["end_stable_seconds"],
        no_restart=document["no_restart"],
        disabled_labels=tuple(document["disabled_labels"]),
        route_coverage=document["route_coverage"],
        start_sha256="0" * 64,
        end_sha256="1" * 64,
    )


def _window_row(document: dict[str, Any], *, gateway: str = GW, env: str = ENV) -> dict[str, Any]:
    return {
        "id": "window-1",
        "gateway_instance_id": gateway,
        "environment": env,
        "window_start": document["window_start"],
        "window_end": document["window_end"],
        "disabled_labels": sorted(document["disabled_labels"]),
        "route_coverage_json": json.dumps(document["route_coverage"], sort_keys=True),
        "window_reasons": window_reasons(_manifest(document)),
        "evidence_ids": ["evidence:window-1"],
    }


def _series_rows(document: dict[str, Any], series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest = _manifest(document)
    valid = not window_reasons(manifest)
    rows = []
    for index, item in enumerate(series):
        status, delta = series_status(
            item["start"],
            item["end"],
            first_in_window=first_in_window_allowed(manifest, item["route"]),
        )
        row: dict[str, Any] = {
            "id": f"series-{index}",
            "window_id": "window-1",
            "route": item["route"],
            "consumer": item["consumer"],
            "code": item["code"],
            "response_source": item["response_source"],
            "status": status if valid else "WINDOW_INVALID",
            "evidence_ids": ["evidence:window-1"],
        }
        if valid and delta is not None:
            row["request_count_delta"] = delta
        rows.append(row)
    return rows


def _inventory(
    inventory: dict[str, Any], gateway: str = GW, env: str = ENV
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scope = {"gateway_instance_id": gateway, "environment": env}
    consumers = [{"id": f"consumer:{n}", "username": n, **scope} for n in inventory["consumers"]]
    routes = [{"id": f"route:{n}", "route_id": n, **scope} for n in inventory["routes"]]
    return consumers, routes


def _access(pairs: list[list[str]]) -> list[dict[str, Any]]:
    return [{"consumer_id": f"consumer:{c}", "route_id": f"route:{r}"} for c, r in pairs]


def _run(
    document: dict[str, Any],
    inventory: dict[str, Any],
    configured: list[list[str]],
    series: list[dict[str, Any]],
    *,
    gateway: str = GW,
    env: str = ENV,
    window_scope: tuple[str, str] = (GW, ENV),
) -> dict[str, Any]:
    consumers, routes = _inventory(inventory, gateway, env)
    windows = [_window_row(document, gateway=window_scope[0], env=window_scope[1])]
    series_rows = _series_rows(document, series)
    attributions = reconcile(
        windows=windows,
        consumers=consumers,
        routes=routes,
        services=[],
        series=series_rows,
        mapping_entries=[],
        operations=[],
        associations=[],
        canonical_services=[],
    )["attributions"]
    return qualify(
        windows=windows,
        consumers=consumers,
        routes=routes,
        configured_access=_access(configured),
        series=series_rows,
        attributions=attributions,
    )


def _case_result(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    doc = _vectors("qualification.json")
    case = next(c for c in doc["cases"] if c["id"] == case_id)
    document = {**doc["base_manifest"], **case["manifest_patch"]}
    return case, _run(document, doc["inventory"], case["configured_access"], case["series"])


def _vector_ids() -> list[str]:
    return [c["id"] for c in _vectors("qualification.json")["cases"]]


@pytest.mark.parametrize("case_id", _vector_ids())
def test_every_qualification_vector_through_the_production_function(case_id: str) -> None:
    case, result = _case_result(case_id)
    rows = [
        {k: v for k, v in row.items() if k in ROW_FIELDS} for row in result["qualification_rows"]
    ]
    expected = [
        {k: v for k, v in row.items() if k in ROW_FIELDS or v is not None}
        for row in case["expected_rows"]
    ]
    # an invalid window carries null counts in the vector; the snapshot omits the key instead
    expected = [{k: v for k, v in row.items() if v is not None} for row in expected]
    assert rows == expected


@pytest.mark.parametrize("case_id", _vector_ids())
def test_rule_id_and_a_row_per_pair_with_one_interaction_per_attributed_series_pair(
    case_id: str,
) -> None:
    _, result = _case_result(case_id)
    assert result["qualification_rule"] == {
        "rule_id": QUALIFICATION_RULE_ID,
        "rule_version": QUALIFICATION_RULE_VERSION,
    }
    row_ids = {r["id"] for r in result["qualification_rows"]}
    assert len(row_ids) == len(result["qualification_rows"])
    interaction_ids = {i["id"] for i in result["interactions"]}
    assert {r["interaction_id"] for r in result["qualification_rows"] if "interaction_id" in r} == (
        interaction_ids
    )
    assert all(r["evidence_ids"] == ["evidence:window-1"] for r in result["qualification_rows"])


def test_the_ids_follow_the_independent_vectors_m06_to_m09() -> None:
    by_id = {v["id"]: v for v in _vectors("ids.json")["vectors"]}
    for vector_id in ("M06", "M07", "M08"):
        assert (
            observed_consumer_interaction_id(**by_id[vector_id]["inputs"])
            == by_id[vector_id]["expected"]
        )
    assert usage_qualification_id(**by_id["M09"]["inputs"]) == by_id["M09"]["expected"]


def test_a_row_and_its_interaction_get_the_ids_of_the_frozen_formulas() -> None:
    doc = _vectors("qualification.json")
    case = next(c for c in doc["cases"] if c["id"] == "Q01")
    _, result = _case_result("Q01")
    [row] = result["qualification_rows"]
    [interaction] = result["interactions"]
    args = (
        "consumer:spike-alpha",
        "route:orders-route",
        ENV,
        doc["base_manifest"]["window_start"],
        doc["base_manifest"]["window_end"],
    )
    assert row["id"] == usage_qualification_id(*args)
    assert interaction["id"] == observed_consumer_interaction_id(*args) == row["interaction_id"]
    assert (interaction["upstream_request_count"], interaction["rejected_attempt_count"]) == (3, 0)
    assert case["expected_rows"][0]["upstream_request_count"] == 3


def test_a_configured_pair_without_series_has_a_row_but_no_interaction() -> None:
    _, result = _case_result("Q02")
    assert [r["usage_status"] for r in result["qualification_rows"]] == ["MEASURED_ZERO"]
    assert result["interactions"] == []


def test_rejected_attempts_are_counted_without_creating_usage_or_access() -> None:
    _, result = _case_result("Q09")
    [row] = result["qualification_rows"]
    assert row["configured_status"] == "NO_MATCHING_CONFIGURED_ACCESS_FACT"
    assert row["usage_status"] == "USAGE_UNESTABLISHED"
    assert row["rejected_attempt_count"] > 0 and row["upstream_request_count"] == 0
    [interaction] = result["interactions"]
    assert interaction["rejected_attempt_count"] == row["rejected_attempt_count"]


def test_an_invalid_window_keeps_the_pair_but_drops_counts_and_interactions_keep_no_counts() -> (
    None
):
    _, result = _case_result("Q21")
    [row] = result["qualification_rows"]
    assert row["usage_status"] == "USAGE_UNESTABLISHED"
    assert "upstream_request_count" not in row and "rejected_attempt_count" not in row
    [interaction] = result["interactions"]
    assert "upstream_request_count" not in interaction


def test_unattributed_and_unknown_route_series_create_no_interaction_and_no_row() -> None:
    for case_id in ("Q11", "Q13", "Q20"):
        case, result = _case_result(case_id)
        assert [r["consumer"] for r in result["qualification_rows"]] == [
            r["consumer"] for r in case["expected_rows"]
        ], case_id
    _, unattributed = _case_result("Q11")
    assert unattributed["interactions"] == []


def test_there_is_a_coverage_row_for_every_route_of_the_windows_scope() -> None:
    doc = _vectors("qualification.json")
    _, result = _case_result("Q01")
    assert [(c["route_id"], c["coverage"]) for c in result["coverage"]] == [
        ("route:billing-route", "SUFFICIENT_FOR_ZERO"),
        ("route:orders-route", "SUFFICIENT_FOR_ZERO"),
    ]
    assert len(result["coverage"]) == len(doc["inventory"]["routes"])
    _, unknown = _case_result("Q17")
    assert {c["route_id"]: c["coverage"] for c in unknown["coverage"]}["route:orders-route"] == (
        "UNKNOWN_COVERAGE"
    )


def test_the_universe_is_the_bounded_union_not_a_cartesian_product() -> None:
    doc = _vectors("qualification.json")
    document = dict(doc["base_manifest"])
    result = _run(document, doc["inventory"], [["spike-alpha", "orders-route"]], [])
    # three consumers and two routes exist, but only the one configured pair has a row
    assert [(r["consumer"], r["route"]) for r in result["qualification_rows"]] == [
        ("spike-alpha", "orders-route")
    ]


def test_access_and_inventory_of_another_gateway_or_environment_do_not_join() -> None:
    doc = _vectors("qualification.json")
    document = dict(doc["base_manifest"])
    series = [
        {
            "route": "orders-route",
            "consumer": "spike-alpha",
            "code": "200",
            "response_source": "upstream",
            "start": 1,
            "end": 4,
        }
    ]
    for scope in (("gw-other", ENV), (GW, "staging")):
        result = _run(
            document,
            doc["inventory"],
            [["spike-alpha", "orders-route"]],
            series,
            gateway=scope[0],
            env=scope[1],
        )
        assert result["qualification_rows"] == [] and result["interactions"] == []
        assert result["coverage"] == []


def test_output_is_independent_of_input_order() -> None:
    doc = _vectors("qualification.json")
    case = next(c for c in doc["cases"] if c["id"] == "Q24")
    document = {**doc["base_manifest"], **case["manifest_patch"]}
    consumers, routes = _inventory(doc["inventory"])
    windows = [_window_row(document)]
    series_rows = _series_rows(document, case["series"])
    attributions = reconcile(
        windows=windows,
        consumers=consumers,
        routes=routes,
        services=[],
        series=series_rows,
        mapping_entries=[],
        operations=[],
        associations=[],
        canonical_services=[],
    )["attributions"]
    access = _access(case["configured_access"])

    def run() -> dict[str, Any]:
        return qualify(
            windows=windows,
            consumers=consumers,
            routes=routes,
            configured_access=access,
            series=series_rows,
            attributions=attributions,
        )

    baseline = run()
    rng = random.Random(7)
    for rows in (consumers, routes, access, series_rows, attributions):
        rng.shuffle(rows)
    assert run() == baseline
