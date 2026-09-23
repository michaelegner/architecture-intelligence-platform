import pytest
import yaml

from app.sources.migration_mappings import (
    IdentityMappingEntry,
    MigrationMappingsDocument,
    build_shared_identity_index,
    load_migration_mappings,
    parse_migration_mappings,
)
from app.sources.model import DiagnosticCode

SOURCE_A = "urn:aip:source:filesystem:" + "a" * 64
SOURCE_B = "urn:aip:source:filesystem:" + "b" * 64


def _document(**overrides):
    document = {
        "apiVersion": "aip.dev/v1",
        "kind": "AipSharedIdentityMappings",
        "metadata": {"id": "aip-v0.5.0-bundled-example-identities-v1", "revision": "v1"},
        "schemaMappings": [
            {
                "sourceInstanceId": SOURCE_A,
                "documentPath": "root.yaml",
                "pointer": "/components/schemas/OrderRequest",
                "schemaId": "schema:OrderRequest",
            }
        ],
        "messageMappings": [
            {
                "sourceInstanceId": SOURCE_A,
                "documentPath": "root.yaml",
                "pointer": "/components/messages/PaymentRequested",
                "messageId": "message:PaymentRequested:v2",
            }
        ],
        "queueMappings": [
            {
                "sourceInstanceId": SOURCE_A,
                "documentPath": "root.yaml",
                "pointer": "/channels/payment-q",
                "queueId": "queue:payment-q",
            }
        ],
    }
    document.update(overrides)
    return document


def test_parse_valid_document():
    parsed, diagnostics = parse_migration_mappings(
        _document(), locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert diagnostics == []
    assert parsed is not None
    assert parsed.artifact_id == "aip-v0.5.0-bundled-example-identities-v1"
    assert parsed.artifact_revision == "v1"
    assert len(parsed.schema_mappings) == 1
    assert parsed.schema_mappings[0].target_id == "schema:OrderRequest"
    assert parsed.schema_mappings[0].pointer_tokens == ("components", "schemas", "OrderRequest")
    assert len(parsed.message_mappings) == 1
    assert len(parsed.queue_mappings) == 1


def test_parse_accepts_a_document_with_no_mapping_arrays_at_all():
    document = {
        "apiVersion": "aip.dev/v1",
        "kind": "AipSharedIdentityMappings",
        "metadata": {"id": "empty", "revision": "v1"},
    }
    parsed, diagnostics = parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert diagnostics == []
    assert parsed.schema_mappings == ()
    assert parsed.message_mappings == ()
    assert parsed.queue_mappings == ()


def test_parse_rejects_additional_top_level_field():
    document = _document()
    document["extra"] = "not allowed"
    parsed, diagnostics = parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID


def test_parse_rejects_wrong_kind():
    document = _document()
    document["kind"] = "SomethingElse"
    parsed, diagnostics = parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID


def test_parse_rejects_entry_missing_document_path():
    document = _document()
    del document["schemaMappings"][0]["documentPath"]
    parsed, diagnostics = parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID


def test_parse_rejects_malformed_pointer():
    document = _document()
    document["schemaMappings"][0]["pointer"] = "no-leading-slash"
    parsed, diagnostics = parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID


def test_parse_rejects_target_id_with_wrong_prefix():
    document = _document()
    document["schemaMappings"][0]["schemaId"] = "message:WrongKind"
    parsed, diagnostics = parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MIGRATION_MAPPING_TARGET_INVALID


def test_parse_rejects_target_id_with_whitespace():
    document = _document()
    document["queueMappings"][0]["queueId"] = "queue: has space"
    parsed, diagnostics = parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MIGRATION_MAPPING_TARGET_INVALID


def _entry(
    source_instance_id: str, pointer: str, target_id: str, *, document_path: str = "root.yaml"
) -> IdentityMappingEntry:
    from app.sources.pointers import decode_pointer_tokens

    return IdentityMappingEntry(
        source_instance_id=source_instance_id,
        document_path=document_path,
        pointer=pointer,
        pointer_tokens=decode_pointer_tokens(pointer),
        target_id=target_id,
    )


def _index_document(artifact_id: str, *, schema=(), message=(), queue=()):
    return MigrationMappingsDocument(
        artifact_id=artifact_id,
        artifact_revision="v1",
        locator=f"{artifact_id}.yaml",
        content_digest="test-content-digest",
        schema_mappings=tuple(schema),
        message_mappings=tuple(message),
        queue_mappings=tuple(queue),
    )


def test_build_index_resolves_configured_mappings():
    doc = _index_document(
        "a",
        schema=[_entry(SOURCE_A, "/components/schemas/OrderRequest", "schema:OrderRequest")],
        message=[_entry(SOURCE_A, "/components/messages/X", "message:X:v1")],
        queue=[_entry(SOURCE_A, "/channels/payment-q", "queue:payment-q")],
    )
    index, diagnostics = build_shared_identity_index([doc])

    assert diagnostics == []
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A,
            document_path="root.yaml",
            pointer="/components/schemas/OrderRequest",
        )
        == "schema:OrderRequest"
    )
    assert (
        index.message_id_for(
            source_instance_id=SOURCE_A, document_path="root.yaml", pointer="/components/messages/X"
        )
        == "message:X:v1"
    )
    assert (
        index.queue_id_for(
            source_instance_id=SOURCE_A, document_path="root.yaml", pointer="/channels/payment-q"
        )
        == "queue:payment-q"
    )
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_B,
            document_path="root.yaml",
            pointer="/components/schemas/OrderRequest",
        )
        is None
    )


