# AIP v0.3.0 I1 Specification — Real-World Validation Contract

**Status:** Final implementation specification  
**Target release:** `v0.3.0-alpha.1`  
**Parent release:** `v0.3.0 — Real-World Validation & Model Hardening`  
**Iteration:** I1 — Real-World Validation Contract

---

## 1. Purpose

I1 establishes the validation methodology that all later v0.3 real-system work must follow.

It intentionally validates **no external system yet**.

Its purpose is to freeze:

```text
ground-truth methodology
finding vocabulary
validation dossier structure
upstream pinning rules
supported-scope rules
comparison semantics
decision-record format
runbook contract
deterministic reporting contract
```

before Quarkus Super Heroes or Apache Airflow are evaluated.

The key rule is:

> **The validation method must exist before any AIP output can influence what the method considers
> correct.**

I1 therefore protects v0.3 from circular validation.

---

## 2. I1 Release Identity

The v0.3 progression is:

```text
v0.1
architecture intelligence exists

v0.2
architecture intelligence is reproducibly verified

v0.3
architecture intelligence survives real systems
```

I1 contributes only the validation contract required to make the final statement credible.

The I1 identity is:

```text
v0.3.0-alpha.1
real-world validation methodology is frozen and reproducible
```

It does not claim:

```text
Quarkus validated
Airflow validated
model hardened
real-world correctness proven
```

Those belong to later iterations.

---

## 3. Entry Criteria

I1 may begin when:

```text
v0.2.0 is released or the exact final v0.2 candidate is frozen
v0.2 deterministic evaluation is green
current Canonical Model semantics are documented
current evidence/runtime semantics are documented
```

I1 SHALL NOT require:

```text
Kubernetes support
MCP support
gRPC support
Dapr support
real-system fixtures
new canonical entity types
```

---

## 4. Non-Goals

I1 SHALL NOT:

```text
run the qualifying Quarkus comparison
run the qualifying Airflow comparison
change Canonical Model semantics
change relation semantics
change runtime status semantics
change evidence semantics
change identity-resolution production behavior
introduce new adapters
introduce new messaging concepts
introduce Kubernetes support
introduce MCP
add GraphRAG
create aggregate architecture scores
generate expected facts from AIP output
```

If implementation work uncovers a production defect while building I1 tooling, that defect SHALL be
tracked separately unless it blocks the validation contract itself.

---

## 5. Central Methodological Invariant

The normative rule is:

```text
AIP Input != AIP Expected Output
AIP Output MUST NOT define Ground Truth
```

The prohibited process is:

```text
run AIP
   |
   v
inspect AIP result
   |
   v
search upstream source for confirmation
   |
   v
write expected.yaml to match AIP
```

The required process is:

```text
upstream contracts
upstream architecture documentation
upstream configuration
upstream source where necessary
independent runtime evidence
        |
        v
independent architecture dossier
        |
        v
freeze supported expected facts
        |
        v
run AIP
        |
        v
compare
```

A qualifying system's expected facts SHALL be frozen before the qualifying AIP comparison.

---

## 6. Ground-Truth Source Hierarchy

The validation contract SHALL define the following preferred evidence hierarchy:

```text
1. official machine-readable contracts
2. official architecture documentation
3. official deployment/runtime configuration
4. upstream source code
5. independently captured runtime evidence
```

Examples include:

```text
OpenAPI
official architecture diagrams
broker/executor configuration
source showing a producer/consumer
raw or independently inspected OTLP traces
```

The following are explicitly not independent ground-truth sources:

```text
AIP graph state
AIP REST analysis output
AIP-generated Cypher result
AIP evaluation projection
AIP-generated expected files
AIP-generated prose describing the architecture
```

---

## 7. Ground-Truth Evidence References

Every expected supported fact SHOULD reference one or more independent evidence items.

Conceptual shape:

```yaml
expected:
  relations:
    - id: qsh-rest-fights-calls-heroes
      type: CALLS
      source: service:rest-fights
      target: operation:service:rest-heroes:GET:/api/heroes
      evidence:
        - source: official-openapi
          ref: docs/real-world-validation/quarkus-super-heroes/evidence/openapi.md
        - source: upstream-source
          ref: docs/real-world-validation/quarkus-super-heroes/evidence/source.md
```

