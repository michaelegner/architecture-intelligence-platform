# AIP v0.4.0 — I3 Drift Capability and Deterministic Qualification

**Status:** Draft 1 — self-contained implementation contract  
**Target release:** `v0.4.0`  
**Release increment:** I3  
**Target repository path:** `docs/specifications/0.4.0/i3-drift-capability-and-deterministic-qualification.md`  
**Entry baseline:** `main` at `302fc3759eea144780bba26049edb40f7126f041`  
**Qualified I1 candidate:** `8031f640daac3067ba9e709b19464d8246959fe2`  
**Qualified I2 candidate:** `da5602524ca375b178922fab4f1c21016f3971d1`  
**Governing specification:** `docs/specifications/0.4.0/specification.md`, Draft 1.2 semantics  
**Primary outcome:** The third bounded architecture tool exposes declared-versus-observed drift without
creating a second semantic engine, and the complete three-tool surface is qualified deterministically
against independently authored synthetic expectations plus immutable v0.3 real-system-derived evidence.

---

## 1. Purpose

I1 established the product-facing semantic boundary:

```text
ArchitectureIntelligenceService
    -> deterministic direct dependency answer
    -> qualification
    -> evidence references
    -> observation context
    -> virtual current-state snapshot
```

I2 exposed that boundary through one stateless MCP endpoint and added snapshot-bound evidence
drill-down:

```text
independent MCP client
    -> get_service_dependencies
    -> ArchitectureAnswer<ServiceDependenciesData>
    -> get_evidence
    -> ArchitectureAnswer<EvidenceData>
```

I3 completes the bounded `v0.4.0` tool surface.

It SHALL prove:

> **Given one known service and one explicit observation context, a caller can ask which of that
> service's supported direct dependencies are architecturally drifting, receive only the existing
> dependency claims whose qualification is `OBSERVED_ONLY` or `NOT_OBSERVED_IN_WINDOW`, and resolve
> the same snapshot-bound evidence that justifies those claims.**

I3 then qualifies the complete three-tool surface:

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

through deterministic synthetic scenarios, immutable v0.3 real-system-derived inputs, two complete
clean-state evaluation passes, and the release hero demo.

I3 MUST NOT invent a second drift interpretation.

The central invariant is:

```text
drift answer
    =
bounded view of the already-qualified dependency answer
```

not:

```text
drift answer
    =
new analysis that re-derives declared-vs-observed semantics
```

---

## 2. Normative Language and Precedence

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The parent `v0.4.0` release specification governs whenever this document is silent.

The executable I1/I2 schemas and merged behavior are frozen input to I3.

If this specification cannot be implemented without changing:

```text
dependency claim identity
destination resolution
delivery semantics
qualification semantics
evidence semantics
observation-context identity
snapshot fingerprinting
stable-read retry semantics
MCP protocol semantics
```

implementation SHALL stop and record the blocker instead of introducing an I3-only interpretation.

---

## 3. Entry Conditions

I3 starts from fully implemented and merged I1 and I2.

The repository baseline is:

```text
main:
    302fc3759eea144780bba26049edb40f7126f041

I1 qualified candidate:
    8031f640daac3067ba9e709b19464d8246959fe2

I2 qualified candidate:
    da5602524ca375b178922fab4f1c21016f3971d1
```

The following are frozen facts at I3 entry:

### I1

```text
ArchitectureIntelligenceService
    sole product-facing semantic entry point

get_service_dependencies
    direct outgoing dependencies only
    one hop
    maximum 500 unique claims
    zero graph writes

DependencyClaim
    subject
    DIRECT_DEPENDENCY predicate
    destination independent from delivery
    qualification
    optional coverage
    evidence_refs
    resolution_evidence_refs
    deterministic claim_id

Qualification
    CONFIRMED
    OBSERVED_ONLY
    NOT_OBSERVED_IN_WINDOW
```

### I2

```text
MCP protocol
    2026-07-28

transport
    one stateless Streamable HTTP endpoint

public tools
    get_evidence
    get_service_dependencies

get_evidence
    explicit snapshot required
    1..20 opaque evidence references
    sanitized provenance
    no architecture claim creation

independent client
    real HTTP listener
    production wiring
    no app.* imports
    no LLM key
    semantic differences from direct service = 0
    graph writes = 0
```

I3 SHALL preserve all of these behaviors.

---

## 4. Scope Budget

I3 has a fixed budget.

| Area | I3 limit |
|---|---|
| New service operations | Exactly one: `get_architecture_drift` |
| New public MCP tools | Exactly one |
| Public tools after I3 | Exactly three |
| New result payloads | One: `ArchitectureDriftData` |
| New request payloads | One: `ArchitectureDriftRequest` |
| Drift scope | Direct outgoing dependency claims of one service |
| Drift states | `OBSERVED_ONLY`, `NOT_OBSERVED_IN_WINDOW` |
| Confirmed claims in drift output | Zero |
| Dependency depth | I1 one-hop scope, unchanged |
| Result bound | I1 500-candidate bound, unchanged |
| Snapshot model | I1 virtual current-state snapshot, unchanged |
| Observation-context model | I1 normalized explicit context, unchanged |
| New Canonical Model entities/relations | Zero |
| New architecture-analysis algorithms | Zero |
| Graph mutations | Zero |
| MCP transport | Existing Streamable HTTP only |
| MCP protocol | Existing `2026-07-28` only |
| LLM usage for correctness | Zero |
| New evaluation framework | Zero; generalize the I1 architecture-answer suite |
| Fresh Quarkus/Airflow runs | Zero by default |
| Hero demo | One bounded five-minute path |

A fourth tool, transitive traversal, generic graph querying, a new discovery source, or a new
architecture model relation is outside I3.

---

## 5. In Scope

I3 SHALL deliver:

1. `ArchitectureDriftRequest`.
2. `ArchitectureDriftData`.
3. `ArchitectureAnswer<ArchitectureDriftData>` as a third executable answer specialization.
4. A frozen `drift-answer.schema.json`.
5. `ArchitectureIntelligenceService.get_architecture_drift`.
6. One thin MCP adapter for `get_architecture_drift`.
7. Deterministic three-tool discovery.
8. Direct-service/MCP equivalence for the drift tool.
9. Snapshot-bound evidence drill-down from drift claims.
10. Negative and failure-semantic drift scenarios.
11. Generalization of the existing architecture-answer evaluator to all three tools.
12. Two complete clean-state deterministic evaluation passes.
13. Qualification against immutable Quarkus and Airflow v0.3 artifacts or explicitly derived fixtures.
14. The five-minute `service:order-service` hero demo.
15. One machine-readable I3 evaluation result suitable for I4 release-candidate qualification.
16. A concise update to the `0.4.0` status index and MCP usage/demo documentation.

---

## 6. Explicit Non-Goals

I3 SHALL NOT implement:

```text
new declared-vs-observed semantics
new runtime status values
numeric confidence
generic drift scoring
drift severity
policy violations
architecture compliance rules
transitive drift
blast radius through MCP
snapshot diffing
historical architecture comparison
cross-snapshot drift
new Canonical Model nodes
new Canonical Model relation families
materialized DRIFT or DEPENDS_ON relations
generic graph/Cypher access
new source adapters
Kubernetes discovery
fresh Quarkus or Airflow execution by default
authentication
multi-tenancy
audit-control-plane features
MCP resources/prompts/tasks/subscriptions
another MCP transport
LLM-generated architecture explanation
agent orchestration
production-scale performance qualification
published-artifact verification
v0.4.0 release tagging
```

