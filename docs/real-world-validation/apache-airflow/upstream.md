# Upstream Identity — Apache Airflow

```text
project:              Apache Airflow
role:                 Real-World OSS Software
repository:            https://github.com/apache/airflow
license:               Apache-2.0
release:               3.3.1
tag:                   3.3.1
tag object:            8d7af742565409cf8857c92c1cec98568dae4296
full commit SHA:        3adbbe1c58e4532df1964cb7794805e763816ee8
release date:           2026-08-12
pin date:               2026-08-31
official image:         apache/airflow (image name/version pin recorded in profile.md)
```

Confirmed live via GitHub's tree API at pin time
(`GET /repos/apache/airflow/git/trees/3adbbe1c58e4532df1964cb7794805e763816ee8?recursive=1`,
200 OK, `truncated: false`) and by fetching the pinned Compose and OpenAPI files directly (both
200 OK) — see "Relevant upstream references" below for exact paths.

A validation result applies only to this pinned commit (I1 §8 / I3 spec §4). Changing the pinned
revision requires a documented reason, a new exact SHA, a new release/tag identity, a ground-truth
review against the new SHA, and a profile re-freeze (I3 spec §4).

This is the **Airflow upstream release identity** — distinct from the **AIP candidate identity**
(the AIP commit/build under test), which is not yet recorded: I3.1 performs no AIP comparison run
(I3 spec §70's I3.1 scope). The AIP candidate SHA is first recorded in `results.md` at Phase D
(I3.3).

## Relevant provider dependencies

```text
executor:               CeleryExecutor
broker:                 Redis (redis://:@redis:6379/0 in the pinned official Compose profile)
result backend:         PostgreSQL (db+postgresql+psycopg2://airflow:airflow@postgres/airflow)
metadata database:      PostgreSQL (postgresql+psycopg2://airflow:airflow@postgres/airflow)
execution API:          http://airflow-apiserver:8080/execution/ (internal, task/worker <-> API server)
```

Source: `airflow-core/docs/howto/docker-compose/docker-compose.yaml` @ pinned commit (fetched and
inspected directly — see `ground-truth.md` for the full component/env extraction).

## Relevant upstream architecture references

```text
Architecture Overview
    https://airflow.apache.org/docs/apache-airflow/3.3.1/core-concepts/overview.html
Airflow 3 architecture changes
    https://airflow.apache.org/docs/apache-airflow/3.3.1/
Public REST API reference
    https://airflow.apache.org/docs/apache-airflow/3.3.1/stable-rest-api-ref.html
CeleryExecutor
    https://airflow.apache.org/docs/apache-airflow-providers-celery/3.23.1/celery_executor.html
OpenTelemetry traces
    https://airflow.apache.org/docs/apache-airflow/3.3.1/administration-and-deployment/logging-monitoring/traces.html
```

All fetched at specification/ground-truth time; the dossier records the Airflow version (3.3.1)
alongside each reference per I3 spec §7 (moving `stable` docs may be used for research, but the
version is recorded here rather than relied upon implicitly).

The CeleryExecutor reference above is now version-pinned (PR #47 review F3 — a previous version of
this file left it as the moving `stable` URL, with the exact provider version recorded as not yet
fixed). The `apache-airflow-providers-celery` package versions independently of Airflow core; its
exact version, as actually installed in the digest-pinned `apache/airflow:3.3.1` image
(`sha256:0c4bcc0370e526de1b7892a3bf4343d260c6c82359c66f77155b53cd773d6339`), was queried directly
from a running container during I3.4's revalidation run (`docker compose exec airflow-scheduler
airflow providers list`):

```text
apache-airflow-providers-celery   3.23.1
celery                            5.6.3
```

The Celery/Redis ground truth this dossier actually relies on (broker URL, result backend, default
queue name) still comes from the pinned Compose file and `config_templates/config.yml`, not this
doc link — this version pin exists so the documentation reference itself stays exact, and so any
future re-run of this exact image can confirm identical provider/instrumentation versions per I3
spec §72's Upstream category.

## Relevant OpenAPI source

```text
airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml
@ 3adbbe1c58e4532df1964cb7794805e763816ee8
```

Fetched directly: `info.title` = "Airflow API 2", 88 total paths under `/api/v2` (excluding
UI-only routes, which the OpenAPI document itself distinguishes from the stable contract per I3
spec §15). No standalone *generated OpenAPI file* exists in the pinned repository for the internal
execution API (`/execution/*`) the way one does for `/api/v2` — but the pinned source
(`airflow-core/src/airflow/api_fastapi/execution_api/app.py`, `routes/__init__.py`,
`routes/task_instances.py`) independently defines a full FastAPI application with concrete route
declarations, which is valid I1 tier-4 (upstream source code) evidence. That source evidence is
what `ground-truth.md`'s execution-API boundary classification (I3 spec §19) is actually based on —
the absence of a *generated contract file* is not itself load-bearing; see `ground-truth.md` for
why the classification remains `UNRESOLVED_IDENTITY` (caller identity + deliberate scope, not
absence of evidence).

## Relevant Compose source

```text
airflow-core/docs/howto/docker-compose/docker-compose.yaml
@ 3adbbe1c58e4532df1964cb7794805e763816ee8
```

Also referenced: `scripts/ci/docker-compose/otel-collector-config.yaml` @ the same commit, the
project's own CI reference Collector config (OTLP HTTP receiver -> batch -> debug/Jaeger
exporters) — cited in `profile.md` as prior art, not used verbatim.

## Why this is classified as Real-World OSS Software, not an external reference architecture

Apache Airflow is a mature, independently governed Apache Software Foundation project running in
production at a large number of organizations, not a sample/demo application authored to showcase
a framework (contrast I2's Quarkus Super Heroes). Per I3 spec §1/§21, it is deliberately selected
because its architecture — API server, scheduler, DAG processor, Celery workers, a broker, and
asynchronous task execution — does not map trivially to "one process = one Service," making it the
model-stress iteration of `v0.3` rather than a reference-architecture comparison.
