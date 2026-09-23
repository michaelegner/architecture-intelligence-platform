"""v0.5.0 I4 slice 1 (spec §6.2, §11, §15): the in-memory Topic/Subscription foundation, and the
fail-closed guard that no Pub/Sub node or relation can be persisted before slice 2.

Slice 2 opens the persistence path atomically - `ArchitectureModel` Topic/Subscription lists,
importer `NODE_LABELS`/`KNOWN_RELATION_TYPES`, the `graph_schema` `RELATIONS` registry, dedicated
Topic/Subscription canonicalization queries, and the `_CANONICALIZATION_VERSION` 2 -> 3 bump - and
must update `test_pubsub_persistence_path_is_closed_until_slice_2` in that same commit.
"""

from app.architecture_intelligence import repository
from app.canonical.model import ArchitectureModel, Subscription, Topic
from app.graph.importer import KNOWN_RELATION_TYPES, NODE_LABELS
from app.graph.schema import CONSTRAINTS
from app.graph_schema.registry import RELATIONS


def test_topic_and_subscription_carry_exactly_the_spec_fields():
    expected = {"id", "name", "protocol", "namespace"}
    assert set(Topic.model_fields) == expected
    assert set(Subscription.model_fields) == expected


def test_topic_and_subscription_optional_metadata_defaults_to_none():
    topic = Topic(id="topic:owned:" + "a" * 64, name="orders")
    subscription = Subscription(id="subscription:owned:" + "b" * 64, name="billing")
    assert (topic.protocol, topic.namespace) == (None, None)
    assert (subscription.protocol, subscription.namespace) == (None, None)


def test_pubsub_persistence_path_is_closed_until_slice_2():
    """I4 spec §11: "Slice 1 may add in-memory models/schema skeletons only; it SHALL persist no
    Pub/Sub node or relation." Persisting any Pub/Sub relation before the canonicalization-v3 bump
    is prohibited, so every persistence/NL-query entry point still excludes Pub/Sub here."""
    model_fields = set(ArchitectureModel.model_fields)
    assert not model_fields & {"topics", "subscriptions"}
    assert not {"Topic", "Subscription"} & set(NODE_LABELS.values())
    assert not {"PUBLISHES_TO", "SUBSCRIPTION_OF"} & set(KNOWN_RELATION_TYPES)
    assert not {"PUBLISHES_TO", "SUBSCRIPTION_OF"} & set(RELATIONS)
    for relation in RELATIONS.values():
        assert not {"Topic", "Subscription"} & (relation.source_labels | relation.target_labels)
    assert repository._CANONICALIZATION_VERSION == 2


def test_topic_and_subscription_uniqueness_constraints_are_declared():
    assert "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE" in (
        CONSTRAINTS
    )
    assert (
        "CREATE CONSTRAINT subscription_id IF NOT EXISTS "
        "FOR (s:Subscription) REQUIRE s.id IS UNIQUE"
    ) in CONSTRAINTS
