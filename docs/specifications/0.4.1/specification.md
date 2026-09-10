# AIP v0.4.1 Release Specification — Semantic Hardening for Broader Discovery

**Status:** Draft 0.1 — release specification  
**Target release:** `v0.4.1`  
**Release theme:** Semantic Hardening for Broader Discovery  
**Entry baseline:** Published and post-release-verified `v0.4.0`  
**Primary outcome:** AIP enters `v0.5.0` with one executable declared-vs-observed qualification rule, a guarded messaging-correlation boundary that cannot silently turn Pub/Sub-shaped evidence into a canonical `Queue`, and a guarded service-identity boundary that refuses ambiguous runtime identities, without expanding the public MCP surface or the Canonical Model.

---

## 1. Release Promise

`v0.4.0` made AIP's validated architecture intelligence safely consumable by external tools and AI agents. The post-release architecture review found no need for a large-scale refactoring, but it identified several structural and semantic decisions that become load-bearing once `v0.5.0` broadens architecture discovery.

`v0.4.1` is a deliberately small hardening release. It SHALL prove this capability:

> **Before AIP broadens discovery or introduces first-class Pub/Sub semantics, the existing architecture-intelligence surfaces agree on qualification semantics, and the runtime messaging path refuses destination or service identities that cannot safely support the current canonical `Queue` model.**

The release is not a discovery release. It does not add Kubernetes, Topic, Subscription, new source adapters, or new MCP tools.

```text
v0.4.0
Trusted Architecture Context for Agents

        ↓

v0.4.1
Semantic hardening
- one executable qualification rule
- queue/topic safety guard
- service-identity safety guard
- reproducible read-cost baseline

        ↓

v0.5.0
Broader Architecture Discovery
- real adapter seam
- generic Pub/Sub model
- Kubernetes discovery
- deeper runtime reconciliation
```

The governing principles remain:

> **AIP may help agents reason about architecture, but an agent must never become the source of architectural truth.**

and:

> **Recognizing a telemetry signal is not the same as qualifying a canonical architecture fact.**

---

## 2. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

Examples in this document illustrate semantics. Executable tests, frozen evaluation fixtures, and published release artifacts SHALL be the authoritative implementation evidence.

---

## 3. Source Decisions and Entry Conditions

This specification is self-contained. The repository documents that motivated it are summarized
normatively below so that implementation does not depend on following external or relative links.

For traceability, the corresponding repository documents are:

- `docs/architecture-review-0.4.0.md`
- `docs/adr/0010-single-qualification-rule.md`
- `docs/adr/0011-snapshot-identity-read-cost.md`
- `docs/adr/0013-no-topic-family-without-guards.md`
- `docs/real-world-validation/cross-system/decisions/queue-topic-boundary.md`
- `docs/real-world-validation/cross-system/decisions/messaging-operation-compatibility.md`

### 3.1 Post-`v0.4.0` architecture review — relevant findings

The architecture review concluded that **no large-scale refactoring is warranted** before
`v0.5.0`. The following load-bearing decisions were found sound and SHALL remain unchanged by
`v0.4.1` unless this specification explicitly says otherwise:

- the Canonical Model remains the single mapping target for all sources;
- adapters do not write directly to Neo4j;
- canonical IDs remain deterministic and path-independent;
- facts retain evidence references and imports remain atomic;
- the revision-fenced stable-read mechanism remains the basis for snapshot-consistent answers;
- the `ArchitectureAnswer<T>` contract remains frozen against silent drift;
- the LLM and MCP boundaries remain read-only;
- non-obvious semantic rules remain backed by explicit specification/ADR rationale.

The review identified four structural findings:

| Finding | Meaning | `v0.4.1` disposition |
|---|---|---|
| **F1 — adapter extension point is a convention, not a seam** | `parse_sources` and filesystem scanning are hard-coded around per-service directories. Kubernetes and other broader sources do not fit this shape. | **Deferred to `v0.5.0`.** No Adapter Registry or `SourceDescriptor` in this patch release. |
| **F2 — qualification exists in two paths without an executable cross-check** | The analysis/REST path and Architecture Intelligence/MCP path independently implement declared-vs-observed qualification. Their scenario suites are separate, so silent divergence is possible. | **Implement in `v0.4.1`.** One named semantic owner plus a differential integration test over shared fixtures. |
| **F3 — read cost grows with the whole graph and observed evidence is unbounded** | Snapshot fingerprinting reads the full graph. The review measured about **16.06 s** for fingerprinting and **29.1 s** end-to-end for `get_service_dependencies` at about **98,566 nodes**. Observed evidence also grows without bound. | **Benchmark only in `v0.4.1`.** Commit a reproducible benchmark; do not change snapshot or retention semantics in this patch release. |
| **F4 — the queue/topic boundary was only captured in validation records** | The Canonical Model has competing-consumer `Queue` semantics only. Widening runtime messaging recognition is unsafe until both destination-kind and service-identity guards exist. | **Implement both guards in `v0.4.1`.** Generic Pub/Sub remains for `v0.5.0`. |

