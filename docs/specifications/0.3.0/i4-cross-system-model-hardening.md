# AIP v0.3.0 I4 Specification — Cross-System Model Hardening

## 1. Purpose

I4 converts the independent Quarkus Super Heroes and Apache Airflow validation results into one
evidence-based model-hardening decision for AIP.

I4 SHALL distinguish:

```text
system-specific behavior
        vs
general AIP model or implementation defect
```

It SHALL implement only general corrections justified by real-system evidence, add deterministic
regression coverage for every accepted semantic change, and revalidate:

```text
Quarkus Super Heroes
Apache Airflow
the v0.2 synthetic evaluation suite
```

The target release identity is `v0.3.0-rc.1`.

I4 is not a feature-expansion iteration. It exists to determine whether the current Canonical
Architecture Model and runtime/evidence semantics remain defensible after two deliberately
different real-system validations.

---

## 2. Normative Language

The key words `SHALL`, `SHALL NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` are normative.

Where this specification conflicts with the frozen v0.3 validation contract, the contract takes
precedence:

```text
docs/specifications/0.3.0/specification.md
docs/specifications/0.3.0/i1-real-world-validation-contract.md
```

I4 SHALL not weaken or retrospectively reinterpret the I1 finding vocabulary, ground-truth
independence rules, supported-scope rules, or comparator semantics.

---

## 3. I4 Release Identity

I4 SHALL produce an exact candidate identity containing:

```text
AIP candidate commit SHA
complete dependency lock
Quarkus upstream SHA and complete profile revision
Airflow upstream SHA and complete profile revision
all qualifying image digests
all qualifying provider/instrumentation versions
comparison-tool revision
ground-truth revisions
```

The same identities SHALL appear in the I4 report and the `v0.3.0-rc.1` qualification record.
Content equivalence between different commits SHALL NOT substitute for literal candidate identity.

---

## 4. Entry Criteria

I4 SHALL begin only when:

- I1 is complete and its methodology remains frozen.
- I2 is complete and the Quarkus dossier is committed.
- I3 is complete and the Airflow dossier is committed.
- The I3 post-merge auditability correction explicitly binds both qualifying §59 runs to the same
  Airflow upstream SHA, AIP candidate SHA, full profile revision, image digests, and
  provider/instrumentation versions.
- All critical I2 and I3 findings are dispositioned.
- Both systems report zero material `INCORRECT_SUPPORTED` findings.
- The v0.2 deterministic evaluation is green.
- Unit tests, integration tests, Ruff, dependency audit, CI, and CodeQL are green on the I4 base.

If an entry criterion is not met, I4 SHALL remain blocked. It SHALL not absorb unfinished I2 or I3
qualification work and then describe it as cross-system hardening.

---

## 5. Frozen Evidence Inputs

Mandatory inputs:

```text
docs/real-world-validation/quarkus-super-heroes/
docs/real-world-validation/apache-airflow/
evaluation/
docs/specifications/0.3.0/
```

I4 starts from these qualifying results:

### Quarkus Super Heroes

```text
CORRECT                38
UNSUPPORTED             2
INSUFFICIENT_EVIDENCE   1
MISSING_SUPPORTED       0
INCORRECT_SUPPORTED     0
UNRESOLVED_IDENTITY     0
```

### Apache Airflow

```text
CORRECT                 9
UNSUPPORTED             3
UNRESOLVED_IDENTITY     2
INSUFFICIENT_EVIDENCE   1
MISSING_SUPPORTED       0
INCORRECT_SUPPORTED     0
```

These counts are inputs, not permanent expected outputs. An approved semantic correction MAY change
an in-scope result, but I4 SHALL explain the migration and preserve an auditable before/after
record. Ground truth SHALL never be changed merely to make a candidate pass.

---

## 6. Mandatory Finding Inventory

I4 SHALL create one normalized ledger covering at least:

| Finding | Current classification | I4 question |
|---|---|---|
| Quarkus gRPC locations dependency | `UNSUPPORTED` | Confirm that no v0.3 model change is justified. |
| Quarkus Kafka `fights` topic | `UNSUPPORTED` | Decide whether Queue semantics remain safe and bounded. |
| Quarkus legacy `messaging.operation: publish` | `INSUFFICIENT_EVIDENCE` | Decide whether safe semantic-convention normalization is justified. |
| Airflow PostgreSQL dependencies | `UNSUPPORTED` | Decide whether database relations remain future scope. |
| Airflow Execution API boundary | `UNRESOLVED_IDENTITY` | Decide whether leaving the boundary unresolved is semantically safe. |
| Airflow runtime-role identity | `UNRESOLVED_IDENTITY` | Decide whether role/instance distinctions require a v0.3 model change. |
| Airflow Celery messaging runtime status | `INSUFFICIENT_EVIDENCE` | Decide whether current identity and messaging qualification remain safe. |

The ledger SHALL also include every decision record referenced by either dossier and any new
material finding discovered during I4.

Each entry SHALL record:

```text
finding id
source system(s)
independent evidence references
current classification and severity
claimed AIP semantic scope
cross-system relevance
candidate disposition
decision record
production impact
test impact
validation impact
final disposition
```

---

## 7. I4 Decision Vocabulary

Every material finding SHALL receive exactly one disposition:

```text
FIX
DOCUMENT_UNSUPPORTED
DEFER
NO_CHANGE
```

- `FIX`: a general defect or safely correctable semantic gap is demonstrated and corrected.
- `DOCUMENT_UNSUPPORTED`: the mechanism is deliberately outside current AIP semantics.
- `DEFER`: a plausible future capability or model change lacks sufficient evidence or safe scope.
- `NO_CHANGE`: current behavior is already correct for the claimed scope.

`DEFER` SHALL name the missing evidence or prerequisite. `NO_CHANGE` SHALL explain why current
semantics are safe; absence of a critical failure alone is insufficient.

---

## 8. Production-Change Admission Gate

Before any production change, its decision record SHALL demonstrate:

```text
independent real-system evidence
general applicability
compatibility with the I1 finding contract
no invented canonical identity
no unsupported-to-supported coercion
deterministic regression strategy
Quarkus impact assessment
Airflow impact assessment
v0.2 evaluation impact assessment
migration/documentation impact
```

A change justified by one system MAY be accepted only when it corrects a general semantic-
convention compatibility defect or prevents an objectively false supported fact, and when the rule
can be tested independently of upstream-specific names and topology.

Production code SHALL NOT contain behavior such as:

```text
if system == "airflow"
if framework == "quarkus"
if destination == "fights"
if queue == "default"
if service name starts with an upstream-specific prefix
```

System-specific logic MAY exist only in profiles, traffic generators, dossier capture, fixtures,
and independently authored comparison inputs.

---

## 9. Mandatory Cross-System Questions

I4 SHALL answer with explicit evidence:

1. Does canonical `Service` remain adequate for the supported v0.3 scope?
2. Is a runtime role/instance distinction needed to prevent a false supported claim, or is
   `UNRESOLVED_IDENTITY` the safe result?
3. Can legacy and current OpenTelemetry messaging-operation attributes be normalized without
   widening unsupported mechanisms into Queue semantics?
4. Is `Queue` safe for competing-consumer queues while excluding topic/subscription semantics?
5. Are resolved logical sender and consumer identities prerequisites for `SENDS` and
   `RECEIVES_FROM`?
6. Does runtime evidence/status handling lose, fabricate, or overstate evidence?
7. Do database dependencies require an immediate canonical relation family for correctness?
8. Does any finding require a fundamental Canonical Model redesign before v0.4?

Every answer SHALL distinguish:

```text
model capability
discovery capability
telemetry availability
identity resolution
supported-scope qualification
```

A discovery limitation SHALL NOT automatically be labeled a model defect.

---

## 10. Messaging Semantics Decision

