# Decision: Messaging Operation-Attribute Compatibility

Spec §10.1 / §9 question 3. Covers ledger findings `qsh-kafka-operation-type-gap`,
`airflow-celery-messaging-runtime-status`, and `i4-celery-instrumentation-semconv-mismatch`.

## Context

`app/telemetry/adapter.py::correlate_queue_observations()` recognizes exactly one attribute for
messaging-operation classification: `messaging.operation.type` (`app/telemetry/semconv/
messaging.py`'s `MESSAGING_OPERATION_TYPE`), with values `send`/`receive`/`process`. A span
carrying no recognized value for this attribute is silently skipped - not reported as unresolved,
per the function's own docstring.

I2.3 found that Quarkus's SmallRye Reactive Messaging Kafka connector emits the legacy
`messaging.operation` attribute (no `.type` suffix) with value `publish`, and deferred a decision
on recognizing it pending Airflow's own messaging evidence (`qsh-kafka-operation-type-gap.md`).
I4 now has that second system's evidence.

## Independent evidence

Three distinct, independently captured real-world attribute shapes exist for the same general
question ("how does this system's OTel instrumentation describe a messaging operation"):

```text
AIP's current allowlist (app/telemetry/semconv/messaging.py):
    messaging.operation.type: send | receive | process
    messaging.destination.name

Quarkus / SmallRye Reactive Messaging Kafka connector (I2.3, verified against real span):
    messaging.operation: publish
    messaging.destination.name: fights
    messaging.system: kafka

Airflow / opentelemetry-instrumentation-celery==0.65b0 (I3.2 diagnostic-only capture,
docs/real-world-validation/apache-airflow/profile.md's "Standard Celery instrumentation
decision" section):
    messaging.destination_kind: queue
    messaging.destination: default
    (no operation attribute of any name; no messaging.system)
```

## Alternatives considered

1. **Widen `MESSAGING_OPERATION_TYPE` recognition to also accept `messaging.operation`** (the
   legacy, non-suffixed key), mapping `publish` -> `SENDS`, `consume`/`receive` -> `RECEIVES_FROM`.
   This would close the Quarkus gap. It does nothing for Airflow: Airflow's span has no
   `messaging.operation` key at all (legacy or current), and its destination-name attribute is
   `messaging.destination`, not `messaging.destination.name` - the resolver's very first read
   would still miss it. A widening built for Quarkus's shape is a single-system fix dressed as a
   general one; spec §8's admission gate requires general applicability across both systems, not
   just one.
2. **Additionally recognize `messaging.destination_kind`/`messaging.destination`** to also cover
   Airflow's shape. This is a second, independent widening with its own attribute-name and
   precedence questions (spec §10.1 requires "conflicting attributes have deterministic
   precedence" and "regression tests cover current, legacy, conflicting, missing, and unknown
   forms" for *each* recognized shape) - i.e., two separate general rules bundled as one PR, each
   needing its own safety case. Nothing in either dossier demonstrates this combination is safe;
   it would be built from two data points, not evidenced as general.
3. **Defer both, name the missing prerequisite.** Chosen.

## Decision

`DEFER` for both `qsh-kafka-operation-type-gap` and
`airflow-celery-messaging-runtime-status`/`i4-celery-instrumentation-semconv-mismatch`.

## General semantic rule

None adopted. The rule this decision explicitly declines to write, until evidenced: *"AIP
recognizes messaging-operation attributes under [set of attribute-name/value mappings], with
deterministic precedence when more than one is present, and only when paired with the
topic-vs-queue safety guard in `decisions/queue-topic-boundary.md`."* Two real systems produced two
non-overlapping legacy shapes; a rule built from either alone is not general, and a rule combining
both is not evidenced as safe (see `decisions/queue-topic-boundary.md` for the specific blocking
risk on Quarkus's side).

## Consequences

- No change to `correlate_queue_observations()` or `MESSAGING_OPERATION_TYPE` recognition.
- `qsh-kafka-operation-type-gap` remains `INSUFFICIENT_EVIDENCE`; the underlying
  `qsh-kafka-fights-topic` classification (`UNSUPPORTED`) is unaffected either way.
- `airflow-celery-messaging-runtime-status` remains `INSUFFICIENT_EVIDENCE`, now with a third,
  independently-shaped piece of real evidence on record (`i4-celery-instrumentation-semconv-
  mismatch`) rather than only the absence-of-native-attributes observation I3.2 recorded.
- Neither system's `SENDS`/`RECEIVES_FROM` fact count changes.

## Production changes

None.

## Regression coverage

None required (no implementation change). If a future iteration widens attribute recognition, it
SHALL add, per spec §10.1: (1) a regression test proving each newly recognized shape, (2) a
regression test proving deterministic precedence when current/legacy/conflicting attributes are
all present on one span, (3) a regression test proving missing/unknown forms remain unresolved
rather than guessed, and (4) the topic-vs-queue safety guard's own regression test
(`decisions/queue-topic-boundary.md`).

## Quarkus impact

None. `qsh-kafka-fights-topic` and `qsh-kafka-operation-type-gap` stand exactly as I2.3 left them.

## Airflow impact

None. `airflow-celery-messaging-runtime-status` stands exactly as I3.2 left it, now cross-
referenced by this cross-system record.

## Deferred work

A future iteration MAY revisit this once a general, evidenced attribute-recognition rule exists
that (a) covers both Quarkus's and Airflow's real shapes (or explicitly scopes to a named subset
with a stated reason), (b) states deterministic precedence, and (c) is paired with the
topic-vs-queue safety guard in `decisions/queue-topic-boundary.md` so that widening recognition
cannot, by itself, convert a topic-shaped messaging system into a canonical `Queue` fact.
