from app.graph_schema.model import RelationDefinition

RELATIONS: dict[str, RelationDefinition] = {
    "PROVIDES": RelationDefinition(
        name="PROVIDES",
        source_labels=frozenset({"Service"}),
        target_labels=frozenset({"Operation"}),
    ),
    "CALLS": RelationDefinition(
        name="CALLS",
        source_labels=frozenset({"Service"}),
        target_labels=frozenset({"Operation"}),
    ),
    "REQUEST_SCHEMA": RelationDefinition(
        name="REQUEST_SCHEMA",
        source_labels=frozenset({"Operation"}),
        target_labels=frozenset({"Schema"}),
    ),
    "RESPONSE_SCHEMA": RelationDefinition(
        name="RESPONSE_SCHEMA",
        source_labels=frozenset({"Operation"}),
        target_labels=frozenset({"Schema"}),
    ),
    "SENDS": RelationDefinition(
        name="SENDS",
        source_labels=frozenset({"Service"}),
        target_labels=frozenset({"Queue"}),
    ),
    # v0.5.0 I4 spec §6.3: RECEIVES_FROM also targets a Subscription, CARRIES also leaves a Topic.
    "RECEIVES_FROM": RelationDefinition(
        name="RECEIVES_FROM",
        source_labels=frozenset({"Service"}),
        target_labels=frozenset({"Queue", "Subscription"}),
    ),
    "CARRIES": RelationDefinition(
        name="CARRIES",
        source_labels=frozenset({"Queue", "Topic"}),
        target_labels=frozenset({"Message"}),
    ),
    "PUBLISHES_TO": RelationDefinition(
        name="PUBLISHES_TO",
        source_labels=frozenset({"Service"}),
        target_labels=frozenset({"Topic"}),
    ),
    "SUBSCRIPTION_OF": RelationDefinition(
        name="SUBSCRIPTION_OF",
        source_labels=frozenset({"Subscription"}),
        target_labels=frozenset({"Topic"}),
    ),
    "CONFORMS_TO": RelationDefinition(
        name="CONFORMS_TO",
        source_labels=frozenset({"Message"}),
        target_labels=frozenset({"Schema"}),
    ),
    "DEAD_LETTERS_TO": RelationDefinition(
        name="DEAD_LETTERS_TO",
        source_labels=frozenset({"Queue"}),
        target_labels=frozenset({"Queue"}),
    ),
}