Quarkus and Airflow messaging findings SHALL be evaluated together.

### 10.1 Operation-attribute compatibility

I4 SHALL decide whether AIP should recognize both:

```text
messaging.operation.type
messaging.operation
```

Recognition MAY be widened only if:

- relevant OpenTelemetry meanings are mapped explicitly;
- supported producer/consumer values are allowlisted;
- conflicting attributes have deterministic precedence;
- missing or unknown values remain unresolved or ignored rather than guessed;
- destination identity remains low-cardinality;
- regression tests cover current, legacy, conflicting, missing, and unknown forms;
- recognition does not itself convert a Kafka topic into a canonical Queue.

### 10.2 Queue-versus-topic safety

I4 SHALL preserve:

```text
recognized telemetry
        !=
qualified canonical Queue semantics
```

A messaging span SHALL produce `SENDS` or `RECEIVES_FROM` only when destination kind and
interaction semantics are safely compatible with the current Queue model.

If topic/subscription semantics cannot be represented without semantic loss, I4 SHALL retain or
strengthen `DOCUMENT_UNSUPPORTED` and SHALL NOT introduce an approximate Queue relation.

### 10.3 Identity prerequisites

I4 SHALL decide whether an observed messaging relation requires a safely resolved logical sender or
consumer. Ambiguous Airflow identities SHALL not be repaired using name, hostname, container, or
queue-specific heuristics.

Where evidence cannot establish direction and identity independently, the result SHALL remain
`UNRESOLVED_IDENTITY` or `INSUFFICIENT_EVIDENCE`.

---

## 11. Service, Role, and Instance Identity Decision

I4 SHALL evaluate whether Airflow role/instance evidence and Quarkus service evidence justify a
canonical identity change.

The default is preservation of the current model unless evidence demonstrates a false supported
claim or both systems require the same general distinction.

Adding any of these is a major canonical change:

```text
Process
RuntimeRole
Deployment
ServiceInstance
new identity hierarchy
```

Such a change SHALL enter I4 only if:

- required for correctness inside frozen v0.3 scope;
- justified beyond one upstream naming convention;
- identifiers and reconciliation rules can be deterministic;
- declared and observed identities can reconcile without guessing;
- graph, API, analysis, and adapter impacts are bounded;
- both dossiers can be updated without deriving ground truth from AIP output;
- full qualification is feasible before `v0.3.0-rc.1`.

Otherwise I4 SHALL document and defer the richer identity model.

---

## 12. Unsupported-Mechanism Decisions

I4 SHALL explicitly disposition:

```text
gRPC/protobuf calls
Kafka topic/subscription semantics
PostgreSQL/database dependencies
private Execution API caller identity
Airflow runtime-role identity
```

Explicit unsupported or unresolved behavior is acceptable when AIP makes no incorrect supported
claim.

I4 SHALL NOT add unrelated adapter or entity families, including Kubernetes discovery, a gRPC
adapter, Kafka Connect, a Topic/Subscription family, or a Database family, unless required to
remove a release-blocking false claim that cannot be addressed by a narrower general safety fix.
Such an exception requires an approved specification amendment before implementation.

---

## 13. Canonical Redesign Gate

I4 SHALL answer:

```text
Does any unresolved finding require a fundamental
Canonical Model redesign before v0.4?
```

Permitted answers:

```text
NO — current supported claims remain semantically correct;
     limitations are explicit and bounded.

YES — a false supported claim or fundamental invariant failure
      cannot be fixed safely within the current model.
```

`YES` blocks `v0.3.0-rc.1` until the redesign is specified, implemented, regression-tested, and
both systems are revalidated. Missing optional capability is not a redesign requirement.

---

## 14. Permitted Hardening Categories

Approved production work SHALL be limited to:

```text
general identity-resolution correction
general operation-resolution correction
OTel semantic-convention compatibility correction
runtime/evidence correctness correction
supported-scope safety guard
determinism correction
unsupported-boundary documentation
```

