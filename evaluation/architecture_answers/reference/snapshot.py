"""Independent re-derivation of the snapshot/model-revision fingerprint (spec §17/§18) - own Cypher
queries and canonicalization, transcribed directly from §18's allowlist and canonicalization rules,
deliberately not imported from app.architecture_intelligence.repository. Authoring-time only - see
`canonical_json.py`'s module docstring for why the live evaluation path never imports this module.

This is the largest, most maintenance-sensitive piece of the reference tool: a scenario's frozen
`snapshot_id`/`model_revision` must be regenerated (by re-running this against that scenario's
prepared fixture) whenever its own `input/` fixture files change.

v0.5.0 I5 Slice 1 (I5 §3 gap 3, §12) brings this to canonicalization version 3, the candidate's
version. It is transcribed from the specifications, not from app code:
- **v2, I3 spec §17:** the deployment-relevant state, namely current Workloads with their retained
  Service-ID annotations, captured Pod UID bindings, WORKLOAD_OWNS_POD links, runtime identity
  observations, and the reconciliation rule identity. It also binds the configured mapping
  artifact's identity (I3 §8.3). Kubernetes-sourced evidence is excluded from the public evidence
  projection (I2 §9).
- **v3, I4 spec §11:** dedicated Topic and Subscription projections. The internal
  PubSubDeclaration and SubscriptionDeadLetterConfiguration carriers are not snapshot inputs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import neo4j

from evaluation.architecture_answers.reference.canonical_json import canonical_json_bytes

# spec §18's allowlist, one query per node label plus one for relations.
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
# I4 spec §11: Topic/Subscription public state binds snapshot identity.
_TOPIC_QUERY = (
    "MATCH (n:Topic) RETURN n.id AS id, n.name AS name, n.protocol AS protocol, "
    "n.namespace AS namespace"
)
_SUBSCRIPTION_QUERY = (
    "MATCH (n:Subscription) RETURN n.id AS id, n.name AS name, n.protocol AS protocol, "
    "n.namespace AS namespace"
)
_MESSAGE_QUERY = (
    "MATCH (n:Message) RETURN n.id AS id, n.name AS name, n.version AS version, "
    "n.schema_id AS schema_id"
)
_SCHEMA_QUERY = (
    "MATCH (n:Schema) RETURN n.id AS id, n.name AS name, n.version AS version, "
    "n.format AS format, n.canonical_hash AS canonical_hash"
)
# I2 §9: Kubernetes-sourced evidence supports only internal infrastructure state, so it is not part
# of the public evidence projection.
_EVIDENCE_QUERY = (
    "MATCH (n:Evidence) WHERE n.source_type <> 'KUBERNETES' "
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

# I3 spec §17: the deployment-relevant state a public DEPLOYED_AS answer can depend on.
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
_DEPLOYMENT_CAPTURED_PODS_QUERY = (
    "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_POD'}) "
    "MATCH (c:InfrastructureContribution {entity_id: e.id}) "
    "WHERE c.captured_resource_uid IS NOT NULL "
    "RETURN e.id AS id, c.captured_resource_uid AS captured_resource_uid, "
    "c.captured_at AS captured_at, coalesce(c.evidence_refs, []) AS evidence_refs"
)
_DEPLOYMENT_WORKLOAD_OWNS_POD_QUERY = (
    "MATCH (c:InfrastructureClaim {kind: 'WORKLOAD_OWNS_POD'}) "
    "RETURN c.id AS id, c.subject_id AS workload_id, c.object_id AS pod_id, "
    "coalesce(c.evidence_refs, []) AS evidence_refs"
)
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
# I3 spec §6: the frozen reconciliation rule identity.
_RECONCILIATION_RULE = {"rule_id": "service-workload-reconciliation", "rule_version": 1}

_DATETIME_FIELDS = frozenset({"bucket_start", "bucket_end", "first_seen", "last_seen"})
_LIST_FIELDS = frozenset(
    {
        "request_schema_ids",
        "response_schema_ids",
        "sample_trace_ids",
        "evidence_ids",
        "conflicting_consistency_attributes",
    }
)


@dataclass(frozen=True)
class MappingArtifactIdentity:
    """I3 §8.3: the configured Service-Workload mapping artifact's identity, bound into
    `semantic_config` only when an artifact is configured. Supplied by the author (the artifact's
    `artifact_id`, `artifact_revision`, and content digest), since it is configuration, not graph
    state."""

    artifact_id: str
    artifact_revision: str
    content_digest: str


def _project_row(record: neo4j.Record) -> dict:
    """Drops null/absent properties (spec §18's null/absent normalization rule), normalizes
    set-valued arrays (sorted, deduplicated) and temporal properties to native UTC."""
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


def _nodes(session: neo4j.Session, query: str) -> list[dict]:
    """Node arrays sorted by `(type, id)` - type is constant within one label's own list, so
    sorting by id alone is equivalent (spec §18)."""
    return sorted((_project_row(r) for r in session.run(query)), key=lambda row: row["id"])


def _relations(session: neo4j.Session) -> list[dict]:
    rows = [_project_row(r) for r in session.run(_RELATION_QUERY)]
    return sorted(rows, key=lambda row: (row["type"], row["source_id"], row["target_id"]))


def _deployment_workloads(session: neo4j.Session) -> list[dict]:
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
                {"annotation": a["annotation"], "evidence_refs": sorted(set(a["evidence_refs"]))}
                for a in record["annotations"]
            ),
            key=lambda a: (a["annotation"], tuple(a["evidence_refs"])),
        )
        if annotations:
            row["annotations"] = annotations
        rows.append(row)
    return sorted(rows, key=lambda row: row["id"])


def _deployment_rows(session: neo4j.Session, query: str, fields: tuple[str, ...]) -> list[dict]:
    """Rows kept verbatim for the listed fields (nulls included), with `evidence_refs` sorted and
    deduplicated, then sorted by id."""
    rows = []
    for record in session.run(query):
        row = {key: record[key] for key in fields}
        row["evidence_refs"] = sorted(set(record["evidence_refs"]))
        rows.append(row)
    return sorted(rows, key=lambda row: row["id"])


def canonical_state(
    session: neo4j.Session,
    *,
    coverage_qualification_enabled: bool,
    mapping_artifact: MappingArtifactIdentity | None = None,
) -> dict:
    semantic_config: dict = {"coverage_qualification_enabled": coverage_qualification_enabled}
    if mapping_artifact is not None:
        semantic_config["service_workload_mapping_artifact"] = {
            "artifact_id": mapping_artifact.artifact_id,
            "artifact_revision": mapping_artifact.artifact_revision,
            "content_digest": mapping_artifact.content_digest,
        }
    return {
        "version": 3,
        "services": _nodes(session, _SERVICE_QUERY),
        "operations": _nodes(session, _OPERATION_QUERY),
        "queues": _nodes(session, _QUEUE_QUERY),
        "topics": _nodes(session, _TOPIC_QUERY),
        "subscriptions": _nodes(session, _SUBSCRIPTION_QUERY),
        "messages": _nodes(session, _MESSAGE_QUERY),
        "schemas": _nodes(session, _SCHEMA_QUERY),
        "evidence": _nodes(session, _EVIDENCE_QUERY),
        "relations": _relations(session),
        "semantic_config": semantic_config,
        "deployment_workloads": _deployment_workloads(session),
        "deployment_captured_pods": _deployment_rows(
            session, _DEPLOYMENT_CAPTURED_PODS_QUERY, ("id", "captured_resource_uid", "captured_at")
        ),
        "deployment_workload_owns_pod": _deployment_rows(
            session, _DEPLOYMENT_WORKLOAD_OWNS_POD_QUERY, ("id", "workload_id", "pod_id")
        ),
        "deployment_runtime_identity_observations": _nodes(
            session, _DEPLOYMENT_RUNTIME_IDENTITY_OBSERVATIONS_QUERY
        ),
        "deployment_reconciliation_rule": dict(_RECONCILIATION_RULE),
    }


def fingerprint(
    session: neo4j.Session,
    *,
    coverage_qualification_enabled: bool,
    mapping_artifact: MappingArtifactIdentity | None = None,
) -> tuple[str, str]:
    """`(snapshot_id, model_revision)` - the same digest under different public prefixes (spec §17)."""
    state = canonical_state(
        session,
        coverage_qualification_enabled=coverage_qualification_enabled,
        mapping_artifact=mapping_artifact,
    )
    digest = hashlib.sha256(canonical_json_bytes(state)).hexdigest()
    return f"aip:snapshot:v1:{digest}", f"sha256:{digest}"
