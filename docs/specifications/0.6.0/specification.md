# AIP v0.6.0 Release Specification — Locality-Aware Current State

**Status:** Accepted parent release specification — normative v0.6.0 scope and acceptance contract; implementation-specific decisions in §33 SHALL be frozen in reviewed increment specifications before the corresponding work. Acceptance of this document does not claim that v0.6.0 is implemented, qualified or released.  
**Target release:** `v0.6.0`  
**Release theme:** Locality-Aware Current State  
**Entry baseline:** Published and post-release-verified `v0.5.1` (`5719738091baa701d9867726fc89c93fa80bea46`); v0.5.0 provides the underlying discovery and qualification semantics  
**Primary outcome:** AIP can establish which supported architectural relationships hold in explicitly evidenced localities and observation contexts, and deterministically project and compare these local assessments without turning local knowledge into a universal architecture claim.  
**Governing inputs:** [Product Doctrine and Strategic Direction](../../product-doctrine-and-strategic-direction.md), [ROADMAP.md](../../../ROADMAP.md), [v0.5.0 parent specification](../0.5.0/specification.md), [v0.5.1 specification](../0.5.1/specification.md).  
**Sources consulted during specification development:** ROADMAP `5082ec45`; Product Doctrine `9c03d53e`; v0.5.0 specification `b4c0163e`; v0.5.1 specification `815fcf0a`. The review iterations also inspected the current v0.5 observed-evidence/runtime-identity, snapshot fingerprint and Path C capture-matching implementations, the frozen golden-path expected file, and proposed [ADR 0012](../../adr/0012-observed-evidence-retention.md). These are source-input identities, not an implementation baseline or release candidate.

---

## 1. Release Promise

`v0.5.0` established broader declared, infrastructure, and observed architecture and bounded Service–Workload identity reconciliation. `v0.5.1` demonstrated the released capabilities through the Quarkus Super Heroes developer workflow without adding semantics. Neither release establishes locality-qualified dependencies or a deterministic projection of local assessments into a broader Current-State view.

`v0.6.0` SHALL make a materially new class of architecture question safely answerable:

> **Where is this dependency established?**  
> **Does this relation differ by supported locality?**

The release SHALL prove:

> **Given a stable Current-State snapshot, applicable evidence, and an explicit observation/locality scope, AIP establishes bounded qualified local evidence assessments and deterministically projects them into a Current-State answer which identifies the included and excluded localities, evidence lineage, qualification, coverage, and limits. An agent can inspect where a relationship is supported without inferring that it holds, or fails to hold, anywhere else.**

The governing semantic path is:

```text
Current-State Evidence
       +
Explicit, evidence-supported locality / observation context
       ↓
Applicable Evidence + Identity Reconciliation
       ↓
Qualified Local Evidence Assessments
       ↓
Deterministic, bounded Current-State Projection
       ↓
Evidence-Qualified Current State
```

The non-negotiable invariants are:

```text
local assessment != universal/global fact
locality != connectivity; WHERE != HOW
co-location != interaction
not observed here != does not happen here
unknown locality != every locality
Service != Kubernetes Service != Workload != Pod
Service version != Service identity
source/capture location != automatically the subject's runtime location
deployment association != location of every runtime call
path through qualified edges != qualified causal end-to-end flow
observed / declared Current State != explicit Architecture Intent
consumer projection != new source of Architecture Knowledge
```

AIP remains advisory and read-only on its public Architecture Intelligence surface. Agents, LLMs, demos, and external context tools never establish or strengthen canonical architectural truth.

## 2. Normative Language

**MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative. An example, conceptual type, suggested endpoint, or illustrative field name is not a frozen public wire contract unless explicitly stated as such. The reviewed increment specification and versioned schema SHALL freeze concrete names before the corresponding implementation/fixture authorship; they may not weaken this accepted parent contract by selecting convenient defaults.

Independent expected results, not output copied from AIP or an agent interpretation, constitute qualification evidence. Tests of implementation alone do not settle ambiguous semantics.

## 3. Entry Conditions and Preserved Baseline

The final candidate SHALL derive from the published `v0.5.1` baseline and retain its supported v0.5.0 Architecture Knowledge semantics:

- one Canonical Model mapping target; source adapters do not write directly to persistence;
- deterministic source inventory, revision, authoritative-removal, atomic import, and replay rules;
- distinct declared, observed, and infrastructure-derived evidence modes;
- bounded identity guards and conflicts, including the established `DEPLOYED_AS` contract;
- one declared-vs-observed qualification owner; non-observation and coverage retain their existing meanings;
- snapshot/revision fencing, evidence resolution, sanitized provenance, deterministic answers, and explicit limitations;
- `ArchitectureIntelligenceService` as the sole semantic owner for public Architecture Knowledge;
- REST and standard negotiated MCP as the supported public adapters, with transport-independent evaluation against the service;
- existing dependency/drift/evidence and Pub/Sub semantics; neither Queue/Topic/Subscription nor Service/Workload distinctions may collapse;
- read-only public Architecture Intelligence and a deterministic, no-LLM-required execution path;
- the released Quarkus demonstration and minimal demonstration remain valid; existing unscoped queries keep their documented v0.5 meanings unless a versioned, reviewed compatibility decision explicitly changes them.

**Important baseline limitation.** A v0.5.1 Service-level `DEPLOYED_AS` resolution is not enough by itself to attribute an individual observed HTTP or messaging interaction to that Workload. The Quarkus demo's frozen 7-second replay and disclosed operator-authored messaging overlay must not be presented as independently establishing two runtime localities, observed Kafka behavior, or a complete application topology. v0.6 qualification needs its own independently authored locality cases.

**Required ingestion change.** Today `app/canonical/ids.py:observed_evidence_id` keys observed relationship evidence by environment, UTC day and subject/relation/object, without caller Pod UID. Separately, `app/telemetry/runtime_identity.py` records Service/Pod observations which do not themselves establish an interaction. Two Workloads of one Service therefore collapse into the same persisted `CALLS` bucket. Joining that bucket to a Service-level Pod observation would guess the event's origin. The positive v0.6 capability **requires per-interaction caller attribution during ingestion and versioned scoped observed evidence**, not a read-side join. Historical v1 aggregates cannot be silently reclassified as workload-local facts.

## 4. Fixed Scope Budget

### 4.1 In scope

`v0.6.0` SHALL deliver:

1. An explicit **locality/context applicability contract**, including ingestion-time caller attribution, versioned scoped evidence/migration, minimum supported dimensions and refusal rules (§§6–8).
2. A first-class internal **Qualified Local Evidence Assessment** semantic unit, independent of Intent (§§10–12).
3. One bounded, deterministic **Current-State projection** over applicable local assessments, with explicit included/excluded/unknown scope, coverage, qualification, and limitations (§§13–16).
4. A **question-specific locality answer**, with mandatory bounded enumeration of evidenced candidate localities and optional selected-locality comparison (§§14, 17–19).
5. REST and negotiated-MCP exposure through the single Architecture Intelligence semantic owner, versioned contracts, and same-snapshot evidence drill-down (§18).
6. Independent deterministic positive/negative qualification, v0.5 regression, two real-system boundary checks, a realistic developer walkthrough, and an explicit product-value/pilot disposition (§§20–25).
7. Exact-candidate release qualification, owner-authorized publication if granted, and post-publication artifact verification (§§26–28).

The minimum positive question slice SHALL demonstrate one application dependency relation (`CALLS`) scoped to the **observed caller's independently evidenced runtime locality** and differentiated across two eligible localities. It SHALL also preserve existing `DEPLOYED_AS` placement evidence as placement, not as inferred interaction. Other existing relation kinds may gain locality-aware claims **only** after their evidence, scope and qualification rules are separately specified and tested. They otherwise remain answerable through **unchanged v0.5 requests and responses**; unsupported locality qualification is disclosed in the **new locality answer**, not inserted as a new limitation into an existing v0.5 answer (§16).

