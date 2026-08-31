# AIP v0.2.0 — Iteration 3 Implementation Specification

**Status:** Draft 1 — self-contained implementation contract  
**Release target:** `v0.2.0-alpha.3`  
**Iteration:** I3 — Evidence and Runtime Semantics  
**Project:** Architecture Intelligence Platform (AIP)

---

## 1. Purpose

Iterations 1 and 2 established a deterministic evaluation kernel and proved that AIP preserves
canonical relation identity, interaction type, and direction under representative REST and messaging
topologies.

The shipped baseline for this iteration is:

```text
v0.2.0-alpha.1
    evaluation kernel
    CONFIRMED / OBSERVED_ONLY
    deterministic comparison

v0.2.0-alpha.2
    forbidden assertions
    exhaustive unexpected-fact detection
    topology / directionality scenarios
```

Iteration 3 extends that same evaluation kernel to the evidence semantics that are deliberately more
subtle than simple relation presence:

```text
declared but not observed in selected context
surviving evidence after declaration reconciliation
fact survival while evidence remains
status transition caused by surviving evidence
```

I3 does **not** add new architecture intelligence. These behaviors already exist in AIP's runtime
analysis, evidence model, and graph reconciliation logic. I3 makes them reproducibly verifiable
against independently authored ground truth.

The target release is:

```text
v0.2.0-alpha.3
```

---

### 1.1 Specification Relationship

This document is the implementation contract for Iteration 3 and builds on the released I2 baseline:

```text
I1 specification
    = implementation contract for v0.2.0-alpha.1

I2 specification
    = implementation contract for v0.2.0-alpha.2

I3 specification
    = implementation contract for v0.2.0-alpha.3 (this document)

v0.2.0 specification
    = normative final-release contract
```

`v0.2.0-alpha.2` is tagged at commit:

```text
f7534aae03e0a1132d324da550b5297488600165
```

I3 SHALL NOT redesign behavior already proven by I1/I2. Existing AIP runtime-analysis, evidence,
reconciliation, OpenTelemetry, and canonical-model code remains the system under test.

The release-level specification remains authoritative if this document is silent.

---

## 2. Iteration Goal

Iteration 3 SHALL deliver four capabilities:

1. deterministic evaluation of `NOT_OBSERVED_IN_WINDOW`,
2. one evidence-reconciliation scenario in which declared support is removed while observed support
   survives,
3. explicit proof that the fact survives the reconciliation because evidence remains,
4. explicit proof that its status changes from `CONFIRMED` to `OBSERVED_ONLY` after the declaration
   evidence is removed.

Two new scenarios are added:

```text
07-not-observed-in-window
08-evidence-reconciliation
```

Together with the six scenarios delivered by I1/I2, I3 leaves the suite at:

```text
8 deterministic core scenarios
```

This reaches the final `v0.2.0` specification's required minimum of eight scenarios while leaving
coverage qualification and optional hardening cases to I4.

---

## 3. Non-Goals

Iteration 3 SHALL NOT implement:

- quantitative telemetry coverage,
- `SUFFICIENT` / `PARTIAL` / `NONE` / `UNKNOWN` assertions in the evaluation record,
- the partial-observation scenario from final Scenario 10,
- DLQ directionality,
- cross-batch HTTP correlation as an evaluation scenario,
- a generic multi-phase scenario DSL,
- arbitrary scenario actions,
- generic before/after assertion checkpoints,
- evidence scoring,
- precision/recall/F1,
- exact runtime request counting,
- W3C PROV,
- a policy/rules engine,
- a new canonical entity or relation type,
- an LLM-based evaluator,
- GraphRAG,
- CI sharding or unrelated test-infrastructure redesign.

For avoidance of doubt, the release-level delivery plan assigns the **partial-observation scenario and
coverage hardening to I4**. I3 only establishes the underlying `NOT_OBSERVED_IN_WINDOW` and evidence
reconciliation semantics.

Scenario 1 from the final target suite (a pure declared REST relation without runtime semantics)
also remains outside I3's focus.

---

## 4. Governing Semantics

### 4.1 Fact, Evidence, Status, and Observation Context Remain Distinct

I3 is centered on this distinction:

```text
Fact
    != Evidence
    != Status
    != Observation Context
```

A canonical relation is the fact.

