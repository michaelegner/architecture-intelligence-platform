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