### 3.2 ADR 0010 — one qualification rule, one executable cross-check

AIP currently has two user-visible qualification paths:

```text
analysis / REST / UI
    -> Cypher-based runtime qualification

ArchitectureIntelligenceService / MCP
    -> Python projection-based qualification
```

Both classify architecture relations using the same conceptual states:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
```

They also apply observation-window and telemetry-coverage rules. The problem is not that two
implementations exist; the problem is that nothing executable proves they remain semantically
equivalent.

`v0.4.1` therefore SHALL:

1. establish one named semantic owner for the predicate
   "does this evidence count as observed for `(environment, observation window)`?";
2. make both execution paths reference that rule or a representation derived from the same rule;
3. add a differential integration test over one shared Neo4j fixture;
4. require equal qualification and equal coverage classification for equivalent effective
   observation contexts;
5. keep the existing REST/MCP request-window asymmetry documented rather than pretending the two
   request contracts are identical.

The two layers are **not** required to merge. The objective is semantic consistency, not
architectural convergence.

### 3.3 ADR 0011 — snapshot identity must not require a full-graph read forever

Every `ArchitectureAnswer` identifies a committed state using `snapshot_id` / `model_revision`.
Today the fingerprint is computed from the complete queryable graph, including all Evidence nodes
and relations. The stable-read algorithm may repeat that operation if the revision fence changes
while the answer is being assembled.

The post-`v0.4.0` review measured this cost approximately as follows:

| Evidence nodes | Total nodes | Fingerprint |
|---:|---:|---:|
| 6 | 124 | 0.05 s |
| 4,604 | 4,722 | 0.75 s |
| 23,004 | 23,122 | 3.60 s |
| 97,548 | 98,566 | 16.06 s |

At roughly 98k total nodes, one end-to-end `get_service_dependencies` call measured about
**29.1 seconds** on the review machine.

ADR 0011 proposes a future revision-fence-aware fingerprint cache and request-scoped lookup
optimization. That implementation is **not** part of `v0.4.1`, because it narrows the meaning of
`snapshot_id`: out-of-band database writes would no longer change the fingerprint until a fenced
AIP write occurs.

`v0.4.1` SHALL instead make the measurement reproducible by committing a deterministic benchmark
and machine-readable benchmark result format. This provides qualified evidence for the later
implementation without changing public snapshot semantics in a patch release.

### 3.4 ADR 0013 — no Pub/Sub canonical family before two guards exist

The current Canonical Model contains:

```text
Queue
Message
Schema
Service
```

A `Queue` has **competing-consumer semantics**. `SENDS` / `RECEIVES_FROM` therefore mean that a
message flows through one logical queue to one logical consumer service. The current model has no
`Topic`, `Subscription`, fan-out, or broadcast family.

The governing rule is:

> **Recognizing a telemetry signal is not the same as qualifying a canonical architecture fact.**

Before AIP can safely widen messaging recognition or introduce first-class Pub/Sub semantics, two
independent guards MUST exist:

1. **topic-vs-queue guard** — a topic/fan-out-shaped destination must not be converted into a
   canonical `Queue`;
2. **service-identity guard** — an ambiguous or placeholder runtime service name must not be minted
   into a canonical Service and then used to support a messaging relation.

`v0.4.1` implements these guards but does **not** add Topic or Subscription. Once the guards are
qualified, `v0.5.0` may introduce a new ADR that supersedes the prohibition and defines a generic
source-independent Pub/Sub model.

### 3.5 Queue-versus-Topic safety decision — concrete failure mechanism

The current queue resolver has historically had this effective shape:

```text
if destination matches a declared Queue:
    resolve declared Queue
else:
    mint OBSERVED_ONLY Queue
