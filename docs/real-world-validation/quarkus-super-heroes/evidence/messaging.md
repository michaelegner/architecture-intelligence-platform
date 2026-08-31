# Evidence — Kafka `fights` Topic Boundary

All permalinks are rooted at:

```text
https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/
```

## Producer

[`rest-fights/src/main/resources/application.properties`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/src/main/resources/application.properties):

```properties
mp.messaging.outgoing.fights.connector=smallrye-kafka
mp.messaging.outgoing.fights.topic=fights
mp.messaging.outgoing.fights.apicurio.registry.auto-register=true
```

[`rest-fights/README.md`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/rest-fights/README.md):

> Fight messages are also published on an Apache Kafka topic called `fights`. The
> [event-statistics service](../event-statistics) listens for these events. Messages are stored in
> [Apache Avro](https://avro.apache.org/docs/current) format and the fight schema is automatically
> registered in the [Apicurio Schema Registry](https://www.apicur.io/registry).

## Consumer

[`event-statistics/src/main/resources/application.properties`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/event-statistics/src/main/resources/application.properties):

```properties
mp.messaging.incoming.fights.connector=smallrye-kafka
mp.messaging.incoming.fights.topic=fights
mp.messaging.incoming.fights.auto.offset.reset=earliest
```

[`event-statistics/README.md`](https://github.com/quarkusio/quarkus-super-heroes/blob/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce/event-statistics/README.md):

> This is the event statistics microservice. It is an event-driven microservice, listening for
> fight event messages on an [Apache Kafka](https://kafka.apache.org/) topic utilizing
> [SmallRye Reactive Messaging](https://quarkus.io/guides/kafka). Messages arrive on the `fights`
> topic.

## Classification rationale

Both ends independently name the same Kafka topic (`fights`) and the same transport
(`smallrye-kafka`), corroborated by both services' own READMEs in prose. That is strong evidence of
a real producer/consumer relationship — but per I2 spec §13-14, a Kafka **topic** is a
publish/subscribe destination, not AIP's queue-with-competing-consumers model, and a
one-producer/one-consumer topic must not be assumed to collapse onto Queue semantics merely because
the multiplicities happen to match a Queue's shape. This is recorded as `unsupported` ground truth
(mechanism `kafka-topic`), not as a `SENDS`/`RECEIVES_FROM` expectation.

## Runtime telemetry evidence (I2.3, PR #41 re-review)

A dedicated diagnostic re-run of the qualifying profile (same pinned commit/images, Collector
temporarily set to `verbosity: detailed` for this inspection only — no committed runtime file
changed) captured the actual raw OTLP span `rest-fights` exports for its Kafka publish:

```text
Attributes:
  messaging.kafka.offset: 0
  messaging.destination.name: fights
  messaging.operation: publish
  messaging.client_id: kafka-producer-fights
  messaging.system: kafka
```

This confirms the interaction is real (a genuine Kafka producer span, correct destination name,
correct system) but also reveals that Quarkus's SmallRye Reactive Messaging Kafka connector emits
the attribute key `messaging.operation` (legacy OTel messaging semantic convention, value
`publish`), not `messaging.operation.type` (`app/telemetry/semconv/messaging.py`'s
`MESSAGING_OPERATION_TYPE`, the only attribute name AIP's `correlate_queue_observations()` checks).
No consumer-side (`event-statistics`) messaging span was observed in the Collector's export stream
in this window at all. See
[`decisions/qsh-kafka-operation-type-gap.md`](../decisions/qsh-kafka-operation-type-gap.md) for the
resulting finding and disposition, and `results.md`/`findings.md` for how this reclassifies what the
qualifying run's "0 SENDS/RECEIVES_FROM" result actually demonstrates.
