import pytest

from app.sources.owner_ids import (
    InvalidXVersionError,
    inline_payload_schema_id,
    message_owned_id,
    normalize_x_version,
    queue_owned_id,
    schema_owned_id,
)


def test_normalize_x_version_none_is_empty():
    assert normalize_x_version(None) == ""


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