`DECLARED` and `OBSERVED` records support that fact.

A status is a context-sensitive interpretation of that support.

The observation environment/window determines which runtime evidence is relevant to that
interpretation.

---

### 4.2 Evidence-Preservation Invariant

The existing AIP graph invariant is normative for I3:

```text
Delete(Fact) iff Evidence(Fact) is empty
```

Equivalent operationally:

```text
Evidence(Fact) != empty
    -> Fact MUST survive
```

Removing one evidence class MUST NOT remove another evidence class.

In particular:

```text
remove stale DECLARED evidence
    != remove surviving OBSERVED evidence
```

---

### 4.3 Status Semantics

I3 completes the three-state runtime status vocabulary used by `v0.2.0`:

```text
DECLARED + OBSERVED in selected context
    -> CONFIRMED

no DECLARED + OBSERVED in selected context
    -> OBSERVED_ONLY

DECLARED + no OBSERVED in selected context
    -> NOT_OBSERVED_IN_WINDOW
```

The evaluator MUST read the actual status produced by AIP.

It MUST NOT contain an independent Python status engine such as:

```python
if declared and not observed:
    status = "NOT_OBSERVED_IN_WINDOW"
```

That would duplicate the production behavior under test.

---

### 4.4 `NOT_OBSERVED_IN_WINDOW` Is Context-Qualified

`NOT_OBSERVED_IN_WINDOW` means exactly:

> The relation has declared support, but AIP found no matching observed evidence in the selected
> environment and observation window.

It does **not** mean:

```text
unused
obsolete
dead
invalid
unreachable
absent
forbidden
```

Therefore:

```text
NOT_OBSERVED_IN_WINDOW != architectural absence
NOT_OBSERVED_IN_WINDOW != policy violation
```

A relation with this status remains an expected canonical fact.

---

### 4.5 Evidence Flags in Evaluation Records

I3 makes the runtime meaning of the existing evaluation fields explicit.

For a `RelationFact` evaluated with an observation context:

```text
declared_evidence
    = declared support exists for the relation

observed_evidence
    = observed support matches the scenario's selected environment/window
```

The `observed_evidence` assertion is therefore context-qualified in runtime scenarios.

This matters because Scenario 07 deliberately contains an observation outside the selected window.
The graph may contain historical observed evidence while the scenario expectation is still:

```yaml
observed: false
status: NOT_OBSERVED_IN_WINDOW
```

for the selected window.

No field rename or new evidence model is required in I3.

---

## 5. Canonical Semantics Used by I3

I3 continues to use the existing relation vocabulary already projected by the evaluation suite:

```text
(Service)-[:CALLS]->(Operation)
(Service)-[:PROVIDES]->(Operation)
(Service)-[:SENDS]->(Queue)
(Service)-[:RECEIVES_FROM]->(Queue)
```

The two I3 scenarios use `CALLS` as the smallest sufficient relation type for exercising
environment/window classification and declaration reconciliation.

No generic service-to-service relation is introduced.

No new persisted status property is introduced: AIP status remains derived at query time.

---

## 6. Evaluation Data Model

### 6.1 `RelationFact` Remains Unchanged

I3 SHALL reuse:

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

No `EvidenceFact`, `StatusTransition`, `CoverageFact`, or generic checkpoint model is required.

---

### 6.2 `Scenario` Remains Unchanged

The existing loaded scenario model remains sufficient.

I3 SHALL NOT add workflow/actions to `expected.yaml`.

The reconciliation phase is represented by a narrowly defined **input-directory convention**, not a
generic scenario language.

---

### 6.3 Comparator Failure Vocabulary Remains Unchanged

I3 does not need a new mismatch category.

Existing categories remain sufficient:

```text
MISSING
SEMANTIC_MISMATCH
FORBIDDEN_PRESENT
UNEXPECTED
```

Examples:

```text
expected NOT_OBSERVED_IN_WINDOW
actual CONFIRMED
    -> SEMANTIC_MISMATCH / wrong status

expected observed=false
actual observed=true
    -> SEMANTIC_MISMATCH / evidence error

expected reconciliation-surviving CALLS
actual fact missing
    -> MISSING
```

---

## 7. Projector Extension

### 7.1 Current Gap

At the I2 baseline, `evaluation/projector.py` classifies:

```text
CONFIRMED
OBSERVED_ONLY
```

using AIP's own runtime-analysis guard predicates.

A declared relation with no observation in the selected environment/window currently falls through
to an unclassified `RelationFact(status=None, ...)`.

I3 SHALL close that gap.

---

### 7.2 Third Classification Branch

The projector SHALL reuse AIP's existing runtime predicates and status constant:

```text
_DECLARED_EXISTS
_NOT_DECLARED_EXISTS
_OBSERVED_EXISTS
_NOT_OBSERVED_EXISTS
NOT_OBSERVED_IN_WINDOW
```

The third branch is semantically:

```text
_DECLARED_EXISTS
AND
_NOT_OBSERVED_EXISTS
    -> NOT_OBSERVED_IN_WINDOW
```

at exact canonical identity:

```text
(type, source, target)
```

The projector MUST preserve the I1 post-merge correction that prevents coarser
`(source, relation_type)` matching.

---

### 7.3 Refactor the Existing Branch Helper Instead of Adding Status Logic

The I2 helper effectively assumes:

```text
CONFIRMED      -> declared=true, observed=true
OBSERVED_ONLY  -> declared=false, observed=true
```

That assumption is no longer sufficient because:

```text
NOT_OBSERVED_IN_WINDOW
    -> declared=true, observed=false
```

The helper SHOULD therefore become mechanically parameterized, for example:

```python
_classified_branch(
    relation_type=...,
    target_label=...,
    declared_guard=...,
    observed_guard=...,
    status=...,
    declared=True,
    observed=False,
)
```

The important rule is:

> The query branch selects rows using AIP's production guard predicates and emits the corresponding
> AIP status literal. Python must not derive the status from evidence booleans.

---

### 7.4 Relation Types Classified in I3

The projector SHOULD add the third branch for all relation types it already runtime-classifies:

```text
CALLS
SENDS
RECEIVES_FROM
```

even though Scenario 07 uses `CALLS`.

This keeps the projection symmetric and avoids a later special case.

`PROVIDES` remains outside the runtime-status branch unless existing production runtime analysis
exposes equivalent semantics required by a scenario.

---

## 8. Scenario 07 — Not Observed in Window

### 8.1 Purpose

Prove that a declared dependency remains a real canonical fact when no matching observation exists in
the selected time window.

The scenario SHALL also prove that an observation outside the selected window does not incorrectly
turn the relation into `CONFIRMED`.

---

### 8.2 Topology

```text
OrderService
    |
    | CALLS
    v
ProductService.GET /products/{id}
```

Declared architecture exists.

A matching runtime call is supplied, but its timestamp is **outside** the selected evaluation window.

Example:

```text
runtime observation: 2026-08-01T09:30:00Z

evaluation window:
    start 2026-08-01T10:00:00Z
    end   2026-08-01T11:00:00Z
```

---

### 8.3 Expected Ground Truth

Recommended `expected.yaml`:

```yaml
scenario: not-observed-in-window

description: >
  OrderService declares a call to ProductService GET /products/{id}. A matching runtime observation
  exists outside the selected evaluation window, so the dependency remains a declared canonical
  fact but is NOT_OBSERVED_IN_WINDOW for this observation context.

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
      status: NOT_OBSERVED_IN_WINDOW
      evidence:
        declared: true
        observed: false

forbidden:
  relations: []
```

---

### 8.4 Runtime Fixture

The scenario SHOULD use the real OTLP ingestion path.

The fixture contains a normal matched HTTP CLIENT/SERVER observation for the declared route, but
with a timestamp before the window.

This is preferable to having no telemetry at all because it discriminates between:

```text
"no observation exists anywhere"
```

and:

```text
"an observation exists, but not in this observation context"
```

without introducing I4 coverage assertions.

---

### 8.5 Sanity-Break Test

A focused integration regression test SHOULD prove that the window actually matters.

If the same scenario is evaluated with a window that includes the synthetic observation:

```text
09:00Z .. 10:00Z
```

AIP should classify the relation as:

```text
CONFIRMED
```

Therefore the original `NOT_OBSERVED_IN_WINDOW` expectation would no longer pass.

This prevents a projector implementation that simply treats "any historical OBSERVED evidence" as
confirmation.

---

### 8.6 Acceptance

