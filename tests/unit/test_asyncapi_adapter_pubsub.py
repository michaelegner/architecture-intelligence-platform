"""v0.5.0 I4 slice 2b - the §13.1 declared-source matrix for AsyncAPI 2.6.0 Topic/Subscription
mapping. Queue non-regression is covered by the unchanged tests in test_asyncapi_adapter.py."""

import copy

import pytest

from app.canonical.model import ArchitectureModel
from app.ingestion.asyncapi_adapter import AsyncApiSourceAdapter
from app.sources.migration_mappings import (
    EMPTY_SHARED_IDENTITY_INDEX,
    IdentityMappingEntry,
    MigrationMappingsDocument,
    build_shared_identity_index,
)
from app.sources.model import (
    DiagnosticCode,
    IngestionResult,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.owner_ids import queue_owned_id, subscription_owned_id, topic_owned_id
from app.sources.pointers import decode_pointer_tokens
from app.sources.service_identity import resolve_service_identity

SOURCE_INSTANCE_ID = "urn:aip:source:filesystem:" + "a" * 64
BROKER = "gcp-pubsub:projects/commerce"
TOPIC_ID = topic_owned_id(
    stable_broker_id=BROKER, normalized_namespace_or_empty="", exact_topic_address="orders"
)


class _StubResolver:
    def resolve(self, *, source_instance_id, construct_pointer, extension_value):
        return resolve_service_identity(
            source_instance_id=source_instance_id,
            construct_pointer=construct_pointer,
            extension_value=extension_value,
            configured_mappings=[],
            manifest_bindings=[],
        )


def _loaded(document: dict) -> LoadedSource:
    descriptor = SourceDescriptor(
        source_instance_id=SOURCE_INSTANCE_ID,
        source_kind=SourceKind.FILESYSTEM,
        locator="test.yaml",
        discovery_scope_id="urn:aip:discovery-scope:" + "b" * 64,
        scope_definition_digest="c" * 64,
        content_sha256="d" * 64,
        declared_provider_revision="rev-1",
        semantic_input_digest="",
        mapping_context_digest="",
        adapter_identity="asyncapi-adapter@1",
        mapping_rule_id="asyncapi-adapter@1",
        mapping_rule_version="v1",
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


def _topic_document(*, operations=None, broker=True, **channel_overrides) -> dict:
    channel = {"x-aip-destination-kind": "topic", **channel_overrides}
    if operations is None:
        operations = {"publish": {"message": {"$ref": "#/components/messages/OrderCreated"}}}
    channel.update(copy.deepcopy(operations))
    return {
        "asyncapi": "2.6.0",
        "info": {"title": "Svc"},
        "x-aip-service-id": "service:svc",
        "servers": (
            {
                "gcp": {
                    "url": "pubsub.googleapis.com",
                    "protocol": "googlepubsub",
                    "x-aip-broker-id": BROKER,
                }
            }
            if broker
            else {}
        ),
        "channels": {"orders": channel},
        "components": {
            "messages": {
                "OrderCreated": {
                    "name": "OrderCreated",
                    "payload": {"type": "object", "properties": {"id": {"type": "string"}}},
                }
            }
        },
    }


def _subscribe(name="billing", **extra) -> dict:
    operation = {"message": {"$ref": "#/components/messages/OrderCreated"}, **extra}
    if name is not None:
        operation["x-aip-subscription-name"] = name
    return {"subscribe": operation}


def _index(*, topic=(), subscription=(), queue=()):
    def entry(pointer, target_id, **extra):
        return IdentityMappingEntry(
            source_instance_id=SOURCE_INSTANCE_ID,
            document_path="test.yaml",
            pointer=pointer,
            pointer_tokens=decode_pointer_tokens(pointer),
            target_id=target_id,
            **extra,
        )

    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="test",
                artifact_revision="v1",
                locator="mappings.yaml",
                content_digest="x",
                queue_mappings=tuple(entry(p, t) for p, t in queue),
                topic_mappings=tuple(entry(p, t) for p, t in topic),
                subscription_mappings=tuple(
                    entry(p, sid, bound_topic_id=tid, subscription_name=name)
                    for p, tid, name, sid in subscription
                ),
            )
        ]
    )
    assert diagnostics == []
    return index


