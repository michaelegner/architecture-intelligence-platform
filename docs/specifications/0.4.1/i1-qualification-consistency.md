# AIP v0.4.1 — I1 Qualification Consistency

**Status:** Draft 0.1  
**Target release:** `v0.4.1`  
**Release increment:** I1 — Qualification Consistency  
**Target repository path:** `docs/specifications/0.4.1/i1-qualification-consistency.md`  
**Governing specification:** `docs/specifications/0.4.1/specification.md`  
**Entry baseline:** Published and post-release-verified `v0.4.0` plus the accepted `v0.4.1` parent specification  
**Primary outcome:** The existing analysis/REST qualification path and the
`ArchitectureIntelligenceService`/MCP qualification path are provably governed by one
declared-versus-observed rule and produce the same qualification and telemetry-coverage result for
the same canonical relation, evidence set, environment, and effective observation window.

---

## 1. Purpose

`v0.4.0` exposes architecture answers through `ArchitectureIntelligenceService` and three read-only
MCP tools. The post-`v0.4.0` architecture review identified one correctness risk that should be
removed before broader discovery adds more evidence sources:

```text
analysis / REST / UI
        |
        | Cypher qualification
        v

CONFIRMED / OBSERVED_ONLY / NOT_OBSERVED_IN_WINDOW

ArchitectureIntelligenceService / MCP
        |
        | Python projection qualification
        v

CONFIRMED / OBSERVED_ONLY / NOT_OBSERVED_IN_WINDOW
```

Both paths implement the same architecture semantics, but no executable test currently proves that
they remain equivalent.

I1 SHALL establish this guarantee:

> **For equivalent effective observation contexts, AIP has one declared-versus-observed
> qualification rule, and its existing analysis and Architecture Intelligence execution paths
> produce the same qualification and telemetry-coverage classification for the same relation.**

I1 is a correctness-hardening increment. It SHALL NOT add a new architecture capability.

---

## 2. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The governing release specification is:

```text
docs/specifications/0.4.1/specification.md
```

If this I1 specification conflicts with that parent specification, implementation SHALL stop and
resolve the conflict explicitly. It MUST NOT silently select one interpretation.

Executable tests over real Neo4j and the existing frozen `v0.4.0` evaluation remain the authoritative
behavioral evidence when I1 exits.

---

## 3. Governing Decision — Explicit Content

I1 implements the decision currently recorded as ADR 0010, “The declared-vs-observed rule has one
owner and one executable cross-check.”

The relevant decision is reproduced here so this specification is self-contained.

### 3.1 Current duplication

The same semantics currently exist in two implementation paths.

#### Analysis / REST / UI path

`app/analysis/runtime.py` contains:

- Cypher predicates equivalent to:
  - observed evidence exists;
  - observed evidence does not exist;
  - declared evidence exists;
  - declared evidence does not exist;
- telemetry coverage classification;
- consumers including runtime analyses, REST runtime endpoints, and UI runtime views.

The current observed-evidence rule is semantically:

```text
Evidence exists for relation
AND evidence_type == OBSERVED
AND evidence.environment == requested environment
AND evidence.last_seen >= requested lower bound
AND (
    requested upper bound is absent
    OR evidence.last_seen <= requested upper bound
)
```

Declared evidence is semantically:

```text
Evidence exists for relation
AND evidence_type == DECLARED
```

Declared evidence is not restricted by runtime environment or runtime observation window.

#### Architecture Intelligence / MCP path

`app/architecture_intelligence/dependency_projection.py` independently performs equivalent
declared/observed evidence matching in Python and independently restates coverage classification.

That path is consumed by:

```text
get_service_dependencies
get_architecture_drift
```

`get_evidence` is not a qualification consumer. It resolves provenance for an already-identified
evidence reference and is outside I1's semantic comparison.

### 3.2 Why this is a defect risk

Both paths are already tested, but against separate scenario sets:

```text
evaluation/projector.py
    -> analysis/Cypher-oriented evaluation

evaluation/architecture_answers/
    -> Architecture Intelligence answer evaluation
```

A change to one implementation can therefore diverge from the other without either independent suite
necessarily failing.

The failure mode is:

```text
same canonical fact
same evidence
same environment
same effective time window

analysis path              Architecture Intelligence path
      |                              |
      v                              v
   result A                       result B

A != B
```

Two AIP surfaces answering the same semantic question differently is forbidden unless the difference
is explicitly designed, documented by a later ADR, and encoded as an expected difference.

### 3.3 Decision implemented by I1

I1 SHALL:

1. establish **one named semantic owner** for evidence matching and coverage classification;
2. preserve the two execution paths;
3. make both paths reference the shared semantic owner rather than maintaining independent semantic
   spellings;
4. add a differential integration test over one shared graph fixture;
5. prove equal qualification and equal coverage classification for equivalent effective contexts;
6. document the legitimate REST/MCP window-default asymmetry instead of removing it.