```text
CALLS fact exists
status = NOT_OBSERVED_IN_WINDOW
declared evidence expectation = true
observed evidence in selected context = false
fact is not reported missing
fact is not reported forbidden
no other in-scope fact exists
```

---

## 9. Evidence Reconciliation Input Convention

### 9.1 Why a Second Input Phase Is Required

Evidence reconciliation cannot be demonstrated from a single static declaration import.

The behavior under test is sequential:

```text
declare relation
    |
observe relation
    |
re-import declaration without relation
    |
verify observed evidence survives
```

I3 therefore adds exactly one narrowly scoped optional input phase.

---

### 9.2 Directory Shape

A reconciliation scenario MAY contain:

```text
input/
├── declarations/
│   ├── order-service/
│   │   └── architecture.yaml
│   └── product-service/
│       └── openapi.yaml
├── telemetry/
│   └── spans.py
└── reconciliation/
    └── declarations/
        └── order-service/
            └── architecture.yaml
```

Meaning:

```text
input/declarations/
    = initial declared architecture

input/telemetry/
    = runtime observations after the initial declaration

input/reconciliation/declarations/
    = declaration state re-imported after telemetry
```

The final `expected.yaml` remains the single ground-truth file.

---

### 9.3 No Generic Phase DSL

I3 SHALL NOT add structures such as:

```yaml
steps:
  - import: ...
  - observe: ...
  - remove: ...
  - assert: ...
```

or:

```yaml
workflow:
actions:
phases:
checkpoints:
```

The one optional reconciliation directory is sufficient for the concrete semantic case being tested.

If future work needs a materially different sequence, it SHALL be justified separately rather than
generalizing I3 into a scenario execution framework.

---

## 10. Runner Extension

### 10.1 Normal Scenario Sequence

Existing scenarios remain:

```text
reset graph
    |
ingest input/declarations
    |
inject input/telemetry
    |
project
    |
compare
```

---

### 10.2 Reconciliation Scenario Sequence

When:

```text
input/reconciliation/declarations/
```

exists and contains declarations, the runner SHALL execute:

```text
reset graph
    |
ingest initial declarations
    |
inject runtime fixture
    |
re-import reconciliation declarations
    |
project final canonical facts
    |
compare with expected.yaml
```

The re-import MUST use the real existing declaration import/reconciliation path.

No evaluation-only graph mutation is allowed to remove evidence or relationships.

In particular, the runner MUST NOT perform:

```cypher
DELETE relation
REMOVE evidence id
```

to simulate reconciliation.

The production importer must cause the transition.

---

### 10.3 Reconciliation Input Validation

The runner SHOULD treat an existing but empty reconciliation declaration directory as an invalid or
ineffective fixture rather than silently pretending a re-import occurred.

A reconciliation fixture SHOULD contain a real declaration for the same source service whose
previous declaration is being superseded.

Example final caller manifest:

```yaml
service: order-service
calls: []
```

This allows the production importer to identify `order-service` as the re-imported source and expire
only stale declaration evidence owned by that source.

---

## 11. Scenario 08 — Evidence Reconciliation

### 11.1 Purpose

Prove the core evidence-preservation invariant:

```text
DECLARED + OBSERVED
        |
remove stale DECLARED support
        v
OBSERVED remains
        |
        v
fact survives
        |
        v
status = OBSERVED_ONLY
```

---

### 11.2 Initial State

Initial declarations define:

```text
OrderService
    |
    | CALLS
    v
ProductService.GET /products/{id}
```

The static OTLP fixture observes the same call inside:

```text
environment = test
window      = 2026-08-01T10:00:00Z .. 11:00:00Z
```

Before the reconciliation re-import, AIP must be capable of classifying the relation as:

```text
CONFIRMED
declared = true
observed = true
```

---

### 11.3 Reconciliation State

The reconciliation declaration re-imports `order-service` without the `CALLS` declaration.

The ProductService operation declaration may remain unchanged in the graph.

The production reconciliation code must:

```text
remove the stale DECLARED evidence supporting CALLS
preserve the OBSERVED evidence supporting CALLS
preserve the CALLS relation itself
```

---

### 11.4 Final Ground Truth

Recommended `expected.yaml`:

