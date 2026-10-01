# AIP v0.6.0 I3 — Bounded Current-State Projection and Public Answers

**Status:** **Accepted — revision 0.2, owner-accepted increment specification following PR #382 review.** The I3 scope, invariants and acceptance gates below are approved; details explicitly marked **[I3 proposal]** remain delegated to the reviewed I3.1 public-contract freeze before implementation. Acceptance here does **not** freeze a REST route, a fourth MCP tool, schema fields or numeric presentation caps.  
**Release / increment:** v0.6.0 / I3, Locality-Aware Current State.  
**Repository path:** `docs/specifications/0.6.0/i3-bounded-current-state-projection-and-public-answers.md`  
**Entry baseline inspected:** main at 2bf9cd5a1e45ded2447297f3563da98f8ce06b00.  
**I2 completion:** I2.6d merged in #376 (46f700ee4a67399a67e406c8e445db572fd0a31a); its closure SHA was recorded in #377 (1263db508d37c8cbc9421349f6cc661b2542f9c9). I2 is complete as an **internal** increment, not qualified or released as v0.6.0.  
**Governing authority:** [accepted v0.6.0 parent](specification.md), especially §§3–5, 13–19, 29–34; [accepted I1 contract](i1-locality-and-evidence-applicability.md) and [support matrix](i1-locality-support-matrix.md), particularly I1 §5.1; [accepted I2 specification](i2-scoped-evidence-and-qualified-local-assessment.md), [D1–D16 decisions](i2-decision-record.md), [I2 completion record](i2-completion-record.md), and [I2 → I3 internal handoff](i2-i3-handoff.md).  
**Frozen inputs:** I1's read-only 65-variant [oracle](i1-vectors/conformance-expected.json) and [I2 mapping](i2-conformance-matrix.md), I2 identity/snapshot vectors, and the [controlled-capture rehearsal](../../../tests/fixtures/locality/rehearsal/RUN-RECORD.md) (REHEARSAL — NOT I5). Do not rewrite them to match new public output.

This follows the I2 specification's **purpose → scope → authority/decisions → semantic flow → concrete contracts → independent qualification → slices → DoD → review decisions** structure. This accepted document governs I3 implementation and qualification; bracketed **[I3 proposal]** choices remain open for I3.1 review. No implementation, public schema, tool count, API route, or successful qualification is claimed here.

## 1. Purpose and exit outcome

I3 turns I2's first independently qualified **caller-Workload-local** HTTP CALLS assessments into one bounded, deterministic, user-facing Current-State question:

> **Where is this dependency established, and how do the positively supported results differ between selected evidenced caller localities?**

A caller supplies the full canonical Service identity, an environment and whole-UTC-day observation window, and optionally an exact Operation/provider or captured-locality selection. They **do not need to know the locality IDs first**. AIP enumerates a bounded inventory of the caller's evidenced localities, retains positive assessments and unresolved/unsupported/excluded candidates, projects exact Operation-granular results to provider Services where ownership is proved, and optionally compares selected scopes **within one canonical snapshot**. It explains what was actually evaluated and where further evidence is required.

Minimum demonstrable result, building on I2's already-rehearsed example: the single canonical caller Service `service:orders` has two separately captured Deployment Workload identities. On the compatible C1 overlap capture, W1 (Deployment `orders`) → O1 (`pricing`, `GET /prices`) is `CONFIRMED`; W2 (Deployment `orders-canary`) → O2 (`legacy-pricing`, `GET /prices`) is `OBSERVED_ONLY`. W1 and W2 are **caller Workloads**, not two caller Services. The public answer preserves the original Operations, identity/provenance and explicit limitation that an omitted relation in the other Workload is **not** evidence of local absence. After C2 replaces the old Pod chain, its retained v2 record is visible as `UNRESOLVED`, not silently reassigned or removed.

I3's exit deliverable is a **read-only, independently testable public semantic service + REST + negotiated MCP** capability, versioned schema and a same-snapshot scoped-evidence drill-down. I4 owns independent final-candidate truth tables and two-run/surface repeatability; I5 still owns the actual, independently captured controlled reference and user demonstration; I6 owns release qualification and publication. The I2 rehearsal does not become I5 evidence merely because it is replayed through I3.

## 2. Scope and non-goals

**In scope:** a versioned relation-locality query contract; mandatory evidenced-locality enumeration; explicit selected capture and exact caller-Workload filters; bounded candidate/pair inventory and continuation or honest refusal; Operation → unique provider Service resolution; deterministic per-Workload Current-State projection; qualification-preserving same-snapshot comparison; completeness/included/excluded/unknown accounting; sanitized scoped-evidence drill-down; one semantic owner; REST and negotiated MCP parity; independently authored tests and I4 handoff.

**Not in scope:** changing CLIENT attribution/v2 identities or I1/I2 phase rules; a new Kubernetes/OTel source; historical capture reconstruction; inferring target Workload or Service placement from caller location; region/tenant/service-version/messaging locality; a workload-coverage source or local NOT_OBSERVED_IN_WINDOW; causal paths, mesh topology, global absence or exclusivity; an arbitrary graph/Cypher tool; Intent/policy/remediation; compaction/retention from proposed ADR 0012; a fifth MCP tool without separate approval; or a default-flag flip outside the D16 golden-path re-freeze.

The existing three Architecture Intelligence MCP tools, legacy REST routes, dependency/drift/evidence semantics and published v0.5.1 demonstration remain compatible. A v0.5 request does not gain a locality limitation simply because I3 cannot localize a messaging or unscoped relation.

