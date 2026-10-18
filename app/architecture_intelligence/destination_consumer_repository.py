"""v0.7.1 I3.1: the one graph read of `get_destination_consumers` beyond the canonical snapshot state.

The Topic node records no broker, and its name is the channel name (an explicit Topic id is also
allowed), so "declared on this broker" is read from the Topic's internal `PubSubDeclaration`
carriers (owner decision). The read runs in the same revision-fenced stable-read attempt as the
state and returns only broker ids for the check; no declaration content is projected into the
snapshot state or the answer, which is why it lives outside `repository.py`.
"""

import neo4j

_TOPIC_DECLARATION_BROKERS_QUERY = (
    "MATCH (d:PubSubDeclaration {entity_kind: 'TOPIC', entity_id: $topic_id}) "
    "WHERE d.broker_id IS NOT NULL RETURN DISTINCT d.broker_id AS broker_id"
)


def read_topic_declaration_brokers(session: neo4j.Session, *, topic_id: str) -> frozenset[str]:
    return frozenset(
        record["broker_id"]
        for record in session.run(_TOPIC_DECLARATION_BROKERS_QUERY, topic_id=topic_id)
    )
