# Validation Profile: `apache-airflow` (v0.5.0)

This is the bounded, reproducible profile that I5 Slice 5 exercises (I5 §6 item 1, §8.2). It is
carried over from the v0.3 I3 profile (`../../apache-airflow/profile.md`), with the v0.5 changes
below. The owner's merge of this dossier freezes it.

## Input classification (I5 §6, Draft 0.3)

| Input | Kind | Path | Content identity |
| --- | --- | --- | --- |
| Airflow public REST OpenAPI | upstream-supplied | `runtime/declarations/airflow-apiserver/openapi.yml` | sha256 `2c57114da43a131f68772f1660ed52ca7116089a20893ac5e5f6225ffde3abd9`, byte-identical to upstream `airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml` |
| OTLP traces from the running Airflow components (native Airflow OTel only) | independently captured | via `runtime/otel-collector-config.yaml` | The observation window of the qualifying run |
| OpenAPI identity binding (I1 §4.1 path 3) | AIP operator configuration | `runtime/declarations/identity-bindings.yaml` | Freeze commit |
| Validation Dag `i3_validation` (the profile workload, carried over unchanged from v0.3) | AIP operator configuration | `runtime/dags/i3_validation.py` | Freeze commit |
| Traffic script | AIP operator configuration | `runtime/traffic.sh` | Freeze commit |
| AIP configuration | AIP operator configuration | `runtime/config.airflow-i5.yaml` | Freeze commit |
| Compose profile, derived from the official Compose; its header lists the differences | AIP operator configuration | `runtime/docker-compose.yml` | Freeze commit |

There is no upstream-derived input. The official Compose is **evidence** for the component
inventory (`ground-truth.md`). The profile's Compose is operator configuration built from it, not a
verbatim input. The OpenAPI digest is also asserted by `tests/unit/test_airflow_v05_dossier.py`.
For operator configuration, "freeze commit" means the git blob at the dossier's merge commit.

## Components/processes started

These are unchanged from v0.3:
- `postgres`, `redis` and `airflow-init`;
- `airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor` and `airflow-triggerer`;
- **two** `airflow-worker` replicas (`--scale airflow-worker=2`), a runtime-instance identity case;
- Neo4j, the pinned OTel Collector, and the AIP candidate image.

`airflow-cli` and `flower` are not started.

## Runtime/deployment mode

The runtime is Docker Compose with CeleryExecutor, a Redis broker, and PostgreSQL for both the
metadata database and the result backend. All images are the pinned official release images
(`upstream.md`). There is no Kubernetes input, no Path B mapping and no `DEPLOYED_AS` (I5 §5, §8.2).

## Telemetry configuration

Native Airflow OTel only (I5 §8.2):
- `AIRFLOW__TRACES__OTEL_ON=True`, with the standard `OTEL_EXPORTER_OTLP_*` variables and
  `OTEL_TRACES_EXPORTER=otlp_proto_http`;
- `OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=airflow-i5`;
- no per-role `OTEL_SERVICE_NAME`;
- no additional instrumentation packages. The v0.3 diagnostic Celery instrumentation was never part
  of the frozen profile and is not used.

## Architecture flows exercised

`runtime/traffic.sh` is unchanged from v0.3, and runs these steps in order:
1. token authentication;
2. `GET /api/v2/monitor/health`;
3. `GET /api/v2/dags`, `GET /api/v2/dags/{dag_id}` and `GET /api/v2/variables`;
4. triggering the `i3_validation` Dag with a fixed `dag_run_id`;
5. polling the Dag Run to a terminal state;
6. verifying both task instances.

That exercises the nine selected operations and a Celery round trip through Redis.

## Supported AIP semantics in scope

| I5 §7 fact class | In this profile |
| --- | --- |
| `PROVIDES` | yes: the 9 selected operations |
| `CALLS` | in scope as a negative only (no in-scope caller) |
| `SENDS`, `PUBLISHES_TO`, `RECEIVES_FROM` | in scope as negatives only, over `queue:default` |
| `SUBSCRIPTION_OF`, `CARRIES`, `DEPLOYED_AS` | not applicable. The absence of messaging entities is a manual check (`ground-truth.md`). |

## Known upstream mechanisms out of scope

These are:
- PostgreSQL dependencies (`UNSUPPORTED`);
- the Execution API (`UNRESOLVED_IDENTITY`);
- process-role identity (`UNRESOLVED_IDENTITY`);
- Celery/Redis messaging (`INSUFFICIENT_EVIDENCE`);
- the 119 unselected REST operations;
- the UI and `/auth` routes.

## Comparison projection, window, and determinism (I5 §6 item 4, §12)

```text
run identity:               The candidate SHA is the HEAD of the clean checkout at the frozen
                            location. The AIP image aip-i5-candidate:<SHA> is rebuilt with
                            --no-cache for every run. Every third-party image is pinned by digest
                            in docker-compose.yml, and AIRFLOW_IMAGE_NAME cannot override it. The
                            running containers are verified before any import or traffic
                            (runbook.md steps 2-5).
observation environment:    airflow-i5
observation window:         [WINDOW_START, WINDOW_END]. WINDOW_END is stamped only after the
                            runbook.md step 9 drain barrier: a successful POST /v1/traces logged
                            by AIP since WINDOW_START, after a 15s settle, bounded to 45s.
comparison projection:      expected.yaml scope. The 9 selected operations plus queue:default, over
                            PROVIDES, CALLS, SENDS, PUBLISHES_TO and RECEIVES_FROM.
absolute checkout location: /home/michael/code/ArchitectureIntelligencePlatform
                            Both §12 byte-identity evaluations run from this one path. Declared
                            sources are mounted at the fixed container path /app/declarations.
normalization policy:       - The comparator report is compared byte-for-byte between paired runs.
                            - In actual.yaml, only the window bounds and capture timestamps may
                              differ between runs.
                            - Nothing is normalized by location (I5 §12).
                            - The raw actual.yaml of every run is retained.
rerun criteria:             A comparison is rerun only after a documented clean-state reset, and
                            only for one of three reasons:
                            (a) a readiness, Dag-registration or drain step failed and is
                                documented;
                            (b) a new candidate (I5 §12);
                            (c) a §6 post-freeze correction.
                            A rerun never replaces a failed comparison.
```

## Revision history

- **Freeze:** #242 (`1760786`).
- **Post-freeze runbook hardening** (#243). The expected facts, components, scope, traffic, capture
  authority and comparison rules are unchanged (I5 §6). Every Compose call now goes through
  `frozen_compose`. It passes a fixed project name, `--project-directory`,
  `-f runtime/docker-compose.yml` and `--env-file /dev/null`, so a gitignored `.env` (which could
  set `COMPOSE_FILE`) or a `docker-compose.override.yml` cannot change the run.

## Startup, traffic, and shutdown procedures

See `runbook.md`. Clean state is `docker compose down -v`. The Airflow logs, config and plugins are
named volumes, so they are removed too.
