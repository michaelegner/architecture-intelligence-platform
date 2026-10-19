# Roadmap

**Product mission:** Build architecture intelligence that agents can consume and humans can inspect,
challenge, and understand.

The current product boundary is **distributed architecture across autonomous services/components**.
The initial adoption wedge remains AI-assisted bounded change in existing distributed systems: before
editing one component, help the agent identify which external components and distributed
relationships require inspection, why they are relevant, what evidence supports that relevance, and
what remains unresolved.

The roadmap follows the doctrine:

> **Current State is locally observed. Intent is locally attributable. Assessment is locally made.
> AIP answers distributed-architecture questions by projecting the relevant local views into a
> bounded, evidence-qualified result.**

This does **not** make a complete enterprise architecture model a product goal. AIP may retain
evidence from many systems, but it composes local views only as far as a concrete
distributed-architecture question requires. Repository/source analysis remains complementary:
AIP should establish where investigation crosses autonomous boundaries; source analysis should
establish what each implementation does.

## Versioning

AIP follows [Semantic Versioning](https://semver.org/) with an additional product discipline from
`v0.5.0` onward:

> **A new `0.x.0` capability release should add at least one materially new class of
> evidence-qualified architecture question that AIP can answer safely and deterministically.**

The release is not complete merely because the semantic core exists. The new question must ship
end-to-end through the supported public adapters, with evidence/provenance continuity, qualification,
deterministic evaluation, and release qualification.

A patch release `0.x.y` preserves the `0.x.0` architecture-question space. It is normally for a
**post-release correction or maintenance change** that preserves the intended semantic contract:
for example a defect fix, security/dependency patch, documentation correction, or
semantics-preserving performance improvement.

A patch release may also carry a **bounded, independently validated semantic completion** of an
existing architecture-question class when real-system evidence demonstrates that the current model
cannot preserve a required distinction safely. Such a completion may extend canonical or public
semantics only as needed to answer the existing question class more correctly or completely; it
must not introduce a materially new architecture-question class, and it must ship with appropriate
evidence/provenance continuity, deterministic evaluation, and release qualification.

Patch releases are not pre-planned buckets for unfinished `0.x.0` work, nor a way to move a new
architecture-question class out of a capability release.

After the final pre-1.0 capability release, contract freeze and production qualification use
`v1.0.0-rc.N` prereleases rather than inventing another `0.x.0` product release with no new
architecture question.

Historical `v0.1`–`v0.4` releases predate this question-oriented versioning doctrine and remain
unchanged.

Not yet guaranteed stable pre-1.0 — expect breaking changes on a capability-release minor bump or
during the `v1.0.0-rc.N` freeze phase:

- Canonical Model (`app/canonical/model.py`)
- REST API surface
- Graph persistence schema (node labels, relationship types/properties; implementation
  compatibility surface, not the public Architecture Knowledge contract)
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

## v0.4.2 — shipped

**Goal: MCP Client Interoperability**

Purpose: make the existing read-only Architecture Intelligence MCP surface directly consumable by
qualified coding-agent clients, without changing architecture semantics. Adds a negotiated MCP
transport mode alongside the existing direct-envelope mode; adds no discovery source, Canonical Model
family, or MCP tool. See [`docs/specifications/0.4.2/`](docs/specifications/0.4.2/) for the full
design history and
[`v0.4.2`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.4.2)
for the published release.

| Increment | Purpose | Status |
|---|---|---|
| I1 — Dual-Mode MCP Transport | Negotiated MCP transport mode alongside the existing direct envelope, identical Architecture Answer semantics in both | ✓ complete — `2b6f865` |
| I2 — Client-Ready Demo and Documentation | Candidate setup guides for Codex CLI, Claude Code, Cursor, and VS Code; local security boundary documentation | ✓ complete — `279c0ae` |
| I3 — Actual-Client Qualification, Release, and Post-Release Verification | Real-client qualification (not test-suite-only), candidate freeze, RC/final publication, post-release verification | ✓ complete — **shipped as `v0.4.2`** |

- ✓ A negotiated MCP transport mode (standard `initialize`/session handshake), dispatching to the
  same three read-only tools with byte-identical `ArchitectureAnswer` semantics as the existing
  direct-envelope mode — see [`docs/mcp.md`](docs/mcp.md) and
  [`docs/adr/0014-negotiated-mcp-client-interoperability.md`](docs/adr/0014-negotiated-mcp-client-interoperability.md).
- ✓ Four coding-agent client families qualified end to end against a real, running server — not only
  a test suite — each completing the full protocol-qualification and reconnect workflow with
  byte-for-byte identical architecture results: Codex CLI `0.154.0`, Claude Code CLI `2.1.270`,
  Cursor `3.20.17`, VS Code `1.137.0` + GitHub Copilot Chat. Cross-client semantic mismatches = `0`,
  evidence-meaning mismatches = `0` — see the
  [qualified client/platform matrix](docs/release-validation/v0.4.2-client-qualification.md).
- ✓ Actual-client qualification found and fixed two real interoperability defects the test suite
  alone had not caught: a negotiated-mode routing gap that let an unbounded direct-marked method
  reach the SDK and hang the server (found via Claude Code), and an over-strict rejection of a
  negotiated follow-up missing the `MCP-Protocol-Version` header, stricter than both the pinned SDK's
  own fallback and the MCP specification's own backward-compatibility allowance (found via VS
  Code/GitHub Copilot Chat) — both fixed and reconfirmed before candidate freeze; see ADR 0014's two
  Amendment sections.
- ✓ `v0.4.2`'s full qualification (candidate gate table, four qualified tuples, cross-client
  comparison) and the technical GO decision are recorded in
  [`docs/release-validation/v0.4.2-go-no-go.md`](docs/release-validation/v0.4.2-go-no-go.md)
  (**RELEASE_READY**, publication authorized by the repository owner 2026-09-14).
