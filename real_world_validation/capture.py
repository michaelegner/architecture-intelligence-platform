"""Projects AIP's actual canonical facts from a live Neo4j graph into RelationFacts (I1 §31 "AIP
Result Capture").

PR #41 review F1/F2: every relation AIP writes carries real evidence (every declared-source adapter
attaches a DECLARED Provenance/evidence_ids to every relation it produces -
app/ingestion/openapi_adapter.py, app/ingestion/asyncapi_adapter.py - and PROVIDES specifically can
also carry OBSERVED evidence for runtime-discovered operations, docs/graph-model.md/
app/telemetry/adapter.py). So this module queries declared/observed evidence generically for AIP's
complete current canonical relation vocabulary (app.graph_schema.registry.RELATIONS - the same
registry real_world_validation.model.KNOWN_RELATION_TYPES already derives from), never omitting a
type the loader/comparator would otherwise accept. Only the relation types with genuine
runtime-observation *status* semantics (CALLS/SENDS/RECEIVES_FROM, plus PUBLISHES_TO since v0.5.0
I5 Slice 1: CONFIRMED/OBSERVED_ONLY/NOT_OBSERVED_IN_WINDOW) get a `status` value - the others
(PROVIDES included) have no separate status concept, matching how
AIP's own analysis boundary treats them, but still get real declared/observed evidence flags -
REQUEST_SCHEMA/RESPONSE_SCHEMA/CARRIES/CONFORMS_TO/DEAD_LETTERS_TO are always written by a
declared-source adapter and never independently reconfirmed by telemetry at all (so they always
report observed=false in practice), while PROVIDES can genuinely be either.

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
from app.architecture_intelligence.request import ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph_schema.registry import RELATIONS
from real_world_validation.model import (
    DeploymentFact,
    RelationFact,
    ScopeDeclaration,
    WorkloadKey,
)

# The relation types with runtime-observation status semantics (CONFIRMED/OBSERVED_ONLY/
# NOT_OBSERVED_IN_WINDOW), from the shared declared-vs-observed kernel. v0.5.0 I5 Slice 1 adds
# PUBLISHES_TO, which is a messaging relation qualified by the same kernel rule (I4 §20 item 6).
# RECEIVES_FROM -> Subscription gets status through the label-pair expansion below. Every other
# canonical relation type still gets real declared/observed evidence flags, just no status. See this
# module's docstring for why PROVIDES, unlike the others, can genuinely have observed evidence.
_RUNTIME_STATUS_RELATION_TYPES = frozenset({"CALLS", "SENDS", "RECEIVES_FROM", "PUBLISHES_TO"})
_EVIDENCE_ONLY_RELATION_TYPES = frozenset(RELATIONS) - _RUNTIME_STATUS_RELATION_TYPES


def _label_pairs(relation_type: str) -> list[tuple[str, str]]:
    """Every admitted (source label, target label) pair for `relation_type`, in sorted order.

    v0.5.0 I5 §3 gap 1: this used to pick one label per endpoint with `next(iter(frozenset))`.
    Which label that returned depended on the string-hash seed, so a multi-label relation such as
    RECEIVES_FROM (Queue|Subscription) or CARRIES (Queue|Topic) was captured for only one label, and
    the choice could change between processes."""
    definition = RELATIONS[relation_type]
    return [
        (source_label, target_label)
        for source_label in sorted(definition.source_labels)
        for target_label in sorted(definition.target_labels)
    ]


def _classified_branch(
    relation_type: str,
    source_label: str,
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
        source_label,
        target_label,
        declared_guard,
        observed_guard,
        status,
        declared=is_declared,
        observed=is_observed,
    )
    for relation_type in sorted(_RUNTIME_STATUS_RELATION_TYPES)
    for source_label, target_label in _label_pairs(relation_type)
    for declared_guard, observed_guard, status, is_declared, is_observed in [
        (_DECLARED_EXISTS, _OBSERVED_EXISTS, "CONFIRMED", True, True),
        (_NOT_DECLARED_EXISTS, _OBSERVED_EXISTS, "OBSERVED_ONLY", False, True),
        (_DECLARED_EXISTS, _NOT_OBSERVED_EXISTS, NOT_OBSERVED_IN_WINDOW, True, False),
    ]
)


def _evidence_branch(relation_type: str, source_label: str, target_label: str) -> str:
    return (
        f"MATCH (a:{source_label})-[r:{relation_type}]->(t:{target_label}) "
        f"RETURN '{relation_type}' AS type, a.id AS source, t.id AS target, "
        f"({_DECLARED_EXISTS}) AS declared, ({_OBSERVED_EXISTS}) AS observed"
    )


# Every other current canonical relation type: real declared/observed evidence flags (queried the
# same generic way app.analysis.runtime queries any relation's evidence_ids), no status concept.
_EVIDENCE_QUERY = " UNION ".join(
    _evidence_branch(relation_type, source_label, target_label)
    for relation_type in sorted(_EVIDENCE_ONLY_RELATION_TYPES)
    for source_label, target_label in _label_pairs(relation_type)
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
    canonical relation vocabulary (app.graph_schema.registry.RELATIONS), over every admitted
    endpoint-label pair. CALLS/SENDS/RECEIVES_FROM/PUBLISHES_TO get AIP's own CONFIRMED/OBSERVED_ONLY/NOT_OBSERVED_IN_WINDOW status classification; every other
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


def capture_deployment_facts(
    service: ArchitectureIntelligenceService,
    *,
    scope: ScopeDeclaration,
    environment: str,
    since: datetime,
    until: datetime,
) -> list[DeploymentFact]:
    """v0.5.0 I5 §7: the public `DEPLOYED_AS` outcomes for every scoped `service:` entity, read only
    through `ArchitectureIntelligenceService`'s public deployment projection. `DEPLOYED_AS` is never
    a graph edge (I3), so it is never read from Neo4j directly.

    Each public `DeploymentResolution`, one per I3 §13.1 reconciliation candidate group, becomes
    one `DeploymentFact`. A `RESOLVED_*` resolution always names the same (Service, Workload) as its
    `DeploymentClaim`, so resolutions cover the claims too.

    A resolution whose `candidate_service_ids` names several scoped Services is returned in each of
    those Services' answers (I3 §13.4). It is recorded once, keyed by its `resolution_id`, because
    every answer here is read at the same snapshot and context."""
    facts: dict[str, DeploymentFact] = {}
    for service_id in sorted(e for e in scope.entities if e.startswith("service:")):
        answer = service.get_service_dependencies(
            ServiceDependenciesRequest.model_validate(
                {
                    "service_id": service_id,
                    "observation_context": {
                        "environment": environment,
                        "window_start": since,
                        "window_end": until,
                    },
                }
            )
        )
        if answer.data is None:
            continue
        for resolution in answer.data.deployment_resolutions:
            workload = resolution.workload
            facts.setdefault(
                resolution.resolution_id,
                DeploymentFact(
                    service=resolution.service_id,
                    workload=(
                        WorkloadKey(
                            namespace=workload.namespace,
                            kind=workload.workload_kind.value,
                            name=workload.name,
                        )
                        if workload is not None
                        else None
                    ),
                    status=resolution.status.value,
                    supporting_methods=tuple(m.value for m in resolution.supporting_methods),
                    candidate_service_ids=tuple(resolution.candidate_service_ids),
                    resolution_id=resolution.resolution_id,
                ),
            )
    return [facts[resolution_id] for resolution_id in sorted(facts)]


def _deployment_dict(fact: DeploymentFact) -> dict:
    workload = fact.workload
    return {
        "resolution_id": fact.resolution_id,
        "service": fact.service,
        "workload": (
            {"namespace": workload.namespace, "kind": workload.kind, "name": workload.name}
            if workload is not None
            else None
        ),
        "status": fact.status,
        "supporting_methods": list(fact.supporting_methods or ()),
        "candidate_service_ids": list(fact.candidate_service_ids or ()),
    }


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


def write_actual_facts(
    path: Path, facts: list[RelationFact], deployments: list[DeploymentFact] | None = None
) -> None:
    """Writes an actual-facts capture in real_world_validation.loader.load_actual's format,
    sorted for a deterministic diff between captures of the same qualifying run. `deployments`
    is written only when deployment capture ran (v0.5.0 I5), so an empty list stays distinct from
    "not captured"."""
    sorted_facts = sorted(facts, key=lambda f: (f.type, f.source, f.target))
    document: dict = {"relations": [_relation_dict(f) for f in sorted_facts]}
    if deployments is not None:
        document["deployments"] = [
            _deployment_dict(d)
            for d in sorted(
                deployments, key=lambda d: (d.identity, d.status, d.resolution_id or "")
            )
        ]
    path.write_text(yaml.safe_dump(document, sort_keys=False))
