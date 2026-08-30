# AIP v0.2.0 — Iteration 1 Implementation Specification

**Status:** Draft 2 — self-contained implementation contract  
**Release target:** `v0.2.0-alpha.1`  
**Iteration:** I1 — Evaluation Kernel  
**Project:** Architecture Intelligence Platform (AIP)

---

## 1. Purpose

Iteration 1 establishes the smallest complete end-to-end evaluation capability for AIP.

The goal is to prove that AIP can be executed against controlled declared and observed architecture
inputs and that its resulting canonical architecture facts can be compared deterministically with
independently authored ground truth.

Iteration 1 is intentionally narrow. It does not attempt to implement the complete `v0.2.0`
evaluation suite.

The iteration is successful when this pipeline works reproducibly:

```text
scenario fixture
      |
      v
     AIP
      |
      v
canonical architecture facts
      |
      v
scenario-owned comparison scope
      |
      v
expected.yaml
      |
      v
deterministic comparison
      |
      v
PASS / FAIL
```

The target release for this iteration is:

```text
v0.2.0-alpha.1
```

---

### 1.1 Specification Relationship

This document is self-contained for implementing Iteration 1.

The release-level `v0.2.0` specification defines the complete final release target and later
iterations, but it is not required to implement I1.

Where I1 deliberately implements only a subset of the final `v0.2.0` evaluation semantics, that
limitation is stated explicitly in this document.

For implementation purposes:

```text
I1 specification
    = implementation contract for v0.2.0-alpha.1

v0.2.0 specification
    = final release contract and broader delivery context
```

Existing AIP source code and technical documentation remain authoritative for the behavior of current
OpenAPI, AsyncAPI, Architecture Manifest, OTLP, canonical-ID, evidence, and persistence components
that this specification reuses.


## 2. Iteration Goal

Iteration 1 SHALL deliver:

1. the evaluation directory structure,
2. a minimal declarative `expected.yaml` format,
3. deterministic scenario isolation,
4. a small evaluation runner,
5. three end-to-end scenarios,
6. canonical fact projection for comparison,
7. deterministic PASS/FAIL reporting,
8. a non-zero exit code on evaluation failure.

The three required scenarios are:

```text
1. REST CONFIRMED
2. REST OBSERVED_ONLY
3. ASYNC CONFIRMED
```

Together they exercise:

- declared architecture input,
- runtime observation input,
- REST dependencies,
- queue-based dependencies,
- evidence classification,
- status classification,
- canonical identifiers,
- deterministic comparison.

---

## 3. Non-Goals

Iteration 1 SHALL NOT implement:

- the complete 8–10 scenario `v0.2.0` suite,
- `NOT_OBSERVED_IN_WINDOW`,
- evidence reconciliation,
- partial-observation semantics,
- request/response queue directionality tests,
- orphan queue scenarios,
- DLQ scenarios,
- cross-batch HTTP correlation scenarios,
- evaluation of non-empty `forbidden` assertions,
- release-blocking exhaustive unexpected-fact analysis,
- a generic policy language,
- a generic rule engine,
- a metrics framework,
- precision/recall/F1 scoring,
- historical regression storage,
- a dedicated CI release gate,
- a plugin system,
- multiple report backends,
- an LLM-based evaluator,
- GraphRAG,
- new canonical architecture entity or relation types.

I1 SHALL use the final scenario-file shape where practical, but it SHALL NOT implement behavior
explicitly deferred to later iterations.

---

## 4. Design Principles

### 4.1 Vertical Slice First

Iteration 1 SHALL prioritize a complete working vertical slice over framework completeness.

The implementation order is:

```text
scenario
   -> input
   -> AIP ingestion
   -> AIP runtime observation handling
   -> persisted/canonical facts
   -> projection
   -> comparison
   -> report
```

A partially implemented generic evaluation framework is not an acceptable outcome.

---

### 4.2 Ground Truth Is Independent

Ground truth SHALL be manually authored and SHALL NOT be generated from AIP's derivation code.

```text
GroundTruth != AIPDerivationImplementation
```

The evaluator MUST NOT use AIP status derivation logic to compute the expected result.

