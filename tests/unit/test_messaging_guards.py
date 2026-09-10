"""AIP v0.4.1 I2.1 - app.telemetry.messaging_guards
(docs/specifications/0.4.1/i2-messaging-semantic-guards.md §9-§17, §25-§26).

Pins the destination guard's D1-D17 matrix and the service-identity guard's S1-S16 matrix directly
against the two pure functions - ahead of I2.2's production wiring. No Neo4j required anywhere in
this file.
"""

from app.telemetry.messaging_guards import (
    AMBIGUOUS_DESTINATION_IDENTITY,
    AMBIGUOUS_SERVICE_IDENTITY,
    CONFLICTING_SERVICE_IDENTITY,
    PLACEHOLDER_SERVICE_IDENTITY,
    UNRESOLVED_DESTINATION_SEMANTICS,
    UNSUPPORTED_DESTINATION_SEMANTICS,
    decide_destination_semantics,
    decide_service_identity,
)
from app.telemetry.model import DiscoveryStatus
from app.telemetry.queue_resolver import DeclaredQueueCandidate
from app.telemetry.service_resolver import DeclaredServiceCandidate

PAYMENT_Q = DeclaredQueueCandidate(id="queue:payment-q", name="payment-q", namespace=None)
NAMESPACED_Q = DeclaredQueueCandidate(id="queue:kafka:orders-q", name="orders-q", namespace="kafka")
DUPLICATE_Q_A = DeclaredQueueCandidate(id="queue:events-v1", name="events", namespace=None)
DUPLICATE_Q_B = DeclaredQueueCandidate(id="queue:events-v2", name="events", namespace=None)
CONFLICT_Q = DeclaredQueueCandidate(id="queue:legacy:orders-q", name="orders-q", namespace="legacy")

ORDER_SVC = DeclaredServiceCandidate(
    id="service:order-service", name="OrderService", namespace=None
)
PAYMENT_SVC = DeclaredServiceCandidate(
    id="service:payment-service", name="PaymentService", namespace=None
)
NAMESPACED_SVC = DeclaredServiceCandidate(
    id="service:commerce:fraud-service", name="FraudService", namespace="commerce"
)
DUPLICATE_SVC_A = DeclaredServiceCandidate(id="service:billing-v1", name="Billing", namespace=None)
DUPLICATE_SVC_B = DeclaredServiceCandidate(id="service:billing-v2", name="Billing", namespace=None)


def _destination(
    candidates, *, messaging_system=None, destination_name="payment-q", kind=None, aliases=None
):
    return decide_destination_semantics(
        candidates,
        messaging_system=messaging_system,
        destination_name=destination_name,
        destination_kind=kind,
        aliases=aliases or {},
    )


def _service(candidates, *, service_name="FraudService", service_namespace=None, aliases=None):
    return decide_service_identity(
        candidates,
        service_name=service_name,
        service_namespace=service_namespace,
        aliases=aliases or {},
    )


# --- Destination guard: D1-D17 -------------------------------------------------------------------


def test_d1_exact_declared_queue_no_kind_is_accepted():
    result = _destination([PAYMENT_Q], destination_name="payment-q", kind=None)
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.queue_id == "queue:payment-q"


def test_d2_exact_declared_queue_with_kind_queue_is_accepted():
    result = _destination([PAYMENT_Q], destination_name="payment-q", kind="queue")
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.queue_id == "queue:payment-q"


def test_d3_exact_declared_queue_with_kind_topic_is_unsupported_refusal():
    result = _destination([PAYMENT_Q], destination_name="payment-q", kind="topic")
    assert not result.accepted
    assert result.refusal_reason == UNSUPPORTED_DESTINATION_SEMANTICS


def test_d4_no_candidate_with_kind_queue_mints_observed_only():
    result = _destination([], destination_name="unknown-q", kind="queue")
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY
    assert result.queue_id == "queue:unknown-q"


def test_d5_no_candidate_no_kind_is_unresolved_refusal():
    result = _destination([], destination_name="unknown-q", kind=None)
    assert not result.accepted
    assert result.refusal_reason == UNRESOLVED_DESTINATION_SEMANTICS


def test_d6_no_candidate_unknown_kind_is_unresolved_refusal():
    result = _destination([], destination_name="unknown-q", kind="banana")
    assert not result.accepted
    assert result.refusal_reason == UNRESOLVED_DESTINATION_SEMANTICS


def test_d7_duplicate_exact_candidates_with_kind_queue_is_ambiguous_refusal():
    result = _destination([DUPLICATE_Q_A, DUPLICATE_Q_B], destination_name="events", kind="queue")
    assert not result.accepted
    assert result.refusal_reason == AMBIGUOUS_DESTINATION_IDENTITY