def test_build_index_is_permutation_independent_across_documents():
    doc_a = _index_document("a", schema=[_entry(SOURCE_A, "/x", "schema:X")])
    doc_b = _index_document("b", schema=[_entry(SOURCE_B, "/y", "schema:Y")])

    forward, forward_diagnostics = build_shared_identity_index([doc_a, doc_b])
    backward, backward_diagnostics = build_shared_identity_index([doc_b, doc_a])

    assert forward.schema_index == backward.schema_index
    assert forward_diagnostics == backward_diagnostics == []


def test_build_index_deduplicates_identical_entries_across_documents():
    entry = _entry(SOURCE_A, "/components/schemas/X", "schema:X")
    doc_one = _index_document("a", schema=[entry])
    doc_two = _index_document("b", schema=[entry])

    index, diagnostics = build_shared_identity_index([doc_one, doc_two])
    assert diagnostics == []
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A, document_path="root.yaml", pointer="/components/schemas/X"
        )
        == "schema:X"
    )


def test_build_index_flags_conflicting_target_for_same_pointer():
    one = _entry(SOURCE_A, "/components/schemas/X", "schema:X")
    two = _entry(SOURCE_A, "/components/schemas/X", "schema:DifferentX")
    index, diagnostics = build_shared_identity_index([_index_document("a", schema=[one, two])])

    assert any(d.code is DiagnosticCode.MIGRATION_MAPPING_CONFLICT for d in diagnostics)
    # exactly one of the two disagreeing targets wins deterministically (sorted-first)
    assert index.schema_id_for(
        source_instance_id=SOURCE_A, document_path="root.yaml", pointer="/components/schemas/X"
    ) in (
        "schema:X",
        "schema:DifferentX",
    )


def test_build_index_keeps_same_pointer_in_different_documents_independent():
    """I1 §8.1/§9.1: "the normalized definition source pointer is the normalized relative document
    path plus decoded RFC 6901 pointer" - one SourceInstanceId's own bounded multi-file $ref closure
    (PR3b) can resolve the identical relative pointer inside two different files, and each file's
    mapping must resolve independently rather than colliding or spuriously conflicting."""
    entry_a = _entry(SOURCE_A, "/components/schemas/X", "schema:FromA", document_path="a.yaml")
    entry_b = _entry(SOURCE_A, "/components/schemas/X", "schema:FromB", document_path="b.yaml")
    index, diagnostics = build_shared_identity_index(
        [_index_document("both", schema=[entry_a, entry_b])]
    )

    assert diagnostics == []
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A, document_path="a.yaml", pointer="/components/schemas/X"
        )
        == "schema:FromA"
    )
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A, document_path="b.yaml", pointer="/components/schemas/X"
        )
        == "schema:FromB"
    )
    # A lookup for a document path that was never mapped for this pointer must not fall through to
    # either real entry - the two documents' identical pointers must never cross-contaminate.
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A, document_path="c.yaml", pointer="/components/schemas/X"
        )
        is None
    )


