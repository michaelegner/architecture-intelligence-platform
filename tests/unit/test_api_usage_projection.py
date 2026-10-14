"""v0.7.0 I3.2: properties of the API usage projection that no single oracle answer states -
independence from input order, no mutation of the input, deterministic refusal precedence, bounded
pages, stable refs, and a credential that never reaches the answer. The oracle itself is executed by
`test_v070_i3_projection_oracle.py`; the worlds here are its worlds."""

import copy
import json
import random
from pathlib import Path
from typing import Any

import pytest

from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageQueryRequest,
    ApiUsageLimitationCode,
    decode_cursor,
)
from app.architecture_intelligence.api_usage_projection import (
    project_api_consumer_usage,
    refusal_answer,
)
from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef

ORACLE = (
    Path(__file__).resolve().parents[2]
    / "docs/specifications/0.7.0/i3-vectors/expected-answers.json"
)
DOC = json.loads(ORACLE.read_text(encoding="utf-8"))
STATE = DOC["worlds"]["base"]["snapshot_state"]
SNAPSHOT = SnapshotRef(**DOC["snapshots"]["A"])
OTHER = SnapshotRef(**DOC["snapshots"]["B"])
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.0", build_revision="t")
ROUTES = {row["route_id"]: row["id"] for row in STATE["gateway_configuration_v1"]["routes"]}
BASE = {
    "mode": "query",
    "gateway_instance_id": "gw-prod-1",
    "environment": "prod",
    "window_start": "2026-10-13T10:00:00Z",
    "window_end": "2026-10-13T10:10:00Z",
}


def request(target_kind: str, target_id: str, **extra: Any) -> ApiConsumerUsageQueryRequest:
    return ApiConsumerUsageQueryRequest.model_validate(
        {**BASE, "target": {"kind": target_kind, "id": target_id}, **extra}
    )


def route_request(label: str = "billing-route", **extra: Any) -> ApiConsumerUsageQueryRequest:
    return request("GATEWAY_ROUTE", ROUTES[label], **extra)


def project(req, state=STATE, snapshot=SNAPSHOT):
    return project_api_consumer_usage(req, state, snapshot=snapshot, producer=PRODUCER)


def code(answer) -> str:
    return answer.limitations[0].code.value


def shuffled(value: Any, rng: random.Random) -> Any:
    if isinstance(value, dict):
        return {key: shuffled(item, rng) for key, item in value.items()}
    if isinstance(value, list):
        items = [shuffled(item, rng) for item in value]
        rng.shuffle(items)
        return items
    return value


def test_the_answer_does_not_depend_on_the_order_of_the_input_rows():
    expected = project(request("API_OPERATION", "operation:orders-api:listOrders"))
    assert len(expected.data.rows) > 1
    for seed in range(5):
        state = shuffled(copy.deepcopy(STATE), random.Random(seed))
        assert (
            project(request("API_OPERATION", "operation:orders-api:listOrders"), state) == expected
        )


def test_the_input_state_is_not_modified():
    state = copy.deepcopy(STATE)
    project(request("APPLICATION_SERVICE", "service:orders"), state)
    assert state == STATE


def test_every_defect_at_once_yields_the_first_refusal_in_the_decision_record_order():
    cursor = project(route_request("orders-route", limit=1)).data.page.next_cursor
    assert cursor is not None
    other_target = ROUTES["orders-v2-route"]
    stale = SNAPSHOT.snapshot_id
    defects = {
        "snapshot_id": stale,
        "cursor": cursor,  # bound to another query
        "window_end": "2026-10-13T10:20:00Z",  # no such window
    }
    # snapshot first, then window, then target, then cursor
    assert code(project(request("GATEWAY_ROUTE", other_target, **defects), snapshot=OTHER)) == (
        "SNAPSHOT_NOT_AVAILABLE"
    )
    assert code(project(request("GATEWAY_ROUTE", other_target, **defects))) == (
        "MEASUREMENT_WINDOW_NOT_AVAILABLE"
    )
    unknown = {"gateway_instance_id": "gw-prod-1", "snapshot_id": stale, "cursor": cursor}
    assert code(
        project(request("GATEWAY_ROUTE", "gateway-route:owned:" + "0" * 64, **unknown))
    ) == ("UNKNOWN_TARGET")
    assert code(project(request("GATEWAY_ROUTE", ROUTES["other-route"], **unknown))) == (
        "TARGET_NOT_IN_WINDOW_SCOPE"
    )
    assert code(project(request("GATEWAY_ROUTE", other_target, **unknown))) == (
        "CURSOR_QUERY_MISMATCH"
    )


