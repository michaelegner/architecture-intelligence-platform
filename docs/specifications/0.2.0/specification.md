# AIP v0.2.0 Specification — Deterministic Evaluation Suite

**Status:** Draft 4 — iterative delivery model integrated  
**Target release:** `v0.2.0`  
**Project:** Architecture Intelligence Platform (AIP)

## 1. Purpose

AIP `v0.1.x` introduced an evidence-backed architecture knowledge graph built from declared
architecture sources and runtime observations.

The purpose of `v0.2.0` is **not** to add a new architecture-intelligence dimension. The purpose is
to make the existing semantics reproducibly testable against independently defined ground truth.

> **AIP v0.2.0 provides a deterministic evaluation suite that verifies known architecture situations
> against explicit expected architecture facts, statuses, and evidence.**

```text
Declared input
      +
Observed input
      +
Observation context
      |
      v
     AIP
      |
      v
Canonical architecture facts
 + status + evidence
      |
      | compare
      v
Declarative ground truth
      |
      v
   PASS / FAIL
```

## 2. Release Goals

`v0.2.0` SHALL provide:

1. A small synthetic multi-service reference fixture.
2. A deterministic scenario suite covering the core `v0.1` semantics.
3. Declarative, independently authored ground-truth expectations.
4. A lightweight evaluation runner.
5. A deterministic pass/fail report showing semantic deviations.

A useful implementation target is approximately:

```text
Reference fixture:    5–6 logical services
Core scenarios:       8–10
Ground truth:         one static expected.yaml per scenario
Runner:               one small Python entry point
Report:               PASS / FAIL + deviations
```

These numbers are guidance rather than externally guaranteed limits.

## 3. Specification Structure and Delivery Iterations

This document defines the normative target state for the final AIP `v0.2.0` release.

Implementation is delivered incrementally through iteration-specific implementation specifications:

```text
I1 — Evaluation Kernel
I2 — Topology and Directionality
I3 — Evidence and Runtime Semantics
I4 — Coverage and Hardening
I5 — Release Qualification
```

Each iteration specification SHALL be self-contained for implementing that iteration.

An iteration MAY intentionally implement only a subset of the final semantics defined by this
specification, provided that:

1. the iteration specification states the deferred behavior explicitly,
2. the staged implementation does not redefine the final `v0.2.0` semantics, and
3. later iterations close the documented gap before the final release.

Unless explicitly stated otherwise, `MUST` and `SHALL` requirements in this document are requirements
for the final `v0.2.0` release. Pre-release iterations MAY stage those capabilities according to their
iteration-specific implementation specifications.

The final `v0.2.0` release MUST satisfy this specification in full.

## 4. Non-Goals

The following are explicitly outside the scope of `v0.2.0`:

- Kubernetes discovery
- gRPC/protobuf ingestion
- Kafka Connect ingestion
- additional major `ArchitectureSourceAdapter` families
- new canonical architecture entity types
- a Saga canonical model
- deployment topology as a new canonical graph dimension
- a generic architecture policy engine
- CALM ingestion
- W3C PROV representation
- GraphRAG
- vector search
- embeddings
- LangGraph agents
- LLM-as-a-Judge evaluation
- probabilistic architecture inference
- graph neural networks or link prediction
- scenario mutation/generation
- scale benchmarking
- architecture trajectories
- formal architecture-conformance proofs
- a weighted or composite "AIP intelligence score"

The evaluation runner MAY be usable from CI, but a dedicated release-gating framework is not required
for `v0.2.0`.

## 5. Design Principles

### 5.1 Deterministic First

The evaluation suite SHALL test deterministic AIP behavior.

```text
known input
   -> deterministic ingestion / observation handling
   -> deterministic architecture facts
   -> deterministic comparison
   -> deterministic result
```

Probabilistic LLM output SHALL NOT be required for a scenario to pass.

### 5.2 Independent Ground Truth

Ground truth SHALL be authored independently from AIP's derivation logic.

```text
GroundTruth != AIPDerivationImplementation
```

Expected results MUST NOT be generated from the same code paths that derive actual architecture
facts.

Acceptable:

```yaml
expected:
  relations:
    - type: CALLS
      source: service:order-service
      target: operation:service:product-service:GET:/prices
      status: CONFIRMED
```

Not acceptable as the primary oracle:

```yaml
expected_cypher:
  - MATCH (s:Service)-[:CALLS]->(o:Operation) ...
```

The suite tests architecture semantics, not whether a particular Cypher query returns a particular
row shape.

### 5.3 Canonical Model Is the Semantic Source of Truth

The Canonical Architecture Model defines the meaning of AIP architecture entities and relations.

Neo4j is a persistence and query representation of that model.

```text
Canonical semantics != Neo4j implementation details
```

The evaluation format SHALL use canonical entity identifiers, relation types, statuses, and evidence
semantics.

### 5.4 Fact, Evidence, and Status Are Distinct

The evaluation model SHALL distinguish:

```text
Fact
Evidence
Status
Observation context
```

For example, the same logical `CALLS` fact may be:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
```

depending on the available declared and observed evidence.

### 5.5 Runtime Non-Observation Is Not Architectural Absence

`NOT_OBSERVED_IN_WINDOW` means:

> Declared evidence exists, but no matching runtime evidence was found in the selected environment
> and observation window.

It MUST NOT be interpreted as proof that a dependency is unused, obsolete, unreachable, dead, invalid,
or architecturally prohibited.

```text
NOT_OBSERVED_IN_WINDOW != architectural absence
NOT_OBSERVED_IN_WINDOW != violation
```

### 5.6 No Unexpected Fact Is Silently Accepted

The suite SHALL detect both missing and unexpected architecture facts.

```text
expected facts present?
unexpected facts present?
forbidden facts present?
status correct?
evidence correct?
direction correct?
```

A false architecture dependency is considered a critical semantic error.

## 6. Canonical Semantics Covered by v0.2.0

### 6.1 Core Entity Types

At minimum:

```text
Service
Operation
Queue
Message
Schema
Evidence
```

No new canonical entity is required by this specification.

### 6.2 Core Relation Types

The evaluation suite SHOULD cover the existing relation semantics, including:

```text
(Service)-[:PROVIDES]->(Operation)
(Service)-[:CALLS]->(Operation)

(Operation)-[:REQUEST_SCHEMA]->(Schema)
(Operation)-[:RESPONSE_SCHEMA]->(Schema)

(Service)-[:SENDS]->(Queue)
(Service)-[:RECEIVES_FROM]->(Queue)

(Queue)-[:CARRIES]->(Message)
(Message)-[:CONFORMS_TO]->(Schema)

(Queue)-[:DEAD_LETTERS_TO]->(Queue)
```

## 7. Synthetic Reference Fixture

`v0.2.0` SHALL contain a synthetic reference architecture designed to exercise AIP semantics.

The fixture SHALL be synthetic by construction and MUST NOT reproduce proprietary production
topologies, identifiers, message names, traces, URLs, schemas, or customer-specific structures.

A suitable logical fixture may contain approximately 5–6 generic services, for example:

```text
ProductService
OrderService
PaymentService
InventoryService
FulfillmentService
NotificationService
```

The exact names are not normative.

The architecture SHOULD include enough structure to represent:

- synchronous REST dependencies,
- asynchronous queue-based communication,
- request/response queue pairs,
- mixed REST and async communication between the same service pair,
- a declared-only dependency,
- an observed-only dependency,
- an orphan sender or orphan consumer,
- optional DLQ semantics,
- evidence reconciliation.

The fixture exists to exercise architecture semantics, not to simulate a realistic commerce business
domain in detail.

## 8. Scenario Model

A scenario represents one controlled architecture situation.

Each scenario SHALL contain:

1. Input artifacts and/or runtime observations.
2. One `expected.yaml` file containing the declarative ground truth.
3. An explicit scenario-owned comparison scope.
4. Observation context where runtime evidence is involved.
5. A stable scenario identifier.
6. A short human-readable description.

The recommended repository structure is:

```text
evaluation/
├── README.md
├── scenarios/
│   ├── 01-rest-confirmed/
│   │   ├── input/
│   │   │   ├── declarations/
│   │   │   └── telemetry/
│   │   └── expected.yaml
│   ├── 02-rest-observed-only/
│   │   ├── input/
│   │   │   ├── declarations/
│   │   │   └── telemetry/
│   │   └── expected.yaml
│   └── ...
└── runner.py
```

A scenario MAY omit an input subdirectory that it does not need.

For example, a declaration-only scenario may omit `telemetry/`, while a runtime-only scenario may
contain no architecture declaration beyond the minimum fixture needed to resolve the observation.

The implementation MAY use a small Python package instead of a single `runner.py`, but SHALL avoid
introducing a general plugin architecture, reporter framework, metrics subsystem, or oracle engine.

## 9. Declarative Ground Truth

Ground truth SHALL be represented by exactly one `expected.yaml` file per scenario.

The format describes **concrete expected canonical facts**, not rules for deriving those facts.

### 9.1 Normative v0.2 Scenario Schema

The `v0.2.0` schema is deliberately small:

```yaml
scenario: rest-confirmed

