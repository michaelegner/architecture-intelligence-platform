import hashlib
import inspect

import pytest

from app.sources.owner_ids import (
    MISSING,
    InvalidXVersionError,
    inline_payload_schema_id,
    message_owned_id,
    normalize_x_version,
    queue_owned_id,
    schema_owned_id,
    subscription_owned_id,
    topic_owned_id,
)


def test_normalize_x_version_missing_sentinel_is_empty():
    assert normalize_x_version(MISSING) == ""


def test_normalize_x_version_missing_key_via_dict_get_is_empty():
    document = {}
    assert normalize_x_version(document.get("x-version", MISSING)) == ""


def test_normalize_x_version_explicit_none_is_rejected():
    # x-version: null in a source document is an explicit non-string value, distinct from the key
    # being absent - dict.get would return None for both, so callers must pass MISSING for "absent"
    # and let a genuine None reach this function to be rejected here.
    with pytest.raises(InvalidXVersionError):
        normalize_x_version(None)


def test_normalize_x_version_explicit_none_via_dict_get_is_rejected():
    document = {"x-version": None}
    with pytest.raises(InvalidXVersionError):
        normalize_x_version(document.get("x-version", MISSING))


def test_normalize_x_version_empty_string_is_empty():
    assert normalize_x_version("") == ""


def test_normalize_x_version_nonempty_string_participates():
    assert normalize_x_version("v2") == "v2"


def test_normalize_x_version_rejects_non_string():
    with pytest.raises(InvalidXVersionError):
        normalize_x_version(2)


def test_schema_owned_id_is_stable_for_identical_inputs():
    first = schema_owned_id(
        canonical_service_id="service:order-service",
        source_instance_id="urn:aip:source:filesystem:" + "a" * 64,
        normalized_definition_document_path="openapi.yaml",
        definition_pointer_tokens=("components", "schemas", "Order"),
    )
    second = schema_owned_id(
        canonical_service_id="service:order-service",
        source_instance_id="urn:aip:source:filesystem:" + "a" * 64,
        normalized_definition_document_path="openapi.yaml",
        definition_pointer_tokens=("components", "schemas", "Order"),
    )
    assert first == second
    assert first.startswith("schema:owned:")


def test_schema_owned_id_unaffected_by_unrelated_schema_addition():
    # Adding/removing an unrelated content-equivalent schema cannot change an inline schema's ID -
    # true by construction here since the formula has no such input, but characterized explicitly.
    base_kwargs = {
        "canonical_service_id": "service:order-service",
        "source_instance_id": "urn:aip:source:filesystem:" + "a" * 64,
        "normalized_definition_document_path": "openapi.yaml",
        "definition_pointer_tokens": ("paths", "/orders", "post", "requestBody"),
    }
    before = schema_owned_id(**base_kwargs)
    after = schema_owned_id(**base_kwargs)
    assert before == after


def test_schema_owned_id_changes_with_owner_pointer():
    kwargs = {
        "canonical_service_id": "service:order-service",
        "source_instance_id": "urn:aip:source:filesystem:" + "a" * 64,
        "normalized_definition_document_path": "openapi.yaml",
    }
    a = schema_owned_id(definition_pointer_tokens=("components", "schemas", "Order"), **kwargs)
    b = schema_owned_id(definition_pointer_tokens=("components", "schemas", "Invoice"), **kwargs)
    assert a != b


def test_schema_owned_id_pointer_encoding_does_not_confuse_path_and_token_boundary():
    # Path vs. pointer-token fields are encoded separately so a token that looks like a path
    # fragment can't collide with an actual path change.
    one = schema_owned_id(
        canonical_service_id="service:a",
        source_instance_id="urn:aip:source:filesystem:" + "a" * 64,
        normalized_definition_document_path="openapi.yaml",
        definition_pointer_tokens=("foo/bar",),
    )
    two = schema_owned_id(
        canonical_service_id="service:a",
        source_instance_id="urn:aip:source:filesystem:" + "a" * 64,
        normalized_definition_document_path="openapi.yaml/foo",
        definition_pointer_tokens=("bar",),
    )
    assert one != two


def test_message_owned_id_changes_with_x_version():
    kwargs = {
        "canonical_service_id": "service:payment-service",
        "source_instance_id": "urn:aip:source:filesystem:" + "b" * 64,
        "normalized_definition_document_path": "asyncapi.yaml",
        "definition_pointer_tokens": ("channels", "payment-q", "publish", "message"),
    }
    unversioned = message_owned_id(**kwargs)
    versioned = message_owned_id(normalized_x_version_or_empty="v2", **kwargs)
    assert unversioned != versioned
    assert unversioned.startswith("message:owned:")