The minimum locality dimensions SHALL include the existing explicit **environment and observation window** and, for a positive differentiated case, **evidenced cluster identity and namespace/workload scope** through ingestion-time caller Pod attribution and the admitted v0.5 Kubernetes/OTel identity chain. This is an **explicit narrowing of the ROADMAP's candidate dimensions and relation coverage for the first v0.6 slice**: region, tenant, service-version-specific locality qualification, positive workload-local declared-only `CALLS`, and messaging locality are deferred unless separately specified and qualified. A namespace is not a region or tenant; service version is not a distinct Service identity. Record the narrowed surface in the support matrix and release notes. The ROADMAP's “when and only when evidence supports the dimension” rule remains authoritative.

### 4.2 Explicitly out of scope

```text
new discovery-source family or live Kubernetes admission
new general-purpose graph/Cypher access or arbitrary graph-neighbourhood API
service-mesh or network-topology discovery
service-to-service communication inferred from Kubernetes placement
causal end-to-end runtime flow or inferred system-level business outcome
fully closed-world absence claims or global dependency completeness
health, readiness, availability or SLO conclusions
explicit Architecture Intent / promises / authority evaluation (v0.7)
Current ↔ Intent assessment or policy/compliance judgment (v0.8)
historical snapshot retention and architecture trajectories
sidecar, DaemonSet, OTel extension or distributed Local Architecture Assessor
migration planning, architecture mutation, approval workflows or remediation
LLM/agent-derived locality, evidence, identity, or qualification
SSTorytime, GT, A2A, GraphRAG or a new agent orchestration framework in the core
```

v0.6 adds a semantic locality capability, not a new placement source or deployment architecture. A future distributed local assessor remains a post-v1.0 hypothesis. New source families such as gRPC/protobuf or Kafka Connect require separate authorization and do not enter v0.6 through the existing adapter seam.

## 5. Increment Contract and Dependency Order

| Increment | Title | Required outcome |
|---|---|---|
| I1 | Locality and Evidence Applicability Contract | Supported scope vocabulary, evidence attribution and refusal semantics are frozen and executable. |
| I2 | Scoped Evidence Implementation and Qualified Local Evidence Assessment | AIP implements per-interaction scoped evidence ingestion/persistence and independently establishes local Current-State assertions without duplicating or weakening v0.5 qualification. |
| I3 | Bounded Current-State Projection and Public Answers | Users/agents ask the new question deterministically through service, REST and negotiated MCP, with same-snapshot evidence drill-down. |
| I4 | Deterministic Semantic Qualification | Independent positive/negative locality truth tables, cross-context reconciliation, compatibility and repeatability qualify the increment capabilities. |
| I5 | Real-System Qualification and Product Demonstration | Quarkus/Airflow baseline preservation; externally authored locality evidence where real upstream lacks it; useful task-oriented demonstration and bounded pilot disposition. |
| I6 | Release Candidate, Publication and Verification | One exact candidate reaches a recorded `RELEASE_READY_NOT_PUBLISHED` or verified published outcome. |

```text
I1 → I2 → I3 → I4 → I5 → I6
```

I1–I3 MAY be sliced internally, but positive acceptance must be end-to-end and public-question oriented, not merely schema or storage completion. A material semantic ambiguity SHALL stop the affected implementation until resolved by reviewed specification amendment. The parent specification controls the release scope; increment specs may narrow it or freeze deferred details, not silently expand it.

---

# Part I — Locality and Evidence Applicability

## 6. Locality as Supported Applicability, Not a Universal Coordinate

A *locality* is an explicit, bounded scope under which a Current-State assertion may be established. It need not equal one Service, Workload, team, namespace, or graph node; an assessment may span several components where one evidence/rule combination supports that scope. The locality of an **observer/caller**, a **target**, a **source artifact**, and a **claim** are different propositions and SHALL not be silently substituted.

The I1 contract SHALL distinguish:

```text
requested scope             what the caller asked about
source/capture scope        what the source is known to cover
subject runtime scope       where the caller/subject event is evidenced
target runtime scope        where the target event/entity is independently evidenced, if at all
claim applicability scope   where that precise assertion is supported
projection selection scope  which supported assessments were included
```

Each scope dimension SHALL be supported by a named admissible evidence/mapping path and a rule version. An omitted, unavailable, contradictory, stale, or unsupported dimension is **unknown/unresolved/unsupported as appropriate**, never wildcard `*`, never inferred from a similar display name, and never a reason to expand the claim to all localities. Exact wire vocabulary for these cases is an I1 freeze decision; their distinct meanings are mandatory now.

### 6.1 Admitted minimum scope

- `environment` and explicit `observation_window`: reuse the existing runtime observation contract and inclusive window-applicability rule where applicable; preserve actual source timestamps and capture identity.
- `cluster identity`: a configured and/or captured identity accepted by the existing source/identity rules; a human-friendly cluster name is not a surrogate for a UID.
- `namespace` and `workload`: only through the Pod UID and a time-compatible captured Kubernetes owner chain available in the **selected, revision-fenced query snapshot**; the retained observed interaction identity is not by itself a resolved Workload. Workload kinds and bounded references remain those admitted in v0.5. A capture's `capturedAt` is evidence of that capture, not continuous proof of Pod presence.
- `service.version`: optional discriminant only if the specific runtime or declared evidence establishes it and compatible identity/rule logic is defined. A version is not a distinct AIP Service by default.
- Other dimensions (region/tenant etc.): explicit `UNSUPPORTED` or `UNRESOLVED` for a request unless I1 records a supported source, mapping, applicability rule and negative tests. A namespace is not a region or tenant.

The parent SHALL fix the minimum semantic capability; I1 SHALL freeze the actual context type, dimension keys, supported combinations and versioned schema before independent fixtures are written. The first positive scoped-observation contract is **UTC-day-granular** (§7). Existing v0.5 daily buckets retain `first_seen` and `last_seen`, not all event times: the existing inclusive `last_seen` matching rule cannot establish complete sub-day activity or inactivity.

## 7. Evidence Attribution and Temporal Compatibility

A positive local claim requires **directly attributable applicable evidence**, not simply a successful relationship query plus a separate Service placement. For the minimum local HTTP `CALLS` case, the observed caller's OTel Resource and the v0.5 Pod-UID → Pod → owner-chain/Workload linkage (including compatible environment/time/captured resource identity) SHALL justify the claimed caller locality. A configured or explicit Service–Workload binding by itself does not assign an individual HTTP event to that Workload. Target locality SHALL be left unknown unless separately evidenced; a caller in namespace A can call a target in namespace B.

**Ingestion and scoped evidence identity are part of v0.6.** For the minimum `CALLS` slice, carry the actual **CLIENT span's** bounded caller Resource/Pod-UID identity through correlation (including cross-batch cases) into the resolved fact **before aggregation**. Preserve the existing SERVER-sourced route/method and v0.5 correlation/qualification guards. Do not store raw spans or arbitrary resource attributes. Persist separately identifiable scoped observed evidence with a deterministic **v2 key** distinguishing environment, UTC day, canonical subject/relation/object and exact caller Pod identity (including accepted cluster identity as needed to avoid collisions), under an explicit identity/canonicalization version. I1 freezes exact key, normalization and ambiguity/conflict treatment. The same-Service runtime identity observation is not a substitute for this per-event attribution. Missing/incompatible caller identity leaves an unscoped v1 observation but mints no workload-local claim.

