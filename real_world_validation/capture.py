"""Projects AIP's actual canonical facts from a live Neo4j graph into RelationFacts (I1 §31 "AIP
Result Capture").

Adapted from evaluation/projector.py's proven query shape (v0.2's synthetic evaluation kernel) -
same raw-edges query, same 3-branch classified-status union reusing app.analysis.runtime's own
guard predicates, so status is always AIP's own definition of CONFIRMED/OBSERVED_ONLY/
NOT_OBSERVED_IN_WINDOW, never re-derived here (I1 §16: never repair or infer). Deliberately not
shared code with evaluation/projector.py: the two are separate methodology kernels (I1 §"three
similar lines beats a premature abstraction" precedent already set in model.py/loader.py), and this
module uses real_world_validation's own ScopeDeclaration rather than evaluation's ScenarioScope.

This module is the one place in real_world_validation/ that touches Neo4j - the loader/comparator/
reporter remain pure data-in/data-out, per I1 §19's "SHALL NOT consume upstream source directly
during comparison".
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import neo4j
import yaml

from app.analysis.runtime import (
    _DECLARED_EXISTS,
    _NOT_DECLARED_EXISTS,
    _NOT_OBSERVED_EXISTS,
    _OBSERVED_EXISTS,
    NOT_OBSERVED_IN_WINDOW,
)
from real_world_validation.model import RelationFact, ScopeDeclaration

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


# PROVIDES stays outside runtime-status classification, matching I2.1's own ground-truth decision
# (declared-only provider facts are never given a runtime status).
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


def capture_actual_facts(
    session: neo4j.Session,
    *,
    scope: ScopeDeclaration,
    environment: str,
    since: datetime,
    until: datetime | None = None,
) -> list[RelationFact]:
    """Projects the scope-owned subgraph into RelationFacts, labeled CONFIRMED/OBSERVED_ONLY/
    NOT_OBSERVED_IN_WINDOW by AIP's own classification at exact (type, source, target) identity, or
    left unclassified (e.g. PROVIDES) for anything else."""
    classified = _classified_facts(session, environment=environment, since=since, until=until)

    facts: list[RelationFact] = []
    for relation_type, source, target in _raw_edges(session):
        fact = classified.get(
            (relation_type, source, target),
            RelationFact(type=relation_type, source=source, target=target),
        )
        if scope.contains(fact):
            facts.append(fact)
    return facts


def _relation_dict(fact: RelationFact) -> dict:
    relation: dict = {"type": fact.type, "source": fact.source, "target": fact.target}
    if fact.status is not None:
        relation["status"] = fact.status
    evidence = {}
    if fact.declared_evidence is not None:
        evidence["declared"] = fact.declared_evidence
    if fact.observed_evidence is not None:
        evidence["observed"] = fact.observed_evidence
    if evidence:
        relation["evidence"] = evidence
    return relation


def write_actual_facts(path: Path, facts: list[RelationFact]) -> None:
    """Writes an actual-facts capture in real_world_validation.loader.load_actual's format,
    sorted for a deterministic diff between captures of the same qualifying run."""
    sorted_facts = sorted(facts, key=lambda f: (f.type, f.source, f.target))
    document = {"relations": [_relation_dict(f) for f in sorted_facts]}
    path.write_text(yaml.safe_dump(document, sort_keys=False))