## 3. Authority and frozen versus proposed decisions

| Area | Already fixed by parent/I1/I2 | Decision I3 must freeze before implementing it |
|---|---|---|
| Semantic owner | ArchitectureIntelligenceService; pure I2 applicability/qualification under one revision fence | Public service method and projection/read-model ownership; no adapter-side reasoning |
| Supported facts | CALLS from original CLIENT with admitted v2; exact canonical Operation; qualified caller Workload only | Public query/filter names, supported dimensions and provider-Service projection shape |
| Source choice | Explicit source (ID, current revision) or implicit **proven covering sources**; all candidate/source pair results retained | Public source selection, inventory descriptions and visibility of every pair |
| Candidate reading | Filter by caller Service and optional exact Operation only; **not** by environment/day/workload | Enumeration order, fan-out limits and continuation/refusal |
| Context | Whole UTC days and exact environment; unsupported finer granularity; no Workload coverage | Public request validation and outcome/error mapping |
| Churn | Retained v2 remains; missing selected-capture Pod/owner is UNRESOLVED | Selection and comparison behavior when current snapshot has lost C1 |
| Positive qualification | CONFIRMED or OBSERVED_ONLY **per Operation**, via shared kernel | Provider grouping and presentation of mixed Operation qualifications; no pooled promotion |
| Identity | I2 stable assertion vs snapshot-bound assessment instance; captured Workload UID distinguishes incarnations | Public reference and grouping representation; public schema/version |
| Snapshot | One canonical snapshot/model revision; conditional v2 keys, exact no-v2 pin; no historical query | Cross-page snapshot binding and scoped-evidence resolver |
| Public API | One bounded relation-locality answer via both REST and negotiated MCP is mandatory | Fourth read-only tool versus reviewed equivalent extension; route/tool count |
| Completeness | Relative to **evaluated** inventory only; unobserved/unsupported ≠ absent | Exact status, counts, continuation/bounds and explicit unknown/excluded categories |
| D16 | Default scoped-evidence flag remains false until reviewed golden-path re-freeze | No I3-only early default flip; record I6 owner and migration impact |

**Accepted scope vs delegated choices.** The I3 exit capability and semantic invariants in this document are accepted. Choices marked **[I3 proposal]** are not yet frozen and SHALL be decided in the reviewed I3.1 public-contract decision record before their implementation. Parent §§13–19 and I1/I2 semantic decisions remain authoritative; an I3 proposal that contradicts them is not silently adopted by writing code or updating expectations.

## 4. End-to-end data flow and one semantic owner

~~~text
Caller Service + environment + exact whole-day window
  + optional Operation / provider / capture / captured Workload
    ↓
I2 read_scoped_applicability / assess_local_calls:
  unfiltered v2 candidate page → every eligible source pair
  → phase-gated applicability → local Operation assessments/limitations
  → one canonical snapshot_id / model_revision
    ↓
I3: validated bounded inventory → unique Operation owner lookup
  → exact caller-Workload grouping → qualified per-Operation findings
  → optional same-snapshot selected-locality comparison
  → positive / unresolved / excluded / unknown + completeness
    ↓
ArchitectureIntelligenceService (sole semantic owner)
    ├── versioned REST adapter
    └── negotiated MCP adapter (proposed fourth read-only tool)
    ↓
Same-snapshot scoped evidence and capture/owner lineage drill-down
~~~

I3 SHALL reuse I2's LocalityRequest, source-selection phases and QualifiedLocalEvidenceAssessment. It SHALL NOT re-evaluate a Pod's owner or the declared/observed truth table in API/MCP/LLM code. I3's pure read-side projection can be a separate module called by ArchitectureIntelligenceService, but **not a second semantic engine** or a persisted inferred locality graph.

I2's assess_local_calls currently opens its **own** read-only session and returns at most one 500-v2-record page. If I3 combines pages, inventory queries or evidence lookups, it must use a demonstrably consistent snapshot (or refuse on changed snapshot) rather than joining independently read latest results. An independent I3 read helper may be needed; that helper reuses I2's evaluation/assessment owners rather than reimplementing them.

## 5. Public query and exact-scope selection

**[I3 proposal — request shape to freeze]** A new typed request, tentatively ServiceDependenciesByLocalityRequest, has:

| Field | Proposed meaning |
|---|---|
| subject_service_id | Full canonical caller Service ID; never display-name matching |
| environment, first_day, last_day | Required exact environment and inclusive whole UTC days, YYYY-MM-DD; no implicit current day |
| relation_type | CALLS only for first v0.6 locality answer |
| object_operation_id | Optional exact canonical Operation; narrowing the **candidate** read is permitted by I2 |
| provider_service_id | Optional exact provider Service filter applied **after** unique Operation ownership is established; no early omission of unresolved owners |
| source_selector | Optional exact accepted source instance and its current revision; absent invokes I2 proven-covering-source rules, **not all sources treated as missing-Pod tests** |
| caller_localities | Optional exact captured caller Workload identities, including cluster UID, namespace, supported kind and captured Workload UID; absence means **mandatory discovery** |
| compare | Optional finite exact identities to compare (proposed maximum two). If caller_localities is supplied, every compared identity MUST be in that filter; otherwise the query enumerates the unfiltered evidenced candidates and compares the two requested identities within that one evaluated inventory. A compared identity beyond a bound does not become an absence/difference result. |
| snapshot_id | Optional latest-snapshot assertion or required continuation/drill-down fence; reject stale/mismatched values |
| cursor | Optional opaque bounded continuation, exclusively for the same normalized query and snapshot |

