"""v0.8 I2b B4/B10 (unit): the R1-R7 status rule, the D9 crossing, the delivery flag, refusals and
paging of the binding picture, on small synthetic snapshot states."""

import pytest

from app.architecture_intelligence.binding_picture_contracts import (
    BindingEvidenceKind,
    BindingPictureQueryRequest,
    Crossing,
    binding_evidence_ref,
)
from app.architecture_intelligence.binding_picture_projection import project_binding_picture
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.architecture_intelligence.destination_consumer_contracts import (
    EvidenceKind,
    evidence_ref,
)
from app.architecture_intelligence.kafka_consumer_attribution import resolve_declared_service
from app.sources.owner_ids import topic_owned_id
from app.telemetry.messaging_guards import DeclaredServiceCandidate

PRODUCER = Producer(name="architecture-intelligence-platform", version="0.8.0", build_revision="t")
SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "1" * 64, model_revision="sha256:" + "1" * 64
)
ENV, B, B2 = "local", "kafka:a", "kafka:b"


def tid(broker: str, name: str) -> str:
    return topic_owned_id(
        stable_broker_id=broker, normalized_namespace_or_empty="", exact_topic_address=name
    )


def build(
    *,
    receives=(("consumer", "E1"),),
    sends=(("producer", "E1"),),
    memberships=(("ctx-c", "consumer"), ("ctx-p", "producer")),
    resolved=("consumer", "producer"),
    topics=((B, "t1"),),
    publishes=(("producer", B, "t1"),),
    groups=(("g-consumer", B, "RESOLVED", "consumer"),),
    attached=(("g-consumer", B, "t1"),),
    capture_brokers=(B,),
    lookup=(("E1", "t1"),),
    split_captures=False,
):
    """A minimal state: catalog services resolve to `service:<name>`; each attachment's
    attribution follows its group's outcome."""

    def sid(name):
        return f"service:{name}"

    def source(group, broker):
        # One capture per broker, or (split_captures) one per group with its own T.
        return f"cap:{broker}:{group}" if split_captures else f"cap:{broker}"

    group_rows = [
        {
            "id": f"c:{g}",
            "group_id": g,
            "broker_id": b,
            "environment": ENV,
            "source_instance_id": source(g, b),
        }
        for g, b, _, _ in groups
    ]
    capture_rows = (
        [
            {
                "broker_id": b,
                "environment": ENV,
                "source_instance_id": source(g, b),
                "captured_at": f"2026-10-27T1{i}:00:00Z",
                "source_revision": "rev",
            }
            for i, (g, b, _, _) in enumerate(groups)
            if b in capture_brokers
        ]
        if split_captures
        else [
            {
                "broker_id": b,
                "environment": ENV,
                "source_instance_id": source("", b),
                "captured_at": "2026-10-27T10:00:00Z",
                "source_revision": "rev",
            }
            for b in capture_brokers
        ]
    )
    outcome = {f"c:{g}": (o, s) for g, _, o, s in groups}
    attributions = []
    for i, (g, b, name) in enumerate(attached):
        o, s = outcome[f"c:{g}"]
        row = {
            "id": f"att:{i}",
            "consumer_id": f"c:{g}",
            "topic_id": tid(b, name),
            "captured_at": "2026-10-27T10:00:00Z",
            "outcome": o,
            "attachment_evidence_ids": [f"ev:{i}"],
            "mapping_entries": [{"id": f"map:{g}", "evidence_ids": ["mev"]}],
        }
        if o == "RESOLVED":
            row["service_id"] = sid(s)
        else:
            row["reason"] = "NO_MAPPING"
        attributions.append(row)
    promises = [
        {
            "id": f"p:{s}:{d}:{e}",
            "service_name": s,
            "direction": d,
            "event_id": e,
            "environment": ENV,
            "evidence_ids": ["cev"],
        }
        for d, items in (("RECEIVES", receives), ("SENDS", sends))
        for s, e in items
    ]
    return {
        "topics": [{"id": tid(b, n), "name": n} for b, n in topics],
        "kafka_topic_brokers_v1": [{"topic_id": tid(b, n), "broker_id": b} for b, n in topics],
        "relations": [
            {"type": "PUBLISHES_TO", "source_id": sid(s), "target_id": tid(b, n)}
            for s, b, n in publishes
        ],
        "event_catalog_v1": {
            "evidence": [
                {
                    "id": "cev",
                    "source_instance_id": "urn:aip:source:event-catalog:" + "a" * 64,
                    "environment": ENV,
                    "catalog_digest": "c" * 64,
                    "lookup_digest": "l" * 64,
                    "source_revision": "r",
                }
            ],
            "promises": promises,
            "memberships": [
                {"bounded_context_id": c, "service_name": s, "environment": ENV}
                for c, s in memberships
            ],
            "event_topics": [{"event_id": e, "topic": t, "environment": ENV} for e, t in lookup],
            "service_resolutions": [
                {"service_name": n, "outcome": "RESOLVED", "service_id": sid(n)} for n in resolved
            ],
        },
        "kafka_consumer_state_v1": {
            "evidence": capture_rows,
            "groups": group_rows,
            "attachments": [],
        },
        "kafka_consumer_attribution_v1": {
            "mapping_sources": [],
            "mapping_entries": [],
            "groups": [
                {
                    "id": f"c:{g}",
                    "outcome": o,
                    **({"service_id": sid(s)} if o == "RESOLVED" else {}),
                }
                for g, _, o, s in groups
            ],
            "attributions": attributions,
        },
    }


