"""Author the I4 bridge expectation B07 (v0.7.0 I4.1a; I4 spec §4.1 row 7, parent §22 item 7).

Standalone and stdlib-only: it imports nothing from `app`, so the expectation cannot be derived from
the implementation it qualifies. Identifier formulas and the D8/D9 derivations are reused from the
frozen I3 author (`../i3-vectors/author_expected_answers.py`, itself stdlib-only and checked against
the I1 and I2 vectors), loaded by path; this script adds no id formula of its own.

**What B07 is.** Parent §22 item 7 asks for an ambiguous Route -> Operation mapping. The frozen I3
oracle has no public answer with an `AMBIGUOUS` Route -> Operation outcome, and the I2 vectors K06
and K08 establish it only at the reconciliation level. B07 is one additive public-projection
vector: the world is the **exact frozen I2 handoff snapshot state** (raw facts and the derived
sections, as the repository's snapshot queries and the I2 rules produce them), in which the Route
`invoices-route` has no explicit mapping and its exact path and method are exposed by two
Operations of two contracts (K08), so the I2 outcome is `AMBIGUOUS` and no Operation attaches.

Three cases, all authored by hand before any AIP run on the I4 candidate:
- `B07a` a `GATEWAY_ROUTE` query: the rows keep `api.reconciliation = AMBIGUOUS` with no
  `operation_id`, the independent Service chain stays `RESOLVED`;
- `B07b` an `API_OPERATION` query for one of the two candidate Operations: the Route is **not**
  selected (`NO_ROUTE_SELECTED` with data) and the association summary counts it as `ambiguous`;
- `B07c` the evidence mode: the Route -> Operation reconciliation payload states the `AMBIGUOUS`
  outcome with no mapping statement, and exposes no basis.

Every list and count is a literal. The only placeholder is the I3 matrix wildcard `{{*}}` for
limitation messages and the producer version. Usage, from the repository root:

    python docs/specifications/0.7.0/i4-vectors/author_i4_expected.py

writes `expected-i4.json` next to this file. Re-running must reproduce it byte for byte.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "expected-i4.json"
I3_AUTHOR = HERE.parent / "i3-vectors" / "author_expected_answers.py"


def _load_i3_author() -> Any:
    spec = importlib.util.spec_from_file_location("i3_author_expected_answers", I3_AUTHOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


I3 = _load_i3_author()

GW, ENV = I3.GW1, I3.ENV
WS, WE = I3.WS, I3.WE
REVISION = "apisix:3.19.0+etcd:4242"
CONFIGURED_SOURCE = "apisix-metrics-prod"
SNAPSHOT_SEED = "i4.1a bridge snapshot"
SNAPSHOT = {
    "snapshot_id": "aip:snapshot:v1:" + hashlib.sha256(SNAPSHOT_SEED.encode()).hexdigest(),
    "model_revision": "sha256:" + hashlib.sha256(SNAPSHOT_SEED.encode()).hexdigest(),
}

# The two candidate Operations of K08 (the same path and method in two contracts) and a control.
OP_BILLING = "operation:billing-api:listInvoices"
OP_BILLING2 = "operation:billing2-api:listInvoices"
OP_ORDERS = "operation:orders-api:listOrders"
SVC_BILLING, SVC_ORDERS = "service:billing", "service:orders"
OPERATIONS = {
    OP_BILLING: ("billing-api", "listInvoices", SVC_BILLING, "/invoices"),
    OP_BILLING2: ("billing2-api", "listInvoices", SVC_BILLING, "/invoices"),
    OP_ORDERS: ("orders-api", "listOrders", SVC_ORDERS, "/orders"),
}
CONTRACTS = {
    name: I3.contract_id(f"urn:aip:source:openapi:{name}")
    for name in ("billing-api", "billing2-api", "orders-api")
}
VERSIONS = {name: I3.contract_version_id(cid, "1.0.0") for name, cid in CONTRACTS.items()}

CONSUMERS = {"alpha": "spike-alpha", "beta": "spike-beta"}
CONSUMER_IDS = {label: I3.consumer_id(GW, name) for label, name in CONSUMERS.items()}
ROUTES = {
    # (uri, labelled Service); no explicit mapping entry anywhere: the exact-URI fallback applies
    "invoices-route": ("/invoices", SVC_BILLING),
    "orders-route": ("/orders", SVC_ORDERS),
}
ROUTE_IDS = {label: I3.route_id(GW, label) for label in ROUTES}

WINDOW_PARTS = (GW, ENV, WS, WE, I3.START_SHA, I3.END_SHA)
WINDOW = {
    "id": "measurement-window:owned:" + I3.sha(*WINDOW_PARTS),  # I2 M04
    "evidence_id": "evidence:apisix-measurement:" + I3.sha(*WINDOW_PARTS),  # I2 M05
    "source_instance_id": I3.measurement_source_id(CONFIGURED_SOURCE, GW, ENV),  # I2 M01
}
SOURCE_EVIDENCE_ID = I3.source_evidence_id(GW, REVISION)  # I1 V13

# (consumer label, route label): configured, usage status, upstream count
PAIRS = [
    ("alpha", "invoices-route", True, "OBSERVED_USAGE", 4),
    ("beta", "invoices-route", True, "MEASURED_ZERO", 0),
    ("alpha", "orders-route", True, "MEASURED_ZERO", 0),
]
OBSERVED = {("alpha", "invoices-route")}
RULE = I3.RECONCILIATION_RULE
QUALIFICATION = I3.QUALIFICATION_RULE


def by(keys: tuple[str, ...], rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: tuple(row[key] for key in keys))


# --- The world: the exact frozen I2 handoff snapshot state ------------------------------------------


def snapshot_state() -> dict:
    consumers = [
        {
            "id": CONSUMER_IDS[label],
            "gateway_instance_id": GW,
            "environment": ENV,
            "username": name,
        }
        for label, name in CONSUMERS.items()
    ]
    routes = [
        {
            "id": ROUTE_IDS[label],
            "gateway_instance_id": GW,
            "environment": ENV,
            "route_id": label,
            "uri": uri,
            "methods": ["GET"],
            "labels_json": I3.compact_json({"aip/service": service}),
        }
        for label, (uri, service) in ROUTES.items()
    ]
    configured = [
        {
            "id": I3.configured_access_id(CONSUMER_IDS[c], ROUTE_IDS[r]),
            "consumer_id": CONSUMER_IDS[c],
            "route_id": ROUTE_IDS[r],
            "rule_kind": I3.RULE_KIND,
            "polarity": "ALLOW",
            "scope": "ROUTE",
            "evidence_ids": [SOURCE_EVIDENCE_ID],
            "source_revision": REVISION,
        }
        for c, r, is_configured, _, _ in PAIRS
        if is_configured
    ]
    gateway = {
        "consumers": by(("id",), consumers),
        "routes": by(("id",), routes),
        "services": [],
        "configured_access": by(("id",), configured),
        "limitations": [],
        "source_evidence": [
            {
                "id": SOURCE_EVIDENCE_ID,
                "gateway_instance_id": GW,
                "environment": ENV,
                "apisix_version": I3.APISIX_VERSION,
                "source_revision": REVISION,
                "evidence_type": "DECLARED",
            }
        ],
    }
    operations = [
        {
            "id": op,
            "name": name,
            "service_id": service,
            "operation_id": name,
            "method": "GET",
            "path": path,
        }
        for op, (_, name, service, path) in OPERATIONS.items()
    ]
    contracts = {
        "contracts": by(
            ("id",),
            [
                {
                    "id": cid,
                    "openapi_source_instance_id": f"urn:aip:source:openapi:{name}",
                    "limitations": [],
                }
                for name, cid in CONTRACTS.items()
            ],
        ),
        "versions": by(
            ("id",),
            [
                {"id": VERSIONS[name], "contract_id": cid, "info_version": "1.0.0"}
                for name, cid in CONTRACTS.items()
            ],
        ),
        "associations": by(
            ("id",),
            [
                {
                    "id": I3.association_id(
                        "OPERATION_IN_CONTRACT_VERSION", VERSIONS[contract], op
                    ),
                    "kind": "OPERATION_IN_CONTRACT_VERSION",
                    "contract_version_id": VERSIONS[contract],
                    "target_id": op,
                    "evidence_ids": [
                        "evidence:openapi:" + I3.sha("i4.1a openapi evidence", CONTRACTS[contract])
                    ],
                }
                for op, (contract, _, _, _) in OPERATIONS.items()
            ],
        ),
    }
    return {
        "gateway_configuration_v1": gateway,
        "operations": by(("id",), operations),
        "services": [
            {"id": sid, "name": sid.split(":", 1)[1], "version": "1.0.0"}
            for sid in (SVC_BILLING, SVC_ORDERS)
        ],
        "api_contracts_v1": contracts,
        "api_usage_v1": usage_state(),
    }


def usage_state() -> dict:
    window_row = {
        "id": WINDOW["id"],
        "source_instance_id": WINDOW["source_instance_id"],
        "gateway_instance_id": GW,
        "environment": ENV,
        "apisix_version": I3.APISIX_VERSION,
        "window_start": WS,
        "window_end": WE,
        "start_settled": True,
        "end_settled": True,
        "no_restart": True,
        "start_stable_seconds": 24,
        "end_stable_seconds": 22,
        "disabled_labels": [],
        "route_coverage_json": I3.compact_json({label: True for label in ROUTES}),
        "window_reasons": [],
        "evidence_ids": [WINDOW["evidence_id"]],
    }
    evidence_row = {
        "id": WINDOW["evidence_id"],
        "source_instance_id": WINDOW["source_instance_id"],
        "gateway_instance_id": GW,
        "environment": ENV,
        "apisix_version": I3.APISIX_VERSION,
        "window_start": WS,
        "window_end": WE,
        "start_sha256": I3.START_SHA,
        "end_sha256": I3.END_SHA,
        "evidence_type": "OBSERVED",
    }
    series, attributions, interactions, rows = [], [], [], []
    window = {**window_row, "evidence_id": WINDOW["evidence_id"]}
    for consumer, route, is_configured, usage, upstream in PAIRS:
        args = (CONSUMER_IDS[consumer], ROUTE_IDS[route], ENV, WS, WE)
        base = {
            "window_id": WINDOW["id"],
            "consumer_id": CONSUMER_IDS[consumer],
            "route_id": ROUTE_IDS[route],
            "consumer": CONSUMERS[consumer],
            "route": route,
        }
        totals = {"upstream_request_count": upstream, "rejected_attempt_count": 0}
        row: dict[str, Any] = {
            "id": I3.qualification_id(*args),  # I2 M09
            **base,
            "configured_status": "CONFIGURED_ACCESS_ESTABLISHED"
            if is_configured
            else "NO_MATCHING_CONFIGURED_ACCESS_FACT",
            "usage_status": usage,
            "coverage": "SUFFICIENT_FOR_ZERO",
            **totals,
            "limitations": [],
            "evidence_ids": [WINDOW["evidence_id"]],
        }
        if (consumer, route) in OBSERVED:
            series.append(
                I3.series_row(
                    window,
                    GW,
                    ENV,
                    CONSUMERS[consumer],
                    route,
                    "200",
                    "upstream",
                    "DELTA",
                    upstream,
                )
            )
            attributions.append(
                {
                    "window_id": WINDOW["id"],
                    "consumer": CONSUMERS[consumer],
                    "route": route,
                    "consumer_outcome": "RESOLVED",
                    "route_outcome": "RESOLVED",
                    "consumer_id": CONSUMER_IDS[consumer],
                    "route_id": ROUTE_IDS[route],
                }
            )
            interaction = I3.interaction_id(*args)  # I2 M06
            row["interaction_id"] = interaction
            interactions.append(
                {"id": interaction, **base, **totals, "evidence_ids": [WINDOW["evidence_id"]]}
            )
        rows.append(row)
    route_operation = [
        {
            "window_id": WINDOW["id"],
            "route_id": ROUTE_IDS["invoices-route"],
            "operation": "AMBIGUOUS",
        },
        {
            "window_id": WINDOW["id"],
            "route_id": ROUTE_IDS["orders-route"],
            "operation": "RESOLVED",
            "operation_id": OP_ORDERS,
            "contract_version": "RESOLVED",
            "contract_version_id": VERSIONS["orders-api"],
        },
    ]
    target_service = [
        {
            "window_id": WINDOW["id"],
            "route_id": ROUTE_IDS[label],
            "target": "RESOLVED",
            "service_id": service,
        }
        for label, (_, service) in ROUTES.items()
    ]
    coverage = [
        {
            "window_id": WINDOW["id"],
            "route_id": ROUTE_IDS[label],
            "coverage": "SUFFICIENT_FOR_ZERO",
            "limitations": [],
        }
        for label in ROUTES
    ]
    pair = ("window_id", "consumer", "route")
    per_route = ("window_id", "route_id")
    return {
        "windows": [window_row],
        "evidence": [evidence_row],
        "series": by(("id",), series),
        "limitations": [],
        "mapping_entries": [],
        "reconciliation_rule": RULE,
        "attributions": by(pair, attributions),
        "route_operation": by(per_route, route_operation),
        "target_service": by(per_route, target_service),
        "qualification_rule": QUALIFICATION,
        "coverage": by(per_route, coverage),
        "interactions": by(pair, interactions),
        "qualification_rows": by(pair, rows),
    }


# --- Literals shared by the answers ------------------------------------------------------------------


def request(kind: str, target: str, **extra: Any) -> dict:
    return {
        "mode": "query",
        "target": {"kind": kind, "id": target},
        "gateway_instance_id": GW,
        "environment": ENV,
        "window_start": WS,
        "window_end": WE,
        **extra,
    }


def context_of(req: dict) -> dict:
    return {
        "target": dict(req["target"]),
        "gateway_instance_id": req["gateway_instance_id"],
        "environment": req["environment"],
        "window_start": req["window_start"],
        "window_end": req["window_end"],
    }


class Refs:
    """The D9 refs of one request context under the case's snapshot."""

    def __init__(self, req: dict):
        self.digest = I3.query_digest(context_of(req))

    def _ref(self, kind: str, ids: list[str]) -> str:
        return I3.evidence_ref(SNAPSHOT["snapshot_id"], self.digest, kind, ids)

    def window(self) -> str:
        return self._ref("MEASUREMENT_WINDOW", [WINDOW["id"], WINDOW["evidence_id"]])

    def route_operation(self, route: str) -> str:
        return self._ref("ROUTE_OPERATION_RECONCILIATION", [ROUTE_IDS[route]])  # no mapping entry

    def target_service(self, route: str) -> str:
        return self._ref("TARGET_SERVICE_RECONCILIATION", [ROUTE_IDS[route]])  # label only

    def configured(self, consumer: str, route: str) -> str:
        return self._ref(
            "CONFIGURED_ACCESS",
            [I3.configured_access_id(CONSUMER_IDS[consumer], ROUTE_IDS[route]), SOURCE_EVIDENCE_ID],
        )