description: >
  OrderService calls ProductService and the relation is both declared and observed.

scope:
  entities:
    - service:order-service
    - service:product-service
    - operation:service:product-service:GET:/products/{id}
  relation_types:
    - CALLS
    - PROVIDES

observation:
  environment: test
  window:
    start: "2026-08-01T10:00:00Z"
    end: "2026-08-01T11:00:00Z"

expected:
  relations:
    - type: CALLS
      source: service:order-service
      target: operation:service:product-service:GET:/products/{id}
      status: CONFIRMED
      evidence:
        declared: true
        observed: true

forbidden:
  relations: []
```

The top-level fields have the following meaning:

| Field | Required | Meaning |
| --- | --- | --- |
| `scenario` | yes | Stable scenario identifier. |
| `description` | yes | Human-readable purpose of the scenario. |
| `scope` | yes | Canonical entities and optional relation types owned by the scenario. |
| `observation` | runtime scenarios | Environment and, where required, observation window. |
| `expected.relations` | yes | Canonical relation facts that MUST exist. |
| `forbidden.relations` | yes | Canonical relation facts that MUST NOT exist. |

`forbidden.relations` MAY be an empty list.

### 9.2 Scenario-Owned Scope

The evaluation SHALL compare only the scenario-owned subgraph rather than the complete AIP graph.

`scope.entities` lists canonical entity identifiers owned by the scenario.

`scope.relation_types` MAY restrict the comparison to specific canonical relation types. If omitted,
all canonical relation types touching the scoped entities are considered.

A relation is considered in scope when:

```text
(source is in scope.entities OR target is in scope.entities)
AND
(relation type is allowed by scope.relation_types, if specified)
```

All source and target identifiers explicitly referenced by `expected` or `forbidden` SHOULD also be
listed under `scope.entities`.

Within the scenario-owned scope:

```text
all expected facts must exist
all forbidden facts must not exist
all other semantically relevant facts are unexpected
```

This prevents unrelated fixture or infrastructure facts from making scenarios brittle while still
detecting unexpected dependencies involving the scenario's entities.

### 9.3 Positive Expectations

`expected.relations` means that the matching canonical architecture fact MUST exist.

Each expected relation MAY specify:

- relation type,
- source entity,
- target entity,
- status,
- declared evidence presence,
- observed evidence presence.

Where a field is specified, it is part of the assertion.

### 9.4 Forbidden Expectations

`forbidden.relations` means that the matching canonical architecture fact MUST NOT exist.

This is used for explicit negative assertions, especially where relation direction matters.

Example:

```yaml
forbidden:
  relations:
    - type: RECEIVES_FROM
      source: service:order-service
      target: queue:order-product-request-q
```

### 9.5 Evidence Expectations

For `v0.2.0`, evidence expectations are intentionally limited to presence or absence by evidence
class:

```yaml
evidence:
  declared: true
  observed: true
```

The ground-truth format does not need to reproduce the complete persisted `Evidence` object.

Where a scenario specifically tests evidence reconciliation, it MAY additionally assert stable
evidence identifiers or counts if existing AIP APIs already expose them deterministically.

### 9.6 No Declarative Rules Engine

The ground-truth format SHALL NOT reproduce AIP's derivation logic.

This is explicitly out of scope:

```yaml
rules:
  - when:
      evidence.declared: false
      evidence.observed: true
    then:
      status: OBSERVED_ONLY