def _relations(outcome) -> set[tuple[str, str, str]]:
    return {(r.type, r.source_id, r.target_id) for r in outcome.model.relations}


def _codes(outcome) -> list[DiagnosticCode]:
    return [d.code for d in outcome.diagnostics]


def _derived_subscription_id(name="billing", topic_id=TOPIC_ID):
    return subscription_owned_id(
        stable_broker_id=BROKER,
        normalized_namespace_or_empty="",
        topic_id=topic_id,
        exact_subscription_name=name,
    )


# --- Topic kind and identity (§7.1, §8.1) -----------------------------------------------------


def test_topic_with_stable_broker_identity_maps_to_topic():
    outcome = _map(_topic_document())
    assert outcome.result is IngestionResult.ACCEPTED
    [topic] = outcome.model.topics
    assert (topic.id, topic.name, topic.namespace) == (TOPIC_ID, "orders", None)
    assert outcome.model.queues == []


def test_topic_publish_maps_to_publishes_to_and_topic_carries_message():
    outcome = _map(_topic_document())
    [message] = outcome.model.messages
    assert _relations(outcome) >= {
        ("PUBLISHES_TO", "service:svc", TOPIC_ID),
        ("CARRIES", TOPIC_ID, message.id),
    }
    assert not {r.type for r in outcome.model.relations} & {"SENDS", "RECEIVES_FROM"}


def test_pre_i4_topic_kind_without_identity_is_still_omitted_and_rejected_unsupported():
    """§13.1: the pre-I4 `x-aip-destination-kind: topic` input becomes a Topic *only* when every
    I4 guard passes - with no broker id and no configured Topic id, nothing is emitted."""
    outcome = _map(_topic_document(broker=False))
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.model.topics == []
    assert DiagnosticCode.AMBIGUOUS in _codes(outcome)


def test_configured_topic_id_without_broker_evidence_is_accepted():
    index = _index(topic=[("/channels/orders", "topic:configured-orders")])
    outcome = _map(_topic_document(broker=False), shared_identity=index)
    assert outcome.result is IngestionResult.ACCEPTED
    assert [t.id for t in outcome.model.topics] == ["topic:configured-orders"]


def test_configured_topic_id_agreeing_with_the_derived_id_is_accepted():
    index = _index(topic=[("/channels/orders", TOPIC_ID)])
    outcome = _map(_topic_document(), shared_identity=index)
    assert outcome.result is IngestionResult.ACCEPTED
    [declaration] = [d for d in outcome.model.pubsub_declarations if d.entity_kind == "TOPIC"]
    assert declaration.identity_methods == ["CONFIGURED", "DERIVED"]


def test_configured_topic_id_disagreeing_with_the_derived_id_rejects_atomically():
    index = _index(topic=[("/channels/orders", "topic:other")])
    outcome = _map(_topic_document(), shared_identity=index)
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert _codes(outcome) == [DiagnosticCode.TOPIC_IDENTITY_CONFLICT]
    assert outcome.model == ArchitectureModel()


def test_topic_mapping_alone_is_positive_topic_kind_evidence():
    index = _index(topic=[("/channels/orders", TOPIC_ID)])
    document = _topic_document()
    del document["channels"]["orders"]["x-aip-destination-kind"]
    outcome = _map(document, shared_identity=index)
    assert [t.id for t in outcome.model.topics] == [TOPIC_ID]


def test_unrecognized_kind_plus_topic_mapping_is_topic():
    """Slice-2 decision: an unrecognized kind value is a non-Queue vote only; it neither supports
    nor contradicts positive Topic evidence."""
    index = _index(topic=[("/channels/orders", TOPIC_ID)])
    document = _topic_document(**{"x-aip-destination-kind": "pubsub"})
    outcome = _map(document, shared_identity=index)
    assert [t.id for t in outcome.model.topics] == [TOPIC_ID]


@pytest.mark.parametrize("kind", ["pubsub", "broadcast", "fanout", "Topic", "kafka-topic"])
def test_unrecognized_kind_alone_preserves_i1_omission_and_aggregation(kind):
    outcome = _map(_topic_document(**{"x-aip-destination-kind": kind}))
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert _codes(outcome) == [DiagnosticCode.QUEUE_EVIDENCE_MISSING]
    assert outcome.model.topics == [] and outcome.model.queues == []