The final two items belong to I4.

---

## 7. Governing Drift Semantics

### 7.1 Drift Is a View of Existing Dependency Claims

For a fixed:

```text
service_id
snapshot
observation_context
```

let:

```text
D = get_service_dependencies(...).claims
```

Then:

```text
get_architecture_drift(...).claims
    =
[c in D where c.qualification in {
    OBSERVED_ONLY,
    NOT_OBSERVED_IN_WINDOW
}]
```

subject only to the limitation-projection rules in this specification.

`CONFIRMED` claims MUST NOT appear in the drift answer.

No new status calculation is permitted.

---

### 7.2 Meaning of the Two Drift States

```text
OBSERVED_ONLY

    A supported direct dependency was observed in the selected
    environment/window but has no declared support.

    This is an undocumented observed dependency.
```

```text
NOT_OBSERVED_IN_WINDOW

    A supported declared direct dependency has no matching observed
    evidence in the selected environment/window.

    This is NOT architecture absence.
```

I3 SHALL preserve the existing rule:

```text
NOT_OBSERVED_IN_WINDOW
    != unused
    != obsolete
    != dead
    != incorrect
    != unreachable
    != absent
```

The tool reports evidence-qualified discrepancy.

It does not judge whether the discrepancy is desirable.

---

### 7.3 No New Drift Predicate

I3 SHALL NOT add:

```text
DRIFTS_FROM
ARCHITECTURE_DRIFT
UNDECLARED_DEPENDENCY
UNUSED_DEPENDENCY
```

to the Canonical Model or public claim predicate vocabulary.

Returned drift claims remain ordinary:

```text
DIRECT_DEPENDENCY
```

claims.

Their qualification carries the discrepancy semantics.

This is important because:

```text
the same architecture fact
    does not become a different fact
    merely because its evidence state changed
```

---

## 8. Exact Claim-Reuse Invariant

For any underlying dependency returned by both tools at the same snapshot/context:

```text
dependency_claim.claim_id
    ==
drift_claim.claim_id
```

and these fields MUST be identical:

```text
subject
predicate
object
destination_resolution
delivery
qualification
coverage
evidence_refs
resolution_evidence_refs
```

I3 MUST NOT create a "drift claim id" namespace.

I3 MUST NOT replace the original evidence list with a drift-specific evidence list.

I3 MUST NOT alter the destination to make a discrepancy easier to describe.

The only semantic difference between the two answers is:

```text
dependency tool
    returns all supported direct dependency claims

drift tool
    returns only discrepancy-qualified dependency claims
```

---

## 9. Request Contract

The new request type is conceptually:

```python
class ArchitectureDriftRequest(BaseModel):
    service_id: str
    observation_context: ObservationContextInput | None = None
    snapshot_id: str | None = None
```

Its field validation SHALL be equivalent to `ServiceDependenciesRequest`.

Required semantic input:

```text
service_id
observation_context.environment
observation_context.window_start
observation_context.window_end
```

Optional:

```text
snapshot_id
```

### 9.1 Why a Separate Request Type

I3 SHOULD use a separate public request type even though the field set is currently identical.

Reason:

```text
request shape equality today
    != permanent semantic identity
```

A separate type gives the third tool its own executable contract while allowing validators/helpers to
be shared.

It MUST NOT duplicate observation-context normalization logic.

---

## 10. Output Contract

I3 adds:

```python
class ArchitectureDriftData(BaseModel):
    service: EntityRef
    drift_claim_ids: list[str]
```

The enclosing response is:

```text
ArchitectureAnswer<ArchitectureDriftData>
```

with:

```text
tool = "get_architecture_drift"
```

No redundant status buckets or counts are required.

Do not add:

```text
observed_only[]
not_observed[]
severity
score
summary_text
```

because each returned `DependencyClaim` already carries the authoritative qualification.

---

## 11. `ArchitectureAnswer<T>` Extension

I3 SHALL make the narrowest additive contract change needed for the third specialization.

Required changes include:

```text
tool Literal:
    get_architecture_drift
    get_evidence
    get_service_dependencies

_TOOL_NAME_BY_DATA_TYPE:
    ArchitectureDriftData -> get_architecture_drift
    EvidenceData -> get_evidence
    ServiceDependenciesData -> get_service_dependencies

_TOOLS_REQUIRING_OBSERVATION_CONTEXT:
    get_architecture_drift
    get_service_dependencies
```

Envelope invariants SHALL enforce:

```text
ArchitectureAnswer<ArchitectureDriftData>
    tool == get_architecture_drift

drift ANSWERED/PARTIAL
    data != null

drift NOT_ANSWERED
    data may be null

drift observation_context
    required unless OBSERVATION_CONTEXT_REQUIRED refusal

data.drift_claim_ids
    exactly equals claims[*].claim_id in the same order

top-level evidence_refs
    exact sorted deduplicated union of all returned claims'
    evidence_refs + resolution_evidence_refs
```

Existing dependency and evidence answer schemas MUST retain their current meaning.

---

## 12. Frozen Drift Answer Schema

I3 SHALL add:

```text
schemas/architecture_intelligence/v0.4/drift-answer.schema.json
```

`schema_export.py` SHALL regenerate all three answer schemas.

Schema drift tests SHALL prove that committed schemas equal generated schemas.

The drift schema SHALL be closed:

```text
additionalProperties = false
```

where the corresponding Pydantic models are closed.

The schema SHALL freeze:

```text
tool const = get_architecture_drift
data type = ArchitectureDriftData
claim shape = existing DependencyClaim
qualification enum = existing Qualification
limitation shape = existing Limitation
snapshot/context = existing v0.4 contract
```

I3 MUST NOT fork `DependencyClaim` into a second nearly-identical model.

---

## 13. Parent-Spec `UNSUPPORTED` Clarification

The parent release specification lists `UNSUPPORTED` among the release-level limitation/refusal
vocabulary.

The merged I1/I2 executable `LimitationCode` contract does not currently contain `UNSUPPORTED`, and
the bounded three-tool input model contains no mechanism selector through which a caller can request
an arbitrary unsupported architecture mechanism.

I3 SHALL NOT widen the already-qualified I1/I2 schemas solely to manufacture an artificial
`UNSUPPORTED` tool scenario.

For I3:

```text
tool-visible unsupported request
    if a concrete real case is discovered
        -> specify an explicit contract extension before implementation

unsupported external-system construct
    not representable by these bounded tools
        -> preserve it in real-system qualification metadata
        -> do not fabricate a dependency/drift claim
```

This specifically applies to frozen Airflow PostgreSQL dependencies.

Their existence remains visible in the v0.3 real-system qualification record, but I3 SHALL NOT turn
them into Queue, Operation, or Service dependency claims merely to exercise an enum.

---

## 14. Service Operation

The semantic operation is conceptually:

```python
ArchitectureIntelligenceService.get_architecture_drift(
    request: ArchitectureDriftRequest,
) -> ArchitectureAnswer[ArchitectureDriftData]
```

The service remains the sole semantic entry point.

The MCP adapter MUST NOT call:

```text
app.analysis.runtime
Neo4j
repository functions
dependency_projection directly
```

---

## 15. Preferred Service Implementation

I3 SHOULD refactor the service only enough to share the already-qualified direct-dependency
projection.

Preferred internal shape:

```text
_validate/normalize request
        |
        v
_acquire stable direct-dependency projection
        |
        +--> get_service_dependencies
        |        return all safe claims
        |
        +--> get_architecture_drift
                 retain discrepancy-qualified claims
```