```

That means the resolver itself does not know whether an unmatched destination is actually a queue
or a fan-out topic.

The Quarkus real-system validation exposed a Kafka topic named `fights`. It currently produces zero
Queue facts only because its emitted operation attribute shape is not recognized by the current
runtime allowlist, so queue resolution is never reached for that span.

Therefore the present zero-fact behavior is **not evidence that the resolver is safe**. If operation
recognition were widened without a destination-kind guard, the topic could be minted as an
`OBSERVED_ONLY` Queue and could incorrectly produce a `SENDS` or `RECEIVES_FROM` fact.

`v0.4.1` SHALL close this gap directly: a recognized messaging signal may reach canonical Queue
resolution only when destination semantics are positively compatible with the competing-consumer
Queue model.

A topic-shaped or unresolved destination SHALL yield **no Queue fact**. This remains true even when
other telemetry attributes are syntactically valid.

### 3.6 Messaging-operation compatibility decision — second failure mechanism

The cross-system validation found a parallel issue on the Service side.

The historical service resolver can mint an `OBSERVED_ONLY` Service when no declared service
matches an observed `service.name`. This is valid for an explicit, stable runtime-only identity and
is necessary for legitimate `OBSERVED_ONLY` architecture.

It is unsafe, however, for generic or ambiguous names.

Apache Airflow provided a concrete example: several architecturally distinct roles can report the
generic placeholder identity:

```text
service.name: unknown_service
```

If broader messaging-operation recognition were to reach those spans without an identity guard,
AIP could merge distinct roles into one invented Service and attach messaging relations to it.

Therefore `v0.4.1` SHALL distinguish:

```text
explicit unambiguous runtime identity
    -> OBSERVED_ONLY Service may be valid

generic / placeholder / conflicting / ambiguous identity
    -> unresolved
    -> no canonical messaging relation
