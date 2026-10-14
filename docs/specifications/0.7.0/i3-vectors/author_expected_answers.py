"""Author the I3 independent expected answers (v0.7.0 I3.1c; I3 spec §12, decision record D11).

Standalone and stdlib-only: it imports nothing from `app`, so the oracle cannot be derived from the
I3 implementation it qualifies (I3 §12: "Expected outputs SHALL not be generated from AIP
execution"). Every literal id comes from the frozen rules alone:

- consumer / route / Gateway Service / configured-access ids and the Gateway source evidence id:
  I1 `i1-vectors/ids.json` V01, V03, V04, V06, V13;
- measurement window / evidence / interaction / limitation / mapping ids: I2 `i2-vectors/ids.json`
  M01, M04-M06, M11, M12;
- contract and contract-version ids: I1 V08, V09;
- query-context digest, evidence ref and cursor: I3 decision record D8 and D9.

Selection is **authored by hand, per case**: each case names the Routes and the `(consumer, Route)`
pairs its answer contains, and the counts, limitation codes and outcome it expects. The helpers below
only compose JSON and derive identifiers, they never choose a Route, filter a row or qualify
anything, so no projection logic is reimplemented here. Usage, from the repository root:

    python docs/specifications/0.7.0/i3-vectors/author_expected_answers.py

writes `expected-answers.json` next to this file. Re-running must reproduce it byte for byte.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).resolve().parent / "expected-answers.json"

WILDCARD = "{{*}}"

# --- Frozen identity rules ----------------------------------------------------------------------


def ld(*parts: str) -> bytes:
    """app.common.encoding convention: 8-byte big-endian UTF-8 length + the UTF-8 bytes, per part."""
    out = bytearray()
    for part in parts:
        raw = part.encode("utf-8")
        out += len(raw).to_bytes(8, "big") + raw
    return bytes(out)


def sha(*parts: str) -> str:
    return hashlib.sha256(ld(*parts)).hexdigest()


def owned(prefix: str, *parts: str) -> str:
    return f"{prefix}:owned:{sha(*parts)}"


def consumer_id(gateway: str, username: str) -> str:
    return owned("gateway-consumer", gateway, username)  # I1 V01


def route_id(gateway: str, source_route_id: str) -> str:
    return owned("gateway-route", gateway, source_route_id)  # I1 V03


def gateway_service_id(gateway: str, source_service_id: str) -> str:
    return owned("gateway-service", gateway, source_service_id)  # I1 V04


RULE_KIND = "CONSUMER_RESTRICTION_ALLOW_LIST"


def configured_access_id(consumer: str, route: str) -> str:
    return owned("configured-access", consumer, route, RULE_KIND)  # I1 V06


def source_evidence_id(gateway: str, source_revision: str) -> str:
    return f"evidence:apisix:{sha(gateway, source_revision)}"  # I1 V13


def contract_id(source_instance_id: str) -> str:
    return owned("api-contract", source_instance_id)  # I1 V08


def contract_version_id(contract: str, version: str) -> str:
    return owned("api-contract-version", contract, version)  # I1 V09


def measurement_source_id(configured_source: str, gateway: str, environment: str) -> str:
    return "urn:aip:source:apisix-measurement:" + sha(
        configured_source, gateway, environment
    )  # M01


def interaction_id(consumer: str, route: str, environment: str, start: str, end: str) -> str:
    return owned("observed-consumer-interaction", consumer, route, environment, start, end)  # M06


def limitation_id(window: str, code: str, route: str, response_source: str) -> str:
    return owned("measurement-limitation", window, code, route, response_source)  # M11


def mapping_id(gateway: str, environment: str, kind: str, source: str, target: str) -> str:
    return owned("measurement-mapping", gateway, environment, kind, source, target)  # M12


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def query_digest(ctx: dict) -> str:
    """D9 `normalized_query_context_digest`."""
    return hashlib.sha256(
        canonical(
            {
                "consumer_id": ctx.get("consumer_id"),
                "environment": ctx["environment"],
                "gateway_instance_id": ctx["gateway_instance_id"],
                "target": {"id": ctx["target"]["id"], "kind": ctx["target"]["kind"]},
                "window_end": ctx["window_end"],
                "window_start": ctx["window_start"],
            }
        ).encode("utf-8")
    ).hexdigest()


def evidence_ref(snapshot_id: str, digest: str, kind: str, ids: list[str]) -> str:
    """D9 `api-evidence:<sha256(ld(snapshot_id, digest, kind, *sorted distinct ids))>`."""
    return "api-evidence:" + sha(snapshot_id, digest, kind, *sorted(set(ids)))


def encode_cursor(*, after: tuple[str, str], digest: str, snapshot_id: str) -> str:
    """D8: unpadded base64url of the canonical JSON."""
    payload = canonical(
        {
            "after": list(after),
            "query_digest": digest,
            "schema_version": "0.7",
            "snapshot_id": snapshot_id,
            "v": 1,
        }
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


# --- World ---------------------------------------------------------------------------------------

GW1 = "gw-prod-1"
GW2 = "gw-prod-2"
ENV = "prod"
WS = "2026-10-13T10:00:00Z"
WE = "2026-10-13T10:10:00Z"
START_SHA = "37016ed92411f67d01e64485f1b41e391896bee09d5dfeb2484c71f5380cbb2e"  # i2 M04
END_SHA = "f753e83a206e90bd8b1ac0b4466b503f290b25dea2f34a1b42911dbd4734f97b"  # i2 M04
GW2_START_SHA = hashlib.sha256(b"i3.1c gw-prod-2 start extract").hexdigest()
GW2_END_SHA = hashlib.sha256(b"i3.1c gw-prod-2 end extract").hexdigest()
SOURCE_REVISION = {GW1: "apisix:3.19.0+etcd:4242", GW2: "apisix:3.19.0+etcd:77"}
APISIX_VERSION = "3.19.0"
CANARY = "CANARY-aip-i3-credential-5f3c9a1e"

RECONCILIATION_RULE = {"rule_id": "apisix-api-usage-reconciliation", "rule_version": "1"}
QUALIFICATION_RULE = {
    "rule_id": "apisix-configured-vs-observed-qualification",
    "rule_version": "1",
}

SNAPSHOTS = {
    label: {
        "snapshot_id": f"aip:snapshot:v1:{hashlib.sha256(f'i3.1c snapshot {label}'.encode()).hexdigest()}",
        "model_revision": f"sha256:{hashlib.sha256(f'i3.1c snapshot {label}'.encode()).hexdigest()}",
    }
    for label in ("A", "B")
}

OP_ORDERS = "operation:orders-api:listOrders"
OP_GET_ORDER = "operation:orders-api:getOrder"
OP_INVOICES = "operation:billing-api:listInvoices"
SVC_ORDERS = "service:orders"
SVC_BILLING = "service:billing"
CONTRACTS = {
    "orders-api": contract_id("urn:aip:source:openapi:orders-api"),
    "billing-api": contract_id("urn:aip:source:openapi:billing-api"),
}
VERSIONS = {name: contract_version_id(cid, "1.0.0") for name, cid in CONTRACTS.items()}
OPERATION_VERSIONS = {
    OP_ORDERS: ("orders-api", VERSIONS["orders-api"]),
    OP_INVOICES: ("billing-api", VERSIONS["billing-api"]),
}


def _route(
    label: str,
    *,
    gateway: str = GW1,
    op: str | None = None,
    svc: str | None = None,
    svc_outcome: str | None = None,
    gw_service: str | None = None,
    op_entries: tuple[str, ...] = (),
    svc_entries: tuple[tuple[str, str], ...] = (),
    labels: tuple[tuple[str, str], ...] = (),
    limits: tuple[str, ...] = (),
    carriers: tuple[tuple[str, str], ...] = (),
) -> dict:
    return {
        "label": label,
        "gateway": gateway,
        "source_route_id": label,
        "id": route_id(gateway, label),
        "gateway_service": gw_service,
        "route_operation": ("RESOLVED", op) if op else ("UNRESOLVED", None),
        "target_service": (svc_outcome or ("RESOLVED" if svc else "UNRESOLVED"), svc),
        "operation_mapping_entries": list(op_entries),
        "service_mapping_entries": [list(entry) for entry in svc_entries],
        "service_labels": [list(entry) for entry in labels],
        "route_limitations": list(limits),
        "limitation_carriers": [list(entry) for entry in carriers],
    }


def _pair(
    consumer: str,
    route: str,
    *,
    configured: bool,
    usage: str,
    upstream: int = 0,
    rejected: int = 0,
    interaction: bool = False,
    series_status: str = "DELTA",
) -> dict:
    return {
        "consumer": consumer,
        "route": route,
        "configured": configured,
        "usage_status": usage,
        "upstream_request_count": upstream,
        "rejected_attempt_count": rejected,
        "interaction": interaction,
        "series_status": series_status,
    }


OBSERVED = "OBSERVED_USAGE"
ZERO = "MEASURED_ZERO"
UNESTABLISHED = "USAGE_UNESTABLISHED"


def base_world() -> dict:
    routes = [
        _route(
            "orders-route",
            op=OP_ORDERS,
            svc=SVC_ORDERS,
            op_entries=(OP_ORDERS,),
            labels=(("ROUTE", SVC_ORDERS),),
        ),
        _route(
            "orders-v2-route",
            op=OP_ORDERS,
            svc=SVC_ORDERS,
            gw_service="svc-orders-v2",
            op_entries=(OP_ORDERS,),
            labels=(("GATEWAY_SERVICE", SVC_ORDERS),),
        ),
        _route(
            "billing-route",
            op=OP_INVOICES,
            svc=SVC_BILLING,
            op_entries=(OP_INVOICES,),
            svc_entries=(("ROUTE", SVC_BILLING),),
        ),
        _route(
            "legacy-route",
            limits=("GWM_COUNTER_DECREASED",),
            carriers=(("GWM_COUNTER_DECREASED", "upstream"),),
        ),
        _route("nocov-route", limits=("GWM_ROUTE_COVERAGE_ABSENT",)),
        _route("bare-route"),
        _route(
            "conflict-route",
            svc_outcome="CONFLICT",
            gw_service="svc-conflict",
            svc_entries=(("GATEWAY_SERVICE", SVC_BILLING),),
            labels=(("ROUTE", SVC_ORDERS),),
        ),
        _route(
            "other-route",
            gateway=GW2,
            op=OP_ORDERS,
            svc=SVC_ORDERS,
            op_entries=(OP_ORDERS,),
            labels=(("ROUTE", SVC_ORDERS),),
        ),
    ]
    consumers = [
        {"label": "alpha", "gateway": GW1, "username": "spike-alpha"},
        {"label": "beta", "gateway": GW1, "username": "spike-beta"},
        {"label": "gamma", "gateway": GW1, "username": "spike-gamma"},
        {"label": "alpha2", "gateway": GW2, "username": "spike-alpha"},
    ]
    for consumer in consumers:
        consumer["id"] = consumer_id(consumer["gateway"], consumer["username"])
    pairs = [
        _pair(
            "alpha", "orders-route", configured=True, usage=OBSERVED, upstream=3, interaction=True
        ),
        _pair("alpha", "orders-v2-route", configured=True, usage=ZERO),
        _pair(
            "alpha",
            "legacy-route",
            configured=True,
            usage=UNESTABLISHED,
            interaction=True,
            series_status="DECREASED",
        ),
        _pair("alpha", "bare-route", configured=True, usage=ZERO),
        _pair(
            "beta", "orders-route", configured=False, usage=OBSERVED, upstream=2, interaction=True
        ),
        _pair(
            "beta",
            "billing-route",
            configured=False,
            usage=UNESTABLISHED,
            rejected=2,
            interaction=True,
        ),
        _pair("beta", "conflict-route", configured=True, usage=ZERO),
        _pair("gamma", "billing-route", configured=True, usage=ZERO),
        _pair(
            "alpha2", "other-route", configured=True, usage=OBSERVED, upstream=7, interaction=True
        ),
    ]
    windows = {
        GW1: {
            "configured_source": "apisix-metrics-prod",
            "window_start": WS,
            "window_end": WE,
            "start_sha256": START_SHA,
            "end_sha256": END_SHA,
            "start_settled": True,
            "end_settled": True,
            "no_restart": True,
            "start_stable_seconds": 24,
            "end_stable_seconds": 22,
            "window_reasons": [],
        },
        GW2: {
            "configured_source": "apisix-metrics-prod-2",
            "window_start": WS,
            "window_end": WE,
            "start_sha256": GW2_START_SHA,
            "end_sha256": GW2_END_SHA,
            "start_settled": True,
            "end_settled": True,
            "no_restart": True,
            "start_stable_seconds": 25,
            "end_stable_seconds": 21,
            "window_reasons": [],
        },
    }
    return {
        "snapshot": "A",
        "environment": ENV,
        "apisix_version": APISIX_VERSION,
        "rules": {"reconciliation": RECONCILIATION_RULE, "qualification": QUALIFICATION_RULE},
        "operations": {
            OP_ORDERS: {"contract": "orders-api", "contract_version_id": VERSIONS["orders-api"]},
            OP_GET_ORDER: {"contract": "orders-api", "contract_version_id": VERSIONS["orders-api"]},
            OP_INVOICES: {
                "contract": "billing-api",
                "contract_version_id": VERSIONS["billing-api"],
            },
        },
        "services": [SVC_ORDERS, SVC_BILLING],
        "gateways": {
            GW1: {"source_revision": SOURCE_REVISION[GW1]},
            GW2: {"source_revision": SOURCE_REVISION[GW2]},
        },
        "consumers": consumers,
        "routes": routes,
        "pairs": pairs,
        "windows": windows,
        "internal_only": {
            "credential_canary": CANARY,
            "note": "A credential canary placed in the plugin configuration of a Consumer and a "
            "Route. It must be absent from every answer and evidence payload (D7, case C01).",
            "consumer_plugin_config": {"spike-alpha": {"key-auth": {"key": CANARY}}},
            "route_plugin_config": {"orders-route": {"key-auth": {"header": CANARY}}},
        },
    }


def window_ids(world: dict, gateway: str) -> dict:
    window = world["windows"][gateway]
    parts = (
        gateway,
        world["environment"],
        window["window_start"],
        window["window_end"],
        window["start_sha256"],
        window["end_sha256"],
    )
    return {
        "id": "measurement-window:owned:" + sha(*parts),  # M04
        "evidence_id": "evidence:apisix-measurement:" + sha(*parts),  # M05
        "source_instance_id": measurement_source_id(
            window["configured_source"], gateway, world["environment"]
        ),
    }


def finalize(world: dict) -> dict:
    """Add the derived window identifiers and index the world."""
    world = copy.deepcopy(world)
    for gateway, window in world["windows"].items():
        window.update(window_ids(world, gateway))
    world["_consumers"] = {c["label"]: c for c in world["consumers"]}
    world["_routes"] = {r["label"]: r for r in world["routes"]}
    world["_pairs"] = {(p["consumer"], p["route"]): p for p in world["pairs"]}
    return world


# --- The serialized world: the frozen I2 -> I3 handoff state (i2-i3-handoff.md §1) ----------------
#
# The author works with the hand-authored abstraction above (routes, pairs, windows). What a world
# serializes is the snapshot state I3 may project: the section and row shapes of the repository's
# `gateway_configuration_v1`, `api_usage_v1`, `api_contracts_v1`, `operations` and `services`, so
# the I3.2 harness loads it without translating anything. These functions compose rows from the
# authored values; they select, filter and qualify nothing (every row of a section is listed in
# the abstraction, and the abstraction states the outcome, status and counts of every row).


def association_id(kind: str, version: str, target: str) -> str:
    return owned("api-contract-association", kind, version, target)


def series_id(window: str, series_key: str) -> str:
    return owned("measurement-series", window, series_key)  # M10


def qualification_id(consumer: str, route: str, environment: str, start: str, end: str) -> str:
    return owned("usage-qualification", consumer, route, environment, start, end)  # M09


def sort_by(keys: tuple[str, ...], rows: Any) -> list[dict]:
    return sorted(rows, key=lambda row: tuple(row[key] for key in keys))


def compact_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def series_labels(consumer: str, route: str, code: str, response_source: str) -> dict:
    return {
        "code": code,
        "consumer": consumer,
        "llm_model": "",
        "matched_host": "",
        "matched_uri": "/" + route,
        "request_llm_model": "",
        "request_type": "traditional_http",
        "response_source": response_source,
        "route": route,
        "service": "",
    }


def series_key(labels: dict) -> str:
    return ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))


def series_row(
    window: dict,
    gateway: str,
    environment: str,
    consumer: str,
    route: str,
    code: str,
    response_source: str,
    status: str,
    delta: int | None,
) -> dict:
    labels = series_labels(consumer, route, code, response_source)
    row: dict[str, Any] = {
        "id": series_id(window["id"], series_key(labels)),
        "window_id": window["id"],
        "gateway_instance_id": gateway,
        "environment": environment,
        "window_start": window["window_start"],
        "window_end": window["window_end"],
        "route": route,
        "consumer": consumer,
        "code": code,
        "response_source": response_source,
        "status": status,
        "labels_json": compact_json(labels),
        "evidence_ids": [window["evidence_id"]],
    }
    if delta is not None:
        row["request_count_delta"] = delta
    return row


def operation_row(operation: str, world: dict) -> dict:
    service = SVC_BILLING if operation == OP_INVOICES else SVC_ORDERS
    name = operation.rsplit(":", 1)[1]
    path = {"listOrders": "/orders", "getOrder": "/orders/{id}", "listInvoices": "/invoices"}[name]
    return {
        "id": operation,
        "name": name,
        "service_id": service,
        "operation_id": name,
        "method": "GET",
        "path": path,
    }


def gateway_configuration_state(world: dict) -> dict:
    environment = world["environment"]
    consumers = [
        {
            "id": c["id"],
            "gateway_instance_id": c["gateway"],
            "environment": environment,
            "username": c["username"],
        }
        for c in world["consumers"]
    ]
    routes = []
    services: dict[str, dict] = {}
    for route in world["routes"]:
        row: dict[str, Any] = {
            "id": route["id"],
            "gateway_instance_id": route["gateway"],
            "environment": environment,
            "route_id": route["source_route_id"],
            "uri": "/" + route["source_route_id"],
        }
        route_labels: dict[str, str] = {}
        service_labels: dict[str, str] = {}
        for carrier, sid in route["service_labels"]:
            (route_labels if carrier == "ROUTE" else service_labels)["aip/service"] = sid
        if route["gateway_service"]:
            row["service_id"] = route["gateway_service"]
            services[route["id"]] = {
                "id": gateway_service_id(route["gateway"], route["gateway_service"]),
                "gateway_instance_id": route["gateway"],
                "environment": environment,
                "service_id": route["gateway_service"],
                "labels_json": compact_json(service_labels),
            }
        row["labels_json"] = compact_json(route_labels)
        routes.append(row)
    configured = []
    for pair in world["pairs"]:
        if not pair["configured"]:
            continue
        who = world["_consumers"][pair["consumer"]]
        route = world["_routes"][pair["route"]]
        revision = world["gateways"][who["gateway"]]["source_revision"]
        configured.append(
            {
                "id": configured_access_id(who["id"], route["id"]),
                "consumer_id": who["id"],
                "route_id": route["id"],
                "rule_kind": RULE_KIND,
                "polarity": "ALLOW",
                "scope": "ROUTE",
                "evidence_ids": [source_evidence_id(who["gateway"], revision)],
                "source_revision": revision,
            }
        )
    evidence = [
        {
            "id": source_evidence_id(gateway, data["source_revision"]),
            "gateway_instance_id": gateway,
            "environment": environment,
            "apisix_version": world["apisix_version"],
            "source_revision": data["source_revision"],
            "evidence_type": "DECLARED",
        }
        for gateway, data in world["gateways"].items()
    ]
    return {
        "consumers": sort_by(("id",), consumers),
        "routes": sort_by(("id",), routes),
        "services": sort_by(("id",), services.values()),
        "configured_access": sort_by(("id",), configured),
        "limitations": [],
        "source_evidence": sort_by(("id",), evidence),
    }


def api_contracts_state(world: dict) -> dict:
    contracts = [
        {
            "id": cid,
            "openapi_source_instance_id": f"urn:aip:source:openapi:{name}",
            "limitations": [],
        }
        for name, cid in CONTRACTS.items()
    ]
    versions = [
        {"id": VERSIONS[name], "contract_id": cid, "info_version": "1.0.0"}
        for name, cid in CONTRACTS.items()
    ]
    associations = []
    for operation, data in world["operations"].items():
        kind = "OPERATION_IN_CONTRACT_VERSION"
        associations.append(
            {
                "id": association_id(kind, data["contract_version_id"], operation),
                "kind": kind,
                "contract_version_id": data["contract_version_id"],
                "target_id": operation,
                "evidence_ids": [
                    "evidence:openapi:" + sha("i3.1c openapi evidence", CONTRACTS[data["contract"]])
                ],
            }
        )
    return {
        "contracts": sort_by(("id",), contracts),
        "versions": sort_by(("id",), versions),
        "associations": sort_by(("id",), associations),
    }


def api_usage_state(world: dict) -> dict:
    environment = world["environment"]
    windows, evidence, limitations, mappings = [], [], [], []
    series, attributions = [], []
    route_operation, target_service, coverage = [], [], []
    interactions, rows = [], []
    for gateway, window in sorted(world["windows"].items()):
        wid = window["id"]
        gateway_routes = [r for r in world["routes"] if r["gateway"] == gateway]
        route_coverage = {
            r["source_route_id"]: True
            for r in gateway_routes
            if "GWM_ROUTE_COVERAGE_ABSENT" not in r["route_limitations"]
        }
        windows.append(
            {
                "id": wid,
                "source_instance_id": window["source_instance_id"],
                "gateway_instance_id": gateway,
                "environment": environment,
                "apisix_version": world["apisix_version"],
                "window_start": window["window_start"],
                "window_end": window["window_end"],
                "start_settled": window["start_settled"],
                "end_settled": window["end_settled"],
                "no_restart": window["no_restart"],
                "start_stable_seconds": window["start_stable_seconds"],
                "end_stable_seconds": window["end_stable_seconds"],
                "disabled_labels": [],
                "route_coverage_json": compact_json(route_coverage),
                "window_reasons": sorted(window["window_reasons"]),
                "evidence_ids": [window["evidence_id"]],
            }
        )
        evidence.append(
            {
                "id": window["evidence_id"],
                "source_instance_id": window["source_instance_id"],
                "gateway_instance_id": gateway,
                "environment": environment,
                "apisix_version": world["apisix_version"],
                "window_start": window["window_start"],
                "window_end": window["window_end"],
                "start_sha256": window["start_sha256"],
                "end_sha256": window["end_sha256"],
                "evidence_type": "OBSERVED",
            }
        )
        valid = not window["window_reasons"]
        for route in gateway_routes:
            for code, response_source in route["limitation_carriers"]:
                limitations.append(
                    {
                        "id": limitation_id(wid, code, route["source_route_id"], response_source),
                        "window_id": wid,
                        "code": code,
                        "route": route["source_route_id"],
                        "response_source": response_source,
                    }
                )
            for kind, source, target in route_mapping_entries(route):
                mappings.append(
                    {
                        "id": mapping_id(gateway, environment, kind, source, target),
                        "gateway_instance_id": gateway,
                        "environment": environment,
                        "kind": kind,
                        "source_id": source,
                        "target_id": target,
                    }
                )
            outcome, operation = route["route_operation"]
            op_row: dict[str, Any] = {
                "window_id": wid,
                "route_id": route["id"],
                "operation": outcome,
            }
            if operation:
                op_row["operation_id"] = operation
                op_row["contract_version"] = "RESOLVED"
                op_row["contract_version_id"] = world["operations"][operation][
                    "contract_version_id"
                ]
            route_operation.append(op_row)
            target_outcome, service = route["target_service"]
            target_row: dict[str, Any] = {
                "window_id": wid,
                "route_id": route["id"],
                "target": target_outcome,
            }
            if target_outcome == "RESOLVED":
                target_row["service_id"] = service
            target_service.append(target_row)
            limits = sorted(route["route_limitations"])
            coverage.append(
                {
                    "window_id": wid,
                    "route_id": route["id"],
                    "coverage": "UNKNOWN_COVERAGE" if limits else "SUFFICIENT_FOR_ZERO",
                    "limitations": limits,
                }
            )
        for pair in world["pairs"]:
            who = world["_consumers"][pair["consumer"]]
            route = world["_routes"][pair["route"]]
            if who["gateway"] != gateway:
                continue
            limits = sorted(route["route_limitations"])
            args = (
                who["id"],
                route["id"],
                environment,
                window["window_start"],
                window["window_end"],
            )
            base = {
                "window_id": wid,
                "consumer_id": who["id"],
                "route_id": route["id"],
                "consumer": who["username"],
                "route": route["source_route_id"],
            }
            totals: dict[str, Any] = {}
            if valid:
                totals = {
                    "upstream_request_count": pair["upstream_request_count"],
                    "rejected_attempt_count": pair["rejected_attempt_count"],
                }
            row: dict[str, Any] = {
                "id": qualification_id(*args),
                **base,
                "configured_status": "CONFIGURED_ACCESS_ESTABLISHED"
                if pair["configured"]
                else "NO_MATCHING_CONFIGURED_ACCESS_FACT",
                "usage_status": pair["usage_status"],
                "coverage": "UNKNOWN_COVERAGE" if limits else "SUFFICIENT_FOR_ZERO",
                **totals,
                "limitations": limits,
                "evidence_ids": [window["evidence_id"]],
            }
            if pair["interaction"]:
                for response_source, code, count in (
                    ("upstream", "200", pair["upstream_request_count"]),
                    ("apisix", "403", pair["rejected_attempt_count"]),
                ):
                    decreased = (
                        pair["series_status"] == "DECREASED" and response_source == "upstream"
                    )
                    if not count and not decreased:
                        continue
                    series.append(
                        series_row(
                            window,
                            gateway,
                            environment,
                            who["username"],
                            route["source_route_id"],
                            code,
                            response_source,
                            "DECREASED" if decreased else "DELTA",
                            None if decreased else count,
                        )
                    )
                attributions.append(
                    {
                        "window_id": wid,
                        "consumer": who["username"],
                        "route": route["source_route_id"],
                        "consumer_outcome": "RESOLVED",
                        "route_outcome": "RESOLVED",
                        "consumer_id": who["id"],
                        "route_id": route["id"],
                    }
                )
                iid = interaction_id(*args)
                row["interaction_id"] = iid
                interactions.append(
                    {"id": iid, **base, **totals, "evidence_ids": [window["evidence_id"]]}
                )
            rows.append(row)
    for extra in world.get("unattributed_series", []):
        window = world["windows"][extra["gateway"]]
        route = world["_routes"][extra["route"]]
        series.append(
            series_row(
                window,
                extra["gateway"],
                environment,
                extra["consumer"],
                route["source_route_id"],
                "200",
                "upstream",
                "DELTA",
                extra["count"],
            )
        )
        attributions.append(
            {
                "window_id": window["id"],
                "consumer": extra["consumer"],
                "route": route["source_route_id"],
                "consumer_outcome": "UNRESOLVED",
                "route_outcome": "RESOLVED",
                "route_id": route["id"],
            }
        )
    return {
        "windows": sort_by(("id",), windows),
        "evidence": sort_by(("id",), evidence),
        "series": sort_by(("id",), series),
        "limitations": sort_by(("id",), limitations),
        "mapping_entries": sort_by(("id",), mappings),
        "reconciliation_rule": RECONCILIATION_RULE,
        "attributions": sort_by(("window_id", "consumer", "route"), attributions),
        "route_operation": sort_by(("window_id", "route_id"), route_operation),
        "target_service": sort_by(("window_id", "route_id"), target_service),
        "qualification_rule": QUALIFICATION_RULE,
        "coverage": sort_by(("window_id", "route_id"), coverage),
        "interactions": sort_by(("window_id", "consumer", "route"), interactions),
        "qualification_rows": sort_by(("window_id", "consumer", "route"), rows),
    }


def route_mapping_entries(route: dict) -> list[tuple[str, str, str]]:
    entries = [
        ("route_operation", route["source_route_id"], op)
        for op in route["operation_mapping_entries"]
    ]
    for carrier, service in route["service_mapping_entries"]:
        if carrier == "ROUTE":
            entries.append(("target_service_route", route["source_route_id"], service))
        else:
            entries.append(("target_service_service", route["gateway_service"], service))
    return entries


def handoff_state(world: dict) -> dict:
    state: dict[str, Any] = {
        "gateway_configuration_v1": gateway_configuration_state(world),
        "operations": sorted(
            (operation_row(op, world) for op in world["operations"]), key=lambda r: r["id"]
        ),
        "services": [
            {"id": sid, "name": sid.split(":", 1)[1], "version": "1.0.0"}
            for sid in sorted(world["services"])
        ],
        "api_contracts_v1": api_contracts_state(world),
    }
    if world["windows"]:
        state["api_usage_v1"] = api_usage_state(world)
    return state


def public_world(world: dict) -> dict:
    """What a world serializes: the handoff snapshot state plus the harness-only inputs."""
    return {
        "snapshot_state": handoff_state(world),
        "internal_only": world["internal_only"],
    }


# --- Worlds (variants of the base world) ----------------------------------------------------------


def world_base() -> dict:
    return finalize(base_world())


def world_unattributed() -> dict:
    """A10: unattributed upstream traffic on orders-route; only the configured pair has a row."""
    world = base_world()
    for route in world["routes"]:
        if route["label"] == "orders-route":
            route["route_limitations"] = ["GWM_UNATTRIBUTED_UPSTREAM"]
        if route["label"] == "legacy-route":  # its decreased series is not part of this world
            route["route_limitations"] = []
            route["limitation_carriers"] = []
    world["pairs"] = [
        _pair("alpha", "orders-route", configured=True, usage=UNESTABLISHED),
    ]
    world["unattributed_series"] = [
        {"gateway": GW1, "route": "orders-route", "consumer": "no-such-consumer", "count": 1}
    ]
    return finalize(world)


def _invalid_window_world(reasons: list[str], **window_changes: Any) -> dict:
    world = base_world()
    world["windows"][GW1]["window_reasons"] = reasons
    world["windows"][GW1].update(window_changes)
    for route in world["routes"]:
        if route["gateway"] == GW1:
            route["route_limitations"] = list(reasons)
    world["pairs"] = [
        _pair("alpha", "orders-route", configured=True, usage=UNESTABLISHED),
    ]
    return finalize(world)


def world_not_settled() -> dict:
    """A11: the end boundary is not settled, so the window carries GWM_WINDOW_NOT_SETTLED."""
    return _invalid_window_world(["GWM_WINDOW_NOT_SETTLED"], end_settled=False)


def world_reversed() -> dict:
    """A20: window_start > window_end is an accepted but invalid I2 window."""
    return _invalid_window_world(
        ["GWM_WINDOW_ORDER_INVALID"], window_start="2026-10-13T10:10:00Z", window_end=WS
    )


def world_no_measurement() -> dict:
    """A13: gw-prod-1 has an accepted configuration source but no accepted measurement window."""
    world = base_world()
    del world["windows"][GW1]
    world["pairs"] = [p for p in world["pairs"] if p["consumer"] == "alpha2"]
    return finalize(world)


def world_new_snapshot() -> dict:
    """A16/A17: an unrelated import made snapshot B current; the data is unchanged."""
    world = base_world()
    world["snapshot"] = "B"
    return finalize(world)


WORLDS = {
    "base": world_base,
    "unattributed": world_unattributed,
    "not-settled": world_not_settled,
    "reversed": world_reversed,
    "no-measurement": world_no_measurement,
    "new-snapshot": world_new_snapshot,
}

# --- Composition helpers (identifiers and JSON only: no selection, filtering or qualification) ----


def snapshot_ref(label: str) -> dict:
    return dict(SNAPSHOTS[label])


def producer() -> dict:
    return {
        "name": "architecture-intelligence-platform",
        "version": WILDCARD,
        "build_revision": WILDCARD,
    }


def limitation(code: str) -> dict:
    return {"code": code, "message": WILDCARD}


def envelope(mode, outcome, snapshot, data, codes) -> dict:
    return {
        "schema_version": "0.7",
        "producer": producer(),
        "tool": "get_api_consumer_usage",
        "mode": mode,
        "outcome": outcome,
        "snapshot": snapshot,
        "data": data,
        "limitations": [limitation(code) for code in sorted(codes)],
    }


def refusal(mode: str, code: str, snapshot_label: str | None) -> dict:
    snapshot = snapshot_ref(snapshot_label) if snapshot_label else None
    return envelope(mode, "NOT_ANSWERED", snapshot, None, [code])


def request_context(request: dict) -> dict:
    context = {
        "target": dict(request["target"]),
        "gateway_instance_id": request["gateway_instance_id"],
        "environment": request["environment"],
        "window_start": request["window_start"],
        "window_end": request["window_end"],
    }
    if request.get("consumer_id"):
        context["consumer_id"] = request["consumer_id"]
    return context


def query_request(target_kind: str, target_id: str, **extra: Any) -> dict:
    request = {
        "mode": "query",
        "target": {"kind": target_kind, "id": target_id},
        "gateway_instance_id": GW1,
        "environment": ENV,
        "window_start": WS,
        "window_end": WE,
    }
    request.update(extra)
    return request


def route_target(world: dict, label: str, **extra: Any) -> dict:
    return query_request("GATEWAY_ROUTE", world["_routes"][label]["id"], **extra)


def with_consumer(world: dict, label: str) -> dict:
    return {"consumer_id": world["_consumers"][label]["id"]}


class Refs:
    """The D9 refs of one world and one request context."""

    def __init__(self, world: dict, request: dict, snapshot_label: str | None = None):
        self.world = world
        self.snapshot_id = SNAPSHOTS[snapshot_label or world["snapshot"]]["snapshot_id"]
        self.context = request_context(request)
        self.digest = query_digest(self.context)
        self.gateway = request["gateway_instance_id"]

    def _ref(self, kind: str, ids: list[str]) -> str:
        return evidence_ref(self.snapshot_id, self.digest, kind, ids)

    def window_ids(self) -> list[str]:
        window = self.world["windows"][self.gateway]
        return [window["id"], window["evidence_id"]]

    def window(self) -> str:
        return self._ref("MEASUREMENT_WINDOW", self.window_ids())

    def configured(self, consumer: str, route: str) -> str:
        cid = self.world["_consumers"][consumer]["id"]
        rid = self.world["_routes"][route]["id"]
        revision = self.world["gateways"][self.gateway]["source_revision"]
        return self._ref(
            "CONFIGURED_ACCESS",
            [configured_access_id(cid, rid), source_evidence_id(self.gateway, revision)],
        )

    def _route_mappings(self, route: dict, kinds: dict) -> list[str]:
        return [
            mapping_id(self.gateway, self.world["environment"], kind, source, target)
            for kind, source, target in kinds
        ]

    def route_operation(self, route_label: str) -> str:
        route = self.world["_routes"][route_label]
        entries = [
            ("route_operation", route["source_route_id"], op)
            for op in route["operation_mapping_entries"]
        ]
        return self._ref(
            "ROUTE_OPERATION_RECONCILIATION", [route["id"], *self._route_mappings(route, entries)]
        )

    def target_service(self, route_label: str) -> str:
        route = self.world["_routes"][route_label]
        entries = []
        for carrier, service in route["service_mapping_entries"]:
            if carrier == "ROUTE":
                entries.append(("target_service_route", route["source_route_id"], service))
            else:
                entries.append(("target_service_service", route["gateway_service"], service))
        ids = [route["id"], *self._route_mappings(route, entries)]
        if route["gateway_service"]:
            ids.append(gateway_service_id(self.gateway, route["gateway_service"]))
        return self._ref("TARGET_SERVICE_RECONCILIATION", ids)

    def limitations(self, route_label: str) -> str:
        route = self.world["_routes"][route_label]
        window = self.world["windows"][self.gateway]
        ids = [route["id"], window["id"]]
        for code, response_source in route["limitation_carriers"]:
            ids.append(limitation_id(window["id"], code, route["source_route_id"], response_source))
        return self._ref("QUALIFICATION_LIMITATIONS", ids)


def route_limits(world: dict, route_label: str) -> list[str]:
    return sorted(world["_routes"][route_label]["route_limitations"])


def window_block(world: dict, refs: Refs, request: dict) -> dict:
    window = world["windows"][request["gateway_instance_id"]]
    reasons = sorted(window["window_reasons"])
    return {
        "window_start": request["window_start"],
        "window_end": request["window_end"],
        "source_instance_id": window["source_instance_id"],
        "valid": not reasons,
        "reasons": reasons,
        "evidence_refs": [refs.window()],
    }


def selected_route(world: dict, refs: Refs, route_label: str) -> dict:
    route = world["_routes"][route_label]
    limits = route_limits(world, route_label)
    return {
        "route_id": route["id"],
        "source_route_id": route["source_route_id"],
        "coverage": "UNKNOWN_COVERAGE" if limits else "SUFFICIENT_FOR_ZERO",
        "limitations": limits,
        "evidence_refs": [refs.limitations(route_label)] if limits else [],
    }


def api_block(world: dict, route_label: str) -> dict:
    outcome, op = world["_routes"][route_label]["route_operation"]
    block: dict[str, Any] = {"reconciliation": outcome}
    if op:
        block["operation_id"] = op
        block["contract_version_reconciliation"] = "RESOLVED"
        block["contract_version_id"] = world["operations"][op]["contract_version_id"]
        block["contract_id"] = CONTRACTS[world["operations"][op]["contract"]]
    return block


def service_block(world: dict, route_label: str) -> dict:
    outcome, service = world["_routes"][route_label]["target_service"]
    block: dict[str, Any] = {"reconciliation": outcome}
    if service and outcome == "RESOLVED":
        block["service_id"] = service
    return block


def row_block(world: dict, refs: Refs, request: dict, consumer: str, route_label: str) -> dict:
    pair = world["_pairs"][(consumer, route_label)]
    route = world["_routes"][route_label]
    who = world["_consumers"][consumer]
    window = world["windows"][request["gateway_instance_id"]]
    valid = not window["window_reasons"]
    limits = route_limits(world, route_label)
    usage: dict[str, Any] = {
        "status": pair["usage_status"],
        "coverage": "UNKNOWN_COVERAGE" if limits else "SUFFICIENT_FOR_ZERO",
    }
    if valid:
        usage["upstream_request_count"] = pair["upstream_request_count"]
        usage["rejected_attempt_count"] = pair["rejected_attempt_count"]
    if pair["interaction"]:
        usage["interaction_id"] = interaction_id(
            who["id"],
            route["id"],
            world["environment"],
            request["window_start"],
            request["window_end"],
        )
    evidence = [
        refs.window(),
        refs.route_operation(route_label),
        refs.target_service(route_label),
    ]
    if pair["configured"]:
        evidence.append(refs.configured(consumer, route_label))
    if limits:
        evidence.append(refs.limitations(route_label))
    return {
        "consumer": {"id": who["id"], "source_name": who["username"]},
        "gateway_route": {
            "id": route["id"],
            "gateway_instance_id": route["gateway"],
            "source_route_id": route["source_route_id"],
        },
        "api": api_block(world, route_label),
        "application_service": service_block(world, route_label),
        "configured_access": {
            "status": "CONFIGURED_ACCESS_ESTABLISHED"
            if pair["configured"]
            else "NO_MATCHING_CONFIGURED_ACCESS_FACT"
        },
        "usage": usage,
        "evidence_refs": sorted(evidence),
        "limitations": limits,
    }


def sort_rows(rows: list[dict]) -> list[dict]:
    """The contract order: bytewise by (consumer.id, gateway_route.id)."""
    return sorted(rows, key=lambda r: (r["consumer"]["id"], r["gateway_route"]["id"]))


def counts(to_target: int, elsewhere: int, unresolved: int, ambiguous: int, conflict: int) -> dict:
    return {
        "resolved_to_target": to_target,
        "resolved_elsewhere": elsewhere,
        "unresolved": unresolved,
        "ambiguous": ambiguous,
        "conflict": conflict,
    }


def query_answer(
    world: dict,
    request: dict,
    *,
    routes: list[str],
    pairs: list[tuple[str, str]],
    outcome: str,
    codes: list[str],
    summary: dict | None = None,
    limit: int | None = None,
    after: tuple[str, str] | None = None,
) -> dict:
    """An evaluated query answer. `routes`, `pairs`, `outcome`, `codes`, `summary` and the paging
    are stated by the case author, not derived."""
    refs = Refs(world, request)
    gateway = request["gateway_instance_id"]
    window = world["windows"][gateway]
    rows = sort_rows([row_block(world, refs, request, c, r) for c, r in pairs])
    page: dict[str, Any] = {"limit": limit or request.get("limit", 100), "returned": len(rows)}
    if after:
        page["next_cursor"] = encode_cursor(
            after=(world["_consumers"][after[0]]["id"], world["_routes"][after[1]]["id"]),
            digest=refs.digest,
            snapshot_id=refs.snapshot_id,
        )
    data: dict[str, Any] = {
        "request_context": request_context(request),
        "window": window_block(world, refs, request),
        "rules": world["rules"],
    }
    if summary:
        data["association_summary"] = summary
    data.update(
        {
            "selected_routes": sorted(
                (selected_route(world, refs, label) for label in routes),
                key=lambda r: r["route_id"],
            ),
            "configuration_sources": [
                {
                    "gateway_instance_id": gateway,
                    "environment": world["environment"],
                    "source_revision": world["gateways"][gateway]["source_revision"],
                }
            ],
            "measurement_sources": [
                {
                    "source_instance_id": window["source_instance_id"],
                    "window_start": request["window_start"],
                    "window_end": request["window_end"],
                    "apisix_version": world["apisix_version"],
                }
            ],
            "rows": rows,
            "page": page,
        }
    )
    return envelope("query", outcome, snapshot_ref(world["snapshot"]), data, codes)


# --- Evidence payloads (hand-written from the world; D9 allow-lists) -------------------------------


def evidence_route(world: dict, label: str) -> dict:
    route = world["_routes"][label]
    return {"id": route["id"], "source_route_id": route["source_route_id"]}


def payload_configured(world: dict, request: dict, consumer: str, label: str) -> dict:
    who = world["_consumers"][consumer]
    gateway = request["gateway_instance_id"]
    return {
        "kind": "CONFIGURED_ACCESS",
        "gateway_instance_id": gateway,
        "environment": world["environment"],
        "source_revision": world["gateways"][gateway]["source_revision"],
        "consumer": {"id": who["id"], "source_name": who["username"]},
        "gateway_route": evidence_route(world, label),
        "rule_kind": RULE_KIND,
        "polarity": "ALLOW",
        "scope": "ROUTE",
    }


def payload_window(world: dict, request: dict) -> dict:
    gateway = request["gateway_instance_id"]
    window = world["windows"][gateway]
    reasons = sorted(window["window_reasons"])
    return {
        "kind": "MEASUREMENT_WINDOW",
        "source_instance_id": window["source_instance_id"],
        "gateway_instance_id": gateway,
        "environment": world["environment"],
        "window_start": window["window_start"],
        "window_end": window["window_end"],
        "apisix_version": world["apisix_version"],
        "start_settled": window["start_settled"],
        "end_settled": window["end_settled"],
        "no_restart": window["no_restart"],
        "start_stable_seconds": window["start_stable_seconds"],
        "end_stable_seconds": window["end_stable_seconds"],
        "valid": not reasons,
        "reasons": reasons,
        "evidence_type": "OBSERVED",
        "extract_digests": {
            "start_sha256": window["start_sha256"],
            "end_sha256": window["end_sha256"],
        },
    }


def payload_route_operation(world: dict, label: str) -> dict:
    route = world["_routes"][label]
    outcome, op = route["route_operation"]
    payload: dict[str, Any] = {
        "kind": "ROUTE_OPERATION_RECONCILIATION",
        "gateway_route": evidence_route(world, label),
        "outcome": outcome,
    }
    if op:
        payload["operation_id"] = op
        payload["contract_version_reconciliation"] = "RESOLVED"
        payload["contract_version_id"] = world["operations"][op]["contract_version_id"]
    payload["mapping_entries"] = [
        {"operation_id": entry} for entry in sorted(route["operation_mapping_entries"])
    ]
    payload["rule"] = RECONCILIATION_RULE
    return payload


def payload_target_service(world: dict, label: str) -> dict:
    route = world["_routes"][label]
    outcome, service = route["target_service"]
    payload: dict[str, Any] = {
        "kind": "TARGET_SERVICE_RECONCILIATION",
        "gateway_route": evidence_route(world, label),
        "outcome": outcome,
    }
    if outcome == "RESOLVED":
        payload["service_id"] = service
    payload["mapping_entries"] = [
        {"target": carrier, "service_id": sid}
        for carrier, sid in sorted(route["service_mapping_entries"])
    ]
    payload["labels"] = [
        {"carrier": carrier, "service_id": sid} for carrier, sid in sorted(route["service_labels"])
    ]
    payload["rule"] = RECONCILIATION_RULE
    return payload


def payload_limitations(world: dict, request: dict, label: str) -> dict:
    window = world["windows"][request["gateway_instance_id"]]
    limits = route_limits(world, label)
    return {
        "kind": "QUALIFICATION_LIMITATIONS",
        "gateway_route": evidence_route(world, label),
        "coverage": "UNKNOWN_COVERAGE" if limits else "SUFFICIENT_FOR_ZERO",
        "codes": limits,
        "window_valid": not window["window_reasons"],
    }


def resolved(ref: str, kind: str, payload: dict) -> dict:
    return {"ref": ref, "status": "RESOLVED", "kind": kind, "evidence": payload}


def not_resolved(ref: str) -> dict:
    return {"ref": ref, "status": "NOT_RESOLVED"}


def evidence_request(world: dict, base: dict, refs: list[str], snapshot_label: str = "A") -> dict:
    request = {
        "mode": "evidence",
        "snapshot_id": SNAPSHOTS[snapshot_label]["snapshot_id"],
        "target": dict(base["target"]),
        "gateway_instance_id": base["gateway_instance_id"],
        "environment": base["environment"],
        "window_start": base["window_start"],
        "window_end": base["window_end"],
        "evidence_refs": sorted(refs),
    }
    if base.get("consumer_id"):
        request["consumer_id"] = base["consumer_id"]
    return request


def evidence_answer(world: dict, request: dict, entries: list[dict], outcome: str, codes) -> dict:
    data = {
        "request_context": request_context(request),
        "entries": sorted(entries, key=lambda entry: entry["ref"]),
    }
    return envelope("evidence", outcome, snapshot_ref(world["snapshot"]), data, codes)


# --- Cases ----------------------------------------------------------------------------------------


def answer_case(
    case_id: str,
    title: str,
    spec_refs: list[str],
    world_name: str,
    request: dict,
    expected: dict,
    note: str | None = None,
) -> dict:
    inputs: dict[str, Any] = {"world": world_name, "current_snapshot": None}
    case = {
        "id": case_id,
        "kind": "answer",
        "title": title,
        "spec_refs": spec_refs,
        "inputs": inputs,
        "request": request,
        "expected": expected,
    }
    if note:
        case["note"] = note
    return case


def cases() -> list[dict]:
    base = world_base()
    new = world_new_snapshot()
    unattributed = world_unattributed()
    not_settled = world_not_settled()
    reversed_window = world_reversed()
    no_measurement = world_no_measurement()
    out: list[dict] = []

    def add(case_id, title, spec_refs, world_name, world, request, expected, note=None):
        case = answer_case(case_id, title, spec_refs, world_name, request, expected, note)
        case["inputs"]["current_snapshot"] = world["snapshot"]
        out.append(case)

    alpha = with_consumer(base, "alpha")
    beta = with_consumer(base, "beta")
    summary_orders_op = counts(2, 1, 4, 0, 0)

    # A01-A07: one Route and one consumer each.
    request = route_target(base, "orders-route", **alpha)
    add(
        "A01",
        "Configured and observed",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["orders-route"],
            pairs=[("alpha", "orders-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )
    request = route_target(base, "orders-v2-route", **alpha)
    add(
        "A02",
        "Configured and measured zero",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["orders-v2-route"],
            pairs=[("alpha", "orders-v2-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )
    request = route_target(base, "legacy-route", **alpha)
    add(
        "A03",
        "Configured and insufficient measurement",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["legacy-route"],
            pairs=[("alpha", "legacy-route")],
            outcome="PARTIAL",
            codes=["COVERAGE_UNKNOWN"],
        ),
    )
    request = route_target(base, "orders-route", **beta)
    add(
        "A04",
        "Observed without a matching configured fact",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["orders-route"],
            pairs=[("beta", "orders-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )
    request = route_target(base, "billing-route", **beta)
    add(
        "A05",
        "Rejected attempt only",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["billing-route"],
            pairs=[("beta", "billing-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )
    request = route_target(base, "bare-route", **alpha)
    add(
        "A06",
        "Unresolved Route to Operation",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["bare-route"],
            pairs=[("alpha", "bare-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )
    request = route_target(base, "conflict-route", **beta)
    add(
        "A07",
        "Conflicting target Service",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["conflict-route"],
            pairs=[("beta", "conflict-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )

    # A08/A09: exact Operation and exact Service targets.
    request = query_request("API_OPERATION", OP_INVOICES)
    add(
        "A08",
        "Exact Operation target",
        ["I3 §12", "I3 §5.2", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["billing-route"],
            pairs=[("beta", "billing-route"), ("gamma", "billing-route")],
            outcome="ANSWERED",
            codes=[],
            summary={"route_operation": counts(1, 2, 4, 0, 0)},
        ),
    )
    request = query_request("APPLICATION_SERVICE", SVC_BILLING)
    add(
        "A09",
        "Exact Service target",
        ["I3 §12", "I3 §5.3", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["billing-route"],
            pairs=[("beta", "billing-route"), ("gamma", "billing-route")],
            outcome="ANSWERED",
            codes=[],
            summary={"target_service": counts(1, 2, 3, 0, 1)},
        ),
    )

    # A10-A12: what stays visible when there is no row.
    request = route_target(unattributed, "orders-route")
    add(
        "A10",
        "Unattributed traffic invents no consumer row",
        ["I3 §12", "D11"],
        "unattributed",
        unattributed,
        request,
        query_answer(
            unattributed,
            request,
            routes=["orders-route"],
            pairs=[("alpha", "orders-route")],
            outcome="PARTIAL",
            codes=["COVERAGE_UNKNOWN"],
        ),
    )
    request = route_target(not_settled, "nocov-route")
    add(
        "A11",
        "Empty rows with an invalid window",
        ["I3 §12", "I3 §6", "D11"],
        "not-settled",
        not_settled,
        request,
        query_answer(
            not_settled,
            request,
            routes=["nocov-route"],
            pairs=[],
            outcome="PARTIAL",
            codes=["COVERAGE_UNKNOWN", "WINDOW_NOT_VALID"],
        ),
    )
    request = route_target(base, "nocov-route")
    add(
        "A12",
        "Selected Route without pair rows",
        ["I3 §12", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["nocov-route"],
            pairs=[],
            outcome="PARTIAL",
            codes=["COVERAGE_UNKNOWN"],
        ),
    )

    # A13: no measurement source.
    request = route_target(no_measurement, "orders-route")
    add(
        "A13",
        "Gateway without a measurement source",
        ["I3 §12", "D6", "D11"],
        "no-measurement",
        no_measurement,
        request,
        refusal("query", "MEASUREMENT_WINDOW_NOT_AVAILABLE", "A"),
    )

    # A14: the same environment and window on two gateways.
    request = route_target(base, "orders-route")
    add(
        "A14",
        "Gateway one selects its own window",
        ["I3 §12", "D3", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["orders-route"],
            pairs=[("alpha", "orders-route"), ("beta", "orders-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )
    request = query_request("GATEWAY_ROUTE", base["_routes"]["other-route"]["id"])
    request["gateway_instance_id"] = GW2
    add(
        "A14b",
        "Gateway two selects its own window",
        ["I3 §12", "D3", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=["other-route"],
            pairs=[("alpha2", "other-route")],
            outcome="ANSWERED",
            codes=[],
        ),
    )

    # A15: paging. Three rows on the listOrders selection, two per page.
    orders_op = query_request("API_OPERATION", OP_ORDERS)
    all_pairs = [("alpha", "orders-route"), ("alpha", "orders-v2-route"), ("beta", "orders-route")]

    def key(pair: tuple[str, str]) -> tuple[str, str]:
        return (base["_consumers"][pair[0]]["id"], base["_routes"][pair[1]]["id"])

    sequence = sorted(all_pairs, key=key)
    keys = [key(pair) for pair in sequence]
    first_page = {**orders_op, "limit": 2}
    add(
        "A15a",
        "Page boundary: first page",
        ["I3 §8", "D8", "D11"],
        "base",
        base,
        first_page,
        query_answer(
            base,
            first_page,
            routes=["orders-route", "orders-v2-route"],
            pairs=sequence[:2],
            outcome="PARTIAL",
            codes=["MORE_ROWS_AVAILABLE"],
            summary={"route_operation": summary_orders_op},
            after=sequence[1],
        ),
    )
    cursor = out[-1]["expected"]["data"]["page"]["next_cursor"]
    second_page = {
        **orders_op,
        "limit": 2,
        "cursor": cursor,
        "snapshot_id": SNAPSHOTS["A"]["snapshot_id"],
    }
    add(
        "A15b",
        "Page boundary: continuation from the issued cursor",
        ["I3 §8", "D8", "D11"],
        "base",
        base,
        second_page,
        query_answer(
            base,
            second_page,
            routes=["orders-route", "orders-v2-route"],
            pairs=sequence[2:],
            outcome="ANSWERED",
            codes=[],
            summary={"route_operation": summary_orders_op},
            limit=2,
        ),
    )
    substituted = encode_cursor(
        after=keys[0],
        digest=query_digest(request_context(orders_op)),
        snapshot_id=SNAPSHOTS["A"]["snapshot_id"],
    )
    forged = {**orders_op, "cursor": substituted, "snapshot_id": SNAPSHOTS["A"]["snapshot_id"]}
    add(
        "A15c",
        "Page boundary: a substituted well-formed position",
        ["I3 §8", "D8", "D11"],
        "base",
        base,
        forged,
        query_answer(
            base,
            forged,
            routes=["orders-route", "orders-v2-route"],
            pairs=sequence[1:],
            outcome="ANSWERED",
            codes=[],
            summary={"route_operation": summary_orders_op},
        ),
        note="D8: a substituted `after` only starts the continuation at that position; the rows "
        "stay inside the same snapshot and selection and are strictly after it.",
    )
    add(
        "A15d",
        "Page boundary: the same selection unpaged",
        ["I3 §8", "D11"],
        "base",
        base,
        orders_op,
        query_answer(
            base,
            orders_op,
            routes=["orders-route", "orders-v2-route"],
            pairs=sequence,
            outcome="ANSWERED",
            codes=[],
            summary={"route_operation": summary_orders_op},
        ),
    )
    other_filter = {**second_page, "consumer_id": base["_consumers"]["gamma"]["id"]}
    add(
        "A15e",
        "A cursor bound to different request inputs",
        ["I3 §8", "D6", "D8", "D11"],
        "base",
        base,
        other_filter,
        refusal("query", "CURSOR_QUERY_MISMATCH", "A"),
    )

    # A16/A17: a changed snapshot.
    add(
        "A16",
        "Unrelated import during paging",
        ["I3 §8", "D6", "D8", "D11"],
        "new-snapshot",
        new,
        second_page,
        refusal("query", "SNAPSHOT_NOT_AVAILABLE", "B"),
    )
    stale = route_target(base, "orders-route", snapshot_id=SNAPSHOTS["A"]["snapshot_id"], **alpha)
    add(
        "A17",
        "Stale snapshot",
        ["I3 §12", "D6", "D11"],
        "new-snapshot",
        new,
        stale,
        refusal("query", "SNAPSHOT_NOT_AVAILABLE", "B"),
    )

    # A18/A19: unknown and out-of-scope targets, and an Operation without a Route.
    request = query_request("APPLICATION_SERVICE", "service:not-in-the-snapshot")
    add(
        "A18a",
        "Unknown target",
        ["D6", "D11"],
        "base",
        base,
        request,
        refusal("query", "UNKNOWN_TARGET", "A"),
    )
    request = query_request("GATEWAY_ROUTE", base["_routes"]["other-route"]["id"])
    add(
        "A18b",
        "A Route that belongs to another gateway",
        ["D6", "D11"],
        "base",
        base,
        request,
        refusal("query", "TARGET_NOT_IN_WINDOW_SCOPE", "A"),
    )
    request = query_request("API_OPERATION", OP_GET_ORDER)
    add(
        "A19",
        "Operation with no resolved Route",
        ["I3 §5.2", "D6", "D11"],
        "base",
        base,
        request,
        query_answer(
            base,
            request,
            routes=[],
            pairs=[],
            outcome="NOT_ANSWERED",
            codes=["NO_ROUTE_SELECTED"],
            summary={"route_operation": counts(0, 3, 4, 0, 0)},
        ),
    )

    # A20: a reversed window stays addressable.
    request = {
        **route_target(reversed_window, "orders-route", **with_consumer(reversed_window, "alpha")),
        "window_start": "2026-10-13T10:10:00Z",
        "window_end": WS,
    }
    add(
        "A20",
        "A reversed window is accepted and invalid",
        ["D3", "I2 handoff"],
        "reversed",
        reversed_window,
        request,
        query_answer(
            reversed_window,
            request,
            routes=["orders-route"],
            pairs=[("alpha", "orders-route")],
            outcome="PARTIAL",
            codes=["COVERAGE_UNKNOWN", "WINDOW_NOT_VALID"],
        ),
    )

    out.extend(evidence_cases(base, new))
    out.extend(property_cases())
    out.extend(request_cases(base))
    return out


def evidence_cases(base: dict, new: dict) -> list[dict]:
    out: list[dict] = []

    def add(case_id, title, spec_refs, world_name, world, request, expected, note=None):
        case = answer_case(case_id, title, spec_refs, world_name, request, expected, note)
        case["inputs"]["current_snapshot"] = world["snapshot"]
        out.append(case)

    # E01a: every kind, for a Route with limitations.
    ctx = route_target(base, "legacy-route", **with_consumer(base, "alpha"))
    refs = Refs(base, ctx)
    entries = [
        resolved(
            refs.configured("alpha", "legacy-route"),
            "CONFIGURED_ACCESS",
            payload_configured(base, ctx, "alpha", "legacy-route"),
        ),
        resolved(refs.window(), "MEASUREMENT_WINDOW", payload_window(base, ctx)),
        resolved(
            refs.route_operation("legacy-route"),
            "ROUTE_OPERATION_RECONCILIATION",
            payload_route_operation(base, "legacy-route"),
        ),
        resolved(
            refs.target_service("legacy-route"),
            "TARGET_SERVICE_RECONCILIATION",
            payload_target_service(base, "legacy-route"),
        ),
        resolved(
            refs.limitations("legacy-route"),
            "QUALIFICATION_LIMITATIONS",
            payload_limitations(base, ctx, "legacy-route"),
        ),
    ]
    request = evidence_request(base, ctx, [entry["ref"] for entry in entries])
    add(
        "E01a",
        "All five evidence kinds resolve",
        ["I3 §9", "D9", "D11"],
        "base",
        base,
        request,
        evidence_answer(base, request, entries, "ANSWERED", []),
    )

    # E01b: a CONFLICT service reconciliation with its raw statements.
    ctx = route_target(base, "conflict-route", **with_consumer(base, "beta"))
    refs = Refs(base, ctx)
    entries = [
        resolved(
            refs.target_service("conflict-route"),
            "TARGET_SERVICE_RECONCILIATION",
            payload_target_service(base, "conflict-route"),
        ),
        resolved(
            refs.configured("beta", "conflict-route"),
            "CONFIGURED_ACCESS",
            payload_configured(base, ctx, "beta", "conflict-route"),
        ),
    ]
    request = evidence_request(base, ctx, [entry["ref"] for entry in entries])
    add(
        "E01b",
        "A conflicting Service reconciliation exposes only the raw statements",
        ["I3 §9", "D9", "D11"],
        "base",
        base,
        request,
        evidence_answer(base, request, entries, "ANSWERED", []),
    )

    # E01c: a RESOLVED Route -> Operation -> contract version chain.
    ctx = route_target(base, "orders-route", **with_consumer(base, "alpha"))
    refs = Refs(base, ctx)
    entries = [
        resolved(
            refs.route_operation("orders-route"),
            "ROUTE_OPERATION_RECONCILIATION",
            payload_route_operation(base, "orders-route"),
        ),
        resolved(
            refs.target_service("orders-route"),
            "TARGET_SERVICE_RECONCILIATION",
            payload_target_service(base, "orders-route"),
        ),
    ]
    request = evidence_request(base, ctx, [entry["ref"] for entry in entries])
    add(
        "E01c",
        "A resolved chain",
        ["I3 §9", "D9", "D11"],
        "base",
        base,
        request,
        evidence_answer(base, request, entries, "ANSWERED", []),
    )

    # E02: forged, cross-snapshot and cross-context refs are indistinguishable.
    ctx = route_target(base, "orders-route", **with_consumer(base, "alpha"))
    refs = Refs(base, ctx)
    other_snapshot = Refs(base, ctx, snapshot_label="B")
    other_ctx = route_target(base, "billing-route", **with_consumer(base, "gamma"))
    other_context = Refs(base, other_ctx)
    forged = "api-evidence:" + hashlib.sha256(b"i3.1c forged ref").hexdigest()
    good = refs.window()
    bad = [forged, other_snapshot.window(), other_context.window()]
    request = evidence_request(base, ctx, [good, *bad])
    add(
        "E02a",
        "Some refs resolve, forged, cross-snapshot and cross-context refs do not",
        ["I3 §12", "D6", "D9", "D11"],
        "base",
        base,
        request,
        evidence_answer(
            base,
            request,
            [resolved(good, "MEASUREMENT_WINDOW", payload_window(base, ctx))]
            + [not_resolved(ref) for ref in bad],
            "PARTIAL",
            ["EVIDENCE_REF_NOT_RESOLVED"],
        ),
    )
    request = evidence_request(base, ctx, bad)
    add(
        "E02b",
        "No ref resolves",
        ["I3 §12", "D6", "D9", "D11"],
        "base",
        base,
        request,
        evidence_answer(
            base,
            request,
            [not_resolved(ref) for ref in bad],
            "NOT_ANSWERED",
            ["EVIDENCE_REF_NOT_RESOLVED"],
        ),
    )
    request = evidence_request(new, ctx, [good], snapshot_label="A")
    add(
        "E02c",
        "Evidence for a snapshot that is no longer current",
        ["D6", "D9", "D11"],
        "new-snapshot",
        new,
        request,
        refusal("evidence", "SNAPSHOT_NOT_AVAILABLE", "B"),
    )
    return out


def property_cases() -> list[dict]:
    return [
        {
            "id": "A15",
            "kind": "property",
            "title": "No duplicate or lost row across the page boundary",
            "spec_refs": ["I3 §8", "I3 §12", "D8", "D11"],
            "steps": ["A15a", "A15b", "A15d"],
            "assert": [
                {
                    "op": "pages_concatenate_to",
                    "pages": ["A15a", "A15b"],
                    "whole": "A15d",
                    "description": "rows(A15a) + rows(A15b) equals rows(A15d)",
                },
                {
                    "op": "no_duplicate_rows",
                    "cases": ["A15a", "A15b"],
                    "description": "no (consumer.id, gateway_route.id) occurs twice",
                },
                {
                    "op": "suffix_of",
                    "case": "A15c",
                    "whole": "A15d",
                    "description": "a substituted position yields only rows strictly after it",
                },
                {
                    "op": "row_count",
                    "case": "A15a",
                    "equals": 2,
                    "description": "non-empty cardinality: the first page has two rows",
                },
            ],
        },
        {
            "id": "A14c",
            "kind": "property",
            "title": "The gateway selects exactly one window",
            "spec_refs": ["I3 §12", "D3", "D11"],
            "steps": ["A14", "A14b"],
            "assert": [
                {
                    "op": "differ",
                    "path": "expected.data.window.source_instance_id",
                    "cases": ["A14", "A14b"],
                    "description": "the two gateways answer from different measurement sources",
                },
                {
                    "op": "disjoint_rows",
                    "cases": ["A14", "A14b"],
                    "description": "no row of one gateway appears in the other's answer",
                },
                {
                    "op": "row_count",
                    "case": "A14",
                    "equals": 2,
                    "description": "non-empty cardinality: gateway one has two rows",
                },
            ],
        },
        {
            "id": "C01",
            "kind": "property",
            "title": "A credential canary appears in no answer and no evidence payload",
            "spec_refs": ["I3 §12", "D7", "D11"],
            "steps": ["ALL"],
            "canary": CANARY,
            "assert": [
                {
                    "op": "absent_everywhere",
                    "value": CANARY,
                    "description": "the canary placed in the world's plugin configuration is "
                    "absent from the serialized expected answer of every case",
                },
                {
                    "op": "present_in_world",
                    "value": CANARY,
                    "description": "non-vacuous: the canary is present in the world inputs",
                },
            ],
        },
    ]


def request_cases(base: dict) -> list[dict]:
    route = base["_routes"]["orders-route"]["id"]
    alpha = base["_consumers"]["alpha"]["id"]
    good_query = query_request("GATEWAY_ROUTE", route)
    snap = SNAPSHOTS["A"]["snapshot_id"]
    ref_a = "api-evidence:" + "a" * 64
    ref_b = "api-evidence:" + "b" * 64
    good_evidence = evidence_request(base, good_query, [ref_a])
    pydantic_only = {"V10", "V11", "V12", "V17"}

    def bad(case_id, title, request, spec_refs, reason=None):
        case = {
            "id": case_id,
            "kind": "request",
            "title": title,
            "spec_refs": spec_refs,
            "request": request,
            "expected": {"validation_error": True},
        }
        if case_id in pydantic_only:
            case["pydantic_only"] = reason or "the JSON Schema cannot express it (D12.12)"
        return case

    def replace(request: dict, **changes: Any) -> dict:
        updated = {**request, **changes}
        return {key: value for key, value in updated.items() if value is not None}

    return [
        bad(
            "V01",
            "A Service target with an Operation id",
            replace(good_query, target={"kind": "APPLICATION_SERVICE", "id": OP_ORDERS}),
            ["D3"],
        ),
        bad(
            "V02",
            "An Operation target that is a display name",
            replace(good_query, target={"kind": "API_OPERATION", "id": "listOrders"}),
            ["D3"],
        ),
        bad(
            "V03",
            "A Route target with a short digest",
            replace(good_query, target={"kind": "GATEWAY_ROUTE", "id": "gateway-route:owned:abc"}),
            ["D3"],
        ),
        bad(
            "V04",
            "An empty gateway_instance_id",
            replace(good_query, gateway_instance_id=""),
            ["D3"],
        ),
        bad(
            "V05",
            "A gateway_instance_id with trailing whitespace",
            replace(good_query, gateway_instance_id="gw-prod-1 "),
            ["D3"],
        ),
        bad(
            "V06",
            "An environment of 129 characters",
            replace(good_query, environment="e" * 129),
            ["D3"],
        ),
        bad(
            "V07",
            "A window start that is not whole-second UTC",
            replace(good_query, window_start="2026-10-13T10:00:00.5Z"),
            ["D3"],
        ),
        bad("V08", "limit 0", replace(good_query, limit=0), ["D3"]),
        bad("V09", "limit 201", replace(good_query, limit=201), ["D3"]),
        bad(
            "V10",
            "A cursor without snapshot_id",
            replace(
                good_query,
                cursor=encode_cursor(after=(alpha, route), digest="0" * 64, snapshot_id=snap),
            ),
            ["D3", "D8"],
        ),
        bad(
            "V11",
            "A cursor that is not an API usage cursor",
            replace(good_query, cursor="bm90LWpzb24", snapshot_id=snap),
            ["D8"],
        ),
        bad(
            "V12",
            "A cursor in a non-canonical form",
            replace(
                good_query,
                cursor=base64.urlsafe_b64encode(
                    json.dumps(
                        {
                            "v": 1,
                            "after": [alpha, route],
                            "query_digest": "0" * 64,
                            "schema_version": "0.7",
                            "snapshot_id": snap,
                        }
                    ).encode()
                )
                .decode()
                .rstrip("="),
                snapshot_id=snap,
            ),
            ["D8"],
            "the cursor decodes but is not the canonical encoding (D8 integrity); a pattern-only "
            "schema accepts it",
        ),
        bad(
            "V13",
            "A consumer filter that is a username",
            replace(good_query, consumer_id="spike-alpha"),
            ["D3"],
        ),
        bad(
            "V14",
            "An unknown field (a Cypher fragment)",
            replace(good_query, cypher="MATCH (n) RETURN n"),
            ["D1", "D3"],
        ),
        bad(
            "V15",
            "A credential-like field",
            replace(good_query, api_key="not-accepted"),
            ["D7"],
        ),
        bad("V16", "An unknown mode", replace(good_query, mode="history"), ["D1", "D3"]),
        bad(
            "V17",
            "Evidence refs that are not sorted",
            replace(good_evidence, evidence_refs=[ref_b, ref_a]),
            ["D3"],
        ),
        bad(
            "V18",
            "Duplicate evidence refs",
            replace(good_evidence, evidence_refs=[ref_a, ref_a]),
            ["D3"],
        ),
        bad("V19", "No evidence refs", replace(good_evidence, evidence_refs=[]), ["D3"]),
        bad(
            "V20",
            "21 evidence refs",
            replace(
                good_evidence,
                evidence_refs=sorted("api-evidence:" + f"{n:064x}" for n in range(21)),
            ),
            ["D3"],
        ),
        bad(
            "V21",
            "An evidence request without snapshot_id",
            replace(good_evidence, snapshot_id=None),
            ["D3", "D9"],
        ),
        bad("V22", "An evidence request with a limit", replace(good_evidence, limit=10), ["D3"]),
    ]


def document() -> dict:
    return {
        "contract": "aip-v0.7-i3-expected-answers",
        "vector_set": 1,
        "governing": [
            "docs/specifications/0.7.0/i3-api-aware-current-state-projection-and-public-answer.md",
            "docs/specifications/0.7.0/i3-decision-record.md D1-D12",
        ],
        "authored": "I3.1c, by author_expected_answers.py (stdlib only, no app import), before any "
        "I3.2 semantic code",
        "schemas": [
            "schemas/architecture_intelligence/v0.7/api-consumer-usage-request.schema.json",
            "schemas/architecture_intelligence/v0.7/api-consumer-usage-answer.schema.json",
        ],
        "matching": "docs/specifications/0.7.0/i3-expected-answer-matrix.md §2",
        "snapshots": SNAPSHOTS,
        "worlds": {name: public_world(build()) for name, build in WORLDS.items()},
        "cases": cases(),
    }


def render() -> str:
    return (
        json.dumps(copy.deepcopy(document()), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