```yaml
scenario: evidence-reconciliation

description: >
  OrderService initially declares and observes a call to ProductService GET /products/{id}. The
  OrderService declaration is then re-imported without that CALLS relation. The stale declared
  evidence must disappear, the observed evidence must survive, the canonical fact must remain, and
  its final status must be OBSERVED_ONLY.

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
      status: OBSERVED_ONLY
      evidence:
        declared: false
        observed: true

forbidden:
  relations: []
```

---

### 11.5 What This Final Assertion Proves

The final expectation simultaneously verifies:

```text
fact identity still exists
    -> relation was not deleted

declared=false
    -> stale declared support was removed

observed=true
    -> runtime support survived reconciliation

status=OBSERVED_ONLY
    -> AIP reclassified using the surviving evidence
```

No stable evidence-id field is required in `expected.yaml` for I3.

The existing declared/observed booleans are sufficient for the release-level semantic assertion.

---

### 11.6 Transition Regression Test

Because the final scenario evaluates the post-reconciliation state, I3 SHOULD add one focused
integration test that explicitly checks the transition:

```text
after initial declaration + telemetry:
    CONFIRMED

after reconciliation declaration:
    OBSERVED_ONLY
```

This test SHALL call the same projector/runtime analysis used by the evaluator and SHALL NOT
implement its own status derivation.

The purpose is to prove the transition itself, while `expected.yaml` remains a single final-state
oracle rather than becoming a checkpoint DSL.

---

### 11.7 Sanity-Break Test

A useful discriminating control is:

```text
omit the reconciliation re-import
    -> actual remains CONFIRMED
    -> final OBSERVED_ONLY expectation must fail
```

This test proves the new reconciliation phase is causally relevant to the scenario result.

---

## 12. Evidence-Preservation Assertions

### 12.1 Required Semantic Assertion

I3 requires semantic preservation, not persistence-shape duplication.

Required:

```text
expected relation exists
declared=false
observed=true
status=OBSERVED_ONLY
```

Not required in ground truth:

```text
exact Evidence node count
exact evidence_ids ordering
exact sample_trace_ids
exact observation_count
raw Cypher row shape
```

---

### 12.2 Optional Lower-Level Regression Assertion

A targeted integration test MAY additionally verify the persisted invariant through the existing
graph/evidence boundary:

```text
the relation still has at least one evidence id
no stale declared evidence id remains for the re-imported source
at least one OBSERVED Evidence node still supports the relation
```

Such a test is implementation-level protection.

It MUST NOT become the semantic contract of `expected.yaml`.

---

## 13. Observation Window Rules

For any I3 scenario using runtime status:

```text
environment is required
window.start is required
window.end is required
```

The fixture timestamps SHALL be fixed UTC timestamps.

No scenario may depend on:

```text
datetime.now()
current wall-clock time
CI runner timezone
host timezone
```

The runner SHALL continue to pass explicit `since` / `until` values to the projector.

---

## 14. Evaluation-State Isolation

I3 keeps the existing clean-state rule:

```text
scenario start
    -> reset graph
```

The optional reconciliation re-import occurs **inside the same scenario state** after initial
declaration and runtime ingestion.

It MUST NOT trigger a graph reset between the initial and reconciliation imports, because doing so
would destroy the evidence whose survival is being tested.

Correct:

```text
reset
initial declaration
runtime observation
reconciliation declaration
assert
```

Incorrect:

```text
reset
initial declaration
runtime observation
reset              # destroys the state under test
reconciliation declaration
assert
```

---

## 15. Canonical Fact Access

The I1/I2 projection rules remain binding:

```text
canonical semantics
    != Neo4j row shape
```

For `NOT_OBSERVED_IN_WINDOW`, the projector SHOULD continue using the same narrow read-only approach
already established by I2:

```text
production AIP evidence guard predicates
    |
exact canonical (type, source, target)
    |
RelationFact
```

Using `app.analysis.runtime.declared_only_relations()` directly is not required because its
human-readable `CALLS` result intentionally coalesces a target operation toward its provider service,
while the evaluator contract requires the raw canonical Operation target.

The evaluator may therefore reuse the production predicates while preserving exact canonical
identity, just as I2 already does for `CONFIRMED` and `OBSERVED_ONLY`.

---

## 16. Reporting

I3 introduces no new failure class or numeric metric.

The human-readable report SHOULD update its iteration banner and scenario count:

```text
AIP Evaluation — I3

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed
[PASS] 04-orphan-messaging
[PASS] 05-mixed-rest-async
[PASS] 06-request-response-queue-pair
[PASS] 07-not-observed-in-window
[PASS] 08-evidence-reconciliation

Scenarios:          8
Passed:             8
Failed:             0

Missing facts:      0
Unexpected facts:   0
Forbidden facts present: 0
Wrong statuses:     0
Evidence errors:    0

RESULT: PASS
```

An incorrect I3 status or evidence state continues to use the existing detailed mismatch rendering.

Example:

```text
Expected:
  CALLS
  service:order-service
    -> operation:service:product-service:GET:/products/{id}
  status: NOT_OBSERVED_IN_WINDOW
  evidence: declared=true observed=false

Actual:
  status: CONFIRMED
  evidence: declared=true observed=true

Reason:
  wrong status
  unexpected observed evidence
```

---

## 17. Tests

### 17.1 Unit Tests

I3 SHOULD add/adjust focused unit tests for:

```text
projector query construction / classification branch includes NOT_OBSERVED_IN_WINDOW
classification helper can represent declared=true / observed=false
existing CONFIRMED behavior unchanged
existing OBSERVED_ONLY behavior unchanged
normal scenarios without reconciliation input remain unchanged
reconciliation directory detection is deterministic
```

The loader requires no new YAML status derivation logic.

---

### 17.2 Integration Tests

Required integration coverage:

```text
07-not-observed-in-window passes end-to-end
08-evidence-reconciliation passes end-to-end
07 window sanity-break proves an in-window observation becomes CONFIRMED
08 transition test proves CONFIRMED -> OBSERVED_ONLY
08 sanity-break without re-import does not satisfy final OBSERVED_ONLY expectation
all six I1/I2 scenarios still pass
```

The existing shared session-scoped Neo4j Testcontainer infrastructure may be reused.

No new integration-test container architecture is required by I3.

---

## 18. Implementation Tasks

A practical task-per-PR breakdown is:

### Task I3.1 — `NOT_OBSERVED_IN_WINDOW`

Deliver:

```text
projector.py:
    reuse _NOT_OBSERVED_EXISTS / NOT_OBSERVED_IN_WINDOW
    support explicit declared/observed output flags
    add third status branch for CALLS/SENDS/RECEIVES_FROM

07-not-observed-in-window:
    declarations
    out-of-window OTLP fixture
    expected.yaml

tests:
    end-to-end scenario
    window sanity-break
```

Exit condition:

```text
07 passes as NOT_OBSERVED_IN_WINDOW
same observation becomes CONFIRMED when evaluated inside its time window
existing six scenarios remain green
```

---

### Task I3.2 — Evidence Reconciliation

Deliver:

```text
runner.py:
    recognize optional input/reconciliation/declarations/
    re-import after telemetry and before projection

08-evidence-reconciliation:
    initial declarations
    in-window OTLP fixture
    reconciliation declaration
    final expected.yaml

tests:
    final scenario pass
    explicit CONFIRMED -> OBSERVED_ONLY transition regression
    optional no-reimport sanity-break
```

Exit condition:

```text
fact survives stale declaration removal
declared evidence disappears
observed evidence survives
final status = OBSERVED_ONLY
```

---

### Task I3.3 — Documentation and Release Qualification

Deliver:

```text
reporter.py:
    I3 banner

evaluation/README.md:
    document scenarios 07 and 08
    document NOT_OBSERVED_IN_WINDOW
    document reconciliation input convention
    explain context-qualified observed evidence

docs/specifications/0.2.0/README.md:
    add i3-evidence-runtime-semantics.md
    mark I2 shipped
    mark I3 implementation complete / tag pending when appropriate
```

Exit condition:

```text
8/8 deterministic scenarios pass
unit/integration suites green
ruff check / format clean
CI and CodeQL green
Definition of Done satisfied
```

---

## 19. Definition of Done

Iteration 3 is complete when all of the following are true:

- [ ] The evaluator projects `NOT_OBSERVED_IN_WINDOW` from existing AIP runtime semantics.
- [ ] The evaluator does not derive actual status in Python from evidence booleans.
- [ ] Exact `(type, source, target)` identity remains preserved.
- [ ] `07-not-observed-in-window` passes.
- [ ] Scenario 07 contains an observation outside the selected window.
- [ ] Scenario 07 proves that the declared relation remains present.
- [ ] Scenario 07 expects `declared=true`, `observed=false`, and
      `status=NOT_OBSERVED_IN_WINDOW`.