The objective is:

```text
one semantic rule
      |
      +----------------------+
      |                      |
      v                      v
analysis/Cypher         Architecture Intelligence/Python
      |                      |
      +----------+-----------+
                 |
                 v
       executable cross-check
```

The objective is **not** to merge the analysis, REST, UI, Architecture Intelligence, or MCP layers.

---

## 4. Frozen Semantic Baseline

I1 SHALL preserve the following shipped meanings.

### 4.1 Qualification vocabulary

The qualification vocabulary remains exactly:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
```

No fourth qualification state is introduced.

### 4.2 Non-observation rule

`NOT_OBSERVED_IN_WINDOW` means:

```text
the relation has DECLARED evidence
AND
no OBSERVED evidence for that relation matches the selected runtime environment and observation window
```

It MUST NOT mean:

```text
unused
dead
obsolete
removed
unreachable
false
safe to delete
```

Non-observation remains distinct from absence.

### 4.3 Coverage vocabulary

Coverage remains exactly:

```text
SUFFICIENT
PARTIAL
NONE
UNKNOWN
```

Coverage qualifies how much telemetry exists around a
`NOT_OBSERVED_IN_WINDOW` result. It is not a confidence score.

### 4.4 Existing public contracts

I1 SHALL preserve:

```text
ArchitectureAnswer<T>.schema_version == "0.4"

exactly three MCP tools:
- get_service_dependencies
- get_architecture_drift
- get_evidence

read-only MCP behavior
snapshot binding
observation-context binding
evidence/provenance references
existing claim identity
existing limitation vocabulary
```

Normal producer metadata may report application version `0.4.1`; that is not a schema-version change.

---

## 5. Scope Budget

I1 has the following fixed budget:

| Area | I1 limit |
|---|---|
| Semantic objective | Qualification consistency only |
| Shared semantic owner | One internal qualification module |
| Existing execution paths | Preserve both |
| Differential integration fixture | One shared deterministic fixture family |
| Qualification vocabulary | No change |
| Coverage vocabulary | No change |
| MCP tools | No change; exactly 3 |
| MCP protocol | No change |
| ArchitectureAnswer schema | No breaking change |
| Canonical Model | No change |
| Graph Schema | No change |
| Source adapters | No change |
| Runtime discovery | No widening |
| Messaging operation recognition | No widening |
| Topic / Subscription | None |
| Graph writes from Architecture Intelligence/MCP | Zero |
| LLM usage | Zero |

---

## 6. In Scope

I1 SHALL deliver:

1. a named internal semantic owner for evidence-window matching;
2. a named internal semantic owner for telemetry coverage classification;
3. shared Cypher predicate fragments derived from that owner for the analysis path;
4. shared Python predicates/functions derived from that owner for the Architecture Intelligence path;
5. migration of the existing analysis path to the shared owner;
6. migration of the existing dependency/drift projection path to the shared owner;
7. a real-Neo4j differential integration test over shared deterministic fixtures;
8. explicit comparison of qualification and coverage results;
9. explicit tests for environment and observation-window boundaries;
10. documentation of REST/MCP effective-window differences;
11. full regression of the shipped `v0.4.0` Architecture Answers evaluation;
12. acceptance of ADR 0010 once the implementation and cross-check are complete.

---

## 7. Explicit Non-Goals

I1 SHALL NOT implement:

```text
topic-vs-queue guard
service-identity guard
Pub/Sub support
Topic entity
Subscription entity
Kubernetes discovery
new source adapter
Adapter Registry
SourceDescriptor
source-scoped reimport
messaging.operation widening
messaging.operation.type widening
new runtime telemetry attribute support
snapshot fingerprint caching
observed-evidence retention or compaction
new MCP tool
new REST endpoint
generic Cypher tool
transitive dependency analysis
new architecture-analysis algorithm
REST/ArchitectureIntelligence layer convergence
migration of all REST/UI Cypher behind ArchitectureIntelligenceService
historical architecture
Intent / Desired State / Transformation
LLM-based qualification
```

The topic/queue and service-identity safety work belongs to I2 of `v0.4.1`.

---

## 8. Required Internal Architecture

I1 SHALL introduce one internal qualification module as the named semantic owner.

The recommended repository location is:

```text
app/qualification/declared_observed.py
```

An equivalent path MAY be chosen during implementation only if it preserves the same architectural
boundary and the final path is documented in the completion record.

The module is internal. It is not a new public API.

Conceptually:

```text
                    app/qualification/declared_observed.py
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
app/analysis/runtime.py              dependency_projection.py
      Cypher path                         Python path
             |                                     |
             +------------------+------------------+
                                |
                                v
                    differential integration test
