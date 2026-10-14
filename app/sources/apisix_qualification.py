"""v0.7.0 I2.4: the pure configured-vs-observed qualification (I2 spec §§6, 8, 9; I2.1 contract §7).
No I/O, no graph, no clock: a deterministic function of raw facts the snapshot already binds (the
APISIX configuration carriers, the measurement windows and series, and the I2.3 attributions). Like
the I2.3 reconciliation (the v0.5.0 I3 pattern) nothing is persisted; the rule id and version are
recorded in the snapshot, so a rule change is itself a fingerprint change.

It derives, per measurement window:

- `coverage`: per `GatewayRoute` of the window's `(gateway_instance_id, environment)`;
- `interactions`: per attributed `(GatewayRoute, GatewayConsumer)` pair with at least one series;
- `qualification_rows`: the bounded union of configured pairs and attributed observed pairs, never a
  Cartesian product.

Consumer and Route resolution comes from the I2.3 `attributions` (nothing is re-joined here) and the
per-series status from the I2.2 carriers (nothing is re-derived). The expected rows are the
independent vectors in `docs/specifications/0.7.0/i2-vectors/qualification.json`.
"""

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from app.canonical.gateway_measurement import (
    COUNTER_DECREASED,
    SERIES_ONE_BOUNDARY,
    observed_consumer_interaction_id,
    usage_qualification_id,
)
from app.sources.apisix_reconciliation import RESOLVED

QUALIFICATION_RULE_ID = "apisix-configured-vs-observed-qualification"
QUALIFICATION_RULE_VERSION = "1"

SUFFICIENT_FOR_ZERO = "SUFFICIENT_FOR_ZERO"
UNKNOWN_COVERAGE = "UNKNOWN_COVERAGE"

CONFIGURED_ACCESS_ESTABLISHED = "CONFIGURED_ACCESS_ESTABLISHED"
NO_MATCHING_CONFIGURED_ACCESS_FACT = "NO_MATCHING_CONFIGURED_ACCESS_FACT"

OBSERVED_USAGE = "OBSERVED_USAGE"
MEASURED_ZERO = "MEASURED_ZERO"
USAGE_UNESTABLISHED = "USAGE_UNESTABLISHED"

UPSTREAM = "upstream"
APISIX = "apisix"
UNATTRIBUTED_UPSTREAM = "GWM_UNATTRIBUTED_UPSTREAM"
CONSUMER_LABEL_DISABLED = "GWM_CONSUMER_LABEL_DISABLED"
ROUTE_COVERAGE_ABSENT = "GWM_ROUTE_COVERAGE_ABSENT"
ROUTE_PROMETHEUS_DISABLED = "GWM_ROUTE_PROMETHEUS_DISABLED"

_DELTA_STATUSES = ("DELTA", "DELTA_FIRST_IN_WINDOW")

Row = Mapping[str, Any]
Pair = tuple[str, str]  # (consumer carrier id, route carrier id)


def _scope(row: Row) -> tuple[str, str]:
    return row["gateway_instance_id"], row["environment"]


def _route_wide_codes(window_series: Sequence[Row], attributions: Mapping[Pair, Row]) -> dict:
    """Route label -> the route-wide series limitation codes (contract §7). Only upstream series
    affect coverage; a series on an unresolved Route belongs to no known Route."""
    codes: dict[str, set[str]] = defaultdict(set)
    for item in window_series:
        if item["response_source"] != UPSTREAM:
            continue
        attribution = attributions.get((item["consumer"], item["route"]))
        if attribution is None or attribution["route_outcome"] != RESOLVED:
            continue
        status = item["status"]
        # independent reasons: an unattributed series that is also broken carries both codes
        if attribution["consumer_outcome"] != RESOLVED:
            codes[item["route"]].add(UNATTRIBUTED_UPSTREAM)
        if status == "DECREASED":
            codes[item["route"]].add(COUNTER_DECREASED)
        elif status.startswith("ONE_BOUNDARY"):
            codes[item["route"]].add(SERIES_ONE_BOUNDARY)
    return codes


def _coverage(
    *, valid: bool, reasons: Sequence[str], window: Row, route_label: str, broken: set[str]
) -> tuple[str, list[str]]:
    if not valid:
        return UNKNOWN_COVERAGE, sorted(reasons)
    limits: set[str] = set(broken)
    if "consumer" in (window.get("disabled_labels") or ()):
        limits.add(CONSUMER_LABEL_DISABLED)
    route_coverage = json.loads(window.get("route_coverage_json") or "{}")
    if route_label not in route_coverage:
        limits.add(ROUTE_COVERAGE_ABSENT)
    elif not route_coverage[route_label]:
        limits.add(ROUTE_PROMETHEUS_DISABLED)
    return (UNKNOWN_COVERAGE if limits else SUFFICIENT_FOR_ZERO), sorted(limits)


def _usage_status(*, valid: bool, upstream: int, configured: bool, coverage: str) -> str:
    """Contract §7, first match wins."""
    if valid and upstream > 0:
        return OBSERVED_USAGE
    if valid and configured and coverage == SUFFICIENT_FOR_ZERO:
        return MEASURED_ZERO
    return USAGE_UNESTABLISHED