```

The expected status SHALL instead be written explicitly in each scenario.

The `v0.2.0` format SHALL NOT add:

- rule expressions,
- inheritance,
- variables,
- templates,
- macros,
- conditional assertions,
- a generic assertion DSL.

## 10. Observation Context and Runtime Fixtures

Scenarios that evaluate runtime semantics SHALL define an observation context.

At minimum:

```yaml
observation:
  environment: test
```

Where time-window semantics matter:

```yaml
observation:
  environment: test
  window:
    start: "2026-08-01T10:00:00Z"
    end: "2026-08-01T11:00:00Z"
```

Runtime scenarios SHOULD use small, static, synthetic OTLP fixtures and exercise the real AIP OTLP
ingestion path:

```text
static synthetic OTLP fixture
        |
        v
existing OTLP ingestion
        |
        v
observation resolution / aggregation
        |
        v
canonical architecture facts
```

A continuously running traffic generator is not required for the evaluation suite.

Lower-level pre-normalized runtime observations MAY be used only when:

1. exercising OTLP ingestion adds no semantic value to the scenario, or
2. using OTLP would introduce disproportionate fixture or harness complexity.

Such exceptions SHOULD be documented in the scenario description.

The purpose is to make runtime expectations reproducible, not to introduce a generic runtime-model
platform.

## 11. Evaluation Runner

The release SHALL provide one simple command for running the suite.

Target interface:

```bash
uv run python -m evaluation run
```

Equivalent packaging is acceptable.

The runner SHALL perform the following logical steps for each scenario:

```text
load scenario
     |
reset isolated evaluation state
     |
ingest declared architecture
     |
inject static runtime fixture, if present
     |
allow AIP to derive/reconcile architecture facts
     |
read actual canonical facts
     |
project them into stable comparison records
     |
filter to scenario-owned scope
     |
compare with declarative ground truth
     |
produce report
```

### 11.1 Isolation Strategy

Each scenario SHALL start from deterministic clean evaluation state.

Preferred implementation:

```text
scenario start
    |
clear dedicated evaluation database/state
    |
load scenario
    |
evaluate
```

The suite SHOULD reuse existing AIP test infrastructure where it already provides reliable clean
database fixtures.

The evaluation implementation SHALL NOT introduce tenant IDs, graph namespaces, or complex
transactional sandboxing solely to isolate scenarios.

### 11.2 Canonical Fact Access

The runner SHOULD read actual facts through the narrowest existing AIP application or canonical query
boundary that exposes the required semantics.

Preferred order:

```text
existing canonical/application query boundary
        |
        v
small read-only evaluation projection, if required
        |
        v
direct Neo4j extraction only as an implementation fallback
```

The semantic contract of the evaluation suite SHALL NOT be Cypher.

A direct Neo4j extractor, if unavoidable, MUST immediately project persisted graph data into canonical
comparison records and MUST NOT embed derivation rules that duplicate AIP behavior.

### 11.3 No Alternative Reasoning Engine

The evaluation runner SHALL NOT implement an alternative architecture reasoning engine.

Its responsibilities are limited to:

- scenario setup,
- invoking existing AIP behavior,
- reading canonical results,
- normalization,
- scope filtering,
- comparison,
- reporting.

## 12. Actual-Fact Projection

The runner MAY contain a small deterministic, read-only projection from AIP's application or
persistence representation into a stable comparison representation.

Example:

```text
RelationFact(
    type = "CALLS",
    source = "service:order-service",
    target = "operation:service:product-service:GET:/products/{id}",
    status = "CONFIRMED",
    declared_evidence = true,
    observed_evidence = true
)
```

The projection exists only to normalize actual AIP output into the same semantic vocabulary used by
`expected.yaml`.

It is not a second domain model.

It MUST NOT:

- infer missing relationships,
- derive statuses,
- reinterpret evidence,
- repair identifiers,
- execute policy rules,
- reproduce the logic under test.

Canonical identifier normalization MAY be reused from existing AIP code where that code is already
part of the production semantics.

## 13. Comparison Semantics

Comparison SHALL be performed only within the scenario-owned scope defined in `expected.yaml`.

The runner SHALL detect at least the following failure classes.

### 13.1 Missing Facts

An expected relation does not exist.

Result: `FAIL`.

### 13.2 Unexpected Facts

An in-scope canonical relation exists but is neither expected nor explicitly accepted by the
scenario.

Example:

```text
Scoped entity:
OrderService