def run(state, context="ctx-c", **request):
    query = BindingPictureQueryRequest(
        mode="query", bounded_context_id=context, environment=ENV, **request
    )
    return project_binding_picture(query, state, snapshot=SNAPSHOT, producer=PRODUCER).model_dump(
        mode="json"
    )


def rows(answer):
    return answer["data"]["rows"]


def status(row):
    return (row["status"], row.get("reason"))


def test_r1_promised_and_observed():
    [row] = rows(run(build()))
    assert status(row) == ("PROMISED_AND_OBSERVED", None)
    assert row["declared_event_types"] == ["E1"] and row["promise_evidence_refs"]


def test_r2_promised_not_observed_needs_scope_not_an_attachment():
    [row] = rows(run(build(attached=())))
    assert status(row) == ("PROMISED_NOT_OBSERVED", None)
    assert row["attachment_evidence_refs"] == [] and row["captured_at"] == "2026-10-27T10:00:00Z"


def test_r3_no_row_outside_scope_or_without_capture():
    assert rows(run(build(groups=(), attached=()))) == []
    unscoped = run(build(capture_brokers=(B2,)), broker_ids=[B, B2])
    assert all(r["broker_id"] == B2 for r in rows(unscoped))
    [missing] = [i for i in unscoped["limitations"] if i["code"] == "NO_ACCEPTED_CAPTURE"]
    assert missing["message"].endswith(f": {B}")  # names the requested broker without a capture


def test_r4_observed_undeclared():
    [row] = rows(run(build(receives=())))
    assert status(row) == ("UNRESOLVED", "PROMISE_COVERAGE_MISSING")
    assert row["declared_event_types"] == [] and row["promise_evidence_refs"] == []


def test_r5_no_promise_and_no_attachment_gives_no_row():
    assert rows(run(build(receives=(), attached=()))) == []


def test_r6_names_the_group_invents_no_service_and_no_crossing():
    [row] = rows(run(build(groups=(("g-consumer", B, "UNRESOLVED", None),), receives=())))
    assert status(row) == ("UNRESOLVED", "NO_MAPPING")
    assert row["group_ids"] == ["g-consumer"] and "consumer_service_id" not in row
    assert row["crossing"] == "UNRESOLVED"


def test_r7_undeclared_topic_in_scope_has_no_topic_id():
    [row] = rows(run(build(topics=(), publishes=(), attached=())))
    assert status(row) == ("UNRESOLVED", "TOPIC_NOT_DECLARED")
    assert "topic_id" not in row and "captured_at" not in row