def test_d8_exact_namespaced_candidate_same_system_is_accepted():
    result = _destination(
        [NAMESPACED_Q], messaging_system="kafka", destination_name="orders-q", kind=None
    )
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.queue_id == "queue:kafka:orders-q"


def test_d9_conflicting_namespace_kind_absent_is_identity_refusal():
    # CONFLICT_Q declares orders-q under namespace "legacy"; the runtime span reports a different
    # non-null system ("kafka") - a bare-name fallback MUST NOT merge across that conflict.
    result = _destination(
        [CONFLICT_Q], messaging_system="kafka", destination_name="orders-q", kind=None
    )
    assert not result.accepted
    assert result.refusal_reason == AMBIGUOUS_DESTINATION_IDENTITY


def test_d10_conflicting_namespace_kind_queue_is_ambiguous_not_a_parallel_mint():
    # Explicit kind=queue proves Queue semantics but does not resolve the conflicting identity -
    # it must not fall through to minting an unrelated observed-only Queue either.
    result = _destination(
        [CONFLICT_Q], messaging_system="kafka", destination_name="orders-q", kind="queue"
    )
    assert not result.accepted
    assert result.refusal_reason == AMBIGUOUS_DESTINATION_IDENTITY


def test_d11_unnamespaced_declared_candidate_with_system_present_is_accepted():
    result = _destination(
        [PAYMENT_Q], messaging_system="azure.servicebus", destination_name="payment-q", kind=None
    )
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.queue_id == "queue:payment-q"


def test_d12_valid_alias_no_kind_is_accepted():
    result = _destination(
        [PAYMENT_Q],
        destination_name="legacy-payment-queue",
        kind=None,
        aliases={"legacy-payment-queue": "queue:payment-q"},
    )
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.queue_id == "queue:payment-q"


def test_d13_alias_to_absent_candidate_with_kind_queue_is_ambiguous_refusal():
    result = _destination(
        [PAYMENT_Q],
        destination_name="dangling-alias",
        kind="queue",
        aliases={"dangling-alias": "queue:does-not-exist"},
    )
    assert not result.accepted
    assert result.refusal_reason == AMBIGUOUS_DESTINATION_IDENTITY


def test_d14_destination_name_content_does_not_classify_semantics():
    # "events-topic" contains the substring "topic", but only the kind attribute is semantic
    # evidence - an explicit kind=queue still authorizes an observed-only mint.
    result = _destination([], destination_name="events-topic", kind="queue")
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY
    assert result.queue_id == "queue:events-topic"


def test_d15_ordinary_name_with_kind_topic_is_unsupported_refusal():
    result = _destination([], messaging_system="kafka", destination_name="orders-q", kind="topic")
    assert not result.accepted
    assert result.refusal_reason == UNSUPPORTED_DESTINATION_SEMANTICS


def test_d16_kafka_system_alone_with_no_kind_and_no_declaration_is_unresolved_refusal():
    result = _destination([], messaging_system="kafka", destination_name="unknown-q", kind=None)
    assert not result.accepted
    assert result.refusal_reason == UNRESOLVED_DESTINATION_SEMANTICS


def test_d17_candidate_order_does_not_affect_the_result():
    forward = _destination([DUPLICATE_Q_A, DUPLICATE_Q_B], destination_name="events", kind="queue")
    reversed_ = _destination(
        [DUPLICATE_Q_B, DUPLICATE_Q_A], destination_name="events", kind="queue"
    )
    assert forward == reversed_


# --- Service-identity guard: S1-S16 ---------------------------------------------------------------


def test_s1_exact_declared_service_no_namespace_is_accepted():
    result = _service([ORDER_SVC, PAYMENT_SVC], service_name="OrderService", service_namespace=None)
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.service_id == "service:order-service"


def test_s2_exact_namespaced_service_with_namespace_is_accepted():
    result = _service([NAMESPACED_SVC], service_name="FraudService", service_namespace="commerce")
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.service_id == "service:commerce:fraud-service"


def test_s3_unnamespaced_declared_service_with_runtime_namespace_is_accepted():
    # No same-name namespaced candidate exists at all, so a supplied runtime namespace makes no
    # contradictory assertion against the unnamespaced declared candidate.
    result = _service([ORDER_SVC], service_name="OrderService", service_namespace="prod")
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.service_id == "service:order-service"


def test_s4_namespaced_declared_service_with_different_namespace_is_conflicting_refusal():
    result = _service([NAMESPACED_SVC], service_name="FraudService", service_namespace="warehouse")
    assert not result.accepted
    assert result.refusal_reason == CONFLICTING_SERVICE_IDENTITY


def test_s5_duplicate_exact_name_candidates_no_namespace_is_ambiguous_refusal():
    result = _service(
        [DUPLICATE_SVC_A, DUPLICATE_SVC_B], service_name="Billing", service_namespace=None
    )
    assert not result.accepted
    assert result.refusal_reason == AMBIGUOUS_SERVICE_IDENTITY


