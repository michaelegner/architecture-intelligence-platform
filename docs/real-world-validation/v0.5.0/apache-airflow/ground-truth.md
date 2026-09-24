# Independent Ground Truth: `apache-airflow` (v0.5.0)

This was drafted on 2026-09-24 from upstream evidence at commit
`3adbbe1c58e4532df1964cb7794805e763816ee8` (release 3.3.1) only. No qualifying AIP output for this
target existed or was inspected. The owner reviews it, and merging the dossier PR freezes it
(I5 §6, spec Draft 0.3).

## Rules

- Every fact cites its upstream source. Unless stated otherwise, a path is relative to the upstream
  repository root at the pin, and `path:N` is line N.
- AIP graph contents, API responses, comparator output, and generated prose never determine a fact.
- v0.3 used the same pin. Its dossier (`../../apache-airflow/`) was research input only. Every fact
  below was re-derived from the upstream files, including the v0.3 runtime findings on native
  telemetry. Those findings describe AIP-independent upstream behavior, and v0.3 recorded them as
  research.

## Evidence sources used, strongest first

1. **Official machine-readable contract.** `airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml`. Its title is "Airflow API 2", with 88 paths and
   128 operations. There is no AsyncAPI document for Airflow.
2. **Official deployment configuration.** The official Compose file `airflow-core/docs/howto/docker-compose/docker-compose.yaml`, and the configuration
   reference `airflow-core/src/airflow/config_templates/config.yml`.
3. **Upstream source code.**
   - `airflow-core/src/airflow/api_fastapi/app.py`, and
     `airflow-core/src/airflow/api_fastapi/execution_api/`: the Execution API.
   - `shared/observability/src/airflow_shared/observability/traces/__init__.py`: OTel resource
     identity.
4. **Independently captured runtime evidence.** None is used for the freeze. OTel is captured during
   the qualifying run (Slice 5) and is compared, not used to author facts.

## Components (official Compose)

| Component | Command / image | Citation | Role in I5 |
| --- | --- | --- | --- |
| `airflow-apiserver` | `api-server`, port 8080 | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:122-126` | The only declared Service. It serves `/api/v2` and `/execution`. |
| `airflow-scheduler` | `scheduler` | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:139-141` | Process role, `UNRESOLVED_IDENTITY` |
| `airflow-dag-processor` | `dag-processor` | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:154-156` | Process role, `UNRESOLVED_IDENTITY` |
| `airflow-worker` | `celery worker`, 2 replicas in the profile | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:169-171` | Process role, `UNRESOLVED_IDENTITY` |
| `airflow-triggerer` | `triggerer` | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:192-194` | Process role, `UNRESOLVED_IDENTITY` |
| `airflow-init` | one-shot migration and user creation | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:207` | Not a runtime role |
| `postgres` | `postgres:16` upstream, pinned to 16.15 in the profile | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:93-94` | Metadata DB and result backend, `UNSUPPORTED` |
| `redis` | `redis:7.2-bookworm` | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:108-111` | Celery broker, `INSUFFICIENT_EVIDENCE` |
| `airflow-cli`, `flower` | opt-in profiles | `airflow-core/docs/howto/docker-compose/docker-compose.yaml:299, 317-319` | Not started |

All Airflow components share one image and one environment block (`x-airflow-common`,
`airflow-core/docs/howto/docker-compose/docker-compose.yaml:47-66`). That block sets:
- `AIRFLOW__CORE__EXECUTOR: CeleryExecutor` (`:58`);
- a PostgreSQL metadata connection (`:60`);
- a PostgreSQL Celery result backend (`:61`);
- a Redis broker (`:62`);
- `AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://airflow-apiserver:8080/execution/` (`:66`).

## Service identity

The canonical Service id is `service:airflow-apiserver`, the official Compose component that
serves the REST API (`airflow-core/docs/howto/docker-compose/docker-compose.yaml:122-124`). The upstream OpenAPI carries no `x-aip-service-id`, and I1
§4.1 forbids deriving identity from a directory name or `info.title`. So
`runtime/declarations/identity-bindings.yaml` binds the OpenAPI source to this Service
(I1 §4.1 path 3). That file is disclosed AIP operator configuration, not ground truth.

## Selected operations: PROVIDES (9)

I5 §8.2 bounds `PROVIDES` to the operations the dossier selects. The nine v0.3 operations were
re-reviewed at the pin. Each is present verbatim, is stable `/api/v2` public API, and is used by the
frozen traffic's phases: readiness, then trigger, then poll, then verify. `/auth/*` session
endpoints are excluded. The citation is each operation's `operationId` line in `airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml`.