The shared internal operation SHOULD own:

```text
stable snapshot acquisition
explicit-snapshot comparison
unknown-service check
dependency repository read
I1 dependency projection
500-candidate bound
```

It SHALL NOT become a new public method.

---

## 16. Prohibited Drift Implementation

The following is prohibited:

```python
# DO NOT build a second status engine.
if declared and observed:
    ...
elif observed:
    drift = ...
elif declared:
    drift = ...
```

Also prohibited:

```text
call O3 and O4 separately
merge their rows
re-resolve destinations
recompute claim IDs
rebuild evidence lists
```

The implementation must reuse the I1 dependency projection's result.

`app.analysis.runtime` remains authoritative historical semantics, but I3's public drift capability is
built from the already-qualified I1 public dependency view.

---

## 17. Result Bound

I1's 500-claim safety bound remains authoritative.

I3 SHALL apply the bound to the underlying supported direct-dependency candidate result **before**
drift filtering.

Reason:

```text
underlying dependency result exceeds safe bound
    +
drift filter happens to return 2
    != proof that the drift answer is complete
```

Therefore:

```text
underlying unique dependency claims > 500
    -> NOT_ANSWERED / RESULT_LIMIT_EXCEEDED
```

The drift tool MUST NOT silently inspect an unbounded dependency set and return a deceptively
"complete" subset.

---

## 18. Outcome Semantics

### 18.1 Known Service With Drift

If one or more safe discrepancy claims exist and no material limitation remains:

```text
outcome = ANSWERED
data != null
claims = drift claims
```

---

### 18.2 Known Service With No Drift

If the service is known and all supported direct dependencies are `CONFIRMED`, or the service has
zero applicable outgoing dependency claims:

```text
outcome = ANSWERED

data = {
    service: ...,
    drift_claim_ids: []
}

claims = []
evidence_refs = []
limitations = []
```

Empty drift is a successful answer.

It is not `NOT_ANSWERED`.

---

### 18.3 Partial Drift

If at least one safe drift claim is returned and a material unresolved/insufficient part affects the
completeness or interpretation of the drift result:

```text
outcome = PARTIAL
```

---

### 18.4 No Safe Drift Claim Because Evidence Is Insufficient

If candidate paths exist but all potentially relevant paths lack the evidence needed to construct a
supported dependency claim:

```text
outcome = NOT_ANSWERED
limitation = INSUFFICIENT_EVIDENCE
```

The tool SHALL NOT treat "could not establish a claim" as "no drift".

---

### 18.5 Unknown Service

```text
NOT_ANSWERED / UNKNOWN_ENTITY
```

---

### 18.6 Missing or Incomplete Observation Context

```text
NOT_ANSWERED / OBSERVATION_CONTEXT_REQUIRED
observation_context = null
```

Malformed supplied context values remain input-schema errors.

---

### 18.7 Explicit Stale Snapshot

```text
NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE
```

No fallback to current state.

---

### 18.8 Unstable Current Snapshot

After the existing bounded stable-read retry cannot acquire one consistent state:

```text
NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE
```

---

## 19. Limitation Projection

Drift filtering MUST NOT accidentally drop a limitation that affects whether the drift answer is
complete.

Use these rules.

### 19.1 Claim-Scoped Limitations

A limitation with non-empty:

```text
claim_ids
```

is retained only if it applies to a returned drift claim.

If one limitation references several claim IDs:

```text
claim_ids
    -> intersect with returned drift claim IDs
```

If the intersection is empty, omit that limitation from the drift answer.

Example:

```text
CONFIRMED dependency
    DIRECT_TARGET_FALLBACK
    UNRESOLVED_IDENTITY

dependency omitted from drift
    ->
its claim-scoped unresolved limitation is also omitted
```

---

### 19.2 Claim-Independent Insufficient-Evidence Limitations

A dependency candidate with no safe claim may carry:

```text
INSUFFICIENT_EVIDENCE
claim_ids = []
```

Such a limitation SHALL be retained in the drift answer.

Reason:

```text
no safe claim
    !=
proved non-drift
```

It materially limits the completeness of the drift result.

---

### 19.3 Request/Snapshot/Entity Refusals

These remain unchanged:

```text
UNKNOWN_ENTITY
OBSERVATION_CONTEXT_REQUIRED
SNAPSHOT_NOT_AVAILABLE
RESULT_LIMIT_EXCEEDED
```

---

## 20. Drift Claim Ordering

Drift claims SHALL use the exact I1 dependency order:

```text
(
    object.id,
    delivery.kind,
    delivery.via.id,
    claim_id
)
```

I3 MUST NOT sort by qualification first.

Reason:

```text
filtering the dependency result
    should preserve the same stable relative order
```

`data.drift_claim_ids` SHALL match `claims[*].claim_id` exactly in that order.

Limitations SHALL retain the existing deterministic limitation ordering.

---

## 21. Evidence Semantics

Every drift claim MUST retain its exact I1 evidence linkage.

```text
claim.evidence_refs
    qualification evidence

claim.resolution_evidence_refs
    destination-resolution evidence

answer.evidence_refs
    sorted deduplicated union of both
```

For a claim present in both dependency and drift answers:

```text
dependency evidence refs
    ==
drift evidence refs
```

---

## 22. Drift-to-Evidence Drill-Down

The required user flow is:

```text
get_architecture_drift
    |
    +--> snapshot.snapshot_id
    |
    +--> evidence_refs[]
              |
              v
get_evidence(
    same snapshot_id,
    selected evidence_refs
)
```

The evidence tool remains unchanged.

It SHALL:

```text
resolve against the explicit originating snapshot
never fall forward
create no claim
return sanitized provenance only
```

I3 SHALL add integration coverage that every drift answer's evidence references resolve through the
I2 evidence tool when the snapshot is still current.

---

## 23. MCP Tool Contract

I3 adds exactly one tool:

```text
get_architecture_drift
```

Description SHOULD communicate:

```text
direct service dependencies whose current evidence qualification
shows declared-versus-observed discrepancy
```

The MCP adapter SHALL:

1. accept the real `ArchitectureDriftRequest`;
2. perform only the same caller-input pre-validation pattern already required for the dependency tool;
3. call `ArchitectureIntelligenceService.get_architecture_drift` exactly once;
4. return the `ArchitectureAnswer<ArchitectureDriftData>` unchanged as structured content;
5. add no claims, limitations, evidence, summaries, or classifications;
6. use the existing read-only tool annotations.

Unexpected exceptions SHALL use the same sanitized SDK behavior as the existing tools.

---

## 24. Three-Tool Discovery

After I3:

```text
tools/list
```

SHALL return exactly:

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

in deterministic lexicographic order.

All three tools SHALL advertise:

```text
closed input schemas
closed output schemas
read-only hints
non-destructive behavior
idempotent behavior
```

No fourth placeholder tool is permitted.

---

## 25. Read-Only Boundary

The new drift operation SHALL use Neo4j `READ_ACCESS`.

Required proof:

```text
revision/fingerprint before call
    ==
revision/fingerprint after call
```

for:

```text
ANSWERED
PARTIAL
NOT_ANSWERED
validation/refusal paths
```

The MCP package SHALL continue to have no graph repository/session imports.

No drift query may:

```text
write a temporary marker
persist a snapshot
persist an observation context
materialize DIRECT_DEPENDENCY
materialize DRIFT
```

---

## 26. Concurrency and Stable-State Behavior