def envelope(mode: str, outcome: str, data: dict, codes: list[str]) -> dict:
    return {
        "schema_version": "0.7",
        "producer": {
            "name": "architecture-intelligence-platform",
            "version": I3.WILDCARD,
            "build_revision": I3.WILDCARD,
        },
        "tool": "get_api_consumer_usage",
        "mode": mode,
        "outcome": outcome,
        "snapshot": dict(SNAPSHOT),
        "data": data,
        "limitations": [{"code": code, "message": I3.WILDCARD} for code in sorted(codes)],
    }


def common_blocks(req: dict, refs: Refs) -> dict:
    return {
        "request_context": context_of(req),
        "window": {
            "window_start": WS,
            "window_end": WE,
            "source_instance_id": WINDOW["source_instance_id"],
            "valid": True,
            "reasons": [],
            "evidence_refs": [refs.window()],
        },
        "rules": {"reconciliation": dict(RULE), "qualification": dict(QUALIFICATION)},
        "configuration_sources": [
            {"gateway_instance_id": GW, "environment": ENV, "source_revision": REVISION}
        ],
        "measurement_sources": [
            {
                "source_instance_id": WINDOW["source_instance_id"],
                "window_start": WS,
                "window_end": WE,
                "apisix_version": I3.APISIX_VERSION,
            }
        ],
    }