def test_s6_valid_alias_to_one_declared_candidate_is_accepted():
    result = _service(
        [ORDER_SVC],
        service_name="legacy-order-svc",
        service_namespace=None,
        aliases={"legacy-order-svc": "service:order-service"},
    )
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.DECLARED
    assert result.service_id == "service:order-service"


def test_s7_alias_to_absent_candidate_is_ambiguous_refusal():
    result = _service(
        [ORDER_SVC],
        service_name="dangling-alias",
        service_namespace=None,
        aliases={"dangling-alias": "service:does-not-exist"},
    )
    assert not result.accepted
    assert result.refusal_reason == AMBIGUOUS_SERVICE_IDENTITY


def test_s8_distinctive_undeclared_name_mints_observed_only():
    result = _service([], service_name="FraudService", service_namespace=None)
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY
    assert result.service_id == "service:fraudservice"


def test_s9_hero_finding_name_mints_observed_only():
    # v0.4.0's hero finding (OrderService -> LegacyPricingService = OBSERVED_ONLY) is an HTTP-path
    # fact, not messaging - but the predicate itself must accept this exact name regardless, since
    # it's a distinctive, non-placeholder identity by construction (spec §17).
    result = _service([], service_name="LegacyPricingService", service_namespace=None)
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY
    assert result.service_id == "service:legacypricingservice"


def test_s10_unknown_service_is_placeholder_refusal():
    result = _service([], service_name="unknown_service", service_namespace=None)
    assert not result.accepted
    assert result.refusal_reason == PLACEHOLDER_SERVICE_IDENTITY


def test_s11_unknown_service_case_and_whitespace_variants_are_placeholder_refusals():
    for variant in ("UNKNOWN_SERVICE", "  unknown_service  ", "Unknown-Service", "unknownservice"):
        result = _service([], service_name=variant, service_namespace=None)
        assert not result.accepted, variant
        assert result.refusal_reason == PLACEHOLDER_SERVICE_IDENTITY, variant


def test_s12_unknown_service_with_process_suffix_is_placeholder_refusal():
    result = _service([], service_name="unknown_service:python", service_namespace=None)
    assert not result.accepted
    assert result.refusal_reason == PLACEHOLDER_SERVICE_IDENTITY


def test_s13_blank_or_punctuation_only_value_is_placeholder_refusal():
    for value in ("", "   ", "###"):
        result = _service([], service_name=value, service_namespace=None)
        assert not result.accepted, repr(value)
        assert result.refusal_reason == PLACEHOLDER_SERVICE_IDENTITY, repr(value)


def test_s14_distinctive_name_with_namespace_preserves_namespace_in_the_minted_id():
    result = _service([], service_name="FraudService", service_namespace="commerce")
    assert result.accepted
    assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY
    assert result.service_id == "service:commerce:fraudservice"


def test_s15_candidate_order_does_not_affect_the_result():
    forward = _service(
        [DUPLICATE_SVC_A, DUPLICATE_SVC_B], service_name="Billing", service_namespace=None
    )
    reversed_ = _service(
        [DUPLICATE_SVC_B, DUPLICATE_SVC_A], service_name="Billing", service_namespace=None
    )
    assert forward == reversed_


def test_s16_identical_identity_inputs_produce_the_same_canonical_service_id():
    # service.instance.id is never a parameter here at all (spec §13) - two spans from different
    # runtime instances reporting the same name/namespace always resolve to the same Service id.
    first = _service([], service_name="FraudService", service_namespace="commerce")
    second = _service([], service_name="FraudService", service_namespace="commerce")
    assert first.service_id == second.service_id == "service:commerce:fraudservice"


# --- Determinism/robustness beyond the named matrices ---------------------------------------------


def test_destination_kind_is_case_and_whitespace_insensitive():
    for kind in ("QUEUE", " queue ", "Queue"):
        result = _destination([], destination_name="q", kind=kind)
        assert result.accepted, kind
        assert result.discovery_status == DiscoveryStatus.OBSERVED_ONLY, kind


def test_unsupported_destination_kinds_are_all_refused():
    for kind in ("topic", "subscription", "pubsub", "publish-subscribe", "fanout", "broadcast"):
        result = _destination([PAYMENT_Q], destination_name="payment-q", kind=kind)
        assert not result.accepted, kind
        assert result.refusal_reason == UNSUPPORTED_DESTINATION_SEMANTICS, kind


def test_non_string_destination_kind_is_unresolved_refusal():
    result = _destination([], destination_name="unknown-q", kind=123)
    assert not result.accepted
    assert result.refusal_reason == UNRESOLVED_DESTINATION_SEMANTICS