```

The shared module MUST NOT import:

```text
FastAPI
MCP
Neo4j Session
ArchitectureIntelligenceService
public ArchitectureAnswer envelopes
LLM clients
```

It SHOULD be a small deterministic semantics module.

---

## 9. Shared Semantic Owner

The shared owner SHALL define the semantics required by both paths.

At minimum it SHALL own:

```text
DECLARED evidence recognition
OBSERVED evidence recognition
environment matching
observation-window matching
coverage classification
relation-kind -> relevant coverage mapping
```

It MAY also own the internal qualification table if doing so reduces duplication without coupling the
public contract enums to analysis internals.

### 9.1 Public enum decoupling stays intact

`app/architecture_intelligence/contracts.py` MAY continue to define its public enums independently by
value.

I1 MUST NOT force the public `ArchitectureAnswer<T>` contract to import internal analysis enums.

A valid structure is:

```text
shared semantic literal/internal result
        |
        +--> analysis path maps to existing analysis literals
        |
        +--> Architecture Intelligence path maps to existing public enums
```

The requirement is semantic identity, not Python type identity.

---

## 10. Evidence Matching — Normative Semantics

### 10.1 Declared evidence

An evidence reference matches as declared if and only if:

```text
the referenced Evidence exists
AND
evidence.evidence_type == "DECLARED"
```

Environment and observation-window fields SHALL NOT affect declared-evidence matching.

A dangling evidence id SHALL NOT count as declared evidence.

### 10.2 Observed evidence

An evidence reference matches as observed if and only if:

```text
the referenced Evidence exists
AND
evidence.evidence_type == "OBSERVED"
AND
evidence.environment == requested environment
AND
evidence.last_seen is not null
AND
evidence.last_seen >= window_start
AND
(
    window_end is null
    OR
    evidence.last_seen <= window_end
)
```

The lower bound is inclusive.

When an upper bound exists, the upper bound is inclusive.

A dangling evidence id SHALL NOT count as observed evidence.

An observed Evidence record whose `last_seen` is null SHALL NOT match.

### 10.3 Environment equality

Environment matching is exact according to the existing stored and requested environment values.

I1 SHALL NOT introduce:

```text
case folding
aliases
wildcards
environment inheritance
fuzzy matching
cross-environment fallback
```

### 10.4 Evidence set behavior

For one canonical relation:

```text
declared_matches = sorted valid DECLARED evidence ids
observed_matches = sorted valid OBSERVED evidence ids matching environment/window
```

Input order MUST NOT affect the result.

Duplicate evidence ids MUST NOT create duplicate semantic evidence references.

---

## 11. Qualification Table — Normative

The qualification rule is:

| Declared match | Observed match | Result |
|---|---|---|
| yes | yes | `CONFIRMED` |
| no | yes | `OBSERVED_ONLY` |
| yes | no | `NOT_OBSERVED_IN_WINDOW` |
| no | no | no supported qualified relation/claim |

For `CONFIRMED`:

```text
qualifying evidence = union(declared_matches, observed_matches)
coverage = null
```

For `OBSERVED_ONLY`:

```text
qualifying evidence = observed_matches
coverage = null
```

For `NOT_OBSERVED_IN_WINDOW`:

```text
qualifying evidence = declared_matches
coverage = classify_coverage(...)
```

For neither:

```text
the relation MUST NOT be promoted into a supported qualified architecture claim merely because the
graph relation exists
```

A relation with only dangling evidence references is therefore semantically equivalent to “neither”
for qualification.

---

## 12. Coverage Classification — Normative

The shared coverage rule SHALL preserve current semantics.

Inputs:

```text
qualification_enabled
service coverage exists
relation kind
http_observed
messaging_observed
spans_observed
```

### 12.1 Relevant coverage mapping

Relevant telemetry is determined by relation kind:

```text
CALLS
    -> http_observed

SENDS
    -> messaging_observed

RECEIVES_FROM
    -> messaging_observed
```

I1 SHALL NOT introduce new relation families.

### 12.2 Classification

Coverage SHALL be:

```text
if qualification is disabled:
    UNKNOWN

else if no service coverage row exists:
    UNKNOWN

else if telemetry of the relevant relation kind was observed:
    SUFFICIENT

else if any usable telemetry spans were observed for the service:
    PARTIAL

else:
    NONE