def invoices_row(refs: Refs, consumer: str, interaction: bool) -> dict:
    route = "invoices-route"
    pair = next(p for p in PAIRS if p[0] == consumer and p[1] == route)
    usage_block: dict[str, Any] = {
        "status": pair[3],
        "coverage": "SUFFICIENT_FOR_ZERO",
        "upstream_request_count": pair[4],
        "rejected_attempt_count": 0,
    }
    if interaction:
        usage_block["interaction_id"] = I3.interaction_id(
            CONSUMER_IDS[consumer], ROUTE_IDS[route], ENV, WS, WE
        )
    return {
        "consumer": {"id": CONSUMER_IDS[consumer], "source_name": CONSUMERS[consumer]},
        "gateway_route": {
            "id": ROUTE_IDS[route],
            "gateway_instance_id": GW,
            "source_route_id": route,
        },
        # the I2 outcome is AMBIGUOUS: no operation_id and no contract chain (K08)
        "api": {"reconciliation": "AMBIGUOUS"},
        # the independent Service chain is untouched by the Operation ambiguity
        "application_service": {"reconciliation": "RESOLVED", "service_id": SVC_BILLING},
        "configured_access": {"status": "CONFIGURED_ACCESS_ESTABLISHED"},
        "usage": usage_block,
        "evidence_refs": sorted(
            [
                refs.window(),
                refs.route_operation(route),
                refs.target_service(route),
                refs.configured(consumer, route),
            ]
        ),
        "limitations": [],
    }