- ✓ `v0.4.2` was tagged at the exact GO candidate, published, and its GHCR artifact and tagged source
  independently re-verified — see
  [`docs/release-validation/v0.4.2-post-release-verification.md`](docs/release-validation/v0.4.2-post-release-verification.md),
  which also records an authorized-owner risk acceptance for 12 newly-disclosed HIGH/CRITICAL Trivy
  findings, all Debian base-image OS package patches unrelated to any AIP code or dependency change.

## v0.5 — Broader Architecture Discovery — shipped

**Goal: Broaden what AIP can safely know about distributed systems.**

Shipped and post-release verified as [`v0.5.0`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.5.0) on 2026-09-26 (`SHIPPED_VERIFIED`; see
[`docs/release-validation/v0.5.0-post-release-verification.md`](docs/release-validation/v0.5.0-post-release-verification.md)
and [`docs/specifications/0.5.0/`](docs/specifications/0.5.0/) for the full design history). I4 ended
`GO`; Kubernetes discovery shipped `OFFLINE_ONLY`.

**Product questions:**

> **Where is this service deployed?**  
> **Which deployment identities are unresolved?**

The [v0.5.0 parent specification](docs/specifications/0.5.0/specification.md) defines the release
contract. The scope combines ingestion hardening, one new discovery-source family, and bounded
identity reconciliation while preserving evidence, provenance, unsupported-case, and read-only
Architecture Intelligence guarantees.

| Increment | Scope and exit |
|---|---|
| I1 — Source Ingestion Foundation | One adapter/discoverer seam for existing OpenAPI, AsyncAPI, Architecture Manifest, and filesystem discovery; bounded local references, deterministic identity/inventory/replay, and explicit versioned migration mappings. |
| I2 — Kubernetes Discovery | Kubernetes is the only new source family. Deterministic offline discovery is mandatory; bounded read-only live discovery is optional and decided before implementation. Infrastructure claims do not establish application interaction. |
| I3 — Runtime Identity Reconciliation | Bounded declared-Service/Workload association through explicit annotations, configured mappings, or qualified OTel Pod-UID/owner-chain evidence. The public relation is `DEPLOYED_AS`; disagreements remain conflicts, not precedence-based guesses. Consolidates public Architecture Knowledge access around REST and standard negotiated MCP over one `ArchitectureIntelligenceService` semantic owner, retiring the v0.4.x direct MCP envelope. |
| I4 — Conditional Pub/Sub | Recorded `GO` or `DEFER`. Source-independent semantics require qualified Queue/Topic/Subscription distinctions and identity guards. No live broker adapter is introduced. |
| I5 — Cross-System Qualification | Two materially different systems and negative fixtures; deterministic cross-source qualification and evidence-justified hardening. |
| I6 — Release and Post-Release Verification | Exact-candidate qualification, publication disposition, and separate unpublished `RELEASE_READY_NOT_PUBLISHED` or published `SHIPPED_VERIFIED` outcomes. Publication requires authorization; shipped verification requires final-artifact and security evidence. |

The [I1 implementation contract](docs/specifications/0.5.0/i1-source-ingestion-foundation.md)
accepts exactly OpenAPI `3.0.3`/`3.1.0`/`3.1.2` (the last added by its Draft 0.3 amendment) and
AsyncAPI `2.6.0`. It preserves composition
structurally with explicit limitations. Equal content does not establish shared Schema/Message
identity: owner-scoped IDs remain distinct unless explicitly mapped. Portable, versioned
Service/Schema/Message/Queue mappings preserve qualified legacy fixture meaning without naming
fallbacks. Additional dialects require a reviewed amendment and qualification.

Source disappearance is not authorized removal. Expiration requires a qualified complete
same-scope inventory or an explicit versioned tombstone. Failed/incomplete discovery preserves the
last committed state; changed scopes cannot silently expire previous ownership.

I2/I3 freeze concrete claim schemas and public exposure locations before implementation and
fixtures. The existing three read-only MCP tools remain the scope budget. During I3, REST and
standard negotiated MCP become the two public Architecture Knowledge adapters over
`ArchitectureIntelligenceService`; the deterministic evaluator calls the service directly, and the
v0.4.x direct MCP envelope is retired. A live-discovery decision activates live-specific
qualification in I2, not I1.

> **WHERE something is does not establish HOW it interacts.**

Every source maps through the shared Canonical Model. Placement is retained as source/context
evidence only; v0.5 exposes no locality-qualified claim or projection.

The release preserves these distinctions:

- Non-observation is not absence.
- Source disappearance is not authorized source removal.
- An unresolved identity is preferable to a guessed identity.
- Explicitly unsupported semantics are preferable to incorrectly representing them as supported.
- A Queue is distinct from a Topic, and a Topic is distinct from a Subscription.
- A Service, Kubernetes Service, Workload, and Pod are distinct identities.
- Co-location does not establish a dependency.
- Observed behavior does not establish Intent.

Exit capability:

> **AIP can safely discover a broader distributed-system Current State while retaining the context
> and locality required for later qualification.**

gRPC/protobuf, Kafka Connect, other new source families, explicit Intent, Current↔Intent assessment,
historical trajectories, and distributed local-assessor deployment are outside v0.5. I4 may end in
`DEFER` without blocking the remaining qualified release.

## v0.5.1 — Realistic Architecture Demo — shipped

Shipped and post-release verified as [`v0.5.1`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.5.1) on 2026-09-27 (`SHIPPED_VERIFIED`, lightweight release path; see
[`docs/release-validation/v0.5.1-release-record.md`](docs/release-validation/v0.5.1-release-record.md)
and [`docs/specifications/0.5.1/specification.md`](docs/specifications/0.5.1/specification.md)).

