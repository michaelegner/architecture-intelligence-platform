"""v0.5.0 I4 slice 3 - the §13.2 runtime destination matrix for the Topic route
(`decide_messaging_destination`). The unchanged Queue guard is still covered by D1-D17 in
test_messaging_guards.py."""

import pytest

from app.telemetry.messaging_guards import (
    AMBIGUOUS_DESTINATION_IDENTITY,
    UNRESOLVED_DESTINATION_SEMANTICS,
    UNSUPPORTED_DESTINATION_SEMANTICS,
    DestinationDecision,
    PubSubDecision,
    decide_messaging_destination,
)
from app.telemetry.model import DiscoveryStatus
from app.telemetry.pubsub_resolver import DeclaredSubscriptionCandidate, DeclaredTopicCandidate
from app.telemetry.queue_resolver import DeclaredQueueCandidate

ORDERS_TOPIC = DeclaredTopicCandidate(id="topic:owned:orders", name="orders", namespace=None)
INVOICES_TOPIC = DeclaredTopicCandidate(id="topic:owned:invoices", name="invoices", namespace=None)
BILLING = DeclaredSubscriptionCandidate(
    id="subscription:owned:billing", name="billing", topic_id=ORDERS_TOPIC.id
)
CAFE = DeclaredSubscriptionCandidate(
    id="subscription:owned:cafe", name="Café", topic_id=ORDERS_TOPIC.id
)
INVOICE_AUDIT = DeclaredSubscriptionCandidate(
    id="subscription:owned:audit", name="audit", topic_id=INVOICES_TOPIC.id
)
ORDERS_QUEUE = DeclaredQueueCandidate(id="queue:owned:orders", name="orders", namespace=None)
PAYMENT_QUEUE = DeclaredQueueCandidate(id="queue:owned:payment", name="payment-q", namespace=None)


def _decide(
    *,
    destination_name="orders",
    kind=None,
    consumer=False,
    subscription_name=None,
    messaging_system=None,
    queues=(PAYMENT_QUEUE,),
    topics=(ORDERS_TOPIC, INVOICES_TOPIC),
    subscriptions=(BILLING, CAFE, INVOICE_AUDIT),
    queue_aliases=None,
    topic_aliases=None,
):
    return decide_messaging_destination(
        list(queues),
        list(topics),
        list(subscriptions),
        messaging_system=messaging_system,
        destination_name=destination_name,
        destination_kind=kind,
        is_consumer=consumer,
        subscription_name=subscription_name,
        queue_aliases=queue_aliases or {},
        topic_aliases=topic_aliases or {},
    )


def _refused(decision, reason):
    assert isinstance(decision, PubSubDecision)
    assert decision.accepted is False
    assert decision.refusal_reason == reason
    assert decision.topic_id is None and decision.subscription_id is None


# --- Topic resolution and no-minting -----------------------------------------------------------


@pytest.mark.parametrize("kind", [None, "topic", " Topic "])
def test_declared_topic_send_is_accepted(kind):
    decision = _decide(kind=kind)
    assert decision == PubSubDecision(accepted=True, topic_id=ORDERS_TOPIC.id)


def test_topic_kind_without_a_declared_topic_is_never_minted():
    """§9: `topic` may confirm a declared Topic but SHALL NOT mint one - refused with the exact
    v0.4.1 reason, so pre-I4 outcomes are byte-identical when no Topic is declared."""
    _refused(_decide(destination_name="fights", kind="topic"), UNSUPPORTED_DESTINATION_SEMANTICS)
    _refused(_decide(kind="topic", topics=()), UNSUPPORTED_DESTINATION_SEMANTICS)


def test_topic_name_only_without_kind_cannot_mint_a_topic():
    decision = _decide(destination_name="fights")
    assert isinstance(decision, DestinationDecision)  # the unchanged Queue guard's refusal
    assert decision.accepted is False
    assert decision.refusal_reason == UNRESOLVED_DESTINATION_SEMANTICS


def test_queue_and_topic_both_viable_without_kind_is_unresolved():
    _refused(_decide(queues=(ORDERS_QUEUE,)), UNRESOLVED_DESTINATION_SEMANTICS)


def test_queue_kind_preserves_the_queue_route_even_when_a_topic_shares_the_name():
    decision = _decide(kind="queue", queues=(ORDERS_QUEUE,))
    assert decision == DestinationDecision(
        accepted=True, discovery_status=DiscoveryStatus.DECLARED, queue_id=ORDERS_QUEUE.id
    )


def test_topic_kind_selects_the_topic_even_when_a_queue_shares_the_name():
    decision = _decide(kind="topic", queues=(ORDERS_QUEUE,))
    assert decision == PubSubDecision(accepted=True, topic_id=ORDERS_TOPIC.id)


@pytest.mark.parametrize("kind", ["subscription", "pubsub", "fanout", "broadcast"])
def test_subscription_and_other_pubsub_kinds_remain_unsupported(kind):
    decision = _decide(kind=kind, consumer=True, subscription_name="billing")
    assert isinstance(decision, DestinationDecision)
    assert decision.refusal_reason == UNSUPPORTED_DESTINATION_SEMANTICS


def test_queue_only_names_keep_the_unchanged_queue_guard():
    decision = _decide(destination_name="payment-q")
    assert decision == DestinationDecision(
        accepted=True, discovery_status=DiscoveryStatus.DECLARED, queue_id=PAYMENT_QUEUE.id
    )


