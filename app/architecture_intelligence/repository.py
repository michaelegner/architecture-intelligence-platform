"""v0.4.0 I1.2/I1.3 - canonical snapshot projection, fingerprinting, the bounded stable-read retry
(spec §17/§18/§19.1), and the request-scoped dependency-projection read (spec §13).

This is the `ArchitectureReadRepository` the I1 spec's architecture diagram places between
`ArchitectureIntelligenceService` and Neo4j - it owns only read mechanics and raw graph projection
(spec §7). Neither this module nor its callers may decide public outcome semantics or return an
`ArchitectureAnswer`; `app.architecture_intelligence.dependency_projection` and `.service` own that.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import neo4j

from app.analysis.runtime import telemetry_coverage
from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import DEPLOYMENT_RECONCILIATION_RULE_ID
from app.canonical.infrastructure import KUBERNETES_SOURCE_TYPE
from app.graph.revision_fence import read_revision
from app.sources.service_workload_mapping import ServiceWorkloadMappingDocument

# Mirrors `deployment_projection._RECONCILIATION_RULE_VERSION` - kept as its own local constant
# rather than importing that module's private name; both must move together if the rule version
# ever bumps (a reviewed spec change either way, per that module's own comment).
_DEPLOYMENT_RECONCILIATION_RULE_VERSION = 1

# Bumping this - or changing any query/rule below - is a snapshot-fingerprint contract change and
# MUST be recorded explicitly (spec §18). Not bumped for the PR #215 mapping-artifact-binding
# addition below: that addition is purely conditional on a real caller supplying a document (no
# caller does yet - I3 slice 5 wires that), so every existing caller's hashed state is byte-
# identical to before, and every already-frozen snapshot_id in this repo's independently-authored
# evaluation fixtures stays valid. See `canonical_snapshot_state`'s own comment.
#
# v0.5.0 I3 slice 5b bumps this 1 -> 2 (spec §17): the deployment-relevant state below now
# genuinely affects public answers for a request that configures/observes it, so every existing
# fixture's own `snapshot_id` moves *only if* that fixture's graph actually contains Kubernetes/
# OTel-runtime-identity/mapping-artifact state - a request with none of that present hashes the
# same new-but-empty keys every time, which is itself still a real, deliberate fingerprint change
# per this comment's own "MUST be recorded explicitly" rule, not an oversight.
_CANONICALIZATION_VERSION = 2

_SERVICE_QUERY = "MATCH (n:Service) RETURN n.id AS id, n.name AS name, n.version AS version"
_OPERATION_QUERY = (
    "MATCH (n:Operation) RETURN n.id AS id, n.name AS name, n.service_id AS service_id, "
    "n.operation_id AS operation_id, n.method AS method, n.path AS path, "
    "n.request_schema_ids AS request_schema_ids, n.response_schema_ids AS response_schema_ids, "
    "n.discovery_status AS discovery_status"
)
_QUEUE_QUERY = (
    "MATCH (n:Queue) RETURN n.id AS id, n.name AS name, n.protocol AS protocol, "
    "n.namespace AS namespace, n.queue_type AS queue_type, n.discovery_status AS discovery_status"
)
_MESSAGE_QUERY = (
    "MATCH (n:Message) RETURN n.id AS id, n.name AS name, n.version AS version, "
    "n.schema_id AS schema_id"
)
_SCHEMA_QUERY = (
    "MATCH (n:Schema) RETURN n.id AS id, n.name AS name, n.version AS version, "
    "n.format AS format, n.canonical_hash AS canonical_hash"
)
# I2 Draft 0.2 §9 (amended): evidence from a Kubernetes source supports only internal-only
# infrastructure entities/contributions/claims, none of which this projection exposes - so the
# evidence itself stays internal too. Without this filter, merely configuring a Kubernetes source
# would change the public snapshot fingerprint every MCP answer carries.
_EVIDENCE_QUERY = (
    f"MATCH (n:Evidence) WHERE n.source_type <> '{KUBERNETES_SOURCE_TYPE}' "
    "RETURN n.id AS id, n.source_type AS source_type, "
    "n.source_file AS source_file, n.source_revision AS source_revision, "
    "n.evidence_type AS evidence_type, n.environment AS environment, "
    "n.bucket_start AS bucket_start, n.bucket_end AS bucket_end, n.first_seen AS first_seen, "
    "n.last_seen AS last_seen, n.observation_count AS observation_count, "
    "n.sample_trace_ids AS sample_trace_ids, n.service_version AS service_version, "
    "n.correlation_mode AS correlation_mode"
)
_RELATION_QUERY = (
    "MATCH (a)-[r]->(b) RETURN type(r) AS type, a.id AS source_id, b.id AS target_id, "
    "r.evidence_ids AS evidence_ids"
)

# v0.5.0 I3 slice 5b (spec §17): the deployment-relevant state a public `DEPLOYED_AS` answer can
# now depend on, bound into the fingerprint the same way every other public-answer input already
# is. Scoped to exactly what Path A/B/C's own resolvers read (`deployment_repository.py`'s live
# request-scoped equivalents of these same three queries) - not I2's full infrastructure graph.
#
# "Current supported Workload identity" + "retained explicit Service-ID annotation values" (spec
# §17's first and fourth bullets) are naturally one query: an annotation lives on a Workload's own
# contribution. `evidence_refs` is included (not just the annotation string) so a changed
# underlying evidence id - itself derived from `(source_type, pointer, revision)`, see
# `app.ingestion.kubernetes_adapter._mint_evidence` - moves the snapshot even if the annotation
# value and Workload identity are otherwise unchanged.
_DEPLOYMENT_WORKLOADS_QUERY = (
    "MATCH (e:InfrastructureEntity) WHERE e.entity_kind = 'KUBERNETES_WORKLOAD' "
    "OPTIONAL MATCH (c:InfrastructureContribution) "
    "WHERE c.entity_id = e.id AND c.service_id_annotation IS NOT NULL "
    "WITH e, [x IN collect(c) WHERE x IS NOT NULL] AS contributions "
    "RETURN e.id AS id, e.resource_kind AS resource_kind, e.namespace AS namespace, "
    "e.name AS name, "
    "[c IN contributions | {annotation: c.service_id_annotation, "
    "evidence_refs: coalesce(c.evidence_refs, [])}] AS annotations"
)

# spec §17's second bullet: "current captured Pod UID bindings used by I3" - every current
# CAPTURED_RESOURCE Pod contribution, full scan (Path C's own live read,
# `deployment_repository.read_captured_pods_by_uid`, is a point lookup by UID; this is its
# canonicalization-time full-scan equivalent).
_DEPLOYMENT_CAPTURED_PODS_QUERY = (
    "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_POD'}) "
    "MATCH (c:InfrastructureContribution {entity_id: e.id}) "
    "WHERE c.captured_resource_uid IS NOT NULL "
    "RETURN e.id AS id, c.captured_resource_uid AS captured_resource_uid, "
    "c.captured_at AS captured_at, coalesce(c.evidence_refs, []) AS evidence_refs"
)

# spec §17's third bullet: "current WORKLOAD_OWNS_POD links used by I3" - full scan, canonicalizing
# `deployment_repository.read_workload_ids_owning_pod`'s own point-lookup equivalent.
_DEPLOYMENT_WORKLOAD_OWNS_POD_QUERY = (
    "MATCH (c:InfrastructureClaim {kind: 'WORKLOAD_OWNS_POD'}) "
    "RETURN c.id AS id, c.subject_id AS workload_id, c.object_id AS pod_id, "
    "coalesce(c.evidence_refs, []) AS evidence_refs"
)

# spec §17's sixth bullet: "bounded OTel runtime identity observations" - the exact same rows
# `deployment_repository.read_runtime_identity_observations` already reads for Path C.
_DEPLOYMENT_RUNTIME_IDENTITY_OBSERVATIONS_QUERY = (
    "MATCH (o:RuntimeIdentityObservation) "
    "RETURN o.id AS id, o.service_name AS service_name, o.service_namespace AS service_namespace, "
    "o.service_version AS service_version, o.environment AS environment, "
    "o.k8s_pod_uid AS k8s_pod_uid, o.k8s_pod_name AS k8s_pod_name, "
    "o.k8s_namespace_name AS k8s_namespace_name, o.k8s_cluster_uid AS k8s_cluster_uid, "
    "o.k8s_deployment_name AS k8s_deployment_name, "
    "o.k8s_statefulset_name AS k8s_statefulset_name, o.k8s_daemonset_name AS k8s_daemonset_name, "
    "o.last_seen AS last_seen, o.first_seen AS first_seen, "
    "o.observation_count AS observation_count, "
    "o.conflicting_consistency_attributes AS conflicting_consistency_attributes"
)

# neo4j.time.DateTime isn't a datetime.datetime - convert to native so canonical_json_bytes'
# datetime handling applies (same conversion app.telemetry.aggregator._read_existing_evidence uses).
_DATETIME_FIELDS = frozenset({"bucket_start", "bucket_end", "first_seen", "last_seen"})
# Set-valued properties (spec §18: "set-valued arrays sorted and deduplicated").
_LIST_FIELDS = frozenset(
    {
        "request_schema_ids",
        "response_schema_ids",
        "sample_trace_ids",
        "evidence_ids",
        "conflicting_consistency_attributes",
    }
)


def _project_row(record: neo4j.Record) -> dict:
    """Projects one record to a plain dict, excluding Neo4j element ids and record order (only
    the allowlisted RETURN columns exist at all), dropping any null/absent property rather than
    keeping it as an explicit null (spec §18's one chosen null/absent normalization rule), and
    normalizing set-valued and temporal properties."""
    row = {}
    for key, value in record.items():
        if value is None:
            continue
        if key in _DATETIME_FIELDS:
            value = value.to_native()
        elif key in _LIST_FIELDS:
            value = sorted(set(value))
        row[key] = value
    return row


def _project_nodes(session: neo4j.Session, query: str) -> list[dict]:
    """Node arrays sorted by id (spec §18's "(type, id)" - type is constant within one label's
    own list here, so sorting by id alone is equivalent)."""
    return sorted(
        (_project_row(record) for record in session.run(query)), key=lambda row: row["id"]
    )


def _project_relations(session: neo4j.Session) -> list[dict]:
    rows = [_project_row(record) for record in session.run(_RELATION_QUERY)]
    return sorted(rows, key=lambda row: (row["type"], row["source_id"], row["target_id"]))


def _project_deployment_workloads(session: neo4j.Session) -> list[dict]:
    """spec §17's "current supported Workload identity" + "retained explicit Service-ID annotation
    values" bullets, combined (see `_DEPLOYMENT_WORKLOADS_QUERY`'s own comment for why)."""
    rows = []
    for record in session.run(_DEPLOYMENT_WORKLOADS_QUERY):
        row = {
            "id": record["id"],
            "resource_kind": record["resource_kind"],
            "namespace": record["namespace"],
            "name": record["name"],
        }
        annotations = sorted(
            (
                {
                    "annotation": a["annotation"],
                    "evidence_refs": sorted(set(a["evidence_refs"])),
                }
                for a in record["annotations"]
            ),
            key=lambda a: (a["annotation"], tuple(a["evidence_refs"])),
        )
        if annotations:
            row["annotations"] = annotations
        rows.append(row)
    return sorted(rows, key=lambda row: row["id"])


def _project_deployment_captured_pods(session: neo4j.Session) -> list[dict]:
    """spec §17's "current captured Pod UID bindings used by I3" bullet."""
    rows = [
        {
            "id": record["id"],
            "captured_resource_uid": record["captured_resource_uid"],
            "captured_at": record["captured_at"],
            "evidence_refs": sorted(set(record["evidence_refs"])),
        }
        for record in session.run(_DEPLOYMENT_CAPTURED_PODS_QUERY)
    ]
    return sorted(rows, key=lambda row: row["id"])


def _project_deployment_workload_owns_pod(session: neo4j.Session) -> list[dict]:
    """spec §17's "current WORKLOAD_OWNS_POD links used by I3" bullet."""
    rows = [
        {
            "id": record["id"],
            "workload_id": record["workload_id"],
            "pod_id": record["pod_id"],
            "evidence_refs": sorted(set(record["evidence_refs"])),
        }
        for record in session.run(_DEPLOYMENT_WORKLOAD_OWNS_POD_QUERY)
    ]
    return sorted(rows, key=lambda row: row["id"])


def _semantic_config_state(
    *,
    coverage_qualification_enabled: bool,
    service_workload_mapping_document: ServiceWorkloadMappingDocument | None,
) -> dict:
    """I3 spec §8.3: "Changing the mapping artifact content SHALL change the I3 reconciliation
    context and public snapshot identity even if no source document or Kubernetes bundle changes."
    §17 repeats this as a general snapshot-binding requirement, and §23 lists "snapshot binding of
    mapping digest" as in-scope for slice 3 itself (PR #215 review finding: the first version of
    this slice bound only the mapping *evidence* id, never the snapshot/reconciliation-context
    identity `resolve_path_b` itself receives as a caller-supplied opaque string).

    `service_workload_mapping_artifact` is omitted entirely (not merely set to `null`) when
    `service_workload_mapping_document is None` - deliberately, so `semantic_config`'s hashed JSON
    shape for every existing caller (none of which passes a real document yet; I3 slice 5 wires
    that) stays byte-identical to before this addition, and no already-frozen snapshot_id in this
    repo's independently-authored evaluation fixtures moves. Only a caller that actually supplies a
    configured artifact changes the fingerprint, exactly as intended.
    """
    semantic_config = {"coverage_qualification_enabled": coverage_qualification_enabled}
    if service_workload_mapping_document is not None:
        semantic_config["service_workload_mapping_artifact"] = {
            "artifact_id": service_workload_mapping_document.artifact_id,
            "artifact_revision": service_workload_mapping_document.artifact_revision,
            "content_digest": service_workload_mapping_document.content_digest,
        }
    return semantic_config


def canonical_snapshot_state(
    session: neo4j.Session,
    *,
    coverage_qualification_enabled: bool,
    service_workload_mapping_document: ServiceWorkloadMappingDocument | None = None,
) -> dict:
    """The complete queryable canonical model-and-evidence state, as an allowlisted (spec §18),
    canonically-ordered plain dict ready for `canonical_json_bytes`. Excludes Neo4j element ids,
    read/insertion order, relation `.key`, reconciliation-only `.owner_source_ids` arrays, and the
    internal revision-fence value - none of those are ever selected by the queries above in the
    first place, so there is nothing further to strip here.

    `service_workload_mapping_document` is the currently configured I3 Path B artifact (or `None`),
    supplied by the caller rather than read from Neo4j here, mirroring `coverage_qualification_
    enabled`'s own "externally configured semantic value" shape - see `_semantic_config_state`.
    """
    return {
        "version": _CANONICALIZATION_VERSION,
        "services": _project_nodes(session, _SERVICE_QUERY),
        "operations": _project_nodes(session, _OPERATION_QUERY),
        "queues": _project_nodes(session, _QUEUE_QUERY),
        "messages": _project_nodes(session, _MESSAGE_QUERY),
        "schemas": _project_nodes(session, _SCHEMA_QUERY),
        "evidence": _project_nodes(session, _EVIDENCE_QUERY),
        "relations": _project_relations(session),
        "semantic_config": _semantic_config_state(
            coverage_qualification_enabled=coverage_qualification_enabled,
            service_workload_mapping_document=service_workload_mapping_document,
        ),
        # v0.5.0 I3 slice 5b (spec §17): deployment-relevant state a public DEPLOYED_AS answer can
        # now depend on. Deliberately does NOT include a separately-computed "reachable evidence
        # id"/reconciliation-output key: that would be circular (resolution_id/claim_id are
        # themselves hashed from snapshot_id, which this function's own return value determines -
        # see this slice's plan, Open Questions #3) and is redundant anyway, since reachability is
        # a pure function of exactly the raw facts already bound below (services, these four keys,
        # and the mapping-artifact digest already carried in semantic_config) - two states with
        # identical values for all of those always reduce to identical claims/reachability, by
        # construction. The `service-workload-reconciliation` rule id/version is included directly
        # so a future rule-version bump is itself a recorded fingerprint change even if no query
        # above it also changes.
        "deployment_workloads": _project_deployment_workloads(session),
        "deployment_captured_pods": _project_deployment_captured_pods(session),
        "deployment_workload_owns_pod": _project_deployment_workload_owns_pod(session),
        "deployment_runtime_identity_observations": _project_nodes(
            session, _DEPLOYMENT_RUNTIME_IDENTITY_OBSERVATIONS_QUERY
        ),
        "deployment_reconciliation_rule": {
            "rule_id": DEPLOYMENT_RECONCILIATION_RULE_ID,
            "rule_version": _DEPLOYMENT_RECONCILIATION_RULE_VERSION,
        },
    }


def snapshot_fingerprint(state: dict) -> tuple[str, str]:
    """`(snapshot_id, model_revision)` sharing one digest under different public prefixes (spec
    §17) - this is what guarantees `SnapshotRef`'s digest-consistency check always holds."""
    digest = hashlib.sha256(canonical_json_bytes(state)).hexdigest()
    return f"aip:snapshot:v1:{digest}", f"sha256:{digest}"


class SnapshotUnstable(RuntimeError):
    """Raised when `max_attempts` reads couldn't observe one consistent committed state (spec
    §19.1). The caller (I1.3's service layer) is expected to translate this to
    `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE`."""


@dataclass(frozen=True)
class StableSnapshot[T]:
    snapshot_id: str
    model_revision: str
    extra: T


def read_stable_snapshot[T](
    read_revision_fn: Callable[[], int],
    read_state: Callable[[], dict],
    read_extra: Callable[[], T],
    *,
    max_attempts: int = 3,
) -> StableSnapshot[T]:
    """spec §19.1's stable-read algorithm: read revision, read state, read extra, read revision
    again, accept only if both revisions match, otherwise discard everything and retry.

    Parameterized over its three reads (rather than taking a session directly) so the retry/discard
    behavior is unit-testable with fake reads instead of needing a real concurrent-write race - see
    `read_stable_snapshot_from_session` for the Neo4j-backed wiring.
    """
    for _ in range(max_attempts):
        revision_before = read_revision_fn()
        state = read_state()
        extra = read_extra()
        revision_after = read_revision_fn()
        if revision_before == revision_after:
            snapshot_id, model_revision = snapshot_fingerprint(state)
            return StableSnapshot(
                snapshot_id=snapshot_id, model_revision=model_revision, extra=extra
            )
    raise SnapshotUnstable(f"no consistent snapshot after {max_attempts} attempts")


def read_stable_snapshot_from_session[T](
    session: neo4j.Session,
    *,
    coverage_qualification_enabled: bool,
    service_workload_mapping_document: ServiceWorkloadMappingDocument | None = None,
    read_extra: Callable[[neo4j.Session], T] = lambda _session: None,
    max_attempts: int = 3,
) -> StableSnapshot[T]:
    """I1.2 has no request-specific data yet, so `read_extra` defaults to a no-op; I1.3 passes its
    dependency-projection read here unchanged, reusing this same retry loop rather than
    duplicating it. `service_workload_mapping_document` defaults to `None` - no caller loads and
    passes a real Path B artifact yet (I3 slice 5 wires that); the parameter exists now so the
    snapshot-binding mechanism itself is real and tested ahead of that wiring."""
    return read_stable_snapshot(
        read_revision_fn=lambda: read_revision(session),
        read_state=lambda: canonical_snapshot_state(
            session,
            coverage_qualification_enabled=coverage_qualification_enabled,
            service_workload_mapping_document=service_workload_mapping_document,
        ),
        read_extra=lambda: read_extra(session),
        max_attempts=max_attempts,
    )


# --- I1.3: request-scoped dependency-projection read (spec §13) --------------------------------
#
# Deliberately small, targeted queries in the style of app.analysis.runtime rather than reusing
# the full-graph canonical_snapshot_state above: that state exists to fingerprint the *entire*
# queryable graph for the snapshot, not to double as the data source for a single service's
# question. Every query here is passed as this call's `read_extra` (see service.py), so it runs
# inside the same stable-read attempt - and therefore observes the same committed state - as the
# fingerprinted state used to compute snapshot_id/model_revision (spec §19: "snapshot and answer
# can observe different committed states" is a release blocker).

_SERVICE_NAME_QUERY = "MATCH (s:Service {id: $service_id}) RETURN s.name AS name"

_CALLS_QUERY = (
    "MATCH (a:Service {id: $service_id})-[r:CALLS]->(o:Operation) "
    "RETURN o.id AS operation_id, o.name AS operation_name, o.method AS method, o.path AS path, "
    "coalesce(r.evidence_ids, []) AS evidence_ids"
)
_PROVIDES_FOR_OPERATIONS_QUERY = (
    "MATCH (p:Service)-[r:PROVIDES]->(o:Operation) WHERE o.id IN $operation_ids "
    "RETURN o.id AS operation_id, p.id AS provider_id, p.name AS provider_name, "
    "coalesce(r.evidence_ids, []) AS evidence_ids"
)
_SENDS_QUERY = (
    "MATCH (a:Service {id: $service_id})-[r:SENDS]->(q:Queue) "
    "RETURN q.id AS queue_id, q.name AS queue_name, q.protocol AS protocol, "
    "q.namespace AS namespace, coalesce(r.evidence_ids, []) AS evidence_ids"
)
_RECEIVES_FOR_QUEUES_QUERY = (
    "MATCH (c:Service)-[r:RECEIVES_FROM]->(q:Queue) WHERE q.id IN $queue_ids "
    "RETURN q.id AS queue_id, c.id AS consumer_id, c.name AS consumer_name, "
    "coalesce(r.evidence_ids, []) AS evidence_ids"
)
_EVIDENCE_FOR_IDS_QUERY = (
    "MATCH (e:Evidence) WHERE e.id IN $evidence_ids "
    "RETURN e.id AS id, e.evidence_type AS evidence_type, e.environment AS environment, "
    "e.last_seen AS last_seen"
)


def _referenced_evidence_ids(*row_groups: list[dict]) -> list[str]:
    return sorted({eid for rows in row_groups for row in rows for eid in row["evidence_ids"]})


# --- I2.3: request-scoped evidence-lookup read (spec §11/§13) -----------------------------------
#
# Deliberately excludes `sample_trace_ids` - spec §11.2 explicitly keeps it out of the public
# `EvidenceRecord` contract, unlike `_EVIDENCE_QUERY` above which selects it for internal
# fingerprinting only. Passed as this call's `read_extra` (see service.py), so it runs inside the
# same stable-read attempt - and therefore observes the same committed state - as the fingerprinted
# state used to compute snapshot_id/model_revision (spec §13).

# I2 Draft 0.2 §9 (amended): unlike `_EVIDENCE_QUERY` above, this lookup is keyed by caller-supplied
# ids (`EvidenceRequest.evidence_refs`, spec §11.1) - a client can name *any* id string, not only
# one it already learned from a public answer. Without this filter, a client that merely guessed or
# otherwise obtained a Kubernetes evidence id could read its full internal record back through
# `get_evidence`, even though every other public surface hides it (a real gap found in PR review).
# v0.5.0 I3 slice 5b (spec §16.2): a Kubernetes-sourced `:Evidence` node (Path A's own real
# evidence) is additionally admitted when its id is in the caller-supplied reachable set - every
# other source type is unaffected (`$reachable_ids` is irrelevant to a non-Kubernetes id, since the
# first disjunct already admits it). Path B/C's own synthetic (non-`:Evidence`-node) records are
# never returned by this Cypher query at all - `service.py` merges those in separately from the
# reconciliation step's own in-memory map, since they have no backing graph node this query could
# ever match.
_EVIDENCE_BY_ID_QUERY = (
    "MATCH (e:Evidence) WHERE e.id IN $evidence_ids "
    f"AND (e.source_type <> '{KUBERNETES_SOURCE_TYPE}' OR e.id IN $reachable_ids) "
    "RETURN e.id AS id, e.source_type AS source_type, e.source_file AS source_file, "
    "e.source_revision AS source_revision, e.evidence_type AS evidence_type, "
    "e.environment AS environment, e.bucket_start AS bucket_start, e.bucket_end AS bucket_end, "
    "e.first_seen AS first_seen, e.last_seen AS last_seen, "
    "e.observation_count AS observation_count, e.service_version AS service_version, "
    "e.correlation_mode AS correlation_mode"
)
# Restricted to the 7 canonical relation kinds `EvidenceRelationType` closes over (spec §11.2) -
# REQUEST_SCHEMA/RESPONSE_SCHEMA also carry evidence_ids but describe Operation->Schema payload
# wiring, not a "supported fact" this contract exposes; excluding them here (rather than filtering
# in Python) keeps the query itself the single source of truth for what counts as a supporting
# relation.
_SUPPORTING_RELATIONS_QUERY = (
    "MATCH (a)-[r:PROVIDES|CALLS|SENDS|RECEIVES_FROM|CARRIES|CONFORMS_TO|DEAD_LETTERS_TO]->(b) "
    "WHERE any(eid IN coalesce(r.evidence_ids, []) WHERE eid IN $evidence_ids) "
    "RETURN type(r) AS type, a.id AS source_id, b.id AS target_id, "
    "coalesce(r.evidence_ids, []) AS evidence_ids"
)

_EVIDENCE_DATETIME_FIELDS = frozenset({"bucket_start", "bucket_end", "first_seen", "last_seen"})


def read_evidence_rows(
    session: neo4j.Session,
    *,
    evidence_ids: list[str],
    reachable_kubernetes_evidence_ids: frozenset[str] = frozenset(),
) -> dict:
    """The raw rows `evidence_projection.project_evidence` needs to resolve `evidence_ids` into
    `EvidenceRecord`s (spec §11.2): the requested `Evidence` nodes' full public field set, and every
    relation supported by at least one of the requested ids (for `EvidenceRecord.supports`).
    `evidence` is keyed by id so a requested id absent from it is reported as missing by the caller
    - this function only reports raw presence/absence, never decides the public outcome.

    `reachable_kubernetes_evidence_ids` (v0.5.0 I3 slice 5b, spec §16.2) admits a Kubernetes-sourced
    `:Evidence` node (Path A) that's reachable from a public deployment claim/resolution - the
    default empty set preserves pre-I3-slice-5b behavior exactly. Path B/C's own synthetic evidence
    has no backing `:Evidence` node at all and is never returned here - `service.py` merges those in
    separately."""
    evidence = {}
    for record in session.run(
        _EVIDENCE_BY_ID_QUERY,
        evidence_ids=evidence_ids,
        reachable_ids=list(reachable_kubernetes_evidence_ids),
    ):
        row = dict(record)
        for field in _EVIDENCE_DATETIME_FIELDS:
            if row.get(field) is not None:
                row[field] = row[field].to_native()
        evidence[row["id"]] = row

    relations = [
        dict(record)
        for record in session.run(_SUPPORTING_RELATIONS_QUERY, evidence_ids=evidence_ids)
    ]

    return {"evidence": evidence, "relations": relations}


# --- v0.5.0 I3 slice 5a: public evidence list/lookup reads (spec §16.3) ------------------------
#
# `read_evidence_rows` above only resolves a caller-supplied bounded id list (spec §11.1's 1-20-ref
# `EvidenceRequest.evidence_refs`); the REST `GET /api/evidence`/`GET /api/evidence/{evidence_id}`
# convenience surfaces need an open-ended "list every publicly visible Evidence record" and "get one
# arbitrary id" capability with no bounded caller-supplied id set to key off. These reuse the exact
# same public-evidence predicate/field projection `app/api/evidence.py` ran directly against Neo4j
# before this slice (spec §16.2: "Existing pre-I3 public evidence remains public under its existing
# rules" - I3 slice 5b's DEPLOYED_AS-reachability widening is structurally inapplicable until a
# public DeploymentClaim/DeploymentResolution exists to reach evidence from, so this predicate is
# unchanged in slice 5a).

_PUBLIC_EVIDENCE_FIELDS = (
    "e.id AS id, e.source_type AS source_type, e.source_file AS source_file, "
    "e.source_revision AS source_revision, e.evidence_type AS evidence_type"
)
# v0.5.0 I3 slice 5b (spec §16.2): widened exactly like `_EVIDENCE_BY_ID_QUERY` above - see that
# query's own comment. `$reachable_ids` defaults to an empty list for a caller that hasn't computed
# any (preserves pre-slice-5b behavior byte-for-byte).
_PUBLIC_EVIDENCE_LIST_QUERY = (
    "MATCH (e:Evidence) "
    f"WHERE e.source_type <> '{KUBERNETES_SOURCE_TYPE}' OR e.id IN $reachable_ids "
    f"RETURN {_PUBLIC_EVIDENCE_FIELDS} ORDER BY e.id"
)
_PUBLIC_EVIDENCE_GET_QUERY = (
    "MATCH (e:Evidence {id: $evidence_id}) "
    f"WHERE e.source_type <> '{KUBERNETES_SOURCE_TYPE}' OR e.id IN $reachable_ids "
    f"RETURN {_PUBLIC_EVIDENCE_FIELDS}"
)


def read_public_evidence_list_rows(
    session: neo4j.Session, *, reachable_kubernetes_evidence_ids: frozenset[str] = frozenset()
) -> list[dict]:
    """Every publicly visible Evidence record's REST convenience-surface fields (spec §16.3's list
    endpoint), read inside the same stable-read attempt as the snapshot used to validate the
    caller's supplied `snapshot_id` - see `read_stable_snapshot_from_session`'s `read_extra`
    parameter. `reachable_kubernetes_evidence_ids` per spec §16.2 - see `_EVIDENCE_BY_ID_QUERY`'s
    own comment; Path B/C's synthetic evidence is merged in separately by `service.py`."""
    return [
        record.data()
        for record in session.run(
            _PUBLIC_EVIDENCE_LIST_QUERY, reachable_ids=list(reachable_kubernetes_evidence_ids)
        )
    ]


def read_public_evidence_row(
    session: neo4j.Session,
    *,
    evidence_id: str,
    reachable_kubernetes_evidence_ids: frozenset[str] = frozenset(),
) -> dict | None:
    """One publicly visible Evidence record's REST convenience-surface fields by id (spec §16.3's
    lookup endpoint), or `None` if it doesn't exist or isn't publicly visible - the caller decides
    the 404, this function only reports raw presence/absence."""
    record = session.run(
        _PUBLIC_EVIDENCE_GET_QUERY,
        evidence_id=evidence_id,
        reachable_ids=list(reachable_kubernetes_evidence_ids),
    ).single()
    return record.data() if record is not None else None


def read_service_dependency_rows(
    session: neo4j.Session,
    *,
    service_id: str,
    environment: str,
    window_start: datetime,
    window_end: datetime,
) -> dict:
    """The raw rows `dependency_projection.project_service_dependencies` needs for one service:
    its own outgoing `CALLS`/`SENDS` relations, the evidenced `PROVIDES`/`RECEIVES_FROM` relations
    that could resolve each destination, the referenced `Evidence` rows' qualification-relevant
    fields, and the existing O5 telemetry-coverage signal (spec §14 reuses the existing runtime
    evidence rules unchanged - `app.analysis.runtime.telemetry_coverage` *is* that rule, not a
    reimplementation of it). `service_name` is `None` when the service doesn't exist at all - the
    caller decides the `UNKNOWN_ENTITY` outcome, this function only reports raw absence."""
    name_row = session.run(_SERVICE_NAME_QUERY, service_id=service_id).single()
    service_name = name_row["name"] if name_row else None

    calls = [dict(record) for record in session.run(_CALLS_QUERY, service_id=service_id)]
    operation_ids = sorted({call["operation_id"] for call in calls})
    provides = (
        [
            dict(record)
            for record in session.run(_PROVIDES_FOR_OPERATIONS_QUERY, operation_ids=operation_ids)
        ]
        if operation_ids
        else []
    )

    sends = [dict(record) for record in session.run(_SENDS_QUERY, service_id=service_id)]
    queue_ids = sorted({send["queue_id"] for send in sends})
    receives = (
        [dict(record) for record in session.run(_RECEIVES_FOR_QUEUES_QUERY, queue_ids=queue_ids)]
        if queue_ids
        else []
    )

    evidence_ids = _referenced_evidence_ids(calls, provides, sends, receives)
    evidence = {}
    if evidence_ids:
        for record in session.run(_EVIDENCE_FOR_IDS_QUERY, evidence_ids=evidence_ids):
            row = dict(record)
            if row["last_seen"] is not None:
                row["last_seen"] = row["last_seen"].to_native()
            evidence[row["id"]] = row

    coverage = telemetry_coverage(
        session,
        environment=environment,
        since=window_start,
        until=window_end,
        service_ids=[service_id],
    )[0]

    return {
        "service_name": service_name,
        "calls": calls,
        "provides": provides,
        "sends": sends,
        "receives": receives,
        "evidence": evidence,
        "coverage": coverage,
    }