---

### 4.3 Canonical Semantics, Not Cypher Semantics

The evaluator compares canonical architecture facts.

The semantic contract MUST NOT be:

```text
Cypher query + expected row set
```

It SHALL instead be:

```text
canonical relation type
canonical source identifier
canonical target identifier
status
evidence classification
```

Neo4j MAY be used internally to retrieve data, but Cypher MUST remain an implementation detail.

---

### 4.4 Deterministic Only

The complete I1 suite SHALL run without an LLM API key.

No scenario result may depend on probabilistic model output.

---

### 4.5 Canonical Semantics Used by I1

I1 uses only the canonical relation semantics required by its three scenarios:

```text
(Service)-[:PROVIDES]->(Operation)
(Service)-[:CALLS]->(Operation)
(Service)-[:SENDS]->(Queue)
(Service)-[:RECEIVES_FROM]->(Queue)
```

Their meanings for I1 are:

- `PROVIDES`: a service exposes a specific operation.
- `CALLS`: a service has a synchronous dependency on a specific operation.
- `SENDS`: a service produces/sends messages to a queue.
- `RECEIVES_FROM`: a service consumes/receives messages from a queue.

`PROVIDES` does not imply `CALLS`. A caller relationship must remain evidence-backed.

The evaluator SHALL compare these canonical meanings and SHALL NOT replace them with generic
service-to-service dependency semantics.

### 4.6 Status Semantics Used by I1

I1 evaluates two statuses:

```text
CONFIRMED
  declared evidence is present
  observed evidence is present

OBSERVED_ONLY
  declared evidence is absent
  observed evidence is present
```

These definitions state the expected AIP semantics.

The evaluator MUST NOT derive the actual status from the evidence booleans. It SHALL read the status
produced by AIP and compare it with the independently declared expected status.

For example, the evaluator MUST NOT contain logic equivalent to:

```python
if declared and observed:
    actual_status = "CONFIRMED"
```

because that would duplicate the behavior under test.


## 5. Repository Structure

Iteration 1 SHOULD introduce the following structure:

```text
evaluation/
├── README.md
├── __init__.py
├── __main__.py
├── model.py
├── loader.py
├── projector.py
├── comparator.py
├── reporter.py
├── runner.py
└── scenarios/
    ├── 01-rest-confirmed/
    │   ├── input/
    │   │   ├── declarations/
    │   │   └── telemetry/
    │   └── expected.yaml
    ├── 02-rest-observed-only/
    │   ├── input/
    │   │   ├── declarations/
    │   │   └── telemetry/
    │   └── expected.yaml
    └── 03-async-confirmed/
        ├── input/
        │   ├── declarations/
        │   └── telemetry/
        └── expected.yaml
```

This structure is a recommendation, not a requirement to create unnecessary abstractions.

If the implementation remains clearer with fewer modules, the following is also acceptable:

```text
evaluation/
├── README.md
├── runner.py
├── model.py
└── scenarios/
```

The implementation SHOULD prefer clarity over module count.

---

## 6. Evaluation Data Model

Iteration 1 requires only a small comparison model.

### 6.1 `RelationFact`

Recommended representation:

```python
@dataclass(frozen=True, order=True)
class RelationFact:
    type: str
    source: str
    target: str
    status: str | None
    declared_evidence: bool | None
    observed_evidence: bool | None
```

The exact Python type may differ, but the semantic fields SHALL remain equivalent.

### 6.2 `Scenario`

A loaded scenario SHOULD contain:

```python
@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    scope: ...
    observation: ...
    expected_relations: tuple[RelationFact, ...]
    path: Path
```

Iteration 1 does not require a large domain hierarchy.

---

## 7. Declarative Scenario Format

Each scenario SHALL contain exactly one `expected.yaml`.

The minimum I1 format is:

```yaml
scenario: rest-confirmed

description: >
  OrderService calls ProductService and the dependency is both
  declared and observed.

scope:
  entities:
    - service:order-service
    - service:product-service
    - operation:service:product-service:GET:/products/{id}

  relation_types:
    - CALLS

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

### 7.1 Required Fields

For I1:

```text
scenario
description
scope.entities
expected.relations
forbidden.relations
```

Runtime scenarios SHALL also provide:

```text
observation.environment
```

A window SHALL be provided when the existing runtime-analysis API requires it or when deterministic
status calculation depends on it.


### 7.2 `forbidden` Field in I1

I1 SHALL use the final scenario-file shape:

```yaml
forbidden:
  relations: []
```

For `v0.2.0-alpha.1`, `forbidden.relations` MUST be present and MUST be empty.

Evaluation of non-empty forbidden assertions is deliberately deferred to I2. A non-empty
`forbidden.relations` in an I1 scenario SHALL therefore be rejected as unsupported configuration
rather than silently ignored.

This avoids a scenario-format migration between I1 and I2 while keeping I1's comparison semantics
small.

### 7.3 Validation

Invalid scenario configuration SHALL fail before AIP execution.

Examples:

```text
missing scenario id
missing expected.relations
unknown relation type
duplicate expected fact
malformed canonical identifier
missing runtime environment for runtime scenario
non-empty forbidden.relations in I1
```

The loader SHOULD produce a clear error that identifies:

```text
scenario
file
field
reason
```

A general-purpose schema engine is not required for I1.

Pydantic, dataclasses plus explicit validation, or another existing project-standard mechanism is
acceptable.

---

## 8. Scenario-Owned Scope

Each scenario SHALL define the entities it owns.

For I1, a relation is in comparison scope when:

```text
(source in scope.entities OR target in scope.entities)
AND
(relation type in scope.relation_types, when relation_types is present)
```

The evaluator SHOULD ignore unrelated facts outside this scope.

This allows scenarios to share infrastructure without becoming brittle.

Example:

```yaml
scope:
  entities:
    - service:order-service
    - service:product-service
    - operation:service:product-service:GET:/products/{id}

  relation_types:
    - CALLS
```

The comparison then evaluates `CALLS` facts involving these canonical entities.

---

## 9. Scenario 1 — REST CONFIRMED

### 9.1 Purpose

Verify that a REST dependency with both declared and observed evidence becomes:

```text
CONFIRMED
```

### 9.2 Architecture

```text
OrderService
     |
     | CALLS
     v
ProductService.GET /products/{id}
```

The provider operation SHALL be declared.

The caller relation SHALL be declared through an existing evidence-backed source supported by AIP.

Runtime telemetry SHALL independently show the matching call.

### 9.3 Required Input

Declared input SHOULD reuse existing AIP source formats where possible:

```text
ProductService OpenAPI
OrderService Architecture Manifest or existing CALLS declaration source
```

Runtime input SHALL use a small static synthetic OTLP fixture representing the same HTTP interaction.

### 9.4 Expected Result

```yaml
expected:
  relations:
    - type: CALLS
      source: service:order-service
      target: operation:service:product-service:GET:/products/{id}
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
```

### 9.5 Acceptance

The scenario passes only if:

```text
CALLS identity is correct
source is correct
target operation is correct
status == CONFIRMED
declared evidence exists
observed evidence exists
```

---

## 10. Scenario 2 — REST OBSERVED_ONLY

### 10.1 Purpose

Verify that a runtime REST dependency without corresponding declared caller evidence becomes:

```text
OBSERVED_ONLY
```

### 10.2 Architecture

```text
OrderService
     |
     | runtime-only CALLS
     v
ProductService.GET /prices
```

ProductService MAY still declare/provide the operation.

The key condition is:

```text
no declared CALLS evidence
+
matching observed runtime interaction
```

### 10.3 Runtime Fixture

The telemetry fixture SHALL contain enough information for the existing AIP resolver to identify:

```text
caller service
provider service
HTTP method
HTTP route/template
environment
```

The fixture MUST use low-cardinality route/template semantics consistent with existing AIP runtime
ingestion.

### 10.4 Expected Result

```yaml
expected:
  relations:
    - type: CALLS
      source: service:order-service
      target: operation:service:product-service:GET:/prices
      status: OBSERVED_ONLY
      evidence:
        declared: false
        observed: true