# --- The cases ------------------------------------------------------------------------------------


def case_b07a() -> dict:
    req = request("GATEWAY_ROUTE", ROUTE_IDS["invoices-route"])
    refs = Refs(req)
    rows = sorted(
        [
            invoices_row(refs, "alpha", interaction=True),
            invoices_row(refs, "beta", interaction=False),
        ],
        key=lambda r: (r["consumer"]["id"], r["gateway_route"]["id"]),
    )
    data = {
        **common_blocks(req, refs),
        "selected_routes": [
            {
                "route_id": ROUTE_IDS["invoices-route"],
                "source_route_id": "invoices-route",
                "coverage": "SUFFICIENT_FOR_ZERO",
                "limitations": [],
                "evidence_refs": [],
            }
        ],
        "rows": rows,
        "page": {"limit": 100, "returned": 2},
    }
    return {
        "id": "B07a",
        "kind": "answer",
        "title": "An ambiguous Route to Operation outcome stays ambiguous in the public row",
        "spec_refs": ["I4 §4.1 row 7", "parent §22.7", "I2 K08"],
        "inputs": {"world": "bridge", "current_snapshot": "A"},
        "request": req,
        "expected": envelope("query", "ANSWERED", data, []),
    }


def case_b07b() -> dict:
    req = request("API_OPERATION", OP_BILLING)
    refs = Refs(req)
    data = {
        **common_blocks(req, refs),
        # all two Routes of the scope by the Route -> Operation outcome, before target filtering
        "association_summary": {
            "route_operation": {
                "resolved_to_target": 0,
                "resolved_elsewhere": 1,
                "unresolved": 0,
                "ambiguous": 1,
                "conflict": 0,
            }
        },
        "selected_routes": [],
        "rows": [],
        "page": {"limit": 100, "returned": 0},
    }
    return {
        "id": "B07b",
        "kind": "answer",
        "title": "An Operation target never selects a Route whose Operation is ambiguous",
        "spec_refs": ["I4 §4.1 row 7", "I3 §5.2", "parent §22.7"],
        "inputs": {"world": "bridge", "current_snapshot": "A"},
        "request": req,
        "expected": envelope("query", "NOT_ANSWERED", data, ["NO_ROUTE_SELECTED"]),
    }


