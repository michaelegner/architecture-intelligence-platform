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

## v0.3 — shipped

Focus: prove the architecture intelligence validated reproducibly in v0.2 survives real,
independently authored systems, and harden only where real evidence justifies it — not to add
another architecture-intelligence dimension. See
[`docs/specifications/0.3.0/`](docs/specifications/0.3.0/) for the full design history and
[`v0.3.0`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.3.0)
for the published release.

| Iteration | Purpose | Status |
|---|---|---|
| I1 — Real-World Validation Contract | Freeze methodology, finding vocabulary, dossier structure, comparison semantics, runbook contract | ✓ complete (internal iteration work; no separate tag cut) |
| I2 — Quarkus Super Heroes Validation | Validate against an external reference architecture | ✓ complete — `v0.3.0-alpha.2` |
| I3 — Apache Airflow Validation | Validate against real-world OSS software | ✓ complete (internal iteration work; no separate tag cut) |
| I4 — Cross-System Model Hardening | Apply only general fixes justified by independent real-system evidence; revalidate both systems | ✓ complete — `v0.3.0-rc.1` |
| I5 — Release Qualification | Qualify the exact candidate and publish `v0.3.0` | ✓ complete — **shipped as `v0.3.0`** |

- ✓ Zero production changes were justified by either system's independent evidence — see
  [`docs/real-world-validation/cross-system/report.md`](docs/real-world-validation/cross-system/report.md)
  for the full cross-system report, finding ledger, and the canonical-redesign-gate answer (`NO`, no
  fundamental Canonical Model redesign is required before v0.4).
- ✓ `v0.3.0-rc.1` was tagged at the I4-qualified candidate, then superseded by `v0.3.0-rc.2` after
  I5's entry qualification found `pyproject.toml`/`uv.lock` still declared project version
  `0.2.0` — a release-blocking inconsistency, fixed under this project's no-substitution policy
  (both RC tags remain immutable historical record).
- ✓ `v0.3.0-rc.2`'s fresh Quarkus/Airflow revalidation, Quick Start, GHCR artifact, and
  CI/CodeQL/Trivy qualification are all recorded in
  [`docs/release-validation/v0.3.0-go-no-go.md`](docs/release-validation/v0.3.0-go-no-go.md)
  (**GO**, decided by the repository owner 2026-09-02).
- ✓ `v0.3.0` was tagged at the exact GO candidate, published, and its GHCR artifact and tagged
  source independently re-verified — see
  [`docs/release-validation/v0.3.0-post-release-verification.md`](docs/release-validation/v0.3.0-post-release-verification.md).

## v0.4 — shipped

**Goal: Trusted Architecture Context for Agents**

Purpose: expose AIP's validated architecture model as stable, snapshot-bound, evidence-backed, and
machine-consumable context for AI agents and architecture tools. See
[`docs/specifications/0.4.0/`](docs/specifications/0.4.0/) for the full design history and
[`v0.4.0`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.4.0)
for the published release.

An agent consuming AIP must be able to determine not only what AIP claims about the architecture,
but why that claim exists and under which evidence and observation context it was derived.

| Iteration | Purpose | Status |
|---|---|---|
| I1 — Service Contract and Dependency Vertical Slice | `ArchitectureIntelligenceService`, `ArchitectureAnswer<T>`, snapshot fingerprinting, dependency projection | ✓ complete — `8031f64` |
| I2 — MCP Vertical Slice and Evidence Drill-Down | `get_service_dependencies`/`get_evidence` MCP tools, independent-client qualification | ✓ complete — `da56025` |
| I3 — Drift Capability and Deterministic Qualification | `get_architecture_drift`, full 3-tool deterministic evaluation, frozen Quarkus/Airflow qualification, hero demo | ✓ complete — `bbde691` |
| I4 — Release Candidate, Publication, and Verification | Candidate freeze, RC/final publication, published-artifact verification | ✓ complete — **shipped as `v0.4.0`** |

