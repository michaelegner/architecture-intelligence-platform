"""v0.5.0 I4 slice 2b: canonical validation, merge, and cross-source conflict rules for the
Topic/Subscription family (spec §4.2, §6.2-§6.3, §10, §11)."""

import pytest

from app.canonical.model import ArchitectureModel, Relation, Service, Subscription, Topic
from app.canonical.pubsub import PubSubDeclaration, SubscriptionDeadLetterConfiguration
from app.ingestion.orchestrator import merge_models
from app.sources.claim_conflicts import detect_subscription_topic_binding_conflicts
from app.sources.model import DiagnosticCode
from app.validation.canonical_validation import CanonicalValidationError, validate_canonical_model

SERVICE = Service(id="service:svc", name="Svc")
TOPIC = Topic(id="topic:orders", name="orders")
OTHER_TOPIC = Topic(id="topic:invoices", name="invoices")
SUBSCRIPTION = Subscription(id="subscription:billing", name="billing")
SOURCE_A = "urn:aip:source:filesystem:" + "a" * 64
SOURCE_B = "urn:aip:source:filesystem:" + "b" * 64


def _declaration(**overrides) -> PubSubDeclaration:
    fields = {
        "entity_id": TOPIC.id,
        "entity_kind": "TOPIC",
        "source_instance_id": SOURCE_A,
        "source_locator": "svc/asyncapi.yaml",
        "source_pointer": "/channels/orders",
        "semantic_input_digest": "d" * 64,
        "adapter_identity": "asyncapi-adapter@1",
        "mapping_rule_id": "asyncapi-adapter@1",
        "mapping_rule_version": "v1",
        "kind_evidence": ["x-aip-destination-kind"],
        "identity_methods": ["DERIVED"],
    }
    fields.update(overrides)
    return PubSubDeclaration(**fields)


def _dead_letter(**overrides) -> SubscriptionDeadLetterConfiguration:
    fields = {
        "subscription_id": SUBSCRIPTION.id,
        "source_instance_id": SOURCE_A,
        "source_locator": "svc/asyncapi.yaml",
        "source_pointer": "/channels/orders/subscribe/x-aip-subscription-dead-letter",
        "target_token": "orders-dlq",
    }
    fields.update(overrides)
    return SubscriptionDeadLetterConfiguration(**fields)


def _valid_model(**overrides) -> ArchitectureModel:
    fields = {
        "services": [SERVICE],
        "topics": [TOPIC],
        "subscriptions": [SUBSCRIPTION],
        "relations": [
            Relation(type="PUBLISHES_TO", source_id=SERVICE.id, target_id=TOPIC.id),
            Relation(type="SUBSCRIPTION_OF", source_id=SUBSCRIPTION.id, target_id=TOPIC.id),
            Relation(type="RECEIVES_FROM", source_id=SERVICE.id, target_id=SUBSCRIPTION.id),
        ],
        "pubsub_declarations": [_declaration()],
        "subscription_dead_letter_configurations": [_dead_letter()],
    }
    fields.update(overrides)
    return ArchitectureModel(**fields)


def _errors(model: ArchitectureModel) -> str:
    with pytest.raises(CanonicalValidationError) as exc:
        validate_canonical_model(model)
    return str(exc.value)


def test_valid_pubsub_model_passes():
    validate_canonical_model(_valid_model())


def test_duplicate_topic_and_subscription_ids_are_rejected():
    assert "Topic id is not unique" in _errors(_valid_model(topics=[TOPIC, TOPIC]))
    assert "Subscription id is not unique" in _errors(
        _valid_model(subscriptions=[SUBSCRIPTION, SUBSCRIPTION])
    )