```

The guard MUST NOT equate "not declared" with "invalid". A legitimate explicit runtime-only service
must remain representable as `OBSERVED_ONLY`.

### 3.7 What remains deliberately deferred after these decisions

`v0.4.1` does **not** implement the features that these guards enable.

The following remain `v0.5.0` concerns:

```text
real Adapter Registry / SourceDescriptor
source-scoped reimport
generic Topic model
generic Subscription model
Pub/Sub relation semantics
Kubernetes discovery
wider messaging semantic-convention recognition
candidate gRPC/protobuf discovery
deeper cross-source runtime reconciliation
```

Kafka is not required to define the Pub/Sub Canonical Model. A future Kafka adapter, if ever added,
must populate an already-defined generic model rather than dictate it.

`v0.4.1` SHALL NOT reinterpret the historical `v0.3` validation findings. It implements the concrete
prerequisites those findings deferred.

---

## 4. Scope Budget

To prevent the patch release from becoming a discovery release, `v0.4.1` has a fixed scope budget:

| Area | `v0.4.1` limit |
|---|---|
| Public MCP tools | Exactly the existing 3 |
| MCP protocol/transport | No change from `v0.4.0` |
| `ArchitectureAnswer<T>` schema family | No breaking change; `schema_version` remains `0.4` |
| Canonical entity families | No additions |
| Canonical relation families | No additions |
| Messaging operation recognition | No widening required or permitted as part of the release goal |
| Discovery sources | No additions |
| Adapter SPI | No redesign or registry implementation |
| Kubernetes | Out of scope |
| Pub/Sub `Topic` / `Subscription` | Out of scope |
| Snapshot optimization | Benchmark only; no fingerprint-cache semantics change |
| Evidence retention/compaction | Out of scope |
| Graph writes through MCP | None |
| LLM dependency | None for correctness, qualification, or release gates |
| Real-system qualification | Reuse frozen Quarkus/Airflow evidence; no default live rerun |

Any feature that broadens what AIP discovers or represents SHALL move to `v0.5.0` or later unless it is strictly required to make one of the safety guarantees in this specification executable.

---

## 5. In Scope

`v0.4.1` SHALL deliver:

1. One named owner for the evidence-window matching semantics used by declared-vs-observed qualification.
2. An executable differential test proving the existing Cypher/analysis and `ArchitectureIntelligenceService` projection paths agree.
3. A topic-vs-queue safety guard in the runtime messaging path.
4. A service-identity safety guard in the runtime messaging path.
5. Regression coverage proving the two ADR 0013 prerequisites are real executable constraints.
6. Preservation of valid explicit `OBSERVED_ONLY` service identities; the identity guard SHALL reject ambiguous or placeholder identity, not undeclared identity merely because it is undeclared.
7. A committed, reproducible version of the snapshot/read-cost benchmark described by the post-`v0.4.0` architecture review.
8. Full regression of the `v0.4.0` Architecture Answers/MCP evaluation.
9. Frozen Quarkus/Airflow regression against the new messaging guards.
10. Patch-release qualification and published-artifact verification.

---

## 6. Explicit Non-Goals

The following are outside `v0.4.1`:

```text
Kubernetes discovery
ArchitectureSourceAdapter registry
SourceDescriptor / source-scoped reimport redesign
gRPC/protobuf adapter
Kafka Connect adapter
Kafka support
generic Pub/Sub support
Topic canonical entity
Subscription canonical entity
new messaging relation families
widening messaging.operation / messaging.operation.type recognition
new source formats
new MCP tools
generic graph query tools
MCP resources/prompts/tasks
graph writes through MCP
new architecture-analysis algorithms
transitive dependency exposure
snapshot fingerprint caching
incremental snapshot hashing
observed-evidence compaction or archival
architecture trajectories/history
Intent / Desired State / Transformation
GraphRAG
Backstage integration
production-scale performance qualification
v0.9 contract freeze
```

In particular, `v0.4.1` MUST NOT introduce a temporary or vendor-specific Topic representation that would later constrain the generic Pub/Sub model planned for `v0.5.0`.

---

## 7. Release Structure

`v0.4.1` is delivered in three increments:

| Iteration | Purpose |
|---|---|
| **I1 — Qualification Consistency** | Implement ADR 0010 and prove the two qualification paths agree |
| **I2 — Messaging Semantic Guards** | Implement the two ADR 0013 prerequisites and their regression suite |
| **I3 — Hardening Qualification and Release** | Commit the read-cost benchmark, run complete regressions, qualify and publish |

No iteration may introduce a new public architecture capability.

---

# I1 — Qualification Consistency

## 8. I1 Goal

I1 SHALL eliminate the risk that AIP's existing architecture surfaces silently disagree about declared-versus-observed qualification.

The implementation SHALL preserve the architectural separation between:

```text
analysis / REST / UI path
and
ArchitectureIntelligenceService / MCP path
```

The goal is semantic agreement, not layer convergence.

---

## 9. One Owner for Evidence-Window Semantics

The rule answering:

> Does this evidence count as observed for this `(environment, observation window)`?

SHALL have one named semantic owner.

Both existing implementation paths MUST reference that owner or a representation generated from the same owner rather than independently maintaining equivalent rules.

The implementation MAY preserve distinct Python and Cypher execution forms if required by the existing architecture, but the normative predicate and test fixtures MUST be shared.

The rule SHALL preserve existing meanings for:

- declared evidence;
- observed evidence;
- environment matching;
- lower and upper observation-window bounds;
- `CONFIRMED`;
- `OBSERVED_ONLY`;
- `NOT_OBSERVED_IN_WINDOW`;
- telemetry coverage classification.

`get_evidence` remains outside this qualification rule because it resolves already-identified evidence and does not independently classify an architecture claim.

---

## 10. Differential Qualification Test

A new integration test SHALL execute both qualification paths over the **same graph fixture**.

For every relation covered by the fixture, the two paths SHALL agree on:

```text
claim identity
qualification
coverage classification
evidence-window membership
environment membership
```

At minimum the fixture SHALL include:

1. declared-only relation;
2. observed-only relation;
3. declared + observed relation;
4. neither/irrelevant relation;
5. observed evidence in the wrong environment;
6. observed evidence before the requested window;
7. observed evidence after the requested window;
8. evidence exactly on an inclusive/exclusive boundary used by the current contract;
9. partial telemetry coverage;
10. no telemetry coverage.

A deliberate future difference between the two surfaces MUST be recorded by ADR and encoded as an explicit expected difference. Silent divergence is forbidden.

---

## 11. REST/MCP Window Asymmetry

The existing API asymmetry SHALL be documented, not removed:

- REST/analysis may use an implicit clock-relative default window.
- MCP architecture tools require an explicit observation context where the current `v0.4` contract requires one.

The same underlying relation MAY therefore receive a different qualification when the effective observation windows differ.

Documentation MUST make that reason inspectable. The implementation MUST NOT "fix" the difference by silently forcing the two interfaces to use identical request contracts.

---

## 12. I1 Exit Gate

I1 is complete when:

```text
[ ] the evidence-window rule has one named owner
[ ] both existing qualification paths use that rule or a derived representation of it
[ ] the differential integration test runs against real Neo4j
[ ] all shared-fixture qualifications agree
[ ] all shared-fixture coverage classifications agree
[ ] REST/MCP window-default differences are documented
[ ] existing public MCP schemas are unchanged
[ ] existing v0.4 Architecture Answers evaluation still passes
```

ADR 0010 SHOULD move from `Proposed` to `Accepted` when the implementation and differential test land.

---

# I2 — Messaging Semantic Guards

## 13. I2 Goal

I2 SHALL make ADR 0013's two prerequisites executable before `v0.5.0` introduces generic Pub/Sub semantics or widens runtime messaging discovery.

The two guards are independent and both are REQUIRED:

```text
messaging destination
        ↓
topic-vs-queue safety

runtime service identity
        ↓
service-identity safety
```

Passing only one guard is insufficient.

---

## 14. Topic-vs-Queue Safety Guard

The current Canonical Model defines `Queue` with competing-consumer semantics. A runtime destination MUST NOT become a canonical `Queue` merely because:

```text
a messaging span exists
a destination name exists
an operation attribute is recognized
a protocol/system name is present
the destination name resembles a queue
```

The runtime messaging path SHALL contain an explicit safety decision between telemetry recognition and canonical `Queue` creation.

Conceptually:

```text
recognized messaging signal
        ↓