The selected locality is **caller** scope. Do not conflate it with capture authority scope, caller Service, provider's target runtime, or a placement fact. Exact Workload identity includes the captured UID; two versions of one named Workload are distinct. A source revision is not a human-readable cluster name or a substitute Workload ID.

**Input outcomes:** malformed IDs/windows/cursors are validation errors; well-formed but unsupported relations, dimensions or sub-day resolutions preserve I2's machine-visible `UNSUPPORTED` refusal. An empty candidate read is **not** proof that the caller Service is unknown. An absent or stale explicit source selector produces **zero admitted pairs**, exactly as I2 D13.3 specifies; it shares I2's `INSUFFICIENT_EVIDENCE` / `NO_SELECTABLE_COVERING_SOURCE` result with implicit no-cover and MUST NOT be relabeled as a distinct I2 disposition. An absent eligible v2 similarly does not establish an absent dependency or legacy-only history. [I3 proposal] If identifying a genuinely unknown Service or stale selector is useful to the public caller, introduce **separate read-only, snapshot-bound existence/revision diagnostics** alongside the unchanged I2 result, with independent tests; do not promise those distinctions until the lookups are implemented and frozen. A candidate query MUST still let wrong-environment/UTC-day v2 reach I2 phase 3 (L10b/L17d); locality and provider filters cannot become a shortcut that erases these diagnostics.

Freeze exact public field names and REST/MCP refusal mappings before schemas or independent expected fixtures are authored.

## 6. Evidenced-locality inventory and provenance

Enumeration is **mandatory** when caller_localities is absent. Its starting point is I2's retained v2 candidates for the caller (and optional exact Operation), plus the accepted captured-source inventory against which I2 actually evaluates them. Report **both** the per-candidate summary and its original source-specific pair outcomes; do not replace the latter with a preferred capture, one winning source, or a generic "not found."

An evidenced candidate caller locality is a **proposition derived from the evaluated candidate/source pair**, not a catalog of all Workloads in the cluster. Eligible APPLICABLE candidates support a captured Workload locality. Non-applicable candidates remain visible in an explicit limitations inventory, including incompatible environments/days, capture-timestamp mismatches, Pod missing from an actually covering source, inconsistent UID/namespace, ambiguous/conflicting owners and the no-cover abstention. A capture with an unrelated cluster/namespace that did not meet I2's implicit coverage predicate is **not** a missing Pod; a rejected snapshot is not an eligible source.

**[I3 proposal — inventory fields]** Each public response carries:

- evaluated_snapshot_id and model_revision, normalized requested environment/days and source-selection mode;
- evaluated_v2_candidate_count, admitted_pair_count, evaluated capture source IDs/revisions/scope summaries, and the actual internal/public bounds;
- included positive caller Workload identities and positive Operation assessments;
- candidate summaries plus every admitted pair's source ID/revision, admission basis, phase, disposition, reason/limitation codes, and bounded source evidence refs;
- known excluded/inapplicable, unresolved/conflicting, unsupported and no-cover items; non-paired sources are **not** represented as pairs;
- enumeration completeness/continuation and any unscanned remainder as **unknown**, not absent.

Do not label a source "complete across the cluster" merely because its captured envelope is COMPLETE; its actual finite namespace/resource scope is the authority. No claim about other Services, clusters, localities or unobserved calls follows from completing this enumeration.

## 7. Bounds, stable continuation and incomplete pages

I2's fixed D3 read is **up to 500 v2 records per candidate page** (in ascending v2 ID, with a one-row-ahead truncation check). That is an *internal* bound, not a public promise of exhaustive enumeration. I3 must separately bound published candidate, pair, positive-locality, Operation-group, evidence and comparison cardinalities, and refuse or return PARTIAL before uncontrolled expansion.

**[I3 proposal — initial bounded shape, subject to cost review]**

