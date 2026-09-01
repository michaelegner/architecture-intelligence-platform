# Decision: Queue-versus-Topic Safety

Spec §10.2 / §9 question 4. Covers ledger finding `qsh-kafka-fights-topic`.

## Context

Quarkus's `fights` Kafka topic is `UNSUPPORTED` by design - Kafka's topic/fan-out semantics are
deliberately outside the Canonical Model's competing-consumer `Queue` abstraction (project
CLAUDE.md, spec §26 of the parent v0.3 spec, `qsh-kafka-fights-topic`). I4 must confirm this
boundary stays safe, independent of whatever is decided in
`decisions/messaging-operation-compatibility.md`.

## Independent evidence

Read directly from current production source (`app/telemetry/queue_resolver.py::resolve_queue()`
and `app/telemetry/adapter.py::correlate_queue_observations()`, both re-read for this decision):

```python
# queue_resolver.py — resolve_queue()
if destination_name in aliases:
    return QueueResolution(aliases[destination_name], DiscoveryStatus.DECLARED)

minted_id = ids.queue_id(destination_name, namespace=messaging_system)
return QueueResolution(minted_id, DiscoveryStatus.OBSERVED_ONLY)
```

Any destination name not matched against a declared AsyncAPI Queue is minted as a new
`OBSERVED_ONLY` Queue - there is no refusal path. `correlate_queue_observations()` then
unconditionally builds a `SENDS`/`RECEIVES_FROM` `ObservedFactCandidate` for that resolution once
`messaging.operation.type` and `messaging.destination.name` are both present and recognized.

This means the resolver itself carries no topic-vs-queue distinction at all today - the only
reason Quarkus's `fights` topic currently produces zero `SENDS`/`RECEIVES_FROM` facts is that its
span's `messaging.operation` attribute name is not `messaging.operation.type`, so
`correlate_queue_observations()` never reaches `resolve_queue()` for that span in the first place
(confirmed in `qsh-kafka-operation-type-gap.md` and reconfirmed here by direct code reading).

## Alternatives considered

1. **Do nothing to the resolver; keep operation-attribute recognition narrow (the status quo).**
   Chosen - see Decision.
2. **Widen operation-attribute recognition without adding a topic-safety guard.** Rejected: per the
   evidence above, this would make Kafka's `fights` topic pass straight through
   `correlate_queue_observations()` into `resolve_queue()`, which would mint it as an
   `OBSERVED_ONLY` Queue and produce a `SENDS` fact - exactly the false "Kafka topic represented as
   competing-consumer Queue" claim spec §10.2 exists to prevent. This is the concrete mechanism
   `decisions/messaging-operation-compatibility.md` cites as the reason a bare attribute widening
   cannot be approved as `FIX` on its own.
3. **Design an explicit topic-safety guard (e.g. a `messaging.system` allowlist/denylist, or a
   required destination-kind check) and pair it with any future attribute widening.** Not
   implemented in I4.1 - no evidence yet establishes which guard shape is general and safe across
   more than the one Kafka case observed. Named as the explicit prerequisite for any future `FIX`.

## Decision

`DOCUMENT_UNSUPPORTED` (retained). The current absence of a topic-safety guard is not itself a
defect requiring `FIX`, because no attribute widening is approved in this iteration - see
`decisions/messaging-operation-compatibility.md`. Kafka topic/fan-out semantics remain outside
`Queue` scope; `qsh-kafka-fights-topic` stays `UNSUPPORTED`, unchanged.

## General semantic rule

`recognized telemetry != qualified canonical Queue semantics` (spec §10.2, restated as the
governing rule): a messaging span SHALL produce `SENDS`/`RECEIVES_FROM` only when destination kind
and interaction semantics are safely compatible with the current competing-consumer Queue model.
Recognizing an *attribute* is not the same decision as qualifying a *destination* as a Queue; the
two must not be conflated by any future implementation change.

## Consequences

- `resolve_queue()` and `correlate_queue_observations()` are unchanged.
- The dependency this decision creates on `decisions/messaging-operation-compatibility.md` is now
  explicit and traceable: any future attempt to widen operation-attribute recognition MUST first
  satisfy this decision's guard requirement, not treat it as a separate, later concern.
- No topic/subscription canonical family is introduced (spec §12 forbids this absent a
  release-blocking false claim; none exists - zero facts are currently emitted for the `fights`
  topic).

## Production changes

None.

## Regression coverage

None required now. Named prerequisite for any future `FIX` here: a regression test proving that,
even with widened operation-attribute recognition, a topic-shaped messaging system (e.g. one
carrying `messaging.system: kafka` with fan-out/broadcast semantics) still does not produce a
`SENDS`/`RECEIVES_FROM` fact - i.e., a test that fails today would demonstrate the guard is
missing, and must pass before any attribute widening is merged.

## Quarkus impact

None. `qsh-kafka-fights-topic` stands exactly as I2.1-I2.3 left it.

## Airflow impact

None directly - Airflow has no Kafka/topic mechanism. Relevant only as the second data point
confirming that any future attribute-recognition widening is a cross-cutting change requiring this
same guard, not a Quarkus-only concern.

## Deferred work

Design and evidence a general topic-vs-queue safety guard before any future iteration approves
widening `messaging.operation`/`messaging.operation.type` recognition. This guard is a hard
precondition for that `FIX`, not an independent nice-to-have. A parallel, equally necessary
precondition exists on the Service-identity side of the same widening -
`decisions/messaging-operation-compatibility.md` documents that `resolve_service()` has the
identical unconditional-minting shape as `resolve_queue()`.
