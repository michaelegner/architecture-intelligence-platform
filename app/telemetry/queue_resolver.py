from dataclasses import dataclass

import neo4j

_CANDIDATES_QUERY = "MATCH (q:Queue) RETURN q.id AS id, q.name AS name, q.namespace AS namespace"


@dataclass(frozen=True)
class DeclaredQueueCandidate:
    id: str
    name: str
    namespace: str | None


def fetch_queue_candidates(session: neo4j.Session) -> list[DeclaredQueueCandidate]:
    return [
        DeclaredQueueCandidate(id=record["id"], name=record["name"], namespace=record["namespace"])
        for record in session.run(_CANDIDATES_QUERY)
    ]
