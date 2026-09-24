"""Cross-checks the evaluator-owned reference implementation (authoring-time only, never imported
by the live loader/runner/comparator) against the real production functions it must independently
agree with - not because the live path calls it, but because a scenario author trusts its printed
literals when freezing expected_answer.json (I1.4 review finding #1)."""

from datetime import UTC, datetime

import pytest

from app.architecture_intelligence import observation_context as real_observation_context
from app.architecture_intelligence.dependency_projection import compute_claim_id as real_claim_id
from app.canonical import ids as real_ids
from evaluation.architecture_answers.reference import canonical_json, identities
from evaluation.architecture_answers.reference.__main__ import main as reference_main

_ENVIRONMENT = "test"
_WINDOW_START = datetime(2026, 8, 26, tzinfo=UTC)
_WINDOW_END = datetime(2026, 8, 27, tzinfo=UTC)


def test_context_id_matches_the_real_implementation():
    real = real_observation_context.compute_context_id(_ENVIRONMENT, _WINDOW_START, _WINDOW_END)
    reference = identities.context_id(
        environment=_ENVIRONMENT, window_start=_WINDOW_START, window_end=_WINDOW_END
    )
    assert reference == real


def test_declared_evidence_id_matches_the_real_implementation():
    assert identities.declared_evidence_id("OPENAPI", "product-service") == real_ids.evidence_id(
        "OPENAPI", "product-service"
    )
    assert identities.declared_evidence_id(
        "MANIFEST", "order-service", "rev1"
    ) == real_ids.evidence_id("MANIFEST", "order-service", "rev1")


def test_observed_evidence_id_matches_the_real_implementation():
    bucket_start = datetime(2026, 8, 26, tzinfo=UTC)
    real = real_ids.observed_evidence_id(
        "test", bucket_start, "service:order-service", "CALLS", "operation:x:GET:/x"
    )
    reference = identities.observed_evidence_id(
        environment="test",
        bucket_start=bucket_start,
        subject_id="service:order-service",
        relation_type="CALLS",
        object_id="operation:x:GET:/x",
    )
    assert reference == real


def test_claim_id_matches_the_real_implementation():
    real = real_claim_id(
        subject_id="service:order-service",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:product-service",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:product-service:GET:/products/{id}",
    )
    reference = identities.claim_id(
        subject_id="service:order-service",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:product-service",
        delivery_kind="SYNC_HTTP",
        delivery_via_id="operation:product-service:GET:/products/{id}",
    )
    assert reference == real


@pytest.mark.parametrize(
    ("object_id", "delivery_via_id", "subscription_id"),
    [
        ("service:payment-service", "queue:asb:commerce:payment-q", None),
        ("topic:owned:" + "a" * 64, "topic:owned:" + "a" * 64, None),
        ("service:billing", "topic:owned:" + "a" * 64, "subscription:owned:" + "b" * 64),
    ],
)
def test_async_claim_ids_match_the_real_implementation(object_id, delivery_via_id, subscription_id):
    """v0.5.0 I4 §12.4: Queue and Topic-fallback ids omit `subscription_id`; a Subscription route
    binds it - the reference must agree with production for all three shapes."""
    kwargs = {
        "subject_id": "service:orders",
        "predicate": "DIRECT_DEPENDENCY",
        "object_id": object_id,
        "delivery_kind": "ASYNC_MESSAGE",
        "delivery_via_id": delivery_via_id,
        "subscription_id": subscription_id,
    }
    assert identities.claim_id(**kwargs) == real_claim_id(**kwargs)


def test_claim_id_cli_accepts_an_optional_subscription_id(capsys):
    args = ["claim-id", "service:orders", "DIRECT_DEPENDENCY", "service:billing", "ASYNC_MESSAGE"]
    args += ["topic:owned:t"]
    reference_main([*args, "--subscription-id", "subscription:owned:s"])
    routed = capsys.readouterr().out.strip()
    reference_main(args)
    unrouted = capsys.readouterr().out.strip()

    assert routed == real_claim_id(
        subject_id="service:orders",
        predicate="DIRECT_DEPENDENCY",
        object_id="service:billing",
        delivery_kind="ASYNC_MESSAGE",
        delivery_via_id="topic:owned:t",
        subscription_id="subscription:owned:s",
    )
    assert unrouted != routed


def test_canonical_json_bytes_sorts_keys_and_formats_utc_timestamps():
    payload = {"b": 1, "a": datetime(2026, 8, 26, 12, 30, tzinfo=UTC)}
    encoded = canonical_json.canonical_json_bytes(payload).decode()
    assert encoded == '{"a":"2026-08-26T12:30:00.000000Z","b":1}'
