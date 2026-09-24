"""v0.5.0 I4 slice 4 (spec §12.2-§12.5): Topic/Subscription routes in the pure dependency
projection. Queue/HTTP behavior is covered by `test_architecture_intelligence_dependency_projection`;
this module pins only the Pub/Sub rows of §12.3 and the Queue/HTTP claim-id compatibility of §12.4.
"""

import hashlib
import json
import random
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from app.analysis.runtime import ServiceTelemetryCoverage
from app.architecture_intelligence import dependency_projection as proj
from app.architecture_intelligence.contracts import (
    Coverage,
    DeliveryKind,
    DeliveryRelationType,
    DestinationResolution,
    EntityType,
    LimitationCode,
    Qualification,
)
from evaluation.architecture_answers.reference import identities

ENVIRONMENT = "demo"
WINDOW_START = datetime(2026, 8, 26, tzinfo=UTC)
WINDOW_END = datetime(2026, 8, 27, tzinfo=UTC)
INSIDE_WINDOW = datetime(2026, 8, 26, 12, tzinfo=UTC)

SUBJECT = "service:orders"
TOPIC = "topic:owned:" + "a" * 64
OTHER_TOPIC = "topic:owned:" + "d" * 64
BILLING = "subscription:owned:" + "b" * 64
SHIPPING = "subscription:owned:" + "c" * 64

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "architecture_intelligence"
    / "v0.5"
    / "architecture-answer.schema.json"
)


def _declared(*eids: str) -> dict:
    return {
        eid: {"evidence_type": "DECLARED", "environment": None, "last_seen": None} for eid in eids
    }


def _observed(*eids: str) -> dict:
    return {
        eid: {"evidence_type": "OBSERVED", "environment": ENVIRONMENT, "last_seen": INSIDE_WINDOW}
        for eid in eids
    }


def _coverage(*, http=False, messaging=False) -> ServiceTelemetryCoverage:
    return ServiceTelemetryCoverage(
        service_id=SUBJECT,
        service_name="orders",
        environment=ENVIRONMENT,
        since=WINDOW_START,
        http_observed=http,
        messaging_observed=messaging,
        spans_observed=http or messaging,
    )


def _publish(topic_id: str = TOPIC, evidence_ids=("p1",)) -> dict:
    return {
        "topic_id": topic_id,
        "topic_name": "orders",
        "protocol": "googlepubsub",
        "namespace": None,
        "evidence_ids": list(evidence_ids),
    }


def _subscription(sub_id: str, name: str, evidence_ids, topic_id: str = TOPIC) -> dict:
    return {
        "topic_id": topic_id,
        "subscription_id": sub_id,
        "subscription_name": name,
        "protocol": "googlepubsub",
        "namespace": None,
        "evidence_ids": list(evidence_ids),
    }


def _receive(sub_id: str, consumer: str, evidence_ids) -> dict:
    return {
        "subscription_id": sub_id,
        "consumer_id": f"service:{consumer}",
        "consumer_name": consumer,
        "evidence_ids": list(evidence_ids),
    }


def _project(rows: dict, *, coverage=None) -> proj.ProjectionResult:
    base_rows = {
        "calls": [],
        "provides": [],
        "sends": [],
        "receives": [],
        "publishes": [],
        "subscriptions": [],
        "subscription_receives": [],
        "evidence": {},
        "coverage": coverage or _coverage(),
    }
    base_rows.update(rows)
    return proj.project_service_dependencies(
        base_rows,
        service_id=SUBJECT,
        service_name="orders",
        environment=ENVIRONMENT,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        coverage_enabled=True,
    )


def _fanout_rows() -> dict:
    return {
        "publishes": [_publish()],
        "subscriptions": [
            _subscription(BILLING, "billing", ["so-b"]),
            _subscription(SHIPPING, "shipping", ["so-s"]),
        ],
        "subscription_receives": [
            _receive(BILLING, "billing", ["r-b"]),
            _receive(SHIPPING, "shipping", ["r-s"]),
        ],
        "evidence": _declared("p1", "so-b", "so-s", "r-b", "r-s"),
    }