@pytest.mark.parametrize(
    ("context", "memberships", "expected"),
    [
        ("ctx-c", (("ctx-c", "consumer"), ("ctx-p", "producer")), Crossing.INBOUND),
        ("ctx-p", (("ctx-c", "consumer"), ("ctx-p", "producer")), Crossing.OUTBOUND),
        (
            "ctx-x",
            (("ctx-c", "consumer"), ("ctx-p", "producer"), ("ctx-x", "other")),
            Crossing.NONE,
        ),
        ("ctx-c", (("ctx-c", "consumer"), ("ctx-c", "producer")), Crossing.INSIDE),
        ("ctx-c", (("ctx-c", "consumer"),), Crossing.UNRESOLVED),  # producer without membership
    ],
)
def test_the_crossing_table(context, memberships, expected):
    [row] = rows(run(build(memberships=memberships), context=context))
    assert row["crossing"] == expected.value


def test_no_declared_producer_is_an_unresolved_crossing():
    [row] = rows(run(build(publishes=())))
    assert row["crossing"] == "UNRESOLVED" and row["producers"] == []


def test_the_delivery_flag_and_limitation_follow_the_evidence_chain():
    same = run(build())
    assert not rows(same)[0]["cross_broker_producers"]
    assert "CROSS_BROKER_DELIVERY_NOT_ESTABLISHED" not in [i["code"] for i in same["limitations"]]
    # The producer publishes on B2 (a broker of the environment); the consumer reads on B.
    off = run(
        build(
            topics=((B, "t1"), (B2, "t1")),
            publishes=(("producer", B2, "t1"),),
            capture_brokers=(B, B2),
        ),
        broker_ids=[B],
    )
    [row] = rows(off)
    assert row["cross_broker_producers"] and row["crossing"] == "INBOUND"
    assert "CROSS_BROKER_DELIVERY_NOT_ESTABLISHED" in [i["code"] for i in off["limitations"]]


def test_a_producer_on_a_broker_outside_the_environment_is_not_counted():
    state = build(topics=((B, "t1"), (B2, "t1")), publishes=(("producer", B2, "t1"),))
    [row] = rows(run(state))  # B2 has no capture or mapping source in the environment.
    assert row["producers"] == [] and row["crossing"] == "UNRESOLVED"


def test_contradicted_and_observed_not_promised_are_never_emitted():
    states = [
        build(),
        build(attached=()),
        build(receives=()),
        build(topics=(), publishes=(), attached=()),
    ]
    emitted = {r["status"] for s in states for r in rows(run(s))}
    assert emitted.isdisjoint({"CONTRADICTED", "OBSERVED_NOT_PROMISED"})


def test_always_present_limitations_and_partial_outcome():
    answer = run(build())
    assert answer["outcome"] == "PARTIAL"
    assert [i["code"] for i in answer["limitations"]] == [
        "CAPTURE_SCOPE_LIMITED",
        "EVENT_HANDLING_NOT_ESTABLISHED",
        "PRODUCER_SIDE_DECLARED_ONLY",
        "PROMISES_ASSUMED_CONFIRMED",
    ]


@pytest.mark.parametrize(
    ("state", "context", "request_extra", "code"),
    [
        ({}, "ctx-c", {}, "NO_ACCEPTED_CATALOG"),
        (None, "ctx-unknown", {}, "UNKNOWN_BOUNDED_CONTEXT"),
        ("no-capture", "ctx-c", {}, "NO_ACCEPTED_CAPTURE"),
        (None, "ctx-c", {"snapshot_id": "aip:snapshot:v1:" + "2" * 64}, "SNAPSHOT_NOT_AVAILABLE"),
    ],
)
def test_refusals(state, context, request_extra, code):
    if state is None:
        state = build()
    elif state == "no-capture":
        state = build(capture_brokers=())
    answer = run(state, context=context, **request_extra)
    assert answer["outcome"] == "NOT_ANSWERED" and answer["data"] is None
    assert [i["code"] for i in answer["limitations"]] == [code]


def test_paging_is_stable_and_the_cursor_is_bound_to_the_query():
    state = build(
        receives=(("consumer", "E1"), ("consumer", "E2")),
        lookup=(("E1", "t1"), ("E2", "t2")),
        topics=((B, "t1"), (B, "t2")),
        publishes=(("producer", B, "t1"), ("producer", B, "t2")),
    )
    first = run(state, limit=1)
    assert len(rows(first)) == 1 and "MORE_ROWS_AVAILABLE" in [
        i["code"] for i in first["limitations"]
    ]
    cursor = first["data"]["page"]["next_cursor"]
    second = run(state, limit=1, cursor=cursor)
    assert [r["topic_name"] for r in rows(first) + rows(second)] == ["t1", "t2"]
    other = run(state, context="ctx-p", limit=1, cursor=cursor)
    assert [i["code"] for i in other["limitations"]] == ["CURSOR_QUERY_MISMATCH"]


