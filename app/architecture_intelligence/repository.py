"""v0.4.0 I1.2 - canonical snapshot projection, fingerprinting, and the bounded stable-read retry
(spec §17/§18/§19.1).

This is the beginning of the `ArchitectureReadRepository` the I1 spec's architecture diagram places
between `ArchitectureIntelligenceService` and Neo4j - it owns only read mechanics and raw graph
projection (spec §7). I1.3 will add the request-specific dependency-projection queries here
alongside what I1.2 delivers; neither this module nor I1.3's additions may decide public outcome
semantics or return an `ArchitectureAnswer`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

import neo4j

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.graph.revision_fence import read_revision

# Bumping this - or changing any query/rule below - is a snapshot-fingerprint contract change and
# MUST be recorded explicitly (spec §18).
_CANONICALIZATION_VERSION = 1

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

# neo4j.time.DateTime isn't a datetime.datetime - convert to native so canonical_json_bytes'
# datetime handling applies (same conversion app.telemetry.aggregator._read_existing_evidence uses).
_DATETIME_FIELDS = frozenset({"bucket_start", "bucket_end", "first_seen", "last_seen"})
# Set-valued properties (spec §18: "set-valued arrays sorted and deduplicated").
_LIST_FIELDS = frozenset(
    {"request_schema_ids", "response_schema_ids", "sample_trace_ids", "evidence_ids"}
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


def canonical_snapshot_state(
    session: neo4j.Session, *, coverage_qualification_enabled: bool
) -> dict:
    """The complete queryable canonical model-and-evidence state, as an allowlisted (spec §18),
    canonically-ordered plain dict ready for `canonical_json_bytes`. Excludes Neo4j element ids,
    read/insertion order, relation `.key`, reconciliation-only `.sources` arrays, and the internal
    revision-fence value - none of those are ever selected by the queries above in the first
    place, so there is nothing further to strip here."""
    return {
        "version": _CANONICALIZATION_VERSION,
        "services": _project_nodes(session, _SERVICE_QUERY),
        "operations": _project_nodes(session, _OPERATION_QUERY),
        "queues": _project_nodes(session, _QUEUE_QUERY),
        "messages": _project_nodes(session, _MESSAGE_QUERY),
        "schemas": _project_nodes(session, _SCHEMA_QUERY),
        "evidence": _project_nodes(session, _EVIDENCE_QUERY),
        "relations": _project_relations(session),
        "semantic_config": {"coverage_qualification_enabled": coverage_qualification_enabled},
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
    read_extra: Callable[[neo4j.Session], T] = lambda _session: None,
    max_attempts: int = 3,
) -> StableSnapshot[T]:
    """I1.2 has no request-specific data yet, so `read_extra` defaults to a no-op; I1.3 passes its
    dependency-projection read here unchanged, reusing this same retry loop rather than
    duplicating it."""
    return read_stable_snapshot(
        read_revision_fn=lambda: read_revision(session),
        read_state=lambda: canonical_snapshot_state(
            session, coverage_qualification_enabled=coverage_qualification_enabled
        ),
        read_extra=lambda: read_extra(session),
        max_attempts=max_attempts,
    )