def test_amqp_routing_key_alone_is_never_topic_evidence():
    document = _topic_document(bindings={"amqp": {"is": "routingKey"}})
    del document["channels"]["orders"]["x-aip-destination-kind"]
    outcome = _map(document)
    assert outcome.model.topics == []
    assert _codes(outcome) == [DiagnosticCode.QUEUE_EVIDENCE_MISSING]


def test_amqp_routing_key_plus_topic_extension_is_topic():
    outcome = _map(_topic_document(bindings={"amqp": {"is": "routingKey"}}))
    assert len(outcome.model.topics) == 1


@pytest.mark.parametrize(
    ("overrides", "mappings"),
    [
        ({"bindings": {"amqp": {"is": "queue"}}}, {}),
        ({}, {"queue": [("/channels/orders", "queue:orders")]}),
        (
            {"x-aip-destination-kind": "queue"},
            {"topic": [("/channels/orders", TOPIC_ID)]},
        ),
    ],
)
def test_queue_and_topic_kind_evidence_conflict_rejects_atomically(overrides, mappings):
    outcome = _map(_topic_document(**overrides), shared_identity=_index(**mappings))
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert _codes(outcome) == [DiagnosticCode.QUEUE_KIND_CONFLICT]
    assert outcome.model == ArchitectureModel()


def test_protocol_or_vendor_alone_never_establishes_topic():
    document = _topic_document(bindings={"googlepubsub": {"topic": "orders"}})
    del document["channels"]["orders"]["x-aip-destination-kind"]
    outcome = _map(document)
    assert outcome.model.topics == []


def test_publish_or_subscribe_operation_alone_never_establishes_topic():
    document = _topic_document(operations=_subscribe())
    del document["channels"]["orders"]["x-aip-destination-kind"]
    outcome = _map(document)
    assert outcome.model.topics == [] and outcome.model.subscriptions == []


def test_same_name_queue_and_topic_have_distinct_ids():
    queue_id = queue_owned_id(
        stable_broker_id=BROKER, normalized_namespace_or_empty="", exact_channel_address="orders"
    )
    assert TOPIC_ID != queue_id
    outcome = _map(_topic_document())
    assert queue_id not in {t.id for t in outcome.model.topics}


def _amqp_topic_document(*, broker: str, virtual_host: str | None) -> dict:
    document = _topic_document()
    server = {"url": "amqps://broker.example.com", "protocol": "amqp", "x-aip-broker-id": broker}
    if virtual_host is not None:
        server["bindings"] = {"amqp": {"virtualHost": virtual_host}}
    document["servers"] = {"amqp": server}
    return document


def test_same_topic_name_under_different_brokers_or_namespaces_is_distinct():
    """§13.1: same names across brokers/namespaces remain distinct - at the adapter level, not only
    in the id formula."""
    ids = {}
    for broker, virtual_host in (
        ("broker-a", None),
        ("broker-b", None),
        ("broker-a", "commerce"),
        ("broker-a", "billing"),
    ):
        [topic] = _map(_amqp_topic_document(broker=broker, virtual_host=virtual_host)).model.topics
        assert topic.name == "orders"
        assert topic.namespace == virtual_host
        ids[(broker, virtual_host)] = topic.id
    assert len(set(ids.values())) == 4


def test_parameterized_channel_address_is_a_literal_identity_input():
    document = _topic_document()
    document["channels"] = {"orders/{region}": document["channels"]["orders"]}
    outcome = _map(document)
    [topic] = outcome.model.topics
    assert topic.id == topic_owned_id(
        stable_broker_id=BROKER,
        normalized_namespace_or_empty="",
        exact_topic_address="orders/{region}",
    )


def test_ambiguous_broker_blocks_topic_even_with_a_configured_id():
    document = _topic_document()
    document["servers"]["other"] = {"url": "x", "protocol": "googlepubsub", "x-aip-broker-id": "b"}
    index = _index(topic=[("/channels/orders", TOPIC_ID)])
    outcome = _map(document, shared_identity=index)
    assert outcome.model.topics == []
    assert DiagnosticCode.AMBIGUOUS in _codes(outcome)


