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

## Delivery Direction

The planned release surface comprises the `ArchitectureIntelligenceService`, structured
evidence-backed result contracts, snapshot and observation-context binding, evidence and provenance
linkage, qualification of architectural claims, read-only MCP tools, deterministic tool evaluation,
and one focused end-to-end hero demo.

Delivery remains capability-first and scope-bounded: establish the trusted service contract first,
then expose selected read-only tools, qualify them deterministically, and complete the release without
adding new architecture-discovery domains or analysis algorithms.

For shipped versus planned capabilities, see the project [Roadmap](../../../ROADMAP.md).