destination-semantics guard
        ├── safely Queue-compatible
        │       ↓
        │   queue resolution may continue
        │
        ├── Pub/Sub / topic-shaped
        │       ↓
        │   no Queue fact
        │
        └── unresolved / conflicting
                ↓
            no Queue fact
```

The guard SHALL be based on deterministic evidence semantics, not on upstream project names or repository-specific special cases.

The exact classifier representation is an implementation choice. It MAY use declared-model evidence, semantic-convention attributes, protocol metadata, destination-kind metadata, or a combination, provided the rule is documented and regression-tested.

The guard MUST preserve the general rule:

> **Recognizing a telemetry signal is not the same as qualifying a canonical architecture fact.**

---

## 15. Topic-vs-Queue Required Behavior

The following SHALL hold:

1. A destination positively identified as Pub/Sub/topic-shaped MUST NOT create a canonical `Queue`.
2. A destination whose semantics conflict with the Queue model MUST NOT create `SENDS` or `RECEIVES_FROM`.
3. A destination whose semantics are unresolved MUST NOT be guessed into a newly supported messaging shape merely because a name is available.
4. An already-declared canonical Queue MAY continue to provide the semantic evidence required to resolve matching runtime observations.
5. Existing valid Queue scenarios MUST remain supported unless an independently evidenced false fact is being corrected.
6. The guard MUST be exercised in the production runtime-correlation path, not exist only as an unused helper.

`v0.4.1` MUST NOT create `Topic`, `Subscription`, or any placeholder equivalent when the guard refuses Queue qualification. Refusal is the correct result until `v0.5.0`.

---

## 16. Service-Identity Safety Guard

The runtime messaging path SHALL distinguish:

```text
undeclared but explicit identity
from
ambiguous / generic / placeholder identity
```

This distinction is required to preserve AIP's valid `OBSERVED_ONLY` semantics.

A service MUST NOT be rejected merely because it is absent from declared architecture. For example, an explicit, stable runtime identity may legitimately establish an `OBSERVED_ONLY` service.

However, a generic, placeholder, conflicting, or otherwise ambiguous identity MUST NOT be silently minted as a canonical Service for a messaging fact.

Conceptually:

```text
runtime service identity
        ↓
identity-safety guard
        ├── declared deterministic match
        │       → resolved Service
        │
        ├── explicit unambiguous observed identity
        │       → OBSERVED_ONLY Service allowed
        │
        └── ambiguous / generic / placeholder / conflicting
                → unresolved; no messaging relation
```

The implementation SHALL define a deterministic predicate for "identity is sufficiently explicit to support a canonical service fact".

The predicate MUST NOT depend on application-specific names such as `OrderService`, Quarkus, Airflow, or any one real-system fixture.

A known generic case such as `service.name: unknown_service` SHALL be covered by regression and SHALL not qualify four architecturally distinct roles into one merged service merely because they share that placeholder value.

---

## 17. Identity Preservation Requirements

The identity guard MUST preserve the following valid behavior:

- an explicit runtime-only service may remain `OBSERVED_ONLY`;
- a deterministic declared-service match remains declared/confirmed as appropriate;
- namespace/environment semantics already used for identity remain enforced;
- unresolved identity is reported/refused rather than guessed;
- no fuzzy name matching is introduced;
- no LLM is used for identity resolution.

The `v0.4.0` hero finding:

```text
OrderService -> LegacyPricingService = OBSERVED_ONLY
```

SHALL remain valid if its runtime identity satisfies the explicit, unambiguous identity rule. The service-identity guard is not permission to erase legitimate observed-only architecture.

---

## 18. Messaging Operation Recognition Is Frozen

`v0.4.1` SHALL NOT broaden messaging operation-attribute recognition as part of this release.

In particular, the release MUST NOT use the new guards as justification to simultaneously add support for additional legacy/current operation-attribute forms.

This sequencing is intentional:

```text
v0.4.1
guards first