@pytest.mark.parametrize(
    ("relation", "expected"),
    [
        (
            Relation(type="PUBLISHES_TO", source_id=SERVICE.id, target_id=SUBSCRIPTION.id),
            "not a topic",
        ),
        (Relation(type="PUBLISHES_TO", source_id=TOPIC.id, target_id=TOPIC.id), "not a service"),
        (
            Relation(type="SUBSCRIPTION_OF", source_id=TOPIC.id, target_id=TOPIC.id),
            "not a subscription",
        ),
        (Relation(type="RECEIVES_FROM", source_id=SERVICE.id, target_id=TOPIC.id), "is a Topic"),
        (
            Relation(type="CARRIES", source_id=SUBSCRIPTION.id, target_id=SERVICE.id),
            "is a Subscription",
        ),
    ],
)
def test_pubsub_relation_endpoint_violations_are_rejected(relation, expected):
    model = _valid_model()
    model = model.model_copy(update={"relations": [*model.relations, relation]})
    assert expected in _errors(model)


def test_subscription_must_be_bound_to_exactly_one_topic():
    unbound = _valid_model(
        relations=[Relation(type="RECEIVES_FROM", source_id=SERVICE.id, target_id=SUBSCRIPTION.id)]
    )
    assert "exactly one Topic" in _errors(unbound)
    doubly_bound = _valid_model(
        topics=[TOPIC, OTHER_TOPIC],
        relations=[
            Relation(type="SUBSCRIPTION_OF", source_id=SUBSCRIPTION.id, target_id=TOPIC.id),
            Relation(type="SUBSCRIPTION_OF", source_id=SUBSCRIPTION.id, target_id=OTHER_TOPIC.id),
        ],
    )
    assert "exactly one Topic" in _errors(doubly_bound)


def test_carrier_references_must_resolve():
    assert "unknown TOPIC" in _errors(
        _valid_model(pubsub_declarations=[_declaration(entity_id="topic:missing")])
    )
    assert "unknown SUBSCRIPTION" in _errors(
        _valid_model(
            pubsub_declarations=[
                _declaration(entity_kind="SUBSCRIPTION", entity_id="subscription:missing")
            ]
        )
    )
    assert "references unknown Subscription" in _errors(
        _valid_model(
            subscription_dead_letter_configurations=[
                _dead_letter(subscription_id="subscription:missing")
            ]
        )
    )


def test_carrier_ids_are_source_scoped():
    assert _declaration().id != _declaration(source_instance_id=SOURCE_B).id
    assert _declaration().id != _declaration(source_pointer="/channels/other").id
    assert _dead_letter().id != _dead_letter(source_instance_id=SOURCE_B).id
    assert _declaration().id.startswith("urn:aip:pubsub-declaration:")
    assert _dead_letter().id.startswith("urn:aip:subscription-dlq:")


def test_merge_models_carries_every_pubsub_list_and_dedupes_by_id():
    one = _valid_model()
    two = _valid_model(
        pubsub_declarations=[_declaration(source_instance_id=SOURCE_B)],
        subscription_dead_letter_configurations=[_dead_letter(source_instance_id=SOURCE_B)],
    )
    merged = merge_models([one, two])
    assert [t.id for t in merged.topics] == [TOPIC.id]
    assert [s.id for s in merged.subscriptions] == [SUBSCRIPTION.id]
    assert len(merged.pubsub_declarations) == 2
    assert len(merged.subscription_dead_letter_configurations) == 2
    validate_canonical_model(merged)


def test_subscription_bound_to_two_topics_across_sources_is_a_conflict():
    one = _valid_model()
    two = _valid_model(
        topics=[OTHER_TOPIC],
        relations=[
            Relation(type="SUBSCRIPTION_OF", source_id=SUBSCRIPTION.id, target_id=OTHER_TOPIC.id)
        ],
        pubsub_declarations=[],
        subscription_dead_letter_configurations=[],
    )
    conflicts = detect_subscription_topic_binding_conflicts({SOURCE_A: one, SOURCE_B: two})
    assert [d.code for d in conflicts.diagnostics] == [
        DiagnosticCode.SUBSCRIPTION_IDENTITY_CONFLICT
    ]
    assert conflicts.conflicted_source_instance_ids == {SOURCE_A, SOURCE_B}


def test_agreeing_subscription_bindings_across_sources_are_not_a_conflict():
    conflicts = detect_subscription_topic_binding_conflicts(
        {SOURCE_A: _valid_model(), SOURCE_B: _valid_model()}
    )
    assert not conflicts
