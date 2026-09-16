from app.sources.jcs import canonical_sha256_hex
from app.sources.message_contract import (
    message_contract_digest,
    message_contract_projection,
    message_document_digest,
)


def test_presentation_only_differences_produce_identical_contract_digest():
    base = {
        "name": "PaymentRequested",
        "title": "Payment Requested",
        "description": "before",
        "x-version": "v1",
        "payload": {"type": "object"},
    }
    changed = {
        "name": "DifferentName",
        "title": "Different Title",
        "description": "after",
        "x-version": "v2",
        "payload": {"type": "object"},
    }

    digest_base = message_contract_digest(base, normalized_payload=None)
    digest_changed = message_contract_digest(changed, normalized_payload=None)
    assert digest_base == digest_changed


def test_x_aip_extensions_are_excluded_from_the_contract_digest():
    base = {"payload": {"type": "object"}, "x-aip-service-id": "service:a"}
    changed = {"payload": {"type": "object"}, "x-aip-service-id": "service:b"}
    assert message_contract_digest(base, normalized_payload=None) == message_contract_digest(
        changed, normalized_payload=None
    )


def test_a_real_contract_field_difference_changes_the_digest():
    base = {"payload": {"type": "object"}, "bindings": {"amqp": {"exchange": "a"}}}
    changed = {"payload": {"type": "object"}, "bindings": {"amqp": {"exchange": "b"}}}
    assert message_contract_digest(base, normalized_payload=None) != message_contract_digest(
        changed, normalized_payload=None
    )


def test_the_raw_payload_ref_is_replaced_by_the_resolved_normalized_payload():
    document_ref = {"payload": {"$ref": "other.yaml#/Foo"}}
    document_inline = {"payload": {"type": "object", "properties": {"id": {"type": "string"}}}}
    resolved_shape = {"type": "object", "properties": {"id": {"type": "string"}}}

    digest_via_ref = message_contract_digest(document_ref, normalized_payload=resolved_shape)
    digest_via_inline = message_contract_digest(document_inline, normalized_payload=resolved_shape)
    assert digest_via_ref == digest_via_inline


def test_projection_omits_payload_key_when_there_is_no_payload_at_all():
    projection = message_contract_projection({"bindings": {}}, normalized_payload=None)
    assert "payload" not in projection


def test_document_digest_is_sensitive_to_presentation_only_fields():
    base = {"name": "X", "payload": {"type": "object"}}
    changed = {"name": "Y", "payload": {"type": "object"}}
    assert message_document_digest(base) != message_document_digest(changed)
    assert message_document_digest(base) == canonical_sha256_hex(base)
