# AIP v0.3.0 I3 Specification — Apache Airflow Validation

**Status:** Draft 1 — implementation-ready specification  
**Target release:** `v0.3.0-alpha.3`  
**Parent release:** `v0.3.0 — Real-World Validation & Model Hardening`  
**Iteration:** I3 — Apache Airflow Validation  
**Predecessor:** `I2 — Quarkus Super Heroes Validation`

---

## 1. Purpose

I3 applies the real-world validation contract established in I1 to the second and deliberately harder
external system:

```text
Apache Airflow
    role: Real-World OSS Software
```

I3 is the model-stress iteration of v0.3.

Quarkus Super Heroes challenged AIP with an externally authored architecture that is still relatively
close to AIP's existing microservice assumptions.

Apache Airflow challenges those assumptions directly.

The iteration SHALL answer:

> **Does AIP preserve materially correct architecture semantics when a mature distributed system
> contains API servers, schedulers, workers, a broker, multiple runtime processes, and asynchronous
> task execution that do not map trivially to "one process = one Service"?**

I3 is not an Airflow integration feature.

It is a semantic validation exercise.

---

## 2. I3 Release Identity

The v0.3 progression is:

```text
I1
validation methodology is frozen

I2
the model is challenged by an
external reference architecture

I3
the model is challenged by
mature real-world OSS

I4
cross-system evidence drives
general model hardening
```

The I3 release identity is:

```text
v0.3.0-alpha.3

Apache Airflow validation is
independently grounded,
reproducible,
identity-aware,
and fully classified
```

I3 SHALL NOT claim that final cross-system hardening is complete.

That decision belongs to I4.

---

## 3. Entry Criteria

I3 SHALL begin only after I2 has produced a reviewable completed Quarkus dossier and the I1
validation contract remains frozen.

Required baseline:

```text
I1 validation vocabulary frozen
I1 severity model frozen
I1 expected.yaml contract frozen
I1 comparator semantics frozen
I1 dossier/runbook contract frozen

Quarkus qualifying comparison complete
Quarkus material findings classified
Quarkus critical supported-semantic errors = 0
Quarkus repeatability gate complete

v0.2 deterministic evaluation = 10/10 PASS
```

The exact AIP baseline SHA from which I3 starts SHALL be recorded in the Airflow dossier before the
first qualifying comparison.

If the I1 contract changes during I3, the change SHALL be explicit, independently justified, and
reviewed before it is used for Airflow qualification.

I3 SHALL NOT redefine the validation method merely because Airflow exposes inconvenient architecture.

---

## 4. Upstream System Pin

The qualifying I3 upstream baseline SHALL be:

```text
Repository:
    apache/airflow

Release:
    Apache Airflow 3.3.1

Pinned commit:
    3adbbe1c58e4532df1964cb7794805e763816ee8

Annotated tag:
    3.3.1

Tag object:
    8d7af742565409cf8857c92c1cec98568dae4296

Release date:
    2026-08-12

Pin date:
    2026-08-31

License:
    Apache-2.0
```

The exact commit is normative for I3.

The validation SHALL NOT run against:

```text
main
latest
apache/airflow:latest
an unpinned provider set
an unrecorded nightly image
```

Changing the Airflow pin requires:

```text
documented reason
new exact SHA
new release/tag identity
ground-truth review against the new SHA
profile re-freeze
```

A different upstream revision SHALL not silently replace the pinned baseline.

---

## 5. Why Airflow 3.3.1

Airflow 3.3.1 is selected because it is the current stable Airflow release at the I3 specification
freeze and exposes the architecture properties v0.3 intends to test:

```text
stable public REST API v2
separate API server
scheduler
Dag processor
Celery worker model
CeleryExecutor
Redis broker option
PostgreSQL metadata/result backend
native OpenTelemetry tracing support
task execution API architecture
```

The profile SHALL use Airflow 3.x semantics.

I3 SHALL NOT fall back to Airflow 2.x merely because its component boundaries are simpler.

---

## 6. Verified Upstream Reference Facts at the Pin

The pinned Airflow repository contains an official Docker Compose development profile explicitly
described as:

```text
Basic Airflow cluster configuration
for CeleryExecutor with Redis and PostgreSQL
```

At the pin, that profile configures:

```text
AIRFLOW__CORE__EXECUTOR
    CeleryExecutor

AIRFLOW__CELERY__BROKER_URL
    redis://:@redis:6379/0

AIRFLOW__CELERY__RESULT_BACKEND
    db+postgresql+psycopg2://airflow:airflow@postgres/airflow

AIRFLOW__DATABASE__SQL_ALCHEMY_CONN
    postgresql+psycopg2://airflow:airflow@postgres/airflow

AIRFLOW__CORE__EXECUTION_API_SERVER_URL
    http://airflow-apiserver:8080/execution/
```

The same upstream profile starts at least:

```text
airflow-apiserver
airflow-scheduler
airflow-dag-processor
airflow-worker
airflow-triggerer
redis
postgres
```

These are upstream deployment facts.

They SHALL NOT automatically become AIP `Service` entities.

---

## 7. Pinned Upstream Evidence References

The I3 dossier SHALL cite immutable upstream references.

Primary repository references include:

```text
Airflow 3.3.1 tag / pinned commit
    apache/airflow @ 3adbbe1c58e4532df1964cb7794805e763816ee8

Official Docker Compose profile
    airflow-core/docs/howto/docker-compose/docker-compose.yaml
    @ 3adbbe1c58e4532df1964cb7794805e763816ee8

Public REST OpenAPI
    airflow-core/src/airflow/api_fastapi/core_api/openapi/
    v2-rest-api-generated.yaml
    @ 3adbbe1c58e4532df1964cb7794805e763816ee8
```

The implementation dossier SHALL also record version-pinned official documentation references for:

```text
Architecture Overview
Airflow 3 architecture changes
Public REST API
CeleryExecutor
OpenTelemetry traces
```

Every repository source cited as ground truth SHALL use an immutable permalink.

Moving `stable` documentation MAY be used during research, but the dossier SHALL record the
corresponding Airflow version.

---

## 8. Validation Profile

I3 SHALL define one bounded qualifying local profile.

The qualifying profile SHALL use:

```text
Airflow:
    3.3.1

Executor:
    CeleryExecutor

Broker:
    Redis

Metadata database:
    PostgreSQL

Celery result backend:
    PostgreSQL

API:
    public REST API v2

Runtime:
    API server
    scheduler
    Dag processor
    at least one Celery worker
    triggerer when required by official profile

Observability:
    OpenTelemetry / OTLP
```

The preferred deployment basis is the pinned official Airflow Docker Compose profile.

The I3 profile MAY use a small external Compose override for:

```text
exact image pin
OTLP endpoint
Collector fan-out
bounded resource settings
deterministic validation Dag mount
readiness helpers
```

The override SHALL not redesign the Airflow architecture.

---

## 9. Worker Cardinality

The preferred qualifying profile SHALL run:

```text
two Celery worker instances
```

when the official Compose profile can be scaled reproducibly without semantic changes.

Reason:

```text
one logical worker role
        |
        +--> worker instance A
        |
        +--> worker instance B
```

is a direct test of the distinction:

```text
runtime instance identity
    !=
logical architecture identity
```

If two workers prove operationally impractical, one worker MAY be used for the qualifying run, but:

```text
reason SHALL be documented
multiple-instance identity question SHALL remain explicit
```

A second diagnostic profile MAY then be used to examine multiple worker instances.

---

## 10. Mandatory Supported-Scope Targets

I3 SHALL validate current AIP semantics where independent evidence supports them.

Mandatory targets are:

```text
Service identity
Operation identity
PROVIDES
CALLS where independently established
SENDS where queue semantics and runtime evidence qualify
RECEIVES_FROM where queue semantics and runtime evidence qualify
declared evidence
observed evidence
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
runtime environment/window qualification
evidence preservation
```

Not every target must produce a positive expected fact.

A valid result may instead show:

```text
UNSUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
```

where the evidence does not support a safe AIP claim.

---

## 11. The Central Identity Question

The primary I3 model question is:

```text
What does Airflow mean as an AIP Service?
```

Airflow exposes distinct runtime/deployment roles:

```text
API server
scheduler
Dag processor
worker
triggerer
```

but the existence of different processes or containers does not by itself prove that AIP should model
each role as a separate canonical `Service`.

Before the qualifying AIP run, the ground-truth dossier SHALL explicitly evaluate at least these two
candidate interpretations:

```text
Interpretation A

Airflow
    one logical Service

process roles
    runtime/deployment structure outside
    the current canonical Service abstraction
```

and:

```text
Interpretation B

airflow-api-server
airflow-scheduler
airflow-worker
...

    distinct logical Services
    because their architecture boundaries
    are independently meaningful
```

The dossier SHALL choose or bound the interpretation using upstream evidence.

The choice SHALL NOT be based on which interpretation makes AIP pass.

---

## 12. Service-Boundary Decision Criteria

The pre-run Airflow identity analysis SHALL consider:

```text
independent deployability
network addressability
public or internal contract ownership
responsibility boundary
runtime lifecycle
scaling independence
upstream architecture terminology
upstream telemetry identity
whether multiple instances represent one role
```

The following alone are insufficient to define a new logical `Service`:

```text
container name
PID
hostname
Celery worker node name
service.instance.id
temporary runtime process suffix
```

The final ground-truth decision SHALL distinguish:

```text
logical identity
runtime role
runtime instance
deployment artifact
```

even when AIP cannot model all four separately.

---

## 13. Identity Must Be Frozen Before Comparison

The chosen service-boundary interpretation SHALL be recorded in:

```text
ground-truth.md
```

before the first qualifying AIP comparison.

The dossier SHALL contain:

```text
upstream term
candidate logical identity
supporting evidence
counter-evidence
normalization rule
ambiguity, if any
```

If independent evidence cannot justify one safe mapping:

```text
UNRESOLVED_IDENTITY
```

is the correct result.

I3 SHALL prefer:

```text
unresolved
    >
guessed
```

---

## 14. No Observability-Driven Identity Rewriting

Standard OTel configuration is allowed.

However, the qualifying profile SHALL NOT set artificial per-component `service.name` values solely
to make AIP resolve Airflow into a desired topology.

Prohibited sequence:

```text
AIP collapses identities
        |
        v
set OTEL_SERVICE_NAME values
until AIP output matches
```

The first qualifying identity observation SHALL preserve upstream/default identity behavior as far as
practical.

If additional per-role OTel resource naming is explored, it SHALL be a separately documented
diagnostic experiment and SHALL not retroactively redefine the frozen ground truth.

---

## 15. Public REST API Scope

Airflow 3.3.1 exposes its stable public API under:

```text
/api/v2
```

The pinned generated OpenAPI source is:

```text
airflow-core/src/airflow/api_fastapi/core_api/openapi/
v2-rest-api-generated.yaml
```

The OpenAPI description explicitly distinguishes stable `/api/v2` endpoints from UI-specific
endpoints.

I3 SHALL use the public `/api/v2` contract as the declared REST source.

UI-only routes SHALL be outside qualifying declared REST scope.

---

## 16. Bounded REST Operation Set

The full Airflow public API is large.

I3 SHALL NOT require every public operation to be part of the qualifying comparator scope.

Instead, I3.1 SHALL freeze a bounded operation set of approximately:

```text
8-15 public REST operations
```

selected from independently documented stable API areas such as:

```text
monitor/health
Dags
Dag Runs
Task Instances
Pools or Variables when useful
```

Selection criteria:

```text
stable /api/v2 route
present in pinned OpenAPI
useful to qualifying traffic
representative path-template behavior
bounded enough for review
```

The complete official OpenAPI file MAY be imported into AIP.

Comparator scope SHALL be bounded to the selected operation identities rather than treating every
operation in the full API as a mandatory expected fact.

No filtered or reconstructed OpenAPI file SHALL replace the official contract as ground truth.

---

## 17. REST Provider Ground Truth

For every qualifying REST operation, I3 SHALL establish independently:

```text
logical provider identity
HTTP method
route/template
upstream operationId
AIP canonical normalization
```

The selected expected `PROVIDES` set SHALL be frozen before AIP comparison.

Ground truth SHALL not depend on AIP-generated operation IDs.

Canonical IDs MAY be normalized into AIP format for comparison, but the source operation identity
SHALL be recorded independently.

---

## 18. REST Caller Ground Truth

The profile SHALL distinguish:

```text
public API client -> API server
```

from:

```text
internal Airflow component -> internal execution API
```

The external validation traffic script is not itself an AIP Service and SHALL not create a synthetic
architecture caller merely because it invokes Airflow's public REST API.

Internal Airflow HTTP interactions MAY qualify as AIP `CALLS` only when:

```text
caller logical identity is independently established
target operation identity is independently established
the interaction is inside AIP's supported HTTP semantics
runtime evidence is sufficient
```

The existence of an HTTP span alone SHALL not authorize comparator-side guessing.

---

## 19. Execution API Boundary

Airflow 3.x uses an execution API for task/worker interaction.

The official Compose profile points workers/tasks toward:

```text
http://airflow-apiserver:8080/execution/
```

This is architecturally relevant but is not automatically equivalent to the stable public `/api/v2`
contract.

I3 SHALL investigate:

```text
whether execution API operations are separately contract-described
whether AIP can resolve them safely
whether they belong in current supported scope
```

If the operation identity cannot be independently established:

```text
UNRESOLVED_IDENTITY
```

or:

```text
INSUFFICIENT_EVIDENCE
```

SHALL be used.

I3 SHALL NOT synthesize an HTTP Operation merely from a concrete URL.

---

## 20. CeleryExecutor Ground Truth

The qualifying profile SHALL use:

```text
CeleryExecutor
```

with:

```text
Redis broker
```

and PostgreSQL as configured result backend.

Independent ground truth SHALL establish at least:

```text
scheduler/executor side submits work
Redis is the Celery broker
worker consumes queued work
default task queue semantics
worker acknowledgement/redelivery semantics where relevant
```

The dossier SHALL record the actual queue configured for the qualifying Dag.

The preferred explicit queue is:

```text
default
```

unless the pinned profile deliberately chooses a different named queue before the AIP run.

---

## 21. Queue Versus Broker

The Airflow profile SHALL preserve the distinction:

```text
Redis
    broker technology / server

default
    logical Celery task queue
```

AIP's `Queue` entity represents the architecture messaging destination.

Therefore the ground truth SHALL NOT pre-author:

```text
Queue(redis)
```

merely because Redis is the broker.

The candidate queue identity is the Celery queue name, for example:

```text
queue:default
```

subject to confirmation from pinned configuration and observed runtime evidence.

---

## 22. Why Redis/Celery Is a Strong I3 Boundary Test

Quarkus exposed a Kafka topic, which was deliberately not assumed to be compatible with AIP's
queue-centric semantics.

Airflow's CeleryExecutor with a Redis broker provides a complementary case.

A Celery task queue with competing workers is much closer to:

```text
Queue
```

semantics.

Therefore I3 SHALL answer:

> **Can AIP represent a real competing-consumer task queue when the external system actually has
> queue semantics, while still refusing to invent facts when the runtime telemetry is insufficient?**

This creates a useful cross-system contrast for I4:

```text
Quarkus Kafka topic
    topic/fan-out boundary

Airflow Celery queue
    competing-consumer queue candidate
```

---

## 23. Messaging Qualification Rule

A Celery/Redis interaction SHALL become an expected AIP:

```text
SENDS
RECEIVES_FROM
```

fact only when all of the following are independently established before comparison:

```text
logical sender/consumer identity is sufficiently established
destination is a queue, not merely a broker endpoint
queue name is known
direction is known
runtime telemetry exposes architecture-relevant messaging evidence
that falls inside AIP's claimed supported semantics
```

Configuration/source evidence may establish the architecture fact.

However, a runtime-qualified expected status requires matching runtime evidence.

If the Celery flow is known architecturally but qualifying OTel does not expose sufficient messaging
attributes, I3 SHALL NOT manufacture observed evidence.

Possible outcomes include:

```text
CORRECT
MISSING_SUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
UNSUPPORTED
```

depending on what is independently established.

---

## 24. No Synthetic AsyncAPI for Airflow

Airflow does not need to provide AsyncAPI for I3.

I3 SHALL NOT author an AIP-specific AsyncAPI file solely to turn the Celery topology into declared
`SENDS` / `RECEIVES_FROM` facts.

That would violate:

```text
AIP Input != Ground Truth
```

and would change the validation question from:

```text
Can AIP understand the real system?
```

to:

```text
Can AIP understand a declaration created for AIP?
```

The Airflow messaging test is primarily a real runtime/evidence test.

---

## 25. PostgreSQL Boundary

The official profile uses PostgreSQL for:

```text
Airflow metadata database
Celery result backend
```

Current AIP does not model generic database dependencies as first-class canonical relations.

Therefore:

```text
scheduler -> PostgreSQL
API server -> PostgreSQL
Celery result backend -> PostgreSQL
```

are mandatory architecture observations but SHALL initially be treated as:

```text
UNSUPPORTED
```

with respect to the current canonical relation vocabulary.

AIP SHALL NOT represent PostgreSQL as:

```text
Queue
HTTP Operation
another supported relation
```

merely to increase coverage.

---

## 26. Dag Processor and Triggerer Boundary

The official profile starts:

```text
airflow-dag-processor
airflow-triggerer
```

These are valid Airflow runtime components.

Their presence SHALL be recorded in the complete upstream architecture inventory.

They SHALL not automatically become expected AIP Services or expected relations.

The identity analysis SHALL determine whether they are:

```text
logical Services
runtime roles outside current model
unsupported deployment/process structure
```

AIP output that creates architecture claims from these process identities SHALL be reviewed against
the frozen decision.

---

## 27. OpenTelemetry Validation Scope

Airflow 3.3.1 supports OpenTelemetry tracing.

The qualifying profile SHALL route architecture-relevant OTLP to AIP through the existing AIP OTLP
ingestion path.

Preferred topology:

```text
Airflow processes / task runners
        |
        v
OpenTelemetry / OTLP
        |
        v
OpenTelemetry Collector
        |
        +--> diagnostic/raw evidence path
        |
        +--> AIP /v1/traces
```

A Collector is strongly preferred because it permits independent raw telemetry inspection without
using AIP output as ground truth.

---

## 28. Native Airflow Tracing First

The first qualifying telemetry profile SHALL use Airflow's supported tracing configuration before
adding extra instrumentation.

The profile SHALL enable tracing using supported Airflow/OpenTelemetry configuration.

Configuration SHALL be recorded explicitly.

The dossier SHALL capture the actual OTel resource identity and relevant span attributes emitted by:

```text
API server
scheduler
worker/task runner
other started Airflow components where present
```

This raw capture is evidence about the external system's observability behavior.

It is not AIP output.

---

## 29. Standard Celery Instrumentation

If native Airflow tracing does not expose enough messaging attributes to evaluate the Celery queue
path, I3 MAY add standard OpenTelemetry Celery instrumentation.

This is permitted only when:

```text
instrumentation package/version is pinned
configuration is applied before ground-truth freeze
no Airflow architecture logic is changed
raw spans are inspected independently of AIP
the instrumentation exposes an existing interaction rather than creating a new one
```

The decision to add instrumentation SHALL be documented in `profile.md`.

The reason SHALL be:

```text
make existing runtime interaction observable
```

not:

```text
make AIP pass
```

If sufficient safe messaging telemetry still cannot be obtained, the result SHALL remain explicitly
insufficient or unsupported.

---

## 30. Telemetry Attribute Safety

I3 SHALL preserve AIP's existing privacy and low-cardinality rules.

The profile SHALL not require ingestion of:

```text
task payloads
DAG source code
credentials
JWT tokens
Authorization headers
SQL statements
full HTTP bodies
arbitrary user data
```

Architecture-relevant runtime evidence SHOULD be limited to fields such as:

```text
service.name
service.instance.id
HTTP method
HTTP route
server address/port when needed for resolution
messaging system
messaging destination
messaging operation/type
trace/span correlation identifiers
environment
timestamps
```

Any diagnostic raw capture SHALL be reviewed before commit.

Secrets SHALL not be committed.

---

## 31. Environment and Observation Window

The I3 runtime environment SHALL use a dedicated deterministic name.

Recommended:

```text
airflow-i3
```

All runtime-qualified comparison SHALL record:

```text
environment
window_start
window_end
AIP candidate SHA
Airflow upstream SHA
profile revision
```

The window SHALL contain the qualifying validation traffic.

Startup noise SHOULD be excluded where practical.

Telemetry generated by the qualifying task execution but exported shortly after client traffic ends
MUST still be included.

Therefore:

```text
traffic completion
    !=
observation window end
```

The runbook SHALL include a bounded telemetry drain barrier before capture.

---

## 32. Deterministic Validation Dag

I3 SHALL add one small deterministic Dag as validation workload.

The Dag is test workload/configuration, not an Airflow architecture modification.

It SHALL:

```text
contain no external network dependency
contain no LLM call
contain no random output required for validation
run on the qualifying Celery queue
contain at least two ordered tasks
finish quickly
be safe to run repeatedly
```

Recommended logical shape:

```text
i3_validation
    |
    v
task_a
    |
    v
task_b
```

The tasks MAY emit simple deterministic logs.

They SHALL not emit AIP-specific architecture declarations.

---

## 33. Traffic Script

I3 SHALL define a deterministic traffic/exercise script.

It SHALL perform at minimum:

```text
1. confirm API readiness
2. obtain API authentication using the configured official auth path
3. call one or more selected public /api/v2 read operations
4. trigger the deterministic validation Dag
5. poll the Dag Run through the stable REST API
6. verify task execution completes successfully
7. wait for the OTLP drain condition
```

The traffic script SHALL use fixed identifiers where the API permits them.

It SHALL avoid relying on UI automation.

The UI MAY be used diagnostically, but the qualifying traffic path SHOULD use the stable API.

---

## 34. Qualifying Architecture Flows

The profile SHALL exercise at least these conceptual flows:

```text
External client
    -> Airflow public API

Airflow scheduler / executor
    -> Celery task queue

Celery task queue
    -> worker

worker / task runner
    -> Airflow execution API
        where this occurs in the pinned architecture

Airflow components
    -> PostgreSQL
        recorded as unsupported database dependency
```

Not every flow is required to become an AIP supported relation.

Each flow SHALL be independently classified.

---

## 35. Ground-Truth Source Hierarchy

I3 SHALL follow the frozen I1 hierarchy:

```text
1. official machine-readable contract
2. official architecture documentation
3. official deployment/runtime configuration
4. upstream source
5. independently captured raw runtime evidence
```

For Airflow specifically:

```text
REST provider facts
    pinned OpenAPI first

Celery topology
    pinned Compose/config/provider docs/source

process-role architecture
    official architecture docs + pinned Compose

runtime identity
    independent raw OTel capture

specific runtime direction
    raw OTel + upstream behavior
```

AIP output SHALL not be part of this hierarchy.

---

## 36. Airflow Dossier Structure

I3 SHALL populate:

```text
docs/real-world-validation/apache-airflow/
├── upstream.md
├── profile.md
├── ground-truth.md
├── expected.yaml
├── runbook.md
├── results.md
├── findings.md
├── evidence/
├── decisions/
└── runtime/
```

Suggested `runtime/` contents include:

```text
docker-compose.override.yml
otel-collector-config.yaml
dags/i3_validation.py
traffic.sh
README.md
```

Only compact, legally reusable validation material SHALL be committed.

The full Airflow repository SHALL not be vendored.

---

## 37. `upstream.md`

`upstream.md` SHALL record:

```text
project
role: Real-World OSS Software
repository
license
release
tag
full commit SHA
pin date
official image
relevant provider dependencies
relevant upstream architecture references
relevant OpenAPI source
relevant Compose source
```

It SHALL clearly distinguish:

```text
Airflow release identity
```

from:

```text
AIP candidate identity
```

---

## 38. `profile.md`

`profile.md` SHALL define:

```text
Airflow image/version
executor
broker
result backend
metadata database
components started
worker count
validation Dag
public API endpoints exercised
OpenAPI acquisition method
OTel configuration
Collector path
environment name
observation-window method
drain barrier
cleanup/reset procedure
resource assumptions
ports
```

It SHALL explicitly record:

```text
PostgreSQL dependency -> unsupported by current AIP relation model

runtime process/container identity
    != automatically logical Service identity
```

---

## 39. `ground-truth.md`

`ground-truth.md` SHALL be authored before the first qualifying AIP comparison.

It SHALL contain:

```text
complete relevant component inventory
logical Service boundary analysis
runtime role vs instance distinction
selected REST provider inventory
Celery broker and queue ground truth
scheduler/worker direction ground truth
execution API boundary
PostgreSQL unsupported dependencies
identity normalization rationale
raw OTel resource observations available before comparison
known ambiguities
insufficient-evidence items
```

It SHALL clearly separate:

```text
upstream architecture fact
```

from:

```text
expected AIP supported fact
```

and from:

```text
unsupported / unresolved architecture fact
```

---

## 40. `expected.yaml`

The qualifying `expected.yaml` SHALL contain only supported AIP relation facts.

It SHALL preserve the I1 schema.

Conceptual example only:

```yaml
system: apache-airflow
upstream_revision: "3adbbe1c58e4532df1964cb7794805e763816ee8"

scope:
  entities:
    - operation:service:airflow-api-server:GET:/api/v2/dags
    - operation:service:airflow-api-server:POST:/api/v2/dags/{dag_id}/dagRuns
  relation_types:
    - PROVIDES
    - CALLS
    - SENDS
    - RECEIVES_FROM

expected:
  relations:
    - id: airflow-api-provides-dags
      type: PROVIDES
      source: service:airflow-api-server
      target: operation:service:airflow-api-server:GET:/api/v2/dags
      evidence:
        declared: true
        observed: null

unsupported:
  - id: airflow-postgres-dependency
    mechanism: database-dependency
    description: >
      Airflow components depend on PostgreSQL, which is outside the current
      AIP canonical relation vocabulary.
```

The example does not freeze the final Airflow logical service ID.

I3.1 SHALL determine that from independent evidence.

---

## 41. Identity Findings Outside `expected.yaml`

The frozen I1 comparator is relation-oriented.

I3 SHALL NOT extend `expected.yaml` into a generic entity/process ontology merely because Airflow has
a difficult identity model.

Logical-service/process identity findings that cannot be represented as relation expectations SHALL
be recorded in:

```text
ground-truth.md
findings.md
decision records
raw evidence references
```

A comparator/schema extension MAY be proposed only if it is clearly general and necessary.

Prefer:

```text
focused evidence + finding
```

over:

```text
new validation language
```

for I3.

---

## 42. Identity Normalization

The dossier SHALL define expected normalization between upstream identities and AIP canonical IDs.

Candidate upstream identity evidence may include:

```text
official component names
Compose service names
OpenAPI provider ownership
Airflow OTel service.name
service.instance.id
worker node names
HTTP host/service address
```

Normalization SHALL be frozen before comparison.

I3 SHALL NOT:

```text
fuzzy-match actual names after the run
drop prefixes until a result passes
map every process to a Service by default
merge roles after seeing AIP output
split roles after seeing AIP output
repair AIP IDs in comparator code
```

---

## 43. Multiple Runtime Instances

If two workers are used, I3 SHALL independently record:

```text
worker logical role
worker instance A identity
worker instance B identity
resource attributes that distinguish them
resource attributes that intentionally remain common
```

AIP SHOULD not create two logical Services merely because two instances exist unless the frozen
canonical interpretation requires that.

Conversely, AIP SHALL not collapse architecturally distinct roles merely because they share a
generic telemetry resource name if that creates false supported claims.

Any ambiguity SHALL be classified explicitly.

---

## 44. Operation Identity

Expected REST relations SHALL target specific operations.

For each qualifying operation, the dossier SHALL establish:

```text
provider interpretation
HTTP method
route template
OpenAPI operationId
canonical normalized operation ID
```

Concrete Dag IDs, Dag Run IDs, Task Instance IDs, or UUIDs SHALL not become route-specific canonical
operations.

For example:

```text
/api/v2/dags/my_validation_dag/dagRuns
```

