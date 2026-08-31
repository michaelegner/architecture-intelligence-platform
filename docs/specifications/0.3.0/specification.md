# AIP v0.3.0 Specification — Real-World Validation & Model Hardening

**Status:** Final  
**Target release:** `v0.3.0`  
**Project:** Architecture Intelligence Platform (AIP)  
**Predecessor:** `v0.2.0` — Deterministic Evaluation Suite

---

## 1. Purpose

AIP `v0.1.x` established evidence-backed architecture intelligence from declared architecture
sources and runtime observations.

AIP `v0.2.0` made those semantics reproducibly testable against independently authored synthetic
ground truth.

The purpose of `v0.3.0` is to validate whether the current AIP architecture model remains correct
when applied to independently authored external systems that were not designed for AIP.

The release identity is:

```text
v0.1
architecture intelligence exists

v0.2
architecture intelligence is reproducibly verified

v0.3
architecture intelligence survives real systems
```

The central question is:

> **Does AIP's current Canonical Architecture Model remain materially correct when confronted with
> independently authored real systems, without modifying those systems or their expected
> architecture to fit AIP?**

The intended progression is:

```text
Synthetic correctness
        |
        v
External reference validation
        |
        v
Real-world software validation
        |
        v
Model hardening
        |
        v
Revalidation
```

This release validates the core before later releases expose it through a broader public tool
contract or populate it from additional discovery sources.

---

## 2. Release Statement

AIP `v0.3.0` SHALL validate the current architecture-intelligence core against two independently
authored systems:

```text
External Reference Architecture
    Quarkus Super Heroes

Real-World OSS Software
    Apache Airflow
```

The release SHALL:

1. pin an exact upstream version of each validation system,
2. define a bounded and reproducible validation profile for each system,
3. establish expected architecture facts independently of AIP output,
4. run AIP against the selected profiles without introducing AIP-specific architecture changes,
5. classify all material findings using a fixed vocabulary,
6. correct genuine general AIP defects exposed by the validation,
7. document unsupported architecture semantics explicitly rather than approximating them
   incorrectly,
8. add deterministic regression coverage for every accepted model-hardening change,
9. re-run both synthetic and real-system validation after hardening,
10. publish the validation evidence and known limitations with the release.

The release SHALL NOT claim that AIP understands every mechanism used by either external system.

---

## 3. Roadmap Position

The intended pre-1.0 sequence is:

```text
v0.1  Architecture Intelligence
v0.2  Deterministic Evaluation
v0.3  Real-World Validation & Model Hardening
v0.4  Architecture Intelligence Tools
v0.5  Broader Architecture Discovery
v0.9  Contract Freeze / Production Qualification
v1.0  Stable Architecture Intelligence Platform
```

The sequence is deliberate:

```text
Build
  ->
Prove
  ->
Validate against reality
  ->
Expose as a public machine-consumable contract
  ->
Broaden discovery
  ->
Freeze
```

AIP SHOULD validate the semantic core before creating a broader public tool/MCP contract around it,
and before adding more discovery adapters that would increase the cost of later semantic changes.

---

## 4. Why Validation Precedes Public Tool Contracts and Broader Discovery

Without real-world validation, a later model correction could affect all of:

```text
Canonical Model
OpenAPI adapter
AsyncAPI adapter
OpenTelemetry resolution
runtime analysis
future Kubernetes adapter
future MCP/tool contracts
evaluation
documentation
```

The preferred dependency order is therefore:

```text
current core
    |
    v
real systems
    |
    v
discover model weaknesses
    |
    v
fix or explicitly mark unsupported
    |
    v
expose and expand
```

Formally:

```text
ValidateCore -> HardenCore -> ExposeCore -> ExpandDiscovery
```

`v0.3.0` is the validation-and-hardening stage.

---

## 5. Validation Systems

### 5.1 System A — Quarkus Super Heroes

Role:

```text
External Reference Architecture
```

Purpose:

- validate AIP against a non-AIP microservice system,
- exercise official OpenAPI-described REST endpoints,
- exercise real service-to-service REST communication,
- exercise asynchronous messaging,
- exercise mixed synchronous and asynchronous communication,
- exercise OpenTelemetry runtime observations,
- validate canonical service and operation identity across independent upstream artifacts,
- verify that unsupported protocols remain explicitly unsupported.

Quarkus Super Heroes is a controlled external architecture reference.

It SHALL NOT be described as production software.

---

### 5.2 System B — Apache Airflow

Role:

```text
Real-World OSS Software
```

Purpose:

- validate AIP against mature real-world software,
- stress logical `Service` identity,
- validate REST provider discovery,
- validate scheduler/worker/broker interaction where it intersects AIP's supported semantics,
- exercise a real asynchronous task-execution topology,
- exercise OpenTelemetry runtime behavior,
- reveal differences between runtime-process identity and logical architecture identity,
- identify where the current queue-centric model is sufficient or insufficient.

Airflow is the primary model-validity stress test.

---

## 6. Core Methodological Rule

The most important v0.3 invariant is:

```text
AIP Input != AIP Expected Output
```

and:

```text
AIP Output MUST NOT define Ground Truth
```

The following workflow is prohibited:

```text
run AIP
   |
   v
AIP says X
   |
   v
inspect source until X appears plausible
   |
   v
declare X expected
```

The required workflow is:

```text
official upstream contracts
official architecture documentation
upstream configuration
upstream source where necessary
independent runtime evidence
        |
        v
independent architecture dossier
        |
        v
freeze expected supported facts
        |
        v
run AIP
        |
        v
compare
```

Ground truth SHALL be frozen before the qualifying AIP comparison run.

---

## 7. Independent Ground-Truth Sources

Ground truth SHOULD use the strongest available independent evidence in this order:

```text
1. official machine-readable contracts
2. official architecture documentation
3. official deployment/runtime configuration
4. upstream source code
5. independently captured runtime evidence
```

Examples:

```text
OpenAPI
official service diagrams
broker/executor configuration
source showing producer/consumer behavior
raw or independently inspected OTLP traces
```

The following SHALL NOT be used as primary ground-truth sources:

```text
AIP graph output
AIP REST analysis responses
AIP-generated Cypher results
AIP evaluation projections
AIP-generated expected files
```

---

## 8. Upstream Version Pinning

Each validation system SHALL be pinned to an exact upstream identity.

The validation dossier SHALL record:

```text
repository
release/tag if available
exact commit SHA
validation date
local deployment profile
required upstream configuration
instrumentation additions, if any
```

Validation results apply only to the pinned upstream state.

Changing the upstream revision requires revalidation.

---

## 9. Bounded Validation Profiles

The release SHALL NOT attempt to validate every upstream feature.

Each system SHALL define a bounded profile that states:

```text
which services/processes are started
which broker/executor configuration is used
which architecture flows are exercised
which telemetry is enabled
which upstream features are intentionally out of scope
which AIP semantics are expected to apply
```

The profile SHALL be reproducible.

The profile SHALL be broad enough to challenge AIP's current semantics, but small enough to run
repeatably during release qualification.

---

## 10. Allowed Instrumentation Changes

Standard observability configuration MAY be added to expose existing runtime behavior.

Acceptable examples:

```text
enable native OpenTelemetry export
configure OTLP endpoint
configure an OpenTelemetry Collector
add standard OpenTelemetry agent/instrumentation
enable existing tracing configuration
```

These changes SHALL NOT alter the logical architecture being validated.

The following are prohibited:

```text
adding an AIP-specific architecture manifest after inspecting AIP output
rewriting service identities solely to satisfy AIP resolution
rewriting messaging topology to fit AIP Queue semantics
creating declarations only to turn OBSERVED_ONLY into CONFIRMED
changing upstream architecture until AIP passes
```

The external system is the subject of validation, not a fixture to be modified until it matches AIP.

---

## 11. Supported Scope Versus Complete Architecture

Real-system validation SHALL distinguish:

```text
complete upstream architecture
        !=
AIP-supported semantic scope
```

AIP is not required to model every mechanism present in either validation system.