v0.5.0
new Pub/Sub semantics and/or broader runtime recognition second
```

Any future widening SHALL cite ADR 0013 and SHALL include:

1. regression for each newly recognized attribute shape;
2. deterministic precedence when current/legacy/conflicting attributes coexist;
3. missing/unknown forms remaining unresolved;
4. topic-vs-queue guard regression;
5. service-identity guard regression.

---

## 19. I2 Required Regression Matrix

At minimum the new regression suite SHALL cover:

| Case | Expected result |
|---|---|
| declared Queue + known service + supported operation | existing Queue relation preserved |
| explicit observed-only service + Queue-compatible destination | `OBSERVED_ONLY` service relation may be produced |
| Pub/Sub/topic-shaped destination | zero Queue facts |
| Pub/Sub/topic-shaped destination + otherwise valid service | zero `SENDS`/`RECEIVES_FROM` Queue facts |
| unresolved/conflicting destination semantics | no guessed Queue |
| generic placeholder service identity | no canonical service minted for messaging fact |
| ambiguous service match | unresolved; no guessed service |
| explicit undeclared service identity | may remain `OBSERVED_ONLY` |
| wrong environment/namespace identity | no cross-environment merge |
| both guards fail | neither Queue nor Service relation is invented |

Regression names and fixture structure SHOULD make each semantic guarantee visible without requiring knowledge of the implementation.

---

## 20. Frozen Real-System Regression

I2 SHALL reuse the frozen real-system evidence from `v0.3`/`v0.4`.

### Quarkus Super Heroes

The historical Kafka `fights` topic remains unsupported in `v0.4.1`.

Expected result:

```text
canonical Topic facts = 0
canonical Queue facts for fights = 0
SENDS/RECEIVES_FROM facts derived from fights = 0
```

This is a safety regression, not Kafka support.

### Apache Airflow

The historical generic/ambiguous runtime service identity remains unable to create a false merged messaging service relation.

Expected result:

```text
ambiguous placeholder identity
        ↓
unresolved
        ↓
