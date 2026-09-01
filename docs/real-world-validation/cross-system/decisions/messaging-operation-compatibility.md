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

Spec §8's admission gate does **not** require a change to work across both systems: "a change
justified by one system MAY be accepted only when it corrects a general semantic-convention
compatibility defect or prevents an objectively false supported fact, and when the rule can be
tested independently of upstream-specific names and topology." A Quarkus-only-observed attribute
shape can still be a legitimate `FIX` candidate if the recognized rule itself is general (keyed on
attribute name/value, not on "Quarkus" or "fights"). The reasoning below therefore does not reject
widening because it fails to also cover Airflow - it rejects widening because two of §10.1's own
required safety conditions are not yet satisfiable, independent of which system's shape is in
scope.

## Independent evidence — a second, previously unexamined safety gap

Re-reading `app/telemetry/service_resolver.py::resolve_service()` for this decision (used via
`resolve_runtime_span()` inside `correlate_queue_observations()`) shows it has the **same**
unconditional-minting shape as `resolve_queue()`:

```python
# service_resolver.py — resolve_service(), Tier 4
minted_id = ids.service_id(_slugify(service_name), namespace=service_namespace)
return ServiceResolution(minted_id, DiscoveryStatus.OBSERVED_ONLY)
```

Any unmatched `service_name` - including a generic, ambiguous one like Airflow's
`service.name: unknown_service` (`airflow-runtime-role-identity`) - is minted as an `OBSERVED_ONLY`
Service with no refusal path. Today this never executes for Airflow's messaging spans, because
`correlate_queue_observations()`'s operation-attribute check runs *before* `resolve_runtime_span()`
is ever called, so an unrecognized-shape span (Airflow's) is filtered out first. But that means
Airflow's current zero `SENDS`/`RECEIVES_FROM` result is evidence of a narrow attribute allowlist,
**not** evidence that a resolved-identity prerequisite is already safely enforced. If operation-
attribute recognition were ever widened to reach Airflow's shape, the same generic `unknown_service`
name - shared across four architecturally distinct roles - would be minted as one merged
`OBSERVED_ONLY` Service and could produce a messaging fact that conflates those roles. This is a
second, independent blocking condition alongside the Queue/topic one below, not something either
dossier's run-level evidence currently proves safe.

## Alternatives considered

1. **Widen `MESSAGING_OPERATION_TYPE` recognition to also accept `messaging.operation`** (the
   legacy, non-suffixed key), mapping `publish` -> `SENDS`, `consume`/`receive` -> `RECEIVES_FROM`.
   Eligible in principle under §8 (the rule itself would be general, keyed on attribute name/value).
   Blocked in practice by two of §10.1's own required conditions not yet being satisfied for *any*
   widening of this kind: (a) "recognition does not itself convert a Kafka topic into a canonical
   Queue" - no such guard exists (`decisions/queue-topic-boundary.md`); (b) an equivalent guard is
   now also needed on the identity side, since `resolve_service()`'s Tier 4 would mint an
   unqualified Service for any newly-reachable span exactly as `resolve_queue()` mints an
   unqualified Queue (see evidence above). Rejected for this iteration on those two grounds, not
   because Airflow's shape differs.
2. **Additionally recognize `messaging.destination_kind`/`messaging.destination`** to also cover
   Airflow's shape. Independently blocked by the same two conditions as (1), plus its own
   unmapped precedence/conflict questions (spec §10.1: "conflicting attributes have deterministic
   precedence," "regression tests cover current, legacy, conflicting, missing, and unknown
   forms"). Rejected for this iteration.
3. **Defer both, name the missing prerequisites explicitly.** Chosen.

## Decision

`DEFER` for `qsh-kafka-operation-type-gap`, `airflow-celery-messaging-runtime-status`, and
`i4-celery-instrumentation-semconv-mismatch`. Each is blocked by the same two unmet safety
conditions (Queue/topic guard, Service-identity guard), not by a requirement that one rule solve
both systems' distinct shapes at once.

## General semantic rule

None adopted. The rule this decision explicitly declines to write, until evidenced: *"AIP
recognizes messaging-operation attributes under [set of attribute-name/value mappings], with
deterministic precedence when more than one is present, only when paired with the topic-vs-queue
safety guard in `decisions/queue-topic-boundary.md`, and only when paired with an equivalent
identity-safety guard preventing an ambiguous/generic `service.name` from being minted as a
qualified Service for a messaging fact."* Neither guard exists today, independent of which
system's attribute shape a future rule targets.

## Consequences

- No change to `correlate_queue_observations()`, `MESSAGING_OPERATION_TYPE` recognition, or
  `resolve_service()`.
- `qsh-kafka-operation-type-gap` remains `INSUFFICIENT_EVIDENCE`; the underlying
  `qsh-kafka-fights-topic` classification (`UNSUPPORTED`) is unaffected either way.
- `airflow-celery-messaging-runtime-status` moves from its I3.2 `NO_CHANGE`-leaning framing to an
  explicit `DEFER`, now naming two concrete prerequisites (Queue/topic guard, Service-identity
  guard) instead of only "identity remains unresolved."
- Neither system's `SENDS`/`RECEIVES_FROM` fact count changes.

## Production changes

None.

## Regression coverage

None required (no implementation change). If a future iteration widens attribute recognition, it
SHALL add, per spec §10.1: (1) a regression test proving each newly recognized shape, (2) a
regression test proving deterministic precedence when current/legacy/conflicting attributes are
all present on one span, (3) a regression test proving missing/unknown forms remain unresolved
rather than guessed, (4) the topic-vs-queue safety guard's own regression test
(`decisions/queue-topic-boundary.md`), and (5) a regression test proving a generic/ambiguous
`service.name` does not get silently qualified as a Service for a newly-recognized messaging fact.

## Quarkus impact

None. `qsh-kafka-fights-topic` and `qsh-kafka-operation-type-gap` stand exactly as I2.3 left them.

## Airflow impact

None to graph state. `airflow-celery-messaging-runtime-status`'s classification is unchanged; its
disposition is corrected from I3.2's `NO_CHANGE`-leaning framing to `DEFER`, and its rationale now
names the identity-safety gap explicitly rather than treating it as already closed.

## Deferred work

A future iteration MAY revisit this once a general, evidenced attribute-recognition rule exists
that (a) is keyed on attribute name/value semantics rather than upstream-specific names, (b) states
deterministic precedence, (c) is paired with the topic-vs-queue safety guard in
`decisions/queue-topic-boundary.md`, and (d) is paired with an equivalent Service-identity guard so
that widening recognition cannot, by itself, either convert a topic-shaped messaging system into a
canonical `Queue` fact or mint a qualified Service from an ambiguous/generic observed name.