**Goal: Demonstrate how users and coding agents obtain architecture knowledge needed to work on a
realistic multi-service system.**

- provide a ready-to-run Quarkus Super Heroes demo using the final v0.5.0 I5 dossier and qualified evidence;
- demonstrate task-driven questions and follow-up exploration, starting with understanding the fight
  service before changing it;
- make dependencies, runtime qualification, deployment bindings, and supporting evidence accessible
  through existing REST and MCP capabilities;
- provide deterministic demo preparation/replay and example conversations using an existing agent client;
- preserve unsupported/unresolved boundaries and show limitations in answers;
- keep the existing minimal demo;
- no new Architecture Knowledge semantics, source families, or MCP tools.

Exit capability:

> **A user and their coding agent can obtain and inspect architecture context for a concrete Quarkus
> development task without reconstructing that context themselves.**

## v0.6 — Locality-Aware Current State (shipped)

Published **v0.6.0 on 2026-10-05**; terminal outcome **SHIPPED_VERIFIED**. See the
[post-release verification](docs/release-validation/v0.6.0-post-release-verification.md).

**Goal: Establish architecture knowledge locally and contextually before projecting it into broader
Current-State views.**

**Product questions:**

> **Where is this dependency established?**  
> **Does this relation differ by supported locality?**

Focus: make context/locality an explicit part of Current-State qualification without changing the
fundamental rule that Current State is derived only from Current-State evidence.

The accepted v0.6.0 minimum is bounded direct HTTP `CALLS` under environment and whole-UTC-day
observation context, with evidenced caller cluster/namespace and exact captured Workload identity
through CLIENT Pod UID → Kubernetes owner chain. It does not establish target locality, local
absence, global/exclusive dependency sets or historical snapshot access.

Region, tenant, service-version locality and messaging locality are **deferred/unassigned
candidates**. They are not allocated to v0.7 or v0.8 by this release. The product pilot remains
`NOT_RUN`, with its product-value gate carried into v1.0-rc stable-contract admission.

Conceptually, AIP evaluates Current-State evidence into qualified local evidence assessments and
then uses deterministic Current-State projection to produce evidence-qualified Current State.

Key requirements:

- define a first-class internal semantics for qualified local evidence assessment;
- preserve locality/context from source evidence through qualification and projection;
- keep observation window separate from any future Intent effective interval;
- make projection completeness and limitations explicit;
- prevent locally established claims from being silently promoted into universal/global facts;
- treat local as an explicit scope, which may span components when supported by evidence;
- require separate applicable evidence and qualification rules for new cross-boundary or system-level
  claims; composing local results alone does not establish causal flows or end-to-end outcomes;
- keep place/locality and connectivity independent (`WHERE != HOW`);
- prove that adding locality does not weaken deterministic replay, evidence provenance, or
  unsupported/unresolved semantics.

The implementation may remain centralized. A sidecar, DaemonSet, local agent, OTel extension, or
other distributed Local Architecture Assessor is **not** a v0.6 requirement.

Exit capability:

> **AIP can establish what its evidence supports within an explicit locality and observation context,
> and can deterministically project those qualified local assessments into a bounded Current-State
> view.**

## v0.6.1 — Broker Semantic Completion (shipped)

Published **v0.6.1 on 2026-10-06**; terminal outcome **SHIPPED_VERIFIED**. See the
[release record](docs/release-validation/v0.6.1-release-record.md).

**Goal: Complete AIP's existing messaging semantics with evidence-qualified Broker knowledge.**

**Product question:**

> **Which messaging infrastructure does this service use, and how far can the available evidence safely resolve that relationship?**

Focus: promote broker identity and broker-level connectivity from supporting messaging identity
information into qualified Architecture Knowledge where source evidence justifies it, without
weakening or inventing Queue, Topic, Subscription, Message, producer, or consumer semantics.

This is a **semantic completion of the existing messaging capability**, not a new
architecture-question class. Existing Quarkus Super Heroes, FINOS FluxNova/CALM, and Apache Airflow
evidence provides the cross-system basis for defining and qualifying the missing Broker semantic
level.

Key requirements:

- define the smallest source-independent Broker semantics and identity rules;
- ingest and reconcile Broker evidence without name-based identity guessing;
- keep Broker connectivity independent from richer Queue/Topic/Subscription/Message semantics;
- expose qualified Broker knowledge through the existing Architecture Intelligence surfaces;
- qualify the semantics deterministically against Quarkus Super Heroes, FINOS FluxNova/CALM, and
  Apache Airflow;
- do not introduce a generic `CONNECTED_TO` relation or a live broker adapter.

Exit capability:

> **AIP can establish which messaging infrastructure a service is evidenced to use and state how far
> that relationship can be resolved without inventing richer messaging semantics.**

## v0.6.2 — Live AIP Demo (shipped)

Published **v0.6.2 on 2026-10-09**; terminal outcome **SHIPPED_VERIFIED**. See the
[release record](docs/release-validation/v0.6.2-release-record.md).

**Goal: Make the existing v0.6 Current-State and messaging knowledge tangible in a realistic,
hosted product demo.**

**Demo question:**

> **Which services receive from the messaging destination this service publishes to, how far can
> the evidence resolve that topology, and what must I still inspect before changing the event?**

Focus: establish a hosted, persistent Live AIP Demo using Pitstop, continuously driven by controlled
traffic and queried against explicit completed observation windows. This is a demo release, not a
capability release: it adds no new Architecture Knowledge semantics, source family, schema, or MCP
tool. Its one product change is a small hardening prerequisite (I0) that fixes two evidence-correctness
defects found by the I1 gate spike: runtime evidence must not create undeclared receiver routes, and a
claim for an explicit observation window must not cite evidence from outside it. See
[`docs/specifications/0.6.2/specification.md`](docs/specifications/0.6.2/specification.md)
for the detailed scope.

