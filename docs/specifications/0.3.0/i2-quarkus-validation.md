# AIP v0.3.0 I2 Specification — Quarkus Super Heroes Validation

**Status:** Final implementation specification  
**Target release:** `v0.3.0-alpha.2`  
**Parent release:** `v0.3.0 — Real-World Validation & Model Hardening`  
**Iteration:** I2 — Quarkus Super Heroes Validation  
**Predecessor:** `I1 — Real-World Validation Contract`

---

## 1. Purpose

I2 applies the real-world validation contract established in I1 to the first independently authored
external system:

```text
Quarkus Super Heroes
    role: External Reference Architecture
```

I2 is the first point at which AIP is compared against architecture ground truth that was not created
for AIP.

The iteration SHALL answer:

> **Does AIP correctly represent the subset of Quarkus Super Heroes architecture that falls inside
> AIP's current supported semantics, while leaving unsupported mechanisms explicit and
> unmisrepresented?**

I2 is not a framework-compatibility marketing exercise.

It is a semantic validation exercise.

---

## 2. I2 Release Identity

The v0.3 progression is:

```text
I1
validation methodology is frozen

I2
the current AIP model is challenged by
an external reference architecture

I3
the current AIP model is challenged by
real-world OSS software

I4
cross-system findings drive model hardening
```

The I2 release identity is:

```text
v0.3.0-alpha.2
Quarkus Super Heroes validation is reproducible,
independently grounded, and fully classified
```

I2 SHALL NOT claim that Apache Airflow has been validated or that all final v0.3 model hardening is
complete.

---

## 3. Entry Criteria

I2 SHALL begin only after I1 is complete.

Required I1 baseline:

```text
ground-truth independence rule frozen
finding vocabulary frozen
severity model frozen
validation dossier format frozen
expected.yaml contract frozen
comparison semantics frozen
runbook contract frozen
decision-record format frozen
v0.2 deterministic evaluation green
```

If I1 semantics change during I2, the change SHALL be explicit and justified independently of the
Quarkus result.

I2 SHALL NOT redefine the validation method merely because the first real result is inconvenient.

---

## 4. Upstream System Pin

The qualifying I2 upstream baseline SHALL be:

```text
Repository:
    quarkusio/quarkus-super-heroes

Pinned commit:
    8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce

Default branch at pin time:
    main

Pin date:
    2026-08-31

License:
    Apache-2.0
```

The exact commit is normative for I2.

The validation SHALL NOT run against an unpinned `main` or `latest`.

If this revision proves operationally unusable for reasons unrelated to AIP, changing the pin
requires:

```text
documented reason
new exact SHA
ground-truth review against the new SHA
profile re-freeze
```

A different upstream revision SHALL not silently replace the pinned baseline.

---

## 5. Verified Upstream Architecture Facts at the Pin

The pinned upstream project documents itself as a set of multiple microservices communicating:

```text
synchronously via REST
asynchronously via Kafka
```

and exporting:

```text
traces
metrics
logs
via OpenTelemetry / OTLP
```

The pinned repository includes at least:

```text
ui-super-heroes
rest-villains
rest-heroes
rest-narration
grpc-locations
rest-fights
event-statistics
```

For I2, the most relevant verified upstream facts are:

```text
rest-fights
    is a REST API
    uses contract-first OpenAPI
    calls Hero service
    calls Villain service
    calls Narration service
    calls Location service through gRPC
    publishes fight events to Kafka topic "fights"

event-statistics
    consumes fight events from Kafka topic "fights"

all services
    are documented as exporting OpenTelemetry telemetry
```

These upstream facts define research targets.

They do not, by themselves, define AIP expected facts until translated through the I1 supported-scope
process.

---

## 6. Pinned Upstream Evidence References

The I2 dossier SHALL cite pinned upstream evidence rather than moving branch URLs.

Primary references include:

```text
Repository README
    README.md @ 8ea03377...

Fight service README
    rest-fights/README.md @ 8ea03377...

Fight service configuration
    rest-fights/src/main/resources/application.properties @ 8ea03377...

Event statistics README
    event-statistics/README.md @ 8ea03377...

Fight OpenAPI
    rest-fights/src/main/resources/openapi/openapi.yml @ 8ea03377...
```