def test_build_index_keeps_schema_message_queue_namespaces_independent():
    # The same (source_instance_id, pointer) key in different kinds must never cross-contaminate.
    doc = _index_document(
        "a",
        schema=[_entry(SOURCE_A, "/x", "schema:X")],
        message=[_entry(SOURCE_A, "/x", "message:X")],
        queue=[_entry(SOURCE_A, "/x", "queue:X")],
    )
    index, diagnostics = build_shared_identity_index([doc])
    assert diagnostics == []
    assert (
        index.schema_id_for(source_instance_id=SOURCE_A, document_path="root.yaml", pointer="/x")
        == "schema:X"
    )
    assert (
        index.message_id_for(source_instance_id=SOURCE_A, document_path="root.yaml", pointer="/x")
        == "message:X"
    )
    assert (
        index.queue_id_for(source_instance_id=SOURCE_A, document_path="root.yaml", pointer="/x")
        == "queue:X"
    )


def test_load_migration_mappings_from_real_files(tmp_path):
    path = tmp_path / "migrations.yaml"
    path.write_text(yaml.safe_dump(_document()))

    index, diagnostics = load_migration_mappings([path])
    assert diagnostics == ()
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A,
            document_path="root.yaml",
            pointer="/components/schemas/OrderRequest",
        )
        == "schema:OrderRequest"
    )
    assert len(index.documents) == 1
    assert index.documents[0].artifact_id == "aip-v0.5.0-bundled-example-identities-v1"


def test_load_migration_mappings_diagnoses_a_missing_file(tmp_path):
    index, diagnostics = load_migration_mappings([tmp_path / "does-not-exist.yaml"])
    assert index.documents == ()
    assert any(d.code is DiagnosticCode.MIGRATION_MAPPING_FILE_UNAVAILABLE for d in diagnostics)


def test_load_migration_mappings_diagnoses_malformed_yaml(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("not: valid: yaml: [")
    index, diagnostics = load_migration_mappings([path])
    assert index.documents == ()
    assert any(d.code is DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID for d in diagnostics)


def test_load_migration_mappings_diagnoses_non_mapping_root(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- just\n- a\n- list\n")
    index, diagnostics = load_migration_mappings([path])
    assert index.documents == ()
    assert any(d.code is DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID for d in diagnostics)


def test_load_migration_mappings_merges_multiple_files(tmp_path):
    path_a = tmp_path / "a.yaml"
    path_a.write_text(yaml.safe_dump(_document(metadata={"id": "artifact-a", "revision": "v1"})))
    path_b = tmp_path / "b.yaml"
    doc_b = _document(metadata={"id": "artifact-b", "revision": "v1"})
    doc_b["schemaMappings"][0]["pointer"] = "/components/schemas/Other"
    doc_b["schemaMappings"][0]["schemaId"] = "schema:Other"
    path_b.write_text(yaml.safe_dump(doc_b))

    index, diagnostics = load_migration_mappings([path_a, path_b])
    assert diagnostics == ()
    assert len(index.documents) == 2
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A,
            document_path="root.yaml",
            pointer="/components/schemas/OrderRequest",
        )
        == "schema:OrderRequest"
    )
    assert (
        index.schema_id_for(
            source_instance_id=SOURCE_A,
            document_path="root.yaml",
            pointer="/components/schemas/Other",
        )
        == "schema:Other"
    )


# --- v0.5.0 I4 spec §7.3: topicMappings / subscriptionMappings ---------------------------------

