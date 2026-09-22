"""v0.5.0 I3 slices 3-4 - read-only Neo4j access into I2's `InfrastructureEntity`/
`InfrastructureContribution`/`InfrastructureClaim` facts, declared `Service` existence, and OTel
`RuntimeIdentityObservation` evidence, for `app.architecture_intelligence.deployment_projection`'s
Path A/B/C resolvers. Mirrors `app.architecture_intelligence.repository`'s plain `session.run(...)`
idiom (an already-open `neo4j.Session`, no `driver`/`open_session` call here) - the first reader of
I2's infrastructure facts (I2 itself never reads them; they were write-only until slice 3) and,
from slice 4 on, the first reader of `InfrastructureClaim` and `RuntimeIdentityObservation` rows
too.

A live `:InfrastructureEntity`/`:InfrastructureContribution`/`:InfrastructureClaim` node is, by
construction, a *current* fact: the importer's shared ownership/reconciliation machinery
(`app.graph.importer`) deletes a node outright once its `owner_source_ids` empties, so no separate
"is this current" filter is needed here - presence in the graph already means current. Every
function here is a pure read - none ever calls `app.telemetry.aggregator`'s or
`app.telemetry.service_resolver`'s own write/mint paths.
"""

from __future__ import annotations

from datetime import datetime

import neo4j

from app.architecture_intelligence.deployment_projection import (
    CapturedPodRow,
    CurrentKubernetesWorkload,
    DeclaredServiceIdentity,
    RuntimeIdentityObservationRow,
    WorkloadContribution,
    WorkloadOwnershipRow,
)

# PR #215 review finding (spec §3/§7/§29): a `:Service` node minted purely from telemetry
# (`app.telemetry.aggregator._MERGE_STUB_NODE_QUERY`) must never qualify Path A/B deployment
# identity - only a currently declared Service can. `discovery_status` is not authoritative here:
# if telemetry creates a stub first, the later canonical import's `SET n += $props` deliberately
# leaves that old property in place because `app.canonical.model.Service` has no such field.
# Canonical import ownership is the authoritative current-declaration signal instead: every
# declared node is claimed through `_MERGE_NODE_TEMPLATE.owner_source_ids`, while a telemetry-only
# stub has no owner. The normal reconciliation path removes ownership again when a declaration is
# withdrawn, so this also follows current rather than historical declaration state.
_DECLARED_SERVICE_NAME_QUERY = (
    "MATCH (s:Service {id: $service_id}) "
    "WHERE size(coalesce(s.owner_source_ids, [])) > 0 "
    "RETURN s.name AS name"
)

