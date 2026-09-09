# 11. Snapshot identity must not cost a full-graph read per call

Status: Proposed — a committed benchmark is required before this is Accepted. See
[`architecture-review-0.4.0.md`](../architecture-review-0.4.0.md#f3--read-cost-grows-with-the-whole-graph-and-evidence-never-stops-growing)

## Context

Every `ArchitectureAnswer` names an exact graph state (`snapshot_id`/`model_revision`). Today that id
is produced by reading the entire queryable graph and hashing it:
`app/architecture_intelligence/repository.py:99` (`canonical_snapshot_state`) selects every `Service`,
`Operation`, `Queue`, `Message`, `Schema` and `Evidence` node plus every relation, and
`snapshot_fingerprint` hashes the canonical JSON of all of it. The stable read
(`repository.py:140`) may repeat that up to three times per call.

The cost is therefore a function of total graph size, not of the question asked. Measured on a
developer machine (WSL2, single-node Neo4j 5 container):

| Evidence nodes | Total nodes | Fingerprint | End-to-end `get_service_dependencies` |
|---:|---:|---:|---:|
| 6 | 124 | 0.05 s | 0.11 s |
| 4,604 | 4,722 | 0.75 s | — |
| 23,004 | 23,122 | 3.60 s | — |
| 97,548 | 98,566 | 16.06 s | 29.1 s |

98k nodes is a small landscape — roughly 300 observed facts kept for a year in one environment. The
same design also makes `get_evidence` for a single reference pay the full cost.

The mechanism for avoiding this already exists: `app/graph/revision_fence.py`'s monotonic counter is
bumped inside the same transaction as every write (`graph/importer.py`, `telemetry/aggregator.py`),
which is what makes the stable read sound in the first place.

## Decision

Snapshot identity must be obtainable in time independent of total graph size when the graph has not
changed.

1. **The fingerprint is cached against the revision fence.** A cached `(revision, snapshot_id,
   model_revision)` is reused while the revision is unchanged, and recomputed when it moves. The
   fingerprint stays a pure function of committed state, so two processes and two restarts still
   derive the same id for the same state.
2. **The contract is narrowed explicitly.** `snapshot_id` identifies a committed state produced
   through AIP's own write paths. A write made out of band — hand-run Cypher against the database —
   will no longer change `snapshot_id` until the next fenced write. This is a real narrowing of
   today's behavior and must be stated in [`mcp.md`](../mcp.md) and the answer contract, not left
   implicit.
3. **A benchmark is committed before this ADR is Accepted**, reproducing the table above and showing
   the cache's effect, so the claim is qualified the way every other release claim in this project
   is, rather than asserted.
4. **Request-scoped reads must not scan the graph either.** The same rule applies to
   `app/api/telemetry.py:46`'s per-export loading of all services/operations/queues, and to
   `telemetry_coverage`'s `_ALL_SERVICES_QUERY` when it is scoped to a single service. Those are
   lookups, and should be expressed as lookups.

Alternative considered and not chosen now: maintaining an incremental/rolling fingerprint at write
time. It removes the recompute entirely but makes every write path responsible for the hash's
correctness, which is a much larger correctness surface than caching a pure function.

## Consequences

- The stable-read algorithm itself is unchanged — revision before, revision after, discard on
  mismatch. Only the recomputation of the fingerprinted state is elided when the revision is stable.
- Out-of-band database edits stop being visible in `snapshot_id`. Anything that needs them visible
  (a repair procedure, a migration) must bump the fence, and that becomes a documented requirement.
- Cache is per-process and in-memory: a restart pays one recomputation, and multiple replicas each
  pay their own. No shared cache, no new infrastructure.
- Even with the cache, the *first* call after any write still pays the full-graph read. Sustained
  telemetry ingestion bumps the revision constantly, so this ADR alone does not make the cost
  acceptable at scale — it is necessary but not sufficient, and depends on
  [ADR 0012](0012-observed-evidence-retention.md) bounding how large the graph gets in the first
  place.
