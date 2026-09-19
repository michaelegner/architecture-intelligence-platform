"""v0.5.0 I3 slice 3 - read-only Neo4j access into I2's `InfrastructureEntity`/
`InfrastructureContribution` facts and declared `Service` existence, for
`app.architecture_intelligence.deployment_projection`'s Path A/B resolvers. Mirrors
`app.architecture_intelligence.repository`'s plain `session.run(...)` idiom (an already-open
`neo4j.Session`, no `driver`/`open_session` call here) - the first reader of I2's infrastructure
facts, which no repository module has read back until now (I2 itself never reads them; they were
write-only until this slice).

A live `:InfrastructureEntity`/`:InfrastructureContribution` node is, by construction, a *current*
fact: the importer's shared ownership/reconciliation machinery (`app.graph.importer`) deletes a
node outright once its `owner_source_ids` empties, so no separate "is this current" filter is
needed here - presence in the graph already means current.
"""

from __future__ import annotations

import neo4j

from app.architecture_intelligence.deployment_projection import (
    CurrentKubernetesWorkload,
    WorkloadContribution,
)

# PR #215 review finding (spec §3/§7/§29): a `:Service` node minted purely from telemetry
# (`app.telemetry.aggregator._MERGE_STUB_NODE_QUERY`, `ON CREATE SET n.discovery_status =
# 'OBSERVED_ONLY'`) must never qualify Path A/B deployment identity - only a declared Service can.
# A declared `Service` (`app.canonical.model.Service`, written via the normal `_write_nodes` import
# path) never sets `discovery_status` at all, so `coalesce(..., 'DECLARED')` treats an absent
# property as declared and excludes only the explicit 'OBSERVED_ONLY' stub.
_DECLARED_SERVICE_NAME_QUERY = (
    "MATCH (s:Service {id: $service_id}) "
    "WHERE coalesce(s.discovery_status, 'DECLARED') <> 'OBSERVED_ONLY' "
    "RETURN s.name AS name"
)

_WORKLOAD_BY_ID_QUERY = (
    "MATCH (e:InfrastructureEntity {id: $entity_id}) "
    "WHERE e.entity_kind = 'KUBERNETES_WORKLOAD' "
    "RETURN e.id AS id, e.resource_kind AS resource_kind, e.namespace AS namespace, "
    "e.name AS name"
)

# `OPTIONAL MATCH ... WHERE c.entity_id = e.id AND c.service_id_annotation IS NOT NULL` still
# yields one row per Workload with `c = null` when no contribution matches - `[x IN collect(c)
# WHERE x IS NOT NULL]` strips that null entry rather than collecting a single
# `{annotation: null, ...}` placeholder Path A would otherwise have to filter itself.
_CURRENT_KUBERNETES_WORKLOADS_QUERY = (
    "MATCH (e:InfrastructureEntity) WHERE e.entity_kind = 'KUBERNETES_WORKLOAD' "
    "OPTIONAL MATCH (c:InfrastructureContribution) "
    "WHERE c.entity_id = e.id AND c.service_id_annotation IS NOT NULL "
    "WITH e, [x IN collect(c) WHERE x IS NOT NULL] AS contributions "
    "RETURN e.id AS id, e.resource_kind AS resource_kind, e.namespace AS namespace, "
    "e.name AS name, contributions "
    "ORDER BY e.id"
)


def read_service_name(session: neo4j.Session, *, service_id: str) -> str | None:
    """`None` when no *declared* `Service` with this id currently exists - spec §7/§8.2's
    "annotation/mapping names a missing Service" case, and (PR #215 review) also spec §3/§7/§29's
    "an `OBSERVED_ONLY` Service cannot qualify deployment identity" case: a telemetry-minted stub
    Service is excluded exactly like a genuinely absent one."""
    record = session.run(_DECLARED_SERVICE_NAME_QUERY, service_id=service_id).single()
    return record["name"] if record is not None else None


def read_current_kubernetes_workload(
    session: neo4j.Session, *, entity_id: str
) -> CurrentKubernetesWorkload | None:
    """Exact point lookup by the Workload's own logical resource id
    (`app.sources.identity.kubernetes_logical_resource_id`), which carries a uniqueness constraint
    (`app.graph.schema`) - `None` when no current Workload matches (spec §8.2's "mapping -> missing
    Workload" case, including a wrong configured Kubernetes source id/cluster UID, which the
    caller already excludes before computing `entity_id`). `contributions` is left at its default
    empty tuple - Path B never needs a Workload's own annotation contributions.
    """
    record = session.run(_WORKLOAD_BY_ID_QUERY, entity_id=entity_id).single()
    if record is None:
        return None
    return CurrentKubernetesWorkload(
        workload_id=record["id"],
        workload_kind=record["resource_kind"],
        namespace=record["namespace"],
        name=record["name"],
    )


def iter_current_kubernetes_workloads(session: neo4j.Session) -> list[CurrentKubernetesWorkload]:
    """Every current I2 `KUBERNETES_WORKLOAD` entity, each paired with its own current
    `InfrastructureContribution` rows that carry a non-null `service_id_annotation` - Path A's full
    scan (spec §7 evaluates every current Workload, not just ones a caller names in advance, unlike
    Path B's mapping-artifact-driven lookups)."""
    workloads: list[CurrentKubernetesWorkload] = []
    for record in session.run(_CURRENT_KUBERNETES_WORKLOADS_QUERY):
        contributions = tuple(
            WorkloadContribution(
                annotation=node["service_id_annotation"],
                evidence_refs=tuple(node.get("evidence_refs") or ()),
            )
            for node in record["contributions"]
        )
        workloads.append(
            CurrentKubernetesWorkload(
                workload_id=record["id"],
                workload_kind=record["resource_kind"],
                namespace=record["namespace"],
                name=record["name"],
                contributions=contributions,
            )
        )
    return workloads