A mechanism may legitimately be classified as:

```text
UNSUPPORTED
```

provided AIP does not silently convert it into a semantically incorrect supported fact.

The release principle is:

```text
Explicitly unsupported
    >
Incorrectly represented as supported
```

---

## 12. Finding Vocabulary

All material findings SHALL use the following classifications.

### 12.1 `CORRECT`

A supported expected fact is represented correctly by AIP.

Examples:

```text
correct canonical identity
correct relation type
correct direction
correct runtime status
correct evidence linkage
```

---

### 12.2 `MISSING_SUPPORTED`

Independent ground truth establishes a fact inside AIP's claimed supported scope, but AIP does not
represent it.

This is a false negative.

---

### 12.3 `INCORRECT_SUPPORTED`

AIP emits a supported architecture claim that contradicts independent ground truth.

Examples:

```text
invented relation
wrong relation direction
wrong target operation
wrong sender or consumer
wrong runtime status
incorrect evidence attribution
```

This is a false positive or semantic defect.

This classification is release-critical when material.

---

### 12.4 `UNSUPPORTED`

The upstream system uses a mechanism outside AIP's current supported semantic scope.

Examples may include:

```text
gRPC before a gRPC adapter exists
topic/subscription semantics that cannot safely map to Queue
deployment/process relationships outside the current Canonical Model
```

Unsupported behavior SHALL be documented.

AIP SHALL NOT fabricate an approximate supported relation to increase apparent coverage.

---

### 12.5 `UNRESOLVED_IDENTITY`

Independent evidence suggests that architecture entities correspond, but AIP cannot safely resolve
their canonical identity.

Examples:

```text
runtime process name cannot be mapped safely to a logical service
multiple runtime instances map ambiguously to one logical entity
operation identity cannot be resolved without guessing
```

AIP SHALL prefer unresolved identity over heuristic invention.

---

### 12.6 `INSUFFICIENT_EVIDENCE`

The validation dossier itself cannot establish the fact strongly enough to use it as expected
ground truth.

This is not an AIP failure.

The item remains outside the qualifying expected set until independent evidence is sufficient.

---

## 13. No Composite Accuracy Score

`v0.3.0` SHALL NOT introduce a weighted architecture-intelligence score.

The validation SHALL report concrete counts:

```text
expected supported facts
correct
missing supported
incorrect supported
unsupported constructs
unresolved identities
insufficient-evidence items
```

Percentages MAY be reported for readability.

No aggregate score is normative.

The goal is semantic diagnosis, not benchmark optimization.

---

## 14. Validation Dossier

Each system SHALL have a committed validation dossier.

Recommended structure:

```text
docs/real-world-validation/
├── README.md
│
├── quarkus-super-heroes/
│   ├── upstream.md
│   ├── profile.md
│   ├── ground-truth.md
│   ├── expected.yaml
│   ├── runbook.md
│   ├── results.md
│   └── findings.md
│
└── apache-airflow/
    ├── upstream.md
    ├── profile.md
    ├── ground-truth.md
    ├── expected.yaml
    ├── runbook.md
    ├── results.md
    └── findings.md
```

Exact filenames MAY differ.

The separation between:

```text
upstream identity
validation profile
independent ground truth
AIP results
findings
```

SHALL remain.

---

## 15. Real-System Expectation Format

A lightweight semantic YAML format MAY be used.

Example:

```yaml
system: quarkus-super-heroes
upstream_revision: "<pinned-sha>"

scope:
  entities:
    - service:rest-fights
    - service:rest-heroes
  relation_types:
    - CALLS
    - PROVIDES

expected:
  relations:
    - type: CALLS
      source: service:rest-fights
      target: operation:service:rest-heroes:GET:/api/heroes

unsupported:
  - mechanism: grpc
    description: >
      Present upstream but outside the current AIP supported scope.
```

The format SHALL remain declarative.

It SHALL NOT become a generic policy engine or rule language.

---

## 16. Comparison Semantics

The comparison SHALL evaluate:

```text
ExpectedSupported
        vs
ActualAIPSupported
```

