"""Canonical fact projection - the evaluator's one narrow Neo4j read boundary (spec I1 §14-15).

Design note (see the plan this iteration followed, and the I1 post-merge review's F1 finding):
status is determined purely by evaluating AIP's own declared/observed evidence predicates
(`_DECLARED_EXISTS`/`_NOT_DECLARED_EXISTS`/`_OBSERVED_EXISTS`/`_NOT_OBSERVED_EXISTS`, imported
verbatim from app.analysis.runtime - the exact Cypher fragments its own tested
`confirmed_relations()`/`observed_only_relations()`/`declared_only_relations()` use) - never by
inspecting evidence booleans in Python. That keeps this module free of any
`if declared and observed: status = ...`-shaped logic, which spec §4.6/I3 spec §4.3 explicitly
forbids the evaluator from containing.

I3 adds a third classification branch, `NOT_OBSERVED_IN_WINDOW` (declared, but no OBSERVED
evidence in the selected environment/window) - same guard-predicate reuse, same canonical identity
keying, no independent status derivation.

Unlike an earlier version of this module, classification is now keyed at true canonical relation
identity - (type, source, target) - not just (source, type). Reusing app.analysis.runtime's own
`confirmed_relations()`/`observed_only_relations()` functions directly isn't enough for this: for
CALLS, those functions intentionally resolve the target through the declared PROVIDES edge to the
*provider service* id (a display choice for human-readable runtime dependency lists - see their own
docstrings), which collapses distinct CALLS targets and doesn't match I1's canonical
`(Service)-[:CALLS]->(Operation)` identity. Querying directly with the same guard predicates, but
returning the raw Operation/Queue id every time, avoids that coalescing entirely while still using
AIP's own definition of what counts as CONFIRMED/OBSERVED_ONLY, unchanged.
"""

from __future__ import annotations

from datetime import datetime

import neo4j

from app.analysis.runtime import (
    _DECLARED_EXISTS,
    _NOT_DECLARED_EXISTS,
    _NOT_OBSERVED_EXISTS,
    _OBSERVED_EXISTS,
    NOT_OBSERVED_IN_WINDOW,
)
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


def _classified_branch(
    relation_type: str,
    target_label: str,
    declared_guard: str,
    observed_guard: str,
    status: str,
    *,
    declared: bool,
    observed: bool,
) -> str:
    declared_lit = "true" if declared else "false"
    observed_lit = "true" if observed else "false"
    return (
        f"MATCH (a:Service)-[r:{relation_type}]->(t:{target_label}) "
        f"WHERE {declared_guard} AND {observed_guard} "
        f"RETURN '{relation_type}' AS type, a.id AS source, t.id AS target, "
        f"'{status}' AS status, {declared_lit} AS declared, {observed_lit} AS observed"
    )


# Every branch shares the same $environment/$since/$until parameters (referenced inside
# _OBSERVED_EXISTS/_NOT_OBSERVED_EXISTS) - no relation type needs its own parameter shape.
#
# Three branches per relation type (I3 spec §7.2-7.4): CONFIRMED (declared+observed),
# OBSERVED_ONLY (not declared+observed), and NOT_OBSERVED_IN_WINDOW (declared+not observed) -
# added for CALLS/SENDS/RECEIVES_FROM, the same relation types this projector already
# runtime-classifies. PROVIDES stays outside the runtime-status branch (I3 spec §7.4).
_CLASSIFIED_QUERY = " UNION ".join(
    _classified_branch(
        relation_type,
        target_label,
        declared_guard,
        observed_guard,
        status,
        declared=is_declared,
        observed=is_observed,
    )
    for relation_type, target_label in [
        ("CALLS", "Operation"),
        ("SENDS", "Queue"),
        ("RECEIVES_FROM", "Queue"),
    ]
    for declared_guard, observed_guard, status, is_declared, is_observed in [
        (_DECLARED_EXISTS, _OBSERVED_EXISTS, "CONFIRMED", True, True),
        (_NOT_DECLARED_EXISTS, _OBSERVED_EXISTS, "OBSERVED_ONLY", False, True),
        (_DECLARED_EXISTS, _NOT_OBSERVED_EXISTS, NOT_OBSERVED_IN_WINDOW, True, False),
    ]
)


def _raw_edges(session: neo4j.Session) -> list[tuple[str, str, str]]:
    return [(r["type"], r["source"], r["target"]) for r in session.run(_RAW_EDGES_QUERY)]


def _classified_facts(
    session: neo4j.Session, *, environment: str, since: datetime, until: datetime | None
) -> dict[tuple[str, str, str], RelationFact]:
    classified: dict[tuple[str, str, str], RelationFact] = {}
    for row in session.run(_CLASSIFIED_QUERY, environment=environment, since=since, until=until):
        key = (row["type"], row["source"], row["target"])
        classified[key] = RelationFact(
            type=row["type"],
            source=row["source"],
            target=row["target"],
            status=row["status"],
            declared_evidence=row["declared"],
            observed_evidence=row["observed"],
        )
    return classified


def load_relation_facts(
    session: neo4j.Session,
    *,
    scope: ScenarioScope,
    environment: str | None,
    since: datetime,
    until: datetime | None = None,
) -> set[RelationFact]:
    """Projects the scenario-owned subgraph into RelationFacts, labeled CONFIRMED/OBSERVED_ONLY by
    AIP's own classification at exact (type, source, target) identity, or left unclassified (None)
    for anything else - outside what I1's three scenarios assert; see spec I1 §16.2 for what's
    deferred to I2."""
    classified = (
        _classified_facts(session, environment=environment, since=since, until=until)
        if environment is not None
        else {}
    )

    facts: set[RelationFact] = set()
    for relation_type, source, target in _raw_edges(session):
        fact = classified.get(
            (relation_type, source, target),
            RelationFact(type=relation_type, source=source, target=target),
        )
        if scope.contains(fact):
            facts.add(fact)
    return facts
