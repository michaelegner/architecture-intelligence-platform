# I4 Finding Ledger

Normalized per spec §6, covering the mandatory seven-row inventory plus one new material finding
discovered while assembling this ledger. Every finding was independently reconfirmed against its
source dossier and, where relevant, the actual current production source — no disposition below
restates a prior disposition without re-checking it against the code as it stands today.

## `qsh-grpc-locations`

```text
source system(s):              Quarkus Super Heroes
independent evidence:          docs/real-world-validation/quarkus-super-heroes/findings.md
current classification:        UNSUPPORTED / severity INFO
claimed AIP semantic scope:    none - gRPC/protobuf is outside the Canonical Model entirely
cross-system relevance:        none - Airflow has no gRPC involvement to cross-check against
candidate disposition:         NO_CHANGE
decision record:               none required (spec §12: explicit unsupported behavior needs no
                                record when AIP makes no incorrect supported claim)
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             NO_CHANGE
```

Confirmed unaffected by any Airflow finding; no cross-system question applies.

## `qsh-kafka-fights-topic`

```text
source system(s):              Quarkus Super Heroes
independent evidence:          docs/real-world-validation/quarkus-super-heroes/findings.md,
                                docs/real-world-validation/quarkus-super-heroes/evidence/messaging.md
current classification:        UNSUPPORTED / severity INFO
claimed AIP semantic scope:    none - Kafka topic/fan-out semantics are explicitly out of Queue scope
cross-system relevance:        directly implicated by the messaging-operation-compatibility question
                                below - see decisions/queue-topic-boundary.md
candidate disposition:         DOCUMENT_UNSUPPORTED (mechanism stays explicitly, deliberately
                                outside current AIP semantics - see decisions/queue-topic-
                                boundary.md for why NO_CHANGE would understate the resolver's lack
                                of a structural guard)
decision record:               decisions/queue-topic-boundary.md
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             DOCUMENT_UNSUPPORTED
```

Re-verified directly against `app/telemetry/queue_resolver.py::resolve_queue()`: any undeclared
destination name is minted as an `OBSERVED_ONLY` Queue and `correlate_queue_observations()` still
emits a `SENDS`/`RECEIVES_FROM` fact for it. Widening operation-attribute recognition without a
topic-safety guard would let this exact topic start producing a Queue fact - see
`decisions/queue-topic-boundary.md`.

## `qsh-kafka-operation-type-gap`

```text
source system(s):              Quarkus Super Heroes (evidence), Apache Airflow (cross-check)
independent evidence:          docs/real-world-validation/quarkus-super-heroes/decisions/
                                qsh-kafka-operation-type-gap.md; Airflow's Celery span evidence
                                below (i4-celery-instrumentation-semconv-mismatch)
current classification:        INSUFFICIENT_EVIDENCE / severity MINOR
claimed AIP semantic scope:    messaging.operation.type recognition in
                                app/telemetry/adapter.py::correlate_queue_observations()
cross-system relevance:        high - this is the finding I2.3's own decision record deferred
                                pending Airflow's messaging evidence (I4 mandatory question 3)
candidate disposition:         DEFER, reasoning strengthened by cross-system evidence
decision record:                decisions/messaging-operation-compatibility.md
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             DEFER
```

Airflow's own Celery span evidence (below) does not converge with Quarkus's gap onto one general
fix - see `decisions/messaging-operation-compatibility.md`.

## `airflow-scheduler-postgres-dependency` / `airflow-apiserver-postgres-dependency` / `airflow-celery-result-backend-postgres-dependency`

```text
source system(s):              Apache Airflow
independent evidence:          docs/real-world-validation/apache-airflow/findings.md
current classification:        UNSUPPORTED / severity INFO (x3)
claimed AIP semantic scope:    none - no database relation family exists in the Canonical Model
cross-system relevance:        none - Quarkus has no equivalent PostgreSQL-dependency finding
candidate disposition:         NO_CHANGE
decision record:               none required (spec §12 explicitly disallows adding a Database
                                family absent a release-blocking false claim; none exists)
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             NO_CHANGE
```

## `airflow-execution-api-boundary`

```text
source system(s):              Apache Airflow
independent evidence:          docs/real-world-validation/apache-airflow/findings.md
current classification:        UNRESOLVED_IDENTITY / severity MINOR
claimed AIP semantic scope:    CALLS (Service -> Operation) - correctly not claimed
cross-system relevance:        none - Quarkus's REST callers are all resolvable; no equivalent
                                private-API caller-identity ambiguity exists there
candidate disposition:         NO_CHANGE
decision record:               none required - already correctly unclaimed rather than guessed,
                                and no cross-system evidence resolves the ambiguity safely
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             NO_CHANGE
```

## `airflow-runtime-role-identity`

