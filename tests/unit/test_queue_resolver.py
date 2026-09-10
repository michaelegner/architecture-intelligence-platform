from app.telemetry.model import DiscoveryStatus
from app.telemetry.queue_resolver import DeclaredQueueCandidate, resolve_queue

PAYMENT_Q = DeclaredQueueCandidate(id="queue:payment-q", name="payment-q", namespace=None)
NAMESPACED_Q = DeclaredQueueCandidate(id="queue:kafka:orders-q", name="orders-q", namespace="kafka")
DUPLICATE_A = DeclaredQueueCandidate(id="queue:events-v1", name="events", namespace=None)
DUPLICATE_B = DeclaredQueueCandidate(id="queue:events-v2", name="events", namespace=None)


def test_system_and_name_exact_match():
    result = resolve_queue(
        [NAMESPACED_Q], messaging_system="kafka", destination_name="orders-q", aliases={}
    )
    assert result.queue_id == "queue:kafka:orders-q"
    assert result.discovery_status == DiscoveryStatus.DECLARED


def test_bare_name_match_when_system_does_not_match():
    # payment-q has no namespace, so the system-qualified tier can't match it - falls through to
    # the bare-name tier, which is what actually unifies AsyncAPI-declared and OTel-observed queues
    # today (spec §27).
    result = resolve_queue(
        [PAYMENT_Q], messaging_system="azure.servicebus", destination_name="payment-q", aliases={}
    )
    assert result.queue_id == "queue:payment-q"
    assert result.discovery_status == DiscoveryStatus.DECLARED


def test_bare_name_collision_does_not_guess():
    result = resolve_queue(
        [DUPLICATE_A, DUPLICATE_B], messaging_system=None, destination_name="events", aliases={}
    )
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY


def test_alias_fallback():
    result = resolve_queue(
        [PAYMENT_Q],
        messaging_system=None,
        destination_name="legacy-payment-queue",
        aliases={"legacy-payment-queue": "queue:payment-q"},
    )
    assert result.queue_id == "queue:payment-q"
    assert result.discovery_status == DiscoveryStatus.DECLARED


def test_observed_only_mint_includes_messaging_system():
    result = resolve_queue(
        [PAYMENT_Q], messaging_system="kafka", destination_name="unknown-q", aliases={}
    )
    assert result.queue_id == "queue:kafka:unknown-q"
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY


def test_observed_only_mint_without_messaging_system():
    result = resolve_queue(
        [PAYMENT_Q], messaging_system=None, destination_name="unknown-q", aliases={}
    )
    assert result.queue_id == "queue:unknown-q"
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY


def test_missing_messaging_system_skips_tier_one_gracefully():
    # No exception, no false match - just falls straight to the bare-name tier.
    result = resolve_queue(
        [PAYMENT_Q], messaging_system=None, destination_name="payment-q", aliases={}
    )
    assert result.queue_id == "queue:payment-q"
    assert result.discovery_status == DiscoveryStatus.DECLARED


def test_topic_shaped_destination_is_still_minted_as_observed_only_queue():
    # Documents docs/real-world-validation/cross-system/decisions/queue-topic-boundary.md
    # (I4.1, motivated by Quarkus's Kafka `fights` topic finding): resolve_queue() itself has no
    # topic-vs-queue refusal path - it is a shared, low-level candidate-matching primitive, not a
    # safety decision. Once v0.4.1 I2.2 wires app.telemetry.messaging_guards.
    # decide_destination_semantics into production messaging correlation, that guard becomes the
    # sole entry point for turning a messaging destination into a Queue and does refuse this exact
    # shape (see tests/unit/test_messaging_guards.py's D3/D10/D15) - until then, and afterward for
    # any other caller, this function stays as a historical/shared-primitive characterization only.
    result = resolve_queue(
        [PAYMENT_Q], messaging_system="kafka", destination_name="events-topic", aliases={}
    )
    assert result.queue_id == "queue:kafka:events-topic"
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY
