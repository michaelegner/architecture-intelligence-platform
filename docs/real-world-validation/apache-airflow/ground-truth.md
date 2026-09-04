# Independent Ground Truth — Apache Airflow

Authored from primary upstream evidence at commit `3adbbe1c58e4532df1964cb7794805e763816ee8` —
**before** any AIP run against this system (I1 §5/§36, I3 spec §13/§39). No fact below is derived
from AIP output.

## Provisional scope of this freeze (I3 spec §48-49) — RESOLVED by I3.2, see Change log

The I3 spec's own normative phase order runs Phase A (upstream/identity research, this document)
-> Phase B (observability qualification: start the profile, capture raw OTel independently) ->
Phase C (ground-truth freeze) -> Phase D (first AIP comparison), and §49's freeze gate requires
"raw OTel evidence captured enough to qualify runtime expectations" before Phase D. I3.1 performs
only Phase A — no Airflow instance has been started and no OTLP has been captured yet — so this
freeze is **complete and final for every declaration-only fact** (the 9 `PROVIDES` facts, the
PostgreSQL/execution-API/runtime-role boundaries, all of which need no runtime evidence to
establish), but **provisional for the Celery messaging boundary specifically**: whether a real,
independently qualified `SENDS`/`RECEIVES_FROM` relation belongs in `expected.yaml` cannot be
decided until Phase B's raw telemetry exists. `queue:default`'s scope entry and the
`airflow-celery-messaging-runtime-status` `insufficient_evidence` item below are the visible marker
of that: I3.2 SHALL complete Phase B/the §49 freeze gate for this item specifically — adding a
qualified expected relation if the evidence supports one — **before** I3.3 runs the first AIP
comparison (I3 spec §39's own ordering: "before the first qualifying AIP comparison"). This is an
allowed, documented ground-truth amendment under this file's own Change log policy below (new
independent evidence completing an item this freeze explicitly left open), not a retroactive
rewrite to match AIP output.

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

**Interpretation B** — `airflow-apiserver`, `airflow-scheduler`, `airflow-worker`,
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

Answering this correctly requires keeping four separate questions apart, rather than letting an
answer to the last one quietly stand in for the first (a mistake this dossier's own first draft
made by writing the runtime-telemetry limitation as *the reason* no split is asserted, which reads
as if the roles weren't architecturally distinct — they are; see the finding recorded below):

```text
1. Independent architecture conclusion
   What boundaries exist upstream, on the evidence alone?
   -> Interpretation B's evidence (above) stands undisputed: scheduler, dag-processor, worker,
      triggerer, and api-server are independently deployable, independently scaled/lifecycled,
      security-boundary-separated roles. This is a fact about Airflow, not about AIP.

2. Canonical-model interpretation
   Which of those boundaries fit AIP's current `Service` semantics?
   -> AIP's `Service` is (per app/canonical/ids.py and the OpenAPI/AsyncAPI adapters) an entity
      that owns a network-addressable contract a source adapter can attach PROVIDES/SENDS/
      RECEIVES_FROM facts to. Only `airflow-apiserver` unambiguously fits that shape today — it
      owns the one independently documented contract (/api/v2). The other four roles are real
      architecture roles that AIP's current Service abstraction has no independent contract-based
      way to address (no OpenAPI/AsyncAPI/manifest source names them the way it names
      airflow-apiserver). That is a gap in what AIP's model can currently express, not evidence
      that the roles aren't distinct.

3. Runtime resolvability
   Which canonical identities can the unmodified OTel profile distinguish?
   -> None of the five, beyond what's already settled by (2): the pinned profile's default OTel
      configuration gives every role in the shared x-airflow-common environment block the same
      (or all-unknown_service) resource identity (evidence above). This bears only on whether a
      *runtime-observed* fact citing one of the four unresolved roles could be safely attributed —
      it says nothing about whether those roles exist.

4. AIP result
   Can AIP resolve them without guessing, given (2) and (3)?
   -> For airflow-apiserver: yes — it is asserted as a canonical Service below. For the other
      four: no safe canonical identity exists without either a contract-based source AIP doesn't
      have for them, or runtime telemetry the default profile doesn't emit. Per I3 spec §13,
      "unresolved > guessed" applies, and they are recorded as UNRESOLVED_IDENTITY.
```

This dossier freezes:

```text
service:airflow-apiserver
    the one logical Service this dossier asserts with full confidence — it independently owns
    a public, versioned REST contract (/api/v2) that no other component provides, and is the
    sole Compose service running `command: api-server`.

airflow-scheduler / airflow-dag-processor / airflow-worker / airflow-triggerer
    NOT asserted as distinct canonical Services in this qualifying profile — not because they
    lack independent architectural identity (layer 1 above says they don't lack it), but because
    neither AIP's current contract-based Service semantics (layer 2) nor the pinned profile's
    default runtime telemetry (layer 3) gives a safe, non-guessed way to name them individually
    (layer 4). Their runtime-role identity is recorded as UNRESOLVED_IDENTITY below, not folded
    into `service:airflow-apiserver` and not split into four guessed Service ids.
```

**Flag for I4 (per I3 spec §54/§75):** layer 2 above is itself a candidate model-hardening
question, not just a runtime-evidence gap — AIP's current `Service` abstraction has no way to
represent "an architecturally distinct, independently deployed role with no independently owned
network contract of its own." Whether that deserves a canonical model change (e.g. a role/process
concept distinct from `Service`) is exactly the kind of cross-system question I4 exists to decide
once Quarkus's and Airflow's findings can be compared; I3.1 deliberately does not propose one
(I3 spec §54 lists new role/process entities among the changes normally deferred to I4).

A separate, pre-declared diagnostic profile that sets explicit per-role `OTEL_SERVICE_NAME` values
(standard OTel configuration, decided now from this architectural reasoning rather than reactively
after observing AIP's behavior) may test whether runtime resolvability (layer 3) can be improved
without changing layers 1-2. Per I3 spec §14, any such experiment SHALL be documented separately
and SHALL NOT retroactively redefine this frozen ground truth.

### Runtime role vs. runtime instance vs. deployment artifact (I3 spec §12)

```text
logical identity     service:airflow-apiserver (frozen); the other four roles: unresolved
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

Sole provider: `airflow-apiserver` — the only Compose service running `command: api-server`, and
the only component the pinned OpenAPI document itself attributes these routes to.

Canonical identities (per `app/canonical/ids.py`'s `service_id()`/`operation_id()` format):

```text
service:airflow-apiserver

operation:service:airflow-apiserver:GET:/api/v2/monitor/health
operation:service:airflow-apiserver:GET:/api/v2/dags
operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}
operation:service:airflow-apiserver:POST:/api/v2/dags/{dag_id}/dagRuns
operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns
operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}
operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances
operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}
operation:service:airflow-apiserver:GET:/api/v2/variables
```

## REST caller ground truth (I3 spec §18)

None established in I3.1 — no traffic has run yet. The external validation traffic script that
I3.2 will add is not itself an AIP Service and will not be represented as a synthetic architecture
caller merely because it invokes the public REST API (I3 spec §18, first paragraph). Internal
Airflow HTTP interactions (e.g. worker/task -> execution API) are addressed separately below.

## Execution API boundary (I3 spec §19)

The pinned official profile points workers/tasks at `http://airflow-apiserver:8080/execution/`.

**Correction from an earlier draft of this section.** An earlier version of this dossier justified
`UNRESOLVED_IDENTITY` solely by the absence of a committed OpenAPI document for this surface. That
was too strong: I1's evidence hierarchy explicitly permits pinned upstream *source code* (tier 4),
and the pinned commit contains a complete, independently readable FastAPI application for this
surface at `airflow-core/src/airflow/api_fastapi/execution_api/`:

```text
app.py               create_task_execution_api_app() — title "Airflow Task Execution API",
                     description "The private Airflow Task Execution API." Cadwyn-versioned via
                     an `Airflow-API-Version` header (version affects request/response schema, not
                     the route path).
routes/__init__.py    execution_api_router composes, with concrete path prefixes:
                         /health, /health/ping                (unauthenticated)
                         /assets, /asset-events, /connection-tests, /connections, /dag-runs,
                         /dags, /task-instances, /task-reschedules, /variables, /xcoms,
                         /hitlDetails, /store/ti, /store/asset   (all behind require_auth)
routes/task_instances.py  concrete route declarations exist, e.g.
                         PATCH /task-instances/{task_instance_id}/run
                         (ti_id_router, mounted with no extra prefix under the /task-instances
                         router — full path /execution/task-instances/{task_instance_id}/run)
```

So route *target* identity is independently derivable from pinned source, the same tier-4 evidence
this dossier already relies on for the OTel resource-identity finding above — the earlier "no
evidence exists" framing was wrong. This dossier still does not add these routes to the qualifying
bounded REST set or to `expected.yaml`, for two narrower, evidence-based reasons rather than the
withdrawn one:

```text
1. Caller identity: the interaction is worker/task-runner -> airflow-apiserver. "Worker" is
   exactly the runtime role left UNRESOLVED_IDENTITY above (Logical Service boundary analysis,
   layer 4) — a concrete CALLS fact needs both ends resolved, and one end isn't, independent of
   whether the target route is known.
2. Scope discipline: I3.1's bounded REST provider set (I3 spec §16's ~8-15 target) was selected
   from the one contract this profile treats as the qualifying public surface (/api/v2). Extending
   comparator scope to the execution API pulls in a second, differently-versioned contract surface
   this profile did not select against — appropriate to decide deliberately in I3.2 (where the
   validation Dag's actual worker/task-runner call pattern can be confirmed against these routes),
   not to fold in silently here.
```

Net classification is unchanged — `UNRESOLVED_IDENTITY: execution API boundary` — but for the
caller-identity and scope-discipline reasons above, not for absence of evidence. I3.2/I3.3 SHOULD
revisit this once the worker's runtime-role identity question and the validation Dag's concrete
call pattern are both available.

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
airflow-scheduler      -> PostgreSQL   (metadata database)
airflow-apiserver      -> PostgreSQL   (metadata database)
Celery result backend  -> PostgreSQL   (result backend)
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
component). This dossier chooses `airflow-apiserver`, matching the pinned Compose file's own
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
AIP SHALL NOT collapse the worker role into service:airflow-apiserver merely because native
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
UNRESOLVED_IDENTITY   execution API boundary (§19 above) — route targets ARE independently
                      derivable from pinned source, but the caller ("worker") is itself an
                      unresolved runtime role, and I3.1 deliberately did not extend comparator
                      scope to this second contract surface (see §19's corrected rationale).
UNRESOLVED_IDENTITY   airflow-scheduler / airflow-dag-processor / airflow-worker /
                      airflow-triggerer logical Service identity under the pinned profile's
                      default (undifferentiated) native telemetry configuration — an
                      architecture-vs-model-vs-runtime distinction, not an architecture-absence
                      finding (see Logical Service boundary analysis's four-layer decision above).
INSUFFICIENT_EVIDENCE Celery SENDS/RECEIVES_FROM runtime status — no traffic has been run and no
                      OTLP has been captured yet (I3.1 authors PROVISIONAL, pre-runtime ground
                      truth for this item — see "Provisional scope" note below; the final freeze
                      for this item happens in I3.2 per I3 spec §48-49's phase order).
```

No `CALLS` ground truth is asserted or attempted in I3.1 for the reason above (§18): it requires
independent caller-side evidence this dossier does not yet have, and none is manufactured.

## Change log (I1 §37: ground truth may change only for a documented, non-AIP-output reason)

**I3.2 — Phase B closes the freeze gate for the Celery messaging item (2026-09-01).** Per the
"Provisional scope of this freeze" section above, I3.2 started the profile, captured raw OTel
independently (never through AIP), and closed the §49 freeze gate for the one item I3.1 left open.
Reason recorded here, not derived from any AIP output (no AIP comparison has run):

- Native Airflow tracing (`[traces] otel_on = True`) exposes task/dagrun/execution-API spans only —
  zero Celery/broker/queue attributes, confirmed directly from the Collector's raw `debug` exporter
  output across multiple runs.
- Per I3 spec §29, standard, pinned `opentelemetry-instrumentation-celery==0.65b0` was added as a
  diagnostic-only experiment (not kept in the frozen profile). It surfaced a real `Producer`-kind
  span (`messaging.destination_kind: queue`, `messaging.destination: default`) confirming the
  destination is a queue with the pinned `default` name — but no consumer-side span, and, decisively,
  **every span's resource `service.name` was `unknown_service` regardless of which Airflow component
  produced it.**
- This directly and independently confirms (now from captured runtime evidence, not just source
  reading) the `airflow-runtime-role-identity` `unresolved_identity` item below: sender/consumer
  logical identity is not resolvable from this profile's OTel configuration. I3 spec §23's
  qualification rule requires resolved identity as a precondition for any qualified `SENDS`/
  `RECEIVES_FROM` fact, independent of how good the messaging-attribute evidence is.

**Outcome:** no qualified `SENDS`/`RECEIVES_FROM` relation is added to `expected.yaml`. The
`airflow-celery-messaging-runtime-status` item is reclassified from `insufficient_evidence` (open,
pending Phase B) to a final, closed `insufficient_evidence` result — this is itself a legitimate I3
spec §23 outcome, not an open question. `queue:default`'s scope entry remains in `expected.yaml`
unchanged (still correctly excludes any unqualified `SENDS`/`RECEIVES_FROM` fact from silently
passing). Full experiment detail: `profile.md`'s "Standard Celery instrumentation decision" section.
Full run procedure: `runtime/README.md`, `runbook.md`.