no invented messaging relation
```

No live Quarkus or Airflow rerun is required by default. Frozen evidence is the release baseline.

---

## 21. I2 Exit Gate

I2 is complete when:

```text
[ ] topic-vs-queue guard is in the production runtime messaging path
[ ] service-identity guard is in the production runtime messaging path
[ ] topic-shaped evidence cannot become Queue
[ ] ambiguous/generic service identity cannot become a qualified messaging Service
[ ] explicit runtime-only service identity can still produce valid OBSERVED_ONLY architecture
[ ] current messaging operation-attribute allowlist is not widened
[ ] no Topic/Subscription canonical entities exist
[ ] no new relation family exists
[ ] Quarkus frozen topic case remains zero-fact/unsupported
[ ] Airflow frozen ambiguous-identity case remains safely unresolved
[ ] all existing supported Queue regressions pass
```

ADR 0013 remains historically valid during `v0.4.1`: the release satisfies its two prerequisites but does not yet introduce the Pub/Sub family whose absence it records.

A future `v0.5.0` ADR MAY supersede ADR 0013 only after these two guards are present and qualified.

---

# I3 — Hardening Qualification and Release

## 22. I3 Goal

I3 SHALL prove that the semantic hardening is compatible with the shipped `v0.4.0` public capability, and SHALL turn the architecture review's ad-hoc scaling measurement into a reproducible repository artifact without changing snapshot semantics in this patch release.

---

## 23. Committed Snapshot/Read-Cost Benchmark

The post-`v0.4.0` architecture review measured whole-graph snapshot/read cost using synthetic graph growth. The measurement script was deliberately not committed.

`v0.4.1` SHALL add a committed benchmark that can reproduce the same **shape of cost**.

The benchmark SHALL:

1. seed deterministic synthetic architecture/evidence data into a disposable graph;
2. use evidence shaped consistently with AIP's observed-evidence model;
3. measure at least:
   - snapshot-state/fingerprint time;
   - one representative Architecture Intelligence/MCP dependency call;
4. record graph size and evidence-node count;
5. record runtime/environment metadata needed to interpret the result;
6. clean up or provide a documented disposable-stack workflow;
7. produce a machine-readable result artifact in addition to human-readable output;
8. avoid becoming a default unit-test/CI latency burden unless a later decision adds such a gate.

The benchmark SHOULD include points comparable in order of magnitude to:

```text
~10^2 nodes
~5 x 10^3 nodes
~2 x 10^4 nodes
~1 x 10^5 nodes
```

Absolute timing equality with the architecture review is NOT a release requirement because hardware and container environments differ.

The benchmark SHALL demonstrate whether read cost remains a function of total graph size rather than the size of the requested answer.

---

## 24. ADR 0011 Disposition

`v0.4.1` SHALL NOT implement the ADR 0011 fingerprint cache or otherwise change the public semantics of `snapshot_id`.

The benchmark MAY satisfy ADR 0011's requirement for a committed reproducible measurement and MAY therefore allow the repository owner to move ADR 0011 from `Proposed` to `Accepted` as a settled future decision.

Implementation of fingerprint caching, request-scoped lookup optimization, or related scaling work remains for a later release when broader discovery provides the qualifying landscape.

No out-of-band-write visibility semantics SHALL change in `v0.4.1`.

---

## 25. ADR 0012 Disposition

ADR 0012 remains outside `v0.4.1`.

The release SHALL NOT:

```text
compact observed evidence
delete old evidence
cap evidence_refs
change retention defaults
introduce archival storage
change old-window qualification semantics
```

Retention thresholds remain a separate semantic decision.

---

## 26. Public Contract Compatibility

The following `v0.4.0` public properties SHALL remain true:

- exactly three read-only MCP tools:
  - `get_service_dependencies`
  - `get_architecture_drift`
  - `get_evidence`
- no graph writes through MCP;
- no LLM API key required;
- existing `ArchitectureAnswer<T>` envelope family;
- `schema_version` remains `0.4`;
- snapshot-bound answers;
- explicit observation-context binding where required;
- evidence/provenance drill-down;
- conservative qualification;
- closed tool input/output schemas.

Normal producer metadata SHALL report `0.4.1` and the exact build revision.

No fourth tool may be introduced.

---

## 27. Existing Evaluation Regression

The complete `v0.4.0` Architecture Answers evaluation SHALL pass against the `v0.4.1` candidate.

The existing 23 deterministic scenarios SHALL remain valid unless a scenario directly encoded a behavior now proven unsafe by the new guards.

If an existing expected result must change:

1. the change MUST be justified by an explicit semantic finding in this specification or its cited ADR/validation record;
2. the old behavior MUST be shown to permit a false canonical fact;
3. the changed expectation MUST be independently authored;
4. the release record MUST identify the exact scenario and rationale.

A patch release MUST NOT rewrite unrelated expected results.

---

## 28. Determinism

All newly added semantic tests SHALL be deterministic.

Where evaluation artifacts contain ordering-sensitive collections, timestamps, identifiers, or generated evidence, the comparison SHALL canonicalize or freeze them according to the same principles used by `v0.4.0`.

Two clean-state qualification runs SHALL produce semantically identical results.

The committed performance benchmark is exempt from timing equality, but its seeded graph topology and machine-readable structural result fields MUST be deterministic.

---

## 29. Security and Write Boundary

No `v0.4.1` item may weaken the read-only architecture-tool boundary.

The release SHALL preserve:

```text
MCP tools -> ArchitectureIntelligenceService -> read repositories
```

for agent-facing reads.

The messaging guards operate on ingestion/runtime correlation and are not callable by agents as write-capable tools.

No LLM or agent may:

- classify destination semantics;
- resolve canonical service identity;
- override a safety refusal;
- write a Queue or Service;
- change evidence qualification.

Those decisions remain deterministic AIP logic.

---

## 30. Release Qualification

The `v0.4.1` candidate SHALL be qualified from an exact immutable commit.

At minimum qualification SHALL include:

1. unit and integration test suite;
2. ADR 0010 differential qualification test;
3. topic-vs-queue guard regression suite;
4. service-identity guard regression suite;
5. frozen Quarkus/Airflow messaging regressions;
6. existing Architecture Answers evaluation;
7. existing independent MCP golden path;
8. unchanged three-tool discovery;
9. committed read-cost benchmark smoke/reproducibility run;
10. lint/static checks;
11. CodeQL/security checks used by the existing release process;
12. dependency audit;
13. clean-checkout execution;
14. container/GHCR candidate verification where applicable.

Release blockers SHALL be explicit. A known limitation is not a blocker merely because it remains unsupported, provided the release does not claim support for it.

---

## 31. Hero Demo Regression

`v0.4.1` does not require a new hero demo.

The existing `v0.4.0` hero demo SHALL remain semantically valid:

```text
OrderService -> LegacyPricingService = OBSERVED_ONLY
```

with evidence drill-down against the same architecture snapshot semantics.

Expected changes are limited to producer/build metadata and any graph-state fingerprint changes caused by deterministic ingestion differences that are explicitly justified by this release.

The release SHALL NOT replace the hero finding with a Pub/Sub example. Pub/Sub is `v0.5.0`.

---

## 32. Release Documentation

Before final publication, the repository SHALL contain:

```text
docs/specifications/0.4.1/README.md
docs/specifications/0.4.1/specification.md
release qualification record for v0.4.1
post-release verification record
CHANGELOG.md update
ROADMAP.md update
ADR index/status updates where justified
```

`ROADMAP.md` SHOULD show:

```text
v0.4.0  Trusted Architecture Context for Agents — shipped
v0.4.1  Semantic Hardening for Broader Discovery — shipped
v0.5.0  Broader Architecture Discovery — planned
```

The `v0.5.0` section SHOULD state that generic Pub/Sub work may proceed only on the qualified `v0.4.1` messaging guards.

---

## 33. Required README Summary for `docs/specifications/0.4.1/`

The specification directory README SHOULD summarize the release as:

> `v0.4.1` hardens AIP's existing architecture-intelligence semantics before broader discovery. It makes declared-vs-observed qualification cross-checked across both existing execution paths, adds deterministic topic-vs-queue and service-identity safety guards to runtime messaging correlation, and commits a reproducible read-cost benchmark. It deliberately adds no new Canonical Model family, discovery source, or MCP tool.

---

## 34. Definition of Done

`v0.4.1` is complete only when all of the following are true:

### Qualification consistency

```text
[ ] one named evidence-window semantic rule exists
[ ] Cypher/analysis and Architecture Intelligence projection paths are cross-checked
[ ] differential fixture covers declared-only / observed-only / both / mismatch cases
[ ] qualification differences = 0 for equivalent effective observation contexts
[ ] coverage-classification differences = 0
```

### Messaging safety

```text
[ ] topic-vs-queue guard exists in the production messaging path
[ ] Pub/Sub/topic-shaped evidence cannot mint Queue
[ ] Pub/Sub/topic-shaped evidence cannot produce Queue SENDS/RECEIVES_FROM
[ ] service-identity guard exists in the production messaging path
[ ] generic/placeholder identity cannot mint a qualified messaging Service
[ ] ambiguous identity remains unresolved
[ ] explicit undeclared service identity can still remain OBSERVED_ONLY
[ ] no fuzzy/LLM identity inference is introduced
```

### Scope preservation

```text
[ ] canonical Topic does not exist
[ ] canonical Subscription does not exist
[ ] no new canonical relation family exists
[ ] messaging operation recognition is not widened
[ ] Kubernetes is not added
[ ] adapter registry/source-descriptor redesign is not added
[ ] exactly three MCP tools remain
[ ] MCP write paths remain zero
```

### Qualification and release

```text
[ ] existing 23 Architecture Answers scenarios pass
[ ] new semantic guard scenarios pass
[ ] frozen Quarkus topic regression passes
[ ] frozen Airflow ambiguous-identity regression passes
[ ] existing MCP independent-client golden path passes
[ ] existing hero demo remains semantically valid
[ ] committed read-cost benchmark reproduces a deterministic graph and machine-readable output
[ ] full CI/security/dependency qualification passes
[ ] clean-checkout candidate qualification passes
[ ] release blockers = 0
[ ] exact candidate is tagged and published
[ ] published artifact is independently re-verified
```

---

## 35. Explicit Deferred Work for `v0.5.0`

The following work is intentionally enabled by, but not included in, `v0.4.1`.

### Discovery seam

Implement ADR 0009:

```text
SourceDescriptor
    ↓
