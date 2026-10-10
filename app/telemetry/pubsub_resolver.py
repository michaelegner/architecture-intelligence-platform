"""v0.5.0 I4 spec §9: declared Topic/Subscription candidates for runtime qualification.

Mirrors `app.telemetry.queue_resolver`'s candidate read and, like it, has no resolve/mint
function: runtime evidence may only qualify already-declared Topic/Subscription topology and SHALL
NOT mint an `OBSERVED_ONLY` Topic or Subscription (ADR 0017 #5). A Subscription candidate carries
the id of the Topic it is declared `SUBSCRIPTION_OF`, so Subscription matching is scoped to the
already-resolved Topic by construction.
"""

from dataclasses import dataclass

import neo4j

from app.qualification.declared_observed import declared_evidence_condition

_TOPIC_CANDIDATES_QUERY = (
    "MATCH (t:Topic) RETURN t.id AS id, t.name AS name, t.namespace AS namespace"
)
_SUBSCRIPTION_CANDIDATES_QUERY = (
    "MATCH (s:Subscription)-[:SUBSCRIPTION_OF]->(t:Topic) "
    "RETURN s.id AS id, s.name AS name, t.id AS topic_id"
)
# v0.6.2 I0 H1a: the (Service, Subscription) pairs that carry a declared RECEIVES_FROM.
_DECLARED_RECEIVERS_QUERY = (
    "MATCH (sv:Service)-[r:RECEIVES_FROM]->(s:Subscription) "
    "UNWIND coalesce(r.evidence_ids, []) AS eid "
    "MATCH (e:Evidence {id: eid}) "
    f"WHERE {declared_evidence_condition('e')} "
    "RETURN DISTINCT sv.id AS service_id, s.id AS subscription_id"
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


def fetch_declared_receivers(session: neo4j.Session) -> frozenset[tuple[str, str]]:
    """v0.6.2 I0 H1a: `(service_id, subscription_id)` pairs with a declared `RECEIVES_FROM`. A
    consumer span supports `RECEIVES_FROM -> Subscription` only for one of these pairs."""
    return frozenset(
        (record["service_id"], record["subscription_id"])
        for record in session.run(_DECLARED_RECEIVERS_QUERY)
    )
