"""Checks that a hand-authored oracle world is the exact frozen I2 handoff snapshot state
(`docs/specifications/0.7.0/i2-i3-handoff.md` §1), shared by the I3 oracle test and the I4 bridge
vector test. Each function returns a list of problems; an empty list means the world is sound.

Unlike the matcher and the property checker, this module imports `app` on purpose: the world is
validated *against* the repository's snapshot queries and the I2 rules, never the other way round -
the expected answers stay independent of the implementation they qualify."""

import re
from collections.abc import Mapping
from typing import Any

from app.architecture_intelligence.repository import _API_USAGE_QUERIES, _GATEWAY_QUERIES
from app.sources.apisix_qualification import qualify
from app.sources.apisix_reconciliation import reconcile

SECTIONS = {
    "gateway_configuration_v1": {
        "consumers",
        "routes",
        "services",
        "configured_access",
        "limitations",
        "source_evidence",
    },
    "api_usage_v1": {
        "windows",
        "evidence",
        "series",
        "limitations",
        "mapping_entries",
        "reconciliation_rule",
        "attributions",
        "route_operation",
        "target_service",
        "qualification_rule",
        "coverage",
        "interactions",
        "qualification_rows",
    },
    "api_contracts_v1": {"contracts", "versions", "associations"},
}


def _columns(query: str) -> set[str]:
    return set(re.findall(r" AS (\w+)", query))


def shape_problems(state: Mapping[str, Any]) -> list[str]:
    problems = []
    if not set(state) <= {"operations", "services", *SECTIONS}:
        problems.append(
            f"unexpected top-level keys {sorted(set(state) - {'operations', 'services', *SECTIONS})}"
        )
    for key, sections in SECTIONS.items():
        if key in state and set(state[key]) != sections:
            problems.append(f"{key} sections differ: {sorted(set(state[key]) ^ sections)}")
    return problems


def raw_row_problems(state: Mapping[str, Any]) -> list[str]:
    """Raw rows use only the repository's snapshot columns, are sorted by id and carry no null."""
    queries = {
        ("gateway_configuration_v1", section): _columns(query)
        for section, query in _GATEWAY_QUERIES.items()
    } | {
        ("api_usage_v1", section): _columns(query)  # type: ignore[arg-type]
        for section, query in _API_USAGE_QUERIES.items()
    }
    problems = []
    for (key, section), columns in queries.items():
        rows = state.get(key, {}).get(section, [])
        if [row["id"] for row in rows] != sorted(row["id"] for row in rows):
            problems.append(f"{key}.{section} is not sorted by id")
        for row in rows:
            if not set(row) <= columns:
                problems.append(f"{key}.{section} has foreign columns {sorted(set(row) - columns)}")
            if any(value is None for value in row.values()):
                problems.append(f"{key}.{section} has a null value")
    return problems


def reconciliation_problems(state: Mapping[str, Any]) -> list[str]:
    """`reconcile` applied to the raw facts, as serialized, reproduces the stated sections."""
    usage, gateway = state["api_usage_v1"], state["gateway_configuration_v1"]
    derived = reconcile(
        windows=usage["windows"],
        consumers=gateway["consumers"],
        routes=gateway["routes"],
        services=gateway["services"],
        series=usage["series"],
        mapping_entries=usage["mapping_entries"],
        operations=state["operations"],
        associations=state["api_contracts_v1"]["associations"],
        canonical_services=state["services"],
    )
    return [
        f"{section} differs from the I2 reconciliation rule"
        for section in ("reconciliation_rule", "attributions", "route_operation", "target_service")
        if usage[section] != derived[section]
    ]


def qualification_problems(state: Mapping[str, Any]) -> list[str]:
    """`qualify` applied to the raw facts, as serialized, reproduces the stated sections."""
    usage, gateway = state["api_usage_v1"], state["gateway_configuration_v1"]
    derived = qualify(
        windows=usage["windows"],
        consumers=gateway["consumers"],
        routes=gateway["routes"],
        configured_access=gateway["configured_access"],
        series=usage["series"],
        attributions=usage["attributions"],
    )
    return [
        f"{section} differs from the I2 qualification rule"
        for section in ("qualification_rule", "coverage", "interactions", "qualification_rows")
        if usage[section] != derived[section]
    ]


def world_problems(state: Mapping[str, Any]) -> list[str]:
    problems = shape_problems(state)
    if "api_usage_v1" in state:
        problems += raw_row_problems(state)
        problems += reconciliation_problems(state)
        problems += qualification_problems(state)
    return problems