AdapterRegistry
    ↓
ArchitectureSourceAdapter
    ↓
Canonical Model
```

including source-scoped reimport and many-services-per-source semantics.

### Generic Pub/Sub model

Only after the `v0.4.1` messaging guards are qualified, `v0.5.0` MAY introduce source-independent:

```text
Topic
Subscription

Publisher Service
      |
   PUBLISHES
      v
    Topic
      |
      +-- HAS_SUBSCRIPTION --> Subscription --> Consumer Service
```

Exact entity/relation names are NOT decided by this specification.

Kafka is not required for that model and MUST NOT define its canonical semantics.

### Kubernetes discovery

Kubernetes remains a `v0.5.0` declared-evidence source candidate and SHALL map through the real adapter seam rather than adding another hard-coded pipeline branch.

### Deeper runtime discovery

`v0.5.0` MAY widen messaging/runtime recognition only after proving deterministic attribute precedence, destination semantics, and identity safety against the guards delivered here.

### Scaling implementation

ADR 0011 implementation and ADR 0012 retention/compaction remain separate from this patch release and SHALL be qualified against real broader-discovery landscapes rather than folded into `v0.4.1` without evidence.

---

## 36. Release Narrative

The intended public release narrative is deliberately modest:

> **AIP v0.4.1 hardens the semantics behind Trusted Architecture Context for Agents.**
>
> Before broadening discovery, AIP now cross-checks declared-vs-observed qualification across its existing execution paths and guards runtime messaging against two unsafe assumptions: that every recognized destination is a Queue, and that every observed service name is a trustworthy architecture identity.
>
> The public agent surface remains unchanged: the same three read-only MCP tools, with no new architecture domain and no LLM in the correctness path.

The release SHOULD NOT be marketed as Pub/Sub support.

Its value is that `v0.5.0` can add Pub/Sub and broader discovery **after the semantic prerequisites are already executable and qualified**.

---

## 37. Sequencing Principle

```text
v0.4.0
Trusted Architecture Context for Agents
        |
        v
v0.4.1
Qualification consistency
+ messaging semantic guards
+ reproducible scaling evidence
        |
        v
v0.5.0
Broader Architecture Discovery
+ generic Pub/Sub
+ Kubernetes
+ deeper runtime reconciliation
        |
        v
v0.9
Contract Freeze / Production Qualification
        |
        v
v1.0
Stable Architecture Intelligence Platform
```

`v0.4.1` succeeds by making `v0.5.0` safer to build, not by borrowing `v0.5.0` features early.
