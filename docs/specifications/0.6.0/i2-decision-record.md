# AIP v0.6.0 I2 — Decision Record (I2.1)

**Status:** I2.1 decision table under review. Once this PR merges, the decisions below are **frozen** for I2 implementation. Each one fills a gap that the [I2 specification](i2-scoped-evidence-and-qualified-local-assessment.md) §3/§17 left to "an I2 review before the corresponding semantic code is enabled". None of them reopens an accepted I1 or parent semantic. Where a decision needs an amendment to accepted text, that amendment is stated here and carried in the same PR (D5).  
**Release / increment:** `v0.6.0` — Locality-Aware Current State / I2, slice I2.1  
**Governing specification:** I2 specification revision 0.4, merged in PR #312 (merge `6cebe35b1c520f754c6306a5ff9629c89ace6dc5`). The owner treats it as **accepted**, and this PR changes its status line accordingly (status only).  
**Entry baseline:** `main` at `059ac63` (PR #318).  
**I1 closure:** PR #311, merge `7a949cd3046e91ddd6ea67036b6bf47c241ed037`. PR #318 wrote that SHA into [`i1-completion-record.md`](i1-completion-record.md) (merge `059ac63`); this satisfies the I2 header requirement to record the I1 closure SHA. The I1 oracle ([`i1-vectors/conformance-expected.json`](i1-vectors/conformance-expected.json), the dossier and the vectors) is unchanged.

The I2.1 work is cut into three PRs:
- **I2.1a** (this record);
- **I2.1b** (the fail-closed NL graph-reachability gate, D2);
- **I2.1c** (the CLIENT carrier and guards I-1 to I-5, with no persistence).

The owner merges each before the next starts.

---

## D1 — v2 storage and isolation (I2 §6; §17 item 1)

| Item | Frozen decision |
|---|---|
| Label | `ScopedObservedCallV2`, an internal label and not a public contract |
| Constraint | `CREATE CONSTRAINT scoped_observed_call_v2_id IF NOT EXISTS FOR (v:ScopedObservedCallV2) REQUIRE v.id IS UNIQUE` in `app/graph/schema.py`, added in I2.2 |
| Properties | Exactly the v2 contract §1 identity fields, `id`, and the §3 fields, including the rule IDs and versions. Nothing else, and no raw Resource. |
| Forbidden | The `:Evidence` label, **any** incident relationship, and `owner_source_ids`. I2.2 must test each of these directly, including after a declaration or Kubernetes reimport and removal. |
| Reads | A dedicated I2 reader in `app/architecture_intelligence/`. `_EVIDENCE_QUERY`, `read_evidence_rows`, `read_public_evidence_list_rows`, `read_public_evidence_row` and `_RELATION_QUERY` are unchanged and must never return v2 (negative tests). |
| NL reachability | Not in `KNOWN_NODE_LABELS` or the NL approved set (D2) |
| Enablement flag | New config field `telemetry.scoped-evidence.enabled`, default **`false`**. It gates every v2 write. It may only be set to `true` in tests until the I2 §11 pre-enablement gates (a)–(f) pass, and I2.5 flips the default. With the flag off, the graph, snapshot and every v0.5 answer are byte-identical to the baseline. |

## D2 — Fail-closed NL graph reachability (I2 §6; pre-enablement gate (f))

**Scope of the exposure.** The only executor of LLM-generated Cypher is `ArchitectureQuestionService.ask` (`app/ai/question_service.py`), reached from `POST /api/query` and the UI `GET /query`. It is not on any MCP tool. On the baseline, `validate_cypher` and `SemanticQueryValidator` accept:
- unlabeled patterns (`MATCH (n)`);
- label expressions (`(n:Service|X)`);
- backtick labels, which the stripper blanks out.

That already reaches internal labels such as `AipInternalState`, `SourceState` and `Infrastructure*`, and would reach v2.

**Approved label set:** the current eight `KNOWN_NODE_LABELS`: Service, Operation, Queue, Message, Schema, Evidence, Topic, Subscription.
- `Evidence` stays approved because the generator prompt steers evidence lookups to `MATCH (e:Evidence)`.
- **Disclosed exposure (owner decision):** Kubernetes-sourced `Evidence`, which is hidden from the public evidence API, is reachable through NL today. That is a separate follow-up issue and not an I2 change.

**Rule 1 — syntactic check.** Every node pattern must satisfy one of:
- (a) only approved labels in the plain `:A:B` form;
- (b) a variable bound with an approved label **earlier** in query order;
- (c) an endpoint of a relationship pattern with an explicit known type. v2 and internal nodes have no relationships, so a typed expansion cannot reach them.

The check rejects:
- label expressions `| & ! %` and dynamic `$` labels;
- backtick labels (fail-closed);
- untyped relationships with an unbound endpoint;
- any `labels(` call.

Parentheses count as node patterns only in pattern context, so function calls are not node patterns.

**Rule 2 — plan backstop.** In the same read-only session, the service runs `EXPLAIN <final query>` and walks the plan. Every leaf operator must be in an allowlist:
- node label scans and index seeks/scans on approved labels;
- typed relationship scans on known types;
- `Argument`.

Anything else is rejected. That covers `AllNodesScan`, id and elementId seeks, all-relationship scans, operators whose details can't be parsed, and unknown operators. It is pinned to `neo4j:5.26.31`.

**Other elements of the gate:**
- **Prompt:** the generator prompt gains the rule "label every node variable".
- **Error path:** rejections use the existing `CypherValidationError` path.
- **Unchanged:** authorized questions that are already fully labeled stay unchanged.

## D3 — Candidate reader (I2 §8.1; §17 item 6)

The reader filters by exact caller Service ID + `CALLS` + an optional exact Operation ID **only**. There is no environment, UTC-day, `last_seen`, cluster or Workload prefilter, so L10b and L17d reach phase 3. It reads in ascending v2 `id` order under one revision fence. Pages hold **500** records, and an explicit `truncated` flag plus a count is returned whenever the scan stops early. I3 freezes the public bounds.

## D4 — Source selection and one-candidate roll-up (I2 §8.1)

**Selection:**
- **Explicit selection** evaluates exactly the named, currently committed contribution. An absent, stale or rejected selector gives candidate `INSUFFICIENT_EVIDENCE` plus limitation `NO_SELECTABLE_COVERING_SOURCE`.
- **Implicit selection** admits a source by rule 1 (it contains the exact Pod UID, under any cluster) or rule 2 (equal `clusterUid` **and** the D5-persisted complete `scope.namespaces` contains the admissible CLIENT `client_namespace`). Every other source is omitted.

**Roll-up:**
- zero covering sources → candidate `INSUFFICIENT_EVIDENCE` with `LOCALITY_LOCAL_COVERAGE_UNAVAILABLE` plus limitation `NO_SELECTABLE_COVERING_SOURCE`;
- one covering pair → that pair's result exactly;
- several covering pairs → `CONFLICT` > `AMBIGUOUS` > `APPLICABLE` (one exact Workload) > common disposition > `INSUFFICIENT_EVIDENCE`, with every pair kept as a source-specific limitation, as I2 §8.1 states.

**Limitation name.** `NO_SELECTABLE_COVERING_SOURCE` is an internal I2 **limitation code** and not a `LOCALITY_*` reason; no I1 amendment is needed. When the answer has no positive local CALLS, it falls back to `LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION` + `LOCALITY_LOCAL_COVERAGE_UNAVAILABLE`.

**Frozen test specifications S01–S06.** These are the I2 §8.1 regression rows, authored here independently; I2.3 makes them executable. Shared inputs: P1 is the v2 caller Pod, with CLIENT cluster K1 and CLIENT namespace `shop` unless stated.

| ID | Current accepted sources | Admitted pairs | Candidate summary | Pair results kept |
|---|---|---|---|---|
| S01 | A: K1, scope [`shop`], P1 → W1. B: K1, scope [`billing`], no P1 | A | `APPLICABLE` W1 | A: `APPLICABLE` |
| S02 | A as in S01. B: K2, scope [`shop`], no P1 | A | `APPLICABLE` W1 | A: `APPLICABLE` |
| S03 | A as in S01. B: K1, scope [`shop`], no P1 | A, B | `APPLICABLE` W1 | A: `APPLICABLE`; B: `UNRESOLVED` [`LOCALITY_CAPTURE_MISSING_POD`] |
| S04 | A as in S01. B: K2 capturing the same Pod UID P1 | A, B | `CONFLICT` | A: `APPLICABLE`; B: `CONFLICT` [`LOCALITY_CLUSTER_UID_CONFLICT`] |
| S05 | C2 only: K1, scope [`shop`], P1 absent | C2 | `UNRESOLVED` [`LOCALITY_CAPTURE_MISSING_POD`] | C2: same |
| S06 | Namespace-scoped sources only, none containing P1; the CLIENT namespace is missing | none | `INSUFFICIENT_EVIDENCE` [`LOCALITY_LOCAL_COVERAGE_UNAVAILABLE`] + limitation `NO_SELECTABLE_COVERING_SOURCE` | — |

All six cases use the whole-day window D, environment `production`, and captures on day D (phases 1–3 pass). The v2 P1 record is retained in every case.

## D5 — Capture scope under the fence and in the fingerprint (I2 §8.1 stop condition; amendment)

**Baseline gap, verified at `059ac63`:**
- An envelope's `scope.namespaces` is used only at mapping time (`app/ingestion/kubernetes_adapter.py:90`). The graph stores only a `scope_definition_digest` on `SourceState`/`CurrentInventory`, and neither is part of the canonical state.
- Kubernetes evidence refs use the operator-declared `metadata.revision` (`kubernetes_adapter.py:101`), not a content digest. So a namespace-scope change is not provably visible in the snapshot.
- I2 §8.1 requires a stop here for a reviewed decision.

**Decision (owner):**
1. **Persist.** For every accepted Kubernetes source, the importer records on its `SourceState` node, in the same import transaction:
   - `capture_scope_namespaces` (sorted);
   - `capture_cluster_uid`;
   - `capture_revision` (the envelope `metadata.revision`);
   - `capture_evidence_mode`;
   - `capture_captured_at` (the raw envelope value).

   These properties are readable under the revision fence. A rejected import (L29) does not overwrite them.
2. **Conditional second key.** When **at least one** v2 record exists, the canonical state also gains `scoped_capture_scopes_v2`. It is a list sorted by `source_instance_id`, with exactly these fields: `source_instance_id`, `discovery_scope_id`, `revision`, `cluster_uid`, `namespaces`, `evidence_mode`, `captured_at`. With no v2 records the key is absent, so every no-v2 state, `_CANONICALIZATION_VERSION = 3` and the golden pin stay byte-identical.
3. **Amendments carried in this PR:**
   - I2 §6 ("the only new canonical-state input from v2");
   - I2 §11 ("add only I1 contract §8's … key");
   - I1 v2 contract §8 ("gains **one** top-level key").

   Each now also admits `scoped_capture_scopes_v2` under the same conditional rule. The I1 fragment vector and the oracle are unchanged, and I2.5's independently expected full after-`snapshot_id` vector covers both keys.

   **Why `captured_at` is in the key.** It is a disclosed deviation from the approved plan's six-field list. Phase 3 evaluates each admitted source's real `capturedAt`, including a covering source that does **not** contain the Pod (S03, S05). The existing `deployment_captured_pods` state carries `captured_at` only per captured Pod, so without this field that input would be outside the fingerprint.
4. **Revision advancement.** Persisting the properties is not enough, because the importer bumps the revision only when node, relation or claim content changes (`app/graph/importer.py:954-970`). A scope-only change would therefore alter the new key without moving the fence. In `_import_source_tx`:
   - (a) Read the source's persisted `capture_*` properties before the `SourceState` write and compare them with the new values. The comparison runs even when the replay decision is a no-op; a replay no-op that changes these properties is **not** a no-op for this rule.
   - (b) If they differ, first acquire the write lock on the revision singleton (`AipInternalState`), for example with a no-op `SET` on it. Then, still in the same transaction, check whether any `ScopedObservedCallV2` node exists.
   - (c) If one does, call `bump_revision(tx)`, unless the transaction already bumps.

   Taking the lock before the v2 check serializes this transaction against a concurrent ingestion unit whose first v2 write also bumps the singleton. The import therefore cannot miss a v2 record that commits in the meantime.

   With no v2 present, a scope-only change still does not bump, so no-v2 v0.5 revision behaviour is unchanged. Source removal already bumps unconditionally and deletes `SourceState` (`importer.py:1088`), which drops the source from the key.

   **Required regressions (I2.2 / I2.5):**
   - a scope-only reimport with v2 present bumps the revision and changes the snapshot;
   - the same reimport without v2 does not bump the revision;
   - a replay-no-op scope change is covered;
   - a concurrent stable read around a scope-only reimport never sees two different `scoped_capture_scopes_v2` values at one revision;
   - an import that races the first v2 unit bumps the revision.

## D6 — Ingestion unit and transactions (I2 §6, §7; §17 item 3)

- **Unit:** one decoded `/v1/traces` POST and its `ObservationBatch` form one unit. The unit is committed in **one** `execute_write` with one `bump_revision`, exactly as today (`app/telemetry/aggregator.py:243-248`), and the v1 facts and eligible v2 seeds go in that transaction.
- **Atomicity:** a v2 write failure rolls back the whole unit. The driver's transient-error retry re-runs the whole transaction function.
- **Cross-batch pairs** contribute in the POST in which they resolve.
- **Repeated POSTs:** a separately repeated successful POST is a new unit and counts again in v1 and v2. This is disclosed; there is no v2-only deduplication.
- **Within one unit:** each accepted interaction is folded once.

## D7 — Transition report (I2 §7; §17 item 4)

**Name and form:** `aip-scoped-evidence-transition-report/1`, with I1's three categories. It is operational: not architecture evidence, not snapshot input, and not NL-reachable.

**Counters:**
- stored in internal `ScopedEvidenceTransitionCounter` nodes, keyed by (`stream_id`, `environment`, `utc_day`, `category`, `primary_reason` or `—`);
- each carries `count` and `last_revision`;
- updated in the same unit transaction;
- counts are exact and never truncated;
- no relationships and not in NL-approved labels;
- retention: kept, since cardinality is bounded by stream × environment × day × category × reason.

**Diagnostic samples:**
- logged only, at INFO, sanitized (trace ID plus sorted reason codes; no attribute values);
- at most **20 per reason per unit**, with an overflow count logged per reason.

**Availability:** an internal repository reader returns the report. There is no public endpoint in I2; I3/I6 decide exposure.

## D8 — Cutover ledger, durable legacy membership and legacy-only status (I2 §7.1)

**Scope: graph-scoped, one stream per graph.** v1 evidence carries no stream attribution (`evidence:otel:{env}:{day}:{hash}`, B1), so membership can be proven only per graph. In v0.6 an AIP graph has exactly one configured `telemetry.scoped-evidence.stream-id` (D10). Overlapping streams writing one graph are **not supported** in v0.6 and are disclosed as such.

**Ledger:**
- One internal `ScopedEvidenceCutover` singleton per graph, with a uniqueness constraint.
- It is written in the first unit processed with the flag enabled, and holds:
  - `stream_id`;
  - `enabled_at_revision`;
  - `pre_enablement_v1_bucket_count`;
  - `pre_enablement_v1_bucket_digest`: SHA-256 over the sorted, newline-joined v1 `evidence:otel:` IDs that exist before that unit. It is used as an integrity check of the membership below.
- Immutable afterwards.

**Durable membership:**
- In the same cutover transaction, one internal `ScopedEvidenceLegacyBucket` node is written per pre-enablement v1 bucket, with a uniqueness constraint on `id`. Each holds:
  - `id`, which is the v1 evidence ID;
  - `cutover_revision`;
  - `mixed_at_revision`, initially `null`.
- The nodes have no relationships, no `owner_source_ids`, no NL reachability and no canonical-state input.
- Afterwards, whenever an enabled unit persists **any** v1 contribution, with or without v2, to a bucket that has a membership node, the same transaction sets `mixed_at_revision` if it is still `null`. That bucket is then no longer legacy-only.
- The membership survives restarts because it lives in the graph and not in process memory.
- Cost: one node per pre-existing v1 CALLS bucket, disclosed in the I2 completion record's cardinality measurements.

**Report classification (D7):**

| Situation | Classification |
|---|---|
| Membership node with `mixed_at_revision = null` | `LEGACY_UNSCOPED`, counted in v1 buckets, with the as-of revision |
| Membership node with `mixed_at_revision` set | *mixed*, an operational diagnostic and not a fourth category |
| No cutover ledger | *unknown*, never legacy-by-absence |
| Configured `stream-id` differs from the ledger's | *unknown* for all history, with no second cutover and no reclassification |
| Membership count or digest does not match the ledger | *unknown* |

**Required regressions (I2.2):**
- pre-cutover-only;
- a post-cutover v1 contribution makes a bucket mixed, both when v2 was written and when it was refused;
- restart, with the membership re-read from the graph;
- a changed `stream-id` gives unknown;
- a repeated import leaves membership unchanged;
- a v1-only bucket plus an unrelated `RuntimeIdentityObservation` stays legacy.

**`LOCALITY_LEGACY_V1_UNSCOPED` is not emitted in v0.6.** Snapshot-bound proof would require ledger or membership state in the canonical state, which would change the no-v2 pin. By I2 §7.1's fallback, answers use only `LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION` + `LOCALITY_LOCAL_COVERAGE_UNAVAILABLE`. The membership is operational provenance for the report only.

## D9 — Assertion and assessment-instance identity (I2 §9; §17 items 2, 5)

The assessment is read-side only; no `LOCAL_ASSESSMENT` node is materialized. Both IDs are built with canonical JSON (the `canonical_json.py` convention) and full SHA-256.

| ID | Prefix | Canonical fields |
|---|---|---|
| Assertion | `aip:local-assertion:v1:` | `version: 1`, `subject_service_id`, `relation_type: "CALLS"`, `object_operation_id`, `environment`, `first_utc_day`, `last_utc_day`, `workload: {cluster_uid, namespace, kind, uid}` |
| Assessment instance | `aip:local-assessment:v1:` | `version: 1`, `assertion_id`, `snapshot_id`, `capture_revisions` (sorted), `rules` (sorted `{id, version}` list) |

- **Negative candidates:** a candidate without a unique resolved Workload gets **no** assertion ID. It is reported as a candidate limitation keyed by its v2 ID and `snapshot_id`.
- **Lineage:** v2 IDs are lineage and never an assertion key.
- **Vectors:** independently authored vectors are frozen in I2.4 before its implementation.
- **Scope:** neither ID is a public I3 wire contract.

## D10 — Source identity and revision (I2 §7; §17 item 4)

| Input | Source identity | Revision |
|---|---|---|
| Live OTLP POST | New config field `telemetry.scoped-evidence.stream-id`: a non-empty string, default `"otlp-http"`, identifying this AIP instance's `/v1/traces` stream | The committed graph revision of the unit (`bump_revision`) |
| Offline replay corpus | The corpus file's SHA-256 | The corpus SHA-256 plus the 1-based line index |

No Kubernetes or architecture source revision is ever invented for telemetry.

## D11 — Deferred to later slices (not open blockers)

- **I2.6:** rehearsal harness image and tool digests, and capture provenance.
- **I2.5:** the full after-`snapshot_id` vector, covering both conditional keys.
- **I2.4:** assertion and instance vectors.

---

## Traceability

| I2 requirement | Decision |
|---|---|
| §3 legacy isolation; §17.1 | D1, D2 |
| §3 candidate selection; §17.6 | D3 |
| §3 multiple captures / no covering source; §8.1 regression rows | D4 (S01–S06) |
| §8.1 scope under the fence (stop condition) | D5 |
| §6 one POST transaction; §17.3 | D6 |
| §7 report; §17.4 | D7, D10 |
| §7.1 legacy-only proof; durable membership, restart and stream scope | D8 |
| §8.1 same-snapshot fence for scope changes | D5 item 4 |
| §9 identity; §17.2, §17.5 | D9 |
| §15 I2.1: record the I1 closure SHA | Header |
