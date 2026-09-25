# I5 Final-Candidate Finding Ledger (v0.5.0, Slice 7)

This ledger covers **candidate `aa04a150965924bd23ecf0125bcf7095a3cf72d9`** (the #257 merge),
revalidated on 2026-09-25 from the one frozen checkout location. It rests on:
- the frozen dossiers #240 and #242;
- the lifecycle and coverage freeze #244;
- the corrections #243 and #246;
- the Slice 6 FIXes #254 and #255;
- the lifecycle re-freeze #256;
- the pre-run result-label freeze #257.

Every §9 row and every §13 item was rerun from clean state at this one candidate (I5 §12). The
Slice 5 ledger (`../finding-ledger.md`) is left unchanged as the record of candidate `174a17c`.

**Records:**
- `quarkus-super-heroes/results.md`, `apache-airflow/results.md` and `lifecycle/results.md`, with
  raw records under each `artifacts/`;
- `evaluation-artifacts/`;
- `suites/`, which holds the test-suite output at the candidate and the CI check-runs of the exact
  SHA.

## Coverage matrix, row by row (`../coverage-matrix.md`)

| # | Area | Outcome at `aa04a15` | Evidence |
| --- | --- | --- | --- |
| 1 | I1 lifecycle (real declarations) | **Pass on both targets: all 9 steps match**, with 84 checks against the ledger. Quarkus L2, L5 and L3 now pass on the corrected X (#256). The L4a/L4b/L6 labels frozen before the run (#257) all hold. | `lifecycle/results.md` |
| 2 | I1 lifecycle (regression) | Pass: `tests/unit` 2221 passed, `tests/integration` 466 passed | `suites/` |
| 3 | I2 offline discovery (upstream-derived) | Pass: `ACCEPTED_WITH_LIMITATIONS`, the complete inventory (13/13/1, 2 routes, all `DECLARED_MANIFEST`, no interaction), and the 13 `NO_QUALIFIED_POD_MATCH` exactly per object. **The `K8S_RESOURCE_UNSUPPORTED` list matches exactly per kind** (9/10/1/1/3/1 = 25, no other code). It cannot be attributed per object (F8, `DEFER`). | `quarkus-super-heroes/results.md` |
| 4 | I2 namespace-less rejection | Pass, **now publicly observed:** `REJECTED_INVALID` with `K8S_RESOURCE_INVALID`, in a `PARTIAL` run that did not commit | same |
| 5 | I2 captured resources and owner chain (independent capture) | Pass (`test_kubernetes_independent_capture.py`, in the integration suite) | `suites/` |
| 6 | I3 Path B and the name-only negative | Pass: 3 × `RESOLVED_CONFIGURED`, and both name-only pairs never resolve | `quarkus-super-heroes/artifacts/compare.txt` |
| 7 | I3 Path A (a gap on the real targets) | Fixture only; pass (`test_i3_cross_source_qualification.py`) | `suites/` |
| 8 | I3 Path C, conflict, ambiguity | Fixture only; pass | `suites/` |
| 9 | I4 positive | Fixture only; pass (`test_i4_pubsub_qualification.py`) | `suites/` |
| 10 | I4 negative (a consumer group is not a Subscription) | Pass: no Queue, Topic or Subscription fact or entity for Kafka `fights`, and the Kafka fixture passes | `quarkus-super-heroes/results.md`, `suites/` |
| 11 | Airflow messaging negative | Pass: no messaging fact or entity, and Celery stays `INSUFFICIENT_EVIDENCE` | `apache-airflow/results.md` |
| 12 | Public answers and provenance | Pass on both targets: Service = REST = negotiated MCP, one snapshot per read set, three tools, and zero writes (the Q-GRAPH digests are unchanged) | both `results.md` files |
| 13 | Public messaging-claim parity (a gap on the real targets) | Fixture only; pass (the `test_mcp_*_equivalence.py` tests and the I4 tests) | `suites/` |
| 14 | v0.4 Architecture Answer contract | Pass: 23 of 23 scenarios. **The two runs are byte-identical** (result sha256 `03dc173098a92806c3c32dc714219636b37a11ceeeb50231a855c7ec958bb92c`). The committed report is not refreshed, because that is I6's job. | `evaluation-artifacts/` |
| 15 | Import-report observability | **Resolved by F2 (#254):** every result label and diagnostic code in this ledger was read from the public `aip-import-report/1`. The residual per-object granularity for unsupported Kubernetes kinds is F8. | this ledger |

## §13 qualification matrix, item by item

| §13 item | Status at `aa04a15` |
| --- | --- |
| I1 lifecycle: every §10 scenario passes on both targets | **Holds** (row 1) |
| Quarkus REST: all `PROVIDES` and `CALLS` `CORRECT`, zero `INCORRECT_SUPPORTED` | **Holds**: 35 PROVIDES and 7 CALLS are `CORRECT`, and 0 are incorrect |
| Quarkus Kafka `fights`: no Queue, Topic, Subscription, `SENDS`, `PUBLISHES_TO` or `RECEIVES_FROM` fact; the legacy key creates no fact | **Holds**: both forbidden `queue:fights` facts are absent, there are no messaging entities, the relation types are PROVIDES, CALLS and schema edges only, and the two mechanisms are `UNSUPPORTED` |
| Quarkus Kubernetes: unmodified `REJECTED_INVALID`, nothing committed; derived `ACCEPTED_WITH_LIMITATIONS` with exactly its frozen limitations; Workloads `DECLARED_MANIFEST`; no interaction from Kubernetes | **Holds, with the F8 limitation**: the frozen limitation list matches exactly per kind and per count, and the per-object attribution of unsupported kinds is not observable (`DEFER`) |
| Quarkus `DEPLOYED_AS`: each Workload has its frozen outcome; name similarity never resolves; evidence drills down at the same snapshot | **Holds**: 3 × `RESOLVED_CONFIGURED`, both name-only pairs absent, and all 8 evidence refs (7 dependency claims and 1 `DEPLOYED_AS`) resolve at `aip:snapshot:v1:f01a35de…`, with 0 missing |
| Airflow: the selected `PROVIDES` `CORRECT`; Postgres `UNSUPPORTED`; roles `UNRESOLVED_IDENTITY`; Celery `INSUFFICIENT_EVIDENCE`; no guessed messaging | **Holds** (9/9; the classifications are as frozen) |
| Supporting evidence: the I2 capture, the I3 cross-source fixture, and the I4 ASB/GCP/Kafka fixtures pass | **Holds** (the suites at the candidate; the fixture digests match `../coverage-matrix.md`, asserted by `test_i5_lifecycle_freeze.py`) |
| Public surfaces: identical answers; exactly three MCP tools; zero writes | **Holds** (row 12). Messaging-claim parity is fixture-only (row 13). |
| Determinism: two byte-identical evaluations at one location | **Holds** (row 14) |
| v0.4 contract preserved | **Holds** (23/23) |
| Accounting: zero unexplained canonical facts, zero guessed identities, zero silent unsupported cases | **Holds**. Scope closure found no unexpected fact. F4's `OBSERVED_ONLY` entity is explained. Every unsupported mechanism is explicit (F3, F8). |

## Findings: final dispositions

The owner decided F1-F7 in the Slice 5 review (#253). F8 is new in this run, and the owner decided
it on 2026-09-25.

| Id | Finding | Disposition | Final outcome at `aa04a15` |
| --- | --- | --- | --- |
| F1 | A canonical-validation failure escaped as HTTP 500 | `FIX` (#255) | Fixed. The manifest rejects an undeclared caller, and discovery-time validation gives a per-source rejection. No lifecycle step returns 500. Quarkus L6 now shows the manifest's `MANIFEST_CALL_SOURCE_UNRESOLVED` as frozen. |
| F2 | The import report omitted what I1 §10 requires | `FIX` (#254) | Fixed. `aip-import-report/1` carries every result, code, effect and removal used in this ledger. |
| F3 | Airflow OpenAPI `ACCEPTED_WITH_LIMITATIONS` (`SCHEMA_COMPOSITION_UNINTERPRETED`) | `DOCUMENT_UNSUPPORTED` | Unchanged, and now publicly observable in the report. No in-scope fact is affected. |
| F4 | A relation-less `OBSERVED_ONLY` `service:grpc-locations` | `NO_CHANGE` | Unchanged; the manual check is byte-identical to Slice 5 |
| F5 | A dossier bindings-layout defect; no diagnostic for skipped files | `DEFER` | Limitation stands: a present but un-enumerated file is still silent. The #246 layout guards hold. |
| F6 | `without_x.py` printed a header for an empty result | `NO_CHANGE` for AIP; harness fixed (#256) | Every diff exits 0 |
| F7 | The frozen Quarkus lifecycle mutation was invalid | `NO_CHANGE` for AIP; I5 §6 re-freeze (#256) | Quarkus L2, L5 and L3 match on the corrected X |
| F8 | See below | `DEFER` | Limitation recorded |

### F8: Unsupported Kubernetes kinds are not attributable per object, and a false "server log" claim. Disposition: **DEFER** (owner, 2026-09-25).

| Field | Value |
| --- | --- |
| Target and scenario | quarkus-super-heroes, the namespaced Kubernetes bundle (matrix row 3) |
| Expected | The frozen limitation list in `ground-truth.md`: 25 named objects with "one limitation each", plus 13 `NO_QUALIFIED_POD_MATCH` and nothing else |
| Actual | AIP emits exactly one `K8S_RESOURCE_UNSUPPORTED` per unsupported object: 25 in total, with the frozen per-kind distribution. Their pointer is `file:apiVersion/Kind`, with no namespace or name (`app/sources/kubernetes_mapping.py`, `map_kubernetes_resources`). So which named object each limitation belongs to is observable nowhere, and the report's deterministic deduplication shows six per-kind entries. **Related:** #254's `docs/ingestion.md` said diagnostic messages "stay in the server log". `_log_run` logs only per-source stats, so that claim was false. |
| Evidence | `quarkus-super-heroes/artifacts/import.json`, `quarkus-super-heroes/artifacts/k8s-limitations-per-kind.txt`, and the AIP log of the run (not committed). The two-target impact test asserts the 25 and the 13. |
| Affected contract | I2 §10 (diagnostics carry "source/resource IDs where safely known") and I1 §10 (report auditability). No fact is wrong: this is attribution granularity. |
| Severity | MINOR (auditability) |
| Disposition | **`DEFER`.** Adding namespace and name to the unsupported-resource pointer, and either logging diagnostics or correcting the `app/ingestion/import_report.py` docstring, would change executable files and so create a new candidate. Both are named follow-ups outside I5. **This PR corrects the false claim in `docs/ingestion.md`**, which is docs only, so the candidate is unchanged. The docstring correction is part of the deferred follow-up. |

## Exit decision

Every §9 row is qualified or recorded as a gap: rows 7, 8, 9 and 13 are fixture-only by design.
Every §13 item holds at one candidate, with the F8 limitation stated. Every finding has exactly one
disposition, and no material supported mismatch is unresolved. Both FIXes meet §11, and neither is
target-specific. The §12 byte-identity evidence is recorded.

**Candidate `aa04a150965924bd23ecf0125bcf7095a3cf72d9` is `FINAL_CANDIDATE_QUALIFIED`** (I5 §16),
subject to the owner's merge of the Slice 7 record. I5 qualification is neither a publication
decision nor evidence of a shipped artifact (§16); I6 owns release.
