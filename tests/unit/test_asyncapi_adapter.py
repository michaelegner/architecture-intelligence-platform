import copy
from pathlib import Path

from app.canonical.model import ArchitectureModel
from app.ingestion.asyncapi_adapter import AsyncApiSourceAdapter
from app.ingestion.filesystem_discoverer import FilesystemSourceDiscoverer
from app.sources.jcs import canonical_sha256_hex
from app.sources.migration_mappings import (
    EMPTY_SHARED_IDENTITY_INDEX,
    IdentityMappingEntry,
    MigrationMappingsDocument,
    build_shared_identity_index,
)
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionResult,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.owner_ids import queue_owned_id
from app.sources.service_identity import resolve_service_identity

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SOURCE_INSTANCE_ID = "urn:aip:source:filesystem:" + "a" * 64

BASE_SERVER = {
    "asb": {
        "url": "amqps://asb.example.com",
        "protocol": "amqp",
        "x-aip-broker-id": "asb",
        "bindings": {"amqp": {"virtualHost": "commerce"}},
    }
}


class _StubResolver:
    def resolve(self, *, source_instance_id, construct_pointer, extension_value):
        return resolve_service_identity(
            source_instance_id=source_instance_id,
            construct_pointer=construct_pointer,
            extension_value=extension_value,
            configured_mappings=[],
            manifest_bindings=[],
        )


def _loaded(document: dict, *, source_instance_id: str = SOURCE_INSTANCE_ID):
    descriptor = SourceDescriptor(
        source_instance_id=source_instance_id,
        source_kind=SourceKind.FILESYSTEM,
        locator="test.yaml",
        discovery_scope_id="urn:aip:discovery-scope:" + "b" * 64,
        scope_definition_digest="c" * 64,
        content_sha256="d" * 64,
        semantic_input_digest="",
        mapping_context_digest="",
        adapter_identity="",
        mapping_rule_id="",
        mapping_rule_version="",
    )
    return LoadedSource(descriptor=descriptor, document=document)


def _map(document: dict, *, shared_identity=EMPTY_SHARED_IDENTITY_INDEX):
    return AsyncApiSourceAdapter().map(
        _loaded(document),
        service_identity=_StubResolver(),
        shared_identity=shared_identity,
        upstream_model=ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )


def _base_document(**channel_overrides) -> dict:
    return {
        "asyncapi": "2.6.0",
        "info": {"title": "Svc"},
        "x-aip-service-id": "service:svc",
        "servers": copy.deepcopy(BASE_SERVER),
        "channels": {
            "orders-q": {
                "x-aip-destination-kind": "queue",
                "publish": {
                    "operationId": "sendOrder",
                    "message": {"$ref": "#/components/messages/OrderPlaced"},
                },
                **channel_overrides,
            }
        },
        "components": {
            "messages": {
                "OrderPlaced": {
                    "name": "OrderPlaced",
                    "x-version": "v1",
                    "payload": {"$ref": "#/components/schemas/OrderPlacedPayload"},
                }
            },
            "schemas": {
                "OrderPlacedPayload": {"type": "object", "properties": {"id": {"type": "string"}}}
            },
        },
    }


def _no_broker_document(**channel_overrides) -> dict:
    """A channel with real Queue-kind evidence but genuinely NO broker/namespace evidence at all
    (no `x-aip-broker-id` anywhere) - the actual "unchanged v0.4.2 fixture, no modern broker
    extension yet" scenario I1 spec §9's migration-mapping language describes, where a configured
    Queue mapping has no derived id to possibly disagree with."""
    document = _base_document(**channel_overrides)
    document["servers"] = {}
    return document