def test_inline_payload_schema_id_is_scoped_to_message_id():
    one = inline_payload_schema_id(
        message_id="message:owned:" + "a" * 64,
        normalized_inline_payload_document_path="asyncapi.yaml",
        inline_payload_pointer_tokens=("channels", "payment-q", "publish", "message", "payload"),
    )
    two = inline_payload_schema_id(
        message_id="message:owned:" + "b" * 64,
        normalized_inline_payload_document_path="asyncapi.yaml",
        inline_payload_pointer_tokens=("channels", "payment-q", "publish", "message", "payload"),
    )
    assert one != two
    assert one.startswith("schema:owned:")


def test_queue_owned_id_requires_broker_namespace_and_channel_agreement():
    base = queue_owned_id(
        stable_broker_id="broker:asb:commerce",
        normalized_namespace_or_empty="",
        exact_channel_address="payment-q",
    )
    different_broker = queue_owned_id(
        stable_broker_id="broker:asb:other",
        normalized_namespace_or_empty="",
        exact_channel_address="payment-q",
    )
    different_namespace = queue_owned_id(
        stable_broker_id="broker:asb:commerce",
        normalized_namespace_or_empty="ns",
        exact_channel_address="payment-q",
    )
    different_channel = queue_owned_id(
        stable_broker_id="broker:asb:commerce",
        normalized_namespace_or_empty="",
        exact_channel_address="invoice-q",
    )
    assert len({base, different_broker, different_namespace, different_channel}) == 4
    assert base.startswith("queue:owned:")


# --- v0.5.0 I4 spec §7.1/§7.2 ------------------------------------------------------------------


def _independent_length_delimited(*parts: str) -> bytes:
    # Written from the I1 §5 encoding rule (8-byte big-endian length prefix per UTF-8 part), not by
    # calling app.sources.encoding.length_delimited - an independent golden-vector derivation.
    return b"".join(len(p.encode()).to_bytes(8, "big") + p.encode() for p in parts)


def test_topic_owned_id_matches_the_independently_derived_formula():
    expected = (
        "topic:owned:"
        + hashlib.sha256(
            _independent_length_delimited("broker:asb:commerce", "ns", "orders")
        ).hexdigest()
    )
    assert (
        topic_owned_id(
            stable_broker_id="broker:asb:commerce",
            normalized_namespace_or_empty="ns",
            exact_topic_address="orders",
        )
        == expected
    )


def test_subscription_owned_id_matches_the_independently_derived_formula():
    topic_id = "topic:owned:" + "a" * 64
    expected = (
        "subscription:owned:"
        + hashlib.sha256(
            _independent_length_delimited("broker:asb:commerce", "", topic_id, "billing")
        ).hexdigest()
    )
    assert (
        subscription_owned_id(
            stable_broker_id="broker:asb:commerce",
            normalized_namespace_or_empty="",
            topic_id=topic_id,
            exact_subscription_name="billing",
        )
        == expected
    )


def test_topic_owned_id_requires_broker_namespace_and_address_agreement():
    def topic(broker="broker:asb:commerce", namespace="", address="orders"):
        return topic_owned_id(
            stable_broker_id=broker,
            normalized_namespace_or_empty=namespace,
            exact_topic_address=address,
        )

    ids = {topic(), topic(broker="broker:asb:other"), topic(namespace="ns"), topic(address="x")}
    assert len(ids) == 4


def test_queue_and_topic_ids_never_alias_for_identical_inputs():
    """I4 spec §7.2: Queue, Topic, and Subscription ids use distinct prefixes and never alias merely
    because names match."""
    inputs = {"stable_broker_id": "b", "normalized_namespace_or_empty": "n"}
    queue = queue_owned_id(**inputs, exact_channel_address="orders")
    topic = topic_owned_id(**inputs, exact_topic_address="orders")
    subscription = subscription_owned_id(**inputs, topic_id=topic, exact_subscription_name="orders")
    assert queue.startswith("queue:owned:")
    assert topic.startswith("topic:owned:")
    assert subscription.startswith("subscription:owned:")
    # Queue and Topic share the owner-key formula; only the type prefix separates them.
    assert queue.removeprefix("queue:owned:") == topic.removeprefix("topic:owned:")
    assert len({queue, topic, subscription}) == 3


def test_same_subscription_name_under_different_topics_is_distinct():
    def subscription(topic_id):
        return subscription_owned_id(
            stable_broker_id="b",
            normalized_namespace_or_empty="",
            topic_id=topic_id,
            exact_subscription_name="billing",
        )

    orders = topic_owned_id(
        stable_broker_id="b", normalized_namespace_or_empty="", exact_topic_address="orders"
    )
    invoices = topic_owned_id(
        stable_broker_id="b", normalized_namespace_or_empty="", exact_topic_address="invoices"
    )
    assert subscription(orders) != subscription(invoices)


def test_subscription_owned_id_has_no_consumer_group_input():
    """I4 spec §7.2: "A consumer-group identifier SHALL NOT be fed into the Subscription identity
    formula." Pinned structurally on the helper's signature."""
    assert list(inspect.signature(subscription_owned_id).parameters) == [
        "stable_broker_id",
        "normalized_namespace_or_empty",
        "topic_id",
        "exact_subscription_name",
    ]