The implementation dossier SHALL record the exact GitHub permalink for every referenced file.

---

## 7. Validation Profile

I2 SHALL define one bounded local validation profile.

The profile SHALL exercise:

```text
rest-fights
rest-heroes
rest-villains
rest-narration
event-statistics
Kafka infrastructure required by the upstream system
OpenTelemetry export path
```

The profile MAY also start:

```text
grpc-locations
UI
Grafana/LGTM
databases
schema registry
```

when required for the official upstream startup path.

However:

```text
started != supported by AIP
```

The profile SHALL distinguish runtime prerequisites from AIP validation scope.

---

## 8. Mandatory Supported-Scope Targets

I2 SHALL validate at least the following current AIP semantics where independent upstream evidence
supports them:

```text
Service identity
PROVIDES
CALLS
declared evidence
observed evidence
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
evidence preservation
runtime environment/window qualification
```

Messaging SHALL be treated separately under the explicit messaging-boundary rules in this
specification.

---

## 9. OpenAPI Validation Scope

The minimum declared REST scope SHALL include:

```text
rest-fights
rest-heroes
rest-villains
rest-narration
```

At least one official OpenAPI artifact SHALL be captured for each service that participates in
qualifying provider/caller resolution.

For `rest-fights`, the pinned static contract-first source is:

```text
rest-fights/src/main/resources/openapi/openapi.yml
```

For other services, I2 MAY use:

```text
pinned static OpenAPI files in the repository
or
OpenAPI emitted by the pinned running service
```

provided the source is:

```text
official upstream output
captured before AIP comparison
stored or hash-pinned
documented in ground-truth evidence
```

AIP-generated OpenAPI or reconstructed contracts are prohibited as ground truth.

---

## 10. Declared Provider Ground Truth

For each OpenAPI document in the qualifying scope, I2 SHALL establish independently:

```text
logical service
operation method
operation route/template
canonical expected provider identity
```

The expected `PROVIDES` set SHALL be frozen before the qualifying AIP run.

The ground truth SHALL not depend on AIP-generated operation IDs.

The dossier MAY translate official upstream operations into AIP canonical identifiers as a
normalization step, but the source operation identity SHALL be independently documented.

---

## 11. REST Caller Ground Truth

The primary synchronous caller under validation is:

```text
rest-fights
```

I2 SHALL independently establish at least three REST dependencies from `rest-fights`.

The initial target set is:

```text
rest-fights -> rest-heroes
rest-fights -> rest-villains
rest-fights -> rest-narration
```

The exact called operation for each relation SHALL be established from:

```text
upstream OpenAPI
rest-client configuration
upstream source
runtime trace evidence
```

before the expected AIP `CALLS` fact is frozen.

The gRPC Location dependency SHALL NOT be translated into `CALLS` to an HTTP Operation.

---

## 12. gRPC Boundary

The pinned Fight service calls the Location service through gRPC.

AIP v0.3 does not include a gRPC/protobuf ingestion adapter.

Therefore:

```text
rest-fights -> grpc-locations
```

is a mandatory `UNSUPPORTED` architecture mechanism for I2 unless AIP's supported semantics are
deliberately expanded through a separately approved model-hardening decision.

I2 SHALL verify that AIP does not silently represent this gRPC dependency as:

```text
HTTP CALLS
Queue messaging
another incorrect supported relation
```

The expected result is not "AIP discovers gRPC".

The expected result is:

```text
unsupported remains explicit
no false supported architecture fact is invented
```

---

## 13. Kafka Messaging Boundary

The pinned Fight service publishes events to Kafka topic:

```text
fights
```

and `event-statistics` consumes from that topic.

This is an important I2 model-boundary test.

The current AIP canonical asynchronous model is queue-centric and distinguishes queue semantics from
topic/fan-out semantics.

Therefore I2 SHALL NOT assume:

```text
Kafka Topic -> AIP Queue
```

merely because there is one producer and one consumer in the selected profile.

The independent ground truth SHALL record:

```text
destination kind:
    Kafka topic

name:
    fights

producer:
    rest-fights

consumer:
    event-statistics
```

separately from AIP expected Queue facts.

---

## 14. Messaging Qualification Rule