def _assert_schema_valid(result: proj.ProjectionResult) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    claim_schema = {"$ref": "#/$defs/DependencyClaim", "$defs": schema["$defs"]}
    for claim in result.claims:
        jsonschema.validate(instance=claim.model_dump(mode="json"), schema=claim_schema)


# --- §12.3 projection rows ----------------------------------------------------------------------


def test_topic_without_usable_subscription_falls_back_to_the_topic():
    result = _project({"publishes": [_publish()], "evidence": _declared("p1")})

    [claim] = result.claims
    assert claim.object.id == TOPIC
    assert claim.object.type == EntityType.TOPIC
    assert claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    assert claim.delivery.kind == DeliveryKind.ASYNC_MESSAGE
    assert claim.delivery.relation_type == DeliveryRelationType.PUBLISHES_TO
    assert claim.delivery.via.id == TOPIC
    assert claim.delivery.via.protocol == "googlepubsub"
    assert claim.delivery.subscription is None
    assert claim.evidence_refs == ["p1"]
    assert claim.resolution_evidence_refs == []
    [limitation] = result.limitations
    assert limitation.code == LimitationCode.UNRESOLVED_IDENTITY
    assert limitation.claim_ids == [claim.claim_id]
    assert "direct topic target" in limitation.message
    _assert_schema_valid(result)


def test_subscription_without_evidenced_consumer_falls_back_to_the_subscription():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [_subscription(BILLING, "billing", ["so-b"])],
            "evidence": _declared("p1", "so-b"),
        }
    )

    [claim] = result.claims
    assert claim.object.id == BILLING
    assert claim.object.type == EntityType.SUBSCRIPTION
    assert claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    assert claim.delivery.via.id == TOPIC
    assert claim.delivery.subscription.id == BILLING
    # frozen contract: a DIRECT_TARGET_FALLBACK claim never carries resolution evidence
    assert claim.resolution_evidence_refs == []
    [limitation] = result.limitations
    assert limitation.code == LimitationCode.UNRESOLVED_IDENTITY
    assert limitation.claim_ids == [claim.claim_id]
    assert "direct subscription target" in limitation.message
    _assert_schema_valid(result)


def test_one_consumer_resolves_the_service_through_its_subscription_route():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [_subscription(BILLING, "billing", ["so-b"])],
            "subscription_receives": [_receive(BILLING, "billing", ["r-b"])],
            "evidence": _declared("p1", "so-b", "r-b"),
        }
    )

    [claim] = result.claims
    assert claim.object.id == "service:billing"
    assert claim.object.type == EntityType.SERVICE
    assert claim.destination_resolution == DestinationResolution.RESOLVED_SERVICE
    assert claim.delivery.via.id == TOPIC
    assert claim.delivery.subscription.id == BILLING
    assert claim.delivery.subscription.name == "billing"
    assert claim.evidence_refs == ["p1"]
    assert claim.resolution_evidence_refs == ["r-b", "so-b"]
    assert result.limitations == []
    _assert_schema_valid(result)


def test_two_subscriptions_are_two_distinct_routed_claims():
    result = _project(_fanout_rows())

    assert [(c.object.id, c.delivery.subscription.id) for c in result.claims] == [
        ("service:billing", BILLING),
        ("service:shipping", SHIPPING),
    ]
    assert len({c.claim_id for c in result.claims}) == 2
    # evidence for one Subscription never reaches its sibling's claim
    billing, shipping = result.claims
    assert billing.resolution_evidence_refs == ["r-b", "so-b"]
    assert shipping.resolution_evidence_refs == ["r-s", "so-s"]
    _assert_schema_valid(result)


