# 12. Observed evidence is compacted on a retention policy, never silently dropped

Status: Proposed — the retention thresholds are an open parameter for the repository owner. See
[`architecture-review-0.4.0.md`](../architecture-review-0.4.0.md#f3--read-cost-grows-with-the-whole-graph-and-evidence-never-stops-growing)

## Context

[ADR 0003](0003-evidence-as-first-class-concept.md) made evidence a persisted, first-class concept,
and [ADR 0007](0007-do-not-store-full-traces-in-neo4j.md) kept raw spans out of the graph. Neither
decided how long observed evidence lives.

Today it lives forever. `app/canonical/ids.py:39` mints one `Evidence` node per (fact, day,
environment) bucket, and `app/telemetry/aggregator.py:48` appends each bucket id to the relation's
`evidence_ids` array with no upper bound. A single relation observed daily in three environments
accumulates ~1,100 evidence ids per year, and the graph accumulates one node per bucket. Nothing in
`app/settings.py` configures a retention window, and no compaction path exists.

Three consequences follow: the snapshot fingerprint hashes all of it on every uncached call (see
[ADR 0011](0011-snapshot-identity-read-cost.md)); a claim's `evidence_refs` list grows without bound
even though `get_evidence` accepts at most 20 references per request; and the graph grows
monotonically for as long as telemetry flows.

Deleting old evidence is not a neutral storage decision. It removes the basis of past claims, and it
interacts directly with this project's governing rule that **non-observation is not absence** —
evidence that is dropped rather than summarized would silently turn a `CONFIRMED` relation into a
`NOT_OBSERVED_IN_WINDOW` one.

## Decision

1. **Compaction, not deletion.** Beyond a configured age, per-day observed evidence buckets for the
   same (fact, environment) are merged into coarser-grained buckets — preserving `first_seen`,
   `last_seen`, summed `observation_count`, and the strongest `correlation_mode`, exactly as
   `aggregator.py` already merges same-day observations. What is lost is temporal resolution, never
   the fact that something was observed.
2. **Declared evidence is never compacted.** It is one record per source, already bounded, and it is
   what the reconciliation invariant depends on.
3. **Retention is explicit configuration** with a documented default and a documented meaning: the
   age beyond which daily buckets are merged, and the coarser period they merge into. Compaction runs
   as a write path and therefore bumps the revision fence.
4. **Answers stay bounded.** A claim's `evidence_refs` is capped, with the most recent and most
   qualifying references retained and the truncation reported as a `limitations` entry — never
   silently truncated. Bounding the array is a public contract change and must be recorded in the
   answer schema.
5. **Open parameter:** the default thresholds (for example: daily buckets for 30 days, then monthly).
   The repository owner sets these before this ADR moves to Accepted; nothing else in the decision
   depends on the exact numbers.

## Consequences

- Windowed queries older than the retention boundary answer at reduced resolution: a coarse bucket
  overlapping a requested window is either fully in or fully out. That boundary behavior must be
  defined and tested, because it is a semantic change to `NOT_OBSERVED_IN_WINDOW`.
- Compaction changes `snapshot_id` when it runs, which is correct — the committed state did change —
  but it means snapshot ids can move without any architectural fact changing. The answer contract
  should say so.
- Existing graphs need a one-off compaction pass; the frozen evaluation fixtures are small and
  unaffected, so both evaluation suites keep their current expectations.
- Retention makes AIP's storage cost predictable, which is a prerequisite for `v0.9`'s production
  qualification. Without it, the only bound on graph size is how long the deployment has existed.
- Deliberately not decided here: archival of compacted detail to anything outside Neo4j. AIP stays a
  current-state system ([`ROADMAP.md`](../../ROADMAP.md) keeps architecture trajectories beyond
  v1.0); this ADR must not become a history-store design by accident.