For the qualifying I2 comparison:

```text
Kafka topic "fights"
```

SHALL initially be treated as:

```text
UNSUPPORTED messaging mechanism
```

with respect to AIP's strict Queue semantics.

The qualifying expected set SHALL NOT pre-author:

```text
SENDS -> Queue(fights)
RECEIVES_FROM -> Queue(fights)
```

solely because upstream Kafka metadata contains a destination named `fights`.

If AIP emits Queue-based facts for the Kafka topic, I2 SHALL classify that behavior through the I1
finding process.

Possible outcomes include:

```text
INCORRECT_SUPPORTED
    if AIP makes a semantically false Queue claim

DOCUMENT_UNSUPPORTED
    if AIP safely refuses/omits the topic

DEFER
    if supporting Topic/Subscription is a later model extension
```

I2 SHALL NOT add a `Topic` entity merely to make this single validation pass.

A canonical messaging redesign belongs in I4 unless an urgent general correction is required to
prevent false supported facts.

---

## 15. Why Kafka Is Still Mandatory in I2

Although Kafka topic semantics are not assumed to fit AIP's current Queue model, Kafka remains part
of the mandatory validation profile because it tests a critical property:

> **Does AIP preserve semantic boundaries when real systems contain architecture it does not yet
> support?**

A successful I2 result MAY therefore include:

```text
REST supported and correct
gRPC unsupported and explicit
Kafka topic unsupported and explicit
```

That is preferable to:

```text
REST correct
gRPC guessed
Kafka topic mislabeled as Queue
```

---

## 16. OpenTelemetry Validation Scope

The pinned upstream service configuration includes OpenTelemetry export configuration.

I2 SHALL configure the selected profile so that architecture-relevant traces are available to AIP
through the existing OTLP path.

The preferred path is:

```text
Quarkus services
    |
    v
OpenTelemetry / OTLP
    |
    +--> upstream observability stack if required
    |
    +--> AIP OTLP ingestion
```

A Collector MAY be used for fan-out.

I2 SHALL NOT require source-code instrumentation changes if the pinned upstream application already
emits the required telemetry.

---

## 17. Telemetry Configuration Rules

Changes required only to route existing telemetry to AIP are allowed.

Examples:

```text
OTLP endpoint override
Collector fan-out configuration
environment name
sampling configuration
```

Every change SHALL be recorded in:

```text
profile.md
runbook.md
```

The profile SHALL avoid changes that alter logical service identity unless the change is standard
observability configuration and independently justified.

---

## 18. Environment and Observation Window

The I2 runtime environment SHALL use a dedicated deterministic name.

Recommended:

```text
quarkus-i2
```

All runtime-qualified comparisons SHALL record:

```text
environment
window_start
window_end
```

The selected window SHALL include only the qualifying traffic run.

Unrelated startup traces SHOULD be excluded where practical.

---

## 19. Runtime Traffic Script

I2 SHALL define a deterministic traffic/exercise procedure.

It SHALL exercise at minimum:

```text
hero retrieval through Fight flow
villain retrieval through Fight flow
fight execution
narration request if operationally deterministic enough
Kafka fight event publication
event-statistics consumption
```

The exact HTTP commands MAY use:

```text
official UI workflow
curl
upstream documented endpoints
a small deterministic validation script
```

The traffic script SHALL not call AIP-specific endpoints inside the upstream system.

---

## 20. External Dependencies and Nondeterminism

The Narration service integrates with OpenAI in the pinned upstream project.

I2 SHALL NOT make the qualifying validation depend on successful external generative-AI output.

If the upstream project provides:

```text
fallback behavior
mock mode
local deterministic mode
documented dev/test substitute
```

I2 SHOULD use it.

The validation target is:

```text
architecture interaction
```

not generated narration quality.

The runbook SHALL document how external nondeterminism is removed from the qualifying profile.

---

## 21. Upstream Application Modification Policy

The preferred profile uses the upstream system unmodified.

Allowed additions are limited to:

```text
external Docker Compose override
environment variables
OTel Collector configuration
traffic scripts
AIP-side source capture
```

If a source modification becomes unavoidable, I2 SHALL document:

```text
exact patch
reason
why architecture semantics are unchanged
```

