"""v0.7.0 I2.3: the pure APISIX reconciliation (I2 spec §7, I2.1 contract §6). No I/O, no graph, no
clock: a deterministic function of raw facts the snapshot already binds (the APISIX configuration
carriers, the measurement carriers, the OpenAPI `Operation`s and contract associations, the
application `Service` ids). That is the v0.5.0 I3 pattern: nothing is persisted, and the rule id and
version are recorded in the snapshot, so a rule change is itself a fingerprint change.

Four outcomes only (not public wire vocabulary): `RESOLVED`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`.
Two independent chains, neither reading the other's result:

    Gateway Route -> Operation -> ApiContractVersion
    Gateway target (Route / Gateway Service) -> application Service

Nothing here infers an association from a name, host, path similarity or graph neighbourhood. The
expected results are the independent vectors in
`docs/specifications/0.7.0/i2-vectors/reconciliation.json`.
"""

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

RECONCILIATION_RULE_ID = "apisix-api-usage-reconciliation"
RECONCILIATION_RULE_VERSION = "1"

RESOLVED = "RESOLVED"
UNRESOLVED = "UNRESOLVED"
AMBIGUOUS = "AMBIGUOUS"
CONFLICT = "CONFLICT"

AIP_SERVICE_LABEL = "aip/service"
OPERATION_IN_CONTRACT_VERSION = "OPERATION_IN_CONTRACT_VERSION"

Row = Mapping[str, Any]


def _scope(row: Row) -> tuple[str, str]:
    return row["gateway_instance_id"], row["environment"]


def _resolve_operation(
    route: Row,
    statements: set[str],
    operations_by_path: Mapping[str, Sequence[Row]],
    known: set[str],
) -> tuple[str, str | None]:
    """Contract §6 steps 1-2: explicit statements are authoritative and are not compared with the
    fallback; the fallback is exact and unique or nothing."""
    if len(statements) > 1:
        return CONFLICT, None
    if statements:
        (operation_id,) = statements
        return (RESOLVED, operation_id) if operation_id in known else (UNRESOLVED, None)
    uri = route.get("uri")
    if not uri or route.get("uris") or "*" in uri:
        return UNRESOLVED, None
    methods = {method.upper() for method in route.get("methods") or ()}
    found = [
        operation["id"]
        for operation in operations_by_path.get(uri, ())
        if not methods or operation["method"].upper() in methods
    ]
    if len(found) == 1:
        return RESOLVED, found[0]
    return (AMBIGUOUS if found else UNRESOLVED), None


def _resolve_contract_version(versions: set[str]) -> tuple[str, str | None]:
    """Contract §6 step 3, evaluated only for a `RESOLVED` Operation."""
    if len(versions) > 1:
        return CONFLICT, None
    if versions:
        (version_id,) = versions
        return RESOLVED, version_id
    return UNRESOLVED, None


def _resolve_target(
    statements: set[str], canonical_service_ids: set[str]
) -> tuple[str, str | None]:
    if len(statements) > 1:
        return CONFLICT, None
    if statements:
        (service_id,) = statements
        return (RESOLVED, service_id) if service_id in canonical_service_ids else (UNRESOLVED, None)
    return UNRESOLVED, None


def _labels(row: Row) -> dict[str, str]:
    raw = row.get("labels_json")
    return json.loads(raw) if raw else {}