**Migration and compatibility:** preserve the existing v1 observed-evidence path and v0.5 unscoped semantics. New ingestions SHALL retain the original v1 contribution and, when the admitted per-interaction identity is present, also write a **separately isolated v2** scoped contribution; v2 MUST NOT be counted again in v0.5 relation qualification, coverage, counts or public evidence arrays. Freeze storage, evidence reachability, scoped snapshot fingerprint, source/normalization lineage, idempotent replay and coexistence before implementation. Existing historical v1 aggregates cannot be backfilled to positive Pod locality without independently replayable original per-interaction evidence. A versioned transition/migration report SHALL distinguish legacy unscoped evidence from scoped evidence; raw-trace restoration and historical trajectories are not required.

**Pod churn and capture-selection rule (frozen for this release):** v2 preserves the actual caller Pod UID **at ingestion**; attribution from that Pod to a Workload is **resolved at query time against the time-compatible Pod/owner-chain capture present in the single selected canonical snapshot**, using v0.5 Path C's environment, persisted observation timestamp and real `capturedAt` guards, plus I1's scoped per-event identity checks. Do not bind the call to a later replacement Pod, a same-named Workload, a current Service-level `DEPLOYED_AS`, or an inferred past capture. If a subsequent authoritative capture no longer contains the observed Pod/valid owner chain, its scoped evidence remains attributable to its Pod UID but its **Workload locality becomes `UNRESOLVED`** in the new query, not absent, deleted, or reassigned. The answer identifies the capture revision/time and resolution limitation. This contract does not provide historical snapshots or permit rebuilding an absent capture from memory. Pod replacement, promotion and rollback can change the currently resolvable locality without erasing the original observed event; the snapshot/derivation identity must reflect the change.

**Temporal support:** the minimum positive scoped `CALLS` contract SHALL support only complete UTC-calendar-day observation windows, with exact inclusive boundary canonicalization frozen in I1. A finer request receives a machine-visible unsupported-resolution disposition, not a negative architecture assertion. Evidence supports locality at the actual accepted event/capture context, never continuous presence throughout a bucket. Existing v0.5 `last_seen` window semantics remain unchanged. Later finer granularity needs separately reviewed timestamp-preserving evidence/matching rules. Proposed ADR 0012 is not implemented merely by adding locality.

The assessment SHALL preserve:

```text
source instance / artifact revision / capture identity
source evidence mode (DECLARED / OBSERVED / INFRASTRUCTURE_DERIVED, etc.)
applicable raw or normalized evidence references (bounded and sanitized)
identity reconciliation and mapping path / rule version
observation environment and window; actual relevant timestamps
supported locality dimensions and any unsupported/missing dimensions
qualification and limitations
```

An offline Kubernetes manifest is declared infrastructure input, not proof that a live resource currently exists. A captured resource is evidence of the capture, not a timeless claim about cluster state. A source-level service declaration SHALL NOT be silently made region-specific merely because a Service has a Workload in a region. Such a declaration may contribute as separately labelled source/Service-level evidence to qualification of an independently observed local call under §11; it never thereby becomes a Workload-authored or Workload-exclusive declaration. Partial or incompatible time context cannot be repaired by nearest-window matching. `NOT_OBSERVED_IN_WINDOW` retains v0.5 coverage semantics and never means verified local absence.

## 8. Source Scope, Identity, and Conflict Rules

I1 SHALL freeze an evidence applicability table per admitted claim kind and dimension before implementation, including at least:

| Evidence or existing fact | What v0.6 may support | What it cannot support alone |
|---|---|---|
| OpenAPI declaration | Service/operation declaration under the source's evidenced scope | Operation observed in a particular runtime Workload |
| Ingestion-time attributable OTel HTTP CLIENT observation with v2 scoped evidence | Observed direct `CALLS` in that caller's supported runtime scope | Target co-location, causal multi-hop path or source-independent global dependency |
| Kubernetes Workload/Pod capture and owner chain | Captured infrastructure identity and bounded placement scope | An application `CALLS`, `SENDS`, or `PUBLISHES_TO` relationship |
| Existing `DEPLOYED_AS` resolution | Supported Service–Workload association with its exact evidence mode | Attribution of all Service interactions to that Workload |
| Configured mapping | The exact mapped identity association and its versioned provenance | Runtime behavior or live placement beyond the source's own evidence |
| Operator-authored AsyncAPI overlay | Attributable declaration evidence for the admitted messaging claim | Independent upstream or runtime confirmation, or implied Subscription identity |

Where evidence for two scopes differs, assess them separately. A discrepancy in compatible identity/evidence within one scope must be reconciled or reported as conflict; it must not be hidden through specificity ranking, “latest wins”, a global source-trust order, or merging unlike localities. A broader view may describe both different established local states without calling them a contradiction.

A missing scoped source, ambiguous Pod owner, unsupported runtime semantic convention, name-only Workload match, or unproven intersection of contexts SHALL not mint a positive locality-qualified dependency claim. Existing import/inventory authority is preserved; absence from an incomplete discovery scope cannot authorize removal or produce a negative locality conclusion.

## 9. I1 Exit Gates

I1 is complete when:

1. an exact, versioned scope/applicability contract states which locality dimensions, evidence paths and combinations are admitted;
2. positive and negative examples discriminate observer/caller, target, source/capture and claim applicability;
3. scope extraction never broadens a v0.5 refusal or changes a Service identity by name;
4. missing, conflicting, unsupported and temporally incompatible locality evidence have deterministic machine-visible dispositions;
5. the distinction between observation window and future Intent effective interval is explicit in types and documentation;
6. its independently authored examples include a runtime-identity attribution case and a name/co-location-only rejection;
7. the v1/v2 observed-evidence identity, migration/coexistence/replay and public reachability rules, per-event cross-batch attribution, UTC-day window support and ADR 0012 cost/retention implications are frozen and testable;
8. query-time, snapshot-pinned capture selection and Pod-churn behavior are frozen, and I1 supplies an executable plan for the controlled live capture harness before I2 begins (including Pod UID, CLIENT `k8s.cluster.uid`, capture `clusterUid`, `capturedAt`, ownership and replay pins).

---

# Part II — Qualified Local Evidence Assessment

## 10. Internal Assessment Contract

I2 SHALL implement a first-class semantic unit equivalent to the Product Doctrine's **Qualified Local Evidence Assessment**, independent of storage topology:

```text
QualifiedLocalEvidenceAssessment(
  subject,
  assertion,
  context / supported locality scope,
  observation_window,
  applicable_current_state_evidence,
  source / mapping / identity / qualification rule versions,
  qualification,
  provenance / derivation lineage,
  limitations
)
```

**I1 freezes the v2 scoped-evidence contract in §7; I2 SHALL implement the corresponding per-interaction ingestion, isolated persistence and read-side consumption.** Existing v1 fact buckets and independent `RuntimeIdentityObservation` records cannot establish a local interaction through a read-side Service/Pod join. Once v2 evidence exists, the *assessment* MAY be a deterministic read-side projection over it. No materialized `LOCAL_ASSESSMENT` node/edge is mandated. Scoped evidence storage needs explicit ownership, replay, expiration, snapshot and reachability rules; materializing an assessment separately needs its own reviewed ownership/expiry/snapshot decision.

**No `applicable_intent`, policy result, or migration decision belongs in this unit.** Changing future Intent artifacts while Current-State evidence/context/identity/rules are held fixed SHALL not change the resulting Current State.

An assessment's stable semantic identity SHALL be based on its qualified assertion and evidenced scope using a frozen canonicalization version. Evidence revision, source capture, rule versions, observation window and resulting qualification SHALL be recoverable through its snapshot/assessment lineage. The exact identity relationship (stable assertion ID versus versioned assessment instance) is an I2 freeze decision; it SHALL never let an unchanged display label disguise changed scope or qualification.