must resolve, if supported, to a template equivalent to:

```text
/api/v2/dags/{dag_id}/dagRuns
```

No comparator-side route reconstruction is allowed.

---

## 45. Declared Versus Observed Semantics

I3 SHALL preserve:

```text
declared evidence
    !=
observed evidence
```

The public OpenAPI contract can establish declared:

```text
PROVIDES
```

facts.

It SHALL NOT establish internal callers.

Runtime telemetry may establish observed:

```text
CALLS
SENDS
RECEIVES_FROM
```

where identity and direction are safe.

Expected status SHALL be supplied only where the frozen evidence context justifies it.

AIP output SHALL determine actual status.

The comparator SHALL not derive AIP status from booleans.

---

## 46. Runtime Non-Observation

The existing rule remains normative:

```text
NOT_OBSERVED_IN_WINDOW
    !=
architecture absence
```

Airflow makes this especially important because:

```text
not every component emits every useful span
not every task reaches every component
worker execution is asynchronous
telemetry can flush after HTTP traffic completes
```

I3 SHALL record coverage limitations explicitly.

No finding may infer:

```text
component is unused
dependency does not exist
queue is obsolete
```

solely because it was not observed in one window.

---

## 47. Raw Telemetry Evidence

I3 SHALL preserve compact evidence from at least one independent raw telemetry inspection.

The evidence SHOULD record:

```text
resource service.name values
service.instance.id where present
representative HTTP route/method attributes
representative messaging attributes
representative span kind
timestamps
component producing the span when independently known
```

The evidence SHALL be sanitized.

It SHALL NOT commit full uncontrolled trace dumps if compact excerpts are sufficient.

Raw telemetry inspection occurs before or independently of AIP comparison and MAY inform whether an
item is safe to include in frozen expected ground truth.

---

## 48. Qualifying Comparison Phases

I3 SHALL execute in logically separated phases.

### Phase A — Upstream Research and Identity Decision

```text
pin Airflow
study official architecture
study pinned Compose/config
study pinned OpenAPI
define service-boundary decision
define queue/broker semantics
define unsupported database boundary
```

### Phase B — Observability Qualification

```text
start profile without AIP comparison
enable native OTel
capture raw telemetry independently
qualify resource identities
qualify HTTP attributes
qualify Celery messaging evidence
add standard Celery instrumentation only if justified
```

### Phase C — Ground-Truth Freeze

```text
complete upstream.md
complete profile.md
complete ground-truth.md
freeze expected.yaml
commit/review freeze point
```

### Phase D — First AIP Comparison

```text
start clean profile
start clean AIP
import official OpenAPI
route OTLP to AIP
run deterministic traffic
drain telemetry
capture normalized AIP facts
compare
```

### Phase E — Findings

```text
classify every material mismatch
classify identity findings
classify messaging findings
classify coverage findings
create decision records where required
```

### Phase F — I3 Revalidation

After any accepted general fix:

```text
reset
repeat same profile
compare against same frozen ground truth
```

---

## 49. Ground-Truth Freeze Gate

Before Phase D:

```text
upstream.md        complete
profile.md         complete
ground-truth.md    complete
expected.yaml      frozen
identity decision  frozen
raw OTel evidence  captured enough to qualify runtime expectations
```

A visible repository freeze point SHALL exist.

Preferred:

```text
I3.1 ground-truth PR merged
before first AIP results PR
```

Acceptable:

```text
single PR with explicit pre-run freeze commit
followed by result commits
```

The history SHALL prove that expected facts preceded AIP comparison.

---

## 50. AIP Result Capture

I3 SHALL use the existing real-world validation capture/comparison contract where sufficient.

The normalized result SHALL include reviewable relation fields:

```text
type
source
target
status
declared evidence presence
observed evidence presence
context
```

The I3 result capture SHALL NOT:

```text
invent identities
derive ground truth
rewrite source/target after query
synthesize missing relations
```

If Airflow exposes a limitation not representable by the current capture format, document the finding
first.

Do not extend the capture format merely to make the report look complete.

---

## 51. Finding Classification

Every material Airflow item SHALL use the frozen vocabulary:

```text
CORRECT
MISSING_SUPPORTED
INCORRECT_SUPPORTED
UNSUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
```

Severity remains separate:

```text
CRITICAL
MAJOR
MINOR
INFO
```

Examples:

```text
INCORRECT_SUPPORTED / CRITICAL
    process-specific hostname becomes a false logical Service
    and creates false architecture relations

MISSING_SUPPORTED / MAJOR
    independently established supported Celery queue relation
    is absent despite sufficient supported telemetry

UNRESOLVED_IDENTITY / MAJOR
    AIP cannot safely distinguish scheduler and worker
    where the frozen service model requires distinction

UNSUPPORTED / INFO
    PostgreSQL dependency is outside current relation model

INSUFFICIENT_EVIDENCE / INFO
    native traces do not expose enough messaging semantics
    to freeze a runtime expected relation
```

---

## 52. Airflow-Specific Expected Challenges

I3 SHALL actively examine at least:

```text
logical Service vs runtime process
logical Service vs runtime instance
API server provider identity
Airflow 3 execution API boundary
scheduler/executor/worker role separation
Celery default queue identity
Redis broker vs queue distinction
multiple workers
OTel resource naming
HTTP route-template resolution
asynchronous telemetry timing
PostgreSQL unsupported dependency
native Airflow tracing coverage
Celery messaging semconv coverage
```

A validation that checks only OpenAPI `PROVIDES` is insufficient.

---

## 53. Material Finding Decisions

A material I3 finding MAY result in:

```text
FIX
DOCUMENT_UNSUPPORTED
DEFER
NO_CHANGE
```

Before production code changes, the decision SHALL be recorded.

I3 MAY implement small general corrections such as:

```text
safe identity-resolution fix
safe operation-resolution fix
runtime/evidence correctness fix
supported OTel semantic-convention compatibility fix
prevention of a false supported relation
```

when justified by independent Airflow evidence and general semantics.

---

## 54. Changes Normally Deferred to I4

The following SHOULD normally be deferred to I4:

```text
new Process entity
new RuntimeRole entity
new Deployment entity
new Database entity/relation family
major Service semantic redesign
major messaging redesign
new executor-specific abstraction
new canonical identity hierarchy
```

Reason:

```text
Airflow finding
    +
Quarkus finding
    ->
cross-system model decision
```

I4 exists specifically to decide whether a model limitation is general enough to justify canonical
change.

---

## 55. Immediate False-Claim Mitigation

A critical false supported fact SHALL not remain merely because the complete model redesign is
deferred.

If Airflow exposes behavior where AIP turns an unsupported/ambiguous runtime mechanism into a false
supported architecture claim, I3 MAY introduce a narrow general safety fix:

```text
wrong supported fact
        |
        v
unresolved / unsupported / omitted
```

without introducing the final richer model.

The governing rule remains:

```text
correct but incomplete
    >
complete-looking but wrong
```

---

## 56. No Airflow-Specific Production Logic

Production code SHALL NOT contain behavior such as:

```text
if system == "airflow"
if service == "airflow-scheduler"
if queue == "default" and broker == "redis"
if hostname starts with "airflow-worker"
```

