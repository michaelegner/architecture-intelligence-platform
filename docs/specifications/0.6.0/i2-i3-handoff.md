# AIP v0.6.0 I2 → I3 Handoff: the internal locality read contract

**Status:** I2.6d deliverable (I2 spec §16, "Handoff to I3"). It documents the **internal** request/result API that I2 built under the one Architecture Intelligence semantic owner, and lists what I3 must still freeze. It creates no public contract: there is no REST route, MCP tool, public schema or wire version (I2 §1, §9). I3 owns all of that.
**Governing:** [I2 specification](i2-scoped-evidence-and-qualified-local-assessment.md) revision 0.4, the [decision record](i2-decision-record.md) D1–D16, and the [I1 contract](i1-locality-and-evidence-applicability.md).

## 1. Entry points

| Entry point | Module | What it returns |
|---|---|---|
| `ArchitectureIntelligenceService.assess_local_calls(request, *, after_id=None)` | `app/architecture_intelligence/service.py` | `LocalAssessmentResult`: the qualified assessment of one candidate page. It opens its own read-only session. **This is the method I3 should call.** |
| `read_scoped_applicability(session, request, *, coverage_qualification_enabled, after_id=None)` | `app/architecture_intelligence/scoped_evidence_repository.py` | `ScopedApplicabilityRead`: the fenced read (candidates, source inventories, declared `CALLS` evidence) and its I2.3 evaluation, with the read's `snapshot_id`/`model_revision` |
| `evaluate_candidates(request, records, sources, *, truncated)` | `app/architecture_intelligence/scoped_applicability.py` | `ApplicabilityResult`: pure, per candidate and per pair (D4, D13) |
| `assess(read, request)` | `app/architecture_intelligence/local_assessment.py` | `LocalAssessmentResult`: pure (D9, D14) |

The service is the only semantic owner (I2 §4). I3 adapters must call `assess_local_calls` and must not re-derive any disposition, qualification or identity.

## 2. Request (`LocalityRequest`, `SourceSelector`)

| Field | Meaning |
|---|---|
| `subject_service_id` | Canonical caller Service. The candidate read filters by this **only** (D3). |
| `object_operation_id` | Optional exact canonical Operation |
| `environment` | Exact observation environment; it is never a read filter. A mismatch is phase 3 `INAPPLICABLE` + `REQUEST_ENVIRONMENT_MISMATCH` (D13.4). |
| `first_day`, `last_day` | Whole UTC days, `YYYY-MM-DD` (`ScopedDayWindowV1`, matrix §13). A date-time bound is phase 1 `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION`; any other malformed or reversed window raises `ValueError`. |
| `relation_type` | Only `CALLS`; anything else is phase 1 `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_RELATION` |
| `dimensions` | Only `cluster`, `namespace` and `workload`; anything else is phase 1 `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_DIMENSION` |
| `selector` | Optional explicit `(source_instance_id, revision)`. If it is absent or stale, the result is zero pairs (D13.3). |
| `after_id` (a keyword argument, not a field) | Page continuation, ascending v2 `id` |

## 3. Result (`LocalAssessmentResult`)

| Field | Meaning |
|---|---|
| `snapshot_id`, `model_revision` | The one canonical snapshot the whole read was fenced under. With v2 present it includes the two conditional keys (D15). |
| `disposition`, `reasons` | Answer level: `APPLICABLE` with no reasons when at least one assertion exists. With none, the answer is `INSUFFICIENT_EVIDENCE` [`LOCALITY_LOCAL_COVERAGE_UNAVAILABLE`, `LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION`] (D14.5). A phase-1 refusal gives `UNSUPPORTED` with its reasons. There is never a local `NOT_OBSERVED_IN_WINDOW`, and never `LOCALITY_LEGACY_V1_UNSCOPED` (D8). |
| `coverage` | Always `LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE` (I1 §5) |
| `assertions` | `QualifiedLocalEvidenceAssessment`s, sorted by `assertion_id` (§4) |
| `candidate_limitations` | One per v2 candidate that supports no assertion, sorted by v2 ID. Each carries the candidate's I2.3 summary disposition, sorted reasons, limitation codes and **every** pair unchanged (D4, D14.5). |
| `truncated`, `next_after_id` | Page bound: at most 500 candidates per call (D3). A truncated page also marks each assertion's lineage incomplete (D14.8). |

## 4. `QualifiedLocalEvidenceAssessment` (I2 §9)