The drift answer MUST describe one committed state.

I3 SHALL reuse the I1 revision fence and stable-read retry.

A concurrent mutation to:

```text
canonical relation
evidence
destination-resolution relation
coverage-relevant state
```

during the stable read SHALL result in:

```text
retry
or
safe SNAPSHOT_NOT_AVAILABLE refusal
```

never:

```text
claims from state A
snapshot fingerprint from state B
```

I3 does not need a new concurrency algorithm.

At least one integration test SHALL prove the drift path uses the same stable-read boundary.

---

## 27. Synthetic Drift Scenarios

I3 SHALL add focused independently authored scenarios.

The intent is semantic coverage, not maximum scenario count.

### 27.1 `drift-observed-only`

Input:

```text
one supported direct dependency
observed in selected context
no declared support
```

Expected:

```text
one DIRECT_DEPENDENCY claim
qualification = OBSERVED_ONLY
outcome = ANSWERED
```

---

### 27.2 `drift-not-observed-in-window`

Input:

```text
one declared supported dependency
no matching observation in selected context
```

Expected:

```text
one DIRECT_DEPENDENCY claim
qualification = NOT_OBSERVED_IN_WINDOW
coverage = independently expected qualitative value
```

---

### 27.3 `drift-empty-confirmed`

Input:

```text
known service
one or more CONFIRMED dependencies
```

Expected:

```text
ANSWERED
drift_claim_ids = []
claims = []
limitations = []
```

This proves `CONFIRMED` is not drift.

---

### 27.4 `drift-mixed`

Input:

```text
same service has:
    one CONFIRMED dependency
    one OBSERVED_ONLY dependency
    one NOT_OBSERVED_IN_WINDOW dependency
```

Expected:

```text
exactly two returned claims

OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW

CONFIRMED omitted
```

This is the primary synthetic drift scenario.

---

### 27.5 `drift-unresolved-destination`

Input:

```text
a discrepancy-qualified direct relation
whose logical destination service cannot be safely resolved
```

Expected:

```text
drift claim retained
DIRECT_TARGET_FALLBACK
UNRESOLVED_IDENTITY limitation
PARTIAL when appropriate
no guessed Service identity
```

---

### 27.6 `drift-insufficient-evidence`

Input:

```text
candidate dependency path
without sufficient accepted evidence to construct a safe claim
```

Expected:

```text
no fabricated drift claim
INSUFFICIENT_EVIDENCE
NOT_ANSWERED or PARTIAL according to whether other safe drift claims exist
```

---

### 27.7 `drift-unknown-service`

Expected:

```text
NOT_ANSWERED / UNKNOWN_ENTITY
```

---

### 27.8 `drift-missing-context`

Expected:

```text
NOT_ANSWERED / OBSERVATION_CONTEXT_REQUIRED
```

---

### 27.9 `drift-stale-snapshot`

Expected:

```text
NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE
```

with no fallback.

---

## 28. Reuse of Existing I1 Fixtures

Where semantically identical input already exists, I3 SHOULD reuse or derive from the independently
authored I1 fixture rather than create a differently-shaped architecture merely to test drift.

Useful anchors include:

```text
sync-confirmed
observed-only-undeclared
sync-not-observed-in-window
unresolved-queue-destination
multiple-delivery-paths
unknown-service
empty-service
```

Expected drift answers MUST still be authored independently.

They MUST NOT be produced by:

```text
run dependency tool
filter output
save as expected drift answer
```

The mathematical invariant may guide independent authorship, but AIP output is never the oracle.

---

## 29. Full Three-Tool Evaluation

I3 SHALL generalize the existing:

```text
evaluation/architecture_answers/
```

suite rather than create a third evaluation framework.

The generalized scenario model SHALL identify:

```text
scenario id
tool
request
input fixture
expected ArchitectureAnswer
```

Supported tool values:

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

Existing I1 dependency expected answers SHALL retain their meaning.

---

## 30. Evaluator Architecture

Preferred shape:

```text
scenario loader
        |
        v
fixture preparation
        |
        v
real ArchitectureIntelligenceService
        |
        +--> dependencies
        +--> drift
        +--> evidence
        |
        v
canonical ArchitectureAnswer
        |
        v
independent expected answer comparator
```

The evaluator MUST NOT query Neo4j to compute expected drift.

The comparator MUST NOT derive expected qualifications.

The reference/ground-truth code MUST remain separate from the live implementation path.

---

## 31. Tool-Aware Scenario Dispatch

The evaluator MAY have a fixed dispatch table:

```text
get_service_dependencies
    -> ServiceDependenciesRequest
    -> service.get_service_dependencies

get_architecture_drift
    -> ArchitectureDriftRequest
    -> service.get_architecture_drift

get_evidence
    -> EvidenceRequest
    -> service.get_evidence
```

This is dispatch, not architecture semantics.

A generic tool-workflow DSL is unnecessary.

---

## 32. Direct `get_evidence` Evaluation

At least one independently authored evaluation scenario SHALL call `get_evidence` directly.

Its request SHALL use:

```text
known deterministic evidence refs
explicit snapshot
```

derived from the fixture's independently specified provenance identities.

Expected output SHALL check:

```text
record ids
evidence/source types
sanitized source metadata
bounded observation metadata where applicable
supported canonical facts
missing refs where applicable
ordering
limitations
```

The expected evidence result MUST NOT be generated from an earlier tool call.

---

## 33. Cross-Tool Invariants

In addition to per-scenario exact comparison, I3 SHALL prove:

### 33.1 Dependency-to-Drift Invariant

For the same:

```text
service
context
snapshot
```

```text
drift.claims
    ==
dependency.claims filtered by discrepancy qualification
```

using semantic object comparison, not separate hand-written reimplementation.

This is a **live cross-tool consistency assertion**, not the source of expected ground truth.

---

### 33.2 Claim Identity Invariant

Any claim returned by both tools has identical:

```text
claim_id
payload
evidence linkage
```

---

### 33.3 Drift-to-Evidence Invariant

All evidence refs returned by drift resolve through `get_evidence` at the same snapshot.

---

### 33.4 Service-to-MCP Invariant

For every tested drift case:

```text
direct ArchitectureIntelligenceService answer
    ==
MCP structuredContent semantic answer
```

---

## 34. Two Complete Deterministic Runs

I3 SHALL extend the existing two-pass architecture-answer runner.

"Two runs" means:

```text
Pass 1:
    reset -> ingest -> telemetry/reconcile -> call tool
    for every scenario

Pass 2:
    reset -> ingest -> telemetry/reconcile -> call tool
    for every scenario
```

not:

```text
call the same already-prepared graph twice
```

The candidate SHA SHALL be resolved exactly once per evaluation invocation and threaded through:

```text
Producer
live service calls
comparator
machine-readable report
```

The two complete run output hashes MUST match.

---

## 35. Machine-Readable I3 Evaluation Result

I3 SHALL produce one deterministic machine-readable result artifact.

Recommended path:

```text
evaluation/architecture_answers/results/i3-evaluation-result.json
```

or a compatible generalized replacement of the current result file.

It SHALL record at least:

```text
candidate_sha
schema/evaluation version
run_count = 2
run_output_sha256[2]
semantic_outputs_identical
scenario count
per-scenario tool
per-scenario PASS/FAIL
mismatch categories
broken evidence refs
cross-tool invariant failures
real-system qualification results
```

A filtered single-scenario invocation MUST NOT overwrite the committed full-suite artifact.

---

## 36. Failure Detection