- ✓ Exactly three read-only MCP tools (`2026-07-28` protocol) — `get_architecture_drift`,
  `get_evidence`, `get_service_dependencies` — every answer snapshot-bound and, where
  runtime-sensitive, observation-context-bound; zero graph writes through any tool.
- ✓ A complete deterministic tool evaluation (23 scenarios, synthetic plus real-system-derived)
  passes two full clean-state runs with byte-identical semantic output, reusing `v0.3.0`'s frozen
  Quarkus/Airflow evidence rather than re-running either system live.
- ✓ A deterministic, timestamp-frozen hero demo: an independent MCP client discovers all three
  tools and finds `OrderService -> LegacyPricingService` = `OBSERVED_ONLY`, reproducibly from a
  clean state, with no LLM required — see [`docs/mcp.md`](docs/mcp.md).
- ✓ I4.1's entry audit caught a real pre-existing gap (the committed evaluation artifact was bound
  to a stale, pre-squash I3.3 commit rather than the actual I3.4-qualified candidate) and fixed it
  before candidate freeze — see
  [`docs/release-validation/v0.4.0-rc.1-candidate-preparation.md`](docs/release-validation/v0.4.0-rc.1-candidate-preparation.md).
- ✓ `v0.4.0-rc.1`'s full qualification (clean-checkout, hero demo, published-image golden path) and
  the GO decision are recorded in
  [`docs/release-validation/v0.4.0-go-no-go.md`](docs/release-validation/v0.4.0-go-no-go.md)
  (**GO**, decided by the repository owner 2026-09-07).
- ✓ `v0.4.0` was tagged at the exact GO candidate, published, and its GHCR artifact and tagged
  source independently re-verified — see
  [`docs/release-validation/v0.4.0-post-release-verification.md`](docs/release-validation/v0.4.0-post-release-verification.md),
  which also corrects an I4.2 Trivy query-scoping gap (same 3 pre-existing, non-exploitable
  findings already accepted for `v0.3.0`; release blocker count unaffected).

Principle:

> **AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth.**

The tool layer stays downstream of AIP's deterministic architecture model. It must not let an LLM,
agent, or MCP client create canonical facts, bypass semantic validation, or reach a graph write path.

## v0.4.1 — shipped

**Goal: Semantic Hardening for Broader Discovery**

Purpose: harden the qualification and messaging semantics `v0.4.0` shipped, and commit
reproducible evidence of current whole-graph read cost, before any `v0.5` discovery work widens
the surface those semantics govern. Adds no discovery source, Canonical Model family, or MCP tool.
See [`docs/specifications/0.4.1/`](docs/specifications/0.4.1/) for the full design history and
[`v0.4.1`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.4.1)
for the published release.

| Increment | Purpose | Status |
|---|---|---|
| I1 — Qualification Consistency | One declared-versus-observed semantic owner, real-Neo4j differential qualification | ✓ complete — `385604b` |
| I2 — Messaging Semantic Guards | Queue-compatible destination guard, safe messaging service-identity guard | ✓ complete — `d37399b` |
| I3 — Hardening, Qualification and Release | Committed snapshot/read-cost benchmark, exact-candidate qualification, RC/final publication, post-release verification | ✓ complete — **shipped as `v0.4.1`** |

- ✓ One declared-versus-observed semantic owner (`app/qualification/declared_observed.py`)
  governs both the analysis/REST path and MCP; qualification mismatches = 0, coverage mismatches =
  0 against a real-Neo4j differential fixture — see
  [`docs/adr/0010-single-qualification-rule.md`](docs/adr/0010-single-qualification-rule.md)
  (`Accepted`).
- ✓ Runtime messaging requires two independent guards (Queue-compatible destination, safe
  service-identity) before minting any canonical fact; either guard's refusal creates zero
  semantic artifacts — see
  [`docs/adr/0013-no-topic-family-without-guards.md`](docs/adr/0013-no-topic-family-without-guards.md)
  (satisfied).