- [ ] A regression test demonstrates that including the observation in the selected window changes
      the AIP classification to `CONFIRMED`.
- [ ] The runner supports exactly one optional reconciliation declaration phase without introducing
      a general workflow DSL.
- [ ] The reconciliation phase uses the real declaration importer/reconciliation path.
- [ ] `08-evidence-reconciliation` passes.
- [ ] Scenario 08 begins with declared and observed support for the same relation.
- [ ] Scenario 08 re-imports the declaring service without that relation.
- [ ] The relation survives the re-import.
- [ ] Stale declared evidence is absent after reconciliation.
- [ ] Observed evidence remains after reconciliation.
- [ ] Final status is `OBSERVED_ONLY`.
- [ ] A regression test proves the transition `CONFIRMED -> OBSERVED_ONLY`.
- [ ] Existing `MISSING`, `SEMANTIC_MISMATCH`, `FORBIDDEN_PRESENT`, and `UNEXPECTED` behavior remains
      unchanged.
- [ ] All six I1/I2 scenarios still pass unchanged.
- [ ] The full evaluation suite passes 8/8.
- [ ] The suite still runs without an LLM API key.
- [ ] Existing unit/integration tests remain green.
- [ ] CI and CodeQL are green.
- [ ] No new canonical model concept is introduced.
- [ ] Coverage qualification and partial-observation semantics remain deferred to I4.

---

## 20. Alpha.3 Release Criteria

`v0.2.0-alpha.3` may be cut when:

```text
Scenarios:        8
Passed:           8
Failed:           0

Critical semantic errors: 0
```

and a clean checkout reproduces the result.

The tag SHALL be created only after:

```text
implementation PRs merged
    |
main CI green
    |
local main updated
    |
evaluation 8/8 green
    |
unit/integration suites green
    |
tag v0.2.0-alpha.3
```

The meaning of the release is:

> **AIP's evaluation suite now verifies the full core declared/observed status model and proves that
> architecture facts survive declaration reconciliation whenever independent observed evidence still
> supports them.**

---

## 21. Critical Semantic Errors for I3

The following are release-blocking:

```text
declared + unobserved-in-context relation classified as CONFIRMED
declared + unobserved-in-context relation omitted from the scenario
NOT_OBSERVED_IN_WINDOW interpreted as absence
historical/out-of-window evidence incorrectly treated as in-window confirmation
stale declaration reconciliation removes surviving OBSERVED evidence
fact deleted while OBSERVED evidence remains
stale DECLARED evidence survives when its source no longer declares the relation
post-reconciliation relation remains CONFIRMED instead of OBSERVED_ONLY
reconciliation implemented by evaluation-only graph mutation
evaluator independently re-derives AIP status semantics
```

Target:

```text
Critical semantic errors = 0
```

---

## 22. Expected Follow-Up in I4

Iteration 4 builds on I3 rather than expanding I3's scope.

Expected I4 work:

```text
partial-observation scenario
coverage qualification / hardening
declared-only scenario if selected to complete target scenario count
DLQ directionality if inexpensive
cross-batch HTTP correlation only if low-cost
schema/error-report hardening
stable output ordering / reproducibility checks
```

The main boundary is:

```text
I3:
    Does the evidence/status model behave correctly?

I4:
    How well is non-observation qualified and how robust is the suite at release-candidate level?
```

---

## 23. Summary

I3 adds no new architecture concept.

It verifies two existing invariants that are central to trusting AIP runtime intelligence:

```text
1. absence of matching telemetry in a selected context
   does not erase a declared architecture fact

2. removal of declaration evidence
   does not erase independent runtime evidence
```

The two new scenarios make those statements executable:

```text
07-not-observed-in-window
    D + no O(window) -> NOT_OBSERVED_IN_WINDOW

08-evidence-reconciliation
    D + O -> CONFIRMED
    remove D
    O survives
    fact survives
    -> OBSERVED_ONLY
```

The governing principle remains unchanged:

> **The evaluator observes AIP semantics; it does not become a second implementation of them.**
