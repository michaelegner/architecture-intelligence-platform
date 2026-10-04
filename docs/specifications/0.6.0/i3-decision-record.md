# AIP v0.6.0 I3 — Decision Record (I3.1)

**Status:** **Frozen.** D1–D15 were frozen by I3.1a (#386), D16 by I3.1b/c (#387, #388), and D17 by I3.2a (#393). I3 is complete; see the [completion record](i3-completion-record.md). Each decision settles an item that the [I3 specification](i3-bounded-current-state-projection-and-public-answers.md) §3/§17 marks **[I3 proposal]**, and none reopens a parent, I1 or I2 semantic. Any later change is a reviewed amendment to this record.  
**Release / increment:** `v0.6.0` — Locality-Aware Current State / I3, slice I3.1  
**Governing specification:** I3 specification revision 0.2 (Accepted), merged in #382 (`82652f44b0f35f4349f94c5b5c62598a3d03bbd4`), with the tool-name proposal of #385 (`2278252`), which also amended [parent](specification.md) §17.  
**Entry baseline:** `main` at `2278252` (PR #385).  
**I2 closure:** PR #376, merge `46f700ee4a67399a67e406c8e445db572fd0a31a`; closure SHA recorded by #377 (`1263db508d37c8cbc9421349f6cc661b2542f9c9`). The I1 oracle, the I2 vectors and the rehearsal fixture are unchanged by this record.

The I3.1 work is cut into three PRs:
- **I3.1a** (this record);
- **I3.1b**: the draft v0.6 contract models and the generated JSON Schemas (no behaviour, no registration);
- **I3.1c**: the independently authored expected-answer matrix and negative fixtures, validated against the I3.1b schemas.

The owner merges each before the next starts. No semantic code (I3.2) or adapter (I3.3) is written before I3.1c merges.

**Revision 2 (PR #386 review of `858f679`):** D4/D6 bound the candidate×source fan-out with a same-fence preflight instead of a cap applied after evaluation; D10 no longer labels an identity outside the evaluated inventory as evaluated (new `EVALUATED_NO_POSITIVE`/`UNKNOWN` statuses and `SELECTION_NOT_ESTABLISHED`); D11 resolves capture/owner refs in the evidence mode under its own authority rule (owner decision), and D14 routes them there instead of to `get_evidence`. The required I3.1c cases are listed in D15.

**Revision 3 (PR #386 re-review of `098e183`):** D10 `EVALUATED_NO_POSITIVE` is defined on an evaluated `APPLICABLE` *pair* whose candidate rolled up non-positive (only `APPLICABLE` pairs carry a Workload); R5 is rebuilt on I2 D4 S04 and R6b adds the unreachable-via-`INAPPLICABLE` case. I2 applicability is unchanged.

---

## D1 — Exposure and tool count (I3 §13, §17 item 1; parent §17, §19)

| Item | Frozen decision |
|---|---|
| MCP | **One** new read-only tool, `get_service_dependencies_by_locality`. It is the fourth tool; there is no fifth. |
| Modes | One request argument, `request`, discriminated on `mode`: `query` (the locality answer, D3–D10) and `evidence` (the same-snapshot scoped resolver, D11). |
| Service | `ArchitectureIntelligenceService.get_service_dependencies_by_locality(request)` and `ArchitectureIntelligenceService.resolve_scoped_locality_evidence(request)`. They are the only semantic owners. The MCP adapter dispatches on `mode` to exactly one of them. |
| REST | `POST /api/services/{service_id}/dependencies/by-locality` (query) and `POST /api/services/{service_id}/dependencies/by-locality/evidence` (evidence). The Service comes from the path; the body carries every other field and must not repeat `subject_service_id` (closed body). |
| Annotations | The same `_READ_ONLY_ANNOTATIONS` as the three v0.5 tools (`app/mcp/tools.py`). |
| Unchanged | `get_service_dependencies`, `get_architecture_drift`, `get_evidence`, their schemas, the `/api/services/{id}/dependencies`, `/drift`, `/deployments` routes and `/api/evidence/*`. `contracts.TOOL_NAMES` and `ArchitectureToolName` stay the three v0.5 names (D2). |
| MCP description | The I3 §13 proposed description, unchanged in meaning: positively established HTTP dependencies per evidenced caller-Workload locality, not an exhaustive partition, no local absence; second mode resolves exact scoped refs at the supplied snapshot. |

**Why POST:** typed exact selections, cursors and bounded ref lists do not fit GET query parameters (I3 §13). Both routes are reads with zero graph writes.

## D2 — Versioning (I3 §11, §17 item 2; parent §18)

| Item | Frozen decision |
|---|---|
| Schema version | A new locality envelope with `schema_version` `"0.6"`. It is **not** a widening of `ArchitectureAnswer`: the 0.5 `tool` enum, claim union and `schema_version` stay closed. Scoped Operation assertions are **not** forced into `DependencyClaim`/`DeploymentClaim`. |
| Reuse | The envelope reuses the existing `Producer`, `SnapshotRef` and `Outcome` models from `app/architecture_intelligence/contracts.py`. Producer build version and schema version stay separate. |
| Models | New module `app/architecture_intelligence/locality_contracts.py` (core package; import-linter unchanged). Envelope `LocalityAnswer`, with `tool` const `get_service_dependencies_by_locality`, `mode`, and `data` discriminated on `mode`: `ServiceDependenciesByLocalityData` (query) or `ScopedLocalityEvidenceData` (evidence). |
| Published files | `schemas/architecture_intelligence/v0.6/service-dependencies-by-locality-request.schema.json` and `…-answer.schema.json`, generated by `schema_export.py` like v0.5, with a byte-for-byte frozen test. Unlike v0.5, the request schema is published as a file. |
| v0.5 | `schemas/architecture_intelligence/v0.5/*` stay byte-identical; their frozen tests are not edited. |
| Closedness | Every object is `extra="forbid"` / `additionalProperties: false`. Every identity array is sorted and duplicate-free, and the JSON Schema expresses that wherever it can (`uniqueItems`, const/enum, patterns, if/then), per the frozen-contract parity rule. |

## D3 — Query request vocabulary (I3 §5, §17 item 3)

`mode: "query"` request fields:

| Field | Frozen decision |
|---|---|
| `subject_service_id` | Required full canonical Service ID (MCP); path parameter (REST). Never a display name. |
| `environment` | Required exact string. Passed to I2 as-is; never a read filter (D13.4). |
| `first_day`, `last_day` | Required strings. `YYYY-MM-DD` is the supported form. An RFC 3339 date-time is **well-formed but unsupported**: I2 phase 1 `UNSUPPORTED` / `LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION` (D9). Anything else, or a reversed window, is a validation error. |
| `relation_type` | Optional string, default `CALLS`. Any other value is well-formed but unsupported: `LOCALITY_UNSUPPORTED_RELATION`. |
| `dimensions` | Optional sorted, distinct list of strings, default `["cluster", "namespace", "workload"]`. Passed to I2; any other entry (e.g. `region`, `tenant`) is `LOCALITY_UNSUPPORTED_DIMENSION`. This field exists so the I3 §14 unsupported-dimension row is reachable publicly. |
| `object_operation_id` | Optional exact canonical Operation. Narrows the I2 **candidate read** (permitted by D3). |
| `provider_service_id` | Optional exact Service. Applied **only** to the provider projection, after D8 ownership. It never narrows candidate admission, and an unresolved-owner Operation is still reported (D8). |
| `source_selector` | Optional `{source_instance_id, revision}`, passed to I2 unchanged. Absent or stale gives zero pairs and I2's `INSUFFICIENT_EVIDENCE` / `NO_SELECTABLE_COVERING_SOURCE`, the **same** disposition as implicit no-cover (D13.3). |
| `caller_localities` | Optional list of 1–50 `WorkloadIdentity` values, sorted and distinct. Absent means mandatory enumeration of the evaluated inventory (D10). Present means a post-evaluation filter over the evaluated inventory: it never shortcuts I2 phases (L10b/L17d still reach phase 3). |
| `compare` | Optional list of exactly **two** distinct `WorkloadIdentity` values. If `caller_localities` is present, both must be members of it; otherwise it is a validation error. |
| `snapshot_id` | Optional assertion that the latest snapshot is this one (D9). |
| `cursor` | Optional opaque continuation (D5). |

`WorkloadIdentity` is `{cluster_uid, namespace, kind, uid}`. `kind` is the captured kind exactly (`Deployment`, `StatefulSet`, `DaemonSet`, as D14.1). `uid` is the captured Workload UID and is **required**: under D14.1 a Workload without a captured UID never has an assertion, so it can appear in the inventory as a candidate limitation (`WORKLOAD_UID_UNAVAILABLE`) but cannot be selected or compared. Workload `name` is presentation only and never matched.

**Not introduced:** separate unknown-Service or stale-selector diagnostics (I3 §5). An empty candidate read is reported as I2 reports it and does not claim the Service is unknown.

## D4 — Bounds and the same-fence fan-out preflight (I3 §7, §17 item 4)

These are initial bounds, **not** measured safe limits or SLOs. I3.4 records cap and refusal frequencies and the read cost (I3 §14).

| Bound | Value |
|---|---|
| Pair bound `P` | **2,000** candidate/source pairs per answer page, enforced **before** any pair is materialized (below) |
| Capture-source bound | at most **2,000** accepted capture sources considered by one request (`S ≤ P`) |
| Internal candidate page `k` | `min(500, ⌊P / S⌋)` v2 candidates (`S ≥ 1`); `500` when `S = 0` or an explicit `source_selector` is given (`S ≤ 1`). Never above D3's 500. |
| Presentation caps per answer page | at most **50** distinct caller Workloads and **200** provider/Operation memberships |
| `caller_localities` | 1–50 |
| `compare` | exactly 2 |
| Evidence refs | 1–20 per evidence-mode request |

**Why a preflight.** I2's read evaluates *every* candidate against *every* admitted source. A 500-candidate page is therefore not a pair, memory or work bound: the pair count is at most candidates × capture sources, and [`i2-churn-cost.json`](i2-churn-cost.json) measured Pod count, not source fan-out. A cap applied after `evaluate_candidates` would not bound anything.

**Preflight, inside the same stable-snapshot attempt** (one `read_extra`, I2 §11):
1. Read the accepted capture-source inventory **first** (I2's existing `SOURCE_CAPTURES_QUERY`; no Pods, owners or candidates yet). With an explicit `source_selector`, `S` is 1 if the selected `(source, revision)` is current, else 0 (and D13.3 then yields zero pairs). Otherwise `S` is the number of accepted capture sources.
2. If `S > 2,000`, stop: `NOT_ANSWERED` / `RESULT_LIMIT_EXCEEDED` (D6). No candidate is read.
3. Read at most `k` candidates. Each candidate has at most `S` admitted pairs, so the page has at most `k × S ≤ P` pairs **before** they are built. Pod and owner reads stay restricted to the page's Pod UIDs, as in I2 (D13.6).
4. Evaluate and assess with I2's unchanged pure functions.

`S` counts every accepted capture source, including those that will not pair with any candidate (other clusters or namespaces). This makes the bound conservative, not exact. It may shrink `k` but never under-counts.

**Reviewed I2 change (I3 §7 permits it).** `read_scoped_applicability` and `assess_local_calls` gain a keyword `page_size` (1–500, default 500, so the I2 behaviour and tests are unchanged), and a hook that lets the caller choose `k` from the sources read in step 1 inside the same fence. Both are I3.2 implementation work; this record freezes only the rule.

**Presentation caps.** After the bounded read, I3 walks the candidates in ascending v2 ID and keeps the longest prefix of **complete** candidates (each with all of its pairs) whose projection stays within the Workload and membership caps. If that prefix is shorter than the page, I3 re-runs I2's pure `assess` over the **same fenced read**, restricted to the prefix, with `truncated = true` and `next_after_id` = the last presented v2 ID. There is no second database read, so the prefix stays on the same snapshot, and I2 itself marks every assertion's lineage incomplete (D14.8). A candidate's pairs are never cut. These caps limit the size of the answer, not the work, which the preflight already bounds.

## D5 — Cursor (I3 §7, §17 item 4)

| Item | Frozen decision |
|---|---|
| Encoding | Unpadded base64url of canonical JSON `{"v": 1, "after_id", "query_digest", "snapshot_id", "schema_version"}` (sorted keys, no whitespace). Opaque to clients. |
| `after_id` | The last **fully presented** v2 ID (D4). |
| `query_digest` | `sha256` over the canonical JSON of the normalized request **without** `cursor` and `snapshot_id`. |
| Validation | A cursor that is not decodable, has an unknown `v`, or has a malformed field is a **validation error**. A well-formed cursor whose `query_digest` differs from the request's is `NOT_ANSWERED` / `CURSOR_QUERY_MISMATCH`. One whose `snapshot_id` is not the current snapshot is `NOT_ANSWERED` / `SNAPSHOT_NOT_AVAILABLE`, with the current `SnapshotRef`. There is never a silent restart on the latest snapshot. |
| Authority | A cursor grants no access and attests no evidence. |

## D6 — Source fan-out beyond the bound: fail closed (I3 §7 option (a); §17 item 4) — owner decision

With the D4 preflight, one candidate can have at most `S ≤ 2,000` pairs, so a single candidate can no longer exceed the pair bound after it has been read. The fail-closed case moves **before** materialization: if `S > 2,000` (D4 step 2), the answer is `NOT_ANSWERED` / `RESULT_LIMIT_EXCEEDED`, the limitation states `S` and the bound, no candidate is read and no cursor is emitted. The message says that this request cannot be answered with the current capture inventory, and that a client may narrow it with an explicit `source_selector`. This is option (a) of I3 §7: no candidate is skipped, and nothing is published as positive or absent.

## D7 — Grouping across page and cap boundaries: page-local, provisional (I3 §7; §17 item 4) — owner decision

v2 IDs are not ordered by Workload or Operation, so any later page can contribute to any group. Therefore:
1. Groups (assertions, provider groups) are computed per answer page only. There is no cross-request accumulator.
2. If the page has **any** continuation (I2 `truncated`, or a D4 cap prefix), **every** group on the page is `lineage_complete: false`, the inventory is `PARTIAL`, and so is any comparison.
3. A group is complete only when the whole inventory was evaluated on one page under one snapshot.
4. A later page never revises an earlier page's identities. A client that unions pages is told (field description and `docs/mcp.md`) that the union is only meaningful for pages carrying the same `snapshot_id`.

## D8 — Operation → provider Service projection (I3 §8, §17 item 5; I1 §5.1)

| Item | Frozen decision |
|---|---|
| Owner rule | The v0.5 rule of `dependency_projection._resolve_sync_destination`, reused, not restated: group the Operation's `(:Service)-[:PROVIDES]->(:Operation)` rows by provider, counting only rows whose `evidence_ids` resolve to accepted Evidence in the snapshot. Exactly **one** evidenced provider resolves the owner. |
| Unresolved | **Zero** evidenced providers gives `PROVIDER_OWNER_MISSING`; **two or more** gives `PROVIDER_OWNER_AMBIGUOUS`. The positive Operation assessment stays visible in its Workload locality with that code, and no provider dependency is minted (L32b). |
| Observed-only Operations | A runtime-discovered Operation already has its own observed `PROVIDES` fact from telemetry, with `ObservedEvidence` and the provider taken from the resolved SERVER-side Service (`app/telemetry/adapter.py` `_calls_fact_core`), not from a name. So L04a's O2 resolves to `service:legacy-pricing` under the same rule. This ownership evidence is **not** a CALLS locality input and does not qualify the call. |
| Same fence | The `PROVIDES` and Evidence rows are read inside the **same** stable-snapshot attempt as I2's candidate read. I3.2 composes I2's existing read helpers with one more fenced query. It is not a separate latest read. |
| Group key | `(subject Service, WorkloadIdentity, provider Service, environment, window, snapshot_id)` |
| Members | The distinct canonical Operation IDs with an I2 positive assessment and that owner, sorted. Each member keeps its own `qualification`, `assertion_id`, `assessment_id`, v2 IDs, `declared_evidence_ids`, selected captures, rules and limitations, unchanged from I2. |
| Group fields | `member_qualifications`: the sorted, distinct set of the members' statuses (`CONFIRMED`, `OBSERVED_ONLY`). There is **no** group-level qualification label and no `MIXED` enum. `evidence_refs`: the sorted, deduplicated union of the members' refs, which is presentation only and never a qualification input. |
| Not derived | `target_runtime_scope` stays `UNKNOWN`. A W1 member never qualifies W2. |

## D9 — Outcome, limitation and status mapping (I3 §9, §11, §13; §17 item 6) — Q1 owner decision

**Envelope outcome** (`Outcome`, reused):

| Case | Outcome | `data` |
|---|---|---|
| Malformed request (schema, cursor encoding, `compare` ⊄ `caller_localities`) | no answer: REST **422**, MCP validation error | — |
| Phase-1 refusal (relation, dimension, sub-day) | `NOT_ANSWERED` / `UNSUPPORTED_REQUEST`, with I2's reason codes | null |
| `snapshot_id` or cursor snapshot is not current; `SnapshotUnstable` | `NOT_ANSWERED` / `SNAPSHOT_NOT_AVAILABLE` (current `SnapshotRef` when known) | null |
| Cursor for another query | `NOT_ANSWERED` / `CURSOR_QUERY_MISMATCH` | null |
| Capture-source fan-out beyond the bound (D4, D6) | `NOT_ANSWERED` / `RESULT_LIMIT_EXCEEDED` | null |
| Evaluated, any continuation or cap, a requested comparison incomplete, or a selected identity `UNKNOWN` (D10) | `PARTIAL` / `INVENTORY_INCOMPLETE`, `COMPARISON_INCOMPLETE` and/or `SELECTION_NOT_ESTABLISHED` | present |
| Evaluated, complete, ≥1 positive, but a positive Operation's owner is missing or ambiguous | `PARTIAL` / `PROVIDER_OWNER_UNRESOLVED` | present |
| Evaluated, complete, **no positive** assertion (including no v2 and all-nonpositive candidates) | **`NOT_ANSWERED` / `INSUFFICIENT_EVIDENCE`, with the inventory payload** | present |
| Evaluated, complete, ≥1 positive, every positive owner resolved, comparison (if any) complete | `ANSWERED` | present |

- This keeps the v0.5 meaning of `_claims_outcome` (no positive content means not answered), so an empty result is never read as "no dependencies". Unlike `ArchitectureAnswer`, the 0.6 envelope **allows `data` on `NOT_ANSWERED`** when the request was evaluated, and requires `data` to be null on a refusal that evaluated nothing. I3.1b expresses this as a schema rule keyed on the limitation code.
- `LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE` is a payload `coverage` field, always present. It is not an envelope limitation, so it does not make every answer `PARTIAL`.
- Non-applicable candidates are inventory facts (`candidates`, D10), not envelope limitations.
- I2's local dispositions (`APPLICABLE`, `INAPPLICABLE`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`, `UNSUPPORTED`, `INSUFFICIENT_EVIDENCE`) and `LOCALITY_*` reasons are carried **unchanged** inside the payload; they are never envelope outcomes. There is no local `NOT_OBSERVED_IN_WINDOW` and no `LOCALITY_LEGACY_V1_UNSCOPED`.

**0.6 envelope limitation codes** (closed enum, separate from the 0.5 `LimitationCode`): `UNSUPPORTED_REQUEST`, `SNAPSHOT_NOT_AVAILABLE`, `CURSOR_QUERY_MISMATCH`, `RESULT_LIMIT_EXCEEDED`, `INVENTORY_INCOMPLETE`, `COMPARISON_INCOMPLETE`, `SELECTION_NOT_ESTABLISHED`, `PROVIDER_OWNER_UNRESOLVED`, `INSUFFICIENT_EVIDENCE`. A limitation is `{code, message, reasons}`, where `reasons` is the sorted list of I2 `LOCALITY_*`/internal codes it carries (possibly empty).

**HTTP.** Every evaluated or refused answer is **200** with the envelope, as for the v0.5 `/api/services` routes. Only a malformed request is 422. There is no 404 for an unknown Service (D3 "not introduced") and no 409/503 split (unlike `/api/evidence` GET routes).

## D10 — Query answer payload and inventory (I3 §6, §9, §11; §17 items 3, 6)

`ServiceDependenciesByLocalityData` fields (names frozen; I3.1b fixes types):

| Field | Content |
|---|---|
| `request_context` | The normalized request (D3), `relation_type`, `dimensions`, selection mode (`EXPLICIT_SOURCE` or `IMPLICIT_COVERING_SOURCES`) |
| `coverage` | Always `LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE` |
| `inventory` | `evaluated_v2_candidate_count`, `admitted_pair_count`, `evaluated_sources` (source ID, revision, cluster UID, namespaces, mode, `captured_at`; only sources that formed at least one pair), `bounds` (the D4 values actually applied), `i2_truncated`, `continuation` (D16.11), `cap_reached` (which caps, if any), `next_cursor`, `completeness` (`COMPLETE` or `PARTIAL`, relative to this inventory only) |
| `candidates` | One entry per evaluated v2 candidate, sorted by v2 ID: its I2 summary disposition, reasons, limitation codes, resolved Workload (if any), and **every** admitted pair (source, revision, admission basis, phase, disposition, reasons, limitations, evidence refs), unchanged from I2. A candidate's pairs are never cut (D4). |
| `localities` | One entry per positive `WorkloadIdentity`, sorted by `(cluster_uid, namespace, kind, uid)`: the Workload, its positive Operation assessments (I2 fields unchanged), its provider groups (D8), its unresolved-owner Operations, `target_runtime_scope: UNKNOWN` and `lineage_complete`. If `caller_localities` is set, only those Workloads are listed here; the `candidates` inventory is never filtered. |
| `comparison` | Present only if `compare` was given (see Comparison below) |

Unscanned remainder is represented only by `completeness: PARTIAL` and `next_cursor`; it is never counted or labelled absent. "Complete" means only that this evaluated inventory was fully presented (I3 §7, §9).

### Selected-scope evaluation status (I3 §5, §10; §17 item 6)

A Workload identity named in `caller_localities` or `compare` is a request, not evidence that the scope exists. Its status is derived only from **this** evaluated inventory, never from the identity alone:

| `evaluation` | When |
|---|---|
| `POSITIVE` | The Workload has at least one positive assessment on this page. On a `PARTIAL` inventory it is still provisional (D7). |
| `EVALUATED_NO_POSITIVE` | **Both:** the inventory is `COMPLETE`, **and** the identity is the `workload` of at least one evaluated `APPLICABLE` **pair** in `candidates`, while no assessment for it is positive. Only an `APPLICABLE` pair carries a resolved Workload (I2 `_phase_4`; an `INAPPLICABLE`, `UNRESOLVED`, `AMBIGUOUS` or `CONFLICT` pair has none). Every `APPLICABLE` candidate with a captured UID becomes an assertion (`assess()`), so this status arises exactly when the pair's **candidate** rolled up non-positive: I2 D4 S04 (an `APPLICABLE` pair at W1 plus a conflicting second source gives candidate `CONFLICT`) or two `APPLICABLE` pairs resolving different Workload incarnations (`CONFLICT`). A selected accepted capture tied the identity to this Service's v2 evidence under this snapshot, but the candidate was not qualified. This is **not** an absence. |
| `UNKNOWN` | Every other case: the identity never appears as a resolved Workload in the evaluated inventory (including an invented or mistyped identity), or the inventory is `PARTIAL` and the Workload has no positive assessment yet. |

`data.selection` lists each `caller_localities` entry with its `evaluation`, sorted by identity. Every `UNKNOWN` identity, whether named in `caller_localities` or only in `compare`, adds the envelope limitation `SELECTION_NOT_ESTABLISHED` (D16.10), so the outcome is at best `PARTIAL`. No new graph read is made for selected identities. In particular, I3 does not query the capture inventory for an identity that no v2 candidate resolved to, so a valid but unexercised Workload stays `UNKNOWN`.

### Comparison (I3 §10; §17 item 6)

For `compare = [A, B]` (A, B in request order):

| Field | Content |
|---|---|
| `scopes` | A and B, each with its `evaluation` from the table above |
| `in_both` | Memberships `(provider Service or unresolved, Operation)` positive in both, with each side's qualification and assertion/assessment IDs |
| `only_in_first`, `only_in_second` | Positive in one scope; the label means "positively evidenced here", never "absent there" |
| `qualification_differs` | Subset of `in_both` whose qualifications differ |
| `completeness` | `COMPLETE` only if the inventory is `COMPLETE` **and** neither scope is `UNKNOWN`; `PARTIAL` if the inventory is `PARTIAL`; `NOT_ESTABLISHED` if the inventory is `COMPLETE` but a scope is `UNKNOWN`. Anything but `COMPLETE` adds `COMPARISON_INCOMPLETE`. |

Sorted by provider Service ID, Operation ID, then assertion ID. A positive relation in A against an `UNKNOWN` or `EVALUATED_NO_POSITIVE` B is listed in `only_in_first` and is never a contradiction, an exclusivity or an absence in B. C1 and C2 are different snapshots and are never compared within one answer (I3 §10).

## D11 — Same-snapshot scoped resolver (`mode: "evidence"`; I3 §12; §17 item 7) — owner decision on capture refs

The evidence mode resolves **both** kinds of ref a locality answer emits: scoped v2 refs and the capture/owner refs of its pairs and assessments. Legacy `get_evidence` admits Kubernetes `:Evidence` only when it is in `reachable_kubernetes_evidence_ids`, which is built from public deployment claims (`repository._EVIDENCE_BY_ID_QUERY`). A caller-local `CALLS` can rest on Pod/owner evidence outside that set, so routing these refs to `get_evidence` (as rev 1 of this record did) would advertise a drill-down that reports them missing.

| Item | Frozen decision |
|---|---|
| Request | `subject_service_id` (path on REST), required `snapshot_id`, `refs`: 1–20 distinct, sorted, non-empty IDs. Optional `object_operation_id`. A ref matching `evidence:otel:calls-scoped:v2:<64 hex>` is a **v2 ref**; any other ref is treated as a **capture ref**. |
| Snapshot | Everything is resolved in one stable-snapshot attempt; a non-current `snapshot_id` is `NOT_ANSWERED` / `SNAPSHOT_NOT_AVAILABLE`. Never latest data. |
| v2 authority | A v2 ref resolves only if the record exists at that snapshot, its `subject_id` is `subject_service_id`, and (if given) its `object_id` is `object_operation_id`. |
| Capture authority | A capture ref resolves only if, at that snapshot, it is a Kubernetes-sourced `:Evidence` **and** it is in the `evidence_refs` of either (a) an `InfrastructureContribution` of a `KUBERNETES_POD` whose `captured_resource_uid` is the `caller_pod_uid` of a v2 record of `subject_service_id` (and of `object_operation_id`, if given), or (b) a `WORKLOAD_OWNS_POD` claim contribution whose Pod is such a Pod. These are exactly the reads I2 uses for pairs (D13.6). The rule does not depend on which capture an answer selected, so it never recomputes a pair, an owner or a claim. |
| Not found | Any ref that fails its rule is `NOT_FOUND`, with no detail that distinguishes "absent" from "belongs to another caller" or "not capture evidence". A declared or legacy OTel evidence ID is therefore `NOT_FOUND` here; it is resolved by `get_evidence` as before. |
| v2 fields | `id`, `subject_id`, `object_id`, `environment`, `bucket_utc_day`, `caller_cluster_uid`, `caller_pod_uid` (the v2 contract §1 names), `first_seen`, `last_seen`, `observation_count`, `correlation_mode`, `sample_trace_ids` (the v2 contract's sorted ≤5), `key_rule_id`/`version`, `normalization_rule_id`/`version`. No raw span, Resource, host or IP, and no query-time Workload resolution (that lives in the query answer). |
| Capture fields | The existing sanitized public evidence-row projection that `get_evidence` already returns for Kubernetes evidence (no new field), plus `ref_kind`: `POD_CAPTURE` or `OWNER_CAPTURE`. |
| Isolation | v2 is read only through the D1 (I2) reader path. `get_evidence`, `/api/evidence/*`, the legacy resolver Cypher and its `reachable_kubernetes_evidence_ids`, NL labels and v0.5 claims are **unchanged**: they still cannot return v2, and they do not gain the capture refs this mode admits (negative tests in I3.3). #323 is not widened. |
| Outcome | `ANSWERED` if every ref resolved; `PARTIAL` if some are `NOT_FOUND`; `NOT_ANSWERED` / `INSUFFICIENT_EVIDENCE` with data if none resolved. |

## D12 — MCP argument closure (I3 §13) — Q2 owner decision

The new tool rejects every top-level argument other than `request` **before dispatch**, with a test over the real negotiated transport. Unknown fields inside `request` are already rejected by `extra="forbid"`. The three v0.5 tools keep today's behaviour (`tests/unit/test_mcp_discovery.py` documents that a top-level extra is dropped), because I3 §2 keeps them compatible. I3.3 also corrects `docs/mcp.md` and the `app/mcp/server.py` docstring, which today say all tools reject such arguments.

## D13 — Unchanged and deferred

- The D16 default (`telemetry.scoped-evidence.enabled = false`) is not flipped by I3. With the flag off there is no v2, so the query answer is the D9 no-positive case.
- No change to I1/I2 dispositions, identities, vectors, the conformance oracle or the rehearsal fixture.
- I3.2 adds no cache across snapshots and no ADR 0012 compaction.
- #323 (NL-to-Kubernetes-Evidence exposure) is not widened and not resolved here.

## D14 — Parent §18 exposure table

| Semantic field / variant | Canonical / internal source | Service | REST | MCP | Published schema | Evidence resolution |
|---|---|---|---|---|---|---|
| Positive Workload-local Operation assessment | I2 `QualifiedLocalEvidenceAssessment` | `get_service_dependencies_by_locality` | POST `…/dependencies/by-locality` | tool, `mode: query` | `…-answer.schema.json`, `localities[].assessments[]` | v2 IDs and `capture_evidence_refs` via `mode: evidence`; declared IDs via `get_evidence` |
| Provider Service group | D8 projection over I2 assessments + fenced `PROVIDES` | same | same | same | `localities[].provider_groups[]` | member refs only |
| Unresolved owner | D8 | same | same | same | `localities[].unresolved_owner_operations[]` | member refs only |
| Candidate + pair inventory | I2 `CandidateResult`/`PairResult`, `CandidateLimitation` | same | same | same | `candidates[]` | pair `evidence_refs` (capture/owner) via `mode: evidence` (D11 capture authority) |
| Inventory bounds/completeness | D4, D5, D7 | same | same | same | `inventory` | — |
| Selected-scope status | D10 selection | same | same | same | `selection`, `comparison.scopes` | — |
| Comparison | D10 comparison | same | same | same | `comparison` | — |
| Scoped v2 record | `ScopedObservedCallV2` via the I2 reader | `resolve_scoped_locality_evidence` | POST `…/by-locality/evidence` | tool, `mode: evidence` | `ScopedLocalityEvidenceData` | is the resolution |
| Capture/owner evidence | Kubernetes `:Evidence` via the D13.6 Pod/owner reads | `resolve_scoped_locality_evidence` | POST `…/by-locality/evidence` | tool, `mode: evidence` | `ScopedLocalityEvidenceData` | is the resolution (D11 capture authority) |
| Refusals and limitations | D9 | both | 200 / 422 | `NOT_ANSWERED`, validation error | envelope `limitations` | — |

## D15 — Cases I3.1c must author (from the PR #386 review)

In addition to the I3 §14 table, the independent I3.1c matrix includes these cases, with expected answers written from this record, not from code:

| # | Case | Expected |
|---|---|---|
| R1 | `S = 2,001` accepted capture sources | `NOT_ANSWERED` / `RESULT_LIMIT_EXCEEDED` stating `S`; no candidate read, no cursor |
| R2 | `S = 5`, 500 candidates | internal page `k = 400`; at most 2,000 pairs; `PARTIAL` with a cursor at the 400th v2 ID |
| R3 | explicit current `source_selector` | `S = 1`, `k = 500`; a stale selector gives `S = 0`, zero pairs and the D13.3 disposition |
| R4 | `compare` with an invented `WorkloadIdentity` on a complete inventory | that scope `UNKNOWN`; comparison `NOT_ESTABLISHED`; `COMPARISON_INCOMPLETE` + `SELECTION_NOT_ESTABLISHED`; `PARTIAL` |
| R5 | I2 D4 S04 construction: candidate V (P1) has source A `APPLICABLE` at W1 and source B (K2, same Pod UID) `CONFLICT` [`LOCALITY_CLUSTER_UID_CONFLICT`]; no other v2 for W1; a second candidate is positive at W2; `compare = [W1, W2]`, complete inventory | W1 `EVALUATED_NO_POSITIVE`, W2 `POSITIVE`; W2's memberships in `only_in_second`; comparison `COMPLETE`; candidate V and both pairs listed unchanged; no absence or contradiction wording |
| R6 | the same as R5 on a `PARTIAL` inventory (a continuation exists) | W1 `UNKNOWN`, not `EVALUATED_NO_POSITIVE`; comparison `PARTIAL` |
| R6b | `compare` naming a Workload that appears only as an `INAPPLICABLE` (wrong environment/day) candidate's would-be owner, complete inventory | `UNKNOWN`: phase 3 resolves no Workload, so the identity is never established by the inventory |
| R7 | evidence mode with a capture ref of a positive assessment whose Pod/owner evidence is **not** deployment-reachable | the ref resolves here (`POD_CAPTURE`/`OWNER_CAPTURE`); legacy `get_evidence` for the same ID is still not found |
| R8 | evidence mode with a capture ref of another caller's Pod, a declared evidence ID, and a legacy OTel v1 evidence ID | each `NOT_FOUND`, indistinguishable |

## D16 — I3.1b clarifications (added in I3.1b; additive, D1–D15 unchanged)

These are decisions taken while publishing the draft schemas. D16.4 is an owner decision; the rest settle representation details that D1–D15 leave open. The models are `app/architecture_intelligence/locality_contracts.py`, and the generated, frozen files are `schemas/architecture_intelligence/v0.6/service-dependencies-by-locality-{request,answer}.schema.json`.

| # | Clarification |
|---|---|
| D16.1 | **Evidence-mode limitation.** D11's `PARTIAL` (some refs `NOT_FOUND`) and `NOT_ANSWERED` (none resolved) both carry `INSUFFICIENT_EVIDENCE`. So the outcome rule is mode-specific: for `query`, `INSUFFICIENT_EVIDENCE` means `NOT_ANSWERED` (D9); for `evidence`, it is `PARTIAL` while any ref resolved. No new code is added. |
| D16.2 | **Request shape.** The published request schema is the MCP `request` argument itself: a union discriminated on `mode` (`LocalityQueryRequest`, `LocalityEvidenceRequest`). The REST bodies (D1: no `subject_service_id`, and no `mode` because the route selects it) are derived from these in I3.3 and are not separate published files. |
| D16.3 | **Assessment placement.** `localities[].assessments[]` carry each I2 assessment's own values unchanged (`assertion_id`, `assessment_id`, Operation, qualification, observation, declared IDs, selected captures, capture refs, source limitations, rules). Its subject, relation, environment, window, caller Workload and snapshot are carried **once**, by `request_context`, the locality's `workload` and the envelope's `snapshot`, so they cannot disagree. |
| D16.4 | **Provider filter (owner decision).** With `provider_service_id`, `localities[]` keeps only Operations owned by that provider plus unresolved-owner Operations; a Workload left with none is not listed. `selection` and `comparison` are evaluated on that filtered projection. `candidates[]` stays the complete, unfiltered inventory. "No positive relation to this provider" is never an absence. |
| D16.5 | **Ordering.** Pairs are sorted by `(source_instance_id, revision)`; `admission`, reasons, limitation codes and every ID list are sorted by value and duplicate-free; `compare` and `comparison.scopes` keep the request order (first, second); `selection` follows `caller_localities`; envelope limitations are sorted by code, one per code. |
| D16.6 | **Inventory fields.** `considered_capture_source_count` is D4's `S`, and `bounds.candidate_page_size` is D4's `k`, checked as `min(500, ⌊2000/S⌋)` (500 when `S = 0`). An explicit `source_selector` gives `S ≤ 1`. `evaluated_sources` are exactly the sources of the listed pairs. |
| D16.7 | **Evidence refs.** Each ref is an opaque, non-empty ID with no whitespace. A ref matching the v2 pattern can only resolve as `SCOPED_V2`, any other ref only as `POD_CAPTURE`/`OWNER_CAPTURE` with Kubernetes evidence. `NOT_FOUND` carries no kind and no record. |
| D16.8 | **Cursor form.** A cursor must decode to exactly the five D5 fields **and** re-encode to the same string, so a non-canonical encoding of a valid payload is a validation error, as is anything undecodable. A `next_cursor` must carry the answer's own `snapshot_id`. |
| D16.9 | **Schema-expressible versus model-only.** Everything JSON Schema can state (closed objects, enums, consts, patterns, bounds, `uniqueItems`, `mode`↔payload, data-null↔refusal, outcome↔limitations, pair phase/Workload rules, NOT_FOUND/kind/record rules) is in the published schema and tested to fail **both** validators. Ordering, counts, cross-references, D10 selection status and comparison derivation, D16.4 and the cursor's decoding are model-only and tested as such. |
| D16.10 | **`SELECTION_NOT_ESTABLISHED` from `compare` (PR #387 review).** The code is derived from every `UNKNOWN` scope in `selection` **and** in `comparison.scopes`, so a `compare`-only request naming an unestablished identity (D15 R4) carries both `COMPARISON_INCOMPLETE` and `SELECTION_NOT_ESTABLISHED`. The `UNKNOWN`/`NOT_ESTABLISHED` semantics are unchanged. |
| D16.11 | **Continuation pages (PR #388 review; owner decision; corrects I3.1b to match D7 item 3).** `inventory.continuation` is `true` when the request carried a `cursor`. Such a page never evaluated the whole inventory, so `completeness` is `PARTIAL` exactly when `i2_truncated`, a cap was hit **or** `continuation` is true, and `next_cursor` is present exactly when more candidates remain. The final page of a cursor walk is therefore `PARTIAL` / `INVENTORY_INCOMPLETE` with `next_cursor: null`. Its groups are `lineage_complete: false`, and it can never report `EVALUATED_NO_POSITIVE` or a `COMPLETE` comparison for a Workload whose positives were on an earlier page. |

## D17 — I3.2 implementation clarifications (added in I3.2a; additive, D1–D16 unchanged)

These settle representation and ordering details that D1–D16 leave open, so that I3.2 can implement them as written. None of them changes an I1/I2 disposition, identity or vector, the I3.1c oracle or the 0.6 schemas.

| # | Clarification |
|---|---|
| D17.1 | **Refusal precedence.** When more than one refusal applies, request-intrinsic refusals win over state-dependent ones: `UNSUPPORTED_REQUEST` (phase 1) > `CURSOR_QUERY_MISMATCH` > `SNAPSHOT_NOT_AVAILABLE` > `RESULT_LIMIT_EXCEEDED`. The answer still carries the fenced current `SnapshotRef`, except for `SnapshotUnstable` (`snapshot: null`). A phase-1 refusal or a cursor mismatch reads no capture or candidate, and `RESULT_LIMIT_EXCEEDED` reads no candidate (D6). |
| D17.2 | **What the presentation caps count.** The 50-Workload and 200-membership caps (D4) count the **presented** projection, after the D16.4 `provider_service_id` filter and the `caller_localities` filter. I3 finds the longest prefix of complete candidates within the caps by re-running I2's pure `assess` on prefixes of the same fenced read. This relies on `assess` being monotone in the prefix: adding a candidate never removes a Workload or a membership. A unit test pins that property. |
| D17.3 | **Lineage on a continuation page.** On a page requested with a `cursor`, every assessment's `observation.lineage_complete` is `false`, even when I2 did not truncate that page. D7 item 3, D16.11 and the `LocalityEntry` validator require this. The value is set in the 0.6 presentation only; I2's `LocalObservation` and its vectors are unchanged. |
| D17.4 | **The I2 read hook.** `scoped_evidence_repository.read_applicability_page(runner, request, *, after_id, page_size_for)` runs inside the caller's stable-snapshot `read_extra`. It reads the accepted captures first, computes `S` (D4 step 1), and calls `page_size_for(S)`. A return of `None` stops the read before any candidate is read (D6); otherwise the value is the candidate page size `k` (1–500). `read_scoped_applicability` and `assess_local_calls` gain `page_size` (default 500, so I2 behaviour is unchanged). `read_provider_owners` reads the v0.5 `PROVIDES` rows and their evidence under the same fence (D8). |

## Traceability

| I3 requirement | Decision |
|---|---|
| §17.1 exposure and tool count; §13; parent §17, §19 | D1, D12 |
| §17.2 versioning; §11; parent §18 | D2, D14, D16 |
| §17.3 inventory and selectors; §5, §6 | D3, D10 |
| §17.4 continuation and budget; §7 | D4, D5, D6, D7, D15 |
| §17.5 provider projection; §8; I1 §5.1 (L04a, L32a, L32b) | D8 |
| §17.6 completeness and comparison; §9, §10 | D9, D10, D15 |
| §17.7 scoped resolver; §12 | D11, D14, D15 |
| §17.8 cost and qualification evidence; §14 | D4 (values are not SLOs); I3.1c matrix; I3.4 measurements |
| §2 compatibility; D16 | D1, D12, D13 |
| I3.2 implementation details (§7, §10; D4–D9) | D17 |