- ✓ A committed, reproducible read-cost benchmark (`benchmarks/`) makes AIP's current whole-graph
  snapshot/read cost measurable, supplying the baseline half of
  [`docs/adr/0011-snapshot-identity-read-cost.md`](docs/adr/0011-snapshot-identity-read-cost.md)'s
  acceptance condition — no cache or retention change shipped; ADR 0011 stays `Proposed`.
- ✓ `v0.4.1-rc.1`'s full qualification (clean-checkout, hero demo, published-image golden path) and
  the GO decision are recorded in
  [`docs/release-validation/v0.4.1-go-no-go.md`](docs/release-validation/v0.4.1-go-no-go.md)
  (**GO**, decided by the repository owner 2026-09-10).
- ✓ `v0.4.1` was tagged at the exact GO candidate, published, and its GHCR artifact and tagged
  source independently re-verified — see
  [`docs/release-validation/v0.4.1-post-release-verification.md`](docs/release-validation/v0.4.1-post-release-verification.md).

## v0.5 — Broader Architecture Discovery (planned)

**Goal: Broaden what AIP can safely know about distributed systems.**

Focus: broaden architecture discovery now that the semantic core is validated and exposed through
controlled tools, while preserving AIP's evidence, identity, qualification, provenance, and
unsupported-case guarantees.

- Kubernetes discovery as an additional architecture source, with explicit mapping between
  Kubernetes workload/service resources and AIP identities rather than name-based equivalence
- Source-adapter extension seam suitable for broader discovery sources
- Deeper runtime discovery reconciled with existing declared/observed evidence
- Generic source-independent Pub/Sub semantics may enter scope only if Topic/Subscription/Queue
  distinctions and identity guards can be qualified without broker-specific guessing
- Additional adapters remain candidates (for example gRPC/protobuf or Kafka Connect configuration)
  and require separately approved semantics and deterministic conformance tests

Every new discovery source maps through the shared Canonical Model, retains provenance, and must
prove it does not create supported relations from mere co-location, naming coincidence, or an
insufficiently qualified runtime signal.

The structural rule for infrastructure discovery is:

> **WHERE something is does not establish HOW it interacts.**

Therefore deployment/locality evidence and connectivity/cooperation evidence remain independent.
The release continues to preserve:

```text
non-observation != absence
unresolved identity > guessed identity
explicitly unsupported > incorrectly represented as supported
Queue != Topic
Topic != Subscription
co-location != dependency
observed behavior != intent
```

Exit capability:

> **AIP can safely discover a broader distributed-system Current State while retaining the context
> and locality required for later qualification.**

No explicit architectural Intent model, Current↔Intent assessment, historical trajectory model, or
distributed local-assessor runtime is required in v0.5.

## v0.6 — Locality-Aware Current State (planned)

**Goal: Establish architecture knowledge locally and contextually before projecting it into broader
Current-State views.**

Focus: make context/locality an explicit part of Current-State qualification without changing the
fundamental rule that Current State is derived only from Current-State evidence.

AIP should be able to qualify a local assertion under an explicit context such as environment,
region, cluster/namespace, workload identity, service version, or observation window when — and
only when — the available evidence can support that dimension.

Conceptually:

```text
Current-State Evidence
        ↓
Qualified Local Evidence Assessment
        ↓
Deterministic Current-State Projection
        ↓
Evidence-Qualified Current State
```

Key requirements:

- define a first-class internal semantics for qualified local evidence assessment;
- preserve locality/context from source evidence through qualification and projection;
- keep observation window separate from any future Intent effective interval;
- make projection completeness and limitations explicit;
- prevent locally established claims from being silently promoted into universal/global facts;
- keep place/locality and connectivity independent (`WHERE != HOW`);
- prove that adding locality does not weaken deterministic replay, evidence provenance, or
  unsupported/unresolved semantics.

