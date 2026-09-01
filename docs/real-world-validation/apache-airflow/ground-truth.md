# Independent Ground Truth — Apache Airflow

Authored from primary upstream evidence at commit `3adbbe1c58e4532df1964cb7794805e763816ee8` —
**before** any AIP run against this system (I1 §5/§36, I3 spec §13/§39). No fact below is derived
from AIP output.

## Evidence sources used, strongest first (I1 §6-7, I3 spec §35)

1. Official machine-readable contract — the pinned public OpenAPI document
   `airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml` (fetched and
   parsed directly: `info.title` "Airflow API 2", 88 `/api/v2` paths).
2. Official architecture documentation — the Architecture Overview page (fetched at pin-adjacent
   version 3.3.1) and the OpenTelemetry traces configuration page (same version).
3. Official deployment/runtime configuration — the pinned official Compose profile
   `airflow-core/docs/howto/docker-compose/docker-compose.yaml` (fetched and inspected directly),
   plus `airflow-core/src/airflow/config_templates/config.yml` for `[operators] default_queue`.
4. Upstream source code — `shared/observability/src/airflow_shared/observability/traces/__init__.py`
   (`configure_otel()`) and `shared/observability/src/airflow_shared/observability/otel_env_config.py`,
   both fetched directly at the pinned commit.
5. Independently captured raw runtime evidence — none yet. I3.1 authors declaration-only ground
   truth; no Airflow instance has been started and no OTLP has been captured. Runtime-observed
   evidence is established in I3.2/I3.3 once the profile is running and traffic is exercised.

## Complete component inventory

From the pinned Compose file's own service list:

```text
airflow-apiserver      command: api-server        started by default   owns /api/v2 (public REST)
airflow-scheduler      command: scheduler          started by default   submits work to Celery
airflow-dag-processor  command: dag-processor      started by default   parses DAG files (isolated
                                                                          from the scheduler process
                                                                          for security, per official
                                                                          architecture docs)
airflow-worker         command: celery worker      started by default   executes tasks from the
                                                                          Celery queue
airflow-triggerer      command: triggerer          started by default   runs deferred/async triggers
postgres               image: postgres:16          started by default   metadata DB + Celery result
                                                                          backend
redis                  image: redis:7.2-bookworm   started by default   Celery broker
airflow-init           one-shot init job           runs once, exits     DB migration + admin user
                                                                          creation; not a running
                                                                          architecture component
airflow-cli            profiles: [debug]           NOT started by default (opt-in diagnostic only)
flower                 profiles: [flower]          NOT started by default (opt-in diagnostic only)
```

No `container_name` is set on any service in the pinned Compose file, so
`docker compose up --scale airflow-worker=2` scales the worker role reproducibly without a
Compose-level rewrite (I3 spec §9's preference for two workers).

## Logical Service boundary analysis (I3 spec §11-13)

**Interpretation A** — Airflow is one logical Service; the five process roles above are
runtime/deployment structure outside the current canonical `Service` abstraction.

**Interpretation B** — `airflow-api-server`, `airflow-scheduler`, `airflow-worker`,
`airflow-dag-processor`, `airflow-triggerer` are each distinct logical Services, because their
architecture boundaries are independently meaningful.

### Evidence for Interpretation B (architectural)

- The official Architecture Overview page describes the components as "separate, independently
  deployable" and states Airflow "is able to run in a distributed environment - where various
  components can run on different machines."
- The DAG processor "always runs as a standalone process, ensuring the scheduler never has direct
  access to DAG bundles" — a deliberate security-motivated process boundary, not an incidental
  deployment detail.
- Each role has its own Compose service definition, its own health check
  (`airflow jobs check --job-type <RoleJob>` for scheduler/dag-processor/triggerer; a Celery
  `inspect ping` for the worker), and its own `restart: always` lifecycle — independent runtime
  lifecycle per I3 spec §12's criteria.
- The worker role scales independently (`--scale airflow-worker=2`) while the others do not in this
  profile — independent scaling per I3 spec §12.
- The API server is the sole owner of a public, versioned, independently documented network
  contract (`/api/v2`, its own generated OpenAPI document) — public contract ownership and network
  addressability per I3 spec §12.

### Evidence for Interpretation A / against a naive per-role split (runtime-identity)

- `configure_otel()` (`shared/observability/.../traces/__init__.py`) constructs the `TracerProvider`
  with `resource=None` unless the *deprecated* `otel_service` config key is set. When `resource` is
  `None`, the OpenTelemetry SDK falls back to its own default `Resource` (`service.name` taken from
  the standard `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` environment variables if set, else
  `unknown_service`).
- The pinned Compose file gives every one of `airflow-apiserver`, `airflow-scheduler`,
  `airflow-dag-processor`, `airflow-worker`, `airflow-triggerer` the *same* environment block via
  the shared `x-airflow-common` YAML anchor. Nothing in the pinned, unmodified official profile sets
  a per-role `OTEL_SERVICE_NAME` or `OTEL_RESOURCE_ATTRIBUTES` value.
- **Net effect**: under the pinned official profile with no additional configuration, native
  Airflow runtime telemetry does not distinguish these five roles by resource identity at all —
  they would all present the same (or all-`unknown_service`) `service.name`. Upstream telemetry
  identity (an explicit I3 spec §12 criterion) does not, by default, support a five-way split.

### Decision

For the profile as pinned (no additional per-role OTel configuration), this dossier freezes:

```text
service:airflow-api-server
    the one logical Service this dossier asserts with full confidence — it independently owns
    a public, versioned REST contract (/api/v2) that no other component provides, and is the
    sole Compose service running `command: api-server`.

airflow-scheduler / airflow-dag-processor / airflow-worker / airflow-triggerer
    NOT asserted as distinct canonical Services in this qualifying profile. Real architectural
    separation exists (Interpretation B's evidence above is not disputed), but the pinned
    official profile's own native telemetry configuration does not expose it, and I3 spec §13
    requires "unresolved > guessed." Their runtime-role identity is recorded as
    UNRESOLVED_IDENTITY below, not folded into `service:airflow-api-server` and not split
    into four guessed Service ids.
```

This is a statement about what the *default, pinned, unmodified* profile can safely establish —
not a claim that Interpretation B is wrong. A separate, pre-declared diagnostic profile that sets
explicit per-role `OTEL_SERVICE_NAME` values (standard OTel configuration, decided now from this
architectural reasoning rather than reactively after observing AIP's behavior) may test
Interpretation B directly. Per I3 spec §14, any such experiment SHALL be documented separately and
SHALL NOT retroactively redefine this frozen ground truth.

### Runtime role vs. runtime instance vs. deployment artifact (I3 spec §12)

```text
logical identity     service:airflow-api-server (frozen); the other four roles: unresolved
runtime role          scheduler / dag-processor / worker / triggerer / api-server, as named by
                      the pinned Compose file's own service names and `command:` values
runtime instance      one container per role, except the worker (deliberately scaled to 2 —
                      see "Multiple runtime instances" below)
deployment artifact    the pinned `apache/airflow` image, one per container, exact tag recorded
                      in profile.md
```

## Bounded REST provider inventory (I3 spec §16-17)

Selected from the pinned OpenAPI document's 88 `/api/v2` paths — 9 operations, within the 8-15
target, covering `monitor/health`, `Dags`, `Dag Runs`, `Task Instances`, and `Variables`:

```text
GET  /api/v2/monitor/health                                              get_health
GET  /api/v2/dags                                                         get_dags
GET  /api/v2/dags/{dag_id}                                                get_dag
POST /api/v2/dags/{dag_id}/dagRuns                                        trigger_dag_run
GET  /api/v2/dags/{dag_id}/dagRuns                                        get_dag_runs
GET  /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}                           get_dag_run
GET  /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances              get_task_instances
GET  /api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}    get_task_instance
GET  /api/v2/variables                                                    get_variables
```

Selection criteria satisfied: stable `/api/v2` routes, present verbatim in the pinned OpenAPI,
useful to the deterministic traffic script's phases (readiness -> trigger -> poll -> verify, I3
spec §33), representative path-template behavior (including a `{dag_id}/{dag_run_id}/{task_id}`
three-level template), bounded enough for review. `/api/v2/auth/login` and `/api/v2/auth/logout`
exist in the same document but are UI session-redirect endpoints, not the API authentication
mechanism, and are excluded from the bounded set.

Sole provider: `airflow-api-server` — the only Compose service running `command: api-server`, and
the only component the pinned OpenAPI document itself attributes these routes to.

Canonical identities (per `app/canonical/ids.py`'s `service_id()`/`operation_id()` format):

```text
service:airflow-api-server

operation:service:airflow-api-server:GET:/api/v2/monitor/health
operation:service:airflow-api-server:GET:/api/v2/dags
operation:service:airflow-api-server:GET:/api/v2/dags/{dag_id}
operation:service:airflow-api-server:POST:/api/v2/dags/{dag_id}/dagRuns
operation:service:airflow-api-server:GET:/api/v2/dags/{dag_id}/dagRuns
operation:service:airflow-api-server:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}
operation:service:airflow-api-server:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances
operation:service:airflow-api-server:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}
operation:service:airflow-api-server:GET:/api/v2/variables
```

## REST caller ground truth (I3 spec §18)

None established in I3.1 — no traffic has run yet. The external validation traffic script that
I3.2 will add is not itself an AIP Service and will not be represented as a synthetic architecture
caller merely because it invokes the public REST API (I3 spec §18, first paragraph). Internal
Airflow HTTP interactions (e.g. worker/task -> execution API) are addressed separately below.

## Execution API boundary (I3 spec §19)

The pinned official profile points workers/tasks at
`http://airflow-apiserver:8080/execution/`. No pinned OpenAPI or other machine-readable contract
document describes this surface in the repository at this commit (the only related file,
`task-sdk/src/airflow/sdk/execution_time/schema/schema.json`, is a payload JSON Schema, not a REST
operation contract) — confirmed by inspecting the full pinned repository tree. Because the
operation identity cannot be independently established from a pinned contract:

```text
UNRESOLVED_IDENTITY: execution API boundary
```

This is not automatically equivalent to the stable `/api/v2` contract and is not treated as such
anywhere in this dossier or in `expected.yaml`.

## CeleryExecutor / Redis / queue ground truth (I3 spec §20-22)

```text
executor:            CeleryExecutor (AIRFLOW__CORE__EXECUTOR=CeleryExecutor)
broker:              Redis, redis://:@redis:6379/0 (AIRFLOW__CELERY__BROKER_URL) — broker
                     technology / server, NOT a Queue identity (I3 spec §21)
result backend:      PostgreSQL, db+postgresql+psycopg2://airflow:airflow@postgres/airflow
default task queue:  "default" — confirmed from `[operators] default_queue` in
                     airflow-core/src/airflow/config_templates/config.yml (`default: "default"`);
                     the pinned Compose profile does not override
                     AIRFLOW__OPERATORS__DEFAULT_QUEUE
producer direction:  scheduler/executor submits work to the Celery queue
consumer direction:  worker(s) consume queued work
```

Candidate queue identity: `queue:default`, per `app/canonical/ids.py`'s `queue_id()` format.

## No synthetic AsyncAPI for Airflow (I3 spec §24)

This dossier does not author, and I3 will not author, an AIP-specific AsyncAPI document to turn
the Celery topology into declared `SENDS`/`RECEIVES_FROM` facts. The Airflow messaging test is a
runtime/evidence test, established only from independently captured OTLP once I3.2/I3.3 exercise
real traffic.

## PostgreSQL boundary (I3 spec §25)

Current AIP does not model generic database dependencies as first-class canonical relations.
Mandatory architecture observations, all classified `UNSUPPORTED` (mechanism
`database-dependency`) with respect to the current canonical relation vocabulary:

```text
airflow-scheduler       -> PostgreSQL   (metadata database)
airflow-api-server      -> PostgreSQL   (metadata database)
Celery result backend   -> PostgreSQL   (result backend)
```

None of these will be represented as `Queue`, an HTTP `Operation`, or any other supported relation
merely to increase coverage.

## Dag processor and triggerer boundary (I3 spec §26)

`airflow-dag-processor` and `airflow-triggerer` are recorded in the component inventory above as
valid, default-started Airflow runtime components. Per the Logical Service boundary decision
above, neither is asserted as a distinct canonical `Service` in this qualifying profile — they fall
under the same "unresolved runtime role" treatment as the scheduler and worker roles, for the same
reason (no native per-default-profile telemetry distinction). This is a ground-truth/identity
finding, not a relation-shaped fact, and per I3 spec §41 it is recorded here rather than as a
synthetic `expected.yaml` entry.

## Identity normalization rationale (I3 spec §42)

AIP's OpenAPI adapter derives a service's canonical id from the declaration directory/service name
supplied to the importer (`app/ingestion/openapi_adapter.py`'s `service_id` parameter), not from
the OpenAPI `info.title` (which is the generic "Airflow API 2" and does not name the owning
component). This dossier chooses `airflow-api-server`, matching the pinned Compose file's own
service name for the one component running `command: api-server` — the same identity Airflow's own
deployment tooling uses for this role. `queue:default` is taken directly from Celery's own
`default_queue` configuration name, independent of any AIP output.

This normalization is frozen before comparison. It will not be revised after seeing what AIP
actually resolves (I3 spec §42's prohibited list: no fuzzy-matching, no prefix-dropping, no
after-the-fact merging or splitting, no repairing AIP ids in comparator code).

## Multiple runtime instances (I3 spec §43)

The qualifying profile is intended to run two `airflow-worker` container instances
(`docker compose up --scale airflow-worker=2`), both inheriting the identical `x-airflow-common`
environment block — no resource attribute in the pinned profile is expected to distinguish them
beyond ephemeral container/hostname identifiers (which I3 spec §59 explicitly allows to differ
across repeatable runs). This dossier freezes the rule I3.3 must be checked against:

```text
AIP SHOULD NOT create two logical Services merely because two worker instances exist.
AIP SHALL NOT collapse the worker role into service:airflow-api-server merely because native
telemetry may not distinguish them, if doing so creates a false PROVIDES/CALLS claim.
```

If the profile proves two workers operationally impractical, one worker MAY be used for the
qualifying run per I3 spec §9, with the reason documented in `profile.md` and this
multiple-instance question left explicit rather than silently dropped.

## Operation identity rule (I3 spec §44)

All nine selected operations above are route templates (e.g.
`/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}`), never concrete Dag/DagRun/TaskInstance IDs.
Whatever concrete `dag_id` the I3.2 validation Dag uses, an operation match must resolve to the
template form above — no comparator-side route reconstruction is used or will be used.

## Known ambiguities / unresolved / insufficient-evidence items

```text
UNRESOLVED_IDENTITY   execution API boundary (§19 above) — no pinned contract exists to
                      independently establish operation identity.
UNRESOLVED_IDENTITY   airflow-scheduler / airflow-dag-processor / airflow-worker /
                      airflow-triggerer logical Service identity under the pinned profile's
                      default (undifferentiated) native telemetry configuration.
INSUFFICIENT_EVIDENCE Celery SENDS/RECEIVES_FROM runtime status — no traffic has been run and no
                      OTLP has been captured yet (I3.1 authors declaration-only ground truth);
                      established in I3.2/I3.3 once real messaging telemetry exists.
```

No `CALLS` ground truth is asserted or attempted in I3.1 for the reason above (§18): it requires
independent caller-side evidence this dossier does not yet have, and none is manufactured.

## Change log (I1 §37: ground truth may change only for a documented, non-AIP-output reason)

None yet — this is the initial freeze.
