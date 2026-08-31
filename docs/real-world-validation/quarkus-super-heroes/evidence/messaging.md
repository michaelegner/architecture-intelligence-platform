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