while separately recording:

```text
Unsupported
UnresolvedIdentity
InsufficientEvidence
```

The comparator SHALL NOT:

```text
derive ground truth
repair AIP output
invent canonical identities
convert unsupported mechanisms into expected facts
```

The comparison output SHALL be deterministic.

---

## 17. Quarkus Super Heroes — Mandatory Scope

The exact upstream revision and identifiers SHALL be fixed in the I2 implementation specification.

The mandatory validation profile SHALL include:

```text
multiple logical services
official OpenAPI provider declarations
at least three real inter-service REST interactions
asynchronous messaging
at least one producer
at least one consumer
mixed synchronous + asynchronous behavior
OpenTelemetry runtime traces
```

Candidate architecture flows MAY include:

```text
rest-fights -> rest-heroes
rest-fights -> rest-villains
rest-fights -> rest-narration
rest-fights -> messaging destination
messaging destination -> event-statistics
```

Exact operation and destination identifiers SHALL be taken from the pinned upstream source.

If gRPC exists in the selected profile and AIP has no gRPC semantics, it SHALL be recorded as
unsupported.

---

## 18. Quarkus Validation Questions

The Quarkus validation SHALL answer at least:

```text
Does OpenAPI ingestion create the expected PROVIDES facts?

Does runtime telemetry resolve expected REST CALLS?

Are relation directions correct?

Does mixed REST + messaging remain semantically distinct?

Does AIP preserve declared versus observed evidence?

Does messaging produce correct SENDS / RECEIVES_FROM facts
for the subset compatible with the current Queue model?

Are unsupported protocols left unsupported rather than misrepresented?

Do service identities remain stable across OpenAPI and OTLP?
```

---

## 19. Apache Airflow — Mandatory Scope

The exact deployment profile SHALL be fixed in the I3 implementation specification.

The selected profile SHOULD include:

```text
stable/public REST API
CeleryExecutor
one documented supported broker configuration
scheduler
one or more workers
metadata database
OpenTelemetry tracing
```

The purpose is not to validate every executor or Airflow feature.

The profile SHALL be reproducible locally.

---

## 20. Airflow Validation Questions

The Airflow validation SHALL answer at least:

```text
What is the correct logical Service boundary for AIP?

Can REST PROVIDES facts be mapped without confusing runtime process identity
with logical architecture identity?

How do API server, scheduler, worker, and broker identities appear in telemetry?

Can supported Celery/broker interactions be represented without guessing?

Can multiple runtime instances map safely to one logical service?

Do process names accidentally create false logical services?

Where is the current Queue model sufficient?

Where is the current Queue model insufficient?

Does runtime non-observation remain correctly qualified?

Does the current Canonical Model require a fundamental redesign?
```

---

## 21. Airflow as a Model Stress Test

Airflow SHALL NOT be simplified merely to resemble a standard microservice demo.

Its value is that it challenges assumptions such as:

```text
one runtime process == one logical Service
one HTTP server == one architectural Service
one worker == one Service
all asynchronous communication == Queue semantics
```

Where these assumptions fail, the validation SHALL document the mismatch before deciding whether AIP
should change.

---

## 22. Model-Hardening Decision Records

Every material finding that may change AIP semantics SHALL receive a decision record.

Recommended fields:

```text
finding id
system
independent evidence
current AIP behavior
classification
impact
decision
canonical-model impact
compatibility impact
implementation change
regression coverage
```

Allowed decisions:

```text
FIX
DOCUMENT_UNSUPPORTED
DEFER
NO_CHANGE
```

A finding SHALL NOT trigger a model change merely because a richer model is conceivable.

---

## 23. Model-Hardening Rule

A canonical or semantic change is justified only when all of the following are true:

1. independent real-system evidence demonstrates the problem,
2. the current AIP behavior is materially incorrect or blocks an important supported use case,
3. the proposed correction is general rather than system-specific,
4. the corrected semantic can be stated precisely,
5. deterministic regression coverage can be added.

Preferred decision order:

```text
incorrect supported behavior
    -> FIX

unsupported but safely explicit
    -> DOCUMENT_UNSUPPORTED

interesting future capability
    -> DEFER
```

---

## 24. No System-Specific Production Hacks

The following are prohibited:

```text
if system == "airflow": ...
if service name == "rest-fights": ...
hard-coded upstream endpoint IDs in production resolver logic
hard-coded topic/queue names in production semantics
validation-only graph repair
post-processing AIP output until it matches expected.yaml
```

Hardening SHALL improve general AIP semantics.

---

## 25. Identity Resolution

Identity resolution is a primary v0.3 concern.

AIP MAY harden:

```text
service identity normalization
runtime-to-logical-service mapping
operation resolution
messaging destination resolution
evidence correlation
```

when justified by validation findings.

The rule remains:

```text
unresolved
    >
guessed
```

AIP SHALL NOT invent canonical identity merely to improve apparent coverage.

---

## 26. Messaging Model Boundary

The current AIP messaging model is queue-centric.

Real systems may expose topic/fan-out semantics that cannot safely be represented as competing
queue consumers.

The rule is:

```text
Queue semantics SHALL NOT be stretched to represent Topic semantics incorrectly.
```

If a qualifying system exposes an important semantic that cannot be represented, the model-hardening
process SHALL decide whether to:

```text
extend the model in v0.3
or
document the mechanism as unsupported and defer it
```

A full messaging-model redesign is not automatically required for release.

---

## 27. Runtime Coverage Semantics

Existing runtime semantics remain normative:

```text
NOT_OBSERVED_IN_WINDOW != architecture absence
```

Real-system observations SHALL remain qualified by:

```text
environment
time window
instrumentation coverage
```

Where only part of the system is instrumented:

```text
ObservedSubset != CompleteSystem
```

AIP SHALL NOT strengthen incomplete telemetry into claims of architectural absence.

---

## 28. False-Positive Priority

v0.3 SHALL prioritize correctness over apparent completeness.

Priority order:

```text
1. eliminate invented or semantically wrong supported facts
2. eliminate wrong direction, status, identity, and evidence
3. improve missing supported facts
4. document unsupported architecture
5. broaden coverage in later releases
```

The governing principle is:

```text
correct but incomplete
    >
complete-looking but wrong
```

---

## 29. Mandatory Release Gates

`v0.3.0` SHALL NOT ship with unresolved critical supported-semantic defects inside the qualifying
scope.

Mandatory gates:

```text
Quarkus validation completed
Airflow validation completed

critical INCORRECT_SUPPORTED findings = 0

no known invented supported relation
no known wrong relation direction
no known wrong runtime status
no known fabricated or lost evidence
no unsupported mechanism silently represented as supported

all accepted model-hardening fixes have deterministic regression coverage
all material findings have explicit dispositions
synthetic deterministic evaluation remains green
```

---

## 30. Coverage Is Not Required to Be Complete

The release does NOT require:

```text
100% of Quarkus architecture modeled
100% of Airflow architecture modeled
all protocols supported
all runtime interactions observed
all identities resolvable
```

A successful release means:

```text
supported claims are materially correct
unsupported semantics remain explicit
evidence remains traceable
runtime non-observation remains correctly qualified
known limitations are documented
```

---

## 31. Fundamental-Redesign Gate

Before moving from v0.3 to v0.4:

> **No unresolved real-world finding may indicate that the current Canonical Architecture Model
> requires a fundamental breaking redesign before AIP exposes that model through a broader
> machine-consumable contract.**

If such a finding exists:

```text
v0.3 = NO-GO
```

until either:

```text
the model is corrected
```

or:

```text
the affected semantic claim is deliberately removed from supported scope
```

This is the primary reason v0.3 precedes Architecture Intelligence Tools.

---

## 32. Regression Strategy

Every accepted hardening change SHALL add deterministic regression coverage.

Preferred layers:

```text
unit test
integration test
small distilled regression fixture
```

The complete external upstream projects SHALL NOT be required in every normal test run.

Real-system validation remains a separate qualification path.

---