def reconcile(
    *,
    windows: Sequence[Row],
    consumers: Sequence[Row],
    routes: Sequence[Row],
    services: Sequence[Row],
    series: Sequence[Row],
    mapping_entries: Sequence[Row],
    operations: Sequence[Row],
    associations: Sequence[Row],
    canonical_services: Sequence[Row],
) -> dict[str, Any]:
    """Every argument is a sequence of snapshot rows (`gateway_configuration_v1`, `api_usage_v1`,
    `api_contracts_v1`, `operations`, `services`). Returns the derived `api_usage_v1` sections
    `reconciliation_rule`, `attributions`, `route_operation` and `target_service`, each sorted by a
    stable key, with an absent key instead of a null.

    Scope: a window reconciles against the Routes, Consumers and Gateway Services of its own
    `(gateway_instance_id, environment)` and the mapping entries of that pair. A window with no such
    inventory resolves nothing (`UNRESOLVED`); it is not an error. A mapping entry naming no known
    Route produces no row."""
    operations_by_path: dict[str, list[Row]] = defaultdict(list)
    for operation in operations:
        operations_by_path[operation["path"]].append(operation)
    operation_ids = {operation["id"] for operation in operations}
    canonical_service_ids = {service["id"] for service in canonical_services}
    versions_by_operation: dict[str, set[str]] = defaultdict(set)
    for association in associations:
        if association.get("kind") == OPERATION_IN_CONTRACT_VERSION:
            versions_by_operation[association["target_id"]].add(association["contract_version_id"])

    consumers_by_scope: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for consumer in consumers:
        consumers_by_scope[_scope(consumer)][consumer["username"]] = consumer["id"]
    routes_by_scope: dict[tuple[str, str], list[Row]] = defaultdict(list)
    for route in routes:
        routes_by_scope[_scope(route)].append(route)
    services_by_scope: dict[tuple[str, str], dict[str, Row]] = defaultdict(dict)
    for service in services:
        services_by_scope[_scope(service)][service["service_id"]] = service
    mappings_by_scope: dict[tuple[str, str], list[Row]] = defaultdict(list)
    for entry in mapping_entries:
        mappings_by_scope[_scope(entry)].append(entry)
    series_by_window: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for item in series:
        series_by_window[item["window_id"]].add((item["consumer"], item["route"]))

    attributions: list[dict[str, Any]] = []
    route_operation: list[dict[str, Any]] = []
    target_service: list[dict[str, Any]] = []
    for window in windows:
        scope = _scope(window)
        window_id = window["id"]
        scoped_consumers = consumers_by_scope.get(scope, {})
        scoped_routes = {route["route_id"]: route for route in routes_by_scope.get(scope, ())}
        for consumer_label, route_label in sorted(series_by_window.get(window_id, ())):
            row: dict[str, Any] = {
                "window_id": window_id,
                "consumer": consumer_label,
                "route": route_label,
                "consumer_outcome": UNRESOLVED,
                "route_outcome": UNRESOLVED,
            }
            if consumer_label and consumer_label in scoped_consumers:
                row["consumer_outcome"] = RESOLVED
                row["consumer_id"] = scoped_consumers[consumer_label]
            if route_label in scoped_routes:
                row["route_outcome"] = RESOLVED
                row["route_id"] = scoped_routes[route_label]["id"]
            attributions.append(row)

        entries = mappings_by_scope.get(scope, ())
        for route in scoped_routes.values():
            apisix_route_id = route["route_id"]
            operation_statements = {
                entry["target_id"]
                for entry in entries
                if entry["kind"] == "route_operation" and entry["source_id"] == apisix_route_id
            }
            outcome, operation_id = _resolve_operation(
                route, operation_statements, operations_by_path, operation_ids
            )
            operation_row: dict[str, Any] = {
                "window_id": window_id,
                "route_id": route["id"],
                "operation": outcome,
            }
            if operation_id is not None:
                operation_row["operation_id"] = operation_id
                version_outcome, version_id = _resolve_contract_version(
                    versions_by_operation.get(operation_id, set())
                )
                operation_row["contract_version"] = version_outcome
                if version_id is not None:
                    operation_row["contract_version_id"] = version_id
            route_operation.append(operation_row)

            gateway_service_id = route.get("service_id")
            gateway_service = services_by_scope.get(scope, {}).get(gateway_service_id or "")
            target_statements = {
                entry["target_id"]
                for entry in entries
                if (entry["kind"], entry["source_id"])
                in {
                    ("target_service_route", apisix_route_id),
                    ("target_service_service", gateway_service_id),
                }
            }
            for source in (_labels(route), _labels(gateway_service) if gateway_service else {}):
                if AIP_SERVICE_LABEL in source:
                    target_statements.add(source[AIP_SERVICE_LABEL])
            target_outcome, service_id = _resolve_target(target_statements, canonical_service_ids)
            target_row: dict[str, Any] = {
                "window_id": window_id,
                "route_id": route["id"],
                "target": target_outcome,
            }
            if service_id is not None:
                target_row["service_id"] = service_id
            target_service.append(target_row)

    return {
        "reconciliation_rule": {
            "rule_id": RECONCILIATION_RULE_ID,
            "rule_version": RECONCILIATION_RULE_VERSION,
        },
        "attributions": sorted(
            attributions, key=lambda r: (r["window_id"], r["consumer"], r["route"])
        ),
        "route_operation": sorted(route_operation, key=lambda r: (r["window_id"], r["route_id"])),
        "target_service": sorted(target_service, key=lambda r: (r["window_id"], r["route_id"])),
    }