def test_asyncapi_3_remains_rejected():
    document = _topic_document()
    document["asyncapi"] = "3.0.0"
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.model.topics == []


# --- Subscription identity (§7.2, §7.3, §8.3) -------------------------------------------------


def test_subscribe_with_explicit_name_maps_subscription_topology():
    outcome = _map(_topic_document(operations=_subscribe()))
    assert outcome.result is IngestionResult.ACCEPTED
    [subscription] = outcome.model.subscriptions
    assert (subscription.id, subscription.name) == (_derived_subscription_id(), "billing")
    [message] = outcome.model.messages
    assert _relations(outcome) >= {
        ("SUBSCRIPTION_OF", subscription.id, TOPIC_ID),
        ("RECEIVES_FROM", "service:svc", subscription.id),
        ("CARRIES", TOPIC_ID, message.id),
    }
    assert ("RECEIVES_FROM", "service:svc", TOPIC_ID) not in _relations(outcome)


@pytest.mark.parametrize("name", [None, "", 42])
def test_missing_subscription_identity_never_guesses_one(name):
    operations = _subscribe(name=None)
    if name is not None:
        operations["subscribe"]["x-aip-subscription-name"] = name
    operations["subscribe"]["operationId"] = "billingHandler"
    outcome = _map(_topic_document(operations=operations))
    assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert outcome.model.subscriptions == []
    [missing] = [
        d for d in outcome.diagnostics if d.code is DiagnosticCode.SUBSCRIPTION_IDENTITY_MISSING
    ]
    assert missing.source_pointer == "/channels/orders/subscribe"
    # Topic publication/message semantics remain; no subscribe-side topology is fabricated.
    [message] = outcome.model.messages
    assert {r for r in _relations(outcome) if r[0] != "CONFORMS_TO"} == {
        ("CARRIES", TOPIC_ID, message.id)
    }


def test_subscription_name_without_broker_or_configured_id_is_missing_identity():
    index = _index(topic=[("/channels/orders", "topic:configured-orders")])
    outcome = _map(_topic_document(operations=_subscribe(), broker=False), shared_identity=index)
    assert outcome.model.subscriptions == []
    assert DiagnosticCode.SUBSCRIPTION_IDENTITY_MISSING in _codes(outcome)


def test_configured_subscription_mapping_alone_supplies_identity():
    index = _index(
        topic=[("/channels/orders", "topic:configured-orders")],
        subscription=[
            ("/channels/orders/subscribe", "topic:configured-orders", "billing", "subscription:cfg")
        ],
    )
    outcome = _map(
        _topic_document(operations=_subscribe(name=None), broker=False), shared_identity=index
    )
    assert outcome.result is IngestionResult.ACCEPTED
    [subscription] = outcome.model.subscriptions
    assert (subscription.id, subscription.name) == ("subscription:cfg", "billing")


def test_configured_subscription_agreeing_with_declared_and_derived_is_accepted():
    subscription_id = _derived_subscription_id()
    index = _index(
        subscription=[("/channels/orders/subscribe", TOPIC_ID, "billing", subscription_id)]
    )
    outcome = _map(_topic_document(operations=_subscribe()), shared_identity=index)
    assert outcome.result is IngestionResult.ACCEPTED
    [declaration] = [
        d for d in outcome.model.pubsub_declarations if d.entity_kind == "SUBSCRIPTION"
    ]
    assert declaration.kind_evidence == ["subscriptionMappings", "x-aip-subscription-name"]
    assert declaration.identity_methods == ["CONFIGURED", "DERIVED"]


@pytest.mark.parametrize(
    "mapping",
    [
        # wrong Topic binding
        ("/channels/orders/subscribe", "topic:other", "billing", "subscription:x"),
        # name disagrees with x-aip-subscription-name
        ("/channels/orders/subscribe", TOPIC_ID, "shipping", "subscription:x"),
        # configured id disagrees with the derived id
        ("/channels/orders/subscribe", TOPIC_ID, "billing", "subscription:x"),
    ],
)
def test_configured_subscription_disagreement_rejects_atomically(mapping):
    outcome = _map(
        _topic_document(operations=_subscribe()), shared_identity=_index(subscription=[mapping])
    )
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert _codes(outcome) == [DiagnosticCode.SUBSCRIPTION_IDENTITY_CONFLICT]
    assert outcome.model == ArchitectureModel()