Every code change SHALL map to a finding and decision record. Unmapped production changes SHALL be
removed. Refactoring MAY be included only when required to implement or test an approved correction.

---

## 15. Decision Records and Dossier

Recommended structure:

```text
docs/real-world-validation/cross-system/
├── README.md
├── finding-ledger.md
├── decisions/
│   ├── messaging-operation-compatibility.md
│   ├── queue-topic-boundary.md
│   ├── runtime-role-identity.md
│   └── canonical-redesign-gate.md
├── regression-map.md
├── revalidation.md
└── report.md
```

Each material `FIX`, `DEFER`, or redesign-gate decision SHALL record:

```text
context
independent evidence
alternatives
decision
general semantic rule
consequences
production changes
regression coverage
Quarkus impact
Airflow impact
deferred work
```

---

## 16. Ground-Truth Change Control

Quarkus and Airflow ground truth remains independently authored.

An I4 correction MAY require a ground-truth update only when it changes explicitly claimed scope or
fixes a documented oracle error. Any update SHALL:

- derive from pinned upstream source/configuration or independent raw evidence;
- be committed and reviewed before qualifying AIP output is captured;
- explain the old and new expectation;
- never copy or transform AIP output into `expected.yaml`;
- preserve original I2/I3 results for auditability.

If supported-scope semantics do not change, frozen `expected.yaml` files SHOULD remain
byte-identical.

---

## 17. Distilled Regression Coverage

Every accepted semantic fix SHALL have deterministic tests independent of running Quarkus or
Airflow.

### Messaging coverage

- current `messaging.operation.type` producer/consumer forms;
- legacy `messaging.operation` producer/consumer forms;
- compatible and conflicting dual attributes;
- missing and unknown operations;
- Queue, topic, and missing destination kind;
- unresolved sender and consumer identity;
- proof that unsupported topics do not emit Queue relations.

### Identity coverage

- multiple runtime instances of one safely resolved logical service;
- distinct roles sharing an unhelpful `service.name`;
- ambiguous identity remaining unresolved;
- no hostname/container-name promotion to canonical `Service`;
- no false merge or split producing supported claims.

### Evidence/status coverage

- declared and observed evidence remain independent;
- reconciliation loses or fabricates no evidence;
- normalization fabricates no evidence;
- runtime status stays deterministic;
- observation-window and coverage qualification remain intact.

Tests SHALL assert canonical facts and evidence semantics, not upstream-specific logs or names.

---

## 18. Synthetic Evaluation Gate

The complete v0.2 suite SHALL pass after every accepted semantic change and at the final candidate:

```bash
uv run python -m evaluation run
```

Expected result unless an approved semantic migration changes the suite:

```text
Scenarios: 10
Passed: 10
Failed: 0
Missing facts: 0
Unexpected facts: 0
Forbidden facts: 0
Wrong statuses: 0
Evidence errors: 0
```

An approved migration SHALL update independent expectations before candidate capture and explain why
the old result was wrong. Silent fixture adjustment is prohibited.

---

## 19. Real-System Revalidation

I4 SHALL revalidate both systems against the final candidate using their pinned upstream revision,
committed profile, independent ground truth, and bounded supported scope.

### Quarkus

Execute mandatory REST/runtime traffic and any messaging diagnostic required by an accepted I4
messaging correction.

### Airflow

Execute the deterministic DAG, REST traffic, telemetry drain, capture, comparison, and cleanup.
Diagnostic Celery instrumentation MAY be used only in the dossier's separated diagnostic phase; it
SHALL NOT silently alter the frozen native profile.

### No substitution

A source diff or content-equivalence argument SHALL NOT replace either real-system execution. I4
explicitly requires both systems to be revalidated against the final candidate.

---

## 20. Revalidation Identity and Repeatability

For each system I4 SHALL record:

```text
AIP candidate SHA
upstream SHA
complete profile revision
ground-truth revision
comparison-tool revision
dependency lock identity
image digests
provider/instrumentation versions
environment
window_start
window_end
actual-facts artifact SHA-256
comparator report SHA-256
```

Both normative revalidations SHALL use the literal candidate proposed for `v0.3.0-rc.1`.

If production code, validation code, profile, ground truth, or comparator changes afterward, all
affected runs SHALL be repeated. A `git diff` equivalence argument SHALL NOT substitute for final-
candidate execution.

At least two clean executions per system SHOULD have identical semantic results. Where operational
nondeterminism prevents byte-identical artifacts, reports SHALL identify nondeterministic fields and
prove canonical facts, classifications, and counters remain identical.

---

## 21. Deterministic Cross-System Report

I4 SHALL publish separate Quarkus and Airflow counts:

```text
Expected supported facts
Correct
Missing supported
Incorrect supported
Unsupported constructs
Unresolved identities
Insufficient-evidence items
Critical semantic errors
```

It SHALL also contain:

```text
input finding ledger
final disposition of every material finding
accepted production changes
regression-test mapping
before/after semantics
known limitations
canonical-redesign gate answer
release blockers
exact candidate identity
```

No weighted or composite accuracy score is permitted.

Ordering SHALL be deterministic by system, classification, severity, relation type, source, target,
and finding id.

---

## 22. Quality Gates

The final candidate SHALL pass:

```text
Ruff lint and format
unit tests
integration tests
I1 validation-contract tests
v0.2 deterministic evaluation
Quarkus supported-scope comparison
Airflow supported-scope comparison
dependency audit
CodeQL Python and Actions
CI
```

Recommended local commands:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit -q
uv run pytest tests/integration -q
uv run python -m evaluation run
```

Exact commands and results SHALL be committed in the I4 report.

---

## 23. Release Blockers

The following block `v0.3.0-rc.1`:

```text
material INCORRECT_SUPPORTED finding
wrong relation direction
invented canonical identity
false identity merge or split producing a supported claim
wrong runtime status
lost or fabricated evidence
unsupported mechanism coerced into a supported relation
ground truth derived from AIP output
system-specific production workaround
unrecorded semantic change
accepted fix without deterministic regression coverage
Quarkus or Airflow revalidation failure
v0.2 evaluation failure without approved migration
nondeterministic qualifying comparison
unbound candidate/profile/upstream identity
fundamental redesign required before v0.4
red CI, CodeQL, or dependency audit
```

Targets:

```text
Critical semantic errors = 0
Release blockers = 0
```

---

## 24. Non-Blocking Outcomes

These do not automatically block I4 when explicit and safely bounded:

```text
gRPC remains unsupported
Kafka topic/subscription semantics remain unsupported
PostgreSQL dependencies remain unsupported
Airflow role identity remains unresolved rather than guessed
Celery sender/consumer identity remains unresolved
non-critical accepted missing supported fact
future adapter/model proposal with no false current claim
```

A non-blocking label SHALL NOT hide a material incorrect supported claim.

---

## 25. Deliverables

I4 SHALL deliver:

1. This reviewed implementation specification.
2. A normalized cross-system finding ledger.
3. Decision records for material `FIX`, `DEFER`, and redesign-gate decisions.
4. Any approved general production corrections.
5. Distilled deterministic tests for every accepted correction.
6. Updated semantic and known-limitations documentation where required.
7. Clean Quarkus revalidation against the final candidate.
8. Clean Airflow revalidation against the final candidate.
9. Green v0.2 synthetic evaluation against the final candidate.
10. A deterministic cross-system report.
11. Updated `ROADMAP.md`, `README.md`, `CHANGELOG.md`, and v0.3 specification index.
12. The current post-v0.3 release sequence with explicitly non-normative dates.
13. Exact `v0.3.0-rc.1` candidate identity and GO/NO-GO handoff to I5.

---

## 26. Roadmap Update and Next Releases

I4 SHALL update the public roadmap before RC qualification. The update SHALL make the current
delivery track visible rather than leaving v0.3 hidden under a generic `v0.3+` heading.

At minimum:

- `ROADMAP.md` SHALL describe v0.3 as the real-world validation and cross-system hardening release.
- I1–I3 SHALL be marked complete, I4 SHALL show its actual status, and I5 SHALL remain pending until
  release qualification is complete.
- `README.md` Project Status SHALL reflect the I4/I5 state without claiming that v0.3 has shipped
  before the final release.
- `CHANGELOG.md` SHALL record approved I4 changes under `[Unreleased]`; it SHALL NOT create a
  dated `[0.3.0]` section before I5 publishes the release.
- `docs/specifications/0.3.0/README.md` SHALL link this I4 specification and show the actual
  iteration/release status.

### 26.1 Required v0.3 roadmap entry

The updated roadmap SHALL describe:

```text
v0.3 — Real-World Validation and Cross-System Hardening

