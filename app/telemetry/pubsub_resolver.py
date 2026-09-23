"""v0.5.0 I4 spec §9: declared Topic/Subscription candidates for runtime qualification.

Mirrors `app.telemetry.queue_resolver`'s candidate read, but deliberately has no resolve/mint
function: runtime evidence may only qualify already-declared Topic/Subscription topology and SHALL
NOT mint an `OBSERVED_ONLY` Topic or Subscription (ADR 0017 #5). A Subscription candidate carries
the id of the Topic it is declared `SUBSCRIPTION_OF`, so Subscription matching is scoped to the
already-resolved Topic by construction.
"""

from dataclasses import dataclass

import neo4j

_TOPIC_CANDIDATES_QUERY = (
    "MATCH (t:Topic) RETURN t.id AS id, t.name AS name, t.namespace AS namespace"
)
_SUBSCRIPTION_CANDIDATES_QUERY = (
    "MATCH (s:Subscription)-[:SUBSCRIPTION_OF]->(t:Topic) "
    "RETURN s.id AS id, s.name AS name, t.id AS topic_id"
)


@dataclass(frozen=True)
class DeclaredTopicCandidate:
    id: str
    name: str
    namespace: str | None


@dataclass(frozen=True)
class DeclaredSubscriptionCandidate:
    id: str
    name: str
    topic_id: str


def fetch_topic_candidates(session: neo4j.Session) -> list[DeclaredTopicCandidate]:
    return [
        DeclaredTopicCandidate(id=record["id"], name=record["name"], namespace=record["namespace"])
        for record in session.run(_TOPIC_CANDIDATES_QUERY)
    ]


def fetch_subscription_candidates(session: neo4j.Session) -> list[DeclaredSubscriptionCandidate]:
    return [
        DeclaredSubscriptionCandidate(
            id=record["id"], name=record["name"], topic_id=record["topic_id"]
        )
        for record in session.run(_SUBSCRIPTION_CANDIDATES_QUERY)
    ]