```

### 10.5 Acceptance

The scenario passes only if:

```text
CALLS fact exists
status == OBSERVED_ONLY
declared evidence is absent
observed evidence exists
```

A synthetic declared `CALLS` MUST NOT be inferred merely because ProductService `PROVIDES` the
operation.

---

## 11. Scenario 3 — ASYNC CONFIRMED

### 11.1 Purpose

Verify the core asynchronous sender/receiver semantics with both declared and observed evidence.

### 11.2 Architecture

```text
OrderService
     |
     | SENDS
     v
order-events-q
     ^
     | RECEIVES_FROM
     |
InventoryService
```

### 11.3 Declared Input

The existing AsyncAPI or other current supported architecture source SHALL declare the messaging
topology.

The scenario SHOULD use existing supported ingestion behavior rather than introducing a new fixture
adapter.

### 11.4 Runtime Input

Static synthetic OTel messaging spans SHALL represent:

```text
OrderService producer/send
InventoryService consumer/process or receive
queue = order-events-q
environment = test
```

The fixture SHOULD use the semantic-convention fields already consumed by AIP.

### 11.5 Expected Result

At minimum:

```yaml
expected:
  relations:
    - type: SENDS
      source: service:order-service
      target: queue:order-events-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true

    - type: RECEIVES_FROM
      source: service:inventory-service
      target: queue:order-events-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
```

### 11.6 Acceptance

Both relations SHALL exist with correct direction, status, and evidence.

I1 does not yet require explicit negative assertions for the inverse direction. That becomes a primary
focus of Iteration 2.

---

## 12. Runtime Fixture Strategy

Iteration 1 SHALL prefer static OTLP fixtures over a continuously running traffic generator.

Recommended flow:

```text
fixture file
    |
    v
load fixture
    |
    v
POST / existing OTLP ingestion path
    |
    v
existing runtime resolver
    |
    v
existing aggregation/reconciliation
```

The fixture representation SHOULD be as close as practical to actual OTLP HTTP input.

Acceptable options include:

```text
JSON OTLP payload
protobuf payload if existing tests already use it
existing internal test builder that emits real OTLP structures
```

The evaluator SHALL NOT bypass the runtime resolver merely to simplify expected results unless the
existing test infrastructure makes real OTLP ingestion disproportionately complex.

---

## 13. Evaluation-State Isolation

Each scenario SHALL start from clean evaluation state.

Preferred sequence:

```text
reset state
   |
load declared input
   |
load runtime input
   |
evaluate
```

The implementation SHOULD reuse an existing test/reset mechanism if available.

Acceptable I1 strategies include:

```text
dedicated evaluation Neo4j database
fresh Neo4j test container
deterministic delete/reset of evaluation graph
```

The implementation SHALL NOT introduce:

```text
multi-tenant graph namespaces
scenario IDs on production entities
complex transactional sandboxes
```

solely for evaluation isolation.

---

## 14. Canonical Fact Access

The evaluator SHOULD obtain actual facts through the narrowest existing AIP boundary that preserves
canonical semantics.

Preferred order:

```text
1. existing application/canonical query service
2. existing REST API returning sufficient canonical semantics
3. small read-only evaluation projection
4. direct Neo4j query only as fallback
```

If direct Neo4j access is required, the implementation SHALL contain it behind one narrow function or
adapter such as:

```python
def load_relation_facts(scope: ScenarioScope) -> set[RelationFact]:
    ...