TOPIC_ID = "topic:owned:" + "1" * 64
OTHER_TOPIC_ID = "topic:owned:" + "2" * 64
SUBSCRIPTION_ID = "subscription:owned:" + "3" * 64


def _pubsub_document(**overrides):
    document = {
        "apiVersion": "aip.dev/v1",
        "kind": "AipSharedIdentityMappings",
        "metadata": {"id": "pubsub", "revision": "v1"},
        "topicMappings": [
            {
                "sourceInstanceId": SOURCE_A,
                "documentPath": "root.yaml",
                "pointer": "/channels/orders",
                "topicId": TOPIC_ID,
            }
        ],
        "subscriptionMappings": [
            {
                "sourceInstanceId": SOURCE_A,
                "documentPath": "root.yaml",
                "pointer": "/channels/orders/subscribe",
                "topicId": TOPIC_ID,
                "subscriptionName": "billing",
                "subscriptionId": SUBSCRIPTION_ID,
            }
        ],
    }
    document.update(overrides)
    return document


def _parse(document):
    return parse_migration_mappings(
        document, locator="migrations.yaml", content_digest="test-content-digest"
    )


def test_parse_valid_topic_and_subscription_mappings():
    parsed, diagnostics = _parse(_pubsub_document())
    assert diagnostics == []
    [topic] = parsed.topic_mappings
    assert (topic.pointer_tokens, topic.target_id) == (("channels", "orders"), TOPIC_ID)
    [subscription] = parsed.subscription_mappings
    assert subscription.pointer_tokens == ("channels", "orders", "subscribe")
    assert subscription.target_id == SUBSCRIPTION_ID
    assert subscription.bound_topic_id == TOPIC_ID
    assert subscription.subscription_name == "billing"


def test_pre_i4_document_has_empty_topic_and_subscription_mappings():
    parsed, diagnostics = _parse(_document())
    assert diagnostics == []
    assert parsed.topic_mappings == ()
    assert parsed.subscription_mappings == ()


def test_subscription_name_is_nfc_normalized_without_trimming_or_case_folding():
    document = _pubsub_document()
    document["subscriptionMappings"][0]["subscriptionName"] = " Café "
    parsed, _ = _parse(document)
    assert parsed.subscription_mappings[0].subscription_name == " Café "


@pytest.mark.parametrize(
    ("array", "mutate"),
    [
        ("topicMappings", lambda e: e.update(kind="topic")),
        ("topicMappings", lambda e: e.pop("topicId")),
        ("topicMappings", lambda e: e.update(topicId="")),
        ("subscriptionMappings", lambda e: e.pop("topicId")),
        ("subscriptionMappings", lambda e: e.pop("subscriptionName")),
        ("subscriptionMappings", lambda e: e.pop("subscriptionId")),
        ("subscriptionMappings", lambda e: e.update(subscriptionName="")),
        ("subscriptionMappings", lambda e: e.update(consumerGroup="billing-group")),
    ],
)
def test_pubsub_mapping_shape_violations_are_shape_invalid(array, mutate):
    document = _pubsub_document()
    mutate(document[array][0])
    parsed, diagnostics = _parse(document)
    assert parsed is None
    assert diagnostics
    assert {d.code for d in diagnostics} == {DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID}


@pytest.mark.parametrize(
    ("array", "field", "value"),
    [
        ("topicMappings", "topicId", "queue:owned:x"),
        ("topicMappings", "topicId", "topic: has space"),
        ("subscriptionMappings", "topicId", "subscription:owned:x"),
        ("subscriptionMappings", "subscriptionId", "topic:owned:x"),
    ],
)
def test_pubsub_mapping_target_grammar_violations_are_target_invalid(array, field, value):
    document = _pubsub_document()
    document[array][0][field] = value
    parsed, diagnostics = _parse(document)
    assert parsed is None
    [diagnostic] = diagnostics
    assert diagnostic.code is DiagnosticCode.MIGRATION_MAPPING_TARGET_INVALID
    assert diagnostic.source_pointer == f"/{array}/0/{field}"