The exact storage representation MAY be simplified.

The semantic requirement is:

```text
ExpectedFact -> IndependentEvidence
```

---

## 8. Upstream Version Contract

Every validation dossier SHALL record an exact upstream identity.

Required fields:

```text
system
upstream repository URL
upstream project version/tag, if applicable
exact commit SHA
validation profile revision
validation date
```

Conceptual example:

```yaml
system: quarkus-super-heroes
repository: https://github.com/quarkusio/quarkus-super-heroes
tag: "<tag-if-used>"
commit: "<full-sha>"
```

A validation result SHALL NOT be described as applying to "latest".

Changing the pinned SHA invalidates the previous qualifying comparison until revalidated.

---

## 9. Validation Profile Contract

Each real-system dossier SHALL define a bounded validation profile.

Required sections:

```text
upstream identity
components/processes started
runtime/deployment mode
broker/executor configuration
telemetry configuration
architecture flows exercised
supported AIP semantics in scope
known upstream mechanisms out of scope
startup procedure
traffic/exercise procedure
shutdown procedure
```

The profile SHALL be reproducible from public repository content and documented prerequisites.

It SHALL NOT depend on undocumented maintainer-local state.

---

## 10. Instrumentation Rules

The profile MAY add standard observability configuration to expose existing behavior.

Allowed:

```text
enable native OpenTelemetry export
configure OTLP endpoint
configure Collector
add standard OTel instrumentation
enable existing tracing feature
```

Prohibited:

```text
add AIP-specific architecture declarations after seeing AIP output
rename services solely to improve AIP matching
rewrite messaging topology to fit AIP semantics
add architecture manifest entries merely to turn OBSERVED_ONLY into CONFIRMED
modify upstream architecture until the comparison passes
```

Every instrumentation addition SHALL be documented in the profile.

---

## 11. Supported Semantic Scope

Each validation system SHALL declare which AIP semantics are being validated.

Example:

```yaml
supported_scope:
  relation_types:
    - PROVIDES
    - CALLS
    - SENDS
    - RECEIVES_FROM
  runtime_statuses:
    - CONFIRMED
    - OBSERVED_ONLY
    - NOT_OBSERVED_IN_WINDOW
```

The scope SHALL be defined from AIP's documented semantics and upstream evidence.

It SHALL NOT be expanded merely because AIP happened to emit an additional fact.

---

## 12. Unsupported Scope

The dossier SHALL explicitly record upstream mechanisms that are outside AIP's supported semantics.

Conceptual example:

```yaml
unsupported:
  - mechanism: grpc
    reason: >
      The selected upstream profile uses gRPC, but AIP v0.3 does not claim gRPC ingestion.
```

Unsupported items SHALL not be counted as missing supported facts.

AIP MAY still be criticized if it incorrectly maps an unsupported mechanism into a supported fact.

---

## 13. Finding Vocabulary

I1 SHALL freeze the following classifications.

### 13.1 `CORRECT`

A supported expected fact is represented correctly.

---

### 13.2 `MISSING_SUPPORTED`

Independent evidence establishes an in-scope supported fact that AIP does not represent.

This is a false negative.

---

### 13.3 `INCORRECT_SUPPORTED`

AIP emits a supported fact that contradicts independent ground truth.

Examples:

```text
invented relation
wrong direction
wrong target
wrong sender/consumer
wrong runtime status
wrong evidence attribution
```

This is the highest-severity normal finding category.

---

### 13.4 `UNSUPPORTED`

The upstream architecture contains a mechanism outside the current AIP semantic scope.

This is not automatically an AIP defect.

---

### 13.5 `UNRESOLVED_IDENTITY`

Independent evidence suggests a relationship or identity, but AIP cannot resolve it safely without
guessing.

The preferred behavior is:

```text
unresolved > guessed
```

---

### 13.6 `INSUFFICIENT_EVIDENCE`

The independent dossier cannot establish the expected fact strongly enough.

This is not an AIP defect.

The item SHALL remain outside the qualifying expected set.

---

## 14. Severity

Finding classification and severity SHALL remain distinct.

Recommended severity:

```text
CRITICAL
MAJOR
MINOR
INFO
```

Guidance:

```text
CRITICAL
    false architecture claim that invalidates supported semantics
    fundamental Canonical Model defect
    wrong direction/status/evidence with material architectural impact

MAJOR
    supported fact missing across an important validation path
    identity failure that materially blocks supported analysis

MINOR
    bounded incompleteness with no false architecture claim

INFO
    unsupported/deferred observation or documentation note
```

The final v0.3 release requires:

```text
unresolved CRITICAL findings = 0
```

---

## 15. Validation Dossier Structure

I1 SHALL establish the dossier layout.

Required logical structure:

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

The exact names MAY vary.

The following separation is normative:

```text
upstream identity
validation profile
ground truth
execution runbook
AIP results
findings
```

---

## 16. Root Real-World Validation README

I1 SHALL add:

```text
docs/real-world-validation/README.md
```

It SHALL explain:

```text
purpose of the validation track
ground-truth independence rule
finding vocabulary
how system dossiers are structured
how to reproduce a validation
difference between supported and unsupported scope
```

It SHALL NOT contain system-specific qualifying results.

---

## 17. `expected.yaml` Contract

I1 SHALL define a minimal semantic expected format.

A recommended initial schema is:

```yaml
system: <system-id>
upstream_revision: <full-sha>

scope:
  entities:
    - <canonical-id>
  relation_types:
    - <relation-type>

expected:
  relations:
    - id: <stable-finding-id>
      type: <relation-type>
      source: <canonical-source-id>
      target: <canonical-target-id>
      status: <optional-runtime-status>
      evidence:
        declared: <true|false|null>
        observed: <true|false|null>

unsupported:
  - id: <stable-id>
    mechanism: <name>
    description: <text>
```

The final I1 schema MAY omit fields not required for the initial validation.

It SHALL NOT include:

```text
Cypher
AIP graph IDs as oracle implementation details
generated expected result
policy expressions
weighted scoring rules
```

---

## 18. Stable Finding IDs

Expected items and findings SHOULD have stable human-readable IDs.

Examples:

```text
qsh-rest-fights-calls-heroes
qsh-event-statistics-receives-fight
airflow-api-provides-dags
airflow-worker-identity-01
```

IDs SHALL be unique inside a system dossier.

They SHOULD remain stable when descriptive text changes.

---

## 19. Comparison Input

The comparator SHALL consume:

```text
frozen expected supported facts
actual AIP canonical facts
declared supported scope
```

It SHALL NOT consume upstream source directly during comparison.

Ground-truth research and AIP comparison are separate phases.

---

## 20. Comparison Output

The comparator SHALL produce deterministic finding records.

Conceptual structure:

```yaml
findings:
  - id: qsh-rest-fights-calls-heroes
    classification: CORRECT
    severity: INFO
    expected:
      type: CALLS
      source: service:rest-fights
      target: operation:service:rest-heroes:GET:/api/heroes
    actual:
      type: CALLS
      source: service:rest-fights
      target: operation:service:rest-heroes:GET:/api/heroes
```

For a mismatch:

```yaml
findings:
  - id: airflow-worker-call-01
    classification: MISSING_SUPPORTED
    severity: MAJOR
    expected: ...
    actual: null
```

Output ordering SHALL be deterministic.

---

## 21. Deterministic Finding Order

The canonical finding sort key SHALL be defined in I1.

Recommended order:

```text
classification
severity
relation type
source
target
finding id
```

If an alternative order is selected, it SHALL be documented and tested.

Repeated comparison of identical inputs SHALL produce semantically identical output.

---

## 22. No Composite Score

I1 SHALL explicitly reject a weighted architecture score.

The report SHALL use counts:

```text
expected supported facts
correct
missing supported
incorrect supported
unsupported
unresolved identity
insufficient evidence
```

Percentages MAY be derived for display.

No weighted total SHALL determine PASS/FAIL.

---

## 23. Validation Summary Contract

Every system result SHALL expose a concise summary.

Example:

```text
Expected supported facts:      42
Correct:                       38
Missing supported:              4
Incorrect supported:            0
Unsupported constructs:         3
Unresolved identities:          2
Critical semantic errors:       0
```

The exact numbers are system-specific.

The field names SHALL remain consistent across Quarkus and Airflow.

---

## 24. Model-Hardening Decision Record

I1 SHALL define the format for material decisions.

Recommended template:

```markdown
# Finding <id>

## System
<system>

## Independent evidence
<references>

## Current AIP behavior
<description>

## Classification
<finding classification>

## Severity
<severity>

## Decision
FIX | DOCUMENT_UNSUPPORTED | DEFER | NO_CHANGE

## Rationale
<why>

## Canonical-model impact
<none / description>

## Compatibility impact
<none / description>

## Required implementation change
<description>

## Regression coverage
<test/fixture>
```

The decision record SHALL be authored before or together with the corresponding production fix.

---

## 25. Allowed Decisions

Allowed material finding dispositions are:

```text
FIX
DOCUMENT_UNSUPPORTED
DEFER
NO_CHANGE
```

Meanings:

```text
FIX
    AIP behavior is wrong or insufficient inside supported scope.

DOCUMENT_UNSUPPORTED
    mechanism is outside current supported semantics and is handled safely.

DEFER
    finding is valid, but belongs to a later capability/release.

NO_CHANGE
    evidence does not justify a semantic/model change.
```

---

## 26. Model Change Gate

A model or semantic change SHALL require all of:

```text
independent real-system evidence
material supported-scope problem
general rather than system-specific correction
precise semantic statement
deterministic regression coverage
```

A richer possible model is not sufficient justification.

---

## 27. No System-Specific Hacks

I1 SHALL document that later implementation MUST NOT contain production behavior such as:

```text
if system == "airflow": ...
if service == "rest-fights": ...
special-case pinned upstream endpoint names
special-case topic/queue names
validation-only graph repair
post-processing actual output to match expected output
```

Validation adapters or scripts MAY contain system-specific setup logic.

Production AIP semantics SHALL remain general.

---

## 28. Runbook Contract

Each system's `runbook.md` SHALL define an ordered reproducible process.

Required phases:

```text
1. prerequisites
2. fetch pinned upstream version
3. configure profile
4. start system
5. enable/configure telemetry
6. exercise declared validation flows
7. import declared architecture sources into AIP
8. send/capture runtime observations
9. query/capture AIP result
10. execute comparison
11. store deterministic report
12. tear down environment
```

The runbook SHALL identify any step that is manual.

---

## 29. Clean-State Requirement

Each qualifying validation SHOULD begin from clean state.

The runbook SHALL describe how to reset:

```text
upstream system state where required
broker state where required
AIP graph state
AIP evidence state
temporary telemetry captures
containers/volumes
```

A validation SHALL NOT depend on unexplained data from an earlier run.

---

## 30. Runtime Evidence Contract

Runtime evidence MAY be:

```text
live telemetry generated by the pinned profile
```

or:

```text
sanitized committed telemetry capture
```

If captures are committed, they SHALL:

```text
contain no secrets
contain no personal/customer data
document source system/version
document capture procedure
preserve semantic attributes required by AIP
```

I1 SHALL define where such captures belong if they are used.

---

## 31. AIP Result Capture

The validation SHOULD preserve the actual AIP result used for comparison.

The result capture SHALL:

```text
use canonical identities
be deterministic where possible
exclude irrelevant volatile fields
not become the expected oracle
```

Recommended logical location:

```text
docs/real-world-validation/<system>/artifacts/
```

or a generated release-validation artifact directory.

Large captures need not be committed when reproducible regeneration is simpler.

---

## 32. Validation Utility

I1 MAY introduce a focused comparison utility.

Preferred conceptual CLI:

```bash
uv run python -m real_world_validation compare <system>
```

It MAY:

```text
load expected.yaml
load/query normalized AIP facts
compare exact supported facts
classify differences
sort deterministically
emit summary + findings
```

It SHALL NOT:

```text
run an LLM
generate expected.yaml
infer unsupported semantics
change AIP graph state
repair canonical identities
```

---

## 33. Exit Codes

If a CLI comparison utility is implemented, it SHOULD use:

```text
0
    comparison completed and no release-blocking finding exists

1
    one or more release-blocking comparison findings exist

2
    invalid validation configuration / expected data
```

Unexpected infrastructure/programmer failures MAY terminate with a traceback unless a later
iteration explicitly standardizes them.

---

## 34. Comparator Failure Semantics

The comparator SHALL detect at least:

```text
missing expected supported fact
unexpected supported fact
incorrect relation direction
incorrect relation identity
incorrect runtime status where asserted
incorrect evidence expectation where asserted
duplicate expected identity
invalid expected schema
scope-excluded expectation
```

Unsupported items SHALL not be counted as missing supported facts.

---

## 35. Unexpected Supported Facts

AIP facts inside the declared comparison scope that are neither expected nor explicitly accepted
SHALL be surfaced.

The validator SHALL NOT silently ignore extra in-scope architecture claims.

Conceptually:

```text
ExpectedSupported
    vs
ActualInScope
```

Both missing and extra facts matter.

---

## 36. Ground-Truth Review Gate

Before the first qualifying run for a system:

```text
upstream.md        complete
profile.md         complete
ground-truth.md    complete
expected.yaml      frozen
```

The commit containing the frozen expected set SHOULD precede the commit containing the first
qualifying results.

This provides a visible audit trail that the ground truth was not rewritten after seeing AIP output.

If repository workflow makes a separate commit impractical, the PR history SHALL still make the
freeze point explicit.

---

## 37. Ground-Truth Change Policy

After a qualifying AIP run, expected ground truth MAY change only when:

```text
independent evidence was wrong/incomplete
upstream scope changed
pinned upstream revision changed
validation profile changed
a documented evidence interpretation was corrected
```

It SHALL NOT change merely because AIP disagreed.

Every post-freeze expectation change SHALL be documented.

---

## 38. Documentation of Unknowns

Where upstream architecture cannot be established confidently:

```text
do not guess
```

Record:

```text
INSUFFICIENT_EVIDENCE
```

or:

```text
UNRESOLVED_IDENTITY
```

depending on whether the uncertainty is in the independent dossier or in AIP resolution.

This distinction SHALL remain explicit.

---

## 39. Repository Licensing Hygiene

I1 SHALL define that real-system validation documentation records:

```text
upstream repository
upstream license
pinned revision
```

AIP SHALL NOT vendor complete external projects merely for validation convenience.

Minimal derived metadata and legally reusable fixtures are preferred.

---

## 40. Privacy and Secrets

Validation artifacts SHALL NOT commit:

```text
passwords
API keys
authorization headers
private tokens
customer data
personal data
full request/response bodies unless demonstrably harmless and required
```

OTel captures SHALL be sanitized before commit.

Architecture-relevant low-cardinality metadata is preferred.

---

## 41. I1 Deliverables

I1 SHALL deliver at minimum:

```text
docs/real-world-validation/README.md
validation dossier template
expected.yaml schema or validation model
finding classification model
deterministic comparison semantics
summary/report format
model-hardening decision template
runbook template
tests for the validation contract
```

If a CLI comparator is implemented, its behavior SHALL be covered by unit tests.

---

## 42. Suggested Implementation Files

A possible implementation is:

```text
real_world_validation/
├── __init__.py
├── loader.py
├── model.py
├── comparator.py
├── reporter.py
└── __main__.py

tests/unit/
├── test_real_world_validation_loader.py
├── test_real_world_validation_comparator.py
└── test_real_world_validation_reporter.py
```

Exact paths are non-normative.

The validation utility SHALL remain outside production architecture semantics.

---

## 43. Required Tests

I1 SHALL include deterministic tests for at least:

```text
valid expected document
unknown field rejection
duplicate finding id rejection
invalid relation type rejection
invalid canonical identity rejection where validation exists
unsupported entry loading
missing supported classification
unexpected supported classification
incorrect status classification
deterministic ordering
summary counters
invalid configuration exit behavior if CLI exists
```

No real external system is required in I1 tests.

---

## 44. v0.2 Regression

I1 SHALL preserve the v0.2 evaluation baseline.

Required before `v0.3.0-alpha.1`:

```bash
uv run python -m evaluation run
```

Expected:

```text
10/10 PASS
```

I1 SHALL NOT change v0.2 semantic expectations.

---

## 45. CI Qualification

Before I1 is complete:

```text
ruff check                PASS
ruff format --check       PASS
unit tests                PASS
integration tests         PASS
v0.2 evaluation           10/10 PASS
CI                        PASS
CodeQL                    PASS
dependency audit          PASS
```

The exact test counts are not normative.

---

## 46. I1 Release Blockers