```

Cypher SHALL NOT leak into scenario definitions.

---

## 15. Projection Rules

Projection SHALL be mechanical.

It MAY:

```text
map persisted relation -> RelationFact
map canonical IDs into stable strings
map evidence collection -> declared/observed booleans
map stored status -> status string
sort result deterministically
```

It SHALL NOT:

```text
derive CONFIRMED from evidence
derive OBSERVED_ONLY from evidence
infer missing CALLS
repair relation direction
invent canonical IDs
perform fuzzy entity resolution
```

Those behaviors belong to AIP and are exactly what the evaluator must test.

---

## 16. Comparison Algorithm

For each scenario:

```text
expected = set(expected RelationFacts)
actual   = set(projected in-scope RelationFacts)
```

I1 SHALL evaluate:

```text
missing expected fact
wrong canonical source/target/type
wrong status
wrong declared-evidence expectation
wrong observed-evidence expectation
```

### 16.1 Required I1 Comparison

The required I1 comparison is expectation-driven.

Every expected fact SHALL have an exact matching actual fact.

A mismatch in status or evidence SHALL be reported as a semantic mismatch rather than merely as one
missing and one unrelated fact.

### 16.2 Behavior Explicitly Deferred to I2

I1 does **not** require the following final-release comparison capabilities:

```text
non-empty forbidden assertions
exhaustive unexpected in-scope fact failures
explicit inverse-direction negative assertions
```

Those capabilities are introduced in I2.

The I1 implementation MAY calculate unexpected facts for diagnostics, but their presence SHALL NOT be
a release-blocking `alpha.1` failure unless they directly conflict with an expected fact.

The report MUST make this staging explicit and MUST NOT imply that the final `v0.2.0` unexpected-fact
semantics are already complete.

### 16.3 Matching

Matching SHALL be exact for all declared expectation fields.

No fuzzy matching is allowed.

```text
type
source
target
status
declared evidence
observed evidence
```

must match the expected values.



## 17. Reporting

The default I1 report SHALL be human-readable and deterministic.

Target output:

```text
AIP Evaluation — I1

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed

Scenarios:          3
Passed:             3
Failed:             0

Missing facts:      0
Unexpected facts:   not enforced in I1
Wrong statuses:     0
Evidence errors:    0

RESULT: PASS
```

Failure example:

```text
[FAIL] 02-rest-observed-only

Expected:
  CALLS
  service:order-service
    -> operation:service:product-service:GET:/prices
  status: OBSERVED_ONLY
  evidence: declared=false observed=true

Actual:
  status: CONFIRMED
  evidence: declared=true observed=true

Reason:
  wrong status
  unexpected declared evidence
