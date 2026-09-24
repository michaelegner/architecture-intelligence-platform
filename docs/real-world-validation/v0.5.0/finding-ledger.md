# I5 Cross-System Finding Ledger (v0.5.0, Slice 5)

This ledger covers **candidate `174a17c5d0f8be35291032c677585291c330cc0a`**, qualified on 2026-09-24,
against the frozen dossiers (#240 and #242), the lifecycle and coverage freeze (#244), and the
post-freeze corrections #243 and #246.

Every material result has exactly one disposition (I5 §11). The dispositions below are
**proposed**: the owner decides them in the Slice 5 review. Each accepted `FIX` becomes its own
Slice 6 PR.

## Coverage matrix, row by row (`coverage-matrix.md`)

| # | Area | Outcome at this candidate | Evidence |
| --- | --- | --- | --- |
| 1 | I1 lifecycle (real declarations) | **Airflow: all 9 steps match. Quarkus: 6 of 9 match; L2, L5 and L3 fail with HTTP 500 (F1).** Not fully qualified. | `lifecycle/results.md` |
| 2 | I1 lifecycle (regression) | Pass: `tests/unit` 2206 passed, `tests/integration` 448 passed | test-suite run at the candidate |
| 3 | I2 offline discovery (upstream-derived) | Pass for the result label and the complete inventory (13/13/1, 2 routes, all `DECLARED_MANIFEST`, no interaction). **The exact frozen limitation list cannot be observed** (F2). | `quarkus-super-heroes/results.md` |
| 4 | I2 namespace-less rejection | The source is absent from the import response, and nothing from it committed. **`K8S_RESOURCE_INVALID` cannot be observed** (F2). | same |
| 5 | I2 captured resources and owner chain (independent capture) | Pass (`test_kubernetes_independent_capture.py`, in the integration suite) | test-suite run |
| 6 | I3 Path B and the name-only negative | Pass: 3 × `RESOLVED_CONFIGURED`, and both name-only pairs never resolve | `quarkus-super-heroes/artifacts/compare.txt` |
| 7 | I3 Path A (gap on the real targets) | Fixture only; pass (`test_i3_cross_source_qualification.py`) | test-suite run |
| 8 | I3 Path C, conflict, ambiguity | Fixture only; pass | test-suite run |
| 9 | I4 positive | Fixture only; pass (`test_i4_pubsub_qualification.py`) | test-suite run |
| 10 | I4 negative (consumer group ≠ Subscription) | Pass: no Queue, Topic or Subscription fact or entity for Kafka `fights`, and the Kafka fixture passes | `quarkus-super-heroes/results.md`, test-suite run |
| 11 | Airflow messaging negative | Pass: no messaging fact or entity, and Celery stays `INSUFFICIENT_EVIDENCE` | `apache-airflow/results.md` |
| 12 | Public answers and provenance | Pass on both targets: Service = REST = negotiated MCP, one snapshot, three tools, and zero writes (the Q-GRAPH digests are unchanged) | both `results.md` files |
| 13 | Public messaging-claim parity (gap on the real targets) | Fixture only; pass (the `test_mcp_*_equivalence.py` tests and the I4 tests) | test-suite run |
| 14 | v0.4 Architecture Answer contract | Pass: 23 of 23 scenarios. **Two runs are byte-identical** (result sha256 `66943d70d87236b451c6ed7a0190205306ac442d2a89b6cce24246dfcd0bea01`). The committed report is not refreshed, because that is I6's job. | `evaluation-artifacts/` |
| 15 | Import-report observability | Confirmed as a finding (F2) | this ledger |

## Findings

### F1: HTTP 500 when a manifest's caller Service loses its only minting source. Proposed disposition: **FIX**, plus an owner decision on semantics.

| Field | Value |
| --- | --- |
| Target and scenario | quarkus-super-heroes, lifecycle L2, L5 and L3 (every step that omits `rest-fights/openapi.yml`) |
| Expected | Per I1 §6: commit; only X's ownership is removed (L2 and L3); X is preserved on the scope change (L5) |
| Actual | `POST /api/import` → **HTTP 500**. `CanonicalValidationError: Relation CALLS has unknown source service:rest-fights` (×7) escapes `import_discovery_run` → `validate_canonical_model`. Nothing commits. |
| Evidence | `lifecycle/artifacts/quarkus-super-heroes/{L2,L5,L3}/aip.log` and `import.json` |
| Affected contract | I1 §10: "Each source receives exactly one result", and conflicts lead to a "deterministic conflict diagnostic; affected import rejected". An unhandled exception is neither. |
| Severity | MAJOR. The trigger is an ordinary operator action (removing an OpenAPI whose Service a manifest still names), and the failure hides its reason (F2). |
| Proposed disposition | **FIX**: map a canonical-validation failure of the merged model to a per-run rejection with a deterministic diagnostic, never an unhandled exception. |
| **Open owner decision** | Should a manifest's own resolved `x-aip-service-id` **establish** the caller Service entity when no OpenAPI or AsyncAPI source mints it? If yes, the frozen expectation (commit and removal) holds, and the FIX also changes the manifest adapter's output. If no, the correct outcome is a rejection. The frozen lifecycle ledger then needs an amended expected outcome, and X must be re-chosen or the scenario redefined, under I5 §6's correction rule. The I1 spec does not state which applies (§19 item 9). |
| Also | The dossier assumption "no other declaration depends on X" (`lifecycle/README.md`) was wrong. The manifest depends on X's Service entity. |

### F2: The import report omits what I1 §10 requires. Proposed disposition: **FIX**.

| Field | Value |
| --- | --- |
| Target and scenario | Both targets. Every lifecycle step. The Quarkus Kubernetes imports. |
| Expected | I1 §10: "The import report SHALL include discovered sources and inventories, … unsupported constructs, unresolved references, conflicts, planned mutations/expirations, tombstones, and final commit status." |
| Actual | `POST /api/import` returns `import_id`, a combined `committed`, and per-source stats. The stats are `{}` for a non-committing run. There is no inventory status, no diagnostics, no removed-source ids and no rejected-source results. FAILED, PARTIAL and `REJECTED_CONFLICT` are indistinguishable. Kubernetes limitation lists and rejection codes cannot be observed. |
| Evidence | Pre-registered in `lifecycle/README.md`. **Confirmed in practice twice:** the aborted `34067b7` attempt (F5) and F1 each failed with no visible reason. Both needed an offline re-run or a container traceback to diagnose. |
| Affected contract | I1 §10 (report) |
| Severity | MAJOR (auditability). The qualification evidence depends on internal-state Cypher and logs. |
| Proposed disposition | **FIX**: add the missing report fields additively to the `POST /api/import` response. This is not a new tool (§4.2). |

### F3: Airflow OpenAPI `ACCEPTED_WITH_LIMITATIONS` (`SCHEMA_COMPOSITION_UNINTERPRETED`). Proposed disposition: **DOCUMENT_UNSUPPORTED**.

| Field | Value |
| --- | --- |
| Target and scenario | apache-airflow, the qualifying import and lifecycle S0 |
| Expected | The dossier expected the source to be "accepted" and did not anticipate a limitation |
| Actual | `ACCEPTED_WITH_LIMITATIONS`. The offline discovery diagnostic is `SCHEMA_COMPOSITION_UNINTERPRETED`. |
| Evidence | `apache-airflow/artifacts/import.json`; offline discovery over the frozen declarations |
| Affected contract | I1 §8.1 (schema composition is outside the interpreted subset) |
| Severity | MINOR. No in-scope fact is affected: 9/9 PROVIDES are `CORRECT`. |
| Proposed disposition | **DOCUMENT_UNSUPPORTED**: an intentionally uninterpreted construct, disclosed explicitly and not silently dropped |

### F4: An OBSERVED_ONLY `service:grpc-locations` entity with no relations. Proposed disposition: **NO_CHANGE**.

| Field | Value |
| --- | --- |
| Target and scenario | quarkus-super-heroes, the qualifying run |
| Expected | gRPC `UNSUPPORTED`: no CALLS, Queue or Pub/Sub fact |
| Actual | Runtime observation admitted a `service:grpc-locations` Service entity (`discovery_status: OBSERVED_ONLY`) from the running process's OTel identity. **No relation** involves it, and no gRPC interaction fact exists. |
| Evidence | `quarkus-super-heroes/artifacts/manual-checks/grpc-locations-*.txt` |
| Affected contract | Runtime observation of Services (the v0.3 semantics); the I5 §8.1 gRPC boundary |
| Severity | INFO |
| Proposed disposition | **NO_CHANGE**: correct for its claimed scope. The unsupported boundary held. The entity is explained, not guessed. |

### F5: The discoverer silently skips non-candidate and root-level declaration files. Proposed disposition: **DEFER**.

| Field | Value |
| --- | --- |
| Target and scenario | Slice 5 attempt 1 at `34067b7` (non-qualifying) |
| Expected | A declaration file in the configured root is either enumerated or diagnosed |
| Actual | `runtime/declarations/identity-bindings.yaml` was ignored with no diagnostic, because it had a non-candidate name at root level. Every OpenAPI source was then `SERVICE_IDENTITY_UNRESOLVED`, and the run was PARTIAL. The API showed only `committed:false` (F2). |
| Evidence | The attempt's test-suite results passed (2202 unit, 448 integration). The dossier defect is corrected in #246 (see its `profile.md` revision histories). |
| Affected contract | `FilesystemSourceDiscoverer`'s documented enumeration convention (ADR 0009) |
| Severity | MINOR. The root cause was an input-authoring defect, now guarded by tests. |
| Proposed disposition | **DEFER**: a diagnostic for skipped files would be a behavior change outside I5's safely evidenced scope |

### F6: `without_x.py` keeps the header line when every row is removed. Proposed disposition: **NO_CHANGE** (AIP).

| Field | Value |
| --- | --- |
| Target and scenario | apache-airflow lifecycle L2 and L3 |
| Expected | A `diff` exit of 0 when the row sets are equal |
| Actual | Exit 1 only because `without_x.py` prints the header while `cypher-shell` prints nothing for an empty result. The row sets are identical. |
| Evidence | `lifecycle/artifacts/apache-airflow/{L2,L3}/Q-*.diff` (a one-line header diff) |
| Affected contract | None in AIP. This is qualification tooling. |
| Severity | INFO |
| Proposed disposition | **NO_CHANGE** for AIP. The harness is corrected in the Slice 6/7 tooling update, and no verdict depends on it. |

## Exit status of Slice 5

Both targets and every §9 row ran against one candidate, and every material result has a finding
with one proposed disposition. The candidate is **not** yet `FINAL_CANDIDATE_QUALIFIED`: row 1 is
incomplete for Quarkus (F1), and the proposed FIXes (F1 and F2) create a new candidate. Slice 7
reruns every row at the final candidate (I5 §12).
