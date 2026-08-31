# AIP v0.2.0 — Iteration 4 Implementation Specification

**Status:** Draft 1 — self-contained implementation contract  
**Release target:** `v0.2.0-rc.1`  
**Iteration:** I4 — Coverage and Hardening  
**Project:** Architecture Intelligence Platform (AIP)

---

## 1. Purpose

Iterations 1–3 established and verified the semantic core of AIP's deterministic evaluation suite:

```text
I1
  evaluation kernel
  CONFIRMED
  OBSERVED_ONLY

I2
  forbidden facts
  unexpected facts
  topology and directionality

I3
  NOT_OBSERVED_IN_WINDOW
  evidence reconciliation
  CONFIRMED -> OBSERVED_ONLY
```

Iteration 4 has a different role.

It SHALL NOT introduce another architecture-intelligence dimension. It turns the alpha-quality
evaluation suite into a release-candidate-quality suite by:

1. covering partial runtime observation explicitly,
2. completing the target ten-scenario core suite with the cheap declaration-only REST case,
3. hardening scenario validation and reconciliation-fixture validation,
4. making comparison/report ordering deterministic below the presentation layer,
5. cleaning up known I3 documentation inconsistencies,
6. documenting and verifying local reproducibility.

The target release is:

```text
v0.2.0-rc.1
```

The governing idea is:

```text
I1-I3:
    prove the core semantics

I4:
    prove the suite is robust enough to qualify those semantics reproducibly
```

---

## 1.1 Specification Relationship

This document is the implementation contract for Iteration 4.

```text
I1 specification
    = v0.2.0-alpha.1

I2 specification
    = v0.2.0-alpha.2

I3 specification
    = v0.2.0-alpha.3

I4 specification
    = v0.2.0-rc.1 (this document)

v0.2.0 specification
    = normative final-release contract
```

The shipped I3 baseline is:

```text
tag:    v0.2.0-alpha.3
commit: dda80c7f3492da7ece6be2c4ac8ba36e3c8e503a
```

I4 SHALL build from that tagged baseline.

The release-level specification remains authoritative where this document is silent.

---

## 2. Iteration Goal

Iteration 4 SHALL deliver the following mandatory outcomes:

```text
09-partial-observation
10-declared-rest-relation

strict scenario-schema validation
strong reconciliation-fixture validation
deterministic comparison ordering
deterministic report ordering
clear deterministic validation errors
local reproducibility documentation
I3 post-review hardening
```

At completion, the required evaluation corpus becomes:

```text
01-rest-confirmed
02-rest-observed-only
03-async-confirmed
04-orphan-messaging
05-mixed-rest-async
06-request-response-queue-pair
07-not-observed-in-window
08-evidence-reconciliation
09-partial-observation
10-declared-rest-relation
```

Result:

```text
10 deterministic core scenarios
```

This reaches the release specification's target of 8–10 scenarios without depending on optional
DLQ or cross-batch additions.

---

## 3. Non-Goals

Iteration 4 SHALL NOT implement:

- Kubernetes discovery,
- deployment topology,
- gRPC/protobuf ingestion,
- Kafka Connect ingestion,
- CALM ingestion,
- W3C PROV,
- a new canonical entity type,
- a new generic architecture relation abstraction,
- a generic assertion DSL,
- generic scenario phases/actions/checkpoints,
- a metrics subsystem,
- precision/recall/F1 scoring,
- benchmark-history storage,
- test-data generation,
- mutation testing as an evaluation feature,
- a policy engine,
- GraphRAG,
- embeddings,
- LLM-as-a-Judge,
- a dedicated release-gating framework,
- CI sharding solely for I4,
- a numeric telemetry-confidence score.

I4 SHALL NOT turn qualitative telemetry coverage into a score.

The existing vocabulary remains:

```text
SUFFICIENT
PARTIAL
NONE
UNKNOWN
```

Optional DLQ and cross-batch scenarios are governed separately by §16 and MUST NOT block `rc.1`.

---

## 4. Design Principles

### 4.1 Harden the Existing Evaluator, Do Not Redesign It

The existing shape remains:

```text
scenario
  |
AIP ingestion/runtime behavior
  |
canonical facts
  |
small read-only projection
  |
exact comparison
  |
deterministic report
```

I4 SHALL prefer narrow corrections and validation improvements over new abstractions.

---

### 4.2 Coverage Is Qualification, Not Truth Replacement

For a declared relation that is not observed in a selected context:

```text
status = NOT_OBSERVED_IN_WINDOW
```

Coverage answers a different question:

> How much relevant telemetry did AIP actually observe for the subject in this environment/window?

Therefore:

```text
status != coverage
```

and:

```text
coverage does not convert NOT_OBSERVED_IN_WINDOW into absence
```

A relation can be:

```text
NOT_OBSERVED_IN_WINDOW + SUFFICIENT
NOT_OBSERVED_IN_WINDOW + PARTIAL
NOT_OBSERVED_IN_WINDOW + NONE
NOT_OBSERVED_IN_WINDOW + UNKNOWN
```

without any of those combinations meaning:

```text
obsolete
unused
dead
invalid
architecturally absent
```

---

### 4.3 Do Not Expand `expected.yaml` into a Coverage DSL

The final `v0.2.0` ground-truth format is deliberately small.

I4 SHALL NOT add:

```yaml
coverage:
rules:
analysis_assertions:
policy:
confidence:
```

to `expected.yaml`.

Scenario 09 SHALL verify canonical status/evidence through the existing evaluator.

Coverage qualification SHALL be verified through a focused integration test against AIP's existing
runtime-analysis boundary.

This keeps:

```text
expected.yaml
    = canonical fact oracle
```

rather than turning it into a generic analysis assertion language.

---

### 4.4 Determinism Applies Below the Reporter

I2/I3 already sort report output.

I4 SHALL additionally ensure that comparison results themselves are deterministic.

The following should not depend on:

```text
Python set iteration order
hash randomization
filesystem discovery order
Neo4j row ordering where no semantic ordering exists
```

Given the same canonical actual facts and scenario ground truth:

```text
ScenarioResult == same ordered ScenarioResult
rendered report == same rendered report
```

---

### 4.5 Validation Must Fail Fast

Malformed scenarios are configuration errors, not semantic evaluation failures.

They SHALL fail before AIP scenario execution wherever practical.

```text
invalid fixture/schema
    -> exit 2 / configuration error

valid scenario with semantic mismatch
    -> exit 1 / evaluation failure

valid passing suite
    -> exit 0
```

---

## 5. Baseline Evaluation Model

I4 keeps the existing core model:

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

No `CoverageFact` is required.

No additional generic assertion object is required.

The existing mismatch vocabulary remains:

```text
MISSING
SEMANTIC_MISMATCH
FORBIDDEN_PRESENT
UNEXPECTED
```

No dedicated `WRONG_DIRECTION` mismatch type is required for I4.

Direction remains enforced through:

```text
missing expected relation
+
forbidden inverse relation
+
unexpected in-scope relation
```

---

## 6. Scenario 09 — Partial Observation

### 6.1 Purpose

Scenario 09 SHALL prove that AIP behaves correctly when a service is instrumented and emits useful
telemetry, but only part of its declared behavior is observed in the selected window.

The scenario SHALL distinguish:

```text
observed declared relation
declared but unobserved relation of an observed interaction kind
declared but unobserved relation of a different, unobserved interaction kind
```

This exercises both:

```text
NOT_OBSERVED_IN_WINDOW
```

and AIP's qualitative coverage qualification.

---

## 6.2 Reference Topology

Use a small synthetic topology:

```text
                          observed HTTP
OrderService --------------------------------> ProductService
     |
     | declared HTTP, not observed
     +---------------------------------------> InventoryService
     |
     | declared messaging, not observed
     +-------------------- SENDS ------------> audit-q
```

Canonical facts:

```text
OrderService
    CALLS ProductService.GET /products/{id}

OrderService
    CALLS InventoryService.GET /inventory/{id}

OrderService
    SENDS audit-q
```

Runtime fixture:

```text
only OrderService -> ProductService GET /products/{id}
is observed in the selected environment/window
```

No messaging telemetry is supplied.

---

## 6.3 Expected Canonical Statuses

The three expected relations SHALL be:

```text
CALLS ProductService.GET /products/{id}
    status = CONFIRMED
    declared = true
    observed = true

CALLS InventoryService.GET /inventory/{id}
    status = NOT_OBSERVED_IN_WINDOW
    declared = true
    observed = false

SENDS audit-q
    status = NOT_OBSERVED_IN_WINDOW
    declared = true
    observed = false
```

This proves that partial observation does not cause AIP to:

```text
delete unobserved declared facts
invent observations
collapse relation types
treat non-observation as absence
```

---

## 6.4 Recommended `expected.yaml`

```yaml
scenario: partial-observation

description: >
  OrderService declares two REST calls and one messaging send. Only the ProductService REST call is
  observed in the selected environment/window. The other declared relations remain canonical facts
  with NOT_OBSERVED_IN_WINDOW rather than being interpreted as absent.

scope:
  entities:
    - service:order-service
    - service:product-service
    - service:inventory-service
    - operation:service:product-service:GET:/products/{id}
    - operation:service:inventory-service:GET:/inventory/{id}
    - queue:audit-q
  relation_types:
    - CALLS
    - SENDS

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

    - type: CALLS
      source: service:order-service
      target: operation:service:inventory-service:GET:/inventory/{id}
      status: NOT_OBSERVED_IN_WINDOW
      evidence:
        declared: true
        observed: false

    - type: SENDS
      source: service:order-service
      target: queue:audit-q
      status: NOT_OBSERVED_IN_WINDOW
      evidence:
        declared: true
        observed: false

forbidden:
  relations: []
```

---

## 6.5 Runtime Fixture

Scenario 09 SHOULD use the real OTLP ingestion path.

The fixture SHALL contain a matched HTTP CLIENT/SERVER pair for:

```text
OrderService
  -> ProductService
  GET /products/{id}
```

inside the fixed scenario window.

It SHALL contain no runtime observation for:

```text
OrderService
  -> InventoryService
  GET /inventory/{id}

OrderService
  SENDS audit-q
```

No clock-relative timestamps are allowed.

---

## 6.6 Coverage Qualification Assertions

Scenario 09's `expected.yaml` SHALL remain limited to canonical facts.

A dedicated integration test SHALL call AIP's existing production runtime-analysis boundary and
verify the two not-observed relations are qualified correctly.

For the unobserved `CALLS` relation:

```text
OrderService has HTTP observations in the same window
relation kind = CALLS / HTTP

coverage = SUFFICIENT
```

For the unobserved `SENDS` relation:

```text
OrderService has some usable telemetry
but no messaging observations in the same window

coverage = PARTIAL
```

Required assertions:

```text
unobserved CALLS -> NOT_OBSERVED_IN_WINDOW + SUFFICIENT
unobserved SENDS -> NOT_OBSERVED_IN_WINDOW + PARTIAL
```

The test SHALL use existing AIP functions such as:

```text
declared_only_relations(...)
telemetry_coverage(...)
```

rather than reproducing `_classify_coverage` logic in the evaluator.

---

## 6.7 What I4 Does Not Need to Prove in Scenario 09

Scenario 09 does not need to create separate evaluation scenarios for:

```text
NONE
UNKNOWN
```

if those production branches are already covered by existing runtime-analysis tests.

The purpose of Scenario 09 is representative partial observation, not exhaustive multiplication of:

```text
relation type x status x coverage class
```

---

## 6.8 Acceptance

```text
3 expected canonical relations exist
1 is CONFIRMED
2 are NOT_OBSERVED_IN_WINDOW
no unexpected in-scope relations exist

coverage check:
    unobserved CALLS = SUFFICIENT
    unobserved SENDS = PARTIAL
```

The scenario SHALL remain deterministic under repeated runs.

---

## 7. Scenario 10 — Declared REST Relation

### 7.1 Purpose

The release-level target suite includes a pure declared REST relation case that was intentionally
deferred by I1–I3.

I4 SHALL add it because it is inexpensive and completes the ten-scenario target without introducing
new runtime or harness semantics.

---

## 7.2 Topology

```text
OrderService
    |
    | CALLS
    v
ProductService.GET /products/{id}

ProductService
    |
    | PROVIDES
    v
GET /products/{id}
```

Inputs:

```text
ProductService OpenAPI declaration
OrderService Architecture Manifest CALLS declaration
no telemetry
```

---

## 7.3 Ground Truth

This scenario tests relation identity and direction only.

No runtime status is required.

Recommended `expected.yaml`:

```yaml
scenario: declared-rest-relation

description: >
  ProductService declares GET /products/{id} and OrderService explicitly declares a CALLS
  dependency on that operation. No runtime observation is involved.

scope:
  entities:
    - service:order-service
    - service:product-service
    - operation:service:product-service:GET:/products/{id}
  relation_types:
    - PROVIDES
    - CALLS

expected:
  relations:
    - type: PROVIDES
      source: service:product-service
      target: operation:service:product-service:GET:/products/{id}

    - type: CALLS
      source: service:order-service
      target: operation:service:product-service:GET:/products/{id}

forbidden:
  relations: []
```

No `observation` block is required.

No status/evidence fields are required because the purpose is declaration topology, not runtime
classification.

---

## 7.4 Acceptance

```text
ProductService PROVIDES operation
OrderService CALLS same exact operation
PROVIDES does not imply an additional CALLS
no telemetry required
no LLM required
no unexpected in-scope relation
```

After Scenario 10:

```text
core scenario count = 10
```

---

## 8. Scenario Schema Hardening

I4 SHALL make the hand-authored scenario format strict enough that typos cannot silently weaken or
change an assertion.

The loader SHALL continue to raise:

```text
ScenarioValidationError
```

with:

```text
scenario
file
field
reason
```

---

## 8.1 Allowed Top-Level Keys

Exactly these top-level keys are recognized:

```text
scenario
description
scope
observation
expected
forbidden
```

`observation` is optional.

Unknown top-level keys SHALL be rejected.

Example:

```yaml
expectd:   # typo
```

must fail at load time.

---

## 8.2 `scope` Validation

Allowed keys:

```text
entities
relation_types
```

Requirements:

```text
entities:
    required
    list
    non-empty
    canonical ids
    no duplicates

relation_types:
    optional
    list when present
    non-empty when present
    known relation types
    no duplicates
```

Unknown `scope` fields SHALL be rejected.

---

## 8.3 `observation` Validation

Allowed keys:

```text
environment
window
```

Allowed `window` keys:

```text
start
end
```

For a scenario containing runtime telemetry:

```text
environment required
window.start required
window.end required
```

Both timestamps SHALL be timezone-aware ISO-8601 timestamps.

Required:

```text
start < end
```

Naive timestamps SHALL be rejected.

Example invalid value:

```yaml
start: "2026-08-01T10:00:00"
```

Example valid values:

```yaml
start: "2026-08-01T10:00:00Z"
end:   "2026-08-01T11:00:00+00:00"
```

The evaluation runner MUST NOT depend on the host timezone.

---

## 8.4 `expected` Validation

Allowed key:

```text
relations
```

Each expected relation allows exactly:

```text
type
source
target
status
evidence
```

Unknown keys SHALL be rejected.

Required:

```text
type
source
target
```

Optional status values are limited to:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
```

A missing status remains valid for declaration-only assertions.

---

## 8.5 Evidence Validation

Allowed evidence keys:

```text
declared
observed
```

If present, each value MUST be a real YAML boolean:

```yaml
declared: true
observed: false
```

Values such as:

```yaml
declared: "true"
observed: 1
```

SHALL be rejected.

Unknown evidence fields SHALL be rejected.

---

## 8.6 `forbidden` Validation

I2's rules remain unchanged.

Allowed key:

```text
relations
```

Each forbidden relation contains exactly:

```text
type
source
target
```

No status or evidence is allowed.

Duplicate forbidden identities and expected/forbidden contradictions remain invalid.

---

## 8.7 Scope Consistency

Every expected or forbidden relation MUST be inside the scenario-owned scope.

At minimum:

```text
source in scope.entities
OR
target in scope.entities
```

If `scope.relation_types` is present:

```text
relation type MUST be included
```

A scenario SHALL NOT contain an assertion that its own scope excludes.

I4 does not require both endpoints to be listed if one endpoint is sufficient for the normative scope
rule, although scenario authors SHOULD list all explicitly referenced canonical ids for readability.

---

## 9. Reconciliation Fixture Hardening

### 9.1 I3 Finding

I3 rejects:

```text
input/reconciliation/declarations/
    <completely empty>
```

but the current check is filesystem-level.

A directory can contain entries while still containing zero importable declaration sources:

```text
input/reconciliation/declarations/
└── order-service/
    <empty>
```

A placeholder-only directory can therefore silently result in:

```text
import_all_sources(...)
    -> zero imported services
    -> reconciliation no-op
```

I4 SHALL close this gap.

---

## 9.2 Required Behavior

If:

```text
input/reconciliation/declarations/
```

exists, it MUST contain at least one declaration source recognized by the existing AIP ingestion
pipeline.

The evaluator SHALL reuse production source discovery/parsing semantics where practical.

Preferred approach:

```text
parse_sources(reconciliation_dir)
    |
empty service/model result
    -> ScenarioValidationError
```

The evaluator SHOULD NOT maintain a second independent list of recognized declaration filenames or
extensions.

---

## 9.3 Failure Shape

Example deterministic error:

```text
invalid scenario configuration:
scenario=evidence-reconciliation
field=input.reconciliation.declarations
reason=no importable declaration sources found
```

Exact punctuation is not normative.

The semantic information is.

---

## 9.4 Existing Valid Scenario Must Remain Unchanged

`08-evidence-reconciliation` remains valid.

The hardening is intended only to turn misleading fixtures into configuration errors.

Required tests:

```text
root reconciliation directory empty -> invalid
only empty service directory -> invalid
only non-importable placeholder file -> invalid
valid declaration source -> accepted
existing scenario 08 -> accepted and passes
```

---

## 10. Deterministic Comparison Ordering

### 10.1 Current Requirement

Report rendering is already sorted.

I4 SHALL make `ScenarioResult.mismatches` deterministic as well.

The comparator SHALL NOT rely on iteration order of:

```python
set[RelationFact]
```

for `UNEXPECTED` mismatches.

---

## 10.2 Normative Mismatch Order

A stable ordering key SHOULD be:

```text
relation type
source
target
mismatch kind
```

with expected/actual identity fallback as required.

Equivalent deterministic ordering is acceptable.

The important property is:

```text
same semantic input
    -> same mismatch tuple order
```

---

## 10.3 Regression Test

Construct equivalent actual fact sets in different insertion/hash orders.

Required:

```text
compare(...).mismatches identical
render(...) identical
```

The test SHOULD include more than one mismatch category.

---

## 11. Deterministic Error Reporting

Known scenario configuration errors SHALL be rendered through one stable path.

Examples:

```text
unknown scenario
empty scenario suite
malformed expected.yaml
unknown relation type
unknown field
invalid evidence boolean
invalid timestamp
invalid window
empty/non-importable reconciliation input
duplicate assertion
expected/forbidden contradiction
scope-excluded assertion
```

These are:

```text
configuration failures
exit code = 2
```

Semantic mismatches remain:

```text
exit code = 1
```

Passing evaluation remains:

```text
exit code = 0
```

I4 does not need to suppress Python tracebacks for genuinely unexpected programmer/infrastructure
exceptions.

The goal is deterministic handling of known invalid input, not hiding defects.

---

## 12. Documentation Cleanup from I3 Review

I4 SHALL close the two non-semantic I3 review findings.

### 12.1 Projector Docstring

`evaluation/projector.py::load_relation_facts()` SHALL no longer describe the runtime vocabulary as
only:

```text
CONFIRMED / OBSERVED_ONLY
```

It SHALL include:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
```

---

## 12.2 Runner Docstring

The runner's orchestration description SHALL include the optional reconciliation phase:

```text
reset
-> declarations
-> telemetry
-> optional reconciliation
-> project
-> compare
```

---

## 12.3 Specification Index

Because `v0.2.0-alpha.3` is already tagged, the v0.2 specification index SHALL be corrected from:

```text
I3 | Implementation complete — tag pending
```

to:

```text
I3 | Shipped
```

and the I4 specification SHALL be added to the document table.

During I4 implementation:

```text
I4 | Implementation in progress
```

or equivalent is acceptable.

Immediately before the `rc.1` tag:

```text
I4 | Implementation complete — tag pending
```

After the tag:

```text
I4 | Shipped
```

---

## 13. Local Reproducibility

A clean checkout SHALL be able to reproduce I4 without an LLM API key.

Required environment:

```text
Python/uv according to project metadata
Docker available
no separately running Neo4j required
no OPENAI_API_KEY required
```

Reference commands:

```bash
uv sync

uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit
uv run pytest tests/integration

uv run python -m evaluation run
```

Expected evaluation result:

```text
10/10 PASS
```

---

## 13.1 Repeated-Run Determinism

At least one release-candidate verification SHALL run the evaluator more than once against a clean
state.

Required property:

```text
same scenarios
same PASS/FAIL result
same ordered scenario lines
same ordered mismatch output
same counters
```

A byte-for-byte stdout comparison MAY be used.

A dedicated benchmark/history framework SHALL NOT be introduced.

---

## 13.2 CI

The existing CI SHALL remain green.

I4 does not require adding a second full evaluation-container run to CI if existing integration tests
already exercise all scenarios and the CLI is verified separately.

A direct:

```bash
uv run python -m evaluation run
```

CI step MAY be added if its maintenance/runtime cost remains small, but it is not required for
`rc.1`.

This preserves the project's recent CI performance improvements.

---

## 14. Reporting

The human-readable report SHALL update its banner:

```text
AIP Evaluation — I4
```

Expected successful shape:

```text
AIP Evaluation — I4

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed
[PASS] 04-orphan-messaging
[PASS] 05-mixed-rest-async
[PASS] 06-request-response-queue-pair
[PASS] 07-not-observed-in-window
[PASS] 08-evidence-reconciliation
[PASS] 09-partial-observation
[PASS] 10-declared-rest-relation

Scenarios:          10
Passed:             10
Failed:             0

Missing facts:      0
Unexpected facts:   0
Forbidden facts present: 0
Wrong statuses:     0
Evidence errors:    0

RESULT: PASS
```

I4 SHALL NOT add a scoring system.

A dedicated `Wrong directions` counter remains optional because direction failures are already
represented deterministically by missing/forbidden/unexpected facts.

---

## 15. Test Requirements

### 15.1 Unit Tests

Required or equivalent unit coverage:

```text
strict top-level key validation
strict nested key validation
expected relation unknown key rejected
unknown status rejected
evidence non-boolean rejected
duplicate scope entity rejected
duplicate relation type rejected
runtime scenario without complete window rejected
naive runtime timestamp rejected
window start >= end rejected
scope-excluded assertion rejected

reconciliation:
    empty root rejected
    empty nested service directory rejected
    placeholder-only content rejected
    recognized source accepted

comparison:
    mismatch order deterministic across differently ordered actual sets

existing I1-I3 loader/comparator tests remain green
```

---

## 15.2 Integration Tests

Required:

```text
09-partial-observation passes end-to-end
09 coverage qualification:
    unobserved CALLS -> SUFFICIENT
    unobserved SENDS -> PARTIAL

10-declared-rest-relation passes end-to-end

08-evidence-reconciliation still passes after validation hardening

all previous scenarios 01-08 pass unchanged

full suite:
    10/10 PASS
```

No production AIP semantic change is expected for mandatory I4 work.

If a failing I4 scenario exposes a real AIP defect, fix the production defect rather than weakening
the ground truth.

---

## 16. Optional Candidate — DLQ Directionality

The release-level specification allows a DLQ scenario only if inexpensive.

It is **not** part of I4's mandatory Definition of Done.

### 16.1 Admission Gate

Add the scenario only if all are true:

```text
an existing production ingestion path already produces DEAD_LETTERS_TO
a small synthetic declaration fixture can exercise it
no new canonical concept is needed
no new adapter family is needed
evaluation support is a narrow raw-relation projection extension
one focused PR is sufficient
```

If any condition is false:

```text
DEFER
```

and `rc.1` proceeds without it.

---

## 16.2 If Included

Candidate scenario:

```text
11-dlq-directionality
```

Expected topology:

```text
primary-q
    |
    | DEAD_LETTERS_TO
    v
primary-dlq
```

Forbidden inverse:

```text
primary-dlq
    DEAD_LETTERS_TO
primary-q
```

Required evaluator changes would be limited to declaration-level relation support:

```text
KNOWN_RELATION_TYPES += DEAD_LETTERS_TO
raw canonical projector includes Queue -> Queue DEAD_LETTERS_TO
```

No runtime status branch is required unless production AIP already defines one.

---

## 17. Optional Candidate — Cross-Batch HTTP Correlation

Cross-batch HTTP correlation is already a production capability.

An evaluation scenario is optional.

It SHALL be added only if the fixture mechanism remains small.

### 17.1 Admission Gate

Accept only if it can be expressed without:

```text
generic step DSL
generic workflow engine
arbitrary fixture actions
persistent test orchestration framework
```

A narrowly scoped mechanism such as two deterministic OTLP submissions is acceptable.

---

## 17.2 Candidate Semantics

```text
OTLP POST 1:
    CLIENT span

OTLP POST 2:
    matching SERVER span

AIP correlation buffer:
    combines them

result:
    canonical CALLS relation observed
    expected status according to declaration state
```

The scenario must prove cross-batch correlation itself, not merely reproduce the same outcome using
one combined batch.

If implementation-specific harness work becomes material:

```text
DEFER
```

The release SHALL NOT be delayed for this scenario.

---

## 18. Implementation Tasks

A practical delivery split is:

### I4.1 — Partial Observation and Coverage

Deliver:

```text
09-partial-observation
static declarations
static OTLP fixture
canonical expected.yaml
coverage qualification integration test
```

Exit condition:

```text
scenario 09 PASS
unobserved CALLS coverage = SUFFICIENT
unobserved SENDS coverage = PARTIAL
01-08 remain green
```

---

### I4.2 — Complete Core Scenario Set

Deliver:

```text
10-declared-rest-relation
declaration-only fixture
PROVIDES + CALLS assertions
```

Exit condition:

```text
10/10 core scenarios PASS
```

No runtime/evaluator-model change should be necessary beyond any validation changes delivered
elsewhere.

---

### I4.3 — Validation and Determinism Hardening

Deliver:

```text
strict scenario schema
typed evidence/status validation
timezone/window validation
scope consistency validation
strong reconciliation-source validation
deterministic comparator mismatch order
I3 docstring cleanup
unit regression coverage
```

Exit condition:

```text
known malformed inputs fail deterministically with exit 2
valid scenarios remain unchanged
same semantic input produces same ordered comparison/report
```

---

### I4.4 — RC Documentation and Reproducibility

Deliver:

```text
evaluation/README.md:
    scenarios 09/10
    partial-observation explanation
    coverage qualification explanation
    clean-checkout commands

docs/specifications/0.2.0/README.md:
    I3 -> Shipped
    add i4-coverage-hardening.md
    I4 status updated appropriately

reporter.py:
    AIP Evaluation — I4

clean-checkout verification:
    unit
    integration
    evaluation 10/10
    lint/format
```

Exit condition:

```text
Definition of Done satisfied
rc.1 release criteria satisfied
```

---

### I4.X — Optional Edge-Case Scenario

Only after I4.1–I4.4 are complete:

```text
DLQ directionality
OR
cross-batch HTTP correlation
```

may be added if it satisfies its admission gate.

Neither is required.

---

## 19. Definition of Done

I4 is complete when all mandatory items below are true.

### Scenario coverage

- [ ] `09-partial-observation` exists and passes.
- [ ] Scenario 09 contains fixed synthetic OTLP input through the real ingestion path.
- [ ] Scenario 09 has one `CONFIRMED` relation.
- [ ] Scenario 09 has at least one `NOT_OBSERVED_IN_WINDOW` relation.
- [ ] Scenario 09 proves non-observation is not interpreted as architectural absence.
- [ ] Scenario 09 coverage integration test asserts `SUFFICIENT` for an unobserved relation of an
      observed interaction kind.
- [ ] Scenario 09 coverage integration test asserts `PARTIAL` for an unobserved relation of a
      different, unobserved interaction kind.
- [ ] `10-declared-rest-relation` exists and passes.
- [ ] Scenario 10 asserts exact `PROVIDES` and `CALLS` canonical identities.
- [ ] Scenario 10 requires no telemetry.
- [ ] Core suite reaches 10 scenarios.
- [ ] All 10 scenarios pass.

### Validation hardening

- [ ] Unknown top-level scenario fields are rejected.
- [ ] Unknown nested fields are rejected.
- [ ] Expected relation fields are strict.
- [ ] Status vocabulary is validated.
- [ ] Evidence values must be booleans when specified.
- [ ] Duplicate scope items are rejected.
- [ ] Runtime timestamps are timezone-aware.
- [ ] Runtime windows require `start < end`.
- [ ] Assertions excluded by their own scenario scope are rejected.
- [ ] Reconciliation directories with zero importable sources are rejected.
- [ ] Valid Scenario 08 remains unchanged.

### Determinism

- [ ] Comparator mismatch tuple order is deterministic.
- [ ] Reporter order remains deterministic.
- [ ] Tests prove differently ordered equivalent actual fact sets produce identical results.
- [ ] Scenario discovery remains deterministic.
- [ ] Validation errors identify scenario/file/field/reason consistently.

### Documentation / reproducibility

- [ ] I3 is marked shipped in the v0.2 specification index.
- [ ] I4 specification is indexed.
- [ ] I3 stale projector/runner docstrings are corrected.
- [ ] `evaluation/README.md` documents scenarios 09/10.
- [ ] `evaluation/README.md` documents partial observation and qualitative coverage.
- [ ] Clean-checkout commands are documented.
- [ ] The suite runs without an LLM API key.
- [ ] Unit tests are green.
- [ ] Integration tests are green.
- [ ] Ruff check and format check are green.
- [ ] CI and CodeQL are green.
- [ ] Critical semantic errors = 0.

Optional DLQ/cross-batch scenarios are explicitly excluded from this checklist.

---

## 20. RC.1 Release Criteria

`v0.2.0-rc.1` may be cut when:

```text
Core scenarios:          10
Passed:                  10
Failed:                   0

Critical semantic errors: 0

unit tests:               green
integration tests:        green
lint/format:              green
CI:                       green
CodeQL:                   green
clean-checkout run:       reproducible
```

Tag only after verification on the resulting `main` commit:

```text
implementation PRs merged
        |
        v
main green
        |
        v
clean checkout / local verification
        |
        v
10/10 deterministic evaluation
        |
        v
v0.2.0-rc.1
```

---

## 21. Critical Semantic Errors for I4

The following remain release-blocking:

```text
invented architecture dependency
missing expected architecture dependency
wrong canonical source/target identity
reversed relation direction
wrong provider resolution
wrong sender/consumer resolution

incorrect CONFIRMED
incorrect OBSERVED_ONLY
incorrect NOT_OBSERVED_IN_WINDOW

out-of-window evidence treated as in-window
non-observation interpreted as absence

surviving evidence lost during reconciliation
fact deleted while evidence remains

partial observation causing declared facts to disappear
coverage classification implemented independently in evaluator
coverage label used as an architecture-absence verdict

scenario typo silently accepted in a way that weakens an assertion
nondeterministic PASS/FAIL result for identical semantic input
```

Target:

```text
Critical semantic errors = 0
```

---

## 22. Expected Follow-Up in I5

I5 SHALL introduce no new architecture semantics.

After I4, the semantic/evaluation feature set is frozen for `v0.2.0`.

I5 activities should be limited to:

```text
clean-checkout qualification
final documentation
release notes
ROADMAP update
CHANGELOG update
final regression fixes
final status/index updates
confirmation of zero critical semantic errors
tag/release v0.2.0
```

The intended boundary is:

```text
I4:
    release candidate is technically robust

I5:
    release candidate is qualified and published as v0.2.0
```

If I5 uncovers a semantic defect, fixing the defect is allowed.

Adding a new feature merely because it is interesting is not.

---

## 23. Summary

I4 moves AIP from semantic alpha to release candidate without broadening the product.

Mandatory additions are intentionally small:

```text
partial observation
+
pure declared REST case
+
validation hardening
+
deterministic ordering
+
reconciliation-fixture hardening
+
reproducibility
```

The resulting suite reaches the intended ten core scenarios:

```text
10/10 deterministic scenarios
```

while preserving the core architectural rule established throughout v0.2:

> **The evaluator verifies AIP's architecture semantics; it does not become a second implementation
> of them.**

And the runtime qualification rule remains:

```text
NOT_OBSERVED_IN_WINDOW
    != architectural absence

coverage
    = qualification of observation context
    != truth replacement
```