I1  validation contract
I2  Quarkus Super Heroes validation
I3  Apache Airflow validation
I4  cross-system model hardening
I5  exact-candidate release qualification
```

It SHALL preserve the release mapping:

```text
I1 -> v0.3.0-alpha.1
I2 -> v0.3.0-alpha.2
I3 -> v0.3.0-alpha.3
I4 -> v0.3.0-rc.1
I5 -> v0.3.0
```

Only artifacts actually published SHALL be described as shipped releases. Completed internal
iterations without a corresponding tag SHALL be described as completed iteration work, not as a
published release.

### 26.2 Next-release sequence

The roadmap SHALL use the following ordered planning baseline:

#### v0.4 — Architecture Intelligence Tools

Purpose:

```text
Expose the validated semantic core through stable, evidence-backed tool contracts.
```

Planned scope:

```text
ArchitectureIntelligenceService
structured evidence-backed query contracts
read-only MCP tools
deterministic tool evaluation
```

The tool layer SHALL remain downstream of AIP's deterministic architecture model. It SHALL NOT
allow an LLM or MCP client to create canonical facts, bypass semantic validation, or access a graph
write path.

Every structured result SHOULD expose the evidence and qualification needed to explain why AIP
returned it. Deterministic tool evaluation SHALL cover contract shape, semantic correctness,
evidence linkage, read-only enforcement, and stable ordering.

#### v0.5 — Broader Architecture Discovery

Purpose:

```text
Broaden what AIP can discover only after the semantic core
has been validated and exposed through controlled tools.
```

Planned scope:

```text
Kubernetes discovery
additional source adapters
deeper runtime discovery
reconciliation with existing declared and observed evidence
```

Kubernetes is therefore a v0.5 discovery candidate, not a v0.4 deliverable.

Each new discovery source SHALL map through the shared Canonical Model, retain provenance, avoid
environment-specific identity leakage, and prove that it does not create supported relations from
mere co-location or naming coincidence.

Additional adapter families SHALL require an accepted proposal and deterministic conformance tests.
Candidate adapters MAY include gRPC/protobuf definitions and Kafka Connect configuration, but the
roadmap SHALL not promise a specific adapter before its semantics and validation profile are
approved.

Deeper runtime discovery SHALL preserve the current safety rules:

```text
non-observation != absence
unresolved identity > guessed identity
explicitly unsupported > incorrectly represented as supported
```

#### v0.9 — Contract Freeze / Production Qualification

Purpose:

```text
Stabilize public contracts and qualify the platform for production-grade use.
```

Planned scope:

```text
Canonical Model compatibility review
REST and MCP contract stabilization
Graph Schema stabilization
Adapter SPI stabilization
configuration-format stabilization
migration and deprecation rules
security and production-operability qualification
performance and resilience qualification
release/support policy
```

v0.9 SHALL define the exact compatibility promises intended for v1.0. Any known breaking redesign
required for the stable contract SHALL be completed before the v1.0 candidate is frozen.

#### v1.0 — Stable Architecture Intelligence Platform

Purpose:

```text
Publish the first stable AIP release with mature architecture-intelligence
semantics and public contracts.
```

The v1.0 release SHALL require:

```text
stable architecture-intelligence model
stable public REST and MCP contracts
stable Graph Schema and Adapter SPI
documented compatibility and migration policy
production qualification completed
critical semantic errors = 0
release blockers = 0
```

Versions between v0.5 and v0.9 remain intentionally unspecified. Their scope SHALL be derived from
validated user/tool experience and discovery findings rather than invented during I4.

### 26.3 Sequencing principle

The roadmap SHALL state the governing sequence explicitly:

```text
validate the semantic core first
        |
        v
