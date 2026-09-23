"""v0.5.0 I4 (spec §6.2, §11, §15): the Topic/Subscription canonical foundation, and the guard
that the Pub/Sub persistence path opened (slice 2b) only together with canonicalization v3.

Slice 1 pinned the path closed; slice 2b opened it atomically - `ArchitectureModel`
Topic/Subscription lists, importer `NODE_LABELS`/`KNOWN_RELATION_TYPES`, the `graph_schema`
`RELATIONS` registry, dedicated Topic/Subscription canonicalization queries, and the
`_CANONICALIZATION_VERSION` 2 -> 3 bump - in one commit.
"""

from app.architecture_intelligence import repository
from app.canonical.model import ArchitectureModel, Subscription, Topic
from app.canonical.pubsub import (
    PUBSUB_DECLARATION_LABEL,
    SUBSCRIPTION_DEAD_LETTER_CONFIGURATION_LABEL,
)
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


def test_pubsub_persistence_path_is_open_and_bound_to_canonicalization_v3():
    """I4 spec §11: persisting any Pub/Sub relation before dedicated Topic/Subscription node
    queries and the canonicalization-v3 bump is prohibited - so the persistence path, the
    NL-query registry, and the v3 snapshot projection must all be present together."""
    model_fields = set(ArchitectureModel.model_fields)
    assert {"topics", "subscriptions"} <= model_fields
    assert NODE_LABELS["topics"] == "Topic"
    assert NODE_LABELS["subscriptions"] == "Subscription"
    assert {"PUBLISHES_TO", "SUBSCRIPTION_OF"} <= set(KNOWN_RELATION_TYPES)
    assert {"PUBLISHES_TO", "SUBSCRIPTION_OF"} <= set(RELATIONS)
    assert repository._CANONICALIZATION_VERSION == 3
    assert "MATCH (n:Topic)" in repository._TOPIC_QUERY
    assert "MATCH (n:Subscription)" in repository._SUBSCRIPTION_QUERY
    for relation_type in ("PUBLISHES_TO", "SUBSCRIPTION_OF"):
        assert relation_type in repository._SUPPORTING_RELATIONS_QUERY


def test_internal_pubsub_carriers_stay_out_of_public_and_nl_query_surfaces():
    """I4 spec §10/§12.6: the carriers are internal-only - not NL-query labels (the Cypher
    validator's allowlist is derived from NODE_LABELS) and not snapshot projections."""
    internal = {PUBSUB_DECLARATION_LABEL, SUBSCRIPTION_DEAD_LETTER_CONFIGURATION_LABEL}
    assert not internal & set(NODE_LABELS.values())
    for relation in RELATIONS.values():
        assert not internal & (relation.source_labels | relation.target_labels)
    snapshot_queries = " ".join(
        value
        for name, value in vars(repository).items()
        if name.endswith("_QUERY") and isinstance(value, str)
    )
    for label in internal:
        assert label not in snapshot_queries


def test_topic_and_subscription_uniqueness_constraints_are_declared():
    assert "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE" in (
        CONSTRAINTS
    )
    assert (
        "CREATE CONSTRAINT subscription_id IF NOT EXISTS "
        "FOR (s:Subscription) REQUIRE s.id IS UNIQUE"
    ) in CONSTRAINTS
