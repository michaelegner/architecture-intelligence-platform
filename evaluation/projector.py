"""Canonical fact projection - the evaluator's one narrow Neo4j read boundary (spec I1 §14-15).

Design note (see the plan this iteration followed): status is determined purely by *membership* in
AIP's own `confirmed_relations()`/`observed_only_relations()` output (app.analysis.runtime, already
tested and used by the real `/api/analysis/runtime/*` endpoints) - never by inspecting evidence
booleans in this module. That keeps this file free of any `if declared and observed: status = ...`
-shaped logic, which spec §4.6 explicitly forbids the evaluator from containing.

Target identity is read separately, directly off the raw persisted edge. This matters only for
CALLS: confirmed_relations()/observed_only_relations() resolve a CALLS target through the declared
PROVIDES edge to the *provider service* id (a display choice for human-readable runtime dependency
lists - see their own docstrings), but I1's canonical model needs the raw
`(Service)-[:CALLS]->(Operation)` target, i.e. the operation id. Reading that id directly off the
persisted edge is a pure identifier lookup, not a semantic derivation (spec §15 explicitly allows
"map canonical IDs into stable strings"). SENDS/RECEIVES_FROM have no such quirk - their O2/O3
target_id is already the raw Queue id - so they need no extra lookup.
"""

from __future__ import annotations

from datetime import datetime

import neo4j

from app.analysis.runtime import confirmed_relations, observed_only_relations
from evaluation.model import RelationFact, ScenarioScope

_RAW_EDGES_QUERY = (
    "MATCH (a:Service)-[:CALLS]->(o:Operation) RETURN 'CALLS' AS type, a.id AS source, o.id AS target "
    "UNION "
    "MATCH (a:Service)-[:PROVIDES]->(o:Operation) "
    "RETURN 'PROVIDES' AS type, a.id AS source, o.id AS target "
    "UNION "
    "MATCH (a:Service)-[:SENDS]->(q:Queue) RETURN 'SENDS' AS type, a.id AS source, q.id AS target "
    "UNION "
    "MATCH (a:Service)-[:RECEIVES_FROM]->(q:Queue) "
    "RETURN 'RECEIVES_FROM' AS type, a.id AS source, q.id AS target"
)


def _raw_edges(session: neo4j.Session) -> list[tuple[str, str, str]]:
    return [(r["type"], r["source"], r["target"]) for r in session.run(_RAW_EDGES_QUERY)]


def load_relation_facts(
    session: neo4j.Session,
    *,
    scope: ScenarioScope,
    environment: str | None,
    since: datetime,
    until: datetime | None = None,
) -> set[RelationFact]:
    """Projects the scenario-owned subgraph into RelationFacts, labeled CONFIRMED/OBSERVED_ONLY by
    AIP's own classification (or left unclassified - None - for anything else, which is outside
    what I1's three scenarios assert; see spec I1 §16.2 for what's deferred to I2)."""
    confirmed_keys: set[tuple[str, str]] = set()
    observed_only_keys: set[tuple[str, str]] = set()
    if environment is not None:
        confirmed_keys = {
            (r.source_id, r.relation_type)
            for r in confirmed_relations(session, environment=environment, since=since, until=until)
        }
        observed_only_keys = {
            (r.source_id, r.relation_type)
            for r in observed_only_relations(
                session, environment=environment, since=since, until=until
            )
        }

    facts: set[RelationFact] = set()
    for relation_type, source, target in _raw_edges(session):
        fact = RelationFact(type=relation_type, source=source, target=target)
        if not scope.contains(fact):
            continue

        key = (source, relation_type)
        if key in confirmed_keys:
            fact = RelationFact(
                type=relation_type,
                source=source,
                target=target,
                status="CONFIRMED",
                declared_evidence=True,
                observed_evidence=True,
            )
        elif key in observed_only_keys:
            fact = RelationFact(
                type=relation_type,
                source=source,
                target=target,
                status="OBSERVED_ONLY",
                declared_evidence=False,
                observed_evidence=True,
            )
        facts.add(fact)
    return facts