# --- Five-step Topic precedence and type-specific aliases --------------------------------------


def test_topic_tier1_exact_name_and_matching_messaging_system():
    namespaced = DeclaredTopicCandidate(id="topic:ns", name="orders", namespace="gcp_pubsub")
    other = DeclaredTopicCandidate(id="topic:other", name="orders", namespace="servicebus")
    decision = _decide(messaging_system="gcp_pubsub", topics=(namespaced, other))
    assert decision.topic_id == "topic:ns"


def test_topic_conflicting_namespace_is_ambiguous():
    conflicting = DeclaredTopicCandidate(id="topic:c", name="orders", namespace="servicebus")
    _refused(
        _decide(messaging_system="gcp_pubsub", topics=(ORDERS_TOPIC, conflicting)),
        AMBIGUOUS_DESTINATION_IDENTITY,
    )


def test_duplicate_topic_names_are_ambiguous():
    twin = DeclaredTopicCandidate(id="topic:twin", name="orders", namespace=None)
    _refused(_decide(topics=(ORDERS_TOPIC, twin)), AMBIGUOUS_DESTINATION_IDENTITY)


def test_topic_alias_applies_only_after_no_unique_direct_match():
    decision = _decide(destination_name="orders-v2", topic_aliases={"orders-v2": ORDERS_TOPIC.id})
    assert decision == PubSubDecision(accepted=True, topic_id=ORDERS_TOPIC.id)
    # a unique direct match wins over an alias for the same name
    direct = _decide(topic_aliases={"orders": INVOICES_TOPIC.id})
    assert direct.topic_id == ORDERS_TOPIC.id


def test_topic_alias_to_a_non_candidate_is_ambiguous():
    _refused(
        _decide(destination_name="orders-v2", topic_aliases={"orders-v2": "topic:missing"}),
        AMBIGUOUS_DESTINATION_IDENTITY,
    )


def test_queue_alias_can_never_select_a_topic():
    decision = _decide(destination_name="orders-v2", queue_aliases={"orders-v2": ORDERS_TOPIC.id})
    # the Queue alias is resolved only against Queue candidates, where a Topic id is not a
    # candidate - so it is ambiguous on the Queue route, never a Topic selection
    assert decision == DestinationDecision(
        accepted=False, refusal_reason=AMBIGUOUS_DESTINATION_IDENTITY
    )


def test_topic_alias_can_never_select_a_queue():
    decision = _decide(
        destination_name="payment-v2",
        kind="queue",
        topic_aliases={"payment-v2": PAYMENT_QUEUE.id},
    )
    assert isinstance(decision, DestinationDecision)
    # kind=queue with no Queue match mints an observed-only Queue (unchanged v0.4.1 row 4) -
    # never the Queue the Topic alias names
    assert decision.queue_id != PAYMENT_QUEUE.id


# --- Subscription resolution within the resolved Topic -----------------------------------------


def test_exact_subscription_name_within_the_resolved_topic_is_accepted():
    decision = _decide(consumer=True, subscription_name="billing")
    assert decision == PubSubDecision(
        accepted=True, topic_id=ORDERS_TOPIC.id, subscription_id=BILLING.id
    )


def test_subscription_name_is_nfc_normalized():
    decision = _decide(consumer=True, subscription_name="Café")
    assert decision.subscription_id == CAFE.id


@pytest.mark.parametrize("name", ["Billing", "billing ", "BILLING"])
def test_subscription_matching_is_not_case_folded_or_trimmed(name):
    _refused(_decide(consumer=True, subscription_name=name), UNRESOLVED_DESTINATION_SEMANTICS)


@pytest.mark.parametrize("name", [None, "", 7])
def test_consumer_without_subscription_name_is_unresolved(name):
    _refused(_decide(consumer=True, subscription_name=name), UNRESOLVED_DESTINATION_SEMANTICS)


def test_subscription_of_a_different_topic_never_matches():
    _refused(_decide(consumer=True, subscription_name="audit"), UNRESOLVED_DESTINATION_SEMANTICS)


def test_duplicate_subscription_ids_under_one_topic_are_ambiguous():
    twin = DeclaredSubscriptionCandidate(
        id="subscription:twin", name="billing", topic_id=ORDERS_TOPIC.id
    )
    _refused(
        _decide(consumer=True, subscription_name="billing", subscriptions=(BILLING, twin)),
        AMBIGUOUS_DESTINATION_IDENTITY,
    )


def test_subscription_name_in_destination_name_does_not_match_a_topic():
    decision = _decide(destination_name="billing", consumer=True, subscription_name="billing")
    assert decision == DestinationDecision(
        accepted=False, refusal_reason=UNRESOLVED_DESTINATION_SEMANTICS
    )


def test_composite_destination_name_does_not_match_a_topic():
    decision = _decide(destination_name="orders/billing", kind="topic", consumer=True)
    _refused(decision, UNSUPPORTED_DESTINATION_SEMANTICS)


def test_consumer_group_is_not_an_input_to_the_guard():
    """ADR 0017 #4: the guard has no consumer-group parameter at all - consumer-group-to-
    Subscription equivalence is structurally impossible here."""
    import inspect

    assert "consumer_group" not in " ".join(
        inspect.signature(decide_messaging_destination).parameters
    )