```

Equivalent boolean form:

| Enabled | Coverage row | Relevant kind observed | Any spans observed | Result |
|---|---|---|---|---|
| no | any | any | any | `UNKNOWN` |
| yes | no | n/a | n/a | `UNKNOWN` |
| yes | yes | yes | yes | `SUFFICIENT` |
| yes | yes | no | yes | `PARTIAL` |
| yes | yes | no | no | `NONE` |

Coverage is meaningful only for `NOT_OBSERVED_IN_WINDOW`.

For `CONFIRMED` and `OBSERVED_ONLY`, the Architecture Intelligence answer SHALL continue to expose
`coverage = null`.

---

## 13. Shared Cypher Predicates

The analysis path currently embeds independent Cypher strings for declared and observed evidence.

After I1, the authoritative Cypher fragments SHALL originate from the shared semantic owner.

Conceptually:

```cypher
EXISTS {
    UNWIND r.evidence_ids AS eid
    MATCH (e:Evidence {id: eid})
    WHERE e.evidence_type = 'DECLARED'
}
```

and:

```cypher
EXISTS {
    UNWIND r.evidence_ids AS eid
    MATCH (e:Evidence {id: eid})
    WHERE e.evidence_type = 'OBSERVED'
      AND e.environment = $environment
      AND e.last_seen >= $since
      AND ($until IS NULL OR e.last_seen <= $until)
}
```

The exact symbol names MAY differ.

The semantics MUST NOT differ.

Negative forms SHOULD be constructed from the authoritative positive rule where practical rather than
maintained as independent semantic text.

For example:

```text
NOT (<authoritative observed-exists expression>)
```

is preferred over a separately maintained copy of the observed predicate.

If Cypher syntax requires a distinct wrapper, the inner evidence predicate MUST remain shared.

---

## 14. Shared Python Predicates

The Architecture Intelligence projection path SHALL use the shared semantic owner for Python
matching.

Conceptually:

```text
matches_declared_evidence(...)
matches_observed_evidence(...)
classify_telemetry_coverage(...)
```

The exact API MAY differ, but `dependency_projection.py` SHALL NOT continue to contain an independent
copy of the evidence-window rules after I1.

The projection layer may continue to own:

```text
claim construction
destination resolution
delivery projection
claim id construction
public enum mapping
evidence union for public claims
limitations
```

Those concerns are not part of the shared qualification kernel.

---

## 15. Analysis Path Migration

`app/analysis/runtime.py` SHALL consume the shared semantic owner.

I1 SHALL NOT change the externally observable meaning of existing analysis operations.

In particular:

```text
O1 observed relation queries
O2/O3 confirmed/observed-only logic
O4 not-observed logic
O5 telemetry coverage
service_runtime_profile
runtime REST/UI consumers
```

must remain behaviorally compatible except where a differential test exposes a pre-existing
inconsistency between the two paths.

If implementation discovers a real pre-existing inconsistency, it SHALL:

1. stop treating I1 as a mechanical refactor;
2. record the exact divergent case;
3. identify which behavior matches the governing existing semantics;
4. add an explicit regression test;
5. change only the incorrect path;
6. document the correction in the I1 completion record.

I1 MUST NOT silently choose whichever path is easier to preserve.

---

## 16. Architecture Intelligence Path Migration

`app/architecture_intelligence/dependency_projection.py` SHALL consume the same shared evidence and
coverage semantics.

The following remain outside the shared kernel and SHALL keep their existing responsibilities:

```text
DIRECT_DEPENDENCY claim projection
CALLS -> provider Service destination resolution
SENDS -> consumer Service destination resolution
delivery.via construction
claim_id
resolution_evidence_refs
limitations
deterministic claim ordering
```

`get_service_dependencies` and `get_architecture_drift` SHALL continue to expose their existing
`v0.4` public contracts.

`get_evidence` SHALL remain unchanged except for incidental refactoring required by imports.

---

## 17. Differential Test — Required Architecture

I1 SHALL add an integration test under:

```text
tests/integration/
```

The test MUST use real Neo4j.

A recommended file name is:

```text
tests/integration/test_qualification_consistency.py
```

An equivalent name MAY be used.

The test SHALL:

1. create one deterministic shared graph fixture;
2. exercise the real analysis/Cypher path;
3. exercise the real Architecture Intelligence/Python path;
4. normalize the outputs to the underlying canonical relation being qualified;
5. compare qualification and coverage;
6. fail on any unexplained difference.

It SHALL NOT merely call the shared helper twice.

The purpose is to catch:

```text
query wiring differences
parameter differences
environment differences
window-boundary differences
coverage mapping differences
evidence-loading differences
projection wiring differences
```

even after the low-level rule itself is shared.

---

## 18. Differential Comparison Identity

The two user-facing paths do not project every relation into the same final shape.

For example:

```text
analysis SENDS status
    -> Service -> Queue

Architecture Intelligence dependency claim
    -> Service -> Consumer Service
       with delivery.via == Queue
