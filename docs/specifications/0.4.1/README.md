# AIP v0.4.1 — Semantic Hardening for Broader Discovery

**Release:** `v0.4.1`
**Status:** In release qualification — I1 and I2 are `GO`; I3 (this document's own increment) is
in progress.
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

- **I3 (Hardening, Qualification and Release) — in progress.** Delivered as I3.1 Reproducible
  Benchmark Harness (PR #119, merged). I3.2 (candidate preparation and exact qualification), I3.3
  (RC publication, GO decision, final publication), and I3.4 (post-release verification and public
  closure) are not yet complete. This section is updated to `GO`, with the full exit record, once
  I3 closes — see [`i3-hardening-qualification-and-release.md`](i3-hardening-qualification-and-release.md)
  for the governing spec in the meantime.

## Delivery Direction

`v0.4.1` is hardening and release-qualification work, not architecture-discovery expansion: zero
new MCP tools, zero new Canonical Model entities/relations, zero new discovery sources, zero
messaging-recognition widening. It commits reproducible read-cost evidence (I3) without
implementing a snapshot cache or retention policy — those remain separately reviewable `v0.5.0`
work, gated behind this release's own guard regressions (ADR 0009/0013) and evidence (ADR
0011/0012).

For shipped versus planned capabilities, see the project [Roadmap](../../../ROADMAP.md).
