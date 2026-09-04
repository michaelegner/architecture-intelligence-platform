"""Independent re-derivation of the snapshot/model-revision fingerprint (spec §17/§18) - own Cypher
queries and canonicalization, transcribed directly from §18's allowlist and canonicalization rules,
deliberately not imported from app.architecture_intelligence.repository. Authoring-time only - see
`canonical_json.py`'s module docstring for why the live evaluation path never imports this module.

This is the largest, most maintenance-sensitive piece of the reference tool: a scenario's frozen
`snapshot_id`/`model_revision` must be regenerated (by re-running this against that scenario's
prepared fixture) whenever its own `input/` fixture files change.
"""

from __future__ import annotations

import hashlib

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
_MESSAGE_QUERY = (
    "MATCH (n:Message) RETURN n.id AS id, n.name AS name, n.version AS version, "
    "n.schema_id AS schema_id"
)
_SCHEMA_QUERY = (
    "MATCH (n:Schema) RETURN n.id AS id, n.name AS name, n.version AS version, "
    "n.format AS format, n.canonical_hash AS canonical_hash"
)
_EVIDENCE_QUERY = (
    "MATCH (n:Evidence) RETURN n.id AS id, n.source_type AS source_type, "
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

_DATETIME_FIELDS = frozenset({"bucket_start", "bucket_end", "first_seen", "last_seen"})
_LIST_FIELDS = frozenset(
    {"request_schema_ids", "response_schema_ids", "sample_trace_ids", "evidence_ids"}
)


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


def canonical_state(session: neo4j.Session, *, coverage_qualification_enabled: bool) -> dict:
    return {
        "version": 1,
        "services": _nodes(session, _SERVICE_QUERY),
        "operations": _nodes(session, _OPERATION_QUERY),
        "queues": _nodes(session, _QUEUE_QUERY),
        "messages": _nodes(session, _MESSAGE_QUERY),
        "schemas": _nodes(session, _SCHEMA_QUERY),
        "evidence": _nodes(session, _EVIDENCE_QUERY),
        "relations": _relations(session),
        "semantic_config": {"coverage_qualification_enabled": coverage_qualification_enabled},
    }


def fingerprint(session: neo4j.Session, *, coverage_qualification_enabled: bool) -> tuple[str, str]:
    """`(snapshot_id, model_revision)` - the same digest under different public prefixes (spec §17)."""
    state = canonical_state(session, coverage_qualification_enabled=coverage_qualification_enabled)
    digest = hashlib.sha256(canonical_json_bytes(state)).hexdigest()
    return f"aip:snapshot:v1:{digest}", f"sha256:{digest}"