```

Therefore I1 SHALL compare the **underlying qualified canonical relation**, not the final public
destination object.

A normalized comparison key SHALL contain at least:

```text
subject_service_id
relation_type
delivery_target_id
```

For `CALLS`:

```text
relation_type = CALLS
delivery_target_id = Operation id
```

For `SENDS`:

```text
relation_type = SENDS
delivery_target_id = Queue id
```

The normalized comparison result SHALL contain:

```text
qualification
coverage
```

It MAY additionally compare the qualifying evidence ids where the two paths expose enough raw data
to do so without weakening the test boundary.

The differential test MUST NOT report a false mismatch merely because Architecture Intelligence
resolves a delivery target to a logical destination Service.

---

## 19. Differential Fixture — Required Cases

The fixture SHALL use fixed timestamps and explicit environments. It MUST NOT depend on wall-clock
time.

A recommended comparison context is:

```text
environment = "qualification-test"
window_start = 2026-09-01T00:00:00Z
window_end   = 2026-09-02T00:00:00Z
```

The fixture SHALL include at least the following cases.

### Q1 — HTTP declared + observed

```text
CALLS relation
DECLARED evidence
OBSERVED evidence in environment and window
```

Expected:

```text
CONFIRMED
coverage = null
```

### Q2 — HTTP observed only

```text
CALLS relation
no DECLARED evidence
OBSERVED evidence in environment and window
```

Expected:

```text
OBSERVED_ONLY
coverage = null
```

### Q3 — HTTP declared only with sufficient HTTP coverage

```text
CALLS relation
DECLARED evidence
no matching OBSERVED evidence for this relation
other matching HTTP telemetry exists for the subject service
```

Expected:

```text
NOT_OBSERVED_IN_WINDOW
SUFFICIENT
```

### Q4 — HTTP declared only with partial coverage

```text
CALLS relation
DECLARED evidence
no matching OBSERVED evidence for this relation
no matching HTTP telemetry
matching messaging telemetry exists for the subject service
```

Expected:

```text
NOT_OBSERVED_IN_WINDOW
PARTIAL
```

### Q5 — HTTP declared only with no coverage

```text
CALLS relation
DECLARED evidence
no matching OBSERVED evidence for this relation
no usable telemetry for the subject service
```

Expected:

```text
NOT_OBSERVED_IN_WINDOW
NONE
```

### Q6 — Messaging declared + observed

```text
SENDS relation
DECLARED evidence
OBSERVED evidence in environment and window
```

Expected:

```text
CONFIRMED
coverage = null
```

### Q7 — Messaging observed only

```text
SENDS relation
no DECLARED evidence
OBSERVED evidence in environment and window
```

Expected:

```text
OBSERVED_ONLY
coverage = null
```

### Q8 — Messaging declared only with sufficient messaging coverage

```text
SENDS relation
DECLARED evidence
no matching OBSERVED evidence for this relation
other matching messaging telemetry exists for the subject service
```

Expected:

```text
NOT_OBSERVED_IN_WINDOW
SUFFICIENT
```

### Q9 — Wrong environment

```text
DECLARED evidence
OBSERVED evidence exists but only for another environment
```

Expected for the selected environment:

```text
NOT_OBSERVED_IN_WINDOW
```

Coverage is determined independently from the selected environment's service coverage.

### Q10 — Before lower boundary

```text
OBSERVED.last_seen < window_start
```

The observed evidence MUST NOT match.

### Q11 — Exactly lower boundary

```text
OBSERVED.last_seen == window_start
```

The observed evidence MUST match.

### Q12 — Exactly upper boundary

```text
OBSERVED.last_seen == window_end
```

The observed evidence MUST match.

### Q13 — After upper boundary

```text
OBSERVED.last_seen > window_end
```

The observed evidence MUST NOT match.

### Q14 — Dangling evidence reference

```text
relation.evidence_ids contains id with no Evidence node
```

The dangling id MUST NOT count as declared or observed.

If no other valid evidence exists:

```text
no supported qualified relation/claim
```

### Q15 — Neither declared nor observed

```text
relation exists
no valid DECLARED evidence
no valid matching OBSERVED evidence
```

Expected:

```text
no supported qualified relation/claim
```

The two paths SHALL agree on exclusion.

---

## 20. Optional Additional Cases

I1 SHOULD add these cases if they can be expressed without broadening scope:

```text
duplicate evidence ids
multiple observed evidence buckets in the same window
observed evidence both inside and outside the window
declared evidence plus wrong-environment observed evidence
relation insertion order variation
evidence insertion order variation
```

The output MUST remain deterministic.

---

## 21. Open-Ended REST Window

The analysis/REST path supports an absent upper bound:

```text
until = null
```

The MCP Architecture Intelligence operations use explicit observation contexts with a finite
`window_end` under the shipped `v0.4` contract.

This difference is legitimate.

### 21.1 Differential-test rule

The required cross-path differential comparison SHALL use an equivalent effective bounded context:

```text
analysis:
since = X
until = Y

Architecture Intelligence:
window_start = X
window_end = Y
```

That isolates semantic qualification from request-default differences.

### 21.2 Separate analysis-only regression

I1 SHALL preserve an analysis-path regression proving:

```text
until = null
```

still means:

```text
no upper observation bound
```

This case is not required to have an MCP twin.

---

## 22. Default REST Window

The analysis/REST path may derive a default lower bound relative to the current clock when the caller
does not provide one.

Architecture Intelligence/MCP requires an explicit observation context for the relevant tools.

I1 SHALL document:

> A relation can legitimately receive a different qualification from REST and MCP when the two
> requests resolve to different effective observation windows.

This is not semantic divergence.

Semantic divergence means:

```text
same relation
same evidence
same environment
same effective lower bound
same effective upper bound