Airflow-specific logic belongs only in:

```text
validation profile
traffic script
ground-truth dossier
evidence capture
comparison input
```

Any production fix SHALL be stated as a general semantic rule.

---

## 57. Reproducible Runbook

The I3 `runbook.md` SHALL contain exact commands for:

```text
clone apache/airflow
checkout 3adbbe1c58e4532df1964cb7794805e763816ee8
verify tag/revision
prepare profile directory
set exact image/version
prepare validation Dag
initialize Airflow
start PostgreSQL
start Redis
start Airflow services
scale workers if required
verify readiness
start/configure AIP
configure Collector fan-out
capture/import pinned public OpenAPI
obtain API auth token
start observation window
execute deterministic traffic
wait for Dag completion
wait for telemetry drain
end observation window
capture AIP results
run comparator
store result
tear down
remove volumes/state
```

The runbook SHALL identify:

```text
Docker/Compose requirements
CPU/RAM assumptions
disk assumptions
required ports
environment variables
secret handling
expected startup time bounds
timeout behavior
```

---

## 58. Clean-State Requirement

Every qualifying run SHALL begin from clean validation state.

At minimum reset:

```text
AIP Neo4j state
AIP runtime/evidence state
Airflow PostgreSQL volume
Redis broker state
Airflow logs relevant to the run
temporary OTLP capture
validation output artifact
Dag Run state
```

The run SHALL not depend on a previous Airflow database.

The run SHALL not depend on queued Celery messages from a previous execution.

---

## 59. Repeatability

The final I3 qualification SHALL execute the same frozen comparison at least twice from clean state.

Required invariants:

```text
same Airflow upstream SHA
same Airflow image
same provider/instrumentation versions
same profile revision
same validation Dag
same traffic procedure
same frozen expected.yaml
same identity decision
same AIP candidate
same finding classifications
same summary counts
same deterministic ordering
```

Runtime-generated values MAY differ when they are outside the semantic contract:

```text
container ID
PID
trace ID
span ID
worker hostname suffix
Dag Run creation timestamp
```

Those differences SHALL not alter the canonical result.

---

## 60. Expected I3 Report

The final report SHALL use the shared v0.3 summary shape.

Example:

```text
Apache Airflow
---------------------
Release:                       3.3.1
Upstream SHA:                  3adbbe1c58e4532df1964cb7794805e763816ee8
AIP candidate:                 <sha>

Expected supported facts:      N
Correct:                       N
Missing supported:             N
Incorrect supported:           0
Unsupported constructs:        N
Unresolved identities:         N
Insufficient evidence:         N

Critical semantic errors:      0
```

The report SHALL additionally summarize, without a weighted score:

```text
REST provider result
logical-service identity result
Celery queue result
runtime coverage result
database boundary result
```

---

## 61. I3 Success Criteria

I3 does not require Airflow to fit the current AIP model completely.

It requires:

```text
all material findings classified
all CRITICAL findings dispositioned
critical INCORRECT_SUPPORTED findings = 0
no process/instance identity silently converted into false architecture
no broker technology silently mislabeled as queue identity
no PostgreSQL dependency silently represented as a supported non-database relation
ground truth remains independent
qualifying comparison is reproducible
```

A successful I3 may contain:

```text
MISSING_SUPPORTED
UNSUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
```

when documented and non-critical.

---

## 62. Mandatory Airflow Gates

Before I3 is complete:

```text
Airflow 3.3.1 exact SHA pinned
official Compose profile source pinned
public OpenAPI source pinned
CeleryExecutor + Redis profile reproducible
logical Service boundary explicitly reviewed before AIP run
bounded public REST scope frozen
deterministic validation Dag executed
Celery queue flow exercised
native OTel captured
raw runtime identity inspected independently
messaging evidence qualified explicitly
PostgreSQL boundary classified
multiple worker instances tested or documented as impractical
all material findings classified
all CRITICAL findings dispositioned
critical false supported facts = 0
two clean-state qualifying comparisons completed
```

---

## 63. Regression Coverage

Every production AIP fix accepted in I3 SHALL add deterministic regression coverage.

Preferred order:

```text
unit test
integration test
small distilled regression fixture
```

Examples of acceptable distilled fixtures:

```text
two runtime instances sharing one logical service name
ambiguous process identities that must not be guessed
Celery-compatible messaging attributes
late telemetry inside a bounded drain window
HTTP concrete Dag IDs resolving to route templates
```

The complete Airflow system SHALL NOT become part of the normal unit/integration suite.

---

## 64. v0.2 Regression Gate

I3 SHALL preserve the v0.2 semantic baseline.

Required:

```bash
uv run python -m evaluation run
```

Expected:

```text
10/10 PASS
```

If a justified Airflow finding proves an existing v0.2 semantic expectation incorrect, the v0.3
migration rule applies:

```text
decision record
independent evidence
explanation of old semantic defect
deliberate expected update
regression coverage
release-note entry
```

Silent weakening is prohibited.

---

## 65. Quarkus Regression Gate

I3 SHALL not rewrite I2 ground truth to accommodate Airflow findings.

If I3 introduces a production AIP fix, Quarkus validation SHALL be rerun when that fix could affect:

```text
identity
HTTP resolution
messaging
runtime status
evidence
```

At minimum, I3 results SHALL state whether the change has potential I2 impact.

Full cross-system revalidation remains mandatory in I4.

---

## 66. Test and CI Gate

Before `v0.3.0-alpha.3`:

```text
ruff check                       PASS
ruff format --check              PASS
unit tests                       PASS
integration tests                PASS
v0.2 evaluation                  10/10 PASS
I1 validation-contract tests     PASS
real-world comparator tests      PASS
Airflow comparison               reproducible
CI                               PASS
CodeQL                           PASS
dependency audit                 PASS
```

Exact test counts are non-normative.

---

## 67. I3 Release Blockers

The following SHALL block `v0.3.0-alpha.3`:

```text
ground truth written or rewritten to match AIP output
unpinned Airflow revision
qualifying run against latest/main
unrecorded image/provider/instrumentation versions
artificial telemetry identity rewriting used to make AIP pass
full Airflow architecture reduced to a microservice-shaped fixture
public REST contract reconstructed instead of using upstream OpenAPI
runtime process or instance guessed into a logical Service
false Service identity producing false supported relations
Redis broker silently treated as Queue identity without destination qualification
PostgreSQL silently represented as Queue/HTTP relation
wrong messaging direction
wrong runtime status with material impact
fabricated or lost evidence
AIP-specific AsyncAPI created to manufacture declared Celery topology
Airflow-specific production hack
nondeterministic qualifying comparison
unresolved CRITICAL finding
v0.2 regression without approved semantic migration
```

Target:

```text
critical semantic errors = 0
I3 release blockers = 0
```

---

## 68. Non-Blocking Findings

The following may remain after I3 when explicit:

```text
PostgreSQL dependency UNSUPPORTED
process/deployment topology UNSUPPORTED
non-critical UNRESOLVED_IDENTITY
non-critical MISSING_SUPPORTED
INSUFFICIENT_EVIDENCE for Celery messaging telemetry
execution API operation identity unresolved
future Process/Deployment model proposal
future Database relation proposal
future richer runtime identity model
```