def _shared_identity_index(*, schema_mappings=(), message_mappings=(), queue_mappings=()):
    def _entries(mappings):
        return tuple(
            IdentityMappingEntry(
                source_instance_id=SOURCE_INSTANCE_ID,
                pointer=pointer,
                pointer_tokens=tuple(pointer.strip("/").split("/")),
                target_id=target_id,
            )
            for pointer, target_id in mappings
        )

    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="test-artifact",
                artifact_revision="v1",
                locator="migrations.yaml",
                schema_mappings=_entries(schema_mappings),
                message_mappings=_entries(message_mappings),
                queue_mappings=_entries(queue_mappings),
            )
        ]
    )
    assert diagnostics == []
    return index


def test_explicit_shared_message_mapping_overrides_the_owner_scoped_default():
    index = _shared_identity_index(
        message_mappings=[("/components/messages/OrderPlaced", "message:OrderPlaced:v2")]
    )
    outcome = _map(_base_document(), shared_identity=index)

    assert outcome.result is IngestionResult.ACCEPTED
    [message] = outcome.model.messages
    assert message.id == "message:OrderPlaced:v2"


def test_explicit_shared_payload_schema_mapping_overrides_the_owner_scoped_default():
    index = _shared_identity_index(
        schema_mappings=[("/components/schemas/OrderPlacedPayload", "schema:OrderPlaced:v2")]
    )
    outcome = _map(_base_document(), shared_identity=index)

    assert outcome.result is IngestionResult.ACCEPTED
    [schema] = outcome.model.schemas
    assert schema.id == "schema:OrderPlaced:v2"


def test_explicit_shared_mapping_for_an_inline_payload_overrides_the_owner_scoped_default():
    """Regression: the explicit-mapping check was only wired into the $ref payload branch of
    resolve_payload_schema_id, not the inline branch - an inline payload's explicit mapping was
    silently ignored, always falling back to inline_payload_schema_id."""
    document = _base_document()
    document["components"]["messages"]["OrderPlaced"]["payload"] = {"type": "object"}
    index = _shared_identity_index(
        schema_mappings=[("/components/messages/OrderPlaced/payload", "schema:OrderPlaced:legacy")]
    )
    outcome = _map(document, shared_identity=index)

    assert outcome.result is IngestionResult.ACCEPTED
    [schema] = outcome.model.schemas
    assert schema.id == "schema:OrderPlaced:legacy"


def test_explicit_message_mapping_to_the_same_id_with_disagreeing_content_conflicts():
    document = _base_document()
    document["channels"]["invoices-q"] = {
        "x-aip-destination-kind": "queue",
        "publish": {
            "operationId": "sendInvoice",
            "message": {"$ref": "#/components/messages/InvoiceCreated"},
        },
    }
    document["components"]["messages"]["InvoiceCreated"] = {
        "name": "InvoiceCreated",
        "x-version": "v1",
        "payload": {"type": "object", "properties": {"totally": {"type": "different"}}},
    }
    index = _shared_identity_index(
        message_mappings=[
            ("/components/messages/OrderPlaced", "message:Shared"),
            ("/components/messages/InvoiceCreated", "message:Shared"),
        ]
    )
    outcome = _map(document, shared_identity=index)

    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert any(d.code is DiagnosticCode.MESSAGE_CONTENT_CONFLICT for d in outcome.diagnostics)
    assert outcome.model.messages == []


def test_no_channels_is_accepted_as_service_only():
    document = {"asyncapi": "2.6.0", "info": {"title": "Svc"}, "x-aip-service-id": "service:svc"}
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    [service] = outcome.model.services
    assert service.id == "service:svc"
    assert outcome.model.queues == []


def test_fully_supported_channel_is_accepted():
    outcome = _map(_base_document())
    assert outcome.result is IngestionResult.ACCEPTED
    assert outcome.diagnostics == ()
    [queue] = outcome.model.queues
    assert queue.name == "orders-q"
    assert queue.id.startswith("queue:owned:")
    [message] = outcome.model.messages
    assert message.name == "OrderPlaced"
    assert message.version == "v1"


def test_queue_kind_from_amqp_binding_alone():
    document = _base_document()
    del document["channels"]["orders-q"]["x-aip-destination-kind"]
    document["channels"]["orders-q"]["bindings"] = {"amqp": {"is": "queue"}}
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    assert len(outcome.model.queues) == 1