def test_same_consumer_on_two_subscriptions_yields_two_claims():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [
                _subscription(BILLING, "billing", ["so-b"]),
                _subscription(SHIPPING, "shipping", ["so-s"]),
            ],
            "subscription_receives": [
                _receive(BILLING, "worker", ["r-b"]),
                _receive(SHIPPING, "worker", ["r-s"]),
            ],
            "evidence": _declared("p1", "so-b", "so-s", "r-b", "r-s"),
        }
    )

    assert [c.object.id for c in result.claims] == ["service:worker", "service:worker"]
    assert {c.delivery.subscription.id for c in result.claims} == {BILLING, SHIPPING}
    assert len({c.claim_id for c in result.claims}) == 2


def test_multiple_instances_of_one_service_collapse_with_evidence_union():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [_subscription(BILLING, "billing", ["so-b"])],
            "subscription_receives": [
                _receive(BILLING, "billing", ["r-1"]),
                _receive(BILLING, "billing", ["r-2"]),
            ],
            "evidence": _declared("p1", "so-b", "r-1", "r-2"),
        }
    )

    [claim] = result.claims
    assert claim.resolution_evidence_refs == ["r-1", "r-2", "so-b"]


def test_distinct_services_on_one_subscription_are_competing_consumers_sharing_the_route():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [_subscription(BILLING, "billing", ["so-b"])],
            "subscription_receives": [
                _receive(BILLING, "billing-a", ["r-a"]),
                _receive(BILLING, "billing-b", ["r-b"]),
            ],
            "evidence": _declared("p1", "so-b", "r-a", "r-b"),
        }
    )

    assert [c.object.id for c in result.claims] == ["service:billing-a", "service:billing-b"]
    assert {c.delivery.subscription.id for c in result.claims} == {BILLING}
    assert all(
        c.destination_resolution == DestinationResolution.RESOLVED_SERVICE for c in result.claims
    )
    assert result.limitations == []


def test_dangling_subscription_of_evidence_is_not_a_usable_route():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [_subscription(BILLING, "billing", ["missing"])],
            "subscription_receives": [_receive(BILLING, "billing", ["r-b"])],
            "evidence": _declared("p1", "r-b"),
        }
    )

    [claim] = result.claims
    assert claim.object.id == TOPIC
    assert claim.delivery.subscription is None


def test_consumer_with_dangling_evidence_leaves_the_subscription_unresolved():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [_subscription(BILLING, "billing", ["so-b"])],
            "subscription_receives": [_receive(BILLING, "billing", ["missing"])],
            "evidence": _declared("p1", "so-b"),
        }
    )

    [claim] = result.claims
    assert claim.object.id == BILLING
    assert claim.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK


def test_subscription_rows_are_scoped_to_their_own_topic():
    result = _project(
        {
            "publishes": [_publish()],
            "subscriptions": [_subscription(BILLING, "billing", ["so-b"], topic_id=OTHER_TOPIC)],
            "evidence": _declared("p1", "so-b"),
        }
    )

    [claim] = result.claims
    assert claim.object.id == TOPIC


def test_publish_without_any_evidence_creates_no_claim():
    result = _project({"publishes": [_publish(evidence_ids=("missing",))]})

    assert result.claims == []
    [limitation] = result.limitations
    assert limitation.code == LimitationCode.INSUFFICIENT_EVIDENCE
    assert limitation.claim_ids == []
    assert "-PUBLISHES_TO->" in limitation.message


# --- §12.5 qualification --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("coverage", "expected"),
    [
        (_coverage(messaging=True), Coverage.SUFFICIENT),
        (_coverage(http=True), Coverage.PARTIAL),
        (_coverage(), Coverage.NONE),
    ],
)
def test_declared_only_publish_is_not_observed_under_the_messaging_coverage_rule(
    coverage, expected
):
    result = _project(_fanout_rows(), coverage=coverage)

    assert {c.qualification for c in result.claims} == {Qualification.NOT_OBSERVED_IN_WINDOW}
    assert {c.coverage for c in result.claims} == {expected}