def case_b07c() -> dict:
    query = request("GATEWAY_ROUTE", ROUTE_IDS["invoices-route"])
    refs = Refs(query)
    route = {"id": ROUTE_IDS["invoices-route"], "source_route_id": "invoices-route"}
    operation = {
        "kind": "ROUTE_OPERATION_RECONCILIATION",
        "gateway_route": dict(route),
        "outcome": "AMBIGUOUS",
        "mapping_entries": [],
        "rule": dict(RULE),
    }
    service = {
        "kind": "TARGET_SERVICE_RECONCILIATION",
        "gateway_route": dict(route),
        "outcome": "RESOLVED",
        "service_id": SVC_BILLING,
        "mapping_entries": [],
        "labels": [{"carrier": "ROUTE", "service_id": SVC_BILLING}],
        "rule": dict(RULE),
    }
    entries = sorted(
        [
            {
                "ref": refs.route_operation("invoices-route"),
                "status": "RESOLVED",
                "kind": "ROUTE_OPERATION_RECONCILIATION",
                "evidence": operation,
            },
            {
                "ref": refs.target_service("invoices-route"),
                "status": "RESOLVED",
                "kind": "TARGET_SERVICE_RECONCILIATION",
                "evidence": service,
            },
        ],
        key=lambda entry: entry["ref"],
    )
    req = {
        "mode": "evidence",
        "snapshot_id": SNAPSHOT["snapshot_id"],
        "evidence_refs": [entry["ref"] for entry in entries],
        **{key: value for key, value in query.items() if key != "mode"},
    }
    data = {"request_context": context_of(req), "entries": entries}
    return {
        "id": "B07c",
        "kind": "answer",
        "title": "The ambiguous outcome is evidenced as raw facts only, with no basis",
        "spec_refs": ["I4 §4.1 row 7", "I3 D9 provenance boundary"],
        "inputs": {"world": "bridge", "current_snapshot": "A"},
        "request": req,
        "expected": envelope("evidence", "ANSWERED", data, []),
    }


