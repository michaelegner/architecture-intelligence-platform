# AIP v0.4.0 — Architecture Intelligence Tools

**Release:** `v0.4.0`  
**Status:** Draft  
**Goal:** Trusted Architecture Context for Agents

## Purpose

`v0.4.0` exposes AIP's validated architecture model as stable, snapshot-bound,
evidence-backed and machine-consumable context for AI agents and architecture tools.

The release follows one principle:

> AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth.

## Documents

| Document | Purpose | Status |
|---|---|---|
| [`specification.md`](specification.md) | Normative capability and release contract for `v0.4.0`. | Draft 1.2 |
| [`i1-service-contract-and-dependency-vertical-slice.md`](i1-service-contract-and-dependency-vertical-slice.md) | Self-contained implementation contract for the first service-level dependency vertical slice. | Draft 1 |
| [`i2-mcp-vertical-slice-and-evidence-drill-down.md`](i2-mcp-vertical-slice-and-evidence-drill-down.md) | MCP exposure of the qualified dependency answer plus snapshot-bound evidence drill-down. | Draft 1 |
| [`i3-drift-capability-and-deterministic-qualification.md`](i3-drift-capability-and-deterministic-qualification.md) | Drift capability plus complete deterministic three-tool qualification and hero demo. | Draft 1 |

## Status

- **I1 (Service Contract and Dependency Vertical Slice) — GO.** Candidate
  `8031f640daac3067ba9e709b19464d8246959fe2` (PR #74). See
  [`i1-completion-record.md`](i1-completion-record.md) for the full exit record.
- **I2 (MCP Vertical Slice and Evidence Drill-Down) — GO.** Delivered as I2.1 Protocol and Contract
  Skeleton (PR #77), I2.2 Dependency MCP Adapter (PR #78), I2.3 Evidence Service and Tool (PR #79),
  I2.4 Independent-Client Qualification (this PR). No separate completion-record dossier per spec
  §18; the executable schemas, focused test suites (including
  `tests/integration/test_mcp_independent_client_golden_path.py`'s real end-to-end golden path
  through the actual production app), and each PR's own verification record are the evidence.

  ```text
  GO — At da5602524ca375b178922fab4f1c21016f3971d1, an independent MCP 2026-07-28 client can
  obtain AIP's qualified, snapshot-bound direct-dependency answer and resolve its evidence and
  provenance through two read-only tools, with semantic differences from direct service calls = 0
  and graph writes = 0.
  ```

  Verified against that exact commit via `gh api repos/.../commits/da56025.../check-runs` (never
  the PR's ambient current-head view): `lint + test` ×2, `CodeQL`, `analyze (actions)`,
  `analyze (python)`, `dependency security scan (pip-audit, spec §29)` ×2 — all `completed`/
  `success`. The candidate carries the review-round-1 fixes: the golden path runs over a real
  `uvicorn` listener rather than an in-process ASGI dispatch, spec §17 scenario 19 (concurrent
  evidence writes) is qualified against real Neo4j, and both answers are validated against the
  tools' advertised `outputSchema`.
- **I3 (Drift Capability and Deterministic Qualification) — GO.** Delivered as I3.1 Drift Contract
  and Service (PR #82), I3.2 Drift MCP Tool (PR #83), I3.3 Full Deterministic Three-Tool Evaluation
  (PR #84), I3.4 Hero Demo and I3 Completion (this PR). No separate completion-record dossier per
  spec §63; the drift contract/schema, the three-tool evaluator's two clean-state passes, the
  frozen Quarkus/Airflow-derived qualification, and each PR's own verification record are the
  evidence.

  ```text
  GO — At bbde691d5d317ae167394b9871e26c0b2e183b63, ArchitectureIntelligenceService and the MCP
  2026-07-28 surface expose exactly three read-only architecture tools. get_architecture_drift
  returns only the existing direct-dependency claims qualified OBSERVED_ONLY or
  NOT_OBSERVED_IN_WINDOW, preserving I1 claim identity, destination/delivery semantics, evidence,
  observation context and snapshot binding. The complete three-tool deterministic evaluation passes
  two clean-state runs with identical semantic outputs, frozen Quarkus/Airflow-derived qualification
  passes without invented facts, the hero demo completes, and graph writes = 0.
  ```

  Verified against that exact commit via
  `gh api repos/.../commits/bbde691.../check-runs` (never the PR's ambient current-head view):
  `lint + test` ×2, `CodeQL`, `analyze (actions)`, `analyze (python)`,
  `dependency security scan (pip-audit, spec §29)` ×2 — all `completed`/`success`. I3.4 itself made
  no service/contract/MCP code changes (I3.1-I3.3 already delivered and qualified all drift
  semantics); it added `examples/runtime-demo/seed_frozen_evidence.py` (a one-shot,
  timestamp-frozen evidence seed satisfying spec §43's determinism requirement, rather than the
  live traffic-generator's wall-clock loop), `examples/runtime-demo/hero-demo.md` (the ~5-minute
  walkthrough), and `docs/mcp.md` (concise tool reference). PR review caught that an earlier
  candidate (`0f45f5b`, now superseded) froze span timestamps but not the trace/span IDs
  (`uuid.uuid4()`) or span-duration jitter (`random.randint`) also reachable from
  `canonical_snapshot_state()`'s fingerprinted `Evidence.sample_trace_ids`/`first_seen`/`last_seen` -
  `bbde691` fixes that by seeding a `random.Random` through the same span builders. The hero demo
  was run live against a real local stack twice from a clean state (`docker compose down -v`
  between runs) and produced byte-for-byte identical full tool responses both times - not just
  matching qualifications, but identical `snapshot_id`, `model_revision`, `sample_trace_ids`, and
  `first_seen`/`last_seen`: `OrderService -> LegacyPricingService` `OBSERVED_ONLY` (the hero finding)
  and `OrderService -> unused-q` `NOT_OBSERVED_IN_WINDOW`, with `ProductService`/`payment-q`
  correctly excluded as `CONFIRMED`.
- **I4 (Release Candidate/Publication/Verification) — not started.**

## Delivery Direction

The planned release surface comprises the `ArchitectureIntelligenceService`, structured
evidence-backed result contracts, snapshot and observation-context binding, evidence and provenance
linkage, qualification of architectural claims, read-only MCP tools, deterministic tool evaluation,
and one focused end-to-end hero demo.

Delivery remains capability-first and scope-bounded: establish the trusted service contract first,
then expose selected read-only tools, qualify them deterministically, and complete the release without
adding new architecture-discovery domains or analysis algorithms.

For shipped versus planned capabilities, see the project [Roadmap](../../../ROADMAP.md).