expose it as evidence-backed tools second
        |
        v
broaden discovery third
        |
        v
freeze and qualify the public contracts
```

In release terms:

```text
v0.3 validation and hardening
  -> v0.4 architecture-intelligence tools
  -> v0.5 broader discovery
  -> v0.9 contract freeze and production qualification
  -> v1.0 stable platform
```

v0.3 has a hard gate: if Quarkus or Airflow evidence shows that the Canonical Architecture Model
requires a fundamental breaking redesign, AIP SHALL NOT proceed to v0.4 until that redesign is
specified, implemented, and revalidated.

The roadmap SHALL explicitly state that release scopes are a planning sequence, not committed dates.

### 26.4 Roadmap consistency gate

The four public planning surfaces SHALL agree:

| File | Required state at I4 exit |
|---|---|
| `ROADMAP.md` | v0.3 track and current v0.4/v0.5/v0.9/v1.0 sequence documented |
| `README.md` | current project status and next milestone stated accurately |
| `CHANGELOG.md` | accepted I4 changes under `[Unreleased]` |
| `docs/specifications/0.3.0/README.md` | I4 specification linked and iteration status current |

Contradictory release status across these files SHALL block I4.5.

---

## 27. Suggested Delivery Split

### I4.1 — Finding Consolidation and Decision Freeze

Deliver the ledger, evidence links, messaging/identity/unsupported-boundary decisions, redesign-gate
answer, and approved production-change list.

Gate:

```text
No production semantic change begins before its decision record is approved.
```

### I4.2 — General Model and Runtime Hardening

Implement only I4.1-approved corrections. Each needs a general semantic rule, implementation,
regression coverage, and documentation/migration note.

If no production correction is approved, I4.2 SHALL record an evidence-backed `NO_CHANGE` rather
than manufacture hardening work.

### I4.3 — Distilled Regression and Synthetic Revalidation

Deliver the finding-to-test map, distilled tests, v0.2 result, unit/integration/I1 contract results,
and determinism verification.

### I4.4 — Final-Candidate Real-System Revalidation

Deliver clean Quarkus and Airflow runs against the same final candidate, actual-facts/report hashes,
comparison reports, final dispositions, and known limitations.

### I4.5 — RC Qualification

Deliver the final cross-system report, Definition of Done, blocker assessment, GO/NO-GO, exact
candidate/tag identity, updated roadmap/public project status, next-release sequence, and I5 handoff.

I4.5 SHALL introduce no new semantics. Any semantic change reopens affected I4.2–I4.4 gates.

---

## 28. Definition of Done

### Entry and evidence

- [ ] I1 methodology remains frozen.
- [ ] I2 and I3 dossiers are complete.
- [ ] The I3 run-identity auditability correction is committed.
- [ ] Exact I4 base and input revisions are recorded.

### Cross-system decisions

- [ ] Every material finding appears in the ledger and has one final disposition.
- [ ] Messaging attribute compatibility is decided.
- [ ] Queue-versus-topic safety and identity prerequisites are decided.
- [ ] Service/role/instance identity is decided.
- [ ] gRPC and database boundaries are decided.
- [ ] The fundamental redesign gate is answered.
- [ ] Known limitations are explicit.

### Hardening

- [ ] Every production change maps to independent evidence.
- [ ] Every accepted rule is general and system-independent.
- [ ] No unsupported mechanism is represented as supported.
- [ ] No ambiguous identity is guessed.
- [ ] No unrelated adapter/entity family is introduced.
- [ ] Every accepted fix has deterministic regression coverage.
- [ ] Any no-change conclusion is evidence-backed.

### Regression and quality

- [ ] Unit, integration, and I1 contract tests are green.
- [ ] Ruff lint and format are green.
- [ ] v0.2 deterministic evaluation is green.
- [ ] Dependency audit, CI, and CodeQL are green.

### Real-system revalidation

- [ ] Quarkus and Airflow are revalidated from clean state against the final candidate.
- [ ] Exact upstream, candidate, profile, image, and instrumentation identities are recorded.
- [ ] Qualifying artifact and report hashes are recorded.
- [ ] Comparator output is deterministic.
- [ ] All findings are dispositioned.
- [ ] Material `INCORRECT_SUPPORTED` findings = `0`.
- [ ] Critical semantic errors = `0`.

### Release candidate

- [ ] The deterministic cross-system report is committed.
- [ ] Release blockers = `0`.
- [ ] GO/NO-GO names the exact candidate.
- [ ] `v0.3.0-rc.1` points to the approved candidate.
- [ ] I5 receives candidate identity, dossiers, reports, limitations, and commands.

### Roadmap and public status

- [ ] `ROADMAP.md` contains the v0.3 I1–I5 delivery track and actual iteration status.
- [ ] `ROADMAP.md` identifies v0.4 as Architecture Intelligence Tools.
- [ ] `ROADMAP.md` places Kubernetes and broader discovery in v0.5, not v0.4.
- [ ] `ROADMAP.md` identifies v0.9 as Contract Freeze / Production Qualification.
- [ ] `ROADMAP.md` identifies v1.0 as the first stable platform release.
- [ ] Versions between v0.5 and v0.9 remain intentionally unspecified.
- [ ] The validate → tools → discovery sequencing principle is explicit.
- [ ] The fundamental-redesign gate blocks progression from v0.3 to v0.4 when triggered.
- [ ] `README.md` Project Status matches the actual I4/I5 state.
- [ ] `CHANGELOG.md` records I4 under `[Unreleased]` without prematurely declaring v0.3 shipped.
- [ ] `docs/specifications/0.3.0/README.md` links this specification and reflects current status.
- [ ] The four public planning surfaces contain no contradictory release claims.

---

## 29. Exit State

I4 is complete when:

```text
all material cross-system findings are dispositioned
all approved general corrections are implemented
all accepted fixes have deterministic regression coverage
Quarkus is revalidated
Airflow is revalidated
v0.2 evaluation is green
critical semantic errors = 0
release blockers = 0
v0.3.0-rc.1 identifies the exact approved candidate
```

The report SHALL state:

```text
GO — proceed to I5 release qualification
NO-GO — return to the named I4 work package
```

---

## 30. Relationship to I5

I5 SHALL introduce no new model semantics.

I4 hands I5:

```text
exact candidate SHA and dependency lock
Quarkus and Airflow qualifying identities
final ledger and decision records
regression map
real-system comparison reports
known limitations
canonical-redesign gate answer
GO / NO-GO record
updated roadmap and public project status
post-v0.3 release-planning baseline
```

If I5 requires a production semantic change, affected I4 decision, regression, and real-system
revalidation gates SHALL reopen. The changed commit is a new candidate.

---

## 31. Summary

```text
Quarkus findings
        +
Airflow findings
        |
        v
cross-system decisions
        |
        v
only justified general corrections
        |
        v
distilled deterministic regressions
        |
        v
Quarkus + Airflow + synthetic revalidation
        |
        v
v0.3.0-rc.1
```

The governing rule remains:

```text
correct but incomplete
        >
complete-looking but wrong
```

I4 succeeds by proving that AIP's supported claims remain semantically correct across both real
systems, not by maximizing modeled surface area.