The implementation may remain centralized. A sidecar, DaemonSet, local agent, OTel extension, or
other distributed Local Architecture Assessor is **not** a v0.6 requirement.

Exit capability:

> **AIP can establish what its evidence supports within an explicit locality and observation context,
> and can deterministically project those qualified local assessments into a bounded Current-State
> view.**

## v0.7 — Explicit Architecture Intent (planned)

**Goal: Represent explicit, attributable architectural intent without allowing Intent to alter
established Current State.**

Focus: introduce a source-neutral Intent/Assertion model after the Current-State path is already
locality-aware and independently qualified.

The governing invariant is:

> **For an unchanged evidence snapshot, adding, removing, or changing an Intent artifact must not
> change the established Current State.**

Conceptually:

```text
CURRENT-STATE PATH

Current-State Evidence
        ↓
Qualified Local Evidence Assessments
        ↓
Current-State Projection


INTENT PATH

Explicit Attributable Intent Artifact
        ↓
Intent Assertion
        ↓
Applicable Intent Projection
```

Candidate Intent semantics include explicit promises/capabilities, constraints, required or
prohibited relationships, scope, effective interval, and provenance.

Potential carriers may include OpenAPI Overlay, AsyncAPI-compatible explicit extensions/artifacts,
standalone AIP Intent artifacts, OpenSpec, or other attributable machine-readable specifications.
The carrier must not become the semantic model: AIP should normalize Intent into source-neutral
assertions.

Intent must never be inferred as authoritative from runtime frequency, code structure, naming,
co-location, probabilistic interpretation, or agent-generated rationale.

Exit capability:

> **AIP can ingest explicit architectural Intent with provenance, scope, and effective applicability
> without treating that Intent as evidence of Current State.**

No Current↔Intent compliance/enforcement engine, historical trajectory model, migration scripting,
or automatic remediation is required in v0.7.

## v0.8 — Qualified Architecture Assessment (planned)

**Goal: Assess independently established Current State against independently established applicable
Intent.**

Focus: add a separate, read-only, evidence-linked assessment layer over the two already independent
semantic paths.

The dependency direction is:

```text
Current-State Evidence
        ↓
Qualified Local Evidence Assessments
        ↓
Current-State Projection
                         \
                          +--> Qualified Current ↔ Intent Assessment
                         /
Explicit Intent Artifacts
        ↓
Applicable Intent Projection
```

Never:

```text
Intent
  ↓
Current-State qualification
```

Assessment semantics must preserve both temporal dimensions independently:

```text
observation_window
    = when Current-State evidence was observed

effective_from / effective_until
    = when the explicit Intent applies
```

Possible assessment outcomes may include concepts such as `ESTABLISHED`, `CONTRADICTED`,
`NOT_ESTABLISHED`, `INSUFFICIENT_EVIDENCE`, and `CONFLICTING_EVIDENCE`, but the exact public
vocabulary must not be frozen until deterministic truth tables and independently authored evaluation
fixtures exist.

`CONTRADICTED` must never mean merely "not observed" unless an explicit closed-world rule permits
that interpretation.

The agent-facing surface may gain additional read-only Architecture Intelligence capabilities if
needed, but MCP transport should remain stable and generic graph/Cypher access should remain outside
the correctness path.

Exit capability:

> **AIP can explain where an independently established Current State aligns with, diverges from, or
> cannot yet be evaluated against the explicit Intent that applies in the selected context.**

Explicitly out of scope for v0.8:

- architecture trajectories / historical architecture state;
- migration planning or transformation scripting;
- automatic remediation;
- policy authoring, approval workflow, or CI blocking;
- distributed local-assessor deployment as a requirement;
- agent-generated authoritative Intent.

## v0.9 — Contract Freeze / Production Qualification (planned)

**Goal: Stabilize and production-qualify the architecture-intelligence contracts intended for
v1.0.**