but different qualification or coverage
```

That condition SHALL fail the differential test.

---

## 23. Qualification-Disabled Behavior

The analysis subsystem supports cases where qualification/coverage classification is disabled.

The shared coverage owner SHALL preserve:

```text
qualification disabled -> coverage UNKNOWN
```

If the Architecture Intelligence path has no equivalent public request mode, this behavior SHALL be
covered by shared-kernel and analysis-path tests rather than fabricated into the MCP contract.

I1 SHALL NOT add a new MCP input solely to produce `UNKNOWN`.

---

## 24. Determinism Requirements

The shared semantic owner SHALL be deterministic.

Given identical:

```text
relation evidence ids
evidence records
environment
window_start
window_end
coverage inputs
```

it MUST return identical semantics independent of:

```text
database row order
evidence insertion order
Python dictionary order
relation insertion order
test execution time
process restart
```

Evidence-id outputs, where returned, SHALL be sorted.

The differential fixture SHALL use fixed timestamps and fixed ids.

No random values or current-time calls may influence expected qualification.

---

## 25. Error and Missing-Data Semantics

I1 SHALL preserve conservative behavior.

### 25.1 Missing Evidence node

```text
evidence id referenced
Evidence node absent
```

Result:

```text
reference does not qualify as DECLARED
reference does not qualify as OBSERVED
```

No evidence type is guessed from the id string.

### 25.2 Missing observed `last_seen`

```text
evidence_type = OBSERVED
last_seen = null
```

Result:

```text
does not match observation window
```

I1 MUST NOT substitute:

```text
first_seen
current time
ingestion time
```

unless a separately approved semantic change explicitly requires it.

### 25.3 Missing service coverage row

For coverage classification:

```text
UNKNOWN
```

This remains a “cannot assess coverage” result, not `NONE`.

---

## 26. No Public Schema Change

I1 SHALL NOT change the frozen `v0.4` public answer schema.

The existing schema drift test SHALL continue to pass.

No new field is added to:

```text
ArchitectureAnswer
DependencyClaim
Drift answer
Evidence answer
ObservationContext
SnapshotRef
```

No enum value is added.

The shared internal qualification module MUST remain implementation detail.

---

## 27. No MCP Surface Change

The MCP server SHALL continue to expose exactly:

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

I1 SHALL NOT change:

```text
tool names
input schemas
output schemas
read-only behavior
transport behavior
tool count
```

except producer version/build metadata that naturally identifies the `0.4.1` artifact.

The differential test does not require adding a diagnostic MCP tool.

---

## 28. Existing Evaluation Regression

The complete existing Architecture Answers evaluation SHALL pass after I1.

The current suite contains 23 deterministic scenarios.

I1 SHALL NOT regenerate expected answers from the implementation.

If any existing scenario changes because I1 exposes a real pre-existing semantic inconsistency:

1. the mismatch SHALL be captured independently;
2. the governing existing semantic rule SHALL determine the correct side;
3. the implementation defect SHALL be fixed;
4. the expected fixture SHALL change only if the old expected result itself is proven wrong;
5. the completion record SHALL name the exact scenario and rationale.

“Shared implementation now returns something else” is not sufficient justification.

---

## 29. Required Integration-Test Execution

The differential test SHALL run against real Neo4j, not a mocked repository.

It SHOULD exercise the same application-level functions used in production paths.

The comparison MUST include at least:

```text
CALLS
SENDS
```

`RECEIVES_FROM` SHOULD be covered in shared-kernel or analysis tests even if it is not required by
the outgoing dependency operation.

The integration test MUST fail if either path is accidentally rewired to:

```text
wrong environment
different bounds
different evidence type
different coverage relation family
different dangling-evidence behavior
```

---

## 30. Implementation Slices

I1 SHOULD be implemented in three small slices.

### I1.1 — Shared Qualification Kernel

Deliver:

```text
internal qualification module
declared-evidence predicate
observed-evidence predicate
shared coverage classifier
shared relation-kind coverage mapping
unit tests for exact boundary semantics
```

No consumer behavior should change intentionally in this slice.

### I1.2 — Wire Both Existing Paths

Deliver:

```text
analysis/runtime path imports shared Cypher/coverage semantics
dependency_projection imports shared Python/coverage semantics
duplicate semantic spellings removed
public schemas unchanged
existing focused tests pass
```

Any remaining duplication MUST be mechanical representation, not independent semantic ownership.

### I1.3 — Differential Qualification and Completion

Deliver:

```text
shared deterministic Neo4j fixture
real cross-path differential integration test
REST/MCP window-asymmetry documentation
full existing evaluation regression
ADR 0010 status update to Accepted
I1 completion record / verification evidence
```

These slice labels are local to this I1 specification. They do not define or imply an iteration
structure for `v0.5.0`.

---

## 31. Expected Repository Changes

The exact file set may vary, but the implementation is expected to touch approximately:

```text
app/qualification/__init__.py                       # if a new package is used
app/qualification/declared_observed.py             # new semantic owner
app/analysis/runtime.py                             # consume shared Cypher/coverage semantics
app/architecture_intelligence/dependency_projection.py
tests/unit/...qualification...                     # shared semantic boundary tests
tests/integration/test_qualification_consistency.py
docs/adr/0010-single-qualification-rule.md          # Proposed -> Accepted when complete
docs/adr/README.md                                  # status/index update if needed
docs/specifications/0.4.1/i1-qualification-consistency.md
```

I1 MUST NOT require changes to:

```text
app/canonical/model.py
Graph Schema relation families
MCP tool registration
source adapters
telemetry attribute allowlists
```

If implementation discovers that one of those changes is required, I1 scope SHALL be re-reviewed
before proceeding.

---

## 32. Review Invariants

Code review SHALL explicitly check these invariants.

### QI-1 — One semantic owner

There is no independent evidence-window rule left in both:

```text
app/analysis/runtime.py
app/architecture_intelligence/dependency_projection.py
```

### QI-2 — Shared semantics, separate contracts

The public Architecture Intelligence enums remain decoupled from analysis implementation types.

### QI-3 — Cypher and Python both exercised

The differential test reaches:

```text
real Cypher analysis path
real Python projection path
```

It is not a helper-vs-helper unit test.

### QI-4 — Same effective context

Every compared result uses exactly the same:

```text
environment
lower bound
upper bound
```

### QI-5 — Relation identity preserved

The test compares the qualified underlying `CALLS`/`SENDS` relation, not two different destination
projection shapes.

### QI-6 — No public expansion

Tool count, schema family, Canonical Model, and discovery sources remain unchanged.

---

## 33. Test Matrix

At minimum I1 SHALL provide executable evidence for:

| ID | Relation | Evidence/context | Expected qualification | Expected coverage |
|---|---|---|---|---|
| Q1 | `CALLS` | declared + matching observed | `CONFIRMED` | null |
| Q2 | `CALLS` | matching observed only | `OBSERVED_ONLY` | null |
| Q3 | `CALLS` | declared only + HTTP telemetry | `NOT_OBSERVED_IN_WINDOW` | `SUFFICIENT` |
| Q4 | `CALLS` | declared only + messaging-only telemetry | `NOT_OBSERVED_IN_WINDOW` | `PARTIAL` |
| Q5 | `CALLS` | declared only + no telemetry | `NOT_OBSERVED_IN_WINDOW` | `NONE` |
| Q6 | `SENDS` | declared + matching observed | `CONFIRMED` | null |
| Q7 | `SENDS` | matching observed only | `OBSERVED_ONLY` | null |
| Q8 | `SENDS` | declared only + messaging telemetry | `NOT_OBSERVED_IN_WINDOW` | `SUFFICIENT` |
| Q9 | either | observed only in different environment + declared | `NOT_OBSERVED_IN_WINDOW` | derived from selected env |
| Q10 | either | observed before lower bound + declared | `NOT_OBSERVED_IN_WINDOW` | derived |
| Q11 | either | observed exactly at lower bound + declared | `CONFIRMED` | null |
| Q12 | either | observed exactly at upper bound + declared | `CONFIRMED` | null |
| Q13 | either | observed after upper bound + declared | `NOT_OBSERVED_IN_WINDOW` | derived |
| Q14 | either | only dangling evidence refs | excluded | n/a |
| Q15 | either | no valid declared or observed evidence | excluded | n/a |

The implementation MAY split these across more than one fixture as long as they share the same
semantic setup and the differential test covers both execution paths.

---

## 34. Performance Expectations

I1 is not a performance increment.

The shared semantic owner MUST NOT introduce a material additional database round trip for each
relation.

No performance target is added.

The full-graph snapshot/read-cost benchmark belongs to I3 of `v0.4.1`, not I1.

If the refactor causes a clear order-of-magnitude regression in existing qualification queries, I1
SHALL stop and investigate before completion.

---

## 35. Security and Mutation Boundary

I1 introduces no new write path.

Architecture Intelligence and MCP calls remain read-only.

The differential fixture may write setup data into disposable test Neo4j, but production
qualification calls MUST NOT mutate graph state.

No LLM may participate in:

```text
evidence classification
environment matching
window matching
coverage classification
qualification selection
differential comparison
```

---

## 36. Documentation Requirements

I1 SHALL update documentation so the following is explicit:

### Analysis / REST

```text
The REST/runtime path may use an implicit clock-relative default observation window and may allow an
open-ended upper bound.
```

### Architecture Intelligence / MCP

```text
The relevant MCP architecture tools require the explicit observation context defined by the v0.4
contract.
```

### Cross-surface interpretation

The documentation SHALL state exactly:

> **Equivalent effective observation contexts MUST produce equivalent qualification semantics.
> Different effective observation windows MAY legitimately produce different qualifications.**

This is the line reviewers and users should use to distinguish intended request-contract asymmetry
from implementation divergence.

---

## 37. ADR 0010 Completion

ADR 0010 is currently `Proposed`.

It SHALL move to `Accepted` only when:

```text
shared semantic owner exists
both execution paths consume it
differential integration test exists
differential test passes
window asymmetry is documented
existing public contracts remain unchanged
```

The ADR status MUST NOT be changed merely because the shared module has been created.

---

## 38. I1 Verification Record

The I1 completion evidence SHALL record:

```text
exact commit SHA
files changed
shared semantic owner path
differential test path
fixture cases executed
qualification mismatches
coverage mismatches
existing Architecture Answers scenario result
public schema drift result
MCP tool-count result
CI result
CodeQL/security result where run for the increment
```

Required semantic completion statement:

```text
qualification mismatches = 0
coverage mismatches = 0
unexplained differential cases = 0
```

If any intended difference exists, I1 is NOT complete until that difference is separately recorded
as an approved architectural decision.

---

## 39. Definition of Done

I1 is complete only when all of the following are true:

### Shared semantics

```text
[ ] one named internal qualification owner exists
[ ] DECLARED matching has one semantic definition
[ ] OBSERVED matching has one semantic definition
[ ] environment matching has one semantic definition
[ ] lower/upper window matching has one semantic definition
[ ] coverage classification has one semantic definition
[ ] relation-kind coverage mapping has one semantic definition
```

### Analysis path

```text
[ ] analysis/Cypher predicates consume the shared owner
[ ] analysis coverage classification consumes the shared owner
[ ] existing runtime behavior remains compatible
[ ] open-ended REST upper-window behavior remains supported
```

### Architecture Intelligence path

```text
[ ] dependency projection consumes shared evidence semantics
[ ] dependency projection consumes shared coverage semantics
[ ] get_service_dependencies public contract is unchanged
[ ] get_architecture_drift public contract is unchanged
[ ] get_evidence semantics are unchanged
```

### Differential qualification

```text
[ ] real Neo4j shared fixture exists
[ ] real analysis/Cypher path is exercised
[ ] real Architecture Intelligence/Python path is exercised
[ ] CALLS is compared
[ ] SENDS is compared
[ ] declared-only is compared
[ ] observed-only is compared
[ ] declared + observed is compared
[ ] neither is compared
[ ] wrong-environment behavior is compared
[ ] lower boundary is compared
[ ] upper boundary is compared
[ ] dangling evidence behavior is compared
[ ] qualification mismatches = 0
[ ] coverage mismatches = 0
```

### Scope preservation

```text
[ ] no Canonical Model change
[ ] no Graph Schema relation-family change
[ ] no new discovery source
[ ] no messaging-operation widening
[ ] no Pub/Sub model
[ ] no new MCP tool
[ ] MCP tool count remains exactly 3
[ ] ArchitectureAnswer schema_version remains "0.4"
[ ] graph writes through MCP remain zero
[ ] LLM usage for qualification remains zero
```

### Regression and closure

```text
[ ] existing 23 Architecture Answers scenarios pass
[ ] public schema drift test passes
[ ] relevant runtime/analysis tests pass
[ ] deterministic ordering tests pass
[ ] ADR 0010 moves to Accepted only after all semantic gates pass
[ ] exact I1 candidate commit is recorded
[ ] I1 completion record reports 0 unexplained semantic differences
```

---

## 40. I1 Exit Statement

The canonical I1 exit statement SHALL have this form:

```text
GO — At <commit>, AIP's analysis/REST and ArchitectureIntelligenceService/MCP qualification paths
are governed by one declared-versus-observed semantic owner. Against a shared deterministic
real-Neo4j fixture, equivalent effective observation contexts produce qualification mismatches = 0
and coverage mismatches = 0 across CALLS and SENDS cases including declared-only, observed-only,
confirmed, environment mismatch, window boundaries, and unsupported/dangling evidence. The shipped
v0.4 public schemas and exactly three read-only MCP tools remain unchanged.
```

If that statement cannot be supported by executable evidence, I1 is `NO-GO`.

---

## 41. Handoff to I2

I1 establishes consistency of AIP's existing qualification semantics.

It deliberately does not solve the messaging-safety problems assigned to I2.

The handoff is:

```text
I1
one qualification rule
+ executable cross-path consistency

        ↓

I2
topic-vs-queue safety guard
+ service-identity safety guard
```

I2 MAY rely on I1's shared qualification semantics.

I2 MUST NOT weaken them.