The following block `v0.3.0-alpha.1`:

```text
ground truth can be generated from AIP output
unsupported items are counted as supported failures
unexpected supported facts can be silently ignored
finding categories are ambiguous
comparison order is nondeterministic
expected schema accepts unknown semantic fields silently
post-freeze ground-truth changes need no explanation
validation requires an LLM
v0.2 semantic evaluation regresses
```

Target:

```text
critical methodology defects = 0
release blockers = 0
```

---

## 47. I1 Non-Blocking Items

The following are intentionally deferred:

```text
actual Quarkus results
actual Airflow results
model hardening
production resolver changes
messaging-model changes
new architecture adapters
live external-system CI
MCP
Kubernetes
Dapr
gRPC
GraphRAG
```

---

## 48. Definition of Done

I1 is complete when all mandatory conditions are satisfied.

### Methodology

- [ ] Ground-truth independence rule is documented.
- [ ] Ground-truth source hierarchy is documented.
- [ ] Upstream pinning contract is documented.
- [ ] Validation profile contract is documented.
- [ ] Instrumentation rules are documented.
- [ ] Supported-versus-unsupported scope rules are documented.
- [ ] Ground-truth freeze/change policy is documented.

### Findings

- [ ] `CORRECT` is defined.
- [ ] `MISSING_SUPPORTED` is defined.
- [ ] `INCORRECT_SUPPORTED` is defined.
- [ ] `UNSUPPORTED` is defined.
- [ ] `UNRESOLVED_IDENTITY` is defined.
- [ ] `INSUFFICIENT_EVIDENCE` is defined.
- [ ] Severity remains separate from classification.
- [ ] Stable finding IDs are defined.

### Validation Artifacts

- [ ] `docs/real-world-validation/README.md` exists.
- [ ] System dossier template exists.
- [ ] `expected.yaml` contract exists.
- [ ] Runbook template exists.
- [ ] Model-hardening decision template exists.
- [ ] Summary/report format exists.

### Comparator

- [ ] Missing supported facts are detected.
- [ ] Unexpected supported facts are detected.
- [ ] Incorrect status/evidence can be represented.
- [ ] Unsupported items remain separate.
- [ ] Comparison output is deterministic.
- [ ] Summary counters are deterministic.
- [ ] Validation configuration is strict.

### Quality

- [ ] Validation-contract unit tests are green.
- [ ] Existing unit tests are green.
- [ ] Existing integration tests are green.
- [ ] Ruff is green.
- [ ] v0.2 evaluation remains `10/10 PASS`.
- [ ] CI is green.
- [ ] CodeQL is green.
- [ ] Dependency audit is green.
- [ ] Release blockers = `0`.

---

## 49. Exit State

At the end of I1, AIP SHALL be ready to begin Quarkus validation without changing the validation
method in response to Quarkus results.

Expected state:

```text
Methodology                 FROZEN
Finding vocabulary          FROZEN
Dossier format              FROZEN
Expected schema             FROZEN
Comparison semantics        FROZEN
Decision-record format      FROZEN

Quarkus ground truth        NOT YET QUALIFIED
Airflow ground truth        NOT YET QUALIFIED
Model hardening             NOT STARTED
```

Minor editorial improvements remain possible.

Semantic changes to the validation contract after I1 SHALL be explicit and justified.

---

## 50. Relationship to I2

I2 uses the I1 contract to validate Quarkus Super Heroes.

The I2 sequence SHALL be:

```text
pin upstream revision
        |
        v
build independent dossier
        |
        v
freeze expected.yaml
        |
        v
run AIP
        |
        v
compare using I1 semantics
        |
        v
classify findings
```

I2 SHALL NOT redefine the finding vocabulary because the first results are inconvenient.

---

## 51. Summary

I1 does not prove that AIP works on real systems.

It makes the later proof credible.

The defining invariant is:

> **Ground truth is established independently, frozen before comparison, and never repaired to make
> AIP pass.**

The I1 output is the methodological foundation for:

```text
I2
Quarkus Super Heroes

I3
Apache Airflow

I4
Cross-System Model Hardening

I5
v0.3.0 Release Qualification
```

`v0.3.0-alpha.1` is complete when the validation contract is strict, deterministic, reproducible,
and independent of AIP's own output.