Focus: freeze only semantics and public contracts that have survived implementation, deterministic
evaluation, and real-system qualification across v0.5-v0.8.

Qualification/freeze scope includes, where actually implemented and accepted:

- Canonical Model compatibility review
- Current-State evidence and qualification semantics
- locality/context semantics and Current-State projection contracts
- explicit Intent and applicable-Intent projection contracts
- qualified Current↔Intent assessment contracts
- derivation-lineage and evidence/provenance requirements
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

v0.9 must not freeze hypothetical contracts merely because they appeared in earlier strategy or
roadmap text. A capability that did not survive implementation and qualification is either removed,
kept explicitly experimental, or deferred beyond v1.0.

Exit capability:

> **The architecture-intelligence model and public contracts intended for v1.0 are semantically
> stable, reproducible, migration-aware, and production-qualified.**

## v1.0 — Stable Architecture Intelligence Platform (planned)

Focus: publish the first stable AIP release with mature architecture-intelligence semantics and
public contracts. Requires: a stable architecture-intelligence model; stable public REST and MCP
contracts; stable Graph Schema and Adapter SPI; a documented compatibility/migration policy;
production qualification completed; critical semantic errors = 0; release blockers = 0.

## Sequencing principle

```text
v0.3  validation and hardening
  -> v0.4  trusted architecture context for agents
  -> v0.5  broader architecture discovery
  -> v0.6  locality-aware Current State
  -> v0.7  explicit architecture Intent
  -> v0.8  qualified architecture assessment
  -> v0.9  contract freeze and production qualification
  -> v1.0  stable platform
```

In capability terms:

```text
VALIDATE
   ↓
EXPOSE
   ↓
DISCOVER
   ↓
ESTABLISH LOCALLY
   ↓
REPRESENT INTENT
   ↓
ASSESS
   ↓
FREEZE
```

The ordering is semantic, not merely chronological:

1. broader evidence must be trustworthy before it is used to establish more Current State;
2. locality-aware Current State must remain independently derivable before Intent exists;
3. Intent must be explicit and attributable before AIP compares Current State with it;
4. Current↔Intent assessment must remain read-only and downstream of both independent projections;
5. only implemented and qualified contracts are frozen for v1.0.

`v0.3` carried a hard gate: had either real-system dossier shown the Canonical Architecture Model
needed a fundamental breaking redesign, AIP would not proceed to v0.4 until that redesign was
specified, implemented, and revalidated — I4's
[`canonical-redesign-gate.md`](docs/real-world-validation/cross-system/decisions/canonical-redesign-gate.md)
answered `NO`, so that gate did not block.

None of the above are committed dates — this is a planning sequence, not a schedule. The detailed
scope of each planned release remains subject to its release specification and qualification gate;
the semantic dependency between the release themes is the stable part of this roadmap.

## Future (beyond v1.0, unscheduled)

- Historical architecture-state retention/import sufficient for principled temporal reasoning
- Architecture trajectories (how evidence-qualified Current State and applicable Intent evolve over
  time, once historical identity/provenance continuity exists)
- Distributed Local Architecture Assessor deployment options (for example sidecar, DaemonSet, OTel
  extension, or local gateway) if real-system evidence shows that moving deterministic qualification
  closer to the locality provides correctness or operational value
- Safe architecture transformation research, potentially including Bigraphical Reactive Systems,
  process calculi, type systems, temporal logic, or related formalisms
- Causal runtime flow analysis (beyond pairwise CLIENT/SERVER and send/receive correlation)
- GraphRAG (retrieval over the graph as LLM context, distinct from today's Cypher-generation-only
  query layer)
- Architecture Wiki (auto-generated narrative documentation from the graph)
- Backstage integration (surfacing the Architecture Knowledge Graph as a Backstage catalog/plugin)

See [`CONTRIBUTING.md`](CONTRIBUTING.md) if you want to help with any of it, and open an issue
before starting significant work on a roadmap item so it doesn't go to waste.
