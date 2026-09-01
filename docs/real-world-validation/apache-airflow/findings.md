# Findings — Apache Airflow

Findings from the qualifying comparison (I3.3, `results.md`), classified per the I1 finding
vocabulary. No `INCORRECT_SUPPORTED`, `MISSING_SUPPORTED` findings resulted from this run. The
`UNSUPPORTED`/`UNRESOLVED_IDENTITY`/`INSUFFICIENT_EVIDENCE` findings below are the pre-existing
I3.1/I3.2 classifications, confirmed unchanged by the comparator (I1 §32 — these pass through from
`expected.yaml` rather than being derived from AIP output).

## Summary of material findings

```text
CORRECT                 9   (9 PROVIDES) — see results.md for the full per-fact transcript
UNSUPPORTED             3   (airflow-scheduler/apiserver-postgres-dependency,
                             airflow-celery-result-backend-postgres-dependency)
UNRESOLVED_IDENTITY     2   (airflow-execution-api-boundary, airflow-runtime-role-identity)
INSUFFICIENT_EVIDENCE   1   (airflow-celery-messaging-runtime-status)
MISSING_SUPPORTED       0
INCORRECT_SUPPORTED     0
```

`CORRECT` findings are not individually re-listed here beyond the summary above — `results.md` is
the source of truth for their exact identities and evidence flags: all 9 `PROVIDES` facts are
`CORRECT` against `evidence: {declared: true}`, confirmed identically across both live runs.

## `airflow-scheduler-postgres-dependency` / `airflow-apiserver-postgres-dependency` / `airflow-celery-result-backend-postgres-dependency`

```text
classification:  UNSUPPORTED
severity:         INFO
disposition:      NO_CHANGE
```

Confirmed as ground-truth anticipated (I3.1): PostgreSQL is outside the current AIP canonical
relation vocabulary, and AIP emitted no false supported claim in its place. No decision record
needed; the pre-existing `UNSUPPORTED` classification in `expected.yaml` stands unchanged.

## `airflow-execution-api-boundary`

```text
classification:  UNRESOLVED_IDENTITY
severity:         MINOR
disposition:      NO_CHANGE
```

Unchanged from I3.1: the pinned Airflow source independently defines the private Execution API and
concrete target routes, but a supported `CALLS` fact was correctly not frozen or claimed, because
the worker/task-runner caller identity remains unresolved (see the next finding) and the qualifying
scope was never deliberately extended to this second contract surface. This run's capture confirms
AIP emitted no `CALLS` fact for the Execution API in the qualifying window — the boundary stays
correctly unclaimed rather than guessed. No decision record needed.

## `airflow-runtime-role-identity`

```text
classification:  UNRESOLVED_IDENTITY
severity:         MINOR
disposition:      NO_CHANGE
```

