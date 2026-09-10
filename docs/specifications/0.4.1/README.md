# AIP v0.4.1 — Semantic Hardening for Broader Discovery

**Release:** `v0.4.1`  
**Status:** Shipped — [`v0.4.1`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.4.1) released 2026-09-10  
**Goal:** Semantic Hardening for Broader Discovery

## Purpose

`v0.4.1` hardens AIP's existing architecture-intelligence semantics before broader discovery. It
cross-checks declared-versus-observed qualification, guards runtime messaging destination and
service identity, and commits reproducible evidence of current whole-graph read cost. It adds no
discovery source, Canonical Model family, or MCP tool.

## Documents

| Document | Purpose | Status |
|---|---|---|
| [`specification.md`](specification.md) | Normative capability and release contract for `v0.4.1`. | Draft |
| [`i1-qualification-consistency.md`](i1-qualification-consistency.md) | One declared-versus-observed semantic owner, real-Neo4j differential qualification. | Draft |
| [`i2-messaging-semantic-guards.md`](i2-messaging-semantic-guards.md) | Queue-compatible destination guard and safe messaging service-identity guard. | Draft |
| [`i3-hardening-qualification-and-release.md`](i3-hardening-qualification-and-release.md) | Committed snapshot/read-cost benchmark, exact-candidate qualification, RC/final publication, post-release verification. | Draft 0.1 |
| [`i3-completion-record.md`](i3-completion-record.md) | Full I3 exit record: run identity, regression suite, benchmark result, release publication identity. | Final |

## Status

- **I1 (Qualification Consistency) — GO.** Delivered as I1.1 Shared Qualification Kernel (PR
  #112), I1.2 Runtime/Architecture-Intelligence Wiring (PR #113), I1.3 Differential Qualification
  and Completion (PR #114). See [`i1-completion-record.md`](i1-completion-record.md) for the full
  exit record.

  ```text
  GO — At 385604b7c7098184b04193abf13727e90cd8b555, AIP's analysis/REST and
  ArchitectureIntelligenceService/MCP qualification paths are governed by one
  declared-versus-observed semantic owner
  (app/qualification/declared_observed.py). Against a shared deterministic real-Neo4j fixture,
  equivalent effective observation contexts produce qualification mismatches = 0 and coverage
  mismatches = 0 across CALLS and SENDS cases including declared-only, observed-only, confirmed,
  environment mismatch, window boundaries, and unsupported/dangling evidence. One real pre-existing
  coverage-window bug was found and fixed in the process, with its own permanent regression test.
  The shipped v0.4 public schemas and exactly three read-only MCP tools remain unchanged.
  ```

  ADR 0010 moved from `Proposed` to `Accepted` on this record.

- **I2 (Messaging Semantic Guards) — GO.** Delivered as I2.1 Pure Guard Decisions (PR #115), I2.2
  Atomic Production Wiring (PR #116), I2.3 Frozen Qualification and Completion (PR #117). See
  [`i2-completion-record.md`](i2-completion-record.md) for the full exit record.

  ```text
  GO — At d37399b256062d4da5c116ae332ed25d69395e04, AIP's production runtime messaging path
  requires both deterministic Queue-compatible destination semantics and safe service identity
  before deriving a canonical SENDS/RECEIVES_FROM observation. Topic-shaped, unresolved,
  conflicting, ambiguous, and placeholder inputs produce zero Service/Queue/Evidence/relation
  artifacts from the refused span, while declared Queues and explicit unambiguous runtime-only
  Services preserve valid OBSERVED_ONLY behavior. The frozen Quarkus Kafka and Airflow/Celery
  shapes remain unsupported with zero invented messaging facts; operation recognition, the
  Canonical Model, public v0.4 schemas, and the exactly three read-only MCP tools remain unchanged.
  I2 release blockers = 0.
  ```

  ADR 0013 is satisfied (not superseded) by this record.

- **I3 (Hardening, Qualification and Release) — GO.** Delivered as I3.1 Reproducible Benchmark
  Harness (PR #119), I3.2 Candidate Preparation (PR #120) plus qualification evidence (PR #121),
  I3.3 RC Publication/GO Decision/Final Publication (PRs #122-124), I3.4 Post-Release Verification
  and Closure (this record). See [`i3-completion-record.md`](i3-completion-record.md) for the full
  exit record.

  ```text
  GO — At bc03602f95557eb0450506a9f5c3a7f7c296b2da, AIP v0.4.1 preserves the shipped v0.4
  ArchitectureAnswer schema family and exactly three read-only MCP tools while completing its
  semantic hardening: the analysis and Architecture Intelligence paths remain governed by one
  declared-versus-observed rule with qualification mismatches = 0 and coverage mismatches = 0, and
  runtime messaging still requires both Queue-compatible destination semantics and safe service
  identity before producing any canonical artifact. A committed, disposable, deterministic
  benchmark reproduces and records the current relationship between total graph/evidence size and
  snapshot/dependency read cost without changing snapshot identity, retention, or public semantics.
  The exact source candidate, release-triggered RC image, final v0.4.1 tag, and final GHCR image
  have passed their required independent qualification, with producer.version=0.4.1 and
  producer.build_revision=bc03602f95557eb0450506a9f5c3a7f7c296b2da. Release blockers = 0.
  ```

  ADR 0011 follows spec §18 and stays `Proposed` — this record does not imply the cache shipped.
  ADR 0012 remains deferred/proposed. ADR 0010 and ADR 0013 remain `Accepted`.

  **`v0.4.1` is now shipped — see [`ROADMAP.md`](../../../ROADMAP.md)'s `v0.4.1` section.**

## Delivery Direction

`v0.4.1` is hardening and release-qualification work, not architecture-discovery expansion: zero
new MCP tools, zero new Canonical Model entities/relations, zero new discovery sources, zero
messaging-recognition widening. It commits reproducible read-cost evidence (I3) without
implementing a snapshot cache or retention policy — those remain separately reviewable `v0.5.0`
work, gated behind this release's own guard regressions (ADR 0009/0013) and evidence (ADR
0011/0012).

For shipped versus planned capabilities, see the project [Roadmap](../../../ROADMAP.md).