def test_pubsub_mapping_malformed_pointer_is_shape_invalid():
    document = _pubsub_document()
    document["subscriptionMappings"][0]["pointer"] = "channels/orders/subscribe"
    parsed, diagnostics = _parse(document)
    assert parsed is None
    [diagnostic] = diagnostics
    assert diagnostic.code is DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID
    assert diagnostic.source_pointer == "/subscriptionMappings/0/pointer"


def test_index_resolves_topic_and_subscription_mappings_by_exact_key():
    parsed, _ = _parse(_pubsub_document())
    index, diagnostics = build_shared_identity_index([parsed])
    assert diagnostics == []
    lookup = {"source_instance_id": SOURCE_A, "document_path": "root.yaml"}
    assert index.topic_id_for(**lookup, pointer="/channels/orders") == TOPIC_ID
    mapping = index.subscription_mapping_for(**lookup, pointer="/channels/orders/subscribe")
    assert (mapping.topic_id, mapping.subscription_name, mapping.subscription_id) == (
        TOPIC_ID,
        "billing",
        SUBSCRIPTION_ID,
    )
    # exact lookup only - no sibling pointer, other document, or other kind resolves
    assert index.topic_id_for(**lookup, pointer="/channels/orders/subscribe") is None
    assert index.subscription_mapping_for(**lookup, pointer="/channels/orders") is None
    assert index.queue_id_for(**lookup, pointer="/channels/orders") is None
    assert (
        index.topic_id_for(
            source_instance_id=SOURCE_B, document_path="root.yaml", pointer="/channels/orders"
        )
        is None
    )


def test_index_deduplicates_identical_subscription_entries_across_documents():
    parsed, _ = _parse(_pubsub_document())
    twin, _ = _parse(_pubsub_document(metadata={"id": "twin", "revision": "v1"}))
    _, diagnostics = build_shared_identity_index([parsed, twin])
    assert diagnostics == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subscriptionId", "subscription:owned:" + "9" * 64),
        ("topicId", OTHER_TOPIC_ID),
        ("subscriptionName", "shipping"),
    ],
)
def test_subscription_entries_disagreeing_on_any_payload_field_conflict(field, value):
    """I4 spec §7.3: two entries at one key that agree on the Subscription id but disagree on its
    Topic binding or name are a conflict, never a silent first-wins."""
    parsed, _ = _parse(_pubsub_document())
    other = _pubsub_document(metadata={"id": "other", "revision": "v1"})
    other["subscriptionMappings"][0][field] = value
    other_parsed, _ = _parse(other)
    _, diagnostics = build_shared_identity_index([parsed, other_parsed])
    assert [d.code for d in diagnostics] == [DiagnosticCode.MIGRATION_MAPPING_CONFLICT]


def test_conflicting_topic_mappings_for_same_channel_conflict():
    parsed, _ = _parse(_pubsub_document())
    other = _pubsub_document(metadata={"id": "other", "revision": "v1"})
    other["topicMappings"][0]["topicId"] = OTHER_TOPIC_ID
    other_parsed, _ = _parse(other)
    _, diagnostics = build_shared_identity_index([parsed, other_parsed])
    assert [d.code for d in diagnostics] == [DiagnosticCode.MIGRATION_MAPPING_CONFLICT]


def test_topic_and_queue_mappings_at_the_same_pointer_stay_in_independent_namespaces():
    """The index never merges kinds; a Queue+Topic mapping at one Channel pointer is a kind
    conflict the AsyncAPI adapter rejects (I4 spec §8.1), not something the index resolves."""
    document = _pubsub_document(queueMappings=_document()["queueMappings"])
    document["queueMappings"][0]["pointer"] = "/channels/orders"
    parsed, _ = _parse(document)
    index, diagnostics = build_shared_identity_index([parsed])
    assert diagnostics == []
    lookup = {
        "source_instance_id": SOURCE_A,
        "document_path": "root.yaml",
        "pointer": "/channels/orders",
    }
    assert index.queue_id_for(**lookup) == "queue:payment-q"
    assert index.topic_id_for(**lookup) == TOPIC_ID