A source modification that changes architecture semantics invalidates the external-reference
character of the test and requires explicit review.

---

## 22. Quarkus Dossier Structure

I2 SHALL populate:

```text
docs/real-world-validation/quarkus-super-heroes/
├── upstream.md
├── profile.md
├── ground-truth.md
├── expected.yaml
├── runbook.md
├── results.md
├── findings.md
├── evidence/
└── decisions/
```

`evidence/` SHOULD contain compact source-reference records rather than copied upstream repositories.

`decisions/` SHALL contain material model-hardening decisions raised by I2.

---

## 23. `upstream.md`

`upstream.md` SHALL record at minimum:

```text
project name
repository
license
pinned SHA
pin date
JVM requirement
relevant upstream components
relevant upstream documentation links
why the project is classified as External Reference Architecture
```

It SHALL clearly state that Quarkus Super Heroes is a sample/reference architecture, not production
software.

---

## 24. `profile.md`

`profile.md` SHALL define:

```text
services started
infrastructure started
services included in AIP scope
services excluded from AIP scope
OpenAPI acquisition method per service
OTel export path
traffic generation
environment name
observation-window method
external dependencies disabled/mocked/fallback
cleanup/reset procedure
```

It SHALL explicitly list:

```text
gRPC -> unsupported
Kafka topic semantics -> unsupported for Queue qualification
```

unless later changed by an approved decision record.

---

## 25. `ground-truth.md`

`ground-truth.md` SHALL be authored before the first qualifying AIP comparison.

It SHALL contain:

```text
logical service inventory
REST provider inventory
qualifying REST dependencies
gRPC unsupported dependency
Kafka topic producer/consumer ground truth
evidence references
identity normalization rationale
known ambiguities
insufficient-evidence items
```

The document SHALL clearly separate:

```text
upstream architecture fact
```

from:

```text
expected AIP supported fact
```

---

## 26. `expected.yaml`

The qualifying `expected.yaml` SHALL contain only supported AIP facts.

It SHOULD include:

```text
PROVIDES
CALLS
runtime status where intentionally asserted
declared/observed evidence expectations
```

It SHALL NOT encode unsupported gRPC or Kafka topic semantics as fake AIP relations.

Those belong under the dossier's `unsupported` section.

---

## 27. Expected Runtime Status Strategy

I2 SHOULD create a small deterministic set of runtime-qualified expectations.

At minimum, it SHOULD validate:

```text
CONFIRMED
```

for one or more REST dependencies where both:

```text
declared provider/dependency evidence
observed runtime evidence
```

are intentionally present.

If a declared caller source is not independently available for a relation, runtime evidence MAY
produce:

```text
OBSERVED_ONLY
```

That is acceptable and SHOULD be tested where it arises naturally.

I2 SHALL NOT manufacture a declaration solely to force `CONFIRMED`.

---

## 28. Architecture Manifest Rule

The AIP Architecture Manifest MAY be used only if an equivalent caller declaration exists
independently in the upstream project or validation dossier before the AIP run.

It SHALL NOT be created after observing telemetry merely to convert:

```text
OBSERVED_ONLY -> CONFIRMED
```

If upstream source/config proves a caller relation but no machine-readable AIP-supported declaration
exists, the preferred I2 outcome is:

```text
ground truth knows the caller
AIP runtime may observe it
status may remain OBSERVED_ONLY
```

unless a pre-run independently authored manifest is explicitly part of the frozen validation profile.

---

## 29. Identity Normalization

The dossier SHALL define expected mappings between upstream service identities and AIP canonical IDs.

Examples may include:

```text
quarkus.application.name
OpenAPI service identity
OTel service.name
repository service directory
```

The mapping SHALL be derived from upstream evidence before comparison.

I2 SHALL NOT:

```text
repair actual AIP IDs in comparator code
fuzzy-match names after the run
drop prefixes/suffixes until results pass
```

If AIP fails to resolve identities safely:

```text
UNRESOLVED_IDENTITY
```

or:

```text
MISSING_SUPPORTED
```

SHALL be used as appropriate.

---

## 30. Operation Identity

Expected REST relations SHALL target specific canonical operations, not only service names.

For each qualifying `CALLS`, the dossier SHALL establish:

```text
provider service
HTTP method
route/template
operation identity
```

Where runtime telemetry emits concrete path values, AIP SHALL resolve to a low-cardinality route
template using its existing production resolver.

No comparator-side route reconstruction is allowed.

---

## 31. Provider and Caller Independence

I2 SHALL preserve the existing semantic rule:

```text
PROVIDES != CALLS
```

An OpenAPI provider declaration proves only:

```text
Service PROVIDES Operation
```

It SHALL NOT be used to infer which other service calls that operation.

Caller ground truth SHALL come from independent caller-side evidence.

---

## 32. Qualifying Comparison Phases

I2 SHALL execute the validation in four logically separated phases.

### Phase A — Ground Truth

```text
pin upstream
build dossier
capture official contracts
inspect upstream config/source
freeze expected.yaml
commit/review freeze point
```

No qualifying AIP result may influence this phase.

### Phase B — First AIP Run

```text
start clean external system
start clean AIP
import supported declared sources
route OTLP
exercise traffic
capture AIP facts
run comparator
```

### Phase C — Findings

```text
classify every material mismatch
assign severity
create decision record where required
```

### Phase D — Revalidation

After any accepted general AIP fix:

```text
reset
repeat qualifying profile
compare against same frozen ground truth
```

---

## 33. Ground-Truth Freeze Gate

Before Phase B:

```text
upstream.md        complete
profile.md         complete
ground-truth.md    complete
expected.yaml      frozen
```

A visible repository freeze point SHALL exist.

Preferred:

```text
ground-truth PR/commit merged before results PR
```

Acceptable alternative:

```text
one PR with explicit pre-run commit
followed by result commits
```

The history SHALL make it possible to prove that expected facts preceded AIP comparison results.

---

## 34. AIP Result Capture

I2 SHALL preserve the normalized actual fact set used by the comparator.

The result MAY be stored as:

```text
generated JSON/YAML artifact
release-validation artifact
committed compact result file
```

It SHALL include enough information to review:

```text
type
source
target
status
evidence presence
context
```

Volatile internal IDs unrelated to semantics SHOULD be excluded.

---

## 35. Finding Classification

Every material comparison item SHALL use the I1 vocabulary:

```text
CORRECT
MISSING_SUPPORTED
INCORRECT_SUPPORTED
UNSUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
```

I2 SHALL NOT add Quarkus-specific finding categories.

---

## 36. Quarkus-Specific Expected Challenges

The iteration SHALL actively examine at least these model boundaries:

```text
REST contract-first provider identity
runtime target-operation resolution
service-name consistency across OpenAPI and OTel
Stork/service-discovery naming versus canonical service identity
gRPC unsupported boundary
Kafka Topic versus Queue semantic boundary
external narration dependency nondeterminism
mixed sync/async topology
```

A validation that exercises only the easiest REST path is insufficient.

---

## 37. Material Finding Decisions

A material I2 finding MAY result in:

```text
FIX
DOCUMENT_UNSUPPORTED
DEFER
NO_CHANGE
```

Before production code changes, the decision SHALL be recorded.

I2 MAY implement:

```text
small general identity fixes
small general operation-resolution fixes
evidence/status correctness fixes
safe prevention of false supported facts
```

when independently justified.

---

## 38. Changes Deferred to I4

The following SHOULD normally be deferred to I4 for cross-system review:

```text
new canonical entity family
new canonical relation family
Topic/Subscription model
major Service identity redesign
large runtime-status redesign
new protocol adapter family
```

Reason:

```text
one external system
    !=
sufficient evidence for a broad canonical redesign
```

I4 exists to compare Quarkus and Airflow findings before major model decisions.

---

## 39. Immediate False-Claim Mitigation

A critical false supported fact SHALL not remain merely because the complete model redesign is
deferred.

If AIP currently misrepresents an unsupported mechanism, I2 MAY implement a narrow general safety
fix that changes behavior from:

```text
wrong supported fact
```

to:

```text
unsupported / unresolved / omitted
```

without introducing the final richer model.

This follows:

```text
correct but incomplete
    >
complete-looking but wrong
```

---

## 40. No Quarkus-Specific Production Logic

Production AIP code SHALL NOT contain:

```text
if service == "rest-fights"
if topic == "fights"
if system == "quarkus-super-heroes"
if service starts with "rest-heroes"
```

System-specific logic belongs only in:

```text
validation setup
ground-truth dossier
traffic scripts
comparison inputs
```

General production semantics remain system-independent.

---

## 41. Reproducible Runbook

The I2 `runbook.md` SHALL contain exact commands for:

```text
clone upstream
checkout pinned SHA
start selected upstream profile
verify health/readiness
start/configure AIP
capture/import OpenAPI
configure OTLP routing
start observation window
execute validation traffic
end observation window
capture AIP results
run comparator
store report
tear down upstream
tear down AIP
remove temporary state
```

The runbook SHALL identify:

```text
required Docker version/features
required Java version if host execution is used
required ports
required disk/memory assumptions
```

---

## 42. Clean-State Requirement

Every qualifying run SHALL begin from clean validation state.

At minimum reset:

```text
AIP Neo4j state
AIP evidence state
upstream application data where required
Kafka/topic state where required
temporary OTel capture state
validation output directory
```

The validation SHALL not rely on unexplained facts from an earlier run.

---

## 43. Repeatability

The final I2 qualification SHALL run the same comparison at least twice from clean state.

Required invariants:

```text
same upstream SHA
same profile
same frozen expected.yaml
same AIP candidate
same finding classifications
same summary counts
same deterministic ordering
```

Runtime-generated opaque IDs MAY differ if they are not part of the semantic result contract.

---

## 44. Expected I2 Report

The final report SHALL use the shared v0.3 summary shape.

Example:

```text
Quarkus Super Heroes
---------------------
Upstream SHA:                 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce

Expected supported facts:     N
Correct:                      N
Missing supported:            N
Incorrect supported:          0
Unsupported constructs:       N
Unresolved identities:        N
Insufficient evidence:        N

Critical semantic errors:     0
```

Actual counts SHALL come from the frozen scope.

They SHALL not be preselected to make the result look favorable.

---

## 45. I2 Success Criteria

I2 does not require perfect coverage.

It requires:

```text
all material findings classified
all CRITICAL findings dispositioned
critical INCORRECT_SUPPORTED findings = 0
no unsupported mechanism silently misrepresented
ground truth remains independent
revalidation is reproducible
```

A valid I2 outcome may contain:

```text
MISSING_SUPPORTED
UNSUPPORTED
UNRESOLVED_IDENTITY
```

when they are documented, non-critical for the iteration, and carried into I4 where appropriate.

---

## 46. Mandatory Quarkus Gates

Before I2 is complete:

```text
exact upstream SHA pinned
profile reproducible
ground truth frozen before AIP result
at least four REST provider contracts in scope where available
at least three REST caller dependencies investigated
at least one runtime-confirmed REST flow
gRPC boundary evaluated
Kafka topic boundary evaluated
OTel identity evaluated
all findings classified
all CRITICAL findings dispositioned
critical false supported facts = 0
```

---

## 47. Regression Coverage

Every production AIP fix accepted in I2 SHALL add deterministic regression coverage.

Preferred order:

```text
unit test
integration test
distilled validation fixture
```

Do not add the complete Quarkus repository to normal AIP unit/integration tests.

The full upstream system remains a separate validation run.

---

## 48. v0.2 Regression Gate

I2 SHALL preserve the v0.2 semantic baseline.

Required:

```bash
uv run python -m evaluation run
```

Expected:

```text
10/10 PASS
```

If a justified I2 fix changes an existing v0.2 semantic expectation, the parent v0.3 migration rule
applies:

```text
explicit decision record
explanation why old semantic was wrong
deliberate expected update
regression coverage
release-note entry
```

Silent weakening is prohibited.

---

## 49. Test and CI Gate

Before `v0.3.0-alpha.2`:

```text
ruff check                     PASS
ruff format --check            PASS
unit tests                     PASS
integration tests              PASS
v0.2 evaluation                PASS
I1 validation-contract tests   PASS
Quarkus comparison             reproducible
CI                             PASS
CodeQL                         PASS
dependency audit               PASS
```

Exact test counts are non-normative.

---

## 50. I2 Release Blockers

The following SHALL block `v0.3.0-alpha.2`:

```text
ground truth written or rewritten to match AIP output
unpinned upstream revision
qualifying run against moving main/latest
less than three REST caller paths investigated without documented upstream impossibility
gRPC silently mapped to an incorrect supported relation
Kafka topic silently asserted as Queue without approved semantic justification
invented supported REST relation
wrong supported relation direction
wrong runtime status with material impact
fabricated or lost evidence
critical identity misresolution producing false architecture
Quarkus-specific production hack
nondeterministic comparison result
unresolved CRITICAL finding
v0.2 evaluation regression without approved migration
```

Target:

```text
critical semantic errors = 0
I2 release blockers = 0
```

---

## 51. Non-Blocking Findings

The following may remain after I2:

```text
explicit gRPC UNSUPPORTED
explicit Kafka Topic UNSUPPORTED
non-critical MISSING_SUPPORTED findings
non-critical UNRESOLVED_IDENTITY findings
INSUFFICIENT_EVIDENCE items
deferred Topic/Subscription model proposal
deferred broader identity-model proposal
```

Each SHALL be visible in `findings.md`.

---

## 52. I2 Deliverables

I2 SHALL deliver at minimum:

```text
docs/real-world-validation/quarkus-super-heroes/upstream.md
docs/real-world-validation/quarkus-super-heroes/profile.md
docs/real-world-validation/quarkus-super-heroes/ground-truth.md
docs/real-world-validation/quarkus-super-heroes/expected.yaml
docs/real-world-validation/quarkus-super-heroes/runbook.md
docs/real-world-validation/quarkus-super-heroes/results.md
docs/real-world-validation/quarkus-super-heroes/findings.md
```

and, as required:

```text
evidence reference records
decision records
traffic scripts
OTel Collector config
small validation helper scripts
regression tests for accepted fixes
```

---

## 53. Suggested Delivery Split

I2 SHOULD be delivered through focused short-lived branches/PRs.

A practical split is:

### I2.1 — Upstream Pin and Ground Truth

```text
upstream.md
profile.md
ground-truth.md
expected.yaml
evidence references
ground-truth freeze
```

No qualifying AIP result in this task.

Suggested branch:

```text
docs/v0.3-i2-quarkus-ground-truth
```

### I2.2 — Reproducible Runtime Profile

```text
runbook
traffic script
OTel routing
OpenAPI capture/import preparation
clean-state procedure
```

Suggested branch:

```text
feat/v0.3-i2-quarkus-runtime-profile
```

No production semantic fix unless required for setup.

### I2.3 — First Comparison and Findings

```text
first qualifying run
actual result capture
deterministic comparison
results.md
findings.md
decision records
```

Suggested branch:

```text
docs/v0.3-i2-quarkus-results
```

### I2.4 — Quarkus Hardening and Revalidation

Only if required:

```text
approved general fixes
regression tests
clean-state rerun
repeatability verification
final I2 report
```

Suggested branch:

```text
fix/v0.3-i2-quarkus-hardening
```

If no production fix is required, this task may be documentation-only or omitted.

---

## 54. Ground-Truth Review Checklist

Before the first AIP comparison:

- [ ] Exact upstream SHA is full-length and immutable.
- [ ] All source references use pinned permalinks.
- [ ] REST operations were derived independently.
- [ ] Caller dependencies were derived independently.
- [ ] `grpc-locations` is not represented as HTTP.
- [ ] Kafka `fights` is described as a Kafka topic, not pre-labeled as Queue.
- [ ] Expected canonical IDs are normalization artifacts, not copied from AIP output.
- [ ] Unsupported mechanisms are explicit.
- [ ] Ambiguous items are excluded or marked insufficient evidence.
- [ ] No AIP result was used to create the expected set.

---

## 55. Definition of Done

I2 is complete when all mandatory conditions below are satisfied.

### Upstream

- [ ] `quarkusio/quarkus-super-heroes` is pinned to `8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce`.
- [ ] Apache-2.0 license is recorded.
- [ ] Upstream architecture references use pinned permalinks.
- [ ] The selected runtime profile is reproducible.

### Ground Truth