## 33. Relationship to v0.2 Evaluation

The v0.2 deterministic suite remains the synthetic regression baseline.

Target:

```text
v0.2 core evaluation
    10/10 PASS
```

If a justified v0.3 correction intentionally changes a semantic represented by a v0.2 scenario, the
change SHALL:

```text
be documented explicitly
explain why the previous behavior was incorrect
update the versioned expectation deliberately
add regression coverage
appear in release notes
```

Silent weakening of v0.2 expectations is prohibited.

---

## 34. Real-System Validation Runner

v0.3 MAY provide a small helper runner for reproducibility.

Example:

```bash
uv run python -m real_world_validation quarkus-super-heroes
uv run python -m real_world_validation apache-airflow
```

The runner MAY:

```text
load frozen supported expectations
query or load AIP facts
normalize deterministic identifiers
compare expected versus actual
produce deterministic finding categories
```

It SHALL NOT:

```text
infer ground truth
modify expected.yaml
repair AIP output
```

This SHALL remain a focused validation utility, not a generic enterprise policy framework.

---

## 35. Runtime Evidence

A qualifying run MAY use:

```text
live generated telemetry
```

or:

```text
a committed sanitized capture produced from the pinned profile
```

provided the capture:

```text
contains no secrets
contains no personal/customer data
preserves the tested architecture semantics
has documented provenance
```

Where practical, release qualification SHOULD include at least one live run for each system.

---

## 36. Repository and Licensing Hygiene

AIP SHALL NOT vendor entire upstream repositories merely for convenience.

Validation documentation SHALL record:

```text
upstream repository
upstream license
pinned tag/SHA
setup procedure
```

Only minimal derived metadata and legally reusable fixtures SHOULD be committed.

Large upstream source/artifact content SHOULD remain external.

---

## 37. Non-Goals

The following are explicitly outside mandatory `v0.3.0` scope:

```text
Architecture Intelligence Service public contract
MCP server
AI tool interface
GraphRAG
vector database
embeddings
Architecture Copilot
Kubernetes discovery
cloud discovery
Dapr discovery
gRPC/protobuf adapter
Kafka Connect adapter
Backstage integration
Architecture Wiki
architecture mutation
policy engine
multi-agent systems
LLM-as-a-Judge
performance benchmarking
complete upstream-system coverage
production-support certification
1.0 compatibility freeze
```

A capability exposed by a validation finding MAY be proposed for a later release without being
implemented in v0.3.

---

## 38. Iteration Structure

The v0.3 delivery model is:

```text
I1 — Real-World Validation Contract
I2 — Quarkus Super Heroes Validation
I3 — Apache Airflow Validation
I4 — Cross-System Model Hardening
I5 — Release Qualification
```

Suggested release mapping:

```text
I1 -> v0.3.0-alpha.1
I2 -> v0.3.0-alpha.2
I3 -> v0.3.0-alpha.3
I4 -> v0.3.0-rc.1
I5 -> v0.3.0
```

Each iteration SHALL receive a self-contained implementation specification before implementation
begins.

---

## 39. I1 — Real-World Validation Contract

I1 establishes methodology before system-specific qualification.

Mandatory outcomes:

```text
validation directory structure
finding vocabulary
ground-truth source hierarchy
expected.yaml shape
upstream pinning rules
supported/unsupported scope rules
comparison/report format
model-change decision-record format
runbook template
```

I1 SHALL NOT contain expected results derived from an AIP run.

---

## 40. I2 — Quarkus Super Heroes Validation

I2 SHALL:

```text
pin exact upstream revision
define reproducible profile
freeze independent ground truth
exercise selected OpenAPI/REST flows
exercise selected messaging flows
capture/observe OpenTelemetry
run AIP
classify findings
fix only general AIP defects justified by evidence
add regression coverage
publish results dossier
```

Exit condition:

```text
all material Quarkus findings dispositioned
critical INCORRECT_SUPPORTED findings = 0
```

---

## 41. I3 — Apache Airflow Validation

I3 SHALL:

```text
pin exact upstream revision
define reproducible local deployment profile
freeze independent ground truth
exercise stable REST API
exercise selected Celery/broker flow
enable/capture OpenTelemetry
run AIP
classify logical-service/process identity findings
classify messaging findings
classify runtime-coverage findings
fix only general AIP defects justified by evidence
add regression coverage
publish results dossier
```

Exit condition:

```text
all material Airflow findings dispositioned
critical INCORRECT_SUPPORTED findings = 0
```

---

## 42. I4 — Cross-System Model Hardening

I4 reviews findings across both systems and distinguishes:

```text
system-specific curiosity
        vs
general model defect
```

Mandatory outcomes:

```text
all critical findings dispositioned
general model corrections implemented
identity-resolution corrections implemented where justified
runtime/evidence corrections implemented where justified
unsupported semantics documented
distilled regression tests added
Quarkus revalidated
Airflow revalidated
synthetic evaluation revalidated
deterministic validation reports
```

I4 SHALL NOT add unrelated adapter families.

---

## 43. I5 — Release Qualification

I5 introduces no new model semantics.

It SHALL qualify the exact `v0.3.0` candidate.

At minimum:

```text
fresh checkout
locked dependency sync
lint/format
unit tests
integration tests
v0.2 synthetic evaluation
Quarkus validation
Airflow validation
finding/disposition review
known-limitations review
security checks
GO / NO-GO
published artifact verification
```

---

## 44. Final Validation Report

The release SHALL publish a concise summary using actual frozen-scope counts.

Example:

```text
Quarkus Super Heroes
---------------------
Expected supported facts:      N
Correct:                       N
Missing supported:             N
Incorrect supported:           0
Unsupported constructs:        N
Unresolved identities:         N
Critical semantic errors:      0

Apache Airflow
---------------------
Expected supported facts:      N
Correct:                       N
Missing supported:             N
Incorrect supported:           0
Unsupported constructs:        N
Unresolved identities:         N
Critical semantic errors:      0
```

`Missing supported` need not be zero if the remaining gap is non-critical, documented, and explicitly
accepted for release.

`Incorrect supported` SHALL be zero for critical qualifying findings.

---

## 45. Release Definition of Done

`v0.3.0` is complete when all mandatory conditions below are satisfied.

### Validation Method

- [ ] Ground-truth methodology is documented.
- [ ] AIP output is excluded from ground-truth generation.
- [ ] Finding categories are fixed.
- [ ] Upstream versions are pinned.
- [ ] Validation profiles are reproducible.
- [ ] Comparison output is deterministic.

### Quarkus Super Heroes

- [ ] Upstream revision is pinned.
- [ ] Independent ground truth is frozen.
- [ ] OpenAPI/REST scope is validated.
- [ ] Messaging scope is validated.
- [ ] OpenTelemetry/runtime scope is validated.
- [ ] Unsupported mechanisms are explicit.
- [ ] Critical supported-semantic errors = `0`.
- [ ] Results and findings are committed.

### Apache Airflow

- [ ] Upstream revision is pinned.
- [ ] Reproducible deployment profile is documented.
- [ ] Independent ground truth is frozen.
- [ ] REST provider scope is validated.
- [ ] Celery/broker scope is validated.
- [ ] Runtime/logical-service identity behavior is validated.
- [ ] OpenTelemetry/runtime scope is validated.
- [ ] Unsupported mechanisms are explicit.
- [ ] Critical supported-semantic errors = `0`.
- [ ] Results and findings are committed.

### Model Hardening

- [ ] Every material finding has an explicit decision.
- [ ] No system-specific production hack is introduced.
- [ ] Every accepted semantic fix has deterministic regression coverage.
- [ ] No unsupported mechanism is silently represented as supported.
- [ ] No unresolved finding requires a fundamental pre-v0.4 Canonical Model redesign.
- [ ] Known model limitations are documented.

### Regression

- [ ] v0.2 deterministic evaluation is green.
- [ ] Quarkus supported-scope validation is green.
- [ ] Airflow supported-scope validation is green.
- [ ] Unit tests are green.
- [ ] Integration tests are green.
- [ ] Ruff is green.
- [ ] CI is green.
- [ ] CodeQL is green.
- [ ] Dependency audit is green.

