# Roadmap

## Versioning

[Semantic Versioning](https://semver.org/). The first public release is `v0.1.0`, cut as
`v0.1.0-alpha.1` first to validate the release pipeline end-to-end before promotion.

Not yet guaranteed stable pre-1.0 — expect breaking changes on a minor version bump:

- Canonical Model (`app/canonical/model.py`)
- REST API surface
- Graph Schema (node labels, relationship types/properties)
- Adapter SPI (`docs/adapter-development.md`'s `Protocol` contracts)
- Configuration format (`config.yaml`)

## v0.1 — shipped

- ✓ OpenAPI adapter
- ✓ AsyncAPI adapter
- ✓ Evidence (persisted `Evidence`/`Provenance`, queryable via `/api/evidence`)
- ✓ Five deterministic analyses (queue senders/consumers, orphan queues, mixed-architecture blast
  radius)
- ✓ Semantic validation (Graph Schema + Semantic Query Validator for the LLM layer)
- ✓ OpenTelemetry (OTLP ingestion, service/environment resolution, REST + queue observation,
  evidence aggregation, a Collector-based demo)
- ✓ Declared vs observed (`CONFIRMED`/`OBSERVED_ONLY`/`NOT_OBSERVED_IN_WINDOW`, with the 11H
  evidence-reconciliation invariant and cross-batch HTTP correlation)

## v0.2 — shipped
Focus: make the architecture intelligence introduced in v0.1 reproducibly testable against known
ground truth.

- ✓ Ten deterministic core scenarios (REST/queue dependencies, topology/directionality, partial
  observation with qualitative coverage, evidence reconciliation, a pure declared-only case)
- ✓ Independent, hand-authored `expected.yaml` ground truth per scenario, never generated from
  AIP's own derivation code
- ✓ A deterministic evaluation runner and canonical-fact projector reading real AIP ingestion and
  runtime resolution
- ✓ Exhaustive missing/unexpected/forbidden-fact detection, strict scenario-schema validation, and
  deterministic comparison/report ordering
- ✓ Local reproducibility with no separately running Neo4j and no LLM API key required

The goal of v0.2 is not to add another architecture-intelligence dimension, but to provide a
reproducible way to demonstrate that the existing one behaves correctly. See
[`evaluation/README.md`](evaluation/README.md) and
[`docs/specifications/0.2.0/`](docs/specifications/0.2.0/) for the full design history.

## v0.3 — Real-World Validation and Cross-System Hardening

Focus: prove the architecture intelligence validated reproducibly in v0.2 survives real,
independently authored systems, and harden only where real evidence justifies it — not to add
another architecture-intelligence dimension. See
[`docs/specifications/0.3.0/`](docs/specifications/0.3.0/) for the full design history.

| Iteration | Purpose | Status |
|---|---|---|
| I1 — Real-World Validation Contract | Freeze methodology, finding vocabulary, dossier structure, comparison semantics, runbook contract | ✓ complete (internal iteration work; no separate tag cut) |
| I2 — Quarkus Super Heroes Validation | Validate against an external reference architecture | ✓ complete — `v0.3.0-alpha.2` |
| I3 — Apache Airflow Validation | Validate against real-world OSS software | ✓ complete (internal iteration work; no separate tag cut) |
| I4 — Cross-System Model Hardening | Apply only general fixes justified by independent real-system evidence; revalidate both systems | ✓ complete — `v0.3.0-rc.1` |
| I5 — Release Qualification | Qualify the exact candidate and publish `v0.3.0` | pending |

I4's outcome: zero production changes were justified by either system's independent evidence — see
[`docs/real-world-validation/cross-system/report.md`](docs/real-world-validation/cross-system/report.md)
for the full cross-system report, finding ledger, and the canonical-redesign-gate answer (`NO`, no
fundamental Canonical Model redesign is required before v0.4). The `v0.3.0-rc.1` tag is cut at that
exact candidate. `v0.3.0` itself has not shipped yet; I5 has not started.

## v0.4 — Architecture Intelligence Tools (planned)

Focus: expose the validated semantic core through stable, evidence-backed tool contracts.

- `ArchitectureIntelligenceService`
- Structured, evidence-backed query contracts
- Read-only MCP tools
- Deterministic tool evaluation (contract shape, semantic correctness, evidence linkage, read-only
  enforcement, stable ordering)

The tool layer stays downstream of AIP's deterministic architecture model — it must not let an LLM
or MCP client create canonical facts, bypass semantic validation, or reach a graph write path.

## v0.5 — Broader Architecture Discovery (planned)

Focus: broaden what AIP can discover, now that the semantic core is validated and exposed through
controlled tools rather than before.

- Kubernetes discovery (declared-architecture source: Deployments/Services as an additional
  `ArchitectureSourceAdapter`)
- Additional source adapters (candidates: gRPC/protobuf service definitions, Kafka Connect configs
  — see the "New adapter proposal" issue template for the extension-point contract; no specific
  adapter is promised before its semantics and validation profile are approved)
- Deeper runtime discovery, reconciled with existing declared/observed evidence

Every new discovery source maps through the shared Canonical Model, retains provenance, avoids
environment-specific identity leakage, and must prove it doesn't create supported relations from
mere co-location or naming coincidence. Deeper runtime discovery preserves the same safety rules
already governing v0.1–v0.3: non-observation != absence; unresolved identity beats guessed identity;
explicitly unsupported beats incorrectly represented as supported.

Versions between v0.5 and v0.9 are intentionally unspecified — their scope will be derived from
validated user/tool experience and discovery findings, not invented ahead of that evidence.

## v0.9 — Contract Freeze / Production Qualification (planned)

Focus: stabilize public contracts and qualify the platform for production-grade use.

- Canonical Model compatibility review
- REST and MCP contract stabilization
- Graph Schema stabilization
- Adapter SPI stabilization
- Configuration-format stabilization
- Migration and deprecation rules
- Security and production-operability qualification
- Performance and resilience qualification
- Release/support policy

Any known breaking redesign required for the stable contract must be completed before the v1.0
candidate is frozen.

## v1.0 — Stable Architecture Intelligence Platform (planned)

Focus: publish the first stable AIP release with mature architecture-intelligence semantics and
public contracts. Requires: a stable architecture-intelligence model; stable public REST and MCP
contracts; stable Graph Schema and Adapter SPI; a documented compatibility/migration policy;
production qualification completed; critical semantic errors = 0; release blockers = 0.

## Sequencing principle

```text
v0.3 validation and hardening
  -> v0.4 architecture-intelligence tools
  -> v0.5 broader discovery
  -> v0.9 contract freeze and production qualification
  -> v1.0 stable platform
```

Validate the semantic core first, expose it as evidence-backed tools second, broaden discovery
third, then freeze and qualify the public contracts last. `v0.3` carries a hard gate: had either
real-system dossier shown the Canonical Architecture Model needed a fundamental breaking redesign,
AIP would not proceed to v0.4 until that redesign was specified, implemented, and revalidated — I4's
[`canonical-redesign-gate.md`](docs/real-world-validation/cross-system/decisions/canonical-redesign-gate.md)
answered `NO`, so that gate does not block here.

None of the above are committed dates — this is a planning sequence, not a schedule.

## Future (beyond v1.0, unscheduled)

- Architecture trajectories (how the declared/observed graph changes over time, not just a single
  snapshot)
- Causal runtime flow analysis (beyond pairwise CLIENT/SERVER and send/receive correlation)
- GraphRAG (retrieval over the graph as LLM context, distinct from today's Cypher-generation-only
  query layer)
- Architecture Wiki (auto-generated narrative documentation from the graph)
- Backstage integration (surfacing the Architecture Knowledge Graph as a Backstage catalog/plugin)

See [`CONTRIBUTING.md`](CONTRIBUTING.md) if you want to help with any of it, and open an issue
before starting significant work on a roadmap item so it doesn't go to waste.
