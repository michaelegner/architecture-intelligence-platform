# Validation Profile — Apache Airflow

Bounded profile for I3 (I3 spec §8/§38). This document defines *what will be run and why*. No
runtime override, validation Dag, traffic script, or Collector config exists yet — those are
I3.2's deliverables (`runtime/`); this file records the intended profile so it can be reviewed and
frozen before that runtime work begins.

## Airflow image/version

```text
apache/airflow, pinned at release 3.3.1 (exact image tag/digest to be recorded in I3.2 when the
runtime override sets AIRFLOW_IMAGE_NAME)
```

## Executor / broker / result backend / metadata database

```text
executor:            CeleryExecutor
broker:              Redis (redis://:@redis:6379/0, official Compose default)
result backend:      PostgreSQL (db+postgresql+psycopg2://airflow:airflow@postgres/airflow)
metadata database:   PostgreSQL (postgresql+psycopg2://airflow:airflow@postgres/airflow)
```

Unmodified from the pinned official Compose profile's own defaults (`ground-truth.md`).

## Components started

```text
postgres                metadata DB + Celery result backend
redis                   Celery broker
airflow-apiserver       public REST API (/api/v2), execution API for workers/tasks
airflow-scheduler       submits work to Celery
airflow-dag-processor   parses DAG files (isolated from the scheduler process)
airflow-worker          x2 (see "Worker count" below)
airflow-triggerer       deferred/async trigger execution
airflow-init            one-shot: DB migration + admin user creation
```

`airflow-cli` and `flower` are not started — both are opt-in diagnostic profiles
(`--profile debug` / `--profile flower`) not required for qualifying traffic.

## Worker count

```text
2 (docker compose up --scale airflow-worker=2)
```

Per I3 spec §9: the pinned Compose file sets no `container_name` on any service, so two worker
instances scale without a Compose rewrite — this is a direct test of runtime instance identity vs.
logical architecture identity (`ground-truth.md`'s "Multiple runtime instances"). If this proves
operationally impractical during I3.2, one worker MAY be used instead, with the reason documented
here and the multiple-instance question left explicit (I3 spec §9).

## Validation Dag (intent only — code lands in I3.2)

```text
i3_validation
    task_a -> task_b
```

Must, per I3 spec §32: contain no external network dependency, no LLM call, no non-deterministic
output required for validation, run on the qualifying Celery queue (`default`), contain at least
two ordered tasks, finish quickly, and be safe to run repeatedly.

## Bounded public REST API endpoints exercised

The 9 operations frozen in `ground-truth.md`'s "Bounded REST provider inventory":

```text
GET  /api/v2/monitor/health
GET  /api/v2/dags
GET  /api/v2/dags/{dag_id}
POST /api/v2/dags/{dag_id}/dagRuns
GET  /api/v2/dags/{dag_id}/dagRuns
GET  /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}
GET  /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances
GET  /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}
GET  /api/v2/variables
```

These map directly onto the traffic script phases I3 spec §33 requires: readiness (`monitor/health`),
trigger (`POST .../dagRuns`), poll (`GET .../dagRuns`, `GET .../dagRuns/{dag_run_id}`), and verify
(`GET .../taskInstances`, `GET .../taskInstances/{task_id}`).

## OpenAPI acquisition method

Direct import of the pinned, official, generated contract:

```text
airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml
@ 3adbbe1c58e4532df1964cb7794805e763816ee8
```

No AIP-generated or reconstructed OpenAPI is used (I3 spec §16). The complete document MAY be
imported; comparator scope is bounded to the 9 selected operations, not the full 88-path document.

## OTel configuration

Native Airflow tracing, `[traces]` section:

```text
otel_on = True
```

exported via the **standard** OpenTelemetry environment variables (`OTEL_EXPORTER_OTLP_ENDPOINT`,
`OTEL_SERVICE_NAME` if set, `OTEL_EXPORTER_OTLP_PROTOCOL`) — never the deprecated
`otel_host`/`otel_port`/`otel_service`/`otel_ssl_active` keys, which `configure_otel()`'s
backcompat path only reads when the standard variables are absent (`ground-truth.md`'s central
identity finding). Per the frozen Logical Service boundary decision, this first qualifying profile
does **not** set a per-role `OTEL_SERVICE_NAME` — that is reserved for a separately documented
diagnostic experiment, not this qualifying run (I3 spec §14).

## Collector path

OTLP -> OpenTelemetry Collector -> (diagnostic/raw evidence path) + AIP `/v1/traces`, per I3 spec
§27. The project's own CI reference config
(`scripts/ci/docker-compose/otel-collector-config.yaml` @ the pinned commit — OTLP HTTP receiver,
batch processor, debug/Jaeger exporters) is cited as prior art; AIP's own Collector config is an
I3.2 deliverable, adapted the same way I2.2 adapted `examples/runtime-demo/otel-collector-config.yaml`.

## Environment name

```text
airflow-i3
```

Per I3 spec §31's recommendation.

## Observation-window method

To be defined operationally in I3.2's `runbook.md`, following the same pattern as Quarkus's
`runbook.md` phase 8 (UTC `window_start`/`window_end` bracketing only the qualifying traffic). I3
spec §31 requires a bounded telemetry drain barrier before capture, since task execution is
asynchronous and OTLP may flush after client traffic completes.

## Cleanup/reset procedure

At minimum (I3 spec §58), each qualifying run resets: AIP Neo4j state, AIP runtime/evidence state,
the Airflow PostgreSQL volume, Redis broker state, relevant Airflow logs, temporary OTLP capture,
the validation output artifact, and Dag Run state — `docker compose down -v` for the Airflow stack,
mirroring Quarkus's `runbook.md` clean-state procedure.

## Resource / port assumptions

To be finalized in I3.2 once the runtime override is written; the pinned official Compose profile's
own default ports apply unless overridden (`airflow-apiserver` on 8080 per the pinned file).

## Mandatory boundary notes (I3 spec §38)

```text
PostgreSQL dependency               -> UNSUPPORTED by current AIP relation model (ground-truth.md)
runtime process/container identity  -> NOT automatically logical Service identity (ground-truth.md)
```