- run a canonical hosted AIP + Pitstop demo continuously with accumulated OTLP runtime evidence and
  disclosed operator-authored AsyncAPI declarations;
- make semantic reproducibility, explicit observation windows, evidence resolution, limitations,
  and abstention visible in the live experience;
- provide a one-command local replay for reproducibility and offline use while keeping the hosted
  live instance canonical;
- demonstrate a realistic `MaintenanceJobFinished` change where AIP resolves the messaging topology
  the agent should inspect without claiming payload or field usage;
- provide a Claude Code plugin with an architecture-aware development skill and `/aip:inspect`;
  any Mod-based UX remains optional and non-blocking;
- use the persistent demo as the product-demo base that later releases can extend for API-aware
  Current State and explicit Intent.

Exit capability:

> **A user and coding agent can use a hosted AIP instance to obtain evidence-qualified messaging
> context from the last completed supported observation window for a realistic development task, see
> the limits of that knowledge, and identify what still needs inspection without reconstructing the
> topology from the checkout alone.**

## v0.6.3 — Runtime and Import Robustness (shipped)

Published **v0.6.3 on 2026-10-11**; terminal outcome **SHIPPED_VERIFIED**. See the
[release record](docs/release-validation/v0.6.3-release-record.md).

**Goal: fix two bounded robustness defects without changing the v0.6 architecture-question space or evidence semantics.**

See the accepted maintenance specification in [docs/specifications/0.6.3/specification.md](docs/specifications/0.6.3/specification.md).

The release contains exactly two maintenance corrections:

- **Telemetry responsiveness:** POST /v1/traces currently calls synchronous ingestion on the FastAPI event loop, so REST, MCP and UI requests can wait for the whole batch. Move blocking ingestion work off the event loop while preserving serialized ingestion. The committed benchmarks/traces_stall.py baseline remains measurement evidence, not a product SLO.
- **Per-source import rejection/diagnosis (#305):** an OpenAPI/AsyncAPI document containing an integer outside RFC 8785's safe integer domain must be rejected with an explicit diagnostic instead of escaping as an uncaught exception. The overall discovery run remains `PARTIAL`, nothing from that run commits, and previously accepted state is preserved. Preserve strict current hashing semantics; do not add lossy coercion, alternate encoding or a hash migration in this patch release.

No API-aware Current-State semantics, new source family, canonical relationship, public Architecture Intelligence question or MCP tool belongs in v0.6.3. Broader support for out-of-range JSON integers is deferred to a separate semantic decision.

## v0.7 — API-Aware Current State (shipped)

Published **v0.7.0 on 2026-10-16**; terminal outcome **SHIPPED_VERIFIED**. See the
[post-release verification](docs/release-validation/v0.7.0-post-release-verification.md) and the
[release notes](docs/release-validation/v0.7.0-release-notes.md). Apache APISIX was selected as the
reference gateway in I0 (Kong, Gravitee and Tyk were surveyed); the configured-access model is qualified for
APISIX only, and associations need a mapping or an exact match. The scope below is the original plan.

**Goal: Establish evidence-qualified Current-State knowledge of how APIs are exposed and consumed,
while retaining the distinct meanings of contracts, operations, gateway objects, application services,
consumers, and observed interactions.**

**Product question:**

> **How are APIs exposed and consumed, and what can the available evidence establish about those
> relationships?**

**First bounded validation question:**

> **Which configured consumer/API relationships have matching observed runtime usage in a selected
> environment and observation window, and which remain unestablished from the available evidence?**

The first vertical slice SHALL use **real gateway configuration and consumer-attributed usage
measurements**. The reference system is not AIP's canonical terminology or a
required gateway for later adapters (APISIX was selected in I0). Its actual source capability determines whether a relationship
can be described as a product subscription, access registration, ACL membership, or another
configured relationship; AIP must not invent a subscription from the mere presence of a consumer.
Broader gateway/provider support remains incremental and separately qualified.

Minimum requirements for the slice:

- freeze a small, **platform-independent semantic vocabulary**, keeping API contract/version,
  API operation, gateway route/service, application service, gateway consumer, configured access
  relationship, and observed interaction distinct; API product, business capability, domain boundary,
  and organizational owner must not be inferred from a technical name, URL, or graph proximity;
- preserve the distinction between **integration style**, **interaction pattern**, and **runtime
  component**: gateway configuration and telemetry may establish bounded API exposure, configured
  access, and observed usage, but do not establish a system-wide integration style, architectural
  ownership, or completeness of the integration landscape; neither gateway presence nor absent
  gateway observations justify those inferences;
- reconcile source identities through accepted source-specific evidence or explicit mappings,
  including unresolved, ambiguous and conflicting cases; association is not necessarily entity
  equivalence;
- reuse source inventory, revision, authoritative-removal, snapshot/replay, and provenance semantics;
  preserve contract-version applicability and any evidenced source authority without treating the
  newest or similarly named artifact as automatically canonical;
- acquire or pin real, **consumer-attributed** usage evidence with bounded environment/window,
  measurement meaning, identity resolution, and applicable telemetry coverage; missing metrics must
  not turn into zero observed requests or a claim of non-use;
- qualify configured and observed relationships independently as Current State: configured access
  does not establish actual usage and does not become authoritative architectural Intent;
- expose one deterministic, question-specific Architecture Intelligence answer through the shared
  semantic service, REST and negotiated MCP, with same-snapshot evidence resolution, limitations,
  bounded enumeration, and independently authored positive/negative real-source tests;
- run a product-value pilot that includes useful answer coverage and the cost of setup, source
  synchronization, attribution, and identity mapping; record a continue/narrow/defer/stop disposition.

**Explicitly outside the initial v0.7 slice:** complete enterprise/API-product cataloging,
business-capability classification, automatic ownership inference, multiple gateway integrations as
a release gate, generic analytics/dashboarding, formal Intent, policy/compliance assessment, approval
workflows, and historical architecture reconstruction. Additional OpenAPI/AsyncAPI, repository,
CI/CD, architecture-model, and vendor sources may enter only through separately qualified,
question-driven increments. The new source family must not weaken the already accepted v0.6
locality or v0.5 Current-State contracts.

**External research inputs:** [Understanding API Landscapes, Not Just Managing Them](https://adorsys.com/en/techradar/understanding-api-landscapes-not-just-managing-them/)
and [The API Is Not the Boundary](https://adorsys.com/en/techradar/the-api-is-not-the-boundary/).
They motivate the validation question; they are not AIP's semantic authority.

Exit capability:

> **AIP can relate an API's evidenced exposure and configured consumers to independently observed,
> consumer-attributed usage, and state which relationships are established, unresolved, or
> insufficiently supported in the selected context without silently inventing product, business,
> authorization, or Intent claims.**

## v0.7.1 — Broker-Mediated Consumer Attribution (planned)

**Goal:** complete the existing messaging Current-State question so AIP can qualify which Services
consume a broker-mediated destination without collapsing broker-native identities.

**Product question:**

> **For destination D in environment E, which Services can the available evidence safely attribute
> as consumers, and with what qualification?**

**Evidence basis:** Round 5 found the question recurring across Kafka and RabbitMQ systems. PR #527
then demonstrated a **SUPPORTED EVIDENCE PATH** for Kafka: broker-held group/member state established
topic attachment, while separate configuration/runtime evidence mapped that identity to a Service
without treating the consumer group as a Subscription.

Requirements:

- define the smallest source-independent consumer-attribution semantics while keeping Kafka groups,
  RabbitMQ queues/bindings, Service Bus subscriptions, destinations, and Services distinct;
- keep broker evidence and Service-mapping evidence separate and preserve provenance, environment/time,
  unresolved mappings, and the difference between attachment and actual message processing;
- qualify the semantics against the captured Kafka case and at least one contrasting RabbitMQ shape;
- add only the bounded ingestion/public-surface changes needed for this existing question.

Out of scope: general broker-topology modelling, routing predicates, lag/offset/rebalancing,
DLQ/retry topology, or broad broker administration.

**Exit capability:**

> **AIP can evidence-qualify Service-level consumer attribution for broker-mediated destinations
> without inventing equivalence between distinct broker-native concepts.**

## v0.7.2 — Context-Engine Interoperability + Product-Boundary Qualification (planned)

**Goal:** make the complete v0.7.x Architecture Intelligence MCP surface consumable through the
hosted read-only endpoint and use a mature context engine to challenge AIP's product boundary before
v0.8 scope is finalized.

**Product-boundary question:**

> **Given comparable access to source and distributed-system evidence, does adding AIP materially
> improve what a coding agent can establish, needs to inspect, or changes beyond a mature context
> engine alone?**

**Unblocked** is the initial representative mature context engine and its open-source
`context-engine-simulator` is the initial evaluation harness; neither is a normative dependency or
exclusive comparator.

The hosted product-validation system moves from Pitstop to **Sokol111** so v0.7.2 and v0.8 can use
the same realistic distributed system. Pitstop remains historical/local demo and regression material;
it is not removed.

Scope:

- update the hosted read-only MCP deployment to expose the complete six-tool v0.7.1 surface,
  including `get_api_consumer_usage` and `get_destination_consumers`, with external-client,
  evidence-drill-down and public-edge verification;
- provide a Sokol111 hosted dataset/configuration that preserves what the existing v0.7.x semantics
  actually establish. Positive, partial, unresolved and insufficient-evidence outcomes are all valid;
  do not manufacture evidence merely to exercise a tool;
- run a controlled comparison of **Unblocked alone** versus **Unblocked + AIP** on one realistic
  bounded Sokol111 change, using the same coding agent/task and comparable repository,
  direct-execution and raw distributed-evidence access;
- evaluate architecture correctness and useful investigation impact first: relevant external
  components found or missed, unsupported claims, preserved unresolved cases, provenance/context,
  and material changes to the plan/implementation. Time, tokens and cost are secondary product
  measures;
- record whether task vocabulary can reach the existing canonical AIP query contexts naturally.
  A new discovery/search capability is **not pre-authorized**; if navigation is a material blocker,
  record the finding and make an explicit scope decision before adding public semantics or tools.

v0.7.2 does **not** add a new architecture-question class or compose the existing v0.7.x answers
into a new architecture conclusion. API-consumer usage, broker-mediated consumer attribution,
dependency, deployment and locality answers remain independent qualified views. The experiment may
observe how Unblocked composes them, but AIP-owned cross-capability composition remains a v0.8
decision.

**Exit capability / checkpoint:**

> **A mature context engine can consume AIP's complete hosted v0.7.x Architecture Intelligence
> surface in a realistic coding workflow, and a controlled comparison records whether AIP adds
> material distributed-architecture value beyond that context engine alone.**

Record **continue, narrow, integrate, defer, or stop**. The result is an input to the v0.8 scope:
v0.8 must not duplicate context-engine composition that v0.7.2 shows can be done safely outside AIP.

## v0.8 — Cross-Boundary Architecture Knowledge + Real-World Product Demonstration (planned; scope shaped by v0.7.2)

**Goal:** deliver the first complete real-world product demonstration of AIP on Sokol111, with
AIP-owned Current-State composition/membership semantics limited to the gap that survives the
v0.7.2 context-engine checkpoint.

**Product question:**

> **Which evidence-qualified distributed relationships cross independently established System or
> Component boundaries?**

**Product-boundary question:**

> **Does that cross-boundary evidence materially change what a coding agent can establish and needs
> to inspect before a bounded change, beyond repository/source analysis and direct execution
> alone?**

The core rule remains:

> **A relationship does not establish a boundary. A boundary does not establish a relationship.**

The detailed v0.8 composition boundary is intentionally **not frozen before v0.7.2**. If a mature
context engine can safely compose AIP's existing qualified views for the bounded-change workflow,
v0.8 should narrow to the AIP-owned semantic gap and integration proof rather than duplicate that
context-engine capability. If v0.7.2 shows that semantic distinctions, uncertainty or provenance are
lost outside AIP, v0.8 may own the smallest composition semantics needed to preserve them.

Where AIP owns the composition, it may classify already-qualified relationships as within-boundary,
cross-boundary, or unresolved. System/Component membership must be established independently; it
must not be inferred from connectivity, repository structure, naming, deployment placement, or
graph proximity. Only the composition/membership semantics needed for the bounded cross-boundary
question are in scope; a generic enterprise architecture metamodel remains out of scope.

### Real-world product demonstration

v0.8 uses **Sokol111** for one realistic bounded-change workflow and compares AIP with strong
repository/source analysis. **Teamscale 2026.7.x is the initial representative tool, not a normative
dependency or exclusive comparator; equivalent mature tooling may be substituted or added.**

The demonstration should use the applicable AIP Current-State capabilities available at v0.8
entry — including dependency/evidence drill-down, deployment, locality, messaging, **v0.7.0
API-aware Current State**, and broker-mediated consumer attribution. How those qualified views are
composed into the workflow is determined by the v0.7.2 result: AIP should own only composition
semantics that cannot safely remain in the context/agent layer. Partial, unresolved and unsupported
results remain valid; the demo must not manufacture positive evidence merely to exercise a feature.

Where the demonstration depends on transient runtime or environment evidence, freeze the relevant
evidence, context, mappings and rules so the same architectural conclusion can be replayed
deterministically. Replay of a captured snapshot is not evidence that the same Current State still
holds later; freshness requires new evidence.

The comparison should give source-analysis tooling realistic access to the repositories,
configuration and contracts it can analyze, while retaining realistic direct-execution checks
available to the coding agent. AIP contributes independently qualified distributed-system evidence.
The product test is whether the combined workflow materially improves what the coding agent can
establish and must inspect beyond strong source analysis and direct execution without introducing
unsupported architectural claims.

**Exit capability:**

> **AIP can compose independently established System/Component membership with evidence-qualified
> distributed Current State into a bounded cross-boundary view on a real system.**

The product checkpoint records **continue, narrow, integrate, defer, or stop** based on whether that
view materially improves the coding-agent workflow and justifies AIP's evidence and maintenance
cost. The same checkpoint informs whether later AIP-owned external Intent and local distributed
Assessment remain justified.

## v0.9 — External Architecture Intent (provisional; checkpoint-dependent)

**Status:** provisional candidate scope. Execution is not authorized by this roadmap alone. The v0.8
checkpoint must first demonstrate that AIP should own external distributed Intent rather than consume
it from an adjacent architecture/governance product.

**Goal:** represent explicit, locally attributable promises made by autonomous components to the
outside, without allowing those promises to alter established Current State.

**Product question:**

> **What does this autonomous service/component explicitly promise to the outside in this context?**

For AIP, Intent is deliberately narrower than general architecture policy or internal design intent.
Repository-local layering rules, package rules, class dependencies, and internal source conformance
remain outside this product capability.

The governing separation is that **Current State describes locally observed distributed
cooperation**, while **Intent captures locally attributable external promises**. Neither is a
substitute for the other.

Candidate external-Intent semantics include:

- a provider promise to expose or publish a contract/capability;
- a consumer promise to consume/use an external contract/capability;
- explicit offer/acceptance semantics where the distinction matters;
- required or prohibited external relationships where an accountable participant actually makes the
  assertion;
- conditions, scope, effective interval, attribution, provenance, and lifecycle.

A provider promise and a consumer promise remain separate. A consumer dependency or desire does not
create a provider obligation. Central enterprise policy may constrain a relationship but does not
manufacture an autonomous participant's promise.

Intent must never be inferred as authoritative from runtime frequency, code structure, naming,
co-location, repository structure, probabilistic interpretation, or agent-generated rationale.

Potential carriers may include OpenAPI Overlay, AsyncAPI-compatible explicit extensions/artifacts,
standalone AIP artifacts, or externally managed architecture-intent systems. The carrier must not
become the semantic model.

The Current-State invariant remains:

> **With Current-State evidence and qualification inputs held constant, adding, removing, or changing
> external Intent must not change established Current State.**

Exit capability:

> **AIP can represent an explicit external promise with its attributable participant, scope,
> conditions, effective interval, provenance, and unresolved authority/lifecycle limits without
> treating that promise as evidence that the distributed relationship currently exists.**

No internal architecture conformance engine, approval workflow, generic policy model, Current↔Intent
assessment, historical trajectory model, migration scripting, or automatic remediation is required.

## v0.10 — Local Distributed Architecture Assessment (provisional; checkpoint-dependent)

**Status:** provisional candidate scope. Execution depends on the v0.8 product-boundary checkpoint
and, if AIP-owned external Intent is retained, on a qualified v0.9 capability. The checkpoint must
show that AIP adds material value by assessing external promises against distributed cooperation
rather than leaving that function entirely to an adjacent conformance product.

**Goal:** make a local, evidence-qualified assessment of the relationship between independently
established distributed Current State and independently attributable external Intent.

**Product question:**

> **What does the available evidence support about the relationship between this external promise and
> the distributed cooperation observed here?**

A local distributed assessment is derived from an independently established local Current-State view
and an independently attributable external promise.

A promise or policy must never be used to manufacture Current State.

Assessment is explicitly local. It is bound to the participant(s), locality, observation context,
time, evidence, promise, and rule used. A local assessment does not become a universal compliance
judgment merely because AIP can project it with other local assessments.

Temporal dimensions remain independent:

- **Observation window** records when Current-State evidence was observed.
- **Effective from / effective until** records when the external promise applies.

Evidence predating a promise's effective interval does not by itself establish present fulfillment or
contradiction. Partial or incompatible coverage must remain inconclusive unless an explicit
qualification rule supports a narrower conclusion.

Exact public outcome vocabulary must be frozen only after deterministic truth tables and real-system
fixtures exist. "Not observed" must never become "contradicted" without a supported closed-world
rule.

A bounded projection may combine several local assessments to answer a larger
distributed-architecture question, but it must preserve each assessment's locality, authority,
provenance, qualification, and uncertainty.

Exit capability:

> **AIP can state what evidence supports, contradicts, or cannot establish about an applicable
> external promise in a specific distributed context, and can include that local assessment in a
> bounded question-specific projection without turning it into global truth.**

Explicitly out of scope:

- repository-internal architecture assessment;
- generic enterprise compliance;
- policy authoring or approval;
- CI blocking;
- migration planning or transformation scripting;
- automatic remediation;
- agent-generated authoritative Intent;
- historical architecture trajectories.

## v1.0 Release-Candidate Phase — Contract Freeze / Production Qualification (planned)

**Goal: Stabilize and production-qualify the architecture-intelligence contracts intended for
v1.0 without pretending that stabilization introduces a new architecture-question class.**

This phase uses `v1.0.0-rc.N` prereleases. It freezes only semantics and public contracts that have
survived implementation, deterministic evaluation, and real-system qualification across the pre-v1.0 capability releases actually implemented and accepted.

Qualification/freeze scope includes, where actually implemented and accepted:

- Canonical Model compatibility review
- Current-State evidence and qualification semantics
- locality/context semantics and Current-State projection contracts
- qualified API exposure/consumption identity, source lifecycle, configured-vs-observed usage, and
  observation coverage contracts where accepted from the v0.7 pilot
- cross-boundary projection contracts and the minimal System/Component composition semantics
  required to support them, where accepted from the v0.8 qualification
- external-Intent promise semantics, attribution, applicability, and versioned projection contracts
  only if retained and qualified after the v0.8 checkpoint
- local distributed-assessment contracts only if retained and qualified after the v0.8 checkpoint
- derivation-lineage and evidence/provenance requirements, including authority/lifecycle evidence
  references, rule versions, and exact projection binding
- temporal compatibility and coverage rules for local distributed assessment, where that provisional capability is retained
- REST and MCP contract stabilization
- graph-persistence compatibility and migration rules; the internal graph representation is not
  frozen as a public Architecture Knowledge contract
- Adapter SPI stabilization
- Configuration-format stabilization
- Migration and deprecation rules
- Security and production-operability qualification
- Performance and resilience qualification, including evidence that bounded architecture questions
  do not become unbounded in cost merely because unrelated systems/evidence share the same knowledge
  space
- Release/support policy

Any known breaking redesign required for the stable contract must be completed before the final
`v1.0.0` release.

The release-candidate phase must not freeze hypothetical contracts merely because they appeared in
earlier strategy or roadmap text. A capability that did not survive implementation and
qualification is either removed, kept explicitly experimental, or deferred beyond v1.0.

Exit condition:

> **The architecture-intelligence model and public contracts intended for v1.0 are semantically
> stable, reproducible, migration-aware, and production-qualified.**

## v1.0 — Stable Architecture Intelligence Platform (planned)

Focus: publish the first stable AIP release with mature architecture-intelligence semantics and
public contracts. Requires: a stable architecture-intelligence model; stable public REST and MCP
contracts; a stable Adapter SPI where it is intentionally public; documented compatibility and
migration rules for graph persistence and configuration; production qualification completed;
critical semantic errors = 0; release blockers = 0.

**v1.0 scope boundary:** stable v1.0 contains only contracts that were implemented and independently
qualified through the pre-v1.0 capability releases and the release-candidate phase. Externally sourced
decision-history linkage, historical architecture-state retention/import, and architecture trajectories
remain outside v1.0 under this roadmap. Moving any of those domains into the stable v1.0 scope would
require an explicit roadmap revision plus its own product-value, semantic, and executable validation;
landscape relevance or conceptual fit alone does not promote a future capability into v1.0.

The stable-product demonstration should make the bounded-change workflow tangible on a realistic
existing distributed system: establish relevant architecture context, use it to guide inspection and
planning, let the coding agent implement a bounded change, verify implementation behavior with the
normal deterministic engineering toolchain, and independently re-establish the resulting architecture
state with AIP. This is a product demonstration of the existing contracts, not a new v1.0 semantic
capability and not a claim that AIP itself verifies implementation correctness.

The v1.0 production-qualification phase should also test the **shape of scale** for the bounded
question model. Adding unrelated services, systems, and retained evidence must not force every
question to reconstruct or fingerprint the entire enterprise landscape at request time. This is a
performance/operability qualification requirement, not a new architecture-question class. v0.8
supplies only the minimal System/Component semantics that survive its own product and semantic
qualification; v1.0-rc must not broaden them into a generic enterprise model.

## Sequencing principle

The planned release sequence is:

1. **v0.3** — validation and hardening.
2. **v0.4** — trusted architecture context for agents.
3. **v0.5** — broader architecture discovery.
4. **v0.6** — locality-aware Current State.
5. **v0.7** — API-aware distributed Current State, followed by broker-mediated consumer attribution.
6. **v0.7.2** — hosted v0.7.x MCP interoperability and pre-v0.8 product-boundary qualification
   against a mature context engine.
7. **v0.8** — full Sokol111 product demonstration and only the cross-boundary composition semantics
   justified by the v0.7.2 result.
8. **Checkpoint** — decide whether the surviving AIP product boundary adds material value beyond
   strong source/repository analysis, direct execution and adjacent context-engine capabilities.
9. **v0.9** — provisional external promises, only if AIP ownership is justified.
10. **v0.10** — provisional local distributed assessment, only if justified.
11. **v1.0-rc** — freeze and qualify only the contracts that survived validation.
12. **v1.0** — stable platform.

The durable semantic frame is:

- **Current State** describes locally observed distributed cooperation.
- **Intent** captures locally attributable external promises.
- **Assessment** is a locally made evaluation of promise versus cooperation.
- A **question** produces a bounded projection over only the relevant local views.

The version order is chronological planning, while the semantic dependencies are narrower.
Qualified distributed Current State is the basis for both API-aware Current State and cross-boundary
projection. Before v0.8 freezes its composition boundary, v0.7.2 tests whether a mature context
engine can safely consume and compose the existing qualified AIP views and whether AIP materially
improves that workflow. v0.8 then proves the product boundary that survives that checkpoint against
strong source/repository analysis and direct execution. If an adjacent tool already owns the needed
capability well, AIP should integrate with it rather than duplicate it. If the resulting checkpoint
demonstrates an AIP-owned gap, external Intent may proceed provisionally, followed by local
Assessment. Only capabilities that survive those product and semantic checks should enter the stable
contract.

The product-question sequence is:

- **v0.6:** Where does this distributed relationship hold?
- **v0.7:** How are APIs exposed or consumed, and what does the evidence establish?
- **v0.8:** Which established distributed relationships cross independently established boundaries,
  and does that change what the coding agent can establish and must inspect beyond source analysis
  and direct execution?
- **v0.9, provisional:** What does this autonomous component explicitly promise to the outside?
- **v0.10, provisional:** What does the evidence support about promise versus cooperation here?
- **v1.0-rc:** Freeze only what survived product and semantic qualification.

For the bounded-change wedge, each capability should answer a concrete question:

- **Current State:** Which external relationships make me inspect outside this component?
- **Cross-boundary projection:** Which of those relationships cross the relevant autonomous
  boundaries?
- **External Intent, if retained:** What does each relevant component explicitly promise to the
  outside?
- **Local Assessment, if retained:** What does the available evidence support about those promises in
  this context?

A new source adapter is not, by itself, a new product capability. It matters when it enables a
materially new class of qualified distributed relationship or a recurring bounded question.

The stable parts of the roadmap are therefore:

1. Current State remains independent from Intent.
2. External promises do not manufacture observed/configured relationships.
3. Relationships and boundaries are established independently.
4. Assessment is downstream of independently established Current State and external Intent.
5. Bounded projections preserve locality, authority, provenance, qualification, and uncertainty.
6. Internal repository architecture remains complementary source-analysis territory.
7. Only implemented, product-validated, and independently qualified contracts are frozen for v1.0.

None of the above are committed dates. Detailed scope still belongs in release specifications.

## Product validation gates

Planned scope, authorization to execute a release, and qualification for the stable v1.0 contract are
separate decisions. Planned status does not waive product-value or technical qualification gates.

Validate representative architecture tasks with and without AIP using comparable source access,
realistic direct-execution access, and independently authored expected results. Define baselines and success/stop thresholds before the
pilot. Assess correctness together with useful answer coverage, justified abstention, false alarms,
and total engineering effort including setup, source maintenance, identity mapping, and clarification.
Reducing false claims only by returning more unresolved answers does not establish product value.

For **every capability release**, product qualification must include at least one recurring
architecture question that the capability turns into a **reusable, deterministic, evidence-qualified
answer or bounded context**. Validate that answer end to end: the consumer can resolve its evidence,
qualification, context and limitations, the conclusion can be reproduced from the same frozen
premises, and the workflow is compared with reconstruction from the same available source and
direct-execution access. Internal semantic correctness alone is necessary but not sufficient
evidence of product value.

Record a continue, narrow, defer, or stop decision when evaluating these gates. Failed gates require
a documented scope decision and, where release assignment or product boundaries change materially,
a corresponding roadmap update. Apply these gates before accepting affected capabilities into the
stable contract. Detailed pilot design belongs in release-specific specifications; see
[Product Doctrine §8](docs/product-doctrine-and-strategic-direction.md#8-product-validation).

## Future (beyond v1.0, unscheduled)

Future work must remain inside the distributed product boundary and requires its own product-value
evidence. Candidates include:

- historical retention of evidence-qualified distributed relationships sufficient for principled
  temporal comparison and trajectories;
- causal runtime-flow analysis beyond pairwise interactions, only where the evidence can support it;
- distributed/local assessor deployment options if moving qualification closer to the evidence
  locality materially improves correctness or operability;
- additional distributed protocol/configuration evidence sources, including **gRPC/protobuf** and
  **Kafka Connect configuration**, where they unlock a new bounded architecture question; these
  require explicit semantics, deterministic qualification, and their own specification rather than
  being admitted automatically through the adapter seam;
- richer external-promise and local-assessment semantics if the v0.8 product checkpoint retains AIP
  ownership of those domains.

Generic enterprise modeling, architecture wikis, broad GraphRAG, organization/capability modeling,
internal source-architecture conformance, and transformation orchestration are not default roadmap
directions. They require an explicit product-strategy revision rather than entering through the
"future" list.

See [CONTRIBUTING.md](CONTRIBUTING.md) before starting significant roadmap work.