## 11. Reuse of v0.5 Qualification and Uncertainty

I2 MUST reuse the existing semantic owner for declared-versus-observed status and coverage. It SHALL NOT implement a parallel `CONFIRMED`/`OBSERVED_ONLY`/`NOT_OBSERVED_IN_WINDOW` formula for local claims. Qualification is computed over **applicable evidence in the requested scope**; evidence from another locality must not improve or downgrade the local qualification through a global union.

Examples to qualify independently:

```text
Locality A: observed caller A CALLS B
Locality B: observed caller A CALLS C

Supported: A→B is established in A; A→C is established in B.
Not supported: A→B is absent in B; A→C is absent in A.
```

**Declared-evidence applicability (frozen minimum `CALLS` rule):** an accepted, currently applicable Service/operation-level declaration is admissible **as source/Service-scoped declared evidence** for an independently observed and exactly matching local `CALLS`, subject to the existing v0.5 identity, source-inventory and operation-matching guards. Thus an observed scoped call with matching declaration is `CONFIRMED`; without one it is `OBSERVED_ONLY`. Only the observed event is Workload-local; `CONFIRMED` does not assert that the declaration was authored for, or exclusively applies to, that Workload. A declared-only Service-level relation creates **no positive Workload-local call**. I1/I2 SHALL test applicable and inapplicable declaration provenance explicitly and reuse the single v0.5 qualification owner on scoped input rather than fork its status algorithm.

**Local coverage boundary:** no v0.6 minimum input supplies independently admissible **Workload-level HTTP coverage**. Therefore local `NOT_OBSERVED_IN_WINDOW` is **not an achievable status in this release's scoped `CALLS` slice and SHALL NOT be emitted**. A matching declared-only Service relation does not create a positive Workload-local claim or a local negative one; where no eligible local `CALLS` is established, the new answer says **not established from available local evidence** with unknown/insufficient local coverage, not verified absence. Service-level `NOT_OBSERVED_IN_WINDOW` and its existing coverage semantics remain unchanged on v0.5 unscoped surfaces. If Workload-level coverage is ever admitted, its evidence source and scope-specific qualification rules require a separate reviewed contract and independent tests, not a silent global-to-local promotion. A locally unsupported/unresolved path stays visible even if another scope is fully supported. Historical v1-only observations are unscoped, not positive v2 evidence.

## 12. I2 Exit Gates

I2 is complete when the versioned v2 ingress/persistence path and legacy v1 coexistence are implemented and one pinned-snapshot input yields reproducible local assessments for two evidenced localities, with a complete lineage to source, identity/mapping, observation and qualification rules. Same-locality disagreements remain visible; different supported localities can coexist. Repeating, reordering, reimporting, and source removal follow the pre-existing deterministic lifecycle guarantees, including v1/v2 coexistence without double-counting and deterministic scoped-evidence replay. Changing only one locality's applicable evidence cannot silently change another locality's result, other than by an explicitly justified shared identity/rule/snapshot dependency recorded in lineage.

---

# Part III — Deterministic Current-State Projection and Public Answers

## 13. Projection Contract and Completeness

A Current-State projection SHALL be a deterministic selection/reconciliation of applicable **Qualified Local Evidence Assessments** for one explicit snapshot and bounded requested scope. It SHALL preserve:

```text
requested and actually evidenced scopes
included local assessments and their identities
known excluded / incompatible scopes and reasons
unresolved/unsupported inputs and missing dimensions
qualification of every returned architectural claim
source/evidence/provenance and rule lineage
observation context / window
projection completeness and truncation/selection limits
```

“Complete” MUST be defined relative to a specified **evaluated input inventory, its bounded evidenced-locality enumeration and the requested selection**, not interpreted as proof that the system has no unknown services, dependencies, other localities or unobserved traffic. A scope filter returning no supported claims is not a verified negative architecture assertion.

Projection SHALL NOT strengthen a claim merely by combining it with other locally supported claims. New cross-boundary or system-level architectural claims require their own applicable evidence, temporal/identity compatibility and qualification rule. In particular:

```text
A CALLS B in scope X + B CALLS C in scope Y
    != established causal A→B→C flow in any scope

A and B DEPLOYED_AS Workloads in namespace N
    != A CALLS B
```

## 14. Context Selection and Differentiated-Locality Answer

I3 SHALL provide a **bounded deterministic answer to the new product question**, without requiring an LLM to compare loosely related snapshots. The caller supplies a subject, supported observation context and optional exact relation/target filters. **Bounded enumeration of evidenced candidate localities is REQUIRED**, not a MAY: discover candidates from current applicable source inventory and independently attributable scoped evidence on one stable snapshot. The answer SHALL disclose the enumeration inventory/revision, included candidates, known unresolved/excluded candidates and reasons, applied bounds, coverage and any truncation. A caller MAY optionally supply a finite exact locality selection for comparison, but need not know the locality list before asking *where*. If the bound is reached, emit an explicit `PARTIAL`/incomplete-enumeration limitation with deterministic continuation or refusal, never silently treat a subset as exhaustive. Localities outside the evaluated inventory remain unknown, not absent. Every included result is evaluated against the **same frozen snapshot/revision fence**.

The answer SHALL distinguish:

- **established in selected locality**: positive supported claim in the stated scope;
- **not established from applicable evidence**: no positive claim, with qualification and coverage/limitations; not an asserted absence;
- **unknown/unsupported/conflicting locality**: no manufactured result for that scope;
- **differing supported claims**: a comparison of separately established scoped assertions, not an inferred contradiction or assurance of completeness.

The comparison is a deterministic **difference between the supported answers for selected localities**; it is not an assessment against Architecture Intent. Missing or insufficient evidence in one selected locality cannot be reported as a negative contrast to positive evidence in another.

### 14.1 Minimum illustrative captured-reference scenario

An independently captured and disclosed controlled reference may establish the same declared Service `service:orders` through two distinct Pod-UID/owner-chain-linked Workloads and two admissible OTel CLIENT observations within the same supported UTC-day window. **Two clusters are not required:** the minimum positive scenario may use two Workloads in the same cluster and namespace, provided each CLIENT span's `k8s.cluster.uid` exactly matches the corresponding captured Kubernetes envelope's `clusterUid` and the Pod UID/owner chain resolves unambiguously in the selected time-compatible capture:

```text
cluster K1 / namespace n1 / caller workload W1 (Pod UID P1):
  orders CALLS pricing
  -> evidence-qualified, observed in whole-UTC-day window T

cluster K1 / namespace n1 / caller workload W2 (Pod UID P2):
  orders CALLS legacy-pricing
  -> evidence-qualified, observed in same window T
```

Its output must report both supported relationships at their exact caller localities and state that no absence or exclusivity has been proved in either locality. The controlled capture MUST NOT use name matching, merely configured Service-level `DEPLOYED_AS`, or synthetic telemetry represented as independent upstream runtime capture. Capture provenance, independent expected results and any *separate* synthetic negative-test fixtures are disclosed.

## 15. Snapshot, Derivation and Stability

All results SHALL be bound to one stable snapshot and deterministic rule/configuration identity, including locality extraction, source capture/revision, accepted identity mappings, qualification and projection versions. Claim/evidence identifiers SHALL be stable under input permutation and idempotent reimport and distinguish genuinely different scoped assertions. **One canonical `snapshot_id` / `model_revision` pair is shared by existing and new service/REST/MCP answers; there is no independent unbound locality fingerprint.** The v0.6 canonicalization SHALL preserve the exact existing v0.5 canonical state, version and fingerprint bytes when **no scoped-v2 evidence exists**: do not unconditionally bump the fingerprint rule version or add empty v2 keys merely by installing v0.6. When v2 evidence exists, include its canonical ordered records and relevant scoped normalization/rule identities **conditionally** in that one canonical state; the snapshot then changes as an intentional consequence of different committed evidence. Existing v1 contribution remains single-counted and v1-only histories stay unscoped. Pod/Workload resolution depends on the captured-resource state already in the canonical snapshot, and changes to that state must also change/qualify the scoped assessment lineage.