Each SHALL be visible in `findings.md`.

---

## 69. I3 Deliverables

I3 SHALL deliver at minimum:

```text
docs/specifications/0.3.0/i3-airflow-validation.md

docs/real-world-validation/apache-airflow/upstream.md
docs/real-world-validation/apache-airflow/profile.md
docs/real-world-validation/apache-airflow/ground-truth.md
docs/real-world-validation/apache-airflow/expected.yaml
docs/real-world-validation/apache-airflow/runbook.md
docs/real-world-validation/apache-airflow/results.md
docs/real-world-validation/apache-airflow/findings.md
```

and as required:

```text
evidence/*.md
decisions/*.md
runtime/docker-compose.override.yml
runtime/otel-collector-config.yaml
runtime/dags/i3_validation.py
runtime/traffic.sh
small helper scripts
regression tests for accepted fixes
```

---

## 70. Suggested Delivery Split

I3 SHOULD be delivered through focused short-lived branches and PRs.

### I3.1 — Upstream Pin, Identity Analysis, and Ground Truth

Deliver:

```text
upstream.md
profile.md
ground-truth.md
expected.yaml
pinned evidence references
logical Service boundary decision
queue/broker decision
unsupported database boundary
ground-truth freeze
```

No qualifying AIP comparison result in this task. This task performs Phase A (§48) only: the
"ground-truth freeze" it delivers is final for every fact establishable without runtime evidence
(declared REST facts, unsupported/unresolved boundary classifications), but per §48-49's phase
order — Phase B (observability qualification) precedes Phase C (ground-truth freeze) — any item
whose safe qualification genuinely requires independent raw telemetry (the Celery messaging
boundary, per §22-23) remains provisional until I3.2 completes Phase B and the §49 freeze gate for
that item specifically, before I3.3's Phase D comparison runs.

Suggested branch:

```text
docs/v0.3-i3-airflow-ground-truth
```

---

### I3.2 — Reproducible Airflow Runtime Profile

Deliver:

```text
Compose override
exact image pin
validation Dag
traffic script
OTel Collector routing
native trace configuration
raw telemetry evidence procedure
clean-state procedure
readiness/drain barriers
```

Suggested branch:

```text
feat/v0.3-i3-airflow-runtime-profile
```

No production semantic fix unless required for general setup correctness. This task carries the
Phase B (§48) responsibility for whichever I3.1 items were left provisional pending independent
raw telemetry: it SHALL complete that qualification and finalize the §49 freeze gate for those
items (amending `expected.yaml` if the evidence supports a qualified relation) before I3.3 runs the
first AIP comparison.

---

### I3.3 — First Comparison and Findings

Deliver:

```text
first qualifying live run
normalized actual result capture
deterministic comparison
results.md
findings.md
identity findings
messaging findings
coverage findings
decision records
```

Suggested branch:

```text
docs/v0.3-i3-airflow-results
```

No expected-ground-truth edits after seeing AIP output unless the original ground truth is proven
factually wrong by independent evidence; such a correction SHALL have a visible audit trail and
requires re-freeze plus a fresh qualifying run.

---

### I3.4 — Airflow Hardening and Final Revalidation

Only approved general fixes are allowed.

Deliver as required:

```text
general production fix
distilled regression tests
Quarkus impact check
fresh Airflow clean-state rerun
second same-contract qualifying comparison
repeatability proof
final I3 result
```

Suggested branch:

```text
fix/v0.3-i3-airflow-hardening
```

If no production fix is required, I3.4 becomes a documentation/revalidation PR rather than being
omitted, because I3 repeatability still requires the second clean qualifying run.

---

## 71. Ground-Truth Review Checklist

Before the first AIP comparison:

- [ ] Airflow release is `3.3.1`.
- [ ] Full upstream SHA is `3adbbe1c58e4532df1964cb7794805e763816ee8`.
- [ ] All repository evidence uses pinned permalinks.
- [ ] Official public OpenAPI is the declared REST source.
- [ ] REST operation subset was selected independently.
- [ ] Service-boundary interpretation was written before AIP output.
- [ ] Runtime role and runtime instance are explicitly distinguished.
- [ ] Multiple workers do not automatically imply multiple logical Services.
- [ ] Redis is described as broker technology, not pre-labeled as Queue identity.
- [ ] The actual Celery task queue name is frozen independently.
- [ ] PostgreSQL dependencies are recorded as unsupported by the current relation model.
- [ ] Execution API is not silently equated with the public API.
- [ ] Native OTel resource identities were inspected independently.
- [ ] Any extra Celery instrumentation was selected before AIP comparison and version-pinned.
- [ ] Runtime expected facts are supported by independent raw telemetry.
- [ ] No AIP-specific AsyncAPI/manifest was created to improve the result.
- [ ] Expected canonical IDs are normalization artifacts, not copied from AIP output.
- [ ] Ambiguous items are unresolved or insufficient, not guessed.

---

## 72. Definition of Done

I3 is complete when all mandatory conditions below are satisfied.

### Upstream

- [ ] `apache/airflow` is pinned to `3adbbe1c58e4532df1964cb7794805e763816ee8`.
- [ ] Airflow release `3.3.1` is recorded.
- [ ] Apache-2.0 license is recorded.
- [ ] Official Compose and OpenAPI references are pinned.
- [ ] Exact runtime image/provider/instrumentation versions are recorded.
- [ ] Selected runtime profile is reproducible.

### Ground Truth

- [ ] `upstream.md` complete.
- [ ] `profile.md` complete.
- [ ] `ground-truth.md` complete.
- [ ] `expected.yaml` frozen before qualifying AIP output.
- [ ] Logical Service boundary independently analyzed.
- [ ] Runtime role vs instance distinction documented.
- [ ] Bounded REST provider scope independently established.
- [ ] Celery queue/broker semantics independently established.
- [ ] PostgreSQL boundary classified.
- [ ] Ground truth not derived from AIP output.

### Runtime

- [ ] Airflow starts from clean state.
- [ ] AIP starts from clean state.
- [ ] CeleryExecutor active.
- [ ] Redis broker active.
- [ ] PostgreSQL active.
- [ ] API server ready.
- [ ] Scheduler ready.
- [ ] Worker(s) ready.
- [ ] Validation Dag loaded.
- [ ] Official OpenAPI imported.
- [ ] Native OTLP reaches Collector.
- [ ] OTLP reaches AIP.
- [ ] Validation environment/window explicit.
- [ ] Deterministic traffic executes successfully.
- [ ] Dag completes successfully.
- [ ] Telemetry drain succeeds.
- [ ] Cleanup succeeds.

### Identity

- [ ] API server identity reviewed.
- [ ] Scheduler identity reviewed.
- [ ] Worker role identity reviewed.
- [ ] Worker instance identity reviewed.
- [ ] Dag processor/triggerer identity behavior reviewed.
- [ ] No runtime instance is silently promoted to a false logical Service.
- [ ] No architecturally distinct identity is falsely merged where that creates a supported false claim.
- [ ] Ambiguous cases are explicitly classified.

### REST

