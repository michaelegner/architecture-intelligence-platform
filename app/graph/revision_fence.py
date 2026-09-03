"""Internal monotonic revision fence (v0.4.0 I1.2, spec §19).

Neo4j's default read-committed isolation permits non-repeatable reads, so a sequence of ordinary
read queries alone cannot prove that a canonical-state fingerprint and a request-specific
projection describe one consistent committed state. This module provides the single counter every
write path bumps atomically inside its own transaction, so a read-only caller can detect whether
the graph changed between two reads (see `app.architecture_intelligence.repository.read_stable_snapshot`).

The `(:AipInternalState)` node is internal metadata, not part of the Canonical Model: it is
excluded from the snapshot fingerprint, stores no historical state or architecture fact, and is
never exposed in an answer.
"""

from __future__ import annotations

import neo4j

_SINGLETON_ID = "architecture"

_ENSURE_SINGLETON_QUERY = "MERGE (s:AipInternalState {id: $id}) ON CREATE SET s.revision = 0"
_READ_REVISION_QUERY = "MATCH (s:AipInternalState {id: $id}) RETURN s.revision AS revision"
# coalesce(..., 0) heals a null/missing revision (e.g. hand-edited state) on the next bump instead
# of propagating null forever - Cypher's `null + 1` is `null`, so without this a single corrupted
# write would permanently break the fence for every subsequent write.
_BUMP_REVISION_QUERY = (
    "MATCH (s:AipInternalState {id: $id}) SET s.revision = coalesce(s.revision, 0) + 1"
)


class RevisionSingletonMissing(RuntimeError):
    """Raised when no `(:AipInternalState)` singleton exists. A read-only caller MUST fail safely
    rather than create or repair it (spec §19) - that is `ensure_revision_singleton`'s job, run
    from the schema-initialization path."""


def ensure_revision_singleton(session: neo4j.Session) -> None:
    """Idempotently creates the singleton at revision 0. Safe to call on every startup/import -
    `ON CREATE` means an existing revision is never reset."""
    session.run(_ENSURE_SINGLETON_QUERY, id=_SINGLETON_ID)


def bump_revision(tx: neo4j.ManagedTransaction) -> None:
    """MUST be called inside the same transaction as the write it fences (never a separate one),
    so a rolled-back write can never advance the committed revision."""
    tx.run(_BUMP_REVISION_QUERY, id=_SINGLETON_ID)


def read_revision(session: neo4j.Session) -> int:
    record = session.run(_READ_REVISION_QUERY, id=_SINGLETON_ID).single()
    if record is None:
        raise RevisionSingletonMissing(
            "no (:AipInternalState) singleton found - schema initialization did not run"
        )
    revision = record["revision"]
    # bool is an int subclass in Python but was never a valid revision value; reject it alongside
    # null/non-integer/negative so a corrupted singleton fails safely (spec §19) instead of two
    # equally-corrupted reads spuriously comparing equal and being accepted as "stable".
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise RevisionSingletonMissing(
            f"(:AipInternalState) singleton has an invalid revision value: {revision!r}"
        )
    return revision