- At most **500 v2 candidates** per query page, aligned with the existing I2 maximum.
- At most **50 distinct caller Workload localities**, **200 provider/Operation membership rows**, and **2,000 candidate/source pair rows** returned per answer page. Exhausting a presentation cap is visibly `PARTIAL` or a typed bounded refusal; it never drops the remaining items with `ANSWERED`/exhaustive meaning. Limits are applied to a **deterministic prefix of complete v2 candidates**, not by cutting the admitted source-pair list or evidence for an individual candidate. The counts are proposals, not proven safe fan-out limits.
- Comparison accepts **two** exact Workload identities for the first slice. No broad Cartesian product across localities.
- Scoped-evidence drill-down accepts **1–20** exact refs per request, independently bounded by payload size and sanitized metadata.
- A single candidate may have more source pairs than the proposed 2,000-pair presentation cap; I2's 500-candidate page may likewise exceed an I3 cap before I2's own `truncated` flag is set. I3 MUST either add a **bounded preflight/fan-out check** plus a smaller internal batch size (a separately reviewed `assess_local_calls`/read size parameter, never exceeding D3's maximum of 500), or fail closed with a typed result-limit refusal **before** uncontrolled materialization. If a single candidate exceeds the permitted pair/evidence representation, it MUST NOT be silently omitted, partially represented as a qualified positive, or bypassed without an explicit machine-visible disposition. **[I3.1 liveness decision to freeze]** Either (a) fail closed with a typed refusal and no advancement past that candidate, disclosing that later candidates cannot be reached with this request/bound, **or** (b) publish a bounded explicit `REFUSED`/`UNKNOWN` candidate entry identifying its v2 ID and over-limit reason, omit its unexamined pairs without suggesting they were evaluated, and allow the cursor to advance past that **accounted-for** candidate. In (b), the result remains incomplete for positive qualification and candidate/source-pair inventory; a later page must not treat that candidate as a positive or as absent. Freeze the chosen option, data shape, counts and test oracle in I3.1 before implementation; these are not measured limits or SLOs.

**[I3 proposal — continuation contract]** A cursor is an opaque, versioned encoding of the last **fully presented or explicitly accounted-for v2 candidate ID**, the **entire normalized query/selection**, the chosen canonical `snapshot_id`, and its schema/rule version. Validate every decoded field; it does not grant access or attest evidence. A follow-up request against a changed snapshot is an explicit stale-snapshot refusal (no automatic latest-snapshot restart). If an I3 cap stops publication **partway through an internal I2 page**, emit a cursor at the last **fully presented** candidate (`after_id` can resume there) and re-evaluate the not-yet-presented candidates on the next same-snapshot request. Advancing beyond an individually oversized candidate is permitted **only** if I3.1 chooses the §7 explicit-refused/unknown-entry policy and emits that candidate's identity and reason; otherwise refuse without a non-progress cursor. No candidate can silently disappear. Continue in v2 ID order, never page by display name, qualified-positive-only rows or unstable database iteration order.

**Critical grouping boundary:** a single caller Workload/Operation may have v2 contributions on both sides of **either I2's candidate-page boundary or any I3 presentation cap** (Workloads, memberships, pairs or evidence). I2 marks a truncated I2 page's assertion lineage incomplete; I3 SHALL preserve that flag and **add its own incomplete-group/lineage status when an I3 cap splits the evaluated inventory even if I2 reports `truncated=false`**. It may use a bounded multi-page, one-snapshot accumulator if separately proven, **or** expose explicitly provisional page-local groups with a continuation. It SHALL NOT call a group complete, compare its omissions as negatives or compute a final evidence union until every relevant candidate has been evaluated under the same snapshot. An exact selected-locality comparison that cannot establish the required complete evaluated inventory—or whose requested Workload falls beyond any applicable cap—must return `PARTIAL`/incomplete (or a typed refusal), never a confident difference, absent Workload or absent dependency.

A response declares precisely whether the **evaluated inventory/page**, **selected-locality groups** and **requested comparison** are complete, partial or not established. "Complete" never means the architecture or the network was completely observed.

## 8. Operation → unique provider Service projection

I1 §5.1 fixes the semantics; I3 freezes the response shape and bounds. The original fact stays canonical **caller Service —CALLS→ provider Operation**. I2 qualifies it per exact Operation; I3 SHALL resolve that Operation's **unique canonical owning provider Service** from the same selected, accepted source/identity state. Never infer ownership from an Operation display name, HTTP URL alone, runtime target placement, or Service-level DEPLOYED_AS. Missing/ambiguous owners produce an explicit unresolved Operation entry; they do **not** mint a provider-Service dependency.

**[I3 proposal — positive group identity]** One presentation group for:

~~~text
(subject Service, exact captured caller Workload identity,
 provider Service, environment, whole-day window, selected snapshot)
~~~

Its sorted members are the **distinct canonical Operation IDs** which individually have an I2 positive assessment and that exact provider owner. For each member retain its own CONFIRMED/OBSERVED_ONLY, assertion ID, assessment instance ID, distinct applicable v2 IDs, exact-operation declaration IDs, selected source revisions, derived rule versions and limitations. Group evidence is the **deduplicated union** of its member evidence, not a new qualification input. A provider group may contain both CONFIRMED and OBSERVED_ONLY Operations; do not mark the entire provider "CONFIRMED" by pooling unrelated declarations.

**[I3 proposal — group qualification presentation]** Prefer listing the per-Operation qualification and a deterministic **set of observed member statuses** rather than inventing a new shared qualification enum. If a concise group label is required, freeze it as a **presentation-only summary** (including a MIXED representation), never as an input to the shared qualifier or proof that every provider Operation is confirmed. Missing ownership and incomplete group membership are separate from qualification.

One provider may own two different Operations reached in the same caller Workload. They form **one** provider presentation group with **two** independently qualified members and a union of distinct IDs; do not count two provider dependencies. A valid Operation in W1 does not qualify the same provider in W2 without independently applicable v2 there. Scope stays the **caller**; target_runtime_scope remains UNKNOWN.

## 9. Deterministic Current-State projection and completeness

Projection selects the positively applicable I2 Operation assessments **without changing their semantics** and combines them only where exact group identity and provider ownership match. Every output must show:

| Concept | Required semantics |
|---|---|
| requested_scope | Exact caller and requested context, source/Workload filters |
| evaluated_inventory | Actual snapshot, candidate/source pairs examined, bounds and revisions; counts never imply unseen rows were examined |
| included | Positively established Workload-local Operation assessments and uniquely resolved provider groups |
| excluded | Known explicitly requested or evaluated entries found inapplicable **with reason**, not silently filtered away |
| unresolved/unknown | Owner conflicts, capture disappearance, unsupported inputs, unscanned candidate remainder, unproved target scope |
| coverage | LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE and no assertion of full Workload traffic |
| projection_completeness | Relative to **the specified evaluated inventory and selection**, with explicit truncated/continuation and group-lineage completeness |
| derivation | Exact I2 assertion/instance refs, admission/qualification rules, source/capture evidence and one snapshot/model revision |

For no v2 records, return a bounded insufficient-evidence answer: no positive local dependencies and no inferred absence; do not infer legacy-only history from merely missing v2 (I2 D8). Do not claim that an empty but complete evaluated v2 page proves *no* dependencies, globally or in one Workload. I1's unsupported relation, unsupported dimension, missing local coverage and I2's no-cover limitation remain distinct.

The projection is a **Current-State** selection, not an Intent assessment. Connecting two positive local edges across Workloads does not establish an end-to-end causal path. Deployment evidence may support caller identity resolution; it does not create a CALLS fact.

## 10. Optional selected-locality comparison

**[I3 proposal]** Compare **two exact captured caller Workload identities** for the same canonical caller Service, environment, whole-day window, source-selection rule and snapshot. If `caller_localities` is present, `compare` MUST select a subset of it; if absent, enumeration remains unfiltered and the requested two Workloads are compared **within that one evaluated inventory**. Both are drawn from the same evaluated inventory, never two independent latest-snapshot requests. Reject a selection that lacks an exact identity or capture authority; do not name-match two similarly labelled Workloads or merge UID incarnations. If a requested Workload has not yet been evaluated because of a page/presentation cap, return incomplete comparison with continuation or typed refusal—not “missing” or a final difference.

Compare the **sets of positively established** (provider Service, canonical Operation, qualification) memberships and their assessment/evidence lineage. Report separately: positive relations in both; positive in the first evaluated scope; positive in the second; same Operation with different observed qualification; and any incomplete/unknown side. The labels mean **"positively evidenced here"**, never "absent there" or "exclusive to one deployment."

A positive W1 call to pricing and an unresolved/missing W2 observation is **not a proven W1-versus-W2 contradiction**. A changed C1 → C2 capture must either be consistently selected before/after the change under the corresponding snapshot or produce an explicit stale-snapshot refusal; I3 must not quietly recreate old owner chains or compare a C1 page with a C2 page.

For any truncated candidate page, missing owner, unknown capture, or partial selected group, the comparison carries an explicit incompleteness marker. Sorting and duplicate handling are deterministic: exact Workload identity, provider Service ID, Operation ID, assertion ID and source/revision, with no display-name primary keys.

## 11. Public response, versioning and refusal shape

**[I3 proposal — public contract; names illustrative until frozen]** Add a typed ServiceDependenciesByLocalityData payload containing:

~~~text
request_context:
  subject_service_id, environment, first_day, last_day
  relation_type = CALLS; optional operation/provider/source/Workload selection
snapshot:
  snapshot_id, model_revision
inventory:
  examined_v2_count, examined_pair_count, capture sources/revisions
  candidate_summaries with all admitted source-pair dispositions
  included_localities, excluded/inapplicable, unresolved/conflicting, unknown
  bounds, truncated, next_cursor, completeness_relative_to_inventory
localities[]:
  captured caller Workload identity (cluster UID, namespace, kind, UID)
  positive Operation assessments with I2 identity and lineage
  uniquely resolved provider Service groups with per-Operation qualification
  UNKNOWN target runtime scope, LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE
comparison:
  selected Workloads; positive overlap/differences; unknown/partial flags
evidence_refs:
  scoped v2, declaration, capture/owner refs with distinct typed provenance
limitations:
  stable codes and unchanged I2 phases; no negative inference
~~~

**Versioning decision:** existing ArchitectureAnswer public schema_version **0.5** and the current three-tool request/claim enums are closed. They cannot simply accept a fourth tool name, a new local claim variant, or v2 evidence records by pretending the old 0.5 schema is unchanged. Propose a **new locality-specific 0.6 schema** with its own published request/response JSON Schemas and validator, preserving the established producer/snapshot/outcome/limitations discipline. A code-level reuse of ArchitectureAnswer requires explicitly reviewed widening and backward-compatibility tests; **do not force scoped Operation assertions into existing unscoped DependencyClaim/DeploymentClaim semantics**. Published schema version and producer build version are separate.

Use existing ANSWERED/PARTIAL/NOT_ANSWERED **envelope outcomes** for transport-level answerability; carry I2's APPLICABLE/INAPPLICABLE/UNRESOLVED/CONFLICT/UNSUPPORTED/INSUFFICIENT_EVIDENCE **locally**, not as interchangeable envelope statuses. Freeze the rules for mapping truncation, validation, unknown Service, no-v2, stale snapshot, no-cover, selected-source and selected-Workload refusals to the envelope/REST/MCP behavior. A valid partial answer has explicit payload and limitations, never falsely exhaustive success. No local NOT_OBSERVED_IN_WINDOW; no unearned LOCALITY_LEGACY_V1_UNSCOPED.

**Contract-first test:** validate serialized service responses against the exact published v0.6 schema before checking either REST or MCP; strict extra-field rejection and sorted/deduplicated identity arrays are mandatory. Existing v0.5 schemas/route behavior remain unchanged unless separately versioned and reviewed.

## 12. Same-snapshot scoped-evidence drill-down

I2 D1 intentionally isolates ScopedObservedCallV2 from the legacy Evidence label, relation arrays, approved NL labels, public evidence resolver and legacy get_evidence lookup. I3 SHALL NOT bypass that isolation by expanding the old resolver's Cypher or exposing raw graph records.

**[I3 proposal — resolver]** Add one service-owned, bounded read path which resolves **exact scoped v2 evidence refs returned by a locality answer** under the **same supplied snapshot_id** and caller/Operation/source authority constraints. It may also return sanitized linked declaration/capture/owner references through existing authorized lookup functions, but must not reinterpret a scoped record as legacy Evidence or add it to old evidence arrays. A lookup after a changed snapshot returns an explicit stale/unavailable refusal, not latest data.

Each returned scoped record contains only admitted public fields and provenance needed to substantiate the answer: v2 ID, original caller cluster/Pod UID, canonical caller/Operation, UTC-day and relevant first/last observed timestamps, bounded sample trace IDs where allowed, source mode/revision references, and the evidence's identity/normalization rule. Omit raw spans, arbitrary OTel Resources, credentials, host/IP inference and unqualified target placement. Preserve the distinction between v2 event attribution and query-time Workload resolution. Evidence lookup must not recompute an independent digest, an ownership fact, or an architecture claim.

**Fourth-tool budget proposal:** expose drill-down as a **bounded second request mode on the new get_service_dependencies_by_locality MCP tool**, with a dedicated REST subroute if useful; this prevents quietly creating a fifth public tool or widening the legacy get_evidence contract. The mode is a reviewed discriminated request union (query vs exact evidence lookup), not an arbitrary graph query. A different fourth-tool design is acceptable only with documented semantic equivalence and the parent §17 review. Freeze exact mode names, ID/ref partition, refusal and routing before code.

Test v2-positive, no-v2, stale snapshot, mismatched caller/Operation, unsupported ref, 20-ref boundary, cross-source limitations and negative attempts to fetch v2 via legacy APIs/NL. Existing v0.5 evidence resolution remains byte/semantic compatible.

## 13. Service, REST and negotiated MCP parity

**[I3 proposal — surface decision pending review]**

| Surface | Proposed operation | Boundary |
|---|---|---|
| Semantic service | ArchitectureIntelligenceService.get_service_dependencies_by_locality(request) | Sole source of enumeration, grouping, comparison, dispositions and lineage |
| Semantic service | ArchitectureIntelligenceService.resolve_scoped_locality_evidence(request) | Sole snapshot-bound scoped resolver, sharing authorized I2 reads |
| REST | POST /api/services/{service_id}/dependencies/by-locality | Typed bounded request body; response is exact versioned service answer |
| REST scoped lookup | POST /api/services/{service_id}/dependencies/by-locality/evidence | Exact ref+snapshot request, not the existing unscoped evidence endpoint |
| MCP | get_service_dependencies_by_locality | **Proposed fourth read-only tool**, query/resolver modes; negotiated transport, one typed request argument |
| Existing MCP | get_architecture_drift, get_evidence, get_service_dependencies | Unmodified 0.5 meanings and existing tool contracts |

**Proposed MCP description:** Discover evidenced caller-Workload localities and return positively established HTTP dependencies per locality, with optional same-snapshot comparison. The results are **not** an exhaustive partition of all Service dependencies: missing relationships do not establish local absence. Unknown, unresolved, excluded and unscanned items remain explicit. In the proposed second request mode, the same tool resolves exact scoped evidence refs under the supplied snapshot without widening legacy `get_evidence`. Tool name, modes and route are still I3.1 freeze decisions.

Why POST is proposed: typed exact selections/cursors/filters and bounded explicit v2 refs do not fit comfortably into long GET query parameters. This remains an **[I3 proposal]**, not a frozen route or tool-count commitment. Parent §17 permits an equivalent compatible extension of three tools only through a reviewed decision proving the same public question and drill-down; the default proposal is one fourth tool, not generic graph traversal.

Adapters perform argument parsing, validation and transport error mapping only. They SHALL call ArchitectureIntelligenceService once per semantic operation and return the service-owned claim/limitation semantics **unchanged**. Direct service, REST and negotiated MCP against the **same inputs and snapshot** must have equivalent normalized payload, identity, evidence refs, inclusion/exclusion, page boundary, qualification, coverage and comparison; MCP wrapping and HTTP status are transport differences only.

Freeze exact HTTP status mapping for syntax-invalid requests, semantic refusals, snapshot mismatch and internal SnapshotUnstable. MCP advertises closed input/output schemas and read-only annotations, rejects unexpected arguments before dispatch, and uses existing guard and negotiated-session behavior. A fresh independent MCP client must discover exactly the reviewed tool set, execute both modes (if adopted), reconnect and obtain the same answer semantics.

No public write path, LLM-chosen graph query, authorization bypass, implicit current-state fallback or agent-assembled claim is allowed.

## 14. Independent qualification, security and observed cost

Author I3's **public expected outputs independently of the new I3 projection/serialization code**, using I1's frozen contract, I2's pre-committed real-rehearsal expected answers and separate negative fixtures. Do not generate expected outputs from the implementation being tested, or rewrite I1's oracle. The rehearsal is a reproducible I3 test input, **not** independent I5 real-system qualification.

| Test case | Required assertion |
|---|---|
| Two actual caller Workloads | C1 produces separate evidenced localities from one Service, with O1 CONFIRMED and O2 OBSERVED_ONLY; target runtime UNKNOWN |
| Same provider, two Operations | One provider Service presentation group with two distinct Operation members and exact deduplicated evidence; no declaration pooling |
| Missing/ambiguous provider | Operation assessment remains visible as unresolved ownership; no provider dependency minted |
| No v2 / refused attribution | No positive local result or false legacy-only/absence claim; v0.5 unchanged |
| Wrong day / environment | L10b/L17d remain phase-3 inapplicability, not an empty prefiltered set |
| Two captures / source selection | Explicit/current revision vs implicit proven covering source; unrelated namespace omitted; actual covering-source missing Pod retained; conflicting sources not silently preferred |
| Pod churn C1 → C2 | Original v2 preserved, missing old owner chain UNRESOLVED; snapshot/lineage changes; no name-based reassignment |
| Complete and incomplete inventory | Every admitted pair represented; item counts accurate; same snapshot, deterministic sorted output; unknown remainder visible; explicit stale selector and implicit no-cover retain D13.3's **same I2 disposition** |
| I2 page or I3 presentation cap splits Workload group | Partial lineage and `PARTIAL`/refusal even when I2 `truncated=false`; safe cursor from the last fully presented/accounted-for v2 ID; a **single oversized candidate** follows the reviewed I3.1 refusal-or-explicit-unknown policy without silent data loss or a false positive |
| Selected comparison | Both selected Workloads exact; `compare` is a subset of `caller_localities` when filtered, otherwise uses the unfiltered evaluated inventory; an identity beyond the cap means incomplete/refusal, never absence; positive overlap/difference only |
| Unsupported scope/relations | Sub-day, messaging, region, tenant and unsupported dimension/ref refusals; no invented local absence |
| Scoped drill-down | Same snapshot, authorized exact v2 refs, bounded fields; legacy evidence/NL reads do not leak isolated v2 |
| API and schema parity | Service/REST/negotiated MCP normalized result identical; published versioned schema validated; three old tools unaffected |
| Replay and permutation | Identical request/evidence/source order permutations yield identical semantic bytes and IDs under the same graph snapshot |
| Regression and isolation | Golden no-v2 pin, old service/drift/deployment/evidence and Pub/Sub semantics unchanged; zero graph writes |

The independent evaluator SHALL consume the semantic service directly; adapter parity tests separately prove the wire contract. I4 later reruns the frozen matrix across **two clean complete states** and qualifies the exact final candidate. I3 tests do not self-certify I4/I5.

**Safety/read cost:** I2 measured per-Pod v2 growth and nonconstant snapshot/local-assessment read costs at 0/100/1000 Pods; that single recorded host/run is a baseline, **not** an SLO or a production scale proof. I3 must log bounded internal/public counts, number of source pairs, number of localities and provider groups, cap/refusal frequency, revision retries and time spent in candidate read, owner lookup, projection, serialization and evidence lookup. Benchmark high-Pod-churn with fixed Workload count; verify bounded work and honest truncation before publicly enabling the route. Do not invent performance thresholds, cache cross-snapshot results or quietly implement ADR 0012 compaction.

The known, separately tracked NL-to-Kubernetes-Evidence exposure (#323) is **not** resolved by this I3 feature; do not widen it. Keep private v2 inaccessible to all old public readers even if the new scoped resolver is added.

## 15. I3 slices and exit evidence

| Slice | Bounded delivery | Required exit artifact |
|---|---|---|
| **I3.1 — Reviewed public contract freeze** | Decide tool vs compatible extension, query/response/schema version, source/workload selectors, bounds, continuation, page-boundary semantics, provider qualification presentation, comparator, scoped resolver and status mapping; keep parent and I2 frozen | Accepted I3 decision record, published *draft* JSON schemas and independently written positive/negative expected-answer matrix **before** semantic code |
| **I3.2 — Internal projection and inventory** | Under ArchitectureIntelligenceService, reuse I2 and implement unique Operation owner mapping, exact Workload group, inventory/exclusions, stable bound and same-snapshot comparison | Real-Neo4j positive + negative + 500-boundary tests, scope/capture churn regression, lineage and no-v2 pin |
| **I3.3 — Scoped resolver and public adapters** | Snapshot-bound ref lookup; REST and reviewed fourth MCP tool (or explicitly approved equivalent); versioned schemas, deterministic serialization | Same-snapshot cross-surface tests, independent MCP client discovery/call/reconnect, resolver no-leak tests and preserved three-tool compatibility |
| **I3.4 — Qualification and I4 handoff** | Freeze fixture/expected results, cost observations, exact tested HEAD, status/limitations/known findings; hand off independent final-candidate truth tables | I3 completion record with tests and failures/skips, reviewed source/version/route/tool map, independently authored I4 test inputs |

Slices may be split or regrouped if the accepted semantics, test order and one-snapshot rules are preserved. Do not optimize for administrative slices at the expense of an executable end-to-end user question. All major contract choices precede code and self-confirming fixtures; review-driven changes record their rationale.

## 16. Definition of Done and I4 handoff

I3 is complete only when all of the following have **executed evidence**, not assertions in prose:

1. An ordinary client can ask **where** a canonical caller Service's direct HTTP CALLS are positively established, for explicit environment/whole-day context, **without giving caller Workload identities first**.
2. The answer enumerates the actual bounded evidenced-candidate/source inventory, all admitted pair results, positive included Workloads and reasoned nonpositive candidates; unscanned or unrelated capture inventory never becomes "no Pod"/"no dependency."
3. Exact source/revision and Workload-UID selection respects I2 phase, temporal, no-cover and conflict rules; C1 and C2 are never silently interchanged or reconstructed.
4. Each Operation retains its own I2 assertion/assessment identity, CONFIRMED/OBSERVED_ONLY status, v2/declaration/capture refs, UNKNOWN target placement and LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE.
5. Unique provider Service ownership is proved under the same snapshot; distinct Operations for one provider group without pooling unrelated qualification; missing/ambiguous owner stays an explicit limitation.
6. Public result schema defines explicit requested/evaluated/included/excluded/unresolved/unknown scopes, actual caps, truncated candidates, group-lineage completeness and deterministic ordering. Both I2 candidate-page truncation **and I3 presentation caps** mark affected group/assessment lineage incomplete; indivisible over-limit source-pair candidates receive the reviewed I3.1 **fail-closed or explicitly accounted-for unknown** disposition, never silently dropping a candidate or fabricating a qualified result. A split page cannot be presented as an exhaustive group or comparison.
7. Two exact selected caller localities can be compared under **the same snapshot**; comparison targets must be within an explicit `caller_localities` filter when supplied, or within the unfiltered evaluated inventory otherwise. A target beyond any cap yields an incomplete/refused comparison, without negative/exclusive/global/causal claims or comparing a historical C1 view to a current C2 view.
8. A returned scoped-v2 evidence ref has a bounded, sanitized **same-snapshot** resolver; legacy get_evidence/REST, graph/NL and old dependency claims remain isolated from v2, with negative tests.
9. One reviewed, versioned new public contract is reachable through ArchitectureIntelligenceService, REST and negotiated MCP. The final tool count and exact routes are frozen and independent schema/client checks agree on semantics. Old schemas and three tool meanings remain compatible.
10. No-v2 canonical snapshot/golden pins, legacy relations/dependency/drift/deployment/Pub/Sub, v1 counts and source-capture qualification remain unchanged. The D16 flag default is **not flipped by I3**.
11. Bounded high-Pod-churn reads and cap/refusal behavior are measured, with no invented SLOs; exact HEAD CI, unit, integration, security and schema results (including failed/skipped) are recorded.
12. An I3 completion record reconciles proposals against accepted decisions and changed implementation, plus outstanding limitations, deferred work, reproducible commands, merged SHAs and **I4 handoff**. The independently captured **I5 remains NOT_RUN**, regardless of passing I3 rehearsal replay.

**Handoff to I4:** versioned public schemas; service/REST/MCP routes and final tool count; exact positive and negative expected-answer fixtures and provenance; selected C1/C2/replay identity; unique-owner and mixed-Operation truth tables; complete-vs-partial enumeration boundaries; selected-locality comparison and stale-snapshot negatives; scoped resolver access/lineage checks; no-v2/v2 fingerprint pins; cross-surface normalization procedure; measured cardinality/read cost; and every deferred requirement. I4 must compare repeated clean-state results independently, not treat an I3 test run as its own final-candidate qualification.

## 17. Items requiring explicit owner review before implementation

The accepted parent and completed I2 do **not** themselves select the following public I3 details. These are **proposals**, not silently decided facts:

1. **Public exposure and tool count:** one new read-only get_service_dependencies_by_locality tool versus a proven equivalent extension of the three existing tools; exact REST route/method and whether the fourth tool has a separate scoped-evidence lookup mode. A fifth tool requires independent approval.
2. **Versioning:** new locality-specific 0.6 request/result schema vs widening the 0.5 ArchitectureAnswer and its closed claim/tool enums; migration and existing-client compatibility. Do not equate versioned schema and producer version.
3. **Inventory and selectors:** exact request vocabulary, captured Workload UID representation, source-selector behavior, owner-unresolved presentation, and whether a provider filter changes only projection rather than candidate admission.
4. **Continuation and budget:** public page/candidate/pair/group caps, safe fan-out preflight or smaller I2 read batches (maximum still 500), stable cursor format/validation, incomplete cross-page **and I3 cap-induced** Workload grouping, the **oversized-candidate liveness policy** (fail closed vs explicit refused/unknown entry with advancing cursor and visible incomplete inventory), and the rules for honestly refusing incomplete comparison.
5. **Provider projection:** unique canonical Operation owner lookup, exact group/Operation identity and bounded evidence union, mixed-qualification presentation and missing/ambiguous-provider result.
6. **Completeness and comparison:** what counts as evaluated/included/excluded/unknown relative to named inventory/revisions; `compare` subset/selection behavior and targets beyond caps; precise ANSWERED/PARTIAL/NOT_ANSWERED versus I2 dispositions (especially D13.3's intentionally merged zero-cover cases); no unsupported absence.
7. **Same-snapshot scoped resolver:** safe authorized v2 record fields, source/caller checks, method/ref bounds, route/tool packaging and stale-snapshot refusal; no change to legacy Evidence visibility.
8. **Cost and qualification evidence:** selected initial caps measured against I2 churn data, independently authored I3 public expected outputs, exact transport parity, and separate I4/I5 responsibilities.

**Stop condition:** do not publish a positive local claim from name matching, a Service-level deployment map, a legacy v1 daily bucket or a rejected/stale capture; do not erase phase-3 mismatches with early filtering, silently omit a covering-source limitation, roll all Workload incarnations together, promote a mixed Operation group to CONFIRMED, treat a truncated page or unknown locality as complete/absent, merge C1 and C2 under different snapshots, introduce a separate fingerprint or public graph bypass, or change v0.5 semantics. Resolve material disagreement by a reviewed specification amendment **before** changing independently authored expectations.