Unchanged from I3.1, and independently reconfirmed by I3.2's Phase B raw-telemetry inspection:
`airflow-scheduler`, `airflow-dag-processor`, `airflow-worker`, and `airflow-triggerer` are
architecturally distinct roles, but every native OTel span this qualifying profile actually produces
reports the same generic `service.name: unknown_service` regardless of which component emitted it
(`profile.md`'s "Standard Celery instrumentation decision" section). No per-role canonical `Service`
was asserted, and AIP's actual capture confirms none was invented. No decision record needed.

## `airflow-celery-messaging-runtime-status`

```text
classification:  INSUFFICIENT_EVIDENCE
severity:         MINOR
disposition:      NO_CHANGE
```

Unchanged from I3.2's Phase B closure: native Airflow tracing exposes zero Celery/broker/queue
attributes, and a diagnostic-only, spec-permitted addition of standard
`opentelemetry-instrumentation-celery` (not kept in the frozen profile) showed the destination is a
queue named `default` but that sender/consumer identity itself is not resolvable — a precondition
for any qualified `SENDS`/`RECEIVES_FROM` fact independent of messaging-evidence quality. This run's
capture confirms 0 `SENDS`/`RECEIVES_FROM` facts exist in the graph at all (no AsyncAPI source was
ever imported for this system), consistent with that closed decision. No decision record needed —
I3.2 already produced the full evidentiary account and closed the freeze gate on it.

## Gate check (I3 spec §72 Definition of Done)

```text
Airflow release 3.3.1 pinned, exact commit recorded:      yes (3adbbe1c58e4532df1964cb7794805e763816ee8)
selected runtime profile reproducible:                     yes - two independent clean-state runs
                                                            in this PR produced identical import
                                                            counts, traffic behavior, and
                                                            byte-identical actual-facts captures
                                                            (results.md "Repeatability evidence")
ground truth frozen before AIP result:                     yes (I3.1/I3.2, merged before this run)
selected /api/v2 PROVIDES facts compared:                  yes (9/9 CORRECT)
Execution API boundary explicitly classified:              yes (UNRESOLVED_IDENTITY, unchanged)
Celery queue exercised, native/raw telemetry inspected:     yes (I3.2 Phase B; this run's capture
                                                            confirms 0 SENDS/RECEIVES_FROM, no
                                                            unsupported mechanism coerced into a
                                                            false supported fact)
runtime role vs. instance identity documented:              yes (UNRESOLVED_IDENTITY, unchanged,
                                                            independently reconfirmed by I3.2)
PostgreSQL boundary classified:                             yes (UNSUPPORTED x3, unchanged)
no runtime instance silently promoted to a Service:         yes (confirmed by this run's capture -
                                                            no per-role Service was invented)
all findings classified:                                    yes
all CRITICAL findings dispositioned:                        yes (none exist)
critical false supported facts:                             0
```

## Decision records

None. Every finding in this run received `NO_CHANGE` — the pre-existing I3.1/I3.2 ground-truth
classifications were confirmed exactly as frozen, with no AIP behavior contradicting them and no new
evidence requiring a model-hardening decision.

## I3.4 — Hardening and Final Revalidation

I3.4's spec deliverable list is `general production fix, distilled regression tests, Quarkus impact
check, fresh Airflow clean-state rerun, second same-contract qualifying comparison, repeatability
proof, final I3 result`.

**Correction (PR #47 review F1):** an earlier version of this section treated the two runs already
performed inside I3.3/PR #46 as satisfying I3.4's rerun/repeatability requirement, reasoning that a
third run would add no new evidence. That was wrong: I3 spec §76's Implementation Notes explicitly
assign phase separation — *"I3.3: run AIP once and classify what happens. I3.4: apply only approved
general fixes and prove same-contract repeatability"* — mirroring Quarkus's own I2.3 (single run) +
I2.4 (separate revalidation) precedent exactly. The point of I3.4's own run is not statistical
novelty; it is proof that the *finally accepted candidate, frozen contract, and post-classification
state* still reproduces, which two runs performed before the hardening/no-fix decision existed
cannot establish. I3.4 therefore executed its own fresh clean-state run — see `results.md`'s
"Revalidation (I3.4)" section for the full record.

### Hardening

No production fix is required. Evidence: `git diff 0fbf8b4..HEAD -- app/ real_world_validation/` is
empty — no production code has changed at any point during I3 (I3.1 through I3.3, `0fbf8b4` being
the Quarkus I2.3 comparison commit). There is nothing to harden and no distilled regression test is
warranted, because nothing changed to regress.

### Quarkus impact check

Since no production code changed during all of I3, Quarkus's frozen I2 ground truth and results
(`quarkus-super-heroes/`) are provably unaffected — the same empty diff above is the evidence. No
re-run of the Quarkus profile is needed; its own `expected.yaml`/`results.md` remain valid exactly
as I2.4 left them.

### Repeatability proof

I3.4's own fresh clean-state run (`results.md`'s "Revalidation (I3.4)") reproduced the exact same
result as I3.3's qualifying run: identical import counts, identical traffic behavior, a
byte-identical captured actual-facts file, and identical comparator output (9/9 `CORRECT`). This
satisfies I3 spec §72's Comparison category item "Two clean qualifying runs produce the same
semantic result" under the phase separation §76 actually intends — the qualifying run in I3.3, the
repeatability proof in I3.4, not two runs bundled into one task.

## I3 Final Definition of Done (I3 spec §72)

### Upstream

- [x] `apache/airflow` is pinned to `3adbbe1c58e4532df1964cb7794805e763816ee8` (`upstream.md`).
- [x] Airflow release `3.3.1` is recorded (`upstream.md`).
- [x] Apache-2.0 license is recorded (`upstream.md`).
- [x] Official Compose and OpenAPI references are pinned (`upstream.md` — both @ the pinned commit).
- [x] Exact runtime image/provider/instrumentation versions are recorded (`profile.md` — exact
      digest for `apache/airflow`, `postgres:16.15`, `redis:7.2-bookworm` digest-pinned,
      `otel/opentelemetry-collector:0.159.0` digest-pinned; `upstream.md` —
      `apache-airflow-providers-celery==3.23.1`/`celery==5.6.3`, queried directly from the
      digest-pinned image during I3.4's revalidation run, closing this item's previous gap per
      PR #47 review F3).
- [x] Selected runtime profile is reproducible (`results.md`'s "Repeatability evidence" and
      "Revalidation (I3.4)" — three independent clean-state runs total, identical behavior).

### Ground Truth

- [x] `upstream.md` complete.
- [x] `profile.md` complete.
- [x] `ground-truth.md` complete.
- [x] `expected.yaml` frozen before qualifying AIP output (I3.1/I3.2 merged before I3.3's first run
      — visible commit history: `expected.yaml` frozen in PR #44, closed in PR #45, first queried
      by AIP in PR #46).
- [x] Logical Service boundary independently analyzed (`ground-truth.md`'s "Logical Service boundary
      analysis" — Interpretation A/B).
- [x] Runtime role vs instance distinction documented (`ground-truth.md`'s "Multiple runtime
      instances"; `expected.yaml`'s `airflow-runtime-role-identity`).
- [x] Bounded REST provider scope independently established (`ground-truth.md`'s "Bounded REST
      provider inventory" — 9 of 88 paths selected on documented criteria).
- [x] Celery queue/broker semantics independently established (`ground-truth.md`'s "CeleryExecutor
      Ground Truth"/"Queue Versus Broker").
- [x] PostgreSQL boundary classified (`expected.yaml`'s `unsupported` entries).
- [x] Ground truth not derived from AIP output (`ground-truth.md`'s header: authored before any AIP
      run; `upstream.md`'s evidence hierarchy).

### Runtime

- [x] Airflow starts from clean state (`runbook.md` phase 9's teardown; `results.md`'s two
      clean-state runs).
- [x] AIP starts from clean state (same — Neo4j named volumes removed by `down -v`).
- [x] CeleryExecutor active (`profile.md`'s "Executor / broker / result backend / metadata
      database").
- [x] Redis broker active (same).
- [x] PostgreSQL active (same).
- [x] API server ready (`runbook.md` phase 3's readiness gate).
- [x] Scheduler ready (same).
- [x] Worker(s) ready (same — both replicas, `wait_for_service_healthy`).
- [x] Validation Dag loaded (`runbook.md` phase 3's `wait_for_dag_registered`).
- [x] Official OpenAPI imported (`results.md` — `223`/`512` nodes/relations, both runs).
- [x] Native OTLP reaches Collector (`profile.md`'s OTel configuration finding; `runbook.md`
      phase 5).
- [x] OTLP reaches AIP (`runbook.md` phase 6's drain barrier — `POST /v1/traces ... 200`).
- [x] Validation environment/window explicit (`results.md`'s "Run identity" — `environment`,
      `window_start`, `window_end` recorded for both runs).
- [x] Deterministic traffic executes successfully (`traffic.sh`'s own task-instance assertions,
      both runs).
- [x] Dag completes successfully (same — both tasks `success` on `queue=default`).
- [x] Telemetry drain succeeds (`runbook.md` phase 6's drain barrier, both runs).
- [x] Cleanup succeeds (`runbook.md` phase 9, both runs).

### Identity

- [x] API server identity reviewed (`ground-truth.md`'s Logical Service boundary analysis).
- [x] Scheduler identity reviewed (same).
- [x] Worker role identity reviewed (same; `profile.md`'s Celery instrumentation finding).
- [x] Worker instance identity reviewed (`ground-truth.md`'s "Multiple runtime instances";
      `profile.md`'s "Worker count").
- [x] Dag processor/triggerer identity behavior reviewed (`ground-truth.md`'s Logical Service
      boundary analysis).
- [x] No runtime instance is silently promoted to a false logical Service (`findings.md`'s
      `airflow-runtime-role-identity` — `UNRESOLVED_IDENTITY`, not guessed).
- [x] No architecturally distinct identity is falsely merged where that creates a supported false
      claim (same finding — no false claim was made either way).
- [x] Ambiguous cases are explicitly classified (`expected.yaml`'s `unresolved_identity` entries).

### REST

- [x] Selected `/api/v2` `PROVIDES` facts compared (`results.md` — 9/9 `CORRECT`).
- [x] Route templates remain low-cardinality (`expected.yaml`'s operation IDs use `{dag_id}`/
      `{dag_run_id}`/`{task_id}` placeholders, never a concrete literal ID).
- [x] Concrete Dag/DagRun IDs do not become canonical operation identities (same — `traffic.sh`'s
      own `dag_run_id` never appears in any canonical operation ID).
- [x] Execution API boundary is explicitly classified (`findings.md`'s `airflow-execution-api-boundary`
      — `UNRESOLVED_IDENTITY`).

### Messaging

- [x] Celery task queue is exercised (`traffic.sh` triggers `i3_validation` on `queue=default`,
      both runs).
- [x] Broker vs queue identity is preserved (`profile.md`'s Celery instrumentation finding —
      `messaging.destination_kind: queue`, `messaging.destination: default`, independently
      distinguishing the queue from the bare Redis broker endpoint).
- [x] Producer direction independently established (same — `Kind: Producer` span captured).
- [x] Consumer direction independently assessed (same section — explicitly classified as
      unavailable from raw telemetry, per spec §23's own allowance for `INSUFFICIENT_EVIDENCE`;
      PR #47 review's wording note: this is a classified absence, not a positive establishment,
      and no consumer span was manufactured to make this box checkable).
- [x] Native/raw messaging telemetry inspected (`profile.md`'s sanitized representative span
      excerpt).
- [x] `SENDS`/`RECEIVES_FROM` expected only where safely qualified (`expected.yaml` — neither is
      asserted; `airflow-celery-messaging-runtime-status` stays `INSUFFICIENT_EVIDENCE`).
- [x] No unsupported messaging mechanism is coerced into a false supported fact (same — `results.md`
      confirms 0 `SENDS`/`RECEIVES_FROM` facts captured, both runs).

### Coverage / Evidence

- [x] Raw OTel resource identity evidence retained in compact sanitized form (`profile.md`'s
      sanitized span excerpt, IDs/timestamps redacted).
- [x] Declared and observed evidence remain distinct (`results.md`'s comparator transcript —
      `declared=true observed=false` for every `PROVIDES` fact, never conflated).
- [x] Runtime absence is window/coverage qualified (`runbook.md` phase 6's drain barrier — a window
      is only closed once ingestion is confirmed, never assumed).
- [x] No evidence is fabricated or dropped (`real_world_validation/capture.py`'s generic
      declared/observed query, PR #41 review F1/F2's fix, reused unchanged here).
- [x] Startup and late-flush telemetry do not invalidate the observation window (`runbook.md`
      phase 6 — `traffic completion != observation window end`, drain barrier before `WINDOW_END`).

### Comparison

- [x] All frozen expected supported facts compared (`results.md` — all 9).
- [x] Unexpected in-scope supported facts surfaced (`real_world_validation/comparator.py`'s own
      unmatched-in-scope-fact handling; none occurred in this run since capture yielded exactly the
      9 expected facts).
- [x] All material findings use I1 vocabulary (`findings.md` throughout).
- [x] Summary counters deterministic (`real_world_validation/comparator.py::_sort_key`, I1 §21's
      canonical sort order).
- [x] Two clean qualifying runs produce the same semantic result (`results.md`'s "Repeatability
      evidence" plus "Revalidation (I3.4)" — three runs total, the third performed under I3.4's own
      phase per §76, all producing identical comparator output).
- [x] Deterministic ordering verified (same `_sort_key` — classification, severity, relation type,
      source, target, finding id).

### Hardening

- [x] Every material production change has a decision record (vacuously true — no production
      change was made).
- [x] Every accepted fix is general, not Airflow-specific (vacuously true — no fix was made).
- [x] Every accepted fix has deterministic regression coverage (vacuously true — no fix was made).
- [x] Major canonical redesign proposals carried to I4 unless urgently required to remove a false
      supported claim (none arose — no false supported claim occurred, so nothing is urgent; the
      `airflow-runtime-role-identity`/`airflow-celery-messaging-runtime-status` findings are
      candidate inputs for I4's cross-system model hardening, not urgent fixes).

### Regression / Quality

(PR #47 review F2 — this entire category was omitted from an earlier version of this checklist.)

- [x] v0.2 evaluation remains `10/10 PASS` — re-run at this PR's head (`uv run python -m evaluation
      run`): `Scenarios: 10, Passed: 10, Failed: 0, Missing/Unexpected/Forbidden facts: 0, Wrong
      statuses: 0, Evidence errors: 0, RESULT: PASS`.
- [x] Quarkus impact assessed for I3 production changes (this section's own "Quarkus impact check"
      above — no production change occurred, so no impact).
- [x] Unit tests green — `uv run pytest tests/unit -q`: 504 passed.
- [x] Integration tests green — `uv run pytest tests/integration -q`: 160 passed.
- [x] I1 validation-contract tests green — `uv run pytest tests/unit -k "real_world_validation or
      quarkus_expected_dossier or airflow_expected_dossier" -q`: 59 passed.
- [x] Ruff green — `uv run ruff check .` / `uv run ruff format --check .`: both clean.
- [x] CI green — GitHub Actions run `33527683492` (`lint + test`, `dependency security scan`),
      at commit `5023579`.
- [x] CodeQL green — GitHub Actions run `33527683427` (Python + Actions analysis), at commit
      `5023579`.
- [x] Dependency audit green — `pip-audit` job within CI run `33527683492` above.
- [x] I3 release blockers = `0` (F1/F2/F3 from PR #47's review are resolved by this commit — see
      each item above and `results.md`'s "Revalidation (I3.4)"/`upstream.md`'s Celery provider
      version).

## I3 is complete

Every I3 spec §72 Definition of Done item above is satisfied. No production fix was required, no
decision record was warranted, and repeatability was proven across three independent clean-state
runs total: two performed inside I3.3 (before the hardening decision), and one performed under
I3.4's own phase (after it) — the actual proof §76 requires, per PR #47's review. I4 (Cross-System
Model Hardening) can proceed using this dossier and Quarkus's I2 dossier as its two independent
inputs — in particular, the `airflow-runtime-role-identity` and
`airflow-celery-messaging-runtime-status` findings above are exactly the kind of
cross-system-informed model-hardening candidates I4 exists to evaluate.