I2 SHALL independently check `examples/release-golden-path/expected.json`'s frozen demo-phase `expected_snapshot_id` and v0.5.1 demo/evaluation pins with v2 absent, then show an actual v2-positive capture changes the unified fingerprint and preserves same-snapshot evidence drill-down. If retaining an existing pin proves impossible, no silent fixture update is allowed: record the exact fingerprint-contract change, get a reviewed compatibility/parent-spec amendment, regenerate independently justified expectations and requalify the golden path before candidate freeze. A change in applicable source capture, mapping, rule or locality that affects the answer must be reflected in its lineage and snapshot/assessment identity, not silently treated as an unchanged answer.

An evidence request for a claim SHALL resolve under the **same snapshot**; mismatched or unavailable historical dependencies receive the existing explicit refusal/limitation behavior. This release does not introduce historical snapshot retrieval or trajectory storage. Stale-snapshot retry and revision-fence limits follow the existing service contract; neither transport may silently substitute the newest snapshot.

## 16. Existing Dependency, Drift and Deployment Behavior

Existing unscoped dependency/drift/deployment requests keep their v0.5 meaning, including published qualification statuses and existing `DEPLOYED_AS` resolution methods. I3 SHALL not silently relabel a globally requested service-level claim as local, reinterpret deployment as an application dependency, or turn the existing drift endpoint into future Intent-vs-Current assessment. Where new scoped request parameters are admitted, their absence SHALL preserve existing behavior unless a reviewed versioned compatibility change is required and documented.

`DEPLOYED_AS` remains a Service–Workload identity relation; a locality-aware answer MAY cite it as a contributing identity fact, but it SHALL not treat all dependency claims of the Service as workload-specific on that basis alone. Messaging claims stay under their v0.5 source/identity guards and are only locality-qualified after a separate reviewed applicability amendment and dedicated tests; **they remain unscoped in the minimum v0.6 surface**. Existing `get_service_dependencies`, `get_architecture_drift`, `get_evidence` and REST responses SHALL NOT gain a locality limitation or change meaning merely because a relation cannot be localized. Only the **new relation-locality answer** reports unsupported locality kinds/dimensions. Changing an existing response requires a separate reviewed schema/compatibility decision.

## 17. Public Question-Specific Exposure Proposal

The release requires a bounded, service-owned, deterministic, publicly usable relation-locality projection, not an arbitrary traversal API. **I3 exposure option to freeze before implementation:**

```text
ArchitectureIntelligenceService.get_service_dependencies_by_locality(request)
  REST: /api/services/{id}/dependencies/by-locality  [illustrative route]
  MCP:  get_service_dependencies_by_locality                 [proposed fourth read-only tool]
```

The proposed `get_service_dependencies_by_locality` name follows the existing `get_service_dependencies` convention, but **does not** imply an exhaustive partition of all dependency kinds or proof that a relationship absent from a caller Workload's positive results is locally absent. The initial v0.6 query establishes supported caller-Workload-local HTTP `CALLS` only, discloses unknown/unresolved/excluded results and enumeration bounds, and may compare two evidenced caller Workloads in one snapshot. This is a proposed name and illustrative route; I3.1 still freezes the exact public contract.

The proposed tool expresses a materially new architecture question directly rather than forcing the agent to stitch separate dependency answers into a conclusion. It SHALL not become a generic `get_graph`, free-form query, spatial join, or agent-orchestration capability. If I3 can demonstrate the identical bounded question and comparison safely through a compatible extension of the existing three tools, a reviewed parent amendment may retain three instead. **The final tool count, exact route, request and response shapes are open decisions in §33, not presumed implementation facts.** The positive exit contract is not optional: one deterministic relation-locality answer must be available through both public adapters.

Minimum semantic request fields, to be frozen in versioned schemas:

```text
subject: full canonical Service identity
observation context: explicit environment / compatible bounded window
locality selection: optional finite, exact, validated scope filter; absent = bounded evidenced-candidate enumeration
relation/target selection: supported bounded filters only
```

Minimum answer semantics:

```text
ArchitectureAnswer: producer / schema / snapshot / outcome / limitations
enumerated evidenced candidate scopes, evaluated inventory/revision and enumeration coverage
selected scope, known excluded/unresolved scopes, bounds/truncation and per-scope evaluation status
qualified local claim refs and assessment/claim identity
where each relation is positively established
differing supported results, without implicit negative comparison
coverage/completeness/selection and truncation metadata
source, mapping, qualification and projection lineage
same-snapshot evidence refs
```

The actual supported request/response schema MUST NOT expose a dimension the I1 evidence contract cannot interpret.

## 18. Public Schema and Adapter Parity

I3 SHALL freeze an exposure table **before implementation** mapping each new semantic field/variant to canonical representation (or internal read-model), `ArchitectureIntelligenceService`, REST, negotiated MCP, published JSON Schemas, and evidence resolution. A released public enum/contract change must carry an explicit schema version/migration decision; the v0.5 `schema_version` value `"0.5"` SHALL not be silently reused if the response meaning has changed incompatibly. Build producer version and public schema version remain different concepts.

Equivalent service, REST, and negotiated MCP requests must agree on claims, scopes, qualification, inclusion/exclusion, evidence refs, snapshot and limitations after removing transport envelope differences. All public read calls perform zero graph writes. Tool implementations and REST adapters SHALL not independently reconstruct the locality reasoning. The transport-independent deterministic evaluator calls the semantic service directly.

## 19. I3 Exit Gates

I3 is complete when a coding agent or ordinary HTTP client can enumerate the evidenced localities of a dependency **without first supplying locality identities**, optionally compare two selected supported localities, and receive the same bounded deterministic answer, including enumeration coverage, meaningful abstentions and snapshot-bound drill-down. An independent MCP client SHALL discover the frozen public tool contract, execute the question, resolve evidence at the same snapshot, and reconnect without change in meaning. The existing three v0.5 tools/REST routes and published v0.5.1 demo SHALL pass compatibility regression. A fourth tool is permitted only if the reviewed I3 specification freezes it and the corresponding qualified public schema.

---

# Part IV — Independent Qualification and User Demonstration

## 20. I4 Frozen Evaluation Method

Before running AIP or deriving expected results from code, I4 SHALL independently author the input/evidence dossier, supported claim inventory, selected localities/windows, expected qualifications, expected exclusions and forbidden claims. Each expected fact SHALL identify the original evidence and the rule that licenses the specific locality attribution. Implementation tests and an LLM-generated expected file are not independent truth.

At a minimum, deterministic scenarios SHALL cover:

| Scenario | Required assertion or refusal |
|---|---|
| Same Service, two distinct caller Workloads, two different observed dependencies | Ingestion-time CLIENT Pod attribution yields two distinct scoped-v2 evidence records and qualified edges; no Service-level cross-attribution. |
| Legacy v1 bucket with a separate same-Service Pod identity observation | Unscoped v0.5 relation remains queryable, but no retroactively invented local `CALLS`. |
| Concurrent v1/v2 contributions and replay/order/cross-batch correlation | Existing v0.5 counts, coverage and answer semantics are not doubled; v2 identities/lineage/snapshot are deterministic. |
| No requested localities, multiple evidenced caller scopes, inventory exceeding bound | Bounded enumeration returns attributable candidates, included/excluded/unknown and explicit incomplete coverage or refusal; never silently exhaustive. |
| Matching Service-level declaration and scoped observed call | `CONFIRMED` with separately labelled source-scoped declaration and Workload-local observed evidence; declaration-only never becomes positive Workload-local. |
| Scoped observation with no applicable declaration | `OBSERVED_ONLY`; wrong/missing source scope cannot confirm it. |
| Service-level HTTP coverage but no admitted local evidence | No inferred local `NOT_OBSERVED_IN_WINDOW` or verified absence. |
| Full UTC-day window versus narrower/overlapping partial-day request | The former is eligible under frozen temporal rules; the latter is explicitly unsupported for the first scoped slice. |
| Same Service, two localities with different targets | Comparison describes only differences between established positive results, not inferred absence. |
| Existing `DEPLOYED_AS` via configured mapping but spans have no admissible Pod UID | Service placement may resolve; workload-local `CALLS` does not. |
| Pod UID + time-compatible owner-chain capture in selected snapshot | Caller-local `CALLS` may qualify where other HTTP identity guards succeed; retain capture identity and timestamp. |
| Same-day canary replaces P1 with P3; captures before/after rollout and subsequent promotion or rollback | Against each single snapshot, resolve only retained time-compatible Pod UID/owner evidence; if later authoritative capture lacks P1, P1's old v2 event persists as Pod-scoped but Workload-local assessment becomes `UNRESOLVED`, never absent or silently transferred to P3/current Workload. |
| No v2 evidence versus eligible v2 ingestion | Existing golden-path v0.5 `snapshot_id` is byte-identical without v2; v2 changes the one canonical fingerprint and same-snapshot provenance deterministically. |
| Name-only/namespace-only/label-only/co-location-only | No positive runtime locality qualification or interaction. |
| Source declaration applies at Service level without explicit regional binding | No automatic per-region declared assertion. |
| Different known localities with different target edges | Coexist without global conflict or inferred absence in the other locality. |
| Contradictory applicable identity paths within one locality | Explicit conflict, no precedence guess. |
| Missing cluster UID, unsupported region/tenant, wrong namespace, stale capture | Bounded unsupported/unresolved/inapplicable result, no fabricated scope. |
| No eligible scoped call, with a declared-only Service relation and Service-level partial/none/unknown coverage | New local answer reports not established with unknown/insufficient **local** coverage; no local `NOT_OBSERVED_IN_WINDOW`. Existing unscoped v0.5 qualification and coverage stay unchanged. |
| Snapshot changes between result and evidence drill-down | Explicit refusal or bounded retry, never silent evidence substitution. |
| Source reimport/reorder/inventory disappearance/authorized removal | Deterministic result and existing lifecycle/removal authority preserved. |
| Caller locality evidenced but target locality missing | Do not claim target is local or remote. |
| Two qualified one-hop edges / cross-boundary path | No new causal flow or end-to-end business outcome from traversal alone. |
| Intent-like document or agent-generated narrative is added | No alteration to Current State or its lineage. |
| Existing v0.5.1 Quarkus replay and operator AsyncAPI overlay | No newly inferred runtime locality or Kafka observation. |

I4 SHALL run all qualifying scenarios twice from clean state with byte-identical normalized semantic output and no unexplained nondeterminism. For equivalent requests, semantic mismatches across service/REST/MCP SHALL be zero; no material missing supported claims, no false supported scope, no silent context loss, and no regression in pre-existing qualification. A lower false-claim rate achieved solely by returning every locality unresolved is not success (§24).

## 21. I4 Compatibility and Security Gates

The qualification matrix SHALL include existing v0.5.0/v0.5.1 deterministic evaluation, ingestion/identity/Pub/Sub regression, REST/negotiated MCP interoperability and read-only/security tests. No new transport authorization, persistent distributed assessor, remote reference expansion, broad telemetry payload retention, source-scope widening, or secret capture is permitted by the locality feature. New locality evidence is bounded and sanitized; snapshot and reference identifiers remain opaque on public surfaces.

The new per-Pod/per-relation evidence identity increases bucket cardinality with **distinct Pod UIDs over time (Pod churn), not just the number of Workloads**. I4 SHALL benchmark fixed Workload count with repeated same-day Pod replacement as well as two-locality and higher-cardinality ingestion/read/fingerprint cost and retained evidence size against the existing benchmark, including capture-selection/unresolved rates, with an explicit growth/bound budget and product impact. [ADR 0012](../../adr/0012-observed-evidence-retention.md) remains **Proposed**, not an implemented retention policy: do not silently compact, delete or coarsen scoped evidence to make performance pass. Any later accepted compaction rule must preserve locality identity/provenance and explicitly degrade time resolution and snapshot identity; unscoped compaction must not silently erase scoped support. Do not mask a correctness issue with undocumented caching or stronger claims from stale projections. Public answer bounding and determinism outrank maximal graph coverage.

## 22. I5 Real-System Qualification

I5 SHALL revalidate the released, pinned **Quarkus Super Heroes** and **Apache Airflow** v0.5 dossiers on the final v0.6 candidate, preserving independent upstream truth and source-mode labels. Quarkus provides a realistic positive developer story; Airflow remains a materially different system and an important negative/insufficient-evidence case for application dependencies. Their lack of a suitable pair of upstream-proven cross-locality `CALLS` examples is a **coverage gap**, not a license to rewrite either frozen dossier.

To qualify the new two-locality positive path, I5 SHALL include **one independently captured, actual two-locality execution** of a bounded deployed reference/harness (for example two distinct caller Workloads of one logical Service in one cluster/namespace during a controlled canary rollout; two clusters are not a prerequisite). Freeze the deployed revision, Kubernetes envelope `clusterUid`, independently emitted OTel CLIENT Resource `k8s.cluster.uid` that matches it, Pod UID/owner-chain capture, real `capturedAt` timestamps, cross-batch attribution where used, selected query/capture revision, and independently authored expected results **before** comparing with AIP. An additional generated negative-test fixture MAY be used but MUST be labelled as synthetic; neither may be described as a property of upstream Quarkus/Airflow or a production pilot. I1 SHALL define the minimal capture harness, owner, collection steps (including capturing the old/new Pod overlap before an authoritative replacement removes either), and required source/expected-result pins; I2 SHALL rehearse its attribution/capture plumbing and capture-format validation early enough to expose infrastructure blockers before I5. This is a qualification data-acquisition dependency, **not** a live Kubernetes ingestion/admission feature in AIP. A live deployment is needed when recording the qualifying capture, **not** for an end user's later frozen replay/demo (§23). If the actual two-locality capture cannot be independently established, I5 cannot claim real-execution locality qualification; stop and seek an explicit scope/gate amendment rather than substitute hand-crafted telemetry. Prefer reusing known v0.5 semantic vocabulary for continuity, never editing the frozen upstream dossiers.

Findings SHALL distinguish `CORRECT`, `MISSING_SUPPORTED`, `UNSUPPORTED`, `UNRESOLVED`, `INSUFFICIENT_EVIDENCE`, and genuine semantic defects per the governing validation methodology. No target-specific exception may be introduced solely to pass one demonstration. Re-run both targets and the supporting locality cases on the final candidate after accepted cross-system fixes.

## 23. I5 User Demonstration