The full evaluator SHALL fail on at least:

```text
missing expected claim
unexpected claim
wrong claim id
wrong destination
wrong delivery
wrong qualification
wrong coverage
wrong evidence refs
wrong resolution evidence refs
wrong limitation
wrong outcome
wrong snapshot
wrong observation context
wrong tool specialization
broken evidence reference
direct/MCP semantic difference
drift/dependency cross-tool difference
nondeterministic repeated result
```

The evaluator SHALL return a non-zero exit code on semantic failure.

---

## 37. Frozen Quarkus Qualification

I3 SHALL reuse immutable v0.3 Quarkus evidence.

At the I3 entry baseline, the frozen Quarkus:

```text
actual.yaml
actual-revalidation.yaml
```

are byte-identical and have Git blob identity:

```text
656446cd79c4cefec8f1ac0124fbb6b34e993704
```

The frozen capture includes three supported `CONFIRMED` `CALLS` facts from:

```text
service:rest-fights
    -> rest-heroes GET /api/heroes/random
    -> rest-narration POST /api/narration
    -> rest-villains GET /api/villains/random
```

with declared and observed evidence.

### 37.1 Expected Tool-Level Meaning

A derived immutable qualification fixture SHALL prove:

```text
get_service_dependencies(service:rest-fights)
    -> three supported confirmed direct dependencies

get_architecture_drift(service:rest-fights)
    -> ANSWERED, empty drift claims

get_evidence(...)
    -> evidence for the dependency claims resolves
```

The fixture SHALL record:

```text
source upstream revision
source v0.3 artifact path
source artifact hash / blob id
derivation method
```

---

## 38. Frozen Airflow Qualification

I3 SHALL reuse immutable v0.3 Airflow evidence.

At the I3 entry baseline, frozen Airflow:

```text
actual.yaml
actual-revalidation.yaml
```

are byte-identical and have Git blob identity:

```text
8891289baa9facaf70a0cc0c6b9b2e0fdd9c838a
```

The supported frozen capture contains:

```text
9 PROVIDES facts
0 CALLS
0 SENDS
0 RECEIVES_FROM
```

for the bounded Airflow profile.

The v0.3 dossier separately retains:

```text
3 UNSUPPORTED constructs
2 UNRESOLVED_IDENTITY items
1 INSUFFICIENT_EVIDENCE item
0 critical semantic errors
```

### 38.1 Expected Tool-Level Meaning

I3 SHALL NOT invent an Airflow outgoing dependency merely because the release wants a positive tool
scenario.

For:

```text
service:airflow-apiserver
```

the derived bounded tool qualification SHOULD establish:

```text
get_service_dependencies
    known service
    no supported outgoing CALLS/SENDS in frozen scope
    ANSWERED with empty dependency claims

get_architecture_drift
    ANSWERED with empty drift claims
```

The frozen unsupported/unresolved/insufficient external-system findings SHALL remain visible in the
I3 real-system qualification record.

They are not converted into false direct-dependency claims.

---

## 39. No Fresh Heavy Real-System Run

I3 SHALL NOT start Quarkus Super Heroes or Apache Airflow merely to test a read-only tool adapter.

A fresh real-system run becomes mandatory only if I3 changes semantics relevant to those frozen
captures, including:

```text
ingestion
runtime correlation
identity resolution
evidence reconciliation
Canonical Model semantics
real-world comparator semantics
```

The expected I3 implementation does none of these.

If such a change becomes necessary, stop I3 and apply the parent release scope-change rule.

---

## 40. Derived Real-System Fixture Rule

A derived immutable fixture is allowed.

It MUST:

```text
name the source v0.3 system
name the source revision
name source artifact path
name source artifact hash/blob identity
preserve only facts actually supported by the frozen capture
use existing AIP declaration/telemetry fixture mechanisms
avoid any new production adapter
```

It MUST NOT:

```text
invent missing edges
upgrade unresolved identity to resolved identity
reinterpret unsupported constructs
create synthetic evidence that changes the frozen semantic classification
pretend to be a fresh live-system run
```

---

## 41. Hero Demo

I3 SHALL deliver the five-minute hero demo promised by the release specification.

Question:

> **Which direct dependencies of this service were observed but not declared, and what evidence
> supports that answer?**

Subject:

```text
service:order-service
```

Architecture:

```text
bundled runtime-demo
```

Observation context:

```text
frozen deterministic demo context
```

Expected primary finding:

```text
OrderService
    -> LegacyPricingService

qualification:
    OBSERVED_ONLY
```

The claim SHALL link to its OpenTelemetry evidence.

---

## 42. Hero Demo Flow

Required flow:

```text
1. start documented local AIP prerequisites
2. load the bundled/frozen demo architecture and evidence
3. start or use the real MCP endpoint
4. independent client -> tools/list
5. verify exactly three tools
6. tools/call get_architecture_drift
7. show LegacyPricingService OBSERVED_ONLY claim
8. show snapshot + observation context
9. collect evidence refs
10. tools/call get_evidence with same snapshot
11. display sanitized provenance
12. exit successfully
```

No LLM API key is required.

A separate optional LLM/agent demonstration MAY consume the same result but adds no qualification
claim.

---

## 43. Hero Demo Determinism

The hero demo SHALL not rely on a moving `now - 24h` window.

The demo SHALL use either:

```text
fixed bundled telemetry timestamps + fixed explicit window
```

or another explicitly frozen equivalent.

The semantic result SHALL not depend on:

```text
wall clock
host timezone
random trace ids
random invocation ids
LLM output
```

---

## 44. MCP Independent-Client Extension

I2 already provides an independent client that:

```text
uses HTTP
imports no app.* module
talks to the real uvicorn listener
uses production MCP wiring
```

I3 SHOULD extend that client rather than introduce a new client implementation.

The I3 golden path SHALL execute:

```text
tools/list
get_architecture_drift
get_evidence
get_service_dependencies
```

At I3 exit, the client SHALL prove:

```text
three advertised tools
schemas usable by an external client
drift claim survives transport unchanged
dependency claim survives transport unchanged
evidence drill-down works
read-only behavior
deterministic repeated semantic outputs
```

I4 will repeat the complete independent-client qualification on the exact release candidate and
published artifact.

---

## 45. Tool Discovery Compatibility

I3 changes:

```text
tools/list count
    2 -> 3
```

This is expected pre-release evolution inside the still-unreleased `v0.4.0` line.

Tests that currently assert exactly two tools SHALL be deliberately updated to exactly three.

No existing tool name or schema meaning may be changed to make room for the third tool.

---

## 46. Input Error Mapping

The drift adapter SHALL follow the dependency adapter's established split:

```text
malformed caller-supplied context value
    -> actionable ToolError/input error

unexpected service/internal validation failure
    -> SDK-sanitized generic execution error
```

Do not catch all `pydantic.ValidationError` around the full service call.

That could leak graph/output data through an internal validation exception.

Pre-validate only the caller's own context values using the existing normalization helper.

---

## 47. Evidence Privacy

I3 does not broaden evidence disclosure.

The existing `get_evidence` contract remains the only evidence-detail surface.

Drift responses SHALL expose only opaque evidence IDs.

They SHALL NOT embed:

```text
raw span payload
trace payload
authorization headers
baggage
arbitrary OTel resource attributes
source file contents
secrets
sample trace ids
```

The hero demo SHALL display only fields already allowed by the I2 evidence contract.

---

## 48. Contract Compatibility Tests

I3 SHALL extend frozen contract tests to prove:

```text
ArchitectureDriftData is closed
ArchitectureDriftRequest is closed
drift answer tool const is exact
drift observation context is required
drift claim ids exactly match claims
drift evidence union is exact
existing dependency schema meaning unchanged
existing evidence schema meaning unchanged
all three schemas regenerate deterministically
invalid extra fields are rejected
```

---

## 49. Unit Tests

At minimum:

### Drift Projection / Filtering

```text
CONFIRMED omitted
OBSERVED_ONLY retained unchanged
NOT_OBSERVED_IN_WINDOW retained unchanged
mixed qualifications filter correctly
relative claim ordering preserved
claim ids unchanged
evidence refs unchanged
coverage unchanged
unresolved limitation retained only for returned drift claim
confirmed-only unresolved limitation omitted
claim-independent insufficient-evidence limitation retained
```

### Service

```text
known service + drift -> ANSWERED
known service + no drift -> ANSWERED empty
unknown service -> UNKNOWN_ENTITY
missing context -> OBSERVATION_CONTEXT_REQUIRED
stale snapshot -> SNAPSHOT_NOT_AVAILABLE
result limit enforced before drift filter
stable-read retry used
```

### MCP

```text
three tools listed exactly
drift input schema closed
drift output schema advertised
drift dispatch calls service exactly once
malformed context safely mapped
unexpected failure sanitized
read-only boundary static check remains green
```

---

## 50. Integration Tests

At minimum:

```text
real Neo4j drift observed-only
real Neo4j drift not-observed-in-window
real Neo4j mixed drift/confirmed
real Neo4j unresolved destination
real Neo4j insufficient evidence
real Neo4j stale snapshot
real Neo4j stable-read concurrency behavior
direct drift vs MCP equivalence
drift -> evidence drill-down
dependency -> drift cross-tool invariant
zero graph writes on success
zero graph writes on partial/refusal
real HTTP independent-client three-tool path
```

Existing I1/I2 integration tests remain green.

---

## 51. Deterministic Evaluation Scenario Budget

I3 SHOULD keep the architecture-answer suite compact.

A recommended target is:

```text
existing dependency scenarios
    8 unchanged

new drift scenarios
    6-9 focused scenarios

direct evidence scenarios
    2-3 focused scenarios

real-system-derived qualification
    2 source profiles
```

The exact number is non-normative.

Coverage quality is more important than reaching a particular scenario count.

---

## 52. Negative / Failure Semantics

The required failure matrix includes:

| Situation | Required result |
|---|---|
| Known service, no drift | `ANSWERED`, empty drift claims |
| Unknown service | `NOT_ANSWERED / UNKNOWN_ENTITY` |
| Missing/incomplete observation context | `NOT_ANSWERED / OBSERVATION_CONTEXT_REQUIRED` |
| Explicit stale snapshot | `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE` |
| Stable snapshot cannot be acquired | `NOT_ANSWERED / SNAPSHOT_NOT_AVAILABLE` |
| Some drift safe, some paths insufficient/unresolved | `PARTIAL` with exact limitations |
| All candidate paths insufficient | `NOT_ANSWERED / INSUFFICIENT_EVIDENCE` |
| Underlying result exceeds 500 unique claims | `NOT_ANSWERED / RESULT_LIMIT_EXCEEDED` |
| Malformed request value | protocol/input error, not architecture limitation |
| Unexpected internal failure | sanitized tool execution error |

---

## 53. Qualification of "No Drift"

The evaluator SHALL distinguish:

```text
no drift
```

from:

```text
unable to determine drift
```

Valid no-drift:

```text
known service
safe supported direct-dependency projection
all returned claims CONFIRMED
or no applicable dependencies
no material limitation
```

Not valid no-drift:

```text
unknown service
missing context
stale snapshot
all candidate paths missing evidence
unsupported/unresolved architecture silently discarded
```

This distinction is release-critical.

---

## 54. Coverage Semantics

For a returned:

```text
NOT_OBSERVED_IN_WINDOW
```

drift claim, `coverage` remains mandatory and retains the I1 meaning.

I3 SHALL NOT:

```text
convert coverage into confidence
use coverage to suppress the claim
upgrade/downgrade qualification based on a score
```

Coverage tells the client how much weight to give the non-observation.

It does not determine architecture truth by itself.

---

## 55. Multiple Delivery Paths

If one logical destination is reached through:

```text
SYNC_HTTP
ASYNC_MESSAGE
```

and both paths are discrepancy-qualified, drift SHALL preserve both claims.

If:

```text
SYNC_HTTP = CONFIRMED
ASYNC_MESSAGE = OBSERVED_ONLY
```

drift SHALL return only the async claim.

I3 MUST NOT deduplicate by destination service alone.

---

## 56. Snapshot Cross-Tool Consistency

A client MAY:

```text
1. call get_service_dependencies without snapshot_id
2. receive snapshot S
3. call get_architecture_drift with snapshot_id S
```

If the live graph is unchanged:

```text
drift answer snapshot == S
```

and the cross-tool filtering invariant applies.

If the graph changed:

```text
get_architecture_drift(snapshot_id=S)
    -> SNAPSHOT_NOT_AVAILABLE
```

No comparison across silently different snapshots is allowed.

---

## 57. Observation-Context Cross-Tool Consistency

The dependency and drift calls SHALL use the same normalized observation-context semantics.

For identical structured context fields:

```text
context_id dependency
    ==
context_id drift
```

I3 SHALL not add a "drift context".

---

## 58. Candidate Identity

The existing evaluation rule remains:

```text
candidate SHA resolved once
```

For a qualification run, use:

```bash
uv run python -m evaluation answers --candidate-sha <40-hex-sha>
```

or the I3-equivalent generalized command.

The result artifact SHALL carry that same SHA internally.

The comparator SHALL compare against that explicitly threaded identity.

No independent ambient `git rev-parse HEAD` calls may create divergent run identities.

---

## 59. I3 Qualification Command

The final command MAY remain:

```bash
uv run python -m evaluation answers --candidate-sha <sha>
```

if the existing architecture-answer suite is generalized cleanly.

A new sibling command is not required.

If a renamed command is introduced, it SHALL still:

```text
run all three tool families
perform two full clean-state passes
produce one machine-readable result
return non-zero on semantic failure
```

Avoid multiplying evaluator entry points.

---

## 60. Full Regression Gate

Before I3 GO:

```bash
uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit
uv run pytest tests/integration

uv run python -m evaluation run
uv run python -m evaluation answers --candidate-sha <candidate>
```

Expected baseline properties:

```text
v0.2 relation-fact evaluation:
    10/10 PASS

I1 dependency architecture-answer expectations:
    unchanged

I2 MCP dependency/evidence expectations:
    unchanged

I3 full architecture-answer evaluation:
    all scenarios PASS
    two full semantic output hashes identical
```

Exact unit/integration test counts are non-normative.

---

## 61. Real-System Qualification Report

The I3 machine-readable report SHALL contain a compact real-system section such as:

```json
{
  "real_system_qualification": [
    {
      "system": "quarkus-super-heroes",
      "source_artifact": "...",
      "source_artifact_hash": "...",
      "status": "PASS"
    },
    {
      "system": "apache-airflow",
      "source_artifact": "...",
      "source_artifact_hash": "...",
      "status": "PASS"
    }
  ]
}
```

It SHALL not pretend those fixtures are fresh live executions.

---

## 62. Documentation Deliverables

I3 SHALL keep documentation compact.

Required:

```text
docs/specifications/0.4.0/i3-drift-capability-and-deterministic-qualification.md

docs/specifications/0.4.0/README.md
    I3 status

one concise MCP/demo usage document
    or an existing document updated for the third tool

machine-readable I3 evaluation artifact
```

A separate large I3 completion dossier is not required unless implementation discovers a material
semantic exception needing an audit record.

---

## 63. Suggested Delivery Split

I3 SHOULD be implemented in four focused increments.

### I3.1 — Drift Contract and Service

Deliver:

```text
ArchitectureDriftRequest
ArchitectureDriftData
third ArchitectureAnswer specialization
drift-answer.schema.json
shared dependency-projection service refactor
get_architecture_drift service method
unit + Neo4j integration tests
```

Exit capability:

> A direct service call returns only discrepancy-qualified direct dependency claims, with exact I1
> claim identity/evidence semantics and zero graph writes.

Suggested branch:

```text
feat/v0.4-i3-drift-service
```

---

### I3.2 — Drift MCP Tool

Deliver:

```text
get_architecture_drift MCP adapter
three-tool tools/list
closed input/output schemas
direct/MCP equivalence
drift-to-evidence drill-down
independent-client extension
read-only tests
```

Exit capability:

> An independent MCP client can obtain a drift claim and resolve why it exists through the same
> snapshot.

Suggested branch:

```text
feat/v0.4-i3-drift-mcp
```

---

### I3.3 — Full Deterministic Three-Tool Evaluation

Deliver:

```text
tool-aware architecture-answer scenarios
new drift scenarios
direct evidence scenarios
cross-tool invariants
two full clean-state passes
machine-readable I3 evaluation result
Quarkus derived qualification
Airflow derived qualification
```

Exit capability:

> The complete three-tool semantic surface is independently and deterministically qualified against
> synthetic plus immutable real-system-derived inputs.

Suggested branch:

```text
test/v0.4-i3-tool-qualification
```

---

### I3.4 — Hero Demo and I3 Completion

Deliver:

```text
five-minute deterministic hero demo
service:order-service drift call
LegacyPricingService OBSERVED_ONLY proof
snapshot-bound evidence drill-down
concise usage docs
0.4.0 status-index update
final exact-candidate checks
I3 GO/NO-GO statement
```

Exit capability:

> A new external client can see one meaningful architecture drift finding, inspect its evidence, and
> reproduce the result without an LLM or graph knowledge.

Suggested branch:

```text
docs/v0.4-i3-hero-and-completion
```

---

## 64. I3 Release Blockers

Any of the following blocks I3:

### Semantic Integrity

```text
drift re-derives status independently from the I1 dependency projection
drift includes CONFIRMED claims
drift drops a valid OBSERVED_ONLY claim
drift drops a valid NOT_OBSERVED_IN_WINDOW claim
same fact has different claim_id in dependency and drift answers
same fact has different destination/delivery between the tools
same fact has different evidence refs between the tools
non-observation is called absent, dead, obsolete, unused, or incorrect
unresolved destination is guessed
insufficient evidence is treated as proof of no drift
```

### Contract / MCP

```text
existing dependency/evidence contract meaning is weakened
tools/list exposes anything other than exactly three tools
drift adapter contains graph/analysis logic
drift adapter calls service more than once to synthesize one answer
structuredContent differs from direct service result
input/output schemas are open or inconsistent with runtime validation
```

### Snapshot / Evidence

```text
stale snapshot silently falls forward
drift and evidence calls resolve against different snapshots without refusal
broken evidence reference
concurrent write can produce mixed-state accepted answer
```

### Evaluation

```text
expected drift answer generated from AIP output
evaluator creates a second drift-semantic implementation as oracle
single prepared graph is called twice and described as two full runs
two complete run hashes differ
real-system-derived fixture invents a fact absent from frozen evidence
Airflow unsupported/unresolved constructs are turned into fake supported dependencies
```

### Scope / Safety

```text
graph write
fourth tool
second transport
new Canonical Model relation
fresh heavy external-system rerun without semantic reason
LLM required for correctness
```

Targets:

```text
Dependency/drift claim-identity differences = 0
Service/MCP semantic differences = 0
Broken evidence references = 0
Unexpected public tools = 0
Graph writes = 0
Two-run semantic differences = 0
I3 blockers = 0
```

---

## 65. Definition of Done

### Entry / Regression

- [ ] I3 starts from merged I1/I2 main.
- [ ] Existing relation-fact suite remains `10/10 PASS`.
- [ ] Existing I1 dependency expected answers remain unchanged.
- [ ] Existing I2 dependency/evidence MCP behavior remains unchanged.

### Drift Contract

- [ ] `ArchitectureDriftRequest` is executable and closed.
- [ ] `ArchitectureDriftData` is executable and closed.
- [ ] `ArchitectureAnswer<ArchitectureDriftData>` is a valid third specialization.
- [ ] `drift-answer.schema.json` is committed and drift-tested.
- [ ] `tool` is frozen to `get_architecture_drift`.
- [ ] Drift requests require explicit observation context semantically.
- [ ] Drift data claim IDs exactly match returned claims.

### Drift Semantics

- [ ] Drift is implemented as a view over the existing dependency projection.
- [ ] `OBSERVED_ONLY` is returned.
- [ ] `NOT_OBSERVED_IN_WINDOW` is returned.
- [ ] `CONFIRMED` is excluded.
- [ ] Non-observation is never represented as absence.
- [ ] Claim identity is unchanged between dependency and drift answers.
- [ ] Destination and delivery are unchanged between dependency and drift answers.
- [ ] Qualification, coverage and evidence are unchanged.
- [ ] Multiple delivery paths remain independent.
- [ ] Unresolved destination identity is retained rather than guessed.
- [ ] Insufficient evidence never masquerades as no drift.
- [ ] Known zero-drift service returns `ANSWERED` with empty drift claims.
- [ ] Result limit applies before drift filtering.

### Snapshot / Context / Read-Only

- [ ] Drift uses the I1 stable-read/revision fence.
- [ ] Explicit matching snapshot repeats.
- [ ] Stale snapshot refuses without fallback.
- [ ] Context normalization is shared with dependencies.
- [ ] Same structured context produces the same context ID across tools.
- [ ] Drift service uses `READ_ACCESS`.
- [ ] Success, partial and refusal paths produce zero graph writes.
- [ ] No historical snapshot or ObservationContext persistence is added.

### MCP

- [ ] Exactly three tools are exposed.
- [ ] Order is `get_architecture_drift`, `get_evidence`, `get_service_dependencies`.
- [ ] Drift MCP input/output schemas are advertised and closed.
- [ ] Drift adapter calls only `ArchitectureIntelligenceService`.
- [ ] Direct and MCP drift outputs are semantically identical.
- [ ] Unexpected internal errors are sanitized.
- [ ] Independent client imports no AIP internal module.
- [ ] No LLM key is required.

### Evidence

- [ ] Drift answer evidence refs are exact.
- [ ] Every drift evidence ref resolves through `get_evidence` at the same snapshot.
- [ ] Missing evidence remains explicit.
- [ ] Evidence output remains sanitized.
- [ ] No new evidence disclosure field is added merely for the demo.

### Deterministic Evaluation