### Release

- [ ] Release-validation evidence is committed.
- [ ] Critical semantic errors = `0`.
- [ ] Release blockers = `0`.
- [ ] GO / NO-GO names the exact candidate.
- [ ] `v0.3.0` tag points to the exact approved candidate.
- [ ] Published artifact is verified.

---

## 46. Release Blockers

The following SHALL block `v0.3.0`:

```text
invented supported relation in qualifying scope
wrong relation direction
wrong canonical identity producing a false architecture claim
wrong runtime status
lost or fabricated evidence
unsupported mechanism silently coerced into an incorrect supported relation
ground truth authored from AIP output
unresolved critical Quarkus finding
unresolved critical Airflow finding
system-specific production hack required to pass validation
known fundamental Canonical Model redesign still required before v0.4
nondeterministic qualifying comparison
synthetic regression failure without an explicit approved semantic migration
```

Target:

```text
Critical semantic errors = 0
Release blockers = 0
```

---

## 47. Non-Blocking Findings

The following do not automatically block v0.3:

```text
explicitly unsupported gRPC
explicitly unsupported topic/subscription semantics
unresolved identity where AIP refuses to guess
missing optional architecture outside the frozen scope
incomplete telemetry with correctly qualified coverage
future Kubernetes/deployment-topology needs
future Dapr integration
future broader adapter opportunities
```

These SHALL be documented rather than hidden.

---

## 48. Relationship to v0.4

The expected next release is:

```text
v0.4 — Architecture Intelligence Tools
```

Expected scope:

```text
ArchitectureIntelligenceService
structured evidence-backed result contracts
read-only MCP tools
deterministic tool evaluation
```

The public tool contract SHOULD be defined only after v0.3 demonstrates that the underlying model is
credible against external systems.

---

## 49. Relationship to v0.5

The expected later release is:

```text
v0.5 — Broader Architecture Discovery
```

Candidate areas include:

```text
Kubernetes
additional ArchitectureSourceAdapter families
deeper runtime discovery
gRPC/protobuf
Dapr
Kafka Connect
```

Exact v0.5 scope is outside this specification.

The sequencing rule is:

```text
validate the model first
then add more ways to populate it
```

---

## 50. Relationship to v1.0

Real-world validation is a hard precondition for the eventual 1.0 contract freeze.

AIP SHOULD NOT enter its v0.9 contract-freeze phase unless:

```text
Quarkus external-reference validation is complete
Airflow real-software validation is complete
material false positives are resolved
material false negatives are understood
unsupported semantics are explicit
no fundamental Canonical Model redesign is known to be required
```

This makes v0.3 a foundational release rather than an optional demonstration.

---

## 51. Expected Repository Structure

A possible final structure is:

```text
docs/specifications/0.3.0/
├── README.md
├── specification.md
├── i1-real-world-validation-contract.md
├── i2-quarkus-validation.md
├── i3-airflow-validation.md
├── i4-model-hardening.md
├── i5-release-qualification.md
└── git-workflow.md

docs/real-world-validation/
├── README.md
├── quarkus-super-heroes/
└── apache-airflow/
```

Exact paths are non-normative.

---

## 52. Summary

AIP `v0.3.0` moves the project from controlled semantic verification to real-world model validation.

```text
v0.1
Build architecture intelligence

        |

v0.2
Prove it against synthetic ground truth

        |

v0.3
Challenge it with independently authored systems

        |

v0.4
Expose the hardened intelligence as tools

        |

v0.5
Broaden discovery
```

The defining principle is:

> **Do not make external systems fit AIP. Make AIP prove that its supported semantics fit external
> systems, and explicitly admit where they do not.**

The release succeeds not when AIP recognizes everything, but when:

```text
supported architecture claims are materially correct
unsupported mechanisms remain explicit
evidence remains traceable
runtime absence remains properly qualified
real-world findings do not require an unresolved fundamental redesign
```