def test_subscription_mapping_is_not_evidence_for_a_sibling_channel():
    document = _topic_document(operations=_subscribe(name=None))
    document["channels"]["invoices"] = copy.deepcopy(document["channels"]["orders"])
    invoices_topic = topic_owned_id(
        stable_broker_id=BROKER, normalized_namespace_or_empty="", exact_topic_address="invoices"
    )
    index = _index(
        subscription=[
            ("/channels/orders/subscribe", TOPIC_ID, "billing", _derived_subscription_id())
        ]
    )
    outcome = _map(document, shared_identity=index)
    assert [s.id for s in outcome.model.subscriptions] == [_derived_subscription_id()]
    missing = [
        d for d in outcome.diagnostics if d.code is DiagnosticCode.SUBSCRIPTION_IDENTITY_MISSING
    ]
    assert [d.source_pointer for d in missing] == ["/channels/invoices/subscribe"]
    assert invoices_topic in {t.id for t in outcome.model.topics}


def test_same_subscription_name_under_different_topics_is_distinct():
    document = _topic_document(operations=_subscribe())
    document["channels"]["invoices"] = copy.deepcopy(document["channels"]["orders"])
    outcome = _map(document)
    assert len({s.id for s in outcome.model.subscriptions}) == 2
    assert {s.name for s in outcome.model.subscriptions} == {"billing"}


def test_subscription_name_is_nfc_normalized():
    outcome = _map(_topic_document(operations=_subscribe(name="Café")))
    [subscription] = outcome.model.subscriptions
    assert subscription.name == "Café"
    assert subscription.id == _derived_subscription_id("Café")


def test_consumer_group_extension_never_becomes_subscription_identity():
    operations = _subscribe(name=None, **{"x-aip-consumer-group": "billing"})
    outcome = _map(_topic_document(operations=operations))
    assert outcome.model.subscriptions == []
    assert DiagnosticCode.SUBSCRIPTION_IDENTITY_MISSING in _codes(outcome)


# --- Subscription dead-letter carrier (§10) ---------------------------------------------------


def test_subscription_dead_letter_is_retained_only_for_the_named_subscription():
    document = _topic_document(
        operations=_subscribe(
            **{"x-aip-subscription-dead-letter": {"target": "orders-dlq", "targetKind": "topic"}}
        )
    )
    document["channels"]["invoices"] = copy.deepcopy(document["channels"]["orders"])
    del document["channels"]["invoices"]["subscribe"]["x-aip-subscription-dead-letter"]
    outcome = _map(document)
    [configuration] = outcome.model.subscription_dead_letter_configurations
    assert configuration.subscription_id == _derived_subscription_id()
    assert (configuration.target_token, configuration.target_kind_token) == ("orders-dlq", "topic")
    assert configuration.source_pointer == (
        "/channels/orders/subscribe/x-aip-subscription-dead-letter"
    )
    # no generic target entity or relation is minted
    assert "DEAD_LETTERS_TO" not in {r.type for r in outcome.model.relations}
    assert {t.name for t in outcome.model.topics} == {"orders", "invoices"}
    assert outcome.model.queues == []


def test_subscription_dead_letter_without_target_kind_is_retained():
    outcome = _map(
        _topic_document(
            operations=_subscribe(**{"x-aip-subscription-dead-letter": {"target": "dlq"}})
        )
    )
    [configuration] = outcome.model.subscription_dead_letter_configurations
    assert configuration.target_kind_token is None


def test_subscription_dead_letter_on_an_unresolved_subscription_is_not_retained():
    outcome = _map(
        _topic_document(
            operations=_subscribe(
                name=None, **{"x-aip-subscription-dead-letter": {"target": "dlq"}}
            )
        )
    )
    assert outcome.model.subscription_dead_letter_configurations == []