Extend (do not destroy) the v0.5.1 Quarkus task-led entry point with a bounded **where-is-this-dependency-established?** walkthrough. Primary-user job story: *Before changing a Service during a canary or multi-workload rollout, identify which direct dependencies are actually established by the old and new deployed caller Workloads, rather than assuming the Service has one global dependency set.* The developer first inspects the original published Quarkus answer, then a **separately labelled replay of the independently captured two-locality reference** demonstrates what changes when per-interaction caller-locality evidence is available. **Capture the rollout while the old and new Pod UID/owner chains are both present in one time-compatible selected snapshot** (or use the pinned controlled capture of that overlap for offline replay); demonstrate the locality answer **before a later authoritative capture displaces either Pod**. A post-rollout capture omitting the old Pod makes its earlier Workload-local result `UNRESOLVED`; do not promise historical canary comparison after replacement, reconstruct lost Pod ownership, or claim that archived files enable querying an unavailable snapshot. State this time-sensitive operational prerequisite prominently in the demo instructions. Do not claim the frozen v0.5.1 Quarkus replay already provides this evidence.

The walkthrough SHALL show the actual request and answer for:

1. one positively localized direct relationship with its evidence;
2. the same Service in a second evidenced locality with a different supported dependency;
3. one missing/unresolved-locality or no-eligible-local-call case with **unknown/insufficient local coverage**, never a local `NOT_OBSERVED_IN_WINDOW` claim or proof of absence;
4. a Service `DEPLOYED_AS` mapping which does **not** prove that every runtime `CALLS` originated at that Workload;
5. enumeration of evidenced candidate localities without caller-supplied IDs, optional included/excluded selection, explicit inventory/enumeration coverage and same-snapshot evidence drill-down.

This is a deterministic, LLM-optional AIP demonstration. An optional real agent conversation illustrates consumption but is not itself qualification evidence. AIP output, pinned upstream source dossier, **independently captured controlled two-locality reference with separately authored expected results**, any explicitly synthetic negative-test fixture, and agent interpretation SHALL remain separately labelled. Keep setup/teardown simple and do not require a live Kubernetes cluster, Kafka broker, Quarkus build, extra agent harness or model key merely to reproduce the release capability.

## 24. Product Pilot Decision Gate

A release capability is not product-validated solely because semantic tests pass. Before a bounded pilot, the **pilot owner SHALL choose and freeze** representative service-change tasks, independently expected answers and **numeric or categorical success/stop thresholds before any pilot results are inspected**; this parent spec prescribes no values. Compare with and without AIP under comparable source access for the initial target user (platform/architecture teams enabling coding agents). Include the canary/multi-workload job story from §23 and instruct pilot users to obtain/use a time-compatible capture **during the old/new rollout overlap**, before a subsequent authoritative import drops the old Pod. If the eligible capture is unavailable, record an attribution/coverage limitation and the added capture overhead; do not score an unsupported historical comparison as a success. Measure together:

```text
time/engineering effort to establish the correct scoped dependency context
time to distinguish local deviation from system-wide deviation
useful supported-answer coverage and justified abstention
false local/global assumptions and misleading absence claims caught
setup, capture, source maintenance, mapping and clarification effort
agent/reviewer ability to preserve scope and evidence in follow-up questions
independently detectable post-change differences versus false alarms
```

If the pilot runs, record `CONTINUE`, `NARROW`, `DEFER`, or `STOP` with measured outcomes and reasons against the **pre-frozen owner-defined thresholds**. If it has not run by the v0.6 technical release decision, record `NOT_RUN`, identify the owner/follow-up validation and explicitly carry the unsatisfied product-value gate into the **v1.0-rc stable-contract admission ledger**: no claim of demonstrated customer outcome or stable-contract readiness for affected capabilities is permitted until a later pilot reaches an accepted disposition. Do not re-label the I5 technical captured run or the demonstration as a product pilot. A failed gate requires an explicit product/scope disposition and, where material, a roadmap update; `NARROW`/`DEFER`/`STOP` dispositions must be applied before freezing affected capabilities. Technical release qualification and product-value validation are distinct; this parent prescribes no arbitrary numerical thresholds.

## 25. I4/I5 Exit Evidence

Completion records SHALL cite exact pinned upstream dossiers and independently captured two-locality run, source/evidence revisions, expected facts authored independently, qualification command/results for both clean runs, public schema parity, real-system results, enumerated scope/coverage, unresolved/unsupported cases, legacy-v1 migration/retention-cost findings, evidence-lineage checks, pilot thresholds/status/disposition and v1.0-rc carry-forward if NOT_RUN, and any documented scope amendment. A dossier claim unsupported by the source is not repaired by an attractive demo narrative.

---

# Part V — Release, Compatibility and Completion

## 26. Candidate Freeze and Identity

I6 freezes an exact `CANDIDATE_SHA`, package/producer version, committed schema/mapping/rule versions, test and evaluation results, pinned upstream sources and actual controlled capture (plus any separately identified synthetic fixtures), expected snapshots and demo outputs. Every qualification assertion SHALL name the exact candidate or immutable artifact it tested. After a change, requalify affected and required end-to-end gates before presenting the candidate as ready. An earlier source checkout, successful PR head, locally rebuilt image, or older tagged RC is not substitutable for the final candidate.

## 27. Pre-Publication Qualification and Decision

The final candidate SHALL pass the release's unit/integration/independent-evaluation suites, both pinned real-system revalidations, the **independently captured controlled two-locality reference and any disclosed auxiliary synthetic tests**, clean-state deterministic two-run comparison, public REST/MCP parity and evidence drill-down, v0.5.1 demo regression **including existing no-v2 snapshot-ID pins**, golden-path deployment, dependency/container/security/SBOM review, and documentation/source-link checks. Any accepted vulnerability disposition SHALL identify the specific artifact and owner decision; no unresolved release-blocking finding remains.

Technical readiness and publication authority remain distinct. Record a clear `GO`/`NO_GO` technical result against the exact candidate. Only the repository owner authorizes publication. `RELEASE_READY` is not a claim that a final GitHub release or container image was published.

## 28. Publication, Published-Image Golden Path and Closure

If authorized, tag and publish the exact qualified candidate as `v0.6.0`, verify tag/commit identity, published workflow attempt, GHCR digest, anonymous pull, package/build revision, schemas, release notes, full security disposition and published-image golden path. Re-execute a same-snapshot locality answer and evidence drill-down from the published digest, and record its evidence/projection identity. The published image, not a candidate rebuild, is the verification target.

Terminal results are:

```text
RELEASE_READY_NOT_PUBLISHED
  technical qualification passed; owner did not authorize publication; closure records no release claim

SHIPPED_VERIFIED
  owner authorized publication; exact tagged/published artifacts independently verified

NO_GO / POST_RELEASE_FAILED
  release-blocking technical or post-publication verification failure, with explicit disposition
```

The exact files/commands and whether an RC tag is warranted are I6 decisions; v0.5.0's I6 and v0.5.1's lightweight release record are process precedents, not authorization to skip the capability-release qualification specified here.

## 29. Public Surface and Compatibility

`ArchitectureIntelligenceService` SHALL remain the single semantic owner. REST and standard negotiated MCP are public adapters, not alternate sources of architectural truth. The new locality question must be available equivalently on both and validated by a service-direct semantic oracle. Versioned schema changes and migration examples SHALL accompany any added claim/context/limitation shape. Maintain backward compatibility for supported v0.5 requests where feasible; an intentional pre-v1.0 breaking change requires an explicit reviewed decision and migration note, not a silent optional-field widening. Existing generic graph browsing remains outside the Architecture Intelligence correctness path.

## 30. Required Documentation and Evidence