def test_a_refusal_carries_no_data_and_one_code():
    answer = project(route_request(snapshot_id=OTHER.snapshot_id))
    assert answer.data is None and answer.outcome is Outcome.NOT_ANSWERED
    assert [item.code for item in answer.limitations] == [
        ApiUsageLimitationCode.SNAPSHOT_NOT_AVAILABLE
    ]
    assert answer.snapshot == SNAPSHOT, "the refusal names the current snapshot"


def test_an_unstable_read_is_a_refusal_without_a_snapshot():
    answer = refusal_answer(PRODUCER, None, ApiUsageLimitationCode.SNAPSHOT_NOT_AVAILABLE)
    assert answer.snapshot is None and answer.data is None


def test_a_window_is_never_substituted():
    for change in ({"gateway_instance_id": "gw-prod-3"}, {"environment": "staging"}):
        answer = project(request("GATEWAY_ROUTE", ROUTES["billing-route"], **change))
        assert code(answer) == "MEASUREMENT_WINDOW_NOT_AVAILABLE"


def test_a_page_never_exceeds_its_limit_and_the_pages_cover_the_selection_once():
    whole = project(request("APPLICATION_SERVICE", "service:orders"))
    keys = [(r.consumer.id, r.gateway_route.id) for r in whole.data.rows]
    assert len(keys) >= 3
    seen: list[tuple[str, str]] = []
    cursor = None
    for _ in range(len(keys) + 1):
        extra = {"snapshot_id": SNAPSHOT.snapshot_id, "cursor": cursor} if cursor else {}
        page = project(request("APPLICATION_SERVICE", "service:orders", limit=1, **extra))
        assert len(page.data.rows) <= 1 and page.data.page.limit == 1
        seen += [(r.consumer.id, r.gateway_route.id) for r in page.data.rows]
        cursor = page.data.page.next_cursor
        if cursor is None:
            break
        assert decode_cursor(cursor).snapshot_id == SNAPSHOT.snapshot_id
    assert seen == keys


def test_refs_are_stable_and_distinguish_target_consumer_and_snapshot():
    def refs(answer) -> list[str]:
        return [ref for row in answer.data.rows for ref in row.evidence_refs]

    first = project(route_request("orders-route"))
    assert refs(first) == refs(project(route_request("orders-route")))
    assert not set(refs(first)) & set(refs(project(route_request("orders-v2-route"))))
    assert not set(refs(first)) & set(refs(project(route_request("orders-route"), snapshot=OTHER)))
    consumer = first.data.rows[0].consumer.id
    filtered = project(route_request("orders-route", consumer_id=consumer))
    assert not set(refs(first)) & set(refs(filtered)), "the consumer filter is part of the context"


def test_rows_come_only_from_the_qualification_rows_of_the_window():
    state = copy.deepcopy(STATE)
    state["api_usage_v1"]["qualification_rows"] = []
    answer = project(route_request("orders-route"), state)
    assert answer.data.rows == [] and answer.data.selected_routes
    assert answer.outcome is Outcome.ANSWERED, "empty rows with a known selection is not a refusal"


def test_the_credential_canary_never_reaches_an_answer():
    canary = DOC["worlds"]["base"]["internal_only"]["credential_canary"]
    for kind, target in (
        ("APPLICATION_SERVICE", "service:orders"),
        ("API_OPERATION", "operation:orders-api:listOrders"),
        ("GATEWAY_ROUTE", ROUTES["orders-route"]),
    ):
        assert canary not in project(request(kind, target)).model_dump_json()


@pytest.mark.parametrize("kind", ["API_OPERATION", "APPLICATION_SERVICE"])
def test_a_known_target_without_a_resolved_route_is_evaluated_not_refused(kind):
    target = "operation:orders-api:getOrder" if kind == "API_OPERATION" else "service:unused"
    state = copy.deepcopy(STATE)
    if kind == "APPLICATION_SERVICE":
        state["services"].append({"id": "service:unused", "name": "unused", "version": "1"})
    answer = project(request(kind, target), state)
    assert answer.outcome is Outcome.NOT_ANSWERED and answer.data is not None
    assert code(answer) == "NO_ROUTE_SELECTED" and answer.data.rows == []