Expected:
OrderService -> ProductService only

Actual:
OrderService -> ProductService
OrderService -> InventoryService

Result:
unexpected architecture fact -> FAIL
```

This is intentionally stricter than checking only for the presence of expected facts.

### 13.3 Forbidden Facts

A relation listed under `forbidden.relations` exists.

Result: `FAIL`.

### 13.4 Incorrect Direction

The intended relation exists only in the opposite direction.

Example:

```text
Expected:
OrderService SENDS request-q

Actual:
OrderService RECEIVES_FROM request-q
```

Result: `FAIL`.

### 13.5 Incorrect Status

The fact exists but has the wrong declared/observed classification.

Example:

```text
Expected: OBSERVED_ONLY
Actual:   CONFIRMED
```

Result: `FAIL`.

### 13.6 Evidence Violation

The fact exists with the expected identity and status but does not satisfy the declared/observed
evidence expectation.

Example:

```text
Expected:
declared = true
observed = true

Actual:
declared = true
observed = false
```

Result: `FAIL`.

### 13.7 Exact Matching Rule

For the fields explicitly declared in `expected.yaml`, comparison is exact.

The evaluation suite SHALL NOT use fuzzy matching, LLM interpretation, similarity thresholds, or
probabilistic matching to decide whether an actual fact satisfies an expected fact.

## 14. Initial Scenario Suite

The required `v0.2.0` suite SHOULD contain 8–10 core scenarios.

The following ten scenarios define the target core suite.

### Scenario 1 — Declared REST Relation

Verify that a declared REST provider/caller relationship is represented correctly.

Primary semantics:

```text
PROVIDES
CALLS
```

### Scenario 2 — REST Confirmed

A declared REST dependency is also observed at runtime.

Expected:

```text
status = CONFIRMED
declared evidence = true
observed evidence = true
```

### Scenario 3 — REST Observed Only

A runtime REST dependency exists without corresponding declared architecture evidence.

Expected:

```text
status = OBSERVED_ONLY
declared evidence = false
observed evidence = true
```

### Scenario 4 — Declared but Not Observed in Window

A declared dependency has no matching observation in the scenario's environment/window.

Expected:

```text
status = NOT_OBSERVED_IN_WINDOW
```

The scenario SHALL demonstrate that this is not treated as proof of architectural absence or a policy
violation.

### Scenario 5 — Async Sender and Consumer Confirmed

Verify:

```text
Producer -[:SENDS]-> Queue
Consumer -[:RECEIVES_FROM]-> Queue
```

Both directions must be correct.

### Scenario 6 — Orphan Messaging Relationship

Exercise at least one of:

```text
sender without known consumer
consumer without known sender
```

The purpose is to verify the existing deterministic queue semantics and analyses.

### Scenario 7 — Mixed REST and Async Between the Same Services

A service pair uses both:

```text
CALLS
```

and:

```text
SENDS / RECEIVES_FROM
```

The scenario SHALL prove that AIP preserves both interaction modes without collapsing them into one
generic service dependency.

### Scenario 8 — Request/Response Queue Pair

Verify:

```text
OrderService    SENDS          request-q
ProductService  RECEIVES_FROM  request-q

