"""v0.5.0 I4 slice 3 - composed runtime Topic/Subscription qualification through
`correlate_queue_observations`/`adapt` (§9, §13.2). Queue C1-C17 stay in test_adapter.py."""

import itertools

import pytest

from app.telemetry.adapter import adapt, correlate_queue_observations
from app.telemetry.messaging_guards import (
    AMBIGUOUS_SERVICE_IDENTITY,
    PLACEHOLDER_SERVICE_IDENTITY,
    UNRESOLVED_DESTINATION_SEMANTICS,
)
from app.telemetry.model import ObservedOnlyEntity
from app.telemetry.pubsub_resolver import DeclaredSubscriptionCandidate, DeclaredTopicCandidate
from app.telemetry.service_resolver import DeclaredServiceCandidate
from tests.unit.test_adapter import SERVICE_CANDIDATES, _span

ORDERS_TOPIC = DeclaredTopicCandidate(id="topic:owned:orders", name="orders", namespace=None)
BILLING = DeclaredSubscriptionCandidate(
    id="subscription:owned:billing", name="billing", topic_id=ORDERS_TOPIC.id
)


def _correlate(spans, *, service_candidates=SERVICE_CANDIDATES, **kwargs):
    return correlate_queue_observations(
        spans,
        service_candidates=service_candidates,
        queue_candidates=[],
        service_aliases={},
        queue_aliases={},
        topic_candidates=[ORDERS_TOPIC],
        subscription_candidates=[BILLING],
        **kwargs,
    )


def _messaging_span(operation, trace="a", **attributes):
    return _span(
        trace_id=trace * 32,
        attributes={
            "messaging.operation.type": operation,
            "messaging.destination.name": "orders",
            **attributes,
        },
    )


def test_publish_to_declared_topic_yields_one_publishes_to_fact_and_no_minted_entities():
    batch = _correlate([_messaging_span("send")])
    [fact] = batch.facts
    assert (fact.subject_id, fact.relation_type, fact.object_id) == (
        "service:order-service",
        "PUBLISHES_TO",
        ORDERS_TOPIC.id,
    )
    assert fact.evidence.correlation_mode == "MESSAGING_SEND"
    assert batch.entities == []
    assert batch.unresolved == []


@pytest.mark.parametrize(
    ("operation", "mode"), [("receive", "MESSAGING_RECEIVE"), ("process", "MESSAGING_PROCESS")]
)
def test_consumer_with_declared_subscription_yields_receives_from_subscription(operation, mode):
    batch = _correlate(
        [_messaging_span(operation, **{"messaging.destination.subscription.name": "billing"})]
    )
    [fact] = batch.facts
    assert (fact.relation_type, fact.object_id) == ("RECEIVES_FROM", BILLING.id)
    assert fact.evidence.correlation_mode == mode
    assert batch.entities == []


@pytest.mark.parametrize(
    "attributes",
    [
        {},  # no subscription name at all
        {"messaging.consumer.group.name": "billing"},  # consumer group only
        {
            "messaging.consumer.group.name": "billing",
            "messaging.destination.subscription.name": "shipping",
        },
    ],
)
def test_consumer_without_matching_subscription_records_nothing(attributes):
    batch = _correlate([_messaging_span("receive", **attributes)])
    assert batch.facts == [] and batch.entities == []
    assert [u.reason for u in batch.unresolved] == [UNRESOLVED_DESTINATION_SEMANTICS]


def test_consumer_group_equal_to_subscription_name_is_still_not_an_implicit_match():
    batch = _correlate([_messaging_span("receive", **{"messaging.consumer.group.name": "billing"})])
    assert batch.facts == []


@pytest.mark.parametrize(
    ("service_name", "candidates", "reason"),
    [
        ("unknown_service:python", SERVICE_CANDIDATES, PLACEHOLDER_SERVICE_IDENTITY),
        (
            "Billing",
            [
                DeclaredServiceCandidate(id="service:a", name="Billing", namespace=None),
                DeclaredServiceCandidate(id="service:b", name="Billing", namespace=None),
            ],
            AMBIGUOUS_SERVICE_IDENTITY,
        ),
    ],
)
def test_placeholder_or_ambiguous_service_creates_zero_pubsub_fact(
    service_name, candidates, reason
):
    span = _messaging_span("send").model_copy(update={"service_name": service_name})
    batch = _correlate([span], service_candidates=candidates)
    assert batch.facts == [] and batch.entities == []
    assert [u.reason for u in batch.unresolved] == [reason]


@pytest.mark.parametrize(
    "system",
    ["gcp_pubsub", "servicebus"],
)
def test_gcp_and_asb_consumer_shapes_carry_topic_and_subscription_separately(system):
    """§9/§13.2: the current conventions put the Topic in messaging.destination.name and the
    Subscription in messaging.destination.subscription.name for both GCP Pub/Sub and ASB."""
    span = _messaging_span(
        "process",
        **{
            "messaging.system": system,
            "messaging.destination.subscription.name": "billing",
        },
    )
    [fact] = _correlate([span]).facts
    assert (fact.relation_type, fact.object_id) == ("RECEIVES_FROM", BILLING.id)


def test_unsupported_operation_keys_remain_unrecognized_on_the_topic_route():
    span = _span(
        attributes={
            "messaging.operation": "publish",  # legacy key, not messaging.operation.type
            "messaging.destination.name": "orders",
        }
    )
    batch = _correlate([span])
    assert batch.facts == [] and batch.unresolved == []


def test_span_order_has_no_semantic_effect():
    spans = [
        _messaging_span("send", trace="a"),
        _messaging_span(
            "receive", trace="b", **{"messaging.destination.subscription.name": "billing"}
        ),
        _messaging_span("receive", trace="c"),
    ]
    baseline = None
    for permutation in itertools.permutations(spans):
        batch = _correlate(list(permutation))
        key = (
            sorted((f.relation_type, f.object_id, f.trace_id) for f in batch.facts),
            sorted((u.trace_id, u.reason) for u in batch.unresolved),
        )
        baseline = baseline or key
        assert key == baseline


def test_adapt_threads_topic_candidates_and_never_mints_pubsub_entities():
    batch = adapt(
        [_messaging_span("send")],
        service_candidates=SERVICE_CANDIDATES,
        operation_candidates=[],
        queue_candidates=[],
        service_aliases={},
        queue_aliases={},
        topic_candidates=[ORDERS_TOPIC],
        subscription_candidates=[BILLING],
    )
    assert [f.relation_type for f in batch.facts] == ["PUBLISHES_TO"]
    assert all(e.label in {"Service", "Operation", "Queue"} for e in batch.entities)


def test_observed_only_entity_label_structurally_excludes_topic_and_subscription():
    from typing import get_args

    assert set(get_args(ObservedOnlyEntity.model_fields["label"].annotation)) == {
        "Service",
        "Operation",
        "Queue",
    }
