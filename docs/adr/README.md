# Architecture Decision Records

Numbered, immutable records of significant architectural decisions and the reasoning behind them —
see [`architecture.md`](../architecture.md#architecture-principles) for how these map onto the
project's stated architecture principles.

| ADR | Decision |
|---|---|
| [0001](0001-use-neo4j.md) | Use Neo4j as the graph store |
| [0002](0002-canonical-model.md) | A shared Canonical Model decouples adapters from the graph |
| [0003](0003-evidence-as-first-class-concept.md) | Evidence is a first-class, persisted concept |
| [0004](0004-deterministic-before-generative.md) | Deterministic analyses before generative ones |
| [0005](0005-llm-is-not-source-of-truth.md) | The LLM is not a source of truth, and access is read-only by design |
| [0006](0006-declared-vs-observed.md) | Declared and observed architecture are independent evidence sources |
| [0007](0007-do-not-store-full-traces-in-neo4j.md) | Never store full traces or raw span payloads in Neo4j |
| [0008](0008-apache-2.0-license.md) | License under Apache License 2.0 |
| [0009](0009-source-adapter-seam.md) | Source adapters are a registered seam, not a pipeline convention (Proposed) |
| [0010](0010-single-qualification-rule.md) | The declared-vs-observed rule has one owner and one executable cross-check (Proposed) |
| [0011](0011-snapshot-identity-read-cost.md) | Snapshot identity must not cost a full-graph read per call (Proposed) |
| [0012](0012-observed-evidence-retention.md) | Observed evidence is compacted on a retention policy, never silently dropped (Proposed) |
| [0013](0013-no-topic-family-without-guards.md) | No topic/pub-sub family in the Canonical Model without both safety guards |

A new ADR is numbered sequentially and never renumbered or deleted — if a decision is superseded,
add a new ADR and mark the old one's Status as `Superseded by NNNN`.

An ADR whose decision is settled but not yet implemented carries `Status: Proposed`; it moves to
`Accepted` when the work it describes lands (or, for [0011](0011-snapshot-identity-read-cost.md)
and [0012](0012-observed-evidence-retention.md), when the benchmark and the retention thresholds
it names are decided). 0009-0013 came out of
[`architecture-review-0.4.0.md`](../architecture-review-0.4.0.md).