ProductService  SENDS          response-q
OrderService    RECEIVES_FROM  response-q
```

The inverse relationships SHALL be explicitly forbidden.

### Scenario 9 — Evidence Reconciliation

A declared architecture relationship is removed while runtime evidence remains.

The resulting fact SHALL survive if supporting observed evidence still exists.

```text
Delete(Fact) iff Evidence(Fact) is empty
```

The expected post-reconciliation status SHALL reflect the surviving evidence.

### Scenario 10 — Partial Observation

Exercise a situation in which declared behavior is not fully observed because the runtime observation
context is deliberately limited.

The scenario SHALL confirm that AIP does not overstate the meaning of missing observations.

### Candidate Extension — DLQ Directionality

Include a DLQ scenario in `v0.2.0` if it remains a small static fixture and does not delay the core
suite.

Verify:

```text
Queue -[:DEAD_LETTERS_TO]-> Queue
```

The direction MUST be preserved.

### Candidate Extension — Cross-Batch HTTP Correlation

Cross-batch HTTP correlation is optional for `v0.2.0`.

It SHOULD be added only after the core suite is stable and only if it requires little
evaluation-specific harness logic.

The release SHALL NOT be delayed merely to maximize scenario count.

## 15. Reporting

The report SHOULD be intentionally simple.

Target output:

```text
AIP Evaluation

Scenarios:               10
Passed:                  10
Failed:                   0

Expected facts:          27
Missing facts:            0
Unexpected facts:         0
Forbidden facts present:  0
Wrong directions:         0
Wrong statuses:           0
Evidence violations:      0

RESULT: PASS
```

The runner MAY additionally emit a machine-readable JSON report.

`v0.2.0` SHALL NOT require:

- F1 score,
- precision/recall dashboards,
- weighted scoring,
- trend storage,
- benchmark history.

## 16. Exit Codes

The evaluation command SHOULD return:

```text
0  all required scenarios passed
1  one or more evaluation failures
```

This makes the runner CI-compatible without requiring a dedicated CI-gating subsystem.

## 17. Acceptance Criteria

`v0.2.0` is ready when:

1. The synthetic reference fixture is committed and documented.
2. At least 8 core deterministic scenarios are implemented; 10 is the target.
3. Every scenario has exactly one declarative `expected.yaml`.
4. Ground truth is authored independently of AIP derivation logic.
5. Every scenario declares a scenario-owned comparison scope.
6. Scenarios compare canonical architecture semantics rather than raw Cypher output.
7. Positive and negative expectations are supported.
8. Unexpected in-scope architecture facts are reported as failures.
9. Relation direction is checked.
10. Status semantics are checked.
11. Evidence presence is checked where relevant.
12. Runtime observation context is explicit where required.
13. Runtime scenarios use small static synthetic OTLP fixtures through the real ingestion path unless
    the scenario documents a justified exception.
14. Each scenario starts from deterministic clean evaluation state.
15. `NOT_OBSERVED_IN_WINDOW` is not interpreted as architectural absence.
16. The suite produces deterministic pass/fail output.
17. The full required suite passes.
18. There are zero known critical semantic errors in the reference scenarios.
19. The runner works without requiring an LLM API key.
20. CI integration may invoke the runner, but a dedicated release-gating subsystem is not required.

## 18. Critical Semantic Errors

Release-blocking errors include:

- invented architecture dependency,
- missing expected architecture dependency,
- reversed relation direction,
- wrong provider resolution,
- wrong queue sender/receiver resolution,
- incorrect `CONFIRMED` classification,
- incorrect `OBSERVED_ONLY` classification,
- incorrect `NOT_OBSERVED_IN_WINDOW` classification,
- loss of surviving evidence during reconciliation,
- deletion of a fact while evidence remains,
- interpretation of non-observation as proof of architectural absence.

Target:

```text
Critical semantic errors = 0
```

## 19. Relationship to Architecture Conformance

The Evaluation Suite can be viewed as a controlled architecture-conformance experiment.

```text
CONFIRMED
  declared and observed evidence agree

OBSERVED_ONLY
  runtime behavior exists without corresponding declaration

NOT_OBSERVED_IN_WINDOW
  declaration exists but no confirming runtime evidence was found
  in the selected observation context