- [ ] Selected `/api/v2` PROVIDES facts compared.
- [ ] Route templates remain low-cardinality.
- [ ] Concrete Dag/DagRun IDs do not become canonical operation identities.
- [ ] Execution API boundary is explicitly classified.

### Messaging

- [ ] Celery task queue is exercised.
- [ ] Broker vs queue identity is preserved.
- [ ] Producer direction independently established.
- [ ] Consumer direction independently established.
- [ ] Native/raw messaging telemetry inspected.
- [ ] `SENDS` / `RECEIVES_FROM` expected only where safely qualified.
- [ ] No unsupported messaging mechanism is coerced into a false supported fact.

### Coverage / Evidence

- [ ] Raw OTel resource identity evidence retained in compact sanitized form.
- [ ] Declared and observed evidence remain distinct.
- [ ] Runtime absence is window/coverage qualified.
- [ ] No evidence is fabricated or dropped.
- [ ] Startup and late-flush telemetry do not invalidate the observation window.

### Comparison

- [ ] All frozen expected supported facts compared.
- [ ] Unexpected in-scope supported facts surfaced.
- [ ] All material findings use I1 vocabulary.
- [ ] Summary counters deterministic.
- [ ] Two clean qualifying runs produce the same semantic result.
- [ ] Deterministic ordering verified.

### Hardening

- [ ] Every material production change has a decision record.
- [ ] Every accepted fix is general, not Airflow-specific.
- [ ] Every accepted fix has deterministic regression coverage.
- [ ] Major canonical redesign proposals carried to I4 unless urgently required to remove a false supported claim.

### Regression / Quality

- [ ] v0.2 evaluation remains `10/10 PASS`.
- [ ] Quarkus impact assessed for I3 production changes.
- [ ] Unit tests green.
- [ ] Integration tests green.
- [ ] I1 validation-contract tests green.
- [ ] Ruff green.
- [ ] CI green.
- [ ] CodeQL green.
- [ ] Dependency audit green.
- [ ] I3 release blockers = `0`.

---

## 73. Exit State

At the end of I3:

```text
I1 validation method
    FROZEN

Quarkus evidence
    COMPLETE

Airflow upstream
    PINNED

Airflow profile
    REPRODUCIBLE

Airflow identity model
    INDEPENDENTLY CLASSIFIED

Airflow ground truth
    FROZEN

Airflow qualifying comparison
    COMPLETE

Airflow repeatability
    VERIFIED

Airflow findings
    CLASSIFIED

Critical Airflow supported-semantic errors
    0

Cross-system model decision
    NOT FINAL
```

The complete Quarkus and Airflow finding sets become input to I4.

---

## 74. Relationship to I4

I4 receives two intentionally different bodies of evidence:

```text
Quarkus Super Heroes

    microservice-like external reference
    REST
    gRPC boundary
    Kafka topic boundary

Apache Airflow

    mature distributed OSS
    public REST API
    scheduler / worker roles
    Celery competing-consumer queue
    Redis broker
    PostgreSQL dependency
    process / instance identity stress
```

I4 SHALL compare these findings before making broad canonical changes.

Especially important cross-system questions include:

```text
Does Service need refinement?

Does runtime identity need an explicit
role/instance distinction?

Does the messaging model need only
better qualification, or richer entities?

Is Queue sufficient for real
competing-consumer semantics?

Are database dependencies important enough
for a future canonical relation family?

Which gaps are model defects versus
unsupported discovery capabilities?
```

---

## 75. Relationship to the Fundamental-Redesign Gate

Airflow is the strongest v0.3 test of whether the current Canonical Architecture Model can survive
real systems.

At I3 exit, every finding that may imply a fundamental redesign SHALL be explicitly marked for I4.

I3 SHALL NOT hide such a finding by:

```text
renaming runtime services
dropping difficult components from discussion
inventing AIP declarations
narrowing scope after seeing the result
```

If Airflow shows that a supported current claim is fundamentally false, the result is valuable even
if it creates work for I4.

The purpose of v0.3 is to discover that before v0.4 exposes the model more broadly.

---

## 76. Implementation Notes

The preferred implementation sequence is:

```text
I3.1
freeze upstream + identity + ground truth

I3.2
make the exact Airflow profile and raw OTel
reproducible without relying on AIP output

I3.3
run AIP once and classify what happens

I3.4
apply only approved general fixes
and prove same-contract repeatability
```

Do not combine all four steps into one opaque implementation commit.

The repository history is part of the proof that ground truth preceded AIP results.

---

## 77. Research Baseline Used for This Specification

At specification time, the following upstream facts were verified:

```text
Apache Airflow stable release:
    3.3.1
    released 2026-08-12

Git tag:
    3.3.1

Tag object:
    8d7af742565409cf8857c92c1cec98568dae4296

Pinned commit:
    3adbbe1c58e4532df1964cb7794805e763816ee8

Public OpenAPI:
    airflow-core/src/airflow/api_fastapi/core_api/openapi/
    v2-rest-api-generated.yaml

Official local Celery profile:
    airflow-core/docs/howto/docker-compose/docker-compose.yaml

Profile executor:
    CeleryExecutor

Profile broker:
    Redis

Profile metadata/result backend:
    PostgreSQL

Public REST prefix:
    /api/v2

Native tracing:
    OpenTelemetry supported by Airflow
```

Reference URLs:

```text
https://github.com/apache/airflow/tree/3adbbe1c58e4532df1964cb7794805e763816ee8

https://github.com/apache/airflow/blob/3adbbe1c58e4532df1964cb7794805e763816ee8/airflow-core/docs/howto/docker-compose/docker-compose.yaml

https://github.com/apache/airflow/blob/3adbbe1c58e4532df1964cb7794805e763816ee8/airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml

https://airflow.apache.org/docs/apache-airflow/3.3.1/core-concepts/overview.html

https://airflow.apache.org/docs/apache-airflow/3.3.1/stable-rest-api-ref.html

https://airflow.apache.org/docs/apache-airflow/3.3.1/administration-and-deployment/logging-monitoring/traces.html
```

Provider-specific Celery documentation SHALL be version-pinned in `upstream.md` when the I3 runtime
profile freezes its exact installed provider version.

---

## 78. Summary

I3 is not intended to prove that AIP can enumerate every part of Apache Airflow.

It is intended to test whether AIP remains semantically trustworthy when the external architecture is
not naturally microservice-shaped.

The defining rules are:

```text
pin real Airflow
use its real public OpenAPI
use its real CeleryExecutor topology
preserve Redis broker vs queue distinction
observe native runtime identity before rewriting anything
distinguish process, role, instance, and logical Service
freeze ground truth before AIP comparison
never manufacture declarations to improve the score
prefer unresolved/unsupported over guessed
fix only general semantic defects
prove the final comparison twice from clean state
```

The most important success criterion is:

> **Within the semantics AIP claims to support, Apache Airflow must not cause AIP to invent false
> logical services, false operation identities, false messaging destinations, false relation
> directions, false runtime statuses, or fabricated evidence. Where Airflow exposes architecture
> outside the current model, that boundary must remain explicit and auditable.**

`v0.3.0-alpha.3` is complete when the Airflow validation is independently grounded, reproducible,
identity-aware, fully classified, and free of unresolved critical supported-semantic errors.