- [ ] Existing architecture-answer evaluator is generalized rather than replaced.
- [ ] Expected drift answers are independently authored.
- [ ] Positive observed-only drift is covered.
- [ ] NOT_OBSERVED_IN_WINDOW drift is covered.
- [ ] Empty drift is covered.
- [ ] Mixed confirmed/drift is covered.
- [ ] Unresolved identity is covered.
- [ ] Insufficient evidence is covered.
- [ ] Unknown service is covered.
- [ ] Missing context is covered.
- [ ] Stale snapshot is covered.
- [ ] `get_evidence` has direct independently authored evaluation.
- [ ] Missing/unexpected/wrongly-qualified claims fail.
- [ ] Cross-tool dependency/drift invariant is proven.
- [ ] Cross-tool drift/evidence invariant is proven.
- [ ] Two complete clean-state evaluation passes execute.
- [ ] Two run hashes are identical.
- [ ] Candidate SHA is explicitly threaded through the full run.
- [ ] Machine-readable I3 evaluation artifact is produced.

### Real-System Evidence

- [ ] Frozen Quarkus source artifact/revision/hash is recorded.
- [ ] Quarkus supported dependency answer is qualified.
- [ ] Quarkus confirmed-only subject returns empty drift.
- [ ] Frozen Airflow source artifact/revision/hash is recorded.
- [ ] Airflow known service is not given fabricated outgoing dependencies.
- [ ] Airflow unsupported/unresolved/insufficient v0.3 findings remain explicit qualification metadata.
- [ ] No fresh Quarkus/Airflow run occurs unless semantic changes make it mandatory.

### Hero Demo

- [ ] Demo uses `service:order-service`.
- [ ] Demo uses explicit frozen observation context.
- [ ] Drift call returns LegacyPricingService as `OBSERVED_ONLY`.
- [ ] Evidence drill-down uses the same snapshot.
- [ ] Demo requires no LLM.
- [ ] Demo is runnable from clean documented state in approximately five minutes.
- [ ] Demo result is deterministic.

### Quality

- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Ruff check passes.
- [ ] Ruff format check passes.
- [ ] CI passes on the exact I3 candidate.
- [ ] CodeQL passes on the exact I3 candidate.
- [ ] Dependency audit passes on the exact I3 candidate.
- [ ] I3 blockers equal `0`.

---

## 66. Exact-Candidate Qualification

I3 SHALL follow the qualification discipline established by I1/I2.

The final I3 candidate SHA SHALL be explicit.

Do not infer qualification from:

```text
PR current head
ambient local HEAD
later docs-only commit
```

The qualifying code candidate's checks SHALL be inspected against that exact SHA.

The committed machine-readable evaluation artifact SHALL name that same candidate.

A docs-only follow-up may record the verified candidate after checks complete, provided it does not
change qualified code or executable contracts.

---

## 67. I3 GO Statement

I3 exits with exactly one of:

```text
GO — At <exact candidate SHA>, ArchitectureIntelligenceService and the MCP 2026-07-28 surface expose
exactly three read-only architecture tools. get_architecture_drift returns only the existing
direct-dependency claims qualified OBSERVED_ONLY or NOT_OBSERVED_IN_WINDOW, preserving I1 claim
identity, destination/delivery semantics, evidence, observation context and snapshot binding. The
complete three-tool deterministic evaluation passes two clean-state runs with identical semantic
outputs, frozen Quarkus/Airflow-derived qualification passes without invented facts, the hero demo
completes, and graph writes = 0.
```

or:

```text
NO-GO — the v0.4.0 drift/tool qualification is not proven; return to <named I3 sub-increment and
blocker>.
```

A successful UI screenshot, tool listing, or LLM narration is not a substitute.

---

## 68. Boundary to I4

I3 hands I4:

```text
one semantic service boundary

three read-only service operations:
    get_service_dependencies
    get_architecture_drift
    get_evidence

one stateless MCP endpoint
three frozen public tools
three executable answer schemas
complete deterministic multi-tool evaluation
two identical full evaluation passes
frozen Quarkus qualification
frozen Airflow qualification
one reproducible hero demo
one exact I3 candidate identity
```

I4 owns:

```text
final release-candidate freeze
production build-revision wiring if still outstanding
clean-checkout qualification
complete independent-client RC qualification
CI/CodeQL/dependency/container checks on exact RC
GO/NO-GO
v0.4.0 tag/release
published source/image smoke test
README/ROADMAP/CHANGELOG final release closure
```

I3 SHALL not pre-implement I4 publication work.

---

## 69. Implementation Guidance

The safest implementation order is:

```text
contract
    ->
direct service
    ->
MCP adapter
    ->
full evaluator
    ->
frozen real-system qualification
    ->
hero demo
```

Do not begin by writing the hero demo.

Do not begin by adding MCP code before the direct service semantics are executable.

Do not begin by writing a fresh drift Cypher query.

The most important implementation property is:

```text
one semantic dependency projection
        |
        +--> complete dependency answer
        |
        +--> discrepancy-only drift answer
```

This minimizes semantic duplication and makes cross-tool consistency testable by construction.

---

## 70. Expected Repository Touch Points

Likely production/contract files:

```text
app/architecture_intelligence/contracts.py
app/architecture_intelligence/request.py
app/architecture_intelligence/service.py
app/architecture_intelligence/schema_export.py
app/mcp/tools.py
```

Likely evaluation files:

```text
evaluation/architecture_answers/model.py
evaluation/architecture_answers/loader.py
evaluation/architecture_answers/runner.py
evaluation/architecture_answers/comparator.py
evaluation/architecture_answers/reporter.py
evaluation/architecture_answers/reference/
evaluation/architecture_answers/scenarios/
```

Likely schemas:

```text
schemas/architecture_intelligence/v0.4/architecture-answer.schema.json
schemas/architecture_intelligence/v0.4/evidence-answer.schema.json
schemas/architecture_intelligence/v0.4/drift-answer.schema.json
```

Existing dependency/evidence schema files SHOULD change only where the deliberate third-tool generic
envelope extension makes an additive shared enum/schema change unavoidable.

Any unrelated churn is a review smell.

---

## 71. References

Repository contracts and qualification records:

```text
docs/specifications/0.4.0/specification.md
docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md
docs/specifications/0.4.0/i1-completion-record.md
docs/specifications/0.4.0/i2-mcp-vertical-slice-and-evidence-drill-down.md
docs/specifications/0.4.0/README.md

evaluation/README.md
evaluation/architecture_answers/

docs/real-world-validation/quarkus-super-heroes/
docs/real-world-validation/apache-airflow/

examples/runtime-demo/
```

MCP:

```text
https://modelcontextprotocol.io/specification/2026-07-28
https://modelcontextprotocol.io/specification/2026-07-28/server/tools
https://modelcontextprotocol.io/specification/2026-07-28/basic/transports
```

---

## 72. Summary

I3 completes the product capability promised by `v0.4.0` without broadening the architecture model.

The semantic progression is:

```text
I1

AIP can answer:
    What are this service's direct dependencies?

I2

An external client can ask that question
and resolve why the answer exists.

I3

The external client can ask:
    Which of those dependencies disagree
    between declared architecture and
    observed runtime evidence?
```

The key rules are:

```text
drift is a filtered dependency view
not a second architecture engine

OBSERVED_ONLY is drift

NOT_OBSERVED_IN_WINDOW is drift
but never proof of absence

CONFIRMED is not drift

same fact -> same claim_id
same destination
same delivery
same evidence

same snapshot/context -> same semantics

no guessing
no writes
no LLM truth
no new model relation
```

I3 succeeds when the third tool adds useful architecture intelligence **without adding a second
source of architectural truth**, and when the complete three-tool surface is independently,
deterministically, and reproducibly qualified before I4 freezes the release candidate.
