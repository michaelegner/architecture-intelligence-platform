"""Author the expected readings of the APISIX replay package (v0.7.0 I4.1c; I4 spec §5, decision
record D4).

Stdlib-only and written **before** any capture is taken: the readings follow from the traffic plan
below and the frozen I2 and I3 vocabulary (replay plan §5: P1, P2, N1-N4; the I4 additions OBS and
the revision transition), never from a captured byte. The capture session
(`capture_session.py`) sends exactly this traffic; the replay test and the I4 runner then compare the
answers of the imported captures with these facts. Facts, not full answers: the snapshot id and the
evidence refs depend on the captured bytes, so a reading states the rows (consumer, configured
access, usage, counts, coverage, limitations), the outcome and the window validity.

    python docs/specifications/0.7.0/i4-replay/author_replay_expected.py

writes `expected-replay.json` next to this file. Re-running must reproduce it byte for byte.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).resolve().parent / "expected-replay.json"

GATEWAY, ENVIRONMENT = "gw-i4-replay", "replay"

# --- The traffic plan (the only input of the capture session besides the configuration) ----------
# Window W1 (configuration R1). Every request is one HTTP call to the gateway.
TRAFFIC_W1 = [
    {"consumer": "alice", "route": "orders-route", "count": 3, "answered_by": "upstream"},
    {
        "consumer": "carol",
        "route": "orders-route",
        "count": 2,
        "answered_by": "apisix",
        "code": 403,
    },
    {"consumer": "", "route": "open-route", "count": 2, "answered_by": "upstream"},
    {"consumer": "erin", "route": "billing-route", "count": 4, "answered_by": "upstream"},
    {"consumer": "frank", "route": "shared-route", "count": 2, "answered_by": "upstream"},
    # legacy-route has no prometheus plugin: the request is answered, no series exists
    {"consumer": "alice", "route": "legacy-route", "count": 1, "answered_by": "upstream"},
]
# Window W2 (configuration R2, after a gateway restart: the counters start from nothing).
TRAFFIC_W2 = [
    {"consumer": "alice", "route": "reports-route", "count": 2, "answered_by": "upstream"},
]

# The configuration of each revision: allow-list per Route (None = no consumer-restriction), whether
# the prometheus plugin is enabled, and whether a key-auth plugin identifies the consumer.
R1 = {
    "orders-route": {"allow": ["alice", "bob", "dave", "erin"], "auth": True, "prometheus": True},
    "billing-route": {"allow": ["alice", "erin"], "auth": True, "prometheus": True},
    "legacy-route": {"allow": ["alice"], "auth": True, "prometheus": False},
    "open-route": {"allow": None, "auth": False, "prometheus": True},
    "shared-route": {"allow": None, "auth": True, "prometheus": True},
}
# R2: bob and dave leave orders-route, billing-route is deleted, reports-route is added.
R2 = {
    "orders-route": {"allow": ["alice", "erin"], "auth": True, "prometheus": True},
    "legacy-route": {"allow": ["alice"], "auth": True, "prometheus": False},
    "open-route": {"allow": None, "auth": False, "prometheus": True},
    "shared-route": {"allow": None, "auth": True, "prometheus": True},
    "reports-route": {"allow": ["alice"], "auth": True, "prometheus": True},
}
CONSUMERS = ["alice", "bob", "carol", "dave", "erin", "frank"]

CONFIGURED = "CONFIGURED_ACCESS_ESTABLISHED"
NO_FACT = "NO_MATCHING_CONFIGURED_ACCESS_FACT"
SUFFICIENT, UNKNOWN = "SUFFICIENT_FOR_ZERO", "UNKNOWN_COVERAGE"


def row(
    consumer: str,
    configured: str,
    usage: str,
    upstream: int | None,
    rejected: int | None,
    *,
    coverage: str = SUFFICIENT,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "consumer": consumer,
        "configured_access": configured,
        "usage": usage,
        "upstream_request_count": upstream,
        "rejected_attempt_count": rejected,
        "coverage": coverage,
        "limitations": limitations or [],
    }


def case(
    case_id: str,
    title: str,
    world: str,
    route: str,
    expect: dict[str, Any],
    consumer: str | None = None,
    derived: str | None = None,
    spec: str = "",
) -> dict[str, Any]:
    return {
        "id": case_id,
        "title": title,
        "world": world,
        "target": {"kind": "GATEWAY_ROUTE", "route": route},
        "consumer": consumer,
        "derived": derived,
        "origin": "derived" if derived else "real",
        "spec_refs": spec,
        "expect": expect,
    }


def answered(
    rows: list[dict[str, Any]],
    *,
    window_valid: bool = True,
    route_limitations: list[str] | None = None,
) -> dict[str, Any]:
    limitations = route_limitations or []
    codes = (["COVERAGE_UNKNOWN"] if limitations else []) + (
        [] if window_valid else ["WINDOW_NOT_VALID"]
    )
    return {
        "outcome": "PARTIAL" if codes else "ANSWERED",
        "limitations": sorted(codes),
        "window_valid": window_valid,
        "route_limitations": limitations,
        "rows": rows,
    }


def refusal(code: str) -> dict[str, Any]:
    return {"outcome": "NOT_ANSWERED", "limitations": [code], "refusal": code}


def cases() -> list[dict[str, Any]]:
    unestablished = "USAGE_UNESTABLISHED"
    return [
        case(
            "P1",
            "Allow-listed consumer with upstream usage",
            "r1",
            "orders-route",
            answered([row("alice", CONFIGURED, "OBSERVED_USAGE", 3, 0)]),
            "alice",
            spec="replay plan P1; parent §22.1",
        ),
        case(
            "P2",
            "Allow-listed consumer, closed coverage, no series: measured zero",
            "r1",
            "orders-route",
            answered([row("bob", CONFIGURED, "MEASURED_ZERO", 0, 0)]),
            "bob",
            spec="replay plan P2; parent §22.3",
        ),
        case(
            "N1",
            "Prometheus disabled on the Route: configured access, usage unestablished",
            "r1",
            "legacy-route",
            answered(
                [
                    row(
                        "alice",
                        CONFIGURED,
                        unestablished,
                        0,
                        0,
                        coverage=UNKNOWN,
                        limitations=["GWM_ROUTE_PROMETHEUS_DISABLED"],
                    )
                ],
                route_limitations=["GWM_ROUTE_PROMETHEUS_DISABLED"],
            ),
            spec="replay plan N1; parent §22.2",
        ),
        case(
            "N2",
            "Not allow-listed, rejected by the gateway: no access fact, no usage",
            "r1",
            "orders-route",
            answered([row("carol", NO_FACT, unestablished, 0, 2)]),
            "carol",
            spec="replay plan N2; parent §22.4",
        ),
        case(
            "N3",
            "Unattributed upstream traffic invents no consumer row",
            "r1",
            "open-route",
            answered([], route_limitations=["GWM_UNATTRIBUTED_UPSTREAM"]),
            spec="replay plan N3; parent §22.5",
        ),
        case(
            "N4",
            "Usage on another Route is not usage of this Route",
            "r1",
            "orders-route",
            answered([row("erin", CONFIGURED, "MEASURED_ZERO", 0, 0)]),
            "erin",
            spec="replay plan N4",
        ),
        case(
            "N4b",
            "...and it is usage of the Route it happened on",
            "r1",
            "billing-route",
            answered([row("erin", CONFIGURED, "OBSERVED_USAGE", 4, 0)]),
            "erin",
            spec="replay plan N4",
        ),
        case(
            "OBS",
            "Observed usage with no matching configured access",
            "r1",
            "shared-route",
            answered([row("frank", NO_FACT, "OBSERVED_USAGE", 2, 0)]),
            spec="parent §22.4",
        ),
        case(
            "REVa",
            "After R2 the Route holds only the current allow-list",
            "r2",
            "orders-route",
            answered(
                [
                    row("alice", CONFIGURED, "MEASURED_ZERO", 0, 0),
                    row("erin", CONFIGURED, "MEASURED_ZERO", 0, 0),
                ]
            ),
            spec="parent §22.9",
        ),
        case(
            "REVb",
            "After R2 a Route removed by R2 is unknown",
            "r2",
            "billing-route",
            refusal("UNKNOWN_TARGET"),
            spec="parent §22.9",
        ),
        case(
            "REVc",
            "After R2 the new Route's usage is established",
            "r2",
            "reports-route",
            answered([row("alice", CONFIGURED, "OBSERVED_USAGE", 2, 0)]),
            "alice",
            spec="parent §22.9",
        ),
        case(
            "W-INVALID",
            "An unsettled end boundary: rows keep their identity, carry no counts",
            "r1",
            "orders-route",
            answered(
                [
                    row(
                        "alice",
                        CONFIGURED,
                        unestablished,
                        None,
                        None,
                        coverage=UNKNOWN,
                        limitations=["GWM_WINDOW_NOT_SETTLED"],
                    ),
                    row(
                        "bob",
                        CONFIGURED,
                        unestablished,
                        None,
                        None,
                        coverage=UNKNOWN,
                        limitations=["GWM_WINDOW_NOT_SETTLED"],
                    ),
                    row(
                        "carol",
                        NO_FACT,
                        unestablished,
                        None,
                        None,
                        coverage=UNKNOWN,
                        limitations=["GWM_WINDOW_NOT_SETTLED"],
                    ),
                    row(
                        "dave",
                        CONFIGURED,
                        unestablished,
                        None,
                        None,
                        coverage=UNKNOWN,
                        limitations=["GWM_WINDOW_NOT_SETTLED"],
                    ),
                    row(
                        "erin",
                        CONFIGURED,
                        unestablished,
                        None,
                        None,
                        coverage=UNKNOWN,
                        limitations=["GWM_WINDOW_NOT_SETTLED"],
                    ),
                ],
                window_valid=False,
                route_limitations=["GWM_WINDOW_NOT_SETTLED"],
            ),
            derived="the manifest of the real P1 window with end_settled set to false",
            spec="parent §22.2",
        ),
        case(
            "W-NONE",
            "A window that was never imported is refused, not synthesized",
            "r1",
            "orders-route",
            refusal("MEASUREMENT_WINDOW_NOT_AVAILABLE"),
            derived="a request whose window_end is one hour after the imported window's",
            spec="parent §22.2",
        ),
    ]


def document() -> dict[str, Any]:
    return {
        "contract": "aip-v0.7-i4-replay-expected",
        "vector_set": 1,
        "governing": [
            "docs/specifications/0.7.0/i4-decision-record.md D4",
            "docs/specifications/0.7.0/i0-acquisition-replay-plan.md §5",
        ],
        "authored": "I4.1c, by author_replay_expected.py (stdlib only), before any capture",
        "gateway_instance_id": GATEWAY,
        "environment": ENVIRONMENT,
        "traffic": {"W1": TRAFFIC_W1, "W2": TRAFFIC_W2},
        "revisions": {"R1": R1, "R2": R2},
        "consumers": CONSUMERS,
        "cases": cases(),
    }


def render() -> str:
    return json.dumps(document(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
