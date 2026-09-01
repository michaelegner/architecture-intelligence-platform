# Results — Apache Airflow

Qualifying comparison for the pinned commit `3adbbe1c58e4532df1964cb7794805e763816ee8` (I3.3),
against `expected.yaml` as fully and finally frozen by I3.1 (declaration-only facts) and I3.2
(Phase B closure of the one item I3.1 left provisional). Executed by following `runbook.md` phases
1-9 for real against a freshly built, freshly started stack for the qualifying run, then phase 10
for the independent clean-state revalidation below.

## Run identity

```text
upstream commit:    3adbbe1c58e4532df1964cb7794805e763816ee8
image:              apache/airflow:3.3.1@sha256:0c4bcc0370e526de1b7892a3bf4343d260c6c82359c66f77155b53cd773d6339
environment:        airflow-i3
window_start:       2026-09-01T13:47:23Z
window_end:         2026-09-01T13:47:58Z
```

The full compose stack (`runtime/docker-compose.yml`) was started from clean state
(`docker compose down -v` had already run; no prior volumes existed), the bounded readiness gate
(`runbook.md` phase 3 — AIP/apiserver/Collector HTTP+TCP checks, scheduler/dag-processor/triggerer/
both workers' container healthchecks via `docker compose ps --all`, and `i3_validation` DAG
registration) passed on the first pass, `POST /api/import` succeeded (`nodes_written: 223`,
`relations_written: 512` for `airflow-apiserver`), `runtime/traffic.sh` ran once inside the window
above (both tasks `success` on `queue=default`, asserted by the script itself), and the drain
barrier (`docker compose logs --since <window_start> architecture-intelligence` showing a
`POST /v1/traces ... 200` entry) confirmed AIP had received the OTLP batch before capture began.
The stack was torn down (`docker compose down -v`) after capture.

## Repeatability evidence

A second, independent execution of this exact profile — same commit, same image digest, same
unmodified `expected.yaml`/`runtime/`/`runbook.md` — was run from a fresh clean state immediately
after the first:

```text
window_start:       2026-09-01T13:51:12Z
window_end:         2026-09-01T13:51:46Z
```

`POST /api/import` returned identical counts (`223`/`512`), `traffic.sh` behaved identically (same
task states, same queue, same assertions passing), and the drain barrier confirmed ingestion the
same way. The captured actual-facts file
([`artifacts/actual-revalidation.yaml`](artifacts/actual-revalidation.yaml)) is **byte-identical**
to the first run's ([`artifacts/actual.yaml`](artifacts/actual.yaml)) — confirmed with `diff`. The
comparator produced the identical summary and identical per-fact classification both times. This
satisfies the repeatability requirement (I1 §28's runbook-reproducibility contract, matching
Quarkus's I2.3/I2.4 precedent): two independent clean-state runs, same upstream pin, same profile,
same frozen `expected.yaml`, same result.

## AIP result capture

[`artifacts/actual.yaml`](artifacts/actual.yaml) — captured via:

```bash
uv run python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password <redacted> \
  --database neo4j --environment airflow-i3 \
  --since 2026-09-01T13:47:23Z --until 2026-09-01T13:47:58Z \
  --scope-entities operation:service:airflow-apiserver:GET:/api/v2/monitor/health,operation:service:airflow-apiserver:GET:/api/v2/dags,operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id},operation:service:airflow-apiserver:POST:/api/v2/dags/{dag_id}/dagRuns,operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns,operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id},operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances,operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id},operation:service:airflow-apiserver:GET:/api/v2/variables,queue:default \
  --scope-relation-types PROVIDES,SENDS,RECEIVES_FROM \
  --out artifacts/actual.yaml
```

(`--scope-entities` copied verbatim from `expected.yaml`'s own `scope.entities`, never hand-typed a
second time.)

9 facts captured: all 9 `PROVIDES` (`declared=true, observed=false` — real `DECLARED` evidence from
the OpenAPI import; no runtime *status* concept applies to `PROVIDES`, matching Quarkus's own
`PROVIDES` facts in I2.3). **0** `SENDS`/`RECEIVES_FROM` facts were captured — expected, since no
AsyncAPI source exists for this system and I3.2's Phase B closure explicitly concluded no qualified
messaging relation belongs in `expected.yaml` (see `ground-truth.md`'s Change log).

## Summary

```text
Expected supported facts:      9
Correct:                       9
Missing supported:             0
Incorrect supported:           0
Unsupported constructs:        3
Unresolved identities:         2
Insufficient evidence:         1
Critical semantic errors:      0
```

Every one of the 9 selected `PROVIDES` facts was captured and matched exactly; the 3 `unsupported`,
2 `unresolved_identity`, and 1 `insufficient_evidence` entries are the pre-existing I3.1/I3.2
classifications passing through unchanged (I1 §32 — the comparator never re-derives these, it only
carries them through). No finding in this run required a new decision record (`findings.md`).

## Comparator output

```bash
uv run python -m real_world_validation compare \
  --expected expected.yaml --actual artifacts/actual.yaml
```

```text
AIP Real-World Validation — I1 contract


[UNRESOLVED_IDENTITY/MINOR] airflow-execution-api-boundary

[UNRESOLVED_IDENTITY/MINOR] airflow-runtime-role-identity

[INSUFFICIENT_EVIDENCE/MINOR] airflow-celery-messaging-runtime-status

[UNSUPPORTED/INFO] airflow-apiserver-postgres-dependency

[UNSUPPORTED/INFO] airflow-celery-result-backend-postgres-dependency

[UNSUPPORTED/INFO] airflow-scheduler-postgres-dependency

[CORRECT/INFO] airflow-provides-get-dags
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-get-dag
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-get-dag-runs
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-get-dag-run
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-get-task-instances
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-get-task-instance
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-health
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/monitor/health
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/monitor/health
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-get-variables
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/variables
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:GET:/api/v2/variables
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] airflow-provides-trigger-dag-run
Expected:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:POST:/api/v2/dags/{dag_id}/dagRuns
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:airflow-apiserver
    -> operation:service:airflow-apiserver:POST:/api/v2/dags/{dag_id}/dagRuns
  status: None  evidence: declared=true observed=false

Expected supported facts:      9
Correct:                       9
Missing supported:             0
Incorrect supported:           0
Unsupported constructs:        3
Unresolved identities:         2
Insufficient evidence:         1
Critical semantic errors:      0
```

## Exit code

```text
0  (no release-blocking / CRITICAL-severity finding)
```
