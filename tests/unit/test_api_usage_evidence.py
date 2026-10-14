"""v0.7.0 I3.3: properties of the evidence mode that no single oracle answer states - a ref resolves
only for the context that minted it, payloads carry no internal id, the refusal order matches the
query's, and the answer is rebuilt from the state alone. The oracle's evidence cases (E01a-c, E02a-c)
are executed by `test_v070_i3_projection_oracle.py`."""

import copy
import json
import random
from pathlib import Path
from typing import Any

from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
    EvidenceStatus,
)
from app.architecture_intelligence.api_usage_evidence import resolve_api_consumer_usage_evidence
from app.architecture_intelligence.api_usage_projection import project_api_consumer_usage
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
INTERNAL_IDS = {
    row["id"]
    for section in ("windows", "evidence", "limitations", "mapping_entries", "qualification_rows")
    for row in STATE["api_usage_v1"][section]
} | {row["id"] for row in STATE["gateway_configuration_v1"]["configured_access"]}
CONTEXT = {
    "gateway_instance_id": "gw-prod-1",
    "environment": "prod",
    "window_start": "2026-10-13T10:00:00Z",
    "window_end": "2026-10-13T10:10:00Z",
}


def target(label: str = "orders-route") -> dict[str, str]:
    return {"kind": "GATEWAY_ROUTE", "id": ROUTES[label]}


def query_refs(label: str = "orders-route", **extra: Any) -> list[str]:
    answer = project_api_consumer_usage(
        ApiConsumerUsageQueryRequest.model_validate(
            {"mode": "query", "target": target(label), **CONTEXT, **extra}
        ),
        STATE,
        snapshot=SNAPSHOT,
        producer=PRODUCER,
    )
    assert answer.data is not None
    refs = {ref for row in answer.data.rows for ref in row.evidence_refs}
    refs |= set(answer.data.window.evidence_refs)
    return sorted(refs)


def resolve(refs, label="orders-route", state=STATE, snapshot=SNAPSHOT, **extra):
    request = ApiConsumerUsageEvidenceRequest.model_validate(
        {
            "mode": "evidence",
            "snapshot_id": SNAPSHOT.snapshot_id,
            "target": target(label),
            "evidence_refs": sorted(refs),
            **CONTEXT,
            **extra,
        }
    )
    return resolve_api_consumer_usage_evidence(request, state, snapshot=snapshot, producer=PRODUCER)


def statuses(answer) -> dict[str, EvidenceStatus]:
    return {entry.ref: entry.status for entry in answer.data.entries}


def test_every_ref_a_query_emits_resolves_in_the_same_context():
    refs = query_refs()
    assert len(refs) >= 4
    answer = resolve(refs)
    assert answer.outcome is Outcome.ANSWERED and answer.limitations == []
    assert set(statuses(answer).values()) == {EvidenceStatus.RESOLVED}


def test_a_ref_does_not_resolve_in_another_target_consumer_or_snapshot_context():
    refs = query_refs()
    other_route = statuses(resolve(refs, label="orders-v2-route"))
    assert set(other_route.values()) == {EvidenceStatus.NOT_RESOLVED}, "the target is in the digest"
    consumer = next(
        row["consumer_id"]
        for row in STATE["api_usage_v1"]["qualification_rows"]
        if row["route"] == "orders-route"
    )
    filtered = resolve(refs, consumer_id=consumer)
    assert set(statuses(filtered).values()) == {EvidenceStatus.NOT_RESOLVED}
    # a ref minted for another snapshot is not in this snapshot's map: the same state under B
    foreign = resolve(refs, snapshot=OTHER, snapshot_id=OTHER.snapshot_id)
    assert set(statuses(foreign).values()) == {EvidenceStatus.NOT_RESOLVED}


def test_a_forged_ref_is_not_resolved_and_indistinguishable_from_a_cross_context_ref():
    forged = "api-evidence:" + "0" * 64
    cross = query_refs(consumer_id=STATE["gateway_configuration_v1"]["consumers"][0]["id"])
    answer = resolve([forged, *cross[:1]])
    assert statuses(answer)[forged] is EvidenceStatus.NOT_RESOLVED
    assert answer.outcome in {Outcome.PARTIAL, Outcome.NOT_ANSWERED}
    assert [item.code.value for item in answer.limitations] == ["EVIDENCE_REF_NOT_RESOLVED"]


def test_no_ref_resolves_gives_not_answered_with_data():
    answer = resolve(["api-evidence:" + "0" * 64])
    assert answer.outcome is Outcome.NOT_ANSWERED and answer.data is not None
    assert {entry.status for entry in answer.data.entries} == {EvidenceStatus.NOT_RESOLVED}


def test_entries_are_one_per_requested_ref_in_ref_order():
    refs = query_refs()
    answer = resolve(refs)
    assert [entry.ref for entry in answer.data.entries] == sorted(refs)


def test_payloads_carry_no_internal_id_and_no_canary():
    canary = DOC["worlds"]["base"]["internal_only"]["credential_canary"]
    answer = resolve(query_refs())
    text = answer.model_dump_json()
    assert canary not in text
    for internal_id in INTERNAL_IDS:
        assert internal_id not in text, internal_id


def test_refusals_follow_the_query_order_and_have_no_cursor_code():
    forged = ["api-evidence:" + "0" * 64]

    def code(answer) -> str:
        return answer.limitations[0].code.value

    stale = resolve(forged, snapshot=OTHER)
    assert code(stale) == "SNAPSHOT_NOT_AVAILABLE" and stale.data is None
    assert code(resolve(forged, window_end="2026-10-13T10:20:00Z")) == (
        "MEASUREMENT_WINDOW_NOT_AVAILABLE"
    )
    unknown = {"kind": "GATEWAY_ROUTE", "id": "gateway-route:owned:" + "0" * 64}
    request = ApiConsumerUsageEvidenceRequest.model_validate(
        {
            "mode": "evidence",
            "snapshot_id": SNAPSHOT.snapshot_id,
            "target": unknown,
            "evidence_refs": forged,
            **CONTEXT,
        }
    )
    answer = resolve_api_consumer_usage_evidence(
        request, STATE, snapshot=SNAPSHOT, producer=PRODUCER
    )
    assert code(answer) == "UNKNOWN_TARGET"
    other = resolve(forged, label="other-route")
    assert code(other) == "TARGET_NOT_IN_WINDOW_SCOPE"
    assert answer.mode == "evidence"


def test_the_answer_is_rebuilt_from_the_state_not_remembered():
    refs = query_refs()
    first = resolve(refs)
    for seed in range(3):
        shuffled = copy.deepcopy(STATE)
        for section in ("api_usage_v1", "gateway_configuration_v1"):
            for rows in shuffled[section].values():
                if isinstance(rows, list):
                    random.Random(seed).shuffle(rows)
        assert resolve(refs, state=shuffled) == first