```text
source system(s):              Apache Airflow (evidence), Quarkus Super Heroes (cross-check)
independent evidence:          docs/real-world-validation/apache-airflow/findings.md,
                                docs/real-world-validation/apache-airflow/profile.md
current classification:        UNRESOLVED_IDENTITY / severity MINOR
claimed AIP semantic scope:    Service identity (canonical Service = {id, name, version?})
cross-system relevance:        high - I4 mandatory question 2 asks whether a role/instance
                                distinction is needed generally, not just for Airflow
candidate disposition:         DEFER (a named, real, but not-yet-cross-system-justified gap)
decision record:               decisions/runtime-role-identity.md
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             DEFER
```

Re-verified directly against `app/canonical/model.py`: `Service` remains `{id, name, version?}`
with no role/instance hierarchy - see `decisions/runtime-role-identity.md`.

## `airflow-celery-messaging-runtime-status`

```text
source system(s):              Apache Airflow
independent evidence:          docs/real-world-validation/apache-airflow/findings.md,
                                docs/real-world-validation/apache-airflow/profile.md
current classification:        INSUFFICIENT_EVIDENCE / severity MINOR
claimed AIP semantic scope:    SENDS/RECEIVES_FROM (messaging identity prerequisite, spec §10.3)
cross-system relevance:        high - shares the messaging-operation-compatibility question with
                                the Quarkus Kafka finding, and additionally exposes a second,
                                independent identity-safety gap (see below)
candidate disposition:         DEFER (semantic-convention gap and identity-safety prerequisite
                                both remain open; not yet a demonstrated defect requiring FIX)
decision record:               decisions/messaging-operation-compatibility.md
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             DEFER
```

Re-verified directly against `app/telemetry/service_resolver.py::resolve_service()`: its Tier 4
mints a deterministic `OBSERVED_ONLY` Service id for *any* unmatched `service_name` unconditionally
- there is no refusal path for a generic/ambiguous name such as Airflow's `unknown_service`. Today
this never executes for Airflow's messaging path because `correlate_queue_observations()` filters
the span earlier on its unrecognized operation attribute (see
`decisions/messaging-operation-compatibility.md`) - so the zero `SENDS`/`RECEIVES_FROM` result is
evidence that attribute recognition is narrow, not evidence that a resolved-identity prerequisite
is already enforced. See `decisions/messaging-operation-compatibility.md` and
`decisions/canonical-redesign-gate.md` (mandatory question 5) for the corrected reasoning.

## `i4-celery-instrumentation-semconv-mismatch` (new finding, discovered during I4.1)

```text
source system(s):              Apache Airflow
independent evidence:          docs/real-world-validation/apache-airflow/profile.md's "Standard
                                Celery instrumentation decision" section (I3.2's diagnostic-only,
                                non-frozen opentelemetry-instrumentation-celery==0.65b0 capture)
current classification:        INSUFFICIENT_EVIDENCE / severity MINOR (newly ledgered as its own
                                finding; the same evidentiary gap was previously recorded only as
                                part of airflow-celery-messaging-runtime-status's narrative, not
                                as its own inventory row with an independent attribute-shape
                                citation)
claimed AIP semantic scope:    messaging.operation.type / messaging.destination.name recognition
cross-system relevance:        decisive - this is a third, independently-shaped piece of real
                                evidence for I4 mandatory question 3, distinct from both AIP's
                                current allowlist and Quarkus's legacy shape
candidate disposition:         DEFER
decision record:               decisions/messaging-operation-compatibility.md
production impact:             none
test impact:                   none
validation impact:             none
final disposition:             DEFER
```

Airflow's diagnostic Celery producer span uses `messaging.destination_kind: queue` /
`messaging.destination: default` - neither a recognized `operation` attribute of any name
(current or legacy), nor the `messaging.destination.name` key AIP's resolver reads. This span
would remain unrecognized even under a Quarkus-shaped attribute widening.

## Summary table

| Finding | Current | Disposition |
|---|---|---|
| `qsh-grpc-locations` | UNSUPPORTED | NO_CHANGE |
| `qsh-kafka-fights-topic` | UNSUPPORTED | DOCUMENT_UNSUPPORTED |
| `qsh-kafka-operation-type-gap` | INSUFFICIENT_EVIDENCE | DEFER |
| Airflow PostgreSQL dependencies (x3) | UNSUPPORTED | NO_CHANGE |
| `airflow-execution-api-boundary` | UNRESOLVED_IDENTITY | NO_CHANGE |
| `airflow-runtime-role-identity` | UNRESOLVED_IDENTITY | DEFER |
| `airflow-celery-messaging-runtime-status` | INSUFFICIENT_EVIDENCE | DEFER |
| `i4-celery-instrumentation-semconv-mismatch` (new) | INSUFFICIENT_EVIDENCE | DEFER |

No `FIX` disposition results from this ledger. The approved production-change list for I4.2 is
empty (see `../README.md`).