# Same `owner_source_ids` gate as `_DECLARED_SERVICE_NAME_QUERY`, additionally returning
# `namespace`/`version` for Path C's own §9.6 consistency checks. `s.namespace` mirrors
# `app.telemetry.service_resolver`'s own `_CANDIDATES_QUERY` read of the same property (not part of
# `app.canonical.model.Service`'s own field list - no current write path sets it, so it reads as
# `None` today; kept consistent with that existing precedent rather than assumed away).
_DECLARED_SERVICE_IDENTITY_QUERY = (
    "MATCH (s:Service {id: $service_id}) "
    "WHERE size(coalesce(s.owner_source_ids, [])) > 0 "
    "RETURN s.name AS name, s.namespace AS namespace, s.version AS version"
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

# I3 spec §9.5: `k8s.pod.uid` -> exactly one current CAPTURED_RESOURCE Pod contribution.
# `captured_resource_uid` is `None` for every `DECLARED_MANIFEST` contribution (see
# `app.canonical.infrastructure.InfrastructureContribution`'s own docstring), so a match here can
# only ever be a `CAPTURED_RESOURCE` row - no separate evidence-mode filter is needed. No
# `cluster_uid` filter by design: real Kubernetes Pod UIDs are globally-unique UUIDs, so a
# cross-cluster collision cannot occur with real evidence (a synthetic test fixture that reuses the
# same short literal UID across two different synthetic clusters would still correctly surface as
# AMBIGUOUS below, just not for the reason such a test might intend).
_CAPTURED_PODS_BY_UID_QUERY = (
    "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_POD'}) "
    "MATCH (c:InfrastructureContribution {entity_id: e.id}) "
    "WHERE c.captured_resource_uid = $pod_uid "
    "RETURN e.id AS pod_id, e.name AS pod_name, e.namespace AS pod_namespace, "
    "e.cluster_uid AS cluster_uid, c.captured_at AS captured_at, c.evidence_refs AS evidence_refs"
)

# I3 spec §9.5: exactly one current WORKLOAD_OWNS_POD claim naming this Pod as its object.
# `InfrastructureClaim.id = hash(kind, subject_id, object_id)` (`app.canonical.infrastructure`), so
# two rows here always name two genuinely distinct Workloads - no separate dedup is needed for the
# cardinality check this feeds. `evidence_refs` reads directly off the claim node's own property,
# which `app.graph.importer._recompute_infrastructure_claim_evidence` keeps as the live union of
# every current per-source `InfrastructureClaimContribution.evidence_refs` for this claim.
_WORKLOAD_OWNS_POD_QUERY = (
    "MATCH (c:InfrastructureClaim {kind: 'WORKLOAD_OWNS_POD', object_id: $pod_id}) "
    "RETURN c.subject_id AS workload_id, c.evidence_refs AS evidence_refs"
)

# I3 spec §9.7: filters by the requested observation context's environment and `last_seen` window
# in the query itself (both a query-scalability bound and the "not applicable to this context"
# exclusion spec's own applicability rule describes) - `resolve_path_c`'s own per-observation checks
# independently re-verify both, since a raw Neo4j row is never re-validated the way the write-side
# Pydantic model was, and the required §21.3 "absent"/"mismatch" cases are exercised at that level
# via hand-built fake rows.
_RUNTIME_IDENTITY_OBSERVATIONS_QUERY = (
    "MATCH (o:RuntimeIdentityObservation) "
    "WHERE o.environment = $environment "
    "AND o.last_seen >= $window_start AND o.last_seen <= $window_end "
    "RETURN o.id AS id, o.service_name AS service_name, o.service_namespace AS service_namespace, "
    "o.service_version AS service_version, o.environment AS environment, "
    "o.k8s_pod_uid AS k8s_pod_uid, o.k8s_pod_name AS k8s_pod_name, "
    "o.k8s_namespace_name AS k8s_namespace_name, o.k8s_cluster_uid AS k8s_cluster_uid, "
    "o.k8s_deployment_name AS k8s_deployment_name, "
    "o.k8s_statefulset_name AS k8s_statefulset_name, o.k8s_daemonset_name AS k8s_daemonset_name, "
    "o.last_seen AS last_seen, "
    "o.conflicting_consistency_attributes AS conflicting_consistency_attributes"
)


def read_service_name(session: neo4j.Session, *, service_id: str) -> str | None:
    """`None` when no *declared* `Service` with this id currently exists - spec §7/§8.2's
    "annotation/mapping names a missing Service" case, and (PR #215 review) also spec §3/§7/§29's
    "an `OBSERVED_ONLY` Service cannot qualify deployment identity" case. Current canonical-import
    ownership, not the telemetry marker, distinguishes a declared Service from a telemetry-only
    stub and correctly handles an observed-first Service that is declared later."""
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


def read_declared_service_identity(
    session: neo4j.Session, *, service_id: str
) -> DeclaredServiceIdentity | None:
    """`None` under the exact same authoritative "currently declared" gate as `read_service_name`
    - spec §9.2's "Path C succeeds only if the result is an existing declared AIP Service" case,
    reused for the identical reason (PR #215's `owner_source_ids` fix)."""
    record = session.run(_DECLARED_SERVICE_IDENTITY_QUERY, service_id=service_id).single()
    if record is None:
        return None
    return DeclaredServiceIdentity(
        service_id=service_id,
        name=record["name"],
        namespace=record["namespace"],
        version=record["version"],
    )


def read_captured_pods_by_uid(session: neo4j.Session, *, pod_uid: str) -> list[CapturedPodRow]:
    """Every current I2 `KUBERNETES_POD` contribution whose `captured_resource_uid` matches - spec
    §9.5's Pod-UID lookup. Zero, one, or more than one row; the caller (`resolve_path_c`) decides
    UNRESOLVED/continue/AMBIGUOUS from the returned count, mirroring how `resolve_path_a`/`_b`
    already let the pure layer own cardinality decisions rather than filtering here."""
    return [
        CapturedPodRow(
            pod_id=record["pod_id"],
            pod_name=record["pod_name"],
            pod_namespace=record["pod_namespace"],
            cluster_uid=record["cluster_uid"],
            captured_at=record["captured_at"],
            evidence_refs=tuple(record.get("evidence_refs") or ()),
        )
        for record in session.run(_CAPTURED_PODS_BY_UID_QUERY, pod_uid=pod_uid)
    ]


def read_workload_ids_owning_pod(
    session: neo4j.Session, *, pod_id: str
) -> list[WorkloadOwnershipRow]:
    """Every current `WORKLOAD_OWNS_POD` claim naming this Pod - spec §9.5's owner-chain lookup.
    The first-ever repository read of `InfrastructureClaim` (I2 never reads its own claims back;
    slice 3's Path A/B never needed to)."""
    return [
        WorkloadOwnershipRow(
            workload_id=record["workload_id"],
            evidence_refs=tuple(record.get("evidence_refs") or ()),
        )
        for record in session.run(_WORKLOAD_OWNS_POD_QUERY, pod_id=pod_id)
    ]


def read_runtime_identity_observations_in_window(
    session: neo4j.Session, *, environment: str, window_start: datetime, window_end: datetime
) -> list[RuntimeIdentityObservationRow]:
    """Every `RuntimeIdentityObservation` matching the requested environment with `last_seen`
    inside `[window_start, window_end]` - Path C's own full scan (spec §9 evaluates every
    applicable persisted observation, not just ones a caller names in advance, mirroring Path A's
    own full-scan shape rather than Path B's mapping-artifact-driven one)."""
    return [
        RuntimeIdentityObservationRow(
            id=record["id"],
            service_name=record["service_name"],
            service_namespace=record["service_namespace"],
            service_version=record["service_version"],
            environment=record["environment"],
            k8s_pod_uid=record["k8s_pod_uid"],
            k8s_pod_name=record["k8s_pod_name"],
            k8s_namespace_name=record["k8s_namespace_name"],
            k8s_cluster_uid=record["k8s_cluster_uid"],
            k8s_deployment_name=record["k8s_deployment_name"],
            k8s_statefulset_name=record["k8s_statefulset_name"],
            k8s_daemonset_name=record["k8s_daemonset_name"],
            last_seen=record["last_seen"].to_native() if record["last_seen"] is not None else None,
            conflicting_consistency_attributes=tuple(
                record.get("conflicting_consistency_attributes") or ()
            ),
        )
        for record in session.run(
            _RUNTIME_IDENTITY_OBSERVATIONS_QUERY,
            environment=environment,
            window_start=window_start,
            window_end=window_end,
        )
    ]
