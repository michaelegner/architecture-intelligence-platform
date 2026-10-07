"""v0.6.1 I1b: AsyncAPI Broker emission (spec §4.2). A Broker and one deduplicated `USES_BROKER`
come only from an admitted operation whose channel resolved a Queue or Topic and whose selected
server carries an explicit stable `x-aip-broker-id`."""

import copy

from app.canonical.model import ArchitectureModel
from app.ingestion.asyncapi_adapter import AsyncApiSourceAdapter
from app.sources.model import IngestionResult
from app.sources.owner_ids import broker_owned_id
from tests.unit.test_asyncapi_adapter_pubsub import (
    BROKER,
    _index,
    _map,
    _relations,
    _subscribe,
    _topic_document,
)

BROKER_ID = broker_owned_id(stable_broker_id=BROKER)
USES = ("USES_BROKER", "service:svc", BROKER_ID)


def _uses(outcome) -> list[tuple[str, str, str]]:
    return [
        (r.type, r.source_id, r.target_id)
        for r in outcome.model.relations
        if r.type == "USES_BROKER"
    ]


def _server(broker_id: str | None, *, virtual_host: str | None = None) -> dict:
    server: dict = {"url": "broker.example", "protocol": "amqp"}
    if broker_id is not None:
        server["x-aip-broker-id"] = broker_id
    if virtual_host is not None:
        server["bindings"] = {"amqp": {"virtualHost": virtual_host}}
    return server


def _two_channel_document(server_a: dict, server_b: dict) -> dict:
    document = _topic_document()
    document["servers"] = {"a": server_a, "b": server_b}
    channel = document["channels"]["orders"]
    channel["servers"] = ["a"]
    other = copy.deepcopy(channel)
    other["servers"] = ["b"]
    document["channels"]["invoices"] = other
    return document


def test_adapter_mapping_rule_version_is_bumped_for_the_new_facts():
    assert AsyncApiSourceAdapter.mapping_rule_version == "v2"
    assert AsyncApiSourceAdapter.adapter_identity == "asyncapi-adapter@1"


def test_topic_publish_emits_one_broker_with_declared_evidence():
    outcome = _map(_topic_document())
    assert outcome.result is IngestionResult.ACCEPTED
    [broker] = outcome.model.brokers
    assert (broker.id, broker.stable_broker_id) == (BROKER_ID, BROKER)
    [relation] = [r for r in outcome.model.relations if r.type == "USES_BROKER"]
    assert (relation.source_id, relation.target_id) == ("service:svc", BROKER_ID)
    assert relation.evidence_ids
    assert set(relation.evidence_ids) <= {p.id for p in outcome.model.provenance}


def test_publish_and_subscribe_on_one_channel_dedupe_to_one_relation():
    operations = {
        **_subscribe(),
        "publish": {"message": {"$ref": "#/components/messages/OrderCreated"}},
    }
    outcome = _map(_topic_document(operations=operations))
    assert _uses(outcome) == [USES]
    assert len(outcome.model.brokers) == 1


def test_topic_without_subscription_identity_still_evidences_the_broker():
    outcome = _map(_topic_document(operations=_subscribe(name=None)))
    assert outcome.model.subscriptions == []
    assert _uses(outcome) == [USES]


def test_queue_channel_emits_the_broker():
    outcome = _map(_topic_document(**{"x-aip-destination-kind": "queue"}))
    assert [q.name for q in outcome.model.queues] == ["orders"]
    assert _uses(outcome) == [USES]


def test_bare_server_without_any_admitted_operation_emits_no_broker():
    document = _topic_document()
    document["channels"] = {}
    outcome = _map(document)
    assert outcome.model.brokers == []
    assert _uses(outcome) == []


def test_channel_without_destination_kind_evidence_emits_no_broker():
    document = _topic_document()
    del document["channels"]["orders"]["x-aip-destination-kind"]
    outcome = _map(document)
    assert outcome.model.brokers == []
    assert _uses(outcome) == []


def test_destination_resolved_only_by_a_mapping_emits_no_broker():
    index = _index(topic=[("/channels/orders", "topic:configured-orders")])
    outcome = _map(_topic_document(broker=False), shared_identity=index)
    assert [t.id for t in outcome.model.topics] == ["topic:configured-orders"]
    assert outcome.model.brokers == []
    assert _uses(outcome) == []


def test_disagreeing_servers_on_one_channel_emit_no_broker():
    document = _topic_document()
    document["servers"] = {"a": _server("kafka:one"), "b": _server("kafka:two")}
    outcome = _map(document)
    assert outcome.model.brokers == []
    assert outcome.model.topics == []
    assert _uses(outcome) == []


def test_partially_identified_servers_on_one_channel_emit_no_broker():
    document = _topic_document()
    document["servers"] = {"a": _server("kafka:one"), "b": _server(None)}
    outcome = _map(document)
    assert outcome.model.brokers == []
    assert _uses(outcome) == []


def test_same_broker_id_in_different_virtual_hosts_is_one_broker():
    document = _two_channel_document(
        _server(BROKER, virtual_host="tenant-a"), _server(BROKER, virtual_host="tenant-b")
    )
    outcome = _map(document)
    assert len(outcome.model.topics) == 2  # namespace still distinguishes the destinations
    assert [b.id for b in outcome.model.brokers] == [BROKER_ID]
    assert _uses(outcome) == [USES]


def test_two_independently_evidenced_brokers_for_one_service_are_both_kept():
    other = "gcp-pubsub:projects/other"
    document = _two_channel_document(_server(BROKER), _server(other))
    outcome = _map(document)
    other_id = broker_owned_id(stable_broker_id=other)
    assert {b.id for b in outcome.model.brokers} == {BROKER_ID, other_id}
    assert set(_uses(outcome)) == {USES, ("USES_BROKER", "service:svc", other_id)}


def test_broker_is_independent_of_the_destination_relations():
    relations = _relations(_map(_topic_document()))
    assert {r[0] for r in relations} >= {"PUBLISHES_TO", "CARRIES", "USES_BROKER"}
    assert not {r for r in relations if r[0] == "USES_BROKER" and r[2] != BROKER_ID}
    assert ArchitectureModel().brokers == []


def test_the_rule_version_bump_moves_the_mapping_context_digest(monkeypatch):
    """Unchanged bytes now map new facts (Broker, USES_BROKER); the active mapping-rule version is
    part of the mapping context (I1 §5.3), so the bump is what makes an already-imported unchanged
    AsyncAPI source re-evaluate."""
    from app.ingestion.orchestrator import _compute_mapping_context_digest, default_registry
    from app.sources.manifest_bindings import BindingIndex
    from app.sources.migration_mappings import EMPTY_SHARED_IDENTITY_INDEX

    def digest() -> str:
        return _compute_mapping_context_digest(
            BindingIndex(entries=()), default_registry(), EMPTY_SHARED_IDENTITY_INDEX
        )

    current = digest()
    monkeypatch.setattr(AsyncApiSourceAdapter, "mapping_rule_version", "v1")
    assert digest() != current