def test_observed_publish_confirms_every_route_from_publisher_evidence_only():
    rows = _fanout_rows()
    rows["publishes"] = [_publish(evidence_ids=("p1", "p-obs"))]
    rows["evidence"] = {**rows["evidence"], **_observed("p-obs")}

    result = _project(rows, coverage=_coverage(messaging=True))

    assert {c.qualification for c in result.claims} == {Qualification.CONFIRMED}
    assert all(c.evidence_refs == ["p-obs", "p1"] for c in result.claims)


def test_observed_consumer_evidence_stays_on_its_own_route_and_does_not_qualify():
    rows = _fanout_rows()
    rows["subscription_receives"] = [
        _receive(BILLING, "billing", ["r-b", "r-b-obs"]),
        _receive(SHIPPING, "shipping", ["r-s"]),
    ]
    rows["evidence"] = {**rows["evidence"], **_observed("r-b-obs")}

    result = _project(rows, coverage=_coverage(messaging=True))

    billing, shipping = result.claims
    assert "r-b-obs" in billing.resolution_evidence_refs
    assert "r-b-obs" not in shipping.resolution_evidence_refs
    assert "r-b-obs" not in billing.evidence_refs
    # decision 1: qualification is publisher-only, same as Queue
    assert billing.qualification == shipping.qualification == Qualification.NOT_OBSERVED_IN_WINDOW


def test_projection_is_independent_of_row_order():
    rows = _fanout_rows()
    rows["subscription_receives"].append(_receive(BILLING, "billing-b", ["r-b2"]))
    rows["evidence"] = {**rows["evidence"], **_declared("r-b2")}
    expected = _project(rows)

    rng = random.Random(4)
    for _ in range(10):
        shuffled = {key: list(value) for key, value in rows.items() if isinstance(value, list)}
        for value in shuffled.values():
            rng.shuffle(value)
        assert _project({**rows, **shuffled}) == expected


# --- §12.4 claim identity -------------------------------------------------------------------------


def _five_field_claim_id(**payload: str) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "aip:claim:v1:" + hashlib.sha256(raw.encode()).hexdigest()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "subject_id": "service:order-service",
            "predicate": "DIRECT_DEPENDENCY",
            "object_id": "service:product-service",
            "delivery_kind": "SYNC_HTTP",
            "delivery_via_id": "operation:product-service:GET:/products/{id}",
        },
        {
            "subject_id": "service:order-service",
            "predicate": "DIRECT_DEPENDENCY",
            "object_id": "service:payment-service",
            "delivery_kind": "ASYNC_MESSAGE",
            "delivery_via_id": "queue:asb:commerce:payment-q",
        },
    ],
)
def test_http_and_queue_claim_ids_are_the_unchanged_five_field_payload(payload):
    assert proj.compute_claim_id(**payload) == _five_field_claim_id(**payload)


def test_topic_fallback_claim_id_omits_subscription_id_entirely():
    [claim] = _project({"publishes": [_publish()], "evidence": _declared("p1")}).claims

    assert claim.claim_id == _five_field_claim_id(
        subject_id=SUBJECT,
        predicate="DIRECT_DEPENDENCY",
        object_id=TOPIC,
        delivery_kind="ASYNC_MESSAGE",
        delivery_via_id=TOPIC,
    )


def test_subscription_route_claim_id_binds_the_subscription_id():
    billing, _shipping = _project(_fanout_rows()).claims

    raw = json.dumps(
        {
            "subject_id": SUBJECT,
            "predicate": "DIRECT_DEPENDENCY",
            "object_id": "service:billing",
            "delivery_kind": "ASYNC_MESSAGE",
            "delivery_via_id": TOPIC,
            "subscription_id": BILLING,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert billing.claim_id == "aip:claim:v1:" + hashlib.sha256(raw.encode()).hexdigest()
    assert billing.claim_id == identities.claim_id(
        subject_id=SUBJECT,
        predicate="DIRECT_DEPENDENCY",
        object_id="service:billing",
        delivery_kind="ASYNC_MESSAGE",
        delivery_via_id=TOPIC,
        subscription_id=BILLING,
    )