```

The third case MUST remain context-qualified and MUST NOT be simplified to "absence".

## 20. Delivery Plan

The final release is implemented through five vertical iterations.

### I1 — Evaluation Kernel → `v0.2.0-alpha.1`

Deliver the smallest complete end-to-end evaluation capability:

- scenario discovery and loading,
- one `expected.yaml` per scenario,
- deterministic scenario isolation,
- canonical fact projection,
- REST `CONFIRMED`,
- REST `OBSERVED_ONLY`,
- async `CONFIRMED`,
- deterministic PASS/FAIL reporting,
- CI-compatible exit codes.

I1 proves that the evaluation architecture works end-to-end.

### I2 — Topology and Directionality → `v0.2.0-alpha.2`

Extend the evaluation kernel with topology-sensitive semantics:

- orphan messaging,
- mixed REST + async relationships,
- request/response queue pairs,
- `forbidden` fact evaluation,
- unexpected in-scope fact detection,
- strict relation-direction checks.

I2 proves that AIP preserves interaction type and direction rather than collapsing dependencies into
generic service-to-service edges.

### I3 — Evidence and Runtime Semantics → `v0.2.0-alpha.3`

Add the more subtle evidence and observation semantics:

- `NOT_OBSERVED_IN_WINDOW`,
- evidence reconciliation,
- evidence-preservation assertions,
- status transitions caused by surviving evidence.

I3 completes the semantic core required for the final release.

### I4 — Coverage and Hardening → `v0.2.0-rc.1`

Add representative edge cases and harden the evaluator:

- partial-observation scenario,
- DLQ directionality if inexpensive,
- cross-batch HTTP correlation only if it remains low-cost,
- deterministic error reporting,
- schema-validation hardening,
- stable output ordering,
- local reproducibility.

The release SHALL NOT be delayed merely to maximize scenario count.

### I5 — Release Qualification → `v0.2.0`

No new architecture semantics are introduced in I5.

Activities are limited to:

- clean-checkout verification,
- documentation,
- release notes,
- ROADMAP/CHANGELOG updates,
- final regression fixes,
- confirmation of zero known critical semantic errors.

The final `v0.2.0` release MUST satisfy all normative requirements in this specification.



## 21. Suggested Public Roadmap Text

```markdown
## v0.2 — planned

Focus: make the architecture intelligence introduced in v0.1 reproducibly testable against known
ground truth.

- Synthetic multi-service reference fixture covering REST, asynchronous messaging, and mixed
  sync/async dependencies
- A small deterministic scenario suite with explicit expected architecture facts
- A lightweight evaluation runner comparing AIP output with those expectations
- Simple pass/fail reporting for missing facts, unexpected facts, incorrect statuses, relation
  direction, and evidence violations

The goal of v0.2 is not to add another architecture-intelligence dimension, but to provide a
reproducible way to demonstrate that the existing one behaves correctly.
```

## 22. Resolved Implementation Decisions

The implementation questions raised in Draft 2 §21 are resolved for this specification as follows:

| Topic | v0.2.0 decision |
| --- | --- |
| Ground-truth format | Exactly one `expected.yaml` per scenario. |
| Assertion language | Concrete expected/forbidden facts only; no rules DSL. |
| Comparison scope | Scenario-owned subgraph defined in `expected.yaml`. |
| Unexpected facts | Unexpected in-scope relations are failures. |
| Actual-fact access | Prefer existing canonical/application boundary; use a thin read-only projection if required. |
| Cypher coupling | Cypher MUST NOT be the evaluation semantic contract. |
| Isolation | Deterministic reset/cleanup before each scenario. |
| Runtime input | Small static synthetic OTLP fixtures through the existing ingestion path by default. |
| Scenario count | 8 required minimum; 10 core scenarios targeted. |
| DLQ | Add if it remains inexpensive and does not delay the core suite. |
| Cross-batch HTTP correlation | Optional for `v0.2.0`. |
| CI | Runner is CI-compatible; dedicated release-gating infrastructure is not required. |

These decisions are normative for `v0.2.0` unless implementation work exposes a concrete technical
constraint that requires a specification amendment.


## 23. Summary

`v0.2.0` is intentionally narrow.

It does not broaden AIP into a policy engine, agent platform, GraphRAG system, or deployment-analysis
platform.

Instead it establishes one capability:

> **Given a known declared/observed architecture situation, AIP can be evaluated deterministically
> against independently defined canonical ground truth.**

```text
v0.1 = architecture intelligence exists

v0.2 = architecture intelligence is reproducibly verifiable
```