| Fact | Citation |
| --- | --- |
| `service:airflow-apiserver` PROVIDES `GET /api/v2/monitor/health` (`get_health`) | `:10681` (path `:10676`) |
| PROVIDES `GET /api/v2/dags` (`get_dags`) | `:3485` (path `:3479`) |
| PROVIDES `GET /api/v2/dags/{dag_id}` (`get_dag`) | `:3955` (path `:3949`) |
| PROVIDES `POST /api/v2/dags/{dag_id}/dagRuns` (`trigger_dag_run`) | `:2649` (path `:2080`) |
| PROVIDES `GET /api/v2/dags/{dag_id}/dagRuns` (`get_dag_runs`) | `:2155` (path `:2080`) |
| PROVIDES `GET /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}` (`get_dag_run`) | `:1902` (path `:1897`) |
| PROVIDES `GET /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances` (`get_task_instances`) | `:8022` (path `:7993`) |
| PROVIDES `GET /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}` (`get_task_instance`) | `:6879` (path `:6873`) |
| PROVIDES `GET /api/v2/variables` (`get_variables`) | `:9552` (path `:9546`) |

The profile imports the complete upstream document. The other 119 operations are declared too, but
they fall outside the frozen scope.

## REST callers: no CALLS

No in-scope Service calls a selected operation. The frozen traffic client (`runtime/traffic.sh`) is
an external validation driver, not an architecture Service. No CALLS fact is expected, and any CALLS
into a selected operation is unexpected (scope closure).

## Execution API boundary: UNRESOLVED_IDENTITY

`airflow-apiserver` also mounts the private Execution API at `/execution`
(`airflow-core/src/airflow/api_fastapi/app.py:64, 140-143`). Its routes include
`/task-instances`, `/variables` and `/xcoms`
(`airflow-core/src/airflow/api_fastapi/execution_api/routes/__init__.py:50-67`). Task runners reach
it through `AIRFLOW__CORE__EXECUTION_API_SERVER_URL` (`airflow-core/docs/howto/docker-compose/docker-compose.yaml:66`). The caller is a worker or
task-runner process role, which has no admitted identity (next section). So no CALLS is
established. The Execution API has no generated contract file in the repository, and it is not in
the selected scope (`airflow-execution-api-boundary`).

## Process-role identity: UNRESOLVED_IDENTITY

The scheduler, dag-processor, worker and triggerer are distinct processes of one image. The profile
sets `OTEL_RESOURCE_ATTRIBUTES` only to `deployment.environment.name=airflow-i5`, with no per-role
`OTEL_SERVICE_NAME`. When `OTEL_RESOURCE_ATTRIBUTES` is set, Airflow ignores its deprecated
`[traces] otel_service` option
(`shared/observability/src/airflow_shared/observability/traces/__init__.py:174-177`). So no role
carries a distinct, admitted runtime identity. None is asserted as a canonical Service, and the two
worker replicas are runtime instances of one role (`airflow-runtime-role-identity`).

## CeleryExecutor and Redis: INSUFFICIENT_EVIDENCE

```text
executor:      CeleryExecutor                    airflow-core/docs/howto/docker-compose/docker-compose.yaml:58
broker:        redis://:@redis:6379/0            airflow-core/docs/howto/docker-compose/docker-compose.yaml:62
result store:  PostgreSQL                        airflow-core/docs/howto/docker-compose/docker-compose.yaml:61
task queue:    "default"                         airflow-core/src/airflow/config_templates/config.yml:2382-2388
                                                 ([operators] default_queue, section at :2332)
direction:     the scheduler/executor submits task messages; the workers consume them
```

There is no declaration (no AsyncAPI), and native Airflow OTel, the only telemetry in this profile
(I5 §8.2), gives no admitted sender or receiver identity for the broker exchange. So the expected
state is:
- **no** `SENDS`, `RECEIVES_FROM` or `PUBLISHES_TO`;
- **no** Queue, Topic or Subscription fact (`airflow-celery-messaging`).

`expected.yaml` enforces this with scope closure over `queue:default`. It also has two named
forbidden facts for `service:airflow-apiserver`, the only declared Service, so the only one a
Celery Queue fact could be attributed to.

## PostgreSQL: UNSUPPORTED

The metadata database (`airflow-core/docs/howto/docker-compose/docker-compose.yaml:60`) and the Celery result backend (`airflow-core/docs/howto/docker-compose/docker-compose.yaml:61`) are database dependencies
outside the v0.5 relation vocabulary. They are recorded as three `UNSUPPORTED` entries.

## Checks the comparator cannot express

Slice 5 SHALL verify these from public reads and the import response, and record the result in
`results.md`:
1. **Import.** The declarations source is accepted, with the Service identity resolved through the
   bindings.
2. **No role Services.** No Service other than `service:airflow-apiserver` is minted from this
   profile's declarations or telemetry for the Airflow process roles.
3. **No messaging entities.** No Queue, Topic or Subscription entity exists.

## Unknowns

There are none beyond the classified entries above.

## Change log

- 2026-09-24: initial v0.5 freeze draft (I5 Slice 3).
