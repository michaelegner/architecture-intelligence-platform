# AIP v0.6.0 I1 — Locality Support Matrix

**Status:** I1 supporting deliverable. Slice I1.1 (§§1–9: baseline inventory, role vocabulary and applicability matrix) was accepted in PR #307. Slice I1.2 (§§10–16: CLIENT field allowlist, UTC-day window and phase-gated disposition contract) is under review. Contract freeze artifact under review; it claims no implementation and no executed conformance.  
**Release / increment:** `v0.6.0` — Locality-Aware Current State / I1  
**Governing specification:** [I1 — Locality and Evidence Applicability Contract](i1-locality-and-evidence-applicability.md) (accepted, [PR #283](https://github.com/michaelegner/architecture-intelligence-platform/pull/283), merge `aafb03d5735d78b2741a3dc8a2d0336079535ed6`), under the [accepted v0.6.0 parent](specification.md) (PR #278, merge `be26edcd133edc8576a85d301be33b836335c41b`).  
**Code baseline inspected:** `main` at `77479c107ddc719e465cf6827c4bedd18afea8bd`. Every `file:line` reference below is to that commit.  
**Internal contract identifier:** `locality-contract/1` (I1 §4.1). This identifies the internal semantic contract, not the future public I3 JSON schema version.

This document restates **no new semantics**. It freezes, in tabular and reviewable form, what the accepted I1 specification already decides, and records the verified current code baseline those decisions build on. Where this document and the I1 specification appear to disagree, the I1 specification wins and this document is defective. Later I1 slices extend this document (I1.2: CLIENT field allowlist, UTC-day window normalization and the phase-gated disposition table) or add sibling deliverables (I1.3 v2 evidence contract, I1.4 capture runbook, I1.5 conformance dossier and completion record).

---

## 1. Baseline inventory (I1 §2, slice I1.1)

The table verifies each I1 §2 baseline claim against the code and adds the facts I2 must not overlook. "Consequence" is the constraint that follows from the accepted I1 contract; it is not an additional rule.

| # | Mechanism (at `77479c1`) | Verified current behaviour | Consequence under the accepted I1 contract |
|---|---|---|---|
| B1 | [`app/canonical/ids.py`](../../../app/canonical/ids.py):39 `observed_evidence_id` | ID is `evidence:otel:{environment}:{YYYY-MM-DD}:{h}` where `h` is the first **12** hex characters of SHA-256 over the UTF-8 seed string formed by joining `subject_id`, `relation_type` and `object_id` with a literal pipe character (see the note below this table). No Pod, cluster, trace or span component. | **The v1 attribution gap:** a v1 bucket cannot distinguish caller Pods or clusters. v1 stays byte-unchanged; caller attribution requires the separate v2 identity (I1 §7). |
| B2 | [`app/telemetry/correlation_buffer.py`](../../../app/telemetry/correlation_buffer.py):9 `PendingHttpSpan` | Fields: `trace_id, span_id, parent_span_id, span_kind, service_name, service_namespace, service_version, environment, method, route, target_identity, timestamp`. **No `k8s_*` or cluster field.** | I2 must extend the transient carrier with the admitted CLIENT identity (I1 §6.1). Without that, cross-batch pairs cannot produce v2. |
| B3 | `HttpCorrelationConfig`, [`app/settings.py`](../../../app/settings.py):57; buffer `sweep_expired`/eviction, `correlation_buffer.py`:78–94 | TTL defaults to 60 s, measured from **wall-clock insertion time**. The size bound defaults to 10 000. TTL-expired spans are returned by `sweep_expired()`. Size-evicted spans are only counted in `evictions` and otherwise **dropped silently**. | The existing TTL and size bounds are preserved (I1 §6.1). A size-evicted CLIENT yields neither v1 nor v2 today; this contract does not change that. |
| B4 | [`app/telemetry/adapter.py`](../../../app/telemetry/adapter.py):234 `correlate_http_call_observations` | Pairing: SERVER is keyed `(trace_id, parent_span_id)` and CLIENT `(trace_id, span_id)`, in batch and across batches (`offer_server` at `correlation_buffer.py`:96, `offer_client` at :115). An expired CLIENT can become a `CLIENT_ONLY` fact (`adapter.py`:393). An expired SERVER **always** becomes `UnresolvedObservation(missing_caller_identity)` (`adapter.py`:402–426). | `SERVER_ONLY` produces no CALLS fact today, so it can produce neither v1 CALLS nor v2 (I1 §6.1, L09). `CLIENT_ONLY` may become v2 only if its CLIENT identity survives (I1 §6.1). |
| B5 | `adapter.py`:256–262 (docstring) and :311–314 | On the paired path (in-batch and cross-batch), environment, method, route and fact timestamp (`server.end_time`) all come from the **SERVER** span. The CLIENT supplies only `source_service_version`. **The CLIENT environment is never compared with the SERVER/fact environment.** | Preserve the SERVER-sourced route/method/timestamp (I1 §2, §6.1). Ingestion guard (3) (CLIENT environment == accepted fact environment, I1 §6.2) is a **new, v2-only** check and does not alter v1 acceptance. |
| B6 | [`app/telemetry/otlp_receiver.py`](../../../app/telemetry/otlp_receiver.py):46 `_resource_identity` | The only Resource reader. It reads exactly `service.name`, `service.namespace`, `service.version`, `service.instance.id`, `deployment.environment.name`, `k8s.pod.uid`, `k8s.pod.name`, `k8s.namespace.name`, `k8s.cluster.uid`, `k8s.deployment.name`, `k8s.statefulset.name`, `k8s.daemonset.name`. | All CLIENT fields the I1 contract needs are already read by the receiver; nothing wider may be admitted (I1 §6.2(5), §11.4). The exact allowlist is frozen in slice I1.2. |
| B7 | `otlp_receiver.py`:66 `_to_datetime`; [`app/telemetry/model.py`](../../../app/telemetry/model.py):69 `day_bucket` | Span times are `datetime.fromtimestamp(unix_nano / 1e9, tz=UTC)`, which gives microsecond precision after float conversion. `day_bucket` truncates to a calendar day in the timestamp's own `tzinfo`; it is UTC in practice because the receiver emits UTC. | The event-instant precision and UTC-day assignment are frozen in slice I1.2 (I1 §8). |
| B8 | [`app/telemetry/runtime_identity.py`](../../../app/telemetry/runtime_identity.py); `RuntimeIdentityObservation`, [`app/provenance/model.py`](../../../app/provenance/model.py):71 | A per-Service/Pod/day observation, derived from **any** span with `service.name`, `k8s.pod.uid` and environment. It is independent of any individual relationship. | It is **Path C input only**. It never attributes a CALLS to a Pod (I1 §2, §5; L05, L26). |
| B9 | [`app/architecture_intelligence/deployment_projection.py`](../../../app/architecture_intelligence/deployment_projection.py):677 `_observation_context_limitation` | In order: missing environment gives `DEPLOYMENT_EVIDENCE_INCOMPLETE`; environment mismatch gives `DEPLOYMENT_ENVIRONMENT_MISMATCH`; `window_start <= last_seen <= window_end` is inclusive; then `window_start <= capturedAt <= window_end` is inclusive, and an unparseable or missing `capturedAt` gives `DEPLOYMENT_TEMPORAL_MISMATCH`. | I1 §8 reuses this **exact inclusive predicate**, fed with the v2 bucket's own `last_seen` and the matching Pod capture's `capturedAt`. v0.5 Path C itself is unchanged. |
| B10 | `deployment_projection.py`:628 `_consistency_attributes_agree`, :658 | Cluster UID is checked only here, as `obs.k8s_cluster_uid is not None and obs.k8s_cluster_uid != pod.cluster_uid`. A **missing** observation cluster UID counts as agreement. | This lenient v0.5 rule is **not** the v2 rule. v2 requires a non-empty CLIENT `k8s.cluster.uid` at ingestion (I1 §6.2(2)) and exact equality with the envelope `clusterUid` at query time (I1 §4.2, §9; L16). v0.5 behaviour is unchanged. |
| B11 | `DeploymentResolutionStatus`, [`app/architecture_intelligence/contracts.py`](../../../app/architecture_intelligence/contracts.py):598 | `RESOLVED_EXPLICIT`, `RESOLVED_CONFIGURED`, `RESOLVED_OBSERVED`, `CONFLICT`, `AMBIGUOUS`, `UNRESOLVED`. | The locality dispositions preserve the distinct Path C meanings of `AMBIGUOUS` and `CONFLICT` (I1 §9, §10.1; L19). |
| B12 | [`app/sources/kubernetes_envelope.py`](../../../app/sources/kubernetes_envelope.py):206–216; [`app/sources/kubernetes_mapping.py`](../../../app/sources/kubernetes_mapping.py):44; [`app/sources/kubernetes_owner_chain.py`](../../../app/sources/kubernetes_owner_chain.py):186 | `metadata.capturedAt` is **envelope-wide**; there is no per-resource capture time. `source.clusterUid` and `source.mode` ∈ {`DECLARED_MANIFEST`, `CAPTURED_RESOURCE`}. Supported Workload kinds are Deployment, StatefulSet and DaemonSet. Owner chains are Pod→ReplicaSet→Deployment, Pod→StatefulSet and Pod→DaemonSet. | `capturedAt` is the capture's time, not continuous Pod presence (I1 §8–9). One Deployment rolling across two ReplicaSets is **one** Workload (I1 §2.1, §12; L33). |
| B13 | [`app/qualification/declared_observed.py`](../../../app/qualification/declared_observed.py):25–27, :58 | The statuses are `CONFIRMED`, `OBSERVED_ONLY` and `NOT_OBSERVED_IN_WINDOW`. Observed matching requires exact environment and an inclusive `last_seen` window. Declared evidence ignores environment and window. | This remains the single qualification owner (ADR 0010). Local `NOT_OBSERVED_IN_WINDOW` is unreachable and forbidden (I1 §5). |
| B14 | [`app/architecture_intelligence/repository.py`](../../../app/architecture_intelligence/repository.py):53, :344; [`examples/release-golden-path/expected.json`](../../../examples/release-golden-path/expected.json):45 | `_CANONICALIZATION_VERSION = 3`. The snapshot ID is `aip:snapshot:v1:` plus the full SHA-256 of sorted-key canonical JSON of the state. The frozen golden pin is `aip:snapshot:v1:0bfcbdeda363876559bb78f53e432f1a73c368e9fbd4d21c37f8f4335ecdbd5f`. | With no v2 records, the bytes, the version and this pin must stay identical (I1 §11.1; L13). The conditional v2 contribution is frozen in slice I1.3. |

**B1 seed literal.** The hashed v1 seed is exactly the following (it is written outside the table so that no Markdown pipe escaping appears in it):

```text
subject_id|relation_type|object_id
```

Here `|` is the literal U+007C separator and there are no backslashes (`f"{subject_id}|{relation_type}|{object_id}".encode()`, `ids.py`:45).

---

## 2. Role vocabulary (I1 §4.1)

The six roles are **independent even when their values coincide**. No role's value may be copied into another role without its own admissible evidence path.

| Role (contract name) | Answers | Admissible source | Must never be derived from |
|---|---|---|---|
| `RequestedScope` | What the caller asked about: question, environment, whole-UTC-day window, optional later I3 locality selection | The request | Evidence. A request is not evidence. |
| `SourceCaptureScope` | What a source is known to cover: source instance/revision, admitted inventory, evidence mode, `capturedAt` | The source's accepted inventory and envelope | Timeless presence. A capture is not continuous state. |
| `CallerRuntimeScope` | Where the caller side of **one individual** accepted CALLS ran (cluster UID, Pod UID, then, after query-time resolution, namespace and Workload) | The actual CLIENT span's Resource, carried with that interaction | Same-Service Pod co-occurrence, SERVER Resource, `DEPLOYED_AS`, display names |
| `TargetRuntimeScope` | Where the target ran | Only separately evidenced target runtime placement | The caller's scope, or the logical Operation owner. **Unknown by default** (L20). |
| `ClaimApplicabilityScope` | Where the precise assertion is supported | The derivation of that assertion from its inputs and rule | Anything broader than its inputs |
| `ProjectionSelectionScope` | Which candidate localities a later I3 answer evaluated, included or excluded | The I3 projection | Source evidence. Filtering is not evidence. |

## 3. Internal contract types (I1 §4.3)

The field sets below are frozen as **internal** types of `locality-contract/1`. They are not public API, storage labels or the I3 wire schema. The `V1` suffix versions *the type*, not the v1 observed-evidence generation (I1 §2.1).

| Type | Fields (I1 §4.3) | Semantic boundary |
|---|---|---|
| `LocalityDayContextV1` | `environment`, `first_utc_day`, `last_utc_day` (inclusive date range), `requested_dimensions` (admitted only), `selected_snapshot_ref` | An **observed Current-State evidence window** (§6 below). |
| `CallerAttributionV1` | `subject_service_id`, `relation_type` = `CALLS`, `object_operation_id`, `accepted_fact_environment`, `accepted_fact_timestamp`, `client_environment`, `client_timestamp`, `client_cluster_uid`, `client_pod_uid`, `optional_consistency` (admitted allowlist), `normalization_rule` (ID and version) | Retained at **ingestion**, independently of any Workload resolution. It establishes Pod attribution, not Workload locality. |
| `ResolvedCallerLocalityV1` | `attribution_ref`, `selected_snapshot_ref`, `capture_source_revision`, `captured_at`, `cluster_uid`, `namespace`, `workload_ref`, `disposition`, `reasons` (sorted, distinct) | Computed at **query time** against the one selected snapshot. It is never written back into the v2 event identity. |

---

## 4. Evidence × claim-kind applicability matrix (I1 §5, parent §8)

This is the **minimum** matrix. Any claim kind or evidence not listed is not admitted in v0.6 and needs separately reviewed scope, rules and independent tests.

| Evidence | Nature | May support | Cannot support alone | Conformance |
|---|---|---|---|---|
| Accepted OpenAPI Service/Operation declaration | DECLARED | A source- and Service-scoped declared Operation. It may match an **independently observed** local CALLS through the shared qualification owner. | That an event executed in a particular Workload; a region-local declaration; a Workload-authored or Workload-exclusive declaration | L21, L22, L23 |
| Resolved OTel HTTP CLIENT span with actual bounded Resource | OBSERVED | Per-interaction caller **Pod and cluster** identity | A unique owner Workload, or target placement, without captured evidence | L06, L07, L15 |
| Correlated OTel HTTP SERVER span | OBSERVED | The existing resolved provider method, route and fact timestamp | Caller locality from the SERVER Resource | L07, L09 |
| Existing v1 daily CALLS evidence | OBSERVED | The existing Service-level observed relation, coverage and counts | Retrospective Pod or Workload attribution by a Service/time join | L05, L12 |
| `RuntimeIdentityObservation` | OBSERVED | Its own Path C Service/Pod/`DEPLOYED_AS` inputs | Proof that a particular CALLS originated from that Pod | L05, L26 |
| Isolated v2 scoped CALLS record | OBSERVED | A caller-Pod/cluster-specific observed contribution | Positive Workload locality without a compatible capture in the query snapshot | L02, L15, L18 |
| Unique `CAPTURED_RESOURCE` Pod/owner chain | INFRASTRUCTURE capture | The exact captured resource and owner/Workload identity at `capturedAt` | A CALLS edge; timeless Pod presence; an observed action inferred from placement | L15, L18, L27 |
| `DECLARED_MANIFEST` Kubernetes contribution | DECLARED infrastructure | Its own declared infrastructure identity (v0.5 semantics) | Any observed caller-Workload locality: per candidate `UNSUPPORTED` / `LOCALITY_CAPTURE_MODE_UNSUPPORTED` | L17, L37 |
| Configured or explicit `DEPLOYED_AS` | CONFIGURED / DECLARED | Its own source-qualified Service–Workload association | The location of all of that Service's interactions | L26 |
| Operator-authored AsyncAPI overlay | DECLARED | A source-attributable declared messaging claim under v0.5 | Observed Kafka behaviour or local messaging qualification (`UNSUPPORTED` in this slice) | L24 |

### 4.1 Qualification boundary (I1 §5)

| Inputs for one caller-local CALLS against one exact Operation | Shared qualification owner result | Forbidden |
|---|---|---|
| Matching accepted Service/Operation declaration **and** an applicable scoped observed CALLS | `CONFIRMED` | Treating the declaration as Workload-authored or Workload-exclusive |
| Applicable scoped observed CALLS, no matching declaration (or a declaration for a different Service or Operation) | `OBSERVED_ONLY` | Confirming from the wrong Service or Operation (L22) |
| Declaration only, or Service-level coverage only, no applicable scoped CALLS | No positive Workload-local CALLS; `INSUFFICIENT_EVIDENCE` with `LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION` / `LOCALITY_LOCAL_COVERAGE_UNAVAILABLE` | Local `NOT_OBSERVED_IN_WINDOW`, which is unreachable because no Workload-level coverage source is admitted (L23) |

Unscoped v0.5 qualification, coverage and `NOT_OBSERVED_IN_WINDOW` semantics are unchanged.

---

## 5. Locality dimension support matrix (I1 §4.2, parent §6.1)

The **ingestion** column is used only when the original CLIENT/accepted-CALLS input fails a v2 eligibility check. **No v2 record is written.** The specific reason goes only to the bounded, sanitized ingestion diagnostics and the per-source import/migration report (I1 §10.2). It is never a query-visible architecture fact.

The **query** column applies only to a candidate with a retained v2 record. Candidates are evaluated in the §10.1 phase order: (1) request preflight, (2) selected source/evidence mode, (3) environment and time, (4) captured Pod/owner identity. The first terminating phase gives the primary disposition, and later phases are not evaluated.

| Dimension | Status in `locality-contract/1` | Only admissible source | Ingestion failure: diagnostic/report only, no v2 written | Query-time result for a retained v2 candidate (§10.1 phase) |
|---|---|---|---|---|
| `environment` | **Admitted, required** | Accepted fact `deployment.environment.name`. The CLIENT value must be present and exactly equal at ingestion. | CLIENT environment missing: `INSUFFICIENT_EVIDENCE` / `LOCALITY_CLIENT_IDENTITY_MISSING`. Present but different: `INAPPLICABLE` / `LOCALITY_CLIENT_FACT_ENVIRONMENT_MISMATCH`. | Phase 3: the persisted v2 environment differs from the exact query environment, giving `INAPPLICABLE` (exact environment-mismatch limitation). No alias or widening, and owner identity is not evaluated. |
| Whole UTC-day window | **Admitted, required** | The request's inclusive date range. Normalization is frozen in slice I1.2. | CLIENT and fact timestamps not in the same UTC day: `INAPPLICABLE` / `LOCALITY_CLIENT_FACT_DAY_MISMATCH`. | Phase 1: sub-day or partial-day request, giving `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION`. Phase 3: v2 bucket `last_seen` outside the selected days, giving `INAPPLICABLE` / `LOCALITY_OBSERVATION_TEMPORAL_MISMATCH`. |
| Caller cluster UID | **Admitted, required, exact** | Actual CLIENT `k8s.cluster.uid`, which must equal the selected captured envelope `clusterUid` | Missing: `INSUFFICIENT_EVIDENCE` / `LOCALITY_CLUSTER_UID_MISSING`. | Phase 4: differs from the selected envelope `clusterUid`, giving `CONFLICT` / `LOCALITY_CLUSTER_UID_CONFLICT`. The v2 record is retained unchanged (L16, L34). |
| Caller Pod UID | **Admitted as attribution identity only** | Actual CLIENT `k8s.pod.uid` | Missing: `INSUFFICIENT_EVIDENCE` / `LOCALITY_POD_UID_MISSING`. | Phase 4: no matching captured Pod UID in the selected capture, giving `UNRESOLVED` / `LOCALITY_CAPTURE_MISSING_POD`. The v2 record is retained unchanged (L18). |
| Capture revision/time | **Admitted, required** positive prerequisite (I1 §4.2) | An identified, admitted **selected** `CAPTURED_RESOURCE` contribution with its source instance/revision and a real, parseable envelope `capturedAt`. `capturedAt` is evidence of that capture, not continuous or timeless Pod presence (I1 §8–9, B12). | Not applicable. The capture is selected only at query time, and ingestion never guesses it (I1 §6.2). | Phase 2: selected contribution is `DECLARED_MANIFEST`, giving `UNSUPPORTED` / `LOCALITY_CAPTURE_MODE_UNSUPPORTED` as a terminal per-candidate result (L17, L37). Phase 3: missing or unparseable `capturedAt` gives `INSUFFICIENT_EVIDENCE` / `LOCALITY_CAPTURE_TIMESTAMP_MISSING`; `capturedAt` outside the selected days under the exact inclusive Path C predicate (B9) gives `INAPPLICABLE` / `LOCALITY_CAPTURE_TEMPORAL_MISMATCH` (L31, L36). |
| Caller namespace | **Admitted, derived at query time** | The captured Pod/owner-chain namespace in the selected snapshot. The CLIENT `k8s.namespace.name` is a consistency check only. | Only a contradiction inside the CLIENT Resource/carrier: `CONFLICT` / `LOCALITY_CLIENT_INTERNAL_CONFLICT`. | Phase 4: no resolvable captured chain gives `UNRESOLVED` / `LOCALITY_POD_OWNER_UNRESOLVED`. A present CLIENT namespace that contradicts the captured one gives `CONFLICT` / `LOCALITY_NAMESPACE_CONFLICT`, and the v2 record is retained (L34). |
| Caller Workload | **Admitted, derived at query time** | A unique supported captured owner chain (Deployment, StatefulSet, DaemonSet) in the selected snapshot | Not applicable. It is never inferred at ingestion. | Phase 4: `UNRESOLVED` / `LOCALITY_POD_OWNER_UNRESOLVED`, `AMBIGUOUS` / `LOCALITY_POD_OWNER_AMBIGUOUS` or `CONFLICT` / `LOCALITY_POD_OWNER_CONFLICT` under Path C (L19). |
| Target runtime locality | **Not established by this contract** | Separately evidenced target placement only; none is admitted in the minimum slice | Not applicable. | Unknown (L20). |
| Region | **Unsupported** | — | — | Phase 1: `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_DIMENSION` |
| Tenant | **Unsupported** | — | — | Phase 1: `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_DIMENSION` |
| Service-version locality | **Unsupported** (`service.version` never mints a canonical Service) | — | — | Phase 1: `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_DIMENSION` |
| Messaging locality (SENDS / PUBLISHES_TO / …) | **Unsupported** | — | — | Phase 1: `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_RELATION` |

Other ingestion-only refusals (I1 §10.1–10.2):
- `SERVER_ONLY` gives `LOCALITY_SERVER_ONLY_NO_CLIENT`.
- Any other absent CLIENT carrier gives `LOCALITY_CLIENT_IDENTITY_MISSING`.
- When a carrier exists but specific fields are missing, only the specific field codes are emitted, **never together with** the generic carrier-missing code (L35).

**Query-time abstention when only v1 remains (I1 §10.2; DoD 9; L35).** A read-side query that finds only an unscoped v1 bucket **cannot know** whether the underlying CLIENT lacked a carrier, a Pod UID or a cluster UID, or failed another guard. The new locality answer therefore:
- abstains generically, with `INSUFFICIENT_EVIDENCE` / `LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION`;
- adds `LOCALITY_LOCAL_COVERAGE_UNAVAILABLE` where relevant;
- adds `LOCALITY_LEGACY_V1_UNSCOPED` **only** where legacy-only source/inventory status is independently known.

It MUST NOT expose or reconstruct any ingestion-specific code from the ingestion column, imply that every v1 contribution was refused, or invent a positive locality. The specific cause is disclosed only in the import/migration report's own surface.

Admitted relation: HTTP `CALLS` (caller Service → provider **Operation**) only. Other v0.5 relations keep their existing query semantics; only the new relation-locality surface reports them as unsupported for locality qualification.

**No wildcard.** An omitted, missing, contradictory, stale or unsupported dimension is reported with its disposition. It is never `*`, never inferred from a similar display name, a label, namespace proximity or co-location, and never a reason to widen the claim to all localities (parent §6; I1 §4.2).

**Two Workloads in one cluster and namespace are two localities** if and only if their captured owner chains independently establish two distinct supported Workload objects. Two ReplicaSets of one Deployment are one Workload (L33).

---

## 6. No-inference matrix (DoD 2 and 10; parent gates 3 and 6)

Each row is an inference the contract forbids, together with the conformance case that must prove it stays forbidden.

| Attempted basis for assigning an individual CALLS to a caller Pod or Workload | Result | Case |
|---|---|---|
| Same-Service `RuntimeIdentityObservation` joined to a v1 bucket by Service/time | No attribution: unscoped v1 only, no backfill | L05 |
| Pod or Workload **name** match, labels, namespace proximity, co-location | No attribution | L26 |
| Configured or explicit Service-level `DEPLOYED_AS` | No attribution | L26 |
| SERVER Resource, `peer.service`, tracing parentage alone | No caller identity | L09, §6.1 |
| Legacy v1 aggregate without replayable original per-interaction input | `INSUFFICIENT_EVIDENCE` / `LOCALITY_LEGACY_V1_UNSCOPED` (only where legacy-only status is independently known) | L05, L35 |
| Replacement Pod P2 for an event from P1 | Never reattached: P1's Workload becomes `UNRESOLVED` when P1 leaves the selected capture | L18, L27 |
| Nearest timestamp, skew allowance, implicit timezone, substituted `capturedAt` | Not admitted | L17, L31 |
| Latest, friendliest or most specific of several owner candidates | Not admitted: `AMBIGUOUS` or `CONFLICT` retained | L19 |
| Display-name matching of a canonical Service or Operation owner | Never rewrites Service identity or Operation ownership | L32 |
| Extracting a narrower scope from an existing v0.5 refusal | Never converts a refusal into positive locality | §10.2 |

## 7. Operation → provider Service projection constraints (I1 §5.1; handoff to I3)

I1 fixes **constraints only**. The exact public roll-up shape is an I3 freeze.

1. The observed relation is `caller Service --CALLS--> provider Operation`. The v2 `object_id` is the canonical **Operation ID**.
2. Each eligible local CALLS is qualified against its **exact** Operation through the existing qualification owner.
3. The logical provider Service is the Operation's **unique canonical owning Service** from accepted source/identity state. It is never taken from a display name or an inferred deployed target.
4. Grouping key for a later Service dependency: *(caller Service, resolved caller Workload locality, provider Service, selected observation context/snapshot)*. Evidence and claim references are the deduplicated, sorted **union** of the qualifying per-Operation references, and each Operation-level status and provenance is retained.
5. When Operation ownership is missing or ambiguous, no provider Service dependency is minted.
6. No `CONFIRMED` is produced by pooling a declaration of one Operation with an observation of another.
7. No global, absent, exclusive or target-runtime-locality claim is derived from a group.

**Handed to I3:** response shape, bounded Operation membership and evidence union, canonical ordering, group-level qualification presentation, the incomplete or ambiguous-owner disposition, and distinct-Operation/same-provider and missing-owner acceptance scenarios (L32).

## 8. Observation window versus Intent effective interval (I1 §4.3; parent gate 5; DoD 11)

| | Current-State observation window | Future (v0.7) Intent effective interval |
|---|---|---|
| Type | `LocalityDayContextV1.first_utc_day` / `last_utc_day` (and the I1.2 `ScopedDayWindowV1`) | A different type on a different semantic timeline (not defined in v0.6) |
| Meaning | The days in which **actual observed evidence** is considered | When an intended architecture is meant to hold |
| Enters Current-State qualification | Yes, as the observation-context bound | **Never.** It cannot substitute for the observation window and cannot change evidence or qualification (L30). |

Documentation, examples and later types must not use one term for the other.

---

## 9. Traceability of this slice

| I1 requirement | Section here |
|---|---|
| §14 slice I1.1: baseline code/source inventory and v1 attribution gap | §1 (B1–B14) |
| §4.1 roles, `locality-contract/1` | §2 |
| §4.3 internal types | §3 |
| §5 / parent §8 claim-kind × evidence matrix; qualification boundary | §4, §4.1 |
| §4.2 / parent §6.1 dimensions, unsupported set, no wildcard | §5 |
| §4.2 capture revision/time prerequisite; §10.1 phase order; §10.2 ingestion-diagnostic vs query-visible split (DoD 9, L35) | §5 (capture row, ingestion/query columns, v1-only abstention) |
| DoD 2 and 10 no-inference (parent gates 3 and 6) | §6 |
| §5.1 Operation → provider Service constraints | §7 |
| §4.3 / DoD 11 observation window vs Intent | §8 |

Slice I1.2 content is in §§10–16 below. Still deferred: the v2 key, vectors and snapshot contract (I1.3); the capture runbook (I1.4); and the independent L01–L37 expected dossier and completion record (I1.5).

---

# Slice I1.2: scope, UTC-day, CLIENT field and disposition contract

Sections 10–16 freeze the **implementation-level spellings** that I1 §15 delegates to I1: the CLIENT allowlist and normalization, the carrier retention set, the guard split, timestamp precision, UTC-day window normalization and the §10.1 disposition lookup. Every row cites the accepted I1 rule it spells out. Owner decisions taken for this slice are marked **[owner decision, I1.2]**. The spec left each of them open to I1, and none weakens it.

## 10. CLIENT caller-attribution allowlist and normalization (I1 §4.2, §6.1–6.2)

**Normalization rule identity:** `otel-client-caller-attribution`, version `1`. This is recorded as `CallerAttributionV1.normalization_rule` and in v2 lineage (I1 §7.1). The naming follows the existing `otel-runtime-identity-observation` rule (`RuntimeIdentityObservation`, B8).

### 10.1 Admitted fields

All values are read from the Resource of the **same original CLIENT span** that produced the accepted v0.5 CALLS (I1 §6.1). No other Resource or span attribute is admitted. Every field below is already read by `_resource_identity` (B6).

| Field | OTel source | Role | Required for v2 |
|---|---|---|---|
| `client_environment` | `deployment.environment.name` | Compared with the accepted fact environment (ingestion guard 3) | **Yes** |
| `client_pod_uid` | `k8s.pod.uid` | Attribution identity; a v2 key input | **Yes** |
| `client_cluster_uid` | `k8s.cluster.uid` | Exact cluster identity; a v2 key input | **Yes** |
| `client_timestamp` | The CLIENT span's `end_time`, as converted by the receiver (§12) | The CLIENT event instant for ingestion guard 4 | **Yes** (always present on a decoded span) |
| `client_namespace` | `k8s.namespace.name` | Optional consistency check against the captured Pod namespace, **at query time only** | No |
| `client_pod_name` | `k8s.pod.name` | Optional consistency check against the captured Pod name, at query time only | No |
| `client_deployment_name` / `client_statefulset_name` / `client_daemonset_name` | `k8s.deployment.name` / `k8s.statefulset.name` / `k8s.daemonset.name` | Optional consistency check against the captured Workload kind and name at query time, and CLIENT-internal kind check at ingestion (§10.3) | No |

`client_timestamp` is the CLIENT span's `end_time`. That is the instant the existing adapter already uses for a CLIENT-sourced fact (`CLIENT_ONLY`, B4) and for `RuntimeIdentityObservation` (B8), so no second CLIENT clock reading is introduced.

`service.version` and `service.namespace` stay what they are in v0.5: existing Service-resolution and source metadata. They are **not** locality dimensions and not v2 key inputs (I1 §4.2, §7.1).

### 10.2 Value normalization **[owner decision, I1.2]**

1. **Admissible value:** an admitted attribute is present only if its decoded value is a **non-empty string**. A missing attribute, an empty string or any non-string value (int, bool, array, kvlist, bytes) is treated as **missing**. For example, a non-string `k8s.pod.uid` gives `LOCALITY_POD_UID_MISSING`.
2. **Comparison:** exact equality of the string's code points (and so of its UTF-8 bytes). There is no trimming, case-folding, Unicode normalization, alias, prefix or wildcard matching.
3. **No repair:** a value is never reconstructed from another attribute, a name, a label or another span.

Duplicate Resource keys: the receiver keeps the last value for a repeated key (`_attributes_to_dict`, `otlp_receiver.py`:42–43). This contract admits the value the receiver yields and **does not** detect duplicates. Detecting them would need a receiver change, which is outside this contract.

### 10.3 CLIENT-internal contradiction (I1 §6.2(5)) **[owner decision, I1.2]**

The complete, closed set of CLIENT-internal contradictions that refuse v2 with `CONFLICT` / `LOCALITY_CLIENT_INTERNAL_CONFLICT` is:

| Rule | Condition, evaluated on admissible values only (§10.2) | Why it is knowable at ingestion |
|---|---|---|
| `CLIENT_MULTIPLE_WORKLOAD_KINDS` | More than one of `k8s.deployment.name`, `k8s.statefulset.name`, `k8s.daemonset.name` is present | A Pod has at most one supported controlling Workload kind (B12). Two kind names in one Resource contradict each other without any capture. This mirrors v0.5 Path C, where any kind name other than the resolved kind is contradictory (`_consistency_attributes_agree`, B10). |

No other combination of CLIENT values is an ingestion contradiction. In particular, namespace, Pod name and Workload name are **never** compared with anything at ingestion, because the capture they must match is selected only at query time (I1 §6.2). Their mismatches are query-time `CONFLICT`s that retain the v2 record (§15, L34).

## 11. Transient carrier retention (I1 §6.1)

For each pending CLIENT, the bounded cross-batch carrier (`PendingHttpSpan`, B2) must additionally retain the admitted values from §10.1: `client_environment` (already carried as `environment`), `client_pod_uid`, `client_cluster_uid`, the optional consistency fields, and the CLIENT `end_time` (already carried as `timestamp`).

| Requirement | Rule |
|---|---|
| Arrival orders | CLIENT-first (the SERVER later pops the waiting CLIENT) and SERVER-first (the CLIENT later pops the waiting SERVER) must yield the same `CallerAttributionV1` as an in-batch pair (L07, L08). |
| Source of caller values | Always the original CLIENT span's Resource. The SERVER Resource, `peer.service`, a `RuntimeIdentityObservation`, `DEPLOYED_AS` or trace parentage never fill a missing caller value (I1 §6.1). |
| Bounds | TTL (60 s default) and size (10 000 default) are unchanged. The extra fields are bounded strings from the §10.1 allowlist only. No raw span or Resource payload is retained, and nothing from the carrier is written to Neo4j. |
| Expiry | A TTL-expired CLIENT that v0.5 turns into a `CLIENT_ONLY` CALLS keeps its carried values and may be v2-eligible. An expired SERVER has no CLIENT and never yields v2 (`LOCALITY_SERVER_ONLY_NO_CLIENT`, B4, L09). A size-evicted CLIENT yields nothing, as today (B3). |

## 12. Timestamps and UTC-day assignment (I1 §8) **[owner decision, I1.2]**

1. **Event instant precision.** The event instant is the receiver's timezone-aware UTC `datetime` at **microsecond** precision, `datetime.fromtimestamp(unix_nano / 1e9, tz=UTC)` (B7). Sub-microsecond information is not retained.
   - *Disclosed baseline property:* the float division can round a value within about 0.5 µs of UTC midnight **up** into the next day. The contract accepts each receiver-converted instant as that span's time and never re-derives it from the raw nanoseconds. Which of the two instants plays which role is fixed in §12.6.
2. **UTC day of an instant:** the calendar date of the instant **after conversion to UTC**. An instant with no timezone is not admissible.
3. **Ingestion guard 4:** `client_timestamp` and the accepted fact timestamp must have the same UTC day (§12.2). That common day is the v2 `bucket_utc_day`, and it always equals the v1 bucket day of the same interaction. A difference gives `INAPPLICABLE` / `LOCALITY_CLIENT_FACT_DAY_MISMATCH` at ingestion, with no v2 written and v1 unchanged (L11).
4. **Query-time instants** (`capturedAt`) are parsed by the existing Path C rule, unchanged: `datetime.fromisoformat`. A value without an explicit UTC offset is unparsable (PR #292), and unparsable or missing gives `LOCALITY_CAPTURE_TIMESTAMP_MISSING`. After parsing, comparisons are between aware instants, so offsets are honoured (`2026-09-29T01:30:00+02:00` is `2026-09-28T23:30:00Z`).
5. **Canonical serialization** of an instant is `YYYY-MM-DDTHH:MM:SS.ffffffZ` in UTC with exactly six fractional digits. This is the existing `format_utc_timestamp` form (`canonical_json.py`:33).
6. **Timestamp roles (the CLIENT instant and the fact instant are different values).** For a paired call, the accepted fact timestamp is the SERVER `end_time` (B5), and `client_timestamp` is the CLIENT `end_time` (§10.1). The two need not be equal. Their roles are fixed as follows:

| Use | Timestamp | Why |
|---|---|---|
| v1 bucket day, v1 `first_seen`/`last_seen` | Accepted fact timestamp | Existing v0.5 path (`adapter.py`:137–146), unchanged |
| v2 `bucket_utc_day` | Accepted fact timestamp's UTC day, which I-4 has verified equals the CLIENT's UTC day | Same day as v1 by construction |
| v2 `first_seen`/`last_seen`, merged as min/max over contributions like v1 | **Accepted fact timestamp** | This is the value the query-time phase 3 check (`LOCALITY_OBSERVATION_TEMPORAL_MISMATCH`) and the Path C `last_seen` predicate read. It is consistent with the v1 path, so v1 and v2 of one interaction never disagree about when it was observed. |
| Ingestion guard I-4 | Both: same UTC day | I1 §6.2(4) |
| `CallerAttributionV1.client_timestamp` | CLIENT `end_time` | Attribution metadata only. Not a v2 key input, not `first_seen`/`last_seen`, and not read by any query-time guard. |

For `CLIENT_ONLY` the accepted fact timestamp already is the CLIENT `end_time` (B4), so the two roles coincide.

Paired examples (vectors `T01`–`T03` in [`i1-vectors/utc-day-window.json`](i1-vectors/utc-day-window.json)):
- **T01:** CLIENT `end_time` `2026-09-28T10:00:00.250000Z`, SERVER/fact `2026-09-28T10:00:00.200000Z`. I-4 passes; v1 and v2 day `2026-09-28`; v2 `first_seen` = `last_seen` = `2026-09-28T10:00:00.200000Z`, the fact instant and not the CLIENT instant.
- **T02:** CLIENT `2026-09-29T00:00:00.000100Z`, SERVER/fact `2026-09-28T23:59:59.999900Z`. I-4 fails with `LOCALITY_CLIENT_FACT_DAY_MISMATCH`; v1 is recorded on `2026-09-28` unchanged; no v2.
- **T03:** `CLIENT_ONLY` at `2026-09-28T23:59:59.999999Z`. I-4 passes; v2 day `2026-09-28`; `first_seen` = `last_seen` = that instant.

## 13. `ScopedDayWindowV1`: whole-UTC-day window (I1 §8)

| Item | Frozen rule |
|---|---|
| Input | `first_day`, `last_day`, each a string matching exactly `^[0-9]{4}-[0-9]{2}-[0-9]{2}$` that is a valid proleptic-Gregorian calendar date (so `2028-02-29` is valid, `2026-02-29` invalid). Other ISO-8601 forms (`20260928`, `2026-W40-1`, a date-time) are rejected. |
| Order | `first_day <= last_day`, otherwise rejected. A one-day window has `first_day == last_day`. |
| Normalized start | `first_day` at `00:00:00.000000` UTC |
| Normalized end | `(last_day + 1 day)` at `00:00:00.000000` UTC **minus 1 µs**, that is `last_day` at `23:59:59.999999` UTC |
| Representability | `9999-12-31` is a valid `last_day`. Its next midnight is not representable in common date-time types, so an implementation must compute the end bound as `last_day` midnight plus (1 day − 1 µs), not as (next midnight) − 1 µs (vector `W05`). |
| Membership | Inclusive on both bounds: `start <= t <= end` for a microsecond instant `t` (§12). The next day's midnight is excluded. |
| Serialization | Both bounds in the §12.5 form, e.g. `2026-09-28T00:00:00.000000Z` / `2026-09-28T23:59:59.999999Z` |
| Invalid input | Malformed or reversed input is a request-validation refusal. The request is not treated as a narrower or wider window. |
| Finer request | Any request whose bounds are not whole UTC days, e.g. a date-time range, is `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION` at phase 1 (L25). Existing v0.5 date-time windows are untouched. |

The golden vectors for this section are in [`i1-vectors/utc-day-window.json`](i1-vectors/utc-day-window.json). `tests/unit/test_v060_i1_contract_vectors.py` recomputes them using only the Python standard library, with no `app/` import. The vectors were authored from the rules above.

## 14. Guard split: ingestion versus query (I1 §6.2)

| Guard | Phase | Inputs it may inspect | Failure result |
|---|---|---|---|
| I-1 Exact canonical subject Service and Operation IDs of the accepted v1 CALLS | Ingestion | The accepted v0.5 CALLS | No v1 CALLS means no v2 at all. v0.5 refusals are unchanged and never become locality evidence. |
| I-2 Non-empty `client_environment`, `client_pod_uid`, `client_cluster_uid` | Ingestion | CLIENT carrier | `LOCALITY_CLIENT_IDENTITY_MISSING` / `LOCALITY_POD_UID_MISSING` / `LOCALITY_CLUSTER_UID_MISSING` (§15.1) |
| I-3 `client_environment` exactly equals the accepted fact environment | Ingestion | CLIENT carrier, accepted fact | `LOCALITY_CLIENT_FACT_ENVIRONMENT_MISMATCH` |
| I-4 Same UTC day for `client_timestamp` and fact timestamp | Ingestion | CLIENT carrier, accepted fact | `LOCALITY_CLIENT_FACT_DAY_MISMATCH` |
| I-5 CLIENT-internal consistency (§10.3) | Ingestion | CLIENT carrier only | `LOCALITY_CLIENT_INTERNAL_CONFLICT` |
| Q-1…Q-4 Request preflight, source mode, environment/time, captured Pod/owner identity | Query | Retained v2 record, selected snapshot, request | §15.2 |

Ingestion guards never read a capture, a `RuntimeIdentityObservation`, `DEPLOYED_AS` or another span. Query guards never delete, rewrite or suppress a retained v2 record (I1 §6.2).

## 15. Disposition and reason lookup (I1 §10–10.2)

**Dispositions:** `APPLICABLE`, `INAPPLICABLE`, `INSUFFICIENT_EVIDENCE`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`, `UNSUPPORTED`.

**Reason codes:** the 23 `LOCALITY_*` codes of I1 §10, and no others.

**Reason ordering:** distinct codes, sorted by ascending code-point (ASCII) order.

**Within-phase primary precedence:** `CONFLICT > AMBIGUOUS > INAPPLICABLE > UNRESOLVED > INSUFFICIENT_EVIDENCE > APPLICABLE`. `UNSUPPORTED` is terminal in phases 1–2 and so is never ranked.

### 15.1 Ingestion phase: no v2 written; the result is visible only in diagnostics and the import/migration report (I1 §10.2)

| Cause | Disposition | Reason | Cases |
|---|---|---|---|
| `SERVER_ONLY` | `INSUFFICIENT_EVIDENCE` | `LOCALITY_SERVER_ONLY_NO_CLIENT` | L09, L35 |
| No CLIENT carrier at all (other than `SERVER_ONLY`) | `INSUFFICIENT_EVIDENCE` | `LOCALITY_CLIENT_IDENTITY_MISSING` | L35 |
| Carrier present, `client_pod_uid` and/or `client_cluster_uid` missing | `INSUFFICIENT_EVIDENCE` | `LOCALITY_POD_UID_MISSING` and/or `LOCALITY_CLUSTER_UID_MISSING`. **Not** also `LOCALITY_CLIENT_IDENTITY_MISSING` on their account. | L06, L35 |
| Carrier present, `client_environment` missing | `INSUFFICIENT_EVIDENCE` | `LOCALITY_CLIENT_IDENTITY_MISSING` | L35 |
| `client_environment` present and different from the fact environment | `INAPPLICABLE` | `LOCALITY_CLIENT_FACT_ENVIRONMENT_MISMATCH` | L10, L35 |
| CLIENT and fact timestamps on different UTC days | `INAPPLICABLE` | `LOCALITY_CLIENT_FACT_DAY_MISMATCH` | L11, L35 |
| §10.3 CLIENT-internal contradiction | `CONFLICT` | `LOCALITY_CLIENT_INTERNAL_CONFLICT` | L34, L35 |

Several ingestion causes in one interaction are one phase. Every cause that can actually be established is retained, and the primary disposition follows the within-phase precedence. For example, a missing Pod UID plus a CLIENT-internal contradiction gives `CONFLICT` with reasons `[LOCALITY_CLIENT_INTERNAL_CONFLICT, LOCALITY_POD_UID_MISSING]`. A guard whose input is missing establishes nothing further: a missing `client_environment` cannot also yield an environment mismatch.

**Interpretation, flagged for review:** when the carrier exists and **both** `client_environment` and a UID are missing, the reasons are `LOCALITY_CLIENT_IDENTITY_MISSING` (for the environment, per the I1 §10.1 row) **and** the specific UID code. The I1 §10.1 no-double-emit rule forbids emitting the generic code *because of* a missing UID. It does not suppress the separately specified environment cause.

### 15.2 Query phases: one retained v2 candidate (I1 §10.1)

Phases are evaluated strictly in order, and the first terminating phase decides the primary disposition. Later phases are **not evaluated**, and no reasons are invented for them.

| Phase | Cause | Disposition | Reason | Cases |
|---|---|---|---|---|
| 1 Request preflight | Unadmitted dimension (region, tenant, version) | `UNSUPPORTED` (terminates the request) | `LOCALITY_UNSUPPORTED_DIMENSION` | L24 |
| 1 | Unadmitted relation (e.g. messaging) | `UNSUPPORTED` | `LOCALITY_UNSUPPORTED_RELATION` | L24 |
| 1 | Sub-day or non-whole-day window (§13) | `UNSUPPORTED` | `LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION` | L25 |
| 2 Source/evidence mode | Candidate's selected Kubernetes contribution is `DECLARED_MANIFEST` | `UNSUPPORTED` (terminal **per candidate**) | `LOCALITY_CAPTURE_MODE_UNSUPPORTED` | L17, L37 |
| 3 Environment and time | Persisted v2 environment differs from the exact query environment | `INAPPLICABLE` | Exact environment-mismatch limitation. I1 §10.1 names no `LOCALITY_*` code for it, and none is minted here. | — (dossier sub-case, I1.5) |
| 3 | v2 bucket `last_seen` outside the §13 window | `INAPPLICABLE` | `LOCALITY_OBSERVATION_TEMPORAL_MISMATCH` | L17, L31 |
| 3 | Selected `capturedAt` outside the §13 window | `INAPPLICABLE` | `LOCALITY_CAPTURE_TEMPORAL_MISMATCH` | L31, L36 |
| 3 | Selected `capturedAt` missing or unparsable (§12.4) | `INSUFFICIENT_EVIDENCE` | `LOCALITY_CAPTURE_TIMESTAMP_MISSING` | L17 |
| 4 Captured Pod/owner identity | No captured Pod with the v2 cluster and Pod UID | `UNRESOLVED` | `LOCALITY_CAPTURE_MISSING_POD` | L18, L27 |
| 4 | Pod captured, owner chain incomplete or unsupported | `UNRESOLVED` | `LOCALITY_POD_OWNER_UNRESOLVED` | L18 |
| 4 | CLIENT cluster UID ≠ selected envelope `clusterUid` | `CONFLICT` | `LOCALITY_CLUSTER_UID_CONFLICT` | L16, L34 |
| 4 | Present `client_namespace` ≠ captured Pod namespace | `CONFLICT` | `LOCALITY_NAMESPACE_CONFLICT` | L34 |
| 4 | Other present optional consistency value (Pod name, Workload kind or name) contradicts the capture | `CONFLICT` | `LOCALITY_POD_OWNER_CONFLICT` (the applicable bounded Path C contradiction) | L34 |
| 4 | Several admissible Workload candidates, no contradiction | `AMBIGUOUS` | `LOCALITY_POD_OWNER_AMBIGUOUS` | L19, L35 |
| 4 | Contradictory owner paths or identity assertions | `CONFLICT` | `LOCALITY_POD_OWNER_CONFLICT` | L19, L35 |
| 4 | Unique supported Workload, all guards pass | `APPLICABLE` | — | L15 |

Phase 3 short-circuit example: a day-D v2 `last_seen`, a selected capture from day D+1 and a request for day D give `INAPPLICABLE` / `LOCALITY_CAPTURE_TEMPORAL_MISMATCH`, even if that capture's owner chain would conflict. The owner chain is not evaluated (L36).

**Cluster-UID conflict versus missing Pod (I1 §9, §10.1, L16).** `LOCALITY_CLUSTER_UID_CONFLICT` applies when the selected snapshot contains a captured Pod with the v2 Pod UID under a `clusterUid` different from the v2 `caller_cluster_uid`. That is a known contradiction between compatible identity inputs. When no selected capture contains that Pod UID at all, the result is `LOCALITY_CAPTURE_MISSING_POD`: nothing contradicts, the Pod is simply absent from the selected capture.

**Interpretation, flagged for review:** I1 §10.1 names no dedicated code for a contradicted optional Pod-name or Workload-kind/name attribute ("applicable bounded Path C contradiction"). This contract maps both to `LOCALITY_POD_OWNER_CONFLICT`, the only existing identity-conflict code for the captured Pod/owner chain. No new code is minted.

### 15.3 Answer-level results without a retained v2 candidate (I1 §10.2)

| Situation | Disposition | Reasons | Cases |
|---|---|---|---|
| No eligible local CALLS, only unscoped v1 or nothing | `INSUFFICIENT_EVIDENCE` | `LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION`, plus `LOCALITY_LOCAL_COVERAGE_UNAVAILABLE` where relevant, plus `LOCALITY_LEGACY_V1_UNSCOPED` **only** where legacy-only source/inventory status is independently known | L05, L23, L35 |
| Any request for local absence | Never local `NOT_OBSERVED_IN_WINDOW` | `LOCALITY_LOCAL_COVERAGE_UNAVAILABLE` | L23 |

A §15.1 ingestion code is never emitted in a query answer.

## 16. Traceability of slice I1.2

| I1 requirement (§14 slice I1.2: "exact normalization, allowlist and negative tests frozen") | Section |
|---|---|
| §4.2 minimum positive dimensions; §6.2 ingestion guards (2), (3), (5) | §10, §14 |
| §6.1 carrier in both arrival orders; bounded; `CLIENT_ONLY`/`SERVER_ONLY` | §11 |
| §8 timestamp precision, UTC parser, day-range validation, serialization, midnight boundary | §12, §13, vectors |
| §8 CLIENT vs accepted-fact timestamp roles; v2 `last_seen` input to the phase 3 check | §12.6, vectors T01–T03 |
| §6.2 guard split; query-time conflicts never suppress v2 | §14, §15.2 |
| §10 taxonomy; §10.1 phase gates, terminal per-candidate `UNSUPPORTED`, within-phase precedence and sorted reasons (L35–L37) | §15 |
| §10.2 ingestion-only visibility; generic read-side abstention | §15.1, §15.3 |