@pytest.mark.parametrize(
    "value",
    [
        "orders-dlq",
        {},
        {"target": ""},
        {"target": 1},
        {"target": "d", "targetKind": ""},
        {"target": "d", "x": 1},
    ],
)
def test_malformed_subscription_dead_letter_rejects_invalid(value):
    outcome = _map(
        _topic_document(operations=_subscribe(**{"x-aip-subscription-dead-letter": value}))
    )
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert _codes(outcome) == [DiagnosticCode.DOCUMENT_PARSE_INVALID]
    assert outcome.model == ArchitectureModel()


def test_channel_level_dead_letter_queue_on_a_topic_keeps_i1_omission():
    outcome = _map(_topic_document(**{"x-dead-letter-queue": "orders-dlq"}))
    assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert DiagnosticCode.QUEUE_EVIDENCE_MISSING in _codes(outcome)
    assert outcome.model.queues == []
    assert "DEAD_LETTERS_TO" not in {r.type for r in outcome.model.relations}


# --- Per-artifact evidence retention (§11) ----------------------------------------------------


def test_topic_declaration_retains_the_full_evidence_record():
    outcome = _map(_topic_document())
    [declaration] = outcome.model.pubsub_declarations
    assert declaration.model_dump() == {
        "entity_id": TOPIC_ID,
        "entity_kind": "TOPIC",
        "source_instance_id": SOURCE_INSTANCE_ID,
        "source_locator": "test.yaml",
        "source_revision": "rev-1",
        "source_pointer": "/channels/orders",
        "semantic_input_digest": outcome.semantic_input_digest,
        "adapter_identity": "asyncapi-adapter@1",
        "mapping_rule_id": "asyncapi-adapter@1",
        "mapping_rule_version": "v1",
        "broker_id": BROKER,
        "namespace": None,
        "kind_evidence": ["x-aip-destination-kind"],
        "identity_methods": ["DERIVED"],
        "topic_address": "orders",
        "topic_id": None,
        "subscription_name": None,
    }


def test_subscription_declaration_retains_identity_inputs():
    outcome = _map(_topic_document(operations=_subscribe()))
    [declaration] = [
        d for d in outcome.model.pubsub_declarations if d.entity_kind == "SUBSCRIPTION"
    ]
    assert declaration.source_pointer == "/channels/orders/subscribe"
    assert (declaration.topic_id, declaration.subscription_name, declaration.topic_address) == (
        TOPIC_ID,
        "billing",
        "orders",
    )
    assert declaration.kind_evidence == ["x-aip-subscription-name"]
    assert declaration.identity_methods == ["DERIVED"]


def test_topic_only_document_with_publish_and_subscribe_is_accepted():
    operations = {
        **_subscribe(),
        "publish": {"message": {"$ref": "#/components/messages/OrderCreated"}},
    }
    outcome = _map(_topic_document(operations=operations))
    assert outcome.result is IngestionResult.ACCEPTED
    assert {r.type for r in outcome.model.relations} - {"CONFORMS_TO"} == {
        "PUBLISHES_TO",
        "SUBSCRIPTION_OF",
        "RECEIVES_FROM",
        "CARRIES",
    }


def test_configured_subscription_bound_to_another_topic_rejects_without_derived_evidence():
    """Isolates the §7.3 Topic-binding check: with no broker evidence there is no derived
    Subscription id to disagree with, so only the binding comparison can catch this."""
    index = _index(
        topic=[("/channels/orders", "topic:configured-orders")],
        subscription=[
            ("/channels/orders/subscribe", "topic:configured-other", "billing", "subscription:cfg")
        ],
    )
    outcome = _map(
        _topic_document(operations=_subscribe(name=None), broker=False), shared_identity=index
    )
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert _codes(outcome) == [DiagnosticCode.SUBSCRIPTION_IDENTITY_CONFLICT]


def test_configured_subscription_name_disagreeing_without_derived_evidence_rejects():
    index = _index(
        topic=[("/channels/orders", "topic:configured-orders")],
        subscription=[
            (
                "/channels/orders/subscribe",
                "topic:configured-orders",
                "shipping",
                "subscription:cfg",
            )
        ],
    )
    outcome = _map(_topic_document(operations=_subscribe(), broker=False), shared_identity=index)
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert _codes(outcome) == [DiagnosticCode.SUBSCRIPTION_IDENTITY_CONFLICT]