```

The report SHOULD sort:

```text
scenarios by scenario id
facts by type/source/target
errors by stable category
```

to ensure reproducible output.

In I1, unexpected-fact information MAY be shown diagnostically but is not part of the `alpha.1`
release gate. Full unexpected/forbidden semantics begin in I2.

---

## 18. Exit Codes

The command:

```bash
uv run python -m evaluation run
```

SHALL return:

```text
0  all I1 scenarios pass
1  one or more semantic evaluation failures
```

It is RECOMMENDED to use a separate value for invalid test configuration or internal evaluator errors,
for example:

```text
2  invalid scenario or evaluation infrastructure error
```

The exact distinction is optional for I1, but failures MUST never return `0`.

---

## 19. CLI

Required command:

```bash
uv run python -m evaluation run
```

Optional if inexpensive:

```bash
uv run python -m evaluation run 01-rest-confirmed
```

or:

```bash
uv run python -m evaluation run --scenario 01-rest-confirmed
```

The optional single-scenario mode MUST NOT delay I1.

---

## 20. Tests for the Evaluation Code

The evaluator itself SHOULD have focused unit tests.

Minimum recommended tests:

### Loader

```text
loads valid scenario
rejects missing scenario id
rejects unknown relation type
rejects duplicate expectation
```

### Projector

```text
projects canonical CALLS correctly
projects status without re-derivation
projects declared/observed evidence flags
```

### Comparator

```text
exact match -> PASS
missing fact -> FAIL
wrong status -> FAIL
wrong evidence -> FAIL
```

### Runner

At least one integration test SHOULD prove:

```text
fixture -> AIP -> projection -> comparison -> PASS
```

The three real I1 scenarios remain the primary end-to-end acceptance test.

---

## 21. Documentation

`evaluation/README.md` SHALL document:

1. what the evaluation suite tests,
2. what it does not test,
3. how to run it,
4. how scenarios are structured,
5. how `expected.yaml` is interpreted,
6. that ground truth is independent from AIP derivation logic,
7. that I1 contains only the first three scenarios,
8. that `forbidden.relations` must be present but empty in I1,
9. that full unexpected/forbidden semantics are deferred to I2.

Minimal example:

```bash
uv run python -m evaluation run
```

Expected result:

```text
3 passed
RESULT: PASS
```

---

## 22. Implementation Tasks

A practical implementation breakdown is:

### Task I1.1 — Evaluation Skeleton

Deliver:

```text
evaluation package/directory
CLI entry point
scenario discovery
scenario loader
basic validation, including required empty `forbidden.relations`
```

Exit condition:

```text
runner discovers all three scenarios and parses expected.yaml
```

### Task I1.2 — Isolation and Input Execution

Deliver:

```text
clean-state mechanism
declared fixture ingestion
static OTLP fixture ingestion
```

Exit condition:

```text
one scenario can be loaded into AIP reproducibly from clean state
```

### Task I1.3 — Canonical Projection and Comparison

Deliver:

```text
RelationFact
canonical fact reader/projection
scope filtering
expectation-driven exact comparison
```

Exit condition:

```text
REST CONFIRMED scenario passes end-to-end
```

### Task I1.4 — Complete Three Scenarios and Report

Deliver:

```text
REST CONFIRMED
REST OBSERVED_ONLY
ASYNC CONFIRMED
human-readable report
exit codes
documentation
```

Exit condition:

```text
3/3 scenarios pass deterministically
```

These tasks may be implemented in fewer or more GitHub issues if that better matches the repository
workflow.

---

## 23. Definition of Done

Iteration 1 is complete when all of the following are true:

- [ ] `evaluation/` exists and is documented.
- [ ] Exactly one `expected.yaml` exists for each I1 scenario.
- [ ] Every I1 `expected.yaml` contains `forbidden.relations: []`.
- [ ] Non-empty `forbidden.relations` is rejected as unsupported in I1.
- [ ] All scenario files validate before execution.
- [ ] Scenario state is deterministically isolated/reset.
- [ ] Declared architecture fixtures use existing AIP ingestion paths.
- [ ] Runtime fixtures use the existing OTLP ingestion path unless a documented technical constraint
      prevents this.
- [ ] Actual results are projected into canonical `RelationFact` records.
- [ ] The evaluator does not derive AIP status semantics itself.
- [ ] Scenario-owned scope is applied.
- [ ] REST CONFIRMED passes.
- [ ] REST OBSERVED_ONLY passes.
- [ ] ASYNC CONFIRMED passes.
- [ ] Evidence expectations are checked.
- [ ] Wrong status causes failure.
- [ ] Missing expected fact causes failure.
- [ ] Evaluation output is deterministic.
- [ ] `uv run python -m evaluation run` returns `0` only when all scenarios pass.
- [ ] The evaluation suite runs without an LLM API key.
- [ ] Existing project tests remain green.
- [ ] No new canonical model concept is introduced solely for evaluation.

---

## 24. Alpha.1 Release Criteria

`v0.2.0-alpha.1` may be cut when:

```text
Scenarios:        3
Passed:           3
Failed:           0

Critical semantic errors: 0
```

and a clean checkout can reproduce the result using documented commands.

The alpha release does not imply that the full `v0.2.0` evaluation suite is complete.

Its meaning is narrower:

> **The deterministic AIP evaluation pipeline works end-to-end for representative REST and async
> architecture facts.**

---

## 25. Expected Follow-Up in Iteration 2

Iteration 2 is expected to extend the same kernel with:

```text
orphan messaging
mixed REST + async
request/response queue pair
forbidden facts
unexpected-fact checks
strict directionality checks
```

Iteration 1 SHOULD therefore avoid design choices that prevent those additions, but SHALL NOT
implement them prematurely.

---

## 26. Summary

Iteration 1 establishes the evaluation kernel for AIP `v0.2.0`.

It proves:

```text
known declared/runtime input
        |
        v
       AIP
        |
        v
canonical architecture facts
        |
        v
independent expected ground truth
        |
        v
deterministic PASS / FAIL
```

The iteration deliberately stops after three representative scenarios.

The governing principle is:

> **Prove the evaluation architecture with the smallest complete vertical slice before expanding the
> scenario corpus.**