def test_binding_refs_have_their_own_domain():
    ids = ["x", "y"]
    ref = binding_evidence_ref(
        snapshot_id=SNAPSHOT.snapshot_id,
        query_digest="d" * 64,
        kind=BindingEvidenceKind.KAFKA_ATTACHMENT,
        internal_ids=ids,
    )
    other = evidence_ref(
        snapshot_id=SNAPSHOT.snapshot_id,
        query_digest="d" * 64,
        kind=EvidenceKind.KAFKA_ATTACHMENT,
        internal_ids=ids,
    )
    assert ref.startswith("binding-evidence:") and other.startswith("destination-evidence:")
    assert ref.split(":", 1)[1] != other.split(":", 1)[1]  # distinct domain, also in the hash
    assert ref == binding_evidence_ref(
        snapshot_id=SNAPSHOT.snapshot_id,
        query_digest="d" * 64,
        kind=BindingEvidenceKind.KAFKA_ATTACHMENT,
        internal_ids=list(reversed(ids)),
    )


def test_resolution_accepts_only_declared_services():
    declared = [DeclaredServiceCandidate("service:a", "a", None)]
    assert resolve_declared_service("a", None, candidates=declared, aliases={}) == (
        "service:a",
        None,
    )
    service_id, reason = resolve_declared_service(
        "not-declared", None, candidates=declared, aliases={}
    )
    assert service_id is None and reason is not None and reason.value == "SERVICE_NOT_DECLARED"


def test_two_captures_on_one_broker_are_never_collapsed():
    """Two accepted captures with disjoint allow-lists on one broker: both are capture sources, and
    each R2 row carries the T of the capture that scopes its Service (I2 §6)."""
    state = build(
        receives=(("consumer", "E1"), ("other", "E1")),
        memberships=(("ctx-c", "consumer"), ("ctx-c", "other"), ("ctx-p", "producer")),
        resolved=("consumer", "other", "producer"),
        groups=(("g-consumer", B, "RESOLVED", "consumer"), ("g-other", B, "RESOLVED", "other")),
        attached=(),
        split_captures=True,
    )
    answer = run(state)
    sources = [
        (c["source_instance_id"], c["captured_at"]) for c in answer["data"]["capture_sources"]
    ]
    assert sources == [
        (f"cap:{B}:g-consumer", "2026-10-27T10:00:00Z"),
        (f"cap:{B}:g-other", "2026-10-27T11:00:00Z"),
    ]
    times = {r["consumer_service_id"]: (r["status"], r["captured_at"]) for r in rows(answer)}
    assert times == {
        "service:consumer": ("PROMISED_NOT_OBSERVED", "2026-10-27T10:00:00Z"),
        "service:other": ("PROMISED_NOT_OBSERVED", "2026-10-27T11:00:00Z"),
    }


def test_two_groups_of_one_service_on_one_topic_keep_all_their_evidence():
    """Review of #644: two groups mapped to one Service and attached to one Topic make one row
    that carries both attachments and both mappings; differing T is not collapsed into one."""
    state = build(
        groups=(("g-a", B, "RESOLVED", "consumer"), ("g-b", B, "RESOLVED", "consumer")),
        attached=(("g-a", B, "t1"), ("g-b", B, "t1")),
    )
    [row] = rows(run(state))
    assert status(row) == ("PROMISED_AND_OBSERVED", None)
    assert row["group_ids"] == ["g-a", "g-b"]
    assert len(row["attachment_evidence_refs"]) == 2 and len(row["mapping_evidence_refs"]) == 2
    times = state["kafka_consumer_attribution_v1"]["attributions"]
    times[1]["captured_at"] = "2026-10-27T12:00:00Z"
    [row] = rows(run(state))
    assert "captured_at" not in row  # two T values: none is invented
