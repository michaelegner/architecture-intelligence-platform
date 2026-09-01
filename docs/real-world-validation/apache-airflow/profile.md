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

Defined in `runbook.md` phase 6, and owned entirely by the runbook, not `traffic.sh` (PR #45
re-review N1 — an earlier version of this section described `traffic.sh` as recording the window,
which stopped being true once PR #45 review F1's fix moved window ownership out of the script to
resolve a race between two independently-stamped, undrained timestamps). The runbook captures UTC
`window_start` immediately before invoking `traffic.sh`, then — only after `traffic.sh` returns —
runs an explicit drain barrier (a bounded sleep plus a retried check that AIP's own access log shows
a successful `POST /v1/traces` since `window_start`) before stamping `window_end` and treating the
window as closed (I3 spec §31 — task execution is asynchronous and OTLP may flush after client
traffic completes; observed drain latency during I3.2 was under 10s from `traffic.sh` completion to
the batch appearing at the Collector).

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
`[operators] default_queue` — but no consumer-side span ever appeared across multiple runs, despite
the same plugin file sitting in the same shared volume every Airflow component (including both
workers) mounts. (An earlier version of this section attributed this to `CeleryInstrumentor
().is_instrumented_by_opentelemetry` returning `False` when checked via a separate `docker exec ...
python3 -c` process on the worker — PR #45 re-review's F2 verification process surfaced that this
check is unreliable: it reads a *new* process's own fresh state, not the actual running daemon's, and
printed `False` on the scheduler too even in a run where the scheduler's own producer span
unambiguously proves it was instrumented. The only evidence that survives is the direct,
functional one: no consumer-side span was ever observed.) More importantly, **every span's resource
`service.name` was `unknown_service`
regardless of which component produced it** — scheduler, worker, and api-server spans are
indistinguishable by resource identity. This independently confirms, via real captured telemetry
rather than reading documentation alone, the `airflow-runtime-role-identity` finding already frozen
in `expected.yaml`'s `unresolved_identity` section: sender/consumer identity is not resolvable from
this profile's default OTel configuration, which is §23's first (and here, blocking) qualification
condition — regardless of how good the messaging-attribute evidence is.

The diagnostic package/plugin were **not** kept in the frozen `runtime/` profile (they didn't change
the qualification outcome, and I3.3 doesn't need them) — this section, plus the exact reproduction
recipe below (PR #45 review's "Recommended strengthening"), is the durable record of the experiment
and its result, per §29's own documentation requirement.

### Exact reproduction recipe

All commands below run from `runtime/` (`docker compose` is invoked without `-f`, so it resolves the
profile from the current directory). `/opt/airflow/plugins` is the named volume `airflow-i3-plugins`,
not a host bind mount (PR #45 review F2 changed this) — a file only placed under a local
`runtime/plugins/` directory never reaches the containers. `docker cp` into the shared volume through
the running scheduler container instead, resolved dynamically rather than by its generated name
(PR #45 re-review N3 — `runtime-airflow-scheduler-1` assumes the default Compose project name, which
the runbook's own readiness fix deliberately stopped depending on):

1. Save the plugin locally (content unchanged from the original experiment — Airflow's own
   plugin-loading extension point, no Airflow architecture logic changed):
   ```python
   # otel_celery_instrumentation.py
   from opentelemetry.instrumentation.celery import CeleryInstrumentor

   CeleryInstrumentor().instrument()
   ```
2. Copy it into the shared `airflow-i3-plugins` volume via the running scheduler container (any
   container using `airflow-common`'s volumes works identically — it's the same named volume), and
   explicitly set a world-readable mode — `docker cp` preserves the source file's own mode rather
   than guaranteeing one, so a restrictive local umask would otherwise copy in a file the container's
   `airflow` user (uid 50000) can't read (verified: a `600`-mode source file copied in as `600`,
   unreadable by uid 50000, until explicitly `chmod`ed):
   ```bash
   SCHEDULER_ID="$(docker compose ps -q airflow-scheduler)"
   docker cp otel_celery_instrumentation.py "$SCHEDULER_ID:/opt/airflow/plugins/otel_celery_instrumentation.py"
   docker exec -u root "$SCHEDULER_ID" chmod 644 /opt/airflow/plugins/otel_celery_instrumentation.py
   ```
3. Add one line to `runtime/docker-compose.yml`'s `airflow-common-env`:
   ```yaml
   _PIP_ADDITIONAL_REQUIREMENTS: opentelemetry-instrumentation-celery==0.65b0
   ```
4. `docker compose up -d --scale airflow-worker=2 --force-recreate airflow-scheduler airflow-worker`
   (only these two need the package; `_PIP_ADDITIONAL_REQUIREMENTS` reinstalls at every container
   start, so this is intentionally not left in the frozen profile — it adds real startup latency for
   no qualifying benefit once the experiment's conclusion is recorded here). The named volume
   persists across `--force-recreate` (only `down -v` empties it — verified), so the plugin file
   copied in step 2 is still there for the freshly-started scheduler process to load.
5. Run `traffic.sh`.

**Positive activation check — must be functional, not process-introspection:** checking
`CeleryInstrumentor().is_instrumented_by_opentelemetry` via a *separate* `docker exec ... python3 -c`
process reads that new process's own fresh state, not the actual running scheduler daemon's — tried
this while re-verifying the recipe and it printed `False` even though the daemon plainly was
instrumented (the producer span below appeared in the same run). The only reliable positive check is
functional: inspect the Collector's own `debug` exporter output (`verbosity: detailed`) for the
instrumentation's scope:

```bash
docker compose logs otel-collector | grep -A5 "InstrumentationScope opentelemetry.instrumentation.celery"
```

Presence of that scope (and the `Producer`-kind span below) is the positive check; its absence means
the plugin didn't load and the experiment should be re-attempted from step 2 before concluding
anything.

Representative sanitized excerpt actually captured (IDs/timestamps redacted, message content
unchanged):

```text
ResourceSpans
Resource attributes:
     -> telemetry.sdk.language: Str(python)
     -> telemetry.sdk.name: Str(opentelemetry)
     -> telemetry.sdk.version: Str(1.44.0)
     -> service.instance.id: Str(<redacted>)
     -> deployment.environment.name: Str(airflow-i3)
     -> service.name: Str(unknown_service)
ScopeSpans
InstrumentationScope opentelemetry.instrumentation.celery 0.65b0
Span
    Kind           : Producer
    Name           : apply_async/execute_workload
Attributes:
     -> celery.action: Str(apply_async)
     -> messaging.message.id: Str(<redacted>)
     -> celery.task_name: Str(execute_workload)
     -> messaging.destination_kind: Str(queue)
     -> messaging.destination: Str(default)
```

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