def qualify(
    *,
    windows: Sequence[Row],
    consumers: Sequence[Row],
    routes: Sequence[Row],
    configured_access: Sequence[Row],
    series: Sequence[Row],
    attributions: Sequence[Row],
) -> dict[str, Any]:
    """Every argument is a sequence of snapshot rows (`api_usage_v1`, `gateway_configuration_v1`).
    Returns the derived `api_usage_v1` sections `qualification_rule`, `coverage`, `interactions` and
    `qualification_rows`, each sorted by a stable key, with an absent key instead of a null.

    Scope: a window qualifies the Routes, Consumers and configured access of its own
    `(gateway_instance_id, environment)`. A configured pair is scoped by its Route; access whose
    Route or Consumer is outside the window's scope produces no row. Series on an unresolved Route,
    or from an unresolved consumer, create no row."""
    consumers_by_id = {consumer["id"]: consumer for consumer in consumers}
    routes_by_scope: dict[tuple[str, str], dict[str, Row]] = defaultdict(dict)
    for route in routes:
        routes_by_scope[_scope(route)][route["id"]] = route
    series_by_window: dict[str, list[Row]] = defaultdict(list)
    for item in series:
        series_by_window[item["window_id"]].append(item)
    attributions_by_window: dict[str, dict[Pair, Row]] = defaultdict(dict)
    for attribution in attributions:
        key = (attribution["consumer"], attribution["route"])
        attributions_by_window[attribution["window_id"]][key] = attribution

    coverage_rows: list[dict[str, Any]] = []
    interactions: list[dict[str, Any]] = []
    qualification_rows: list[dict[str, Any]] = []
    for window in windows:
        window_id = window["id"]
        scope = _scope(window)
        reasons = list(window.get("window_reasons") or ())
        valid = not reasons
        scoped_routes = routes_by_scope.get(scope, {})
        window_series = series_by_window.get(window_id, [])
        window_attributions = attributions_by_window.get(window_id, {})
        broken = _route_wide_codes(window_series, window_attributions)

        coverage_by_route: dict[str, tuple[str, list[str]]] = {}
        for route_id, route in scoped_routes.items():
            label = route["route_id"]
            coverage, limits = _coverage(
                valid=valid,
                reasons=reasons,
                window=window,
                route_label=label,
                broken=broken.get(label, set()),
            )
            coverage_by_route[route_id] = (coverage, limits)
            coverage_rows.append(
                {
                    "window_id": window_id,
                    "route_id": route_id,
                    "coverage": coverage,
                    "limitations": limits,
                }
            )

        # attributed observed pairs: (consumer id, route id) -> counts and series evidence
        observed: dict[Pair, dict[str, Any]] = {}
        for item in window_series:
            attribution = window_attributions.get((item["consumer"], item["route"]))
            if (
                attribution is None
                or attribution["route_outcome"] != RESOLVED
                or attribution["consumer_outcome"] != RESOLVED
            ):
                continue
            pair = (attribution["consumer_id"], attribution["route_id"])
            bucket = observed.setdefault(pair, {UPSTREAM: 0, APISIX: 0, "evidence_ids": set()})
            bucket["evidence_ids"].update(item.get("evidence_ids") or ())
            if valid and item["status"] in _DELTA_STATUSES:
                bucket[item["response_source"]] += item["request_count_delta"]

        configured: set[Pair] = set()
        for access in configured_access:
            route = scoped_routes.get(access["route_id"])
            consumer = consumers_by_id.get(access["consumer_id"])
            if route is not None and consumer is not None and _scope(consumer) == scope:
                configured.add((access["consumer_id"], access["route_id"]))

        window_evidence = sorted(window.get("evidence_ids") or ())
        for pair in sorted(observed.keys() | configured):
            consumer_id, route_id = pair
            counts = observed.get(pair)
            consumer_label = consumers_by_id[consumer_id]["username"]
            route_label = scoped_routes[route_id]["route_id"]
            args = (
                consumer_id,
                route_id,
                window["environment"],
                window["window_start"],
                window["window_end"],
            )
            base = {
                "window_id": window_id,
                "consumer_id": consumer_id,
                "route_id": route_id,
                "consumer": consumer_label,
                "route": route_label,
            }
            totals: dict[str, Any] = {}
            if valid:
                totals = {
                    "upstream_request_count": counts[UPSTREAM] if counts else 0,
                    "rejected_attempt_count": counts[APISIX] if counts else 0,
                }
            row: dict[str, Any] = {
                "id": usage_qualification_id(*args),
                **base,
                "configured_status": (
                    CONFIGURED_ACCESS_ESTABLISHED
                    if pair in configured
                    else NO_MATCHING_CONFIGURED_ACCESS_FACT
                ),
                "usage_status": _usage_status(
                    valid=valid,
                    upstream=totals.get("upstream_request_count", 0),
                    configured=pair in configured,
                    coverage=coverage_by_route[route_id][0],
                ),
                "coverage": coverage_by_route[route_id][0],
                **totals,
                "limitations": coverage_by_route[route_id][1],
                "evidence_ids": window_evidence,
            }
            if counts is not None:
                interaction_id = observed_consumer_interaction_id(*args)
                row["interaction_id"] = interaction_id
                interactions.append(
                    {
                        "id": interaction_id,
                        **base,
                        **totals,
                        "evidence_ids": sorted(counts["evidence_ids"]),
                    }
                )
            qualification_rows.append(row)

    def by_pair(r: Row) -> tuple[str, str, str]:
        return r["window_id"], r["consumer"], r["route"]

    return {
        "qualification_rule": {
            "rule_id": QUALIFICATION_RULE_ID,
            "rule_version": QUALIFICATION_RULE_VERSION,
        },
        "coverage": sorted(coverage_rows, key=lambda r: (r["window_id"], r["route_id"])),
        "interactions": sorted(interactions, key=by_pair),
        "qualification_rows": sorted(qualification_rows, key=by_pair),
    }