def test_agreeing_kind_paths_are_accepted():
    document = _base_document()
    document["channels"]["orders-q"]["bindings"] = {"amqp": {"is": "queue"}}
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    assert len(outcome.model.queues) == 1


def test_conflicting_kind_paths_reject_the_whole_source():
    """Disagreement among Queue-kind evidence paths is a materially worse case than no evidence at
    all (an operator explicitly declared two contradictory things about the same channel) - it must
    reject the whole source with QUEUE_KIND_CONFLICT, not silently omit the channel."""
    document = _base_document()
    document["channels"]["orders-q"]["bindings"] = {"amqp": {"is": "topic"}}
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert any(d.code is DiagnosticCode.QUEUE_KIND_CONFLICT for d in outcome.diagnostics)
    assert outcome.model.queues == []


def test_missing_kind_evidence_channel_is_unsupported():
    document = _base_document()
    del document["channels"]["orders-q"]["x-aip-destination-kind"]
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.diagnostics[0].code is DiagnosticCode.QUEUE_EVIDENCE_MISSING


def test_missing_broker_id_leaves_channel_unsupported():
    document = _base_document()
    del document["servers"]["asb"]["x-aip-broker-id"]
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.model.queues == []


def test_multi_server_disagreement_is_ambiguous():
    document = _base_document()
    document["servers"]["other"] = {
        "url": "amqps://other.example.com",
        "protocol": "amqp",
        "x-aip-broker-id": "other-broker",
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.AMBIGUOUS for d in outcome.diagnostics)


def test_explicit_queue_mapping_does_not_override_multi_server_disagreement():
    """§9: real disagreement among a channel's own selected servers must remain AMBIGUOUS with no
    Queue emitted, even when an explicit Queue mapping is also configured. `_resolve_broker_and_
    namespace` previously returned the same `None` for "genuinely no evidence" and "servers exist
    but disagree", so the explicit-mapping branch treated a real disagreement as if there were
    simply nothing to compare against and silently used the configured id - a configured id doesn't
    resolve a disagreement among the channel's own server declarations, it only supplies something
    to compare a *resolved* derived id against."""
    document = _base_document()
    document["servers"]["other"] = {
        "url": "amqps://other.example.com",
        "protocol": "amqp",
        "x-aip-broker-id": "other-broker",
    }
    index = _shared_identity_index(queue_mappings=[("/channels/orders-q", "queue:orders-q")])
    outcome = _map(document, shared_identity=index)

    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.AMBIGUOUS for d in outcome.diagnostics)
    assert outcome.model.queues == []


