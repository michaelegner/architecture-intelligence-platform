"""Projects AIP's actual canonical facts from a live Neo4j graph into RelationFacts (I1 §31 "AIP
Result Capture").

PR #41 review F1/F2: every relation AIP writes carries real evidence (every declared-source adapter
attaches a DECLARED Provenance/evidence_ids to every relation it produces -
app/ingestion/openapi_adapter.py, app/ingestion/asyncapi_adapter.py - and AIP also has a genuine
"observed PROVIDES" concept for runtime-discovered operations, docs/graph-model.md). So this module
queries declared/observed evidence generically for AIP's complete current canonical relation
vocabulary (app.graph_schema.registry.RELATIONS - the same registry
real_world_validation.model.KNOWN_RELATION_TYPES already derives from), never omitting a type the
loader/comparator would otherwise accept. Only the three relation types AIP's own
app.analysis.runtime module defines genuine runtime-observation *status* semantics for
(CALLS/SENDS/RECEIVES_FROM, its O1-O4 CONFIRMED/OBSERVED_ONLY/NOT_OBSERVED_IN_WINDOW) get a
`status` value - the rest (PROVIDES, REQUEST_SCHEMA, RESPONSE_SCHEMA, CARRIES, CONFORMS_TO,
DEAD_LETTERS_TO) are always written by a declared-source adapter and never independently
reconfirmed by telemetry, so they report declared/observed evidence flags with no separate status
concept, matching how AIP's own analysis boundary treats them.

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
from app.graph_schema.registry import RELATIONS
from real_world_validation.model import RelationFact, ScopeDeclaration

# The only relation types AIP's own app.analysis.runtime module defines runtime-observation status
# semantics for (its O1-O4 CONFIRMED/OBSERVED_ONLY/NOT_OBSERVED_IN_WINDOW). Every other current
# canonical relation type is always written by a declared-source adapter and never independently
# reconfirmed by telemetry - see this module's docstring.
_RUNTIME_STATUS_RELATION_TYPES = frozenset({"CALLS", "SENDS", "RECEIVES_FROM"})
_EVIDENCE_ONLY_RELATION_TYPES = frozenset(RELATIONS) - _RUNTIME_STATUS_RELATION_TYPES


def _node_label(relation_type: str, *, source: bool) -> str:
    labels = (
        RELATIONS[relation_type].source_labels if source else RELATIONS[relation_type].target_labels
    )
    return next(iter(labels))


def _classified_branch(
    relation_type: str,
    declared_guard: str,
    observed_guard: str,
    status: str,
    *,
    declared: bool,
    observed: bool,
) -> str:
    source_label = _node_label(relation_type, source=True)
    target_label = _node_label(relation_type, source=False)
    declared_lit = "true" if declared else "false"
    observed_lit = "true" if observed else "false"
    return (
        f"MATCH (a:{source_label})-[r:{relation_type}]->(t:{target_label}) "
        f"WHERE {declared_guard} AND {observed_guard} "
        f"RETURN '{relation_type}' AS type, a.id AS source, t.id AS target, "
        f"'{status}' AS status, {declared_lit} AS declared, {observed_lit} AS observed"
    )


# Three branches per runtime-status relation type (mirrors app.analysis.runtime's own O1-O4
# semantics): CONFIRMED (declared+observed), OBSERVED_ONLY (not declared+observed), and
# NOT_OBSERVED_IN_WINDOW (declared+not observed).
_CLASSIFIED_QUERY = " UNION ".join(
    _classified_branch(
        relation_type,
        declared_guard,
        observed_guard,
        status,
        declared=is_declared,
        observed=is_observed,
    )
    for relation_type in sorted(_RUNTIME_STATUS_RELATION_TYPES)
    for declared_guard, observed_guard, status, is_declared, is_observed in [
        (_DECLARED_EXISTS, _OBSERVED_EXISTS, "CONFIRMED", True, True),
        (_NOT_DECLARED_EXISTS, _OBSERVED_EXISTS, "OBSERVED_ONLY", False, True),
        (_DECLARED_EXISTS, _NOT_OBSERVED_EXISTS, NOT_OBSERVED_IN_WINDOW, True, False),
    ]
)


def _evidence_branch(relation_type: str) -> str:
    source_label = _node_label(relation_type, source=True)
    target_label = _node_label(relation_type, source=False)
    return (
        f"MATCH (a:{source_label})-[r:{relation_type}]->(t:{target_label}) "
        f"RETURN '{relation_type}' AS type, a.id AS source, t.id AS target, "
        f"({_DECLARED_EXISTS}) AS declared, ({_OBSERVED_EXISTS}) AS observed"
    )


# Every other current canonical relation type: real declared/observed evidence flags (queried the
# same generic way app.analysis.runtime queries any relation's evidence_ids), no status concept.
_EVIDENCE_QUERY = " UNION ".join(
    _evidence_branch(relation_type) for relation_type in sorted(_EVIDENCE_ONLY_RELATION_TYPES)
)


def capture_actual_facts(
    session: neo4j.Session,
    *,
    scope: ScopeDeclaration,
    environment: str,
    since: datetime,
    until: datetime | None = None,
) -> list[RelationFact]:
    """Projects the scope-owned subgraph into RelationFacts, covering AIP's complete current
    canonical relation vocabulary (app.graph_schema.registry.RELATIONS). CALLS/SENDS/RECEIVES_FROM
    get AIP's own CONFIRMED/OBSERVED_ONLY/NOT_OBSERVED_IN_WINDOW status classification; every other
    relation type gets real declared/observed evidence flags with no status field."""
    facts: list[RelationFact] = []

    for row in session.run(_CLASSIFIED_QUERY, environment=environment, since=since, until=until):
        fact = RelationFact(
            type=row["type"],
            source=row["source"],
            target=row["target"],
            status=row["status"],
            declared_evidence=row["declared"],
            observed_evidence=row["observed"],
        )
        if scope.contains(fact):
            facts.append(fact)

    for row in session.run(_EVIDENCE_QUERY, environment=environment, since=since, until=until):
        fact = RelationFact(
            type=row["type"],
            source=row["source"],
            target=row["target"],
            declared_evidence=row["declared"],
            observed_evidence=row["observed"],
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