- [ ] `upstream.md` is complete.
- [ ] `profile.md` is complete.
- [ ] `ground-truth.md` is complete.
- [ ] `expected.yaml` is frozen before qualifying AIP output.
- [ ] At least three REST caller dependencies are independently investigated.
- [ ] REST provider operations in scope are independently established.
- [ ] gRPC is explicitly classified at the supported-scope boundary.
- [ ] Kafka `fights` topic semantics are explicitly classified at the supported-scope boundary.
- [ ] Ground truth is not derived from AIP output.

### Runtime

- [ ] Selected upstream services start from clean state.
- [ ] AIP starts from clean state.
- [ ] Required OpenAPI artifacts are captured/imported.
- [ ] OTLP reaches AIP.
- [ ] Validation environment/window is explicit.
- [ ] Deterministic traffic is executed.
- [ ] Runtime result capture succeeds.
- [ ] Cleanup succeeds.

### Comparison

- [ ] All expected supported facts are compared.
- [ ] Unexpected in-scope supported facts are surfaced.
- [ ] All material findings use the I1 vocabulary.
- [ ] Summary counters are deterministic.
- [ ] Repeated clean runs produce the same classifications and counts.

### Semantics

- [ ] No critical invented supported relation remains.
- [ ] No critical wrong direction remains.
- [ ] No critical wrong runtime status remains.
- [ ] No critical evidence defect remains.
- [ ] gRPC is not silently misrepresented.
- [ ] Kafka topic semantics are not silently mislabeled as Queue.
- [ ] Critical `INCORRECT_SUPPORTED` findings = `0`.

### Hardening

- [ ] Every material production change has a decision record.
- [ ] Every accepted fix is general, not Quarkus-specific.
- [ ] Every accepted fix has deterministic regression coverage.
- [ ] Major canonical redesign proposals are carried to I4 unless explicitly approved earlier.

### Regression / Quality

- [ ] v0.2 evaluation remains `10/10 PASS`.
- [ ] Unit tests are green.
- [ ] Integration tests are green.
- [ ] I1 validation-contract tests are green.
- [ ] Ruff is green.
- [ ] CI is green.
- [ ] CodeQL is green.
- [ ] Dependency audit is green.
- [ ] I2 release blockers = `0`.

---

## 56. Exit State

At the end of I2:

```text
I1 validation method
    FROZEN

Quarkus upstream
    PINNED

Quarkus independent ground truth
    FROZEN

Quarkus qualifying comparison
    COMPLETE

Quarkus findings
    CLASSIFIED

Critical Quarkus supported-semantic errors
    0

Airflow validation
    NOT STARTED

Cross-system model decision
    NOT FINAL
```

The Quarkus findings become input to I4.

They SHALL not be treated as proof that the same design decision is correct for Airflow.

---

## 57. Relationship to I3

I3 applies the same I1 methodology to Apache Airflow.

The purpose is intentionally different:

```text
Quarkus
    externally authored reference microservices
    close to current AIP domain

Airflow
    mature real-world OSS
    stronger identity and process-model stress test
```

I3 SHALL not weaken Quarkus findings merely because Airflow behaves differently.

Instead, I4 compares both bodies of evidence.

---

## 58. Relationship to I4

I4 receives:

```text
Quarkus findings
+
Airflow findings
```

and decides whether observed gaps imply:

```text
small implementation defect
identity-resolution hardening
runtime/evidence hardening
documented unsupported mechanism
future adapter capability
canonical-model change
```

The Quarkus Kafka topic and gRPC findings are expected to be especially useful inputs to this
cross-system decision.

---

## 59. Summary

I2 is AIP's first deliberate contact with an independently authored external architecture under a
frozen validation method.

The defining rules are:

```text
pin upstream
establish ground truth first
freeze expected facts
run AIP second
classify every material mismatch
prefer unsupported over wrong
fix only general defects
revalidate from clean state
```

The most important success criterion is not maximum coverage.

It is:

> **Within the semantics AIP claims to support, Quarkus Super Heroes must not reveal unresolved
> critical false architecture claims. Where the external system uses unsupported mechanisms such as
> gRPC or Kafka topic semantics, AIP must remain explicit rather than pretending those mechanisms
> are something else.**

`v0.3.0-alpha.2` is complete when the Quarkus validation is independently grounded, reproducible,
fully classified, and free of unresolved critical supported-semantic errors.