def test_multi_server_agreement_is_accepted():
    document = _base_document()
    document["servers"]["mirror"] = {
        "url": "amqps://mirror.example.com",
        "protocol": "amqp",
        "x-aip-broker-id": "asb",
        "bindings": {"amqp": {"virtualHost": "commerce"}},
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    assert len(outcome.model.queues) == 1


def test_channel_scoped_servers_restriction_is_honored():
    document = _base_document()
    document["servers"]["other"] = {
        "url": "amqps://other.example.com",
        "protocol": "amqp",
        "x-aip-broker-id": "other-broker",
    }
    document["channels"]["orders-q"]["servers"] = ["asb"]
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED


def test_namespace_defaults_to_empty_without_virtual_host():
    document = _base_document()
    del document["servers"]["asb"]["bindings"]
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    [queue] = outcome.model.queues
    assert queue.namespace is None


def test_channel_address_normalizes_to_unicode_nfc():
    # A precomposed "e with acute accent" (U+00E9) vs. "e" + a combining acute accent (U+0065
    # U+0301) must resolve to the same owner-scoped Queue id (I1 spec §9: "normalized to Unicode
    # NFC without trimming or case folding"). Explicit \u escapes, not literal characters, so the
    # decomposed form can't be silently re-normalized by an editor/formatter round-trip.
    precomposed_name = "caf\u00e9-q"
    decomposed_name = "cafe\u0301-q"
    assert precomposed_name != decomposed_name  # sanity: genuinely different code point sequences

    precomposed = _base_document()
    precomposed["channels"][precomposed_name] = precomposed["channels"].pop("orders-q")

    decomposed = _base_document()
    decomposed["channels"][decomposed_name] = decomposed["channels"].pop("orders-q")

    id_precomposed = _map(precomposed).model.queues[0].id
    id_decomposed = _map(decomposed).model.queues[0].id
    assert id_precomposed == id_decomposed


def test_one_supported_one_omitted_channel_is_accepted_with_limitations():
    document = _base_document()
    document["channels"]["unsupported-q"] = {
        "publish": {"operationId": "sendX", "message": {"payload": {"type": "object"}}}
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert len(outcome.model.queues) == 1


def test_dead_letters_to_relation_inherits_declaring_channel_broker():
    document = _base_document()
    document["channels"]["orders-q"]["x-dead-letter-queue"] = "orders-dlq"
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    dlq_relations = [r for r in outcome.model.relations if r.type == "DEAD_LETTERS_TO"]
    assert len(dlq_relations) == 1
    dlq_queue = next(q for q in outcome.model.queues if q.name == "orders-dlq")
    assert dlq_relations[0].target_id == dlq_queue.id
    declaring_queue = next(q for q in outcome.model.queues if q.name == "orders-q")
    # The DLQ target's identity hash already incorporates the inherited namespace (§9); its node
    # property must agree, not just its id, or the two would silently disagree about ownership.
    assert dlq_queue.namespace == declaring_queue.namespace


def test_explicit_queue_mapping_is_used_when_there_is_no_derived_broker_evidence_at_all():
    """The real §9 use case: a channel with no broker/namespace evidence whatsoever (the genuine
    "unchanged v0.4.2 fixture, no x-aip-broker-id yet" scenario) has no derived id to possibly
    disagree with, so the configured mapping alone establishes identity."""
    index = _shared_identity_index(queue_mappings=[("/channels/orders-q", "queue:orders-q")])
    outcome = _map(_no_broker_document(), shared_identity=index)

    assert outcome.result is IngestionResult.ACCEPTED
    [queue] = outcome.model.queues
    assert queue.id == "queue:orders-q"


def test_explicit_queue_mapping_agreeing_with_the_derived_id_is_accepted():
    """When broker/namespace evidence IS available, an explicit mapping that happens to equal the
    real derived id agrees rather than conflicts."""
    derived_id = queue_owned_id(
        stable_broker_id="asb",
        normalized_namespace_or_empty="commerce",
        exact_channel_address="orders-q",
    )
    index = _shared_identity_index(queue_mappings=[("/channels/orders-q", derived_id)])
    outcome = _map(_base_document(), shared_identity=index)

    assert outcome.result is IngestionResult.ACCEPTED
    assert outcome.model.queues[0].id == derived_id


def test_explicit_queue_mapping_disagreeing_with_the_derived_id_rejects():
    """I1 spec §9: "a configured Queue ID that disagrees with the derived ID" is REJECTED_CONFLICT
    - both identity paths must be computed and compared whenever broker/namespace evidence is
    available, not just whichever path happens to be present."""
    index = _shared_identity_index(queue_mappings=[("/channels/orders-q", "queue:orders-q")])
    outcome = _map(_base_document(), shared_identity=index)

    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert any(d.code is DiagnosticCode.QUEUE_IDENTITY_CONFLICT for d in outcome.diagnostics)
    assert outcome.model.queues == []


def test_explicit_queue_mapping_conflicting_with_kind_evidence_rejects():
    index = _shared_identity_index(queue_mappings=[("/channels/orders-q", "queue:orders-q")])
    document = _no_broker_document()
    # An explicit mapping votes "queue"; an AMQP binding declaring "topic" disagrees. No broker
    # evidence at all here, so this isolates the kind-conflict path from the identity-conflict path
    # exercised by the tests above.
    document["channels"]["orders-q"]["bindings"] = {"amqp": {"is": "topic"}}
    outcome = _map(document, shared_identity=index)

    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert any(d.code is DiagnosticCode.QUEUE_KIND_CONFLICT for d in outcome.diagnostics)


def test_explicit_dlq_target_mapping_is_used_when_declaring_channel_has_no_derived_broker():
    """When the declaring channel has no broker/namespace evidence at all (so no derived id to
    inherit), the DLQ target can still resolve via its own explicit mapping, keyed at the
    x-dead-letter-queue field's own pointer."""
    index = _shared_identity_index(
        queue_mappings=[
            ("/channels/orders-q", "queue:orders-q"),
            ("/channels/orders-q/x-dead-letter-queue", "queue:orders-dlq"),
        ]
    )
    document = _no_broker_document()
    document["channels"]["orders-q"]["x-dead-letter-queue"] = "orders-dlq"
    outcome = _map(document, shared_identity=index)

    assert outcome.result is IngestionResult.ACCEPTED
    dlq_queue = next(q for q in outcome.model.queues if q.name == "orders-dlq")
    assert dlq_queue.id == "queue:orders-dlq"
    dlq_relations = [r for r in outcome.model.relations if r.type == "DEAD_LETTERS_TO"]
    assert dlq_relations[0].target_id == "queue:orders-dlq"


def test_explicit_dlq_target_mapping_disagreeing_with_the_derived_id_rejects():
    """The DLQ target's own explicit mapping is compared against ITS derived id the same way a
    declaring channel's is, when the declaring channel does have broker/namespace evidence to
    inherit."""
    index = _shared_identity_index(
        queue_mappings=[
            (
                "/channels/orders-q",
                queue_owned_id(
                    stable_broker_id="asb",
                    normalized_namespace_or_empty="commerce",
                    exact_channel_address="orders-q",
                ),
            ),
            ("/channels/orders-q/x-dead-letter-queue", "queue:orders-dlq"),
        ]
    )
    document = _base_document()
    document["channels"]["orders-q"]["x-dead-letter-queue"] = "orders-dlq"
    outcome = _map(document, shared_identity=index)

    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert any(d.code is DiagnosticCode.QUEUE_IDENTITY_CONFLICT for d in outcome.diagnostics)


def test_referenced_message_payload_uses_schema_owned_id():
    outcome = _map(_base_document())
    [message] = outcome.model.messages
    [schema] = outcome.model.schemas
    assert message.schema_id == schema.id
    assert schema.id.startswith("schema:owned:")
    assert schema.canonical_hash == canonical_sha256_hex(
        {"type": "object", "properties": {"id": {"type": "string"}}}
    )


def test_inline_message_payload_uses_inline_payload_schema_id():
    document = _base_document()
    document["channels"]["orders-q"]["publish"]["message"] = {
        "name": "InlineMessage",
        "payload": {"type": "object", "properties": {"x": {"type": "string"}}},
    }
    outcome = _map(document)
    [message] = outcome.model.messages
    assert message.name == "InlineMessage"
    [schema] = outcome.model.schemas
    assert schema.id == message.schema_id
    assert schema.name == "InlineMessage payload"


def test_two_channels_with_distinct_inline_messages_do_not_collide():
    """A real bug found in PR review: an inline (non-`$ref`) message's pointer used to be the bare
    `("message",)` (or `("message", "oneOf", index)`), with no channel/operation disambiguation -
    two different channels each declaring their own inline message got the identical owner-scoped
    message_owned_id, silently merging two distinct messages/payloads into one Message node with
    the first channel's content, and both queues' CARRIES relations pointing at it."""
    document = _base_document()
    document["channels"]["orders-q"]["publish"]["message"] = {
        "name": "OrderMessage",
        "payload": {"type": "object", "properties": {"order_id": {"type": "string"}}},
    }
    document["channels"]["shipping-q"] = {
        "x-aip-destination-kind": "queue",
        "publish": {
            "operationId": "sendShipping",
            "message": {
                "name": "ShippingMessage",
                "payload": {"type": "object", "properties": {"tracking_id": {"type": "string"}}},
            },
        },
    }
    outcome = _map(document)

    assert outcome.result is IngestionResult.ACCEPTED
    assert {m.name for m in outcome.model.messages} == {"OrderMessage", "ShippingMessage"}
    assert len({m.id for m in outcome.model.messages}) == 2
    assert len({s.id for s in outcome.model.schemas}) == 2

    carries = {r.source_id: r.target_id for r in outcome.model.relations if r.type == "CARRIES"}
    order_queue = next(q.id for q in outcome.model.queues if q.name == "orders-q")
    shipping_queue = next(q.id for q in outcome.model.queues if q.name == "shipping-q")
    assert carries[order_queue] != carries[shipping_queue]


def test_message_with_no_name_or_title_gets_deterministic_fallback():
    document = _base_document()
    document["channels"]["orders-q"]["publish"]["message"] = {
        "payload": {"type": "object"},
    }
    outcome = _map(document)
    [message] = outcome.model.messages
    assert message.name == "orders-q:publish"


def test_explicit_null_x_version_is_rejected_invalid():
    document = _base_document()
    document["components"]["messages"]["OrderPlaced"]["x-version"] = None
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_INVALID


def test_absent_x_version_participates_as_empty():
    document = _base_document()
    del document["components"]["messages"]["OrderPlaced"]["x-version"]
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    [message] = outcome.model.messages
    assert message.version is None


def test_missing_service_identity_is_rejected_unsupported():
    document = {"asyncapi": "2.6.0", "info": {"title": "X"}}
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.diagnostics[0].code is DiagnosticCode.SERVICE_IDENTITY_UNRESOLVED


def test_invalid_document_structure_is_rejected_invalid():
    document = {"asyncapi": "2.6.0"}  # missing required info/channels
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert outcome.diagnostics[0].code is DiagnosticCode.DOCUMENT_PARSE_INVALID


def test_supports_matches_only_asyncapi_documents():
    adapter = AsyncApiSourceAdapter()
    assert adapter.supports(_loaded(_base_document())) is True
    assert adapter.supports(_loaded({"openapi": "3.1.0"})) is False


def test_provenance_recorded_and_attached_to_relations():
    outcome = _map(_base_document())
    [provenance] = outcome.model.provenance
    assert provenance.source_type == "ASYNCAPI"
    assert provenance.evidence_type == "DECLARED"
    assert all(r.evidence_ids == [provenance.id] for r in outcome.model.relations)


def test_maps_real_bundled_fixtures_with_matching_queue_ids_across_sources():
    discoverer = FilesystemSourceDiscoverer(
        FilesystemSourceConfig(id="aip-bundled-examples-v0.5", root=EXAMPLES_DIR)
    )
    loaded_sources = [s for s in discoverer.discover().loaded_sources if "asyncapi" in s.document]
    adapter = AsyncApiSourceAdapter()

    queue_ids_by_name: dict[str, set[str]] = {}
    for loaded in loaded_sources:
        outcome = adapter.map(
            loaded,
            service_identity=_StubResolver(),
            shared_identity=EMPTY_SHARED_IDENTITY_INDEX,
            upstream_model=ArchitectureModel(),
            mapping_context_digest="e" * 64,
        )
        assert outcome.result is IngestionResult.ACCEPTED, (
            loaded.descriptor.locator,
            outcome.diagnostics,
        )
        for queue in outcome.model.queues:
            queue_ids_by_name.setdefault(queue.name, set()).add(queue.id)

    # payment-q and invoice-q are declared by two different services each; both must resolve to
    # exactly one shared owner-scoped Queue id.
    assert len(queue_ids_by_name["payment-q"]) == 1
    assert len(queue_ids_by_name["invoice-q"]) == 1