Publish an I1 support matrix (dimension × source/mapping × claim kind), expressly identifying the narrowed v0.6 slice versus wider ROADMAP candidates; distinction between source, caller and target locality; query-snapshot capture selection and Pod-churn limitations; v1/v2 observed-evidence migration/replay and UTC-day resolution; no-v2 snapshot-ID compatibility with frozen golden-path pins and conditional v2 fingerprinting; evidence-cardinality/ADR 0012 disposition; explicit absence of Workload-level coverage/local `NOT_OBSERVED_IN_WINDOW` in this slice; assessment/projection semantics; evidenced-locality enumeration, reasoned limitations and completeness; REST/MCP request/response examples and schemas; non-observation and temporal compatibility examples; controlled real-capture setup and replay, with a prominent rollout-overlap capture prerequisite and later-capture `UNRESOLVED` example; deterministic evaluation; real-system findings; version/migration guidance; candidate and publication records. **Before I6 candidate freeze**, reconcile the v0.6 entry in `ROADMAP.md` with the accepted release scope and record region, tenant, service-version and messaging locality as explicitly deferred/unassigned candidates or attach a separately authorized later milestone; do not silently assign these to v0.7/v0.8, whose Intent/Assessment scope remains distinct. Explain the difference between *supported in selected localities* and *universally true*, and distinguish independently captured controlled reference behaviour, separately authored expected results, synthetic test fixtures and independently observed production behaviour; none are interchangeable.

## 31. Release-Level Definition of Done

A user can answer **“Where is this dependency established?” without supplying locality identities first, and “How do supported results differ between selected evidenced localities?”** over one stable snapshot, with independently justified local assessments, explicit locality evidence/qualification, deterministic projection, exclusions/coverage, same-snapshot provenance, and correct refusal where the evidence does not support an answer. The new question works through real REST and negotiated MCP clients, is independently qualified twice from clean state, survives v0.5 regression, and is understandable in a task-led demonstration. Final release claims follow only from the terminal I6 outcome.

Permitted capability claim upon qualification:

> **AIP v0.6.0 discovers bounded evidenced caller localities, establishes supported direct HTTP `CALLS` within their admitted UTC-day observation contexts, and deterministically compares qualified local Current-State results without inventing global truths, negative dependencies, intent or causal flows. The initial locality-qualified relation/dimension surface is explicitly narrower than the full roadmap candidates.**

## 32. Relationship to Later Releases

`v0.6.0` produces **Current State only**. `v0.7` may subsequently represent independently attributable Architectural Intent Statements and their authority/lifecycle/scope/effective-time applicability. `v0.8` may then assess Current State against independently applicable Intended Architecture. Neither future path can retroactively become an input into v0.6 Current-State qualification. Historical trajectories, transformation reasoning and distributed local-assessor deployment remain beyond v1.0 unless a later authorized roadmap decision changes that boundary.

## 33. Increment-Level Contract Freeze Register

The parent release scope and semantic constraints above are accepted. The following **implementation and public-contract details remain deliberately delegated to reviewed increment specifications** and MUST be frozen **before** their corresponding implementation and independent truth fixtures. Their delegation does not reopen or weaken the accepted constraints.

| Owner | Decision to freeze | Constraint already fixed by this parent |
|---|---|---|
| I1 | Actual `LocalityScope` representation, supported keys/combinations and rejection taxonomy; UTC-day window bound normalization | Minimum environment/full UTC-day window plus evidenced cluster/namespace/Workload; region/tenant/version-locality and messaging outside the minimum slice; missing/unsupported is never wildcard; source/caller/target/claim scopes stay distinct. |
| I1/I2 | Exact ingestion-time CLIENT Resource/Pod attribution (including cross-batch), v2 scoped observed-evidence ID/key/schema, scoped persistence and evidence reachability, v1/v2 coexistence, no-double-counting replay/migration and ADR 0012 cardinality budget | A distinct interaction-preserving v2 path is mandatory; legacy v1 daily aggregates and independent runtime identity observations cannot be rejoined/backfilled into scoped calls; no locality from `DEPLOYED_AS` alone. |
| I1/I2 | Query-time, selected-snapshot capture/owner selection across Pod churn; capture disappearance disposition; exact full UTC-day window bounds/refusal for finer requests | Retain per-event Pod UID; no historical snapshot, nearest-name resolution, absent-Pod backfill or continuous Pod presence inference; preserve v0.5 matching unchanged. |
| I1/I2 | Source/matching conformance for shared Service-scoped declaration and local observed call; Workload-coverage scope guard | `CONFIRMED` requires matching declaration and observed scoped call; no admitted Workload-level coverage, so local `NOT_OBSERVED_IN_WINDOW` is unreachable and MUST NOT be emitted in the first slice. |
| I2 | Stable scoped assertion/assessment identity, internal read/persist choice, qualification/lineage, and conditional one-fingerprint v2 canonical-state implementation | When v2 is absent, existing v0.5 canonicalization/version/snapshot ID and frozen golden pins remain byte-identical; v2 adds fingerprint inputs conditionally, not a separate snapshot. |
| I3 | Public relation-locality route/tool versus equivalent compatible extension; enumerated-evidence inventory/bounds and deterministic continuation/refusal, optional exact locality selection, response names/schema-version migration | Mandatory bounded evidenced-locality enumeration without supplying locality IDs, plus optional same-snapshot comparison via service, REST and negotiated MCP; no agent-assembled truth or generic graph tool. |
| I3 | Exact completeness, enumeration inventory/coverage, included/excluded/unknown scope fields, scoped limitations and canonical order | Completeness relative to evaluated inventory/enumeration only, with visible bounds/truncation; no silent exclusion, universal claim or absent-dependency inference. |
| I4 | Independent truth tables including capture-before/after canary replacement/promotion, no-v2/v2 snapshot pins, no-local-coverage guard, Pod-churn cardinality; normalized two-run comparison | False supported scope, context loss, unrecorded snapshot-ID changes and cross-surface disagreement are blockers. |
| I5 | Pin/independent authorship of an actual controlled two-Workload rollout-overlap capture (not necessarily two clusters), clusterUid/OTel k8s.cluster.uid match, capture revisions/timestamps and expected results; pilot thresholds/status | I1 plans and I2 rehearses the capture harness before I5; demo/pilot must use the selected capture while both Pod chains are available; distinguish actual capture, auxiliary synthetic tests and production pilot; frozen upstream dossiers remain unchanged. |
| I6 | Candidate evidence filenames, RC use, ROADMAP deferred-scope reconciliation, publication/verification commands and owner decision | Before candidate freeze, update ROADMAP v0.6 scope and explicitly track deferred region/version/messaging locality without assuming a later release; exact candidate/digest and terminal outcomes. |

## 34. Release Specification Acceptance Contract

This accepted parent specification binds the increment specifications and final v0.6.0 qualification to the following conditions:

1. it adds a materially new **locality-aware architecture question**, including bounded evidenced-locality enumeration, rather than repackaging deployment resolution or requiring the caller to supply known localities;
2. a distinct versioned ingestion-time per-interaction v2 caller identity and conservative v1 migration are required for the positive `CALLS` slice; source-scoped declarations and configured deployment mapping cannot masquerade as observed workload-local interactions;
3. supported local claims can coexist, while unknown/unsupported/partial scopes never imply universal truth or local absence;
4. local assessments and projections preserve existing qualification, source applicability, no-v2 golden snapshot IDs, one conditional v2 fingerprint, derivation and evidence-reference rules; local `NOT_OBSERVED_IN_WINDOW` is not claimed without a Workload-level coverage source, and Intent remains separate;
5. REST/MCP exposure is bounded, deterministic and owned by one semantic service, with explicit public versioning and a decision on the proposed fourth tool;
6. independent tests and a disclosed **actual two-Workload capture**, with matched CLIENT/Kubernetes cluster identity and query-snapshot Pod-chain resolution, prove the new capability without rewriting frozen Quarkus/Airflow source truth or claiming that the current capture retains replaced Pods; and
7. completion delivers a runnable user-job demonstration and records product-value measurements or an explicit `NOT_RUN`/v1.0-rc carry-forward, never misreporting a technical release as a passed product pilot or stable-contract gate.