| Field | Content |
|---|---|
| `assertion_id` | `aip:local-assertion:v1:<sha256>` over the caller Service, `CALLS`, the Operation, the environment, the window and the Workload (captured kind + captured UID; D9, D14.1). It is stable across snapshots. Frozen vectors are A01–A05 in [`i2-vectors/local-assessment-id.json`](i2-vectors/local-assessment-id.json). |
| `assessment_id` | `aip:local-assessment:v1:<sha256>` over the assertion, the `snapshot_id`, the supporting `(source, revision)` pairs and the four D14.2 rules; it is instance-bound. Frozen vectors are I01–I03. |
| `subject_service_id`, `relation_type`, `object_operation_id`, `environment`, `window` | The assertion's subject, relation, object and context |
| `caller_workload` | `CapturedWorkload`: logical ID, kind, namespace, name, cluster UID and captured UID |
| `target_runtime_scope` | Always `UNKNOWN` (I1 §4.1) |
| `observation` | The distinct v2 evidence IDs (lineage, never the key), `first_seen`/`last_seen` and `lineage_complete` |
| `declared_evidence_ids` | The DECLARED IDs on the caller's `CALLS` edge to **this** Operation only (D14.4) |
| `selected_captures`, `capture_evidence_refs` | The supporting sources (ID, revision, mode, real `capturedAt`) and the Pod/owner evidence refs |
| `applicability`, `qualification` | `APPLICABLE`; `CONFIRMED` or `OBSERVED_ONLY` from the shared kernel `qualify_relation` (D14.4) |
| `source_limitations` | Every non-applicable pair of a contributing candidate, as `(v2 id, PairResult)` |
| `rules`, `snapshot_id`, `model_revision` | The derivation rules and the snapshot binding |

Grouping (D14.3) gives one assertion per (caller, Operation, environment, window, **full Workload identity including the captured UID**). The I2.3 roll-up deduplicates only exactly identical Workload identities, and two incarnations are `CONFLICT` (the PR #365 review fix).

## 5. Pair versus candidate (I2.3; D4, D13)

- **Admission (D13.7).** A pair is one (v2 candidate, accepted Kubernetes source), admitted explicitly or by implicit rule 1 (the source captured the Pod UID) or rule 2 (same cluster, and the CLIENT namespace is in the scope). Each pair records its `admission` basis.
- **Evaluation.** Each pair runs I1 phases 2–4 independently; the first phase with a cause terminates, and the causes of that phase are collected (D13.2).
- **Summary.** The candidate summary rolls the pairs up per D4/D13.5 and never recomputes a pair.

I3's public enumeration must expose **both** levels:
- the summary per candidate;
- all source-specific pair results, including the no-cover abstention `NO_SELECTABLE_COVERING_SOURCE`.

## 6. Stability and evidence lookup hooks

- **One fence.** Everything in one result is read in one stable-snapshot attempt; `SnapshotUnstable` propagates. I3 must refuse a mismatched or stale `snapshot_id` rather than silently switch to the latest one (I2 §11).
- **Record retrieval.** v2 records are reachable only through `read_scoped_observed_calls` (D1). They are never `:Evidence`, never on a relation, never in the NL-approved labels, and never served by the public evidence resolver. If I3 exposes scoped evidence by ID, it needs its own resolver bound to the same snapshot (I2 §16: "no second evidence-resolving hash").
- **Test hooks.** The executable reference inputs are:
  - the rehearsal fixture `tests/fixtures/locality/rehearsal/` (REHEARSAL – NOT I5);
  - the frozen vectors;
  - the 65-variant [conformance matrix](i2-conformance-matrix.md).

## 7. What I3 must still freeze

1. The public request/response schemas and versions, REST routes and MCP tools, and the final route/tool count.
2. Public page bounds and continuation (I2's 500-record internal page is not a public bound, D3).
3. The Service-level dependency roll-up (Operation → provider Service, the union of evidence, group qualification presentation, missing/ambiguous owners), which covers dossier L32 and L04a's `provider_services` (I1 §5.1).
4. Selected-scope comparison and bounded locality enumeration (parent §§8–10).
5. A same-snapshot drill-down for scoped evidence.
6. At the next reviewed release-golden-path re-freeze: the default flip of `telemetry.scoped-evidence.enabled` together with the demo oracle's handling of the `ScopedEvidence*` operational nodes (D16).
