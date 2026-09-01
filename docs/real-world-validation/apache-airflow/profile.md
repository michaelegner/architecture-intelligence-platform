# Validation Profile — Apache Airflow

Bounded profile for I3 (I3 spec §8/§38). `runtime/` (I3.2's deliverable) implements exactly this
profile; this file records what was run and why, and (below) what I3.2's Phase B run actually found.

I3.2 carried the spec's Phase B responsibility (§48-49): starting this profile and capturing raw
OTel independently, before `ground-truth.md`/`expected.yaml`'s Celery messaging item could move from
provisional to finally frozen (see `ground-truth.md`'s "Provisional scope of this freeze", now
resolved — see that file's Change log). Everything else in this profile description was already
final as of I3.1.

## Airflow image/version

```text
apache/airflow:3.3.1
@ sha256:0c4bcc0370e526de1b7892a3bf4343d260c6c82359c66f77155b53cd773d6339 (resolved at I3.2 research
time via AIRFLOW_IMAGE_NAME)
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
logical architecture identity (`ground-truth.md`'s "Multiple runtime instances"). This proved fully
practical: `docker compose up -d --scale airflow-worker=2` started and health-checked both instances
identically with no Compose rewrite, confirmed across two independent clean-state runs (I3.2). Both
workers executed `i3_validation` tasks (task distribution observed across `runtime-airflow-worker-1`
and `runtime-airflow-worker-2` container names during the qualifying traffic).

## Validation Dag

```text
i3_validation
    task_a -> task_b
```

`runtime/dags/i3_validation.py`: two `@task(queue="default")`-decorated TaskFlow tasks, no external
network dependency, no LLM call, no non-deterministic output, deterministic logs only. Confirmed
across three independent runs: both tasks report `"queue":"default"` and `"state":"success"` in
`GET .../taskInstances`, completing in ~4-5s total per run — satisfies I3 spec §32 in full.

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

exported via the standard OpenTelemetry environment variables `OTEL_EXPORTER_OTLP_ENDPOINT` and
`OTEL_RESOURCE_ATTRIBUTES` — never the deprecated `otel_host`/`otel_port`/`otel_service`/
`otel_ssl_active` keys, which `configure_otel()`'s backcompat path only reads when the standard
variables are absent (`ground-truth.md`'s central identity finding). Per the frozen Logical Service
boundary decision, this qualifying profile does **not** set a per-role `OTEL_SERVICE_NAME`.

**I3.2 finding, not documentable before actually running the profile:** `OTEL_EXPORTER_OTLP_PROTOCOL`
— the "standard" env var this document originally expected to control HTTP vs. gRPC — is **not**
read by Airflow's own exporter selection. `configure_otel()`
(`shared/observability/src/airflow_shared/observability/traces/__init__.py` @ the pinned commit)
picks the exporter via `_load_exporter_from_env()`, which reads **`OTEL_TRACES_EXPORTER`** instead
(an OTel SDK entry-point name: `otlp` = OTLP/gRPC, the default, or `otlp_proto_http` = OTLP/HTTP).
Without `OTEL_TRACES_EXPORTER=otlp_proto_http` set explicitly, every component's default gRPC
exporter dialed the Collector's HTTP port and failed
(`Failed parsing HTTP/2 ... Trying to connect an http1.x server`) — no traces reached the Collector
at all until this was corrected. `runtime/docker-compose.yml` sets `OTEL_TRACES_EXPORTER:
otlp_proto_http` for exactly this reason; `runtime/README.md` records the same finding.

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

Defined in `runbook.md` phase 6, following the same pattern as Quarkus's `runbook.md` phase 8: UTC
`window_start`/`window_end` recorded by `traffic.sh` itself, bracketing only the qualifying traffic,
plus an explicit sleep-based drain barrier before treating the window as closed (I3 spec §31 — task
execution is asynchronous and OTLP may flush after client traffic completes; observed drain latency
during I3.2 was under 10s from `traffic.sh` completion to the batch appearing at the Collector).

## Standard Celery instrumentation decision (I3 spec §29)

Native Airflow tracing (previous section) exposes task/dagrun/execution-API spans only — zero
Celery/broker/queue attributes on any span, confirmed by directly inspecting the Collector's `debug`
exporter output at `verbosity: detailed` across multiple qualifying runs. Per §29, I3.2 added the
standard, pinned `opentelemetry-instrumentation-celery==0.65b0` package as a **diagnostic-only**
experiment (via `_PIP_ADDITIONAL_REQUIREMENTS` plus an Airflow plugin calling
`CeleryInstrumentor().instrument()` — no Airflow architecture logic changed), purely to determine
whether the existing Celery interaction *could* be made observable, not to force a passing result.

Finding: instrumenting did surface a real `Producer`-kind span (`apply_async/execute_workload`) with
`messaging.destination_kind: queue` and `messaging.destination: default` — independently confirming
the destination is a queue (not a bare broker endpoint) and the queue name matches the pinned
`[operators] default_queue` — but no consumer-side span appeared (`CeleryInstrumentor
.is_instrumented_by_opentelemetry` was `False` on the worker process; Airflow's plugin-loading
evidently doesn't activate for the `celery worker` command's execution context the way it does for
the scheduler). More importantly, **every span's resource `service.name` was `unknown_service`
regardless of which component produced it** — scheduler, worker, and api-server spans are
indistinguishable by resource identity. This independently confirms, via real captured telemetry
rather than reading documentation alone, the `airflow-runtime-role-identity` finding already frozen
in `expected.yaml`'s `unresolved_identity` section: sender/consumer identity is not resolvable from
this profile's default OTel configuration, which is §23's first (and here, blocking) qualification
condition — regardless of how good the messaging-attribute evidence is.

The diagnostic package/plugin were **not** kept in the frozen `runtime/` profile (they didn't change
the qualification outcome, and I3.3 doesn't need them) — this section is the durable record of the
experiment and its result, per §29's own documentation requirement.

## Resource / port assumptions

Confirmed via I3.2: the pinned official Compose profile's own default ports apply unmodified —
`airflow-apiserver` on `8080`, AIP on `8000`, Neo4j on `7474`/`7687`, the Collector on `4317` (gRPC,
unused by this profile) / `4318` (HTTP, in use). No port conflicts encountered across three
independent stack starts.

## Cleanup/reset procedure

At minimum (I3 spec §58), each qualifying run resets: AIP Neo4j state, AIP runtime/evidence state,
the Airflow PostgreSQL volume, Redis broker state, relevant Airflow logs, temporary OTLP capture,
the validation output artifact, and Dag Run state — `docker compose down -v` for the Airflow stack,
mirroring Quarkus's `runbook.md` clean-state procedure.

## Mandatory boundary notes (I3 spec §38)

```text
PostgreSQL dependency               -> UNSUPPORTED by current AIP relation model (ground-truth.md)
runtime process/container identity  -> NOT automatically logical Service identity (ground-truth.md)
```