# --- The frozen result class of every required case ---------------------------------------------
#
# I4 spec §10: a case is `I4_EXPECTED_NEGATIVE` when the outcome it tests is an abstention, a
# refusal or a rejection, and `I4_CORRECT` when it tests a positive or resolved outcome. These two
# lists are authored by hand, once, from each case's purpose in the I3 matrix and the register's
# class table; they are not derived from any expected answer or any run, so a run cannot move a case
# between the denominators. `RT01a`-`RT01d` are the questions of the I4 runner's generated
# real-import world (a page, its continuation and the evidence resolve; a stale snapshot is refused);
# the replay ids are those of `../i4-replay/expected-replay.json` and its structural fences.

POSITIVE = [
    *("A01", "A02", "A04", "A08", "A09", "A14", "A14b"),
    *("A15a", "A15b", "A15c", "A15d"),
    *("E01a", "E01b", "E01c", "B07c"),
    *("A14c", "A15", "C01"),
    *("RT01a", "RT01b", "RT01c"),
    # the APISIX replay (real captures; decision record D4)
    *("P1", "P2", "N4", "N4b", "OBS", "REVa", "REVc", "EV"),
]
ABSTAINING = [
    *("A03", "A05", "A06", "A07", "A10", "A11", "A12", "A13", "A15e"),
    *("A16", "A17", "A18a", "A18b", "A19", "A20"),
    *("E02a", "E02b", "E02c", "B07a", "B07b"),
    *(f"V{n:02d}" for n in range(1, 23)),
    "RT01d",
    *("N1", "N2", "N3", "REVb", "REVd", "REVe", "W-INVALID", "W-NONE"),
]


def classifications() -> dict[str, str]:
    classes = {case: "I4_CORRECT" for case in POSITIVE}
    classes.update({case: "I4_EXPECTED_NEGATIVE" for case in ABSTAINING})
    assert len(classes) == len(POSITIVE) + len(ABSTAINING), "a case is in both lists"
    return dict(sorted(classes.items()))


def document() -> dict:
    return {
        "contract": "aip-v0.7-i4-bridge-expected",
        "vector_set": 1,
        "governing": [
            (
                "docs/specifications/0.7.0/i4-deterministic-real-system-and-product-value-"
                "qualification.md §4.1 row 7"
            ),
            "docs/specifications/0.7.0/i3-expected-answer-matrix.md §2",
        ],
        "authored": "I4.1a, by author_i4_expected.py (stdlib only, no app import), before any "
        "execution on the I4 candidate",
        "matching": "docs/specifications/0.7.0/i3-expected-answer-matrix.md §2 (exact equality; "
        "the wildcard matches any non-empty string)",
        "snapshots": {"A": dict(SNAPSHOT)},
        "worlds": {"bridge": {"snapshot_state": snapshot_state()}},
        "classifications": classifications(),
        "cases": [case_b07a(), case_b07b(), case_b07c()],
    }


def render() -> str:
    return (
        json.dumps(copy.deepcopy(document()), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
